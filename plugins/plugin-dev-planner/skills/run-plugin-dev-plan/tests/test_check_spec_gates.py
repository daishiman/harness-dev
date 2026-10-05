"""check-spec-gates.py の機能テスト (per-phase 転換)。

inventory component の quality_gates / harness_coverage 値域検証 + index.plugin_meta 値域検証。
component-gate 検証は component-inventory.json 経由 (gates.check_inventory) で行う。
"""
from __future__ import annotations

import json

import pytest

from conftest import (
    SPECFM,
    component_entry,
    write_inventory,
    write_phase_index as _write_phase_index,
    valid_quality_gates,
    valid_plugin_meta,
)



def write_phase_index(directory, **kwargs):
    index = _write_phase_index(directory, **kwargs)
    if kwargs.get("plugin_meta"):
        (directory / "phase-13-release.md").write_text(
            SPECFM.render_minimal_phase(13, plugin_slug="test-plugin"), encoding="utf-8"
        )
        (directory / "handoff-run-plugin-dev-plan.json").write_text(
            json.dumps({"target_plugin_slug": "test-plugin", "mode": "create"}), encoding="utf-8"
        )
    return index


def _inv_errs(tmp_path, gates, comp) -> list[str]:
    errs, fatal = gates.check_inventory(write_inventory(tmp_path, [comp]))
    assert fatal is None, fatal
    return errs


# ─────────────────── inventory component gates/harness ───────────────────
def test_component_clean_skill(tmp_path, gates):
    assert _inv_errs(tmp_path, gates, component_entry("C01", "skill")) == []


def test_component_clean_each_kind(tmp_path, gates):
    for ck in ("sub-agent", "slash-command", "hook", "script"):
        assert _inv_errs(tmp_path, gates, component_entry("C01", ck)) == [], ck


def test_missing_quality_gates(tmp_path, gates):
    errs = _inv_errs(tmp_path, gates, component_entry("C01", "skill", drop=["quality_gates"]))
    assert any("quality_gates ブロックが無い" in e for e in errs)


def test_p0_lint_incomplete(tmp_path, gates):
    qg = valid_quality_gates("skill")
    qg["p0_lint"] = ["lint-skill-name"]  # 8 本に満たない
    errs = _inv_errs(tmp_path, gates, component_entry("C01", "skill", overrides={"quality_gates": qg}))
    assert any("p0_lint が必須 lint を欠く" in e for e in errs)


def test_build_trace_not_required(tmp_path, gates):
    qg = valid_quality_gates("skill")
    qg["build_trace"] = "optional"
    errs = _inv_errs(tmp_path, gates, component_entry("C01", "skill", overrides={"quality_gates": qg}))
    assert any("build_trace は 'required'" in e for e in errs)


def test_elegant_review_bad(tmp_path, gates):
    qg = valid_quality_gates("skill")
    qg["elegant_review"] = {"conditions": ["C1", "C2"], "all_pass": False}
    errs = _inv_errs(tmp_path, gates, component_entry("C01", "skill", overrides={"quality_gates": qg}))
    assert any("conditions は" in e for e in errs)
    assert any("all_pass は true" in e for e in errs)


def test_elegant_review_missing(tmp_path, gates):
    qg = valid_quality_gates("skill")
    del qg["elegant_review"]
    errs = _inv_errs(tmp_path, gates, component_entry("C01", "skill", overrides={"quality_gates": qg}))
    assert any("elegant_review ブロックが無い" in e for e in errs)


def test_content_review_bad(tmp_path, gates):
    qg = valid_quality_gates("skill")
    qg["content_review"] = {"verdict": "FAIL", "sha_match": False}
    errs = _inv_errs(tmp_path, gates, component_entry("C01", "skill", overrides={"quality_gates": qg}))
    assert any("verdict は PASS" in e for e in errs)
    assert any("sha_match は true" in e for e in errs)


