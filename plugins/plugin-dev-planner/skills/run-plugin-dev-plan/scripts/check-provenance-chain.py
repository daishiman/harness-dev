#!/usr/bin/env python3
# /// script
# name: check-provenance-chain
# purpose: E1-E3 を貫く provenance chain (intake.json→goal-spec→plan→build handoff→改善成果物) の追跡可能性を検証し、いずれかの provenance フィールド欠落 (chain 断裂) を fail-closed で検出する。inventory が surface_build_projection を宣言する場合は required plugin_level_surfaces の build_target 実在も assert する (欠落=exit 1)。
# inputs:
#   - argv: --goal-spec <goal-spec.json> [--plan-dir <dir>] [--require-improvement] [--allow-missing-intake] [--resolve]
# outputs:
#   - stdout: OK summary (追跡できたノード)
#   - stderr: chain 断裂 (欠落した provenance ノード)
#   - exit: 0=chain 追跡可能 / 1=断裂検出 / 2=usage error
# contexts: [C, E]
# network: false
# write-scope: none
# dependencies: []
# requires-python: ">=3.10"
# ///
"""provenance chain 5 ノードの追跡可能性ゲート (E1-E3 横断)。

chain: (1) intake.json → (2) goal-spec → (3) plan → (4) build handoff → (5) 改善成果物。
goal-spec の source_intake (node1→2) と source_improvement (node4→5) の provenance フィールド、
および plan_dir の handoff (node3→4) の実在で chain の連続性を検査する。いずれかが欠落すると
断裂として fail-closed で弾く。--resolve 指定時は ref 先ファイルの実在と改善サイクルの継続性
(improvement-handoff.provenance.source_intake が goal-spec.source_intake と一致するか) も検査する。

加えて plan_dir の component-inventory.json が surface_build_projection を宣言する場合、
required:true な plugin_level_surfaces の build_target 実在を assert し、欠落を fail-closed
(exit 1) で弾く (provenance_chain_trigger.all_required_surface_outputs_exist の機械層。
required surface が builder 未割当のまま無言欠落した build を pass marker で緑化させない)。
宣言不在の旧 inventory では本検査は no-op (後方互換)。goal-spec digest pin 検査は不変。
"""
from __future__ import annotations

import argparse
import hashlib
import json
import sys
from pathlib import Path

HANDOFF_NAME = "handoff-run-plugin-dev-plan.json"
# C11 hook が検証する pass marker のゲート名 (digest pin 契約)。
_MARKER_GATE = "provenance-chain"


def write_pass_marker(marker_dir: Path, gate_name: str, pinned_file: Path) -> Path:
    """<marker_dir>/.gate/<gate_name>.pass に pinned_file の sha256 を書く (digest pin)。

    marker を goal-spec の内容に pin することで、goal-spec が後で変わると C11 hook が
    stale と判定して --mode update を block する (stale marker による fail-open を封じる)。
    """
    digest = hashlib.sha256(pinned_file.read_bytes()).hexdigest()
    gate_dir = marker_dir / ".gate"
    gate_dir.mkdir(parents=True, exist_ok=True)
    marker = gate_dir / f"{gate_name}.pass"
    marker.write_text(digest + "\n", encoding="utf-8")
    return marker


def _prov_ref(data: dict, key: str) -> str | None:
    """provenance フィールド (source_intake/source_improvement) の ref を返す (無ければ None)。"""
    val = data.get(key)
    if isinstance(val, dict):
        ref = val.get("ref")
        if isinstance(ref, str) and ref.strip():
            return ref.strip()
    return None


