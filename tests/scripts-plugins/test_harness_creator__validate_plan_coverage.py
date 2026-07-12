"""plugins/harness-creator/scripts/validate-plan-coverage.py の genuine 機能テスト。

計画 (component-inventory.json) ↔ plugin 実体の completeness 照合器の全分岐を
tmp_path で網羅する。network/keychain/実 repo 書換なし (全 tmp_path)。

カバー分岐:
- _plugin_root_of: plugins/<plugin>/... 抽出 / plugins/ 外 → None
- _target_exists: skill dir (SKILL.md 有/無) / 単一ファイル (有/無)
- verify: 全実在 / component 欠落 / build_target 未宣言 / component が object でない /
          required surface 欠落 / path 無し required surface skip / 複数 plugin 跨ぎ /
          空 components
- main: --self-test / usage(引数なし) / inventory 不在 / JSON parse error /
        non-dict root / 正常 OK(exit0) / FAIL(exit1) / --json(ok=false) / --all(exit0/1)
- verify_all (--all sweep): 実体化済み plan の pass / 漏れ fail-closed / 未 build plan skip /
        plugin-plans 不在。実体化前の計画を誤 FAIL しない自動スコープ限定を回帰固定。
"""
import importlib.util
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
SCRIPT = ROOT / "plugins" / "harness-creator" / "scripts" / "validate-plan-coverage.py"

SPEC = importlib.util.spec_from_file_location("validate_plan_coverage_uut", SCRIPT)
MOD = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(MOD)


def _make_plugin(root: Path, *, skill=True, agent=True, script=True,
                 manifest=True, composition=True):
    """tmp_path に demo plugin 実体を作る (フラグで欠落を再現)。"""
    if skill:
        (root / "plugins/demo/skills/run-demo").mkdir(parents=True, exist_ok=True)
        (root / "plugins/demo/skills/run-demo/SKILL.md").write_text("x", encoding="utf-8")
    if agent:
        (root / "plugins/demo/agents").mkdir(parents=True, exist_ok=True)
        (root / "plugins/demo/agents/demo-verifier.md").write_text("x", encoding="utf-8")
    if script:
        (root / "plugins/demo/scripts").mkdir(parents=True, exist_ok=True)
        (root / "plugins/demo/scripts/demo-check.py").write_text("x", encoding="utf-8")
    if manifest:
        (root / "plugins/demo/.claude-plugin").mkdir(parents=True, exist_ok=True)
        (root / "plugins/demo/.claude-plugin/plugin.json").write_text("{}", encoding="utf-8")
    if composition:
        (root / "plugins/demo/plugin-composition.yaml").write_text("x", encoding="utf-8")


def _inv():
    return {
        "components": [
            {"id": "C01", "component_kind": "skill", "build_target": "plugins/demo/skills/run-demo/"},
            {"id": "C04", "component_kind": "sub-agent", "build_target": "plugins/demo/agents/demo-verifier.md"},
            {"id": "C09", "component_kind": "script", "build_target": "plugins/demo/scripts/demo-check.py"},
        ],
        "plugin_level_surfaces": {
            "manifest": {"required": True, "path": ".claude-plugin/plugin.json"},
            "composition": {"required": True, "path": "plugin-composition.yaml"},
            "schemas": {"required": False, "omitted_reason": "n/a"},
            "notion_config": {"required": True, "resolution": "notion_config"},
        },
    }


# ── _plugin_root_of ─────────────────────────────────────────────────────────
def test_plugin_root_of_extracts():
    assert MOD._plugin_root_of("plugins/demo/skills/x/") == "plugins/demo"


def test_plugin_root_of_non_plugins_returns_none():
    assert MOD._plugin_root_of("other/demo/x") is None


# ── _target_exists ──────────────────────────────────────────────────────────
def test_target_exists_skill_needs_skill_md(tmp_path):
    _make_plugin(tmp_path)
    ok, _ = MOD._target_exists(tmp_path, "plugins/demo/skills/run-demo/", "skill")
    assert ok
    (tmp_path / "plugins/demo/skills/run-demo/SKILL.md").unlink()
    ok, detail = MOD._target_exists(tmp_path, "plugins/demo/skills/run-demo/", "skill")
    assert not ok and "SKILL.md" in detail


def test_target_exists_file_missing(tmp_path):
    ok, detail = MOD._target_exists(tmp_path, "plugins/demo/agents/x.md", "sub-agent")
    assert not ok and "ファイル不在" in detail


# ── verify ──────────────────────────────────────────────────────────────────
def test_verify_all_present(tmp_path):
    _make_plugin(tmp_path)
    mc, ms, summ = MOD.verify(_inv(), tmp_path)
    assert not mc and not ms
    assert "notion_config" in summ["surfaces_skipped"]


def test_verify_missing_component(tmp_path):
    _make_plugin(tmp_path, agent=False)
    mc, _, _ = MOD.verify(_inv(), tmp_path)
    assert any("C04" in e for e in mc)


