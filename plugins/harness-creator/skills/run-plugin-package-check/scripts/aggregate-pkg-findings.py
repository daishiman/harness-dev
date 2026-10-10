#!/usr/bin/env python3
# /// script
# name: aggregate-pkg-findings
# purpose: 1 run の PKG ログ (個別ログと evaluator の一括ログ) を phase の required_pkg ごとに集約し、run-report JSON を書く
# inputs:
#   - argv: --plugin NAME --run <YYYY-MM-DD>-<run> --phase {0,1,2,all} [--pkg PKG-NNN,...] --out PATH（相対 path は repo root から）
#   - env: CLAUDE_PROJECT_DIR（repo root。無ければ本ファイルの parents[5]、それも無ければ cwd）
#   - files: eval-log/<plugin>/pkg-*/<run>.json（--run の run だけ。pkg-summary を除き、pkg-batch も読む）、../workflow-manifest.json
# outputs:
#   - stdout: run-report JSON（schemas/run-report.schema.json）
#   - files: --out の run-report JSON。verdict.fail > 0 のとき .claude/logs/meta-harness.jsonl に pkg_check_failed を 1 行追記
#   - stderr: exit 2 の理由
#   - exit: 0=fail なし / 1=fail あり / 2=引数の誤り・manifest を読めない・--out か observable log を書けない
# contexts: [C, E]
# network: false
# write-scope: --out と .claude/logs/meta-harness.jsonl だけ
# dependencies: []
# requires-python: ">=3.9"
# ///
"""1 run の PKG ログを集約し run-report.json を生成。

入力: eval-log/<plugin>/pkg-*/<run>.json（--run で渡した run のログだけ。別の run のログは新しくても読まない）
  - PKG result 形式: {"pkg_id", "status", "findings"}（run-pkg-015.py・lint-pkg-009.py・validate-plugin-permissions.py など）
  - evaluator 形式: {"pkg_checks": {"PKG-xxx": {"status", "findings"}}, "package_mode", "verdict"}
    （validate-plugin-package.py。pkg-batch/ の一括実行も pkg-0NN/ の単発実行もこの形）
数える PKG ID: ../workflow-manifest.json の completion_signals にある --phase の required_pkg（includes_phase_* を辿る。
  all は全 phase）。--pkg を渡したらその ID だけ。PKG-013a〜d は run-report の key の PKG-013 に畳む。
  数える ID の外のログは読んでも数えない。
出力: eval-log/<plugin>/pkg-summary/<date>-<run>.json
副作用: verdict.fail > 0 のとき .claude/logs/meta-harness.jsonl に
        pkg_check_failed event を 1 行 append（35章 observable）。

fail-closed (走っていない検査や読めないログで集約を緑にしない):
- 数える ID のうち、この run のログが無いものは fail。ただし、この run の evaluator ログがすべて
  package_mode=skill-only を報告し、その ID が manifest の not_applicable_default にあれば not_applicable。
- status を読めないログ (壊れた JSON・壊れた symlink・status の無い単発ログ・未知の status 値) は fail。
  読めないログの PKG ID は、manifest がその出力先に割り当てた ID (pkg-batch なら evaluator に渡す ID) にする。
- 同じ PKG ID がこの run の複数のログに出たら、重い status を採る。
"""

from __future__ import annotations
import argparse
import json
import os
import re
import sys
from datetime import datetime, timezone
from pathlib import Path


def _resolve_repo_root() -> Path:
    """$CLAUDE_PROJECT_DIR → 本ファイル parents[5] → cwd の順 (validate-plugin-permissions.py と同じ)。

    install 先では parents[5] が marketplace のディレクトリになるので、plugins/ を含むときだけ採る。
    """
    env = os.environ.get("CLAUDE_PROJECT_DIR")
    if env and (Path(env) / "plugins").is_dir():
        return Path(env)
    here = Path(__file__).resolve()
    if len(here.parents) > 5 and (here.parents[5] / "plugins").is_dir():
        return here.parents[5]
    return Path.cwd()


