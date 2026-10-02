// 図と表をデータから決定的に組み立てる。analysis.mjs から import して、ソース (.src.html) に埋め込む文字列を作る。
// 座標・ラベル幅・値の位置はここで計算する (手で SVG を書かない)。色はクラスだけ (c-* / s-* / vl-danger)。
//
//   import { figure, hbar, columns, line, table, fmt } from ".../scripts/charts.mjs";
//   figure({ title: "車種別の実車率", legend: "赤=目標未達、破線=目標", svg: hbar({ ... }) })
//
// どの結果にどの図を使うかは references/charts.md。
// 形: hbar=群の比較 / columns=少数の対比 / line=推移 (比較系列・出来事) / multiline=複数系列の推移 / waterfall=増減の分解
//     stacked=構成 / dumbbell=2時点の変化 / butterfly=左右の対比 (人口ピラミッド) / heatmap=2軸の表 / table=項目が多いとき
// 統計: histogram=分布 / boxplot=ばらつきと外れ値 / scatter=2量の関係・4象限 / forest=推定値と区間 / paretoChart=集中 / statStrip=指標カード
// 図解: flow=背景の説明仮説の筋 (背景 → 枝 → 指標)
import { describe, outliersIQR, linreg } from "./stats.mjs";
import { esc, REPORT_DETAILS } from "./lib.mjs";
import { CHART_HOWTO } from "./glossary.mjs";

// esc の正本は lib.mjs。charts.mjs から import している呼び出し元のために再 export する
export { esc };

const W = 760;
const TONES = new Set(["main", "sub", "danger", "ok", "base", "1", "2", "3", "4", "5"]);

/** 数値の表示。桁区切りと小数桁を固定する */
export const fmt = (v, digits = 0) =>
  Number(v).toLocaleString("en-US", { minimumFractionDigits: digits, maximumFractionDigits: digits }).replace(/^-(?=[0.,]*$)/, ""); // 丸めて0なら符号を付けない (-0.0 → 0.0)
/** 表示幅の見積もり (px)。全角 = 1em、半角 = 0.58em。図の文字は --chart-text (14px) */
export const textWidth = (s, size = 14) => [...String(s)].reduce((w, c) => w + (/[\u0000-\u00ff]/.test(c) ? 0.58 : 1) * size, 0);
/** 目盛りの上限を 1・2・2.5・5 × 10^n に丸める */
export function niceMax(v) {
  if (!(v > 0)) return 1;
  const p = 10 ** Math.floor(Math.log10(v));
  return [1, 2, 2.5, 5, 10].map((m) => m * p).find((m) => m >= v);
}
const r1 = (n) => Math.round(n * 10) / 10;
const tone = (t = "main") => {
  if (!TONES.has(String(t))) throw new Error(`tone は ${[...TONES].join(" / ")} のどれか (現在: ${t})`);
  return `c-${t}`;
};
const valueClass = (t) => (t === "danger" ? "vl-danger" : "vl");
// kind = 図の種類。figure() がこれを見て「この図の読み方」(glossary.mjs の CHART_HOWTO) を自動で付ける
const svgOpen = (h, aria, kind) => {
  if (!aria) throw new Error("aria (図の結論を含む説明) は必須です");
  if (!CHART_HOWTO[kind]) throw new Error(`svgOpen: 図の種類 ${kind} の読み方が glossary.mjs の CHART_HOWTO にありません`);
  return `<svg viewBox="0 0 ${W} ${h}" class="chart" role="img" aria-label="${esc(aria)}" data-chart="${kind}">`;
};

/** マイナスを ▲ で書く値の表示 (prompts/analyst.md「C. 解釈」の「書き方」)。plus=true なら増加に + を付ける */
export const sfmt = (v, digits = 0, unit = "", plus = false) => {
  const s = fmt(Math.abs(v), digits), zero = !/[1-9]/.test(s); // 丸めて0なら ▲ も + も付けない
  return `${zero ? "" : v < 0 ? "▲" : plus && v > 0 ? "+" : ""}${s}${unit}`;
};
/** 0 を含む目盛りの範囲 [下限, 上限]。負の値があれば下限も 1・2・2.5・5 × 10^n に丸める */
function span(vals) {
  const lo = Math.min(0, ...vals), hi = Math.max(0, ...vals);
  const top = hi > 0 ? niceMax(hi) : 0, bot = lo < 0 ? -niceMax(-lo) : 0;
  return top === bot ? [0, 1] : [bot, top];
}
/** 負の値の既定の色は danger (赤字・悪化) */
const toneOf = (t, v) => t || (v < 0 ? "danger" : "main");

/**
 * 横棒。items の並び順のまま上から描く (大きい順にしたいなら呼ぶ側で並べ替える)。
 * 負の値 (赤字など) があれば 0 の軸を立て、左へ伸ばして ▲ で表示する。
 * @param {{items: {label: string, value: number, tone?: string, tip?: string, note?: string}[],
 *          unit?: string, digits?: number, aria: string, threshold?: {value: number, label: string}, noteHead?: string}} o
 *   note = 右端に出す副の値 (例: 実車率)。noteHead = その列の見出し
 */
export function hbar({ items, unit = "", digits = 0, aria, threshold, noteHead }) {
  if (!items?.length) throw new Error("hbar: items が空です");
  const rowH = 34, barH = 24, top = noteHead ? 28 : 8;
  const val = (v) => sfmt(v, digits, unit);
  const labelW = Math.min(240, Math.max(...items.map((i) => textWidth(i.label)))) + 16;
  const valW = Math.max(...items.map((i) => textWidth(val(i.value), 13))) + 12;
  const noteW = items.some((i) => i.note != null) ? Math.max(textWidth(noteHead || "", 13), ...items.map((i) => textWidth(i.note ?? "", 13))) + 16 : 0;
  const [lo, hi] = span([...items.map((i) => i.value), threshold?.value ?? 0]);
  // 負の側にも値ラベルの幅を空ける
  const xL = labelW + (lo < 0 ? valW : 0), xR = W - valW - noteW - 8;
  const x = (v) => r1(xL + ((v - lo) / (hi - lo)) * (xR - xL)), zero = x(0);
  const h = top + rowH * items.length + (threshold ? 24 : 4);
  const out = [svgOpen(h, aria, "hbar")];
  if (noteHead) out.push(`  <text x="${W - 4}" y="16" text-anchor="end" class="an">${esc(noteHead)}</text>`);
  if (lo < 0) out.push(`  <line x1="${zero}" y1="${top - 4}" x2="${zero}" y2="${top + rowH * items.length}" class="s-axis"/>`);
  items.forEach((it, i) => {
    const y = top + i * rowH, end = x(it.value), neg = it.value < 0;
    const w = r1(Math.max(2, Math.abs(end - zero)));
    const t = toneOf(it.tone, it.value);
    out.push(
      `  <text x="${labelW - 10}" y="${y + 17}" text-anchor="end" class="lb">${esc(it.label)}</text>`,
      `  <rect x="${neg ? r1(zero - w) : zero}" y="${y}" width="${w}" height="${barH}" rx="3" class="${tone(t)}" data-tip="${esc(it.tip || `${it.label}: ${val(it.value)}`)}"/>`,
      neg
        ? `  <text x="${r1(zero - w - 8)}" y="${y + 17}" text-anchor="end" class="${valueClass(t)}">${esc(val(it.value))}</text>`
        : `  <text x="${r1(zero + w + 8)}" y="${y + 17}" class="${valueClass(t)}">${esc(val(it.value))}</text>`,
    );
    if (it.note != null) out.push(`  <text x="${W - 4}" y="${y + 17}" text-anchor="end" class="vl2">${esc(it.note)}</text>`);
  });
  if (threshold) {
    const tx = x(threshold.value), yEnd = top + rowH * items.length;
    out.push(
      `  <line x1="${tx}" y1="${top - 4}" x2="${tx}" y2="${yEnd}" class="s-threshold"/>`,
      `  <text x="${tx}" y="${yEnd + 16}" text-anchor="middle" class="an">${esc(threshold.label)}</text>`,
    );
  }
  out.push("</svg>");
  return out.join("\n");
}

