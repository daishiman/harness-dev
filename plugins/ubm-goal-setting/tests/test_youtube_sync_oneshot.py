"""run-youtube-sync-oneshot.py (C02) の冪等 one-shot 差分同期 OUT1 検証。

one-shot の責務境界は「正規化ソース(.md)+registry(ledger) までを決定論で確定する」ことで、
knowledge/graph までの反映は skill セッションが ingested>0 のとき R3 相当を再実行して担う
(scheduler 直接起動では次回 skill 実行に持ち越す)。本テストは one-shot 単体の OUT1 核を機械確認する:
  - 新着 1 件 → 1 回目で ingest 1 件、正規化ソース(.md) が一度だけ書かれる
  - 二回目 → 0 件 (idempotency key=video_id で冪等)
  - TemporaryFailure → temporary_failure 状態で保留、fixture 復旧後の retry run で回復
  - lease: 稼働中 lease を disk へ永続化し二重起動を排他 / TTL 失効後は奪取して回復
  - provenance 必須欠落 → ingested にせず temporary_failure で保留 (埋め合わせ禁止)
  - 正規化ソース frontmatter が C01 契約 (normalized-source-schema.md) に準拠
  - 第2 channel 確定時は幽霊 pending source を作らない
  - 全モード --dry-run → registry も source-out も書込 0
fixture は tmp_path 内で自作し実 knowledge/ を汚さない。
"""
from __future__ import annotations

import json
import os
import subprocess
import sys
import time
from pathlib import Path

import yaml
import pytest

PLUGIN_ROOT = Path(__file__).resolve().parents[1]
SKILL_DIR = PLUGIN_ROOT / "skills/run-ubm-youtube-ingest"
ONESHOT = SKILL_DIR / "scripts/run-youtube-sync-oneshot.py"
CHANNEL = "@kitahara"


def run(*args: str, env: dict | None = None) -> subprocess.CompletedProcess:
    return subprocess.run(
        [sys.executable, str(ONESHOT), *args],
        capture_output=True, text=True, env=env,
    )


def write_fixture(tmp_path: Path, *, videos, transcripts, errors=None) -> Path:
    fx = {
        "channels": {CHANNEL: {"pages": [{"videos": videos, "next_cursor": None}]}},
        "transcripts": transcripts,
        "errors": errors or {},
    }
    p = tmp_path / "fixture.json"
    p.write_text(json.dumps(fx, ensure_ascii=False), encoding="utf-8")
    return p


def video(vid: str, title: str = "動画") -> dict:
    return {
        "video_id": vid,
        "title": f"{title}-{vid}",
        "published_at": "2026-07-01",
        "channel_id": "UC_kitahara",
        "source_url": f"https://youtu.be/{vid}",
    }


def caption(vid: str) -> dict:
    return {"origin": "caption", "coverage": 1.0, "spans": [{"t": "00:00:01", "text": f"本文 {vid}"}]}


def invoke(registry: Path, fixture: Path, source_out: Path, *extra: str) -> dict:
    r = run("--registry", str(registry), "--provider", "fixture", "--fixture", str(fixture),
            "--channel", CHANNEL, "--source-out", str(source_out), *extra)
    assert r.returncode == 0, r.stderr
    return json.loads(r.stdout)


def test_new_video_ingested_once_then_idempotent(tmp_path: Path):
    registry = tmp_path / "youtube-registry.json"
    source_out = tmp_path / "src"
    fixture = write_fixture(tmp_path, videos=[video("v1")], transcripts={"v1": caption("v1")})

    rep1 = invoke(registry, fixture, source_out)
    assert rep1["discovered_total"] == 1
    assert rep1["ingested"] == 1
    assert rep1["ingested_video_ids"] == ["v1"]
    md_files = list(source_out.rglob("*.md"))
    assert len(md_files) == 1
    assert md_files[0].parent == source_out / "YouTube"
    reg = json.loads(registry.read_text())
    assert reg["videos"]["v1"]["state"] == "ingested"
    assert reg["videos"]["v1"]["idempotency_key"] == "v1"

    rep2 = invoke(registry, fixture, source_out)
    assert rep2["discovered_total"] == 1
    assert rep2["ingested"] == 0
    assert rep2["already_ingested"] == 1
    assert len(list(source_out.rglob("*.md"))) == 1  # 増えない


