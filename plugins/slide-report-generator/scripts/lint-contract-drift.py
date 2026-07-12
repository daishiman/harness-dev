#!/usr/bin/env python3
# /// script
# name: lint-contract-drift
# purpose: report 経路の prose(references/prompts)↔code(render-report.js/validate-report-visual.py/schema)の contract-drift を fail-closed 検出する plugin-root glue。散文が主張する data-* 属性名・閾値・render-fidelity class・placement field 消費を実装と機械突合し、「宣言 > 実装」の同型ドリフト(phantom data-focal-y / report.css phantom / dead field / 閾値ズレ)の再発を封鎖する。CLI と import(pytest)両対応・Python 標準ライブラリのみ。
# inputs:
#   - CLI: [--root <plugin-root>] [--json]
# outputs:
#   - stdout: JSON (findings[])
#   - exit: 0=drift 無し(PASS) / 1=drift 検出(fail-closed) / 2=対象ファイル不在。
# contexts: [glue]
# network: false
# write-scope: none
# dependencies: []
# requires-python: ">=3.10"
# ///
"""report 経路の prose↔code contract-drift ゲート (fail-closed)。

30思考法エレガント検証(3 独立 analyst)が amplified pattern として一致提案した機構。
build のたびに散文(prompts/references)と実装(renderer/validator/schema)が
静かに乖離する『宣言 > 実装/ゲート』の同型ドリフトを、人手照合でなく機械で封鎖する。

検査 (report 語彙にスコープ):
  A data-attr existence : prose が引用する data-* 属性名を render-report.js が実 emit するか。
                          (phantom 属性 = 実装しない属性名の教示 を検出。例: data-focal-y)
  B threshold parity    : prose が `key=N` で引用する閾値が DEFAULT_THRESHOLDS の値と一致するか。
                          (例: doc_highlight_budget=24 の散文↔code ズレ)
  C fidelity chain      : validate-report-visual.py が render-fidelity で検査する class/属性を
                          render-report.js が実 emit するか。(validator が emit しない class を
                          検査する = 常に fail する空ゲート を検出)
  D placement field     : schema placement の各 field が render-report.js に消費されるか、
                          消費しないなら schema description に "advisory" と明記されているか。
                          (dead field = 宣言のみで render 未反映 を検出)
  E role-policy SSOT     : role→narrative 方針の機械可読 SSOT (validate-report-visual.py の
                          _NARRATIVE_REQUIRED/OPTIONAL_ROLES) と reference report-narrative-logic.md
                          §6.1 の role 群表が過不足なく一致するか。(3系統手更新の drift を封鎖。
                          schema role enum との MECE は tests が担保)

exit: 0=PASS(drift 無し) / 1=drift 検出 / 2=usage・対象ファイル不在。
pytest からは run_checks(root) を import して findings[] を得る。
"""
from __future__ import annotations

import argparse
import json
import re
import sys
from pathlib import Path


def _plugin_root(explicit: str | None) -> Path:
    if explicit:
        return Path(explicit)
    # scripts/lint-contract-drift.py → plugin root は 1 つ上。
    return Path(__file__).resolve().parent.parent


# report 経路で「render が X を Y へ反映する」系の主張を書く散文ファイル群 (drift 源)。
_PROSE_GLOBS = [
    "references/report-*.md",
    "references/mermaid-integration.md",
    "skills/run-slide-report-generate/references/report-*.md",
    "skills/run-slide-report-generate/prompts/R2-agent-report-structure-designer.md",
    "skills/run-slide-report-generate/prompts/R2-agent-visual-strategist.md",
    "skills/run-slide-report-generate/prompts/R3-agent-report-composer.md",
    "skills/run-slide-report-generate/prompts/R3-agent-report-quality-reviewer.md",
]

_RENDER = "vendor/scripts/render-report.js"
_VALIDATOR = "scripts/validate-report-visual.py"
_SCHEMA = "schemas/report-structure.schema.json"

_DATA_ATTR_RE = re.compile(r"data-[a-z][a-z0-9-]*")
# render が emit する data-* だけを真とみなすため、renderReport 由来のコードから抽出する。
# prose 側で意味マーカとして許容する非 render 由来の data-*（現状なし）はここで allowlist する。
_DATA_ATTR_ALLOWLIST: set[str] = set()


