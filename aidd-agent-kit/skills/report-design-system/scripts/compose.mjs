// レポートのソース (.src.html) を部品の関数で組み立てる。analysis.mjs から import する。
// 毎回同じ位置に同じ情報 (ヘッダーの対象と作成日・結論の数字・要因ごとの図と統計・打ち手の効果/担当/期限・フッターの出所) が
// 出るように、引数を必須にしてある。欠けていればここで例外になる (build の前に気づける)。
//
//   import { header, conclusion, factor, actions, footer, source } from ".../scripts/compose.mjs";
//   writeFileSync(out, source({ title, parts: [header({...}), conclusion({...}), factor({...}), actions({...}), footer({...})] }));
//
// 文字列の引数はエスケープする。facts と figures と table だけは HTML をそのまま入れる
// (facts は <b class="num"> / <b class="num loss"> を使うため。figures / table は charts.mjs の出力)。
import { statStrip } from "./charts.mjs";
import { DEFAULT_REPORT_DETAIL, REPORT_DETAILS, OVERVIEW_JARGON, TECHNICAL_STAT, OVERVIEW_ITEMS, ACT_FIELDS, LIMITS, esc, parseCsv, serializeImpact } from "./lib.mjs";

// parseCsv の正本は lib.mjs。analysis.mjs (雛形と生成済み) が compose.mjs から import するので再 export する
export { parseCsv };

/** 打ち手の dt (ACT_FIELDS) → actions の items のキー */
const ACT_KEYS = { 効果: "effect", 担当: "owner", 期限: "due" };

const need = (o, keys, where) => {
  for (const k of keys) if (o[k] == null || o[k] === "" || (Array.isArray(o[k]) && !o[k].length)) throw new Error(`${where}: ${k} は必須です`);
};
const indent = (s, n = 2) => s.replace(/^(?=.)/gm, " ".repeat(n));
const unitSpan = (u) => (u ? `<span class="unit">${esc(u)}</span>` : "");
/** 根拠の数字。悪化なら loss=true (赤)、改善なら profit=true */
export const num = (v, { loss = false, profit = false } = {}) => `<b class="num${loss ? " loss" : profit ? " profit" : ""}">${esc(v)}</b>`;

/** 文書ヘッダー。detail は 要点・標準・詳細。指定がなければ質問で止めず標準にする。 */
export function header({ crumb, title, target, created, detail = DEFAULT_REPORT_DETAIL }) {
  need({ crumb, title, target, created }, ["crumb", "title", "target", "created"], "header");
  if (!/^\d{4}-\d{2}-\d{2}$/.test(created)) throw new Error(`header: created は YYYY-MM-DD にしてください (${created})`);
  if (!REPORT_DETAILS[detail]) throw new Error(`header: detail は ${Object.keys(REPORT_DETAILS).join("・")} のどれかにしてください (${detail})`);
  return `<header class="doc" data-detail="${REPORT_DETAILS[detail].token}">
  <p class="crumb">${esc(crumb)}</p>
  <h1 class="page-title">${esc(title)}</h1>
  <p class="sub">対象: ${esc(target)}｜作成 ${esc(created)}｜情報量: ${esc(detail)}</p>
</header>`;
}

/**
 * 結論。hero = 主数字1つ、kpis = 前提ストリップ1〜3個。
 * overview = 初心者向けの4行概要 (OVERVIEW_ITEMS)。各行 LIMITS.overview 字までで、専門用語や式は統計の要約へ回す。
 * caution = 前提の注意の1文 (具体的なデータ欠損など。任意・LIMITS.line 字まで)。
 * figure = 結論の数字の内訳を1枚で見せる図 (任意。例: 前月からの増減の waterfall)。要因ランキングの後に置かれる
 * @param {{h2: string, unit: string, toc?: string,
 *   hero: {label: string, value: string, unit?: string, chip?: string},
 *   kpis: {label: string, value: string, unit?: string, sub?: string, loss?: boolean}[],
 *   overview: {comparison: string, finding: string, interpretation: string, limitation: string},
 *   caution?: string, figure?: string}} o
 */
