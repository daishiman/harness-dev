"""check-spec-gates.py の機能テスト (per-phase 転換)。

inventory component の quality_gates / harness_coverage 値域検証 + index.plugin_meta 値域検証。
component-gate 検証は component-inventory.json 経由 (gates.check_inventory) で行う。
"""
from __future__ import annotations

from conftest import (
    component_entry,
    write_inventory,
    write_phase_index,
    valid_quality_gates,
    valid_plugin_meta,
)


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