def test_content_review_missing(tmp_path, gates):
    qg = valid_quality_gates("skill")
    del qg["content_review"]
    errs = _inv_errs(tmp_path, gates, component_entry("C01", "skill", overrides={"quality_gates": qg}))
    assert any("content_review ブロックが無い" in e for e in errs)


def test_evaluator_bad(tmp_path, gates):
    qg = valid_quality_gates("skill")
    qg["evaluator"] = {"threshold": 70, "high_max": 2}
    errs = _inv_errs(tmp_path, gates, component_entry("C01", "skill", overrides={"quality_gates": qg}))
    assert any("threshold は >=80" in e for e in errs)
    assert any("high_max は 0" in e for e in errs)


def test_evaluator_missing(tmp_path, gates):
    qg = valid_quality_gates("skill")
    del qg["evaluator"]
    errs = _inv_errs(tmp_path, gates, component_entry("C01", "skill", overrides={"quality_gates": qg}))
    assert any("evaluator ブロックが無い" in e for e in errs)


def test_harness_low(tmp_path, gates):
    errs = _inv_errs(tmp_path, gates, component_entry(
        "C01", "skill", overrides={"harness_coverage": {"min": 50, "kind_pass": "criteria+content-review"}}))
    assert any("harness_coverage.min は >=80" in e for e in errs)


def test_harness_no_kind_pass(tmp_path, gates):
    errs = _inv_errs(tmp_path, gates, component_entry("C01", "skill", overrides={"harness_coverage": {"min": 90}}))
    assert any("kind_pass が空" in e for e in errs)


def test_harness_missing(tmp_path, gates):
    errs = _inv_errs(tmp_path, gates, component_entry("C01", "skill", drop=["harness_coverage"]))
    assert any("harness_coverage ブロックが無い" in e for e in errs)


def test_harness_kind_pass_mismatch(tmp_path, gates):
    # skill run なのに kind_pass が ref 用語だけ → kind と無関係で弾く
    errs = _inv_errs(tmp_path, gates, component_entry(
        "C01", "skill", skill_kind="run",
        overrides={"harness_coverage": {"min": 80, "kind_pass": "source-traceability-only"}}))
    assert any("kind と無関係" in e for e in errs)


def test_harness_kind_pass_ref_ok(tmp_path, gates):
    errs = _inv_errs(tmp_path, gates, component_entry("C01", "skill", skill_kind="ref"))
    assert [e for e in errs if "kind_pass" in e] == []


# ─────────────────── plugin_meta 値域検証 (現状維持) ───────────────────
def test_plugin_meta_clean(gates):
    assert gates.check_plugin_meta(valid_plugin_meta(distributable=False)) == []
    assert gates.check_plugin_meta(valid_plugin_meta(distributable=True)) == []


def test_plugin_meta_conditional_na_with_reason_ok(gates):
    """条件付きキーは {applicable: false, reason: <非空>} で明示 N/A 可 (A7 整合)。"""
    pm = valid_plugin_meta(distributable=False)
    pm["pkg_contract"] = {"applicable": False, "reason": "単一 skill・PKG packaging 不要"}
    pm["governance"] = {"applicable": False, "reason": "rubric 改訂を伴わない"}
    assert gates.check_plugin_meta(pm) == []


def test_plugin_meta_conditional_na_without_reason_fails(gates):
    """applicable:false で reason 欠落/空は N/A 根拠不足としてエラー。"""
    pm = valid_plugin_meta(distributable=False)
    pm["pkg_contract"] = {"applicable": False}  # reason なし
    pm["governance"] = {"applicable": False, "reason": "  "}  # 空白のみ
    errs = gates.check_plugin_meta(pm)
    assert any("pkg_contract が applicable:false だが reason が空" in e for e in errs)
    assert any("governance が applicable:false だが reason が空" in e for e in errs)


