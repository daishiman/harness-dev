"""InterviewData の各フィールドが「聞く問い」と「出力する層」まで閉じているかを検査する。

正本に足した規則やフィールドが、利用する側へ降りないまま CI を通った。

- #37（前回のやらないことが守れたか。週報・月報）と #38（北原さんの原則。月報だけ）は期報・1年に
  出さないフィールドなのに、月報の骨格を読み替えで継承する期報・1年へ見出しがそのまま漏れた。
- #9（前回成果実績）は、値を聞くターンが R1 にも面接テンプレートにも無かった。
- 旧基準の言い回しは、語を少し変えただけで固定文字列の grep をすり抜けた。

どの対応も、どこからも実行されない文書どうしの約束なので、赤くならなかった。
ここでは data-contract.md §3.1 の「集める問い」「出力する層」の2列を台帳とし、次を検査する。

(a) 2列が全フィールドで埋まっていて、書式どおりであること
(b) 週報・月報テンプレートの `{{変数}}` が DC のフィールドに対応し、その層を「出力する層」が含むこと
(c) 月報に出て期・年に出ないフィールドの見出しが、期報節・1年節に「出力しない」と書かれていること
(d) 「集める問い」に書いたターンの見出しが、参照先のファイルに実在すること
(e) 旧基準の言い換えが、プラグイン内の文書に残っていないこと
"""
from __future__ import annotations

import re
from pathlib import Path

PLUGIN_ROOT = Path(__file__).resolve().parents[1]
SKILL_ROOT = PLUGIN_ROOT / "skills/run-ubm-goal-setting"
DATA_CONTRACT = SKILL_ROOT / "references/data-contract.md"
OUTPUT_FORMATS = SKILL_ROOT / "references/output-formats.md"
PROMPTS_DIR = SKILL_ROOT / "prompts"
IQT = SKILL_ROOT / "assets/interview-quick-templates.md"

LAYERS = ("週", "月", "期", "年")
# output-formats.md の層の節。節は見出しから、フェンスの外にある次の `## ` 見出しの手前まで。
LAYER_SECTIONS = {
    "週": "週報（1週間目標）フォーマット",
    "月": "月報（1ヶ月目標）フォーマット",
    "期": "期報（3ヶ月目標）フォーマット",
    "年": "1年目標（1年）フォーマット",
}
# interview-quick-templates.md（DC の表では iqt と略す）の層別フロー。
IQT_FLOWS = {
    "週報": "週報（1週間目標）フロー",
    "月報": "月報（1ヶ月目標）フロー",
    "期報": "期報（3ヶ月目標）フロー",
}

# --- 許可リスト --------------------------------------------------------------
# DC のフィールド名とテンプレート変数名が一致しないものだけを、理由つきで置く。
# 解決の順: DC のフィールド名 → DC 備考の「テンプレート変数 `{{x}}` の生成元」→
# §3.1.1/§3.1.2 の構造のサブフィールド（親へ）→ 下の許可リスト。
# どれにも当たらない変数は FAIL にする（新しい変数を足したら DC か許可リストに書く）。

# 月報の提出用セクションの変数。管理用と同じ値を提出用の粒度で写したもので、接尾辞を外して解決する。
SUBMISSION_SUFFIX = "_submission"

# 名前違い: テンプレート変数 → (DC フィールド, 理由)
RENAMED = {
    "user_name": ("name", "【名前】の表示値"),
    "business_description": ("business", "【事業内容】の表示値"),
    "phase_label": ("phase", "【確認された情報】の表示用ラベル"),
    "type_label": ("type", "【確認された情報】の表示用ラベル"),
    "sales_diff": ("prev_sales_diff", "前回ブロックの売上差分"),
    "action_change": ("prev_action_change", "前回ブロックの行動の挽回"),
    "current_sales_target": ("sales_target", "今回（今週・今月・今期）の売上目標"),
    "current_other_target": ("other_targets", "今回の売上以外の成果目標"),
    "current_action_target": ("actions", "月報の今月の行動目標"),
    "outcome_1": ("actions", "週報の行動目標のグループ見出し。actions[].outcome_group の値"),
    "outcome_2": ("actions", "同上（2つ目のグループ）"),
    "criteria": ("decision_criteria", "【今週の判断基準】"),
    "project_tasks": ("projects", "【プロジェクト別タスク】。projects の出力形"),
}

