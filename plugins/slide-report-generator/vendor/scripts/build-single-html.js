#!/usr/bin/env node
/**
 * build-single-html.js
 *
 * 分離形式のHTMLスライド（index.html + styles.css + scripts.js）を
 * GASデプロイ用の1ファイルHTMLに結合するビルドスクリプト。
 * --inline-images 指定時はローカル画像をbase64 data URIに焼き込み、
 * 外部ファイル参照ゼロの単一HTMLにする。
 *
 * 予算チェック: GAS HTMLファイルのサイズ上限は500KB。base64化で容易に超過するため、
 * 書き出し後に最終HTMLのバイト数を必ず500KBと対比して出力する（残量も表示）。
 * 通常モードは超過しても warn のみで終了コード0（後方互換）。
 * 厳格モード（--strict / --full-image-deck）では超過時に FAIL（exit 1）。
 *
 * サイレント失敗の昇格: --inline-images で画像が未検出/未解決のまま元パスが残ると、
 * GAS上でbrokenリンクになる。厳格モードでは未解決1件以上で FAIL（exit 1）。
 * 通常モードは現状どおり warn 継続（後方互換）。
 *
 * 注: 完成判定はファイルの目視/Readで行う設計思想（Bash標準出力に依存しない）に従い、
 * 本スクリプトは予算・未解決を明示出力しつつ、厳格モードでのみ終了コードで失敗を伝える。
 *
 * Usage:
 *   node build-single-html.js ./output/
 *   node build-single-html.js ./output/ --output=index-single.html
 *   node build-single-html.js ./output/ --inline-images --output=index.deploy.html
 *   node build-single-html.js ./output/ --inline-images --image-format=jpg --output=index.deploy.jpg.html
 *   node build-single-html.js ./output/ --inline-images --strict --output=index.deploy.html
 *   node build-single-html.js ./output/ --inline-images --full-image-deck --output=index.deploy.html
 *
 * Arguments:
 *   directory           分離形式スライドが格納されているディレクトリ
 *   --output, --out     出力ファイル名または相対パス（デフォルト: index-single.html）
 *   --inline-images     ローカル画像参照をbase64 data URIに焼き込む（GASデプロイ用）
 *   --image-format      焼き込み時の優先フォーマット（webp | jpg、デフォルト: webp）
 *   --strict            厳格モード。500KB超過・画像未解決を FAIL（exit 1）扱いにする
 *   --full-image-deck   全面画像デッキ向け厳格モード（--strict と同義の厳格化）
 */

import { readFileSync, writeFileSync, existsSync, mkdirSync } from 'fs';
import { join, resolve, dirname } from 'path';

// デフォルト設定
const DEFAULT_OUTPUT_NAME = 'index-single.html';

// GAS HTMLファイルのサイズ上限（バイト）
const GAS_SIZE_LIMIT_BYTES = 512000;

// 拡張子→MIMEタイプ
const IMAGE_MIME = {
  webp: 'image/webp',
  png: 'image/png',
  jpg: 'image/jpeg',
  jpeg: 'image/jpeg',
  gif: 'image/gif',
  svg: 'image/svg+xml'
};

function detectImageMime(buffer, relPath) {
  if (buffer.length >= 12 && buffer.toString('ascii', 0, 4) === 'RIFF' && buffer.toString('ascii', 8, 12) === 'WEBP') {
    return 'image/webp';
  }
  if (buffer.length >= 8 && buffer[0] === 0x89 && buffer.toString('ascii', 1, 4) === 'PNG') {
    return 'image/png';
  }
  if (buffer.length >= 3 && buffer[0] === 0xff && buffer[1] === 0xd8 && buffer[2] === 0xff) {
    return 'image/jpeg';
  }
  if (buffer.length >= 6 && ['GIF87a', 'GIF89a'].includes(buffer.toString('ascii', 0, 6))) {
    return 'image/gif';
  }
  if (/\.svg$/i.test(relPath)) {
    return 'image/svg+xml';
  }
  return null;
}

