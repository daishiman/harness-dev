#!/usr/bin/env python3
# /// script
# name: live-trial-boot
# purpose: 隔離 claude セッションを tmux 上で起動し READY まで待つ (session UUID 固定で transcript を決定的に引けるようにする)。
# inputs:
#   - argv: <session> <cwd> [--model M] [--session-id UUID] [--target-skill plugin:skill] [--self-test]
#   - env: BOOT_TIMEOUT(90) BOOT_GRACE(3) — テスト高速化用。通常は触らない
# outputs:
#   - stdout: "READY: <session> (Ns) MODEL:<model|default> SESSION_ID:<uuid>" / BOOT_FAIL / TIMEOUT
#   - exit: 0=READY / 1=BOOT_FAIL・TIMEOUT / 2=usage・denylist / 3=BLOCKED (tmux 不在)
# contexts: [C, E]
# network: false
# write-scope: none
# dependencies: []
# requires-python: ">=3.10"
# ///
"""本物の claude を別 tmux プロセスで起動する (fork subagent では自走/入れ子/hook が再現できないため)。

- model 省略/空 = ユーザー既定 model。指定時は claude コマンド行に --model を焼き込む
  (env 継承は tmux 越しに不確実なためコマンドライン焼き込みが唯一確実)。
- 注意: claude は --model を起動時検証しない (実測 v2.1.173: 不正 model でも READY まで
  到達し初 turn でエラー)。BOOT_FAIL が捕まえるのは claude 不在 / 即 crash のみ —
  実走 model の検証は live-trial-verdict.py の transcript 機械 gate で行う。
- --session-id で transcript を ~/.claude/projects/*/<uuid>.jsonl に決定的に固定する
  (transcript は初 prompt 送信時に生成されるため READY 検知自体は TUI capture で行う)。
- trial の workdir (task.md / out/ / verdict) は eval-log/<plugin>/<skill>/live-trial/<run-id>/
  固定 (SKILL.md 準備局面参照)。旧 AG 版の $HOME/playground fallback / .mso は全廃。
"""
from __future__ import annotations

import argparse
import importlib.util
import json
import os
import re
import shlex
import sys
import time
import uuid
from pathlib import Path

_MODEL_RE = re.compile(r"^[A-Za-z0-9._-]+$")
_SESSION_ID_RE = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._-]{0,127}$")
_PLUGIN_SLUG_RE = re.compile(r"^[a-z0-9][a-z0-9-]*$")
_SKILL_NAME_RE = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._-]*$")
_READY_RE = re.compile(
    r"for shortcuts|^❯[ \u00a0]+(?:Try\b[^\r\n]*|[ \u00a0]*)$",
    re.MULTILINE,
)
_BYPASS_CONFIRM_MARKERS = (
    "WARNING: Claude Code running in Bypass Permissions mode",
    "1. No, exit",
    "2. Yes, I accept",
    "Enter to confirm",
)
# pane_current_command 実測: claude (native binary) 起動中は版数文字列 (node とは限らない)
# → whitelist でなく shell blacklist (+ 空 = tmux 消失) 固定で判定。ワイルドカード不使用
# (`*sh` は ssh 等を誤爆)。blacklist 外 shell (tcsh/ksh/nu/pwsh) では BOOT_FAIL も READY
# 偽陽性 guard も無効 → TIMEOUT へ縮退 (安全側)。
_SHELL_BLACKLIST = {"zsh", "bash", "sh", "fish", "dash", ""}


def _load_sibling(stem: str):
    path = Path(__file__).resolve().parent / f"{stem}.py"
    spec = importlib.util.spec_from_file_location(stem.replace("-", "_"), path)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


def valid_model(model: str) -> bool:
    return not model or bool(_MODEL_RE.fullmatch(model))


def valid_session_id(session_id: str) -> bool:
    return bool(_SESSION_ID_RE.fullmatch(session_id)) and ".." not in session_id


def _resolve_plugin_dir(root: Path, plugin_slug: str, *, purpose: str) -> Path:
    plugins_root = (root / "plugins").resolve()
    candidate = (plugins_root / plugin_slug).resolve()
    try:
        candidate.relative_to(plugins_root)
    except ValueError as exc:
        raise ValueError(f"{purpose} plugin escapes cwd/plugins: {candidate}") from exc
    if not candidate.is_dir():
        raise ValueError(f"{purpose} plugin directory not found: {candidate}")
    manifest_path = candidate / ".claude-plugin" / "plugin.json"
    try:
        manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise ValueError(
            f"{purpose} plugin manifest read/parse error: {manifest_path}: {exc}"
        ) from exc
    if not isinstance(manifest, dict) or manifest.get("name") != plugin_slug:
        actual = manifest.get("name") if isinstance(manifest, dict) else None
        raise ValueError(
            f"{purpose} plugin manifest name mismatch: "
            f"expected={plugin_slug} actual={actual}"
        )
    return candidate


