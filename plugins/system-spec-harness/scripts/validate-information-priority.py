#!/usr/bin/env python3
# /// script
# name: validate-information-priority
# version: 0.1.0
# purpose: 任意の表現物の information priority map を検証する決定論ゲート。schema 形状だけでは表せない「順位確定より先に装飾していない」「削除に理由がある」「装飾が意味を運ぶ」「色だけに意味を担わせていない」を機械検査し、情報設計を主観レビューから設計判断へ移す。知識正本 = ref-system-design-knowledge/references/information-design.md。
# inputs:
#   - argv: [MAP_JSON ...]  # information-priority-map.schema.json 準拠の JSON
# outputs:
#   - stdout: OK summary
#   - stderr: violation 一覧
#   - exit: 0=OK / 1=violation / 2=usage error
# contexts: [E, C]
# network: false
# write-scope: none
# dependencies: []
# requires-python: ">=3.9"
# ///
"""Information priority map の決定論ゲート。

read-only / stdlib-only。JSON Schema (schemas/information-priority-map.schema.json) が
形状の SSOT だが、本 script はそれに加えて **手順の順序制約** を検査する。
すなわち「装飾 (styling/emphasis) は順位 (groups[].rank) が確定してからでないと書けない」
という information-design の中核制約を、宣言の整合性として機械検出する。

意味の妥当性 (その順位が本当に正しいか) は content-review / human の未閉塞責務である。
本 gate が保証するのは well-formedness と順序制約のみで、良いデザインを保証しない。
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

DISPOSITIONS = {"keep", "drop", "transform"}
SEMANTIC_INTENTS = {
    "actionable",
    "selected",
    "important",
    "hidden-affordance",
    "status",
    "grouping",
    "disabled",
}
CHANNELS = {"position", "size", "weight", "color", "spacing", "contrast", "icon", "motion"}
EXPERTISE = {"first-time", "occasional", "expert", "mixed"}
LEVELS = {"high", "medium", "low"}


def _require(obj: dict, keys: tuple[str, ...], where: str, errors: list[str]) -> bool:
    missing = [k for k in keys if k not in obj]
    if missing:
        errors.append(f"{where}: 必須キー欠落 {missing}")
        return False
    return True


def validate(doc: dict) -> list[str]:
    """violation メッセージの一覧を返す (空 list = OK)。"""
    errors: list[str] = []
    if not isinstance(doc, dict):
        return ["ルートが object でない"]

    if not _require(
        doc,
        ("artifact_id", "artifact_kind", "context_of_use", "inventory", "groups", "form_selection"),
        "root",
        errors,
    ):
        return errors

    # ── context of use: 形式より先に文脈が決まっていること ──────────────
    ctx = doc["context_of_use"]
    if not isinstance(ctx, dict):
        errors.append("context_of_use: object でない")
        ctx = {}
    elif _require(ctx, ("audience", "primary_tasks", "environment", "expertise"), "context_of_use", errors):
        if ctx["expertise"] not in EXPERTISE:
            errors.append(f"context_of_use.expertise: 未知の値 {ctx['expertise']!r}")
        tasks = ctx["primary_tasks"]
        if not isinstance(tasks, list) or not tasks:
            errors.append("context_of_use.primary_tasks: 1 件以上必要 (task が無ければ順位は決められない)")
        else:
            for i, t in enumerate(tasks):
                if not isinstance(t, dict) or not _require(
                    t, ("task", "frequency", "failure_cost"), f"primary_tasks[{i}]", errors
                ):
                    continue
                for key in ("frequency", "failure_cost"):
                    if t[key] not in LEVELS:
                        errors.append(f"primary_tasks[{i}].{key}: high/medium/low 以外 ({t[key]!r})")

    # ── groups: 順位が本当に順位であること ──────────────────────────────
    groups = doc["groups"]
    group_ids: set[str] = set()
    ranks: list[int] = []
    if not isinstance(groups, list) or not groups:
        errors.append("groups: 1 件以上必要")
        groups = []
    for i, g in enumerate(groups):
        if not isinstance(g, dict) or not _require(
            g, ("group_id", "label", "rank", "rank_rationale"), f"groups[{i}]", errors
        ):
            continue
        if g["group_id"] in group_ids:
            errors.append(f"groups[{i}].group_id: 重複 {g['group_id']!r}")
        group_ids.add(g["group_id"])
        if not isinstance(g["rank"], int) or isinstance(g["rank"], bool) or g["rank"] < 1:
            errors.append(f"groups[{i}].rank: 1 以上の整数でない ({g['rank']!r})")
        else:
            ranks.append(g["rank"])
        if not str(g["rank_rationale"]).strip():
            errors.append(f"groups[{i}].rank_rationale: 空 (順位は理由とセットでしか成立しない)")
    if ranks and sorted(ranks) != list(range(1, len(ranks) + 1)):
        errors.append(
            f"groups[].rank: 1..{len(ranks)} の連番でない ({sorted(ranks)})。"
            "同順位や飛び番は『順位付けを避けた』状態で、強弱を写像できない"
        )

    # ── inventory: 削除と加工に理由が残っていること ─────────────────────
    inventory = doc["inventory"]
    element_ids: set[str] = set()
    kept: list[dict] = []
    if not isinstance(inventory, list) or not inventory:
        errors.append("inventory: 1 件以上必要")
        inventory = []
    for i, e in enumerate(inventory):
        if not isinstance(e, dict) or not _require(
            e, ("element_id", "source_value", "disposition"), f"inventory[{i}]", errors
        ):
            continue
        if e["element_id"] in element_ids:
            errors.append(f"inventory[{i}].element_id: 重複 {e['element_id']!r}")
        element_ids.add(e["element_id"])
        disp = e["disposition"]
        if disp not in DISPOSITIONS:
            errors.append(f"inventory[{i}].disposition: 未知の値 {disp!r}")
            continue
        if disp in ("drop", "transform") and not str(e.get("reason", "")).strip():
            errors.append(
                f"inventory[{i}] ({e['element_id']}): disposition={disp} だが reason が無い。"
                "理由なき削除/加工は『漏れ』と区別できない"
            )
        if disp == "transform" and not str(e.get("display_value", "")).strip():
            errors.append(f"inventory[{i}] ({e['element_id']}): transform だが display_value が無い")
        if disp == "keep" and e.get("display_value"):
            errors.append(
                f"inventory[{i}] ({e['element_id']}): keep なのに display_value がある。"
                "加工したなら disposition=transform にする"
            )
        if disp != "drop":
            kept.append(e)
            gid = e.get("group_id")
            if not gid:
                errors.append(
                    f"inventory[{i}] ({e['element_id']}): group_id が無い。"
                    "表示する要素はどれかの意味の束に属さなければならない (漏れなし)"
                )
            elif group_ids and gid not in group_ids:
                errors.append(f"inventory[{i}] ({e['element_id']}): group_id={gid!r} が groups に存在しない")
    if inventory and not kept:
        errors.append("inventory: 全要素が drop。表示する情報が残っていない")

    # 空 group (誰も属さない束) は順位の意味を壊す
    used_groups = {e.get("group_id") for e in kept}
    for gid in sorted(group_ids - used_groups):
        errors.append(f"groups: {gid!r} に属する表示要素が無い (空の束は順位を占有するだけ)")

    # member_order は実在かつ当該 group 所属
    for i, g in enumerate(groups):
        if not isinstance(g, dict):
            continue
        order = g.get("member_order")
        if order is None:
            continue
        if not isinstance(order, list):
            errors.append(f"groups[{i}].member_order: 配列でない")
            continue
        for eid in order:
            owner = next((e.get("group_id") for e in kept if e.get("element_id") == eid), None)
            if owner is None:
                errors.append(f"groups[{i}].member_order: {eid!r} が inventory の表示要素に無い")
            elif owner != g.get("group_id"):
                errors.append(f"groups[{i}].member_order: {eid!r} は group {owner!r} の要素")

    # ── form_selection: 早期形式固定の禁止 ──────────────────────────────
    form = doc["form_selection"]
    if not isinstance(form, dict):
        errors.append("form_selection: object でない")
    elif _require(form, ("chosen", "candidates_considered", "rationale"), "form_selection", errors):
        cands = form["candidates_considered"]
        if not isinstance(cands, list) or len(cands) < 2:
            errors.append(
                "form_selection.candidates_considered: 2 件以上必要。"
                "比較せずに形式を決めるのが最頻の失敗 (いきなり表を作る)"
            )
        else:
            for j, c in enumerate(cands):
                if not isinstance(c, dict) or not _require(
                    c, ("form", "why_not"), f"form_selection.candidates_considered[{j}]", errors
                ):
                    continue
                if not str(c["why_not"]).strip():
                    errors.append(f"candidates_considered[{j}]: why_not が空 (比較した記録にならない)")

    # ── 順序制約: 装飾は順位確定後にしか書けない ────────────────────────
    rank_by_group = {
        g["group_id"]: g["rank"]
        for g in groups
        if isinstance(g, dict) and "group_id" in g and isinstance(g.get("rank"), int)
    }
    group_of_element = {e["element_id"]: e.get("group_id") for e in kept if "element_id" in e}
    targets = group_ids | set(group_of_element)

    color_only: list[str] = []
    emphasis = doc.get("emphasis") or []
    if not isinstance(emphasis, list):
        errors.append("emphasis: 配列でない")
        emphasis = []
    for i, em in enumerate(emphasis):
        if not isinstance(em, dict) or not _require(
            em, ("target", "channel", "expresses_rank"), f"emphasis[{i}]", errors
        ):
            continue
        target = em["target"]
        if targets and target not in targets:
            errors.append(f"emphasis[{i}].target: {target!r} が group/表示要素に存在しない")
        chans = em["channel"]
        if not isinstance(chans, list) or not chans:
            errors.append(f"emphasis[{i}].channel: 1 件以上必要")
        else:
            unknown = [c for c in chans if c not in CHANNELS]
            if unknown:
                errors.append(f"emphasis[{i}].channel: 未知の視覚変数 {unknown}")
            if list(chans) == ["color"]:
                color_only.append(f"emphasis[{i}] ({target})")
        expected = rank_by_group.get(target if target in rank_by_group else group_of_element.get(target))
        if expected is None:
            continue
        if em["expresses_rank"] != expected:
            errors.append(
                f"emphasis[{i}] ({target}): expresses_rank={em['expresses_rank']} だが "
                f"所属 group の rank は {expected}。強弱が順位の写像になっていない"
            )

    styling = doc.get("styling") or []
    if not isinstance(styling, list):
        errors.append("styling: 配列でない")
        styling = []
    for i, st in enumerate(styling):
        if not isinstance(st, dict) or not _require(
            st, ("target", "decoration", "semantic_intent"), f"styling[{i}]", errors
        ):
            continue
        if targets and st["target"] not in targets:
            errors.append(f"styling[{i}].target: {st['target']!r} が group/表示要素に存在しない")
        if st["semantic_intent"] not in SEMANTIC_INTENTS:
            errors.append(
                f"styling[{i}].semantic_intent: {st['semantic_intent']!r} は意味の列挙に無い。"
                "装飾は『押せる/選択中/重要/隠れ機能/状態/グループ/無効』のどれかを表すためだけに使う"
            )

    # 装飾を書いているのに順位が無い = 手順の順序違反
    if (emphasis or styling) and not rank_by_group:
        errors.append(
            "emphasis/styling を宣言しているが groups[].rank が確定していない。"
            "情報設計では順位付けが装飾に先行する (逆順は『いきなり色を塗る』失敗)"
        )

    # ── アクセシビリティ: 色だけに意味を担わせない (WCAG 1.4.1) ─────────
    if color_only and not (doc.get("accessibility") or {}).get("color_not_sole_channel"):
        errors.append(
            f"色のみで強弱を表している項目がある ({', '.join(color_only)}) のに "
            "accessibility.color_not_sole_channel が真でない。"
            "色覚特性・モノクロ印刷・低コントラスト環境で情報が消える"
        )

    exemption = doc.get("exemption")
    if exemption is not None and not _require(exemption, ("reason", "approved_by"), "exemption", errors):
        pass

    return errors


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description="information priority map の決定論ゲート")
    ap.add_argument("maps", nargs="+", help="information-priority-map JSON のパス")
    args = ap.parse_args(argv)

    total = 0
    for raw in args.maps:
        path = Path(raw)
        if not path.exists():
            sys.stderr.write(f"USAGE ERROR: 入力が存在しない: {path}\n")
            return 2
        try:
            doc = json.loads(path.read_text(encoding="utf-8"))
        except json.JSONDecodeError as exc:
            sys.stderr.write(f"USAGE ERROR: {path}: JSON として読めない: {exc}\n")
            return 2
        errors = validate(doc)
        for message in errors:
            sys.stderr.write(f"VIOLATION: {path}: {message}\n")
        total += len(errors)

    if total:
        sys.stderr.write(f"FAIL: {total} 件の information-priority 違反\n")
        return 1
    print(f"OK information priority map ({len(args.maps)} file)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
