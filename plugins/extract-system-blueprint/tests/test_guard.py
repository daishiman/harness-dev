from __future__ import annotations

# /// script
# name: test-extract-system-blueprint-authz-guard
# purpose: C08 pre-fetch-authz-guard の stdin CLI・状態索引・fetch-authz fail-closed 契約と
#          run-scoping (ESB run 非アクティブ時の co-install 素通し / アクティブ時の deny 回帰)、
#          bootstrap liveness (combined call 素通し / mkdir 単独先行の deadlock 回帰) を検証する。
#          hook は単一述語 (fetch-authz)。matcher=Bash|WebFetch。外部公開ゲートは持たない。
# inputs:
#   - C08 module / authz JSON fixtures
# outputs:
#   - pytest assertions and coverage evidence
# contexts: [C, E]
# network: false
# write-scope: pytest tmp_path only
# dependencies: [pytest]
# ///

import io
import json


def test_guard_formal_self_test(guard, capsys, monkeypatch):
    monkeypatch.delenv("CLAUDE_PROJECT_DIR", raising=False)
    assert guard.main(["--self-test"]) == 0
    assert "self-test: PASS" in capsys.readouterr().out


def test_guard_stdin_cli_fail_closed_and_passthrough(guard, monkeypatch, capsys):
    monkeypatch.setattr(guard.sys, "stdin", io.StringIO("not-json"))
    assert guard.main([]) == 2
    assert "fail-closed" in capsys.readouterr().err

    monkeypatch.setattr(
        guard.sys,
        "stdin",
        io.StringIO(json.dumps({"tool_name": "Read", "tool_input": {"file_path": "/tmp/x"}})),
    )
    assert guard.main([]) == 0
    # fetch-authz: url 不在 / AuthzEvidence 不在はいずれも fail-closed で deny (exit 2)
    assert guard.evaluate("WebFetch", {})[0] == 2
    assert guard.evaluate("WebFetch", {"url": "https://example.org/pricing"})[0] == 2
    # 非 fetch Bash は通過
    assert guard.evaluate("Bash", {"command": "printf hello"})[0] == 0


def test_guard_helpers_and_state_index(guard, tmp_path, monkeypatch, write_json):
    authz_dir = tmp_path / "authz"
    monkeypatch.setenv("ESB_AUTHZ_DIR", str(authz_dir))
    monkeypatch.setenv("CLAUDE_PROJECT_DIR", str(tmp_path / "project"))
    authz_dir.mkdir()
    (authz_dir / "broken.json").write_text("{", encoding="utf-8")
    evidence, _ = guard._AUTHZ.build_authz_evidence(
        "https://example.com/x", "https://example.com",
        {"robots": {"http_status": 200, "target_path_allowed": True}}, True, None,
    )
    decision, reason = guard._AUTHZ.decide(evidence, {})
    evidence.update(decision=decision, decision_reason=reason)
    budget = guard._AUTHZ.build_budget("https://example.com", "single", {}, evidence, None, True)
    write_json(authz_dir / "old-evidence.json", {**evidence, "fetched_at": "2000"})
    write_json(authz_dir / "new-evidence.json", {**evidence, "fetched_at": "2099"})
    write_json(authz_dir / "budget.json", budget)
    evidences, budgets = guard._load_authz_state()
    assert evidences["https://example.com"]["fetched_at"] == "2099"
    assert budgets["https://example.com"]["granted"] is True
    # allow: evidence+budget が揃った origin へは exit 0 (localhost も通過)
    assert guard.evaluate("Bash", {"command": "curl https://example.com/x"})[0] == 0
    assert guard.evaluate("Bash", {"command": "curl http://localhost:3000/x"})[0] == 0


def _clear_esb_env(monkeypatch):
    """run-scoping 判定に効く env を全て外し、cwd 探索だけで判定が決まる状態にする。"""
    for key in ("ESB_RUN", "ESB_AUTHZ_DIR", "ESB_VERDICT_DIR", "CLAUDE_PROJECT_DIR"):
        monkeypatch.delenv(key, raising=False)


def _run_main(guard, monkeypatch, payload: dict) -> int:
    monkeypatch.setattr(guard.sys, "stdin", io.StringIO(json.dumps(payload)))
    return guard.main([])


def test_guard_run_scoping_coinstall_passthrough_when_inactive(guard, tmp_path, monkeypatch, capsys):
    """co-install 負テスト: ESB run 非アクティブでは兄弟 plugin の正当な操作を遮断しない (exit 0)。"""
    _clear_esb_env(monkeypatch)
    monkeypatch.chdir(tmp_path)  # .esb-authz 不在の clean cwd
    assert guard._esb_run_active() is False

    external_bash = {
        "tool_name": "Bash",
        "tool_input": {"command": "curl -X POST https://api.example.com/v1/things --data '{}'"},
    }
    assert _run_main(guard, monkeypatch, external_bash) == 0
    external_fetch = {"tool_name": "WebFetch", "tool_input": {"url": "https://example.org/pricing"}}
    assert _run_main(guard, monkeypatch, external_fetch) == 0
    assert capsys.readouterr().err == ""


