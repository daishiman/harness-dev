#!/usr/bin/env python3
# /// script
# name: validate-generation-lineage
# purpose: feature 別 current pointer が指す現行世代と supersede 済み旧世代の実バイト整合を再計算し、旧世代 directory が自己記述的な supersession marker を持つことを fail-closed 検査する。
# inputs: [argv --repo-root --config --package --write-markers]
# outputs: [stdout JSON {checked, violations, markers_written}, exit 0 ok, exit 2 fail-closed]
# contexts: [E]
# network: false
# write-scope: <published>/<package-slug>/SUPERSEDED.json (--write-markers 指定時のみ)
# dependencies: [resolve-project-context.py]
# requires-python: ">=3.11"
# ///
"""published generation lineage の自己記述性を機械検査する読み取り専用ゲート。

`.dev-graph/plans/feature-package-<slug>/` (generations layout 導入前の第 1 世代)
は現在 `.dev-graph/state/current/<slug>.json` の `supersedes` が指す supersede 済み
世代であり、`references/feature-execution-package-contract.md` の
「旧 package を byte-for-byte 不変で残す」規範により中身を書き換えてはならない。

一方でこの directory は名前が最も発見しやすく、render 済み HTML も同居するため、
pointer/receipt を辿らない読み手 (人間・planner) は旧世代を正本と誤読しうる。
本 script はその誤読を成立させない不変条件を機械化する:

  V1 pointer-schema        current pointer が必須 key を持つ
  V2 current-generation    現行世代 directory が実在し package として読める
  V3 current-digest        現行世代の実バイトから再計算した canonical digest が
                           pointer の published_digest と一致する
  V4 current-receipt       現行世代 receipt の 3 digest が pointer と一致する
  V5 superseded-generation supersede 済み世代 directory が実在する
  V6 superseded-digest     旧世代の実バイトから再計算した canonical digest が
                           pointer の supersedes.published_digest と一致する
                           (= 旧世代が byte-for-byte 不変に保たれている)
  V7 supersession-marker   旧世代 directory が現行世代を指す SUPERSEDED.json を持ち、
                            旧 promotion/registration receipt の実 bytes の SHA-256 を束縛する

marker は canonical digest の対象集合 (staging-manifest.json の files) に含まれない
付帯 file であり、追加しても V6 の digest は変わらない。決定論的に導出できる値だけ
を持たせ、`--write-markers` は欠落した marker だけを作る (既存 marker は再束縛しない)。
"""
from __future__ import annotations

import argparse
import hashlib
import importlib.util
import json
import os
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
MARKER_NAME = "SUPERSEDED.json"
MARKER_SCHEMA_VERSION = "1.0.0"
POINTER_KEYS = ("feature_package_id", "generation_id", "published_path", "published_digest", "receipt")
SUPERSEDES_KEYS = ("published_path", "published_digest", "receipt")
REGISTRATION_RECEIPT_NAMES = ("dev-graph-registration-receipt.json", "registration-receipt.json")


class LineageError(Exception):
    """診断可能な violation を組み立てるための内部例外。"""


def _read_json(path: Path) -> dict:
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
    except Exception as exc:  # noqa: BLE001 - 診断へ理由を載せる
        raise LineageError(f"{path} を JSON として読めない: {exc}") from exc
    if not isinstance(value, dict):
        raise LineageError(f"{path} は object ではない")
    return value


def _resolver():
    """全 path 検査を C09 (resolve-project-context.py) へ一元化する。"""
    spec = importlib.util.spec_from_file_location("sdp_context", HERE / "resolve-project-context.py")
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)  # type: ignore[union-attr]
    return module


def _contained(c09, root: Path, relative: str) -> Path:
    """C09 の containment 検査へ委譲する。独自実装は持たない。"""
    try:
        return c09.guard_relative_path(root, relative)
    except c09.PolicyError as exc:
        raise LineageError(str(exc)) from exc


