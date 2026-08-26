#!/usr/bin/env python3
# /// script
# name: validate-journal-output
# version: 0.5.0
# purpose: 生成した日次ジャーナル Markdown が正本フォーマット (frontmatter・骨格15ブロック・
#          目標4階層の期間/残り/目標・3ジャーナル×3小節・フェーズ別課題チェックシート・
#          毎日固定の習慣) を満たすかを保存前に検査する決定論ゲート。習慣の件数と
#          検査範囲は references/daily-habits.json が正本 (ここに件数を焼かない)。
#          未置換プレースホルダと空セクションを FAIL にする。
# inputs:
#   - argv: --file <path> [--expected-number N] [--expected-date YYYY-MM-DD]
#   - fs: {skill}/references/daily-habits.json (欠落・破損は exit 2)
# outputs:
#   - stdout: PASS/FAIL と違反一覧
#   - exit: 0=PASS / 1=FAIL / 2=引数不正・ファイル読み込み不能 (fail-closed)
# contexts: [E]
# network: false
# write-scope: none
# dependencies: []
# requires-python: ">=3.9"
# ///
"""日次ジャーナルの保存前バリデーション。

「フォーマットに合わせる」ことより「やったことを構造的にまとめる」ことが目的なので、
本文の中身までは縛らない。検査するのは骨格の存在と順序、各枠が実際に埋まっていること、
テンプレのプレースホルダが残っていないこと、そして daily-habits.json が宣言する固定習慣の
記録が `search_scopes` の節にあること (H01/H02) に絞る。文章の質は評価しない。
"""
from __future__ import annotations

import argparse
import json
import re
import sys
from pathlib import Path

# 毎日固定の習慣リストの正本。build-journal-context.py と同じファイルを見る (SSOT 一本化)。
DAILY_HABITS_PATH = Path(__file__).resolve().parents[1] / "references" / "daily-habits.json"


