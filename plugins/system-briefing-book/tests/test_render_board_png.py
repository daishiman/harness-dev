"""render-board-png.mjs: ボードの静的検査・切り出しの順番・ブラウザでの検査と PNG / WebP 化。

ブラウザ (Chrome / Edge) を使うテストは、見つからない環境では skip する (needs_browser)。
"""
from __future__ import annotations

import json
import hashlib
from pathlib import Path

import pytest

from conftest import codes, needs_browser, node_eval, run_script

SCRIPT = "render-board-png"


def static_check(html: str) -> dict:
    return node_eval(
        'import { staticCheck } from "./render-board-png.mjs";\n'
        f"console.log(JSON.stringify(staticCheck({json.dumps(html)})));"
    )


def order(specs: list[dict], export_dir: Path, selected: tuple[str, ...] = ()) -> dict:
    """orderLevels と selectWithSources を通し、段・依存・ボードごとの検査コードを返す。"""
    return node_eval(
        'import { orderLevels, selectWithSources } from "./render-board-png.mjs";\n'
        f"const [specs, exportDir, selected] = {json.dumps([specs, str(export_dir), list(selected)])};\n"
        "const boards = specs.map((s) => ({ no: s.no, file: `${s.no}_x.html`, exports: s.exports ?? [], refs: s.refs ?? [],\n"
        "  errors: [], warnings: [], selected: selected.includes(s.no) }));\n"
        "const { levels, deps } = orderLevels(boards, exportDir);\n"
        "selectWithSources(boards, deps);\n"
        "const codes = (items) => items.map((i) => i.code);\n"
        "console.log(JSON.stringify({\n"
        "  levels: levels.map((level) => level.map((b) => b.no)),\n"
        "  deps: Object.fromEntries([...deps].map(([no, set]) => [no, [...set].sort()])),\n"
        "  boards: Object.fromEntries(boards.map((b) => [b.no, { errors: codes(b.errors), warnings: codes(b.warnings), selected: b.selected }])),\n"
        "}));"
    )


# --- 静的検査 -------------------------------------------------------------

@pytest.mark.parametrize("html, code", [
    ('<div style="color:#1747B5">x</div>', "RAW-COLOR"),
    ("<style>.a { background: rgb(0, 0, 0); }</style>", "RAW-COLOR"),
    ('<svg><rect fill="red"/></svg>', "RAW-COLOR"),
    ('<img src="https://example.com/a.png">', "EXTERNAL-REF"),
    ('<style>.a { background: url("//cdn.example.com/a.png"); }</style>', "EXTERNAL-REF"),
    ('<style>@import "x.css";</style>', "EXTERNAL-REF"),
    ("<h1>{{TITLE}}</h1>", "PLACEHOLDER"),
])
def test_static_check_finds(html: str, code: str) -> None:
    assert code in codes(static_check(html)["errors"])


def test_static_check_allows_tokens_and_comments() -> None:
    html = """<style>/* 色は #fff ではなく var を使う */ .a { color: var(--text-brand); border-color: var(--line); }</style>
<!-- 例: style="color:#000" や <img src="https://example.com/x.png"> や {{TITLE}} は数えない -->
<div style="left:12px;top:4px" class="mk">1</div><img src="assets/photo.png">"""
    assert static_check(html) == {"errors": [], "warnings": []}


def test_static_check_caps_repeated_colors() -> None:
    html = "".join(f'<i style="color:#00000{i % 10}">.</i>' for i in range(15))
    errors = static_check(html)["errors"]
    assert len(errors) == 11 and "ほかに 5 か所" in errors[-1]["message"]


# --- 切り出しの順番 ---------------------------------------------------------

def test_order_levels_puts_sources_first(tmp_path: Path) -> None:
    specs = [{"no": "00", "refs": ["s01-send"]}, {"no": "02", "exports": ["s01-send"]}]
    result = order(specs, tmp_path, selected=("00",))
    assert result["levels"] == [["02"], ["00"]]
    assert result["deps"] == {"00": ["02"], "02": []}
    assert result["boards"]["00"]["errors"] == [] and result["boards"]["02"]["errors"] == []
    assert result["boards"]["02"]["selected"], "--only 00 でも切り出し元の 02 を描く"