function printUsage() {
  console.log(`
Usage: node build-single-html.js <directory> [options]

Arguments:
  directory              分離形式スライドが格納されているディレクトリ

Options:
  --output=<filename>    出力ファイル名または相対パス（デフォルト: ${DEFAULT_OUTPUT_NAME}）
  --out <filename>       --output の別名
  --inline-images        ローカル画像をbase64 data URIに焼き込む（GASデプロイ用）
  --image-format=<fmt>   焼き込み時の優先フォーマット（webp | jpg、デフォルト: webp）
  --strict               厳格モード。GAS 500KB超過・画像未解決を FAIL（exit 1）にする
  --full-image-deck      全面画像デッキ向け厳格モード（--strict と同義の厳格化）
  --help                 このヘルプを表示

予算チェック:
  書き出し後に最終HTMLサイズを必ず GAS上限500KB と対比して出力（残量も表示）。
  通常モードは超過しても warn のみ・終了コード0（後方互換）。
  厳格モードは超過時に FAIL（exit 1）。--inline-images の画像未解決も厳格モードで FAIL。

Example:
  node build-single-html.js ./slide-2026-01-23-workshop/
  node build-single-html.js ./output/ --output=combined.html
  node build-single-html.js ./output/ --inline-images --output=index.deploy.html
  node build-single-html.js ./output/ --inline-images --image-format=jpg --output=index.deploy.jpg.html
  node build-single-html.js ./output/ --inline-images --strict --output=index.deploy.html
  node build-single-html.js ./output/ --inline-images --full-image-deck --output=index.deploy.html
`);
}

function parseArgs(args) {
  const result = {
    directory: null,
    outputName: DEFAULT_OUTPUT_NAME,
    inlineImages: false,
    imageFormat: 'webp',
    strict: false
  };

  for (let i = 2; i < args.length; i++) {
    const arg = args[i];
    if (arg === '--help' || arg === '-h') {
      printUsage();
      process.exit(0);
    } else if (arg === '--inline-images') {
      result.inlineImages = true;
    } else if (arg === '--strict' || arg === '--full-image-deck') {
      // どちらか/両方の指定で厳格モード（500KB超過・画像未解決を FAIL 扱い）
      result.strict = true;
    } else if (arg.startsWith('--image-format=')) {
      result.imageFormat = arg.slice('--image-format='.length).toLowerCase();
    } else if (arg === '--image-format') {
      result.imageFormat = (args[++i] || '').toLowerCase();
    } else if (arg.startsWith('--output=')) {
      result.outputName = arg.slice('--output='.length);
    } else if (arg.startsWith('--out=')) {
      result.outputName = arg.slice('--out='.length);
    } else if (arg === '--output' || arg === '--out') {
      result.outputName = args[++i];
    } else if (!arg.startsWith('-')) {
      result.directory = arg;
    }
  }

  return result;
}

function readFileContent(filePath) {
  if (!existsSync(filePath)) {
    console.error(`Error: File not found: ${filePath}`);
    return null;
  }
  return readFileSync(filePath, 'utf-8');
}