/**
 * 縦棒の対比。1グループに2〜3本 (例: 前年=sub / 今年=main か danger)。負の値は 0 の軸から下へ伸ばす。
 * @param {{groups: {label: string, bars: {value: number, tone?: string, tip?: string, text?: string}[]}[],
 *          unit?: string, digits?: number, aria: string, threshold?: {value: number, label: string}}} o
 *   text = 棒の上に出す文字 (省略時は値)
 */
export function columns({ groups, unit = "", digits = 0, aria, threshold }) {
  if (!groups?.length) throw new Error("columns: groups が空です");
  const [lo, hi] = span([...groups.flatMap((g) => g.bars.map((b) => b.value)), threshold?.value ?? 0]);
  const top = 30, plotH = 150, left = 40, right = 20, base = top + plotH;
  const y = (v) => r1(top + ((hi - v) / (hi - lo)) * plotH), zero = y(0);
  const gw = (W - left - right) / groups.length;
  const k = Math.max(...groups.map((g) => g.bars.length));
  const bw = Math.min(56, (gw * 0.7 - (k - 1) * 8) / k);
  const out = [svgOpen(base + 44, aria, "columns"), `  <line x1="${left}" y1="${zero}" x2="${W - right}" y2="${zero}" class="s-axis"/>`];
  groups.forEach((g, gi) => {
    const cx = left + gw * (gi + 0.5), span_ = g.bars.length * bw + (g.bars.length - 1) * 8;
    g.bars.forEach((b, bi) => {
      const x = r1(cx - span_ / 2 + bi * (bw + 8)), yv = y(b.value), neg = b.value < 0, t = toneOf(b.tone, b.value);
      const label = b.text ?? sfmt(b.value, digits);
      out.push(
        `  <rect x="${x}" y="${Math.min(yv, zero)}" width="${r1(bw)}" height="${r1(Math.max(1, Math.abs(zero - yv)))}" rx="3" class="${tone(t)}" data-tip="${esc(b.tip || `${g.label}: ${sfmt(b.value, digits, unit)}`)}"/>`,
        `  <text x="${r1(x + bw / 2)}" y="${neg ? r1(yv + 18) : r1(yv - 6)}" text-anchor="middle" class="${t === "sub" ? "vl2" : valueClass(t)}">${esc(label)}</text>`,
      );
    });
    out.push(`  <text x="${r1(cx)}" y="${base + 30}" text-anchor="middle" class="lb">${esc(g.label)}</text>`);
  });
  if (threshold) {
    const ty = y(threshold.value);
    out.push(`  <line x1="${left}" y1="${ty}" x2="${W - right}" y2="${ty}" class="s-threshold"/>`, `  <text x="${W - right}" y="${r1(ty - 6)}" text-anchor="end" class="an">${esc(threshold.label)}</text>`);
  }
  out.push("</svg>");
  return out.join("\n");
}

/**
 * 折れ線 (推移)。値ラベルは点の上。tone=danger の点は赤。
 * compare = 比較の系列 (例: 前年同月)。points と同じ並びの値の配列を淡い線で重ねる (値ラベルは最後の点だけ)。
 * ラベルは文字幅で重なりを判定し、重なるものは出さない。値は 最後→最初→最大→最小→danger→残り の順、横軸は 最後→最初→残り の順に置く。
 * @param {{points: {label: string, value: number, tone?: string, tip?: string}[],
 *          unit?: string, digits?: number, aria: string, baseline?: {value: number, label: string},
 *          compare?: {label: string, values: number[]}, events?: {at: number, label: string}[]}} o
 *   events = 背景の出来事 (制度の施行・衝撃など)。at = points の添字 (小数で点の間も可)。縦の破線と上端のラベルで示す
 */
export function line({ points, unit = "", digits = 0, aria, baseline, compare, events }) {
  if (!points || points.length < 2) throw new Error("line: points は2つ以上必要です");
  if (compare && compare.values?.length !== points.length) throw new Error("line: compare.values は points と同じ個数にしてください");
  const top = events?.length ? 64 : 36, bottom = top + 144, left = 60, right = 60, n = points.length;
  const vals = [...points.map((p) => p.value), ...(baseline ? [baseline.value] : []), ...(compare ? compare.values : [])];
  const lo = Math.min(...vals), hi = Math.max(...vals), pad = (hi - lo || Math.abs(hi) || 1) * 0.15;
  const y = (v) => r1(bottom - ((v - (lo - pad)) / (hi + pad - (lo - pad))) * (bottom - top));
  const x = (i) => r1(left + ((W - left - right) * i) / (n - 1));
  const vs = points.map((p) => p.value), iMax = vs.indexOf(Math.max(...vs)), iMin = vs.indexOf(Math.min(...vs));
  const valueText = (p) => sfmt(p.value, digits);
  // 値ラベル: 近い点どうし (横の間隔が文字幅未満、かつ縦の差が 16px 未満) は後の順位を出さない
  const valuePri = [n - 1, 0, iMax, iMin, ...points.flatMap((p, i) => (p.tone === "danger" ? [i] : [])), ...points.map((_, i) => i)];
  const showValue = place(valuePri, (i) => ({ x: x(i), y: y(vs[i]), w: textWidth(valueText(points[i]), 13) }), 16);
  // 横軸: 同じ高さに並ぶので、横の間隔だけで判定する
  const showLabel = place([n - 1, 0, ...points.map((_, i) => i)], (i) => ({ x: x(i), y: 0, w: textWidth(points[i].label, 13) }), Infinity);
  const out = [svgOpen(bottom + 40, aria, "line"), `  <line x1="${left - 20}" y1="${bottom + 6}" x2="${W - right + 20}" y2="${bottom + 6}" class="s-axis"/>`];
  if (baseline) {
    out.push(`  <line x1="${left - 20}" y1="${y(baseline.value)}" x2="${W - right + 20}" y2="${y(baseline.value)}" class="s-threshold"/>`, `  <text x="${W - 4}" y="${r1(y(baseline.value) + 16)}" text-anchor="end" class="an">${esc(baseline.label)}</text>`);
  }
  if (compare) {
    out.push(`  <polyline points="${compare.values.map((v, i) => `${x(i)},${y(v)}`).join(" ")}" class="s-sub"/>`);
    compare.values.forEach((v, i) => out.push(`  <circle cx="${x(i)}" cy="${y(v)}" r="4" class="c-sub" data-tip="${esc(`${compare.label} ${points[i].label}: ${sfmt(v, digits, unit)}`)}"/>`));
    const last = compare.values.at(-1);
    out.push(`  <text x="${W - right + 8}" y="${r1(y(last) + 4)}" class="vl2">${esc(compare.label)}</text>`);
  }
  out.push(...eventMarks(events, x, top, bottom, n));
  out.push(`  <polyline points="${points.map((p, i) => `${x(i)},${y(p.value)}`).join(" ")}" class="s-main"/>`);
  points.forEach((p, i) => {
    const t = p.tone || "main";
    out.push(`  <circle cx="${x(i)}" cy="${y(p.value)}" r="5" class="${tone(t)}" data-tip="${esc(p.tip || `${p.label}: ${sfmt(p.value, digits, unit)}`)}"/>`);
    if (showValue.has(i)) out.push(`  <text x="${x(i)}" y="${r1(y(p.value) - 12)}" text-anchor="middle" class="${valueClass(t)}">${esc(valueText(p))}</text>`);
    if (showLabel.has(i)) out.push(`  <text x="${x(i)}" y="${bottom + 28}" text-anchor="middle" class="lb">${esc(p.label)}</text>`);
  });
  out.push("</svg>");
  return out.join("\n");
}

