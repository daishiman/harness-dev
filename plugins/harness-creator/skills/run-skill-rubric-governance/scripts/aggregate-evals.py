#!/usr/bin/env python3
# -*- coding: utf-8 -*-
# /// script
# name: aggregate-evals
# version: 0.2.1
# purpose: SessionEnd hook で評価の記録を集計し、連続 FAIL・平均スコアの低下・苦戦の重なりを見つけたら rubric 改正の提案ドラフトを plugin の外の state に書く
# inputs:
#   - stdin: SessionEnd hook の payload（使わずに読み捨てる）
#   - argv: 無ければ SessionEnd hook の経路。--list-proposals（書かずに、自動ドラフトと手書きの提案の両方の置き場を一覧する。CLAUDE_PROJECT_DIR が無ければ cwd と git の作業ツリーの root を project とみなして読む）。ほかの引数は受けない（--help は usage を出す）
#   - files: plugins/harness-creator/EVALS.json、eval-log/**/*-score.jsonl、eval-log/**/content-review/*-verdict.json、eval-log/*/*/live-trial/*/verdict.json
#   - env: HC_ROOT・CLAUDE_PLUGIN_ROOT（plugin root）、HARNESS_CREATOR_PROPOSALS_DIR（書き込み先の明示）、CLAUDE_PROJECT_DIR（既定の書き込み先。--list-proposals では読む先）、XDG_STATE_HOME（書けないときの退避先）
# outputs:
#   - file: $CLAUDE_PROJECT_DIR/.claude/state/harness-creator/proposals/<date>-rubric-update.md（同じ日は上書き。書けなければ退避先へ、どこにも書けなければ書かない。plugin のツリーには書かない）
#   - stdout: --list-proposals のときだけ、置き場と提案の一覧の JSON（--help のときは usage）
#   - stderr: 書いた先 / 読めなかった記録 / 書けなかった理由 / --list-proposals で project を推し量ったこと / 引数の誤り
#   - exit: 0（hook を止めない。提案が要らないとき・書けないときも 0）/ 2（--list-proposals 以外の引数。hook は引数を渡さないので、hook の経路では返さない）
# requires-python: ">=3.9"
# dependencies: []
# contexts: [D]
# network: false
# write-scope: output-dir（state の proposals/ の提案ドラフトだけ。plugin のツリーと git は触らない）
# ///
"""aggregate-evals.py

SessionEnd hook から発火し、plugins/harness-creator/EVALS.json を集計する。
閾値超え変動 (連続 FAIL / 平均スコア低下) を検出したら
$CLAUDE_PROJECT_DIR/.claude/state/harness-creator/proposals/ に rubric-update 提案ドラフトを書き出す。

副作用境界:
    - state の proposals/ ディレクトリへの書き込みのみ。git は触らない。
    - plugin のツリー (run-skill-rubric-governance/proposals/) には書かない。そこは手書きの
      提案が tracked で残る置き場で、読むだけにする。書くと配布物に生成物が混ざり、
      session を終えるたびに plugin の fingerprint が動く。

exit_code 仕様 (Claude Code Hooks 準拠):
    0  非ブロック (正常 / 提案不要 / 提案書き込み成功)
    2  明示拒否 (hook の経路では使わない。手で流したときの引数の誤りに argparse が返す)
    その他 非ブロック警告

閾値:
    - 同一 rubric_id (skill) で直近 3 連続 verdict=FAIL
    - 同一 rubric_id の平均スコアが直近窓で 0.1 以上低下
    - 同一 rubric_id で直近窓 (6件) 中 2 レコード以上が苦戦シグナルを示す
      (iterations>=2 / negative_feedback>=2件 / findings>=3件 のいずれか)
"""

from __future__ import annotations

import argparse
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
# 直近窓内で摩擦レコード 2 件以上 (相互裏付け)。この「裏付け」が成立するのは
# 1 レビュー = 1 レコードが保証されている場合だけで、content-review の 2 ファイル投影を
# そのまま数えていた頃は自分自身のコピーで満たされ実質 >= 1 に退化していた。
# 畳み込みは _load_content_review_verdicts 側の責務。ここを上げて対処してはいけない
# (投影の数が変わればまた壊れる)。
_FRICTION_MIN_RECORDS = 2
_FRICTION_RECENT_WINDOW = 6  # 苦戦密度の直近窓

