"""build-briefing-scaffold.mjs: 出力フォルダと雛形を作る。既にあるファイルは上書きしない。"""
from __future__ import annotations

import json
import re
from pathlib import Path

from conftest import PLUGIN_ROOT, node_eval, run_script

SCRIPT = "build-briefing-scaffold"
ALL_TYPES = ["overview", "screen-map", "phone", "pc", "data-map", "mechanism", "future"]
DOCS = ["ヒアリング.md", "要件定義.md", "仕様書.md", "変更点.md"]


def make_materials(root: Path) -> Path:
    materials = root / "素材"
    (materials / "写真").mkdir(parents=True)
    (materials / "記録票.pdf").write_bytes(b"%PDF-1.4\n%%EOF\n")
    (materials / "一覧.xlsx").write_bytes(b"PK\x03\x04")
    (materials / "取り込み.csv").write_text("日付,数\n2026-10-01,3\n", encoding="utf-8")
    (materials / "写真" / "現場.jpg").write_bytes(b"\xff\xd8\xff\xd9")
    (materials / "聞き取りメモ.md").write_text("- 打ち直しが大変\n", encoding="utf-8")
    (materials / "~$一覧.xlsx").write_bytes(b"lock")
    return materials


def init(materials: Path, *extra: str):
    return run_script(SCRIPT, "init", "--materials", str(materials), "--title", "写真で記録", "--date", "2026-10-01", *extra)


def test_init_creates_folder_and_lists_materials(tmp_path: Path) -> None:
    materials = make_materials(tmp_path)
    rc, out, err = init(materials)
    assert rc == 0, err
    base = materials / "打ち合わせ資料"
    assert out["status"] == "ok" and out["missing_templates"] == []
    for name in DOCS + ["briefing.json", "_src/tokens.css", "_src/common.css"]:
        assert (base / name).is_file(), name
    assert (base / "_src" / "assets").is_dir() and (base / "_check").is_dir()

    briefing = json.loads((base / "briefing.json").read_text(encoding="utf-8"))
    assert briefing["schema"] == "briefing-v1" and briefing["title"] == "写真で記録"
    assert briefing["pages"] == [] and briefing["materials"] == ".."
    req = (base / "要件定義.md").read_text(encoding="utf-8")
    assert req.startswith("# 要件定義書: 写真で記録") and "版: v0.1" in req and "更新日: 2026-10-01" in req

    report = json.loads((base / "_check" / "materials.json").read_text(encoding="utf-8"))
    kinds = {item["path"]: item["type"] for item in report["items"]}
    assert kinds["記録票.pdf"] == "pdf" and kinds["写真/現場.jpg"] == "image" and kinds["取り込み.csv"] == "csv"
    assert report["needs_csv"] == ["一覧.xlsx"]
    assert not any(p.startswith("打ち合わせ資料") or p.startswith("~$") for p in kinds), "出力フォルダと一時ファイルは数えない"


def test_init_never_overwrites(tmp_path: Path) -> None:
    materials = make_materials(tmp_path)
    init(materials)
    req = materials / "打ち合わせ資料" / "要件定義.md"
    req.write_text("書き足した中身\n", encoding="utf-8")
    rc, out, _ = init(materials)
    assert rc == 0
    assert out["created"] == []
    assert "要件定義.md" in out["skipped"]
    assert req.read_text(encoding="utf-8") == "書き足した中身\n"


def test_refresh_css_only_touches_css(tmp_path: Path) -> None:
    materials = make_materials(tmp_path)
    init(materials)
    base = materials / "打ち合わせ資料"
    (base / "_src" / "tokens.css").write_text("/* 古い */\n", encoding="utf-8")
    (base / "仕様書.md").write_text("書きかけ\n", encoding="utf-8")
    rc, _, _ = init(materials, "--refresh-css")
    assert rc == 0
    assert "古い" not in (base / "_src" / "tokens.css").read_text(encoding="utf-8")
    assert (base / "仕様書.md").read_text(encoding="utf-8") == "書きかけ\n"


