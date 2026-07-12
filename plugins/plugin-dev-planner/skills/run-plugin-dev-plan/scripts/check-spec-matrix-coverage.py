#!/usr/bin/env python3
# /// script
# name: check-spec-matrix-coverage
# purpose: harness-creator-spec-reflection.md の46行を読み、各行に scope(phase|inventory|plugin)/klass 別の適用述語と焼き先アンカーを持たせ、適用される行のアンカーが該当 inventory component(component-level)か index plugin_meta(plugin-level)に反映されているか検査する決定論ゲート。
# inputs:
#   - argv: <plan-dir> [--matrix PATH] [--index NAME] [--inventory FILE] | --self-test
# outputs:
#   - stdout: OP/conditional/N-A 内訳件数 + OK サマリ
#   - stderr: 未反映の適用行 violation
#   - exit: 0=OK / 1=violation / 2=usage error
# contexts: [C, E]
# network: false
# write-scope: none
# dependencies: []
# requires-python: ">=3.10"
# ///
"""46行マトリクスの operationalize 被覆検査 (R4 自然言語突合の機械化)。

per-phase 転換 (凍結契約 §4/§11): 焼き先は 3 scope へ写像される。
- `inventory` scope: 焼き先アンカーは component-inventory.json の component エントリのキー
  (旧 per-component frontmatter の焼き先を inventory component へ remap)。
- `plugin` scope: 焼き先アンカーは index(main) の plugin_meta のキー (plugin 階層)。
- `phase` scope: 焼き先が phase ファイルの物語 (完了条件等) で機械アンカーを持たない process/reference 行
  (旧 component-scope N-A)。計数のみ (機械検査対象外・意味は content-review/人間トラスト)。

--self-test は (a) reflection.md の行 id 集合と本 table の id 集合の drift (46 行・集合完全一致) と
(b) reflection.md 焼き先列の粗トークン (inventory / plugin_meta) と ROWS scope の矛盾を検出する
(md が機械アンカーを謳うのに table が別 scope に登録される片肺 drift を塞ぐ)。
harness-creator-spec-reflection.md の焼き先列と同期する。
"""
from __future__ import annotations

import argparse
import json
import re
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import specfm  # noqa: E402

_DEFAULT_MATRIX = Path(__file__).resolve().parent.parent / "references" / "harness-creator-spec-reflection.md"
_ROW_ID_RE = re.compile(r"^\|\s*([A-G]\d{1,2})\s*\|")


# --- 適用述語 (inventory-scope 行のみ使用・引数は component context dict) ---
def _always(c: dict) -> bool:
    return True


def _is_skill(c: dict) -> bool:
    return c["component_kind"] == "skill"


def _skill_loop(c: dict) -> bool:
    return c["component_kind"] == "skill" and c["skill_kind"] in specfm.FEEDBACK_LOOP_SKILL_KINDS


def _prompt_bearing(c: dict) -> bool:
    return (c["component_kind"] == "skill" and c["skill_kind"] in ("run", "assign")) \
        or c["component_kind"] == "sub-agent"


def _feat_knowledge(c: dict) -> bool:
    return "knowledge_loop" in c["features"]


def _is_script(c: dict) -> bool:
    return c["component_kind"] == "script"


