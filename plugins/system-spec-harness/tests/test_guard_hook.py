# /// script
# name: test-guard-hook
# version: 0.1.0
# purpose: C11 guard-confirmed-chapter-overwrite hook の負例/正例を Write/Edit/Bash × 確定章(C03実出力形状)/対象外混在確定章/再オープン章/新規章/正本spec-state.json直接書換/正本位置外spec-state(交差汚染回避)/自pluginパス誤爆回避(system-spec境界)/正本解決不能confirmed章の層別fail-closed/read-only の判定分岐で網羅検証する pytest (in-process decide() + subprocess で stdin→exit を確認)。正本位置は system-spec/spec-state.json の1経路のみ。フィクスチャは C03 実 frontmatter (category + spec_cells list) と writer 正本 reopen キー (reopened_from/reopen_reason) に整合。
# inputs:
#   - argv: pytest 経由 (直接 argv は取らない)
# outputs:
#   - stdout: pytest 結果
#   - exit: 0=all pass / 1=failure
# contexts: [E, C]
# network: false
# write-scope: none
# dependencies: []
# requires-python: ">=3.9"
# ///
"""C11 guard-confirmed-chapter-overwrite hook の負例/正例検証。

判定分岐 (Write/Edit/Bash × 確定章/対象外混在確定章/再オープン章/新規章/spec-state.json/read-only) を
in-process の decide()/bash_decision() で網羅し、stdin→exit の end-to-end を subprocess で確認する。

フィクスチャは C03 (compile-spec-doc.py render_frontmatter) の実出力形状に整合させる:
  frontmatter = status/category/aggregate/spec_cells([<cat>.<pf>, ...] list)。章ファイル名は <category>.md。
reopen フィクスチャは writer (apply-spec-transition.py) 正本キー reopened_from/reopen_reason を用いる。
"""
from __future__ import annotations

import importlib.util
import json
import subprocess
import sys
from pathlib import Path

HOOK = Path(__file__).resolve().parent.parent / "hooks" / "guard-confirmed-chapter-overwrite.py"


def _load():
    spec = importlib.util.spec_from_file_location("guard_hook", HOOK)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


g = _load()

PLATFORMS = ["web", "mobile", "tablet", "desktop-windows", "desktop-linux", "desktop-macos"]
DESKTOPS = ["desktop-windows", "desktop-linux", "desktop-macos"]
CATEGORIES = ["database", "auth", "ui-ux", "security", "infrastructure", "backend", "frontend", "maintenance-ops"]


# ── フィクスチャ ────────────────────────────────────────────────────────────
def _spec_state(*, security_mixed: bool = False) -> dict:
    """全カテゴリ×全platform を『確定』にした spec-state。

    security_mixed=True で security の desktop×3 を『対象外』へ (C03 混在確定章の再現)。
    """
    matrix = {c: {p: {"state": "確定", "qa_ref": "qa-001"} for p in PLATFORMS} for c in CATEGORIES}
    if security_mixed:
        for p in DESKTOPS:
            matrix["security"][p] = {"state": "対象外", "reason": "デスクトップ配信対象外"}
    return {
        "categories": [{"id": c, "label": c} for c in CATEGORIES],
        "platforms": PLATFORMS,
        "matrix": matrix,
        "qa_log": [{"id": "qa-001", "question": "q", "answer": "a"}],
    }


def _chapter(status: str, category: str, platforms: list[str] | None = None, aggregate: str = "確定") -> str:
    """C03 実出力形状の章 frontmatter (category + spec_cells list) を組み立てる。"""
    pfs = platforms if platforms is not None else PLATFORMS
    cells = ", ".join(f"{category}.{p}" for p in pfs)
    return (
        f"---\nstatus: {status}\ncategory: {category}\n"
        f"aggregate: {aggregate}\nspec_cells: [{cells}]\n---\n# 章\n本文\n"
    )


