"""handout-extract (C08) の slash-command 宣言的契約チェッカ。

slash-command component は実行そのものを機械検査できないため、検査対象は
`commands/handout-extract.md` の宣言 (frontmatter / 委譲先 skill の宣言と実在 /
引数の既定値と上書き規則 / 委譲先不在時の縮退 / round-trip の粒度の開示 /
入口が自前でパースロジックを持たないこと) である。

契約の出典:
  - plugin-plans/guide-doc-generator/briefs/command-brief-C08.json (正本)
  - plugin-plans/guide-doc-generator/component-inventory.json #C08
  - plugin-plans/guide-doc-generator/briefs/skill-brief-C02.json (委譲先)

標準ライブラリのみを使う (PyYAML は使わない)。
"""

from __future__ import annotations

import json
import re
from collections import namedtuple
from pathlib import Path

import resolution_spec as rspec

Violation = namedtuple("Violation", ["contract_id", "message"])


# --------------------------------------------------------------------------
# パス解決 (定数の一部を正本ファイルから読むため、定数より前に置く)
# --------------------------------------------------------------------------

def repo_root() -> Path:
    return Path(__file__).resolve().parents[4]


def plan_root() -> Path:
    return repo_root() / "plugin-plans" / "guide-doc-generator"


def command_brief() -> dict:
    """C08 の brief (argument-hint の正本) を読む。

    正本の決定は plugin-plans/guide-doc-generator/RESOLUTION-P05-x-15-argument-hint.md。
    """
    path = plan_root() / "briefs" / "command-brief-C08.json"
    return json.loads(path.read_text(encoding="utf-8"))


# --------------------------------------------------------------------------
# 契約の定数 (すべて brief / inventory 由来)
# --------------------------------------------------------------------------

COMMAND_NAME = "handout-extract"
BUILD_TARGET = "plugins/guide-doc-generator/commands/handout-extract.md"

# component-inventory.json #C08 allowed-tools (過不足を許さない)
REQUIRED_TOOLS = ("Read", "Write", "Bash", "Skill")
FORBIDDEN_TOOLS = ("Edit", "MultiEdit", "NotebookEdit", "Task", "WebFetch", "Grep", "Glob")

# argument-hint の正本は briefs/command-brief-C08.json#argument_hint
# (RESOLUTION-P05-x-15-argument-hint.md §1)。ここでは値を再掲せず正本から読み、
# 成果物 frontmatter と component-inventory.json の双方をこの値へ完全一致で突き合わせる。
# token 集合 (C07/C09 の書き方) には寄せない — C08 は完全文字列一致が契約であり、
# token 集合にすると語順・空白・角括弧の崩れを見逃して検査が弱くなる。
ARGUMENT_HINT = command_brief()["argument_hint"]

# 委譲先 (brief delegates_to / delegation_form)
DELEGATE_SKILL = "run-handout-extract"
DELEGATION_FORM = 'Skill(run-handout-extract, args="$ARGUMENTS")'

# skill-brief-C02.json deterministic_checks — Bash で回る委譲チェーン
DELEGATED_SCRIPTS = (
    "extract-handout-config.py",       # C20
    "validate-handout-config.py",      # C12
    "render-handout.py",               # C11
    "verify-handout-selfcontained.py",  # C16
)

# skill-brief-C02.json responsibilities (behavior 2 が委譲すると書いている 3 責務)
DELEGATED_RESPONSIBILITIES = ("R1-scan", "R2-complete", "R3-roundtrip")

# 引数解決の機械可読ブロックの id (本テスト群が定めた形式 — README の gap 参照)
ARGS_BLOCK_ID = "CR-EXTRACT-ARGS"

# behavior 4「HTML から一意に定まる構造」
RESTORABLE_TERMS = (
    "セクションの並び", "部品種別", "見出し", "埋め込みアセット",
    "アイコン参照", "日付表記", "アクセント",
)
# behavior 4「HTML から一意に定まらない意味情報」
UNRESTORABLE_TERMS = (
    "lead-line", "判断軸", "goal", "用語言い換え", "前提知識", "本質的課題",
)