# --- 46行 operationalization テーブル (scope, klass, applies, anchor) ---
# scope: inventory=component-inventory.json の component エントリ / plugin=index.plugin_meta /
#        phase=phase ファイル物語 (機械アンカー無し・N-A)。anchor は dotted path。
ROWS: dict[str, tuple[str, str, object, str | None]] = {
    "A1": ("inventory", "OP", _always, "quality_gates.elegant_review"),
    "A2": ("phase", "N-A", _always, None),
    "A3": ("phase", "N-A", _always, None),
    "A4": ("phase", "N-A", _always, None),
    "A5": ("inventory", "OP", _always, "quality_gates.evaluator"),
    "A6": ("phase", "N-A", _always, None),
    # 注: A7(plugin-package-evaluator) と F5(PKG 契約) は意図的に同一 anchor `pkg_contract` を
    # 共有する (io-contract.md plugin_meta「# A7/F5」と一致)。matrix-coverage はスロット存在のみを
    # 見るため両行は 1 スロットで addressed 判定される。A7 vs F5 の値レベル充足の区別は
    # check-spec-gates(値域) / content-review(内容) の責務 (機械=存在 / LLM=faithfulness の二層分離)。
    "A7": ("plugin", "conditional", _always, "pkg_contract"),
    "A8": ("inventory", "OP", _always, "quality_gates.content_review"),
    "A9": ("phase", "N-A", _always, None),
    "A10": ("plugin", "conditional", _always, "governance"),
    "A11": ("inventory", "conditional", _prompt_bearing, "prompt_layer"),
    "B1": ("inventory", "conditional", _skill_loop, "feedback_contract.criteria"),
    "B2": ("phase", "N-A", _always, None),
    "B3": ("phase", "N-A", _always, None),
    # B4/B5: feedback+Notion 連携 (B4=notion_config per-project DB 解決 SSOT / B5=improvement-request
    # schema 受け皿 DB)。両行は D6 と同一 anchor `feedback_deploy` を意図的共有する (A7/F5 と同型:
    # matrix はスロット存在のみ・notion_sink/portability の値域は check-spec-gates、inventory 側
    # notion_config surface の採否は specfm.validate_surface_inventory の責務)。
    "B4": ("plugin", "conditional", _always, "feedback_deploy"),
    "B5": ("plugin", "conditional", _always, "feedback_deploy"),
    "C1": ("inventory", "OP", _always, "harness_coverage"),
    "C2": ("inventory", "OP", _always, "harness_coverage.min"),
    "C3": ("phase", "N-A", _always, None),
    "C4": ("phase", "N-A", _always, None),
    "D1": ("inventory", "conditional", _skill_loop, "goal_seek"),
    "D2": ("inventory", "conditional", _skill_loop, "goal_seek"),
    "D3": ("phase", "N-A", _always, None),
    "D4": ("phase", "N-A", _always, None),
    "D5": ("inventory", "conditional", _skill_loop, "goal_seek"),
    "D6": ("plugin", "conditional", _always, "feedback_deploy"),
    "E1": ("inventory", "conditional", _is_skill, "skill_name"),
    # E2: skill kind は inventory では canonical `skill_kind` に載る (kind は後方互換)。焼き先を skill_kind へ。
    "E2": ("inventory", "conditional", _is_skill, "skill_kind"),
    "E3": ("phase", "N-A", _always, None),
    "E4": ("phase", "N-A", _always, None),
    "E5": ("inventory", "conditional", _prompt_bearing, "prompt_layer"),
    "E6": ("inventory", "conditional", _prompt_bearing, "prompt_layer"),
    "F1": ("inventory", "OP", _always, "quality_gates.p0_lint"),
    "F2": ("inventory", "OP", _always, "quality_gates.build_trace"),
    "F3": ("plugin", "OP", _always, "distribution"),
    "F4": ("plugin", "OP", _always, "distribution.bundles"),
    "F5": ("plugin", "conditional", _always, "pkg_contract"),
    "F6": ("plugin", "OP", _always, "ci"),
    "F7": ("plugin", "conditional", _always, "ssot_dedup"),
    # F8: install-portability。script component のみ placement_scope 焼き先を要求する
    # (共有 script の plugin-root hoist 判定=install 携帯性。skill/agent 等は対象外)。
    "F8": ("inventory", "conditional", _is_script, "placement_scope"),
    "G1": ("inventory", "conditional", _feat_knowledge, "knowledge_loop"),
    "G2": ("inventory", "conditional", _is_skill, "combinators"),
    "G3": ("phase", "N-A", _always, None),
    "G4": ("phase", "N-A", _always, None),
    "G5": ("phase", "N-A", _always, None),
    "G6": ("phase", "N-A", _always, None),
}


# --- 分類の行 ID 集合を固定 (件数 drift でなく集合入替も検出する) ---
EXPECTED_OP = {"A1", "A5", "A8", "C1", "C2", "F1", "F2", "F3", "F4", "F6"}
EXPECTED_CONDITIONAL = {
    "A7", "A10", "F5", "F7", "F8", "D6", "B1", "B4", "B5", "D1", "D2", "D5",
    "A11", "E5", "E6", "E1", "E2", "G1", "G2",
}
EXPECTED_NA = {
    "A2", "A3", "A4", "A6", "A9", "B2", "B3", "C3", "C4",
    "D3", "D4", "E3", "E4", "G3", "G4", "G5", "G6",
}


def classify_counts() -> dict[str, int]:
    counts = {"OP": 0, "conditional": 0, "N-A": 0}
    for _scope, klass, _ap, _anchor in ROWS.values():
        counts[klass] += 1
    return counts


def current_classification() -> dict[str, str]:
    """行 id -> klass の現行マッピングを返す。"""
    return {rid: klass for rid, (_s, klass, _a, _an) in ROWS.items()}