def test_verify_missing_surface(tmp_path):
    _make_plugin(tmp_path, composition=False)
    _, ms, _ = MOD.verify(_inv(), tmp_path)
    assert any("composition" in e for e in ms)


def test_verify_build_target_undeclared(tmp_path):
    mc, _, _ = MOD.verify({"components": [{"id": "Cx", "component_kind": "hook"}]}, tmp_path)
    assert any("Cx" in e and "build_target" in e for e in mc)


def test_verify_component_not_object(tmp_path):
    mc, _, _ = MOD.verify({"components": ["oops"]}, tmp_path)
    assert any("object でない" in e for e in mc)


def test_verify_multi_plugin_span_path_surface_unresolvable(tmp_path):
    # cross-plugin inventory + plugin-relative path surface: root を一意解決できないと報告
    inv = {
        "components": [
            {"id": "C1", "component_kind": "script", "build_target": "plugins/a/scripts/x.py"},
            {"id": "C2", "component_kind": "script", "build_target": "plugins/b/scripts/y.py"},
        ],
        "plugin_level_surfaces": {"manifest": {"required": True, "path": ".claude-plugin/plugin.json"}},
    }
    _, ms, _ = MOD.verify(inv, tmp_path)
    assert any("一意解決できない" in e for e in ms)


def test_verify_multi_plugin_span_targets_surface_checked(tmp_path):
    # cross-plugin inventory + targets[] surface: repo-relative で各 target を直接照合 (C7)
    (tmp_path / "plugins" / "a" / "scripts").mkdir(parents=True)
    (tmp_path / "plugins" / "a" / "scripts" / "x.py").write_text("x", encoding="utf-8")
    (tmp_path / "plugins" / "b" / "scripts").mkdir(parents=True)
    (tmp_path / "plugins" / "b" / "scripts" / "y.py").write_text("y", encoding="utf-8")
    (tmp_path / "plugins" / "a" / "refs").mkdir(parents=True)
    (tmp_path / "plugins" / "a" / "refs" / "z.md").write_text("z", encoding="utf-8")
    inv = {
        "components": [
            {"id": "C1", "component_kind": "script", "build_target": "plugins/a/scripts/x.py"},
            {"id": "C2", "component_kind": "script", "build_target": "plugins/b/scripts/y.py"},
        ],
        "plugin_level_surfaces": {
            "ref": {"required": True, "targets": ["plugins/a/refs/z.md", "plugins/b/vendor/missing.py"]},
        },
    }
    _, ms, _ = MOD.verify(inv, tmp_path)
    # 実在する z.md は通り、不在の missing.py だけ検出される (cross-plugin でも照合実行)
    assert any("missing.py 不在" in e for e in ms)
    assert not any("z.md 不在" in e for e in ms)
    assert not any("一意解決できない" in e for e in ms)


def test_verify_empty(tmp_path):
    mc, ms, _ = MOD.verify({"components": [], "plugin_level_surfaces": {}}, tmp_path)
    assert not mc and not ms


# ── main (CLI) ──────────────────────────────────────────────────────────────
def test_main_self_test():
    assert MOD.main(["--self-test"]) == 0


def test_main_usage_no_args():
    assert MOD.main([]) == 2


def test_main_inventory_missing(tmp_path):
    assert MOD.main([str(tmp_path / "nope.json")]) == 2


def test_main_json_parse_error(tmp_path):
    p = tmp_path / "bad.json"
    p.write_text("{not json", encoding="utf-8")
    assert MOD.main([str(p)]) == 2


def test_main_non_dict_root(tmp_path):
    p = tmp_path / "arr.json"
    p.write_text("[]", encoding="utf-8")
    assert MOD.main([str(p)]) == 2


def test_main_ok(tmp_path):
    _make_plugin(tmp_path)
    p = tmp_path / "inv.json"
    p.write_text(json.dumps(_inv()), encoding="utf-8")
    assert MOD.main([str(p), "--repo-root", str(tmp_path)]) == 0


def test_main_fail(tmp_path):
    _make_plugin(tmp_path, agent=False)
    p = tmp_path / "inv.json"
    p.write_text(json.dumps(_inv()), encoding="utf-8")
    assert MOD.main([str(p), "--repo-root", str(tmp_path)]) == 1


def test_main_json_flag(tmp_path, capsys):
    _make_plugin(tmp_path, agent=False)
    p = tmp_path / "inv.json"
    p.write_text(json.dumps(_inv()), encoding="utf-8")
    rc = MOD.main([str(p), "--repo-root", str(tmp_path), "--json"])
    out = json.loads(capsys.readouterr().out)
    assert rc == 1 and out["ok"] is False
    assert any("C04" in e for e in out["missing_components"])


# ── verify_all / --all sweep (CI 常設 fail-closed ガード) ─────────────────────
def _write_plan(root, slug, inv):
    d = root / "plugin-plans" / slug
    d.mkdir(parents=True, exist_ok=True)
    (d / "component-inventory.json").write_text(json.dumps(inv), encoding="utf-8")


