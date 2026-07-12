"""run-prompt-creator-7layer/scripts/convert-format.py の genuine 機能テスト (scripts4)。

7層正規形 YAML を構造保存のまま md/json/xml/yaml へ変換する CLI スクリプト。
純関数 (parse_layers / to_md / to_json / to_xml / parse_args) を実ファイルから
importlib でロードして実入力で assert し、main は in-process(argv monkeypatch +
SystemExit + tmp_path 出力)で全終了コード(0/1/2)と stdout/stderr/出力ファイルを
踏み、さらに subprocess(sys.executable)で end-to-end の exit code と
`if __name__ == "__main__"` ガード行まで踏む。

名前衝突回避のため _r4 サフィックスを付し、scripts/scripts2/scripts3 に同名ファイルは
作らない。各テストは単独で script 行カバレッジ >=80% を達成する自己完結セット。

network: false, keychain: なし, 実 repo 書換: なし(tmp_path / stdout のみ)。
"""
import importlib.util
import json
import subprocess
import sys
from pathlib import Path

import pytest

SCRIPT = (
    Path(__file__).resolve().parents[2]
    / "plugins"
    / "prompt-creator"
    / "skills"
    / "run-prompt-creator-7layer"
    / "scripts"
    / "convert-format.py"
)

_SPEC = importlib.util.spec_from_file_location("convert_format_uut_r4", SCRIPT)
MOD = importlib.util.module_from_spec(_SPEC)
_SPEC.loader.exec_module(MOD)


# 7層マーカー付き正規形 YAML(本文に key:value / リスト / チェックリストを含め構造保存を検証)
SAMPLE = """# Layer 1: 役割
あなたは熟練のプロンプト設計者です。
- [ ] 達成ゴール: 構造保存

# Layer 2: 目的
purpose: 7層を可逆変換する

# Layer 3: 背景
背景テキスト

# Layer 4: 制約
constraints:
  - 標準ライブラリのみ

# Layer 5: 入力
input: hearing.json

# Layer 6: 出力
output: sheet.md

# Layer 7: 検証
- [ ] 7層すべて保持されている
"""


def _write(tmp_path, text=SAMPLE, name="canon.yaml"):
    p = tmp_path / name
    p.write_text(text, encoding="utf-8")
    return p


def _call_main(monkeypatch, argv):
    # 成功経路は sys.exit() せず正常 return する(終了コード 0 相当)。
    # 異常経路のみ SystemExit を送出するため両方を受ける。
    monkeypatch.setattr(MOD.sys, "argv", argv)
    try:
        MOD.main()
    except SystemExit as exc:
        return 0 if exc.code is None else exc.code
    return 0


# ── parse_args 純関数 ───────────────────────────────────────────────────────
def test_parse_args_defaults_format_md(monkeypatch):
    monkeypatch.setattr(MOD.sys, "argv", ["convert-format.py", "--input", "a.yaml"])
    args = MOD.parse_args()
    assert args.input == "a.yaml"
    assert args.format == "md"
    assert args.output is None


def test_parse_args_rejects_unknown_failfast(monkeypatch):
    # A4-10: parse_known_args の黙殺を廃止。未知フラグ --bogus は argparse が exit 2 で failfast。
    monkeypatch.setattr(
        MOD.sys,
        "argv",
        ["convert-format.py", "--input", "a", "--output", "b", "--bogus", "z"],
    )
    with pytest.raises(SystemExit) as exc:
        MOD.parse_args()
    assert exc.value.code == 2


# ── parse_layers 純関数: 分割・本文保持・全角コロン・件数 ────────────────────
def test_parse_layers_extracts_all_seven_in_order():
    layers = MOD.parse_layers(SAMPLE)
    assert [l["n"] for l in layers] == [1, 2, 3, 4, 5, 6, 7]
    assert layers[0]["title"] == "役割"
    assert layers[6]["title"] == "検証"


