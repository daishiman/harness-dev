"""Turn a scenario into a cost report + interactive HTML calculator + JSON.

Usage:
  python simulate.py scenario.json --out-dir out/ \
      [--pricing ../data/pricing.json] \
      [--compare claude-opus-4-8,claude-sonnet-4-6,claude-haiku-4-5,gpt-4o,gemini-2.5-flash]

Outputs in --out-dir:
  cost_report.md     human-readable report
  calculator.html    self-contained interactive calculator (sliders, model compare)
  cost_model.json    machine-readable model (calls, tokens, costs, assumptions)
"""

from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any

import engine

HERE = Path(__file__).resolve().parent
DEFAULT_PRICING = HERE.parent / "data" / "pricing.json"
DEFAULT_TEMPLATE = HERE.parent / "templates" / "calculator.html.template"


def _fmt_usd(x: float) -> str:
    if x == 0:
        return "$0"
    if x < 0.01:
        return f"${x:.6f}".rstrip("0").rstrip(".")
    if x < 1:
        return f"${x:.4f}".rstrip("0").rstrip(".")
    if x < 1000:
        return f"${x:,.2f}"
    return f"${x:,.0f}"


def _fmt_int(x: float) -> str:
    return f"{x:,.0f}"


# --------------------------------------------------------------------------- #
# Markdown report
# --------------------------------------------------------------------------- #
def build_report(
    scenario: dict[str, Any],
    pricing: dict[str, Any],
    flow: dict[str, Any],
    projection: dict[str, Any],
    comparison: list[dict[str, Any]],
    sensitivity: list[dict[str, Any]],
) -> str:
    meta = scenario.get("meta", {})
    L: list[str] = []
    L.append(f"# LLM コスト試算: {meta.get('app_name', 'app')} / {meta.get('flow_name', 'flow')}")
    L.append("")
    L.append(f"- 解析日時: {meta.get('analyzed_at', '-')}")
    L.append(f"- 測定ティア: {meta.get('measurement_tier', '-')}  "
             "(T0=静的推定 / T1=無料exact入力 / T2=Claude実測サンプル / T3=実プロバイダ実測)")
    if meta.get("notes"):
        L.append(f"- 備考: {meta['notes']}")
    L.append("")
    L.append("## 結論 (1 フローあたり)")
    L.append("")
    L.append(f"**1 回の処理コスト: {_fmt_usd(flow['usd_per_flow'])}**")
    tp = flow["tokens_per_flow"]
    L.append("")
    L.append(f"- 入力(full): {_fmt_int(tp['input'])} tok / "
             f"キャッシュ読: {_fmt_int(tp['cache_read'])} tok / "
             f"キャッシュ書: {_fmt_int(tp['cache_write'])} tok / "
             f"出力(+思考): {_fmt_int(tp['output'])} tok")
    L.append(f"- 想定キャッシュヒット率: {flow['cache_hit_rate'] * 100:.0f}%")
    if projection.get("monthly"):
        m = projection["monthly"]
        L.append(f"- 月間 {_fmt_int(m['volume'])} 件想定: "
                 f"**{_fmt_usd(m['usd_per_month'])}/月**  (年 {_fmt_usd(m['usd_per_year'])})")
    L.append("")

    # call inventory
    L.append("## 呼び出し箇所の内訳")
    L.append("")
    L.append("| # | 処理 | モデル | 実行回数 | 入力tok | 出力tok | 反復 | 確度 | $/フロー |")
    L.append("|---|------|--------|---------:|--------:|--------:|-----:|------|---------:|")
    for c in flow["calls"]:
        L.append(
            f"| {c['id']} | {c['label']} | `{c['model']}` | {c['runs_per_flow']:.0f} | "
            f"{_fmt_int(c['tokens']['input'] + c['tokens']['cache_read'] + c['tokens']['cache_write'])} | "
            f"{_fmt_int(c['tokens']['output'])} | {c['iterations']} | {c['confidence']} | "
            f"{_fmt_usd(c['usd_per_flow'])} |"
        )
    L.append(f"| | **合計** | | | | | | | **{_fmt_usd(flow['usd_per_flow'])}** |")
    L.append("")
    for c in flow["calls"]:
        if c.get("source_ref"):
            L.append(f"- `{c['id']}` → {c['source_ref']}")
    L.append("")

    # model comparison
    if comparison:
        L.append("## モデル比較 (同一トークンプロファイルで価格のみ差し替え)")
        L.append("")
        L.append("> 注: 出力トークン長はモデル間で変わるが、ここでは固定して**価格差のみ**を比較。")
        L.append("")
        L.append("| モデル | $/フロー | 最安比 | 確度 |")
        L.append("|--------|---------:|-------:|------|")
        best = next((r["usd_per_flow"] for r in comparison if "usd_per_flow" in r), None)
        for r in comparison:
            if "error" in r:
                L.append(f"| `{r['model']}` | (不明) | - | - |")
                continue
            ratio = (r["usd_per_flow"] / best) if best else 1.0
            L.append(f"| {r['display_name']} (`{r['model']}`) | {_fmt_usd(r['usd_per_flow'])} | "
                     f"{ratio:.2f}x | {r['confidence']} |")
        L.append("")

    # projections
    L.append("## 件数スケール")
    L.append("")
    L.append("| 件数 | コスト |")
    L.append("|-----:|-------:|")
    for row in projection["volume_table"]:
        L.append(f"| {_fmt_int(row['runs'])} | {_fmt_usd(row['usd'])} |")
    L.append("")
    if projection.get("dau_table"):
        L.append("### DAU シナリオ")
        L.append("")
        L.append("| DAU | 1人1日あたりフロー数 | $/日 | $/月 | $/年 |")
        L.append("|----:|--------------------:|-----:|-----:|-----:|")
        for r in projection["dau_table"]:
            L.append(f"| {_fmt_int(r['dau'])} | {r['flows_per_user_per_day']:.1f} | "
                     f"{_fmt_usd(r['usd_per_day'])} | {_fmt_usd(r['usd_per_month'])} | "
                     f"{_fmt_usd(r['usd_per_year'])} |")
        L.append("")

    # sensitivity
    if sensitivity:
        L.append("### キャッシュヒット率の感度")
        L.append("")
        L.append("| ヒット率 | $/フロー | 月間 |")
        L.append("|--------:|---------:|-----:|")
        mv = scenario.get("projection", {}).get("monthly_volume")
        for s in sensitivity:
            month = _fmt_usd(s["usd_per_flow"] * mv) if mv else "-"
            L.append(f"| {s['hit_rate'] * 100:.0f}% | {_fmt_usd(s['usd_per_flow'])} | {month} |")
        L.append("")

    # assumptions
    assums = [a for c in flow["calls"] for a in c.get("assumptions", [])]
    if assums:
        L.append("## 前提・仮定")
        L.append("")
        for a in assums:
            L.append(f"- {a}")
        L.append("")

    # recommendations
    recs = _recommendations(scenario, flow, comparison)
    if recs:
        L.append("## 推奨アクション")
        L.append("")
        for r in recs:
            L.append(f"- {r}")
        L.append("")

    # provenance
    L.append("## 料金の出典")
    L.append("")
    used_models = {c["model"] for c in flow["calls"]} | {
        r["model"] for r in comparison if "error" not in r
    }
    L.append("| モデル | as_of | 確度 | 出典 |")
    L.append("|--------|-------|------|------|")
    for mid in sorted(used_models):
        try:
            m = engine.get_model(pricing, mid)
            L.append(f"| `{mid}` | {m.get('as_of', '-')} | {m.get('confidence', '-')} | "
                     f"{m.get('source', '-')} |")
        except KeyError:
            continue
    L.append("")
    L.append("> `confidence: verify/estimate` のモデルは ROI 判断前に公式料金ページで再確認すること "
             "(data/pricing.json の meta.refresh 参照)。")
    L.append("")
    return "\n".join(L)


