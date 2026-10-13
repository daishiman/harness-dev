from __future__ import annotations

import importlib.util
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[3]
SCRIPT = ROOT / "plugins/harness-creator/scripts/lint-skill-runtime-profiles.py"
SPEC = importlib.util.spec_from_file_location("lint_skill_runtime_profiles", SCRIPT)
assert SPEC and SPEC.loader
MODULE = importlib.util.module_from_spec(SPEC)
sys.modules[SPEC.name] = MODULE
SPEC.loader.exec_module(MODULE)


def _skill(
    tmp_path: Path,
    *,
    kind: str = "run",
    goal_seek: str = "  engine: inline\n  fork: inline\n",
    tools: tuple[str, ...] = ("Read",),
) -> tuple[Path, Path]:
    root = tmp_path
    skill = root / "plugins/demo/skills/run-demo/SKILL.md"
    skill.parent.mkdir(parents=True)
    tools_yaml = "\n".join(f"  - {tool}" for tool in tools)
    block = f"goal_seek:\n{goal_seek}" if goal_seek else ""
    skill.write_text(
        f"---\nname: run-demo\nallowed-tools:\n{tools_yaml}\nkind: {kind}\n"
        f"prefix: {kind}\n{block}---\n\n## ゴールシーク実行\n",
        encoding="utf-8",
    )
    return root, skill


def test_inline_profile_passes(tmp_path: Path) -> None:
    root, skill = _skill(tmp_path)
    profile = MODULE.inspect_skill(skill, root / "plugins")
    assert profile.findings == ()
    assert profile.engine == "inline"
    assert profile.fork == "inline"


def test_inline_without_agent_tool_rejects_mandatory_agent_fork_prose(tmp_path: Path) -> None:
    root, skill = _skill(tmp_path)
    skill.write_text(
        skill.read_text(encoding="utf-8")
        + "\n- `Agent` で分離 context に fork する。\n",
        encoding="utf-8",
    )
    profile = MODULE.inspect_skill(skill, root / "plugins")
    assert any("本文が分離委譲を必須化" in finding for finding in profile.findings)


def test_loop_profile_is_required(tmp_path: Path) -> None:
    root, skill = _skill(tmp_path, goal_seek="")
    profile = MODULE.inspect_skill(skill, root / "plugins")
    assert any("goal_seek block" in finding for finding in profile.findings)
    assert any("goal_seek.engine" in finding for finding in profile.findings)
    assert any("goal_seek.fork" in finding for finding in profile.findings)


def test_subagent_requires_agent_tool(tmp_path: Path) -> None:
    root, skill = _skill(
        tmp_path, goal_seek="  engine: inline\n  fork: subagent\n"
    )
    profile = MODULE.inspect_skill(skill, root / "plugins")
    assert any("allowed-tools に Agent/Task がない" in finding for finding in profile.findings)


def test_subagent_with_agent_tool_passes(tmp_path: Path) -> None:
    root, skill = _skill(
        tmp_path,
        goal_seek="  engine: inline\n  fork: subagent\n",
        tools=("Read", "Agent"),
    )
    profile = MODULE.inspect_skill(skill, root / "plugins")
    assert profile.findings == ()


def test_subagent_with_claude_task_tool_passes(tmp_path: Path) -> None:
    root, skill = _skill(
        tmp_path,
        goal_seek="  engine: inline\n  fork: subagent\n",
        tools=("Read", "Task"),
    )
    profile = MODULE.inspect_skill(skill, root / "plugins")
    assert profile.findings == ()