# 派生: InterviewData のフィールドではない値（DC フィールドに対応させない理由）
DERIVED = {
    "start_date": "GoalConfig.target_period から決まる期間",
    "end_date": "GoalConfig.target_period から決まる期間",
    "week_summary": "週報の冒頭の要約。全フィールドから output-formatter が書く",
    "month_summary": "月報の冒頭の要約。全フィールドから output-formatter が書く",
    "week_context": "【今週の位置づけ】。上位の月報・期報の文脈から書く",
    "previous_monthly_sales": "PastSummary の user_info.prev_sales（DC §2）。InterviewData には持たない",
    "key_metric_1": "【今週の最重要数字】。#12・#13 から選ぶ見出しKPI",
    "key_number": "【今月の最重要数字】。#12 と期報の当月配分から書く",
    "contribution_total": "#13 の売上貢献の合計（#12 との突合に使う）",
    "checklist": "振り返りチェックリストの関係構築ブロック。行動・成果の行を写さない固定の点検項目",
    "missed_days": "週末に利用者が記入する欄（ヒアリング時点では空）",
}

# 既知の欠落: DC に生成元のフィールドが無い変数。直したらここから消す（陳腐化は下の検査で落ちる）。
KNOWN_GAPS = {
    "sales_action_change": "【前回の売上に対して未達を挽回するための行動】。DC の挽回は #35（行動）だけで、売上の挽回のフィールドが無い",
    "other_action_change": "【前回の売上以外の成果に対して未達を挽回するための行動】。同上（成果の挽回のフィールドが無い）",
}

# 変数を持たずに出力する層: (フィールド, 層) → (節の中に必ずある文字列, 理由)
LITERAL_EVIDENCE = {
    ("not_doing", "週"): ("｜やらない：", "週報は独立見出しを持たず、日付索引の行末に注記する"),
    ("yearly_monthly_sales_goal", "月"): ("月間売上到達点：", "月報は1年目標の値を注記行で同値継承する（変数なし）"),
    ("yearly_continuous_consult_count", "月"): ("継続コンサル人数：", "同上"),
}

# --- 読み取り ----------------------------------------------------------------
FENCE_RX = re.compile(r"^\s*(`{3,}|~{3,})")
VAR_RX = re.compile(r"\{\{([a-z][a-z0-9_]*)\}\}")  # 日本語のプレースホルダ（{{項目名}} など）は書式の枠なので対象外
TEMPLATE_HEADING_RX = re.compile(r"^## (【[^】]+】)")
LAYER_CELL_RX = re.compile(r"^(?P<layers>—|[週月期年](?:・[週月期年])*)(?:（(?P<reason>.+)）)?$")
NOT_OUTPUT_RX = re.compile(r"出力しない|出力禁止")
TURN_TOKEN_RX = re.compile(
    r"(?<![A-Za-z0-9])R(?P<prompt>[1-5])(?![0-9])"
    r"|(?P<iqt>iqt)"
    r"|(?P<flow>週報|月報|期報)ターン(?P<flow_turn>\d+(?:\.\d+)?)"
    r"|ターン(?P<turn>\d[0-9A-Za-z.]*(?:-[0-9A-Za-zぁ-ゖァ-ヺ一-鿿]+)*)"
)
QUESTION_COL, LAYER_COL, FIELD_COL = "集める問い", "出力する層", "フィールド"


def read(path: Path) -> str:
    return path.read_text(encoding="utf-8")


def section_lines(text: str, title: str) -> list[tuple[str, bool]]:
    """`## {title}` から、フェンスの外の次の `## ` 見出しの手前までを (行, フェンスの中か) で返す。"""
    out: list[tuple[str, bool]] = []
    fence, inside = None, False
    for line in text.splitlines():
        marker = FENCE_RX.match(line)
        if marker:
            token = marker.group(1)[0]
            if fence is None:
                fence = token
            elif fence == token:
                fence = None
            if inside:
                out.append((line, True))
            continue
        if fence is None and line.startswith("## "):
            if inside:
                break
            inside = line[3:].strip() == title
        if inside:
            out.append((line, fence is not None))
    return out


def dc_tables(text: str) -> list[tuple[list[str], list[dict[str, str]]]]:
    """§3.1 の表（全37フィールドの表と1年層の到達点の表）を (見出し行, 行) で返す。"""
    start = text.index("### 3.1 全37フィールド一覧")
    end = text.index("### 3.1.1 ", start)
    tables: list[tuple[list[str], list[dict[str, str]]]] = []
    header: list[str] | None = None
    for line in text[start:end].splitlines():
        if not line.startswith("|"):
            header = None
            continue
        cells = [c.strip() for c in line.strip().strip("|").split("|")]
        if header is None:
            header = cells
            tables.append((header, []))
            continue
        if set(line) <= set("|-: "):
            continue
        assert len(cells) == len(header), f"列数が見出しと合わない（セルに | が入っている？）: {line}"
        tables[-1][1].append(dict(zip(header, cells)))
    return tables