def test_plugin_meta_core_na_not_allowed(gates):
    """コアキー (ci) は applicable:false を許さず非空 dict 必須のまま。"""
    pm = valid_plugin_meta(distributable=False)
    pm["ci"] = {"applicable": False, "reason": "x"}  # core は N/A 不可だが非空 dict ではある
    errs = gates.check_plugin_meta(pm)
    assert not any("ci" in e for e in errs)
    pm["ci"] = {}  # 空 dict は core でエラー
    assert any("plugin_meta.ci が非空 dict でない" in e for e in gates.check_plugin_meta(pm))


def test_plugin_meta_conditional_missing_fails(gates):
    pm = valid_plugin_meta(distributable=False)
    del pm["pkg_contract"]
    assert any("pkg_contract が非空 dict でない" in e for e in gates.check_plugin_meta(pm))


def test_plugin_meta_distributable_not_bool(gates):
    pm = valid_plugin_meta()
    pm["distribution"]["distributable"] = "false"  # 文字列
    assert any("distributable は bool" in e for e in gates.check_plugin_meta(pm))


def test_plugin_meta_false_but_bundles_nonempty(gates):
    pm = valid_plugin_meta(distributable=False)
    pm["distribution"]["bundles"] = ["harness-full"]
    assert any("bundles 非空" in e for e in gates.check_plugin_meta(pm))


def test_plugin_meta_false_but_marketplace_true(gates):
    pm = valid_plugin_meta(distributable=False)
    pm["distribution"]["marketplace"] = True
    assert any("marketplace" in e for e in gates.check_plugin_meta(pm))


def test_plugin_meta_true_but_empty_bundles(gates):
    pm = valid_plugin_meta(distributable=True)
    pm["distribution"]["bundles"] = []
    assert any("bundles が空" in e for e in gates.check_plugin_meta(pm))


def test_plugin_meta_distribution_not_dict(gates):
    assert any("distribution が dict でない" in e for e in gates.check_plugin_meta({"distribution": "x"}))


def test_plugin_meta_manifest_contract(gates):
    pm = valid_plugin_meta()
    pm["manifest"]["path"] = "plugin.json"
    pm["manifest"]["validate_plugin"] = False
    errs = gates.check_plugin_meta(pm)
    assert any("manifest.path" in e for e in errs)
    assert any("manifest.validate_plugin" in e for e in errs)


def test_plugin_meta_marketplace_policy_contract(gates):
    pm = valid_plugin_meta()
    pm["marketplace"]["policy"]["installation"] = "MAYBE"
    pm["marketplace"]["policy"]["authentication"] = "LATER"
    pm["marketplace"]["policy"]["category"] = ""
    pm["marketplace"]["cachebuster_for_update"] = False
    errs = gates.check_plugin_meta(pm)
    assert any("policy.installation" in e for e in errs)
    assert any("policy.authentication" in e for e in errs)
    assert any("policy.category" in e for e in errs)
    assert any("cachebuster_for_update" in e for e in errs)


def test_plugin_meta_missing_required_dict(gates):
    pm = valid_plugin_meta()
    del pm["ci"]
    pm["governance"] = {}  # 空 dict も不可
    errs = gates.check_plugin_meta(pm)
    assert any("plugin_meta.ci" in e for e in errs)
    assert any("plugin_meta.governance" in e for e in errs)


# ─────────────────── install 値域検証 (Claude/Codex 両 platform・core) ───────────────────
def test_install_missing_is_core_violation(gates):
    """install は core。欠落すると plugin 階層コア規律の未充足になる。"""
    pm = valid_plugin_meta()
    del pm["install"]
    assert any("plugin_meta.install が非空 dict でない" in e for e in gates.check_plugin_meta(pm))


def test_install_codex_dropped_without_reason_fails(gates):
    """両 platform が既定。codex を黙って外すと理由欠落で落ちる。"""
    pm = valid_plugin_meta()
    pm["install"]["platforms"] = ["claude"]
    pm["install"]["registries"] = ["harness-local"]
    errs = gates.check_plugin_meta(pm)
    assert any("excluded_platforms.codex の理由が無い" in e for e in errs)


