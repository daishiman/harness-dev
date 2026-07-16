#!/usr/bin/env python3
# /// script
# name: project-task-status
# purpose: task-graph 駆動 build の live 実行状態を plan dir へ read-only 投影する観測ビュー生成器 (TG-C09)。task-graph.json (構造・単一 writer=derive・plugin-plans/ 追跡) は runtime state を焼かず ephemeral な task-state.json (eval-log/ build dir) が真の状態を持つため、両者を merge した派生ビュー (task-graph-status.json + 人間可読 task-progress.md + 構造化 task-execution-report.html) を plan dir へ書き出し「plugin-plans を見ても status が変わらない」観測性断絶を解消する。task-graph.json/task-state.json は一切書かず単一 writer 不変条件と graph_hash pin を温存する (state を task-graph.json へ焼くと hash が毎遷移で変わり pin が壊れるため投影で解決)。discovered-task inbox を読めば未処理の追加タスク (外ループ待ち) も同一ビューに載る。
# inputs:
#   - argv: --task-graph <task-graph.json> --task-state <task-state.json> [--out-json P] [--out-md P] [--out-html P]
#           [--build-summary P] [--completion-evidence P] [--discovered-inbox DIR]
#           (出力先省略時は task-graph.json の親 dir。build-summary / completion-evidence は task-state と同じ dir の同名 json を自動検出)
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

# フェーズ (毛色/category) ごとの「何のためにやるのか」を平易語で。13 phase plan 共通の
# 決定論マップ。curated override (value-narrative.json の phase_purposes) があれば優先する。
_PHASE_PURPOSE = {
    "P01": "何を作るか — 要件と作業方針を固める",
    "P02": "どう作るか — 構成・データ・依存を設計する",
    "P03": "設計を独立レビューで検証する",
    "P04": "検証方法 (テスト) を先に設計する",
    "P05": "各部品を実際に作る (実装)",
    "P06": "作った部品を動かして検証する",
    "P07": "合格ライン (受け入れ基準) を定める",
    "P08": "重複を整理し保守しやすくする",
    "P09": "全体の品質ゲートを通す",
    "P10": "最終レビューで仕上がりを確認する",
    "P11": "検証した証拠を残す",
    "P12": "使い方・導入手順を文書化する",
    "P13": "リリースしてよいか判定する",
}


def _phase_purpose(phase: str, narrative: dict | None) -> str | None:
    """フェーズの「何のため」を返す。curated override を優先し、無ければ既定マップ。"""
    if narrative:
        curated = narrative.get("phase_purposes")
        if isinstance(curated, dict) and curated.get(phase):
            return str(curated[phase])
    return _PHASE_PURPOSE.get(phase)


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


def _optional_dict(path: Path | None) -> dict | None:
    """存在すれば dict を返す任意入力 read (goal-spec / component-inventory 共通)。"""
    if path is None or not path.is_file():
        return None
    try:
        value = _read_json(path)
    except (OSError, json.JSONDecodeError):
        return None
    return value if isinstance(value, dict) else None


_BOUNDARY_HINTS = ("委譲", "複製しない", "複製せず", "担わない", "留める", "のみ",
                   "禁止", "しない", "迂回しない", "保存しない", "共有しない")


def _first_sentences(text: str, count: int) -> str:
    """日本語文 (。区切り) の先頭 count 文を返す。転記より短い「要点」を作る決定論抽出。"""
    parts = [p.strip() for p in str(text).split("。") if p.strip()]
    if not parts:
        return str(text).strip()
    return "。".join(parts[:count]) + "。"


def _readable(text, max_len: int = 120):
    """長い run-on 文を読みやすく構造化する。

    - 空: None
    - 短い (<= max_len): str のまま (段落表示)
    - 長い: まず「。」で文分割し、単一の巨大文なら「、」節でさらに分割して list[str] を返す
      (箇条書き表示にして狭い列でも折返しが崩れないようにする)。断片化が無意味な
      (節が 3 未満の) 場合は str のまま返す。
    """
    if not text:
        return None
    s = str(text).strip()
    if len(s) <= max_len:
        return s
    sentences = [p.strip() + "。" for p in s.split("。") if p.strip()]
    if len(sentences) >= 3:
        return sentences
    clauses = [c.strip() for c in s.replace("。", "").split("、") if c.strip()]
    return clauses if len(clauses) >= 3 else s


def _derive_essential_problem(goal_spec: dict) -> str | None:
    """本質的課題の決定論既定。background の問題提起部を要点抽出する。

    「明記されていない本質」の synthesize は判断を要するため、curated override
    (<plan_dir>/value-narrative.json の essential_problem) があれば main 側でそれを優先する。
    override 不在時の fail-soft 既定として background 先頭 2 文を採る。
    """
    background = goal_spec.get("background")
    return _first_sentences(background, 2) if background else None


def _derive_capabilities(goal_spec: dict, inventory: dict | None) -> list[str]:
    """「導入で何ができるようになるか」を inventory component の purpose から、無ければ
    checklist criterion から決定論抽出する (先頭 8 件に要約)。"""
    caps: list[str] = []
    comps = (inventory or {}).get("components")
    if isinstance(comps, list):
        for c in comps:
            if not isinstance(c, dict):
                continue
            text = c.get("purpose") or c.get("description") or c.get("name")
            if text:
                caps.append(_first_sentences(str(text), 1))
    if not caps:
        for item in goal_spec.get("checklist", []) or []:
            if isinstance(item, dict) and item.get("criterion"):
                caps.append(_first_sentences(str(item["criterion"]), 1))
    # 重複除去 (順序保持) + 読み切れる粒度に絞る。
    seen: set[str] = set()
    unique = [c for c in caps if not (c in seen or seen.add(c))]
    return unique[:8]


def _derive_boundaries(goal_spec: dict) -> list[str]:
    """責務境界・非目標を constraints から境界語ヒューリスティックで決定論抽出する (先頭 5 件)。"""
    out: list[str] = []
    for c in goal_spec.get("constraints", []) or []:
        if isinstance(c, str) and any(hint in c for hint in _BOUNDARY_HINTS):
            out.append(_first_sentences(c, 2))
    return out[:5]


