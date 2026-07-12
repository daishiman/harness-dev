#!/usr/bin/env python3
"""v1 intake.json (sections-based) を v2 render_notion_page.py context (intake-final-schema.json v2) に変換する。

Usage:
  python3 convert_v1_to_v2_context.py <v1_intake.json> <output_v2_context.json>
"""
from __future__ import annotations

import json
import re
import sys
from pathlib import Path
from datetime import datetime


def _str(val) -> str:
    if val is None:
        return ""
    if isinstance(val, list):
        return ", ".join(str(v) for v in val)
    return str(val)


def convert(v1: dict) -> dict:
    s = v1.get("sections", {})
    es = s.get("0_executive_summary", {})
    ac = s.get("1_assumption_challenger", {})
    up = s.get("2_user_profile", {})
    pe = s.get("3_purpose_excavator", {})
    op_sec = s.get("4_option_presenter", {})
    vis = s.get("5_visualizer", {})
    fa = s.get("6_five_axes_summary", {})
    dd = s.get("7_design_decisions", {})
    oq = s.get("8_open_questions", {})
    hc = s.get("9_handoff_contract", {})
    su = s.get("10_self_updater", {})
    ai = s.get("11_artifact_index", {})

    skill_name = v1.get("skill_name_hint", "")
    # スキーマパターン ^[a-z][a-z0-9-]{3,31}$ (最大32文字) に合わせて短縮
    if not re.match(r'^[a-z][a-z0-9-]{3,31}$', skill_name):
        skill_name = skill_name[:32]
        # 末尾ハイフンを除去
        skill_name = skill_name.rstrip('-')
    generated_at = es.get("generated_at", datetime.utcnow().strftime("%Y-%m-%dT%H:%M:%SZ"))
    pattern = es.get("pattern", "A")
    workflow = es.get("workflow_pattern", "A単体")
    depth = es.get("depth", "standard")
    vocab = es.get("vocabulary_tier", "intermediate")
    state = es.get("state", "gate_a_approved")
    score = es.get("value_realized_score", 0)
    handoff_mode_raw = es.get("handoff_mode", "standard")
    # notion_db_properties allows standard; executive_summary enum: fast-track, human-review, draft-only
    if handoff_mode_raw not in ("fast-track", "standard", "human-review", "draft-only"):
        handoff_mode_raw = "standard"
    handoff_mode = handoff_mode_raw
    es_handoff_mode = "human-review" if handoff_mode_raw == "standard" else handoff_mode_raw

    # ---- meta ----
    # required: skill_name_hint, generated_at, pattern_code, depth, vocabulary_tier, status, value_realized_score
    meta = {
        "skill_name_hint": skill_name,
        "generated_at": generated_at,
        "pattern_code": pattern,
        "pattern_label": {"A": "新規", "B": "改修", "C": "統廃合", "D": "廃止", "E": "分割"}.get(pattern, pattern),
        "workflow_pattern_code": workflow,
        "workflow_pattern_label": workflow,
        "depth": depth,
        "depth_minutes": {"light": 15, "standard": 30, "detailed": 60}.get(depth, 30),
        "vocabulary_tier": vocab,
        "status": state,
        "value_realized_score": score,
    }

    # ---- executive_summary ----
    # required: true_purpose, design_choices, handoff_mode
    executive_summary = {
        "true_purpose": es.get("true_purpose_oneliner", ""),
        "purpose_narrative": es.get("true_purpose_oneliner", ""),
        "design_choices": es.get("design_decision_summary", ""),
        "handoff_mode": es_handoff_mode,
        "handoff_note": "",
    }

    # ---- assumption ----
    # required: surface_request, candidates, deep_problem
    candidates_raw = ac.get("deep_candidates", [])
    candidates = [
        {
            "id": c.get("id", f"D{i+1}"),
            "label": c.get("label", c.get("text", "")),
            "adopted": c.get("adopted", False),
        }
        for i, c in enumerate(candidates_raw)
    ]
    assumption = {
        "surface_request": ac.get("surface_request", ""),
        "candidates": candidates,
        "deep_problem": ac.get("adopted_deep_problem", ""),
        "time_freed_intent": ac.get("time_freed_intent", ""),
        "blind_spots": ac.get("blindspots", []),
    }

    # ---- profile ----
    # required: dimensions, vocabulary_tier
    dimensions = up.get("dimensions", [])
    dim_map = {d.get("dim", ""): d for d in dimensions}
    # Fix dimensions: dim->name, mid->medium
    conf_map = {"mid": "medium", "low": "low", "high": "high"}
    dimensions_v2 = []
    for d in dimensions:
        dimensions_v2.append({
            "name": d.get("dim", d.get("name", "")),
            "value": d.get("value", ""),
            "confidence": conf_map.get(d.get("confidence", "medium"), "medium"),
            "evidence": d.get("evidence", ""),
        })
    profile = {
        "dimensions": dimensions_v2,
        "vocabulary_tier": up.get("vocabulary_tier", vocab),
        "implications": up.get("implications_for_next_phase", []),
    }

    # ---- purpose ----
    # required: true_purpose, rounds, techniques_used_str
    techniques = pe.get("techniques_used", [])
    techniques_str = " -> ".join(techniques) if techniques else ""
    output_priority_raw = pe.get("output_priority", [])
    # schema items require: text, is_top
    output_priority = [
        {
            "text": _str(item.get("output", item.get("text", ""))),
            "is_top": bool(item.get("mandatory", item.get("is_top", False))),
        }
        for item in output_priority_raw
    ]
    purpose = {
        "true_purpose": pe.get("true_purpose", ""),
        "rounds": pe.get("rounds", 1),
        "techniques_used_str": techniques_str,
        "agreement_loop_detected": pe.get("agreement_loop_detected", False),
        "underlying_motivation": pe.get("underlying_motivation", ""),
        "differentiation_title": "",
        "differentiation_text": pe.get("differentiation", ""),
        "output_priority": output_priority,
    }

    # ---- options ----
    # required: groups, connectors (connectors required: input_sources, knowledge_assets, outputs, scheduler)
    conn_raw = op_sec.get("connectors", {})
    connectors = {
        "input_sources": _str(conn_raw.get("input_sources", "")),
        "knowledge_assets": _str(conn_raw.get("knowledge_assets", "")),
        "outputs": _str(conn_raw.get("outputs", "")),
        "scheduler": _str(conn_raw.get("scheduler", "on-demand")),
    }
    decision_tables = op_sec.get("decision_tables", [])
    def _normalize_option_id(raw_id: str, idx: int) -> str:
        """^[A-Z][0-9]+$ に正規化。例: Q4-A -> A1 (prefix + sequential)"""
        # If already matches, return as-is
        if re.match(r'^[A-Z][0-9]+$', raw_id or ''):
            return raw_id
        # Extract prefix letter and make sequential
        # Use group prefix letter (first letter of raw_id that is alpha)
        prefix = 'O'
        for ch in (raw_id or 'O'):
            if ch.isalpha() and ch.isupper():
                prefix = ch
                break
        return f'{prefix}{idx + 1}'

    groups = []
    for dt in decision_tables:
        raw_opts = dt.get("options", [])
        adopted_raw = dt.get("adopted_id", "")
        # Normalize option ids and track adopted mapping
        id_map: dict[str, str] = {}
        norm_opts = []
        for idx, opt in enumerate(raw_opts):
            raw_id = opt.get("id", f"O{idx+1}")
            norm_id = _normalize_option_id(raw_id, idx)
            id_map[raw_id] = norm_id
            weight_raw = opt.get("weight", "中")
            if weight_raw not in ("軽", "中", "重"):
                weight_raw = "中"
            norm_opts.append({
                "id": norm_id,
                "label": opt.get("label", ""),
                "pro": opt.get("pro", ""),
                "con": opt.get("con", ""),
                "weight": weight_raw,
                "adopted": bool(opt.get("adopted", False)),
            })
        # Normalize adopted id
        adopted_norm = id_map.get(adopted_raw, adopted_raw)
        groups.append({
            "title": dt.get("axis", dt.get("label", dt.get("title", ""))),
            "options": norm_opts,
            "adopted": adopted_norm,
        })
    options = {
        "groups": groups,
        "connectors": connectors,
    }

    # ---- figures ----
    # required: entries, mandatory_rules_check
    figures_raw_orig = vis.get("figures", [])
    # Normalize figures entries: mermaid_source -> mermaid
    figures_raw = []
    for fig in figures_raw_orig:
        entry = dict(fig)
        if "mermaid_source" in entry and "mermaid" not in entry:
            entry["mermaid"] = entry.pop("mermaid_source")
        # title, one_liner, mermaid, legend are required
        entry.setdefault("title", "")
        entry.setdefault("one_liner", "")
        entry.setdefault("mermaid", "")
        entry.setdefault("legend", "")
        figures_raw.append(entry)
    rules_check_raw = vis.get("rules_check", {})
    if isinstance(rules_check_raw, dict):
        mandatory_rules_check = [{"text": k, "passed": bool(v)} for k, v in rules_check_raw.items()]
    elif isinstance(rules_check_raw, list):
        # normalize list items to {text, passed}
        mandatory_rules_check = []
        for item in rules_check_raw:
            if isinstance(item, dict):
                mandatory_rules_check.append({
                    "text": item.get("text", item.get("rule", str(item))),
                    "passed": bool(item.get("passed", item.get("result", True))),
                })
            else:
                mandatory_rules_check.append({"text": str(item), "passed": True})
    else:
        mandatory_rules_check = []
    figures = {
        "entries": figures_raw,
        "mandatory_rules_check": mandatory_rules_check,
    }

    # ---- five_axes ----
    # required: rows, pipeline (pipeline required: ingest, analysis, storage, retrieval, update)
    axes_raw = fa.get("axes", [])
    axes_obj = {a.get("axis_id", a.get("axis", "")): a for a in axes_raw}
    kp = fa.get("knowledge_pipeline", {})
    update_raw = _str(kp.get("update", "on-demand"))
    if update_raw not in ("daily", "weekly", "monthly", "on-demand"):
        update_raw = "on-demand"
    pipeline = {
        "ingest": _str(kp.get("ingest", "")),
        "analysis": _str(kp.get("analysis", "")),
        "storage": _str(kp.get("storage", "")),
        "retrieval": _str(kp.get("retrieval", "")),
        "update": update_raw,
    }
    # five_axes.rows: axis_id->name mapping, answer->content, depth enum fix
    axis_name_map = {
        "output_to": "出力先",
        "input_from": "情報源",
        "share_target": "共有相手",
        "real_problem": "真の課題",
        "knowledge_asset": "ナレッジ資産",
        # legacy aliases
        "output": "出力先",
        "input": "情報源",
        "recipient": "共有相手",
        "purpose": "真の課題",
        "knowledge": "ナレッジ資産",
    }
    depth_norm = {"light": "shallow", "shallow": "shallow", "standard": "standard", "detailed": "deep", "deep": "deep"}
    axes_rows = []
    for a in axes_raw:
        axis_id = a.get("axis_id", a.get("axis", ""))
        name = axis_name_map.get(axis_id, axis_id)
        content = a.get("answer", a.get("content", ""))
        depth_val = depth_norm.get(a.get("depth", "standard"), "standard")
        axes_rows.append({"name": name, "content": content, "depth": depth_val})
    five_axes = {
        "rows": axes_rows,
        "pipeline": pipeline,
    }

    # ---- design_decisions ----
    # required: rows, output_priority
    adoptions_raw = dd.get("adoptions", [])
    adoptions = []
    for a in adoptions_raw:
        adoptions.append({
            "axis": a.get("axis", ""),
            "adopted": a.get("adopted_id", a.get("adopted", "")),
            "reason": a.get("reason_one_liner", a.get("reason", "")),
        })
    dd_output_priority_raw = dd.get("output_priority_finalized", output_priority_raw)
    # design_decisions.output_priority items are strings
    dd_output_priority = [
        _str(item.get("output", item.get("text", item if isinstance(item, str) else "")))
        for item in dd_output_priority_raw
    ]
    design_decisions = {
        "rows": adoptions,
        "output_priority": dd_output_priority,
    }

    # ---- open_questions ----
    # items require: question, blocking, defer_to
    oq_raw = oq.get("questions", [])
    open_questions = [
        {
            "question": q.get("q", q.get("question", "")),
            "blocking": q.get("blocking", False),
            "defer_to": q.get("defer_to", ""),
        }
        for q in oq_raw
    ]

    # ---- handoff ----
    # required: recommended_mode, skip_to_phase, reason
    rec = hc.get("recommended_next", {})
    handoff = {
        "recommended_mode": rec.get("mode", handoff_mode),
        "skip_to_phase": rec.get("skip_to_phase", "Phase 1"),
        "reason": rec.get("reason", ""),
        "intake_json_path": hc.get("intake_json_path", ""),
        "starting_command": hc.get("starting_command", ""),
    }

    # ---- self_update ----
    # required: candidates_detected, candidates_applied, skipped_duplicates, value_realized_score
    su_metrics = su.get("metrics", {})
    self_update = {
        "candidates_detected": su_metrics.get("candidates_detected", 0),
        "candidates_applied": su_metrics.get("candidates_applied", 0),
        "skipped_duplicates": su_metrics.get("skipped_duplicates", 0),
        "value_realized_score": su_metrics.get("value_realized_score_estimate", score),
        "score_rationale": su.get("score_rationale", ""),
        "deductions": su.get("deductions", []),
        "question_bank_additions": su.get("question_bank_additions", []),
        "session_observations": su.get("session_observations", []),
    }

    # ---- artifacts ----
    # required: base_path, files
    ai_items = ai.get("artifacts", [])
    artifacts = {
        "base_path": ai.get("base_path", ""),
        "files": [
            {
                "path": a.get("path", ""),
                "description": a.get("role_one_liner", a.get("description", "")),
            }
            for a in ai_items
        ],
    }

    # ---- section_diagrams ----
    # 5_visualizer は schema の additionalProperties:false により禁止。空 dict で OK。
    section_diagrams: dict = {}

    # ---- notion_db_properties ----
    # required: 名前, ステータス, パターン, ワークフロー, 深度, 熟練度, テーマ抽出,
    #           責務境界, 配信タイミング, 出力先, 共有相手, 引き渡しモード, 真の課題, 実行環境, 作成日
    output_axis = axes_obj.get("output_to", axes_obj.get("output", {}))
    output_dest_raw = output_axis.get("answer", "") if output_axis else ""
    output_dest = [opt for opt in ["Obsidian", "Discord", "Slack", "Notion", "X", "Email"] if opt in output_dest_raw]
    if not output_dest:
        output_dest = ["Slack"]

    sharing_raw = dim_map.get("sharing_intent", {}).get("value", "")
    sharing = [opt for opt in ["自分", "Xフォロワー", "クライアント", "受講生", "チーム"] if opt in sharing_raw]
    if not sharing:
        sharing = ["クライアント"]

    kp_str = json.dumps(kp, ensure_ascii=False)
    knowledge_tags = [tag for tag in ["思考プロセス", "暗黙知", "判断基準", "テンプレ", "チェックリスト"] if tag in kp_str]
    if not knowledge_tags:
        knowledge_tags = ["思考プロセス", "判断基準"]

    true_problem_text = ac.get("adopted_deep_problem", "")[:200]

    notion_db_properties = {
        "名前": skill_name,
        "ステータス": "下書き",
        "パターン": pattern,
        "ワークフロー": "A 単体",
        "深度": depth if depth in ["light", "standard", "detailed"] else "standard",
        "熟練度": "中級",
        "テーマ抽出": "",
        "責務境界": "",
        "配信タイミング": "",
        "出力先": output_dest,
        "共有相手": sharing,
        "引き渡しモード": handoff_mode,
        "真の課題": true_problem_text,
        "ナレッジ資産タグ": knowledge_tags,
        "実行環境": "Claude Code",
        "作成日": generated_at,
    }

    # ---- legacy compatibility for quality_gate.py validate_intake / check_completeness ----
    # These use five_axes.rows but also need flat 5_axes dict and user_profile
    axis_name_to_key = {
        "出力先": "output_target",
        "情報源": "info_source",
        "共有相手": "share_target",
        "真の課題": "true_problem",
        "ナレッジ資産": "knowledge_assets",
    }
    five_axes_flat: dict = {}
    for row in axes_rows:
        key = axis_name_to_key.get(row.get("name", ""))
        if key:
            five_axes_flat[key] = row.get("content", "")
    user_profile = {d.get("name", ""): d.get("value", "") for d in dimensions_v2}

    return {
        "meta": meta,
        "executive_summary": executive_summary,
        "assumption": assumption,
        "profile": profile,
        "purpose": purpose,
        "options": options,
        "figures": figures,
        "five_axes": five_axes,
        "design_decisions": design_decisions,
        "open_questions": open_questions,
        "handoff": handoff,
        "self_update": self_update,
        "artifacts": artifacts,
        "section_diagrams": section_diagrams,
        "notion_db_properties": notion_db_properties,
        "5_axes": five_axes_flat,
        "user_profile": user_profile,
    }


def main(argv: list[str]) -> int:
    if len(argv) < 3:
        print("Usage: convert_v1_to_v2_context.py <v1_intake.json> <output_v2.json>", file=sys.stderr)
        return 2
    src = Path(argv[1]).resolve()
    dst = Path(argv[2]).resolve()
    if not src.exists():
        print(f"ERROR: not found: {src}", file=sys.stderr)
        return 2
    v1 = json.loads(src.read_text(encoding="utf-8"))
    v2 = convert(v1)
    dst.parent.mkdir(parents=True, exist_ok=True)
    dst.write_text(json.dumps(v2, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(f"OK: v2 context written to {dst}", file=sys.stderr)
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv))