export function conclusion({ h2, unit, toc = "結論", hero, kpis, overview, caution, figure }) {
  need({ h2, unit, hero, kpis, overview }, ["h2", "unit", "hero", "kpis", "overview"], "conclusion");
  need(hero, ["label", "value"], "conclusion.hero");
  need(overview, OVERVIEW_ITEMS.map(([key]) => key), "conclusion.overview");
  for (const [key, value] of Object.entries(overview)) {
    if (String(value).length > LIMITS.overview) throw new Error(`conclusion.overview.${key} は${LIMITS.overview}字まで (${String(value).length}字)`);
    if (OVERVIEW_JARGON.test(String(value))) throw new Error(`conclusion.overview.${key} は専門用語を平易な表現へ言い換えてください (${value})`);
  }
  if (!/\d/.test(String(overview.finding))) throw new Error("conclusion.overview.finding には最重要の数字を入れてください");
  const kpi = kpis.map((k) => {
    need(k, ["label", "value"], "conclusion.kpis");
    return `      <div class="kpi"><div class="kpi-label">${esc(k.label)}</div><div class="kpi-value num${k.loss ? " loss" : ""}">${esc(k.value)}${unitSpan(k.unit)}</div>${k.sub ? `<div class="kpi-sub">${esc(k.sub)}</div>` : ""}</div>`;
  });
  return `<section data-kind="conclusion" data-toc="${esc(toc)}" data-unit="${esc(unit)}">
  <h2>${esc(h2)}</h2>
  <div class="hero card">
    <div class="hero-number">
      <div class="hn-label">${esc(hero.label)}</div>
      <div class="hn-value num">${esc(hero.value)}${unitSpan(hero.unit)}</div>
${hero.chip ? `      <div class="hn-sub"><span class="delta-chip">${esc(hero.chip)}</span></div>\n` : ""}    </div>
    <div class="kpi-strip">
${kpi.join("\n")}
    </div>
  </div>
  <div class="overview card">
    <div class="overview-title">分析結果の概要</div>
    <ul class="overview-list">
${OVERVIEW_ITEMS.map(([key, label]) => `      <li><span class="overview-label">${label}</span><span class="overview-text">${esc(overview[key])}</span></li>`).join("\n")}
    </ul>
  </div>
${caution ? `  <div class="caution-panel">△ ${esc(caution)}</div>\n` : ""}${figure ? indent(figure) + "\n" : ""}</section>`;
}

/** 背景の説明仮説の根拠の強さ (references/causes.md §4) → キットのバッジ */
export const LEVELS = { データで確認: "badge-success", 公表資料: "badge-active", 想定: "badge-warning" };
export const HYPOTHESIS_VERDICTS = { 採用: "badge-success", 棄却: "badge-danger", 保留: "badge-warning" };

/** brief の主張と results の機械判定を、表示用に重複入力せず接続する。 */
export function hypothesisClaim(brief, results, id) {
  const hypothesis = (brief?.hypotheses || []).find((item) => item.id === id);
  const result = (results?.hypotheses || []).find((item) => item.id === id);
  if (!hypothesis) throw new Error(`hypothesisClaim: brief.hypotheses に ${id} がありません`);
  if (!result) throw new Error(`hypothesisClaim: results.hypotheses に ${id} がありません`);
  if (!HYPOTHESIS_VERDICTS[result.判定]) throw new Error(`hypothesisClaim: ${id} の判定は ${Object.keys(HYPOTHESIS_VERDICTS).join("・")} のどれかにしてください (${result.判定})`);
  return { id, text: hypothesis.主張, verdict: result.判定 };
}

