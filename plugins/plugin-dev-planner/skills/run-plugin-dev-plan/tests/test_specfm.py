"""specfm.py (共有パーサ + criteria 制約) の機能テスト。"""
from __future__ import annotations


def test_split_frontmatter(specfm_mod):
    assert specfm_mod.split_frontmatter("---\nid: C01\n---\nbody").strip() == "id: C01"
    assert specfm_mod.split_frontmatter("no fm") is None
    assert specfm_mod.split_frontmatter("---\nonly one") is None


def test_parse_scalar_types(specfm_mod):
    fm = specfm_mod.parse_frontmatter(
        "---\nname: x\nflag: true\noff: false\nn: 42\nneg: -3\n---\n"
    )
    assert fm == {"name": "x", "flag": True, "off": False, "n": 42, "neg": -3}


def test_parse_inline_and_block_list(specfm_mod):
    fm = specfm_mod.parse_frontmatter(
        "---\ninline: [a, b, c]\nblock:\n  - x\n  - y\n---\n"
    )
    assert fm["inline"] == ["a", "b", "c"]
    assert fm["block"] == ["x", "y"]


def test_parse_quoted_and_comment(specfm_mod):
    fm = specfm_mod.parse_frontmatter(
        '---\nq: "hello world"\nc: value # trailing\nfc: # only comment\n  k: 1\n---\n'
    )
    assert fm["q"] == "hello world"
    assert fm["c"] == "value"
    assert fm["fc"] == {"k": 1}


def test_parse_nested_map(specfm_mod):
    text = (
        "---\n"
        "quality_gates:\n"
        "  p0_lint: [lint-skill-name, validate-frontmatter]\n"
        "  build_trace: required\n"
        "  elegant_review:\n"
        "    conditions: [C1, C2, C3, C4]\n"
        "    all_pass: true\n"
        "  evaluator:\n"
        "    threshold: 80\n"
        "    high_max: 0\n"
        "---\n"
    )
    fm = specfm_mod.parse_frontmatter(text)
    qg = fm["quality_gates"]
    assert qg["p0_lint"] == ["lint-skill-name", "validate-frontmatter"]
    assert qg["build_trace"] == "required"
    assert qg["elegant_review"] == {"conditions": ["C1", "C2", "C3", "C4"], "all_pass": True}
    assert qg["evaluator"] == {"threshold": 80, "high_max": 0}


def test_parse_list_of_flat_maps(specfm_mod):
    text = (
        "---\n"
        "feedback_contract:\n"
        "  criteria:\n"
        "    - id: IN1\n"
        "      loop_scope: inner\n"
        "      text: t\n"
        "      verify_by: lint\n"
        "    - id: OUT1\n"
        "      loop_scope: outer\n"
        "      text: t2\n"
        "      verify_by: evaluator\n"
        "---\n"
    )
    crit = specfm_mod.parse_frontmatter(text)["feedback_contract"]["criteria"]
    assert [c["id"] for c in crit] == ["IN1", "OUT1"]
    assert crit[0]["loop_scope"] == "inner" and crit[1]["verify_by"] == "evaluator"


def test_parse_empty_and_no_fm(specfm_mod):
    assert specfm_mod.parse_frontmatter("no fm") == {}
    assert specfm_mod.parse_frontmatter("---\n---\n") == {}


def test_parse_inline_flow_map(specfm_mod):
    # inline flow map (ネストした flow list の内側カンマも保持)
    fm = specfm_mod.parse_frontmatter(
        "---\nplugin_meta:\n  distribution: {distributable: false, bundles: [a, b], marketplace: false}\n---\n"
    )
    dist = fm["plugin_meta"]["distribution"]
    assert dist == {"distributable": False, "bundles": ["a", "b"], "marketplace": False}


def test_split_top_respects_nesting(specfm_mod):
    assert specfm_mod._split_top("a, [b, c], {d: e, f: g}") == ["a", "[b, c]", "{d: e, f: g}"]


def test_validate_criteria_ok(specfm_mod):
    crit = [
        {"id": "IN1", "loop_scope": "inner", "text": "t", "verify_by": "lint"},
        {"id": "OUT1", "loop_scope": "outer", "text": "t", "verify_by": "elegant-review"},
    ]
    assert specfm_mod.validate_criteria(crit) == []


