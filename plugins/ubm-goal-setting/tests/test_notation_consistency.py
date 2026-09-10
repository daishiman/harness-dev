"""ドキュメントに埋め込まれた記法例が、validator の規則と食い違っていないかを検査する。

`golden-sample-weekly.md` は validate-goal-output.py に直接かけているので守られる。
しかし正本 (output-formats.md)・契約 (data-contract.md)・対話プロンプト (R3/R4/R5)・
agent 定義に埋め込まれた「例」は、どこからも実行されない。

0.3.41 で成果目標の記法を変えたとき、6本のファイルが旧記法のまま残り、それが CI で
赤くならなかったのはこのためだった。旧記法は validator を FAIL させない (裸の数字は
当時受理されていた) ので、劣化は誰にも観測されないまま保存され続ける。

このテストは、その観測されない領域に検査を入れる。規則の正本は validator 側にあり、
ここでは正規表現を再定義せず validate-goal-output.py から読み込む (二重定義を作ると、
規則を変えたときにこのテストだけが古い規則で緑になる)。
"""
from __future__ import annotations

import importlib.util
import re
from pathlib import Path

import pytest

PLUGIN_ROOT = Path(__file__).resolve().parents[1]
SKILL_ROOT = PLUGIN_ROOT / "skills/run-ubm-goal-setting"

# --- 台帳 -------------------------------------------------------------------
# 成果目標・行動目標の記法を本文に持つファイル。記法を変えたら、ここに挙がった
# 全ファイルを追随させる。新しく記法例を書いたファイルは、ここへ足す。
NOTATION_FILES = [
    SKILL_ROOT / "references/output-formats.md",      # 正本
    SKILL_ROOT / "references/data-contract.md",        # 契約・検査表
    SKILL_ROOT / "prompts/R3-step3-goal-setting.md",   # 成果目標のヒアリング
    SKILL_ROOT / "prompts/R4-step4-action-plan.md",    # 行動目標の設計
    SKILL_ROOT / "prompts/R5-step5-final-check.md",    # 最終確認
    SKILL_ROOT / "assets/golden-sample-weekly.md",     # 手本
    SKILL_ROOT / "assets/action-goals-best-practices.md",
    SKILL_ROOT / "assets/interview-quick-templates.md",
    SKILL_ROOT / "assets/execution-prompts.md",
    SKILL_ROOT / "SKILL.md",
    PLUGIN_ROOT / "agents/output-formatter.md",
    PLUGIN_ROOT / "agents/phase3-coordinator.md",
]

# 廃止済みの記法。NG 例・フォールバック説明としてなら本文に出てよいが、
# 「こう書く」という指示や手本として出てはいけない。
RETIRED_NOTATIONS = {
    "優先度グループ見出し": re.compile(r"^### 優先度[ABC]"),
}


def _load_validator():
    """validate-goal-output.py を module として読み込む (ハイフン名で import 不可)。"""
    path = SKILL_ROOT / "scripts/validate-goal-output.py"
    spec = importlib.util.spec_from_file_location("validate_goal_output", path)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


V = _load_validator().Validator


def iter_contribution_lines(text: str):
    """本文から `→ 売上貢献：…` を含む行を (行番号, 行) で列挙する。"""
    for i, line in enumerate(text.split("\n"), start=1):
        if V.CONTRIB_RX.search(line):
            yield i, line


# 「この行はわざと破っている」ことを示す印。行の中に現れる。
# 掛け算の `×` (U+00D7) を印に含めてはいけない。記法そのものが `50000 × 1 = 50000` と
# 書く以上、正しい行が軒並み免除されて検査が空洞化する。バツ印は `✗` (U+2717) と `❌`。
NEGATIVE_MARKER_RX = re.compile(r"[✗❌]|FAIL|NG|違反|不可|禁止|してはいけない|書かない|誤り")

# 違反例の集まりを開くラベル行。効き目は直後の非空行1つぶんだけ。
NEGATIVE_LABEL_RX = re.compile(
    r"^\s*(?:[-*>]\s*)*(?:\*\*)?\s*(?:[✗❌]|NG|FAIL|悪い例|やってはいけない|避ける)"
)


def is_negative_example(line: str, prev_lines: list[str]) -> bool:
    """この貢献行が「破ってみせるための例」なら True を返す。

    正本や契約は、規則を教えるために違反例をわざと書く
    （例: `- ✗ FAIL: → 売上貢献：50000 × 3ヶ月 = 150000`）。
    それらを規則違反として数えると、規則を丁寧に説明したファイルほど赤くなる。

    免除には**行に明示的な印があること**を要求する。印を要らないことにすると、
    免除される範囲が本文の書きぶり次第で伸び縮みし、検査が静かに空洞化する。
    印を要求すれば「違反例には印を付ける」という規律が本文側に課され、それは
    人間の読み手にとっても親切になる（どれが手本でどれが反例か一目で分かる）。

    ラベル行（`✗ NG例:` など）の効き目は直後の非空行1つぶんに限る。段落全体へ
    及ぼすと、ラベルが1つあるだけで以降の正しい例まで検査から外れる。

    Args:
        line: 判定対象の行そのもの。
        prev_lines: 直前の数行（末尾が直前行）。ラベル行の判定に使う。
    """
    if NEGATIVE_MARKER_RX.search(line):
        return True
    for prev in reversed(prev_lines):
        if not prev.strip():
            continue  # 空行は飛ばすが、非空行は最初の1つで打ち切る
        return bool(NEGATIVE_LABEL_RX.match(prev))
    return False


@pytest.mark.parametrize("path", NOTATION_FILES, ids=lambda p: p.name)
def test_contribution_examples_follow_the_rules(path: Path):
    """ドキュメント中の貢献額の例が C1（根拠の随伴）と C1e（計上期間）を満たす。"""
    assert path.exists(), f"台帳に載っているファイルが無い: {path}"
    lines = path.read_text(encoding="utf-8").split("\n")
    violations = []

    for lineno, line in iter_contribution_lines(path.read_text(encoding="utf-8")):
        if is_negative_example(line, lines[max(0, lineno - 4):lineno - 1]):
            continue
        amount, factors, raw, count_unit = V._parse_contribution(line)
        if amount is None:
            continue
        # C1: 式か括弧の根拠のどちらかが随伴していること
        if factors is None and not V.CONTRIB_BASIS_RX.match(raw):
            violations.append(f"{path.name}:{lineno} 根拠のない裸の数字: {raw}")
        # C1c: 式の検算
        if factors is not None and factors[0] * factors[1] != factors[2]:
            violations.append(f"{path.name}:{lineno} 式が合っていない: {raw}")
        # C1e: 件数に期間単位を掛けていないこと
        if count_unit and V.PERIOD_COUNT_UNIT_RX.match(count_unit):
            violations.append(f"{path.name}:{lineno} 件数に期間単位「{count_unit}」: {raw}")

    assert not violations, "\n".join(violations)


@pytest.mark.parametrize("path", NOTATION_FILES, ids=lambda p: p.name)
def test_retired_notations_are_not_used_as_instructions(path: Path):
    """廃止した記法が、手本や指示として残っていない。"""
    found = []
    for i, line in enumerate(path.read_text(encoding="utf-8").split("\n"), start=1):
        for name, rx in RETIRED_NOTATIONS.items():
            if rx.search(line):
                found.append(f"{path.name}:{i} 廃止済みの{name}: {line.strip()}")
    assert not found, "\n".join(found)