def test_install_codex_excluded_with_reason_ok(gates):
    """runtime Codex除外には理由を要求し、両製品package/catalogは維持する。"""
    pm = valid_plugin_meta()
    pm["install"]["platforms"] = ["claude"]
    pm["install"]["excluded_platforms"] = {"codex": "Claude 専用 hook event だけで成り立つため"}
    assert gates.check_plugin_meta(pm) == []


def test_install_claude_cannot_be_excluded(gates):
    """manifest 正本 (.claude-plugin) の platform は理由があっても外せない。"""
    pm = valid_plugin_meta()
    pm["install"]["platforms"] = ["codex"]
    pm["install"]["excluded_platforms"] = {"claude": "x"}
    errs = gates.check_plugin_meta(pm)
    assert any("platforms は claude を含むこと" in e for e in errs)


def test_install_platform_listed_and_excluded_conflict(gates):
    pm = valid_plugin_meta()
    pm["install"]["excluded_platforms"] = {"codex": "迷い"}
    assert any("両方に codex がある" in e for e in gates.check_plugin_meta(pm))


def test_install_unknown_platform(gates):
    pm = valid_plugin_meta()
    pm["install"]["platforms"] = ["claude", "codex", "cursor"]
    assert any("未知の platform" in e for e in gates.check_plugin_meta(pm))


def test_install_registry_missing_for_platform(gates):
    """platform ごとの登録先が無いと、作っても install 経路が無い (harness-local / codex-repo)。"""
    pm = valid_plugin_meta()
    pm["install"]["registries"] = ["codex-repo"]
    errs = gates.check_plugin_meta(pm)
    assert any("registries に harness-local が無い" in e for e in errs)
    pm["install"]["registries"] = ["harness-local"]
    errs = gates.check_plugin_meta(pm)
    assert any("registries に codex-repo が無い" in e for e in errs)


def test_install_codex_manifest_path(gates):
    pm = valid_plugin_meta()
    pm["install"]["codex_manifest"] = ".codex/plugin.json"
    assert any("codex_manifest は .codex-plugin/plugin.json" in e for e in gates.check_plugin_meta(pm))


def test_install_strict_validate_and_release_order(gates):
    pm = valid_plugin_meta()
    pm["install"]["strict_validate"] = False
    pm["install"]["release"] = "bump-then-changelog"
    errs = gates.check_plugin_meta(pm)
    assert any("strict_validate は true" in e for e in errs)
    assert any("install.release は 'changelog-then-bump'" in e for e in errs)


def test_install_verify_isolated_required(gates):
    """隔離 install は副作用が無いので opt-out を設けない。"""
    pm = valid_plugin_meta()
    pm["install"]["verify"] = {"isolated": False, "live": True}
    assert any("verify.isolated は true" in e for e in gates.check_plugin_meta(pm))


def test_install_verify_live_opt_out_needs_reason(gates):
    pm = valid_plugin_meta()
    pm["install"]["verify"] = {"isolated": True, "live": False}
    assert any("live_skip_reason 非空必須" in e for e in gates.check_plugin_meta(pm))
    pm["install"]["verify"]["live_skip_reason"] = "CI 専用 plugin で手元の Claude/Codex に入れない"
    assert gates.check_plugin_meta(pm) == []


def test_install_verify_live_not_bool(gates):
    pm = valid_plugin_meta()
    pm["install"]["verify"] = {"isolated": True, "live": "yes"}
    assert any("verify.live は bool" in e for e in gates.check_plugin_meta(pm))


def test_install_verify_missing(gates):
    pm = valid_plugin_meta()
    del pm["install"]["verify"]
    assert any("install.verify が dict でない" in e for e in gates.check_plugin_meta(pm))


# ─────────────────── feedback_deploy 値域検証 (core 昇格) ───────────────────
def test_feedback_deploy_applicable_false_form_rejected(gates):
    """core 昇格後は {applicable: false} 形の N/A を許さない (opt-out は enabled:false+reason のみ)。"""
    pm = valid_plugin_meta(distributable=False)
    pm["feedback_deploy"] = {"applicable": False, "reason": "loop-kind skill 不在"}
    errs = gates.check_plugin_meta(pm)
    assert any("feedback_deploy は core 規律" in e for e in errs)


