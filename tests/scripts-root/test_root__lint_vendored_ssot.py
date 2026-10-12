"""scripts/lint-vendored-ssot.py の genuine で網羅的な機能テスト (network 不要)。

この lint は plugin へ vendoring した共有 SSOT (runtime module・build-time validator・
配布先で localize せず同一契約を読ませる doc/schema) が、正本 (repo-root scripts/ 側か
当該 SSOT を保持する plugin 側) と byte 一致するかを検証する。失敗種別:
  - canonical 不在
  - vendored 不在
  - vendored が symlink へ回帰 (ファイル自身か途中の dir。単独 install で dangling)
  - 通常ファイルでない (dir など。byte 比較できない)
  - SSOT drift (byte 不一致)
全ペア一致なら exit 0。引数は取らない (--help は exit 0、知らない引数は exit 2)。

戦略:
- check_pairs(pairs) を tmp_path 上の合成ペアで直接呼ぶ (network/実ファイル書換なし)。
- glob で組む run-skill-feedback の組は、script を tmp_path/scripts/ へ写して読み、
  写しの ROOT (= tmp_path) の fixture から VENDORED_PAIRS を組ませて確かめる。
- 加えて subprocess で実 repo に対する CLI exit 0 (現状一致) を健全性確認。

network: false, keychain: なし, 実ファイル書換: なし (tmp_path のみ)。
"""
import importlib.util
import shutil
import subprocess
import sys
from pathlib import Path

import pytest

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


def test_check_pairs_intermediate_dir_symlink_regression(tmp_path, monkeypatch):
    # ファイル自身は実体でも、途中の dir (plugins/p/scripts) が symlink なら単独 install で
    # dangling になる。中身が正本と byte 一致していても通さない。
    monkeypatch.setattr(MOD, "ROOT", tmp_path)
    canonical = tmp_path / "scripts" / "mod.py"
    canonical.parent.mkdir(parents=True)
    canonical.write_bytes(b"x = 1\n")
    (tmp_path / "plugins" / "p").mkdir(parents=True)
    (tmp_path / "plugins" / "p" / "scripts").symlink_to(canonical.parent)
    vendored = tmp_path / "plugins" / "p" / "scripts" / "mod.py"
    assert not vendored.is_symlink() and vendored.read_bytes() == canonical.read_bytes()
    fails = MOD.check_pairs([(canonical, vendored)])
    assert len(fails) == 1
    assert "symlink に回帰" in fails[0] and "dangling" in fails[0]
    assert "経路上の plugins/p/scripts が symlink" in fails[0]


def test_check_pairs_plugin_root_symlink_regression(tmp_path, monkeypatch):
    # plugin dir ごと symlink にした場合も検出する (どの深さの要素でも見る)。
    monkeypatch.setattr(MOD, "ROOT", tmp_path)
    real = tmp_path / "elsewhere" / "p"
    (real / "scripts").mkdir(parents=True)
    (real / "scripts" / "mod.py").write_bytes(b"x = 1\n")
    canonical = tmp_path / "scripts" / "mod.py"
    canonical.parent.mkdir(parents=True)
    canonical.write_bytes(b"x = 1\n")
    (tmp_path / "plugins").mkdir()
    (tmp_path / "plugins" / "p").symlink_to(real)
    fails = MOD.check_pairs([(canonical, tmp_path / "plugins" / "p" / "scripts" / "mod.py")])
    assert len(fails) == 1
    assert "経路上の plugins/p が symlink" in fails[0]


def test_check_pairs_dangling_symlink_reported_as_regression(tmp_path, monkeypatch):
    # link 先の消えた symlink は「不在」ではなく symlink 回帰として報告する。
    monkeypatch.setattr(MOD, "ROOT", tmp_path)
    c, v = _pair(tmp_path, make_vend=False)
    v.symlink_to(tmp_path / "gone.py")
    fails = MOD.check_pairs([(c, v)])
    assert len(fails) == 1
    assert "symlink に回帰" in fails[0]
    assert "経路上" not in fails[0]


