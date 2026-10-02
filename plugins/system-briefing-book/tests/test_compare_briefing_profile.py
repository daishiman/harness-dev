"""compare-briefing-profile.mjs: 作った資料を基準点 (assets/data/target-profile.json) と並べた差の表。"""
from __future__ import annotations

import json
import hashlib
import os
from datetime import datetime, timezone

import pytest
from pathlib import Path

from conftest import PLUGIN_ROOT, run_script, node_eval

SCRIPT = "compare-briefing-profile"
TARGET = json.loads((PLUGIN_ROOT / "assets" / "data" / "target-profile.json").read_text(encoding="utf-8"))
# 判断材料ごとに、ボードに置く最小の HTML
PARTS = {
    "facts": '<div class="facts"><div class="fact"><b>40 枚</b><span>月に書く表</span></div></div>',
    "paper": '<img src="assets/paper.png" data-source="記録票.pdf" alt="">',
    "columns": '<div class="bar"><span class="seg" data-kind="paper" style="flex:3">紙から 3</span></div>',
    "reqs": '<div class="reqs"><span class="req" data-req="F01">F01 写真を送る</span></div>',
}


def make_dir(root: Path, boards: list[tuple[str, list[str]]]) -> Path:
    """(型, 置く判断材料) の並びから、briefing.json と _src/NN_*.html だけの資料フォルダを作る。"""
    base = root / "打ち合わせ資料"
    (base / "_src").mkdir(parents=True)
    (base / "_src" / "assets").mkdir()
    (base / "_src" / "assets" / "paper.png").write_bytes(b"image fixture")
    (root / "記録票.pdf").write_bytes(b"material fixture")
    (base / "_src" / "tokens.css").write_text(":root { --ink: black; }")
    (base / "_src" / "common.css").write_text(".board { color: var(--ink); }")
    pages = []
    for i, (kind, parts) in enumerate(boards):
        no = f"{i:02d}"
        file = f"{no}_{kind}.html"
        pages.append({"no": no, "file": file, "type": kind, "title": kind, "screens": []})
        body = "".join(PARTS[p] for p in parts)
        if kind == "mechanism":
            body += "<p>候補を選ぶ → 次回の候補に反映</p>"
        (base / "_src" / file).write_text(
            f'<!doctype html>\n<div class="board" data-board="{no}" data-type="{kind}">{body}</div>\n', encoding="utf-8")
    briefing = {"schema": "briefing-v1", "title": "テスト", "materials": "..", "pages": pages}
    (base / "briefing.json").write_text(json.dumps(briefing, ensure_ascii=False), encoding="utf-8")
    return base


def test_target_shape_without_measures_is_incomplete(tmp_path: Path) -> None:
    base = target_case(tmp_path)
    rc, out, err = run_script(SCRIPT, "--dir", str(base))
    assert rc == 0, err
    assert out["status"] == "incomplete" and out["missing"] == []
    assert out["comparison"] == "structure-only"
    assert out["fidelity"]["status"] == "not-assessed"
    assert out["profile"].endswith("assets/data/target-profile.json")
    # boards.json が無いので文字の大きさは未測定
    keys = [r["key"] for r in out["rows"]]
    assert [k for k in keys if not k.startswith("text_chars.")] == ["pages", "screens", "facts", "paper", "columns", "reqs", "mechanism", "font_px_min"]
    assert out["rows"][-1]["current"] is None and out["rows"][-1]["same"] is None
    assert json.loads((base / "_check" / "profile.json").read_text(encoding="utf-8")) == out