// HTML属性値のダブルクォートをエスケープ
function escapeAttr(value) {
  return value.replace(/"/g, '&quot;');
}

// ローカル画像ファイルをbase64 data URIに変換（失敗時はnull）
function toDataUri(dir, relPath) {
  const ext = relPath.split('.').pop().toLowerCase();
  if (!IMAGE_MIME[ext]) return null;
  const abs = join(dir, relPath);
  if (!existsSync(abs)) {
    console.warn(`Warning: image not found, left as-is: ${relPath}`);
    return null;
  }
  const buf = readFileSync(abs);
  const mime = detectImageMime(buf, relPath);
  if (!mime) {
    console.warn(`Warning: image signature is unknown, left as-is: ${relPath}`);
    return null;
  }
  if (IMAGE_MIME[ext] !== mime) {
    console.warn(`Warning: image extension/mime mismatch for ${relPath}; using detected ${mime}`);
  }
  return `data:${mime};base64,${buf.toString('base64')}`;
}

// 拡張子を除いたベースパスから、希望フォーマット優先で実在する画像を選ぶ
function pickAsset(dir, baseNoExt, preferExt) {
  const order = preferExt === 'jpg' || preferExt === 'jpeg'
    ? ['jpg', 'jpeg', 'webp', 'png']
    : ['webp', 'png', 'jpg', 'jpeg'];
  for (const ext of order) {
    const rel = `${baseNoExt}.${ext}`;
    if (existsSync(join(dir, rel))) return rel;
  }
  return null;
}

// picture要素を希望フォーマット優先でimg(data URI)に畳み込み、残るローカルimgもbase64化する
// 戻り値: { html, inlined, unresolved }
//   inlined    = base64化に成功した画像数
//   unresolved = 未検出/未解決で元パスのまま残った画像数（GAS上でbroken候補）
function inlineImageRefs(html, dir, preferExt) {
  let inlined = 0;
  let unresolved = 0;

  // 1) <picture>...</picture> を希望フォーマット優先の単一 <img> に置換
  let result = html.replace(/<picture\b[^>]*>([\s\S]*?)<\/picture>/gi, (block, inner) => {
    const imgTag = inner.match(/<img\b[^>]*>/i);
    const altMatch = imgTag ? imgTag[0].match(/\balt=["']([^"']*)["']/i) : null;
    const srcMatch = imgTag ? imgTag[0].match(/\bsrc=["']([^"']+)["']/i) : null;
    const srcsetMatch = inner.match(/<source\b[^>]*srcset=["']([^"']+)["'][^>]*>/i);
    const ref = srcMatch ? srcMatch[1] : (srcsetMatch ? srcsetMatch[1] : null);
    if (!ref) return block;
    const baseNoExt = ref.replace(/\.[^./]+$/, '');
    const chosen = pickAsset(dir, baseNoExt, preferExt);
    if (!chosen) { unresolved++; return block; }
    const dataUri = toDataUri(dir, chosen);
    if (!dataUri) { unresolved++; return block; }
    inlined++;
    const alt = altMatch ? escapeAttr(altMatch[1]) : '';
    return `<img src="${dataUri}" alt="${alt}">`;
  });

  // 2) picture外に残る通常 <img src="ローカル画像"> も base64 化
  result = result.replace(/<img\b[^>]*\bsrc=["']([^"']+)["'][^>]*>/gi, (tag, src) => {
    if (src.startsWith('data:') || /^https?:\/\//i.test(src)) return tag;
    const ext = src.split('.').pop().toLowerCase();
    if (!IMAGE_MIME[ext]) return tag;
    const baseNoExt = src.replace(/\.[^./]+$/, '');
    const chosen = pickAsset(dir, baseNoExt, preferExt) || src;
    const dataUri = toDataUri(dir, chosen);
    if (!dataUri) { unresolved++; return tag; }
    inlined++;
    return tag.replace(src, dataUri);
  });

  console.log(`   Images inlined: ${inlined} (format preference: ${preferExt})`);
  if (unresolved > 0) {
    console.warn(`   Images unresolved: ${unresolved} (left as original path; GASでbroken候補)`);
  }
  return { html: result, inlined, unresolved };
}

function buildSingleHtml(directory, outputName, inlineImages, imageFormat, strict) {
  const dir = resolve(directory);

  // 必要なファイルのパス
  const htmlPath = join(dir, 'index.html');
  const cssPath = join(dir, 'styles.css');
  const jsPath = join(dir, 'scripts.js');

  // ファイルを読み込み
  const html = readFileContent(htmlPath);
  const css = readFileContent(cssPath);
  const js = readFileContent(jsPath);

  if (!html) {
    console.error('Error: index.html is required');
    process.exit(1);
  }

  // CSS/JSがない場合は警告を出すが続行
  if (!css) {
    console.warn('Warning: styles.css not found, proceeding without CSS');
  }
  if (!js) {
    console.warn('Warning: scripts.js not found, proceeding without JS');
  }

  // HTMLをパース
  let result = html;
  let unresolvedImages = 0;

  // 画像参照をbase64 data URIに焼き込む（GASデプロイ用）
  if (inlineImages) {
    const inlineResult = inlineImageRefs(result, dir, imageFormat);
    result = inlineResult.html;
    unresolvedImages = inlineResult.unresolved;
  }

  // 外部CSSリンクをインラインスタイルに置換
  if (css) {
    const cssLinkRegex = /<link\b(?=[^>]*\brel=["']stylesheet["'])(?=[^>]*\bhref=["']styles\.css["'])[^>]*>/gi;
    const styleTag = `<style>\n${css}\n  </style>`;
    result = result.replace(cssLinkRegex, styleTag);
  }

  // 外部JSスクリプトをインラインに置換
  if (js) {
    const jsScriptRegex = /<script\b(?=[^>]*\bsrc=["']scripts\.js["'])[^>]*>\s*<\/script>/gi;
    const scriptTag = `<script>\n${js}\n  </script>`;
    result = result.replace(jsScriptRegex, scriptTag);
  }

  // 出力パス
  const outputPath = resolve(dir, outputName);
  mkdirSync(dirname(outputPath), { recursive: true });

  // 書き出し
  writeFileSync(outputPath, result, 'utf-8');

  console.log(`[OK] Successfully built single-file HTML`);
  console.log(`   Input:  ${htmlPath}`);
  if (css) console.log(`           ${cssPath}`);
  if (js) console.log(`           ${jsPath}`);
  console.log(`   Output: ${outputPath}`);

  // 予算チェック: 最終HTMLの実バイト数を GAS上限500KB と対比して必ず出力（残量も表示）
  const outputBytes = Buffer.byteLength(result, 'utf-8');
  const limitKB = (GAS_SIZE_LIMIT_BYTES / 1024).toFixed(0);
  const sizeKB = (outputBytes / 1024).toFixed(1);
  const remainingKB = ((GAS_SIZE_LIMIT_BYTES - outputBytes) / 1024).toFixed(1);
  const overLimit = outputBytes > GAS_SIZE_LIMIT_BYTES;
  console.log(`   Size:   ${sizeKB} KB / GAS limit ${limitKB}KB (remaining: ${remainingKB} KB)`);

  // 厳格モードで FAIL すべき事由を集約してから終了コードを決める
  let shouldFail = false;

  if (overLimit) {
    if (strict) {
      console.error(`   FAIL: exceeds GAS ${limitKB}KB limit by ${(-remainingKB).toFixed(1)} KB; ホストして外部URL方式(build-deck-html.js --manifest)を検討`);
      shouldFail = true;
    } else {
      console.warn(`   WARNING: exceeds GAS ${limitKB}KB limit; ホストして外部URL方式(build-deck-html.js --manifest)を検討`);
    }
  }

  // 画像未解決のサイレント失敗を厳格モードでは昇格（通常モードは warn 済み・exit0 維持で後方互換）
  if (unresolvedImages > 0 && strict) {
    console.error(`   FAIL: ${unresolvedImages} images unresolved -> GASでbroken`);
    shouldFail = true;
  }

  if (shouldFail) {
    process.exit(1);
  }
}

// メイン処理
const config = parseArgs(process.argv);

if (!config.directory) {
  console.error('Error: Directory argument is required');
  printUsage();
  process.exit(1);
}

if (!existsSync(config.directory)) {
  console.error(`Error: Directory not found: ${config.directory}`);
  process.exit(1);
}

buildSingleHtml(config.directory, config.outputName, config.inlineImages, config.imageFormat, config.strict);
