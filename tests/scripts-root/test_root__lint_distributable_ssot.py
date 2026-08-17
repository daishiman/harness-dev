"""scripts/lint-distributable-ssot.py の分岐検査。

配布メタデータの真偽が sidecar と manifest の2箇所に書ける以上、食い違いは
いつか必ず起きる。本テストは「食い違いを検出できること」を合成データで固定し、
実 repo が現時点で分裂していないことを併せて確認する。
"""
from __future__ import annotations

import importlib.util
import json
import pathlib
import subprocess
import sys

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


def rec(name, manifest, sidecar, key="distributable", manifest_key=None, aliases=()):
    """1 plugin 分の採取結果。指定した 1 キー以外は未宣言で埋める。"""
    fields = {
        f["key"]: {"manifest_key": None, "manifest": S, "sidecar": S, "manifest_aliases": []}
        for f in MOD.FIELDS
    }
    fields[key] = {
        "manifest_key": manifest_key or key,
        "manifest": manifest,
        "sidecar": sidecar,
        "manifest_aliases": list(aliases),
    }
    return {"name": name, "fields": fields}


def codes(violations):
    return [v.split(":", 1)[0] for v in violations]


def real_records():
    plugins = ROOT / "plugins"
    return [
        MOD.read_declarations(d)
        for d in sorted(plugins.iterdir())
        if d.is_dir() and (d / ".claude-plugin" / "plugin.json").is_file()
    ]


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
    assert MOD.check_distributable_ssot([rec("p", False, S)]) == []


def test_sidecar_only_is_not_a_violation():
    assert MOD.check_distributable_ssot([rec("p", S, False)]) == []


def test_neither_declared_is_not_a_violation():
    assert MOD.check_distributable_ssot([rec("p", S, S)]) == []


def test_false_is_distinguished_from_missing():
    """False と「キー無し」を同一視すると、明示的な非配布宣言が消える。"""
    assert S is not False
    assert MOD.check_distributable_ssot([rec("p", False, S)]) == []
    assert codes(MOD.check_distributable_ssot([rec("p", False, True)])) == ["DS-001"]


def test_multiple_plugins_are_all_reported():
    out = MOD.check_distributable_ssot(
        [rec("a", True, False), rec("b", False, False), rec("c", False, True)]
    )
    assert codes(out) == ["DS-001", "DS-002", "DS-001"]
    assert "a" in out[0] and "b" in out[1] and "c" in out[2]


def test_real_repository_has_no_split_declaration():
    """実 repo の現状を固定する。赤化したら片方に寄せてから通すこと。"""
    records = real_records()
    assert records, "plugins/ から 1 件も読めていない"
    assert MOD.check_distributable_ssot(records) == []


def test_read_declarations_resolves_sidecar_and_manifest():
    """ubm-goal-setting は sidecar 単独宣言 (DS-002 解消後の正しい形)。

    値そのものは公開方針の変数なので固定しない。固定したいのは
    「sidecar から読めて manifest 側には残っていない」という寄せ先の向き。
    """
    got = MOD.read_declarations(ROOT / "plugins" / "ubm-goal-setting")
    assert got["name"] == "ubm-goal-setting"
    field = got["fields"]["distributable"]
    assert field["manifest"] is S, "manifest 側に distributable が復活している (DS-002)"
    assert field["sidecar"] is not S, "sidecar が正本なので必ず読めるはず"


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
    assert [v for v in MOD.check_distributable_ssot(real_records()) if v.startswith("DS-002")] == []


# --- distributable 以外のキー ---------------------------------------------
# harness_metadata() は bundle_targets / category / tags にも同じ sidecar-first
# fallback を持つ。distributable だけを見る lint は、同種の分裂を 3 キー分見逃す。


@pytest.mark.parametrize("key", ["bundle_targets", "category", "tags"])
def test_other_distribution_keys_are_checked(key):
    out = MOD.check_distributable_ssot([rec("p", ["x"], ["y"], key=key)])
    assert codes(out) == ["DS-001"], out
    assert key in out[0]


def test_bundle_targets_duplicate_is_ds002():
    out = MOD.check_distributable_ssot([rec("p", ["skills-full"], ["skills-full"], key="bundle_targets")])
    assert codes(out) == ["DS-002"], out


def test_manifest_alias_counts_as_a_declaration():
    """manifest 側は bundles / keywords という別名でも読まれる。

    別名で書かれた値は sidecar と食い違っても実効値になり得ないが、書いた側は
    効いているつもりでいる。名前が違うだけで見逃すと分裂の半分を取りこぼす。
    """
    out = MOD.check_distributable_ssot(
        [rec("p", ["a"], ["b"], key="bundle_targets", manifest_key="bundles")]
    )
    assert codes(out) == ["DS-001"], out
    assert "manifest.bundles" in out[0]


def test_manifest_alias_duplicate_is_ds003():
    out = MOD.check_distributable_ssot(
        [rec("p", ["a"], S, key="bundle_targets", aliases=["bundle_targets", "bundles"])]
    )
    assert codes(out) == ["DS-003"], out
    assert "bundles" in out[0]


