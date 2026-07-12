# /// script
# name: test-validate-scripts
# version: 0.1.0
# purpose: C12 (validate-coverage-matrix.py) / C13 (validate-source-citation.py) の決定論ゲートを正例=OK・負例=各違反・usage=exit2 で網羅検証する pytest (in-process import で validate()/main() を直接呼び coverage 計測可能にする)。
# inputs:
#   - argv: pytest 経由 (直接 argv は取らない)
# outputs:
#   - stdout: pytest 結果
#   - exit: 0=all pass / 1=failure
# contexts: [E, C]
# network: false
# write-scope: none
# dependencies: []
# requires-python: ">=3.9"
# ///
"""C12 (validate-coverage-matrix) / C13 (validate-source-citation) の決定論ゲート検証。

正例=OK / 負例=各違反 / usage=exit2 を網羅する。ハイフン名モジュールを importlib で
in-process ロードし validate()/main() を直接呼ぶ (coverage が main() CLI 経路も計測できる)。
"""
from __future__ import annotations

import importlib.util
import json
from pathlib import Path

SCRIPTS = Path(__file__).resolve().parent.parent / "scripts"

PLATFORMS = ["web", "mobile", "tablet", "desktop-windows", "desktop-linux", "desktop-macos"]
CATEGORIES = ["database", "auth", "ui-ux", "security", "infrastructure", "backend", "frontend", "maintenance-ops"]


def _load(name: str, filename: str):
    spec = importlib.util.spec_from_file_location(name, SCRIPTS / filename)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


c12 = _load("vcm", "validate-coverage-matrix.py")
c13 = _load("vsc", "validate-source-citation.py")


def write(tmp_path: Path, name: str, obj: dict) -> str:
    p = tmp_path / name
    p.write_text(json.dumps(obj, ensure_ascii=False), encoding="utf-8")
    return str(p)


# ── C12 fixtures ──────────────────────────────────────────────────────────
def _valid_matrix() -> dict:
    matrix = {c: {p: {"state": "確定", "qa_ref": "qa-001"} for p in PLATFORMS} for c in CATEGORIES}
    return {
        "categories": [{"id": c, "label": c} for c in CATEGORIES],
        "platforms": PLATFORMS,
        "matrix": matrix,
        "qa_log": [{"id": "qa-001", "question": "q", "answer": "a"}],
        "approval_log": [{"id": "appr-001"}],
    }


# ── C12 validate() branch tests ───────────────────────────────────────────
def test_c12_valid_complete():
    assert c12.validate(_valid_matrix(), require_complete=True) == []


def test_c12_loop_allows_uncollected_but_final_fails():
    d = _valid_matrix()
    d["matrix"]["database"]["web"] = {"state": "未収集"}
    assert c12.validate(d, require_complete=False) == []
    assert any("未収集" in f for f in c12.validate(d, require_complete=True))


def test_c12_missing_platform_row():
    d = _valid_matrix()
    del d["matrix"]["database"]["mobile"]
    assert any("mobile" in f for f in c12.validate(d, require_complete=True))


def test_c12_excluded_without_reason():
    d = _valid_matrix()
    d["matrix"]["auth"]["tablet"] = {"state": "対象外"}
    assert any("対象外" in f for f in c12.validate(d))


def test_c12_excluded_with_reason_ok():
    d = _valid_matrix()
    d["matrix"]["auth"]["tablet"] = {"state": "対象外", "reason": "タブレット非対応"}
    assert c12.validate(d, require_complete=True) == []


def test_c12_excluded_with_approval_ref_ok():
    d = _valid_matrix()
    d["matrix"]["auth"]["tablet"] = {"state": "対象外", "approval_ref": "appr-001"}
    assert c12.validate(d, require_complete=True) == []


def test_c12_confirmed_without_qa_ref():
    d = _valid_matrix()
    d["matrix"]["database"]["web"] = {"state": "確定"}
    assert any("qa_ref" in f for f in c12.validate(d))


def test_c12_confirmed_dangling_qa_ref():
    d = _valid_matrix()
    d["matrix"]["database"]["web"] = {"state": "確定", "qa_ref": "qa-999"}
    assert any("qa-999" in f for f in c12.validate(d))


def test_c12_invalid_state():
    d = _valid_matrix()
    d["matrix"]["database"]["web"] = {"state": "とりあえず"}
    assert c12.validate(d)


def test_c12_cell_not_object():
    d = _valid_matrix()
    d["matrix"]["database"]["web"] = "確定"
    assert any("オブジェクト" in f for f in c12.validate(d))


def test_c12_row_not_object():
    d = _valid_matrix()
    d["matrix"]["database"] = "x"
    assert any("行が存在しない" in f for f in c12.validate(d))


def test_c12_missing_goal_spec_category():
    d = _valid_matrix()
    d["categories"] = [c for c in d["categories"] if c["id"] != "security"]
    del d["matrix"]["security"]
    assert any("security" in f for f in c12.validate(d))


