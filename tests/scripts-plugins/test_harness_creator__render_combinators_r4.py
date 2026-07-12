"""Genuine functional tests for run-build-skill/scripts/render-combinators.py.

カバレッジ方針:
- parse_args / selected_patches: kind×flag×goal-seek×feedback-contract の patch 選択ロジックを
  全 kind (run/ref/assign/wrap/delegate)・全フラグ・opt-out 込みで網羅。
- apply_unified_diff: 正常 hunk 適用、context/removal/add、不正 hunk header、
  overlapping hunk、context/removal mismatch、unsupported tag の各 ComposeError 経路。
- frontmatter_bounds / normalize_base / ensure_frontmatter_line / add_section_after:
  純関数を実値で検証 (frontmatter 未開始/未閉じ、design-note fence 除去、重複キー無挿入、
  after_key 指定挿入、anchor 不在エラー、既挿入の冪等性)。
- apply_semantic_patch: 全 patch_name (with-run/ref/assign-*/wrap/delegate/evaluator/hooks/
  subagent/knowledge/goal-seek/feedback-contract/unknown) を実 _base.md に対して適用し
  frontmatter 行・セクション挿入を確認。
- apply_feedback_loop: tmp_path 配下で実体コピー配備の正常/冪等/harness-creator skip を検証
  (repo を汚さない)。
- main: 実テンプレートから run/ref を合成し stdout / --output / --trace、欠落 combinator・
  読込失敗の error 経路、--deploy-feedback-loop 副作用モードを駆動。

network/keychain/secret 依存は無い (純テキスト合成 + ローカル symlink) ため stub 不要。
すべての書込みは tmp_path に限定。ファイル名は `_r4` を付して衝突回避。
"""
import importlib.util
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[2]
RUN_BUILD = ROOT / "plugins" / "harness-creator" / "skills" / "run-build-skill"
SCRIPT = RUN_BUILD / "scripts" / "render-combinators.py"
TEMPLATES_DIR = RUN_BUILD / "templates"

_SPEC = importlib.util.spec_from_file_location("render_combinators_s4", SCRIPT)
RC = importlib.util.module_from_spec(_SPEC)
_SPEC.loader.exec_module(RC)


# ===================== parse_args / selected_patches =====================

def test_parse_args_defaults():
    ns = RC.parse_args(["--kind", "run"])
    assert ns.kind == "run"
    assert ns.with_evaluator is False
    assert ns.no_goal_seek is False
    # templates-dir のデフォルトは scripts/../templates
    assert ns.templates_dir.name == "templates"


def test_selected_patches_run_default_includes_goalseek_and_feedback():
    ns = RC.parse_args(["--kind", "run"])
    patches = RC.selected_patches(ns)
    assert patches[0] == "with-run.patch"
    assert "with-goal-seek.patch" in patches
    assert "with-feedback-contract.patch" in patches


def test_selected_patches_run_no_goal_seek_opt_out():
    ns = RC.parse_args(["--kind", "run", "--no-goal-seek"])
    patches = RC.selected_patches(ns)
    assert "with-goal-seek.patch" not in patches
    # feedback-contract は no-goal-seek でも残る
    assert "with-feedback-contract.patch" in patches


def test_selected_patches_ref_excludes_loop_combinators():
    ns = RC.parse_args(["--kind", "ref"])
    patches = RC.selected_patches(ns)
    assert patches == ["with-ref.patch"]


def test_selected_patches_assign_default_generator():
    ns = RC.parse_args(["--kind", "assign"])
    patches = RC.selected_patches(ns)
    # role_suffix 未指定 → generator
    assert patches == ["with-assign-generator.patch"]


def test_selected_patches_assign_evaluator_role():
    ns = RC.parse_args(["--kind", "assign", "--role-suffix", "evaluator"])
    patches = RC.selected_patches(ns)
    assert patches[0] == "with-assign-evaluator.patch"
    # assign は loop kind でないので goal-seek / feedback-contract なし
    assert "with-goal-seek.patch" not in patches
    assert "with-feedback-contract.patch" not in patches


def test_selected_patches_all_flags():
    ns = RC.parse_args([
        "--kind", "wrap",
        "--with-evaluator", "--with-hooks", "--with-subagent", "--with-knowledge",
    ])
    patches = RC.selected_patches(ns)
    for p in ("with-evaluator.patch", "with-hooks.patch",
              "with-subagent.patch", "with-knowledge.patch"):
        assert p in patches
    # wrap は loop kind
    assert "with-goal-seek.patch" in patches
    assert "with-feedback-contract.patch" in patches


