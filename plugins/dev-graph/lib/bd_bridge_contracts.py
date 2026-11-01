"""bd-bridge が受理する語彙 (exact-set) と、外部 I/O を持たない判定ロジック (import 専用 module)。

`scripts/bd-bridge.py` は Beads への唯一の書込チョークポイントであり、そこで「何を
受理するか」を決める定数と、bd の応答 row を解釈するだけの純粋関数をこの module に
集める。CLI 引数解析・bd 実行・promotion gate・receipt 出力は script 側に残す。

分離の基準は **外部状態に触るか**。ここに置く関数は引数だけで結果が決まるため、
bd も git も filesystem も要らない。graph / manifest / spec を読むものは
``bd_bridge_graph``、bd を数えるだけの監査は ``bd_bridge_audit`` へ置く。

正本契約: references/execution-tracker-contract.md
"""
from __future__ import annotations

import sys

sys.dont_write_bytecode = True

import hashlib
import json
import re
from pathlib import Path
from typing import Any

SCRIPTS = Path(__file__).resolve().parents[1] / "scripts"
if str(SCRIPTS) not in sys.path:
    sys.path.insert(0, str(SCRIPTS))

from _common import ContractError

MUTATIONS = {"create", "update", "dep-add", "dep-remove", "close", "claim", "github-push", "gate-add", "reconcile-duplicates"}
PHASES = [f"P{i:02d}" for i in range(1, 14)]
SHA256 = re.compile(r"^sha256:[0-9a-f]{64}$")
RFC3339_UTC = re.compile(r"^\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}(?:\.\d+)?Z$")
# ready 候補が parity manifest に載らなかった理由の exact-set。
# 「graph 管理外の bd 課題」と「graph 管理下なのに manifest から落ちた課題」は
# 対処 owner が違う (前者は放置可・後者は sync 必要) ため、同じ袋へ入れない。
# `graph_node_missing` は「external_ref が指す node が graph から消えている」= C02 案件で、
# sync を何度回しても解消しない。これを `parity_manifest_missing` に混ぜると、GC 削除の
# 残置が「sync すれば直る取りこぼし」を装って常駐し、本物の取りこぼしを覆い隠す。
# 全 issue を対象にした逆方向の棚卸しは `--op orphan-audit` が担う。
UNMAPPED_REASONS = ("external_ref_absent", "graph_node_missing", "parity_manifest_missing")
# --op orphan-audit が付ける仕分け札の exact-set。UNMAPPED_REASONS と同じ理由で、
# 対処 owner と次の一手が違うものを同じ袋へ入れない。
# restore_node:     spec 実体が content_roots に在るのに graph 未登録 → C02 build-graph-node.py で復元。
# merge_pending:    他 ref の graph に node が実在 → 参照は正しい。対処不要、当該 ref のマージ待ち。
# repoint_or_close: どこにも実体が無い → 実在 node への張り替えか失効かを中身から人が決める。
ORPHAN_DISPOSITIONS = ("restore_node", "merge_pending", "repoint_or_close")
# graph node を物理削除するときに人が選べる処分の exact-set。
# bridge 自身は close/detach を実行しない。実状態が選択どおり収束したことを read-only で
# 確認してから削除を許可し、未解決 issue の silent drop を不可能にする。
REMOVAL_DISPOSITIONS = ("cancel_deletion", "close_issue_first", "detach_external_ref_first")
# spec markdown の frontmatter から graph_node_id を読む式。C02 build-graph-node.py が graph node
# へ写す field と同名で、spec 実体と node の対応を決める唯一の手がかり。
FRONTMATTER_NODE_ID = re.compile(r"^graph_node_id:\s*[\"']?([^\"'\r\n]+?)[\"']?\s*$", re.M)
# MVP-first: parity manifest の mvp_fit で ready_set の表示順を決める rank。
# schedule-graph.py (C16) も候補の選定順にこの定数を import するので、C16 と C28 の順は食い違わない。
# 受理する非 null 値は build-parity-manifest.py `_mvp_fit` の受理集合と一致必須
# (test_bd_bridge_mvp_ready_order.py が固定する)。
MVP_FIT_RANK: dict[str | None, int] = {"direct": 0, "enabling": 1, None: 2, "deferred": 3}
# --op update が bd update へ転送してよい field の exact-set。
# bridge が単一チョークポイントである以上、ここに無い field は運用上「存在しない」ため、
# 受理する field は網羅的に宣言し、転送忘れ (silent drop) を構造的に起こせなくする。
# priority/assignee/labels は契約 §2 の parity 突合対象外 ("bd 側自由領域") だが、
# 「突合しない」は「bridge を通さない」ではない。C10 guard は bd 直接実行を field 単位で
# 選り分けず全面遮断するため、ここに宣言されて初めてこの 3 field は到達経路を持つ。
# labels の写像先は置換系の `--set-labels` 一本に限る。`--add-label`/`--remove-label` を
# 併せて受けると同一 run の適用順で結果が変わり、receipt から最終状態を再現できなくなる。
UPDATE_FIELDS: tuple[tuple[str, str], ...] = (
    ("status", "--status"),
    ("title", "--title"),
    ("description", "--description"),
    ("notes", "--notes"),
    ("append_notes", "--append-notes"),
    ("design", "--design"),
    ("priority", "--priority"),
    ("assignee", "--assignee"),
    ("labels", "--set-labels"),
)
PRIORITY_ALIASES = {
    "critical": "0",
    "high": "1",
    "medium": "2",
    "low": "3",
    "backlog": "4",
}


