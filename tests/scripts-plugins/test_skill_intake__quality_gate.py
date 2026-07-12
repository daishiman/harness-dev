"""quality_gate.py の統合品質ゲートを実入力で網羅検証する。

対象 script:
  plugins/skill-intake/scripts/quality_gate.py

方針:
  - quality_gate は同階層の validate_intake / check_completeness /
    detect_contradictions / notion_config / render_notion_page を import するため、
    importlib ロード前に script ディレクトリを sys.path へ入れる。
  - 純関数 (_load_required_props / check_db_match / check_property_completeness /
    check_page_id_consistency / check_blocks / gate / parse_flag_args) を実入力で呼ぶ。
  - network/keychain は一切叩かない。check_db_match / check_page_id_consistency は
    notion_config.get_db_id / canonical_notion_id を monkeypatch して解決経路を stub。
  - main は subprocess(sys.executable) と in-process の双方で exit code / 出力 / --out 書き出しを assert。
  - tmp_path のみで完結し repo を汚染しない。
"""
import importlib.util
import json
import subprocess
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[2]
SCRIPT_DIR = ROOT / "plugins" / "skill-intake" / "scripts"
SCRIPT = SCRIPT_DIR / "quality_gate.py"


def _load():
    """script ディレクトリを sys.path に通してから importlib ロードする
    (validate_intake 等の同階層 import を解決するため)。"""
    sys.path.insert(0, str(SCRIPT_DIR))
    spec = importlib.util.spec_from_file_location("quality_gate_t", SCRIPT)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


@pytest.fixture()
def MOD():
    return _load()


@pytest.fixture()
def NC():
    """notion_config モジュール (monkeypatch 対象)。quality_gate が import するのと
    同一インスタンスを sys.modules 経由で取得する。"""
    sys.path.insert(0, str(SCRIPT_DIR))
    import notion_config
    return notion_config


def _run(args):
    return subprocess.run(
        [sys.executable, str(SCRIPT), *args],
        capture_output=True,
        text=True,
        cwd=str(ROOT),
    )


# ---- 合格 intake (5 軸すべて充足 + user_profile) ----
def _valid_intake():
    return {
        "5_axes": {
            "output_target": "Notion ページに業務報告を出力する",
            "info_source": "Slack の過去ログと議事録から情報を集める経路",
            "share_target": "経営チームへ毎週共有する相手",
            "true_problem": "報告作成に時間がかかりすぎる課題を解決する",
            "knowledge_assets": "過去の報告テンプレートと用語集を資産化する",
        },
        "user_profile": {"role": "PM"},
    }


# --- _load_required_props ---


def test_load_required_props_real_schema(MOD):
    req = MOD._load_required_props()
    assert req is not None
    # created_time (作成日) は除外される。名前/真の課題 など required は含む。
    assert "名前" in req
    assert "真の課題" in req
    assert "作成日" not in req


def test_load_required_props_unreadable_returns_none(MOD, monkeypatch, tmp_path):
    monkeypatch.setattr(MOD, "SCHEMA_PATH", tmp_path / "missing.json")
    assert MOD._load_required_props() is None


def test_load_required_props_filters_created_time(MOD, monkeypatch, tmp_path):
    schema = {
        "properties": {
            "名前": {"required": True, "type": "title"},
            "作成日": {"required": True, "type": "created_time"},
            "任意": {"type": "select"},
            "非辞書": "ignored",
        }
    }
    p = tmp_path / "schema.json"
    p.write_text(json.dumps(schema), encoding="utf-8")
    monkeypatch.setattr(MOD, "SCHEMA_PATH", p)
    req = MOD._load_required_props()
    assert req == {"名前"}


# --- check_property_completeness ---


def test_check_property_completeness_pass(MOD):
    r = MOD.check_property_completeness(_valid_intake())
    assert r["ok"] is True
    assert r["missing"] == []


def test_check_property_completeness_schema_unreadable(MOD, monkeypatch, tmp_path):
    monkeypatch.setattr(MOD, "SCHEMA_PATH", tmp_path / "missing.json")
    r = MOD.check_property_completeness(_valid_intake())
    assert r["ok"] is False
    assert "unreadable" in r["reason"]