/**
 * ラベルを優先順に置き、既に置いたものと重なるものは捨てる。box(i) = {x: 中心, y, w: 幅}。
 * dy 未満の縦の差を「同じ高さ」とみなす (Infinity なら常に横の間隔だけで判定)。戻り値 = 置く添字の Set
 */
function place(order, box, dy) {
  const kept = [];
  for (const i of order) {
    if (kept.some((k) => k.i === i)) continue;
    const b = box(i);
    if (kept.every((k) => Math.abs(k.x - b.x) >= (k.w + b.w) / 2 + 6 || Math.abs(k.y - b.y) >= dy)) kept.push({ i, ...b });
  }
  return new Set(kept.map((k) => k.i));
}

/**
 * ウォーターフォール (増減の分解)。start から各要因の増減を積み、end に着く。横向き。
 * 例: 前月の利益 → 売上 +120 / 燃料費 ▲80 / 修繕費 ▲50 → 今月の利益。end の値は start + 増減の合計 (計算する)。
 * 増加は ok (緑)、減少は danger (赤)、start と end は main。
 * @param {{start: {label: string, value: number}, steps: {label: string, value: number}[], end: {label: string},
 *          unit?: string, digits?: number, aria: string}} o
 */
export function waterfall({ start, steps, end, unit = "", digits = 0, aria }) {
  if (!start || !steps?.length || !end) throw new Error("waterfall: start・steps・end は必須です");
  const rows = [{ label: start.label, from: 0, to: start.value, kind: "total" }];
  let cum = start.value;
  for (const s of steps) rows.push({ label: s.label, from: cum, to: (cum += s.value), kind: s.value < 0 ? "down" : "up", delta: s.value });
  rows.push({ label: end.label, from: 0, to: cum, kind: "total" });
  const rowH = 34, barH = 24, top = 8;
  const text = (r) => (r.kind === "total" ? sfmt(r.to, digits, unit) : sfmt(r.delta, digits, unit, true));
  const labelW = Math.min(240, Math.max(...rows.map((r) => textWidth(r.label)))) + 16;
  const valW = Math.max(...rows.map((r) => textWidth(text(r), 13))) + 12;
  const [lo, hi] = span(rows.flatMap((r) => [r.from, r.to]));
  const xL = labelW + (lo < 0 ? valW : 0), xR = W - valW - 8;
  const x = (v) => r1(xL + ((v - lo) / (hi - lo)) * (xR - xL));
  const out = [svgOpen(top + rowH * rows.length + 4, aria, "waterfall")];
  if (lo < 0) out.push(`  <line x1="${x(0)}" y1="${top - 4}" x2="${x(0)}" y2="${top + rowH * rows.length}" class="s-axis"/>`);
  rows.forEach((r, i) => {
    const yy = top + i * rowH, a = x(Math.min(r.from, r.to)), b = x(Math.max(r.from, r.to)), w = r1(Math.max(2, b - a));
    const t = r.kind === "total" ? "main" : r.kind === "down" ? "danger" : "ok";
    // 値ラベルは棒の外側 (減少は棒の左、それ以外は右) に置く
    const left_ = r.kind === "down" || (r.kind === "total" && r.to < 0);
    out.push(
      `  <text x="${labelW - 10}" y="${yy + 17}" text-anchor="end" class="lb">${esc(r.label)}</text>`,
      `  <rect x="${a}" y="${yy}" width="${w}" height="${barH}" rx="3" class="${tone(t)}" data-tip="${esc(`${r.label}: ${text(r)}`)}"/>`,
      left_
        ? `  <text x="${r1(a - 8)}" y="${yy + 17}" text-anchor="end" class="${valueClass(t)}">${esc(text(r))}</text>`
        : `  <text x="${r1(a + w + 8)}" y="${yy + 17}" class="${valueClass(t)}">${esc(text(r))}</text>`,
    );
    // 次の行へのつなぎ線 (累積の位置)
    if (i < rows.length - 1) out.push(`  <line x1="${x(r.to)}" y1="${yy + barH}" x2="${x(r.to)}" y2="${yy + rowH}" class="s-grid"/>`);
  });
  out.push("</svg>");
  return out.join("\n");
}

/**
 * 図のカード (キットの .card .card-pad)。legend = 凡例 (60字まで)。
 * 図の下に「この図の読み方」(details.howto) を必ず置く。文は svg の data-chart から
 * glossary.mjs の CHART_HOWTO を引いて自動で決まるので、通常は howto を渡さなくてよい。
 * 常時表示ではなく折りたたみにして、読める人の邪魔をしない (JS が無くても開ける)。
 * @param {{title: string, legend?: string, svg: string, howto?: string}} o howto = 既定の読み方を上書きする1文
 */
export function figure({ title, legend, svg, howto }) {
  const kind = (svg.match(/\bdata-chart="([^"]+)"/) || [, ""])[1];
  const text = howto || CHART_HOWTO[kind];
  if (!text) throw new Error(`figure「${title}」: この図の読み方が決まりません (charts.mjs の図を使うか、howto を渡してください)`);
  return (
    `<figure class="card card-pad">\n  <figcaption>${esc(title)}${legend ? `<small>${esc(legend)}</small>` : ""}</figcaption>\n` +
    `  <div class="chartbox">\n${svg}\n  </div>\n${howtoBlock(text)}</figure>`
  );
}

/** 「この図の読み方」の折りたたみ。手書きの図 (雛形) もこれを使う */
export const howtoBlock = (text) =>
  `  <details class="howto">\n    <summary>この図の読み方</summary>\n    <p>${esc(text)}</p>\n  </details>\n`;

/**
 * 表 (キットの .table-scroll .card)。num=true の列は右揃え (td.col-num)。
 * セルは文字列か数値、または {text, cls} (cls = "loss" / "profit" など部品クラス)。数値は digits で整形する。
 * @param {{columns: {label: string, num?: boolean, digits?: number}[], rows: any[][], caption?: string}} o
 */
export function table({ columns: cols, rows, caption }) {
  if (!cols?.length || !rows?.length) throw new Error("table: columns と rows は必須です");
  const cell = (c, v) => {
    const o = v && typeof v === "object" ? v : { text: v };
    const text = typeof o.text === "number" ? fmt(o.text, c.digits ?? 0) : o.text ?? "";
    const cls = [c.num ? "col-num" : "", o.cls || ""].filter(Boolean).join(" ");
    return `<td${cls ? ` class="${cls}"` : ""}>${esc(text)}</td>`;
  };
  return [
    `<div class="table-scroll card">`,
    `  <table>${caption ? `<caption>${esc(caption)}</caption>` : ""}`,
    `    <thead><tr>${cols.map((c) => `<th${c.num ? ' class="col-num"' : ""}>${esc(c.label)}</th>`).join("")}</tr></thead>`,
    `    <tbody>`,
    ...rows.map((r) => `      <tr>${r.map((v, i) => cell(cols[i], v)).join("")}</tr>`),
    `    </tbody>`,
    `  </table>`,
    `</div>`,
  ].join("\n");
}

// ================= 統計の図 (references/statistics.md §2) =================

/**
 * ヒストグラム (分布の形)。bins は階級の境界 (例 [0,20,40,60,80,100])。平均 (赤の破線) と中央値 (薄い実線) の線を引く。
 * highlight(lo, hi) が true の階級は danger で塗る (例: 目標未満の階級)
 */
