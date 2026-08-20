"""テンプレートの本文キーと validate-structure.js の表がずれていないことを見る。

vendor/scripts/templates/ には短縮名 (message.html.tpl) と長い名
(slide-message.html.tpl) のテンプレートが対で置かれていて、render-slide.cjs の
loadTemplate はまず slideType そのままの名前を探し、無ければ TYPE_ALIASES を引く。
短縮名の slideType を書いた旧世代の deck は短縮名テンプレートへ落ちるので、どちらも
現役であり、片方は残骸ではない。ただし対の間で本文キーの名前が違うものがあり
(message は {{message}} / slide-message は {{main}} を読む)、短縮名の書き方のまま
slideType だけ長い名にすると「検証は通るのに本文が空で出る」。

このファイルは 3 つを固定する。
 (1) validate-structure.js の TEMPLATE_BODY_KEYS が実際に本文を出すキーであること
     (表の側のキーだけを与えた deck を render し、値が HTML に出ることで確かめる)。
 (2) slide-message に content.message しか無い deck が検証で落ちること (回帰)。
 (3) 短縮名テンプレートが対で残っていること (レガシーは削除でなく分離)。
"""

from __future__ import annotations

import ast
import json
import re
import subprocess
from pathlib import Path

import pytest

PLUGIN_ROOT = Path(__file__).resolve().parent.parent
SCRIPTS = PLUGIN_ROOT / "vendor" / "scripts"
TEMPLATES = SCRIPTS / "templates"
VALIDATE = SCRIPTS / "validate-structure.js"
RENDER = SCRIPTS / "render-slide.cjs"


def _body_keys_map() -> dict[str, list[str]]:
    """validate-structure.js から TEMPLATE_BODY_KEYS を読む (CLI なので export が無い)。"""
    src = VALIDATE.read_text(encoding="utf-8")
    m = re.search(r"const TEMPLATE_BODY_KEYS = \{(.*?)\n\};", src, re.S)
    assert m, "TEMPLATE_BODY_KEYS が validate-structure.js に見つからない"
    body = re.sub(r"//[^\n]*", "", m.group(1))
    out: dict[str, list[str]] = {}
    for entry in re.finditer(r'"([a-z0-9-]+)"\s*:\s*(\[[^\]]*\])', body):
        out[entry.group(1)] = ast.literal_eval(entry.group(2).replace('"', "'"))
    assert out, "TEMPLATE_BODY_KEYS を 1 件も読めなかった"
    return out


BODY_KEYS = _body_keys_map()

# 表の各型について「その型のテンプレートが本文として描く値」を 1 つだけ入れた content。
# 目印は 3 文字にしてある。SVG 図解のラベルは長いと 2 行へ折り返されて <text> が
# 分割されるため、折り返さない長さでなければ HTML 中の一致で確かめられない。
PROBE_CONTENT = {
    "slide-message": lambda mk: {"main": mk},
    "slide-title": lambda mk: {"title": mk, "subtitle": "sub"},
    "slide-hero": lambda mk: {"title": mk, "subtitle": "sub"},
    "slide-quote": lambda mk: {"title": "title", "quote": mk, "author": "author"},
    "slide-highlight": lambda mk: {"title": "title", "value": mk, "label": "label"},
    "slide-list": lambda mk: {"title": "title", "items": [{"label": mk, "icon": "fa-star"}]},
    "slide-icon-grid": lambda mk: {
        "title": "title", "columns": 3, "items": [{"label": mk, "icon": "fa-star"}]
    },
    "slide-grid": lambda mk: {
        "title": "title", "cards": [{"title": mk, "desc": "desc", "icon": "fa-star"}]
    },
    "slide-table": lambda mk: {"title": "title", "headers": ["h1"], "rows": [[mk]]},
    "slide-timeline": lambda mk: {
        "title": "title", "events": [{"date": "2026", "label": mk, "desc": "desc"}]
    },
    "slide-process": lambda mk: {
        "title": "title", "steps": [{"number": 1, "label": mk, "desc": "desc"}]
    },
    "slide-compare": lambda mk: {
        "title": "title",
        "left": {"title": mk, "items": ["a"]},
        "right": {"title": "right", "items": ["b"]},
    },
    "slide-code": lambda mk: {"title": "title", "lang": "js", "code": mk},
    "slide-code-compare": lambda mk: {
        "title": "title",
        "before": {"label": "b", "lang": "js", "code": mk},
        "after": {"label": "a", "lang": "js", "code": "y"},
    },
    "slide-flow": lambda mk: {"title": "title", "steps": [{"label": mk}, {"label": "zz"}]},
    "slide-circle": lambda mk: {
        "title": "title", "steps": [{"label": mk}, {"label": "zz"}, {"label": "ww"}]
    },
    "slide-pyramid": lambda mk: {"title": "title", "levels": [{"label": mk}, {"label": "zz"}]},
}


