#!/usr/bin/env node
// レポート1本分のフォルダと analysis.mjs の雛形を作る。出力先とファイル名を毎回同じ規則にするための入口。
//
//   node scripts/new-report.mjs <出力ルート> <YYYY-MM> <slug>
//   例: node scripts/new-report.mjs reports 2026-05 kuusha
//
// できるもの (SKILL.md の Quickstart):
//   <出力ルート>/<YYYY-MM>-<slug>/
//     brief.json               問い・仮説・情報量の入力欄 (情報量は「標準」を初期値にする)
//     inputs.json              init で受け取った入力データの絶対パスと SHA-256
//     analysis.mjs              データを読み、stats.mjs で計算し、charts.mjs と compose.mjs でソースを書き出す (手で編集する唯一のファイル)
//     <YYYY-MM>-<slug>.src.html analysis.mjs の出力 (手で編集しない)
//     <YYYY-MM>-<slug>.html     build-report.mjs の出力 (配布物)
//     screens/                  verify を実行した場合だけ作るスクリーンショット
// YYYY-MM = 対象データの月 (期間なら最後の月)。slug = 英小文字・数字・ハイフン (例 kuusha / repair-cost)。
// 既にフォルダがあれば上書きしない。終了コード: 0=作成 2=入力エラー
import { chmodSync, copyFileSync, existsSync, mkdirSync, mkdtempSync, readFileSync, renameSync, rmSync, writeFileSync } from "node:fs";
import { dirname, join, relative, resolve } from "node:path";
import { fileURLToPath, pathToFileURL } from "node:url";
import { DEFAULT_REPORT_DETAIL, NAME_RE, INPUT_MANIFEST_FILE, INPUT_MANIFEST_VERSION, BG_RE } from "./lib.mjs";
import { inputManifest } from "./inputs.mjs";

// フォルダ名の規則と入力マニフェストの正本は lib.mjs。new-report.mjs から import している呼び出し元のために再 export する
export { NAME_RE, INPUT_MANIFEST_FILE, INPUT_MANIFEST_VERSION, inputManifest };
const SCRIPTS = dirname(fileURLToPath(import.meta.url));

export const briefTemplate = (month) => ({
  plan: {
    問い: "", 読み手: "", 判断: "", 指標: "", 単位: "", 基準: "", 範囲: month,
    情報量: DEFAULT_REPORT_DETAIL,
    背景分析: false,
  },
  候補: [],
  hypotheses: [],
  unknowns: [],
});

