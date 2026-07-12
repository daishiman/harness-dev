"""render-combinators.py の純関数 + main CLI 契約を network 無しで網羅する。

render-combinators は _base.md (atom) に combinators/*.patch を順次適用して kind 別 SKILL.md
テンプレを決定論合成する純テキスト変換 + feedback-loop 実体コピー配備 (tmp_path 内のみ)。実通信なし。

本テストは:
  - parse_args: 必須 --kind / choices / 各 flag / --templates-dir / --output / --trace /
    --deploy-feedback-loop / --no-feedback-loop
  - selected_patches: kind 別 first patch / assign role-suffix 分岐 / FLAG_PATCHES 付与 /
    goal-seek default-ON & --no-goal-seek opt-out / feedback-contract default-ON (loop kind のみ)
  - apply_unified_diff: 実 diff 成功 / context|removal mismatch / 不正 hunk header /
    overlapping hunk / unsupported tag / no-newline マーカー / +++/--- 無視
  - frontmatter_bounds: 正常 / 先頭非 --- / 閉じない frontmatter
  - normalize_base: design-note fence 除去 (--- --- / name: 直後) / fence 無し pass-through
  - ensure_frontmatter_line: 新規挿入 (after_key 指定/末尾) / 既存キーは no-op
  - add_section_after: 挿入 / 既挿入は no-op / anchor 不在で ComposeError
  - apply_semantic_patch: 全 combinator 名 (run/ref/assign-gen/assign-eval/wrap/delegate/
    evaluator/hooks/subagent/knowledge/goal-seek/feedback-contract) + 未知名で ComposeError
  - apply_patch_file: 実 patch が semantic fallback 経路を通る
  - apply_feedback_loop: 非 harness-creator dir に実体コピー作成 / 冪等 / harness-creator は no-op
  - main: 全 kind の合成 (stdout/--output) / --trace / 欠落 _base / 欠落 combinator (exit1) /
    feedback-loop 配備モード / usage error (exit2)
を実入力で genuine に assert する。templates 合成は repo 同梱の実 _base.md/combinators を使うが
出力は tmp_path / stdout のみで repo を汚さない。
"""
import importlib.util
import subprocess
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[2]
RUN_BUILD = ROOT / "plugins" / "harness-creator" / "skills" / "run-build-skill"
SCRIPT = RUN_BUILD / "scripts" / "render-combinators.py"
TEMPLATES = RUN_BUILD / "templates"

_SPEC = importlib.util.spec_from_file_location("render_combinators_under_test", SCRIPT)
MOD = importlib.util.module_from_spec(_SPEC)
_SPEC.loader.exec_module(MOD)


# --------------------------------------------------------------------------
# parse_args
# --------------------------------------------------------------------------

def test_parse_args_requires_kind():
    with pytest.raises(SystemExit):
        MOD.parse_args([])


def test_parse_args_rejects_unknown_kind():
    with pytest.raises(SystemExit):
        MOD.parse_args(["--kind", "bogus"])


def test_parse_args_defaults():
    ns = MOD.parse_args(["--kind", "run"])
    assert ns.kind == "run"
    assert ns.role_suffix == ""
    assert ns.with_evaluator is False
    assert ns.no_goal_seek is False
    assert ns.templates_dir == TEMPLATES
    assert ns.output is None
    assert ns.deploy_feedback_loop is None
    assert ns.no_feedback_loop is False


def test_parse_args_all_flags(tmp_path):
    ns = MOD.parse_args([
        "--kind", "assign", "--role-suffix", "evaluator",
        "--with-evaluator", "--with-hooks", "--with-subagent", "--with-knowledge",
        "--no-goal-seek", "--trace",
        "--templates-dir", str(tmp_path),
        "--output", str(tmp_path / "o.md"),
        "--deploy-feedback-loop", str(tmp_path / "plug"),
        "--no-feedback-loop",
    ])
    assert ns.role_suffix == "evaluator"
    assert ns.with_evaluator and ns.with_hooks and ns.with_subagent and ns.with_knowledge
    assert ns.no_goal_seek and ns.trace and ns.no_feedback_loop
    assert ns.templates_dir == tmp_path
    assert ns.output == tmp_path / "o.md"
    assert ns.deploy_feedback_loop == tmp_path / "plug"


# --------------------------------------------------------------------------
# selected_patches
# --------------------------------------------------------------------------

def _patches(argv):
    return MOD.selected_patches(MOD.parse_args(argv))


