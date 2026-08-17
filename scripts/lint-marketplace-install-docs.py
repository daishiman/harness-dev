#!/usr/bin/env python3
# /// script
# name: lint-marketplace-install-docs
# purpose: README の install 導線が marketplace/plugins の実体と一致するか fail-closed 検査する。
# inputs:
#   - fs: README.md
#   - fs: .claude-plugin/marketplace.json
#   - fs: marketplaces/local/.claude-plugin/marketplace.json
#   - fs: plugins/*/
#   - git: remote origin URL (WARN 判定にのみ使用)
# outputs:
#   - stdout: OK / 違反一覧
#   - exit: 0=PASS, 1=違反あり, 2=入力不備
# contexts: [A]
# network: false
# write-scope: none
# dependencies: []
# requires-python: ">=3.10"
# ///
"""README の install 導線が実体と一致することを静的検査する (fail-closed)。

なぜ必要か (= 実際に起きた事故)
------------------------------
リポジトリ名を `manju/skills` から `daishiman/harness-dev` へ変更した際、README の
`/plugin marketplace add manju/skills` が取り残された。存在しないリポジトリを指すため
利用者は marketplace を追加できず、「PR をマージしても marketplace に反映されない」
という症状として現れた。同様に plugin 改名 (`skill-creator` → `harness-creator`) でも
README の `/plugin install skill-creator@skills` が実体を失った。

version drift は `validate-plugin-completeness.py` が検査していたが、**install 導線
そのもの** (どのリポジトリを add し、どの plugin を install するか) は誰も検査して
いなかった。本 lint がその穴を塞ぐ。

SSOT の置き方
-------------
リポジトリ名の正本は `.claude-plugin/marketplace.json` の `metadata.repository` とする。
`git remote` を正本にすると fork・mirror・CI の checkout 方式でズレて誤検知するため、
remote との不一致は WARN に留め、exit code には影響させない。

検査する不変条件
----------------
- M1: README の `/plugin marketplace add <X>` の `<X>` が `metadata.repository` と一致する
      (絶対パス・`<...>` プレースホルダはローカル marketplace 手順なので対象外)。
- M2: README の `/plugin install|update|uninstall <name>@<mk>` の `<mk>` が実在する
      marketplace 名 (公開 `skills` / ローカル `harness-local`) である。
- M3: `<name>` がその marketplace の `plugins[].name` か `bundles.json` の bundle 名として実在する。
- M4: README 本文が `/plugin` コマンド以外の文脈で参照する `<plugin>:<skill>` 形式の
      スラッシュコマンドについて、`<plugin>` が `plugins/` に実在する。
"""
from __future__ import annotations

import json
import pathlib
import re
import subprocess
import sys

ROOT = pathlib.Path(__file__).resolve().parents[1]
README = ROOT / "README.md"
PUBLIC_MK = ROOT / ".claude-plugin" / "marketplace.json"
LOCAL_MK = ROOT / "marketplaces" / "local" / ".claude-plugin" / "marketplace.json"
BUNDLES = ROOT / ".claude-plugin" / "bundles.json"
PLUGINS_DIR = ROOT / "plugins"

ADD_RE = re.compile(r"/plugin\s+marketplace\s+(?:add|update|remove)\s+(\S+)")
INSTALL_RE = re.compile(r"/plugin\s+(?:install|update|uninstall)\s+([\w.-]+)@([\w.-]+)")
SLASH_RE = re.compile(r"^/([a-z0-9-]+):([a-z0-9-]+)", re.MULTILINE)


def fail_input(msg: str) -> None:
    print(f"[lint-marketplace-install-docs] 入力不備: {msg}", file=sys.stderr)
    sys.exit(2)


def load_json(path: pathlib.Path) -> dict:
    if not path.exists():
        fail_input(f"{path.relative_to(ROOT)} が存在しない")
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError as exc:
        fail_input(f"{path.relative_to(ROOT)} の解析失敗: {exc}")
    return {}


def git_remote_slug() -> str | None:
    """origin の URL から owner/repo を取り出す。取得できなければ None (WARN も出さない)。"""
    try:
        url = subprocess.run(
            ["git", "-C", str(ROOT), "remote", "get-url", "origin"],
            capture_output=True, text=True, timeout=10,
        ).stdout.strip()
    except (OSError, subprocess.SubprocessError):
        return None
    m = re.search(r"[:/]([\w.-]+)/([\w.-]+?)(?:\.git)?$", url)
    return f"{m.group(1)}/{m.group(2)}" if m else None