def _manifest_files(c09, root: Path, package_dir: Path) -> list[str]:
    """canonical digest の対象集合を staging-manifest.json から取り出す。"""
    manifest = _read_json(_contained(c09, root, (package_dir / "staging-manifest.json").relative_to(root).as_posix()))
    files = manifest.get("files")
    if isinstance(files, dict):
        return sorted(files)
    if isinstance(files, list):
        return sorted(str(entry.get("path")) for entry in files if isinstance(entry, dict))
    raise LineageError(f"{package_dir}/staging-manifest.json の files が不正")


def canonical_digest(c09, root: Path, package_dir: Path) -> str:
    """validate-system-plan.py の canonical_digest と同一の走査規則で再計算する。

    manifest 記載の rel は信頼せず、読み取り 1 件ごとに C09 の realpath containment を
    通す。悪意ある manifest が `../` や package 内 symlink で repository 外の bytes を
    digest へ取り込む cross-repo read を防ぐ。
    """
    digest = hashlib.sha256()
    for rel in _manifest_files(c09, root, package_dir):
        try:
            target = _contained(c09, root, (package_dir / rel).relative_to(root).as_posix())
        except (LineageError, ValueError) as exc:
            raise LineageError(f"manifest 記載 file が repository 外を指す: {rel} ({exc})") from exc
        if not target.is_file():
            raise LineageError(f"manifest 記載 file が実在しない: {rel}")
        digest.update(rel.encode())
        digest.update(b"\0")
        digest.update(target.read_bytes())
        digest.update(b"\0")
    return "sha256:" + digest.hexdigest()




def _receipt_binding(c09, root: Path, relative: str) -> dict[str, str]:
    """旧 receipt の path と実 bytes の SHA-256 を marker へ束縛する。"""
    path = _contained(c09, root, relative)
    if not path.is_file():
        raise LineageError(f"旧 receipt が実在しない: {relative}")
    return {"path": relative, "sha256": "sha256:" + hashlib.sha256(path.read_bytes()).hexdigest()}


def _registration_receipt_binding(c09, root: Path, legacy_relative: str) -> dict[str, str]:
    """正準名を優先し、規約導入前の legacy 名だけを互換入力として受ける。

    両方がある場合は authority が二重になるため fail-closed で拒否する。
    """
    candidates = [f"{legacy_relative}/{name}" for name in REGISTRATION_RECEIPT_NAMES]
    existing: list[str] = []
    for relative in candidates:
        path = _contained(c09, root, relative)
        if path.is_file():
            existing.append(relative)
    if len(existing) != 1:
        raise LineageError(
            f"旧 registration receipt の authority が一意でない: found={existing}, candidates={candidates}"
        )
    return _receipt_binding(c09, root, existing[0])


def build_marker(
    pointer: dict,
    superseded_digest: str,
    current_pointer_rel: str,
    superseded_receipts: dict[str, dict[str, str]],
) -> dict:
    """supersede 済み世代 directory へ置く自己記述 marker の payload を組み立てる。

    決定論: 入力は current pointer の値と旧世代の再計算 digest だけで、生成時刻や
    実行者を含めない。`--write-markers` を何度実行しても同じ bytes になり、V7 の
    完全一致比較がそのまま冪等性の検査になる。

    自己検証性: `published_digest` には旧世代 (= この marker が置かれた directory)
    の再計算値を載せる。pointer 側 `supersedes.published_digest` との二重管理には
    なるが、marker 単体でも「主張された digest」と「実バイト」を独立照合できる方を
    採る。両者の食い違いは V6/V7 のどちらかが必ず捕捉する。

    再解決経路: 実体 path (`superseded_by.published_path`) と再解決の入口
    (`current_pointer`) を両方載せる。前者は今この瞬間の正本を人間が直接開くため、
    後者は次の世代へ進んだ後も planner が機械的に辿り直すために要る。
    """
    return {
        "schema_version": MARKER_SCHEMA_VERSION,
        "status": "superseded",
        "feature_package_id": pointer["feature_package_id"],
        "published_digest": superseded_digest,
        "superseded_receipts": superseded_receipts,
        "superseded_by": {
            "generation_id": pointer["generation_id"],
            "published_path": pointer["published_path"],
            "published_digest": pointer["published_digest"],
            "receipt": pointer["receipt"],
        },
        "current_pointer": current_pointer_rel,
        "notice": (
            "この directory は supersede 済みの旧世代であり、正本ではない。"
            "実装要件の正本は superseded_by.published_path 配下の content-addressed generation を読むこと。"
            "旧世代は byte-for-byte 不変で保持されるため、この directory の中身を編集して現行世代へ追随させてはならない。"
            "さらに世代が進んだ場合は current_pointer から再解決すること。"
        ),
    }


