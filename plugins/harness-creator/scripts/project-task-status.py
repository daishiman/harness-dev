#!/usr/bin/env python3
# /// script
# name: project-task-status
# purpose: task-graph 駆動 build の live 実行状態を plan dir へ read-only 投影する観測ビュー生成器 (TG-C09)。task-graph.json (構造・単一 writer=derive・plugin-plans/ 追跡) は runtime state を焼かず ephemeral な task-state.json (eval-log/ build dir) が真の状態を持つため、両者を merge した派生ビュー (task-graph-status.json + 人間可読 task-progress.md + 構造化 task-execution-report.html) を plan dir へ書き出し「plugin-plans を見ても status が変わらない」観測性断絶を解消する。task-graph.json/task-state.json は一切書かず単一 writer 不変条件と graph_hash pin を温存する (state を task-graph.json へ焼くと hash が毎遷移で変わり pin が壊れるため投影で解決)。discovered-task inbox を読めば未処理の追加タスク (外ループ待ち) も同一ビューに載る。
# inputs:
#   - argv: --task-graph <task-graph.json> --task-state <task-state.json> [--out-json P] [--out-md P] [--out-html P] [--build-summary P] [--discovered-inbox DIR]
#           (出力先省略時は task-graph.json の親 dir。build-summary は task-state と同じ dir の build-summary.json を自動検出)
# outputs:
#   - stdout: 生成先パス + 進捗サマリ JSON
#   - stderr: 読込/parse/write エラー
#   - exit: 0=OK / 2=usage/IO error
#   - write-scope: <plan_dir>/task-graph-status.json + <plan_dir>/task-progress.md + <plan_dir>/task-execution-report.html (派生ビューのみ・task-graph.json/task-state.json は不変)
# contexts: [C, E]
# network: false
# write-scope: <plan_dir>/task-graph-status.json + <plan_dir>/task-progress.md + <plan_dir>/task-execution-report.html
# dependencies: []
# requires-python: ">=3.10"
# ///
"""live 実行状態の plan dir 投影器 (TG-C09・観測性断絶の解消)。

「plugin-plans/<slug>/task-graph.json を見ても status が変わらない」問題の解消。task-graph.json は
構造 SSOT (単一 writer=derive-task-graph・plugin-plans/ 追跡) であり runtime state を焼かない。
真の状態は build 毎に使い捨ての task-state.json (eval-log/<slug>/build dir・gitignore) にあるため、
両者を merge した派生ビューを plan dir へ書き出して可視化する:
  - task-graph.json/task-state.json は read-only (単一 writer 不変条件・graph_hash pin を温存)。
    state を task-graph.json へ焼くと canonical hash が毎遷移で変わり pin (F10) が壊れるため、
    上書きでなく投影で解く。
  - dispatch-ready-set.merge_state (task-state を task-graph へ overlay) と
    summarize-task-progress.summarize (by_state/completion_rate 集計) を sibling import で再利用し
    SSOT を二重実装しない。
  - discovered-task inbox を渡せば未処理 (外ループ待ち) の追加タスクも同一ビューに載る
    (「新しいタスクを追加した」対応が plan dir で見える)。

出力は 3 ファイル: task-graph-status.json (機械可読・overlay 済 node + summary + discovered)、
task-progress.md (差分確認向け・phase グループの ✓/▶/✗/☐ チェックリスト)、
task-execution-report.html (閲覧向け・自己完結の図解/route 証跡/原本リンク)。いずれも派生ビューゆえ
手書き編集しない (再生成で上書き)。
"""
from __future__ import annotations

import argparse
import importlib.util
import json
import os
import sys
from html import escape
from pathlib import Path

_STATE_ICON = {"done": "✓", "running": "▶", "blocked": "✗", "pending": "☐"}
_TERMINAL_DISCOVERED = {"accepted", "rejected", "superseded"}


def _load_sibling(stem: str):
    """同一 scripts/ 配下のハイフン名 module を importlib で読み込む (TG SSOT 再利用)。"""
    path = Path(__file__).resolve().parent / f"{stem}.py"
    spec = importlib.util.spec_from_file_location(stem.replace("-", "_"), path)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


_dispatch = _load_sibling("dispatch-ready-set")
_summarize = _load_sibling("summarize-task-progress")
merge_state = _dispatch.merge_state
summarize = _summarize.summarize


def _read_json(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))


