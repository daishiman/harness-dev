#!/usr/bin/env python3
# /// script
# name: lint-marketplace-install-docs
# purpose: README の install 導線が marketplace/plugins の実体と一致するか fail-closed 検査する。
# inputs:
#   - fs: README.md (必須)
#   - fs: .claude-plugin/marketplace.json (必須)
#   - fs: plugins/*/ (必須)
#   - fs: marketplaces/local/.claude-plugin/marketplace.json (任意・存在時のみ)
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
- M3: `<name>` がその marketplace の `plugins[].name` として実在する。`bundles.json` はinstall scriptの入力でありnative plugin catalogではない。
- M4: README 本文が `/plugin` コマンド以外の文脈で参照する `<plugin>:<skill>` 形式の
      スラッシュコマンドについて、`<plugin>` が `plugins/` に実在する。
- M5: 同じスラッシュコマンドの `<skill>` が、その plugin の `skills/<skill>/SKILL.md`
      として実在する。plugin 改名と skill 改名は同じ事故クラスなので片方だけ守らない。

走査範囲 (2026-08-18 に反転)
---------------------------
当初はコードフェンス (```) の中を「意図的な反例を書けなくなる」という理由で除外していた。
これは検査対象を取り違えていた。README の install 手順は **ほぼ全てフェンスの中にある**
(利用者がコピペする対象なので当然そうなる) ため、除外すると M2/M3 の検査対象行が 0 になり、
docstring が「防ぐ」と明言した 2 事故を実 README 上で再現しても 1 件も検出できなかった。
除外を外しても実 README は違反 0 件のままで、誤検出回避のための除外ですらなかった。

よって既定を「全行を走査する」へ反転し、反例を書きたい場合だけ明示的に opt-out する:

- HTML コメント (`<!-- ... -->`) の中身: レンダリング後に読者へ表示されないので、
  そもそも実行手順ではない。従来どおり除外する。
- フェンスの info string に `lint-ignore` を含める (例: ```` ```text lint-ignore ````):
  そのフェンスブロック全体を除外する。壊れた例を「壊れている」と示すための正規手段。
- 行内に `lint-ignore` を含める: その 1 行だけ除外する。