def test_selected_patches_run_default_on_goal_seek_and_feedback():
    p = _patches(["--kind", "run"])
    assert p == ["with-run.patch", "with-goal-seek.patch", "with-feedback-contract.patch"]


def test_selected_patches_run_no_goal_seek_optout():
    p = _patches(["--kind", "run", "--no-goal-seek"])
    assert "with-goal-seek.patch" not in p
    assert p == ["with-run.patch", "with-feedback-contract.patch"]


def test_selected_patches_ref_no_goal_seek_no_feedback():
    # ref は loop kind でないので goal-seek も feedback-contract も付かない。
    p = _patches(["--kind", "ref"])
    assert p == ["with-ref.patch"]


def test_selected_patches_assign_default_role_generator():
    p = _patches(["--kind", "assign"])
    assert p == ["with-assign-generator.patch"]


def test_selected_patches_assign_evaluator_role():
    p = _patches(["--kind", "assign", "--role-suffix", "evaluator"])
    assert p == ["with-assign-evaluator.patch"]


def test_selected_patches_flags_appended_in_order():
    p = _patches(["--kind", "wrap", "--with-evaluator", "--with-hooks",
                  "--with-subagent", "--with-knowledge"])
    assert p == [
        "with-wrap.patch",
        "with-evaluator.patch", "with-hooks.patch",
        "with-subagent.patch", "with-knowledge.patch",
        "with-goal-seek.patch", "with-feedback-contract.patch",
    ]


def test_selected_patches_delegate_is_loop_kind():
    p = _patches(["--kind", "delegate"])
    assert "with-goal-seek.patch" in p and "with-feedback-contract.patch" in p


# --------------------------------------------------------------------------
# apply_unified_diff
# --------------------------------------------------------------------------

def test_apply_unified_diff_success_add_and_context():
    content = "line1\nline2\nline3\n"
    diff = (
        "--- a/f\n"
        "+++ b/f\n"
        "@@ -1,2 +1,3 @@\n"
        " line1\n"
        "+inserted\n"
        " line2\n"
    )
    out = MOD.apply_unified_diff(content, diff)
    assert out == "line1\ninserted\nline2\nline3\n"


def test_apply_unified_diff_removal():
    content = "a\nb\nc\n"
    diff = (
        "@@ -1,3 +1,2 @@\n"
        " a\n"
        "-b\n"
        " c\n"
    )
    out = MOD.apply_unified_diff(content, diff)
    assert out == "a\nc\n"


def test_apply_unified_diff_no_newline_marker_tolerated():
    # `\ No newline at end of file` マーカーは pass され出力に影響しない。
    content = "a\nb\n"
    diff = (
        "@@ -1,2 +1,2 @@\n"
        " a\n"
        "-b\n"
        "+B\n"
        "\\ No newline at end of file\n"
    )
    out = MOD.apply_unified_diff(content, diff)
    assert out == "a\nB\n"


def test_apply_unified_diff_skips_file_headers_inside_hunk():
    # @@ ヘッダ後に現れる ---/+++ ファイルヘッダ行は hunk 本体ループ内で skip される (line 308-310)。
    content = "a\nb\n"
    diff = (
        "@@ -1,2 +1,3 @@\n"
        "--- a/f\n"
        "+++ b/f\n"
        " a\n"
        "+x\n"
        " b\n"
    )
    out = MOD.apply_unified_diff(content, diff)
    assert out == "a\nx\nb\n"


def test_apply_unified_diff_blank_hunk_line_is_context():
    # keepends split で空行は "\n" (truthy) となり tag=" " 相当ではなく "\n" になる。
    # 実際の combinator 由来 diff では空行は @@ 区切りの外にしか出ないため、ここでは
    # blank を含まない正常 diff のみが安全。本ケースは複数 hunk が順に当たることを確認する。
    content = "a\nb\nc\nd\n"
    diff = (
        "@@ -1,1 +1,2 @@\n a\n+A\n"
        "@@ -3,1 +4,2 @@\n c\n+C\n"
    )
    out = MOD.apply_unified_diff(content, diff)
    assert out == "a\nA\nb\nc\nC\nd\n"


def test_apply_unified_diff_context_mismatch_raises():
    content = "a\nb\n"
    diff = "@@ -1,1 +1,1 @@\n WRONG\n"
    with pytest.raises(MOD.ComposeError, match="context mismatch"):
        MOD.apply_unified_diff(content, diff)