REPO_ROOT = _resolve_repo_root()
MANIFEST = Path(__file__).resolve().parents[1] / "workflow-manifest.json"
STATUSES = ("pass", "fail", "skip", "not_applicable")
PHASES = ("0", "1", "2", "all")
# 同じ run のログが食い違ったときに採る順 (重い方を採る)
_SEVERITY = {"fail": 3, "skip": 2, "pass": 1, "not_applicable": 0}
# run-report.schema.json の pkg_checks の key と同じ範囲
_REPORT_KEY = re.compile(r"PKG-(00[1-9]|01[0-5])")
_RUN = re.compile(r"\d{4}-\d{2}-\d{2}-[A-Za-z0-9][A-Za-z0-9_-]*")
_PLUGIN = re.compile(r"[A-Za-z0-9][A-Za-z0-9_-]*")


class InputError(Exception):
    """exit 2 にする入力の誤り。"""


def now_iso() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def report_id(value: object) -> str | None:
    """PKG ID を run-report の key にする。PKG-013a〜d は PKG-013。範囲の外なら None。"""
    if not isinstance(value, str):
        return None
    key = value.strip().upper()
    if re.fullmatch(r"PKG-013[A-D]", key):
        key = "PKG-013"
    return key if _REPORT_KEY.fullmatch(key) else None


def load_manifest(path: Path = MANIFEST) -> dict:
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, ValueError) as exc:
        raise InputError(f"workflow-manifest.json を読めない: {type(exc).__name__}") from exc
    if not isinstance(data, dict) or not isinstance(data.get("completion_signals"), dict):
        raise InputError("workflow-manifest.json に completion_signals の object が無い")
    return data


def required_ids(manifest: dict, phase: str) -> list[str]:
    """phase の required_pkg を includes_phase_* を辿って集め、run-report の key にして返す。"""
    signals = manifest["completion_signals"]
    pending = sorted(k for k in signals if k.startswith("phase_")) if phase == "all" else [f"phase_{phase}"]
    seen: set[str] = set()
    ids: set[str] = set()
    while pending:
        name = pending.pop()
        if name in seen:
            continue
        seen.add(name)
        signal = signals.get(name)
        raw_ids = signal.get("required_pkg") if isinstance(signal, dict) else None
        if not isinstance(raw_ids, list):
            raise InputError(f"manifest の completion_signals.{name}.required_pkg を読めない")
        for raw in raw_ids:
            key = report_id(raw)
            if key is None:
                raise InputError(f"manifest の completion_signals.{name} に PKG ID でない値: {raw!r}")
            ids.add(key)
        pending += [k[len("includes_"):] for k, v in signal.items() if k.startswith("includes_") and v is True]
    return sorted(ids)


def parse_pkg(value: str) -> list[str]:
    ids: set[str] = set()
    for raw in value.split(","):
        key = report_id(raw)
        if key is None:
            raise InputError(f"--pkg に PKG-001〜015 でない値: {raw.strip()!r}")
        ids.add(key)
    return sorted(ids)


def ids_by_output_dir(manifest: dict) -> dict[str, list[str]]:
    """manifest の phases[].output の出力先ディレクトリ → その step の PKG ID。読めないログの ID に使う。"""
    result: dict[str, set[str]] = {}
    steps = manifest.get("phases")
    for step in steps if isinstance(steps, list) else []:
        output = step.get("output") if isinstance(step, dict) else None
        parts = output.split("/") if isinstance(output, str) else []
        if len(parts) < 2 or not parts[-2].startswith("pkg-"):
            continue
        delegate = step.get("delegate_args")
        raw_ids = delegate.get("pkg_ids") if isinstance(delegate, dict) else None
        keys = {report_id(r) for r in (raw_ids if isinstance(raw_ids, list) else [step.get("id")])}
        result.setdefault(parts[-2], set()).update(k for k in keys if k)
    return {d: sorted(ids) for d, ids in result.items() if ids}


def _findings_count(entry: dict) -> int:
    findings = entry.get("findings")
    return len(findings) if isinstance(findings, list) else 0


