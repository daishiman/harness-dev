#!/usr/bin/env python3
# /// script
# name: lint-agent-prompt-content
# purpose: harness-creator の agents/*.md (frontmatter=plugin YAML + 本文7層) と skills/*/prompts/*.md (純粋7層) の本文が prompt-creator の l5-contract v2.0.0 (7層構造・Layer5 サブ構造・固定手順禁止) に準拠するかを --mode agent|prompt で fail-closed 検証する内容 lint。配置 lint (lint-prompt-placement.py) とは直交する。--check-vendor-parity で vendored verify-completeness.py の canonical への byte 一致を検証する。
# inputs:
#   - argv: --mode agent|prompt [--plugins-dir <dir>] | --check-vendor-parity | --self-test
# outputs:
#   - stdout: OK サマリ
#   - stderr: 違反ファイル + 違反節 + 理由の一覧
#   - exit: 0=OK / 1=violation / 2=usage error
# contexts: [C, E]
# network: false
# write-scope: none
# dependencies: []
# requires-python: ">=3.10"
# ///
"""agents/*.md・skills/*/prompts/*.md の本文 7 層準拠を検証する内容 lint。

正本契約:
  - SubAgent ハイブリッド契約 (frontmatter=plugin YAML / 本文=7層):
    plugins/prompt-creator/skills/run-prompt-creator-7layer/references/subagent-hybrid-format.md
  - 純粋 7 層 (prompts/*.md 向け):
    plugins/prompt-creator/skills/run-prompt-creator-7layer/references/seven-layer-format.md (l5-contract v2.0.0)

本文 7 層の網羅・Layer5 ゴールシーク要素・固定手順不在の判定ロジックは prompt-creator の
verify-completeness.py を vendor/prompt-creator/ へ byte 一致で複製したものを subprocess で
そのまま再利用する (ロジック二重実装を避け drift を --check-vendor-parity で検出する)。本 lint が
その上に重ねるのは mode 別の frontmatter 規律のみ:
  --mode agent : frontmatter が plugin agent YAML (name/description/tools 必須) であること + 本文 7 層 OK
  --mode prompt: frontmatter が不在 (純粋 7 層 Markdown) であること + 本文 7 層 OK

Exit: 0=OK, 1=violation, 2=usage error。
"""
from __future__ import annotations

import argparse
import re
import subprocess
import sys
from pathlib import Path

_SCRIPT_DIR = Path(__file__).resolve().parent
_PLUGIN_ROOT = _SCRIPT_DIR.parent            # plugins/harness-creator
_REPO_ROOT = _PLUGIN_ROOT.parent.parent      # repo root

# 本文 7 層の判定に用いる vendored 検証器 (byte 一致複製・自己完結)。
VENDORED_VERIFY = _PLUGIN_ROOT / "vendor" / "prompt-creator" / "verify-completeness.py"
# --check-vendor-parity が突合する canonical (prompt-creator 所有・drift 検出専用)。
CANONICAL_VERIFY = (
    _REPO_ROOT / "plugins" / "prompt-creator" / "skills" / "run-prompt-creator-7layer"
    / "scripts" / "verify-completeness.py"
)

# plugin agent frontmatter の必須キー (subagent-hybrid-format.md「frontmatter 契約」)。
AGENT_FRONTMATTER_REQUIRED = ("name", "description", "tools")
_FM_KEY_RE = re.compile(r"^([A-Za-z][A-Za-z0-9_-]*)\s*:", re.MULTILINE)


def split_frontmatter(text: str) -> tuple[str | None, str]:
    """YAML frontmatter を (frontmatter本文 or None, 本文) に分離する。

    先頭が `---` 行で始まり閉じ `---` があれば frontmatter とみなす。無ければ (None, 全文)。
    """
    if text.startswith("---\n") or text.startswith("---\r\n"):
        end = text.find("\n---", 3)
        if end != -1:
            nl = text.find("\n", end + 1)
            fm = text[text.find("\n") + 1:end]
            body = text[nl + 1:] if nl != -1 else ""
            return fm, body
    return None, text


def check_agent_frontmatter(fm: str) -> list[str]:
    """agent frontmatter に必須キー (name/description/tools) が揃っているか。欠落キー名を返す。"""
    keys = set(_FM_KEY_RE.findall(fm))
    return [k for k in AGENT_FRONTMATTER_REQUIRED if k not in keys]


