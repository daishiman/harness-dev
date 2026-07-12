#!/usr/bin/env python3
# /// script
# name: check-upstream-pins
# purpose: references/upstream-pins.json に台帳化した plugin 境界外の契約級引用 (upstream) の鮮度を sha256 で機械検証する決定論ゲート。in-repo では pin 対象の実体 hash を再計算し、不一致/消失を「該当 matrix_rows の再監査 + pin bump を同一変更で」と指示して fail-closed 拒否する。standalone install では最終検証時点 (verified_at) を開示して劣化を可視化する (skip でなく情報開示、exit 0)。
# inputs:
#   - argv: [--pins FILE] | --self-test
# outputs:
#   - stdout: OK サマリ / standalone 劣化開示 (verified_at)
#   - stderr: pin drift (sha256 不一致・pin 対象消失) / 台帳形式違反
#   - exit: 0=OK / 1=drift / 2=usage・台帳エラー
# contexts: [C, E]
# network: false
# write-scope: none (--self-test は一時 dir のみ)
# dependencies: []
# requires-python: ">=3.10"
# ///
"""plugin 境界を跨ぐ「引用」の鮮度を機械化する決定論ゲート。

planner は harness-creator 等の上流契約 (schema 形状・閾値・paradigm) を焼き込みでなく
「引用形」(path/ID 参照) で保持する。だが引用先が変質しても planner 側文書は沈黙 drift
する — この gap を references/upstream-pins.json の pin (path+sha256+verified_at+
matrix_rows) で埋める。三層方式「引用=path/ID+実在テスト、数値=複製+値 parity、意味
gloss=event-driven 監査」のうち、引用の鮮度層を本 script が担う。

pin 対象の限定 (オオカミ少年回避):
  契約級・低頻度変更・plugin 境界を跨ぐ引用のみ台帳へ登録する。同 plugin
  (plugin-dev-planner) 内の self-relative 参照は pin 対象外 — 同一変更で原子的に
  追従でき、既存 parity test (test_schema_parity 等) の責務であるため。高頻度変更
  ファイルを pin すると常時赤になり警報が無視される。

実行 mode (script 位置から自動判定):
  (a) in-repo: 上方探索で `.git` と `plugins/plugin-dev-planner` を併せ持つ dir
      (=harness repo root) が見つかる場合。全 pin の実体 hash を再計算し、不一致
      または消失 (移動/削除) を fail-closed で exit 1。是正は「該当 matrix_rows
      (references/harness-creator-spec-reflection.md の行 ID) を再監査し、引用の追従
      修正と pin bump (sha256/verified_at 更新) を同一変更で行う」。
  (b) standalone: repo root が見つからない場合 (単独 install)。引用先実体が無く
      再検証不能なので、pin 済内容が verified_at 時点の検証で凍結されている事実を
      pin ごとに開示して exit 0 (fail-open を情報で埋める)。
"""
from __future__ import annotations

import argparse
import hashlib
import json
import sys
import tempfile
from pathlib import Path

REQUIRED_PIN_KEYS = ("path", "sha256", "verified_at", "matrix_rows")


def load_ledger(pins_path: Path) -> tuple[list[dict], list[str]]:
    """台帳を読み、pin list と形式違反 (=exit 2 相当) を返す。"""
    if not pins_path.is_file():
        return [], [f"pin 台帳が見つからない: {pins_path}"]
    try:
        data = json.loads(pins_path.read_text(encoding="utf-8"))
    except json.JSONDecodeError as exc:
        return [], [f"pin 台帳 JSON parse error: {exc}"]
    pins = data.get("pins") if isinstance(data, dict) else None
    if not isinstance(pins, list) or not pins:
        return [], ["pin 台帳に pins[] (非空 list) が無い"]
    errors: list[str] = []
    for i, pin in enumerate(pins):
        if not isinstance(pin, dict):
            errors.append(f"pins[{i}] が dict でない")
            continue
        for key in REQUIRED_PIN_KEYS:
            if key not in pin:
                errors.append(f"pins[{i}] ({pin.get('path', '?')}) に必須キー {key} が無い")
        rows = pin.get("matrix_rows")
        if not isinstance(rows, list) or not all(isinstance(r, str) and r for r in rows):
            errors.append(f"pins[{i}] ({pin.get('path', '?')}) の matrix_rows が文字列 list でない")
    return [p for p in pins if isinstance(p, dict)], errors


def find_repo_root(start: Path) -> Path | None:
    """`.git` と `plugins/plugin-dev-planner` を併せ持つ祖先 dir = in-repo root を探す。"""
    for cand in (start, *start.parents):
        if (cand / ".git").exists() and (cand / "plugins" / "plugin-dev-planner").is_dir():
            return cand
    return None