# 入口が自前で HTML を解釈しないこと (boundary) — 本文に現れてはならない語
PARSER_TOKENS = (
    "BeautifulSoup", "html.parser", "HTMLParser", "lxml", "html5lib",
    "re.findall", "re.search", "querySelector", "XPath", "xpath",
)

NEGATION = re.compile(r"(ない|なく|せず|ず(に|、|。)|禁止|不可|しません|持たない|行わない|兼ねない)")


# --------------------------------------------------------------------------
# 最小 YAML 部分集合パーサ (handout-verify のチェッカと同じ方針)
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
# 引数解決ブロックの取り出し
# --------------------------------------------------------------------------

_FENCE = re.compile(r"```json\s*\n(.*?)\n```", re.DOTALL)


def extract_args_block(body: str):
    """本文中の fenced json から id == CR-EXTRACT-ARGS のブロックを返す。

    戻り値 (block_or_None, parse_errors)。brief は引数規則を散文で持つだけで
    機械可読形式を規定していないため、機械検査可能な単一形式として
    「CR-EXTRACT-ARGS を id に持つ fenced json ブロック」を本テスト群が要求する。
    """
    errors = []
    for raw in _FENCE.findall(body):
        try:
            obj = json.loads(raw)
        except json.JSONDecodeError as exc:
            errors.append(f"fenced json が JSON として読めない: {exc}")
            continue
        if isinstance(obj, dict) and obj.get("id") == ARGS_BLOCK_ID:
            return obj, errors
    return None, errors


def strip_fences(body: str) -> str:
    """散文検査から fenced code block を除く (宣言ブロックの語で散文検査を通さない)。"""
    return re.sub(r"```.*?```", "\n", body, flags=re.DOTALL)


# --------------------------------------------------------------------------
# 検査本体
# --------------------------------------------------------------------------


def _as_list(value):
    if value is None:
        return []
    if isinstance(value, list):
        return value
    return [value]


def _lines_with(prose, *needles):
    """すべての needle を同一行に含む行を返す。"""
    return [ln for ln in prose.splitlines() if all(n in ln for n in needles)]


def _sentences(prose):
    """散文を文単位へ割る。

    否定の有無は文の単位で見る。同一行の別の文にある否定 (例: 「同定できない場合は
    …。空の構成データでも成功として返す。」) を、後段の文の否定と読み違えないため。
    """
    out = []
    for line in prose.splitlines():
        for part in re.split(r"(?<=。)", line):
            if part.strip():
                out.append(part.strip())
    return out


def _units_with(prose, *needles):
    """すべての needle を同一文に含む文を返す。"""
    return [s for s in _sentences(prose) if all(n in s for n in needles)]


def _has_negated(prose, *needles):
    """needle を含む文のうち、否定表現を伴うものがあるか。"""
    return any(NEGATION.search(s) for s in _units_with(prose, *needles))


def command_path(plugin_root) -> Path:
    return Path(plugin_root) / "commands" / f"{COMMAND_NAME}.md"


def check_command(plugin_root) -> list:
    """commands/handout-extract.md 一式を検査し Violation の一覧を返す。"""
    plugin_root = Path(plugin_root)
    md = command_path(plugin_root)
    v = []

    if not md.is_file():
        v.append(Violation("AC-C08-1", f"command 定義が存在しない: {md}"))
        return v

    text = md.read_text(encoding="utf-8")
    fm, body = split_frontmatter(text)
    if fm is None:
        v.append(Violation("AC-C08-1", "YAML frontmatter が無い"))
        return v

    prose = strip_fences(body)

    _check_frontmatter(fm, v)
    _check_delegation(plugin_root, body, prose, v)
    _check_roundtrip_disclosure(prose, v)
    _check_boundary(prose, v)
    _check_arguments(body, prose, v)
    _check_degradation(prose, v)
    _check_failure_modes(prose, v)
    _check_no_own_parsing(fm, body, prose, v)

    return v


# --- AC-C08-1 -------------------------------------------------------------

