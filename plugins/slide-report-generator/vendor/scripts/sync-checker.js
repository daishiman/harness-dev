#!/usr/bin/env node
/**
 * index.html ⇔ structure.md 同期検証スクリプト
 *
 * 構成案（structure.md）とHTML（index.html）の整合性を検証:
 * - スライド数の一致
 * - スライドタイプの一致
 * - タイトル/メッセージの一致
 *
 * 使用方法:
 *   node scripts/sync-checker.js <html-file-path> [structure-path]
 *
 * オプション:
 *   --json    JSON形式で結果を出力
 *   --fix     structure.mdをHTMLから再生成（TODO）
 *   --help    ヘルプを表示
 *
 * 例:
 *   node scripts/sync-checker.js ./index.html
 *   node scripts/sync-checker.js ./index.html ./structure.md --json
 */

import { readFileSync, existsSync } from 'fs';
import { dirname, join } from 'path';
import { parseArgs, hasFlag, EXIT_CODES, VALID_SLIDE_TYPES } from './utils.js';

// コマンドライン引数
const { flags, positional } = parseArgs();

const showHelp = hasFlag(flags, 'help', 'h');
const jsonOutput = hasFlag(flags, 'json');
const htmlPath = positional[0];
const structurePath = positional[1] || (htmlPath ? join(dirname(htmlPath), 'structure.md') : null);

// ヘルプ表示
if (showHelp) {
  console.log(`
index.html ⇔ structure.md 同期検証スクリプト

使用方法:
  node sync-checker.js <html-file-path> [structure-path]

引数:
  <html-file-path>   HTMLファイルのパス（必須）
  [structure-path]   structure.mdのパス（省略時: HTMLと同じディレクトリ）

オプション:
  --json    JSON形式で結果を出力
  --help    ヘルプを表示

検証項目:
  1. スライド数の一致
  2. スライドタイプの一致（slider__item の data-type 属性）
  3. セクション構成の一致

例:
  node sync-checker.js ./index.html
  node sync-checker.js ./index.html ./structure.md --json
`);
  process.exit(EXIT_CODES.SUCCESS);
}

// 入力チェック
if (!htmlPath) {
  console.error('❌ HTMLファイルパスを指定してください');
  console.error('   例: node sync-checker.js ./index.html');
  process.exit(EXIT_CODES.ARGS_ERROR);
}

if (!existsSync(htmlPath)) {
  console.error(`❌ HTMLファイルが見つかりません: ${htmlPath}`);
  process.exit(EXIT_CODES.FILE_NOT_FOUND);
}

if (!existsSync(structurePath)) {
  console.error(`❌ structure.mdが見つかりません: ${structurePath}`);
  process.exit(EXIT_CODES.FILE_NOT_FOUND);
}

/**
 * structure.mdからスライド情報を抽出
 */
function parseStructureMd(filepath) {
  const content = readFileSync(filepath, 'utf-8');
  const slides = [];
  let title = '';

  // タイトル抽出（# で始まる行）
  const titleMatch = content.match(/^#\s+(.+)$/m);
  if (titleMatch) {
    title = titleMatch[1].trim();
  }

  // SR-01 (2026-05-09): frontmatter から meta.total_slides を抽出
  // structure.md 上部の YAML frontmatter (---...---) を解析
  let metaTotalSlides = null;
  const fmMatch = content.match(/^---\s*\n([\s\S]*?)\n---\s*\n/);
  if (fmMatch) {
    const fm = fmMatch[1];
    const totalMatch = fm.match(/^\s*total_slides\s*:\s*(\d+)\s*$/m);
    if (totalMatch) {
      metaTotalSlides = parseInt(totalMatch[1], 10);
    }
  }

  // JSONコードブロック内の構造化データを検出
  const jsonMatch = content.match(/```json\s*([\s\S]*?)\s*```/);
  if (jsonMatch) {
    try {
      const data = JSON.parse(jsonMatch[1]);
      // JSON 内 meta.total_slides も尊重
      if (data.meta && typeof data.meta.total_slides === 'number') {
        metaTotalSlides = metaTotalSlides ?? data.meta.total_slides;
      }
      if (data.slides) {
        return { title: data.title || title, slides: data.slides, metaTotalSlides };
      }
    } catch (e) {
      // JSONパース失敗は無視してMarkdownパースを続行
    }
  }

  // Markdownリスト形式のパース
  // パターン: - **スライドN**: [タイプ] メッセージ
  const slidePattern = /^[-*]\s+\*\*スライド(\d+)\*\*[：:]\s*\[([^\]]+)\]\s*(.+)$/gm;
  let match;
  while ((match = slidePattern.exec(content)) !== null) {
    slides.push({
      num: parseInt(match[1], 10),
      type: match[2].trim(),
      message: match[3].trim()
    });
  }

  // 代替パターン: | スライド | タイプ | メッセージ | (テーブル形式)
  if (slides.length === 0) {
    const tablePattern = /\|\s*(\d+)\s*\|\s*([^|]+)\s*\|\s*([^|]+)\s*\|/g;
    while ((match = tablePattern.exec(content)) !== null) {
      slides.push({
        num: parseInt(match[1], 10),
        type: match[2].trim(),
        message: match[3].trim()
      });
    }
  }

  return { title, slides, metaTotalSlides };
}

