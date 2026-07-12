#!/usr/bin/env python3
# /// script
# name: validate-consult-session
# version: 0.3.0
# purpose: run-ubm-consult の分岐別 record と role=user provenance、保存同意、closure、非処方スタンスを決定論検証し (--ephemeral は非永続前提で consent 要求のみ免除)、--gc で retention 超過/orphan session を回収する。
# inputs: ["--record JSON", "--transcript JSON (consult_completed のみ)", "--ephemeral", "--gc SESSIONS_ROOT [--apply]"]
# outputs: ["stdout JSON verdict", "exit 0=valid / 1=invalid / 2=usage"]
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
from datetime import datetime, timezone
from pathlib import Path

MODES = {"question-led", "framework-led", "hypothesis-example", "reflect-only"}
OUTCOMES = {"redirected_goal_setting", "safety_redirect", "consult_completed"}
SECRET = re.compile(r"(sk-[A-Za-z0-9_-]{16,}|gh[pousr]_[A-Za-z0-9]{20,}|AKIA[0-9A-Z]{16}|xox[baprs]-[A-Za-z0-9-]{10,})")
# IN1/OUT1 の決定論マーカー正本 (tests/test_ubm_consult_contract.py はここから import する)
PRESCRIPTION = re.compile(r"すべきです|しなさい|が正解|以上が正解|実行してください|従ってください")
FRAME = re.compile(r"考え方|思考フレーム|見方|フレーム")
VERBALIZED = re.compile(r"解決|やる|する|決め|言葉")


