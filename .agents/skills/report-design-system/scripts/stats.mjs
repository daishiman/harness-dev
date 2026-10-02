// レポート用の統計計算。analysis.mjs から import する。外部ライブラリなし・決定的 (乱数なし)。
// 使い分けは references/statistics.md。ここは計算だけで、解釈の文は analysis.mjs 側で書く。
//
//   describe(xs)            n・合計・平均・中央値・標準偏差・変動係数・四分位・範囲
//   quantile(xs, p)         分位点 (線形補間。Excel の PERCENTILE.INC と同じ)
//   outliersIQR(items, key) 箱ひげの外れ値 (Q1−1.5IQR 未満 / Q3+1.5IQR 超)
//   pareto(items, key)      大きい順・累積構成比・ABC 区分 (A=累積80%まで / B=95%まで / C=残り)
//   pearson / spearman      相関係数
//   linreg(xs, ys)          単回帰 (傾き・切片・決定係数 R²)
//   meanCI(xs, level)       平均の信頼区間 (t 分布)。対応のある比較は差の配列に使う
//   welch(xs, ys)           2群の平均の差 (Welch の t 検定の p 値・Cohen の d・差の信頼区間)
//   mannWhitney(xs, ys)     2群の順位の差 (外れ値・歪みに強い。p 値・効果量 r = 順位双列相関)
//   rateCI(k, n, level)     比率の信頼区間 (Wilson)
//   chisq(table)            分割表の独立性 (カイ二乗検定の p 値・効果量 Cramér の V)。比率の群間比較にも使う
//   holm(ps)                多重比較の補正 (Holm 法の調整 p 値)
//
// 差を要因に割り切る (どれも要因の合計 = 全体の差 になる)
//   bridge(items)           足し算の指標 (A = B − C …) の増減を項目ごとに。waterfall の steps にそのまま渡せる
//   driverTree(base, cur)   掛け算の指標 (A = B × C …。数量 × 単価も) の差を各要素の寄与に割る (LMDI)

const sum = (xs) => xs.reduce((s, x) => s + x, 0);
const mean = (xs) => sum(xs) / xs.length;
const sorted = (xs) => [...xs].sort((a, b) => a - b);
const isConstant = (xs) => xs.every((x) => x === xs[0]);
const need = (xs, n, name) => {
  if (!Array.isArray(xs) || xs.length < n || xs.some((x) => typeof x !== "number" || !Number.isFinite(x))) {
    throw new Error(`${name}: 有限の数値が ${n} 件以上必要です`);
  }
};
const needPaired = (xs, ys, n, name) => {
  need(xs, n, name);
  need(ys, n, name);
  if (xs.length !== ys.length) throw new Error(`${name}: 2つの配列は同じ件数にしてください`);
};

export function quantile(xs, p) {
  need(xs, 1, "quantile");
  const s = sorted(xs), h = (s.length - 1) * p, lo = Math.floor(h);
  return s[lo] + (s[Math.min(lo + 1, s.length - 1)] - s[lo]) * (h - lo);
}

/** 標本の要約。sd は不偏標準偏差 (n−1)。cv = sd / mean (平均が0なら null) */
export function describe(xs) {
  need(xs, 1, "describe");
  let total = 0, min = Infinity, max = -Infinity;
  for (const x of xs) {
    total += x;
    if (x < min) min = x;
    if (x > max) max = x;
  }
  const n = xs.length, m = total / n;
  const sd = n > 1 ? Math.sqrt(sum(xs.map((x) => (x - m) ** 2)) / (n - 1)) : 0;
  const q1 = quantile(xs, 0.25), q3 = quantile(xs, 0.75);
  return { n, sum: total, mean: m, median: quantile(xs, 0.5), sd, cv: m ? sd / m : null, min, max, q1, q3, iqr: q3 - q1 };
}

/** 箱ひげの外れ値。items は数値か {…, [key]: 数値} の配列 */
export function outliersIQR(items, key) {
  const val = (it) => (key ? it[key] : it);
  const d = describe(items.map(val));
  const lower = d.q1 - 1.5 * d.iqr, upper = d.q3 + 1.5 * d.iqr;
  return { lower, upper, low: items.filter((it) => val(it) < lower), high: items.filter((it) => val(it) > upper) };
}

