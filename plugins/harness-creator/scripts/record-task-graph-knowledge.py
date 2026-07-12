#!/usr/bin/env python3
# /// script
# name: record-task-graph-knowledge
# purpose: task-graph 駆動 build の外ループ完了ゲート + knowledge 記録 owner (TG-C08)。inbox の未処理 discovered-task を検出して completion_gate:ok|blocked + handback_command を出す (未処理残存なら capability-build を completed にせず外ループへ制御返却)。gate ok 時のみ task-events/stall/handoff_notes から依存詰まり・成果物欠落・blocked 伝播起点・再試行で解消した判断だけを蒸留し、add_entry.py 経由で target harness (Loop A) と harness-creator (Loop B) の双方 knowledge へ source_ref 付き要約を追記する。graph 更新は planner 限定 (本 script は task-graph/phase/component-inventory/handoff を一切書かない)。
# inputs:
#   - argv: --target-plugin-slug S [--cycle-id C] [--discovered-inbox DIR] [--plan-dir PLAN_DIR]
#           [--handoff H] [--task-events P] [--task-state P] [--summary-json P] [--target-knowledge-dir A]
#           [--harness-knowledge-dir B] [--add-entry-path P] [--max-entries N] [--dry-run]
# outputs:
#   - stdout: completion_gate JSON (全形に inbox_absent: bool を携帯 = inbox ディレクトリ不在
#             「外ループ未発火」と 実在+全件処理済 の区別)
#       blocked 時 (第1段=未処理 discovered-task 残存): pending_discovered_tasks[]{path,change_level,status}
#                   + needs_approval(bool・未処理に structural が1件以上か) + handback_command (--plan-dir
#                   有れば planner locator --out-dir を含む copy-paste 実行可能形・structural 未処理時は
#                   --approved 二段受理指示付き) + next_steps[[0]=planner drain(完全形),
#                   [1]=capability-build 再実行(--handoff 指定時に完全形・未指定時は <handoff> を
#                   テンプレート表示)]
#       blocked 時 (第2段=--task-state の blocked node 残存): blocked_tasks[]{id,blocked_reason}
#                   (origin-failure/propagated 双方・id 昇順) + next_steps 分岐指示
#                   [人手救済 (受入基準修正→再検証), emit-discovered-task による外ループ合流]
#       ok 時: 記録サマリ (entries_recorded + knowledge_record_status=ok|ok_no_lessons|loop_a_skipped|
#              loop_b_skipped|record_failed + store_results{loop_a,loop_b}{status,recorded[,reason]}
#              per-store 件数 + empty_reason (entries==0 の理由・それ以外 null))。store 不在/consult_at
#              未宣言は書込前に事前検知して skipped へ分類し (record_failed にしない)、書込は store 単位+
#              entry 単位で try 隔離する (Loop A 失敗でも Loop B 継続)。蒸留 0 件を vacuous "ok" で偽装しない
#   - stderr: usage / Loop A 未配線・add_entry 失敗の WARN 診断
#   - exit: 0=gate ok (knowledge 記録の成否に依らず・疎結合) / 1=gate blocked (未処理 discovered-task または blocked node 残存) / 2=usage/IO error (引数/parse のみ)
#   - write-scope: <target-knowledge-dir> knowledge/ (Loop A) + <harness-knowledge-dir> knowledge/ (Loop B) (add_entry.py 委譲) + <task-events> task-events.jsonl (gate 判定 event append・TG-C02 append_event 再利用・--dry-run 時は書かない)
# contexts: [C, E]
# network: false
# write-scope: Loop A/Loop B knowledge stores + task-events.jsonl append (task-graph/plan は一切書かない)
# dependencies: []
# requires-python: ">=3.10"
# ///
"""task-graph 駆動 build の完了ゲート + knowledge 記録 (TG-C08)。

外ループ結合点: producer accept-discovered-task.py --inbox が受理時に discovered-task form へ
status (accepted/rejected/superseded) を書き戻す。本 script はその裏返しとして inbox を走査し、
status が処理済でない (未設定/pending) form が 1 件でも残れば completion_gate:"blocked" と
handback_command を出して exit1 し、/capability-build の task-graph dispatcher (TG-C06) の
completed 宣言を機構的に遅延させる。
handback_command は TG-C06 のラッピングに依存せず TG-C08 出力単体で外ループを閉じられる copy-paste
実行可能形にする: (1) --plan-dir <PLAN_DIR> があれば handback へ planner locator (--out-dir <PLAN_DIR>)
を含め、planner がどの task-graph.json をドレインするか決定論解決できるようにする。(2) 未処理に
structural discovered-task (stall spec-gap 由来を含む) が 1 件でもあれば needs_approval=true とし、
planner ドレインが --approved 二段受理を要する旨を handback に明示する (未承認だと structural は
pending 据置で block が永久継続しデッドロックするため)。(3) next_steps の 2 コマンドで次の一手を
単体提示する: [0]=planner drain (常に完全形)・[1]=capability-build 再実行 (--handoff 指定時は実パス
置換で完全形・未指定時は <handoff> をテンプレート表示する後方互換)。本 script は planner を
起動せず graph も書かない (gate 判定 event の task-events.jsonl append は TG-C02 append_event を
sibling import で再利用し単一 writer 経由を維持・--dry-run 時は書かない)。

完了ゲート第2段: --task-state が与えられた場合、pending discovered-task がゼロでも state=blocked
の node (blocked_reason=origin-failure の起点故障・propagated の伝播 双方) が残存する限り
completion_gate:"blocked" とする (blocked を放置した completed 宣言を封鎖)。出力の blocked_tasks
[]{id,blocked_reason} と next_steps 分岐指示 [人手救済 (受入基準修正→再検証) / emit-discovered-task
起票による外ループ合流] で救済経路を単体提示する。全出力形は inbox_absent (inbox ディレクトリ
不在=外ループ未発火 と 実在+全件処理済 の区別) を携帯する。

完了ゲート第3段: --task-state の実パスから上方探索した repo root に唯一の生成器
scripts/build-claude-symlinks.py が実在する場合、--check を実行して .claude symlink drift
(build した skill/agent/command が .claude へ未展開で Claude Code に認識されない状態) を検査し、
drift なら completion_gate:"blocked" + fix_command (bash scripts/sync-skills-to-claude.sh --apply)
を単体提示する (run-build-skill SKILL.md の build 完了契約「build/更新後は sync 必須」の機械層。
宣言のみだと route 分散 build の task-graph モードで owner 不在のまま skip される実害が出た)。
生成器不在 (テスト隔離環境・配布先) は claude_symlink_gate.status:"skipped" で fail-soft 通過する。

gate ok 時のみ knowledge 記録へ進む: task-events.jsonl / stall summary / route-build-report
handoff_notes に加え、task-state nodes の route_report 実体から deviations[] (string 配列) と
handover/handoff_notes (string 配列形式) を読み、「依存詰まり / 成果物欠落 / blocked 伝播起点 /
再試行で解消した判断 / 計画逸脱 / 申し送り」だけを最大 --max-entries 件へ蒸留し (生ログ全文・
全 notes は複製しない)、add_entry.py 必須6フィールド (id/title/intent/background/keywords/source)
の entry を組んで Loop A (target harness) と Loop B (harness-creator) 双方の knowledge へ同 schema
で追記する。source には {file, task_id, route_id, event_id} の参照だけを持たせる。蒸留 0 件は
knowledge_record_status=ok_no_lessons + empty_reason で明示し vacuous "ok" を出さない。
"""
from __future__ import annotations