def _check_required_surfaces(plan_dir: Path) -> list[str]:
    """inventory が surface_build_projection を宣言する場合、required surface の build_target 実在を assert する。

    plugin_level_surfaces (宣言は同 dict 内 or top-level) の required:true surface が
    build_target を欠く/実在しない場合を断裂として列挙する (fail-closed)。宣言不在の
    旧 inventory・inventory 不在/非 JSON は no-op (後方互換。inventory 自体の整合は
    validate-task-graph 等の既存 gate が担う)。build_target の相対パスは repo-root 相対で
    記録されるため cwd 基準で解決し、見つからなければ plan_dir/../.. (repo root 相当) でも試す。
    """
    inv_path = plan_dir / "component-inventory.json"
    if not inv_path.is_file():
        return []
    try:
        inv = json.loads(inv_path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return []
    if not isinstance(inv, dict):
        return []
    pls = inv.get("plugin_level_surfaces")
    pls = pls if isinstance(pls, dict) else {}
    decl = inv.get("surface_build_projection") or pls.get("surface_build_projection")
    if not isinstance(decl, dict):
        return []
    breaks: list[str] = []
    for key in sorted(pls):
        sf = pls[key]
        if not isinstance(sf, dict) or sf.get("required") is not True:
            continue
        bt = sf.get("build_target")
        if not isinstance(bt, str) or not bt.strip():
            breaks.append(
                f"SURFACE 断裂: required surface {key!r} に build_target が無い "
                "(surface_build_projection 宣言下では builder 未割当 surface を許容しない)"
            )
            continue
        p = Path(bt)
        candidates = [p] if p.is_absolute() else [Path.cwd() / p, plan_dir.parent.parent / p]
        if not any(c.exists() for c in candidates):
            breaks.append(
                f"SURFACE 断裂: required surface {key!r} の build_target が実在しない: {bt}"
            )
    return breaks


def check_chain(
    goal_spec: dict,
    *,
    plan_dir: Path | None,
    require_improvement: bool,
    allow_missing_intake: bool,
    resolve: bool,
) -> list[str]:
    """chain 断裂を列挙する (空 list なら追跡可能)。"""
    breaks: list[str] = []

    # node 1→2: intake → goal-spec
    intake_ref = _prov_ref(goal_spec, "source_intake")
    if intake_ref is None and not allow_missing_intake:
        breaks.append(
            "E1 断裂: goal-spec.source_intake が無い (intake→goal-spec の provenance link 欠落)"
        )

    # node 3→4: plan → build handoff
    if plan_dir is not None:
        if not (plan_dir / HANDOFF_NAME).is_file():
            breaks.append(f"E2 断裂: plan_dir に {HANDOFF_NAME} が無い (plan→build handoff link 欠落)")
        # surface_build_projection 宣言時のみ: required surface の build_target 実在 assert (fail-closed)
        breaks.extend(_check_required_surfaces(plan_dir))

    # node 4→5: 改善成果物 → 再生成 goal-spec
    improvement_ref = _prov_ref(goal_spec, "source_improvement")
    if require_improvement and improvement_ref is None:
        breaks.append(
            "E3 断裂: 改善サイクルだが goal-spec.source_improvement が無い (改善成果物→goal-spec link 欠落)"
        )

    if resolve:
        breaks.extend(_resolve_refs(goal_spec, intake_ref, improvement_ref, plan_dir))
    return breaks


def _resolve_refs(goal_spec, intake_ref, improvement_ref, plan_dir) -> list[str]:
    """ref 先ファイルの実在 + 改善サイクルの継続性を検査する (--resolve 時のみ)。"""
    breaks: list[str] = []
    base = plan_dir if plan_dir is not None else Path(".")

    def _resolved(ref: str) -> Path:
        p = Path(ref)
        return p if p.is_absolute() else base / p

    if intake_ref and not _resolved(intake_ref).is_file():
        breaks.append(f"E1 断裂: source_intake.ref が実在しない: {intake_ref}")
    if improvement_ref:
        imp_path = _resolved(improvement_ref)
        if not imp_path.is_file():
            breaks.append(f"E3 断裂: source_improvement.ref が実在しない: {improvement_ref}")
        else:
            # 継続性: improvement-handoff.provenance.source_intake が goal-spec の source_intake と一致するか。
            try:
                imp = json.loads(imp_path.read_text(encoding="utf-8"))
            except (json.JSONDecodeError, OSError) as exc:
                breaks.append(f"E3 断裂: source_improvement.ref を読めない: {exc}")
                return breaks
            imp_intake = (imp.get("provenance") or {}).get("source_intake") if isinstance(imp, dict) else None
            if intake_ref and imp_intake and imp_intake != intake_ref:
                breaks.append(
                    f"継続性断裂: improvement-handoff.provenance.source_intake={imp_intake!r} が "
                    f"goal-spec.source_intake.ref={intake_ref!r} と不一致 (chain が別 intake に接続)"
                )
    return breaks


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description="provenance chain の追跡可能性を検証する")
    ap.add_argument("--goal-spec", required=True)
    ap.add_argument("--plan-dir", default=None)
    ap.add_argument("--require-improvement", action="store_true",
                    help="改善サイクルとして source_improvement を必須にする")
    ap.add_argument("--allow-missing-intake", action="store_true",
                    help="intake 由来でない greenfield goal-spec で source_intake 欠落を許容する")
    ap.add_argument("--resolve", action="store_true",
                    help="ref 先ファイルの実在と改善サイクル継続性も検査する")
    ap.add_argument("--marker-dir", default=None,
                    help="PASS 時に <dir>/.gate/provenance-chain.pass (goal-spec digest pin) を書く (C11 hook 用)")
    args = ap.parse_args(argv)

    gs_path = Path(args.goal_spec)
    if not gs_path.is_file():
        sys.stderr.write(f"goal-spec not found: {gs_path}\n")
        return 2
    try:
        goal_spec = json.loads(gs_path.read_text(encoding="utf-8"))
    except json.JSONDecodeError as exc:
        sys.stderr.write(f"JSON parse error: {exc}\n")
        return 2
    if not isinstance(goal_spec, dict):
        sys.stderr.write("goal-spec root が object でない\n")
        return 2

    plan_dir = Path(args.plan_dir) if args.plan_dir else None
    breaks = check_chain(
        goal_spec,
        plan_dir=plan_dir,
        require_improvement=args.require_improvement,
        allow_missing_intake=args.allow_missing_intake,
        resolve=args.resolve,
    )
    if breaks:
        for b in breaks:
            sys.stderr.write(b + "\n")
        return 1
    if args.marker_dir:
        write_pass_marker(Path(args.marker_dir), _MARKER_GATE, gs_path)
    sys.stdout.write("OK: provenance chain が追跡可能 (断裂なし)\n")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
