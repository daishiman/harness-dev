"""check-build-handoff.py の機能テスト (per-phase 転換)。

routes は component-inventory.json 由来。route.spec は参照する phase ファイル (任意・推奨は
phase-05-implementation.md)。旧 本数固定/derived_count/force_13 ブロックは削除された。
"""
from __future__ import annotations

import json

from conftest import component_entry, write_inventory, write_phase_spec


def _write_plan(tmp_path, overrides: dict | None = None):
    # route.spec が参照する phase ファイル (実装フェーズ) を用意する (spec 実在検査用)。
    write_phase_spec(tmp_path, 5)
    draft_dir = tmp_path / "envelope-draft"
    draft_dir.mkdir()
    (draft_dir / "plugin.json").write_text(
        json.dumps({"name": "sample-plugin", "version": "0.1.0", "description": "sample"}, ensure_ascii=False),
        encoding="utf-8",
    )
    data = {
        "plan_dir": str(tmp_path),
        "target_plugin_slug": "sample-plugin",
        "mode": "create",
        # task-graph はデフォルト成果物 (§9)。task-graph.json 実体は本 fixture に置かないため
        # _check_task_graph_ref は shape-only 検証となる (file 不在は validate-task-graph の責務)。
        "task_graph_ref": {"path": "task-graph.json", "schema_version": "1.0"},
        "routes": [
            {
                "id": "C01",
                "component_kind": "skill",
                "name": "run-sample",
                "spec": "phase-05-implementation.md",
                "depends_on": [],
                "builder": "run-skill-create",
                "build_kind": "skill",
                "build_args": {"skill_name": "run-sample", "kind": "run"},
                "build_target": "plugins/sample-plugin/skills/run-sample/",
                "status": "planned",
            },
            {
                "id": "C02",
                "component_kind": "sub-agent",
                "name": "sample-verifier",
                "spec": "phase-05-implementation.md",
                "depends_on": ["C01"],
                "builder": "run-build-skill",
                "build_kind": "agent",
                "build_args": {"kind": "agent", "name": "sample-verifier"},
                "build_target": "plugins/sample-plugin/agents/sample-verifier.md",
                "status": "planned",
            },
        ],
        "envelope": {
            "manifest": {
                "owner": "plugin-scaffold",
                "status": "external_gap",
                "build_target": "plugins/sample-plugin/.claude-plugin/plugin.json",
                "draft_path": "envelope-draft/plugin.json",
                "gap_reason": "scaffold executor is external",
            }
        },
    }
    if overrides:
        data.update(overrides)
    path = tmp_path / "handoff-run-plugin-dev-plan.json"
    path.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")
    return path, data


def _write_inventory_for_handoff(tmp_path):
    c01 = component_entry(
        "C01", "skill",
        overrides={
            "name": "run-sample",
            "build_target": "plugins/sample-plugin/skills/run-sample/",
            "build_args": {"skill_name": "run-sample", "kind": "run"},
        },
    )
    c02 = component_entry(
        "C02", "sub-agent",
        depends_on=["C01"],
        overrides={
            "name": "sample-verifier",
            "build_target": "plugins/sample-plugin/agents/sample-verifier.md",
            "build_args": {"kind": "agent", "name": "sample-verifier"},
        },
    )
    write_inventory(tmp_path, [c01, c02])


def test_clean_handoff(tmp_path, handoff):
    path, data = _write_plan(tmp_path)
    assert handoff.validate_handoff(data, path) == []
    assert handoff.main([str(path)]) == 0


def test_inventory_provenance_compares_depends_on(tmp_path, handoff):
    path, data = _write_plan(tmp_path)
    _write_inventory_for_handoff(tmp_path)
    data["routes"][1]["depends_on"] = []
    errs = handoff.validate_handoff(data, path)
    assert any("depends_on" in e and "inventory" in e for e in errs)


def test_inventory_provenance_compares_build_args(tmp_path, handoff):
    path, data = _write_plan(tmp_path)
    _write_inventory_for_handoff(tmp_path)
    data["routes"][1]["build_args"] = {"kind": "agent", "name": "other"}
    errs = handoff.validate_handoff(data, path)
    assert any("build_args" in e and "inventory" in e for e in errs)