def test_init_usage_errors(tmp_path: Path) -> None:
    rc, out, _ = run_script(SCRIPT, "init", "--materials", str(tmp_path / "なし"), "--title", "x")
    assert rc == 2 and out["status"] == "usage-error"
    rc, _, _ = run_script(SCRIPT, "init", "--materials", str(tmp_path), "--title", "  ")
    assert rc == 2
    rc, _, _ = run_script(SCRIPT, "init", "--materials", str(tmp_path), "--title", "x", "--date", "10/01")
    assert rc == 2


def test_init_writes_data_policy(tmp_path: Path) -> None:
    materials = make_materials(tmp_path)
    rc, _, err = init(materials)
    assert rc == 0, err
    briefing = json.loads((materials / "打ち合わせ資料" / "briefing.json").read_text(encoding="utf-8"))
    assert briefing["data_policy"] == "source", "既定は素材のまま"
    masked = tmp_path / "伏せる"
    rc, _, err = init(materials, "--out", str(masked), "--data-policy", "masked")
    assert rc == 0, err
    assert json.loads((masked / "briefing.json").read_text(encoding="utf-8"))["data_policy"] == "masked"
    rc, out, _ = init(materials, "--out", str(tmp_path / "違う値"), "--data-policy", "public")
    assert rc == 2 and out["status"] == "usage-error"
    assert not (tmp_path / "違う値").exists(), "値が違うときはフォルダも作らない"


def test_boards_from_every_template(tmp_path: Path) -> None:
    materials = make_materials(tmp_path)
    init(materials)
    base = materials / "打ち合わせ資料"
    briefing = json.loads((base / "briefing.json").read_text(encoding="utf-8"))
    briefing["pages"] = [
        {"no": f"{i:02d}", "file": f"{i:02d}_{kind}.html", "type": kind, "title": f"<見出し{i}>",
         "reader": "開発する人", "screens": ["S01"] if kind in ("phone", "pc", "screen-map") else [],
         "message": "伝える 1 文"}
        for i, kind in enumerate(ALL_TYPES)
    ]
    (base / "briefing.json").write_text(json.dumps(briefing, ensure_ascii=False), encoding="utf-8")

    rc, out, err = run_script(SCRIPT, "boards", "--dir", str(base))
    assert rc == 0, err
    assert len(out["created"]) == len(ALL_TYPES) and out["unreplaced"] == []
    phone = (base / "_src" / "02_phone.html").read_text(encoding="utf-8")
    assert 'data-board="02"' in phone and 'data-type="phone"' in phone
    assert "&lt;見出し2&gt;" in phone, "タイトルは HTML として逃がす"
    assert "画面 1 / 2" in phone, "端末ボードの kicker は通し番号"
    kickers = {
        page["type"]: re.search(r'<div class="kicker">(.*?)</div>', (base / "_src" / page["file"]).read_text(encoding="utf-8")).group(1)
        for page in briefing["pages"]
    }
    assert kickers == {
        "overview": "はじめに", "screen-map": "画面 ・ 全体", "phone": "画面 1 / 2 ・ スマホ", "pc": "画面 2 / 2 ・ PC",
        "data-map": "見えない部分 1 / 2", "mechanism": "見えない部分 2 / 2", "future": "これから",
    }, "kicker は「区分 ・ 順番」で、h1 (ページの題) と同じ言葉にしない"

    rc, out, _ = run_script(SCRIPT, "boards", "--dir", str(base))
    assert rc == 0 and out["created"] == [] and len(out["skipped"]) == len(ALL_TYPES)


