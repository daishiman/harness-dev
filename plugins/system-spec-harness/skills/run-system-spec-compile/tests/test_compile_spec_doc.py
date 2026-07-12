#!/usr/bin/env python3
# /// script
# name: test-compile-spec-doc
# version: 0.1.0
# purpose: run-system-spec-compile の受入テスト。IN1(validate-coverage-matrix.py + validate-source-citation.py が fixture spec-state/fetched-references に exit0)/OUT1(生成章がカテゴリ×プラットフォームの確定/対象外理由と最新ドキュメント出典を含む)/章 frontmatter の確定マーカー(status:confirmed + spec_cells)を検証する。
# inputs:
#   - argv: pytest 収集 (引数なし)
# outputs:
#   - pytest 結果
#   - exit: 0=PASS / 非0=FAIL
# contexts: [C, E]
# network: false
# write-scope: none (tmp_path のみ)
# dependencies: []
# requires-python: ">=3.9"
# ///
"""run-system-spec-compile acceptance tests (IN1 / OUT1 / 確定マーカー / index 相互参照)。"""
from __future__ import annotations

import copy
import importlib.util
import json
import subprocess
import sys
from pathlib import Path

import pytest

SKILL_DIR = Path(__file__).resolve().parents[1]
PLUGIN_ROOT = SKILL_DIR.parents[1]
FIXTURES = SKILL_DIR / "fixtures"
SPEC = FIXTURES / "spec-state.json"
REFS = FIXTURES / "fetched-references.json"
COV_VALIDATOR = PLUGIN_ROOT / "scripts" / "validate-coverage-matrix.py"
CITE_VALIDATOR = PLUGIN_ROOT / "scripts" / "validate-source-citation.py"


def _load_mod():
    path = SKILL_DIR / "scripts" / "compile-spec-doc.py"
    spec = importlib.util.spec_from_file_location("compile_spec_doc", path)
    assert spec and spec.loader
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


mod = _load_mod()


def _spec() -> dict:
    return json.loads(SPEC.read_text(encoding="utf-8"))


def _refs() -> dict:
    return json.loads(REFS.read_text(encoding="utf-8"))


def _run(script: Path, args: list[str]) -> int:
    return subprocess.run(
        [sys.executable, str(script), *args], capture_output=True, text=True
    ).returncode


# --------------------------------------------------------------------------- #
# IN1 (inner, script): 生成直前の spec-state / fetched-references に            #
# validate-coverage-matrix.py と validate-source-citation.py が exit0          #
# --------------------------------------------------------------------------- #
def test_IN1_coverage_matrix_exit0_loop():
    assert SPEC.is_file()
    assert _run(COV_VALIDATOR, ["--matrix", str(SPEC)]) == 0


def test_IN1_coverage_matrix_exit0_require_complete():
    # 生成直前 (最終) は未収集0 が必須。fixture は最終状態を表す。
    assert _run(COV_VALIDATOR, ["--matrix", str(SPEC), "--require-complete"]) == 0


def test_IN1_source_citation_exit0():
    assert REFS.is_file()
    assert _run(CITE_VALIDATOR, ["--targets", str(SPEC), "--references", str(REFS)]) == 0


# --------------------------------------------------------------------------- #
# OUT1 (outer, test): 生成ドキュメントセットがカテゴリ×プラットフォームの        #
# 確定/対象外理由と最新ドキュメント出典を含む                                    #
# --------------------------------------------------------------------------- #
def test_OUT1_docset_has_confirmed_excluded_and_citation():
    docset = mod.compile_docset(_spec(), _refs())
    # 確定セルの状態が確定章に現れる
    assert "確定" in docset["database.md"]
    # 対象外セルの理由が対象外章に現れる
    assert "対象外" in docset["maintenance-ops.md"]
    assert "保守運用は外部委託のため本仕様の対象外" in docset["maintenance-ops.md"]
    # 最新ドキュメント出典 (source_url + version + 公式発行元) が該当章に現れる
    assert "https://www.postgresql.org/docs/16/" in docset["database.md"]
    assert "16.1" in docset["database.md"]
    assert "PostgreSQL Global Development Group" in docset["database.md"]
    assert "https://react.dev/reference/react" in docset["frontend.md"]
    assert "https://nodejs.org/docs/latest/api/" in docset["backend.md"]