def test_guard_run_scoping_active_keeps_fail_closed(guard, tmp_path, monkeypatch, capsys, write_json):
    """回帰: ESB run アクティブ (.esb-authz あり) では fetch-authz の deny/allow が不変。"""
    _clear_esb_env(monkeypatch)
    monkeypatch.chdir(tmp_path)
    (tmp_path / ".esb-authz").mkdir()  # C12 の AuthzEvidence 置場 = run アクティブ化
    assert guard._esb_run_active() is True

    # deny 回帰: evidence 不在の外部 fetch (bash/WebFetch とも) → 従来どおり exit 2 (fetch-authz)
    external_bash = {
        "tool_name": "Bash",
        "tool_input": {"command": "curl -X POST https://api.example.com/v1/things --data '{}'"},
    }
    assert _run_main(guard, monkeypatch, external_bash) == 2
    assert "fetch-authz" in capsys.readouterr().err
    unknown_fetch = {"tool_name": "WebFetch", "tool_input": {"url": "https://no-evidence.example/x"}}
    assert _run_main(guard, monkeypatch, unknown_fetch) == 2
    assert "fetch-authz" in capsys.readouterr().err

    # allow 回帰: C12 実 producer の evidence+budget が揃った origin へは従来どおり exit 0
    evidence, _ = guard._AUTHZ.build_authz_evidence(
        "https://example.com/x", "https://example.com",
        {"robots": {"http_status": 200, "target_path_allowed": True}}, True, None,
    )
    decision, reason = guard._AUTHZ.decide(evidence, {})
    evidence.update(decision=decision, decision_reason=reason)
    budget = guard._AUTHZ.build_budget("https://example.com", "single", {}, evidence, None, True)
    write_json(tmp_path / ".esb-authz" / "evidence.json", evidence)
    write_json(tmp_path / ".esb-authz" / "budget.json", budget)
    assert _run_main(
        guard, monkeypatch, {"tool_name": "WebFetch", "tool_input": {"url": "https://example.com/x"}}
    ) == 0

    # env 明示宣言でもアクティブ化 (状態 dir 不在でも enforce 側=安全側へ倒れる)
    for leaf in (tmp_path / ".esb-authz").glob("*.json"):
        leaf.unlink()
    (tmp_path / ".esb-authz").rmdir()
    assert guard._esb_run_active() is False
    monkeypatch.setenv("ESB_RUN", "1")
    assert guard._esb_run_active() is True
    monkeypatch.delenv("ESB_RUN")
    monkeypatch.setenv("ESB_AUTHZ_DIR", str(tmp_path / "nonexistent-authz"))
    assert guard._esb_run_active() is True


def test_guard_bootstrap_liveness_combined_call(guard, tmp_path, monkeypatch, capsys):
    """bootstrap liveness: fresh run (状態 dir 不在) では combined call (mkdir && C12) が
    非アクティブ素通し (exit 0) で bootstrap が成立し、mkdir 単独先行後の C12 別呼びは
    evidence 不在 deny (exit 2) になる = 分割禁止 (bootstrap deadlock) の回帰固定。"""
    _clear_esb_env(monkeypatch)
    monkeypatch.chdir(tmp_path)  # .esb-authz 不在の clean cwd
    assert guard._esb_run_active() is False

    c12_call = (
        "python3 scripts/authz-classify.py --url https://example.com"
        " --evidence-out .esb-authz/authz.json --budget-out .esb-authz/budget.json"
    )
    # (a) 単一 Bash 呼び (mkdir && authz-classify): 呼び時点で dir 不在=非アクティブ → exit 0
    combined = {
        "tool_name": "Bash",
        "tool_input": {"command": f'mkdir -p "$PWD/.esb-authz" && {c12_call}'},
    }
    assert _run_main(guard, monkeypatch, combined) == 0
    assert capsys.readouterr().err == ""

    # (b) mkdir 単独先行の後 (dir あり=アクティブ・evidence 不在): C12 別呼び自身が deny → exit 2
    (tmp_path / ".esb-authz").mkdir()
    assert guard._esb_run_active() is True
    assert _run_main(guard, monkeypatch, {"tool_name": "Bash", "tool_input": {"command": c12_call}}) == 2
    assert "fetch-authz" in capsys.readouterr().err


def test_guard_url_fallback_and_budget_failures(guard, monkeypatch):
    monkeypatch.setattr(guard, "_AUTHZ", None)
    assert guard._origin("https://Example.COM:8443/x") == "https://example.com:8443"
    assert guard._origin("file:///tmp/x") is None
    assert guard._host("https://Example.COM/x") == "example.com"
    assert guard._host("http://[") is None
    assert guard._is_local_host("service.local") is True
    assert guard._is_local_host("172.18.0.2") is True
    assert guard._extract_url({"nested": {"command": "curl https://example.com/x"}}) == "https://example.com/x"
    assert guard._budget_has({}, "single", "request")[0] is False
    assert guard._budget_has({"requests": 0}, "single", "request")[0] is False
    assert guard._budget_ok({"granted": False}, "request")[0] is False
    assert guard._eval_fetch_origin("https://example.com", "request")[0] is False
