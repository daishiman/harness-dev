# /// script
# name: test-validate-knowledge-graph
# version: 0.1.0
# purpose: C14 (validate-knowledge-graph.py) の 3 profile (knowledge/required-info/doctrine) を正例=OK・負例=各違反・usage=exit2 で網羅検証する pytest。ハイフン名モジュールを in-process import して validate_*()/main() を直接呼び coverage 計測する。
# inputs:
#   - argv: pytest 経由
# outputs:
#   - stdout: pytest 結果
#   - exit: 0=all pass / 1=failure
# contexts: [E, C]
# network: false
# write-scope: none
# dependencies: []
# requires-python: ">=3.9"
# ///
"""C14 (validate-knowledge-graph) の 3 profile 決定論ゲート検証。

knowledge=depends_on DAG/refines/conflicts_with 型則・循環/dangling/孤立/root到達性・topo_order、
required-info=最低形状/domain被覆/収集順序/coverage certificate/missing_effect、
doctrine=concern authority 一意性/category→concern 写像全射/pending 例外 を網羅する。
"""
from __future__ import annotations

import importlib.util
import json
from pathlib import Path

SCRIPTS = Path(__file__).resolve().parent.parent / "scripts"


def _load(name: str, filename: str):
    spec = importlib.util.spec_from_file_location(name, SCRIPTS / filename)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


kg = _load("vkg", "validate-knowledge-graph.py")


def write(tmp_path: Path, name: str, obj: dict) -> str:
    p = tmp_path / name
    p.write_text(json.dumps(obj, ensure_ascii=False), encoding="utf-8")
    return str(p)


# ── knowledge fixtures ────────────────────────────────────────────────────
def _valid_knowledge() -> dict:
    return {
        "schema_version": "1.0",
        "entries": [
            {"knowledge_id": "clean-code", "depends_on": [], "refines": [], "conflicts_with": []},
            {"knowledge_id": "design-patterns", "depends_on": [], "refines": [], "conflicts_with": []},
            {"knowledge_id": "ddd", "depends_on": ["clean-code"], "refines": [], "conflicts_with": []},
            {"knowledge_id": "clean-architecture", "depends_on": ["ddd", "design-patterns"], "refines": [], "conflicts_with": []},
            {"knowledge_id": "api-design-patterns", "depends_on": ["clean-architecture"], "refines": ["design-patterns"], "conflicts_with": []},
            {"knowledge_id": "secure-by-design", "depends_on": ["clean-architecture"], "refines": [], "conflicts_with": []},
        ],
    }


def test_knowledge_valid_topo_order():
    findings, result = kg.validate_knowledge(_valid_knowledge())
    assert findings == []
    assert result["status"] == "ok"
    order = result["topo_order"]
    # B before A: clean-code before ddd, ddd before clean-architecture, etc.
    assert order.index("clean-code") < order.index("ddd")
    assert order.index("ddd") < order.index("clean-architecture")
    assert order.index("clean-architecture") < order.index("api-design-patterns")
    # 同順位 (root) は id 昇順: clean-code < design-patterns
    assert order.index("clean-code") < order.index("design-patterns")


def test_knowledge_deterministic():
    _, r1 = kg.validate_knowledge(_valid_knowledge())
    _, r2 = kg.validate_knowledge(_valid_knowledge())
    assert r1["topo_order"] == r2["topo_order"]


def test_knowledge_empty_rejected():
    findings, _ = kg.validate_knowledge({"entries": []})
    assert any("空カタログ" in f for f in findings)


def test_knowledge_dangling():
    d = _valid_knowledge()
    d["entries"][2]["depends_on"] = ["nonexistent"]
    findings, _ = kg.validate_knowledge(d)
    assert any("dangling" in f for f in findings)


def test_knowledge_self_reference():
    d = _valid_knowledge()
    d["entries"][0]["depends_on"] = ["clean-code"]
    findings, _ = kg.validate_knowledge(d)
    assert any("自己参照" in f for f in findings)


def test_knowledge_cycle():
    d = {
        "entries": [
            {"knowledge_id": "a", "depends_on": ["b"]},
            {"knowledge_id": "b", "depends_on": ["a"]},
        ]
    }
    findings, _ = kg.validate_knowledge(d)
    assert any("循環" in f for f in findings)


def test_knowledge_refines_cycle():
    d = {
        "entries": [
            {"knowledge_id": "a", "depends_on": [], "refines": ["b"]},
            {"knowledge_id": "b", "depends_on": [], "refines": ["a"]},
        ]
    }
    findings, _ = kg.validate_knowledge(d)
    assert any("refines に循環" in f for f in findings)