def membership_drift(classification: dict[str, str] | None = None) -> list[str]:
    """各クラスの行 ID 集合が固定集合と完全一致するかを検査する。

    件数 {10,17,17} が保たれたまま OP↔N-A を 1:1 入替するような分類すり替えを
    集合差で検出する (件数 only ガードの穴を塞ぐ)。
    """
    c = classification if classification is not None else current_classification()
    op = {r for r, k in c.items() if k == "OP"}
    cond = {r for r, k in c.items() if k == "conditional"}
    na = {r for r, k in c.items() if k == "N-A"}
    errs: list[str] = []
    for name, got, exp in (("OP", op, EXPECTED_OP), ("conditional", cond, EXPECTED_CONDITIONAL), ("N-A", na, EXPECTED_NA)):
        if got != exp:
            errs.append(f"{name} 集合 drift: 余分={sorted(got - exp)} 欠落={sorted(exp - got)}")
    return errs


def parse_matrix_ids(md_text: str) -> list[str]:
    """reflection.md のテーブル行から行 id を抽出する。"""
    return [m.group(1) for line in md_text.splitlines() if (m := _ROW_ID_RE.match(line))]


def parse_matrix_burn_targets(md_text: str) -> dict[str, str]:
    """reflection.md のテーブル行から 行 id -> 焼き先列 (最終セル) を抽出する。

    セル内のエスケープ pipe (`\\|`) を退避してから分割する (`PASS\\|FAIL` 等を跨がない)。
    """
    out: dict[str, str] = {}
    for line in md_text.splitlines():
        m = _ROW_ID_RE.match(line)
        if not m:
            continue
        sanitized = line.replace("\\|", "\x00")
        cells = [c.replace("\x00", "\\|").strip() for c in sanitized.strip().strip("|").split("|")]
        if len(cells) >= 5:
            out[m.group(1)] = cells[-1]
    return out


def burn_target_scope_drift(md_text: str) -> list[str]:
    """reflection.md 焼き先列の粗トークンと ROWS scope の矛盾を返す (MD-02 の機械化)。

    焼き先列が機械アンカー粗トークン (`inventory` / `plugin_meta`) を謳う行は、ROWS の scope が
    その集合に含まれること。P 段階名のみ (粗トークン無し) の行は無拘束 (phase scope の物語焼き先)。
    N-A/phase 行が機械アンカーを謳う・md と table で焼き先層が食い違う、の両 drift を検出する。
    """
    errs: list[str] = []
    for rid, cell in parse_matrix_burn_targets(md_text).items():
        if rid not in ROWS:
            continue  # id 集合 drift は self_test の集合検査が担う
        scope = ROWS[rid][0]
        tokens: set[str] = set()
        if "inventory" in cell:
            tokens.add("inventory")
        if "plugin_meta" in cell:
            tokens.add("plugin")
        if tokens and scope not in tokens:
            errs.append(
                f"行 {rid}: reflection.md 焼き先列の粗トークン {sorted(tokens)} と "
                f"ROWS scope={scope!r} が不一致 (md↔table の焼き先層 drift)"
            )
    return errs


def _has(d: object, dotted: str) -> bool:
    """dotted path のキーが「焼き先として addressed」かを返す。

    matrix-coverage は「焼き先スロットが反映されているか」を見る (値域の正否は
    check-spec-gates の責務)。明示的に置かれた空コンテナ ([] / {}) は addressed と
    みなす。欠落・None・空文字のみ未反映とする。
    """
    cur = d
    for part in dotted.split("."):
        if not isinstance(cur, dict) or part not in cur:
            return False
        cur = cur[part]
    return cur is not None and cur != ""


def component_context(comp: dict) -> dict:
    """inventory component から適用述語用の context を作る。"""
    return {
        "component_kind": str(comp.get("component_kind", "")).strip(),
        "skill_kind": specfm._skill_kind_of(comp),
        "features": set(comp.get("features", []) or []),
    }


def check_inventory_coverage(components: list[dict]) -> list[str]:
    """各 inventory component に対し、適用される inventory-scope 行で未反映の焼き先を返す。"""
    findings: list[str] = []
    for comp in components:
        cid = str(comp.get("id", "")).strip() or "?"
        ctx = component_context(comp)
        for rid, (scope, klass, applies, anchor) in ROWS.items():
            if scope != "inventory" or klass == "N-A" or anchor is None:
                continue
            if applies(ctx) and not _has(comp, anchor):
                findings.append(f"component {cid}: 適用行 {rid} (anchor={anchor}) の焼き先が未反映")
    return findings


