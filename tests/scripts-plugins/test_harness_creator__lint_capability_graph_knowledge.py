"""ENG-C08 lint-capability-graph-knowledge.py の genuine 機能テスト (H6 実装)。

生成 task-graph harness の ENG-C06/ENG-C07 同梱・各 surface consult token・knowledge source_ref を fail-closed 検査。

カバー分岐:
- _CONCRETE_TASK_GRAPH_ENGINE_RE: YAML 宣言のみ一致・散文/placeholder 非一致
- collect_task_graph_skills: engine:task-graph 宣言 skill のみ / 単一ファイル入力
- check_bundling: 同梱 4 script 実在+テンプレ原本 byte 一致 OK / 欠落 violation / 手改変 byte-parity violation
- check_consult_tokens: token あり OK / 欠落 violation
- check_source_refs: 全 source_ref OK / 欠落 violation / store 不在 warning
- self_test: BUNDLED_SCRIPTS↔SKILL.md Step10.6 parity + peer regex 定義一致 (drift ガード)
- lint / main(CLI): not-applicable exit0 / 完全準拠 exit0 / 各 violation exit1 / 非存在 exit2

network: false, 実 repo 書換: なし (tmp_path のみ)。
"""
import importlib.util
import json
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
RB = ROOT / "plugins/harness-creator/skills/run-build-skill"
SCRIPT = RB / "scripts/lint-capability-graph-knowledge.py"
TG = RB / "templates/task-graph-engine/scripts"


def _load():
    spec = importlib.util.spec_from_file_location("lint_capability_graph_knowledge", SCRIPT)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


mod = _load()


def _tg_harness(tmp_path, *, bundle=True, consult=True, store=True, bad_ref=False):
    root = tmp_path / "h"
    sk = root / "skills/run-tg"
    (sk / "scripts").mkdir(parents=True)
    body = "本文。" + ("dependency graph knowledge を consult する。" if consult else "consult なし")
    # check_engine_profile の hard gate 準拠: engine_profile / full_task_spec_graph を宣言する
    # (未実装機構を成功扱いしない fail-closed 境界。checklist-graph は planner full graph と非同等)。
    (sk / "SKILL.md").write_text(
        "---\nname: run-tg\n  engine: task-graph\n"
        "  engine_profile: checklist-graph\n  full_task_spec_graph: false\n"
        f"---\n{body}\n"
    )
    if bundle:
        # 同梱契約は「テンプレ原本の無改変コピー」— byte-parity 検査対象のため実バイトを複製する。
        for s in ("ready-set-from-checklist.py", "self-reflect-append.py",
                  "extract-capability-dependency-graph.py", "record-capability-graph-knowledge.py"):
            (sk / "scripts" / s).write_bytes((TG / s).read_bytes())
    if store:
        kdir = sk / "knowledge"
        kdir.mkdir()
        item = {"id": "cdg-summary", "title": "t"}
        if not bad_ref:
            item["source_ref"] = "graph.json"
        (kdir / "knowledge-capability-graph.json").write_text(json.dumps({"items": [item]}))
    return root


def _tg_harness_with_surfaces(tmp_path, *, command_consult=False, agent_consult=False):
    root = _tg_harness(tmp_path)
    (root / "commands").mkdir()
    (root / "agents").mkdir()
    command_body = "run command"
    agent_body = "agent body"
    if command_consult:
        command_body += "\ndependency graph knowledge を consult する。"
    if agent_consult:
        agent_body += "\ndependency graph knowledge を consult する。"
    (root / "commands/run-tg.md").write_text(command_body)
    (root / "agents/reviewer-tg.md").write_text(agent_body)
    return root


def _run(target):
    return subprocess.run([sys.executable, str(SCRIPT), str(target)], capture_output=True, text=True)


# --- regex ---
def test_concrete_engine_regex():
    r = mod._CONCRETE_TASK_GRAPH_ENGINE_RE
    assert r.search("  engine: task-graph      # comment")
    assert r.search("  engine: task-graph")
    assert not r.search("engine:task-graph 変種の説明")
    assert not r.search('  engine: {{goal_seek.engine | default("inline")}}')


# --- collect_task_graph_skills ---
def test_collect_only_task_graph(tmp_path):
    root = _tg_harness(tmp_path)
    (root / "skills/run-inline").mkdir(parents=True)
    (root / "skills/run-inline/SKILL.md").write_text("---\nname: run-inline\n  engine: inline\n---\nx\n")
    skills = mod.collect_task_graph_skills(root, None)
    assert len(skills) == 1 and skills[0].parent.name == "run-tg"


