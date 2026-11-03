"""1ターンの問いは、回（「（1回目）」「（2回目）」）ごとに3問までであることを検査する。

数え方の正本は `agents/phase3-coordinator.md` の CONST_001。
ターンのテンプレートが回に分かれているときは、回ごとに1回の発話として数える。
問いの番号は回をまたいで通しにする（「ターン1A の問2」などの参照を変えない）ので、
番号の大きさではなく、回の中にある問いの行の数を数える。
- 番号付きの問いがある回: 番号付きの行と、そのあとに置く「？」で終わる確認の行を数える
  （番号付きの問いの前に置く導入の1文「実績はどうでしたか？」は数えない。2文目からは数える）
- 番号付きの問いが無い回: 「？」で終わる行を数える
- 注記（※）・矢印（→）・箇条書き（`- ` `* `）の行は数えない（箇条書きは親が確かめる項目の一覧）

発話の正本の書き方はファイルで違う:
- prompts/R*.md は `> ` で始まる引用行が発話
- assets/interview-quick-templates.md は ``` で囲んだブロックが発話
"""
from __future__ import annotations

import re
from pathlib import Path

PLUGIN_ROOT = Path(__file__).resolve().parents[1]
SKILL_ROOT = PLUGIN_ROOT / "skills/run-ubm-goal-setting"
LIMIT = 3

# 問いではなく選択肢を番号で並べているターン（1つを選んでもらう1問）
CHOICE_LIST_TURNS = {
    ("R2-step2-gap-analysis.md", "", "ターン2C"),
}

_TURN = re.compile(r"^(?:#{2,5}\s+|\*\*)(ターン[^*:：（(\s]*)")
_ROUND = re.compile(r"（([0-9]+)回目）")
_NUMBERED = re.compile(r"^[0-9]+[.．]\s")
# 注記（※）・矢印（→）・箇条書き（- *）は問いではない
_ASKING = re.compile(r"^(?![※→*-]).*[？?]）?$")


def count_questions(text: str, quoted: bool) -> dict[tuple[str, str, int], int]:
    """(フロー名, ターン名, 回) ごとに、答えを待つ問いの数を数える。"""
    # 回ごとに [番号付きの数, 番号付きより前の「？」の数, 番号付きより後の「？」の数]
    tally: dict[tuple[str, str, int], list[int]] = {}
    turn: str | None = None
    flow = ""
    rnd = 1
    fence = False
    for line in text.splitlines():
        if line.startswith("```"):
            fence = not fence
            continue
        if not fence:
            m = _TURN.match(line)
            if m:
                turn, rnd = m.group(1), 1
                continue
            if line.startswith("## "):
                # 面接テンプレートは週報・月報・期報で同じターン名を使うので、フローで分ける
                # （プロンプトはターン名がファイル内で一意なので、フロー名を持たない）
                turn = None
                if not quoted:
                    flow = line[3:].split("（")[0].strip()
                continue
        if turn is None:
            continue
        if quoted:
            if not line.startswith(">"):
                continue
            body = line[1:].strip()
        else:
            if not fence:
                continue
            body = line.strip()
        r = _ROUND.search(body)
        if r:
            rnd = int(r.group(1))
            body = _ROUND.sub("", body).strip()
        if not body:
            continue
        t = tally.setdefault((flow, turn, rnd), [0, 0, 0])
        if _NUMBERED.match(body):
            t[0] += 1
        elif _ASKING.match(body):
            t[2 if t[0] else 1] += 1
    counts: dict[tuple[str, str, int], int] = {}
    for key, (numbered, lead, after) in tally.items():
        # 番号付きの問いの前は導入の1文だけを数えない（CONST_001）
        n = numbered + after + max(lead - 1, 0) if numbered else lead
        if n:
            counts[key] = n
    return counts


def _documents() -> list[tuple[Path, bool]]:
    prompts = sorted((SKILL_ROOT / "prompts").glob("R*.md"))
    return [(p, True) for p in prompts] + [(SKILL_ROOT / "assets/interview-quick-templates.md", False)]


def test_each_round_has_at_most_three_questions():
    over, seen = [], 0
    for path, quoted in _documents():
        for (flow, turn, rnd), n in count_questions(path.read_text(encoding="utf-8"), quoted).items():
            seen += 1
            if n > LIMIT and (path.name, flow, turn) not in CHOICE_LIST_TURNS:
                where = f"{flow} " if flow else ""
                over.append(f"{path.name}: {where}{turn}（{rnd}回目）に {n} 問")
    assert seen >= 30, f"数えた回が少なすぎる（{seen}）。ターン見出しや発話の書式が変わっていないか"
    assert not over, "1回の発話は3問まで（CONST_001）。「（1回目）」「（2回目）」に分ける:\n" + "\n".join(over)


def test_split_turn_counts_per_round():
    """回に分けたターンは回ごとに数え、番号は通しのまま（R1 ターン1A の2回目は問1〜3）。"""
    counts = count_questions((SKILL_ROOT / "prompts/R1-step1-current-review.md").read_text(encoding="utf-8"), True)
    assert counts[("", "ターン1A", 1)] == 1  # 「この情報に変更はありますか？」
    assert counts[("", "ターン1A", 2)] == 3
    assert counts[("", "ターン1B", 1)] == 2 and counts[("", "ターン1B", 2)] == 2


def test_counter_flags_unsplit_turn():
    """回に分けずに4問を並べたターンは超過として数える（検査が空振りしないことの確認）。"""
    text = "\n".join([
        "**ターン9Z**:",
        "> 1. 一つ目", "> 2. 二つ目", "> 3. 三つ目", "> 4. 四つ目",
    ])
    assert count_questions(text, True) == {("", "ターン9Z", 1): 4}
    split = text.replace("> 4. 四つ目", "> （2回目）\n> 4. 四つ目")
    assert count_questions(split, True) == {("", "ターン9Z", 1): 3, ("", "ターン9Z", 2): 1}


def test_counter_counts_unnumbered_confirmation():
    """番号付きの問いのあとの「？」の確認は1問と数え、前に置く導入の1文と注記は数えない。"""
    text = "\n".join([
        "**ターン9Y**:",
        "> 実績はどうでしたか？",
        "> 1. 一つ目", "> 2. 二つ目", "> 3. 三つ目",
        "> ※ 補足はありますか？",
        "> この計算で合っていますか？",
    ])
    assert count_questions(text, True) == {("", "ターン9Y", 1): 4}
    only_confirm = "**ターン9X**:\n> この情報に変更はありますか？"
    assert count_questions(only_confirm, True) == {("", "ターン9X", 1): 1}
    two_leads = text.replace("> 実績はどうでしたか？", "> 実績はどうでしたか？\n> 先週は忙しかったですか？")
    assert count_questions(two_leads, True) == {("", "ターン9Y", 1): 5}  # 導入の2文目は数える