/**
 * HTMLからスライド情報を抽出
 */
function parseHtml(filepath) {
  const content = readFileSync(filepath, 'utf-8');
  const slides = [];

  // タイトル抽出
  let title = '';
  const titleMatch = content.match(/<title>([^<]+)<\/title>/);
  if (titleMatch) {
    title = titleMatch[1].trim();
  }

  // スライド抽出（div/section.slider__item）
  const slideRegex = /<(?:div|section)\b[^>]*class="[^"]*slider__item[^"]*"[^>]*(?:data-type="([^"]*)")?[^>]*>/g;
  let match;
  let slideNum = 0;

  while ((match = slideRegex.exec(content)) !== null) {
    slideNum++;
    const fullMatch = match[0];

    // data-type属性を抽出
    let type = match[1] || '';
    if (!type) {
      const typeAttrMatch = fullMatch.match(/data-type="([^"]*)"/);
      if (typeAttrMatch) type = typeAttrMatch[1];
    }

    // クラス名からタイプを推測
    if (!type) {
      const classMatch = fullMatch.match(/slide-(\w+)/);
      if (classMatch) type = classMatch[1];
    }

    slides.push({
      num: slideNum,
      type: type || 'unknown',
      raw: fullMatch
    });
  }

  return { title, slides };
}

/**
 * 同期検証
 */
function verifySynchronization(structureData, htmlData) {
  const issues = [];
  const warnings = [];

  // 1. スライド数チェック
  if (structureData.slides.length !== htmlData.slides.length) {
    issues.push({
      type: 'slide-count-mismatch',
      severity: 'error',
      message: `スライド数が不一致: structure.md=${structureData.slides.length}枚, HTML=${htmlData.slides.length}枚`
    });
  }

  // SR-01 (2026-05-09): meta.total_slides ↔ 実装スライド数 の drift 検査
  if (typeof structureData.metaTotalSlides === 'number') {
    if (structureData.metaTotalSlides !== htmlData.slides.length) {
      issues.push({
        type: 'meta-total-slides-drift',
        severity: 'error',
        message: `meta.total_slides=${structureData.metaTotalSlides} だが HTML 実装は ${htmlData.slides.length} 枚（spec frontmatter / JSON meta を更新するか、HTML を再生成してください）`
      });
    }
    if (structureData.metaTotalSlides !== structureData.slides.length) {
      warnings.push({
        type: 'meta-total-slides-vs-list',
        severity: 'warning',
        message: `structure.md の meta.total_slides=${structureData.metaTotalSlides} と slides リスト件数 ${structureData.slides.length} が不一致`
      });
    }
  }

  // 2. 各スライドのタイプチェック
  const minLength = Math.min(structureData.slides.length, htmlData.slides.length);
  for (let i = 0; i < minLength; i++) {
    const structSlide = structureData.slides[i];
    const htmlSlide = htmlData.slides[i];

    // タイプの正規化（日本語→英語変換）
    const normalizedStructType = normalizeSlideType(structSlide.type);
    const normalizedHtmlType = normalizeSlideType(htmlSlide.type);

    if (normalizedStructType !== normalizedHtmlType && normalizedHtmlType !== 'unknown') {
      issues.push({
        type: 'slide-type-mismatch',
        severity: 'warning',
        slideNum: i + 1,
        message: `スライド${i + 1}: タイプ不一致 - structure.md="${structSlide.type}", HTML="${htmlSlide.type}"`
      });
    }
  }

  // 3. タイトルチェック
  if (structureData.title && htmlData.title) {
    if (!htmlData.title.includes(structureData.title) && !structureData.title.includes(htmlData.title)) {
      warnings.push({
        type: 'title-mismatch',
        severity: 'info',
        message: `タイトルが異なる可能性: structure.md="${structureData.title}", HTML="${htmlData.title}"`
      });
    }
  }

  return { issues, warnings };
}

