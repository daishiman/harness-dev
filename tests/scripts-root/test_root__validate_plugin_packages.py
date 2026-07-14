"""scripts/validate-plugin-packages.py の genuine 機能テスト (network 不要)。

対象は単一 plugin 用の実検査器 (validate-plugin-package.py) へ全 plugin を回す
advisory ラッパー。テストは外部 I/O を排して全分岐を実入力で駆動する:

- discover_plugins : MOD.REPO_ROOT を tmp_path へ向け、実 glob で plugin.json を
                     列挙し sorted 結果を assert (空/単数/複数)。
- main             : MOD.VALIDATOR を tmp_path に書いた「fake validator」へ向け、
                     plugin 名ごとに制御された JSON を吐かせて実 subprocess +
                     json.loads 経路を genuine に通す。各終了コード/分岐
                     (clean / advisory-only / blocking / JSON 破損 / validator 不在 /
                      plugin ゼロ) を網羅し stdout/stderr を assert。

実 .claude/ や実 repo の plugins は一切書き換えない。network: false。
"""
import importlib.util
import json
import subprocess
import sys
import textwrap
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[2]
SCRIPT = ROOT / "scripts" / "validate-plugin-packages.py"

SPEC = importlib.util.spec_from_file_location("validate_plugin_packages_uut", SCRIPT)
MOD = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(MOD)


# --- helpers -----------------------------------------------------------------

def _make_plugin_tree(base: Path, names: list[str]) -> None:
    """tmp_path 配下に plugins/<name>/.claude-plugin/plugin.json を作る。"""
    for n in names:
        d = base / "plugins" / n / ".claude-plugin"
        d.mkdir(parents=True)
        (d / "plugin.json").write_text(json.dumps({"name": n}), encoding="utf-8")


def _write_fake_validator(tmp_path: Path, behaviors: dict) -> Path:
    """plugin 名 -> JSON 文字列 (stdout) のマップを返す fake validator を書く。

    behaviors[name] が dict なら json.dumps して stdout に出す。
    behaviors[name] が "<RAW>:..." 形式なら : 以降を生 stdout として出す
        (JSON 破損ケース用)。
    behaviors[name] が "<EXIT2>" なら stderr に出して exit 2 (JSON 無し) を返す。
    未知 name は空 dict を返す。
    """
    payload = {}
    for name, beh in behaviors.items():
        if isinstance(beh, dict):
            payload[name] = {"kind": "json", "value": json.dumps(beh)}
        elif isinstance(beh, str) and beh.startswith("<RAW>:"):
            payload[name] = {"kind": "json", "value": beh[len("<RAW>:"):]}
        elif beh == "<EXIT2>":
            payload[name] = {"kind": "exit2"}
        else:
            raise AssertionError(f"unsupported behavior: {beh!r}")

    src = textwrap.dedent(
        """
        import argparse, json, sys
        PAYLOAD = json.loads(sys.argv[-1]) if False else None
        BEHAVIORS = {behaviors!r}

        def main():
            ap = argparse.ArgumentParser()
            ap.add_argument("--plugin", required=True)
            ap.add_argument("--check", default="all")
            args = ap.parse_args()
            beh = BEHAVIORS.get(args.plugin)
            if beh is None:
                sys.stdout.write(json.dumps({{"pkg_checks": {{}}}}))
                return 0
            if beh["kind"] == "exit2":
                sys.stderr.write("fake validator hard error for " + args.plugin)
                return 2
            sys.stdout.write(beh["value"])
            return 0

        if __name__ == "__main__":
            sys.exit(main())
        """
    ).format(behaviors=payload)
    p = tmp_path / "fake_validator.py"
    p.write_text(src, encoding="utf-8")
    return p


def _checks(**status_by_id) -> dict:
    """{'PKG-002': 'fail', 'PKG-003': 'pass'} -> pkg_checks dict を組む。"""
    return {"pkg_checks": {cid: {"status": st} for cid, st in status_by_id.items()}}


# ============================================================================
# discover_plugins : 実 glob を tmp_path 上で駆動
# ============================================================================

def test_discover_plugins_empty_when_no_plugins(tmp_path, monkeypatch):
    monkeypatch.setattr(MOD, "REPO_ROOT", tmp_path)
    assert MOD.discover_plugins() == []


def test_discover_plugins_single(tmp_path, monkeypatch):
    _make_plugin_tree(tmp_path, ["solo"])
    monkeypatch.setattr(MOD, "REPO_ROOT", tmp_path)
    assert MOD.discover_plugins() == ["solo"]