def test_selected_patches_delegate_loop_kind():
    ns = RC.parse_args(["--kind", "delegate"])
    patches = RC.selected_patches(ns)
    assert patches[0] == "with-delegate.patch"
    assert "with-goal-seek.patch" in patches
    assert "with-feedback-contract.patch" in patches


# ===================== apply_unified_diff =====================

def test_apply_unified_diff_context_add_remove():
    content = "line1\nline2\nline3\n"
    diff = (
        "--- a/x\n"
        "+++ b/x\n"
        "@@ -1,3 +1,3 @@\n"
        " line1\n"
        "-line2\n"
        "+LINE2\n"
        " line3\n"
    )
    out = RC.apply_unified_diff(content, diff)
    assert out == "line1\nLINE2\nline3\n"


def test_apply_unified_diff_pure_addition():
    content = "a\nb\n"
    diff = (
        "@@ -1,1 +1,2 @@\n"
        " a\n"
        "+inserted\n"
    )
    out = RC.apply_unified_diff(content, diff)
    assert "inserted\n" in out
    # 残りの行 (b) は cursor から末尾へ温存される
    assert out.endswith("b\n")


def test_apply_unified_diff_invalid_hunk_header():
    with pytest.raises(RC.ComposeError, match="invalid hunk header"):
        RC.apply_unified_diff("a\n", "@@ bogus @@\n a\n")


def test_apply_unified_diff_overlapping_hunk():
    content = "a\nb\nc\nd\n"
    diff = (
        "@@ -3,1 +3,1 @@\n"
        " c\n"
        "@@ -1,1 +1,1 @@\n"   # 2 番目が前方 → overlapping
        " a\n"
    )
    with pytest.raises(RC.ComposeError, match="overlapping hunk"):
        RC.apply_unified_diff(content, diff)


def test_apply_unified_diff_context_mismatch():
    content = "a\nb\n"
    diff = (
        "@@ -1,1 +1,1 @@\n"
        " WRONG\n"   # content[0] は 'a' なので mismatch
    )
    with pytest.raises(RC.ComposeError, match="context mismatch"):
        RC.apply_unified_diff(content, diff)


def test_apply_unified_diff_removal_mismatch():
    content = "a\nb\n"
    diff = (
        "@@ -1,1 +1,1 @@\n"
        "-WRONG\n"   # 'a' を消そうとして 'WRONG' を期待 → mismatch
    )
    with pytest.raises(RC.ComposeError, match="removal mismatch"):
        RC.apply_unified_diff(content, diff)


def test_apply_unified_diff_unsupported_hunk_line():
    content = "a\n"
    diff = (
        "@@ -1,1 +1,1 @@\n"
        "?weird\n"   # 既知タグでない行 → unsupported
    )
    with pytest.raises(RC.ComposeError, match="unsupported hunk line"):
        RC.apply_unified_diff(content, diff)


def test_apply_unified_diff_no_newline_marker_ignored():
    content = "a\nb\n"
    diff = (
        "@@ -1,1 +1,1 @@\n"
        " a\n"
        "\\ No newline at end of file\n"
    )
    out = RC.apply_unified_diff(content, diff)
    assert out.startswith("a\n")


def test_apply_unified_diff_skips_file_headers_and_blank_before_hunk():
    content = "a\nb\n"
    diff = (
        "--- a/x\n"
        "+++ b/x\n"
        "\n"           # blank line before hunk → top-level skip
        "@@ -1,1 +1,1 @@\n"
        " a\n"
    )
    out = RC.apply_unified_diff(content, diff)
    assert out.startswith("a\n")


def test_apply_unified_diff_skips_file_headers_inside_hunk():
    # @@ の後に --- / +++ が混ざるケース (in-hunk file-header スキップ分岐)
    content = "a\nb\n"
    diff = (
        "@@ -1,2 +1,2 @@\n"
        " a\n"
        "--- a/x\n"     # in-hunk file header → skip
        "+++ b/x\n"     # in-hunk file header → skip
        " b\n"
    )
    out = RC.apply_unified_diff(content, diff)
    assert out == "a\nb\n"


