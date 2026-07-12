"""detect-unassigned.py の機能テスト (per-phase 転換)。

(a) 13 phase ファイル (P01..P13) 全存在 + §5 section 床、(b) 各 inventory component が
>=1 phase の entities_covered に出現 (orphan 防止) + build_target 非空。
"""
from __future__ import annotations

import json

from conftest import component_entry, write_all_phases, write_phase_spec


def _inv_text(components) -> str:
    return json.dumps({"components": components}, ensure_ascii=False)


# ─────────────────── 純関数 ───────────────────
def test_load_inventory_components_object(unassigned):
    text = '{"components": [{"id": "C01", "build_target": "x"}, {"id": "C02", "build_target": "y"}]}'
    comps = unassigned.load_inventory_components(text)
    assert [c["id"] for c in comps] == ["C01", "C02"]


def test_load_inventory_components_non_object_forms(unassigned):
    assert unassigned.load_inventory_components('["C01", "C02"]') == []
    assert unassigned.load_inventory_components("- C01: skill\n- C02: hook") == []
    assert unassigned.load_inventory_components("   ") == []


def test_missing_sections(unassigned, specfm_mod):
    # 節集合は specfm.PHASE_BODY_SECTIONS を単一正本にする (SSOT 追従)。
    full = "".join(f"{sec}\n" for sec in specfm_mod.PHASE_BODY_SECTIONS)
    assert unassigned.missing_sections(full) == []
    # 先頭節のみを残す → それ以外は全欠落として報告される
    miss = unassigned.missing_sections(specfm_mod.PHASE_BODY_SECTIONS[0] + " only")
    for sec in specfm_mod.PHASE_BODY_SECTIONS[1:]:
        assert sec in miss


def test_empty_body_sections_all_nonempty(unassigned, specfm_mod):
    text = "".join(f"{sec}\n中身\n" for sec in specfm_mod.PHASE_BODY_SECTIONS)
    assert unassigned.empty_body_sections(text) == []


def test_empty_body_sections_detects_empty(unassigned, specfm_mod):
    secs = specfm_mod.PHASE_BODY_SECTIONS
    # 先頭節=空本文 (直後に次見出し)・末尾節=whitespace のみ=空・中間節=非空
    parts = [f"{secs[0]}\n"]
    for sec in secs[1:-1]:
        parts.append(f"{sec}\n中身\n")
    parts.append(f"{secs[-1]}\n   \n")
    miss = unassigned.empty_body_sections("".join(parts))
    assert secs[0] in miss and secs[-1] in miss
    assert secs[1] not in miss


def test_empty_body_sections_ignores_missing_heading(unassigned):
    assert unassigned.empty_body_sections("## 目的\nx\n") == []


def test_is_not_applicable(unassigned):
    assert unassigned.is_not_applicable({"applicability": {"applicable": False, "reason": "x"}}) is True
    assert unassigned.is_not_applicable({"applicability": {"applicable": True}}) is False
    assert unassigned.is_not_applicable({}) is False


def test_covered_entities(tmp_path, unassigned):
    write_all_phases(tmp_path, entities_by_phase={2: ["C01", "C02"], 5: ["C01"]})
    phase_files, errors = unassigned.collect_phase_files(tmp_path)
    assert errors == []
    covered = unassigned.covered_entities(phase_files)
    assert covered == {"C01", "C02"}


def test_collect_phase_files_skips_index(tmp_path, unassigned):
    write_phase_spec(tmp_path, 1)
    (tmp_path / "index.md").write_text("---\nid: IDX0\n---\nx", encoding="utf-8")
    files, errors = unassigned.collect_phase_files(tmp_path)
    assert errors == []
    assert "P01" in files and "IDX0" not in files


def test_expected_phase_filename(unassigned):
    assert unassigned.expected_phase_filename(3) == "phase-03-design-review.md"


# ─────────────────── run ───────────────────
def test_run_clean(tmp_path, unassigned):
    write_all_phases(tmp_path, entities_by_phase={2: ["C01", "C02"]})
    comps = [component_entry("C01", "skill"), component_entry("C02", "hook")]
    code, errs, warns = unassigned.run(_inv_text(comps), tmp_path)
    assert code == 0 and errs == [], errs


def test_run_missing_phase(tmp_path, unassigned):
    # P13 を書かず 12 phase のみ → phase 欠落
    for n in range(1, 13):
        write_phase_spec(tmp_path, n, entities_covered=["C01"] if n == 2 else [])
    code, errs, warns = unassigned.run(_inv_text([component_entry("C01", "skill")]), tmp_path)
    assert code == 1
    assert any("phase ファイル欠落: P13 (phase-13-release.md)" in e for e in errs)


def test_run_bad_phase_filename_fails(tmp_path, unassigned):
    write_all_phases(tmp_path, entities_by_phase={2: ["C01"]})
    good = tmp_path / "phase-03-design-review.md"
    bad = tmp_path / "phase-03-wrong.md"
    bad.write_text(good.read_text(encoding="utf-8"), encoding="utf-8")
    good.unlink()
    code, errs, warns = unassigned.run(_inv_text([component_entry("C01", "skill")]), tmp_path)
    assert code == 1
    assert any("phase ファイル名不一致" in e for e in errs)


