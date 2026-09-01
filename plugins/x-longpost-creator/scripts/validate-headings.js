#!/usr/bin/env node
/**
 * validate-headings.js - 見出し構造の絶対ルール検証（決定論的処理）
 *
 * 長文Aパターン（文脈改行型）の見出し構造が
 * prompts/x-longpost-optimize-length.md §4.2 の絶対ルールを満たすか検証する。
 *
 * 検証項目:
 *   H1  先頭の非空行が見出し1（# ）で始まる
 *   H2  見出し1は本文中にちょうど1つ
 *   H3  見出し1のタイトルが50文字以内
 *   H4  見出し1の後に見出し2（## ）が必ず1つ以上存在する
 *   H4b 見出し1と最初の見出し2の間はリード文のみ（見出しを挟まず、空行を除き最大行数以内）
 *   H5  見出し2が3〜8個ある（デフォルトは警告のみ。--strict-h2-count でFAIL扱い）
 *   H6  見出しに絵文字が含まれない
 *   H7  見出し3以下（###）を使っていない
 *   H8  見出し1が --title と完全一致する（--text 使用時は --title 必須。--allow-no-title で省略可）
 *   H9  見出し2の長さが12〜28字の範囲内（範囲外は警告）
 *   H10 見出し2が構成の役割名そのものになっていない（references/heading-title-guide.md のNG役割名）
 *
 * --file でファイル全体を渡した場合の追加検証:
 *   F1  Bパターン先頭行が見出し1のタイトルと完全一致する
 *   F2  `# タイトル` セクションの値が見出し1のタイトルと完全一致する
 *   F3  ファイル名のタイトル部が見出し1のタイトル（サニタイズ後）と完全一致する
 *   F4  Markdown 見出しを除いた A 本文と、先頭タイトルを除いた B 本文が空白正規化後に同値
 *   F5  B の非空本文行が1行につきちょうど1文
 *
 * 使用例:
 *   node scripts/validate-headings.js --file "/path/to/X長文投稿-prompt作成 - 2026-08-11_タイトル.md"
 *   node scripts/validate-headings.js --text "$(cat body.txt)" --title "タイトル"
 *
 * 終了コード: 0 = 全項目PASS / 1 = FAILあり / 2 = 引数エラー / 3 = ファイル入出力エラー
 */

const fs = require("fs");
const path = require("path");
const { findEmoji } = require("./lib/text-rules.js");

const EXIT_PASS = 0;
const EXIT_FAIL = 1;
const EXIT_ARGS_ERROR = 2;
const EXIT_FILE_ERROR = 3;

const DEFAULT_MAX_TITLE_CHARS = 50;
const DEFAULT_MIN_H2 = 3;
const DEFAULT_MAX_H2 = 8;
// 見出し1と最初の見出し2の間に置けるリード文（冒頭フック）の最大行数・最大文字数
const DEFAULT_MAX_LEAD_LINES = 8;
const DEFAULT_MAX_LEAD_CHARS = 300;
// 見出し2の推奨長（範囲外は警告）
const DEFAULT_MIN_H2_CHARS = 12;
const DEFAULT_MAX_H2_CHARS = 28;

// references/heading-title-guide.md「避けるべき汎用的なタイトル」および
// 「セクション別タイトル作成例」の NG に列挙された役割名のみ（推測で追加しない）
const NG_ROLE_HEADINGS = [
  "問いかけ",
  "理想の状態",
  "現状の問題",
  "原因分析",
  "このままだと",
  "最悪の未来",
  "解決策",
  "まとめ",
];

const FILENAME_PREFIX = "X長文投稿-prompt作成 - ";

function showHelp() {
  console.log(`
Usage: node validate-headings.js (--file <path> | --text <string>) [options]

Options:
  --file <path>       検証対象の生成ファイル（Aパターンのコードブロックを自動抽出）
  --text <string>     Aパターン本文を直接渡す（--file との排他）
  --title <string>    期待する見出し1タイトル（--text 使用時は必須）
  --allow-no-title    --text 使用時に --title の指定を省略する（H8は判定しない）
  --max-title <n>     見出し1の最大文字数（デフォルト: ${DEFAULT_MAX_TITLE_CHARS}）
  --min-h2 <n>        見出し2の最小個数（デフォルト: ${DEFAULT_MIN_H2}）
  --max-h2 <n>        見出し2の最大個数（デフォルト: ${DEFAULT_MAX_H2}）
  --min-h2-chars <n>  見出し2の最小文字数（デフォルト: ${DEFAULT_MIN_H2_CHARS}・警告）
  --max-h2-chars <n>  見出し2の最大文字数（デフォルト: ${DEFAULT_MAX_H2_CHARS}・警告）
  --strict-h2-count   見出し2の個数を警告でなくFAIL扱いにする
  --strict-adjacent   見出し1の直後（リード文なし）に見出し2を強制する
  --max-lead-lines <n> リード文の最大行数（デフォルト: ${DEFAULT_MAX_LEAD_LINES}）
  --max-lead-chars <n> リード文の最大文字数（デフォルト: ${DEFAULT_MAX_LEAD_CHARS}）
  -h, --help          このヘルプを表示

終了コード: 0 = PASS / 1 = FAIL / 2 = 引数エラー / 3 = ファイルエラー
`);
}

