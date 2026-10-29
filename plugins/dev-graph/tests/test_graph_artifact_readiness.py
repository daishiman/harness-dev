"""lib/graph_artifact_readiness.py (C11 の本文 readiness 部品) の単体検証。"""
from __future__ import annotations

import sys
from pathlib import Path

sys.dont_write_bytecode = True

LIB = Path(__file__).resolve().parents[1] / "lib"
if str(LIB) not in sys.path:
    sys.path.insert(0, str(LIB))

from graph_artifact_readiness import missing_required_headings, placeholder_sections


def test_structural_parent_requires_a_substantive_child(tmp_path):
    template_root = tmp_path / "templates"
    template_root.mkdir()
    (template_root / "document.md").write_text(
        "# 本文\n\n## 詳細\n\n<canonical-detail>\n",
        encoding="utf-8",
    )
    contract = {
        "placeholder_tokens": ["<", "TBD", "TODO", "未定"],
        "artifacts": {
            "document": {
                "template": "document.md",
                "required_sections": ["本文"],
            }
        },
    }
    artifact = tmp_path / "document.md"

    artifact.write_text(
        "# 本文\n\n## 詳細\n\n<canonical-detail>\n",
        encoding="utf-8",
    )
    assert placeholder_sections(
        artifact, "document", contract, template_root
    ) == ["本文"]

    artifact.write_text(
        "# 本文\n\n## 詳細\n\n具体的な運用手順と検証結果を記録する。\n",
        encoding="utf-8",
    )
    assert placeholder_sections(artifact, "document", contract, template_root) == []


def test_missing_required_headings_catches_absent_heading_invisible_to_placeholder_check(
    tmp_path,
):
    """placeholder_sections only inspects headings that exist.

    A required section whose heading was never written (not even empty) never
    enters `sections`/`direct_invalid`, so placeholder_sections silently misses
    it. missing_required_headings must catch what placeholder_sections cannot.
    """
    contract = {
        "placeholder_tokens": ["<", "TBD", "TODO", "未定"],
        "artifacts": {
            "specification": {
                "template": "specification.md",
                "required_sections": ["目的と成功状態", "スコープ", "未決事項"],
            }
        },
    }
    template_root = tmp_path / "templates"
    template_root.mkdir()
    (template_root / "specification.md").write_text(
        "# 目的と成功状態\n\n<value>\n\n## スコープ\n\n- In: <x>\n\n## 未決事項\n\n<owner>\n",
        encoding="utf-8",
    )
    artifact = tmp_path / "spec.md"

    artifact.write_text("# 目的と成功状態\n\n利用者価値を書く。\n", encoding="utf-8")
    assert missing_required_headings(artifact, "specification", contract) == [
        "スコープ",
        "未決事項",
    ]
    # placeholder_sections cannot see the same gap: absent headings never
    # reach `sections`, so its required-section filter skips them entirely.
    assert placeholder_sections(artifact, "specification", contract, template_root) == []

    artifact.write_text(
        "# 目的と成功状態\n\n利用者価値を書く。\n\n## スコープ\n\nIn: x\n\n## 未決事項\n\nなし\n",
        encoding="utf-8",
    )
    assert missing_required_headings(artifact, "specification", contract) == []