export function histogram({ values, bins, unit = "", aria, highlight = () => false, digits = 0 }) {
  if (!values?.length || !bins || bins.length < 3) throw new Error("histogram: values と3つ以上の境界 bins が必要です");
  const counts = bins.slice(0, -1).map((lo, i) => values.filter((v) => v >= lo && (i === bins.length - 2 ? v <= bins[i + 1] : v < bins[i + 1])).length);
  // 上 40px は平均・中央値のラベル2段の領域 (棒の件数ラベルと重ねない)
  const base = 200, plotH = 140, left = 40, right = 20;
  const max = niceMax(Math.max(...counts));
  const bw = (W - left - right) / counts.length;
  const xOf = (v) => r1(left + ((v - bins[0]) / (bins.at(-1) - bins[0])) * (W - left - right));
  const d = describe(values);
  const out = [svgOpen(base + 40, aria, "histogram"), `  <line x1="${left}" y1="${base}" x2="${W - right}" y2="${base}" class="s-axis"/>`];
  counts.forEach((c, i) => {
    const x = r1(left + i * bw + 2), h = r1((plotH * c) / max), t = highlight(bins[i], bins[i + 1]) ? "danger" : "main";
    const range = `${fmt(bins[i], digits)}〜${fmt(bins[i + 1], digits)}${unit}`;
    out.push(
      `  <rect x="${x}" y="${r1(base - h)}" width="${r1(bw - 4)}" height="${h}" rx="3" class="${tone(t)}" data-tip="${esc(`${range}: ${c}件`)}"/>`,
      `  <text x="${r1(x + (bw - 4) / 2)}" y="${r1(base - h - 6)}" text-anchor="middle" class="${valueClass(t)}">${c}</text>`,
    );
  });
  bins.forEach((b) => out.push(`  <text x="${xOf(b)}" y="${base + 20}" text-anchor="middle" class="ax">${esc(fmt(b, digits))}</text>`));
  out.push(`  <text x="${W - right}" y="${base + 36}" text-anchor="end" class="an">${esc(unit ? `単位: ${unit}` : "")}</text>`);
  // 2本の線が近いときは、ラベルを互いに外側へ寄せる (左の線は右揃え、右の線は左揃え)
  const near = Math.abs(xOf(d.mean) - xOf(d.median)) < 80, meanLeft = d.mean <= d.median;
  const anchor = (isMean) => (!near ? "middle" : isMean === meanLeft ? "end" : "start");
  for (const [v, label, y, isMean] of [[d.mean, `平均 ${fmt(d.mean, 1)}`, 14, true], [d.median, `中央値 ${fmt(d.median, 1)}`, 30, false]]) {
    const x = xOf(v), a = anchor(isMean), tx = a === "end" ? x - 3 : a === "start" ? x + 3 : x;
    out.push(`  <line x1="${x}" y1="${y + 4}" x2="${x}" y2="${base}" class="${isMean ? "s-threshold" : "s-sub"}"/>`, `  <text x="${tx}" y="${y}" text-anchor="${a}" class="an">${esc(label)}</text>`);
  }
  out.push("</svg>");
  return out.join("\n");
}

/**
 * 箱ひげ図 (群ごとのばらつきと外れ値)。横向き。ひげは 1.5IQR 以内の最小・最大、外の点は外れ値 (danger)。
 * @param {{groups: {label: string, values: number[], names?: string[]}[], unit?: string, digits?: number, aria: string, threshold?: {value: number, label: string}}} o
 *   names = 外れ値の点の data-tip に出す名前 (values と同じ順)
 */
export function boxplot({ groups, unit = "", digits = 1, aria, threshold }) {
  if (!groups?.length) throw new Error("boxplot: groups が空です");
  const rowH = 52, top = 16, labelW = Math.max(...groups.map((g) => textWidth(g.label))) + 20, right = 24;
  const all = groups.flatMap((g) => g.values).concat(threshold ? [threshold.value] : []);
  const lo = Math.min(...all), hi = Math.max(...all), pad = (hi - lo || 1) * 0.05;
  const x = (v) => r1(labelW + ((v - (lo - pad)) / (hi - lo + 2 * pad)) * (W - labelW - right));
  const h = top + rowH * groups.length + 40;
  const out = [svgOpen(h, aria, "boxplot")];
  groups.forEach((g, i) => {
    const d = describe(g.values), o = outliersIQR(g.values);
    const inside = g.values.filter((v) => v >= o.lower && v <= o.upper);
    const wl = Math.min(...inside), wh = Math.max(...inside), cy = top + i * rowH + 18;
    const f = (v) => `${fmt(v, digits)}${unit}`;
    out.push(
      `  <text x="${labelW - 12}" y="${cy + 5}" text-anchor="end" class="lb">${esc(g.label)}</text>`,
      `  <line x1="${x(wl)}" y1="${cy}" x2="${x(wh)}" y2="${cy}" class="s-axis"/>`,
      `  <line x1="${x(wl)}" y1="${cy - 8}" x2="${x(wl)}" y2="${cy + 8}" class="s-axis"/>`,
      `  <line x1="${x(wh)}" y1="${cy - 8}" x2="${x(wh)}" y2="${cy + 8}" class="s-axis"/>`,
      `  <rect x="${x(d.q1)}" y="${cy - 12}" width="${r1(Math.max(2, x(d.q3) - x(d.q1)))}" height="24" rx="3" class="c-sub" data-tip="${esc(`${g.label}: 中央値 ${f(d.median)}・Q1 ${f(d.q1)}・Q3 ${f(d.q3)}・n=${d.n}`)}"/>`,
      `  <line x1="${x(d.median)}" y1="${cy - 12}" x2="${x(d.median)}" y2="${cy + 12}" class="s-main"/>`,
      `  <text x="${x(d.median)}" y="${cy + 28}" text-anchor="middle" class="vl">${esc(fmt(d.median, digits))}</text>`,
    );
    g.values.forEach((v, j) => {
      if (v >= o.lower && v <= o.upper) return;
      out.push(`  <circle cx="${x(v)}" cy="${cy}" r="5" class="c-danger" data-tip="${esc(`${g.names?.[j] ?? g.label} (外れ値): ${f(v)}`)}"/>`);
    });
  });
  const axisY = top + rowH * groups.length + 4;
  out.push(`  <line x1="${labelW}" y1="${axisY}" x2="${W - right}" y2="${axisY}" class="s-axis"/>`);
  const ticks = [lo, (lo + hi) / 2, hi];
  ticks.forEach((t) => out.push(`  <text x="${x(t)}" y="${axisY + 18}" text-anchor="middle" class="ax">${esc(fmt(t, digits))}${esc(unit)}</text>`));
  if (threshold) out.push(`  <line x1="${x(threshold.value)}" y1="${top - 6}" x2="${x(threshold.value)}" y2="${axisY}" class="s-threshold"/>`, `  <text x="${x(threshold.value)}" y="${axisY + 34}" text-anchor="middle" class="an">${esc(threshold.label)}</text>`);
  out.push("</svg>");
  return out.join("\n");
}

/**
 * 散布図 + 回帰直線 (2つの量の関係)。fit=true のときだけ r と R² を右上に出す。相関は因果ではない (凡例か facts で明記する)。
 * @param {{points: {x: number, y: number, label?: string, tone?: string}[], xLabel: string, yLabel: string, aria: string, digits?: number,
 *          fit?: boolean, refs?: {x?: {value: number, label: string}, y?: {value: number, label: string}}}} o
 *   fit=false で回帰直線と r / R² の計算・表示を消す (4象限で分類だけしたいとき)。refs = 4象限の基準線
 */