function parseArgs(argv) {
  const result = {
    maxTitle: DEFAULT_MAX_TITLE_CHARS,
    minH2: DEFAULT_MIN_H2,
    maxH2: DEFAULT_MAX_H2,
    maxLeadLines: DEFAULT_MAX_LEAD_LINES,
    maxLeadChars: DEFAULT_MAX_LEAD_CHARS,
    minH2Chars: DEFAULT_MIN_H2_CHARS,
    maxH2Chars: DEFAULT_MAX_H2_CHARS,
    strictH2Count: false,
    strictAdjacent: false,
    allowNoTitle: false,
  };
  for (let i = 2; i < argv.length; i++) {
    if (argv[i] === "-h" || argv[i] === "--help") result.help = true;
    else if (argv[i] === "--file" && argv[i + 1] !== undefined) result.file = argv[++i];
    else if (argv[i] === "--text" && argv[i + 1] !== undefined) result.text = argv[++i];
    else if (argv[i] === "--title" && argv[i + 1] !== undefined) result.title = argv[++i];
    else if (argv[i] === "--max-title" && argv[i + 1] !== undefined) result.maxTitle = parseInt(argv[++i], 10);
    else if (argv[i] === "--min-h2" && argv[i + 1] !== undefined) result.minH2 = parseInt(argv[++i], 10);
    else if (argv[i] === "--max-h2" && argv[i + 1] !== undefined) result.maxH2 = parseInt(argv[++i], 10);
    else if (argv[i] === "--max-lead-lines" && argv[i + 1] !== undefined) result.maxLeadLines = parseInt(argv[++i], 10);
    else if (argv[i] === "--max-lead-chars" && argv[i + 1] !== undefined) result.maxLeadChars = parseInt(argv[++i], 10);
    else if (argv[i] === "--min-h2-chars" && argv[i + 1] !== undefined) result.minH2Chars = parseInt(argv[++i], 10);
    else if (argv[i] === "--max-h2-chars" && argv[i + 1] !== undefined) result.maxH2Chars = parseInt(argv[++i], 10);
    else if (argv[i] === "--allow-no-title") result.allowNoTitle = true;
    else if (argv[i] === "--strict-h2-count") result.strictH2Count = true;
    else if (argv[i] === "--strict-adjacent") result.strictAdjacent = true;
  }
  return result;
}

function countChars(text) {
  // NFD 保存（macOS の濁点分解）でも同じ文字数になるよう NFC へ正規化してから数える
  return [...text.normalize("NFC")].length;
}