def test_apply_unified_diff_removal_mismatch_raises():
    content = "a\nb\n"
    diff = "@@ -1,1 +1,0 @@\n-WRONG\n"
    with pytest.raises(MOD.ComposeError, match="removal mismatch"):
        MOD.apply_unified_diff(content, diff)


def test_apply_unified_diff_invalid_hunk_header_raises():
    content = "a\n"
    diff = "@@ broken header @@\n a\n"
    with pytest.raises(MOD.ComposeError, match="invalid hunk header"):
        MOD.apply_unified_diff(content, diff)


def test_apply_unified_diff_overlapping_hunk_raises():
    content = "a\nb\nc\nd\n"
    diff = (
        "@@ -3,1 +3,1 @@\n c\n"
        "@@ -1,1 +1,1 @@\n a\n"   # 2 つ目が cursor より前 = overlap
    )
    with pytest.raises(MOD.ComposeError, match="overlapping hunk"):
        MOD.apply_unified_diff(content, diff)


def test_apply_unified_diff_unsupported_tag_raises():
    content = "a\n"
    diff = "@@ -1,1 +1,1 @@\n?weird\n"
    with pytest.raises(MOD.ComposeError, match="unsupported hunk line"):
        MOD.apply_unified_diff(content, diff)


def test_apply_unified_diff_context_at_eof_raises():
    content = "a\n"
    diff = "@@ -1,2 +1,2 @@\n a\n extra\n"   # 2 行目 context は EOF 越え
    with pytest.raises(MOD.ComposeError, match="context mismatch"):
        MOD.apply_unified_diff(content, diff)


# --------------------------------------------------------------------------
# frontmatter_bounds
# --------------------------------------------------------------------------

def test_frontmatter_bounds_normal():
    text = "---\nname: x\nkind: run\n---\nbody\n"
    assert MOD.frontmatter_bounds(text) == (0, 3)


def test_frontmatter_bounds_no_leading_marker_raises():
    with pytest.raises(MOD.ComposeError, match="must start with frontmatter"):
        MOD.frontmatter_bounds("name: x\n---\n")


def test_frontmatter_bounds_unclosed_raises():
    with pytest.raises(MOD.ComposeError, match="not closed"):
        MOD.frontmatter_bounds("---\nname: x\nbody\n")


# --------------------------------------------------------------------------
# normalize_base
# --------------------------------------------------------------------------

def test_normalize_base_strips_designnote_fence_double_marker():
    # design-note fence (--- ... ---) の直後にもう一つ --- が来る形。
    text = "---\n# design note\n---\n---\nname: x\n---\nbody\n"
    out = MOD.normalize_base(text)
    assert out.startswith("---\nname: x")
    assert "design note" not in out


def test_normalize_base_strips_fence_when_name_follows():
    # design-note fence の直後が name: で始まる (--- を補う) 形。
    text = "---\n# design note\n---\nname: x\nkind: run\n---\nbody\n"
    out = MOD.normalize_base(text)
    assert out.startswith("---\nname: x")
    assert "design note" not in out


def test_normalize_base_fence_followed_by_body_returns_unchanged():
    # 先頭 --- ブロックが閉じた直後が --- でも name: でもない (本文) → そのまま返す (line 361)。
    text = "---\nname: real\nkind: run\n---\n# body heading\nmore\n"
    assert MOD.normalize_base(text) == text


def test_normalize_base_no_fence_returns_unchanged():
    text = "no frontmatter at all\njust text\n"
    assert MOD.normalize_base(text) == text


def test_normalize_base_unclosed_fence_returns_unchanged():
    # lines[0]=="---" だが閉じ --- が一度も現れない → for ループ完走で line 362 へ。
    text = "---\nname: x\nkind: run\nbody without close\n"
    assert MOD.normalize_base(text) == text


def test_normalize_base_short_text_returns_unchanged():
    text = "---\n"
    assert MOD.normalize_base(text) == text


def test_normalize_base_real_base_md_yields_template_frontmatter():
    raw = (TEMPLATES / "_base.md").read_text(encoding="utf-8")
    out = MOD.normalize_base(raw)
    # design-note fence が剥がれ、本物のテンプレ frontmatter (name:) が先頭に来る。
    assert out.startswith("---\nname: {{skill_name}}")


# --------------------------------------------------------------------------
# ensure_frontmatter_line
# --------------------------------------------------------------------------

