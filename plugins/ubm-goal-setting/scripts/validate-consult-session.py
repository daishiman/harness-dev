#!/usr/bin/env python3
# /// script
# name: validate-consult-session
# version: 0.5.0
# purpose: run-ubm-consult の分岐別 record と role=user provenance (transcript turn id の重複拒否を含む)、保存同意、closure、非処方スタンス、日時の形を決定論検証し (--ephemeral は非永続前提で consent 要求のみ免除)、--gc で retention 超過/orphan session を回収する。
# inputs: ["--record JSON", "--transcript JSON (consult_completed のみ)", "--ephemeral", "--gc SESSIONS_ROOT [--apply]"]
# outputs: ["stdout JSON verdict / gc report", "exit 0=valid (gc は完了) / 1=invalid / 2=usage・読込不能・gc の root 不在や削除失敗"]
# contexts: [C, E]
# network: false
# write-scope: "--gc --apply 時のみ sessions root 配下 (期限切れ/orphan session の削除 + index.jsonl append)。検証モードは none"
# dependencies: []
# requires-python: ">=3.9"
# ///
from __future__ import annotations

import argparse
import json
import re
import shutil
import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path

MODES = {"question-led", "framework-led", "hypothesis-example", "reflect-only"}
REDIRECT_TARGETS = {
    "redirected_goal_setting": "run-ubm-goal-setting",
    "redirected_challenge": "run-ubm-challenge",
}
OUTCOMES = {*REDIRECT_TARGETS, "safety_redirect", "consult_completed"}
# session-record-format.md「retention_until は既定30日以内」。retention_until の無い record の期限に使う。
DEFAULT_RETENTION = timedelta(days=30)
SECRET = re.compile(r"(sk-[A-Za-z0-9_-]{16,}|gh[pousr]_[A-Za-z0-9]{20,}|AKIA[0-9A-Z]{16}|xox[baprs]-[A-Za-z0-9-]{10,})")
# IN1/OUT1 の決定論マーカー正本 (tests/test_ubm_consult_contract.py はここから import する)
PRESCRIPTION = re.compile(r"すべきです|しなさい|が正解|以上が正解|実行してください|従ってください")
FRAME = re.compile(r"考え方|思考フレーム|見方|フレーム")
VERBALIZED = re.compile(r"解決|やる|する|決め|言葉")
ACTION_CLOSE = re.compile(r"次の一歩")
ACTION_FRAME = re.compile(r"現状|ゴール|ギャップ")
REFLECTION_CLOSE = re.compile(r"再開条件")
REFLECTION_FRAME = re.compile(r"見えてきたこと|まだ決めないこと")


def _load(path: str) -> object:
    return json.loads(Path(path).read_text(encoding="utf-8"))


def parse_iso8601(value: object) -> datetime | None:
    """ISO 8601 の日時を UTC 前提の aware datetime で返す。文字列でない・読めないときは None。

    Python 3.9 の fromisoformat は末尾の Z を読めないので +00:00 に置き換える。
    タイムゾーンの無い値は UTC とみなす。
    """
    if not isinstance(value, str) or not value.strip():
        return None
    try:
        parsed = datetime.fromisoformat(value.strip().replace("Z", "+00:00"))
    except ValueError:
        return None
    return parsed if parsed.tzinfo else parsed.replace(tzinfo=timezone.utc)


def _turns(transcript: list | None) -> list[dict]:
    """transcript の object の turn だけを返す (形の違う要素は validate() が別に報告する)。"""
    return [t for t in (transcript or []) if isinstance(t, dict)]


def _duplicate_ids(entries: list[dict]) -> list[str]:
    """provenance の集合化前に、同じ ID を持つ別 turn を検出する。"""
    seen: set[str] = set()
    duplicates: set[str] = set()
    for entry in entries:
        value = entry.get("id")
        if not isinstance(value, str):
            continue
        if value in seen:
            duplicates.add(value)
        seen.add(value)
    return sorted(duplicates)


def detect_prescription_stance(response: str) -> dict[str, bool]:
    """IN1: 1 応答が考え方/フレームを提示し処方マーカーを含まないかを決定論検出する。"""
    return {
        "frame_presented": bool(FRAME.search(response)),
        "no_prescription": not PRESCRIPTION.search(response),
    }


