"""scripts/validate-plugin-completeness.py の genuine 機能テスト。

純関数 (load_bundle_members / load_marketplace_entries / collect / validate /
register_missing / run_check) を tmp_path 上に構築した擬似 plugin ツリーで実入力に
より呼び、実出力を assert する。main() は PLUGINS_DIR / BUNDLES_JSON /
MARKETPLACE_JSON / ROOT を monkeypatch で tmp_path へ向け in-process 駆動し、
OK / VIOLATION / PLUGINS_DIR 不在 / --fix(予防層) の returncode を検証する。
network/keychain/Notion 等の外部 I/O は一切なし (純粋なファイル検査スクリプト)。
subprocess 経路は実 repo に対し returncode (0 or 1) を許容範囲で検証する。
"""
import importlib.util
import json
import subprocess
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[2]
SCRIPT = ROOT / "scripts" / "validate-plugin-completeness.py"

SPEC = importlib.util.spec_from_file_location("validate_plugin_completeness_uut", SCRIPT)
MOD = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(MOD)


# --- helpers -----------------------------------------------------------------

def _make_plugin(base: Path, name: str, manifest: dict | None = None,
                 *, skills=(), agents=(), commands=(), hooks=(),
                 scripts=(), config=()) -> Path:
    d = base / name
    d.mkdir(parents=True)
    for s in skills:
        sd = d / "skills" / s
        sd.mkdir(parents=True)
        (sd / "SKILL.md").write_text(f"---\nname: {s}\n---\nbody\n", encoding="utf-8")
    for a in agents:
        (d / "agents").mkdir(exist_ok=True)
        (d / "agents" / a).write_text("agent", encoding="utf-8")
    for c in commands:
        (d / "commands").mkdir(exist_ok=True)
        (d / "commands" / c).write_text("cmd", encoding="utf-8")
    for h in hooks:
        (d / "hooks").mkdir(exist_ok=True)
        (d / "hooks" / h).write_text("#!/bin/sh\n", encoding="utf-8")
    for sc in scripts:
        sd = d / "scripts"
        sd.mkdir(exist_ok=True)
        (sd / sc).write_text("# py\n", encoding="utf-8")
    for cf in config:
        (d / "config").mkdir(exist_ok=True)
        (d / "config" / cf).write_text("{}", encoding="utf-8")
    if manifest is not None:
        md = d / ".claude-plugin"
        md.mkdir(parents=True)
        (md / "plugin.json").write_text(json.dumps(manifest), encoding="utf-8")
    return d


def _mk(*names) -> dict[str, str]:
    """marketplace_entries dict {name: ./plugins/name} を作る簡易ヘルパ。"""
    return {n: f"./plugins/{n}" for n in names}


# --- load_bundle_members -----------------------------------------------------

def test_load_bundle_members_missing_file_returns_empty(tmp_path, monkeypatch):
    monkeypatch.setattr(MOD, "BUNDLES_JSON", tmp_path / "absent.json")
    assert MOD.load_bundle_members() == set()


def test_load_bundle_members_collects_all_plugins(tmp_path, monkeypatch):
    bj = tmp_path / "bundles.json"
    bj.write_text(json.dumps({
        "bundles": [
            {"name": "core", "plugins": ["harness-creator", "skill-intake"]},
            {"name": "extra", "plugins": ["skill-intake", "another"]},
        ]
    }), encoding="utf-8")
    monkeypatch.setattr(MOD, "BUNDLES_JSON", bj)
    assert MOD.load_bundle_members() == {"harness-creator", "skill-intake", "another"}


def test_load_bundle_members_empty_bundles_key(tmp_path, monkeypatch):
    bj = tmp_path / "bundles.json"
    bj.write_text(json.dumps({"bundles": []}), encoding="utf-8")
    monkeypatch.setattr(MOD, "BUNDLES_JSON", bj)
    assert MOD.load_bundle_members() == set()


# --- load_marketplace_entries ------------------------------------------------

def test_load_marketplace_entries_missing_file_returns_empty(tmp_path, monkeypatch):
    monkeypatch.setattr(MOD, "MARKETPLACE_JSON", tmp_path / "absent.json")
    assert MOD.load_marketplace_entries() == {}