def _check_frontmatter(fm, v):
    if fm.get("name") != COMMAND_NAME:
        v.append(Violation("AC-C08-1", f"frontmatter name は {COMMAND_NAME!r} (実際: {fm.get('name')!r})"))

    desc = fm.get("description")
    if not isinstance(desc, str) or not desc.strip():
        v.append(Violation("AC-C08-1", "description が空"))
    else:
        for word in ("逆抽出", "round-trip"):
            if word not in desc:
                v.append(Violation("AC-C08-1", f"description に {word!r} が無い (inventory #C08 description と揃える)"))

    hint = str(fm.get("argument-hint") or "").strip()
    if hint != ARGUMENT_HINT:
        v.append(Violation("AC-C08-1", f"argument-hint は {ARGUMENT_HINT!r} (実際: {hint!r})"))

    tools = [str(x) for x in _as_list(fm.get("allowed-tools"))]
    for tool in REQUIRED_TOOLS:
        if tool not in tools:
            v.append(Violation("AC-C08-1", f"allowed-tools に {tool} が無い (inventory #C08 と一致させる)"))
    for tool in tools:
        if tool not in REQUIRED_TOOLS:
            v.append(Violation("AC-C08-1", f"allowed-tools に inventory 外の {tool} がある (4 件ちょうど)"))
    for tool in FORBIDDEN_TOOLS:
        if tool in tools:
            v.append(Violation("AC-C08-1", f"allowed-tools に {tool} を持ってはならない"))

    if fm.get("disable-model-invocation") is not False:
        v.append(Violation(
            "AC-C08-1",
            f"disable-model-invocation は false (実際: {fm.get('disable-model-invocation')!r})",
        ))


# --- AC-C08-2 -------------------------------------------------------------

def _check_delegation(plugin_root, body, prose, v):
    if DELEGATION_FORM not in body:
        v.append(Violation("AC-C08-2", f"delegation_form {DELEGATION_FORM!r} の宣言が無い"))

    skill_dir = Path(plugin_root) / "skills" / DELEGATE_SKILL
    if not (skill_dir / "SKILL.md").is_file():
        v.append(Violation("AC-C08-2", f"委譲先 skill が実在しない: {skill_dir / 'SKILL.md'}"))

    for script in DELEGATED_SCRIPTS:
        if script not in body:
            v.append(Violation("AC-C08-2", f"委譲チェーンの script {script} が本文で宣言されていない"))
        target = Path(plugin_root) / "scripts" / script
        if not target.is_file():
            v.append(Violation("AC-C08-2", f"委譲チェーンの script の実体が存在しない: {target}"))

    for rid in DELEGATED_RESPONSIBILITIES:
        if rid not in body:
            v.append(Violation("AC-C08-2", f"委譲する責務 {rid} の宣言が無い (brief behavior 2)"))

    if not _lines_with(prose, "$ARGUMENTS"):
        v.append(Violation("AC-C08-2", "$ARGUMENTS をそのまま委譲先へ渡す宣言が無い"))


# --- AC-C08-3 -------------------------------------------------------------

def _check_roundtrip_disclosure(prose, v):
    for word in ("正規化", "構成データ等価", "バイト一致"):
        if word not in prose:
            v.append(Violation("AC-C08-3", f"round-trip の粒度の説明に {word!r} が無い"))

    if not _has_negated(prose, "バイト一致"):
        v.append(Violation(
            "AC-C08-3",
            "HTML のバイト一致を判定しない旨の宣言が無い (バイト一致を含む行に否定が無い)",
        ))
    if not _lines_with(prose, "バイト一致", "再生成"):
        v.append(Violation(
            "AC-C08-3",
            "バイト一致が課されるのは同一構成データからの再生成のみ、という宣言が無い",
        ))
    if not (_lines_with(prose, "起動時") or _lines_with(prose, "先に宣言")):
        v.append(Violation("AC-C08-3", "round-trip の粒度の限界を起動時に先に宣言する旨が無い"))

    missing_ok = [w for w in RESTORABLE_TERMS if w not in prose]
    if missing_ok:
        v.append(Violation("AC-C08-3", f"復元される範囲の列挙に不足がある: {missing_ok}"))
    missing_ng = [w for w in UNRESTORABLE_TERMS if w not in prose]
    if missing_ng:
        v.append(Violation("AC-C08-3", f"復元されない意味情報の具体名に不足がある: {missing_ng}"))
    if "復元" not in prose or not _has_negated(prose, "復元"):
        v.append(Violation("AC-C08-3", "復元されない範囲を区別して伝える宣言が無い"))