def test_check_pairs_symlink_above_root_is_ignored(tmp_path, monkeypatch):
    # ROOT より上の symlink (/tmp -> /private/tmp のような別名) は対象外。
    real_root = tmp_path / "real"
    real_root.mkdir()
    alias = tmp_path / "alias"
    alias.symlink_to(real_root)
    monkeypatch.setattr(MOD, "ROOT", alias)
    c, v = _pair(alias)
    assert MOD.check_pairs([(c, v)]) == []


def test_check_pairs_drift_byte_mismatch(tmp_path, monkeypatch):
    monkeypatch.setattr(MOD, "ROOT", tmp_path)
    c, v = _pair(tmp_path, canon_bytes=b"version_a\n", vend_bytes=b"version_b\n")
    fails = MOD.check_pairs([(c, v)])
    assert any("SSOT drift" in f for f in fails)


def test_check_pairs_directory_is_failure_not_traceback(tmp_path, monkeypatch):
    # vendored が dir だと read_bytes が IsADirectoryError で落ちていた。FAIL の一覧に出す。
    monkeypatch.setattr(MOD, "ROOT", tmp_path)
    c, v = _pair(tmp_path, make_vend=False)
    v.mkdir()
    fails = MOD.check_pairs([(c, v)])
    assert fails == ["通常ファイルでない: plugins/p/scripts/mod.py。byte 比較できない。"]


FEEDBACK_REL = (
    "SKILL.md",
    "workflow-manifest.json",
    "references/notion-submit-contract.md",
    "scripts/validate-inline-goal-seek-anchor.py",
)


def _feedback_fixture(root, shape):
    """root に正本 (harness-creator) と量産先 plugins/p の run-skill-feedback を作る。

    量産先の SKILL.md (shape=skill_link / skill_dangling) か dir ごと (shape=dir_dangling) を
    symlink にする。skill_* では、notion-submit-contract.md と anchor validator をわざと食い違わせる。
    """
    anchor = root / "plugins/harness-creator/skills/run-build-skill/templates/goal-seek-runtime/scripts/validate-inline-goal-seek-anchor.py"
    anchor.parent.mkdir(parents=True)
    anchor.write_bytes(b"anchor = 1\n")
    canon = root / "plugins/harness-creator/skills/run-skill-feedback"
    for rel in FEEDBACK_REL:
        (canon / rel).parent.mkdir(parents=True, exist_ok=True)
        (canon / rel).write_bytes(anchor.read_bytes() if rel.endswith(".py") else f"{rel}\n".encode())
    deploy = root / "plugins/p/skills/run-skill-feedback"
    if shape == "dir_dangling":
        deploy.parent.mkdir(parents=True)
        deploy.symlink_to(root / "gone")
        return
    for rel in FEEDBACK_REL[1:]:
        (deploy / rel).parent.mkdir(parents=True, exist_ok=True)
        (deploy / rel).write_bytes((canon / rel).read_bytes())
    (deploy / "references/notion-submit-contract.md").write_bytes(b"drift\n")
    (deploy / "scripts/validate-inline-goal-seek-anchor.py").write_bytes(b"anchor = 2\n")
    (deploy / "SKILL.md").symlink_to(canon / "SKILL.md" if shape == "skill_link" else root / "gone.md")


def _load_copy(root):
    """script を root/scripts/ へ写して読む。写しの ROOT は root になり、VENDORED_PAIRS も root から組まれる。"""
    dst = root / "scripts" / SCRIPT.name
    dst.parent.mkdir(parents=True)
    shutil.copy(SCRIPT, dst)
    spec = importlib.util.spec_from_file_location("lint_vendored_ssot_fixture", dst)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


