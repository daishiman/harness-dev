"""Catalog compatibility and bounded interview schedule, without question-text snapshots."""
from __future__ import annotations

from collections import Counter
import json
from conftest import PLUGIN_ROOT, node_eval


def test_catalog_keeps_existing_identifiers_and_interview_budget() -> None:
    catalog = json.loads((PLUGIN_ROOT / "assets/data/hearing-catalog.json").read_text(encoding="utf-8"))
    questions = catalog["questions"]
    assert sorted(q["id"] for q in questions) == [f"H{i:02d}" for i in range(1, 37)]
    assert len({q["key"] for q in questions}) == 36
    by_key = {q["key"]: q["id"] for q in questions}
    legacy = [f"{c}{i}" for c, n in (("A", 6), ("B", 8), ("C", 6), ("D", 4)) for i in range(1, n + 1)]
    assert [by_key[key] for key in legacy] == [f"H{i:02d}" for i in range(1, 25)]
    assert {key: by_key[key] for key in ("A7", "B9", "B10", "B11", "C7", "C8", "C9", "C10", "C11", "C12", "D5", "D6")} == dict(zip(
        ("A7", "B9", "B10", "B11", "C7", "C8", "C9", "C10", "C11", "C12", "D5", "D6"),
        (f"H{i:02d}" for i in range(25, 37)),
    ))
    sections = {section["id"] for section in catalog["sections"]}
    assert sections == {1, 2, 3, 4}
    rounds = Counter(q["round"] for q in questions if q["round"] is not None)
    assert set(rounds) == set(range(1, 7)) and max(rounds.values()) <= 4
    for question in questions:
        assert question["section"] in sections
        assert question["section"] == "ABCD".index(question["key"][0]) + 1
        assert question["question"].strip() and question["design_default"].strip()
        assert len(question["options"]) in (2, 3, 4)
        assert "(おすすめ)" in question["options"][0]
        for key in ("options", "destinations", "capture"):
            assert question[key] and all(isinstance(value, str) and value.strip() for value in question[key])


def test_shared_catalog_api_reads_the_same_source_and_is_immutable() -> None:
    catalog = json.loads((PLUGIN_ROOT / "assets/data/hearing-catalog.json").read_text(encoding="utf-8"))
    exported = node_eval(
        'import { HEARING_QUESTIONS, HEARING_SECTIONS } from "./lib/hearing-catalog.mjs";\n'
        'let blocked = false; try { HEARING_QUESTIONS[0].options.push("extra"); } catch { blocked = true; }\n'
        'console.log(JSON.stringify({questions: HEARING_QUESTIONS, sections: HEARING_SECTIONS, blocked}));'
    )
    assert exported == {"questions": catalog["questions"], "sections": catalog["sections"], "blocked": True}
