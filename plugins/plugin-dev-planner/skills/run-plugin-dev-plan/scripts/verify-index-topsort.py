#!/usr/bin/env python3
# /// script
# name: verify-index-topsort
# purpose: 生成 plan の index(main) が §9 基盤層+全体制御 section 床(specfm.INDEX_REQUIRED_SECTIONS=基本定義/ドメイン知識/インフラ/環境ポリシー/フェーズ一覧/完了チェックリスト/受入確認)を満たし、13 フェーズ(P01..P13)を phase_number 昇順で全列挙し、かつ component-inventory.json の component 依存 DAG が非循環(top-sort 可能)であることを検証する三層決定論ゲート。
# inputs:
#   - argv: <plan-dir> [--index NAME] [--inventory PATH]
# outputs:
#   - stdout: OK サマリ
#   - stderr: phase 列挙漏れ / 昇順違反 / 重複 / DAG 循環 violation
#   - exit: 0=OK / 1=violation / 2=usage error
# contexts: [C, E]
# network: false
# write-scope: none
# dependencies: []
# requires-python: ">=3.10"
# ///
"""index.md(main) の宣言型 section 床・phase 完全性・component 依存 DAG の非循環を三層で機械検証する。

per-phase 転換 (凍結契約 §3/§4/§8/§9/§13-C4):
  - 層0 (index section 床): index が specfm.INDEX_REQUIRED_SECTIONS の各見出し + 非空本文を備える
    (基盤層 = 基本定義/ドメイン知識/インフラ/環境ポリシー + 全体制御 = フェーズ一覧/完了チェック
    リスト/受入確認)。計画全体の宣言型コンテキスト (elegant-review 7 層の Layer1-4) を毎回再現性で焼く。
  - 層1 (phase 完全性): index の `## フェーズ一覧` が P01..P13 を **phase_number 昇順** で
    全 13 列挙する (漏れ 0 / 重複 0 / 昇順)。id 体系は specfm.PHASE_ID_RE。
  - 層2 (component DAG): component-inventory.json の components[] の `depends_on` 有向グラフが
    非循環 (top-sort 可能) で、各 depends_on が実在 component を指す。

旧 per-component (C*.md) の spec-id top-sort 突合は廃止 (phase 軸へ全面転換)。
yaml は import しない (scripts 規約)。inventory は JSON。
"""
from __future__ import annotations

import argparse
import json
import re
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import specfm  # noqa: E402

# 行内から phase id (P01..P13) を拾う探索用パターン (specfm.PHASE_ID_RE は full-match ゆえ別途定義)。
PHASE_TOKEN_RE = re.compile(r"\bP(?:0[1-9]|1[0-3])\b")
_PHASE_LIST_HEADING = "フェーズ一覧"


def body_after_frontmatter(text: str) -> str:
    """先頭 --- frontmatter を除いた本文を返す (frontmatter 内 id を拾わない)。"""
    if text.startswith("---"):
        parts = text.split("---", 2)
        if len(parts) >= 3:
            return parts[2]
    return text


def expected_phase_ids() -> list[str]:
    """canonical な P01..P13 (phase_number 昇順) を返す。"""
    return [specfm.phase_id(n) for n in range(1, 14)]


def index_section_floor_errors(index_body: str) -> list[str]:
    """index が specfm.INDEX_REQUIRED_SECTIONS の各見出し + 非空本文を備えるか検査する (層0 床)。

    基盤層 (基本定義/ドメイン知識/インフラ/環境ポリシー) + 全体制御 (フェーズ一覧/完了チェック
    リスト/受入確認) を計画全体の宣言型コンテキストとして毎回再現性で強制する。見出し欠落と空本文の
    双方を弾く。本文収集は次の `## ` (level-2) 見出しまでで、`### ` サブ見出しは本文とみなす
    (detect-unassigned.empty_body_sections と同一挙動)。意味の正否は下流トラスト (床のみ機械強制)。
    """
    lines = index_body.splitlines()
    errors: list[str] = []
    for sec in specfm.INDEX_REQUIRED_SECTIONS:
        if sec not in index_body:
            errors.append(f"index に必須 section 欠落 '{sec}' (基盤層+全体制御を宣言的に備えること・§9)")
            continue
        idx = next(
            (i for i, ln in enumerate(lines)
             if ln.strip() == sec or ln.strip().startswith(sec + " ")),
            None,
        )
        if idx is None:
            continue  # 見出しは substring で在るがブロック見出しとして独立行に無い→床の対象外
        body: list[str] = []
        for ln in lines[idx + 1:]:
            if ln.startswith("## "):
                break
            body.append(ln)
        if not "".join(body).strip():
            errors.append(f"index の必須 section '{sec}' の本文が空 (見出し直後に非空本文を要求・§9 index 床)")
    return errors


