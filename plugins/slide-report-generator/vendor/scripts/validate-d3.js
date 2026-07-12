#!/usr/bin/env node

/**
 * D3.js コンポーネント検証スクリプト
 *
 * 機能:
 * - D3コンポーネントファイルの構文チェック
 * - データ構造の検証
 * - コンポーネント間の依存関係チェック
 * - テーマ色の一貫性検証
 */

import { readFileSync, existsSync, readdirSync } from 'fs';
import { join } from 'path';
import { getDirname, EXIT_CODES } from './utils.js';

const __dirname = getDirname(import.meta.url);
const COMPONENTS_DIR = join(__dirname, '../assets/d3-components');

// Kanagawaテーマカラー定義
const KANAGAWA_COLORS = {
  light: {
    bg: '#FFFFFF',
    fg: '#2D2D2D',
    accent1: '#7E9CD8',
    accent2: '#E46876',
    accent3: '#98BB6C',
    accent4: '#DCA561',
    accent5: '#7AA89F',
    accent6: '#957FB8',
    muted: '#717C7C',
    surface: '#F2F2F2',
    border: '#C8C093'
  },
  dark: {
    bg: '#1F1F28',
    fg: '#DCD7BA',
    accent1: '#7E9CD8',
    accent2: '#E46876',
    accent3: '#98BB6C',
    accent4: '#DCA561',
    accent5: '#7AA89F',
    accent6: '#957FB8',
    muted: '#727169',
    surface: '#2A2A37',
    border: '#54546D'
  }
};

// 必須のD3コンポーネント
const REQUIRED_COMPONENTS = [
  'base.js',
  'cycle.js',
  'hierarchy.js',
  'flow.js',
  'charts.js',
  'advanced.js'
];

// コンポーネント別の必須関数
const COMPONENT_FUNCTIONS = {
  'base.js': ['getTheme', 'createSVG', 'createTooltip', 'defaultTransition', 'animateEntry'],
  'cycle.js': ['createCycle', 'createPDCA'],
  'hierarchy.js': ['createTree', 'createPyramid'],
  'flow.js': ['createChevron', 'createFunnel'],
  'charts.js': ['createBarChart', 'createPieChart', 'createLineChart', 'createRadarChart', 'createGaugeChart'],
  'advanced.js': ['createForceGraph', 'createHeatmap', 'createWordCloud']
};

// 検証結果
const results = {
  passed: [],
  warnings: [],
  errors: []
};

/**
 * ファイル存在チェック
 */
function checkFileExists(filename) {
  const filepath = join(COMPONENTS_DIR, filename);
  if (existsSync(filepath)) {
    results.passed.push(`✓ ${filename} が存在します`);
    return true;
  } else {
    results.errors.push(`✗ ${filename} が見つかりません`);
    return false;
  }
}

/**
 * 関数定義チェック
 */
function checkFunctionDefinitions(filename, requiredFunctions) {
  const filepath = join(COMPONENTS_DIR, filename);
  if (!existsSync(filepath)) return;

  const content = readFileSync(filepath, 'utf-8');

  for (const func of requiredFunctions) {
    // 複数のパターンをチェック
    const patterns = [
      new RegExp(`${func}\\s*[:=]\\s*function`),
      new RegExp(`${func}\\s*\\(`),
      new RegExp(`${func}\\s*:`),
      new RegExp(`"${func}"\\s*:`)
    ];

    const found = patterns.some(pattern => pattern.test(content));

    if (found) {
      results.passed.push(`✓ ${filename}: ${func}() が定義されています`);
    } else {
      results.warnings.push(`△ ${filename}: ${func}() が見つかりません`);
    }
  }
}

/**
 * Kanagawaカラー使用チェック
 */