def _cited_data_attrs(text: str) -> set[str]:
    """散文中で『HTML data-* 属性として主張されている』トークンだけを抽出する。

    backtick インラインコード内 or 属性構文 `data-xxx=` に現れるものに限定し、
    『data-ink 比』のような可視化ドメイン用語(属性でない散文)を誤検出しない。
    """
    attrs: set[str] = set()
    for span in re.findall(r"`([^`]+)`", text):          # インラインコード span 内
        attrs.update(_DATA_ATTR_RE.findall(span))
    attrs.update(re.findall(r"(data-[a-z][a-z0-9-]*)\s*=", text))  # 属性構文 data-xxx=
    return attrs


def _read(root: Path, rel: str) -> str:
    p = root / rel
    return p.read_text(encoding="utf-8") if p.is_file() else ""


def _prose_files(root: Path) -> list[Path]:
    files: list[Path] = []
    for g in _PROSE_GLOBS:
        files.extend(sorted(root.glob(g)))
    return [f for f in files if f.is_file()]


def _load_thresholds(root: Path) -> dict:
    """validate-report-visual.py を import せず DEFAULT_THRESHOLDS を決定論抽出する。"""
    src = _read(root, _VALIDATOR)
    m = re.search(r"DEFAULT_THRESHOLDS\s*=\s*\{(.*?)\n\}", src, re.DOTALL)
    out: dict[str, int] = {}
    if not m:
        return out
    for key, val in re.findall(r'"([a-z_]+)"\s*:\s*(\d+)', m.group(1)):
        out[key] = int(val)
    return out


def _validator_fidelity_targets(root: Path) -> set[str]:
    """validate-report-visual.py が render-fidelity で存在検査する class/data 属性を抽出する。"""
    src = _read(root, _VALIDATOR)
    targets: set[str] = set()
    # `"report-xxx" not in html` / `"data-xxx" not in html` パターン + block_class map の値。
    for tok in re.findall(r'"(report-[a-z-]+|data-[a-z-]+)"\s*(?:not )?in html', src):
        targets.add(tok)
    for tok in re.findall(r'"(report-[a-z-]+)"', src):
        # block_class map の値 (report-deflist 等) も含める。render-fidelity で使う class に限定するため
        # 実際の in-html 検査に現れるものだけを上で拾い、ここは補助 (block_class 由来)。
        if tok in ("report-deflist", "report-footnotes", "report-tasklist"):
            targets.add(tok)
    return targets


def _load_role_sets(root: Path) -> tuple[set[str], set[str]]:
    """validate-report-visual.py を機械可読 SSOT とみなし role→narrative 方針2集合を抽出する。"""
    src = _read(root, _VALIDATOR)

    def extract(name: str) -> set[str]:
        m = re.search(name + r"\s*=\s*\{(.*?)\n\}", src, re.DOTALL)
        return set(re.findall(r'"([a-z-]+)"', m.group(1))) if m else set()

    return extract("_NARRATIVE_REQUIRED_ROLES"), extract("_NARRATIVE_OPTIONAL_ROLES")


def _reference_role_groups(root: Path) -> dict[str, set[str]]:
    """report-narrative-logic.md §6.1 の role→narrative 表から group 別 role 集合を抽出する。

    group 列 (`**期待**` / `**不要**` / `**文脈依存**`) を含む行の backtick role を拾う。
    表が見つからなければ空 dict (構造変更時に誤検出しないため呼び出し側で skip)。
    """
    text = _read(root, "references/report-narrative-logic.md")
    groups: dict[str, set[str]] = {}
    for line in text.splitlines():
        if not line.lstrip().startswith("|"):
            continue
        for label, key in (("**期待**", "expected"), ("**不要**", "optional_strict"), ("**文脈依存**", "context")):
            if label in line:
                roles = set(re.findall(r"`([a-z][a-z-]*)`", line))
                if roles:
                    groups[key] = roles
    return groups


def _placement_fields(root: Path) -> tuple[list[str], dict[str, str]]:
    """schema placement の field 名と各 field description を返す (deprecated alias emphasis は除外)。"""
    try:
        schema = json.loads(_read(root, _SCHEMA))
    except (json.JSONDecodeError, ValueError):
        return [], {}
    props = (((schema.get("$defs") or {}).get("placement") or {}).get("properties")) or {}
    fields = [k for k in props if k != "emphasis"]  # emphasis は emphasisZone の後方互換 alias
    descs = {k: (props[k].get("description") or "") for k in props}
    return fields, descs


