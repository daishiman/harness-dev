#!/usr/bin/env python3
# /// script
# name: live-trial-poll
# purpose: trial の完了を「成果物 glob 出現 + busy 不在の安定」で検知し、DONE/HARD_CAP/STALL/GATE の終端 exit を返す。
# inputs:
#   - argv: [--state-file <path.json>] [--max-ticks N] <out_glob> <session>
#   - env: INTERVAL(15) STABLE_TICKS(3) STALL_LIMIT(600) HARD_CAP(7200, 0=無制限) SESSION_ID CLAUDE_PROJECTS_DIR
# outputs:
#   - stdout: DONE/STALL/GATE/HARD_CAP/WARN 行
#   - exit: 0=DONE / 1=HARD_CAP / 2=STALL / 4=GATE / 5=TICK_BUDGET (--max-ticks 到達, 同一 state-file で再呼び) / 3=BLOCKED
# contexts: [C, E]
# network: false
# write-scope: state-file のみ
# dependencies: []
# requires-python: ">=3.10"
# ///
"""完了は「成果物の出現」を主シグナルにする (絶対ルール: 完了 = 成果物出現 + busy 不在)。

TUI の idle 推定だけだと未着手/tool 境界/質問返し停止を完走と誤判定するため、
成果物 (task が out/ に書く完了マーカー) の出現を必要条件にする。

観測ソースは二層:
  一次     = transcript JSONL (env SESSION_ID 指定時)。live-trial-status.py が
             turn_duration / pending tool_use で状態分類する。
  fallback = TUI capture-pane。SESSION_ID 未指定 / jsonl 未出現 (初 prompt 前) /
             parse 不能のとき。busy 判定は ASCII のみ — 旧 AG 版で「… ✻ 等の
             マルチバイトは standard BSD grep で不安定」と実測された知見を、
             Python re でも表示ゆらぎに強い ASCII マーカー (経過秒/token) の
             まま維持する。re の findall はマッチ 0 件でも例外を出さず [] を
             返す (set -e 下の grep 自殺問題は構造的に消滅) が、空リストを
             明示処理して busy=False に落とす。

jsonl 利用時の進捗 = bytes + STATE (busy 中の jsonl は完全無音 = mtime 停止が
正常なので、bytes 変化 or 状態変化を進捗とみなす)。subagents/*.jsonl bytes は
live-trial-status.transcript_bytes() が合算する (fork 内長時間実行の STALL 誤報
対策)。kill/crash したセッションは jsonl 上 BUSY_GENERATING のまま凍結 →
STALL になるので、STALL 時の tmux 生存確認 (STALL 分岐表 #1) は必須。

--state-file (JSON) は elapsed/stall/settle/prev (+gate_ticks/warned80) を
呼び越し永続化する。orchestrator の Bash ツールは 600s 上限で poll を kill
しうる — state-file なしの再呼びは counter が 0 に戻り STALL_LIMIT (>600s) /
HARD_CAP が構造的に実効しない。長時間 trial は「同じ --state-file で前景
chunk 呼びを終端 exit まで繰り返す」(SKILL.md poll 局面) が必須。

既定値の出典: run-elegant-review/references/convergence-policy.json
loop_bounds.trial_acceptance (stall_limit_s=600 / hard_cap_s=7200)。本 script は
env 上書き可能な既定値としてのみ保持し、SKILL.md 本文には生値を二重宣言しない。
"""
from __future__ import annotations

import argparse
import glob as globmod
import importlib.util
import json
import os
import re
import sys
import time
from pathlib import Path

# 処理中マーカー (ASCII のみ): スピナー行の経過秒 "(6s" "(12m 33s" / token 数
# "156 tokens" "1.0k tokens"。idle / 完了サマリ "Cogitated for 22s" /
# ステータスバー "(4h38m)" はマッチしない。
BUSY_RE = re.compile(r"\([0-9]+m? ?[0-9]*s|[0-9.]+k? tokens")

_STATE_KEYS = ("elapsed", "stall", "settle", "prev", "gate_ticks", "warned80")

EXIT_DONE = 0
EXIT_HARD_CAP = 1
EXIT_STALL = 2
EXIT_GATE = 4
EXIT_TICK_BUDGET = 5


def _load_sibling(stem: str):
    path = Path(__file__).resolve().parent / f"{stem}.py"
    spec = importlib.util.spec_from_file_location(stem.replace("-", "_"), path)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


def load_state(path: str | None) -> dict:
    state = {"elapsed": 0, "stall": 0, "settle": 0, "prev": "", "gate_ticks": 0, "warned80": 0}
    if path and Path(path).is_file():
        try:
            data = json.loads(Path(path).read_text(encoding="utf-8"))
            for k in _STATE_KEYS:
                if k in data:
                    state[k] = data[k]
        except (json.JSONDecodeError, OSError):
            pass  # 壊れた state は defaults から再開 (安全側)
    return state


def save_state(path: str | None, state: dict) -> None:
    if not path:
        return
    Path(path).write_text(
        json.dumps({k: state[k] for k in _STATE_KEYS}, ensure_ascii=False), encoding="utf-8"
    )


