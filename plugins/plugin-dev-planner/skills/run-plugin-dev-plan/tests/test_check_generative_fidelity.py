"""check-generative-fidelity.py の機能テスト (生成時品質 layer A・C6/C7)。

(C6) 曖昧語 denylist の部分一致検出 + 自己言及/反例/コード span の ignored_context 分類。
(C7) skeleton プレースホルダ (_PHASE_SECTION_HINT) の未カスタマイズ完全一致検出。
"""
from __future__ import annotations

import json

import specfm as _specfm  # scripts が sys.path 済 (conftest)
from conftest import component_entry, write_inventory, write_phase_spec


# ─────────────────── C6: detect_ambiguous_vocab / classify (単体) ───────────────────
def test_detect_ambiguous_vocab_hits(genfidelity):
    assert "適切に" in genfidelity.detect_ambiguous_vocab("これを適切に処理する")
    # 複数語・出現順
    hits = genfidelity.detect_ambiguous_vocab("必要に応じて柔軟に対応する")
    assert "必要に応じて" in hits and "柔軟に" in hits


def test_detect_ambiguous_vocab_no_false_positive(genfidelity):
    assert genfidelity.detect_ambiguous_vocab("関数 foo を呼び exit0 を返す") == []


def test_negation_prefix_not_flagged(genfidelity):
    """否定接頭辞『不』直前のみの出現 (不適切に/不十分に) は曖昧語と見なさない (誤検出回避)。"""
    assert genfidelity.detect_ambiguous_vocab("不適切に扱わないこと") == []
    assert genfidelity.detect_ambiguous_vocab("テストが不十分にならないよう網羅する") == []
    # 「不」直前でない出現が混在すれば該当する
    assert "適切に" in genfidelity.detect_ambiguous_vocab("不適切な例だが適切に直す")


def test_negative_condition_clause_not_swallowed(genfidelity):
    """通常の『満たさない場合』条件文は ignored でなく violation として検出する (見逃し回避)。

    否定例マーカーは『満たさない例』に限定し、裸の『満たさない』で genuine 違反を握り潰さない。
    """
    assert genfidelity.classify_denylist_context(
        "## 完了チェックリスト", "要件を満たさない場合は適切にリトライする") == "violation"


def test_scan_plan_negative_condition_clause_detected(genfidelity, tmp_path):
    text = (
        "---\nid: P05\n---\n# P05\n\n"
        "## 完了チェックリスト\n- [ ] 要件を満たさない場合は適切にリトライする。\n"
    )
    (tmp_path / "phase-05-implementation.md").write_text(text, encoding="utf-8")
    code, result = genfidelity.run(tmp_path)
    assert code == 1
    assert any(v["word"] == "適切に" for v in result["denylist_violations"])


def test_scan_plan_non_utf8_phase_is_failsoft(genfidelity, tmp_path):
    """非 UTF-8 の phase ファイルは crash せず fail-soft でスキップする。"""
    (tmp_path / "phase-05-implementation.md").write_bytes(b"\xff\xfe invalid")
    code, result = genfidelity.run(tmp_path)  # 例外を投げない
    assert code == 0
    assert result["denylist_violations"] == []


def test_classify_negative_example_is_ignored(genfidelity):
    assert genfidelity.classify_denylist_context(
        "## 完了チェックリスト", "満たさない例: 適切に実装する") == "ignored_context"


def test_classify_denylist_definition_is_ignored(genfidelity):
    assert genfidelity.classify_denylist_context(
        "## 目的", 'AMBIGUOUS_VOCAB_DENYLIST = ("適切に",)') == "ignored_context"


def test_classify_prose_is_violation(genfidelity):
    assert genfidelity.classify_denylist_context("## 目的", "これを適切に処理する") == "violation"


# ─────────────────── C7: detect_uncustomized_sections (単体) ───────────────────
def test_uncustomized_section_hint_match_detected(genfidelity):
    hint = _specfm._PHASE_SECTION_HINT["## 目的"]
    assert "## 目的" in genfidelity.detect_uncustomized_sections({"## 目的": hint})


def test_customized_section_not_flagged(genfidelity):
    hint = _specfm._PHASE_SECTION_HINT["## 目的"]
    assert genfidelity.detect_uncustomized_sections({"## 目的": hint + " 実ドメイン目的"}) == []


def test_all_hints_detected_as_uncustomized(genfidelity):
    """全 8 節が hint のままなら全節が未カスタマイズとして列挙される。"""
    body = dict(_specfm._PHASE_SECTION_HINT)
    assert set(genfidelity.detect_uncustomized_sections(body)) == set(_specfm._PHASE_SECTION_HINT)


