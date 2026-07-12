#!/usr/bin/env python3
"""marketplace 配布 plugin のユーザー向け文書のコマンド例が install 位置に依存しないことを静的検査する (fail-closed)。

検証する不変条件:
  marketplace 配布対象 plugin の **ユーザー向け文書** (README.md +
  `references/*-setup.md` 等の setup 手順) 内の bash/sh コードフェンス
  (= 導入者が素のターミナルへコピー&ペーストしうるコマンド) は、install 位置に
  依存して壊れる記法を **一次手順として** 含んではならない。

なぜ (= 生ターミナル空展開の恒久防止):
  `$CLAUDE_PLUGIN_ROOT` は Claude Code の実行環境でのみ定義される変数である。
  README の bash/sh フェンスに 裸 `"$CLAUDE_PLUGIN_ROOT/..."` や repo 相対
  `python3 plugins/<name>/...` を一次手順として置くと、marketplace install した
  ユーザーがそれを素のターミナルへ貼ったとき `$CLAUDE_PLUGIN_ROOT` が空文字へ展開し、
  パス先頭が `/lib/...` になって `can't open file '/lib/...'` で壊れる
  (mf-kessai で実際に発生した事故)。本 lint はこの空展開事故の恒久再発防止器。
  README だけでなく `references/*-setup.md` 等の setup 手順も走査するため、
  company-master elegant-review の deferred 「文書層 repo 相対コマンド検出 lint」を
  実際に回収する (company-master の setup 手順は references 配下に置かれるため、
  README のみの走査では被覆できなかった)。

許可 (robust):
  - fallback 形 `${CLAUDE_PLUGIN_ROOT:-plugins/<name>}/...` (`:-` を含む。
    `P="${CLAUDE_PLUGIN_ROOT:-plugins/<name>}"` へ代入し `"$P/..."` 参照する形も可)。
  - 裸 `"$CLAUDE_PLUGIN_ROOT/..."` は、**同一コードフェンス内に開発者補足注記行
    (「開発者」または「clone」を含むコメント/文) がある場合のみ** 許可
    (clone 開発者向けデバッグの降格温存)。
  - Python の `os.environ.get("CLAUDE_PLUGIN_ROOT") or "<fallback>"`。
  - 一次セットアップ導線としての doctor 委譲 (`/run-...-doctor` / 自然文) は
    そもそもコマンド例ではないため対象外。

禁止 (fragile):
  - repo 相対直書き `python3 plugins/<name>/...` (bash/sh フェンス内のどこでも。
    開発者補足注記があっても不可 — fallback 形なら clone 開発者でも同一挙動で通る)。
    `python3 -u plugins/<name>/...` や `uv run python plugins/<name>/...` も同じく不可。
  - 一次手順の裸 `"$CLAUDE_PLUGIN_ROOT/..."` (fallback も開発者補足注記も無いもの)。
  - `P="$CLAUDE_PLUGIN_ROOT"` のような裸 root 代入後に `"$P/lib/..."` を叩く二段展開。
  - Python の `os.environ["CLAUDE_PLUGIN_ROOT"]` (未定義時 KeyError を誘発)。

検査対象 (ユーザー向け文書 = 導入者が手順として読み bash をコピペしうる):
  次の glob に一致する doc の bash/sh (shell/zsh/console) コードフェンス、及び
  python コードフェンス (os.environ 添字検査用):
    - `plugins/*/README.md`                        (常にユーザー向け)
    - `plugins/*/references/*setup*.md`            (setup 手順。例: README-setup.md /
                                                    keychain-setup.md / oauth-setup.md)
    - `plugins/*/skills/*/references/*setup*.md`   (skill 内 setup 手順)
  これらは開発者補足を **引用付きフェンス (`> ```bash`)** でも書くため、
  引用/非引用の両コードフェンスを走査する。`distributable: false` の plugin
  (prompt-creator 等の clone 専用開発ツール・marketplace 配布対象外) は
  repo 相対で正しいため検査対象外にする。

検査対象外 (Claude Code 注入文脈で `$CLAUDE_PLUGIN_ROOT` が正しく解決される):
  `plugins/*/.claude-plugin/plugin.json` の `hooks[].command` /
  `plugins/*/skills/*/SKILL.md` / `plugins/*/skills/*/prompts/*.md` /
  `*setup*.md` 命名でない reference (execution-contract.md / hook-wiring.md /
  build-steps.md 等の LLM・開発者向け仕様) 等。これらは走査 glob に入らない。
  また文書本文の散文 (blockquote / 段落 / 表) の inline code も、コピペ対象の
  コマンドフェンスではないため対象外 (fence 内のみを走査する)。

Usage:
  lint-readme-plugin-root-portability.py [--repo-root /path/to/repo]

Exit 0 = ok, 1 = violation, 2 = usage error。
"""
from __future__ import annotations

