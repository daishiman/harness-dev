#!/usr/bin/env python3
# /// script
# name: guard-change-category
# version: 0.3.0
# purpose: git diff <base>...HEAD の変更を 33章の P0〜P3 に分類し、proposal_required の変更の承認と cooldown を governance-log と照合する（CI の governance gate。判定の拠り所は merge-base の policy と、merge-base から追記だけの governance-log）
# inputs:
#   - --base: 比べる ref（既定 origin/main。空・- で始まる・.. や空白を含む値は exit 2）
#   - --policy: governance-policy.json の絶対パス（省略時は merge-base の時点の plugins/skill-governance-config/config/governance-policy.json。merge-base に無いときだけ作業ツリーの同じ file）
#   - --proposal-id: この変更を承認した entry の proposal_id（省略時は target_sha256 が現物と一致する承認だけを数える）
#   - --report: 判定を JSON で stdout に出す
#   - --bypass-cooldown: cooldown のある分類で、現物に束縛された承認済みの incident_fix=true の entry があるときだけ cooldown を飛ばす（無ければその変更を止める）
#   - .claude/changelog/governance-log.jsonl: 承認の記録（読むだけ。merge-base の内容をそのまま先頭に含む追記だけを認める）
# outputs:
#   - stdout: summary 行、または --report の JSON（base・changes・blocked）
#   - stderr: BLOCK の行 / ERROR の行
#   - exit: 0=承認済みか auto_apply の範囲だけ / 1=承認か cooldown が足りない変更がある（CI block） / 2=usage の誤り・policy や governance-log を読めない（壊れた行・merge-base からの追記以外の変更を含む）・git の失敗
# requires-python: ">=3.9"
# dependencies: []
# contexts: [E, C]
# network: false
# write-scope: none
# ///
"""33章 Change Governance の自動分類器。

git diff <base>...HEAD の変更ファイルを governance-policy.json の change_categories に従って
P0/P1/P2/P3 に分類する。proposal_required の分類で承認が無い、または cooldown 中なら exit 1
（CI block）。

usage:
  python3 scripts/guard-change-category.py [--base origin/main] [--policy ABSOLUTE_POLICY_JSON]
      [--proposal-id ID] [--report] [--bypass-cooldown]

変更ファイルの一覧:
  git diff --name-status -z で読むので、core.quotePath の設定によらず非 ASCII のパス（06・27・
  28・33章など）をそのまま分類する。リネームは元のパスも変更に数える（元のパスは削除と同じ扱い）。
  merge-base に無かった plugins/<名前>/ の下の変更は、manifest の有無によらず新規 plugin（P0）。
  plugin ディレクトリのリネームも新規 plugin になる。SKILL.md の公開名の変更（P0）は frontmatter
  の name の前後を比べて判定し、本文のコードブロックにある name: 行は数えない。この判定の git diff
  は --no-color --no-ext-diff --no-textconv で呼び、手元の color.ui や diff.external の設定で
  hunk を読み違えない。governance-policy.json 自身の変更は、policy の分類によらず P1 以上とする。

判定の拠り所:
  policy（--policy の省略時）と governance-log は、PR の HEAD ではなく merge-base を基準にする。
  HEAD の内容を信じると、同じ PR の中で P0/P1 の workflow を auto_apply に書き換えたり、以前の
  変更の行を governance-log から消したりして、ゲートを外せるため。
  - policy は merge-base の内容（git cat-file blob <merge-base>:<path>）で判定する。merge-base に
    その path が無いとき（policy を初めて入れる PR）だけ、作業ツリーの file を使う。作業ツリーの
    policy も従来どおり読めて正しい形であることが要る（壊した policy を merge させない）。
  - governance-log は、作業ツリーの内容が merge-base の内容をそのまま先頭に含む（追記だけ）こと
    が要る。既存の行の削除や書き換えは exit 2。merge-base に無ければ確かめない。
  - 差分が空なら merge-base を見ない（判定する変更が無い）。
  rubric-registry.json の分類は変えていない（P1 に上げるかは 33章の改訂で決める）。

承認（.claude/changelog/governance-log.jsonl の entry）:
  - status が approved（省略時も approved）で、approver に auto と pending を含まない（大文字と
    小文字、末尾の括弧書きは区別しない）。approver は文字列か文字列の配列で、"A + B" は2名。
  - 承認者の人数は policy の change_categories.<分類>.approver の人数以上が要る（P0 の
    "team-skills + solo_operator (両方)" なら2名、P1 は1名）。
  - target_path が対象パスを含み、--proposal-id を付けたときはその proposal_id を持つ。
    target_sha256 があれば現物との一致が要り、--proposal-id が無いときは target_sha256 が必須。
  - target_sha256 の値が null のパスは削除の承認で、そのパスにファイルが無いときだけ一致とみなす。
  提案者と承認者が同じかは見ない。33章と policy に規定が無く、solo_operator の運用では人が提案と
  承認を兼ねるため。自己採点罠は approver=auto の拒否で防ぐ。

cooldown:
  同じ対象パスへの以前の変更（いま照合している承認以外の entry）から policy の日数が過ぎて
  いなければ違反。例外は承認済みの incident_fix=true だけで、--bypass-cooldown もそのときだけ通す。
  --bypass-cooldown は cooldown のある分類にだけ効き、cooldown「なし」の分類（P2・P3 など）は
  flag の有無で結果を変えない。governance-log の JSON として読めない行や object でない行は、
  黙って飛ばさず設定エラー（exit 2）にする（以前の変更の行が壊れると cooldown が素通りになるため）。
  timestamp の無い古い entry は数えない。同じ proposal_id の古い entry（直した後に target_sha256
  を付け直す前の承認）も以前の変更に数える。除くと proposal_id の使い回しで cooldown を逃れられる
  ので、扱いを変えるには 33章の改訂が要る。

exit code:
  0 承認済み or auto_apply 範囲のみ
  1 proposal/承認が必要な変更を検出 (CI block)
  2 usage の誤り、設定エラー（policy・governance-log を読めない、governance-log に壊れた行が
    ある、governance-log が merge-base から追記以外の形で変わった、cooldown の日数や timestamp を
    読めない）、または git の失敗（base が無い、shallow clone で merge-base が取れない等）。
    空の差分や読めない設定を「変更なし」「cooldown なし」に畳まない。
"""
from __future__ import annotations