def test_validate_criteria_empty(specfm_mod):
    assert specfm_mod.validate_criteria([]) != []
    assert specfm_mod.validate_criteria(None) != []


def test_validate_criteria_non_dict_item(specfm_mod):
    errs = specfm_mod.validate_criteria(["not a dict"])
    assert any("object でない" in e for e in errs)


def test_validate_criteria_missing_outer(specfm_mod):
    crit = [{"id": "IN1", "loop_scope": "inner", "text": "t", "verify_by": "lint"}]
    assert any("outer" in e for e in specfm_mod.validate_criteria(crit))


def test_validate_criteria_bad_fields(specfm_mod):
    crit = [
        {"id": "X1", "loop_scope": "sideways", "text": "t", "verify_by": "magic"},
        {"id": "X1", "loop_scope": "outer", "text": "", "verify_by": "lint"},
    ]
    errs = specfm_mod.validate_criteria(crit)
    assert any("^(IN|OUT|C)" in e for e in errs)
    assert any("enum 外" in e for e in errs)
    assert any("inner|outer" in e for e in errs)
    assert any("重複" in e for e in errs)
    assert any(".text が空" in e for e in errs)


def test_purpose_signals_extracts_cjk_bigrams_and_ascii(specfm_mod):
    sig = specfm_mod.purpose_signals("冪等同期され差分0 Notion へ")
    assert {"冪等", "同期", "差分"} <= sig  # CJK bigram (hiragana 区切り)
    assert "notion" in sig                  # ascii 語 (3 文字以上・小文字化)
    assert "へ" not in sig and "0" not in sig  # hiragana 単独 / 数字は素片にしない


def test_purpose_signals_empty_for_glue_only(specfm_mod):
    # hiragana / 1 文字漢字 / 短い ascii のみ → 内容語シグナル無し (判定材料なし)
    assert specfm_mod.purpose_signals("を する した で") == set()
    assert specfm_mod.purpose_signals("全 P0") == set()


def test_criteria_purpose_traceability_detects_generic_fallback(specfm_mod):
    goal = "タスク台帳が Notion へ冪等同期され差分0で完了した状態"
    checklist = ["差分抽出", "冪等upsert", "同期検証"]
    generic = [
        {"id": "IN1", "loop_scope": "inner", "text": "P0 lint 8 本 exit0", "verify_by": "lint"},
        {"id": "OUT1", "loop_scope": "outer", "text": "elegant-review の C1-C4 が全 PASS する",
         "verify_by": "elegant-review"},
    ]
    errs = specfm_mod.criteria_purpose_traceability_errors(generic, goal=goal, checklist=checklist)
    assert any("purpose 由来でない" in e for e in errs)


def test_criteria_purpose_traceability_accepts_derived(specfm_mod):
    goal = "タスク台帳が Notion へ冪等同期され差分0で完了した状態"
    checklist = ["差分抽出", "冪等upsert", "同期検証"]
    good = [
        {"id": "IN1", "loop_scope": "inner", "text": "同期ペイロードを送信前に検証する", "verify_by": "script"},
        {"id": "OUT1", "loop_scope": "outer", "text": "二回同期で差分0=冪等性を検証テストが確認", "verify_by": "test"},
    ]
    assert specfm_mod.criteria_purpose_traceability_errors(good, goal=goal, checklist=checklist) == []


def test_criteria_purpose_traceability_lenient_without_vocab(specfm_mod):
    # goal/checklist から content シグナルが取れなければ判定不能で [] (偽陽性回避)
    generic = [{"id": "OUT1", "loop_scope": "outer", "text": "4 条件 PASS", "verify_by": "lint"}]
    assert specfm_mod.criteria_purpose_traceability_errors(generic, goal="", checklist=None) == []
    assert specfm_mod.criteria_purpose_traceability_errors(generic, goal="を する", checklist=[]) == []
    # criteria が空/非 list でも構造不備は validate_criteria の責務ゆえここでは [] を返す
    assert specfm_mod.criteria_purpose_traceability_errors([], goal="冪等同期", checklist=None) == []