def test_order_levels_reports_problems(tmp_path: Path) -> None:
    specs = [{"no": "01", "exports": ["Bad_Name"], "refs": ["nowhere"]},
             {"no": "02", "exports": ["dup"]}, {"no": "03", "exports": ["dup"]}]
    boards = order(specs, tmp_path)["boards"]
    assert {"EXPORT-NAME", "EXPORT-UNKNOWN"} <= set(boards["01"]["errors"])
    assert "EXPORT-DUP" in boards["03"]["errors"] and boards["02"]["errors"] == []


def test_order_levels_orphan_png_is_warning(tmp_path: Path) -> None:
    (tmp_path / "old.png").write_bytes(b"x")
    board = order([{"no": "01", "refs": ["old"]}], tmp_path)["boards"]["01"]
    assert board["errors"] == [] and "EXPORT-ORPHAN" in board["warnings"]


def test_order_levels_detects_cycle(tmp_path: Path) -> None:
    specs = [{"no": "01", "exports": ["a"], "refs": ["b"]}, {"no": "02", "exports": ["b"], "refs": ["a"]}]
    result = order(specs, tmp_path)
    assert all("EXPORT-CYCLE" in result["boards"][no]["errors"] for no in ("01", "02"))
    assert sum(len(level) for level in result["levels"]) == 2, "輪になっても全ボードを検査に回す"


# --- ブラウザ探し ---------------------------------------------------------

def find_browser(explicit: str | None, env: dict, candidates: list[str]) -> str | None:
    """見つかればその場所、ToolMissing なら None。"""
    return node_eval(
        'import { findBrowser } from "./lib/browser-session.mjs";\n'
        'import { ToolMissing } from "./lib/cli-contract.mjs";\n'
        f"const [explicit, env, candidates] = {json.dumps([explicit, env, candidates])};\n"
        "try { console.log(JSON.stringify(findBrowser(explicit, { env, candidates }))); }\n"
        "catch (error) { if (!(error instanceof ToolMissing)) throw error; console.log('null'); }"
    )


def test_find_browser_order(tmp_path: Path) -> None:
    fake, other, missing = tmp_path / "chrome", tmp_path / "edge", str(tmp_path / "なし")
    fake.write_text("")
    other.write_text("")
    env = {"BRIEFING_BROWSER": str(other)}
    assert find_browser(str(fake), env, []) == str(fake), "--browser がいちばん強い"
    assert find_browser(None, env, [str(fake)]) == str(other), "次に環境変数"
    assert find_browser(None, {"BRIEFING_BROWSER": missing}, [str(fake)]) is None, "指定された場所に無ければ探し直さない"
    assert find_browser(None, {}, [missing, str(fake)]) == str(fake)
    assert find_browser(None, {}, []) is None


# --- CLI -----------------------------------------------------------------

def test_cli_usage_and_tool_errors(case: Path, tmp_path: Path) -> None:
    rc, out, _ = run_script(SCRIPT, "--dir", str(tmp_path / "なし"))
    assert rc == 2 and out["status"] == "usage-error"
    rc, _, _ = run_script(SCRIPT, "--dir", str(case), "--only", "99")
    assert rc == 2
    rc, _, _ = run_script(SCRIPT, "--dir", str(case), "--jobs", "0")
    assert rc == 2
    rc, out, _ = run_script(SCRIPT, "--dir", str(case), "--browser", str(tmp_path / "なし"))
    assert rc == 3 and out["status"] == "tool-missing"
    rc, out, _ = run_script(SCRIPT, "--dir", str(case), env={"BRIEFING_BROWSER": str(tmp_path / "なし")})
    assert rc == 3


# --- ブラウザで動かす -------------------------------------------------------

