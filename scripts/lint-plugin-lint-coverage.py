#!/usr/bin/env python3
# /// script
# name: lint-plugin-lint-coverage
# purpose: marketplace 登録 plugin が skill lint (name/description/frontmatter) の被覆対象に配線済みかを検査するメタ lint。
# inputs:
#   - .claude-plugin/marketplace.json
#   - Makefile
#   - .github/workflows/*.yml
# outputs:
#   - stdout: 被覆マトリクス + OK
#   - stderr: 未被覆 plugin と修正方法
# contexts: [C, E]
# network: false
# write-scope: none
# dependencies: []
# requires-python: ">=3.10"
# ///
"""plugin 横断の lint 被覆メタ検査。

背景 (elegant-review finding): skill lint (lint-skill-name / lint-skill-description /
validate-frontmatter) の対象 plugin が Makefile / CI yml に per-plugin 手書き配線
されており、新 plugin 追加時の被覆漏れを検出する機械層が無く同型漏れが構造的に
再発する。本スクリプトは marketplace.json を plugin 一覧の SSOT として、実体
skill を所有する全 plugin が 3 種 lint の `--skills-dir` 対象に含まれることを
fail-closed で強制する (新 plugin 追加忘れをここで fail させる)。

起点バイアスの依存関係 (elegant-review 20260626-ngs-mechanization):
  本スクリプトは marketplace.json 起点で巡回するため、marketplace 未登録の
  新 plugin は被覆判定の母集合に入らず素通りする (「漏れが漏れを隠す」自己強化
  ループの構造要素)。この盲点は `scripts/validate-plugin-completeness.py` の
  MK-001 (実体ディレクトリ起点で marketplace 未登録を fail-closed 検出) が
  上流ゲートとして塞ぐ前提。両者は必ずセットで CI 配線すること
  (validate-plugin-completeness を外す/弱めると本 lint の盲点が復活する)。

被覆判定の定義:
  - 対象 plugin: marketplace.json 登録済み かつ skills/ 配下に実体 (非 symlink)
    の skill ディレクトリ (SKILL.md 持ち) を 1 つ以上所有するもの。
    symlink 共有 (run-skill-feedback 等) のみの plugin は対象外
    (PKG-003 と同じ「実体のみ所有カウント」原則)。
  - 被覆: Makefile または .github/workflows/*.yml 内に
    `<lint script> ... --skills-dir plugins/<plugin>/skills` の配線が存在すること。
    backslash 行継続は連結して判定する。

例外 (allowlist): lint が現状 FAIL する等の理由で被覆編入できない plugin は
ALLOWLIST に (plugin, lint_kind) と非空の理由を宣言する。被覆済みになった
stale エントリはエラー (掃除を強制)。

Usage:
  lint-plugin-lint-coverage.py [--repo-root /path/to/repo]

Exit 0 = ok, 1 = violation, 2 = usage error.
"""
from __future__ import annotations

import json
import re
import sys
from pathlib import Path

# 検査対象 lint 種別 -> 配線として認める script basename 群。
# repo-root scripts/ 直下と plugins/skill-governance-lint/scripts/ の両系統が
# 同名 basename で存在するため basename で同定する。
LINT_KINDS: dict[str, tuple[str, ...]] = {
    "skill-name": ("lint-skill-name.py",),
    "skill-description": ("lint-skill-description.py",),
    "frontmatter": ("validate-frontmatter.py",),
}

# 被覆配線を探索するファイル (repo-root 相対 glob)。
COVERAGE_SOURCE_GLOBS: tuple[str, ...] = (
    "Makefile",
    ".github/workflows/*.yml",
    ".github/workflows/*.yaml",
)

# 例外宣言: {(plugin名, lint_kind): 理由 (非空必須)}。
# 理由には「なぜ被覆編入できないか」と検出日を残し、後日の是正課題として追跡する。
ALLOWLIST: dict[tuple[str, str], str] = {
    ("skill-intake", "frontmatter"): (
        "run-intake-revise の frontmatter effect 'notion-mutation' が "
        "validate-frontmatter の enum (conversation-output/external-mutation/"
        "local-artifact/none) 外で lint FAIL する。plugins/skill-intake 実体の "
        "修正は被覆メタ検査導入のスコープ外のため後日是正 (2026-06-10 検出)。"
        "name/description lint は PASS のため被覆編入済み。"
    ),
}

SKILLS_DIR_RE = re.compile(r"--skills-dir[ =]+(?:\./)?plugins/([A-Za-z0-9_-]+)/skills")


def load_marketplace_plugins(root: Path) -> list[tuple[str, Path]]:
    """marketplace.json から (plugin名, plugin絶対パス) を返す。"""
    marketplace = root / ".claude-plugin" / "marketplace.json"
    data = json.loads(marketplace.read_text(encoding="utf-8"))
    out: list[tuple[str, Path]] = []
    for entry in data.get("plugins", []):
        name = entry.get("name")
        source = entry.get("source", f"./plugins/{name}")
        if not name:
            continue
        out.append((name, (root / source).resolve()))
    return out


def owned_skill_dirs(plugin_dir: Path) -> list[Path]:
    """plugin が実体所有する skill ディレクトリ (非 symlink + SKILL.md 持ち)。"""
    skills = plugin_dir / "skills"
    if not skills.is_dir():
        return []
    owned: list[Path] = []
    for child in sorted(skills.iterdir()):
        if child.is_symlink():
            continue  # symlink 共有 skill は所有とみなさない (PKG-003 原則)
        if child.is_dir() and (child / "SKILL.md").exists():
            owned.append(child)
    return owned


