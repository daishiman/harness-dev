"""check-downstream-harness.py の機能テスト (下流ハーネス layer B・C10/C11)。

各 phase の ## 完了チェックリスト に ### 受入例 / ### 事前解決済み判断 サブ節を強制する。
gate 系 phase (P03/P07/P09/P10) は縮小要件 (見出し存在のみ)、他 phase はフル要件 (見出し+本文)。
"""
from __future__ import annotations


def _phase(phase_id: str, checklist_body: str) -> str:
    return (
        f"---\nid: {phase_id}\nphase_number: 1\n---\n"
        f"# {phase_id} — sample\n\n## 完了チェックリスト\n{checklist_body}\n\n## 参照情報\n- x\n"
    )


_FULL_OK = (
    "- [ ] 項目A。\n\n"
    "### 受入例 (満たす例 / 満たさない例)\n- 満たす例: X。\n- 満たさない例: Y。\n\n"
    "### 事前解決済み判断\n- 分岐点: Z → 判断: W。\n"
)


# ─────────────────── check_phase_downstream (単体) ───────────────────
def test_full_requirement_phase_passes(downstream):
    assert downstream.check_phase_downstream(_phase("P01", _FULL_OK), "P01") == []


def test_full_requirement_empty_acceptance_body_fails(downstream):
    """フル要件 phase で受入例見出し直下が空だと非空本文欠落で弾く。"""
    text = _phase("P01", "- [ ] A。\n\n### 受入例\n\n### 事前解決済み判断\n- 分岐: A→B。\n")
    errs = downstream.check_phase_downstream(text, "P01")
    assert any("受入例" in e and "非空本文" in e for e in errs)


def test_reduced_requirement_phase_allows_headings_only(downstream):
    """gate 系 phase (P03) は見出しのみで通る (本文空でも縮小要件で許容)。"""
    text = _phase("P03", "- [ ] 判定記録。\n\n### 受入例\n\n### 事前解決済み判断\n")
    assert downstream.check_phase_downstream(text, "P03") == []


def test_reduced_phases_constant(downstream):
    assert downstream.REDUCED_REQUIREMENT_PHASES == ("P03", "P07", "P09", "P10")


def test_missing_acceptance_subheading_detected(downstream):
    text = _phase("P01", "- [ ] 項目のみ。\n\n### 事前解決済み判断\n- 分岐: A→B。\n")
    errs = downstream.check_phase_downstream(text, "P01")
    assert any("受入例" in e and "サブ節が無い" in e for e in errs)


def test_missing_resolved_subheading_detected(downstream):
    text = _phase("P01", "- [ ] 項目のみ。\n\n### 受入例\n- 満たす例: X。\n")
    errs = downstream.check_phase_downstream(text, "P01")
    assert any("事前解決済み判断" in e and "サブ節が無い" in e for e in errs)


def test_missing_checklist_section_detected(downstream):
    text = "---\nid: P01\n---\n# P01\n\n## 目的\nx\n"
    errs = downstream.check_phase_downstream(text, "P01")
    assert any("下流ハーネス検査不能" in e for e in errs)


def test_acceptance_heading_prefix_match(downstream):
    """`### 受入例 (満たす例 / 満たさない例)` の付記付き見出しも prefix で受理される。"""
    text = _phase("P01", (
        "- [ ] A。\n\n### 受入例 (満たす例 / 満たさない例)\n- 満たす例: X。\n\n"
        "### 事前解決済み判断\n- 分岐: A→B。\n"
    ))
    assert downstream.check_phase_downstream(text, "P01") == []


def test_annotated_h2_heading_accepted(downstream):
    """親 H2 `## 完了チェックリスト (gate 合否)` の付記も prefix 境界で受理する (親子照合の整合)。"""
    text = (
        "---\nid: P01\nphase_number: 1\n---\n# P01\n\n"
        "## 完了チェックリスト (gate 合否)\n" + _FULL_OK + "\n\n## 参照情報\n- x\n"
    )
    assert downstream.check_phase_downstream(text, "P01") == []


def test_acceptance_overmatch_rejected(downstream):
    """`### 受入例外の扱い` (受入例外) は `### 受入例` として偽充足しない (過剰一致回避)。"""
    text = _phase("P01", (
        "- [ ] A。\n\n### 受入例外の扱い\n- 例外時の挙動。\n\n"
        "### 事前解決済み判断\n- 分岐: A→B。\n"
    ))
    errs = downstream.check_phase_downstream(text, "P01")
    assert any("受入例" in e and "サブ節が無い" in e for e in errs)


def test_na_phase_exempted_by_run(tmp_path, downstream):
    """applicability.applicable:false の N/A phase はサブ節要件を免除する (detect-unassigned と対称)。"""
    na = (
        "---\nid: P09\nphase_number: 9\napplicability:\n  applicable: false\n  reason: skill-only で該当なし\n---\n"
        "# P09\n\n## 目的\n該当なし。\n"  # 完了チェックリストもサブ節も無い
    )
    (tmp_path / "phase-09-quality-assurance.md").write_text(na, encoding="utf-8")
    (tmp_path / "phase-01-requirements.md").write_text(_phase("P01", _FULL_OK), encoding="utf-8")
    code, errs = downstream.run(tmp_path)
    assert code == 0, errs  # N/A phase は虚偽 violation を出さない


# ─────────────────── run / main 統合 ───────────────────
def test_run_clean_plan(tmp_path, downstream):
    (tmp_path / "phase-01-requirements.md").write_text(_phase("P01", _FULL_OK), encoding="utf-8")
    (tmp_path / "phase-03-design-review.md").write_text(
        _phase("P03", "- [ ] 判定。\n\n### 受入例\n\n### 事前解決済み判断\n"), encoding="utf-8")
    code, errs = downstream.run(tmp_path)
    assert code == 0, errs


def test_run_detects_violation(tmp_path, downstream):
    (tmp_path / "phase-01-requirements.md").write_text(
        _phase("P01", "- [ ] 項目のみ。\n"), encoding="utf-8")
    code, errs = downstream.run(tmp_path)
    assert code == 1
    assert any("P01" in e for e in errs)


def test_run_no_phase_files_is_usage_error(tmp_path, downstream):
    code, errs = downstream.run(tmp_path)
    assert code == 2


def test_self_test_passes(downstream):
    code, msgs = downstream._self_test()
    assert code == 0, msgs


def test_main_self_test(downstream, capsys):
    assert downstream.main(["--self-test"]) == 0
    assert "C10/C11" in capsys.readouterr().out


def test_main_clean(tmp_path, downstream, capsys):
    (tmp_path / "phase-01-requirements.md").write_text(_phase("P01", _FULL_OK), encoding="utf-8")
    assert downstream.main([str(tmp_path)]) == 0
    assert "OK" in capsys.readouterr().out


def test_main_violation(tmp_path, downstream):
    (tmp_path / "phase-01-requirements.md").write_text(
        _phase("P01", "- [ ] 項目のみ。\n"), encoding="utf-8")
    assert downstream.main([str(tmp_path)]) == 1


def test_main_no_plan_dir(downstream):
    assert downstream.main([]) == 2


def test_main_not_a_dir(tmp_path, downstream):
    f = tmp_path / "x.txt"
    f.write_text("x", encoding="utf-8")
    assert downstream.main([str(f)]) == 2