@pytest.fixture
def scaffolded(tmp_path: Path) -> Path:
    """雛形から作った 3 枚 (全体図 + スマホ 2 枚)。雛形の説明コメントには data-export の例が入っている。"""
    materials = tmp_path / "素材"
    materials.mkdir()
    rc, _, err = run_script("build-briefing-scaffold", "init", "--materials", str(materials),
                            "--title", "写真で記録", "--date", "2026-10-01")
    assert rc == 0, err
    base = materials / "打ち合わせ資料"
    briefing = json.loads((base / "briefing.json").read_text(encoding="utf-8"))
    briefing["pages"] = [
        {"no": "00", "file": "00_overview.html", "type": "overview", "title": "全体図", "reader": "発注側の責任者",
         "screens": [], "message": "写真を送るだけで一覧に入る"},
        {"no": "01", "file": "01_phone-send.html", "type": "phone", "title": "写真を送る", "reader": "現場の担当者",
         "screens": ["S01"], "message": "撮って送るだけ"},
        {"no": "02", "file": "02_phone-done.html", "type": "phone", "title": "送ったあと", "reader": "現場の担当者",
         "screens": ["S02"], "message": "送れたことがすぐわかる"},
    ]
    (base / "briefing.json").write_text(json.dumps(briefing, ensure_ascii=False), encoding="utf-8")
    rc, _, err = run_script("build-briefing-scaffold", "boards", "--dir", str(base))
    assert rc == 0, err
    return base


def written_files(base: Path) -> set[str]:
    """render が書く場所にあるファイル (PNG・WebP・切り出し・boards.json)。"""
    found = {p.name for p in base.glob("*.png")}
    for sub in ("_src/book", "_src/assets/export"):
        found |= {f"{sub}/{p.name}" for p in (base / sub).glob("*")} if (base / sub).is_dir() else set()
    if (base / "_check" / "boards.json").exists():
        found.add("_check/boards.json")
    return found


def edit_src(base: Path, file: str, old: str, new: str) -> None:
    path = base / "_src" / file
    text = path.read_text(encoding="utf-8")
    assert old in text, f"{file} に {old!r} がありません"
    path.write_text(text.replace(old, new, 1), encoding="utf-8")


@needs_browser
def test_templates_pass_check_and_write_nothing(scaffolded: Path) -> None:
    rc, out, err = run_script(SCRIPT, "--dir", str(scaffolded), "--check-only")
    assert rc == 0, err
    assert out["summary"] == {"errors": 0, "warnings": 0, "notices": 0, "boards": 3, "ok": 3, "warn": 0, "ng": 0, "png": 0}
    assert out["check"] is None
    assert written_files(scaffolded) == set(), "--check-only は PNG も WebP も _check も書かない"


@needs_browser
def test_broken_board_fails(scaffolded: Path) -> None:
    path = scaffolded / "_src" / "01_phone-send.html"
    text = path.read_text(encoding="utf-8")
    text = text.replace("<h1>写真を送る</h1>", "").replace('<div class="phone">', '<div class="phone" style="background:#fff">')
    path.write_text(text, encoding="utf-8")
    rc, out, _ = run_script(SCRIPT, "--dir", str(scaffolded), "--check-only", "--only", "01")
    assert rc == 1
    (entry,) = out["boards"]
    assert entry["status"] == "ng" and {"RAW-COLOR", "NO-TITLE"} <= codes(entry["errors"])


@needs_browser
def test_kicker_same_as_title_warns(scaffolded: Path) -> None:
    path = scaffolded / "_src" / "01_phone-send.html"
    text = path.read_text(encoding="utf-8")
    assert '<div class="kicker">画面 1 / 2 ・ スマホ</div>' in text
    path.write_text(text.replace('<div class="kicker">画面 1 / 2 ・ スマホ</div>', '<div class="kicker">写真を 送る</div>'),
                    encoding="utf-8")
    rc, out, _ = run_script(SCRIPT, "--dir", str(scaffolded), "--check-only", "--only", "01")
    assert rc == 1, "render は warn だけでも止める (見た目の崩れを最初の版に残さない)"
    (entry,) = out["boards"]
    assert entry["status"] == "warn" and codes(entry["warnings"]) == {"KICKER-SAME"} and entry["errors"] == []
    rc, out, _ = run_script(SCRIPT, "--dir", str(scaffolded), "--check-only", "--only", "01", "--allow-warn")
    assert rc == 0, "独立レビューの検査だけなら --allow-warn で通す"