def test_minimal_frontmatter_criteria_are_purpose_traceable(specfm_mod):
    """skeleton 生成器が purpose-traceability ゲートを自前で満たす (汎用 fallback を吐かない)。"""
    for sk in specfm_mod.FEEDBACK_LOOP_SKILL_KINDS:
        fm = specfm_mod.minimal_frontmatter("skill", skill_kind=sk)
        crit = fm["feedback_contract"]["criteria"]
        errs = specfm_mod.criteria_purpose_traceability_errors(
            crit, goal=fm.get("goal"), checklist=fm.get("checklist"))
        assert errs == [], (sk, errs)


def test_as_int(specfm_mod):
    assert specfm_mod.as_int(80) == 80
    assert specfm_mod.as_int("80") == 80
    assert specfm_mod.as_int(True) is None
    assert specfm_mod.as_int("x") is None
    assert specfm_mod.as_int(None) is None


def test_contract_tables_present(specfm_mod):
    assert len(specfm_mod.SKILL_P0_LINTS) == 8
    assert set(specfm_mod.COMPONENT_KINDS) == {"skill", "sub-agent", "slash-command", "hook", "script"}
    assert "lint-agent-prompt-section" in specfm_mod.P0_LINT_BY_KIND["sub-agent"]
    assert set(specfm_mod.PLUGIN_META_REQUIRED_DICTS) == {
        "manifest", "marketplace", "ci", "governance", "pkg_contract", "ssot_dedup", "feedback_deploy"
    }


def test_plugin_level_surfaces_include_schemas_vendor(specfm_mod):
    """PLUGIN_LEVEL_SURFACES が schemas / vendor / notion_config を含む 8 面 (feedback+Notion 連携面を追加)。"""
    assert set(specfm_mod.PLUGIN_LEVEL_SURFACES) == {
        "manifest", "composition", "harness_eval", "references_config_assets",
        "schemas", "vendor", "mcp_app_connector", "notion_config",
    }


def test_placement_scopes_and_placement_of(specfm_mod):
    assert specfm_mod.PLACEMENT_SCOPES == ("skill", "plugin-root")
    assert specfm_mod.placement_of({}) == "skill"  # 未指定は既定 skill
    assert specfm_mod.placement_of({"placement_scope": "  "}) == "skill"  # 空白も既定
    assert specfm_mod.placement_of({"placement_scope": "plugin-root"}) == "plugin-root"


def test_builder_for_maps_placement(specfm_mod):
    # plugin-root script のみ plugin-scaffold へ写す。他は §6 kind→builder 写像。
    assert specfm_mod.builder_for("script", "plugin-root") == "plugin-scaffold"
    assert specfm_mod.builder_for("script", "skill") == "parent-skill-build"
    assert specfm_mod.builder_for("script") == "parent-skill-build"  # 既定 skill
    assert specfm_mod.builder_for("skill", "plugin-root") == "run-skill-create"  # 非 script は無関係
    assert specfm_mod.builder_for("hook") == "run-build-skill"


def test_validate_component_plugin_root_script_clean(specfm_mod):
    """plugin-root script (builder=plugin-scaffold・plugins/<slug>/scripts/ 直下) が通る。"""
    comp = {
        "id": "C09", "component_kind": "script", "placement_scope": "plugin-root",
        "script_name": "s.py", "purpose": "p", "inputs": "i", "outputs": "o",
        "exit_codes": "0/1/2", "network": False, "write_scope": "none",
        "stdlib_only": True, "tests_min": 80, "depends_on": [],
        "build_target": "plugins/x/scripts/s.py", "builder": "plugin-scaffold", "build_kind": "script",
        "quality_gates": {
            "p0_lint": list(specfm_mod.P0_LINT_BY_KIND["script"]), "build_trace": "required",
            "elegant_review": {"conditions": ["C1", "C2", "C3", "C4"], "all_pass": True},
            "content_review": {"verdict": "PASS", "sha_match": True},
            "evaluator": {"threshold": 80, "high_max": 0},
        },
        "harness_coverage": {"min": 80, "kind_pass": "content-review-verdict"},
    }
    assert specfm_mod.validate_inventory_component(comp) == []