def test_check_property_completeness_render_raises(MOD, monkeypatch, tmp_path):
    # render_notion_page.project_db_properties を例外化 -> ok False + reason
    import render_notion_page as rnp

    def _boom(ctx):
        raise RuntimeError("render boom")

    monkeypatch.setattr(rnp, "project_db_properties", _boom)
    r = MOD.check_property_completeness(_valid_intake())
    assert r["ok"] is False
    assert "project_db_properties failed" in r["reason"]


def test_check_property_completeness_missing_required(MOD, monkeypatch, tmp_path):
    # schema が render が送らない required プロパティを要求 -> missing 検出
    schema = {"properties": {"存在しないプロパティ": {"required": True, "type": "select"}}}
    p = tmp_path / "schema.json"
    p.write_text(json.dumps(schema), encoding="utf-8")
    monkeypatch.setattr(MOD, "SCHEMA_PATH", p)
    r = MOD.check_property_completeness(_valid_intake())
    assert r["ok"] is False
    assert "存在しないプロパティ" in r["missing"]


# --- check_db_match ---


def test_check_db_match_skipped_when_no_requested(MOD):
    r = MOD.check_db_match({}, None)
    assert r["ok"] is True
    assert r["skipped"] is True


def test_check_db_match_resolved_equals_requested(MOD, NC, monkeypatch):
    monkeypatch.setattr(NC, "get_db_id", lambda key: "11111111222233334444555566667777")
    r = MOD.check_db_match({}, "11111111-2222-3333-4444-555566667777")
    assert r["ok"] is True
    assert r["reason"] == ""


def test_check_db_match_mismatch(MOD, NC, monkeypatch):
    monkeypatch.setattr(NC, "get_db_id", lambda key: "aaaaaaaabbbbccccddddeeeeeeeeeeee")
    r = MOD.check_db_match({}, "11111111-2222-3333-4444-555566667777")
    assert r["ok"] is False
    assert "resolved database_id != requested" in r["reason"]


def test_check_db_match_resolved_none_explicit_arg_only(MOD, NC, monkeypatch):
    monkeypatch.setattr(NC, "get_db_id", lambda key: None)
    r = MOD.check_db_match({}, "11111111-2222-3333-4444-555566667777")
    assert r["ok"] is True
    assert r["source"] == "explicit_arg_only"


def test_check_db_match_canon_fallback_hex_filter(MOD, NC, monkeypatch):
    # _canon 内で canonical_notion_id が例外 -> hex-filter fallback 経路。
    # resolved と requested は hex 抽出後に一致するため ok True。
    monkeypatch.setattr(NC, "get_db_id", lambda key: "abc-def-123")

    def _boom(v):
        raise RuntimeError("canon boom")

    monkeypatch.setattr(NC, "canonical_notion_id", _boom)
    # 両者とも hex 文字のみ抽出すると "abcdef123" で一致する
    r = MOD.check_db_match({}, "ABC_DEF/123")
    assert r["ok"] is True


def test_check_db_match_resolution_raises(MOD, NC, monkeypatch):
    def _boom(key):
        raise RuntimeError("resolve boom")

    monkeypatch.setattr(NC, "get_db_id", _boom)
    r = MOD.check_db_match({}, "11111111-2222-3333-4444-555566667777")
    assert r["ok"] is False
    assert "db resolution failed" in r["reason"]


# --- check_page_id_consistency ---


def test_page_id_skipped_initial_create(MOD):
    r = MOD.check_page_id_consistency(None, None)
    assert r["ok"] is True
    assert r["skipped"] is True


def test_page_id_missing_result_file(MOD, tmp_path):
    r = MOD.check_page_id_consistency(str(tmp_path / "no.json"), "prev-id")
    assert r["ok"] is False
    assert "result file missing" in r["reason"]


def test_page_id_result_read_error(MOD, tmp_path):
    bad = tmp_path / "result.json"
    bad.write_text("{not json", encoding="utf-8")
    r = MOD.check_page_id_consistency(str(bad), "prev-id")
    assert r["ok"] is False
    assert "result read error" in r["reason"]


def test_page_id_match(MOD, tmp_path):
    rp = tmp_path / "result.json"
    rp.write_text(json.dumps({"page_id": "11111111-2222-3333-4444-555566667777"}),
                  encoding="utf-8")
    r = MOD.check_page_id_consistency(str(rp), "11111111222233334444555566667777")
    assert r["ok"] is True