def _declared_dependency_slugs(plugin_dir: Path, skill_name: str) -> tuple[str, ...]:
    """Return only the direct plugins needed by ``skill_name``.

    ``depends_on`` remains the package-level allow-list.  When the optional
    ``skill_dependencies`` map is present it narrows runtime loading per skill;
    an absent map preserves the legacy behavior of loading every direct
    dependency.  This keeps old contracts working while preventing one
    dependency change from forcing unrelated live trials to reload and rerun.
    """
    contract_path = plugin_dir / "references" / "package-contract.json"
    if not contract_path.is_file():
        return ()
    try:
        contract = json.loads(contract_path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise ValueError(
            f"target package contract read/parse error: {contract_path}: {exc}"
        ) from exc
    if not isinstance(contract, dict) or contract.get("plugin_name") != plugin_dir.name:
        actual = contract.get("plugin_name") if isinstance(contract, dict) else None
        raise ValueError(
            "target package contract plugin_name mismatch: "
            f"expected={plugin_dir.name} actual={actual}"
        )
    depends = contract.get("depends_on", [])
    if not isinstance(depends, list) or not all(
        isinstance(item, str) and _PLUGIN_SLUG_RE.fullmatch(item)
        for item in depends
    ):
        raise ValueError(
            f"target package contract depends_on must be plugin slug strings: {contract_path}"
        )
    if len(depends) != len(set(depends)):
        raise ValueError(f"target package contract depends_on contains duplicates: {contract_path}")
    if plugin_dir.name in depends:
        raise ValueError(f"target package contract depends_on contains self: {contract_path}")
    scoped = contract.get("skill_dependencies")
    if scoped is None:
        return tuple(sorted(depends))
    if not isinstance(scoped, dict):
        raise ValueError(
            f"target package contract skill_dependencies must be an object: {contract_path}"
        )
    known_skills = set(
        contract.get("entry_points", {}).get("skills", [])
        if isinstance(contract.get("entry_points"), dict) else []
    )
    for declared_skill, dependencies in scoped.items():
        if not isinstance(declared_skill, str) or not _SKILL_NAME_RE.fullmatch(declared_skill):
            raise ValueError(
                f"target package contract skill_dependencies has invalid skill: {declared_skill!r}"
            )
        if known_skills and declared_skill not in known_skills:
            raise ValueError(
                "target package contract skill_dependencies references an undeclared "
                f"entry point: {declared_skill}"
            )
        if not isinstance(dependencies, list) or not all(
            isinstance(item, str) and _PLUGIN_SLUG_RE.fullmatch(item)
            for item in dependencies
        ):
            raise ValueError(
                "target package contract skill_dependencies values must be plugin slug "
                f"arrays: {declared_skill}"
            )
        if len(dependencies) != len(set(dependencies)):
            raise ValueError(
                f"target package contract skill_dependencies contains duplicates: {declared_skill}"
            )
        undeclared = sorted(set(dependencies) - set(depends))
        if undeclared:
            raise ValueError(
                "target package contract skill_dependencies must be a subset of depends_on: "
                f"{declared_skill} -> {undeclared}"
            )
    return tuple(sorted(scoped.get(skill_name, [])))


def resolve_target_plugin_dirs(cwd: str, target_skill: str) -> tuple[Path, ...]:
    """qualified targetと宣言済みdirect dependenciesをcwd内へ固定する。

    plain skill name/空は後方互換のため空tuple。`plugin:skill` はtargetの
    package-contract.depends_onだけを追加loadし、未宣言pluginはargvへ入れない。
    """
    target = str(target_skill or "").strip()
    if ":" not in target:
        return ()
    if target.count(":") != 1:
        raise ValueError(f"invalid qualified target skill: {target}")
    plugin_slug, skill_name = target.split(":", 1)
    if not _PLUGIN_SLUG_RE.fullmatch(plugin_slug):
        raise ValueError(f"invalid target plugin slug: {plugin_slug}")
    if not _SKILL_NAME_RE.fullmatch(skill_name):
        raise ValueError(f"invalid target skill name: {skill_name}")

    root = Path(cwd).resolve()
    candidate = _resolve_plugin_dir(root, plugin_slug, purpose="target")
    skill_file = candidate / "skills" / skill_name / "SKILL.md"
    if not skill_file.is_file():
        raise ValueError(f"target skill not found in pinned plugin: {skill_file}")
    dependencies = tuple(
        _resolve_plugin_dir(root, dependency, purpose="declared dependency")
        for dependency in _declared_dependency_slugs(candidate, skill_name)
    )
    return (candidate, *dependencies)


def resolve_target_plugin_dir(cwd: str, target_skill: str) -> Path | None:
    """Compatibility wrapper returning only the target plugin directory."""
    plugin_dirs = resolve_target_plugin_dirs(cwd, target_skill)
    return plugin_dirs[0] if plugin_dirs else None


def _normalize_plugin_dirs(
    plugin_dirs: str | Path | tuple[str | Path, ...] | list[str | Path] | None,
) -> tuple[Path, ...]:
    if plugin_dirs is None:
        return ()
    values = (plugin_dirs,) if isinstance(plugin_dirs, (str, Path)) else tuple(plugin_dirs)
    resolved: list[Path] = []
    for plugin_dir in values:
        path = Path(plugin_dir).resolve()
        if not path.is_dir():
            raise ValueError(f"plugin directory not found: {path}")
        if path in resolved:
            raise ValueError(f"duplicate plugin directory: {path}")
        resolved.append(path)
    return tuple(resolved)


def build_claude_argv(
    session_id: str, model: str,
    plugin_dir: str | Path | tuple[str | Path, ...] | list[str | Path] | None = None,
) -> tuple[str, ...]:
    """validated values からだけ claude argv を構成する。"""
    if not valid_session_id(session_id):
        raise ValueError(f"invalid session id: {session_id}")
    if not valid_model(model):
        raise ValueError(f"invalid model: {model}")
    # trust 済み project 前提。多数のツール呼びを止めないため bypass で起動
    argv = [
        "claude", "--session-id", session_id,
        "--dangerously-skip-permissions",
        # live-trial はplugin本体とそのhooksを --plugin-dir からロードし、
        # 無関係なuser/project settings driftはacceptance環境から除外する。
        # auth/sessionはsetting sourceと別系統のため維持される。
        "--setting-sources", "local",
    ]
    if model:
        argv += ["--model", model]
    for resolved in _normalize_plugin_dirs(plugin_dir):
        argv += ["--plugin-dir", str(resolved)]
    return tuple(argv)


def build_claude_command(
    session_id: str, model: str,
    plugin_dir: str | Path | tuple[str | Path, ...] | list[str | Path] | None = None,
) -> str:
    """後方互換用の表示形。実起動は build_claude_argv を使う。"""
    return shlex.join(build_claude_argv(session_id, model, plugin_dir))


def _tail(text: str, n: int = 15) -> str:
    return "\n".join(text.splitlines()[-n:])


def is_bypass_permissions_confirm(text: str) -> bool:
    """自動応答を許す唯一の既知gate。4 markerのAND一致に限定する。"""
    return all(marker in text for marker in _BYPASS_CONFIRM_MARKERS)


def boot(backend, session: str, cwd: str, model: str, session_id: str,
         timeout: int, grace: int,
         plugin_dir: str | Path | tuple[str | Path, ...] | list[str | Path] | None = None) -> int:
    # tmux 既定の対話 shell 起動→send-line に依存せず、検証済み
    # claude argv を pane の直接 shell-command として起動する。
    backend.new_session(
        session, cwd, command_argv=build_claude_argv(session_id, model, plugin_dir)
    )
    bypass_confirmed = False
    for i in range(1, timeout + 1):
        cap = backend.capture_pane(session)
        cmd = backend.pane_current_command(session)
        at_shell = cmd in _SHELL_BLACKLIST
        exact_bypass_gate = is_bypass_permissions_confirm(cap)
        if exact_bypass_gate and not bypass_confirmed:
            # `--dangerously-skip-permissions` 初回起動で出る既知gateだけを
            # 一度だけ受理する。他の質問/gateは自動応答しない。
            # 実TUIで数字`2`は選択移動として受理されないため、
            # option 1 から Down で1段移動し Enter で確定する。
            backend.send_keys(session, "Down")
            # TUIが選択移動をrenderする前にEnterを連続送信すると
            # option 1を確定し得るため、key境界を分ける。
            time.sleep(0.25)
            backend.send_keys(session, "Enter")
            bypass_confirmed = True
            time.sleep(1)
            continue
        # READY = 「READY パターン + 前面プロセスが shell でない」の AND
        # (shell prompt の ❯ で偽 READY しない)。受理済みgateが
        # 残っている間もREADYにせず、実入力promptまで待つ。
        if not exact_bypass_gate and not at_shell and _READY_RE.search(cap):
            print(f"READY: {session} ({i}s) MODEL:{model or 'default'} SESSION_ID:{session_id}")
            return 0
        # 死亡検出: direct process が即死すると tmux session が消失し
        # pane_current_command="" になる。後方互換の shell 復帰も同じ分岐。
        if at_shell and i > grace:
            print(f"BOOT_FAIL: claude exited before ready ({i}s)")
            print("--- capture tail ---")
            print(_tail(cap))
            backend.kill_session(session)
            return 1
        time.sleep(1)
    print(f"TIMEOUT: {session} did not boot in {timeout}s")
    print("--- capture tail ---")
    print(_tail(backend.capture_pane(session)))
    backend.kill_session(session)
    return 1


def _self_test() -> int:
    backend = _load_sibling("live-trial-backend")
    assert _MODEL_RE.match("claude-opus-4-8")
    assert not _MODEL_RE.match("bad model; rm -rf")
    assert valid_session_id("u-1")
    assert valid_session_id("550e8400-e29b-41d4-a716-446655440000")
    assert not valid_session_id("bad; touch /tmp/nope")
    assert not valid_session_id("../bad")
    gate = "\n".join(_BYPASS_CONFIRM_MARKERS)
    assert is_bypass_permissions_confirm(gate)
    assert not is_bypass_permissions_confirm(gate.replace("2. Yes, I accept", "2. Continue"))
    assert resolve_target_plugin_dir("/tmp", "plain-skill") is None
    assert resolve_target_plugin_dirs("/tmp", "plain-skill") == ()
    assert backend.deny_target_skill("run-skill-live-trial")
    argv = build_claude_argv("u-1", "claude-opus-4-8")
    assert argv == (
        "claude", "--session-id", "u-1", "--dangerously-skip-permissions",
        "--setting-sources", "local",
        "--model", "claude-opus-4-8",
    )
    cmd = build_claude_command("u-1", "claude-opus-4-8")
    assert "--session-id u-1" in cmd and "--model claude-opus-4-8" in cmd
    assert "--model" not in build_claude_command("u-1", "")
    print("OK: live-trial-boot self-test")
    return 0


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("session", nargs="?")
    ap.add_argument("cwd", nargs="?")
    ap.add_argument("--model", default="", help="空=ユーザー既定 model。proof trial は full id 必須")
    ap.add_argument("--session-id", default="", help="transcript 固定用 UUID (省略時は自動生成)")
    ap.add_argument("--target-skill", default="",
                    help="被験 skill (denylist 再帰遮断の機械 gate。省略可だが指定推奨)")
    ap.add_argument("--self-test", action="store_true")
    ns = ap.parse_args(argv)
    if ns.self_test:
        return _self_test()
    if not ns.session or not ns.cwd:
        ap.print_usage(sys.stderr)
        return 2

    backend = _load_sibling("live-trial-backend")
    if ns.target_skill and backend.deny_target_skill(ns.target_skill):
        print(f"[ERROR] DENYLIST: 被験 skill {ns.target_skill} は再帰遮断対象 "
              f"({sorted(backend.DENY_TARGET_SKILLS)})", file=sys.stderr)
        return 2
    if not backend.valid_session_name(ns.session):
        print(f"[ERROR] invalid session name: {ns.session}", file=sys.stderr)
        return 2
    if not Path(ns.cwd).is_dir():
        print(f"[ERROR] cwd not found: {ns.cwd}", file=sys.stderr)
        return 2
    if not valid_model(ns.model):
        print(f"[ERROR] invalid model: {ns.model}", file=sys.stderr)
        return 2
    session_id = (ns.session_id or str(uuid.uuid4())).lower()
    if not valid_session_id(session_id):
        print(f"[ERROR] invalid session id: {session_id}", file=sys.stderr)
        return 2
    try:
        plugin_dirs = resolve_target_plugin_dirs(ns.cwd, ns.target_skill)
    except ValueError as exc:
        print(f"[ERROR] {exc}", file=sys.stderr)
        return 2
    backend.require_tmux()
    timeout = int(os.environ.get("BOOT_TIMEOUT", "90"))
    grace = int(os.environ.get("BOOT_GRACE", "3"))
    return boot(
        backend, ns.session, ns.cwd, ns.model, session_id, timeout, grace,
        plugin_dir=plugin_dirs,
    )


if __name__ == "__main__":
    raise SystemExit(main())