def test_validate_component_plugin_root_only_script(specfm_mod):
    """placement_scope=plugin-root を非 script (hook) に付けると error。"""
    comp = {
        "id": "C11", "component_kind": "hook", "placement_scope": "plugin-root",
        "event": "PreToolUse", "matcher": "Bash", "exit_semantics": "fail-closed-exit2",
        "settings_wiring": "settings.json", "fail_closed": True, "depends_on": [],
        "build_target": "plugins/x/hooks/h.py", "builder": "run-build-skill", "build_kind": "hook",
        "quality_gates": {
            "p0_lint": list(specfm_mod.P0_LINT_BY_KIND["hook"]), "build_trace": "required",
            "elegant_review": {"conditions": ["C1", "C2", "C3", "C4"], "all_pass": True},
            "content_review": {"verdict": "PASS", "sha_match": True},
            "evaluator": {"threshold": 80, "high_max": 0},
        },
        "harness_coverage": {"min": 80, "kind_pass": "content-review-verdict+test"},
    }
    errs = specfm_mod.validate_inventory_component(comp)
    assert any("plugin-root は script のみ" in e for e in errs)


def test_validate_component_plugin_root_script_build_target_shape(specfm_mod):
    """plugin-root script の build_target が /skills/ 配下だと error (plugins/<slug>/scripts/ 直下でない)。"""
    comp = {
        "id": "C09", "component_kind": "script", "placement_scope": "plugin-root",
        "script_name": "s.py", "purpose": "p", "inputs": "i", "outputs": "o",
        "exit_codes": "0/1/2", "network": False, "write_scope": "none",
        "stdlib_only": True, "tests_min": 80, "depends_on": [],
        "build_target": "plugins/x/skills/run-x/scripts/s.py",  # skills 配下=違反
        "builder": "plugin-scaffold", "build_kind": "script",
        "quality_gates": {
            "p0_lint": list(specfm_mod.P0_LINT_BY_KIND["script"]), "build_trace": "required",
            "elegant_review": {"conditions": ["C1", "C2", "C3", "C4"], "all_pass": True},
            "content_review": {"verdict": "PASS", "sha_match": True},
            "evaluator": {"threshold": 80, "high_max": 0},
        },
        "harness_coverage": {"min": 80, "kind_pass": "content-review-verdict"},
    }
    errs = specfm_mod.validate_inventory_component(comp)
    assert any("plugin-root" in e and "build_target" in e for e in errs)


def test_validate_component_skill_placement_script_needs_scripts_dir(specfm_mod):
    """skill placement の script は build_target に /skills/ と /scripts/ を要求する。"""
    comp = {
        "id": "C09", "component_kind": "script",  # placement 既定 skill
        "script_name": "s.py", "purpose": "p", "inputs": "i", "outputs": "o",
        "exit_codes": "0/1/2", "network": False, "write_scope": "none",
        "stdlib_only": True, "tests_min": 80, "depends_on": [],
        "build_target": "plugins/x/scripts/s.py",  # /skills/ が無い=skill placement 違反
        "builder": "parent-skill-build", "build_kind": "script",
        "quality_gates": {
            "p0_lint": list(specfm_mod.P0_LINT_BY_KIND["script"]), "build_trace": "required",
            "elegant_review": {"conditions": ["C1", "C2", "C3", "C4"], "all_pass": True},
            "content_review": {"verdict": "PASS", "sha_match": True},
            "evaluator": {"threshold": 80, "high_max": 0},
        },
        "harness_coverage": {"min": 80, "kind_pass": "content-review-verdict"},
    }
    errs = specfm_mod.validate_inventory_component(comp)
    assert any("placement_scope=skill" in e and "build_target" in e for e in errs)


def test_plugin_meta_core_conditional_partition(specfm_mod):
    """core/conditional が従来 7 キーを重複なく分割する (feedback_deploy は core 昇格・和集合不変)。"""
    core = set(specfm_mod.PLUGIN_META_CORE_DICTS)
    cond = set(specfm_mod.PLUGIN_META_CONDITIONAL_DICTS)
    assert core == {"manifest", "marketplace", "ci", "feedback_deploy"}
    assert cond == {"pkg_contract", "governance", "ssot_dedup"}
    assert core.isdisjoint(cond)
    assert core | cond == set(specfm_mod.PLUGIN_META_REQUIRED_DICTS)