def test_discover_plugins_sorted_and_dedupe_by_dir(tmp_path, monkeypatch):
    _make_plugin_tree(tmp_path, ["zeta", "alpha", "mike"])
    monkeypatch.setattr(MOD, "REPO_ROOT", tmp_path)
    # 名前は親の親 (plugin ルート) ディレクトリ名 = plugin 名、sorted で返る
    assert MOD.discover_plugins() == ["alpha", "mike", "zeta"]


def test_discover_plugins_ignores_dirs_without_manifest(tmp_path, monkeypatch):
    _make_plugin_tree(tmp_path, ["real"])
    # plugin.json を持たないディレクトリは列挙されない
    (tmp_path / "plugins" / "nomanifest").mkdir(parents=True)
    (tmp_path / "plugins" / "nomanifest" / "skills").mkdir()
    monkeypatch.setattr(MOD, "REPO_ROOT", tmp_path)
    assert MOD.discover_plugins() == ["real"]


# ============================================================================
# main : validator 不在 / plugin ゼロ
# ============================================================================

def test_main_validator_missing_returns_1(tmp_path, monkeypatch, capsys):
    monkeypatch.setattr(MOD, "VALIDATOR", tmp_path / "does-not-exist.py")
    rc = MOD.main()
    assert rc == 1
    assert "validator が見つかりません" in capsys.readouterr().err


def test_main_no_plugins_returns_0_with_warn(tmp_path, monkeypatch, capsys):
    # validator は存在させる (空 fake) が、plugin はゼロ
    fake = _write_fake_validator(tmp_path, {})
    monkeypatch.setattr(MOD, "VALIDATOR", fake)
    monkeypatch.setattr(MOD, "REPO_ROOT", tmp_path)  # plugins/ 無し -> discover 空
    rc = MOD.main()
    assert rc == 0
    assert "plugin.json が見つかりません" in capsys.readouterr().err


# ============================================================================
# main : clean / advisory-only / blocking / JSON破損 を fake validator で genuine 駆動
# ============================================================================

def _wire(monkeypatch, tmp_path, fake: Path, plugins: list[str]):
    monkeypatch.setattr(MOD, "VALIDATOR", fake)
    monkeypatch.setattr(MOD, "discover_plugins", lambda: list(plugins))


def test_main_clean_plugin_returns_0(tmp_path, monkeypatch, capsys):
    fake = _write_fake_validator(
        tmp_path, {"cleanp": _checks(**{"PKG-003": "pass", "PKG-005": "pass"})}
    )
    _wire(monkeypatch, tmp_path, fake, ["cleanp"])
    rc = MOD.main()
    out = capsys.readouterr().out
    assert rc == 0
    assert "cleanp" in out
    assert "OK (clean)" in out
    assert "blocking failure なし" in out
    # advisory 0 件なので advisory サマリ行は出ない
    assert "advisory finding" not in out


def test_main_advisory_only_returns_0_with_advisory_summary(tmp_path, monkeypatch, capsys):
    # PKG-002/PKG-004 が fail (= ADVISORY) のみ -> 非ブロッキング, exit 0
    fake = _write_fake_validator(
        tmp_path,
        {"advp": _checks(**{"PKG-002": "fail", "PKG-004": "fail", "PKG-003": "pass"})},
    )
    _wire(monkeypatch, tmp_path, fake, ["advp"])
    rc = MOD.main()
    out = capsys.readouterr().out
    assert rc == 0
    assert "OK (advisory=['PKG-002', 'PKG-004'])" in out
    assert "advisory finding 2 件" in out
    assert "blocking failure なし" in out


def test_main_blocking_fail_returns_1(tmp_path, monkeypatch, capsys):
    # PKG-003 (非 advisory) が fail -> blocking, exit 1
    fake = _write_fake_validator(
        tmp_path,
        {"badp": _checks(**{"PKG-003": "fail", "PKG-002": "fail"})},
    )
    _wire(monkeypatch, tmp_path, fake, ["badp"])
    rc = MOD.main()
    captured = capsys.readouterr()
    assert rc == 1
    assert "FAIL (blocking): ['PKG-003']" in captured.out
    assert "blocking failure あり" in captured.err
    # advisory (PKG-002) も同時に集計される
    assert "advisory finding 1 件" in captured.out


def test_main_json_decode_error_returns_1(tmp_path, monkeypatch, capsys):
    # validator が JSON でない生文字列を吐く -> JSONDecodeError 分岐 -> hard_fail
    fake = _write_fake_validator(
        tmp_path, {"brokenp": "<RAW>:this is not json at all"}
    )
    _wire(monkeypatch, tmp_path, fake, ["brokenp"])
    rc = MOD.main()
    captured = capsys.readouterr()
    assert rc == 1
    assert "brokenp" in captured.out
    assert "ERROR" in captured.out
    assert "JSON を返さず" in captured.out
    assert "blocking failure あり" in captured.err