def test_feedback_deploy_opt_out_with_reason_ok(gates):
    """opt-out は {enabled: false, reason: <非空>} の明示例外のみ許容。"""
    pm = valid_plugin_meta(distributable=False)
    pm["feedback_deploy"] = {"enabled": False, "reason": "loop-kind skill 不在で評価ループ対象外"}
    assert gates.check_plugin_meta(pm) == []


def test_feedback_deploy_opt_out_without_reason_fails(gates):
    """enabled:false で reason 欠落/空は明示例外の根拠不足としてエラー。"""
    pm = valid_plugin_meta(distributable=False)
    pm["feedback_deploy"] = {"enabled": False}
    errs = gates.check_plugin_meta(pm)
    assert any("feedback_deploy.enabled:false (opt-out) は reason 非空必須" in e for e in errs)


def test_feedback_deploy_value_domain(gates):
    """採用時は deploy=run-skill-feedback / notion_sink.config_key 非空 / portability enum を強制。"""
    pm = valid_plugin_meta(distributable=False)
    pm["feedback_deploy"] = {"deploy": "other-skill", "enabled": True,
                             "notion_sink": {"config_key": ""}, "portability": "symlink"}
    errs = gates.check_plugin_meta(pm)
    assert any("feedback_deploy.deploy は 'run-skill-feedback'" in e for e in errs)
    assert any("notion_sink.config_key が非空でない" in e for e in errs)
    assert any("portability は repo-bundled|vendored のみ" in e for e in errs)


def test_feedback_deploy_distributable_requires_vendored(gates):
    """distributable:true は portability=vendored を強制 (単独 install 携帯性・D6 symlink 禁止と同根)。"""
    pm = valid_plugin_meta(distributable=True)
    pm["feedback_deploy"]["portability"] = "repo-bundled"
    errs = gates.check_plugin_meta(pm)
    assert any("portability=vendored を要求" in e for e in errs)
    # 非配布は repo-bundled のままで良い (valid_plugin_meta(distributable=False) の既定)
    assert gates.check_plugin_meta(valid_plugin_meta(distributable=False)) == []


# ─────────────────── main 統合 (index plugin_meta + inventory) ───────────────────
def test_main_ok(tmp_path, gates, capsys):
    write_phase_index(tmp_path, plugin_meta=True)
    write_inventory(tmp_path, [component_entry("C01", "skill"), component_entry("C02", "hook")])
    assert gates.main(["--specs-dir", str(tmp_path)]) == 0
    assert "OK" in capsys.readouterr().out


def test_main_violation(tmp_path, gates, capsys):
    write_phase_index(tmp_path, plugin_meta=True)
    write_inventory(tmp_path, [component_entry("C01", "skill", drop=["quality_gates"])])
    assert gates.main(["--specs-dir", str(tmp_path)]) == 1
    assert "quality_gates" in capsys.readouterr().err


def test_main_no_args(gates):
    assert gates.main([]) == 2


def test_main_specs_dir_not_dir(tmp_path, gates):
    assert gates.main(["--specs-dir", str(tmp_path / "nope")]) == 2


def test_main_file_not_found(tmp_path, gates):
    assert gates.main([str(tmp_path / "ghost.md")]) == 2


def test_run_validates_index_plugin_meta_clean(tmp_path, gates):
    write_phase_index(tmp_path, plugin_meta=True)  # 非配布 (bundles 空) airtight・inventory 無し
    assert gates.main(["--specs-dir", str(tmp_path)]) == 0


