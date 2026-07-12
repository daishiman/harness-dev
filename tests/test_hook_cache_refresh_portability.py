"""hook-cache-refresh.py の plugins-root 解決が cwd 非依存であることを実証する。

UserPromptExpansion hook は毎プロンプト発火。ユーザが repo 外で Claude を起動しても
裸の相対パス `plugins` ではなく self-relative の絶対パスを notifier-check へ渡し、
notifier cache 更新が silent skip しないことを保証する。
"""
import importlib.util
import os
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
SCRIPT = (
    ROOT
    / "plugins"
    / "harness-creator"
    / "skills"
    / "run-skill-update-notifier"
    / "scripts"
    / "hook-cache-refresh.py"
)


def _load():
    spec = importlib.util.spec_from_file_location("hook_cache_refresh", SCRIPT)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


MOD = _load()


def test_plugins_root_is_absolute(monkeypatch):
    monkeypatch.delenv("CLAUDE_PLUGIN_ROOT", raising=False)
    root = MOD._plugins_root()
    assert root.is_absolute()


def test_plugins_root_points_to_plugins_dir(monkeypatch):
    """self-relative 解決は「複数 plugin を含む plugins/ ディレクトリ」を指す。"""
    monkeypatch.delenv("CLAUDE_PLUGIN_ROOT", raising=False)
    root = MOD._plugins_root()
    assert root.name == "plugins"
    # 実際に harness-creator サブディレクトリを含む = notifier-check の走査対象として妥当
    assert (root / "harness-creator").is_dir()


def test_plugins_root_is_cwd_independent(monkeypatch, tmp_path):
    """cwd を repo 外に変えても同一の plugins/ を指す (silent skip 回避の核心)。"""
    monkeypatch.delenv("CLAUDE_PLUGIN_ROOT", raising=False)
    monkeypatch.chdir(tmp_path)  # repo 外 cwd を模す
    root = MOD._plugins_root()
    assert root.name == "plugins"
    assert (root / "harness-creator").is_dir()
    # 裸の相対 "plugins" だったら tmp_path/plugins になり不在になる、を反証
    assert root != Path("plugins").resolve()


def test_env_plugin_root_takes_precedence(monkeypatch, tmp_path):
    """CLAUDE_PLUGIN_ROOT (単一 plugin ルート) があればその親 = plugins/ を返す。"""
    plugin = tmp_path / "myplugins" / "harness-creator"
    plugin.mkdir(parents=True)
    monkeypatch.setenv("CLAUDE_PLUGIN_ROOT", str(plugin))
    root = MOD._plugins_root()
    assert root == (tmp_path / "myplugins").resolve()


def test_main_passes_absolute_plugins_root(monkeypatch, tmp_path):
    """refresh 呼び出しに渡す --plugins-root が絶対パスであることを捕捉。"""
    monkeypatch.delenv("CLAUDE_PLUGIN_ROOT", raising=False)
    monkeypatch.chdir(tmp_path)
    captured = {}

    class _Result:
        stdout = "stale"

    def fake_run(cmd, **kwargs):
        # 1 回目 = cache-status, 2 回目 = refresh
        if "refresh" in cmd:
            idx = cmd.index("--plugins-root") + 1
            captured["plugins_root"] = cmd[idx]
        return _Result()

    monkeypatch.setattr(MOD.subprocess, "run", fake_run)
    rc = MOD.main()
    assert rc == 0
    pr = captured.get("plugins_root")
    assert pr is not None
    assert os.path.isabs(pr), f"--plugins-root must be absolute, got {pr!r}"
    assert Path(pr).name == "plugins"


def test_main_passes_current_plugin_root(monkeypatch, tmp_path):
    plugin = tmp_path / "marketplace-cache" / "harness-creator"
    plugin.mkdir(parents=True)
    monkeypatch.setenv("CLAUDE_PLUGIN_ROOT", str(plugin))
    captured = {}

    class _Result:
        stdout = "stale"

    def fake_run(cmd, **kwargs):
        if "refresh" in cmd:
            captured["plugin_root"] = cmd[cmd.index("--plugin-root") + 1]
        return _Result()

    monkeypatch.setattr(MOD.subprocess, "run", fake_run)
    assert MOD.main() == 0
    assert captured["plugin_root"] == str(plugin.resolve())