# --- check_bundling ---
def test_bundling_ok(tmp_path):
    root = _tg_harness(tmp_path, bundle=True)
    skills = mod.collect_task_graph_skills(root, None)
    assert mod.check_bundling(skills) == []


def test_bundling_missing(tmp_path):
    root = _tg_harness(tmp_path, bundle=False)
    skills = mod.collect_task_graph_skills(root, None)
    findings = mod.check_bundling(skills)
    assert len(findings) == 4  # C01/C02/C06/C07 全4本欠落 (gate-coverage parity)


def test_bundling_byte_parity_violation(tmp_path):
    root = _tg_harness(tmp_path, bundle=True)
    tampered = root / "skills/run-tg/scripts/self-reflect-append.py"
    tampered.write_text(tampered.read_text() + "\n# 手改変\n")
    skills = mod.collect_task_graph_skills(root, None)
    findings = mod.check_bundling(skills)
    assert any("byte-parity 違反" in f and "self-reflect-append.py" in f for f in findings)


def test_self_test_ok():
    r = subprocess.run([sys.executable, str(SCRIPT), "--self-test"], capture_output=True, text=True)
    assert r.returncode == 0 and "self-test 通過" in r.stdout


# --- check_consult_tokens ---
def test_consult_ok(tmp_path):
    root = _tg_harness(tmp_path, consult=True)
    skills = mod.collect_task_graph_skills(root, None)
    assert mod.check_consult_tokens(skills) == []


def test_consult_missing(tmp_path):
    root = _tg_harness(tmp_path, consult=False)
    skills = mod.collect_task_graph_skills(root, None)
    assert mod.check_consult_tokens(skills)


def test_advisory_surface_consults_warn_for_command_agent(tmp_path):
    root = _tg_harness_with_surfaces(tmp_path)
    warnings = mod.check_advisory_surface_consults(root)
    assert len(warnings) == 2
    assert all("advisory consult 未配線" in w for w in warnings)


def test_advisory_surface_consults_ok_when_token_present(tmp_path):
    root = _tg_harness_with_surfaces(tmp_path, command_consult=True, agent_consult=True)
    assert mod.check_advisory_surface_consults(root) == []


# --- check_source_refs ---
def test_source_refs_ok(tmp_path):
    root = _tg_harness(tmp_path, store=True, bad_ref=False)
    findings, warnings = mod.check_source_refs(root)
    assert findings == []


def test_source_refs_missing(tmp_path):
    root = _tg_harness(tmp_path, store=True, bad_ref=True)
    findings, _ = mod.check_source_refs(root)
    assert any("source_ref" in f for f in findings)


def test_source_refs_no_store_warns(tmp_path):
    root = _tg_harness(tmp_path, store=False)
    findings, warnings = mod.check_source_refs(root)
    assert findings == [] and warnings


# --- main CLI ---
def test_main_not_applicable(tmp_path):
    root = tmp_path / "h"
    (root / "skills/run-x").mkdir(parents=True)
    (root / "skills/run-x/SKILL.md").write_text("---\nname: run-x\n  engine: inline\n---\nx\n")
    r = _run(root)
    assert r.returncode == 0 and "not-applicable" in r.stdout


def test_main_full_compliant(tmp_path):
    root = _tg_harness(tmp_path)
    r = _run(root)
    assert r.returncode == 0 and "OK" in r.stdout


def test_main_command_agent_consult_warnings_do_not_fail(tmp_path):
    root = _tg_harness_with_surfaces(tmp_path)
    r = _run(root)
    assert r.returncode == 0 and "OK" in r.stdout
    assert "advisory consult 未配線" in r.stderr


def test_main_bundling_violation_exit1(tmp_path):
    root = _tg_harness(tmp_path, bundle=False)
    r = _run(root)
    assert r.returncode == 1 and "同梱欠落" in r.stderr


def test_main_single_file_input(tmp_path):
    root = _tg_harness(tmp_path)
    r = _run(root / "skills/run-tg/SKILL.md")
    assert r.returncode == 0


def test_main_missing_target_exit2(tmp_path):
    r = _run(tmp_path / "nope")
    assert r.returncode == 2
