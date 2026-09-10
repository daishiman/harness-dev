#!/usr/bin/env node
/**
 * スライド統一感検証スクリプト
 *
 * 各スライド内の視覚的統一感を検証:
 * - カラーコード直書きの検出（CSS変数推奨。正本は vendor/assets/style-genome-*.json の palette）
 * - フォントサイズ直書きの検出
 * - 統一されていないスタイルの検出
 *
 * 使用方法:
 *   node scripts/check-consistency.js <html-file-path> [options]
 *
 * オプション:
 *   --fix     問題の自動修正を試みる（実験的）
 *   --json    JSON形式で結果を出力
 *   --help    ヘルプを表示
 *
 * 例:
 *   node scripts/check-consistency.js ./index.html
 *   node scripts/check-consistency.js ./index.html --json
 */

import { existsSync, readFileSync, readdirSync } from 'fs';
import { join } from 'path';
import { parseArgs, hasFlag, EXIT_CODES, getDirname } from './utils.js';

const __dirname = getDirname(import.meta.url);
const ASSETS_DIR = join(__dirname, '../assets');

// コマンドライン引数
const { flags, positional } = parseArgs();

const showHelp = hasFlag(flags, 'help', 'h');
const jsonOutput = hasFlag(flags, 'json');
const autoFix = hasFlag(flags, 'fix');
const htmlPath = positional[0];

// ヘルプ表示
if (showHelp) {
  console.log(`
スライド統一感検証スクリプト

使用方法:
  node check-consistency.js <html-file-path> [options]

オプション:
  --fix     問題の自動修正を試みる（実験的）
  --json    JSON形式で結果を出力
  --help    ヘルプを表示

検証項目:
  1. カラーコード直書き（#XXXXXX）の検出
  2. インラインfont-size指定の検出
  3. 1スライド内で色相を持つ色の数（濃度3段まで）
  4. CSS変数未使用の検出

例:
  node check-consistency.js ./index.html
  node check-consistency.js ./index.html --json
`);
  process.exit(EXIT_CODES.SUCCESS);
}

// 入力チェック
if (!htmlPath) {
  console.error('❌ HTMLファイルパスを指定してください');
  console.error('   例: node check-consistency.js ./index.html');
  process.exit(EXIT_CODES.ARGS_ERROR);
}

if (!existsSync(htmlPath)) {
  console.error(`❌ ファイルが見つかりません: ${htmlPath}`);
  process.exit(EXIT_CODES.FILE_NOT_FOUND);
}

// 配色の正本は vendor/assets/style-genome-*.json の palette。
// この検査器に色値を写経しない（写経すると genome を替えても検査器だけが旧配色を
// 正解と言い続け、意匠の変更が「違反」として報告される）。
// 取得方式は validate-d3.js の loadGenomePalette と同じで、読めなければ fail-closed。
function normalizeHex(hex) {
  const body = hex.slice(1).toLowerCase();
  if (body.length === 3 || body.length === 4) {
    return '#' + body.slice(0, 3).split('').map(c => c + c).join('');
  }
  return '#' + body.slice(0, 6);
}

/**
 * palette を再帰的に歩いて { hex, cssVar, name, hsl } を持つ葉を集める。
 * 戻り値: { variables: Map<正規化hex, 提案文字列>, hued: Set<正規化hex>, sources, failure }
 * hued は hsl を持つ葉（= 色相を持つ色）。無彩の紙・墨・罫と区別する軸を
 * genome 側の項目の有無から取り、検査器で色を分類し直さない。
 */
function loadGenomePalette() {
  let files = [];
  try {
    files = readdirSync(ASSETS_DIR).filter(f => /^style-genome-.*\.json$/.test(f));
  } catch (e) {
    return { variables: new Map(), hued: new Set(), sources: [], failure: `style genome ディレクトリを読めません: ${ASSETS_DIR} (${e.message})` };
  }
  if (files.length === 0) {
    return { variables: new Map(), hued: new Set(), sources: [], failure: `style genome が見つかりません: ${ASSETS_DIR}/style-genome-*.json` };
  }

  const variables = new Map();
  const hued = new Set();
  const sources = [];
  const problems = [];

  const walk = node => {
    if (!node || typeof node !== 'object') return;
    if (typeof node.hex === 'string' && /^#[0-9a-fA-F]{3,8}$/.test(node.hex)) {
      const key = normalizeHex(node.hex);
      if (!variables.has(key)) {
        const label = node.cssVar
          ? `CSS変数 ${node.cssVar}`
          : `style genome の ${node.name || 'palette 項目'}（CSS変数は未発行）`;
        variables.set(key, label);
      }
      if (typeof node.hsl === 'string') hued.add(key);
      return;
    }
    Object.values(node).forEach(walk);
  };

  for (const file of files) {
    const path = join(ASSETS_DIR, file);
    try {
      const genome = JSON.parse(readFileSync(path, 'utf-8'));
      if (!genome.palette) {
        problems.push(`${file}: palette 定義がありません`);
        continue;
      }
      walk(genome.palette);
      sources.push(file);
    } catch (e) {
      problems.push(`${file}: パースに失敗 (${e.message})`);
    }
  }
  if (variables.size === 0) {
    return { variables, hued, sources, failure: `style genome の palette から色トークンを取得できません: ${problems.join(' / ') || 'palette が空'}` };
  }
  return { variables, hued, sources, failure: null };
}

