"""hook event 語彙の3正本 (実配線 / schema enum / rubric HK-001) の集合一致を検査する。

件数だけを数える検査では「3つとも9値だが中身が違う」という壊れ方が通る。
ここでは集合として比較し、実配線 (hooks.json) にあって宣言側に無い event を落とす。
逆向き (宣言にあって未配線) は将来の宣言として許容する。
"""
from __future__ import annotations

import json
import re
from pathlib import Path

PLUGIN_ROOT = Path(__file__).resolve().parents[1]

HOOKS_JSON = PLUGIN_ROOT / "hooks" / "hooks.json"
SCHEMA_JSON = (
    PLUGIN_ROOT / "skills" / "run-build-skill" / "references" / "capability-manifest.schema.json"
)
RUBRIC_JSON = PLUGIN_ROOT / "skills" / "ref-skill-design-rubric" / "references" / "rubric.json"


def _wired_events() -> set[str]:
    return set(json.loads(HOOKS_JSON.read_text(encoding="utf-8"))["hooks"].keys())


def _schema_events() -> set[str]:
    schema = json.loads(SCHEMA_JSON.read_text(encoding="utf-8"))
    enum = schema["definitions"]["kindHook"]["properties"]["event"]["enum"]
    return set(enum)


def _rubric_events() -> set[str]:
    rubric = json.loads(RUBRIC_JSON.read_text(encoding="utf-8"))
    rules = [r for r in rubric["rules"] if r["id"] == "HK-001"]
    assert len(rules) == 1, f"HK-001 は1件であること (実測 {len(rules)} 件)"
    body = re.search(r"\{([^}]*)\}", rules[0]["check"])
    assert body, "HK-001 の check に {..} 形式の event 列挙が見つからない"
    return {tok.strip() for tok in body.group(1).split(",") if tok.strip()}


def test_wired_hook_events_are_declared_in_schema_and_rubric() -> None:
    wired = _wired_events()
    assert wired, "hooks.json に配線 event が1件も無い (分母0では検査が成立しない)"

    schema = _schema_events()
    rubric = _rubric_events()

    assert not (wired - schema), (
        f"schema enum に無い配線 event: {sorted(wired - schema)} "
        f"(配線 {len(wired)} 件 / enum {len(schema)} 件)"
    )
    assert not (wired - rubric), (
        f"rubric HK-001 に無い配線 event: {sorted(wired - rubric)} "
        f"(配線 {len(wired)} 件 / HK-001 {len(rubric)} 件)"
    )


def test_schema_enum_and_rubric_hk001_describe_the_same_set() -> None:
    schema = _schema_events()
    rubric = _rubric_events()
    assert schema == rubric, (
        f"schema のみ: {sorted(schema - rubric)} / rubric のみ: {sorted(rubric - schema)} "
        f"(schema {len(schema)} 件 / rubric {len(rubric)} 件)"
    )
