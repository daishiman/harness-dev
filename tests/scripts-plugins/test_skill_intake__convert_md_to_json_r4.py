"""convert_md_to_json.py の genuine 機能テスト (scripts4 / 独立計測用)。

対象: plugins/skill-intake/scripts/convert_md_to_json.py

挙動の要約:
  intake.md (front-matter + 見出しセクション) を intake.json へ変換する。
  純関数:
    * parse_sections  : '#'〜'####' 見出しで本文を分割し {見出し: 本文} を返す。
    * pick_axis       : セクション見出しに needle が部分一致する最初の本文を返す (無→'')。
    * extract_frontmatter: 先頭 '---\n...\n---\n' を key:value で解析し残り body を返す。
    * convert         : meta + sections から 5_axes / pattern / user_profile 等を組成。
  main(argv):
    * 引数 0 個        → usage を stderr、exit 2
    * 入力読み込み失敗 → 'input error' を stderr、exit 2
    * 出力先省略       → stdout へ JSON
    * 出力先指定       → そのファイルへ JSON+改行を書く、exit 0

検証方針:
  - 純関数を importlib で実ファイルからロードし、正常系・エッジ
    (見出し前テキスト無視 / front-matter 無 / クォート除去 / 複数 needle /
     日英見出し両対応 / integrations の空・カンマ分割 / name フォールバック /
     pattern 既定 'E') を実入力で assert。
  - main は (a) argv 経由 in-process で stdout / ファイル出力 / 異常系 exit code を、
    (b) CLI subprocess(sys.executable) で __main__ guard と exit code を実測。

network: false / keychain: なし / 実 repo 書換: なし (tmp_path のみ)。
"""
import importlib.util
import json
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
SCRIPT = ROOT / "plugins" / "skill-intake" / "scripts" / "convert_md_to_json.py"


def _load_module():
    spec = importlib.util.spec_from_file_location("convert_md_to_json_uut_r4", SCRIPT)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


MOD = _load_module()


def _run_cli(*args):
    return subprocess.run(
        [sys.executable, str(SCRIPT), *args], text=True, capture_output=True
    )


SAMPLE_MD = """---
skill_name_hint: 月次レポート生成
pattern: C
integrations: notion, slack , drive
extra: 'quoted value'
---
# User Profile
経理担当のユーザー。

## 出力先
Notion の月次DB。

## 情報源
freee の仕訳データ。

## 共有相手
経営チーム。

## 真の課題
締め作業の属人化。

## ナレッジ資産
過去レポートの様式。
"""


# ── parse_sections ───────────────────────────────────────────────────────────
def test_parse_sections_splits_by_heading():
    md = "preamble ignored\n# A\nbody a1\nbody a2\n## B\nbody b\n"
    s = MOD.parse_sections(md)
    assert s == {"A": "body a1\nbody a2", "B": "body b"}


def test_parse_sections_ignores_text_before_first_heading():
    md = "no heading here\nstill no heading\n"
    assert MOD.parse_sections(md) == {}


def test_parse_sections_trims_surrounding_blank_lines():
    md = "# H\n\n\ncontent\n\n\n"
    assert MOD.parse_sections(md) == {"H": "content"}


def test_parse_sections_respects_heading_levels_1_to_4_only():
    # ##### (5 個) は _HEADING (1..4) にマッチせず本文扱い
    md = "# H1\n##### not-a-heading\nbody\n"
    s = MOD.parse_sections(md)
    assert "H1" in s
    assert "##### not-a-heading" in s["H1"]
    assert "not-a-heading" not in s


def test_parse_sections_last_section_flushed():
    md = "# only\nlast line"
    assert MOD.parse_sections(md) == {"only": "last line"}


# ── pick_axis ────────────────────────────────────────────────────────────────
def test_pick_axis_partial_match_returns_body():
    sections = {"出力先の詳細": "Notion DB"}
    assert MOD.pick_axis(sections, ["出力先", "Output Destination"]) == "Notion DB"


def test_pick_axis_english_needle():
    sections = {"Output Destination": "to notion"}
    assert MOD.pick_axis(sections, ["出力先", "Output Destination"]) == "to notion"


