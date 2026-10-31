#!/usr/bin/env python3
# /// script
# name: audit_fork_attribution
# version: 0.1.0
# purpose: 完成度評価の独立監査 fork receipt を PostToolUse 台帳へ fail-closed で照合する内部モジュール
# inputs:
#   - Python API: report, ledger, expected_session
# outputs:
#   - Python API: 違反リストまたは台帳集計
# contexts: [E, C]
# network: false
# write-scope: none
# dependencies: []
# requires-python: ">=3.9"
# ///
"""`aggregate-completeness.py` の独立監査帰属を扱う内部モジュール。

台帳の読取り、receipt と実 fork の照合、run/session 束縛をここへ集約する。
CLI と集約判定は呼び出し元の `aggregate-completeness.py` が所有する。
"""
from __future__ import annotations

import json
import os
import re
from pathlib import Path

EVALUATOR_NAME = "assign-system-spec-completeness-evaluator"
ASPECTS: dict[str, dict[str, str]] = {
    "foundation_trace": {
        "label": "上位概念トレーサビリティ",
        "auditor": EVALUATOR_NAME,
        "component": "C05",
    },
    "decision_guidance": {
        "label": "意思決定支援",
        "auditor": EVALUATOR_NAME,
        "component": "C05",
    },
    "matrix_coverage": {
        "label": "マトリクス網羅性",
        "auditor": "system-spec-matrix-auditor",
        "component": "C07",
    },
    "design_knowledge_reflection": {
        "label": "設計知識反映",
        "auditor": EVALUATOR_NAME,
        "component": "C05",
    },
    "doc_freshness": {
        "label": "最新ドキュメント出典",
        "auditor": "system-spec-doc-freshness-auditor",
        "component": "C08",
    },
    "prompt_quality": {
        "label": "prompt-creator準拠",
        "auditor": EVALUATOR_NAME,
        "component": "C05",
    },
}
ASPECT_VERDICTS = {"PASS", "FAIL", "INDETERMINATE"}
OVERALL_VERDICTS = {"PASS", "FAIL"}
SEVERITIES = {"high", "medium", "low", "info"}
SUB_INPUT_AUDITORS: dict[str, dict[str, str]] = {
    "matrix_coverage": {"auditor": "system-spec-hearing-auditor", "component": "C06"},
}
DELEGATION_ROLES = {"primary", "sub_input"}
LEDGER_ENV = "SYSTEM_SPEC_AUDIT_FORK_LEDGER"
LEDGER_RELPATH = Path("eval-log") / "system-spec-harness" / "audit-fork-ledger.jsonl"
LEDGER_TOOL_NAMES = ("Task", "Agent")
LEDGER_SCHEMA_LEGACY = "1.1"
LEDGER_SCHEMA_TOOL_USE = "1.2"
# 1.3: SubagentStop が書く completion 行。非同期 fork では PostToolUse が起動受理しか観測できず、
# dispatch 行が恒久的に pending のまま残るため、完了という別の観測事実を追記して昇格させる。
LEDGER_SCHEMA_COMPLETION = "1.3"
RECORD_KIND_COMPLETION = "completion"
PROMPT_SHA256_RE = re.compile(r"^[0-9a-f]{64}$")
RESPONSE_SHA256_RE = re.compile(r"^[0-9a-f]{64}$")


def _plugin_root() -> Path:
    """.../skills/<skill>/scripts/<module>.py から plugin root を返す。"""
    return Path(__file__).resolve().parents[3]


def required_delegations() -> list[dict]:
    """実 fork receipt が必須の (aspect, role, auditor, component) を返す。"""
    required = [
        {"aspect": aid, "role": "primary", "auditor": spec["auditor"], "component": spec["component"]}
        for aid, spec in ASPECTS.items()
        if spec["auditor"] != EVALUATOR_NAME
    ]
    required += [
        {"aspect": aid, "role": "sub_input", "auditor": spec["auditor"], "component": spec["component"]}
        for aid, spec in SUB_INPUT_AUDITORS.items()
    ]
    return required