opt-out を無言の既定ではなく明示マーカーにしたことで、「検査されていない行」が
README の diff 上で見えるようになる。
"""
from __future__ import annotations

import json
import pathlib
import re
import subprocess
import sys
from typing import NoReturn

ROOT = pathlib.Path(__file__).resolve().parents[1]
README = ROOT / "README.md"
PUBLIC_MK = ROOT / ".claude-plugin" / "marketplace.json"
LOCAL_MK = ROOT / "marketplaces" / "local" / ".claude-plugin" / "marketplace.json"
PLUGINS_DIR = ROOT / "plugins"

# `(\S+)` にすると和文の句読点や括弧まで引数に飲み込み、正しいリポジトリ名を書いていても
# 「daishiman/harness-dev。」として M1 が誤検出する。CI ブロッキングの lint が
# 「文章の書き方」で赤くなるのは、検査対象を取り違えている。引数として妥当な字種に絞る。
ADD_RE = re.compile(r"/plugin\s+marketplace\s+(?:add|update|remove)\s+([`'\"]?[\w./~<>-]+[`'\"]?)")
INSTALL_RE = re.compile(r"/plugin\s+(?:install|update|uninstall)\s+([\w.-]+)@([\w.-]+)")
# 走査の入口は「行頭」と「インラインコード span の先頭」。バッククォート直後だけを足す
# 場当たり対応では `**/x:y**` や散文中のベタ書きを取りこぼしたままになるので、
# インラインコードを span として抜き出したうえで、素の本文も併せて見る。
# 先頭の否定後読みが無いと URL パス (`https://x.com/foo:bar`) や日付・時刻の記録
# (`2026/08:17`) を M4 として拾い、README に URL を 1 本書いただけで CI が赤くなる。
# スラッシュコマンドは行頭・空白・記号の直後にしか現れないので、直前が識別子文字や
# `/` `:` `.` `-` のときは除外する。skill 名側も英字始まりに限って数値を弾く。
SLASH_RE = re.compile(r"(?<![\w./:-])/([a-z][a-z0-9-]*):([a-z][a-z0-9-]*)")
INLINE_CODE_RE = re.compile(r"`([^`\n]+)`")
FENCE_RE = re.compile(r"^\s*(?P<marker>`{3,}|~{3,})(?P<info>.*)$")
HTML_COMMENT_RE = re.compile(r"<!--.*?-->", re.DOTALL)
# 明示 opt-out マーカー。フェンスの info string に置けばブロック全体、
# 行内に置けばその 1 行だけを走査から外す。
IGNORE_MARKER = "lint-ignore"


def fail_input(msg: str) -> NoReturn:
    print(f"[lint-marketplace-install-docs] 入力不備: {msg}", file=sys.stderr)
    sys.exit(2)


def load_json(path: pathlib.Path) -> dict:
    """必須 JSON を読む。読めない・object でないものは入力不備 (exit 2) とする。"""
    if not path.exists():
        fail_input(f"{path.relative_to(ROOT)} が存在しない")
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError as exc:
        fail_input(f"{path.relative_to(ROOT)} の解析失敗: {exc}")
    if not isinstance(data, dict):
        fail_input(f"{path.relative_to(ROOT)} の top-level が object ではない")
    return data


def catalog_names(entries: object, source: str) -> set[str]:
    """Marketplace `plugins[]` から name を集める。形が違えば入力不備 (exit 2)。

    `e["name"]` を直接引くと、name 欠落という「JSON としては妥当だが契約違反」の
    入力で KeyError の traceback → exit 1 (=違反あり) になり、宣言した exit 2 と食い違う。
    """
    if not isinstance(entries, list):
        fail_input(f"{source} が配列ではない")
    names = set()
    for e in entries:
        if not isinstance(e, dict) or not isinstance(e.get("name"), str):
            fail_input(f"{source} の要素に文字列の name がない: {e!r}")
        names.add(e["name"])
    return names


def git_remote_slug() -> str | None:
    """origin の URL から owner/repo を取り出す。取得できなければ None (WARN も出さない)。"""
    try:
        proc = subprocess.run(
            ["git", "-C", str(ROOT), "remote", "get-url", "origin"],
            capture_output=True, text=True, timeout=10,
        )
    except (OSError, subprocess.SubprocessError):
        return None
    if proc.returncode != 0:
        # 失敗を黙って None にすると「WARN が出ないのは一致しているから」と読めてしまう。
        print(
            f"[lint-marketplace-install-docs] WARN: git remote を取得できませんでした "
            f"(rc={proc.returncode}): {proc.stderr.strip()}"
        )
        return None
    m = re.search(r"[:/]([\w.-]+)/([\w.-]+?)(?:\.git)?$", proc.stdout.strip())
    return f"{m.group(1)}/{m.group(2)}" if m else None


def scanned_lines(text: str) -> tuple[list[tuple[int, str]], list[str]]:
    """(走査対象の行, opt-out 自体の異常) を返す。行番号は元テキストのものを保つ。

    既定は全行。除外するのは HTML コメントの中身と、明示 `lint-ignore` マーカーで
    opt-out された行 / フェンスブロックだけ (理由は module docstring 参照)。

    opt-out は「検査を止める」機能なので、その使い方自体を検査しないと穴になる。
    閉じ忘れた ```` ```text lint-ignore ```` は以降の全行を無言で除外でき、
    README 末尾まで検査が消えても緑のままになる (実測で再現)。よって未閉のまま
    EOF に達した除外フェンスは違反として報告する。
    """
    # HTML コメントは複数行にまたがるので、行数を保ったまま中身だけ潰す。
    masked = HTML_COMMENT_RE.sub(lambda m: "\n" * m.group(0).count("\n"), text)
    out: list[tuple[int, str]] = []
    problems: list[str] = []
    fence_ignored: bool | None = None  # None = フェンス外
    fence_marker: str = ""             # 開きフェンスの記号列 (``` / ~~~~ など)
    fence_line = 0
    for i, line in enumerate(masked.splitlines(), start=1):
        m = FENCE_RE.match(line)
        if m:
            marker, info = m.group("marker"), m.group("info")
            if fence_ignored is None:
                # 開きフェンス。info string を見てこのブロックを除外するか決める。
                fence_ignored = IGNORE_MARKER in info
                fence_marker, fence_line = marker, i
                continue
            # フェンス内。同種で開きと同じ長さ以上の記号列だけを閉じフェンスとみなす。
            # 単純トグルにすると、除外ブロック内に現れた別種のフェンス行で
            # 除外が早期終了し、以降が意図せず検査対象へ戻る。
            if marker[0] == fence_marker[0] and len(marker) >= len(fence_marker) and not info.strip():
                fence_ignored = None
                fence_marker, fence_line = "", 0
            continue
        if fence_ignored:
            continue
        if IGNORE_MARKER in line:
            continue
        out.append((i, line))
    if fence_ignored:
        problems.append(
            f"README.md:{fence_line}: `{IGNORE_MARKER}` フェンスが閉じられていません。"
            "以降の全行が無言で検査対象から外れます"
        )
    return out, problems


def slash_commands(line: str) -> list[tuple[str, str]]:
    """1 行から `<plugin>:<skill>` 形式のスラッシュコマンドを拾う。

    インラインコード span (`` `...` ``) の中と、素の本文の両方を走査する。
    """
    found: list[tuple[str, str]] = []
    for span in INLINE_CODE_RE.findall(line):
        found.extend(SLASH_RE.findall(span))
    found.extend(SLASH_RE.findall(INLINE_CODE_RE.sub(" ", line)))
    # 同一行に同じ参照が素と code span の両方で出ることは無いが、重複は潰しておく。
    return list(dict.fromkeys(found))