# --- AC-C08-4 -------------------------------------------------------------

def _check_boundary(prose, v):
    if "/handout-build" not in prose:
        v.append(Violation("AC-C08-4", "次の一手として /handout-build を案内する宣言が無い"))
    elif not _lines_with(prose, "/handout-build", "--config"):
        v.append(Violation("AC-C08-4", "/handout-build --config <出力パス> の形での案内になっていない"))

    if not _has_negated(prose, "生成"):
        v.append(Violation("AC-C08-4", "資料の生成は行わない (C07 の責務) 旨の宣言が無い"))
    if "C07" not in prose:
        v.append(Violation("AC-C08-4", "生成の責務が C07 にある旨の明示が無い"))

    verify_lines = _units_with(prose, "C09") + _units_with(prose, "/handout-verify")
    if not verify_lines:
        v.append(Violation("AC-C08-4", "検証 (C09) を兼ねない旨の宣言が無い"))
    elif not any(NEGATION.search(ln) for ln in verify_lines):
        v.append(Violation("AC-C08-4", "検証 (C09) を兼ねないことが否定形で書かれていない"))

    if not _has_negated(prose, "改善提案"):
        v.append(Violation("AC-C08-4", "資料内容の改善提案をしない旨の宣言が無い (C02 boundary)"))
    if not _has_negated(prose, "書き換え"):
        v.append(Violation("AC-C08-4", "資料内容の書き換えをしない旨の宣言が無い (C02 boundary)"))
    if not (_lines_with(prose, "構成データ", "止ま") or _lines_with(prose, "構成データ", "止め")):
        v.append(Violation("AC-C08-4", "構成データを出すところで止まる旨の宣言が無い"))


# --- AC-C08-ARGS ----------------------------------------------------------

def _check_arguments(body, prose, v):
    # 散文側 (利用者が読む形)
    if "handout-config.json" not in prose:
        v.append(Violation("AC-C08-ARGS", "--out の既定値 handout-config.json の宣言が無い"))
    if not _lines_with(prose, "--out", "既定") and not _lines_with(prose, "handout-config.json", "同じディレクトリ"):
        v.append(Violation("AC-C08-ARGS", "--out 既定が入力 HTML と同じディレクトリである宣言が無い"))
    if not _lines_with(prose, "上書き", "確認"):
        v.append(Violation("AC-C08-ARGS", "--out の既存ファイルに対する上書き可否の確認の宣言が無い"))
    if not (_lines_with(prose, "レポート", "同じディレクトリ") or _lines_with(prose, "レポート", "併置")):
        v.append(Violation("AC-C08-ARGS", "逆抽出レポートを --out と同じディレクトリへ併置する宣言が無い"))
    if not _lines_with(prose, "html-path", "必須"):
        v.append(Violation("AC-C08-ARGS", "html-path が必須 positional である宣言が無い"))

    # 機械可読側
    block, errors = extract_args_block(body)
    for msg in errors:
        v.append(Violation("AC-C08-ARGS", msg))
    if block is None:
        v.append(Violation(
            "AC-C08-ARGS",
            f'id="{ARGS_BLOCK_ID}" を持つ機械可読な引数解決ブロック (fenced json) が無い',
        ))
        return

    reasons = rspec.declared_stop_reasons(block)
    if reasons != set(rspec.STOP_REASONS):
        v.append(Violation(
            "AC-C08-ARGS",
            f"停止理由の語彙は {sorted(rspec.STOP_REASONS)} と一致 (実際: {sorted(str(x) for x in reasons)})",
        ))

    try:
        mismatches = rspec.diff_against_oracle(block)
    except rspec.SpecError as exc:
        v.append(Violation("AC-C08-ARGS", f"引数解決ブロックが解釈できない: {exc}"))
        return
    if mismatches:
        head = mismatches[:5]
        v.append(Violation(
            "AC-C08-ARGS",
            f"引数解決が正解表と {len(mismatches)} 件食い違う。先頭 5 件: "
            + "; ".join(f"{c.name} 期待={w} 実際={g}" for c, w, g in head),
        ))