def rows(value: Any) -> list[dict[str, Any]]:
    if isinstance(value, list): return [row for row in value if isinstance(row, dict)]
    if isinstance(value, dict):
        for key in ("issues", "results", "data"):
            candidate = value.get(key)
            if isinstance(candidate, list): return [row for row in candidate if isinstance(row, dict)]
        return [value]
    return []


def workspace_identity(value: Any) -> dict[str, Any]:
    identified = rows(value)
    if len(identified) != 1: raise ContractError("bd where must identify exactly one workspace")
    row = identified[0]
    identity_keys = ("database_path", "prefix", "schema_version") if row.get("database_path") else ("path", "prefix", "schema_version", "workspace", "id")
    stable = {key: str(row[key]) for key in identity_keys if row.get(key) is not None}
    if not stable: raise ContractError("bd where did not expose a stable workspace identity")
    fingerprint = hashlib.sha256(json.dumps(stable, sort_keys=True, separators=(",", ":")).encode()).hexdigest()
    return {"workspace_id": f"bdw_{fingerprint[:24]}", "attributes": stable}


def issue_row(value: Any, issue_id: str) -> dict[str, Any]:
    matched = [row for row in rows(value) if str(row.get("id")) == issue_id]
    if len(matched) != 1: raise ContractError(f"bd show did not return exactly one issue: {issue_id}")
    return matched[0]


def dependency_ids(issue: dict[str, Any]) -> set[str]:
    raw = issue.get("dependencies", [])
    if not isinstance(raw, list): raise ContractError("bd show dependencies must be an array")
    result: set[str] = set()
    for item in raw:
        relation = (item.get("dependency_type") or item.get("type")) if isinstance(item, dict) else None
        if relation not in (None, "blocks"):
            continue
        dep = item.get("id") if isinstance(item, dict) else item
        if not isinstance(dep, str) or not dep: raise ContractError("bd dependency is missing its id")
        result.add(dep)
    return result


def verify_parity(issue: dict[str, Any], expected_status: str | None, expected_dependencies: list[str]) -> dict[str, Any]:
    if not expected_status: raise ContractError("parity verification requires --expected-status")
    expected = set(expected_dependencies)
    actual = dependency_ids(issue)
    status_match = issue.get("status") == expected_status
    edges_match = actual == expected
    receipt = {
        "confirmed": status_match and edges_match,
        "expected_status": expected_status,
        "actual_status": issue.get("status"),
        "expected_depends_on": sorted(expected),
        "actual_depends_on": sorted(actual),
        "missing_edges": sorted(expected - actual),
        "unexpected_edges": sorted(actual - expected),
    }
    if not receipt["confirmed"]: raise ContractError(f"Beads parity conflict: {json.dumps(receipt, sort_keys=True)}")
    return receipt