def default_ledger_path() -> Path:
    """env 上書き > CLAUDE_PROJECT_DIR 相対 > cwd 相対で台帳を解決する。"""
    env = os.environ.get(LEDGER_ENV)
    if env:
        return Path(env)
    return Path(os.environ.get("CLAUDE_PROJECT_DIR") or Path.cwd()) / LEDGER_RELPATH


def empty_ledger() -> dict:
    """台帳不在時の fail-closed な空集計を返す。"""
    return {
        "path": None,
        "exists": False,
        "dispatched": {},
        "sessions": {},
        "receipts": {},
        "receipts_v12": {},
        "completions": {},
        "malformed": 0,
    }


def _parse_completion(record: dict) -> dict | None:
    """schema 1.3 の completion 行を検証して正規形へ写す。不正なら None。"""
    if record.get("record_kind") != RECORD_KIND_COMPLETION:
        return None
    subagent_type = record.get("subagent_type")
    session_id = record.get("session_id")
    response_sha256 = record.get("response_sha256")
    token = record.get("dispatch_token")
    token = token if isinstance(token, str) and token else None
    if not isinstance(subagent_type, str) or not subagent_type:
        # ハーネスは agent_type を空で届けることがある。token があれば exact join で
        # 帰属できるので受理し、無ければ照合の手掛かりが無いので不正として除外する。
        if token is None:
            return None
        subagent_type = None
    if (
        not isinstance(session_id, str)
        or not session_id
        or not isinstance(response_sha256, str)
        or not RESPONSE_SHA256_RE.fullmatch(response_sha256)
    ):
        return None
    return {
        "session_id": session_id,
        "subagent_type": subagent_type,
        "tool_name": record.get("tool_name"),
        "response_sha256": response_sha256,
        "verdict": record.get("audit_verdict"),
        "verdict_state": record.get("verdict_state"),
        "dispatch_token": token,
        "agent_id": record.get("agent_id"),
    }


def promote_completions(receipts_v12: dict, completions: dict) -> None:
    """pending の dispatch 行を completion 行の観測へ昇格させる (in-place)。

    ハーネスは親の ``tool_use_id`` と子の ``agent_id`` を繋ぐ鍵を提供しないため、接合は
    2 段階で行い、いずれにも当たらない場合は **昇格させない** (取り違えより未確定を選ぶ)。

    1. **dispatch token による exact join**: 親が prompt へ埋め auditor が応答へ echo した
       ``AUDIT_DISPATCH: <token>`` が、当該 (session, subagent_type) の pending 側でも
       completion 側でも一意なときだけ接合する。
    2. **1 対 1 の fallback**: token が無い旧来の起動でも、残った pending が 1 件・resolved な
       completion が 1 件しかなければ対応は一意に決まる。2 件以上が残る並列起動は曖昧なので
       pending のまま残す。``subagent_type`` を観測できなかった completion はこの fallback の
       母数に入れない (型が不明な行を数合わせに使うと別 auditor の verdict を取り違える)。
    """
    for session_id, by_tool_use in receipts_v12.items():
        by_type: dict[str, list[dict]] = {}
        session_dispatch_token_counts: dict[str, int] = {}
        for candidates in by_tool_use.values():
            for candidate in candidates:
                token = candidate.get("dispatch_token") if isinstance(candidate, dict) else None
                if token:
                    session_dispatch_token_counts[token] = (
                        session_dispatch_token_counts.get(token, 0) + 1
                    )
            if len(candidates) != 1:
                continue  # 重複・競合行は照合時に fail-closed で拒否される
            receipt = candidates[0]
            if receipt.get("verdict_state") == "resolved":
                continue
            by_type.setdefault(receipt.get("subagent_type"), []).append(receipt)
        session_completions = completions.get(session_id, {})
        for subagent_type, pendings in by_type.items():
            def _usable(rows):
                return [
                    c
                    for c in rows
                    if c.get("verdict_state") == "resolved" and c.get("verdict") in ASPECT_VERDICTS
                ]

            typed = _usable(session_completions.get(subagent_type, []))
            # subagent_type を観測できなかった completion は token join でしか帰属できない。
            # 型が分からない以上 1 対 1 fallback の母数に入れると別 auditor の verdict を
            # 取り違えるため、typed の後ろへ並べて leftover 判定から外す。
            untyped = [c for c in _usable(session_completions.get(None, [])) if c["dispatch_token"]]
            available = typed + untyped
            if not available:
                continue
            used: set[int] = set()
            unmatched = []
            token_counts: dict[str, int] = {}
            for c in available:
                if c["dispatch_token"]:
                    token_counts[c["dispatch_token"]] = token_counts.get(c["dispatch_token"], 0) + 1
            for p in pendings:
                token = p.get("dispatch_token")
                if (
                    not token
                    or token_counts.get(token) != 1
                    or session_dispatch_token_counts.get(token) != 1
                ):
                    unmatched.append(p)
                    continue
                index = next(i for i, c in enumerate(available) if c["dispatch_token"] == token)
                _apply_promotion(p, available[index], "dispatch-token")
                used.add(index)
            leftover = [c for i, c in enumerate(typed) if i not in used]
            if len(unmatched) == 1 and len(leftover) == 1:
                _apply_promotion(unmatched[0], leftover[0], "one-to-one")