def test_builder_mismatch_fails(tmp_path, handoff):
    path, data = _write_plan(tmp_path)
    data["routes"][0]["builder"] = "run-build-skill"
    errs = handoff.validate_handoff(data, path)
    assert any("builder=run-skill-create" in e for e in errs)


def test_build_kind_mismatch_fails(tmp_path, handoff):
    path, data = _write_plan(tmp_path)
    data["routes"][1]["build_kind"] = "sub-agent"
    errs = handoff.validate_handoff(data, path)
    assert any("build_kind=agent" in e for e in errs)


def test_run_build_skill_args_kind_mismatch_fails(tmp_path, handoff):
    path, data = _write_plan(tmp_path)
    data["routes"][1]["build_args"]["kind"] = "command"
    errs = handoff.validate_handoff(data, path)
    assert any("build_args.kind" in e for e in errs)


def _plugin_root_script_route() -> dict:
    # plugin-scaffold は contract-only builder ゆえ builder_status 明示 + open_issues の
    # gap id への gap_ref を携帯する (check-build-handoff の fail-closed 強制)。
    return {
        "id": "C09",
        "component_kind": "script",
        "name": "validate-payload.py",
        "spec": "phase-05-implementation.md",
        "depends_on": [],
        "placement_scope": "plugin-root",
        "builder": "plugin-scaffold",
        "builder_status": "contract-only",
        "gap_ref": "GAP-SCRIPT-BUILDER",
        "build_kind": "script",
        "build_args": {"script_path": "scripts/validate-payload.py"},
        "build_target": "plugins/sample-plugin/scripts/validate-payload.py",
        "status": "planned",
    }


_SCRIPT_BUILDER_GAP = [{
    "id": "GAP-SCRIPT-BUILDER",
    "severity": "medium",
    "text": "script builder (plugin-scaffold/parent-skill-build) is contract-only",
}]


def test_plugin_root_script_route_clean(tmp_path, handoff):
    """plugin-root script route (builder=plugin-scaffold・build_args.script_path) が通る。"""
    route = _plugin_root_script_route()
    path, data = _write_plan(tmp_path, {"routes": [route], "open_issues": _SCRIPT_BUILDER_GAP})
    assert handoff.validate_handoff(data, path) == []
    assert handoff.main([str(path)]) == 0


def test_plugin_root_script_wrong_builder_fails(tmp_path, handoff):
    """plugin-root script が parent-skill-build のままだと builder 不整合で弾かれる。"""
    route = _plugin_root_script_route()
    route["builder"] = "parent-skill-build"
    path, data = _write_plan(tmp_path, {"routes": [route]})
    errs = handoff.validate_handoff(data, path)
    assert any("builder=plugin-scaffold" in e for e in errs)


def test_plugin_scaffold_route_needs_script_path(tmp_path, handoff):
    """plugin-scaffold route は build_args.script_path 必須。"""
    route = _plugin_root_script_route()
    route["build_args"] = {"parent_skill": "run-x"}  # script_path 欠落
    path, data = _write_plan(tmp_path, {"routes": [route]})
    errs = handoff.validate_handoff(data, path)
    assert any("script_path" in e for e in errs)


# ─────────────────── 二相 build 順序 (requires_parent_scaffold・M2) ───────────────────
def _skill_with_child_script_routes(parent_ref: str = "C01") -> list[dict]:
    """親 skill C01 と、その build_target 配下に置かれる placement=skill script C09。

    C09 (parent-skill-build) は build_target が C01 (run-skill-create) の dir 配下ゆえ二相 build の
    順序逆転が生じる。requires_parent_scaffold で親 skill id を宣言する契約を検証するための fixture。
    """
    script = {
        "id": "C09", "component_kind": "script", "name": "validate.py",
        "spec": "phase-05-implementation.md", "depends_on": [],
        "placement_scope": "skill",
        "builder": "parent-skill-build", "builder_status": "contract-only",
        "gap_ref": "GAP-SCRIPT-BUILDER", "build_kind": "script",
        "build_args": {"parent_skill": "run-sample", "script_path": "scripts/validate.py"},
        "build_target": "plugins/sample-plugin/skills/run-sample/scripts/validate.py",
        "status": "planned",
        "requires_parent_scaffold": parent_ref,
    }
    skill = {
        "id": "C01", "component_kind": "skill", "name": "run-sample",
        "spec": "phase-05-implementation.md", "depends_on": ["C09"],
        "builder": "run-skill-create", "build_kind": "skill",
        "build_args": {"skill_name": "run-sample", "kind": "run"},
        "build_target": "plugins/sample-plugin/skills/run-sample/",
        "status": "planned",
    }
    return [script, skill]  # script を先に (skill が depends_on するため top-sort 準拠)


