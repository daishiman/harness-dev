"""build-briefing-book.mjs: 文書とボードの画像を 1 つの HTML にまとめる。問題があれば HTML を書かない。"""
from __future__ import annotations

import hashlib
import json
import os
import re
import struct
from pathlib import Path

from conftest import TITLE, codes, make_case, needs_browser, node_eval, run_script, write_png

SCRIPT = "build-briefing-book"
OUT_NAME = f"{TITLE}_打ち合わせ資料.html"
STEMS = ("00_overview", "02_phone-send", "03_pc-list")


def build(base: Path, *extra: str, env: dict | None = None):
    return run_script(SCRIPT, "--dir", str(base), *extra, env=env)


def append(path: Path, text: str) -> None:
    path.write_text(path.read_text(encoding="utf-8") + text, encoding="utf-8")


def write_webp(path: Path, size: tuple[int, int] = (3360, 2100)) -> Path:
    """頭だけの WebP (VP8L) を書く。まとめは中身を描かずに埋め込むので、形式と大きさが読めれば足りる。"""
    width, height = size
    bits = (width - 1) | ((height - 1) << 14)
    payload = b"\x2f" + struct.pack("<I", bits) + b"\x00" * 11
    chunk = b"VP8L" + struct.pack("<I", len(payload)) + payload
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(b"RIFF" + struct.pack("<I", 4 + len(chunk)) + b"WEBP" + chunk)
    return path


def with_webp(base: Path) -> None:
    """render-board-png.mjs と同じく、PNG のあとに _src/book/NN_*.webp を書く。"""
    for stem in STEMS:
        write_webp(base / "_src" / "book" / f"{stem}.webp")


def test_builds_one_self_contained_file(case_with_png: Path) -> None:
    rc, out, err = build(case_with_png)
    assert rc == 0, err
    html_path = case_with_png / OUT_NAME
    assert out["written"] is True and Path(out["out"]) == html_path
    html = html_path.read_text(encoding="utf-8")
    for pid in ("p-cover", "b00", "b02", "b03", "p-req", "p-spec"):
        assert f'id="{pid}"' in html, pid
    assert 'id="p-hear"' not in html, "ヒアリング記録は既定では載せない"
    assert 'id="p-chg"' not in html, "変更点が見出しだけならページを作らない"
    assert "{{" not in html
    assert not re.search(r"""(?:src|href)\s*=\s*["'](?:https?:)?//""", html)
    assert "http://" not in html and "https://" not in html
    assert html.count('<figure class="shot"') == 3
    assert "Q01" in html and "決めること" in html, "注記の文字も載る"
    assert out["version"] == "v0.1" and out["summary"]["boards"] == 3
    saved = json.loads((case_with_png / "_check" / "book.json").read_text(encoding="utf-8"))
    assert saved["status"] == "warn" and saved["written"] is True
    assert "IMAGE-UNVERIFIED" in codes(saved["warnings"])


def test_cover_counts_only_open_questions(case_with_png: Path) -> None:
    req = case_with_png / "要件定義.md"
    text = req.read_text(encoding="utf-8")
    req.write_text(text.replace("| 30 日分 | 発注側の責任者 |", "| 30 日分 | 決定 (v0.1) |"), encoding="utf-8")
    rc, _, err = build(case_with_png)
    assert rc == 0, err
    html = (case_with_png / OUT_NAME).read_text(encoding="utf-8")
    assert "決めること <b>1</b> 件" in html, "「決定」の行は数えない"


def test_cover_when_all_questions_are_decided(case_with_png: Path) -> None:
    req = case_with_png / "要件定義.md"
    text = req.read_text(encoding="utf-8")
    text = text.replace("| 日付・相手先・数・メモ | 現場の担当者 |", "| 日付・相手先・数・メモ | 決定 (v0.1) |")
    req.write_text(text.replace("| 30 日分 | 発注側の責任者 |", "| 30 日分 | 決定 (v0.1) |"), encoding="utf-8")
    rc, _, err = build(case_with_png)
    assert rc == 0, err
    html = (case_with_png / OUT_NAME).read_text(encoding="utf-8")
    assert "決めること <b>0</b> 件" in html
    assert "すべて決まりました" in html and "0 件あります" not in html, "0 件のときは数の文を出さない"


