"""確定判断ごとの原則採否・knowledge_ref ゲート・知識グラフ順・doctrine 例外の回帰テスト。"""
from __future__ import annotations

import copy
import importlib.util
import json
import subprocess
import sys
from pathlib import Path


SKILL_DIR = Path(__file__).resolve().parents[1]
PLUGIN_ROOT = SKILL_DIR.parents[1]
FIXTURES = SKILL_DIR / "fixtures"
SPEC = FIXTURES / "spec-state.json"
REFS = FIXTURES / "fetched-references.json"
KNOWLEDGE_DIR = PLUGIN_ROOT / "skills" / "ref-system-design-knowledge" / "references"


def _load_mod():
    path = SKILL_DIR / "scripts" / "compile-spec-doc.py"
    spec = importlib.util.spec_from_file_location("compile_spec_doc_knowledge", path)
    assert spec and spec.loader
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


mod = _load_mod()


def _spec() -> dict:
    return json.loads(SPEC.read_text(encoding="utf-8"))


def _qa(spec: dict, qa_id: str) -> dict:
    return next(item for item in spec["qa_log"] if item["id"] == qa_id)


# --------------------------------------------------------------------------- #
# 確定判断ごとの原則採否 (qa_log[].design_applications)                         #
# --------------------------------------------------------------------------- #
def test_render_design_refs_ties_principle_to_chapter_confirmed_decision():
    # card の汎用原則を固定文で「適用済み」にせず、caller が記録した章固有の採否・理由・
    # trade-off を qa_ref と共に描画する。
    spec = _spec()
    _qa(spec, "qa-database")["design_applications"] = [
        {
            "knowledge_ref": "ddd.md#Bounded Context / Context Map",
            "principle": "Bounded Context / Context Map",
            "applicability": "not_applicable",
            "rationale": "単一利用者の単純 CRUD で文脈間翻訳が無いため、境界分割は採用しない",
            "tradeoffs": ["将来複数の業務語彙が生じた場合は再評価する"],
        }
    ]
    rendered = mod.render_design_refs("database", spec)
    assert "### 確定判断ごとの原則採否" in rendered
    assert "確定内容 `qa-database`" in rendered
    assert "対応セル: web, mobile, tablet, desktop-windows, desktop-linux, desktop-macos" in rendered
    assert "Bounded Context / Context Map" in rendered
    assert "`not_applicable`" in rendered
    assert "単一利用者の単純 CRUD" in rendered
    assert "将来複数の業務語彙" in rendered
    assert "資するゴール: G1" in rendered


def test_render_design_refs_distinguishes_dialogue_and_legacy_backfill():
    spec = _spec()
    qa = _qa(spec, "qa-database")
    qa["design_applications"] = [{
        "knowledge_ref": "ddd.md#Bounded Context",
        "principle": "Bounded Context",
        "applicability": "applied",
        "rationale": "DB 境界を明確にする",
        "tradeoffs": ["境界の維持コスト"],
    }]
    assert "設計解釈の記録経路: `dialogue`" in mod.render_design_refs("database", spec)

    qa["design_application_provenance"] = {
        "mode": "legacy_backfill",
        "writer": "set-qa-design-applications",
    }
    rendered = mod.render_design_refs("database", spec)
    assert "設計解釈の記録経路: `legacy_backfill`" in rendered
    assert "`set-qa-design-applications`" in rendered


def test_render_design_refs_missing_application_is_fail_visible_not_generic_pass():
    rendered = mod.render_design_refs("database", _spec())
    assert "設計解釈の記録経路: `unrecorded`" in rendered
    assert "qa_log[].design_applications を writer 経由で補完" in rendered
    assert "上記原則は確定内容" not in rendered


def test_render_design_refs_application_note_explicit_when_no_confirmed_cell():
    # 対象外/収集中カテゴリでは適用先を捏造せず「未確定」を明示する (fail-visible)。
    rendered = mod.render_design_refs("maintenance-ops", _spec())
    assert "### 確定判断ごとの原則採否" in rendered
    assert "確定セルなし。本章は対象外または収集中のため、上記原則の適用先は未確定" in rendered