def test_task_graph_requires_all_assets(tmp_path: Path) -> None:
    root, skill = _skill(
        tmp_path,
        goal_seek=(
            "  engine: task-graph\n"
            "  engine_profile: checklist-graph\n"
            "  full_task_spec_graph: false\n"
            "  fork: inline\n"
        ),
    )
    skill.write_text(
        skill.read_text(encoding="utf-8")
        + "depends_on extract-ready-set-from-checklist.py build-self-reflection-entry.py "
        + "ready_set selected_item\n",
        encoding="utf-8",
    )
    profile = MODULE.inspect_skill(skill, root / "plugins")
    assert any("engine asset が不足" in finding for finding in profile.findings)

    scripts = skill.parent / "scripts"
    scripts.mkdir()
    templates = (
        root
        / "plugins/harness-creator/skills/run-build-skill/templates"
        / "task-graph-engine/scripts"
    )
    templates.mkdir(parents=True)
    for name in MODULE.TASK_GRAPH_ASSETS:
        (templates / name).write_text("# fixture\n", encoding="utf-8")
        (scripts / name).write_text("# fixture\n", encoding="utf-8")
    profile = MODULE.inspect_skill(skill, root / "plugins")
    assert profile.findings == ()

    (scripts / MODULE.TASK_GRAPH_ASSETS[0]).write_text("# drift\n", encoding="utf-8")
    profile = MODULE.inspect_skill(skill, root / "plugins")
    assert any("正本と不一致" in finding for finding in profile.findings)


def test_inline_rejects_unused_task_graph_assets(tmp_path: Path) -> None:
    root, skill = _skill(tmp_path)
    scripts = skill.parent / "scripts"
    scripts.mkdir()
    (scripts / MODULE.TASK_GRAPH_ASSETS[0]).write_text("# fixture\n", encoding="utf-8")
    profile = MODULE.inspect_skill(skill, root / "plugins")
    assert any("task-graph asset が残存" in finding for finding in profile.findings)


def test_goal_seek_anchor_validator_must_match_canonical(tmp_path: Path) -> None:
    root, skill = _skill(tmp_path)
    skill.write_text(
        skill.read_text(encoding="utf-8")
        + '\npython3 "${CLAUDE_PLUGIN_ROOT}/scripts/validate-inline-goal-seek-anchor.py"\n',
        encoding="utf-8",
    )
    profile = MODULE.inspect_skill(skill, root / "plugins")
    assert any("plugin の scripts/ に写しが不在" in finding for finding in profile.findings)

    canonical = (
        root
        / "plugins/harness-creator/skills/run-build-skill/templates"
        / "goal-seek-runtime/scripts/validate-inline-goal-seek-anchor.py"
    )
    canonical.parent.mkdir(parents=True)
    canonical.write_text("# canonical\n", encoding="utf-8")
    deployed = root / "plugins/demo/scripts/validate-inline-goal-seek-anchor.py"
    deployed.parent.mkdir(parents=True)
    deployed.write_text("# drift\n", encoding="utf-8")
    profile = MODULE.inspect_skill(skill, root / "plugins")
    assert any("正本と不一致" in finding for finding in profile.findings)
    deployed.write_bytes(canonical.read_bytes())
    assert MODULE.inspect_skill(skill, root / "plugins").findings == ()


def test_goal_seek_anchor_validator_may_be_bundled_in_skill(tmp_path: Path) -> None:
    root, skill = _skill(tmp_path)
    skill.write_text(
        skill.read_text(encoding="utf-8")
        + '\npython3 "$SKILL_ROOT/scripts/validate-inline-goal-seek-anchor.py"\n',
        encoding="utf-8",
    )
    canonical = (
        root
        / "plugins/harness-creator/skills/run-build-skill/templates"
        / "goal-seek-runtime/scripts/validate-inline-goal-seek-anchor.py"
    )
    canonical.parent.mkdir(parents=True)
    canonical.write_text("# canonical\n", encoding="utf-8")
    bundled = skill.parent / "scripts/validate-inline-goal-seek-anchor.py"
    bundled.parent.mkdir(parents=True)
    bundled.write_text("# drift\n", encoding="utf-8")
    profile = MODULE.inspect_skill(skill, root / "plugins")
    assert any("正本と不一致" in finding for finding in profile.findings)
    bundled.write_bytes(canonical.read_bytes())
    assert MODULE.inspect_skill(skill, root / "plugins").findings == ()

    # plugin scripts/ にも写しがあるなら、どちらも正本と一致していなければならない。
    plugin_copy = root / "plugins/demo/scripts/validate-inline-goal-seek-anchor.py"
    plugin_copy.parent.mkdir(parents=True)
    plugin_copy.write_text("# drift\n", encoding="utf-8")
    profile = MODULE.inspect_skill(skill, root / "plugins")
    assert any("正本と不一致" in finding for finding in profile.findings)