def dc_rows(text: str) -> list[dict[str, str]]:
    return [row for _, rows in dc_tables(text) for row in rows]


def dc_fields(rows: list[dict[str, str]]) -> dict[str, dict[str, str]]:
    return {r[FIELD_COL]: r for r in rows if r[FIELD_COL] != "（欠番）"}


def dc_template_aliases(rows: list[dict[str, str]]) -> dict[str, str]:
    """備考に「テンプレート変数 `{{x}}` の生成元」と宣言された変数 → フィールド。"""
    aliases = {}
    for r in rows:
        for var in re.findall(r"テンプレート変数\s*`\{\{([a-z][a-z0-9_]*)\}\}`", r.get("備考", "")):
            aliases[var] = r[FIELD_COL]
    return aliases


def dc_subfield_parents(text: str) -> dict[str, str]:
    """§3.1.1 projects・§3.1.2 habit_check の構造のサブフィールド → 親フィールド。"""
    parents = {}
    rx = re.compile(r"^### 3\.1\.\d+ (?P<parent>[a-z_]+)（#\d+）の構造\n(?P<body>.*?)(?=^### )", re.M | re.S)
    for m in rx.finditer(text):
        for name in re.findall(r"^\| ([a-z_]+) \|", m["body"], re.M):
            parents[name] = m["parent"]
    return parents


def parse_layers(cell: str) -> tuple[str, ...] | None:
    """「出力する層」のセル → 層のタプル（`—` は空）。書式違反は None。"""
    m = LAYER_CELL_RX.match(cell)
    if not m:
        return None
    if m["layers"] == "—":
        return () if m["reason"] else None  # 出力しないなら理由が要る
    layers = tuple(m["layers"].split("・"))
    if layers != tuple(l for l in LAYERS if l in layers):
        return None  # 重複か、週・月・期・年の順でない
    return layers


def turn_refs(cell: str) -> tuple[list[tuple[str, str, str]], list[str]]:
    """「集める問い」のセル → ([(\"R\", プロンプト番号, ターン) | (\"iqt\", 層, ターン)], 書き方の誤り)。

    `R1 ターン1A／ターン1B` のように、裸のターンは直前の R に属する。
    iqt のターンは `iqt 週報ターン1／月報ターン2` のように層の語を付ける。
    """
    refs: list[tuple[str, str, str]] = []
    errors: list[str] = []
    context: str | None = None
    for m in TURN_TOKEN_RX.finditer(cell):
        if m["prompt"]:
            context = "R" + m["prompt"]
        elif m["iqt"]:
            context = "iqt"
        elif m["flow"]:
            if context != "iqt":
                errors.append(f"{m.group(0)} の前に iqt が無い")
            else:
                refs.append(("iqt", m["flow"], m["flow_turn"]))
        elif context is None or not context.startswith("R"):
            errors.append(f"{m.group(0)} がどの R プロンプトのターンか分からない（iqt のターンは層の語を付ける）")
        else:
            refs.append(("R", context[1:], m["turn"]))
    return refs, errors


def turn_exists(kind: str, where: str, turn: str) -> bool:
    if kind == "R":
        files = sorted(PROMPTS_DIR.glob(f"R{where}-*.md"))
        if len(files) != 1:
            return False
        return bool(re.search(rf"^\*\*ターン{re.escape(turn)}(?:\*\*|（)", read(files[0]), re.M))
    lines = section_lines(read(IQT), IQT_FLOWS[where])
    return any(re.match(rf"### ターン{re.escape(turn)}:", line) for line, fenced in lines if not fenced)


def template_vars(formats_text: str, layer: str) -> list[tuple[str, str | None]]:
    """層の節のテンプレート（フェンスの中）の英字変数を (変数, 直前の `## 【…】` 見出し) で返す。"""
    out: list[tuple[str, str | None]] = []
    heading = None
    for line, fenced in section_lines(formats_text, LAYER_SECTIONS[layer]):
        if not fenced:
            continue
        m = TEMPLATE_HEADING_RX.match(line)
        if m:
            heading = m.group(1).replace("（提出）", "")
        out.extend((var, heading) for var in VAR_RX.findall(line))
    return out


