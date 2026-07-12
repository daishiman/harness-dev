"""Genuine functional tests for
plugins/skill-intake/scripts/dogfooding_regression.py

The script compares a generated intake.json against a baseline using a lexical
fingerprint + a SequenceMatcher-based semantic similarity over 5 keys. Pure
functions (_collect_semantic_texts / _extract_lexical_fingerprint /
_semantic_similarity / _compare) are imported and tested directly. The CLI modes
(--baseline-only / --schema-robustness / --multi-self / positional) are driven by
calling main() on the imported module with the module-level PROJECT_ROOT /
CONFIG_PATH monkeypatched to a tmp sandbox, and subprocess.call stubbed so the
real validate_intake_schema.py / network / disk outside tmp are never invoked.

No network, no Notion, no keychain, no secrets, repo untouched.
"""
import importlib.util
import json
import sys
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parents[2]
SCRIPT = REPO_ROOT / "plugins" / "skill-intake" / "scripts" / "dogfooding_regression.py"


def _load():
    spec = importlib.util.spec_from_file_location("dogfooding_regression_under_test", SCRIPT)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


MOD = _load()


# ── intake fixture builder ───────────────────────────────────────────────
def _intake(*, tp="目的の本文", motiv="動機の本文", axis_answer="軸の答え",
            fig_one="図の説明", slot="決めること") -> dict:
    return {
        "schema_version": "1.0",
        "sections": {
            "3_purpose_excavator": {
                "true_purpose": tp,
                "underlying_motivation": motiv,
                "purpose_slots": {
                    "decides_what": slot,
                    "ensures_what": "保証",
                    "prevents_what": "防止",
                },
            },
            "5_visualizer": {
                "figures": [
                    {"index": 1, "kind": "flow", "one_liner": fig_one},
                    {"index": 2, "kind": "matrix", "one_liner": "別の図"},
                ]
            },
            "6_five_axes_summary": {
                "axes": [
                    {"axis_id": "scope", "answer": axis_answer},
                    {"axis_id": "depth", "answer": "深さの答え"},
                ]
            },
        },
    }


# ── _collect_semantic_texts ──────────────────────────────────────────────
def test_collect_semantic_texts_all_keys():
    out = MOD._collect_semantic_texts(_intake())
    assert set(out.keys()) == set(MOD.SEMANTIC_KEYS)
    assert "決めること" in out["purpose_slots"]
    assert "保証" in out["purpose_slots"]
    assert out["axes.answer"].startswith("軸の答え")
    assert "図の説明" in out["figures.one_liner"]
    assert out["true_purpose"] == "目的の本文"
    assert out["underlying_motivation"] == "動機の本文"


def test_collect_semantic_texts_empty_and_non_string_robust():
    intake = {
        "sections": {
            "3_purpose_excavator": {"purpose_slots": {"decides_what": 123}},  # non-str ignored
            "5_visualizer": {"figures": [{"one_liner": None}]},
            "6_five_axes_summary": {"axes": [{"answer": 42}]},
        }
    }
    out = MOD._collect_semantic_texts(intake)
    # non-string values are filtered, never crash
    assert out["purpose_slots"] == ""
    assert out["figures.one_liner"] == ""
    assert out["axes.answer"] == ""
    assert out["true_purpose"] == ""


def test_collect_semantic_texts_missing_sections():
    out = MOD._collect_semantic_texts({})
    assert all(v == "" for v in out.values())


# ── _extract_lexical_fingerprint ─────────────────────────────────────────
def test_extract_lexical_fingerprint():
    fp = MOD._extract_lexical_fingerprint(_intake())
    assert fp["section_keys"] == sorted(
        ["3_purpose_excavator", "5_visualizer", "6_five_axes_summary"]
    )
    assert fp["axes_ids"] == ["depth", "scope"]
    assert fp["figures_kinds"] == [(1, "flow"), (2, "matrix")]


def test_extract_lexical_fingerprint_empty():
    fp = MOD._extract_lexical_fingerprint({})
    assert fp == {"section_keys": [], "axes_ids": [], "figures_kinds": []}


# ── _semantic_similarity ─────────────────────────────────────────────────
def test_semantic_similarity_identical():
    assert MOD._semantic_similarity("hello", "hello") == 1.0


def test_semantic_similarity_both_empty_is_one():
    # LS-04 fix: both missing means "no divergence" → 1.0
    assert MOD._semantic_similarity("", "") == 1.0


def test_semantic_similarity_one_empty_is_zero():
    assert MOD._semantic_similarity("x", "") == 0.0
    assert MOD._semantic_similarity("", "y") == 0.0


def test_semantic_similarity_partial():
    sim = MOD._semantic_similarity("abcdef", "abcxyz")
    assert 0.0 < sim < 1.0


def test_semantic_similarity_exception_returns_zero(monkeypatch):
    class Boom:
        def __init__(self, *a, **k):
            raise RuntimeError("boom")

    monkeypatch.setattr(MOD, "SequenceMatcher", Boom)
    assert MOD._semantic_similarity("a", "b") == 0.0