def _pending_discovered(inbox: Path) -> list[dict]:
    """discovered-task inbox から未処理 (status が terminal でない) の追加タスクを昇順で返す。"""
    if not inbox.is_dir():
        return []
    out: list[dict] = []
    for form_path in sorted(inbox.glob("*.json")):
        try:
            form = _read_json(form_path)
        except (OSError, json.JSONDecodeError):
            continue
        status = form.get("status") or "pending"
        if status in _TERMINAL_DISCOVERED:
            continue
        node = form.get("proposed_node", {}) if isinstance(form.get("proposed_node"), dict) else {}
        out.append({
            "form": form_path.name,
            "proposed_id": node.get("id"),
            "title": node.get("title"),
            "phase_ref": node.get("phase_ref"),
            "change_level": form.get("change_level"),
            "reason": form.get("reason"),
            "status": status,
        })
    return out


def _route_reports(build_dir: Path) -> list[dict]:
    """build dir の route report を人間向け投影へ載せる順で返す。壊れた JSON は無視する。"""
    reports: list[dict] = []
    for report_path in sorted(build_dir.glob("route-*.json")):
        try:
            report = _read_json(report_path)
        except (OSError, json.JSONDecodeError):
            continue
        if not isinstance(report, dict):
            continue
        reports.append({
            "file": report_path.name,
            "route_id": report.get("route_id"),
            "component_kind": report.get("component_kind"),
            "name": report.get("name"),
            "build_target": report.get("build_target"),
            "status": report.get("status"),
            "summary": report.get("summary"),
            "evidence": report.get("evidence") if isinstance(report.get("evidence"), list) else [],
            "deviations": report.get("deviations") if isinstance(report.get("deviations"), list) else [],
            "handover": report.get("handover"),
            "covered_task_ids": (
                report.get("covered_task_ids")
                if isinstance(report.get("covered_task_ids"), list) else []
            ),
        })
    return reports


def _optional_build_summary(path: Path | None) -> dict | None:
    if path is None or not path.is_file():
        return None
    try:
        value = _read_json(path)
    except (OSError, json.JSONDecodeError):
        return None
    return value if isinstance(value, dict) else None


def build_status(graph: dict, task_state: dict, build_dir: Path,
                 discovered: list[dict]) -> dict:
    """overlay 済 node + summary + discovered を統合した status ビュー dict を返す (read-only 純関数)。"""
    state_by_id = {n.get("id"): n for n in task_state.get("nodes", []) if isinstance(n, dict)}
    merged = merge_state(graph, state_by_id)
    live_nodes = []
    for n in merged.get("nodes", []):
        if not isinstance(n, dict):
            continue
        st = state_by_id.get(n.get("id"), {})
        entry = {
            "id": n.get("id"),
            "title": n.get("title"),
            "phase_ref": n.get("phase_ref"),
            "entity_ref": n.get("entity_ref"),
            "state": n.get("state", "pending"),
        }
        if st.get("blocked_reason"):
            entry["blocked_reason"] = st.get("blocked_reason")
        if st.get("route_report"):
            entry["route_report"] = st.get("route_report")
        live_nodes.append(entry)
    live_nodes.sort(key=lambda x: str(x.get("id")))
    # summary は **full graph (overlay 済 live_nodes) を母集団**に算出する。task-state.json は
    # build 中 sparse (遷移発生 node のみ on-demand 追加) ゆえ summarize(task_state) の分母を使うと、
    # 未着手 node が分母から欠け「done 1件のみ→完了率100%」と過大表示され、直下の全 graph
    # チェックリスト (未着手=pending 計上) と同一文書で矛盾する。route_report_count のみ
    # summarize (build_dir の route-*.json 実ファイル数) を read-only 流用する。
    by_state = {k: 0 for k in ("pending", "running", "done", "blocked")}
    for n in live_nodes:
        st = n.get("state")
        if st in by_state:
            by_state[st] += 1
    total = len(live_nodes)
    completion_rate = (by_state["done"] / total) if total else 0.0
    blocked_tasks = [n["id"] for n in live_nodes if n.get("state") == "blocked"]
    route_report_count = summarize(task_state, build_dir)["route_report_count"]
    return {
        "_generated": "project-task-status.py (派生ビュー・手書き編集しない・再生成で上書き)",
        "graph_hash": task_state.get("graph_hash"),
        "summary": {
            "total": total,
            "by_state": by_state,
            "completion_rate": completion_rate,
            "blocked_tasks": blocked_tasks,
            "route_report_count": route_report_count,
        },
        "nodes": live_nodes,
        "discovered_pending": discovered,
    }


