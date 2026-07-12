"""verify-index-topsort.py の機能テスト (per-phase 転換)。

(層1) index が `## フェーズ一覧` で P01..P13 を phase_number 昇順で全列挙する。
(層2) component-inventory.json の component 依存 DAG が非循環 (top-sort 可能)。
"""
from __future__ import annotations

from conftest import component_entry, write_inventory, write_phase_index


def _phase_list_body(ids) -> str:
    return "# index\n## フェーズ一覧\n\n" + "".join(f"{i + 1}. {pid} — phase\n" for i, pid in enumerate(ids))


def _all_ids(topsort):
    return topsort.expected_phase_ids()


# ─────────────────── 純関数 ───────────────────
def test_body_after_frontmatter_strips(topsort):
    assert topsort.body_after_frontmatter("---\nid: IDX0\n---\nbody P01").strip() == "body P01"
    assert topsort.body_after_frontmatter("no fm P01") == "no fm P01"


def test_expected_phase_ids(topsort):
    assert topsort.expected_phase_ids() == [f"P{n:02d}" for n in range(1, 14)]


def test_extract_phase_list_ids(topsort):
    ids, found = topsort.extract_phase_list_ids(_phase_list_body(["P01", "P02", "P03"]))
    assert ids == ["P01", "P02", "P03"] and found is True


def test_extract_phase_list_ids_no_section(topsort):
    ids, found = topsort.extract_phase_list_ids("# index\n## 別章\n- P01\n")
    assert found is False


def test_extract_ignores_ids_outside_section(topsort):
    body = "## フェーズ一覧\n1. P01 — x\n## 受入確認\nP05 に触れる散文\n"
    ids, found = topsort.extract_phase_list_ids(body)
    assert ids == ["P01"] and "P05" not in ids


def test_verify_phase_enumeration_clean(topsort):
    assert topsort.verify_phase_enumeration(_all_ids(topsort), True) == []


def test_verify_phase_enumeration_missing(topsort):
    ids = _all_ids(topsort)[:-1]  # P13 欠落
    errs = topsort.verify_phase_enumeration(ids, True)
    assert any("未列挙" in e for e in errs)


def test_verify_phase_enumeration_dup(topsort):
    ids = ["P01"] + _all_ids(topsort)
    errs = topsort.verify_phase_enumeration(ids, True)
    assert any("重複" in e for e in errs)


def test_verify_phase_enumeration_order(topsort):
    ids = _all_ids(topsort)
    ids[0], ids[1] = ids[1], ids[0]  # P02, P01, ...
    errs = topsort.verify_phase_enumeration(ids, True)
    assert any("昇順でない" in e for e in errs)


def test_verify_phase_enumeration_no_section(topsort):
    errs = topsort.verify_phase_enumeration([], False)
    assert any("section が無い" in e for e in errs)


# ─────────────────── index section 床 (層0) ───────────────────
def test_index_section_floor_clean(topsort, specfm_mod):
    body = "".join(f"{sec}\n中身\n" for sec in specfm_mod.INDEX_REQUIRED_SECTIONS)
    assert topsort.index_section_floor_errors(body) == []


def test_index_section_floor_detects_missing(topsort, specfm_mod):
    secs = specfm_mod.INDEX_REQUIRED_SECTIONS
    body = "".join(f"{sec}\n中身\n" for sec in secs[1:])  # 先頭節を欠落させる
    errs = topsort.index_section_floor_errors(body)
    assert any(secs[0] in e and "欠落" in e for e in errs)


def test_index_section_floor_detects_empty_body(topsort, specfm_mod):
    secs = specfm_mod.INDEX_REQUIRED_SECTIONS
    parts = [f"{secs[0]}\n"]  # 先頭: 空本文 (直後に次見出し)
    for sec in secs[1:]:
        parts.append(f"{sec}\n中身\n")
    errs = topsort.index_section_floor_errors("".join(parts))
    assert any(secs[0] in e and "本文が空" in e for e in errs)


