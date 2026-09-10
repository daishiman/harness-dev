"""run-handout-extract (C02) の SKILL.md 宣言的契約チェッカ。

skill component は実行そのものを機械検査できないため、検査対象は SKILL.md の
宣言 (frontmatter / 必須セクション / 参照スクリプトの実在 / 逆抽出の入出力契約 /
呼び出す component の宣言) である。

契約の出典 (すべてブリーフ由来。推測で発明しない):
  - plugin-plans/guide-doc-generator/briefs/skill-brief-C02.json (正本)
  - plugin-plans/guide-doc-generator/component-inventory.json #C02
  - plugin-plans/guide-doc-generator/briefs/script-brief-C20.json
    (single_writer / roundtrip_granularity / heuristic_fallback.never_guessed /
     fail_semantics / report_shape — 逆抽出の入出力契約の実質的な正本)
  - plugin-plans/guide-doc-generator/briefs/command-brief-C08.json
    (behavior 3-8 / boundary の「skill へ渡す責務」— C02 への委譲契約)

標準ライブラリのみを使う (PyYAML は使わない)。frontmatter は本 plugin の
SKILL.md が使う YAML 部分集合だけを解釈する簡易パーサで読む。
"""

from __future__ import annotations

import re
from collections import namedtuple
from pathlib import Path

Violation = namedtuple("Violation", ["contract_id", "message"])


# --------------------------------------------------------------------------
# 契約の定数 (すべてブリーフ / inventory / 委譲元 command 由来)
# --------------------------------------------------------------------------

SKILL_NAME = "run-handout-extract"
BUILD_TARGET = "plugins/guide-doc-generator/skills/run-handout-extract/"

# skill-brief-C02.json responsibilities[].id
REQUIRED_RESPONSIBILITIES = ("R1-scan", "R2-complete", "R3-roundtrip")

# skill-brief-C02.json deterministic_checks
REQUIRED_SCRIPTS = (
    "extract-handout-config.py",
    "validate-handout-config.py",
    "render-handout.py",
    "verify-handout-selfcontained.py",
)

# component-inventory.json #C02 feedback_contract.criteria
REQUIRED_CRITERIA = {
    "IN1": ("inner", "script"),
    "OUT1": ("outer", "test"),
    "OUT2": ("outer", "live-trial"),
}

# component-inventory.json #C02 goal_seek
REQUIRED_GOAL_SEEK = {"engine": "inline", "fork": "subagent", "max_loops": 5}

# component-inventory.json #C02 combinators
REQUIRED_COMBINATORS = ("with-goal-seek", "with-feedback-contract")

# component-inventory.json #C02 depends_on
REQUIRED_DEPENDS_ON = ("C11", "C12", "C16", "C20")

# 本 repo の run 系 skill が共有する本文骨格 (C01 のテストと同一)
REQUIRED_SECTIONS = (
    "## Purpose & Output Contract",
    "## ゴールシーク実行",
    "## Criteria acceptance",
    "## Gotchas",
)

REQUIRED_SUBSECTIONS = (
    "### ゴール (Goal)",
    "### 目的・背景 (Why)",
    "### 完了チェックリスト",
    "### ゴールシークループ",
    "### ゴールシーク配線",
    "### ゴールシーク検証",
)

# skill-brief-C02.json output_contract の逆抽出レポート 3 要素
REPORT_ELEMENTS = ("復元した部品一覧", "復元不能箇所と採った補完", "round-trip 差分")

# script-brief-C20.json heuristic_fallback.never_guessed
# (マーカーが無い限り推測してはならない意味情報)
NEVER_GUESSED = (
    "lead_line",
    "judgment_axis",
    "section goal",
    "reader",
    "prior_knowledge_level",
    "essential_problem",
    "doc_type",
)

# command-brief-C08.json behavior 5 — 補完方針は 3 択のいずれかを明示する
COMPLETION_POLICIES = ("推測値の充填", "空のまま残置", "利用者への確認")

# skill-brief-C02.json checklist
REQUIRED_CHECKLIST = (
    "既存 HTML の走査",
    "構成データの復元",
    "復元不能箇所の補完判断",
    "round-trip 等価の確認",
)