import argparse
import datetime
import fnmatch
import hashlib
import json
import os
import pathlib
import re
import subprocess
import sys

POLICY_REL_PATH = "plugins/skill-governance-config/config/governance-policy.json"
POLICY_PATH_CANDIDATES = (pathlib.Path(POLICY_REL_PATH),)
CHANGELOG_PATH = pathlib.Path(".claude/changelog/governance-log.jsonl")


class GitDiffError(RuntimeError):
    """git が失敗した。変更なしとして扱わず、呼び出し側で exit 2 にする。"""


class ConfigError(RuntimeError):
    """policy や governance-log を読めない。承認なし・cooldown なしに畳まず exit 2 にする。"""


def _git(args: list[str]) -> str:
    try:
        return subprocess.check_output(["git", *args], encoding="utf-8", errors="surrogateescape")
    except (subprocess.CalledProcessError, OSError) as exc:
        raise GitDiffError(f"git {' '.join(args)} failed: {exc}") from exc


def _git_bytes(args: list[str]) -> bytes:
    """改行を変換せずに読む（governance-log の先頭一致を byte で比べるため）。"""
    try:
        return subprocess.check_output(["git", *args])
    except (subprocess.CalledProcessError, OSError) as exc:
        raise GitDiffError(f"git {' '.join(args)} failed: {exc}") from exc


def _merge_base(base: str) -> str:
    return _git(["merge-base", base, "HEAD"]).strip()


def _blob_at(rev: str, path: str) -> bytes | None:
    """rev の時点の path の中身。その時点に path が無ければ None。"""
    listed = _git(["ls-tree", "-z", "--name-only", rev, "--", path]).split("\0")
    if path not in listed:
        return None
    return _git_bytes(["cat-file", "blob", f"{rev}:{path}"])


def _name_status(base: str) -> list[tuple[str, str]]:
    """(status, path) の一覧。リネームは元のパスも含める（元のパスは消えている）。"""
    tokens = _git(["diff", "--name-status", "-z", f"{base}...HEAD"]).split("\0")
    if tokens[-1] == "":
        tokens.pop()
    pairs = []
    i = 0
    while i < len(tokens):
        status = tokens[i]
        width = 2 if status[:1] in ("R", "C") else 1
        paths = tokens[i + 1:i + 1 + width]
        if not status or len(paths) != width or not all(paths):
            raise GitDiffError(f"git diff --name-status -z の出力を読めない: {tokens[i:i + 1 + width]!r}")
        if status[:1] == "R":
            pairs.append((status, paths[0]))
        pairs.append((status, paths[-1]))
        i += 1 + width
    return pairs


