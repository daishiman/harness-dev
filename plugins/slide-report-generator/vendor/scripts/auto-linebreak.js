#!/usr/bin/env node
/**
 * 自動改行挿入スクリプト
 *
 * テキスト要素に<br>タグを自動挿入して可読性を向上:
 * - 1行30-40文字を目安に改行
 * - 句読点・助詞を考慮した自然な改行位置
 * - スライドタイプ別の最適化
 *
 * 使用方法:
 *   node scripts/auto-linebreak.js <html-file-path> [options]
 *
 * オプション:
 *   --dry-run   変更せずに提案のみ表示
 *   --fix       改行を自動挿入して上書き保存
 *   --json      JSON形式で結果を出力
 *   --max-chars 1行の最大文字数（デフォルト: 35）
 *   --help      ヘルプを表示
 *
 * 例:
 *   node scripts/auto-linebreak.js ./index.html --dry-run
 *   node scripts/auto-linebreak.js ./index.html --fix
 */

import { readFileSync, writeFileSync, existsSync } from 'fs';
import { parseArgs, hasFlag, EXIT_CODES } from './utils.js';

// コマンドライン引数
const { flags, positional, options } = parseArgs();

const showHelp = hasFlag(flags, 'help', 'h');
const dryRun = hasFlag(flags, 'dry-run');
const autoFix = hasFlag(flags, 'fix');
const jsonOutput = hasFlag(flags, 'json');
const maxChars = parseInt(options['max-chars'] || '35', 10);
const htmlPath = positional[0];

// ヘルプ表示
if (showHelp) {
  console.log(`
自動改行挿入スクリプト

使用方法:
  node auto-linebreak.js <html-file-path> [options]

オプション:
  --dry-run       変更せずに提案のみ表示（デフォルト）
  --fix           改行を自動挿入して上書き保存
  --json          JSON形式で結果を出力
  --max-chars=N   1行の最大文字数（デフォルト: 35）
  --help          ヘルプを表示

対象要素:
  - h1, h2, h3（タイトル系）
  - p, li（本文系）
  - span.step-text, span.flow-text（フロー図解）
  - .card-title, .card-desc（カード系）

改行ルール:
  1. 句読点（。、！？）の後で優先的に改行
  2. 助詞（は、が、を、に、で、と）の後で改行可
  3. 指定文字数を超えたら強制改行
  4. 既存の<br>は保持

例:
  node auto-linebreak.js ./index.html --dry-run
  node auto-linebreak.js ./index.html --fix --max-chars=30
`);
  process.exit(EXIT_CODES.SUCCESS);
}

// 入力チェック
if (!htmlPath) {
  console.error('❌ HTMLファイルパスを指定してください');
  console.error('   例: node auto-linebreak.js ./index.html --dry-run');
  process.exit(EXIT_CODES.ARGS_ERROR);
}

if (!existsSync(htmlPath)) {
  console.error(`❌ ファイルが見つかりません: ${htmlPath}`);
  process.exit(EXIT_CODES.FILE_NOT_FOUND);
}

// 改行候補の優先度（高い順）
const BREAK_PRIORITIES = [
  { pattern: /([。！？])(?!<br>)/g, priority: 100, after: true },      // 句点の後
  { pattern: /([、])(?!<br>)/g, priority: 80, after: true },           // 読点の後
  { pattern: /(ます|です|した|ない)(?!<br>)/g, priority: 70, after: true }, // 文末表現の後
  { pattern: /(は|が|を|に|で|と|も|の)(?!<br>)/g, priority: 50, after: true }, // 助詞の後
  { pattern: /(、|・)(?!<br>)/g, priority: 40, after: true },          // 中黒の後
];

/**
 * テキストに改行を挿入
 */