def test_goal_seek_anchor_accepts_run_skill_feedback_vendor_path(tmp_path: Path) -> None:
    # 配布コピーの run-skill-feedback は plugin 直下に写しを持たず、自分の skills/…/scripts/ に
    # 同梱して $SKILL_ROOT から呼ぶ。この置き場所を認め、正本との drift は検出する。
    root, demo = _skill(tmp_path)
    skill = demo.parent.parent / "run-skill-feedback" / "SKILL.md"
    skill.parent.mkdir(parents=True)
    skill.write_text(
        demo.read_text(encoding="utf-8").replace("name: run-demo", "name: run-skill-feedback")
        + '\npython3 "$SKILL_ROOT/scripts/validate-inline-goal-seek-anchor.py"\n',
        encoding="utf-8",
    )
    canonical = (
        root
        / "plugins/harness-creator/skills/run-build-skill/templates"
        / "goal-seek-runtime/scripts/validate-inline-goal-seek-anchor.py"
    )
    canonical.parent.mkdir(parents=True)
    canonical.write_text("# canonical\n", encoding="utf-8")
    vendored = (
        root
        / "plugins/demo/skills/run-skill-feedback/scripts"
        / "validate-inline-goal-seek-anchor.py"
    )
    vendored.parent.mkdir(parents=True)
    vendored.write_bytes(canonical.read_bytes())
    profile = MODULE.inspect_skill(skill, root / "plugins")
    assert not any(
        "validate-inline-goal-seek-anchor.py" in finding
        for finding in profile.findings
    )

    vendored.write_text("# drift\n", encoding="utf-8")
    profile = MODULE.inspect_skill(skill, root / "plugins")
    assert any("正本と不一致" in finding for finding in profile.findings)


def test_agent_team_requires_fan_out_fan_in_and_ownership(tmp_path: Path) -> None:
    root, skill = _skill(
        tmp_path,
        goal_seek="  engine: inline\n  fork: agent-team\n",
        tools=("Read", "Agent"),
    )
    profile = MODULE.inspect_skill(skill, root / "plugins")
    assert any("並列所有権配線が不足" in finding for finding in profile.findings)

    skill.write_text(
        skill.read_text(encoding="utf-8")
        + "fan-out workers, fan-in results, explicit file ownership\n",
        encoding="utf-8",
    )
    profile = MODULE.inspect_skill(skill, root / "plugins")
    assert profile.findings == ()


def test_non_loop_skill_is_not_applicable(tmp_path: Path) -> None:
    root, skill = _skill(tmp_path, kind="assign", goal_seek="")
    profile = MODULE.inspect_skill(skill, root / "plugins")
    assert profile.applicable is False
    assert profile.findings == ()


def test_non_loop_skill_rejects_runtime_profile(tmp_path: Path) -> None:
    root, skill = _skill(tmp_path, kind="assign")
    profile = MODULE.inspect_skill(skill, root / "plugins")
    assert any("runtime profile 非適用" in finding for finding in profile.findings)


def test_collection_excludes_nested_test_fixtures(tmp_path: Path) -> None:
    root, canonical = _skill(tmp_path)
    fixture = root / "plugins/demo/tests/fixtures/skills/run-fixture/SKILL.md"
    fixture.parent.mkdir(parents=True)
    fixture.write_text("---\nkind: run\n---\n", encoding="utf-8")
    assert MODULE.collect_skills(root) == [canonical]


