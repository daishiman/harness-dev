#!/usr/bin/env python3
# /// script
# name: lint-agent-prompt-section
# purpose: SubAgent files must declare Prompt Templates and Self-Evaluation sections.
# inputs:
#   - argv: agent .md path or --agents-dir <dir> or --plugins-root <dir>
# outputs:
#   - stdout: OK status
#   - stderr: violation findings
#   - exit: 0=ok / 1=violation (unreadable agent files included) / 2=usage error or unreadable/invalid --brief
# contexts: [C, E]
# network: false
# write-scope: none
# dependencies: []
# requires-python: ">=3.10"
# ///
"""Lint SubAgent markdown files for required sections.

Required sections (agent-template.md):
  - ## Prompt Templates   (日本語の正規形: ## プロンプトの型)
  - ## Self-Evaluation    (日本語の正規形: ## 自己採点)
見出しは英語も日本語も行全体の一致で照合し、code fence の中の行は見出しとして数えない。

Skip rule:
  If body contains the literal '(対話なし: 自動実行 agent)' then Prompt Templates
  section may omit a question example block (only the heading is required).

Tier 2 (responsibility coverage) is enabled by `--strict-coverage --brief <path>`.
It cross-checks brief.responsibilities[] ids with `<!-- responsibility: <id> -->`
anchors inside the Prompt Templates section. brief が読めない・JSON object でない・
responsibilities が無いか配列でないときは、Tier 2 を飛ばさず exit 2 で止める。
responsibilities が空、または kind が delegate のときだけ Tier 2 を適用外とし、OK 行にそう書く。

Usage:
  lint-agent-prompt-section.py path/to/agent.md
  lint-agent-prompt-section.py --agents-dir plugins/skill-intake/agents
  lint-agent-prompt-section.py --plugins-root plugins
  lint-agent-prompt-section.py --strict-coverage --brief eval-log/skill-brief.json path/to/agent.md

Exit 0 = ok (--help も 0), 1 = violation (読めない agent file も violation として報告),
2 = usage error (未知の option・対象なし) または --brief を読めない・形が違う.
"""
from __future__ import annotations
import json
import re
import sys
from pathlib import Path

REQUIRED_HEADINGS = ("## Prompt Templates", "## Self-Evaluation")
# 日本語の正規形 (2つ目の正規形)。REQUIRED_HEADINGS と同じ並びで対応し、
# 行頭 `## ` からの行全体の一致だけを受け入れる。
REQUIRED_HEADINGS_JA = ("## プロンプトの型", "## 自己採点")
DIMENSIONS = ("完全性", "一貫性", "深度", "検証可能性", "簡潔性")
AUTO_AGENT_MARKER = "(対話なし: 自動実行 agent)"
ANCHOR_RE = re.compile(r"<!--\s*responsibility:\s*(R[0-9]+)\s*-->")
PLACEHOLDER_RE = re.compile(r"(?:<[^>]+>|\bTODO\b)")
FENCE_RE = re.compile(r"^[ \t]*(```|~~~)")
USAGE = (
    "usage: lint-agent-prompt-section.py <agent.md> | "
    "--agents-dir <dir> | --plugins-root <dir> "
    "[--strict-coverage --brief <skill-brief.json>]\n"
)


class BriefError(ValueError):
    """--brief を読めない、または Tier 2 に使える形でない (exit 2)。"""


def _mask_fences(text: str) -> str:
    """code fence の中の行を同じ長さの空白にする (見出しの照合から外し、位置は保つ)。"""
    out: list[str] = []
    fence: str | None = None
    for line in text.splitlines(keepends=True):
        m = FENCE_RE.match(line)
        if fence is None and m:
            fence = m.group(1)
            out.append(line)
        elif fence is not None:
            if m and m.group(1) == fence:
                fence = None
                out.append(line)
            else:
                out.append("".join(c if c == "\n" else " " for c in line))
        else:
            out.append(line)
    return "".join(out)


