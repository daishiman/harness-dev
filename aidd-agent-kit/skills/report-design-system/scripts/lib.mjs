// レポート側スクリプト全体の共有部分 (埋め込む CSS/JS、契約の定数、文字列と書き込みの小道具)。sync-kit.mjs 以外を import しない。
// 埋め込むCSS/JSの正本はここで1回だけ組み立てる。sync-kit.mjs はこのファイルを import しない (循環させない)。
import { readFileSync, renameSync, rmSync, writeFileSync } from "node:fs";
import { dirname, join, resolve, sep } from "node:path";
import { fileURLToPath } from "node:url";
import { VENDOR_FILES, vendorPath, sha256 } from "./sync-kit.mjs";

export { sha256 };

export const SKILL_DIR = resolve(dirname(fileURLToPath(import.meta.url)), "..");
/** path がスキルのフォルダの中か。成果物をスキルの中 (見本の template.src.html の隣など) に書かないために使う */
export const isInsideSkill = (path) => resolve(path).startsWith(SKILL_DIR + sep);
export const REPORT_CSS = join(SKILL_DIR, "assets/report.css");
export const REPORT_JS = join(SKILL_DIR, "assets/report.js");

/**
 * キット部品CSSの先頭にある配色の @import 行。単一HTMLでは配色CSSを直前に埋め込むので、この1行だけを除く。
 * 除去はこの完全一致の1行に限る (別の @import が増えたら除かずに残し、check の E02 で止める)。
 */
export const KIT_COLOR_IMPORT = '@import url("../standard/standard-color-system.css");\n';

/**
 * 埋め込むCSS (vendor 配色 → vendor キット部品 → report.css の順。後ろほど優先)。
 * 色の値はキット正本 (vendor) だけが持つ。レポート側で基本色を上書きする層は置かない。
 */
export const embeddedCss = () =>
  [...VENDOR_FILES.map((f) => readFileSync(vendorPath(f), "utf8").replace(KIT_COLOR_IMPORT, "")), readFileSync(REPORT_CSS, "utf8")]
    .map((s) => s.trimEnd())
    .join("\n");
/** 埋め込むJS */
export const embeddedJs = () => readFileSync(REPORT_JS, "utf8").trimEnd();

/**
 * 配布する単一HTMLの外枠 (vendor 配色 → キット部品 → report.css の <style>、report.js の <script>)。
 * title・nav・body は HTML としてそのまま入れる (エスケープは呼ぶ側)。nav があれば目次と本文を .shell で横に並べる。
 * 図のツールチップ要素 (#tip) は常に置く (report.js は無ければ何もしない)。末尾は改行1つで終える。
 */
export const pageShell = ({ title, nav, mainClass = "wrap", body }) => [
  "<!doctype html>",
  '<html lang="ja">',
  "<head>",
  '<meta charset="utf-8">',
  '<meta name="viewport" content="width=device-width, initial-scale=1">',
  `<title>${title}</title>`,
  "<style>",
  embeddedCss(),
  "</style>",
  "</head>",
  '<body class="standard-app">',
  '<a class="skip btn btn-secondary" href="#main">本文へ移動</a>',
  ...(nav ? ['<div class="shell">', nav] : []),
  `<main id="main" class="${mainClass}">`,
  body,
  "</main>",
  ...(nav ? ["</div>"] : []),
  '<div id="tip" class="tooltip" role="status" aria-hidden="true"></div>',
  "<script>",
  embeddedJs(),
  "</script>",
  "</body>",
  "</html>",
  "",
].join("\n");

/** セクションの見出し帯 (番号・種類のチップ + h2)。h2 は <h2>…</h2> の要素ごと渡す */
export const secHead = (chip, h2) => `<div class="sec-head"><span class="secno">${chip}</span>${h2}</div>`;
/** 文書ヘッダーの印刷ボタン (副操作) */
export const PRINT_BUTTON = '<div class="doc-tools"><button type="button" class="btn btn-secondary" data-print>印刷・PDFで保存</button></div>';

