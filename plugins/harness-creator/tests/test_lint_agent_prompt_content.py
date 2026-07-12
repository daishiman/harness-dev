"""lint-agent-prompt-content.py (plan component C02) の機能テスト。

agents/*.md (frontmatter=plugin YAML + 本文7層) と skills/*/prompts/*.md (純粋7層) の本文が
l5-contract v2.0.0 に準拠するかを --mode agent|prompt で fail-closed 検証する内容 lint の
受入・負例・vendor parity・symlink 除外・usage error を固定する。
"""
from __future__ import annotations

import subprocess
import sys
from pathlib import Path

import pytest

SCRIPT = (
    Path(__file__).resolve().parent.parent / "scripts" / "lint-agent-prompt-content.py"
)

# ── 最小の合格 7 層本文 (verify-completeness を exit0 で通過する) ──
_VALID_BODY = """\
## Layer 1: 基本定義層
- 目的: probe

## Layer 2: ドメイン定義層
- 単一責務: probe

## Layer 3: インフラストラクチャ定義層
- Read

## Layer 4: 共通ポリシー層
- 品質基準

## Layer 5: エージェント定義層
### 5.1 担当 agent
- probe-agent
### 5.2 ゴール定義
- 目的: x / 背景: y / 達成ゴール: x が完了した状態になっている
### 5.3 完了チェックリスト (ゴール到達の停止条件)
- [ ] z が YES
### 5.4 実行方式
- 固定手順を持たない。未充足項目を都度立案し反復する。

## Layer 6: オーケストレーション層
- handoff: 後続へ渡す

## Layer 7: UI / 提示層
- 出力形式: JSON
"""

_AGENT_FM = (
    "---\n"
    "name: probe-agent\n"
    "description: テスト用。〜なとき、〜したいときに使う。\n"
    "tools: Read, Glob\n"
    "---\n\n"
)


def _valid_agent() -> str:
    return _AGENT_FM + _VALID_BODY


# ─────────────────── split_frontmatter (単体) ───────────────────
def test_split_frontmatter_present(content_lint):
    fm, body = content_lint.split_frontmatter(_valid_agent())
    assert fm is not None and "name: probe-agent" in fm
    assert body.lstrip().startswith("## Layer 1")  # frontmatter 終端後の空行を許容


def test_split_frontmatter_absent(content_lint):
    fm, body = content_lint.split_frontmatter(_VALID_BODY)
    assert fm is None
    assert body.startswith("## Layer 1")


# ─────────────────── check_agent_frontmatter (単体) ───────────────────
def test_frontmatter_complete_has_no_missing(content_lint):
    assert content_lint.check_agent_frontmatter("name: x\ndescription: y\ntools: Read") == []


def test_frontmatter_missing_tools_detected(content_lint):
    missing = content_lint.check_agent_frontmatter("name: x\ndescription: y")
    assert "tools" in missing and "name" not in missing


# ─────────────────── lint_file --mode agent ───────────────────
def test_agent_valid_passes(content_lint, tmp_path):
    f = tmp_path / "agents" / "probe-agent.md"
    f.parent.mkdir(parents=True)
    f.write_text(_valid_agent(), encoding="utf-8")
    assert content_lint.lint_file(f, "agent") == []


def test_agent_without_frontmatter_flagged(content_lint, tmp_path):
    f = tmp_path / "a.md"
    f.write_text(_VALID_BODY, encoding="utf-8")  # 本文7層 OK だが frontmatter 無し
    viols = content_lint.lint_file(f, "agent")
    assert any("AGENT-FRONTMATTER-MISSING" in v for v in viols)


def test_agent_missing_key_flagged(content_lint, tmp_path):
    f = tmp_path / "a.md"
    f.write_text("---\nname: x\ndescription: y\n---\n\n" + _VALID_BODY, encoding="utf-8")
    viols = content_lint.lint_file(f, "agent")
    assert any("AGENT-FRONTMATTER-KEYS" in v and "tools" in v for v in viols)