# 自動ドラフトの本文に必ず入る行。手書きの提案と分ける唯一の手がかりで、
# scripts/build-plugin-release.py の GENERATED_PROPOSAL_MARKER と同じ文字列にする。
_GENERATED_MARKER = "aggregate-evals.py により自動生成された"


def _manifest_name(root: Path) -> str | None:
    """<root>/.claude-plugin/plugin.json の name。読めなければ None。"""
    try:
        manifest = json.loads(
            (root / ".claude-plugin" / "plugin.json").read_text(encoding="utf-8")
        )
    except (OSError, ValueError):
        return None
    return manifest.get("name") if isinstance(manifest, dict) else None


def _self_plugin_name() -> str | None:
    """このファイル自身が属する plugin の manifest name。

    リテラル直書きは制御リテラル散在として禁止 (tests/test_dogfooding_boundary.py)、
    SSOT 定数は「SSOT を探すのに plugin root が要る」循環のため使えない。__file__ は
    循環せず改名にも自動追従する第三の出所。plugin は入れ子にならないので、上向きに
    最初に見つかる manifest が自 plugin のもので確定する。
    """
    for parent in Path(__file__).resolve().parents:
        name = _manifest_name(parent)
        if name:
            return name
    return None


def _hc_env_root() -> Path | None:
    """env から自 plugin root を得る。他 plugin を指す値は拒否する。

    他 repo が .claude 平置き projection で本 plugin を借用している場合、
    env CLAUDE_PLUGIN_ROOT は **別 plugin** を指していることがある
    (ObsidianMemo では ubm-goal-setting)。空ではなく「存在するが別物」なので
    `if env:` では弾けない。manifest の name で自 plugin か検証する。
    借用側は HC_ROOT を設定すれば明示指定できる。
    拒否するのは manifest が読めて **別 plugin と確認できた** 場合だけにする。
    判定材料が無い (manifest 不在) env は従来どおり採用し、既存挙動を後退
    させない。vendored コピー先 (company-master / skill-intake) でも同様。
    """
    expected = _self_plugin_name()
    if not expected:
        return None
    for _var in ("HC_ROOT", "CLAUDE_PLUGIN_ROOT"):
        raw = os.environ.get(_var)
        if not raw:
            continue
        root = Path(raw).expanduser()
        _name = _manifest_name(root)
        if _name is None or _name == expected:
            return root.resolve()
    return None


def _plugin_root() -> Path:
    # 本ファイル: plugins/harness-creator/skills/run-skill-rubric-governance/scripts/
    return _hc_env_root() or Path(__file__).resolve().parents[3]


def _project_state_root() -> Path | None:
    """自動ドラフトの既定の置き場 (project の state)。$CLAUDE_PROJECT_DIR が無ければ None。"""
    project = os.environ.get("CLAUDE_PROJECT_DIR")
    if project:
        return Path(project) / ".claude" / "state" / "harness-creator"
    return None


def _inferred_project_state_roots() -> list[Path]:
    """$CLAUDE_PROJECT_DIR が無いときに、project の state を推し量る。読む側だけで使う。

    SessionEnd hook は $CLAUDE_PROJECT_DIR のある環境で動くので、自動ドラフトはその project の
    state に書かれる。一方、Bash から手で --list-proposals を流すときは $CLAUDE_PROJECT_DIR が無い。
    project は Claude Code を起動したディレクトリで、ふつうは cwd か、cwd を含む git の作業ツリーの
    root (.git のあるディレクトリ。`git rev-parse --show-toplevel` と同じ) なので、両方を候補にする。
    書く側には使わない。推し量った先に書くと、hook の書き先とずれたときに提案が散らばる。
    """
    if os.environ.get("CLAUDE_PROJECT_DIR"):
        return []
    try:
        cwd = Path.cwd()
    except OSError:
        return []
    toplevel = next((d for d in (cwd, *cwd.parents) if (d / ".git").exists()), None)
    projects = dict.fromkeys(d for d in (cwd, toplevel) if d is not None)
    return [d / ".claude" / "state" / "harness-creator" for d in projects]


def _state_fallback_root() -> Path:
    """project の state に書けないとき (CLAUDE_PROJECT_DIR 未設定・read-only) の退避先。

    手本: notifier-check.py の `Path.home()/.cache/harness` (user 領域退避)。
    優先順: $XDG_STATE_HOME → ~/.claude/state。
    """
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


def _legacy_proposals_dir() -> Path:
    """手書きの提案が tracked で残る従来の置き場 (plugin のツリーの中)。読むだけで書かない。"""
    return _plugin_root() / "skills" / "run-skill-rubric-governance" / "proposals"