def verify_body_7layer(path: Path) -> tuple[bool, str]:
    """vendored verify-completeness.py を subprocess で実行し (合格?, 詳細) を返す。

    verify-completeness は frontmatter を無視し `# Layer N:` マーカーで本文を分割するため、
    frontmatter 付き agent / 純粋 prompt の双方をファイルごとそのまま渡せる。
    """
    if not VENDORED_VERIFY.is_file():
        return False, f"vendored verifier 不在: {VENDORED_VERIFY}"
    proc = subprocess.run(
        [sys.executable, str(VENDORED_VERIFY), "--input", str(path)],
        capture_output=True, text=True,
    )
    detail = (proc.stderr or proc.stdout).strip()
    return proc.returncode == 0, detail


def lint_file(path: Path, mode: str) -> list[str]:
    """1 ファイルの内容違反メッセージ一覧を返す (空=OK)。mode ∈ {agent, prompt}。"""
    rel = _rel(path)
    violations: list[str] = []
    text = path.read_text(encoding="utf-8")
    fm, _body = split_frontmatter(text)

    if mode == "agent":
        if fm is None:
            violations.append(
                f"AGENT-FRONTMATTER-MISSING {rel}: plugin agent YAML frontmatter (--- ... ---) が無い "
                "(subagent-hybrid-format.md: frontmatter=plugin YAML 必須)"
            )
        else:
            missing = check_agent_frontmatter(fm)
            if missing:
                violations.append(
                    f"AGENT-FRONTMATTER-KEYS {rel}: 必須キー欠落 {', '.join(missing)} "
                    "(name/description/tools は必須)"
                )
    elif mode == "prompt":
        if fm is not None:
            violations.append(
                f"PROMPT-FRONTMATTER-PRESENT {rel}: prompts/*.md は frontmatter を持たない純粋 7 層 "
                "Markdown であること (subagent-hybrid-format.md 差分表)"
            )

    ok, detail = verify_body_7layer(path)
    if not ok:
        violations.append(f"BODY-7LAYER {rel}: 本文が l5-contract v2.0.0 非準拠 — {detail}")
    return violations


def _rel(path: Path) -> str:
    try:
        return path.resolve().relative_to(_REPO_ROOT).as_posix()
    except ValueError:
        return str(path)


def collect_targets(plugins_dir: Path, mode: str) -> list[Path]:
    """走査対象ファイル一覧。agent=<dir>/agents/*.md、prompt=<dir>/skills/*/prompts/*.md。

    symlink は除外する: plugins_dir 配下には他プラグインの skill を bundling する symlink が
    存在しうる (例 harness-creator/skills/run-contract-* → contract-generator)。それらは所有元
    プラグインが lint するため、本 lint は plugins_dir の**自前**コンテンツのみを対象にする。
    """
    if mode == "agent":
        agents_dir = plugins_dir / "agents"
        if not agents_dir.is_dir():
            return []
        return sorted(p for p in agents_dir.glob("*.md") if not p.is_symlink())
    targets: list[Path] = []
    skills_dir = plugins_dir / "skills"
    if not skills_dir.is_dir():
        return targets
    for skill in sorted(skills_dir.iterdir()):
        if skill.is_symlink() or not skill.is_dir():
            continue
        targets.extend(sorted(p for p in (skill / "prompts").glob("*.md") if not p.is_symlink()))
    return targets


def scan(plugins_dir: Path, mode: str) -> list[str]:
    """plugins_dir 配下の対象を走査し全違反メッセージを返す。"""
    violations: list[str] = []
    for path in collect_targets(plugins_dir, mode):
        if path.is_file():
            violations.extend(lint_file(path, mode))
    return violations


def check_vendor_parity() -> tuple[str, str]:
    """vendored verifier が canonical と byte 一致か。(status, msg) を返す。

    status ∈ {OK, MISMATCH, MISSING_VENDOR, SKIP_NO_CANONICAL}。
    canonical 不在 (prompt-creator 未同梱の install 文脈) は SKIP で 0 扱い (携帯性)。
    """
    if not VENDORED_VERIFY.is_file():
        return "MISSING_VENDOR", f"vendored verifier 不在: {_rel(VENDORED_VERIFY)}"
    if not CANONICAL_VERIFY.is_file():
        return "SKIP_NO_CANONICAL", (
            f"canonical 不在: {_rel(CANONICAL_VERIFY)} (install 文脈のため parity 検証を skip)"
        )
    if VENDORED_VERIFY.read_bytes() == CANONICAL_VERIFY.read_bytes():
        return "OK", f"byte 一致: {_rel(VENDORED_VERIFY)} == {_rel(CANONICAL_VERIFY)}"
    return "MISMATCH", (
        f"drift 検出: {_rel(VENDORED_VERIFY)} != {_rel(CANONICAL_VERIFY)} "
        "— canonical から再 vendoring すること"
    )