def test_agent_bad_body_flagged(content_lint, tmp_path):
    f = tmp_path / "a.md"
    f.write_text(_AGENT_FM + "# 役割\n本文だけで Layer マーカー無し\n", encoding="utf-8")
    viols = content_lint.lint_file(f, "agent")
    assert any("BODY-7LAYER" in v for v in viols)


# ─────────────────── lint_file --mode prompt ───────────────────
def test_prompt_valid_passes(content_lint, tmp_path):
    f = tmp_path / "R1.md"
    f.write_text(_VALID_BODY, encoding="utf-8")
    assert content_lint.lint_file(f, "prompt") == []


def test_prompt_with_frontmatter_flagged(content_lint, tmp_path):
    f = tmp_path / "R1.md"
    f.write_text(_valid_agent(), encoding="utf-8")  # frontmatter 付きは prompt では違反
    viols = content_lint.lint_file(f, "prompt")
    assert any("PROMPT-FRONTMATTER-PRESENT" in v for v in viols)


# ─────────────────── collect_targets: symlink 除外 ───────────────────
def test_collect_targets_excludes_symlinked_skill(content_lint, tmp_path):
    pdir = tmp_path / "myplugin"
    own = pdir / "skills" / "run-own" / "prompts"
    own.mkdir(parents=True)
    (own / "R1.md").write_text(_VALID_BODY, encoding="utf-8")
    # 他プラグインの skill を bundling する symlink
    other = tmp_path / "otherplugin" / "skills" / "run-linked"
    (other / "prompts").mkdir(parents=True)
    (other / "prompts" / "R1.md").write_text("x", encoding="utf-8")
    link = pdir / "skills" / "run-linked"
    link.symlink_to(other, target_is_directory=True)

    targets = content_lint.collect_targets(pdir, "prompt")
    names = {t.parent.parent.name for t in targets}
    assert "run-own" in names
    assert "run-linked" not in names  # symlink は除外


# ─────────────────── check_vendor_parity ───────────────────
def test_vendor_parity_ok_on_real_files(content_lint):
    status, _ = content_lint.check_vendor_parity()
    # monorepo 文脈では canonical 実在 → OK。install 文脈でも SKIP は 0 扱い。
    assert status in ("OK", "SKIP_NO_CANONICAL")


def test_vendor_parity_mismatch(content_lint, tmp_path, monkeypatch):
    vend = tmp_path / "vendored.py"
    canon = tmp_path / "canonical.py"
    vend.write_text("A", encoding="utf-8")
    canon.write_text("B", encoding="utf-8")
    monkeypatch.setattr(content_lint, "VENDORED_VERIFY", vend)
    monkeypatch.setattr(content_lint, "CANONICAL_VERIFY", canon)
    status, _ = content_lint.check_vendor_parity()
    assert status == "MISMATCH"


def test_vendor_parity_skip_when_canonical_absent(content_lint, tmp_path, monkeypatch):
    vend = tmp_path / "vendored.py"
    vend.write_text("A", encoding="utf-8")
    monkeypatch.setattr(content_lint, "VENDORED_VERIFY", vend)
    monkeypatch.setattr(content_lint, "CANONICAL_VERIFY", tmp_path / "nope.py")
    status, _ = content_lint.check_vendor_parity()
    assert status == "SKIP_NO_CANONICAL"


# ─────────────────── main / CLI exit codes ───────────────────
def _run(*args) -> subprocess.CompletedProcess:
    return subprocess.run(
        [sys.executable, str(SCRIPT), *args], capture_output=True, text=True
    )


def test_cli_self_test_ok():
    assert _run("--self-test").returncode == 0


def test_cli_vendor_parity_ok():
    assert _run("--check-vendor-parity").returncode == 0


def test_cli_no_args_is_usage_error():
    assert _run().returncode == 2


def test_cli_mode_prompt_own_content_passes():
    # 所有プラグイン (既定 plugins-dir) の prompts は全て準拠している
    assert _run("--mode", "prompt").returncode == 0