def test_cover_data_note_follows_data_policy(case_with_png: Path) -> None:
    path = case_with_png / "briefing.json"
    briefing = json.loads(path.read_text(encoding="utf-8"))
    source = "素材の名前と数字をそのまま載せています。素材をくれた方と、作る側の中だけで扱ってください。"
    masked = "ボードの画面の中の名前と値は例です。"
    for policy, note, other in (("source", source, masked), ("masked", masked, source), (None, source, masked)):
        briefing.pop("data_policy", None)
        if policy is not None:
            briefing["data_policy"] = policy
        path.write_text(json.dumps(briefing, ensure_ascii=False), encoding="utf-8")
        rc, _, err = build(case_with_png)
        assert rc == 0, err
        html = (case_with_png / OUT_NAME).read_text(encoding="utf-8")
        assert f'<p class="sub">{note}</p>' in html and other not in html, f"data_policy={policy} (無ければ source の文)"


def test_embeds_webp_when_render_wrote_it(case_with_png: Path) -> None:
    with_webp(case_with_png)
    rc, out, err = build(case_with_png)
    assert rc == 0, err
    html = (case_with_png / OUT_NAME).read_text(encoding="utf-8")
    assert html.count("data:image/webp;base64,") == 3 and "data:image/png" not in html
    assert out["image_format"] == "webp"
    assert {b["image"] for b in out["boards"]} == {f"_src/book/{s}.webp" for s in STEMS}
    assert not codes(out["warnings"]) & {"WEBP-MISSING", "WEBP-OLD", "WEBP-BROKEN"}


def test_without_webp_embeds_png_and_warns(case_with_png: Path) -> None:
    rc, out, err = build(case_with_png)
    assert rc == 0, err
    html = (case_with_png / OUT_NAME).read_text(encoding="utf-8")
    assert html.count("data:image/png;base64,") == 3
    assert out["image_format"] == "png"
    assert [w["file"] for w in out["warnings"] if w["code"] == "WEBP-MISSING"] == [f"_src/book/{s}.webp" for s in STEMS]


def test_old_or_broken_webp_falls_back_to_png(case_with_png: Path) -> None:
    with_webp(case_with_png)
    old = case_with_png / "_src" / "book" / "02_phone-send.webp"
    earlier = (case_with_png / "02_phone-send.png").stat().st_mtime - 60
    os.utime(old, (earlier, earlier))
    (case_with_png / "_src" / "book" / "03_pc-list.webp").write_bytes(b"not a webp")
    rc, out, err = build(case_with_png)
    assert rc == 0, err
    assert {"WEBP-OLD", "WEBP-BROKEN"} <= codes(out["warnings"])
    assert out["image_format"] == "mixed"
    formats = {b["no"]: b["image_format"] for b in out["boards"]}
    assert formats == {"00": "webp", "02": "png", "03": "png"}


def test_png_size_is_checked_from_header(case_with_png: Path) -> None:
    write_png(case_with_png / "00_overview.png", size=(1680, 1050))
    rc, out, _ = build(case_with_png)
    assert rc == 1 and "PNG-SIZE" in codes(out["errors"]) and not out["written"]
    (case_with_png / "02_phone-send.png").write_bytes(b"not a png")
    rc, out, _ = build(case_with_png)
    assert rc == 1 and "PNG-READ" in codes(out["errors"])


def test_version_mismatch_writes_nothing(tmp_path: Path) -> None:
    base = make_case(tmp_path, pngs=True)
    spec = base / "仕様書.md"
    spec.write_text(spec.read_text(encoding="utf-8").replace("版: v0.1", "版: v0.2"), encoding="utf-8")
    rc, out, _ = build(base)
    assert rc == 1
    assert "VERSION-MISMATCH" in codes(out["errors"])
    assert out["written"] is False and not (base / OUT_NAME).exists()
    assert json.loads((base / "_check" / "book.json").read_text(encoding="utf-8"))["written"] is False


