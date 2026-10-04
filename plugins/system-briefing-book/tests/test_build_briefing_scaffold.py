"""build-briefing-scaffold.mjs: 出力フォルダと雛形を作る。既にあるファイルは上書きしない。"""
from __future__ import annotations

import json
import re
from pathlib import Path

import pytest

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


def test_palette_follows_briefing_json(tmp_path: Path) -> None:
    """配色の正は briefing.json の palette。--palette を省いて作り直しても、記録した上書きが残る。"""
    materials = make_materials(tmp_path)
    first = tmp_path / "案件の配色.css"
    first.write_text(":root { --p-brand-indigo: #0B5E4A; }\n", encoding="utf-8")
    rc, _, err = init(materials, "--palette", str(first))
    assert rc == 0, err
    base = materials / "打ち合わせ資料"
    tokens = base / "_src" / "tokens.css"
    briefing = base / "briefing.json"
    assert json.loads(briefing.read_text(encoding="utf-8"))["palette"].endswith("案件の配色.css")

    rc, _, err = init(materials, "--refresh-css")
    assert rc == 0, err
    assert "--p-brand-indigo: #0B5E4A" in tokens.read_text(encoding="utf-8"), "記録した上書きで作り直す"

    rc, out, _ = init(materials, "--palette", "standard", "--refresh-css")
    assert rc == 2 and out["status"] == "usage-error", "記録と違う --palette は止める"
    assert "--p-brand-indigo: #0B5E4A" in tokens.read_text(encoding="utf-8")

    second = tmp_path / "別の配色.css"
    second.write_text(":root { --p-brand-indigo: #123456; }\n", encoding="utf-8")
    data = json.loads(briefing.read_text(encoding="utf-8"))
    data["palette"] = "../../別の配色.css"
    briefing.write_text(json.dumps(data, ensure_ascii=False), encoding="utf-8")
    rc, out, err = init(materials)
    assert rc == 0, err
    assert out["stale_css"] == ["_src/tokens.css"], "--refresh-css を付け忘れたら、記録と合わない CSS を知らせる"
    assert "#0B5E4A" in tokens.read_text(encoding="utf-8")
    rc, out, err = init(materials, "--refresh-css")
    assert rc == 0, err
    assert out["stale_css"] == []
    css = tokens.read_text(encoding="utf-8")
    assert "#123456" in css and "#0B5E4A" not in css, "palette を直せば、その上書きで作り直す (相対は briefing.json の場所から)"


def test_palette_is_recorded_relative_and_survives_a_move(tmp_path: Path) -> None:
    """palette は materials と同じく資料フォルダからの相対で書く。素材と配色をまとめて動かしても同じ色で作り直せる。"""
    project = tmp_path / "案件"
    materials = make_materials(project)
    (project / "案件の配色.css").write_text(":root { --p-brand-indigo: #0B5E4A; }\n", encoding="utf-8")
    rc, _, err = init(materials, "--palette", str(project / "案件の配色.css"))
    assert rc == 0, err
    recorded = json.loads((materials / "打ち合わせ資料" / "briefing.json").read_text(encoding="utf-8"))["palette"]
    assert recorded == "../../案件の配色.css"

    moved = tmp_path / "移した先"
    project.rename(moved)
    rc, out, err = init(moved / "素材", "--refresh-css")
    assert rc == 0, err
    assert out["stale_css"] == []
    assert "--p-brand-indigo: #0B5E4A" in (moved / "素材" / "打ち合わせ資料" / "_src" / "tokens.css").read_text(encoding="utf-8")

    (moved / "案件の配色.css").unlink()
    rc, out, err = init(moved / "素材", "--refresh-css")
    assert rc == 2 and out["status"] == "usage-error"
    assert "briefing.json の palette" in json.dumps(out, ensure_ascii=False) + err, "どこから来た値かを言う"


def overlay(root: Path, css: str = ":root { --p-brand-indigo: #345678; }\n", name: str = "custom.css") -> Path:
    path = root / name
    path.write_text(css, encoding="utf-8")
    return path


def snapshot(base: Path) -> dict:
    return {p.relative_to(base): p.read_bytes() for p in base.rglob("*") if p.is_file()}


def test_palette_paths_use_cli_cwd_and_manifest_directory(tmp_path: Path, monkeypatch) -> None:
    """--palette の相対は今いるフォルダ、記録した palette の相対は briefing.json のフォルダから数える。同じ CSS なら衝突しない。"""
    materials = make_materials(tmp_path)
    overlay(tmp_path)
    monkeypatch.chdir(tmp_path)
    assert init(materials, "--palette", "custom.css")[0] == 0
    manifest_path = materials / "打ち合わせ資料" / "briefing.json"
    assert json.loads(manifest_path.read_text(encoding="utf-8"))["palette"] == "../../custom.css"
    rc, out, err = init(materials, "--palette", "custom.css", "--refresh-css")
    assert rc == 0, (out, err)
    assert "#345678" in (materials / "打ち合わせ資料/_src/tokens.css").read_text(encoding="utf-8")
    assert json.loads(manifest_path.read_text(encoding="utf-8"))["palette"] == "../../custom.css"