def changed_files(base: str) -> list[str]:
    return [path for _, path in _name_status(base)]


def changed_file_statuses(base: str) -> dict[str, str]:
    return {path: status for status, path in _name_status(base)}


def _plugin_root(path: str) -> str | None:
    match = re.match(r"plugins/[^/]+(?=/)", path)
    return match.group(0) if match else None


def _base_plugin_dirs(base: str) -> set[str]:
    """merge-base の時点で plugins/ の下にあったディレクトリ。"""
    out = _git(["ls-tree", "-d", "-z", "--name-only", _merge_base(base), "plugins/"])
    return {path for path in out.split("\0") if path}


_SKILL_DIR_RE = re.compile(r"^plugins/[a-z0-9][a-z0-9-]*/skills/([a-z0-9][a-z0-9-]*)/")
_SKILL_MD_RE = re.compile(r"^plugins/[a-z0-9][a-z0-9-]*/skills/[a-z0-9][a-z0-9-]*/SKILL\.md$")
_SINK_ADAPTER_RE = re.compile(r"^(?:scripts|plugins/skill-governance-adapters/scripts)/adapters/sink_[a-z0-9_]+\.py$")
_P1_DOC_PATHS = (
    "doc/ClaudeCodeスキルの設計書/06-classification-and-naming",
    "doc/ClaudeCodeスキルの設計書/27-rubric-governance-runbook",
    "doc/ClaudeCodeスキルの設計書/28-script-execution-model",
    "doc/ClaudeCodeスキルの設計書/33-change-governance",
)
_P3_SUFFIXES = (".gitignore", ".editorconfig")


def _frontmatter_name(lines: list[str]) -> str | None:
    """先頭の --- から次の --- までにある name の値。無ければ None。"""
    if not lines or lines[0].rstrip() != "---":
        return None
    for line in lines[1:]:
        if line.rstrip() == "---":
            return None
        match = re.match(r"name:\s*(.*?)\s*$", line)
        if match:
            return match.group(1).strip("'\"")
    return None


def _name_field_changed(path: str, base: str = "HEAD") -> bool:
    """SKILL.md の frontmatter の name が変わったか (P0_breaking)。

    全文を文脈にした差分から変更前と変更後の本文を組み立て、frontmatter の name どうしを比べる。
    本文のコードブロックにある name: 行は数えない。
    """
    out = _git(["diff", "--no-color", "--no-ext-diff", "--no-textconv", "--unified=1000000",
                base, "--", path])
    old, new, in_hunk = [], [], False
    for line in out.split("\n"):
        if line.startswith("@@"):
            if in_hunk:
                break  # 文脈が全文なので、frontmatter は最初の hunk にある
            in_hunk = True
        elif in_hunk and line[:1] in (" ", "-", "+"):
            if line[:1] != "+":
                old.append(line[1:])
            if line[:1] != "-":
                new.append(line[1:])
    return in_hunk and _frontmatter_name(old) != _frontmatter_name(new)


def classify_change(path: str, status: str = "", *, name_changed: bool | None = None,
                    new_plugin: bool = False) -> str:
    """変更パスから P0/P1/P2/P3 を推定する (33章 Change Governance)。

    fallback は P2_content (Goodhart 罠回避のため P3 にしない)。
    Phase 0 省略検出: plugins/ 配下の新規ディレクトリは P0_breaking 扱いとする。
    """
    if new_plugin and path.startswith("plugins/"):
        return "P0_breaking"
    # Sink Contract I/F 変更
    if _SINK_ADAPTER_RE.match(path):
        return "P0_breaking"
    # ゲート自身の判定の拠り所。policy の分類で auto_apply に下げられないようにする
    if path == POLICY_REL_PATH:
        return "P1_structural"
    # 新 Skill 追加/削除/rename は git status で判定する。作業ツリー存在有無は追加後に True になるため使わない。
    if _SKILL_MD_RE.match(path) and status[:1] in {"A", "D", "R"}:
        return "P1_structural"
    # name の追加行は新 Skill の必須項目で、既存の公開名変更とは異なる。
    if _SKILL_DIR_RE.match(path) and path.endswith("/SKILL.md"):
        changed = _name_field_changed(path) if name_changed is None else name_changed
        return "P0_breaking" if changed else "P2_content"
    # 命名規則 / governance / script モデル / change governance ドキュメント
    if any(path.startswith(p) for p in _P1_DOC_PATHS):
        return "P1_structural"
    # manifest forbidden_dependencies
    if path.endswith(("/.claude-plugin/plugin.json", "/.codex-plugin/plugin.json")):
        return "P1_structural"
    # rubric 本体
    if path.endswith("/rubric.json"):
        return "P1_structural"
    # cosmetic
    if path.endswith(_P3_SUFFIXES):
        return "P3_cosmetic"
    # ドキュメント本文 / references / examples / templates
    if (
        path.startswith("doc/")
        or "/references/" in path
        or "/examples/" in path
        or "/templates/" in path
    ):
        return "P2_content"
    return "P2_content"