/** パレート分析。share / cum は 0〜1。全て0なら集中なし (share=0, cum=0, rank=C) */
export function pareto(items, key) {
  const values = Array.isArray(items) ? items.map((it) => it?.[key]) : items;
  need(values, 1, "pareto");
  if (values.some((value) => value < 0)) throw new Error("pareto: 値は0以上にしてください");
  const total = sum(values);
  if (!Number.isFinite(total)) throw new Error("pareto: 合計は有限の数値にしてください");
  if (total === 0) return items.map((item, i) => ({ item, rank: "C", share: 0, cum: 0, order: i + 1 }));
  let cum = 0;
  return [...items]
    .sort((a, b) => b[key] - a[key])
    .map((it, i) => {
      const before = cum;
      cum += it[key] / total;
      // 累積が 80% に達するまでの項目 (達した項目を含む) を A とする
      const rank = before < 0.8 ? "A" : before < 0.95 ? "B" : "C";
      return { item: it, rank, share: it[key] / total, cum, order: i + 1 };
    });
}

export function pearson(xs, ys) {
  needPaired(xs, ys, 3, "pearson");
  if (isConstant(xs) || isConstant(ys)) throw new Error("pearson: x または y の分散が0のため相関係数を計算できません");
  const mx = mean(xs), my = mean(ys);
  const sxy = sum(xs.map((x, i) => (x - mx) * (ys[i] - my)));
  const sxx = sum(xs.map((x) => (x - mx) ** 2)), syy = sum(ys.map((y) => (y - my) ** 2));
  if (sxx === 0 || syy === 0) throw new Error("pearson: x または y の分散が0のため相関係数を計算できません");
  return sxy / Math.sqrt(sxx * syy);
}

const ranks = (xs) => {
  const idx = xs.map((x, i) => [x, i]).sort((a, b) => a[0] - b[0]);
  const r = new Array(xs.length);
  for (let i = 0; i < idx.length; ) {
    let j = i;
    while (j + 1 < idx.length && idx[j + 1][0] === idx[i][0]) j++;
    for (let k = i; k <= j; k++) r[idx[k][1]] = (i + j) / 2 + 1; // 同順位は平均順位
    i = j + 1;
  }
  return r;
};
export const spearman = (xs, ys) => {
  needPaired(xs, ys, 3, "spearman");
  return pearson(ranks(xs), ranks(ys));
};

/** 単回帰 y = a + b x。r2 = 決定係数 */
export function linreg(xs, ys) {
  needPaired(xs, ys, 3, "linreg");
  if (isConstant(xs) || isConstant(ys)) throw new Error("linreg: x または y の分散が0のため回帰を計算できません");
  const mx = mean(xs), my = mean(ys);
  const sxx = sum(xs.map((x) => (x - mx) ** 2));
  if (sxx === 0) throw new Error("linreg: x または y の分散が0のため回帰を計算できません");
  const slope = sum(xs.map((x, i) => (x - mx) * (ys[i] - my))) / sxx;
  const r = pearson(xs, ys);
  return { slope, intercept: my - slope * mx, r, r2: r * r, n: xs.length };
}