def test_apply_unified_diff_context_eof_mismatch():
    # cursor が原文末尾を超える context → got=<eof>
    content = "a\n"
    diff = (
        "@@ -1,2 +1,2 @@\n"
        " a\n"
        " b\n"   # 原文に 2 行目が無い → <eof> mismatch
    )
    with pytest.raises(RC.ComposeError, match="context mismatch"):
        RC.apply_unified_diff(content, diff)


# ===================== frontmatter_bounds =====================

FM = "---\nname: x\nkind: run\n---\nbody\n"


def test_frontmatter_bounds_ok():
    assert RC.frontmatter_bounds(FM) == (0, 3)


def test_frontmatter_bounds_no_start():
    with pytest.raises(RC.ComposeError, match="must start with frontmatter"):
        RC.frontmatter_bounds("not frontmatter\n")


def test_frontmatter_bounds_not_closed():
    with pytest.raises(RC.ComposeError, match="not closed"):
        RC.frontmatter_bounds("---\nname: x\nbody without close\n")


# ===================== normalize_base =====================

def test_normalize_base_strips_design_note_fence():
    text = (
        "---\n"
        "# design note\n"
        "---\n"
        "---\n"
        "name: real\n"
        "---\n"
        "body\n"
    )
    out = RC.normalize_base(text)
    # 2 つ目の --- 直後に --- があるパターン → 後半 (real frontmatter) を残す
    assert out.startswith("---\nname: real")


def test_normalize_base_design_note_then_name_line():
    # 閉じ --- の次が name: で始まる (二重 --- でない) パターン
    text = (
        "---\n"
        "# note\n"
        "---\n"
        "name: real\n"
        "description: d\n"
        "---\n"
        "body\n"
    )
    out = RC.normalize_base(text)
    assert out.startswith("---\nname: real")


def test_normalize_base_no_fence_returns_unchanged():
    text = "---\nname: x\n---\nbody\n"
    assert RC.normalize_base(text) == text


def test_normalize_base_too_short_unchanged():
    text = "short"
    assert RC.normalize_base(text) == text


def test_normalize_base_no_leading_fence_unchanged():
    text = "no fence here\nmore\nlines\n"
    assert RC.normalize_base(text) == text


def test_normalize_base_open_fence_never_closed_unchanged():
    # 先頭 --- はあるが 2 つ目の --- が無い → for ループ尽きて末尾 return text
    text = "---\nname: x\ndescription: y\n"
    assert RC.normalize_base(text) == text


def test_normalize_base_real_base_md():
    # 実 _base.md は design-note fence を持つ → normalize で real frontmatter (name:) 始まりへ
    raw = (TEMPLATES_DIR / "_base.md").read_text(encoding="utf-8")
    out = RC.normalize_base(raw)
    assert out.startswith("---\nname: {{skill_name}}")


# ===================== ensure_frontmatter_line =====================

def test_ensure_frontmatter_line_appends_at_end():
    out = RC.ensure_frontmatter_line(FM, "newkey: v")
    lines = out.splitlines()
    # frontmatter 閉じ --- の直前に挿入される
    assert "newkey: v" in lines
    assert lines.index("newkey: v") < lines.index("---", 1)


def test_ensure_frontmatter_line_after_key():
    out = RC.ensure_frontmatter_line(FM, "effect: x", after_key="name")
    lines = out.splitlines()
    # name: の直後
    assert lines[lines.index("name: x") + 1] == "effect: x"


def test_ensure_frontmatter_line_idempotent_existing_key():
    # 同じ key が既にあれば挿入しない (冪等)
    out = RC.ensure_frontmatter_line(FM, "kind: somethingelse")
    assert out == FM


def test_ensure_frontmatter_line_after_key_not_found_falls_to_end():
    out = RC.ensure_frontmatter_line(FM, "z: 1", after_key="nonexistent")
    assert "z: 1" in out.splitlines()


# ===================== add_section_after =====================

def test_add_section_after_inserts():
    text = "## A\nbody\n## B\n"
    out = RC.add_section_after(text, "## A\nbody", "## NEW\ncontent")
    assert "## A\nbody\n\n## NEW\ncontent" in out


def test_add_section_after_idempotent_when_present():
    text = "## A\n\n## NEW\ncontent\n"
    # section の 1 行目 (## NEW) が既に存在 → no-op
    out = RC.add_section_after(text, "## A", "## NEW\ncontent")
    assert out == text