def test_run_validates_index_plugin_meta_violation(tmp_path, gates, capsys):
    write_phase_index(tmp_path, plugin_meta=True, distributable=False)
    idx = tmp_path / "index.md"
    idx.write_text(
        idx.read_text(encoding="utf-8").replace("bundles: []", "bundles: [harness-full]"),
        encoding="utf-8",
    )
    assert gates.main(["--specs-dir", str(tmp_path)]) == 1
    assert "bundles 非空" in capsys.readouterr().err


@pytest.mark.parametrize("mode", ["create", "update"])
def test_install_release_contract_reaches_p13(tmp_path, gates, mode):
    write_phase_index(tmp_path, plugin_meta=True)
    (tmp_path / "handoff-run-plugin-dev-plan.json").write_text(
        json.dumps({"target_plugin_slug": "test-plugin", "mode": mode}), encoding="utf-8"
    )
    assert gates.main(["--specs-dir", str(tmp_path)]) == 0
    (tmp_path / "phase-13-release.md").unlink()
    assert gates.main(["--specs-dir", str(tmp_path)]) == 1


@pytest.mark.parametrize("obligation", ["release", "registries", "strict_validate", "isolated", "live"])
def test_install_release_each_missing_clause_fails(tmp_path, gates, obligation):
    write_phase_index(tmp_path, plugin_meta=True)
    inst = SPECFM.default_install_contract()
    phase = tmp_path / "phase-13-release.md"
    clause = SPECFM.install_release_obligations(inst, "test-plugin")[obligation]
    phase.write_text(phase.read_text().replace("- [ ] " + clause, ""), encoding="utf-8")
    errors = gates.check_install_release(tmp_path, inst)
    assert len(errors) == 1 and f"obligation {obligation}" in errors[0]


def test_install_runtime_opt_out_keeps_packages(gates):
    inst = SPECFM.default_install_contract()
    inst["platforms"] = ["claude"]
    inst["excluded_platforms"] = {"codex": "runtime hooks are Claude-only"}
    assert gates.check_install(inst) == []
    del inst["codex_manifest"]
    inst["registries"] = ["harness-local"]
    errors = gates.check_install(inst)
    assert any("codex_manifest" in e for e in errors)
    assert any("codex-repo" in e for e in errors)


def test_install_opt_out_changes_actual_p13_commands(tmp_path, gates):
    write_phase_index(tmp_path, plugin_meta=True)
    inst = SPECFM.default_install_contract()
    inst["platforms"] = ["claude"]
    inst["excluded_platforms"] = {"codex": "runtime not used here"}
    inst["verify"] = {"isolated": True, "live": False, "live_skip_reason": "CI run"}
    assert gates.check_install(inst) == []
    assert gates.check_install_release(tmp_path, inst)  # default both/live clauses cannot satisfy opt-out
    text = SPECFM.render_minimal_phase(13, plugin_slug="test-plugin", install=inst)
    (tmp_path / "phase-13-release.md").write_text(text, encoding="utf-8")
    assert "--platform claude" in text and "--platform both" not in text
    assert "codex-home" in text  # isolated storage remains explicit
    assert gates.check_install_release(tmp_path, inst) == []
    del inst["verify"]["live_skip_reason"]
    assert gates.check_install(inst)


def test_install_clause_outside_p13_checklist_is_not_execution(tmp_path, gates):
    write_phase_index(tmp_path, plugin_meta=True)
    phase = tmp_path / "phase-13-release.md"
    clause = SPECFM.install_release_obligations(SPECFM.default_install_contract(), "test-plugin")["isolated"]
    phase.write_text(phase.read_text().replace("- [ ] " + clause, "") + "\n- [ ] " + clause, encoding="utf-8")
    assert any("isolated" in e for e in gates.check_install_release(tmp_path, SPECFM.default_install_contract()))



def test_install_unknown_shape_fails_closed(tmp_path, gates):
    index = write_phase_index(tmp_path, plugin_meta=True)
    index.write_text(index.read_text().replace("id: IDX0", "id: IDX0\nshape_marker: unknown-shape"), encoding="utf-8")
    assert gates.main(["--specs-dir", str(tmp_path)]) == 1
    assert any("unknown shape_marker" in e for e in gates.check_install_release(tmp_path, SPECFM.default_install_contract()))