def _make_project(tmp_path: Path, *, reopen: str | None = None, security_mixed: bool = False) -> Path:
    """spec-state.json + system-spec/ 章 (C03 形状) を tmp に構築。

    reopen: None=全確定 / "state"=auth/mobile を writer 実出力 (未収集+reopened_from) へ /
            "flag"=state は確定のまま reopen 正本キーだけ付与 (フラグ分岐検証)。
    security_mixed: True で security 章を 確定+対象外 混在にする。
    """
    spec = _spec_state(security_mixed=security_mixed)
    if reopen == "state":
        spec["matrix"]["auth"]["mobile"] = {"state": "未収集", "reopened_from": "確定", "reopen_reason": "R4-reopen"}
    elif reopen == "flag":
        spec["matrix"]["auth"]["mobile"] = {
            "state": "確定", "qa_ref": "qa-001", "reopened_from": "確定", "reopen_reason": "R4-reopen",
        }

    ss = tmp_path / "system-spec"
    ss.mkdir()
    # 正本位置: <root>/system-spec/spec-state.json (spec-state-contract.md「正本位置」節)
    (ss / "spec-state.json").write_text(json.dumps(spec, ensure_ascii=False), encoding="utf-8")
    # 確定章 (全セル確定)
    (ss / "database.md").write_text(_chapter("confirmed", "database"), encoding="utf-8")
    # 再オープン対象を含み得る章 (frontmatter は confirmed のまま・セル側で再オープン)
    (ss / "auth.md").write_text(_chapter("confirmed", "auth"), encoding="utf-8")
    # 未確定 (draft) 章
    (ss / "ui-ux.md").write_text(_chapter("draft", "ui-ux", aggregate="収集中"), encoding="utf-8")
    # 対象外混在の確定章 (web/mobile/tablet 確定 + desktop×3 対象外 でも status:confirmed)
    (ss / "security.md").write_text(_chapter("confirmed", "security"), encoding="utf-8")
    return tmp_path


def _wr(fp: str) -> dict:
    return {"tool_name": "Write", "tool_input": {"file_path": fp}}


def _ed(fp: str) -> dict:
    return {"tool_name": "Edit", "tool_input": {"file_path": fp}}


def _bash(cmd: str) -> dict:
    return {"tool_name": "Bash", "tool_input": {"command": cmd}}


# ── Write / Edit (確定章) ────────────────────────────────────────────────────
def test_write_confirmed_chapter_blocked(tmp_path):
    root = _make_project(tmp_path)
    code, _ = g.decide(_wr(str(root / "system-spec" / "database.md")), root)
    assert code == 2


def test_edit_confirmed_chapter_blocked(tmp_path):
    root = _make_project(tmp_path)
    code, _ = g.decide(_ed(str(root / "system-spec" / "database.md")), root)
    assert code == 2


def test_write_security_mixed_confirmed_chapter_blocked(tmp_path):
    """web/mobile/tablet 確定 + desktop×3 対象外 の混在でも status:confirmed → 全セル終端で保護。"""
    root = _make_project(tmp_path, security_mixed=True)
    code, _ = g.decide(_wr(str(root / "system-spec" / "security.md")), root)
    assert code == 2


def test_write_normal_file_passes(tmp_path):
    root = _make_project(tmp_path)
    code, _ = g.decide(_wr(str(root / "notes.txt")), root)
    assert code == 0


def test_write_non_md_under_system_spec_passes(tmp_path):
    root = _make_project(tmp_path)
    code, _ = g.decide(_wr(str(root / "system-spec" / "assets.json")), root)
    assert code == 0


def test_write_reopened_state_chapter_passes(tmp_path):
    """auth/mobile が writer 実出力 (未収集+reopened_from) の章は非終端セルを含み保護しない。"""
    root = _make_project(tmp_path, reopen="state")
    code, _ = g.decide(_wr(str(root / "system-spec" / "auth.md")), root)
    assert code == 0


def test_write_reopened_flag_chapter_passes(tmp_path):
    """state は確定でも reopen 正本キー (reopened_from/reopen_reason) 付きなら保護しない。"""
    root = _make_project(tmp_path, reopen="flag")
    code, _ = g.decide(_wr(str(root / "system-spec" / "auth.md")), root)
    assert code == 0


def test_write_draft_chapter_passes(tmp_path):
    root = _make_project(tmp_path)
    code, _ = g.decide(_wr(str(root / "system-spec" / "ui-ux.md")), root)
    assert code == 0


def test_write_new_chapter_passes(tmp_path):
    root = _make_project(tmp_path)
    code, _ = g.decide(_wr(str(root / "system-spec" / "brand-new.md")), root)
    assert code == 0


def test_write_missing_file_path_passes(tmp_path):
    root = _make_project(tmp_path)
    code, _ = g.decide({"tool_name": "Write", "tool_input": {}}, root)
    assert code == 0


