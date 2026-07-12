"""lint-contract-drift.py のテスト。

(1) 現在の plugin 実体に対し drift ゼロ (回帰ガード: prose↔code の乖離を再導入したら赤)。
(2) 4 チェックの検出能 (合成入力・helper 単体)。
(3) false-positive 非発火 (data-ink 比のような可視化ドメイン用語を属性と誤認しない)。
"""
from __future__ import annotations

import importlib.util
import json
from pathlib import Path

_PLUGIN_ROOT = Path(__file__).resolve().parent.parent
_SCRIPT = _PLUGIN_ROOT / "scripts" / "lint-contract-drift.py"


def _load():
    spec = importlib.util.spec_from_file_location("lint_contract_drift_mod", _SCRIPT)
    assert spec and spec.loader
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


mod = _load()


# --- (1) 回帰ガード: 現行実体は drift ゼロ ---------------------------------------

def test_current_plugin_has_no_contract_drift():
    findings = mod.run_checks(_PLUGIN_ROOT)
    assert findings == [], "contract-drift 検出: " + json.dumps(findings, ensure_ascii=False)


# --- (2) helper: data-* 属性抽出は backtick/属性構文のみ (false-positive 排除) ---

def test_cited_data_attrs_extracts_backtick_and_attr_syntax():
    text = "`data-reading-order` と `data-focal=\"x,y\"` を使い、data-attr=1 も拾う。"
    got = mod._cited_data_attrs(text)
    assert "data-reading-order" in got
    assert "data-focal" in got
    assert "data-attr" in got


def test_cited_data_attrs_ignores_prose_domain_term():
    # 『data-ink 比』(Tufte 用語) は HTML 属性でないので拾わない。
    text = "定量は data-ink 比を意識し過剰装飾を避ける。"
    assert mod._cited_data_attrs(text) == set()


# --- (2) helper: 閾値抽出は DEFAULT_THRESHOLDS と一致 ---------------------------

def test_load_thresholds_matches_validator():
    th = mod._load_thresholds(_PLUGIN_ROOT)
    # 主要キーが抽出できる。
    assert th.get("doc_highlight_budget") == 24
    assert th.get("monotone_block_floor") == 6
    assert "max_visuals_per_section" in th


# --- (2) 検出能: 合成 root で 4 チェックが drift を掴む -------------------------

def _mk_min_plugin(tmp_path: Path) -> Path:
    """render/validator/schema/prose の最小 clean tree を作る (drift ゼロが既定)。"""
    root = tmp_path / "plg"
    (root / "vendor" / "scripts").mkdir(parents=True)
    (root / "scripts").mkdir(parents=True)
    (root / "schemas").mkdir(parents=True)
    (root / "references").mkdir(parents=True)
    (root / "skills" / "run-slide-report-generate" / "references").mkdir(parents=True)
    (root / "skills" / "run-slide-report-generate" / "prompts").mkdir(parents=True)
    # render: data-emphasis のみ emit / report-throughline を生成
    (root / "vendor" / "scripts" / "render-report.js").write_text(
        'const a = ` data-emphasis="${e}" `;\nfunction f(){ return "report-throughline"; }\n// layout.grid layout.emphasisZone\n',
        encoding="utf-8",
    )
    # validator: report-throughline を fidelity 検査 / DEFAULT_THRESHOLDS / role 方針2集合(SSOT)
    (root / "scripts" / "validate-report-visual.py").write_text(
        'DEFAULT_THRESHOLDS = {\n    "doc_highlight_budget": 24,\n}\n'
        '_NARRATIVE_REQUIRED_ROLES = {\n    "analysis", "argument",\n}\n'
        '_NARRATIVE_OPTIONAL_ROLES = {\n    "reference", "summary",\n}\n'
        'x = "report-throughline" not in html\n',
        encoding="utf-8",
    )
    # schema: placement grid(消費) + zones(advisory)
    schema = {"$defs": {"placement": {"properties": {
        "grid": {"type": "string", "description": "レイアウト"},
        "emphasisZone": {"type": "string", "description": "強調"},
        "zones": {"type": "array", "description": "advisory メタ"},
    }}}}
    (root / "schemas" / "report-structure.schema.json").write_text(
        json.dumps(schema, ensure_ascii=False), encoding="utf-8"
    )
    (root / "references" / "report-writing-rules.md").write_text(
        "doc_highlight_budget=24 を守る。`data-emphasis` を使う。\n", encoding="utf-8"
    )
    # references §6.1 role→narrative 表 (validator の2集合と一致させる)
    (root / "references" / "report-narrative-logic.md").write_text(
        "### 6.1 role\n"
        "| 群 | role |\n|---|---|\n"
        "| **期待** | `analysis` `argument` |\n"
        "| **不要** | `reference` |\n"
        "| **文脈依存** | `summary` |\n",
        encoding="utf-8",
    )
    return root


def test_detects_phantom_data_attr(tmp_path):
    root = _mk_min_plugin(tmp_path)
    (root / "references" / "report-bad.md").write_text("`data-focal-y` を反映する。\n", encoding="utf-8")
    findings = mod.run_checks(root)
    assert any(f["check"] == "data-attr-phantom" and "data-focal-y" in f["message"] for f in findings)


def test_detects_threshold_drift(tmp_path):
    root = _mk_min_plugin(tmp_path)
    (root / "references" / "report-bad.md").write_text("doc_highlight_budget=99 が上限。\n", encoding="utf-8")
    findings = mod.run_checks(root)
    assert any(f["check"] == "threshold-drift" for f in findings)


def test_detects_fidelity_orphan(tmp_path):
    root = _mk_min_plugin(tmp_path)
    src = (root / "scripts" / "validate-report-visual.py").read_text(encoding="utf-8")
    (root / "scripts" / "validate-report-visual.py").write_text(
        src + '\ny = "report-orphan-cls" not in html\n', encoding="utf-8"
    )
    findings = mod.run_checks(root)
    assert any(f["check"] == "fidelity-orphan" and "report-orphan-cls" in f["message"] for f in findings)


def test_detects_placement_dead_field(tmp_path):
    root = _mk_min_plugin(tmp_path)
    schema = json.loads((root / "schemas" / "report-structure.schema.json").read_text(encoding="utf-8"))
    schema["$defs"]["placement"]["properties"]["bogusZone"] = {"type": "string", "description": "未消費"}
    (root / "schemas" / "report-structure.schema.json").write_text(
        json.dumps(schema, ensure_ascii=False), encoding="utf-8"
    )
    findings = mod.run_checks(root)
    assert any(f["check"] == "placement-dead-field" and "bogusZone" in f["message"] for f in findings)


def test_detects_role_policy_drift(tmp_path):
    root = _mk_min_plugin(tmp_path)
    # reference §6.1『期待』群から argument を削除 → validator の REQUIRED と不一致。
    p = root / "references" / "report-narrative-logic.md"
    p.write_text(p.read_text(encoding="utf-8").replace("`analysis` `argument`", "`analysis`"), encoding="utf-8")
    findings = mod.run_checks(root)
    assert any(f["check"] == "role-policy-drift" for f in findings)


def test_role_policy_reference_matches_validator_on_real_plugin():
    req, opt = mod._load_role_sets(_PLUGIN_ROOT)
    groups = mod._reference_role_groups(_PLUGIN_ROOT)
    assert groups.get("expected") == req
    assert (groups.get("optional_strict", set()) | groups.get("context", set())) == opt


def test_min_plugin_is_clean(tmp_path):
    # 合成 clean tree は drift ゼロ (検出能テストの陰性対照)。
    assert mod.run_checks(_mk_min_plugin(tmp_path)) == []
