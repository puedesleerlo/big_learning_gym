"""Validated curriculum authoring. Authored content never becomes learner evidence.

Item corrections create a replacement identity: historical sessions, attempts and
rubric snapshots continue to refer to the exact question the learner encountered.
"""

from typing import Literal

import bleach
from pydantic import Field, HttpUrl, model_validator

from .contracts import GeneratedItem, Strict
from .importer import SAFE_TAGS
from .store import digest, now, uid


class RevisionConflict(ValueError):
    """The caller must read current state before changing it."""


class Provenance(Strict):
    author: str = Field(min_length=1, max_length=200)
    method: Literal["agent", "human", "import"] = "agent"
    rationale: str = Field(min_length=5, max_length=3000)
    reference_urls: list[HttpUrl] = Field(default_factory=list, max_length=100)


class Module(Strict):
    id: str = Field(min_length=1, max_length=120, pattern=r"^[A-Za-z0-9_.:-]+$")
    title: str = Field(min_length=2, max_length=200)
    description: str = Field(default="", max_length=5000)
    prerequisites: list[str] = Field(default_factory=list, max_length=100)
    objectives: list[str] = Field(default_factory=list, max_length=30)
    capabilities: list[str] = Field(default_factory=list, max_length=30)
    estimated_minutes: int = Field(default=30, ge=5, le=10000)
    level: Literal["beginner", "intermediate", "advanced", "frontier"] = "beginner"


class CourseWrite(Strict):
    expected_revision: int = Field(ge=0)
    title: str = Field(min_length=2, max_length=180)
    description: str = Field(default="", max_length=5000)
    modules: list[Module] = Field(default_factory=list, max_length=100)
    provenance: Provenance

    @model_validator(mode="after")
    def module_graph(self):
        by_id = {m.id: m for m in self.modules}
        if len(by_id) != len(self.modules):
            raise ValueError("Module IDs must be unique")
        visited, pending = set(), set()

        def visit(ident):
            if ident not in by_id:
                raise ValueError("Module prerequisite does not exist")
            if ident in pending:
                raise ValueError("Module prerequisites must not contain cycles")
            if ident in visited:
                return
            pending.add(ident)
            for other in by_id[ident].prerequisites:
                visit(other)
            pending.remove(ident)
            visited.add(ident)

        for ident in by_id:
            visit(ident)
        return self


class GuideBlock(Strict):
    id: str = Field(min_length=1, max_length=120)
    h: str = Field(min_length=1, max_length=200)
    html: str = Field(min_length=1, max_length=50000)


class GuideWrite(Strict):
    expected_revision: int = Field(ge=0)
    course_id: str
    code: str
    subtitle: str = Field(min_length=2, max_length=200)
    blocks: list[GuideBlock] = Field(min_length=1, max_length=100)
    source_fragment_ids: list[str] = Field(min_length=1, max_length=100)
    provenance: Provenance

    @model_validator(mode="after")
    def unique_blocks(self):
        if len({b.id for b in self.blocks}) != len(self.blocks):
            raise ValueError("Guide block IDs must be unique")
        return self


class TermWrite(Strict):
    expected_revision: int = Field(ge=0)
    course_id: str
    module: str
    term: str = Field(min_length=1, max_length=200)
    definition: str = Field(alias="def", min_length=5, max_length=5000)
    distinguish: str = Field(default="", max_length=3000)
    why: str = Field(default="", max_length=3000)
    source_fragment_ids: list[str] = Field(min_length=1, max_length=100)
    provenance: Provenance


class ItemWrite(GeneratedItem):
    expected_revision: int = Field(default=0, ge=0)
    course_id: str
    module: str
    pool: Literal["practice", "transfer"] = "practice"
    rubric_version_id: str | None = None
    term_ids: list[str] = Field(default_factory=list, max_length=100)
    provenance: Provenance


class RetireItem(Strict):
    expected_revision: int = Field(ge=1)
    provenance: Provenance


class GuideImport(GuideWrite):
    id: str = Field(min_length=1, max_length=200)


class TermImport(TermWrite):
    id: str = Field(min_length=1, max_length=200)


class ItemImport(ItemWrite):
    id: str = Field(min_length=1, max_length=200)


