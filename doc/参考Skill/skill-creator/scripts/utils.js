/**
 * 共通ユーティリティモジュール
 *
 * skill-creatorスクリプト群で共通使用される関数・定数を集約。
 * DRY原則に基づき、重複コードを排除する。
 *
 * 使用例:
 *   import { EXIT_CODES, getArg, resolvePath, getDirname } from "./utils.js";
 */

import { existsSync, readFileSync, writeFileSync, mkdirSync } from "fs";
import { resolve, dirname, join } from "path";
import { fileURLToPath } from "url";

// ============================================================================
// 終了コード定数
// ============================================================================

export const EXIT_CODES = {
  SUCCESS: 0,
  ERROR: 1,
  ARGS_ERROR: 2,
  FILE_NOT_FOUND: 3,
  VALIDATION_FAILED: 4,
  APPLY_FAILED: 4,
  UPDATE_FAILED: 4,
  PNPM_ERROR: 4,
  CODEX_ERROR: 4,
};

// ============================================================================
// CLI引数処理
// ============================================================================

/**
 * コマンドライン引数から指定した名前の値を取得
 * @param {string[]} args - process.argv.slice(2)
 * @param {string} name - 引数名（例: "--input"）
 * @returns {string|null} 引数の値、存在しない場合はnull
 */
export function getArg(args, name) {
  const index = args.indexOf(name);
  return index !== -1 && args[index + 1] ? args[index + 1] : null;
}

/**
 * 複数の引数名で値を取得（エイリアス対応）
 * @param {string[]} args - process.argv.slice(2)
 * @param {...string} names - 引数名（例: "--dev", "-D"）
 * @returns {boolean} いずれかの引数が存在するか
 */
export function hasArg(args, ...names) {
  return names.some((name) => args.includes(name));
}

// ============================================================================
// パス解決
// ============================================================================

/**
 * パスを解決（絶対パス or カレントディレクトリからの相対パス）
 * @param {string} p - 解決するパス
 * @returns {string} 解決されたパス
 */
export function resolvePath(p) {
  if (p.startsWith("/")) return p;
  return resolve(process.cwd(), p);
}

/**
 * ESM環境での__dirname相当を取得
 * @param {string} importMetaUrl - import.meta.url
 * @returns {string} ディレクトリパス
 */
export function getDirname(importMetaUrl) {
  return dirname(fileURLToPath(importMetaUrl));
}

/**
 * スキルディレクトリを取得
 * @param {string} importMetaUrl - import.meta.url
 * @returns {string} スキルディレクトリのパス
 */
export function getSkillDir(importMetaUrl) {
  return join(getDirname(importMetaUrl), "..");
}

// ============================================================================
// ファイル操作
// ============================================================================

/**
 * JSONファイルを読み込む
 * @param {string} path - ファイルパス
 * @returns {object} パースされたJSONオブジェクト
 * @throws {Error} ファイルが存在しないかパースに失敗した場合
 */
export function readJSON(path) {
  if (!existsSync(path)) {
    throw new Error(`ファイルが存在しません: ${path}`);
  }
  return JSON.parse(readFileSync(path, "utf-8"));
}

/**
 * JSONファイルに書き込む
 * @param {string} path - ファイルパス
 * @param {object} data - 書き込むデータ
 * @param {boolean} createDir - ディレクトリが存在しない場合に作成するか
 */
export function writeJSON(path, data, createDir = true) {
  if (createDir) {
    const dir = dirname(path);
    if (!existsSync(dir)) {
      mkdirSync(dir, { recursive: true });
    }
  }
  writeFileSync(path, JSON.stringify(data, null, 2), "utf-8");
}

/**
 * ファイルが存在するか確認
 * @param {string} path - ファイルパス
 * @returns {boolean}
 */
export function fileExists(path) {
  return existsSync(path);
}

// ============================================================================
// フロントマター解析
// ============================================================================

/**
 * SKILL.mdのYAMLフロントマターを解析
 * @param {string} content - ファイル内容
 * @returns {object|null} フロントマターのオブジェクト、存在しない場合はnull
 */
