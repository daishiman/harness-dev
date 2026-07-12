#!/usr/bin/env python3
# /// script
# name: extract-capability-dependency-graph
# purpose: 生成された harness 内の skill / slash-command / sub-agent / hook / script surface を走査し、frontmatter refs・明示参照から capability 依存グラフを決定論的に抽出する。checklist item depends_on だけでなく cross-surface の『どの capability がどの capability/asset を使うか』を knowledge 化できる入力にする (H6 の横断依存 graph 抽出物)。
# inputs:
#   - argv: <plugin_root_or_generated_harness_dir> (生成先 harness の skills/ commands/ agents/ hooks/ scripts/ を read-only 走査)
# outputs:
#   - stdout: {"nodes":[{id,kind,path}],"edges":[{from,to,type,source_ref}],"gaps":[...]} JSON (node/edge は id 昇順で正準化)
#   - stderr: fail-closed 診断 (空 graph / 循環 / 未知参照)
#   - exit: 0=OK / 1=fail-closed (空 graph・循環・未知参照) / 2=usage/IO error
# contexts: [C, E]
# network: false
# write-scope: none
# dependencies: []
# requires-python: ">=3.10"
# ///
"""生成 harness の cross-surface 依存グラフを決定論抽出する (C06)。

with-goal-seek の engine:task-graph 変種が、生成済み harness の surface 間依存を knowledge 化
するための入力を作る。checklist の実行順序状態 (progress.json = 唯一の truth) とは別レイヤの
**派生情報** (どの surface がどの capability/asset に依存するか) であり、別状態ファイルを
新設しない (H6・単一truth原則と非矛盾)。

node = 第一級 surface (skill/command/agent/hook/script)。id は `<kind>:<name>` で衝突回避。
edge = ある surface 定義内から別の**発見済み** surface を参照する明示リンク。
gaps = 第一級 surface の呼出形 (Skill(x)/Agent(x)/scripts/x.py 等) だが x が未発見 & builtin
        allowlist 外の参照 (dangling)。

fail-closed (exit1): node 空 / edge 循環 / gaps 非空 (常に最も厳格な依存整合検査)。
JSON は失敗時も stdout へ出す (C07/C08 が graph+gaps を読めるようにするため)。

Exit 0 = OK, 1 = fail-closed, 2 = usage/IO error。
"""
from __future__ import annotations

import argparse
import json
import re
import sys
from pathlib import Path

# builtin (第一党でない) 参照先。gap 誤検出を避けるため edge/gap どちらにもしない。
BUILTIN_AGENTS = frozenset({"general-purpose", "explore", "plan", "claude", "statusline-setup"})

_SKILL_INVOKE_RE = re.compile(r"Skill\(\s*([a-z0-9][a-z0-9-]*)\s*\)")
_AGENT_INVOKE_RE = re.compile(r"Agent\(\s*([a-z0-9][a-z0-9-]*)\s*\)")
_FM_PAIR_RE = re.compile(r"^\s*pair:\s*([a-z0-9][a-z0-9-]*)\s*$", re.MULTILINE)
_FM_AGENT_RE = re.compile(r"^\s*(?:agent|subagent_type):\s*([a-z0-9][a-z0-9-]*)\s*$", re.MULTILINE)
_SCRIPT_REF_RE = re.compile(r"scripts/([A-Za-z0-9_][A-Za-z0-9_.-]*\.py)")
_FM_NAME_RE = re.compile(r"^\s*name:\s*([A-Za-z0-9][A-Za-z0-9_-]*)\s*$", re.MULTILINE)

_ID_NUM_TAIL_RE = re.compile(r"(\d+)$")


def _read(path: Path) -> str:
    try:
        return path.read_text(encoding="utf-8")
    except OSError:
        return ""


def _surface_name(path: Path, text: str, fallback: str) -> str:
    m = _FM_NAME_RE.search(text)
    return m.group(1) if m else fallback


def discover_nodes(root: Path) -> list[dict]:
    """skills/commands/agents/hooks/scripts を走査し node 一覧を返す (path でソート)。"""
    nodes: list[dict] = []

    for skill_md in sorted(root.glob("skills/*/SKILL.md")):
        text = _read(skill_md)
        name = _surface_name(skill_md, text, skill_md.parent.name)
        nodes.append({"id": f"skill:{name}", "kind": "skill", "path": str(skill_md.relative_to(root))})

    for cmd in sorted(root.glob("commands/*.md")):
        text = _read(cmd)
        name = _surface_name(cmd, text, cmd.stem)
        nodes.append({"id": f"command:{name}", "kind": "command", "path": str(cmd.relative_to(root))})

    for agent in sorted(root.glob("agents/*.md")):
        text = _read(agent)
        name = _surface_name(agent, text, agent.stem)
        nodes.append({"id": f"agent:{name}", "kind": "agent", "path": str(agent.relative_to(root))})

    for hook in sorted(root.glob("hooks/*")):
        if hook.is_file():
            nodes.append({"id": f"hook:{hook.name}", "kind": "hook", "path": str(hook.relative_to(root))})

    # scripts は plugin-root と各 skill 配下の両方を対象 (id は basename で衝突回避)。
    for script in sorted(set(root.glob("scripts/*.py")) | set(root.glob("skills/*/scripts/*.py"))):
        nodes.append({"id": f"script:{script.name}", "kind": "script", "path": str(script.relative_to(root))})

    # id 昇順で正準化 (kind, name の辞書順)。
    nodes.sort(key=lambda n: n["id"])
    return nodes