def find_section(text: str, heading: str) -> str | None:
    """行全体が heading の見出しから次の `## ` 見出しまでの本文を返す (fence の中の見出しは数えない)。"""
    pattern = re.compile(
        rf"^{re.escape(heading)}[ \t]*(?:\n|\Z)(.*?)(?=^## |\Z)",
        re.MULTILINE | re.DOTALL,
    )
    m = pattern.search(_mask_fences(text))
    return text[m.start(1):m.end(1)] if m else None


def has_heading_line(text: str, heading: str) -> bool:
    return re.search(rf"^{re.escape(heading)}[ \t]*$", _mask_fences(text), re.MULTILINE) is not None


def find_required_section(text: str, index: int) -> tuple[str, str | None]:
    """REQUIRED_HEADINGS[index] の (ラベル, 本文) を返す。英語が無ければ日本語の見出しを使う。

    英語を先に見るので、英語のエージェントの報告は今までと変わらない。
    """
    heading = REQUIRED_HEADINGS[index]
    body = find_section(text, heading)
    if body is None:
        heading_ja = REQUIRED_HEADINGS_JA[index]
        body_ja = find_section(text, heading_ja)
        if body_ja is not None:
            return heading_ja.removeprefix("## "), body_ja
    return heading.removeprefix("## "), body


def extract_anchor_blocks(prompt_body: str) -> list[tuple[str, str]]:
    """Return list of (responsibility_id, body_under_anchor) tuples.

    Body extends from the anchor up to the next anchor or end of section.
    """
    blocks: list[tuple[str, str]] = []
    anchors = list(ANCHOR_RE.finditer(prompt_body))
    for i, m in enumerate(anchors):
        start = m.end()
        end = anchors[i + 1].start() if i + 1 < len(anchors) else len(prompt_body)
        blocks.append((m.group(1), prompt_body[start:end]))
    return blocks


def load_brief_responsibilities(brief_path: Path) -> tuple[list[dict], str | None]:
    """brief の (responsibilities, kind) を返す。読めない・形が違うときは BriefError。

    responsibilities が null なら空として扱う (Tier 2 適用外)。キーが無いときは、
    別の JSON を渡した取り違えを見逃さないよう形の誤りとする。
    """
    try:
        brief = json.loads(brief_path.read_text(encoding="utf-8"))
    except (OSError, UnicodeDecodeError, ValueError, RecursionError) as e:
        raise BriefError(f"brief read error: {brief_path}: {e}") from e
    if not isinstance(brief, dict):
        raise BriefError(f"brief must be a JSON object: {brief_path} is {type(brief).__name__}")
    if "responsibilities" not in brief:
        raise BriefError(f"brief has no 'responsibilities': {brief_path}")
    responsibilities = brief["responsibilities"] or []
    if not isinstance(responsibilities, list) or not all(isinstance(r, dict) for r in responsibilities):
        raise BriefError(f"brief 'responsibilities' must be an array of objects: {brief_path}")
    kind = brief.get("kind")
    if kind is not None and not isinstance(kind, str):
        raise BriefError(f"brief 'kind' must be a string: {brief_path}")
    return responsibilities, kind