def _load(path: str) -> object:
    return json.loads(Path(path).read_text(encoding="utf-8"))


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
    """
    assistant_text = "\n".join(str(t.get("content", "")) for t in transcript if t.get("role") == "assistant")
    user_text = "\n".join(str(t.get("content", "")) for t in transcript if t.get("role") == "user")
    return {
        "frame_presented": bool(FRAME.search(assistant_text)),
        "elicit_question": ("？" in assistant_text) or ("?" in assistant_text),
        "user_verbalized": bool(VERBALIZED.search(user_text)),
        "next_step": bool(re.search(r"次の一歩", assistant_text) and re.search(r"現状|ゴール|ギャップ", assistant_text)),
    }


def validate(record: dict, transcript: list[dict] | None, *, ephemeral: bool = False) -> list[str]:
    errors: list[str] = []
    outcome = record.get("outcome")
    if outcome not in OUTCOMES:
        return [f"outcome が enum 外: {outcome!r} (許容: {sorted(OUTCOMES)})"]
    if SECRET.search(json.dumps(record, ensure_ascii=False)):
        errors.append("secret 様文字列が未 redaction")
    # record の永続は outcome に依らず persistence_consent=true が前提 (redirect 系も同じ)。
    # ephemeral=True (非永続前提・通過後破棄) は consent 要求のみ免除し、他の検査は一切緩めない。
    if not ephemeral and record.get("persistence_consent") is not True:
        errors.append("record 永続には persistence_consent=true が必須 (outcome に依らず)")
    if outcome == "redirected_goal_setting":
        if record.get("handoff_to") != "run-ubm-goal-setting" or record.get("referral_confirmed") is not True:
            errors.append("goal-setting redirect 契約不備")
        return errors
    if outcome == "safety_redirect":
        for key in ("risk_class", "handoff_to", "referral_message"):
            if not record.get(key):
                errors.append(f"safety redirect の {key} 欠落")
        return errors
    for key in ("session_id", "created_at", "retention_until", "issue_statement"):
        if not record.get(key):
            errors.append(f"{key} 欠落")
    if record.get("collaboration_mode") not in MODES:
        errors.append("collaboration_mode 不正")
    frames = record.get("frames_presented")
    if not isinstance(frames, list) or not frames:
        errors.append("frames_presented が空")
    elif any(not isinstance(f, dict) or not f.get("source_ids") for f in frames):
        errors.append("frames_presented[*].source_ids が空 (出典 ID 必須)")
    solution = record.get("user_solution")
    turn_ids = solution.get("source_turn_ids") if isinstance(solution, dict) else None
    if not isinstance(turn_ids, list) or not turn_ids:
        errors.append("user_solution.source_turn_ids 欠落")
    user_turn_ids = {t.get("id") for t in (transcript or []) if t.get("role") == "user"}
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
    if transcript is not None:
        prescriptive = any(
            t.get("role") == "assistant" and PRESCRIPTION.search(str(t.get("content", "")))
            for t in transcript
        )
        if prescriptive:
            errors.append("assistant 発話に処方マーカー (非処方スタンス違反)")
        machine = {
            "no_prescription": not prescriptive,
            "user_verbalized": detect_transcript_elements(transcript)["user_verbalized"],
        }
        stance = record.get("stance_self_check")
        if isinstance(stance, dict):
            for key, expected in machine.items():
                if key in stance and bool(stance[key]) != expected:
                    errors.append(f"stance_self_check.{key} が機械検査結果と不一致")
    return errors


def gc_sessions(sessions_root: Path, *, apply: bool = False, now: datetime | None = None) -> dict:
    """retention_until 超過 record と handoff 無し orphan session を回収する。

    dry-run 既定。--apply でのみ実削除し index.jsonl へ status=deleted を append する。
    破損 handoff は誤削除を避けて保持する (手動確認へ委ねる)。
    """
    now = now or datetime.now(timezone.utc)
    report: dict = {"mode": "apply" if apply else "dry-run", "deleted": [], "kept": []}
    if not sessions_root.is_dir():
        return report
    for entry in sorted(p for p in sessions_root.iterdir() if p.is_dir()):
        reason = None
        created_at = ""
        handoff = entry / "handoff.json"
        if not handoff.is_file():
            reason = "orphan"
        else:
            try:
                rec = json.loads(handoff.read_text(encoding="utf-8"))
                created_at = str(rec.get("created_at", ""))
                expiry = datetime.fromisoformat(str(rec.get("retention_until", "")).replace("Z", "+00:00"))
                if expiry.tzinfo is None:
                    expiry = expiry.replace(tzinfo=timezone.utc)
                if expiry <= now:
                    reason = "retention_expired"
            except (OSError, json.JSONDecodeError, ValueError):
                pass
        if reason is None:
            report["kept"].append(entry.name)
            continue
        item = {
            "session_id": entry.name,
            "path": str(entry),
            "created_at": created_at,
            "status": "deleted",
            "reason": reason,
        }
        report["deleted"].append(item)
        if apply:
            shutil.rmtree(entry)
            with (sessions_root / "index.jsonl").open("a", encoding="utf-8") as fh:
                fh.write(json.dumps({**item, "deleted_at": now.isoformat()}, ensure_ascii=False) + "\n")
    return report


def main(argv: list[str] | None = None) -> int:
    p = argparse.ArgumentParser()
    p.add_argument("--record")
    p.add_argument("--transcript")
    p.add_argument("--ephemeral", action="store_true")
    p.add_argument("--gc", metavar="SESSIONS_ROOT")
    p.add_argument("--apply", action="store_true")
    args = p.parse_args(argv)
    if args.gc:
        print(json.dumps(gc_sessions(Path(args.gc), apply=args.apply), ensure_ascii=False, sort_keys=True))
        return 0
    if not args.record:
        print(json.dumps({"valid": False, "errors": ["--record か --gc のいずれかが必要"]}, ensure_ascii=False))
        return 2
    try:
        record = _load(args.record)
        transcript = _load(args.transcript) if args.transcript else None
        if not isinstance(record, dict) or (transcript is not None and not isinstance(transcript, list)):
            raise ValueError("JSON shape invalid")
    except (OSError, json.JSONDecodeError, ValueError) as exc:
        print(json.dumps({"valid": False, "errors": [str(exc)]}, ensure_ascii=False))
        return 2
    errors = validate(record, transcript, ephemeral=args.ephemeral)
    print(json.dumps({"valid": not errors, "errors": errors}, ensure_ascii=False, sort_keys=True))
    return 0 if not errors else 1


if __name__ == "__main__":
    sys.exit(main())
