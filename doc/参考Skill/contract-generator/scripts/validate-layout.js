#!/usr/bin/env node
/**
 * 契約書レイアウト崩れ検証スクリプト
 *
 * Usage:
 *   node validate-layout.js <contract.md>
 *   node validate-layout.js <contract.md> --fix  # 自動修正を試行
 *   node validate-layout.js <contract.md> --strict  # 警告もエラーとして扱う
 *
 * 検証項目:
 *   1. 長すぎる文字列（会社名、住所、項目名）
 *   2. 表のセル内容の長さ
 *   3. ページ区切り位置の問題
 *   4. 署名欄の構造
 *   5. 特殊文字・機種依存文字
 *   6. 空白プレースホルダーの残存
 */

const fs = require('fs');
const path = require('path');

// === 設定 ===
const CONFIG = {
  // 文字数制限（半角換算）
  limits: {
    companyName: 40,      // 会社名
    address: 60,          // 住所
    personName: 20,       // 人名
    tableCell: 50,        // 表セル
    singleLine: 80,       // 1行の最大文字数
    title: 30,            // 見出し
  },
  // 危険な文字パターン（日本語法律文書で一般的な全角括弧等は除外）
  dangerousChars: [
    // 丸数字（機種依存）→ (1)(2)(3) に置換推奨
    { pattern: /[\u2460-\u2473]/g, name: '丸数字①②③', severity: 'warning' },
    // ローマ数字（機種依存）→ 第1、第2 に置換推奨
    { pattern: /[\u2160-\u217F]/g, name: 'ローマ数字Ⅰ Ⅱ Ⅲ', severity: 'warning' },
    // 括弧付き数字（機種依存）→ (1)(2)(3) に置換推奨
    { pattern: /[\u3220-\u3243]/g, name: '括弧付き数字㈠㈡', severity: 'warning' },
    // 株式会社等の省略記号（機種依存）→ 正式名称に置換推奨
    { pattern: /[\u3231\u3232]/g, name: '㈱㈲（省略記号）', severity: 'warning' },
    // サロゲートペア（絵文字等）→ 削除推奨
    { pattern: /[\uD800-\uDFFF]/g, name: 'サロゲートペア（絵文字等）', severity: 'error' },
    // 制御文字 → 削除必須
    { pattern: /[\u0000-\u001F]/g, name: '制御文字', severity: 'error' },
  ],
  // ページ区切り問題のパターン
  pageBreakIssues: [
    { pattern: /^#{2,3} .+\n\n*$/m, name: '見出し直後の空行（本文なし）' },
    { pattern: /^\|.+\|\n(?![\|\-])/m, name: '表の途中終了' },
  ],
  // 署名欄必須要素
  signatureRequired: [
    '甲',
    '乙',
    '住所',
    '氏名',
    '印',
  ],
};

// === ユーティリティ ===

/**
 * 文字列の表示幅を計算（全角=2, 半角=1）
 */
function getDisplayWidth(str) {
  let width = 0;
  for (const char of str) {
    const code = char.charCodeAt(0);
    // 全角文字の判定
    if (
      (code >= 0x3000 && code <= 0x9FFF) ||  // CJK
      (code >= 0xFF00 && code <= 0xFFEF) ||  // 全角記号
      (code >= 0xAC00 && code <= 0xD7AF)     // ハングル
    ) {
      width += 2;
    } else {
      width += 1;
    }
  }
  return width;
}

/**
 * 長い文字列を安全に折り返し
 */
function wrapLongString(str, maxWidth) {
  if (getDisplayWidth(str) <= maxWidth) return str;

  const result = [];
  let current = '';
  let currentWidth = 0;

  for (const char of str) {
    const charWidth = getDisplayWidth(char);
    if (currentWidth + charWidth > maxWidth) {
      result.push(current);
      current = char;
      currentWidth = charWidth;
    } else {
      current += char;
      currentWidth += charWidth;
    }
  }
  if (current) result.push(current);

  return result.join('\n');
}

// === 検証関数 ===

/**
 * 長すぎる文字列を検出
 */
function checkLongStrings(content, issues) {
  const lines = content.split('\n');

  lines.forEach((line, idx) => {
    const lineNum = idx + 1;

    // 会社名パターン
    const companyMatch = line.match(/(?:株式会社|有限会社|合同会社).{1,50}/);
    if (companyMatch && getDisplayWidth(companyMatch[0]) > CONFIG.limits.companyName) {
      issues.push({
        type: 'warning',
        line: lineNum,
        message: `会社名が長すぎます（${getDisplayWidth(companyMatch[0])}文字）: ${companyMatch[0].slice(0, 20)}...`,
        suggestion: '改行または略称の使用を検討',
      });
    }

    // 住所パターン
    const addressMatch = line.match(/(?:都|道|府|県).{1,80}(?:番地|号|丁目)/);
    if (addressMatch && getDisplayWidth(addressMatch[0]) > CONFIG.limits.address) {
      issues.push({
        type: 'warning',
        line: lineNum,
        message: `住所が長すぎます（${getDisplayWidth(addressMatch[0])}文字）`,
        suggestion: '「〒」と郵便番号を別行にする',
      });
    }

    // 1行の長さ
    if (getDisplayWidth(line) > CONFIG.limits.singleLine && !line.startsWith('|')) {
      issues.push({
        type: 'info',
        line: lineNum,
        message: `行が長すぎる可能性（${getDisplayWidth(line)}文字）`,
        suggestion: '適切な位置で改行を検討',
      });
    }
  });
}

/**
 * 表のセル内容を検証
 */
function checkTableCells(content, issues) {
  const lines = content.split('\n');
  lines.forEach((line, idx) => {
    if (line.startsWith('|') && !line.match(/^\|[\s\-:]+\|$/)) {
      const cells = line.split('|').filter(c => c.trim());
      cells.forEach((cell, cellIdx) => {
        const trimmed = cell.trim();
        if (getDisplayWidth(trimmed) > CONFIG.limits.tableCell) {
          issues.push({
            type: 'warning',
            line: idx + 1,
            message: `表セル${cellIdx + 1}が長すぎます（${getDisplayWidth(trimmed)}文字）: ${trimmed.slice(0, 20)}...`,
            suggestion: '改行またはセル幅の調整を検討',
          });
        }
      });
    }
  });
}

/**
 * 署名欄の構造を検証
 */
function checkSignatureSection(content, issues) {
  const signatureSection = content.match(/## 署名欄[\s\S]*$/);
  if (!signatureSection) {
    issues.push({
      type: 'error',
      line: null,
      message: '署名欄セクションが見つかりません',
      suggestion: '「## 署名欄」を追加してください',
    });
    return;
  }

  const section = signatureSection[0];

  // 必須要素の確認
  CONFIG.signatureRequired.forEach(req => {
    if (!section.includes(req)) {
      issues.push({
        type: 'error',
        line: null,
        message: `署名欄に「${req}」が含まれていません`,
        suggestion: `署名欄に${req}を追加してください`,
      });
    }
  });

  // 署名欄の前に改ページ指示があるか
  const beforeSignature = content.split('## 署名欄')[0];
  if (!beforeSignature.includes('page-break') && !beforeSignature.match(/---\s*$/)) {
    issues.push({
      type: 'warning',
      line: null,
      message: '署名欄の前に改ページ指示がありません',
      suggestion: '署名欄が途中で分割される可能性があります。改ページを追加してください。',
    });
  }
}

/**
 * 特殊文字・機種依存文字を検出
 */
function checkDangerousChars(content, issues) {
  const lines = content.split('\n');

  lines.forEach((line, idx) => {
    CONFIG.dangerousChars.forEach(({ pattern, name, severity }) => {
      const matches = line.match(pattern);
      if (matches) {
        issues.push({
          type: severity,
          line: idx + 1,
          message: `${name}が含まれています: ${matches.slice(0, 3).join(', ')}`,
          suggestion: '標準的な文字に置き換えてください',
        });
      }
    });
  });
}

/**
 * 空白プレースホルダーの残存チェック
 */
function checkPlaceholders(content, issues) {
  const placeholderPatterns = [
    { pattern: /【\s*】/g, name: '空の【】' },
    { pattern: /\{\{\s*\}\}/g, name: '空の{{}}' },
    { pattern: /\[\s*\]/g, name: '空の[]（リンク以外）' },
    { pattern: /○○/g, name: '○○（未入力）' },
    { pattern: /××/g, name: '××（未入力）' },
    { pattern: /＿＿/g, name: '＿＿（未入力）' },
  ];

  const lines = content.split('\n');
  lines.forEach((line, idx) => {
    placeholderPatterns.forEach(({ pattern, name }) => {
      if (pattern.test(line)) {
        issues.push({
          type: 'error',
          line: idx + 1,
          message: `未入力のプレースホルダー（${name}）があります`,
          suggestion: '必要な情報を入力してください',
        });
      }
    });
  });
}

/**
 * ページ区切り問題を検出
 */
function checkPageBreakIssues(content, issues) {
  // 見出しの後に本文がない
  const headingPattern = /^(#{2,3} .+)\n\n*(#{1,3} |\n*$)/gm;
  let match;

  while ((match = headingPattern.exec(content)) !== null) {
    const lineNum = content.slice(0, match.index).split('\n').length;
    issues.push({
      type: 'warning',
      line: lineNum,
      message: `見出し「${match[1]}」の直後に本文がありません`,
      suggestion: '見出しと本文が分離してページ分割される可能性があります',
    });
  }

  // 表の直前に改ページ防止がない（長い表の場合）
  const tableStartPattern = /\n\|[^\n]+\|\n\|[-:\s|]+\|/g;
  while ((match = tableStartPattern.exec(content)) !== null) {
    // 表の行数をカウント
    const afterTable = content.slice(match.index);
    const tableRows = afterTable.match(/^\|[^\n]+\|$/gm);
    if (tableRows && tableRows.length > 10) {
      const lineNum = content.slice(0, match.index).split('\n').length;
      issues.push({
        type: 'info',
        line: lineNum,
        message: `長い表（${tableRows.length}行）が途中で分割される可能性があります`,
        suggestion: '表の前に改ページを検討するか、表を分割してください',
      });
    }
  }
}

/**
 * 印鑑欄のサイズ検証
 */
function checkSealSpace(content, issues) {
  // 印鑑欄が十分なスペースを持っているか
  const sealPattern = /印\s*[）\)】]?/g;
  const matches = content.match(sealPattern);

  if (matches && matches.length < 2) {
    issues.push({
      type: 'warning',
      line: null,
      message: '印鑑欄が不足している可能性があります（甲・乙両方に必要）',
      suggestion: '甲・乙それぞれの印鑑欄を確認してください',
    });
  }
}

// === メイン処理 ===

function main() {
  const args = process.argv.slice(2);
  const inputFile = args.find(a => !a.startsWith('--'));
  const shouldFix = args.includes('--fix');
  const strictMode = args.includes('--strict');

  if (!inputFile) {
    console.error('Usage: node validate-layout.js <contract.md> [--fix] [--strict]');
    console.error('');
    console.error('Options:');
    console.error('  --fix     自動修正を試行');
    console.error('  --strict  警告もエラーとして扱う');
    process.exit(1);
  }

  const filePath = path.resolve(inputFile);
  let content;

  try {
    content = fs.readFileSync(filePath, 'utf-8');
  } catch (err) {
    console.error(`Error: ファイルが読み込めません: ${filePath}`);
    process.exit(1);
  }

  console.log(`\n📄 レイアウト検証: ${path.basename(filePath)}\n`);
  console.log('=' .repeat(60));

  const issues = [];

  // 検証実行
  checkLongStrings(content, issues);
  checkTableCells(content, issues);
  checkSignatureSection(content, issues);
  checkDangerousChars(content, issues);
  checkPlaceholders(content, issues);
  checkPageBreakIssues(content, issues);
  checkSealSpace(content, issues);

  // 結果表示
  const errors = issues.filter(i => i.type === 'error');
  const warnings = issues.filter(i => i.type === 'warning');
  const infos = issues.filter(i => i.type === 'info');

  if (errors.length > 0) {
    console.log('\n❌ エラー:');
    errors.forEach(issue => {
      const lineInfo = issue.line ? `L${issue.line}: ` : '';
      console.log(`  ${lineInfo}${issue.message}`);
      if (issue.suggestion) {
        console.log(`     → ${issue.suggestion}`);
      }
    });
  }

  if (warnings.length > 0) {
    console.log('\n⚠️  警告:');
    warnings.forEach(issue => {
      const lineInfo = issue.line ? `L${issue.line}: ` : '';
      console.log(`  ${lineInfo}${issue.message}`);
      if (issue.suggestion) {
        console.log(`     → ${issue.suggestion}`);
      }
    });
  }

  if (infos.length > 0) {
    console.log('\nℹ️  情報:');
    infos.forEach(issue => {
      const lineInfo = issue.line ? `L${issue.line}: ` : '';
      console.log(`  ${lineInfo}${issue.message}`);
    });
  }

  // サマリー
  console.log('\n' + '=' .repeat(60));
  console.log(`\n📊 検証結果: エラー ${errors.length} / 警告 ${warnings.length} / 情報 ${infos.length}`);

  if (errors.length === 0 && warnings.length === 0) {
    console.log('\n✅ レイアウト検証に問題は見つかりませんでした。');
  }

  // 終了コード
  if (strictMode) {
    process.exit(errors.length + warnings.length > 0 ? 1 : 0);
  } else {
    process.exit(errors.length > 0 ? 1 : 0);
  }
}

main();