@needs_browser
def test_small_font_is_measured_after_transform(scaffolded: Path) -> None:
    edit_src(scaffolded, "01_phone-send.html", '<div class="hint">',
             '<div class="hint" style="transform:scale(0.5);transform-origin:left top">')
    rc, out, _ = run_script(SCRIPT, "--dir", str(scaffolded), "--check-only", "--only", "01")
    assert rc == 1
    (entry,) = out["boards"]
    hits = [e["message"] for e in entry["errors"] if e["code"] == "FONT-SMALL"]
    assert hits and "6.5px" in hits[0], "transform で縮めた見た目の px で見る"


@needs_browser
def test_volume_is_only_reported(scaffolded: Path) -> None:
    extra = '<li data-kind="how"><b>補足 5</b></li><li data-kind="how"><b>補足 6</b></li>'
    long_text = '<div data-clip-ok style="height:16px;overflow:hidden">' + "あ" * 1000 + "</div>"
    edit_src(scaffolded, "01_phone-send.html", "</ol>", f"{extra}</ol>\n      {long_text}")
    rc, out, err = run_script(SCRIPT, "--dir", str(scaffolded), "--check-only", "--only", "01")
    assert rc == 0, "量 (字数・注記の数) は報告だけで止めない"
    (entry,) = out["boards"]
    assert entry["status"] == "ok" and entry["errors"] == [] and entry["warnings"] == []
    assert codes(entry["notices"]) == {"TEXT-LONG", "NOTES-MANY"}
    assert out["summary"]["notices"] == 2
    assert "note  TEXT-LONG _src/01_phone-send.html" in err


@needs_browser
def test_sample_flag_follows_data_policy(scaffolded: Path) -> None:
    edit_src(scaffolded, "01_phone-send.html", '<div class="meta">写真で記録</div>',
             '<div class="meta">写真で記録<br><span class="sample-flag">画面の中の名前と値は例です</span></div>')
    path = scaffolded / "briefing.json"
    briefing = json.loads(path.read_text(encoding="utf-8"))
    found = {}
    for policy in ("source", "masked", None):
        briefing.pop("data_policy", None)
        if policy is not None:
            briefing["data_policy"] = policy
        path.write_text(json.dumps(briefing, ensure_ascii=False), encoding="utf-8")
        rc, out, err = run_script(SCRIPT, "--dir", str(scaffolded), "--check-only", "--only", "01", "02", "--allow-warn")
        assert rc == 0, err
        found[policy] = {b["no"]: codes(b["warnings"]) & {"NO-SAMPLE-FLAG", "SAMPLE-FLAG-UNNEEDED"} for b in out["boards"]}
    assert found == {
        "source": {"01": {"SAMPLE-FLAG-UNNEEDED"}, "02": set()},
        "masked": {"01": set(), "02": {"NO-SAMPLE-FLAG"}},
        None: {"01": set(), "02": set()},
    }, "札は masked のときだけ置く。data_policy が無ければ見ない"


IMAGE_FACTS_JS = """
import { readFileSync } from "node:fs";
import { findBrowser, launchBrowser } from "./lib/browser-session.mjs";
import { imageSize } from "./lib/image-size.mjs";
const session = await launchBrowser(findBrowser());
try {
  const page = await session.newPage({ width: 800, height: 600 });
  const facts = [];
  for (const file of FILES) {
    const buffer = readFileSync(file);
    const size = imageSize(buffer);
    const url = `data:image/${size.format};base64,${buffer.toString("base64")}`;
    const green = await page.evaluate(`(async () => {
      const bitmap = await createImageBitmap(await (await fetch(${JSON.stringify(url)})).blob());
      const canvas = new OffscreenCanvas(bitmap.width, bitmap.height);
      const context = canvas.getContext("2d");
      context.drawImage(bitmap, 0, 0);
      const data = context.getImageData(0, 0, bitmap.width, bitmap.height).data;
      let count = 0;
      for (let i = 0; i < data.length; i += 4) if (data[i + 1] > 200 && data[i] < 80 && data[i + 2] < 80) count++;
      return count;
    })()`);
    facts.push({ format: size.format, width: size.width, height: size.height, green });
  }
  console.log(JSON.stringify(facts));
} finally {
  await session.close();
}
"""


