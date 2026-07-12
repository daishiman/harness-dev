"""render_notion_page.py の純関数 + main CLI 契約を network 無しで網羅する。

render_notion_page は notion_db_properties の Notion 型 projection と
intake-final context (§0〜§11) からの children ブロック組み立てだけを行う
純レンダラであり、実通信は一切しない。よって本テストは:

  - block primitives (rt/heading/paragraph/bullet/numbered/code/divider/callout/quote)
  - DB projection helpers (_select/_multi/_rich/_title/_date/_url) + project_db_properties
  - _render_section_diagrams の mermaid / image / 早期 return 分岐
  - 全 13 section renderer を「完全版 smoke fixture」で一括実行 (render)
  - jsonschema 検証失敗の伝播 (render は不正 ctx で ValidationError)
  - main の CLI 契約 (位置引数 / --ctx/--out/--manifest / 欠落 / 不正 JSON / manifest 欠落)

を実入力で genuine に assert する。すべて tmp_path を使い repo を汚さない。
"""
import importlib.util
import json
import subprocess
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[2]
SCRIPTS_DIR = ROOT / "plugins" / "skill-intake" / "scripts"
SCRIPT = SCRIPTS_DIR / "render_notion_page.py"
SMOKE_CTX = ROOT / "plugins" / "skill-intake" / "fixtures" / "intake-final-smoke" / "context.json"

# _jsonschema_compat / notion_limits.json を解決できるよう scripts dir を sys.path へ。
if str(SCRIPTS_DIR) not in sys.path:
    sys.path.insert(0, str(SCRIPTS_DIR))

_SPEC = importlib.util.spec_from_file_location("render_notion_page_under_test", SCRIPT)
MOD = importlib.util.module_from_spec(_SPEC)
_SPEC.loader.exec_module(MOD)

import _jsonschema_compat as _jc  # noqa: E402  (scripts dir 経由)


# --------------------------------------------------------------------------
# block primitives
# --------------------------------------------------------------------------

def test_rt_wraps_text_and_caps_at_max_rt():
    huge = "x" * (MOD.MAX_RT + 500)
    out = MOD.rt(huge)
    assert out[0]["type"] == "text"
    assert len(out[0]["text"]["content"]) == MOD.MAX_RT


def test_rt_none_becomes_empty_string():
    out = MOD.rt(None)
    assert out[0]["text"]["content"] == ""


def test_rt_coerces_non_str():
    out = MOD.rt(42)
    assert out[0]["text"]["content"] == "42"


def test_heading_clamps_level_into_1_3():
    assert MOD.heading(0, "x")["type"] == "heading_1"
    assert MOD.heading(2, "x")["type"] == "heading_2"
    assert MOD.heading(9, "x")["type"] == "heading_3"


def test_heading_carries_rich_text():
    h = MOD.heading(1, "見出し")
    assert h["heading_1"]["rich_text"][0]["text"]["content"] == "見出し"


def test_paragraph_bullet_numbered_quote_shapes():
    assert MOD.paragraph("p")["type"] == "paragraph"
    assert MOD.bullet("b")["type"] == "bulleted_list_item"
    assert MOD.numbered("n")["type"] == "numbered_list_item"
    assert MOD.quote("q")["quote"]["rich_text"][0]["text"]["content"] == "q"


def test_code_default_language_is_plain_text():
    c = MOD.code("print(1)")
    assert c["type"] == "code"
    assert c["code"]["language"] == "plain text"


def test_code_explicit_language():
    c = MOD.code("graph TD", "mermaid")
    assert c["code"]["language"] == "mermaid"


def test_divider_shape():
    assert MOD.divider() == {"object": "block", "type": "divider", "divider": {}}


def test_callout_without_emoji_has_no_icon():
    c = MOD.callout("注意")
    assert "icon" not in c["callout"]


def test_callout_with_emoji_attaches_icon():
    c = MOD.callout("目的", "🎯")
    assert c["callout"]["icon"] == {"type": "emoji", "emoji": "🎯"}


# --------------------------------------------------------------------------
# DB projection helpers
# --------------------------------------------------------------------------

def test_select_value_and_none():
    assert MOD._select("草案") == {"select": {"name": "草案"}}
    assert MOD._select(None) == {"select": None}


def test_multi_select_maps_each_value():
    out = MOD._multi(["a", "b"])
    assert out == {"multi_select": [{"name": "a"}, {"name": "b"}]}


def test_multi_select_none_becomes_empty_list():
    assert MOD._multi(None) == {"multi_select": []}


def test_rich_and_title_wrap_rich_text():
    assert MOD._rich("本文")["rich_text"][0]["text"]["content"] == "本文"
    assert MOD._title("名前")["title"][0]["text"]["content"] == "名前"