def _resolve(kind: str, name: str, node_ids: set[str]) -> str | None:
    cand = f"{kind}:{name}"
    return cand if cand in node_ids else None


def extract_edges(root: Path, nodes: list[dict]) -> tuple[list[dict], list[dict]]:
    """各 node 定義から発見済み surface への edge を抽出し、未解決を gaps に分離する。"""
    node_ids = {n["id"] for n in nodes}
    edges: list[dict] = []
    gaps: list[dict] = []
    seen_edges: set[tuple[str, str, str]] = set()

    def add(src: str, kind: str, name: str, etype: str, ref: str) -> None:
        if kind == "agent" and name in BUILTIN_AGENTS:
            return
        target = _resolve(kind, name, node_ids)
        if target is None:
            gap_key = (src, f"{kind}:{name}", etype)
            if gap_key not in seen_edges:
                seen_edges.add(gap_key)
                gaps.append({"from": src, "ref": f"{kind}:{name}", "type": etype, "source_ref": ref})
            return
        key = (src, target, etype)
        if key not in seen_edges:
            seen_edges.add(key)
            edges.append({"from": src, "to": target, "type": etype, "source_ref": ref})

    for node in nodes:
        path = root / node["path"]
        text = _read(path)
        src = node["id"]
        ref = node["path"]
        for m in _SKILL_INVOKE_RE.finditer(text):
            add(src, "skill", m.group(1), "skill-invoke", ref)
        for m in _AGENT_INVOKE_RE.finditer(text):
            add(src, "agent", m.group(1), "agent-invoke", ref)
        for m in _FM_PAIR_RE.finditer(text):
            add(src, "skill", m.group(1), "pair", ref)
        for m in _FM_AGENT_RE.finditer(text):
            add(src, "agent", m.group(1), "agent-bind", ref)
        for m in _SCRIPT_REF_RE.finditer(text):
            add(src, "script", m.group(1), "script-call", ref)

    edges.sort(key=lambda e: (e["from"], e["to"], e["type"]))
    gaps.sort(key=lambda g: (g["from"], g["ref"], g["type"]))
    return edges, gaps


def find_cycle(nodes: list[dict], edges: list[dict]) -> list[str] | None:
    """edge (from->to) の依存グラフに循環があれば 1 例のパスを返す (反復 DFS)。

    明示スタックの 3-color DFS + path 追跡で、数百 surface の深い直鎖でも Python 再帰上限に
    触れない (再帰実装は深鎖で RecursionError=crash になり fail-closed でないため反復化する)。
    """
    adjacency: dict[str, list[str]] = {n["id"]: [] for n in nodes}
    for e in edges:
        adjacency.setdefault(e["from"], []).append(e["to"])
    WHITE, GRAY, BLACK = 0, 1, 2
    color = {node: WHITE for node in adjacency}

    for start in adjacency:
        if color[start] != WHITE:
            continue
        color[start] = GRAY
        stack: list[tuple[str, object]] = [(start, iter(adjacency.get(start, [])))]
        path: list[str] = [start]
        while stack:
            node, it = stack[-1]
            nxt = None
            for cand in it:  # type: ignore[assignment]
                if cand not in color or color[cand] == BLACK:
                    continue
                nxt = cand
                break
            if nxt is None:
                color[node] = BLACK
                stack.pop()
                path.pop()
            elif color[nxt] == GRAY:
                return path[path.index(nxt):] + [nxt]
            else:  # WHITE
                color[nxt] = GRAY
                stack.append((nxt, iter(adjacency.get(nxt, []))))
                path.append(nxt)
    return None


def build_graph(root: Path) -> tuple[dict, list[str]]:
    """(graph, findings) を返す。findings 非空 = fail-closed 条件成立。"""
    nodes = discover_nodes(root)
    edges, gaps = extract_edges(root, nodes)
    graph = {"nodes": nodes, "edges": edges, "gaps": gaps}
    findings: list[str] = []
    if not nodes:
        findings.append("空 graph: surface node が 1 件も発見されない (走査対象が harness ディレクトリか確認)")
    cycle = find_cycle(nodes, edges)
    if cycle:
        findings.append("循環依存: " + " -> ".join(cycle))
    if gaps:
        findings.append(
            f"未知参照 (dangling) {len(gaps)} 件: "
            + ", ".join(f"{g['from']}→{g['ref']}" for g in gaps[:5])
            + (" ..." if len(gaps) > 5 else "")
        )
    return graph, findings


def main(argv: list[str]) -> int:
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("harness_dir", help="生成先 harness ディレクトリ (plugin root 相当)")
    try:
        args = p.parse_args(argv)
    except SystemExit as exc:
        return int(exc.code) if isinstance(exc.code, int) else 2

    root = Path(args.harness_dir)
    if not root.is_dir():
        sys.stderr.write(f"harness ディレクトリが存在しない: {root}\n")
        return 2

    graph, findings = build_graph(root)
    # JSON は失敗時も stdout へ (C07/C08 が graph+gaps を読めるように)。
    sys.stdout.write(json.dumps(graph, ensure_ascii=False, indent=2) + "\n")
    if findings:
        for f in findings:
            sys.stderr.write(f"fail-closed: {f}\n")
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