def test_missing_materials_and_measures_are_listed(tmp_path: Path) -> None:
    base = make_dir(tmp_path, [
        ("overview", ["paper"]),  # 今の手間の数字が無い
        ("phone", ["reqs"]),
        ("pc", []),  # 要件の札が無い
        ("data-map", []),  # 列の区分の棒が無い
        ("future", []),  # mechanism のページが無い
    ])
    (base / "_check").mkdir()
    write_measures(base, fonts=[11, 12, 10, 11.5, 11], chars=[500, 300, 350, 400, 50])
    rc, out, err = run_script(SCRIPT, "--dir", str(base))
    assert rc == 0, err  # 差があっても止めない
    assert out["status"] == "diff"
    assert out["missing"] == ["facts", "columns", "reqs", "mechanism"]
    rows = {r["key"]: r for r in out["rows"]}
    assert rows["reqs"]["target"] == "○" and rows["reqs"]["current"] == "1/2"
    assert rows["paper"]["same"] is True and rows["screens"]["same"] is False
    # 字数は並べるだけ (same は null)。文字は基準点より小さい 10 を差にする
    pc_chars = [p["text_chars"] for p in TARGET["pages"] if p["type"] == "pc"]
    pc = rows["text_chars.pc"]
    assert (pc["target"], pc["current"], pc["same"]) == (pc_chars, [350], None)
    assert rows["font_px_min"]["current"] == 10 and rows["font_px_min"]["same"] is False


def test_usage_and_profile_errors(tmp_path: Path) -> None:
    rc, out, _ = run_script(SCRIPT, "--dir", str(tmp_path))  # briefing.json が無い
    assert rc == 2 and out["status"] == "usage-error"
    base = make_dir(tmp_path, [("overview", [])])
    broken = tmp_path / "profile.json"
    broken.write_text("{", encoding="utf-8")
    rc, out, _ = run_script(SCRIPT, "--dir", str(base), "--profile", str(broken))
    assert rc == 3 and out["status"] == "tool-missing"


def write_measures(base: Path, fonts=None, chars=None) -> None:
    pages = json.loads((base / "briefing.json").read_text())["pages"]
    receipts = node_eval(
        'import { dependencyReceipt } from "./lib/resource-refs.mjs";\n'
        + "const base = " + json.dumps(str(base)) + ";\n"
        + "const pages = " + json.dumps(pages) + ";\n"
        + 'console.log(JSON.stringify(pages.map(p => dependencyReceipt(base + "/_src/" + p.file, base))));'
    )
    entries = []
    for i, page in enumerate(pages):
        entries.append({**page, "font_px_min": fonts[i] if fonts else 11,
                        "text_chars": chars[i] if chars else 100, "status": "ok", "dependencies": receipts[i],
                        "checked": datetime.now(timezone.utc).isoformat(),
                        "html_sha256": hashlib.sha256((base / "_src" / page["file"]).read_bytes()).hexdigest()})
    (base / "_check").mkdir(exist_ok=True)
    (base / "_check" / "boards.json").write_text(json.dumps({"boards": entries}))


def target_case(tmp_path: Path) -> Path:
    return make_dir(tmp_path, [(p["type"], [m for m in p["materials"] if m in PARTS]) for p in TARGET["pages"]])


def test_same_is_only_structure_with_current_complete_measurements(tmp_path: Path) -> None:
    base = target_case(tmp_path)
    write_measures(base)
    rc, out, err = run_script(SCRIPT, "--dir", str(base))
    assert rc == 0, err
    assert out["status"] == "same"
    assert out["comparison"] == "structure-only"
    assert out["fidelity"]["required"] == ["meaning", "reference-version", "scope", "visual"]
    assert out["invalid"] == []


@pytest.mark.parametrize("change", ["html", "css", "asset", "same-second", "partial", "null", "receiptless", "failed"])
def test_stale_or_incomplete_measurements_never_same(tmp_path: Path, change: str) -> None:
    base = target_case(tmp_path)
    write_measures(base)
    report = base / "_check" / "boards.json"
    data = json.loads(report.read_text())
    if change == "html":
        board = base / "_src" / data["boards"][0]["file"]
        board.write_text(board.read_text() + "<!-- changed -->")
    elif change == "same-second":
        checked = int(datetime.now(timezone.utc).timestamp())
        for entry in data["boards"]:
            entry["checked"] = datetime.fromtimestamp(checked, timezone.utc).isoformat()
        report.write_text(json.dumps(data))
        dep = base / "_src" / "common.css"
        dep.write_text("changed after measurement")
        os.utime(dep, (checked + 0.5, checked + 0.5))
    elif change in ("css", "asset"):
        dep = base / "_src" / ("common.css" if change == "css" else "assets/paper.png")
        dep.write_text("changed")
        os.utime(dep, (report.stat().st_mtime + 10, report.stat().st_mtime + 10))
    else:
        if change == "partial": data["boards"].pop()
        if change == "null": data["boards"][0]["font_px_min"] = None
        if change == "receiptless": data["boards"][0].pop("dependencies")
        if change == "failed": data["boards"][0]["status"] = "ng"
        report.write_text(json.dumps(data))
    rc, out, err = run_script(SCRIPT, "--dir", str(base))
    assert rc == 0, err
    assert out["status"] == "incomplete"
    assert out["measurements"]["unavailable"]
    assert out["rows"][-1]["current"] is None