const GENOME_PALETTE = loadGenomePalette();

// 読めなかったときに「問題なし」で通さない（fail-closed）。
// 通してしまうと、配色検査を素通りした deck が緑で出荷される。
if (GENOME_PALETTE.failure) {
  console.error(`❌ 配色の正本を読めません: ${GENOME_PALETTE.failure}`);
  console.error('   配色検査を実施できないため、PASS を返さずに終了します。');
  process.exit(EXIT_CODES.VALIDATION_FAILED);
}

const colorVariables = GENOME_PALETTE.variables;

// 色相を持つ色（genome の palette 項目のうち hsl を持つもの = 図解内の濃度段）。
// 面に出る色は紙・墨・その濃度だけで、強調は色ではなく反転で作る。
const huedPaletteColors = GENOME_PALETTE.hued;

// 1 面で許す色相段の数。VGCONST_002 の「単一色相の濃度 3 段まで」に対応する。
const MAX_HUED_COLORS_PER_SLIDE = 3;

// 検証結果
const results = {
  file: htmlPath,
  totalIssues: 0,
  issues: [],
  slides: [],
};

// HTMLファイル読み込み
const htmlContent = readFileSync(htmlPath, 'utf-8');

// スライドを抽出
// SR-02 (2026-05-09): slider__item 開始タグ行で初期 depth=0 から opens/closes を加算する方式に修正。
// 旧実装は開始行で depth=1 + (opens-closes) を加算するため、開始行に他の <div> や </div> が
// 同居する HTML（特に決定論レンダラ出力）でカウントが狂い、複数スライドが 1 枚に連結されていた。
const slides = [];

const lines = htmlContent.split('\n');
let currentSlide = [];
let inSlide = false;
let slideIndex = 0;
let depth = 0;

for (const line of lines) {
  // slider__item の開始行を検出（既に追跡中なら新規開始扱いしない）
  if (!inSlide && line.includes('class="') && line.includes('slider__item')) {
    inSlide = true;
    depth = 0;
    currentSlide = [line];
    const opens = (line.match(/<div/g) || []).length;
    const closes = (line.match(/<\/div>/g) || []).length;
    depth += opens - closes;
    // 単一行で完結する空 slider__item にも対応
    if (depth <= 0) {
      slides.push({ index: slideIndex++, content: currentSlide.join('\n') });
      inSlide = false;
      currentSlide = [];
    }
    continue;
  }

  if (inSlide) {
    currentSlide.push(line);
    // divの開閉を追跡
    const opens = (line.match(/<div/g) || []).length;
    const closes = (line.match(/<\/div>/g) || []).length;
    depth += opens - closes;

    if (depth <= 0) {
      slides.push({
        index: slideIndex++,
        content: currentSlide.join('\n'),
      });
      inSlide = false;
      currentSlide = [];
    }
  }
}