def test_load_marketplace_entries_maps_name_to_source(tmp_path, monkeypatch):
    mj = tmp_path / "marketplace.json"
    mj.write_text(json.dumps({"plugins": [
        {"name": "a", "source": "./plugins/a"},
        {"name": "b", "source": "./plugins/b"},
    ]}), encoding="utf-8")
    monkeypatch.setattr(MOD, "MARKETPLACE_JSON", mj)
    assert MOD.load_marketplace_entries() == {"a": "./plugins/a", "b": "./plugins/b"}


# --- collect -----------------------------------------------------------------

def test_collect_enumerates_all_asset_kinds(tmp_path):
    d = _make_plugin(
        tmp_path, "p1",
        manifest={"name": "p1", "version": "1.0.0", "description": "d"},
        skills=["run-a", "run-b"],
        agents=["x.md"],
        commands=["c.md"],
        hooks=["h.sh", "g.py"],
        scripts=["tool.py"],
        config=["conf.json"],
    )
    out = MOD.collect(d)
    assert out["skills"] == ["run-a", "run-b"]
    assert out["agents"] == ["x.md"]
    assert out["commands"] == ["c.md"]
    assert out["hooks"] == ["g.py", "h.sh"]  # sorted
    assert out["scripts"] == ["tool.py"]
    assert out["config"] == ["conf.json"]
    assert out["manifest"]["name"] == "p1"


def test_collect_hooks_filter_only_sh_and_py(tmp_path):
    d = _make_plugin(tmp_path, "p2", manifest={"name": "p2"}, hooks=["a.sh", "b.py"])
    # 非 .sh/.py のファイルを hooks/ に追加 -> 列挙されない
    (d / "hooks" / "readme.txt").write_text("x", encoding="utf-8")
    out = MOD.collect(d)
    assert out["hooks"] == ["a.sh", "b.py"]


def test_collect_manifest_none_when_absent(tmp_path):
    d = _make_plugin(tmp_path, "p3", manifest=None, skills=["run-a"])
    out = MOD.collect(d)
    assert out["manifest"] is None


def test_collect_resolves_plugin_relative_hook_config(tmp_path):
    d = _make_plugin(
        tmp_path,
        "p4",
        manifest={
            "name": "p4",
            "version": "1.0.0",
            "description": "plugin relative hook config",
            "hooks": "./hooks/hooks.json",
        },
        hooks=["guard.py"],
    )
    (d / "hooks" / "hooks.json").write_text(json.dumps({
        "hooks": {
            "PreToolUse": [{
                "hooks": [{
                    "command": "python3 $CLAUDE_PLUGIN_ROOT/hooks/guard.py"
                }]
            }]
        }
    }), encoding="utf-8")

    out = MOD.collect(d)

    assert isinstance(out["manifest"]["hooks"], dict)
    assert out["manifest_hook_error"] is None
    errs = MOD.validate("p4", out, {"p4"}, _mk("p4"))
    assert not any("declares hooks not on disk" in err for err in errs)


def test_collect_reports_invalid_plugin_relative_hook_config(tmp_path):
    d = _make_plugin(
        tmp_path,
        "p5",
        manifest={
            "name": "p5",
            "version": "1.0.0",
            "description": "missing hook config",
            "hooks": "./hooks/missing.json",
        },
        skills=["run-a"],
    )

    out = MOD.collect(d)
    errs = MOD.validate("p5", out, set(), {})

    assert any("manifest hook reference invalid" in err for err in errs)


def test_collect_loads_harness_package_contract_sidecar(tmp_path):
    d = _make_plugin(
        tmp_path,
        "sidecar",
        manifest={"name": "sidecar", "version": "1.0.0", "description": "d"},
        skills=["run-a"],
    )
    (d / "references").mkdir()
    contract = {
        "package_mode": "bundle",
        "plugin_name": "sidecar",
        "entry_points": {"skills": ["run-a"]},
        "distribution": {"distributable": False},
        "pkg_checks": {},
    }
    (d / "references" / "package-contract.json").write_text(
        json.dumps(contract), encoding="utf-8"
    )

    out = MOD.collect(d)

    assert out["package_contract"] == contract
    assert out["package_contract_error"] is None


# --- validate ----------------------------------------------------------------

def _data(manifest, **assets):
    base = {"skills": [], "agents": [], "commands": [],
            "hooks": [], "scripts": [], "config": []}
    base.update(assets)
    base["manifest"] = manifest
    return base