/** generate-filename.js の sanitizeTitle と同一ロジック */
function sanitizeTitle(title) {
  return title.replace(/[\\/:*?"<>|]/g, "").replace(/\s+/g, "_");
}

/**
 * 指定見出し直後のフェンス付きコードブロック本体を取り出す。
 * 見つからない場合は null。
 */
function extractCodeBlockAfter(fileText, headingRe) {
  const lines = fileText.split("\n");
  let start = -1;
  for (let i = 0; i < lines.length; i++) {
    if (headingRe.test(lines[i])) { start = i; break; }
  }
  if (start === -1) return null;

  let fenceStart = -1;
  for (let i = start + 1; i < lines.length; i++) {
    if (/^```/.test(lines[i])) { fenceStart = i; break; }
    // 次の見出しに到達したらコードブロックなしと判断
    if (/^#{1,2}\s/.test(lines[i])) return null;
  }
  if (fenceStart === -1) return null;

  const body = [];
  for (let i = fenceStart + 1; i < lines.length; i++) {
    if (/^```/.test(lines[i])) return body.join("\n");
    body.push(lines[i]);
  }
  return null;
}

/** `# タイトル` セクション直下の `- 値` を取り出す */
function extractTitleSection(fileText) {
  const lines = fileText.split("\n");
  for (let i = 0; i < lines.length; i++) {
    if (/^#\s*タイトル\s*$/.test(lines[i])) {
      for (let j = i + 1; j < lines.length; j++) {
        const line = lines[j];
        if (line.trim() === "") continue;
        if (/^#{1,6}\s/.test(line)) return null;
        const m = line.match(/^-\s+(.*\S)\s*$/);
        return m ? m[1] : null;
      }
      return null;
    }
  }
  return null;
}

/** ファイル名からタイトル部（`_` 以降・拡張子除く）を取り出す */
function extractFilenameTitle(filePath) {
  const base = path.basename(filePath, ".md");
  if (!base.startsWith(FILENAME_PREFIX)) return null;
  const rest = base.slice(FILENAME_PREFIX.length);
  const m = rest.match(/^\d{4}-\d{2}-\d{2}_(.+)$/);
  return m ? m[1] : null;
}

/** 改行形式の差だけを無視するため、Unicode と空白を正規化する。 */
function normalizeComparableBody(text) {
  return String(text).normalize("NFC").replace(/\s+/gu, "");
}

/** A の表示用 Markdown 見出しを除き、本文だけを比較可能な形にする。 */
function extractComparableABody(aBody) {
  return normalizeComparableBody(
    String(aBody)
      .split("\n")
      .filter(line => !/^#{1,6}\s+\S/u.test(line.trim()))
      .join("\n")
  );
}

/** B の先頭非空行（確定タイトル）を除き、本文行を返す。 */
function extractBBodyLines(bBody) {
  const lines = String(bBody).split("\n");
  const titleIndex = lines.findIndex(line => line.trim() !== "");
  return titleIndex === -1 ? [] : lines.slice(titleIndex + 1);
}

/**
 * B の1行が「ちょうど1文」かを判定する。
 * `!?` のような連続終端記号は1組として扱い、閉じ括弧・閉じ引用符は文末に許可する。
 */
function isSingleSentenceLine(line) {
  const text = String(line).normalize("NFC").trim();
  if (text === "") return true;
  let terminatorGroups = 0;
  let previousWasTerminator = false;
  for (let index = 0; index < text.length; index++) {
    const character = text[index];
    let isTerminator = /[。！？!?]/u.test(character);
    if (character === "." || character === "．") {
      const previous = text[index - 1] || "";
      const next = text[index + 1] || "";
      const decimalPoint = /[0-9０-９]/u.test(previous) && /[0-9０-９]/u.test(next);
      const sentencePosition = next === "" || /\s|[」』）】〕〉》”’"')\]]/u.test(next);
      isTerminator = !decimalPoint && sentencePosition;
    }
    if (isTerminator && !previousWasTerminator) terminatorGroups++;
    previousWasTerminator = isTerminator;
  }
  return terminatorGroups === 1
    && /[。！？!?．.]+[」』）】〕〉》”’"')\]]*$/u.test(text);
}

function analyzeBody(body, opts) {
  const lines = body.split("\n");
  const checks = [];

  // 見出し行の収集（コードフェンス内は対象外だが、本文自体がブロック内なので単純走査で足りる）
  const headings = [];
  lines.forEach((line, i) => {
    const m = line.match(/^(#{1,6})\s+(.*\S)\s*$/);
    if (m) headings.push({ line: i + 1, level: m[1].length, text: m[2] });
  });

  const firstNonEmptyIndex = lines.findIndex(l => l.trim() !== "");
  const firstNonEmpty = firstNonEmptyIndex === -1 ? "" : lines[firstNonEmptyIndex];
  const h1s = headings.filter(h => h.level === 1);
  const h2s = headings.filter(h => h.level === 2);
  const deep = headings.filter(h => h.level >= 3);

  const startsWithH1 = /^#\s+\S/.test(firstNonEmpty);
  checks.push({
    id: "H1",
    name: "先頭が見出し1",
    ok: startsWithH1,
    detail: startsWithH1 ? `先頭行: ${firstNonEmpty}` : `先頭の非空行が見出し1ではない: ${firstNonEmpty || "(本文が空)"}`,
  });

  checks.push({
    id: "H2",
    name: "見出し1は1つ",
    ok: h1s.length === 1,
    detail: `見出し1の個数: ${h1s.length}`,
  });

  const title = h1s.length > 0 ? h1s[0].text : null;
  const titleLength = title === null ? 0 : countChars(title);
  checks.push({
    id: "H3",
    name: "見出し1が50文字以内",
    ok: title !== null && titleLength <= opts.maxTitle,
    detail: title === null
      ? "見出し1が存在しない"
      : `${titleLength}文字 / 上限${opts.maxTitle}文字`,
  });

  // H4: 見出し1の後に見出し2が必ず存在すること（絶対ルール）
  const h1Line = h1s.length > 0 ? h1s[0].line : null;
  const firstH2 = h1Line === null ? null : (h2s.find(h => h.line > h1Line) || null);
  checks.push({
    id: "H4",
    name: "見出し1の後に見出し2が存在",
    ok: firstH2 !== null,
    detail: h1Line === null
      ? "見出し1が存在しない"
      : firstH2 === null
        ? "見出し1の後に見出し2（##）が1つも存在しない"
        : `最初の見出し2: ${firstH2.text}`,
  });

  // H4b: 見出し1と最初の見出し2の間はリード文（冒頭フック）のみ
  let lead = [];
  let leadHasHeading = false;
  if (h1Line !== null && firstH2 !== null) {
    const between = lines.slice(h1Line, firstH2.line - 1);
    lead = between.filter(l => l.trim() !== "");
    leadHasHeading = lead.some(l => /^#{1,6}\s/.test(l));
  }
  const leadChars = countChars(lead.join(""));
  // H4 未達（見出し2がゼロ）のときは H4b を skipped 扱いにし、本質的な指摘（H4）を埋もれさせない
  const leadSkipped = firstH2 === null;
  const leadOk = leadSkipped
    ? true
    : !leadHasHeading
      && (opts.strictAdjacent ? lead.length === 0 : lead.length <= opts.maxLeadLines && leadChars <= opts.maxLeadChars);
  checks.push({
    id: "H4b",
    name: opts.strictAdjacent
      ? "見出し1の直後が見出し2（リード文なし）"
      : `見出し1と最初の見出し2の間はリード文のみ（${opts.maxLeadLines}行・${opts.maxLeadChars}字以内）`,
    ok: leadOk,
    ...(leadSkipped ? { severity: "skipped" } : {}),
    detail: leadSkipped
      ? "見出し2が存在しないため判定をスキップ（H4を先に解消する）"
      : leadHasHeading
        ? "リード文に見出しが混入している"
        : `リード文 ${lead.length}行 / ${leadChars}文字`,
  });

  const h2CountOk = h2s.length >= opts.minH2 && h2s.length <= opts.maxH2;
  checks.push({
    id: "H5",
    name: `見出し2が${opts.minH2}〜${opts.maxH2}個`,
    // 「3〜8個」は目安のため、デフォルトは警告扱い
    ok: opts.strictH2Count ? h2CountOk : true,
    severity: h2CountOk ? "info" : "warning",
    detail: h2CountOk
      ? `見出し2の個数: ${h2s.length}`
      : `見出し2の個数: ${h2s.length}（目安${opts.minH2}〜${opts.maxH2}個から外れている${opts.strictH2Count ? "" : "・警告"}）`,
  });

  const emojiHeadings = headings
    .filter(h => findEmoji(h.text).length > 0)
    .map(h => `L${h.line}: ${h.text}`);
  checks.push({
    id: "H6",
    name: "見出しに絵文字なし",
    ok: emojiHeadings.length === 0,
    detail: emojiHeadings.length === 0 ? "絵文字なし" : `絵文字あり: ${emojiHeadings.join(" / ")}`,
  });

  checks.push({
    id: "H7",
    name: "見出し3以下を使わない",
    ok: deep.length === 0,
    detail: deep.length === 0 ? "見出し3以下なし" : `検出: ${deep.map(h => `L${h.line}: ${"#".repeat(h.level)} ${h.text}`).join(" / ")}`,
  });

  if (typeof opts.title === "string") {
    const expectedTitle = opts.title.normalize("NFC").trim();
    const actualTitle = title === null ? null : title.normalize("NFC");
    checks.push({
      id: "H8",
      name: "見出し1が指定タイトルと一致",
      ok: actualTitle === expectedTitle,
      detail: actualTitle === expectedTitle
        ? "一致"
        : `見出し1「${title}」 / 指定「${opts.title.trim()}」`,
    });
  }

  // H9: 見出し2の長さ（範囲外は警告。FAILにはしない）
  const h2LengthOut = h2s
    .map(h => ({ ...h, len: countChars(h.text) }))
    .filter(h => h.len < opts.minH2Chars || h.len > opts.maxH2Chars);
  checks.push({
    id: "H9",
    name: `見出し2の長さが${opts.minH2Chars}〜${opts.maxH2Chars}字`,
    ok: true,
    severity: h2LengthOut.length === 0 ? "info" : "warning",
    detail: h2LengthOut.length === 0
      ? `見出し2 ${h2s.length}件はすべて${opts.minH2Chars}〜${opts.maxH2Chars}字`
      : `範囲外 ${h2LengthOut.length}件: ${h2LengthOut.map(h => `L${h.line}(${h.len}字): ${h.text}`).join(" / ")}`,
  });

  // H10: 見出し2が構成の役割名そのもの（NG役割名と完全一致）になっていないか
  const roleHeadings = h2s.filter(h => NG_ROLE_HEADINGS.includes(h.text.normalize("NFC").trim()));
  checks.push({
    id: "H10",
    name: "見出し2が役割名そのものでない",
    ok: roleHeadings.length === 0,
    detail: roleHeadings.length === 0
      ? "役割名の見出しなし"
      : `役割名の見出し: ${roleHeadings.map(h => `L${h.line}: ${h.text}`).join(" / ")}（references/heading-title-guide.md の具体的なタイトルへ書き換える）`,
  });

  return { checks, title, h2Count: h2s.length, headings };
}

function main() {
  const args = parseArgs(process.argv);

  if (args.help) {
    showHelp();
    process.exit(EXIT_PASS);
  }

  if (!args.file && typeof args.text !== "string") {
    console.error(JSON.stringify({ error: "--file <path> または --text <string> を指定してください" }));
    showHelp();
    process.exit(EXIT_ARGS_ERROR);
  }

  if (args.file && typeof args.text === "string") {
    console.error(JSON.stringify({ error: "--file と --text は同時に指定できません" }));
    process.exit(EXIT_ARGS_ERROR);
  }

  // H8 を実効化する: --text 使用時は --title を必須にする（4箇所一致の唯一の破れ口を塞ぐ）
  if (typeof args.text === "string" && typeof args.title !== "string" && !args.allowNoTitle) {
    console.error(JSON.stringify({
      error: "--text 使用時は --title <string> が必須です（H8: 見出し1と確定タイトルの一致検証）",
      hint: "従来どおり --title なしで実行する場合は --allow-no-title を付けてください",
    }));
    process.exit(EXIT_ARGS_ERROR);
  }

  const numericArgs = [
    ["--max-title", args.maxTitle, 1],
    ["--min-h2", args.minH2, 1],
    ["--max-h2", args.maxH2, 1],
    ["--min-h2-chars", args.minH2Chars, 1],
    ["--max-h2-chars", args.maxH2Chars, 1],
    ["--max-lead-lines", args.maxLeadLines, 0],
    ["--max-lead-chars", args.maxLeadChars, 0],
  ];
  for (const [key, value, min] of numericArgs) {
    if (!Number.isInteger(value) || value < min) {
      console.error(JSON.stringify({ error: `${key} は${min}以上の整数で指定してください` }));
      process.exit(EXIT_ARGS_ERROR);
    }
  }

  let body;
  let fileText = null;
  const extraChecks = [];

  if (args.file) {
    try {
      fileText = fs.readFileSync(args.file, "utf8");
    } catch (err) {
      console.error(JSON.stringify({ error: `ファイルを読み込めません: ${args.file}`, message: err.message }));
      process.exit(EXIT_FILE_ERROR);
    }
    body = extractCodeBlockAfter(fileText, /^##\s*Aパターン/);
    if (body === null) {
      console.error(JSON.stringify({
        error: "`## Aパターン（文脈改行型）` 直後のコードブロックを抽出できません",
        hint: "assets/output-template.md の構造に一致しているか確認する",
      }));
      process.exit(EXIT_FILE_ERROR);
    }
  } else {
    body = args.text;
  }

  const analysis = analyzeBody(body, {
    maxTitle: args.maxTitle,
    minH2: args.minH2,
    maxH2: args.maxH2,
    maxLeadLines: args.maxLeadLines,
    maxLeadChars: args.maxLeadChars,
    minH2Chars: args.minH2Chars,
    maxH2Chars: args.maxH2Chars,
    strictH2Count: args.strictH2Count,
    strictAdjacent: args.strictAdjacent,
    title: args.title,
  });

  // ファイル全体を渡した場合の一貫性検証
  if (fileText !== null) {
    const title = analysis.title;

    const bBody = extractCodeBlockAfter(fileText, /^##\s*Bパターン/);
    const bFirst = bBody === null ? null : (bBody.split("\n").find(l => l.trim() !== "") || "").trim();
    extraChecks.push({
      id: "F1",
      name: "Bパターン先頭行が見出し1と一致",
      ok: bFirst !== null && title !== null && bFirst === title,
      detail: bBody === null
        ? "Bパターンのコードブロックを抽出できない"
        : `Bパターン先頭「${bFirst}」 / 見出し1「${title}」`,
    });

    const titleSection = extractTitleSection(fileText);
    extraChecks.push({
      id: "F2",
      name: "`# タイトル` セクションが見出し1と一致",
      ok: titleSection !== null && title !== null && titleSection === title,
      detail: titleSection === null
        ? "`# タイトル` セクションの値を抽出できない"
        : `セクション「${titleSection}」 / 見出し1「${title}」`,
    });

    // macOS は NFD で保存することがあるため、ファイル名と見出し1を NFC 同士で比較する
    const rawFilenameTitle = extractFilenameTitle(args.file);
    const filenameTitle = rawFilenameTitle === null ? null : rawFilenameTitle.normalize("NFC");
    const expected = title === null ? null : sanitizeTitle(title).normalize("NFC");
    extraChecks.push({
      id: "F3",
      name: "ファイル名のタイトル部が見出し1と一致",
      ok: filenameTitle !== null && expected !== null && filenameTitle === expected,
      detail: filenameTitle === null
        ? `ファイル名が命名規則（${FILENAME_PREFIX}YYYY-MM-DD_タイトル.md）に一致しない`
        : `ファイル名「${filenameTitle}」 / 見出し1（サニタイズ後）「${expected}」`,
    });

    const bBodyLines = bBody === null ? [] : extractBBodyLines(bBody);
    const normalizedA = extractComparableABody(body);
    const normalizedB = normalizeComparableBody(bBodyLines.join("\n"));
    extraChecks.push({
      id: "F4",
      name: "A/B本文が空白・改行正規化後に同値",
      ok: bBody !== null && normalizedA === normalizedB,
      detail: bBody === null
        ? "Bパターンのコードブロックを抽出できない"
        : normalizedA === normalizedB
          ? `一致（正規化後 ${countChars(normalizedA)}文字）`
          : `不一致（A ${countChars(normalizedA)}文字 / B ${countChars(normalizedB)}文字）`,
    });

    const invalidBLines = bBodyLines
      .map((line, index) => ({ line, lineNumber: index + 2 }))
      .filter(item => item.line.trim() !== "" && !isSingleSentenceLine(item.line));
    extraChecks.push({
      id: "F5",
      name: "B本文が1文1行",
      ok: bBody !== null && invalidBLines.length === 0 && bBodyLines.some(line => line.trim() !== ""),
      detail: bBody === null
        ? "Bパターンのコードブロックを抽出できない"
        : invalidBLines.length > 0
          ? `1文1行でない本文行: ${invalidBLines.map(item => `B内L${item.lineNumber}: ${item.line.trim()}`).join(" / ")}`
          : bBodyLines.some(line => line.trim() !== "")
            ? "すべての非空本文行が1文"
            : "Bパターンの本文が空",
    });
  }

  const checks = [...analysis.checks, ...extraChecks];
  const failed = checks.filter(c => !c.ok);
  const warnings = checks.filter(c => c.ok && c.severity === "warning");

  const result = {
    ok: failed.length === 0,
    source: args.file ? { file: args.file } : { text: true },
    title: analysis.title,
    titleLength: analysis.title === null ? 0 : countChars(analysis.title),
    h2Count: analysis.h2Count,
    checks,
    failed: failed.map(c => `${c.id} ${c.name}: ${c.detail}`),
    warnings: warnings.map(c => `${c.id} ${c.name}: ${c.detail}`),
    nextAction: failed.length === 0
      ? null
      : "FAIL項目を修正してから再実行する。H3はタイトルを50文字以内へリライト、H4は見出し1の後に見出し2を必ず置く、H10は役割名の見出しを内容の核心を表す具体的な見出しへ書き換える。F4はA/Bの本文内容を一致させ、F5はB本文を1文1行へ直す。PASSするまで出力を確定しない。",
  };

  console.log(JSON.stringify(result, null, 2));
  process.exit(result.ok ? EXIT_PASS : EXIT_FAIL);
}

main();