export function scatter({ points, xLabel, yLabel, aria, digits = 0, fit: showFit = true, refs = {} }) {
  if (!points || points.length < 3) throw new Error("scatter: points は3つ以上必要です");
  const left = 64, right = 24, top = 24, bottom = 200;
  const xs = points.map((p) => p.x), ys = points.map((p) => p.y);
  const pad = (a) => (Math.max(...a) - Math.min(...a) || 1) * 0.06;
  // 余白で負の目盛りを作らない (距離・金額など 0 以上の量)
  const lo = (a) => (Math.min(...a) >= 0 ? Math.max(0, Math.min(...a) - pad(a)) : Math.min(...a) - pad(a));
  const [x0, x1] = [lo(xs), Math.max(...xs) + pad(xs)], [y0, y1] = [lo(ys), Math.max(...ys) + pad(ys)];
  const X = (v) => r1(left + ((v - x0) / (x1 - x0)) * (W - left - right)), Y = (v) => r1(bottom - ((v - y0) / (y1 - y0)) * (bottom - top));
  const fit = showFit ? linreg(xs, ys) : null;
  const out = [
    svgOpen(bottom + 44, aria, "scatter"),
    `  <line x1="${left}" y1="${bottom}" x2="${W - right}" y2="${bottom}" class="s-axis"/>`,
    `  <line x1="${left}" y1="${top}" x2="${left}" y2="${bottom}" class="s-axis"/>`,
  ];
  if (fit) {
    // 回帰直線は描画範囲 (y0〜y1) の中だけ描く
    const at = (v) => fit.intercept + fit.slope * v, xAt = (v) => (v - fit.intercept) / fit.slope;
    const clip = (v) => (fit.slope === 0 ? v : Math.min(x1, Math.max(x0, v)));
    const [la, lb] = fit.slope === 0 ? [x0, x1] : [clip(Math.max(x0, Math.min(xAt(y0), xAt(y1)))), clip(Math.min(x1, Math.max(xAt(y0), xAt(y1))))];
    out.push(`  <line x1="${X(la)}" y1="${Y(at(la))}" x2="${X(lb)}" y2="${Y(at(lb))}" class="s-threshold"/>`);
  }
  // 2軸で4つに分ける基準線 (例: 平均・目標)
  if (refs.x) out.push(`  <line x1="${X(refs.x.value)}" y1="${top}" x2="${X(refs.x.value)}" y2="${bottom}" class="s-dash"/>`, `  <text x="${X(refs.x.value) + 4}" y="${bottom - 6}" class="an">${esc(refs.x.label)}</text>`);
  if (refs.y) out.push(`  <line x1="${left}" y1="${Y(refs.y.value)}" x2="${W - right}" y2="${Y(refs.y.value)}" class="s-dash"/>`, `  <text x="${W - right}" y="${Y(refs.y.value) - 6}" text-anchor="end" class="an">${esc(refs.y.label)}</text>`);
  points.forEach((p) => out.push(`  <circle cx="${X(p.x)}" cy="${Y(p.y)}" r="4.5" class="${tone(p.tone || "main")}" data-tip="${esc(`${p.label ?? ""} ${xLabel} ${fmt(p.x, digits)} / ${yLabel} ${fmt(p.y, digits)}`.trim())}"/>`));
  for (const [v, pos] of [[x0, "start"], [x1, "end"]]) out.push(`  <text x="${X(v)}" y="${bottom + 18}" text-anchor="${pos}" class="ax">${esc(fmt(v, digits))}</text>`);
  for (const v of [y0, y1]) out.push(`  <text x="${left - 8}" y="${Y(v) + 4}" text-anchor="end" class="ax">${esc(fmt(v, digits))}</text>`);
  out.push(
    `  <text x="${(left + W - right) / 2}" y="${bottom + 38}" text-anchor="middle" class="lb">${esc(xLabel)}</text>`,
    `  <text x="${left + 8}" y="${top + 4}" class="lb">${esc(yLabel)}</text>`,
  );
  if (fit) out.push(`  <text x="${W - right}" y="${top + 4}" text-anchor="end" class="an">r=${fit.r.toFixed(2)}・R²=${fit.r2.toFixed(2)}・n=${fit.n}</text>`);
  out.push("</svg>");
  return out.join("\n");
}

/**
 * パレート図 (大きい順の棒 + 累積構成比の折れ線 + 80% 線)。A 区分 (累積80%まで) の棒は danger。
 * items は pareto() の戻り値。labelOf で表示名を取り出す。多いときは top 件だけ描き、残りを「その他」にまとめる
 */
export function paretoChart({ rows, labelOf, valueOf, unit = "", aria, top = 12, digits = 0 }) {
  if (!rows?.length) throw new Error("paretoChart: rows が空です");
  const shown = rows.slice(0, top);
  const rest = rows.slice(top);
  const bars = shown.map((r) => ({ label: labelOf(r.item), value: valueOf(r.item), cum: r.cum, rank: r.rank }));
  if (rest.length) bars.push({ label: `その他${rest.length}件`, value: rest.reduce((s, r) => s + valueOf(r.item), 0), cum: 1, rank: "C" });
  const left = 56, right = 56, top_ = 24, base = 200;
  const max = niceMax(Math.max(...bars.map((b) => b.value)));
  const bw = (W - left - right) / bars.length;
  const yv = (v) => r1(base - ((base - top_) * v) / max), yc = (c) => r1(base - (base - top_) * c);
  const out = [svgOpen(base + 64, aria, "pareto"), `  <line x1="${left}" y1="${base}" x2="${W - right}" y2="${base}" class="s-axis"/>`,
    `  <line x1="${left}" y1="${yc(0.8)}" x2="${W - right}" y2="${yc(0.8)}" class="s-threshold"/>`, `  <text x="${W - 4}" y="${yc(0.8) - 6}" text-anchor="end" class="an">累積80%</text>`];
  bars.forEach((b, i) => {
    const x = r1(left + i * bw + 3), t = b.rank === "A" ? "danger" : b.label.startsWith("その他") ? "base" : "main";
    out.push(
      `  <rect x="${x}" y="${yv(b.value)}" width="${r1(bw - 6)}" height="${r1(base - yv(b.value))}" rx="3" class="${tone(t)}" data-tip="${esc(`${b.label}: ${fmt(b.value, digits)}${unit}（累積 ${fmt(b.cum * 100, 1)}%）`)}"/>`,
      `  <text x="${r1(x + (bw - 6) / 2)}" y="${base + 16}" text-anchor="end" transform="rotate(-35 ${r1(x + (bw - 6) / 2)} ${base + 16})" class="ax">${esc(b.label)}</text>`,
    );
  });
  const pts = bars.map((b, i) => `${r1(left + i * bw + bw / 2)},${yc(b.cum)}`);
  out.push(`  <polyline points="${pts.join(" ")}" class="s-main"/>`);
  bars.forEach((b, i) => out.push(`  <circle cx="${r1(left + i * bw + bw / 2)}" cy="${yc(b.cum)}" r="3.5" class="c-main" data-tip="${esc(`累積 ${fmt(b.cum * 100, 1)}%`)}"/>`));
  out.push(`  <text x="${left - 8}" y="${yv(max) + 4}" text-anchor="end" class="ax">${esc(fmt(max, digits))}</text>`, `  <text x="${W - right + 8}" y="${yc(1) + 4}" class="ax">100%</text>`, "</svg>");
  return out.join("\n");
}

/**
 * 統計指標のカード (要因ごとに1つ)。items は {label, value, sub?} で、value は数字を含む文字列。
 * 例: [{label:"n", value:"22台"}, {label:"中央値", value:"1,480km", sub:"平均 1,564"}, {label:"変動係数", value:"0.42"}]
 */
export function statStrip(items, title = "統計の要約") {
  const max = Math.max(...Object.values(REPORT_DETAILS).map((detail) => detail.statsMax));
  if (!items?.length || items.length > max) throw new Error(`statStrip: 1〜${max}項目にしてください`);
  return (
    `<div class="stats card">\n  <div class="stats-title">${esc(title)}</div>\n  <div class="kpi-strip">\n` +
    items.map((i) => `    <div class="kpi"><div class="kpi-label">${esc(i.label)}</div><div class="kpi-value num">${esc(i.value)}</div>${i.sub ? `<div class="kpi-sub">${esc(i.sub)}</div>` : ""}</div>`).join("\n") +
    `\n  </div>\n</div>`
  );
}

// ================= 追加の形と図解 (references/charts.md) =================

const SERIES = ["1", "2", "3", "4", "5"];
const LINE_TONES = new Set(["main", "sub", "danger", ...SERIES]);

/** 図の上端の凡例 (色の四角 + 名前)。幅を超えたら折り返す。戻り値 = { out, h } */
function legend(items, x0, y0 = 16) {
  const out = [];
  let x = x0, y = y0;
  for (const it of items) {
    const w = 18 + textWidth(it.label) + 20;
    if (x + w > W && x > x0) (x = x0), (y += 22);
    out.push(`  <rect x="${r1(x)}" y="${y - 11}" width="12" height="12" rx="2" class="${tone(it.t)}"/>`, `  <text x="${r1(x + 18)}" y="${y}" class="lb">${esc(it.label)}</text>`);
    x += w;
  }
  return { out, h: y + 14 };
}