def test_run_index_missing_floor_section_fails(tmp_path, topsort):
    # フェーズ一覧だけの旧式 index → 基盤層 (基本定義 等) section 床欠落で違反
    ids = topsort.expected_phase_ids()
    enum = "".join(f"{i + 1}. {pid} — phase / 未実施\n" for i, pid in enumerate(ids))
    (tmp_path / "index.md").write_text(
        "---\nid: IDX0\ntitle: t\n---\n# index\n## フェーズ一覧\n\n" + enum, encoding="utf-8"
    )
    write_inventory(tmp_path, [component_entry("C01", "skill")])
    code, errs = topsort.run(tmp_path, "index.md", None)
    assert code == 1
    assert any("必須 section 欠落" in e for e in errs)


def test_detect_cycle_finds_loop(topsort):
    cyc = topsort.detect_cycle({"C1", "C2"}, [("C1", "C2"), ("C2", "C1")])
    assert cyc and cyc[0] == cyc[-1]


def test_detect_cycle_none_for_dag(topsort):
    assert topsort.detect_cycle({"C1", "C2"}, [("C1", "C2")]) is None


def test_verify_component_dag_clean(topsort):
    comps = [{"id": "C01", "depends_on": []}, {"id": "C02", "depends_on": ["C01"]}]
    assert topsort.verify_component_dag(comps) == []


def test_verify_component_dag_missing_dep(topsort):
    comps = [{"id": "C01", "depends_on": ["C99"]}]
    errs = topsort.verify_component_dag(comps)
    assert any("対応する component が無い" in e for e in errs)


def test_verify_component_dag_cycle(topsort):
    comps = [{"id": "C01", "depends_on": ["C02"]}, {"id": "C02", "depends_on": ["C01"]}]
    errs = topsort.verify_component_dag(comps)
    assert any("循環" in e for e in errs)


# ─────────────────── run / main ───────────────────
def test_run_clean(tmp_path, topsort):
    write_phase_index(tmp_path)
    write_inventory(tmp_path, [component_entry("C01", "skill"), component_entry("C02", "hook", depends_on=["C01"])])
    code, errs = topsort.run(tmp_path, "index.md", None)
    assert code == 0 and errs == [], errs


def test_index_frontmatter_id_not_leaked(tmp_path, topsort):
    # plugin_meta 等を持つ index frontmatter の id(IDX0) を phantom として拾わない
    write_phase_index(tmp_path, plugin_meta=True)
    write_inventory(tmp_path, [component_entry("C01", "skill")])
    code, errs = topsort.run(tmp_path, "index.md", None)
    assert code == 0 and errs == [], errs


def test_run_order_violation(tmp_path, topsort):
    ids = topsort.expected_phase_ids()
    ids[0], ids[1] = ids[1], ids[0]
    write_phase_index(tmp_path, order=ids)
    write_inventory(tmp_path, [component_entry("C01", "skill")])
    code, errs = topsort.run(tmp_path, "index.md", None)
    assert code == 1
    assert any("昇順でない" in e for e in errs)


def test_run_dag_cycle(tmp_path, topsort):
    write_phase_index(tmp_path)
    write_inventory(tmp_path, [
        component_entry("C01", "skill", depends_on=["C02"]),
        component_entry("C02", "skill", depends_on=["C01"]),
    ])
    code, errs = topsort.run(tmp_path, "index.md", None)
    assert code == 1
    assert any("循環" in e for e in errs)


def test_run_missing_index(tmp_path, topsort):
    write_inventory(tmp_path, [component_entry("C01", "skill")])
    code, errs = topsort.run(tmp_path, "index.md", None)
    assert code == 2


def test_run_missing_inventory(tmp_path, topsort):
    write_phase_index(tmp_path)
    code, errs = topsort.run(tmp_path, "index.md", None)
    assert code == 2


def test_main_ok(tmp_path, topsort, capsys):
    write_phase_index(tmp_path)
    write_inventory(tmp_path, [component_entry("C01", "skill")])
    assert topsort.main([str(tmp_path)]) == 0
    assert "OK" in capsys.readouterr().out


def test_main_violation(tmp_path, topsort, capsys):
    ids = topsort.expected_phase_ids()[:-1]  # P13 欠落
    write_phase_index(tmp_path, order=ids)
    write_inventory(tmp_path, [component_entry("C01", "skill")])
    assert topsort.main([str(tmp_path)]) == 1
    assert "未列挙" in capsys.readouterr().err


def test_main_not_a_directory(tmp_path, topsort):
    f = tmp_path / "x.txt"
    f.write_text("x", encoding="utf-8")
    assert topsort.main([str(f)]) == 2