def load_policy(explicit_path: pathlib.Path | None = None):
    if explicit_path is not None and not explicit_path.is_absolute():
        print("ERROR: --policy requires an observed absolute path", file=sys.stderr)
        raise SystemExit(2)
    candidates = [explicit_path] if explicit_path is not None else POLICY_PATH_CANDIDATES
    for policy_path in candidates:
        if policy_path.is_file():
            try:
                policy = json.loads(policy_path.read_text(encoding="utf-8"))
            except (OSError, ValueError, RecursionError) as exc:
                print(f"ERROR: policy cannot be read: {exc}", file=sys.stderr)
                raise SystemExit(2)
            problem = _policy_problem(policy)
            if problem:
                print(f"ERROR: policy category/cooldown contract is invalid: {problem}", file=sys.stderr)
                raise SystemExit(2)
            return policy
    print("ERROR: policy not found at any of: " + ", ".join(str(p) for p in candidates), file=sys.stderr)
    raise SystemExit(2)


def _policy_problem(policy) -> str | None:
    if (not isinstance(policy, dict)
            or not isinstance(policy.get("change_categories"), dict)
            or not policy["change_categories"]
            or not isinstance(policy.get("cooldown_rules"), dict)):
        return "change_categories と cooldown_rules が object でない"
    for category in policy["change_categories"]:
        try:
            needs_proposal(category, policy)
            required_approver_count(category, policy)
            if category in policy["cooldown_rules"]:
                _cooldown_days(policy["cooldown_rules"][category])
        except ConfigError as exc:
            return str(exc)
    return None


def load_base_policy(merge_base: str) -> dict | None:
    """merge-base の時点の policy。merge-base に無い（初めて入れる PR）ときは None。

    PR の HEAD の policy で判定すると、同じ PR で分類の workflow を auto_apply に書き換えて
    ゲートを外せる。だから --policy の省略時は merge-base の内容を判定に使う。
    """
    for candidate in POLICY_PATH_CANDIDATES:
        if candidate.is_absolute():
            continue  # repo の中の path ではない（test が差し替えた file など）
        raw = _blob_at(merge_base, candidate.as_posix())
        if raw is None:
            continue
        try:
            policy = json.loads(raw.decode("utf-8"))
        except (UnicodeDecodeError, ValueError, RecursionError) as exc:
            raise ConfigError(f"merge-base の {candidate} を読めない: {exc}") from exc
        problem = _policy_problem(policy)
        if problem:
            raise ConfigError(f"merge-base の {candidate} の category/cooldown contract が不正: {problem}")
        return policy
    return None


def check_changelog_append_only(merge_base: str) -> None:
    """governance-log が merge-base の内容をそのまま先頭に含む（追記だけ）か。違えば ConfigError。

    以前の変更の行を消すと、その変更の cooldown が外れる。merge-base に無ければ確かめない。
    """
    if CHANGELOG_PATH.is_absolute():
        return  # repo の中の path ではない（test が差し替えた file など）
    base = _blob_at(merge_base, CHANGELOG_PATH.as_posix())
    if base is None:
        return
    try:
        current = CHANGELOG_PATH.read_bytes()
    except OSError as exc:
        raise ConfigError(f"{CHANGELOG_PATH} を読めない: {exc}") from exc
    if not current.startswith(base):
        raise ConfigError(f"{CHANGELOG_PATH} が merge-base から追記以外の形で変わった"
                          "（既存の行の削除・書き換え・並べ替えは認めない）")