def _apply_promotion(receipt: dict, completion: dict, join: str) -> None:
    """dispatch 行の観測を completion 行の観測で確定させる。

    verdict と response digest は **completion 行** を正とする。dispatch 行の digest は
    起動受理 payload のもので、監査結果を何も表していないため receipt の束縛先にできない。
    """
    receipt["verdict_state"] = "resolved"
    receipt["verdict"] = completion["verdict"]
    receipt["response_sha256"] = completion["response_sha256"]
    receipt["promoted_by"] = join
    receipt["completion_agent_id"] = completion.get("agent_id")


def load_fork_ledger(path) -> dict:
    """JSONL 台帳を subagent と session 単位で集計する。

    部分破損した追記専用台帳では、壊れた行を数えつつ健全な fork 証跡を保持する。
    """
    if path is None:
        return empty_ledger()
    ledger_path = Path(path)
    if not ledger_path.is_file():
        return {
            "path": str(ledger_path),
            "exists": False,
            "dispatched": {},
            "sessions": {},
            "receipts": {},
            "receipts_v12": {},
            "malformed": 0,
        }
    dispatched: dict[str, int] = {}
    sessions: dict[str, dict[str, int]] = {}
    receipts: dict[str, dict[str, dict[str, dict[str, str]]]] = {}
    receipts_v12: dict[str, dict[str, list[dict[str, str]]]] = {}
    # session_id -> subagent_type -> [completion 行]。SubagentStop が書く 1.3 行の受け皿。
    completions: dict[str, dict[str, list[dict]]] = {}
    malformed = 0
    try:
        lines = ledger_path.read_text(encoding="utf-8").splitlines()
    except (OSError, UnicodeDecodeError):
        return {
            "path": str(ledger_path),
            "exists": False,
            "dispatched": {},
            "sessions": {},
            "receipts": {},
            "receipts_v12": {},
            "malformed": 0,
        }
    for line in lines:
        if not line.strip():
            continue
        try:
            record = json.loads(line)
        except json.JSONDecodeError:
            malformed += 1
            continue
        if not isinstance(record, dict) or record.get("tool_name") not in LEDGER_TOOL_NAMES:
            malformed += 1
            continue
        schema_version = record.get("schema_version")
        if schema_version == LEDGER_SCHEMA_COMPLETION:
            completion = _parse_completion(record)
            if completion is None:
                malformed += 1
            else:
                completions.setdefault(completion["session_id"], {}).setdefault(
                    completion["subagent_type"], []
                ).append(completion)
            continue
        if schema_version not in {LEDGER_SCHEMA_LEGACY, LEDGER_SCHEMA_TOOL_USE}:
            malformed += 1
            continue
        if schema_version == LEDGER_SCHEMA_LEGACY and record.get("tool_name") != "Task":
            # Current Agent calls expose tool_use_id. Treating Agent as legacy would allow
            # a malformed current receipt to bypass the schema 1.2 identity binding.
            malformed += 1
            continue
        subagent_type = record.get("subagent_type")
        session_id = record.get("session_id")
        prompt_sha256 = record.get("prompt_sha256")
        response_sha256 = record.get("response_sha256")
        audit_verdict = record.get("audit_verdict")
        if (
            not isinstance(subagent_type, str)
            or not subagent_type
            or not isinstance(session_id, str)
            or not session_id
            or not isinstance(prompt_sha256, str)
            or not PROMPT_SHA256_RE.fullmatch(prompt_sha256)
            or not isinstance(response_sha256, str)
            or not RESPONSE_SHA256_RE.fullmatch(response_sha256)
        ):
            malformed += 1
            continue
        receipt = {
            "subagent_type": subagent_type,
            "tool_name": record["tool_name"],
            "response_sha256": response_sha256,
            "verdict": audit_verdict,
        }
        if schema_version == LEDGER_SCHEMA_TOOL_USE:
            tool_use_id = record.get("tool_use_id")
            if not isinstance(tool_use_id, str) or not tool_use_id:
                malformed += 1
                continue
            receipt["verdict_state"] = record.get("verdict_state")
            token = record.get("dispatch_token")
            receipt["dispatch_token"] = token if isinstance(token, str) and token else None
            receipts_v12.setdefault(session_id, {}).setdefault(tool_use_id, []).append(receipt)
            # 未確定 (pending) の計上は completion 行による昇格の **後** に行う。ここで数えると
            # 非同期 fork が必ず破損扱いになり、昇格で解消した行まで破損として残ってしまう。
            continue
        if audit_verdict not in ASPECT_VERDICTS:
            malformed += 1
            continue
        dispatched[subagent_type] = dispatched.get(subagent_type, 0) + 1
        by_session = sessions.setdefault(subagent_type, {})
        by_session[session_id] = by_session.get(session_id, 0) + 1
        receipts.setdefault(subagent_type, {}).setdefault(session_id, {})[response_sha256] = receipt

    # 非同期 fork の dispatch 行は起動受理しか観測できず pending のまま残る。SubagentStop が
    # 追記した completion 行を join して昇格させる (台帳は append-only のまま = 既存行は不変)。
    promote_completions(receipts_v12, completions)

    # schema 1.2 の識別子は session 内で一意でなければならない。候補を list のまま保持し、
    # 重複・競合を last-write-wins に潰さず照合時にも fail-closed で拒否する。
    for session_id, by_tool_use in receipts_v12.items():
        for candidates in by_tool_use.values():
            if len(candidates) != 1:
                malformed += len(candidates)
                continue
            receipt = candidates[0]
            if receipt.get("verdict_state") != "resolved" or receipt.get("verdict") not in ASPECT_VERDICTS:
                # 昇格しても未確定なら破損として計上する (下流の診断文へ件数を出すため)。
                malformed += 1
                continue
            subagent_type = receipt["subagent_type"]
            dispatched[subagent_type] = dispatched.get(subagent_type, 0) + 1
            by_session = sessions.setdefault(subagent_type, {})
            by_session[session_id] = by_session.get(session_id, 0) + 1
    return {
        "path": str(ledger_path),
        "exists": True,
        "dispatched": dispatched,
        "sessions": sessions,
        "receipts": receipts,
        "receipts_v12": receipts_v12,
        "completions": completions,
        "malformed": malformed,
    }