// ---- t 分布 (正則化不完全ベータ関数による。Numerical Recipes の betacf) ----
function lgamma(x) {
  const c = [76.18009172947146, -86.50532032941677, 24.01409824083091, -1.231739572450155, 0.1208650973866179e-2, -0.5395239384953e-5];
  let y = x, tmp = x + 5.5, ser = 1.000000000190015;
  tmp -= (x + 0.5) * Math.log(tmp);
  for (const ci of c) ser += ci / ++y;
  return -tmp + Math.log((2.5066282746310005 * ser) / x);
}
function betacf(a, b, x) {
  let c = 1, d = 1 - ((a + b) * x) / (a + 1);
  d = 1 / (Math.abs(d) < 1e-30 ? 1e-30 : d);
  let h = d;
  for (let m = 1; m <= 200; m++) {
    const m2 = 2 * m;
    for (const aa of [(m * (b - m) * x) / ((a + m2 - 1) * (a + m2)), (-(a + m) * (a + b + m) * x) / ((a + m2) * (a + m2 + 1))]) {
      d = 1 + aa * d; d = 1 / (Math.abs(d) < 1e-30 ? 1e-30 : d);
      c = 1 + aa / c; if (Math.abs(c) < 1e-30) c = 1e-30;
      h *= d * c;
    }
    if (Math.abs(d * c - 1) < 1e-12) break;
  }
  return h;
}
function betai(a, b, x) {
  if (x <= 0) return 0;
  if (x >= 1) return 1;
  const bt = Math.exp(lgamma(a + b) - lgamma(a) - lgamma(b) + a * Math.log(x) + b * Math.log(1 - x));
  return x < (a + 1) / (a + b + 2) ? (bt * betacf(a, b, x)) / a : 1 - (bt * betacf(b, a, 1 - x)) / b;
}
/** t 分布の両側 p 値 */
export const tTwoSided = (t, df) => betai(df / 2, 0.5, df / (df + t * t));
/** t 分布の上側分位点 (両側 level の臨界値)。二分法 */
export function tCritical(df, level = 0.95) {
  let lo = 0, hi = 1000;
  for (let i = 0; i < 100; i++) {
    const mid = (lo + hi) / 2;
    if (tTwoSided(mid, df) > 1 - level) lo = mid; else hi = mid;
  }
  return (lo + hi) / 2;
}

export function meanCI(xs, level = 0.95) {
  need(xs, 2, "meanCI");
  const d = describe(xs), half = (tCritical(d.n - 1, level) * d.sd) / Math.sqrt(d.n);
  return { mean: d.mean, lower: d.mean - half, upper: d.mean + half, level, n: d.n };
}

/**
 * 2群の平均の差 (x − y)。等分散を仮定しない Welch の t 検定。
 * d は Cohen の d (プールした標準偏差)。目安: 0.2=小 / 0.5=中 / 0.8=大
 */
export function welch(xs, ys, level = 0.95) {
  need(xs, 2, "welch");
  need(ys, 2, "welch");
  const a = describe(xs), b = describe(ys);
  const va = a.sd ** 2 / a.n, vb = b.sd ** 2 / b.n, se = Math.sqrt(va + vb);
  const diff = a.mean - b.mean;
  const pooled = Math.sqrt(((a.n - 1) * a.sd ** 2 + (b.n - 1) * b.sd ** 2) / (a.n + b.n - 2));
  if ((isConstant(xs) && isConstant(ys)) || !Number.isFinite(se) || se === 0 || !Number.isFinite(pooled) || pooled === 0) {
    throw new Error("welch: 標準誤差またはプール標準偏差が0か非有限のため、平均差の検定と効果量を計算できません");
  }
  const df = (va + vb) ** 2 / (va ** 2 / (a.n - 1) + vb ** 2 / (b.n - 1));
  const t = diff / se;
  const half = tCritical(df, level) * se;
  return { diff, t, df, p: tTwoSided(t, df), d: diff / pooled, lower: diff - half, upper: diff + half, level };
}

/** Cohen の d の大きさの言葉 (レポートの表示用) */
export const effectLabel = (d) => (Math.abs(d) >= 0.8 ? "大" : Math.abs(d) >= 0.5 ? "中" : Math.abs(d) >= 0.2 ? "小" : "ほぼ無し");
/** Pearson の相関の強さの言葉 (|r| の目安) */
export const corrLabel = (r) => (Math.abs(r) >= 0.7 ? "強い" : Math.abs(r) >= 0.4 ? "中程度の" : Math.abs(r) >= 0.2 ? "弱い" : "ほぼ無い");
/** Mann-Whitney の順位双列相関 r の効果量 (|r|: 0.1=小 / 0.3=中 / 0.5=大) */
export const rankEffectLabel = (r) => (Math.abs(r) >= 0.5 ? "大" : Math.abs(r) >= 0.3 ? "中" : Math.abs(r) >= 0.1 ? "小" : "ほぼ無し");
/** p 値の表示 (0.001 未満は不等号) */
export const pText = (p) => (p < 0.001 ? "p<0.001" : `p=${p.toFixed(3)}`);