def _rule_text(category: str, policy: dict, key: str) -> str:
    rule = policy.get("change_categories", {}).get(category, {})
    value = rule.get(key, "") if isinstance(rule, dict) else None
    if not isinstance(value, str):
        raise ConfigError(f"change_categories.{category}.{key} が文字列でない")
    return value


def needs_proposal(category: str, policy: dict) -> bool:
    return "proposal_required" in _rule_text(category, policy, "workflow")


_NAME_TOKEN = re.compile(r"[(（)）]|\s+\+\s+")
_TRAILING_NOTE = re.compile(r"\s*[（(].*$")
_NON_APPROVERS = {"auto", "pending"}


def _split_names(text: str) -> list[str]:
    """括弧の外にある " + " だけで区切る（"X (review + 承認)" は1名）。"""
    parts, depth, start = [], 0, 0
    for token in _NAME_TOKEN.finditer(text):
        if token.group(0) in "(（":
            depth += 1
        elif token.group(0) in ")）":
            depth = max(0, depth - 1)
        elif depth == 0:
            parts.append(text[start:token.start()])
            start = token.end()
    parts.append(text[start:])
    return parts


def _names(text: str) -> list[str]:
    """"A + B (注記)" を ["A", "B"] にする。末尾の括弧書きは外し、大文字と小文字の違いは同じ名前とみなす。"""
    names: list[str] = []
    for part in _split_names(text):
        name = _TRAILING_NOTE.sub("", part).strip()
        if name and name.casefold() not in {n.casefold() for n in names}:
            names.append(name)
    return names


def required_approver_count(category: str, policy: dict) -> int:
    """policy の approver（"team-skills + solo_operator (両方)" なら2名）が求める承認者の人数。"""
    return max(1, len(_names(_rule_text(category, policy, "approver"))))


def _approver_names(raw) -> list[str]:
    """entry の承認者。読めない値、空の名前、auto・pending を含む値は [] (承認なし)。"""
    parts = [raw] if isinstance(raw, str) else raw if isinstance(raw, list) else []
    if not all(isinstance(part, str) and _names(part) for part in parts):
        return []
    names = _names(" + ".join(parts))
    return [] if any(n.casefold() in _NON_APPROVERS for n in names) else names


def _entries() -> list[dict]:
    if not CHANGELOG_PATH.exists():
        return []
    try:
        text = CHANGELOG_PATH.read_text(encoding="utf-8")
    except (OSError, UnicodeDecodeError) as exc:
        raise ConfigError(f"{CHANGELOG_PATH} を読めない: {exc}") from exc
    entries = []
    # splitlines は U+2028 などでも区切るので、JSON の文字列の中で行が割れないよう \n で区切る
    for number, line in enumerate(text.split("\n"), start=1):
        line = line.strip()
        if not line:
            continue
        try:
            entry = json.loads(line)
        except (ValueError, RecursionError) as exc:
            raise ConfigError(f"{CHANGELOG_PATH} の {number} 行目が JSON として読めない: {exc}") from exc
        if not isinstance(entry, dict):
            raise ConfigError(f"{CHANGELOG_PATH} の {number} 行目が object でない")
        entries.append(entry)
    return entries


def _matches_target(target_path: str, entry: dict) -> bool:
    """Use the same file/directory/glob semantics for scalar and list targets."""
    targets = entry.get("target_path", [])
    if isinstance(targets, str):
        targets = targets.split(" + ")  # legacy logs used a human-readable list
    if not isinstance(targets, list):
        return False
    path = pathlib.PurePosixPath(target_path.replace("\\", "/")).as_posix()
    for target in targets:
        if not isinstance(target, str):
            continue
        target = re.sub(r"\s+[（(].*$", "", target).strip().replace("\\", "/").rstrip("/")
        if not target:
            continue
        if path == target or path.startswith(target + "/") or fnmatch.fnmatchcase(path, target):
            return True
    return False


def _approved(entry: dict, min_approvers: int = 1) -> bool:
    return (len(_approver_names(entry.get("approver"))) >= max(1, min_approvers)
            and entry.get("status", "approved") == "approved")