def _run_parity() -> int:
    status, msg = check_vendor_parity()
    if status in ("OK", "SKIP_NO_CANONICAL"):
        print(f"OK vendor-parity: {msg}")
        return 0
    sys.stderr.write(f"FAIL vendor-parity ({status}): {msg}\n")
    return 1


def _run_mode(mode: str, plugins_dir: Path) -> int:
    if not plugins_dir.is_dir():
        sys.stderr.write(f"usage: --plugins-dir に有効なディレクトリを指定 (not a dir: {plugins_dir})\n")
        return 2
    targets = collect_targets(plugins_dir, mode)
    if not targets:
        # fail-closed floor guard: 走査対象 0 件の空振り合格 (vacuous pass) を禁止する。
        # dir 改名・--plugins-dir の typo・symlink 化で対象が消えても CI が恒久緑のまま
        # 保証が無言で腐るのを防ぐ (plan component C02 の fail-closed 契約)。
        sys.stderr.write(
            f"FAIL content-lint (--mode {mode}): scanned=0 under {_rel(plugins_dir)} — "
            "走査対象 0 件は fail-closed で違反扱い (--plugins-dir は agents/ または "
            "skills/*/prompts/ を持つ単一 plugin root を指すこと)\n"
        )
        return 1
    violations = scan(plugins_dir, mode)
    if violations:
        sys.stderr.write(f"FAIL content-lint (--mode {mode}):\n")
        for v in violations:
            sys.stderr.write(f"  - {v}\n")
        sys.stderr.write(f"\nscanned={len(targets)} violations={len(violations)}\n")
        return 1
    print(f"OK content-lint (--mode {mode}): scanned={len(targets)} files 全て 7 層準拠 "
          f"(l5-contract v2.0.0) under {_rel(plugins_dir)}")
    return 0


def _self_test() -> int:
    """frontmatter 分離・agent 必須キー検出の合成テスト (subprocess/実ファイル非依存)。"""
    failures: list[str] = []
    fm, body = split_frontmatter("---\nname: x\ntools: Read\n---\n\n## Layer 1: a\n")
    if fm is None or "name: x" not in fm or "## Layer 1" not in body:
        failures.append("split_frontmatter: frontmatter 付き分離に失敗")
    fm2, body2 = split_frontmatter("## Layer 1: a\n本文\n")
    if fm2 is not None or "## Layer 1" not in body2:
        failures.append("split_frontmatter: frontmatter 無しを None にできず")
    if check_agent_frontmatter("name: x\ndescription: y\ntools: Read") != []:
        failures.append("check_agent_frontmatter: 完全 frontmatter を違反判定")
    if "tools" not in check_agent_frontmatter("name: x\ndescription: y"):
        failures.append("check_agent_frontmatter: tools 欠落を検出できず")
    if failures:
        for f in failures:
            print(f, file=sys.stderr)
        print("self-test: FAIL", file=sys.stderr)
        return 1
    print("self-test: PASS (frontmatter split + agent key detection)")
    return 0


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        add_help=True,
        description="agents/prompts 本文の 7 層準拠 (l5-contract v2.0.0) を検証する内容 lint",
    )
    parser.add_argument("--mode", choices=("agent", "prompt"))
    parser.add_argument(
        "--plugins-dir",
        default=str(_PLUGIN_ROOT),
        help="走査基点ディレクトリ (既定: 所有プラグイン plugins/harness-creator)",
    )
    parser.add_argument("--check-vendor-parity", action="store_true")
    parser.add_argument("--self-test", action="store_true")
    args = parser.parse_args(argv)

    if args.self_test:
        return _self_test()
    if args.check_vendor_parity:
        return _run_parity()
    if args.mode:
        return _run_mode(args.mode, Path(args.plugins_dir))
    sys.stderr.write(
        "usage: lint-agent-prompt-content.py --mode agent|prompt [--plugins-dir <dir>] "
        "| --check-vendor-parity | --self-test\n"
    )
    return 2


if __name__ == "__main__":
    raise SystemExit(main())