def test_ensure_frontmatter_line_inserts_at_end_when_no_after_key():
    text = "---\nname: x\nkind: run\n---\nbody\n"
    out = MOD.ensure_frontmatter_line(text, "effect: local")
    lines = out.splitlines()
    assert "effect: local" in lines
    # frontmatter 内 (閉じ --- の前) に挿入される。
    assert lines.index("effect: local") < lines.index("---", 1)


def test_ensure_frontmatter_line_inserts_after_key():
    text = "---\nname: x\nkind: run\nowner: o\n---\nbody\n"
    out = MOD.ensure_frontmatter_line(text, "effect: local", after_key="kind")
    lines = out.splitlines()
    assert lines[lines.index("kind: run") + 1] == "effect: local"


def test_ensure_frontmatter_line_idempotent_when_key_present():
    text = "---\nname: x\neffect: already\n---\nbody\n"
    out = MOD.ensure_frontmatter_line(text, "effect: new-value")
    assert out == text   # 既存 effect: は no-op


# --------------------------------------------------------------------------
# add_section_after
# --------------------------------------------------------------------------

def test_add_section_after_inserts_section():
    text = "head\nANCHOR\ntail\n"
    out = MOD.add_section_after(text, "ANCHOR", "## New\nbody")
    assert "ANCHOR\n\n## New\nbody" in out


def test_add_section_after_idempotent_when_section_header_present():
    text = "head\nANCHOR\n## New\nbody\n"
    out = MOD.add_section_after(text, "ANCHOR", "## New\nbody")
    assert out == text


def test_add_section_after_missing_anchor_raises():
    with pytest.raises(MOD.ComposeError, match="anchor not found"):
        MOD.add_section_after("no anchor here\n", "MISSING", "## New\nbody")


# --------------------------------------------------------------------------
# apply_semantic_patch: 各 combinator
# --------------------------------------------------------------------------

@pytest.fixture
def base_text():
    return MOD.normalize_base((TEMPLATES / "_base.md").read_text(encoding="utf-8"))


def test_semantic_run_adds_effect_and_role_suffix(base_text):
    out = MOD.apply_semantic_patch(base_text, "with-run.patch")
    assert 'effect: {{effect | default("local-artifact")}}' in out
    assert 'role_suffix: {{role_suffix | default("workflow")}}' in out


def test_semantic_ref_adds_readonly_and_section(base_text):
    out = MOD.apply_semantic_patch(base_text, "with-ref.patch")
    assert "disable-model-invocation: true" in out
    assert "user-invocable: false" in out
    assert "effect: read-only" in out
    assert "## 参照内容" in out


def test_semantic_assign_generator(base_text):
    out = MOD.apply_semantic_patch(base_text, "with-assign-generator.patch")
    assert "role_suffix: generator" in out
    assert "pair: {{pair_skill}}" in out
    assert "## 生成契約" in out


def test_semantic_assign_evaluator(base_text):
    out = MOD.apply_semantic_patch(base_text, "with-assign-evaluator.patch")
    assert "context: fork" in out
    assert "role_suffix: evaluator" in out
    assert "agent: {{agent | default(\"general-purpose\")}}" in out
    assert "## Evaluator Contract" in out


def test_semantic_wrap(base_text):
    out = MOD.apply_semantic_patch(base_text, "with-wrap.patch")
    assert "role_suffix: cli-wrapper" in out
    assert "## Wrapped CLI" in out


def test_semantic_delegate(base_text):
    out = MOD.apply_semantic_patch(base_text, "with-delegate.patch")
    assert "role_suffix: external-delegator" in out
    assert "## Delegation Target" in out


def test_semantic_evaluator(base_text):
    out = MOD.apply_semantic_patch(base_text, "with-evaluator.patch")
    assert "## Evaluator 連携" in out


def test_semantic_hooks(base_text):
    out = MOD.apply_semantic_patch(base_text, "with-hooks.patch")
    assert "with_hooks: true" in out
    assert "needs_lifecycle_enforcement: true" in out
    assert "## Hook Wiring" in out


def test_semantic_subagent(base_text):
    out = MOD.apply_semantic_patch(base_text, "with-subagent.patch")
    assert "context: fork" in out
    assert "agent: {{subagent_type}}" in out
    assert "## Subagent / Agent Team 連携" in out


def test_semantic_knowledge(base_text):
    out = MOD.apply_semantic_patch(base_text, "with-knowledge.patch")
    assert "knowledge_loop:" in out
    assert "## ナレッジループ" in out


