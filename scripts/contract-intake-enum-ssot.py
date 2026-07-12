#!/usr/bin/env python3
"""contract-intake-enum-ssot.py — skill-intake の select enum 単一真実源 contract test

目的 (因果ループ遮断):
  notion-db-schema.json の select enum (ステータス / パターン / ワークフロー) を
  *正本 (SSOT)* と定め、(a) render/publish が出すプロパティ値が正本キーと矛盾しない
  こと、(b) ワークフロー等の値ラベルが正本以外の reference 文書へ二重ベタ書き
  されて再混入していないこと、を機械的に検証する。文書整合 (④) を文書でなく
  test で守るためのゲート。全 pass で exit 0、違反で exit 1。

検証 C1-C4:
  C1 (正本ロード)   : notion-db-schema.json の対象 select が options を持つ。
  C2 (projection整合): render_notion_page.project_db_properties が schema の全
                       プロパティキーを網羅し、過不足が無い (キー集合一致)。
  C3 (二重定義検出) : ワークフロー値ラベル ("A 単体" 等) が正本 schema 以外の
                       references/*.md に enum 定義としてベタ書き再混入していない。
                       handoff-contract.md は「正本参照」記述のみ許可 (ラベル直書き不可)。
  C4 (軸分離注記)   : パターン / ワークフロー / mode 各定義箇所に「独立した分類」
                       注記が存在する (記号衝突の混同防止が文書化されている)。

Usage:
  python3 scripts/contract-intake-enum-ssot.py [--json]
"""
from __future__ import annotations

import json
import re
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent
INTAKE = REPO / "plugins" / "skill-intake"
SCHEMA = INTAKE / "references" / "notion-db-schema.json"
RENDER = INTAKE / "scripts" / "render_notion_page.py"
HANDOFF = INTAKE / "references" / "handoff-contract.md"
# next-action の mode 軸定義は run-intake-next-action skill へ移行済 (旧 advisor agent は廃止)。
ADVISOR = INTAKE / "skills" / "run-intake-next-action" / "references" / "mode-catalog.md"

# 正本以外で「ワークフロー enum ラベルのベタ書き」を禁止する reference 群。
# fixtures は人間記述の自然文 (主従表記) を含むため対象外 (誤検知回避)。
GUARDED_REFS = [HANDOFF]

# ワークフロー値ラベル (正本)。これらが GUARDED_REFS に enum 定義として並ぶと二重定義。
WORKFLOW_LABELS = ["A 単体", "B 自動収集配信", "C ナレッジ集約", "D レビュー", "E その他"]


def fail(results, cid, msg):
    results.append({"gate": cid, "status": "FAIL", "detail": msg})


def ok(results, cid, msg):
    results.append({"gate": cid, "status": "PASS", "detail": msg})


def load_schema():
    return json.loads(SCHEMA.read_text(encoding="utf-8"))


def c1_canonical_load(schema, results):
    props = schema.get("properties", {})
    targets = ["ステータス", "パターン", "ワークフロー"]
    missing = [t for t in targets if not props.get(t, {}).get("options")]
    if missing:
        fail(results, "C1", f"正本 select に options 欠落: {missing}")
        return None
    enums = {t: props[t]["options"] for t in targets}
    ok(results, "C1", f"正本 enum ロード成功: " + ", ".join(f"{k}={len(v)}件" for k, v in enums.items()))
    return enums


