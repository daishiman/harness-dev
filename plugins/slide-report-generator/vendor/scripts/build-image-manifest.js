#!/usr/bin/env node
/**
 * build-image-manifest.js
 *
 * 役割: 全面画像デッキの GAS デプロイ用画像 SSoT である
 *       <slide-dir>/assets/generated/image-asset-manifest.json を
 *       generated 配下の実画像から決定論生成/更新する。
 *
 * 背景(GAS デプロイの事故):
 *   build-deck-html.js が出力する index.html は画像を相対パス
 *   (assets/generated/<name>.<ext>) で参照する。Google Apps Script の
 *   HtmlService は相対パス参照の画像を読めないため、デッキを GAS へ
 *   デプロイすると画像が全滅する。自己完結 base64 インライン
 *   (build-single-html.js --inline-images)は GAS HTML 上限 500KB に
 *   収まる範囲でしか使えない。そこで画像を外部ホスティングし、その
 *   絶対 URL を manifest に記録 -> build-deck-html.js --manifest が
 *   src/srcset を外部 URL へ差し替える、という経路を用意する。
 *   その外部 URL の正本がこの manifest(image-asset-manifest.json)。
 *
 * SSoT としての役割:
 *   - key = slide-dir 基準の相対パス(build-deck-html.js が index.html に
 *     書く src/srcset と同一表記 assets/generated/<name>.<ext>)
 *   - bytes = 実バイト, sha256 = 内容ハッシュ(変更検知用)
 *   - publicUrl = 外部ホスティング絶対 URL(空=未ホスト)
 *   - assetBaseUrl(トップ) = URL=base+'/'+basename で導出できるホスティング基底 URL(空可)
 *   このスクリプトは bytes/sha256 を機械生成する。ホスティング後の
 *   publicUrl / assetBaseUrl はユーザーが記入し、本スクリプトは
 *   再実行しても既存の publicUrl / assetBaseUrl を必ず保持する
 *   (ユーザー記入 URL を破壊しない)。
 *
 * 使い方:
 *   node scripts/build-image-manifest.js <slide-dir> [--asset-base-url=<URL>]
 *   入力: <slide-dir>/assets/generated/ 配下の画像
 *         (.webp/.png/.jpg/.jpeg/.gif/.svg)
 *   出力: <slide-dir>/assets/generated/image-asset-manifest.json
 *   --asset-base-url=<URL> 指定時はトップの assetBaseUrl を上書きする
 *     (未指定時は既存値を保持)。
 *
 * サイズ予算(末尾レポート):
 *   base64 自己完結の可否を判定する。base64 換算 = 実バイト x1.37、
 *   HTML 骨格 +30KB、GAS HTML 上限 500KB。インライン対象は webp 優先
 *   (無ければ png)。合計が予算内なら build-single-html.js --inline-images
 *   で自己完結可、超過なら外部 URL 化が必要、と1行で示す。
 *
 * 終了コード: 正常 0、引数欠落/ディレクトリ無し 2。
 *
 * 検証方針: 標準出力やサイズ表示を鵜呑みにせず、生成された
 *   image-asset-manifest.json を Read で確認すること(本スクリプトの
 *   stdout はあくまで補助レポート)。
 *
 * 自己テスト:
 *   1. node --check scripts/build-image-manifest.js (構文)
 *   2. node scripts/build-image-manifest.js <deck> 実行 ->
 *      image-asset-manifest.json を Read して bytes/sha256/publicUrl/
 *      assetBaseUrl を目視確認。
 */

import { readFileSync, writeFileSync, existsSync, statSync, readdirSync } from 'fs';
import { join, basename } from 'path';
import { createHash } from 'crypto';

const SCHEMA_VERSION = '1.0.0';
// 走査対象の画像拡張子(小文字)。index.html が参照しうる画像のみ。
const IMAGE_EXT = ['.webp', '.png', '.jpg', '.jpeg', '.gif', '.svg'];
// base64 換算係数・HTML 骨格・GAS HTML 上限(byte)。サイズ予算判定用。
const BASE64_FACTOR = 1.37;
const HTML_SKELETON_BYTES = 30 * 1024;
const GAS_HTML_LIMIT_BYTES = 500 * 1024;

function extOf(name) {
  const dot = name.lastIndexOf('.');
  return dot < 0 ? '' : name.slice(dot).toLowerCase();
}

function sha256File(absPath) {
  return createHash('sha256').update(readFileSync(absPath)).digest('hex');
}

// 既存 manifest を読む。壊れていても落とさず空構造を返す(ユーザー URL は
// 読めた範囲で後段が保持する)。
function readExistingManifest(manifestPath) {
  if (!existsSync(manifestPath)) return null;
  try {
    const obj = JSON.parse(readFileSync(manifestPath, 'utf8'));
    if (obj && typeof obj === 'object') return obj;
  } catch (e) {
    console.error('WARN: 既存 manifest を JSON として読めませんでした。新規生成します: ' + manifestPath);
  }
  return null;
}