def load_daily_habits() -> list[dict]:
    """固定習慣リストを読む。欠落・壊れは H01 検査を素通しさせないため即時終了する。"""
    try:
        data = json.loads(DAILY_HABITS_PATH.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        sys.stderr.write(f"validate-journal-output: daily-habits.json を読めません: {exc}\n")
        sys.exit(2)
    # top-level が dict でない (例: JSON 配列) と .get が AttributeError になり、
    # 宣言した exit 2 ではなく traceback 付き exit 1 で落ちる。
    if not isinstance(data, dict):
        sys.stderr.write("validate-journal-output: daily-habits.json の top-level が object ではありません\n")
        sys.exit(2)
    habits = data.get("habits")
    if not isinstance(habits, list) or not habits:
        sys.stderr.write("validate-journal-output: daily-habits.json の habits が空です\n")
        sys.exit(2)
    for i, h in enumerate(habits):
        for problem in habit_schema_problems(h, i):
            sys.stderr.write(f"validate-journal-output: daily-habits.json {problem}\n")
            sys.exit(2)
    return habits


def habit_schema_problems(h: object, i: int) -> list[str]:
    """habit 1件の形の不備を列挙する。1件でもあれば読み込み不能 (exit 2) 扱い。

    SKILL.md も interview-map も「項目を増減するときは daily-habits.json だけを編集する」と
    利用者をこの編集面へ誘導している。にもかかわらず `label` 欠落は `habit['label']` の
    KeyError → traceback + exit 1 になり、宣言した「破損 = exit 2」と食い違っていた。
    さらに `keywords` を list でなく文字列で書くと 1 文字ずつ照合され、`"G"` が
    どこかに当たるだけで H01 が無条件 PASS になる (SSOT 破損時の fail-open を実測)。
    形の検査を読み込み時に寄せて、下流の素の添字アクセスを安全にする。
    """
    where = f"habits[{i}]"
    if not isinstance(h, dict):
        return [f"{where} が object ではありません"]
    problems = []
    for key in ("label", "target_section"):
        if not isinstance(h.get(key), str) or not h[key].strip():
            problems.append(f"{where} の {key} が非空文字列ではありません")
    kws = h.get("keywords")
    if not isinstance(kws, list) or not kws or not all(isinstance(k, str) and k for k in kws):
        problems.append(f"{where} の keywords が非空文字列の配列ではありません")
    scopes = h.get("search_scopes")
    if scopes is not None:
        if not isinstance(scopes, list) or not scopes:
            problems.append(f"{where} の search_scopes が非空配列ではありません")
        else:
            for j, s in enumerate(scopes):
                if not isinstance(s, dict):
                    problems.append(f"{where}.search_scopes[{j}] が object ではありません")
                    continue
                if not isinstance(s.get("heading"), str) or not s["heading"]:
                    problems.append(f"{where}.search_scopes[{j}] の heading がありません")
                # level を検査しないと、`"level": "2"` (文字列) で section_lines の
                # `lv == level` が常に偽になり、記録が正しく書かれた本文が H01 で
                # FAIL する。利用者は本文を直し続けても直らない (実測)。
                # heading の欠落は exit 2 で原因を名指しするので、level も同じ扱いに揃える。
                lv = s.get("level", 2)
                if not isinstance(lv, int) or isinstance(lv, bool) or not 1 <= lv <= 6:
                    problems.append(f"{where}.search_scopes[{j}] の level が 1-6 の整数ではありません")
    return problems

HEADING_RE = re.compile(r"^#\s*No\.\s*(\d+)\s*[-–—]\s*ジャーナル\s*[（(]\s*(\d{4}-\d{2}-\d{2})\s*[)）]\s*$")
FILE_DATE_RE = re.compile(r"^(\d{4}-\d{2}-\d{2})\.md$")
# 角括弧型 (`[名前]`) に加えて波括弧型 (`{分類}` `{journal_number}`) も拾う。
# 正本テンプレ (references/output-format.md) が使うのは波括弧型で、
# 「テンプレを貼って埋め忘れる」という最も起きやすい事故はこちら側で起きる。
#
# ただし波括弧を「中身が英数字か和文なら何でも」で拾うと、ジャーナル本文に書かれた
# 正当な記述 (`/invoice/{id}` のような API パス、コード片) を未置換プレースホルダとして
# X01 で FAIL にする (実測)。X01 の対象は正本テンプレが実際に使う名前だけに限定する。
# テンプレへプレースホルダを足すときはここにも足す (output-format.md と対で管理する)。
# なお「対で管理する」という上の約束は、導入時点で既に破れていた (`{名前}` の登録漏れ。
# output-format.md:70 の `- {名前}: {何をしてもらったか}` が正本)。約束を人手の注意力へ
# 預けたのが原因なので、tests 側で output-format.md の `{...}` 集合がこのタプルに
# 含まれることを機械的に固定してある (test_brace_placeholders_cover_output_format)。
BRACE_PLACEHOLDERS = (
    "番号", "名前", "終了日", "何をしてもらったか", "journal_number", "N", "YYYY-MM-DD",
    "分類", "日数", "days_remaining",
)
PLACEHOLDER_RE = re.compile(
    r"\[(?:数字|名前|日数|感謝の内容|分類|2ヶ月目標|3ヶ月目標|1ヶ月目標|1週間目標|yyyy/mm/dd)\]"
    r"|\{(?:" + "|".join(re.escape(p) for p in BRACE_PLACEHOLDERS) + r")\}"
)
HRULE_RE = re.compile(r"^\s*(?:-{3,}|\*{3,}|_{3,})\s*$")
HTML_COMMENT_RE = re.compile(r"<!--.*?-->", re.DOTALL)
# コードフェンスの中身は Obsidian が描画せずそのまま文字として出す。HTML コメントと
# 同じ「書いてはあるが埋め込まれない」クラスなので、埋め込みの有無を見る検査からは
# 同じように外す。外さないと ```![[人生の究極の目的]]``` で Y02 が PASS する (実測)。
FENCED_CODE_RE = re.compile(r"^(?P<f>`{3,}|~{3,}).*?(?:\n(?P=f)`*~*[ \t]*$|\Z)", re.M | re.S)


def visible_text(text: str) -> str:
    """Obsidian が実際に描画する部分だけを残す。埋め込み判定の前処理。"""
    return FENCED_CODE_RE.sub(" ", HTML_COMMENT_RE.sub(" ", text))
# 目標4階層の「- 期間：」が取るべき値の形。節全体ではなくこの行の値だけに掛ける。
# 区切りは半角ハイフンのみ。`/` も通していたが、output-format.md も G02 の
# メッセージも「YYYY-MM-DD〜YYYY-MM-DD」と宣言しており、検査だけが緩い状態だった。
# 検査が文書より緩いと、文書を読んで直した人が「直したのに何も変わらない」を経験する。
DATE_RANGE_RE = re.compile(
    r"\d{4}-\d{2}-\d{2}\s*[〜～~]\s*\d{4}-\d{2}-\d{2}"
)
# 正本が要求する究極目的の transclusion。frontmatter の tags は has_review_tag() が見る。
TRANSCLUSION_RE = re.compile(r"!\[\[[^\]]*人生の究極の目的[^\]]*\]\]")

# 見出し照合の既定は完全一致。部分一致にすると `## 目標` が `## 今週の習慣目標` に、
# `## 感謝` が `## 感謝したくないリスト` に化けても S01 が通ってしまい、
# 「骨格が正本どおりか」という S01 の目的そのものが崩れる。
# 部分一致を許すのは、日付や番号が可変で完全一致できない見出しだけに限る。
EXACT, CONTAINS = "exact", "contains"

# 2ヶ月階層の見出しは正本が `2ヶ月目標`。`3ヶ月目標` は旧表記で、既存ジャーナルを
# 再検証したときに骨格違反にしないため受理だけ続ける。タプルの先頭が正本。
QUARTERLY_HEADING = ("2ヶ月目標", "3ヶ月目標")

# (見出しレベル, 照合する文字列, 照合モード) を出現順で並べた骨格の正本。
# 照合する文字列はタプルにでき、その場合は「どれか 1 つに一致すれば可」を意味する。
REQUIRED_OUTLINE = [
    (1, "人生の究極の目標", EXACT),
    (1, "ジャーナル", CONTAINS),  # `# No.388 - ジャーナル（2026-08-16）` は可変部を含む
    (2, "人生の究極目的", EXACT),
    (2, "目標", EXACT),
    (3, "1年目標", EXACT),
    (3, QUARTERLY_HEADING, EXACT),
    (3, "1ヶ月目標", EXACT),
    (3, "1週間目標", EXACT),
    (2, "感謝", EXACT),
    (2, "【禁止事項】", EXACT),
    (2, "【タスク】", EXACT),
    (2, "【行動のジャーナル】", EXACT),
    (2, "【時間のジャーナル】", EXACT),
    (2, "【お金のジャーナル】", EXACT),
    (1, "フェーズ別 課題チェックシート", EXACT),
    (1, "原理原則 チェックシート", EXACT),
]

JOURNAL_SECTIONS = ["【行動のジャーナル】", "【時間のジャーナル】", "【お金のジャーナル】"]
JOURNAL_SUBSECTIONS = ["現状を確認する", "効果性を評価する", "更に良くする方法はないか"]
GOAL_SECTIONS = ["1年目標", QUARTERLY_HEADING, "1ヶ月目標", "1週間目標"]
PHASE_SECTIONS = ["【0→1】", "【1→10】", "【10→100】"]

# `# 原理原則 チェックシート` (原理原則チェックシート) が持つ H2 設問群の正本。
# 人間向けの正本は references/principle-checklist.md で、増減時は両方を同時に直す。
# 照合は見出し行の部分一致で行うため、設問文の末尾の記号ゆれ (？ / ?) に依存しない
# 十分に固有な前半を持たせてある。(1)(2) の対は末尾の括弧まで含めて区別する。
PRINCIPLE_SECTIONS = [
    "毎月の利益と口座残高の状況がわかるようになっていますか",
    "右肩上がりになっていますか",
    "原理原則を学び見直す状態は作れていますか",
    "歴史の共有ができていますか？（1）",
    "歴史の共有ができていますか？（2）",
    "支出は前回から下げられましたか",
    "今の行動を積み上げた先に上記のチェックが全て埋まる行動になっていますか",
    "川上に繋がる描きができスケジュールが配置されていますか",
    "次回、UBMで原理原則を学び確認する日は入っていますか",
    "あなたと共に同じ学びを共有するメンバーは増えていますか",
    "あなたの教え子からリーダーが生まれていますか",
]


def headings(lines: list[str]) -> list[tuple[int, str, int]]:
    """(レベル, テキスト, 行番号) の一覧。"""
    out = []
    for i, line in enumerate(lines, start=1):
        s = line.strip()
        if not s.startswith("#"):
            continue
        level = len(s) - len(s.lstrip("#"))
        text = s[level:].strip()
        if text:
            out.append((level, text, i))
    return out


def frontmatter_block(lines: list[str]) -> str:
    """先頭の `---` で挟まれた YAML frontmatter 本体。無ければ ""。

    本文中の水平線 (`---`) を終端と取り違えないよう、1 行目が `---` の場合だけ探す。
    """
    if not lines or lines[0].strip() != "---":
        return ""
    for i, line in enumerate(lines[1:], start=1):
        if line.strip() == "---":
            return "\n".join(lines[1:i])
    return ""


def has_review_tag(fm: str) -> bool:
    """frontmatter の `tags` が review を含むか。

    「`- review` という行がどこかにある」だけを見ると、`aliases:` 配下の
    `- review` でも通り (偽陰性)、正しい inline 記法 `tags: [review]` を
    FAIL にする (偽陽性)。どちらも tags キーに紐づけていないことが原因なので、
    キーを特定してからその値だけを見る。
    """
    lines = fm.splitlines()
    for i, line in enumerate(lines):
        m = re.match(r"^tags\s*:(?P<inline>.*)$", line)
        if m is None:
            continue
        inline = m.group("inline").strip()
        if inline:  # `tags: [review, x]` / `tags: review`
            return "review" in re.findall(r"[A-Za-z0-9_-]+", inline)
        # ブロック記法。`- item` が続く間だけを値とみなす。インデントを必須にすると
        # YAML として妥当なゼロインデント記法 (`tags:` の次行に `- review`) を
        # Y01 で FAIL にする (偽陽性を実測)。終端は「次のキー行が現れたとき」で見る。
        for nxt in lines[i + 1 :]:
            if not nxt.strip():
                continue
            item = re.match(r"^\s*-\s*(?P<v>.+?)\s*$", nxt)
            if item is None:
                break  # `- ` で始まらない = 別のキーへ移った
            if item.group("v").strip("\"'") == "review":
                return True
        return False
    return False


def needle_label(needle: str | tuple[str, ...]) -> str:
    """違反メッセージに出す見出し名。別表記候補は「または」で並べる。"""
    return needle if isinstance(needle, str) else " または ".join(needle)


def heading_matches(text: str, needle: str | tuple[str, ...], mode: str) -> bool:
    """見出しテキストの照合。exact は装飾記号 (`◇` や末尾コロン) だけ落として完全一致。

    needle がタプルのときは別表記の候補列で、どれか 1 つに一致すれば可とする。
    """
    candidates = (needle,) if isinstance(needle, str) else needle
    if mode == CONTAINS:
        return any(c in text for c in candidates)
    stripped = text.strip().strip("◇◆・:：").strip()
    return any(stripped == c for c in candidates)


def section_lines(
    lines: list[str], level: int, needle: str | tuple[str, ...], mode: str = EXACT
) -> list[str] | None:
    """指定見出し直下の本文行 (同レベル以上の次見出しまで) を返す。見出しが無ければ None。"""
    start = None
    for i, line in enumerate(lines):
        s = line.strip()
        if not s.startswith("#"):
            continue
        lv = len(s) - len(s.lstrip("#"))
        text = s[lv:].strip()
        if start is None:
            if lv == level and heading_matches(text, needle, mode):
                start = i + 1
            continue
        if lv <= level:
            return lines[start:i]
    if start is None:
        return None
    return lines[start:]


# `-` に加えて `*` と番号付き (`1.` `1)`) も箇条書きとして数える。正本は `-` を使うが、
# 「枠が埋まっているか」を見る C0x/J02 で番号付きリストを空扱いにすると、
# 正しく書かれた記録を FAIL にしてしまう (書式の強制は S01/G01 の役目ではない)。
BULLET_RE = re.compile(r"^(?:[-*+]|\d+[.)])\s*")

# チェックボックス行 (`- [ ]` / `- [x]`)。ネストしたサブ項目も数えるため先頭の空白を許す。
# P02 と K02 が同じ形の行を数えるので、片方だけ書式が緩む/締まることのないよう共有する。
CHECKBOX_RE = re.compile(r"^\s*-\s*\[[ xX]\]")


def content_bullets(body: list[str]) -> list[str]:
    items = []
    for line in body:
        s = line.strip()
        if HRULE_RE.match(line) or not BULLET_RE.match(s):
            continue
        s = BULLET_RE.sub("", s, count=1)
        s = re.sub(r"^\[[ xX]\]\s*", "", s).strip()
        if s:
            items.append(s)
    return items


def deprecation_notices(lines: list[str]) -> list[str]:
    """旧表記の見出しが使われていることを利用者へ知らせる (違反にはしない)。

    REQUIRED_OUTLINE の見出しタプルは「先頭が正本、以降は受理だけ続ける旧表記」という規約。
    その規約からそのまま導出するので、次に別の見出しを改称したときも通知経路が自動で付く。

    違反にしないのは後方互換のため。旧表記で書かれた既存ジャーナルの再検証を落とすと、
    過去分を一括で書き換えるまで検査そのものが使えなくなる。一方、黙って受理するだけだと
    「前回ジャーナルを継承して今日の分を書く」運用の中で旧表記が自己複製し続け、
    正本へ寄る契機が永久に来ない。通す・けれど毎回知らせる、が正しい強さになる。
    """
    notices: list[str] = []
    written = {text for _, text, _ in headings(lines)}
    for _, needle, mode in REQUIRED_OUTLINE:
        if not isinstance(needle, tuple):
            continue
        canonical, legacy_names = needle[0], needle[1:]
        for legacy in legacy_names:
            if any(heading_matches(t, legacy, mode) for t in written):
                notices.append(
                    f"D01: 旧表記の見出し「{legacy}」が使われています。正本は「{canonical}」です"
                    "（前回ジャーナルの継承で複製され続けるため、次回分から書き換えてください）"
                )
    return notices


def validate(
    path: Path,
    expected_number: int | None,
    expected_date: str | None,
    habits: list[dict],
) -> list[str]:
    violations: list[str] = []
    text = path.read_text(encoding="utf-8")
    lines = text.splitlines()

    # --- ファイル名と見出しの整合 ---
    fm = FILE_DATE_RE.match(path.name)
    file_date = fm.group(1) if fm else None
    if not fm:
        violations.append(f"F01: ファイル名が YYYY-MM-DD.md 形式ではありません: {path.name}")

    heading = None
    for line in lines:
        m = HEADING_RE.match(line.strip())
        if m:
            heading = m
            break
    if heading is None:
        violations.append("F02: 「# No.<数字> - ジャーナル（YYYY-MM-DD）」の見出しがありません")
    else:
        number, heading_date = int(heading.group(1)), heading.group(2)
        if file_date and heading_date != file_date:
            violations.append(
                f"F03: 見出しの日付 {heading_date} がファイル名の日付 {file_date} と一致しません"
                "（ファイル日付＝見出し日付＝振り返る日）"
            )
        if expected_number is not None and number != expected_number:
            violations.append(
                f"F04: 通し番号 No.{number} が期待値 No.{expected_number} と一致しません"
                "（build-journal-context の採番を使ってください）"
            )
        if expected_date is not None and heading_date != expected_date:
            violations.append(f"F05: 見出しの日付 {heading_date} が対象日 {expected_date} と一致しません")

    # --- 正本が要求する frontmatter と transclusion ---
    # Obsidian 側の検索性 (tags) と究極目的の埋め込みは正本仕様の一部。
    # 見出しだけ揃っていても、これが欠けると vault 内で他のジャーナルと同じに扱われない。
    if not has_review_tag(frontmatter_block(lines)):
        violations.append("Y01: 先頭の YAML frontmatter に `tags: - review` がありません")
    # H01 と同じ理由で HTML コメントを外してから探す。コメント内の `![[...]]` は
    # Obsidian で埋め込まれないので、生テキスト照合だと「究極目的が表示されている」
    # という Y02 の判定根拠が成立しないまま PASS する (実測)。
    if not TRANSCLUSION_RE.search(visible_text(text)):
        violations.append("Y02: 「人生の究極の目的」の transclusion (![[...]]) がありません")

    # --- 骨格の存在と順序 ---
    hs = headings(lines)
    cursor = 0
    for level, needle, mode in REQUIRED_OUTLINE:
        found = None
        for idx in range(cursor, len(hs)):
            lv, txt, _ = hs[idx]
            if lv == level and heading_matches(txt, needle, mode):
                found = idx
                break
        if found is None:
            violations.append(
                f"S01: 必須見出しが見つからないか順序が不正です: {'#' * level} {needle_label(needle)}"
            )
        else:
            cursor = found + 1

    # --- 目標4階層: 期間・残り・目標が揃っているか ---
    for goal in GOAL_SECTIONS:
        # 別表記候補は「正本 (タプル先頭) を優先」で 1 つの節に決め、本文とラベルを
        # 同じ探索から取る。両者を別々に決めると、2ヶ月・3ヶ月が併存し本文で旧表記が
        # 先に現れたとき body は 3ヶ月節・ラベルは「2ヶ月目標」というズレが起き、
        # さらに正本の節を空にしても手前の完全な旧表記節が検査を通す fail-open になる
        # (どちらも実測で再現済み)。正本が存在するなら必ず正本を検査対象にする。
        candidates = (goal,) if isinstance(goal, str) else goal
        goal, body = next(
            (
                (c, found)
                for c in candidates
                if (found := section_lines(lines, 3, c)) is not None
            ),
            (needle_label(goal), None),
        )
        if body is None:
            continue  # S01 で既に報告済み
        joined = "\n".join(body)
        values: dict[str, str] = {}
        for field in ("期間", "残り", "目標"):
            # ラベル行の存在だけを見ると `- 目標：` (値なし) が通り、
            # 「各枠が実際に埋まっている」という本 script の宣言目的が空振りする。
            m = re.search(rf"^\s*-\s*{field}\s*[：:](?P<value>.*)$", joined, re.MULTILINE)
            if m is None:
                violations.append(f"G01: {goal} に「- {field}：」の行がありません")
            elif not m.group("value").strip():
                violations.append(f"G03: {goal} の「- {field}：」が空です")
            else:
                values[field] = m.group("value")
        # 日付範囲は「- 期間：」の値そのものに掛ける。節全体へ掛けると、期間を
        # 「今週いっぱい」と書いても同じ節の別行 (目標本文の日付など) が要件を
        # 満たしてしまい、G02 が fail-open になる (実測で exit 0 を再現済み)。
        # 期間行が無い / 空のときは G01・G03 が既に報告しているので二重に出さない。
        if "期間" in values and not DATE_RANGE_RE.search(values["期間"]):
            violations.append(f"G02: {goal} の期間が YYYY-MM-DD〜YYYY-MM-DD 形式で書かれていません")

    # --- 中身が埋まっているか ---
    for needle, rule, minimum in (
        ("人生の究極目的", "C01", 1),
        ("感謝", "C02", 1),
        ("【禁止事項】", "C03", 1),
    ):
        body = section_lines(lines, 2, needle)
        if body is None:
            continue
        if len(content_bullets(body)) < minimum:
            violations.append(f"{rule}: {needle} に箇条書きが {minimum} 件以上必要です")

    task_body = section_lines(lines, 2, "【タスク】")
    if task_body is not None:
        first_sub = next(
            (i for i, l in enumerate(task_body) if l.strip().startswith("### ")), None
        )
        if first_sub is None:
            violations.append("C04: 【タスク】に分類見出し（### 【分類名】）が1つ以上必要です")
        # 分類見出しより前の箇条書きは「分類の下」ではない。全体で数えると、
        # 見出しだけ作って中身を書かなかったケースを取りこぼす。
        elif not content_bullets(task_body[first_sub + 1:]):
            violations.append("C05: 【タスク】の分類の下に箇条書きが1件以上必要です")

    for section in JOURNAL_SECTIONS:
        body = section_lines(lines, 2, section)
        if body is None:
            continue
        for sub in JOURNAL_SUBSECTIONS:
            sub_body = section_lines(body, 3, sub)
            if sub_body is None:
                violations.append(f"J01: {section} に「### {sub}」がありません")
            elif not content_bullets(sub_body):
                violations.append(f"J02: {section} の「{sub}」が空です（箇条書き1件以上）")

    phase_body = section_lines(lines, 1, "フェーズ別 課題チェックシート")
    if phase_body is not None:
        for phase in PHASE_SECTIONS:
            if not any(phase in l for l in phase_body if l.strip().startswith("## ")):
                violations.append(f"P01: フェーズ別課題チェックシートに「## ◇{phase}」がありません")
        checks = [l for l in phase_body if CHECKBOX_RE.match(l)]
        if not checks:
            violations.append("P02: フェーズ別課題チェックシートにチェックボックス行がありません")

    # --- 原理原則チェックシート (`# 原理原則 チェックシート`) ---
    # ブロック自体の有無は S01 が見る (REQUIRED_OUTLINE の最後の要素)。ここは中身を見る。
    # PHASE 側と違い、このブロックは「11 設問を毎回丸ごと出す」ことが利用者の要求そのもので、
    # 抜粋・要約されたチェックシートを受理するかどうかは、この検査の厳しさが直接決める。
    # 見出し名に「原理原則」を冠してあるので `# フェーズ別 課題チェックシート` とは
    # 部分一致でも衝突しない。EXACT を明示して、将来 CONTAINS へ緩めたくなったときに
    # 「衝突しないから CONTAINS でよい」と考える余地を残さない。
    principle_body = section_lines(lines, 1, "原理原則 チェックシート", mode=EXACT)
    if principle_body is not None:
        for key in PRINCIPLE_SECTIONS:
            # 11 設問すべての存在を要求する。「1 つでもあれば可」にすると、設問を 3 つだけ
            # 抜粋したチェックシートが PASS で通り、「毎回丸ごと出す」という要求が
            # 検査を素通りして静かに空洞化する。欠落は 1 件ずつ出す (Phase5 の修正ループが
            # 違反行単位で直すため、まとめて 1 行にすると何を足すのかが読めない)。
            body = section_lines(principle_body, 2, key, mode=CONTAINS)
            if body is None:
                violations.append(f"K01: チェックシートに「## ◇{key}…」の設問がありません")
                continue
            # チェックボックスの探索は設問セクションごとに行う。principle_body 全体から
            # 1 行でも見つかれば可にすると、1 設問だけ埋まっていて残り 10 設問が見出しだけ、
            # という状態を通す (P02 と同じ形の fail-open)。
            if not any(CHECKBOX_RE.match(l) for l in body):
                violations.append(f"K02: チェックシートの「{key}…」にチェックボックス行がありません")

    # --- 未置換プレースホルダ ---
    for i, line in enumerate(lines, start=1):
        m = PLACEHOLDER_RE.search(line)
        if m:
            violations.append(f"X01: L{i} にテンプレートのプレースホルダ {m.group(0)} が残っています")

    # --- 毎日固定の習慣がヒアリングされ記録されたか ---
    # 達成/未達は問わない。「毎日確認する」契約なので、どちらであれ本文に痕跡が残るはず。
    # 痕跡ゼロ = そもそも聞かなかった、と判定する。
    #
    # 探索範囲は search_scopes が指す小節本文に限る。本文全体を substring 検索すると、
    # 禁止事項の定型行 (「漫画・YouTubeへ逃げない」)・H1 見出し・必須セクション名
    # (【行動のジャーナル】)・チェックシートの固定設問 (「発信、営業…」) にキーワードが
    # 常在するため、6 習慣中 4 件が骨格さえ正しければ常に PASS する死んだ検査になる。
    violations.extend(check_daily_habits(lines, habits))

    return violations


def check_daily_habits(lines: list[str], habits: list[dict]) -> list[str]:
    """search_scopes が指す小節の本文だけを見て習慣の記録有無を判定する。"""
    out: list[str] = []
    for habit in habits:
        scopes = habit.get("search_scopes")
        if not scopes:
            # scope 未宣言を「全文検索でよい」と読み替えると v1 の死んだ検査へ逆戻りする。
            # 検査できない habit は素通しではなく違反として可視化する。
            out.append(
                f"H02: 習慣「{habit.get('label', habit.get('id'))}」に search_scopes が"
                "宣言されていません（daily-habits.json を修正してください）"
            )
            continue

        keywords = habit.get("keywords") or []
        found = False
        missing_scope = False
        for scope in scopes:
            body = section_lines(lines, scope.get("level", 2), scope["heading"])
            if body is None:
                missing_scope = True
                continue
            # HTML コメントは Obsidian で表示されない = 記録として読まれない。
            # 生行のまま照合すると `<!-- Gridノート -->` を貼るだけで H01 が通り、
            # 「本文に痕跡が残るはず」という判定根拠が成立しなくなる。
            #
            # コードフェンスは Y02 とは理由が違う。フェンスの中身は Obsidian でも
            # 読者に見えるので「表示されない」を根拠にはできない。除外するのは、
            # フェンスに入るのはその日の記録ではなく貼り付けたテンプレ・例・コマンドで、
            # そこにキーワードが常在すると H01 が v1 の死んだ検査へ戻るためである。
            # 帰結として、記録をフェンスの中だけに書くと H01 は「記録がありません」と
            # 言う (fail-closed 側の誤り)。素の箇条書きで書けば解消する。
            joined = visible_text("\n".join(body))
            if any(kw in joined for kw in keywords):
                found = True
                break
        if found:
            continue
        # 見出しが無い (missing_scope) 場合も違反にする。欠落は S01/J01 が別途報告するが、
        # 「書く場所が無かった」を H01 の免罪符にすると記録漏れが見えなくなる。
        # 検査の粒度は search_scopes が指すセクション。メッセージで target_section
        # (より細かい小節) だけを名指しすると「どこを直せば緑になるか」がズレる。
        where = " / ".join(s["heading"] for s in scopes)
        out.append(
            f"H01: 毎日の習慣「{habit['label']}」の記録が {where} セクションに"
            f"ありません（達成/未達のいずれかを、推奨は {habit['target_section']} へ書く）"
        )
    return out


def main() -> int:
    ap = argparse.ArgumentParser(description="日次ジャーナルの保存前バリデーション")
    ap.add_argument("--file", required=True)
    ap.add_argument("--expected-number", type=int, default=None)
    ap.add_argument("--expected-date", default=None)
    args = ap.parse_args()

    path = Path(args.file)
    if not path.is_file():
        sys.stderr.write(f"validate-journal-output: ファイルがありません: {path}\n")
        return 2
    try:
        violations = validate(path, args.expected_number, args.expected_date, load_daily_habits())
        # 違反ではないので exit code には効かせない。同じ try で包むのは、読み直しが
        # ここで失敗しても「1=違反あり / 2=読み込み不能」の契約から外れないようにするため。
        notices = deprecation_notices(path.read_text(encoding="utf-8").splitlines())
    except (OSError, UnicodeDecodeError) as exc:
        # UnicodeDecodeError は OSError を継承しないため個別に拾う。
        # 拾わないと非 UTF-8 ファイルが traceback + exit 1 となり、
        # frontmatter が宣言する「1=違反あり / 2=読み込み不能」の契約が壊れる。
        sys.stderr.write(f"validate-journal-output: 読み込みに失敗しました: {exc}\n")
        return 2

    # notice は PASS / FAIL のどちらでも出す。FAIL のときに黙ると、違反を直して
    # 再実行して PASS した瞬間にしか旧表記へ気づけず、通知が一番効く周回で消える。
    for n in notices:
        print(f"NOTICE: {n}")

    if violations:
        print(f"FAIL: {path.name} — 違反 {len(violations)} 件")
        for v in violations:
            print(f"  - {v}")
        return 1
    print(f"PASS: {path.name} — 違反 0 件")
    return 0


if __name__ == "__main__":
    sys.exit(main())
