"""Populate the CURRENT Learning Gym through its public HTTP authoring API.

Run from the repository: uv run python scripts/install_causality.py
Safe to repeat with the same bundle. No synthetic learning history or model calls.
"""

import argparse
import hashlib
import html
import json
import os
import sys
from pathlib import Path

import httpx
from dotenv import load_dotenv

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))


def paragraphs(values):
    return "".join(f"<p>{html.escape(str(v))}</p>" for v in values)


def bullets(values):
    return "<ul>" + "".join(f"<li>{html.escape(str(v))}</li>" for v in values) + "</ul>"


def source_link(source):
    return f'<a href="{html.escape(source["url"], quote=True)}">{html.escape(source["title"])}</a>'


def lesson_text(lesson, sources, number):
    bridge = lesson["paper_bridge"]
    lines = [f"# {number:02}. {lesson['title']}", lesson["question"],
             "Original teaching notes prepared with AI assistance for this Learning Gym. These are explanatory material, not a copy of the referenced publications.",
             "# What you will learn", *lesson["objectives"], "# Intuition", *lesson["intuition"],
             "# " + lesson["worked_example"]["title"], lesson["worked_example"]["body"],
             "# Try it", lesson["experiment_task"], "# Remember", *lesson["takeaways"],
             "# Common mistake", lesson["pitfall"], "# Research bridge", bridge["why_it_matters"],
             bridge["claim"], "# Assumptions", *bridge["assumptions"], "# Limits", *bridge["limits"],
             "# Reading task", bridge["read_first"], bridge["exercise"], "# Reflection", lesson["reflection"],
             "# Referenced readings (external originals)"]
    for sid in lesson["source_ids"]:
        s = sources[sid]
        lines.append(f"{s['title']} ({s.get('year', '')}). {s.get('status', s.get('kind', ''))}. {s['url']}")
    return "\n\n".join(lines)


def guide_blocks(lesson, sources, module_names):
    bridge = lesson["paper_bridge"]
    paper = sources[bridge["source_id"]]
    prerequisites = [module_names[p] for p in lesson["prerequisites"]]
    return [
        {"id": "start", "h": lesson["question"], "html": paragraphs([
            f"{lesson['stage']} · About {lesson['minutes']} minutes. Start with the explanation; the paper is the last step.",
            "Before this lesson: " + ("; ".join(prerequisites) if prerequisites else "Nothing. Begin here."),
        ]) + bullets(lesson["objectives"])},
        {"id": "intuition", "h": "The idea in everyday language", "html": paragraphs(lesson["intuition"])},
        {"id": "example", "h": lesson["worked_example"]["title"], "html": paragraphs([lesson["worked_example"]["body"]])},
        {"id": "try", "h": "Predict, try, explain", "html": paragraphs([lesson["experiment_task"], lesson["reflection"]])},
        {"id": "remember", "h": "What to keep; what to question", "html": bullets(lesson["takeaways"]) + paragraphs(["Common mistake: " + lesson["pitfall"]])},
        {"id": "paper", "h": "Your bridge to the research", "html":
            "<p>" + source_link(paper) + "</p>" + paragraphs([
                str(paper.get("year", "")) + " · " + paper.get("status", paper.get("kind", "")),
                bridge["why_it_matters"], "Claim: " + bridge["claim"], "Read first: " + bridge["read_first"],
            ]) + "<h4>Assumptions</h4>" + bullets(bridge["assumptions"]) + "<h4>Limits</h4>" + bullets(bridge["limits"]) + paragraphs([bridge["exercise"]])},
        {"id": "practice", "h": "Check your understanding in the gym", "html": paragraphs([
            "Return to Workbench, select this gym and this module, and start Practice. Try the questions before opening hints. Explain the open response in your own words; feedback on open answers comes from the gym's configured assessor.",
            "Reading or recognizing a correct answer does not establish mastery. Come back later and solve a fresh example without help.",
        ])},
        {"id": "sources", "h": "Readings and provenance", "html":
            "<ul>" + "".join("<li>" + source_link(sources[s]) + "</li>" for s in lesson["source_ids"]) + "</ul>" + paragraphs([
                "This guide is original AI-assisted teaching synthesis. Follow the links for original evidence; preprints and company summaries are labeled. The two books mentioned by the learner have not yet been located.",
            ])},
    ]