def test_cli_mode_agent_scans_own_dir(content_lint):
    # 既定 plugins-dir が所有プラグインを指し、agents をちょうど 6 本走査する
    targets = content_lint.collect_targets(content_lint._PLUGIN_ROOT, "agent")
    assert len(targets) == 6


def test_cli_bad_plugins_dir_is_usage_error(tmp_path):
    assert _run("--mode", "agent", "--plugins-dir", str(tmp_path / "nope")).returncode == 2


# ─────────────────── main() を in-process で叩く (dispatch/exit code 網羅) ───────────────────
def test_main_self_test_in_process(content_lint):
    assert content_lint.main(["--self-test"]) == 0


def test_main_parity_in_process(content_lint):
    assert content_lint.main(["--check-vendor-parity"]) == 0


def test_main_mode_prompt_in_process(content_lint):
    assert content_lint.main(["--mode", "prompt"]) == 0


def test_main_no_args_returns_2(content_lint):
    assert content_lint.main([]) == 2


def test_main_bad_dir_returns_2(content_lint, tmp_path):
    assert content_lint.main(["--mode", "agent", "--plugins-dir", str(tmp_path / "nope")]) == 2


def test_main_mode_agent_on_valid_temp_dir_passes(content_lint, tmp_path):
    adir = tmp_path / "agents"
    adir.mkdir()
    (adir / "probe-agent.md").write_text(_valid_agent(), encoding="utf-8")
    assert content_lint.main(["--mode", "agent", "--plugins-dir", str(tmp_path)]) == 0


def test_main_mode_agent_on_bad_temp_dir_fails(content_lint, tmp_path):
    adir = tmp_path / "agents"
    adir.mkdir()
    (adir / "broken.md").write_text("# 役割\nLayer マーカー無し\n", encoding="utf-8")
    assert content_lint.main(["--mode", "agent", "--plugins-dir", str(tmp_path)]) == 1


# ─────────────────── scanned=0 floor guard (fail-open 封鎖) ───────────────────
def test_main_scanned_zero_agents_dir_absent_fails(content_lint, tmp_path):
    # dir は実在するが agents/ が無い (plugins 親ディレクトリ誤指定と同型) → 空振り合格を禁止
    assert content_lint.main(["--mode", "agent", "--plugins-dir", str(tmp_path)]) == 1


def test_main_scanned_zero_empty_agents_dir_fails(content_lint, tmp_path):
    (tmp_path / "agents").mkdir()
    assert content_lint.main(["--mode", "agent", "--plugins-dir", str(tmp_path)]) == 1


def test_main_scanned_zero_prompt_mode_fails(content_lint, tmp_path):
    (tmp_path / "skills" / "run-empty").mkdir(parents=True)  # prompts/*.md 0 件
    assert content_lint.main(["--mode", "prompt", "--plugins-dir", str(tmp_path)]) == 1


def test_cli_scanned_zero_reports_fail_closed(tmp_path):
    (tmp_path / "agents").mkdir()
    proc = _run("--mode", "agent", "--plugins-dir", str(tmp_path))
    assert proc.returncode == 1
    assert "scanned=0" in proc.stderr


def test_verify_body_missing_vendor_returns_false(content_lint, tmp_path, monkeypatch):
    monkeypatch.setattr(content_lint, "VENDORED_VERIFY", tmp_path / "nope.py")
    f = tmp_path / "a.md"
    f.write_text(_VALID_BODY, encoding="utf-8")
    ok, detail = content_lint.verify_body_7layer(f)
    assert ok is False and "vendored verifier 不在" in detail


def test_parity_missing_vendor_run_returns_1(content_lint, tmp_path, monkeypatch):
    monkeypatch.setattr(content_lint, "VENDORED_VERIFY", tmp_path / "nope.py")
    monkeypatch.setattr(content_lint, "CANONICAL_VERIFY", tmp_path / "canon.py")
    assert content_lint._run_parity() == 1
