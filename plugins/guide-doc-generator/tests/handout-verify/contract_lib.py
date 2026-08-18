"""handout-verify (C09) の slash-command 宣言的契約チェッカ。

slash-command component は実行そのものを機械検査できないため、検査対象は
`commands/handout-verify.md` の宣言 (frontmatter / 参照 script の実在と argv /
集約規則 CR-GATE-AGG の宣言 / 引数の既定値と上書き規則 / 縮退時の挙動) である。

契約の出典:
  - plugin-plans/guide-doc-generator/briefs/command-brief-C09.json (正本)
  - plugin-plans/guide-doc-generator/component-inventory.json #C09
  - plugin-plans/guide-doc-generator/briefs/RESOLUTION-P03.md Y-07

標準ライブラリのみを使う (PyYAML は使わない)。
"""

from __future__ import annotations

import json
import re
from collections import namedtuple
from pathlib import Path

import aggregation_spec as spec

Violation = namedtuple("Violation", ["contract_id", "message"])


# --------------------------------------------------------------------------
# 契約の定数 (すべて brief / inventory / RESOLUTION 由来)
# --------------------------------------------------------------------------

COMMAND_NAME = "handout-verify"
BUILD_TARGET = "plugins/guide-doc-generator/commands/handout-verify.md"

# component-inventory.json #C09 allowed-tools
REQUIRED_TOOLS = ("Read", "Bash")
# allowed_tools_rationale: Skill と Write を持たないのは意図的
FORBIDDEN_TOOLS = ("Skill", "Write", "Edit", "MultiEdit", "NotebookEdit")

# inventory の argument-hint が持つ最小語 + brief argument_hint の全フラグ
ARGUMENT_HINT_TOKENS = ("<html-path>", "--config", "--out-dir", "--only", "--json-report")

# brief arguments[] の name と default の要点 (既定値と上書き規則の宣言検査に使う)
ARGUMENT_DEFAULTS = {
    "html-path": "なし",
    "--config": "not-run",           # 未指定時は language / narrative が not-run
    "--out-dir": "親ディレクトリ",     # 未指定時は html-path の親
    "--only": "4",                    # 未指定時は 4 ゲート全実行
    "--json-report": "stdout",        # 未指定時は stdout/stderr のみ
}

# canonical_aggregation / behavior に現れる必須語
CANONICAL_ID = "CR-GATE-AGG"
CONSUMER_COMMAND = "run-handout-build"

# 集約サマリに必ず含める項目 (behavior 7)
SUMMARY_KEYS = ("verdict", "gates")

# 「未実行を通ったことにしない」ことの宣言に使う語
NOT_RUN_TO_PASS_PATTERNS = (
    re.compile(r"not-run\s*(を|は)\s*pass"),
    re.compile(r"未実行\s*(を|は)\s*(pass|合格|成功)"),
    re.compile(r"(skip|スキップ)\s*(を|は)\s*pass"),
)


# --------------------------------------------------------------------------
# 最小 YAML 部分集合パーサ (run-handout-build のチェッカと同じ方針)
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
# 集約規則ブロックの取り出し
# --------------------------------------------------------------------------

_FENCE = re.compile(r"```json\s*\n(.*?)\n```", re.DOTALL)


def extract_aggregation_block(body: str):
    """本文中の fenced json から id == CR-GATE-AGG のブロックを返す。

    戻り値 (block_or_None, parse_errors)。brief は集約規則を散文で持つだけで
    機械可読形式を規定していないため、機械検査可能な単一形式として
    「CR-GATE-AGG を id に持つ fenced json ブロック」を本テスト群が要求する。
    """
    errors = []
    for raw in _FENCE.findall(body):
        try:
            obj = json.loads(raw)
        except json.JSONDecodeError as exc:
            errors.append(f"fenced json が JSON として読めない: {exc}")
            continue
        if isinstance(obj, dict) and obj.get("id") == CANONICAL_ID:
            return obj, errors
    return None, errors


# --------------------------------------------------------------------------
# 検査本体
# --------------------------------------------------------------------------


def _as_list(value):
    if value is None:
        return []
    if isinstance(value, list):
        return value
    return [value]


def command_path(plugin_root) -> Path:
    return Path(plugin_root) / "commands" / f"{COMMAND_NAME}.md"


