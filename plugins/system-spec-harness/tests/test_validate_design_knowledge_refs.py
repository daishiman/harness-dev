#!/usr/bin/env python3
"""validate-design-knowledge-refs (knowledge_ref 実在ゲート) の acceptance tests。

``validate-coverage-matrix.py`` は design_applications の形状しか見ないため、存在しない
知識カードや綴り違いのファイル名を参照したままでも緑になる。参照先の無い設計解釈は「deep card に基づいて判断した」という
主張の根拠を持たないので、path の実在と anchor 見出しの実在の両方を fail-closed に検査する。
"""
from __future__ import annotations

import importlib.util
import json
from pathlib import Path

import pytest

SCRIPT = Path(__file__).resolve().parents[1] / "scripts" / "validate-design-knowledge-refs.py"


def _load_mod():
    spec = importlib.util.spec_from_file_location("validate_design_knowledge_refs", SCRIPT)
    assert spec and spec.loader
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


mod = _load_mod()


@pytest.fixture()
def repo(tmp_path: Path) -> Path:
    card = tmp_path / "refs" / "clean-architecture.md"
    card.parent.mkdir(parents=True)
    card.write_text("# タイトル\n\n## 中核概念\n\n本文\n", encoding="utf-8")
    return tmp_path


def _state(*refs: str) -> dict:
    return {
        "qa_log": [
            {
                "id": "qa-001",
                "design_applications": [{"knowledge_ref": ref} for ref in refs],
            }
        ]
    }


def test_existing_path_and_anchor_pass(repo):
    findings = mod.collect_findings(_state("refs/clean-architecture.md#中核概念"), repo)
    assert findings == []


def test_missing_file_is_reported(repo):
    findings = mod.collect_findings(_state("refs/testing-strategy.md#中核概念"), repo)
    assert len(findings) == 1 and "参照先が実在しない" in findings[0]


def test_missing_anchor_is_reported(repo):
    # ファイルは実在するが見出しが無い場合。path 実在だけでは引用の接地を保証できない。
    findings = mod.collect_findings(_state("refs/clean-architecture.md#存在しない見出し"), repo)
    assert len(findings) == 1 and "見出しが参照先に存在しない" in findings[0]


def test_path_without_anchor_is_accepted(repo):
    assert mod.collect_findings(_state("refs/clean-architecture.md"), repo) == []


@pytest.mark.parametrize("ref", ["/etc/passwd#x", "../outside.md#x", "  "])
def test_unsafe_or_empty_path_is_rejected(repo, ref):
    findings = mod.collect_findings(_state(ref), repo)
    assert len(findings) == 1


def test_non_string_ref_is_rejected(repo):
    state = {"qa_log": [{"id": "qa-001", "design_applications": [{"knowledge_ref": None}]}]}
    findings = mod.collect_findings(state, repo)
    assert len(findings) == 1 and "非空文字列必須" in findings[0]


def test_qa_without_design_applications_is_skipped(repo):
    assert mod.collect_findings({"qa_log": [{"id": "qa-001"}]}, repo) == []


def test_cli_returns_1_on_violation(repo, tmp_path, capsys):
    state_path = tmp_path / "spec-state.json"
    state_path.write_text(json.dumps(_state("refs/nope.md#中核概念"), ensure_ascii=False), encoding="utf-8")
    assert mod.main(["--matrix", str(state_path), "--repo-root", str(repo)]) == 1
    assert "VIOLATION" in capsys.readouterr().out


def test_cli_returns_0_when_clean(repo, tmp_path):
    state_path = tmp_path / "spec-state.json"
    state_path.write_text(
        json.dumps(_state("refs/clean-architecture.md#中核概念"), ensure_ascii=False), encoding="utf-8"
    )
    assert mod.main(["--matrix", str(state_path), "--repo-root", str(repo)]) == 0


def test_cli_returns_2_on_unreadable_state(tmp_path, repo):
    assert mod.main(["--matrix", str(tmp_path / "absent.json"), "--repo-root", str(repo)]) == 2


# 利用側 repo には plugin の写しが無い。harness repo の配置で書いた C04 card 参照は、
# validator 自身が属する plugin root で解決されなければ、install 先によらず必ず落ちる。
CARD_IN_HARNESS_LAYOUT = "plugins/system-spec-harness/skills/ref-system-design-knowledge/references/ddd.md"


def test_harness_layout_card_resolves_via_plugin_root_in_consumer_repo(tmp_path):
    assert not (tmp_path / "plugins").exists()
    assert mod.collect_findings(_state(f"{CARD_IN_HARNESS_LAYOUT}#中核概念"), tmp_path) == []


def test_plugin_root_fallback_still_checks_anchor(tmp_path):
    findings = mod.collect_findings(_state(f"{CARD_IN_HARNESS_LAYOUT}#存在しない見出し"), tmp_path)
    assert len(findings) == 1 and "見出しが参照先に存在しない" in findings[0]


def test_repo_root_copy_wins_over_plugin_root(tmp_path):
    # harness repo 自身では repo root の card を正とし、install 済み plugin に読み替えない。
    card = tmp_path / CARD_IN_HARNESS_LAYOUT
    card.parent.mkdir(parents=True)
    card.write_text("# repo 側の写し\n\n## repo だけの見出し\n", encoding="utf-8")
    assert mod.collect_findings(_state(f"{CARD_IN_HARNESS_LAYOUT}#repo だけの見出し"), tmp_path) == []
    findings = mod.collect_findings(_state(f"{CARD_IN_HARNESS_LAYOUT}#中核概念"), tmp_path)
    assert len(findings) == 1 and "見出しが参照先に存在しない" in findings[0]


def test_other_plugin_prefix_is_not_rewritten(tmp_path):
    ref = "plugins/other-plugin/skills/ref-system-design-knowledge/references/ddd.md#中核概念"
    findings = mod.collect_findings(_state(ref), tmp_path)
    assert len(findings) == 1 and "参照先が実在しない" in findings[0]