def test_manifest_dependencies_and_delegate_refs_are_validated(tmp_path: Path) -> None:
    root, skill = _skill(tmp_path)
    text = skill.read_text(encoding="utf-8").replace(
        "prefix: run\n", "prefix: run\nmanifest: workflow-manifest.json\n"
    )
    skill.write_text(text, encoding="utf-8")
    (skill.parent / "workflow-manifest.json").write_text(
        '{"phases": ['
        '{"id": "P1", "dependsOn": ["P2"], "delegateSkill": "missing"},'
        '{"id": "P2", "dependsOn": ["P1"]}'
        "]}",
        encoding="utf-8",
    )
    profile = MODULE.inspect_skill(skill, root / "plugins")
    assert any("delegateSkill が不在" in finding for finding in profile.findings)
    assert any("dependsOn が循環" in finding for finding in profile.findings)


def test_legacy_loop_declaration_findings_are_demoted(tmp_path: Path) -> None:
    root, skill = _skill(tmp_path, goal_seek="")
    profile = MODULE.inspect_skill(skill, root / "plugins")
    enforced, legacy = profile.split_findings()
    assert profile.is_legacy_loop is True
    assert enforced == ()
    assert len(legacy) == 3


def test_declared_loop_keeps_findings_enforced(tmp_path: Path) -> None:
    root, skill = _skill(
        tmp_path, goal_seek="  engine: inline\n  fork: subagent\n"
    )
    profile = MODULE.inspect_skill(skill, root / "plugins")
    enforced, legacy = profile.split_findings()
    assert profile.is_legacy_loop is False
    assert legacy == ()
    assert any("allowed-tools に Agent/Task がない" in finding for finding in enforced)


def test_fork_tools_baseline_path_is_demoted(tmp_path: Path) -> None:
    root = tmp_path
    skill = (
        root / "plugins/system-spec-harness/skills/run-system-spec-compile/SKILL.md"
    )
    skill.parent.mkdir(parents=True)
    skill.write_text(
        "---\nname: run-system-spec-compile\nallowed-tools:\n  - Read\n"
        "kind: run\nprefix: run\ngoal_seek:\n  engine: inline\n  fork: subagent\n"
        "---\n\n## ゴールシーク実行\n",
        encoding="utf-8",
    )
    profile = MODULE.inspect_skill(skill, root / "plugins")
    enforced, legacy = profile.split_findings()
    assert enforced == ()
    assert any("allowed-tools に Agent/Task がない" in finding for finding in legacy)


DEMO_SKILL_PATH = "plugins/demo/skills/run-demo/SKILL.md"


def test_report_exit_uses_legacy_ratchet(tmp_path: Path, monkeypatch, capsys) -> None:
    """path 固定 ratchet: 登録済みなら通し、未登録の legacy loop skill なら落ちること。"""
    root, _skill_path = _skill(tmp_path, goal_seek="")
    monkeypatch.setattr(
        MODULE, "LEGACY_LOOP_BASELINE_PATHS", frozenset({DEMO_SKILL_PATH})
    )
    # 実 repo の FORK_TOOLS_BASELINE は一時 repo に無いので、全体実行では陳腐化になる。
    monkeypatch.setattr(MODULE, "FORK_TOOLS_BASELINE", frozenset())
    assert MODULE.main(["--repo-root", str(root)]) == 0
    captured = capsys.readouterr()
    assert "legacy=1 registered=1 unlisted=0 stale=0" in captured.out
    assert "[legacy]" in captured.err

    monkeypatch.setattr(MODULE, "LEGACY_LOOP_BASELINE_PATHS", frozenset())
    assert MODULE.main(["--repo-root", str(root)]) == 1
    captured = capsys.readouterr()
    assert "ratchet 超過" in captured.err
    assert DEMO_SKILL_PATH in captured.err