def test_OUT1_mixed_chapter_shows_both_states_and_reason():
    docset = mod.compile_docset(_spec(), _refs())
    sec = docset["security.md"]
    assert "確定" in sec  # web/mobile/tablet
    assert "対象外" in sec  # desktop-*
    assert "デスクトップ配信対象外" in sec  # 対象外理由


def test_OUT1_every_chapter_has_all_platforms():
    docset = mod.compile_docset(_spec(), _refs())
    for cat in ("database", "auth", "security", "maintenance-ops"):
        chap = docset[f"{cat}.md"]
        for pf in mod.CANONICAL_PLATFORMS:
            assert f"({pf})" in chap


def test_OUT1_matches_golden_fixtures():
    docset = mod.compile_docset(_spec(), _refs())
    golden = {
        "00-requirements-definition.md": "expected-00-requirements-definition.md",
        "database.md": "expected-database.md",
        "maintenance-ops.md": "expected-maintenance-ops.md",
        "security.md": "expected-security.md",
        "index.md": "expected-index.md",
    }
    for src, gold in golden.items():
        expected = (FIXTURES / gold).read_text(encoding="utf-8")
        got = docset[src]
        got = got if got.endswith("\n") else got + "\n"
        assert got == expected, f"{src} が golden {gold} と不一致"


# --------------------------------------------------------------------------- #
# 要件定義書 (上位概念 U1-U9) を最初の章に + serves_goals トレース (要件 C9)     #
# --------------------------------------------------------------------------- #
def test_requirements_definition_is_first_chapter():
    docset = mod.compile_docset(_spec(), _refs())
    keys = list(docset.keys())
    assert keys[0] == "00-requirements-definition.md"  # 最初の章
    chap = docset["00-requirements-definition.md"]
    fm = _parse_frontmatter(chap)
    assert fm["category"] == "requirements-definition"
    assert fm["status"] == "confirmed"  # foundation.confirmed=true
    # U1-U9 の見出しと上位概念が現れる
    for heading in ("## U1 本質的目的", "## U3 ゴール", "## U9 具体的にやりたいこと"):
        assert heading in chap
    assert "社内の請求・監査業務を単一の Web システムへ統合" in chap
    assert "| G1 |" in chap and "| G2 |" in chap
    assert "## 意思決定支援 (decisions)" in chap
    assert "recommended_pending_confirmation" in chap
    assert "managed-free" in chap
    assert "確認待ち" in chap  # AI推奨はユーザー確認済みとして描画しない


def test_render_decisions_confirmed_shows_user_choice():
    spec = _spec()
    spec["decisions"][0]["status"] = "confirmed"
    spec["decisions"][0]["user_decision"] = {
        "option_id": "managed-free", "confirmed_at": "2026-07-11T01:00:00Z"
    }
    rendered = mod.render_decisions(spec)
    assert "managed-free @ 2026-07-11T01:00:00Z" in rendered


def test_requirements_definition_draft_when_no_foundation():
    spec = _spec()
    del spec["requirements_foundation"]  # 上位概念が無い spec-state でも空落ちさせない
    docset = mod.compile_docset(spec, _refs())
    chap = docset["00-requirements-definition.md"]
    fm = _parse_frontmatter(chap)
    assert fm["status"] == "draft"  # 未確定
    assert "(未記入)" in chap  # 空要素は placeholder


def test_chapter_frontmatter_has_serves_goals():
    docset = mod.compile_docset(_spec(), _refs())
    # 確定セルの serves_goals がカテゴリ章 frontmatter へ集約される
    assert _parse_frontmatter(docset["database.md"])["serves_goals"] == "[G1]"
    assert _parse_frontmatter(docset["ui-ux.md"])["serves_goals"] == "[G2]"
    assert _parse_frontmatter(docset["backend.md"])["serves_goals"] == "[G1, G2]"
    # 全セル対象外の章は serves_goals 空
    assert _parse_frontmatter(docset["maintenance-ops.md"])["serves_goals"] == "[]"


def test_chapter_serves_goals_aggregates_union_dedup():
    spec = _spec()
    # 同一カテゴリの複数セルに重複含む serves_goals を付与 → 和集合・順序保持・重複除去
    spec["matrix"]["database"]["mobile"]["serves_goals"] = ["G2", "G1"]
    assert mod.chapter_serves_goals(spec, "database") == ["G1", "G2"]
    assert mod.chapter_serves_goals(spec, "maintenance-ops") == []


