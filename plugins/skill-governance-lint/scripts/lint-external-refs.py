#!/usr/bin/env python3
# /// script
# name: lint-external-refs
# purpose: Reject undeclared cross-plugin SKILL.md references while allowing package-contract dependencies, owned-vendored copies and existence-checked repo refs.
# inputs:
#   - --skills-dir: directory containing skill subdirectories
#   - --package-contract: package contract JSON that declares depends_on / runtime_dependencies / repo_refs (default: <skills-dir>/../references/package-contract.json)
#   - --allowed-prefix: repo-root-relative prefix that is never external (repeatable; replaces the defaults)
#   - --json: emit machine-readable JSON
#   - --fail-on-external: exit 1 when external references or contract errors are found
# outputs:
#   - stdout: inventory report
#   - exit: 0 = scanned (findings only fail with --fail-on-external) / 1 = --fail-on-external and
#     external refs or contract errors, or a skill dir / SKILL.md could not be read, or no SKILL.md was found /
#     2 = --skills-dir is not a directory
# contexts: [E]
# network: false
# write-scope: none
# dependencies: []
# ///
"""SKILL.md の外部参照を棚卸しする。

34章 Phase 0 の「全 SKILL.md 外部参照棚卸し」を機械化するための lint。
plugin の外を指す参照は、package contract (`references/package-contract.json`) の
次の 3 つの宣言でだけ許し、どれにも当たらない参照は fail-closed にする。

- `depends_on`: install 時に一緒に入る plugin。その plugin を指す参照を許す。
- `runtime_dependencies` の `owned-vendored`: 他の plugin が正本の skill を byte のまま持つ写し。
  正本と byte が同じで、正本の plugin がその skill を写しと宣言していないときだけ、
  その写しの参照の扱いを正本の plugin の検査に任せる (任せ合いで誰も検査しない形を作らない)。
- `repo_refs`: repo の clone の中にだけある資産 (設計書や、循環になるので depends_on に
  入れられない兄弟 plugin)。参照ごとに repo の中での実在を確かめ、使われていない宣言は
  contract error にする。install した plugin の中では確かめられないので外部参照のまま数える。

どの宣言でも外さない参照:

- `unnormalized_path`: 先頭の `../` の並びの後ろに `.`・`..`・空の segment がある参照
  (`references/../../x` や `skills/../../x`)。普通の dir 名・`$VAR/` の後ろの dir 名・絶対 path の後ろに
  `../` が続く参照 (`assets/../../x`・`$WORK/sub/../x`・`/a/../x`) と、長い相対 path の途中の root の語から
  `..` が続く参照 (`assets/scripts/../../x`・`xscripts/../x`) もここに入れ、token の先頭から報告する。
  書いた prefix と指す先が食い違うので、許可の判定に使えない。
- `unknown_base`: 起点の分からない変数や式の後ろの `../` (`$WORK/../x`・`"$WORK"/../x`・`<ROOT>/../x`・
  `$(cmd)/../x`)。起点を決められる変数は `CLAUDE_PLUGIN_ROOT`・`PLUGIN_ROOT`・`PLUGIN_DIR` (plugin の root) と
  `SKILL_DIR`・`CLAUDE_SKILL_DIR` (その SKILL.md の dir) だけ。変数と `../` の間の `./`・重ねた `/`・
  閉じの引用符 (`$ROOT/./../x`・`$ROOT//../x`・`"$ROOT"/../x`) は起点を変えない。

既知の限界:

- 参照は空白・全角括弧・引用符で切る。全角括弧や空白を含む path は途中までしか見ない
  (文章を path に取り込まないための切り方)。最後の segment で拡張子の直後に続く日本語も切る。
- 長い相対 path や URL の途中の一致 (`.agents/plugins/x`・`https://host/plugins/x`・`my-plugins/x`) は
  この lint が見る root ではないので数えない。絶対 path の途中の root (`/repo/plugins/<name>/...`) は、
  その root から分類する (repo の外の絶対 path かどうかは確かめない)。開きの引用符・`(`・`=`・`:`・`[` や、
  続けて書いた日本語の文章 (`パスは/Users/...`) の後ろの `/` も絶対 path の始まりと読む。
- `.claude/plugins/` (他の plugin の install 先) は、allowed prefix の `.claude/` の下でも外部に数える。
- `skills/<name>/...` は、自分の plugin に `skills/<name>` の dir があれば自分の skill として扱い
  (その先の file の実在は確かめない)、無ければ `foreign_skill_ref` として外部に数える。
  他の plugin の skill は `plugins/<owner>/skills/...` と持ち主を書けば、depends_on と repo_refs で判定できる。
- allowed prefix (既定は `.claude/`・`eval-log/`・`references/`・`scripts/`) の参照は
  実在を確かめない。plugin の root の `scripts/` と repo の root の `scripts/` を区別しない。
"""
from __future__ import annotations