def render_markdown(status: dict) -> str:
    """status ビューを人間可読な task-progress.md 文字列へ整形する (phase グループ・状態アイコン)。"""
    s = status["summary"]
    pct = round(s["completion_rate"] * 100)
    lines = [
        "# task-progress (live 実行状態・派生ビュー)",
        "",
        "> `project-task-status.py` 生成の派生ビュー。構造の正本は `task-graph.json`、状態の正本は "
        "build dir の `task-state.json`。手書き編集しない (再生成で上書き)。build 異常終了時は最後の "
        "投影時点のスナップショットで stale の可能性がある (最新は再投影で得る)。",
        "",
        "- 凡例: ✓=done / ▶=running / ✗=blocked / ☐=pending / ⏳=未処理の発見タスク (外ループ待ち)",
        f"- 完了率: **{pct}%** ({s['by_state']['done']}/{s['total']})",
        f"- 状態内訳: done={s['by_state']['done']} / running={s['by_state']['running']} "
        f"/ blocked={s['by_state']['blocked']} / pending={s['by_state']['pending']}",
        f"- route-report 数: {s['route_report_count']}",
    ]
    if status.get("graph_hash"):
        lines.append(f"- graph_hash pin: `{status['graph_hash']}`")
    lines.append("")

    # phase グループの node チェックリスト。
    by_phase: dict[str, list[dict]] = {}
    for n in status["nodes"]:
        by_phase.setdefault(str(n.get("phase_ref")), []).append(n)
    for phase in sorted(by_phase):
        lines.append(f"## {phase}")
        for n in by_phase[phase]:
            icon = _STATE_ICON.get(n.get("state"), "?")
            extra = ""
            if n.get("blocked_reason"):
                extra = f" — blocked_reason={n['blocked_reason']}"
            lines.append(f"- {icon} `{n.get('id')}` {n.get('title', '')}{extra}")
        lines.append("")

    disc = status.get("discovered_pending") or []
    if disc:
        lines.append("## 未処理の発見タスク (外ループ待ち・`--mode update --discovered-inbox` で反映)")
        for d in disc:
            lines.append(
                f"- ⏳ `{d.get('proposed_id')}` {d.get('title', '')} "
                f"[{d.get('change_level')}] — {d.get('reason', '')}"
            )
        lines.append("")
    return "\n".join(lines) + "\n"


def _state_label(summary: dict) -> tuple[str, str]:
    by_state = summary["by_state"]
    if summary["total"] > 0 and by_state["done"] == summary["total"]:
        return "完了", "complete"
    if by_state["blocked"]:
        return "要対応", "blocked"
    if by_state["running"]:
        return "実行中", "running"
    return "待機中", "pending"


def _phase_groups(status: dict) -> list[tuple[str, list[dict]]]:
    grouped: dict[str, list[dict]] = {}
    for node in status.get("nodes", []):
        grouped.setdefault(str(node.get("phase_ref") or "未分類"), []).append(node)
    return [(phase, grouped[phase]) for phase in sorted(grouped)]


def _artifact_href(target: Path, html_path: Path) -> str:
    """自己完結 HTML からローカル証跡へ移動できる相対 href。"""
    relative = os.path.relpath(target.resolve(), start=html_path.parent.resolve())
    return escape(Path(relative).as_posix(), quote=True)


