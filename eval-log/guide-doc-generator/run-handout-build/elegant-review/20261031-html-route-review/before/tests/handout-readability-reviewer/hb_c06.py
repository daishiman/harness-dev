"""C06 handout-readability-reviewer (sub-agent) 受入テストの共通ハーネス。

このモジュール自体はテストを持たない (discover の pattern test_*.py に一致しない)。
契約の正本は 1 つだけであり、ここには「契約をどう観測するか」だけを置く:

  - plugin-plans/guide-doc-generator/briefs/agent-brief-C06.json

C06 は script ではなく **agent 定義 Markdown** なので、検査対象は実行結果ではなく
宣言的契約 (frontmatter / 必須セクション / 責務境界の明記 / findings スキーマの宣言) である。
期待値のうち機械可読な部分 (frontmatter フィールド一覧・body_sections・tools・
axis 語彙・description) はブリーフから実行時に読み出しており、テスト側へ複製していない。
ブリーフが変われば期待値も追随する。

実装が未着手のあいだ require_agent() は AssertionError を投げる。
これにより各テストは error ではなく failure (赤) として記録される。
"""

from __future__ import annotations

import importlib.util
import json
import re
import subprocess
import sys
import unittest
from pathlib import Path

TESTS_DIR = Path(__file__).resolve().parent
PLUGIN_ROOT = TESTS_DIR.parents[1]          # plugins/guide-doc-generator
REPO_ROOT = TESTS_DIR.parents[3]            # repo root

# agent-brief-C06.json#build_target
AGENT = PLUGIN_ROOT / "agents" / "handout-readability-reviewer.md"

BRIEF_PATH = (
    REPO_ROOT / "plugin-plans" / "guide-doc-generator" / "briefs" / "agent-brief-C06.json"
)
LINT_DIR = REPO_ROOT / "plugins" / "skill-governance-lint" / "scripts"

VALIDATE_FRONTMATTER = LINT_DIR / "validate-frontmatter.py"
LINT_AGENT_PROMPT_SECTION = LINT_DIR / "lint-agent-prompt-section.py"
LINT_SKILL_DESCRIPTION = LINT_DIR / "lint-skill-description.py"

# 決定論ゲートの component id (agent-brief-C06.json#boundary / question_solved)
MACHINE_GATES = ("C16", "C17", "C18", "C22")

# C06 が Bash で読み取り実行してよい検査 script (tools_rationale)
ALLOWED_BASH_SCRIPTS = (
    "verify-handout-language.py",
    "verify-handout-narrative.py",
    "verify-handout-selfcontained.py",
    "verify-handout-a11y-print.py",
)


# --------------------------------------------------------------------------
# ブリーフ (契約の正本) の読み出し
# --------------------------------------------------------------------------
def load_brief() -> dict:
    if not BRIEF_PATH.exists():
        raise AssertionError(
            "契約の正本 {} が存在しない。C06 のテストは正本なしには成立しない".format(
                BRIEF_PATH
            )
        )
    return json.loads(BRIEF_PATH.read_text(encoding="utf-8"))


BRIEF = load_brief()


def brief_axes() -> tuple[str, ...]:
    """output_contract.returns の宣言から axis 語彙を取り出す (テスト側へ複製しない)。"""
    m = re.search(r'\\"axis\\": \\"([^\\"]+)\\"', BRIEF["output_contract"]["returns"])
    if m is None:
        m = re.search(r'"axis": "([^"]+)"', BRIEF["output_contract"]["returns"])
    if m is None:
        raise AssertionError("brief#output_contract.returns から axis 語彙を取り出せない")
    return tuple(m.group(1).split("|"))


def brief_severities() -> tuple[str, ...]:
    m = re.search(
        r'\\"severity\\": \\"([^\\"]+)\\"', BRIEF["output_contract"]["returns"]
    )
    if m is None:
        m = re.search(r'"severity": "([^"]+)"', BRIEF["output_contract"]["returns"])
    if m is None:
        raise AssertionError("brief#output_contract.returns から severity 語彙を取り出せない")
    return tuple(m.group(1).split("|"))


# --------------------------------------------------------------------------
# 実装の有無 (赤の起点)
# --------------------------------------------------------------------------
def require_agent() -> str:
    """実装が存在しなければ赤で落とす。存在すれば本文を返す。"""
    if not AGENT.exists():
        raise AssertionError(
            "未実装: {} が存在しない。P05 でこの build_target を実装すること "
            "(agent-brief-C06.json#build_target)".format(AGENT)
        )
    return AGENT.read_text(encoding="utf-8")