/**
 * スライドタイプを正規化（日本語→英語）
 */
function normalizeSlideType(type) {
  if (!type) return 'unknown';
  const raw = String(type).trim();
  const simplified = raw
    .replace(/[（(].*?[）)]/g, '')
    .trim()
    .toLowerCase();

  const aliases = {
    '自己紹介': 'self-intro',
    'self-intro': 'self-intro',
    '背景': 'context',
    'context': 'context',
    'ヒーロー': 'hero',
    'hero': 'hero',
    'タイトル': 'title',
    'メッセージ': 'message',
    'フロー': 'flow',
    'プロセス': 'process',
    '比較': 'compare',
    'グリッド': 'grid',
    'サークル': 'circle',
  };
  if (aliases[raw]) return aliases[raw];
  if (aliases[simplified]) return aliases[simplified];

  // 既に英語の場合はそのまま
  if (VALID_SLIDE_TYPES[type]) return type;

  // 日本語→英語変換
  for (const [engType, jpType] of Object.entries(VALID_SLIDE_TYPES)) {
    if (type === jpType) return engType;
  }

  return type.toLowerCase();
}

// メイン処理
const structureData = parseStructureMd(structurePath);
const htmlData = parseHtml(htmlPath);
const { issues, warnings } = verifySynchronization(structureData, htmlData);

// 結果オブジェクト
const results = {
  htmlPath,
  structurePath,
  structure: {
    title: structureData.title,
    slideCount: structureData.slides.length
  },
  html: {
    title: htmlData.title,
    slideCount: htmlData.slides.length
  },
  synchronized: issues.filter((issue) => issue.severity === 'error').length === 0,
  issues,
  warnings
};

// 結果出力
if (jsonOutput) {
  console.log(JSON.stringify(results, null, 2));
} else {
  console.log('═══════════════════════════════════════════════════════════');
  console.log('📊 index.html ⇔ structure.md 同期検証');
  console.log('═══════════════════════════════════════════════════════════');
  console.log(`📁 HTML: ${htmlPath}`);
  console.log(`📄 Structure: ${structurePath}`);
  console.log('');
  console.log(`📋 structure.md: ${structureData.slides.length}枚のスライド`);
  console.log(`🌐 HTML: ${htmlData.slides.length}枚のスライド`);
  console.log('');

  const errorIssues = issues.filter((issue) => issue.severity === 'error');
  const warningIssues = issues.filter((issue) => issue.severity !== 'error');

  if (results.synchronized) {
    console.log('✅ 同期OK: structure.mdとHTMLの必須整合は保たれています');
  } else {
    console.log(`❌ 同期エラー: ${errorIssues.length}件の不整合`);
    console.log('');
    errorIssues.forEach((issue) => console.log(`  ❌ ${issue.message}`));
  }

  if (warningIssues.length > 0) {
    console.log('');
    console.log(`⚠️  注意: ${warningIssues.length}件`);
    warningIssues.forEach((issue) => console.log(`  ⚠️ ${issue.message}`));
  }

  if (warnings.length > 0) {
    console.log('');
    console.log(`ℹ️  警告: ${warnings.length}件`);
    warnings.forEach(w => console.log(`  ℹ️  ${w.message}`));
  }

  console.log('');
  console.log('💡 修正方法:');
  console.log('   1. structure.mdを更新してHTML生成を再実行');
  console.log('   2. または手動でHTMLとstructure.mdを同期');
}

// 終了コード
process.exit(results.synchronized ? EXIT_CODES.SUCCESS : EXIT_CODES.VALIDATION_FAILED);
