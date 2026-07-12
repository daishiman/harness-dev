from __future__ import annotations

# /// script
# name: test-extract-system-blueprint-doc-emit
# purpose: C11 doc-emit の strict blueprint・redaction・screen・apply・生成物 CLI 契約を検証する
# inputs:
#   - C11 module / strict extraction and ledger fixtures
# outputs:
#   - pytest assertions and generated-contract evidence
# contexts: [C, E]
# network: false
# write-scope: pytest tmp_path only
# dependencies: [pytest, jsonschema]
# ///

import json


def extraction_fixture():
    diagrams = {
        "system_overview": "%% blueprint-diagram: system-architecture\nflowchart LR\nA[Web] --> B[API]",
        "fact_inference_layers": "%% blueprint-diagram: fact-inference-layers\nflowchart TB\nA[Fact] --> B[Inference]",
        "screen_flow": "%% blueprint-diagram: screen-flow\nstateDiagram-v2\n[*] --> Home",
        "data_flow_sequence": "sequenceDiagram\nUser->>API: GET\nAPI-->>User: 200",
        "data_model": "erDiagram\nUSER ||--o{ ORDER : places",
    }
    gap = {"kind": "observation_gap", "observation_status": "not_observed", "reason": "fixture unavailable"}
    confidence = {"level": "medium", "rationale": "fixture evidence"}

    def inference(claim):
        return {"kind": "inference", "claim": claim, "evidence_refs": ["hero"], "confidence": confidence}

    return {
        "metadata": {
            "canonical_url": "https://example.com/",
            "observation_snapshot_id": "snap-1",
            "schema_version": "1.0.0",
            "target_name": "Fixture",
            "document_brand": {
                "theme_color_meta": "#112233",
                "favicon_dominant_colors": ["#112233"],
                "root_background": "#ffffff",
                "color_scheme_support": ["light"],
            },
            "prompt_contract": {
                "names_must_appear_in_prompt": True,
                "required_sections": [
                    "Observations", "Lens — Fixture Expert", "Cross-lens conflicts",
                    "Neutral synthesis", "Confidence and gaps",
                ],
                "guard_rules": ["Do not invent observations"],
            },
        },
        "source": {"canonical_url": "https://example.com/"},
        "snapshot": {"observation_snapshot_id": "snap-1"},
        "schema_version": "1.0.0",
        "essence": {
            "core_problem_jtbd": inference("core problem"),
            "target_audience": inference("target audience"),
            "value_proposition": inference("value proposition"),
            "key_messages": inference("key messages"),
            "tone_voice": inference("tone"),
            "positioning_differentiation": inference("positioning"),
        },
        "mermaid_refs": list(diagrams),
        "content": {
            "per_screen_verbatim_copy": {"home": "person@example.com"},
            "headings_outline": ["Fixture"],
            "cta_inventory": ["Start"],
            "meta_seo_og": {},
            "structured_data": [],
            "locales": ["en"],
        },
        "tech_stack": {
            "signals": {
                "meta_generator": None, "response_headers": {}, "bundle_script_src_paths": [],
                "third_party_request_domains": [], "cookie_names": [],
            },
            "identified": [],
        },
        "nonfunctional_baseline": {
            "transfer_bytes_by_type": {"document": 100}, "request_count": 1,
            "cache_policy": "fixture", "compression": "none", "image_formats": ["png"],
            "security_headers": {"csp": "default-src 'self'"},
            "observed_scope": "single fixture visit",
        },
        "feature_map": {"per_screen_affordances": [{"screen_ref": "home", "ctas": ["Start"]}]},
        "user_journeys": [{
            "task": "start", "steps": [{"screen_ref": "home", "action": "select Start"}],
            "evidence_refs": ["hero"], "confidence": confidence,
        }],
        "security_design": {
            "auth_method": inference("unknown auth"), "session_mgmt": inference("cookie session"),
            "csrf_xss": inference("standard controls"), "csp_eval": inference("restrictive CSP"),
            "attack_surface": inference("public form"), "adopt_avoid_practices": inference("adopt CSP"),
        },
        "delivery_topology": {
            "cdn_edge_origin": "edge front",
            "rendering": "static",
            "cache_tiers": "browser and edge cache",
            "evidence_refs": ["hero"],
            "confidence": confidence,
        },
        "cwv_field_sample": {
            "lcp": {"value_ms": 1800}, "cls": {"value": 0.02},
            "inp": {"value_ms": 100}, "ttfb": {"value_ms": 250},
            "scope_note": "single fixture visit",
        },
        "compliance_surfaces": {
            "privacy_policy": {
                "present": True, "url": "https://example.com/privacy", "structure_summary": "policy sections",
            },
            "terms": {
                "present": True, "url": "https://example.com/terms", "structure_summary": "terms sections",
            },
            "tokushoho": {
                "present": True, "url": "https://example.com/tokushoho", "structure_summary": "seller disclosures",
            },
            "cookie_banner_cmp": {"present": True, "url": "https://example.com/cookies", "structure_summary": "accept/reject"},
        },
        "screens": [{
            "screen_id": "home",
            "source_url": "https://example.com/",
            "observation_status": "observed",
            "captured_at": "2026-01-01T00:00:00Z",
            "viewport": {
                "width": 800, "height": 600, "dpr": 1, "scroll_x": 0, "scroll_y": 0,
                "color_scheme": "light", "reduced_motion": False, "locale": "en",
            },
            "coverage": {
                "screen_regions_total": 1, "regions_extracted": 1,
                "elements_targeted": 1, "elements_extracted": 1, "fields_not_observed": 9,
            },
            "screenshot_ref": "screens/home.png",
            "annotated_screenshot_ref": "screens/home-annotated.png",
            "layout_overlay_ref": "overlays/home.layout-overlay.svg",
            "visual_formation_tree": {
                "element_id": "hero",
                "reading_order": 1,
                "identity": {"element_id": "hero", "role": "heading person@example.com"},
                "geometry": {"observation_status": "observed", "bounding_box_px": [10, 20, 300, 100]},
                "layout": {"observation_status": "observed", "display": "block"},
                "paint": {"observation_status": "observed", "foreground_color": "#112233"},
                "typography": dict(gap), "media": dict(gap), "effects": dict(gap),
                "pseudo_elements": dict(gap), "state": dict(gap), "motion": dict(gap),
                "responsive": dict(gap), "a11y": dict(gap), "tokens": dict(gap),
            },
        }],
        "design_tokens": {
            "palette": [{
                "role": "foreground", "value": "#112233", "canonical_hex8": "#112233ff",
                "gamut": "srgb", "usage_count": 1,
            }],
            "type_scale": [12, 16], "spacing_scale": [4, 8], "radius_scale": [4],
            "shadow_elevation_scale": [1], "breakpoints": [800], "z_layers": [1],
            "theme_variants": [{"theme": "light"}],
        },
        "site_inventory": {
            "crawl_mode": "single",
            "discovered_urls": ["https://example.com/"],
            "in_scope": ["https://example.com/"],
            "extracted": ["https://example.com/"],
            "excluded": [],
            "coverage": {"discovered": 1, "extracted": 1, "pending": 0, "excluded": 0},
            "layout_template_dedup": {"unique_templates": 1, "screenshots_saved": 0},
        },
        "request_ledger": {},
    }


