#!/usr/bin/env python3
"""Shared deterministic fixtures for spec-transition acceptance tests."""
from __future__ import annotations

import hashlib


FOUNDATION_U_LABELS = tuple(f"U{number}" for number in range(1, 10))
FOUNDATION_SOURCE_TEXTS = (
    "請求と監査を単一 Web システムへ統合し二重管理をなくす",
    "表計算と個別ツールが乱立し請求漏れと監査コストが慢性化している",
    "請求・監査データを単一の信頼できる情報源へ統合する",
    "請求漏れ検知を自動化する",
    "請求漏れ0件が3ヶ月継続する",
    "経理チーム",
    "請求管理を対象とし給与計算を対象外とする",
    "社内 k8s 上で稼働する",
    "日次バックアップを行う",
)


def effective_source_refs(
    *,
    qa_ids: tuple[str, ...] | None = None,
    approval_ids: tuple[str, ...] | None = None,
) -> dict[str, dict[str, str]]:
    """Return one effective QA/approval binding for each U1--U9."""
    qa_ids = qa_ids or tuple(f"qa-foundation-u{number}" for number in range(1, 10))
    approval_ids = approval_ids or ("appr-foundation",) * 9
    assert len(qa_ids) == len(approval_ids) == 9
    return {
        f"U{number}": {"qa_ref": qa_id, "approval_ref": approval_id}
        for number, (qa_id, approval_id) in enumerate(
            zip(qa_ids, approval_ids), start=1
        )
    }


def valid_foundation() -> dict:
    """Return a complete, user-approved U1--U9 foundation fixture."""
    return {
        "essential_purpose": "請求と監査を単一 Web システムへ統合し二重管理をなくす",
        "background": "表計算と個別ツールが乱立し請求漏れと監査コストが慢性化している",
        "goals": [
            {"id": "G1", "text": "請求・監査データを単一の信頼できる情報源へ統合する"},
            {"id": "G2", "text": "主要業務動線を Web だけで完結できるようにする"},
        ],
        "objectives": [{"id": "O1", "text": "請求漏れ検知を自動化", "measure": "月次0件"}],
        "success_criteria": ["請求漏れ0件が3ヶ月継続"],
        "stakeholders": ["経理チーム"],
        "scope": {"in": ["請求管理"], "out": ["給与計算"]},
        "constraints": ["社内 k8s 上で稼働"],
        "concrete_intents": [{"id": "I1", "text": "日次バックアップ", "serves": ["G1"]}],
        "confirmed": True,
        "approval_ref": "appr-foundation",
        "effective_source_refs": effective_source_refs(),
        "approval_note": "上位概念 U1-U9 をユーザーと確認し合意した",
    }


def foundation_source_turns(*, written: bool = False) -> list[dict]:
    """Return U1--U9 one-topic source turns accepted by the writer gate."""
    turns = []
    for number, (label, answer) in enumerate(
        zip(FOUNDATION_U_LABELS, FOUNDATION_SOURCE_TEXTS), start=1
    ):
        source = {"kind": "user-dialogue"}
        question = f"利用者との対話で {label} は何か"
        if written:
            source = {
                "kind": "written-requirements",
                "path": "requirements-brief.md",
                "section": "§1",
                "sha256": hashlib.sha256(answer.encode("utf-8")).hexdigest(),
            }
            question = f"書面入力 requirements-brief.md §1 の {label} は何か"
        turns.append(
            {
                "qa_id": f"qa-foundation-u{number}",
                "question": question,
                "answer": answer,
                "source": source,
                "ops": [],
            }
        )
    return turns


def record_foundation_sources(mod, state, *, written: bool = False) -> None:
    """Use the normal chunk path; preserve the production five-turn limit."""
    turns = foundation_source_turns(written=written)
    assert mod.run_chunk(state, turns[:5], max_loops=5) == 5
    assert mod.run_chunk(state, turns[5:], max_loops=5) == 4