def test_stale_png(case_with_png: Path) -> None:
    board = case_with_png / "_src" / "02_phone-send.html"
    later = (case_with_png / "02_phone-send.png").stat().st_mtime + 60
    os.utime(board, (later, later))
    rc, out, _ = build(case_with_png)
    assert rc == 1 and "STALE-PNG" in codes(out["errors"])
    rc, out, _ = build(case_with_png, "--allow-stale")
    assert rc == 0 and "STALE-PNG" in codes(out["warnings"])


def test_stale_when_shared_css_changes(case_with_png: Path) -> None:
    css = case_with_png / "_src" / "common.css"
    later = (case_with_png / "00_overview.png").stat().st_mtime + 60
    os.utime(css, (later, later))
    rc, out, _ = build(case_with_png)
    assert rc == 1
    assert len([e for e in out["errors"] if e["code"] == "STALE-PNG"]) == 3


def test_missing_png_is_error_even_with_allow_stale(case: Path) -> None:
    rc, out, _ = build(case, "--allow-stale")
    assert rc == 1
    assert "PNG-MISSING" in codes(out["errors"])
    assert not (case / OUT_NAME).exists()


def test_markdown_link_stays_text(case_with_png: Path) -> None:
    append(case_with_png / "要件定義.md", "\n参考: [説明](https://example.com/x) と ![図](https://example.com/a.png)\n")
    rc, out, err = build(case_with_png)
    assert rc == 0, err
    html = (case_with_png / OUT_NAME).read_text(encoding="utf-8")
    assert "参考: 説明 と 図" in html, "リンクと画像は文字だけ残す"
    assert "example.com" not in html and out["summary"]["external"] == 0


def test_external_import_in_tokens(case_with_png: Path) -> None:
    append(case_with_png / "_src" / "tokens.css", '@import url("https://fonts.example.com/a.css");\n')
    rc, out, _ = build(case_with_png, "--allow-stale")
    assert rc == 1 and "EXTERNAL-REF" in codes(out["errors"])
    assert out["summary"]["external"] >= 1 and not (case_with_png / OUT_NAME).exists()


def test_failed_board_check_blocks(case_with_png: Path) -> None:
    def sha(name: str) -> str:
        return hashlib.sha256((case_with_png / "_src" / name).read_bytes()).hexdigest()

    report = {"boards": [
        {"no": "00", "file": "00_overview.html", "status": "ok", "html_sha256": sha("00_overview.html"), "errors": []},
        {"no": "02", "file": "02_phone-send.html", "status": "ng", "html_sha256": sha("02_phone-send.html"),
         "errors": [{"code": "CLIPPED"}]},
        {"no": "03", "file": "03_pc-list.html", "status": "ok", "html_sha256": "0" * 64, "errors": []},
    ]}
    (case_with_png / "_check" / "boards.json").write_text(json.dumps(report), encoding="utf-8")
    rc, out, _ = build(case_with_png)
    assert rc == 1
    assert "BOARD-CHECK-NG" in codes(out["errors"])
    assert "BOARD-CHECK-OLD" in codes(out["warnings"]), "検査のあとで変わったボードは warn"


def test_hearing_and_changes_pages(case_with_png: Path) -> None:
    briefing_path = case_with_png / "briefing.json"
    briefing = json.loads(briefing_path.read_text(encoding="utf-8"))
    briefing["book"]["include_hearing"] = True
    briefing_path.write_text(json.dumps(briefing, ensure_ascii=False), encoding="utf-8")
    append(case_with_png / "変更点.md", "\n## v0.1 (2026-10-01)\n- 最初の版\n")
    rc, _, err = build(case_with_png)
    assert rc == 0, err
    html = (case_with_png / OUT_NAME).read_text(encoding="utf-8")
    assert 'id="p-hear"' in html and 'id="p-chg"' in html
    assert html.index('id="p-chg"') < html.index('id="b00"'), "変更点は表紙のすぐ後"
    assert 'id="chg-v0-1"' in html


def test_heading_ids_and_toc(case_with_png: Path) -> None:
    rc, _, err = build(case_with_png)
    assert rc == 0, err
    html = (case_with_png / OUT_NAME).read_text(encoding="utf-8")
    assert '<h2 class="doc-title">' in html, "最初の # は文書の題"
    assert '<span class="d-no">3</span><h3 id="req-3">範囲</h3>' in html, "## は番号の札と名前の区画、id は番号から"
    assert '<h4 id="req-3-1">' in html, "### は 1 段下げて番号から id"
    assert '<a href="#req-3">3. 範囲</a>' in html, "## は目次に入る"
    assert 'href="#req-3-1"' not in html, "### は目次に入れない"
    assert '<div class="d-groups">' in html, "6 章の表は部品で描く (部品の細かい見分けは test_doc_report.py)"