def test_is_plugin_meta_na(specfm_mod):
    """{applicable: false} のみ N/A 判定 (true / 欠落 / 非 dict は False)。"""
    assert specfm_mod.is_plugin_meta_na({"applicable": False, "reason": "x"}) is True
    assert specfm_mod.is_plugin_meta_na({"applicable": True}) is False
    assert specfm_mod.is_plugin_meta_na({"pkg": "002"}) is False
    assert specfm_mod.is_plugin_meta_na("x") is False


def test_plan_slug_deterministic(specfm_mod):
    """plan_slug が決定論的 kebab-case を返す (同一入力→同一 slug=再現性)。"""
    assert specfm_mod.plan_slug("Notion Task Sync") == "notion-task-sync"
    assert specfm_mod.plan_slug("  MF_掛け払い  Check!! ") == "mf-check"  # 非英数は - 圧縮
    assert specfm_mod.plan_slug("already-kebab") == "already-kebab"
    assert specfm_mod.plan_slug("a---b__c") == "a-b-c"
    # 冪等性: slug(slug(x)) == slug(x)
    once = specfm_mod.plan_slug("Some Plugin v2")
    assert specfm_mod.plan_slug(once) == once


def test_plan_output_dir(specfm_mod):
    """plan_output_dir が既定/上書きを決定論的に解決する。"""
    assert specfm_mod.plan_output_dir("Notion Task Sync") == "plugin-plans/notion-task-sync"
    # --out-dir 明示は優先 (末尾スラッシュ除去)
    assert specfm_mod.plan_output_dir("x", out_dir="plans/custom/") == "plans/custom"
    # slug 化不能 (全て非英数) は ValueError
    import pytest as _pytest
    with _pytest.raises(ValueError):
        specfm_mod.plan_output_dir("日本語のみ")


def test_expected_kind_pass_tokens(specfm_mod):
    assert specfm_mod.expected_kind_pass_tokens("skill", "run") == {"criteria", "content-review"}
    assert specfm_mod.expected_kind_pass_tokens("skill", "ref") == {"source-traceability", "ref-review"}
    assert specfm_mod.expected_kind_pass_tokens("skill", "assign") == {"evaluator", "verdict"}
    assert "content-review" in specfm_mod.expected_kind_pass_tokens("hook", "")


def test_kind_pass_ok(specfm_mod):
    assert specfm_mod.kind_pass_ok("loop=criteria-test+content-review-verdict", "skill", "run")
    assert not specfm_mod.kind_pass_ok("source-traceability-only", "skill", "run")
    assert specfm_mod.kind_pass_ok("ref=source-traceability+ref-review", "skill", "ref")
    assert specfm_mod.kind_pass_ok("content-review-verdict", "hook", "")
    assert not specfm_mod.kind_pass_ok("", "skill", "run")


def _as_inventory_component(specfm_mod, comp: dict) -> dict:
    """component skeleton (frontmatter dict) に build routing フィールドを足して inventory 化する。"""
    ck = str(comp.get("component_kind", "")).strip()
    comp = dict(comp)
    # script は placement 別 build_target 不変条件 (skill placement は /skills/ と /scripts/ を含む)。
    comp["build_target"] = (
        "plugins/sample/skills/run-sample/scripts/do.py" if ck == "script"
        else "plugins/sample/skills/run-sample/"
    )
    comp["builder"] = specfm_mod.BUILDER_BY_KIND[ck]
    comp["build_kind"] = specfm_mod.BUILD_KIND_BY_KIND[ck]
    return comp


def test_minimal_frontmatter_each_kind_passes_contract(specfm_mod):
    """specfm 生成 skeleton (+ build routing) が validate_inventory_component を通る。"""
    for ck in specfm_mod.COMPONENT_KINDS:
        comp = _as_inventory_component(specfm_mod, specfm_mod.minimal_frontmatter(ck, spec_id="C01", skill_kind="run"))
        assert specfm_mod.validate_inventory_component(comp) == [], ck


def test_render_spec_skeleton_kind_cli(skeleton, specfm_mod, capsys):
    assert skeleton.main(["--kind", "hook", "--id", "C04"]) == 0
    out = capsys.readouterr().out
    assert '"component_kind": "hook"' in out
    assert '"id": "C04"' in out
    import json
    comp = _as_inventory_component(specfm_mod, json.loads(out))
    assert specfm_mod.validate_inventory_component(comp) == []