def check_command(plugin_root) -> list:
    """commands/handout-verify.md 一式を検査し Violation の一覧を返す。"""
    plugin_root = Path(plugin_root)
    md = command_path(plugin_root)
    v = []

    if not md.is_file():
        v.append(Violation("AC-C09-1", f"command 定義が存在しない: {md}"))
        return v

    text = md.read_text(encoding="utf-8")
    fm, body = split_frontmatter(text)
    if fm is None:
        v.append(Violation("AC-C09-1", "YAML frontmatter が無い"))
        return v

    body_lines = body.splitlines()

    _check_frontmatter(fm, v)
    _check_scripts(plugin_root, body, v)
    _check_aggregation(body, v)
    _check_states_and_reasons(body, v)
    _check_degradation(body, v)
    _check_arguments(body, v)
    _check_boundary(fm, body, body_lines, v)
    _check_reporting(body, v)
    _check_consumer_parity(body, v)

    return v


# --- AC-C09-1 -------------------------------------------------------------

def _check_frontmatter(fm, v):
    if fm.get("name") != COMMAND_NAME:
        v.append(Violation("AC-C09-1", f"frontmatter name は {COMMAND_NAME!r} (実際: {fm.get('name')!r})"))

    desc = fm.get("description")
    if not isinstance(desc, str) or not desc.strip():
        v.append(Violation("AC-C09-1", "description が空"))
    else:
        # inventory #C09 description は 4 面と 4 状態を名指しする (P03 Y-07)
        for face in spec.GATE_FACES.values():
            if face not in desc:
                v.append(Violation("AC-C09-1", f"description が集約対象 {face} を名指ししていない (P03 Y-07 で 4 面に確定)"))
        for state in spec.GATE_STATES:
            if state not in desc:
                v.append(Violation("AC-C09-1", f"description に 4 状態の {state!r} が無い"))

    hint = str(fm.get("argument-hint") or "")
    if not hint.strip():
        v.append(Violation("AC-C09-1", "argument-hint が無い"))
    else:
        if not hint.strip().startswith("<html-path>"):
            v.append(Violation("AC-C09-1", f"argument-hint は positional の <html-path> で始まる (実際: {hint!r})"))
        for token in ARGUMENT_HINT_TOKENS:
            if token not in hint:
                v.append(Violation("AC-C09-1", f"argument-hint に {token} が無い (brief arguments[] の 5 件を落とさない)"))

    tools = [str(x) for x in _as_list(fm.get("allowed-tools"))]
    for tool in REQUIRED_TOOLS:
        if tool not in tools:
            v.append(Violation("AC-C09-1", f"allowed-tools に {tool} が無い"))
    for tool in FORBIDDEN_TOOLS:
        if tool in tools:
            v.append(Violation("AC-C09-1", f"allowed-tools に {tool} を持ってはならない (read-only 集約入口)"))

    if fm.get("disable-model-invocation") is not False:
        v.append(Violation(
            "AC-C09-1",
            f"disable-model-invocation は false (実際: {fm.get('disable-model-invocation')!r})",
        ))


# --- AC-C09-2 -------------------------------------------------------------

def _check_scripts(plugin_root, body, v):
    for gate_id, script in spec.GATE_SCRIPTS.items():
        if script not in body:
            v.append(Violation("AC-C09-2", f"ゲート {gate_id} の script {script} が本文で参照されていない"))
            continue
        target = Path(plugin_root) / "scripts" / script
        if not target.is_file():
            v.append(Violation("AC-C09-2", f"参照 script の実体が存在しない: {target}"))

    # delegation_form: ${HB_ROOT:-$CLAUDE_PLUGIN_ROOT}/scripts/<script>.py
    if not re.search(r"HB_ROOT[^\n]{0,60}scripts/", body) or "CLAUDE_PLUGIN_ROOT" not in body:
        v.append(Violation(
            "AC-C09-2",
            "script の解決パスが ${HB_ROOT:-$CLAUDE_PLUGIN_ROOT}/scripts/ 形で宣言されていない",
        ))

    # argv の形
    for gate_id, argv in spec.GATE_ARGV.items():
        for flag in argv:
            if flag not in body:
                v.append(Violation("AC-C09-2", f"ゲート {gate_id} へ渡す argv {flag} の宣言が無い"))
    if "--json-report" not in body:
        v.append(Violation("AC-C09-2", "各 script の --json-report を使う宣言が無い"))

    # gates[].requires: config が要るのは language / narrative だけ
    for gate_id in spec.GATES_REQUIRING_CONFIG:
        if gate_id not in body:
            v.append(Violation("AC-C09-2", f"config を要求するゲート {gate_id} の宣言が無い"))


