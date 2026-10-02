"""Semantic token completeness is shared by scaffold, renderer and book.

Only top-level :root declarations count. Class rules and conditional blocks (@media) in the bundled
standard colors are skipped, so a palette defined only inside @media leaves the roles missing.
"""
from __future__ import annotations

import json
import pytest
from conftest import TOKENS_CSS, node_eval


def validate(css: str) -> list[str]:
    return node_eval(
        'import { validateDesignTokens } from "./lib/design-tokens.mjs";\n'
        f'console.log(JSON.stringify(validateDesignTokens({json.dumps(css)})));'
    )


def test_standard_and_custom_primitive_names_are_complete() -> None:
    assert validate(TOKENS_CSS) == []
    assert validate(TOKENS_CSS.replace('--p-', '--company-').replace('#1747B5', '#123456')) == []


@pytest.mark.parametrize('css, marker', [
    ('', '--bg-board'),
    (':root { --text: #123456; }', '--bg-board'),
    (TOKENS_CSS.replace('--p-ink: #14233B;', '--p-ink: ;'), '--p-ink'),
    (TOKENS_CSS.replace('--p-ink: #14233B;', '--p-ink: var(--missing);'), '--missing'),
    (TOKENS_CSS.replace('--p-ink: #14233B;', '--p-ink: var(--loop); --loop: var(--p-ink);'), '循環'),
    (TOKENS_CSS.replace('--p-ink: #14233B;', '--p-ink: initial;'), '--p-ink'),
    (TOKENS_CSS.replace('--p-ink: #14233B;', '--p-ink: var(--missing;'), '閉じ'),
    ('@media print {' + TOKENS_CSS + '}', '--bg-board'),
    (TOKENS_CSS + '@import "other.css";', '宣言以外'),
], ids=['empty', 'partial', 'empty-value', 'undefined', 'cycle', 'initial', 'unclosed-var', 'conditional', 'import'])
def test_invalid_contracts(css: str, marker: str) -> None:
    assert any(marker in error for error in validate(css))


def test_nested_fallback_and_quoted_delimiters() -> None:
    custom = TOKENS_CSS.replace('--p-ink: #14233B;', '--p-ink: var(--absent, var(--also-absent, rgb(20, 35, 59)));')
    custom += ':root { --font-ui: "Font; with { punctuation } and var(--unused)"; }'
    assert validate(custom) == []


def test_empty_or_broken_fallback_does_not_hide_missing_value() -> None:
    assert validate(TOKENS_CSS.replace('--p-ink: #14233B;', '--p-ink: var(--absent,);'))
    assert validate(TOKENS_CSS.replace('--p-ink: #14233B;', '--p-ink: var(--absent, var(--also-absent));'))


@pytest.mark.parametrize("priority", ["!important", "! important", "!/**/important"])
def test_important_declaration_cannot_be_hidden_by_later_plain_value(priority: str) -> None:
    css = TOKENS_CSS + f':root {{ --text: var(--missing) {priority}; --text: #123456; }}'
    assert any('--missing' in error for error in validate(css))
    assert validate(css + ':root { --text: #123456 !important; }') == []


def test_cycles_in_unused_fallback_are_invalid_but_undefined_fallback_is_allowed() -> None:
    assert any('循環' in error for error in validate(TOKENS_CSS + ':root { --text: var(--p-ink, var(--text)); }'))
    assert validate(TOKENS_CSS + ':root { --text: var(--p-ink, var(--unused)); }') == []