import argparse
import hashlib
import importlib.util
import json
import subprocess
import sys
from pathlib import Path

_HERE = Path(__file__).resolve().parent
_PLUGIN_ROOT = _HERE.parent

# 完了ゲートが「処理済」とみなす status 集合 (producer accept-discovered-task.py と一致)。
# これ以外 (未設定/pending) の form が 1 件でも inbox に残ると completed を block する。
PROCESSED_STATUSES = {"accepted", "rejected", "superseded"}
KNOWLEDGE_CATEGORY = "build-patterns"
DEFAULT_MAX_ENTRIES = 3

# 蒸留対象シグナルの title / intent プレフィックス。
_SIGNAL_TITLE = {
    "dependency-stall": "依存詰まり (spec-gap)",
    "artifact-missing": "成果物欠落",
    "blocked-origin": "blocked 起点故障",
    "blocked-propagation": "blocked 伝播",
    "retry-resolved": "再試行で解消した判断",
    "friction": "route friction note",
    "deviation": "計画からの逸脱 (route deviation)",
    "handover": "route 申し送り (handover)",
}
_SIGNAL_INTENT = {
    "dependency-stall": "task-graph 上に依存先が不在の停滞を次回 planner --mode update で解消できるよう記録すること",
    "artifact-missing": "producer done でも成果物が実在しない乖離を fail-closed で捕捉できるよう記録すること",
    "blocked-origin": "route 実行失敗の起点 (origin-failure) を特定し人手救済導線を残すこと",
    "blocked-propagation": "blocked の伝播連鎖を辿り起点故障へ帰着できるよう記録すること",
    "retry-resolved": "lease 回収→再試行で解消したパターンを次回 build へ再利用すること",
    "friction": "route 実行で得た摩擦点を次回 build の判断材料として残すこと",
    "deviation": "route 実行が計画から逸脱した判断・代替生成を次回 plan/build へ再利用できるよう記録すること",
    "handover": "route 完了時の申し送り (次タスク前提の自然文) を次回 build の判断材料として残すこと",
}

# route report 由来 message の蒸留上限 (生 report の長文 prose を knowledge へ丸写ししない)。
_REPORT_MESSAGE_CLIP = 200

# entries==0 (蒸留レーン全滅) 時に出力 JSON へ携帯する既定理由。
_EMPTY_REASON_NO_LESSONS = "no distillable events matched distiller lanes"


def _clip(text: str) -> str:
    """report 由来の長文 prose を蒸留上限で打ち切る (超過は … を付す)。"""
    text = text.strip()
    if len(text) <= _REPORT_MESSAGE_CLIP:
        return text
    return text[:_REPORT_MESSAGE_CLIP] + "…"


# ── sibling importlib ロード (TG-C02 resolve_build_dir の SSOT 再利用) ─────────
def _load_sibling(stem: str):
    """同一 scripts/ のハイフン名 module を importlib で読み込む。"""
    path = _HERE / f"{stem}.py"
    spec = importlib.util.spec_from_file_location(stem.replace("-", "_"), path)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


def _resolve_build_dir(target_plugin_slug: str, cycle_id: str | None) -> str:
    """TG-C02 (sync-task-state) の resolve_build_dir SSOT を import して再利用する。"""
    sts = _load_sibling("sync-task-state")
    return sts.resolve_build_dir(target_plugin_slug, cycle_id)


