#!/usr/bin/env python3
# /// script
# name: aggregate-issue-diffs
# purpose: 対象 issue に紐づく全未triage変更を完全な commit diff として時系列集約する決定論段。spec-diff-history.md の80行 preview はイベント日時の索引にだけ使い、対応する `chore: update yaml-spec-cache (<timestamp>)` commit と親 commit から完全 diff を復元する。欠落・曖昧照合・shallow clone・digest不一致は fail-closed (exit2)。
# inputs:
#   - argv: --issue NUMBER --events FILE [--since TIMESTAMP] [--repo-root DIR]
# outputs:
#   - stdout: JSON {entries[], latest_entry, untriaged_entries, source_provenance}
#   - stderr: violation メッセージ + 回復手順
#   - exit: 0=正常 / 1=一般エラー / 2=完全性違反 (missing/shallow/ambiguous/digest mismatch)
# contexts: [E, C]
# network: false
# write-scope: none
# dependencies: []
# requires-python: ">=3.10"
# ///
"""issue に紐づく未triage変更を完全 commit diff として時系列集約する決定論スクリプト。

設計:
  - events FILE は gh issue metadata/comment timestamps と spec-diff-history.md の
    見出し (`## <timestamp>`) を索引化した JSON。実 diff は events からは読まず、
    見出しに対応するローカル git commit pair (cache commit と親 commit) から復元する。
  - spec-diff-history.md の 80行 preview は「いつ変更が起きたか」の索引にだけ使い、
    復元する完全 diff の内容照合には使わない (preview は切り詰められているため)。
  - network=false のため不足 commit を自動 fetch しない。復元できない入力は判定せず
    fail-closed する (exit2)。

exit code:
  0  正常集約
  1  一般エラー (引数不正 / events 読取失敗 / JSON 破損 / git 環境不備)
  2  完全性違反 (shallow clone / commit 欠落 / 曖昧照合 / digest 不一致)
"""
from __future__ import annotations

import argparse
import datetime
import hashlib
import json
import subprocess
import sys
from pathlib import Path

# cache commit の subject テンプレート。history 見出し (timestamp) を差し込んで exact match する。
_CACHE_SUBJECT_TEMPLATE = "chore: update yaml-spec-cache ({heading})"

# 決定論的な git diff を得るためのフラグ。色/外部差分/textconv を無効化し、環境非依存にする。
_DIFF_FLAGS = ("-c", "color.ui=false", "diff", "--no-color", "--no-ext-diff", "--no-textconv")


class GeneralError(Exception):
    """exit 1 に対応する一般エラー。"""


class CompletenessError(Exception):
    """exit 2 に対応する完全性違反 (fail-closed)。"""


class _GitCommandError(Exception):
    """予期しない git コマンド失敗 (exit 1 扱い)。"""

    def __init__(self, cmd: list[str], proc: subprocess.CompletedProcess) -> None:
        self.cmd = cmd
        self.proc = proc
        stderr = (proc.stderr or "").strip()
        super().__init__(
            f"git コマンドが失敗しました (returncode={proc.returncode}): "
            f"{' '.join(cmd)}\n{stderr}"
        )


class _ArgumentParser(argparse.ArgumentParser):
    """引数不正時に exit 2 (argparse 既定) ではなく exit 1 (一般エラー) を返す。"""

    def error(self, message: str) -> "NoReturn":  # type: ignore[override]  # noqa: F821
        self.print_usage(sys.stderr)
        self.exit(1, f"{self.prog}: エラー: {message}\n")