def test_boards_sample_flag_follows_data_policy(tmp_path: Path) -> None:
    materials = make_materials(tmp_path)
    init(materials)
    base = materials / "打ち合わせ資料"
    path = base / "briefing.json"
    board = base / "_src" / "01_phone.html"
    briefing = json.loads(path.read_text(encoding="utf-8"))
    briefing["pages"] = [{"no": "01", "file": "01_phone.html", "type": "phone", "title": "写真を送る",
                          "reader": "現場の担当者", "screens": ["S01"], "message": "撮って送るだけ"}]
    found = {}
    for policy in ("source", "masked", "other"):
        briefing["data_policy"] = policy
        path.write_text(json.dumps(briefing, ensure_ascii=False), encoding="utf-8")
        board.unlink(missing_ok=True)
        rc, out, err = run_script(SCRIPT, "boards", "--dir", str(base))
        assert rc == 0, err
        meta = re.search(r'<div class="meta">(.*?)</div>', board.read_text(encoding="utf-8")).group(1)
        found[policy] = (meta, out["unreplaced"])
    assert found == {
        "source": ("写真で記録", []),
        "masked": ('写真で記録<br><span class="sample-flag">画面の中の名前と値は例です</span>', []),
        "other": ("写真で記録{{SAMPLE_FLAG}}", ["_src/01_phone.html: {{SAMPLE_FLAG}}"]),
    }, "札は masked のときだけ置く。値が違えば置換子を残して知らせる"


def test_hearing_template_matches_guide() -> None:
    guide = (PLUGIN_ROOT / "skills/run-briefing-hearing/references/hearing-guide.md").read_text(encoding="utf-8")
    section = guide.split("## 4. 質問の一覧", 1)[1].split("\n## 5.", 1)[0]
    asked = re.findall(r"^\| ([A-D]\d+) \| (H\d{2}) \| ([^|]+?) \|", section, re.M)
    numbers = sorted(no for _, no, _ in asked)
    assert numbers == [f"H{i:02d}" for i in range(1, len(asked) + 1)], "番号は H01 から欠けも重なりもない"
    legacy = [f"{c}{i}" for c, n in (("A", 6), ("B", 8), ("C", 6), ("D", 4)) for i in range(1, n + 1)]
    by_symbol = {sym: no for sym, no, _ in asked}
    assert [by_symbol[s] for s in legacy] == [f"H{i:02d}" for i in range(1, 25)], "もとからある H01〜H24 は変えない"
    template = (PLUGIN_ROOT / "assets/templates/hearing.md.tmpl").read_text(encoding="utf-8")
    rows = re.findall(r"^\| (H\d{2}) \| ([^|]+?) \|", template, re.M)
    assert rows == [(no, q) for _, no, q in asked], "雛形の行は hearing-guide 4 章の表と同じ順・同じ番号・同じ文"


def test_kicker_for_single_hidden_page_has_no_number() -> None:
    pages = [{"no": "00", "type": "overview"}, {"no": "01", "type": "phone"}, {"no": "02", "type": "mechanism"}]
    assert node_eval(
        'import { kickerFor } from "./build-briefing-scaffold.mjs";\n'
        f"const pages = {json.dumps(pages)};\n"
        "console.log(JSON.stringify(pages.map((p) => kickerFor(p, pages))));"
    ) == ["はじめに", "画面 1 / 1 ・ スマホ", "見えない部分"]


def test_boards_rejects_bad_file_name(tmp_path: Path) -> None:
    materials = make_materials(tmp_path)
    init(materials)
    base = materials / "打ち合わせ資料"
    briefing = json.loads((base / "briefing.json").read_text(encoding="utf-8"))
    briefing["pages"] = [{"no": "01", "file": "02_Overview.html", "type": "overview", "title": "全体図",
                          "reader": "開発する人", "screens": [], "message": "x"}]
    (base / "briefing.json").write_text(json.dumps(briefing, ensure_ascii=False), encoding="utf-8")
    rc, out, _ = run_script(SCRIPT, "boards", "--dir", str(base))
    assert rc == 1 and out["errors"]
    assert not (base / "_src" / "02_Overview.html").exists()