def test_parse_layers_preserves_body_verbatim_including_checklist():
    layers = MOD.parse_layers(SAMPLE)
    body1 = layers[0]["body"]
    assert "あなたは熟練のプロンプト設計者です。" in body1
    assert "- [ ] 達成ゴール: 構造保存" in body1  # チェックリスト要素を落とさない
    # YAML key:value / リスト構造も保持
    assert "constraints:" in layers[3]["body"]
    assert "- 標準ライブラリのみ" in layers[3]["body"]


def test_parse_layers_accepts_fullwidth_colon():
    text = "# Layer 1：全角\n本文1\n# Layer 2：次\n本文2\n"
    layers = MOD.parse_layers(text)
    assert [l["title"] for l in layers] == ["全角", "次"]


def test_parse_layers_strips_trailing_whitespace_of_body():
    text = "# Layer 1: t\n本文   \n\n\n"
    layers = MOD.parse_layers(text)
    assert layers[0]["body"] == "本文"  # re.sub(r"\s+$","") で末尾空白除去


def test_parse_layers_no_markers_returns_empty():
    assert MOD.parse_layers("マーカーの無い本文だけ") == []


def test_parse_layers_partial_subset():
    text = "# Layer 3: only\nbody3\n"
    layers = MOD.parse_layers(text)
    assert [l["n"] for l in layers] == [3]


def test_parse_layers_multiple_hashes_marker():
    text = "### Layer 1: h3\nbody\n"
    layers = MOD.parse_layers(text)
    assert layers and layers[0]["title"] == "h3"


# ── to_md 純関数 ────────────────────────────────────────────────────────────
def test_to_md_header_and_layer_titles():
    md = MOD.to_md(MOD.parse_layers(SAMPLE))
    assert md.startswith("# 7層構造プロンプト")
    assert "## Layer 1: 役割" in md
    assert "## Layer 7: 検証" in md


def test_to_md_empty_body_layer_skips_body_block():
    layers = [{"n": 1, "title": "t", "body": "   "}]
    md = MOD.to_md(layers)
    # body.strip() が空 → 本文行は出力されず見出しのみ
    assert "## Layer 1: t" in md
    lines = [ln for ln in md.splitlines() if ln.strip()]
    assert lines == ["# 7層構造プロンプト", "## Layer 1: t"]


def test_to_md_nonempty_body_rendered():
    md = MOD.to_md([{"n": 2, "title": "目的", "body": "本文X"}])
    assert "本文X" in md


# ── to_json 純関数 ──────────────────────────────────────────────────────────
def test_to_json_structure_and_strip():
    js = json.loads(MOD.to_json([{"n": 1, "title": "t", "body": "  body  "}]))
    assert js == [{"layer": 1, "title": "t", "body": "body"}]


def test_to_json_preserves_japanese_non_ascii():
    js = MOD.to_json([{"n": 1, "title": "役割", "body": "日本語"}])
    assert "役割" in js and "\\u" not in js  # ensure_ascii=False


# ── to_xml 純関数: エスケープ・CDATA ────────────────────────────────────────
def test_to_xml_escapes_title_special_chars():
    xml = MOD.to_xml([{"n": 1, "title": "a&b<c>d", "body": "x"}])
    assert 'title="a&amp;b&lt;c&gt;d"' in xml


def test_to_xml_wraps_body_in_cdata():
    xml = MOD.to_xml([{"n": 1, "title": "t", "body": "raw & <tag>"}])
    assert "<![CDATA[\nraw & <tag>\n]]>" in xml
    assert xml.startswith('<?xml version="1.0" encoding="UTF-8"?>')
    assert xml.rstrip().endswith("</prompt>")


# ── main in-process: 各 format / 終了コード ─────────────────────────────────
def test_main_md_writes_output_exit0(monkeypatch, capsys, tmp_path):
    src = _write(tmp_path)
    out = tmp_path / "out.md"
    code = _call_main(
        monkeypatch,
        ["convert-format.py", "--input", str(src), "--format", "md", "--output", str(out)],
    )
    assert code == 0
    assert out.read_text(encoding="utf-8").startswith("# 7層構造プロンプト")
    assert f"converted → {out} (md)" in capsys.readouterr().out


