#!/usr/bin/env python3
# /// script
# name: validate-plan-coverage
# purpose: component-inventory.json (計画) と plugin のディスク実体を照合し、計画に
#          あって未 build の component / 未生成の required plugin-level surface を検出
#          する決定論 completeness gate。「同じ計画から漏れなく同じ Capability 集合が
#          生成されたか」を機械判定し、目視・AI 照合の非再現を排除する。
# inputs:
#   - argv: <component-inventory.json> [--repo-root <dir>] [--json]  (単一 plan の strict 照合)
#   - argv: --all [--repo-root <dir>] [--json]  (plugin-plans/*/ を sweep し実体化済み plan を fail-closed で gate)
#   - argv: --self-test  (分岐検査)
# outputs:
#   - stdout: OK summary / JSON report (--json)
#   - stderr: coverage violations (未 build component / 未生成 surface)
#   - exit: 0=全 build 済 (or 未 build plan は skip) / 1=実体化済み plan に漏れあり / 2=usage error
# contexts: [C, E]
# network: false
# write-scope: none
# dependencies: []
# requires-python: ">=3.10"
# ///
"""計画 (component-inventory.json) ↔ plugin 実体の completeness 照合。

背景: harness-creator の標準フローは
  /plugin-dev-plan → (routes[] を 1 個ずつ build) → /plugin-compose
  → /run-plugin-package-check
という連結で「総体を漏れなく組む」。このうち「計画にあって未 build の component が
無いか」の照合を README は『漏れなく』を測る唯一の gate と呼ぶが、従来は
plugin-compose の doc に「照合する」と散文で書かれるのみで実装が無く、AI の目視判断
に落ちていた (非再現)。plugin-compose Step2 は実体から capabilities[] を再計算する
ため、fan-out が component を 1 個落としても欠落が静かに消え、下流 (Step3/4/5) は
実在物しか見ないので「計画に対する漏れ」を誰も捕捉できない。本 script はその照合を
決定論化し、fail-closed (漏れ検出で exit 1) にする。

- check-surface-inventory.py (plugin-dev-planner) は inventory の *内部整合*
  (5 kind 検討証跡・surface 採否理由) を見る。本 script は *計画↔ディスク実体* を
  照合する (相補・別レイヤー)。
- check-build-handoff.py の inventory provenance は routes(計画)==inventory(計画)
  の計画内整合を見る。本 script は inventory(計画)==build(実体) を見る (別軸)。
- 実体が真実: trace・自己申告でなく build_target のディスク実在を検査する。

Exit 0 = 全 component + required surface が実在, 1 = 漏れあり, 2 = usage error。
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

# component_kind のうち build_target がディレクトリ (skill dir) になるもの。
# それ以外 (sub-agent/slash-command/hook/script) は単一ファイル。
_DIR_KINDS = {"skill"}

# inventory 直下 build_status がこれらの値のとき「未 build の計画ドキュメント」として
# 計画↔実体 completeness 照合を skip する (build 実行時に build_status を realized 等へ
# 更新すると gate が発火する)。既存の「対象 plugin 不在→skip」は *新規 plugin* の未 build を
# 扱うが、*既存 plugin を対象とする拡張計画* は plugin root が実在するため従来 skip 経路に
# 乗らず build 漏れと誤検出されていた。build_status はその非対称を埋める第一級ライフサイクル
# 宣言で、計画側 (component-inventory.json) が自身の状態を SSOT として宣言する。gate script を
# 個別 plan ごとに編集する path ハードコード allowlist ではなく、任意の将来計画へ汎用に効く。
_NOT_BUILT_STATES = {"planned", "draft"}


def _plugin_root_of(build_target: str) -> str | None:
    """build_target 'plugins/<plugin>/...' から 'plugins/<plugin>' を抽出する。

    build_target が plugins/ 配下でない (想定外) 場合は None。
    """
    parts = Path(build_target).parts
    if len(parts) >= 2 and parts[0] == "plugins":
        return str(Path(parts[0]) / parts[1])
    return None


def _target_exists(repo_root: Path, build_target: str, component_kind: str) -> tuple[bool, str]:
    """build_target のディスク実在を判定する。

    skill (ディレクトリ) は配下 SKILL.md も要求する。戻り値 (exists, detail)。
    """
    p = repo_root / build_target
    is_dir_target = build_target.rstrip().endswith("/") or component_kind in _DIR_KINDS
    if is_dir_target:
        if not p.is_dir():
            return False, "ディレクトリ不在"
        if component_kind in _DIR_KINDS and not (p / "SKILL.md").exists():
            return False, "SKILL.md 不在"
        return True, "ok"
    if not p.exists():
        return False, "ファイル不在"
    return True, "ok"


def _clean_surface_path(value: str) -> str:
    """surface path 宣言から実在照合に使う path 部分だけを取り出す。

    既存 inventory には `skills/x/ (補足...)` のように、path フィールドへ人間向け補足を
    混ぜたものがある。照合は path 部分のみを使い、補足は inventory 側の記述として温存する。
    """
    s = value.strip()
    if " (" in s:
        s = s.split(" (", 1)[0].rstrip()
    return s


def _surface_exists(repo_root: Path, plugin_roots: set[str], raw_path: str) -> tuple[bool, str | None]:
    """surface path を repo-root 相対または plugin-root 相対として解決する。

    - `plugins/<slug>/...` で始まる path は repo-root 相対として直接照合する。
    - それ以外は従来通り plugin-root 相対として、build_target から root が一意な場合だけ照合する。
    """
    rel = _clean_surface_path(raw_path)
    if not rel:
        return True, None
    if Path(rel).parts[:1] == ("plugins",):
        return (repo_root / rel).exists(), rel
    if len(plugin_roots) == 1:
        pr = Path(next(iter(plugin_roots)))
        candidate = str(pr / rel)
        return (repo_root / candidate).exists(), candidate
    return False, None


def verify(inventory: dict, repo_root: Path) -> tuple[list[str], list[str], dict]:
    """(missing_components, missing_surfaces, summary) を返す。

    missing_components: 計画にあって未 build の component (id/kind/理由)。
    missing_surfaces:   required=true だが未生成の plugin-level surface。
    """
    missing_components: list[str] = []
    components = inventory.get("components") or []
    plugin_roots: set[str] = set()

    for comp in components:
        if not isinstance(comp, dict):
            missing_components.append(f"? : component が object でない ({comp!r})")
            continue
        cid = comp.get("id", "?")
        kind = comp.get("component_kind", "")
        bt = comp.get("build_target", "")
        if not bt:
            missing_components.append(f"{cid} ({kind}): build_target 未宣言")
            continue
        pr = _plugin_root_of(bt)
        if pr:
            plugin_roots.add(pr)
        ok, detail = _target_exists(repo_root, bt, kind)
        if not ok:
            missing_components.append(f"{cid} ({kind}): {bt} — {detail}")

    # plugin-level surface 照合 (required=true のもののみ)。surface は 4 形式を持つ:
    #   - path    : plugin-relative 単一パス、または plugins/<slug>/... の repo-relative パス。
    #               plugin-relative の場合は plugin-root を build_target 群から導出する (1 plugin 前提)。
    #   - target  : repo-relative 単一パス。
    #   - targets : repo-relative パス配列。所有 plugin を跨ぐ計画 (artifact_class=
    #               existing-plugin-update で C7 の cross-plugin routing を持つ plan) でも
    #               各 target を repo_root 起点で直接照合できる (plugin-root 導出不要)。
    # path/target/targets を持たない required surface (record_in / resolution 型: Notion config
    # ・index 記録先など) はファイル実在照合の対象外。宣言妥当性は check-surface-inventory.py
    # (inventory 内部整合) が担う (責務分離)。
    missing_surfaces: list[str] = []
    skipped_surfaces: list[str] = []
    surfaces = inventory.get("plugin_level_surfaces") or {}
    for name, spec in surfaces.items():
        if not isinstance(spec, dict) or not spec.get("required"):
            continue
        targets = spec.get("targets")
        target = spec.get("target")
        rel = spec.get("path")
        if isinstance(targets, list) and targets:
            # repo-relative 直接照合 (cross-plugin 安全)。
            for t in targets:
                if not isinstance(t, str) or not t.strip():
                    continue
                cleaned = _clean_surface_path(t)
                if cleaned and not (repo_root / cleaned).exists():
                    missing_surfaces.append(f"{name}: {cleaned} 不在")
        elif isinstance(target, str) and target.strip():
            cleaned = _clean_surface_path(target)
            if cleaned and not (repo_root / cleaned).exists():
                missing_surfaces.append(f"{name}: {cleaned} 不在")
        elif rel:
            ok, resolved = _surface_exists(repo_root, plugin_roots, str(rel))
            if resolved:
                if not ok:
                    missing_surfaces.append(f"{name}: {resolved} 不在")
            else:
                missing_surfaces.append(
                    f"{name}: plugin-relative path={_clean_surface_path(str(rel))!r} だが build_target が "
                    f"{sorted(plugin_roots)} を跨ぎ plugin-root を一意解決できない "
                    "(targets[] で repo-relative 宣言すれば cross-plugin 照合可能)"
                )
        else:
            skipped_surfaces.append(name)

    summary = {
        "components_total": len(components),
        "components_missing": len(missing_components),
        "surfaces_missing": len(missing_surfaces),
        "surfaces_skipped": sorted(skipped_surfaces),
        "plugin_roots": sorted(plugin_roots),
    }
    return missing_components, missing_surfaces, summary


def _plugin_roots_of(inventory: dict) -> set[str]:
    """inventory の全 build_target から plugins/<plugin> 集合を導出する。"""
    roots: set[str] = set()
    for comp in inventory.get("components") or []:
        if isinstance(comp, dict):
            pr = _plugin_root_of(comp.get("build_target", "") or "")
            if pr:
                roots.add(pr)
    return roots


def verify_all(repo_root: Path, plans_dir: str = "plugin-plans") -> tuple[list[dict], list[str], list[str]]:
    """plugin-plans/*/component-inventory.json を sweep し実体化済み plan を fail-closed で gate する。

    戻り値 (gated_failures, gated_ok, skipped):
      gated_failures: 実体化済みだが漏れありの plan 情報 [{inventory, missing_components, missing_surfaces}]
      gated_ok:       実体化済みで漏れなしの inventory パス
      skipped:        gate 対象外の inventory パス + 理由。3 種:
                      (a) build_status=planned/draft の未 build 計画ドキュメント (第一級宣言)、
                      (b) 対象 plugin 不在の未 build 新規 plugin 計画、
                      (c) plugins/ 外で照合不能なもの。
    """
    gated_failures: list[dict] = []
    gated_ok: list[str] = []
    skipped: list[str] = []
    base = repo_root / plans_dir
    if not base.is_dir():
        return gated_failures, gated_ok, skipped
    for inv_path in sorted(base.glob("*/component-inventory.json")):
        try:
            inventory = json.loads(inv_path.read_text(encoding="utf-8"))
        except (json.JSONDecodeError, OSError) as exc:
            gated_failures.append({
                "inventory": str(inv_path.relative_to(repo_root)),
                "missing_components": [f"JSON/IO error: {exc}"],
                "missing_surfaces": [],
            })
            continue
        if not isinstance(inventory, dict):
            gated_failures.append({
                "inventory": str(inv_path.relative_to(repo_root)),
                "missing_components": ["inventory root が object でない"],
                "missing_surfaces": [],
            })
            continue
        rel = str(inv_path.relative_to(repo_root))
        status = inventory.get("build_status")
        if isinstance(status, str) and status.strip().lower() in _NOT_BUILT_STATES:
            # 未 build の計画ドキュメント (build_status=planned/draft): 計画↔実体照合の対象外。
            # malformed / root 不在 / component gap 判定より前に評価し、既存 plugin を対象とする
            # 拡張計画でも root 実在に引きずられず正しく skip する (build 時に status 更新で gate 化)。
            skipped.append(
                f"{rel} — build_status={status.strip()} "
                "(未 build の計画ドキュメント。build 実行時に build_status を realized へ更新すると gate 化)"
            )
            continue
        roots = _plugin_roots_of(inventory)
        if (inventory.get("components") or []) and not roots:
            # component はあるが build_target が 1 つも plugins/ 配下でない = malformed。
            # 「未 build」と区別し fail-closed 分類する (prefix 無しを silent skip すると
            # 実在ファイルでも照合対象外になる fail-open になるため)。
            gated_failures.append({
                "inventory": rel,
                "missing_components": ["build_target が 1 つも plugins/<plugin>/... 形式でない (malformed inventory)"],
                "missing_surfaces": [],
            })
            continue
        if not any((repo_root / pr).is_dir() for pr in roots):
            skipped.append(f"{rel} — 未 build (対象 plugin 不在。build 実行時に自動 gate 化)")
            continue
        mc, ms, _ = verify(inventory, repo_root)
        if mc or ms:
            gated_failures.append({"inventory": rel, "missing_components": mc, "missing_surfaces": ms})
        else:
            gated_ok.append(rel)
    return gated_failures, gated_ok, skipped


