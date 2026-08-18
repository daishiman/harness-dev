"""run-handout-build (C01) の SKILL.md 宣言的契約チェッカ。

skill component は実行そのものを機械検査できないため、検査対象は SKILL.md の
宣言 (frontmatter / 必須セクション / 参照スクリプトの実在 / ヒアリング必須項目 /
呼び出す component の宣言) である。

契約の出典:
  - plugin-plans/guide-doc-generator/briefs/skill-brief-C01.json (正本)
  - plugin-plans/guide-doc-generator/component-inventory.json #C01
  - plugin-plans/guide-doc-generator/briefs/RESOLUTION-P03.md (Y-04 / Y-07 / Y-09)
  - plugin-plans/guide-doc-generator/briefs/RESOLUTION-R21.md (C57 / C58)

標準ライブラリのみを使う (PyYAML は使わない)。frontmatter は本 plugin の
SKILL.md が使う YAML 部分集合だけを解釈する簡易パーサで読む。
"""

from __future__ import annotations

import re
from collections import namedtuple
from pathlib import Path

Violation = namedtuple("Violation", ["contract_id", "message"])


# --------------------------------------------------------------------------
# 契約の定数 (すべてブリーフ / inventory / RESOLUTION 由来)
# --------------------------------------------------------------------------

SKILL_NAME = "run-handout-build"
BUILD_TARGET = "plugins/guide-doc-generator/skills/run-handout-build/"

# skill-brief-C01.json responsibilities[].id
REQUIRED_RESPONSIBILITIES = ("R1-elicit", "R2-design", "R3-render", "R4-verify", "R5-refine")

# skill-brief-C01.json deterministic_checks
REQUIRED_SCRIPTS = (
    "validate-handout-config.py",
    "resolve-handout-preset.py",
    "verify-handout-selfcontained.py",
    "verify-handout-a11y-print.py",
    "verify-handout-language.py",
    "verify-handout-narrative.py",
    "route-handout-output.py",
)

# component-inventory.json #C01 feedback_contract.criteria
REQUIRED_CRITERIA = {
    "IN1": ("inner", "script"),
    "OUT1": ("outer", "test"),
    "OUT2": ("outer", "test"),
    "OUT3": ("outer", "live-trial"),
}

# component-inventory.json #C01 goal_seek
REQUIRED_GOAL_SEEK = {"engine": "inline", "fork": "subagent", "max_loops": 5}

# component-inventory.json #C01 combinators
REQUIRED_COMBINATORS = ("with-goal-seek", "with-feedback-contract")

# skill-brief-C01.json hearing_required_items_r21.items[].field
REQUIRED_HEARING_FIELDS = (
    "target_tasks",
    "focus_theme",
    "attainment_level",
    "must_remember",
    "no_need_to_remember",
)

# 本 repo の run 系 skill が共有する本文骨格 (plugins/dev-graph/skills/run-*/SKILL.md)
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

# skill-brief-C01.json readme_writer の 5 節
README_SECTIONS = ("原題", "目的", "適用プリセット", "同梱物一覧", "使い方")

# skill-brief-C01.json output_contract の生成レポート要素
REPORT_ELEMENTS = ("適用部品", "埋め込みサイズ", "warning", "ゲート結果")

WRITE_VERBS = ("書く", "書き込", "複製", "配置")


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
# 検査本体
# --------------------------------------------------------------------------


def _as_list(value):
    if value is None:
        return []
    if isinstance(value, list):
        return value
    return [value]


def _hearing_items(fm):
    block = fm.get("hearing_required_items_r21")
    if isinstance(block, dict):
        return [i for i in _as_list(block.get("items")) if isinstance(i, dict)]
    if isinstance(block, list):
        return [i for i in block if isinstance(i, dict)]
    return []