def _build_parser() -> argparse.ArgumentParser:
    parser = _ArgumentParser(
        prog="aggregate-issue-diffs.py",
        description=(
            "issue に紐づく未triage変更を完全 commit diff として時系列集約する。"
            "spec-diff-history の見出しを索引にローカル git commit pair から完全 diff を復元する。"
        ),
    )
    parser.add_argument(
        "--issue",
        type=int,
        required=True,
        metavar="NUMBER",
        help="対象の issue 番号 (集約対象の識別に使う)。",
    )
    parser.add_argument(
        "--events",
        required=True,
        metavar="FILE",
        help="event 索引 JSON。各 event は event_at と history_heading を持つ。",
    )
    parser.add_argument(
        "--since",
        default=None,
        metavar="TIMESTAMP",
        help="この ISO8601 timestamp 以降 (>=) の event のみ集約する。",
    )
    parser.add_argument(
        "--repo-root",
        default=".",
        metavar="DIR",
        help="git 操作を行う repo root (既定: カレントディレクトリ)。",
    )
    return parser


def _parse_ts(value: str, *, label: str) -> datetime.datetime:
    """ISO8601 (末尾 Z 許容) を tz-aware datetime に変換する。naive は UTC とみなす。"""
    if not isinstance(value, str):
        raise GeneralError(f"{label} は文字列である必要があります: {value!r}")
    text = value.strip()
    if text.endswith("Z"):
        text = text[:-1] + "+00:00"
    try:
        parsed = datetime.datetime.fromisoformat(text)
    except ValueError as exc:
        raise GeneralError(
            f"{label} が ISO8601 timestamp として不正です: {value!r}"
        ) from exc
    if parsed.tzinfo is None:
        parsed = parsed.replace(tzinfo=datetime.timezone.utc)
    return parsed


def _git(repo_root: Path, args: tuple[str, ...] | list[str], *, check: bool = True) -> subprocess.CompletedProcess:
    """git を subprocess で実行する。stdlib only、network=false。"""
    cmd = ["git", "-C", str(repo_root), *args]
    try:
        proc = subprocess.run(cmd, capture_output=True, text=True)
    except FileNotFoundError as exc:  # git 未インストール
        raise GeneralError(
            "git 実行ファイルが見つかりません。git をインストールしてください。"
        ) from exc
    if check and proc.returncode != 0:
        raise _GitCommandError(cmd, proc)
    return proc


def _load_events(events_path: Path) -> list[dict]:
    """events JSON を読み込み、正規化した event dict の list を返す。"""
    try:
        raw = events_path.read_text(encoding="utf-8")
    except FileNotFoundError as exc:
        raise GeneralError(f"events ファイルが見つかりません: {events_path}") from exc
    except OSError as exc:
        raise GeneralError(f"events ファイルの読取に失敗しました: {events_path} ({exc})") from exc
    try:
        data = json.loads(raw)
    except json.JSONDecodeError as exc:
        raise GeneralError(
            f"events ファイルが JSON として不正です: {events_path} ({exc})"
        ) from exc

    if isinstance(data, dict):
        events = data.get("events")
    elif isinstance(data, list):
        events = data
    else:
        raise GeneralError(
            "events ファイルは object({events:[...]}) または array である必要があります。"
        )
    if not isinstance(events, list):
        raise GeneralError("events フィールドは配列である必要があります。")

    normalized: list[dict] = []
    for index, event in enumerate(events):
        if not isinstance(event, dict):
            raise GeneralError(f"events[{index}] は object である必要があります。")
        event_at = event.get("event_at")
        heading = event.get("history_heading")
        if not isinstance(event_at, str) or not event_at.strip():
            raise GeneralError(f"events[{index}].event_at が欠落しています。")
        if not isinstance(heading, str) or not heading.strip():
            raise GeneralError(f"events[{index}].history_heading が欠落しています。")
        triaged = bool(event.get("triaged", False))
        expected = event.get("expected_diff_sha256")
        if expected is not None and not isinstance(expected, str):
            raise GeneralError(
                f"events[{index}].expected_diff_sha256 は文字列である必要があります。"
            )
        normalized.append(
            {
                "event_at": event_at.strip(),
                "history_heading": heading.strip(),
                "triaged": triaged,
                "expected_diff_sha256": expected.strip() if isinstance(expected, str) else None,
            }
        )
    return normalized