# --- AC-C08-DEGRADE -------------------------------------------------------

def _check_degradation(prose, v):
    """委譲先 (skill / script) が解決できないときの縮退。

    brief は failure_modes に委譲先不在の項を持たないが、task-spec
    acceptance_criterion が「委譲先不在時の縮退」を要求するため、
    failure_modes 3 の思想 (空の構成データを成功として返さない) を延長して固定する。
    """
    absent = [
        s for s in _sentences(prose)
        if ("不在" in s or "見つから" in s or "解決できな" in s)
    ]
    if not absent:
        v.append(Violation("AC-C08-DEGRADE", "委譲先が不在のときの挙動が宣言されていない"))
        return

    groups = {
        f"委譲先 skill {DELEGATE_SKILL}": [
            s for s in absent if DELEGATE_SKILL in s or "委譲先" in s
        ],
        "委譲チェーンの script": [
            s for s in absent if "script" in s or ".py" in s
        ],
    }
    for label, sentences in groups.items():
        if not sentences:
            v.append(Violation("AC-C08-DEGRADE", f"{label} が解決できない場合の宣言が無い"))
            continue
        if not any(("停止" in s) or ("成功" in s and NEGATION.search(s)) for s in sentences):
            v.append(Violation(
                "AC-C08-DEGRADE",
                f"{label} の不在を成功として返さず停止する旨の宣言が無い (不在を pass に読み替えない)",
            ))
        if not any("パス" in s for s in sentences):
            v.append(Violation(
                "AC-C08-DEGRADE",
                f"{label} の不在時に解決を試みたパスを提示する宣言が無い",
            ))


# --- AC-C08-FM-* ----------------------------------------------------------

