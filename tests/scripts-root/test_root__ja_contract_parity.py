"""日本語の正規形が、それを照合する各スクリプトと rubric で同じ値になっていることを固定する。

日本語の正規形は 2 つ目の正規形で、定数は照合する側のモジュールにそれぞれ置いてある
(正本を 1 か所に寄せると、配布物の plugin が repo ルートの scripts を import することになる)。
ここでは置き場所は変えず、値が食い違ったら落ちるようにする。
"""
from __future__ import annotations

import importlib.util
import json
import pathlib
import re

import pytest


ROOT = pathlib.Path(__file__).resolve().parents[2]
HC = ROOT / "plugins" / "harness-creator"


def _load(path: pathlib.Path, name: str):
    assert path.is_file(), f"missing: {path}"
    spec = importlib.util.spec_from_file_location(name, path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


@pytest.fixture(scope="module")
def delivery():
    return _load(ROOT / "scripts" / "build-artifact-delivery.py", "ja_parity_delivery")


@pytest.fixture(scope="module")
def entrypoint_lint():
    return _load(ROOT / "scripts" / "lint-entrypoint-artifact-first.py", "ja_parity_entrypoint")


@pytest.fixture(scope="module")
def parity_audit():
    return _load(HC / "scripts" / "audit-capability-parity.py", "ja_parity_audit")


@pytest.fixture(scope="module")
def agent_section_lint():
    return _load(
        ROOT / "plugins" / "skill-governance-lint" / "scripts" / "lint-agent-prompt-section.py",
        "ja_parity_agent_section",
    )


@pytest.fixture(scope="module")
def findings_score():
    return _load(
        HC / "skills" / "assign-skill-design-evaluator" / "scripts" / "render-findings-score.py",
        "ja_parity_findings_score",
    )


@pytest.fixture(scope="module")
def rubric_checks() -> dict[str, str]:
    rubric = json.loads(
        (HC / "skills" / "ref-skill-design-rubric" / "references" / "rubric.json").read_text(
            encoding="utf-8"
        )
    )
    checks: dict[str, str] = {}

    def walk(node):
        if isinstance(node, dict):
            if isinstance(node.get("id"), str) and isinstance(node.get("check"), str):
                checks[node["id"]] = node["check"]
            for value in node.values():
                walk(value)
        elif isinstance(node, list):
            for value in node:
                walk(value)

    walk(rubric)
    return checks


def test_post_choice_heading_is_shared_by_generator_and_lint(delivery, entrypoint_lint):
    assert delivery.POST_CHOICE_HEADING == entrypoint_lint.POST_CHOICE_HEADING
    assert delivery.POST_CHOICE_HEADING_JA == entrypoint_lint.POST_CHOICE_HEADING_JA
    assert delivery.POST_CHOICE_HEADINGS == {
        "en": entrypoint_lint.POST_CHOICE_HEADING,
        "ja": entrypoint_lint.POST_CHOICE_HEADING_JA,
    }


@pytest.mark.parametrize(
    ("section_attr", "heading_attr", "tokens_attr"),
    [
        ("RUNTIME_ROOT_CONTRACT_SECTION", "RUNTIME_ROOT_CONTRACT_HEADING", "RUNTIME_ROOT_CONTRACT_TOKENS"),
        (
            "RUNTIME_ROOT_CONTRACT_SECTION_JA",
            "RUNTIME_ROOT_CONTRACT_HEADING_JA",
            "RUNTIME_ROOT_CONTRACT_TOKENS_JA",
        ),
    ],
)
def test_runtime_root_section_satisfies_parity_tokens(
    delivery, parity_audit, section_attr, heading_attr, tokens_attr
):
    # 生成器が足す節を、parity 監査はトークンの全部入りで照合する。
    # 生成器の文を直して監査のトークンを直し忘れると、生成直後の SKILL.md が監査で落ちる。
    section = getattr(delivery, section_attr)
    tokens = getattr(parity_audit, tokens_attr)
    assert tokens[0] == getattr(delivery, heading_attr)
    missing = [token for token in tokens if token not in section]
    assert missing == []


def test_runtime_root_sections_cover_both_languages(delivery):
    assert delivery.RUNTIME_ROOT_CONTRACT_SECTIONS == {
        "en": delivery.RUNTIME_ROOT_CONTRACT_SECTION,
        "ja": delivery.RUNTIME_ROOT_CONTRACT_SECTION_JA,
    }
    assert set(delivery.EXTERNAL_GUARD_BLOCK_MARKERS) == set(delivery.POST_CHOICE_HEADINGS)


@pytest.mark.parametrize("language", ["en", "ja"])
def test_canonical_guard_block_is_excluded_by_ssot_lint(delivery, language):
    # ssot lint は `<!-- name:vN -->` 形の生成ブロックを重複の検出から外す。
    # 日本語のマーカーがこの形から外れると、6 スキルに同じ文があると誤検出される。
    ssot = _load(
        HC / "skills" / "run-build-skill" / "scripts" / "lint-ssot-duplication.py",
        f"ja_parity_ssot_{language}",
    )
    block = delivery._canonical_external_guard_block(language)
    begin, end = delivery.EXTERNAL_GUARD_BLOCK_MARKERS[language]
    assert block.startswith(begin)
    assert block.rstrip().endswith(end)
    assert ssot.GENERATED_BLOCK_RE.sub("", block).strip() == ""


def test_agent_prompt_headings_match_rubric_pr002(agent_section_lint, rubric_checks):
    english, japanese = agent_section_lint.REQUIRED_HEADINGS, agent_section_lint.REQUIRED_HEADINGS_JA
    assert len(english) == len(japanese)
    # PR-002 は自己採点の見出しを、英語と日本語のどちらでも認める。
    assert english[1] in rubric_checks["PR-002"]
    assert japanese[1] in rubric_checks["PR-002"]


@pytest.mark.parametrize(
    ("rule_ids", "english_attr", "japanese_attr"),
    [
        (("BD-001", "PD-002"), "PURPOSE_HEADING", "PURPOSE_HEADING_JA"),
        (("BD-002",), "GOTCHAS_HEADING", "GOTCHAS_HEADING_JA"),
    ],
)
def test_scorer_headings_match_rubric(findings_score, rubric_checks, rule_ids, english_attr, japanese_attr):
    english = getattr(findings_score, english_attr)
    japanese = getattr(findings_score, japanese_attr)
    for rule_id in rule_ids:
        assert japanese in rubric_checks[rule_id], rule_id
    # BD-001 の英語の見出しは、PD-002 の check には短い形 ('## Purpose') でしか出てこない。
    assert english in rubric_checks[rule_ids[0]]


def test_japanese_headings_are_level_two_lines(
    delivery, entrypoint_lint, agent_section_lint, findings_score
):
    headings = [
        entrypoint_lint.PRE_CHOICE_HEADING_JA,
        delivery.POST_CHOICE_HEADING_JA,
        delivery.RUNTIME_ROOT_CONTRACT_HEADING_JA,
        *agent_section_lint.REQUIRED_HEADINGS_JA,
        findings_score.PURPOSE_HEADING_JA,
        findings_score.GOTCHAS_HEADING_JA,
    ]
    for heading in headings:
        assert re.fullmatch(r"## [^\s#].*\S", heading), heading
    assert len(set(headings)) == len(headings)
