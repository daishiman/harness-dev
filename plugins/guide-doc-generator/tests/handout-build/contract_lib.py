"""handout-build (C07) の slash-command 宣言的契約チェッカ。

slash-command component は実行そのものを機械検査できないため、検査対象は
`commands/handout-build.md` の宣言 (frontmatter / 引数表 / 経路判定 /
委譲先の宣言 / 矛盾停止条件 / 報告の形 / 薄い入口であることの宣言) である。

契約の出典:
  - plugin-plans/guide-doc-generator/briefs/command-brief-C07.json (正本)
  - plugin-plans/guide-doc-generator/component-inventory.json #C07
  - plugin-plans/guide-doc-generator/briefs/skill-brief-C01.json (委譲先)
  - plugin-plans/guide-doc-generator/briefs/RESOLUTION-P03.md / RESOLUTION-R21.md

標準ライブラリのみを使う (PyYAML は使わない)。
"""

from __future__ import annotations

import json
import re
from collections import namedtuple
from pathlib import Path

Violation = namedtuple("Violation", ["contract_id", "message"])


# --------------------------------------------------------------------------
# 契約の定数 (すべて brief / inventory 由来。ここで発明しない)
# --------------------------------------------------------------------------

COMMAND_NAME = "handout-build"
BUILD_TARGET = "plugins/guide-doc-generator/commands/handout-build.md"

# component-inventory.json #C07 description (brief の description と同一文字列)
DESCRIPTION = (
    "題材から単一 HTML の資料生成を手動起動する "
    "(--theme は構成データにテーマ欄が無い場合のみ有効で、"
    "採用値は同梱構成データへ書き戻されるため再現の単位は同梱構成データに閉じる)"
)

# component-inventory.json #C07 allowed-tools (過不足なく一致させる)
REQUIRED_TOOLS = ("Read", "Write", "Bash", "Skill")

# brief argument_hint (正本) が持つ全フラグ
ARGUMENT_HINT_TOKENS = ("[題材]", "--config", "--doc-type", "--out-dir", "--theme", "--date")

# brief arguments[] の name (順序も brief の並び)
ARGUMENT_NAMES = ("題材", "--config", "--doc-type", "--out-dir", "--theme", "--date")

# 機械可読な引数表の id。brief は引数を散文で持つだけで機械可読形式を規定して
# いないため、機械検査可能な単一形式として本テスト群がこの fenced json を要求する。
ARGS_BLOCK_ID = "CR-HB-ARGS"

# 委譲先 (brief delegates_to / delegation_form)
DELEGATE_SKILL = "run-handout-build"
DELEGATION_FORM = 'Skill(run-handout-build, args="$ARGUMENTS")'
DELEGATE_BUILD_TARGET = "plugins/guide-doc-generator/skills/run-handout-build/"

# AC-C07-2: 用途種別の語彙は C23 が単一正本。command 本文へ列挙してはならない。
DOC_TYPE_VOCABULARY = (
    "lecture",
    "agenda",
    "guide",
    "onboarding",
    "study-notes",
    "study-plan",
    "report",
    "proposal",
)
PRESET_RESOLVER = "resolve-handout-preset.py"

# 単一正本の script 名 (brief 本文が名指しする相手)
CONFIG_VALIDATOR = "validate-handout-config.py"
OUTPUT_ROUTER = "route-handout-output.py"
THEME_WRITEBACK_WRITER = "render-handout.py"

# behavior 6 が要求する生成レポートの 5 要素
REPORT_ELEMENTS = (
    re.compile(r"出力(先|ディレクトリ)"),
    re.compile(r"同梱"),
    re.compile(r"(適用|使用)部品|適用された部品"),
    re.compile(r"埋め込みサイズ"),
    re.compile(r"ゲート"),
)

# failure_modes 末尾の任意依存
OPTIONAL_DEP = "slide-report-generator"


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
# 引数表ブロックの取り出し
# --------------------------------------------------------------------------

_FENCE = re.compile(r"```json\s*\n(.*?)\n```", re.DOTALL)