def test_knowledge_conflicts_asymmetric():
    d = _valid_knowledge()
    d["entries"][0]["conflicts_with"] = ["ddd"]  # ddd 側に対称辺無し
    findings, _ = kg.validate_knowledge(d)
    assert any("非対称" in f for f in findings)


def test_knowledge_conflicts_symmetric_ok():
    d = _valid_knowledge()
    d["entries"][0]["conflicts_with"] = ["design-patterns"]
    d["entries"][1]["conflicts_with"] = ["clean-code"]
    findings, result = kg.validate_knowledge(d)
    assert findings == []
    assert result["status"] == "ok"


def test_knowledge_isolated_node():
    d = _valid_knowledge()
    d["entries"].append({"knowledge_id": "orphan", "depends_on": [], "refines": [], "conflicts_with": []})
    findings, _ = kg.validate_knowledge(d)
    assert any("孤立 node" in f for f in findings)


def test_knowledge_duplicate_id():
    d = _valid_knowledge()
    d["entries"].append({"knowledge_id": "clean-code", "depends_on": []})
    findings, _ = kg.validate_knowledge(d)
    assert any("重複" in f for f in findings)


def test_knowledge_missing_id():
    d = {"entries": [{"depends_on": []}]}
    findings, _ = kg.validate_knowledge(d)
    assert any("knowledge_id 欠落" in f for f in findings)


# ── required-info fixtures ────────────────────────────────────────────────
def _item(iid: str, domain: str, deps=None, missing="warn") -> dict:
    return {
        "item_id": iid,
        "domain": domain,
        "concern": "application-architecture",
        "question": "q?",
        "required_reason": "r",
        "evidence_required": True,
        "depends_on": deps or [],
        "required_when": "always",
        "completion_rule": "answered",
        "missing_effect": missing,
        "serves_goals": ["C16"],
    }


def _valid_required_info() -> dict:
    return {
        "schema_version": "1.0",
        "in_scope_domains": ["api", "frontend", "backend"],
        "items": [
            _item("api-contract", "api", missing="block"),
            _item("fe-state", "frontend", deps=["api-contract"]),
            _item("be-persistence", "backend"),
        ],
        "na_domains": [],
    }


def test_required_info_valid():
    findings, result = kg.validate_required_info(_valid_required_info())
    assert findings == []
    assert result["status"] == "ok"
    assert result["coverage_certificate"]["total_items"] == 3
    assert "api-contract" in result["coverage_certificate"]["blocking_items"]
    # depends_on: api-contract before fe-state
    order = result["collection_order"]
    assert order.index("api-contract") < order.index("fe-state")


def test_required_info_evidence_required_false_is_valid():
    # boolean の false は正当値。truthiness で欠落扱いしてはいけない (regression guard)。
    d = _valid_required_info()
    d["items"][0]["evidence_required"] = False
    findings, result = kg.validate_required_info(d)
    assert findings == []
    assert result["status"] == "ok"


def test_required_info_evidence_required_non_bool_fails():
    d = _valid_required_info()
    d["items"][0]["evidence_required"] = "yes"
    findings, _ = kg.validate_required_info(d)
    assert any("boolean 必須" in f for f in findings)


def test_required_info_evidence_required_missing_fails():
    d = _valid_required_info()
    del d["items"][0]["evidence_required"]
    findings, _ = kg.validate_required_info(d)
    assert any("boolean 必須" in f for f in findings)


def test_required_info_empty_rejected():
    findings, _ = kg.validate_required_info({"items": [], "in_scope_domains": ["api"]})
    assert any("空カタログ" in f for f in findings)


def test_required_info_missing_field():
    d = _valid_required_info()
    del d["items"][0]["question"]
    findings, _ = kg.validate_required_info(d)
    assert any("question" in f for f in findings)


def test_required_info_non_str_field_fails():
    # 文字列必須フィールドに非str値 (int) を入れたら最低形状違反 (regression guard:
    # 以前は str 値のときだけ空検査し非str値が素通りしていた型検査漏れを塞ぐ)。
    d = _valid_required_info()
    d["items"][0]["concern"] = 123
    findings, _ = kg.validate_required_info(d)
    assert any("concern" in f and "非文字列" in f for f in findings)


def test_required_info_non_str_item_id_fails():
    # 非str の item_id は seen/sorted/heap で型混在 TypeError を招くため早期拒否する。
    d = _valid_required_info()
    d["items"][0]["item_id"] = 42
    findings, _ = kg.validate_required_info(d)
    assert any("item_id" in f and "非文字列" in f for f in findings)