SKIP = "（DC フィールドに対応させない）"


def resolver(contract_text: str, rows: list[dict[str, str]]):
    fields = dc_fields(rows)
    aliases = dc_template_aliases(rows)
    parents = dc_subfield_parents(contract_text)

    def resolve(var: str) -> str | None:
        base = var.removesuffix(SUBMISSION_SUFFIX)
        if base in fields:
            return base
        for table in (aliases, parents):
            if base in table:
                return table[base]
        if base in RENAMED:
            return RENAMED[base][0]
        if base in DERIVED or base in KNOWN_GAPS:
            return SKIP
        return None

    return resolve


def variable_errors(formats_text: str, contract_text: str, rows: list[dict[str, str]]) -> list[str]:
    """(b) 週報・月報テンプレートの変数と DC の「出力する層」の対応の食い違い。"""
    fields = dc_fields(rows)
    resolve = resolver(contract_text, rows)
    errors = []
    for layer in ("週", "月"):
        section = "\n".join(line for line, _ in section_lines(formats_text, LAYER_SECTIONS[layer]))
        seen: set[str] = set()
        for var, heading in template_vars(formats_text, layer):
            field = resolve(var)
            if field is None:
                errors.append(f"{layer}: {{{{{var}}}}}（{heading}）が DC のフィールドにも許可リストにも無い")
            elif field != SKIP:
                seen.add(field)
                layers = parse_layers(fields[field][LAYER_COL]) or ()
                if layer not in layers:
                    errors.append(f"{layer}: {{{{{var}}}}}（{heading}）は {field} だが、DC の出力する層 "
                                  f"{fields[field][LAYER_COL]!r} に {layer} が無い")
        for name, row in fields.items():
            if layer not in (parse_layers(row[LAYER_COL]) or ()) or name in seen:
                continue
            literal = LITERAL_EVIDENCE.get((name, layer))
            if literal and literal[0] in section:
                continue
            errors.append(f"{layer}: DC は {name} を{layer}に出力すると書くが、テンプレートに対応する変数が無い")
    return errors


def not_output_errors(formats_text: str, contract_text: str, rows: list[dict[str, str]]) -> tuple[int, list[str]]:
    """(c) 月報に出て期・年に出ないフィールドの見出しが、期報・1年の節で「出力しない」と同じ行にあるか。"""
    fields = dc_fields(rows)
    resolve = resolver(contract_text, rows)
    targets: dict[tuple[str, str], str] = {}
    for var, heading in template_vars(formats_text, "月"):
        field = resolve(var)
        if field in (None, SKIP) or heading is None:
            continue
        layers = parse_layers(fields[field][LAYER_COL]) or ()
        for layer in ("期", "年"):
            if "月" in layers and layer not in layers:
                targets[(heading, layer)] = field
    errors = []
    for (heading, layer), field in sorted(targets.items()):
        lines = [line for line, _ in section_lines(formats_text, LAYER_SECTIONS[layer])]
        if not any(heading in line and NOT_OUTPUT_RX.search(line) for line in lines):
            errors.append(f"{LAYER_SECTIONS[layer]} に「{heading} … 出力しない」の行が無い（{field} は{layer}に出さない）")
    return len(targets), errors


# --- (a) 2列が埋まっている ------------------------------------------------------
def test_dc_tables_have_question_and_layer_columns():
    tables = dc_tables(read(DATA_CONTRACT))
    assert len(tables) == 2, f"§3.1 の表の数が想定（全37フィールドの表＋1年層の到達点の表）と違う: {len(tables)}"
    for header, rows in tables:
        assert header[-2:] == [QUESTION_COL, LAYER_COL], f"表の末尾2列が「集める問い」「出力する層」でない: {header}"
        assert rows
    numbered = [r for r in tables[0][1] if r[FIELD_COL] != "（欠番）"]
    assert len(numbered) == 37, f"番号つきフィールドの数が37でない: {len(numbered)}"


def test_every_field_has_question_and_layer():
    errors = []
    for row in dc_rows(read(DATA_CONTRACT)):
        name, question, layer = row[FIELD_COL], row[QUESTION_COL], row[LAYER_COL]
        if not question:
            errors.append(f"{name}: 集める問いが空")
        elif question.startswith("—"):
            if not re.fullmatch(r"—（.+）", question):
                errors.append(f"{name}: 聞かない理由が `—（理由）` の形でない: {question!r}")
        elif not turn_refs(question)[0]:
            errors.append(f"{name}: 集める問いにターンが1つも無い: {question!r}")
        if parse_layers(layer) is None:
            errors.append(f"{name}: 出力する層が `週・月・期・年` の組合せ（この順）か `—（理由）` でない: {layer!r}")
    assert not errors, "\n".join(errors)