def _single_status(data: dict) -> tuple[str, str | None]:
    """PKG result 形式の status を返す。読めなければ ("fail", 理由)。"""
    status = data.get("status")
    if status in STATUSES:
        return status, None
    if status is not None:
        return "fail", f"未知の status: {status!r}"
    # 旧 lint-pkg-009.py は lint-external-refs.py --json をそのまま出していた (status なし)
    count = data.get("external_ref_count")
    if isinstance(count, int) and not isinstance(count, bool):
        return ("fail" if count or data.get("contract_errors") else "pass"), "status なし: external_ref_count から導出"
    return "fail", "status を読めない"


def entries_from_log(log: Path, fallback_ids: list[str]) -> tuple[list[dict], str | None]:
    """1 つのログを (PKG ID ごとの集約エントリ, 報告された package_mode) にする。

    読めないログは fallback_ids の fail のエントリにする。
    """
    source = str(log.relative_to(REPO_ROOT)) if log.is_relative_to(REPO_ROOT) else str(log)

    def unreadable(note: str) -> tuple[list[dict], None]:
        return [{"pkg_id": i, "source_log": source, "status": "fail", "findings_count": 0, "status_note": note}
                for i in fallback_ids], None

    try:
        data = json.loads(log.read_text(encoding="utf-8"))
    except (OSError, ValueError) as exc:
        return unreadable(f"ログを読めない: {type(exc).__name__}")
    if not isinstance(data, dict):
        return unreadable("ログが JSON object でない")
    pkg_checks = data.get("pkg_checks")
    if "status" not in data and isinstance(pkg_checks, dict):
        # evaluator 形式。PKG ID ごとに展開し、それぞれの status を使う
        entries = []
        for raw_id, check in pkg_checks.items():
            pkg_id = report_id(raw_id)
            if pkg_id is None:
                continue
            status = check.get("status") if isinstance(check, dict) else None
            entry = {"pkg_id": pkg_id, "source_log": source,
                     "status": status if status in STATUSES else "fail",
                     "findings_count": _findings_count(check) if isinstance(check, dict) else 0}
            if status not in STATUSES:
                entry["status_note"] = f"pkg_checks.{raw_id}.status を読めない: {status!r}"
            entries.append(entry)
        if not entries:
            return unreadable("pkg_checks に PKG ID が無い")
        mode = data.get("package_mode")
        return entries, mode if isinstance(mode, str) else None
    status, note = _single_status(data)
    if "pkg_id" in data:
        pkg_id = report_id(data["pkg_id"])
        if pkg_id is None:
            return unreadable(f"pkg_id が PKG-001〜015 でない: {data['pkg_id']!r}")
        ids = [pkg_id]
    else:
        ids = fallback_ids
    entries = [{"pkg_id": i, "source_log": source, "status": status, "findings_count": _findings_count(data)}
               for i in ids]
    for entry in entries:
        if note:
            entry["status_note"] = note
    return entries, None


def aggregate(plugin: str, run: str, phase: str, required: list[str], manifest: dict) -> dict:
    eval_root = REPO_ROOT / "eval-log" / plugin
    summary = {
        "plugin": plugin,
        "run": run,
        "phase": phase,
        "aggregated_at": now_iso(),
        "pkg_checks": {},
        "verdict": {"pass": 0, "fail": 0, "skip": 0, "not_applicable": 0},
    }
    fallback = ids_by_output_dir(manifest)
    chosen: dict[str, dict] = {}
    modes: set[str] = set()
    logs_read = 0
    for pkg_dir in sorted(eval_root.glob("pkg-*")) if eval_root.is_dir() else []:
        log = pkg_dir / f"{run}.json"
        if pkg_dir.name == "pkg-summary" or not pkg_dir.is_dir() or not os.path.lexists(log):
            continue
        logs_read += 1
        own_id = report_id(pkg_dir.name)
        entries, mode = entries_from_log(log, fallback.get(pkg_dir.name) or ([own_id] if own_id else []))
        if mode:
            modes.add(mode)
        for entry in entries:
            current = chosen.get(entry["pkg_id"])
            if current is None or _SEVERITY[entry["status"]] > _SEVERITY[current["status"]]:
                chosen[entry["pkg_id"]] = entry

    handling = manifest.get("package_mode_handling")
    skill_only = handling.get("skill-only") if isinstance(handling, dict) else None
    na_default = skill_only.get("not_applicable_default") if isinstance(skill_only, dict) else None
    not_applicable = ({report_id(r) for r in na_default}
                      if modes == {"skill-only"} and isinstance(na_default, list) else set())
    for pkg_id in required:
        if pkg_id in chosen:
            entry = {k: v for k, v in chosen[pkg_id].items() if k != "pkg_id"}
        elif pkg_id in not_applicable:
            entry = {"status": "not_applicable", "findings_count": 0,
                     "status_note": "package_mode=skill-only の対象外 (この run のログは無い)"}
        else:
            entry = {"status": "fail", "findings_count": 0, "status_note": f"この run ({run}) のログが無い"}
        summary["pkg_checks"][pkg_id] = entry
        summary["verdict"][entry["status"]] += 1

    summary["verdict"]["total"] = sum(summary["verdict"][k] for k in STATUSES)
    if logs_read == 0:
        summary["verdict_note"] = f"この run ({run}) のログが 1 件も無い"
    return summary