def _approved_current_content(target_path: str, entry: dict) -> bool:
    """target_sha256 がこの対象の現物と一致するか。値が null なら削除の承認で、ファイルが無いときだけ一致。"""
    hashes = entry.get("target_sha256")
    if not isinstance(hashes, dict) or target_path not in hashes:
        return False
    expected = hashes[target_path]
    if expected is None:
        return not os.path.lexists(target_path)
    if not isinstance(expected, str):
        return False
    try:
        return hashlib.sha256(pathlib.Path(target_path).read_bytes()).hexdigest() == expected
    except OSError:
        return False


def _is_current(target_path: str, entry: dict, proposal_id: str | None, min_approvers: int) -> bool:
    """いま照合している変更の承認か。--proposal-id があればその提案、無ければ現物に束縛された承認。"""
    if not (_approved(entry, min_approvers) and _matches_target(target_path, entry)):
        return False
    if proposal_id is None:
        return _approved_current_content(target_path, entry)
    return (entry.get("proposal_id") == proposal_id
            and ("target_sha256" not in entry or _approved_current_content(target_path, entry)))


def has_recent_changelog(target_path: str, proposal_id: str | None = None, min_approvers: int = 1) -> bool:
    return any(_is_current(target_path, e, proposal_id, min_approvers) for e in _entries())


def _cooldown_days(value) -> int | None:
    """cooldown_rules の値を日数にする。"なし" は None。数字の無い値は cooldown なしに畳まず ConfigError。"""
    if value == "なし":
        return None
    match = re.search(r"\d+", value) if isinstance(value, str) else None
    if match is None:
        raise ConfigError(f"cooldown の日数を読めない: {value!r}（\"なし\" か数字を含む文字列にする）")
    return int(match.group(0))


def _entry_time(entry: dict) -> datetime.datetime | None:
    """entry の timestamp（空なら ts）。無い古い entry は None。読めない値は ConfigError。"""
    raw = entry.get("timestamp")
    if raw is None or raw == "":
        raw = entry.get("ts")
    if raw is None or raw == "":
        return None
    try:
        if not isinstance(raw, str):
            raise ValueError("not a string")
        ts = datetime.datetime.fromisoformat(raw.replace("Z", "+00:00"))
    except ValueError as exc:
        raise ConfigError(f"governance-log の timestamp を読めない: {raw!r}") from exc
    return ts if ts.tzinfo is not None else ts.replace(tzinfo=datetime.timezone.utc)


def check_cooldown(target_path: str, category: str, policy: dict, bypass: bool = False,
                   proposal_id: str | None = None) -> bool:
    """cooldown_rules に従い、直近変更から規定日数を過ぎているか確認する。

    戻り値: True=OK（cooldown クリア or 対象外）、False=cooldown 違反
    --bypass-cooldown は cooldown のある分類にだけ効き、現物に束縛された承認済み incident 修正の
    場合だけ許可する。cooldown の無い分類では bypass の有無で結果を変えない。
    """
    entries = _entries()
    cooldown_days = _cooldown_days(policy.get("cooldown_rules", {}).get(category, "なし"))
    if cooldown_days is None:
        return True
    min_approvers = required_approver_count(category, policy)
    current = [e for e in entries if _is_current(target_path, e, proposal_id, min_approvers)]
    approved_incident = any(e.get("incident_fix") is True for e in current)
    if bypass:
        return approved_incident
    # Only the policy's approved incident exception can bypass an earlier change.
    if approved_incident:
        return True
    now = datetime.datetime.now(datetime.timezone.utc)
    for entry in entries:
        if entry in current or not _matches_target(target_path, entry):
            continue  # the operation being checked is not a previous operation
        ts = _entry_time(entry)
        if ts is not None and (now - ts).total_seconds() < cooldown_days * 86400:
            return False  # cooldown 違反
    return True


_UNSAFE_REF = re.compile(r"^-|\.\.|[\s\x00-\x1f\x7f]")


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="guard-change-category.py", allow_abbrev=False,
        description="git diff <base>...HEAD の変更を P0〜P3 に分類し、承認と cooldown を照合する（33章）。",
        epilog="Installed usage: resolve skill-governance-config root and pass its "
               "config/governance-policy.json with --policy. Bypass requires current approved incident content.")
    parser.add_argument("--policy", type=pathlib.Path, help="governance-policy.json の絶対パス")
    parser.add_argument("--base", default="origin/main", help="比べる ref（既定 origin/main）")
    parser.add_argument("--report", action="store_true", help="判定を JSON で出す")
    parser.add_argument("--proposal-id", help="この変更を承認した entry の proposal_id")
    parser.add_argument("--bypass-cooldown", action="store_true",
                        help="承認済みの incident_fix=true があるときだけ cooldown を飛ばす")
    return parser


