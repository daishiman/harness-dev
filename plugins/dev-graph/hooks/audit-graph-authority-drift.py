#!/usr/bin/env python3
# /// script
# name: audit-graph-authority-drift
# purpose: C10 が遮断できない間接書込みを PostToolUse で事後検出し、graph authority の drift を報告する。
# inputs: ["stdin: Claude hook JSON", "argv: --repo-root PATH [--ledger PATH]"]
# outputs: ["stdout: JSON receipt (advisory 時のみ)", "stderr: warning", "exit 0 clean/advisory", "exit 2 confirmed drift"]
# requires-python: ">=3.11"
# dependencies: ["lib/graph_envelope.py"]
# contexts: [E]
# network: false
# write-scope: the caller repository .dev-graph/tmp/authority-audit.json only
# ///
"""graph authority の事後 drift 監査 (HarnessHub-kzth)。

C10 PreToolUse (`guard-graph-schema.py`) は「interpreter 起動 x 書込み動詞 x authority
path」の共起をコマンド文字列から読んで遮断する。書込みを別 script file へ移した間接起動は
この 3 条件がコマンド文字列上で 1 つも成立しないため、PreToolUse では原理的に閉じられない。
遮断強度を上げようとして hook 側で script の中身を読みに行くと、HarnessHub-6in4 で実測した
fail-open 窓 (Bash 枝 39.79s / timeout で素通り) が再発するため、その方向は採らない。

そこでこの hook は遮断ではなく事後検出を担う。判定は「誰が書いたか」ではなく
「書かれた結果が正規 writer の残す形か」に置く。中核は graph_revision の不変条件で、
C02 writer は 1 回の書込みにつき必ず +1 する (build-graph-node.py / register-package.py)。したがって
「内容が変わったのに revision が進んでいない」は、正規 writer では起こり得ない形であり、
迂回書込みの決定的な痕跡になる。

判定の強さは 2 段に分ける。

- ``confirmed``  正規 writer では成立し得ない形。exit 2 + stderr で agent へ差し戻す。
  (revision 据置・envelope 逸脱・authority の消失・parse 不能)
- ``advisory``   正規運用でも起こり得る弱い痕跡。exit 0 のまま receipt に載せる。
  (コマンド文字列に sanctioned writer 名が現れない、VCS 操作に伴う revision 後退)

VCS 操作 (checkout/merge/rebase 等) は履歴の移動なので revision が後退し得る。これを
confirmed にすると日常操作が毎回赤くなり、監査そのものが無視されるため advisory に落とす。

**この監査でも検出できない範囲**: 迂回書込みが revision を正しく +1 し、envelope も
canonical に保った場合は、結果の形が正規 writer と区別できないため通過する。そこは
C11 (`validate-graph-schema.py`) の node 検査と、レビュー時の graph diff が受け持つ。
遮断・事後検出・store 検証のいずれもが単独では閉じないことは
`references/claude-code-hooks-contract.md` に契約として明記してある。

台帳は保護対象外の ``.dev-graph/tmp/`` に置く。state/ や config.json へ置くと監査自身の
書込みが C10 の保護対象を叩き、監査を回すたびに guard の判定材料を汚すことになる。
"""
from __future__ import annotations

import argparse
import hashlib
import json
import os
import re
import shlex
import sys
import tempfile
from pathlib import Path
from typing import Any

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE.parent / "lib"))
sys.dont_write_bytecode = True

from graph_envelope import envelope_violations  # noqa: E402

LEDGER_RELATIVE = Path(".dev-graph") / "tmp" / "authority-audit.json"
GRAPH_RELATIVE = ".dev-graph/state/graph.json"
CONFIG_RELATIVE = ".dev-graph/config.json"
AUDITED_PATHS = (GRAPH_RELATIVE, CONFIG_RELATIVE)
LEDGER_VERSION = "1.0.0"
MAX_COMMAND_LENGTH = 32_768
# 2MB 級の store を想定した上限。これを超える authority は digest 計算を諦めて advisory にする
# (監査のために hook が数秒止まるほうが運用上の害が大きい)。
MAX_AUDITED_BYTES = 64 * 1024 * 1024
READ_CHUNK = 1 << 20

# graph.json / config.json を書く正規経路の名前。直接 atomic_json を呼ぶ writer だけでなく、
# それらを subprocess 起動する側 (reconcile-*-lifecycle) も含める。コマンド文字列に現れる
# のは最外殻の名前だけなので、内側の writer 名しか許さないと正規運用が advisory で埋まる。
SANCTIONED_WRITERS = {
    GRAPH_RELATIVE: re.compile(
        r"(?:^|[^\w.-])(?:build-graph-node|build-init-scaffold|build-merged-graph|register-package"
        r"|reconcile-github-lifecycle|reconcile-task-lifecycle)\.py(?:$|[^\w-])"
    ),
    CONFIG_RELATIVE: re.compile(
        r"(?:^|[^\w.-])(?:build-init-scaffold|build-project-hook-fallback)\.py(?:$|[^\w-])"
    ),
}

