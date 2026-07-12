#!/usr/bin/env python3
# /// script
# name: check-route-component-parity
# purpose: E2 境界ゲート。handoff の routes[] と component-inventory.json の components[] が 1:1 対応することを検査し、run-skill-create (PB-C06) が build 開始前に parity 不一致を fail-closed で止められるようにする。
# inputs:
#   - argv: <handoff-json> [--inventory <inventory-json>]
# outputs:
#   - stdout: OK summary
#   - stderr: parity violations (漏れ/余分/フィールド不一致)
#   - exit: 0=OK / 1=violation / 2=usage error
# contexts: [C, E]
# network: false
# write-scope: none
# dependencies: []
# requires-python: ">=3.10"
# ///
"""routes[] ↔ component-inventory.json の parity を検査する独立ゲート。

check-build-handoff.py は handoff 全体 (routing/top-sort/envelope) を検証する重いゲートだが、
build 実行入口 (run-skill-create=PB-C06) は「route が inventory と 1:1 で一致するか」だけを
build 開始前に軽く preflight したい。本 script はその parity 部分のみを切り出した focused gate。

harness-creator/scripts/ 配下の plugin-root script のため cross-plugin の specfm を import せず
自己完結する (feedback_contract_ssot.py と同じ複製方針)。parity 判定は id 集合の一致 +
主要 route フィールドの一致 + side_effect_targets (不在は [] 扱い・順序非依存) の一致のみで、
specfm の enum 定数を必要としない。
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

# route と inventory component の双方が持ち、突合すべきスカラフィールド。
_SCALAR_KEYS = (
    "component_kind",
    "name",
    "builder",
    "build_kind",
    "build_target",
    "placement_scope",
)


def _load_json(path: Path):
    return json.loads(path.read_text(encoding="utf-8"))


def _id_map(items: object, id_errors: list[str], label: str) -> dict[str, dict]:
    """list of dict を id→dict へ畳む。id 欠落/重複は id_errors へ記録する。"""
    result: dict[str, dict] = {}
    if not isinstance(items, list):
        id_errors.append(f"{label} が list でない")
        return result
    for idx, item in enumerate(items):
        if not isinstance(item, dict):
            id_errors.append(f"{label}[{idx}] が object でない")
            continue
        rid = str(item.get("id", "")).strip()
        if not rid:
            id_errors.append(f"{label}[{idx}] に id が無い")
            continue
        if rid in result:
            id_errors.append(f"{label} の id={rid!r} が重複している")
            continue
        result[rid] = item
    return result


def _scalar(v: object) -> object:
    return v.strip() if isinstance(v, str) else v


def check_parity(routes: object, components: object) -> list[str]:
    """routes[] と components[] の 1:1 parity 違反を列挙する (空 list なら parity OK)。"""
    errors: list[str] = []
    route_map = _id_map(routes, errors, "routes")
    comp_map = _id_map(components, errors, "components")
    if not route_map and not comp_map:
        errors.append("routes / components がどちらも空 (parity 検証不能)")
        return errors

    for missing in sorted(set(comp_map) - set(route_map)):
        errors.append(f"inventory component {missing} に対応する route が無い (全 component を routing すること)")
    for extra in sorted(set(route_map) - set(comp_map)):
        errors.append(f"route {extra} が component-inventory.json に存在しない (routes は inventory 由来)")

    for rid in sorted(set(route_map) & set(comp_map)):
        route = route_map[rid]
        comp = comp_map[rid]
        for key in _SCALAR_KEYS:
            r_val = _scalar(route.get(key))
            c_val = _scalar(comp.get(key))
            # 双方が非空で不一致のときのみ error (片側欠落は各 kind の構造検査の責務で本ゲート対象外)。
            if r_val and c_val and r_val != c_val:
                errors.append(f"route {rid} の {key}={r_val!r} が inventory の {c_val!r} と不一致")
        r_dep = route.get("depends_on")
        c_dep = comp.get("depends_on")
        if isinstance(r_dep, list) and isinstance(c_dep, list) and r_dep != c_dep:
            errors.append(f"route {rid} の depends_on={r_dep!r} が inventory の {c_dep!r} と不一致")
        c_args = comp.get("build_args")
        r_args = route.get("build_args")
        if isinstance(c_args, dict) and c_args and r_args != c_args:
            errors.append(f"route {rid} の build_args が inventory と不一致")
        # side_effect_targets は宣言済み副作用面の突合 (不在は [] 扱い)。scalar と違い片側欠落も
        # 「副作用なし宣言」の意味を持つため、[] へ正規化しソート後 list 比較で不一致を NG にする。
        r_se = route.get("side_effect_targets")
        c_se = comp.get("side_effect_targets")
        r_se_n = sorted(str(x) for x in r_se) if isinstance(r_se, list) else []
        c_se_n = sorted(str(x) for x in c_se) if isinstance(c_se, list) else []
        if r_se_n != c_se_n:
            errors.append(
                f"route {rid} の side_effect_targets={r_se_n!r} が inventory の {c_se_n!r} と不一致"
            )
    return errors


def resolve_inventory(handoff_path: Path, data: dict, override: str | None) -> Path:
    """inventory パスを解決する。--inventory 明示 > handoff.plan_dir(絶対) > handoff と同ディレクトリ。"""
    if override:
        return Path(override)
    plan_dir_raw = str(data.get("plan_dir", "")).strip()
    # handoff は必ず <PLAN_DIR> 直下に書かれる。相対 plan_dir を cwd で再構成すると CI で
    # 二重化するため handoff ファイルの所在を基準にする (check-build-handoff と同方針)。
    if plan_dir_raw and Path(plan_dir_raw).is_absolute():
        return Path(plan_dir_raw) / "component-inventory.json"
    return handoff_path.parent / "component-inventory.json"


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description="routes[]↔component-inventory.json の parity を検査する")
    ap.add_argument("handoff", help="handoff-run-plugin-dev-plan.json")
    ap.add_argument("--inventory", help="component-inventory.json (省略時は handoff の plan_dir から解決)")
    args = ap.parse_args(argv)

    handoff_path = Path(args.handoff)
    if not handoff_path.is_file():
        sys.stderr.write(f"handoff not found: {handoff_path}\n")
        return 2
    try:
        data = _load_json(handoff_path)
    except json.JSONDecodeError as exc:
        sys.stderr.write(f"handoff JSON parse error: {exc}\n")
        return 2
    if not isinstance(data, dict):
        sys.stderr.write("handoff root が object でない\n")
        return 2

    inv_path = resolve_inventory(handoff_path.resolve(), data, args.inventory)
    if not inv_path.is_file():
        sys.stderr.write(f"component-inventory not found: {inv_path}\n")
        return 2
    try:
        inv = _load_json(inv_path)
    except json.JSONDecodeError as exc:
        sys.stderr.write(f"component-inventory JSON parse error: {exc}\n")
        return 2
    if not isinstance(inv, dict):
        sys.stderr.write("component-inventory root が object でない\n")
        return 2

    errors = check_parity(data.get("routes"), inv.get("components"))
    if not errors:
        n = len(data.get("routes") or [])
        sys.stdout.write(f"OK: {n} routes が component-inventory.json と 1:1 parity を満たす\n")
        return 0
    for err in errors:
        sys.stderr.write(err + "\n")
    return 1


if __name__ == "__main__":
    raise SystemExit(main())