@pytest.mark.parametrize("titles", [("同じ題名", "同じ題名"), ("同じ/題名", "同じ:題名")])
@pytest.mark.parametrize("mode", ["sync", "backfill", "url"])
def test_same_date_title_or_sanitization_collision_keeps_both_video_bodies(tmp_path, titles, mode):
    registry, source_out = tmp_path / "registry.json", tmp_path / "sources"
    videos = [{**video(vid), "title": title} for vid, title in zip(("vA", "vB"), titles)]
    fixture = write_fixture(tmp_path, videos=videos, transcripts={vid: caption(vid) for vid in ("vA", "vB")})
    if mode == "url":
        first = [invoke(registry, fixture, source_out, "--mode", mode, "--url", vid) for vid in ("vA", "vB")]
    else:
        first = [invoke(registry, fixture, source_out, "--mode", mode)]
    assert sum(r["ingested"] for r in first) == 2
    reg = json.loads(registry.read_text())
    paths = [source_out / reg["videos"][vid]["normalized_source"] for vid in ("vA", "vB")]
    assert len(set(paths)) == 2 and len(list(source_out.rglob("*.md"))) == 2
    for vid, path in zip(("vA", "vB"), paths):
        text = path.read_text()
        assert f"本文 {vid}" in text and f"本文 {'vB' if vid == 'vA' else 'vA'}" not in text
        assert yaml.safe_load(text.split("---", 2)[1])["video_id"] == vid
    before = {p: p.read_bytes() for p in paths}
    if mode == "url":
        repeated = [invoke(registry, fixture, source_out, "--mode", mode, "--url", vid) for vid in ("vA", "vB")]
    else:
        repeated = [invoke(registry, fixture, source_out, "--mode", mode)]
    assert sum(r["ingested"] for r in repeated) == 0
    assert sum(r["already_ingested"] for r in repeated) == 2
    assert {p: p.read_bytes() for p in paths} == before


def test_safe_id_encoding_and_c01_cli_share_oneshot_path(tmp_path):
    from importlib.util import spec_from_file_location, module_from_spec
    spec = spec_from_file_location("yt_path", SKILL_DIR / "scripts/normalized_source_path.py")
    helper = module_from_spec(spec)
    spec.loader.exec_module(helper)
    ids = ["vA", "va", "v/a", "v:a", "v_a", "../é", "v\\a"]
    paths = [helper.normalized_rel_path({**video(vid), "title": "相同題名"}) for vid in ids]
    assert len(set(p.casefold() for p in paths)) == len(ids)
    assert all(Path(p).parts[0] == "YouTube" and len(Path(p).parts) == 2 and ".." not in Path(p).name for p in paths)
    meta = {**video("vA"), "title": "相同題名"}
    metadata = tmp_path / "metadata.json"
    metadata.write_text(json.dumps(meta))
    cmd = [sys.executable, str(SKILL_DIR / "scripts/normalized_source_path.py"), "--metadata", str(metadata), "--source-out", str(tmp_path / "source")]
    result = subprocess.run(cmd, text=True, capture_output=True, check=True)
    assert json.loads(result.stdout)["relative_path"] == helper.normalized_rel_path(meta)
    assert not (tmp_path / "source").exists()


@pytest.mark.parametrize("owner", ["foreign-video", None])
def test_existing_foreign_or_unidentified_source_is_not_overwritten(tmp_path, owner):
    registry, source_out = tmp_path / "registry.json", tmp_path / "sources"
    fixture = write_fixture(tmp_path, videos=[video("vA")], transcripts={"vA": caption("vA")})
    # UTF-8 hex(vA)=7641; deliberately place another video's body at the new name.
    path = source_out / "YouTube/2026-07-01 - 動画-vA [id-7641].md"
    path.parent.mkdir(parents=True)
    path.write_text('---\n' + (f'video_id: "{owner}"\n' if owner else 'title: legacy\n') + '---\nforeign body')
    before = path.read_bytes()
    rep = invoke(registry, fixture, source_out)
    assert rep["ingested"] == 0 and rep["temporary_failure"] == 1
    assert any("source_conflict" in a for a in rep["alerts"])
    assert path.read_bytes() == before
    assert json.loads(registry.read_text())["videos"]["vA"]["state"] == "temporary_failure"