def _value_narrative(goal_spec: dict | None, inventory: dict | None) -> dict | None:
    """goal-spec と component-inventory から「価値の物語」データモデルを組み立てる。

    実行記録に「結果 (状態遷移)」だけでなく **なぜ導入するのか・どの本質的課題を解決する
    のか・導入すると何ができるようになるのか** を載せるための source 抽出。purpose /
    background / goal は goal-spec の該当 field をそのまま採り (機械的転記)、essential_problem /
    capabilities / boundaries は goal-spec/inventory から決定論導出する。「明記されていない
    本質」の synthesize は判断を要するため、main 側で <plan_dir>/value-narrative.json (curated
    override) があれば非空キーを上書き合成する (決定論既定の上に人手 curation を重ねる二層)。
    """
    if not goal_spec:
        return None
    return {
        # 技術層 (goal-spec から決定論導出)
        "purpose": _readable(goal_spec.get("purpose")),
        "background": _readable(goal_spec.get("background")),
        "goal": goal_spec.get("goal"),
        "essential_problem": _derive_essential_problem(goal_spec),
        "capabilities": _derive_capabilities(goal_spec, inventory),
        "boundaries": _derive_boundaries(goal_spec),
        # 非エンジニア (やさしい) 層。決定論では作れないため既定は空で、
        # <plan_dir>/value-narrative.json (curated override) が埋める想定。
        "plain_intro": None,
        "essential_problem_plain": None,
        "capabilities_plain": [],
    }


def build_status(graph: dict, task_state: dict, build_dir: Path | None,
                 discovered: list[dict],
                 completion_evidence: dict | None = None) -> dict:
    """overlay 済 node + summary + discovered を統合した status ビュー dict を返す (read-only 純関数)。

    build_dir=None は plan モード (build 前・task-state 無し)。route report は集計しない。
    """
    state_by_id = {n.get("id"): n for n in task_state.get("nodes", []) if isinstance(n, dict)}
    evidence_blocked = (
        isinstance(completion_evidence, dict)
        and completion_evidence.get("overall_status") != "pass"
    )
    invalidated_ids = set(completion_evidence.get("invalidated_task_ids", [])) \
        if evidence_blocked and isinstance(completion_evidence.get("invalidated_task_ids"), list) else set()
    invalidated_phases = set(completion_evidence.get("invalidated_phase_refs", [])) \
        if evidence_blocked and isinstance(completion_evidence.get("invalidated_phase_refs"), list) else set()
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
        if (
            entry["state"] == "done"
            and (entry["id"] in invalidated_ids or entry["phase_ref"] in invalidated_phases)
        ):
            # task-state は実行履歴として不変のまま保ち、派生ビューだけを証跡 truth へ補正する。
            # これにより route の done 自己申告を消さず、受入ゲート未達を完了率へ反映できる。
            entry["reported_state"] = "done"
            entry["state"] = "blocked"
            entry["blocked_reason"] = "completion-evidence"
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
    route_report_count = summarize(task_state, build_dir)["route_report_count"] if build_dir else 0
    return {
        "_generated": "project-task-status.py (派生ビュー・手書き編集しない・再生成で上書き)",
        "graph_hash": task_state.get("graph_hash"),
        "summary": {
            "total": total,
            "by_state": by_state,
            "completion_rate": completion_rate,
            "blocked_tasks": blocked_tasks,
            "route_report_count": route_report_count,
            "completion_gate": "blocked" if evidence_blocked else None,
            "effective_status": (
                "blocked"
                if evidence_blocked or by_state["blocked"]
                else "complete"
                if total > 0 and by_state["done"] == total
                else "in_progress"
            ),
        },
        "nodes": live_nodes,
        "discovered_pending": discovered,
    }


def render_markdown(status: dict, narrative: dict | None = None,
                    graph: dict | None = None, plan_mode: bool = False) -> str:
    """status ビューを人間可読な Markdown へ整形する (価値/依存関係/phase グループ)。

    plan_mode=True は build 前の計画構造ビュー (見出し・凡例を計画向けに切替)。graph を
    渡すと依存関係 (何が何に依存するか) ブロックを追加する。
    """
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
    if not plan_mode:
        # plan モード (build 前) は全 node が pending で gate 評価が存在しないため出さない。
        lines.append(
            f"- 実効状態: **{s.get('effective_status', 'in_progress')}**"
            f" / completion gate: **{s.get('completion_gate') or '未評価'}**"
        )
    if status.get("graph_hash"):
        lines.append(f"- graph_hash pin: `{status['graph_hash']}`")
    lines.append("")

    # 価値の物語 (dual audience: やさしい説明 + 技術的な詳細)。narrative 不在なら省略 (fail-soft)。
    if narrative:
        def _md_value(label: str, value) -> list[str]:
            if isinstance(value, list):
                items = [v for v in value if v]
                if not items:
                    return []
                return [f"- **{label}**:"] + [f"  - {v}" for v in items]
            if value:
                return [f"- **{label}**: {value}"]
            return []

        lines.append("## このタスクの目的と、導入で得られる価値")
        lines.append("")
        if any(narrative.get(k) for k in ("plain_intro", "essential_problem_plain", "capabilities_plain")):
            lines.append("### やさしい説明 (どなたでも)")
            lines += _md_value("これは何をするもの?", narrative.get("plain_intro"))
            lines += _md_value("どんな困りごとを解決する?", narrative.get("essential_problem_plain"))
            lines += _md_value("導入すると何がうれしい?", narrative.get("capabilities_plain"))
            lines.append("")
        lines.append("### 技術的な詳細 (エンジニア向け)")
        lines += _md_value("本質的な問題・課題", narrative.get("essential_problem"))
        lines += _md_value("導入すると何ができるようになるか", narrative.get("capabilities"))
        lines += _md_value("責務境界・非目標", narrative.get("boundaries"))
        lines += _md_value("目的 (何をするか)", narrative.get("purpose"))
        lines += _md_value("背景・前提", narrative.get("background"))
        lines += _md_value("到達状態 (Goal)", narrative.get("goal"))
        lines.append("")

    # 依存関係サマリ (何が何に依存して進むか)。graph があれば追加。
    if graph:
        rel = _relationships(graph)
        if rel["total"]:
            lines.append("## タスクの依存関係 (何が何に依存して進むか)")
            lines.append(f"> 全 {rel['total']} タスク・{rel['count']} 依存エッジ。"
                         "各フェーズの詳細は下記チェックリスト、完全な関係は HTML レポートを参照。")
            roots = rel["roots"][:16]
            if roots:
                lines.append("- 起点タスク (依存なしで最初に着手可能): "
                             + "、".join(f"`{r}`" for r in roots))
            lines.append("")

    # phase グループの node チェックリスト。
    by_phase: dict[str, list[dict]] = {}
    for n in status["nodes"]:
        by_phase.setdefault(str(n.get("phase_ref")), []).append(n)
    for phase in sorted(by_phase):
        lines.append(f"## {phase}")
        pp = _phase_purpose(phase, narrative)
        if pp:
            lines.append(f"> 🎯 何のため: {pp}")
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
    if summary.get("effective_status") == "blocked":
        return "要対応", "blocked"
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