def test_qa_answer_pointer_does_not_restate_the_whole_answer():
    # 回答本文の正本は「確定内容 (質疑録)」節の 1 箇所。ここは所在と抜粋だけを出す。
    long_answer = "あ" * (mod._ANSWER_EXCERPT_LIMIT + 5)
    pointer = mod._qa_answer_pointer({"answer": long_answer}, "qa-x")
    assert long_answer not in pointer
    assert "…" in pointer and "全文は" in pointer and "`qa-x`" in pointer
    assert mod._qa_answer_pointer({"answer": "短い回答"}, "qa-x") == (
        "「短い回答」 (正本: 本章「確定内容 (質疑録)」の `qa-x`)"
    )
    assert mod._qa_answer_pointer({}, "qa-x") == "(qa_log 本文欠落)"


def test_structured_rationale_stays_inside_fence():
    # rationale は spec-state の逐語。行頭 `###` を含んでも章の見出しへ漏らさない。
    spec = _spec()
    _qa(spec, "qa-database")["design_applications"] = [{
        "knowledge_ref": "ddd.md#Bounded Context",
        "principle": "Bounded Context",
        "applicability": "applied",
        "rationale": "一行目\n### 漏れてはならない見出し",
        "tradeoffs": ["境界の維持コスト"],
    }]
    rendered = mod.render_design_refs("database", spec)
    assert "漏れてはならない見出し" in rendered
    assert not any(
        line.startswith("#") and "漏れてはならない見出し" in line for line in rendered.splitlines()
    )


# --------------------------------------------------------------------------- #
# knowledge_ref 実在ゲート (--repo-root) と再 compile                           #
# --------------------------------------------------------------------------- #
def test_cli_repo_root_resolves_knowledge_ref_and_recompile_drops_stale_rationale(tmp_path):
    spec = _spec()
    application = {
        "knowledge_ref": "skills/ref-system-design-knowledge/references/ddd.md#中核概念",
        "principle": "Bounded Context",
        "applicability": "applied",
        "rationale": "初回の根拠",
        "tradeoffs": ["境界の維持コスト"],
    }
    _qa(spec, "qa-database")["design_applications"] = [application]
    spec_path = tmp_path / "state.json"
    out_dir = tmp_path / "docs"
    argv = [
        "compile", "--spec", str(spec_path), "--references", str(REFS),
        "--out-dir", str(out_dir), "--repo-root", str(PLUGIN_ROOT),
    ]

    spec_path.write_text(json.dumps(spec, ensure_ascii=False), encoding="utf-8")
    assert mod.main(argv) == 0
    assert "初回の根拠" in (out_dir / "database.md").read_text(encoding="utf-8")

    # 根拠を差し替えて再 compile すると、旧い根拠は手書き注記として引き継がれない。
    application["rationale"] = "改訂後の根拠"
    spec_path.write_text(json.dumps(spec, ensure_ascii=False), encoding="utf-8")
    assert mod.main(argv) == 0
    chapter = (out_dir / "database.md").read_text(encoding="utf-8")
    assert "改訂後の根拠" in chapter
    assert "初回の根拠" not in chapter
    assert chapter.count("### 確定判断ごとの原則採否") == 1


# --------------------------------------------------------------------------- #
# カテゴリ → card の写像と知識グラフ順 (C14)                                    #
# --------------------------------------------------------------------------- #
def test_category_specific_cards_for_previously_pointer_only_chapters():
    # ui-ux / infrastructure / testing-qa / dev-workflow が汎用ポインタ節でなく、
    # カテゴリ固有の card へ接続することを回帰検知する。
    assert mod.category_design_refs("ui-ux") == [
        "usability-accessibility.md",
        "information-design.md",
    ]
    # infrastructure は SRE に加え、基盤制約 (実行時間/ペイロード上限/トランザクション到達範囲)
    # を非機能要件として扱う cloud-architecture-patterns を depends_on 順で後に置く。
    assert mod.category_design_refs("infrastructure") == [
        "site-reliability-engineering.md",
        "cloud-architecture-patterns.md",
    ]
    assert mod.category_design_refs("testing-qa") == ["test-strategy.md"]
    assert mod.category_design_refs("dev-workflow") == ["continuous-delivery.md"]
    # 章本文が汎用ポインタ節ではなく card 本文 (深度項目) を描画する。
    rendered = mod.render_design_refs("ui-ux")
    assert "resource-map に未定義" not in rendered
    assert "#### 適用条件" in rendered and "#### トレードオフ・失敗モード" in rendered