def test_date_value_and_none():
    assert MOD._date("2026-06-24") == {"date": {"start": "2026-06-24"}}
    assert MOD._date(None) == {"date": None}
    assert MOD._date("") == {"date": None}


def test_url_value_and_falsy():
    assert MOD._url("https://x") == {"url": "https://x"}
    assert MOD._url("") == {"url": None}
    assert MOD._url(None) == {"url": None}


def test_project_db_properties_has_15_keys_and_projects_types():
    ctx = {"notion_db_properties": {
        "名前": "テスト名",
        "ステータス": "草案",
        "出力先": ["Notion", "Slack"],
        "真の課題": "課題本文",
    }}
    props = MOD.project_db_properties(ctx)
    assert len(props) == 15
    assert props["名前"]["title"][0]["text"]["content"] == "テスト名"
    assert props["ステータス"]["select"]["name"] == "草案"
    assert props["出力先"]["multi_select"] == [{"name": "Notion"}, {"name": "Slack"}]
    assert props["真の課題"]["rich_text"][0]["text"]["content"] == "課題本文"


def test_project_db_properties_defaults_when_missing():
    props = MOD.project_db_properties({})
    assert props["名前"]["title"][0]["text"]["content"] == ""
    assert props["ステータス"]["select"] is None
    assert props["出力先"]["multi_select"] == []


# --------------------------------------------------------------------------
# _render_section_diagrams: mermaid / image / 早期 return
# --------------------------------------------------------------------------

def test_render_section_diagrams_empty_returns_no_blocks():
    blocks = []
    MOD._render_section_diagrams({}, blocks, "1_assumption_challenger")
    assert blocks == []
    # section_diagrams は在るがキーが無い場合も early return。
    MOD._render_section_diagrams({"section_diagrams": {}}, blocks, "x")
    assert blocks == []


def test_render_section_diagrams_mermaid_with_legend_and_one_liner():
    ctx = {"section_diagrams": {"1_x": [
        {"kind": "flow", "title": "T", "one_liner": "一言",
         "mermaid_source": "graph TD", "legend": "凡例本文"},
    ]}}
    blocks = []
    MOD._render_section_diagrams(ctx, blocks, "1_x")
    types = [b["type"] for b in blocks]
    assert types == ["heading_3", "paragraph", "code", "paragraph"]
    assert blocks[2]["code"]["language"] == "mermaid"
    assert "凡例本文" in blocks[3]["paragraph"]["rich_text"][0]["text"]["content"]


def test_render_section_diagrams_image_branch():
    ctx = {"section_diagrams": {"1_x": [
        {"kind": "img", "title": "画像", "image_url": "https://x/y.png"},
    ]}}
    blocks = []
    MOD._render_section_diagrams(ctx, blocks, "1_x")
    img = [b for b in blocks if b["type"] == "image"]
    assert img and img[0]["image"]["external"]["url"] == "https://x/y.png"


def test_render_section_diagrams_minimal_defaults_kind():
    ctx = {"section_diagrams": {"1_x": [{"title": "最小"}]}}
    blocks = []
    MOD._render_section_diagrams(ctx, blocks, "1_x")
    # kind 欠落時は 'diagram' にフォールバック。mermaid も image も無いので heading のみ。
    assert len(blocks) == 1
    assert "diagram" in blocks[0]["heading_3"]["rich_text"][0]["text"]["content"]


# --------------------------------------------------------------------------
# render: 完全版 fixture で全 section renderer を一括実行
# --------------------------------------------------------------------------

@pytest.fixture(scope="module")
def smoke_ctx():
    return json.loads(SMOKE_CTX.read_text(encoding="utf-8"))


def test_render_full_fixture_produces_props_and_children(smoke_ctx):
    out = MOD.render(smoke_ctx)
    assert set(out.keys()) == {"properties", "children"}
    assert len(out["properties"]) == 15
    # 13 section renderer が全章を出すので children は十分多い。
    assert len(out["children"]) > 50
    # 全ブロックが Notion block 形 (object/type) であること。
    assert all(b.get("object") == "block" for b in out["children"])
    flat = json.dumps(out["children"], ensure_ascii=False)
    # 各章の見出しが現れること (renderer が呼ばれた証跡)。
    for marker in ["0. エグゼクティブサマリ", "1. Phase: assumption-challenger",
                   "2. Phase: user-profiler", "3. Phase: purpose-excavator",
                   "4. Phase: option-presenter", "5. Phase: visualizer",
                   "6. 5軸サマリ", "7. 設計選択サマリ", "8. 未解決事項",
                   "9. harness-creator への申し送り", "10. Phase: self-updater",
                   "11. 出力ファイル一覧"]:
        assert marker in flat, f"section marker not rendered: {marker}"