def agent_definition_exists(auditor: str) -> bool:
    """監査名が plugin 同梱 agent 定義へ安全に解決できるかを検証する。"""
    if not isinstance(auditor, str) or not auditor or "/" in auditor or auditor.startswith("."):
        return False
    return (_plugin_root() / "agents" / f"{auditor}.md").is_file()


def ledger_corroborates(delegation: dict, ledger: dict) -> tuple[bool, str]:
    """receipt が実 fork の session・tool・response verdict へ束縛されるか検証する。"""
    dispatch = delegation.get("dispatch")
    subagent_type = dispatch.get("subagent_type") if isinstance(dispatch, dict) else None
    if not ledger.get("exists"):
        return False, (
            f"fork 台帳が存在しない ({ledger.get('path')}) ため独立監査の帰属を裏取りできない "
            f"(PostToolUse hook record-audit-fork.py の配線を確認するか、監査を実 fork して再評価する)"
        )
    if not isinstance(subagent_type, str) or not subagent_type:
        return False, "dispatch.subagent_type が無く fork 台帳と突合できない"
    declared_session = dispatch.get("session_id")
    if not isinstance(declared_session, str) or not declared_session:
        return False, (
            "dispatch.session_id が無く fork 台帳の run/session と突合できない "
            "(宣言の無い帰属は自己申告のまま。R2 が fork 起動時の session_id を receipt へ記録する)"
        )
    if declared_session == "unknown":
        return False, (
            "dispatch.session_id='unknown' は run/session 束縛の裏取りに使えない "
            "(session 不明の fork は過去 run の 'unknown' 行と区別できない。"
            "session_id を観測できるハーネスで再評価する)"
        )
    response_sha256 = dispatch.get("response_sha256")
    if not isinstance(response_sha256, str) or not RESPONSE_SHA256_RE.fullmatch(response_sha256):
        return False, (
            "dispatch.response_sha256 が無いか不正で、実監査 response の verdict と突合できない "
            "(PostToolUse hook が記録した response digest を receipt へ転記する)"
        )

    tool_use_id = dispatch.get("tool_use_id")
    if tool_use_id is not None:
        if not isinstance(tool_use_id, str) or not tool_use_id:
            return False, "dispatch.tool_use_id が空または不正で schema 1.2 台帳と突合できない"
        candidates = ledger.get("receipts_v12", {}).get(declared_session, {}).get(tool_use_id, [])
        if len(candidates) > 1:
            signatures = {
                (
                    item.get("subagent_type"),
                    item.get("tool_name"),
                    item.get("response_sha256"),
                    item.get("verdict"),
                )
                for item in candidates
                if isinstance(item, dict)
            }
            kind = "重複" if len(signatures) == 1 else "競合"
            return False, (
                f"schema 1.2 台帳の (session_id={declared_session!r}, tool_use_id={tool_use_id!r}) が{kind}している "
                "(append-only 台帳を last-write-wins で解釈できない)"
            )
        if not candidates:
            return False, (
                f"schema 1.2 台帳に (session_id={declared_session!r}, tool_use_id={tool_use_id!r}) の"
                "監査完了記録が無い (別 dispatch の ID を転記した疑い)"
            )
        recorded = candidates[0]
        if recorded.get("verdict_state") != "resolved" or recorded.get("verdict") not in ASPECT_VERDICTS:
            return False, (
                f"schema 1.2 台帳の tool_use_id={tool_use_id!r} は verdict_state=resolved かつ"
                "有効な audit_verdict でない (未確定・曖昧な PASS を監査完了として扱えない)"
            )
        expected = {
            "subagent_type": subagent_type,
            "tool_name": dispatch.get("tool"),
            "response_sha256": response_sha256,
            "verdict": delegation.get("verdict"),
        }
        mismatches = [
            name for name, value in expected.items() if recorded.get(name) != value
        ]
        if mismatches:
            return False, (
                f"schema 1.2 receipt が hook 観測値と一致しない ({', '.join(mismatches)}) "
                "(session/subagent/tool/response/verdict を同一 dispatch へ束縛する)"
            )
        return True, ""

    # schema 1.2 行へ digest だけで接地すると、同一 message 内の別 dispatch を取り違えられる。
    # 一致候補がある receipt は tool_use_id 欠落として拒否し、1.1 へ downgrade しない。
    v12_matches = [
        item
        for candidates in ledger.get("receipts_v12", {}).get(declared_session, {}).values()
        for item in candidates
        if isinstance(item, dict)
        and item.get("subagent_type") == subagent_type
        and item.get("response_sha256") == response_sha256
    ]
    if v12_matches:
        return False, (
            "dispatch.tool_use_id が無く schema 1.2 台帳の dispatch と突合できない "
            "(response digest のみで 1.1 互換経路へ downgrade しない)"
        )

    if dispatch.get("tool") == "Agent":
        return False, (
            "現行 Agent dispatch には tool_use_id が必須で、schema 1.1 legacy 経路へ "
            "downgrade できない (legacy receipt は Task 専用)"
        )

    if ledger.get("dispatched", {}).get(subagent_type, 0) < 1:
        malformed = ledger.get("malformed", 0)
        suffix = f" / 台帳の破損行 {malformed} 件" if malformed else ""
        return False, (
            f"fork 台帳に subagent_type={subagent_type!r} の完了記録が無い "
            f"(独立監査を起動せずに帰属だけ宣言している疑い。台帳={ledger.get('path')}{suffix})"
        )
    recorded_sessions = ledger.get("sessions", {}).get(subagent_type, {})
    if declared_session not in recorded_sessions:
        return False, (
            f"fork 台帳に (session_id={declared_session!r}, subagent_type={subagent_type!r}) の完了記録が無い "
            f"(宣言 session が台帳へ接地しない = 過去 run の名指し違い / fork 省略 / 偽装の疑い。"
            f"当該 subagent_type の観測済み session {len(recorded_sessions)} 種)"
        )
    recorded = ledger.get("receipts", {}).get(subagent_type, {}).get(declared_session, {}).get(response_sha256)
    if not isinstance(recorded, dict):
        return False, (
            f"fork 台帳に response_sha256={response_sha256!r} の監査完了記録が無い "
            "(別 fork の verdict を流用したか、hook が最終 AUDIT_VERDICT marker を観測できていない)"
        )
    if dispatch.get("tool") != recorded.get("tool_name"):
        return False, (
            f"dispatch.tool={dispatch.get('tool')!r} が hook 観測値 {recorded.get('tool_name')!r} と不一致"
        )
    if delegation.get("verdict") != recorded.get("verdict"):
        return False, (
            f"receipt verdict={delegation.get('verdict')!r} が hook 観測の auditor verdict={recorded.get('verdict')!r} と不一致 "
            "(監査結果を緑化のために書き換えている)"
        )
    return True, ""