def test_doc_emit_cli_and_generated_contract(doc_emit, tmp_path, write_json, capsys):
    out = tmp_path / "out"
    (out / "screens").mkdir(parents=True)
    (out / "screens" / "home.png").write_bytes(b"png")
    (out / "screens" / "home-annotated.png").write_bytes(b"annotated")
    extraction = write_json(tmp_path / "extraction.json", extraction_fixture())
    ledger = write_json(tmp_path / "ledger.json", {"https://example.com": {"requests": 1}})

    rc = doc_emit.main([
        "--extraction", str(extraction), "--out-dir", str(out),
        "--request-ledger", str(ledger),
    ])
    result = json.loads(capsys.readouterr().out)
    assert rc == 0 and result["status"] == "ok"
    # 外部公開 sink は持たず、ローカル成果物のみ (local_draft) を出す。
    assert "notion" not in json.dumps(result)
    assert all((out / name).is_file() for name in doc_emit.CHAPTERS)
    blueprint = json.loads((out / "blueprint.json").read_text())
    assert "person@example.com" not in json.dumps(blueprint["content"])
    layout = json.loads((out / "layout" / "home.layout.json").read_text())
    assert "person@example.com" not in json.dumps(layout)
    assert blueprint["request_ledger"] == {"https://example.com": {"requests": 1}}
    sink_status = json.loads((out / "sink-status.json").read_text())
    assert set(sink_status["sinks"]) == {"local_draft"}

    assert doc_emit.main(["--check-screens", "--extraction", str(out / "blueprint.json"), "--out-dir", str(out)]) == 0
    assert json.loads(capsys.readouterr().out)["status"] == "pass"


