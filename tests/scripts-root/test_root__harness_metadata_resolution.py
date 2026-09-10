"""harness_metadata() の解決順そのものを固定する。

lint-distributable-ssot.py は「sidecar が manifest に勝つ」を前提に、
重複記述の寄せ先を sidecar 側へ指示する。ところがその前提を固定した
テストは repo のどこにも無かった。誰かが fallback を逆向き
(`manifest.get(k, distribution.get(k))`) に書き換えても、lint も
validate-plugin-completeness も緑のまま、指示だけが静かに嘘になる。

ここで固定するのは値ではなく **どちらが勝つか** と **manifest 側の別名**。
"""
from __future__ import annotations

import importlib.util
import pathlib

import pytest

ROOT = pathlib.Path(__file__).resolve().parents[2]
SCRIPT = ROOT / "scripts" / "validate-plugin-completeness.py"


def _load():
    spec = importlib.util.spec_from_file_location("_validate_plugin_completeness", SCRIPT)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


MOD = _load()
HM = MOD.harness_metadata


@pytest.mark.parametrize(
    "key,manifest_value,sidecar_value",
    [
        ("distributable", True, False),
        ("distributable", False, True),
        ("bundle_targets", ["skills-full"], []),
        ("category", "productivity", "development-tools"),
        ("tags", ["a"], ["b"]),
    ],
)
def test_sidecar_wins_over_manifest(key, manifest_value, sidecar_value):
    got = HM({key: manifest_value}, {"distribution": {key: sidecar_value}})
    assert got[key] == sidecar_value


@pytest.mark.parametrize(
    "key,value",
    [
        ("distributable", False),
        ("bundle_targets", ["skills-full"]),
        ("category", "productivity"),
        ("tags", ["a"]),
    ],
)
def test_manifest_is_used_when_sidecar_is_silent(key, value):
    """sidecar 不在時の後方互換 fallback。ここが切れると既存 plugin が全部既定値へ落ちる。"""
    assert HM({key: value}, None)[key] == value
    assert HM({key: value}, {})[key] == value
    assert HM({key: value}, {"distribution": {}})[key] == value


def test_defaults_when_nothing_is_declared():
    """未宣言の既定は「配布する」。非配布は明示宣言でしか起きない。"""
    got = HM({}, None)
    assert got == {"distributable": True, "bundle_targets": [], "category": None, "tags": []}


@pytest.mark.parametrize(
    "key,alias,value",
    [("bundle_targets", "bundles", ["skills-full"]), ("tags", "keywords", ["a", "b"])],
)
def test_manifest_alias_is_read(key, alias, value):
    """旧名も読まれる。lint はこの別名も宣言として数える必要がある。"""
    assert HM({alias: value}, None)[key] == value


@pytest.mark.parametrize(
    "key,alias", [("bundle_targets", "bundles"), ("tags", "keywords")]
)
def test_canonical_name_wins_over_alias(key, alias):
    assert HM({key: ["new"], alias: ["old"]}, None)[key] == ["new"]


@pytest.mark.parametrize(
    "key,alias", [("bundle_targets", "bundles"), ("tags", "keywords")]
)
def test_empty_canonical_falls_through_to_alias(key, alias):
    """`a or b` なので空リストは宣言として効かない。lint の or_chain 判定の根拠。"""
    assert HM({key: [], alias: ["old"]}, None)[key] == ["old"]


@pytest.mark.parametrize("contract", [None, "文字列", ["リスト"], 0])
def test_non_dict_contract_falls_back_instead_of_crashing(contract):
    assert HM({"distributable": False}, contract)["distributable"] is False


def test_non_dict_distribution_falls_back_instead_of_crashing():
    """distribution が dict でない壊れた sidecar で AttributeError を出さない。"""
    assert HM({"distributable": False}, {"distribution": "壊れている"})["distributable"] is False
