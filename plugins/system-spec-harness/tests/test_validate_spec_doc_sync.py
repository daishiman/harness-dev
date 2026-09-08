# /// script
# name: test-validate-spec-doc-sync
# version: 0.1.0
# purpose: validate-spec-doc-sync.py (正本 spec-state.json と章 Markdown の同期ゲート) を正例=OK・負例=goal/根拠/出典の各未投影・入力不備で検証する pytest (in-process import で validate()/main() を直接呼ぶ)。
# inputs:
#   - argv: pytest 経由 (直接 argv は取らない)
# outputs:
#   - stdout: pytest 結果
#   - exit: 0=all pass / 1=failure
# contexts: [E, C]
# network: false
# write-scope: tmp_path のみ
# dependencies: []
# requires-python: ">=3.9"
# ///
"""正本と成果物の同期ゲート (validate-spec-doc-sync) の検証。

このゲートが塞ぐ穴は「全ゲート緑・ただし章は 1 世代前」である。
よってテストの主眼は正例が緑になることではなく、**章だけを古いままにした負例が
確実に赤になる**ことにある。3 投影 (goal / 根拠 / 出典) をそれぞれ独立に欠落させる。
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


sync = _load("vsds", "validate-spec-doc-sync.py")


def _spec() -> dict:
    return {
        "requirements_foundation": {"goals": [{"id": "G1", "text": "請求突合の手作業を無くす"}]},
        "matrix": {
            "database": {
                "web": {"state": "確定", "qa_ref": "qa-001", "serves_goals": ["G1"]},
                "mobile": {"state": "対象外", "approval_ref": "appr-001"},
            }
        },
    }


def _refs() -> dict:
    return {"references": [{"target_id": "postgresql"}]}


def _write_chapters(root: Path, *, goal: str = "G1", qa: str = "qa-001", target: str = "postgresql") -> Path:
    root.mkdir(parents=True, exist_ok=True)
    (root / "00-requirements-definition.md").write_text(
        f"# 要件定義書\n\n- {goal}: 請求突合の手作業を無くす\n", encoding="utf-8"
    )
    (root / "database.md").write_text(
        "---\n"
        "serves_goals: [G1]\n"
        "---\n\n"
        f"# データベース\n\n{goal} に資する。採用: {target} 15 (根拠: {qa})\n",
        encoding="utf-8",
    )
    return root


def test_synced_spec_and_chapters_pass(tmp_path):
    root = _write_chapters(tmp_path / "system-spec")
    assert sync.validate(_spec(), _refs(), root) == []


def test_goal_missing_from_requirements_chapter_fails(tmp_path):
    # 正本に goal を足したが要件定義書を再生成し忘れた状態。
    root = _write_chapters(tmp_path / "system-spec")
    spec = _spec()
    spec["requirements_foundation"]["goals"].append({"id": "G2", "text": "締め日前の残業を無くす"})
    violations = sync.validate(spec, _refs(), root)
    assert any("goal G2" in v and "00-requirements-definition.md" in v for v in violations)


def test_declared_serves_goal_absent_from_body_fails(tmp_path):
    # frontmatter だけ G1 を宣言し、本文が追従していない章。
    root = tmp_path / "system-spec"
    root.mkdir()
    (root / "00-requirements-definition.md").write_text("# 要件定義書\n\n- G1: 目的\n", encoding="utf-8")
    (root / "database.md").write_text(
        "---\nserves_goals: [G1]\n---\n\n# データベース\n\n採用: postgresql 15 (根拠: qa-001)\n",
        encoding="utf-8",
    )
    violations = sync.validate(_spec(), _refs(), root)
    assert any("本文に G1 の記述が無い" in v for v in violations)


def test_confirmed_cell_evidence_not_projected_fails(tmp_path):
    # 章が 1 世代前で、新しい確定セルの根拠 qa-002 をまだ含まない。
    root = _write_chapters(tmp_path / "system-spec")
    spec = _spec()
    spec["matrix"]["database"]["web"]["qa_refs"] = ["qa-002"]
    violations = sync.validate(spec, _refs(), root)
    assert any("qa-002" in v and "未投影" in v for v in violations)


def test_missing_category_chapter_fails(tmp_path):
    root = _write_chapters(tmp_path / "system-spec")
    spec = _spec()
    spec["matrix"]["auth"] = {"web": {"state": "確定", "qa_ref": "qa-002"}}
    assert any("カテゴリ auth の章が無い" in v for v in sync.validate(spec, _refs(), root))


def test_fetched_citation_not_projected_fails(tmp_path):
    root = _write_chapters(tmp_path / "system-spec")
    refs = {"references": [{"target_id": "postgresql"}, {"target_id": "fastapi"}]}
    assert any("出典 fastapi" in v for v in sync.validate(_spec(), refs, root))


def test_excluded_cell_needs_no_projection(tmp_path):
    # 対象外セルは章へ投影する根拠を持たない (approval_ref は qa_ref ではない)。
    root = _write_chapters(tmp_path / "system-spec")
    spec = _spec()
    spec["matrix"]["ui-ux"] = {"web": {"state": "対象外", "approval_ref": "appr-001"}}
    assert sync.validate(spec, _refs(), root) == []


def test_empty_or_missing_spec_root_raises(tmp_path):
    import pytest

    with pytest.raises(sync.SyncError):
        sync.chapter_texts(tmp_path / "absent")
    empty = tmp_path / "empty"
    empty.mkdir()
    with pytest.raises(sync.SyncError):
        sync.chapter_texts(empty)


def test_main_exit_codes(tmp_path, capsys):
    root = _write_chapters(tmp_path / "system-spec")
    matrix = tmp_path / "spec-state.json"
    matrix.write_text(json.dumps(_spec(), ensure_ascii=False), encoding="utf-8")
    references = tmp_path / "fetched-references.json"
    references.write_text(json.dumps(_refs(), ensure_ascii=False), encoding="utf-8")
    argv = ["--matrix", str(matrix), "--references", str(references), "--spec-root", str(root)]
    assert sync.main(argv) == 0

    # 章ディレクトリ不在は入力エラーとして非0で落ちる (緑にしない)。
    bad = argv[:-1] + [str(tmp_path / "absent")]
    assert sync.main(bad) == 1