def test_knowledge_file_topo_order_matches_validator_script():
    # compile が使う順序が、正本 validate-knowledge-graph.py --profile knowledge --order
    # (subprocess) の出力を file 名へ写したものと完全一致する (二重実装のドリフト防止・C14)。
    validator = PLUGIN_ROOT / "scripts" / "validate-knowledge-graph.py"
    catalog_path = KNOWLEDGE_DIR / "knowledge-catalog.json"
    result = subprocess.run(
        [sys.executable, str(validator), "--profile", "knowledge", "--input", str(catalog_path), "--order"],
        capture_output=True, text=True,
    )
    assert result.returncode == 0, result.stderr
    catalog = json.loads(catalog_path.read_text(encoding="utf-8"))
    file_of = {e["knowledge_id"]: e["file"] for e in catalog["entries"]}
    assert [file_of[k] for k in json.loads(result.stdout)] == mod._knowledge_file_topo_order()


def test_category_design_refs_follows_knowledge_topo_order():
    # 描画順は resource-map の記述順ではなく knowledge-catalog.json の depends_on が定める
    # 位相順に従う。A depends_on B は B が前提 (B を先に出す)。
    topo = mod._knowledge_file_topo_order()
    assert topo.index("ddd.md") < topo.index("clean-architecture.md")
    assert topo.index("clean-architecture.md") < topo.index("api-design-patterns.md")
    for cat_id, refs in mod.CATEGORY_DESIGN_REFS.items():
        ranked = [f for f in refs if f in topo]
        assert ranked == sorted(ranked, key=topo.index), cat_id


# --------------------------------------------------------------------------- #
# doctrine anchor の pending 例外                                              #
# --------------------------------------------------------------------------- #
def _registry_with_pending(monkeypatch, entry: dict) -> dict:
    reg = copy.deepcopy(mod._doctrine_registry())
    reg["pending_exceptions"] = [entry]
    monkeypatch.setattr(mod, "_DOCTRINE_REGISTRY", reg)
    return reg


def test_approved_pending_exception_renders_resolved_authorities(monkeypatch):
    # プロジェクト固有カテゴリの確定を、共通の category_concern_map へ昇格させずに章へ通す。
    reg = _registry_with_pending(monkeypatch, {
        "category": "project-only",
        "owner": "spec-owner",
        "reason": "製品固有カテゴリ",
        "approval_state": "approved",
        "concerns": ["security"],
    })
    authority = next(c["authority"] for c in reg["concerns"] if c["concern_id"] == "security")
    rendered = mod.render_doctrine_anchors("project-only")
    assert mod.DOCTRINE_APPROVED_EXCEPTION_NOTE in rendered
    assert "approval_state: approved" in rendered
    assert authority in rendered
    assert mod.DOCTRINE_PENDING_NOTE not in rendered


def test_unapproved_pending_exception_stays_provisional(monkeypatch):
    # concerns を書いていても未承認なら authority を描かず、暫定扱いを明示する。
    reg = _registry_with_pending(monkeypatch, {
        "category": "project-only",
        "owner": "spec-owner",
        "reason": "上流指針を検討中",
        "approval_state": "pending",
        "concerns": ["security"],
    })
    authority = next(c["authority"] for c in reg["concerns"] if c["concern_id"] == "security")
    rendered = mod.render_doctrine_anchors("project-only")
    assert mod.DOCTRINE_PENDING_NOTE in rendered
    assert "approval_state: pending" in rendered
    assert authority not in rendered