def test_index_references_requirements_definition_first():
    docset = mod.compile_docset(_spec(), _refs())
    index = docset["index.md"]
    assert "[要件定義書](./00-requirements-definition.md)" in index
    # 章一覧テーブルより前 (先頭) に要件定義書節が来る
    assert index.index("要件定義書 (上位概念・憲法)") < index.index("## 章一覧と集約状態")
    # index の章一覧に serves_goals 列 (資するゴール) が現れる
    assert "資するゴール" in index


def test_foundation_status_helper():
    assert mod.foundation_status({"requirements_foundation": {"confirmed": True}}) == "confirmed"
    assert mod.foundation_status({"requirements_foundation": {"confirmed": False}}) == "draft"
    assert mod.foundation_status({}) == "draft"  # 不在も draft
    assert mod.requirements_foundation({"requirements_foundation": [1]}) == {}  # 非 dict は空


# --------------------------------------------------------------------------- #
# 章 frontmatter の確定マーカー (status:confirmed + spec_cells + category)      #
# --------------------------------------------------------------------------- #
def _parse_frontmatter(text: str) -> dict:
    assert text.startswith("---")
    fm_block = text.split("---", 2)[1]
    fm: dict = {}
    for line in fm_block.splitlines():
        if ":" in line:
            k, _, v = line.partition(":")
            fm[k.strip()] = v.strip()
    return fm


def test_confirmed_chapter_has_status_and_spec_cells():
    docset = mod.compile_docset(_spec(), _refs())
    fm = _parse_frontmatter(docset["database.md"])
    assert fm["status"] == "confirmed"
    assert fm["category"] == "database"
    assert fm["spec_cells"].startswith("[database.web")
    # spec_cells は 6 platform の対応セル id を持つ
    for pf in mod.CANONICAL_PLATFORMS:
        assert f"database.{pf}" in fm["spec_cells"]


def test_excluded_chapter_is_confirmed_terminal():
    docset = mod.compile_docset(_spec(), _refs())
    fm = _parse_frontmatter(docset["maintenance-ops.md"])
    # 全セル対象外 = 終端カテゴリ → confirmed (章凍結)
    assert fm["status"] == "confirmed"
    assert fm["aggregate"] == "対象外"


def test_spec_cell_ids_and_status_helpers():
    spec = _spec()
    assert mod.spec_cell_ids(spec, "database") == [
        f"database.{pf}" for pf in mod.CANONICAL_PLATFORMS
    ]
    assert mod.chapter_status("確定") == "confirmed"
    assert mod.chapter_status("対象外") == "confirmed"
    assert mod.chapter_status("収集中") == "draft"
    assert mod.chapter_status("未着手") == "draft"


# --------------------------------------------------------------------------- #
# draft 章 (進行中カテゴリ) の描画: 未収集/収集中 は confirmed マーカーを持たない  #
# --------------------------------------------------------------------------- #
def _draft_spec() -> dict:
    """web=確定 / mobile=未収集 の混在で aggregate=収集中 になる合成 spec。"""
    spec = _spec()
    row = spec["matrix"]["database"]
    row["mobile"] = {"state": "未収集"}
    # category_aggregate は render では再導出されるため宣言値に依存しない
    return spec


def test_draft_chapter_status_is_draft():
    spec = _draft_spec()
    assert mod.category_aggregate(spec, "database") == "収集中"
    chap = mod.render_chapter(spec, "database", {})
    fm = _parse_frontmatter(chap)
    assert fm["status"] == "draft"
    assert fm["aggregate"] == "収集中"
    # 収集中セルは状態表に「未収集」と「収集中 (未確定)」根拠を持つ
    assert "未収集" in chap
    assert "収集中 (未確定)" in chap


def test_render_state_table_missing_cell():
    spec = _spec()
    del spec["matrix"]["database"]["mobile"]  # platform 行欠落
    table = mod.render_state_table(spec, "database")
    assert "モバイル (mobile) | 未収集 | —" in table


# --------------------------------------------------------------------------- #
# derive_aggregate 真理値表 (validator と SSOT 整合)                            #
# --------------------------------------------------------------------------- #
def test_derive_aggregate_truth_table():
    assert mod.derive_aggregate([]) == "未着手"
    assert mod.derive_aggregate(["未収集", "未収集"]) == "未着手"
    assert mod.derive_aggregate(["対象外", "対象外"]) == "対象外"
    assert mod.derive_aggregate(["確定", "未収集"]) == "収集中"
    assert mod.derive_aggregate(["確定", "対象外"]) == "確定"