def extract_args_block(body: str):
    """本文中の fenced json から id == CR-HB-ARGS のブロックを返す。

    戻り値 (block_or_None, parse_errors)。
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


def strip_fenced_json(body: str) -> str:
    """fenced json を取り除いた散文だけを返す (語彙ハードコード検査は散文にも効かせる)。"""
    return _FENCE.sub("\n", body)


# --------------------------------------------------------------------------
# 汎用ヘルパ
# --------------------------------------------------------------------------


def plugin_root() -> Path:
    return Path(__file__).resolve().parents[2]


def dir_name_shape() -> str:
    """出力ディレクトリ名の人間可読な形。正本は config/handout-output.json。

    ここで形を綴らないのは、R25 のように書式が変わったとき本テストだけ旧形を
    要求して赤くなる (= 契約でなく写しになる) のを避けるため。
    """
    fmt = json.loads(
        (plugin_root() / "config" / "handout-output.json").read_text(encoding="utf-8")
    )["dir_name_format"]
    return fmt.replace("{date}", "<YYYY-MM-DD>").replace("{slug}", "<主題slug>")


def build_target() -> Path:
    return plugin_root() / "commands" / f"{COMMAND_NAME}.md"


def command_path(root) -> Path:
    return Path(root) / "commands" / f"{COMMAND_NAME}.md"


def violation_ids(violations) -> list:
    seen = []
    for item in violations:
        if item.contract_id not in seen:
            seen.append(item.contract_id)
    return seen


def _as_list(value):
    if value is None:
        return []
    if isinstance(value, list):
        return value
    return [value]


def _requires(v, contract_id, body, patterns, label):
    """patterns (regex 文字列) が全て body に現れることを要求する。

    Markdown の soft wrap で 1 文が改行を跨ぐため DOTALL で照合する。
    """
    for pattern in patterns:
        if not re.search(pattern, body, re.DOTALL):
            v.append(Violation(contract_id, f"{label}: /{pattern}/ に当たる記述が無い"))


# --------------------------------------------------------------------------
# 検査本体
# --------------------------------------------------------------------------


def check_command(root) -> list:
    """commands/handout-build.md 一式を検査し Violation の一覧を返す。"""
    root = Path(root)
    md = command_path(root)
    v = []

    if not md.is_file():
        v.append(Violation("AC-C07-1", f"command 定義が存在しない: {md}"))
        return v

    text = md.read_text(encoding="utf-8")
    fm, body = split_frontmatter(text)
    if fm is None:
        v.append(Violation("AC-C07-1", "YAML frontmatter が無い"))
        return v

    prose = strip_fenced_json(body)

    _check_frontmatter(fm, v)
    _check_arguments_block(body, v)
    _check_doc_type_vocabulary(fm, body, prose, v)
    _check_theme(body, v)
    _check_date(body, v)
    _check_out_dir(body, v)
    _check_config(body, v)
    _check_delegation(root, body, v)
    _check_routes(body, v)
    _check_boundary(body, v)
    _check_behavior_stops(body, v)
    _check_failure_modes(body, v)
    _check_reporting(body, v)

    return v


# --- AC-C07-1: frontmatter -------------------------------------------------

def _check_frontmatter(fm, v):
    cid = "AC-C07-1"

    if fm.get("name") != COMMAND_NAME:
        v.append(Violation(cid, f"frontmatter name は {COMMAND_NAME!r} (実際: {fm.get('name')!r})"))

    desc = fm.get("description")
    if desc != DESCRIPTION:
        v.append(
            Violation(
                cid,
                "description が component-inventory.json#C07 と一致しない\n"
                f"    期待: {DESCRIPTION}\n"
                f"    実際: {desc}",
            )
        )

    tools = _as_list(fm.get("allowed-tools"))
    if sorted(tools) != sorted(REQUIRED_TOOLS):
        v.append(
            Violation(
                cid,
                f"allowed-tools は {list(REQUIRED_TOOLS)} と過不足なく一致すること (実際: {tools})",
            )
        )

    dmi = fm.get("disable-model-invocation")
    if dmi is not False:
        v.append(Violation(cid, f"disable-model-invocation は false (実際: {dmi!r})"))

    hint = fm.get("argument-hint")
    if not isinstance(hint, str) or not hint.strip():
        v.append(Violation(cid, "argument-hint が空"))
    else:
        for token in ARGUMENT_HINT_TOKENS:
            if token not in hint:
                v.append(
                    Violation(
                        cid,
                        f"argument-hint に {token} が無い "
                        "(brief argument_hint が正本。6 引数すべてを露出させる)",
                    )
                )


# --- AC-C07-ARGS: 引数表 ----------------------------------------------------

def _check_arguments_block(body, v):
    cid = "AC-C07-ARGS"
    block, errors = extract_args_block(body)
    for message in errors:
        v.append(Violation(cid, message))

    if block is None:
        v.append(
            Violation(
                cid,
                f"機械可読な引数表 (fenced json / id={ARGS_BLOCK_ID}) が本文に無い",
            )
        )
        return

    args = block.get("arguments")
    if not isinstance(args, list):
        v.append(Violation(cid, f"{ARGS_BLOCK_ID}.arguments が配列でない"))
        return

    names = [a.get("name") for a in args if isinstance(a, dict)]
    if names != list(ARGUMENT_NAMES):
        v.append(
            Violation(
                cid,
                f"引数表の name 列が brief arguments[] と一致しない\n"
                f"    期待: {list(ARGUMENT_NAMES)}\n"
                f"    実際: {names}",
            )
        )

    for arg in args:
        if not isinstance(arg, dict):
            v.append(Violation(cid, f"引数表の要素が object でない: {arg!r}"))
            continue
        name = arg.get("name")
        if arg.get("required") is not False:
            v.append(
                Violation(cid, f"{name}: required は false (brief では 6 引数すべて必須ではない)")
            )
        for key in ("default", "override_rule"):
            value = arg.get(key)
            if not isinstance(value, str) or not value.strip():
                v.append(Violation(cid, f"{name}: {key} が空 (既定値と上書き規則は必ず宣言する)"))

    positional = [a.get("name") for a in args if isinstance(a, dict) and a.get("position") == "positional"]
    if positional != ["題材"]:
        v.append(
            Violation(cid, f"positional は 題材 ただ 1 つ (実際: {positional})")
        )


# --- AC-C07-2: 用途語彙のハードコード禁止 -----------------------------------

def _check_doc_type_vocabulary(fm, body, prose, v):
    cid = "AC-C07-2"
    haystack = f"{fm.get('description', '')}\n{fm.get('argument-hint', '')}\n{body}"
    for slug in DOC_TYPE_VOCABULARY:
        if re.search(rf"(?<![0-9A-Za-z_-]){re.escape(slug)}(?![0-9A-Za-z_-])", haystack):
            v.append(
                Violation(
                    cid,
                    f"用途種別の語彙 {slug!r} が command 定義に列挙されている "
                    f"(語彙正本は C23 {PRESET_RESOLVER} のみ)",
                )
            )

    if PRESET_RESOLVER not in prose:
        v.append(Violation(cid, f"--doc-type の説明が {PRESET_RESOLVER} を参照していない"))
    if not re.search(rf"{re.escape(PRESET_RESOLVER)}\s+--list", body):
        v.append(
            Violation(cid, f"候補提示の手段として `{PRESET_RESOLVER} --list` が案内されていない")
        )


# --- AC-C07-3: --theme の 3 点 ---------------------------------------------

def _check_theme(body, v):
    _requires(
        v,
        "AC-C07-3",
        body,
        [
            r"構成データ.{0,20}テーマ欄.{0,30}(無い|ない).{0,20}(場合|とき).{0,10}(のみ|限)",
            r"(採用|適用).{0,20}テーマ.{0,40}同梱.{0,10}構成データ.{0,20}書き戻",
            r"再現.{0,20}単位.{0,20}同梱.{0,10}構成データ",
        ],
        "AC-C07-3 --theme の 3 点",
    )
    if THEME_WRITEBACK_WRITER not in body:
        v.append(
            Violation(
                "AC-C07-3",
                f"テーマ書き戻しの実行者 {THEME_WRITEBACK_WRITER} (C11) が名指しされていない "
                "(command 自身が書き戻すと読める)",
            )
        )


# --- AC-C07-DATE ------------------------------------------------------------

def _check_date(body, v):
    cid = "AC-C07-DATE"
    _requires(
        v,
        cid,
        body,
        [
            r"yyyy/mm/dd",
            r"(自前で|自分で).{0,10}(現在日|実行日|今日).{0,10}(を)?.{0,10}取得しない",
            rf"{re.escape(CONFIG_VALIDATOR)}\s+--normalize",
        ],
        "AC-C07-DATE --date の規則",
    )
    for tolerant in ("yyyy-mm-dd", "yyyy/m/d", "yyyy-m-d"):
        if tolerant not in body:
            v.append(
                Violation(cid, f"C12 N4 が寛容に受ける書式 {tolerant} の素通し記述が無い")
            )
    if not re.search(r"(書式|形式).{0,20}(判定|検証).{0,20}しない|判定しない", body, re.DOTALL):
        v.append(Violation(cid, "書式判定を command が行わない旨の宣言が無い"))


# --- AC-C07-OUTDIR ----------------------------------------------------------

def _check_out_dir(body, v):
    _requires(
        v,
        "AC-C07-OUTDIR",
        body,
        [
            r"親ディレクトリ.{0,20}(だけ|のみ).{0,20}上書き",
            re.escape(dir_name_shape()),
            r"命名規則.{0,30}上書きでき(ない|ず)",
            re.escape(OUTPUT_ROUTER),
        ],
        "AC-C07-OUTDIR --out-dir の規則",
    )


# --- AC-C07-CONFIG ----------------------------------------------------------

def _check_config(body, v):
    cid = "AC-C07-CONFIG"
    _requires(
        v,
        cid,
        body,
        [
            r"存在.{0,30}(と|・|/).{0,10}JSON.{0,30}(読み取り|読める|読み込み)",
            r"(内容|妥当性).{0,30}判定.{0,10}(は)?.{0,10}しない",
            r"構成データ.{0,30}(に書かれた値.{0,10})?(常に)?.{0,10}CLI.{0,20}(フラグ)?.{0,10}より(も)?強い",
        ],
        "AC-C07-CONFIG --config の規則",
    )
    if CONFIG_VALIDATOR not in body:
        v.append(Violation(cid, f"妥当性判定の担い手 {CONFIG_VALIDATOR} (C12) が名指しされていない"))


# --- AC-C07-4: 委譲 ---------------------------------------------------------

def _check_delegation(root, body, v):
    cid = "AC-C07-4"
    if DELEGATION_FORM not in body:
        v.append(
            Violation(cid, f"brief delegation_form どおりの起動記述が無い: {DELEGATION_FORM}")
        )
    if DELEGATE_BUILD_TARGET not in body:
        v.append(
            Violation(
                cid,
                f"委譲先 skill の build_target ({DELEGATE_BUILD_TARGET}) が明記されていない",
            )
        )
    skill_md = Path(root) / "skills" / DELEGATE_SKILL / "SKILL.md"
    if not skill_md.is_file():
        v.append(Violation(cid, f"委譲先 skill が実在しない: {skill_md}"))


# --- AC-C07-5: 経路判定 -----------------------------------------------------

def _check_routes(body, v):
    _requires(
        v,
        "AC-C07-5",
        body,
        [
            r"--config\s*(が)?\s*(あり|指定).{0,40}(非対話|ヒアリング.{0,10}省略)",
            r"--config\s*(が)?\s*(なし|無し|未指定).{0,40}ヒアリング",
            r"対話.{0,10}は.{0,10}既定.{0,10}経路であって.{0,10}唯一.{0,10}経路ではない",
            r"R2-design",
        ],
        "AC-C07-5 経路判定",
    )


# --- AC-C07-6: 薄い入口 -----------------------------------------------------

def _check_boundary(body, v):
    cid = "AC-C07-6"
    _requires(
        v,
        cid,
        body,
        [
            r"(判断|加工).{0,10}(も)?.{0,10}(加工|判断)?.{0,10}しない",
            r"HTML.{0,20}(組み立て|生成).{0,30}(関与|行わ|行い).{0,10}(しない|ない|ません)",
            r"薄い入口",
            r"資料の内容.{0,40}(関与|触れ).{0,10}(しない|ない)",
        ],
        "AC-C07-6 薄い入口",
    )
    # 委譲先の責務を command が持たない宣言 (brief boundary の後半)
    for delegated in ("ヒアリング", "プリセット解決", "出力先ルーティング", "ゲート結果"):
        if delegated not in body:
            v.append(
                Violation(cid, f"skill へ渡す責務 {delegated!r} が boundary に列挙されていない")
            )


# --- AC-C07-B1 / B2: behavior の停止条件 ------------------------------------

def _check_behavior_stops(body, v):
    _requires(
        v,
        "AC-C07-B1",
        body,
        [r"未知.{0,10}フラグ.{0,30}(推測|解釈).{0,20}(せず|しない).{0,20}停止"],
        "AC-C07-B1 未知フラグ",
    )
    _requires(
        v,
        "AC-C07-B2",
        body,
        [r"題材.{0,10}と.{0,10}--config.{0,20}(同時|両方).{0,20}(指定).{0,20}(は)?.{0,20}矛盾"],
        "AC-C07-B2 題材と --config の同時指定",
    )


# --- AC-C07-FM-1..7: failure_modes -----------------------------------------

def _check_failure_modes(body, v):
    _requires(
        v,
        "AC-C07-FM-1",
        body,
        [
            r"題材.{0,10}(も|も、).{0,10}--config.{0,10}(も).{0,10}(無い|ない).{0,60}"
            r"(エラーにせず|エラーにしない)",
            r"R1-elicit",
        ],
        "AC-C07-FM-1 引数なし起動",
    )
    _requires(
        v,
        "AC-C07-FM-2",
        body,
        [
            r"--config.{0,20}(パス)?.{0,20}(存在しない|不在).{0,80}"
            r"(委譲先を起動せず|起動せず).{0,20}停止",
            r"解決した(パス|経路).{0,20}(を)?.{0,10}(表示|提示)",
        ],
        "AC-C07-FM-2 --config 不在",
    )
    _requires(
        v,
        "AC-C07-FM-3",
        body,
        [r"exit\s*(≠|!=)\s*0.{0,40}停止", r"候補.{0,10}(提示|一覧)"],
        "AC-C07-FM-3 語彙外 --doc-type",
    )
    _requires(
        v,
        "AC-C07-FM-4",
        body,
        [
            r"(黙って|暗黙に).{0,20}(無視|上書き).{0,20}(しない|せず)",
            r"キーパス",
            r"(両方|双方).{0,10}の値",
        ],
        "AC-C07-FM-4 構成データとの衝突",
    )
    _requires(
        v,
        "AC-C07-FM-5",
        body,
        [
            r"生成物.{0,20}(を)?.{0,10}残",
            r"FAIL.{0,30}(明示|提示)",
            r"成功.{0,20}(扱い|と読める).{0,20}(に)?.{0,10}(しない|書かない)",
        ],
        "AC-C07-FM-5 ゲート FAIL",
    )
    _requires(
        v,
        "AC-C07-FM-6",
        body,
        [
            r"HB_OUT_DIR",
            r"default_out_dir",
            r"exit\s*2.{0,40}停止",
        ],
        "AC-C07-FM-6 出力先が解決できない",
    )
    _requires(
        v,
        "AC-C07-FM-7",
        body,
        [
            rf"{re.escape(OPTIONAL_DEP)}.{{0,40}}(不在|無い|ない)",
            r"skip.{0,20}(理由)",
            r"(他|残り).{0,20}(ステップ|工程).{0,20}(は)?.{0,10}(完走|継続)",
            r"fail-soft",
        ],
        "AC-C07-FM-7 任意依存の不在",
    )


# --- AC-C07-REPORT / AC-C07-THEME-NOTICE ------------------------------------

def _check_reporting(body, v):
    cid = "AC-C07-REPORT"
    labels = (
        "出力ディレクトリのパス",
        "同梱 4 点",
        "適用部品",
        "埋め込みサイズと warning",
        "各ゲートの結果",
    )
    for pattern, label in zip(REPORT_ELEMENTS, labels):
        if not pattern.search(body):
            v.append(Violation(cid, f"生成レポートの要素 {label!r} が報告項目に無い"))
    if not re.search(r"そのまま(提示|報告)", body):
        v.append(
            Violation(cid, "委譲先が返すレポートを command が加工せずそのまま提示する旨が無い")
        )

    _requires(
        v,
        "AC-C07-THEME-NOTICE",
        body,
        [r"--theme.{0,40}(再指定|指定).{0,10}(は)?.{0,10}不要"],
        "AC-C07-THEME-NOTICE テーマ採用時の案内",
    )