# --------------------------------------------------------------------------
# Markdown の観測
# --------------------------------------------------------------------------
def split_frontmatter(text: str) -> tuple[str, str]:
    """(frontmatter 生文字列, body) を返す。frontmatter が無ければ AssertionError。"""
    if not text.startswith("---"):
        raise AssertionError(
            "{} が frontmatter (--- 開始) を持たない".format(AGENT)
        )
    parts = text.split("---", 2)
    if len(parts) < 3:
        raise AssertionError("{} の frontmatter が閉じていない".format(AGENT))
    return parts[1], parts[2]


def frontmatter(text: str | None = None) -> dict[str, str]:
    """frontmatter を key -> 値 (生文字列) で返す。stdlib のみ (yaml を使わない)。"""
    raw, _ = split_frontmatter(text if text is not None else require_agent())
    fm: dict[str, str] = {}
    for line in raw.splitlines():
        if not line.strip() or line.lstrip().startswith("#"):
            continue
        if line.lstrip().startswith("-"):
            continue
        if ":" not in line:
            continue
        key, _, value = line.partition(":")
        fm[key.strip()] = value.strip().strip('"').strip("'")
    return fm


def body(text: str | None = None) -> str:
    _, b = split_frontmatter(text if text is not None else require_agent())
    return b


def section(heading: str, text: str | None = None) -> str | None:
    """'## Xxx' 見出し配下の本文を返す (lint-agent-prompt-section.py と同じ切り方)。"""
    src = body(text)
    pattern = re.compile(
        rf"^{re.escape(heading)}\s*\n(.*?)(?=^## |\Z)", re.MULTILINE | re.DOTALL
    )
    m = pattern.search(src)
    return m.group(1) if m else None


def tools_set(fm: dict[str, str]) -> set[str]:
    raw = fm.get("tools", "")
    return {t.strip() for t in raw.replace("[", "").replace("]", "").split(",") if t.strip()}


def normalize(s: str) -> str:
    """語の突合用: 空白・全角空白を落とす (Markdown の折り返しに耐えるため)。"""
    return re.sub(r"[\s　]+", "", s)


# --------------------------------------------------------------------------
# lint の実行
# --------------------------------------------------------------------------
def run_lint(script: Path, *args: str) -> subprocess.CompletedProcess:
    return subprocess.run(
        [sys.executable, str(script), *args],
        cwd=str(REPO_ROOT),
        capture_output=True,
        text=True,
    )


def description_issues(name: str, desc: str) -> list[str]:
    """lint-skill-description.py の check() を直接呼ぶ。

    同 script の main() は SKILL.md と .claude/agents/*.md しか走査しないため、
    plugins/*/agents/*.md を対象にするには関数を直接使うほかない。
    規則 (R1-R5) をテスト側へ複製せず、script 側を正解として使う。
    """
    if not LINT_SKILL_DESCRIPTION.exists():
        raise AssertionError("{} が存在しない".format(LINT_SKILL_DESCRIPTION))
    spec = importlib.util.spec_from_file_location(
        "hb_lint_skill_description", LINT_SKILL_DESCRIPTION
    )
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module.check(name, desc)


# --------------------------------------------------------------------------
# 断言ヘルパ
# --------------------------------------------------------------------------
class AgentContractTestCase(unittest.TestCase):
    """全テストの基底。setUp で実装の有無を見る (setUpClass では見ない)。

    setUpClass で例外を投げると unittest は error として記録し、
    「赤で固定した」ことにならない。setUp 内の AssertionError は failure になる。
    """

    maxDiff = None

    def setUp(self) -> None:
        self.text = require_agent()

    # -- 本文断言 ---------------------------------------------------------
    def assert_mentions(self, needle: str, msg: str, where: str | None = None) -> None:
        haystack = body(self.text) if where is None else (section(where, self.text) or "")
        if where is not None and not haystack:
            self.fail("セクション '{}' が存在しない ({})".format(where, msg))
        if normalize(needle) not in normalize(haystack):
            self.fail(
                "{}: 期待した記述 '{}' が {} に無い".format(
                    msg, needle, where or "本文"
                )
            )

    def assert_mentions_any(
        self, needles, msg: str, where: str | None = None
    ) -> None:
        haystack = body(self.text) if where is None else (section(where, self.text) or "")
        if where is not None and not haystack:
            self.fail("セクション '{}' が存在しない ({})".format(where, msg))
        norm = normalize(haystack)
        if not any(normalize(n) in norm for n in needles):
            self.fail(
                "{}: 次のいずれの記述も {} に無い: {}".format(
                    msg, where or "本文", list(needles)
                )
            )

    def assert_not_mentions(self, needle: str, msg: str) -> None:
        if normalize(needle) in normalize(body(self.text)):
            self.fail("{}: 本文に '{}' があってはならない".format(msg, needle))