/**
 * 要因。impact = 結論の指標への影響 (悪化はマイナス)。figures = charts.mjs の figure() を1つ以上。
 * table = charts.mjs の table() (任意)。stats と facts の個数は plan.情報量 (要点・標準・詳細) に従う。
 * causes = 背景の説明仮説 (仕組み) の2〜4項目 (背景分析では2項目以上を check-llm review が強制) { text, level: データで確認|公表資料|想定, source?: { title, url } }。
 *   探索は結果 → 中間 → 原因と「なぜ」をたどり、表示は原因 → 中間 → 結果の順に戻す (図の数字の言い換えにしない。prompts/analyst.md「C. 解釈」の「背景の説明仮説」)。
 *   見出しの直後に出る。公表資料には source が必須。出典の URL は「データと計算」に文字で出す (外部リンクにしない)
 * hypotheses = この要因で仮説を使う場合の brief/results の仮説 ID 配列。単純な記述は [] でよい。
 *   ID がある場合は少なくとも1つを採用済みにし、claim を hypothesisClaim() で作る。[] なら claim は省略する。
 * interpretation = 統計的事実から読めること。観測していない原因や行動を事実として混ぜない。
 * meaning = 読み手の判断にとっての意味の1文 (必須・LIMITS.line 字まで)。「だから何を前提に・何を変えるか」を書き、図に見える事実を繰り返さない
 */
