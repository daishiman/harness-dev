from __future__ import annotations

# /// script
# name: test-extract-system-blueprint-browser-render
# purpose: browser-render (MCP 非依存 headless Chrome 取得) の認可 fail-closed・graceful 縮退
#          (browser-unavailable)・偽バイナリでの dump-dom/screenshot 経路・ledger 記録を検証する
# inputs:
#   - browser-render module / authz fixtures / 偽ブラウザ shell
# outputs:
#   - pytest assertions
# contexts: [C, E]
# network: false
# write-scope: pytest tmp_path only
# dependencies: [pytest]
# ///

import argparse
import json


def test_browser_render_self_test(browser_render, capsys):
    assert browser_render.main(["--self-test"]) == 0
    assert "self-test: PASS" in capsys.readouterr().out


def _authz(authz, tmp_path, write_json, allow=True):
    url, origin = "https://example.com/", "https://example.com"
    policy = {"robots": {"http_status": 200, "target_path_allowed": allow}}
    evidence, _ = authz.build_authz_evidence(url, origin, policy, offline=True, cached_evidence=None)
    dec, rea = authz.decide(evidence, policy)
    evidence.update(decision=dec, decision_reason=rea)
    budget = authz.build_budget(origin, "single", policy, evidence, None, dec == "allow")
    ev = write_json(tmp_path / "authz.json", evidence)
    bud = write_json(tmp_path / "budget.json", budget)
    return url, str(ev), str(bud)


def _fake_chrome(tmp_path):
    fake = tmp_path / "fake-chrome.sh"
    fake.write_text(
        "#!/usr/bin/env bash\n"
        "shot=\"\"\n"
        "for a in \"$@\"; do case \"$a\" in --screenshot=*) shot=\"${a#--screenshot=}\";; esac; done\n"
        "if [ -n \"$shot\" ]; then printf 'PNG' > \"$shot\"; else printf '<html>rendered</html>'; fi\n",
        encoding="utf-8",
    )
    fake.chmod(0o755)
    return str(fake)


def test_browser_unavailable_is_graceful_exit3(browser_render, authz, tmp_path, write_json, capsys):
    """ブラウザバイナリ不在は exit 3 (browser-unavailable) で graceful に縮退する。"""
    url, ev, bud = _authz(authz, tmp_path, write_json)
    ns = argparse.Namespace(
        url=url, out_dir=str(tmp_path / "out"), authz_evidence=ev, request_budget=bud,
        screenshot=False, viewport="1280x900", timeout=30,
        browser_bin=str(tmp_path / "definitely-not-a-browser"), request_ledger=None,
    )
    assert browser_render.render(ns) == 3
    assert json.loads(capsys.readouterr().out)["status"] == "browser-unavailable"


def test_render_with_fake_browser_captures_dom_and_screenshot(browser_render, authz, tmp_path, write_json, capsys):
    url, ev, bud = _authz(authz, tmp_path, write_json)
    ns = argparse.Namespace(
        url=url, out_dir=str(tmp_path / "out"), authz_evidence=ev, request_budget=bud,
        screenshot=True, viewport="1024x768", timeout=30,
        browser_bin=_fake_chrome(tmp_path), request_ledger=str(tmp_path / "ledger.json"),
    )
    assert browser_render.render(ns) == 0
    out = json.loads(capsys.readouterr().out)
    assert out["status"] == "ok"
    assert (tmp_path / "out" / out["rendered_dom_path"]).is_file()
    assert (tmp_path / "out" / out["screenshot_path"]).is_file()
    assert "browser_render" in json.loads((tmp_path / "ledger.json").read_text())


def test_render_denied_evidence_fail_closed(browser_render, authz, tmp_path, write_json):
    url, ev, bud = _authz(authz, tmp_path, write_json, allow=False)
    ns = argparse.Namespace(
        url=url, out_dir=str(tmp_path / "out"), authz_evidence=ev, request_budget=bud,
        screenshot=False, viewport="1280x900", timeout=30,
        browser_bin=_fake_chrome(tmp_path), request_ledger=None,
    )
    import pytest
    with pytest.raises(browser_render.AuthzDenied):
        browser_render.render(ns)


def test_resolve_browser_bin_prefers_explicit(browser_render, tmp_path):
    fake = _fake_chrome(tmp_path)
    assert browser_render.resolve_browser_bin(fake) == fake
    assert browser_render.resolve_browser_bin(str(tmp_path / "nope")) in (None, browser_render.resolve_browser_bin(None))
