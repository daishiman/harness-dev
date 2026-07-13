from __future__ import annotations

import json
import os
import shutil
import subprocess
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


def test_install_bundle_applies_then_checks_native_settings(tmp_path: Path) -> None:
    repo = tmp_path / "repo"
    (repo / "scripts").mkdir(parents=True)
    (repo / ".claude-plugin").mkdir()
    sync_dir = repo / "plugins/harness-creator/scripts"
    sync_dir.mkdir(parents=True)
    shutil.copy2(ROOT / "scripts/install-bundle.sh", repo / "scripts/install-bundle.sh")
    (repo / ".claude-plugin/bundles.json").write_text(
        json.dumps({"bundles": [{"name": "demo", "description": "demo", "plugins": ["one", "two"]}]}),
        encoding="utf-8",
    )
    (repo / ".claude-plugin/marketplace.json").write_text(
        json.dumps({"name": "skills", "plugins": []}), encoding="utf-8"
    )
    log = repo / "calls.log"
    (sync_dir / "sync-native-surfaces.py").write_text(
        """#!/usr/bin/env python3
import os, sys
with open(os.environ['CALLS_LOG'], 'a', encoding='utf-8') as fh:
    fh.write('sync ' + ' '.join(sys.argv[1:]) + '\\n')
""",
        encoding="utf-8",
    )
    bin_dir = tmp_path / "bin"
    bin_dir.mkdir()
    claude = bin_dir / "claude"
    claude.write_text(
        "#!/bin/sh\nprintf 'claude %s\\n' \"$*\" >> \"$CALLS_LOG\"\n",
        encoding="utf-8",
    )
    claude.chmod(0o755)
    env = dict(os.environ, PATH=f"{bin_dir}:{os.environ['PATH']}", CALLS_LOG=str(log))

    result = subprocess.run(
        ["bash", str(repo / "scripts/install-bundle.sh"), "demo"],
        cwd=repo,
        env=env,
        text=True,
        capture_output=True,
        check=False,
    )

    assert result.returncode == 0, result.stderr
    calls = log.read_text(encoding="utf-8").splitlines()
    assert calls[:2] == [
        "claude plugin install one@skills",
        "claude plugin install two@skills",
    ]
    assert calls[2:] == [
        f"sync --repo-root {repo} --apply",
        f"sync --repo-root {repo} --check",
    ]


def test_install_bundle_does_not_apply_settings_after_partial_install(tmp_path: Path) -> None:
    repo = tmp_path / "repo"
    (repo / "scripts").mkdir(parents=True)
    (repo / ".claude-plugin").mkdir()
    sync_dir = repo / "plugins/harness-creator/scripts"
    sync_dir.mkdir(parents=True)
    shutil.copy2(ROOT / "scripts/install-bundle.sh", repo / "scripts/install-bundle.sh")
    (repo / ".claude-plugin/bundles.json").write_text(
        json.dumps({"bundles": [{"name": "demo", "description": "demo", "plugins": ["broken"]}]}),
        encoding="utf-8",
    )
    (repo / ".claude-plugin/marketplace.json").write_text(
        json.dumps({"name": "skills", "plugins": []}), encoding="utf-8"
    )
    (sync_dir / "sync-native-surfaces.py").write_text("raise SystemExit(99)\n", encoding="utf-8")
    bin_dir = tmp_path / "bin"
    bin_dir.mkdir()
    claude = bin_dir / "claude"
    claude.write_text("#!/bin/sh\nexit 7\n", encoding="utf-8")
    claude.chmod(0o755)
    env = dict(os.environ, PATH=f"{bin_dir}:{os.environ['PATH']}")

    result = subprocess.run(
        ["bash", str(repo / "scripts/install-bundle.sh"), "demo"],
        cwd=repo,
        env=env,
        text=True,
        capture_output=True,
        check=False,
    )

    assert result.returncode == 5
    assert "native settings" not in result.stdout


def test_install_bundle_rejects_unsafe_marketplace_name(tmp_path: Path) -> None:
    repo = tmp_path / "repo"
    (repo / "scripts").mkdir(parents=True)
    (repo / ".claude-plugin").mkdir()
    shutil.copy2(ROOT / "scripts/install-bundle.sh", repo / "scripts/install-bundle.sh")
    (repo / ".claude-plugin/bundles.json").write_text(
        json.dumps({"bundles": [{"name": "demo", "description": "demo", "plugins": ["one"]}]}),
        encoding="utf-8",
    )
    (repo / ".claude-plugin/marketplace.json").write_text(
        json.dumps({"name": "skills; touch injected", "plugins": []}), encoding="utf-8"
    )

    result = subprocess.run(
        ["bash", str(repo / "scripts/install-bundle.sh"), "demo"],
        cwd=repo,
        text=True,
        capture_output=True,
        check=False,
    )

    assert result.returncode == 3
    assert not (repo / "injected").exists()


def test_install_bundle_passes_bundle_name_as_data_not_python_source(tmp_path: Path) -> None:
    repo = tmp_path / "repo"
    (repo / "scripts").mkdir(parents=True)
    (repo / ".claude-plugin").mkdir()
    shutil.copy2(ROOT / "scripts/install-bundle.sh", repo / "scripts/install-bundle.sh")
    (repo / ".claude-plugin/bundles.json").write_text(
        json.dumps({"bundles": [{"name": "demo", "description": "demo", "plugins": ["one"]}]}),
        encoding="utf-8",
    )
    (repo / ".claude-plugin/marketplace.json").write_text(
        json.dumps({"name": "skills", "plugins": []}), encoding="utf-8"
    )

    result = subprocess.run(
        ["bash", str(repo / "scripts/install-bundle.sh"), "demo'"],
        cwd=repo,
        text=True,
        capture_output=True,
        check=False,
    )

    assert result.returncode == 4
    assert "bundle 'demo\'' not found" in result.stderr