def test_layer_cell_parser():
    assert parse_layers("週・月・期・年") == ("週", "月", "期", "年")
    assert parse_layers("週・月（期・年は出さない）") == ("週", "月")
    assert parse_layers("—（専用見出しなし）") == ()
    assert parse_layers("—") is None  # 理由なし
    assert parse_layers("月・週") is None  # 順が違う
    assert parse_layers("") is None


# --- (b) テンプレートの変数と出力する層 ---------------------------------------------
def test_weekly_and_monthly_template_variables_match_output_layers():
    contract = read(DATA_CONTRACT)
    errors = variable_errors(read(OUTPUT_FORMATS), contract, dc_rows(contract))
    assert not errors, "\n".join(errors)


def test_allowlists_are_minimal_and_current():
    contract = read(DATA_CONTRACT)
    formats = read(OUTPUT_FORMATS)
    rows = dc_rows(contract)
    fields = dc_fields(rows)
    known = set(fields) | set(dc_template_aliases(rows)) | set(dc_subfield_parents(contract))
    used = {var.removesuffix(SUBMISSION_SUFFIX) for layer in ("週", "月") for var, _ in template_vars(formats, layer)}
    errors = []
    for name, table in (("RENAMED", RENAMED), ("DERIVED", DERIVED), ("KNOWN_GAPS", KNOWN_GAPS)):
        for var in table:
            if var not in used:
                errors.append(f"{name} の {var} はもうテンプレートに無い（許可リストから消す）")
            if var in known:
                errors.append(f"{name} の {var} は DC から解決できる（許可リストは不要）")
    for var, (field, _) in RENAMED.items():
        if field not in fields:
            errors.append(f"RENAMED の {var} の行き先 {field} が DC に無い")
    for (field, layer), _ in LITERAL_EVIDENCE.items():
        if field not in fields or layer not in (parse_layers(fields[field][LAYER_COL]) or ()):
            errors.append(f"LITERAL_EVIDENCE の ({field}, {layer}) が DC の出力する層と合わない")
    assert not errors, "\n".join(errors)


def test_variable_check_catches_a_layer_the_contract_does_not_list():
    """月報だけの #38 principles を「週」と書き換えると、月報の {{principles}} で落ちる。"""
    contract = read(DATA_CONTRACT)
    rows = [dict(r) for r in dc_rows(contract)]
    for r in rows:
        if r[FIELD_COL] == "principles":
            r[LAYER_COL] = "週"
    errors = variable_errors(read(OUTPUT_FORMATS), contract, rows)
    assert any("{{principles}}" in e for e in errors), errors


# --- (c) 期報・1年の「出力しない」 ---------------------------------------------------
def test_monthly_only_headings_are_marked_not_output_in_quarter_and_year():
    contract = read(DATA_CONTRACT)
    checked, errors = not_output_errors(read(OUTPUT_FORMATS), contract, dc_rows(contract))
    assert checked, "期報・1年に出さないフィールドの見出しを1件も拾えていない"
    assert not errors, "\n".join(errors)


def test_not_output_check_catches_an_inherited_heading():
    """#37・#38 の見出しが期報へ漏れた取りこぼしを再現すると落ちる。"""
    contract = read(DATA_CONTRACT)
    formats = read(OUTPUT_FORMATS)
    quarter = {line for line, _ in section_lines(formats, LAYER_SECTIONS["期"])}
    broken = "\n".join(
        line for line in formats.splitlines()
        if not (line in quarter and "【前回のやらないことが守れたか】" in line and NOT_OUTPUT_RX.search(line))
    )
    _, errors = not_output_errors(broken, contract, dc_rows(contract))
    assert any("【前回のやらないことが守れたか】" in e and "期報" in e for e in errors), errors


# --- (d) ターン見出しの実在 ----------------------------------------------------------
def test_question_turns_exist():
    errors = []
    checked = 0
    for row in dc_rows(read(DATA_CONTRACT)):
        refs, mistakes = turn_refs(row[QUESTION_COL])
        errors.extend(f"{row[FIELD_COL]}: {m}" for m in mistakes)
        for kind, where, turn in refs:
            checked += 1
            if not turn_exists(kind, where, turn):
                place = f"prompts/R{where}-*.md" if kind == "R" else f"iqt の「{IQT_FLOWS[where]}」"
                errors.append(f"{row[FIELD_COL]}: {place} にターン{turn} の見出しが無い")
    assert checked, "ターン参照を1件も拾えていない"
    assert not errors, "\n".join(errors)