def is_local_marketplace_arg(arg: str) -> bool:
    """ローカル marketplace 手順の引数 (絶対パス / プレースホルダ / ローカル marketplace 名)。"""
    return arg.startswith(("/", "<", "`<", ".")) or arg.strip("`") == "harness-local"


def check_install_docs(
    text: str,
    repository: str,
    catalogs: dict[str, set[str]],
    on_disk: set[str],
    skills: dict[str, set[str]] | None = None,
) -> list[str]:
    """README 本文を検査し違反メッセージのリストを返す (純関数・I/O 非依存)。

    fs から切り離してあるのは、この lint 自身の回帰テストを合成テキストで
    書けるようにするため (test_root__lint_marketplace_install_docs.py)。

    skills は {plugin 名: その plugin が持つ skill 名の集合}。省略時は M5 を行わない。
    """
    errs: list[str] = []
    skills = skills or {}

    scanned, problems = scanned_lines(text)
    errs.extend(problems)
    for i, line in scanned:
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

        # M4/M5: スラッシュコマンドの plugin 名と skill 名
        # M1-M3 と同じ行単位で回し、違反メッセージに行番号を載せる (粒度を揃える)。
        for plugin, skill in slash_commands(line):
            if plugin not in on_disk:
                errs.append(
                    f"README.md:{i}: M4 `/{plugin}:{skill}` の plugin '{plugin}' が"
                    " plugins/ に実在しない"
                )
            elif plugin in skills and skill not in skills[plugin]:
                errs.append(
                    f"README.md:{i}: M5 `/{plugin}:{skill}` の skill '{skill}' が"
                    f" plugins/{plugin}/skills/ に実在しない"
                )

    return errs


def main() -> int:
    if not README.exists():
        fail_input("README.md が存在しない")

    text = README.read_text(encoding="utf-8")
    public = load_json(PUBLIC_MK)

    repository = (public.get("metadata") or {}).get("repository")
    if not repository:
        fail_input(
            ".claude-plugin/marketplace.json の metadata.repository が未設定。"
            "install 導線の正本になるため <owner>/<repo> を宣言すること"
        )

    catalogs: dict[str, set[str]] = {}
    public_name = public.get("name")
    # name 欠落を素通りさせると catalogs が空になり、M2 が「実在する marketplace 名が
    # 1 つも無い」状態で全 install 行を違反として吐くか、install 行が無ければ静かに
    # 緑になる。どちらも検査として意味を成さないので入力不備 (exit 2) で止める。
    if not isinstance(public_name, str) or not public_name:
        fail_input(
            ".claude-plugin/marketplace.json の name が未設定。"
            "install 導線の marketplace 名の正本になるため必須"
        )
    if public_name:
        catalogs[public_name] = catalog_names(
            public.get("plugins", []), ".claude-plugin/marketplace.json の plugins"
        )
    if LOCAL_MK.exists():
        local = load_json(LOCAL_MK)
        local_name = local.get("name")
        # 公開側と同じ理由で入力不備にする。ここだけ「name が無ければ黙って飛ばす」に
        # すると、ローカル marketplace 名が catalogs から欠けたまま M2 が走り、
        # 正しい `@harness-local` を「実在しない marketplace」として違反報告する
        # (exit 1 + 濡れ衣の M2)。壊れているのは README ではなく入力なので exit 2 が正しい。
        if not isinstance(local_name, str) or not local_name:
            fail_input(
                f"{LOCAL_MK.relative_to(ROOT)} の name が未設定。"
                "ローカル install 導線の marketplace 名の正本になるため必須"
            )
        catalogs[local_name] = catalog_names(
            local.get("plugins", []), f"{LOCAL_MK.relative_to(ROOT)} の plugins"
        )

    # iterdir() は plugins/ 不在で FileNotFoundError を投げる。捕まえないと
    # traceback + exit 1 (=違反あり) になり、宣言した exit 2 (=入力不備) と食い違う。
    if not PLUGINS_DIR.is_dir():
        fail_input(f"plugins/ が存在しない: {PLUGINS_DIR}")

    on_disk = {d.name for d in PLUGINS_DIR.iterdir() if d.is_dir() and not d.name.startswith(".")}
    # skill の実在は SKILL.md の有無で判定する (ディレクトリだけの抜け殻を実在扱いしない)。
    skills = {
        name: {
            s.name
            for s in (PLUGINS_DIR / name / "skills").iterdir()
            if (s / "SKILL.md").is_file()
        }
        for name in on_disk
        if (PLUGINS_DIR / name / "skills").is_dir()
    }

    errs = check_install_docs(text, repository, catalogs, on_disk, skills)
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