def test_render_spec_skeleton_phase_cli(skeleton, specfm, specfm_mod, capsys):
    assert skeleton.main(["--phase", "3"]) == 0
    out = capsys.readouterr().out
    assert "id: P03" in out
    for sec in specfm_mod.PHASE_BODY_SECTIONS:  # §5 宣言型 8 節が全て在る
        assert sec in out
    assert specfm.check_phase(out) == []


def test_render_spec_skeleton_index_cli(skeleton, topsort, specfm_mod, capsys):
    assert skeleton.main(["--index", "--plugin-slug", "notion-task-sync"]) == 0
    out = capsys.readouterr().out
    assert "notion-task-sync" in out
    # §9 基盤層+全体制御 section 床を全て備え verify-index-topsort の層0 床を通る
    for sec in specfm_mod.INDEX_REQUIRED_SECTIONS:
        assert sec in out
    body = topsort.body_after_frontmatter(out)
    assert topsort.index_section_floor_errors(body) == []
    # フェーズ一覧が P01..P13 を昇順全列挙する (層1 も満たす)
    ordered, has_section = topsort.extract_phase_list_ids(body)
    assert has_section and ordered == topsort.expected_phase_ids()


# ─────────────────── 13 フェーズ定義 (per-phase 転換の ADD) ───────────────────
def test_phase_constants(specfm_mod):
    assert len(specfm_mod.PHASE_NAMES) == 13
    assert specfm_mod.PHASE_NAMES[0] == "requirements" and specfm_mod.PHASE_NAMES[-1] == "release"
    assert specfm_mod.PHASE_REQUIRED == (
        "id", "phase_number", "phase_name", "category", "prev_phase",
        "next_phase", "status", "gate_type", "entities_covered", "applicability",
    )
    assert specfm_mod.PHASE_STATUS == {"未実施", "進行中", "完了"}
    assert specfm_mod.GATE_TYPES == {
        "none", "design-gate", "final-gate", "tdd-red", "tdd-green", "tdd-refactor", "qa", "evidence",
    }
    # 各 phase_name が category / gate_type dict に登録されている
    for name in specfm_mod.PHASE_NAMES:
        assert name in specfm_mod.PHASE_CATEGORY
        assert specfm_mod.PHASE_GATE_TYPE[name] in specfm_mod.GATE_TYPES


def test_phase_id(specfm_mod):
    assert specfm_mod.phase_id(1) == "P01"
    assert specfm_mod.phase_id(13) == "P13"
    for n in (0, 14):
        try:
            specfm_mod.phase_id(n)
            assert False, f"phase_id({n}) が例外を出さない"
        except ValueError:
            pass
    for n in range(1, 14):
        assert specfm_mod.PHASE_ID_RE.match(specfm_mod.phase_id(n))


def test_minimal_phase_frontmatter(specfm_mod):
    for n in range(1, 14):
        fm = specfm_mod.minimal_phase_frontmatter(n)
        assert set(fm) == set(specfm_mod.PHASE_REQUIRED)
        assert fm["id"] == specfm_mod.phase_id(n)
        assert fm["phase_number"] == n
        assert fm["phase_name"] == specfm_mod.PHASE_NAMES[n - 1]
        assert fm["category"] == specfm_mod.PHASE_CATEGORY[fm["phase_name"]]
        assert fm["gate_type"] == specfm_mod.PHASE_GATE_TYPE[fm["phase_name"]]
        assert fm["prev_phase"] == n - 1
        assert fm["next_phase"] == n + 1
        assert fm["status"] in specfm_mod.PHASE_STATUS
        assert fm["entities_covered"] == []
        assert fm["applicability"] == {"applicable": True, "reason": ""}
    # P01 は prev 0、P13 は next 14
    assert specfm_mod.minimal_phase_frontmatter(1)["prev_phase"] == 0
    assert specfm_mod.minimal_phase_frontmatter(13)["next_phase"] == 14