def render_html(
    status: dict,
    graph: dict,
    *,
    html_path: Path,
    graph_path: Path,
    state_path: Path,
    status_json_path: Path,
    progress_md_path: Path,
    build_summary_path: Path | None,
) -> str:
    """同じ status 投影から決定論的な自己完結 HTML 実行記録を生成する。"""
    summary = status["summary"]
    pct = round(summary["completion_rate"] * 100)
    circumference = 2 * 3.141592653589793 * 52
    dash = circumference * summary["completion_rate"]
    verdict, verdict_class = _state_label(summary)
    plan_name = graph_path.parent.name
    phases = _phase_groups(status)

    metric_cards = "".join(
        f'<article class="metric metric--{escape(key)}"><span>{escape(label)}</span>'
        f'<strong>{summary["by_state"][key]}</strong></article>'
        for key, label in (
            ("done", "完了"), ("running", "実行中"),
            ("blocked", "要対応"), ("pending", "未着手"),
        )
    )

    phase_cards: list[str] = []
    task_sections: list[str] = []
    for phase, nodes in phases:
        counts = {key: 0 for key in _STATE_ICON}
        for node in nodes:
            state = str(node.get("state") or "pending")
            if state in counts:
                counts[state] += 1
        done_pct = round((counts["done"] / len(nodes)) * 100) if nodes else 0
        phase_cards.append(
            '<article class="phase-card">'
            f'<div><strong>{escape(phase)}</strong><span>{counts["done"]}/{len(nodes)}</span></div>'
            f'<div class="phase-track" aria-label="{escape(phase)} 完了率 {done_pct}%">'
            f'<span style="width:{done_pct}%"></span></div>'
            f'<small>完了 {counts["done"]}・実行中 {counts["running"]}・'
            f'要対応 {counts["blocked"]}・未着手 {counts["pending"]}</small></article>'
        )
        rows = []
        for node in nodes:
            state = str(node.get("state") or "pending")
            reason = node.get("blocked_reason")
            route = node.get("route_report")
            rows.append(
                '<tr>'
                f'<td><span class="state state--{escape(state)}">{escape(_STATE_ICON.get(state, "?"))} '
                f'{escape(state)}</span></td>'
                f'<td><code>{escape(str(node.get("id") or ""))}</code></td>'
                f'<td>{escape(str(node.get("title") or ""))}</td>'
                f'<td>{escape(str(reason or route or "—"))}</td>'
                '</tr>'
            )
        task_sections.append(
            f'<details class="task-group"><summary><strong>{escape(phase)}</strong>'
            f'<span>{len(nodes)} tasks / {done_pct}%</span></summary>'
            '<div class="table-wrap"><table><thead><tr><th>状態</th><th>ID</th><th>タスク</th>'
            f'<th>実行記録</th></tr></thead><tbody>{"".join(rows)}</tbody></table></div></details>'
        )

    route_cards: list[str] = []
    for route in status.get("route_reports", []):
        evidence = "".join(f"<li>{escape(str(item))}</li>" for item in route["evidence"])
        deviations = "".join(f"<li>{escape(str(item))}</li>" for item in route["deviations"])
        route_file = state_path.parent / str(route["file"])
        route_cards.append(
            '<article class="route-card">'
            f'<header><div><span class="eyebrow">{escape(str(route.get("component_kind") or "route"))}</span>'
            f'<h3>{escape(str(route.get("route_id") or "—"))} · {escape(str(route.get("name") or ""))}</h3></div>'
            f'<span class="route-status route-status--{escape(str(route.get("status") or "unknown"))}">'
            f'{escape(str(route.get("status") or "unknown"))}</span></header>'
            f'<p>{escape(str(route.get("summary") or "概要なし"))}</p>'
            f'<p class="path"><span>出力先</span><code>{escape(str(route.get("build_target") or "—"))}</code></p>'
            '<details><summary>証跡と逸脱を表示</summary>'
            f'<div class="route-detail"><div><h4>Evidence</h4><ul>{evidence or "<li>記録なし</li>"}</ul></div>'
            f'<div><h4>Deviations</h4><ul>{deviations or "<li>なし</li>"}</ul></div></div></details>'
            f'<a class="source-link" href="{_artifact_href(route_file, html_path)}">route report JSON を開く</a>'
            '</article>'
        )

    discovered_cards = "".join(
        '<article class="discovered-card">'
        f'<span>{escape(str(item.get("change_level") or "unknown"))}</span>'
        f'<h3>{escape(str(item.get("proposed_id") or "未採番"))} · {escape(str(item.get("title") or ""))}</h3>'
        f'<p>{escape(str(item.get("reason") or "理由なし"))}</p></article>'
        for item in status.get("discovered_pending", [])
    )

    build_summary = status.get("build_summary") or {}
    gate = build_summary.get("completion_gate") if isinstance(build_summary, dict) else None
    gate_value = gate.get("completion_gate") if isinstance(gate, dict) else None
    rounds = build_summary.get("outer_loop_rounds") if isinstance(build_summary, dict) else None
    round_rows = "".join(
        '<tr>'
        f'<td>{escape(str(item.get("round") or "—"))}</td>'
        f'<td>{escape(str(item.get("origin") or "—"))}</td>'
        f'<td>{escape(str(item.get("result") or "—"))}</td></tr>'
        for item in (rounds if isinstance(rounds, list) else []) if isinstance(item, dict)
    )

    source_links = [
        ("task-graph.json", graph_path),
        ("task-state.json", state_path),
        ("task-graph-status.json", status_json_path),
        ("task-progress.md", progress_md_path),
    ]
    if build_summary_path is not None and build_summary_path.is_file():
        source_links.append(("build-summary.json", build_summary_path))
    sources = "".join(
        f'<a href="{_artifact_href(path, html_path)}"><strong>{escape(label)}</strong>'
        f'<span>{escape(str(path))}</span></a>' for label, path in source_links
    )

    graph_nodes = len(graph.get("nodes", [])) if isinstance(graph.get("nodes"), list) else 0
    graph_edges = len(graph.get("edges", [])) if isinstance(graph.get("edges"), list) else 0
    report_note = (
        "全タスクと完了ゲートが通過しています。"
        if verdict_class == "complete" and gate_value in (None, "ok")
        else "進行中または要対応の項目があります。詳細を確認してください。"
    )

    return f'''<!doctype html>
<html lang="ja">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<meta name="color-scheme" content="light">
<title>{escape(plan_name)} · タスク実行記録</title>
<style>
:root{{--ink:#242330;--muted:#666477;--paper:#f6f3ec;--panel:#fffdf7;--line:#ded8cb;--navy:#26334a;--blue:#376b8c;--aqua:#2f7d70;--green:#27745c;--amber:#a66520;--red:#a33d4b;--violet:#745b92;--shadow:0 18px 48px rgba(45,42,50,.09)}}
*{{box-sizing:border-box}} html{{scroll-behavior:smooth}} body{{margin:0;background:var(--paper);color:var(--ink);font-family:Inter,"Noto Sans JP","Hiragino Sans",system-ui,sans-serif;font-size:17px;line-height:1.75}}
a{{color:var(--blue)}} code{{font-family:"SFMono-Regular",Consolas,monospace;font-size:.88em;overflow-wrap:anywhere}} .shell{{width:min(1180px,calc(100% - 32px));margin:auto}}
.hero{{background:linear-gradient(145deg,#202a3d,#354e68 68%,#3c766d);color:#fdfbf3;padding:56px 0 42px}} .hero-grid{{display:grid;grid-template-columns:minmax(0,1.4fr) minmax(280px,.6fr);gap:44px;align-items:center}}
.eyebrow{{display:block;text-transform:uppercase;letter-spacing:.12em;font-weight:800;font-size:.75rem;opacity:.76}} h1{{font-size:clamp(2rem,5vw,4.1rem);line-height:1.08;margin:.25em 0}} .lead{{font-size:1.1rem;max-width:62ch;color:#e4e7e6}} .verdict{{display:inline-flex;gap:10px;align-items:center;border:1px solid rgba(255,255,255,.28);border-radius:999px;padding:7px 14px;background:rgba(255,255,255,.1);font-weight:800}}
.donut-wrap{{position:relative;width:230px;height:230px;margin:auto}} .donut{{width:100%;height:100%;transform:rotate(-90deg)}} .donut-bg{{fill:none;stroke:rgba(255,255,255,.16);stroke-width:15}} .donut-value{{fill:none;stroke:#e6c86e;stroke-width:15;stroke-linecap:round}} .donut-copy{{position:absolute;inset:0;display:grid;place-content:center;text-align:center}} .donut-copy strong{{font-size:3rem;line-height:1}} .donut-copy span{{opacity:.75}}
.metrics{{display:grid;grid-template-columns:repeat(4,1fr);gap:14px;margin-top:-24px;position:relative}} .metric{{background:var(--panel);border:1px solid var(--line);box-shadow:var(--shadow);border-radius:18px;padding:18px 22px;display:flex;justify-content:space-between;align-items:end;border-top:5px solid var(--blue)}} .metric span{{color:var(--muted);font-size:.9rem}} .metric strong{{font-size:2rem;line-height:1}} .metric--done{{border-top-color:var(--green)}} .metric--running{{border-top-color:var(--blue)}} .metric--blocked{{border-top-color:var(--red)}} .metric--pending{{border-top-color:var(--amber)}}
main{{padding:48px 0 72px}} section{{margin:0 0 56px}} .section-head{{display:flex;justify-content:space-between;align-items:end;gap:20px;margin-bottom:20px}} h2{{font-size:clamp(1.55rem,3vw,2.25rem);line-height:1.25;margin:0}} .section-head p{{max-width:58ch;margin:0;color:var(--muted)}}
.flow-panel,.panel{{background:var(--panel);border:1px solid var(--line);border-radius:22px;padding:24px;box-shadow:var(--shadow)}} .flow-scroll{{overflow-x:auto;overscroll-behavior-inline:contain}} .flow-svg{{display:block;width:100%;min-width:820px;height:auto}} .flow-svg .box{{fill:#f4efe5;stroke:#8a8275;stroke-width:1.2}} .flow-svg .box--active{{fill:#dcebe6;stroke:#2f7d70;stroke-width:2}} .flow-svg text{{font-family:inherit;fill:var(--ink);font-size:16px;font-weight:700}} .flow-svg .sub{{font-size:12px;font-weight:500;fill:var(--muted)}}
.phase-grid{{display:grid;grid-template-columns:repeat(auto-fit,minmax(210px,1fr));gap:12px;margin-top:18px}} .phase-card{{border:1px solid var(--line);border-radius:14px;padding:14px;background:#fff}} .phase-card>div:first-child{{display:flex;justify-content:space-between}} .phase-card small{{color:var(--muted)}} .phase-track{{height:9px;background:#ece7db;border-radius:999px;margin:10px 0;overflow:hidden}} .phase-track span{{display:block;height:100%;background:linear-gradient(90deg,var(--aqua),var(--green));border-radius:inherit}}
.route-grid{{display:grid;grid-template-columns:repeat(auto-fit,minmax(min(100%,420px),1fr));gap:16px}} .route-card{{background:var(--panel);border:1px solid var(--line);border-radius:18px;padding:22px;box-shadow:var(--shadow)}} .route-card header{{display:flex;justify-content:space-between;gap:16px;align-items:start}} h3{{margin:.2rem 0 .65rem;line-height:1.3}} h4{{margin:.5rem 0}} .route-status{{font-size:.78rem;font-weight:800;padding:5px 10px;border-radius:999px;background:#e9e6df}} .route-status--success{{background:#dcebe4;color:#175943}} .route-status--failure{{background:#f3dfe2;color:#802a37}} .path{{display:grid;gap:3px}} .path span{{font-size:.78rem;color:var(--muted)}} details summary{{cursor:pointer}} .route-detail{{display:grid;grid-template-columns:1fr 1fr;gap:18px}} .route-detail ul{{padding-left:1.25rem}} .source-link{{display:inline-block;margin-top:10px;font-weight:700}}
.task-group{{background:var(--panel);border:1px solid var(--line);border-radius:14px;margin-bottom:10px;overflow:hidden}} .task-group>summary{{display:flex;justify-content:space-between;padding:15px 18px;background:#f1ece2}} .table-wrap{{overflow:auto}} table{{width:100%;border-collapse:collapse;font-size:.9rem}} th,td{{text-align:left;padding:11px 14px;border-bottom:1px solid var(--line);vertical-align:top}} th{{color:var(--muted);font-size:.75rem;text-transform:uppercase;letter-spacing:.06em}} .state{{display:inline-block;white-space:nowrap;border-radius:999px;padding:2px 8px;background:#ece8df}} .state--done{{color:var(--green);background:#deeee6}} .state--running{{color:var(--blue);background:#dfeaf0}} .state--blocked{{color:var(--red);background:#f3dfe2}} .state--pending{{color:var(--amber);background:#f3e8d7}}
.gate{{display:flex;gap:18px;align-items:center;padding:20px 24px;border-left:6px solid var(--green)}} .gate strong{{font-size:1.4rem}} .gate p{{margin:0;color:var(--muted)}} .rounds-table{{margin-top:18px}} .discovered-grid{{display:grid;grid-template-columns:repeat(auto-fit,minmax(260px,1fr));gap:12px}} .discovered-card{{background:#fff6e5;border:1px solid #e8c992;border-radius:14px;padding:16px}} .discovered-card span{{font-size:.75rem;font-weight:800;text-transform:uppercase;color:var(--amber)}}
.sources{{display:grid;grid-template-columns:repeat(auto-fit,minmax(230px,1fr));gap:10px}} .sources a{{display:grid;text-decoration:none;background:var(--panel);border:1px solid var(--line);border-radius:12px;padding:14px}} .sources a:hover{{border-color:var(--blue)}} .sources span{{color:var(--muted);font-size:.76rem;overflow-wrap:anywhere}} footer{{border-top:1px solid var(--line);padding:24px 0 42px;color:var(--muted);font-size:.84rem}}
@media(max-width:760px){{.hero-grid{{grid-template-columns:1fr}}.donut-wrap{{width:190px;height:190px}}.metrics{{grid-template-columns:1fr 1fr}}.section-head{{display:block}}.section-head p{{margin-top:8px}}.route-detail{{grid-template-columns:1fr}}.flow-svg text{{font-size:13px}}}}
@media(max-width:470px){{.shell{{width:min(100% - 20px,1180px)}}.metrics{{grid-template-columns:1fr}}.hero{{padding-top:38px}}.panel,.flow-panel{{padding:16px}}}}
@media print{{body{{background:#fff;font-size:10pt}}.hero{{background:#26334a!important;-webkit-print-color-adjust:exact;print-color-adjust:exact}}.shell{{width:100%}}.metrics{{margin-top:16px}}.flow-svg{{min-width:0}}.panel,.flow-panel,.route-card,.metric{{box-shadow:none;break-inside:avoid}}details{{display:block}}details>*{{display:block!important}}a{{color:inherit;text-decoration:none}}section{{break-inside:auto}}}}
</style>
</head>
<body data-report-mode="report" data-report-generator="project-task-status.py">
<header class="hero"><div class="shell hero-grid"><div><span class="eyebrow">Task specification · execution record</span><h1 class="report-title">{escape(plan_name)}</h1><div class="verdict verdict--{verdict_class}">{escape(verdict)} · completion gate {escape(str(gate_value or "未記録"))}</div><p class="lead">{escape(report_note)} Markdownの実行ログを残したまま、成果・依存関係・証跡を一つの読み物として確認できます。</p></div><div class="donut-wrap"><svg class="donut" viewBox="0 0 120 120" role="img" aria-label="全体完了率 {pct}%"><circle class="donut-bg" cx="60" cy="60" r="52"/><circle class="donut-value" cx="60" cy="60" r="52" stroke-dasharray="{dash:.3f} {circumference - dash:.3f}"/></svg><div class="donut-copy"><strong>{pct}%</strong><span>{summary["by_state"]["done"]} / {summary["total"]} tasks</span></div></div></div></header>
<div class="shell metrics">{metric_cards}</div>
<main class="shell">
<section class="report-section" aria-labelledby="overview-title"><div class="section-head"><div><span class="eyebrow">Overview</span><h2 id="overview-title">仕様から証跡までの実行経路</h2></div><p>構造の正本と可変状態を分離し、完了時に同じ状態JSONからMarkdownとHTMLを同時投影します。</p></div><div class="flow-panel"><div class="flow-scroll" tabindex="0" aria-label="実行経路図。狭い画面では横にスクロールできます"><svg class="flow-svg" viewBox="0 0 1000 230" role="img" aria-label="タスク仕様書からHTML実行記録までの流れ"><defs><marker id="arrow" markerWidth="10" markerHeight="10" refX="8" refY="3" orient="auto"><path d="M0,0 L0,6 L9,3 z" fill="#777063"/></marker></defs><g><rect class="box" x="15" y="55" width="170" height="100" rx="16"/><text x="100" y="95" text-anchor="middle">タスク仕様書</text><text class="sub" x="100" y="122" text-anchor="middle">Phase / task specs</text><path d="M185 105 H220" stroke="#777063" stroke-width="2" marker-end="url(#arrow)"/><rect class="box" x="225" y="55" width="170" height="100" rx="16"/><text x="310" y="95" text-anchor="middle">Task Graph</text><text class="sub" x="310" y="122" text-anchor="middle">{graph_nodes} nodes / {graph_edges} edges</text><path d="M395 105 H430" stroke="#777063" stroke-width="2" marker-end="url(#arrow)"/><rect class="box" x="435" y="55" width="170" height="100" rx="16"/><text x="520" y="95" text-anchor="middle">並列 Dispatch</text><text class="sub" x="520" y="122" text-anchor="middle">依存順・単一 writer</text><path d="M605 105 H640" stroke="#777063" stroke-width="2" marker-end="url(#arrow)"/><rect class="box" x="645" y="55" width="150" height="100" rx="16"/><text x="720" y="95" text-anchor="middle">Evidence</text><text class="sub" x="720" y="122" text-anchor="middle">{len(status.get("route_reports", []))} route reports</text><path d="M795 105 H830" stroke="#777063" stroke-width="2" marker-end="url(#arrow)"/><rect class="box box--active" x="835" y="55" width="150" height="100" rx="16"/><text x="910" y="95" text-anchor="middle">HTML Report</text><text class="sub" x="910" y="122" text-anchor="middle">self-contained</text></g></svg></div><div class="phase-grid">{"".join(phase_cards)}</div></div></section>
<section class="report-section" aria-labelledby="routes-title"><div class="section-head"><div><span class="eyebrow">Build outputs</span><h2 id="routes-title">成果物とroute実行証跡</h2></div><p>各componentの生成結果、検証証跡、計画からの逸脱をroute単位で確認できます。</p></div><div class="route-grid">{"".join(route_cards) or '<div class="panel"><p>route report はまだ生成されていません。</p></div>'}</div></section>
<section class="report-section" aria-labelledby="tasks-title"><div class="section-head"><div><span class="eyebrow">Task ledger</span><h2 id="tasks-title">フェーズ別タスク記録</h2></div><p>大きなグラフでもフェーズごとに折りたたみ、blocked理由やroute report参照を追跡できます。</p></div>{"".join(task_sections)}</section>
<section class="report-section" aria-labelledby="gate-title"><div class="section-head"><div><span class="eyebrow">Completion & feedback</span><h2 id="gate-title">完了ゲートと仕様改善ループ</h2></div><p>未処理の発見タスクが残る場合は完了扱いにせず、外ループへ戻す判断材料を表示します。</p></div><div class="panel gate"><strong>{escape(str(gate_value or "未記録"))}</strong><p>{len(status.get("discovered_pending", []))} 件の未処理発見タスク · graph hash <code>{escape(str(status.get("graph_hash") or "未設定"))}</code></p></div>{f'<div class="table-wrap panel rounds-table"><table><thead><tr><th>周回</th><th>起点</th><th>結果</th></tr></thead><tbody>{round_rows}</tbody></table></div>' if round_rows else ''}<div class="discovered-grid">{discovered_cards}</div></section>
<section class="report-section" aria-labelledby="sources-title"><div class="section-head"><div><span class="eyebrow">Source of truth</span><h2 id="sources-title">原本と機械可読データ</h2></div><p>このHTMLは派生ビューです。監査・再生成では以下の正本とJSONを使用します。</p></div><div class="sources">{sources}</div></section>
</main>
<footer><div class="shell">`project-task-status.py` により決定論生成 · 外部CDN/外部JavaScriptなし · 印刷対応 · 手書き編集禁止</div></footer>
</body></html>'''