def emit_observable(summary: dict) -> None:
    if summary["verdict"].get("fail", 0) == 0:
        return
    log_dir = REPO_ROOT / ".claude" / "logs"
    log_dir.mkdir(parents=True, exist_ok=True)
    event = {
        "event": "pkg_check_failed",
        "schema_version": "1.0",
        "ts": now_iso(),
        "plugin": summary["plugin"],
        "fail_count": summary["verdict"]["fail"],
        "failed_pkg_ids": [k for k, v in summary["pkg_checks"].items() if v["status"] == "fail"],
    }
    with (log_dir / "meta-harness.jsonl").open("a", encoding="utf-8") as f:
        f.write(json.dumps(event, ensure_ascii=False) + "\n")


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(
        description="1 run の PKG ログを、phase の required_pkg (workflow-manifest.json) ごとに集約して run-report JSON を書く。"
                    "この run のログが無い ID・読めないログは fail と数える。")
    ap.add_argument("--plugin", required=True, help="plugin 名。eval-log/<plugin>/pkg-*/ を読む")
    ap.add_argument("--run", required=True, help="集約する run。ログのファイル名の stem <YYYY-MM-DD>-<run>")
    ap.add_argument("--phase", required=True, choices=PHASES,
                    help="数える PKG ID の範囲。completion_signals の phase_N (includes_phase_* も含む)。all は全 phase")
    ap.add_argument("--pkg", help="数える PKG ID をカンマ区切りで絞る (例: PKG-006,PKG-013a)。PKG-013a〜d は PKG-013")
    ap.add_argument("--out", required=True, help="run-report JSON の書き先 (相対 path は repo root から)")
    args = ap.parse_args(argv)

    try:
        if not _PLUGIN.fullmatch(args.plugin):
            raise InputError(f"--plugin が plugin 名でない: {args.plugin!r}")
        if not _RUN.fullmatch(args.run):
            raise InputError(f"--run が <YYYY-MM-DD>-<run> でない: {args.run!r}")
        manifest = load_manifest()
        required = parse_pkg(args.pkg) if args.pkg is not None else required_ids(manifest, args.phase)
    except InputError as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 2

    summary = aggregate(args.plugin, args.run, args.phase, required, manifest)
    out_path = Path(args.out)
    if not out_path.is_absolute():
        out_path = REPO_ROOT / out_path
    try:
        out_path.parent.mkdir(parents=True, exist_ok=True)
        out_path.write_text(json.dumps(summary, ensure_ascii=False, indent=2), encoding="utf-8")
        emit_observable(summary)
    except OSError as exc:
        print(f"error: 集約結果か observable log を書けない: {type(exc).__name__}: {exc}", file=sys.stderr)
        return 2

    print(json.dumps(summary, ensure_ascii=False, indent=2))
    return 1 if summary["verdict"]["fail"] > 0 else 0


if __name__ == "__main__":
    sys.exit(main())
