"""lint-legacy-plugin-name.py の外部キット除外の回帰テスト。

外部キット aidd-agent-kit の skill-creator は Claude/Codex 組込の同名別物を指し、
manifest の SHA と一致させるため書き換えられない。除外が広すぎて harness 自身の
投影まで素通りさせないことを含め、所有境界の各分岐を機械保証する。

検証する不変条件:
  K1 キット原本 aidd-agent-kit/ は凍結層
  K2 .claude manifest の行は .claude/ 配下へ、.codex manifest の skills/ は .agents/ 配下・
     それ以外は .codex/ 配下へ解決される
  K3 経路上に symlink を含む (harness 投影の) パスは manifest に載っていても除外しない
  K4 manifest 不在・不正行 (絶対パス / ..) は除外集合を作らない
  実 repo が PASS する (統合)

import 経路: dash 入り script のため importlib.util.spec_from_file_location。
"""
from __future__ import annotations

import importlib.util
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
SCRIPT = ROOT / "scripts" / "lint-legacy-plugin-name.py"
SPEC = importlib.util.spec_from_file_location("lint_legacy_plugin_name", SCRIPT)
MOD = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(MOD)


def _manifest(path: Path, *relatives: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("".join(f"{'0' * 64}|{rel}\n" for rel in relatives), encoding="utf-8")


def test_kit_source_is_frozen():
    assert MOD.is_frozen("aidd-agent-kit/agents/app-orchestrator.md")
    assert not MOD.is_frozen("plugins/harness-creator/README-extra.md")


def test_manifest_paths_resolve_to_each_platform_root(tmp_path):
    _manifest(tmp_path / ".claude/aidd-agent-kit.manifest", "agents/app-orchestrator.md")
    _manifest(
        tmp_path / ".codex/aidd-agent-kit.manifest",
        "skills/app-orchestrator/SKILL.md",
        "agents/app-orchestrator.toml",
    )
    assert MOD.load_external_owned(tmp_path) == {
        ".claude/agents/app-orchestrator.md",
        ".agents/skills/app-orchestrator/SKILL.md",
        ".codex/agents/app-orchestrator.toml",
    }


def test_symlinked_harness_projection_is_not_excluded(tmp_path):
    target = tmp_path / "plugins/harness-creator/skills/run-x"
    target.mkdir(parents=True)
    (tmp_path / ".claude/skills").mkdir(parents=True)
    (tmp_path / ".claude/skills/run-x").symlink_to(target)
    _manifest(tmp_path / ".claude/aidd-agent-kit.manifest", "skills/run-x/SKILL.md", "skills/kit/SKILL.md")
    assert MOD.load_external_owned(tmp_path) == {".claude/skills/kit/SKILL.md"}


def test_missing_manifest_and_invalid_lines_own_nothing(tmp_path):
    assert MOD.load_external_owned(tmp_path) == set()
    _manifest(tmp_path / ".claude/aidd-agent-kit.manifest", "/etc/passwd", "../outside.md", "")
    assert MOD.load_external_owned(tmp_path) == set()


def test_real_repository_passes():
    assert MOD.main() == 0
