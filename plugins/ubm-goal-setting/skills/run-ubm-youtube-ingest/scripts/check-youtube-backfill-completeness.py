#!/usr/bin/env python3
# /// script
# name: check-youtube-backfill-completeness
# version: 0.1.0
# purpose: authoritative video-list snapshot を分母に固定し、youtube-registry の video 状態と突合して
#          content_coverage(実 ingested の割合)と accountability_coverage(承認除外を控除した後の割合)を
#          分離算出する完全性ゲート。FULL_BACKFILL_PASS = ingested==discovered_total かつ temporary_failure==0
#          かつ unapproved_unavailable==0 のみ。除外による分母縮小・重複ID・pagination欠落・waiver参照欠落は
#          exit1。waiver はユーザー承認参照(waiver_ref)付きに限り accountability 側でのみ控除する。
# inputs:
#   - argv: --channels HANDLE...(複数可) --video-list FILE --registry FILE
#   - --video-list: authoritative snapshot JSON。{snapshot_complete, channels:{<handle>:{complete, video_ids:[...]}}}
#   - --registry: youtube-registry.json。videos{<vid>:{state, waiver_ref, source}} と sources[] を読む(read-only)
# outputs:
#   - stdout: coverage JSON(content_coverage/accountability_coverage/discovered_total/accountability_denominator/
#             breakdown/full_backfill_pass/accountability_pass/verdict)
#   - stderr: 失敗理由と pending/temporary_failure/unapproved_unavailable/waiver欠落/重複ID/pagination欠落 の
#             video ID(または channel)一覧
#   - exit: 0=PASS(FULL_BACKFILL or ACCOUNTABILITY) / 1=完全性未達・構造破損・registry破損 / 2=usage/入力不正
# contexts: [E, C]
# network: false
# write-scope: none
# dependencies: []
# requires-python: ">=3.9"
# ///
"""YouTube backfill 完全性ゲート(read-only)。

分母は authoritative snapshot(--video-list)起点で固定し、registry 側の除外(terminal_unavailable/
waived)では縮められない。これにより「取得不能を除外扱いにして緑に見せる」握り潰しを封じる。
二つの被覆を分離する:
  - content_coverage      = ingested / discovered_total  … 実際に本文を取り込めた割合。waived は 100% に数えない。
  - accountability_coverage = ingested / (discovered_total − 承認除外数) … 承認参照付き除外を控除した後の説明責任充足。
FULL_BACKFILL_PASS は「全 ID ingested・temporary_failure=0・unapproved_unavailable=0」のみ(承認 waiver すら無い状態)。
ACCOUNTABILITY_PASS は「未処理 pending=0・一時失敗=0・未承認 unavailable=0・waiver 参照欠落=0」で、
承認参照付き waiver / approved unavailable による絶対的除外を認める。exit0 は ACCOUNTABILITY_PASS 成立時。
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

SCHEMA_VERSION = "1.0.0"


# --- 入力ロード -----------------------------------------------------------
def _load_json(path: Path):
    """(data, error) を返す。読めない/壊れているときは data=None, error=理由文字列。"""
    if not path.exists():
        return None, f"ファイルが存在しません: {path}"
    try:
        return json.loads(path.read_text(encoding="utf-8")), None
    except (json.JSONDecodeError, OSError, UnicodeDecodeError) as e:
        return None, f"JSON として読めません: {path}: {e}"


def _channel_is_complete(snapshot: dict, chan: dict) -> bool:
    """channel の pagination 完走が明示的に true 表明されているか。

    fail-closed: 完走マーカーが無い/false のものは「pagination 欠落」として不完全扱いにする。
    channel 個別の complete が無い場合は snapshot 全体の snapshot_complete を継承する。
    """
    if "complete" in chan:
        return chan.get("complete") is True
    return snapshot.get("snapshot_complete") is True


# --- registry state の分類 ------------------------------------------------
def _classify(entry: dict) -> str:
    """registry の1 video エントリを完全性バケットへ写像する。

    waiver_ref(承認参照)の有無が terminal_unavailable/waived の「承認/未承認」を分ける唯一の根拠。
    無承認の握り潰し(waived なのに参照無し)は waiver_missing として exit1 対象にする。
    """
    state = entry.get("state")
    ref = str(entry.get("waiver_ref") or "").strip()
    if state == "ingested":
        return "ingested"
    if state == "temporary_failure":
        return "temporary_failure"
    if state == "waived":
        return "waived" if ref else "waiver_missing"
    if state == "terminal_unavailable":
        return "approved_unavailable" if ref else "unapproved_unavailable"
    # 未知 state / registry に無い = 一度も処理されていない
    return "pending"


def _resolved_checked_sources(channels: list, registry: dict) -> set:
    """--channels の handle と、registry.sources が対応付ける channel_id を検査対象 source 集合へ束ねる。

    registry の video.source は channel_id か handle のどちらか。sources[] の handle↔channel_id 対応を
    使って、検査対象 channel に属する video を漏れなく特定できるようにする。
    """
    checked = set(channels)
    for s in registry.get("sources", []) or []:
        if s.get("handle") in checked:
            cid = s.get("channel_id")
            if cid:
                checked.add(cid)
    return checked


def evaluate(channels: list, snapshot: dict, registry: dict) -> dict:
    """snapshot(分母正本)× registry(状態)を突合して完全性判定 dict を返す。"""
    snap_channels = snapshot.get("channels", {}) or {}

    structural: list = []  # exit1 相当の構造破損理由
    pagination_gaps: list = []
    duplicates: list = []

    # 検査対象 channel が snapshot に存在し完走表明されているかを確認しつつ video_id を収集。
    ordered_ids: list = []  # 出現順(重複検出用)
    for handle in channels:
        chan = snap_channels.get(handle)
        if chan is None:
            # --channels で要求した channel が snapshot に無い = discovery/pagination の取りこぼし疑い。
            pagination_gaps.append(handle)
            continue
        if not _channel_is_complete(snapshot, chan):
            pagination_gaps.append(handle)
        for vid in chan.get("video_ids", []) or []:
            ordered_ids.append(str(vid))

    # 重複ID: authoritative snapshot に同一 video_id が二度現れるのは分母の水増し/取り違えの兆候。
    seen: set = set()
    for vid in ordered_ids:
        if vid in seen and vid not in duplicates:
            duplicates.append(vid)
        seen.add(vid)
    snapshot_ids = set(seen)

    # registry 側に「検査対象 channel 由来なのに snapshot に無い」ID があれば、分母縮小(snapshot からの
    # 取りこぼし/除外を分母外へ逃がす試み)として拒否する。
    checked_sources = _resolved_checked_sources(channels, registry)
    reg_videos = registry.get("videos", {}) or {}
    registry_not_in_snapshot = sorted(
        vid for vid, e in reg_videos.items()
        if (e or {}).get("source") in checked_sources and vid not in snapshot_ids
    )

    # 各 snapshot video を分類。
    buckets = {
        "ingested": [], "pending": [], "temporary_failure": [],
        "unapproved_unavailable": [], "approved_unavailable": [],
        "waived": [], "waiver_missing": [],
    }
    for vid in sorted(snapshot_ids):
        entry = reg_videos.get(vid)
        cat = _classify(entry) if entry else "pending"
        buckets[cat].append(vid)

    discovered_total = len(snapshot_ids)
    counts = {k: len(v) for k, v in buckets.items()}
    approved_absence = counts["waived"] + counts["approved_unavailable"]
    accountability_denominator = discovered_total - approved_absence

    content_coverage = (
        1.0 if discovered_total == 0 else round(counts["ingested"] / discovered_total, 6)
    )
    accountability_coverage = (
        1.0 if accountability_denominator <= 0
        else round(counts["ingested"] / accountability_denominator, 6)
    )

    if pagination_gaps:
        structural.append(f"pagination 欠落(完走未表明の channel): {sorted(pagination_gaps)}")
    if duplicates:
        structural.append(f"重複 video_id(分母水増し疑い): {sorted(duplicates)}")
    if registry_not_in_snapshot:
        structural.append(
            f"registry に snapshot 外の video_id(分母縮小疑い): {registry_not_in_snapshot}"
        )

    # FULL_BACKFILL: 承認 waiver すら無く全 ID ingested の最厳格通過。
    full_backfill_pass = (
        not structural
        and counts["ingested"] == discovered_total
        and counts["temporary_failure"] == 0
        and counts["unapproved_unavailable"] == 0
    )
    # ACCOUNTABILITY: 未処理・一時失敗・未承認 unavailable・waiver 参照欠落が皆無なら説明責任充足。
    accountability_pass = (
        not structural
        and counts["pending"] == 0
        and counts["temporary_failure"] == 0
        and counts["unapproved_unavailable"] == 0
        and counts["waiver_missing"] == 0
    )
    verdict = (
        "FULL_BACKFILL_PASS" if full_backfill_pass
        else "ACCOUNTABILITY_PASS" if accountability_pass
        else "FAIL"
    )

    return {
        "report": {
            "schema_version": SCHEMA_VERSION,
            "channels": list(channels),
            "discovered_total": discovered_total,
            "content_coverage": content_coverage,
            "accountability_coverage": accountability_coverage,
            "accountability_denominator": accountability_denominator,
            "full_backfill_pass": full_backfill_pass,
            "accountability_pass": accountability_pass,
            "verdict": verdict,
            "breakdown": counts,
        },
        "buckets": buckets,
        "structural": structural,
        "pass": accountability_pass,
    }


def _emit_failure_reasons(res: dict) -> None:
    """失敗内訳と対象 video ID(決定論・ソート済)を stderr へ出す。"""
    for line in res["structural"]:
        print(f"[FAIL] {line}", file=sys.stderr)
    b = res["buckets"]
    labels = [
        ("pending", "未処理(pending・一度も ingest されていない)"),
        ("temporary_failure", "一時失敗(temporary_failure・要 retry)"),
        ("unapproved_unavailable", "未承認 unavailable(承認参照無しの terminal_unavailable)"),
        ("waiver_missing", "waiver 参照欠落(waived だが waiver_ref 無し)"),
    ]
    for key, label in labels:
        if b[key]:
            print(f"[FAIL] {label}: {sorted(b[key])}", file=sys.stderr)


def main(argv: list | None = None) -> int:
    argv = list(sys.argv[1:] if argv is None else argv)
    ap = argparse.ArgumentParser(
        description="YouTube backfill 完全性ゲート(content/accountability 被覆を分離判定)"
    )
    ap.add_argument("--channels", nargs="+", required=True,
                    help="検査対象 channel handle(複数可・required-primary を含む)")
    ap.add_argument("--video-list", required=True,
                    help="authoritative snapshot JSON(分母正本)")
    ap.add_argument("--registry", required=True,
                    help="youtube-registry.json(read-only で状態参照)")
    try:
        args = ap.parse_args(argv)
    except SystemExit:
        return 2

    # authoritative snapshot が読めなければ分母を確定できない → usage/入力不正(exit2)。
    snapshot, snap_err = _load_json(Path(args.video_list))
    if snap_err is not None:
        print(f"エラー: --video-list を読めません: {snap_err}", file=sys.stderr)
        return 2
    if not isinstance(snapshot, dict) or not isinstance(snapshot.get("channels"), dict):
        print("エラー: --video-list の構造が不正です(channels マップが必要)", file=sys.stderr)
        return 2

    # registry は fail-closed: 破損は「完全性を証明できない」として exit1、不在は空 registry(全 pending)。
    registry_path = Path(args.registry)
    if registry_path.exists():
        registry, reg_err = _load_json(registry_path)
        if reg_err is not None:
            print(f"エラー: registry が破損しています(完全性未達扱い): {reg_err}", file=sys.stderr)
            print(json.dumps(
                {"schema_version": SCHEMA_VERSION, "verdict": "FAIL",
                 "error": "registry_corrupt", "channels": list(args.channels)},
                ensure_ascii=False, indent=2, sort_keys=True))
            return 1
    else:
        registry = {"videos": {}, "sources": []}

    res = evaluate(args.channels, snapshot, registry)
    print(json.dumps(res["report"], ensure_ascii=False, indent=2, sort_keys=True))
    if res["pass"]:
        return 0
    _emit_failure_reasons(res)
    return 1


if __name__ == "__main__":
    raise SystemExit(main())