# --------------------------------------------------------------------------- #
# 出典記録の章割り当て (assigned / unassigned)                                  #
# --------------------------------------------------------------------------- #
def test_references_by_category_assigned():
    by_cat, unassigned = mod.references_by_category(_spec(), _refs())
    assert [r["target_id"] for r in by_cat["database"]] == ["postgres"]
    assert [r["target_id"] for r in by_cat["frontend"]] == ["react"]
    assert unassigned == []


def test_references_unassigned_go_to_index():
    spec = _spec()
    # category を持たない target を追加し、その参照を未割当にする
    spec["targets"].append({"target_id": "orphan-lib"})
    refs = _refs()
    refs["references"].append(
        {
            "target_id": "orphan-lib",
            "source_url": "https://example.com/docs",
            "official_host": "example.com",
            "official_publisher": "Example",
            "version": "1.0",
            "retrieved_at": "2026-07-11T00:00:00Z",
            "latest_checked_at": "2026-07-11T00:00:00Z",
        }
    )
    by_cat, unassigned = mod.references_by_category(spec, refs)
    assert [r["target_id"] for r in unassigned] == ["orphan-lib"]
    index = mod.render_index(spec, by_cat, unassigned)
    assert "https://example.com/docs" in index  # 未割当参照が index 全体出典へ


def test_ref_host_fallback_from_url():
    ref = {"source_url": "https://fallback.example/x", "version": "1"}
    assert mod._ref_host(ref) == "fallback.example"
    assert mod._ref_version({"last_updated": "2026-01-01"}) == "2026-01-01"
    assert mod._ref_version({}) == "-"


# --------------------------------------------------------------------------- #
# index 相互参照 (R3-crosslink)                                                 #
# --------------------------------------------------------------------------- #
def test_index_crosslinks_all_chapters_and_aggregates():
    docset = mod.compile_docset(_spec(), _refs())
    index = docset["index.md"]
    for cat in mod._category_ids(_spec()):
        assert f"[{cat}.md](./{cat}.md)" in index  # 各章へのリンク
    # 集約状態 4 値の語彙が index に現れる
    for label in ("未着手", "収集中", "確定", "対象外"):
        assert label in index
    # サマリに対象外カテゴリが列挙される
    assert "maintenance-ops" in index


# --------------------------------------------------------------------------- #
# 入力契約違反 (CompileError)                                                   #
# --------------------------------------------------------------------------- #
def test_compile_error_on_missing_categories():
    bad = {"platforms": [], "matrix": {}}
    with pytest.raises(mod.CompileError):
        mod.compile_docset(bad, {"references": []})


def test_compile_error_on_missing_row():
    spec = _spec()
    del spec["matrix"]["database"]
    with pytest.raises(mod.CompileError):
        mod.compile_docset(spec, _refs())


def test_references_not_a_list():
    with pytest.raises(mod.CompileError):
        mod.references_by_category(_spec(), {"references": "nope"})


def test_category_label_fallback():
    assert mod.category_label({"categories": []}, "unknown") == "unknown"


def test_render_design_refs_non_canonical_not_empty():
    # 非正準カテゴリでも空落ちせず、SSOT (resource-map) への汎用ポインタを必ず添える (A-1)。
    out = mod.render_design_refs("no-such-category")
    assert "割り当てた設計知識参照なし" not in out
    assert "resource-map.yaml" in out
    assert "resource-map 未定義" in out


def test_render_design_knowledge_contains_deep_meaning_not_only_pointer():
    rendered = mod.render_design_refs("database", _spec())
    for heading in (
        "#### 目的",
        "#### 解決する問題",
        "#### 適用条件",
        "#### 非適用条件",
        "#### トレードオフ・失敗モード",
        "#### goalへの寄与",
    ):
        assert heading in rendered
    assert "businessの重要なruleと用語" in rendered
    assert rendered.count("ref-system-design-knowledge/references/ddd.md") == 1