function parseArgs(argv) {
  const args = { slideDir: null, assetBaseUrl: null };
  for (const a of argv) {
    if (a.startsWith('--asset-base-url=')) {
      args.assetBaseUrl = a.slice('--asset-base-url='.length);
    } else if (!args.slideDir) {
      args.slideDir = a;
    }
  }
  return args;
}

function main() {
  const args = parseArgs(process.argv.slice(2));
  if (!args.slideDir) {
    console.error('Usage: node scripts/build-image-manifest.js <slide-dir> [--asset-base-url=<URL>]');
    process.exit(2);
  }
  const genDir = join(args.slideDir, 'assets', 'generated');
  if (!existsSync(genDir)) {
    console.error('FAIL: assets/generated が見つかりません: ' + genDir);
    process.exit(2);
  }

  const manifestPath = join(genDir, 'image-asset-manifest.json');
  const existing = readExistingManifest(manifestPath);
  // 既存の publicUrl はファイル相対パスをキーに引けるよう退避する。
  const existingFiles = (existing && existing.files && typeof existing.files === 'object')
    ? existing.files : {};

  // generated 直下の画像を相対パスキーで走査(サブディレクトリは対象外)。
  const entries = readdirSync(genDir)
    .filter((n) => IMAGE_EXT.includes(extOf(n)))
    .sort();

  const files = {};
  for (const name of entries) {
    const relPath = 'assets/generated/' + name;
    const absPath = join(genDir, name);
    const bytes = statSync(absPath).size;
    const sha256 = sha256File(absPath);
    // 既存エントリの publicUrl は破壊しない(ユーザー記入 URL の保持)。
    const prev = existingFiles[relPath];
    const publicUrl = (prev && typeof prev.publicUrl === 'string') ? prev.publicUrl : '';
    files[relPath] = { bytes, sha256, publicUrl };
  }

  // assetBaseUrl 解決: --asset-base-url 指定時は上書き、未指定なら既存値を保持。
  let assetBaseUrl = '';
  if (args.assetBaseUrl !== null) {
    assetBaseUrl = args.assetBaseUrl;
  } else if (existing && typeof existing.assetBaseUrl === 'string') {
    assetBaseUrl = existing.assetBaseUrl;
  }

  // deck 識別子: 既存値を保持、無ければ slide-dir の basename。
  let deck = (existing && typeof existing.deck === 'string') ? existing.deck : '';
  if (!deck) deck = basename(args.slideDir.replace(/\/+$/, ''));

  const manifest = {
    schemaVersion: SCHEMA_VERSION,
    deck,
    assetBaseUrl,
    files,
  };
  writeFileSync(manifestPath, JSON.stringify(manifest, null, 2) + '\n');

  // --- サイズ予算レポート(base64 自己完結の可否) ---
  // インライン対象は各画像の webp 優先(無ければ png)。slug 単位で集約する。
  // webp/png 以外(jpg/svg 等)はインライン対象集計に含めない(基準は webp|png)。
  const inlineBySlug = {};
  for (const [relPath, info] of Object.entries(files)) {
    const ext = extOf(relPath);
    if (ext !== '.webp' && ext !== '.png') continue;
    const slug = basename(relPath).replace(/\.(webp|png)$/i, '');
    if (!inlineBySlug[slug]) inlineBySlug[slug] = {};
    inlineBySlug[slug][ext] = info.bytes;
  }
  let rawInlineBytes = 0;
  for (const slug of Object.keys(inlineBySlug)) {
    const e = inlineBySlug[slug];
    rawInlineBytes += (typeof e['.webp'] === 'number') ? e['.webp'] : (e['.png'] || 0);
  }
  const base64Bytes = Math.round(rawInlineBytes * BASE64_FACTOR) + HTML_SKELETON_BYTES;
  const rawKB = (rawInlineBytes / 1024).toFixed(1);
  const base64KB = (base64Bytes / 1024).toFixed(1);
  const limitKB = (GAS_HTML_LIMIT_BYTES / 1024).toFixed(0);
  const underBudget = base64Bytes <= GAS_HTML_LIMIT_BYTES;

  console.log('image-asset-manifest.json written: ' + entries.length + ' files, '
    + Object.keys(inlineBySlug).length + ' inline-candidate slides');
  console.log('size budget: raw(webp|png) ' + rawKB + 'KB, base64+skeleton ' + base64KB
    + 'KB vs GAS limit ' + limitKB + 'KB');
  if (underBudget) {
    console.log('recommend: under budget -> build-single-html.js --inline-images で自己完結可');
  } else {
    console.log('recommend: over budget(' + base64KB + 'KB > ' + limitKB
      + 'KB) -> 画像をホストし publicUrl/assetBaseUrl を記入のうえ build-deck-html.js --manifest で外部URL化');
  }
  process.exit(0);
}

main();