def test_validate_happy_path_no_errors(tmp_path, monkeypatch):
    # MK-002 は ROOT/source の実在を見るため、ROOT を tmp に向け実体を用意する。
    monkeypatch.setattr(MOD, "ROOT", tmp_path)
    (tmp_path / "plugins" / "p").mkdir(parents=True)
    data = _data(
        {"name": "p", "version": "1.0", "description": "d"},
        skills=["run-a"],
    )
    errs = MOD.validate("p", data, {"p"}, _mk("p"))
    assert errs == []


def test_validate_missing_manifest():
    data = _data(None, skills=["run-a"])
    errs = MOD.validate("p", data, {"p"}, _mk("p"))
    assert errs == ["p: .claude-plugin/plugin.json missing"]


def test_validate_missing_required_fields():
    data = _data({"name": "p"}, skills=["run-a"])  # version/description 欠如
    errs = MOD.validate("p", data, {"p"}, _mk("p"))
    assert any("missing 'version'" in e for e in errs)
    assert any("missing 'description'" in e for e in errs)


def test_validate_name_mismatch():
    data = _data(
        {"name": "wrong", "version": "1", "description": "d"},
        skills=["run-a"],
    )
    errs = MOD.validate("p", data, {"p"}, _mk("p"))
    assert any("!= directory name" in e for e in errs)


def test_validate_declared_hook_not_on_disk():
    manifest = {
        "name": "p", "version": "1", "description": "d",
        "hooks": {
            "PreToolUse": [
                {"hooks": [{"command": "python3 $CLAUDE_PLUGIN_ROOT/hooks/guard.py"}]}
            ]
        },
    }
    data = _data(manifest, skills=["run-a"], hooks=[])  # guard.py がディスクに無い
    errs = MOD.validate("p", data, {"p"}, _mk("p"))
    assert any("declares hooks not on disk" in e and "guard.py" in e for e in errs)


def test_validate_declared_hook_present_on_disk_ok(tmp_path, monkeypatch):
    monkeypatch.setattr(MOD, "ROOT", tmp_path)
    (tmp_path / "plugins" / "p").mkdir(parents=True)
    manifest = {
        "name": "p", "version": "1", "description": "d",
        "hooks": {
            "Stop": [
                {"hooks": [{"command": "$CLAUDE_PLUGIN_ROOT/hooks/stop.sh"}]}
            ]
        },
    }
    data = _data(manifest, skills=["run-a"], hooks=["stop.sh"])
    errs = MOD.validate("p", data, {"p"}, _mk("p"))
    assert errs == []


def test_validate_empty_distribution():
    data = _data({"name": "p", "version": "1", "description": "d"})  # 全 asset 空
    errs = MOD.validate("p", data, {"p"}, _mk("p"))
    assert any("no assets" in e for e in errs)


def test_validate_not_in_bundle():
    data = _data(
        {"name": "p", "version": "1", "description": "d"},
        skills=["run-a"],
    )
    errs = MOD.validate("p", data, set(), _mk("p"))  # bundle メンバーでない
    assert any("not registered in any" in e for e in errs)


def test_validate_malformed_hook_command_falls_back_to_split():
    # shlex.split が ValueError を投げる不正コマンド (未閉じクォート) -> cmd.split() fallback
    manifest = {
        "name": "p", "version": "1", "description": "d",
        "hooks": {
            "PreToolUse": [
                {"hooks": [{"command": 'echo "unterminated $CLAUDE_PLUGIN_ROOT/hooks/h.py'}]}
            ]
        },
    }
    data = _data(manifest, skills=["run-a"], hooks=[])
    errs = MOD.validate("p", data, {"p"}, _mk("p"))
    # fallback split でも h.py が抽出され missing として検出される
    assert any("h.py" in e for e in errs)


# --- validate: marketplace 検査 (MK-001/002/003) -----------------------------

def test_validate_mk001_not_in_marketplace():
    data = _data(
        {"name": "p", "version": "1", "description": "d"},
        skills=["run-a"],
    )
    errs = MOD.validate("p", data, {"p"}, {})  # marketplace 未登録
    assert any("(MK-001)" in e for e in errs)


def test_validate_mk002_source_not_existing_dir():
    data = _data(
        {"name": "p", "version": "1", "description": "d"},
        skills=["run-a"],
    )
    # name は登録されているが source が実在しない (実 ROOT 下に ./plugins/p なし)
    errs = MOD.validate("p", data, {"p"}, {"p": "./plugins/p"})
    assert any("(MK-002)" in e for e in errs)