def image_facts(*files: Path) -> list[dict]:
    """画像ごとに {format, width, height, green} を返す。green ははっきりした緑の画素の数。

    Pillow を使わず、ブラウザで画像を読んで数える (needs_browser のテストからだけ呼ぶ)。
    """
    code = IMAGE_FACTS_JS.replace("FILES", json.dumps([str(f) for f in files]), 1)
    return node_eval(code, timeout=180)


@needs_browser
def test_render_png_webp_and_export(scaffolded: Path) -> None:
    path = scaffolded / "_src" / "01_phone-send.html"
    path.write_text(path.read_text(encoding="utf-8").replace(
        '<div class="phone">', '<div class="phone" data-export="s01-send">'), encoding="utf-8")
    # 番号の印 (.mk) をはっきりした緑にして、切り出しに写っていないことを数えて確かめる
    with (scaffolded / "_src" / "tokens.css").open("a", encoding="utf-8") as handle:
        handle.write("\n:root { --anno: #00ff00; --anno-ink: #00ff00; --anno-ring: #00ff00; }\n")
    rc, out, err = run_script(SCRIPT, "--dir", str(scaffolded), "--only", "01")
    assert rc == 0, err
    (entry,) = out["boards"]
    assert entry["png"] == "01_phone-send.png" and entry["webp"] == "_src/book/01_phone-send.webp"
    assert entry["exports"] == ["s01-send"]

    png = scaffolded / "01_phone-send.png"
    webp = scaffolded / "_src" / "book" / "01_phone-send.webp"
    export = scaffolded / "_src" / "assets" / "export" / "s01-send.png"
    board, book, crop = image_facts(png, webp, export)
    assert (board["format"], board["width"], board["height"]) == ("png", 3360, 2100)
    assert (book["format"], book["width"], book["height"]) == ("webp", 3360, 2100)
    assert crop["width"] == 520
    assert webp.stat().st_mtime >= png.stat().st_mtime, "WebP は PNG の後に書く"
    assert board["green"] > 100, "ボード本体の PNG には番号の印を残す"
    assert crop["green"] == 0, "切り出しには番号の印を写さない"

    report = json.loads((scaffolded / "_check" / "boards.json").read_text(encoding="utf-8"))
    assert [b["no"] for b in report["boards"]] == ["01"], "--only で選ばなかったボードは前回の結果が無ければ載らない"
    assert report["boards"][0]["mode"] == "render" and len(report["boards"][0]["html_sha256"]) == 64
    first = report["boards"][0]
    assert first["png_sha256"] == hashlib.sha256(png.read_bytes()).hexdigest()
    assert first["webp_sha256"] == hashlib.sha256(webp.read_bytes()).hexdigest()
    assert first["dependencies"]["_src/01_phone-send.html"] == first["html_sha256"]
    assert "_src/tokens.css" in first["dependencies"] and "_src/common.css" in first["dependencies"]
    assert first["notes"] == 4 and first["font_px_min"] >= 10
    assert first["device_chars"] > 0 and first["text_chars"] > 0, "端末の絵の中の字数は説明の字数と分けて数える"

    rc, _, err = run_script(SCRIPT, "--dir", str(scaffolded), "--only", "02")
    assert rc == 0, err
    report = json.loads((scaffolded / "_check" / "boards.json").read_text(encoding="utf-8"))
    assert [b["no"] for b in report["boards"]] == ["01", "02"], "前回の 01 の結果は残す"