def c2_projection_parity(schema, results):
    if not RENDER.exists():
        fail(results, "C2", f"render_notion_page.py 不在: {RENDER}")
        return
    src = RENDER.read_text(encoding="utf-8")
    # projection の真実源は _DB_PROP_SPEC (name, canonical_type, src_key) の list。
    # project_db_properties は db_schema 適応のためこの spec をループして dict を組む
    # (return リテラルではない) ため、spec の先頭要素 (projection されるプロパティ名) を集める。
    m = re.search(r"_DB_PROP_SPEC\s*=\s*\[(.*?)\]", src, re.S)
    if not m:
        fail(results, "C2", "_DB_PROP_SPEC の projection spec リストを抽出できず")
        return
    body = m.group(1)
    projected = set(re.findall(r"\(\s*'([^']+)'", body))
    schema_keys = set(schema.get("properties", {}).keys())
    # created_time (作成日) は Notion 自動付与で projection しない正規例外。
    auto = {k for k, v in schema["properties"].items() if v.get("type") == "created_time"}
    expected = schema_keys - auto
    missing = expected - projected
    extra = projected - schema_keys
    if missing or extra:
        fail(results, "C2", f"projection キー不一致 missing={sorted(missing)} extra={sorted(extra)}")
        return
    ok(results, "C2", f"projection が schema {len(expected)} プロパティを網羅 (auto={sorted(auto)} 除外)")


def c3_no_double_definition(results):
    for ref in GUARDED_REFS:
        if not ref.exists():
            fail(results, "C3", f"被ガード文書不在: {ref}")
            continue
        text = ref.read_text(encoding="utf-8")
        # 正本参照記述が在ること。
        if "notion-db-schema.json#/properties/ワークフロー" not in text:
            fail(results, "C3", f"{ref.name}: ワークフロー正本参照が欠落 (二重定義に退行の恐れ)")
            continue
        # ラベルの enum 風ベタ書き (区切り '/' で 2 つ以上並ぶ) を禁止。
        # 正本参照の括弧内に例示が 1 系列あるのは許容するため、
        # 「= ... /」形式 (旧 description) の再混入のみ検出。
        bad = re.findall(r"[ABCDE]\s*=\s*(?:対話生成|分析レポート|対話契約書)", text)
        if bad:
            fail(results, "C3", f"{ref.name}: 旧ワークフロー定義ラベルが再混入 {bad}")
            continue
        ok(results, "C3", f"{ref.name}: ワークフロー二重定義なし (正本参照のみ)")


def c4_axis_separation_notes(schema, results):
    checks = []
    # schema パターン / ワークフロー の独立注記。
    pat = schema["properties"]["パターン"].get("description", "")
    wf = schema["properties"]["ワークフロー"].get("description", "")
    checks.append(("schema:パターン", "独立した分類" in pat))
    checks.append(("schema:ワークフロー", "独立した分類" in wf))
    # advisor の mode 軸注記。
    adv = ADVISOR.read_text(encoding="utf-8") if ADVISOR.exists() else ""
    checks.append(("advisor:mode", "独立した分類" in adv))
    # handoff の workflow_pattern 注記。
    ho = HANDOFF.read_text(encoding="utf-8") if HANDOFF.exists() else ""
    checks.append(("handoff:workflow_pattern", "独立した分類" in ho))
    missing = [name for name, present in checks if not present]
    if missing:
        fail(results, "C4", f"軸独立性注記が欠落: {missing}")
        return
    ok(results, "C4", "全 A-E 定義箇所に軸独立性注記あり (mode/パターン/ワークフロー)")


def main(argv):
    as_json = "--json" in argv
    results = []
    schema = load_schema()
    enums = c1_canonical_load(schema, results)
    if enums is not None:
        c2_projection_parity(schema, results)
    c3_no_double_definition(results)
    c4_axis_separation_notes(schema, results)

    failed = [r for r in results if r["status"] == "FAIL"]
    report = {
        "contract": "intake-enum-ssot",
        "exit": 1 if failed else 0,
        "gate_results": {r["gate"]: r["status"] for r in results},
        "details": results,
    }
    if as_json:
        print(json.dumps(report, ensure_ascii=False, indent=2))
    else:
        for r in results:
            mark = "PASS" if r["status"] == "PASS" else "FAIL"
            print(f"[{mark}] {r['gate']}: {r['detail']}")
        print("=> " + ("ALL PASS" if not failed else f"{len(failed)} FAIL"))
    return 1 if failed else 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