# --- AC-C09-AGG-1 / AGG-2 -------------------------------------------------

def _check_aggregation(body, v):
    if CANONICAL_ID not in body:
        v.append(Violation("AC-C09-AGG-1", f"集約規則の正本 id {CANONICAL_ID} の宣言が無い"))

    block, errors = extract_aggregation_block(body)
    for msg in errors:
        v.append(Violation("AC-C09-AGG-2", msg))
    if block is None:
        v.append(Violation(
            "AC-C09-AGG-2",
            f'id="{CANONICAL_ID}" を持つ機械可読な集約規則ブロック (fenced json) が無い',
        ))
        return

    faces = block.get("gate_faces")
    if isinstance(faces, dict):
        if faces != spec.GATE_FACES:
            v.append(Violation("AC-C09-AGG-2", f"gate_faces は {spec.GATE_FACES} と一致 (実際: {faces})"))
    elif isinstance(faces, list):
        if sorted(str(x) for x in faces) != sorted(spec.GATE_IDS):
            v.append(Violation("AC-C09-AGG-2", f"gate_faces は 4 面 {sorted(spec.GATE_IDS)} (実際: {faces})"))
    else:
        v.append(Violation("AC-C09-AGG-2", "gate_faces の宣言が無い"))

    states = block.get("states")
    if sorted(str(x) for x in _as_list(states)) != sorted(spec.GATE_STATES):
        v.append(Violation("AC-C09-AGG-2", f"states は 4 状態 {sorted(spec.GATE_STATES)} (実際: {states})"))

    reasons = block.get("not_run_reasons")
    if sorted(str(x) for x in _as_list(reasons)) != sorted(spec.NOT_RUN_REASONS):
        v.append(Violation(
            "AC-C09-AGG-2",
            f"not_run_reasons は {sorted(spec.NOT_RUN_REASONS)} (実際: {reasons})",
        ))

    table = block.get("verdict_table")
    if table is None:
        v.append(Violation("AC-C09-AGG-2", "verdict_table の宣言が無い"))
        return

    mismatches = []
    for states_combo, only_used in spec.all_combinations():
        want = spec.aggregate(states_combo, only_used)
        try:
            got = spec.resolve(table, states_combo, only_used)
        except spec.TableError as exc:
            v.append(Violation("AC-C09-AGG-2", f"verdict_table が壊れている: {exc}"))
            return
        if got != want:
            mismatches.append((dict(states_combo), only_used, want, got))
    if mismatches:
        head = mismatches[:5]
        v.append(Violation(
            "AC-C09-AGG-2",
            f"verdict_table が正解表と {len(mismatches)} 件食い違う。先頭 5 件: "
            + "; ".join(
                f"{s} only={o} 期待={w} 実際={g}" for s, o, w, g in head
            ),
        ))


# --- AC-C09-AGG-3 / AGG-4 -------------------------------------------------

def _check_states_and_reasons(body, v):
    for state in spec.GATE_STATES:
        if state not in body:
            v.append(Violation("AC-C09-AGG-3", f"本文に 4 状態の {state!r} の説明が無い"))
    for verdict in spec.VERDICTS:
        if verdict not in body:
            v.append(Violation("AC-C09-AGG-3", f"本文に全体 verdict の {verdict!r} の説明が無い"))
    for reason in spec.NOT_RUN_REASONS:
        if reason not in body:
            v.append(Violation("AC-C09-AGG-3", f"not-run の理由 {reason!r} の宣言が無い"))
    for code, state in spec.EXIT_CODE_TO_STATE.items():
        if not re.search(rf"exit\s*(code\s*)?{code}\D", body):
            v.append(Violation("AC-C09-AGG-3", f"exit {code} -> {state} の写像宣言が無い"))

    for pattern in NOT_RUN_TO_PASS_PATTERNS:
        hit = pattern.search(body)
        if hit and "畳" not in body[max(0, hit.start() - 40):hit.end() + 40] \
                and "しない" not in body[hit.start():hit.end() + 30]:
            v.append(Violation("AC-C09-AGG-4", f"not-run を pass 側へ読み替える記述がある: {hit.group(0)!r}"))
    if "畳" not in body and "読み替え" not in body:
        v.append(Violation("AC-C09-AGG-4", "not-run を pass へ畳む経路を存在させない旨の宣言が無い"))


