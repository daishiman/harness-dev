#!/usr/bin/env python3
# /// script
# name: lint-rubric-refs-exist
# version: 0.4.0
# purpose: SKILL.md frontmatter の rubric_refs と rubric-registry.json の rubrics[].rubric・upstream が物理存在することを検証する
# inputs:
#   - argv[1..]: 検査対象 SKILL.md パス (省略時は plugins/*/skills/*/SKILL.md と .claude/skills/*/SKILL.md を走査し、
#     実体のパスで重複を除く。.claude/skills には他 plugin の skill の symlink も入る)
#   - -h / --help: 使い方を表示して exit 0 (どの位置にあっても)。ほかの `-` で始まる引数は exit 2
# outputs:
#   - stdout: 検査結果サマリ
#   - stderr: FAIL の内訳、理由つきで免除した未解決の参照、rubric-registry.json が無いときの警告
#   - exit code: 0=PASS / 1=FAIL (未解決 rubric_refs・ファイルでない参照先・空の要素・list でない rubric_refs・
#     glob 記号などを含む ref 名・リポジトリ外や NUL を含む参照・空や文字列でない registry のパス・
#     使われなくなった EXEMPT_UNRESOLVED を検出) /
#     2=入力不正 (指定した SKILL.md が無い、未知の option、走査対象が0件、SKILL.md や registry を読めない・
#     形が違う (rubrics が list でない、要素が object でない、domain・rubric が無い、upstream が list でない))
# requires-python: ">=3.9"
# dependencies: []
# contexts: [C, E]
# network: false
# write-scope: none
# ///
"""rubric_refs の参照先が物理存在するかを CI / pre-commit で検証する。設計書29 §6.3 fail-fast を機械実装。

rubric_refs はブロック形式 (`- x`、インデントは問わない) とフロー形式 (`[x, y]`。複数行にわたってもよい)
の list を読む。`null` と `~` は YAML と同じく「参照なし」として読む。list でないスカラや mapping、空の要素
(`- ""` や `[a, , b]`。最後の要素の後の `,` は YAML と同じく許す)、`-x` のように項目として読めない行は、
参照を黙って読み飛ばさないよう FAIL にする。参照先はリポジトリの中のファイルであることを確かめる
(ディレクトリ・repo 外・NUL を含むパスは不可)。
`ref-` で始まる名前は glob に埋めて探すので、名前に使える文字を英数字と `._-` に限る (`ref-*` が
実在する別の ref に一致して PASS するのを防ぐ)。ref として見つからず、SKILL.md の隣に同じ名前のファイル
(`ref-notes.json` など) があれば、そのローカルのファイルを参照先にする。BOM・CRLF・閉じの `---` の後に
改行が無い書き方、`rubric_refs :` のようにキーの後に空白がある書き方、引用符つきのキー、キー行末のコメント
(引用符の中の `#` はコメントにしない) も読む。

既定の走査は全 plugin を対象にする。guide-doc-generator の assign-handout-readability-evaluator だけは、
rubric.json を持たない ref-handout-design-system を rubric_refs に書くことが plan
(component-inventory.json・skill-brief-C03.json。r4-evaluation.json で hash 固定) と契約 test (AC-C03-17)
で決められているので、その (skill, ref) の1組だけを EXEMPT_UNRESOLVED で理由つきで免除する。
免除は未解決の参照にだけ効き、ref 名の形や repo 外の検査は免除しない。免除した SKILL.md を走査したのに、
その ref が未解決でなくなった (rubric.json が足された、rubric_refs から外された) ときは、免除が古いので FAIL にする。
"""
from __future__ import annotations

import json
import os
import re
import sys
from pathlib import Path

PROJECT_ROOT = Path(os.environ.get("PROJECT_ROOT", os.getcwd())).resolve()
REGISTRY_REL = Path("plugins") / "skill-governance-config" / "config" / "rubric-registry.json"
REF_NAME = re.compile(r"ref-[A-Za-z0-9._-]+")

# 未解決でも FAIL にしない (SKILL.md の repo 相対パス, ref) の組と、その理由。plan を改訂したら外す
EXEMPT_UNRESOLVED = {
    ("plugins/guide-doc-generator/skills/assign-handout-readability-evaluator/SKILL.md",
     "ref-handout-design-system"):
        "plan (skill-brief-C03.json・component-inventory.json) と契約 test (AC-C03-17) が、"
        "rubric.json を持たない設計 system の参照として rubric_refs に書くことを決めている",
}