def test_page_id_mismatch_orphan(MOD, tmp_path):
    rp = tmp_path / "result.json"
    rp.write_text(json.dumps({"page_id": "aaaaaaaabbbbccccddddeeeeeeeeeeee"}),
                  encoding="utf-8")
    r = MOD.check_page_id_consistency(str(rp), "11111111222233334444555566667777")
    assert r["ok"] is False
    assert "orphan" in r["reason"]


def test_page_id_uses_id_field_fallback(MOD, tmp_path):
    # page_id 不在でも id フィールドを使う
    rp = tmp_path / "result.json"
    rp.write_text(json.dumps({"id": "11111111-2222-3333-4444-555566667777"}),
                  encoding="utf-8")
    r = MOD.check_page_id_consistency(str(rp), "11111111222233334444555566667777")
    assert r["ok"] is True


def test_page_id_canonicalize_failure_fallback(MOD, tmp_path, NC, monkeypatch):
    # canonical_notion_id が例外を投げても素の値で比較する fallback 経路
    rp = tmp_path / "result.json"
    rp.write_text(json.dumps({"page_id": "RAW-ID"}), encoding="utf-8")

    def _boom(v):
        raise RuntimeError("canon boom")

    monkeypatch.setattr(NC, "canonical_notion_id", _boom)
    r = MOD.check_page_id_consistency(str(rp), "RAW-ID")
    assert r["ok"] is True  # 素の RAW-ID 同士で一致


# --- check_blocks ---


def _blocks(total=20, mermaid=1, h2=5):
    arr = []
    for _ in range(mermaid):
        arr.append({"type": "code", "code": {"language": "mermaid"}})
    for _ in range(h2):
        arr.append({"type": "heading_2"})
    while len(arr) < total:
        arr.append({"type": "paragraph"})
    return arr


def test_check_blocks_pass(MOD):
    r = MOD.check_blocks(_blocks())
    assert r["ok"] is True
    assert r["reasons"] == []
    assert r["mermaid"] == 1
    assert r["h2"] == 5


def test_check_blocks_children_wrapper(MOD):
    r = MOD.check_blocks({"children": _blocks()})
    assert r["ok"] is True


def test_check_blocks_non_list_treated_empty(MOD):
    r = MOD.check_blocks("not a list")
    assert r["ok"] is False
    assert r["total"] == 0
    assert any("blocks total 0 < 20" in x for x in r["reasons"])


def test_check_blocks_all_thresholds_fail(MOD):
    r = MOD.check_blocks([{"type": "paragraph"}])
    assert r["ok"] is False
    assert any("< 20" in x for x in r["reasons"])
    assert any("mermaid" in x for x in r["reasons"])
    assert any("heading_2" in x for x in r["reasons"])


def test_check_blocks_ignores_non_dict_entries(MOD):
    arr = _blocks()
    arr.append("garbage")
    arr.append(123)
    r = MOD.check_blocks(arr)
    # 非 dict は skip されカウントに影響しない -> 依然 pass
    assert r["ok"] is True


# --- gate (統合) ---


def test_gate_pass(MOD):
    r = MOD.gate(_valid_intake())
    assert r["status"] == "PASS"
    assert r["checks"]["validate_intake"]["ok"] is True
    assert r["checks"]["check_completeness"]["filled_axes"] == 5


def test_gate_fail_on_validate(MOD):
    r = MOD.gate({"user_profile": {}})  # 5_axes 欠落
    assert r["status"] == "FAIL"
    assert r["checks"]["validate_intake"]["ok"] is False


def test_gate_fail_on_completeness(MOD):
    intake = _valid_intake()
    intake["5_axes"]["true_problem"] = "TBD"  # placeholder
    r = MOD.gate(intake)
    assert r["status"] == "FAIL"
    assert "true_problem" in r["checks"]["check_completeness"]["placeholders"]


def test_gate_db_match_failure_makes_fail(MOD, NC, monkeypatch):
    monkeypatch.setattr(NC, "get_db_id", lambda key: "aaaaaaaabbbbccccddddeeeeeeeeeeee")
    r = MOD.gate(_valid_intake(), requested_db_id="11111111-2222-3333-4444-555566667777")
    assert r["status"] == "FAIL"
    assert r["checks"]["db_match"]["ok"] is False