def _value_body_html(value) -> str:
    """narrative の 1 要素 (str または list[str]) を構造化 HTML 本文へ描画する。

    list は箇条書き (<ul>) に、str は段落 (<p>) にする。読みにくい run-on の str が
    渡っても、curated override / _readable が list を渡せば箇条書きで見やすくなる。
    """
    if isinstance(value, list):
        lis = "".join(f"<li>{escape(str(item))}</li>" for item in value if item)
        return f"<ul>{lis}</ul>" if lis else ""
    if value:
        return f"<p>{escape(str(value))}</p>"
    return ""


def render_value_section(narrative: dict | None) -> str:
    """価値の物語を dual audience (やさしい説明 / 技術的な詳細) の二層バンドで描画する。

    narrative が None (goal-spec 不在) なら空文字を返し他セクションは通常生成される (fail-soft)。
    各要素は str でも list[str] でも受け list は箇条書きで構造化する。読み手を選ばないよう、
    上段に非エンジニア向けの平易な説明、下段に技術的な詳細を全幅・単カラムで積む。
    """
    if not narrative:
        return ""

    def block(label: str, value, empty: str | None = None) -> str:
        body = _value_body_html(value)
        if not body:
            if empty is None:
                return ""
            body = f'<p class="value-empty">{escape(empty)}</p>'
        return (f'<div class="value-block"><span class="eyebrow">{escape(label)}</span>'
                f'{body}</div>')

    # ── Band 1: 非エンジニアにも分かる「やさしい説明」 (揃っている項目だけ描画) ──
    plain_blocks = "".join([
        block("これは何をするもの?", narrative.get("plain_intro")),
        block("どんな困りごとを解決する?", narrative.get("essential_problem_plain")),
        block("導入すると何がうれしい?", narrative.get("capabilities_plain")),
    ])
    plain_band = (
        '<div class="value-band value-band--plain">'
        '<span class="band-tag">やさしい説明 (どなたでも)</span>'
        f'{plain_blocks}</div>'
    ) if plain_blocks else ""

    # ── Band 2: エンジニア向け「技術的な詳細」 ──
    problem_body = _value_body_html(narrative.get("essential_problem"))
    problem_html = (
        f'<div class="value-problem"><span class="eyebrow">本質的な問題・課題</span>{problem_body}</div>'
        if problem_body else ""
    )
    tech_blocks = "".join([
        block("導入すると何ができるようになるか", narrative.get("capabilities"), "（未記載）"),
        block("責務境界・非目標", narrative.get("boundaries"), "（未記載）"),
        block("目的 (何をするか)", narrative.get("purpose")),
        block("背景・前提", narrative.get("background")),
        block("到達状態 (Goal)", narrative.get("goal")),
    ])
    tech_band = (
        '<div class="value-band value-band--tech">'
        '<span class="band-tag">技術的な詳細 (エンジニア向け)</span>'
        f'{problem_html}{tech_blocks}</div>'
    )

    return (
        '<section class="report-section value-section" aria-labelledby="value-title">'
        '<div class="section-head"><div><span class="eyebrow">Why &amp; value</span>'
        '<h2 id="value-title">このタスクの目的と、導入で得られる価値</h2></div>'
        '<p>結果 (状態遷移) だけでなく、なぜ導入するのか・どの本質的課題を解決し、何ができるように'
        'なったのかを、どなたでも分かる説明と技術的な詳細の両面で示します。</p></div>'
        f'<div class="value-panel panel">{plain_band}{tech_band}</div>'
        '</section>'
    )


def _relationships(graph: dict) -> dict:
    """task-graph の depends_on エッジから依存関係ビューを構築する (plan 構造の可視化)。

    edge {type:depends_on, from:consumer, to:producer} は「from は to の完了後に着手」を表す。
    各 node の依存先 (upstream) / 被依存 (downstream) と、依存なしの起点タスクを返す。
    """
    nodes = [n for n in graph.get("nodes", []) if isinstance(n, dict) and n.get("id")]
    ids = {n["id"] for n in nodes}
    title = {n["id"]: n.get("title") for n in nodes}
    phase = {n["id"]: n.get("phase_ref") for n in nodes}
    entity = {n["id"]: n.get("entity_ref") for n in nodes}
    deps: dict[str, list[str]] = {i: [] for i in ids}
    dependents: dict[str, list[str]] = {i: [] for i in ids}
    edge_count = 0
    for edge in graph.get("edges", []) or []:
        if not isinstance(edge, dict) or edge.get("type") != "depends_on":
            continue
        frm, to = edge.get("from"), edge.get("to")
        if frm in ids and to in ids:
            deps[frm].append(to)
            dependents[to].append(frm)
            edge_count += 1
    roots = sorted(i for i in ids if not deps[i])
    return {"total": len(nodes), "count": edge_count, "roots": roots,
            "deps": deps, "dependents": dependents, "title": title,
            "phase": phase, "entity": entity}


