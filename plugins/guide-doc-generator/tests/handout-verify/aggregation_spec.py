"""C09 /handout-verify の集約規則 CR-GATE-AGG の正解表 (オラクル)。

出典 (正本):
  - plugin-plans/guide-doc-generator/briefs/command-brief-C09.json
      behavior 手順 4 / 5 / 6
      canonical_aggregation (id: CR-GATE-AGG)
      failure_modes
  - plugin-plans/guide-doc-generator/briefs/RESOLUTION-P03.md Y-07

このモジュールは「正しい集約結果はこれである」という答えを固定するだけで、
実装 (commands/handout-verify.md) には一切依存しない。実装側が宣言する
verdict_table をこの表と突き合わせるのが test_aggregation_rule.py の役割。

標準ライブラリのみ。
"""

from __future__ import annotations

import json
from itertools import product
from pathlib import Path

# --------------------------------------------------------------------------
# 語彙
#
# ゲート面の名簿 (gate_id / 担当 component / 起動 script / 受け取る argv) の
# 正本は command-brief-C09.json#gates[] ただ 1 つであり、ここへは写さず実測で
# 導出する。正本が読めなければ import 時点で落とす (fail-closed)。
# --------------------------------------------------------------------------

BRIEF_PATH = (
    Path(__file__).resolve().parents[4]
    / "plugin-plans"
    / "guide-doc-generator"
    / "briefs"
    / "command-brief-C09.json"
)


def _load_brief():
    try:
        with BRIEF_PATH.open(encoding="utf-8") as handle:
            return json.load(handle)
    except (OSError, ValueError) as exc:  # pragma: no cover - 正本欠落は即座に落とす
        raise RuntimeError(f"契約の正本が読めない: {BRIEF_PATH} ({exc})") from exc


BRIEF = _load_brief()
_GATES = BRIEF["gates"]
if not _GATES:  # pragma: no cover
    raise RuntimeError(f"command-brief-C09.json の gates[] が空: {BRIEF_PATH}")

# gates[].gate_id -> component。C16 / C17 / C18 / C22 の 4 面ちょうど。
# inventory の C09 description が 3 面と書いていたのは誤りで、P03 Y-07 で 4 面に確定。
GATE_FACES = {g["gate_id"]: g["component"] for g in _GATES}

GATE_IDS = tuple(g["gate_id"] for g in _GATES)

# behavior 4: ゲート結果の 4 状態
GATE_STATES = ("pass", "fail", "error", "not-run")

# behavior 4: not-run に必ず添える理由
NOT_RUN_REASONS = (
    "config-missing",
    "config-not-normalized",
    "excluded-by-only",
    "script-absent",
)

# behavior 5 + --only の規約
VERDICTS = ("pass", "fail", "incomplete", "partial")

# gate_id -> 起動する script (gates[].script)
GATE_SCRIPTS = {g["gate_id"]: g["script"] for g in _GATES}

# gates[].requires に config を含む面 (config 必須ゲート)
GATES_REQUIRING_CONFIG = tuple(g["gate_id"] for g in _GATES if "config" in g.get("requires", []))

# 各 script が受け取る argv = gates[].requires + gates[].optional をフラグ化したもの
GATE_ARGV = {
    g["gate_id"]: tuple(f"--{name}" for name in list(g.get("requires", [])) + list(g.get("optional", [])))
    for g in _GATES
}

# script の exit code から状態への写像 (behavior 4)
EXIT_CODE_TO_STATE = {0: "pass", 1: "fail", 2: "error"}


# --------------------------------------------------------------------------
# 正解関数
# --------------------------------------------------------------------------