# --- parse_flag_args ---


def test_parse_flag_args_all_flags(MOD):
    out = MOD.parse_flag_args([
        "--intake", "i.json", "--blocks", "b.json", "--out", "o.json",
        "--database-id", "DB", "--result-path", "r.json", "--prev-page-id", "P",
    ])
    assert out["intake"] == "i.json"
    assert out["blocks"] == "b.json"
    assert out["out_file"] == "o.json"
    assert out["database_id"] == "DB"
    assert out["result_path"] == "r.json"
    assert out["prev_page_id"] == "P"
    assert out["positional"] == []


def test_parse_flag_args_positional(MOD):
    out = MOD.parse_flag_args(["intake.json", "out.json"])
    assert out["positional"] == ["intake.json", "out.json"]


def test_parse_flag_args_unknown_option_raises(MOD):
    with pytest.raises(ValueError):
        MOD.parse_flag_args(["--bogus"])


# --- main: in-process ---


def test_main_no_intake_usage_error(MOD, capsys):
    rc = MOD.main(["prog"])
    assert rc == 2
    assert "usage:" in capsys.readouterr().err


def test_main_unknown_option_returns_2(MOD, capsys):
    rc = MOD.main(["prog", "--bogus"])
    assert rc == 2
    assert "argument error" in capsys.readouterr().err


def test_main_input_read_error_returns_2(MOD, tmp_path, capsys):
    rc = MOD.main(["prog", str(tmp_path / "missing.json")])
    assert rc == 2
    assert "input error" in capsys.readouterr().err


def test_main_pass_stdout(MOD, tmp_path, capsys):
    ij = tmp_path / "intake.json"
    ij.write_text(json.dumps(_valid_intake(), ensure_ascii=False), encoding="utf-8")
    rc = MOD.main(["prog", str(ij)])
    assert rc == 0
    out = json.loads(capsys.readouterr().out)
    assert out["status"] == "PASS"


def test_main_fail_returns_1(MOD, tmp_path, capsys):
    ij = tmp_path / "intake.json"
    ij.write_text(json.dumps({"user_profile": {}}), encoding="utf-8")
    rc = MOD.main(["prog", str(ij)])
    assert rc == 1
    out = json.loads(capsys.readouterr().out)
    assert out["status"] == "FAIL"


def test_main_writes_out_file(MOD, tmp_path, capsys):
    ij = tmp_path / "intake.json"
    ij.write_text(json.dumps(_valid_intake(), ensure_ascii=False), encoding="utf-8")
    of = tmp_path / "out.json"
    rc = MOD.main(["prog", "--intake", str(ij), "--out", str(of)])
    assert rc == 0
    assert of.exists()
    data = json.loads(of.read_text(encoding="utf-8"))
    assert data["status"] == "PASS"
    # --out 指定時は stdout に JSON を出さない
    assert capsys.readouterr().out == ""


def test_main_blocks_pass(MOD, tmp_path):
    ij = tmp_path / "intake.json"
    ij.write_text(json.dumps(_valid_intake(), ensure_ascii=False), encoding="utf-8")
    bj = tmp_path / "blocks.json"
    bj.write_text(json.dumps(_blocks()), encoding="utf-8")
    of = tmp_path / "out.json"
    rc = MOD.main(["prog", "--intake", str(ij), "--blocks", str(bj), "--out", str(of)])
    assert rc == 0
    data = json.loads(of.read_text(encoding="utf-8"))
    assert data["checks"]["blocks_coverage"]["ok"] is True


def test_main_blocks_fail_returns_2(MOD, tmp_path, capsys):
    ij = tmp_path / "intake.json"
    ij.write_text(json.dumps(_valid_intake(), ensure_ascii=False), encoding="utf-8")
    bj = tmp_path / "blocks.json"
    bj.write_text(json.dumps([{"type": "paragraph"}]), encoding="utf-8")
    rc = MOD.main(["prog", "--intake", str(ij), "--blocks", str(bj)])
    # intake は PASS だが blocks 不足で FAIL -> blocks_failed 経路は exit2
    assert rc == 2
    err = capsys.readouterr().err
    assert "blocks-coverage:" in err