@pytest.mark.parametrize(
    "aliases,expected",
    [(["bundle_targets"], []), ([], [])],
)
def test_single_alias_is_not_ds003(aliases, expected):
    out = MOD.check_distributable_ssot(
        [rec("p", ["a"], S, key="bundle_targets", aliases=aliases)]
    )
    assert codes(out) == expected, out


# --- 値の同一性判定 --------------------------------------------------------


def test_bool_and_int_are_not_the_same_value():
    """Python の `True == 1` に引きずられると、型違いの食い違いを DS-002 と誤分類する。"""
    assert MOD.same_value(True, 1) is False
    assert MOD.same_value(False, 0) is False
    assert MOD.same_value(True, True) is True
    assert MOD.same_value(1, 1) is True
    out = MOD.check_distributable_ssot([rec("p", 1, True)])
    assert codes(out) == ["DS-001"], out


# --- manifest 側 or_chain の再現 -------------------------------------------


def test_manifest_falsy_value_is_not_a_declaration_for_or_chain_keys(tmp_path: pathlib.Path):
    """manifest の `bundle_targets: []` は harness_metadata() が読み飛ばす値。

    実装が読まない値を「宣言あり」と数えると、sidecar と併記されただけで
    存在しない分裂を報告してしまう。
    """
    plugin = tmp_path / "p"
    (plugin / ".claude-plugin").mkdir(parents=True)
    (plugin / "references").mkdir()
    (plugin / ".claude-plugin" / "plugin.json").write_text(
        json.dumps({"name": "p", "bundle_targets": []}), encoding="utf-8"
    )
    (plugin / "references" / "package-contract.json").write_text(
        json.dumps({"distribution": {"bundle_targets": ["skills-full"]}}), encoding="utf-8"
    )
    got = MOD.read_declarations(plugin)
    assert got["fields"]["bundle_targets"]["manifest"] is S
    assert MOD.check_distributable_ssot([got]) == []


def test_sidecar_empty_list_is_still_a_declaration(tmp_path: pathlib.Path):
    """sidecar 側は `.get(key, fallback)` なので、[] でも「宣言あり」として勝つ。"""
    plugin = tmp_path / "p"
    (plugin / ".claude-plugin").mkdir(parents=True)
    (plugin / "references").mkdir()
    (plugin / ".claude-plugin" / "plugin.json").write_text(
        json.dumps({"name": "p", "bundle_targets": ["skills-full"]}), encoding="utf-8"
    )
    (plugin / "references" / "package-contract.json").write_text(
        json.dumps({"distribution": {"bundle_targets": []}}), encoding="utf-8"
    )
    out = MOD.check_distributable_ssot([MOD.read_declarations(plugin)])
    assert codes(out) == ["DS-001"], out


# --- 走査そのものが壊れたときに緑にしない ----------------------------------


def test_partial_scan_is_not_green(tmp_path: pathlib.Path, monkeypatch):
    """走査が marketplace の名簿を取りこぼしたら OK ではなく exit 2。

    違反 0 件と「そもそも見ていない」は別物。定数の期待件数を埋める代わりに、
    独立した on-disk の名簿と突き合わせる。
    """
    plugins = tmp_path / "plugins"
    (plugins / "alpha" / ".claude-plugin").mkdir(parents=True)
    (plugins / "alpha" / ".claude-plugin" / "plugin.json").write_text(
        json.dumps({"name": "alpha"}), encoding="utf-8"
    )
    marketplace = tmp_path / ".claude-plugin" / "marketplace.json"
    marketplace.parent.mkdir()
    marketplace.write_text(
        json.dumps({"plugins": [{"name": "alpha"}, {"name": "beta"}]}), encoding="utf-8"
    )
    monkeypatch.setattr(MOD, "PLUGINS", plugins)
    monkeypatch.setattr(MOD, "MARKETPLACE", marketplace)
    assert MOD.main() == 2


def test_full_scan_is_green(tmp_path: pathlib.Path, monkeypatch):
    """上のテストが「常に 2」で通っていないことを示す対照。"""
    plugins = tmp_path / "plugins"
    (plugins / "alpha" / ".claude-plugin").mkdir(parents=True)
    (plugins / "alpha" / ".claude-plugin" / "plugin.json").write_text(
        json.dumps({"name": "alpha"}), encoding="utf-8"
    )
    marketplace = tmp_path / ".claude-plugin" / "marketplace.json"
    marketplace.parent.mkdir()
    marketplace.write_text(json.dumps({"plugins": [{"name": "alpha"}]}), encoding="utf-8")
    monkeypatch.setattr(MOD, "PLUGINS", plugins)
    monkeypatch.setattr(MOD, "MARKETPLACE", marketplace)
    assert MOD.main() == 0


def test_real_repository_passes_end_to_end():
    proc = subprocess.run([sys.executable, str(SCRIPT)], capture_output=True, text=True)
    assert proc.returncode == 0, proc.stdout + proc.stderr