function insertLineBreaks(text, maxLength = 35) {
  // 既存の<br>を一時的にマーカーに置換
  const brMarker = '\u0000BR\u0000';
  let processed = text.replace(/<br\s*\/?>/gi, brMarker);

  // HTMLタグを除いた純粋なテキスト長を計算
  const plainText = processed.replace(/<[^>]+>/g, '').replace(brMarker, '');

  // 短いテキストは改行不要
  if (plainText.length <= maxLength) {
    return text;
  }

  // 改行位置を決定
  const breaks = [];
  let currentPos = 0;
  let lastBreakPos = 0;

  while (currentPos < processed.length) {
    // 次の改行候補を探す
    const segment = processed.slice(lastBreakPos, lastBreakPos + maxLength + 10);
    let bestBreakPos = -1;
    let bestPriority = 0;

    // 各パターンで改行候補を探す
    for (const rule of BREAK_PRIORITIES) {
      const match = [...segment.matchAll(rule.pattern)];
      for (const m of match) {
        const pos = lastBreakPos + m.index + m[0].length;
        const charsSinceLastBreak = pos - lastBreakPos;

        // 最大文字数の70-110%の範囲で改行
        if (charsSinceLastBreak >= maxLength * 0.7 && charsSinceLastBreak <= maxLength * 1.3) {
          if (rule.priority > bestPriority) {
            bestPriority = rule.priority;
            bestBreakPos = pos;
          }
        }
      }
    }

    // 候補が見つからない場合、強制的に最大文字数で改行
    if (bestBreakPos === -1) {
      const forcePos = lastBreakPos + maxLength;
      if (forcePos < processed.length) {
        bestBreakPos = forcePos;
      } else {
        break;
      }
    }

    if (bestBreakPos > lastBreakPos) {
      breaks.push(bestBreakPos);
      lastBreakPos = bestBreakPos;
    }

    currentPos = lastBreakPos;

    // 無限ループ防止
    if (breaks.length > 20) break;
  }

  // 改行を挿入（後ろから挿入して位置ズレを防ぐ）
  let result = processed;
  for (let i = breaks.length - 1; i >= 0; i--) {
    const pos = breaks[i];
    if (pos < result.length && !result.slice(pos, pos + 10).includes(brMarker)) {
      result = result.slice(0, pos) + '<br>' + result.slice(pos);
    }
  }

  // マーカーを元に戻す
  result = result.replace(new RegExp(brMarker, 'g'), '<br>');

  return result;
}

/**
 * HTML内のテキスト要素を処理
 */
function processHtml(html, maxLength) {
  const suggestions = [];

  // 対象セレクタと正規表現
  const targetPatterns = [
    { selector: 'h1', regex: /<h1[^>]*>([^<]+)<\/h1>/g },
    { selector: 'h2', regex: /<h2[^>]*>((?:(?!<\/h2>).)*)<\/h2>/gs },
    { selector: 'h3', regex: /<h3[^>]*>((?:(?!<\/h3>).)*)<\/h3>/gs },
    { selector: 'p', regex: /<p[^>]*>((?:(?!<\/p>).)*)<\/p>/gs },
    { selector: 'li', regex: /<li[^>]*>((?:(?!<\/li>).)*)<\/li>/gs },
    { selector: '.step-text', regex: /<span[^>]*class="[^"]*step-text[^"]*"[^>]*>((?:(?!<\/span>).)*)<\/span>/gs },
    { selector: '.card-desc', regex: /<p[^>]*class="[^"]*card-desc[^"]*"[^>]*>((?:(?!<\/p>).)*)<\/p>/gs },
  ];

  let modifiedHtml = html;

  for (const { selector, regex } of targetPatterns) {
    modifiedHtml = modifiedHtml.replace(regex, (fullMatch, content) => {
      // HTMLタグを含まない純テキスト長をチェック
      const plainText = content.replace(/<[^>]+>/g, '');

      if (plainText.length > maxLength) {
        const modified = insertLineBreaks(content, maxLength);

        if (modified !== content) {
          suggestions.push({
            selector,
            original: content.trim().substring(0, 50) + (content.length > 50 ? '...' : ''),
            modified: modified.trim().substring(0, 80) + (modified.length > 80 ? '...' : ''),
            charCount: plainText.length
          });

          return fullMatch.replace(content, modified);
        }
      }

      return fullMatch;
    });
  }

  return { modifiedHtml, suggestions };
}

// メイン処理
const html = readFileSync(htmlPath, 'utf-8');
const { modifiedHtml, suggestions } = processHtml(html, maxChars);

// 結果オブジェクト
const results = {
  file: htmlPath,
  maxChars,
  suggestionsCount: suggestions.length,
  suggestions,
  modified: modifiedHtml !== html
};

// 結果出力
if (jsonOutput) {
  console.log(JSON.stringify(results, null, 2));
} else {
  console.log('═══════════════════════════════════════════════════════════');
  console.log('📝 自動改行分析レポート');
  console.log('═══════════════════════════════════════════════════════════');
  console.log(`📁 ファイル: ${htmlPath}`);
  console.log(`📏 最大文字数: ${maxChars}文字/行`);
  console.log(`📊 改行提案: ${suggestions.length}件`);
  console.log('');

  if (suggestions.length === 0) {
    console.log('✅ 改行の提案はありません（すべて適切な長さです）');
  } else {
    console.log('【改行提案】');
    suggestions.forEach((s, i) => {
      console.log(`\n  ${i + 1}. ${s.selector} (${s.charCount}文字)`);
      console.log(`     元: ${s.original}`);
      console.log(`     後: ${s.modified}`);
    });

    if (autoFix) {
      writeFileSync(htmlPath, modifiedHtml, 'utf-8');
      console.log('\n✅ 改行を挿入して保存しました');
    } else if (dryRun) {
      console.log('\n💡 --fix オプションで自動挿入できます');
    }
  }
}

// 終了コード
process.exit(EXIT_CODES.SUCCESS);