# ── _compare ─────────────────────────────────────────────────────────────
def test_compare_identical_pass():
    intake = _intake()
    ok, findings = MOD._compare(intake, intake, MOD.DEFAULT_THRESHOLD)
    assert ok is True and findings == []


def test_compare_lexical_divergence():
    base = _intake()
    gen = _intake()
    gen["sections"]["6_five_axes_summary"]["axes"][0]["axis_id"] = "different"
    ok, findings = MOD._compare(base, gen, MOD.DEFAULT_THRESHOLD)
    assert ok is False
    assert any("LEXICAL FAIL [axes_ids]" in f for f in findings)


def test_compare_semantic_divergence():
    base = _intake(tp="まったく同じではない長い目的の説明文章ABCDEF")
    gen = _intake(tp="完全に異なる別個の内容ZZZZZ無関係")
    ok, findings = MOD._compare(base, gen, MOD.DEFAULT_THRESHOLD)
    assert ok is False
    assert any("SEMANTIC FAIL [true_purpose]" in f for f in findings)


# ── sandbox helpers for CLI/main() ───────────────────────────────────────
def _sandbox(tmp_path, monkeypatch, *, fixture_rels, config_extra=None, write_fixtures=True):
    """Point the module's PROJECT_ROOT/CONFIG_PATH at tmp_path with given fixtures."""
    root = tmp_path
    cfg_dir = root / "plugins" / "skill-intake" / "references"
    cfg_dir.mkdir(parents=True)
    dog = {
        "baseline_intake_path": fixture_rels[0] if fixture_rels else "",
        "baseline_intake_paths": list(fixture_rels),
        "embedding_cosine_min": 0.85,
        "similarity_min": 0.85,
    }
    if config_extra:
        dog.update(config_extra)
    (cfg_dir / "runtime-config.json").write_text(
        json.dumps({"dogfooding": dog}), encoding="utf-8"
    )
    if write_fixtures:
        for rel in fixture_rels:
            fp = root / rel
            fp.parent.mkdir(parents=True, exist_ok=True)
            fp.write_text(json.dumps(_intake()), encoding="utf-8")
    monkeypatch.setattr(MOD, "PROJECT_ROOT", root)
    monkeypatch.setattr(MOD, "CONFIG_PATH", cfg_dir / "runtime-config.json")
    return root


# ── main(): --baseline-only ──────────────────────────────────────────────
def test_main_baseline_only_pass(tmp_path, monkeypatch):
    _sandbox(tmp_path, monkeypatch, fixture_rels=["fx/base.json"])
    assert MOD.main(["prog", "--baseline-only"]) == 0


def test_main_baseline_only_missing(tmp_path, monkeypatch):
    _sandbox(tmp_path, monkeypatch, fixture_rels=["fx/base.json"], write_fixtures=False)
    assert MOD.main(["prog", "--baseline-only"]) == 2


def test_main_baseline_only_invalid_json(tmp_path, monkeypatch):
    root = _sandbox(tmp_path, monkeypatch, fixture_rels=["fx/base.json"], write_fixtures=False)
    fp = root / "fx" / "base.json"
    fp.parent.mkdir(parents=True, exist_ok=True)
    fp.write_text("{broken", encoding="utf-8")
    assert MOD.main(["prog", "--baseline-only"]) == 1


# ── main(): positional generated.json regression ─────────────────────────
def test_main_positional_pass(tmp_path, monkeypatch):
    root = _sandbox(tmp_path, monkeypatch, fixture_rels=["fx/base.json"])
    gen = root / "gen.json"
    gen.write_text(json.dumps(_intake()), encoding="utf-8")  # identical → PASS
    assert MOD.main(["prog", str(gen)]) == 0


def test_main_positional_regression_fail(tmp_path, monkeypatch):
    root = _sandbox(tmp_path, monkeypatch, fixture_rels=["fx/base.json"])
    gen = root / "gen.json"
    diverged = _intake(tp="完全に違う目的XYZ無関係な内容")
    diverged["sections"]["6_five_axes_summary"]["axes"][0]["axis_id"] = "changed"
    gen.write_text(json.dumps(diverged), encoding="utf-8")
    assert MOD.main(["prog", str(gen)]) == 1


def test_main_positional_generated_missing(tmp_path, monkeypatch):
    _sandbox(tmp_path, monkeypatch, fixture_rels=["fx/base.json"])
    assert MOD.main(["prog", str(tmp_path / "nope.json")]) == 2


def test_main_positional_baseline_missing_returns_3(tmp_path, monkeypatch):
    root = _sandbox(tmp_path, monkeypatch, fixture_rels=["fx/base.json"], write_fixtures=False)
    gen = root / "gen.json"
    gen.write_text(json.dumps(_intake()), encoding="utf-8")
    assert MOD.main(["prog", str(gen)]) == 3