def _recommendations(
    scenario: dict[str, Any], flow: dict[str, Any], comparison: list[dict[str, Any]]
) -> list[str]:
    recs: list[str] = []
    # cheaper model
    valid = [r for r in comparison if "usd_per_flow" in r]
    if len(valid) >= 2:
        cheapest = valid[0]
        current_total = flow["usd_per_flow"]
        if cheapest["usd_per_flow"] < current_total * 0.95:
            save = (1 - cheapest["usd_per_flow"] / current_total) * 100 if current_total else 0
            recs.append(
                f"最安候補 `{cheapest['model']}` に切替で約 {save:.0f}% 削減の可能性 "
                f"({_fmt_usd(cheapest['usd_per_flow'])}/フロー)。品質要件を満たすか実測で検証。"
            )
    # caching opportunity
    tp = flow["tokens_per_flow"]
    if tp["cache_read"] == 0 and tp["cache_write"] == 0:
        big_static = any(
            sum(c.get("tokens", {}).get(k, 0) for k in ("system", "tools", "context")) > 1024
            for c in scenario.get("calls", [])
        )
        repeated = any(
            c.get("agent_loop") or float(c.get("runs_per_flow", 1)) > 1
            for c in scenario.get("calls", [])
        )
        if big_static and repeated:
            recs.append(
                "安定プレフィックス(system+tools+context)が大きく繰り返し送信されている。"
                "プロンプトキャッシュ導入で入力コストを最大 ~90% 削減できる可能性。"
            )
    # batch opportunity
    batchable = any(
        not c.get("batch") and ("classif" in c.get("label", "").lower()
                                or "extract" in c.get("label", "").lower()
                                or "summar" in c.get("label", "").lower())
        for c in scenario.get("calls", [])
    )
    if batchable:
        recs.append(
            "非同期で許容できる分類/抽出/要約があれば Batch API で 50% 削減可能。"
        )
    # output-heavy
    if tp["output"] > tp["input"] * 1.5 and tp["output"] > 2000:
        recs.append(
            "出力(+思考)トークンが入力を大きく上回る。max_tokens/effort/思考の抑制、"
            "または出力の短縮(構造化出力・要約指示)でコスト削減余地。"
        )
    return recs