# ─────────────────── parse_phase_body ───────────────────
def test_parse_phase_body_splits_h2_only(genfidelity):
    text = (
        "---\nid: P05\n---\n"
        "# P05 — 実装 (impl)\n\n"
        "## 目的\n本文A\n\n"
        "## 背景\n本文B\n### サブ\nサブ本文\n"
    )
    body = genfidelity.parse_phase_body(text)
    assert body["## 目的"] == "本文A"
    assert "### サブ" not in body  # H3 は節境界にならない
    assert "サブ本文" in body["## 背景"]  # H3 本文は親 H2 へ内包


# ─────────────────── scan_plan 統合 ───────────────────
def test_scan_plan_clean(tmp_path, genfidelity):
    """write_phase_spec の本文 (プレースホルダ 'x') は hint と一致せず denylist も無く 0 件。"""
    write_phase_spec(tmp_path, 5)
    code, result = genfidelity.run(tmp_path)
    assert code == 0, result
    assert result["denylist_violations"] == []
    assert result["uncustomized_sections"] == []


def test_scan_plan_detects_uncustomized(tmp_path, genfidelity):
    """render_minimal_phase (全節 hint) を書くと全 8 節が uncustomized として検出される。"""
    (tmp_path / "phase-05-implementation.md").write_text(
        _specfm.render_minimal_phase(5), encoding="utf-8")
    code, result = genfidelity.run(tmp_path)
    assert code == 1
    assert len(result["uncustomized_sections"]) == len(_specfm._PHASE_SECTION_HINT)


def test_scan_plan_detects_denylist_violation(tmp_path, genfidelity):
    """phase 本文 prose の denylist 語は violation として検出され exit1。"""
    text = (
        "---\nid: P05\n---\n# P05\n\n"
        "## 目的\nこのフェーズは適切に処理を行い品質を高める。\n"
    )
    (tmp_path / "phase-05-implementation.md").write_text(text, encoding="utf-8")
    code, result = genfidelity.run(tmp_path)
    assert code == 1
    words = {v["word"] for v in result["denylist_violations"]}
    assert "適切に" in words and "品質を高める" in words


def test_scan_plan_ignores_negative_example(tmp_path, genfidelity):
    """『満たさない例』配下の denylist 語は ignored_context (exit に影響しない)。"""
    text = (
        "---\nid: P05\n---\n# P05\n\n"
        "## 完了チェックリスト\n- 満たさない例: 適切に実装する、で完了扱いにしない。\n"
    )
    (tmp_path / "phase-05-implementation.md").write_text(text, encoding="utf-8")
    code, result = genfidelity.run(tmp_path)
    assert code == 0
    assert result["denylist_violations"] == []
    assert any(e["word"] == "適切に" for e in result["ignored_context"])


def test_scan_plan_ignores_code_span(tmp_path, genfidelity):
    """バッククォート span 内の denylist 語 (コード/定数名) は違反にならない。"""
    text = (
        "---\nid: P05\n---\n# P05\n\n"
        "## 背景\n定数 `適切に` は識別子であり prose ではない。\n"
    )
    (tmp_path / "phase-05-implementation.md").write_text(text, encoding="utf-8")
    code, result = genfidelity.run(tmp_path)
    assert code == 0
    assert result["denylist_violations"] == []


def test_scan_inventory_prose_denylist(tmp_path, genfidelity):
    """inventory の goal/criterion 文字列の denylist 語も検出対象。"""
    comp = component_entry("C01", "skill", overrides={"goal": "必要に応じて機能を追加する"})
    write_inventory(tmp_path, [comp])
    code, result = genfidelity.run(tmp_path)
    assert code == 1
    assert any(v.get("component") == "C01" and v["word"] == "必要に応じて"
               for v in result["denylist_violations"])


# ─────────────────── self-test / main ───────────────────
def test_self_test_passes(genfidelity):
    code, msgs = genfidelity._self_test()
    assert code == 0, msgs


def test_main_self_test(genfidelity, capsys):
    assert genfidelity.main(["--self-test"]) == 0
    assert "C6/C7" in capsys.readouterr().out


def test_main_clean_plan(tmp_path, genfidelity, capsys):
    write_phase_spec(tmp_path, 5)
    assert genfidelity.main([str(tmp_path)]) == 0
    out = capsys.readouterr().out
    assert json.loads(out)["denylist_violations"] == []


def test_main_no_plan_dir(genfidelity):
    assert genfidelity.main([]) == 2


def test_main_not_a_dir(tmp_path, genfidelity):
    f = tmp_path / "x.txt"
    f.write_text("x", encoding="utf-8")
    assert genfidelity.main([str(f)]) == 2
