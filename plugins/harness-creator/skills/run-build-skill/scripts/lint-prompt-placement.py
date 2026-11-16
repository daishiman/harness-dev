#!/usr/bin/env python3
# /// script
# name: lint-prompt-placement
# purpose: plugins/*/skills/*/prompts/* が prompt-placement-convention.md
#          に準拠していることを機械検証する。(a) ファイル名 regex の SSOT は
#          validate-build-trace.py の LAYER_YAML_PATH_PATTERNS から import、
#          (b) run/assign の prompts/<R-id>.md が空殻リダイレクトでない (frontmatter に
#          moved_to: が無く、7 層の見出し「# Layer N:」のそれぞれに agents/ を指すだけでない
#          本文がある = PROMPT-REDIRECT-INVERSION 禁止) ことを検査する。層の分け方は
#          vendor の verify-completeness.py の split_layers を import する。各層の中身が
#          l5-contract に沿うかは検査しない (lint-agent-prompt-content.py --mode prompt の責務)。
# inputs:
#   - argv: --self-test (任意。ほかの引数と併用しない) / なし=リポジトリ全走査
#   - file: <repo>/plugins/*/skills/*/prompts/* (UTF-8 として読む)
#   - file: <harness-creator>/vendor/prompt-creator/verify-completeness.py (split_layers を import)
# outputs:
#   - stdout: ok message / violation list / self-test の結果
#   - stderr: usage error、self-test の失敗の内訳、vendor を読み込めない理由
#   - exit: 0=PASS / 1=規約逸脱検出 / 2=usage error・UTF-8 で読めない prompt (PROMPT-UNREADABLE)・vendor 不在
# requires-python: ">=3.10"
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

import importlib.util
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
# 7 層の見出し「# Layer N:」の分け方の SSOT (scaffold-prompt.py / merge-layers.py の出力に合わせた
# vendor の split_layers)。scripts/ -> run-build-skill/ -> skills/ -> harness-creator/
_VENDORED_VERIFY = (_SCRIPT_DIR.parent.parent.parent / "vendor" / "prompt-creator"
                    / "verify-completeness.py")
# 空殻の層: 本文のどの行も、移送先の agents/ を指すだけのもの。
_POINTER_TOKEN = "agents/"
_MOVED_TO_RE = re.compile(r"^\s*moved_to\s*:", re.MULTILINE)
# packaged prompt は frontmatter の前に <!-- ... --> を置くことがある。
_LEADING_COMMENTS_RE = re.compile(r"\A(?:\s*<!--.*?-->)+\s*", re.DOTALL)
_layers_module = None


class VendorMissing(RuntimeError):
    """split_layers の正本を読み込めない。検査できないので exit 2 にする。"""


def _layers():
    """vendor の verify-completeness.py を 1 度だけ読み込んで返す (main は __name__ で守られている)。"""
    global _layers_module
    if _layers_module is None:
        if not _VENDORED_VERIFY.is_file():
            raise VendorMissing(f"vendored verifier 不在: {_VENDORED_VERIFY}")
        spec = importlib.util.spec_from_file_location("lpp_verify_completeness", _VENDORED_VERIFY)
        module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(module)
        _layers_module = module
    return _layers_module


def _repo_root() -> Path:
    # scripts/ -> run-build-skill/ -> skills/ -> harness-creator/ -> plugins/ -> repo
    return _SCRIPT_DIR.parent.parent.parent.parent.parent


def _skill_kind_of(rel: str) -> str | None:
    """plugins/<p>/skills/<kind>-<name>/prompts/<f> の <kind> を返す。"""
    m = re.search(r"/skills/(run|assign|ref|wrap|delegate)-[a-z0-9-]+/prompts/", rel)
    return m.group(1) if m else None


_BOM = chr(0xFEFF)


def _normalize(text: str) -> str:
    return text.lstrip(_BOM).replace("\r\n", "\n")


def _split_frontmatter(text: str) -> tuple[str, str]:
    """(frontmatter, 残り) を返す。BOM・CRLF・frontmatter の前の <!-- --> を許す。無ければ ("", text)。"""
    norm = _normalize(text)
    lead = _LEADING_COMMENTS_RE.match(norm)
    head = norm[lead.end():] if lead else norm
    if head.startswith("---\n"):
        end = head.find("\n---", 4)
        if end != -1:
            nl = head.find("\n", end + 1)
            return head[4:end], head[nl + 1:] if nl != -1 else ""
    return "", text