def test_render_with_section_diagrams_injected(smoke_ctx):
    # smoke fixture は section_diagrams 空。schema 妥当なダイアグラムを章に注入し
    # _render_section_diagrams が render 経由 (mermaid + legend 経路) で呼ばれることを実証。
    # image_url 単独経路は test_render_section_diagrams_image_branch が直接被覆する。
    ctx = json.loads(json.dumps(smoke_ctx))  # deep copy
    ctx["section_diagrams"] = {
        "1_assumption_challenger": [{
            "role": "primary", "asset_id": "a1", "kind": "workflow",
            "title": "前提逆転図", "one_liner": "言いたい一言",
            "mermaid_source": "graph TD; A-->B", "legend": "凡例本文",
        }],
    }
    out = MOD.render(ctx)
    flat = json.dumps(out["children"], ensure_ascii=False)
    assert "graph TD; A-->B" in flat
    assert "凡例本文" in flat
    assert "前提逆転図" in flat


def test_render_rejects_invalid_ctx_with_validation_error():
    with pytest.raises(_jc.ValidationError):
        MOD.render({})  # required な meta 等が無い


def test_render_minimal_optional_branches_omitted(smoke_ctx):
    # 真に任意のフィールド (schema required でないもの) だけを削り、render が通り
    # 任意分岐の「無い側」(if not ...) を踏むこと。schema required な design_choices /
    # handoff_mode / design_decisions.output_priority は残す。
    ctx = json.loads(json.dumps(smoke_ctx))
    ctx["executive_summary"].pop("purpose_narrative", None)
    ctx["assumption"].pop("time_freed_intent", None)
    ctx["assumption"].pop("blind_spots", None)
    ctx["profile"].pop("implications", None)
    ctx["purpose"].pop("underlying_motivation", None)
    ctx["purpose"].pop("differentiation_title", None)
    ctx["purpose"].pop("magic_wand_text", None)
    ctx["purpose"].pop("output_priority", None)
    ctx["handoff"].pop("starting_note", None)
    ctx["self_update"].pop("score_rationale", None)
    ctx["self_update"].pop("deductions", None)
    out = MOD.render(ctx)
    assert len(out["children"]) > 30


# --------------------------------------------------------------------------
# main CLI 契約 (subprocess; レンダラは network 非到達)
# --------------------------------------------------------------------------

def _run(args, cwd):
    return subprocess.run(
        [sys.executable, str(SCRIPT), *args],
        capture_output=True, text=True, cwd=cwd,
    )


def test_cli_help_exit0(tmp_path):
    proc = _run(["--help"], cwd=str(tmp_path))
    assert proc.returncode == 0
    assert "--ctx" in proc.stdout


def test_cli_missing_ctx_exit2(tmp_path):
    proc = _run([], cwd=str(tmp_path))
    assert proc.returncode == 2
    assert "usage:" in proc.stderr


def test_cli_positional_ctx_to_stdout(tmp_path):
    proc = _run([str(SMOKE_CTX)], cwd=str(tmp_path))
    assert proc.returncode == 0, proc.stderr
    out = json.loads(proc.stdout)
    assert "properties" in out and "children" in out
    assert len(out["properties"]) == 15


def test_cli_opt_ctx_and_out_writes_file(tmp_path):
    out_file = tmp_path / "blocks.json"
    proc = _run(["--ctx", str(SMOKE_CTX), "--out", str(out_file)], cwd=str(tmp_path))
    assert proc.returncode == 0, proc.stderr
    data = json.loads(out_file.read_text(encoding="utf-8"))
    assert len(data["children"]) > 50
    # --out 指定時は stdout に JSON 本体は出ない。
    assert proc.stdout.strip() == ""


def test_cli_positional_ctx_and_out(tmp_path):
    out_file = tmp_path / "pos_blocks.json"
    proc = _run([str(SMOKE_CTX), str(out_file)], cwd=str(tmp_path))
    assert proc.returncode == 0, proc.stderr
    assert json.loads(out_file.read_text(encoding="utf-8"))["properties"]


def test_cli_manifest_not_found_exit2(tmp_path):
    proc = _run(["--ctx", str(SMOKE_CTX), "--out", str(tmp_path / "o.json"),
                 "--manifest", str(tmp_path / "missing-manifest.json")],
                cwd=str(tmp_path))
    assert proc.returncode == 2
    assert "--manifest not found" in proc.stderr


def test_cli_manifest_present_is_not_overwritten(tmp_path):
    # --manifest は参考入力で、レンダ結果は --out にのみ書かれ manifest を破壊しない。
    manifest = tmp_path / "manifest.json"
    manifest.write_text(json.dumps({"assets": ["a.png"]}), encoding="utf-8")
    out_file = tmp_path / "blocks.json"
    proc = _run(["--ctx", str(SMOKE_CTX), "--out", str(out_file),
                 "--manifest", str(manifest)], cwd=str(tmp_path))
    assert proc.returncode == 0, proc.stderr
    # manifest は不変。
    assert json.loads(manifest.read_text(encoding="utf-8")) == {"assets": ["a.png"]}
    assert json.loads(out_file.read_text(encoding="utf-8"))["children"]