def test_confirmed_chapter_blocked_when_spec_state_unresolved(tmp_path):
    """F3 層別 fail-closed: status:confirmed 章 かつ 正本 spec-state 解決不能 → confirmed 章限定で exit2。

    正本 system-spec/spec-state.json が不在で確定状態を確認できないため、confirmed を宣言する章に
    限って安全側へ倒す (誤爆範囲は confirmed 章のみ)。
    """
    ss = tmp_path / "system-spec"
    ss.mkdir()
    (ss / "database.md").write_text(_chapter("confirmed", "database"), encoding="utf-8")
    code, _ = g.decide(_wr(str(ss / "database.md")), tmp_path)
    assert code == 2


def test_draft_chapter_passes_when_spec_state_unresolved(tmp_path):
    """draft 章は spec-state 不在でも fail-closed の対象外 (誤爆回避優先で通す)。"""
    ss = tmp_path / "system-spec"
    ss.mkdir()
    (ss / "ui-ux.md").write_text(_chapter("draft", "ui-ux", aggregate="収集中"), encoding="utf-8")
    code, _ = g.decide(_wr(str(ss / "ui-ux.md")), tmp_path)
    assert code == 0


# ── Write / Edit (正本 spec-state.json 直接書換ガード・D-2/F3) ────────────────
def test_write_spec_state_direct_blocked(tmp_path):
    """確定セルを含む正本 spec-state.json への直接 Write を Bash 経路と同格に遮断。"""
    root = _make_project(tmp_path)
    code, _ = g.decide(_wr(str(root / "system-spec" / "spec-state.json")), root)
    assert code == 2


def test_edit_spec_state_direct_blocked(tmp_path):
    root = _make_project(tmp_path)
    code, _ = g.decide(_ed(str(root / "system-spec" / "spec-state.json")), root)
    assert code == 2


def test_edit_noncanonical_spec_state_passes_despite_canonical_confirmed(tmp_path):
    """別位置の同名 spec-state.json (同梱 fixture 等) の Edit は、正本に確定セルがあっても遮断しない。

    load_spec_state が rglob フォールバックを持たず正本のみを読むため、別の確定 spec-state を
    判定ソースに拾う交差汚染が起きない (F2(b)(c))。
    """
    root = _make_project(tmp_path)  # 正本 system-spec/spec-state.json は確定セルあり
    fixtures = tmp_path / "skills" / "run-system-spec-compile" / "fixtures"
    fixtures.mkdir(parents=True)
    (fixtures / "spec-state.json").write_text(json.dumps(_spec_state(), ensure_ascii=False), encoding="utf-8")
    code, _ = g.decide(_ed(str(fixtures / "spec-state.json")), root)
    assert code == 0


def test_write_spec_state_no_confirmed_cell_passes(tmp_path):
    """確定セルの無い (init 直後・全未収集) 正本 spec-state.json への Write は通す (初期化を妨げない)。"""
    spec = {
        "categories": [{"id": c, "label": c} for c in CATEGORIES],
        "platforms": PLATFORMS,
        "matrix": {c: {p: {"state": "未収集"} for p in PLATFORMS} for c in CATEGORIES},
        "qa_log": [],
    }
    ss = tmp_path / "system-spec"
    ss.mkdir()
    (ss / "spec-state.json").write_text(json.dumps(spec, ensure_ascii=False), encoding="utf-8")
    code, _ = g.decide(_wr(str(ss / "spec-state.json")), tmp_path)
    assert code == 0


# ── Bash ────────────────────────────────────────────────────────────────────
def test_bash_sed_inplace_spec_state_blocked(tmp_path):
    root = _make_project(tmp_path)
    code, _ = g.decide(_bash("sed -i 's/確定/未収集/' system-spec/spec-state.json"), root)
    assert code == 2


def test_bash_redirect_append_spec_state_blocked(tmp_path):
    root = _make_project(tmp_path)
    code, _ = g.decide(_bash('echo "{}" >> system-spec/spec-state.json'), root)
    assert code == 2


def test_bash_redirect_overwrite_spec_state_blocked(tmp_path):
    root = _make_project(tmp_path)
    code, _ = g.decide(_bash("echo x > system-spec/spec-state.json"), root)
    assert code == 2


def test_bash_tee_spec_state_blocked(tmp_path):
    root = _make_project(tmp_path)
    code, _ = g.decide(_bash("echo x | tee system-spec/spec-state.json"), root)
    assert code == 2


def test_bash_python_open_write_spec_state_blocked(tmp_path):
    root = _make_project(tmp_path)
    code, _ = g.decide(_bash("python3 -c \"open('system-spec/spec-state.json','w').write('{}')\""), root)
    assert code == 2


