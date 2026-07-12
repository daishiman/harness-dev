"""Genuine functional tests for
plugins/contract-generator/scripts/lint-config-ssot.py.

network/Notion/keychain は一切叩かない (この lint は純粋な静的検査で外部通信なし)。
スクリプトを実ファイルパスから importlib でロードし、

- _plugin_root (明示 / 既定の 2 階層上)
- 5 つの純チェック関数 (check_party_a_dangling / check_party_a_readme_stub /
  check_dot_config_name / check_runtests_stage_count / check_install_paths)
  を、tmp_path に「合格 fixture」と「各違反 fixture」を作って実入力で fails 配列を assert
- main() を subprocess (sys.executable) で実行し --plugin-root に合格/違反ツリーを渡して
  exit code と stdout を assert

全 fixture は tmp_path 配下なので repo を汚さない。
"""
import importlib.util
import json
import os
import subprocess
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[2]
SCRIPT = ROOT / "plugins" / "contract-generator" / "scripts" / "lint-config-ssot.py"

_SPEC = importlib.util.spec_from_file_location("lint_config_ssot_s3", SCRIPT)
LCS = importlib.util.module_from_spec(_SPEC)
_SPEC.loader.exec_module(LCS)


# ===================== fixture builder =====================

def _write(p: Path, text: str) -> None:
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(text, encoding="utf-8")


def _good_tree(root: Path) -> Path:
    """5 チェック全 PASS になる最小 plugin ツリーを作る。"""
    cg = root / "skills" / "run-contract-generate" / "references"
    # template-mapping: 甲列 party_a 参照キーは全て fields[] に差込経路あり
    mapping = {
        "common": {
            "fixed_values": {
                "甲名称": "{{party_a.name}}",
                "甲住所": "{{party_a.address}}",
                "準拠法": "日本法",  # party_a 参照でない固定値 (無視されるべき)
            }
        },
        "individual": {
            "fields": [
                {"column": "甲名称"},
                {"column": "甲住所"},
            ]
        },
        "corporate": {
            "fields": [
                {"column": "甲名称"},
                {"column": "甲住所"},
            ]
        },
    }
    _write(cg / "template-mapping.json", json.dumps(mapping, ensure_ascii=False))

    # party_a-readme: 正本あり / skill 側スタブは正本参照
    _write(root / "references" / "party_a-readme.md", "正本 party_a-readme.md 本体\n")
    _write(cg / "party_a-readme.md",
           "このファイルは正本 references/party_a-readme.md へのスタブ参照です。\n")

    # 設定名: 旧ドット名なし
    _write(root / "README.md", "google-config.json を使ってください。\n")
    _write(cg / "README-setup.md", "run-tests.sh は 3 段で実行します。\n")

    # run-tests.sh: 段数 [N/3] で統一
    _write(root / "scripts" / "run-tests.sh",
           "echo [1/3]\necho [2/3]\necho [3/3]\n")
    return root


# ===================== _plugin_root =====================

def test_plugin_root_explicit_abspath(tmp_path):
    rel = os.path.relpath(str(tmp_path))
    assert LCS._plugin_root(rel) == str(tmp_path)


def test_plugin_root_default_is_two_levels_up():
    # __file__ の 2 階層上 = plugins/contract-generator
    expected = os.path.dirname(os.path.dirname(os.path.abspath(LCS.__file__)))
    # module の __file__ は SCRIPT 実体なので 2 階層上 = scripts の親 = plugin root
    assert LCS._plugin_root(None) == expected


# ===================== C-A party_a dangling =====================

def test_check_party_a_dangling_ok(tmp_path):
    _good_tree(tmp_path)
    fails = []
    LCS.check_party_a_dangling(str(tmp_path), fails)
    assert fails == []


def test_check_party_a_dangling_detects_missing_route(tmp_path):
    _good_tree(tmp_path)
    cg = tmp_path / "skills" / "run-contract-generate" / "references"
    mapping = json.loads((cg / "template-mapping.json").read_text(encoding="utf-8"))
    # 甲電話 を fixed_values に追加するが fields[] には入れない → 宙吊り
    mapping["common"]["fixed_values"]["甲電話"] = "{{party_a.phone}}"
    _write(cg / "template-mapping.json", json.dumps(mapping, ensure_ascii=False))
    fails = []
    LCS.check_party_a_dangling(str(tmp_path), fails)
    assert len(fails) == 1
    assert "宙吊り" in fails[0]
    assert "甲電話" in fails[0]


def test_check_party_a_dangling_missing_file(tmp_path):
    fails = []
    LCS.check_party_a_dangling(str(tmp_path), fails)
    assert len(fails) == 1
    assert "template-mapping.json が見つかりません" in fails[0]


def test_check_party_a_dangling_non_party_a_fixed_values_ignored(tmp_path):
    # party_a を参照しない固定値だけなら宙吊りなし
    cg = tmp_path / "skills" / "run-contract-generate" / "references"
    mapping = {"common": {"fixed_values": {"準拠法": "日本法"}},
               "individual": {"fields": []}, "corporate": {"fields": []}}
    _write(cg / "template-mapping.json", json.dumps(mapping, ensure_ascii=False))
    fails = []
    LCS.check_party_a_dangling(str(tmp_path), fails)
    assert fails == []


