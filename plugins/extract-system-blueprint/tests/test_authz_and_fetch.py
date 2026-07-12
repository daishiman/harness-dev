from __future__ import annotations

# /// script
# name: test-extract-system-blueprint-authz-fetch
# purpose: C12 authz-classify と C09 fetch-snapshot の正式 CLI・fail-closed・offline fixture 契約を検証する
# inputs:
#   - C12/C09 modules / pytest tmp_path fixtures
# outputs:
#   - pytest assertions and coverage evidence
# contexts: [C, E]
# network: false
# write-scope: pytest tmp_path only
# dependencies: [pytest]
# ///

import email
import json
import urllib.request

import pytest


ALLOW_POLICY = {
    "offline": True,
    "robots": {
        "http_status": 200,
        "target_path_allowed": True,
        "crawl_delay_ms": 0,
        "raw_excerpt": "User-agent: *\nAllow: /",
    },
    "tos": {"decision": "allow", "basis": "fixture"},
    "related_origins": ["https://static.example.com"],
}


def test_authz_cli_allow_budget_and_scope(authz, tmp_path, write_json, capsys):
    discovered = write_json(
        tmp_path / "discovered.json",
        [
            "https://example.com/about",
            "https://static.example.com/app.js",
            "https://twitter.com/example",
            "https://ads.example.net/banner",
            "https://external.example/path?utm_source=x",
            "not-a-url",
        ],
    )
    policy = write_json(tmp_path / "policy.json", ALLOW_POLICY)
    evidence = tmp_path / "evidence.json"
    budget = tmp_path / "budget.json"
    scope = tmp_path / "scope.json"
    rc = authz.main(
        [
            "--url", "https://example.com/",
            "--evidence-out", str(evidence),
            "--budget-out", str(budget),
            "--operator-policy", str(policy),
            "--crawl-mode", "full_site",
            "--discovered-urls", str(discovered),
            "--scope-manifest-out", str(scope),
        ]
    )
    result = json.loads(capsys.readouterr().out)
    assert rc == 0 and result["decision"] == "allow"
    assert json.loads(evidence.read_text())["robots"]["status"] == "allow"
    budget_doc = json.loads(budget.read_text())
    assert budget_doc["granted"] is True
    assert budget_doc["instant_load_levers"]["max_concurrency_per_origin"] == 1
    scope_doc = json.loads(scope.read_text())
    assert {x["reason"] for x in scope_doc["excluded"]} >= {
        "external_social", "external_utm_link", "undecidable_unparseable"
    }
    assert scope_doc["resume"]["multi_run_resume"] is True


def test_authz_deny_unknown_usage_and_helpers(authz, tmp_path, write_json, capsys):
    policy = write_json(tmp_path / "deny.json", {"offline": True})
    rc = authz.main([
        "--url", "https://example.com/x", "--evidence-out", str(tmp_path / "e.json"),
        "--budget-out", str(tmp_path / "b.json"), "--operator-policy", str(policy),
    ])
    assert rc == 1
    assert json.loads(capsys.readouterr().out)["authorized"] is False
    assert authz.main(["--url", "file:///tmp/x", "--evidence-out", "x", "--budget-out", "y"]) == 2
    capsys.readouterr()

    assert authz.classify_url("https://analytics.example.net/x", "https://example.com", set()) == (
        False, "external_tracker"
    )
    assert authz.classify_url("https://a8.net/x", "https://example.com", set()) == (
        False, "external_affiliate"
    )
    assert authz.decide({"expires_at": "2000-01-01T00:00:00Z"}, {})[1] == "evidence_expired"
    assert authz.decide({"robots": {"status": "allowed", "target_path_allowed": True}, "tos": {"decision": "deny"}}, {})[1] == "tos_prohibits"
    assert authz.decide({"robots": {"status": "unknown", "target_path_allowed": None}, "tos": {}}, {"decision_override": "allow"})[0] == "allow"


def test_authz_network_evidence_status_matrix(authz, monkeypatch):
    matrix = [
        ({"http_status": 200, "text": "User-agent: *\nDisallow: /private", "error": None}, "allow"),
        ({"http_status": 403, "text": None, "error": "http 403"}, "restricted"),
        ({"http_status": 404, "text": None, "error": "http 404"}, "no_robots"),
        ({"http_status": 503, "text": None, "error": "http 503"}, "unknown"),
    ]
    for fetched, expected in matrix:
        monkeypatch.setattr(authz, "_fetch_robots", lambda _origin, value=fetched: value)
        evidence, count = authz._robots_evidence(
            "https://example.com", "https://example.com/public", {}, offline=False
        )
        assert count == 1 and evidence["status"] == expected

    cached = {"expires_at": "2099-01-01T00:00:00Z", "robots": {"status": "allow"}}
    reused, count = authz.build_authz_evidence(
        "https://example.com", "https://example.com", {"offline": True}, True, cached
    )
    assert count == 0 and reused["source"] == "reused_cached"


