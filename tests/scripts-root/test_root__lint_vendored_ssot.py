"""scripts/lint-vendored-ssot.py の genuine で網羅的な機能テスト (network 不要)。

この lint は plugin へ vendoring した共有 SSOT (notion_config.py /
feedback_contract_ssot.py) が repo-root 正本と byte 一致するかを検証する。失敗種別:
  - canonical 不在
  - vendored 不在
  - vendored が symlink へ回帰 (単独 install で dangling)
  - SSOT drift (byte 不一致)
全ペア一致なら exit 0。

戦略:
- check_pairs(pairs) を tmp_path 上の合成ペアで直接呼ぶ (network/実ファイル書換なし)。
- 加えて subprocess で実 repo に対する CLI exit 0 (現状一致) を健全性確認。

network: false, keychain: なし, 実ファイル書換: なし (tmp_path のみ)。
"""
import importlib.util
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
SCRIPT = ROOT / "scripts" / "lint-vendored-ssot.py"

SPEC = importlib.util.spec_from_file_location("lint_vendored_ssot_uut", SCRIPT)
MOD = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(MOD)


def _pair(tmp_path, *, canon_bytes=b"x = 1\n", vend_bytes=b"x = 1\n",
          make_canon=True, make_vend=True, vend_symlink=False):
    """tmp_path 配下に (canonical, vendored) ペアを構築して返す。

    check_pairs は ROOT 相対化 (relative_to(MOD.ROOT)) を行うため、MOD.ROOT を
    tmp_path に向ける前提でペアを tmp_path 配下に置く。
    """
    canonical = tmp_path / "scripts" / "mod.py"
    vendored = tmp_path / "plugins" / "p" / "scripts" / "mod.py"
    canonical.parent.mkdir(parents=True, exist_ok=True)
    vendored.parent.mkdir(parents=True, exist_ok=True)
    if make_canon:
        canonical.write_bytes(canon_bytes)
    if vend_symlink:
        vendored.symlink_to(canonical)
    elif make_vend:
        vendored.write_bytes(vend_bytes)
    return canonical, vendored


def test_check_pairs_ok_byte_match(tmp_path, monkeypatch):
    monkeypatch.setattr(MOD, "ROOT", tmp_path)
    c, v = _pair(tmp_path, canon_bytes=b"same\n", vend_bytes=b"same\n")
    assert MOD.check_pairs([(c, v)]) == []


def test_check_pairs_canonical_missing(tmp_path, monkeypatch):
    monkeypatch.setattr(MOD, "ROOT", tmp_path)
    c, v = _pair(tmp_path, make_canon=False)
    fails = MOD.check_pairs([(c, v)])
    assert any("canonical 不在" in f for f in fails)


def test_check_pairs_vendored_missing(tmp_path, monkeypatch):
    monkeypatch.setattr(MOD, "ROOT", tmp_path)
    c, v = _pair(tmp_path, make_vend=False)
    fails = MOD.check_pairs([(c, v)])
    assert any("vendored 不在" in f for f in fails)


def test_check_pairs_vendored_symlink_regression(tmp_path, monkeypatch):
    monkeypatch.setattr(MOD, "ROOT", tmp_path)
    c, v = _pair(tmp_path, vend_symlink=True)
    fails = MOD.check_pairs([(c, v)])
    assert any("symlink に回帰" in f and "dangling" in f for f in fails)


def test_check_pairs_drift_byte_mismatch(tmp_path, monkeypatch):
    monkeypatch.setattr(MOD, "ROOT", tmp_path)
    c, v = _pair(tmp_path, canon_bytes=b"version_a\n", vend_bytes=b"version_b\n")
    fails = MOD.check_pairs([(c, v)])
    assert any("SSOT drift" in f for f in fails)


def test_main_ok_real_repo(capsys):
    """実 repo の VENDORED_PAIRS (2 件) が一致し exit 0 になること。"""
    rc = MOD.main()
    assert rc == 0
    out = capsys.readouterr().out
    assert "OK" in out and "byte 一致" in out


def test_feedback_contract_pair_registered():
    """feedback_contract_ssot の vendored ペアが登録されていること (回帰固定)。"""
    names = {(c.name, v.parent.parent.parent.name) for c, v in MOD.VENDORED_PAIRS}
    # canonical=scripts/feedback_contract_ssot.py, vendored=plugins/harness-creator/scripts/...
    assert any(c.name == "feedback_contract_ssot.py" for c, _ in MOD.VENDORED_PAIRS)


def test_cli_real_repo_exit_zero():
    res = subprocess.run([sys.executable, str(SCRIPT)], text=True, capture_output=True)
    assert res.returncode == 0, f"stderr={res.stderr}"
    assert "OK" in res.stdout