def test_parent_scaffold_declared_passes(tmp_path, handoff):
    """placement=skill script が requires_parent_scaffold で親 skill を宣言していれば通る。"""
    routes = _skill_with_child_script_routes("C01")
    path, data = _write_plan(tmp_path, {"routes": routes, "open_issues": _SCRIPT_BUILDER_GAP})
    assert handoff.validate_handoff(data, path) == []
    assert handoff.main([str(path)]) == 0


def test_parent_scaffold_missing_fails(tmp_path, handoff):
    """親 skill 配下 script が requires_parent_scaffold を欠くと二相 build 順序未宣言で弾かれる。"""
    routes = _skill_with_child_script_routes("C01")
    del routes[0]["requires_parent_scaffold"]
    path, data = _write_plan(tmp_path, {"routes": routes, "open_issues": _SCRIPT_BUILDER_GAP})
    errs = handoff.validate_handoff(data, path)
    assert any("requires_parent_scaffold" in e and "明示" in e for e in errs)


def test_parent_scaffold_wrong_parent_fails(tmp_path, handoff):
    """requires_parent_scaffold が build_target を内包する親 skill を指さないと弾かれる。"""
    routes = _skill_with_child_script_routes("C99")
    path, data = _write_plan(tmp_path, {"routes": routes, "open_issues": _SCRIPT_BUILDER_GAP})
    errs = handoff.validate_handoff(data, path)
    assert any("requires_parent_scaffold" in e and "いずれでもない" in e for e in errs)


def test_plugin_root_script_needs_no_parent_scaffold(tmp_path, handoff):
    """plugin-root へ hoist した共有 script は親 skill 配下でないため requires_parent_scaffold 不要。"""
    route = _plugin_root_script_route()  # build_target=plugins/sample-plugin/scripts/... (skill 配下でない)
    path, data = _write_plan(tmp_path, {"routes": [route], "open_issues": _SCRIPT_BUILDER_GAP})
    assert handoff.validate_handoff(data, path) == []


# ─────────────────── builder_status (executor gap の無音隠蔽防止) ───────────────────
def test_contract_only_route_requires_status_and_gap_ref(tmp_path, handoff):
    """contract-only builder の route は builder_status 明示 + gap_ref を欠くと弾かれる。"""
    route = _plugin_root_script_route()
    del route["builder_status"]
    del route["gap_ref"]
    path, data = _write_plan(tmp_path, {"routes": [route], "open_issues": _SCRIPT_BUILDER_GAP})
    errs = handoff.validate_handoff(data, path)
    assert any("builder_status: contract-only を明示宣言" in e for e in errs)
    assert any("gap_ref" in e and "必須" in e for e in errs)


def test_contract_only_gap_ref_must_exist_in_open_issues(tmp_path, handoff):
    """gap_ref が open_issues[].id に無い (起票漏れ) は fail-closed で弾く。"""
    route = _plugin_root_script_route()
    path, data = _write_plan(tmp_path, {"routes": [route]})  # open_issues 無し
    errs = handoff.validate_handoff(data, path)
    assert any("open_issues[].id に存在しない" in e for e in errs)


def test_builder_status_enum_violation_fails(tmp_path, handoff):
    """builder_status は specfm.BUILDER_STATUSES の enum のみ許容。"""
    route = _plugin_root_script_route()
    route["builder_status"] = "half-baked"
    path, data = _write_plan(tmp_path, {"routes": [route], "open_issues": _SCRIPT_BUILDER_GAP})
    errs = handoff.validate_handoff(data, path)
    assert any("builder_status" in e and "enum 外" in e for e in errs)