def test_stale_baseline_entry_fails(tmp_path: Path, monkeypatch, capsys) -> None:
    """返済済み (goal_seek 宣言済み) の path が登録に残っていたら落ちること。

    片方向 ratchet を防ぐ検査。登録を残したままだと、同 path が将来 legacy に戻った際に
    黙って再免除されてしまう。
    """
    root, _skill_path = _skill(tmp_path)  # goal_seek 宣言済み = legacy でない
    monkeypatch.setattr(
        MODULE, "LEGACY_LOOP_BASELINE_PATHS", frozenset({DEMO_SKILL_PATH})
    )
    assert MODULE.main(["--repo-root", str(root)]) == 1
    captured = capsys.readouterr()
    assert "免除が陳腐化" in captured.err
    assert DEMO_SKILL_PATH in captured.err


def test_stale_baseline_entry_covers_deleted_path(
    tmp_path: Path, monkeypatch, capsys
) -> None:
    """実在しなくなった path も陳腐化として検出されること (リネーム/削除の取りこぼし防止)。"""
    root, _skill_path = _skill(tmp_path, goal_seek="")
    monkeypatch.setattr(
        MODULE,
        "LEGACY_LOOP_BASELINE_PATHS",
        frozenset({DEMO_SKILL_PATH, "plugins/gone/skills/run-gone/SKILL.md"}),
    )
    assert MODULE.main(["--repo-root", str(root)]) == 1
    # [legacy] finding 行にも demo path は出るので、陳腐化メッセージ行だけを見る。
    stale_line = next(
        line for line in capsys.readouterr().err.splitlines() if "免除が陳腐化" in line
    )
    assert "plugins/gone/skills/run-gone/SKILL.md" in stale_line
    assert DEMO_SKILL_PATH not in stale_line


def test_stale_check_is_skipped_when_scope_is_filtered(
    tmp_path: Path, monkeypatch, capsys
) -> None:
    """--plugin/--skill 絞り込み時は陳腐化検査を行わないこと。

    登録は repo 全体の定数なので、範囲外 plugin の登録が「今回集めた path に無い」ことは
    返済の証拠にならない。誤検出に従って登録を削ると全体実行で unlisted へ転じてしまう。
    """
    root, _skill_path = _skill(tmp_path, goal_seek="")
    monkeypatch.setattr(
        MODULE,
        "LEGACY_LOOP_BASELINE_PATHS",
        frozenset({DEMO_SKILL_PATH, "plugins/other/skills/run-other/SKILL.md"}),
    )
    # 全体実行では範囲外の登録が陳腐化として出る。
    assert MODULE.main(["--repo-root", str(root)]) == 1
    assert "免除が陳腐化" in capsys.readouterr().err
    # 同じ登録でも絞り込み実行なら誤検出しない。
    assert MODULE.main(["--repo-root", str(root), "--plugin", "demo"]) == 0
    captured = capsys.readouterr()
    assert "免除が陳腐化" not in captured.err
    # 検査していないことを 0 件と区別して出す。
    assert "stale=skipped" in captured.out
    assert "stale=0" not in captured.out


def test_replica_skill_name_is_allowed_without_path_registration(
    tmp_path: Path, monkeypatch, capsys
) -> None:
    """配布複製は skill 名で一括許容する (plugin 追加のたび path を足さずに済むこと)。"""
    root, _skill_path = _skill(tmp_path, goal_seek="")
    monkeypatch.setattr(MODULE, "LEGACY_LOOP_BASELINE_PATHS", frozenset())
    monkeypatch.setattr(MODULE, "LEGACY_LOOP_REPLICA_SKILLS", frozenset({"run-demo"}))
    # 実 repo の FORK_TOOLS_BASELINE は一時 repo に無いので、全体実行では陳腐化になる。
    monkeypatch.setattr(MODULE, "FORK_TOOLS_BASELINE", frozenset())
    assert MODULE.main(["--repo-root", str(root)]) == 0
    assert "[legacy]" in capsys.readouterr().err