def test_main_validator_exit2_no_stdout_is_hard_fail(tmp_path, monkeypatch, capsys):
    # validator が exit2 + stdout 空 -> json.loads('') が JSONDecodeError -> ERROR
    fake = _write_fake_validator(tmp_path, {"crashp": "<EXIT2>"})
    _wire(monkeypatch, tmp_path, fake, ["crashp"])
    rc = MOD.main()
    captured = capsys.readouterr()
    assert rc == 1
    assert "ERROR" in captured.out
    # stderr の先頭がエラーメッセージとして取り込まれる
    assert "fake validator hard error" in captured.out


def test_main_pkg_checks_absent_treated_as_clean(tmp_path, monkeypatch, capsys):
    # pkg_checks キー欠落 -> checks={} -> blocking/advisory 共に空 -> clean
    fake = _write_fake_validator(tmp_path, {"nokey": {"other": 1}})
    _wire(monkeypatch, tmp_path, fake, ["nokey"])
    rc = MOD.main()
    out = capsys.readouterr().out
    assert rc == 0
    assert "OK (clean)" in out


def test_main_pkg_checks_null_treated_as_clean(tmp_path, monkeypatch, capsys):
    # pkg_checks が null -> `or {}` 分岐で {} になる
    fake = _write_fake_validator(tmp_path, {"nullp": {"pkg_checks": None}})
    _wire(monkeypatch, tmp_path, fake, ["nullp"])
    rc = MOD.main()
    out = capsys.readouterr().out
    assert rc == 0
    assert "OK (clean)" in out


def test_main_mixed_plugins_blocking_dominates(tmp_path, monkeypatch, capsys):
    # 複数 plugin: 1つ clean / 1つ advisory / 1つ blocking -> 全体 exit 1
    fake = _write_fake_validator(
        tmp_path,
        {
            "p_clean": _checks(**{"PKG-003": "pass"}),
            "p_adv": _checks(**{"PKG-004": "fail"}),
            "p_block": _checks(**{"PKG-005": "fail", "PKG-002": "fail"}),
        },
    )
    _wire(monkeypatch, tmp_path, fake, ["p_clean", "p_adv", "p_block"])
    rc = MOD.main()
    out = capsys.readouterr().out
    assert rc == 1
    assert "p_clean" in out and "OK (clean)" in out
    assert "p_adv" in out and "OK (advisory=['PKG-004'])" in out
    assert "p_block" in out and "FAIL (blocking): ['PKG-005']" in out
    # advisory_total = p_adv(1) + p_block(1) = 2
    assert "advisory finding 2 件" in out


def test_main_empty_advisory_set_promotes_advisory_to_blocking(tmp_path, monkeypatch, capsys):
    # ADVISORY_PKG を空にすると PKG-002/004 も blocking 扱いに昇格 (docstring 記載の挙動)
    fake = _write_fake_validator(
        tmp_path, {"promo": _checks(**{"PKG-002": "fail", "PKG-004": "fail"})}
    )
    _wire(monkeypatch, tmp_path, fake, ["promo"])
    monkeypatch.setattr(MOD, "ADVISORY_PKG", set())
    rc = MOD.main()
    out = capsys.readouterr().out
    assert rc == 1
    assert "FAIL (blocking): ['PKG-002', 'PKG-004']" in out
    # advisory_total は 0 のままなので advisory サマリは出ない
    assert "advisory finding" not in out


def test_main_header_lists_advisory_pkgs(tmp_path, monkeypatch, capsys):
    fake = _write_fake_validator(tmp_path, {"hp": _checks(**{"PKG-003": "pass"})})
    _wire(monkeypatch, tmp_path, fake, ["hp"])
    MOD.main()
    out = capsys.readouterr().out
    # ヘッダに plugin 件数と advisory 一覧が出る
    assert "1 plugin を検査" in out
    assert "['PKG-002', 'PKG-004', 'PKG-014']" in out


# ============================================================================
# subprocess: 実 CLI を実 repo に対して起動 (network 不要 / 実 repo 無変更)
# ============================================================================

def test_cli_subprocess_runs_on_real_repo():
    proc = subprocess.run(
        [sys.executable, str(SCRIPT)],
        capture_output=True, text=True, timeout=180,
    )
    # 実 repo 状態に依存するが、現状全 plugin が advisory のみ or clean のため
    # exit 0 (blocking なし) が期待値。万一 blocking が混じれば 1 を許容。
    assert proc.returncode in (0, 1)
    assert "[plugin-package-check]" in proc.stdout
    assert "plugin を検査" in proc.stdout