def test_bash_bare_spec_state_not_canonical_passes(tmp_path):
    """root 直下 (非正本) の bare spec-state.json への書換は正本でないため遮断しない。

    正本位置は system-spec/spec-state.json の 1 経路のみ (spec-state-contract.md「正本位置」節)。
    """
    root = _make_project(tmp_path)
    code, _ = g.decide(_bash("echo x > spec-state.json"), root)
    assert code == 0


def test_bash_self_plugin_pycache_rm_passes(tmp_path):
    """自plugin パス (system-spec-harness) を含む rm は保護領域 (system-spec/) 参照でないため通す。

    部分文字列 'system-spec' ではなく system-spec/ のパスセグメント境界で判定するため
    system-spec-harness/** の __pycache__ 掃除等を誤遮断しない (F2(a))。
    """
    root = _make_project(tmp_path)
    code, _ = g.decide(_bash("rm -rf plugins/system-spec-harness/**/__pycache__"), root)
    assert code == 0


def test_bash_self_plugin_md_sed_passes(tmp_path):
    """自plugin 内 .md への sed -i は system-spec/ 保護領域外なので通す (パス境界判定)。"""
    root = _make_project(tmp_path)
    code, _ = g.decide(_bash("sed -i 's/a/b/' plugins/system-spec-harness/README.md"), root)
    assert code == 0


def test_bash_redirect_confirmed_chapter_blocked(tmp_path):
    root = _make_project(tmp_path)
    code, _ = g.decide(_bash("echo x > system-spec/database.md"), root)
    assert code == 2


def test_bash_ambiguous_glob_over_system_spec_blocked(tmp_path):
    root = _make_project(tmp_path)
    code, _ = g.decide(_bash("find system-spec -name '*.md' | xargs sed -i 's/a/b/'"), root)
    assert code == 2


def test_bash_cat_spec_state_passes(tmp_path):
    root = _make_project(tmp_path)
    code, _ = g.decide(_bash("cat system-spec/spec-state.json"), root)
    assert code == 0


def test_bash_grep_chapter_passes(tmp_path):
    root = _make_project(tmp_path)
    code, _ = g.decide(_bash("grep status system-spec/database.md"), root)
    assert code == 0


def test_bash_read_spec_state_write_elsewhere_passes(tmp_path):
    """正本 spec-state を読み、非保護先へリダイレクトするのは通す (リダイレクト先で判定)。"""
    root = _make_project(tmp_path)
    code, _ = g.decide(_bash("grep 確定 system-spec/spec-state.json > /tmp/out.txt"), root)
    assert code == 0


def test_bash_stderr_redirect_read_only_passes(tmp_path):
    """2>&1 は fd 複製で書込指標にならない (cat の read-only を維持)。"""
    root = _make_project(tmp_path)
    code, _ = g.decide(_bash("cat system-spec/spec-state.json 2>&1"), root)
    assert code == 0


def test_bash_redirect_reopened_chapter_passes(tmp_path):
    root = _make_project(tmp_path, reopen="state")
    code, _ = g.decide(_bash("echo x > system-spec/auth.md"), root)
    assert code == 0


def test_bash_new_chapter_redirect_passes(tmp_path):
    root = _make_project(tmp_path)
    code, _ = g.decide(_bash("echo x > system-spec/brand-new.md"), root)
    assert code == 0


def test_bash_write_unrelated_file_passes(tmp_path):
    root = _make_project(tmp_path)
    code, _ = g.decide(_bash("echo hello > README.md"), root)
    assert code == 0


def test_bash_ls_passes(tmp_path):
    root = _make_project(tmp_path)
    code, _ = g.decide(_bash("ls -la system-spec/"), root)
    assert code == 0


# ── その他ツール ────────────────────────────────────────────────────────────
def test_unrelated_tool_passes(tmp_path):
    root = _make_project(tmp_path)
    code, _ = g.decide({"tool_name": "Read", "tool_input": {"file_path": str(root / "system-spec" / "database.md")}}, root)
    assert code == 0


# ── ヘルパ単体 ──────────────────────────────────────────────────────────────
def test_parse_frontmatter_no_fm():
    assert g.parse_frontmatter("no frontmatter here") == {}


def test_parse_frontmatter_incomplete():
    assert g.parse_frontmatter("---\nstatus: confirmed\n") == {}