VCS_TRANSITIONS = {
    "checkout", "switch", "merge", "rebase", "pull", "reset", "stash", "restore",
    "clone", "worktree", "am", "cherry-pick", "revert", "apply", "bisect",
}
VCS_READ_ONLY = {"status", "diff", "log", "rev-parse", "show", "branch", "tag"}
SHELL_SEPARATORS = {"&&", "||", ";", "|", "&"}


def _vcs_transition_only(command: str) -> bool:
    """全 shell segment が git で、うち 1 つ以上が履歴移動なら True。

    単なる regex 共起だと ``git checkout main && python3 writer.py`` まで VCS 操作扱いになり、
    後半の迂回書込みによる revision 後退を advisory へ落としてしまう。引用符を理解する
    ``shlex`` で segment を分け、非 git command が 1 つでも混ざれば緩和しない。
    """
    if not command.strip() or "$(" in command or "`" in command or "\n" in command:
        return False
    try:
        lexer = shlex.shlex(command, posix=True, punctuation_chars=";&|")
        lexer.whitespace_split = True
        lexer.commenters = ""
        tokens = list(lexer)
    except ValueError:
        return False

    segments: list[list[str]] = [[]]
    for token in tokens:
        if token in SHELL_SEPARATORS:
            if not segments[-1]:
                return False
            segments.append([])
        else:
            segments[-1].append(token)
    if not segments or not segments[-1]:
        return False

    saw_transition = False
    for segment in segments:
        index = 0
        if segment[index] == "command":
            index += 1
        if index >= len(segment) or Path(segment[index]).name != "git":
            return False
        index += 1
        while index < len(segment):
            token = segment[index]
            if token in {"--no-pager", "--paginate", "--literal-pathspecs", "--no-optional-locks"}:
                index += 1
                continue
            if token in {"-C", "--git-dir", "--work-tree"}:
                index += 2
                continue
            if token.startswith("--git-dir=") or token.startswith("--work-tree="):
                index += 1
                continue
            # ``git -c alias.x='!writer' x`` は任意 command を実行できるので VCS-only にしない。
            if token.startswith("-"):
                return False
            break
        if index >= len(segment):
            return False
        subcommand = segment[index]
        if subcommand in VCS_TRANSITIONS:
            saw_transition = True
        elif subcommand not in VCS_READ_ONLY:
            return False
    return saw_transition


def read_payload() -> dict[str, Any]:
    try:
        value = json.load(sys.stdin)
    except Exception:
        return {}
    return value if isinstance(value, dict) else {}


def command_of(payload: dict[str, Any]) -> str:
    tool_input = payload.get("tool_input")
    if not isinstance(tool_input, dict):
        return ""
    command = tool_input.get("command")
    return str(command)[:MAX_COMMAND_LENGTH] if isinstance(command, str) else ""


def _finding(path: str, code: str, severity: str, detail: str) -> dict[str, str]:
    return {"path": path, "code": code, "severity": severity, "detail": detail}


def _stat_snapshot(path: Path) -> dict[str, Any]:
    try:
        stat = path.stat()
    except FileNotFoundError:
        return {"exists": False}
    except OSError as exc:
        return {"exists": False, "stat_error": str(exc)}
    return {
        "exists": True,
        "size": stat.st_size,
        "mtime_ns": stat.st_mtime_ns,
        "ctime_ns": stat.st_ctime_ns,
    }


def _stat_identical(baseline: dict[str, Any], snapshot: dict[str, Any]) -> bool:
    """digest を計算せずに「未変更」と言い切れるかを判定する。

    size / mtime_ns / ctime_ns の一致で早期に打ち切るのは性能のためだけではない。この hook は全ての
    Bash 実行後に走るため、2MB の store を毎回 parse すると監査コストが常時課金される。
    mtime は利用者が戻せるため単独では変更検出子にならない。ctime は通常の file API から任意の
    過去値へ戻せないので、同サイズ書換えで mtime まで復元する迂回も digest 段へ送る。
    """
    return (
        bool(baseline.get("exists"))
        and bool(snapshot.get("exists"))
        and baseline.get("size") == snapshot.get("size")
        and baseline.get("mtime_ns") == snapshot.get("mtime_ns")
        and baseline.get("ctime_ns") == snapshot.get("ctime_ns")
    )


def _digest_of(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(READ_CHUNK), b""):
            digest.update(chunk)
    return "sha256:" + digest.hexdigest()


