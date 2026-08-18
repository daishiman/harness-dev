"""C11 render-handout.py 受入テストの共通土台。

このモジュール自体はテストを持たない (discover の pattern test_*.py に一致しない)。
契約の出所はすべて plugin-plans/guide-doc-generator/briefs/script-brief-C11.json であり、
ここで新しい契約を発明しない。
"""

import json
import os
import re
import subprocess
import sys
from html.parser import HTMLParser
from pathlib import Path

# tests/render-handout.py/ -> tests/ -> guide-doc-generator/ -> plugins/ -> repo root
TESTS_DIR = Path(__file__).resolve().parent
PLUGIN_ROOT = TESTS_DIR.parent.parent
REPO_ROOT = PLUGIN_ROOT.parent.parent

SCRIPT = PLUGIN_ROOT / "scripts" / "render-handout.py"
PARTS_CATALOG = PLUGIN_ROOT / "config" / "handout-parts.json"
CONFIG_SCHEMA = PLUGIN_ROOT / "schemas" / "handout-config.schema.json"

# AC-C11-19 が対象にする配下ディレクトリ (tests/ は対象外)
GREP_SCOPE_DIRS = ("scripts", "skills", "agents", "commands", "hooks", "references")

# AC-C11-19 が禁じているのは「第 2 の部品 id 語彙」であり、語彙になり得るのは
# システムが実行するテキストか、エージェントが指示として読み込むテキストだけ。
# 何にも読み込まれない散文の注釈は語彙になり得ないので走査から外す。外すのは
# 次の 2 種類のみで、判断基準は「そのテキストを何かが読むか」の 1 本:
#
#   1. Python のコメントと docstring。実行されない。カタログを説明する散文で
#      部品 id に言及することと、部品 id の名簿を持つことは別である。
#   2. scripts/ 配下の非実行ファイル。scripts/ はプログラムの置き場であり、
#      ここへ置かれる .md (leaf の作業記録) は誰にも読み込まれない。
#
# skills / agents / commands / hooks / references は拡張子を問わず全て対象の
# まま。prompts/ や references/ の frontmatter を持たない .md も指示として
# 読み込まれるため、ここを外すと本当に検出したい列挙を見逃す。
#
# 除外は allowlist (「.py だけ走査する」) でなく denylist (「読まれないと特定
# できるものだけ外す」) で書く。allowlist だと scripts/part-map.json のような
# 「プログラムが読むデータファイル」が拡張子だけを理由に走査から外れ、表を
# config/ へ逃がす Goodhart 的回避と同じ効果を持つ抜け道になる。未知の拡張子は
# 既定で走査対象側へ倒す (fail-closed)。
#
# scripts/ 配下で「何にも読み込まれない」と言い切れるのは leaf の作業記録
# (.md) だけ。.json / .yaml / .toml / .txt はプログラムが読む前提の置き場所
# なので対象に含める。なお .md でも走査対象から名前で参照されていれば
# 「読まれる側」なので走査へ拾い直す (scannable_sources を参照)。
SCRIPT_UNREAD_SUFFIXES = (".md",)

# 生成物。正本ではなく、正本を直せば必ず追随する。走査しても偽陽性を増やす
# だけなので全ディレクトリで一律に外す (.pyc はどのみち decode に失敗するが、
# 「読めなかったから外れた」ではなく「生成物だから外す」と明示しておく)。
GENERATED_DIR_NAMES = ("__pycache__",)
GENERATED_SUFFIXES = (".pyc", ".pyo")


def _mask_python_prose(text):
    """Python ソースのコメントと docstring を空白へ潰す (行・桁の位置は保つ)。

    文字列リテラル一般は潰さない。照合表の鍵のような「データとしての文字列」は
    まさに検出したい対象であり、潰すと assert が弱くなる。潰すのは文としての
    文字列 (docstring) とコメントだけ。
    """
    import ast
    import io
    import tokenize

    line_starts = []
    offset = 0
    for line in text.splitlines(keepends=True):
        line_starts.append(offset)
        offset += len(line)
    line_starts.append(offset)

    def span(l1, c1, l2, c2):
        return line_starts[l1 - 1] + c1, line_starts[l2 - 1] + c2

    spans = []
    try:
        tree = ast.parse(text)
    except SyntaxError:
        return text
    for node in ast.walk(tree):
        if (isinstance(node, ast.Expr) and isinstance(node.value, ast.Constant)
                and isinstance(node.value.value, str)):
            v = node.value
            spans.append(span(v.lineno, v.col_offset, v.end_lineno, v.end_col_offset))
    try:
        for tok in tokenize.generate_tokens(io.StringIO(text).readline):
            if tok.type == tokenize.COMMENT:
                spans.append(span(tok.start[0], tok.start[1], tok.end[0], tok.end[1]))
    except (tokenize.TokenError, IndentationError):  # pragma: no cover - 診断用
        pass

    buf = list(text)
    for start, end in spans:
        for i in range(start, min(end, len(buf))):
            if buf[i] != "\n":
                buf[i] = " "
    return "".join(buf)