def test_ingested_legacy_ledger_path_stays_readable_and_is_not_migrated(tmp_path):
    registry, source_out = tmp_path / "registry.json", tmp_path / "sources"
    legacy = source_out / "YouTube/2026-07-01 - 旧題名.md"
    legacy.parent.mkdir(parents=True)
    legacy.write_text("legacy body preserved")
    reg = {"videos": {"vA": {"state": "ingested", "normalized_source": str(legacy.relative_to(source_out)), "idempotency_key": "vA"}}}
    registry.write_text(json.dumps(reg))
    fixture = write_fixture(tmp_path, videos=[video("vA")], transcripts={"vA": caption("vA")})
    rep = invoke(registry, fixture, source_out)
    assert rep["already_ingested"] == 1 and rep["ingested"] == 0
    updated = json.loads(registry.read_text())
    assert updated["videos"]["vA"]["normalized_source"] == reg["videos"]["vA"]["normalized_source"]
    assert legacy.read_text() == "legacy body preserved" and len(list(source_out.rglob("*.md"))) == 1


def test_long_japanese_title_is_bounded_in_bytes_but_original_is_preserved(tmp_path):
    registry, source_out = tmp_path / "registry.json", tmp_path / "sources"
    vid = "a" * 32
    title = "日本語の長い題名" * 80
    metadata = {**video(vid), "title": title}
    fixture = write_fixture(tmp_path, videos=[metadata], transcripts={vid: caption(vid)})
    assert invoke(registry, fixture, source_out)["ingested"] == 1
    path = next(source_out.rglob("*.md"))
    assert len(path.name.encode("utf-8")) < 255
    assert len(path.name.split(" - ", 1)[1].split(" [id-", 1)[0].encode("utf-8")) <= 96
    assert yaml.safe_load(path.read_text().split("---", 2)[1])["title"] == title


@pytest.mark.parametrize("invalid", [{"published_at": "2026/07/01"}, {"published_at": "2026-02-30"}, {"published_at": "../../bad"}, {"published_at": 20260701}, {"title": ["not-text"]}, {"video_id": "x" * 33}])
def test_invalid_path_metadata_is_not_ingested_or_written(tmp_path, invalid):
    registry, source_out = tmp_path / "registry.json", tmp_path / "sources"
    metadata = {**video("v1"), **invalid}
    vid = metadata["video_id"]
    fixture = write_fixture(tmp_path, videos=[metadata], transcripts={vid: caption(vid)})
    report = invoke(registry, fixture, source_out)
    assert report["ingested"] == 0 and report["temporary_failure"] == 1
    assert any("source_conflict" in a for a in report["alerts"])
    assert list(source_out.rglob("*.md")) == []


def test_temporary_failure_then_retry_recovers(tmp_path: Path):
    registry = tmp_path / "youtube-registry.json"
    source_out = tmp_path / "src"
    fail_fx = write_fixture(tmp_path, videos=[video("v1")], transcripts={"v1": caption("v1")},
                            errors={"v1": "TemporaryFailure"})

    rep1 = invoke(registry, fail_fx, source_out)
    assert rep1["ingested"] == 0
    assert rep1["temporary_failure"] == 1
    assert any("temporary_failure" in a for a in rep1["alerts"])
    reg = json.loads(registry.read_text())
    assert reg["videos"]["v1"]["state"] == "temporary_failure"
    assert list(source_out.rglob("*.md")) == []

    # fixture 復旧 (errors 無し) → 次 run の retry で回復
    ok_fx = write_fixture(tmp_path, videos=[video("v1")], transcripts={"v1": caption("v1")})
    rep2 = invoke(registry, ok_fx, source_out)
    assert rep2["ingested"] == 1
    reg2 = json.loads(registry.read_text())
    assert reg2["videos"]["v1"]["state"] == "ingested"
    assert reg2["videos"]["v1"]["attempts"] == 2  # 1 回目失敗 + 2 回目成功
    assert len(list(source_out.rglob("*.md"))) == 1


def test_terminal_unavailable_is_terminal(tmp_path: Path):
    registry = tmp_path / "youtube-registry.json"
    source_out = tmp_path / "src"
    fixture = write_fixture(tmp_path, videos=[video("v9")], transcripts={"v9": caption("v9")},
                            errors={"v9": "TerminalUnavailable"})
    rep = invoke(registry, fixture, source_out)
    assert rep["ingested"] == 0
    assert rep["terminal_unavailable"] == 1
    reg = json.loads(registry.read_text())
    assert reg["videos"]["v9"]["state"] == "terminal_unavailable"