def test_turn_reference_parser():
    refs, errors = turn_refs("R1 ターン1A／ターン1D-週報（継承）／iqt 週報ターン4.5／月報ターン2")
    assert refs == [("R", "1", "1A"), ("R", "1", "1D-週報"), ("iqt", "週報", "4.5"), ("iqt", "月報", "2")]
    assert not errors
    assert turn_refs("R2 ターン2F-1年初回（1年）")[0] == [("R", "2", "2F-1年初回")]
    assert turn_refs("週報ターン1")[1], "iqt を付けない層のターンは誤り"
    assert turn_refs("ターン1A")[1], "R の無い裸のターンは誤り"
    assert not turn_exists("R", "1", "9Z")


# --- (e) 旧基準の言い換え --------------------------------------------------------------
# 旧基準は「売上の代わりに接点・人数を追う」と読める書き方。固定文字列ではなく類型で拾う。
OLD_CRITERION_PATTERNS = {
    "「追う」を否定して対比する（例: 売上を追うのではなく）": re.compile(r"追う」?\s*の?\s*(?:で|では)なく"),
    "接点を増やすことを目標に置く（例: 接点を増やす・接点が8件増えたか）": re.compile(r"接点.{0,8}増"),
    "追う対象を人数・回数・接点に置く（例: 追うのは人数）": re.compile(r"追う(?:の|もの)は\s*(?:接点|人数|回数|件数)"),
}
# 走査から外すもの（理由つき）。`>` で始まる行は外さない。R1〜R5 とターンテンプレートの発話本文
# （ユーザーにそのまま話す文）が `>` で書かれており、旧基準が最も残りやすい場所だから。
# 北原さんの原文は knowledge/ に置き、他の文書では「売上目標は追わない」のように類型に当たらない形で引く。
SCAN_EXCLUDED_DIRS = {
    PLUGIN_ROOT / "knowledge": "北原さんの原典と知識DB。原文をそのまま保持する",
    PLUGIN_ROOT / "tests": "検査自身と fixture",
}
SCAN_EXCLUDED_NAMES = {
    "CHANGELOG.md": "変更履歴。改めた旧基準を説明として書く",
    "version-history.md": "凍結した版履歴",
}


def scanned_documents() -> list[Path]:
    return [
        p for p in sorted(PLUGIN_ROOT.rglob("*.md"))
        if p.name not in SCAN_EXCLUDED_NAMES and not any(d in p.parents for d in SCAN_EXCLUDED_DIRS)
    ]


def old_criterion_hits(text: str) -> list[str]:
    hits = []
    for lineno, line in enumerate(text.splitlines(), start=1):
        for kind, rx in OLD_CRITERION_PATTERNS.items():
            if m := rx.search(line):
                hits.append(f"{lineno}: [{kind}] {line[max(0, m.start() - 20):m.end() + 20]}")
    return hits


def test_no_old_criterion_paraphrase():
    documents = scanned_documents()
    assert documents
    found = [f"{p.relative_to(PLUGIN_ROOT)}:{hit}" for p in documents for hit in old_criterion_hits(read(p))]
    assert not found, "旧基準の言い換えが残っている（共通部品G の当てはめに直す）:\n" + "\n".join(found)


def test_old_criterion_patterns_catch_paraphrases_but_not_the_principle():
    for old in ("売上を「追う」ではなく、関係を育てる", "売上を追うのではなく接点を見る",
                "新しい接点が8件以上増えたか", "接点を増やす", "追うのは人数です",
                "> 売上を追うのではなく、まず1人に価値を（発話テンプレート）"):
        assert old_criterion_hits(old), f"旧基準を拾えていない: {old}"
    for current in ("北原さん:「売上目標は追わない。人との関係を育むことが一番大事」",
                    "> 北原さん:「売上目標は追わない」",
                    "根本で追うのはこの売上です",
                    "追うのは月間売上で、継続コンサル人数はその売上を生む手段です",
                    "接点の段は不足の点検に使い、全段・固定件数を出力しない"):
        assert not old_criterion_hits(current), f"正しい書き方を誤って拾った: {current}"