def test_render_deepened_project_candidate_into_goal_related_chapter():
    spec = _spec()
    spec["knowledge_candidates"] = [
        {
            "id": "offline-first-conflict-resolution",
            "topic": "offline-first conflict resolution",
            "status": "deepened",
            "problem": "オフライン更新競合",
            "serves_goals": ["G1"],
            "source_refs": [],
            "card": {
                "purpose": "更新損失を防ぐ",
                "problems": ["最終書込優先で更新が消える"],
                "applies_when": ["複数端末が切断中に更新する"],
                "does_not_apply_when": ["単一writerで常時接続する"],
                "tradeoffs": ["同期メタデータが増える"],
                "failure_modes": ["競合を黙って上書きする"],
                "goal_contribution": ["G1の継続利用に寄与する"],
            },
        }
    ]
    rendered = mod.render_design_refs("database", spec)
    assert "project candidate: `offline-first-conflict-resolution` (`deepened`)" in rendered
    assert "単一writerで常時接続する" in rendered
    assert "G1の継続利用に寄与する" in rendered


def test_category_design_refs_derived_from_resource_map():
    # SSOT = resource-map.yaml の read_when。ハードコード写像のドリフトが無いことを検証 (A-1)。
    # database の read_when は ddd のみ (clean-architecture は backend/frontend 対応 → 混入しない)。
    assert mod.category_design_refs("database") == ["ddd.md"]
    assert "clean-architecture.md" not in mod.category_design_refs("database")
    # backend は read_when に "backend" を含む 3 ファイルを resource-map 出現順で導出。
    assert mod.category_design_refs("backend") == [
        "clean-architecture.md",
        "api-design-patterns.md",
        "ddd.md",
    ]
    assert mod.category_design_refs("security") == ["secure-by-design.md"]
    assert mod.category_design_refs("maintenance-ops") == ["clean-code.md"]
    # 非正準カテゴリは無マッチ (空) → render 側が汎用ポインタへ倒す。
    assert mod.category_design_refs("no-such-category") == []


def test_category_design_refs_map_matches_matcher():
    # materialized view (CATEGORY_DESIGN_REFS) が matcher と一致し drift しない。
    for cat_id, refs in mod.CATEGORY_DESIGN_REFS.items():
        assert refs == mod.category_design_refs(cat_id)


# --------------------------------------------------------------------------- #
# CLI (compile) の網羅                                                          #
# --------------------------------------------------------------------------- #
def test_cli_compile_writes_docset(tmp_path):
    out_dir = tmp_path / "system-spec"
    rc = mod.main(
        ["compile", "--spec", str(SPEC), "--references", str(REFS), "--out-dir", str(out_dir)]
    )
    assert rc == 0
    assert (out_dir / "index.md").is_file()
    assert (out_dir / "database.md").is_file()
    # 生成章 frontmatter に確定マーカー
    fm = _parse_frontmatter((out_dir / "database.md").read_text(encoding="utf-8"))
    assert fm["status"] == "confirmed"


def test_cli_compile_matches_golden(tmp_path):
    out_dir = tmp_path / "system-spec"
    assert mod.main(["compile", "--spec", str(SPEC), "--references", str(REFS), "--out-dir", str(out_dir)]) == 0
    got = (out_dir / "index.md").read_text(encoding="utf-8")
    assert got == (FIXTURES / "expected-index.md").read_text(encoding="utf-8")


def test_cli_bad_spec_returns_1(tmp_path):
    missing = tmp_path / "nope.json"
    rc = mod.main(["compile", "--spec", str(missing), "--references", str(REFS), "--out-dir", str(tmp_path / "o")])
    assert rc == 1


def test_cli_compile_error_returns_1(tmp_path):
    bad_spec = tmp_path / "bad.json"
    bad_spec.write_text(json.dumps({"platforms": [], "matrix": {}}), encoding="utf-8")
    rc = mod.main(["compile", "--spec", str(bad_spec), "--references", str(REFS), "--out-dir", str(tmp_path / "o")])
    assert rc == 1


def test_write_docset_creates_files(tmp_path):
    docset = {"a.md": "hello", "index.md": "idx\n"}
    written = mod.write_docset(docset, tmp_path / "out")
    assert len(written) == 2
    assert (tmp_path / "out" / "a.md").read_text(encoding="utf-8") == "hello\n"


def test_load_json_roundtrip(tmp_path):
    p = tmp_path / "x.json"
    p.write_text(json.dumps({"k": 1}), encoding="utf-8")
    assert mod.load_json(str(p)) == {"k": 1}
