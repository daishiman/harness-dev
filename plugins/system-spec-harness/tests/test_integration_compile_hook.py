# /// script
# name: test-integration-compile-hook
# version: 0.1.0
# purpose: C03 producer (compile-spec-doc.py render_frontmatter / fixtures/expected-*.md) の実出力章を C11 consumer (guard-confirmed-chapter-overwrite.decide) に食わせる結合テスト。producer が出す実 frontmatter (category + spec_cells list) を consumer が確定章として認識し確定章 Write→exit2・対象外混在確定章 Write→exit2・reopen 状態章→exit0・spec-state.json 直接 Edit→exit2 を検証する。producer/consumer 契約断裂 (F1) を赤で露見し修正後に緑化する回帰ガード。
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
"""C03 実出力章 (producer) × C11 hook (consumer) の結合テスト。

C11 hook を単独の架空 frontmatter で検証すると producer/consumer 契約断裂 (F1) が
false-green で隠れる。本テストは compile-spec-doc の実 render 出力および committed な
fixtures/expected-*.md を hook.decide() へ直接食わせ、章 frontmatter (category + spec_cells
list) が確定章として正しく認識され Write/Edit が exit2 で遮断されることを検証する。
"""
from __future__ import annotations

import importlib.util
import json
from pathlib import Path

_TESTS = Path(__file__).resolve().parent
_PLUGIN = _TESTS.parent
HOOK = _PLUGIN / "hooks" / "guard-confirmed-chapter-overwrite.py"
COMPILE = _PLUGIN / "skills" / "run-system-spec-compile" / "scripts" / "compile-spec-doc.py"
FIXTURES = _PLUGIN / "skills" / "run-system-spec-compile" / "fixtures"

PLATFORMS = ["web", "mobile", "tablet", "desktop-windows", "desktop-linux", "desktop-macos"]
DESKTOPS = ["desktop-windows", "desktop-linux", "desktop-macos"]


def _load(path: Path, name: str):
    spec = importlib.util.spec_from_file_location(name, path)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


g = _load(HOOK, "guard_hook")
c = _load(COMPILE, "compile_spec_doc")


def _wr(fp: str) -> dict:
    return {"tool_name": "Write", "tool_input": {"file_path": fp}}


def _ed(fp: str) -> dict:
    return {"tool_name": "Edit", "tool_input": {"file_path": fp}}


def _build_spec(*, reopen_cell: tuple[str, str] | None = None) -> dict:
    """database=全確定 / security=web/mobile/tablet 確定 + desktop×3 対象外 の spec-state。

    reopen_cell=(cat, pf) 指定でそのセルを writer 実出力 (未収集+reopened_from) へ再オープンする。
    """
    matrix: dict = {
        "database": {p: {"state": "確定", "qa_ref": "qa-database"} for p in PLATFORMS},
        "security": {p: {"state": "確定", "qa_ref": "qa-security"} for p in ["web", "mobile", "tablet"]},
    }
    for p in DESKTOPS:
        matrix["security"][p] = {"state": "対象外", "reason": "デスクトップ配信対象外"}
    if reopen_cell is not None:
        cat, pf = reopen_cell
        matrix[cat][pf] = {"state": "未収集", "reopened_from": "確定", "reopen_reason": "R4-reopen"}
    return {
        "categories": [{"id": "database", "label": "データベース"}, {"id": "security", "label": "セキュリティ"}],
        "platforms": PLATFORMS,
        "matrix": matrix,
        "qa_log": [{"id": "qa-database", "question": "q", "answer": "a"}, {"id": "qa-security", "question": "q", "answer": "a"}],
        "approval_log": [],
        "category_aggregate": {},
        "targets": [],
    }


def _materialize(tmp_path: Path, spec: dict, docset: dict[str, str]) -> Path:
    """正本 spec-state.json + compile 済み章群を tmp/system-spec/ へ配置し root を返す。

    正本位置は <root>/system-spec/spec-state.json の 1 経路のみ (spec-state-contract.md「正本位置」節)。
    """
    ss = tmp_path / "system-spec"
    ss.mkdir()
    (ss / "spec-state.json").write_text(json.dumps(spec, ensure_ascii=False), encoding="utf-8")
    for name, content in docset.items():
        (ss / name).write_text(content if content.endswith("\n") else content + "\n", encoding="utf-8")
    return tmp_path