export function scaffold(name, scriptsRel) {
  const imp = (f) => JSON.stringify(`${scriptsRel}/${f}`);
  return `// ${name} の分析。データ → 計算 → 図と統計 → ソース (.src.html) を1本で行う。数字を手で打たない。
// 通常の計算・生成・静的検査は: node ${scriptsRel}/report.mjs build <このフォルダ>
// 4幅の実描画と独立reviewまで依頼された場合だけ: node ${scriptsRel}/report.mjs verify <このフォルダ>
// 問いと仮説は brief.json、判定の数字は results.json (どちらも prompts/analyst.md)。手法は references/statistics.md、背景の説明仮説は references/causes.md、手順は SKILL.md の Quickstart。
import { readdirSync, readFileSync, writeFileSync } from "node:fs";
import { basename, dirname, join } from "node:path";
import { fileURLToPath } from "node:url";
import { describe, quantile, outliersIQR, pareto, pearson, spearman, linreg, meanCI, welch, mannWhitney, rateCI, chisq, holm, effectLabel, corrLabel, rankEffectLabel, pText, bridge, driverTree } from ${imp("stats.mjs")};
import { fmt, sfmt, figure, hbar, columns, line, multiline, waterfall, stacked, dumbbell, butterfly, heatmap, table, histogram, boxplot, scatter, forest, paretoChart, flow } from ${imp("charts.mjs")};
import { header, conclusion, factor, actions, footer, source, num, parseCsv, hypothesisClaim } from ${imp("compose.mjs")};
import { checkBrief, mergeBackgroundFiles, BG_FILE } from ${imp("check-llm.mjs")};
import { readInputManifest, readRows, parseNumericCell } from ${imp("inputs.mjs")};

const HERE = dirname(fileURLToPath(import.meta.url));
const OUT = join(HERE, ${JSON.stringify(`${name}.src.html`)});
// 表示する所属とレポート種別。生成後にここだけ変更する
const REPORT_LABEL = "TODO 組織名｜TODO レポート種別";

// ---- 0. 問いと仮説: brief.json (LLM が書き、check-llm.mjs brief で合格したもの) ----
const need = (f) => {
  try { return JSON.parse(readFileSync(join(HERE, f), "utf8")); }
  catch { throw new Error(\`\${f} がありません。report.mjs init で入力欄を作り、prompts/analyst.md に従って埋める (SKILL.md の Quickstart)\`); }
};
const BRIEF = need("brief.json");
// 背景の仮説の外部の数字 (prompts/research.md が出典つきで集めたもの)。系列 → { 期間: 値 } で引く
// 背景データ.csv (裏づけ) と 背景データ-反証.csv (反証・別の説明) を合わせて読む。
// 同一ファイルの系列・期間重複と、ファイル間の競合は拒否し、ファイル間の完全一致行だけ1件にする。
const BG_INPUTS = readdirSync(HERE).filter((f) => ${BG_RE}.test(f)).sort()
  .map((f) => ({ name: f, rows: parseCsv(readFileSync(join(HERE, f), "utf8")) }));
const MERGED_BG = mergeBackgroundFiles(BG_INPUTS);
if (MERGED_BG.errors.length) throw new Error(\`背景データを統合できません:\\n\${MERGED_BG.errors.join("\\n")}\`);
const BG = MERGED_BG.rows;
const bg = (name) => Object.fromEntries(BG.filter((r) => r.系列 === name).map((r) => [r.期間, Number(r.値)]));
const bgSource = (name) => { const r = BG.find((x) => x.系列 === name); return r && { title: r.出典, url: r.URL }; };
// 調査の途中 (背景データがまだ無い) でも内訳の部分を試せるよう、そのときは背景データの照合だけ後回しにする (最後は check-llm.mjs brief / review が照合する)
const briefErrors = checkBrief(BRIEF, need("profile.json"), BG, { pre: !BG.length });
if (briefErrors.length) throw new Error(\`brief.json が検査に通りません (check-llm.mjs brief):\\n\${briefErrors.join("\\n")}\`);
const PLAN = BRIEF.plan; // { 問い, 読み手, 判断, 指標, 単位, 基準, 範囲, 情報量, 分解・焦点 (任意) }

// ---- 1. データ: 出所のファイルを列挙する (フッターと「データと計算」に同じ名前を出す) ----
// 複数指定は同じ列・型を持つ分割ファイルだけ。異種データの join は行わない (report.mjs init が検査する)
const INPUTS = readInputManifest(HERE);
const DATA_FILES = INPUTS.files.map((entry) => entry.path);
const rows = DATA_FILES.flatMap(readRows);

// ---- 2. 計算: 問いの型ごとの関数 (references/statistics.md §2)。まず describe で n・中央値・外れ値を見る ----
// const parsed = rows.map((r) => parseNumericCell(r["列"])); // 空欄を0にせず、桁区切りをprofileと同じ規則で読む
// const x = parsed.filter(Number.isFinite);
// const excluded = parsed.length - x.length; // 除外数・欠測率と実際のnを示す (statistics.md §4)
// 分布: describe(x) / outliersIQR(rows, "列")          図: histogram / boxplot
// 比較: welch(a, b) と mannWhitney(a, b) (順位双列相関は rankEffectLabel) / rateCI(k, n) / chisq([[..],[..]])   図: hbar / boxplot / columns
// 関係: pearson・spearman(x, y) / linreg(x, y)         図: scatter
// 分解: bridge([{ label, base, cur, sign }]) = 足し算 / driverTree(基準, 今) = 掛け算。合計 = 差   図: waterfall
// 推移: 基準期間の describe から (値 − 平均) / sd       図: line
// 集中: pareto(rows, "列")                             図: paretoChart
// 図は結果の内容で選ぶ (references/charts.md): 構成 = stacked / 2時点 = dumbbell / 区間 = forest / 2軸 = heatmap
//   背景の出来事 = line・multiline の events / 背景の説明仮説の筋 = flow (結論の図に向く)
//   flow の edge は破線が既定。恒等式・定義・機械的に検証済みだけ solid: "identity" | "definition" | "mechanically-verified" で実線にする
// 検定を複数したら holm(ps) で補正する。効果量と区間を主、p 値を従に書く

// 仮説を使う場合だけ、反証条件をコードで判定し、根拠の数字を残す (判定を LLM に任せない)
// const verdict = (cond) => (cond == null ? "保留" : cond ? "棄却" : "採用"); // cond = 反証条件が成り立ったか
const judged = [
  // { id: "H1", 判定: verdict(除いた差 / 全体の差 >= 0.5), 数字: { 全体の差, 除いた差 } },
];
// steps は factors の toc/impact と同じ label/value を全件入れる。分解があれば delta も入れ、steps の合計を一致させる
// const RESULTS = { steps, hypotheses: judged }; // 分解がある場合は delta も入れる
// writeFileSync(join(HERE, "results.json"), JSON.stringify(RESULTS, null, 2) + "\\n");

// ---- 3. 要因: 情報量に応じて 要点2 / 標準3 / 詳細5 つまで。impact は結論の指標への寄与 (分解があれば steps の値)。
//      統計的事実 → 解釈は常に分け、仮説を使う場合だけ仮説・主張を追加する。判断への意味までつなぐ ----
// h2 は、背景を調べた要因なら「なぜ・何が・どれだけ」、記述・比較だけなら未検証の原因を足さず「何が・どれだけ」で書く
// hypotheses は仮説を使う場合だけ書く。その場合は results.json で少なくとも1つ「採用」にする
// claim は仮説を使う場合だけ hypothesisClaim(BRIEF, RESULTS, id) で作る (手入力で写さない)
// facts は再計算できる統計的事実だけ。interpretation はその事実から読めること。観測していない原因は混ぜない
// 探索は結果から「なぜ」をたどり (結果 → 中間 → 原因)、causes の表示は読み手が追える向き (原因 → 中間 → 結果) に戻す。
// causes は plan.背景分析 === true で差の背景を扱うときだけ書き、想定は半分以下にする (prompts/analyst.md「C. 解釈」の「背景の説明仮説」)
// meaning は、読み手がこの要因を受けて何を前提に置き・何を変えるかの1文
const factors = [
  // factor({
  //   toc: "要因の名前", impact: -150, hypotheses: ["H1"], h2: "なぜ・何が・どれだけの1文",
  //   claim: hypothesisClaim(BRIEF, RESULTS, "H1"),
  //   interpretation: "統計的事実から読めること。原因の断定や行動指示を混ぜない (100字まで)",
//   causes: [{ text: "原因候補: 制度の変更日と…の変化時期が対応", level: "公表資料", source: bgSource("出来事") }, { text: "中間: 同じ期間に…も変化 (数字は変数から)", level: "データで確認" }, { text: "結果: …の説明と整合するが、因果は未確認", level: "想定" }],
  //   meaning: "読み手が何を前提に置き・何を変えるかの1文 (60字まで)",
  //   figures: [figure({ title: "実車率の分布", legend: "赤=目標未満、破線=平均", svg: histogram({ values, bins: [0, 20, 40, 60, 80, 100], unit: "%", aria: "…" }) })],
  //   stats: [{ label: "n", value: \`\${d.n}台\` }, { label: "中央値", value: \`\${fmt(d.median, 1)}%\`, sub: "半数の車両はこの値以下" }, { label: "標準偏差", value: \`\${fmt(d.sd, 1)}pt\`, sub: "車両ごとの差は平均から約7pt" }],
  //   facts: [\`全体 \${num(fmt(d.mean, 1) + "%")}、基準 \${num("75%")}\`, "…"],
  //   data: [...DATA_FILES.map((f) => basename(f)), ...(BG.length ? [BG_FILE] : [])].join("・"), calc: "計算式を1行で",
  // }),
];

// ---- 4. 打ち手: ユーザーの依頼、または判断に次の行動が必要な場合だけ作る。空ならセクションも CTA も生成しない ----
// from は要因の名前 (toc) で書く。番号は要因の並びで変わるので、ビルドが番号に直す
const acts = [
  // { title: "動詞で始める指示", from: "要因の名前", source: "pending", effect: "期待値 +12万円/月 (前提: …)", owner: "要確認", due: "要確認" },
];

writeFileSync(
  OUT,
  source({
    title: "TODO 題名",
    parts: [
      header({ crumb: REPORT_LABEL, title: "TODO 題名", target: "TODO 範囲・件数", created: "YYYY-MM-DD", detail: PLAN.情報量 }),
      conclusion({
        h2: "TODO 結論の1文（数字を入れる）", unit: "TODO 影響の単位",
        hero: { label: PLAN.指標, value: "TODO" }, kpis: [],
        // 初心者向け概要。各48字まで。専門用語・式・p値は stats に置き、ここでは平易に言い換える
        overview: {
          comparison: "TODO 何を、どの期間・基準と比べたか",
          finding: "TODO 数字で分かった最重要の結果",
          interpretation: "TODO その結果が判断にとって何を意味するか",
          limitation: "TODO このデータだけでは言えないこと",
        },
        figure: undefined /* 結論の図 (waterfall) */,
      }),
      ...factors,
      ...(acts.length ? [actions({ h2: "TODO 打ち手の1文", items: acts })] : []),
      footer({ crumb: REPORT_LABEL, data: DATA_FILES.map((f) => basename(f)).join("・"), method: \`比較: \${PLAN.基準}\` }),
    ],
  }),
);
console.log(\`書き出し: \${OUT}\`);
`;
}