import json
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent

# コードフェンスの開始/終了。CommonMark に従い先頭 0-3 スペースのインデントを許容する
# (番号付きリストの手順内に ` ```bash ` を 3 スペース字下げして置く書き方を取りこぼさない。
# 行頭固定だと list-nested fence が丸ごと不可視になり壊れるコマンドが素通りする)。
# group(1)=インデント空白 / group(2)=info string の言語。
FENCE_RE = re.compile(r"^( {0,3})`{3,}\s*([A-Za-z0-9_+.-]*)\s*$")
# 素のターミナルへ貼りうる shell 系フェンス。
SHELL_LANGS = {"bash", "sh", "shell", "zsh", "console", "shell-session"}
# os.environ 添字検査を行う python 系フェンス (bash heredoc 内の python は shell 側で拾う)。
PY_LANGS = {"python", "py", "python3"}

# 検査対象 doc の glob。README (常にユーザー向け) + ユーザー向け setup 手順
# (references 配下の *setup*.md。marketplace 導入者が手順として読み bash を素の
# ターミナルへコピペしうる)。LLM/開発者向け reference (execution-contract.md /
# hook-wiring.md / build-steps.md 等) は *setup*.md 命名でないため対象外
# (それらは Claude Code 注入文脈で $CLAUDE_PLUGIN_ROOT が解決され裸で正しい)。
TARGET_DOC_GLOBS = (
    "plugins/*/README.md",
    "plugins/*/references/*setup*.md",
    "plugins/*/skills/*/references/*setup*.md",
)

# 裸パス使用: `$CLAUDE_PLUGIN_ROOT/` / `${CLAUDE_PLUGIN_ROOT}/` (直後が `/` の path 使用)。
# fallback 形 `${CLAUDE_PLUGIN_ROOT:-...}` は `CLAUDE_PLUGIN_ROOT` の直後が `:-` のため
# どちらのパターンにも一致しない (= 許可)。コメント中の説明的言及
# 「$CLAUDE_PLUGIN_ROOT 未定義なら…」(直後が空白) も一致しない。
BARE_ROOT_RE = re.compile(r"\$CLAUDE_PLUGIN_ROOT/|\$\{CLAUDE_PLUGIN_ROOT\}/")
# repo 相対直書き: python(3) / uv run python が (任意の option / `./` 付き)
# `plugins/<name>/` を直接叩く。`python3 -u plugins/demo/foo.py` も検出する。
REPO_RELATIVE_RE = re.compile(
    r"\b(?:uv\s+run\s+)?python3?(?:\s+-[A-Za-z0-9][^\s]*)*\s+[\"']?(?:\./)?plugins/[A-Za-z0-9_.-]+/"
)
# KeyError 誘発の os.environ 添字アクセス (`.get(...)` は一致しない)。
OSENV_SUBSCRIPT_RE = re.compile(r"os\.environ\[\s*[\"']CLAUDE_PLUGIN_ROOT[\"']\s*\]")
# 裸 root 代入: P="$CLAUDE_PLUGIN_ROOT" / ROOT=${CLAUDE_PLUGIN_ROOT} など。
# fallback 形 `${CLAUDE_PLUGIN_ROOT:-...}` は一致しない。
BARE_ROOT_ASSIGN_RE = re.compile(
    r"^\s*([A-Za-z_][A-Za-z0-9_]*)=(?:[\"']?\$CLAUDE_PLUGIN_ROOT[\"']?|[\"']?\$\{CLAUDE_PLUGIN_ROOT\}[\"']?)\s*$"
)
# 開発者補足注記 (裸変数の降格温存を許可する印)。
DEV_NOTE_RE = re.compile(r"開発者|clone")

BLOCKQUOTE_RE = re.compile(r"^\s*(?:>\s?)+")