def extract_phase_list_ids(index_body: str) -> tuple[list[str], bool]:
    """index 本文の `## フェーズ一覧` section 内から phase id を出現順に集める。

    section 見出しから次の `## ` 見出し(または EOF)までの各行の最初の phase-id を拾う。
    prose の他 section が phase id を言及しても拾わないよう section を限定する。
    戻り値 = (出現順 id 列, section が見つかったか)。
    """
    ids: list[str] = []
    in_section = False
    found = False
    for line in index_body.splitlines():
        if line.startswith("## "):
            in_section = _PHASE_LIST_HEADING in line
            found = found or in_section
            continue
        if in_section:
            m = PHASE_TOKEN_RE.search(line)
            if m:
                ids.append(m.group(0))
    return ids, found


def verify_phase_enumeration(ordered: list[str], has_section: bool) -> list[str]:
    """index の phase 列挙が P01..P13 を昇順で全列挙するか検査する。"""
    errors: list[str] = []
    if not has_section:
        errors.append(f"index に `## {_PHASE_LIST_HEADING}` section が無い (P01..P13 を昇順列挙すること)")
        return errors
    seen: set[str] = set()
    for pid in ordered:
        if pid in seen:
            errors.append(f"index フェーズ一覧に id 重複: {pid}")
        seen.add(pid)
    expected = expected_phase_ids()
    missing = [p for p in expected if p not in seen]
    if missing:
        errors.append(f"index フェーズ一覧に未列挙の phase: {missing} (13 フェーズ P01..P13 を全列挙すること)")
    extra = [p for p in ordered if p not in expected]
    if extra:
        errors.append(f"index フェーズ一覧に想定外の phase id: {sorted(set(extra))} (P01..P13 のみ許容)")
    # 昇順: 重複/余分を除いた出現順が expected と一致するか。
    dedup_ordered = list(dict.fromkeys(ordered))
    canonical_seq = [p for p in dedup_ordered if p in expected]
    if canonical_seq != expected and not missing and not extra:
        errors.append(
            f"index フェーズ一覧が phase_number 昇順でない: 出現順={canonical_seq} 期待={expected}"
        )
    return errors


def _shape_marker(index_frontmatter: dict) -> str:
    """index frontmatter の shape_marker を返す (C10)。

    既定 fixed-13-phase。未知値も fixed-13-phase へ fallback する fail-soft 設計 (本 plan 自身を
    含む既存の全 plan はこの既定値に該当し従来の 13 ファイル固定検証ロジックを不変維持する)。
    """
    v = index_frontmatter.get("shape_marker") if isinstance(index_frontmatter, dict) else None
    if isinstance(v, str) and v in specfm.SHAPE_MARKERS:
        return v
    return "fixed-13-phase"