def test_missing_required_headings_resolves_conditional_variants_by_node_trigger(tmp_path):
    """task の required_sections は conditional_required_sections に
    登録された複数 variant のいずれか一致で満たされる。trigger は
    source_lineage.origin_kind==system-dev-planner の node のみ発火し、manual origin
    (node なし/origin_kind 不一致) は base required_sections のまま検査される。"""
    contract = {
        "artifacts": {
            "task": {
                "required_sections": ["目的", "背景"],
                "conditional_required_sections": {
                    "system_development": ["フル見出しA", "フル見出しB"],
                    "system_development_baseline": ["正本仕様書", "依存", "実行契約"],
                },
            }
        }
    }
    artifact = tmp_path / "t.md"

    artifact.write_text("## 正本仕様書\n\nx\n\n## 依存\n\ny\n\n## 実行契約\n\nz\n", encoding="utf-8")
    system_dev_node = {"source_lineage": {"origin_kind": "system-dev-planner"}}
    assert missing_required_headings(artifact, "task", contract, system_dev_node) == []

    # base required_sections ("目的"/"背景") はここでは存在しないが、system-dev-planner
    # trigger を持つ node は軽量 variant の一致で満たされる。trigger の無い node は base だけで見る。
    manual_node = {"source_lineage": {"origin_kind": "manual"}}
    assert missing_required_headings(artifact, "task", contract, manual_node) == ["目的", "背景"]

    # node を渡さない呼び出し (specification など既存呼び出し互換) は base のまま。
    assert missing_required_headings(artifact, "task", contract) == ["目的", "背景"]


def test_conditional_triggers_match_on_source_path_not_origin_kind_alone(tmp_path):
    """同じ origin の章 import まで軽量契約へ巻き込まない。"""
    contract = {
        "artifacts": {
            "specification": {
                "required_sections": ["目的と成功状態", "スコープ", "未決事項"],
                "conditional_required_sections": {"system_spec_index": ["章一覧と集約状態"]},
                "conditional_triggers": [
                    {
                        "family": "system_spec_index",
                        "origin_kind": "system-spec-harness",
                        "source_path": "system-spec/index.md",
                    }
                ],
            }
        }
    }
    artifact = tmp_path / "index.md"
    artifact.write_text("# index\n\n## 章一覧と集約状態\n\n| a |\n", encoding="utf-8")

    index_node = {
        "source_lineage": {
            "origin_kind": "system-spec-harness",
            "source_path": "system-spec/index.md",
        }
    }
    assert missing_required_headings(artifact, "specification", contract, index_node) == []

    chapter_node = {
        "source_lineage": {
            "origin_kind": "system-spec-harness",
            "source_path": "system-spec/backend.md",
        }
    }
    assert missing_required_headings(artifact, "specification", contract, chapter_node) == [
        "スコープ",
        "未決事項",
        "目的と成功状態",
    ]


def test_conditional_trigger_without_conditions_never_fires(tmp_path):
    """空条件 rule が全 node に一致しないよう fail-closed にする。"""
    contract = {
        "artifacts": {
            "specification": {
                "required_sections": ["目的と成功状態"],
                "conditional_required_sections": {"loose": ["何か"]},
                "conditional_triggers": [{"family": "loose"}],
            }
        }
    }
    artifact = tmp_path / "s.md"
    artifact.write_text("# s\n\n## 何か\n\nx\n", encoding="utf-8")

    assert missing_required_headings(
        artifact, "specification", contract, {"source_lineage": {}}
    ) == ["目的と成功状態"]


def test_base_variant_remains_acceptable_when_a_conditional_family_fires(tmp_path):
    """full template 準拠 artifact も conditional trigger 発火時に受理する。"""
    contract = {
        "artifacts": {
            "architecture": {
                "required_sections": ["Architecture overview", "Risks and verification"],
                "conditional_required_sections": {
                    "system_spec_requirements": ["U1 本質的目的 (essential_purpose)"]
                },
                "conditional_triggers": [
                    {
                        "family": "system_spec_requirements",
                        "origin_kind": "system-spec-harness",
                        "source_path": "system-spec/00-requirements-definition.md",
                    }
                ],
            }
        }
    }
    artifact = tmp_path / "a.md"
    artifact.write_text(
        "# a\n\n## Architecture overview\n\nx\n\n## Risks and verification\n\ny\n",
        encoding="utf-8",
    )
    node = {
        "source_lineage": {
            "origin_kind": "system-spec-harness",
            "source_path": "system-spec/00-requirements-definition.md",
        }
    }
    assert missing_required_headings(artifact, "architecture", contract, node) == []