def test_pick_axis_no_match_returns_empty():
    assert MOD.pick_axis({"無関係": "x"}, ["出力先"]) == ""


def test_pick_axis_returns_first_matching_section():
    # dict 挿入順で最初に needle 一致した見出しの本文
    sections = {"first 真の課題": "A", "second 真の課題": "B"}
    assert MOD.pick_axis(sections, ["真の課題"]) == "A"


# ── extract_frontmatter ──────────────────────────────────────────────────────
def test_extract_frontmatter_parses_kv_and_strips_quotes():
    md = "---\nname: foo\nq: 'quoted'\nd: \"dq\"\n---\nbody here\n"
    meta, body = MOD.extract_frontmatter(md)
    assert meta == {"name": "foo", "q": "quoted", "d": "dq"}
    assert body == "body here\n"


def test_extract_frontmatter_absent_returns_empty_and_original():
    md = "# heading\nno frontmatter\n"
    meta, body = MOD.extract_frontmatter(md)
    assert meta == {}
    assert body == md


def test_extract_frontmatter_skips_non_kv_lines():
    # ': ' を含まない / key 形式でない行は無視される
    md = "---\nvalid: 1\nnot a kv line\n---\nbody\n"
    meta, _ = MOD.extract_frontmatter(md)
    assert meta == {"valid": "1"}
    assert "not a kv line" not in meta


def test_extract_frontmatter_hyphen_underscore_keys():
    md = "---\nskill_name_hint: x\nout-put: y\n---\nb\n"
    meta, _ = MOD.extract_frontmatter(md)
    assert meta["skill_name_hint"] == "x"
    assert meta["out-put"] == "y"


# ── convert: 正常系 (全要素) ─────────────────────────────────────────────────
def test_convert_full_sample():
    out = MOD.convert(SAMPLE_MD)
    assert out["skill_name_hint"] == "月次レポート生成"
    assert out["pattern"] == "C"
    assert out["user_profile"] == "経理担当のユーザー。"
    assert out["5_axes"]["output_target"] == "Notion の月次DB。"
    assert out["5_axes"]["info_source"] == "freee の仕訳データ。"
    assert out["5_axes"]["share_target"] == "経営チーム。"
    assert out["5_axes"]["true_problem"] == "締め作業の属人化。"
    assert out["5_axes"]["knowledge_assets"] == "過去レポートの様式。"
    assert out["integrations"] == ["notion", "slack", "drive"]
    assert out["open_questions"] == []
    assert out["raw_meta"]["extra"] == "quoted value"
    # sections には全見出しが含まれる
    assert "User Profile" in out["sections"]


def test_convert_skill_name_hint_falls_back_to_name():
    md = "---\nname: fallback-name\n---\n# x\nbody\n"
    out = MOD.convert(md)
    assert out["skill_name_hint"] == "fallback-name"


def test_convert_skill_name_hint_derives_from_first_heading():
    # meta に name/skill_name_hint が無い場合、先頭見出しから slug を導出
    md = "---\npattern: A\n---\n# x\nb\n"
    out = MOD.convert(md)
    assert out["skill_name_hint"] == "x"


def test_convert_skill_name_hint_defaults_when_no_heading():
    # 見出しも meta name も無ければ既定 'intake-final'
    md = "no heading at all\n"
    out = MOD.convert(md)
    assert out["skill_name_hint"] == "intake-final"


def test_convert_pattern_defaults_to_E():
    # pattern は A-E enum。指定無し・非コード値は既定 'E' へ正規化
    md = "# x\nbody\n"  # front-matter 無し
    out = MOD.convert(md)
    assert out["pattern"] == "E"


def test_convert_user_profile_japanese_heading():
    md = "# 利用者プロファイル\n日本語プロファイル\n"
    out = MOD.convert(md)
    assert out["user_profile"] == "日本語プロファイル"


def test_convert_user_profile_prefers_english_when_both():
    # convert は 'User Profile' を先に評価し or で短絡 (英語優先)
    md = "# User Profile\nEN\n# 利用者プロファイル\nJA\n"
    out = MOD.convert(md)
    assert out["user_profile"] == "EN"