def _graph_revision(document: Any) -> int | None:
    if not isinstance(document, dict):
        return None
    revision = document.get("graph_revision")
    if isinstance(revision, bool) or not isinstance(revision, int):
        return None
    return revision


def audit_path(
    relative: str,
    path: Path,
    baseline: dict[str, Any] | None,
    command: str,
) -> tuple[dict[str, Any], list[dict[str, str]]]:
    """1 つの authority path を検査し、(新しい baseline, findings) を返す。

    baseline が無い初回は内容差分を断定しないが、壊れた JSON / envelope は無警告で採用しない。
    「台帳が無い＝全部 drift」にはせず、正規 writer が残さない形だけを confirmed にする。
    """
    snapshot = _stat_snapshot(path)
    if not snapshot.get("exists"):
        if baseline is not None and baseline.get("exists"):
            return snapshot, [
                _finding(
                    relative,
                    "authority_removed",
                    "confirmed",
                    "graph authority が消失した (C02 writer は authority を削除しない)",
                )
            ]
        return snapshot, []

    if baseline is not None and _stat_identical(baseline, snapshot):
        # 未変更。digest も revision も前回値をそのまま持ち越す。
        carried = {key: baseline[key] for key in ("digest", "graph_revision") if key in baseline}
        return {**snapshot, **carried}, []

    size = snapshot.get("size")
    if isinstance(size, int) and size > MAX_AUDITED_BYTES:
        return snapshot, [
            _finding(
                relative,
                "audit_skipped_oversize",
                "advisory",
                f"{size} bytes は監査上限 {MAX_AUDITED_BYTES} を超えるため digest 検査を省いた",
            )
        ]

    try:
        digest = _digest_of(path)
    except OSError as exc:
        return snapshot, [
            _finding(relative, "audit_unreadable", "advisory", f"digest を計算できない: {exc}")
        ]

    try:
        document = json.loads(path.read_text(encoding="utf-8"))
        parse_error = None
    except (OSError, UnicodeDecodeError, json.JSONDecodeError) as exc:
        document = None
        parse_error = str(exc)

    record: dict[str, Any] = {**snapshot, "digest": digest}
    revision = _graph_revision(document)
    if relative == GRAPH_RELATIVE and revision is not None:
        record["graph_revision"] = revision

    if baseline is None:
        # 内容差分は比較できない初回でも、正規 writer が決して残さない壊れた JSON / envelope
        # まで無条件採用してはならない。そうすると台帳削除 -> authority 破損を 1 command で
        # 行う迂回が silent になる。canonical な初期状態だけを無警告で基準化する。
        if parse_error is not None:
            return record, [
                _finding(
                    relative,
                    "unparsable_authority",
                    "confirmed",
                    f"初回基準化対象が JSON として読めない: {parse_error}",
                )
            ]
        if relative == GRAPH_RELATIVE:
            initial = [
                _finding(relative, "envelope_violation", "confirmed", detail)
                for detail in envelope_violations(document)
            ]
            if initial:
                return record, initial
        return record, []

    if baseline.get("exists") and baseline.get("digest") == digest:
        # mtime だけ動いた (touch・同一内容の再書込み)。内容は変わっていない。
        return record, []

    # ここから先は「authority の内容が変わった」経路。消失後の再生成も同じ扱いとし、中身の形
    # まで見る。生成イベントを writer 名だけで済ませると、消してから壊れた store を置き直す
    # 経路が素通りする。
    findings: list[dict[str, str]] = []
    if parse_error is not None:
        findings.append(
            _finding(
                relative,
                "unparsable_authority",
                "confirmed",
                f"authority が JSON として読めない: {parse_error}",
            )
        )
    elif relative == GRAPH_RELATIVE:
        # graph_revision の型・欠落は envelope 検査が拾うため、ここでは前回値との比較だけを行う。
        for detail in envelope_violations(document):
            findings.append(_finding(relative, "envelope_violation", "confirmed", detail))
        previous = baseline.get("graph_revision")
        if isinstance(previous, int) and isinstance(revision, int) and revision <= previous:
            # C02 writer は 1 回の書込みにつき graph_revision を必ず +1 する。内容が変わって
            # revision が進んでいないのは、正規 writer では成立し得ない形である。
            vcs = _vcs_transition_only(command)
            findings.append(
                _finding(
                    relative,
                    "revision_not_advanced",
                    "advisory" if vcs else "confirmed",
                    f"内容が変わったが graph_revision が {previous} -> {revision} と進んでいない"
                    + (" (VCS 操作に伴う履歴移動の可能性)" if vcs else ""),
                )
            )

    if not SANCTIONED_WRITERS[relative].search(command) and not _vcs_transition_only(command):
        findings.append(
            _finding(
                relative,
                "writer_not_observed",
                "advisory",
                "内容が変わったが、コマンド文字列に正規 writer 名も VCS 操作も現れない "
                "(script file 経由の間接起動なら正規運用でもこの形になる)",
            )
        )
    return record, findings