def detect_transcript_elements(transcript: list[dict]) -> dict[str, bool]:
    """OUT1: role 付き transcript から 4 要素を検出する。

    user_verbalized は role=user の turn 本文のみを根拠とする
    (assistant 発話内の「ユーザー:」文字列は provenance にならない)。
    next_step は 4 要素目「どちらかの締め方で締めていること」を表す。action の締め方は
    次の一歩と現状/ゴール/ギャップ、reflection の締め方は再開条件と見えてきたこと/まだ決めないことで満たす。
    record の closure.type と transcript の締め方が一致するかは、本関数も validate() も検査しない。
    object でない turn は読み飛ばす。
    """
    turns = _turns(transcript)
    assistant_text = "\n".join(str(t.get("content", "")) for t in turns if t.get("role") == "assistant")
    user_text = "\n".join(str(t.get("content", "")) for t in turns if t.get("role") == "user")
    action_closed = bool(ACTION_CLOSE.search(assistant_text) and ACTION_FRAME.search(assistant_text))
    reflection_closed = bool(REFLECTION_CLOSE.search(assistant_text) and REFLECTION_FRAME.search(assistant_text))
    return {
        "frame_presented": bool(FRAME.search(assistant_text)),
        "elicit_question": ("？" in assistant_text) or ("?" in assistant_text),
        "user_verbalized": bool(VERBALIZED.search(user_text)),
        "next_step": action_closed or reflection_closed,
    }


def _nonempty_text(value: object) -> bool:
    return isinstance(value, str) and bool(value.strip())


def validate(record: dict, transcript: list | None, *, ephemeral: bool = False) -> list[str]:
    """record を検査し、違反の一覧を返す (空なら valid)。

    record の値の型が違っても例外にせず、違反として返す (CLI が exit 1 の JSON を出せるように)。
    """
    errors: list[str] = []
    outcome = record.get("outcome")
    if not isinstance(outcome, str) or outcome not in OUTCOMES:
        return [f"outcome が enum 外: {outcome!r} (許容: {sorted(OUTCOMES)})"]
    if SECRET.search(json.dumps(record, ensure_ascii=False)):
        errors.append("secret 様文字列が未 redaction")
    # record の永続は outcome に依らず persistence_consent=true が前提 (redirect 系も同じ)。
    # ephemeral=True (非永続前提・通過後破棄) は consent 要求のみ免除し、他の検査は一切緩めない。
    if not ephemeral and record.get("persistence_consent") is not True:
        errors.append("record 永続には persistence_consent=true が必須 (outcome に依らず)")
    if outcome in REDIRECT_TARGETS:
        if (record.get("handoff_to") != REDIRECT_TARGETS[outcome]
                or record.get("referral_confirmed") is not True
                or not record.get("issue_statement")):
            errors.append(f"{outcome} redirect 契約不備 (issue_statement / handoff_to / referral_confirmed)")
        return errors
    if outcome == "safety_redirect":
        for key in ("risk_class", "handoff_to", "referral_message"):
            if not record.get(key):
                errors.append(f"safety redirect の {key} 欠落")
        return errors
    for key in ("session_id", "created_at", "retention_until", "issue_statement"):
        if not record.get(key):
            errors.append(f"{key} 欠落")
    # session-record-format.md 21行目: created_at は ISO 8601。retention_until も期限の比較に使うので同じ形を要求する。
    created = parse_iso8601(record.get("created_at"))
    expiry = parse_iso8601(record.get("retention_until"))
    for key, parsed in (("created_at", created), ("retention_until", expiry)):
        if record.get(key) and parsed is None:
            errors.append(f"{key} が ISO 8601 の日時でない: {record.get(key)!r}")
    if created and expiry and expiry <= created:
        errors.append("retention_until が created_at より後でない")
    mode = record.get("collaboration_mode")
    if not isinstance(mode, str) or mode not in MODES:
        errors.append("collaboration_mode 不正")
    frames = record.get("frames_presented")
    if not isinstance(frames, list) or not frames:
        errors.append("frames_presented が空")
    elif any(not isinstance(f, dict) or not f.get("source_ids") for f in frames):
        errors.append("frames_presented[*].source_ids が空 (出典 ID 必須)")
    solution = record.get("user_solution")
    if not isinstance(solution, dict) or not _nonempty_text(solution.get("text")):
        errors.append("user_solution.text 欠落")
    turn_ids = solution.get("source_turn_ids") if isinstance(solution, dict) else None
    if not isinstance(turn_ids, list) or not turn_ids:
        errors.append("user_solution.source_turn_ids 欠落")
        turn_ids = []
    elif not all(_nonempty_text(i) for i in turn_ids):
        errors.append("user_solution.source_turn_ids の要素が空でない文字列でない")
        turn_ids = []
    if transcript is not None and len(_turns(transcript)) != len(transcript):
        errors.append("transcript の要素が object でない")
    duplicate_turn_ids = _duplicate_ids(_turns(transcript))
    if duplicate_turn_ids:
        errors.append(f"transcript turn id が重複: {', '.join(duplicate_turn_ids)}")
    # id の無い user turn は参照先にならない (null 同士の一致で provenance を通さない)。
    user_turn_ids = {t["id"] for t in _turns(transcript) if t.get("role") == "user" and _nonempty_text(t.get("id"))}
    if turn_ids and not set(turn_ids).issubset(user_turn_ids):
        errors.append("user_solution が role=user turn を参照していない")
    closure = record.get("closure")
    ctype = closure.get("type") if isinstance(closure, dict) else None
    required = ("current", "goal", "gap", "next_step") if ctype == "action" else (
        "insight", "not_deciding_yet", "resume_when") if ctype == "reflection" else ()
    if not required:
        errors.append("closure.type 不正")
    elif any(not closure.get(k) for k in required):
        errors.append(f"{ctype} closure の必須項目欠落")
    feedback = record.get("user_feedback")
    if not isinstance(feedback, dict) or feedback.get("ownership_confirmed") is not True:
        errors.append("ユーザー所有感の確認欠落")
    evidence = record.get("consult_evidence")
    if not isinstance(evidence, dict) or evidence.get("mode") not in {"graph", "router", "catalog"}:
        errors.append("consult_evidence.mode 不正")
    stance = record.get("stance_self_check")
    if stance is not None and not isinstance(stance, dict):
        errors.append("stance_self_check が object でない")
    if transcript is not None:
        turns = _turns(transcript)
        prescriptive = any(
            t.get("role") == "assistant" and PRESCRIPTION.search(str(t.get("content", "")))
            for t in turns
        )
        if prescriptive:
            errors.append("assistant 発話に処方マーカー (非処方スタンス違反)")
        machine = {
            "no_prescription": not prescriptive,
            "user_verbalized": detect_transcript_elements(turns)["user_verbalized"],
        }
        if isinstance(stance, dict):
            for key, expected in machine.items():
                if key not in stance:
                    continue
                # "false" のような文字列を真偽で読むと自己申告の食い違いを見逃すので、型で判定する。
                if not isinstance(stance[key], bool):
                    errors.append(f"stance_self_check.{key} が真偽値でない")
                elif stance[key] != expected:
                    errors.append(f"stance_self_check.{key} が機械検査結果と不一致")
    return errors