def _deck(slides: list[dict]) -> dict:
    return {
        "title": "body key probe",
        "meta": {"title": "body key probe", "schemaVersion": "8.0.0"},
        "theme": {
            "name": "kanagawa-lotus",
            "mode": "light",
            "accentColors": ["#3B7DD8"],
            "fontScale": 1.3,
        },
        "slides": slides,
    }


def _write(path: Path, deck: dict) -> Path:
    path.write_text(json.dumps(deck, ensure_ascii=False, indent=2), encoding="utf-8")
    return path


# --- (1) 表のキーが本当に本文を描くキーであること -------------------------------

def test_body_keys_map_only_lists_existing_templates():
    for slide_type in BODY_KEYS:
        assert (TEMPLATES / f"{slide_type}.html.tpl").exists(), slide_type


def test_body_keys_map_covers_probe_fixture():
    # 表を増やしたら fixture も足す。片方だけ増えると (2) の検査が素通りする。
    assert set(BODY_KEYS) == set(PROBE_CONTENT)


def test_mapped_body_key_actually_renders(tmp_path):
    types = sorted(BODY_KEYS)
    marks = {t: f"M{i:02d}z" for i, t in enumerate(types)}
    slides = [
        {"slideType": t, "section": "main", "content": PROBE_CONTENT[t](marks[t])}
        for t in types
    ]
    src = _write(tmp_path / "probe.json", _deck(slides))
    out = tmp_path / "out"
    proc = subprocess.run(
        ["node", str(RENDER), str(src), "--out", str(out)],
        capture_output=True, text=True,
    )
    assert proc.returncode == 0, proc.stdout + proc.stderr
    html = (out / "index.html").read_text(encoding="utf-8")
    missing = [t for t in types if marks[t] not in html]
    assert missing == [], (
        "TEMPLATE_BODY_KEYS が挙げたキーを入れても本文が出ない型がある "
        "(テンプレート側のキー名が変わった疑い): " + ", ".join(missing)
    )
    # 目印は当該の面の中に出ていること (別の面へ紛れ込んでいない)
    for t in types:
        seg = html.split(f'data-type="{t}"', 1)
        assert len(seg) == 2, f"{t} の面が HTML に無い"
        assert marks[t] in seg[1][:20000], f"{t} の目印が当該面の中に無い"


# --- (2) 回帰: 旧キーだけの slide-message は検証で落ちる -------------------------

def _validate(path: Path) -> subprocess.CompletedProcess:
    # 終了コードは「落ちたか」を表さない。FAIL が 0 でも、判定する実行体が無い規則
    # (未検査) が 1 つでもあれば exit 2 になる。ここが見たいのは本文キーの受理可否
    # だけなので、合否は report の counts.failed で見る。exit code を代理に使うと、
    # 陽性側は未検査が出た瞬間に全部赤くなり、陰性側 (!= 0) は未検査だけで通って
    # しまい、どちらも判定力を失う。未検査の件数そのものは
    # tests/test_validate_structure_unchecked.py が別に固定している。
    report = path.with_name(path.name + ".report.json")
    proc = subprocess.run(
        ["node", str(VALIDATE), str(path), "--report", str(report)],
        capture_output=True, text=True, check=False,
    )
    assert report.exists(), "--report が出力されなかった\n" + proc.stdout + proc.stderr
    proc.failed = json.loads(report.read_text(encoding="utf-8"))["counts"]["failed"]
    return proc


