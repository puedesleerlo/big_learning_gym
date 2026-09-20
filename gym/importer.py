"""Import the actual legacy gym, with answer keys kept on the server."""

import json
from pathlib import Path

import bleach

from .ingestion import ingest
from .store import digest

SAFE_TAGS = {
    "p",
    "strong",
    "em",
    "h1",
    "h2",
    "h3",
    "h4",
    "ul",
    "ol",
    "li",
    "table",
    "thead",
    "tbody",
    "tr",
    "td",
    "th",
    "blockquote",
    "code",
    "pre",
    "hr",
    "br",
    "a",
    "sup",
    "sub",
}


def import_legacy(store, root):
    root = Path(root).expanduser().resolve()
    raw = (root / "app/data.js").read_text()
    if not raw.startswith("window.GYM="):
        raise ValueError("Expected a JSON window.GYM bundle; JavaScript is never executed")
    bundle = json.loads(raw[len("window.GYM=") :].strip().removesuffix(";"))
    course_id = "ai-strategy"
    checksum = digest(raw.encode())
    with store.tx() as c:
        specification = root / "spec/SPEC.md"
        if specification.exists() and not store.get(
            c, "assessment_profile", "legacy-ai-strategy-archetype", False
        ):
            store.put(
                c,
                "assessment_profile",
                "legacy-ai-strategy-archetype",
                {
                    "course_id": course_id,
                    "status": "proposed",
                    "source_ids": [],
                    "provenance": {
                        "kind": "learner_authored_legacy_specification",
                        "path": "spec/SPEC.md",
                        "sha256": digest(specification.read_bytes()),
                    },
                    "profile": {
                        "title": "AI Strategy · legacy quiz archetype",
                        "assessment_kinds": ["practice_quiz", "exam"],
                        "question_types": ["mcq", "matching"],
                        "structure": specification.read_text(),
                        "length_and_time": "16 items; review timing against the official course instructions",
                        "scoring_rules": "12 MCQ at 5 points and 4 matching at 10 points; 100 points total",
                        "reasoning_demands": [
                            "Distinguish the verdict from its warrant",
                            "Apply a supplied framework while honoring scenario stipulations",
                        ],
                        "difficulty_anchor": "Usually two inferential steps; difficulty through discrimination",
                        "uncertainty": [
                            "A historical style reference, not official validation or learner telemetry",
                            "Review all layout requirements before generation",
                        ],
                        "supporting_fragment_ids": [],
                    },
                },
            )
        if store.get(c, "import", "legacy:" + checksum, False):
            return {"course_id": course_id, "already_imported": True}
        store.put(
            c,
            "course",
            course_id,
            {
                "title": "AI Strategy",
                "description": "94-804 · Frameworks, cases and defensible decisions",
                "modules": [{"id": x["code"], "title": x["subtitle"]} for x in bundle["cheats"]],
                "origin": str(root),
                "imported_content": True,
            },
        )
        for cheat in bundle["cheats"]:
            sanitized = {
                **cheat,
                "blocks": [
                    {
                        **b,
                        "html": bleach.clean(
                            b["html"],
                            tags=SAFE_TAGS,
                            attributes={"a": ["href", "title"], "th": ["colspan"], "td": ["colspan"]},
                            strip=True,
                        ),
                    }
                    for b in cheat["blocks"]
                ],
            }
            store.put(c, "guide", course_id + ":" + cheat["code"], {**sanitized, "course_id": course_id})
        for term in bundle["gloss"]:
            store.put(
                c,
                "term",
                course_id + ":" + term["id"],
                {**term, "legacy_id": term["id"], "course_id": course_id},
            )
        banks = [("practice", None, bundle["train"])] + [
            ("simulation", k, v) for k, v in bundle["forms"].items()
        ]
        total = 0
        for mode, form, bank in banks:
            vignettes = {v["id"]: v for v in bank.get("vignettes", [])}
            for item in bank["items"]:
                ident = course_id + ":" + item["id"]
                data = {
                    **item,
                    "course_id": course_id,
                    "pool": mode,
                    "form": form,
                    "family_id": item["id"],
                    "status": "active",
                    "verification": "imported_answer_key",
                    "provenance": {"import_hash": checksum, "legacy_id": item["id"], "path": "app/data.js"},
                    "capabilities": [f"ai-strategy:{item['module']}"],
                    "cognitive_operation": {
                        "recall": "recall",
                        "apply": "application",
                        "analyze": "application",
                        "evaluate": "communication",
                    }.get(item["bloom"], "application"),
                    "vignette": vignettes.get(item.get("vignetteId")),
                    "rubric_version": "legacy-v1",
                }
                store.put(c, "item", ident, data)
                total += 1
            if form:
                store.put(
                    c,
                    "form",
                    course_id + ":" + form,
                    {
                        "course_id": course_id,
                        "label": form,
                        "item_ids": [course_id + ":" + i["id"] for i in bank["items"]],
                        "minutes": 45,
                        "points": sum(i["points"] for i in bank["items"]),
                        "blueprint": "11 standalone + 5 case; 12 MCQ + 4 matching",
                    },
                )
        store.put(c, "import", "legacy:" + checksum, {"count": total, "source": str(root)})
        store.emit(
            c,
            "course.imported",
            course_id,
            {"items": total, "practice": 314, "forms": 4},
            key="import:" + checksum,
        )
    for file in sorted((root / "content/extract").glob("*.md")):
        ingest(store, course_id, file.name, file.read_bytes())
    return {"course_id": course_id, "items": total, "forms": 4, "terms": len(bundle["gloss"])}