# ── 外ループ完了ゲート: 未処理 discovered-task の走査 ─────────────────────────
def scan_pending_discovered(discovered_dir: Path) -> list[dict]:
    """inbox の *.json を走査し status が処理済でない (未設定/pending) form を未処理として返す。

    producer accept-discovered-task.py --inbox が受理時に status を PROCESSED_STATUSES へ書き戻す
    前提の裏返し。discovered_dir 不在は「発見タスク無し = 未処理 0 件」として空リストを返す。
    戻り値の各 dict は {path, status, discovering_task_id, change_level} (決定論順 = filename 昇順)。
    change_level (additive|structural) は needs_approval 判定に使う (読めない form は None)。
    """
    discovered_dir = Path(discovered_dir)
    if not discovered_dir.is_dir():
        return []
    pending: list[dict] = []
    for form_path in sorted(discovered_dir.glob("*.json")):
        try:
            form = json.loads(form_path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            # 読めない form は処理不能 = 未処理扱い (block して人手介入を促す)。
            # change_level 不明 (None): drain 時に rejected 化され解決するため structural デッドロックは起きない。
            pending.append({"path": str(form_path), "status": None,
                            "discovering_task_id": None, "change_level": None})
            continue
        status = form.get("status") if isinstance(form, dict) else None
        if status in PROCESSED_STATUSES:
            continue
        pending.append({
            "path": str(form_path),
            "status": status,
            "discovering_task_id": form.get("discovering_task_id") if isinstance(form, dict) else None,
            "change_level": form.get("change_level") if isinstance(form, dict) else None,
        })
    return pending


# ── 外ループ完了ゲート第2段: blocked node の走査 (task-state) ─────────────────
def scan_blocked_tasks(task_state: dict) -> list[dict]:
    """task-state.json の state=blocked node を {id, blocked_reason} で列挙する (id 昇順)。

    起点故障 (blocked_reason=origin-failure) と伝播 (propagated) の双方を含む。pending
    discovered-task が 0 でも blocked node が残存する限り build 全体は completed でない
    (blocked 放置の completed 宣言を封鎖する完了ゲート第2段)。
    """
    blocked = [
        {"id": n.get("id"), "blocked_reason": n.get("blocked_reason")}
        for n in (task_state.get("nodes", []) if isinstance(task_state, dict) else [])
        if isinstance(n, dict) and n.get("state") == "blocked"
    ]
    return sorted(blocked, key=lambda b: str(b["id"]))


# ── handback 構築 (TG-C08 出力単体で外ループを閉じられる copy-paste 実行可能形) ──
# 再入は task-graph route モード (--route-id なし) で、planner drain 済みの改善グラフ全体を
# 再駆動する (TG-C07 が新 graph_hash を re-pin し TG-C01 が ready-set を再計算)。--route-id を付けると
# capability-build Step1 が単一 route モードへ落ち改善グラフ全体を回さないため付けない。
# <handoff> は --handoff 実パス指定時に置換され完全形になる (未指定時はテンプレート表示)。
_REBUILD_COMMAND = "/capability-build --handoff <handoff>"


def build_handback_command(inbox_dir: Path, plan_dir: str | None, needs_approval: bool) -> str:
    """未処理 discovered-task を planner でドレインする copy-paste 実行可能な handback を組む。

    plan_dir があれば --out-dir <PLAN_DIR> を付け、planner がどの PLAN_DIR / task-graph.json を
    ドレインするか決定論解決できる locator を含める (無ければ従来どおり inbox のみの handback へ
    フォールバック)。needs_approval (未処理に structural あり) の場合は **主コマンド run-plugin-dev-plan
    へ直接 --approved を付ける** (F1): planner はこれを内部の accept-discovered-task.py --inbox ...
    --approved 二段受理へ転送する。承認指示を散文の括弧注に埋めず主コマンド1本で structural 承認まで
    閉じる (未承認だと structural は pending 据置で block が永久継続しデッドロックするため)。
    """
    cmd = f"run-plugin-dev-plan --mode update --discovered-inbox {inbox_dir}"
    if plan_dir:
        cmd += f" --out-dir {plan_dir}"
    if needs_approval:
        cmd += " --approved"
    return cmd


def build_next_steps(inbox_dir: Path, plan_dir: str | None, needs_approval: bool,
                     handoff: str | None = None) -> list[str]:
    """次の一手を TG-C08 出力単体で提示する 2 コマンド [planner drain(完全形), capability-build 再実行]。

    [0] は build_handback_command と同一 (structural 時は承認指示をインラインで携帯)、
    [1] は反映後の build 再開コマンド (task-graph route モード再入=`--handoff` のみ・`--route-id`
    なしで改善グラフ全体を再駆動)。handoff (実パス) 指定時は <handoff> placeholder を置換して
    [1] も copy-paste 実行可能な完全形になる (未指定時はテンプレート表示の後方互換)。
    TG-C06 のラッピングに依存せず本 gate 出力だけで planner ドレイン→再 build の外ループを閉じられる。
    """
    rebuild = _REBUILD_COMMAND.replace("<handoff>", handoff) if handoff else _REBUILD_COMMAND
    return [
        build_handback_command(inbox_dir, plan_dir, needs_approval),
        rebuild,
    ]


def build_blocked_task_next_steps(inbox_dir: Path, handoff: str | None) -> list[str]:
    """blocked node 残存時の分岐指示 2 択 [人手救済, emit-discovered-task 外ループ合流] を組む。

    blocked は受入基準と実装の乖離 (起点故障) が典型で、planner drain では解消しない。
    (1) 人手救済: 受入基準を修正→再検証し capability-build を再実行 (--handoff 指定時は
    <handoff> を実パス置換した完全形)。(2) 仕様側の欠落が原因なら emit-discovered-task で
    form を起票し planner 外ループへ合流する。いずれも本 gate 出力単体で次の一手が分かる。
    """
    rebuild = _REBUILD_COMMAND.replace("<handoff>", handoff) if handoff else _REBUILD_COMMAND
    return [
        f"人手救済: blocked 起点 task の受入基準を修正して再検証し、{rebuild} で再実行する",
        f"emit-discovered-task.py で discovered-task form を {inbox_dir} へ起票して外ループへ合流する"
        f" (drain: run-plugin-dev-plan --mode update --discovered-inbox {inbox_dir})",
    ]


# ── gate 判定 event の append (TG-C02 append_event 再利用=単一 writer 経由・S-11) ──
def append_gate_event(task_events, event: dict) -> None:
    """完了ゲート判定確定を task-events.jsonl へ append する (build_completed/build_blocked)。

    書込は TG-C02 (sync-task-state) の append_event を sibling import で再利用し単一 writer
    経由を維持する。append 失敗は gate 判定 (exit code) へ伝播させないベストエフォート
    (task_events 未解決=None はスキップ)。呼び出し側が --dry-run 時は呼ばない。
    """
    if task_events is None:
        return
    try:
        sts = _load_sibling("sync-task-state")
        Path(task_events).parent.mkdir(parents=True, exist_ok=True)
        sts.append_event(task_events, event)
    except OSError as exc:
        print(f"warning: gate event 追記失敗 (gate 判定は不変): {exc}", file=sys.stderr)


# ── knowledge 蒸留 (生ログ丸写しを避け signal だけ抽出) ───────────────────────
def _classify_event(ev: dict, file: str, idx: int) -> dict | None:
    """task-events.jsonl の 1 行を 4 シグナルのいずれかへ分類する (該当無しは None=noise)。

    running 遷移 / lease_renewed / graph_hash_pinned 等の noise は None を返し蒸留しない
    (生ログを knowledge へ複製しない)。
    """
    t = ev.get("type")
    event_id = ev.get("ts") or f"L{idx}"
    task_id = ev.get("task_id")
    if t == "lease_reaped":
        return {
            "signal": "retry-resolved",
            "message": f"task {task_id} の lease 期限切れを回収し running→pending で再試行導線を確保した",
            "source_ref": {"file": file, "task_id": task_id, "event_id": event_id},
        }
    if t == "state_transition" and ev.get("to_state") == "blocked":
        if ev.get("blocked_reason") == "propagated":
            origin = ev.get("origin_task_id")
            return {
                "signal": "blocked-propagation",
                "message": f"task {task_id} が origin {origin} の失敗から伝播 blocked へ連鎖した",
                "source_ref": {"file": file, "task_id": task_id, "event_id": event_id},
            }
        return {
            "signal": "blocked-origin",
            "message": f"task {task_id} が route 失敗で blocked (起点故障) となった",
            "source_ref": {"file": file, "task_id": task_id, "event_id": event_id},
        }
    reason = str(ev.get("reason") or ev.get("message") or "")
    if t == "artifact_missing" or "artifact" in reason.lower() or "成果物" in reason:
        return {
            "signal": "artifact-missing",
            "message": f"成果物欠落を検出した: {reason[:80]}".rstrip(),
            "source_ref": {"file": file, "task_id": task_id, "event_id": event_id},
        }
    return None


def distill_events(task_events: Path, summary: dict, limit: int = DEFAULT_MAX_ENTRIES,
                   report_lessons: list[dict] | None = None) -> list[dict]:
    """task-events / stall summary / handoff_notes / route report から signal だけを最大 limit 件へ蒸留する。

    生ログ全文や全 notes は複製せず、依存詰まり・成果物欠落・blocked 伝播起点・再試行で解消した
    判断・計画逸脱 (deviation)・申し送り (handover) へ合致するものだけを short な synthesized
    message へ要約する。(signal, message) で dedupe し limit で打ち切る。report_lessons は
    _collect_report_lessons が route report 実体から蒸留済みの lesson 列 (省略時は空 = 後方互換)。
    """
    summary = summary or {}
    lessons: list[dict] = []

    # 1. stall summary の診断 (TG-C05 detect_stall 出力)。spec-gap=依存詰まり / build-failure=blocked 起点。
    stall = summary.get("stall") or {}
    for d in stall.get("diagnosis", []) or []:
        signal = "dependency-stall" if d.get("kind") == "spec-gap" else "blocked-origin"
        lessons.append({
            "signal": signal,
            "message": str(d.get("message", "")).strip(),
            "source_ref": {"file": "summary:stall", "task_id": d.get("task_id")},
        })

    # 2. route-build-report handoff_notes (friction_points / downstream_watchouts)。
    for hn in summary.get("handoff_notes", []) or []:
        base_ref = {"file": hn.get("file"), "task_id": hn.get("task_id"), "route_id": hn.get("route_id")}
        for fp in (hn.get("friction_points") or []):
            lessons.append({"signal": "friction", "message": str(fp).strip(), "source_ref": dict(base_ref)})
        for wo in (hn.get("downstream_watchouts") or []):
            lessons.append({"signal": "friction", "message": str(wo).strip(), "source_ref": dict(base_ref)})

    # 2b. route report 実体レーン (deviations[] / handover / handoff_notes string 配列)。
    lessons.extend(report_lessons or [])

    # 3. task-events.jsonl の signal イベント。
    if task_events is not None and Path(task_events).exists():
        for idx, raw in enumerate(Path(task_events).read_text(encoding="utf-8").splitlines(), 1):
            raw = raw.strip()
            if not raw:
                continue
            try:
                ev = json.loads(raw)
            except json.JSONDecodeError:
                continue
            lesson = _classify_event(ev, str(task_events), idx)
            if lesson is not None:
                lessons.append(lesson)

    # dedupe (signal, message) 保序 + limit 打ち切り。
    seen: set[tuple[str, str]] = set()
    out: list[dict] = []
    for lesson in lessons:
        key = (lesson["signal"], lesson["message"])
        if key in seen:
            continue
        seen.add(key)
        out.append(lesson)
        if len(out) >= limit:
            break
    return out


# ── knowledge entry 構築 (add_entry.py 必須6フィールド) ───────────────────────
def build_knowledge_entry(lesson: dict, source_ref: dict, target_plugin_slug: str) -> dict:
    """lesson + source_ref から add_entry.py 必須6フィールドの entry を組む (決定論 id)。

    source には {file, task_id, route_id, event_id} の参照だけを持たせ、生ログは焼き込まない。
    """
    signal = lesson.get("signal", "runtime-lesson")
    message = str(lesson.get("message") or "").strip()
    source_ref = source_ref or {}

    # 決定論 id (同一 lesson は同一 id → 冪等・store 内 ID 重複を回避)。
    basis = json.dumps(
        {"s": signal, "m": message, "r": source_ref, "p": target_plugin_slug},
        sort_keys=True, ensure_ascii=False,
    )
    digest = hashlib.sha1(basis.encode("utf-8")).hexdigest()[:10]
    entry_id = f"runtime-{signal}_{digest}"

    title = _SIGNAL_TITLE.get(signal, "task-graph 実行知見")
    if message:
        title = f"{title}: {message[:60]}"
    intent = _SIGNAL_INTENT.get(signal, "task-graph 実行中に得た知見を次回 build へ引き継ぐこと")

    ref_bits = []
    for key in ("task_id", "route_id", "event_id"):
        if source_ref.get(key):
            ref_bits.append(f"{key}={source_ref[key]}")
    background = message or intent
    if ref_bits:
        background = f"{background} (発生源: {', '.join(ref_bits)})"

    keywords = ["task-graph", "runtime", "build-execution", "knowledge-loop", signal]
    if target_plugin_slug:
        keywords.append(target_plugin_slug)

    # source は参照だけ (file は必ず 1 つ持たせて add_entry の truthy 検証を通す)。
    source = {k: source_ref.get(k) for k in ("file", "task_id", "route_id", "event_id")
              if source_ref.get(k) is not None}
    if not source:
        source = {"file": "task-events"}

    return {
        "id": entry_id,
        "title": title,
        "intent": intent,
        "background": background,
        "keywords": keywords,
        "source": source,
        # 内部運搬用 (store へは書かない)。
        "signal": signal,
        "target_plugin_slug": target_plugin_slug,
    }


def _entry_for_store(entry: dict) -> dict:
    """store へ渡す 6 フィールドのみへ整形 (内部運搬キーを除去)。"""
    return {k: entry[k] for k in ("id", "title", "intent", "background", "keywords", "source")
            if k in entry}


# ── knowledge store 事前検知 (add_entry 失敗前に skipped へ分類) ────────────────
def check_store_ready(store_dir: Path) -> str | None:
    """knowledge store の書込可否を add_entry 実行前に判定する (不備理由 str / 可なら None)。

    add_entry.py の --dir 解決 (store/knowledge-index.json → store/knowledge/knowledge-index.json)
    と guard_consult_at (consult_at 宣言必須 = KL-007) を書込前に再現し、store 不在・index 不在・
    consult_at 未宣言を record_failed でなく skipped へ事前分類できるようにする。
    """
    store_dir = Path(store_dir)
    if not store_dir.is_dir():
        return "store ディレクトリ不在"
    index_path = store_dir / "knowledge-index.json"
    if not index_path.exists():
        index_path = store_dir / "knowledge" / "knowledge-index.json"
    if not index_path.exists():
        return "knowledge-index.json 不在"
    # consult_at 宣言 (knowledge-index.json / router.json のどちらか) の事前検査。
    for decl_name in ("knowledge-index.json", "router.json"):
        decl = index_path.parent / decl_name
        if not decl.exists():
            continue
        try:
            data = json.loads(decl.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError) as exc:
            return f"{decl_name} 読込/parse 失敗: {exc}"
        if isinstance(data, dict) and "consult_at" in data:
            return None
    return "consult_at 未宣言 (KL-007)"


# ── knowledge 書込 (add_entry.py subprocess 委譲・1 store 分) ──────────────────
def write_knowledge(entry: dict, store_dir: Path, add_entry_path: Path) -> None:
    """add_entry.py --dir <store_dir> --category build-patterns --json - へ 1 entry を追記する。

    Loop A / Loop B いずれか 1 store 分の追記。双方への追記は呼び出し側 (main) が 2 回呼ぶ。
    add_entry.py が見つからなければ FileNotFoundError、追記失敗は RuntimeError。
    """
    store_dir = Path(store_dir)
    add_entry_path = Path(add_entry_path)
    if not add_entry_path.exists():
        raise FileNotFoundError(f"add_entry.py が見つからない: {add_entry_path}")
    payload = json.dumps(_entry_for_store(entry), ensure_ascii=False)
    proc = subprocess.run(
        [sys.executable, str(add_entry_path), "--dir", str(store_dir),
         "--category", KNOWLEDGE_CATEGORY, "--json", "-"],
        input=payload, capture_output=True, text=True,
    )
    if proc.returncode != 0:
        detail = proc.stderr.strip() or proc.stdout.strip()
        # 決定論 id の重複拒否は「記録済み」= 冪等成功 (gate 再実行/resume で必ず再発するため)。
        if "重複" in detail and entry.get("id", "") in detail:
            return
        raise RuntimeError(f"add_entry 失敗 (store={store_dir}): {detail}")


# ── handoff_notes 収集 (task-state nodes → summary へ合流) ─────────────────────
def _collect_handoff_notes(task_state: dict) -> list[dict]:
    """task-state.json の各 node の consumer 運用 field handoff_notes を distill 用に集約する。"""
    notes: list[dict] = []
    for n in (task_state.get("nodes", []) if isinstance(task_state, dict) else []):
        hn = n.get("handoff_notes")
        if not isinstance(hn, dict):
            continue
        if hn.get("friction_points") or hn.get("downstream_watchouts"):
            notes.append({
                "task_id": n.get("id"),
                "file": n.get("route_report"),
                "friction_points": hn.get("friction_points") or [],
                "downstream_watchouts": hn.get("downstream_watchouts") or [],
            })
    return notes


# ── route report 実体レーン (task-state nodes → route_report ファイル読取) ──────
def _collect_report_lessons(task_state: dict) -> list[dict]:
    """task-state nodes の route_report 実体から deviations[] と handover/handoff_notes を蒸留する。

    route-build-report の deviations[] (string 配列) と handover (string)、checklist-verification
    等の handoff_notes (string 配列形式) を lesson 候補として消費する新レーン。node 内 handoff_notes
    dict (friction_points/downstream_watchouts = _collect_handoff_notes) は不変・後方互換。
    deviation (計画逸脱) を handover (申し送り) より先に並べ limit 打ち切りで優先させる。
    route_report パスは task-state 記載のまま解決 (相対は cwd 基準)。report 不在・非 JSON は
    skip する fail-soft (gate 判定へは影響させない)。
    """
    deviations: list[dict] = []
    handovers: list[dict] = []
    for n in (task_state.get("nodes", []) if isinstance(task_state, dict) else []):
        if not isinstance(n, dict):
            continue
        report_path = n.get("route_report")
        if not report_path or not Path(report_path).is_file():
            continue
        try:
            report = json.loads(Path(report_path).read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            continue
        if not isinstance(report, dict):
            continue
        base_ref = {k: v for k, v in {
            "file": str(report_path), "task_id": n.get("id"), "route_id": report.get("route_id"),
        }.items() if v is not None}
        for dv in report.get("deviations") or []:
            if isinstance(dv, str) and dv.strip():
                deviations.append({"signal": "deviation", "message": _clip(dv),
                                   "source_ref": dict(base_ref)})
        notes = report.get("handoff_notes")
        note_items = [x for x in notes if isinstance(x, str) and x.strip()] \
            if isinstance(notes, list) else []
        handover = report.get("handover")
        if isinstance(handover, str) and handover.strip():
            note_items.append(handover)
        for note in note_items:
            handovers.append({"signal": "handover", "message": _clip(note),
                              "source_ref": dict(base_ref)})
    return deviations + handovers


# ── CLI ───────────────────────────────────────────────────────────────────────
def _build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(
        prog="record-task-graph-knowledge.py",
        description="task-graph build の外ループ完了ゲート + Loop A/Loop B knowledge 記録 (TG-C08)。",
    )
    p.add_argument("--target-plugin-slug", default=None)
    p.add_argument("--cycle-id", default=None)
    p.add_argument("--discovered-inbox", default=None,
                   help="省略時 resolve_build_dir(...)/discovered-tasks")
    p.add_argument("--plan-dir", default=None,
                   help="handback locator: blocked 時 handback へ planner --out-dir <PLAN_DIR> を含める "
                        "(TG-C06 が handoff.plan_dir から渡す・省略時は inbox のみの handback へフォールバック)")
    p.add_argument("--handoff", default=None,
                   help="blocked 時 next_steps[1] (/capability-build 再実行) の <handoff> placeholder を"
                        "実パスへ置換して完全形にする (TG-C06 が消費中 handoff パスを渡す・省略時はテンプレート表示)")
    p.add_argument("--task-events", default=None,
                   help="省略時 resolve_build_dir(...)/task-events.jsonl")
    p.add_argument("--task-state", default=None,
                   help="task-state.json (完了ゲート第2段: blocked node 残存で completion_gate:blocked"
                        " + gate ok 時の handoff_notes 収集)")
    p.add_argument("--summary-json", default=None,
                   help="summarize-task-progress.py 出力 (stall/handoff_notes を含む JSON)")
    p.add_argument("--target-knowledge-dir", default=None, help="Loop A: target harness の knowledge store dir")
    p.add_argument("--harness-knowledge-dir", default=str(_PLUGIN_ROOT / "knowledge"),
                   help="Loop B: harness-creator knowledge store dir")
    p.add_argument("--add-entry-path", default=str(
        _PLUGIN_ROOT / "skills/run-build-skill/templates/knowledge-skeleton/scripts/add_entry.py"))
    p.add_argument("--max-entries", type=int, default=DEFAULT_MAX_ENTRIES)
    p.add_argument("--dry-run", action="store_true")
    return p


def _resolve_default_paths(args) -> tuple[Path, Path | None]:
    """--discovered-inbox / --task-events を resolve_build_dir で補完する。

    戻り値 (inbox_dir, task_events_path)。task_events は不在なら None (distill が空を返す)。
    """
    if args.discovered_inbox and args.task_events:
        return Path(args.discovered_inbox), Path(args.task_events)
    build_dir = None
    if args.target_plugin_slug:
        build_dir = Path(_resolve_build_dir(args.target_plugin_slug, args.cycle_id))
    inbox = Path(args.discovered_inbox) if args.discovered_inbox else (
        build_dir / "discovered-tasks" if build_dir else None)
    events = Path(args.task_events) if args.task_events else (
        build_dir / "task-events.jsonl" if build_dir else None)
    return inbox, events


_SYMLINK_GENERATOR_REL = Path("scripts") / "build-claude-symlinks.py"
_SYMLINK_FIX_COMMAND = "bash scripts/sync-skills-to-claude.sh --apply"


def _resolve_repo_root_for_symlink_gate(task_state_path: str | None) -> Path | None:
    """--task-state の実パスから上方探索で repo root (生成器を持つ祖先) を解決する。

    実 run の task-state は repo (worktree) 配下 eval-log/ に置かれるため必ず解決でき、
    テスト (tmp dir) や生成器を持たない配布先では None を返して gate を fail-soft skip する
    (cwd 非依存: dispatcher の起動位置に関わらず task-state の位置だけで決定論解決する)。
    """
    if not task_state_path:
        return None
    cur = Path(task_state_path).resolve().parent
    for anc in (cur, *cur.parents):
        if (anc / _SYMLINK_GENERATOR_REL).is_file():
            return anc
    return None


def _check_claude_symlink_gate(task_state_path: str | None) -> dict:
    """完了ゲート第3段: .claude symlink drift (build 実体の .claude 未展開) を検査する。

    build 完了契約 (run-build-skill SKILL.md「build/更新後は sync 必須」) の機械層。宣言のみ
    だと task-graph モード (route 分散 build) で owner 不在のまま skip される実害が出た
    (2026-07-11 extract-system-blueprint)。drift は blocked とし fix_command を単体提示する。
    """
    root = _resolve_repo_root_for_symlink_gate(task_state_path)
    if root is None:
        return {"status": "skipped",
                "reason": "generator-absent (--task-state 未指定 or 生成器を持つ祖先なし)"}
    proc = subprocess.run(
        [sys.executable, str(root / _SYMLINK_GENERATOR_REL),
         "--plugins-dir", str(root / "plugins"),
         "--target-dir", str(root / ".claude"), "--check"],
        capture_output=True, text=True)
    if proc.returncode == 0:
        return {"status": "ok", "repo_root": str(root)}
    return {
        "status": "drift",
        "repo_root": str(root),
        "detail": (proc.stdout or proc.stderr).strip()[-400:],
        "fix_command": _SYMLINK_FIX_COMMAND,
    }


def main(argv: list[str] | None = None) -> int:
    argv = list(sys.argv[1:] if argv is None else argv)
    parser = _build_parser()
    try:
        args = parser.parse_args(argv)
    except SystemExit as exc:
        return int(exc.code) if isinstance(exc.code, int) else 2

    inbox_dir, task_events = _resolve_default_paths(args)
    if inbox_dir is None:
        print("--discovered-inbox か --target-plugin-slug のいずれかが必須", file=sys.stderr)
        return 2

    # inbox ディレクトリ不在 (外ループ未発火) と 実在+全件処理済 を全出力形で区別する。
    inbox_absent = not Path(inbox_dir).is_dir()

    # ── 外ループ完了ゲート第1段 (最優先): 未処理 discovered-task 残存 ──
    pending = scan_pending_discovered(inbox_dir)
    if pending:
        # 未処理に structural が 1 件でもあれば --approved 二段受理が必要 (未承認だとデッドロック)。
        needs_approval = any(p.get("change_level") == "structural" for p in pending)
        payload = {
            "completion_gate": "blocked",
            "inbox_absent": inbox_absent,
            "pending_discovered_tasks": [
                {"path": p["path"], "change_level": p.get("change_level"), "status": p.get("status")}
                for p in pending
            ],
            "needs_approval": needs_approval,
            "handback_command": build_handback_command(inbox_dir, args.plan_dir, needs_approval),
            "next_steps": build_next_steps(inbox_dir, args.plan_dir, needs_approval, args.handoff),
        }
        # gate 判定確定 event (S-11): TG-C05 集計や外部監査が判定を event 履歴から機械追跡できる。
        if not args.dry_run:
            append_gate_event(task_events, {
                "type": "build_blocked",
                "pending_count": len(pending),
                "needs_approval": needs_approval,
            })
        print(json.dumps(payload, ensure_ascii=False))
        return 1

    # ── 完了ゲート第2段: --task-state の blocked node 残存 ──
    task_state: dict | None = None
    if args.task_state:
        try:
            task_state = json.loads(Path(args.task_state).read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError) as exc:
            print(f"--task-state 読込/parse 失敗: {exc}", file=sys.stderr)
            return 2
    blocked_tasks = scan_blocked_tasks(task_state) if task_state is not None else []
    if blocked_tasks:
        payload = {
            "completion_gate": "blocked",
            "inbox_absent": inbox_absent,
            "blocked_tasks": blocked_tasks,
            "next_steps": build_blocked_task_next_steps(inbox_dir, args.handoff),
        }
        if not args.dry_run:
            append_gate_event(task_events, {
                "type": "build_blocked",
                "blocked_task_count": len(blocked_tasks),
            })
        print(json.dumps(payload, ensure_ascii=False))
        return 1

    # ── 完了ゲート第3段: .claude symlink drift (build 実体の未展開) ──
    symlink_gate = _check_claude_symlink_gate(args.task_state)
    if symlink_gate["status"] == "drift":
        payload = {
            "completion_gate": "blocked",
            "inbox_absent": inbox_absent,
            "claude_symlink_gate": symlink_gate,
            "next_steps": [
                f"{_SYMLINK_FIX_COMMAND}  # repo root: {symlink_gate['repo_root']}"
                " (唯一の生成器 build-claude-symlinks.py を冪等呼出)",
                "sync 後に本 TG-C08 を同一引数で再実行し completion_gate:ok を確認する",
            ],
        }
        if not args.dry_run:
            append_gate_event(task_events, {
                "type": "build_blocked",
                "claude_symlink_gate": "drift",
            })
        print(json.dumps(payload, ensure_ascii=False))
        return 1

    # ── gate ok: knowledge 蒸留 → entry 構築 ──
    summary: dict = {}
    if args.summary_json:
        try:
            summary = json.loads(Path(args.summary_json).read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError) as exc:
            print(f"--summary-json 読込/parse 失敗: {exc}", file=sys.stderr)
            return 2
    report_lessons: list[dict] = []
    if task_state is not None:
        collected = _collect_handoff_notes(task_state)
        if collected:
            summary.setdefault("handoff_notes", [])
            summary["handoff_notes"].extend(collected)
        report_lessons = _collect_report_lessons(task_state)

    lessons = distill_events(task_events, summary, limit=args.max_entries,
                             report_lessons=report_lessons)
    entries = [
        build_knowledge_entry(l, l.get("source_ref", {}), args.target_plugin_slug or "")
        for l in lessons
    ]

    loop_a_store = args.target_knowledge_dir
    loop_b_store = args.harness_knowledge_dir

    # ── dry-run: 書込せず entry 候補と経路のみを出す ──
    if args.dry_run:
        print(json.dumps({
            "completion_gate": "ok",
            "inbox_absent": inbox_absent,
            "claude_symlink_gate": symlink_gate,
            "dry_run": True,
            "loop_a_store": loop_a_store,
            "loop_b_store": loop_b_store,
            "entry_candidates": [_entry_for_store(e) for e in entries],
        }, ensure_ascii=False))
        return 0

    # ── 実書込: Loop B (常時担保) + Loop A (--target-knowledge-dir 提供時) ──
    # 完了ゲート (制御クリティカル) と knowledge 記録 (ベストエフォート) を疎結合化する (F2)。
    # completion_gate:"ok" は未処理 discovered-task 不在で既に確定済み。knowledge 記録の成否
    # (Loop A 未配線 / add_entry 失敗) を完了判定へ伝播させず、build 完了を巻き込んで落とさない。
    # store 不在/consult_at 未宣言は書込前に事前検知して skipped へ分類し (record_failed にしない)、
    # 書込は store 単位+entry 単位で try 隔離する (Loop A 失敗でも Loop B 継続・per-store 件数を出力)。
    add_entry_path = Path(args.add_entry_path)
    empty_reason = None
    stores: dict[str, dict] = {}
    for label, store in (("loop_a", loop_a_store), ("loop_b", loop_b_store)):
        if not store:
            stores[label] = {"status": "skipped", "recorded": 0, "reason": "store 未配線"}
            continue
        reason = check_store_ready(Path(store))
        stores[label] = ({"status": "skipped", "recorded": 0, "reason": reason} if reason
                         else {"status": "ok", "recorded": 0})
    display = {"loop_a": "Loop A", "loop_b": "Loop B"}
    if entries:
        for label in ("loop_a", "loop_b"):
            if stores[label]["status"] == "skipped":
                print(f"warning: {display[label]} 追記をスキップ ({stores[label]['reason']})",
                      file=sys.stderr)
    # 自己 build (target==harness-creator) では Loop A/B が同一 store へ縮退するため
    # 二重 add (決定論 id の重複拒否) を避けて 1 回だけ書く (loop_b 側を merged 扱い)。
    same_store = (stores["loop_a"]["status"] != "skipped" and stores["loop_b"]["status"] != "skipped"
                  and Path(loop_a_store).resolve() == Path(loop_b_store).resolve())
    if same_store:
        stores["loop_b"] = {"status": "merged_into_loop_a", "recorded": 0,
                            "reason": "Loop A と同一 store (自己 build 縮退)"}
    recorded = 0
    for entry in entries:
        wrote_any = False
        for label, store in (("loop_a", loop_a_store), ("loop_b", loop_b_store)):
            st = stores[label]
            if st["status"] not in ("ok", "failed"):
                continue
            try:
                write_knowledge(entry, Path(store), add_entry_path)
                st["recorded"] += 1
                wrote_any = True
            except (FileNotFoundError, RuntimeError) as exc:
                st["status"] = "failed"
                print(f"warning: {display[label]} への knowledge 記録失敗"
                      f" (完了は継続・他 store/entry は続行): {exc}", file=sys.stderr)
        if wrote_any:
            recorded += 1

    # 総合分類: 実書込失敗のみ record_failed。事前検知 skip は loop_a/b_skipped。
    # 蒸留 0 件は vacuous "ok" で偽装せず ok_no_lessons + empty_reason で明示区別する (F2)。
    if any(st["status"] == "failed" for st in stores.values()):
        record_status = "record_failed"
    elif not entries:
        record_status = "ok_no_lessons"
        empty_reason = _EMPTY_REASON_NO_LESSONS
    elif stores["loop_a"]["status"] == "skipped":
        record_status = "loop_a_skipped"
    elif stores["loop_b"]["status"] == "skipped":
        record_status = "loop_b_skipped"
    else:
        record_status = "ok"

    # gate 判定確定 event (S-11): completed 到達を event 履歴へ残す (--dry-run は上で return 済)。
    append_gate_event(task_events, {
        "type": "build_completed",
        "entries_recorded": recorded,
        "knowledge_record_status": record_status,
    })

    print(json.dumps({
        "completion_gate": "ok",
        "inbox_absent": inbox_absent,
        "claude_symlink_gate": symlink_gate,
        "entries_recorded": recorded,
        "knowledge_record_status": record_status,
        "empty_reason": empty_reason,
        "loop_a_store": loop_a_store,
        "loop_b_store": loop_b_store,
        "store_results": stores,
    }, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    sys.exit(main())