def test_authz_full_site_budget_override_and_resume(authz):
    evidence = {"url": "https://example.com", "policy_version": "p", "expires_at": "2099-01-01T00:00:00Z"}
    coverage = {"request_ledger": {"https://example.com": {"requests": 2, "pages": 1, "bytes": 10}}}
    budget = authz.build_budget(
        "https://example.com", "full_site",
        {"per_run_override": {"approved_by_user": True, "pages_per_run": 2, "requests_per_run": 5}},
        evidence, coverage, True,
    )
    assert budget["limits"]["pages_per_run"] == 2
    assert budget["remaining"]["requests_per_run"] == 3
    ignored = authz.build_budget(
        "https://example.com", "full_site", {"per_run_override": {"pages_per_run": 99}},
        evidence, None, True,
    )
    assert "ignored" in ignored["per_run_override_note"]


def test_fetch_snapshot_formal_self_test(fetch_snapshot, capsys):
    assert fetch_snapshot.main(["--self-test"]) == 0
    assert "self-test: PASS" in capsys.readouterr().out


def test_fetch_snapshot_usage(fetch_snapshot, capsys):
    assert fetch_snapshot.main([]) == 2
    assert "usage:" in capsys.readouterr().err
    assert fetch_snapshot._parse_retry_after({"retry-after": "1"}) == 1.0
    assert fetch_snapshot._parse_sitemap(b"<urlset><url><loc>https://example.com/a</loc></url></urlset>") == [
        "https://example.com/a"
    ]


def _fetch_inputs(authz, tmp_path, write_json, url, origin):
    """fetch-snapshot 用の allow evidence/budget ファイルを組む (offline fixture)。"""
    evidence, _ = authz.build_authz_evidence(url, origin, ALLOW_POLICY, True, None)
    decision, reason = authz.decide(evidence, ALLOW_POLICY)
    evidence["decision"], evidence["decision_reason"] = decision, reason
    budget = authz.build_budget(origin, "single", ALLOW_POLICY, evidence, None, decision == "allow")
    return (
        write_json(tmp_path / "evidence.json", evidence),
        write_json(tmp_path / "budget.json", budget),
    )


def test_fetch_snapshot_cross_origin_redirect_blocked(fetch_snapshot, authz, tmp_path, write_json):
    """same_origin_redirects_only: www サブドメインへの redirect も拒否し observation_gap 記録・本文非保存。"""
    url, origin = "https://example.com/", "https://example.com"
    ev_path, bg_path = _fetch_inputs(authz, tmp_path, write_json, url, origin)
    fixtures = write_json(tmp_path / "fx.json", {
        url: {"status": 301, "headers": {"location": "https://www.example.com/"}, "body": ""},
        "https://www.example.com/": {"status": 200, "headers": {"content-type": "text/html"},
                                     "body": "<html>cross-origin body</html>"},
    })
    out_dir = tmp_path / "out"
    rc, result = fetch_snapshot.run([
        "--url", url, "--out-dir", str(out_dir), "--authz-evidence", str(ev_path),
        "--request-budget", str(bg_path), "--no-assets", "--fixture-map", str(fixtures),
    ])
    assert rc == 1 and result["snapshot_count"] == 0 and result["observation_gap_count"] == 1
    assert "cross-origin-redirect-blocked" in result["primary_failed"]
    index = json.loads((out_dir / "snapshot-index.json").read_text())
    gap = index["observation_gaps"][0]
    assert gap["reason"] == "cross-origin-redirect-blocked"
    assert gap["redirect_origin"] == "https://www.example.com"
    assert gap["body_saved"] is False
    assert not (out_dir / "bodies").exists()  # 別 origin の応答本文はディスクに残らない


def test_fetch_snapshot_same_origin_redirect_followed(fetch_snapshot, authz, tmp_path, write_json):
    """同一 origin redirect は従来どおり追従し snapshot が保存される。"""
    url, origin = "https://example.com/", "https://example.com"
    ev_path, bg_path = _fetch_inputs(authz, tmp_path, write_json, url, origin)
    fixtures = write_json(tmp_path / "fx.json", {
        url: {"status": 302, "headers": {"location": "/home"}, "body": ""},
        "https://example.com/home": {"status": 200, "headers": {"content-type": "text/html"},
                                     "body": "<html>home</html>"},
    })
    out_dir = tmp_path / "out"
    rc, result = fetch_snapshot.run([
        "--url", url, "--out-dir", str(out_dir), "--authz-evidence", str(ev_path),
        "--request-budget", str(bg_path), "--no-assets", "--fixture-map", str(fixtures),
    ])
    assert rc == 0 and result["snapshot_count"] == 1 and result["observation_gap_count"] == 0
    index = json.loads((out_dir / "snapshot-index.json").read_text())
    snap = index["snapshots"][0]
    assert snap["url"] == url and snap["final_url"] == "https://example.com/home"
    assert (out_dir / "bodies").exists()


def test_fetch_snapshot_redirect_handler_enforces_same_origin(fetch_snapshot):
    """RealFetcher が組み込む urllib handler 層でも cross-origin redirect を追従前に拒否する。"""
    handler = fetch_snapshot._SameOriginRedirectHandler("https://example.com")
    req = urllib.request.Request("https://example.com/")
    headers = email.message_from_string("")
    with pytest.raises(fetch_snapshot.CrossOriginRedirect) as exc_info:
        handler.redirect_request(req, None, 301, "Moved Permanently", headers, "https://www.example.com/")
    assert exc_info.value.target_origin == "https://www.example.com"
    followed = handler.redirect_request(req, None, 302, "Found", headers, "https://example.com/next")
    assert followed is not None and followed.full_url == "https://example.com/next"
