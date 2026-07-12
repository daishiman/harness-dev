"""route C04 lint-goal-seek.py の engine:task-graph 変種 self-test 拡張の genuine テスト。

check_task_graph_variant() の (a)engine enum (b)depends_on schema (c)consumption verifier トークン
検査と、per-file の concrete engine:task-graph 検出を検証する。既存 check_default_drift() を
壊さない回帰も確認する。

カバー:
- check_task_graph_variant: 実 SSOT で [] (全整合) / enum 欠落・depends_on 欠落・token 欠落で finding
- check_default_drift: task-graph 検査を含めて [] (実 SSOT 整合)
- lint_file per-file: concrete engine:task-graph 宣言 skill で token 欠落なら finding /
  散文言及や inline engine は非対象 / トークンが配線セクション外のみなら finding (scope 限定・全文 substring 廃止)
- main(--self-test): exit0

network: false, 実 repo 書換: なし (tmp のみ・SSOT パスを monkeypatch)。
"""
import importlib.util
import json
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
RB = ROOT / "plugins/harness-creator/skills/run-build-skill"
SCRIPT = RB / "scripts/lint-goal-seek.py"


def _load():
    spec = importlib.util.spec_from_file_location("lint_goal_seek", SCRIPT)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


mod = _load()


# --- check_task_graph_variant (実 SSOT で整合) ---
def test_task_graph_variant_clean():
    assert mod.check_task_graph_variant() == []


def test_default_drift_includes_task_graph_and_passes():
    # check_default_drift が check_task_graph_variant を包含し、実 SSOT で緑であること。
    assert mod.check_default_drift() == []


# --- 欠落検出 (SSOT パスを temp へ差し替え) ---
def _temp_sources(tmp_path, *, engine_enum, has_depends, render_tokens):
    bf = tmp_path / "build-flags.json"
    bf.write_text(json.dumps({"properties": {"with_goal_seek": {"properties": {
        "engine": {"enum": engine_enum, "default": "inline"}}}}}))
    ls_props = {"id": {}, "text": {}, "status": {}}
    if has_depends:
        ls_props["depends_on"] = {"type": "array", "default": []}
    ls = tmp_path / "loop.json"
    ls.write_text(json.dumps({"properties": {"checklist": {"items": {"properties": ls_props}}}}))
    render = tmp_path / "render.py"
    render.write_text(render_tokens)
    return bf, ls, render


def test_variant_detects_missing_enum(tmp_path, monkeypatch):
    bf, ls, render = _temp_sources(
        tmp_path, engine_enum=["inline"], has_depends=True,
        render_tokens="task-graph " + " ".join(mod._TASK_GRAPH_WIRING_TOKENS + mod._TASK_GRAPH_KNOWLEDGE_TOKENS),
    )
    monkeypatch.setattr(mod, "_BUILD_FLAGS", bf)
    monkeypatch.setattr(mod, "_LOOP_SCHEMA", ls)
    monkeypatch.setattr(mod, "_RENDER", render)
    findings = mod.check_task_graph_variant()
    assert any("engine enum" in f for f in findings)


def test_variant_detects_missing_depends_on(tmp_path, monkeypatch):
    bf, ls, render = _temp_sources(
        tmp_path, engine_enum=["inline", "task-graph"], has_depends=False,
        render_tokens="task-graph " + " ".join(mod._TASK_GRAPH_WIRING_TOKENS + mod._TASK_GRAPH_KNOWLEDGE_TOKENS),
    )
    monkeypatch.setattr(mod, "_BUILD_FLAGS", bf)
    monkeypatch.setattr(mod, "_LOOP_SCHEMA", ls)
    monkeypatch.setattr(mod, "_RENDER", render)
    findings = mod.check_task_graph_variant()
    assert any("depends_on" in f for f in findings)


def test_variant_detects_missing_token(tmp_path, monkeypatch):
    bf, ls, render = _temp_sources(
        tmp_path, engine_enum=["inline", "task-graph"], has_depends=True,
        render_tokens="task-graph (consumption verifier token 欠落)",
    )
    monkeypatch.setattr(mod, "_BUILD_FLAGS", bf)
    monkeypatch.setattr(mod, "_LOOP_SCHEMA", ls)
    monkeypatch.setattr(mod, "_RENDER", render)
    findings = mod.check_task_graph_variant()
    assert any("consumption verifier" in f or "consult" in f for f in findings)


# --- per-file concrete engine 検出 ---
def _skill(engine_line, body_tokens):
    return (f"---\nname: run-tg\nkind: run\n{engine_line}\n---\n"
            "## ゴールシーク実行\n### 完了チェックリスト\n- [ ] やる\n"
            "### ゴールシーク配線\n" + body_tokens + "\n")


def test_per_file_concrete_task_graph_missing_tokens(tmp_path):
    p = tmp_path / "SKILL.md"
    p.write_text(_skill("  engine: task-graph", "intermediate.jsonl original_goal merged_directive_for_next required_keys original_goal_hash hashlib.sha256"))
    findings, warnings = mod.lint_file(p)
    assert any("task-graph" in f for f in findings)


def test_per_file_prose_mention_not_triggered(tmp_path):
    p = tmp_path / "SKILL.md"
    body = "intermediate.jsonl original_goal merged_directive_for_next required_keys original_goal_hash hashlib.sha256 engine:task-graph 変種の説明"
    p.write_text(_skill("kind: run", body))
    findings, _ = mod.lint_file(p)
    assert not any("task-graph" in f for f in findings)  # 散文言及は誤発火しない


def test_per_file_tokens_outside_wiring_scope_detected(tmp_path):
    # トークンが配線セクション外の散文にのみ出現する場合、scope 限定検査が finding を出す
    # (LS-01b と同型: 本文引用による全文 substring の偽陰性経路を封鎖)。
    p = tmp_path / "SKILL.md"
    all_tokens = " ".join(mod._TASK_GRAPH_WIRING_TOKENS + mod._TASK_GRAPH_KNOWLEDGE_TOKENS)
    p.write_text(
        "---\nname: run-tg\nkind: run\n  engine: task-graph\n---\n"
        "## 説明\n" + all_tokens + "\n"
        "## ゴールシーク実行\n### 完了チェックリスト\n- [ ] やる\n"
        "### ゴールシーク配線\nintermediate.jsonl original_goal merged_directive_for_next "
        "required_keys original_goal_hash hashlib.sha256\n"
    )
    findings, _ = mod.lint_file(p)
    assert any("task-graph" in f for f in findings)


def test_per_file_full_task_graph_ok(tmp_path):
    p = tmp_path / "SKILL.md"
    all_tokens = ("intermediate.jsonl original_goal merged_directive_for_next required_keys "
                  "original_goal_hash hashlib.sha256 "
                  + " ".join(mod._TASK_GRAPH_WIRING_TOKENS + mod._TASK_GRAPH_KNOWLEDGE_TOKENS))
    p.write_text(_skill("  engine: task-graph", all_tokens))
    findings, _ = mod.lint_file(p)
    assert not any("task-graph" in f for f in findings)


# --- main self-test ---
def test_main_self_test_exit0():
    r = subprocess.run([sys.executable, str(SCRIPT), "--self-test"], capture_output=True, text=True)
    assert r.returncode == 0