# ===================== C-B party_a-readme stub =====================

def test_check_readme_stub_ok(tmp_path):
    _good_tree(tmp_path)
    fails = []
    LCS.check_party_a_readme_stub(str(tmp_path), fails)
    assert fails == []


def test_check_readme_stub_missing_canon(tmp_path):
    # 正本が無いと FAIL
    fails = []
    LCS.check_party_a_readme_stub(str(tmp_path), fails)
    assert len(fails) == 1
    assert "正本" in fails[0]


def test_check_readme_stub_no_skill_file_ok(tmp_path, capsys):
    # 正本あり・skill 側ファイルなし → OK (複製なし)
    _write(tmp_path / "references" / "party_a-readme.md", "正本\n")
    fails = []
    LCS.check_party_a_readme_stub(str(tmp_path), fails)
    assert fails == []
    assert "skill 側ファイルなし" in capsys.readouterr().out


def test_check_readme_stub_detects_duplicated_table(tmp_path):
    # skill 側が優先順位表を全文複製していたら違反
    _write(tmp_path / "references" / "party_a-readme.md", "正本\n")
    stub = tmp_path / "skills" / "run-contract-generate" / "references" / "party_a-readme.md"
    _write(stub,
           "優先順位:\n1. party_a.json\n2. party_a.json (env)\n3. party_a.json (xdg)\n")
    fails = []
    LCS.check_party_a_readme_stub(str(tmp_path), fails)
    assert len(fails) == 1
    assert "複製" in fails[0]


def test_check_readme_stub_table_with_ref_is_ok(tmp_path):
    # 複製していても正本参照注記があれば許容 (has_ref)
    _write(tmp_path / "references" / "party_a-readme.md", "正本\n")
    stub = tmp_path / "skills" / "run-contract-generate" / "references" / "party_a-readme.md"
    _write(stub,
           "正本 party_a-readme.md スタブ。優先 party_a.json party_a.json party_a.json\n")
    fails = []
    LCS.check_party_a_readme_stub(str(tmp_path), fails)
    assert fails == []


# ===================== C-C dot config name =====================

def test_check_dot_config_ok(tmp_path):
    _good_tree(tmp_path)
    fails = []
    LCS.check_dot_config_name(str(tmp_path), fails)
    assert fails == []


def test_check_dot_config_detects_old_dot_name(tmp_path):
    _good_tree(tmp_path)
    _write(tmp_path / "README.md", "設定は .google-config.json に書きます。\n")
    fails = []
    LCS.check_dot_config_name(str(tmp_path), fails)
    assert len(fails) == 1
    assert "README.md:1" in fails[0]
    assert ".google-config.json" in fails[0]


def test_check_dot_config_backward_compat_note_allowed(tmp_path):
    _good_tree(tmp_path)
    _write(tmp_path / "README.md",
           "後方互換のため .google-config.json も読みます。\n")
    fails = []
    LCS.check_dot_config_name(str(tmp_path), fails)
    assert fails == []


def test_check_dot_config_kyu_note_allowed(tmp_path):
    _good_tree(tmp_path)
    _write(tmp_path / "README.md", "旧名 .google-config.json は非推奨。\n")
    fails = []
    LCS.check_dot_config_name(str(tmp_path), fails)
    assert fails == []


def test_check_dot_config_skips_absent_docs(tmp_path):
    # 監視対象が一つも無くても落ちない (continue 分岐)
    fails = []
    LCS.check_dot_config_name(str(tmp_path), fails)
    assert fails == []


# ===================== C-D run-tests stage count =====================

def test_check_runtests_ok(tmp_path):
    _good_tree(tmp_path)
    fails = []
    LCS.check_runtests_stage_count(str(tmp_path), fails)
    assert fails == []


def test_check_runtests_missing_sh(tmp_path):
    fails = []
    LCS.check_runtests_stage_count(str(tmp_path), fails)
    assert len(fails) == 1
    assert "run-tests.sh が見つかりません" in fails[0]


def test_check_runtests_inconsistent_totals(tmp_path):
    # [N/M] の M が複数 → 不統一
    _write(tmp_path / "scripts" / "run-tests.sh", "echo [1/3]\necho [2/4]\n")
    fails = []
    LCS.check_runtests_stage_count(str(tmp_path), fails)
    assert len(fails) == 1
    assert "不統一" in fails[0]


def test_check_runtests_doc_mismatch(tmp_path):
    _write(tmp_path / "scripts" / "run-tests.sh", "echo [1/3]\necho [2/3]\necho [3/3]\n")
    doc = tmp_path / "skills" / "run-contract-generate" / "references" / "README-setup.md"
    _write(doc, "run-tests.sh は 5 段で実行します。\n")
    fails = []
    LCS.check_runtests_stage_count(str(tmp_path), fails)
    assert len(fails) == 1
    assert "3 段" in fails[0] and "5 段" in fails[0]