def _check_failure_modes(prose, v):
    # FM-1: html-path 未指定 / 不在 / ディレクトリ
    entry = [ln for ln in _lines_with(prose, "html-path") if re.search(r"(停止|起動せず|起動しない)", ln)]
    if not entry:
        v.append(Violation("AC-C08-FM-1", "html-path 不在時に委譲先を起動せず停止する宣言が無い"))
    if not _lines_with(prose, "ディレクトリ", "停止") and not _lines_with(prose, "ディレクトリ", "展開せず"):
        v.append(Violation("AC-C08-FM-1", "ディレクトリを渡された場合に展開せず停止する宣言が無い"))
    if "単一 HTML" not in prose:
        v.append(Violation("AC-C08-FM-1", "期待する形 (単一 HTML ファイル) を示す宣言が無い"))
    if not _lines_with(prose, "解決したパス"):
        v.append(Violation("AC-C08-FM-1", "停止時に解決したパスを示す宣言が無い"))

    # FM-2: --out 既存
    if not _has_negated(prose, "黙って上書き"):
        v.append(Violation("AC-C08-FM-2", "既存ファイルを黙って上書きしない旨の宣言が無い"))

    # FM-3: 部品構造を同定できない
    if not (_lines_with(prose, "同定") and ("同定不能" in prose or _has_negated(prose, "同定"))):
        v.append(Violation("AC-C08-FM-3", "部品構造を同定できない場合の宣言が無い"))
    if not _lines_with(prose, "空の構成データ"):
        v.append(Violation("AC-C08-FM-3", "空の構成データを成功として返さない旨の宣言が無い"))
    elif not _has_negated(prose, "空の構成データ"):
        v.append(Violation("AC-C08-FM-3", "空の構成データを『成功』として返さないことが否定形で書かれていない"))
    if "部分成功" not in prose:
        v.append(Violation("AC-C08-FM-3", "部分成功を部分成功として返す宣言が無い"))

    # FM-4: 復元不能な意味情報の 3 点セット
    for word in ("キーパス", "補完方針"):
        if word not in prose:
            v.append(Violation("AC-C08-FM-4", f"逆抽出レポートの 3 点セットに {word!r} が無い"))
    for policy in ("推測値の充填", "空のまま残置", "利用者への確認"):
        if policy not in prose:
            v.append(Violation("AC-C08-FM-4", f"補完方針の選択肢 {policy!r} が明示されていない"))
    if not (_lines_with(prose, "推測", "区別") or _lines_with(prose, "推測", "印")):
        v.append(Violation("AC-C08-FM-4", "推測で埋めた値と HTML から読み取った値を区別する宣言が無い"))
    if not _has_negated(prose, "黙って"):
        v.append(Violation("AC-C08-FM-4", "復元不能箇所を黙って欠落させない旨の宣言が無い"))

    # FM-5: round-trip 差分
    if not _lines_with(prose, "差分", "FAIL"):
        v.append(Violation("AC-C08-FM-5", "round-trip 差分ありを FAIL とする宣言が無い"))
    if not _has_negated(prose, "等価扱い") and not _has_negated(prose, "等価と読める"):
        v.append(Violation("AC-C08-FM-5", "差分ありを等価扱いしない旨の宣言が無い"))
    if not _lines_with(prose, "差分", "両側"):
        v.append(Violation("AC-C08-FM-5", "差分のキーパスと両側の値を提示する宣言が無い"))

    # FM-6: validate FAIL
    val = _lines_with(prose, "validate-handout-config.py")
    if not val:
        v.append(Violation("AC-C08-FM-6", "validate-handout-config.py を通らない場合の宣言が無い"))
    if not _lines_with(prose, "そのままでは生成に使えない"):
        v.append(Violation("AC-C08-FM-6", "FAIL でも構成データは書き出したうえで生成に使えない旨を示す宣言が無い"))
    if not _has_negated(prose, "捏造"):
        v.append(Violation("AC-C08-FM-6", "値を捏造して validate を通さない旨の宣言が無い"))


# --- AC-C08-PARSE ---------------------------------------------------------

def _check_no_own_parsing(fm, body, prose, v):
    """入口が自前でパースロジックを持たないこと (R14 / brief boundary)。"""
    for token in PARSER_TOKENS:
        if token in body:
            v.append(Violation(
                "AC-C08-PARSE",
                f"command 定義が自前の HTML 解析手段 {token!r} を持ってはならない (解釈は C02 へ委譲)",
            ))

    interp = _lines_with(prose, "HTML の解釈")
    if not interp:
        v.append(Violation("AC-C08-PARSE", "command が HTML の解釈に関与しない旨の宣言が無い"))
    elif not any(NEGATION.search(ln) for ln in interp):
        v.append(Violation("AC-C08-PARSE", "HTML の解釈に関与しないことが否定形で書かれていない"))

    if not _has_negated(prose, "補完"):
        v.append(Violation("AC-C08-PARSE", "command が構成データの補完に関与しない旨の宣言が無い"))

    # Read の用途は入力 HTML の存在確認に限る (allowed_tools_rationale)
    if not _lines_with(prose, "Read", "存在確認"):
        v.append(Violation("AC-C08-PARSE", "Read の用途が入力 HTML の存在確認に限られる宣言が無い"))

    # 走査・部品同定は skill の責務 (boundary)
    if not (_lines_with(prose, "走査", DELEGATE_SKILL) or _lines_with(prose, "走査", "委譲")
            or _lines_with(prose, "走査", "skill")):
        v.append(Violation("AC-C08-PARSE", "HTML の走査と部品同定を skill へ渡す宣言が無い"))


# --------------------------------------------------------------------------

def violation_ids(violations):
    return [x.contract_id for x in violations]


def plugin_root() -> Path:
    return repo_root() / "plugins" / "guide-doc-generator"


def build_target() -> Path:
    return repo_root() / BUILD_TARGET