def run_checks(root: Path) -> list[dict]:
    """4 チェックを実行し drift findings[] を返す (副作用なし)。"""
    findings: list[dict] = []

    def add(check, message, where):
        findings.append({"check": check, "message": message, "where": where})

    render_src = _read(root, _RENDER)
    if not render_src:
        add("io", f"{_RENDER} が読めない (対象不在)", _RENDER)
        return findings

    # render が emit する data-* の集合 (真の実装側)。
    emitted_attrs = set(_DATA_ATTR_RE.findall(render_src)) | _DATA_ATTR_ALLOWLIST

    prose_files = _prose_files(root)

    # -- A: prose の data-* を render が emit するか -------------------------------
    for pf in prose_files:
        text = pf.read_text(encoding="utf-8")
        for attr in sorted(_cited_data_attrs(text)):
            if attr not in emitted_attrs:
                add("data-attr-phantom",
                    f"prose が data 属性 '{attr}' を主張するが render-report.js が emit しない (phantom 属性・実装と一致させる)",
                    str(pf.relative_to(root)))

    # -- B: prose の閾値引用が DEFAULT_THRESHOLDS と一致するか ---------------------
    thresholds = _load_thresholds(root)
    for pf in prose_files:
        text = pf.read_text(encoding="utf-8")
        for key, val in thresholds.items():
            for cited in re.findall(re.escape(key) + r"\s*[=＝]\s*(\d+)", text):
                if int(cited) != val:
                    add("threshold-drift",
                        f"prose が '{key}={cited}' と引用するが DEFAULT_THRESHOLDS は {key}={val} (閾値ズレ)",
                        str(pf.relative_to(root)))

    # -- C: validator の render-fidelity 検査対象を render が emit/生成するか --------
    for target in sorted(_validator_fidelity_targets(root)):
        if target not in render_src:
            add("fidelity-orphan",
                f"validate-report-visual.py が render-fidelity で '{target}' を検査するが render-report.js が生成しない (空ゲート・検査は常に fail する)",
                _VALIDATOR)

    # -- D: schema placement field が render 消費 or advisory 明記か -----------------
    fields, descs = _placement_fields(root)
    for field in fields:
        consumed = (f"layout.{field}" in render_src) or (f".{field}" in render_src) or (field in render_src and field == "grid")
        advisory = "advisory" in descs.get(field, "")
        if not consumed and not advisory:
            add("placement-dead-field",
                f"schema placement.{field} が render-report.js に消費されず schema description にも 'advisory' 明記が無い (dead field・live 化 or advisory 明記が要る)",
                _SCHEMA)

    # -- E: role→narrative 方針の SSOT(validator)↔ reference §6.1 表 一致 --------------
    # validate-report-visual.py の2集合を機械可読 SSOT とし、reference の role 群表が
    # それと過不足なく一致するか検証する (3系統手更新の drift を封鎖)。
    required, optional = _load_role_sets(root)
    groups = _reference_role_groups(root)
    if required and optional and {"expected", "optional_strict", "context"} <= set(groups):
        ref_expected = groups["expected"]
        ref_optional = groups["optional_strict"] | groups["context"]
        if ref_expected != required:
            add("role-policy-drift",
                f"reference §6.1『期待』群 {sorted(ref_expected)} が validator _NARRATIVE_REQUIRED_ROLES {sorted(required)} と不一致",
                "references/report-narrative-logic.md")
        if ref_optional != optional:
            add("role-policy-drift",
                f"reference §6.1『不要+文脈依存』群 {sorted(ref_optional)} が validator _NARRATIVE_OPTIONAL_ROLES {sorted(optional)} と不一致",
                "references/report-narrative-logic.md")
    elif required and optional and _read(root, "references/report-narrative-logic.md") and "**期待**" not in _read(root, "references/report-narrative-logic.md"):
        add("role-policy-drift",
            "reference report-narrative-logic.md に §6.1 role→narrative 表(**期待**/**不要**/**文脈依存**)が見つからない (SSOT 表が消失・validator と突合不能)",
            "references/report-narrative-logic.md")

    return findings


def _build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(
        prog="lint-contract-drift",
        description="report 経路 prose↔code の contract-drift ゲート (fail-closed): data-attr/閾値/render-fidelity/placement field",
    )
    p.add_argument("--root", default=None, help="plugin root (既定=本スクリプトの1つ上)")
    p.add_argument("--json", action="store_true", help="(既定で JSON 出力・互換用フラグ)")
    return p


def main(argv=None) -> int:
    args = _build_parser().parse_args(argv)
    root = _plugin_root(args.root)
    if not (root / _RENDER).is_file():
        sys.stderr.write(f"error: render source not found under {root}\n")
        return 2
    findings = run_checks(root)
    result = {"passed": len(findings) == 0, "count": len(findings), "findings": findings}
    sys.stdout.write(json.dumps(result, ensure_ascii=False, indent=2) + "\n")
    return 0 if result["passed"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
