#!/usr/bin/env python3
# /// script
# name: test-build-fetched-references
# version: 0.1.0
# purpose: run-system-spec-doc-fetch の R3 assembler (build-fetched-references.py) の記録形状ユニットと、IN1 受入 (plugin-root validate-source-citation.py が fixture fetched-references を全件対応/公式host一致で exit0・負例で検出) を検証する pytest。
# inputs:
#   - argv: pytest 経由 (直接 argv は取らない)
# outputs:
#   - stdout: pytest 結果
#   - exit: 0=all pass / 1=failure
# contexts: [E, C]
# network: false
# write-scope: none (tmp_path のみ)
# dependencies: []
# requires-python: ">=3.9"
# ///
"""build-fetched-references.py (R3) と validate-source-citation.py (IN1) の検証。

ハイフン名モジュールを importlib で in-process ロードし、関数と main() CLI 経路の
双方を直接呼ぶ (coverage が CLI 分岐も計測できる)。validate-source-citation.py は
plugin-root の共有 script を read-only で呼び出す (本 skill 配下は改変しない)。
"""
from __future__ import annotations

import importlib.util
import json
from pathlib import Path

import pytest

SKILL_DIR = Path(__file__).resolve().parent.parent
PLUGIN_ROOT = SKILL_DIR.parent.parent  # plugins/system-spec-harness
FIXTURES = Path(__file__).resolve().parent


def _load(name: str, path: Path):
    spec = importlib.util.spec_from_file_location(name, path)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


bfr = _load("bfr", SKILL_DIR / "scripts" / "build-fetched-references.py")
vsc = _load("vsc", PLUGIN_ROOT / "scripts" / "validate-source-citation.py")


# --------------------------------------------------------------------------- #
# record 素材 fixtures                                                          #
# --------------------------------------------------------------------------- #
def _react_rec() -> dict:
    return {
        "target_id": "react",
        "retrieved_at": "2026-07-11T00:00:00Z",
        "source_url": "https://react.dev/reference/react",
        "official_publisher": "Meta",
        "official_host": "react.dev",
        "version": "19.0",
        "latest_checked_at": "2026-07-11T00:00:00Z",
        "summary": "React reference",
    }


def _postgres_rec() -> dict:
    return {
        "target_id": "postgres",
        "retrieved_at": "2026-07-11T00:00:00Z",
        "source_url": "https://www.postgresql.org/docs/",
        "official_publisher": "PGDG",
        "last_updated": "2026-05-01",
        "latest_checked_at": "2026-07-11T00:00:00Z",
        "summary": "PostgreSQL docs",
    }


# --------------------------------------------------------------------------- #
# build_record: 正例 / 各負例                                                   #
# --------------------------------------------------------------------------- #
def test_build_record_version_path():
    out = bfr.build_record(_react_rec())
    assert out["target_id"] == "react"
    assert out["official_host"] == "react.dev"
    assert out["version"] == "19.0"
    # 出力キー順が契約順で欠落フィールドを含まない (last_updated は無い)
    assert "last_updated" not in out
    assert list(out.keys())[0] == "target_id"


def test_build_record_last_updated_path_derives_host():
    # official_host 未指定でも source_url から導出される
    rec = _postgres_rec()
    out = bfr.build_record(rec)
    assert out["official_host"] == "postgresql.org"
    assert out["last_updated"] == "2026-05-01"
    assert "version" not in out


def test_build_record_not_dict():
    with pytest.raises(bfr.RecordError, match="オブジェクト"):
        bfr.build_record("x")


def test_build_record_missing_target_id():
    rec = _react_rec()
    del rec["target_id"]
    with pytest.raises(bfr.RecordError, match="target_id"):
        bfr.build_record(rec)


@pytest.mark.parametrize(
    "field", ["source_url", "official_publisher", "retrieved_at", "latest_checked_at", "summary"]
)
def test_build_record_missing_required_field(field):
    rec = _react_rec()
    del rec[field]
    with pytest.raises(bfr.RecordError, match=field):
        bfr.build_record(rec)


def test_build_record_no_version_no_last_updated():
    rec = _react_rec()
    rec.pop("version", None)
    rec.pop("last_updated", None)
    with pytest.raises(bfr.RecordError, match="last_updated"):
        bfr.build_record(rec)


def test_build_record_unparseable_url():
    rec = _react_rec()
    rec["source_url"] = "notaurl"
    with pytest.raises(bfr.RecordError, match="host を解決できない"):
        bfr.build_record(rec)


def test_build_record_host_mismatch():
    rec = _react_rec()
    rec["source_url"] = "https://random-blog.example/react"
    with pytest.raises(bfr.RecordError, match="不一致"):
        bfr.build_record(rec)


def test_host_helpers():
    assert bfr.host_of("https://www.React.dev/x") == "react.dev"
    assert bfr.host_of("") == ""
    assert bfr.norm_host("") == ""


# --------------------------------------------------------------------------- #
# assemble: 全件 / 重複 / 非配列                                                #
# --------------------------------------------------------------------------- #
def test_assemble_ok_preserves_order():
    result = bfr.assemble([_react_rec(), _postgres_rec()])
    ids = [r["target_id"] for r in result["references"]]
    assert ids == ["react", "postgres"]


def test_assemble_duplicate_target():
    with pytest.raises(bfr.RecordError, match="重複"):
        bfr.assemble([_react_rec(), _react_rec()])