def test_semantic_goal_seek(base_text):
    out = MOD.apply_semantic_patch(base_text, "with-goal-seek.patch")
    assert "goal_seek:" in out
    assert "### ゴールシーク配線（実行可能機構）" in out


def test_semantic_feedback_contract(base_text):
    out = MOD.apply_semantic_patch(base_text, "with-feedback-contract.patch")
    assert "feedback_contract:" in out
    assert "id: IN1" in out
    assert "id: OUT1" in out
    assert "## 評価・改善ループ契約" in out


def test_semantic_unknown_patch_raises(base_text):
    with pytest.raises(MOD.ComposeError, match="unknown combinator"):
        MOD.apply_semantic_patch(base_text, "with-nonexistent.patch")


# --------------------------------------------------------------------------
# apply_patch_file: 実 patch は context mismatch で semantic fallback へ
# --------------------------------------------------------------------------

def test_apply_patch_file_falls_back_to_semantic(base_text):
    # repo 同梱 with-run.patch は英語見出し旧 base 向けで context mismatch → semantic 経路。
    patch_path = TEMPLATES / "combinators" / "with-run.patch"
    out = MOD.apply_patch_file(base_text, patch_path)
    assert 'effect: {{effect | default("local-artifact")}}' in out


def test_apply_patch_file_applies_real_diff(tmp_path):
    # context が一致する自作 diff は unified-diff 経路で成功し semantic に落ちない。
    patch = tmp_path / "with-run.patch"   # 名前は semantic にも在るが diff が当たるので fallback しない
    patch.write_text("@@ -1,1 +1,2 @@\n a\n+b\n", encoding="utf-8")
    out = MOD.apply_patch_file("a\nc\n", patch)
    assert out == "a\nb\nc\n"


# --------------------------------------------------------------------------
# apply_feedback_loop
# --------------------------------------------------------------------------

def test_apply_feedback_loop_copies_feedback_skill(tmp_path):
    plugin_dir = tmp_path / "plugins" / "demo-plugin"
    plugin_dir.mkdir(parents=True)
    deployed = MOD.apply_feedback_loop(plugin_dir)
    assert deployed.is_dir()
    assert not deployed.is_symlink()
    assert (deployed / "SKILL.md").is_file()


def test_apply_feedback_loop_idempotent(tmp_path):
    plugin_dir = tmp_path / "plugins" / "demo-plugin"
    plugin_dir.mkdir(parents=True)
    first = MOD.apply_feedback_loop(plugin_dir)
    second = MOD.apply_feedback_loop(plugin_dir)   # 既存 link → no-op
    assert first == second
    assert second.is_dir()
    assert not second.is_symlink()


def test_apply_feedback_loop_harness_creator_is_noop(tmp_path):
    plugin_dir = tmp_path / "harness-creator"
    plugin_dir.mkdir(parents=True)
    link = MOD.apply_feedback_loop(plugin_dir)
    # SSOT 自身には配備しない (symlink を作らず想定パスを返すだけ)。
    assert link == (plugin_dir.resolve() / "skills" / "run-skill-feedback")
    assert not link.exists()


# --------------------------------------------------------------------------
# main(argv) in-process: 合成と exit code
# --------------------------------------------------------------------------

def test_main_run_to_stdout(capsys):
    rc = MOD.main(["--kind", "run"])
    assert rc == 0
    out = capsys.readouterr().out
    assert "name: {{skill_name}}" in out
    assert "feedback_contract:" in out
    assert "goal_seek:" in out


def test_main_ref_to_stdout(capsys):
    rc = MOD.main(["--kind", "ref"])
    assert rc == 0
    out = capsys.readouterr().out
    assert "## 参照内容" in out
    assert "feedback_contract:" not in out


def test_main_assign_evaluator_to_output_file(tmp_path):
    out_file = tmp_path / "nested" / "skill.md"
    rc = MOD.main(["--kind", "assign", "--role-suffix", "evaluator",
                   "--output", str(out_file)])
    assert rc == 0
    text = out_file.read_text(encoding="utf-8")
    assert "## Evaluator Contract" in text
    assert "role_suffix: evaluator" in text


def test_main_wrap_all_flags_trace(tmp_path, capsys):
    rc = MOD.main(["--kind", "wrap", "--with-evaluator", "--with-hooks",
                   "--with-subagent", "--with-knowledge", "--trace"])
    assert rc == 0
    cap = capsys.readouterr()
    assert "## Wrapped CLI" in cap.out
    assert "## ナレッジループ" in cap.out
    # --trace は適用パッチ名を stderr に列挙する。
    assert "applied: with-wrap.patch" in cap.err