def test_raw_html_in_markdown_is_escaped(case_with_png: Path) -> None:
    append(case_with_png / "要件定義.md", '\n<script>alert("x")</script>\n')
    rc, _, err = build(case_with_png)
    assert rc == 0, err
    html = (case_with_png / OUT_NAME).read_text(encoding="utf-8")
    assert '<script>alert("x")</script>' not in html
    assert "&lt;script&gt;" in html


def test_spec_board_reference_becomes_link(case_with_png: Path) -> None:
    rc, _, _ = build(case_with_png)
    html = (case_with_png / OUT_NAME).read_text(encoding="utf-8")
    assert rc == 0 and 'href="#b02"' in html and 'href="#b03"' in html


def test_title_with_unsafe_characters(tmp_path: Path) -> None:
    base = make_case(tmp_path, title="配車/記録:試し", pngs=True)
    rc, out, err = build(base)
    assert rc == 0, err
    assert Path(out["out"]).name == "配車_記録_試し_打ち合わせ資料.html"


def test_same_input_gives_same_bytes(case_with_png: Path) -> None:
    env = {"SOURCE_DATE_EPOCH": "1790000000"}
    build(case_with_png, env=env)
    first = (case_with_png / OUT_NAME).read_bytes()
    build(case_with_png, env=env)
    assert (case_with_png / OUT_NAME).read_bytes() == first
    assert "2026-09-21 14:13" in first.decode("utf-8"), "SOURCE_DATE_EPOCH は UTC で書く"


def test_out_option(case_with_png: Path, tmp_path: Path) -> None:
    target = tmp_path / "別の場所" / "まとめ.html"
    rc, out, err = build(case_with_png, "--out", str(target))
    assert rc == 0, err
    assert target.is_file() and Path(out["out"]).name == "まとめ.html"
    assert not (case_with_png / OUT_NAME).exists()


def test_usage_errors(case_with_png: Path, tmp_path: Path) -> None:
    rc, out, _ = build(case_with_png, "--out", str(tmp_path / "まとめ.txt"))
    assert rc == 2 and out["status"] == "usage-error"
    rc, _, _ = run_script(SCRIPT, "--dir", str(tmp_path / "なし"))
    assert rc == 2
    rc, _, _ = run_script(SCRIPT)
    assert rc == 2
    rc, out, _ = build(case_with_png, "--no-webp")
    assert rc == 2 and out["status"] == "usage-error", "Python 版の --no-webp / --quality は無い"


def test_quiet_prints_one_line(case_with_png: Path) -> None:
    rc, out, _ = build(case_with_png, "--quiet")
    assert rc == 0
    assert isinstance(out, str) and out.count("\n") == 1 and out.startswith("book: warn 版 v0.1")


def test_code_examples_are_not_resource_references(case_with_png: Path) -> None:
    append(case_with_png / "仕様書.md", '\n```html\n<img src="sample.png">\n<style>.x{background:url(example.png)}</style>\n```\n')
    rc, out, err = build(case_with_png)
    assert rc == 0, err
    assert not out["external"]


def test_wrong_webp_dimensions_fall_back(case_with_png: Path) -> None:
    with_webp(case_with_png)
    write_webp(case_with_png / "_src/book/00_overview.webp", (10, 10))
    rc, out, err = build(case_with_png)
    assert rc == 0, err
    assert "WEBP-SIZE" in codes(out["warnings"])
    assert out["boards"][0]["image_format"] == "png"


def test_quality_warnings_survive_book_assembly(case_with_png: Path) -> None:
    report = {"boards": [{"no": "00", "status": "warn", "warnings": [{"code": "OVERLAP", "message": "重なり"}]}]}
    (case_with_png / "_check/boards.json").write_text(json.dumps(report))
    rc, out, err = build(case_with_png)
    assert rc == 0, err
    assert out["status"] == "warn" and out["written"]
    assert "BOARD-CHECK-WARN" in codes(out["warnings"])
    assert "OVERLAP" in next(w["message"] for w in out["warnings"] if w["code"] == "BOARD-CHECK-WARN")