@pytest.mark.parametrize("mode", ["create", "update"])
def test_install_target_shape_requires_actual_task_specs(tmp_path, gates, mode):
    index = write_phase_index(tmp_path, plugin_meta=True)
    index.write_text(index.read_text().replace("id: IDX0", "id: IDX0\nshape_marker: task-graph-derived"), encoding="utf-8")
    (tmp_path / "handoff-run-plugin-dev-plan.json").write_text(
        json.dumps({"target_plugin_slug": "test-plugin", "mode": mode}), encoding="utf-8"
    )
    inst = SPECFM.default_install_contract()
    assert gates.check_install_release(tmp_path, inst)  # policy P13 alone cannot execute
    tasks = tmp_path / "task-specs"
    tasks.mkdir()
    obligations = SPECFM.install_release_obligations(inst, "test-plugin")
    for key, clause in obligations.items():
        fm = {
            "id": "install-" + key, "title": "verify install " + key,
            "phase_ref": "P13", "execution_kind": "direct-task",
            "write_scope": "eval-log/install", "acceptance_criterion": clause,
            "produces": ["eval-log/install/" + key + ".json"], "depends_on": [],
        }
        (tasks / (fm["id"] + ".md")).write_text(
            "---\n" + "\n".join(SPECFM.yaml_lines(fm)) + "\n---\n# release verification\n", encoding="utf-8"
        )
    assert gates.check_install_release(tmp_path, inst) == []
    (tasks / "install-isolated.md").unlink()
    assert any("obligation isolated" in e for e in gates.check_install_release(tmp_path, inst))


def test_install_stale_handoff_graph_cannot_hide_obligations(tmp_path, gates, derive_task_graph):
    write_phase_index(tmp_path, plugin_meta=True)
    inst = SPECFM.default_install_contract()
    graph = derive_task_graph.derive(tmp_path)
    target = tmp_path / "consumer-graph.json"
    (tmp_path / "handoff-run-plugin-dev-plan.json").write_text(json.dumps({
        "target_plugin_slug": "test-plugin", "task_graph_ref": {"path": target.name}
    }), encoding="utf-8")
    target.write_text(json.dumps(graph), encoding="utf-8")
    assert gates.check_install_release(tmp_path, inst) == []
    clause = SPECFM.install_release_obligations(inst, "test-plugin")["isolated"]
    graph["nodes"] = [n for n in graph["nodes"] if n.get("acceptance_criterion") != clause]
    target.write_text(json.dumps(graph), encoding="utf-8")
    errors = gates.check_install_release(tmp_path, inst)
    assert any("task-graph install obligation isolated" in e for e in errors)


def test_install_malformed_graph_reference_fails_cleanly(tmp_path, gates):
    write_phase_index(tmp_path, plugin_meta=True)
    (tmp_path / "handoff-run-plugin-dev-plan.json").write_text(json.dumps({
        "target_plugin_slug": "test-plugin", "task_graph_ref": {"path": None}
    }), encoding="utf-8")
    assert any("task_graph_ref.path" in e for e in gates.check_install_release(tmp_path, SPECFM.default_install_contract()))


# ─────────────────── install 義務の slug 正本 (goal-spec 優先) ───────────────────
def _write_goal_spec(directory, slug):
    (directory / "goal-spec.json").write_text(json.dumps({"target_plugin_slug": slug}), encoding="utf-8")


def test_install_slug_prefers_goal_spec_without_handoff(tmp_path, gates):
    """slug の正本は goal-spec。handoff が未生成でも P13 突合が進む (生成順序に依存しない)。"""
    write_phase_index(tmp_path, plugin_meta=True)
    (tmp_path / "handoff-run-plugin-dev-plan.json").unlink()
    inst = SPECFM.default_install_contract()
    assert any("解決できない" in e for e in gates.check_install_release(tmp_path, inst))
    _write_goal_spec(tmp_path, "test-plugin")
    assert gates.check_install_release(tmp_path, inst) == []
    _write_goal_spec(tmp_path, "other-plugin")  # P13 は test-plugin の条項のまま
    assert any("obligation release" in e for e in gates.check_install_release(tmp_path, inst))