def test_convert_integrations_empty_when_absent():
    md = "# x\nb\n"
    out = MOD.convert(md)
    assert out["integrations"] == []


def test_convert_integrations_single_value():
    md = "---\nintegrations: solo\n---\n# x\nb\n"
    out = MOD.convert(md)
    assert out["integrations"] == ["solo"]


def test_convert_integrations_trims_and_splits():
    md = "---\nintegrations:  a , b ,c \n---\n# x\nb\n"
    out = MOD.convert(md)
    assert out["integrations"] == ["a", "b", "c"]


def test_convert_missing_axes_are_empty_strings():
    md = "# 出力先\nだけ\n"
    out = MOD.convert(md)
    assert out["5_axes"]["output_target"] == "だけ"
    assert out["5_axes"]["info_source"] == ""
    assert out["5_axes"]["true_problem"] == ""


def test_convert_all_five_axes_keys_present():
    out = MOD.convert("# nothing\n")
    assert set(out["5_axes"].keys()) == {
        "output_target",
        "info_source",
        "share_target",
        "true_problem",
        "knowledge_assets",
    }


# ── main: in-process (argv) ──────────────────────────────────────────────────
def test_main_no_args_usage_exit_2(capsys):
    rc = MOD.main([])
    assert rc == 2
    assert "usage:" in capsys.readouterr().err


def test_main_input_read_error_exit_2(capsys, tmp_path):
    rc = MOD.main([str(tmp_path / "missing.md")])
    assert rc == 2
    assert "input error" in capsys.readouterr().err


def test_main_stdout_when_no_outfile(capsys, tmp_path):
    src = tmp_path / "intake.md"
    src.write_text(SAMPLE_MD, encoding="utf-8")
    rc = MOD.main([str(src)])
    assert rc == 0
    out = capsys.readouterr().out
    data = json.loads(out)
    assert data["skill_name_hint"] == "月次レポート生成"
    assert data["integrations"] == ["notion", "slack", "drive"]


def test_main_writes_outfile(tmp_path):
    src = tmp_path / "intake.md"
    src.write_text(SAMPLE_MD, encoding="utf-8")
    dst = tmp_path / "intake.json"
    rc = MOD.main([str(src), str(dst)])
    assert rc == 0
    text = dst.read_text(encoding="utf-8")
    assert text.endswith("\n")
    data = json.loads(text)
    assert data["pattern"] == "C"
    assert data["5_axes"]["info_source"] == "freee の仕訳データ。"


def test_main_outfile_pretty_printed_unicode(tmp_path):
    # ensure_ascii=False / indent=2 を実出力で確認
    src = tmp_path / "intake.md"
    src.write_text(SAMPLE_MD, encoding="utf-8")
    dst = tmp_path / "out.json"
    MOD.main([str(src), str(dst)])
    text = dst.read_text(encoding="utf-8")
    assert "月次レポート生成" in text  # 非 ASCII がエスケープされていない
    assert "\n  " in text  # indent=2


# ── CLI subprocess (__main__ guard / exit code) ──────────────────────────────
def test_cli_no_args_exit_2():
    res = _run_cli()
    assert res.returncode == 2
    assert "usage:" in res.stderr


def test_cli_missing_input_exit_2(tmp_path):
    res = _run_cli(str(tmp_path / "nope.md"))
    assert res.returncode == 2
    assert "input error" in res.stderr


def test_cli_stdout_roundtrip(tmp_path):
    src = tmp_path / "intake.md"
    src.write_text(SAMPLE_MD, encoding="utf-8")
    res = _run_cli(str(src))
    assert res.returncode == 0, res.stderr
    data = json.loads(res.stdout)
    assert data["skill_name_hint"] == "月次レポート生成"


def test_cli_writes_file(tmp_path):
    src = tmp_path / "intake.md"
    src.write_text(SAMPLE_MD, encoding="utf-8")
    dst = tmp_path / "result.json"
    res = _run_cli(str(src), str(dst))
    assert res.returncode == 0, res.stderr
    data = json.loads(dst.read_text(encoding="utf-8"))
    assert data["5_axes"]["share_target"] == "経営チーム。"