def test_main_no_args_usage_returns_2(tmp_path, monkeypatch):
    _sandbox(tmp_path, monkeypatch, fixture_rels=["fx/base.json"])
    assert MOD.main(["prog"]) == 2


# ── main(): --multi-self ─────────────────────────────────────────────────
def test_main_multi_self_pass(tmp_path, monkeypatch):
    _sandbox(tmp_path, monkeypatch, fixture_rels=["fx/a.json", "fx/b.json"])
    assert MOD.main(["prog", "--multi-self"]) == 0


def test_main_multi_self_no_paths_returns_2(tmp_path, monkeypatch):
    _sandbox(tmp_path, monkeypatch, fixture_rels=[], config_extra={"baseline_intake_paths": []})
    assert MOD.main(["prog", "--multi-self"]) == 2


def test_main_multi_self_missing_fixture_returns_1(tmp_path, monkeypatch):
    _sandbox(tmp_path, monkeypatch, fixture_rels=["fx/a.json", "fx/missing.json"],
             write_fixtures=False)
    # write only the first fixture; second missing → failed=1
    root = MOD.PROJECT_ROOT
    fp = root / "fx" / "a.json"
    fp.parent.mkdir(parents=True, exist_ok=True)
    fp.write_text(json.dumps(_intake()), encoding="utf-8")
    assert MOD.main(["prog", "--multi-self"]) == 1


def test_main_multi_self_reports_findings_on_regression(tmp_path, monkeypatch):
    # Force a self-compare failure to exercise the findings-printing branch.
    _sandbox(tmp_path, monkeypatch, fixture_rels=["fx/a.json"])
    monkeypatch.setattr(MOD, "_compare", lambda b, g, t: (False, ["SEMANTIC FAIL [x]: 0.1"]))
    assert MOD.main(["prog", "--multi-self"]) == 1


def test_main_multi_self_uses_similarity_min(tmp_path, monkeypatch):
    # similarity_min preferred over embedding_cosine_min; self-compare always 1.0
    _sandbox(tmp_path, monkeypatch, fixture_rels=["fx/a.json"],
             config_extra={"similarity_min": 0.99})
    assert MOD.main(["prog", "--multi-self"]) == 0


# ── main(): --schema-robustness (subprocess.call stubbed) ────────────────
def test_main_schema_robustness_all_pass(tmp_path, monkeypatch):
    _sandbox(tmp_path, monkeypatch, fixture_rels=["fx/a.json", "fx/b.json"])
    monkeypatch.setattr(MOD.subprocess if hasattr(MOD, "subprocess") else __import__("subprocess"),
                        "call", lambda *a, **k: 0, raising=False)
    # subprocess is imported lazily inside the function; patch the stdlib module
    import subprocess as _sp
    monkeypatch.setattr(_sp, "call", lambda *a, **k: 0)
    assert MOD.main(["prog", "--schema-robustness"]) == 0


def test_main_schema_robustness_validator_fails(tmp_path, monkeypatch):
    _sandbox(tmp_path, monkeypatch, fixture_rels=["fx/a.json"])
    import subprocess as _sp
    monkeypatch.setattr(_sp, "call", lambda *a, **k: 1)  # validator returns non-zero
    assert MOD.main(["prog", "--schema-robustness"]) == 1


def test_main_schema_robustness_missing_fixture(tmp_path, monkeypatch):
    _sandbox(tmp_path, monkeypatch, fixture_rels=["fx/a.json"], write_fixtures=False)
    import subprocess as _sp
    monkeypatch.setattr(_sp, "call", lambda *a, **k: 0)
    assert MOD.main(["prog", "--schema-robustness"]) == 1  # MISS → failed=1


def test_main_schema_robustness_none_path_is_skipped(tmp_path, monkeypatch):
    # baseline_intake_paths=[] falls back to [baseline_intake_path]; when that is
    # None the loop skips it (rel is None → continue) and returns 0 with 0 fixtures.
    _sandbox(tmp_path, monkeypatch, fixture_rels=[],
             config_extra={"baseline_intake_paths": [], "baseline_intake_path": None})
    import subprocess as _sp
    monkeypatch.setattr(_sp, "call", lambda *a, **k: 0)
    assert MOD.main(["prog", "--schema-robustness"]) == 0


# ── config helpers ───────────────────────────────────────────────────────
def test_load_config_and_resolve_baseline(tmp_path, monkeypatch):
    root = _sandbox(tmp_path, monkeypatch, fixture_rels=["fx/base.json"])
    cfg = MOD._load_config()
    assert cfg["dogfooding"]["baseline_intake_path"] == "fx/base.json"
    assert MOD._resolve_baseline_path(cfg) == (root / "fx/base.json")


# ── real repo config smoke (no subprocess for validator) ─────────────────
def test_real_baseline_only_against_repo():
    # Uses the genuine repo runtime-config + baseline fixture; pure JSON read.
    assert MOD.main(["prog", "--baseline-only"]) == 0