def test_main_blocks_read_error_returns_2(MOD, tmp_path, capsys):
    ij = tmp_path / "intake.json"
    ij.write_text(json.dumps(_valid_intake(), ensure_ascii=False), encoding="utf-8")
    rc = MOD.main(["prog", "--intake", str(ij), "--blocks", str(tmp_path / "no.json")])
    assert rc == 2
    assert "--blocks read error" in capsys.readouterr().err


# --- main: subprocess (exit code 契約) ---


def test_subprocess_pass_exits_0(tmp_path):
    ij = tmp_path / "intake.json"
    ij.write_text(json.dumps(_valid_intake(), ensure_ascii=False), encoding="utf-8")
    proc = _run([str(ij)])
    assert proc.returncode == 0
    assert json.loads(proc.stdout)["status"] == "PASS"


def test_subprocess_fail_exits_1(tmp_path):
    ij = tmp_path / "intake.json"
    ij.write_text(json.dumps({"user_profile": {}}), encoding="utf-8")
    proc = _run([str(ij)])
    assert proc.returncode == 1
    assert json.loads(proc.stdout)["status"] == "FAIL"


def test_subprocess_usage_exits_2():
    proc = _run([])
    assert proc.returncode == 2
    assert "usage:" in proc.stderr


def test_subprocess_blocks_fail_exits_2(tmp_path):
    ij = tmp_path / "intake.json"
    ij.write_text(json.dumps(_valid_intake(), ensure_ascii=False), encoding="utf-8")
    bj = tmp_path / "blocks.json"
    bj.write_text(json.dumps([{"type": "paragraph"}]), encoding="utf-8")
    proc = _run([str(ij), "--blocks", str(bj)])
    assert proc.returncode == 2
    assert "blocks-coverage:" in proc.stderr


# ---------------------------------------------------------------------------
# procedure ゲート (C04 拡張, goal-spec C3/C7) — purpose+procedure 両方揃うまで
# 下流ハンドオフへ進めない invariant を network/LLM 無しで網羅する。
# ---------------------------------------------------------------------------


def _intake_procedure_aware(purpose="報告作成を一気通貫で代行する", with_procedure=True,
                            validation="clean"):
    """procedure-aware な v2 intake を組む。validation: clean|contaminated|incomplete|none。"""
    sections = {
        "3_purpose_excavator": {"true_purpose": purpose} if purpose else {},
        "6_five_axes_summary": {
            "axes": [{"axis_id": "real_problem", "answer": "報告に時間がかかる"}],
        },
    }
    if with_procedure:
        sections["6_five_axes_summary"]["procedure"] = {
            "mode": "detailed",
            "steps": [{"action": "a", "input": "b", "output": "c", "tool": "d", "frequency": "e"}],
        }
    intake = {"schema_version": "2.0.0", "sections": sections}
    if validation == "clean":
        intake["validation"] = {"procedure_completeness": {
            "complete": True, "mode": "detailed", "missing": [],
            "contamination": {"detected": False, "fields": [], "matched_terms": []}}}
    elif validation == "contaminated":
        intake["validation"] = {"procedure_completeness": {
            "complete": True, "mode": "detailed", "missing": [],
            "contamination": {"detected": True, "fields": ["procedure.steps[0].action"],
                              "matched_terms": ["すべき"]}}}
    elif validation == "incomplete":
        intake["validation"] = {"procedure_completeness": {
            "complete": False, "mode": "detailed",
            "missing": ["steps[0].tool: 非空文字列が必要"],
            "contamination": {"detected": False, "fields": [], "matched_terms": []}}}
    # validation == "none": validation を付けない (fail-closed 検証用)
    return intake


def test_procedure_gate_migration_warn_for_legacy_v1(MOD):
    # 旧 intake (procedure 節・validation とも無し) は migration_warn で通す (後方互換)。
    r = MOD.check_procedure_gate(_valid_intake())
    assert r["ok"] is True
    assert r.get("migration_warn") is True


def test_procedure_gate_pass_when_complete(MOD):
    r = MOD.check_procedure_gate(_intake_procedure_aware())
    assert r["ok"] is True
    assert r["violations"] == []