/** 出来事の縦の破線と、上端に2段で交互に置くラベル。at = 点の添字 (小数可) */
function eventMarks(events = [], x, top, bottom, n) {
  return events.flatMap((e, k) => {
    if (!(e.at >= 0 && e.at <= n - 1)) throw new Error(`events: at は 0〜${n - 1} (「${e.label}」: ${e.at})`);
    const ex = x(e.at), ty = 14 + (k % 2) * 18, a = ex < 140 ? "start" : ex > W - 140 ? "end" : "middle";
    return [`  <line x1="${ex}" y1="${ty + 6}" x2="${ex}" y2="${bottom + 6}" class="s-dash"/>`, `  <text x="${ex}" y="${ty}" text-anchor="${a}" class="an">${esc(e.label)}</text>`];
  });
}

/** 縦に並ぶラベルが重ならないよう、上から順に最小の間隔 gap まで押し下げる。ys = 希望の y。戻り値 = 置く y */
function spread(ys, gap = 16) {
  const order = ys.map((y, i) => [y, i]).sort((a, b) => a[0] - b[0]), out = [];
  let last = -Infinity;
  for (const [y, i] of order) out[i] = last = Math.max(y, last + gap);
  return out;
}

/** 文字幅で折り返す (最大 max 行。超えたら例外 = 文言を短くする) */
function wrap(text, width, max = 3) {
  const lines = [""];
  for (const c of String(text)) {
    if (textWidth(lines.at(-1) + c) > width) lines.push("");
    lines[lines.length - 1] += c;
  }
  if (lines.length > max) throw new Error(`「${text}」が長すぎます (${max}行まで)`);
  return lines;
}

/**
 * 積み上げ横棒 (構成)。percent=true で各行を 100% にそろえ、構成比だけを比べる。
 * @param {{rows: {label: string, parts: number[]}[], series: string[], unit?: string, digits?: number, aria: string, percent?: boolean}} o
 *   parts = series と同じ並びの 0 以上の値。series は5つまで (色 c-1〜c-5)
 */
export function stacked({ rows, series, unit = "", digits = 0, aria, percent = false }) {
  if (!rows?.length || !series?.length || series.length > 5) throw new Error("stacked: rows と1〜5個の series が必要です");
  for (const r of rows) if (r.parts?.length !== series.length || r.parts.some((v) => !(v >= 0))) throw new Error(`stacked: 「${r.label}」の parts は series と同じ個数の0以上の値`);
  const tot = rows.map((r) => r.parts.reduce((a, b) => a + b, 0));
  const val = (v) => (percent ? `${fmt(v, digits)}%` : sfmt(v, digits, unit));
  const labelW = Math.min(240, Math.max(...rows.map((r) => textWidth(r.label)))) + 16;
  const totW = percent ? 0 : Math.max(...tot.map((t) => textWidth(val(t), 13))) + 12;
  const lg = legend(series.map((label, i) => ({ label, t: SERIES[i] })), labelW);
  const rowH = 34, top = lg.h + 8, max = percent ? 100 : niceMax(Math.max(...tot)), xR = W - totW - 8;
  const x = (v) => r1(labelW + (v / max) * (xR - labelW));
  const out = [svgOpen(top + rowH * rows.length, aria, "stacked"), ...lg.out];
  rows.forEach((r, i) => {
    const y = top + i * rowH;
    let acc = 0;
    out.push(`  <text x="${labelW - 10}" y="${y + 17}" text-anchor="end" class="lb">${esc(r.label)}</text>`);
    r.parts.forEach((p, j) => {
      const v = percent ? (tot[i] ? (p / tot[i]) * 100 : 0) : p, a = x(acc), w = r1(x((acc += v)) - a);
      out.push(`  <rect x="${a}" y="${y}" width="${w}" height="24" class="${tone(SERIES[j])}" data-tip="${esc(`${r.label}・${series[j]}: ${val(v)}${percent ? `（${sfmt(p, digits, unit)}）` : ""}`)}"/>`);
      if (w >= textWidth(val(v), 13) + 8) out.push(`  <text x="${r1(a + w / 2)}" y="${y + 17}" text-anchor="middle" class="vl-inv">${esc(val(v))}</text>`);
    });
    if (!percent) out.push(`  <text x="${r1(x(tot[i]) + 8)}" y="${y + 17}" class="vl">${esc(val(tot[i]))}</text>`);
  });
  out.push("</svg>");
  return out.join("\n");
}

/**
 * ダンベル (項目ごとの2時点の変化)。前 = c-sub、後 = main (悪化の向きなら danger)。後の値と変化を後の点の外側に書く。
 * @param {{items: {label: string, from: number, to: number}[], fromLabel: string, toLabel: string,
 *          unit?: string, digits?: number, aria: string, bad?: "down"|"up"}} o  bad = 悪化の向き (既定は減少)
 */
export function dumbbell({ items, fromLabel, toLabel, unit = "", digits = 0, aria, bad = "down" }) {
  if (!items?.length) throw new Error("dumbbell: items が空です");
  const text = (i) => `${sfmt(i.to, digits)}（${sfmt(i.to - i.from, digits, "", true)}）`;
  const labelW = Math.min(240, Math.max(...items.map((i) => textWidth(i.label)))) + 16;
  const valW = Math.max(...items.map((i) => textWidth(text(i), 13))) + 12;
  const lg = legend([{ label: fromLabel, t: "sub" }, { label: toLabel, t: "main" }], labelW);
  const vals = items.flatMap((i) => [i.from, i.to]), lo = Math.min(...vals), hi = Math.max(...vals);
  const xL = labelW + valW, xR = W - valW - 8, x = (v) => r1(xL + ((v - lo) / (hi - lo || 1)) * (xR - xL));
  const rowH = 34, top = lg.h + 8, out = [svgOpen(top + rowH * items.length + 18, aria, "dumbbell"), ...lg.out];
  items.forEach((it, k) => {
    const cy = top + k * rowH + 12, worse = bad === "up" ? it.to > it.from : it.to < it.from, t = worse ? "danger" : "main", right = it.to >= it.from;
    out.push(
      `  <text x="${labelW - 10}" y="${cy + 5}" text-anchor="end" class="lb">${esc(it.label)}</text>`,
      `  <line x1="${x(it.from)}" y1="${cy}" x2="${x(it.to)}" y2="${cy}" class="s-sub"/>`,
      `  <circle cx="${x(it.from)}" cy="${cy}" r="6" class="c-sub" data-tip="${esc(`${it.label} ${fromLabel}: ${sfmt(it.from, digits, unit)}`)}"/>`,
      `  <circle cx="${x(it.to)}" cy="${cy}" r="7" class="${tone(t)}" data-tip="${esc(`${it.label} ${toLabel}: ${sfmt(it.to, digits, unit)}`)}"/>`,
      `  <text x="${right ? x(it.to) + 12 : x(it.to) - 12}" y="${cy + 5}" text-anchor="${right ? "start" : "end"}" class="${valueClass(t)}">${esc(text(it))}</text>`,
    );
  });
  const ay = top + rowH * items.length + 12;
  out.push(`  <text x="${xL}" y="${ay}" class="ax">${esc(sfmt(lo, digits, unit))}</text>`, `  <text x="${xR}" y="${ay}" text-anchor="end" class="ax">${esc(sfmt(hi, digits, unit))}</text>`, "</svg>");
  return out.join("\n");
}

/**
 * 区間の図 (推定値と 95% 区間を項目ごとに並べる。フォレストプロット)。区間が ref をまたぐ項目は sub (差があるとは言えない)。
 * @param {{items: {label: string, est: number, lo: number, hi: number, tone?: string}[], unit?: string, digits?: number, aria: string,
 *          ref?: {value: number, label: string}}} o  ref = 比べる基準 (既定は 0 = 差なし)
 */