def _run_all(repo_root: Path, as_json: bool) -> int:
    gated_failures, gated_ok, skipped = verify_all(repo_root)
    ok = not gated_failures
    if as_json:
        print(json.dumps({
            "ok": ok,
            "gated_ok": gated_ok,
            "gated_failures": gated_failures,
            "skipped": skipped,
        }, ensure_ascii=False, indent=2))
        return 0 if ok else 1
    if not ok:
        print(
            f"FAIL: plan coverage (--all) — 実体化済み plan に漏れ ({len(gated_failures)} plan)",
            file=sys.stderr,
        )
        for f in gated_failures:
            print(f"  [{f['inventory']}]", file=sys.stderr)
            for e in f["missing_components"]:
                print(f"    - [component] {e}", file=sys.stderr)
            for e in f["missing_surfaces"]:
                print(f"    - [surface] {e}", file=sys.stderr)
        return 1
    print(
        f"OK: plan coverage (--all) — 実体化済み {len(gated_ok)} plan 網羅 / "
        f"未 build {len(skipped)} plan は gate 対象外 (build 時自動発火)"
    )
    for s in skipped:
        print(f"  skip: {s}")
    return 0


def _self_test() -> int:
    import tempfile

    inv = {
        "components": [
            {"id": "C01", "component_kind": "skill",
             "build_target": "plugins/demo/skills/run-demo/"},
            {"id": "C04", "component_kind": "sub-agent",
             "build_target": "plugins/demo/agents/demo-verifier.md"},
            {"id": "C09", "component_kind": "script",
             "build_target": "plugins/demo/scripts/demo-check.py"},
        ],
        "plugin_level_surfaces": {
            "manifest": {"required": True, "path": ".claude-plugin/plugin.json"},
            "composition": {"required": True, "path": "plugin-composition.yaml"},
            "schemas": {"required": False, "omitted_reason": "n/a"},
            # path を持たない required surface (実在照合の対象外・skip される)
            "notion_config": {"required": True, "resolution": "notion_config"},
        },
    }
    with tempfile.TemporaryDirectory() as td:
        root = Path(td)
        (root / "plugins/demo/skills/run-demo").mkdir(parents=True)
        (root / "plugins/demo/skills/run-demo/SKILL.md").write_text("x", encoding="utf-8")
        (root / "plugins/demo/agents").mkdir(parents=True)
        (root / "plugins/demo/agents/demo-verifier.md").write_text("x", encoding="utf-8")
        (root / "plugins/demo/scripts").mkdir(parents=True)
        (root / "plugins/demo/scripts/demo-check.py").write_text("x", encoding="utf-8")
        (root / "plugins/demo/.claude-plugin").mkdir(parents=True)
        (root / "plugins/demo/.claude-plugin/plugin.json").write_text("{}", encoding="utf-8")
        (root / "plugins/demo/plugin-composition.yaml").write_text("x", encoding="utf-8")

        # 1. 全実体あり → 漏れなし。path 無し required surface (notion_config) は
        #    実在照合の対象外として skip される (missing に入らない)。
        mc, ms, summ = verify(inv, root)
        assert not mc, mc
        assert not ms, ms
        assert summ["components_total"] == 3
        assert "notion_config" in summ["surfaces_skipped"], summ

        # 2. skill dir はあるが SKILL.md 欠落 → component missing
        (root / "plugins/demo/skills/run-demo/SKILL.md").unlink()
        mc, ms, _ = verify(inv, root)
        assert any("C01" in e and "SKILL.md" in e for e in mc), mc
        (root / "plugins/demo/skills/run-demo/SKILL.md").write_text("x", encoding="utf-8")

        # 3. required surface (composition) 欠落 → surface missing
        (root / "plugins/demo/plugin-composition.yaml").unlink()
        mc, ms, _ = verify(inv, root)
        assert not mc, mc
        assert any("composition" in e for e in ms), ms
        (root / "plugins/demo/plugin-composition.yaml").write_text("x", encoding="utf-8")

        # 4. agent 未 build (計画にあって実体なし) → component missing
        (root / "plugins/demo/agents/demo-verifier.md").unlink()
        mc, ms, _ = verify(inv, root)
        assert any("C04" in e for e in mc), mc

    # 5. build_target 未宣言
    mc, ms, _ = verify({"components": [{"id": "Cx", "component_kind": "hook"}]}, Path("/nonexistent"))
    assert any("Cx" in e and "build_target" in e for e in mc), mc

    # 6a. cross-plugin inventory + plugin-relative path surface: root 一意解決不可を報告
    inv2 = {
        "components": [
            {"id": "C1", "component_kind": "script", "build_target": "plugins/a/scripts/x.py"},
            {"id": "C2", "component_kind": "script", "build_target": "plugins/b/scripts/y.py"},
        ],
        "plugin_level_surfaces": {"manifest": {"required": True, "path": ".claude-plugin/plugin.json"}},
    }
    _, ms, _ = verify(inv2, Path("/nonexistent"))
    assert any("一意解決できない" in e for e in ms), ms

    # 6b. cross-plugin inventory + targets[] surface: repo-relative 直接照合 (cross-plugin 安全)
    inv2b = {
        "components": [
            {"id": "C1", "component_kind": "script", "build_target": "plugins/a/scripts/x.py"},
            {"id": "C2", "component_kind": "script", "build_target": "plugins/b/scripts/y.py"},
        ],
        "plugin_level_surfaces": {
            "ref": {"required": True, "targets": ["plugins/a/refs/z.md", "plugins/b/vendor/w.py"]},
        },
    }
    _, ms2b, _ = verify(inv2b, Path("/nonexistent"))
    assert any("plugins/a/refs/z.md 不在" in e for e in ms2b), ms2b
    assert not any("一意解決できない" in e for e in ms2b), ms2b

    # 6c. path が plugins/<slug>/... の repo-relative 単一 path なら plugin-root を二重付与しない。
    with tempfile.TemporaryDirectory() as td:
        root = Path(td)
        (root / "plugins/demo/.claude-plugin").mkdir(parents=True)
        (root / "plugins/demo/.claude-plugin/plugin.json").write_text("{}", encoding="utf-8")
        inv2c = {
            "components": [
                {"id": "C1", "component_kind": "script", "build_target": "plugins/demo/scripts/x.py"},
            ],
            "plugin_level_surfaces": {
                "manifest": {"required": True, "path": "plugins/demo/.claude-plugin/plugin.json"},
            },
        }
        _, ms2c, _ = verify(inv2c, root)
        assert not ms2c, ms2c

    # 6d. target 単数は repo-relative 直接照合。
    with tempfile.TemporaryDirectory() as td:
        root = Path(td)
        (root / "plugins/demo/references").mkdir(parents=True)
        (root / "plugins/demo/references/x.md").write_text("x", encoding="utf-8")
        inv2d = {
            "components": [
                {"id": "C1", "component_kind": "script", "build_target": "plugins/demo/scripts/x.py"},
            ],
            "plugin_level_surfaces": {
                "reference": {"required": True, "target": "plugins/demo/references/x.md"},
            },
        }
        _, ms2d, _ = verify(inv2d, root)
        assert not ms2d, ms2d

    # 6e. path に括弧書き補足が混ざっていても path 部分だけで照合する。
    with tempfile.TemporaryDirectory() as td:
        root = Path(td)
        (root / "plugins/demo/skills/run-demo/schemas").mkdir(parents=True)
        inv2e = {
            "components": [
                {"id": "C1", "component_kind": "skill", "build_target": "plugins/demo/skills/run-demo/"},
            ],
            "plugin_level_surfaces": {
                "schemas": {"required": True, "path": "skills/run-demo/schemas/ (schema files)"},
            },
        }
        (root / "plugins/demo/skills/run-demo/SKILL.md").write_text("x", encoding="utf-8")
        mc2e, ms2e, _ = verify(inv2e, root)
        assert not mc2e, mc2e
        assert not ms2e, ms2e

    # 7. 空 components → 漏れなし (照合対象なし)
    mc, ms, _ = verify({"components": [], "plugin_level_surfaces": {}}, Path("/nonexistent"))
    assert not mc and not ms

    # 8. verify_all: 実体化済み plan は fail-closed で gate・未 build plan は skip
    with tempfile.TemporaryDirectory() as td:
        root = Path(td)
        plans = root / "plugin-plans"
        # (8a) realized plan (対象 plugin 実在) かつ全 build 済 → gated_ok
        (plans / "built-ok").mkdir(parents=True)
        (root / "plugins/built-ok/skills/run-x").mkdir(parents=True)
        (root / "plugins/built-ok/skills/run-x/SKILL.md").write_text("x", encoding="utf-8")
        (plans / "built-ok/component-inventory.json").write_text(json.dumps({
            "components": [{"id": "C1", "component_kind": "skill",
                            "build_target": "plugins/built-ok/skills/run-x/"}],
            "plugin_level_surfaces": {},
        }), encoding="utf-8")
        # (8b) realized plan だが component 未 build → gated_failure
        (plans / "built-gap").mkdir(parents=True)
        (root / "plugins/built-gap/skills/run-y").mkdir(parents=True)  # plugin root は在るが
        (root / "plugins/built-gap/skills/run-y/SKILL.md").write_text("x", encoding="utf-8")
        (plans / "built-gap/component-inventory.json").write_text(json.dumps({
            "components": [
                {"id": "C1", "component_kind": "skill", "build_target": "plugins/built-gap/skills/run-y/"},
                {"id": "C2", "component_kind": "sub-agent", "build_target": "plugins/built-gap/agents/z.md"},
            ],
            "plugin_level_surfaces": {},
        }), encoding="utf-8")
        # (8c) 未 build plan (対象 plugin 不在) → skipped (誤 FAIL しない)
        (plans / "not-built").mkdir(parents=True)
        (plans / "not-built/component-inventory.json").write_text(json.dumps({
            "components": [{"id": "C1", "component_kind": "hook",
                            "build_target": "plugins/not-built/hooks/g.py"}],
            "plugin_level_surfaces": {},
        }), encoding="utf-8")

        # (8e) build_target が plugins/ 配下でない = malformed → skip でなく fail-closed
        (plans / "malformed").mkdir(parents=True)
        (plans / "malformed/component-inventory.json").write_text(json.dumps({
            "components": [{"id": "C1", "component_kind": "script", "build_target": "scripts/toplevel.py"}],
            "plugin_level_surfaces": {},
        }), encoding="utf-8")

        # (8g) build_status=planned の未 build 計画ドキュメント: 対象 plugin (built-gap) が実在し
        #      component gap があっても、計画ドキュメント宣言として skip され failure に入らない。
        (plans / "planned-doc").mkdir(parents=True)
        (plans / "planned-doc/component-inventory.json").write_text(json.dumps({
            "build_status": "planned",
            "components": [
                {"id": "C1", "component_kind": "skill", "build_target": "plugins/built-gap/skills/run-y/"},
                {"id": "C2", "component_kind": "hook", "build_target": "plugins/built-gap/hooks/absent.py"},
            ],
            "plugin_level_surfaces": {},
        }), encoding="utf-8")

        failures, ok_list, skipped = verify_all(root)
        assert any(f["inventory"].endswith("built-gap/component-inventory.json") for f in failures), failures
        assert not any(f["inventory"].endswith("built-ok/component-inventory.json") for f in failures), failures
        assert any(p.endswith("built-ok/component-inventory.json") for p in ok_list), ok_list
        assert any("not-built" in s for s in skipped), skipped
        assert any("malformed" in f["inventory"] for f in failures), failures  # (8e)
        assert not any("malformed" in s for s in skipped), skipped
        assert any("planned-doc" in s and "planned" in s for s in skipped), skipped  # (8g)
        assert not any("planned-doc" in f["inventory"] for f in failures), failures  # (8g)
        assert _run_all(root, as_json=True) == 1  # 漏れありで fail-closed (planned skip は失敗に影響しない)

    # 8f. --all と位置引数の併存 → 排他 usage error (exit 2)
    assert main(["--all", "some-inv.json"]) == 2

    # 8d. plugin-plans 不在 → 対象なしで OK (exit 0)
    with tempfile.TemporaryDirectory() as td:
        assert _run_all(Path(td), as_json=True) == 0

    print("OK: validate-plan-coverage self-test (8 groups)")
    return 0


