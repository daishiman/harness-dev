#!/usr/bin/env node
/**
 * Slide screenshot and 16:9 verification entrypoint.
 *
 * Browser work is delegated to verify-slides-playwright.js, which uses the
 * plugin-local Node Playwright runtime. No global cache or Python Playwright
 * package is required.
 */
import { spawnSync } from 'child_process';
import { existsSync, readdirSync, rmSync } from 'fs';
import { dirname, join, resolve } from 'path';
import { parseArgs, hasFlag, EXIT_CODES, getDirname } from './utils.js';
import { configurePluginLocalPlaywright, setupCommand } from './playwright-runtime.js';

const __dirname = getDirname(import.meta.url);
configurePluginLocalPlaywright();

const { flags, positional } = parseArgs();
const cleanupOnly = hasFlag(flags, 'cleanup');
const autoCleanup = hasFlag(flags, 'auto-cleanup');
const checkRatioOnly = hasFlag(flags, 'check-ratio');
const htmlPath = positional[0];
const outputDir = positional[1] || (htmlPath ? join(dirname(htmlPath), 'screenshots') : null);
const helper = join(__dirname, 'verify-slides-playwright.js');

if (hasFlag(flags, 'help', 'h')) {
  console.log(`
スライド検証スクリプト（plugin-local Playwright / 16:9）

使用方法:
  node verify-slides.js <html-file-path> [output-dir] [options]

オプション:
  --cleanup       指定ディレクトリのスクリーンショットを削除して終了
  --auto-cleanup  検証後にスクリーンショットを削除
  --check-ratio   16:9アスペクト比のみチェック
  --help, -h      このヘルプを表示
`);
  process.exit(EXIT_CODES.SUCCESS);
}

function cleanupScreenshots(dir) {
  if (!dir) {
    console.error('削除対象のディレクトリが指定されていません');
    return false;
  }
  const absoluteDir = resolve(dir);
  if (!existsSync(absoluteDir)) {
    console.log(`スクリーンショットディレクトリは存在しません: ${absoluteDir}`);
    return true;
  }
  try {
    const files = readdirSync(absoluteDir).filter((file) => file.endsWith('.png'));
    for (const file of files) rmSync(join(absoluteDir, file));
    if (readdirSync(absoluteDir).length === 0) rmSync(absoluteDir, { recursive: true });
    console.log(`スクリーンショットを削除: ${files.length} files`);
    return true;
  } catch (error) {
    console.error(`スクリーンショット削除に失敗: ${error.message}`);
    return false;
  }
}

function runBrowser(args, timeout = 300000) {
  const result = spawnSync(process.execPath, [helper, ...args], {
    cwd: resolve(__dirname, '..'),
    env: process.env,
    stdio: 'inherit',
    timeout,
  });
  if (result.error) {
    console.error(`Playwright起動に失敗: ${result.error.message}`);
    console.error(`復元コマンド: ${setupCommand()}`);
    return false;
  }
  if (result.status !== 0) {
    console.error(`Playwright検証に失敗 (exit ${result.status})`);
    console.error(`Chromium未準備の場合: ${setupCommand()}`);
    return false;
  }
  return true;
}

if (cleanupOnly) {
  const target = outputDir || (htmlPath ? join(dirname(htmlPath), 'screenshots') : null);
  process.exit(cleanupScreenshots(target) ? EXIT_CODES.SUCCESS : EXIT_CODES.ERROR);
}

if (!htmlPath) {
  console.error('Usage: node verify-slides.js <html-file-path> [output-dir] [options]');
  process.exit(EXIT_CODES.ARGS_ERROR);
}
const absoluteHtmlPath = resolve(htmlPath);
if (!existsSync(absoluteHtmlPath)) {
  console.error(`HTML file not found: ${absoluteHtmlPath}`);
  process.exit(EXIT_CODES.FILE_NOT_FOUND);
}

if (checkRatioOnly) {
  const success = runBrowser(['--check-ratio', absoluteHtmlPath], 60000);
  process.exit(success ? EXIT_CODES.SUCCESS : EXIT_CODES.VALIDATION_FAILED);
}

const absoluteOutputDir = resolve(outputDir);
const success = runBrowser(['--capture', absoluteHtmlPath, absoluteOutputDir]);
if (!success) process.exit(EXIT_CODES.ERROR);

const screenshots = existsSync(absoluteOutputDir)
  ? readdirSync(absoluteOutputDir).filter((file) => file.endsWith('.png'))
  : [];
console.log(`スクリーンショット保存: ${screenshots.length} files (${absoluteOutputDir})`);

if (autoCleanup) {
  cleanupScreenshots(absoluteOutputDir);
} else {
  console.log(`削除: node verify-slides.js "${absoluteHtmlPath}" "${absoluteOutputDir}" --cleanup`);
}
