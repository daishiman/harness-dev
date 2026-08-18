"""assign-handout-readability-evaluator (C03) の SKILL.md 宣言的契約チェッカ。

skill component は実行そのものを機械検査できないため、検査対象は SKILL.md の
宣言 (frontmatter / 必須セクション / 委譲先 agent と script の実在 / 委譲の
入出力契約 / 責務境界) である。

C03 は「初心者に伝わるか」を自分で判定せず、独立 context の sub-agent
handout-readability-reviewer (C06) へ委譲し、verdict を回収する assign 系 skill
である。したがって契約の重心は「判定基準を持たないこと」と「委譲の入出力が
欠落なく運ばれること」の 2 点にある。

契約の出典:
  - plugin-plans/guide-doc-generator/briefs/skill-brief-C03.json (C03 の正本)
  - plugin-plans/guide-doc-generator/component-inventory.json #C03 / #C06
  - plugin-plans/guide-doc-generator/briefs/agent-brief-C06.json (委譲先の入出力契約の正本)
  - plugin-plans/guide-doc-generator/briefs/RESOLUTION-P03.md (Y-07 / Y-09)
  - plugin-plans/guide-doc-generator/briefs/RESOLUTION-R21.md

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

SKILL_NAME = "assign-handout-readability-evaluator"
BUILD_TARGET = "plugins/guide-doc-generator/skills/assign-handout-readability-evaluator/"

# component-inventory.json #C06 name / build_target
REVIEWER_AGENT = "handout-readability-reviewer"
AGENT_REF = "../../agents/handout-readability-reviewer.md"

# skill-brief-C03.json responsibilities[].id
REQUIRED_RESPONSIBILITIES = ("R1-assign",)

# agent-brief-C06.json prompt_ref (owner skill 配下の責務 prompt)
PROMPT_REF = "prompts/R-review-readability.md"

# skill-brief-C03.json deterministic_checks
REQUIRED_SCRIPTS = ("verify-handout-language.py",)

# component-inventory.json #C03 depends_on
REQUIRED_DEPENDS = ("C04", "C18")

# agent-brief-C06.json input_contract.receives / procedure 1 (起動の前提となる 4 ゲート)
GATE_COMPONENTS = ("C16", "C17", "C18", "C22")

# agent-brief-C06.json input_contract.receives の必須フィールド
DELEGATION_INPUTS = ("html_path", "config_path", "gate_reports", "reader_profile")

# agent-brief-C06.json output_contract.returns のトップレベルキー
VERDICT_KEYS = (
    "status",
    "verdict",
    "reviewed_as",
    "findings",
    "strengths",
    "not_reviewed",
    "blocked_reason",
)

# agent-brief-C06.json output_contract.returns の findings[] の要素
FINDING_KEYS = (
    "severity",
    "axis",
    "location",
    "why_not_understood",
    "suggestion",
    "machine_gate_overlap",
)

# agent-brief-C06.json input_contract.must_not_assume の 5 項目 (C03 が渡してはならないもの)
MUST_NOT_PASS_KEYWORDS = ("設計意図", "ヒアリング", "参照 HTML", "過去", "loop")

# skill-brief-C03.json rubric_refs
REQUIRED_RUBRIC_REFS = ("ref-handout-design-system",)

# 本 repo の assign 系 skill が共有する本文骨格
# (plugins/*/skills/assign-*/SKILL.md の 6/7 が持つ見出し集合)
REQUIRED_SECTIONS = (
    "## Purpose & Output Contract",
    "## Key Rules",
    "## Gotchas",
    "## Additional Resources",
)

# 書き込み系ツール。C03 は verdict の運搬しかせず資料を書き換えない
# (skill-brief-C03.json boundary / agent-brief-C06.json boundary)
FORBIDDEN_TOOLS = ("Write", "Edit", "MultiEdit", "NotebookEdit")

# 委譲に使えるツール (いずれか 1 つ以上)
DELEGATION_TOOLS = ("Task", "Agent")


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


def _tool_names(fm):
    return [str(x) for x in _as_list(fm.get("allowed-tools"))]


def check_skill(skill_dir) -> list:
    """SKILL.md 一式を検査し Violation の一覧を返す。空リストなら受入。"""
    skill_dir = Path(skill_dir)
    skill_md = skill_dir / "SKILL.md"
    v = []

    # AC-C03-1: build_target に SKILL.md が実在する
    if not skill_md.is_file():
        v.append(Violation("AC-C03-1", f"SKILL.md が存在しない: {skill_md}"))
        return v

    text = skill_md.read_text(encoding="utf-8")
    fm, body = split_frontmatter(text)
    if fm is None:
        v.append(Violation("AC-C03-2", "YAML frontmatter が無い"))
        return v

    body_lines = body.splitlines()

    # AC-C03-2: identity (skill-brief-C03.json skill_name / prefix / kind / hierarchy_level)
    identity = {"name": SKILL_NAME, "prefix": "assign", "kind": "assign", "hierarchy": "L2"}
    for key, want in identity.items():
        if fm.get(key) != want:
            v.append(Violation(
                "AC-C03-2",
                f"frontmatter {key} は {want!r} でなければならない (実際: {fm.get(key)!r})",
            ))
    if fm.get("user-invocable") is not False:
        v.append(Violation(
            "AC-C03-2",
            f"assign 系は user-invocable: false (実際: {fm.get('user-invocable')!r})",
        ))

    # AC-C03-3: description (trigger_conditions からの発見可能性)
    desc = fm.get("description")
    if not isinstance(desc, str) or not desc.strip():
        v.append(Violation("AC-C03-3", "description が空"))
    else:
        if not desc.rstrip().endswith("使う。") and not desc.rstrip().endswith("使う"):
            v.append(Violation("AC-C03-3", "description が「〜したいときに使う」形で終わっていない"))
        if "読みやす" not in desc:
            v.append(Violation("AC-C03-3", "description に trigger_conditions の語彙 (読みやすさ) が無い"))
        if "レビュー" not in desc:
            v.append(Violation("AC-C03-3", "description に trigger_conditions の語彙 (レビュー) が無い"))
        if "handout" not in desc and "資料" not in desc:
            v.append(Violation("AC-C03-3", "description に trigger_conditions の語彙 (handout / 資料) が無い"))

    # AC-C03-4: 委譲の配線 (独立 context / 委譲先 agent の宣言と実在)
    if fm.get("context") != "fork":
        v.append(Violation(
            "AC-C03-4",
            f"needs_independent_context: true は context: fork を要求する (実際: {fm.get('context')!r})",
        ))
    if fm.get("agent") != REVIEWER_AGENT:
        v.append(Violation(
            "AC-C03-4",
            f"frontmatter agent は {REVIEWER_AGENT!r} (C06) でなければならない (実際: {fm.get('agent')!r})",
        ))
    agent_refs = [str(x) for x in _as_list(fm.get("agent_refs"))]
    if AGENT_REF not in agent_refs:
        v.append(Violation("AC-C03-4", f"agent_refs に {AGENT_REF} が無い"))
    elif not (skill_dir / AGENT_REF).resolve().is_file():
        v.append(Violation("AC-C03-4", f"委譲先 agent の実体が存在しない: {AGENT_REF}"))
    if REVIEWER_AGENT not in body:
        v.append(Violation("AC-C03-4", f"本文に委譲先 {REVIEWER_AGENT} (C06) の宣言が無い"))

    # AC-C03-5: responsibilities は R1-assign 1 件ちょうど
    resp = [r for r in _as_list(fm.get("responsibilities")) if isinstance(r, dict)]
    ids = [r.get("id") for r in resp]
    if list(ids) != list(REQUIRED_RESPONSIBILITIES):
        v.append(Violation(
            "AC-C03-5",
            f"responsibilities は {list(REQUIRED_RESPONSIBILITIES)} と一致しなければならない (実際: {ids})",
        ))
    for r in resp:
        if r.get("prompt_required") is not True:
            v.append(Violation("AC-C03-5", f"responsibility {r.get('id')} の prompt_required が true でない"))
        if not str(r.get("summary") or "").strip():
            v.append(Violation("AC-C03-5", f"responsibility {r.get('id')} の summary が空"))

    # AC-C03-6: 責務 prompt が宣言され実在する (agent-brief-C06.json prompt_ref)
    refs = [str(x) for x in _as_list(fm.get("responsibility_refs"))]
    if PROMPT_REF not in refs:
        v.append(Violation("AC-C03-6", f"responsibility_refs に {PROMPT_REF} が無い"))
    elif not (skill_dir / PROMPT_REF).is_file():
        v.append(Violation("AC-C03-6", f"{PROMPT_REF} が実在しない"))

    # AC-C03-7: depends_on は C04 / C18 (component-inventory.json #C03)
    depends = sorted(str(x) for x in _as_list(fm.get("depends_on")))
    if depends != sorted(REQUIRED_DEPENDS):
        v.append(Violation(
            "AC-C03-7",
            f"depends_on は {sorted(REQUIRED_DEPENDS)} と一致しなければならない (実際: {depends})",
        ))

    # AC-C03-8: deterministic_checks の script が宣言され実在する
    script_refs = [str(x) for x in _as_list(fm.get("script_refs"))]
    for name in REQUIRED_SCRIPTS:
        hit = [r for r in script_refs if r.endswith("/" + name) or r == name]
        if not hit:
            v.append(Violation("AC-C03-8", f"script_refs に {name} が無い"))
            continue
        for ref in hit:
            if not (skill_dir / ref).resolve().is_file():
                v.append(Violation("AC-C03-8", f"script_refs {ref} の実体が存在しない"))

    # AC-C03-9: 必須セクション
    for heading in REQUIRED_SECTIONS:
        if not any(line.strip() == heading for line in body_lines):
            v.append(Violation("AC-C03-9", f"必須セクション {heading!r} が無い"))

    # AC-C03-10: read-only 境界 (資料を書き換えない / 修正は C01)
    tools = _tool_names(fm)
    if not any(t == "Read" or t.startswith("Read(") for t in tools):
        v.append(Violation("AC-C03-10", "allowed-tools に Read が無い"))
    if not any(t.split("(")[0] in DELEGATION_TOOLS for t in tools):
        v.append(Violation(
            "AC-C03-10",
            f"allowed-tools に委譲手段 ({' / '.join(DELEGATION_TOOLS)}) が無い",
        ))
    for t in tools:
        if t.split("(")[0] in FORBIDDEN_TOOLS:
            v.append(Violation(
                "AC-C03-10",
                f"allowed-tools に書き込み系 {t!r} を含んではならない (資料の書き換えは C01 の責務)",
            ))
    if not re.search(r"資料[^。\n]{0,20}書き換え(は|を)?(し)?ない", body):
        v.append(Violation("AC-C03-10", "資料を書き換えない旨の宣言が無い"))
    if not re.search(r"修正は\s*C01", body):
        v.append(Violation("AC-C03-10", "修正が C01 の責務である旨の宣言が無い"))

    # AC-C03-11: 判定基準を持たない (自分で採点しない)
    if not re.search(r"判定基準[^。\n]{0,20}持たない", body):
        v.append(Violation("AC-C03-11", "本 skill が判定基準を持たない旨の宣言が無い"))
    if not re.search(r"(自分で|自身で|本 skill (が|は))[^。\n]{0,30}判定しない", body):
        v.append(Violation("AC-C03-11", "自分では判定しない旨の宣言が無い"))
    for line in body_lines:
        rule_like = "high" in line and "FAIL" in line
        if rule_like and "C06" not in line and REVIEWER_AGENT not in line:
            v.append(Violation(
                "AC-C03-11",
                f"verdict の決定規則を C06 に帰属させずに自前で持っている: {line.strip()!r}",
            ))

    # AC-C03-12: 委譲入力の組み立て (agent-brief-C06.json input_contract.receives)
    # 入出力契約は ## Purpose & Output Contract に置く。本文のどこかで触れているだけでは
    # 契約とみなさない (触れただけの言及と、渡す約束は別である)。
    contract_section = section_text(body_lines, "## Purpose & Output Contract") or ""
    contract_lines = contract_section.splitlines()
    for field in DELEGATION_INPUTS:
        if field not in contract_section:
            v.append(Violation("AC-C03-12", f"委譲入力 {field} を組み立てて渡す宣言が無い"))
    if "scope" not in contract_section:
        v.append(Violation("AC-C03-12", "任意入力 scope の宣言が無い"))
    else:
        scope_lines = [ln for ln in contract_lines if "scope" in ln]
        if not any(("任意" in ln) or ("省略" in ln) for ln in scope_lines):
            v.append(Violation("AC-C03-12", "scope が任意 (省略可) である旨の宣言が無い"))

    # AC-C03-13: 決定論ゲート全 exit0 が委譲の前提 (FAIL 残存なら blocked)
    for gate in GATE_COMPONENTS:
        if gate not in body:
            v.append(Violation("AC-C03-13", f"起動前提となる決定論ゲート {gate} の宣言が無い"))
    if "exit0" not in body:
        v.append(Violation("AC-C03-13", "決定論ゲートが全て exit0 であることを前提とする宣言が無い"))
    if "status=blocked" not in body and "blocked" not in body:
        v.append(Violation("AC-C03-13", "ゲート FAIL 残存時に blocked を返す宣言が無い"))
    elif not re.search(r"(意味レビューへ進まない|進まない|差し戻)", body):
        v.append(Violation("AC-C03-13", "ゲート FAIL 残存時に意味レビューへ進まない旨の宣言が無い"))

    # AC-C03-14: verdict の回収 (出力契約の項目欠落を落とす)
    for key in VERDICT_KEYS:
        if key not in contract_section:
            v.append(Violation("AC-C03-14", f"回収する verdict の項目 {key} が出力契約に無い"))
    for key in FINDING_KEYS:
        if key not in contract_section:
            v.append(Violation("AC-C03-14", f"findings[] の項目 {key} が出力契約に無い"))
    for token in ("PASS", "FAIL"):
        if token not in contract_section:
            v.append(Violation("AC-C03-14", f"verdict の値 {token} が出力契約に無い"))

    # AC-C03-15: 独立 context の保全 (must_not_assume を渡さない)
    for keyword in MUST_NOT_PASS_KEYWORDS:
        if keyword not in body:
            v.append(Violation(
                "AC-C03-15",
                f"委譲先へ持ち込ませない情報 ({keyword}) の宣言が無い (C06 must_not_assume)",
            ))
    if not re.search(r"(渡さない|持ち込ま(せ)?ない)", body):
        v.append(Violation("AC-C03-15", "親 context の情報を委譲先へ渡さない旨の宣言が無い"))

    # AC-C03-16: 反復ループを持たない (component-inventory.json #C03 feedback_contract)
    combinators = [str(x) for x in _as_list(fm.get("combinators"))]
    if combinators:
        v.append(Violation("AC-C03-16", f"assign kind は combinators を持たない (実際: {combinators})"))
    if fm.get("goal_seek") is not None:
        v.append(Violation("AC-C03-16", "assign kind は goal_seek を持たない"))
    fc = fm.get("feedback_contract")
    if not isinstance(fc, dict):
        v.append(Violation("AC-C03-16", "feedback_contract ブロックが無い"))
    else:
        skip = str(fc.get("skip_reason") or "")
        if "反復ループを持たない" not in skip:
            v.append(Violation(
                "AC-C03-16",
                f"feedback_contract.skip_reason が inventory と一致しない (実際: {skip!r})",
            ))
        if fc.get("criteria"):
            v.append(Violation("AC-C03-16", "skip した feedback_contract に criteria を持たせてはならない"))
    if "max_loops" in body:
        v.append(Violation("AC-C03-16", "再レビュー回数の上限 (max_loops) は C01 の責務であり本 skill は持たない"))

    # AC-C03-17: rubric_refs
    rubric_refs = [str(x) for x in _as_list(fm.get("rubric_refs"))]
    for ref in REQUIRED_RUBRIC_REFS:
        if ref not in rubric_refs:
            v.append(Violation("AC-C03-17", f"rubric_refs に {ref} が無い"))

    # AC-C03-18: output_language
    if fm.get("output_language") != "ja":
        v.append(Violation("AC-C03-18", f"output_language は ja (実際: {fm.get('output_language')!r})"))

    # AC-C03-19: 出所の追跡
    if "component-inventory.json#C03" not in str(fm.get("source") or ""):
        v.append(Violation("AC-C03-19", "frontmatter source が component-inventory.json#C03 を指していない"))

    # AC-C03-20: proposer≠approver (生成した本人が採点しない)
    if not re.search(r"(proposer\s*≠\s*approver|生成した本人)", body):
        v.append(Violation("AC-C03-20", "生成した本人が採点しない構造 (proposer≠approver) の宣言が無い"))
    if "独立 context" not in body:
        v.append(Violation("AC-C03-20", "独立 context で判定させる旨の宣言が無い"))

    return v


def section_text(body_lines, heading):
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


def violation_ids(violations):
    return [x.contract_id for x in violations]


def repo_root() -> Path:
    return Path(__file__).resolve().parents[4]


def build_target_dir() -> Path:
    return repo_root() / BUILD_TARGET