// ---- カイ二乗分布・正規分布 (正則化不完全ガンマ関数による。Numerical Recipes の gser / gcf) ----
function gammaQ(a, x) {
  if (x <= 0) return 1;
  const gln = lgamma(a);
  if (x < a + 1) {
    let ap = a, del = 1 / a, s = del;
    for (let i = 0; i < 500 && Math.abs(del) > Math.abs(s) * 1e-15; i++) { del *= x / ++ap; s += del; }
    return 1 - s * Math.exp(-x + a * Math.log(x) - gln);
  }
  let b = x + 1 - a, c = 1e300, d = 1 / b, h = d;
  for (let i = 1; i < 500; i++) {
    const an = -i * (i - a);
    b += 2; d = an * d + b; if (Math.abs(d) < 1e-300) d = 1e-300;
    c = b + an / c; if (Math.abs(c) < 1e-300) c = 1e-300;
    d = 1 / d; const del = d * c; h *= del;
    if (Math.abs(del - 1) < 1e-15) break;
  }
  return Math.exp(-x + a * Math.log(x) - gln) * h;
}
/** 正規分布の両側 p 値 */
const zTwoSided = (z) => gammaQ(0.5, (z * z) / 2);

/**
 * 2群の順位の差 (Mann-Whitney の U 検定。正規近似・同順位の補正・連続性の補正あり)。
 * r = 順位双列相関 = (P(x>y) − P(x<y))。−1〜1、0 は差なし。目安は Cohen の d と同じ言葉を使わず |r| 0.1 小・0.3 中・0.5 大
 */
export function mannWhitney(xs, ys) {
  need(xs, 2, "mannWhitney");
  need(ys, 2, "mannWhitney");
  const n1 = xs.length, n2 = ys.length, N = n1 + n2, r = ranks([...xs, ...ys]);
  const u = sum(r.slice(0, n1)) - (n1 * (n1 + 1)) / 2;
  const ties = Object.values(r.reduce((m, v) => ((m[v] = (m[v] || 0) + 1), m), {})).reduce((t, c) => t + c ** 3 - c, 0);
  const sd = Math.sqrt(((n1 * n2) / 12) * (N + 1 - ties / (N * (N - 1))));
  const diff = u - (n1 * n2) / 2, z = sd ? (diff - Math.sign(diff) * 0.5) / sd : 0;
  return { u, z, p: sd ? Math.min(1, zTwoSided(z)) : 1, r: (2 * u) / (n1 * n2) - 1, n1, n2 };
}

/**
 * 分割表の独立性 (Pearson のカイ二乗検定。補正なし)。table = [[a, b], [c, d]] のような行 × 列の度数。
 * v = Cramér の V (0=関連なし 1=完全)。期待度数 5 未満のセルが2割を超えたら lowExpected=true (p 値を信用しない)
 */
export function chisq(table) {
  if (!Array.isArray(table) || table.length < 2 || table.some((row) => !Array.isArray(row) || row.length !== table[0].length || row.length < 2 || row.some((v) => !(Number.isFinite(v) && v >= 0)))) {
    throw new Error("chisq: 2行2列以上の、同じ長さの行からなる度数の表にしてください");
  }
  const rs = table.map(sum), cs = table[0].map((_, j) => sum(table.map((row) => row[j]))), n = sum(rs);
  if (!Number.isFinite(n) || n <= 0 || rs.some((v) => !Number.isFinite(v) || v <= 0) || cs.some((v) => !Number.isFinite(v) || v <= 0)) {
    throw new Error("chisq: 各行・各列の合計が有限の正の数になる度数表にしてください");
  }
  let x2 = 0, low = 0;
  table.forEach((row, i) => row.forEach((o, j) => {
    const e = (rs[i] * cs[j]) / n;
    if (e < 5) low++;
    if (e > 0) x2 += (o - e) ** 2 / e;
  }));
  const df = (table.length - 1) * (cs.length - 1), k = Math.min(table.length, cs.length) - 1;
  return { chi2: x2, df, p: gammaQ(df / 2, x2 / 2), v: Math.sqrt(x2 / (n * k)), n, lowExpected: low > 0.2 * table.length * cs.length };
}