def lint_file(
    path: Path,
    strict_coverage: bool = False,
    brief_path: Path | None = None,
) -> list[str]:
    """Tier 1 (と strict なら Tier 2) の違反を返す。brief の誤りは BriefError で投げる。"""
    findings: list[str] = []
    try:
        text = path.read_text(encoding="utf-8")
    except (OSError, UnicodeDecodeError) as e:
        return [f"{path}: read error: {e}"]

    locales = [
        {lang for lang, headings in (("en", REQUIRED_HEADINGS), ("ja", REQUIRED_HEADINGS_JA)) if has_heading_line(text, headings[index])}
        for index in range(2)
    ]
    if any(len(item) > 1 for item in locales) or (all(locales) and locales[0] != locales[1]):
        findings.append(f"{path}: agent canonical section headings are mixed/duplicated languages")

    # Tier 1: 形式検査 (英語も日本語も見出しは行全体の一致で受け入れる)
    # 日本語の見出しだけを使う file には、欠けた見出しも日本語の名前で報告する。
    japanese = set().union(*locales) == {"ja"}
    for index in range(2):
        if not locales[index]:
            missing = (REQUIRED_HEADINGS_JA if japanese else REQUIRED_HEADINGS)[index]
            findings.append(f"{path}: missing required heading '{missing}'")

    prompt_label, prompt_body = find_required_section(text, 0)
    if prompt_body is not None and AUTO_AGENT_MARKER not in prompt_body:
        has_quote = re.search(r"^>\s*", prompt_body, re.MULTILINE) is not None
        has_round = re.search(r"^### ", prompt_body, re.MULTILINE) is not None
        if not (has_quote or has_round):
            findings.append(
                f"{path}: {prompt_label} section needs either a '> ' quote "
                "or '### Round' subheading, or marker '(対話なし: 自動実行 agent)'"
            )

    eval_label, eval_body = find_required_section(text, 1)
    if eval_body is not None:
        if not any(d in eval_body for d in DIMENSIONS):
            findings.append(
                f"{path}: {eval_label} must reference at least one of "
                f"{'/'.join(DIMENSIONS)}"
            )

    # Tier 2: 責務 coverage 検査
    if strict_coverage and brief_path is not None and prompt_body is not None:
        findings.extend(_lint_responsibility_coverage(path, prompt_body, brief_path))

    return findings


def _lint_responsibility_coverage(
    path: Path,
    prompt_body: str,
    brief_path: Path,
) -> list[str]:
    """Tier 2: brief.responsibilities[] と SubAgent.md anchor 集合を照合する。

    照合ポリシーの設計判断:
      (a) 完全集合一致: brief.responsibilities[].id == anchor 集合 (missing/extra 両方 violation)
      (b) カウント比較: anchor 数 >= responsibilities 数 (順序問わない)
      (c) 順序一致: brief 配列順と anchor 出現順が一致

    (a) を採用する。brief の誤りは BriefError で投げる (Tier 2 を黙って飛ばさない)。
    """
    findings: list[str] = []
    responsibilities, kind = load_brief_responsibilities(brief_path)
    # 責務が無い brief と kind=delegate (agent-template.md kind 表) は Tier 2 適用外
    if not responsibilities or kind == "delegate":
        return findings

    brief_ids = [r.get("id") for r in responsibilities if r.get("id")]
    anchor_blocks = extract_anchor_blocks(prompt_body)
    anchor_ids = [aid for aid, _ in anchor_blocks]
    body_by_id = {aid: body for aid, body in anchor_blocks}
    required_by_id = {
        r["id"]: bool(r.get("prompt_required"))
        for r in responsibilities
        if r.get("id")
    }

    # 照合ポリシー (a): 完全集合一致
    brief_set = set(brief_ids)
    anchor_set = set(anchor_ids)
    missing = brief_set - anchor_set
    extra = anchor_set - brief_set
    if missing:
        findings.append(
            f"{path}: missing responsibility anchors: {sorted(missing)} "
            "(expected `<!-- responsibility: <id> -->` for each brief.responsibilities[].id)"
        )
    if extra:
        findings.append(
            f"{path}: extra responsibility anchors not in brief: {sorted(extra)}"
        )

    # 本文検査: prompt_required=true の責務のみ placeholder/空を violation 扱い
    for rid, body in body_by_id.items():
        if rid not in required_by_id:
            continue
        if not required_by_id[rid]:
            continue  # prompt_required=false は anchor 行のみで可
        stripped = body.strip()
        if not stripped:
            findings.append(
                f"{path}: anchor body for {rid} is empty "
                "(prompt_required=true requires Round heading + '>' quote)"
            )
            continue
        # placeholder 検出: 実発話を担う `>` quote 行が存在し、かつその中身が
        # placeholder/TODO のみでないことを要求 (agent-template 規約)
        quote_lines = re.findall(r"^>\s*(.*?)\s*$", body, re.MULTILINE)
        if not quote_lines:
            findings.append(
                f"{path}: anchor body for {rid} has no '>' quote line "
                "(prompt_required=true requires concrete prompt text)"
            )
            continue
        # placeholder marker (`<...>` or TODO) を含む quote 行は非実体扱い。
        # agent-template の `> 「<実発話例>」` 雛形が未充填のまま残るケースを検出。
        substantive = [
            ln for ln in quote_lines
            if ln.strip() and not PLACEHOLDER_RE.search(ln)
        ]
        if not substantive:
            findings.append(
                f"{path}: anchor body for {rid} contains only placeholders/TODO "
                "in '>' quote lines (prompt_required=true requires concrete prompt text)"
            )

    return findings