def test_conflicting_palette_is_rejected_before_any_writes(tmp_path: Path) -> None:
    materials = make_materials(tmp_path)
    init(materials)
    custom = overlay(tmp_path)
    base = materials / "打ち合わせ資料"
    (base / "仕様書.md").unlink()
    before = snapshot(base)
    rc, out, err = init(materials, "--palette", str(custom), "--refresh-css")
    assert rc == 2 and out["status"] == "usage-error", (out, err)
    assert "briefing.json" in out["message"] and "--refresh-css" in out["message"]
    assert snapshot(base) == before, "止めるときは、消した雛形も作り直さない"


def test_reinit_keeps_tokens_when_original_is_missing(tmp_path: Path) -> None:
    """配った資料を再 init するだけなら、配色の CSS が動いていても tokens.css を守る。作り直すときは止める。"""
    materials = make_materials(tmp_path)
    custom = overlay(tmp_path)
    init(materials, "--palette", str(custom))
    tokens = materials / "打ち合わせ資料/_src/tokens.css"
    before = tokens.read_bytes()
    custom.unlink()
    rc, out, err = init(materials)
    assert rc == 0, (out, err)
    assert "_src/tokens.css" in out["skipped"] and out["stale_css"] == []
    assert tokens.read_bytes() == before
    rc, out, _ = init(materials, "--refresh-css")
    assert rc == 2 and out["status"] == "usage-error" and "briefing.json の palette" in out["message"]
    assert tokens.read_bytes() == before


INVALID_OVERLAYS = {
    "cycle": ":root { --text-heading: var(--text-brand); }\n",
    "undefined": ":root { --p-brand-indigo: var(--nai); }\n",
    "import": '@import "other.css";\n',
}


@pytest.mark.parametrize("css", INVALID_OVERLAYS.values(), ids=INVALID_OVERLAYS.keys())
def test_invalid_palette_is_rejected_before_output_creation(tmp_path: Path, css: str) -> None:
    materials = make_materials(tmp_path)
    rc, out, err = init(materials, "--palette", str(overlay(tmp_path, css)))
    assert rc == 2 and out["status"] == "usage-error", (out, err)
    assert "配色の CSS を確認してください" in out["message"]
    assert not (materials / "打ち合わせ資料").exists()


def test_invalid_refresh_preserves_all_existing_files(tmp_path: Path) -> None:
    materials = make_materials(tmp_path)
    custom = overlay(tmp_path)
    init(materials, "--palette", str(custom))
    base = materials / "打ち合わせ資料"
    (base / "仕様書.md").unlink()
    before = snapshot(base)
    custom.write_text(INVALID_OVERLAYS["cycle"], encoding="utf-8")
    rc, out, err = init(materials, "--refresh-css")
    assert rc == 2 and out["status"] == "usage-error", (out, err)
    assert snapshot(base) == before


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


def test_hearing_scaffold_uses_catalog_without_turning_proposals_into_answers(tmp_path: Path) -> None:
    catalog = json.loads((PLUGIN_ROOT / "assets/data/hearing-catalog.json").read_text(encoding="utf-8"))
    materials = make_materials(tmp_path)
    rc, _, err = init(materials)
    assert rc == 0, err
    document = materials / "打ち合わせ資料" / "ヒアリング.md"
    text = document.read_text(encoding="utf-8")
    assert "{{" not in text
    found = re.findall(r"^\| (H\d{2}) \| ([^|]+?) \| ([^|]*) \| ([^|]+?) \|$", text, re.M)
    assert found == [(q["id"], q["question"], "", "未定") for q in catalog["questions"]]
    for section in catalog["sections"]:
        body = text.split(f"## {section['title']}\n", 1)[1].split("\n## ", 1)[0]
        assert re.findall(r"^\| (H\d{2}) \|", body, re.M) == [
            q["id"] for q in catalog["questions"] if q["section"] == section["id"]
        ]
    # Answers in an existing interview remain authoritative on a second init.
    edited = text.replace("|  | 未定 |", "| 実際の聞き取り結果 | 聞き取り |", 1)
    document.write_text(edited, encoding="utf-8")
    rc, out, err = init(materials)
    assert rc == 0, err
    assert "ヒアリング.md" in out["skipped"]
    assert document.read_text(encoding="utf-8") == edited


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