def scannable_sources(plugin_root=None):
    """AC-C11-19 の走査対象を (Path, テキスト) で返す。

    テキストは散文注釈をマスクした後の内容で、行番号は元ファイルと一致する。

    plugin_root を渡すと使い捨ての root を走査する (反例注入用)。モジュール
    グローバルを書き換えないので復元手順が要らず、復元失敗も起こらない。
    """
    base = Path(plugin_root) if plugin_root is not None else PLUGIN_ROOT
    always = []
    deferred = []
    for sub in GREP_SCOPE_DIRS:
        root = base / sub
        if not root.is_dir():
            continue
        for path in sorted(root.rglob("*")):
            if not path.is_file():
                continue
            if any(part in GENERATED_DIR_NAMES for part in path.parts):
                continue
            if path.suffix in GENERATED_SUFFIXES:
                continue
            try:
                text = path.read_text(encoding="utf-8")
            except (UnicodeDecodeError, OSError):
                continue
            if path.suffix == ".py":
                text = _mask_python_prose(text)
            if sub == "scripts" and path.suffix in SCRIPT_UNREAD_SUFFIXES:
                deferred.append((path, text))
            else:
                always.append((path, text))

    # 除外条件は拡張子でなく「何にも読み込まれない」こと。scripts/*.md でも、
    # 走査対象のどれかがファイル名で参照していれば読まれる側なので拾い直す。
    # 判定材料は散文マスク済みのテキスト — コメントで名前に言及しただけの
    # ものを「読んでいる」とは数えない。
    referenced = "\n".join(text for _, text in always)
    out = always + [(p, t) for p, t in deferred if p.name in referenced]
    out.sort(key=lambda pair: str(pair[0]))
    return out


# 部品 id のリテラル (カタログ側の id 体系に合わせた形)。
PART_ID_PATTERN = re.compile(r"\bB[01][0-9]\b")


def enumerated_part_id_offenders(plugin_root=None):
    """走査対象のうち部品 id リテラルを含む行を "path:lineno: line" で返す。

    AC-C11-19 の本体。走査範囲 (scannable_sources) と判定 (この関数) を 1 箇所
    へ置き、本番の検査と反例注入の検査が同じ経路を通るようにする。別実装にする
    と「反例では鳴るが本番では鳴らない」を作り込める。
    """
    offenders = []
    for path, text in scannable_sources(plugin_root):
        try:
            shown = path.relative_to(REPO_ROOT)
        except ValueError:  # 反例注入で使い捨て root を差した場合
            shown = path
        for lineno, line in enumerate(text.splitlines(), 1):
            if PART_ID_PATTERN.search(line):
                offenders.append("%s:%d: %s" % (shown, lineno, line.strip()))
    return offenders

# 1x1 の透過 PNG (data URI 埋め込み用・外部参照ゼロ)
PNG_DATA_URI = (
    "data:image/png;base64,"
    "iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAYAAAAfFcSJAAAADUlEQVR42mNk"
    "YPhfDwAChwGA60e6kgAAAABJRU5ErkJggg=="
)

SCHEMA_VERSION = "1"
DEFAULT_DATE = "2026/01/05"


def require_script():
    """実装が無い状態を error でなく failure として立てる。"""
    if not SCRIPT.is_file():
        raise AssertionError(
            "build_target が未実装: %s\n"
            "P05 が render-handout.py を実装するまで本テスト群は赤で固定される。" % SCRIPT
        )


def require_parts_catalog():
    if not PARTS_CATALOG.is_file():
        raise AssertionError(
            "部品カタログ正本が未実装: %s (P03 Y-05 / owner=C11)" % PARTS_CATALOG
        )


def load_parts_catalog():
    require_parts_catalog()
    with PARTS_CATALOG.open(encoding="utf-8") as fh:
        return json.load(fh)


def catalog_parts():
    return load_parts_catalog()["parts"]


def require_config_schema():
    if not CONFIG_SCHEMA.is_file():
        raise AssertionError("構成データ schema 正本が未実装: %s" % CONFIG_SCHEMA)


