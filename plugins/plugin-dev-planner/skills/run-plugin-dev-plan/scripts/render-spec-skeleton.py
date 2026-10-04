#!/usr/bin/env python3
# /// script
# name: render-spec-skeleton
# purpose: specfm の実行可能契約から phase ファイル(--phase N)/index(--index)の Markdown skeleton または inventory component(--kind KIND)の JSON skeleton を生成する。
# inputs:
#   - argv: --phase N [--plugin-slug SLUG] [--install-contract JSON] | --index [--plugin-slug SLUG] | --kind KIND [--skill-kind run|ref|wrap|assign|delegate] [--id C01]
# outputs:
#   - stdout: Markdown skeleton または JSON object skeleton
#   - exit: 0=OK / 2=usage error
# contexts: [C, E]
# network: false
# write-scope: none
# dependencies: []
# requires-python: ">=3.10"
# ///
"""静的ひな形ファイルを増やさず、specfm の正本から skeleton を生成する。

per-phase 転換: 主用途は `--phase N` (1-13) で phase-NN-<kebab>.md の §5 床付き Markdown skeleton を出す。
`--phase 13 --plugin-slug SLUG` は install 完了条項も生成する。opt-out は `--install-contract JSON` で同じ契約を渡す。
`--index` は index(main) の §9 基盤層+全体制御 section 床付き Markdown skeleton を出す。
`--kind` は component-inventory.json の components[] に入れる JSON object skeleton を出す。
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import specfm  # noqa: E402


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description="phase / index / component の最小 skeleton を生成する")
    ap.add_argument("--phase", type=int, default=None, help="phase_number 1-13 → phase ファイル skeleton")
    ap.add_argument("--index", action="store_true", help="index(main) skeleton (基盤層+全体制御 section 床)")
    ap.add_argument("--kind", default=None, choices=specfm.COMPONENT_KINDS, help="component_kind → component skeleton")
    ap.add_argument("--skill-kind", default="run", choices=specfm.SKILL_KINDS, help="skill kind (--kind skill 用)")
    ap.add_argument("--id", default="C01", help="component id (--kind 用)")
    ap.add_argument("--plugin-slug", default="sample-plugin", help="index/P13 skeleton の target plugin slug")
    ap.add_argument("--install-contract", type=Path, help="P13用install契約JSON (省略時は両製品既定)")
    args = ap.parse_args(argv)

    if args.phase is not None:
        if not (1 <= args.phase <= 13):
            sys.stderr.write("--phase は 1-13 の範囲であること\n")
            return 2
        try:
            install = json.loads(args.install_contract.read_text(encoding="utf-8")) if args.install_contract else None
            if install is not None:
                # Share the existing value-domain gate; no second contract validator.
                import importlib.util
                script = Path(__file__).with_name("check-spec-gates.py")
                loader = importlib.util.spec_from_file_location("install_gate", script)
                gate = importlib.util.module_from_spec(loader)
                loader.loader.exec_module(gate)
                errors = gate.check_install(install) if isinstance(install, dict) else ["install contract must be an object"]
                if errors:
                    raise ValueError("; ".join(errors))
            rendered = specfm.render_minimal_phase(args.phase, plugin_slug=args.plugin_slug, install=install)
        except (OSError, ValueError) as exc:
            sys.stderr.write(str(exc) + "\n")
            return 2
        sys.stdout.write(rendered)
        return 0
    if args.index:
        sys.stdout.write(specfm.render_minimal_index(plugin_slug=args.plugin_slug))
        return 0
    if args.kind is not None:
        sys.stdout.write(specfm.render_minimal_spec(args.kind, spec_id=args.id, skill_kind=args.skill_kind))
        return 0
    sys.stderr.write("usage: render-spec-skeleton.py --phase N | --index [--plugin-slug ...] | --kind KIND [--skill-kind ...] [--id ...]\n")
    return 2


if __name__ == "__main__":
    raise SystemExit(main())
