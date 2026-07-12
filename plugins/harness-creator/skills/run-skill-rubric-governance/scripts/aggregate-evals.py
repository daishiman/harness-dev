#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""aggregate-evals.py

SessionEnd hook から発火し、plugins/harness-creator/EVALS.json を集計する。
閾値超え変動 (連続 FAIL / 平均スコア低下) を検出したら
run-skill-rubric-governance/proposals/ に rubric-update 提案ドラフトを書き出す。

副作用境界:
    - proposals/ ディレクトリへの書き込みのみ。git は触らない。

exit_code 仕様 (Claude Code Hooks 準拠):
    0  非ブロック (正常 / 提案不要 / 提案書き込み成功)
    2  明示拒否 (本 hook は使用しない)
    その他 非ブロック警告

閾値:
    - 同一 rubric_id (skill) で直近 3 連続 verdict=FAIL
    - 同一 rubric_id の平均スコアが直近窓で 0.1 以上低下
    - 同一 rubric_id で直近窓 (6件) 中 2 レコード以上が苦戦シグナルを示す
      (iterations>=2 / negative_feedback>=2件 / findings>=3件 のいずれか)
"""

from __future__ import annotations

import datetime as _dt
import json
import os
import re
import sys
from collections import Counter, defaultdict
from pathlib import Path
from typing import Any

_CONSECUTIVE_FAIL_THRESHOLD = 3
_SCORE_DROP_THRESHOLD = 0.1
_RECENT_WINDOW = 5  # 直近窓

# 苦戦密度 (friction_density) 閾値。
# CI は PASS verdict のみ commit を許すため、FAIL 系列に依存する上記 2 条件は
# 入力が構造的に空集合となり発火し得ない。committed PASS verdict に既に埋まる
# 摩擦データ (再評価 iterations / negative_feedback / findings 件数) を第 3 の
# 発火条件にする。単独レビューアの軽微な摩擦 (iterations=1 かつ negative 1 件)
# では発火せず、同一 skill の直近窓で複数レコードの摩擦が裏付け合う場合のみ
# 発火する (オオカミ少年回避を最優先した保守設計)。
_FRICTION_ITERATIONS_MIN = 2  # 再評価ループが必要だった (上限は max_iterations=3)
_FRICTION_NEGATIVE_MIN = 2  # 1 レコードの negative_feedback が 2 件以上
_FRICTION_FINDINGS_MIN = 3  # 1 レコードの findings が 3 件以上 (score.jsonl 系)
_FRICTION_MIN_RECORDS = 2  # 直近窓内で摩擦レコード 2 件以上 (相互裏付け)
_FRICTION_RECENT_WINDOW = 6  # 苦戦密度の直近窓


def _plugin_root() -> Path:
    # 本ファイル: plugins/harness-creator/skills/run-skill-rubric-governance/scripts/
    env = os.environ.get("CLAUDE_PLUGIN_ROOT")
    if env:
        return Path(env).resolve()
    return Path(__file__).resolve().parents[3]


def _state_fallback_root() -> Path:
    """plugin-root が書込不能な install (read-only / 次回 update で消失) 用の退避先。

    手本: notifier-check.py の `Path.home()/.cache/harness` (user 領域退避)。
    優先順: $CLAUDE_PROJECT_DIR → $XDG_STATE_HOME → ~/.claude/state。
    """
    project = os.environ.get("CLAUDE_PROJECT_DIR")
    if project:
        return Path(project) / ".claude" / "state" / "harness-creator"
    xdg = os.environ.get("XDG_STATE_HOME")
    base = Path(xdg) if xdg else Path.home() / ".claude" / "state"
    return base / "harness-creator"


def _dir_is_writable(d: Path) -> bool:
    """d (存在しなければ最寄りの既存祖先) が書込可能かを実 mkdir せず判定。"""
    probe = d
    while not probe.exists():
        if probe.parent == probe:
            return False
        probe = probe.parent
    return os.access(probe, os.W_OK)


def _repo_root() -> Path:
    # _plugin_root() == <repo>/plugins/harness-creator なので parent.parent が repo root。
    return _plugin_root().parent.parent


def _eval_log_dir() -> Path:
    # write-eval-log.py の sink 基底と一致: <repo>/eval-log/
    return _repo_root() / "eval-log"


def _evals_path() -> Path:
    return _plugin_root() / "EVALS.json"


def _proposals_dir() -> Path:
    """rubric-update 提案ドラフトの書込先。env override > plugin-root (既定)。

    既定を plugin-root 配下に保つことで maintainer の読取フロー (proposals/ 直読み)
    を壊さない。read-only install での fallback は呼び出し側 (main) が担う。
    """
    override = os.environ.get("HARNESS_CREATOR_PROPOSALS_DIR")
    if override:
        return Path(override).resolve()
    return (
        _plugin_root()
        / "skills"
        / "run-skill-rubric-governance"
        / "proposals"
    )


def _candidate_proposals_dirs() -> list[Path]:
    """書込先候補を優先順で返す (3 段 fallback)。

    (a) 既定 = plugin-root 配下 proposals/ (dev 既存挙動・maintainer 読取互換)
    (b) plugin-root が書込不能なら user state 領域へ退避
    env override 明示時はそれを単独で使う。
    """
    if os.environ.get("HARNESS_CREATOR_PROPOSALS_DIR"):
        return [_proposals_dir()]
    return [_proposals_dir(), _state_fallback_root() / "proposals"]


def _date_of(ts: Any) -> str | None:
    # "2026-06-06T19:59:43+0900" / "2026-06-01T00:00:00Z" -> "2026-06-06"
    if not isinstance(ts, str) or not ts:
        return None
    m = re.match(r"(\d{4}-\d{2}-\d{2})", ts)
    return m.group(1) if m else None


def _normalize_score_record(rec: dict[str, Any]) -> dict[str, Any] | None:
    """write-eval-log.py の score.jsonl 1行を共通形へ。

    sink schema: rubric{rubric_id,...} / score / passed / findings / skill_name / timestamp
    -> {skill, date, verdict, score, findings}
    """
    if not isinstance(rec, dict):
        return None
    rubric = rec.get("rubric") if isinstance(rec.get("rubric"), dict) else {}
    skill = rec.get("skill_name") or rubric.get("rubric_id")
    if not skill:
        return None
    passed = rec.get("passed")
    if passed is True:
        verdict = "PASS"
    elif passed is False:
        verdict = "FAIL"
    else:
        verdict = str(rec.get("verdict", ""))
    return {
        "skill": skill,
        "date": _date_of(rec.get("timestamp")),
        "verdict": verdict,
        "score": rec.get("score"),
        "findings": rec.get("findings", []) or [],
    }


def _normalize_verdict_record(rec: dict[str, Any]) -> dict[str, Any] | None:
    """content-review verdict.json を共通形へ。

    verdict schema: target{plugin,skill} / verdict(PASS|FAIL|INCOMPLETE) / reviewed_at
                    / iterations / feedback_loop{negative_feedback[]}
    -> {skill, date, verdict, score, findings, iterations, negative_feedback_count}

    iterations / negative_feedback は PASS verdict にも残る摩擦シグナルで、
    friction_density 検出の入力になる (PASS-only commit 制約下の唯一の負情報)。
    """
    if not isinstance(rec, dict):
        return None
    target = rec.get("target") if isinstance(rec.get("target"), dict) else {}
    skill = target.get("skill")
    if not skill:
        return None
    feedback = rec.get("feedback_loop") if isinstance(rec.get("feedback_loop"), dict) else {}
    negative = feedback.get("negative_feedback")
    return {
        "skill": skill,
        "date": _date_of(rec.get("reviewed_at")),
        "verdict": str(rec.get("verdict", "")),
        "score": None,  # verdict は数値スコアを持たない
        "findings": [],
        "iterations": rec.get("iterations"),
        "negative_feedback_count": len(negative) if isinstance(negative, list) else 0,
    }


def _load_score_jsonl() -> list[dict[str, Any]]:
    """eval-log/<plugin>/<date>-score.jsonl (write-eval-log の実 sink) を全件読む。"""
    out: list[dict[str, Any]] = []
    base = _eval_log_dir()
    if not base.exists():
        return out
    try:
        paths = sorted(base.glob("**/*-score.jsonl"))
    except OSError:
        return out
    for path in paths:
        try:
            text = path.read_text(encoding="utf-8")
        except OSError:
            continue
        for line in text.splitlines():
            line = line.strip()
            if not line:
                continue
            try:
                rec = json.loads(line)
            except json.JSONDecodeError:
                continue
            norm = _normalize_score_record(rec)
            if norm is not None:
                out.append(norm)
    return out


def _normalize_live_trial_record(rec: dict[str, Any], run_id: str = "") -> dict[str, Any] | None:
    """live-trial verdict.json (D10 runtime-evidence 契約) を共通形へ。

    verdict schema: target_skill("plugin:skill") / overall{verdict: PASS|DEGRADED|FAIL|BLOCKED}
                    / goal_verdict{blockers[]} / nudge_count / gate_response_count
    -> {skill, date, verdict, score, findings, negative_feedback_count}

    timestamp フィールドを持たないため date は run-id 先頭の YYYYMMDD から復元する。
    score は構造的に存在しない (goal 判定は PASS|FAIL のみ・点数出力禁止)。
    nudge / gate 応答は「自走できず介入を要した」負シグナルなので
    negative_feedback_count へ合算し friction_density の入力に載せる。
    goal_verdict.blockers は findings として finding カテゴリ集計へ流す。
    """
    if not isinstance(rec, dict):
        return None
    target = rec.get("target_skill")
    if not isinstance(target, str) or not target:
        return None
    skill = target.rsplit(":", 1)[-1]
    if not skill:
        return None
    overall = rec.get("overall") if isinstance(rec.get("overall"), dict) else {}
    goal = rec.get("goal_verdict") if isinstance(rec.get("goal_verdict"), dict) else {}
    blockers = goal.get("blockers")
    nudge = rec.get("nudge_count")
    gate = rec.get("gate_response_count")
    intervention = (nudge if isinstance(nudge, int) else 0) + (
        gate if isinstance(gate, int) else 0
    )
    m = re.match(r"(\d{4})(\d{2})(\d{2})", str(run_id))
    return {
        "skill": skill,
        "date": f"{m.group(1)}-{m.group(2)}-{m.group(3)}" if m else None,
        "verdict": str(overall.get("verdict", "")),
        "score": None,
        "findings": [b for b in blockers if isinstance(b, str)] if isinstance(blockers, list) else [],
        "negative_feedback_count": intervention,
    }


def _load_content_review_verdicts() -> list[dict[str, Any]]:
    """eval-log/<plugin>/<skill>/content-review/*-verdict.json を全件読む。"""
    out: list[dict[str, Any]] = []
    base = _eval_log_dir()
    if not base.exists():
        return out
    try:
        paths = sorted(base.glob("**/content-review/*-verdict.json"))
    except OSError:
        return out
    for path in paths:
        try:
            rec = json.loads(path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            continue
        norm = _normalize_verdict_record(rec)
        if norm is not None:
            out.append(norm)
    return out


def _load_live_trial_verdicts() -> list[dict[str, Any]]:
    """eval-log/<plugin>/<skill>/live-trial/<run-id>/verdict.json (Gate D 実走証拠) を全件読む。"""
    out: list[dict[str, Any]] = []
    base = _eval_log_dir()
    if not base.exists():
        return out
    try:
        paths = sorted(base.glob("*/*/live-trial/*/verdict.json"))
    except OSError:
        return out
    for path in paths:
        try:
            rec = json.loads(path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            continue
        norm = _normalize_live_trial_record(rec, run_id=path.parent.name)
        if norm is not None:
            out.append(norm)
    return out


def _load_evals() -> dict[str, Any]:
    """評価レコードを 4 ソースから集約。

    1) EVALS.json#/evaluations[]   (従来。誰も書かない可能性が高い旧経路)
    2) eval-log/<plugin>/<date>-score.jsonl       (write-eval-log の実 sink)
    3) eval-log/<plugin>/<skill>/content-review/*-verdict.json  (content-review verdict)
    4) eval-log/<plugin>/<skill>/live-trial/<run-id>/verdict.json  (live-trial 実走証拠, D10)

    いずれも {skill,date,verdict,score,findings} 形へ正規化済みで concat する。
    新 writer は作らず既存 writer の出力を読むだけ (重複writer回避)。
    各ソースは防御的に skip (無ければ空)。
    """
    evals: list[dict[str, Any]] = []

    # 1) 従来 EVALS.json
    p = _evals_path()
    if p.exists():
        try:
            data = json.loads(p.read_text(encoding="utf-8"))
            for ev in data.get("evaluations", []) or []:
                if isinstance(ev, dict):
                    evals.append(ev)
        except (OSError, json.JSONDecodeError) as exc:
            sys.stderr.write(f"[aggregate-evals] EVALS.json load failed: {exc}\n")

    # 2) write-eval-log の実 sink (score.jsonl)
    try:
        evals.extend(_load_score_jsonl())
    except Exception as exc:  # 非ブロック (SessionEnd 流儀)
        sys.stderr.write(f"[aggregate-evals] score.jsonl load failed: {exc}\n")

    # 3) content-review verdict
    try:
        evals.extend(_load_content_review_verdicts())
    except Exception as exc:  # 非ブロック
        sys.stderr.write(f"[aggregate-evals] verdict load failed: {exc}\n")

    # 4) live-trial verdict (実走 acceptance 証拠)
    try:
        evals.extend(_load_live_trial_verdicts())
    except Exception as exc:  # 非ブロック
        sys.stderr.write(f"[aggregate-evals] live-trial verdict load failed: {exc}\n")

    return {"evaluations": evals}


def _verdict_is_fail(verdict: str) -> bool:
    return verdict.upper() in {"FAIL", "FAILED", "REJECT", "REJECTED"}


def _score_of(ev: dict[str, Any]) -> float | None:
    # score / overall / mean 等が来る可能性に備える。
    for k in ("score", "overall", "mean_score", "average"):
        v = ev.get(k)
        if isinstance(v, (int, float)):
            return float(v)
    return None


def _is_friction(ev: dict[str, Any]) -> bool:
    """1 レコードが苦戦シグナルを含むか (EVALS.json 旧形式はフィールド欠落 = 非該当)。"""
    iterations = ev.get("iterations")
    if isinstance(iterations, int) and iterations >= _FRICTION_ITERATIONS_MIN:
        return True
    negative = ev.get("negative_feedback_count")
    if isinstance(negative, int) and negative >= _FRICTION_NEGATIVE_MIN:
        return True
    findings = ev.get("findings")
    return isinstance(findings, list) and len(findings) >= _FRICTION_FINDINGS_MIN


def _detect_anomalies(evals: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """rubric_id (= skill) 単位で異常を検出。"""
    grouped: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for ev in evals:
        sk = ev.get("skill") or ev.get("rubric_id")
        if not sk:
            continue
        grouped[sk].append(ev)

    anomalies: list[dict[str, Any]] = []
    for rubric_id, items in grouped.items():
        # date 昇順で安定ソート (欠損は末尾)。
        items_sorted = sorted(items, key=lambda x: x.get("date") or "")
        # 1) 連続 FAIL
        tail = items_sorted[-_CONSECUTIVE_FAIL_THRESHOLD:]
        if len(tail) >= _CONSECUTIVE_FAIL_THRESHOLD and all(
            _verdict_is_fail(str(x.get("verdict", ""))) for x in tail
        ):
            anomalies.append(
                {
                    "rubric_id": rubric_id,
                    "kind": "consecutive_fail",
                    "count": _CONSECUTIVE_FAIL_THRESHOLD,
                    "evidence_dates": [x.get("date") for x in tail],
                }
            )
        # 2) 平均スコア低下 (直近窓 vs それ以前)。
        scores = [(x.get("date"), _score_of(x)) for x in items_sorted]
        scored = [(d, s) for d, s in scores if s is not None]
        if len(scored) >= _RECENT_WINDOW + 1:
            recent = [s for _, s in scored[-_RECENT_WINDOW:]]
            prior = [s for _, s in scored[:-_RECENT_WINDOW]]
            if recent and prior:
                drop = (sum(prior) / len(prior)) - (sum(recent) / len(recent))
                if drop >= _SCORE_DROP_THRESHOLD:
                    anomalies.append(
                        {
                            "rubric_id": rubric_id,
                            "kind": "score_drop",
                            "drop": round(drop, 3),
                            "recent_mean": round(sum(recent) / len(recent), 3),
                            "prior_mean": round(sum(prior) / len(prior), 3),
                        }
                    )
        # 3) 苦戦密度 (PASS verdict 内の摩擦シグナル。FAIL 非依存の第 3 条件)。
        recent_records = items_sorted[-_FRICTION_RECENT_WINDOW:]
        friction_records = [x for x in recent_records if _is_friction(x)]
        if len(friction_records) >= _FRICTION_MIN_RECORDS:
            anomalies.append(
                {
                    "rubric_id": rubric_id,
                    "kind": "friction_density",
                    "friction_records": len(friction_records),
                    "window": len(recent_records),
                    "evidence": [
                        {
                            "date": x.get("date"),
                            "iterations": x.get("iterations"),
                            "negative_feedback_count": x.get("negative_feedback_count"),
                            "findings_count": len(x.get("findings") or []),
                        }
                        for x in friction_records
                    ],
                }
            )
    return anomalies


def _top_finding_categories(evals: list[dict[str, Any]]) -> list[tuple[str, int]]:
    counter: Counter[str] = Counter()
    for ev in evals:
        for f in ev.get("findings", []) or []:
            cat = None
            if isinstance(f, dict):
                cat = f.get("category") or f.get("rule") or f.get("kind")
            elif isinstance(f, str):
                cat = f
            if cat:
                counter[str(cat)] += 1
    return counter.most_common(5)


def _slugify(s: str) -> str:
    s = re.sub(r"[^a-zA-Z0-9]+", "-", s.lower()).strip("-")
    return s or "rubric"


def _render_proposal(
    anomalies: list[dict[str, Any]],
    top_findings: list[tuple[str, int]],
    summary: dict[str, Any],
) -> str:
    today = _dt.date.today().isoformat()
    lines = [
        "---",
        f"date: {today}",
        "kind: rubric-update-proposal",
        "status: draft",
        f"trigger: aggregate-evals (SessionEnd)",
        "---",
        "",
        "# rubric 更新提案 (自動生成ドラフト)",
        "",
        "## 集計サマリ",
        "",
        f"- 評価件数: {summary.get('total', 0)}",
        f"- FAIL 率: {summary.get('fail_rate', 0.0):.2%}",
        f"- 平均スコア: {summary.get('mean_score', 'n/a')}",
        "",
        "## 検出された異常",
        "",
    ]
    if not anomalies:
        lines.append("- (なし)")
    else:
        for a in anomalies:
            lines.append(f"- **{a['rubric_id']}**: {a['kind']} — {json.dumps({k: v for k, v in a.items() if k not in ('rubric_id','kind')}, ensure_ascii=False)}")
    lines += ["", "## 主要 finding カテゴリ (top5)", ""]
    if not top_findings:
        lines.append("- (なし)")
    else:
        for cat, n in top_findings:
            lines.append(f"- {cat}: {n} 件")
    lines += [
        "",
        "## 提案アクション (要 human review)",
        "",
        "- 該当 rubric_id の閾値 / 観点を見直し",
        "- 主要 finding カテゴリに対応する評価項目を新設または重み調整",
        "- 関連する run-* / assign-* Skill の templates を更新",
        "",
        "## 備考",
        "",
        "本ドラフトは aggregate-evals.py により自動生成された。PR 起票は別工程。",
        "",
    ]
    return "\n".join(lines)


def _compute_summary(evals: list[dict[str, Any]]) -> dict[str, Any]:
    total = len(evals)
    fails = sum(1 for e in evals if _verdict_is_fail(str(e.get("verdict", ""))))
    scores = [_score_of(e) for e in evals]
    scores = [s for s in scores if s is not None]
    return {
        "total": total,
        "fail_rate": (fails / total) if total else 0.0,
        "mean_score": round(sum(scores) / len(scores), 3) if scores else "n/a",
    }


def main() -> int:
    # stdin は SessionEnd hook payload。本 script では使わないが drain しておく。
    try:
        sys.stdin.read()
    except Exception:
        pass

    data = _load_evals()
    evals = data.get("evaluations", []) or []
    if not evals:
        return 0

    anomalies = _detect_anomalies(evals)
    if not anomalies:
        return 0

    summary = _compute_summary(evals)
    top_findings = _top_finding_categories(evals)
    proposal = _render_proposal(anomalies, top_findings, summary)

    today = _dt.date.today().isoformat()
    filename = f"{today}-rubric-update.md"

    # 3 段 fallback: 書込可能な最初の候補へ。全滅なら (c) silent no-op exit 0。
    # 同日複数発火に備え、内容ハッシュではなく単純な upsert (上書き) でドラフトを更新。
    last_exc: OSError | None = None
    for out_dir in _candidate_proposals_dirs():
        if not _dir_is_writable(out_dir):
            continue
        try:
            out_dir.mkdir(parents=True, exist_ok=True)
            target = out_dir / filename
            target.write_text(proposal, encoding="utf-8")
            sys.stderr.write(f"[aggregate-evals] proposal -> {target}\n")
            return 0
        except OSError as exc:
            last_exc = exc
            continue
    # どこにも書けない (read-only install 等): クラッシュさせず no-op で握る。
    if last_exc is not None:
        sys.stderr.write(f"[aggregate-evals] no writable sink, skipped: {last_exc}\n")
    else:
        sys.stderr.write("[aggregate-evals] no writable sink, skipped\n")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