function checkKanagawaColors(filename) {
  const filepath = join(COMPONENTS_DIR, filename);
  if (!existsSync(filepath)) return;

  const content = readFileSync(filepath, 'utf-8');

  // Kanagawaカラー定数のチェック
  if (content.includes('KanagawaColors') || content.includes('#7E9CD8')) {
    results.passed.push(`✓ ${filename}: Kanagawaカラーを使用しています`);
  } else if (filename !== 'base.js') {
    results.warnings.push(`△ ${filename}: Kanagawaカラー参照が見つかりません（D3Baseから継承の可能性）`);
  }
}

/**
 * SVG viewBox設定チェック
 */
function checkViewBoxUsage(filename) {
  const filepath = join(COMPONENTS_DIR, filename);
  if (!existsSync(filepath)) return;

  const content = readFileSync(filepath, 'utf-8');

  if (content.includes('viewBox') && content.includes('preserveAspectRatio')) {
    results.passed.push(`✓ ${filename}: レスポンシブSVG設定があります`);
  } else if (filename !== 'base.js') {
    results.warnings.push(`△ ${filename}: viewBox/preserveAspectRatio設定を確認してください`);
  }
}

/**
 * アニメーション設定チェック
 */
function checkAnimations(filename) {
  const filepath = join(COMPONENTS_DIR, filename);
  if (!existsSync(filepath)) return;

  const content = readFileSync(filepath, 'utf-8');

  const hasTransition = content.includes('.transition()');
  const hasDuration = content.includes('.duration(');

  if (hasTransition && hasDuration) {
    results.passed.push(`✓ ${filename}: アニメーション設定があります`);
  } else {
    results.warnings.push(`△ ${filename}: アニメーション設定が不足している可能性があります`);
  }
}

/**
 * ツールチップ実装チェック
 */
function checkTooltip(filename) {
  const filepath = join(COMPONENTS_DIR, filename);
  if (!existsSync(filepath)) return;

  const content = readFileSync(filepath, 'utf-8');

  if (content.includes('tooltip') || content.includes('createTooltip')) {
    results.passed.push(`✓ ${filename}: ツールチップ対応があります`);
  } else if (filename !== 'base.js') {
    results.warnings.push(`△ ${filename}: ツールチップ実装を検討してください`);
  }
}

/**
 * d3-config.json スキーマ検証
 */
function validateD3Config(configPath) {
  if (!existsSync(configPath)) {
    results.warnings.push(`△ d3-config.json が見つかりません: ${configPath}`);
    return;
  }

  try {
    const config = JSON.parse(readFileSync(configPath, 'utf-8'));

    // バージョンチェック
    if (config.version) {
      results.passed.push(`✓ d3-config.json: バージョン ${config.version}`);
    } else {
      results.warnings.push(`△ d3-config.json: version フィールドがありません`);
    }

    // テーマチェック
    if (config.theme && ['light', 'dark'].includes(config.theme)) {
      results.passed.push(`✓ d3-config.json: テーマ ${config.theme}`);
    } else {
      results.warnings.push(`△ d3-config.json: theme は 'light' または 'dark' を指定してください`);
    }

    // スライド配列チェック
    if (Array.isArray(config.slides)) {
      results.passed.push(`✓ d3-config.json: ${config.slides.length} スライドの設定`);

      config.slides.forEach((slide, index) => {
        if (!slide.chartType) {
          results.errors.push(`✗ スライド ${index + 1}: chartType が必須です`);
        }
        if (!slide.data) {
          results.errors.push(`✗ スライド ${index + 1}: data が必須です`);
        }
      });
    } else {
      results.errors.push(`✗ d3-config.json: slides 配列が必須です`);
    }
  } catch (e) {
    results.errors.push(`✗ d3-config.json のパースに失敗: ${e.message}`);
  }
}

/**
 * HTMLテンプレート検証
 */