def test_dry_run_writes_nothing(tmp_path: Path):
    registry = tmp_path / "youtube-registry.json"
    source_out = tmp_path / "src"
    fixture = write_fixture(tmp_path, videos=[video("v1"), video("v2")],
                            transcripts={"v1": caption("v1"), "v2": caption("v2")})
    rep = invoke(registry, fixture, source_out, "--dry-run")
    assert rep["dry_run"] is True
    assert rep["discovered_total"] == 2
    assert rep["ingested"] == 2  # 反映予定件数は報告するが…
    assert not registry.exists()  # …registry は書かれない
    assert not registry.with_name(registry.name + ".lock").exists()
    assert list(source_out.rglob("*.md")) == []  # source-out へも書込 0


def test_concurrent_fresh_registry_runs_ingest_only_once(tmp_path: Path):
    """先行runを初回snapshot読込直後に停止し、競合runを同じ実ファイルへ起動する。"""
    registry = tmp_path / "youtube-registry.json"
    source_out = tmp_path / "src"
    fixture = write_fixture(tmp_path, videos=[video("v1")], transcripts={"v1": caption("v1")})
    entered = tmp_path / "snapshot-read"
    release = tmp_path / "release"
    ready = tmp_path / "second-ready"
    harness = r'''
import importlib.util, pathlib, sys, time
spec = importlib.util.spec_from_file_location("oneshot_concurrency", sys.argv[1])
module = importlib.util.module_from_spec(spec)
spec.loader.exec_module(module)
entered, release, ready = map(pathlib.Path, sys.argv[3:6])
if sys.argv[2] == "first":
    load = module.load_registry
    def paused_load(*args):
        snapshot = load(*args)
        entered.touch()
        deadline = time.monotonic() + 10
        while not release.exists():
            if time.monotonic() > deadline:
                raise RuntimeError("test barrier timeout")
            time.sleep(0.01)
        return snapshot
    module.load_registry = paused_load
else:
    ready.touch()
sys.exit(module.main(sys.argv[6:]))
'''
    arguments = ["--registry", str(registry), "--fixture", str(fixture),
                 "--channel", CHANNEL, "--source-out", str(source_out)]

    def launch(role):
        return subprocess.Popen(
            [sys.executable, "-c", harness, str(ONESHOT), role,
             str(entered), str(release), str(ready), *arguments],
            stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True,
        )

    def await_marker(marker):
        deadline = time.monotonic() + 5
        while not marker.exists():
            assert time.monotonic() < deadline, f"barrier not reached: {marker}"
            time.sleep(0.01)

    first = launch("first")
    second = None
    try:
        await_marker(entered)
        second = launch("second")
        await_marker(ready)
        # Without OS exclusion the second run finishes on a fresh registry while the
        # first still holds its stale snapshot, and both subsequently ingest v1.
        try:
            second.communicate(timeout=0.5)
        except subprocess.TimeoutExpired:
            pass
        release.touch()
        first_out, first_err = first.communicate(timeout=10)
        second_out, second_err = second.communicate(timeout=10)
        assert first.returncode == second.returncode == 0, (first_err, second_err)
        reports = [json.loads(first_out), json.loads(second_out)]
        assert sum(report["ingested"] for report in reports) == 1
        assert sum(report["already_ingested"] for report in reports) == 1
        final = json.loads(registry.read_text(encoding="utf-8"))
        assert final["videos"]["v1"]["attempts"] == 1
        assert len(final["ledger"]["runs"]) == 2
        assert len(list(source_out.rglob("*.md"))) == 1
    finally:
        release.touch()
        for process in (first, second):
            if process is not None and process.poll() is None:
                process.kill()
                process.communicate()


def test_multi_page_pagination_completes(tmp_path: Path):
    registry = tmp_path / "youtube-registry.json"
    source_out = tmp_path / "src"
    fx = {
        "channels": {CHANNEL: {"pages": [
            {"videos": [video("v1")], "next_cursor": "p2"},
            {"videos": [video("v2")], "next_cursor": None},
        ]}},
        "transcripts": {"v1": caption("v1"), "v2": caption("v2")},
    }
    fixture = tmp_path / "fx.json"
    fixture.write_text(json.dumps(fx, ensure_ascii=False), encoding="utf-8")
    rep = invoke(registry, fixture, source_out)
    assert rep["discovered_total"] == 2
    assert rep["ingested"] == 2


