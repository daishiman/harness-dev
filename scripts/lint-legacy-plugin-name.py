#!/usr/bin/env python3
"""lint-legacy-plugin-name: 旧 plugin 固有名の再流入を fail-closed で遮断する。

2026-07-02 の plugin 改名 (skill-creator → harness-creator) 後、並行 worktree・
停滞ブランチの merge で旧固有名が能動層へ silent に復活する経路を封鎖する。
deny 対象は固有名 3 変形のみ (一般語 skill/スキル は意味論境界ルールにより合法)。

allowlist は凍結層 (履歴・別実体・エディタ状態) と、改名の説明として旧名を意図的に
言及するファイルに限定する。allowlist 追加時は reason を必ず書くこと。

外部キット (aidd-agent-kit) の原本と、その installer manifest が所有する配置済み実ファイルは
検査しない。キット内の skill-creator は Claude/Codex 組込の同名別物を指し、manifest の
SHA と一致させるため書き換えられない。symlink 経由の harness 投影は除外しない。
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
    "aidd-agent-kit/",          # 外部キットの原本 (逐語の外部由来。同名別物の skill-creator を含む)
)

# 歴史記録ファイル (path 部品一致): CHANGELOG / changelog / lessons-learned
FROZEN_PARTS = {"CHANGELOG.md", "changelog", "lessons-learned"}

# 意図的言及の許容ファイル (reason 必須)
ALLOWLIST = {
    ".beads/config.yaml": "GitHub 上で現存する repository remote の外部識別子",
    "scripts/lint-legacy-plugin-name.py": "本 lint 自身 (deny パターン定義)",
    "scripts/lint-marketplace-install-docs.py":
        "本 lint が存在する理由である実際の事故 (plugin 改名で README の "
        "install 導線が実体を失った) の歴史記述。新名へ書き換えると"
        "「何が壊れたか」が消え、検査の動機が読めなくなる",
    "tests/scripts-root/test_root__lint_marketplace_install_docs.py":
        "上記 lint の回帰テスト docstring における同じ事故の歴史記述",
    "CONVENTIONS.md": "意味論境界ルールの旧名→新名対応の説明",
    "README.md": "改名移行手順 (旧 enabledPlugins キーの案内)",
    "plugins/harness-creator/skills/ref-skill-glossary/references/terms.md":
        "ハーネス用語定義での旧名由来の説明",
    "plugins/harness-creator/README.md": "改名の経緯と移行手順",
    "doc/harness-creator-完全解剖.md":
        "harnessの対象拡大を説明するための旧名→現名の歴史的な一度きりの言及",
    "plugins/harness-creator/references/plugin-rename-checklist.md":
        "plugin 単位改名手順の恒久チェックリスト",
    "plugins/harness-creator/skills/ref-yaml-spec-fetcher/references/yaml-spec-cache.md":
        "外部 fetch した YAML spec の cache mirror (ref-yaml-spec-fetcher 自動生成)。"
        "逐語の外部由来内容で能動層でないため凍結層と同等に扱う",
    "doc/マルチ企業展開/README.md": "改名経緯 (skill-creator→harness-creator) と旧構成対応表の歴史記述",
    "doc/マルチ企業展開/構築手順.md": "harness-creator への改名経緯の説明 (旧名→新名対応の意図的言及)",
    "doc/マルチ企業展開/移管計画.md": "移管元である旧 meta-skill-creator repo 構造の歴史記述",
    "doc/マルチ企業展開/クリーンアップ計画.md":
        "実在する凍結層ディレクトリ doc/参考Skill/skill-creator/ への整理対象パス言及と"
        "旧 repo 構造の歴史記述",
}


# 外部キットの installer manifest (行形式 "<sha256>|<相対パス>") と、相対パスの配置先。
# 所有境界の正本は manifest で、ここでファイル名を二重定義しない。
# Codex 側は skills/ を .agents/skills/ へ、それ以外を .codex/ へ置く (CODEX-PLACEMENT.md)。
EXTERNAL_KIT_MANIFESTS = {
    ".claude/aidd-agent-kit.manifest": {"": ".claude"},
    ".codex/aidd-agent-kit.manifest": {"skills": ".agents", "": ".codex"},
}


def is_frozen(rel: str) -> bool:
    if rel.startswith(FROZEN_PREFIXES):
        return True
    return bool(FROZEN_PARTS & set(rel.split("/")))


def load_external_owned(root: Path) -> set[str]:
    """外部キット manifest が所有する配置済み実ファイルの root 相対パス集合を返す。

    manifest 不在は「キット未導入」として空集合。不正行は読み飛ばす。経路上に symlink を
    含むパスは harness の投影なので除外対象にしない (manifest の誤記で素通りさせない)。
    """
    owned: set[str] = set()
    for manifest, bases in EXTERNAL_KIT_MANIFESTS.items():
        path = root / manifest
        if not path.is_file():
            continue
        for line in path.read_text(encoding="utf-8").splitlines():
            relative = line.rpartition("|")[2].strip()
            parts = relative.split("/")
            if not relative or relative.startswith("/") or ".." in parts:
                continue
            rel = "/".join([bases.get(parts[0], bases[""]), *parts])
            if not _passes_symlink(root, rel):
                owned.add(rel)
    return owned


def _passes_symlink(root: Path, rel: str) -> bool:
    current = root
    for part in rel.split("/"):
        current = current / part
        if current.is_symlink():
            return True
    return False


def main() -> int:
    files = subprocess.run(
        ["git", "ls-files"], capture_output=True, text=True, cwd=ROOT, check=True
    ).stdout.splitlines()
    external_owned = load_external_owned(ROOT)
    violations: list[str] = []
    for rel in files:
        if is_frozen(rel) or rel in ALLOWLIST or rel in external_owned:
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