export function forest({ items, unit = "", digits = 1, aria, ref = { value: 0, label: "差なし" } }) {
  if (!items?.length) throw new Error("forest: items が空です");
  for (const i of items) if (!(i.lo <= i.est && i.est <= i.hi)) throw new Error(`forest: 「${i.label}」は lo ≤ est ≤ hi にする`);
  const text = (i) => `${sfmt(i.est, digits)} [${sfmt(i.lo, digits)}, ${sfmt(i.hi, digits)}]`;
  const labelW = Math.min(240, Math.max(...items.map((i) => textWidth(i.label)))) + 16;
  const valW = Math.max(...items.map((i) => textWidth(text(i), 13))) + 16;
  const vals = [...items.flatMap((i) => [i.lo, i.hi]), ref.value], lo = Math.min(...vals), hi = Math.max(...vals), pad = (hi - lo || 1) * 0.05;
  const xR = W - valW, x = (v) => r1(labelW + ((v - lo + pad) / (hi - lo + 2 * pad)) * (xR - labelW));
  const rowH = 34, top = 8, bottom = top + rowH * items.length;
  const out = [svgOpen(bottom + 24, aria, "forest"), `  <line x1="${x(ref.value)}" y1="${top - 4}" x2="${x(ref.value)}" y2="${bottom}" class="s-threshold"/>`, `  <text x="${x(ref.value)}" y="${bottom + 16}" text-anchor="middle" class="an">${esc(ref.label)}</text>`];
  items.forEach((it, k) => {
    const cy = top + k * rowH + 12, t = it.tone || (it.lo <= ref.value && ref.value <= it.hi ? "sub" : "main");
    out.push(
      `  <text x="${labelW - 10}" y="${cy + 5}" text-anchor="end" class="lb">${esc(it.label)}</text>`,
      `  <line x1="${x(it.lo)}" y1="${cy}" x2="${x(it.hi)}" y2="${cy}" class="${t === "danger" ? "s-danger" : t === "sub" ? "s-sub" : "s-main"}"/>`,
      `  <circle cx="${x(it.est)}" cy="${cy}" r="6" class="${tone(t)}" data-tip="${esc(`${it.label}: ${text(it)}${unit}`)}"/>`,
      `  <text x="${W - 4}" y="${cy + 5}" text-anchor="end" class="${t === "sub" ? "vl2" : valueClass(t)}">${esc(text(it))}</text>`,
    );
  });
  out.push("</svg>");
  return out.join("\n");
}

/**
 * 複数系列の推移 (5系列まで)。系列名と最後の値を右端に直接書く (凡例を使わない)。events は line と同じ。
 * @param {{labels: string[], series: {label: string, values: number[], tone?: string}[], unit?: string, digits?: number, aria: string,
 *          baseline?: {value: number, label: string}, events?: {at: number, label: string}[]}} o  tone = main・sub・danger・1〜5
 */
export function multiline({ labels, series, unit = "", digits = 0, aria, baseline, events }) {
  if (!labels || labels.length < 2) throw new Error("multiline: labels は2つ以上必要です");
  if (!series?.length || series.length > 5) throw new Error("multiline: series は1〜5個");
  const n = labels.length;
  series.forEach((s, i) => {
    if (s.values?.length !== n) throw new Error(`multiline: 「${s.label}」の values は labels と同じ個数`);
    s.t = s.tone || SERIES[i];
    if (!LINE_TONES.has(s.t)) throw new Error(`multiline: tone は ${[...LINE_TONES].join(" / ")} のどれか`);
  });
  const endText = (s) => `${s.label} ${sfmt(s.values.at(-1), digits)}`;
  const top = events?.length ? 64 : 24, bottom = top + 156, left = 40, right = Math.max(...series.map((s) => textWidth(endText(s), 13))) + 20;
  const vals = [...series.flatMap((s) => s.values), ...(baseline ? [baseline.value] : [])];
  const lo = Math.min(...vals), hi = Math.max(...vals), pad = (hi - lo || Math.abs(hi) || 1) * 0.08;
  const y = (v) => r1(bottom - ((v - lo + pad) / (hi - lo + 2 * pad)) * (bottom - top));
  const x = (i) => r1(left + ((W - left - right) * i) / (n - 1));
  const out = [svgOpen(bottom + 40, aria, "multiline"), `  <line x1="${left - 20}" y1="${bottom + 6}" x2="${W - right + 4}" y2="${bottom + 6}" class="s-axis"/>`];
  if (baseline) out.push(`  <line x1="${left - 20}" y1="${y(baseline.value)}" x2="${W - right + 4}" y2="${y(baseline.value)}" class="s-threshold"/>`, `  <text x="${left - 20}" y="${r1(y(baseline.value) - 6)}" class="an">${esc(baseline.label)}</text>`);
  out.push(...eventMarks(events, x, top, bottom, n));
  const endY = spread(series.map((s) => y(s.values.at(-1)) + 4));
  series.forEach((s, k) => {
    const c = s.t === "danger" ? "s-danger" : `s-${s.t}`;
    out.push(`  <polyline points="${s.values.map((v, i) => `${x(i)},${y(v)}`).join(" ")}" class="${c}"/>`);
    s.values.forEach((v, i) => out.push(`  <circle cx="${x(i)}" cy="${y(v)}" r="3.5" class="${tone(s.t)}" data-tip="${esc(`${s.label} ${labels[i]}: ${sfmt(v, digits, unit)}`)}"/>`));
    out.push(`  <text x="${W - right + 10}" y="${endY[k]}" class="${s.t === "danger" ? "vl-danger" : "vl"}">${esc(endText(s))}</text>`);
  });
  const show = place([n - 1, 0, ...labels.map((_, i) => i)], (i) => ({ x: x(i), y: 0, w: textWidth(labels[i], 13) }), Infinity);
  labels.forEach((l, i) => show.has(i) && out.push(`  <text x="${x(i)}" y="${bottom + 28}" text-anchor="middle" class="lb">${esc(l)}</text>`));
  out.push("</svg>");
  return out.join("\n");
}

/**
 * 左右対比の横棒 (人口ピラミッド・男女・流入と流出など)。項目名を中央に置き、左右へ伸ばす。
 * @param {{items: {label: string, left: number, right: number}[], leftLabel: string, rightLabel: string,
 *          unit?: string, digits?: number, aria: string}} o
 */
export function butterfly({ items, leftLabel, rightLabel, unit = "", digits = 0, aria }) {
  if (!items?.length) throw new Error("butterfly: items が空です");
  if (items.some((i) => !(i.left >= 0 && i.right >= 0))) throw new Error("butterfly: left と right は0以上の値");
  const val = (v) => fmt(v, digits);
  const labelW = Math.max(...items.map((i) => textWidth(i.label, 13))) + 20;
  const valW = Math.max(...items.flatMap((i) => [textWidth(val(i.left), 13), textWidth(val(i.right), 13)])) + 10;
  const mid = W / 2, half = mid - labelW / 2 - valW - 4, max = niceMax(Math.max(...items.flatMap((i) => [i.left, i.right])));
  const len = (v) => r1((v / max) * half), rowH = items.length > 12 ? 20 : 30, barH = rowH - 6, top = 30;
  const out = [svgOpen(top + rowH * items.length + 22, aria, "butterfly"),
    `  <text x="${r1(mid - labelW / 2 - 4)}" y="16" text-anchor="end" class="an">${esc(leftLabel)}</text>`,
    `  <text x="${r1(mid + labelW / 2 + 4)}" y="16" class="an">${esc(rightLabel)}</text>`];
  items.forEach((it, k) => {
    const yy = top + k * rowH, ty = yy + barH / 2 + 5, lx = mid - labelW / 2, rx = mid + labelW / 2;
    out.push(
      `  <rect x="${r1(lx - len(it.left))}" y="${yy}" width="${Math.max(1, len(it.left))}" height="${barH}" rx="2" class="c-1" data-tip="${esc(`${it.label} ${leftLabel}: ${val(it.left)}${unit}`)}"/>`,
      `  <rect x="${r1(rx)}" y="${yy}" width="${Math.max(1, len(it.right))}" height="${barH}" rx="2" class="c-2" data-tip="${esc(`${it.label} ${rightLabel}: ${val(it.right)}${unit}`)}"/>`,
      `  <text x="${mid}" y="${ty}" text-anchor="middle" class="ax">${esc(it.label)}</text>`,
      `  <text x="${r1(lx - len(it.left) - 6)}" y="${ty}" text-anchor="end" class="vl2">${esc(val(it.left))}</text>`,
      `  <text x="${r1(rx + len(it.right) + 6)}" y="${ty}" class="vl2">${esc(val(it.right))}</text>`,
    );
  });
  out.push(`  <text x="${W - 4}" y="${top + rowH * items.length + 16}" text-anchor="end" class="an">${esc(unit ? `単位: ${unit}` : "")}</text>`, "</svg>");
  return out.join("\n");
}

