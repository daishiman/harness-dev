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

from itertools import product

# --------------------------------------------------------------------------
# 語彙 (brief 由来。ここを勝手に増やさない)
# --------------------------------------------------------------------------

# canonical_aggregation.gate_faces — C16 / C17 / C18 / C22 の 4 面ちょうど。
# inventory の C09 description が 3 面と書いていたのは誤りで、P03 Y-07 で 4 面に確定。
GATE_FACES = {
    "selfcontained": "C16",
    "a11y-print": "C17",
    "language": "C18",
    "narrative": "C22",
}

GATE_IDS = ("selfcontained", "a11y-print", "language", "narrative")

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

# gate_id -> 起動する script (behavior 3 / gates[])
GATE_SCRIPTS = {
    "selfcontained": "verify-handout-selfcontained.py",
    "a11y-print": "verify-handout-a11y-print.py",
    "language": "verify-handout-language.py",
    "narrative": "verify-handout-narrative.py",
}

# gates[].requires — config を必須にするのは language / narrative の 2 面だけ
GATES_REQUIRING_CONFIG = ("language", "narrative")

# 各 script が受け取る argv (delegation_form / arguments)
GATE_ARGV = {
    "selfcontained": ("--html",),
    "a11y-print": ("--html",),
    "language": ("--html", "--config", "--out-dir"),
    "narrative": ("--html", "--config"),
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