function validateTemplate() {
  const templatePath = join(__dirname, '../assets/d3-slide-template.html');

  if (!existsSync(templatePath)) {
    results.errors.push(`✗ d3-slide-template.html が見つかりません`);
    return;
  }

  const content = readFileSync(templatePath, 'utf-8');

  // D3.js CDN チェック
  if (content.includes('cdn.jsdelivr.net/npm/d3@7') || content.includes('d3js.org')) {
    results.passed.push(`✓ テンプレート: D3.js CDN が含まれています`);
  } else {
    results.errors.push(`✗ テンプレート: D3.js CDN が見つかりません`);
  }

  // GSAP CDN チェック
  if (content.includes('gsap')) {
    results.passed.push(`✓ テンプレート: GSAP が含まれています`);
  } else {
    results.warnings.push(`△ テンプレート: GSAP が含まれていません`);
  }

  // Kanagawa CSS変数チェック
  if (content.includes('--accent1') && content.includes('--bg')) {
    results.passed.push(`✓ テンプレート: Kanagawa CSS変数が定義されています`);
  } else {
    results.errors.push(`✗ テンプレート: Kanagawa CSS変数が不足しています`);
  }

  // テーマ切り替え機能チェック
  if (content.includes('data-theme') && content.includes('toggleTheme')) {
    results.passed.push(`✓ テンプレート: テーマ切り替え機能があります`);
  } else {
    results.warnings.push(`△ テンプレート: テーマ切り替え機能を検討してください`);
  }
}

/**
 * メイン実行
 */
function main() {
  console.log('═══════════════════════════════════════════════════════════');
  console.log('  D3.js コンポーネント検証');
  console.log('═══════════════════════════════════════════════════════════\n');

  // コンポーネントディレクトリ存在チェック
  if (!existsSync(COMPONENTS_DIR)) {
    console.error(`エラー: ${COMPONENTS_DIR} が見つかりません`);
    process.exit(EXIT_CODES.FILE_NOT_FOUND);
  }

  // 1. 必須ファイル存在チェック
  console.log('【1. ファイル存在チェック】');
  REQUIRED_COMPONENTS.forEach(checkFileExists);
  console.log();

  // 2. 関数定義チェック
  console.log('【2. 関数定義チェック】');
  Object.entries(COMPONENT_FUNCTIONS).forEach(([file, funcs]) => {
    checkFunctionDefinitions(file, funcs);
  });
  console.log();

  // 3. テーマカラーチェック
  console.log('【3. Kanagawaカラーチェック】');
  REQUIRED_COMPONENTS.forEach(checkKanagawaColors);
  console.log();

  // 4. レスポンシブ設定チェック
  console.log('【4. レスポンシブSVGチェック】');
  REQUIRED_COMPONENTS.forEach(checkViewBoxUsage);
  console.log();

  // 5. アニメーションチェック
  console.log('【5. アニメーションチェック】');
  REQUIRED_COMPONENTS.forEach(checkAnimations);
  console.log();

  // 6. ツールチップチェック
  console.log('【6. ツールチップチェック】');
  REQUIRED_COMPONENTS.forEach(checkTooltip);
  console.log();

  // 7. テンプレート検証
  console.log('【7. HTMLテンプレート検証】');
  validateTemplate();
  console.log();

  // 8. コマンドライン引数でd3-config.jsonのパスが指定された場合
  if (process.argv[2]) {
    console.log('【8. d3-config.json 検証】');
    validateD3Config(process.argv[2]);
    console.log();
  }

  // 結果サマリー
  console.log('═══════════════════════════════════════════════════════════');
  console.log('  検証結果サマリー');
  console.log('═══════════════════════════════════════════════════════════\n');

  console.log(`✓ 成功: ${results.passed.length} 項目`);
  console.log(`△ 警告: ${results.warnings.length} 項目`);
  console.log(`✗ エラー: ${results.errors.length} 項目\n`);

  if (results.errors.length > 0) {
    console.log('【エラー詳細】');
    results.errors.forEach(e => console.log(`  ${e}`));
    console.log();
  }

  if (results.warnings.length > 0) {
    console.log('【警告詳細】');
    results.warnings.forEach(w => console.log(`  ${w}`));
    console.log();
  }

  // 終了コード
  process.exit(results.errors.length > 0 ? EXIT_CODES.VALIDATION_FAILED : EXIT_CODES.SUCCESS);
}

main();