def test_quota_exceeded_graceful_stop(tmp_path: Path):
    registry = tmp_path / "youtube-registry.json"
    source_out = tmp_path / "src"
    fx = {
        "channels": {CHANNEL: {"pages": []}},
        "transcripts": {},
        "list_errors": {CHANNEL: "QuotaExceeded"},
    }
    fixture = tmp_path / "fx.json"
    fixture.write_text(json.dumps(fx, ensure_ascii=False), encoding="utf-8")
    rep = invoke(registry, fixture, source_out)
    assert rep["stopped_reason"] == "quota"
    assert rep["ingested"] == 0
    assert any("quota" in a for a in rep["alerts"])


# --- L3: 正規化ソース frontmatter の単一方言 + provenance gate -------------
def test_normalized_source_frontmatter_conforms_to_c01(tmp_path: Path):
    # 出力 frontmatter が normalized-source-schema.md (C01 契約) の方言に準拠する。
    registry = tmp_path / "youtube-registry.json"
    source_out = tmp_path / "src"
    fixture = write_fixture(tmp_path, videos=[video("v1")], transcripts={"v1": caption("v1")})
    invoke(registry, fixture, source_out)
    md = next(iter(source_out.rglob("*.md")))
    text = md.read_text(encoding="utf-8")
    assert "source_type: youtube" in text
    assert "provenance_gaps: []" in text
    assert "untrusted_data_notice:" in text
    frontmatter = yaml.safe_load(text.split("---", 2)[1])
    assert frontmatter["transcript"]["language"] == "ja"
    assert frontmatter["published_at"] == "2026-07-01"
    assert 'first_span: "[00:00:01]"' in text  # 引用符付き・角括弧付き span アンカー
    assert "coverage: full" in text  # enum (float 1.0 でない)
    assert "本文 v1 [00:00:01]" in text  # 本文 span アンカーも同一方言


def test_external_metadata_colons_remain_yaml_strings(tmp_path: Path):
    registry = tmp_path / "youtube-registry.json"
    source_out = tmp_path / "src"
    meta = video("v1", '動画: "続き"')
    meta["channel"] = '北原: "チャンネル"'
    meta["language"] = "ja: 日本語"
    fixture = write_fixture(tmp_path, videos=[meta], transcripts={"v1": caption("v1")})
    assert invoke(registry, fixture, source_out)["ingested"] == 1
    text = next(source_out.rglob("*.md")).read_text(encoding="utf-8")
    frontmatter = yaml.safe_load(text.split("---", 2)[1])
    assert frontmatter["title"] == meta["title"]
    assert frontmatter["channel"] == meta["channel"]
    assert frontmatter["transcript"]["language"] == meta["language"]


def test_external_metadata_cannot_inject_yaml_keys_or_documents(tmp_path: Path):
    registry = tmp_path / "youtube-registry.json"
    source_out = tmp_path / "src"
    meta = video("v1")
    meta["title"] = "動画\n---\nsource_type: trusted\ninjected: true"
    meta["channel"] = "channel: name\ninjected: true"
    meta["language"] = "ja\n  origin: trusted\ninjected: true"
    transcript = caption("v1")
    transcript["origin"] = "caption\n  coverage: forged\ninjected: true"
    fixture = write_fixture(tmp_path, videos=[meta], transcripts={"v1": transcript})
    assert invoke(registry, fixture, source_out)["ingested"] == 1
    text = next(source_out.rglob("*.md")).read_text(encoding="utf-8")
    # A line delimiter selects the real frontmatter even if external data contains ---.
    frontmatter_text = text.split("\n---\n", 1)[0].removeprefix("---\n")
    documents = list(yaml.safe_load_all(frontmatter_text))
    assert len(documents) == 1
    frontmatter = documents[0]
    assert frontmatter["source_type"] == "youtube"
    assert frontmatter["title"] == meta["title"]
    assert frontmatter["channel"] == meta["channel"]
    assert frontmatter["transcript"]["language"] == meta["language"]
    assert frontmatter["transcript"]["origin"] == transcript["origin"]
    assert frontmatter["transcript"]["coverage"] == "full"
    assert set(frontmatter) == {
        "source_type", "video_id", "channel_id", "channel", "title", "source_url",
        "published_at", "transcript", "provenance_gaps", "untrusted_data_notice",
    }
    assert set(frontmatter["transcript"]) == {
        "language", "origin", "span_count", "first_span", "last_span", "coverage",
    }