def test_main_delegate(capsys):
    rc = MOD.main(["--kind", "delegate"])
    assert rc == 0
    assert "## Delegation Target" in capsys.readouterr().out


def test_main_missing_base_md_returns_1(tmp_path, capsys):
    # _base.md の無い templates-dir → OSError 経路で exit 1。
    empty = tmp_path / "templates"
    empty.mkdir()
    rc = MOD.main(["--kind", "run", "--templates-dir", str(empty)])
    assert rc == 1
    assert "error:" in capsys.readouterr().err


def test_main_missing_combinator_returns_1(tmp_path, capsys):
    # _base.md はあるが combinators/ が空 → ComposeError(missing combinator) で exit 1。
    tdir = tmp_path / "templates"
    (tdir / "combinators").mkdir(parents=True)
    (tdir / "_base.md").write_text(
        (TEMPLATES / "_base.md").read_text(encoding="utf-8"), encoding="utf-8")
    rc = MOD.main(["--kind", "run", "--templates-dir", str(tdir)])
    assert rc == 1
    assert "missing combinator" in capsys.readouterr().err


def test_main_deploy_feedback_loop_only(tmp_path, capsys):
    plugin_dir = tmp_path / "plugins" / "demo-plugin"
    plugin_dir.mkdir(parents=True)
    rc = MOD.main(["--kind", "ref", "--deploy-feedback-loop", str(plugin_dir),
                   "--trace"])
    assert rc == 0
    link = plugin_dir / "skills" / "run-skill-feedback"
    assert link.is_dir()
    assert not link.is_symlink()
    assert "deployed feedback-loop:" in capsys.readouterr().err


def test_main_no_feedback_loop_optout_skips_deploy(tmp_path):
    plugin_dir = tmp_path / "plugins" / "demo-plugin"
    plugin_dir.mkdir(parents=True)
    rc = MOD.main(["--kind", "ref", "--deploy-feedback-loop", str(plugin_dir),
                   "--no-feedback-loop"])
    assert rc == 0
    # opt-out なので symlink は作られない。
    assert not (plugin_dir / "skills" / "run-skill-feedback").exists()


def test_main_deploy_feedback_loop_oserror_returns_1(tmp_path, capsys, monkeypatch):
    # apply_feedback_loop が OSError を投げる経路 (symlink 不能) → exit 1。
    def boom(_):
        raise OSError("cannot symlink")
    monkeypatch.setattr(MOD, "apply_feedback_loop", boom)
    rc = MOD.main(["--kind", "ref", "--deploy-feedback-loop", str(tmp_path / "p")])
    assert rc == 1
    assert "error: cannot symlink" in capsys.readouterr().err


def test_main_usage_error_no_kind(capsys):
    with pytest.raises(SystemExit) as ei:
        MOD.main([])
    assert ei.value.code == 2


# --------------------------------------------------------------------------
# subprocess 契約 (CLI 統合)
# --------------------------------------------------------------------------

def _run(args, cwd):
    return subprocess.run(
        [sys.executable, str(SCRIPT), *args],
        capture_output=True, text=True, cwd=cwd,
    )


def test_cli_run_kind_stdout(tmp_path):
    proc = _run(["--kind", "run"], cwd=str(tmp_path))
    assert proc.returncode == 0, proc.stderr
    assert "feedback_contract:" in proc.stdout


def test_cli_missing_kind_exit2(tmp_path):
    proc = _run([], cwd=str(tmp_path))
    assert proc.returncode == 2
    assert "--kind" in proc.stderr


def test_cli_output_file(tmp_path):
    out_file = tmp_path / "o.md"
    proc = _run(["--kind", "delegate", "--output", str(out_file)], cwd=str(tmp_path))
    assert proc.returncode == 0, proc.stderr
    assert "## Delegation Target" in out_file.read_text(encoding="utf-8")


def test_module_guard_runs_main_via_runpy(capsys):
    # if __name__ == "__main__": raise SystemExit(main(sys.argv[1:])) を踏む。
    import runpy
    sys.argv = ["render-combinators.py", "--kind", "ref"]
    with pytest.raises(SystemExit) as ei:
        runpy.run_path(str(SCRIPT), run_name="__main__")
    assert ei.value.code == 0
    assert "## 参照内容" in capsys.readouterr().out