def test_parse_frontmatter_c03_shape():
    """C03 実出力 frontmatter がスカラ辞書へ落ちること (spec_cells は list 文字列)。"""
    fm = g.parse_frontmatter(_chapter("confirmed", "database"))
    assert fm["status"] == "confirmed"
    assert fm["category"] == "database"
    assert fm["spec_cells"].startswith("[database.web")


def test_parse_spec_cells_variants():
    assert g._parse_spec_cells("[database.web, database.mobile]") == [("database", "web"), ("database", "mobile")]
    assert g._parse_spec_cells(["auth.web", "auth.tablet"]) == [("auth", "web"), ("auth", "tablet")]
    # ハイフンを含む category/platform も '.' 分割で一意
    assert g._parse_spec_cells("[maintenance-ops.desktop-macos, ui-ux.desktop-linux]") == [
        ("maintenance-ops", "desktop-macos"),
        ("ui-ux", "desktop-linux"),
    ]
    assert g._parse_spec_cells("") == []
    assert g._parse_spec_cells(None) == []
    assert g._parse_spec_cells("[]") == []


def test_extract_cell_refs_variants():
    # C03 実形状 (spec_cells list)
    assert g._extract_cell_refs({"spec_cells": "[database.web, database.mobile]", "category": "database"}) == [
        ("database", "web"),
        ("database", "mobile"),
    ]
    # 後方互換: 単一 cell 系キー
    assert g._extract_cell_refs({"cell": "database/web"}) == [("database", "web")]
    assert g._extract_cell_refs({"cell_id": "auth:mobile"}) == [("auth", "mobile")]
    # 後方互換: category + platform (単数)
    assert g._extract_cell_refs({"category": "ui-ux", "platform": "tablet"}) == [("ui-ux", "tablet")]
    # category のみ (platform 単数キー無し・C03) は単一キー経路では拾わない
    assert g._extract_cell_refs({"category": "database"}) == []
    assert g._extract_cell_refs({"status": "confirmed"}) == []


def test_cell_terminal_variants():
    assert g._cell_terminal({"state": "確定"}) is True
    assert g._cell_terminal({"state": "対象外"}) is True
    assert g._cell_terminal({"state": "未収集"}) is False
    # reopen 正本キー付きは終端でも保護しない
    assert g._cell_terminal({"state": "確定", "reopened_from": "確定"}) is False
    assert g._cell_terminal({"state": "確定", "reopen_reason": "x"}) is False
    # 後方互換 reopen キー
    assert g._cell_terminal({"state": "確定", "reopen": True}) is False
    assert g._cell_terminal("確定") is False


def test_cell_reopened_variants():
    assert g._cell_reopened({"reopened_from": "確定"}) is True
    assert g._cell_reopened({"reopen_reason": "x"}) is True
    assert g._cell_reopened({"reopened": True}) is True
    assert g._cell_reopened({"state": "確定"}) is False


def test_spec_state_has_confirmed_cell(tmp_path):
    root = _make_project(tmp_path)
    assert g.spec_state_has_confirmed_cell(root) is True


def test_spec_state_has_confirmed_cell_false_when_all_reopened(tmp_path):
    """全確定セルが reopen 済みなら確定セル無し扱い (通す)。"""
    spec = {
        "categories": [{"id": "database", "label": "database"}],
        "platforms": PLATFORMS,
        "matrix": {"database": {p: {"state": "確定", "reopened_from": "確定", "reopen_reason": "r"} for p in PLATFORMS}},
        "qa_log": [],
    }
    ss = tmp_path / "system-spec"
    ss.mkdir()
    (ss / "spec-state.json").write_text(json.dumps(spec, ensure_ascii=False), encoding="utf-8")
    assert g.spec_state_has_confirmed_cell(tmp_path) is False


def test_spec_state_has_confirmed_cell_absent(tmp_path):
    assert g.spec_state_has_confirmed_cell(tmp_path) is False


def test_load_spec_state_absent(tmp_path):
    assert g.load_spec_state(tmp_path) is None


def test_load_spec_state_bad_json(tmp_path):
    ss = tmp_path / "system-spec"
    ss.mkdir()
    (ss / "spec-state.json").write_text("{not json", encoding="utf-8")
    assert g.load_spec_state(tmp_path) is None