def test_c12_excluded_category_ok():
    d = _valid_matrix()
    d["categories"] = [c for c in d["categories"] if c["id"] != "security"]
    del d["matrix"]["security"]
    d["excluded_categories"] = {"security": "セキュリティは別文書へ委譲"}
    assert c12.validate(d, require_complete=True) == []


def test_c12_category_without_id():
    d = _valid_matrix()
    d["categories"].append({"label": "no-id"})
    assert any("id 欠落" in f for f in c12.validate(d))


def test_c12_aggregate_mismatch():
    d = _valid_matrix()
    d["category_aggregate"] = {"database": "未着手"}
    assert any("真理値表" in f for f in c12.validate(d))


def test_c12_aggregate_match():
    d = _valid_matrix()
    d["category_aggregate"] = {c: "確定" for c in CATEGORIES}
    assert c12.validate(d, require_complete=True) == []


def test_c12_empty_categories():
    assert c12.validate({"matrix": {}})
    assert c12.validate({"categories": [{"id": "a"}]})


def test_c12_derive_aggregate_truth_table():
    assert c12._derive_aggregate(["未収集"] * 6) == "未着手"
    assert c12._derive_aggregate(["対象外"] * 6) == "対象外"
    assert c12._derive_aggregate(["確定", "未収集"]) == "収集中"
    assert c12._derive_aggregate(["確定", "対象外"]) == "確定"


# ── C12 main() CLI tests ──────────────────────────────────────────────────
def test_c12_main_ok(tmp_path, capsys):
    m = write(tmp_path, "m.json", _valid_matrix())
    assert c12.main(["--matrix", m, "--require-complete"]) == 0
    assert "OK" in capsys.readouterr().out


def test_c12_main_violation(tmp_path):
    d = _valid_matrix()
    d["matrix"]["database"]["web"] = {"state": "x"}
    m = write(tmp_path, "m.json", d)
    assert c12.main(["--matrix", m]) == 1


def test_c12_main_missing_file(tmp_path):
    assert c12.main(["--matrix", str(tmp_path / "nope.json")]) == 2


def test_c12_main_bad_json(tmp_path):
    p = tmp_path / "bad.json"
    p.write_text("{not json", encoding="utf-8")
    assert c12.main(["--matrix", str(p)]) == 2


# ── C13 fixtures ──────────────────────────────────────────────────────────
def _valid_citation() -> tuple[dict, dict]:
    targets = {"targets": [{"target_id": "react"}, {"target_id": "postgres"}]}
    r1 = {
        "target_id": "react",
        "retrieved_at": "2026-07-11T00:00:00Z",
        "source_url": "https://react.dev/reference/react",
        "official_publisher": "Meta",
        "official_host": "react.dev",
        "version": "19.0",
        "latest_checked_at": "2026-07-11T00:00:00Z",
        "summary": "React reference",
    }
    r2 = dict(r1)
    r2.update(
        target_id="postgres",
        source_url="https://www.postgresql.org/docs/",
        official_host="postgresql.org",
        last_updated="2026-05-01",
    )
    r2.pop("version")
    return targets, {"references": [r1, r2]}


# ── C13 validate() branch tests ───────────────────────────────────────────
def test_c13_valid():
    t, r = _valid_citation()
    assert c13.validate(t, r) == []


def test_c13_missing_target():
    t, r = _valid_citation()
    r["references"] = [x for x in r["references"] if x["target_id"] != "postgres"]
    assert any("postgres" in f for f in c13.validate(t, r))


def test_c13_missing_field():
    t, r = _valid_citation()
    del r["references"][0]["retrieved_at"]
    assert any("retrieved_at" in f for f in c13.validate(t, r))


def test_c13_no_version_no_last_updated():
    t, r = _valid_citation()
    r["references"][0].pop("version", None)
    r["references"][0].pop("last_updated", None)
    assert any("last_updated" in f for f in c13.validate(t, r))


def test_c13_host_mismatch():
    t, r = _valid_citation()
    r["references"][0]["source_url"] = "https://random-blog.example/react"
    assert any("official_host" in f for f in c13.validate(t, r))


def test_c13_unparseable_url():
    t, r = _valid_citation()
    r["references"][0]["source_url"] = "notaurl"
    assert any("host を解決できない" in f for f in c13.validate(t, r))


def test_c13_duplicate_target():
    t, r = _valid_citation()
    dup = dict(r["references"][0])
    r["references"].append(dup)
    assert any("重複" in f for f in c13.validate(t, r))


def test_c13_ref_missing_target_id():
    t, r = _valid_citation()
    r["references"].append({"source_url": "x"})
    assert any("target_id 欠落" in f for f in c13.validate(t, r))


def test_c13_ref_not_object():
    t, r = _valid_citation()
    r["references"].append("x")
    assert any("オブジェクトでない" in f for f in c13.validate(t, r))


def test_c13_references_not_list():
    t, _ = _valid_citation()
    assert any("配列でない" in f for f in c13.validate(t, {"references": "x"}))


def test_c13_empty_targets_and_empty_refs_is_ok():
    # 出典対象なし = targets 空 かつ references 空 → OK (exit0)。コンパイル動線を詰まらせない (F2)。
    assert c13.validate({"targets": []}, {"references": []}) == []