# 自前 HTML parse の痕跡 (C20 single_writer 違反)
SELF_PARSE_PATTERNS = (
    r"html\.parser",
    r"HTMLParser",
    r"BeautifulSoup",
    r"lxml",
    r"正規表現で\s*HTML",
    r"本 skill が\s*HTML を(直接)?(parse|解析)",
)


# --------------------------------------------------------------------------
# 最小 YAML 部分集合パーサ
# --------------------------------------------------------------------------

_MAPPING_LINE = re.compile(r"^[A-Za-z_][A-Za-z0-9_\-]*\s*:(\s|$)")


def _scalar(raw: str):
    text = raw.strip()
    if len(text) >= 2 and text[0] == text[-1] and text[0] in "\"'":
        return text[1:-1]
    if text.startswith("[") and text.endswith("]"):
        inner = text[1:-1].strip()
        if not inner:
            return []
        return [_scalar(part) for part in inner.split(",")]
    if text in ("true", "True"):
        return True
    if text in ("false", "False"):
        return False
    if re.fullmatch(r"-?\d+", text):
        return int(text)
    return text


def _lines(text: str):
    out = []
    for raw in text.splitlines():
        if not raw.strip() or raw.lstrip().startswith("#"):
            continue
        out.append((len(raw) - len(raw.lstrip(" ")), raw.strip()))
    return out


def _parse(lines, idx, indent):
    if idx < len(lines) and lines[idx][0] == indent and lines[idx][1].startswith("- "):
        seq = []
        while idx < len(lines) and lines[idx][0] == indent and lines[idx][1].startswith("- "):
            content = lines[idx][1][2:].strip()
            sub = [(indent + 2, content)] if content else []
            idx += 1
            while idx < len(lines) and lines[idx][0] > indent:
                sub.append(lines[idx])
                idx += 1
            if not sub:
                seq.append(None)
                continue
            if len(sub) == 1 and not _MAPPING_LINE.match(sub[0][1]):
                seq.append(_scalar(sub[0][1]))
                continue
            base = min(item[0] for item in sub)
            value, _ = _parse([(i - base, c) for i, c in sub], 0, 0)
            seq.append(value)
        return seq, idx

    mapping = {}
    while idx < len(lines) and lines[idx][0] == indent:
        line = lines[idx][1]
        if ":" not in line:
            break
        key, _, rest = line.partition(":")
        key = key.strip()
        rest = rest.strip()
        idx += 1
        if rest:
            mapping[key] = _scalar(rest)
            continue
        if idx < len(lines) and lines[idx][0] > indent:
            value, idx = _parse(lines, idx, lines[idx][0])
            mapping[key] = value
        elif idx < len(lines) and lines[idx][0] == indent and lines[idx][1].startswith("- "):
            value, idx = _parse(lines, idx, indent)
            mapping[key] = value
        else:
            mapping[key] = None
    return mapping, idx


def parse_yaml_subset(text: str):
    lines = _lines(text)
    if not lines:
        return {}
    value, _ = _parse(lines, 0, lines[0][0])
    return value


def split_frontmatter(text: str):
    """(frontmatter_dict, body_text) を返す。frontmatter が無ければ (None, text)。"""
    if not text.startswith("---"):
        return None, text
    parts = text.split("\n")
    if parts[0].strip() != "---":
        return None, text
    for i in range(1, len(parts)):
        if parts[i].strip() == "---":
            fm = "\n".join(parts[1:i])
            body = "\n".join(parts[i + 1:])
            parsed = parse_yaml_subset(fm)
            return (parsed if isinstance(parsed, dict) else {}), body
    return None, text


# --------------------------------------------------------------------------
# 補助
# --------------------------------------------------------------------------


def _as_list(value):
    if value is None:
        return []
    if isinstance(value, list):
        return value
    return [value]


def _section_text(body_lines, heading):
    """指定見出しから次の同レベル見出しまでの本文を返す。無ければ None。"""
    level = heading.split(" ")[0]
    start = None
    for i, line in enumerate(body_lines):
        if line.strip() == heading:
            start = i + 1
            break
    if start is None:
        return None
    out = []
    for line in body_lines[start:]:
        if line.startswith(level + " ") and line.strip() != heading:
            break
        out.append(line)
    return "\n".join(out)