def test_required_info_empty_serves_goals():
    d = _valid_required_info()
    d["items"][0]["serves_goals"] = []
    findings, _ = kg.validate_required_info(d)
    assert any("goal trace" in f for f in findings)


def test_required_info_bad_missing_effect():
    d = _valid_required_info()
    d["items"][0]["missing_effect"] = "explode"
    findings, _ = kg.validate_required_info(d)
    assert any("missing_effect" in f for f in findings)


def test_required_info_domain_uncovered():
    d = _valid_required_info()
    d["in_scope_domains"].append("ui-ux")
    findings, _ = kg.validate_required_info(d)
    assert any("被覆欠落" in f for f in findings)


def test_required_info_na_approved_covers():
    d = _valid_required_info()
    d["in_scope_domains"].append("ui-ux")
    d["na_domains"].append({"domain": "ui-ux", "reason": "CLI only", "approval_state": "approved"})
    findings, result = kg.validate_required_info(d)
    assert findings == []
    assert "ui-ux" in result["coverage_certificate"]["na_approved_domains"]


def test_required_info_na_unapproved_fails():
    d = _valid_required_info()
    d["in_scope_domains"].append("ui-ux")
    d["na_domains"].append({"domain": "ui-ux", "reason": "later", "approval_state": "pending"})
    findings, _ = kg.validate_required_info(d)
    assert any("被覆欠落" in f for f in findings)


def test_required_info_depends_cycle():
    d = _valid_required_info()
    d["items"][0]["depends_on"] = ["fe-state"]
    d["items"][1]["depends_on"] = ["api-contract"]
    findings, _ = kg.validate_required_info(d)
    assert any("循環" in f for f in findings)


def test_required_info_depends_dangling():
    d = _valid_required_info()
    d["items"][0]["depends_on"] = ["ghost"]
    findings, _ = kg.validate_required_info(d)
    assert any("dangling" in f for f in findings)


# ── doctrine fixtures ─────────────────────────────────────────────────────
def _valid_doctrine() -> dict:
    return {
        "schema_version": "1.0",
        "concerns": [
            {"concern_id": "presentation", "authority": "Apple HIG"},
            {"concern_id": "application-architecture", "authority": "Clean Architecture"},
            {"concern_id": "security", "authority": "OWASP ASVS"},
            {"concern_id": "reliability", "authority": "Google SRE"},
        ],
        "categories": ["ui-ux", "backend", "security", "infrastructure"],
        "category_concern_map": {
            "ui-ux": ["presentation"],
            "backend": ["application-architecture"],
            "security": ["security"],
            "infrastructure": ["reliability"],
        },
        "pending_exceptions": [],
    }


def test_doctrine_valid():
    findings, result = kg.validate_doctrine(_valid_doctrine())
    assert findings == []
    assert result["status"] == "ok"
    assert result["category_concern_mapping"]["ui-ux"] == ["presentation"]
    assert result["concern_authorities"]["security"] == "OWASP ASVS"


def test_doctrine_empty_concerns():
    findings, _ = kg.validate_doctrine({"concerns": []})
    assert any("concerns" in f for f in findings)


def test_doctrine_duplicate_concern():
    d = _valid_doctrine()
    d["concerns"].append({"concern_id": "security", "authority": "other"})
    findings, _ = kg.validate_doctrine(d)
    assert any("重複" in f for f in findings)


def test_doctrine_missing_authority():
    d = _valid_doctrine()
    d["concerns"][0]["authority"] = ""
    findings, _ = kg.validate_doctrine(d)
    assert any("authority 欠落" in f for f in findings)


def test_doctrine_unmapped_category_fails():
    d = _valid_doctrine()
    d["categories"].append("payments")
    findings, _ = kg.validate_doctrine(d)
    assert any("全射違反" in f for f in findings)


def test_doctrine_pending_exception_covers():
    d = _valid_doctrine()
    d["categories"].append("payments")
    d["pending_exceptions"].append(
        {"category": "payments", "owner": "team-x", "reason": "TBD", "approval_state": "pending"}
    )
    findings, result = kg.validate_doctrine(d)
    assert findings == []
    assert result["pending_exceptions"][0]["category"] == "payments"