import argparse
import hashlib
import json
import pathlib
import re
import stat
import sys


DEFAULT_ALLOWED_PREFIXES = (
    ".claude/",
    "eval-log/",
    "references/",
    "scripts/",
)

PATH_RE = re.compile(
    r"(?P<path>(?:(?:\.\./)+|(?:\.claude|scripts|doc|references|eval-log|plugins|skills)/)"
    r"[A-Za-z0-9_\-./㐀-鿿々ぁ-んァ-ヶー]+)"
)
PLUGIN_NAME_RE = re.compile(r"^[a-z][a-z0-9-]*[a-z0-9]$")
# owned-vendored の local_path と owner_route は、plugin の root 直下の skill 1 つだけを指す
SKILL_ROUTE_RE = re.compile(r"^skills/[A-Za-z0-9][A-Za-z0-9_-]*$")
# 一致の直前にある root の変数 (`$NAME/`・`${NAME}/`・`{{NAME}}/`・引用符で閉じた `"$NAME"/`)
_VARIABLE_BEFORE_RE = re.compile(
    r"(?:\$\{(?P<braced>[A-Za-z_][A-Za-z0-9_]*)\}|\$(?P<bare>[A-Za-z_][A-Za-z0-9_]*)"
    r"|\{\{\s*(?P<template>[A-Za-z_][A-Za-z0-9_]*)\s*\}\})[\"']?/$"
)
# shell の既定値の書き出し (`${X:-` と `${X-`)。この後ろの path は root から始まる
_SHELL_DEFAULT_BEFORE_RE = re.compile(r"\$\{[A-Za-z_][A-Za-z0-9_]*:?-$")
# `<ROOT>` のような置き場所の名前の閉じ。`2>/x` の redirect と区別する
_ANGLE_PLACEHOLDER_BEFORE_RE = re.compile(r"<[A-Za-z_](?:[^<>\n]{0,62}[A-Za-z0-9_])?>$")
PLUGIN_ROOT_VARIABLES = frozenset({"CLAUDE_PLUGIN_ROOT", "PLUGIN_ROOT", "PLUGIN_DIR"})
SKILL_DIR_VARIABLES = frozenset({"SKILL_DIR", "CLAUDE_SKILL_DIR"})
# path の 1 segment に使う ASCII 文字。一致の直前がこれなら、もっと長い path の途中から一致している。
_SEGMENT_CHARS = frozenset("ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnopqrstuvwxyz0123456789_-.")
_CJK_RE = re.compile(r"[㐀-鿿々ぁ-んァ-ヶー]")
# 最後の segment で、拡張子の直後に続く日本語は文章 (`a.mdを参照`)。path に含めない
_TRAILING_PROSE_RE = re.compile(r"^((?:.*/)?[^/]*?\.[A-Za-z0-9]{1,10})[㐀-鿿々ぁ-んァ-ヶー][^/]*$")
# `.claude/` の下でも、他の plugin の install 先は外部として数える (`~/.claude/plugins/cache/<mkt>/<plugin>/...`)
_NOT_ALLOWED_UNDER_PREFIX = (".claude/plugins/",)
REPO_REF_KEYS = frozenset({"ref", "match", "target", "reason"})
REPO_REF_MATCHES = ("exact", "prefix")
# repo_refs で外部参照を外せるのは、この 2 つの分類だけ (allowed_prefix などは元から外部ではない)
REPO_REF_CANDIDATES = ("undeclared_plugin_dependency", "outside_plugin")


