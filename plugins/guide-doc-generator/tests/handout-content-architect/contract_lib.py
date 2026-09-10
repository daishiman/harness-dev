"""handout-content-architect (C05) の agent 定義 Markdown の宣言的契約チェッカ。

sub-agent component は実行そのものを機械検査できないため、検査対象は
`plugins/guide-doc-generator/agents/handout-content-architect.md` の宣言
(frontmatter / 必須セクション / 責務境界の明記 / 入出力スキーマの宣言 /
親会話の前提を持ち込まない旨の禁止宣言) である。

契約の出典:
  - plugin-plans/guide-doc-generator/briefs/agent-brief-C05.json (正本)
  - plugin-plans/guide-doc-generator/component-inventory.json #C05
  - plugin-plans/guide-doc-generator/briefs/RESOLUTION-P03.md (Y-05 / Y-06 / Y-09)
  - plugin-plans/guide-doc-generator/briefs/RESOLUTION-R21.md (C46-C59)

標準ライブラリのみを使う (PyYAML は使わない)。agent の frontmatter は
フラットなスカラーのみなので、その部分集合だけを解釈する簡易パーサで読む。
"""

from __future__ import annotations

import re
from collections import namedtuple
from pathlib import Path

Violation = namedtuple("Violation", ["contract_id", "message"])


# --------------------------------------------------------------------------
# 契約の定数 (すべて brief / inventory / RESOLUTION 由来)
# --------------------------------------------------------------------------

AGENT_NAME = "handout-content-architect"
BUILD_TARGET = "plugins/guide-doc-generator/agents/handout-content-architect.md"

# agent-brief-C05.json frontmatter_fields.fields
REQUIRED_FRONTMATTER_KEYS = (
    "name",
    "description",
    "kind",
    "version",
    "owner",
    "tools",
    "isolation",
    "model",
    "owner_skill",
    "prompt_ref",
    "prompt_layer",
    "since",
    "last-audited",
)

# agent-brief-C05.json acceptance_checks AC1 / inventory #C05.tools
REQUIRED_TOOLS = {"Read", "Write"}
FORBIDDEN_TOOLS = {"Bash", "Edit", "Task", "WebFetch", "WebSearch", "MultiEdit"}

# description の正本。brief と inventory で文言が 1 箇所ずれている (README gap G1)
# ため、どちらか一方に一致すれば受け入れる。
CANONICAL_DESCRIPTIONS = (
    "ヒアリング結果から資料の構成データ (セクション構成・部品選択・lead-line・"
    "判断軸・用語言い換え宣言・日付) を独立 context で設計したいときに使う",
    "ヒアリング結果から資料の構成データ (セクション構成・部品選択・lead-line・"
    "判断軸・用語言い換え宣言・日付・R21 の型フィールド) を独立 context で"
    "設計したいときに使う",
)

# agent-brief-C05.json body_sections
REQUIRED_SECTIONS = (
    "# handout-content-architect",
    "## Purpose",
    "## Inputs",
    "## Outputs",
    "## Goal-Seeking Execution",
    "## Constraints",
    "## Prompt Templates",
    "## Self-Evaluation",
)

# lint-agent-prompt-section.py の ANCHOR_RE / DIMENSIONS / AUTO_AGENT_MARKER
ANCHOR_RE = re.compile(r"<!--\s*responsibility:\s*(R[0-9]+)\s*-->")
AUTO_AGENT_MARKER = "(対話なし: 自動実行 agent)"
SELF_EVAL_DIMENSIONS = ("完全性", "一貫性", "深度", "検証可能性", "簡潔性")

# agent-brief-C05.json prompt_ref と open_questions[0] (R1- へ揃える案が残る)
PROMPT_REF_BASENAMES = ("R2a-design-config.md", "R1-design-config.md")

# agent-brief-C05.json input_contract.receives の hearing_result 13 項目
# (duration_or_volume は所要時間の撤去で消えた。時間・分量の宣言は資料の
#  記述から外し、分量は detail_level / evidence_depth が担う)
HEARING_FIELDS = (
    "reader",
    "prior_knowledge_level",
    "usage_scene",
    "essential_problem",
    "background",
    "overall_goal",
    "section_outline",
    "focus_theme",
    "target_tasks",
    "attainment_level",
    "must_remember",
    "no_need_to_remember",
    "presentation_order",
)