def test_doctrine_pending_exception_incomplete():
    d = _valid_doctrine()
    d["categories"].append("payments")
    d["pending_exceptions"].append({"category": "payments", "owner": "team-x"})
    findings, _ = kg.validate_doctrine(d)
    assert any("reason 欠落" in f or "approval_state 欠落" in f for f in findings)


def test_doctrine_dangling_concern():
    d = _valid_doctrine()
    d["category_concern_map"]["ui-ux"] = ["ghost-concern"]
    findings, _ = kg.validate_doctrine(d)
    assert any("dangling" in f for f in findings)


def test_doctrine_extra_mapping_key():
    d = _valid_doctrine()
    d["category_concern_map"]["stray"] = ["presentation"]
    findings, _ = kg.validate_doctrine(d)
    assert any("in-scope 外" in f for f in findings)


def test_doctrine_orphan_concern():
    # どの category からも写像されない concern は orphan (knowledge 孤立 node と対称)
    d = _valid_doctrine()
    d["concerns"].append({"concern_id": "unused", "authority": "Some Authority"})
    findings, _ = kg.validate_doctrine(d)
    assert any("orphan concern" in f for f in findings)


# ── cross profile ─────────────────────────────────────────────────────────
def _taxonomy(cats):
    return {"categories": [{"id": c, "label": c} for c in cats]}


def _cross_inputs():
    cats = ["ui-ux", "backend", "security", "infrastructure"]
    tax = _taxonomy(cats)
    doc = _valid_doctrine()  # categories = 同一4件
    ri = {
        "in_scope_domains": ["ui-ux", "backend", "api"],
        "items": [
            _item("a", "ui-ux"),
            _item("b", "backend"),
            _item("c", "api"),  # api は extra domain だが concern=application-architecture ∈ doctrine
        ],
    }
    # _item の concern は application-architecture (既定) で doctrine concerns に存在
    return tax, doc, ri


def test_cross_valid():
    tax, doc, ri = _cross_inputs()
    findings, result = kg.validate_cross(tax, doc, ri)
    assert findings == []
    assert result["status"] == "ok"
    assert result["extra_domains"] == ["api"]
    assert "backend" in result["shared_categories"]


def test_cross_category_mismatch():
    tax, doc, ri = _cross_inputs()
    tax["categories"].append({"id": "payments", "label": "payments"})
    findings, _ = kg.validate_cross(tax, doc, ri)
    assert any("category 集合" in f and "不一致" in f for f in findings)


def test_cross_concern_dangling():
    tax, doc, ri = _cross_inputs()
    ri["items"].append(_item("x", "backend"))
    ri["items"][-1]["concern"] = "nonexistent-concern"
    findings, _ = kg.validate_cross(tax, doc, ri)
    assert any("cross dangling" in f for f in findings)


def test_cross_empty_taxonomy():
    _, doc, ri = _cross_inputs()
    findings, _ = kg.validate_cross({"categories": []}, doc, ri)
    assert any("taxonomy.categories" in f for f in findings)


# ── scale robustness (A3 if思考: 深い連鎖で再帰上限クラッシュしない) ──────────
def test_deep_chain_no_recursion_error():
    # 1500 段の depends_on 線形連鎖 (n{i} depends_on n{i-1})。再帰 DFS だと RecursionError。
    n = 1500
    entries = [{"knowledge_id": "n0000", "depends_on": []}]
    for i in range(1, n):
        entries.append({"knowledge_id": f"n{i:04d}", "depends_on": [f"n{i-1:04d}"]})
    findings, result = kg.validate_knowledge({"entries": entries})
    assert findings == []
    assert result["status"] == "ok"
    assert result["topo_order"][0] == "n0000"
    assert result["topo_order"][-1] == f"n{n-1:04d}"


def test_deep_chain_cycle_detected_without_crash():
    n = 1500
    entries = [{"knowledge_id": f"n{i:04d}", "depends_on": [f"n{i-1:04d}"]} for i in range(1, n)]
    entries.insert(0, {"knowledge_id": "n0000", "depends_on": [f"n{n-1:04d}"]})  # 環を閉じる
    findings, _ = kg.validate_knowledge({"entries": entries})
    assert any("循環" in f for f in findings)


# ── shipped-asset parity (A3 #4: 合成 fixture でなく実出荷資産を validator に通す) ──
_SKILLS = Path(__file__).resolve().parent.parent / "skills"
_REF = _SKILLS / "ref-system-design-knowledge" / "references"
_ELICIT_REF = _SKILLS / "run-system-spec-elicit" / "references"


def _load_json(p):
    return json.loads(Path(p).read_text(encoding="utf-8"))