def check_plugin_coverage(plugin_meta: dict) -> list[str]:
    """index の plugin_meta に対し、未反映の plugin-scope 行 id を返す。"""
    missing: list[str] = []
    for rid, (scope, klass, _applies, anchor) in ROWS.items():
        if scope != "plugin" or klass == "N-A" or anchor is None:
            continue
        if not _has(plugin_meta, anchor):
            missing.append(f"{rid} (plugin anchor={anchor})")
    return missing


def load_components(inventory_path: Path) -> tuple[list[dict], str | None]:
    try:
        data = json.loads(inventory_path.read_text(encoding="utf-8"))
    except json.JSONDecodeError as exc:
        return [], f"component-inventory JSON parse error: {exc}"
    if not isinstance(data, dict) or not isinstance(data.get("components"), list):
        return [], "component-inventory.json に components[] list が無い"
    return [c for c in data["components"] if isinstance(c, dict)], None


def run(plan_dir: Path, index_name: str, inventory_path: Path | None) -> tuple[int, list[str], dict[str, int]]:
    counts = classify_counts()
    index_path = plan_dir / index_name
    if not index_path.is_file():
        return 2, [f"index が見つからない: {index_path}"], counts
    if inventory_path is None:
        inventory_path = plan_dir / "component-inventory.json"
    if not inventory_path.is_file():
        return 2, [f"component-inventory.json が見つからない: {inventory_path}"], counts

    components, msg = load_components(inventory_path)
    if msg:
        return 2, [msg], counts
    findings: list[str] = check_inventory_coverage(components)

    index_fm = specfm.parse_frontmatter(index_path.read_text(encoding="utf-8"))
    plugin_meta = index_fm.get("plugin_meta", {})
    if not isinstance(plugin_meta, dict):
        plugin_meta = {}
    for m in check_plugin_coverage(plugin_meta):
        findings.append(f"{index_name}: plugin-level 行 {m} の焼き先が未反映")
    return (1 if findings else 0), findings, counts


def self_test(matrix_path: Path) -> tuple[int, list[str]]:
    if not matrix_path.is_file():
        return 2, [f"matrix not found: {matrix_path}"]
    md_text = matrix_path.read_text(encoding="utf-8")
    ids = set(parse_matrix_ids(md_text))
    table = set(ROWS)
    msgs: list[str] = []
    if ids - table:
        msgs.append(f"reflection.md に table 未登録の行: {sorted(ids - table)}")
    if table - ids:
        msgs.append(f"table にあるが reflection.md に無い行: {sorted(table - ids)}")
    if len(table) != 46:
        msgs.append(f"table 行数 {len(table)} != 46")
    msgs.extend(membership_drift())  # 件数不変の OP↔N-A 入替も検出 (集合完全一致ガード)
    msgs.extend(burn_target_scope_drift(md_text))  # md 焼き先列 ↔ ROWS scope の層 drift (MD-02)
    return (1 if msgs else 0), msgs


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description="46行マトリクスの operationalize 被覆を検証する")
    ap.add_argument("plan_dir", nargs="?", help="plan ディレクトリ")
    ap.add_argument("--matrix", default=str(_DEFAULT_MATRIX), help="reflection.md パス")
    ap.add_argument("--index", default="index.md", help="index ファイル名")
    ap.add_argument("--inventory", default=None, help="component-inventory.json (既定 <plan_dir>/component-inventory.json)")
    ap.add_argument("--self-test", action="store_true", help="table と reflection.md の drift 検査")
    args = ap.parse_args(argv)

    if args.self_test:
        code, msgs = self_test(Path(args.matrix))
        if code == 0:
            sys.stdout.write("OK: 46行 table と reflection.md が一致 (id 集合/分類/焼き先層 drift なし)\n")
            return 0
        for m in msgs:
            sys.stderr.write(m + "\n")
        return code

    if not args.plan_dir:
        sys.stderr.write("usage: check-spec-matrix-coverage.py <plan-dir> | --self-test\n")
        return 2
    plan_dir = Path(args.plan_dir)
    if not plan_dir.is_dir():
        sys.stderr.write(f"not a directory: {plan_dir}\n")
        return 2
    inventory_path = Path(args.inventory) if args.inventory else None
    code, findings, counts = run(plan_dir, args.index, inventory_path)
    sys.stdout.write(
        f"matrix 分類: OP={counts['OP']} / conditional={counts['conditional']} / N-A={counts['N-A']} (計 {sum(counts.values())})\n"
    )
    if code == 0:
        sys.stdout.write("OK: 適用される全マトリクス行の焼き先が反映済み\n")
        return 0
    for m in findings:
        sys.stderr.write(m + "\n")
    return code


if __name__ == "__main__":
    raise SystemExit(main())