def _proposals_dir() -> Path:
    """rubric-update 提案ドラフトの第一の書込先。env の明示 > project の state。

    $CLAUDE_PROJECT_DIR が無いときは user の state を返す。
    read-only のときの退避は呼び出し側 (_candidate_proposals_dirs / main) が担う。
    """
    override = os.environ.get("HARNESS_CREATOR_PROPOSALS_DIR")
    if override:
        return Path(override).resolve()
    return (_project_state_root() or _state_fallback_root()) / "proposals"


def _is_inside_plugin(d: Path) -> bool:
    plugin = _plugin_root().resolve()
    target = d.resolve()
    return target == plugin or plugin in target.parents


def _candidate_proposals_dirs() -> list[Path]:
    """書込先候補を優先順で返す。

    (a) env HARNESS_CREATOR_PROPOSALS_DIR の明示。あればそれだけを使う
    (b) $CLAUDE_PROJECT_DIR/.claude/state/harness-creator/proposals
    (c) 書けなければ user の state ($XDG_STATE_HOME か ~/.claude/state) へ退避
    (b)(c) のうち plugin のツリーの中に落ちるものは外す。plugin のディレクトリを
    cwd にして session を回すと $CLAUDE_PROJECT_DIR が plugin 自身を指し、(b) が
    plugin の中になる。(a) は利用者の明示なので外さない。
    """
    if os.environ.get("HARNESS_CREATOR_PROPOSALS_DIR"):
        return [_proposals_dir()]
    candidates = dict.fromkeys([_proposals_dir(), _state_fallback_root() / "proposals"])
    return [d for d in candidates if not _is_inside_plugin(d)]


def _proposal_read_dirs() -> list[Path]:
    """提案を読む・数えるときに見る置き場。書込先の候補すべてと、従来の置き場。

    自動ドラフトは書込先の候補のどれかに、手書きの提案は従来の置き場にある。
    片方だけを見ると、もう片方の提案を見落とす。
    $CLAUDE_PROJECT_DIR が無いと書込先の候補に project の state が入らないので、推し量った
    project の state を先頭に足す。plugin のツリーの中に落ちるものは、書く側と同じく外す。
    """
    inferred = [r / "proposals" for r in _inferred_project_state_roots()]
    inferred = [d for d in inferred if not _is_inside_plugin(d)]
    return list(dict.fromkeys([*inferred, *_candidate_proposals_dirs(), _legacy_proposals_dir()]))


def _is_generated_proposal(path: Path) -> bool:
    """本文に生成器の marker 行があれば自動ドラフト。読めなければ手書き扱い。"""
    try:
        return _GENERATED_MARKER in path.read_text(encoding="utf-8", errors="replace")
    except OSError:
        return False


