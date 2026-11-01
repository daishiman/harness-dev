"""bd-bridge が読む「graph 側の正本」— canonical graph・parity manifest・spec markdown (import 専用 module)。

bridge の判定は Beads の状態だけでは決まらない。manifest の由来が新鮮か、orphan の
spec 実体がどこに在るか、削除前後の graph で何が消えるか、という graph 側の事実が要る。
その **read-only な解決経路** をここへ集める。

bd へは一切触らない。git を使う関数 (``refs_with_node`` / ``graph_ids_from_source``) は
実行関数を ``git=`` で受け取る。呼び出し側 (scripts/bd-bridge.py) が module 変数を
渡す形にすることで、test の monkeypatch が従来どおり効く。

正本契約: references/execution-tracker-contract.md
"""
from __future__ import annotations

import sys

sys.dont_write_bytecode = True

import json
from pathlib import Path
from typing import Any, Callable

SCRIPTS = Path(__file__).resolve().parents[1] / "scripts"
if str(SCRIPTS) not in sys.path:
    sys.path.insert(0, str(SCRIPTS))

from _common import ContractError, contained, load_json

from bd_bridge_contracts import FRONTMATTER_NODE_ID, RFC3339_UTC, SHA256


def load_manifest(path: str | None, root: Path, *, label: str) -> dict[str, Any] | None:
    if not path:
        return None
    candidate = Path(path)
    candidate = candidate if candidate.is_absolute() else root / candidate
    try:
        candidate = candidate.resolve(strict=True)
        candidate.relative_to(root)
        value = json.loads(candidate.read_text(encoding="utf-8"))
    except (OSError, ValueError, json.JSONDecodeError) as exc:
        raise ContractError(f"invalid {label} manifest: {exc}") from exc
    if not isinstance(value, dict):
        raise ContractError(f"{label} manifest must be an object")
    return value


def canonical_graph_path(root: Path) -> Path:
    """canonical graph の実体 path を `.dev-graph/config.json` から解決する。

    path を引数で受け取らないのは、bridge が「どの graph を正本とみなすか」を呼び出し側の
    裁量にすると、orphan 棚卸しや削除前検査を空の graph へ向けて素通しできてしまうため。
    解決経路は build-parity-manifest.py `_graph_path` と同一で、repository config が
    単一の正本を決める。
    """
    config = load_json(root / ".dev-graph" / "config.json")
    raw = (config.get("local_state") or {}).get("graph") if isinstance(config, dict) else None
    if not isinstance(raw, str) or not raw:
        raise ContractError("bd-bridge requires config local_state.graph to resolve the canonical graph")
    return contained(root / raw, root, must_exist=True)


def graph_node_ids(root: Path) -> set[str]:
    """canonical graph に実在する graph_node_id の集合を fail-closed で読む。"""
    graph = load_json(canonical_graph_path(root))
    nodes = graph.get("nodes") if isinstance(graph, dict) else None
    if not isinstance(nodes, list) or not all(isinstance(node, dict) for node in nodes):
        raise ContractError("canonical graph must contain nodes[] objects")
    ids: set[str] = set()
    for node in nodes:
        node_id = node.get("graph_node_id") or node.get("id")
        if not isinstance(node_id, str) or not node_id:
            raise ContractError("canonical graph node is missing graph_node_id")
        ids.add(node_id)
    return ids


def manifest_provenance(manifest: dict[str, Any]) -> dict[str, Any]:
    """parity manifest の由来 (生成時刻・source graph digest) を必須検証する。

    manifest は graph の snapshot にすぎない。いつ・どの graph から作ったかを持たないと、
    古い snapshot が「parity confirmed」を主張しても下流 (C16 schedule) が stale を
    機械判定できず、消えた/増えた node を黙って無視した ready-set が出る。
    由来欠落は fail-closed で落とし、素性のない snapshot を流通させない。
    """
    generated_at = manifest.get("generated_at")
    if not isinstance(generated_at, str) or RFC3339_UTC.fullmatch(generated_at) is None:
        raise ContractError("parity manifest requires generated_at as RFC3339 UTC (YYYY-MM-DDThh:mm:ssZ)")
    source_graph_digest = manifest.get("source_graph_digest")
    if not isinstance(source_graph_digest, str) or SHA256.fullmatch(source_graph_digest) is None:
        raise ContractError("parity manifest requires source_graph_digest=sha256:<64 lowercase hex>")
    return {"generated_at": generated_at, "source_graph_digest": source_graph_digest}


def manifest_graph_node_ids(manifest: dict[str, Any]) -> set[str]:
    """manifest が申告する「graph に実在する node id の全集合」を fail-closed で読む。

    `nodes[]` (beads 束縛済みの投影) だけでは、候補が manifest に載らない理由が
    「graph から node が消えた」のか「graph には居るが投影から漏れた」のか判別できない。
    前者は C02 (node 復元 / bd close)、後者は C03 sync と対処 owner が異なる。

    欠落を許容して従来の 1 つの札へ丸めると、GC 削除の残置が sync 案件を装って常駐し、
    「sync しても消えない警告」が常態化して本物の取りこぼしを覆い隠す。manifest は
    build-parity-manifest.py の単一経路が毎回作り直す揮発 snapshot なので、
    欠落時の正しい回復は再生成であって黙認ではない。
    """
    raw = manifest.get("graph_node_ids")
    if not isinstance(raw, list) or any(not isinstance(value, str) or not value for value in raw):
        raise ContractError(
            "parity manifest requires graph_node_ids as string[]; "
            "regenerate it with build-parity-manifest.py"
        )
    return set(raw)