def test_freshness_follows_css_import_background_and_srcset(case_with_png: Path) -> None:
    base = case_with_png
    append(base / "_src/00_overview.html", '<link rel=stylesheet href="extra.css"><img srcset="assets/a.png 1x, assets/b.png 2x">')
    (base / "_src/extra.css").write_text('@import "nested.css";')
    (base / "_src/nested.css").write_text('.x{background:image-set("assets/bg.png" 1x)}')
    for name in ("a", "b", "bg"):
        write_png(base / f"_src/assets/{name}.png", (10, 10))
    for stem in STEMS:
        write_png(base / f"{stem}.png")
    rc, _, err = build(base)
    assert rc == 0, err
    for rel in ("extra.css", "nested.css", "assets/bg.png", "assets/b.png"):
        file = base / "_src" / rel
        saved = file.stat().st_mtime_ns
        later = (base / "00_overview.png").stat().st_mtime_ns + 60_000_000_000
        os.utime(file, ns=(later, later))
        rc, out, _ = build(base)
        assert rc == 1 and f"_src/{rel}" in out["stale"][0]["newer"]
        os.utime(file, ns=(saved, saved))


def test_receipt_detects_content_change_even_with_old_mtime(case_with_png: Path) -> None:
    from conftest import node_eval
    base = case_with_png
    receipt = node_eval('import { dependencyReceipt } from "./lib/resource-refs.mjs";\n'
                        f'console.log(JSON.stringify(dependencyReceipt({json.dumps(str(base / "_src/00_overview.html"))}, {json.dumps(str(base))})));')
    report = {"boards": [{"no": "00", "status": "ok", "dependencies": receipt}]}
    (base / "_check/boards.json").write_text(json.dumps(report))
    file = base / "_src/common.css"
    old = file.stat().st_mtime_ns
    append(file, '\n.x{opacity:.5}')
    os.utime(file, ns=(old, old))
    rc, out, _ = build(base)
    assert rc == 1 and "_src/common.css" in out["stale"][0]["newer"]


def test_render_receipt_detects_image_corruption(case_with_png: Path) -> None:
    base = case_with_png
    with_webp(base)
    png = base / "00_overview.png"
    webp = base / "_src/book/00_overview.webp"
    report = {"boards": [{"no": "00", "status": "ok", "png_sha256": hashlib.sha256(png.read_bytes()).hexdigest(),
                          "webp_sha256": hashlib.sha256(webp.read_bytes()).hexdigest()}]}
    (base / "_check/boards.json").write_text(json.dumps(report))
    webp.write_bytes(webp.read_bytes() + b"changed")
    rc, out, err = build(base)
    assert rc == 0, err
    assert "WEBP-HASH" in codes(out["warnings"]) and out["boards"][0]["image_format"] == "png"
    png.write_bytes(png.read_bytes()[:24])
    rc, out, _ = build(base)
    assert rc == 1 and "PNG-HASH" in codes(out["errors"]) and not out["written"]


def test_markdown_local_image_embedded_and_missing_warned(case_with_png: Path) -> None:
    (case_with_png / "assets").mkdir()
    file = write_png(case_with_png / "assets/図.png", (10, 10))
    append(case_with_png / "仕様書.md", '\n![構成図](assets/%E5%9B%B3.png)\n\n![欠落](assets/missing.png)\n')
    rc, out, err = build(case_with_png)
    assert rc == 0, err
    import base64
    html = (case_with_png / OUT_NAME).read_text()
    assert base64.b64encode(file.read_bytes()).decode() in html
    assert 'alt="構成図"' in html
    assert "DOC-IMAGE" in codes(out["warnings"]) and out["status"] == "warn"



def test_data_uri_markdown_image_is_preserved(case_with_png: Path) -> None:
    import base64
    image = write_png(case_with_png / "inline.png", (2, 2))
    uri = "data:image/png;base64," + base64.b64encode(image.read_bytes()).decode()
    append(case_with_png / "仕様書.md", f"\n![埋込済]({uri})\n")
    rc, out, err = build(case_with_png)
    assert rc == 0, err
    html = (case_with_png / OUT_NAME).read_text()
    assert f'src="{uri}" alt="埋込済"' in html
    assert "IMAGE-UNVERIFIED" in codes(out["warnings"]) and out["status"] == "warn"