def is_local_marketplace_arg(arg: str) -> bool:
    """ローカル marketplace 手順の引数 (絶対パス / プレースホルダ / ローカル marketplace 名)。"""
    return arg.startswith(("/", "<", "`<", ".")) or arg.strip("`") == "harness-local"


def check_install_docs(
    text: str,
    repository: str,
    catalogs: dict[str, set[str]],
    on_disk: set[str],
) -> list[str]:
    """README 本文を検査し違反メッセージのリストを返す (純関数・I/O 非依存)。

    fs から切り離してあるのは、この lint 自身の回帰テストを合成テキストで
    書けるようにするため (test_root__lint_marketplace_install_docs.py)。
    """
    errs: list[str] = []

    for i, line in enumerate(text.splitlines(), start=1):
        # M1: marketplace add の引数
        for arg in ADD_RE.findall(line):
            arg = arg.strip("`\"'")
            if is_local_marketplace_arg(arg):
                continue
            if arg in catalogs:  # `marketplace update skills` のような marketplace 名指定
                continue
            if arg != repository:
                errs.append(
                    f"README.md:{i}: M1 `/plugin marketplace add {arg}` が実体と不一致 "
                    f"(正: {repository})"
                )

        # M2/M3: install 対象
        for name, mk in INSTALL_RE.findall(line):
            if mk not in catalogs:
                errs.append(
                    f"README.md:{i}: M2 marketplace 名 '{mk}' が実在しない "
                    f"(実在: {sorted(catalogs)})"
                )
                continue
            if name not in catalogs[mk]:
                hint = " (非配布のためローカル marketplace 経由が必要)" if name in on_disk else ""
                errs.append(
                    f"README.md:{i}: M3 '{name}' が marketplace '{mk}' に登録されていない{hint}"
                )

    # M4: 行頭スラッシュコマンドの plugin 名
    for plugin, skill in SLASH_RE.findall(text):
        if plugin not in on_disk:
            errs.append(
                f"README.md: M4 `/{plugin}:{skill}` の plugin '{plugin}' が plugins/ に実在しない"
            )

    return errs


def main() -> int:
    if not README.exists():
        fail_input("README.md が存在しない")

    text = README.read_text(encoding="utf-8")
    public = load_json(PUBLIC_MK)
    bundles = load_json(BUNDLES)

    repository = (public.get("metadata") or {}).get("repository")
    if not repository:
        fail_input(
            ".claude-plugin/marketplace.json の metadata.repository が未設定。"
            "install 導線の正本になるため <owner>/<repo> を宣言すること"
        )

    catalogs: dict[str, set[str]] = {}
    public_name = public.get("name")
    if public_name:
        catalogs[public_name] = {p["name"] for p in public.get("plugins", [])}
        catalogs[public_name] |= {b["name"] for b in bundles.get("bundles", [])}
    if LOCAL_MK.exists():
        local = load_json(LOCAL_MK)
        if local.get("name"):
            catalogs[local["name"]] = {p["name"] for p in local.get("plugins", [])}

    on_disk = {d.name for d in PLUGINS_DIR.iterdir() if d.is_dir() and not d.name.startswith(".")}

    errs = check_install_docs(text, repository, catalogs, on_disk)
    warns: list[str] = []

    slug = git_remote_slug()
    if slug and slug != repository:
        warns.append(
            f"WARN: metadata.repository ({repository}) と git remote origin ({slug}) が不一致。"
            "fork/mirror なら想定内、そうでなければどちらかが古い"
        )

    for w in warns:
        print(f"[lint-marketplace-install-docs] {w}")
    if errs:
        print(f"[lint-marketplace-install-docs] FAIL: {len(errs)} 件")
        for e in errs:
            print(f"  {e}")
        return 1
    print(
        f"[lint-marketplace-install-docs] OK: install 導線が実体と一致 "
        f"(repository={repository}, marketplace={sorted(catalogs)})"
    )
    return 0


if __name__ == "__main__":
    sys.exit(main())