# agent-brief-C05.json output_contract.returns のキー
RETURN_KEYS = (
    "status",
    "config_path",
    "purpose",
    "section_summary",
    "glossary_terms",
    "date_supplied",
    "materials_used",
    "materials_unused",
    "decision_log",
    "open_questions",
    "blocked_reason",
)

# P03 Y-05: 部品 id 語彙の正本はデータファイル 1 点で、散文へ列挙しない
PARTS_CATALOG_PATH = "config/handout-parts.json"
PART_ID_RE = re.compile(r"\bB(?:0[1-9]|1[0-7])\b")
PART_ID_LINE_MAX = 2

# R21 C46 の閾値正本 (script/散文ではなくデータファイル側)
SECTIONS_CONFIG_PATH = "config/handout-sections.json"

# 生成物が HTML/CSS/SVG へ踏み込んでいないことの機械検査 (boundary)
FORBIDDEN_MARKUP = (
    "<div",
    "<span",
    "<section",
    "<svg",
    "<path",
    "viewBox",
    "class=",
    "style=",
    "localStorage",
    "--hb-",
)

# 親会話の前提 (参照 HTML / 開発計画) の持ち込み痕跡
LEAK_TOKENS = (
    "Claude に触って慣れる日",
    "reference-guide-stripped.html",
    "reference-guide-v2.html",
    "plugin-plans/",
    "task-graph",
    "component-inventory",
    "analysis/guide-doc-generator",
)
NEGATION_WORDS = (
    "持ち込まない",
    "参照しない",
    "読まない",
    "流用しない",
    "使わない",
    "書き写さない",
    "禁止",
    "してはならない",
    "書かない",
    "出さない",
)

# 絵文字の粗い検出 (C10 / C16 CR-EMOJI の正本判定ではない。README 参照)
EMOJI_RE = re.compile(r"[\U0001F000-\U0001FAFF\U0000FE0F]")


# --------------------------------------------------------------------------
# frontmatter (フラットな YAML 部分集合) パーサ
# --------------------------------------------------------------------------


def _scalar(raw: str):
    text = raw.strip()
    if len(text) >= 2 and text[0] == text[-1] and text[0] in "\"'":
        return text[1:-1]
    if text in ("true", "True"):
        return True
    if text in ("false", "False"):
        return False
    return text


def split_frontmatter(text: str):
    """(frontmatter_dict, body_text) を返す。frontmatter が無ければ (None, text)。"""
    lines = text.split("\n")
    if not lines or lines[0].strip() != "---":
        return None, text
    for i in range(1, len(lines)):
        if lines[i].strip() == "---":
            fm = {}
            for raw in lines[1:i]:
                if not raw.strip() or raw.lstrip().startswith("#"):
                    continue
                if ":" not in raw:
                    continue
                key, _, rest = raw.partition(":")
                fm[key.strip()] = _scalar(rest)
            return fm, "\n".join(lines[i + 1:])
    return None, text


def section_text(body: str, heading: str):
    """指定見出しから次の同レベル以上の見出しまでの本文を返す。無ければ None。"""
    level = heading.split(" ")[0]
    lines = body.splitlines()
    start = None
    for i, line in enumerate(lines):
        if line.strip() == heading:
            start = i + 1
            break
    if start is None:
        return None
    out = []
    for line in lines[start:]:
        stripped = line.strip()
        if stripped.startswith("#") and stripped != heading:
            hashes = len(stripped) - len(stripped.lstrip("#"))
            if hashes <= len(level):
                break
        out.append(line)
    return "\n".join(out)


# --------------------------------------------------------------------------
# 検査本体
# --------------------------------------------------------------------------


def _tools(fm) -> set:
    raw = fm.get("tools")
    if not isinstance(raw, str):
        return set()
    return {t.strip() for t in raw.strip().strip("[]").split(",") if t.strip()}