/** Holm 法の調整 p 値 (入力の順で返す)。仮説を複数検定したら、この値で有意かを判断する */
export function holm(ps) {
  const m = ps.length, order = ps.map((p, i) => [p, i]).sort((a, b) => a[0] - b[0]);
  const adj = new Array(m);
  let run = 0;
  order.forEach(([p, i], k) => { run = Math.max(run, Math.min(1, (m - k) * p)); adj[i] = run; });
  return adj;
}

/** 比率 k/n の信頼区間 (Wilson スコア法。正規近似の z は 95%=1.96) */
export function rateCI(k, n, level = 0.95) {
  const z = { 0.9: 1.6449, 0.95: 1.96, 0.99: 2.5758 }[level];
  if (!z) throw new Error("rateCI: level は 0.9 / 0.95 / 0.99");
  if (!Number.isSafeInteger(k) || !Number.isSafeInteger(n) || n <= 0 || k < 0 || k > n) {
    throw new Error("rateCI: k は0以上 n 以下、n は1以上の安全な整数にしてください");
  }
  const p = k / n, den = 1 + z ** 2 / n;
  const c = (p + z ** 2 / (2 * n)) / den, half = (z * Math.sqrt((p * (1 - p)) / n + z ** 2 / (4 * n * n))) / den;
  return { rate: p, lower: c - half, upper: c + half, level };
}

/**
 * 足し算の指標の増減ブリッジ。items = [{label, base, cur, sign}] (sign: 指標を増やす項目は +1、費用のように減らす項目は -1)。
 * 戻り値 = { base, cur, delta, steps: [{label, value}] }。value は「指標への影響」(費用の増加はマイナス)。
 * steps は元の順 (P&L の並び) のまま。影響の大きい順が要るときは呼ぶ側で並べ替える
 */
export function bridge(items) {
  if (!items?.length) throw new Error("bridge: items が空です");
  const steps = items.map(({ label, base, cur, sign = 1 }) => {
    if (![base, cur].every(Number.isFinite)) throw new Error(`bridge: ${label} の base / cur が数値ではありません`);
    if (sign !== 1 && sign !== -1) throw new Error(`bridge: ${label} の sign は 1 か -1 です`);
    return { label, value: sign * (cur - base) };
  });
  const base = items.reduce((t, i) => t + (i.sign ?? 1) * i.base, 0);
  const cur = items.reduce((t, i) => t + (i.sign ?? 1) * i.cur, 0);
  return { base, cur, delta: cur - base, steps };
}

/**
 * 掛け算の KPI ツリーの寄与分解 (LMDI)。base / cur = { ドライバー名: 値 } (同じキー・すべて正)。
 * 指標 = 全ドライバーの積。寄与_i = L(Y1, Y0) × ln(x1_i / x0_i)、L = (Y1 − Y0) / (ln Y1 − ln Y0)。
 * 寄与の合計は Y1 − Y0 に一致し、順番に依存しない (「どれから先に変えたか」で答えが変わる逐次代入法の欠点がない)
 */
export function driverTree(base, cur) {
  const keys = Object.keys(base);
  if (!keys.length || keys.length !== Object.keys(cur).length || !keys.every((k) => k in cur)) throw new Error("driverTree: base と cur のドライバーを揃えてください");
  for (const k of keys) if (!(base[k] > 0 && cur[k] > 0)) throw new Error(`driverTree: ${k} は正の数にしてください (0 や負の値は対数を取れない。足し算の分解 bridge を使う)`);
  const y0 = keys.reduce((t, k) => t * base[k], 1), y1 = keys.reduce((t, k) => t * cur[k], 1);
  const L = y1 === y0 ? y0 : (y1 - y0) / (Math.log(y1) - Math.log(y0));
  return { base: y0, cur: y1, delta: y1 - y0, steps: keys.map((k) => ({ label: k, value: L * Math.log(cur[k] / base[k]), base: base[k], cur: cur[k] })) };
}