def main(argv) -> int:
    for stream in (sys.stdout, sys.stderr):
        try:  # 非 UTF-8 のパスや ascii の端末でも、出力の途中で traceback にしない
            stream.reconfigure(errors="backslashreplace")
        except (AttributeError, ValueError, OSError):
            pass
    try:
        args = _parser().parse_args(argv[1:])
    except SystemExit as exc:  # --help は 0、usage の誤りは argparse が 2
        return exc.code if isinstance(exc.code, int) else 2
    if not args.base or _UNSAFE_REF.search(args.base):
        print(f"ERROR: --base に使えない ref: {args.base!r}（空・- で始まる・.. や空白を含む値は"
              " git の option や範囲として読まれる）", file=sys.stderr)
        return 2
    if args.proposal_id is not None and not args.proposal_id.strip():
        print("ERROR: --proposal-id が空", file=sys.stderr)
        return 2
    explicit = args.policy is not None
    # 作業ツリーの policy も読めて正しい形であることを確かめる（壊した policy を merge させない）
    policy = load_policy(args.policy) if explicit else load_policy()
    try:
        return _evaluate(policy, args.base, args.report, args.bypass_cooldown, args.proposal_id,
                         use_base_policy=not explicit)
    except (GitDiffError, ConfigError) as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        return 2


def _evaluate(policy: dict, base: str, report: bool, bypass_cooldown: bool,
              proposal_id: str | None, use_base_policy: bool = False) -> int:
    files = changed_files(base)
    statuses = changed_file_statuses(base)
    if files:
        # 判定の拠り所は PR の HEAD ではなく merge-base（同じ PR でゲートを外させない）
        merge_base = _merge_base(base)
        if use_base_policy:
            base_policy = load_base_policy(merge_base)
            if base_policy is not None:
                policy = base_policy
        check_changelog_append_only(merge_base)
    roots = {root for root in map(_plugin_root, files) if root}
    new_plugins = roots - _base_plugin_dirs(base) if roots else set()
    results = []
    blocked = []
    for f in files:
        status = statuses.get(f, "")
        name_changed = (_name_field_changed(f, f"{base}...HEAD")
                        if _SKILL_MD_RE.match(f) and status[:1] not in {"A", "D", "R"} else False)
        cat = classify_change(f, status, name_changed=name_changed, new_plugin=_plugin_root(f) in new_plugins)
        proposal = needs_proposal(cat, policy)
        min_approvers = required_approver_count(cat, policy)
        approved = has_recent_changelog(f, proposal_id, min_approvers) if proposal else True
        cooldown_ok = check_cooldown(f, cat, policy, bypass=bypass_cooldown, proposal_id=proposal_id)
        results.append({"path": f, "category": cat, "proposal_required": proposal, "approved": approved, "cooldown_ok": cooldown_ok})
        if proposal and not approved:
            reason = "proposal/承認 changelog 未記録"
            if min_approvers > 1:
                reason += f"（承認者 {min_approvers} 名以上が要る）"
            blocked.append({"path": f, "category": cat, "reason": reason})
        elif not cooldown_ok and bypass_cooldown:
            blocked.append({"path": f, "category": cat, "reason": f"--bypass-cooldown を使えない"
                            f"（{cat} の現物に束縛された承認済み incident_fix が無い）"})
        elif not cooldown_ok:
            blocked.append({"path": f, "category": cat, "reason": f"cooldown 違反（{cat} は cooldown 期間中）"})
    if report:
        print(json.dumps({
            "base": base,
            "changes": results,
            "blocked": blocked,
        }, indent=2, ensure_ascii=False))
    else:
        for b in blocked:
            reason = b.get("reason", "proposal/承認 changelog 未記録")
            print(f"BLOCK {b['path']} ({b['category']}): {reason}", file=sys.stderr)
        print(f"summary: total={len(results)} blocked={len(blocked)}")
    return 1 if blocked else 0


if __name__ == "__main__":
    sys.exit(main(sys.argv))