def test_add_section_after_anchor_missing_raises():
    with pytest.raises(RC.ComposeError, match="anchor not found"):
        RC.add_section_after("## A\n", "## MISSING", "## NEW\nx")


# ===================== apply_semantic_patch (実 _base 正規化済みに対して) =====================

@pytest.fixture
def base_text():
    raw = (TEMPLATES_DIR / "_base.md").read_text(encoding="utf-8")
    return RC.normalize_base(raw)


def test_semantic_with_run(base_text):
    out = RC.apply_semantic_patch(base_text, "with-run.patch")
    assert "effect:" in out
    assert "role_suffix:" in out


def test_semantic_with_ref(base_text):
    out = RC.apply_semantic_patch(base_text, "with-ref.patch")
    assert "disable-model-invocation: true" in out
    assert "effect: read-only" in out
    assert "## 参照内容" in out


def test_semantic_with_assign_generator(base_text):
    out = RC.apply_semantic_patch(base_text, "with-assign-generator.patch")
    assert "role_suffix: generator" in out
    assert "## 生成契約" in out


def test_semantic_with_assign_evaluator(base_text):
    out = RC.apply_semantic_patch(base_text, "with-assign-evaluator.patch")
    assert "context: fork" in out
    assert "role_suffix: evaluator" in out
    assert "## Evaluator Contract" in out


def test_semantic_with_wrap(base_text):
    out = RC.apply_semantic_patch(base_text, "with-wrap.patch")
    assert "role_suffix: cli-wrapper" in out
    assert "## Wrapped CLI" in out


def test_semantic_with_delegate(base_text):
    out = RC.apply_semantic_patch(base_text, "with-delegate.patch")
    assert "role_suffix: external-delegator" in out
    assert "## Delegation Target" in out


def test_semantic_with_evaluator(base_text):
    out = RC.apply_semantic_patch(base_text, "with-evaluator.patch")
    assert "pair: {{pair_skill}}" in out
    assert "## Evaluator 連携" in out


def test_semantic_with_hooks(base_text):
    out = RC.apply_semantic_patch(base_text, "with-hooks.patch")
    assert "with_hooks: true" in out
    assert "## Hook Wiring" in out


def test_semantic_with_subagent(base_text):
    out = RC.apply_semantic_patch(base_text, "with-subagent.patch")
    assert "context: fork" in out
    assert "agent: {{subagent_type}}" in out
    assert "## Subagent / Agent Team 連携" in out


def test_semantic_with_knowledge(base_text):
    out = RC.apply_semantic_patch(base_text, "with-knowledge.patch")
    assert "knowledge_loop:" in out
    assert "## ナレッジループ" in out


def test_semantic_with_goal_seek(base_text):
    out = RC.apply_semantic_patch(base_text, "with-goal-seek.patch")
    assert "goal_seek:" in out
    assert "### ゴールシーク配線（実行可能機構）" in out


def test_semantic_with_feedback_contract(base_text):
    out = RC.apply_semantic_patch(base_text, "with-feedback-contract.patch")
    assert "feedback_contract:" in out
    assert "## 評価・改善ループ契約" in out


def test_semantic_unknown_patch_raises(base_text):
    with pytest.raises(RC.ComposeError, match="unknown combinator"):
        RC.apply_semantic_patch(base_text, "with-bogus.patch")


# ===================== apply_patch_file (fallback) =====================

def test_apply_patch_file_falls_back_to_semantic(base_text, tmp_path):
    # 実 patch ファイルは _base.md と行番号がずれるため unified-diff は context mismatch →
    # apply_semantic_patch にフォールバックして適用される。
    patch = TEMPLATES_DIR / "combinators" / "with-run.patch"
    out = RC.apply_patch_file(base_text, patch)
    assert "effect:" in out


# ===================== apply_feedback_loop (copy, tmp 限定) =====================

def test_apply_feedback_loop_copies_feedback_skill(tmp_path):
    plugin = tmp_path / "plugins" / "demo-plugin"
    plugin.mkdir(parents=True)
    deployed = RC.apply_feedback_loop(plugin)
    assert deployed.is_dir()
    assert not deployed.is_symlink()
    assert (deployed / "SKILL.md").is_file()


def test_apply_feedback_loop_idempotent(tmp_path):
    plugin = tmp_path / "plugins" / "demo-plugin"
    plugin.mkdir(parents=True)
    first = RC.apply_feedback_loop(plugin)
    second = RC.apply_feedback_loop(plugin)   # 2 回目は no-op で同 path 返却
    assert first == second
    assert second.is_dir()
    assert not second.is_symlink()