def test_run_duplicate_phase_id_fails(tmp_path, unassigned):
    write_all_phases(tmp_path, entities_by_phase={2: ["C01"]})
    duplicate = tmp_path / "phase-03-copy.md"
    duplicate.write_text((tmp_path / "phase-03-design-review.md").read_text(encoding="utf-8"), encoding="utf-8")
    code, errs, warns = unassigned.run(_inv_text([component_entry("C01", "skill")]), tmp_path)
    assert code == 1
    assert any("phase id 重複: P03" in e for e in errs)


def test_run_missing_section(tmp_path, unassigned):
    write_all_phases(tmp_path, entities_by_phase={2: ["C01"]})
    write_phase_spec(tmp_path, 5, entities_covered=[], sections=False)  # section 欠落へ差し替え
    code, errs, warns = unassigned.run(_inv_text([component_entry("C01", "skill")]), tmp_path)
    assert code == 1
    assert any("必須 section 欠落" in e for e in errs)


def test_run_na_phase_section_exempt(tmp_path, unassigned):
    write_all_phases(tmp_path, entities_by_phase={2: ["C01"]})
    # P08 を applicable:false + section 無しへ → 床免除で clean
    write_phase_spec(tmp_path, 8, applicable=False, reason="該当リファクタ無し", sections=False)
    code, errs, warns = unassigned.run(_inv_text([component_entry("C01", "skill")]), tmp_path)
    assert code == 0 and errs == [], errs


def test_run_orphan_component(tmp_path, unassigned):
    write_all_phases(tmp_path, entities_by_phase={2: ["C01"]})  # C02 はどこにも出ない
    comps = [component_entry("C01", "skill"), component_entry("C02", "hook")]
    code, errs, warns = unassigned.run(_inv_text(comps), tmp_path)
    assert code == 1
    assert any("orphan component: C02" in e for e in errs)


def test_run_unknown_entities_covered_fails(tmp_path, unassigned):
    write_all_phases(tmp_path, entities_by_phase={2: ["C01", "C99"]})
    comps = [component_entry("C01", "skill")]
    code, errs, warns = unassigned.run(_inv_text(comps), tmp_path)
    assert code == 1
    assert any("unknown covered entity: C99" in e for e in errs)


def test_run_build_target_missing(tmp_path, unassigned):
    write_all_phases(tmp_path, entities_by_phase={2: ["C01"]})
    comps = [component_entry("C01", "skill", drop=["build_target"])]
    code, errs, warns = unassigned.run(_inv_text(comps), tmp_path)
    assert code == 1
    assert any("build_target 欠落" in e for e in errs)


def test_run_empty_inventory(tmp_path, unassigned):
    write_all_phases(tmp_path)
    code, errs, warns = unassigned.run("   ", tmp_path)
    assert code == 2


def test_run_extra_phase_warns(tmp_path, unassigned):
    write_all_phases(tmp_path, entities_by_phase={2: ["C01"]})
    # 想定外 id の phase ファイルを 1 つ足す (frontmatter id は P01..P13 外)
    (tmp_path / "phase-99-extra.md").write_text(
        "---\nid: P99extra\nphase_number: 99\n---\n## 目的\nx\n", encoding="utf-8"
    )
    code, errs, warns = unassigned.run(_inv_text([component_entry("C01", "skill")]), tmp_path)
    assert any("想定外の phase id" in w for w in warns)


# ─────────────────── main ───────────────────
def test_main_ok(tmp_path, unassigned, capsys):
    write_all_phases(tmp_path, entities_by_phase={2: ["C01"]})
    inv = tmp_path / "inv.json"
    inv.write_text(_inv_text([component_entry("C01", "skill")]), encoding="utf-8")
    assert unassigned.main(["--inventory", str(inv), "--specs-dir", str(tmp_path)]) == 0
    assert "OK" in capsys.readouterr().out


def test_main_violation(tmp_path, unassigned, capsys):
    write_all_phases(tmp_path, entities_by_phase={2: ["C01"]})  # C02 orphan
    inv = tmp_path / "inv.json"
    inv.write_text(_inv_text([component_entry("C01", "skill"), component_entry("C02", "hook")]), encoding="utf-8")
    assert unassigned.main(["--inventory", str(inv), "--specs-dir", str(tmp_path)]) == 1
    assert "orphan" in capsys.readouterr().err


def test_main_inventory_not_found(tmp_path, unassigned):
    assert unassigned.main(["--inventory", str(tmp_path / "nope.json"), "--specs-dir", str(tmp_path)]) == 2


def test_main_specs_dir_not_dir(tmp_path, unassigned):
    inv = tmp_path / "inv.json"
    inv.write_text(_inv_text([component_entry("C01", "skill")]), encoding="utf-8")
    assert unassigned.main(["--inventory", str(inv), "--specs-dir", str(tmp_path / "missing")]) == 2