def aggregate(states, only_used: bool) -> str:
    """4 ゲートの状態から全体 verdict を返す (brief behavior 5 の逐語実装)。

    states: {gate_id: state} を 4 面ちょうど持つ dict。
    only_used: --only を使った部分実行かどうか。

    優先順位:
      1. fail か error が 1 本でもあれば fail        (behavior 5-a / failure_modes exit2)
      2. --only を使った実行は成功時でも partial      (arguments --only override_rule)
      3. not-run が 1 つ以上あれば incomplete        (behavior 5-c)
      4. 4 面すべて pass なら pass                   (behavior 5-b)

    not-run を pass 側へ畳む経路は存在しない。
    """
    if set(states) != set(GATE_IDS):
        raise ValueError(f"4 ゲート面ちょうどを渡すこと: {sorted(states)}")
    for gate, state in states.items():
        if state not in GATE_STATES:
            raise ValueError(f"未知の状態 {state!r} (gate={gate})")

    values = [states[g] for g in GATE_IDS]
    if any(v in ("fail", "error") for v in values):
        return "fail"
    if only_used:
        return "partial"
    if any(v == "not-run" for v in values):
        return "incomplete"
    return "pass"


def all_combinations():
    """(states, only_used) の全組み合わせ 4^4 * 2 = 512 件を返す。"""
    for combo in product(GATE_STATES, repeat=len(GATE_IDS)):
        states = dict(zip(GATE_IDS, combo))
        for only_used in (False, True):
            yield states, only_used


# --------------------------------------------------------------------------
# 実装が宣言する verdict_table の評価器
# --------------------------------------------------------------------------
#
# brief は集約規則を散文 (behavior 4-6) で持つだけで機械可読形式を規定していない。
# 集約が実際に規則どおりかを機械検査するため、本テスト群は実装 (handout-verify.md)
# へ「CR-GATE-AGG を id に持つ fenced json ブロックで verdict_table を宣言する」
# ことを要求する。表は first-match で評価する。
#
#   {"when": {...}, "verdict": "fail"}
#     when.any_state : list[str]  — いずれかのゲートがこの状態のとき真
#     when.all_states: list[str]  — 全ゲートがこの集合内の状態のとき真
#     when.only_used : bool       — --only 使用有無が一致するとき真
#     when が空 {} なら常に真 (既定行)
#   複数キーは AND。


class TableError(Exception):
    """verdict_table の宣言そのものが壊れている。"""


_WHEN_KEYS = {"any_state", "all_states", "only_used"}


def _match(when, states, only_used) -> bool:
    if not isinstance(when, dict):
        raise TableError(f"when は object でなければならない: {when!r}")
    unknown = set(when) - _WHEN_KEYS
    if unknown:
        raise TableError(f"未知の when キー: {sorted(unknown)}")
    values = [states[g] for g in GATE_IDS]
    if "any_state" in when:
        wanted = when["any_state"]
        if not isinstance(wanted, list):
            raise TableError("when.any_state は list")
        if not any(v in wanted for v in values):
            return False
    if "all_states" in when:
        wanted = when["all_states"]
        if not isinstance(wanted, list):
            raise TableError("when.all_states は list")
        if not all(v in wanted for v in values):
            return False
    if "only_used" in when:
        if bool(when["only_used"]) != bool(only_used):
            return False
    return True


def resolve(verdict_table, states, only_used) -> str:
    """宣言された verdict_table を first-match で評価して verdict を返す。"""
    if not isinstance(verdict_table, list) or not verdict_table:
        raise TableError("verdict_table は 1 行以上の list でなければならない")
    for row in verdict_table:
        if not isinstance(row, dict):
            raise TableError(f"verdict_table の行は object: {row!r}")
        verdict = row.get("verdict")
        if verdict not in VERDICTS:
            raise TableError(f"未知の verdict {verdict!r} (許容: {list(VERDICTS)})")
        if _match(row.get("when", {}), states, only_used):
            return verdict
    raise TableError(f"どの行にも一致しない入力がある: states={states} only_used={only_used}")


# 参考実装 (受入例 fixture が宣言する表と同じもの)。オラクルと一致することを
# test_aggregation_rule.py が固定するので、この表自体も検査対象になる。
REFERENCE_VERDICT_TABLE = [
    {"when": {"any_state": ["fail", "error"]}, "verdict": "fail"},
    {"when": {"only_used": True}, "verdict": "partial"},
    {"when": {"any_state": ["not-run"]}, "verdict": "incomplete"},
    {"when": {"all_states": ["pass"]}, "verdict": "pass"},
]