export function parseFrontmatter(content) {
  const frontmatterMatch = content.match(/^---\n([\s\S]*?)\n---/);
  if (!frontmatterMatch) return null;

  const frontmatter = {};
  const lines = frontmatterMatch[1].split("\n");
  let currentKey = null;
  let currentValue = [];
  let inMultiline = false;

  for (const line of lines) {
    // マルチラインの終了判定（新しいキーが始まる）
    if (inMultiline && /^[a-z-]+:/.test(line)) {
      frontmatter[currentKey] = currentValue.join("\n").trim();
      inMultiline = false;
      currentValue = [];
    }

    // キー: 値 のパターン
    const match = line.match(/^([a-z-]+):\s*(.*)$/);
    if (match) {
      const [, key, value] = match;
      if (value === "|" || value === ">") {
        // マルチライン開始
        currentKey = key;
        inMultiline = true;
        currentValue = [];
      } else if (value === "" || value.startsWith("-")) {
        // 配列開始
        currentKey = key;
        frontmatter[key] = [];
        if (value.startsWith("-")) {
          frontmatter[key].push(value.substring(1).trim());
        }
      } else {
        frontmatter[key] = value;
      }
    } else if (line.startsWith("  - ") && currentKey) {
      // 配列の続き
      if (!Array.isArray(frontmatter[currentKey])) {
        frontmatter[currentKey] = [];
      }
      frontmatter[currentKey].push(line.substring(4).trim());
    } else if (inMultiline) {
      // マルチライン値の続き
      currentValue.push(line.trim());
    }
  }

  // 最後のマルチライン値を保存
  if (inMultiline && currentKey) {
    frontmatter[currentKey] = currentValue.join("\n").trim();
  }

  return frontmatter;
}

// ============================================================================
// リンク正規化
// ============================================================================

/**
 * Markdownリンクからスキルプレフィックスを除去して正規化
 * @param {string} link - リンクパス
 * @param {string} skillName - スキル名
 * @returns {string} 正規化されたリンク
 */
export function normalizeLink(link, skillName) {
  const prefixPatterns = [
    new RegExp(`^\\.claude/skills/${skillName}/`),
    new RegExp(`^/\\.claude/skills/${skillName}/`),
  ];
  for (const pattern of prefixPatterns) {
    if (pattern.test(link)) {
      return link.replace(pattern, "");
    }
  }
  return link;
}

/**
 * Markdownコンテンツからリンクを抽出
 * @param {string} content - Markdownコンテンツ
 * @returns {string[]} リンクの配列
 */
export function extractLinks(content) {
  const linkPattern = /\[([^\]]+)\]\(([^)]+)\)/g;
  const links = [];
  let match;
  while ((match = linkPattern.exec(content)) !== null) {
    links.push(match[2]);
  }
  return links;
}

// ============================================================================
// バリデーション結果
// ============================================================================

/**
 * バリデーション結果を蓄積するクラス
 */
export class ValidationResult {
  constructor() {
    this.errors = [];
    this.warnings = [];
    this.info = [];
  }

  addError(message, location = null) {
    this.errors.push({ message, location });
  }

  addWarning(message, location = null) {
    this.warnings.push({ message, location });
  }

  addInfo(message, location = null) {
    this.info.push({ message, location });
  }

  get isValid() {
    return this.errors.length === 0;
  }

  get hasWarnings() {
    return this.warnings.length > 0;
  }

  print() {
    if (this.errors.length > 0) {
      console.error(`\n✗ エラー: ${this.errors.length}件`);
      this.errors.forEach((e) => {
        const loc = e.location ? ` (${e.location})` : "";
        console.error(`  - ${e.message}${loc}`);
      });
    }

    if (this.warnings.length > 0) {
      console.warn(`\n⚠ 警告: ${this.warnings.length}件`);
      this.warnings.forEach((w) => {
        const loc = w.location ? ` (${w.location})` : "";
        console.warn(`  - ${w.message}${loc}`);
      });
    }

    if (this.info.length > 0 && this.errors.length === 0) {
      console.log(`\nℹ 情報: ${this.info.length}件`);
      this.info.forEach((i) => {
        const loc = i.location ? ` (${i.location})` : "";
        console.log(`  - ${i.message}${loc}`);
      });
    }
  }
}

// ============================================================================
// スクリプト実行ラッパー
// ============================================================================

/**
 * スクリプトのメイン関数をラップして共通エラーハンドリングを提供
 * @param {Function} handler - async (args) => void
 * @param {Object} options - オプション
 * @param {Function} options.showHelp - ヘルプ表示関数
 */
export async function runScript(handler, options = {}) {
  const { showHelp } = options;

  try {
    const args = process.argv.slice(2);

    if (showHelp && hasArg(args, "-h", "--help")) {
      showHelp();
      process.exit(EXIT_CODES.SUCCESS);
    }

    await handler(args);
  } catch (err) {
    console.error(`Error: ${err.message}`);
    process.exit(EXIT_CODES.ERROR);
  }
}

// ============================================================================
// 日付・時刻
// ============================================================================

/**
 * ISO形式の現在日時を取得
 * @returns {string} ISO形式の日時文字列
 */
export function nowISO() {
  return new Date().toISOString();
}

/**
 * YYYY-MM-DD形式の今日の日付を取得
 * @returns {string} 日付文字列
 */
export function todayDate() {
  return new Date().toISOString().split("T")[0];
}