def test_validate_mk003_source_basename_mismatch(tmp_path, monkeypatch):
    monkeypatch.setattr(MOD, "ROOT", tmp_path)
    # source が別ディレクトリを指す取り違え。basename 'other' != 'p'。
    (tmp_path / "plugins" / "other").mkdir(parents=True)
    data = _data(
        {"name": "p", "version": "1", "description": "d"},
        skills=["run-a"],
    )
    errs = MOD.validate("p", data, {"p"}, {"p": "./plugins/other"})
    assert any("(MK-003)" in e for e in errs)
    # basename 取り違えは独立検査であり、name フィールド一致とは別物
    assert not any("(MK-002)" in e for e in errs)  # other は実在するので MK-002 は出ない


# --- validate: distributable:false 逆ガード (MK-004/BD-002) -------------------

def test_validate_distributable_false_no_registration_required():
    # distributable:false (社内専用) は marketplace/bundle 未登録でも
    # 順方向の登録漏れ検査 (MK-001/BD-001) を一切出さない。
    data = _data(
        {"name": "p", "version": "1", "description": "d", "distributable": False},
        skills=["run-a"],
    )
    errs = MOD.validate("p", data, set(), {})  # bundle / marketplace ともに未登録
    assert not any("(MK-001)" in e for e in errs)
    assert not any("(BD-001" in e for e in errs)
    assert errs == []


def test_validate_distributable_false_registered_emits_mk004_bd002():
    # 非配布宣言なのに登録が残存 → 逆ガード MK-004 / BD-002 を出す。
    data = _data(
        {"name": "p", "version": "1", "description": "d", "distributable": False},
        skills=["run-a"],
    )
    errs = MOD.validate("p", data, {"p"}, _mk("p"))  # bundle / marketplace 両方に残存
    assert any("(MK-004)" in e for e in errs)
    assert any("(BD-002)" in e for e in errs)
    # 逆ガード中は順方向の登録漏れ検査は適用されない
    assert not any("(MK-001)" in e for e in errs)
    assert not any("(BD-001" in e for e in errs)


def test_validate_uses_sidecar_distribution_and_entry_points():
    # Native manifest は公式 schema のキーだけで、harness 契約は sidecar が正本。
    data = _data(
        {"name": "p", "version": "1", "description": "d"},
        skills=["run-a"], agents=["audit.md"], commands=["go.md"], hooks=["guard.py"],
    )
    data["package_contract"] = {
        "plugin_name": "p",
        "entry_points": {
            "skills": ["run-a"],
            "agents": ["audit"],
            "commands": ["go"],
            "hooks": ["guard"],
        },
        "distribution": {"distributable": False},
    }

    assert MOD.validate("p", data, set(), {}) == []


def test_validate_sidecar_declared_entry_point_must_exist():
    data = _data(
        {"name": "p", "version": "1", "description": "d"},
        skills=["run-a"],
    )
    data["package_contract"] = {
        "plugin_name": "p",
        "entry_points": {"skills": ["run-a", "run-missing"]},
        "distribution": {"distributable": False},
    }

    errs = MOD.validate("p", data, set(), {})

    assert any("declares skills not on disk" in err and "run-missing" in err for err in errs)


# --- register_missing: 予防層 (--fix のコア) ---------------------------------