def test_verify_all_realized_ok(tmp_path):
    """対象 plugin が実体化済み & 全 component build 済 → gated_ok・漏れなし。"""
    _make_plugin(tmp_path)  # plugins/demo/... を build 実体化 + manifest/composition
    _write_plan(tmp_path, "demo", _inv())
    failures, ok_list, skipped = MOD.verify_all(tmp_path)
    assert not failures
    assert any(p.endswith("demo/component-inventory.json") for p in ok_list)
    assert not skipped


def test_verify_all_realized_gap_fails_closed(tmp_path):
    """plugin root は在るが計画 component が欠落 → fail-closed で検出。"""
    _make_plugin(tmp_path, agent=False)  # demo-verifier.md を作らない
    _write_plan(tmp_path, "demo", _inv())
    failures, ok_list, _ = MOD.verify_all(tmp_path)
    assert any("C04" in e for f in failures for e in f["missing_components"])
    assert not ok_list
    assert MOD._run_all(tmp_path, as_json=True) == 1


def test_verify_all_unbuilt_plan_skipped(tmp_path):
    """対象 plugin ディレクトリが不在 (未 build 計画) → 誤 FAIL せず skip。"""
    _write_plan(tmp_path, "demo", _inv())  # plugins/demo/ は作らない
    failures, ok_list, skipped = MOD.verify_all(tmp_path)
    assert not failures and not ok_list
    assert any("demo" in s for s in skipped)
    assert MOD._run_all(tmp_path, as_json=True) == 0


def test_verify_all_no_plans_dir_ok(tmp_path):
    """plugin-plans/ 自体が無い → 対象なしで OK。"""
    assert MOD.verify_all(tmp_path) == ([], [], [])
    assert MOD._run_all(tmp_path, as_json=True) == 0


def test_verify_all_malformed_prefix_fails_closed(tmp_path):
    """build_target が plugins/ 配下でない inventory は skip でなく malformed failure。"""
    _write_plan(tmp_path, "bad", {
        "components": [{"id": "C1", "component_kind": "script", "build_target": "scripts/toplevel.py"}],
        "plugin_level_surfaces": {},
    })
    failures, ok_list, skipped = MOD.verify_all(tmp_path)
    assert any("malformed" in e for f in failures for e in f["missing_components"])
    assert not skipped and not ok_list


def test_verify_all_planned_extension_plan_skipped_despite_realized_root(tmp_path):
    """build_status=planned の未 build 拡張計画: plugin root が実在し component gap があっても
    計画ドキュメント宣言として skip され failure に入らない (既存 plugin 拡張計画の非対称是正)。"""
    _make_plugin(tmp_path, agent=False)  # demo-verifier.md 欠落 = realized なら本来 gap
    inv = _inv()
    inv["build_status"] = "planned"
    _write_plan(tmp_path, "demo", inv)
    failures, ok_list, skipped = MOD.verify_all(tmp_path)
    assert not failures  # planned は gap があっても fail-closed 対象外
    assert not ok_list
    assert any("demo" in s and "planned" in s for s in skipped), skipped
    assert MOD._run_all(tmp_path, as_json=True) == 0


def test_verify_all_draft_status_also_skipped(tmp_path):
    """build_status=draft も未 build 状態として skip (状態集合 _NOT_BUILT_STATES)。"""
    inv = _inv()
    inv["build_status"] = "draft"
    _write_plan(tmp_path, "demo", inv)  # plugins/demo/ 未 build
    failures, _ok, skipped = MOD.verify_all(tmp_path)
    assert not failures
    assert any("demo" in s and "draft" in s for s in skipped), skipped


def test_verify_all_unknown_status_not_skipped_and_gated(tmp_path):
    """build_status が未 build 状態でない (例 realized) 場合は従来通り fail-closed 照合する。"""
    _make_plugin(tmp_path, agent=False)  # gap を作る
    inv = _inv()
    inv["build_status"] = "realized"
    _write_plan(tmp_path, "demo", inv)
    failures, _ok, skipped = MOD.verify_all(tmp_path)
    assert any("C04" in e for f in failures for e in f["missing_components"])
    assert not any("demo" in s for s in skipped)


def test_main_all_rejects_positional(tmp_path):
    """--all と単一 inventory 位置引数の併存は排他 usage error (exit 2)。silent 優先しない。"""
    assert MOD.main(["--all", "some-inv.json"]) == 2
    assert MOD.main(["--all", "--repo-root", str(tmp_path)]) == 0


def test_main_all_flag_realized_gap(tmp_path):
    """main(--all) 経由でも実体化済み plan の漏れを exit 1 で報告する。"""
    _make_plugin(tmp_path, agent=False)
    _write_plan(tmp_path, "demo", _inv())
    assert MOD.main(["--all", "--repo-root", str(tmp_path)]) == 1
    # 未 build 計画は skip → exit 0
    _make_plugin(tmp_path)  # 欠落を埋めて実体化完了
    assert MOD.main(["--all", "--repo-root", str(tmp_path)]) == 0