@pytest.mark.parametrize("html", [
    '<img srcset="assets/a.png 1x, https://example.com/b.png 2x">',
    '<img srcset="data:image/png;base64,AAAA 1x, https://example.com/b.png 2x">',
    '<img src=https://example.com/a.png>',
    '<style>.x{background:image-set("https://example.com/a.png" 1x)}</style>',
    '<div style="background:url(&quot;https://example.com/a.png&quot;)"></div>',
])
def test_reference_scanner_covers_real_resource_syntax(html: str) -> None:
    assert "EXTERNAL-REF" in codes(static_check(html)["errors"])
    refs = node_eval('import { scanRefs } from "./build-briefing-book.mjs";\n'
                     f'console.log(JSON.stringify(scanRefs({json.dumps(html)})));')
    assert "EXTERNAL-REF" in codes(refs)


def test_reference_scanner_ignores_comments_strings_and_examples() -> None:
    html = '''<!-- <img src=https://example.com/a.png> -->
    <pre>&lt;img src="https://example.com/a.png"&gt; url(https://example.com/x)</pre>
    <script>const s = '<img src="https://example.com/a.png">';</script>
    <style>/* url(https://example.com/a.png) */ .x::after{content:'url(https://example.com/x)'}</style>'''
    assert static_check(html)["errors"] == []
    refs = node_eval('import { scanRefs } from "./build-briefing-book.mjs";\n'
                     f'console.log(JSON.stringify(scanRefs({json.dumps(html)})));')
    assert refs == []


@needs_browser
@pytest.mark.parametrize("variant, expected", [("list", False), ("anchor", True), ("duplicate", True), ("orphan-mark", True)])
def test_list_only_note_numbers_and_marker_contract(scaffolded: Path, variant: str, expected: bool) -> None:
    # A numbered decisions list has no screen locations. Other marker errors must remain errors.
    board = scaffolded / "_src/00_overview.html"
    anchor = '<div class="anchor"></div>' if variant == "anchor" else ''
    if variant == "orphan-mark":
        anchor = '<div class="anchor"><i class="mk">9</i></div>'
    second = "1" if variant == "duplicate" else "2"
    board.write_text(f'''<!doctype html><html><head><link rel="stylesheet" href="tokens.css">
<link rel="stylesheet" href="common.css"></head><body>
<div class="board" data-board="00" data-type="decisions">
<header class="board-head"><div class="kicker">打ち合わせ</div><h1>決めること</h1><p class="lead">順に確認します</p></header>
{anchor}<aside class="notes"><ol class="marks">
<li data-mark="1" data-kind="ask"><b>確認事項</b></li>
<li data-mark="{second}" data-kind="ask"><b>次の事項</b></li>
</ol></aside></div></body></html>''', encoding="utf-8")
    config = scaffolded / "briefing.json"
    briefing = json.loads(config.read_text())
    briefing["pages"][0]["type"] = "decisions"
    config.write_text(json.dumps(briefing, ensure_ascii=False), encoding="utf-8")
    rc, out, err = run_script(SCRIPT, "--dir", str(scaffolded), "--check-only", "--only", "00", "--allow-warn")
    assert rc in (0, 1), err
    errors = out["boards"][0]["errors"]
    assert ("MARK-MISMATCH" in codes(errors)) is expected, errors
    assert "BOARD-ATTR" not in codes(errors), errors


@pytest.mark.parametrize('css', [None, ':root { --text: #123456; }'])
def test_bad_tokens_stop_before_browser_and_preserve_images(case: Path, css: str | None) -> None:
    tokens = case / '_src' / 'tokens.css'
    if css is None:
        tokens.unlink()
    else:
        tokens.write_text(css, encoding='utf-8')
    image = case / '00_overview.png'
    image.write_bytes(b'previous image')
    rc, out, _ = run_script(SCRIPT, '--dir', str(case), '--browser', '/missing/browser')
    assert rc == 1 and out['status'] == 'ng'
    code = 'TOKENS-MISSING' if css is None else 'TOKENS-INVALID'
    assert any(code in codes(board['errors']) for board in out['boards'])
    assert image.read_bytes() == b'previous image'
    assert not (case / '02_phone-send.png').exists()