def _classify_session(entry: Path, now: datetime) -> dict:
    """1 つの session を検査し、削除か保持かと理由を決める (ここでは何も消さない)。

    保持の理由が付いたもの (needs_review) は、誤削除を避けて手動確認へ回す。
    """
    item = {"session_id": entry.name, "path": str(entry), "created_at": ""}
    if entry.is_symlink():
        return {**item, "action": "review", "reason": "session がシンボリックリンク"}
    handoff = entry / "handoff.json"
    if not handoff.exists() and not handoff.is_symlink():
        return {**item, "action": "delete", "reason": "orphan"}
    if handoff.is_symlink() or not handoff.is_file():
        return {**item, "action": "review", "reason": "handoff.json が通常のファイルでない"}
    try:
        rec = json.loads(handoff.read_text(encoding="utf-8"))
    except (OSError, ValueError, RecursionError) as exc:
        return {**item, "action": "review", "reason": f"handoff.json を読めない ({type(exc).__name__})"}
    if not isinstance(rec, dict):
        return {**item, "action": "review", "reason": "handoff.json が object でない"}
    created_raw = rec.get("created_at")
    item["created_at"] = created_raw if isinstance(created_raw, str) else ""
    if "retention_until" in rec:
        expiry = parse_iso8601(rec.get("retention_until"))
        if expiry is None:
            return {**item, "action": "review", "reason": "不正な retention_until"}
        expired_reason = "retention_expired"
    else:
        # 誘導分岐の record は retention_until を持たない。既定の保存期限 (created_at + 30日) で判定する。
        created = parse_iso8601(created_raw)
        if created is None:
            return {**item, "action": "review", "reason": "retention_until が無く created_at も読めない"}
        expiry = created + DEFAULT_RETENTION
        expired_reason = "retention_default_expired"
    if expiry <= now:
        return {**item, "action": "delete", "reason": expired_reason}
    return {**item, "action": "keep", "reason": "retention 期間内"}