def load_package_contract(contract_path: pathlib.Path) -> tuple[dict | None, list[str]]:
    """package contract を読む。無い・壊れている・object でないときは error を返す。"""
    if not contract_path.is_file():
        return None, [f"package contract not found: {contract_path}"]
    try:
        data = json.loads(contract_path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        return None, [f"package contract parse error: {contract_path}: {exc}"]
    if not isinstance(data, dict):
        return None, [f"package contract must be an object: {contract_path}"]
    return data, []


def declared_dependencies_from(data: dict) -> tuple[set[str], list[str]]:
    raw = data.get("depends_on", [])
    if not isinstance(raw, list):
        return set(), ["package contract depends_on must be an array"]
    errors: list[str] = []
    dependencies: set[str] = set()
    for value in raw:
        if not isinstance(value, str) or not PLUGIN_NAME_RE.fullmatch(value):
            errors.append(f"invalid depends_on plugin name: {value!r}")
        else:
            dependencies.add(value)
    return dependencies, errors


def load_declared_dependencies(contract_path: pathlib.Path) -> tuple[set[str], list[str]]:
    """Load the explicit dependency allowlist; malformed input is an error."""
    data, errors = load_package_contract(contract_path)
    if data is None:
        return set(), errors
    return declared_dependencies_from(data)


def _is_repo_relative(value: str) -> bool:
    """repo root からの相対 path として安全か (絶対 path・`..`・`\\`・空の segment を拒否)。"""
    if not value or value.startswith(("/", "~")) or "\\" in value or ":" in value:
        return False
    parts = value.rstrip("/").split("/")
    return all(part not in ("", ".", "..") for part in parts)


def parse_repo_refs(raw: object) -> tuple[list[dict], list[str]]:
    """package contract の repo_refs を検証する。形の誤りは全部 contract error にする。

    key が無いときは呼ばない (main が見分ける)。`null` は宣言の書き損じとして error にする。
    prefix は `/` で終わり 2 段以上 (`doc/design/` など) に限る。`doc/` のような 1 段の prefix は
    その root の下の参照をまとめて通してしまうので、宣言の粒度として受け付けない。
    """
    if not isinstance(raw, list):
        return [], ["package contract repo_refs must be an array"]
    entries: list[dict] = []
    errors: list[str] = []
    seen: set[tuple[str, str]] = set()
    for index, item in enumerate(raw):
        label = f"repo_refs[{index}]"
        if not isinstance(item, dict):
            errors.append(f"{label} must be an object")
            continue
        ref, match, target, reason = (item.get(k) for k in ("ref", "match", "target", "reason"))
        problems: list[str] = []
        unknown = sorted(set(item) - REPO_REF_KEYS)
        if unknown:
            problems.append(f"unknown keys: {unknown}")
        if "target" in item and target is None:
            problems.append("target must be a string when present (omit the key instead of null)")
        if not isinstance(ref, str) or not ref:
            problems.append("ref must be a non-empty string")
        elif ref.startswith("../"):
            if target is None:
                problems.append("ref starting with ../ needs target (its base depends on the reader)")
        elif not _is_repo_relative(ref):
            problems.append(f"ref must be repo-relative without '..': {ref!r}")
        elif match == "prefix" and (not ref.endswith("/") or len(ref.rstrip("/").split("/")) < 2):
            problems.append(f"prefix ref must end with '/' and have at least 2 segments: {ref!r}")
        if match not in REPO_REF_MATCHES:
            problems.append(f"match must be one of {list(REPO_REF_MATCHES)}: {match!r}")
        if target is not None:
            if match != "exact":
                problems.append("target is only allowed with match=exact")
            if not isinstance(target, str) or not _is_repo_relative(target):
                problems.append(f"target must be repo-relative without '..': {target!r}")
        if not isinstance(reason, str) or not reason.strip():
            problems.append("reason must be a non-empty string")
        if problems:
            errors.extend(f"{label}: {problem}" for problem in problems)
            continue
        if (ref, match) in seen:
            errors.append(f"{label}: duplicate repo_ref {match} {ref!r}")
            continue
        seen.add((ref, match))
        entries.append({"ref": ref, "match": match, "target": target, "reason": reason, "used": 0})
    return entries, errors


def find_repo_ref(ref: str, entries: list[dict], *, parent_exact: bool = True) -> dict | None:
    """exact を先に、無ければいちばん長い prefix の宣言を返す。

    parent_exact が False なら `../` で始まる exact の宣言は使わない (起点が SKILL.md の dir でない参照)。
    """
    for entry in entries:
        if entry["match"] == "exact" and entry["ref"] == ref and (parent_exact or not ref.startswith("../")):
            return entry
    prefixes = [e for e in entries if e["match"] == "prefix" and ref.startswith(e["ref"])]
    return max(prefixes, key=lambda e: len(e["ref"])) if prefixes else None


def repo_root_for(plugin_dir: pathlib.Path) -> pathlib.Path | None:
    """`<repo>/plugins/<plugin>` の配置のときだけ repo root を返す (install 先では確かめられない)。"""
    resolved = plugin_dir.resolve()
    return resolved.parent.parent if resolved.parent.name == "plugins" else None


def classify_repo_ref(ref: str, entry: dict, repo_root: pathlib.Path | None) -> str:
    if repo_root is None:
        return "unverifiable_repo_ref"
    candidate = (repo_root / (entry["target"] or ref)).resolve(strict=False)
    try:
        candidate.relative_to(repo_root)
    except ValueError:
        return "missing_repo_ref"
    return "declared_repo_ref" if candidate.exists() else "missing_repo_ref"


def _sha256(path: pathlib.Path) -> str | None:
    try:
        return hashlib.sha256(path.read_bytes()).hexdigest()
    except OSError:
        return None


def _vendored_local_paths(plugin_dir: pathlib.Path) -> set[str]:
    """その plugin が owned-vendored の写しと宣言している local_path (読めなければ空)。

    正本の plugin の lint は、ここに入る skill を自分では検査せず、さらに別の plugin に任せうる。
    形の誤った宣言も数える (任せ合いの見落としより、任せない方へ倒す)。
    """
    data, _ = load_package_contract(plugin_dir / "references" / "package-contract.json")
    raw = data.get("runtime_dependencies") if data is not None else None
    if not isinstance(raw, list):
        return set()
    return {
        item["local_path"]
        for item in raw
        if isinstance(item, dict)
        and item.get("classification") == "owned-vendored"
        and isinstance(item.get("local_path"), str)
    }


def owned_vendored_skills(
    data: dict,
    plugin_dir: pathlib.Path,
) -> tuple[dict[str, dict], list[str]]:
    """runtime_dependencies の owned-vendored を、skill 名ごとの {owner, status} にする。

    status は identical (正本と byte が同じ) / diverged / owner_missing / owner_not_canonical。
    identical のときだけ、その写しの参照の扱いを正本の plugin の PKG-009 に任せる (同じ bytes を
    正本側が検査する)。正本の plugin がその skill を自分も写しと宣言していれば (任せ合いや連鎖)、
    正本側は検査しないので owner_not_canonical にして任せず、contract error にする。
    宣言の形の誤り (path の形・owner が自分・local_path の重複) も contract error にする。
    """
    raw = data.get("runtime_dependencies", [])
    if not isinstance(raw, list):
        return {}, ["package contract runtime_dependencies must be an array"]
    vendored: dict[str, dict] = {}
    errors: list[str] = []
    plugins_root = plugin_dir.resolve().parent
    for index, item in enumerate(raw):
        label = f"runtime_dependencies[{index}]"
        if not isinstance(item, dict):
            errors.append(f"{label} must be an object")
            continue
        if item.get("classification") != "owned-vendored":
            continue
        owner, local_path, owner_route = item.get("owner"), item.get("local_path"), item.get("owner_route")
        if not all(isinstance(v, str) for v in (owner, local_path, owner_route)):
            errors.append(f"{label}: owned-vendored needs string owner, local_path and owner_route")
            continue
        if owner == plugin_dir.name or not PLUGIN_NAME_RE.fullmatch(owner):
            errors.append(f"{label}: owner must be another plugin's name: {owner!r}")
            continue
        if not SKILL_ROUTE_RE.fullmatch(local_path) or not SKILL_ROUTE_RE.fullmatch(owner_route):
            errors.append(f"{label}: local_path and owner_route must be skills/<name>: {local_path!r}, {owner_route!r}")
            continue
        skill = local_path.split("/", 1)[1]
        if skill in vendored:
            errors.append(f"{label}: duplicate owned-vendored local_path {local_path!r}")
            continue
        local_sha = _sha256(plugin_dir / local_path / "SKILL.md")
        owner_dir = plugins_root / owner
        owner_sha = _sha256(owner_dir / owner_route / "SKILL.md")
        if owner_sha is None:
            status = "owner_missing"
        elif owner_route in _vendored_local_paths(owner_dir):
            status = "owner_not_canonical"
            errors.append(f"{label}: owner {owner} also declares {owner_route} as owned-vendored; point owner at the canonical plugin")
        elif local_sha == owner_sha:
            status = "identical"
        else:
            status = "diverged"
        vendored[skill] = {"owner": owner, "owner_route": owner_route, "status": status}
    return vendored, errors


def _is_token_char(ch: str) -> bool:
    """一致の手前を path の token の先頭まで辿るときに読む文字 (segment・`/`・`~`・PATH_RE と同じ CJK)。"""
    return ch in _SEGMENT_CHARS or ch in "/~" or bool(_CJK_RE.fullmatch(ch))


def _closes_expression(text: str, index: int) -> bool:
    """text[index] が root を表す式の閉じか (`<ROOT>`・`${ROOT}`・`{{ROOT}}`・`$(cmd)`・`"$ROOT"`)。

    `>` は `<名前>` の閉じのときだけ (`cmd >/Users/...` の redirect は閉じではない)。引用符は、直前が
    ASCII の英数字・`_`・`}`・`)` のときだけ閉じと読む (`open("/Users/...")`・`ROOT="/x"`・
    `{"path":"/x"}` の開きの引用符は閉じではない)。
    """
    ch = text[index]
    if ch in "})":
        return True
    if ch == ">":
        return _ANGLE_PLACEHOLDER_BEFORE_RE.search(text, max(0, index - 64), index + 1) is not None
    if ch in "\"'" and index > 0:
        before = text[index - 1]
        return before.isascii() and (before.isalnum() or before in "_})")
    return False


def _token_begin(text: str, end: int) -> int:
    """text[end] の手前から path の token の先頭まで戻った位置。

    token の頭の日本語に `/`・`./`・`../`・`~/` が続くときは、その日本語を文章として外す
    (`詳細は./x`・`パスは/Users/...`・`置き場所は~/.claude/...`)。日本語の dir 名は `doc/設計書/` のように
    root の語の後ろに来るので、PATH_RE の一致の中に入る。
    """
    begin = end
    while begin > 0 and _is_token_char(text[begin - 1]):
        begin -= 1
    prose_end = begin
    while prose_end < end and _CJK_RE.fullmatch(text[prose_end]):
        prose_end += 1
    if prose_end > begin and text.startswith(("/", "./", "../", "~/"), prose_end):
        return prose_end
    return begin


def _context_before(text: str, start: int, end: int) -> tuple[str | None, int]:
    """一致 text[start:end] の手前の文脈と、報告に使う token の先頭。

    - None: root から始まる一致 (手前が空・区切り・root の変数や式の直後、shell の既定値 `:-`・`-`)。
      絶対 path の途中の root (`/repo/plugins/x` の `plugins/x`) もここに入れ、中の root から分類する。
    - "skip": もっと長い相対 path や URL の途中 (`.agents/plugins/x`・`https://host/plugins/x`・
      `my-plugins/x`)。この lint が見る root ではない。
    - "unnormalized_path": 普通の dir 名や絶対 path の後ろの `../` (`assets/../../x`・`$WORK/sub/../x`・
      `/a/../x`)。長い相対 path の途中の一致でも、一致の中に `..` があればここに入れる
      (`assets/scripts/../../x`・`xscripts/../x`)。指す先を書いた形から決められないので、どの許可にも当てない。
    """
    parent_inside = ".." in text[start:end].split("/")
    if start == 0:
        return None, start
    previous = text[start - 1]
    if previous in _SEGMENT_CHARS:
        if previous == "-" and _SHELL_DEFAULT_BEFORE_RE.search(text, max(0, start - 128), start):
            return None, start  # `${X:-plugins/...}`・`${X-plugins/...}` の既定値
        if parent_inside:
            return "unnormalized_path", _token_begin(text, start)
        return "skip", start  # `xscripts/`・`my-plugins/`・`claude-skills/` のような別の語の一部
    if previous != "/":
        return None, start
    begin = _token_begin(text, start)
    head = text[begin:start]
    closed = begin > 0 and _closes_expression(text, begin - 1)
    if begin > 0 and text[begin - 1] == ":" and head.startswith("//"):
        return "skip", begin  # URL (`https://host/plugins/x`)
    segments = head.split("/")[:-1]
    if begin > 0 and text[begin - 1] == "$":
        segments = segments[1:]  # `$ROOT/` の変数名
        begin -= 1
    absolute = not closed and head.startswith(("/", "~"))
    named = [segment for segment in segments if segment not in ("", ".", "~")]
    if text.startswith("../", start) and (named or absolute):
        return "unnormalized_path", begin
    if absolute or not named:
        return None, start
    if parent_inside:
        return "unnormalized_path", begin
    return "skip", start


def _has_dot_segment(ref: str) -> bool:
    """先頭の `../` の並びの後ろに `.`・`..`・空の segment があるか (末尾の `/` 1 つは除く)。

    `references/../../x` は prefix だけ見ると allowed、指す先は plugin の外になる。
    書いた形と指す先が食い違う参照は、どの許可にも当てない。
    """
    rest = ref
    while rest.startswith("../"):
        rest = rest[3:]
    if not rest:
        return False  # `../../` だけの参照は dir を指す。起点から解いて分類する
    if rest.endswith("/"):
        rest = rest[:-1]
    return any(part in ("", ".", "..") for part in rest.split("/"))


def _skip_noop_segments(text: str, end: int) -> int:
    """text[:end] の末尾の `./` と重ねた `/` を読み飛ばした位置 (`$ROOT/./../x`・`$ROOT//../x` の起点は `$ROOT`)。"""
    while True:
        if end >= 3 and text[end - 3:end] == "/./":
            end -= 2
        elif end >= 2 and text[end - 2:end] == "//":
            end -= 1
        else:
            return end


def _base_for(text: str, start: int, skill_path: pathlib.Path, plugin_dir: pathlib.Path | None) -> pathlib.Path | None:
    """`../` を解く起点。直前の変数で決まり、起点の分からない変数や式の後ろなら None。

    変数も式も無ければ SKILL.md の dir (Markdown の相対 path の読み方)。
    """
    end = _skip_noop_segments(text, start)
    found = _VARIABLE_BEFORE_RE.search(text, max(0, end - 128), end)
    if found is None:
        if end >= 2 and text[end - 1] == "/" and _closes_expression(text, end - 2):
            return None  # `<ROOT>/../x`・`$(cmd)/../x`・`${X:-y}/../x`: 式の値が分からない
        return skill_path.parent
    name = found.group("braced") or found.group("bare") or found.group("template")
    if name in PLUGIN_ROOT_VARIABLES:
        return plugin_dir
    if name in SKILL_DIR_VARIABLES:
        return skill_path.parent
    return None


def _plugin_slug_for_ref(
    ref: str,
    base: pathlib.Path | None,
    plugin_dir: pathlib.Path | None,
) -> str | None:
    """参照が指す plugin の名前。`../` は base から解く (base が None なら決めない)。"""
    if ref.startswith("plugins/"):
        parts = pathlib.PurePosixPath(ref).parts
        # `plugins/<name>` だけの参照も plugin を指す。`plugins/marketplace.json` は名前の形でないので外す
        return parts[1] if len(parts) >= 2 and PLUGIN_NAME_RE.fullmatch(parts[1]) else None
    if not ref.startswith("../") or plugin_dir is None or base is None:
        return None
    plugins_root = plugin_dir.resolve().parent
    resolved = (base / ref).resolve(strict=False)
    try:
        relative = resolved.relative_to(plugins_root)
    except ValueError:
        return None
    return relative.parts[0] if len(relative.parts) >= 2 else None


def scan_skill(
    path: pathlib.Path,
    allowed_prefixes: tuple[str, ...],
    *,
    plugin_dir: pathlib.Path | None = None,
    declared_dependencies: set[str] | frozenset[str] = frozenset(),
    vendored_owner: str | None = None,
    repo_refs: list[dict] | None = None,
    repo_root: pathlib.Path | None = None,
) -> dict:
    """1 つの SKILL.md の参照を分類する。

    判定の順は unnormalized_path・unknown_base (どの宣言でも外さない) → same_plugin →
    declared_plugin_dependency → owned_vendored (vendored_owner を渡したとき) → repo_refs → 外部。
    repo_refs の宣言に当たった回数は entry の used に足す。UTF-8 で読めなければ UnicodeDecodeError を返す。
    """
    text = path.read_text(encoding="utf-8")
    refs = []
    for match in PATH_RE.finditer(text):
        context, token_start = _context_before(text, match.start(), match.end())
        if context == "skip":
            continue
        if context == "unnormalized_path":
            refs.append({
                "ref": text[token_start:match.end()].rstrip(").,`\"'"),
                "line": text.count("\n", 0, match.start()) + 1,
                "external": True,
                "classification": "unnormalized_path",
            })
            continue
        ref = match.group("path").rstrip(").,`\"'")
        prose = _TRAILING_PROSE_RE.match(ref)
        if prose:
            ref = prose.group(1)
        base = _base_for(text, match.start(), path, plugin_dir)
        if _has_dot_segment(ref) or (ref.startswith("../") and base is None):
            refs.append({
                "ref": ref,
                "line": text.count("\n", 0, match.start()) + 1,
                "external": True,
                "classification": "unnormalized_path" if _has_dot_segment(ref) else "unknown_base",
            })
            continue
        dependency = _plugin_slug_for_ref(ref, base, plugin_dir)
        if dependency is not None:
            if plugin_dir is not None and dependency == plugin_dir.name:
                external = False
                classification = "same_plugin"
            elif dependency in declared_dependencies:
                external = False
                classification = "declared_plugin_dependency"
            else:
                external = True
                classification = "undeclared_plugin_dependency"
        elif ref.startswith("../") and plugin_dir is not None:
            resolved = (base / ref).resolve(strict=False)
            try:
                resolved.relative_to(plugin_dir.resolve())
                external = False
                classification = "same_plugin"
            except ValueError:
                external = True
                classification = "outside_plugin"
        elif ref.startswith("skills/"):
            # plugin の root から見た skill。自分の plugin にその skill が無ければ、他の plugin の
            # skill を持ち主を書かずに指している (`plugins/<owner>/skills/...` と書けば上で分類できる)
            skill_name = ref.split("/", 2)[1]
            external = plugin_dir is None or not (plugin_dir / "skills" / skill_name).is_dir()
            classification = "foreign_skill_ref" if external else "same_plugin"
        else:
            external = not ref.startswith(allowed_prefixes) or ref.startswith(_NOT_ALLOWED_UNDER_PREFIX)
            classification = "allowed_prefix" if not external else "outside_plugin"
        extra: dict = {"dependency": dependency} if dependency is not None else {}
        if external and vendored_owner is not None:
            external = False
            classification = "owned_vendored"
            extra["owner"] = vendored_owner
        elif external and classification in REPO_REF_CANDIDATES and repo_refs:
            # `../` の exact 宣言は SKILL.md の dir から読んだ参照の宣言。起点の違う参照には当てない
            entry = find_repo_ref(ref, repo_refs, parent_exact=base == path.parent)
            if entry is not None:
                entry["used"] += 1
                classification = classify_repo_ref(ref, entry, repo_root)
                external = classification != "declared_repo_ref"
                extra["repo_ref"] = entry["ref"]
                if entry["target"]:
                    extra["target"] = entry["target"]
        refs.append(
            {
                "ref": ref,
                "line": text.count("\n", 0, match.start()) + 1,
                "external": external,
                "classification": classification,
                **extra,
            }
        )
    return {
        "skill": path.parent.name,
        "path": str(path),
        "refs": refs,
        "external_refs": [r for r in refs if r["external"]],
    }


def _skill_files(skills_dir: pathlib.Path) -> tuple[list[pathlib.Path], list[str]]:
    """skills_dir 直下の dir ごとの SKILL.md と、辿れなかったものの一覧。

    glob は読めない dir や壊れた symlink を黙って飛ばすので、飛ばした分が「外部参照なし」に見える。
    stat で 1 つずつ辿り、辿れなかったもの (権限・壊れた symlink) と SKILL.md が 1 本も無いことを
    scan error にする。SKILL.md を持たない普通の dir は、これまでどおり skill ではないとして飛ばす。
    """
    try:
        entries = sorted(skills_dir.iterdir())
    except OSError as exc:
        return [], [f"{skills_dir}: {exc}"]
    files: list[pathlib.Path] = []
    errors: list[str] = []
    for entry in entries:
        try:
            if not stat.S_ISDIR(entry.stat().st_mode):
                continue
        except FileNotFoundError:
            errors.append(f"{entry}: broken symlink")
            continue
        except OSError as exc:
            errors.append(f"{entry}: {exc}")
            continue
        skill_md = entry / "SKILL.md"
        try:
            skill_md.stat()
        except FileNotFoundError:
            try:
                skill_md.lstat()
            except FileNotFoundError:
                continue  # SKILL.md の無い dir は skill ではない
            except OSError as exc:
                errors.append(f"{skill_md}: {exc}")
                continue
            errors.append(f"{skill_md}: broken symlink")
            continue
        except OSError as exc:
            errors.append(f"{skill_md}: {exc}")
            continue
        files.append(skill_md)
    if not files and not errors:
        errors.append(f"{skills_dir}: no <skill>/SKILL.md found")
    return files, errors


def main(argv: list[str]) -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--skills-dir", default="plugins/harness-creator/skills")
    parser.add_argument(
        "--allowed-prefix",
        action="append",
        default=[],
        help="never-external prefix (repeatable; replaces the defaults .claude/ eval-log/ references/ scripts/)",
    )
    parser.add_argument(
        "--package-contract",
        help="package contract JSON (depends_on / runtime_dependencies / repo_refs); "
        "default: <skills-dir>/../references/package-contract.json",
    )
    parser.add_argument("--json", action="store_true")
    parser.add_argument("--fail-on-external", action="store_true")
    args = parser.parse_args(argv[1:])

    skills_dir = pathlib.Path(args.skills_dir)
    if not skills_dir.is_dir():
        # 0 件の走査を「外部参照なし」と読ませない
        print(f"--skills-dir is not a directory: {skills_dir}", file=sys.stderr)
        return 2
    plugin_dir = skills_dir.parent.resolve()
    allowed = tuple(args.allowed_prefix or DEFAULT_ALLOWED_PREFIXES)
    contract_path = (
        pathlib.Path(args.package_contract)
        if args.package_contract
        else plugin_dir / "references" / "package-contract.json"
    )
    contract, contract_errors = load_package_contract(contract_path)
    dependencies: set[str] = set()
    repo_refs: list[dict] = []
    vendored: dict[str, dict] = {}
    if contract is not None:
        dependencies, errors = declared_dependencies_from(contract)
        contract_errors.extend(errors)
        if "repo_refs" in contract:
            repo_refs, errors = parse_repo_refs(contract["repo_refs"])
            contract_errors.extend(errors)
        vendored, errors = owned_vendored_skills(contract, plugin_dir)
        contract_errors.extend(errors)
    repo_root = repo_root_for(plugin_dir)
    reports = []
    skill_files, scan_errors = _skill_files(skills_dir)
    for skill_md in skill_files:
        info = vendored.get(skill_md.parent.name)
        try:
            reports.append(scan_skill(
                skill_md,
                allowed,
                plugin_dir=plugin_dir,
                declared_dependencies=dependencies,
                vendored_owner=info["owner"] if info and info["status"] == "identical" else None,
                repo_refs=repo_refs,
                repo_root=repo_root,
            ))
        except (OSError, UnicodeDecodeError) as exc:
            # 読めなかった SKILL.md は外部参照の有無を確かめていない。0 件として数えない
            scan_errors.append(f"{skill_md}: {exc}")
    # 使われていない宣言は残すと、後で消えた参照の代わりに別の参照を黙って通す。ratchet として error にする
    contract_errors.extend(
        f"unused repo_ref ({entry['match']}): {entry['ref']}" for entry in repo_refs if not entry["used"]
    )

    def count(classification: str) -> int:
        return sum(1 for report in reports for ref in report["refs"] if ref["classification"] == classification)

    external_total = sum(len(r["external_refs"]) for r in reports)
    declared_total = count("declared_plugin_dependency")
    payload = {
        "skills_dir": str(skills_dir),
        "allowed_prefixes": list(allowed),
        "package_contract": str(contract_path),
        "repo_root": str(repo_root) if repo_root else None,
        "declared_dependencies": sorted(dependencies),
        "contract_errors": contract_errors,
        "scan_errors": scan_errors,
        "skills_scanned": len(reports),
        "external_ref_count": external_total,
        "declared_dependency_ref_count": declared_total,
        "owned_vendored_ref_count": count("owned_vendored"),
        "declared_repo_ref_count": count("declared_repo_ref"),
        "vendored_skills": [{"skill": skill, **info} for skill, info in sorted(vendored.items())],
        "repo_refs": [{k: v for k, v in entry.items() if v is not None} for entry in repo_refs],
        "reports": reports,
    }

    if args.json:
        print(json.dumps(payload, ensure_ascii=False, indent=2))
    else:
        print(
            f"skills_scanned={payload['skills_scanned']} "
            f"external_ref_count={external_total} "
            f"declared_dependency_ref_count={declared_total} "
            f"owned_vendored_ref_count={payload['owned_vendored_ref_count']} "
            f"declared_repo_ref_count={payload['declared_repo_ref_count']}"
        )
        for error in contract_errors:
            print(f"CONTRACT_ERROR {error}")
        for error in scan_errors:
            print(f"SCAN_ERROR {error}")
        for report in reports:
            for ref in report["external_refs"]:
                print(
                    f"EXTERNAL {report['skill']}:{ref['line']} {ref['ref']} "
                    f"({ref['classification']})"
                )

    if scan_errors:
        return 1
    return 1 if args.fail_on_external and (external_total or contract_errors) else 0


if __name__ == "__main__":
    sys.exit(main(sys.argv))