def test_doc_emit_empty_screens_is_normal(doc_emit, tmp_path, write_json, capsys):
    """browser 不使用の既定: screens[] 空 (screenshot は observation_gap) でも emit/check が通る。"""
    out = tmp_path / "out"
    out.mkdir()
    fixture = extraction_fixture()
    fixture["screens"] = []
    extraction = write_json(tmp_path / "extraction.json", fixture)
    ledger = write_json(tmp_path / "ledger.json", {"https://example.com": {"requests": 1}})
    rc = doc_emit.main(["--extraction", str(extraction), "--out-dir", str(out), "--request-ledger", str(ledger)])
    assert rc == 0 and json.loads(capsys.readouterr().out)["status"] == "ok"
    # 空 screens[] は screenshot completeness violation を出さない (browser 不使用の正常状態)
    assert doc_emit.main(["--check-screens", "--extraction", str(out / "blueprint.json"), "--out-dir", str(out)]) == 0
    assert json.loads(capsys.readouterr().out)["status"] == "pass"


def test_doc_emit_apply_gate_and_failure_paths(doc_emit, tmp_path, write_json, capsys):
    blueprint = write_json(tmp_path / "blueprint.json", {"anchors": ["hero"]})
    valid = write_json(tmp_path / "valid.json", [{
        "kind": "inference", "category": "adopt", "claim": "Use it",
        "own_context_ref": "our-system", "confidence": {"level": "high", "rationale": "observed"},
        "evidence_refs": ["hero"],
    }])
    assert doc_emit.main(["--check-apply", str(valid), "--blueprint", str(blueprint)]) == 0
    capsys.readouterr()
    invalid = write_json(tmp_path / "invalid.json", [{"kind": "fact", "category": "copy", "evidence_refs": ["missing"]}])
    assert doc_emit.main(["--check-apply", str(invalid), "--blueprint", str(blueprint)]) == 1
    assert "anchor 解決率" in capsys.readouterr().err
    assert doc_emit.main([]) == 2


def test_doc_emit_screen_violations(doc_emit, tmp_path):
    bad = extraction_fixture()
    bad["screens"][0]["visual_formation_tree"]["geometry"]["bounding_box_px"] = [-1, 0, 0, 2]
    bad["screens"][0]["visual_formation_tree"]["paint"]["foreground_color"] = "rgb(255, 0, 0)"
    bad["site_inventory"]["coverage"]["pending"] = 1
    violations = doc_emit.check_screens(bad, tmp_path)
    assert any("座標範囲が不正" in v for v in violations)
    assert any("palette 孤児" in v for v in violations)
    assert any("coverage 算術不整合" in v for v in violations)


def test_doc_emit_nonvisual_helper_failure_branches(doc_emit):
    assert doc_emit._present_or_gap({
        "kind": "observation_gap", "observation_status": "not_observed", "reason": "not captured",
    })
    assert not doc_emit._present_or_gap("  ")

    confidence_violations = doc_emit._check_confidence_and_refs({
        "kind": "fact", "lane": "fact", "evidence_refs": ["only-one"],
        "confidence": {"level": "high", "rationale": "observed"},
    }, "sample")
    assert any("inference lane" in item for item in confidence_violations)
    assert any("inference 必須" in item for item in confidence_violations)
    assert any("2件以上" in item for item in confidence_violations)
    assert any("evidence_refs" in item for item in doc_emit._check_confidence_and_refs({}, "empty"))
    assert any("rationale" in item for item in doc_emit._check_confidence_and_refs({
        "evidence_refs": ["a"], "confidence": {"level": "medium", "rationale": ""},
    }, "empty-rationale"))

    fact_violations = doc_emit._check_fact_lane({
        "lane": "inference", "kind": "unexpected", "nested": [{"kind": "inference"}],
    }, "facts")
    assert any("inference が混入" in item for item in fact_violations)
    assert any("fact|observation_gap" in item for item in fact_violations)

    assert doc_emit._check_prompt_contract(None)
    prompt_violations = doc_emit._check_prompt_contract({"analyzer": {
        "names_must_appear_in_prompt": False,
        "required_sections": ["Observations"],
        "guard_rules": [],
    }})
    assert any("names_must_appear" in item for item in prompt_violations)
    assert any("欠落" in item for item in prompt_violations)
    assert any("実名 Lens" in item for item in prompt_violations)
    assert any("guard_rules" in item for item in prompt_violations)
    assert any("object でない" in item for item in doc_emit._check_prompt_contract({"analyzer": "bad"}))


def test_doc_emit_nonvisual_contract_aggregates_violations(doc_emit):
    broken = extraction_fixture()
    broken["metadata"].pop("document_brand")
    broken["metadata"]["prompt_contract"] = {}
    broken.pop("content")
    broken["tech_stack"] = {"signals": {}, "identified": "not-a-list"}
    broken["user_journeys"] = ["not-an-object"]
    broken["essence"].pop("target_audience")
    broken["nonfunctional_baseline"].pop("observed_scope")

    violations = doc_emit.check_nonvisual_contract(broken)
    assert any("document_brand" in item for item in violations)
    assert any("prompt_contract" in item for item in violations)
    assert any("content 章" in item for item in violations)
    assert any("tech_stack.signals" in item for item in violations)
    assert any("user_journeys[0]" in item for item in violations)
    assert any("essence.target_audience" in item for item in violations)
    assert any("observed_scope" in item for item in violations)
    assert doc_emit.check_nonvisual_contract({}) == ["metadata が欠落/非object (chapter parity violation)"]