def _join_continuations(text: str) -> str:
    """Makefile / YAML の backslash 行継続を 1 行に連結する。"""
    return re.sub(r"\\\s*\n", " ", text)


def extract_covered(text: str) -> dict[str, set[str]]:
    """テキストから lint_kind -> 被覆 plugin 名集合を抽出する。

    判定 (継続連結後の行単位):
      1. lint script basename と `--skills-dir plugins/<name>/skills` が
         同一行にあれば被覆。
      2. 同一行に --skills-dir が無い場合のみ直後 1 行を見る
         (YAML の run: > 折返しで引数が次行に落ちるケース)。ただし次行が
         別の lint 呼び出し行なら見ない (隣接コマンドへの誤帰属防止)。
    """
    all_basenames = tuple(b for bs in LINT_KINDS.values() for b in bs)
    covered: dict[str, set[str]] = {kind: set() for kind in LINT_KINDS}
    lines = _join_continuations(text).splitlines()
    for i, line in enumerate(lines):
        for kind, basenames in LINT_KINDS.items():
            if not any(b in line for b in basenames):
                continue
            same_line = SKILLS_DIR_RE.findall(line)
            if same_line:
                covered[kind].update(same_line)
                continue
            if i + 1 < len(lines):
                nxt = lines[i + 1]
                if not any(b in nxt for b in all_basenames):
                    covered[kind].update(SKILLS_DIR_RE.findall(nxt))
    return covered


def collect_coverage(root: Path) -> dict[str, set[str]]:
    covered: dict[str, set[str]] = {kind: set() for kind in LINT_KINDS}
    for pattern in COVERAGE_SOURCE_GLOBS:
        for path in sorted(root.glob(pattern)):
            if not path.is_file():
                continue
            file_covered = extract_covered(path.read_text(encoding="utf-8"))
            for kind, names in file_covered.items():
                covered[kind] |= names
    return covered


def check_coverage(
    root: Path,
    allowlist: dict[tuple[str, str], str] | None = None,
) -> tuple[list[str], list[str]]:
    """(errors, report_lines) を返す。errors 空 = 合格。"""
    allowlist = ALLOWLIST if allowlist is None else allowlist
    errors: list[str] = []
    report: list[str] = []

    # allowlist 健全性: 理由は非空必須
    for (plugin, kind), reason in allowlist.items():
        if kind not in LINT_KINDS:
            errors.append(
                f"allowlist エントリ ({plugin}, {kind}) の lint 種別が不正 "
                f"(有効: {sorted(LINT_KINDS)})"
            )
        if not str(reason).strip():
            errors.append(
                f"allowlist エントリ ({plugin}, {kind}) に理由が無い (理由必須)"
            )

    covered = collect_coverage(root)
    required = [
        (name, plugin_dir)
        for name, plugin_dir in load_marketplace_plugins(root)
        if owned_skill_dirs(plugin_dir)
    ]
    if not required:
        errors.append(
            "実体 skill を所有する plugin が 0 件 (marketplace.json か "
            "plugins/ 配置が壊れている可能性)"
        )

    for name, plugin_dir in required:
        states: list[str] = []
        for kind in LINT_KINDS:
            is_covered = name in covered[kind]
            is_allowed = (name, kind) in allowlist
            if is_covered and is_allowed:
                errors.append(
                    f"{name}: lint '{kind}' は被覆済みなのに allowlist に残存 "
                    "(stale エントリ)。scripts/lint-plugin-lint-coverage.py の "
                    "ALLOWLIST から削除すること"
                )
                states.append(f"{kind}=covered+stale-allowlist")
            elif is_covered:
                states.append(f"{kind}=covered")
            elif is_allowed:
                states.append(f"{kind}=allowlisted")
            else:
                errors.append(
                    f"{name}: lint '{kind}' ({'/'.join(LINT_KINDS[kind])}) の被覆対象外。"
                    "修正方法: (1) Makefile の lint ターゲット (または "
                    ".github/workflows/governance-check.yml) に "
                    f"`--skills-dir plugins/{name}/skills` の配線を追加する、"
                    "(2) lint FAIL 等で編入不能なら "
                    "scripts/lint-plugin-lint-coverage.py の ALLOWLIST に "
                    f"(('{name}', '{kind}')) を理由付きで宣言する"
                )
                states.append(f"{kind}=UNCOVERED")
        report.append(f"{name}: {', '.join(states)}")

    return errors, report


def main(argv: list[str]) -> int:
    root = Path(__file__).resolve().parents[1]
    args = list(argv)
    if "--repo-root" in args:
        idx = args.index("--repo-root")
        if idx + 1 >= len(args):
            print(
                "usage: lint-plugin-lint-coverage.py [--repo-root /path/to/repo]",
                file=sys.stderr,
            )
            return 2
        root = Path(args[idx + 1]).resolve()
    if not (root / ".claude-plugin" / "marketplace.json").is_file():
        print(f"marketplace.json not found under: {root}", file=sys.stderr)
        return 2

    errors, report = check_coverage(root)
    for line in report:
        print(f"  {line}")
    if errors:
        for e in errors:
            print(f"NG: {e}", file=sys.stderr)
        return 1
    print(f"ok: plugin lint coverage ({len(report)} plugins, {len(LINT_KINDS)} lint kinds)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