def test_task_graph_ref_required(tmp_path, handoff):
    """task-graph はデフォルト成果物 (§9) ゆえ `task_graph_ref` 未設定は fail-closed で弾く
    (build を linear route mode へ退化させない=成果物=タスクグラフの機械強制)。"""
    path, data = _write_plan(tmp_path)
    del data["task_graph_ref"]
    errs = handoff.validate_handoff(data, path)
    assert any("task_graph_ref が未設定" in e for e in errs)


def test_task_graph_ref_shape_validated(tmp_path, handoff):
    """task_graph_ref の形状 (path/schema_version 非空) を検査する。"""
    path, data = _write_plan(tmp_path)
    data["task_graph_ref"] = {"path": "", "schema_version": "1.0"}
    errs = handoff.validate_handoff(data, path)
    assert any("task_graph_ref.path" in e for e in errs)


def test_executor_backed_declared_status_must_match(tmp_path, handoff):
    """executor-backed builder は builder_status 省略可・宣言時は一致必須。"""
    path, data = _write_plan(tmp_path)
    data["routes"][0]["builder_status"] = "executor-backed"  # 正しい明示宣言は通る
    assert handoff.validate_handoff(data, path) == []
    data["routes"][0]["builder_status"] = "contract-only"  # run-skill-create と不一致
    errs = handoff.validate_handoff(data, path)
    assert any("builder_status='executor-backed' を要求" in e for e in errs)


def test_toposort_violation_fails(tmp_path, handoff):
    path, data = _write_plan(tmp_path)
    data["routes"] = [data["routes"][1], data["routes"][0]]
    errs = handoff.validate_handoff(data, path)
    assert any("top-sort 違反" in e for e in errs)


def test_missing_spec_fails(tmp_path, handoff):
    path, data = _write_plan(tmp_path)
    data["routes"][1]["spec"] = "missing.md"
    errs = handoff.validate_handoff(data, path)
    assert any("plan_dir 配下に存在しない" in e for e in errs)


def test_external_gap_requires_reason(tmp_path, handoff):
    path, data = _write_plan(tmp_path)
    del data["envelope"]["manifest"]["gap_reason"]
    errs = handoff.validate_handoff(data, path)
    assert any("gap_reason/approval_reason" in e for e in errs)


def test_manifest_draft_name_mismatch_fails(tmp_path, handoff):
    path, data = _write_plan(tmp_path)
    (tmp_path / "envelope-draft" / "plugin.json").write_text(
        json.dumps({"name": "other-plugin", "version": "0.1.0", "description": "sample"}, ensure_ascii=False),
        encoding="utf-8",
    )
    errs = handoff.validate_handoff(data, path)
    assert any("target_plugin_slug" in e for e in errs)


# ─────────────────── C2: entry_points × inventory 突合 (MEDIUM-4) ───────────────────
def _write_draft_entry_points(tmp_path, entry_points: dict):
    """envelope-draft/plugin.json を entry_points 付きで書き換える (target 名は sample-plugin)。"""
    (tmp_path / "envelope-draft" / "plugin.json").write_text(
        json.dumps(
            {"name": "sample-plugin", "version": "0.1.0", "description": "sample",
             "entry_points": entry_points},
            ensure_ascii=False),
        encoding="utf-8",
    )


def test_entry_points_full_coverage_passes(tmp_path, handoff):
    """inventory の全 surface component (skill run-sample / sub-agent sample-verifier) が
    manifest entry_points に宣言済みなら通る (2 SSOT 突合の正例)。"""
    path, data = _write_plan(tmp_path)
    _write_inventory_for_handoff(tmp_path)
    _write_draft_entry_points(tmp_path, {
        "skills": ["run-sample"], "agents": ["sample-verifier"], "commands": []})
    assert handoff.validate_handoff(data, path) == []
    assert handoff.main([str(path)]) == 0


def test_entry_points_uncovered_surface_detected(tmp_path, handoff):
    """entry_points.agents に載っていない sub-agent は未宣言 violation として fail-closed で弾く。"""
    path, data = _write_plan(tmp_path)
    _write_inventory_for_handoff(tmp_path)
    _write_draft_entry_points(tmp_path, {
        "skills": ["run-sample"], "agents": [], "commands": []})  # sample-verifier 欠落
    errs = handoff.validate_handoff(data, path)
    assert any("sample-verifier" in e and "entry_points.agents" in e for e in errs)


