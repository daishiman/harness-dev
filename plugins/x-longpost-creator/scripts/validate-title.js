#!/usr/bin/env node
/**
 * validate-title.js - 見出し1タイトルの絶対ルール検証（決定論的処理）
 *
 * 見出し1（# タイトル）に使うタイトル文字列が、
 * ${CLAUDE_PLUGIN_ROOT}/references/title-guidelines.md §3.4 の絶対ルールを満たすか検証する。
 * このタイトルはそのままファイル名のタイトル部にもなるため、
 * ファイル名として安全であることも同時に検証する。
 *
 * 検証項目:
 *   T1 文字数    50文字以内（コードポイント数・空白含む）
 *   T2 非空      前後の空白を除いて1文字以上
 *   T3 単一行    改行を含まない
 *   T4 絵文字    絵文字（Extended_Pictographic）を含まない
 *   T5 禁止表現  「〜した話」型など title-guidelines §3.3 の禁止表現を含まない
 *   T6 ファイル名 ファイル名に使えない文字（\ / : * ? " < > |）を含まない
 *
 * 使用例:
 *   node scripts/validate-title.js --title "プロンプトが思い通りに動かない。原因は前提の省略"
 *   node scripts/validate-title.js --title "..." --max 50
 *
 * 終了コード: 0 = 全項目PASS / 1 = FAILあり / 2 = 引数エラー
 */

const EXIT_PASS = 0;
const EXIT_FAIL = 1;
const EXIT_ARGS_ERROR = 2;
const { findEmoji } = require("./lib/text-rules.js");

const DEFAULT_MAX_CHARS = 50;

// title-guidelines.md §3.3 / create-title.md §9 の禁止表現
const FORBIDDEN_PATTERNS = [
  // 一般形: 動詞連体形（〜た/〜だ）＋「話」。「決めた話」「気づいた話」なども検出する。
  // 「昔話」「小話」のように直前が「た/だ」でない語は対象外。
  { pattern: /[^\s]{1,12}(た|だ)話(?=$|[。、])/, label: "「動詞連体形＋話」型（〜した話・〜決めた話など）" },
  { pattern: /した話$|した話[。、]/, label: "「〜した話」型" },
  { pattern: /作った話/, label: "「〜を作った話」型" },
  { pattern: /してみた話/, label: "「〜してみた話」型" },
  { pattern: /になった話/, label: "「〜になった話」型" },
  { pattern: /だった話/, label: "「〜だった話」型" },
  { pattern: /理想はこんな状態/, label: "「理想はこんな状態です」" },
  { pattern: /このまま放置すると/, label: "「このまま放置するとどうなるか」" },
  { pattern: /最悪のパターン/, label: "「最悪のパターンは」" },
  { pattern: /最悪な未来/, label: "「さらに最悪な未来は」" },
  { pattern: /と感じたことはありませんか/, label: "「〜と感じたことはありませんか？」" },
  { pattern: /(前編|後編|Vol\.\s*\d|第\s*\d+\s*回)/, label: "シリーズ物表現（前編/後編/Vol.N/第N回）" },
];

const FILENAME_NG_CHARS = /[\\/:*?"<>|]/g;

function showHelp() {
  console.log(`
Usage: node validate-title.js --title <string> [options]

Options:
  --title <string>   検証対象のタイトル（必須）
  --max <number>     最大文字数（デフォルト: ${DEFAULT_MAX_CHARS}）
  -h, --help         このヘルプを表示

終了コード: 0 = PASS / 1 = FAIL / 2 = 引数エラー
`);
}

function parseArgs(argv) {
  const result = { max: DEFAULT_MAX_CHARS };
  for (let i = 2; i < argv.length; i++) {
    if (argv[i] === "-h" || argv[i] === "--help") result.help = true;
    else if (argv[i] === "--title" && argv[i + 1] !== undefined) result.title = argv[++i];
    else if (argv[i] === "--max" && argv[i + 1] !== undefined) result.max = parseInt(argv[++i], 10);
  }
  return result;
}

/**
 * コードポイント単位で数える（サロゲートペアを1文字として扱う）
 * macOS は濁点を分解して保存（NFD）することがあるため、NFC へ正規化してから数える。
 */
function countChars(text) {
  return [...text.normalize("NFC")].length;
}

function validateTitle(rawTitle, maxChars) {
  // NFC へ正規化してから検証する（NFD 入力でも同じ判定になるようにする）
  const title = rawTitle.normalize("NFC").trim();
  const checks = [];

  const length = countChars(title);
  checks.push({
    id: "T1",
    name: "文字数",
    ok: length <= maxChars,
    detail: `${length}文字 / 上限${maxChars}文字`,
    ...(length > maxChars ? { over: length - maxChars } : {}),
  });

  checks.push({
    id: "T2",
    name: "非空",
    ok: length > 0,
    detail: length > 0 ? "1文字以上" : "空文字",
  });

  checks.push({
    id: "T3",
    name: "単一行",
    ok: !/[\r\n]/.test(rawTitle),
    detail: /[\r\n]/.test(rawTitle) ? "改行が含まれている" : "改行なし",
  });

  const emoji = findEmoji(title);
  checks.push({
    id: "T4",
    name: "絵文字なし",
    ok: emoji.length === 0,
    detail: emoji.length === 0 ? "絵文字なし" : `絵文字あり: ${emoji.join(" ")}`,
  });

  const forbidden = FORBIDDEN_PATTERNS.filter(f => f.pattern.test(title)).map(f => f.label);
  checks.push({
    id: "T5",
    name: "禁止表現なし",
    ok: forbidden.length === 0,
    detail: forbidden.length === 0 ? "禁止表現なし" : `検出: ${forbidden.join(" / ")}`,
  });

  const ngChars = title.match(FILENAME_NG_CHARS) || [];
  checks.push({
    id: "T6",
    name: "ファイル名安全",
    ok: ngChars.length === 0,
    detail: ngChars.length === 0
      ? "ファイル名に使えない文字なし"
      : `使用不可文字: ${[...new Set(ngChars)].join(" ")}`,
  });

  const failed = checks.filter(c => !c.ok);

  return {
    ok: failed.length === 0,
    title,
    length,
    maxChars,
    checks,
    failed: failed.map(c => `${c.id} ${c.name}: ${c.detail}`),
    // FAIL時の次アクション（LLMへの指示）
    nextAction: failed.length === 0
      ? null
      : "${CLAUDE_PLUGIN_ROOT}/references/title-guidelines.md の構文パターンA〜Hに沿ってタイトルを作り直す。末尾の切り捨てではなく、前半30文字のホリゾンタル入口を維持したまま後半を圧縮する。",
  };
}

function main() {
  const args = parseArgs(process.argv);

  if (args.help) {
    showHelp();
    process.exit(EXIT_PASS);
  }

  if (typeof args.title !== "string") {
    console.error(JSON.stringify({ error: "--title <string> を指定してください" }));
    showHelp();
    process.exit(EXIT_ARGS_ERROR);
  }

  if (!Number.isInteger(args.max) || args.max <= 0) {
    console.error(JSON.stringify({ error: "--max は正の整数で指定してください" }));
    process.exit(EXIT_ARGS_ERROR);
  }

  const result = validateTitle(args.title, args.max);
  console.log(JSON.stringify(result, null, 2));
  process.exit(result.ok ? EXIT_PASS : EXIT_FAIL);
}

main();
