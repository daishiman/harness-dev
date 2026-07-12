#!/usr/bin/env node
/**
 * convert-to-webp.js
 *
 * スライドディレクトリ内のPNG/JPG画像をWebPに一括変換。
 * cwebpコマンドが必要（brew install webp）。
 *
 * 使用方法:
 *   node convert-to-webp.js <slide-dir> [--quality=85] [--lossless] [--dry-run] [--remove-originals]
 *
 * 出力:
 *   - 同ディレクトリに .webp ファイルを生成
 *   - index.html 内の画像参照を自動更新（オプション）
 */

import { readdirSync, existsSync, readFileSync, writeFileSync, unlinkSync, statSync } from 'fs';
import { join, extname, basename } from 'path';
import { execSync } from 'child_process';
import { parseArgs, hasFlag } from './utils.js';

const EXIT_SUCCESS = 0;
const EXIT_INVALID_ARGS = 1;
const EXIT_MISSING_DEPS = 2;
const EXIT_CONVERSION_ERROR = 3;

// ========== メイン処理 ==========

function main() {
  const { flags, positional, options } = parseArgs();

  if (positional.length === 0 || hasFlag(flags, 'help', 'h')) {
    printUsage();
    process.exit(EXIT_INVALID_ARGS);
  }

  const slideDir = positional[0];
  const quality = parseInt(options.quality || '85', 10);
  const lossless = hasFlag(flags, 'lossless');
  const dryRun = hasFlag(flags, 'dry-run');
  const removeOriginals = hasFlag(flags, 'remove-originals');

  // 入力検証
  if (!existsSync(slideDir)) {
    console.error(`[ERROR] ディレクトリが見つかりません: ${slideDir}`);
    process.exit(EXIT_INVALID_ARGS);
  }

  // cwebp コマンドの存在確認
  if (!checkCwebpInstalled()) {
    console.error('[ERROR] cwebpがインストールされていません。');
    console.error('  インストール: brew install webp');
    process.exit(EXIT_MISSING_DEPS);
  }

  // 対象ファイルの収集
  const imageFiles = collectImages(slideDir);

  if (imageFiles.length === 0) {
    console.log('[INFO] 変換対象の画像が見つかりませんでした。');
    process.exit(EXIT_SUCCESS);
  }

  console.log(`[INFO] 変換対象: ${imageFiles.length}ファイル`);
  console.log(`[INFO] 品質: ${lossless ? 'ロスレス' : `${quality}`}`);
  if (dryRun) console.log('[INFO] ドライラン: 実際の変換は行いません');

  // 変換実行
  const results = { success: 0, failed: 0, totalSaved: 0 };

  for (const file of imageFiles) {
    const inputPath = join(slideDir, file);
    const outputPath = join(slideDir, file.replace(/\.(png|jpg|jpeg)$/i, '.webp'));

    if (existsSync(outputPath)) {
      console.log(`  [SKIP] ${file} → .webp は既に存在`);
      continue;
    }

    if (dryRun) {
      console.log(`  [DRY] ${file} → ${basename(outputPath)}`);
      results.success++;
      continue;
    }

    try {
      const cmd = buildCwebpCommand(inputPath, outputPath, quality, lossless);
      execSync(cmd, { stdio: 'pipe' });

      const origSize = statSync(inputPath).size;
      const newSize = statSync(outputPath).size;
      const saved = origSize - newSize;
      const reduction = ((saved / origSize) * 100).toFixed(1);

      console.log(`  [OK] ${file} → ${basename(outputPath)} (${formatSize(origSize)} → ${formatSize(newSize)}, -${reduction}%)`);

      results.success++;
      results.totalSaved += saved;

      if (removeOriginals) {
        unlinkSync(inputPath);
        console.log(`       [DEL] 元ファイル削除: ${file}`);
      }
    } catch (err) {
      console.error(`  [FAIL] ${file}: ${err.message}`);
      results.failed++;
    }
  }

  // index.html の画像参照を更新
  if (!dryRun && results.success > 0) {
    updateHtmlReferences(slideDir, imageFiles);
  }

  // サマリー出力
  console.log('\n--- 変換結果 ---');
  console.log(`成功: ${results.success}件`);
  console.log(`失敗: ${results.failed}件`);
  if (results.totalSaved > 0) {
    console.log(`合計削減: ${formatSize(results.totalSaved)}`);
  }

  process.exit(results.failed > 0 ? EXIT_CONVERSION_ERROR : EXIT_SUCCESS);
}

// ========== ヘルパー関数 ==========

function printUsage() {
  console.log(`
使用方法: node convert-to-webp.js <slide-dir> [options]

オプション:
  --quality=N         品質設定（1-100、デフォルト: 85）
  --lossless          ロスレス変換
  --dry-run           変換をシミュレート（実際のファイルは変更しない）
  --remove-originals  変換後に元ファイルを削除
  --help              このヘルプを表示

例:
  node convert-to-webp.js ./slide-2026-02-15-title/
  node convert-to-webp.js ./slide-dir/ --quality=90
  node convert-to-webp.js ./slide-dir/ --lossless --remove-originals
  `);
}

function checkCwebpInstalled() {
  try {
    execSync('which cwebp', { stdio: 'pipe' });
    return true;
  } catch {
    return false;
  }
}

function collectImages(dir) {
  const extensions = ['.png', '.jpg', '.jpeg'];
  return readdirSync(dir)
    .filter(f => extensions.includes(extname(f).toLowerCase()))
    .filter(f => !f.startsWith('.'));
}

function buildCwebpCommand(input, output, quality, lossless) {
  const qualityFlag = lossless ? '-lossless' : `-q ${quality}`;
  // シェルインジェクション防止: パスをシングルクォートでエスケープ
  const safeInput = input.replace(/'/g, "'\\''");
  const safeOutput = output.replace(/'/g, "'\\''");
  return `cwebp ${qualityFlag} '${safeInput}' -o '${safeOutput}'`;
}

function formatSize(bytes) {
  if (bytes < 1024) return `${bytes}B`;
  if (bytes < 1024 * 1024) return `${(bytes / 1024).toFixed(1)}KB`;
  return `${(bytes / (1024 * 1024)).toFixed(1)}MB`;
}

function updateHtmlReferences(dir, convertedFiles) {
  const htmlPath = join(dir, 'index.html');
  if (!existsSync(htmlPath)) return;

  let html = readFileSync(htmlPath, 'utf-8');
  let updated = false;

  for (const file of convertedFiles) {
    const webpFile = file.replace(/\.(png|jpg|jpeg)$/i, '.webp');
    const webpPath = join(dir, webpFile);
    if (!existsSync(webpPath)) continue;

    // src="image.png" → src="image.webp" に置換
    const escaped = file.replace(/[.*+?^${}()|[\]\\]/g, '\\$&');
    const regex = new RegExp(`(src=["'])${escaped}(["'])`, 'g');
    const newHtml = html.replace(regex, `$1${webpFile}$2`);
    if (newHtml !== html) {
      html = newHtml;
      updated = true;
    }
  }

  if (updated) {
    writeFileSync(htmlPath, html, 'utf-8');
    console.log('\n[INFO] index.html の画像参照をWebPに更新しました。');
  }
}

// ========== 実行 ==========
main();