/** 本文の文字列をHTMLに入れるためのエスケープ (null・undefined は空文字) */
export const esc = (s) => String(s ?? "").replace(/&/g, "&amp;").replace(/</g, "&lt;").replace(/>/g, "&gt;").replace(/"/g, "&quot;");
/** esc の逆 (&lt; &gt; &quot; &amp; だけを戻す。&amp; を最後に戻して二重に解かない) */
export const decodeEntities = (s) => s.replace(/&lt;/g, "<").replace(/&gt;/g, ">").replace(/&quot;/g, '"').replace(/&amp;/g, "&");
/** HTML断片からタグを除いた表示テキスト (実体参照はそのまま残す。字数の検査はこの長さで数える) */
/** 表示テキスト。aria-hidden の飾り (用語マークの ?、棒グラフの帯) は読み上げられないので字数にも数えない */
export const textOf = (html) =>
  html
    .replace(/<(\w+)[^>]*\baria-hidden="true"[^>]*>[\s\S]*?<\/\1>/g, "")
    .replace(/<[^>]*>/g, "")
    .replace(/\s+/g, " ")
    .trim();
/** 見えている文 (style・script を除き、タグを空白にして実体参照を戻したもの) */
export const visibleText = (html) =>
  decodeEntities(html.replace(/<(style|script)\b[\s\S]*?<\/\1>/gi, " ").replace(/<[^>]*>/g, " ")).replace(/\s+/g, " ").trim();

/** 一時ファイルに書いてから rename で置き換える (途中で失敗しても壊れたファイルを残さない)。options は writeFileSync へ渡す (mode など) */
export function writeAtomic(path, text, options = {}) {
  const temporary = `${path}.${process.pid}.tmp`;
  rmSync(temporary, { force: true });
  try {
    writeFileSync(temporary, text, { encoding: "utf8", flag: "wx", ...options });
    renameSync(temporary, path);
  } finally {
    rmSync(temporary, { force: true });
  }
}

/** 検査結果の表示 (NG → 注意 → 合否の1行) */
export function printResult({ errors, warnings }) {
  for (const e of errors) console.log(`  NG ${e}`);
  for (const w of warnings) console.log(`  注意 ${w}`);
  console.log(errors.length ? `検査: 不合格 (エラー ${errors.length} / 警告 ${warnings.length})` : `検査: 合格 (警告 ${warnings.length})`);
}

/** レポートのフォルダ名 (= ファイル名の本体) の規則: <YYYY-MM>-<slug>。slug = 英小文字・数字・ハイフン */
export const NAME_RE = /^\d{4}-(0[1-9]|1[0-2])-[a-z0-9]+(?:-[a-z0-9]+)*$/;
/** init で受け取った入力データの絶対パスと SHA-256 の記録 */
export const INPUT_MANIFEST_FILE = "inputs.json";
export const INPUT_MANIFEST_VERSION = 1;
/** 外部調査の背景データ (背景データ.csv と 背景データ-反証.csv など)。フォルダ直下のこの名前だけを読む */
export const BG_RE = /^背景データ.*\.csv$/;

/**
 * CSV を読む (UTF-8、BOM と "…" の囲み・囲み内の改行とカンマに対応)。1行目を見出しとしてオブジェクトの配列を返す。
 * 数値に変換できる列は呼ぶ側で Number() する (勝手に変換しない)
 */
export function parseCsv(text) {
  if (typeof text !== "string") throw new TypeError("CSV は文字列で渡してください");
  const rows = [];
  let row = [], cell = "", state = "field", line = 1;
  const s = text.replace(/^﻿/, "");
  const pushCell = () => {
    row.push(cell.trim());
    cell = "";
    state = "field";
  };
  const pushRow = () => {
    pushCell();
    if (row.some((value) => value !== "")) rows.push({ values: row, line });
    row = [];
  };
  for (let i = 0; i < s.length; i++) {
    const c = s[i];
    if (state === "quoted") {
      if (c === '"' && s[i + 1] === '"') (cell += '"'), i++;
      else if (c === '"') state = "after-quote";
      else if (c === "\r" || c === "\n") {
        if (c === "\r" && s[i + 1] === "\n") i++;
        cell += "\n";
        line += 1;
      } else cell += c;
      continue;
    }
    if (state === "after-quote") {
      if (c === ",") pushCell();
      else if (c === "\r" || c === "\n") {
        if (c === "\r" && s[i + 1] === "\n") i++;
        pushRow();
        line += 1;
      } else if (!/\s/.test(c)) throw new Error(`CSV ${line}行目: 引用符を閉じた後に余分な文字があります`);
      continue;
    }
    if (c === '"') {
      if (cell.trim() !== "") throw new Error(`CSV ${line}行目: 引用符はセルの先頭に置いてください`);
      cell = "";
      state = "quoted";
    } else if (c === ",") pushCell();
    else if (c === "\n" || c === "\r") {
      if (c === "\r" && s[i + 1] === "\n") i++;
      pushRow();
      line += 1;
    } else cell += c;
  }
  if (state === "quoted") throw new Error(`CSV ${line}行目: 引用符が閉じていません`);
  if (cell !== "" || row.length || state === "after-quote") pushRow();
  if (!rows.length) throw new Error("CSV に見出し行がありません");
  const [headerRow, ...body] = rows;
  const head = headerRow.values;
  if (head.some((name) => name === "")) throw new Error(`CSV ${headerRow.line}行目: 空の見出しがあります`);
  const duplicate = head.find((name, index) => head.indexOf(name) !== index);
  if (duplicate) throw new Error(`CSV ${headerRow.line}行目: 見出し「${duplicate}」が重複しています`);
  for (const record of body) {
    if (record.values.length !== head.length) throw new Error(`CSV ${record.line}行目: 列数が見出しの ${head.length} 列と一致しません (${record.values.length} 列)`);
  }
  return body.map(({ values }) => Object.fromEntries(head.map((name, index) => [name, values[index]])));
}

/** セクションの種別。ソースの並びはこの順 (conclusion 1つ → factor 1つ以上 → 必要な場合だけ action 1つ) */
export const KINDS = { conclusion: "結論", factor: "要因", action: "打ち手" };
export const ORDER = /^conclusion( factor)+( action)?$/;
/**
 * 打ち手の出所 (data-source)。キットの .badge に記号と文言を併記して表示する (色だけで伝えない)。
 *   data    = 担当・期限・効果をデータと既存の決まりから決められた
 *   hearing = データで決められない点をユーザーへのヒアリングで確定した
 *   pending = ヒアリングしても未確定。該当項目に「要確認」と書き、検査は警告 (W04) を出す
 */
export const ACT_SOURCES = {
  data: ["badge-active", "● データで算出"],
  hearing: ["badge-tag", "◆ ヒアリングで確定"],
  pending: ["badge-warning", "△ 要確認"],
};
/** 打ち手の必須項目 (dl.act-meta の dt。この順で書く) */
export const ACT_FIELDS = ["効果", "担当", "期限"];
/** 結論の初心者向け概要 (.overview) の固定4項目。[compose の overview のキー, 表示ラベル] をこの順で置く */
export const OVERVIEW_ITEMS = Object.freeze([
  ["comparison", "対象・比較"],
  ["finding", "数字で分かったこと"],
  ["interpretation", "どう読むか"],
  ["limitation", "言えないこと"],
].map(Object.freeze));

/**
 * 文章量の上限 (認知負荷を上げないための規律)。生成 (compose.mjs) と検査 (check-report.mjs) が共有する正本。
 * prompts/analyst.md「C. 解釈」の字数 (見出し・概要・判断への意味・書き方) と SKILL.md の概要の字数はこの転記
 */
export const LIMITS = {
  h2: 40,        // 見出し = 結論の1文
  line: 60,      // 段落・箇条書き1項目・図の凡例・打ち手の指示・判断への意味
  overview: 48,  // 初心者向け概要 (OVERVIEW_ITEMS) の1項目
  interpretation: 100, // 統計的事実から読めることの1文
  statSub: 48,   // 統計の要約の補足 (kpi-sub) の1文
  howto: 80,     // 「この図の読み方」の1文 (閉じた開閉の中なので line より少し長くて良い)
  glossary: 120, // 用語集の1項目 (何の値か + どう読むか の2文)
  pPerSection: 1,// 段落はセクションに1つまで。それ以上は箇条書きにする
  kpiMin: 1,     // 結論の前提ストリップ (.kpi) の個数。主数字 (.hero-number) は常に1つ
  kpiMax: 3,
  actsMin: 1,    // 打ち手の件数
  actsMax: 5,
  tocLabel: 24,
  smallN: 10,    // n がこれ未満なら「サンプルが少ない」警告 (W05)
};

/** 生成・最終検査で共有する文章契約。片側だけの語彙変更を防ぐ。 */
export const OVERVIEW_JARGON = /p値|p\s*[<=>]|有意(?:差)?|効果量|信頼区間|標準偏差|分散|回帰(?:係数)?|決定係数|R[²2]|相関係数|ジニ係数|IQR|オッズ比|ハザード比|検定/i;
export const TECHNICAL_STAT = /中央値|標準偏差|分散|変動係数|効果量|信頼区間|相関|回帰|決定係数|R[²2]|ジニ係数|IQR|p値|オッズ比|ハザード比/i;

/** 厳格検証で描画・証跡の双方が要求する幅。 */
export const RENDER_WIDTHS = Object.freeze([375, 768, 1280, 1600]);

const IMPACT = /^([+\-−▲])?(\d+(?:\.\d+)?(?:e[+\-]?\d+)?)$/i;

/** Numberの指数表記を小数表記へ展開する。属性serializerと表示精度の計算が共用する。 */
const decimalDigits = (value) => {
  const raw = String(Math.abs(value));
  if (!/e/i.test(raw)) return raw;
  const [mantissa, exponent] = raw.toLowerCase().split("e");
  const [whole, fraction = ""] = mantissa.split(".");
  const digits = whole + fraction, point = whole.length + Number(exponent);
  return point <= 0 ? `0.${"0".repeat(-point)}${digits}`
    : point >= digits.length ? digits + "0".repeat(point - digits.length)
      : `${digits.slice(0, point)}.${digits.slice(point)}`;
};

/** 有限数のdata-impact。生成とparseで往復でき、指数表記でビルドを止めない。 */
export function serializeImpact(value) {
  const number = Number(value);
  if (!Number.isFinite(number)) throw new TypeError(`impact は有限の数値にしてください (${value})`);
  return `${number < 0 ? "-" : ""}${decimalDigits(number)}`;
}

/** data-impactを正規化する。Unicodeマイナスと悪化記号も負数として扱う。 */
export function parseImpact(raw) {
  const match = String(raw ?? "").trim().match(IMPACT);
  if (!match) return null;
  const number = Number(match[2]);
  if (!Number.isFinite(number)) return null;
  const negative = match[1] === "-" || match[1] === "−" || match[1] === "▲";
  return { value: (negative ? -1 : 1) * number, digits: /e/i.test(match[2]) ? decimalDigits(number) : match[2] };
}

/** 通常 build では警告に留め、厳格 done だけが拒否する未確定アクション。 */
export const hasPendingActions = (html) => /<li\b[^>]*class="[^"]*\bact\b[^"]*"[^>]*\bdata-source="pending"/.test(String(html));

/** review.json の機械契約。プロンプトと検査で値を重複定義しない。 */
export const REVIEW_CONDITIONS = Object.freeze(["矛盾なし", "漏れなし", "整合性あり", "依存関係整合"]);
export const REVIEW_VERDICTS = Object.freeze(["PASS", "FAIL"]);
export const REVIEW_SEVERITIES = Object.freeze(["must", "should"]);
export const REVIEW_STATUSES = Object.freeze(["open", "fixed", "accepted"]);
export const REVIEW_FINDING_FIELDS = Object.freeze(["条件", "severity", "status", "箇所", "指摘", "提案"]);
export const REFERENCE_MAX_LINE_LENGTH = 500;
/** 1回の往復でユーザーに聞く質問の上限。レポートの unknowns (prompts/analyst.md) と資料のヒアリング (prompts/handout.md) で共通。転記は selftest が照合する */
export const ASK_LIMIT = 4;

/** レポートの情報量。標準を既定にし、質問待ちで初回生成を止めない。 */
export const DEFAULT_REPORT_DETAIL = "標準";
export const REPORT_DETAILS = Object.freeze({
  要点: Object.freeze({ token: "concise", factorsMax: 2, factsMin: 2, factsMax: 3, statsMin: 2, statsMax: 3 }),
  標準: Object.freeze({ token: "standard", factorsMax: 3, factsMin: 2, factsMax: 5, statsMin: 2, statsMax: 5 }),
  詳細: Object.freeze({ token: "detailed", factorsMax: 5, factsMin: 2, factsMax: 7, statsMin: 2, statsMax: 7 }),
});
export const REPORT_DETAIL_BY_TOKEN = Object.freeze(Object.fromEntries(Object.entries(REPORT_DETAILS).map(([label, value]) => [value.token, { label, ...value }])));

export const isFilled = (value) =>
  Array.isArray(value) ? value.length > 0 : value != null && String(value).trim() !== "";

/**
 * review.json の宣言的な形と、配布する最終 HTML への接続を検査する。
 * 指摘を fixed にした場合も target は必ず最終 HTML の hash に更新する。
 */
export function reviewContractErrors(review, finalHtmlHash) {
  const errors = [];
  if (review?.target !== finalHtmlHash) errors.push("review.target は現在の最終 HTML の sha256 と一致させる");

  const conditions = review?.条件;
  if (!conditions || typeof conditions !== "object" || Array.isArray(conditions)) {
    errors.push("review.条件 は4条件の判定を持つオブジェクトにする");
  } else {
    for (const condition of REVIEW_CONDITIONS) {
      if (!(condition in conditions)) errors.push(`review.条件.${condition} がありません`);
      else if (!REVIEW_VERDICTS.includes(conditions[condition])) errors.push(`review.条件.${condition} は ${REVIEW_VERDICTS.join(" か ")} にする`);
      else if (conditions[condition] !== "PASS") errors.push(`review.条件.${condition} が FAIL です。最終 HTML を改善して全4条件を PASS にする`);
    }
    for (const condition of Object.keys(conditions)) {
      if (!REVIEW_CONDITIONS.includes(condition)) errors.push(`review.条件.${condition} は未知の条件です`);
    }
  }

  if (!Array.isArray(review?.findings)) {
    errors.push("review.findings が配列ではありません");
    return errors;
  }
  for (const [index, finding] of review.findings.entries()) {
    const at = `指摘 ${index + 1}`;
    if (!finding || typeof finding !== "object" || Array.isArray(finding)) {
      errors.push(`${at}: オブジェクトではありません`);
      continue;
    }
    for (const field of REVIEW_FINDING_FIELDS) if (!isFilled(finding[field])) errors.push(`${at}: ${field} が空です`);
    if (isFilled(finding.条件) && !REVIEW_CONDITIONS.includes(finding.条件)) errors.push(`${at}: 条件は ${REVIEW_CONDITIONS.join(" / ")} のどれか`);
    if (isFilled(finding.severity) && !REVIEW_SEVERITIES.includes(finding.severity)) errors.push(`${at}: severity は ${REVIEW_SEVERITIES.join(" か ")}`);
    if (isFilled(finding.status) && !REVIEW_STATUSES.includes(finding.status)) errors.push(`${at}: status は ${REVIEW_STATUSES.join(" / ")} のどれか`);
    if (finding.severity === "must" && finding.status === "open") errors.push(`${at}: 未解決の must です。fixed か accepted にする — ${finding.指摘 || "指摘なし"}`);
  }
  return errors;
}

/** data-impact と results.steps の数値照合。小数指標を誤受理しない小さな計算誤差だけを許す。 */
export const IMPACT_ABSOLUTE_TOLERANCE = 1e-9;
export const IMPACT_RELATIVE_TOLERANCE = 1e-9;
export const nearlyEqual = (actual, expected, absolute = IMPACT_ABSOLUTE_TOLERANCE, relative = IMPACT_RELATIVE_TOLERANCE) =>
  Number.isFinite(actual) && Number.isFinite(expected)
  && Math.abs(actual - expected) <= absolute + relative * Math.max(Math.abs(actual), Math.abs(expected));