def check_skill(skill_dir) -> list:
    """SKILL.md 一式を検査し Violation の一覧を返す。空リストなら受入。"""
    skill_dir = Path(skill_dir)
    skill_md = skill_dir / "SKILL.md"
    v = []

    # AC-C01-1: build_target に SKILL.md が実在する
    if not skill_md.is_file():
        v.append(Violation("AC-C01-1", f"SKILL.md が存在しない: {skill_md}"))
        return v

    text = skill_md.read_text(encoding="utf-8")
    fm, body = split_frontmatter(text)
    if fm is None:
        v.append(Violation("AC-C01-2", "YAML frontmatter が無い"))
        return v

    body_lines = body.splitlines()

    # AC-C01-2: identity
    identity = {"name": SKILL_NAME, "prefix": "run", "kind": "run", "hierarchy": "L1"}
    for key, want in identity.items():
        if fm.get(key) != want:
            v.append(Violation("AC-C01-2", f"frontmatter {key} は {want!r} でなければならない (実際: {fm.get(key)!r})"))

    # AC-C01-3: description (trigger_conditions からの発見可能性)
    desc = fm.get("description")
    if not isinstance(desc, str) or not desc.strip():
        v.append(Violation("AC-C01-3", "description が空"))
    else:
        if not desc.rstrip().endswith("使う。") and not desc.rstrip().endswith("使う"):
            v.append(Violation("AC-C01-3", "description が「〜したいときに使う」形で終わっていない"))
        if "handout" not in desc and "資料" not in desc:
            v.append(Violation("AC-C01-3", "description に trigger_conditions の語彙 (handout / 資料) が無い"))

    # AC-C01-4: responsibilities が brief と完全一致し prompt_required: true
    resp = [r for r in _as_list(fm.get("responsibilities")) if isinstance(r, dict)]
    ids = [r.get("id") for r in resp]
    if list(ids) != list(REQUIRED_RESPONSIBILITIES):
        v.append(Violation("AC-C01-4", f"responsibilities は {list(REQUIRED_RESPONSIBILITIES)} と一致しなければならない (実際: {ids})"))
    for r in resp:
        if r.get("prompt_required") is not True:
            v.append(Violation("AC-C01-4", f"responsibility {r.get('id')} の prompt_required が true でない"))

    # AC-C01-5: responsibility_refs が prompts/<R-id>.md を指し実在する
    refs = [str(x) for x in _as_list(fm.get("responsibility_refs"))]
    for rid in REQUIRED_RESPONSIBILITIES:
        want = f"prompts/{rid}.md"
        if want not in refs:
            v.append(Violation("AC-C01-5", f"responsibility_refs に {want} が無い"))
        elif not (skill_dir / want).is_file():
            v.append(Violation("AC-C01-5", f"{want} が実在しない"))

    # AC-C01-6: combinators / goal_seek
    combinators = [str(x) for x in _as_list(fm.get("combinators"))]
    for c in REQUIRED_COMBINATORS:
        if c not in combinators:
            v.append(Violation("AC-C01-6", f"combinators に {c} が無い"))
    gs = fm.get("goal_seek")
    if not isinstance(gs, dict):
        v.append(Violation("AC-C01-6", "goal_seek ブロックが無い"))
    else:
        for key, want in REQUIRED_GOAL_SEEK.items():
            if gs.get(key) != want:
                v.append(Violation("AC-C01-6", f"goal_seek.{key} は {want!r} (実際: {gs.get(key)!r})"))

    # AC-C01-7: feedback_contract criteria IN1 / OUT1 / OUT2
    fc = fm.get("feedback_contract")
    criteria = []
    if isinstance(fc, dict):
        criteria = [c for c in _as_list(fc.get("criteria")) if isinstance(c, dict)]
    if not criteria:
        v.append(Violation("AC-C01-7", "feedback_contract.criteria が無い"))
    else:
        found = {c.get("id"): c for c in criteria}
        for cid, (scope, verify_by) in REQUIRED_CRITERIA.items():
            c = found.get(cid)
            if c is None:
                v.append(Violation("AC-C01-7", f"criteria に {cid} が無い"))
                continue
            if c.get("loop_scope") != scope:
                v.append(Violation("AC-C01-7", f"{cid}.loop_scope は {scope} (実際: {c.get('loop_scope')})"))
            if c.get("verify_by") != verify_by:
                v.append(Violation("AC-C01-7", f"{cid}.verify_by は {verify_by} (実際: {c.get('verify_by')})"))
            if not str(c.get("text") or "").strip():
                v.append(Violation("AC-C01-7", f"{cid}.text が空"))

    # AC-C01-8: 必須セクション
    for heading in REQUIRED_SECTIONS:
        if not any(line.strip() == heading for line in body_lines):
            v.append(Violation("AC-C01-8", f"必須セクション {heading!r} が無い"))
    for heading in REQUIRED_SUBSECTIONS:
        if not any(line.strip() == heading for line in body_lines):
            v.append(Violation("AC-C01-8", f"必須サブセクション {heading!r} が無い"))

    # AC-C01-9: Criteria acceptance が全 criteria id に言及する
    accept = _section_text(body_lines, "## Criteria acceptance")
    if accept is None:
        v.append(Violation("AC-C01-9", "## Criteria acceptance 節が無い"))
    else:
        for cid in REQUIRED_CRITERIA:
            if cid not in accept:
                v.append(Violation("AC-C01-9", f"## Criteria acceptance が {cid} に言及していない"))

    # AC-C01-10: deterministic_checks 7 本が script_refs にあり実在する
    script_refs = [str(x) for x in _as_list(fm.get("script_refs"))]
    for name in REQUIRED_SCRIPTS:
        hit = [r for r in script_refs if r.endswith("/" + name) or r == name]
        if not hit:
            v.append(Violation("AC-C01-10", f"script_refs に {name} が無い"))
            continue
        for ref in hit:
            if not (skill_dir / ref).resolve().is_file():
                v.append(Violation("AC-C01-10", f"script_refs {ref} の実体が存在しない"))

    # AC-C01-11: R21 ヒアリング必須 5 項目
    items = _hearing_items(fm)
    by_field = {i.get("field"): i for i in items}
    if set(by_field) != set(REQUIRED_HEARING_FIELDS):
        v.append(Violation(
            "AC-C01-11",
            f"hearing_required_items_r21 の field 集合は {sorted(REQUIRED_HEARING_FIELDS)} と一致しなければならない (実際: {sorted(k for k in by_field)})",
        ))
    for field in REQUIRED_HEARING_FIELDS:
        item = by_field.get(field)
        if item is None:
            continue
        if item.get("required") is not True:
            v.append(Violation("AC-C01-11", f"ヒアリング項目 {field} の required が true でない"))
        if not str(item.get("question_ja") or "").strip():
            v.append(Violation("AC-C01-11", f"ヒアリング項目 {field} の question_ja が空"))

    # AC-C01-12: target_tasks は 1 件以上必須 (R21 C58)
    tt = by_field.get("target_tasks")
    if tt is None:
        v.append(Violation("AC-C01-12", "ヒアリング項目 target_tasks が宣言されていない (R21 C58)"))
    else:
        if tt.get("min_count") != 1:
            v.append(Violation("AC-C01-12", f"target_tasks.min_count は 1 (実際: {tt.get('min_count')!r})"))
        if "E-TARGET-TASKS-EMPTY" not in str(tt.get("checked_by") or ""):
            v.append(Violation("AC-C01-12", "target_tasks.checked_by が C12 E-TARGET-TASKS-EMPTY を指していない"))

    # AC-C01-13: must_remember / no_need_to_remember は対で必須 (R21 C57)
    mr = by_field.get("must_remember")
    nn = by_field.get("no_need_to_remember")
    if mr is None or nn is None:
        v.append(Violation("AC-C01-13", "must_remember と no_need_to_remember は対で宣言しなければならない"))
    else:
        if mr.get("paired_with") != "no_need_to_remember":
            v.append(Violation("AC-C01-13", "must_remember.paired_with が no_need_to_remember でない"))
        if nn.get("paired_with") != "must_remember":
            v.append(Violation("AC-C01-13", "no_need_to_remember.paired_with が must_remember でない"))
        if mr.get("max_count") != 2:
            v.append(Violation("AC-C01-13", f"must_remember.max_count は 2 (実際: {mr.get('max_count')!r})"))
        for item, field in ((mr, "must_remember"), (nn, "no_need_to_remember")):
            if "E-REMEMBER-PAIR" not in str(item.get("checked_by") or ""):
                v.append(Violation("AC-C01-13", f"{field}.checked_by が C12 E-REMEMBER-PAIR を指していない"))

    # AC-C01-14: 提示順はヒアリング項目にしない (CR-PRESENTATION-ORDER)
    if "presentation_order" in by_field:
        v.append(Violation("AC-C01-14", "presentation_order をヒアリング必須項目にしてはならない (R21 CR-PRESENTATION-ORDER)"))
    if "CR-PRESENTATION-ORDER" not in body:
        v.append(Violation("AC-C01-14", "提示順が C12 の CR-PRESENTATION-ORDER で導出される旨の宣言が無い"))
    for line in body_lines:
        if ("提示順" in line or "demo_first" in line) and "ですか" in line:
            v.append(Violation("AC-C01-14", f"提示順を尋ねる質問文を持ってはならない: {line.strip()!r}"))

    # AC-C01-15: ゲート結果集約は C09 が正本 (P03 Y-07)
    if "/handout-verify" not in body:
        v.append(Violation("AC-C01-15", "4 ゲートを /handout-verify (C09) 経由で実行する宣言が無い"))
    if "CR-GATE-AGG" not in body:
        v.append(Violation("AC-C01-15", "集約規則の正本 CR-GATE-AGG への参照が無い"))
    if not re.search(r"再実装(も再解釈)?も?しない", body):
        v.append(Violation("AC-C01-15", "集約規則を再実装しない旨の宣言が無い"))
    if re.search(r"not-run\s*(を|は)\s*pass", body):
        v.append(Violation("AC-C01-15", "not-run を pass と読み替える記述を持ってはならない"))
    for line in body_lines:
        states = sum(1 for s in ("pass", "fail", "error", "not-run") if s in line)
        if states == 4 and "C09" not in line and "CR-GATE-AGG" not in line:
            v.append(Violation("AC-C01-15", f"4 状態分類を C09 に帰属させずに自前で列挙している: {line.strip()!r}"))

    # AC-C01-16: 同梱物の writer 境界 (P03 Y-04)
    for flag in ("--place-config", "--assets-src"):
        if flag not in body:
            v.append(Violation("AC-C01-16", f"C19 へ渡す {flag} の宣言が無い"))
    for line in body_lines:
        target = "handout-config.json" in line or "assets/" in line
        if target and any(w in line for w in WRITE_VERBS) and "C19" not in line:
            v.append(Violation("AC-C01-16", f"handout-config.json / assets/ の配置は C19 の責務であり自分では置かない: {line.strip()!r}"))

    # AC-C01-17: README.md の writer は C01 で 5 節を持つ
    # body 全体への部分文字列一致だと、同梱物一覧やチェックリストでの README.md への
    # 言及だけで宣言が成立し、writer 宣言を消した本文を検出できない。また 5 節の語
    # (目的 など) は他節の見出しにも現れるため、宣言を消しても違反状態にならない。
    # 判定スコープを「README.md を書く旨を述べた行」に寄せる (PREDICATE-SCOPE-POLICY.md)。
    readme_decl = [l for l in body_lines if "README.md" in l and any(w in l for w in WRITE_VERBS)]
    if not readme_decl:
        v.append(Violation("AC-C01-17", "README.md の writer である旨の宣言が無い"))
    readme_scope = "\n".join(readme_decl)
    for sec in README_SECTIONS:
        if sec not in readme_scope:
            v.append(Violation("AC-C01-17", f"README.md の必須節 {sec!r} の宣言が無い"))

    # AC-C01-18: 読みやすさ判定は C03 へ委譲 (P03 Y-09)
    depends = [str(x) for x in _as_list(fm.get("depends_on"))]
    if "C03" not in depends:
        v.append(Violation("AC-C01-18", "frontmatter depends_on に C03 が無い (P03 Y-09)"))
    if "assign-handout-readability-evaluator" not in body:
        v.append(Violation("AC-C01-18", "読みやすさの最終判定を assign-handout-readability-evaluator (C03) へ委譲する宣言が無い"))

    # AC-C01-19: 非対話経路 (検証済み構成データ直渡し) を塞がない
    # 宣言は「非対話」を扱う節の中に無ければならない。body 全体への部分文字列一致だと
    # 節見出しや入力一覧の言及だけで条件が満たされ、経路を塞いだ本文を検出できない。
    # そのような節が無い skill では従来どおり body 全体を見る (fallback は現行と同等)。
    noninteractive = _section_text_containing(body_lines, "非対話")
    scope = noninteractive if noninteractive is not None else body
    if "検証済みの構成データ" not in scope:
        v.append(Violation("AC-C01-19", "検証済み構成データを直接受け取る経路の宣言が無い"))
    if "非対話" not in scope and "ヒアリングを省" not in scope:
        v.append(Violation("AC-C01-19", "非対話経路 (ヒアリングを省く経路) の宣言が無い"))

    # AC-C01-20: HTML の組み立ては決定論 script へ委譲する
    # 「決定論」は完了チェックリスト等にも現れるため body 全体一致では委譲宣言を
    # 消しても違反状態にならない。判定スコープを委譲宣言行へ寄せる
    # (PREDICATE-SCOPE-POLICY.md)。
    llm_decl = [l for l in body_lines if "LLM で書かない" in l]
    if not llm_decl:
        v.append(Violation("AC-C01-20", "HTML を LLM で書かない旨の宣言が無い"))
    if "決定論" not in "\n".join(llm_decl):
        v.append(Violation("AC-C01-20", "決定論 script への委譲の宣言が無い"))

    # AC-C01-21: output_contract (同梱 4 点 + 生成レポート 4 要素)
    purpose = _section_text(body_lines, "## Purpose & Output Contract") or ""
    for bundled in ("handout.html", "handout-config.json", "assets/", "README.md"):
        if bundled not in purpose:
            v.append(Violation("AC-C01-21", f"Purpose & Output Contract に同梱物 {bundled} の宣言が無い"))
    for element in REPORT_ELEMENTS:
        if element not in purpose:
            v.append(Violation("AC-C01-21", f"Purpose & Output Contract に生成レポート要素 {element!r} が無い"))

    # AC-C01-22: allowed-tools (決定論 script 起動と README 書き込みに要る)
    tools = [str(x) for x in _as_list(fm.get("allowed-tools"))]
    for tool in ("Read", "Write", "Bash"):
        if tool not in tools:
            v.append(Violation("AC-C01-22", f"allowed-tools に {tool} が無い"))

    # AC-C01-23: output_language
    if fm.get("output_language") != "ja":
        v.append(Violation("AC-C01-23", f"output_language は ja (実際: {fm.get('output_language')!r})"))

    # AC-C01-24: 出所の追跡
    if "component-inventory.json#C01" not in str(fm.get("source") or ""):
        v.append(Violation("AC-C01-24", "frontmatter source が component-inventory.json#C01 を指していない"))

    return v


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


def _section_text_containing(body_lines, keyword):
    """見出し語に keyword を含む最初の節の本文を返す。無ければ None。

    見出し行自体は含めない (見出しの語だけで宣言が成立したと誤判定しないため)。
    """
    for line in body_lines:
        stripped = line.strip()
        if not stripped.startswith("#"):
            continue
        if keyword in stripped:
            return _section_text(body_lines, stripped)
    return None


def violation_ids(violations):
    return [x.contract_id for x in violations]


def repo_root() -> Path:
    return Path(__file__).resolve().parents[4]


def build_target_dir() -> Path:
    return repo_root() / BUILD_TARGET