# ── producer = compile-spec-doc 実 render → consumer = hook.decide ────────────
def test_compiled_confirmed_chapter_write_blocked(tmp_path):
    """全確定カテゴリを compile した実章への Write は確定章として exit2。"""
    spec = _build_spec()
    docset = c.compile_docset(spec, {"references": []})
    root = _materialize(tmp_path, spec, docset)
    # producer が出した frontmatter が実際に C03 形状 (category + spec_cells list) であること
    fm = g.parse_frontmatter(docset["database.md"])
    assert fm["status"] == "confirmed" and fm["category"] == "database"
    assert g._extract_cell_refs(fm) == [("database", p) for p in PLATFORMS]
    code, _ = g.decide(_wr(str(root / "system-spec" / "database.md")), root)
    assert code == 2


def test_compiled_mixed_confirmed_chapter_write_blocked(tmp_path):
    """確定+対象外 混在でも aggregate=確定 で status:confirmed → 全セル終端で保護 (exit2)。"""
    spec = _build_spec()
    docset = c.compile_docset(spec, {"references": []})
    root = _materialize(tmp_path, spec, docset)
    fm = g.parse_frontmatter(docset["security.md"])
    assert fm["status"] == "confirmed"
    code, _ = g.decide(_wr(str(root / "system-spec" / "security.md")), root)
    assert code == 2


def test_compiled_reopened_chapter_write_passes(tmp_path):
    """spec-state 側で database.web を再オープンすると (章 frontmatter は confirmed のままでも) 保護解除→exit0。"""
    spec = _build_spec(reopen_cell=("database", "web"))
    # 章は再オープン前の確定コンパイル済み frontmatter (status:confirmed) を残す (stale 章の露見)
    docset = c.compile_docset(_build_spec(), {"references": []})
    root = _materialize(tmp_path, spec, docset)
    code, _ = g.decide(_wr(str(root / "system-spec" / "database.md")), root)
    assert code == 0


def test_compiled_edit_spec_state_blocked(tmp_path):
    """確定セルを含む正本 spec-state.json への直接 Edit は exit2。"""
    spec = _build_spec()
    docset = c.compile_docset(spec, {"references": []})
    root = _materialize(tmp_path, spec, docset)
    code, _ = g.decide(_ed(str(root / "system-spec" / "spec-state.json")), root)
    assert code == 2


def test_compiled_draft_chapter_write_passes(tmp_path):
    """未収集を含む draft 章 (status:draft) は保護しない (exit0)。"""
    spec = _build_spec(reopen_cell=("database", "web"))
    # database.web=未収集 → aggregate=収集中 → status:draft で再コンパイル
    docset = c.compile_docset(spec, {"references": []})
    assert g.parse_frontmatter(docset["database.md"])["status"] == "draft"
    root = _materialize(tmp_path, spec, docset)
    code, _ = g.decide(_wr(str(root / "system-spec" / "database.md")), root)
    assert code == 0


# ── producer = committed fixtures/expected-*.md → consumer = hook.decide ──────
def _spec_matching_fixtures() -> dict:
    """committed fixtures (expected-database.md 全確定 / expected-security.md 混在) に整合する spec-state。"""
    return _build_spec()


def test_fixture_database_chapter_write_blocked(tmp_path):
    """committed expected-database.md (全確定) を配置した確定章への Write は exit2。"""
    spec = _spec_matching_fixtures()
    content = (FIXTURES / "expected-database.md").read_text(encoding="utf-8")
    root = _materialize(tmp_path, spec, {"database.md": content})
    # fixture が C03 形状であること (架空 cell: 単数キーでない)
    fm = g.parse_frontmatter(content)
    assert "spec_cells" in fm and "cell" not in fm
    code, _ = g.decide(_wr(str(root / "system-spec" / "database.md")), root)
    assert code == 2


def test_fixture_security_chapter_write_blocked(tmp_path):
    """committed expected-security.md (確定+対象外 混在) を配置した確定章への Write は exit2。"""
    spec = _spec_matching_fixtures()
    content = (FIXTURES / "expected-security.md").read_text(encoding="utf-8")
    root = _materialize(tmp_path, spec, {"security.md": content})
    code, _ = g.decide(_wr(str(root / "system-spec" / "security.md")), root)
    assert code == 2