KIND_MESSAGE = {
    "repo-relative": (
        "repo 相対直書き (`python3 plugins/<name>/...`) は marketplace install 先の "
        "作業フォルダに `plugins/` が無く壊れる。`${CLAUDE_PLUGIN_ROOT:-plugins/<name>}/...` "
        "の fallback 形へ (clone 開発者でも素のターミナルで同一挙動)。"
    ),
    "bare-var": (
        "一次手順の裸 `$CLAUDE_PLUGIN_ROOT/...` は素のターミナルで空文字展開し先頭が "
        "`/...` になって壊れる。`${CLAUDE_PLUGIN_ROOT:-plugins/<name>}/...` の fallback 形へ、"
        "または同一コードフェンス内に開発者補足注記 (「開発者」/「clone」) を添える。"
    ),
    "bare-var-alias": (
        "`P=\"$CLAUDE_PLUGIN_ROOT\"` のような裸 root 代入後の `\"$P/...\"` は、"
        "素のターミナルで同じく空展開して壊れる。"
        "`P=\"${CLAUDE_PLUGIN_ROOT:-plugins/<name>}\"` の fallback 形へ。"
    ),
    "os-environ-subscript": (
        "`os.environ[\"CLAUDE_PLUGIN_ROOT\"]` は未定義時 KeyError で壊れる。"
        "`os.environ.get(\"CLAUDE_PLUGIN_ROOT\") or \"<fallback>\"` へ。"
    ),
}

# 例外宣言: {(plugin名, 行に含まれる部分文字列): 理由 (非空必須)}。
# 「なぜ是正できない正当な裸変数/相対パスか」と検出日を残し後日是正を追跡する。
# 現状は空 (全 plugin を fallback 形/開発者補足注記で是正済み)。安易に使わず是正を優先する。
# 該当違反が消えた stale エントリ・空理由エントリはエラー (掃除を強制)。
ALLOWLIST: dict[tuple[str, str], str] = {}


def _strip_blockquote(line: str) -> str:
    """先頭の blockquote マーカー (`> `、ネスト可) を除去する。

    README は開発者補足を引用付きフェンス (`> ```bash`) でも書くため、引用を剥がして
    から非引用フェンスと同一ロジックで走査する。非引用行は素通り (無変換)。
    """
    return BLOCKQUOTE_RE.sub("", line)


def iter_code_fences(text: str) -> list[tuple[str, list[tuple[int, str]]]]:
    """(言語, [(行番号, 内容行), ...]) を返す。引用/非引用・インデント両フェンスに対応。"""
    fences: list[tuple[str, list[tuple[int, str]]]] = []
    in_fence = False
    lang = ""
    indent = 0
    buf: list[tuple[int, str]] = []
    for lineno, raw in enumerate(text.splitlines(), start=1):
        stripped = _strip_blockquote(raw)
        m = FENCE_RE.match(stripped)
        if m:
            if not in_fence:
                in_fence = True
                indent = len(m.group(1))
                lang = m.group(2).lower()
                buf = []
            else:
                fences.append((lang, buf))
                in_fence = False
                lang = ""
                indent = 0
                buf = []
        elif in_fence:
            # 開始フェンスの字下げ分 (0-3 スペース) だけ content 先頭空白を除去する
            # (CommonMark: fenced code の content は開始 fence のインデント分だけ剥がされる)。
            j = 0
            while j < indent and j < len(stripped) and stripped[j] == " ":
                j += 1
            buf.append((lineno, stripped[j:]))
    # 未閉フェンスは安全側で無視 (README 末尾の破損時に誤検出しない)。
    return fences


def _matching_allowlist_key(
    plugin: str, content: str, allowlist: dict[tuple[str, str], str]
) -> tuple[str, str] | None:
    for (p, sig) in allowlist:
        if p == plugin and sig in content:
            return (p, sig)
    return None


def check_readme_text(
    text: str,
    plugin_name: str,
    allowlist: dict[tuple[str, str], str] | None = None,
    used: set[tuple[str, str]] | None = None,
) -> list[tuple[int, str, str]]:
    """1 README の本文を検査し (行番号, 種別, 該当行) の違反リストを返す (空なら PASS)。"""
    allowlist = ALLOWLIST if allowlist is None else allowlist
    violations: list[tuple[int, str, str]] = []
    for lang, buf in iter_code_fences(text):
        is_shell = lang in SHELL_LANGS
        is_py = lang in PY_LANGS
        if not (is_shell or is_py):
            continue
        # 開発者補足注記の有無はフェンス単位で判定する (「同一コードフェンス内」規約)。
        has_dev_note = any(DEV_NOTE_RE.search(c) for _, c in buf)
        bare_aliases = set()
        if is_shell:
            for _, content in buf:
                m = BARE_ROOT_ASSIGN_RE.match(content)
                if m:
                    bare_aliases.add(m.group(1))
        for lineno, content in buf:
            kinds: list[str] = []
            # os.environ 添字は shell heredoc / python 双方で誘発するため両フェンスで検査。
            if OSENV_SUBSCRIPT_RE.search(content):
                kinds.append("os-environ-subscript")
            if is_shell:
                if REPO_RELATIVE_RE.search(content):
                    kinds.append("repo-relative")
                elif BARE_ROOT_RE.search(content) and not has_dev_note:
                    kinds.append("bare-var")
                if bare_aliases and any(re.search(rf"\$\{{?{re.escape(alias)}\}}?/", content) for alias in bare_aliases):
                    if not BARE_ROOT_ASSIGN_RE.match(content):
                        kinds.append("bare-var-alias")
            if not kinds:
                continue
            hit = _matching_allowlist_key(plugin_name, content, allowlist)
            if hit is not None:
                if used is not None:
                    used.add(hit)
                continue
            for kind in kinds:
                violations.append((lineno, kind, content.strip()))
    return violations