def test_assemble_not_list():
    with pytest.raises(bfr.RecordError, match="配列でない"):
        bfr.assemble({"react": 1})


def test_missing_targets_detects_gap():
    result = bfr.assemble([_react_rec()])
    targets = {"targets": [{"target_id": "react"}, {"target_id": "postgres"}]}
    assert bfr.missing_targets(targets, result) == ["postgres"]
    # 文字列配列の targets も対応
    assert bfr.missing_targets({"targets": ["react"]}, result) == []


# --------------------------------------------------------------------------- #
# main() CLI 分岐                                                               #
# --------------------------------------------------------------------------- #
def _write(tmp_path: Path, name: str, obj) -> str:
    p = tmp_path / name
    p.write_text(json.dumps(obj, ensure_ascii=False), encoding="utf-8")
    return str(p)


def test_main_assemble_stdout_ok(tmp_path, capsys):
    recs = _write(tmp_path, "recs.json", [_react_rec(), _postgres_rec()])
    assert bfr.main(["assemble", "--records", recs]) == 0
    out = json.loads(capsys.readouterr().out)
    assert len(out["references"]) == 2


def test_main_assemble_records_wrapper_and_out_file(tmp_path):
    recs = _write(tmp_path, "recs.json", {"records": [_react_rec()]})
    out = tmp_path / "fetched-references.json"
    assert bfr.main(["assemble", "--records", recs, "--out", str(out)]) == 0
    written = json.loads(out.read_text(encoding="utf-8"))
    assert written["references"][0]["target_id"] == "react"


def test_main_assemble_with_targets_ok(tmp_path):
    recs = _write(tmp_path, "recs.json", [_react_rec(), _postgres_rec()])
    tgt = _write(tmp_path, "t.json", {"targets": [{"target_id": "react"}, {"target_id": "postgres"}]})
    assert bfr.main(["assemble", "--records", recs, "--targets", tgt]) == 0


def test_main_assemble_targets_missing_returns_1(tmp_path):
    recs = _write(tmp_path, "recs.json", [_react_rec()])
    tgt = _write(tmp_path, "t.json", {"targets": [{"target_id": "react"}, {"target_id": "postgres"}]})
    assert bfr.main(["assemble", "--records", recs, "--targets", tgt]) == 1


def test_main_assemble_record_error_returns_1(tmp_path):
    bad = _react_rec()
    del bad["summary"]
    recs = _write(tmp_path, "recs.json", [bad])
    assert bfr.main(["assemble", "--records", recs]) == 1


def test_main_missing_file_returns_2(tmp_path):
    assert bfr.main(["assemble", "--records", str(tmp_path / "nope.json")]) == 2


def test_main_bad_json_returns_2(tmp_path):
    bad = tmp_path / "bad.json"
    bad.write_text("{not json", encoding="utf-8")
    assert bfr.main(["assemble", "--records", str(bad)]) == 2


# --------------------------------------------------------------------------- #
# IN1 受入: 組み立て結果が validate-source-citation.py を通る (end-to-end)      #
# --------------------------------------------------------------------------- #
def test_in1_assembled_output_passes_source_citation(tmp_path):
    result = bfr.assemble([_react_rec(), _postgres_rec()])
    refs = _write(tmp_path, "fetched-references.json", result)
    tgt = _write(tmp_path, "t.json", {"targets": [{"target_id": "react"}, {"target_id": "postgres"}]})
    assert vsc.main(["--targets", tgt, "--references", refs]) == 0


# --------------------------------------------------------------------------- #
# IN1 受入: fixture ファイルに対する validate-source-citation.py の正例/負例    #
# --------------------------------------------------------------------------- #
def test_in1_fixture_valid_exit0():
    targets = str(FIXTURES / "fixture-targets.json")
    refs = str(FIXTURES / "fixture-references-valid.json")
    assert vsc.main(["--targets", targets, "--references", refs]) == 0


def test_in1_fixture_missing_target_exit1(capsys):
    targets = str(FIXTURES / "fixture-targets.json")
    refs = str(FIXTURES / "fixture-references-missing.json")
    assert vsc.main(["--targets", targets, "--references", refs]) == 1
    assert "postgres" in capsys.readouterr().err


def test_in1_fixture_host_mismatch_exit1(capsys):
    targets = str(FIXTURES / "fixture-targets.json")
    refs = str(FIXTURES / "fixture-references-host-mismatch.json")
    assert vsc.main(["--targets", targets, "--references", refs]) == 1
    assert "official_host" in capsys.readouterr().err


def test_c02_contract_owns_seed_outside_candidate_qualification():
    skill = (SKILL_DIR / "SKILL.md").read_text(encoding="utf-8")
    identify = (SKILL_DIR / "prompts" / "R1-identify.md").read_text(encoding="utf-8")
    fetch = (SKILL_DIR / "prompts" / "R2-fetch.md").read_text(encoding="utf-8")
    record = (SKILL_DIR / "prompts" / "R3-record.md").read_text(encoding="utf-8")
    assert "Knowledge qualification担当" in skill
    assert "knowledge_candidates[].status=discovered" in identify
    assert "official_or_primary:true" in fetch
    assert "set-knowledge-candidate" in record
    assert "二次ブログだけではqualifiedにしない" in fetch