def install(client, bundle, readings_dir=None):
    def request(method, path, **kwargs):
        response = client.request(method, path, **kwargs)
        if not response.is_success:
            raise ValueError(f"{method} {path}: HTTP {response.status_code}: {response.text[:1500]}")
        return response.json()

    ident = bundle["id"]
    fingerprint = hashlib.sha256(json.dumps(bundle, sort_keys=True).encode()).hexdigest()
    sources = {s["id"]: s for s in bundle["sources"]}
    module_ids = {entry["id"]: f"C{i:02}" for i, entry in enumerate(bundle["lessons"], 1)}
    module_names = {entry["id"]: f"{module_ids[entry['id']]}: {entry['title']}" for entry in bundle["lessons"]}
    provenance = {"author": "Codex, at the learner's request", "method": "import",
                  "rationale": "Original progressive causality curriculum; inspected primary sources; not learner performance. Bundle " + fingerprint,
                  "reference_urls": [s["url"] for s in bundle["sources"]]}
    modules = [{"id": module_ids[entry["id"]], "title": f"{i:02}. {entry['title']}",
                "description": entry["question"], "prerequisites": [module_ids[p] for p in entry["prerequisites"]],
                "objectives": entry["objectives"], "estimated_minutes": entry["minutes"],
                "capabilities": [entry["id"]],
                "level": {"Foundations": "beginner", "Discovery": "intermediate", "Frontier": "frontier"}[entry["stage"]]}
               for i, entry in enumerate(bundle["lessons"], 1)]
    course_spec = {"expected_revision": 0, "title": bundle["title"],
                   "description": bundle["description"], "modules": modules, "provenance": provenance}
    # Validate the full content shape before mutating the current platform.
    from gym.authoring import CourseWrite
    from gym.contracts import GeneratedItem

    CourseWrite.model_validate(course_spec)
    for lesson in bundle["lessons"]:
        for item in lesson["practice"]:
            GeneratedItem.model_validate({**item, "source_fragment_ids": ["pending-upload"]})
        cp = lesson["checkpoint"]
        GeneratedItem.model_validate({"type": "mcq", "stem": cp["question"], "options": cp["options"],
            "key": cp["key"], "explanation": cp["explanation"], "hint": lesson["takeaways"][0],
            "plain": lesson["question"], "source_fragment_ids": ["pending-upload"],
            "capabilities": [lesson["id"]], "cognitive_operation": "application", "points": 5})
    existing = client.get(f"/api/authoring/courses/{ident}")
    if existing.status_code == 404:
        request("PUT", f"/api/authoring/courses/{ident}", json=course_spec)
    elif existing.is_success:
        if existing.json().get("provenance") != provenance:
            raise ValueError("Course ID already exists with different provenance; inspect it before importing")
    else:
        raise ValueError(f"Cannot inspect the gym: HTTP {existing.status_code}")

    guides, items, terms, lesson_sources, lesson_fragments = [], [], [], {}, {}
    for number, lesson in enumerate(bundle["lessons"], 1):
        module = module_ids[lesson["id"]]
        text = lesson_text(lesson, sources, number)
        filename = f"{module}-{lesson['id']}.md"
        if readings_dir:
            readings_dir.mkdir(parents=True, exist_ok=True)
            (readings_dir / filename).write_text(text)
        source = request("POST", "/api/sources", data={"course_id": ident, "role": "instruction"},
                         files={"file": (filename, text.encode(), "text/markdown")})
        fragments = request("GET", f"/api/sources/{source['id']}/fragments")
        if "\n".join(f["text"] for f in fragments) != text:
            raise ValueError("Source extraction changed authored text; review the reconstruction before import")
        if source["reconstruction_status"] != "confirmed":
            request("POST", f"/api/sources/{source['id']}/confirm", json={"expected_revision": source["revision"]})
        refs = [f["id"] for f in fragments]
        lesson_sources[lesson["id"]] = source["id"]
        lesson_fragments[lesson["id"]] = refs
        guides.append({"id": f"{ident}:{module}:guide", "expected_revision": 0, "course_id": ident,
            "code": module, "subtitle": lesson["title"], "blocks": guide_blocks(lesson, sources, module_names),
            "source_fragment_ids": refs, "provenance": provenance})
        cp = lesson["checkpoint"]
        checkpoint = {"type": "mcq", "stem": cp["question"], "options": cp["options"], "key": cp["key"],
                      "explanation": cp["explanation"], "hint": lesson["takeaways"][0], "plain": lesson["question"],
                      "capabilities": [lesson["id"]], "cognitive_operation": "application", "points": 5}
        for index, item in enumerate([checkpoint, *lesson["practice"]]):
            items.append({**item, "id": f"{ident}:{module}:practice:{index}", "expected_revision": 0,
                "course_id": ident, "module": module, "pool": "practice", "source_fragment_ids": refs,
                "provenance": provenance})
    for index, term in enumerate(bundle["glossary"]):
        # Associate with the first lesson that actually uses the concept, and cite its notes.
        match = next((entry for entry in bundle["lessons"] if term["term"].lower() in lesson_text(entry, sources, 1).lower()), bundle["lessons"][0])
        terms.append({"id": f"{ident}:term:{index}", "expected_revision": 0, "course_id": ident,
            "module": module_ids[match["id"]], "term": term["term"], "def": term["definition"],
            "distinguish": term.get("distinguish", ""), "why": term.get("why", ""),
            "source_fragment_ids": lesson_fragments[match["id"]], "provenance": provenance})
    # Orientation is also a normal study guide, so it appears in the existing library.
    first = bundle["lessons"][0]
    guides.insert(0, {"id": f"{ident}:start", "expected_revision": 0, "course_id": ident, "code": "C01",
        "subtitle": "Start here: from everyday questions to frontier papers", "source_fragment_ids": lesson_fragments[first["id"]],
        "provenance": provenance, "blocks": [
            {"id": "route", "h": "A route you can follow from zero", "html": paragraphs([
                "Work through C01–C12 in order. Each lesson connects an everyday question to one research idea. You do not need to understand the entire paper: start with the suggested section and one claim.",
                "Open a guide here, try its small exercise, then close the library and select the matching module in Practice. Choose 3 questions for one lesson. Use the thinking hint or Plain English after your own attempt. For longer exercises, open Coursework & rubrics.",
                "Allow one lesson per sitting. Repeat a lesson when you can recognize the terms but cannot yet explain the example. The gym records actual practice; importing this course gives no credit or mastery.",
            ]) + "<ol>" + "".join(f"<li>{html.escape(module_names[entry['id']])}</li>" for entry in bundle["lessons"]) + "</ol>"},
            {"id": "courses", "h": "Optional course materials", "html": "<ul>" + "".join("<li>" + source_link(s) + "</li>" for s in bundle["sources"] if "course" in s.get("kind", "").lower()) + "</ul>"},
        ]})
    material_result = request("POST", "/api/authoring/import", json={
        "idempotency_key": "causality:" + fingerprint, "course_id": ident, "guides": guides, "terms": terms, "items": items,
    })
    coursework = request("GET", "/api/coursework")
    rubric_title = "Causality: explain, test, and qualify a claim"
    rubric = next((r for r in coursework["rubric"] if r.get("course_id") == ident and r["title"] == rubric_title), None)
    if not rubric:
        rubric = request("POST", "/api/rubrics", json={
            "title": rubric_title, "course_id": ident, "authority": "proposed",
            "permitted_assistance": "Use guides and ask for explanations. Disclose AI assistance and write your own reasoning. This is self-study, not an official course grade.",
            "capabilities": ["causal-research-reasoning"], "criteria": [
                {"name": "Question and causal model", "weight": .25, "anchors": ["Vague association; unclear intervention or arrows", "Defines intervention, outcome, comparison, and justified graph"]},
                {"name": "Assumptions and reasoning", "weight": .3, "anchors": ["Treats correlation as cause; hides identification assumptions", "Explains what assumptions permit the conclusion and checks an alternative"]},
                {"name": "Evidence and reproducibility", "weight": .25, "anchors": ["Unsupported claim or unexplained result", "Traceable calculation or reproducible experiment; cites the relevant paper"]},
                {"name": "Limits and next test", "weight": .2, "anchors": ["Claims more than the evidence supports", "States uncertainty, a limitation, and a test that could change the conclusion"]},
            ],
        })
    exercises = []
    for index, title in [(2, "Lab 1 · Explain a misleading comparison"), (4, "Lab 2 · What can these arrows tell us?"),
                         (8, "Lab 3 · When the environment changes")]:
        lesson = bundle["lessons"][index]
        exercises.append({"title": title, "kind": "lab", "effort_minutes": 35,
            "source_ids": [lesson_sources[lesson["id"]]],
            "prompt": "Start with " + module_names[lesson["id"]] + ".\n\n" + lesson["experiment_task"] + "\n\n" + lesson["reflection"] +
                      "\n\nWrite: (1) your prediction before checking; (2) your diagram, calculation, or result; (3) which assumption makes your conclusion possible; (4) one alternative explanation or limitation. Plain language is welcome. Hand calculations and thought experiments are valid; coding is optional."})
    exercises.append({"title": bundle["capstone"]["title"], "kind": "project", "effort_minutes": 90,
        "prompt": bundle["capstone"]["prompt"], "source_ids": list(lesson_sources.values())})
    created_assignments = []
    for task in exercises:
        previous = next((a for a in coursework["assignment"] if a["course_id"] == ident and a["title"] == task["title"]), None)
        assignment = previous or request("POST", "/api/assignments", json={**task, "course_id": ident,
            "rubric_id": rubric["id"], "follow_shared_rubric": True})
        created_assignments.append(assignment["id"])
    return {"course_id": ident, "guides": len(guides), "sources": len(lesson_sources), "terms": len(terms),
            "practice_items": len(items), "assignments": len(created_assignments), "rubric_id": rubric["id"],
            "already_imported": material_result.get("already_imported", False), "bundle_hash": fingerprint}


def main():
    load_dotenv(ROOT / ".env")
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--base-url", default=os.getenv("GYM_BASE_URL", "http://127.0.0.1:8787"))
    parser.add_argument("--bundle", type=Path, default=ROOT / "content/causality/lab.json")
    args = parser.parse_args()
    token = os.getenv("GYM_ACCESS_TOKEN", "")
    headers = {"Authorization": "Bearer " + token} if token else {}
    with httpx.Client(base_url=args.base_url, headers=headers, timeout=120, follow_redirects=False) as client:
        result = install(client, json.loads(args.bundle.read_text()), ROOT / "content/causality/readings")
    print(json.dumps(result, indent=2))


if __name__ == "__main__":
    main()