# --- AC-C09-3 / 4 / 5 / 7 / 9 ---------------------------------------------

def _lines_with(body, *needles):
    """すべての needle を同一行に含む行を返す。"""
    return [ln for ln in body.splitlines() if all(n in ln for n in needles)]


def _check_degradation(body, v):
    # AC-C09-3: --config 未指定 -> language / narrative が not-run (config-missing) / 全体 incomplete
    if "config-missing" not in body:
        v.append(Violation("AC-C09-3", "--config 未指定時の not-run 理由 config-missing の宣言が無い"))
    if not _lines_with(body, "config-missing", "not-run"):
        v.append(Violation("AC-C09-3", "config-missing が not-run の理由であることの宣言が無い"))
    if not _lines_with(body, "config-missing", "incomplete"):
        v.append(Violation("AC-C09-3", "--config 未指定時の全体 verdict が incomplete である宣言が無い"))

    # AC-C09-4: fail-fast にしない
    if "fail-fast" not in body and "止めず" not in body:
        v.append(Violation("AC-C09-4", "1 ゲートが落ちても後続を止めない (fail-fast にしない) 宣言が無い"))
    if not _lines_with(body, "止めず", "全ゲート"):
        v.append(Violation("AC-C09-4", "複数 fail 時に全ゲートを走らせてまとめて報告する宣言が無い"))

    # AC-C09-5: --only は成功時でも partial
    if "excluded-by-only" not in body:
        v.append(Violation("AC-C09-5", "--only 除外時の not-run 理由 excluded-by-only の宣言が無い"))
    if not _lines_with(body, "excluded-by-only", "not-run"):
        v.append(Violation("AC-C09-5", "excluded-by-only が not-run の理由であることの宣言が無い"))
    if not _lines_with(body, "--only", "partial") and not _lines_with(body, "excluded-by-only", "partial"):
        v.append(Violation("AC-C09-5", "--only 実行の全体 verdict が成功時でも partial である宣言が無い"))
    if not re.search(r"未知[\s\S]{0,120}gate_id|gate_id[\s\S]{0,120}未知", body):
        v.append(Violation("AC-C09-5", "--only に未知の gate_id を渡した場合に停止する宣言が無い"))

    # AC-C09-7: 入口停止 (0 件実行を pass にしない)
    if "ディレクトリ" not in body:
        v.append(Violation("AC-C09-7", "html-path にディレクトリを渡された場合に停止する宣言が無い"))
    entry = [
        ln for ln in _lines_with(body, "html-path")
        if re.search(r"(停止|実行せず|実行しない)", ln)
    ]
    if not entry:
        v.append(Violation("AC-C09-7", "html-path 不在 / ディレクトリ指定時に停止する宣言が無い"))
    elif not any(re.search(r"(1 ゲートも|一つも|ひとつも|0 件)", ln) for ln in entry):
        v.append(Violation("AC-C09-7", "html-path 不在時に 1 ゲートも実行しないことの宣言が無い"))

    # AC-C09-9: script 不在は not-run (script-absent) であって pass ではない
    if "script-absent" not in body:
        v.append(Violation("AC-C09-9", "script 不在時の not-run 理由 script-absent の宣言が無い"))
    absent = _lines_with(body, "script-absent", "not-run")
    if not absent:
        v.append(Violation("AC-C09-9", "script 不在を not-run として扱う宣言が無い (skip を pass に読み替えない)"))
    if not re.search(r"script-absent[\s\S]{0,400}(パス|path)", body):
        v.append(Violation("AC-C09-9", "script 不在時に解決を試みたパスを提示する宣言が無い"))

    # config-not-normalized は command 側で正規化しない
    if "config-not-normalized" not in body:
        v.append(Violation("AC-C09-3", "未正規化 config 時の not-run 理由 config-not-normalized の宣言が無い"))
    if "validate-handout-config.py" not in body or "--strict" not in body:
        v.append(Violation("AC-C09-3", "未正規化の検出に validate-handout-config.py --strict を使う宣言が無い"))


# --- AC-C09-11 ------------------------------------------------------------