def _requires(v, contract_id, body, pattern, message):
    """body が pattern に一致しなければ違反を積む。"""
    if not re.search(pattern, body):
        v.append(Violation(contract_id, message))


def check_agent(agent_md) -> list:
    """agent 定義 Markdown を検査し Violation の一覧を返す。空リストなら受入。"""
    agent_md = Path(agent_md)
    v = []

    # AC-C05-1: build_target のファイルが実在する
    if not agent_md.is_file():
        v.append(Violation("AC-C05-1", f"agent 定義が存在しない: {agent_md}"))
        return v

    text = agent_md.read_text(encoding="utf-8")
    fm, body = split_frontmatter(text)
    if fm is None:
        v.append(Violation("AC-C05-2", "YAML frontmatter が無い"))
        return v

    # --- AC-C05-2: frontmatter identity (AC1) --------------------------
    for key in REQUIRED_FRONTMATTER_KEYS:
        if key not in fm or fm.get(key) in (None, ""):
            v.append(Violation("AC-C05-2", f"frontmatter に {key} が無い (または空)"))
    identity = {
        "name": AGENT_NAME,
        "kind": "agent",
        "isolation": "fork",
        "owner_skill": "run-handout-build",
        "prompt_layer": "7layer",
    }
    for key, want in identity.items():
        if key in fm and fm.get(key) != want:
            v.append(Violation(
                "AC-C05-2",
                f"frontmatter {key} は {want!r} でなければならない (実際: {fm.get(key)!r})",
            ))

    # --- AC-C05-3: tools は Read / Write ちょうど (AC1 / inventory) -----
    tools = _tools(fm)
    if tools != REQUIRED_TOOLS:
        v.append(Violation(
            "AC-C05-3",
            f"tools は {sorted(REQUIRED_TOOLS)} ちょうどでなければならない (実際: {sorted(tools)})",
        ))
    for bad in sorted(tools & FORBIDDEN_TOOLS):
        v.append(Violation(
            "AC-C05-3",
            f"tools に {bad} を持ってはならない (自分の出力を自分で検証する構図を作らない)",
        ))

    # --- AC-C05-4: description (AC1) -----------------------------------
    desc = str(fm.get("description") or "").strip()
    if not desc:
        v.append(Violation("AC-C05-4", "description が空"))
    else:
        norm = re.sub(r"\s+", "", desc).rstrip("。")
        if norm not in {re.sub(r"\s+", "", d).rstrip("。") for d in CANONICAL_DESCRIPTIONS}:
            v.append(Violation(
                "AC-C05-4",
                "description が brief / inventory の正本文言と一致しない (実際: " + desc + ")",
            ))
        if not norm.endswith("したいときに使う"):
            v.append(Violation("AC-C05-4", "description が「〜したいときに使う」形で終わっていない"))

    # --- AC-C05-5: prompt_ref が責務 prompt を指す (AC1) ---------------
    prompt_ref = str(fm.get("prompt_ref") or "")
    if not prompt_ref:
        v.append(Violation("AC-C05-5", "prompt_ref が無い"))
    else:
        if "prompts/" not in prompt_ref:
            v.append(Violation("AC-C05-5", f"prompt_ref が prompts/ 配下を指していない: {prompt_ref}"))
        if Path(prompt_ref).name not in PROMPT_REF_BASENAMES:
            v.append(Violation(
                "AC-C05-5",
                f"prompt_ref の basename は {list(PROMPT_REF_BASENAMES)} のいずれか (実際: {Path(prompt_ref).name})",
            ))

    # --- AC-C05-6: 必須セクションと責務アンカー (body_sections) --------
    body_lines = body.splitlines()
    for heading in REQUIRED_SECTIONS:
        if not any(line.strip() == heading for line in body_lines):
            v.append(Violation("AC-C05-6", f"必須セクション {heading!r} が無い"))
    if not ANCHOR_RE.search(body):
        v.append(Violation(
            "AC-C05-6",
            "lint-agent-prompt-section.py の ANCHOR_RE (<!-- responsibility: R<数字> -->) に"
            "一致する責務アンカーが無い",
        ))

    # --- AC-C05-7: lint-agent-prompt-section 互換 (AC2) ----------------
    prompt_section = section_text(body, "## Prompt Templates")
    if prompt_section is None:
        v.append(Violation("AC-C05-7", "## Prompt Templates 節が無い"))
    elif AUTO_AGENT_MARKER not in prompt_section and not any(
        line.startswith("> ") for line in prompt_section.splitlines()
    ):
        v.append(Violation(
            "AC-C05-7",
            f"## Prompt Templates 節は {AUTO_AGENT_MARKER!r} マーカーか '> ' 引用行を持たなければならない",
        ))
    self_eval = section_text(body, "## Self-Evaluation")
    if self_eval is None:
        v.append(Violation("AC-C05-7", "## Self-Evaluation 節が無い"))
    elif not any(d in self_eval for d in SELF_EVAL_DIMENSIONS):
        v.append(Violation(
            "AC-C05-7",
            f"## Self-Evaluation 節が {list(SELF_EVAL_DIMENSIONS)} のいずれにも言及していない",
        ))

    # --- AC-C05-8: 決定論分界線 — HTML/CSS/SVG を書かない (AC3) --------
    for token in FORBIDDEN_MARKUP:
        for line in body_lines:
            if token in line and not ANCHOR_RE.search(line):
                v.append(Violation(
                    "AC-C05-8",
                    f"HTML/CSS/SVG マークアップの断片 {token!r} を本文へ持ってはならない: {line.strip()[:70]!r}",
                ))
                break
    _requires(v, "AC-C05-8", body, r"HTML[^\n]*(1 行も書かない|書かない|生成しない|出力しない)",
              "HTML を書かない旨の明記が無い")
    _requires(v, "AC-C05-8", body,
              r"(構成データ JSON|config JSON)[^\n]*(1 (個|点|ファイル)|1個)|1 (個|点|ファイル)[^\n]*構成データ JSON",
              "出力が構成データ JSON 1 個に限定される旨の明記が無い")
    _requires(v, "AC-C05-8", body, r"C11", "決定論レンダラ C11 への写像の委譲が明記されていない")

    # --- AC-C05-9: must_not_assume 5 項目の禁止宣言 (AC4) --------------
    must_not_assume = (
        ("参照 HTML の文面",
         r"参照\s*HTML[^\n]*(持ち込まない|流用しない|使わない|書き写さない|禁止)"),
        ("開発計画の文脈",
         r"(plugin-plans|開発計画|task-graph)[^\n]*(持ち込まない|参照しない|読まない|禁止)"),
        ("ヒアリング前の仮説",
         r"(仮説|言い換え)[^\n]*(持ち込まない|補わない|採らない|残さない|禁止)"),
        ("語彙とプリセットの記憶復元",
         r"記憶[^\n]*(復元しない|書かない|頼らない|依存しない|再現しない)"),
        ("現在日の自己取得",
         r"(現在日|実行日|今日の日付)[^\n]*(取得しない|埋めない|補わない|書かない)"),
    )
    for label, pattern in must_not_assume:
        _requires(v, "AC-C05-9", body, pattern,
                  f"must_not_assume の禁止宣言が無い: {label}")

    # --- AC-C05-10: 親会話の前提の持ち込み検出 (task-spec 受入条件) ----
    for line in body_lines:
        stripped = line.strip()
        if any(word in stripped for word in NEGATION_WORDS):
            continue
        for token in LEAK_TOKENS:
            if token in stripped:
                v.append(Violation(
                    "AC-C05-10",
                    f"親会話の前提 {token!r} が禁止文脈以外で本文に混入している: {stripped[:70]!r}",
                ))

    # --- AC-C05-11: lead_line と goal は別フィールドで両方必須 (C40) ---
    _requires(v, "AC-C05-11", body, r"lead_line", "lead_line への言及が無い")
    _requires(v, "AC-C05-11", body, r"decision_line", "decision_line (判断軸) への言及が無い")
    _requires(v, "AC-C05-11", body,
              r"(lead_line[^\n]*goal|goal[^\n]*lead_line)[^\n]*(別|代替|兼ね)|"
              r"(別のフィールド|別フィールド)[^\n]*(lead_line|goal)",
              "lead_line と section goal が別フィールドである旨の明記が無い")
    _requires(v, "AC-C05-11", body, r"(代替しない|代替させない|兼ねない|置き換えない)",
              "一方が他方を代替しない旨の明記が無い (C40)")
    _requires(v, "AC-C05-11", body, r"C40", "C40 への参照が無い")

    # --- AC-C05-12: 日付の単一 writer (AC7 / C33-C35) ------------------
    _requires(v, "AC-C05-12", body,
              r"(date|日付)[^\n]*(フィールドを出さない|フィールドを出力しない|出力しない|書かない)",
              "date が入力に無いとき日付フィールドを出力しない旨の明記が無い")
    _requires(v, "AC-C05-12", body, r"--normalize",
              "既定充填を C12 --normalize に委ねる旨の明記が無い (日付の単一 writer 規約)")

    # --- AC-C05-13: presentation_order を導出しない (R21 C49) ----------
    _requires(v, "AC-C05-13", body, r"presentation_order", "presentation_order への言及が無い")
    _requires(v, "AC-C05-13", body,
              r"(presentation_order|提示順)[^\n]*(導出しない|自分で決めない|決めない|書かない)",
              "presentation_order を自分で導出しない旨の明記が無い")
    _requires(v, "AC-C05-13", body, r"CR-PRESENTATION-ORDER",
              "導出規則の正本 CR-PRESENTATION-ORDER への参照が無い")
    for line in body_lines:
        if re.search(r"(none|basic|intermediate)", line) and re.search(
            r"(demo_first|explain_first)", line
        ):
            v.append(Violation(
                "AC-C05-13",
                "prior_knowledge から提示順への導出表を複製してはならない "
                f"(正本は C12 の CR-PRESENTATION-ORDER 1 箇所): {line.strip()[:70]!r}",
            ))

    # --- AC-C05-14: focus_theme / ties_to / logistics (R21 C47/C48) ----
    _requires(v, "AC-C05-14", body, r"focus_theme[^\n]*(1\s*[-–〜~]\s*2|1〜2|1-2|2 件)",
              "focus_theme を 1-2 件に保つ旨の明記が無い (C47)")
    _requires(v, "AC-C05-14", body, r"ties_to", "section.ties_to への言及が無い (C48)")
    _requires(v, "AC-C05-14", body, r"ties_to[^\n]*(goal|focus_theme|target_task)|"
                                    r"(goal|focus_theme|target_task)[^\n]*ties_to",
              "ties_to が goal / focus_theme / target_task のいずれかを指す旨の明記が無い")
    _requires(v, "AC-C05-14", body, r"logistics[^\n]*appendix|appendix[^\n]*logistics",
              "目的に直結しない伝達事項を appendix の logistics へ隔離する旨の明記が無い (C48)")

    # --- AC-C05-15: flow-overview (R21 C46) ----------------------------
    _requires(v, "AC-C05-15", body, r"flow-overview", "flow-overview セクションへの言及が無い")
    _requires(v, "AC-C05-15", body,
              r"(手順[^\n]*詳細|詳細な手順|個々の手順)[^\n]*(書かない|載せない|入れない)",
              "冒頭の流れに手順の詳細を書かない旨の明記が無い (C46)")
    _requires(v, "AC-C05-15", body, re.escape(SECTIONS_CONFIG_PATH),
              f"section_kind 属性の正本 {SECTIONS_CONFIG_PATH} への参照が無い (件数上限を散文へ焼かない)")

    # --- AC-C05-16: capability-explainer の slot 順 (R21 C51) ----------
    _requires(v, "AC-C05-16", body, r"capability-explainer",
              "capability-explainer セクションへの言及が無い")
    _requires(v, "AC-C05-16", body, r"outcome[^\n]*breakdown[^\n]*feature",
              "parts[].slot を outcome → breakdown → feature の順に与える旨の明記が無い (C51)")
    _requires(v, "AC-C05-16", body, r"機能名[^\n]*(始めない|書き始めない)",
              "lead_line を機能名から始めない旨の明記が無い (C51)")

    # --- AC-C05-17: 到達レベル / 対話枠 / ハンズオン / 所要時間 --------
    _requires(v, "AC-C05-17", body, r"attainment_level[^\n]*(超え|範囲)",
              "attainment_level を超える内容のセクションを作らない旨の明記が無い (C54)")
    for token, label in (("dialogue", "対話枠 (C59)"), ("handson", "ハンズオン (C53)"),
                         ("anticipated-qa", "先回り Q&A (C53)")):
        _requires(v, "AC-C05-17", body, re.escape(token), f"{label} への言及が無い")
    # ハンズオン部品の指し方は P05-x-07 の裁定で「id の literal」から
    # 「カタログ述語 (data_block_type=handson)」へ移った。id を直書きすると
    # config/handout-parts.json 以外に部品 id の名簿が生えるため、ここでも
    # literal を要求しない (要求すると 2 つの契約が同時に満たせなくなる)。
    _requires(v, "AC-C05-17", body, r"data_block_type\s*=\s*handson",
              "ハンズオン部品をカタログ述語 (data_block_type=handson) で指す記述が無い")

    # --- AC-C05-18: must_remember と no_need_to_remember の対 (C57) ----
    _requires(v, "AC-C05-18", body, r"must_remember", "must_remember への言及が無い")
    _requires(v, "AC-C05-18", body, r"no_need_to_remember", "no_need_to_remember への言及が無い")
    _requires(v, "AC-C05-18", body, r"(対で|片方だけ|両方)",
              "must_remember と no_need_to_remember が対である旨の明記が無い (C57)")
    _requires(v, "AC-C05-18", body, r"(片方だけ|一方だけ)[^\n]*blocked|blocked[^\n]*(片方だけ|一方だけ)",
              "片方だけ埋まっている入力を blocked とする旨の明記が無い (C57)")

    # --- AC-C05-19: 入力 14 項目と blocked 差し戻し --------------------
    inputs = section_text(body, "## Inputs")
    if inputs is None:
        v.append(Violation("AC-C05-19", "## Inputs 節が無い"))
    else:
        for field in HEARING_FIELDS:
            if not re.search(r"\b" + re.escape(field) + r"\b", inputs):
                v.append(Violation("AC-C05-19", f"hearing_result の必須項目 {field} が ## Inputs 節に無い"))
    _requires(v, "AC-C05-19", body, r"blocked_reason", "blocked_reason への言及が無い")
    _requires(v, "AC-C05-19", body,
              r"(質問を投げ返さない|ユーザーへ質問しない|質問しない|問い返さない)",
              "ユーザーへ質問を投げ返さず親へ差し戻す旨の明記が無い")

    # --- AC-C05-20: 出力契約 (returns のキーと writes_files) -----------
    outputs = section_text(body, "## Outputs")
    if outputs is None:
        v.append(Violation("AC-C05-20", "## Outputs 節が無い"))
    else:
        for key in RETURN_KEYS:
            if not re.search(r"\b" + re.escape(key) + r"\b", outputs):
                v.append(Violation("AC-C05-20", f"## Outputs に戻り値キー {key} の宣言が無い"))
        if "out_config_path" not in outputs:
            v.append(Violation("AC-C05-20", "## Outputs に書き出し先 out_config_path の宣言が無い"))
        if not re.search(r"1 (ファイル|個|点)", outputs):
            v.append(Violation("AC-C05-20", "書き出すファイルが 1 個だけである旨の明記が無い"))

    # --- AC-C05-21: proposer != approver (自分で合否判定しない) --------
    _requires(v, "AC-C05-21", body,
              r"validate-handout-config\.py[^\n]*(実行しない|起動しない|委ねる|親)",
              "validate-handout-config.py を自分で実行しない旨の明記が無い")
    _requires(v, "AC-C05-21", body, r"Bash[^\n]*(持たない|使わない|無い)",
              "Bash を持たない (script を起動しない) 旨の明記が無い")
    for line in body_lines:
        if re.search(r"(python3?\s+\S*(validate-handout-config|route-handout-output|resolve-handout-preset))",
                     line) and not any(w in line for w in NEGATION_WORDS + ("委ねる", "親",)):
            v.append(Violation(
                "AC-C05-21",
                f"script の実行を指示してはならない: {line.strip()[:70]!r}",
            ))

    # --- AC-C05-22: 語彙 SSOT (P03 Y-05 / Y-06) ------------------------
    _requires(v, "AC-C05-22", body, re.escape(PARTS_CATALOG_PATH),
              f"部品 id 語彙の正本 {PARTS_CATALOG_PATH} への参照が無い")
    for line in body_lines:
        ids = set(PART_ID_RE.findall(line))
        if len(ids) > PART_ID_LINE_MAX:
            v.append(Violation(
                "AC-C05-22",
                f"部品 id をカタログ外へ列挙してはならない ({len(ids)} 件): {line.strip()[:70]!r}",
            ))
    _requires(v, "AC-C05-22", body,
              r"(用途種別|用途語彙|用途の語彙)[^\n]*(列挙しない|復元しない|preset|正本)",
              "用途種別の語彙を自分で列挙せず preset / config 正本に従う旨の明記が無い (Y-06)")
    _requires(v, "AC-C05-22", body, r"handout-config\.schema\.json",
              "スキーマ正本 handout-config.schema.json を読む旨の明記が無い")

    # --- AC-C05-23: 下流責務の境界 (C14 / C15 / C13) -------------------
    _requires(v, "AC-C05-23", body, r"C14[^\n]*座標|座標[^\n]*C14",
              "SVG 座標計算が C14 の責務である旨の明記が無い")
    _requires(v, "AC-C05-23", body, r"C15[^\n]*(symbol|アイコン)|(symbol|アイコン)[^\n]*C15",
              "アイコンの symbol 抽出が C15 の責務である旨の明記が無い")
    _requires(v, "AC-C05-23", body, r"C13[^\n]*(data URI|データ URI)|(data URI|データ URI)[^\n]*C13",
              "素材の data URI 化が C13 の責務である旨の明記が無い")

    # --- AC-C05-24: 絵文字 0 件 (C10 / C16) ----------------------------
    for line in body_lines:
        hits = EMOJI_RE.findall(line)
        if hits:
            v.append(Violation(
                "AC-C05-24",
                f"本文に絵文字を含んではならない ({hits!r}): {line.strip()[:50]!r}",
            ))
    _requires(v, "AC-C05-24", body, r"絵文字[^\n]*(書かない|使わない|出さない|0 件|禁止)",
              "構成データへ絵文字を書かない旨の明記が無い (C10)")

    # --- AC-C05-25: glossary の宣言と本文併記 (C16) --------------------
    _requires(v, "AC-C05-25", body, r"glossary", "glossary への言及が無い")
    _requires(v, "AC-C05-25", body, r"term[^\n]*plain|plain[^\n]*term",
              "glossary[] が {term, plain} の対である旨の明記が無い")
    _requires(v, "AC-C05-25", body, r"初出[^\n]*(括弧|併記)",
              "宣言した用語を本文フィールドの初出で括弧書き併記する旨の明記が無い")
    _requires(v, "AC-C05-25", body, r"(別の)?専門用語で言い換えない|専門用語[^\n]*言い換えない",
              "別の専門用語で言い換えない旨の明記が無い")

    # --- AC-C05-26: プリセットの合成禁止 -------------------------------
    _requires(v, "AC-C05-26", body,
              r"(プリセット|preset)[^\n]*(合成しない|混ぜない|足し合わせない|混成用途は不可)",
              "プリセットを合成しない旨の明記が無い")
    _requires(v, "AC-C05-26", body, r"decision_log",
              "セクション追加で吸収した判断を decision_log へ残す旨の明記が無い")

    return v


def violation_ids(violations):
    return [x.contract_id for x in violations]


def repo_root() -> Path:
    return Path(__file__).resolve().parents[4]


def build_target() -> Path:
    return repo_root() / BUILD_TARGET