@pytest.mark.parametrize("html,reason", [
    ('<div class="fact req bar" data-source="missing.png"></div>', "empty"),
    ('<div hidden><div class="fact req bar">40枚</div></div>', "hidden"),
    ('<div style="display:none" class="fact req bar">40枚</div>', "hidden"),
    ('<div class="fact req bar"><span hidden>40枚</span></div>', "empty"),
    ('<img data-source="missing.png" src="assets/paper.png">', "source-reference-missing"),
    ('<img data-source="記録票.pdf" src="assets/missing.png">', "image-missing"),
    ('<img src="assets/missing.png">', "image-missing"),
])
def test_invalid_materials_are_distinct_from_missing(tmp_path: Path, html: str, reason: str) -> None:
    base = target_case(tmp_path)
    board = base / "_src" / "00_overview.html"
    board.write_text(html)
    write_measures(base)
    rc, out, err = run_script(SCRIPT, "--dir", str(base))
    assert rc == 0, err
    assert out["status"] == "diff"
    assert any(i["no"] == "00" and i["reason"] == reason for i in out["invalid"])


def test_empty_mechanism_and_missing_board_do_not_count(tmp_path: Path) -> None:
    base = target_case(tmp_path)
    (base / "_src" / "09_mechanism.html").write_text('<head><title>しくみ</title></head><div class="board"><template>未表示</template></div>')
    (base / "_src" / "01_screen-map.html").unlink()
    rc, out, err = run_script(SCRIPT, "--dir", str(base))
    assert rc == 0, err
    assert out["status"] == "diff" and "mechanism" in out["missing"]
    assert {i["reason"] for i in out["invalid"]} >= {"empty", "board-missing"}


def test_unrelated_assets_do_not_invalidate_measurements(tmp_path: Path) -> None:
    base = target_case(tmp_path)
    write_measures(base)
    (base / "_src" / "assets" / "unused.png").write_text("not a board dependency")
    rc, out, err = run_script(SCRIPT, "--dir", str(base))
    assert rc == 0, err
    assert out["status"] == "same"


@pytest.mark.parametrize("change", ["nested-css", "srcset", "deleted"])
def test_receipt_detects_referenced_changes_even_with_preserved_mtime(tmp_path: Path, change: str) -> None:
    base = target_case(tmp_path)
    asset = base / "_src" / "assets" / "dependency.png"
    asset.write_text("before")
    if change == "srcset":
        board = base / "_src" / "00_overview.html"
        board.write_text(board.read_text() + '<img src="assets/paper.png" srcset="assets/dependency.png 2x">')
    else:
        (base / "_src" / "common.css").write_text('@import "assets/nested.css";')
        (base / "_src" / "assets" / "nested.css").write_text('.board { background: url("dependency.png"); }')
    write_measures(base)
    before = asset.stat()
    if change == "deleted":
        asset.unlink()
    else:
        asset.write_text("after")
        os.utime(asset, ns=(before.st_atime_ns, before.st_mtime_ns))
    rc, out, err = run_script(SCRIPT, "--dir", str(base))
    assert rc == 0, err
    assert out["status"] == "incomplete"
    assert all(e["reason"] == "stale" for e in out["measurements"]["unavailable"])