def _opens_quote(text: str, i: int) -> bool:
    """text[i] の引用符がスカラの始まりか (行頭、空白・`[`・`,` の直後)。`don't` の `'` は始まりでない。"""
    return text[i] in ("'", '"') and (i == 0 or text[i - 1] in " \t[,")


def strip_comment(raw: str) -> str:
    """引用符の外の行末コメント (` #` 以降、または先頭の `#`) を外す。"""
    quote = None
    for i, ch in enumerate(raw):
        if quote:
            if ch == quote:
                quote = None
        elif _opens_quote(raw, i):
            quote = ch
        elif ch == "#" and (i == 0 or raw[i - 1] in " \t"):
            return raw[:i].strip()
    return raw.strip()


def parse_scalar(raw: str) -> str:
    """YAML のスカラ1つを読む。

    引用符 ('...' / "...") で囲まれていれば中身を返す。YAML として正しい
    `- "../../lib/x.py"` を引用符ごとパスにすると、存在するファイルを NOT FOUND と誤報する
    (harness-aor)。引用符の外の行末コメント (` #` 以降、または値の先頭の `#`) は外す。
    パスに現れないエスケープ ('' や \\") は扱わない。
    """
    s = raw.strip()
    if s[:1] in ("'", '"'):
        end = s.find(s[0], 1)
        if end > 0:
            return s[1:end]
    return strip_comment(s)


def parse_key(raw: str) -> str:
    """mapping のキーを読む。`"rubric_refs"` のような引用符つきのキーも YAML では同じキー。"""
    k = raw.strip()
    if len(k) >= 2 and k[0] in ("'", '"') and k[-1] == k[0]:
        return k[1:-1]
    return k


def _split_flow_items(inner: str) -> list:
    """`,` で分ける。引用符の中の `,` では分けない。"""
    items, buf, quote = [], "", None
    for ch in inner:
        if quote:
            if ch == quote:
                quote = None
        elif ch in ("'", '"') and not buf.strip():
            quote = ch
        elif ch == ",":
            items.append(buf)
            buf = ""
            continue
        buf += ch
    items.append(buf)
    return items


def parse_flow_list(value: str) -> list | None:
    """`[a, "b"]` の flow 形式の list を読む。flow 形式でなければ None。

    空の要素 (`[a, , b]`) は "" として残し、呼び出し側が FAIL にする。最後の要素の後の `,` (`[a, b,]`) は
    YAML が許すので要素にしない。
    """
    if not (value.startswith("[") and value.endswith("]")):
        return None
    inner = value[1:-1].strip()
    if not inner:
        return []
    items = _split_flow_items(inner)
    if len(items) > 1 and not items[-1].strip():
        items.pop()
    return [parse_scalar(item) for item in items]


NULL_SCALARS = ("~", "null", "Null", "NULL")


def find_frontmatter(skill_md: Path) -> dict:
    """frontmatter のトップレベルのキーを読む。`null`・`~` (引用符なし) は None にする。"""
    text = skill_md.read_text(encoding="utf-8-sig")
    m = re.match(r"^---[ \t]*\r?\n(.*?)\r?\n---[ \t]*(?:\r?\n|$)", text, re.DOTALL)
    if not m:
        return {}
    fm = {}
    current_key = None
    flow_key, flow_buf = None, ""
    for line in m.group(1).splitlines():
        if not line.strip() or line.lstrip().startswith("#"):
            continue
        if flow_key is not None:
            # 複数行にわたる flow 形式の list。`]` で閉じるまで行をつなぐ
            flow_buf += " " + strip_comment(line)
            if flow_buf.endswith("]"):
                fm[flow_key] = parse_flow_list(flow_buf)
                flow_key = None
            continue
        item = re.match(r"^\s*-(?:\s+(.*))?$", line)
        if item and current_key:
            fm[current_key].append(parse_scalar(item.group(1) or ""))
        elif current_key and (line[:1] in (" ", "\t") or line.startswith("-")):
            # `key:` の下が list でなく mapping のとき、または `-x` のように項目として読めないとき。
            # list として読めないことを値に残す
            fm[current_key] = line.strip()
            current_key = None
        elif ":" in line and line[:1] not in (" ", "\t"):
            k, _, v = line.partition(":")
            k = parse_key(k)
            raw = strip_comment(v)
            current_key = None
            if raw == "":
                fm[k] = []
                current_key = k
            elif raw in NULL_SCALARS:
                fm[k] = None
            elif raw.startswith("[") and not raw.endswith("]"):
                flow_key, flow_buf = k, raw
            else:
                flow = parse_flow_list(raw)
                fm[k] = parse_scalar(v) if flow is None else flow
    if flow_key is not None:
        fm[flow_key] = flow_buf  # 閉じの `]` が無い flow 形式は list でない値として報告する
    return fm