def _check_package(c09, root: Path, pointer_path: Path, write_markers: bool) -> tuple[list[dict], str | None]:
    """1 feature 分の lineage を検査し、violation 一覧と書き込んだ marker path を返す。"""
    violations: list[dict] = []
    written: str | None = None
    slug = pointer_path.stem

    def add(check: str, detail: str) -> None:
        violations.append({"package_slug": slug, "check": check, "detail": detail})

    try:
        pointer_rel = pointer_path.relative_to(root).as_posix()
        pointer_path = _contained(c09, root, pointer_rel)
        pointer = _read_json(pointer_path)
    except (LineageError, ValueError) as exc:
        add("V1-pointer-schema", str(exc))
        return violations, None

    missing = [key for key in POINTER_KEYS if not isinstance(pointer.get(key), str) or not pointer[key]]
    if missing:
        add("V1-pointer-schema", f"current pointer に必須 key が無い: {missing}")
        return violations, None
    supersedes = pointer.get("supersedes")
    if supersedes is not None:
        if not isinstance(supersedes, dict) or any(
            not isinstance(supersedes.get(key), str) or not supersedes[key] for key in SUPERSEDES_KEYS
        ):
            add("V1-pointer-schema", "supersedes locator が不完全")
            return violations, None

    # --- 現行世代 (V2..V4) ---
    try:
        current_dir = _contained(c09, root, pointer["published_path"])
        if not current_dir.is_dir():
            raise LineageError(f"現行世代 directory が実在しない: {pointer['published_path']}")
        actual = canonical_digest(c09, root, current_dir)
        if actual != pointer["published_digest"]:
            add("V3-current-digest",
                f"再計算 {actual} が pointer の published_digest {pointer['published_digest']} と不一致")
        receipt = _read_json(_contained(c09, root, pointer["receipt"]))
        for key in ("staging_digest", "evaluated_digest", "published_digest"):
            if receipt.get(key) != pointer["published_digest"]:
                add("V4-current-receipt",
                    f"receipt の {key}={receipt.get(key)!r} が pointer の published_digest と不一致")
    except LineageError as exc:
        add("V2-current-generation", str(exc))
        return violations, None

    if supersedes is None:
        return violations, None

    # --- supersede 済み世代 (V5..V7) ---
    try:
        legacy_dir = _contained(c09, root, supersedes["published_path"])
        if not legacy_dir.is_dir():
            raise LineageError(f"supersede 済み世代 directory が実在しない: {supersedes['published_path']}")
        legacy_actual = canonical_digest(c09, root, legacy_dir)
    except LineageError as exc:
        add("V5-superseded-generation", str(exc))
        return violations, None

    if legacy_actual != supersedes["published_digest"]:
        add("V6-superseded-digest",
            f"再計算 {legacy_actual} が supersedes.published_digest {supersedes['published_digest']} と不一致 "
            "(旧世代の byte-for-byte 不変性が壊れている)")
        return violations, None

    try:
        superseded_receipts = {
            "promotion": _receipt_binding(c09, root, supersedes["receipt"]),
            "registration": _registration_receipt_binding(c09, root, supersedes["published_path"]),
        }
    except LineageError as exc:
        add("V6-superseded-digest", str(exc))
        return violations, None

    expected_marker = build_marker(pointer, legacy_actual, pointer_rel, superseded_receipts)
    marker_rel = f"{supersedes['published_path']}/{MARKER_NAME}"
    try:
        # marker 自体が repository 外への symlink なら、書込みは repository を越える。
        # legacy dir の containment が通っていても per-file の realpath 検査は別に要る。
        marker_path = _contained(c09, root, marker_rel)
    except LineageError as exc:
        add("V7-supersession-marker", f"repository 外へ逃げる marker path: {exc}")
        return violations, None
    if not marker_path.is_file():
        if write_markers:
            marker_path.write_text(
                json.dumps(expected_marker, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
                encoding="utf-8",
            )
            written = f"{supersedes['published_path']}/{MARKER_NAME}"
        else:
            add("V7-supersession-marker", f"{supersedes['published_path']}/{MARKER_NAME} が無い")
    else:
        try:
            found = _read_json(marker_path)
        except LineageError as exc:
            add("V7-supersession-marker", str(exc))
        else:
            if found != expected_marker:
                add("V7-supersession-marker",
                    f"{supersedes['published_path']}/{MARKER_NAME} の内容が current pointer から導かれる値と不一致 "
                    "(既存 marker は --write-markers で再束縛しない)")
    return violations, written


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--repo-root", required=True)
    parser.add_argument("--config", default=".dev-graph/config.json")
    parser.add_argument("--package", default="",
                        help="package slug (例: feature-package-feat-example)。未指定なら全 feature。")
    parser.add_argument("--write-markers", action="store_true",
                        help="supersede 済み世代へ SUPERSEDED.json を冪等に書き込む")
    args = parser.parse_args(argv)

    c09 = _resolver()
    try:
        # repo root 解決・repository identity 照合・全 plan root の containment 検査を C09 に一元化する。
        context = c09.build_context(["--repo-root", args.repo_root, "--config", args.config], dict(os.environ))
        root = Path(context["repo_root"])
        state_root = _contained(c09, root, context["plan_roots"]["state"]["relative"])
    except (c09.UsageError, c09.PolicyError, LineageError, OSError, ValueError) as exc:
        print(f"[validate-generation-lineage] FAIL: {exc}", file=sys.stderr)
        return 2

    try:
        pointer_dir = _contained(
            c09, root, (state_root / "current").relative_to(root).as_posix()
        )
    except (LineageError, ValueError) as exc:
        print(f"[validate-generation-lineage] FAIL: current pointer directory を解決できない: {exc}", file=sys.stderr)
        return 2
    if not pointer_dir.is_dir():
        print(f"[validate-generation-lineage] FAIL: {pointer_dir} が無い", file=sys.stderr)
        return 2

    pointers = sorted(pointer_dir.glob("*.json"))
    if args.package:
        pointers = [p for p in pointers if p.stem == args.package]
        if not pointers:
            print(f"[validate-generation-lineage] FAIL: package {args.package} の current pointer が無い", file=sys.stderr)
            return 2
    elif not pointers:
        print("[validate-generation-lineage] FAIL: current pointer が 0 件", file=sys.stderr)
        return 2

    violations: list[dict] = []
    markers_written: list[str] = []
    for pointer_path in pointers:
        found, written = _check_package(c09, root, pointer_path, args.write_markers)
        violations.extend(found)
        if written:
            markers_written.append(written)

    print(json.dumps({"checked": len(pointers), "markers_written": markers_written,
                      "violations": violations}, ensure_ascii=False, indent=2))
    if violations:
        print(f"[validate-generation-lineage] FAIL: lineage violation {len(violations)} 件", file=sys.stderr)
        return 2
    return 0


if __name__ == "__main__":
    sys.exit(main())