@pytest.mark.parametrize("shape", ["skill_link", "skill_dangling", "dir_dangling"])
def test_symlinked_feedback_deploy_keeps_its_pairs(tmp_path, capsys, shape):
    # 以前は SKILL.md が symlink の plugin を glob の段で組から外していた。組が 0 件になり、
    # symlink への回帰もほかの2点の drift も見逃して exit 0 だった。
    root = tmp_path.resolve()
    _feedback_fixture(root, shape)
    mod = _load_copy(root)
    deploy = "plugins/p/skills/run-skill-feedback/"
    # fixture に無い固定の組 (tenant_runtime など) は canonical 不在で落ちるので、run-skill-feedback の組だけを見る。
    mod.VENDORED_PAIRS = [(c, v) for c, v in mod.VENDORED_PAIRS if "run-skill-feedback" in v.parts]
    assert {str(v.relative_to(root)) for _, v in mod.VENDORED_PAIRS} == {
        f"plugins/{p}/skills/run-skill-feedback/{rel}"
        for p, rels in (("harness-creator", FEEDBACK_REL[3:]), ("p", FEEDBACK_REL))
        for rel in rels
    }
    assert mod.main() == 1
    err = capsys.readouterr().err
    if shape == "dir_dangling":
        for rel in FEEDBACK_REL:
            assert f"vendored が symlink に回帰: {deploy}{rel} (経路上の {deploy[:-1]} が symlink)" in err
    else:
        assert f"vendored が symlink に回帰: {deploy}SKILL.md ->" in err
        assert f"SSOT drift: {deploy}references/notion-submit-contract.md" in err
        assert f"SSOT drift: {deploy}scripts/validate-inline-goal-seek-anchor.py" in err
        assert f"{deploy}workflow-manifest.json" not in err


def test_main_ok_real_repo(capsys):
    """実 repo の VENDORED_PAIRS が全件一致し exit 0 になること。"""
    rc = MOD.main()
    assert rc == 0
    out = capsys.readouterr().out
    assert "OK" in out and "byte 一致" in out


def test_feedback_contract_pair_registered():
    """feedback_contract_ssot の vendored ペアが登録されていること (回帰固定)。"""
    # canonical=scripts/feedback_contract_ssot.py, vendored=plugins/harness-creator/scripts/...
    assert any(c.name == "feedback_contract_ssot.py" for c, _ in MOD.VENDORED_PAIRS)


def test_cli_real_repo_exit_zero():
    res = subprocess.run([sys.executable, str(SCRIPT)], text=True, capture_output=True)
    assert res.returncode == 0, f"stderr={res.stderr}"
    assert "OK" in res.stdout


def test_cli_help_exits_zero_with_usage():
    res = subprocess.run([sys.executable, str(SCRIPT), "--help"], text=True, capture_output=True)
    assert res.returncode == 0
    assert res.stdout.startswith("usage:") and "OK" not in res.stdout


def test_cli_unknown_argument_is_usage_error_without_checking():
    # 以前は知らない引数を読まずに全件を検査し、exit 0 を返していた。
    res = subprocess.run([sys.executable, str(SCRIPT), "--bogus"], text=True, capture_output=True)
    assert res.returncode == 2
    assert "unrecognized arguments: --bogus" in res.stderr
    assert res.stdout == ""


def test_all_feedback_anchor_validators_are_content_bound():
    expected = set(MOD.ROOT.glob("plugins/*/skills/run-skill-feedback/scripts/validate-inline-goal-seek-anchor.py"))
    actual = {v for c, v in MOD.VENDORED_PAIRS if c.name == "validate-inline-goal-seek-anchor.py"}
    assert expected
    assert actual == expected
    assert MOD.check_pairs([(c, v) for c, v in MOD.VENDORED_PAIRS if v in expected]) == []


def test_every_anchor_validator_copy_is_byte_identical_to_canonical():
    # lint-vendored-ssot.py が縛るのは run-skill-feedback の写しだけ。plugin 直下の写し
    # (ubm-goal-setting・slide-report-generator・spec-drift-guardian) も生成元と byte 一致であることを縛る。
    canonical = MOD.ROOT / "plugins/harness-creator/skills/run-build-skill/templates/goal-seek-runtime/scripts/validate-inline-goal-seek-anchor.py"
    copies = sorted(
        p for p in MOD.ROOT.glob("plugins/**/validate-inline-goal-seek-anchor.py") if p != canonical
    )
    assert len(copies) >= 25
    canonical_bytes = canonical.read_bytes()
    assert [p for p in copies if p.read_bytes() != canonical_bytes] == []