def resolve_rubric_ref(ref: str, skill_dir: Path) -> Path:
    if ref.startswith("ref-") and REF_NAME.fullmatch(ref):
        # 正規パスは <skill>/references/rubric.json (lint-skill-tree が直下配置を禁止)
        candidates = sorted(PROJECT_ROOT.glob(f"plugins/*/skills/{ref}/references/rubric.json"))
        candidates.append(PROJECT_ROOT / ".claude" / "skills" / ref / "references" / "rubric.json")
        for c in candidates:
            if c.is_file():
                return c
        local = skill_dir / ref
        # ref として見つからず、SKILL.md の隣に `ref-notes.json` のようなファイルがあればそれを使う
        return local.resolve() if local.is_file() else candidates[0]
    return (skill_dir / ref).resolve()


def path_failure(path: Path) -> str | None:
    """参照先が repo の中のファイルでない理由。ファイルなら None。未解決は "NOT FOUND" (免除の対象)。"""
    if "\x00" in str(path):
        return "NUL を含む"  # resolve() の ValueError を「リポジトリの外」と取り違えない
    try:
        real = path.resolve()
        real.relative_to(PROJECT_ROOT)
    except ValueError:
        return "リポジトリの外"
    except (OSError, RuntimeError) as exc:
        return f"解決できない: {exc}"
    if real.is_file():
        return None
    return "ファイルでない" if real.exists() else "NOT FOUND"


def outside_repo(path: Path) -> bool:
    """symlink をたどった実体が PROJECT_ROOT の外にあるか。"""
    return path_failure(path) == "リポジトリの外"


def repo_relative(path: Path) -> str:
    try:
        return path.resolve().relative_to(PROJECT_ROOT).as_posix()
    except ValueError:
        return str(path)


def check_skill_md(skill_md: Path, exempted: list | None = None, used_exemptions: set | None = None) -> list:
    """FAIL の内訳を返す。EXEMPT_UNRESOLVED に当たった未解決の参照は exempted に積み、その鍵を used_exemptions に足す。"""
    failures = []
    fm = find_frontmatter(skill_md)
    refs = fm.get("rubric_refs")
    if refs is None:  # キーが無い、または null・~
        refs = []
    if not isinstance(refs, list):
        return [f"  {skill_md}: rubric_refs={refs!r} は list でない (`- x` か `[x]` で書く)"]
    for ref in refs:
        if not ref:
            failures.append(f"  {skill_md}: rubric_refs に空の要素がある")
            continue
        if "\x00" in ref:
            failures.append(f"  {skill_md}: rubric_refs={ref!r} は NUL を含む")
            continue
        if ref.startswith("ref-") and not REF_NAME.fullmatch(ref) and not (skill_md.parent / ref).is_file():
            failures.append(f"  {skill_md}: rubric_refs={ref!r} は ref 名として読めない "
                            "(英数字と ._- だけ。glob 記号や / は使えない)")
            continue
        resolved = resolve_rubric_ref(ref, skill_md.parent)
        problem = path_failure(resolved)
        if problem is None:
            continue
        key = (repo_relative(skill_md), ref)
        reason = EXEMPT_UNRESOLVED.get(key) if problem == "NOT FOUND" else None
        if reason is None:
            failures.append(f"  {skill_md}: rubric_refs={ref!r} -> {resolved} ({problem})")
            continue
        if exempted is not None:
            exempted.append(f"  {skill_md}: rubric_refs={ref!r} (EXEMPT: {reason})")
        if used_exemptions is not None:
            used_exemptions.add(key)
    return failures


def stale_exemptions(targets: list, used: set) -> list:
    """走査した SKILL.md について、未解決でなくなった (使われなかった) 免除を返す。"""
    scanned = {repo_relative(t) for t in targets}
    return [f"  EXEMPT_UNRESOLVED{key!r} は使われていない (参照が解決した、または rubric_refs から外れた)。"
            "lint-rubric-refs-exist.py から外す"
            for key in EXEMPT_UNRESOLVED if key[0] in scanned and key not in used]