def test_cli_invalid_json_input_exit2(tmp_path):
    bad = tmp_path / "bad.json"
    bad.write_text("{ not valid json", encoding="utf-8")
    proc = _run([str(bad)], cwd=str(tmp_path))
    assert proc.returncode == 2
    assert "input error" in proc.stderr


def test_cli_missing_input_file_exit2(tmp_path):
    proc = _run([str(tmp_path / "nope.json")], cwd=str(tmp_path))
    assert proc.returncode == 2
    assert "input error" in proc.stderr


# --------------------------------------------------------------------------
# main(argv) in-process 契約
#
# subprocess の子プロセス行カバレッジは素の --cov では回収されないため、
# main(argv) は argv を引数で受ける純設計を活かして同一プロセスで直接呼び、
# 返り値 (exit code) / 出力ファイル / stderr / stdout を assert する。
# これにより main 本体 (引数解決・分岐・I/O) を --cov に確実に計上する。
# --------------------------------------------------------------------------

def test_main_help_raises_systemexit0(capsys):
    # argparse の --help は help を出して SystemExit(0)。
    with pytest.raises(SystemExit) as ei:
        MOD.main(["render_notion_page.py", "--help"])
    assert ei.value.code == 0
    assert "--ctx" in capsys.readouterr().out


def test_main_missing_ctx_returns_2(capsys):
    rc = MOD.main(["render_notion_page.py"])
    assert rc == 2
    assert "usage:" in capsys.readouterr().err


def test_main_positional_ctx_to_stdout(capsys):
    rc = MOD.main(["render_notion_page.py", str(SMOKE_CTX)])
    assert rc == 0
    out = json.loads(capsys.readouterr().out)
    assert "properties" in out and "children" in out
    assert len(out["properties"]) == 15


def test_main_opt_ctx_and_out_writes_file(tmp_path):
    out_file = tmp_path / "blocks.json"
    rc = MOD.main(["render_notion_page.py", "--ctx", str(SMOKE_CTX),
                   "--out", str(out_file)])
    assert rc == 0
    data = json.loads(out_file.read_text(encoding="utf-8"))
    assert len(data["children"]) > 50


def test_main_positional_ctx_and_out(tmp_path):
    out_file = tmp_path / "pos_blocks.json"
    rc = MOD.main(["render_notion_page.py", str(SMOKE_CTX), str(out_file)])
    assert rc == 0
    assert json.loads(out_file.read_text(encoding="utf-8"))["properties"]


def test_main_manifest_not_found_returns_2(tmp_path, capsys):
    rc = MOD.main(["render_notion_page.py", "--ctx", str(SMOKE_CTX),
                   "--out", str(tmp_path / "o.json"),
                   "--manifest", str(tmp_path / "missing.json")])
    assert rc == 2
    assert "--manifest not found" in capsys.readouterr().err


def test_main_manifest_present_not_overwritten(tmp_path):
    manifest = tmp_path / "manifest.json"
    manifest.write_text(json.dumps({"assets": ["a.png"]}), encoding="utf-8")
    out_file = tmp_path / "blocks.json"
    rc = MOD.main(["render_notion_page.py", "--ctx", str(SMOKE_CTX),
                   "--out", str(out_file), "--manifest", str(manifest)])
    assert rc == 0
    # --manifest は参考入力で不変。レンダ結果は --out にのみ書かれる。
    assert json.loads(manifest.read_text(encoding="utf-8")) == {"assets": ["a.png"]}
    assert json.loads(out_file.read_text(encoding="utf-8"))["children"]


def test_main_invalid_json_returns_2(tmp_path, capsys):
    bad = tmp_path / "bad.json"
    bad.write_text("{ not valid json", encoding="utf-8")
    rc = MOD.main(["render_notion_page.py", str(bad)])
    assert rc == 2
    assert "input error" in capsys.readouterr().err


def test_main_missing_input_returns_2(tmp_path, capsys):
    rc = MOD.main(["render_notion_page.py", str(tmp_path / "nope.json")])
    assert rc == 2
    assert "input error" in capsys.readouterr().err


def test_module_guard_runs_main_via_runpy(capsys):
    # if __name__ == "__main__": sys.exit(main(sys.argv)) の末尾ガードを踏む。
    import runpy
    sys.argv = ["render_notion_page.py", str(SMOKE_CTX)]
    with pytest.raises(SystemExit) as ei:
        runpy.run_path(str(SCRIPT), run_name="__main__")
    assert ei.value.code == 0
    assert json.loads(capsys.readouterr().out)["properties"]