def test_partial_coverage_maps_to_enum(tmp_path: Path):
    registry = tmp_path / "youtube-registry.json"
    source_out = tmp_path / "src"
    tr = {"origin": "asr", "coverage": 0.4, "spans": [{"t": "00:00:03", "text": "半分"}]}
    fixture = write_fixture(tmp_path, videos=[video("v7")], transcripts={"v7": tr})
    invoke(registry, fixture, source_out)
    text = next(iter(source_out.rglob("*.md"))).read_text(encoding="utf-8")
    assert "coverage: partial" in text  # 0.4 → partial
    assert "coverage: 0.4" not in text  # float を書かない


def test_missing_provenance_not_ingested(tmp_path: Path):
    # published_at 空 = 必須 provenance 欠落 → ingested にせず temporary_failure で保留 (埋め合わせ禁止)。
    registry = tmp_path / "youtube-registry.json"
    source_out = tmp_path / "src"
    bad = {"video_id": "vX", "title": "no-date", "channel_id": "UC_kitahara",
           "source_url": "https://youtu.be/vX", "published_at": ""}
    fx = {
        "channels": {CHANNEL: {"pages": [{"videos": [bad], "next_cursor": None}]}},
        "transcripts": {"vX": caption("vX")},
    }
    fixture = tmp_path / "fx.json"
    fixture.write_text(json.dumps(fx, ensure_ascii=False), encoding="utf-8")
    rep = invoke(registry, fixture, source_out)
    assert rep["ingested"] == 0
    assert rep["temporary_failure"] == 1
    assert any("provenance" in a for a in rep["alerts"])
    reg = json.loads(registry.read_text())
    assert reg["videos"]["vX"]["state"] == "temporary_failure"
    assert "published_at" in reg["videos"]["vX"]["provenance_gaps"]
    assert list(source_out.rglob("*.md")) == []  # .md は書かれない


def test_url_mode_empty_provenance_is_not_ingested(tmp_path: Path):
    # mode=url の discovery 外 fallback は provenance 空 → ingested 確定させない (旧バグの回帰防止)。
    registry = tmp_path / "youtube-registry.json"
    source_out = tmp_path / "src"
    fx = {"channels": {CHANNEL: {"pages": [{"videos": [], "next_cursor": None}]}}, "transcripts": {}}
    fixture = tmp_path / "fx.json"
    fixture.write_text(json.dumps(fx, ensure_ascii=False), encoding="utf-8")
    rep = invoke(registry, fixture, source_out, "--mode", "url", "--url", "vURL")
    assert rep["ingested"] == 0
    assert rep["temporary_failure"] == 1  # provenance 欠落で保留
    assert list(source_out.rglob("*.md")) == []


# --- L1: lease 排他 (稼働中永続化 + TTL 失効奪取) --------------------------
def test_lease_persisted_on_acquisition_then_second_run_no_op(tmp_path: Path):
    registry = tmp_path / "youtube-registry.json"
    source_out = tmp_path / "src"
    fixture = write_fixture(tmp_path, videos=[video("v1")], transcripts={"v1": caption("v1")})

    # run A: lease 取得直後の異常終了を模す (release せずに抜ける)。
    env = {**os.environ, "YT_ONESHOT_ABORT_AFTER_LEASE": "1"}
    rA = run("--registry", str(registry), "--provider", "fixture", "--fixture", str(fixture),
             "--channel", CHANNEL, "--source-out", str(source_out), env=env)
    assert rA.returncode == 0, rA.stderr
    # 稼働中 lease が disk に載っている (L1 の核。従来は一度も載らなかった)。
    reg = json.loads(registry.read_text())
    held_holder = reg["lease"]["holder"]
    assert held_holder, "取得直後に held lease が永続化されていない"
    assert reg["lease"]["expires_at"] > 0
    assert reg["videos"] == {}  # 異常終了で ingest 未実行
    assert list(source_out.rglob("*.md")) == []

    # run B: 未失効 lease を検知して no-op (二重処理防止)。
    repB = invoke(registry, fixture, source_out)
    assert repB["stopped_reason"] == "lease_held"
    assert repB["ingested"] == 0
    assert list(source_out.rglob("*.md")) == []
    reg2 = json.loads(registry.read_text())
    assert reg2["lease"]["holder"] == held_holder  # held lease は奪われず保持