# --------------------------------------------------------------------------
# 検査本体
# --------------------------------------------------------------------------


def check_skill(skill_dir) -> list:
    """SKILL.md 一式を検査し Violation の一覧を返す。空リストなら受入。"""
    skill_dir = Path(skill_dir)
    skill_md = skill_dir / "SKILL.md"
    v = []

    # AC-C02-1: build_target に SKILL.md が実在する
    if not skill_md.is_file():
        v.append(Violation("AC-C02-1", f"SKILL.md が存在しない: {skill_md}"))
        return v

    text = skill_md.read_text(encoding="utf-8")
    fm, body = split_frontmatter(text)
    if fm is None:
        v.append(Violation("AC-C02-2", "YAML frontmatter が無い"))
        return v

    body_lines = body.splitlines()

    # --- identity ---------------------------------------------------------

    # AC-C02-2: identity (brief skill_name / prefix / kind / hierarchy_level)
    identity = {"name": SKILL_NAME, "prefix": "run", "kind": "run", "hierarchy": "L1"}
    for key, want in identity.items():
        if fm.get(key) != want:
            v.append(Violation(
                "AC-C02-2",
                f"frontmatter {key} は {want!r} でなければならない (実際: {fm.get(key)!r})",
            ))

    # AC-C02-3: description が trigger_conditions から発見可能
    desc = fm.get("description")
    if not isinstance(desc, str) or not desc.strip():
        v.append(Violation("AC-C02-3", "description が空"))
    else:
        if not desc.rstrip().rstrip("。").endswith("使う"):
            v.append(Violation("AC-C02-3", "description が「〜したいときに使う」形で終わっていない"))
        if "逆抽出" not in desc:
            v.append(Violation("AC-C02-3", "description に trigger_conditions の語彙 (逆抽出) が無い"))
        if "HTML" not in desc:
            v.append(Violation("AC-C02-3", "description に trigger_conditions の語彙 (HTML) が無い"))
        if "構成データ" not in desc:
            v.append(Violation("AC-C02-3", "description に trigger_conditions の語彙 (構成データ) が無い"))

    # --- 責務 -------------------------------------------------------------

    # AC-C02-4: responsibilities は R1-scan / R2-complete / R3-roundtrip の 3 件ちょうど
    resp = [r for r in _as_list(fm.get("responsibilities")) if isinstance(r, dict)]
    ids = [r.get("id") for r in resp]
    if list(ids) != list(REQUIRED_RESPONSIBILITIES):
        v.append(Violation(
            "AC-C02-4",
            f"responsibilities は {list(REQUIRED_RESPONSIBILITIES)} と一致しなければならない (実際: {ids})",
        ))
    for r in resp:
        if r.get("prompt_required") is not True:
            v.append(Violation("AC-C02-4", f"responsibility {r.get('id')} の prompt_required が true でない"))

    # AC-C02-5: responsibility_refs が prompts/<R-id>.md を指し実在する
    refs = [str(x) for x in _as_list(fm.get("responsibility_refs"))]
    for rid in REQUIRED_RESPONSIBILITIES:
        want = f"prompts/{rid}.md"
        if want not in refs:
            v.append(Violation("AC-C02-5", f"responsibility_refs に {want} が無い"))
        elif not (skill_dir / want).is_file():
            v.append(Violation("AC-C02-5", f"{want} が実在しない"))

    # --- combinator / feedback contract -----------------------------------

    # AC-C02-6: combinators / goal_seek
    combinators = [str(x) for x in _as_list(fm.get("combinators"))]
    for c in REQUIRED_COMBINATORS:
        if c not in combinators:
            v.append(Violation("AC-C02-6", f"combinators に {c} が無い"))
    gs = fm.get("goal_seek")
    if not isinstance(gs, dict):
        v.append(Violation("AC-C02-6", "goal_seek ブロックが無い"))
    else:
        for key, want in REQUIRED_GOAL_SEEK.items():
            if gs.get(key) != want:
                v.append(Violation("AC-C02-6", f"goal_seek.{key} は {want!r} (実際: {gs.get(key)!r})"))

    # AC-C02-7: feedback_contract criteria IN1 / OUT1
    fc = fm.get("feedback_contract")
    criteria = []
    if isinstance(fc, dict):
        criteria = [c for c in _as_list(fc.get("criteria")) if isinstance(c, dict)]
    if not criteria:
        v.append(Violation("AC-C02-7", "feedback_contract.criteria が無い"))
    else:
        found = {c.get("id"): c for c in criteria}
        extra = sorted(k for k in found if k not in REQUIRED_CRITERIA)
        if extra:
            v.append(Violation("AC-C02-7", f"criteria に inventory 外の id がある: {extra}"))
        for cid, (scope, verify_by) in REQUIRED_CRITERIA.items():
            c = found.get(cid)
            if c is None:
                v.append(Violation("AC-C02-7", f"criteria に {cid} が無い"))
                continue
            if c.get("loop_scope") != scope:
                v.append(Violation("AC-C02-7", f"{cid}.loop_scope は {scope} (実際: {c.get('loop_scope')})"))
            if c.get("verify_by") != verify_by:
                v.append(Violation("AC-C02-7", f"{cid}.verify_by は {verify_by} (実際: {c.get('verify_by')})"))
            if not str(c.get("text") or "").strip():
                v.append(Violation("AC-C02-7", f"{cid}.text が空"))

    # --- 本文骨格 ----------------------------------------------------------

    # AC-C02-8: 必須セクション
    for heading in REQUIRED_SECTIONS:
        if not any(line.strip() == heading for line in body_lines):
            v.append(Violation("AC-C02-8", f"必須セクション {heading!r} が無い"))
    for heading in REQUIRED_SUBSECTIONS:
        if not any(line.strip() == heading for line in body_lines):
            v.append(Violation("AC-C02-8", f"必須サブセクション {heading!r} が無い"))

    # AC-C02-9: Criteria acceptance が全 criteria id に言及する
    accept = _section_text(body_lines, "## Criteria acceptance")
    if accept is None:
        v.append(Violation("AC-C02-9", "## Criteria acceptance 節が無い"))
    else:
        for cid in REQUIRED_CRITERIA:
            if cid not in accept:
                v.append(Violation("AC-C02-9", f"## Criteria acceptance が {cid} に言及していない"))

    # AC-C02-10: deterministic_checks 4 本が script_refs にあり実在する
    script_refs = [str(x) for x in _as_list(fm.get("script_refs"))]
    for name in REQUIRED_SCRIPTS:
        hit = [r for r in script_refs if r.endswith("/" + name) or r == name]
        if not hit:
            v.append(Violation("AC-C02-10", f"script_refs に {name} が無い"))
            continue
        for ref in hit:
            if not (skill_dir / ref).resolve().is_file():
                v.append(Violation("AC-C02-10", f"script_refs {ref} の実体が存在しない"))

    # --- 逆抽出の入出力契約 -------------------------------------------------

    # AC-C02-11: HTML の parse を自前で行わない (C20 single_writer)
    if "自前で HTML を parse しない" not in body:
        v.append(Violation("AC-C02-11", "HTML の走査を C20 へ委譲し自前で parse しない旨の宣言が無い"))
    if "extract-handout-config.py" not in body:
        v.append(Violation("AC-C02-11", "R1-scan で extract-handout-config.py (C20) を起動する宣言が無い"))
    for pattern in SELF_PARSE_PATTERNS:
        m = re.search(pattern, body)
        if m:
            v.append(Violation(
                "AC-C02-11",
                f"自前 HTML 解析の記述を持ってはならない (C20 が唯一の逆写像実装): {m.group(0)!r}",
            ))

    # AC-C02-12: round-trip の粒度 (正規化後の構成データ等価 / provenance 除外)
    if "構成データ等価" not in body:
        v.append(Violation("AC-C02-12", "round-trip の合格条件が『構成データ等価』であると宣言されていない"))
    if "正規化" not in body:
        v.append(Violation("AC-C02-12", "比較前に C12 で正規化を揃える旨の宣言が無い"))
    if "provenance" not in body:
        v.append(Violation("AC-C02-12", "比較対象射影から provenance を除く宣言が無い (C20 comparable_projection)"))
    if "バイト一致は課さない" not in body:
        v.append(Violation("AC-C02-12", "HTML のバイト一致を課さない旨の宣言が無い"))
    m = re.search(r"バイト一致.{0,12}(で|により)\s*(round-trip|等価)", body)
    if m:
        v.append(Violation("AC-C02-12", f"round-trip をバイト一致で判定してはならない: {m.group(0)!r}"))

    # AC-C02-13: 復元不能な意味情報を推測しない (C20 never_guessed)
    if "マーカーが無い限り推測しない" not in body:
        v.append(Violation("AC-C02-13", "マーカーが無い限り意味情報を推測しない旨の宣言が無い (C20 never_guessed)"))
    for field in NEVER_GUESSED:
        if field not in body:
            v.append(Violation("AC-C02-13", f"復元しない意味情報の具体名 {field!r} が列挙されていない"))
    if "null" not in body:
        v.append(Violation("AC-C02-13", "復元不能箇所を null のまま残す旨の宣言が無い"))

    # AC-C02-14: 復元不能箇所は キーパス / 理由 / 補完方針 の 3 点セットで列挙する
    for token in ("キーパス", "理由", "補完方針"):
        if token not in body:
            v.append(Violation("AC-C02-14", f"復元不能箇所の報告 3 点セットの要素 {token!r} が無い"))
    for policy in COMPLETION_POLICIES:
        if policy not in body:
            v.append(Violation("AC-C02-14", f"補完方針の選択肢 {policy!r} が明示されていない"))
    if "黙って" not in body:
        v.append(Violation("AC-C02-14", "復元不能箇所を黙って欠落させない旨の宣言が無い"))

    # AC-C02-15: 推測で埋めた値と実読み取り値をレポート上で区別する
    if "fidelity" not in body:
        v.append(Violation("AC-C02-15", "レポートの fidelity (exact / heuristic) 区分の宣言が無い"))
    for token in ("exact", "heuristic"):
        if token not in body:
            v.append(Violation("AC-C02-15", f"fidelity の値 {token!r} が宣言されていない"))
    if "W-EXTRACT-HEURISTIC" not in body:
        v.append(Violation("AC-C02-15", "heuristic 復元の診断コード W-EXTRACT-HEURISTIC への言及が無い"))
    if "区別" not in body:
        v.append(Violation("AC-C02-15", "推測値と実読み取り値を区別する旨の宣言が無い"))

    # AC-C02-16: output_contract (構成データ JSON + 逆抽出レポート 3 要素)
    purpose = _section_text(body_lines, "## Purpose & Output Contract") or ""
    if "構成データ JSON" not in purpose:
        v.append(Violation("AC-C02-16", "Purpose & Output Contract に構成データ JSON の宣言が無い"))
    if "逆抽出レポート" not in purpose:
        v.append(Violation("AC-C02-16", "Purpose & Output Contract に逆抽出レポートの宣言が無い"))
    for element in REPORT_ELEMENTS:
        if element not in purpose:
            v.append(Violation("AC-C02-16", f"逆抽出レポートの要素 {element!r} が宣言されていない"))

    # AC-C02-17: boundary (資料内容の書き換え・改善提案をしない)
    if "資料内容の書き換え" not in body or "改善提案" not in body:
        v.append(Violation("AC-C02-17", "資料内容の書き換え・改善提案をしない旨の boundary 宣言が無い"))
    m = re.search(r"改善(案|提案)を(出す|添える|提示する|返す)", body)
    if m:
        v.append(Violation("AC-C02-17", f"改善提案は C02 の boundary 外である: {m.group(0)!r}"))

    # AC-C02-18: 生成は C07 の責務。構成データを出すところで止まる
    if "/handout-build" not in body:
        v.append(Violation("AC-C02-18", "次の一手として /handout-build (C07) を案内する宣言が無い"))
    if "構成データを出すところで止まる" not in body:
        v.append(Violation("AC-C02-18", "資料生成へ踏み込まず構成データで止まる旨の宣言が無い"))

    # AC-C02-19: 検証 FAIL 時に値を捏造しない / 空の構成データを成功にしない
    if "validate-handout-config.py" not in body:
        v.append(Violation("AC-C02-19", "逆抽出結果を validate-handout-config.py (C12) にかける宣言が無い"))
    if "捏造" not in body:
        v.append(Violation("AC-C02-19", "検証を通すために値を捏造しない旨の宣言が無い"))
    if "空の構成データを成功として返さない" not in body:
        v.append(Violation("AC-C02-19", "空 / 穴つきの構成データを成功として返さない旨の宣言が無い"))
    if "欠落キーパス" not in body:
        v.append(Violation("AC-C02-19", "FAIL 時に欠落キーパスを提示する宣言が無い"))

    # AC-C02-20: round-trip 差分を等価と読める要約にしない
    if "E-ROUNDTRIP-DIFF" not in body:
        v.append(Violation("AC-C02-20", "round-trip 差分の診断コード E-ROUNDTRIP-DIFF への言及が無い"))
    if "JSON Pointer" not in body:
        v.append(Violation("AC-C02-20", "差分を JSON Pointer で示す宣言が無い"))
    for token in ("expected", "actual"):
        if token not in body:
            v.append(Violation("AC-C02-20", f"差分提示に {token} が無い"))
    if "等価と読める要約にしない" not in body:
        v.append(Violation("AC-C02-20", "差分ありを等価と読める要約にしない旨の宣言が無い"))

    # --- 依存とメタ --------------------------------------------------------

    # AC-C02-21: depends_on (inventory C02)
    depends = [str(x) for x in _as_list(fm.get("depends_on"))]
    for dep in REQUIRED_DEPENDS_ON:
        if dep not in depends:
            v.append(Violation("AC-C02-21", f"frontmatter depends_on に {dep} が無い"))

    # AC-C02-22: allowed-tools
    tools = [str(x) for x in _as_list(fm.get("allowed-tools"))]
    for tool in ("Read", "Write", "Bash"):
        if tool not in tools:
            v.append(Violation("AC-C02-22", f"allowed-tools に {tool} が無い"))

    # AC-C02-23: output_language
    if fm.get("output_language") != "ja":
        v.append(Violation("AC-C02-23", f"output_language は ja (実際: {fm.get('output_language')!r})"))

    # AC-C02-24: 出所の追跡
    if "component-inventory.json#C02" not in str(fm.get("source") or ""):
        v.append(Violation("AC-C02-24", "frontmatter source が component-inventory.json#C02 を指していない"))

    # AC-C02-25: 抽出器の起動引数 (--html / --out / --report)
    for flag in ("--html", "--out", "--report"):
        if flag not in body:
            v.append(Violation("AC-C02-25", f"extract-handout-config.py へ渡す {flag} の宣言が無い"))

    # AC-C02-26: R3-roundtrip の再レンダリング経路
    if "render-handout.py" not in body:
        v.append(Violation("AC-C02-26", "R3-roundtrip で render-handout.py (C11) による再レンダリングを行う宣言が無い"))
    if "再レンダリング" not in body:
        v.append(Violation("AC-C02-26", "再レンダリングして等価判定する旨の宣言が無い"))
    if "verify-handout-selfcontained.py" not in body:
        v.append(Violation("AC-C02-26", "再レンダリング結果を verify-handout-selfcontained.py (C16) にかける宣言が無い"))

    # AC-C02-27: 完了チェックリストが brief checklist の 4 項目を覆う
    checklist = _section_text(body_lines, "### 完了チェックリスト") or ""
    for item in REQUIRED_CHECKLIST:
        if item not in checklist:
            v.append(Violation("AC-C02-27", f"完了チェックリストに brief checklist の {item!r} が無い"))

    return v


def violation_ids(violations):
    return [x.contract_id for x in violations]


def repo_root() -> Path:
    return Path(__file__).resolve().parents[4]


def build_target_dir() -> Path:
    return repo_root() / BUILD_TARGET