/**
 * ヒートマップ (行 × 列の2軸。例: 年 × 年齢層、曜日 × 時間帯)。濃さ = 絶対値の大きさを5段階。負の値は赤の系統。
 * @param {{rows: string[], cols: string[], values: number[][], unit?: string, digits?: number, aria: string}} o  values[行][列]
 */
export function heatmap({ rows, cols, values, unit = "", digits = 0, aria }) {
  if (!rows?.length || !cols?.length || values?.length !== rows.length || values.some((r) => r.length !== cols.length)) throw new Error("heatmap: values は rows × cols の2次元配列");
  const labelW = Math.min(200, Math.max(...rows.map((r) => textWidth(r)))) + 14, cw = (W - labelW - 4) / cols.length, ch = 30, top = 26;
  const max = Math.max(...values.flat().map(Math.abs)) || 1, lv = (v) => Math.min(4, Math.ceil((Math.abs(v) / max) * 4));
  const out = [svgOpen(top + ch * rows.length + 26, aria, "heatmap")];
  const show = place(cols.map((_, j) => j), (j) => ({ x: labelW + cw * (j + 0.5), y: 0, w: textWidth(cols[j], 13) }), Infinity);
  cols.forEach((c, j) => show.has(j) && out.push(`  <text x="${r1(labelW + cw * (j + 0.5))}" y="16" text-anchor="middle" class="ax">${esc(c)}</text>`));
  rows.forEach((r, i) => {
    const yy = top + i * ch;
    out.push(`  <text x="${labelW - 10}" y="${yy + 20}" text-anchor="end" class="lb">${esc(r)}</text>`);
    values[i].forEach((v, j) => {
      const l = lv(v), cx = labelW + cw * j, s = sfmt(v, digits);
      out.push(`  <rect x="${r1(cx + 1)}" y="${yy + 1}" width="${r1(cw - 2)}" height="${ch - 2}" class="${v < 0 ? `h-n${l}` : `h-${l}`}" data-tip="${esc(`${r}・${cols[j]}: ${sfmt(v, digits, unit)}`)}"/>`);
      if (cw >= textWidth(s, 12) + 6) out.push(`  <text x="${r1(cx + cw / 2)}" y="${yy + 20}" text-anchor="middle" class="${l >= 3 ? "vl-inv" : "vl2"}">${esc(s)}</text>`);
    });
  });
  out.push(`  <text x="${W - 4}" y="${top + ch * rows.length + 18}" text-anchor="end" class="an">${esc(`濃いほど大きい（最大 ${sfmt(max, digits, unit)}）`)}</text>`, "</svg>");
  return out.join("\n");
}

/**
 * 背景の説明仮説の筋 (背景 → 枝 → 指標)。col (0 = 左) ごとに上から並べ、edges は左の列から右の列へ矢印で結ぶ。
 * 箱の tone: main = 焦点の筋 / danger = 悪化 / 省略 = 中立。edge は未検証の説明仮説として破線が既定。
 * 実線は solid="identity" | "definition" | "mechanically-verified" で、恒等式・定義・機械的に検証済みのつながりだけを明示する。dashed は既存呼出しとの互換用。
 * @param {{nodes: {id: string, label: string, col: number, sub?: string, tone?: "main"|"danger"}[],
 *          edges: {from: string, to: string, label?: string, dashed?: boolean, solid?: "identity"|"definition"|"mechanically-verified"}[], aria: string}} o  sub = 箱の2行目 (数字)
 */
export function flow({ nodes, edges = [], aria }) {
  if (!nodes?.length) throw new Error("flow: nodes が空です");
  const byId = new Map(nodes.map((n) => [n.id, n])), ncol = Math.max(...nodes.map((n) => n.col)) + 1;
  for (const e of edges) {
    const a = byId.get(e.from), b = byId.get(e.to);
    if (!a || !b) throw new Error(`flow: edge ${e.from} → ${e.to} の箱がありません`);
    if (a.col >= b.col) throw new Error(`flow: edge ${e.from} → ${e.to} は左の列から右の列へ結ぶ`);
    if (e.solid != null && !["identity", "definition", "mechanically-verified"].includes(e.solid)) throw new Error(`flow: edge ${e.from} → ${e.to} の solid は identity / definition / mechanically-verified のどれか`);
  }
  const gapX = 56, boxW = (W - gapX * (ncol - 1)) / ncol, gapY = 16;
  const box = new Map();
  const heights = [];
  for (let c = 0; c < ncol; c++) {
    let yy = 0;
    for (const n of nodes.filter((n) => n.col === c)) {
      const lines = wrap(n.label, boxW - 20), h = 16 + lines.length * 20 + (n.sub ? 22 : 0);
      box.set(n.id, { x: r1(c * (boxW + gapX)), y: yy, h, lines });
      yy += h + gapY;
    }
    heights[c] = yy - gapY;
  }
  const H = Math.max(...heights);
  for (const n of nodes) box.get(n.id).y = r1(box.get(n.id).y + (H - heights[n.col]) / 2); // 列を縦の中央にそろえる
  const out = [svgOpen(H + 8, aria, "flow")];
  for (const e of edges) {
    const a = box.get(e.from), b = box.get(e.to), x1 = r1(a.x + boxW), y1 = r1(a.y + a.h / 2), x2 = r1(b.x - 8), y2 = r1(b.y + b.h / 2), mx = r1((x1 + x2) / 2);
    out.push(`  <path d="M${x1} ${y1} C${mx} ${y1} ${mx} ${y2} ${x2} ${y2}" class="${e.solid ? "s-sub" : "s-dash"}"/>`, `  <polygon points="${x2},${y2 - 5} ${x2 + 8},${y2} ${x2},${y2 + 5}" class="c-axis"/>`);
    if (e.label) out.push(`  <text x="${mx}" y="${r1((y1 + y2) / 2 - 6)}" text-anchor="middle" class="an">${esc(e.label)}</text>`);
  }
  for (const n of nodes) {
    const b = box.get(n.id), cls = n.tone === "main" ? "n-main" : n.tone === "danger" ? "n-danger" : "n-box";
    out.push(`  <rect x="${b.x}" y="${b.y}" width="${r1(boxW)}" height="${b.h}" rx="8" class="${cls}" data-tip="${esc(`${n.label}${n.sub ? `: ${n.sub}` : ""}`)}"/>`);
    b.lines.forEach((l, i) => out.push(`  <text x="${b.x + 10}" y="${b.y + 26 + i * 20}" class="lb">${esc(l)}</text>`));
    if (n.sub) out.push(`  <text x="${b.x + 10}" y="${b.y + 26 + b.lines.length * 20 + 2}" class="${n.tone === "danger" ? "vl-danger" : "vl"}">${esc(n.sub)}</text>`);
  }
  out.push("</svg>");
  return out.join("\n");
}