def test_entry_points_coverage_hook_script_out_of_scope(handoff):
    """_check_manifest_entry_points_coverage は hook/script を対象外にする (entry_points に現れない)。"""
    comps = [
        {"id": "C01", "component_kind": "skill", "skill_name": "run-x"},
        {"id": "C09", "component_kind": "script", "script_name": "do.py"},
        {"id": "C08", "component_kind": "hook", "name": "guard"},
    ]
    ep = {"skills": ["run-x"], "agents": [], "commands": []}
    # skill は網羅済・script/hook は entry_points 未宣言でも violation にならない
    assert handoff._check_manifest_entry_points_coverage(ep, comps, "envelope.manifest") == []


def test_entry_points_missing_block_reports_all_surfaces(handoff):
    """entry_points が未宣言 (None) なら全 surface component を未網羅として報告する。"""
    comps = [
        {"id": "C01", "component_kind": "skill", "skill_name": "run-x"},
        {"id": "C02", "component_kind": "sub-agent", "name": "verifier"},
    ]
    errs = handoff._check_manifest_entry_points_coverage(None, comps, "envelope.manifest")
    assert len(errs) == 2


def test_load_inventory_components_failsoft(tmp_path, handoff):
    """_load_inventory_components は不在/壊れ JSON/components 非 list で空 list を返す (後方互換)。"""
    assert handoff._load_inventory_components(tmp_path) == []  # 不在
    (tmp_path / "component-inventory.json").write_text("{not json", encoding="utf-8")
    assert handoff._load_inventory_components(tmp_path) == []  # 壊れ JSON
    (tmp_path / "component-inventory.json").write_text('{"components": "x"}', encoding="utf-8")
    assert handoff._load_inventory_components(tmp_path) == []  # components 非 list


def test_entry_points_check_skipped_without_inventory(tmp_path, handoff):
    """component-inventory.json 不在なら entry_points 突合は発火しない (孤立 handoff の後方互換)。"""
    path, data = _write_plan(tmp_path)  # inventory を書かない・draft も entry_points 無し
    assert handoff.validate_handoff(data, path) == []


def test_main_missing_file_returns_usage_error(tmp_path, handoff):
    """存在しない handoff パスは usage error (exit 2) を返す。"""
    assert handoff.main([str(tmp_path / "does-not-exist.json")]) == 2


def test_main_invalid_json_returns_usage_error(tmp_path, handoff):
    """壊れた JSON は _load_json の ValueError 経由で usage error (exit 2) になる。"""
    bad = tmp_path / "handoff-run-plugin-dev-plan.json"
    bad.write_text("{ not valid json", encoding="utf-8")
    assert handoff.main([str(bad)]) == 2


def test_main_validation_error_returns_one(tmp_path, handoff):
    """検証エラーを持つ handoff は main が stderr へ出力し exit 1 を返す。"""
    path, data = _write_plan(tmp_path)
    data["routes"][0]["builder"] = "run-build-skill"  # skill は run-skill-create であるべき
    path.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")
    assert handoff.main([str(path)]) == 1


def test_relative_plan_dir_is_cwd_independent(monkeypatch, tmp_path, handoff):
    """相対 plan_dir フィールド (repo-root 相対 metadata) を持つ handoff でも、cwd に依存せず
    handoff ファイルの所在 (= PLAN_DIR) を基準に spec を解決する。

    回帰防止: 旧実装は相対 plan_dir を Path.cwd() で再構成していたため、skill dir cwd の CI
    から実行すると plan_dir が二重化して spec を見失っていた (harness-creator-kit-ci の nested-test
    収集で露呈)。本テストは無関係な cwd から実行しても exit0 になることを固定する。
    """
    # 参照 phase ファイル (phase-05-implementation.md) は handoff と同じ tmp_path に在るが、
    # plan_dir フィールドは repo-root 相対の metadata 値にする。
    path, data = _write_plan(tmp_path, {"plan_dir": "eval-log/some-plugin/plan"})
    monkeypatch.chdir(tmp_path.parent)  # repo-root でも skill dir でもない無関係 cwd
    assert handoff.main([str(path)]) == 0
    assert handoff.validate_handoff(data, path) == []
