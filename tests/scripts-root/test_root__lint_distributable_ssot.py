"""scripts/lint-distributable-ssot.py の分岐検査。

distributable の真偽が sidecar と manifest の2箇所に書ける以上、食い違いは
いつか必ず起きる。本テストは「食い違いを検出できること」を合成データで固定し、
実 repo が現時点で分裂していないことを併せて確認する。
"""
from __future__ import annotations

import importlib.util
import pathlib

import pytest

ROOT = pathlib.Path(__file__).resolve().parents[2]
SCRIPT = ROOT / "scripts" / "lint-distributable-ssot.py"


def _load():
    spec = importlib.util.spec_from_file_location("_lint_distributable_ssot", SCRIPT)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


MOD = _load()
S = MOD.SENTINEL


def rec(name, manifest, sidecar, has_sidecar_file=True):
    return {
        "name": name,
        "manifest": manifest,
        "sidecar": sidecar,
        "has_sidecar_file": has_sidecar_file,
    }


def codes(violations):
    return [v.split(":", 1)[0] for v in violations]


def test_script_exists():
    assert SCRIPT.is_file()


@pytest.mark.parametrize(
    "manifest,sidecar",
    [
        (False, True),   # manifest 非配布 / sidecar 配布 → sidecar が勝ち意図せず公開される
        (True, False),   # manifest 配布 / sidecar 非配布 → 公開したつもりが載らない
    ],
)
def test_conflicting_declaration_is_ds001(manifest, sidecar):
    out = MOD.check_distributable_ssot([rec("p", manifest, sidecar)])
    assert codes(out) == ["DS-001"], out


def test_ds001_message_names_the_effective_value():
    """どちらが実効値かをメッセージで示さないと、直す側がまた manifest を触る。"""
    out = MOD.check_distributable_ssot([rec("p", True, False)])
    assert "sidecar" in out[0]
    assert "p" in out[0]


def test_manifest_only_is_not_a_violation():
    assert MOD.check_distributable_ssot([rec("p", False, S, has_sidecar_file=False)]) == []


def test_sidecar_only_is_not_a_violation():
    assert MOD.check_distributable_ssot([rec("p", S, False)]) == []


def test_neither_declared_is_not_a_violation():
    assert MOD.check_distributable_ssot([rec("p", S, S, has_sidecar_file=False)]) == []


def test_false_is_distinguished_from_missing():
    """False と「キー無し」を同一視すると、明示的な非配布宣言が消える。"""
    assert S is not False
    assert MOD.check_distributable_ssot([rec("p", False, S, has_sidecar_file=False)]) == []
    assert codes(MOD.check_distributable_ssot([rec("p", False, True)])) == ["DS-001"]


def test_multiple_plugins_are_all_reported():
    out = MOD.check_distributable_ssot(
        [rec("a", True, False), rec("b", False, False), rec("c", False, True)]
    )
    assert codes(out) == ["DS-001", "DS-002", "DS-001"]
    assert "a" in out[0] and "b" in out[1] and "c" in out[2]


def test_real_repository_has_no_split_declaration():
    """実 repo の現状を固定する。赤化したら片方に寄せてから通すこと。"""
    plugins = ROOT / "plugins"
    records = [
        MOD.read_declarations(d)
        for d in sorted(plugins.iterdir())
        if d.is_dir() and (d / ".claude-plugin" / "plugin.json").is_file()
    ]
    assert records, "plugins/ から 1 件も読めていない"
    assert MOD.check_distributable_ssot(records) == []


def test_read_declarations_resolves_sidecar_and_manifest():
    """ubm-goal-setting は sidecar 単独宣言 (DS-002 解消後の正しい形)。

    値そのものは公開方針の変数なので固定しない。固定したいのは
    「sidecar から読めて manifest 側には残っていない」という寄せ先の向き。
    """
    got = MOD.read_declarations(ROOT / "plugins" / "ubm-goal-setting")
    assert got["name"] == "ubm-goal-setting"
    assert got["manifest"] is S, "manifest 側に distributable が復活している (DS-002)"
    assert got["sidecar"] is not S, "sidecar が正本なので必ず読めるはず"
    assert got["has_sidecar_file"] is True


@pytest.mark.parametrize("value", [True, False])
def test_same_value_in_both_places_is_ds002(value):
    """同値でも重複記述は違反。片方だけ更新された瞬間に DS-001 へ変わる。"""
    out = MOD.check_distributable_ssot([rec("p", value, value)])
    assert codes(out) == ["DS-002"], out


def test_ds002_message_directs_removal_to_the_manifest_side():
    """寄せ先は sidecar 固定。逆向きを許すと harness_metadata() の解決順と齟齬が残る。"""
    out = MOD.check_distributable_ssot([rec("p", True, True)])
    assert "plugin.json" in out[0]
    assert "package-contract.json" in out[0]


def test_ds001_takes_precedence_over_ds002():
    """食い違いは重複より重い。1 plugin から2件出さない。"""
    out = MOD.check_distributable_ssot([rec("p", True, False)])
    assert codes(out) == ["DS-001"]


def test_real_repository_has_no_duplicate_declaration():
    """実 repo に重複記述が無い状態を固定する。"""
    plugins = ROOT / "plugins"
    records = [
        MOD.read_declarations(d)
        for d in sorted(plugins.iterdir())
        if d.is_dir() and (d / ".claude-plugin" / "plugin.json").is_file()
    ]
    assert [v for v in MOD.check_distributable_ssot(records) if v.startswith("DS-002")] == []