def test_stale_fork_tools_registration_fails(
    tmp_path: Path, monkeypatch, capsys
) -> None:
    """FORK_TOOLS_BASELINE も両方向 ratchet であること (返済済み/消滅済みの登録で落ちる)。

    legacy loop 側にだけ陳腐化検査があり、fork/tools 側は片方向だった。解消しても登録が
    残り、同じ path が将来再び不整合になった時に黙って再免除される。
    """
    root, _skill_path = _skill(tmp_path, goal_seek="  engine: inline\n  fork: inline\n")
    # fork=inline なので allowed-tools 不整合 finding は出ない = 登録は返済済み。
    # legacy 側の実登録は tmp root に実在せず陳腐化で先に落ちるので空へ差し替える。
    monkeypatch.setattr(MODULE, "LEGACY_LOOP_BASELINE_PATHS", frozenset())
    monkeypatch.setattr(MODULE, "FORK_TOOLS_BASELINE", frozenset({DEMO_SKILL_PATH}))
    assert MODULE.main(["--repo-root", str(root)]) == 1
    captured = capsys.readouterr()
    assert "fork/allowed-tools ratchet の免除が陳腐化" in captured.err
    assert DEMO_SKILL_PATH in captured.err

    # 対照: 登録を外せば通る。
    monkeypatch.setattr(MODULE, "FORK_TOOLS_BASELINE", frozenset())
    assert MODULE.main(["--repo-root", str(root)]) == 0
    assert "fork_tools_stale=0" in capsys.readouterr().out


def test_unlisted_legacy_paths_matches_skill_segment_not_substring(monkeypatch) -> None:
    """複製判定は skill ディレクトリ名の完全一致であり、部分一致で緩まないこと。"""
    monkeypatch.setattr(MODULE, "LEGACY_LOOP_BASELINE_PATHS", frozenset())
    monkeypatch.setattr(
        MODULE, "LEGACY_LOOP_REPLICA_SKILLS", frozenset({"run-skill-feedback"})
    )
    paths = (
        "plugins/a/skills/run-skill-feedback/SKILL.md",
        "plugins/b/skills/run-skill-feedback-extra/SKILL.md",
        "plugins/c/skills/run-other/SKILL.md",
    )
    assert MODULE._unlisted_legacy_paths(paths) == (
        "plugins/b/skills/run-skill-feedback-extra/SKILL.md",
        "plugins/c/skills/run-other/SKILL.md",
    )


def test_manifest_agent_ref_must_exist(tmp_path: Path) -> None:
    root, skill = _skill(tmp_path)
    text = skill.read_text(encoding="utf-8").replace(
        "prefix: run\n", "prefix: run\nmanifest: workflow-manifest.json\n"
    )
    skill.write_text(text, encoding="utf-8")
    (skill.parent / "workflow-manifest.json").write_text(
        '{"phases": [{"id": "P1", "dependsOn": [], '
        '"delegateType": "agent", "delegateName": "missing-agent"}]}',
        encoding="utf-8",
    )
    profile = MODULE.inspect_skill(skill, root / "plugins")
    assert any("delegate agent が不在" in finding for finding in profile.findings)


def test_manifest_non_object_top_level_is_finding(tmp_path: Path) -> None:
    """top-level が配列などの manifest は traceback ではなく finding で fail-closed にする。"""
    root, skill = _skill(tmp_path)
    text = skill.read_text(encoding="utf-8").replace(
        "prefix: run\n", "prefix: run\nmanifest: workflow-manifest.json\n"
    )
    skill.write_text(text, encoding="utf-8")
    manifest = skill.parent / "workflow-manifest.json"
    for body, kind in (
        ('[{"id": "P1", "dependsOn": []}]', "list"),
        ('"phases"', "str"),
        ("null", "NoneType"),
        ("1", "int"),
    ):
        manifest.write_text(body, encoding="utf-8")
        profile = MODULE.inspect_skill(skill, root / "plugins")
        assert any(
            f"manifest の top-level が object でない ({kind})" in finding
            and "workflow-manifest.json" in finding
            for finding in profile.findings
        ), (body, profile.findings)