def test_main_json_format(monkeypatch, tmp_path):
    src = _write(tmp_path)
    out = tmp_path / "o.json"
    code = _call_main(
        monkeypatch,
        ["convert-format.py", "--input", str(src), "--format", "json", "--output", str(out)],
    )
    assert code == 0
    data = json.loads(out.read_text(encoding="utf-8"))
    assert len(data) == 7 and data[0]["layer"] == 1


def test_main_xml_format(monkeypatch, tmp_path):
    src = _write(tmp_path)
    out = tmp_path / "o.xml"
    _call_main(
        monkeypatch,
        ["convert-format.py", "--input", str(src), "--format", "xml", "--output", str(out)],
    )
    txt = out.read_text(encoding="utf-8")
    assert "<prompt>" in txt and "<![CDATA[" in txt


def test_main_yaml_passthrough_keeps_text_verbatim(monkeypatch, tmp_path):
    src = _write(tmp_path)
    out = tmp_path / "o.yaml"
    code = _call_main(
        monkeypatch,
        ["convert-format.py", "--input", str(src), "--format", "yaml", "--output", str(out)],
    )
    assert code == 0
    # yaml は構造保存のため入力をそのまま書き出す(layers パース不要経路)
    assert out.read_text(encoding="utf-8") == SAMPLE


def test_main_creates_nested_output_dir(monkeypatch, tmp_path):
    src = _write(tmp_path)
    out = tmp_path / "deep" / "nested" / "o.md"
    code = _call_main(
        monkeypatch,
        ["convert-format.py", "--input", str(src), "--format", "md", "--output", str(out)],
    )
    assert code == 0 and out.exists()


def test_main_missing_input_arg_exit2(monkeypatch, capsys):
    code = _call_main(monkeypatch, ["convert-format.py", "--format", "md", "--output", "x"])
    assert code == 2
    assert "usage:" in capsys.readouterr().err


def test_main_missing_output_arg_exit2(monkeypatch, capsys):
    code = _call_main(monkeypatch, ["convert-format.py", "--input", "x"])
    assert code == 2
    assert "usage:" in capsys.readouterr().err


def test_main_no_layer_markers_exit1(monkeypatch, capsys, tmp_path):
    src = _write(tmp_path, text="マーカー無し本文", name="bad.yaml")
    out = tmp_path / "o.md"
    code = _call_main(
        monkeypatch,
        ["convert-format.py", "--input", str(src), "--format", "md", "--output", str(out)],
    )
    assert code == 1
    assert "Layer マーカー" in capsys.readouterr().err
    assert not out.exists()  # エラー時は書き出さない


def test_main_unknown_format_exit2(monkeypatch, capsys, tmp_path):
    src = _write(tmp_path)
    out = tmp_path / "o.bin"
    code = _call_main(
        monkeypatch,
        ["convert-format.py", "--input", str(src), "--format", "toml", "--output", str(out)],
    )
    assert code == 2
    assert "unknown format: toml" in capsys.readouterr().err


# ── subprocess end-to-end: __main__ ガード行/終了コードを実プロセスで踏む ────
def _run_cli(args, **kw):
    return subprocess.run(
        [sys.executable, str(SCRIPT), *args], text=True, capture_output=True, **kw
    )


def test_subprocess_md_exit0(tmp_path):
    src = _write(tmp_path)
    out = tmp_path / "o.md"
    res = _run_cli(["--input", str(src), "--format", "md", "--output", str(out)])
    assert res.returncode == 0
    assert "converted" in res.stdout
    assert out.exists()


def test_subprocess_no_marker_exit1(tmp_path):
    src = _write(tmp_path, text="no markers", name="b.yaml")
    out = tmp_path / "o.md"
    res = _run_cli(["--input", str(src), "--format", "md", "--output", str(out)])
    assert res.returncode == 1


def test_subprocess_missing_args_exit2():
    assert _run_cli([]).returncode == 2