def _check_arguments(body, v):
    for name, marker in ARGUMENT_DEFAULTS.items():
        if name not in body:
            v.append(Violation("AC-C09-11", f"引数 {name} の宣言が無い"))
            continue
        if marker not in body:
            v.append(Violation("AC-C09-11", f"引数 {name} の既定値 ({marker}) の宣言が無い"))
    if not re.search(r"--out-dir[\s\S]{0,300}(親|parent)", body):
        v.append(Violation("AC-C09-11", "--out-dir 未指定時に html-path の親ディレクトリを渡す既定の宣言が無い"))
    if not re.search(r"--only[\s\S]{0,300}(カンマ|,)", body):
        v.append(Violation("AC-C09-11", "--only のカンマ区切り指定の宣言が無い"))


# --- AC-C09-6 -------------------------------------------------------------

def _check_boundary(fm, body, body_lines, v):
    if "read-only" not in body and "読み取り専用" not in body:
        v.append(Violation("AC-C09-6", "read-only な集約入口である宣言が無い"))
    for forbidden in ("正規化", "生成", "逆抽出"):
        if forbidden not in body:
            v.append(Violation("AC-C09-6", f"{forbidden}を行わない旨の境界宣言が無い"))
    # 検査対象を書き換える肯定形の記述を持たない (否定形の宣言は許す)
    positive_write = re.compile(r"(書き換える|書き換えて|上書きする|上書きして|修正する|修正して|正規化する|正規化して)")
    negation = re.compile(r"(ない|なく|せず|ず(に|、)|禁止|べきではない)")
    for line in body_lines:
        for hit in positive_write.finditer(line):
            tail = line[hit.end():hit.end() + 30]
            if not negation.search(tail):
                v.append(Violation(
                    "AC-C09-6",
                    f"対象を書き換える記述を持ってはならない: {line.strip()!r}",
                ))
                break
    tools = [str(x) for x in _as_list(fm.get("allowed-tools"))]
    if "Write" in tools:
        v.append(Violation("AC-C09-6", "allowed-tools の Write は read-only 境界に反する"))


# --- AC-C09-10 ------------------------------------------------------------

def _check_reporting(body, v):
    # behavior 6: 4 ゲート全部を行として出す
    if not re.search(r"4\s*(ゲート|行|面)", body):
        v.append(Violation("AC-C09-10", "報告に 4 ゲート全部を行として出す宣言が無い"))
    if "省かない" not in body and "省略しない" not in body:
        v.append(Violation("AC-C09-10", "実行しなかったゲートを報告から省かない宣言が無い"))
    for column in ("gate_id", "理由", "該当箇所"):
        if column not in body:
            v.append(Violation("AC-C09-10", f"報告行の要素 {column!r} の宣言が無い"))
    # behavior 7: 集約サマリ
    if "集約サマリ" not in body:
        v.append(Violation("AC-C09-10", "--json-report 指定時に集約サマリを出す宣言が無い"))
    for key in SUMMARY_KEYS:
        if key not in body:
            v.append(Violation("AC-C09-10", f"集約サマリの要素 {key!r} の宣言が無い"))
    # behavior 8: 次の一手
    if "次の一手" not in body and "次にすること" not in body:
        v.append(Violation("AC-C09-10", "全体が pass でない場合の次の一手を案内する宣言が無い"))


# --- AC-C09-AGG-1 (C01 との一致) ------------------------------------------

def _check_consumer_parity(body, v):
    if CONSUMER_COMMAND not in body and "C01" not in body:
        v.append(Violation("AC-C09-AGG-1", "delegated_consumers である C01 run-handout-build への言及が無い"))
    if not re.search(r"(同一|同じ)[\s\S]{0,120}verdict", body):
        v.append(Violation(
            "AC-C09-AGG-1",
            "C09 直叩き経路と C01 R4-verify 経路が同一 verdict を返す invariant の宣言が無い",
        ))
    if "単一正本" not in body and "single" not in body.lower():
        v.append(Violation("AC-C09-AGG-1", "集約規則の単一正本がこの command である宣言が無い"))


# --------------------------------------------------------------------------

def violation_ids(violations):
    return [x.contract_id for x in violations]


def repo_root() -> Path:
    return Path(__file__).resolve().parents[4]


def plugin_root() -> Path:
    return repo_root() / "plugins" / "guide-doc-generator"


def build_target() -> Path:
    return repo_root() / BUILD_TARGET