def iter_target_docs(root: Path) -> list[Path]:
    """検査対象 doc (README + ユーザー向け setup 手順) を重複なく決定順で返す。"""
    seen: set[Path] = set()
    docs: list[Path] = []
    for pat in TARGET_DOC_GLOBS:
        for p in sorted(root.glob(pat)):
            if p not in seen:
                seen.add(p)
                docs.append(p)
    return sorted(docs)


def plugin_dir_of(root: Path, doc: Path) -> Path:
    """doc path (plugins/<name>/...) から所属 plugin ディレクトリを取り出す。

    setup 手順は `plugins/<name>/references/…` や `plugins/<name>/skills/<skill>/…`
    と入れ子になるため、`doc.parent` ではなく path 先頭の `plugins/<name>` を採る。
    """
    parts = doc.relative_to(root).parts  # ("plugins", "<name>", ...)
    return root / parts[0] / parts[1]


def is_distributable(plugin_dir: Path) -> bool:
    """plugin.json の `distributable` が明示的に false でない限り配布対象とみなす。"""
    pj = plugin_dir / ".claude-plugin" / "plugin.json"
    if not pj.is_file():
        return True
    try:
        data = json.loads(pj.read_text(encoding="utf-8"))
    except Exception:
        return True
    return data.get("distributable") is not False


def check_repo(
    root: Path, allowlist: dict[tuple[str, str], str] | None = None
) -> tuple[list[str], list[str]]:
    """(errors, report) を返す。errors 空 = 合格。"""
    allowlist = ALLOWLIST if allowlist is None else allowlist
    errors: list[str] = []
    report: list[str] = []
    used: set[tuple[str, str]] = set()

    # allowlist 健全性: 理由は非空必須。
    for (plugin, sig), reason in allowlist.items():
        if not str(reason).strip():
            errors.append(
                f"[allowlist] ({plugin}, {sig!r}) に理由が無い (理由必須)"
            )

    for doc in iter_target_docs(root):
        plugin_dir = plugin_dir_of(root, doc)
        plugin_name = plugin_dir.name
        rel = doc.relative_to(root)
        if not is_distributable(plugin_dir):
            report.append(f"{rel}: skip (distributable:false — clone 専用)")
            continue
        text = doc.read_text(encoding="utf-8")
        found = check_readme_text(text, plugin_name, allowlist, used)
        for lineno, kind, snippet in found:
            errors.append(
                f"{rel}:{lineno}: [{kind}] {KIND_MESSAGE[kind]}\n"
                f"      該当: {snippet}"
            )
        report.append(f"{rel}: {'OK' if not found else f'{len(found)} 件 FAIL'}")

    # stale allowlist: 該当違反が発生しなかったエントリは掃除を強制。
    for key in set(allowlist) - used:
        errors.append(
            f"[allowlist] {key} は該当違反が無い (stale)。"
            "scripts/lint-readme-plugin-root-portability.py の ALLOWLIST から削除すること"
        )

    return errors, report


def main(argv: list[str]) -> int:
    root = ROOT
    args = list(argv)
    if "--repo-root" in args:
        idx = args.index("--repo-root")
        if idx + 1 >= len(args):
            print(
                "usage: lint-readme-plugin-root-portability.py [--repo-root /path]",
                file=sys.stderr,
            )
            return 2
        root = Path(args[idx + 1]).resolve()
    if not (root / "plugins").is_dir():
        print(f"plugins/ not found under: {root}", file=sys.stderr)
        return 2

    errors, report = check_repo(root)
    for line in report:
        print(f"  {line}")
    if errors:
        sys.stderr.write("[lint-readme-plugin-root-portability] FAIL\n")
        for e in errors:
            sys.stderr.write(f"  - {e}\n")
        return 1
    checked = sum(1 for line in report if not line.endswith("clone 専用)"))
    print(
        f"[lint-readme-plugin-root-portability] OK: ユーザー向け文書 {checked} 件が "
        "install 位置非依存 (裸 $CLAUDE_PLUGIN_ROOT / repo 相対直書き / os.environ 添字なし)"
    )
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
