#!/usr/bin/env node
/**
 * presentation-slide-generator 共通ユーティリティ
 *
 * DRY原則に基づき、全スクリプトで共通使用する関数を集約
 */

import { readFileSync, writeFileSync, existsSync, mkdirSync } from 'fs';
import { dirname, join, basename } from 'path';
import { fileURLToPath } from 'url';

// ==================================================
// コマンドライン引数パーサー
// ==================================================

/**
 * コマンドライン引数をパース
 * @param {string[]} argv - process.argv.slice(2)
 * @returns {{ flags: string[], positional: string[], options: Object }}
 */
export function parseArgs(argv = process.argv.slice(2)) {
  const flags = [];
  const positional = [];
  const options = {};

  for (let i = 0; i < argv.length; i++) {
    const a = argv[i];
    if (a.startsWith('--')) {
      if (a.includes('=')) {
        const [key, value] = a.slice(2).split('=');
        options[key] = value;
      } else {
        const next = argv[i + 1];
        if (next !== undefined && !next.startsWith('--')) {
          options[a.slice(2)] = next;
          flags.push(a);
          i++;
        } else {
          flags.push(a);
        }
      }
    } else {
      positional.push(a);
    }
  }

  return { flags, positional, options };
}

/**
 * フラグの存在確認
 * @param {string[]} flags - フラグ配列
 * @param  {...string} names - 確認するフラグ名（--なし）
 * @returns {boolean}
 */
export function hasFlag(flags, ...names) {
  return names.some(name => flags.includes(`--${name}`));
}

// ==================================================
// ファイル操作
// ==================================================

/**
 * JSONファイルを読み込み
 * @param {string} filepath - ファイルパス
 * @returns {Object|null}
 */
export function readJSON(filepath) {
  try {
    if (!existsSync(filepath)) return null;
    return JSON.parse(readFileSync(filepath, 'utf-8'));
  } catch (e) {
    console.error(`JSON読み込みエラー: ${filepath}`, e.message);
    return null;
  }
}

/**
 * JSONファイルを書き込み
 * @param {string} filepath - ファイルパス
 * @param {Object} data - データ
 * @param {number} indent - インデント（デフォルト: 2）
 */
export function writeJSON(filepath, data, indent = 2) {
  const dir = dirname(filepath);
  if (!existsSync(dir)) mkdirSync(dir, { recursive: true });
  writeFileSync(filepath, JSON.stringify(data, null, indent), 'utf-8');
}

/**
 * HTMLファイルを読み込み
 * @param {string} filepath - ファイルパス
 * @returns {string|null}
 */
export function readHTML(filepath) {
  try {
    if (!existsSync(filepath)) return null;
    return readFileSync(filepath, 'utf-8');
  } catch (e) {
    console.error(`HTML読み込みエラー: ${filepath}`, e.message);
    return null;
  }
}

// ==================================================
// バリデーション
// ==================================================

/**
 * 有効なスライドタイプ（59種）
 */
