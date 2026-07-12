#!/usr/bin/env python3
"""lint-legacy-plugin-name: 旧 plugin 固有名の再流入を fail-closed で遮断する。

2026-07-02 の plugin 改名 (skill-creator → harness-creator) 後、並行 worktree・
停滞ブランチの merge で旧固有名が能動層へ silent に復活する経路を封鎖する。
deny 対象は固有名 3 変形のみ (一般語 skill/スキル は意味論境界ルールにより合法)。

allowlist は凍結層 (履歴・別実体・エディタ状態) と、改名の説明として旧名を意図的に
言及するファイルに限定する。allowlist 追加時は reason を必ず書くこと。
"""
from __future__ import annotations

import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]

# 旧固有名 3 変形 (merged-directive 2026-07-02: 固有名層は常にハーネス概念で置換一意)
LEGACY_TOKENS = ["skill-creator", "skill_creator", "スキルクリエイター"]

# 凍結層 prefix (履歴・別実体・エディタ状態): 遡及書換は記録改変のため対象外
FROZEN_PREFIXES = (
    "eval-log/",                # 過去 run 記録 (runtime 参照層は改名時に新パスへ移行済み)
    "doc/参考Skill/",           # 同名別物の外部由来参考資産
    ".obsidian/",               # エディタ状態
    ".claude/changelog/",       # append-only governance 履歴
    "installers/harness-creator-kit/migrate-log/",  # 移行履歴
)

# 歴史記録ファイル (path 部品一致): CHANGELOG / changelog / lessons-learned
FROZEN_PARTS = {"CHANGELOG.md", "changelog", "lessons-learned"}

# 意図的言及の許容ファイル (reason 必須)
ALLOWLIST = {
    ".beads/config.yaml": "GitHub 上で現存する repository remote の外部識別子",
    "scripts/lint-legacy-plugin-name.py": "本 lint 自身 (deny パターン定義)",
    "CONVENTIONS.md": "意味論境界ルールの旧名→新名対応の説明",
    "README.md": "改名移行手順 (旧 enabledPlugins キーの案内)",
    "plugins/harness-creator/skills/ref-skill-glossary/references/terms.md":
        "ハーネス用語定義での旧名由来の説明",
    "plugins/harness-creator/README.md": "改名の経緯と移行手順",
    "plugins/harness-creator/references/plugin-rename-checklist.md":
        "plugin 単位改名手順の恒久チェックリスト",
    "plugins/harness-creator/skills/ref-yaml-spec-fetcher/references/yaml-spec-cache.md":
        "外部 fetch した YAML spec の cache mirror (ref-yaml-spec-fetcher 自動生成)。"
        "逐語の外部由来内容で能動層でないため凍結層と同等に扱う",
}


def is_frozen(rel: str) -> bool:
    if rel.startswith(FROZEN_PREFIXES):
        return True
    return bool(FROZEN_PARTS & set(rel.split("/")))


def main() -> int:
    files = subprocess.run(
        ["git", "ls-files"], capture_output=True, text=True, cwd=ROOT, check=True
    ).stdout.splitlines()
    violations: list[str] = []
    for rel in files:
        if is_frozen(rel) or rel in ALLOWLIST:
            continue
        p = ROOT / rel
        if p.is_symlink() or not p.is_file():
            continue
        try:
            text = p.read_text(encoding="utf-8")
        except (UnicodeDecodeError, OSError):
            continue
        for token in LEGACY_TOKENS:
            if token in text:
                line_no = next(
                    (i for i, ln in enumerate(text.splitlines(), 1) if token in ln), 0
                )
                violations.append(f"{rel}:{line_no}: 旧固有名 {token!r} が能動層に残存/再流入")
                break
    if violations:
        print("[lint-legacy-plugin-name] VIOLATION:")
        for v in violations:
            print(f"  {v}")
        print(
            "  → 旧名 skill-creator は harness-creator へ改名済み (2026-07-02)。"
            "新規参照は新名を使い、意図的な歴史言及は ALLOWLIST に reason 付きで登録する。"
        )
        return 1
    print("[lint-legacy-plugin-name] OK: 旧固有名の能動層残存 0 件")
    return 0


if __name__ == "__main__":
    sys.exit(main())