def test_install_slug_goal_spec_handoff_mismatch_fails(tmp_path, gates):
    write_phase_index(tmp_path, plugin_meta=True)
    inst = SPECFM.default_install_contract()
    _write_goal_spec(tmp_path, "test-plugin")
    assert gates.check_install_release(tmp_path, inst) == []
    (tmp_path / "handoff-run-plugin-dev-plan.json").write_text(
        json.dumps({"target_plugin_slug": "other-plugin"}), encoding="utf-8"
    )
    errors = gates.check_install_release(tmp_path, inst)
    assert len(errors) == 1 and "goal-spec ('test-plugin') と handoff ('other-plugin') で不一致" in errors[0]
    assert gates.main(["--specs-dir", str(tmp_path)]) == 1


def test_install_slug_invalid_goal_spec_fails_cleanly(tmp_path, gates):
    write_phase_index(tmp_path, plugin_meta=True)
    inst = SPECFM.default_install_contract()
    (tmp_path / "goal-spec.json").write_text("{broken", encoding="utf-8")
    assert any("goal-spec.json から読めない" in e for e in gates.check_install_release(tmp_path, inst))
    (tmp_path / "handoff-run-plugin-dev-plan.json").unlink()
    _write_goal_spec(tmp_path, "Not Kebab")
    assert any("target_plugin_slug が不正" in e for e in gates.check_install_release(tmp_path, inst))


# ─────────────────── install 義務は plugin 単位 (component へ複製しない) ───────────────────
def test_install_obligation_attributed_to_component_fails(tmp_path, gates):
    """fixed-13-phase で P13 に component を載せると条項が N 個の leaf へ複製・誤帰属するので拒否する。"""
    write_phase_index(tmp_path, plugin_meta=True)
    write_inventory(tmp_path, [component_entry("C01", "skill"), component_entry("C02", "hook")])
    inst = SPECFM.default_install_contract()
    assert gates.check_install_release(tmp_path, inst) == []
    phase = tmp_path / "phase-13-release.md"
    phase.write_text(
        phase.read_text(encoding="utf-8").replace("entities_covered: []", "entities_covered: [C01, C02]"),
        encoding="utf-8",
    )
    errors = gates.check_install_release(tmp_path, inst)
    assert {e.split()[3] for e in errors} == set(SPECFM.install_release_obligations(inst, "test-plugin"))
    assert all("component に帰属" in e for e in errors)


def test_install_target_shape_task_spec_with_entity_ref_fails(tmp_path, gates):
    index = write_phase_index(tmp_path, plugin_meta=True)
    index.write_text(index.read_text().replace("id: IDX0", "id: IDX0\nshape_marker: task-graph-derived"), encoding="utf-8")
    inst = SPECFM.default_install_contract()
    tasks = tmp_path / "task-specs"
    tasks.mkdir()
    for key, clause in SPECFM.install_release_obligations(inst, "test-plugin").items():
        fm = {
            "id": "install-" + key, "title": "verify install " + key,
            "phase_ref": "P13", "execution_kind": "direct-task",
            "write_scope": "eval-log/install", "acceptance_criterion": clause,
            "produces": ["eval-log/install/" + key + ".json"], "depends_on": [],
        }
        if key == "isolated":
            fm["entity_ref"] = "C01"
        (tasks / (fm["id"] + ".md")).write_text(
            "---\n" + "\n".join(SPECFM.yaml_lines(fm)) + "\n---\n# release verification\n", encoding="utf-8"
        )
    errors = gates.check_install_release(tmp_path, inst)
    assert len(errors) == 1 and "obligation isolated が component に帰属" in errors[0]
