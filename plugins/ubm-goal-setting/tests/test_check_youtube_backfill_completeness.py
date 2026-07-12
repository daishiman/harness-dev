"""check-youtube-backfill-completeness.py (C03) の完全性ゲート検証。

分母維持(denominator-maintenance)の不変則を機械確認する:
  - 全量 ingested → exit0 FULL_BACKFILL_PASS
  - 1 件 pending → exit1(未処理を分母から逃がさない)
  - temporary_failure ≥1 → exit1
  - 未承認 unavailable(waiver_ref 無しの terminal_unavailable)→ exit1
  - 承認参照付き waiver → accountability PASS(exit0)だが content_coverage は waived を 100% に数えない(分離)
  - 分母縮小の試み(registry に snapshot 外の ID・重複 ID・pagination 完走マーカー欠落)→ exit1
  - 同一入力で二回走らせても bit 一致(決定論)
fixture は tmp_path 内で自作し実 knowledge/ を汚さない(read-only ゲートなので書込は起こらない)。
"""
from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

PLUGIN_ROOT = Path(__file__).resolve().parents[1]
SKILL_DIR = PLUGIN_ROOT / "skills/run-ubm-youtube-ingest"
SCRIPT = SKILL_DIR / "scripts/check-youtube-backfill-completeness.py"
CHANNEL = "@北原孝彦のコンサルティング"


def run(*args: str) -> subprocess.CompletedProcess:
    return subprocess.run(
        [sys.executable, str(SCRIPT), *args],
        capture_output=True, text=True,
    )


def write_json(path: Path, obj: dict) -> Path:
    path.write_text(json.dumps(obj, ensure_ascii=False), encoding="utf-8")
    return path


def video_list(tmp_path: Path, video_ids, *, complete=True, snapshot_complete=True) -> Path:
    obj = {
        "snapshot_complete": snapshot_complete,
        "channels": {CHANNEL: {"complete": complete, "video_ids": list(video_ids)}},
    }
    return write_json(tmp_path / "video-list.json", obj)


def registry(tmp_path: Path, videos: dict, *, sources=None) -> Path:
    obj = {
        "schema_version": "1.0.0",
        "sources": sources or [
            {"priority": "required-primary", "handle": CHANNEL,
             "channel_id": "UC_kitahara", "status": "active"},
        ],
        "videos": videos,
    }
    return write_json(tmp_path / "youtube-registry.json", obj)


def vid(state: str, *, waiver_ref=None, source="UC_kitahara") -> dict:
    e = {"state": state, "idempotency_key": "x", "source": source}
    if waiver_ref is not None:
        e["waiver_ref"] = waiver_ref
    return e


def invoke(vl: Path, reg: Path) -> subprocess.CompletedProcess:
    return run("--channels", CHANNEL, "--video-list", str(vl), "--registry", str(reg))


# --- 通過系 ---------------------------------------------------------------
def test_all_ingested_is_full_backfill_pass(tmp_path: Path):
    vl = video_list(tmp_path, ["v1", "v2", "v3"])
    reg = registry(tmp_path, {
        "v1": vid("ingested"), "v2": vid("ingested"), "v3": vid("ingested"),
    })
    r = invoke(vl, reg)
    assert r.returncode == 0, r.stderr
    rep = json.loads(r.stdout)
    assert rep["discovered_total"] == 3
    assert rep["content_coverage"] == 1.0
    assert rep["accountability_coverage"] == 1.0
    assert rep["full_backfill_pass"] is True
    assert rep["accountability_pass"] is True
    assert rep["verdict"] == "FULL_BACKFILL_PASS"


# --- 分母維持: 未処理を分母から逃がさない ---------------------------------
def test_single_pending_fails(tmp_path: Path):
    vl = video_list(tmp_path, ["v1", "v2", "v3"])
    reg = registry(tmp_path, {"v1": vid("ingested"), "v2": vid("ingested")})  # v3 未処理
    r = invoke(vl, reg)
    assert r.returncode == 1
    rep = json.loads(r.stdout)
    assert rep["discovered_total"] == 3  # 分母は snapshot 起点で縮まない
    assert rep["breakdown"]["pending"] == 1
    assert rep["breakdown"]["ingested"] == 2
    assert rep["content_coverage"] < 1.0
    assert rep["verdict"] == "FAIL"
    assert "v3" in r.stderr


def test_temporary_failure_fails(tmp_path: Path):
    vl = video_list(tmp_path, ["v1", "v2"])
    reg = registry(tmp_path, {"v1": vid("ingested"), "v2": vid("temporary_failure")})
    r = invoke(vl, reg)
    assert r.returncode == 1
    rep = json.loads(r.stdout)
    assert rep["breakdown"]["temporary_failure"] == 1
    assert rep["verdict"] == "FAIL"
    assert "v2" in r.stderr


def test_unapproved_unavailable_fails(tmp_path: Path):
    vl = video_list(tmp_path, ["v1", "v2"])
    # terminal_unavailable だが waiver_ref 無し = 未承認 → 握り潰し禁止
    reg = registry(tmp_path, {"v1": vid("ingested"), "v2": vid("terminal_unavailable")})
    r = invoke(vl, reg)
    assert r.returncode == 1
    rep = json.loads(r.stdout)
    assert rep["breakdown"]["unapproved_unavailable"] == 1
    assert rep["verdict"] == "FAIL"
    assert "v2" in r.stderr


