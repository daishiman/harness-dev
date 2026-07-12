#!/usr/bin/env python3
# /// script
# name: check-runtime-portability
# purpose: component-inventory.json の共有 script が install 携帯性を満たすか検証する決定論ゲート。>=2 skill から依存される script は placement_scope=plugin-root で plugins/<slug>/scripts/ へ hoist されていること (P)、全 component の build_target が plugin 内で自己完結する (plugins/ 始まり・.. を含まない) こと (Q)、および target_plugin_slug 指定時は各 build_target の plugins/<slug>/ が target_plugin_slug と一致する (自 plugin 外への build 混在が無い) こと (R) を検査する。
# inputs:
#   - argv: <plan-dir> [--inventory FILE] | --self-test
# outputs:
#   - stdout: OK サマリ
#   - stderr: 共有 script の placement 違反 / build_target 非自己完結 violation
#   - exit: 0=OK / 1=violation / 2=usage error
# contexts: [C, E]
# network: false
# write-scope: none
# dependencies: []
# requires-python: ">=3.10"
# ///
"""install 携帯性 (F8) を検証する決定論ゲート。

deploy 境界の内 (skill 配下) / 外 (plugin-root 共有) が dangling 可否を決める。単一 skill
専用 script は親 skill build へ畳み込めるが、複数 skill から共有される script を単一親 skill
配下に置くと、symlink 共有や単独 install で第二 consumer 側から辿れず dangling する。この
ゲートは plan(L3) 段階で:

  (P) ある script component が >=2 の別個の skill component から depends_on されている (=共有)
      なら placement_scope=="plugin-root" を必須にする (plugins/<slug>/scripts/ へ hoist)。
  (Q) 全 component の build_target が plugin 内で自己完結する: `plugins/` で始まり `..`
      セグメントを含まない (repo 外/親 plugin 外への相対脱出を禁止)。
  (R) target_plugin_slug (goal-spec.json 由来) が判れば、各 build_target の `plugins/<slug>/`
      セグメントが target_plugin_slug と一致する (別 plugin 配下への build 混在を禁止)。
      target 未指定時は (R) を発火させない (後方互換)。

を fail-closed で確認し、後段 build/install 時に初めて dangling が発覚する因果連鎖を前倒しで断つ。
placement_scope の enum と build_target の kind 別形状は specfm.validate_inventory_component が
別途担う (本ゲートは consumer 数由来の共有判定と self-contained のみを見る=責務分離)。
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import specfm  # noqa: E402


def _components(data: object) -> list[dict]:
    if not isinstance(data, dict) or not isinstance(data.get("components"), list):
        return []
    return [c for c in data["components"] if isinstance(c, dict)]


def skill_consumers(components: list[dict]) -> dict[str, set[str]]:
    """script id -> それを depends_on する別個の skill component id 集合 を返す。"""
    consumers: dict[str, set[str]] = {}
    for comp in components:
        if str(comp.get("component_kind", "")).strip() != "skill":
            continue
        sid = str(comp.get("id", "")).strip()
        deps = comp.get("depends_on")
        if not sid or not isinstance(deps, list):
            continue
        for dep in deps:
            dep = str(dep).strip()
            if dep:
                consumers.setdefault(dep, set()).add(sid)
    return consumers


def _target_plugin_slug(plan_dir: Path) -> str | None:
    """<plan_dir>/goal-spec.json の target_plugin_slug を fail-soft に読む。

    ファイル不在・JSON parse error・キー欠落・非 string はいずれも None を返し例外を投げない
    (既存呼び出し元との後方互換=goal-spec を持たない孤立 inventory 検証を壊さない)。
    """
    gs = plan_dir / "goal-spec.json"
    if not gs.is_file():
        return None
    try:
        data = json.loads(gs.read_text(encoding="utf-8"))
    except (json.JSONDecodeError, OSError):
        return None
    if not isinstance(data, dict):
        return None
    slug = data.get("target_plugin_slug")
    return slug.strip() if isinstance(slug, str) and slug.strip() else None


def check_inventory(data: object, target_plugin_slug: str | None = None) -> list[str]:
    """(P) 共有 script の plugin-root 強制 + (Q) build_target 自己完結 + (R) target 束縛を検査する。

    target_plugin_slug が非 None のときのみ (R) を実行する (既定 None=既存の P/Q のみで後方互換)。
    """
    components = _components(data)
    if not components:
        return ["component-inventory.json に components[] list が無い (携帯性検証不能)"]
    errors: list[str] = []
    consumers = skill_consumers(components)
    by_id = {str(c.get("id", "")).strip(): c for c in components if str(c.get("id", "")).strip()}

    # (P) >=2 skill consumer の script は plugin-root 必須
    for sid, comp in by_id.items():
        if str(comp.get("component_kind", "")).strip() != "script":
            continue
        used_by = sorted(consumers.get(sid, set()))
        if len(used_by) >= 2 and specfm.placement_of(comp) != "plugin-root":
            errors.append(
                f"script {sid} は {len(used_by)} skill ({', '.join(used_by)}) から共有されるが "
                f"placement_scope={specfm.placement_of(comp)!r} (>=2 consumer の共有 script は "
                "plugin-root で plugins/<slug>/scripts/ へ hoist すること=install 携帯性)"
            )

    # (Q) build_target が plugin 内で自己完結
    for cid, comp in by_id.items():
        bt = str(comp.get("build_target", "")).strip()
        if not bt:
            continue  # 空は validate_inventory_component の責務
        if not bt.startswith("plugins/"):
            errors.append(f"component {cid} の build_target が plugins/ で始まらない (plugin 内自己完結でない): {bt}")
        elif ".." in bt.split("/"):
            errors.append(f"component {cid} の build_target が '..' で plugin 外へ脱出する (自己完結でない): {bt}")

    # (R) target_plugin_slug 指定時、build_target の plugins/<slug>/ が target と一致すること。
    # plugins/ 始まりでない / '..' 混在は (Q) が捕捉済みゆえ (R) の対象外にする (二重報告回避)。
    if target_plugin_slug:
        for cid, comp in by_id.items():
            bt = str(comp.get("build_target", "")).strip()
            if not bt.startswith("plugins/"):
                continue
            segs = bt.split("/")
            slug = segs[1] if len(segs) >= 2 else ""
            if slug and slug != ".." and slug != target_plugin_slug:
                errors.append(
                    f"component {cid} の build_target が target_plugin_slug={target_plugin_slug!r} と "
                    f"異なる plugin {slug!r} 配下にある (自 plugin 外への build 混在): {bt}"
                )
    return errors


# ─────────────────────────── self-test (埋め込み最小 fixture) ───────────────────────────
def _self_test() -> tuple[int, list[str]]:
    """P/Q 各 1 件を検出できることを埋め込み fixture で固定する。"""
    msgs: list[str] = []

    def _script(sid: str, *, placement: str, build_target: str) -> dict:
        return {"id": sid, "component_kind": "script", "placement_scope": placement, "build_target": build_target}

    def _skill(sid: str, deps: list[str]) -> dict:
        return {"id": sid, "component_kind": "skill", "depends_on": deps, "build_target": f"plugins/x/skills/{sid}/"}

    # (P) 共有 script が skill placement のまま → 検出される
    shared_bad = {"components": [
        _script("C9", placement="skill", build_target="plugins/x/skills/run-a/scripts/s.py"),
        _skill("C1", ["C9"]), _skill("C2", ["C9"]),
    ]}
    p_errs = check_inventory(shared_bad)
    if not any("C9" in e and "plugin-root" in e for e in p_errs):
        msgs.append(f"(P) 共有 script の placement 違反を検出できない: {p_errs}")

    # (P) plugin-root へ hoist 済なら通る (偽陽性なし)
    shared_ok = {"components": [
        _script("C9", placement="plugin-root", build_target="plugins/x/scripts/s.py"),
        _skill("C1", ["C9"]), _skill("C2", ["C9"]),
    ]}
    if any("C9" in e and "plugin-root" in e for e in check_inventory(shared_ok)):
        msgs.append("(P) plugin-root 済 script を誤検出 (偽陽性)")

    # (Q) build_target が '..' で脱出 → 検出される
    escape = {"components": [
        _script("C9", placement="plugin-root", build_target="plugins/../secret/s.py"),
        _skill("C1", ["C9"]), _skill("C2", ["C9"]),
    ]}
    q_errs = check_inventory(escape)
    if not any("C9" in e and "自己完結" in e for e in q_errs):
        msgs.append(f"(Q) build_target の '..' 脱出を検出できない: {q_errs}")

    # (R) target と異なる plugin 配下の build_target → target 指定時のみ検出される
    cross = {"components": [_skill("C1", [])]}  # build_target=plugins/x/skills/C1/ (slug=x)
    r_errs = check_inventory(cross, target_plugin_slug="y")
    if not any("C1" in e and "target_plugin_slug" in e for e in r_errs):
        msgs.append(f"(R) target_plugin_slug 不一致を検出できない: {r_errs}")
    # (R) target 未指定なら発火しない (後方互換)
    if any("target_plugin_slug" in e for e in check_inventory(cross)):
        msgs.append("(R) target 未指定で誤検出 (後方互換違反)")
    # (R) 一致 slug なら通る (偽陽性なし)
    if any("target_plugin_slug" in e for e in check_inventory(cross, target_plugin_slug="x")):
        msgs.append("(R) 一致 slug を誤検出 (偽陽性)")

    return (1 if msgs else 0), msgs


def run(plan_dir: Path, inventory_path: Path | None) -> tuple[int, list[str]]:
    if inventory_path is None:
        inventory_path = plan_dir / "component-inventory.json"
    if not inventory_path.is_file():
        return 2, [f"component-inventory.json が見つからない: {inventory_path}"]
    try:
        data = json.loads(inventory_path.read_text(encoding="utf-8"))
    except json.JSONDecodeError as exc:
        return 2, [f"component-inventory JSON parse error: {exc}"]
    errors = check_inventory(data, _target_plugin_slug(plan_dir))
    return (1 if errors else 0), errors


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description="install 携帯性 (共有 script placement + build_target 自己完結) を検証する")
    ap.add_argument("plan_dir", nargs="?", help="plan ディレクトリ")
    ap.add_argument("--inventory", default=None, help="component-inventory.json (既定 <plan_dir>/component-inventory.json)")
    ap.add_argument("--self-test", action="store_true", help="埋め込み fixture で P/Q 検出を自己検査する")
    args = ap.parse_args(argv)

    if args.self_test:
        code, msgs = _self_test()
        if code == 0:
            sys.stdout.write("OK: check-runtime-portability の P/Q/R 検出が期待どおり\n")
            return 0
        for m in msgs:
            sys.stderr.write(m + "\n")
        return code

    if not args.plan_dir:
        sys.stderr.write("usage: check-runtime-portability.py <plan-dir> | --self-test\n")
        return 2
    plan_dir = Path(args.plan_dir)
    if not plan_dir.is_dir():
        sys.stderr.write(f"not a directory: {plan_dir}\n")
        return 2
    inventory_path = Path(args.inventory) if args.inventory else None
    code, errors = run(plan_dir, inventory_path)
    if code == 0:
        sys.stdout.write("OK: 共有 script は plugin-root へ hoist 済・全 build_target が plugin 内自己完結\n")
        return 0
    for e in errors:
        sys.stderr.write(e + "\n")
    return code


if __name__ == "__main__":
    raise SystemExit(main())
