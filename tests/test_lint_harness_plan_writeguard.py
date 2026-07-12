"""lint-harness-plan-writeguard.py (S1) の検出ロジック回帰テスト。

片方向 writer 不変条件 (harness の task-graph consumer は producer 所有 plan を書かない) を
AST で機械強制する lint が、正当な非 plan 書込を通し・plan 直書きを捕捉する境界を腐らせない。

検証する不変条件:
  ① 実 repo の task-graph consumer 7 本 (現物) が clean (現行 code が違反しない=CI の番人)
  ② plan 成果物 (task-graph.json / plugin-plans / component-inventory / phase-NN / handoff) への
     write_text / open('w') / os.replace 直書きを violation として検出
  ③ 変数経由 (task_graph_path = plan_dir / "task-graph.json"; open(task_graph_path,"w")) も検出
  ④ read (open without write-mode) の task-graph.json は非検出 (誤検出しない)
  ⑤ writeguard: allow マーカー付き行は許可 (tempfile 等の正当例外)
  ⑥ 対象選定: resolve_build_dir 参照の新規 script を自動被覆

import 経路: dash 入り script のため importlib.util.spec_from_file_location。
"""
import importlib.util
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def _load():
    path = ROOT / "scripts" / "lint-harness-plan-writeguard.py"
    spec = importlib.util.spec_from_file_location("lint_harness_plan_writeguard", path)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


wg = _load()


# ① 実 repo の現物が clean
def test_real_repo_scripts_are_clean():
    assert wg.main([]) == 0


# ② plan 直書きを検出
def test_write_text_to_task_graph_is_violation():
    src = (
        "from pathlib import Path\n"
        "def resolve_build_dir(a, b): return '.'\n"
        "def f(plan_dir):\n"
        "    (Path(plan_dir) / 'task-graph.json').write_text('x')\n"
    )
    v = wg.check_source(src, "fake.py")
    assert len(v) == 1 and "task-graph.json" in v[0]


def test_open_write_plugin_plans_is_violation():
    src = (
        "def resolve_build_dir(a, b): return '.'\n"
        "def f():\n"
        "    with open('plugin-plans/x/phase-05-implementation.md', 'w') as fh:\n"
        "        fh.write('x')\n"
    )
    v = wg.check_source(src, "fake.py")
    assert len(v) == 1 and "plugin-plans" in v[0]


def test_os_replace_component_inventory_is_violation():
    src = (
        "import os\n"
        "def resolve_build_dir(a, b): return '.'\n"
        "def f(tmp):\n"
        "    os.replace(tmp, 'plugin-plans/x/component-inventory.json')\n"
    )
    v = wg.check_source(src, "fake.py")
    assert len(v) == 1 and "component-inventory.json" in v[0]


# ③ 変数経由 (1-hop 追跡)
def test_variable_carried_forbidden_token_is_violation():
    src = (
        "def resolve_build_dir(a, b): return '.'\n"
        "def f(plan_dir):\n"
        "    task_graph_path = plan_dir + '/task-graph.json'\n"
        "    open(task_graph_path, 'w').write('x')\n"
    )
    v = wg.check_source(src, "fake.py")
    assert len(v) == 1


# ④ read は非検出
def test_read_task_graph_is_not_violation():
    src = (
        "def resolve_build_dir(a, b): return '.'\n"
        "def f():\n"
        "    data = open('plugin-plans/x/task-graph.json').read()\n"
        "    return data\n"
    )
    assert wg.check_source(src, "fake.py") == []


def test_argparse_help_mentioning_task_graph_is_not_violation():
    # docstring / help 文字列の言及は write sink ではない → 非検出
    src = (
        "def resolve_build_dir(a, b): return '.'\n"
        "def f(p):\n"
        "    p.add_argument('--task-graph', help='task-graph.json のパス')\n"
    )
    assert wg.check_source(src, "fake.py") == []


# ⑤ writeguard: allow マーカーで許可
def test_allow_marker_suppresses_violation():
    src = (
        "from pathlib import Path\n"
        "def resolve_build_dir(a, b): return '.'\n"
        "def f(tmp):\n"
        "    (Path(tmp) / 'task-graph.json').write_text('x')  # writeguard: allow: tempfile\n"
    )
    assert wg.check_source(src, "fake.py") == []


# ⑥ 対象選定: resolve_build_dir 参照で自動被覆 / 非 consumer は対象外
def test_select_targets_includes_resolve_build_dir_and_known(tmp_path):
    (tmp_path / "new-consumer.py").write_text(
        "from x import resolve_build_dir\n", encoding="utf-8")
    (tmp_path / "unrelated.py").write_text("print('hi')\n", encoding="utf-8")
    (tmp_path / "sync-task-state.py").write_text("x = 1\n", encoding="utf-8")  # 既知名
    names = {p.name for p in wg.select_targets(tmp_path)}
    assert "new-consumer.py" in names  # resolve_build_dir 参照 → 自動被覆
    assert "sync-task-state.py" in names  # 既知 consumer
    assert "unrelated.py" not in names  # 非 consumer は対象外