def check_pins(pins: list[dict], root: Path | None) -> tuple[int, list[str], list[str]]:
    """(exit_code, errors→stderr, notes→stdout) を返す。root=None は standalone mode。"""
    errors: list[str] = []
    notes: list[str] = []
    if root is None:
        for pin in pins:
            notes.append(
                f"standalone: {pin['path']} は本 install に実体が無く再検証不能。"
                f"最終検証時点 verified_at={pin['verified_at']} の内容を引用している"
                " (以降の上流変更は未検証=劣化開示)"
            )
        return 0, errors, notes
    for pin in pins:
        target = root / pin["path"]
        rows = ", ".join(pin["matrix_rows"]) or "-"
        if not target.is_file():
            errors.append(
                f"pin 対象が消失: {pin['path']} (移動/削除の疑い) → matrix_rows [{rows}] を"
                "再監査し、引用の追従修正と pin bump を同一変更で行うこと"
            )
            continue
        current = hashlib.sha256(target.read_bytes()).hexdigest()
        if current != pin["sha256"]:
            errors.append(
                f"pin drift: {pin['path']} sha256 不一致 (pinned {pin['sha256'][:12]}… != "
                f"current {current[:12]}…, verified_at={pin['verified_at']}) → "
                f"matrix_rows [{rows}] を再監査し、引用の追従修正と pin bump "
                "(sha256/verified_at 更新) を同一変更で行うこと"
            )
    return (1 if errors else 0), errors, notes


# ─────────────────────────── self-test (壊れ pin fixture を内部生成) ───────────────────────────
def _self_test() -> tuple[int, list[str]]:
    """壊れ pin / 消失 / 一致 / standalone の4象限を一時 fixture で固定する。"""
    msgs: list[str] = []
    with tempfile.TemporaryDirectory() as td:
        root = Path(td)
        (root / ".git").mkdir()
        (root / "plugins" / "plugin-dev-planner").mkdir(parents=True)
        upstream = root / "doc" / "contract.md"
        upstream.parent.mkdir(parents=True)
        upstream.write_text("契約本文 v1\n", encoding="utf-8")
        good_sha = hashlib.sha256(upstream.read_bytes()).hexdigest()

        def _pin(path: str, sha: str) -> dict:
            return {"path": path, "sha256": sha, "verified_at": "2026-07-02", "matrix_rows": ["A1"]}

        # in-repo 判定: fixture root 配下から辿れる
        if find_repo_root(root / "plugins" / "plugin-dev-planner") != root:
            msgs.append("find_repo_root が fixture root を検出できない")
        # 一致 pin → exit 0 (偽陽性なし)
        code, errs, _ = check_pins([_pin("doc/contract.md", good_sha)], root)
        if code != 0 or errs:
            msgs.append(f"一致 pin を誤検出 (偽陽性): {errs}")
        # 壊れ pin (sha 不一致) → exit 1 + matrix_rows 再監査指示
        code, errs, _ = check_pins([_pin("doc/contract.md", "0" * 64)], root)
        if code != 1 or not any("pin drift" in e and "A1" in e for e in errs):
            msgs.append(f"壊れ pin (sha 不一致) を検出できない: {errs}")
        # 消失 pin → exit 1
        code, errs, _ = check_pins([_pin("doc/gone.md", good_sha)], root)
        if code != 1 or not any("消失" in e for e in errs):
            msgs.append(f"pin 対象の消失を検出できない: {errs}")
        # standalone → exit 0 + verified_at 開示
        code, errs, notes = check_pins([_pin("doc/contract.md", good_sha)], None)
        if code != 0 or errs or not any("verified_at=2026-07-02" in n for n in notes):
            msgs.append(f"standalone の劣化開示 (verified_at) が出ない: {notes}")
        # 台帳形式違反 → 検出される
        _, ledger_errs = load_ledger(root / "no-such.json")
        if not ledger_errs:
            msgs.append("台帳欠落を検出できない")
    return (1 if msgs else 0), msgs


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description="upstream 引用の鮮度 (sha256 pin) を検証する")
    ap.add_argument("--pins", default=None, help="pin 台帳 (既定 ../references/upstream-pins.json)")
    ap.add_argument("--self-test", action="store_true", help="壊れ pin fixture を内部生成して検知を自己検査する")
    args = ap.parse_args(argv)

    if args.self_test:
        code, msgs = _self_test()
        if code == 0:
            sys.stdout.write("OK: check-upstream-pins の drift/消失/standalone 検出が期待どおり\n")
            return 0
        for m in msgs:
            sys.stderr.write(m + "\n")
        return code

    script_dir = Path(__file__).resolve().parent
    pins_path = Path(args.pins) if args.pins else script_dir.parent / "references" / "upstream-pins.json"
    pins, ledger_errs = load_ledger(pins_path)
    if ledger_errs:
        for e in ledger_errs:
            sys.stderr.write(e + "\n")
        return 2

    root = find_repo_root(script_dir)
    code, errors, notes = check_pins(pins, root)
    for n in notes:
        sys.stdout.write(n + "\n")
    for e in errors:
        sys.stderr.write(e + "\n")
    if code == 0:
        if root is None:
            sys.stdout.write(f"OK (standalone): pins {len(pins)} 件は verified_at 時点で検証済 (本 install では再検証不能)\n")
        else:
            sys.stdout.write(f"OK: upstream pins {len(pins)} 件 sha256 一致 (in-repo fail-closed)\n")
    return code


if __name__ == "__main__":
    raise SystemExit(main())