def load_config_schema():
    require_config_schema()
    with CONFIG_SCHEMA.open(encoding="utf-8") as fh:
        return json.load(fh)


def provenance_defaults():
    """schema の $defs.provenance から必須キーの const を実行時に導出する。

    値をここに焼き込まない。schema 側で const が外れたら (テストの想定が
    古くなったということなので) AssertionError で気付けるようにする。
    """
    schema = load_config_schema()
    try:
        prov = schema["$defs"]["provenance"]
    except KeyError as exc:  # pragma: no cover - schema 破損時の診断用
        raise AssertionError("schema に $defs.provenance が無い: %s" % CONFIG_SCHEMA) from exc
    props = prov.get("properties") or {}
    out = {}
    for key in prov.get("required") or []:
        spec = props.get(key) or {}
        if "const" not in spec:
            raise AssertionError(
                "$defs.provenance.%s に const が無く fixture 値を導出できない "
                "(schema 変更に追随が必要): %s" % (key, CONFIG_SCHEMA)
            )
        out[key] = spec["const"]
    return out


class Result:
    def __init__(self, proc):
        self.returncode = proc.returncode
        self.stdout = proc.stdout
        self.stderr = proc.stderr

    def json_line(self):
        lines = [ln for ln in self.stdout.splitlines() if ln.strip()]
        if len(lines) != 1:
            raise AssertionError(
                "--out 指定時の stdout は結果 JSON 1 オブジェクト 1 行のはずが %d 行: %r"
                % (len(lines), self.stdout)
            )
        return json.loads(lines[0])


def run_render(args, cwd=None, env_extra=None):
    """render-handout.py を subprocess で起動する。"""
    require_script()
    env = dict(os.environ)
    env["HB_ROOT"] = str(PLUGIN_ROOT)
    env.setdefault("PYTHONHASHSEED", "0")
    if env_extra:
        env.update(env_extra)
    proc = subprocess.run(
        [sys.executable, str(SCRIPT)] + [str(a) for a in args],
        capture_output=True,
        text=True,
        cwd=str(cwd or REPO_ROOT),
        env=env,
    )
    return Result(proc)