def main(argv: list[str]) -> int:
    if "--self-test" in argv:
        return _self_test()

    def _opt(name: str) -> str | None:
        if name in argv:
            i = argv.index(name)
            if i + 1 < len(argv):
                return argv[i + 1]
        return None

    repo_root_val = _opt("--repo-root")
    repo_root = Path(repo_root_val) if repo_root_val else Path.cwd()

    # 位置引数 = ハイフン始まりでなく、--repo-root の値でもないもの。
    positional = [
        a for a in argv
        if not a.startswith("-") and a != repo_root_val
    ]

    # --all: plugin-plans/*/component-inventory.json を sweep し、実体化済み plan だけを
    # fail-closed で gate する CI sweep モード (未 build plan は自動 skip で誤 FAIL しない)。
    # 位置引数 (単一 inventory の strict 照合) と排他 — 併存は silent 優先せず usage error。
    if "--all" in argv:
        if positional:
            print(
                "usage error: --all は単一 inventory 位置引数と併用不可 "
                f"(併存: {positional})。sweep か単一照合のどちらかを指定する。",
                file=sys.stderr,
            )
            return 2
        return _run_all(repo_root, as_json=("--json" in argv))

    if not positional:
        print(
            "usage: validate-plan-coverage.py <component-inventory.json> "
            "[--repo-root <dir>] [--json]",
            file=sys.stderr,
        )
        return 2

    inv_path = Path(positional[0])

    if not inv_path.exists():
        print(f"component-inventory.json not found: {inv_path}", file=sys.stderr)
        return 2
    try:
        inventory = json.loads(inv_path.read_text(encoding="utf-8"))
    except json.JSONDecodeError as exc:
        print(f"JSON parse error: {exc}", file=sys.stderr)
        return 2
    if not isinstance(inventory, dict):
        print("component-inventory root が object でない", file=sys.stderr)
        return 2

    missing_components, missing_surfaces, summary = verify(inventory, repo_root)
    ok = not (missing_components or missing_surfaces)

    if "--json" in argv:
        print(json.dumps(
            {
                "ok": ok,
                "summary": summary,
                "missing_components": missing_components,
                "missing_surfaces": missing_surfaces,
            },
            ensure_ascii=False,
            indent=2,
        ))
        return 0 if ok else 1

    if not ok:
        print(
            f"FAIL: plan coverage — 計画にあって未 build "
            f"({len(missing_components)} component / {len(missing_surfaces)} surface)",
            file=sys.stderr,
        )
        for e in missing_components:
            print(f"  - [component] {e}", file=sys.stderr)
        for e in missing_surfaces:
            print(f"  - [surface] {e}", file=sys.stderr)
        print(
            "  → routes[] の build を完了させるか、計画側 (component-inventory.json) から"
            " 当該 component を除外して再実行する。plugin-compose の実体再計算では"
            "『計画に対する漏れ』は検出できず、本 gate だけが担う。",
            file=sys.stderr,
        )
        return 1

    print(
        f"OK: plan coverage — {summary['components_total']} component "
        f"+ required surface すべて実在 "
        f"({', '.join(summary['plugin_roots']) or 'n/a'})"
    )
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