# --------------------------------------------------------------------------- #
# HTML calculator
# --------------------------------------------------------------------------- #
def build_html(
    template: str,
    scenario: dict[str, Any],
    pricing: dict[str, Any],
    flow: dict[str, Any],
    comparison: list[dict[str, Any]],
) -> str:
    payload = {
        "scenario": scenario,
        "pricing": pricing,
        "flow": flow,
        "comparison": comparison,
    }
    blob = json.dumps(payload, ensure_ascii=False)
    # Template carries `const DATA = /*__DATA__*/null;` so the raw template is
    # valid JS on its own; replacing the whole token (incl. the `null` fallback)
    # yields `const DATA = {...};`.
    if "/*__DATA__*/null" in template:
        return template.replace("/*__DATA__*/null", blob)
    return template.replace("/*__DATA__*/", blob)


# --------------------------------------------------------------------------- #
# main
# --------------------------------------------------------------------------- #
def main() -> int:
    ap = argparse.ArgumentParser(description="Simulate LLM cost from a scenario.")
    ap.add_argument("scenario", help="scenario JSON file")
    ap.add_argument("--pricing", default=str(DEFAULT_PRICING))
    ap.add_argument("--template", default=str(DEFAULT_TEMPLATE))
    ap.add_argument("--out-dir", default="llm_cost_out")
    ap.add_argument("--compare", default="", help="comma-separated model ids to compare")
    args = ap.parse_args()

    scenario = json.loads(Path(args.scenario).read_text(encoding="utf-8"))
    pricing = engine.load_pricing(args.pricing)

    flow = engine.cost_for_flow(scenario, pricing)
    projection = engine.project(flow["usd_per_flow"], scenario)

    compare_ids = [m.strip() for m in args.compare.split(",") if m.strip()]
    if not compare_ids:
        compare_ids = scenario.get("compare_models", [])
    comparison = engine.compare_models(scenario, pricing, compare_ids) if compare_ids else []

    sensitivity = []
    for hr in (0.0, 0.5, 0.7, 0.9):
        s = {**scenario, "projection": {**scenario.get("projection", {}), "cache_hit_rate": hr}}
        sensitivity.append({"hit_rate": hr, "usd_per_flow": engine.cost_for_flow(s, pricing)["usd_per_flow"]})

    out = Path(args.out_dir)
    out.mkdir(parents=True, exist_ok=True)

    report = build_report(scenario, pricing, flow, projection, comparison, sensitivity)
    (out / "cost_report.md").write_text(report, encoding="utf-8")

    cost_model = {
        "meta": scenario.get("meta", {}),
        "usd_per_flow": flow["usd_per_flow"],
        "tokens_per_flow": flow["tokens_per_flow"],
        "cache_hit_rate": flow["cache_hit_rate"],
        "calls": flow["calls"],
        "projection": projection,
        "comparison": comparison,
        "sensitivity": sensitivity,
    }
    (out / "cost_model.json").write_text(
        json.dumps(cost_model, indent=2, ensure_ascii=False), encoding="utf-8"
    )

    template_path = Path(args.template)
    if template_path.exists():
        html = build_html(template_path.read_text(encoding="utf-8"), scenario, pricing, flow, comparison)
        (out / "calculator.html").write_text(html, encoding="utf-8")
        html_note = f"  - {out / 'calculator.html'}"
    else:
        html_note = "  - (HTML template not found; skipped calculator.html)"

    print("生成しました:")
    print(f"  - {out / 'cost_report.md'}")
    print(f"  - {out / 'cost_model.json'}")
    print(html_note)
    print()
    print(f"1 フローあたり: {_fmt_usd(flow['usd_per_flow'])}")
    if projection.get("monthly"):
        print(f"月間 {_fmt_int(projection['monthly']['volume'])} 件: "
              f"{_fmt_usd(projection['monthly']['usd_per_month'])}/月")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