def _shell_reason(text: str) -> str | None:
    """空殻なら理由を、7 層本文を持つなら None を返す。

    空殻かどうかを宣言の語では決めない。「リダイレクト」や「agents/」は 7 層本文の中にも
    ふつうに現れ (adapter への言及、shell のリダイレクトの禁止など)、逆に空殻は英語や別の語でも
    名乗れるからである。見るのは規約が禁じるものそのもの、つまり prompts/ に 7 層本文が無いことで、
    次のどれかに当たれば空殻とする。
    - frontmatter に moved_to: がある (本文の移送を宣言している)。
    - 「# Layer N:」の見出しが 1〜7 のどれか欠けている。
    - ある層の本文が空か、どの行も agents/ を指すだけである。
    各層の中身が l5-contract に沿うかはこの lint では見ない。それは lint-agent-prompt-content.py
    --mode prompt が担い、どの plugin に走らせるかは workflow が決める。この lint は中身を見ない
    代わりに、全 plugin の run/assign の prompt を対象にする。
    """
    fm, _rest = _split_frontmatter(text)
    if _MOVED_TO_RE.search(fm):
        return "frontmatter に moved_to: がある"
    vc = _layers()
    sections = vc.split_layers(_normalize(text))
    missing = [n for n, sec in sections.items() if sec is None]
    if missing:
        return "Layer " + ", ".join(map(str, missing)) + " の見出し (# Layer N:) が無い"
    hollow = [n for n, sec in sections.items()
              if not [ln for ln in vc.non_comment_body(sec) if _POINTER_TOKEN not in ln]]
    if hollow:
        return "Layer " + ", ".join(map(str, hollow)) + " の本文が空か、agents/ を指す行だけ"
    return None


def _is_redirect_shell(text: str) -> bool:
    return _shell_reason(text) is not None


def scan(repo_root: Path) -> list[str]:
    """規約逸脱 (PROMPT-FILENAME-FORMAT / PROMPT-REDIRECT-INVERSION / PROMPT-UNREADABLE) の一覧を返す。"""
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
            try:
                text = path.read_text(encoding="utf-8")
            except (OSError, UnicodeDecodeError) as exc:
                violations.append(f"PROMPT-UNREADABLE {rel} (UTF-8 として読めない: {exc.__class__.__name__})")
                continue
            reason = _shell_reason(text)
            if reason:
                violations.append(
                    f"PROMPT-REDIRECT-INVERSION {rel} "
                    f"(kind={kind} の責務プロンプトが空殻/リダイレクト: {reason}。"
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
        "plugins/x/skills/run-y/prompts/R2B-readiness.md",
        "plugins/x/skills/run-y/prompts/R2b_readiness.md",
    ]
    cases_ok = [
        "plugins/harness-creator/skills/run-foo/prompts/R1.md",
        "plugins/harness-creator/skills/run-foo/prompts/R1-elicit.md",
        "plugins/harness-creator/skills/run-foo/prompts/R2.yaml",
        "plugins/harness-creator/skills/run-foo/prompts/R2b-readiness.md",
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
    layered = "\n".join(f"## Layer {n}: 層{n}\n\n- 層{n} の本文。" for n in range(1, 8))
    cases_shell = (
        ("moved_to", "---\nmoved_to: agents/x.md\n---\n\n" + layered),
        # 冒頭を変更履歴で埋め、宣言をその後ろに英語で置いた空殻 (7 層の見出しが無い)
        ("late declaration", "\n".join(f"- 変更履歴 {i}" for i in range(15))
         + "\n## Body (redirect)\nsee agents/x.md\n"),
        ("pointer-only layer", layered.replace("- 層3 の本文。", "- 本文は agents/x.md の Layer 3。")),
        ("missing layer", layered.replace("## Layer 6: 層6", "## 層6")),
    )
    for label, text in cases_shell:
        if not _is_redirect_shell(text):
            failures.append(f"SHOULD detect redirect shell ({label}) but did not")
    # 冒頭で adapter (agents/) とリダイレクトに触れ、本文の途中で shell のリダイレクトに触れる
    # 7 層本文は空殻ではない
    mention = ("Packaged from agents/x.md (リダイレクト元ではない).\n" + layered
               + "\n- 禁止: Bash の sed やリダイレクトでの書き換え。")
    for label, text in (("7-layer body", layered), ("7-layer body mentioning both words", mention)):
        if _is_redirect_shell(text):
            failures.append(f"SHOULD treat {label} as OK but flagged as shell")
    if failures:
        for f in failures:
            print(f, file=sys.stderr)
        print("self-test: FAIL")
        return 1
    print("self-test: PASS (filename regex + redirect-shell inversion both detected)")
    return 0


def main() -> int:
    argv = sys.argv[1:]
    if argv and argv != ["--self-test"]:
        print(
            "usage: lint-prompt-placement.py [--self-test]",
            file=sys.stderr,
        )
        return 2
    try:
        if argv:
            return _self_test()
        root = _repo_root()
        violations = scan(root)
    except VendorMissing as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 2
    if not violations:
        print(f"ok: all prompts under {root}/plugins/*/skills/*/prompts/ "
              "comply (skill-local-v1 regex + no redirect-inversion)")
        return 0
    print("prompt-placement violations (see references/prompt-placement-convention.md):")
    for v in violations:
        print(f"  - {v}")
    print(f"total: {len(violations)} violation(s)")
    # 読めない prompt は検査できなかったものなので、逸脱 (exit 1) と分けて exit 2 にする
    return 2 if any(v.startswith("PROMPT-UNREADABLE ") for v in violations) else 1


if __name__ == "__main__":
    raise SystemExit(main())