def external_ref(row: dict[str, Any]) -> str | None:
    direct = row.get("external_ref") or row.get("externalRef")
    if isinstance(direct, str) and direct:
        return direct.removeprefix("dev-graph:").removeprefix("external_ref:")
    match = re.search(r"(?:^|\s)external_ref:([^\s]+)", str(row.get("description", "")))
    return match.group(1) if match else None


def unmapped_reason(ref: str | None, graph_node_ids: set[str] | None) -> str:
    """ready 候補が manifest に載らない理由を、対処 owner が分かる粒度で決める。

    `graph_node_ids` が None なのは manifest 自体が渡されていない場合だけで、そのときは
    「投影が存在しない」ことが原因なので `parity_manifest_missing` を返す。
    """
    if not ref:
        return "external_ref_absent"
    if graph_node_ids is not None and ref not in graph_node_ids:
        return "graph_node_missing"
    return "parity_manifest_missing"


def normalize_priority(value: str) -> str:
    """dev-graph / Beads 双方の priority 語彙を Beads の数値表現へ正規化する。"""
    normalized = value.strip().lower()
    if normalized in PRIORITY_ALIASES:
        return PRIORITY_ALIASES[normalized]
    match = re.fullmatch(r"p?([0-4])", normalized)
    if match:
        return match.group(1)
    raise ContractError("priority must be critical|high|medium|low|backlog or 0-4/P0-P4")


def normalize_labels(value: str) -> str:
    """`--labels` のカンマ区切り入力を bd `--set-labels` の単一引数へ正規化する。

    空値を受理しないのは fail-closed の一貫性による。`--set-labels` は repeatable な
    strings フラグで、空文字が全消去か空 label 1 件かは bd の公開 surface に規定がない。
    未検証の意味論へ依存せず拒否し、全消去が必要なら専用 operation を別途定義する。
    """
    labels = [item.strip() for item in value.split(",")]
    if any(not item for item in labels):
        raise ContractError("labels must be a comma-separated list of non-empty values")
    return ",".join(labels)


# 転送前に値を畳む field。ここに無い field は生値をそのまま bd へ渡す。
UPDATE_FIELD_NORMALIZERS = {
    "priority": normalize_priority,
    "labels": normalize_labels,
}


def requested_update_fields(args: Any) -> list[str]:
    """明示指定された update field を argparse dest 名で順序どおり返す。

    判定は truthiness ではなく ``is not None`` で行う。``--notes ""`` は argparse に
    届いた時点で「消去の明示指定」であり、真偽値で落とすと指定が黙って消える
    (転送忘れと同じ silent drop の失敗形) ため。
    """
    return [dest for dest, _ in UPDATE_FIELDS if getattr(args, dest, None) is not None]


def validate_update_fields(requested: list[str]) -> None:
    """update 要求の受理可否を判定し、不正なら ContractError を送出する。

    field 皆無の update は bd 側では成功扱いの no-op になるため、呼び出し側から
    「反映された」と「何も渡っていなかった」を区別できない。本 bridge の他の契約検証と
    同じく fail-closed で落とす。notes の置換/追記同時指定も bd の適用順に依存させない。
    """
    if not requested:
        raise ContractError(f"update requires at least one of: {', '.join(flag for _, flag in UPDATE_FIELDS)}")
    if {"notes", "append_notes"} <= set(requested):
        raise ContractError("update accepts --notes or --append-notes, not both")


def update_argv(args: Any) -> tuple[list[str], list[str], dict[str, str]]:
    """update field を bd argv へ写し、適用名と正規化後の値を返す。"""
    requested = requested_update_fields(args)
    validate_update_fields(requested)
    flags: list[str] = []
    normalized: dict[str, str] = {}
    for dest, flag in UPDATE_FIELDS:
        value = getattr(args, dest, None)
        if value is not None:
            normalize = UPDATE_FIELD_NORMALIZERS.get(dest)
            value = normalize(value) if normalize else value
            normalized[dest] = value
            flags += [flag, value]
    return flags, requested, normalized