def parse_args(argv: list[str]) -> tuple[list[Path], bool, Path | None, int | None]:
    """Returns (targets, strict_coverage, brief_path, error_code).

    error_code is None on success, else the exit code to return (--help は 0)。
    """
    strict_coverage = False
    brief_path: Path | None = None
    positional: list[str] = []
    i = 0
    while i < len(argv):
        a = argv[i]
        if a in ("-h", "--help"):
            sys.stdout.write(USAGE)
            return [], False, None, 0
        if a == "--strict-coverage":
            strict_coverage = True
            i += 1
        elif a == "--brief":
            if i + 1 >= len(argv):
                sys.stderr.write("--brief requires a path argument\n")
                return [], False, None, 2
            brief_path = Path(argv[i + 1])
            i += 2
        elif a.startswith("-") and not (not positional and a in ("--agents-dir", "--plugins-root")):
            sys.stderr.write(f"unknown option: {a}\n" + USAGE)
            return [], False, None, 2
        else:
            positional.append(a)
            i += 1

    if strict_coverage and brief_path is None:
        sys.stderr.write("--strict-coverage requires --brief <path>\n")
        return [], False, None, 2

    targets = collect_targets(positional)
    return targets, strict_coverage, brief_path, None


def collect_targets(argv: list[str]) -> list[Path]:
    if not argv:
        return []
    if argv[0] == "--agents-dir":
        if len(argv) < 2:
            return []
        d = Path(argv[1])
        return sorted(d.glob("*.md")) if d.is_dir() else []
    if argv[0] == "--plugins-root":
        if len(argv) < 2:
            return []
        root = Path(argv[1])
        if not root.is_dir():
            return []
        return sorted(root.glob("*/agents/*.md"))
    return [Path(p) for p in argv]


def main(argv: list[str]) -> int:
    targets, strict_coverage, brief_path, err = parse_args(argv)
    if err is not None:
        return err
    if not targets:
        sys.stderr.write(USAGE)
        return 2

    tier = "Tier 1"
    if strict_coverage and brief_path is not None:
        # 対象 file に関係なく、brief の誤りを最初に exit 2 で止める。
        try:
            responsibilities, kind = load_brief_responsibilities(brief_path)
        except BriefError as e:
            sys.stderr.write(f"{e}\n")
            return 2
        if kind == "delegate":
            tier = "Tier 1; Tier 2 not applicable: brief kind is delegate"
        elif not responsibilities:
            tier = "Tier 1; Tier 2 not applicable: brief has no responsibilities"
        else:
            tier = "Tier 1+2"

    all_findings: list[str] = []
    try:
        for path in targets:
            all_findings.extend(
                lint_file(path, strict_coverage=strict_coverage, brief_path=brief_path)
            )
    except BriefError as e:  # 検査中に brief が変わったときも黙って飛ばさない
        sys.stderr.write(f"{e}\n")
        return 2

    if all_findings:
        for f in all_findings:
            sys.stderr.write(f + "\n")
        return 1

    sys.stdout.write(f"OK: {len(targets)} agent file(s) passed ({tier})\n")
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