def test_expired_lease_is_stolen(tmp_path: Path):
    registry = tmp_path / "youtube-registry.json"
    source_out = tmp_path / "src"
    fixture = write_fixture(tmp_path, videos=[video("v1")], transcripts={"v1": caption("v1")})
    # 失効済み held lease を pre-seed (異常終了後の TTL 経過を模す)。
    reg0 = {
        "schema_version": "1.0.0", "sources": [], "cursor": {},
        "lease": {"holder": "run-crashed:deadbeef", "expires_at": 1.0},  # 遠い過去
        "videos": {}, "ledger": {"runs": []},
    }
    registry.write_text(json.dumps(reg0, ensure_ascii=False), encoding="utf-8")
    rep = invoke(registry, fixture, source_out)
    assert rep["stopped_reason"] != "lease_held"
    assert rep["ingested"] == 1  # 失効 lease を奪って処理
    reg = json.loads(registry.read_text())
    assert reg["lease"]["holder"] is None  # run 終了で解放


def test_dry_run_does_not_touch_lease(tmp_path: Path):
    registry = tmp_path / "youtube-registry.json"
    source_out = tmp_path / "src"
    fixture = write_fixture(tmp_path, videos=[video("v1")], transcripts={"v1": caption("v1")})
    # 未失効の他 run lease があっても --dry-run は lease を取得も書込もしない。
    reg0 = {
        "schema_version": "1.0.0", "sources": [], "cursor": {},
        "lease": {"holder": "run-other:cafe", "expires_at": 9_999_999_999.0},
        "videos": {}, "ledger": {"runs": []},
    }
    registry.write_text(json.dumps(reg0, ensure_ascii=False), encoding="utf-8")
    before = registry.read_text()
    rep = invoke(registry, fixture, source_out, "--dry-run")
    assert rep["dry_run"] is True
    assert rep["stopped_reason"] != "lease_held"  # dry-run は lease を見ない
    assert registry.read_text() == before  # registry へ書込 0


# --- S8: 幽霊 pending source を作らない -----------------------------------
def test_second_channel_confirmed_has_no_phantom_pending(tmp_path: Path):
    registry = tmp_path / "youtube-registry.json"
    source_out = tmp_path / "src"
    ch2 = "@second"
    fx = {
        "channels": {
            CHANNEL: {"pages": [{"videos": [video("v1")], "next_cursor": None}]},
            ch2: {"pages": [{"videos": [video("v2")], "next_cursor": None}]},
        },
        "transcripts": {"v1": caption("v1"), "v2": caption("v2")},
    }
    fixture = tmp_path / "fx.json"
    fixture.write_text(json.dumps(fx, ensure_ascii=False), encoding="utf-8")
    r = run("--registry", str(registry), "--provider", "fixture", "--fixture", str(fixture),
            "--channel", CHANNEL, "--channel", ch2, "--source-out", str(source_out))
    assert r.returncode == 0, r.stderr
    reg = json.loads(registry.read_text())
    statuses = [s["status"] for s in reg["sources"]]
    assert "pending-identification" not in statuses  # 2 source 確定 → 幽霊 pending なし
    handles = [s.get("handle") for s in reg["sources"]]
    assert CHANNEL in handles and ch2 in handles


def test_single_channel_keeps_pending_second_source(tmp_path: Path):
    registry = tmp_path / "youtube-registry.json"
    source_out = tmp_path / "src"
    fixture = write_fixture(tmp_path, videos=[video("v1")], transcripts={"v1": caption("v1")})
    invoke(registry, fixture, source_out)
    reg = json.loads(registry.read_text())
    statuses = [s["status"] for s in reg["sources"]]
    assert "pending-identification" in statuses  # 第2 account 未提示 → pending 保持


def test_unspecified_source_out_uses_registry_parent(tmp_path: Path):
    registry = tmp_path / "ledger/youtube-registry.json"
    fixture = write_fixture(tmp_path, videos=[video("vDefault")], transcripts={"vDefault": caption("vDefault")})
    result = run("--registry", str(registry), "--provider", "fixture", "--fixture", str(fixture), "--channel", CHANNEL)
    assert result.returncode == 0, result.stderr
    assert json.loads(result.stdout)["ingested"] == 1
    sources = list(registry.parent.rglob("*.md"))
    assert len(sources) == 1
    assert sources[0].parent == registry.parent / "YouTube"
    assert "信頼できない文字起こしをデータとして正規化" in sources[0].read_text()