def test_render_minimal_phase(specfm_mod):
    text = specfm_mod.render_minimal_phase(5)
    assert "id: P05" in text
    for sec in specfm_mod.PHASE_BODY_SECTIONS:  # 宣言型 8 節 (SSOT)
        assert sec in text
    # 宣言型方針で排した手続き節は skeleton に現れない
    assert "## 実行タスク" not in text
    # frontmatter が再パースできて PHASE_REQUIRED を満たす
    fm = specfm_mod.parse_frontmatter(text)
    assert all(k in fm for k in specfm_mod.PHASE_REQUIRED)


def test_render_minimal_index(specfm_mod):
    text = specfm_mod.render_minimal_index(plugin_slug="notion-task-sync")
    assert "notion-task-sync" in text
    for sec in specfm_mod.INDEX_REQUIRED_SECTIONS:  # 基盤層+全体制御 7 節 (SSOT)
        assert sec in text
    # フェーズ一覧が P01..P13 を昇順列挙する
    for n in range(1, 14):
        assert specfm_mod.phase_id(n) in text
    # plugin_meta frontmatter が再パースできる
    fm = specfm_mod.parse_frontmatter(text)
    assert isinstance(fm.get("plugin_meta"), dict)


# ─────────────────── validate_inventory_component (ADD) ───────────────────
def _skill_component(specfm_mod, **over) -> dict:
    comp = {
        "id": "C01", "component_kind": "skill", "skill_kind": "run", "kind": "run",
        "skill_name": "run-x", "prefix": "run", "hierarchy_level": "L1",
        "trigger_conditions": ["a"], "output_contract": "o", "boundary": "b",
        "placement_candidates": ["Skill"], "cli_tools": [], "deterministic_checks": [],
        "external_systems": [], "mcp_tools": [], "needs_independent_context": False,
        "needs_lifecycle_enforcement": False, "goal": "台帳を同期し差分0", "purpose_background": "bg",
        "checklist": ["同期"],
        # skill-brief.schema allOf (kind∈{run,assign}) の shape: object 配列 + prompt_required:true ≥1 件。
        "responsibilities": [{"id": "R1", "summary": "台帳同期を実装可能な入力へ落とす", "prompt_required": True}],
        "prompt_layer": "7layer",
        "combinators": ["with-goal-seek"], "goal_seek": {"engine": "inline"},
        "feedback_contract": {"criteria": [
            {"id": "IN1", "loop_scope": "inner", "text": "同期の必須キーを検証", "verify_by": "script"},
            {"id": "OUT1", "loop_scope": "outer", "text": "二回同期で差分0を検証", "verify_by": "test"},
        ]},
        "depends_on": [], "build_target": "plugins/x/skills/run-x/",
        "builder": "run-skill-create", "build_kind": "skill",
        "quality_gates": {
            "p0_lint": list(specfm_mod.P0_LINT_BY_KIND["skill"]),
            "build_trace": "required",
            "elegant_review": {"conditions": ["C1", "C2", "C3", "C4"], "all_pass": True},
            "content_review": {"verdict": "PASS", "sha_match": True},
            "evaluator": {"threshold": 80, "high_max": 0},
        },
        "harness_coverage": {"min": 80, "kind_pass": "loop=criteria-test+content-review-verdict"},
    }
    comp.update(over)
    return comp


def test_validate_inventory_component_clean_skill(specfm_mod):
    assert specfm_mod.validate_inventory_component(_skill_component(specfm_mod)) == []


def test_validate_inventory_component_bad_kind(specfm_mod):
    errs = specfm_mod.validate_inventory_component({"id": "C01", "component_kind": "widget"})
    assert any("enum 外" in e for e in errs)


def test_validate_inventory_component_missing_build_target(specfm_mod):
    comp = _skill_component(specfm_mod)
    del comp["build_target"]
    assert any("build_target が空" in e for e in specfm_mod.validate_inventory_component(comp))


def test_validate_inventory_component_builder_mismatch(specfm_mod):
    comp = _skill_component(specfm_mod, builder="run-build-skill")
    assert any("builder" in e and "不整合" in e for e in specfm_mod.validate_inventory_component(comp))


def test_validate_inventory_component_loop_needs_criteria(specfm_mod):
    comp = _skill_component(specfm_mod)
    del comp["feedback_contract"]
    assert any("criteria 必須" in e for e in specfm_mod.validate_inventory_component(comp))