// 各スライドを検証
slides.forEach((slide, idx) => {
  const slideIssues = [];
  const slideNum = idx + 1;

  // 1. カラーコード直書きの検出
  const colorCodeRegex = /#[0-9A-Fa-f]{6}\b/g;
  const colorMatches = slide.content.match(colorCodeRegex) || [];

  // style属性内のカラーコードを検出
  const styleRegex = /style="[^"]*"/g;
  const styleMatches = slide.content.match(styleRegex) || [];

  styleMatches.forEach(styleAttr => {
    const inlineColors = styleAttr.match(colorCodeRegex) || [];
    inlineColors.forEach(color => {
      const key = normalizeHex(color);
      const suggestion = colorVariables.get(key);
      if (suggestion) {
        slideIssues.push({
          type: 'hardcoded-color',
          severity: 'warning',
          message: `カラーコード直書き: ${color}`,
          suggestion: `${suggestion} を使用してください`,
          location: styleAttr.substring(0, 50) + '...',
        });
      } else {
        slideIssues.push({
          type: 'unknown-color',
          severity: 'info',
          message: `未定義のカラーコード: ${color}`,
          suggestion: `配色の正本は style genome の palette（${GENOME_PALETTE.sources.join(', ')}）。そこに無い色は書けません`,
          location: styleAttr.substring(0, 50) + '...',
        });
      }
    });
  });

  // 2. フォントサイズ直書きの検出
  const fontSizeRegex = /font-size:\s*(\d+(?:\.\d+)?)(px|rem|em)/gi;
  let fontMatch;
  while ((fontMatch = fontSizeRegex.exec(slide.content)) !== null) {
    const value = parseFloat(fontMatch[1]);
    const unit = fontMatch[2];

    // CSS変数を使っていない場合
    if (!slide.content.includes('var(--fs-')) {
      slideIssues.push({
        type: 'hardcoded-fontsize',
        severity: 'warning',
        message: `フォントサイズ直書き: ${fontMatch[0]}`,
        suggestion: 'CSS変数（--fs-title, --fs-body等）を使用してください',
      });
    }

    // 最小サイズ違反チェック（rem単位のみ）
    if (unit === 'rem' && value < 1.4) {
      slideIssues.push({
        type: 'fontsize-too-small',
        severity: 'error',
        message: `フォントサイズが小さすぎます: ${fontMatch[0]}`,
        suggestion: '最小1.4rem以上にしてください',
      });
    }
  }

  // 3. 1スライド内で色相を持つ色の数を検出
  // 旧実装は「アクセント色 5 種のうち何種使ったか」を数えていたが、強調を色相で
  // 作る運用そのものを廃した（強調 = 反転）ため、数える対象を
  // 「genome で色相を持つと宣言された濃度段 + genome に無い色」へ移した。
  // genome 外の色も同じ枠で数えないと、旧配色を書いた面が「アクセント 0 種」で
  // 素通りする（色を減らしたのではなく、検査の語彙から外れただけ）。
  const usedHues = new Set();
  colorMatches.forEach(color => {
    const key = normalizeHex(color);
    if (huedPaletteColors.has(key) || !colorVariables.has(key)) usedHues.add(key);
  });

  if (usedHues.size > MAX_HUED_COLORS_PER_SLIDE) {
    slideIssues.push({
      type: 'too-many-accents',
      severity: 'warning',
      message: `色相を持つ色が多すぎます: ${usedHues.size}色`,
      suggestion: `1スライドは単一色相の濃度 ${MAX_HUED_COLORS_PER_SLIDE} 段まで。強調は色ではなく反転（ink 地 + paper 文字）で作ってください`,
      colors: [...usedHues],
    });
  }

  // SR-03 (2026-05-09): SVG viewBox 16:9 アスペクト比逸脱検査
  // 円形・正方形図解（width===height）は許容、それ以外は 16:9 ±2% 以内を要求
  const viewBoxRegex = /viewBox=["']([-\d.]+)\s+([-\d.]+)\s+([\d.]+)\s+([\d.]+)["']/gi;
  let vbMatch;
  while ((vbMatch = viewBoxRegex.exec(slide.content)) !== null) {
    const w = parseFloat(vbMatch[3]);
    const h = parseFloat(vbMatch[4]);
    if (w > 0 && h > 0) {
      const isSquare = Math.abs(w - h) / Math.max(w, h) < 0.02;
      if (!isSquare) {
        const ratio = w / h;
        const target = 16 / 9;
        const diff = Math.abs(ratio - target) / target;
        if (diff > 0.02) {
          slideIssues.push({
            type: 'viewbox-aspect-mismatch',
            severity: 'warning',
            message: `SVG viewBox が 16:9 から逸脱: ${w}x${h} (ratio ${ratio.toFixed(3)})`,
            suggestion: 'SR-1-02 / SR-5-01: viewBox は 16:9 系（例 960x540, 1600x900）または正方形（円形図解）にしてください',
          });
        }
      }
    }
  }

  // SR-04 (2026-05-09): SVG <text font-size> 最小 13px 検査（SR-3-05）
  const svgFontSizeRegex = /<text[^>]*\bfont-size=["']?(\d+(?:\.\d+)?)(px)?["']?[^>]*>/gi;
  let svgFsMatch;
  while ((svgFsMatch = svgFontSizeRegex.exec(slide.content)) !== null) {
    const value = parseFloat(svgFsMatch[1]);
    if (value < 13) {
      slideIssues.push({
        type: 'svg-fontsize-too-small',
        severity: 'error',
        message: `SVG <text> font-size が小さすぎ: ${value}px`,
        suggestion: 'SR-3-05: SVG <text> 最小 font-size は 13px。12px は小バッジ・軸ラベルのみ許容',
      });
    }
  }

  // 4. border-radiusの不統一チェック
  const borderRadiusRegex = /border-radius:\s*(\d+(?:\.\d+)?)(px|rem|%)/gi;
  const borderRadiusValues = [];
  let brMatch;
  while ((brMatch = borderRadiusRegex.exec(slide.content)) !== null) {
    borderRadiusValues.push(brMatch[0]);
  }

  const uniqueBorderRadius = [...new Set(borderRadiusValues)];
  if (uniqueBorderRadius.length > 2) {
    slideIssues.push({
      type: 'inconsistent-border-radius',
      severity: 'info',
      message: `border-radiusが不統一: ${uniqueBorderRadius.length}種類`,
      suggestion: 'border-radiusを1-2種類に統一してください',
      values: uniqueBorderRadius,
    });
  }

  // スライド結果を記録
  results.slides.push({
    slideNumber: slideNum,
    issueCount: slideIssues.length,
    issues: slideIssues,
  });

  results.issues.push(...slideIssues.map(issue => ({
    ...issue,
    slideNumber: slideNum,
  })));
});

results.totalIssues = results.issues.length;

// 結果出力
if (jsonOutput) {
  console.log(JSON.stringify(results, null, 2));
} else {
  console.log('═══════════════════════════════════════════════════════════');
  console.log('📊 スライド統一感検証レポート');
  console.log('═══════════════════════════════════════════════════════════');
  console.log(`📁 ファイル: ${htmlPath}`);
  console.log(`📋 総スライド数: ${slides.length}`);
  console.log(`⚠️  総問題数: ${results.totalIssues}`);
  console.log('');

  if (results.totalIssues === 0) {
    console.log('✅ 問題は検出されませんでした！');
  } else {
    // 問題をスライドごとに表示
    results.slides.forEach(slide => {
      if (slide.issueCount > 0) {
        console.log(`───────────────────────────────────────────────────────────`);
        console.log(`📍 スライド ${slide.slideNumber} (${slide.issueCount}件の問題)`);
        console.log('');

        slide.issues.forEach((issue, idx) => {
          const icon = issue.severity === 'error' ? '❌' :
                       issue.severity === 'warning' ? '⚠️' : 'ℹ️';
          console.log(`  ${icon} ${issue.message}`);
          console.log(`     💡 ${issue.suggestion}`);
          if (issue.colors) {
            console.log(`     🎨 ${issue.colors.join(', ')}`);
          }
          if (issue.values) {
            console.log(`     📐 ${issue.values.join(', ')}`);
          }
          console.log('');
        });
      }
    });

    // サマリー
    console.log('═══════════════════════════════════════════════════════════');
    console.log('📈 問題タイプ別サマリー');
    console.log('');

    const typeCounts = {};
    results.issues.forEach(issue => {
      typeCounts[issue.type] = (typeCounts[issue.type] || 0) + 1;
    });

    Object.entries(typeCounts).forEach(([type, count]) => {
      const label = {
        'hardcoded-color': 'カラーコード直書き',
        'unknown-color': '未定義カラー',
        'hardcoded-fontsize': 'フォントサイズ直書き',
        'fontsize-too-small': 'フォントサイズ違反',
        'too-many-accents': '色相過多',
        'inconsistent-border-radius': 'border-radius不統一',
        'viewbox-aspect-mismatch': 'SVG viewBox 16:9逸脱',
        'svg-fontsize-too-small': 'SVG font-size 13px未満',
      }[type] || type;

      console.log(`  ${label}: ${count}件`);
    });

    console.log('');
    console.log('💡 推奨アクション:');
    console.log('   1. カラーコードはCSS変数に置き換え');
    console.log('   2. フォントサイズは--fs-*変数を使用');
    console.log(`   3. 色相を持つ色は1スライド ${MAX_HUED_COLORS_PER_SLIDE} 段まで（強調は色ではなく反転で作る）`);
  }

  console.log('');
}

// 終了コード
process.exit(results.totalIssues > 0 ? EXIT_CODES.VALIDATION_FAILED : EXIT_CODES.SUCCESS);