def test_slide_message_with_legacy_key_only_is_rejected(tmp_path):
    src = _write(tmp_path / "legacy.json", _deck([
        {"slideType": "slide-title", "section": "main",
         "content": {"title": "タイトル", "subtitle": "副題"}},
        {"slideType": "slide-message", "section": "main",
         "content": {"message": "旧キーだけの本文"}},
    ]))
    proc = _validate(src)
    assert proc.failed > 0
    assert "content.main" in proc.stdout
    assert "V-044 / SR-16-01" in proc.stdout


def test_slide_message_with_template_key_is_accepted(tmp_path):
    src = _write(tmp_path / "ok.json", _deck([
        {"slideType": "slide-title", "section": "main",
         "content": {"title": "タイトル", "subtitle": "副題"}},
        {"slideType": "slide-message", "section": "main",
         "content": {"main": "正しいキーの本文"}},
    ]))
    proc = _validate(src)
    assert proc.failed == 0, proc.stdout + proc.stderr


# --- (3) 短縮名テンプレートは対で残す (削除でなく分離) ---------------------------

@pytest.mark.parametrize("short_name", sorted(
    p.name[: -len(".html.tpl")]
    for p in TEMPLATES.glob("*.html.tpl")
    if (TEMPLATES / f"slide-{p.name}").exists()
))
def test_legacy_short_template_is_kept(short_name):
    # 旧世代の deck は slideType に短縮名を書く。loadTemplate はその名前を先に引く
    # ので、短縮名テンプレートを消すとその deck は render できなくなる。
    assert (TEMPLATES / f"{short_name}.html.tpl").exists()
    assert (TEMPLATES / f"slide-{short_name}.html.tpl").exists()


# --- (4) 誤検出回帰: 本文キーだけ持つ面が「テキストコンテンツ欠落」で落ちない -------
#
# validate-structure.js の型を見ない hasText は、以前 main/title/message/items/steps/rows
# だけを本文と認めていた。そのため content に quote しか無い slide-quote、value しか
# 無い slide-highlight、cards しか無い slide-grid などが、テンプレートが読む本文を
# 正しく持っているのに落ちていた (実測 17 型中 9 型)。受理集合を TEMPLATE_BODY_KEYS
# から導出することで塞いだ。列挙を再び手書きへ戻すとここが赤くなる。


def _body_only_content(slide_type: str, mark: str) -> dict:
    content = dict(PROBE_CONTENT[slide_type](mark))
    if "title" not in BODY_KEYS[slide_type]:
        content.pop("title", None)
    return content


@pytest.mark.parametrize("slide_type", sorted(BODY_KEYS))
def test_body_key_only_slide_is_accepted(slide_type, tmp_path):
    src = _write(tmp_path / f"{slide_type}.json", _deck([
        {"slideType": slide_type, "section": "main",
         "content": _body_only_content(slide_type, "Mxxz")},
    ]))
    proc = _validate(src)
    assert proc.failed == 0, (
        f"{slide_type}: テンプレートが読む本文キーだけを持つ面が落ちた\n"
        + proc.stdout + proc.stderr
    )


@pytest.mark.parametrize("slide_type,empty", [
    ("slide-message", {"main": "   "}),
    ("slide-quote", {"quote": ""}),
    ("slide-highlight", {"value": ""}),
    ("slide-list", {"items": []}),
    ("slide-grid", {"cards": []}),
    ("slide-code", {"code": ""}),
])
def test_empty_body_slide_is_still_rejected(slide_type, empty, tmp_path):
    # 陰性対照。受理集合を広げた副作用で「本当に空の面」まで通るようになっていないこと。
    src = _write(tmp_path / f"empty-{slide_type}.json", _deck([
        {"slideType": slide_type, "section": "main", "content": empty},
    ]))
    proc = _validate(src)
    assert proc.failed > 0, f"{slide_type}: 本文が空の面が受理された\n{proc.stdout}"


def test_generic_body_keys_are_derived_from_the_map():
    # 受理集合を手書きの列挙へ戻すと (4) の回帰が再発する。導出であることを固定する。
    src = VALIDATE.read_text(encoding="utf-8")
    m = re.search(r"const GENERIC_BODY_KEYS = \[(.*?)\];", src, re.S)
    assert m, "GENERIC_BODY_KEYS が見つからない"
    assert "Object.values(TEMPLATE_BODY_KEYS)" in m.group(1), (
        "GENERIC_BODY_KEYS が TEMPLATE_BODY_KEYS から導出されていない"
    )