def gc_sessions(sessions_root: Path, *, apply: bool = False, now: datetime | None = None) -> dict:
    """retention_until 超過 record と handoff 無し orphan session を回収する。

    dry-run 既定。--apply でのみ実削除し index.jsonl へ status=deleted を append する。
    先に全 session を検査して削除計画を作り、検査の途中では何も消さない。
    壊れた handoff・ディレクトリの handoff・不正な retention_until は誤削除を避けて保持し、
    needs_review に理由付きで出す (手動確認へ委ねる)。
    削除は 1 件ずつ「rmtree → index 追記」の順で、失敗したらそこで止めて errors に残す。
    sessions root が無いときは errors に残す (呼び出し側は exit 2 にする)。
    """
    now = now or datetime.now(timezone.utc)
    report: dict = {"mode": "apply" if apply else "dry-run", "deleted": [], "kept": [], "needs_review": [], "errors": []}
    if not sessions_root.is_dir():
        report["errors"].append(f"sessions root がディレクトリでない: {sessions_root}")
        return report
    plan = [_classify_session(entry, now) for entry in sorted(p for p in sessions_root.iterdir() if p.is_dir())]
    for item in plan:
        if item["action"] == "keep":
            report["kept"].append(item["session_id"])
        elif item["action"] == "review":
            report["kept"].append(item["session_id"])
            report["needs_review"].append({k: item[k] for k in ("session_id", "path", "reason")})
    to_delete = [
        {"session_id": i["session_id"], "path": i["path"], "created_at": i["created_at"],
         "status": "deleted", "reason": i["reason"]}
        for i in plan if i["action"] == "delete"
    ]
    if not apply:
        report["deleted"] = to_delete
        return report
    if not to_delete:
        return report
    try:
        # 先に index を開いておき、開けないなら 1 件も消さない (消したのに記録が無い状態を作らない)。
        index = (sessions_root / "index.jsonl").open("a", encoding="utf-8")
    except OSError as exc:
        report["errors"].append(f"index.jsonl を開けないので削除しない: {exc}")
        return report
    with index:
        for item in to_delete:
            try:
                shutil.rmtree(item["path"])
            except OSError as exc:
                report["errors"].append(f"{item['session_id']} を削除できない: {exc}")
                break
            report["deleted"].append(item)
            try:
                index.write(json.dumps({**item, "deleted_at": now.isoformat()}, ensure_ascii=False) + "\n")
                index.flush()
            except OSError as exc:
                report["errors"].append(f"{item['session_id']} は削除したが index.jsonl へ追記できない: {exc}")
                break
    return report


def _usage_error(message: str) -> int:
    print(json.dumps({"valid": False, "errors": [message]}, ensure_ascii=False))
    return 2


def main(argv: list[str] | None = None) -> int:
    p = argparse.ArgumentParser()
    p.add_argument("--record")
    p.add_argument("--transcript")
    p.add_argument("--ephemeral", action="store_true")
    p.add_argument("--gc", metavar="SESSIONS_ROOT")
    p.add_argument("--apply", action="store_true")
    args = p.parse_args(argv)
    if args.gc:
        if args.record or args.transcript or args.ephemeral:
            return _usage_error("--gc と --record/--transcript/--ephemeral は同時に指定できない")
        report = gc_sessions(Path(args.gc), apply=args.apply)
        print(json.dumps(report, ensure_ascii=False, sort_keys=True))
        return 2 if report["errors"] else 0
    if args.apply:
        return _usage_error("--apply は --gc と一緒にだけ指定できる")
    if not args.record:
        return _usage_error("--record か --gc のいずれかが必要")
    try:
        record = _load(args.record)
        transcript = _load(args.transcript) if args.transcript else None
        if not isinstance(record, dict) or (transcript is not None and not isinstance(transcript, list)):
            raise ValueError("JSON shape invalid")
    except (OSError, ValueError, RecursionError) as exc:
        return _usage_error(str(exc))
    errors = validate(record, transcript, ephemeral=args.ephemeral)
    print(json.dumps({"valid": not errors, "errors": errors}, ensure_ascii=False, sort_keys=True))
    return 0 if not errors else 1


if __name__ == "__main__":
    sys.exit(main())