function main(argv) {
  const [root, month, slug, ...options] = argv;
  const name = `${month}-${slug}`;
  const profile = options[0] === "--profile" && options[1] ? resolve(options[1]) : null;
  const data = profile ? options.slice(2).map((file) => resolve(file)) : [];
  const invalidOptions = options.length && (!profile || !existsSync(profile) || !data.length || !data.every(existsSync));
  if (!root || !month || !slug || !NAME_RE.test(name) || invalidOptions || new Set(data).size !== data.length) {
    console.error("使い方: node scripts/new-report.mjs <出力ルート> <YYYY-MM> <slug>  (slug は英小文字・数字・ハイフン)");
    return 2;
  }
  const rootDir = resolve(root);
  const dir = resolve(rootDir, name);
  if (existsSync(dir)) {
    console.error(`入力エラー: ${dir} は既にあります (上書きしない。analysis.mjs を編集して再実行する)`);
    return 2;
  }
  mkdirSync(rootDir, { recursive: true });
  const staging = mkdtempSync(join(rootDir, `.${name}.tmp-`));
  chmodSync(staging, 0o777 & ~process.umask());
  // 同じリポジトリの中なら相対パス (リポジトリごと動かしても壊れない)。ルートまで遡るなら無関係な場所なので絶対パス
  let rel = relative(dir, SCRIPTS).split("\\").join("/") || ".";
  if (rel.split("/").filter((x) => x === "..").length >= dir.split(/[\\/]/).filter(Boolean).length) rel = SCRIPTS.split("\\").join("/");
  try {
    writeFileSync(join(staging, "analysis.mjs"), scaffold(name, rel));
    writeFileSync(join(staging, "brief.json"), JSON.stringify(briefTemplate(month), null, 2) + "\n");
    writeFileSync(join(staging, INPUT_MANIFEST_FILE), JSON.stringify(inputManifest(data, { allowEmpty: !profile }), null, 2) + "\n");
    if (profile) copyFileSync(profile, join(staging, "profile.json"));
    renameSync(staging, dir);
  } catch (error) {
    rmSync(staging, { recursive: true, force: true });
    throw error;
  }
  console.log(`作成: ${dir}/brief.json・${INPUT_MANIFEST_FILE}・analysis.mjs (情報量: ${DEFAULT_REPORT_DETAIL})`);
  console.log(`次 (SKILL.md の Quickstart): brief.json の入力欄と analysis.mjs を整え、node ${join(SCRIPTS, "report.mjs")} build ${dir}  (途中検査が必要なときだけ check)`);
  return 0;
}

if (process.argv[1] && import.meta.url === pathToFileURL(process.argv[1]).href) process.exit(main(process.argv.slice(2)));