def _setup_repo(tmp_path, monkeypatch, *, plugins, marketplace, bundles):
    """tmp に plugins/ marketplace.json bundles.json を構築し globals を向ける。"""
    pdir = tmp_path / "plugins"
    pdir.mkdir(exist_ok=True)
    for name, manifest in plugins.items():
        _make_plugin(pdir, name, manifest=manifest, skills=["run-a"])
    mj = tmp_path / ".claude-plugin" / "marketplace.json"
    mj.parent.mkdir(parents=True, exist_ok=True)
    mj.write_text(json.dumps(marketplace, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    bj = tmp_path / ".claude-plugin" / "bundles.json"
    bj.write_text(json.dumps(bundles, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    monkeypatch.setattr(MOD, "ROOT", tmp_path)
    monkeypatch.setattr(MOD, "PLUGINS_DIR", pdir)
    monkeypatch.setattr(MOD, "MARKETPLACE_JSON", mj)
    monkeypatch.setattr(MOD, "BUNDLES_JSON", bj)
    return mj, bj


def test_register_missing_appends_marketplace_and_bundle(tmp_path, monkeypatch):
    mj, bj = _setup_repo(
        tmp_path, monkeypatch,
        plugins={"new": {"name": "new", "version": "0.1.0", "description": "d",
                          "bundle_targets": ["full"]}},
        marketplace={"plugins": []},
        bundles={"bundles": [{"name": "full", "plugins": []}]},
    )
    actions, changed = MOD.register_missing()
    assert changed is True
    assert any("marketplace.json: + new" in a for a in actions)
    assert any("bundles.json[full]: + new" in a for a in actions)
    # 書込後の検査で new に MK/BD 違反が無いこと
    _, errs = MOD.run_check()
    assert not any("new:" in e for e in errs)
    mk = json.loads(mj.read_text())
    assert any(p["name"] == "new" and p["source"] == "./plugins/new" for p in mk["plugins"])
    bd = json.loads(bj.read_text())
    assert "new" in bd["bundles"][0]["plugins"]


def test_register_missing_idempotent(tmp_path, monkeypatch):
    mj, bj = _setup_repo(
        tmp_path, monkeypatch,
        plugins={"new": {"name": "new", "version": "0.1.0", "description": "d",
                          "bundle_targets": ["full"]}},
        marketplace={"plugins": []},
        bundles={"bundles": [{"name": "full", "plugins": []}]},
    )
    MOD.register_missing()
    actions2, changed2 = MOD.register_missing()  # 2 回目は no-op
    assert changed2 is False
    assert actions2 == []


def test_register_missing_appendonly_preserves_existing_bytes(tmp_path, monkeypatch):
    # 既存エントリ (tags インライン・日本語 description) のバイトが不変であること。
    existing = {
        "plugins": [
            {"name": "old", "source": "./plugins/old",
             "description": "既存の日本語説明", "version": "1.0.0",
             "category": "productivity", "tags": ["a", "b"]},
        ]
    }
    mj, bj = _setup_repo(
        tmp_path, monkeypatch,
        plugins={
            "old": {"name": "old", "version": "1.0.0", "description": "既存の日本語説明",
                     "bundle_targets": ["full"]},
            "new": {"name": "new", "version": "0.1.0", "description": "新規",
                     "bundle_targets": ["full"]},
        },
        marketplace=existing,
        bundles={"bundles": [{"name": "full", "plugins": ["old"]}]},
    )
    before = mj.read_text()
    MOD.register_missing()
    after = mj.read_text()
    # append-only: plugins[] 閉じ括弧より前の既存バイトは after の接頭辞として温存
    cut = before.rfind("\n  ]")
    assert cut != -1
    assert after.startswith(before[:cut])
    assert '"name": "new"' in after
    # 'old' は二重登録されない
    names = [p["name"] for p in json.loads(after)["plugins"]]
    assert names.count("old") == 1


def test_register_missing_unknown_bundle_reports_and_residual_fail(tmp_path, monkeypatch):
    # bundle_targets が存在しない bundle を指す → 自動作成せず警告。BD-001 が残違反。
    _setup_repo(
        tmp_path, monkeypatch,
        plugins={"new": {"name": "new", "version": "0.1.0", "description": "d",
                          "bundle_targets": ["nonexistent"]}},
        marketplace={"plugins": []},
        bundles={"bundles": [{"name": "full", "plugins": []}]},
    )
    actions, _ = MOD.register_missing()
    assert any("bundle 'nonexistent'" in a and "登録不可" in a for a in actions)
    _, errs = MOD.run_check()
    assert any("(BD-001" in e for e in errs)  # bundle 登録は残違反


def test_register_missing_default_note_when_no_category_tags(tmp_path, monkeypatch):
    _setup_repo(
        tmp_path, monkeypatch,
        plugins={"new": {"name": "new", "version": "0.1.0", "description": "d",
                          "bundle_targets": ["full"]}},  # category/tags なし
        marketplace={"plugins": []},
        bundles={"bundles": [{"name": "full", "plugins": []}]},
    )
    actions, _ = MOD.register_missing()
    assert any("PR で要確認" in a for a in actions)


def test_register_missing_skips_distributable_false(tmp_path, monkeypatch):
    # distributable:false の plugin は bundle_targets を宣言していても
    # marketplace/bundle へ自動登録されない (--fix が逆ガードを踏まない証明)。
    mj, bj = _setup_repo(
        tmp_path, monkeypatch,
        plugins={"internal": {"name": "internal", "version": "0.1.0", "description": "d",
                              "distributable": False, "bundle_targets": ["full"]}},
        marketplace={"plugins": []},
        bundles={"bundles": [{"name": "full", "plugins": []}]},
    )
    actions, changed = MOD.register_missing()
    assert changed is False
    assert actions == []
    mk = json.loads(mj.read_text())
    assert all(p["name"] != "internal" for p in mk["plugins"])
    bd = json.loads(bj.read_text())
    assert "internal" not in bd["bundles"][0]["plugins"]


def test_register_missing_skips_sidecar_non_distributable(tmp_path, monkeypatch):
    # 公式 manifest に harness-only key が無くても sidecar の非配布契約を守る。
    mj, bj = _setup_repo(
        tmp_path, monkeypatch,
        plugins={"internal": {"name": "internal", "version": "0.1.0", "description": "d"}},
        marketplace={"plugins": []},
        bundles={"bundles": [{"name": "full", "plugins": []}]},
    )
    plugin_dir = MOD.PLUGINS_DIR / "internal"
    (plugin_dir / "references").mkdir()
    (plugin_dir / "references" / "package-contract.json").write_text(json.dumps({
        "package_mode": "bundle",
        "plugin_name": "internal",
        "entry_points": {"skills": ["run-a"]},
        "distribution": {"distributable": False, "bundle_targets": ["full"]},
        "pkg_checks": {},
    }), encoding="utf-8")

    actions, changed = MOD.register_missing()

    assert (actions, changed) == ([], False)
    assert json.loads(mj.read_text())["plugins"] == []
    assert json.loads(bj.read_text())["bundles"][0]["plugins"] == []


def test_dev_graph_native_manifest_and_sidecar_are_separated():
    plugin_dir = ROOT / "plugins" / "dev-graph"
    manifest = json.loads(
        (plugin_dir / ".claude-plugin" / "plugin.json").read_text(encoding="utf-8")
    )
    contract = json.loads(
        (plugin_dir / "references" / "package-contract.json").read_text(encoding="utf-8")
    )

    assert {"distributable", "entry_points", "depends_on"}.isdisjoint(manifest)
    assert contract["distribution"]["distributable"] is False
    assert contract["depends_on"] == ["system-spec-harness", "system-dev-planner"]
    actual = {
        "skills": sorted(path.parent.name for path in plugin_dir.glob("skills/*/SKILL.md")),
        "agents": sorted(path.stem for path in plugin_dir.glob("agents/*.md")),
        "commands": sorted(path.stem for path in plugin_dir.glob("commands/*.md")),
        "hooks": sorted(
            path.stem for path in plugin_dir.glob("hooks/*")
            if path.suffix in {".py", ".sh"}
        ),
    }
    declared = {
        kind: sorted(Path(name).stem if kind != "skills" else name for name in names)
        for kind, names in contract["entry_points"].items()
    }
    assert declared == actual
    for dependency in contract["depends_on"]:
        assert (ROOT / "plugins" / dependency).is_dir()


# --- _marketplace_entry_block / _insert_marketplace_entry (unit) -------------

def test_marketplace_entry_block_inline_tags_and_japanese():
    block = MOD._marketplace_entry_block(
        "ng", {"description": "日本語の説明", "version": "0.1.0",
               "category": "productivity", "tags": ["x", "y"]})
    assert '"tags": ["x", "y"]' in block       # インライン
    assert "日本語の説明" in block               # ensure_ascii=False
    assert '"source": "./plugins/ng"' in block
    assert block.startswith("    {")            # indent 4


def test_insert_marketplace_entry_is_append_only():
    text = '{\n  "plugins": [\n    {\n      "name": "a"\n    }\n  ]\n}\n'
    block = '    {\n      "name": "b"\n    }'
    out, ok = MOD._insert_marketplace_entry(text, block)
    assert ok is True
    # 既存 'a' エントリまでのバイトは不変
    idx = text.index('"name": "a"')
    assert out[:idx] == text[:idx]
    assert '"name": "b"' in out
    assert json.loads(out)["plugins"] == [{"name": "a"}, {"name": "b"}]


def test_insert_marketplace_entry_marker_absent_returns_false():
    out, ok = MOD._insert_marketplace_entry("not json with marker", "blk")
    assert ok is False


# --- main(): in-process 駆動 -------------------------------------------------

def test_main_plugins_dir_missing_returns_2(tmp_path, monkeypatch, capsys):
    monkeypatch.setattr(MOD, "PLUGINS_DIR", tmp_path / "absent")
    assert MOD.main([]) == 2
    assert "not found" in capsys.readouterr().err


def test_main_all_complete_returns_0(tmp_path, monkeypatch, capsys):
    mj, bj = _setup_repo(
        tmp_path, monkeypatch,
        plugins={"good": {"name": "good", "version": "1", "description": "d"}},
        marketplace={"plugins": [{"name": "good", "source": "./plugins/good"}]},
        bundles={"bundles": [{"plugins": ["good"]}]},
    )
    rc = MOD.main([])
    out = capsys.readouterr().out
    assert rc == 0
    assert "OK: 1 plugin(s) complete" in out
    assert "good: skills=1" in out


def test_main_violation_returns_1(tmp_path, monkeypatch, capsys):
    # bundle 未登録 + marketplace 未登録 + version/description 欠如 -> VIOLATION
    _setup_repo(
        tmp_path, monkeypatch,
        plugins={"bad": {"name": "bad"}},
        marketplace={"plugins": []},
        bundles={"bundles": []},
    )
    rc = MOD.main([])
    captured = capsys.readouterr()
    assert rc == 1
    assert "VIOLATION" in captured.err
    assert "summary: VIOLATION=" in captured.err


def test_main_skips_dotdir_entries(tmp_path, monkeypatch, capsys):
    mj, bj = _setup_repo(
        tmp_path, monkeypatch,
        plugins={"good": {"name": "good", "version": "1", "description": "d"}},
        marketplace={"plugins": [{"name": "good", "source": "./plugins/good"}]},
        bundles={"bundles": [{"plugins": ["good"]}]},
    )
    (MOD.PLUGINS_DIR / ".hidden").mkdir()  # dot-dir は無視
    rc = MOD.main([])
    out = capsys.readouterr().out
    assert rc == 0
    assert ".hidden" not in out
    assert "OK: 1 plugin(s)" in out


def test_main_fix_registers_and_self_revalidates_exit0(tmp_path, monkeypatch, capsys):
    _setup_repo(
        tmp_path, monkeypatch,
        plugins={"new": {"name": "new", "version": "0.1.0", "description": "d",
                          "bundle_targets": ["full"]}},
        marketplace={"plugins": []},
        bundles={"bundles": [{"name": "full", "plugins": []}]},
    )
    rc = MOD.main(["--fix"])
    out = capsys.readouterr().out
    assert rc == 0                       # 書込後の自己再検証で exit 0
    assert "--fix OK" in out
    assert "+ new" in out


def test_main_fix_residual_violation_returns_1(tmp_path, monkeypatch, capsys):
    # bundle_targets が存在しない bundle → --fix 後も BD-001 残違反で exit 1
    _setup_repo(
        tmp_path, monkeypatch,
        plugins={"new": {"name": "new", "version": "0.1.0", "description": "d",
                          "bundle_targets": ["nonexistent"]}},
        marketplace={"plugins": []},
        bundles={"bundles": [{"name": "full", "plugins": []}]},
    )
    rc = MOD.main(["--fix"])
    err = capsys.readouterr().err
    assert rc == 1
    assert "残違反あり" in err


def test_main_fix_noop_when_all_registered(tmp_path, monkeypatch, capsys):
    _setup_repo(
        tmp_path, monkeypatch,
        plugins={"good": {"name": "good", "version": "1", "description": "d",
                           "bundle_targets": ["full"]}},
        marketplace={"plugins": [{"name": "good", "source": "./plugins/good"}]},
        bundles={"bundles": [{"name": "full", "plugins": ["good"]}]},
    )
    rc = MOD.main(["--fix"])
    out = capsys.readouterr().out
    assert rc == 0
    assert "no-op" in out


# --- subprocess: 実 repo に対して実行 (returncode は 0 or 1 を許容) ----------

def test_subprocess_runs_on_real_repo():
    proc = subprocess.run(
        [sys.executable, str(SCRIPT)],
        capture_output=True, text=True,
    )
    # 実 repo の状態に依存するため returncode は 0(完全) or 1(違反) を許容。
    # いずれにせよ summary 区切り "---" を必ず stdout に出す。
    assert proc.returncode in (0, 1)
    assert "---" in proc.stdout


def test_real_internal_creator_plugins_are_not_distributed():
    marketplace = MOD.load_marketplace_entries()
    bundle_members = MOD.load_bundle_members()
    for name in ("harness-creator", "prompt-creator"):
        manifest_path = ROOT / "plugins" / name / ".claude-plugin" / "plugin.json"
        manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
        assert manifest["distributable"] is False
        assert name not in marketplace
        assert name not in bundle_members


# --- NEVER_DISTRIBUTE: 固有名 denylist (フラグ漂流時の fail-closed 多層防御) -----

def test_never_distribute_contains_creator_plugins():
    # 恒久非配布の固有名が denylist に焼き込まれていること。
    assert "harness-creator" in MOD.NEVER_DISTRIBUTE
    assert "prompt-creator" in MOD.NEVER_DISTRIBUTE


def test_never_distribute_members_exist_on_disk():
    # denylist の各固有名が plugins/ 直下に実在すること。plugin 改名で旧名が denylist に
    # 残ると新名 plugin が denylist 外の通常 plugin として素通りし、二重ロックが無音失効
    # する — 存在しない名前の残置自体を FAIL にして改名時の更新漏れを fail-closed 化する。
    for name in MOD.NEVER_DISTRIBUTE:
        assert (ROOT / "plugins" / name).is_dir(), (
            f"NEVER_DISTRIBUTE の {name!r} が plugins/ に存在しない: "
            "plugin 改名時は denylist を同一 commit で更新すること"
        )


def test_never_distribute_true_flag_drift_emits_violation():
    # NEVER_DISTRIBUTE plugin が distributable:true へ漂流したら、フラグ駆動の逆ガードが
    # 無効化されても固有名検査が NEVER-DISTRIBUTE 違反を出す (fail-closed)。
    data = _data(
        {"name": "harness-creator", "version": "1", "description": "d",
         "distributable": True},
        skills=["run-a"],
    )
    errs = MOD.validate("harness-creator", data, set(), {})
    assert any("(NEVER-DISTRIBUTE)" in e for e in errs)


def test_never_distribute_missing_flag_emits_violation():
    # distributable キー欠落 (= 未宣言 True 扱い) でも NEVER-DISTRIBUTE 違反になる。
    data = _data(
        {"name": "prompt-creator", "version": "1", "description": "d"},
        skills=["run-a"],
    )
    errs = MOD.validate("prompt-creator", data, set(), {})
    assert any("(NEVER-DISTRIBUTE)" in e for e in errs)


def test_never_distribute_false_flag_no_violation():
    # 正常系: distributable:false を明示宣言していれば NEVER-DISTRIBUTE 違反は出ない。
    data = _data(
        {"name": "harness-creator", "version": "1", "description": "d",
         "distributable": False},
        skills=["run-a"],
    )
    errs = MOD.validate("harness-creator", data, set(), {})
    assert not any("(NEVER-DISTRIBUTE)" in e for e in errs)


def test_fix_does_not_register_never_distribute_on_flag_drift(tmp_path, monkeypatch, capsys):
    # NEVER_DISTRIBUTE plugin が distributable:true へ漂流していても、--fix は
    # marketplace.json へ自動登録せず、固有名検査の残違反で returncode 1 を返す。
    mj, bj = _setup_repo(
        tmp_path, monkeypatch,
        plugins={"harness-creator": {"name": "harness-creator", "version": "0.1.0",
                                   "description": "d", "distributable": True,
                                   "bundle_targets": ["full"]}},
        marketplace={"plugins": []},
        bundles={"bundles": [{"name": "full", "plugins": []}]},
    )
    rc = MOD.main(["--fix"])
    err = capsys.readouterr().err
    assert rc == 1
    assert any("(NEVER-DISTRIBUTE)" in line for line in err.splitlines())
    # marketplace/bundle へは自動登録されていない (--fix が固有名を skip)
    mk = json.loads(mj.read_text())
    assert all(p["name"] != "harness-creator" for p in mk["plugins"])
    bd = json.loads(bj.read_text())
    assert "harness-creator" not in bd["bundles"][0]["plugins"]