def test_shipped_knowledge_catalog_passes():
    findings, result = kg.validate_knowledge(_load_json(_REF / "knowledge-catalog.json"))
    assert findings == [], f"出荷 knowledge-catalog が validator を通らない: {findings}"
    assert result["status"] == "ok"


def test_shipped_doctrine_registry_passes():
    findings, _ = kg.validate_doctrine(_load_json(_REF / "doctrine-anchor-registry.json"))
    assert findings == [], f"出荷 doctrine-anchor-registry が validator を通らない: {findings}"


def test_shipped_required_info_catalog_passes():
    findings, _ = kg.validate_required_info(_load_json(_ELICIT_REF / "required-info-catalog.json"))
    assert findings == [], f"出荷 required-info-catalog が validator を通らない: {findings}"


def test_shipped_assets_cross_consistent():
    findings, result = kg.validate_cross(
        _load_json(_REF / "system-category-taxonomy.json"),
        _load_json(_REF / "doctrine-anchor-registry.json"),
        _load_json(_ELICIT_REF / "required-info-catalog.json"),
    )
    assert findings == [], f"出荷資産の cross 整合が破れている: {findings}"
    assert result["extra_domains"] == ["api"]


# ── main() CLI 経路 ────────────────────────────────────────────────────────
def test_main_knowledge_ok(tmp_path, capsys):
    path = write(tmp_path, "kc.json", _valid_knowledge())
    rc = kg.main(["--profile", "knowledge", "--input", path])
    assert rc == 0
    out = json.loads(capsys.readouterr().out)
    assert out["status"] == "ok"


def test_main_order_flag(tmp_path, capsys):
    path = write(tmp_path, "kc.json", _valid_knowledge())
    rc = kg.main(["--profile", "knowledge", "--input", path, "--order"])
    assert rc == 0
    order = json.loads(capsys.readouterr().out)
    assert isinstance(order, list) and "clean-code" in order


def test_main_order_flag_doctrine_rejected(tmp_path):
    path = write(tmp_path, "dr.json", _valid_doctrine())
    rc = kg.main(["--profile", "doctrine", "--input", path, "--order"])
    assert rc == 2


def test_main_violation_exit1(tmp_path):
    path = write(tmp_path, "kc.json", {"entries": []})
    rc = kg.main(["--profile", "knowledge", "--input", path])
    assert rc == 1


def test_main_missing_file_exit2():
    rc = kg.main(["--profile", "knowledge", "--input", "/no/such/file.json"])
    assert rc == 2


def test_main_bad_json_exit2(tmp_path):
    p = tmp_path / "bad.json"
    p.write_text("{not json", encoding="utf-8")
    rc = kg.main(["--profile", "knowledge", "--input", str(p)])
    assert rc == 2


def test_main_non_object_exit2(tmp_path):
    p = tmp_path / "arr.json"
    p.write_text("[]", encoding="utf-8")
    rc = kg.main(["--profile", "required-info", "--input", str(p)])
    assert rc == 2


def test_main_required_info_ok(tmp_path, capsys):
    path = write(tmp_path, "ri.json", _valid_required_info())
    rc = kg.main(["--profile", "required-info", "--input", path])
    assert rc == 0
    out = json.loads(capsys.readouterr().out)
    assert out["coverage_certificate"]["total_items"] == 3


def test_main_doctrine_ok(tmp_path, capsys):
    path = write(tmp_path, "dr.json", _valid_doctrine())
    rc = kg.main(["--profile", "doctrine", "--input", path])
    assert rc == 0
    out = json.loads(capsys.readouterr().out)
    assert out["status"] == "ok"


def test_main_cross_ok(tmp_path, capsys):
    tax, doc, ri = _cross_inputs()
    tp = write(tmp_path, "tax.json", tax)
    dp = write(tmp_path, "doc.json", doc)
    rp = write(tmp_path, "ri.json", ri)
    rc = kg.main(["--profile", "cross", "--taxonomy", tp, "--doctrine", dp, "--required-info", rp])
    assert rc == 0
    out = json.loads(capsys.readouterr().out)
    assert out["status"] == "ok"
    assert out["extra_domains"] == ["api"]


def test_main_cross_missing_args_exit2(tmp_path):
    tp = write(tmp_path, "tax.json", _taxonomy(["ui-ux"]))
    rc = kg.main(["--profile", "cross", "--taxonomy", tp])
    assert rc == 2


def test_main_input_required_for_non_cross_exit2():
    rc = kg.main(["--profile", "knowledge"])
    assert rc == 2