def _dag_layers(rel: dict) -> tuple[dict, dict]:
    """depends_on から各ノードの実行レイヤー (longest-path depth) を決定論算出する。

    depth(n)=0 (依存なし=最初に着手可) / 依存ありは 1+max(依存先 depth)。同じ depth の
    ノードは同時に着手可能 = 実行フローの同一段。cycle は 0 で打ち切る (DAG 前提の安全網)。
    返り値: (depth: {id->int}, layers: {depth->[id...] 昇順})。
    """
    deps = rel["deps"]
    depth: dict[str, int] = {}

    def resolve(node: str, seen: frozenset) -> int:
        if node in depth:
            return depth[node]
        if node in seen:
            return 0
        ups = deps.get(node, [])
        value = 0 if not ups else 1 + max(
            (resolve(u, seen | {node}) for u in ups), default=-1)
        depth[node] = value
        return value

    for n in deps:
        resolve(n, frozenset())
    layers: dict[int, list[str]] = {}
    for node, dp in depth.items():
        layers.setdefault(dp, []).append(node)
    for dp in layers:
        layers[dp].sort()
    return depth, layers


def _render_dag_svg(rel: dict, state_by_id: dict) -> str:
    """依存の流れを層状 DAG の自己完結 SVG で描く (実行フロー図解)。

    列 (左→右) = 実行レイヤー (依存深さ)、ノード = タスク、矢印 = depends_on (先に完了が必要)。
    ノード色は state に連動し plan(全pending=灰) でも execution(done=緑) でも意味を持つ。
    ノード数が多すぎる (>90) 場合は描画を省略しテキスト表 (下段) に委ねる。
    """
    depth, layers = _dag_layers(rel)
    if not layers or rel["total"] > 90:
        return ""
    col, row, bw, bh, pad = 168, 42, 128, 30, 24
    pos: dict[str, tuple[int, int]] = {}
    for dp in sorted(layers):
        for r, node in enumerate(layers[dp]):
            pos[node] = (pad + dp * col, pad + r * row)
    max_rows = max((len(v) for v in layers.values()), default=1)
    width = pad * 2 + (max(layers) + 1) * col
    height = pad * 2 + max_rows * row
    edges = []
    for node, ups in rel["deps"].items():
        if node not in pos:
            continue
        x2, y2 = pos[node]
        for up in ups:
            if up not in pos:
                continue
            x1, y1 = pos[up]
            edges.append(
                f'<path class="dag-edge" marker-end="url(#dag-arrow)" '
                f'd="M{x1 + bw},{y1 + bh // 2} C{x1 + bw + 34},{y1 + bh // 2} '
                f'{x2 - 34},{y2 + bh // 2} {x2},{y2 + bh // 2}"/>'
            )
    nodes = []
    for node, (x, y) in pos.items():
        st = escape(str(state_by_id.get(node, "pending")))
        label = escape(str(node))
        nodes.append(
            f'<g class="dag-node dag-node--{st}">'
            f'<rect x="{x}" y="{y}" width="{bw}" height="{bh}" rx="8"/>'
            f'<text x="{x + bw // 2}" y="{y + bh // 2 + 4}" text-anchor="middle">{label}</text></g>'
        )
    return (
        '<div class="flow-scroll" tabindex="0" aria-label="実行フロー図。左の列から順に着手でき、'
        '矢印は先に完了が必要なタスクを指します。狭い画面では横スクロールできます">'
        f'<svg class="dag-svg" viewBox="0 0 {width} {height}" role="img" '
        'aria-label="タスク依存の実行フロー図">'
        '<defs><marker id="dag-arrow" markerWidth="9" markerHeight="9" refX="7" refY="3" '
        'orient="auto"><path d="M0,0 L0,6 L8,3 z" fill="#8a8275"/></marker></defs>'
        f'{"".join(edges)}{"".join(nodes)}</svg></div>'
    )


def render_relationships_section(graph: dict, status: dict | None = None,
                                 spec_browser_href: str | None = None) -> str:
    """タスク仕様書の構成と依存関係 (spec → タスク → ノード → グラフ) の HTML。

    先頭に実行フロー図解 (層状 DAG の SVG) を置き、続けて depends_on を phase ごとの表へ
    構造化する。「どのタスクが何に依存して進むか」「最初に着手できる起点タスクはどれか」
    「どういう流れで実行するか」を図と表の両方で追える。build 前後どちらでも中核セクション。
    """
    rel = _relationships(graph)
    if rel["total"] == 0:
        return ""
    state_by_id = {
        n.get("id"): n.get("state", "pending")
        for n in (status or {}).get("nodes", []) if isinstance(n, dict)
    }
    dag_svg = _render_dag_svg(rel, state_by_id)
    flow_block = (
        '<div class="flow-panel"><div class="section-head"><div>'
        '<span class="eyebrow">実行フロー図解</span></div>'
        '<p>左の列から順に着手できます。矢印 A → B は「A が終わってから B に着手」を表し、'
        '色はタスクの状態 (緑=完了 / 灰=未着手 / 青=実行中 / 赤=要対応) です。</p></div>'
        f'{dag_svg}</div>'
        if dag_svg else ""
    )
    spec_link = (
        '<div class="panel spec-cta"><span class="eyebrow">各仕様書の中身を読む</span>'
        f'<p><a href="{escape(spec_browser_href)}">📄 仕様書ブラウザを開く</a> — '
        '13 フェーズ仕様書とタスク別仕様書の本文を、index からページ遷移・戻る操作で読めます。</p></div>'
        if spec_browser_href else ""
    )
    roots_html = "".join(
        f'<li><code>{escape(str(i))}</code> {escape(str(rel["title"].get(i) or ""))}</li>'
        for i in rel["roots"][:16]
    )
    by_phase: dict[str, list[str]] = {}
    for i in sorted(rel["deps"]):
        by_phase.setdefault(str(rel["phase"].get(i) or "未分類"), []).append(i)
    phase_blocks: list[str] = []
    for phase in sorted(by_phase):
        rows = []
        for i in by_phase[phase]:
            deps = sorted(rel["deps"][i])
            dep_txt = (
                "、".join(f'<code>{escape(str(x))}</code>' for x in deps)
                if deps else '<span class="rel-root">起点 (依存なし)</span>'
            )
            entity = rel["entity"].get(i)
            entity_txt = f'<code>{escape(str(entity))}</code>' if entity else "—"
            rows.append(
                f'<tr><td><code>{escape(str(i))}</code></td>'
                f'<td>{escape(str(rel["title"].get(i) or ""))}</td>'
                f'<td>{entity_txt}</td><td>{dep_txt}</td></tr>'
            )
        pp = _phase_purpose(phase, None)
        pp_row = f'<p class="phase-purpose">🎯 何のため: {escape(pp)}</p>' if pp else ""
        phase_blocks.append(
            f'<details class="task-group" open><summary><strong>{escape(phase)}</strong>'
            f'<span>{len(by_phase[phase])} tasks</span></summary>{pp_row}'
            '<div class="table-wrap"><table><thead><tr><th>タスク</th><th>内容</th>'
            '<th>成果物 (entity)</th><th>← 依存先 (先に完了が必要)</th></tr></thead>'
            f'<tbody>{"".join(rows)}</tbody></table></div></details>'
        )
    return (
        '<section class="report-section" aria-labelledby="rel-title">'
        '<div class="section-head"><div><span class="eyebrow">Structure &amp; relationships</span>'
        '<h2 id="rel-title">タスク仕様書の構成と依存関係</h2></div>'
        f'<p>全 {rel["total"]} タスク・{rel["count"]} 依存エッジ。まず実行フロー図で全体の流れを、'
        '続く表で各タスクの依存先 (先に完了が必要なタスク) を確認できます。spec → 各タスク → '
        'ノード → グラフのつながりを表します。</p></div>'
        f'{spec_link}'
        f'{flow_block}'
        '<div class="panel"><div class="value-block">'
        '<span class="eyebrow">起点タスク (依存なしで最初に着手できる)</span>'
        f'<ul>{roots_html or "<li>なし</li>"}</ul></div></div>'
        f'{"".join(phase_blocks)}'
        '</section>'
    )