export function factor({ toc, impact, hypotheses = [], h2, figures, table, stats, facts, interpretation, claim, data, calc, causes = [], meaning }) {
  need({ toc, impact, h2, figures, stats, facts, interpretation, data, calc, meaning }, ["toc", "impact", "h2", "figures", "stats", "facts", "interpretation", "data", "calc", "meaning"], "factor");
  if (!Array.isArray(hypotheses) || !hypotheses.every((id) => typeof id === "string" && id === id.trim() && id && !id.includes(",")) || new Set(hypotheses).size !== hypotheses.length) throw new Error(`factor「${toc}」: hypotheses は重複のない仮説 ID 配列にしてください`);
  if (hypotheses.length) {
    need(claim, ["id", "text", "verdict"], `factor「${toc}」.claim`);
    if (!hypotheses.includes(claim.id)) throw new Error(`factor「${toc}」: claim.id ${claim.id} を hypotheses に含めてください`);
    if (claim.verdict !== "採用") throw new Error(`factor「${toc}」: 最終要因の claim は採用された仮説にしてください (${claim.id}: ${claim.verdict})`);
  } else if (claim != null) throw new Error(`factor「${toc}」: hypotheses が空なら claim も省略してください`);
  if (String(interpretation).length > LIMITS.interpretation) throw new Error(`factor「${toc}」: interpretation は${LIMITS.interpretation}字まで (${String(interpretation).length}字)`);
  if (String(meaning).length > LIMITS.line) throw new Error(`factor「${toc}」: meaning は${LIMITS.line}字まで (${String(meaning).length}字)`);
  if (!Number.isFinite(Number(impact))) throw new Error(`factor: impact は数値にしてください (${impact})`);
  if (!stats.some((s) => s.label === "n")) throw new Error(`factor「${toc}」: stats に n (標本の件数) を入れてください`);
  for (const stat of stats) {
    need(stat, ["label", "value"], `factor「${toc}」.stats`);
    if (String(stat.sub || "").length > LIMITS.statSub) throw new Error(`factor「${toc}」: stats の補足は${LIMITS.statSub}字まで (${stat.label})`);
    if (TECHNICAL_STAT.test(`${stat.label} ${stat.value}`) && !stat.sub) throw new Error(`factor「${toc}」: 専門指標「${stat.label}」には初心者向けの読み方 (sub) が必要です`);
  }
  if (causes.length > 4) throw new Error(`factor「${toc}」: causes は4項目まで (${causes.length})`);
  for (const c of causes) {
    need(c, ["text", "level"], `factor「${toc}」.causes`);
    if (!LEVELS[c.level]) throw new Error(`factor「${toc}」: causes の level は ${Object.keys(LEVELS).join("・")} のどれか (${c.level})`);
    if (c.level === "公表資料" && !/^https:\/\//.test(c.source?.url || "")) throw new Error(`factor「${toc}」: 公表資料の項目には source.url (https://…) が必要です (${c.text})`);
  }
  const srcs = [...new Map(causes.filter((c) => c.source?.url).map((c) => [c.source.url, c.source])).values()];
  return `<section data-kind="factor" data-toc="${esc(toc)}" data-impact="${serializeImpact(impact)}"${hypotheses.length ? ` data-hypotheses="${esc(hypotheses.join(","))}"` : ""}>
  <h2>${esc(h2)}</h2>
${causes.length ? `  <div class="causes-h">背景の説明仮説</div>
  <ul class="causes">
${causes.map((c) => `    <li><span class="badge ${LEVELS[c.level]}">${esc(c.level)}</span><span class="cause-text">${esc(c.text)}${c.source ? `<small>${esc(c.source.title)}</small>` : ""}</span></li>`).join("\n")}
  </ul>
` : ""}  <div class="meaning"><span class="meaning-h">判断への意味</span><span class="meaning-text">${esc(meaning)}</span></div>
${figures.map((f) => indent(f)).join("\n")}
${table ? indent(table) + "\n" : ""}${indent(statStrip(stats))}
  <div class="facts-h">統計的事実</div>
  <ul class="facts">
${facts.map((f) => `    <li>${f}</li>`).join("\n")}
  </ul>
  <div class="statement interpretation"><span class="statement-h">解釈</span><span class="statement-text">${esc(interpretation)}</span></div>
${claim ? `  <div class="statement claim" data-hypothesis-id="${esc(claim.id)}" data-verdict="${esc(claim.verdict)}"><span class="statement-h">仮説・主張</span><span class="badge ${HYPOTHESIS_VERDICTS[claim.verdict]}">${esc(claim.verdict)}</span><span class="statement-text">${esc(claim.text)}</span></div>
` : ""}  <details class="disclosure">
    <summary>データと計算</summary>
    <div class="disclosure-body"><dl class="def-list"><dt>データ</dt><dd>${esc(data)}</dd><dt>計算</dt><dd>${esc(calc)}</dd>${srcs.length ? `<dt>出典</dt>${srcs.map((x) => `<dd>${esc(x.title)} ${esc(x.url)}</dd>`).join("")}` : ""}</dl></div>
  </details>
</section>`;
}

/**
 * 打ち手。items の各件: title (動詞で始める) / from (要因番号 "1" や "1,3") / source (data・hearing・pending) /
 * effect (数字を含む) / owner / due。データで決まらない担当・期限は「要確認」と書き source を pending にし、ユーザーに聞く
 */
export function actions({ h2, toc = "打ち手", items }) {
  need({ h2, items }, ["h2", "items"], "actions");
  const li = items.map((a) => {
    need(a, ["title", "from", "source", ...ACT_FIELDS.map((f) => ACT_KEYS[f])], "actions.items");
    return `    <li class="act" data-from="${esc(a.from)}" data-source="${esc(a.source)}">
      <b class="act-title">${esc(a.title)}</b>
      <dl class="act-meta">
${ACT_FIELDS.map((f) => `        <div><dt>${f}</dt><dd>${esc(a[ACT_KEYS[f]])}</dd></div>`).join("\n")}
      </dl>
    </li>`;
  });
  return `<section data-kind="action" data-toc="${esc(toc)}">
  <h2>${esc(h2)}</h2>
  <ol class="actions">
${li.join("\n")}
  </ol>
</section>`;
}

/** フッター。data = 出所 (ファイル名・期間)。method = 手法の一言 (任意) */
export function footer({ crumb, data, method }) {
  need({ crumb, data }, ["crumb", "data"], "footer");
  return `<footer>\n${esc(crumb)}｜データ: ${esc(data)}${method ? `｜${esc(method)}` : ""}\n</footer>`;
}

/** ソース全体 */
export function source({ title, parts }) {
  need({ title, parts }, ["title", "parts"], "source");
  return `<title>${esc(title)}</title>\n\n${parts.join("\n\n")}\n`;
}