def test_unsafe_or_mismatched_data_uri_warns_without_embedding(case_with_png: Path) -> None:
    import base64
    image = write_png(case_with_png / "inline.png", (2, 2))
    wrong = "data:image/jpeg;base64," + base64.b64encode(image.read_bytes()).decode()
    svg = "data:image/svg+xml;base64," + base64.b64encode(b'<svg onload="alert(1)"/>').decode()
    append(case_with_png / "仕様書.md", f"\n![不一致](<{wrong}>)\n\n![SVG](<{svg}>)\n")
    rc, out, err = build(case_with_png)
    assert rc == 0, err
    assert len([w for w in out["warnings"] if w["code"] == "DOC-IMAGE"]) == 2
    html = (case_with_png / OUT_NAME).read_text()
    assert wrong not in html and svg not in html


def test_verified_board_receipts_do_not_emit_unverified_warning(case_with_png: Path) -> None:
    report = {"boards": [{"no": stem[:2], "status": "ok", "png_sha256": hashlib.sha256((case_with_png / f"{stem}.png").read_bytes()).hexdigest()} for stem in STEMS]}
    (case_with_png / "_check/boards.json").write_text(json.dumps(report))
    rc, out, err = build(case_with_png)
    assert rc == 0, err
    assert "IMAGE-UNVERIFIED" not in codes(out["warnings"])
    assert out["status"] == "ok"


def test_reference_images_embed_and_unresolved_warn(case_with_png: Path) -> None:
    write_png(case_with_png / "reference.png", (2, 2))
    append(case_with_png / "仕様書.md", '\n![定義済][drawing]\n\n![未定義][missing]\n\n[drawing]: reference.png\n')
    rc, out, err = build(case_with_png)
    assert rc == 0, err
    html = (case_with_png / OUT_NAME).read_text()
    assert 'alt="定義済"' in html
    assert any(w["code"] == "DOC-IMAGE" and "missing" in w["message"] for w in out["warnings"])


@needs_browser
def test_data_uri_image_decodes_in_standalone_book(case_with_png: Path) -> None:
    import base64
    image = write_png(case_with_png / "inline.png", (2, 2))
    uri = "data:image/png;base64," + base64.b64encode(image.read_bytes()).decode()
    append(case_with_png / "仕様書.md", f"\n![埋込済](<{uri}>)\n")
    rc, out, err = build(case_with_png)
    assert rc == 0, err
    facts = node_eval('''
import { findBrowser, launchBrowser } from "./lib/browser-session.mjs";
const session = await launchBrowser(findBrowser());
try {
  const page = await session.newPage({ width: 1000, height: 800 });
  await page.goto(BOOK_URL);
  const facts = await page.evaluate(`(async () => {
    const img = document.querySelector('img[alt="埋込済"]');
    if (!img) return null;
    await img.decode();
    return [img.naturalWidth, img.naturalHeight];
  })()`);
  console.log(JSON.stringify(facts));
} finally { await session.close(); }
'''.replace("BOOK_URL", json.dumps(Path(out["out"]).as_uri())), timeout=180)
    assert facts == [2, 2]


def test_missing_or_partial_tokens_preserve_existing_book(case_with_png: Path) -> None:
    target = case_with_png / OUT_NAME
    target.write_text('previous published book', encoding='utf-8')
    tokens = case_with_png / '_src' / 'tokens.css'
    tokens.unlink()
    rc, out, _ = build(case_with_png, '--allow-stale')
    assert rc == 1 and out['written'] is False
    assert 'TOKENS-MISSING' in codes(out['errors'])
    assert target.read_text(encoding='utf-8') == 'previous published book'
    tokens.write_text(':root { --text: #123456; }', encoding='utf-8')
    rc, out, _ = build(case_with_png, '--allow-stale')
    assert rc == 1 and out['written'] is False
    assert 'TOKENS-INVALID' in codes(out['errors'])
    assert target.read_text(encoding='utf-8') == 'previous published book'
