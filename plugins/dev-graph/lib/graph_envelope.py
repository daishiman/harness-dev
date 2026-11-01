"""graph store の外枠 (envelope) 契約。

nodes[] の中身は C11 (`validate-graph-schema.py`) が検査するが、それを包む外枠はどこも
検査していなかった。C11 は ``nodes_of()`` で nodes[] を取り出した時点で外枠を捨てる。

C10 PreToolUse は「interpreter 起動 x 書込み動詞 x authority path」をコマンド文字列から読むため、
書込みを別 script file へ移す間接起動を原理的に遮断できない。遮断が閉じない以上、store 側で
「正規 writer が書いた形か」を検査できる層が要る。ここはその層の最小核であり、C11・PostToolUse
監査 (`hooks/audit-graph-authority-drift.py`) が同じ定義を参照するための単一の置き場である。

必須 key は C02 writer が必ず残す 3 つ (`build-init-scaffold.py` の初期 graph と同じ)。
`repository_id` は任意 key として認める: 初期 graph は持たないが、既存 store が持っていれば
writer (`build-graph-node.py` / `register-package.py`) はそのまま引き継ぐ。

envelope 検査は fail-closed だが nodes[] の意味論には踏み込まない。外枠が canonical でも
nodes[] が改竄されている可能性は残るため、C11 の node 検査を置き換えるものではない。
"""
from __future__ import annotations

from typing import Any

SCHEMA_VERSION = "1.0.0"
REQUIRED_GRAPH_KEYS = frozenset({"schema_version", "graph_revision", "nodes"})
OPTIONAL_GRAPH_KEYS = frozenset({"repository_id"})
CANONICAL_GRAPH_KEYS = REQUIRED_GRAPH_KEYS | OPTIONAL_GRAPH_KEYS


def envelope_violations(
    document: Any,
    *,
    repository_id: str | None = None,
) -> list[str]:
    """canonical envelope からの逸脱を人間可読な文字列で返す (逸脱が無ければ空)。

    ``repository_id`` を渡した場合、store が `repository_id` を持つときだけ repo config との
    一致まで検査する。C11 は config を読まない経路 (stdin preview) からも呼ばれるため、突合は
    呼び出し側の任意とする。
    """
    if not isinstance(document, dict):
        return ["graph store must be a JSON object with the canonical envelope"]
    violations: list[str] = []
    unknown = sorted(set(document) - CANONICAL_GRAPH_KEYS)
    missing = sorted(REQUIRED_GRAPH_KEYS - set(document))
    if missing:
        violations.append(f"graph store omits required envelope keys: {', '.join(missing)}")
    if unknown:
        # 未知 key の混入は「正規 writer は書かない形」であり、store を経由した迂回書込みの
        # 直接の痕跡になる。exact-set で落とす (superset を許すと痕跡が消える)。
        violations.append(f"graph store carries unknown envelope keys: {', '.join(unknown)}")
    if "schema_version" in document and document["schema_version"] != SCHEMA_VERSION:
        violations.append(f"schema_version must be {SCHEMA_VERSION}")
    if "repository_id" in document:
        value = document["repository_id"]
        if not isinstance(value, str) or not value:
            violations.append("repository_id must be a non-empty string")
        elif repository_id is not None and value != repository_id:
            violations.append("repository_id must match repo config")
    if "graph_revision" in document:
        revision = document["graph_revision"]
        if not isinstance(revision, int) or isinstance(revision, bool) or revision < 0:
            violations.append("graph_revision must be a non-negative integer")
    if "nodes" in document:
        nodes = document["nodes"]
        if not isinstance(nodes, list) or not all(isinstance(node, dict) for node in nodes):
            violations.append("nodes must be an array of objects")
    return violations