def _list_proposals() -> dict[str, Any]:
    dirs = _proposal_read_dirs()
    proposals = [
        {"path": str(p), "generated": _is_generated_proposal(p)}
        for d in dirs
        if d.is_dir()
        for p in sorted(d.glob("*.md"))
    ]
    return {"dirs": [str(d) for d in dirs], "proposals": proposals}


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
    reviewed_at = rec.get("reviewed_at")
    return {
        "skill": skill,
        "date": _date_of(reviewed_at),
        # 秒精度の生タイムスタンプ。date は日付へ丸まってしまうので、同一レビューラウンドの
        # 2 ファイル投影を畳む _review_identity のキー材料として別に持つ。
        "reviewed_at": reviewed_at if isinstance(reviewed_at, str) else None,
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


def _review_identity(rec: dict[str, Any]) -> tuple[Any, ...]:
    """同一レビューラウンドを指す同一性キー。

    reviewed_at は秒精度のタイムスタンプで、同一ラウンドの 2 ファイルには同じ値が書かれる
    規約なので、これを skill と組めばラウンドを一意に指せる。date (日付) まで丸めると、
    同じ日に 2 回別のレビューを回したケースまで畳んでしまい、本物の相互裏付けを消す。
    """
    return (rec.get("skill"), rec.get("reviewed_at"), rec.get("date"))


def _merge_review_projections(a: dict[str, Any], b: dict[str, Any]) -> dict[str, Any]:
    """同一レビューの 2 投影を 1 レコードへ合成する。

    規約上 a と b の iterations / negative_feedback_count は同値になるはずだが、書き手が
    片方だけ更新した中途半端な状態は現実に起こる。ここでは大きい方を採る (摩擦情報を捨てない)。

    max を採っても過剰検出にはなりにくい。この合成が決めるのは「この 1 ラウンドが摩擦か」
    だけで、friction_density の発火には畳んだ後に別ラウンドの裏付けがなお 2 件必要だからだ。
    先勝ちにすると sorted() 順で elegance 側だけが残り、rubric 側にしか無い摩擦が静かに
    消える — 落とした情報は後から復元できないが、過大な 1 レコードは裏付け不足で発火しない。
    非対称なので、復元できない側を避ける。

    iterations は verdict に無ければ None になるので、max へ直接渡すと TypeError で落ちる。
    """
    merged = dict(a)
    iterations = [
        v for v in (a.get("iterations"), b.get("iterations")) if isinstance(v, int)
    ]
    merged["iterations"] = max(iterations) if iterations else None
    merged["negative_feedback_count"] = max(
        a.get("negative_feedback_count") if isinstance(a.get("negative_feedback_count"), int) else 0,
        b.get("negative_feedback_count") if isinstance(b.get("negative_feedback_count"), int) else 0,
    )
    # content-review では常に [] だが、将来値が入ったときに片方を捨てないよう和を取る。
    findings: list[Any] = list(a.get("findings") or [])
    for f in b.get("findings") or []:
        if f not in findings:
            findings.append(f)
    merged["findings"] = findings
    return merged


def _load_content_review_verdicts() -> list[dict[str, Any]]:
    """eval-log/<plugin>/<skill>/content-review/*-verdict.json を全件読む。

    content-review 規約は同一レビューを elegance-verdict.json と rubric-verdict.json の
    2 ファイルへ同じ iterations / negative_feedback で投影する。glob の結果をそのまま
    返すと 1 回のレビューが常に 2 レコードになり、friction_density の
    _FRICTION_MIN_RECORDS = 2 (「相互裏付け」) が自分自身のコピーで満たされて実質 >= 1 へ
    退化する。投影の数は将来増えうるので、閾値側ではなくここで 1 レビュー 1 レコードへ畳む。
    """
    out: list[dict[str, Any]] = []
    base = _eval_log_dir()
    if not base.exists():
        return out
    try:
        paths = sorted(base.glob("**/content-review/*-verdict.json"))
    except OSError:
        return out
    merged: dict[tuple[Any, ...], dict[str, Any]] = {}
    order: list[tuple[Any, ...]] = []
    for path in paths:
        try:
            rec = json.loads(path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            continue
        norm = _normalize_verdict_record(rec)
        if norm is None:
            continue
        key = _review_identity(norm)
        if key in merged:
            merged[key] = _merge_review_projections(merged[key], norm)
        else:
            merged[key] = norm
            order.append(key)
    for key in order:
        out.append(merged[key])
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
        f"本ドラフトは {_GENERATED_MARKER}。PR 起票は別工程。",
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


def main(argv: list[str] | None = None) -> int:
    # SessionEnd hook は引数を付けずに呼ぶ（hooks/hooks.json）。引数があれば手で流したとみなして argparse に渡す。
    # 知らない引数や綴りの誤りは exit 2 で止める。hook の経路へ落とすと、一覧のつもりで提案を書いてしまう。
    if argv:
        ap = argparse.ArgumentParser(
            allow_abbrev=False,
            description="引数なしでは SessionEnd hook として評価を集計し、異常があれば提案ドラフトを書く。",
        )
        ap.add_argument("--list-proposals", action="store_true", required=True,
                        help="書かずに、自動ドラフトと手書きの提案の両方の置き場を一覧する（JSON）")
        ap.parse_args(argv)
        listing = _list_proposals()
        if not os.environ.get("CLAUDE_PROJECT_DIR"):
            print("[aggregate-evals] CLAUDE_PROJECT_DIR が無いので、cwd と git の作業ツリーの root を "
                  "project とみなして読んだ。見た置き場は dirs にある", file=sys.stderr)
        print(json.dumps(listing, ensure_ascii=False, indent=2))
        return 0

    # stdin は SessionEnd hook payload。本 script では使わないが drain しておく。
    try:
        sys.stdin.read()
    except Exception:  # 捨てる payload なので、stdin が None・閉じている・decode できないのどれでも集計へ進む
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

    # 書込可能な最初の候補へ (_candidate_proposals_dirs の順)。全滅なら silent no-op exit 0。
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
    raise SystemExit(main(sys.argv[1:]))