class MaterialImport(Strict):
    """An atomic batch; sources must already be uploaded and reviewed."""

    idempotency_key: str = Field(min_length=5, max_length=200)
    course_id: str
    course: CourseWrite | None = None
    guides: list[GuideImport] = Field(default_factory=list, max_length=100)
    terms: list[TermImport] = Field(default_factory=list, max_length=500)
    items: list[ItemImport] = Field(default_factory=list, max_length=500)

    @model_validator(mode="after")
    def own_materials(self):
        for collection in (self.guides, self.terms, self.items):
            if len({x.id for x in collection}) != len(collection):
                raise ValueError("Each material ID may occur only once in an import")
            if any(x.course_id != self.course_id for x in collection):
                raise ValueError("Imported material must belong to the declared course")
        if not self.course and not any((self.guides, self.terms, self.items)):
            raise ValueError("Import must contain material")
        return self


def _data(model):
    return model.model_dump(mode="json", by_alias=True, exclude={"expected_revision", "id"})


def _check_revision(old, expected):
    if (old["revision"] if old else 0) != expected:
        raise RevisionConflict("This record changed. Read the latest revision before saving.")


def _module(store, c, course_id, module):
    course = store.get(c, "course", course_id)
    if module not in {m["id"] for m in course.get("modules", [])}:
        raise ValueError("Material module must exist in this course")


def _references(store, c, data):
    refs = data["source_fragment_ids"]
    if len(set(refs)) != len(refs):
        raise ValueError("Source fragment references must be unique")
    for ident in refs:
        fragment = store.get(c, "fragment", ident)
        source = store.get(c, "source", fragment["source_version_id"])
        if fragment["course_id"] != data["course_id"] or source["course_id"] != data["course_id"]:
            raise ValueError("Source fragments must belong to this course")
        if source.get("reconstruction_status") != "confirmed":
            raise ValueError("Review and confirm source reconstruction before authoring from it")
        if source.get("role") not in {"instruction", "research", "rubric"}:
            raise ValueError("Author learning material from instruction, research, or rubric sources")


def _event(store, c, kind, result, previous=None):
    store.emit(
        c,
        "authoring." + kind,
        result["id"],
        {
            "record_revision": result["revision"],
            "previous_id": previous["id"] if previous else None,
            "previous_revision": previous["revision"] if previous else None,
            "content_hash": digest(
                {k: v for k, v in result.items() if k not in {"created_at", "updated_at"}}
            ),
            "source_fragment_ids": result.get("source_fragment_ids", []),
            "provenance": result["provenance"],
            "evidence_kind": "authored_content",
        },
        quality_flags=["authored_content_not_learner_performance"],
    )


def _save_course(store, c, ident, model):
    old = store.get(c, "course", ident, False)
    _check_revision(old, model.expected_revision)
    data = _data(model)
    modules = {m["id"] for m in data["modules"]}
    if old:
        removed = {m["id"] for m in old.get("modules", [])} - modules
        for kind, key in (("guide", "code"), ("term", "module"), ("item", "module")):
            if any(x["course_id"] == ident and x.get(key) in removed for x in store.list(c, kind)):
                raise ValueError("Cannot remove modules referenced by existing learning material")
        if any(lab["course_id"] == ident and any(
            (lesson.get("module") or lesson["id"]) in removed for lesson in lab["lessons"]
        ) for lab in store.list(c, "lab")):
            raise ValueError("Cannot remove modules referenced by published labs")
    result = store.put(c, "course", ident, {**(old or {}), **data, "updated_at": now()})
    _event(store, c, "course.saved", result, old)
    return result


def save_course(store, ident, data):
    model = CourseWrite.model_validate(data)
    with store.tx() as c:
        return _save_course(store, c, ident, model)


def _save_material(store, c, kind, ident, model):
    old = store.get(c, kind, ident, False)
    _check_revision(old, model.expected_revision)
    data = _data(model)
    if old and old["course_id"] != data["course_id"]:
        raise ValueError("Material cannot be moved between courses")
    _module(store, c, data["course_id"], data["code"] if kind == "guide" else data["module"])
    _references(store, c, data)
    if kind == "guide":
        for block in data["blocks"]:
            block["html"] = bleach.clean(
                block["html"],
                tags=SAFE_TAGS,
                attributes={"a": ["href", "title"], "th": ["colspan"], "td": ["colspan"]},
                protocols={"https", "http", "mailto"},
                strip=True,
            )
    result = store.put(c, kind, ident, {**data, "updated_at": now()})
    _event(store, c, kind + ".saved", result, old)
    return result