def _ensure_git_repo(repo_root: Path) -> None:
    proc = _git(repo_root, ["rev-parse", "--git-dir"], check=False)
    if proc.returncode != 0:
        raise GeneralError(
            f"repo-root は git リポジトリではありません: {repo_root}\n"
            "回復手順: --repo-root に有効な git リポジトリを指定してください。"
        )


def _ensure_not_shallow(repo_root: Path) -> None:
    proc = _git(repo_root, ["rev-parse", "--is-shallow-repository"], check=False)
    if proc.returncode != 0:
        # 古い git などで判定不能な場合は完全性を保証できないため fail-closed。
        raise CompletenessError(
            "shallow 判定に失敗しました。完全 diff を保証できないため中断します。\n"
            "回復手順: 新しい git で `git fetch --unshallow` を実行し full history を確保してください。"
        )
    if proc.stdout.strip() == "true":
        raise CompletenessError(
            "shallow clone を検出しました。親 commit が grafted されているため完全 diff を復元できません。\n"
            "回復手順: `git fetch --unshallow` を実行して full history を復元してから再実行してください。"
        )


def _build_subject_index(repo_root: Path) -> dict[str, list[str]]:
    """全 ref を横断し subject -> [commit hash] の索引を作る (曖昧照合検出用)。"""
    proc = _git(repo_root, ["log", "--all", "--no-color", "--format=%H%x1f%s"])
    index: dict[str, list[str]] = {}
    for line in proc.stdout.splitlines():
        if not line:
            continue
        commit_hash, _, subject = line.partition("\x1f")
        bucket = index.setdefault(subject, [])
        if commit_hash not in bucket:  # 複数 ref から到達した同一 commit の重複を排除
            bucket.append(commit_hash)
    return index


def _resolve_commit_pair(
    repo_root: Path, heading: str, subject_index: dict[str, list[str]]
) -> tuple[str, str]:
    """history 見出しから (base_commit, source_commit) を確定する。fail-closed。"""
    subject = _CACHE_SUBJECT_TEMPLATE.format(heading=heading)
    hashes = subject_index.get(subject, [])
    if len(hashes) == 0:
        raise CompletenessError(
            f"曖昧照合: history 見出し '{heading}' に対応する cache commit が見つかりません (0件)。\n"
            f"  期待 subject: {subject}\n"
            "回復手順: network=false のため自動 fetch しません。"
            "対象 commit を含む ref を `git fetch` してから再実行してください。"
        )
    if len(hashes) > 1:
        raise CompletenessError(
            f"曖昧照合: history 見出し '{heading}' に {len(hashes)}件の cache commit が一致しました。\n"
            f"  期待 subject: {subject}\n"
            f"  候補: {', '.join(hashes)}\n"
            "回復手順: 一意に特定できないため fail-closed します。"
            "重複 subject を解消するか events 索引を修正してください。"
        )
    source_commit = hashes[0]

    parent = _git(repo_root, ["rev-parse", "--verify", "--quiet", f"{source_commit}^"], check=False)
    base_commit = parent.stdout.strip()
    if parent.returncode != 0 or not base_commit:
        raise CompletenessError(
            f"base commit 欠落: source commit {source_commit} に親 commit がありません "
            "(root commit または shallow boundary)。\n"
            "回復手順: `git fetch --unshallow` で full history を復元してから再実行してください。"
        )

    exists = _git(repo_root, ["cat-file", "-e", f"{base_commit}^{{commit}}"], check=False)
    if exists.returncode != 0:
        raise CompletenessError(
            f"base commit 欠落: 親 commit {base_commit} のオブジェクトがローカルに存在しません。\n"
            "回復手順: network=false のため自動 fetch しません。"
            "`git fetch` で対象 commit を取得してから再実行してください。"
        )
    return base_commit, source_commit