def test_doc_emit_color_tree_and_geometry_helpers(doc_emit):
    screen = {"layout": [{
        "identity": {"element_id": "parent", "parent_id": "root"},
        "reading_order": 2,
        "geometry": {"bounding_box_px": {"x": 1, "y": 2, "width": 3, "height": 4}},
        "children": [{
            "element_id": "child", "parent_id": "parent", "reading_order": 1,
            "geometry": {"bounding_box_px": [5, 6, 7, 8]},
        }],
    }, {"reading_order": 0}]}
    nodes = doc_emit._nodes(screen)
    assert [doc_emit._element_id(node) for node in nodes] == ["parent", "child"]
    assert doc_emit._parent_id(nodes[0]) == "root"
    assert doc_emit._parent_id(nodes[1]) == "parent"
    assert doc_emit._bbox(nodes[0]) == [1.0, 2.0, 3.0, 4.0]
    assert doc_emit._bbox(nodes[1]) == [5.0, 6.0, 7.0, 8.0]
    assert doc_emit._bbox({"bounding_box_px": ["bad", 0, 1, 2]}) is None
    assert doc_emit._bbox({}) is None
    assert [item["element_id"] for item in doc_emit._numbered_elements(screen)] == ["child", "parent"]

    assert doc_emit._canonical_color({"observation_status": "blocked"}) is None
    assert doc_emit._canonical_color({"value": "#abc"}) == "#aabbccff"
    assert doc_emit._canonical_color("#abcd") == "#aabbccdd"
    assert doc_emit._canonical_color("rgba(1, 2, 3, 50%)") == "#01020380"
    assert doc_emit._canonical_color("rgb(bad, 2, 3)") == "rgb(bad, 2, 3)"
    assert doc_emit._canonical_color("transparent") is None
    assert doc_emit._canonical_color(1) is None

    observed = doc_emit._observed_colors({
        "paint": {
            "foreground_color": "#abc",
            "border_width_style_color": {"color": "#123456"},
            "box_shadow": [{"color": "rgba(1, 2, 3, 0.5)"}],
            "text_shadow": {"color": "#0008"},
        },
        "typography": {"color": "red"},
    })
    assert {"#aabbccff", "#123456ff", "#01020380", "#00000088", "red"} <= observed
    palette = doc_emit._palette_tokens({
        "palette": ["#abc", {"value": "#123456"}],
        "theme_variants": [{"colors": ["#0008", {"canonical_hex8": "#01020380"}]}],
    })
    assert palette == {"#aabbccff", "#123456ff", "#00000088", "#01020380"}


def test_doc_emit_visual_envelope_failure_matrix(doc_emit):
    assert doc_emit._has_observed_payload(None) is False
    assert doc_emit._has_observed_payload("") is False
    assert doc_emit._has_observed_payload(1) is True
    assert doc_emit._has_observed_payload([]) is False
    assert doc_emit._has_observed_payload(object()) is True
    assert doc_emit._has_observed_payload({"reason": "gap only"}) is False
    assert doc_emit._has_observed_payload({"value": 1}) is True

    entries, malformed = doc_emit._visual_node_entries({
        "layout": [{"identity": {"element_id": "a"}, "children": "bad"}, 42],
    })
    assert len(entries) == 1
    assert len(malformed) == 2

    node = {"element_id": "matrix"}
    for category in doc_emit.VISUAL_FORMATION_CATEGORIES:
        node[category] = {"value": "observed"}
    node.pop("geometry")
    node["layout"] = {"kind": "fact", "observation_status": "not_observed", "reason": "blocked"}
    node["paint"] = {"observation_status": "not_observed", "reason": ""}
    node["typography"] = {"observation_status": "mystery"}
    node["media"] = {"kind": "observation_gap", "observation_status": "observed", "value": "x"}
    node["effects"] = {"observation_status": "observed"}
    violations = doc_emit._check_visual_formation_categories({"visual_formation_tree": node}, "matrix")
    assert any("無言欠落" in item and "geometry" in item for item in violations)
    assert any("kind が observation_gap" in item for item in violations)
    assert any("reason が無い" in item for item in violations)
    assert any("observed|not_observed|blocked" in item for item in violations)
    assert any("kind=observation_gap" in item for item in violations)
    assert any("observed 値" in item for item in violations)