def test_apply_feedback_loop_skips_harness_creator(tmp_path):
    plugin = tmp_path / "harness-creator"
    plugin.mkdir(parents=True)
    link = RC.apply_feedback_loop(plugin)
    # SSOT 本体には配備せず、想定 path を返すだけ (symlink は作らない)
    assert link == plugin / "skills" / "run-skill-feedback"
    assert not link.exists()


# ===================== main() =====================

def test_main_run_to_stdout(monkeypatch, capsys):
    rc = RC.main(["--kind", "run"])
    assert rc == 0
    out = capsys.readouterr().out
    assert "name: {{skill_name}}" in out
    assert "effect:" in out
    assert "feedback_contract:" in out


def test_main_ref_to_stdout(capsys):
    rc = RC.main(["--kind", "ref"])
    assert rc == 0
    out = capsys.readouterr().out
    assert "effect: read-only" in out
    assert "## 参照内容" in out


def test_main_output_file(tmp_path):
    out_path = tmp_path / "nested" / "SKILL.md"
    rc = RC.main(["--kind", "run", "--output", str(out_path)])
    assert rc == 0
    assert out_path.exists()
    text = out_path.read_text(encoding="utf-8")
    assert "feedback_contract:" in text


def test_main_trace_lists_patches(capsys):
    rc = RC.main(["--kind", "run", "--trace"])
    assert rc == 0
    err = capsys.readouterr().err
    assert "applied:" in err
    assert "with-run.patch" in err


def test_main_missing_combinator_dir_errors(tmp_path, capsys):
    # templates-dir を空 tmp に向ける → _base.md 読込失敗 (OSError) で error path
    rc = RC.main(["--kind", "run", "--templates-dir", str(tmp_path)])
    assert rc == 1
    assert "error:" in capsys.readouterr().err


def test_main_missing_specific_combinator(tmp_path, capsys):
    # _base.md だけ用意し combinator を欠落 → missing combinator
    (tmp_path / "_base.md").write_text(
        "---\nname: {{skill_name}}\nkind: run\n---\nbody\n", encoding="utf-8")
    rc = RC.main(["--kind", "run", "--templates-dir", str(tmp_path)])
    assert rc == 1
    assert "missing combinator" in capsys.readouterr().err


def test_main_deploy_feedback_loop_side_effect(tmp_path, capsys):
    # --deploy-feedback-loop で実体コピー配備 (副作用) + 通常合成も行う
    plugin = tmp_path / "plugins" / "demo-plugin"
    plugin.mkdir(parents=True)
    rc = RC.main(["--kind", "run", "--deploy-feedback-loop", str(plugin), "--trace"])
    assert rc == 0
    link = plugin / "skills" / "run-skill-feedback"
    assert link.is_dir()
    assert not link.is_symlink()
    err = capsys.readouterr().err
    assert "deployed feedback-loop:" in err


def test_main_deploy_feedback_loop_opt_out(tmp_path):
    plugin = tmp_path / "plugins" / "demo-plugin"
    plugin.mkdir(parents=True)
    rc = RC.main(["--kind", "run", "--deploy-feedback-loop", str(plugin),
                  "--no-feedback-loop"])
    assert rc == 0
    # opt-out で symlink は作られない
    assert not (plugin / "skills" / "run-skill-feedback").exists()


def test_main_deploy_feedback_loop_oserror(tmp_path, capsys, monkeypatch):
    plugin = tmp_path / "plugins" / "demo-plugin"
    plugin.mkdir(parents=True)
    # apply_feedback_loop を OSError で失敗させ exit 1 を確認
    monkeypatch.setattr(
        RC, "apply_feedback_loop",
        lambda d: (_ for _ in ()).throw(OSError("permission denied")))
    rc = RC.main(["--kind", "run", "--deploy-feedback-loop", str(plugin)])
    assert rc == 1
    assert "error:" in capsys.readouterr().err


def test_main_entrypoint_subprocess():
    # __main__ (SystemExit(main(...))) を subprocess で実起動
    import subprocess
    proc = subprocess.run(
        [sys.executable, str(SCRIPT), "--kind", "delegate"],
        capture_output=True, text=True,
    )
    assert proc.returncode == 0
    assert "## Delegation Target" in proc.stdout
    assert "feedback_contract:" in proc.stdout