def _registry_path_failure(label: str, value) -> str | None:
    """registry に書かれたパスが、空でない文字列で repo の中のファイルを指すか。"""
    if not isinstance(value, str) or not value.strip():
        return f"  rubric-registry.json: {label}={value!r} (空、または文字列でない)"
    if "\x00" in value:
        return f"  rubric-registry.json: {label}={value!r} (NUL を含む)"
    problem = path_failure(PROJECT_ROOT / value)
    return None if problem is None else f"  rubric-registry.json: {label}={value} ({problem})"


def check_registry() -> list:
    """registry のパスを確かめる。形が違う registry は ValueError (exit 2) にする。"""
    failures = []
    registry = PROJECT_ROOT / REGISTRY_REL
    if not registry.exists():
        return failures
    data = json.loads(registry.read_text(encoding="utf-8-sig"))
    rubrics = data.get("rubrics", []) if isinstance(data, dict) else None
    if not isinstance(rubrics, list):
        raise ValueError("rubric-registry.json の rubrics が list でない")
    for r in rubrics:
        if not isinstance(r, dict) or "domain" not in r or "rubric" not in r:
            raise ValueError(f"rubric-registry.json の rubrics の要素に domain と rubric が無い: {r!r}")
        upstream = r.get("upstream", [])
        if not isinstance(upstream, list):
            # 文字列を1文字ずつ参照として確かめないよう、形の誤りとして止める
            raise ValueError(f"rubric-registry.json の domain={r['domain']} の upstream が list でない: {upstream!r}")
        f = _registry_path_failure(f"domain={r['domain']} rubric", r["rubric"])
        if f:
            failures.append(f)
        for up in upstream:
            f = _registry_path_failure("upstream", up)
            if f:
                failures.append(f)
    return failures


def default_targets() -> list:
    """全 plugin と .claude/skills の SKILL.md。symlink で同じ実体を指すものは1つにまとめる。"""
    targets, seen = [], set()
    for pattern in ("plugins/*/skills/*/SKILL.md", ".claude/skills/*/SKILL.md"):
        for p in sorted(PROJECT_ROOT.glob(pattern)):
            real = p.resolve()
            if real not in seen:
                seen.add(real)
                targets.append(p)
    return targets


def main() -> int:
    usage = "usage: lint-rubric-refs-exist.py [SKILL.md ...]  (省略時は全 plugin と .claude/skills を走査)"
    args = sys.argv[1:]
    if any(a in ("-h", "--help") for a in args):
        print(__doc__)
        print(usage)
        return 0
    unknown = [a for a in args if a.startswith("-")]
    if unknown:
        print(f"ERROR: 未知の option: {', '.join(unknown)}\n{usage}", file=sys.stderr)
        return 2
    if args:
        targets = [Path(p) for p in sys.argv[1:]]
        missing = [str(t) for t in targets if not t.is_file()]
        if missing:
            print(f"ERROR: 指定した SKILL.md が無い: {', '.join(missing)}", file=sys.stderr)
            return 2
    else:
        targets = default_targets()

    if not targets:
        print(f"ERROR: 走査対象の SKILL.md が0件 (PROJECT_ROOT={PROJECT_ROOT} を確かめる)", file=sys.stderr)
        return 2
    registry = PROJECT_ROOT / REGISTRY_REL
    if not registry.exists():
        print("WARNING: rubric-registry.json が無いので registry の検査はしない", file=sys.stderr)
    elif not registry.is_file():
        print(f"ERROR: rubric-registry.json がファイルでない: {registry}", file=sys.stderr)
        return 2

    all_failures, exempted, used = [], [], set()
    try:
        for t in targets:
            all_failures.extend(check_skill_md(t, exempted, used))
        all_failures.extend(stale_exemptions(targets, used))
        all_failures.extend(check_registry())
    except (OSError, ValueError, KeyError, TypeError, AttributeError, RecursionError) as exc:
        # 非 UTF-8 の SKILL.md (UnicodeDecodeError)・壊れた registry・domain や rubric の欠落
        print(f"ERROR: 入力を読めない: {type(exc).__name__}: {exc}", file=sys.stderr)
        return 2

    if exempted:
        print("NOTE: 理由つきで免除した未解決の rubric_refs:", file=sys.stderr)
        for e in exempted:
            print(e, file=sys.stderr)
    if all_failures:
        print("FAIL: rubric_refs 未解決:", file=sys.stderr)
        for f in all_failures:
            print(f, file=sys.stderr)
        return 1

    print(f"PASS: rubric_refs 全件解決 ({len(targets)} SKILL.md checked, {len(exempted)} exempted)")
    return 0


if __name__ == "__main__":
    sys.exit(main())