def test_check_runtests_no_doc_ok(tmp_path, capsys):
    # sh はあるが README-setup.md が無い → OK 経路
    _write(tmp_path / "scripts" / "run-tests.sh", "echo [1/3]\necho [2/3]\necho [3/3]\n")
    fails = []
    LCS.check_runtests_stage_count(str(tmp_path), fails)
    assert fails == []
    assert "README-setup.md なし" in capsys.readouterr().out


def test_check_runtests_doc_match_ok(tmp_path):
    _write(tmp_path / "scripts" / "run-tests.sh", "echo [1/2]\necho [2/2]\n")
    doc = tmp_path / "skills" / "run-contract-generate" / "references" / "README-setup.md"
    _write(doc, "run-tests.sh は 2 段で実行します。\n")
    fails = []
    LCS.check_runtests_stage_count(str(tmp_path), fails)
    assert fails == []


# ===================== C-E install paths =====================

def test_check_install_paths_ok(tmp_path):
    _good_tree(tmp_path)
    fails = []
    LCS.check_install_paths(str(tmp_path), fails)
    assert fails == []


def test_check_install_paths_detects_placeholder(tmp_path):
    _good_tree(tmp_path)
    _write(tmp_path / "README.md", "cron に cd <repo>/plugins と書く。\n")
    fails = []
    LCS.check_install_paths(str(tmp_path), fails)
    assert len(fails) == 1
    assert "README.md:1" in fails[0]


def test_check_install_paths_dev_repo_note_allowed(tmp_path):
    _good_tree(tmp_path)
    _write(tmp_path / "README.md",
           "開発リポジトリから動かす場合のみ cd <repo>/plugins。\n")
    fails = []
    LCS.check_install_paths(str(tmp_path), fails)
    assert fails == []


def test_check_install_paths_autodetect_note_allowed(tmp_path):
    _good_tree(tmp_path)
    _write(tmp_path / "README.md", "自動検出: cd <plugin-dir> で良い。\n")
    fails = []
    LCS.check_install_paths(str(tmp_path), fails)
    assert fails == []


def test_check_install_paths_plugin_placeholder(tmp_path):
    _good_tree(tmp_path)
    _write(tmp_path / "skills" / "run-template-sync" / "SKILL.md",
           "cd <plugin> して実行。\n")
    fails = []
    LCS.check_install_paths(str(tmp_path), fails)
    assert any("run-template-sync/SKILL.md" in f for f in fails)


# ===================== main() in-process (exit code は戻り値) =====================

def test_main_inprocess_all_pass(tmp_path, monkeypatch, capsys):
    _good_tree(tmp_path)
    monkeypatch.setattr(sys, "argv",
                        ["lint-config-ssot.py", "--plugin-root", str(tmp_path)])
    assert LCS.main() == 0
    out = capsys.readouterr().out
    assert "OK: 設定 SSOT 整合" in out
    assert "lint-config-ssot — 設定 SSOT 整合検査" in out


def test_main_inprocess_failure(tmp_path, monkeypatch, capsys):
    _good_tree(tmp_path)
    _write(tmp_path / "README.md", "設定 .google-config.json を編集。\n")
    monkeypatch.setattr(sys, "argv",
                        ["lint-config-ssot.py", "--plugin-root", str(tmp_path)])
    assert LCS.main() == 1
    out = capsys.readouterr().out
    assert "FAIL: 設定 SSOT 整合違反" in out
    assert "C-C" in out


def test_main_inprocess_default_root(monkeypatch, capsys):
    # --plugin-root 省略時は実 plugin を検査する (回帰: 本物の plugin が PASS する想定)
    monkeypatch.setattr(sys, "argv", ["lint-config-ssot.py"])
    rc = LCS.main()
    assert rc in (0, 1)  # 実 plugin の状態に依存せず main が完走することを保証
    assert "lint-config-ssot" in capsys.readouterr().out


# ===================== main() via subprocess (__main__ 経路) =====================

def _run_main(plugin_root: Path):
    return subprocess.run(
        [sys.executable, str(SCRIPT), "--plugin-root", str(plugin_root)],
        capture_output=True, text=True)


def test_main_all_pass(tmp_path):
    _good_tree(tmp_path)
    r = _run_main(tmp_path)
    assert r.returncode == 0, r.stdout + r.stderr
    assert "OK: 設定 SSOT 整合" in r.stdout
    assert "C-A party_a 宙吊りキー: OK" in r.stdout
    assert "C-E 導入後パス: OK" in r.stdout


def test_main_reports_failures(tmp_path):
    _good_tree(tmp_path)
    # 旧ドット名違反を仕込む
    _write(tmp_path / "README.md", "設定 .google-config.json を編集。\n")
    r = _run_main(tmp_path)
    assert r.returncode == 1, r.stdout + r.stderr
    assert "FAIL: 設定 SSOT 整合違反" in r.stdout
    assert "C-C" in r.stdout


def test_main_multiple_failures(tmp_path):
    # template-mapping 欠落 + run-tests.sh 欠落 + 正本欠落 → 複数 FAIL
    r = _run_main(tmp_path)
    assert r.returncode == 1
    assert "C-A" in r.stdout
    assert "C-B" in r.stdout
    assert "C-D" in r.stdout