def test_load_spec_state_ignores_noncanonical(tmp_path):
    """正本 (system-spec/spec-state.json) が無ければ、配下の別 spec-state.json は読まない (rglob 廃止)。"""
    fixtures = tmp_path / "skills" / "fixtures"
    fixtures.mkdir(parents=True)
    (fixtures / "spec-state.json").write_text(json.dumps(_spec_state(), ensure_ascii=False), encoding="utf-8")
    assert g.load_spec_state(tmp_path) is None


def test_resolve_cell_missing_row():
    assert g._resolve_cell({"matrix": {}}, "database", "web") is None
    assert g._resolve_cell({}, "database", "web") is None


def test_is_canonical_spec_state(tmp_path):
    ss = tmp_path / "system-spec"
    ss.mkdir()
    (ss / "spec-state.json").write_text("{}", encoding="utf-8")
    # 正本 (root/system-spec/spec-state.json) のみ True
    assert g._is_canonical_spec_state(ss / "spec-state.json", tmp_path) is True
    # root 直下・別ディレクトリの同名は正本でない
    assert g._is_canonical_spec_state(tmp_path / "spec-state.json", tmp_path) is False
    assert g._is_canonical_spec_state(tmp_path / "other" / "spec-state.json", tmp_path) is False
    assert g._is_canonical_spec_state(ss / "database.md", tmp_path) is False


def test_token_is_canonical_spec_state():
    assert g._token_is_canonical_spec_state("system-spec/spec-state.json") is True
    assert g._token_is_canonical_spec_state("/abs/system-spec/spec-state.json") is True
    assert g._token_is_canonical_spec_state("spec-state.json") is False  # bare = 非正本
    assert g._token_is_canonical_spec_state("fixtures/spec-state.json") is False
    assert g._token_is_canonical_spec_state("system-spec/database.md") is False


def test_refs_protected_area_path_boundary():
    """system-spec/ をパスセグメント境界で判定し、system-spec-harness には発火しない。"""
    assert g._refs_protected_area("echo x > system-spec/a.md") is True
    assert g._refs_protected_area("find system-spec -name '*.md'") is True
    assert g._refs_protected_area("rm -rf plugins/system-spec-harness/**/__pycache__") is False
    assert g._refs_protected_area("sed -i s/a/b/ plugins/system-spec-harness/README.md") is False


def test_bash_sed_inplace_confirmed_chapter_blocked(tmp_path):
    """glob/変数を含まず具体的な確定章を sed -i する動的書換は case3 で遮断。"""
    root = _make_project(tmp_path)
    code, _ = g.decide(_bash("sed -i 's/a/b/' system-spec/database.md"), root)
    assert code == 2


def test_bash_sed_inplace_reopened_chapter_passes(tmp_path):
    root = _make_project(tmp_path, reopen="state")
    code, _ = g.decide(_bash("sed -i 's/a/b/' system-spec/auth.md"), root)
    assert code == 0


def test_system_spec_md_tokens():
    toks = g._system_spec_md_tokens("sed -i x system-spec/a.md other.txt system-spec/b.md")
    assert toks == ["system-spec/a.md", "system-spec/b.md"]


def test_project_root_prefers_env(tmp_path, monkeypatch):
    monkeypatch.setenv("CLAUDE_PROJECT_DIR", str(tmp_path))
    assert g.project_root() == tmp_path


def test_project_root_falls_back_to_cwd(monkeypatch):
    monkeypatch.delenv("CLAUDE_PROJECT_DIR", raising=False)
    assert g.project_root() == Path.cwd()


# ── main() end-to-end (stdin→exit) ─────────────────────────────────────────
def _run_main(payload: dict, cwd: Path) -> int:
    return subprocess.run(
        [sys.executable, str(HOOK)],
        input=json.dumps(payload),
        text=True,
        capture_output=True,
        cwd=str(cwd),
    ).returncode


def test_main_block_via_stdin(tmp_path):
    root = _make_project(tmp_path)
    assert _run_main(_wr(str(root / "system-spec" / "database.md")), root) == 2


def test_main_block_spec_state_via_stdin(tmp_path):
    root = _make_project(tmp_path)
    assert _run_main(_ed(str(root / "system-spec" / "spec-state.json")), root) == 2


def test_main_pass_via_stdin(tmp_path):
    root = _make_project(tmp_path)
    assert _run_main(_bash("cat system-spec/spec-state.json"), root) == 0


def test_main_bad_stdin_passes(tmp_path):
    root = _make_project(tmp_path)
    proc = subprocess.run(
        [sys.executable, str(HOOK)], input="{not json", text=True, capture_output=True, cwd=str(root)
    )
    assert proc.returncode == 0