def write_config(path, config):
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(config, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    return path


def render_html(tmpdir, config, extra_args=()):
    """正常系の生成 HTML 文字列を返す (exit 0 を前提としない・呼び出し側で検査)。"""
    cfg_path = write_config(Path(tmpdir) / "config.json", config)
    out_path = Path(tmpdir) / "handout.html"
    res = run_render(["--config", cfg_path, "--out", out_path] + list(extra_args))
    html_text = out_path.read_text(encoding="utf-8") if out_path.is_file() else ""
    return res, html_text, out_path


# --------------------------------------------------------------------------
# 構成データ fixture (C12 --normalize 済みの形)
# --------------------------------------------------------------------------

BLOCK_FIXTURES = {
    "steps": {
        "id": "blk-steps",
        "type": "steps",
        "items": [
            {"key": "st1", "label": "資料を開く", "detail": "手元で開く", "time": "5分", "icon": "check"},
            {"key": "st2", "label": "設定を確認する", "detail": "権限を見る", "time": "5分"},
        ],
    },
    "action-items": {
        "id": "blk-action",
        "type": "action-items",
        "items": [
            {"key": "ai1", "label": "議事録を配布する", "owner": "山田", "due": "2026/01/09"},
        ],
    },
    "handson": {
        "id": "blk-handson",
        "type": "handson",
        "live_demo": True,
        "asset_id": "asset-1",
        "steps": [
            {
                "key": "hs1",
                "operation": "画面右上のボタンを押す",
                "expected": "一覧が表示される",
                "stuck_hint": "権限設定を見直す",
            }
        ],
    },
    "trio": {
        "id": "blk-trio",
        "type": "trio",
        "cards": [
            {"key": "tr1", "tone": "today", "title": "分かっている", "body": "既知の範囲", "icon": "check"},
            {"key": "tr2", "tone": "rest", "title": "分からない", "body": "未知の範囲"},
        ],
    },
    "table": {
        "id": "blk-table",
        "type": "table",
        "columns": ["観点", "案A", "案B"],
        "rows": [["速さ", "速い", "遅い"], ["費用", "高い", "安い"]],
        "highlight": [[0, 1]],
    },
    "versus": {
        "id": "blk-versus",
        "type": "versus",
        "left": {"key": "lft", "label": "自前で作る", "tone": "today", "bullets": ["自由度が高い"]},
        "right": {"key": "rgt", "label": "既製品を使う", "tone": "rest", "bullets": ["早く始められる"]},
    },
    "features": {
        "id": "blk-features",
        "type": "features",
        "cards": [
            {"key": "f1", "title": "自動化", "body": "手作業を減らす", "footnote": "社内検証 2026"},
            {"key": "f2", "title": "共有", "body": "同じ資料を配る"},
        ],
    },
    "map": {
        "id": "blk-map",
        "type": "map",
        "items": [
            {"id": "mp1", "title": "調べる", "detail": "検索して確かめる"},
            {"id": "mp2", "title": "聞く", "detail": "担当者に確認する"},
        ],
    },
    "checklist": {
        "id": "blk-check",
        "type": "checklist",
        "items": [{"id": "ck1", "label": "権限を確認した"}, {"id": "ck2", "label": "配布先を決めた"}],
    },
    "accordion": {
        "id": "blk-accordion",
        "type": "accordion",
        "items": [{"key": "ac1", "summary": "補足", "body": "詳しい説明の本文"}],
    },
    "prompt": {
        "id": "blk-prompt",
        "type": "prompt",
        "label": "貼り付けるプロンプト",
        "text": "次の資料を要約してください",
    },
    "download": {
        "id": "blk-download",
        "type": "download",
        "attachments": [
            {
                "id": "att-1",
                "name": "sample.txt",
                "mime": "text/plain",
                "data_uri": "data:text/plain;base64,YQ==",
                "bytes": 1,
                "fallback_hint": "保存できないときは本文をコピーする",
            }
        ],
    },
    "tabs": {
        "id": "blk-tabs",
        "type": "tabs",
        "tabs": [
            {
                "id": "tb1",
                "label": "概要",
                "blocks": [{"id": "blk-tab-text", "type": "text", "body": "タブ内の地の文"}],
            }
        ],
    },
    "flow": {
        "id": "blk-flow",
        "type": "flow",
        "pattern": "flow",
        "steps": [{"key": "fl1", "label": "受付"}, {"key": "fl2", "label": "確認"}],
    },
    "chips": {
        "id": "blk-chips",
        "type": "chips",
        "single": True,
        "options": [{"key": "cp1", "label": "はい"}, {"key": "cp2", "label": "いいえ"}],
    },
    "image": {
        "id": "blk-image",
        "type": "image",
        "asset_id": "asset-1",
        "alt": "操作画面のスクリーンショット",
        "data_uri": PNG_DATA_URI,
        "caption": "実際の画面",
    },
    "diagram": {
        "id": "blk-diagram",
        "type": "diagram",
        "pattern": "flow",
        "steps": [{"key": "dg1", "label": "入力"}, {"key": "dg2", "label": "出力"}],
    },
    "text": {
        "id": "blk-text",
        "type": "text",
        "body": "どの型にも当てはまらない地の文をここへ置く。",
    },
}


def base_section(index=1, blocks=None, **over):
    sid = over.pop("id", "s%d" % index)
    section = {
        "id": sid,
        "heading": "セクション%d" % index,
        "goal": "セクション%d のゴールをここに書く" % index,
        "lead_line": "このセクションで押さえる 1 行の抽象",
        "judgment_axis": "迷ったら手戻りの少ない方を選ぶ",
        "duration": "10分",
        "role": "main",
        "ties_to": "goal",
        "section_kind": "standard",
        "blocks": list(blocks if blocks is not None else [BLOCK_FIXTURES["text"]]),
    }
    section.update(over)
    return section


def base_config(sections=None, **over):
    """正規化済み構成データの最小充足形 (R21 の必須フィールドを含む)。"""
    if sections is None:
        sections = [base_section(1), base_section(2)]
    config = {
        "schema_version": SCHEMA_VERSION,
        "normalized": True,
        "slug": "handout-sample",
        "subject_slug": "handout-sample",
        "title": "配布資料のサンプル",
        "date": DEFAULT_DATE,
        "reader": "はじめて触る担当者",
        "prior_knowledge_level": "none",
        "doc_type": "guide",
        "essential_problem": "手順が人によって違い、結果がそろわない",
        "purpose": "同じ手順で誰でも同じ結果に届くようにする",
        "background": "これまで口頭で共有しており、抜けが起きていた",
        "goal": "配布後 1 週間で全員が自力で最後まで実施できる",
        "duration": "約60分",
        "focus_theme": ["手順をそろえる"],
        "target_tasks": [{"id": "tt1", "label": "週次レポートを自分で作る"}],
        "attainment_level": "operable",
        "must_remember": ["最初に権限を確認する"],
        # schema 上の必須フィールド。空配列 (minItems 0) は正規化済みでも起こりうる形。
        "glossary": [],
        "no_need_to_remember": ["画面の細かい配置はこの資料を見返せばよい"],
        "presentation_order": "demo_first",
        # C12 --normalize が充填する来歴。normalized_by / schema_version は
        # schema の const から実行時に導出する (C18 / C22 の正規化検査の入口)。
        "provenance": dict(
            provenance_defaults(),
            presentation_order_source="derived-from-prior-knowledge",
        ),
        "goal_chips": ["自力で実施できる"],
        "lead": "この資料 1 枚で手順をそろえます",
        "assets": [
            {
                "id": "asset-1",
                "alt": "操作画面のスクリーンショット",
                "caption": "実際の画面",
                "role": "screenshot",
                "data_uri": PNG_DATA_URI,
                "src": "assets/screen.png",
            }
        ],
        "attachments": [],
        "sections": list(sections),
    }
    config["nav"] = [
        {"href": "#" + s["id"], "label": s.get("heading", s["id"])} for s in config["sections"]
    ]
    config.update(over)
    if "sections" in over and "nav" not in over:
        config["nav"] = [
        {"href": "#" + s["id"], "label": s.get("heading", s["id"])} for s in config["sections"]
    ]
    return config


def config_with_block(block):
    """1 ブロックだけを持つ構成データ (部品ごとのレンダリング検査用)。"""
    return base_config(sections=[base_section(1, blocks=[block])])


# --------------------------------------------------------------------------
# 生成 HTML の走査 (標準ライブラリのみ)
# --------------------------------------------------------------------------

VOID_TAGS = {
    "area", "base", "br", "col", "embed", "hr", "img", "input",
    "link", "meta", "param", "source", "track", "wbr",
}


class Element:
    __slots__ = ("tag", "attrs", "text", "children", "parent")

    def __init__(self, tag, attrs, parent=None):
        self.tag = tag
        self.attrs = attrs
        self.text = ""
        self.children = []
        self.parent = parent

    def get(self, name, default=None):
        return self.attrs.get(name, default)

    def classes(self):
        return (self.attrs.get("class") or "").split()

    def __repr__(self):  # pragma: no cover - 診断用
        return "<%s %r>" % (self.tag, self.attrs)


class _Collector(HTMLParser):
    def __init__(self):
        super().__init__(convert_charrefs=True)
        self.elements = []
        self._stack = []

    def handle_starttag(self, tag, attrs):
        el = Element(tag, {k: (v if v is not None else "") for k, v in attrs},
                     self._stack[-1] if self._stack else None)
        if el.parent is not None:
            el.parent.children.append(el)
        self.elements.append(el)
        if tag not in VOID_TAGS:
            self._stack.append(el)

    def handle_startendtag(self, tag, attrs):
        el = Element(tag, {k: (v if v is not None else "") for k, v in attrs},
                     self._stack[-1] if self._stack else None)
        if el.parent is not None:
            el.parent.children.append(el)
        self.elements.append(el)

    def handle_endtag(self, tag):
        for i in range(len(self._stack) - 1, -1, -1):
            if self._stack[i].tag == tag:
                del self._stack[i:]
                break

    def handle_data(self, data):
        for el in self._stack:
            el.text += data


def parse(html_text):
    parser = _Collector()
    parser.feed(html_text)
    parser.close()
    return parser.elements


def elements_with(html_text, attr, value=None):
    out = []
    for el in parse(html_text):
        if attr in el.attrs and (value is None or el.attrs[attr] == value):
            out.append(el)
    return out


def field_elements(html_text, field):
    return elements_with(html_text, "data-hb-field", field)


def field_texts(html_text, field):
    return [el.text.strip() for el in field_elements(html_text, field)]


def part_elements(html_text, part_id):
    return elements_with(html_text, "data-hb-part", part_id)


def source_text():
    require_script()
    return SCRIPT.read_text(encoding="utf-8")


def imported_modules():
    """script が import しているトップレベルモジュール名の集合。"""
    src = source_text()
    names = set()
    for m in re.finditer(r"^\s*import\s+([A-Za-z_][\w.]*)", src, re.M):
        names.add(m.group(1).split(".")[0])
    for m in re.finditer(r"^\s*from\s+([A-Za-z_][\w.]*)\s+import", src, re.M):
        names.add(m.group(1).split(".")[0])
    return names