def test_manifest_non_object_top_level_exits_1(tmp_path: Path, monkeypatch, capsys) -> None:
    root, skill = _skill(tmp_path)
    text = skill.read_text(encoding="utf-8").replace(
        "prefix: run\n", "prefix: run\nmanifest: workflow-manifest.json\n"
    )
    skill.write_text(text, encoding="utf-8")
    (skill.parent / "workflow-manifest.json").write_text("[]", encoding="utf-8")
    monkeypatch.setattr(MODULE, "LEGACY_LOOP_BASELINE_PATHS", frozenset())
    monkeypatch.setattr(MODULE, "FORK_TOOLS_BASELINE", frozenset())
    assert MODULE.main(["--repo-root", str(root)]) == 1
    assert "manifest の top-level が object でない (list)" in capsys.readouterr().err


ANCHOR = "validate-inline-goal-seek-anchor.py"


def _anchor_skill(tmp_path: Path, call: str) -> tuple[Path, Path, Path]:
    root, skill = _skill(tmp_path)
    skill.write_text(skill.read_text(encoding="utf-8") + f"\n{call}\n", encoding="utf-8")
    canonical = (
        root / "plugins/harness-creator/skills/run-build-skill/templates"
        / "goal-seek-runtime/scripts" / ANCHOR
    )
    canonical.parent.mkdir(parents=True)
    canonical.write_text("# canonical\n", encoding="utf-8")
    return root, skill, canonical


def _place(path: Path, data: bytes) -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(data)
    return path


def test_skill_root_call_needs_the_skill_copy_not_only_the_plugin_copy(tmp_path: Path) -> None:
    # 実行時は $SKILL_ROOT/scripts を呼ぶので、plugin 側にだけ写しがあっても動かない。
    root, skill, canonical = _anchor_skill(
        tmp_path, f'python3 "$SKILL_ROOT/scripts/{ANCHOR}" p i'
    )
    _place(root / "plugins/demo/scripts" / ANCHOR, canonical.read_bytes())
    findings = MODULE.inspect_skill(skill, root / "plugins").findings
    assert any("skill の scripts/ に写しが不在" in f for f in findings), findings
    _place(skill.parent / "scripts" / ANCHOR, canonical.read_bytes())
    assert MODULE.inspect_skill(skill, root / "plugins").findings == ()


def test_plugin_root_call_needs_the_plugin_copy_not_only_the_skill_copy(tmp_path: Path) -> None:
    root, skill, canonical = _anchor_skill(
        tmp_path, f'python3 "${{PLUGIN_ROOT:-${{CLAUDE_PLUGIN_ROOT}}}}/scripts/{ANCHOR}" p i'
    )
    _place(skill.parent / "scripts" / ANCHOR, canonical.read_bytes())
    findings = MODULE.inspect_skill(skill, root / "plugins").findings
    assert any("plugin の scripts/ に写しが不在" in f for f in findings), findings
    _place(root / "plugins/demo/scripts" / ANCHOR, canonical.read_bytes())
    assert MODULE.inspect_skill(skill, root / "plugins").findings == ()


def test_prose_mention_of_the_anchor_is_not_a_call(tmp_path: Path) -> None:
    root, skill = _skill(tmp_path)
    skill.write_text(
        skill.read_text(encoding="utf-8")
        + f"\nこの skill は {ANCHOR} を使わない。正本は "
        f"`run-build-skill/templates/goal-seek-runtime/scripts/{ANCHOR}`。\n",
        encoding="utf-8",
    )
    assert MODULE.inspect_skill(skill, root / "plugins").findings == ()