def load_ledger(path: Path) -> tuple[dict[str, Any], str | None]:
    if not path.is_file():
        return {}, None
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, UnicodeDecodeError, json.JSONDecodeError) as exc:
        return {}, str(exc)
    return (value, None) if isinstance(value, dict) else ({}, "ledger must be a JSON object")


def write_ledger(path: Path, payload: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    handle_fd, temporary = tempfile.mkstemp(
        dir=str(path.parent), prefix=".authority-audit-", suffix=".tmp"
    )
    try:
        with os.fdopen(handle_fd, "w", encoding="utf-8") as handle:
            json.dump(payload, handle, ensure_ascii=False, sort_keys=True, indent=2)
            handle.write("\n")
        os.replace(temporary, path)
    except BaseException:
        Path(temporary).unlink(missing_ok=True)
        raise


def audit(root: Path, command: str, ledger_path: Path) -> tuple[dict[str, Any], list[dict[str, str]]]:
    ledger, ledger_error = load_ledger(ledger_path)
    previous = ledger.get("baselines")
    baselines = previous if isinstance(previous, dict) else {}

    findings: list[dict[str, str]] = []
    updated: dict[str, Any] = {}
    for relative in AUDITED_PATHS:
        baseline = baselines.get(relative)
        record, found = audit_path(
            relative,
            root / relative,
            baseline if isinstance(baseline, dict) else None,
            command,
        )
        # PostToolUse は既に行われた変更を巻き戻せない。confirmed drift を新しい baseline に
        # 採用すると、破損が残ったまま次の Bash から警告が消える。修復を観測するまでは前の
        # clean/advisory baseline を保持して再通知する。初回に破損を検出した場合は baseline を
        # 作らず、次回も初回健全性検査を繰り返す。
        confirmed = any(item["severity"] == "confirmed" for item in found)
        if confirmed:
            updated[relative] = baseline if isinstance(baseline, dict) else {}
        else:
            updated[relative] = record
        findings.extend(found)

    if ledger_error is not None:
        findings.append(
            _finding(
                LEDGER_RELATIVE.as_posix(),
                "ledger_unreadable",
                "advisory",
                f"監査台帳を読めないため今回の比較を省いた: {ledger_error}",
            )
        )
    return {
        "schema_version": LEDGER_VERSION,
        "baselines": updated,
        "last_findings": findings,
    }, findings


def main() -> int:
    parser = argparse.ArgumentParser(description="graph authority の事後 drift 監査")
    parser.add_argument("--repo-root", required=True)
    parser.add_argument("--ledger", default=None)
    args = parser.parse_args()

    root = Path(args.repo_root).expanduser().resolve()
    if not (root / ".dev-graph").is_dir():
        # dev-graph を使わないリポジトリで台帳ディレクトリを作らない。
        return 0

    command = command_of(read_payload())
    ledger_path = Path(args.ledger).expanduser() if args.ledger else root / LEDGER_RELATIVE
    ledger, findings = audit(root, command, ledger_path)

    # 台帳ファイル自体は結果によらず更新するが、confirmed path の baseline は前進させない。
    # PostToolUse は変更を巻き戻せないため、修復まで再通知することが fail-closed 契約である。
    write_ledger(ledger_path, ledger)

    confirmed = [item for item in findings if item["severity"] == "confirmed"]
    advisory = [item for item in findings if item["severity"] != "confirmed"]
    if confirmed:
        sys.stderr.write(
            "[audit-graph-authority-drift] graph authority drift detected "
            "(C10 PreToolUse では遮断できない経路の事後検出):\n"
        )
        for item in confirmed:
            sys.stderr.write(f"  - {item['path']}: {item['code']}: {item['detail']}\n")
        sys.stderr.write(
            "  変更が意図的なら C02 atomic writer "
            "(build-init-scaffold.py / build-graph-node.py / register-package.py) 経由で書き直すこと。\n"
        )
        return 2
    if advisory:
        json.dump(
            {"status": "advisory", "findings": advisory},
            sys.stdout,
            ensure_ascii=False,
            sort_keys=True,
        )
        sys.stdout.write("\n")
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except SystemExit:
        raise
    except BaseException as exc:  # 監査自身の異常で PostToolUse を止めない
        sys.stderr.write(f"[audit-graph-authority-drift] audit skipped: {exc}\n")
        raise SystemExit(0)