def test_procedure_gate_missing_purpose(MOD):
    # purpose は true_purpose 節と axes[real_problem].answer の二重ソース。両方空で初めて欠落。
    intake = _intake_procedure_aware(purpose=None)
    intake["sections"]["6_five_axes_summary"]["axes"] = []
    r = MOD.check_procedure_gate(intake)
    assert r["ok"] is False
    assert "missing_purpose" in r["violations"]


def test_procedure_gate_purpose_from_axes_fallback(MOD):
    # true_purpose 節が空でも axes[real_problem].answer から purpose を拾える。
    intake = _intake_procedure_aware(purpose=None)
    intake["sections"]["6_five_axes_summary"]["axes"][0]["answer"] = "報告に時間がかかる課題"
    r = MOD.check_procedure_gate(intake)
    assert "missing_purpose" not in r["violations"]


def test_procedure_gate_missing_procedure(MOD):
    r = MOD.check_procedure_gate(_intake_procedure_aware(with_procedure=False))
    assert r["ok"] is False
    assert "missing_procedure" in r["violations"]


def test_procedure_gate_missing_validation_fail_closed(MOD):
    r = MOD.check_procedure_gate(_intake_procedure_aware(validation="none"))
    assert r["ok"] is False
    assert "missing_procedure_validation" in r["violations"]


def test_procedure_gate_contamination_detected(MOD):
    r = MOD.check_procedure_gate(_intake_procedure_aware(validation="contaminated"))
    assert r["ok"] is False
    assert "to_be_contamination_detected" in r["violations"]


def test_procedure_gate_incomplete_flag_is_missing_procedure(MOD):
    r = MOD.check_procedure_gate(_intake_procedure_aware(validation="incomplete"))
    assert r["ok"] is False
    assert "missing_procedure" in r["violations"]


def test_procedure_gate_require_procedure_forces_legacy_fail(MOD):
    # require_procedure=True では procedure-aware でない旧 intake も fail-closed で強制。
    r = MOD.check_procedure_gate(_valid_intake(), require_procedure=True)
    assert r["ok"] is False
    assert "missing_procedure" in r["violations"]
    assert "missing_purpose" in r["violations"]


def test_gate_integration_procedure_fail_makes_status_fail(MOD):
    # v1 valid intake に validation.procedure_completeness を足すと procedure-aware になり、
    # sections 不在で purpose/procedure 欠落 -> procedure_gate FAIL -> gate status FAIL。
    intake = _valid_intake()
    intake["validation"] = {"procedure_completeness": {
        "complete": True, "mode": "detailed", "missing": [],
        "contamination": {"detected": False, "fields": [], "matched_terms": []}}}
    r = MOD.gate(intake)
    assert r["status"] == "FAIL"
    assert r["checks"]["procedure_gate"]["ok"] is False


def test_gate_legacy_v1_still_passes_procedure_gate(MOD):
    # procedure 拡張は既存 v1 intake の PASS を壊さない (migration_warn)。
    r = MOD.gate(_valid_intake())
    assert r["status"] == "PASS"
    assert r["checks"]["procedure_gate"]["ok"] is True


def test_parse_flag_args_require_procedure(MOD):
    out = MOD.parse_flag_args(["i.json", "--require-procedure"])
    assert out["require_procedure"] is True
    assert out["positional"] == ["i.json"]


def test_main_require_procedure_flag_fails_legacy(MOD, tmp_path, capsys):
    # --require-procedure を付けると旧 intake は procedure 欠落で FAIL し stderr に列挙。
    ij = tmp_path / "intake.json"
    ij.write_text(json.dumps(_valid_intake(), ensure_ascii=False), encoding="utf-8")
    rc = MOD.main(["prog", "--intake", str(ij), "--require-procedure"])
    assert rc == 1
    err = capsys.readouterr().err
    assert "procedure-gate:" in err
    assert "missing_procedure" in err


def test_subprocess_require_procedure_fails_legacy(tmp_path):
    ij = tmp_path / "intake.json"
    ij.write_text(json.dumps(_valid_intake(), ensure_ascii=False), encoding="utf-8")
    proc = _run([str(ij), "--require-procedure"])
    assert proc.returncode == 1
    assert "procedure-gate:" in proc.stderr
