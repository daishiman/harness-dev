#!/usr/bin/env python3
# /// script
# name: lint-prompt-placement
# purpose: plugins/*/skills/*/prompts/* が prompt-placement-convention.md
#          に準拠していることを機械検証する。(a) ファイル名 regex の SSOT は
#          validate-build-trace.py の LAYER_YAML_PATH_PATTERNS から import、
#          (b) run/assign の prompts/<R-id>.md が空殻リダイレクトでない(7層本文を持つ=
#          PROMPT-REDIRECT-INVERSION 禁止)ことを検査する。
# inputs:
#   - argv: --self-test (任意) / なし=リポジトリ全走査
# outputs:
#   - stdout: ok message or violation list
#   - stderr: -
#   - exit: 0=PASS / 1=規約逸脱検出 / 2=usage error
# requires-python = ">=3.10"
# dependencies: []
# contexts: [A, B, C, E]
# network: false
# write-scope: none
# ///
"""Lint prompt placement under plugins/*/skills/*/prompts/.

正本: ../references/prompt-placement-convention.md
SSOT: validate-build-trace.py の LAYER_YAML_PATH_PATTERNS["skill-local-v1"]
"""
from __future__ import annotations

import re
import sys
from pathlib import Path

# SSOT 共有: validate-build-trace.py の正規表現を import (二重定義禁止)
_SCRIPT_DIR = Path(__file__).resolve().parent
if str(_SCRIPT_DIR) not in sys.path:
    sys.path.insert(0, str(_SCRIPT_DIR))

from validate_build_trace_shim import SKILL_LOCAL_V1_RE  # noqa: E402

# kind ∈ これらは prompts/<R-id>.md が 7 層本文必須 (prompt-placement-convention.md L14-20)。
# ref/wrap/delegate は既定 skip のため空殻/不在でも INVERSION 検査の対象外。
_PROMPT_REQUIRED_KINDS = ("run", "assign")
# 空殻リダイレクト判定: 実質本文行が これ未満なら 7 層本文を持たないとみなす。
_MIN_BODY_LINES = 12
_MOVED_TO_RE = re.compile(r"^\s*moved_to\s*:", re.MULTILINE)


def _repo_root() -> Path:
    # scripts/ -> run-build-skill/ -> skills/ -> harness-creator/ -> plugins/ -> repo
    return _SCRIPT_DIR.parent.parent.parent.parent.parent


def _skill_kind_of(rel: str) -> str | None:
    """plugins/<p>/skills/<kind>-<name>/prompts/<f> の <kind> を返す。"""
    m = re.search(r"/skills/(run|assign|ref|wrap|delegate)-[a-z0-9-]+/prompts/", rel)
    return m.group(1) if m else None


def _split_frontmatter(text: str) -> tuple[str, str]:
    if text.startswith("---\n"):
        end = text.find("\n---", 4)
        if end != -1:
            nl = text.find("\n", end + 1)
            return text[4:end], text[nl + 1:] if nl != -1 else ""
    return "", text


def _is_redirect_shell(text: str) -> bool:
    """moved_to リダイレクト宣言、または実質本文が極端に短い空殻なら True。"""
    fm, body = _split_frontmatter(text)
    if _MOVED_TO_RE.search(fm):
        return True
    if "リダイレクト" in body and "agents/" in body:
        return True
    substantial = sum(1 for ln in body.splitlines() if ln.strip() and ln.strip() != "---")
    return substantial < _MIN_BODY_LINES


def scan(repo_root: Path) -> list[str]:
    """規約逸脱 (PROMPT-FILENAME-FORMAT / PROMPT-REDIRECT-INVERSION) のメッセージ一覧を返す。"""
    violations: list[str] = []
    base = repo_root / "plugins"
    if not base.exists():
        return violations
    for path in sorted(base.glob("*/skills/*/prompts/*")):
        if not path.is_file():
            continue
        rel = path.relative_to(repo_root).as_posix()
        if not SKILL_LOCAL_V1_RE.match(rel):
            violations.append(f"PROMPT-FILENAME-FORMAT {rel} (skill-local-v1 regex 不適合)")
        kind = _skill_kind_of(rel)
        if kind in _PROMPT_REQUIRED_KINDS and path.suffix in (".md", ".yaml"):
            if _is_redirect_shell(path.read_text(encoding="utf-8")):
                violations.append(
                    f"PROMPT-REDIRECT-INVERSION {rel} "
                    f"(kind={kind} の責務プロンプトが空殻/リダイレクト。"
                    "7層本文は prompts/ を SSOT 正本とし agents/ へ移送しないこと)"
                )
    return violations


def _self_test() -> int:
    """ファイル名 regex と空殻リダイレクト検出の双方を assert。"""
    cases_violation = [
        "plugins/harness-creator/skills/run-foo/prompts/main.yaml",
        "plugins/harness-creator/skills/wrap-bar/prompts/wrap.yaml",
        "plugins/harness-creator/skills/assign-baz/prompts/evaluate.yaml",
        "plugins/x/skills/run-y/prompts/main.md",
    ]
    cases_ok = [
        "plugins/harness-creator/skills/run-foo/prompts/R1.md",
        "plugins/harness-creator/skills/run-foo/prompts/R2.yaml",
        "plugins/harness-creator/skills/delegate-x/prompts/R1-delegate.md",
    ]
    failures: list[str] = []
    for c in cases_violation:
        if SKILL_LOCAL_V1_RE.match(c):
            failures.append(f"SHOULD violate but matched: {c}")
    for c in cases_ok:
        if not SKILL_LOCAL_V1_RE.match(c):
            failures.append(f"SHOULD match but did not: {c}")
    # INVERSION 検査の self-test (合成テキスト)
    shell = "---\nmoved_to: agents/x.md\n---\n\n# Prompt (リダイレクト)\n本文は agents/x.md。\n"
    body = "---\nresponsibility_id: R1\n---\n\n" + "\n".join(f"行{i} 実質本文" for i in range(20))
    if not _is_redirect_shell(shell):
        failures.append("SHOULD detect redirect shell (moved_to) but did not")
    if _is_redirect_shell(body):
        failures.append("SHOULD treat 7-layer body as OK but flagged as shell")
    if failures:
        for f in failures:
            print(f, file=sys.stderr)
        print("self-test: FAIL")
        return 1
    print("self-test: PASS (filename regex + redirect-shell inversion both detected)")
    return 0


def main() -> int:
    argv = sys.argv[1:]
    if argv and argv[0] == "--self-test":
        return _self_test()
    if argv:
        print(
            "usage: lint-prompt-placement.py [--self-test]",
            file=sys.stderr,
        )
        return 2

    root = _repo_root()
    violations = scan(root)
    if not violations:
        print(f"ok: all prompts under {root}/plugins/*/skills/*/prompts/ "
              "comply (skill-local-v1 regex + no redirect-inversion)")
        return 0
    print("prompt-placement violations (see references/prompt-placement-convention.md):")
    for v in violations:
        print(f"  - {v}")
    print(f"total: {len(violations)} violation(s)")
    return 1


if __name__ == "__main__":
    raise SystemExit(main())