# ── F3: spec-state 採択済み decision があるのに targets 空 → vacuous-green を warning surface ──
def test_c13_state_target_warnings_helper():
    adopted = {"decisions": [{"id": "D1", "user_decision": {"option_id": "x", "confirmed_at": "y"}}]}
    # 採択済み decision があり targets 空 → warning
    assert c13.state_target_warnings({"targets": []}, adopted)
    # targets があれば warning なし
    assert c13.state_target_warnings({"targets": ["react"]}, adopted) == []
    # user_decision 未採択なら warning なし (推奨提示のみは対象外)
    assert c13.state_target_warnings({"targets": []}, {"decisions": [{"id": "D1"}]}) == []
    assert c13.state_target_warnings({"targets": []}, {"decisions": []}) == []


def test_c13_main_state_warns_but_exit0(tmp_path, capsys):
    adopted = {"decisions": [{"id": "D1", "user_decision": {"option_id": "x", "confirmed_at": "y"}}]}
    tp = write(tmp_path, "t.json", {"targets": []})
    rp = write(tmp_path, "r.json", {"references": []})
    sp = write(tmp_path, "s.json", adopted)
    # vacuous-green (targets 空∧references 空) だが採択技術あり → exit0 のまま warning surface
    assert c13.main(["--targets", tp, "--references", rp, "--state", sp]) == 0
    assert "WARNING" in capsys.readouterr().err


def test_c13_main_state_no_warning_when_targets_present(tmp_path, capsys):
    adopted = {"decisions": [{"id": "D1", "user_decision": {"option_id": "x", "confirmed_at": "y"}}]}
    t, r = _valid_citation()
    tp = write(tmp_path, "t.json", t)
    rp = write(tmp_path, "r.json", r)
    sp = write(tmp_path, "s.json", adopted)
    assert c13.main(["--targets", tp, "--references", rp, "--state", sp]) == 0
    assert "WARNING" not in capsys.readouterr().err


def test_c13_main_state_missing_file_returns_2(tmp_path):
    tp = write(tmp_path, "t.json", {"targets": []})
    rp = write(tmp_path, "r.json", {"references": []})
    assert c13.main(["--targets", tp, "--references", rp, "--state", str(tmp_path / "nope.json")]) == 2


def test_c13_empty_targets_but_refs_present_is_violation():
    # targets 空だが references 非空 (orphan) は従来どおり違反。
    _, r = _valid_citation()
    assert any("対象 target_id が空" in f for f in c13.validate({"targets": []}, r))


def test_c13_targets_present_but_refs_empty_is_violation():
    # targets 非空だが references 欠落は従来どおり違反 (全件対応)。
    t, _ = _valid_citation()
    assert any("参照欠落" in f for f in c13.validate(t, {"references": []}))


def test_c13_norm_host_only_strips_www_prefix():
    # F6: lstrip("www.") は {w,.} 先頭除去で web.dev -> eb.dev と別 host を潰す。
    # removeprefix("www.") は先頭が www. のときだけ除去し他 host を保持する。
    assert c13._norm_host("web.dev") == "web.dev"
    assert c13._norm_host("www.postgresql.org") == "postgresql.org"
    assert c13._norm_host("WWW.React.Dev") == "react.dev"
    assert c13._norm_host("wobble.example") == "wobble.example"


def test_c13_web_dev_host_not_mangled():
    # web.dev のような www. で始まらない公式 host が誤剥離されず一致判定される。
    t, r = _valid_citation()
    r["references"][0].update(source_url="https://web.dev/reference", official_host="web.dev")
    assert c13.validate(t, r) == []


def test_c13_string_targets():
    t, r = _valid_citation()
    t["targets"] = ["react", "postgres"]
    assert c13.validate(t, r) == []


# ── C13 main() CLI tests ──────────────────────────────────────────────────
def test_c13_main_ok(tmp_path, capsys):
    t, r = _valid_citation()
    tp = write(tmp_path, "t.json", t)
    rp = write(tmp_path, "r.json", r)
    assert c13.main(["--targets", tp, "--references", rp]) == 0
    assert "OK" in capsys.readouterr().out


def test_c13_main_violation(tmp_path):
    t, r = _valid_citation()
    del r["references"][0]["source_url"]
    tp = write(tmp_path, "t.json", t)
    rp = write(tmp_path, "r.json", r)
    assert c13.main(["--targets", tp, "--references", rp]) == 1


def test_c13_main_missing_file(tmp_path):
    rp = write(tmp_path, "r.json", {"references": []})
    assert c13.main(["--targets", str(tmp_path / "nope.json"), "--references", rp]) == 2


def test_c13_main_bad_json(tmp_path):
    t, _ = _valid_citation()
    tp = write(tmp_path, "t.json", t)
    bad = tmp_path / "bad.json"
    bad.write_text("{nope", encoding="utf-8")
    assert c13.main(["--targets", tp, "--references", str(bad)]) == 2