def _restore_diff(repo_root: Path, base_commit: str, source_commit: str) -> str:
    """base..source の完全 diff テキストを決定論的に復元する。"""
    proc = _git(repo_root, [*_DIFF_FLAGS, base_commit, source_commit])
    return proc.stdout


def _build_entry(repo_root: Path, event: dict, subject_index: dict[str, list[str]]) -> dict:
    heading = event["history_heading"]
    base_commit, source_commit = _resolve_commit_pair(repo_root, heading, subject_index)
    diff_text = _restore_diff(repo_root, base_commit, source_commit)
    digest = hashlib.sha256(diff_text.encode("utf-8")).hexdigest()

    expected = event["expected_diff_sha256"]
    if expected is not None and expected.lower() != digest:
        raise CompletenessError(
            f"digest 不一致: history 見出し '{heading}' の期待 sha256 と復元 diff の sha256 が一致しません。\n"
            f"  expected: {expected}\n"
            f"  restored: {digest}\n"
            f"  commit pair: {base_commit}..{source_commit}\n"
            "回復手順: cache commit が改変されたか events 索引が古い可能性があります。"
            "events を再生成するか対象 commit を確認してください。"
        )

    return {
        "event_at": event["event_at"],
        "history_heading": heading,
        "base_commit": base_commit,
        "source_commit": source_commit,
        "diff_sha256": digest,
        "complete": True,
        "diff": diff_text,
    }


def _aggregate(args: argparse.Namespace) -> dict:
    repo_root = Path(args.repo_root).resolve()
    events_path = Path(args.events).resolve()

    _ensure_git_repo(repo_root)
    _ensure_not_shallow(repo_root)

    events = _load_events(events_path)

    since_dt = _parse_ts(args.since, label="--since") if args.since else None
    subject_index = _build_subject_index(repo_root)

    prepared: list[tuple[tuple, dict]] = []
    for event in events:
        event_dt = _parse_ts(event["event_at"], label="event_at")
        if since_dt is not None and event_dt < since_dt:
            continue
        entry = _build_entry(repo_root, event, subject_index)
        # 決定論安定ソート用のキー: (時刻, 見出し, source commit)。
        sort_key = (event_dt, entry["history_heading"], entry["source_commit"])
        entry["_triaged"] = event["triaged"]
        prepared.append((sort_key, entry))

    prepared.sort(key=lambda item: item[0])

    entries: list[dict] = []
    untriaged_entries: list[dict] = []
    commit_pairs: list[dict] = []
    for _, entry in prepared:
        triaged = entry.pop("_triaged")
        entries.append(entry)
        if not triaged:
            untriaged_entries.append(entry)
        commit_pairs.append(
            {
                "history_heading": entry["history_heading"],
                "base_commit": entry["base_commit"],
                "source_commit": entry["source_commit"],
            }
        )

    latest_entry = entries[-1] if entries else None

    source_provenance = {
        "issue": args.issue,
        "repo_root": str(repo_root),
        "events_file": str(events_path),
        "since": args.since,
        "subject_template": _CACHE_SUBJECT_TEMPLATE,
        "network": False,
        "write_scope": "none",
        "generated_by": "aggregate-issue-diffs.py",
        "history_headings": [entry["history_heading"] for entry in entries],
        "commit_pairs": commit_pairs,
    }

    return {
        "entries": entries,
        "latest_entry": latest_entry,
        "untriaged_entries": untriaged_entries,
        "source_provenance": source_provenance,
    }


def main(argv: list[str] | None = None) -> int:
    parser = _build_parser()
    args = parser.parse_args(argv)
    try:
        result = _aggregate(args)
    except CompletenessError as exc:
        print(str(exc), file=sys.stderr)
        return 2
    except GeneralError as exc:
        print(str(exc), file=sys.stderr)
        return 1
    except _GitCommandError as exc:
        print(str(exc), file=sys.stderr)
        return 1
    sys.stdout.write(json.dumps(result, ensure_ascii=False, indent=2))
    sys.stdout.write("\n")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