def _verify_task_graph_derived(plan_dir: Path, ordered: list[str], has_section: bool) -> list[str]:
    """task-graph-derived shape: 期待 phase 集合を task-graph.json の phase_ref unique から動的算出する。

    将来の task-graph 駆動可変構成 plan 向け分岐 (本 plan 自身=fixed-13-phase では発火しない)。
    task-graph.json 不在時・JSON 不正時は 13 固定検証へ fail-soft fallback する
    (C14 非劣化ゲート PASS を採用前提とする C10⇔C14 相互参照は shape_marker 採否の側で担保する)。
    """
    tg_path = plan_dir / "task-graph.json"
    if not tg_path.is_file():
        return verify_phase_enumeration(ordered, has_section)
    try:
        graph = json.loads(tg_path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return verify_phase_enumeration(ordered, has_section)
    expected = sorted({
        n.get("phase_ref")
        for n in graph.get("nodes", [])
        if isinstance(n, dict) and isinstance(n.get("phase_ref"), str)
    })
    errors: list[str] = []
    if not has_section:
        errors.append("index にフェーズ一覧 section が無い (task-graph-derived)")
    seen = set(ordered)
    missing = [p for p in expected if p not in seen]
    if missing:
        errors.append(f"index フェーズ一覧に task-graph 由来 phase が欠落: {missing}")
    return errors


def load_components(inventory_path: Path) -> tuple[list[dict], str | None]:
    """component-inventory.json の components[] を返す (エラー時 (_, message))。"""
    try:
        data = json.loads(inventory_path.read_text(encoding="utf-8"))
    except json.JSONDecodeError as exc:
        return [], f"component-inventory JSON parse error: {exc}"
    if not isinstance(data, dict) or not isinstance(data.get("components"), list):
        return [], "component-inventory.json に components[] list が無い"
    return [c for c in data["components"] if isinstance(c, dict)], None


def detect_cycle(nodes: set[str], edges: list[tuple[str, str]]) -> list[str] | None:
    """dep->node の有向グラフから循環経路を 1 つ返す (無ければ None)。"""
    adj: dict[str, list[str]] = {n: [] for n in nodes}
    for dep, node in edges:
        adj.setdefault(dep, []).append(node)
        adj.setdefault(node, adj.get(node, []))
    WHITE, GRAY, BLACK = 0, 1, 2
    color = {n: WHITE for n in adj}
    stack: list[str] = []

    def dfs(u: str) -> list[str] | None:
        color[u] = GRAY
        stack.append(u)
        for v in adj.get(u, []):
            if color[v] == GRAY:
                return stack[stack.index(v):] + [v]
            if color[v] == WHITE:
                r = dfs(v)
                if r:
                    return r
        stack.pop()
        color[u] = BLACK
        return None

    for n in sorted(adj):
        if color[n] == WHITE:
            r = dfs(n)
            if r:
                return r
    return None


def verify_component_dag(components: list[dict]) -> list[str]:
    """components[] の depends_on 有向グラフが非循環で、各依存が実在 component を指すか検査する。"""
    errors: list[str] = []
    ids = {str(c.get("id", "")).strip() for c in components if str(c.get("id", "")).strip()}
    edges: list[tuple[str, str]] = []
    for c in components:
        node = str(c.get("id", "")).strip()
        if not node:
            continue
        raw = c.get("depends_on", [])
        deps = raw if isinstance(raw, list) else []
        for dep in deps:
            dep = str(dep).strip()
            if not dep:
                continue
            if dep not in ids:
                errors.append(f"component {node} の depends_on={dep!r} に対応する component が無い")
                continue
            edges.append((dep, node))
    cyc = detect_cycle(ids, [(d, n) for d, n in edges if d in ids])
    if cyc:
        errors.append(f"component 依存グラフに循環 (top-sort 不能): {' -> '.join(cyc)}")
    return errors


def run(plan_dir: Path, index_name: str, inventory_path: Path | None) -> tuple[int, list[str]]:
    index_path = plan_dir / index_name
    if not index_path.is_file():
        return 2, [f"index が見つからない: {index_path}"]
    if inventory_path is None:
        inventory_path = plan_dir / "component-inventory.json"
    if not inventory_path.is_file():
        return 2, [f"component-inventory.json が見つからない: {inventory_path}"]

    errors: list[str] = []
    index_text = index_path.read_text(encoding="utf-8")
    index_body = body_after_frontmatter(index_text)
    errors.extend(index_section_floor_errors(index_body))  # 層0: 基盤層+全体制御 section 床
    ordered, has_section = extract_phase_list_ids(index_body)
    # C10: shape_marker で phase 完全性の検証経路を分岐する (既定 fixed-13-phase は従来ロジック不変)。
    if _shape_marker(specfm.parse_frontmatter(index_text)) == "task-graph-derived":
        errors.extend(_verify_task_graph_derived(plan_dir, ordered, has_section))
    else:
        errors.extend(verify_phase_enumeration(ordered, has_section))

    components, msg = load_components(inventory_path)
    if msg:
        return 2, [msg]
    errors.extend(verify_component_dag(components))
    return (1 if errors else 0), errors


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description="index の phase 完全性 + component DAG 非循環を二層検証する")
    ap.add_argument("plan_dir", help="plan ディレクトリ")
    ap.add_argument("--index", default="index.md", help="index ファイル名 (既定 index.md)")
    ap.add_argument("--inventory", default=None, help="component-inventory.json (既定 <plan_dir>/component-inventory.json)")
    args = ap.parse_args(argv)

    plan_dir = Path(args.plan_dir)
    if not plan_dir.is_dir():
        sys.stderr.write(f"not a directory: {plan_dir}\n")
        return 2
    inventory_path = Path(args.inventory) if args.inventory else None
    code, msgs = run(plan_dir, args.index, inventory_path)
    if code == 0:
        sys.stdout.write("OK: index が §9 section 床を満たし P01..P13 を昇順全列挙し component 依存 DAG が非循環\n")
        return 0
    for m in msgs:
        sys.stderr.write(m + "\n")
    return code


if __name__ == "__main__":
    raise SystemExit(main())