def resolve_jsonl(projects_dir: str, session_id: str) -> Path | None:
    for p in globmod.glob(os.path.join(projects_dir, "*", f"{session_id}.jsonl")):
        if Path(p).is_file():
            return Path(p)
    return None


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--state-file", default=None,
                    help="counters を JSON で呼び越し永続化 (長時間 trial は必須)")
    ap.add_argument("--max-ticks", type=int, default=0,
                    help="N tick で exit 5 (継続要)。0=無制限。前景 chunk 分割の決定論代替")
    ap.add_argument("out_glob", help="完了マーカー限定の glob (ワイルドカード全開は DONE 偽陽性源)")
    ap.add_argument("session")
    ns = ap.parse_args(argv)

    status_mod = _load_sibling("live-trial-status")
    backend = _load_sibling("live-trial-backend")

    interval = int(os.environ.get("INTERVAL", "15"))
    stable_ticks = int(os.environ.get("STABLE_TICKS", "3"))
    # 既定 600/7200 の正本は convergence-policy.json loop_bounds.trial_acceptance
    stall_limit = int(os.environ.get("STALL_LIMIT", "600"))
    hard_cap = int(os.environ.get("HARD_CAP", "7200"))
    session_id = os.environ.get("SESSION_ID", "")
    projects_dir = os.environ.get(
        "CLAUDE_PROJECTS_DIR", str(Path.home() / ".claude" / "projects")
    )

    st = load_state(ns.state_file)
    jsonl_path: Path | None = None
    ticks = 0

    while True:
        artifact = bool(globmod.glob(ns.out_glob))

        # 観測ソース決定: jsonl は初 prompt 後に生まれるため毎 tick 解決を試す
        if session_id and jsonl_path is None:
            jsonl_path = resolve_jsonl(projects_dir, session_id)
        src = "tui"
        state_label = ""
        result = None
        if jsonl_path is not None:
            result = status_mod.classify(jsonl_path)
        if result is not None:
            src = "jsonl"
            state_label = result["state"]
            any_busy = state_label != status_mod.STATE_IDLE
            bytes_total = status_mod.transcript_bytes(jsonl_path)
            progress = f"jsonl:{bytes_total}:{state_label}"
            if state_label == status_mod.STATE_WAITING:
                st["gate_ticks"] += 1
                if st["gate_ticks"] >= 2:
                    # 応答後の再 poll が即 GATE 再発しないようリセットして永続化
                    st["gate_ticks"] = 0
                    save_state(ns.state_file, st)
                    pending = ",".join(result["pending"]) or "-"
                    print(f"GATE: 対話入力待ち (pending: {pending}) — backend send-line で応答して"
                          f"再 poll (via jsonl, {st['elapsed']}s)")
                    return EXIT_GATE
            else:
                st["gate_ticks"] = 0
        else:
            st["gate_ticks"] = 0
            cap = backend.capture_pane(ns.session)
            matches = BUSY_RE.findall(cap)  # マッチ 0 件は [] (例外なし) — 明示処理
            prog = matches[-1] if matches else ""
            any_busy = bool(prog)
            progress = f"tui|{ns.session}:{prog}"

        if os.environ.get("DBG"):
            print(f"[DBG] t={st['elapsed']}s src={src} art={int(artifact)} busy={int(any_busy)} "
                  f"state={state_label} settle={st['settle']} stall={st['stall']} "
                  f"prog='{progress}'", file=sys.stderr)

        if artifact and not any_busy:
            # 成果物が出ていて、書き込みも止まった (busy 不在)。連続 STABLE_TICKS で完了確定。
            st["settle"] += 1
            st["stall"] = 0
            if st["settle"] >= stable_ticks:
                save_state(ns.state_file, st)
                print(f"DONE ({st['elapsed']}s) — 成果物出現 + busy 不在安定 (via {src})")
                return EXIT_DONE
        else:
            st["settle"] = 0
            # 進捗 (jsonl: bytes/STATE 変化、tui: busy の経過秒/token) が止まれば hang。
            # 成果物なしのまま止まれば未着手/hang。
            if progress == st["prev"]:
                # INTERVAL=0 (テスト高速化) でも STALL が構造的に到達不能にならないよう
                # 1 tick = 最低 1 秒相当で加算する (無限 busy loop の封鎖)
                st["stall"] += max(interval, 1)
            else:
                st["stall"] = 0
            if st["stall"] >= stall_limit:
                save_state(ns.state_file, st)
                where = "成果物はあるが書き込みが停止" if artifact else "無進捗・成果物なし = 未着手 or hang"
                print(f"STALL ({st['stall']}s {where}, via {src}, state:{state_label or '-'}) "
                      f"— STALL 分岐表へ")
                return EXIT_STALL
        st["prev"] = progress

        if hard_cap > 0 and not st["warned80"] and st["elapsed"] >= hard_cap * 4 // 5:
            print(f"WARN: HARD_CAP 80% 到達 ({st['elapsed']}s / {hard_cap}s) — 終端しない見込み"
                  "なら今 HARD_CAP を上げる (到達 kill は run 全損)")
            st["warned80"] = 1
        if hard_cap > 0 and st["elapsed"] >= hard_cap:
            save_state(ns.state_file, st)
            print(f"HARD_CAP ({st['elapsed']}s 到達) — 強制打ち切り。正常な超ロングランなら "
                  "HARD_CAP を上げる (verdict=BLOCKED で fail-closed)")
            return EXIT_HARD_CAP

        ticks += 1
        if ns.max_ticks and ticks >= ns.max_ticks:
            save_state(ns.state_file, st)
            print(f"TICK_BUDGET: {ticks} tick 消化 (elapsed {st['elapsed']}s) — 同一 "
                  "--state-file で再呼びして継続")
            return EXIT_TICK_BUDGET

        time.sleep(interval)
        st["elapsed"] += interval
        save_state(ns.state_file, st)


if __name__ == "__main__":
    raise SystemExit(main())