# --- 承認 waiver の分離検証 -----------------------------------------------
def test_approved_waiver_accountability_pass_but_content_not_100(tmp_path: Path):
    vl = video_list(tmp_path, ["v1", "v2", "v3"])
    reg = registry(tmp_path, {
        "v1": vid("ingested"), "v2": vid("ingested"),
        "v3": vid("waived", waiver_ref="user-approval-2026-07-11#slack"),
    })
    r = invoke(vl, reg)
    assert r.returncode == 0, r.stderr
    rep = json.loads(r.stdout)
    # accountability は通過するが content は waived を 100% に数えない(分離)
    assert rep["accountability_pass"] is True
    assert rep["full_backfill_pass"] is False
    assert rep["verdict"] == "ACCOUNTABILITY_PASS"
    assert rep["content_coverage"] < 1.0  # 2/3
    assert rep["accountability_coverage"] == 1.0  # 2/(3-1)
    assert rep["accountability_denominator"] == 2
    assert rep["breakdown"]["waived"] == 1
    assert rep["breakdown"]["ingested"] == 2


def test_approved_terminal_unavailable_is_accountable(tmp_path: Path):
    vl = video_list(tmp_path, ["v1", "v2"])
    reg = registry(tmp_path, {
        "v1": vid("ingested"),
        "v2": vid("terminal_unavailable", waiver_ref="user-ack-deleted#2026-07-11"),
    })
    r = invoke(vl, reg)
    assert r.returncode == 0, r.stderr
    rep = json.loads(r.stdout)
    assert rep["accountability_pass"] is True
    assert rep["full_backfill_pass"] is False
    assert rep["breakdown"]["approved_unavailable"] == 1
    assert rep["content_coverage"] == 0.5  # 1/2 実 ingested のみ


def test_waived_without_ref_fails(tmp_path: Path):
    vl = video_list(tmp_path, ["v1", "v2"])
    reg = registry(tmp_path, {"v1": vid("ingested"), "v2": vid("waived")})  # waiver_ref 欠落
    r = invoke(vl, reg)
    assert r.returncode == 1
    rep = json.loads(r.stdout)
    assert rep["breakdown"]["waiver_missing"] == 1
    assert rep["verdict"] == "FAIL"
    assert "v2" in r.stderr


# --- 分母縮小の試みを拒否 -------------------------------------------------
def test_registry_id_absent_from_snapshot_fails(tmp_path: Path):
    # registry に検査対象 channel 由来の ID があるのに snapshot に無い = 分母縮小/取りこぼし疑い。
    vl = video_list(tmp_path, ["v1", "v2"])
    reg = registry(tmp_path, {
        "v1": vid("ingested"), "v2": vid("ingested"),
        "v3": vid("waived", waiver_ref="ref", source="UC_kitahara"),  # snapshot に無い
    })
    r = invoke(vl, reg)
    assert r.returncode == 1
    assert "v3" in r.stderr
    assert "分母縮小" in r.stderr


def test_duplicate_id_in_snapshot_fails(tmp_path: Path):
    vl = video_list(tmp_path, ["v1", "v2", "v2"])  # 重複
    reg = registry(tmp_path, {"v1": vid("ingested"), "v2": vid("ingested")})
    r = invoke(vl, reg)
    assert r.returncode == 1
    assert "v2" in r.stderr
    assert "重複" in r.stderr


def test_pagination_marker_missing_fails(tmp_path: Path):
    # 完走マーカー(complete/snapshot_complete)が false = pagination 欠落 → fail-closed
    vl = video_list(tmp_path, ["v1", "v2"], complete=False, snapshot_complete=False)
    reg = registry(tmp_path, {"v1": vid("ingested"), "v2": vid("ingested")})
    r = invoke(vl, reg)
    assert r.returncode == 1
    assert "pagination" in r.stderr


# --- fail-closed / usage --------------------------------------------------
def test_missing_registry_is_all_pending_fail(tmp_path: Path):
    vl = video_list(tmp_path, ["v1", "v2"])
    r = run("--channels", CHANNEL, "--video-list", str(vl),
            "--registry", str(tmp_path / "does-not-exist.json"))
    assert r.returncode == 1
    rep = json.loads(r.stdout)
    assert rep["breakdown"]["pending"] == 2


def test_corrupt_registry_fails_closed(tmp_path: Path):
    vl = video_list(tmp_path, ["v1"])
    bad = tmp_path / "youtube-registry.json"
    bad.write_text("{ this is not json", encoding="utf-8")
    r = invoke(vl, bad)
    assert r.returncode == 1
    rep = json.loads(r.stdout)
    assert rep["verdict"] == "FAIL"


def test_unreadable_video_list_is_usage_error(tmp_path: Path):
    reg = registry(tmp_path, {})
    r = run("--channels", CHANNEL, "--video-list", str(tmp_path / "nope.json"),
            "--registry", str(reg))
    assert r.returncode == 2


def test_missing_required_args_is_usage_error():
    r = run("--channels", CHANNEL)  # --video-list / --registry 欠落
    assert r.returncode == 2


# --- 決定論 ---------------------------------------------------------------
def test_deterministic_output(tmp_path: Path):
    vl = video_list(tmp_path, ["v3", "v1", "v2"])  # 敢えて非ソート順
    reg = registry(tmp_path, {
        "v1": vid("ingested"), "v2": vid("temporary_failure"), "v3": vid("ingested"),
    })
    r1 = invoke(vl, reg)
    r2 = invoke(vl, reg)
    assert r1.stdout == r2.stdout
    assert r1.stderr == r2.stderr
    assert r1.returncode == r2.returncode == 1