def save_guide(store, ident, data):
    with store.tx() as c:
        return _save_material(store, c, "guide", ident, GuideWrite.model_validate(data))


def save_term(store, ident, data):
    with store.tx() as c:
        return _save_material(store, c, "term", ident, TermWrite.model_validate(data))


def _save_item(store, c, ident, model):
    old = store.get(c, "item", ident, False)
    _check_revision(old, model.expected_revision)
    data = _data(model)
    if old and old["course_id"] != data["course_id"]:
        raise ValueError("An item cannot be moved between courses")
    if old and old["status"] == "retired":
        raise RevisionConflict("This item is retired. Revise its replacement instead.")
    _module(store, c, data["course_id"], data["module"])
    _references(store, c, data)
    rubric_id = data.get("rubric_version_id")
    if len(set(data["term_ids"])) != len(data["term_ids"]):
        raise ValueError("Glossary references must be unique")
    for term_id in data["term_ids"]:
        if store.get(c, "term", term_id)["course_id"] != data["course_id"]:
            raise ValueError("Glossary references must belong to this course")
    if rubric_id:
        rubric = store.get(c, "rubric_version", rubric_id)
        if rubric.get("course_id") and rubric["course_id"] != data["course_id"]:
            raise ValueError("Rubric must belong to this course")
        if data["type"] in {"mcq", "matching"}:
            raise ValueError("Pinned rubrics apply to open response items")
        if data["rubric"] != rubric["criteria"]:
            raise ValueError("Item rubric must exactly match its pinned rubric version")
    created_id = uid("item_") if old else ident
    data.update(
        status="active",
        verification="authored",
        created_at=now(),
        authored_version=(old.get("authored_version", 1) + 1 if old else 1),
        family_id=old.get("family_id", old["id"]) if old else ident,
        supersedes_item_id=old["id"] if old else None,
        rubric_version=rubric_id or "authored:" + digest(data["rubric"])[:20],
        form=None,
    )
    if old:
        store.put(c, "item", ident, {**old, "status": "retired", "replacement_item_id": created_id})
    result = store.put(c, "item", created_id, data)
    _event(store, c, "item.revised" if old else "item.created", result, old)
    return result


def save_item(store, data, ident=None):
    model = ItemWrite.model_validate(data)
    with store.tx() as c:
        return _save_item(store, c, ident or uid("item_"), model)


def retire_item(store, ident, data):
    model = RetireItem.model_validate(data)
    with store.tx() as c:
        old = store.get(c, "item", ident)
        _check_revision(old, model.expected_revision)
        result = store.put(
            c,
            "item",
            ident,
            {
                **old,
                "status": "retired",
                "provenance": model.provenance.model_dump(mode="json"),
            },
        )
        _event(store, c, "item.retired", result, old)
        return result


def import_materials(store, data):
    model = MaterialImport.model_validate(data)
    payload_hash = digest(model.model_dump(mode="json", by_alias=True))
    receipt_id = "authoring:" + digest(model.idempotency_key)
    with store.tx() as c:
        previous = store.get(c, "authoring_import", receipt_id, False)
        if previous:
            if previous["payload_hash"] != payload_hash:
                raise RevisionConflict("Idempotency key was already used for different import content")
            return {**previous["result"], "already_imported": True}
        result = {"course_id": model.course_id, "guides": [], "terms": [], "items": []}
        if model.course:
            result["course"] = _save_course(store, c, model.course_id, model.course)
        else:
            store.get(c, "course", model.course_id)
        for kind, collection in (("guide", model.guides), ("term", model.terms)):
            for entry in collection:
                result[kind + "s"].append(_save_material(store, c, kind, entry.id, entry))
        for entry in model.items:
            result["items"].append(_save_item(store, c, entry.id, entry))
        store.put(
            c,
            "authoring_import",
            receipt_id,
            {
                "payload_hash": payload_hash,
                "result": result,
                "created_at": now(),
            },
        )
        return {**result, "already_imported": False}