def validate_attribution(
    report: dict, ledger: dict | None = None, expected_session: str | None = None
) -> list[str]:
    """独立監査 receipt を実 fork 証跡へ fail-closed で接地する。"""
    violations: list[str] = []
    ledger = ledger if isinstance(ledger, dict) else empty_ledger()
    aspects = report.get("aspects") if isinstance(report.get("aspects"), dict) else {}
    delegations = report.get("audit_delegations")
    if not isinstance(delegations, list):
        violations.append("audit_delegations: 配列でない (独立監査の fork receipt 一覧が無い = 帰属が自己申告のまま)")
        delegations = []

    seen: dict[tuple, dict] = {}
    for index, delegation in enumerate(delegations):
        if not isinstance(delegation, dict):
            violations.append(f"audit_delegations[{index}]: オブジェクトでない")
            continue
        aspect, role = delegation.get("aspect"), delegation.get("role")
        if aspect not in ASPECTS:
            violations.append(f"audit_delegations[{index}].aspect={aspect!r} が未知の観点")
            continue
        if role not in DELEGATION_ROLES:
            violations.append(f"audit_delegations[{index}].role={role!r} が {sorted(DELEGATION_ROLES)} 外")
            continue
        if (aspect, role) in seen:
            violations.append(f"audit_delegations: (aspect={aspect}, role={role}) の receipt が重複")
            continue
        seen[(aspect, role)] = delegation

    required = required_delegations()
    required_keys = {(item["aspect"], item["role"]) for item in required}
    declared_sessions: set[str] = set()
    for requirement in required:
        aspect, role = requirement["aspect"], requirement["role"]
        delegation = seen.get((aspect, role))
        if delegation is None:
            violations.append(
                f"audit_delegations: {aspect} の {role} 監査 ({requirement['auditor']}/{requirement['component']}) の "
                "fork receipt が無い (独立監査の帰属が自己申告のまま)"
            )
            continue
        label = f"audit_delegations[{aspect}/{role}]"
        if delegation.get("auditor") != requirement["auditor"]:
            violations.append(f"{label}.auditor != {requirement['auditor']!r} (観点↔監査 agent 対応)")
        if delegation.get("component") != requirement["component"]:
            violations.append(f"{label}.component != {requirement['component']!r}")
        if not agent_definition_exists(delegation.get("auditor")):
            violations.append(f"{label}.auditor={delegation.get('auditor')!r} に対応する agent 定義が plugin に実在しない")
        dispatch = delegation.get("dispatch")
        if not isinstance(dispatch, dict):
            violations.append(f"{label}.dispatch: オブジェクトでない (fork の起動方法が記録されていない)")
        else:
            if dispatch.get("tool") not in LEDGER_TOOL_NAMES:
                violations.append(
                    f"{label}.dispatch.tool={dispatch.get('tool')!r} が {list(LEDGER_TOOL_NAMES)} 外"
                    " (独立 context の fork は subagent 起動ツール経由必須)"
                )
            if dispatch.get("subagent_type") != requirement["auditor"]:
                violations.append(f"{label}.dispatch.subagent_type != {requirement['auditor']!r}")
            session_id = dispatch.get("session_id")
            if isinstance(session_id, str) and session_id:
                declared_sessions.add(session_id)
        delegation_verdict = delegation.get("verdict")
        if delegation_verdict not in ASPECT_VERDICTS:
            violations.append(f"{label}.verdict={delegation_verdict!r} が {sorted(ASPECT_VERDICTS)} 外")
        elif role == "primary":
            aspect_value = aspects.get(aspect)
            aspect_verdict = aspect_value.get("verdict") if isinstance(aspect_value, dict) else None
            if aspect_verdict in ASPECT_VERDICTS and delegation_verdict != aspect_verdict:
                violations.append(
                    f"{label}.verdict={delegation_verdict!r} が aspects[{aspect}].verdict={aspect_verdict!r} と不一致 "
                    "(独立監査の判定が観点 verdict へ忠実に転記されていない)"
                )
        evidence = delegation.get("evidence")
        if not isinstance(evidence, list) or not evidence:
            violations.append(f"{label}.evidence: 非空配列でない (監査の根拠が空)")
        corroborated, reason = ledger_corroborates(delegation, ledger)
        if not corroborated:
            violations.append(f"{label}: {reason}")

    if len(declared_sessions) > 1:
        violations.append(
            "audit_delegations: 必須 receipt の dispatch.session_id が単一の評価 run に収束していない "
            f"(宣言された session {len(declared_sessions)} 種: {sorted(declared_sessions)}。"
            "複数 run の fork 記録を組み合わせた帰属は 1 回の独立監査の裏取りにならない)"
        )
    if expected_session and declared_sessions and declared_sessions != {expected_session}:
        violations.append(
            f"audit_delegations: 宣言 session {sorted(declared_sessions)} が評価 run の session "
            f"{expected_session!r} と一致しない (過去 run の fork 記録を今回の評価の裏取りへ流用している疑い)"
        )
    for aspect, role in seen:
        if (aspect, role) in required_keys:
            continue
        if role == "primary" and ASPECTS[aspect]["auditor"] == EVALUATOR_NAME:
            violations.append(
                f"audit_delegations: {aspect} は C05 自前評価の観点であり primary の独立監査 receipt を "
                "持てない (虚偽の独立性主張)"
            )
        else:
            violations.append(f"audit_delegations: (aspect={aspect}, role={role}) は必須 receipt 一覧に無い未知の委譲")
    return violations