export const VALID_SLIDE_TYPES = {
  // 基本タイプ（15種）
  title: 'タイトル', agenda: 'アジェンダ', section: 'セクション',
  message: 'メッセージ', list: 'リスト', compare: '比較',
  flow: 'フロー', timeline: 'タイムライン', table: 'テーブル',
  stats: '統計', chart: 'チャート', diagram: '図解',
  quote: '引用', image: '画像', 'full-image': 'フルイメージ',

  // 拡張タイプ（8種）
  pyramid: 'ピラミッド', circle: 'サークル', grid: 'グリッド',
  highlight: 'ハイライト', 'icon-grid': 'アイコングリッド',
  process: 'プロセス', hero: 'ヒーロー',

  // 図解タイプ（27種）
  cycle: 'サイクル', venn: 'ベン図', mindmap: 'マインドマップ',
  flowchart: 'フローチャート', matrix: 'マトリックス',
  persona: 'ペルソナ', 'problem-solution': '課題解決',
  'value-proposition': 'バリュープロポジション',
  'point-cards': 'ポイントカード', 'concentric': '同心円',
  roadmap: 'ロードマップ', 'value-stack': '価値スタック',
  aidma: 'AIDMA', funnel: 'ファネル', orgchart: '組織図',
  chevron: 'シェブロン', 'person-network': '人物関係図',
  'vertical-timeline': '縦タイムライン', pdca: 'PDCA',
  'triangle-cycle': '三角サイクル', 'wave-steps': 'ウェーブステップ',
  'icon-selection': 'アイコン選択グリッド',

  // グラフタイプ（9種）
  bar: '棒グラフ', 'horizontal-bar': '横棒グラフ',
  'stacked-bar': '積み上げ棒', line: '折れ線',
  pie: '円グラフ', 'clock-pie': '時計型円グラフ',
  scatter: '散布図', radar: 'レーダー', gauge: 'ゲージ'
};

/**
 * スライドタイプが有効か確認
 * @param {string} type - スライドタイプ
 * @returns {boolean}
 */
export function isValidSlideType(type) {
  return type in VALID_SLIDE_TYPES || Object.values(VALID_SLIDE_TYPES).includes(type);
}

/**
 * カラーコード直書きを検出
 * @param {string} html - HTML文字列
 * @returns {{ line: number, match: string }[]}
 */
export function detectHardcodedColors(html) {
  const issues = [];
  const lines = html.split('\n');
  const colorRegex = /#[0-9A-Fa-f]{6}|#[0-9A-Fa-f]{3}(?![0-9A-Fa-f])/g;

  lines.forEach((line, index) => {
    // CSS変数定義（:root内）はスキップ
    if (line.includes(':root') || line.includes('--')) return;

    const matches = line.match(colorRegex);
    if (matches) {
      matches.forEach(match => {
        issues.push({ line: index + 1, match });
      });
    }
  });

  return issues;
}

/**
 * フォントサイズ直書きを検出
 * @param {string} html - HTML文字列
 * @returns {{ line: number, match: string }[]}
 */
export function detectHardcodedFontSizes(html) {
  const issues = [];
  const lines = html.split('\n');
  const fontSizeRegex = /font-size:\s*\d+(?:px|pt|em(?!s))/gi;

  lines.forEach((line, index) => {
    // CSS変数定義はスキップ
    if (line.includes('--fs-') || line.includes('var(--')) return;

    const matches = line.match(fontSizeRegex);
    if (matches) {
      matches.forEach(match => {
        issues.push({ line: index + 1, match });
      });
    }
  });

  return issues;
}

// ==================================================
// 定数
// ==================================================

export const VIEWPORT = {
  WIDTH: 1920,
  HEIGHT: 1080,
  ASPECT_RATIO: 16 / 9
};

export const EXIT_CODES = {
  SUCCESS: 0,
  ERROR: 1,
  ARGS_ERROR: 2,
  FILE_NOT_FOUND: 3,
  VALIDATION_FAILED: 4
};

// ==================================================
// ヘルパー
// ==================================================

/**
 * 結果をコンソール出力（JSON/テキスト対応）
 * @param {Object} result - 結果オブジェクト
 * @param {boolean} jsonMode - JSON出力モード
 */
export function outputResult(result, jsonMode = false) {
  if (jsonMode) {
    console.log(JSON.stringify(result, null, 2));
  } else {
    if (result.success) {
      console.log('✅ 検証成功');
    } else {
      console.log('❌ 検証失敗');
      if (result.errors) {
        result.errors.forEach(e => console.log(`  - ${e}`));
      }
    }
  }
}

/**
 * __dirnameを取得（ESM対応）
 * @param {string} importMetaUrl - import.meta.url
 * @returns {string}
 */
export function getDirname(importMetaUrl) {
  return dirname(fileURLToPath(importMetaUrl));
}