def render_html(
    status: dict,
    graph: dict,
    *,
    html_path: Path,
    graph_path: Path,
    state_path: Path | None,
    status_json_path: Path,
    progress_md_path: Path,
    build_summary_path: Path | None,
    narrative: dict | None = None,
    plan_mode: bool = False,
    spec_browser_href: str | None = None,
) -> str:
    """同じ status 投影から決定論的な自己完結 HTML を生成する。

    plan_mode=True は build 前の「計画構造レポート」(task-state 無し・全タスク未着手)。
    完了率でなく構成と依存関係を主役にし、hero の文言を計画向けに切り替える。
    """
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
        purpose = _phase_purpose(phase, narrative)
        purpose_line = f'<small class="phase-purpose">{escape(purpose)}</small>' if purpose else ""
        phase_cards.append(
            '<article class="phase-card">'
            f'<div><strong>{escape(phase)}</strong><span>{counts["done"]}/{len(nodes)}</span></div>'
            f'{purpose_line}'
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
        purpose_row = f'<p class="phase-purpose">🎯 何のため: {escape(purpose)}</p>' if purpose else ""
        task_sections.append(
            f'<details class="task-group"><summary><strong>{escape(phase)}</strong>'
            f'<span>{len(nodes)} tasks / {done_pct}%</span></summary>'
            f'{purpose_row}'
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
            f'<div class="route-why"><span class="eyebrow">何のために作ったか</span>'
            f'<p>{escape(str(route.get("summary") or "概要なし"))}</p></div>'
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
    gate_value = gate.get("completion_gate") if isinstance(gate, dict) else gate
    if gate_value is None:
        gate_value = summary.get("completion_gate")
    rounds = build_summary.get("outer_loop_rounds") if isinstance(build_summary, dict) else None
    round_rows = "".join(
        '<tr>'
        f'<td>{escape(str(item.get("round") or "—"))}</td>'
        f'<td>{escape(str(item.get("origin") or "—"))}</td>'
        f'<td>{escape(str(item.get("result") or "—"))}</td></tr>'
        for item in (rounds if isinstance(rounds, list) else []) if isinstance(item, dict)
    )

    source_links = [("task-graph.json", graph_path)]
    if state_path is not None:
        source_links.append(("task-state.json", state_path))
    source_links += [
        ("task-graph-status.json", status_json_path),
        ("task-progress.md", progress_md_path),
    ]
    if build_summary_path is not None and build_summary_path.is_file():
        source_links.append(("build-summary.json", build_summary_path))
    completion_evidence = status.get("completion_evidence")
    if isinstance(completion_evidence, dict) and completion_evidence.get("_source_path"):
        source_links.append((
            "completion-evidence.json",
            Path(str(completion_evidence["_source_path"])),
        ))
    sources = "".join(
        f'<a href="{_artifact_href(path, html_path)}"><strong>{escape(label)}</strong>'
        f'<span>{escape(str(path))}</span></a>' for label, path in source_links
    )

    graph_nodes = len(graph.get("nodes", [])) if isinstance(graph.get("nodes"), list) else 0
    graph_edges = len(graph.get("edges", [])) if isinstance(graph.get("edges"), list) else 0

    # plan モード (build 前) は完了率でなく構成・依存関係を主役にする。
    if plan_mode:
        hero_eyebrow = "Task specification · structure map"
        verdict, verdict_class = "計画 (build 前)", "pending"
        report_note = (
            f"これは build 前の計画構造レポートです。この仕様書で何をやるか、"
            f"全 {summary['total']} タスク・{graph_edges} 依存の構成と関係性を示します。"
        )
        donut_number, donut_label, dash = str(summary["total"]), "タスク", 0.0
        gate_line = f"{summary['total']} タスク / {graph_edges} 依存エッジ"
    else:
        hero_eyebrow = "Task specification · execution record"
        report_note = (
            "全タスクと完了ゲートが通過しています。"
            if verdict_class == "complete" and gate_value in (None, "ok")
            else "進行中または要対応の項目があります。詳細を確認してください。"
        )
        donut_number, donut_label = f"{pct}%", f'{summary["by_state"]["done"]} / {summary["total"]} tasks'
        gate_line = f'completion gate {escape(str(gate_value or "未記録"))}'

    overview_note = (
        "この仕様書がどんなタスクへ分解され、どんな順序 (依存) で実行されるかを示します。"
        if plan_mode else
        "構造の正本と可変状態を分離し、完了時に同じ状態JSONからMarkdownとHTMLを同時投影します。"
    )
    # 成果物 route 証跡・完了ゲートは execution モード専用 (plan モードでは build 前で不在ゆえ隠す)。
    _routes_grid = "".join(route_cards) or '<div class="panel"><p>route report はまだ生成されていません。</p></div>'
    routes_section = "" if plan_mode else (
        '<section class="report-section" aria-labelledby="routes-title"><div class="section-head"><div>'
        '<span class="eyebrow">Build outputs</span><h2 id="routes-title">成果物とroute実行証跡</h2></div>'
        '<p>各componentの生成結果・検証証跡・計画からの逸脱をroute単位で、何のために作ったかと合わせて確認できます。</p></div>'
        f'<div class="route-grid">{_routes_grid}</div></section>'
    )
    _rounds_table = (
        '<div class="table-wrap panel rounds-table"><table><thead><tr><th>周回</th><th>起点</th>'
        f'<th>結果</th></tr></thead><tbody>{round_rows}</tbody></table></div>' if round_rows else ''
    )
    gate_section = "" if plan_mode else (
        '<section class="report-section" aria-labelledby="gate-title"><div class="section-head"><div>'
        '<span class="eyebrow">Completion &amp; feedback</span><h2 id="gate-title">完了ゲートと仕様改善ループ</h2></div>'
        '<p>未処理の発見タスクが残る場合は完了扱いにせず、外ループへ戻す判断材料を表示します。</p></div>'
        f'<div class="panel gate"><strong>{escape(str(gate_value or "未記録"))}</strong>'
        f'<p>{len(status.get("discovered_pending", []))} 件の未処理発見タスク · graph hash '
        f'<code>{escape(str(status.get("graph_hash") or "未設定"))}</code></p></div>'
        f'{_rounds_table}<div class="discovered-grid">{discovered_cards}</div></section>'
    )

    # セクションナビ (sticky・ページ内ジャンプ + 現在地ハイライト)。plan/execution で項目を出し分ける。
    nav_items: list[tuple[str, str]] = []
    if narrative:
        nav_items.append(("#value-title", "目的・価値"))
    if graph.get("nodes"):
        nav_items.append(("#rel-title", "構成・依存・フロー図"))
    nav_items.append(("#overview-title", "実行経路"))
    if not plan_mode:
        nav_items.append(("#routes-title", "成果物"))
    nav_items.append(("#tasks-title", "タスク一覧"))
    if not plan_mode:
        nav_items.append(("#gate-title", "完了ゲート"))
    nav_items.append(("#sources-title", "原本"))
    nav_links = "".join(f'<a href="{escape(h)}">{escape(t)}</a>' for h, t in nav_items)
    spec_nav = (
        f'<a class="nav-spec" href="{escape(spec_browser_href)}">📄 仕様書を読む</a>'
        if spec_browser_href else ""
    )
    report_nav = (
        '<nav class="report-nav" aria-label="セクションナビ"><div class="shell report-nav-inner">'
        f'{nav_links}{spec_nav}</div></nav>'
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
main{{padding:40px 0 72px}} section{{margin:0 0 52px;scroll-margin-top:64px}} .section-head{{display:flex;justify-content:space-between;align-items:end;gap:20px;margin-bottom:20px}} h2{{font-size:clamp(1.5rem,3vw,2.2rem);line-height:1.25;margin:0}} h2[id]{{scroll-margin-top:66px}} .section-head p{{max-width:58ch;margin:0;color:var(--muted)}}
.report-nav{{position:sticky;top:0;z-index:30;background:rgba(255,253,247,.94);-webkit-backdrop-filter:blur(6px);backdrop-filter:blur(6px);border-bottom:1px solid var(--line);box-shadow:0 2px 10px rgba(45,42,50,.05)}} .report-nav-inner{{display:flex;gap:6px;overflow-x:auto;padding:9px 0;scrollbar-width:thin}} .report-nav a{{white-space:nowrap;font-size:.85rem;font-weight:700;color:var(--muted);padding:6px 14px;border-radius:999px;text-decoration:none;transition:background .15s}} .report-nav a:hover{{background:#efeadf;color:var(--ink)}} .report-nav a.active{{background:var(--navy);color:#fff}} .report-nav a.nav-spec{{color:var(--green);border:1px solid #bcd8c9}}
.value-panel{{display:grid;gap:26px}} .value-band{{display:grid;gap:16px;padding:24px;border-radius:16px}} .value-band--plain{{background:#eef5f1;border:1px solid #cfe2d7}} .value-band--tech{{background:#f6f2ea;border:1px solid var(--line)}} .band-tag{{justify-self:start;font-size:.8rem;font-weight:800;letter-spacing:.03em;padding:5px 13px;border-radius:999px;background:#fff;border:1px solid var(--line);color:var(--navy)}} .value-band--plain .band-tag{{color:var(--green);border-color:#bcd8c9}} .value-block .eyebrow{{color:var(--blue);margin-bottom:3px}} .value-band--plain .value-block .eyebrow{{color:var(--green)}} .value-block p{{margin:.3rem 0 0;max-width:82ch}} .value-band--plain .value-block p,.value-band--plain .value-block li{{font-size:1.02rem}} .value-block ul{{margin:.3rem 0 0;padding-left:1.25rem}} .value-block li{{margin:.32rem 0;max-width:80ch;line-height:1.7}} .value-problem{{background:#fff;border:1px solid var(--line);border-left:6px solid var(--aqua);border-radius:12px;padding:16px 20px}} .value-problem .eyebrow{{color:var(--aqua)}} .value-problem p{{margin:.3rem 0 0;font-weight:600;max-width:82ch}} .value-problem ul{{margin:.3rem 0 0;padding-left:1.25rem}} .value-problem li{{margin:.3rem 0;max-width:80ch;font-weight:500}} .value-empty{{color:var(--muted);font-style:italic}}
.task-purpose,.phase-purpose{{color:var(--muted);font-size:.86rem;margin:2px 0 0}} .route-why{{color:var(--navy)}} .route-why .eyebrow{{color:var(--blue)}} .rel-root{{color:var(--green);font-weight:700}} .task-group .phase-purpose{{padding:10px 18px 0}}
.spec-cta{{border-left:6px solid var(--blue);margin-bottom:16px}} .spec-cta p{{margin:.3rem 0 0}} .spec-cta a{{font-weight:800}}
.dag-svg{{display:block;width:100%;min-width:640px;height:auto;margin-top:8px}} .dag-edge{{fill:none;stroke:#b7b0a2;stroke-width:1.4}} .dag-node rect{{fill:#f4efe5;stroke:#8a8275;stroke-width:1.3}} .dag-node text{{font-family:inherit;font-size:12px;font-weight:700;fill:var(--ink)}} .dag-node--done rect{{fill:#deeee6;stroke:#27745c}} .dag-node--running rect{{fill:#dfeaf0;stroke:#376b8c}} .dag-node--blocked rect{{fill:#f3dfe2;stroke:#a33d4b}} .dag-node--pending rect{{fill:#f4efe5;stroke:#a99f8c}}
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
<header class="hero"><div class="shell hero-grid"><div><span class="eyebrow">{hero_eyebrow}</span><h1 class="report-title">{escape(plan_name)}</h1><div class="verdict verdict--{verdict_class}">{escape(verdict)} · {gate_line}</div><p class="lead">{escape(report_note)} タスク仕様書の目的・構成・依存関係・証跡を、どなたでも分かる説明と技術詳細の両面で確認できます。</p></div><div class="donut-wrap"><svg class="donut" viewBox="0 0 120 120" role="img" aria-label="{escape(donut_label)}"><circle class="donut-bg" cx="60" cy="60" r="52"/><circle class="donut-value" cx="60" cy="60" r="52" stroke-dasharray="{dash:.3f} {circumference - dash:.3f}"/></svg><div class="donut-copy"><strong>{escape(donut_number)}</strong><span>{escape(donut_label)}</span></div></div></div></header>
<div class="shell metrics">{metric_cards}</div>
{report_nav}
<main class="shell">
{render_value_section(narrative)}
{render_relationships_section(graph, status, spec_browser_href)}
<section class="report-section" aria-labelledby="overview-title"><div class="section-head"><div><span class="eyebrow">Overview</span><h2 id="overview-title">仕様から実行までの経路</h2></div><p>{overview_note}</p></div><div class="flow-panel"><div class="flow-scroll" tabindex="0" aria-label="実行経路図。狭い画面では横にスクロールできます"><svg class="flow-svg" viewBox="0 0 1000 230" role="img" aria-label="タスク仕様書からHTML実行記録までの流れ"><defs><marker id="arrow" markerWidth="10" markerHeight="10" refX="8" refY="3" orient="auto"><path d="M0,0 L0,6 L9,3 z" fill="#777063"/></marker></defs><g><rect class="box" x="15" y="55" width="170" height="100" rx="16"/><text x="100" y="95" text-anchor="middle">タスク仕様書</text><text class="sub" x="100" y="122" text-anchor="middle">Phase / task specs</text><path d="M185 105 H220" stroke="#777063" stroke-width="2" marker-end="url(#arrow)"/><rect class="box" x="225" y="55" width="170" height="100" rx="16"/><text x="310" y="95" text-anchor="middle">Task Graph</text><text class="sub" x="310" y="122" text-anchor="middle">{graph_nodes} nodes / {graph_edges} edges</text><path d="M395 105 H430" stroke="#777063" stroke-width="2" marker-end="url(#arrow)"/><rect class="box" x="435" y="55" width="170" height="100" rx="16"/><text x="520" y="95" text-anchor="middle">並列 Dispatch</text><text class="sub" x="520" y="122" text-anchor="middle">依存順・単一 writer</text><path d="M605 105 H640" stroke="#777063" stroke-width="2" marker-end="url(#arrow)"/><rect class="box" x="645" y="55" width="150" height="100" rx="16"/><text x="720" y="95" text-anchor="middle">Evidence</text><text class="sub" x="720" y="122" text-anchor="middle">{len(status.get("route_reports", []))} route reports</text><path d="M795 105 H830" stroke="#777063" stroke-width="2" marker-end="url(#arrow)"/><rect class="box box--active" x="835" y="55" width="150" height="100" rx="16"/><text x="910" y="95" text-anchor="middle">HTML Report</text><text class="sub" x="910" y="122" text-anchor="middle">self-contained</text></g></svg></div><div class="phase-grid">{"".join(phase_cards)}</div></div></section>
{routes_section}
<section class="report-section" aria-labelledby="tasks-title"><div class="section-head"><div><span class="eyebrow">Task ledger</span><h2 id="tasks-title">フェーズ別タスク記録</h2></div><p>大きなグラフでもフェーズごとに折りたたみ、各フェーズが何のためか・blocked理由やroute report参照を追跡できます。</p></div>{"".join(task_sections)}</section>
{gate_section}
<section class="report-section" aria-labelledby="sources-title"><div class="section-head"><div><span class="eyebrow">Source of truth</span><h2 id="sources-title">原本と機械可読データ</h2></div><p>このHTMLは派生ビューです。監査・再生成では以下の正本とJSONを使用します。</p></div><div class="sources">{sources}</div></section>
</main>
<footer><div class="shell">`project-task-status.py` により決定論生成 · 外部CDN/外部ライブラリ非依存 (装飾のみのインライン JS) · 印刷対応 · 手書き編集禁止</div></footer>
<script>
(function(){{
  var links=[].slice.call(document.querySelectorAll('.report-nav a[href^="#"]'));
  if(!links.length)return;
  function spy(){{
    var y=window.scrollY+90,cur=null;
    links.forEach(function(a){{
      var el=document.getElementById(a.getAttribute('href').slice(1));
      if(el&&el.getBoundingClientRect().top+window.scrollY<=y)cur=a;
    }});
    links.forEach(function(a){{a.classList.remove('active');}});
    if(cur)cur.classList.add('active');
  }}
  window.addEventListener('scroll',spy,{{passive:true}});
  window.addEventListener('resize',spy);spy();
}})();
</script>
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
    p.add_argument("--task-state", default=None,
                   help="task-state.json (live 状態・build dir)。省略時は plan モード "
                        "(build 前・全タスク未着手) で構成と依存関係を主役に描画する")
    p.add_argument("--out-json", default=None, help="省略時 <task-graph の親>/task-graph-status.json")
    p.add_argument("--out-md", default=None, help="省略時 <task-graph の親>/task-progress.md")
    p.add_argument("--out-html", default=None, help="省略時 <task-graph の親>/task-execution-report.html")
    p.add_argument(
        "--build-summary", default=None,
        help="最終 verdict/外ループ記録。省略時は task-state と同じ dir の build-summary.json を自動検出",
    )
    p.add_argument(
        "--completion-evidence", default=None,
        help="実測 acceptance 証跡。省略時は task-state と同じ dir の completion-evidence.json を自動検出",
    )
    p.add_argument("--discovered-inbox", default=None, help="未処理の発見タスクを載せる discovered-task inbox dir")
    p.add_argument("--goal-spec", default=None,
                   help="価値セクション (why & value) の source。省略時 <plan_dir>/goal-spec.json を自動検出 (不在なら価値セクション省略)")
    p.add_argument("--inventory", default=None,
                   help="価値セクション capabilities の source。省略時 <plan_dir>/component-inventory.json を自動検出")
    return p


def main(argv: list[str] | None = None) -> int:
    argv = list(sys.argv[1:] if argv is None else argv)
    parser = _build_parser()
    try:
        args = parser.parse_args(argv)
    except SystemExit as exc:
        return int(exc.code) if isinstance(exc.code, int) else 2

    graph_path = Path(args.task_graph)
    state_path = Path(args.task_state) if args.task_state else None
    plan_mode = state_path is None  # task-state 無し = build 前の計画構造レポート
    try:
        graph = _read_json(graph_path)
        task_state = (
            _read_json(state_path) if state_path
            else {"schema_version": "1.0", "graph_hash": None, "nodes": []}
        )
    except (OSError, json.JSONDecodeError) as exc:
        print(f"読込/parse 失敗: {exc}", file=sys.stderr)
        return 2

    build_dir = state_path.parent if state_path else None
    plan_dir = graph_path.parent
    out_json = Path(args.out_json) if args.out_json else plan_dir / "task-graph-status.json"
    out_md = Path(args.out_md) if args.out_md else plan_dir / "task-progress.md"
    out_html = Path(args.out_html) if args.out_html else plan_dir / "task-execution-report.html"
    if args.build_summary:
        build_summary_path: Path | None = Path(args.build_summary)
    elif build_dir:
        candidate = build_dir / "build-summary.json"
        build_summary_path = candidate if candidate.is_file() else None
    else:
        build_summary_path = None
    if args.completion_evidence:
        completion_evidence_path: Path | None = Path(args.completion_evidence)
    elif build_dir:
        candidate = build_dir / "completion-evidence.json"
        completion_evidence_path = candidate if candidate.is_file() else None
    else:
        completion_evidence_path = None
    completion_evidence = _optional_build_summary(completion_evidence_path)
    if completion_evidence is not None and completion_evidence_path is not None:
        completion_evidence["_source_path"] = str(completion_evidence_path)
    discovered = _pending_discovered(Path(args.discovered_inbox)) if args.discovered_inbox else []

    # 価値セクション source: plan dir の goal-spec / component-inventory を read-only 参照 (不在は fail-soft)。
    goal_spec_path = Path(args.goal_spec) if args.goal_spec else plan_dir / "goal-spec.json"
    inventory_path = Path(args.inventory) if args.inventory else plan_dir / "component-inventory.json"
    narrative = _value_narrative(_optional_dict(goal_spec_path), _optional_dict(inventory_path))
    # curated override (任意): <plan_dir>/value-narrative.json があれば非空キーを決定論既定へ
    # 上書き合成する。essential_problem 等「明記されていない本質」の synthesize は判断を要する
    # ため、決定論導出の上に人手 curation を重ねられる二層にする (override 不在なら既定のまま)。
    override = _optional_dict(plan_dir / "value-narrative.json")
    if override:
        base = narrative or {"purpose": None, "background": None, "goal": None,
                             "essential_problem": None, "capabilities": [], "boundaries": []}
        for key, value in override.items():
            if value:
                base[key] = value
        narrative = base

    # 同 plan dir に仕様書ブラウザ (task-specs.html) があれば導線を出す (中身閲覧への往復)。
    spec_browser = plan_dir / "task-specs.html"
    spec_browser_href = spec_browser.name if spec_browser.exists() else None

    status = build_status(graph, task_state, build_dir, discovered, completion_evidence)
    status["route_reports"] = _route_reports(build_dir) if build_dir else []
    status["build_summary"] = _optional_build_summary(build_summary_path)
    status["completion_evidence"] = completion_evidence
    build_gate = status["build_summary"].get("completion_gate") \
        if isinstance(status["build_summary"], dict) else None
    if isinstance(build_gate, dict):
        build_gate = build_gate.get("completion_gate")
    if build_gate == "blocked":
        status["summary"]["completion_gate"] = "blocked"
        status["summary"]["effective_status"] = "blocked"
    elif build_gate == "ok" and status["summary"]["completion_gate"] is None:
        status["summary"]["completion_gate"] = "ok"
    try:
        out_json.parent.mkdir(parents=True, exist_ok=True)
        out_md.parent.mkdir(parents=True, exist_ok=True)
        out_html.parent.mkdir(parents=True, exist_ok=True)
        out_json.write_text(json.dumps(status, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
        out_md.write_text(render_markdown(status, narrative, graph, plan_mode), encoding="utf-8")
        out_html.write_text(render_html(
            status,
            graph,
            html_path=out_html,
            graph_path=graph_path,
            state_path=state_path,
            status_json_path=out_json,
            progress_md_path=out_md,
            build_summary_path=build_summary_path,
            narrative=narrative,
            plan_mode=plan_mode,
            spec_browser_href=spec_browser_href,
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
        "effective_status": status["summary"]["effective_status"],
        "completion_gate": status["summary"]["completion_gate"],
        "discovered_pending": len(discovered),
    }, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    sys.exit(main())