def _build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(
        prog="project-task-status.py",
        description=(
            "live 実行状態を plan dir へ read-only 投影する "
            "(task-graph-status.json + task-progress.md + task-execution-report.html)。"
        ),
    )
    p.add_argument("--task-graph", required=True, help="task-graph.json (構造・plan dir)")
    p.add_argument("--task-state", required=True, help="task-state.json (live 状態・build dir)")
    p.add_argument("--out-json", default=None, help="省略時 <task-graph の親>/task-graph-status.json")
    p.add_argument("--out-md", default=None, help="省略時 <task-graph の親>/task-progress.md")
    p.add_argument("--out-html", default=None, help="省略時 <task-graph の親>/task-execution-report.html")
    p.add_argument(
        "--build-summary", default=None,
        help="最終 verdict/外ループ記録。省略時は task-state と同じ dir の build-summary.json を自動検出",
    )
    p.add_argument("--discovered-inbox", default=None, help="未処理の発見タスクを載せる discovered-task inbox dir")
    return p


def main(argv: list[str] | None = None) -> int:
    argv = list(sys.argv[1:] if argv is None else argv)
    parser = _build_parser()
    try:
        args = parser.parse_args(argv)
    except SystemExit as exc:
        return int(exc.code) if isinstance(exc.code, int) else 2

    graph_path = Path(args.task_graph)
    state_path = Path(args.task_state)
    try:
        graph = _read_json(graph_path)
        task_state = _read_json(state_path)
    except (OSError, json.JSONDecodeError) as exc:
        print(f"読込/parse 失敗: {exc}", file=sys.stderr)
        return 2

    plan_dir = graph_path.parent
    out_json = Path(args.out_json) if args.out_json else plan_dir / "task-graph-status.json"
    out_md = Path(args.out_md) if args.out_md else plan_dir / "task-progress.md"
    out_html = Path(args.out_html) if args.out_html else plan_dir / "task-execution-report.html"
    if args.build_summary:
        build_summary_path: Path | None = Path(args.build_summary)
    else:
        candidate = state_path.parent / "build-summary.json"
        build_summary_path = candidate if candidate.is_file() else None
    discovered = _pending_discovered(Path(args.discovered_inbox)) if args.discovered_inbox else []

    status = build_status(graph, task_state, state_path.parent, discovered)
    status["route_reports"] = _route_reports(state_path.parent)
    status["build_summary"] = _optional_build_summary(build_summary_path)
    try:
        out_json.parent.mkdir(parents=True, exist_ok=True)
        out_md.parent.mkdir(parents=True, exist_ok=True)
        out_html.parent.mkdir(parents=True, exist_ok=True)
        out_json.write_text(json.dumps(status, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
        out_md.write_text(render_markdown(status), encoding="utf-8")
        out_html.write_text(render_html(
            status,
            graph,
            html_path=out_html,
            graph_path=graph_path,
            state_path=state_path,
            status_json_path=out_json,
            progress_md_path=out_md,
            build_summary_path=build_summary_path,
        ), encoding="utf-8")
    except OSError as exc:
        print(f"write error: {exc}", file=sys.stderr)
        return 2

    print(json.dumps({
        "status_json": str(out_json),
        "progress_md": str(out_md),
        "execution_report_html": str(out_html),
        "completion_rate": status["summary"]["completion_rate"],
        "by_state": status["summary"]["by_state"],
        "discovered_pending": len(discovered),
    }, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    sys.exit(main())