def test_missing_canonical_is_reported_as_missing_not_as_drift(tmp_path: Path) -> None:
    root, skill = _skill(tmp_path)
    skill.write_text(
        skill.read_text(encoding="utf-8") + f'\npython3 "$SKILL_ROOT/scripts/{ANCHOR}"\n',
        encoding="utf-8",
    )
    _place(skill.parent / "scripts" / ANCHOR, b"# copy\n")
    findings = MODULE.inspect_skill(skill, root / "plugins").findings
    assert any("正本が見つからない" in f for f in findings), findings
    assert not any("正本と不一致" in f for f in findings)


def test_anchor_copy_symlinked_outside_the_plugin_is_rejected(tmp_path: Path) -> None:
    root, skill, canonical = _anchor_skill(tmp_path, f'python3 "$SKILL_ROOT/scripts/{ANCHOR}"')
    outside = _place(tmp_path / "elsewhere" / ANCHOR, canonical.read_bytes())
    (skill.parent / "scripts").mkdir()
    (skill.parent / "scripts" / ANCHOR).symlink_to(outside)
    findings = MODULE.inspect_skill(skill, root / "plugins").findings
    assert any("plugin の外を指す symlink" in f for f in findings), findings


def test_unreadable_anchor_copy_exits_2_without_traceback(tmp_path: Path, monkeypatch, capsys) -> None:
    import os
    import pytest

    if os.geteuid() == 0:
        pytest.skip("root は chmod 000 でも読める")
    root, skill, canonical = _anchor_skill(tmp_path, f'python3 "$SKILL_ROOT/scripts/{ANCHOR}"')
    copy = _place(skill.parent / "scripts" / ANCHOR, canonical.read_bytes())
    copy.chmod(0)
    try:
        assert MODULE.main(["--repo-root", str(root), "--plugin", "demo"]) == 2
    finally:
        copy.chmod(0o644)
    err = capsys.readouterr().err
    assert "入力を読めない" in err and ANCHOR in err


def test_non_utf8_skill_md_is_a_read_error_finding(tmp_path: Path) -> None:
    root, skill = _skill(tmp_path)
    skill.write_bytes(b"\xff" + skill.read_bytes())
    findings = MODULE.inspect_skill(skill, root / "plugins").findings
    assert len(findings) == 1 and findings[0].startswith("read error:")


def test_stale_fork_tools_baseline_entry_fails_only_in_full_scope(
    tmp_path: Path, monkeypatch, capsys
) -> None:
    root, _skill_path = _skill(tmp_path)  # fork=inline: Agent/Task 不足の finding は無い
    monkeypatch.setattr(MODULE, "FORK_TOOLS_BASELINE", frozenset({DEMO_SKILL_PATH}))
    monkeypatch.setattr(MODULE, "LEGACY_LOOP_BASELINE_PATHS", frozenset())
    assert MODULE.main(["--repo-root", str(root)]) == 1
    captured = capsys.readouterr()
    assert "fork/allowed-tools ratchet の免除が陳腐化" in captured.err
    assert DEMO_SKILL_PATH in captured.err
    assert "fork_tools_stale=1" in captured.out

    assert MODULE.main(["--repo-root", str(root), "--plugin", "demo"]) == 0
    assert "fork_tools_stale=skipped" in capsys.readouterr().out


def test_json_report_marks_whether_stale_was_checked(tmp_path: Path, monkeypatch, capsys) -> None:
    import json

    root, _skill_path = _skill(tmp_path)
    monkeypatch.setattr(MODULE, "FORK_TOOLS_BASELINE", frozenset())
    monkeypatch.setattr(MODULE, "LEGACY_LOOP_BASELINE_PATHS", frozenset())
    assert MODULE.main(["--repo-root", str(root), "--json"]) == 0
    assert json.loads(capsys.readouterr().out)["summary"]["stale_checked"] is True
    assert MODULE.main(["--repo-root", str(root), "--plugin", "demo", "--json"]) == 0
    assert json.loads(capsys.readouterr().out)["summary"]["stale_checked"] is False