def spec_index(root: Path) -> dict[str, list[str]]:
    """content_roots 配下の markdown が宣言する graph_node_id → 相対 path[] の索引。

    走査範囲を repository config の `content_roots` に限るのは、範囲を固定しないと
    「どこまで探したか」が実行環境で変わり、`disposition` が再現しない診断になるため。
    同じ id を複数ファイルが宣言する多重登録も落とさず全件返す (件数 1 を仮定して
    片方を捨てると、graph 側の整合破れを audit が隠すことになる)。
    """
    config = load_json(root / ".dev-graph" / "config.json")
    roots = config.get("content_roots") if isinstance(config, dict) else None
    if not isinstance(roots, dict) or not roots:
        raise ContractError("bd-bridge requires config content_roots to locate artifact specs")
    index: dict[str, list[str]] = {}
    for relative in sorted({value for value in roots.values() if isinstance(value, str) and value}):
        base = root / relative
        if not base.is_dir():
            continue
        for path in sorted(base.rglob("*.md")):
            try:
                head = path.read_text(encoding="utf-8")[:8192]
            except OSError:
                continue
            if not head.startswith("---"):
                continue
            frontmatter = head[3:].split("\n---", 1)[0]
            match = FRONTMATTER_NODE_ID.search(frontmatter)
            if match:
                index.setdefault(match.group(1), []).append(path.relative_to(root).as_posix())
    return index


def refs_with_node(root: Path, node_ids: set[str], *, git: Callable[..., str]) -> dict[str, list[str]]:
    """他 ref の canonical graph に実在する node_id → その ref[] を返す。

    作業ツリーだけを見ると、未マージブランチで登録された node が「どこにも無い」に
    見える。その誤判定のまま失効扱いすると、参照が正しい生きた課題を消す。dangling か
    マージ待ちかは **同じ「node が無い」** に見えるため、ref 横断でしか区別できない。

    ref ごとに graph を 1 回だけ読む (node_id ごとに git を叩くと ref 数 × node 数の
    実行になる)。読めない ref は「その ref には無い」として黙って飛ばす — graph を持たない
    古い ref や壊れた ref で audit 全体を落とすと、棚卸しそのものが実行不能になるため。
    """
    if not node_ids:
        return {}
    graph_relative = canonical_graph_path(root).relative_to(root.resolve()).as_posix()
    refs = git(["for-each-ref", "--format=%(refname)", "refs/heads", "refs/remotes"], root).split()
    found: dict[str, list[str]] = {}
    for ref in refs:
        blob = git(["show", f"{ref}:{graph_relative}"], root, check=False)
        if not blob:
            continue
        try:
            nodes = json.loads(blob).get("nodes")
        except (json.JSONDecodeError, AttributeError):
            continue
        if not isinstance(nodes, list):
            continue
        present = {
            node.get("graph_node_id") or node.get("id")
            for node in nodes if isinstance(node, dict)
        }
        for node_id in sorted(node_ids & present):
            found.setdefault(node_id, []).append(ref)
    return found


def graph_ids_from_document(value: Any, *, label: str) -> set[str]:
    """removal preflight 用に graph_node_id exact-set を fail-closed で読む。"""
    nodes = value.get("nodes") if isinstance(value, dict) else None
    if not isinstance(nodes, list) or not all(isinstance(node, dict) for node in nodes):
        raise ContractError(f"{label} graph must contain nodes[] objects")
    ids: list[str] = []
    for node in nodes:
        node_id = node.get("graph_node_id") or node.get("id")
        if not isinstance(node_id, str) or not node_id:
            raise ContractError(f"{label} graph node is missing graph_node_id")
        ids.append(node_id)
    if len(ids) != len(set(ids)):
        raise ContractError(f"{label} graph contains duplicate graph_node_id")
    return set(ids)


def graph_ids_from_source(
    root: Path,
    *,
    git: Callable[..., str],
    path: str | None,
    ref: str | None,
    label: str,
    default_current: bool = False,
) -> set[str]:
    """repository 内 path または git ref の graph を読む。両方指定は拒否する。"""
    if path and ref:
        raise ContractError(f"{label} graph accepts path or ref, not both")
    if ref:
        graph_relative = canonical_graph_path(root).relative_to(root).as_posix()
        raw = git(["show", f"{ref}:{graph_relative}"], root, check=False)
        if not raw:
            raise ContractError(f"{label} graph is unavailable at ref: {ref}")
        try:
            value = json.loads(raw)
        except json.JSONDecodeError as exc:
            raise ContractError(f"{label} graph at ref is invalid JSON: {ref}") from exc
        return graph_ids_from_document(value, label=label)
    if not path and default_current:
        candidate = canonical_graph_path(root)
    elif path:
        candidate = Path(path)
        candidate = candidate if candidate.is_absolute() else root / candidate
        candidate = contained(candidate, root, must_exist=True)
    else:
        raise ContractError(f"{label} graph requires --{label}-graph or --{label}-ref")
    return graph_ids_from_document(load_json(candidate), label=label)
