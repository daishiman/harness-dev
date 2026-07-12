#!/usr/bin/env node
/**
 * validate-ai-image-assets.js
 *
 * AI画像アセット（assets/generated/*.webp/.png/.prompt.md/.meta.json）と
 * style-genome の整合を決定論的に検証する。
 *
 * CHANGELOG:
 *   v2 (2026-06-24, elegant-review D5/D6):
 *     - [D5] index.html 実HTML層検証を追加(checkIndexHtmlLayer):
 *         全面画像スライドの主キャンバス class(.ai-slide-canvas / 許容エイリアス
 *         .slide-fullbg / .slide-bg / [data-role=main-canvas])存在、
 *         object-fit:contain、meta.imageFit との cross-check。
 *         coverage 不足(image-only宣言なのに html-primary 実装)検出。
 *     - [D6] 決定論チェーン強制:
 *         full-image-deck で image-deck-plan.json 不在を WARNING→FAIL 昇格。
 *         meta.builtBy:"build-image-prompts" マーカー無し(手書き疑い)を警告。
 *     - 既存 meta/genome-content 検査は不変(後方互換)。
 *   v3 (reproducible-artifact-prompt):
 *     - --strict-intent または --full-image-deck 時に Purpose / Audience takeaway /
 *       Background / Layout / generation を prompt と meta の両方で検査する。
 *       画像生成プロンプトを artifact spec として扱い、目的・背景・構図が空の生成を防ぐ。
 *   v4 (elegant-review 第2弾・D10):
 *     - 支配色(60-30-10の主役色)の prompt 反映を契約化。meta.dominantAccentHex があるスライドは、
 *       対応 prompt 本文に「Dominant accent for this slide ... <hex>」行が無ければ intentIssue。
 *       従来の accent HEX 照合(--check-genome-content)は palette 全色羅列に偶発一致すれば PASS したため、
 *       支配色を意味照合に格上げする(--strict-intent / --full-image-deck で error)。
 *   v5 (baked-table・D12):
 *     - tableMode=illustrated-full-table の検査を追加。textPolicy=baked-with-overlay 固定、
 *       meta.tableContent 必須、各セルが prompt 本文へ verbatim 展開されているかを意味照合(--strict-intent /
 *       --full-image-deck で error)。generation.quality!="high" は密テキストの可読性低下のため warning。
 *       allowedTableModes に illustrated-full-table を追加。
 *   v6 (elegant-review 再検証・D13):
 *     - illustrated-full-table の verbatim 照合に caption/note を追加(画像内に焼くため正本照合の対象)。
 *     - 曖昧語リンターを builder の VAGUE_PROMPT_WORDS と同期(various/several/appropriate/balanced 等を追加)。
 *       genome ガイダンス文(tableAndMatrixRules/contentAdaptationRules/printReadinessRules/artStyle/flowLegendRule)を
 *       除外集合 genomeLang に加え、genome 由来語の誤検出を防ぐ。
 *   v7 (png-signature・実運用事故対策):
 *     - PNG 署名検査を追加。各 .png の先頭バイトが PNG 署名(89 50 4E 47 0D 0A 1A 0A・
 *       最低でも先頭4バイト 89 50 4E 47)であることを検証し、署名を持たない(中身がテキスト等の)
 *       png を FAIL にする。事故: 全面画像デッキで png の中身が "# Image Generation Skill"(先頭
 *       hex 23 20 49 6d 61 67 65)というテキストだったのに、存在チェック/md5固有チェックのみで PASS
 *       していた。webp は RIFF/WEBP 署名検査済みだが png には署名検査が無かったため追加(後方互換)。
 *     - --full-image-deck では image-deck-plan.json の全スライドについて png/webp 双方の署名を検査する。
 */
import { existsSync, readdirSync, readFileSync, statSync } from 'fs';
import { basename, dirname, extname, join, normalize } from 'path';
import { fileURLToPath } from 'url';

const skillDir = join(dirname(fileURLToPath(import.meta.url)), '..');

function usage() {
  console.error('Usage: node scripts/validate-ai-image-assets.js <slide-dir> [--strict-style-genome] [--full-image-deck] [--check-genome-content] [--gas-check]');
  process.exit(2);
}

const args = process.argv.slice(2);
const strictStyleGenome = args.includes('--strict-style-genome') || args.includes('--strict');
const fullImageDeck = args.includes('--full-image-deck');
const requireStyleGenome = strictStyleGenome || fullImageDeck || args.includes('--require-style-genome');
// 追加フラグ(純粋な追加・既定では無効)。prompt 本文が style-genome 仕様を反映しているかを照合する。
const checkGenomeContent = args.includes('--check-genome-content');
const strictIntent = args.includes('--strict-intent');
// opt-in: GAS(Google Apps Script)は単一HTMLしか配信せず assets/ 相対パス画像を配信できない。
// --gas-check を付けたときだけ、デプロイHTML内の相対パス <img>/<source> を GAS非対応として検出する。
// 付けない限り一切動作せず、既存の検証ロジック・終了コード・出力に影響を与えない。
const gasCheck = args.includes('--gas-check');
const slideDir = args.find((arg) => !arg.startsWith('--'));
if (!slideDir) usage();

const generatedDir = join(slideDir, 'assets', 'generated');
if (!existsSync(generatedDir)) {
  if (fullImageDeck) {
    console.error('FAIL: full-image-deck requires assets/generated with style-genome.json and per-slide assets');
    process.exit(1);
  }
  // opt-in: generatedDir が無くてもデプロイHTMLに相対パス画像があれば GAS では broken なので検査する。
  // 既定 WARN(--strict 併用時のみ FAIL)。--gas-check 非指定なら従来通り即 PASS で終了する。
  if (gasCheck) {
    const gasResult = runGasCheckStandalone(slideDir);
    for (const warning of gasResult.warnings) console.warn(`WARN: ${warning}`);
    if (gasResult.errors.length > 0) {
      for (const error of gasResult.errors) console.error(`FAIL: ${error}`);
      process.exit(1);
    }
  }
  console.log('PASS: assets/generated does not exist; no AI image assets to validate.');
  process.exit(0);
}

const files = readdirSync(generatedDir);
const webps = files.filter((file) => extname(file) === '.webp');
const metas = files.filter((file) => extname(file) === '.json' && file.endsWith('.meta.json'));
const errors = [];
const warnings = [];

if (requireStyleGenome) {
  const projectStyleGenome = join(generatedDir, 'style-genome.json');
  const bundledStyleGenome = join(skillDir, 'assets', 'style-genome-kanagawa-comic-diagram.json');
  if (fullImageDeck && !existsSync(projectStyleGenome)) {
    errors.push('full-image-deck requires project-local assets/generated/style-genome.json');
  } else if (!existsSync(projectStyleGenome) && !existsSync(bundledStyleGenome)) {
    errors.push('missing style genome: expected assets/generated/style-genome.json or bundled assets/style-genome-kanagawa-comic-diagram.json');
  }
}

// ===== D6: 決定論ビルドチェーン強制 =====
// image-deck-plan.json(plan) → build-image-prompts.js → prompt/meta が規定工程。
// full-image-deck で plan.json 不在は決定論チェーン迂回(手書き)を意味し FAIL に昇格。
// plan.json は slide-dir 直下 or assets/generated 配下のいずれかを許容。
if (fullImageDeck) {
  const planCandidates = [
    join(slideDir, 'image-deck-plan.json'),
    join(generatedDir, 'image-deck-plan.json'),
  ];
  const planFound = planCandidates.some((p) => existsSync(p));
  if (!planFound) {
    errors.push('full-image-deck requires image-deck-plan.json (deterministic build chain): not found in slide dir or assets/generated. Hand-written meta bypasses build-image-prompts.js.');
  }
}

function isProjectLocalStyleGenome(value) {
  if (typeof value !== 'string') return false;
  const normalized = normalize(value).replace(/^\.\//, '');
  return normalized === join('assets', 'generated', 'style-genome.json')
    || normalized.endsWith(join('assets', 'generated', 'style-genome.json'));
}

function expectedSlideCount() {
  const structurePath = join(slideDir, 'structure.md');
  if (existsSync(structurePath)) {
    const structure = readFileSync(structurePath, 'utf8');
    const totalMatch = structure.match(/(?:総スライド数|total[_\s-]*slides?)\D{0,20}(\d+)\s*(?:枚|slides?)?/i);
    if (totalMatch) return Number(totalMatch[1]);
  }

  const indexPath = join(slideDir, 'index.html');
  if (existsSync(indexPath)) {
    const html = readFileSync(indexPath, 'utf8');
    // 各スライドコンテナは data-slide="N" を1つ持つ(render-slide.cjs / build-deck-html.js 共通)。
    // これを最優先で数える。次点で slider__item クラストークンを数える。
    // 旧実装の `slide\b` は ai-slide-canvas / slide-heading / slide-area といった
    // スライドでないクラスまで部分一致で拾い、枚数を過大算出していた(誤FAILの原因)。
    const dataSlideMarkers = html.match(/\bdata-slide=["']\d+["']/g);
    if (dataSlideMarkers?.length) return dataSlideMarkers.length;
    const itemMarkers = html.match(/class=["'][^"']*\bslider__item\b[^"']*["']/g);
    if (itemMarkers?.length) return itemMarkers.length;
  }
  return null;
}

function detectImageType(buffer) {
  if (buffer.length >= 12 && buffer.toString('ascii', 0, 4) === 'RIFF' && buffer.toString('ascii', 8, 12) === 'WEBP') {
    return 'webp';
  }
  if (buffer.length >= 8 && buffer[0] === 0x89 && buffer.toString('ascii', 1, 4) === 'PNG') {
    return 'png';
  }
  if (buffer.length >= 3 && buffer[0] === 0xff && buffer[1] === 0xd8 && buffer[2] === 0xff) {
    return 'jpeg';
  }
  if (buffer.length >= 6 && ['GIF87a', 'GIF89a'].includes(buffer.toString('ascii', 0, 6))) {
    return 'gif';
  }
  return 'unknown';
}

// PNG 署名(8バイト): 89 50 4E 47 0D 0A 1A 0A。最低でも先頭4バイト 89 50 4E 47 を要求する。
const PNG_SIGNATURE = Buffer.from([0x89, 0x50, 0x4e, 0x47, 0x0d, 0x0a, 0x1a, 0x0a]);

function hasPngSignature(buffer) {
  if (buffer.length < 4) return false;
  // 最低条件: 先頭4バイト 89 50 4E 47("\x89PNG")。
  if (buffer[0] !== 0x89 || buffer[1] !== 0x50 || buffer[2] !== 0x4e || buffer[3] !== 0x47) return false;
  // 8バイト揃っていれば完全な PNG 署名を要求する(改行部の破損も検出)。
  if (buffer.length >= 8) return buffer.subarray(0, 8).equals(PNG_SIGNATURE);
  return true;
}

// .png の中身が本当に PNG かを署名で検査し、テキスト/壊れの場合は errors へ。
// 事故再発防止: 先頭が "# Image Generation Skill"(23 20 49 ...)のテキスト png を FAIL にする。
function checkPngSignature(pngPath, label) {
  if (!existsSync(pngPath)) return;
  let buffer;
  try {
    buffer = readFileSync(pngPath);
  } catch (error) {
    errors.push(`${label}: cannot read PNG file (${error.message})`);
    return;
  }
  if (buffer.length === 0) {
    errors.push(`${label}: empty PNG file`);
    return;
  }
  if (!hasPngSignature(buffer)) {
    const headHex = buffer.subarray(0, Math.min(8, buffer.length)).toString('hex').replace(/(..)(?=.)/g, '$1 ');
    errors.push(`${label}: extension is .png but content is NOT a PNG (missing PNG signature 89 50 4E 47; head bytes: ${headHex}). 中身が PNG でない(テキスト/壊れの可能性)`);
  }
}

function requireOrWarn(condition, message) {
  if (condition) return;
  if (requireStyleGenome) errors.push(message);
  else warnings.push(`${message} (use --strict-style-genome to fail legacy metadata)`);
}

function validateMeta(metaPath, stem) {
  try {
    const meta = JSON.parse(readFileSync(metaPath, 'utf8'));
    for (const key of ['slide', 'asset', 'source', 'decision', 'reason', 'alt']) {
      if (!(key in meta)) errors.push(`${metaPath}: missing key "${key}"`);
    }
    if (typeof meta.source === 'string' && meta.source.trim().toLowerCase() === 'codex') {
      errors.push(`${metaPath}: source must be the actual text-to-image backend, not plain "codex"`);
    }

    const usesStyleGenome = Boolean(meta.styleGenome)
      || meta.styleName === 'kanagawa-comic-diagram'
      || /kanagawa-comic-diagram|style-genome/i.test(JSON.stringify(meta));

    if (requireStyleGenome || usesStyleGenome) {
      for (const key of ['pattern', 'textPolicy', 'backgroundSource', 'styleGenome', 'prompt']) {
        requireOrWarn(key in meta, `${metaPath}: missing key "${key}" for style-genome reproducibility contract`);
      }
      requireOrWarn('imageFit' in meta, `${metaPath}: missing key "imageFit" for HTML/print no-crop contract`);
    }
    if (fullImageDeck && !meta.styleGenome) {
      errors.push(`${metaPath}: full-image-deck requires styleGenome`);
    } else if (fullImageDeck && !isProjectLocalStyleGenome(meta.styleGenome)) {
      errors.push(`${metaPath}: full-image-deck requires project-local styleGenome="assets/generated/style-genome.json"`);
    }
    // D6: build-image-prompts.js を通った成果物にだけ付くマーカー。
    // 無い場合は手書き(決定論チェーン迂回)の疑い。strict/full-image-deck では
    // 警告(plan.json 不在 FAIL とは別軸の観測点。手書きでも plan があれば許容)。
    if ('builtBy' in meta) {
      if (meta.builtBy !== 'build-image-prompts') {
        warnings.push(`${metaPath}: builtBy="${meta.builtBy}" is not "build-image-prompts" (unexpected builder marker)`);
      }
    } else if (fullImageDeck) {
      warnings.push(`${metaPath}: missing meta.builtBy="build-image-prompts" marker (possible hand-written meta bypassing build-image-prompts.js)`);
    }
    if (fullImageDeck && meta.pattern && !['image-only', 'html-composite', 'html-primary'].includes(meta.pattern)) {
      errors.push(`${metaPath}: full-image-deck has invalid pattern "${meta.pattern}"`);
    }

    if ('pattern' in meta) {
      const allowedPatterns = new Set(['image-only', 'html-composite', 'html-primary']);
      if (!allowedPatterns.has(meta.pattern)) {
        errors.push(`${metaPath}: invalid pattern "${meta.pattern}"`);
      }
    }
    if ('textPolicy' in meta) {
      const allowedTextPolicies = new Set(['baked-with-overlay', 'overlay-only', 'none']);
      if (!allowedTextPolicies.has(meta.textPolicy)) {
        errors.push(`${metaPath}: invalid textPolicy "${meta.textPolicy}" (expected baked-with-overlay | overlay-only | none)`);
      }
      if (meta.textPolicy === 'baked-with-overlay' && (!Array.isArray(meta.overlayText) || meta.overlayText.length === 0)) {
        errors.push(`${metaPath}: baked-with-overlay requires non-empty overlayText`);
      }
    }
    if ('backgroundSource' in meta) {
      const allowedBackgroundSources = new Set(['raster', 'svg', 'none']);
      if (!allowedBackgroundSources.has(meta.backgroundSource)) {
        errors.push(`${metaPath}: invalid backgroundSource "${meta.backgroundSource}" (expected raster | svg | none)`);
      }
    }
    if ('imageFit' in meta) {
      const allowedImageFit = new Set(['contain', 'cover-safe', 'html-composite-contain']);
      if (!allowedImageFit.has(meta.imageFit)) {
        errors.push(`${metaPath}: invalid imageFit "${meta.imageFit}" (expected contain | cover-safe | html-composite-contain)`);
      }
      if (meta.pattern === 'image-only' && meta.imageFit === 'cover-safe') {
        errors.push(`${metaPath}: image-only main canvas must use imageFit=contain; cover-safe is only for decorative/background composites`);
      }
      if (meta.pattern === 'html-composite' && meta.imageFit === 'cover-safe') {
        warnings.push(`${metaPath}: imageFit=cover-safe requires visual crop check; prefer html-composite-contain unless the image is decorative-only`);
      }
    }
    if ('tableMode' in meta) {
      const allowedTableModes = new Set(['none', 'illustrated-mini-table', 'illustrated-full-table', 'html-overlay-table', 'diagram-translation', 'html-primary']);
      if (!allowedTableModes.has(meta.tableMode)) {
        errors.push(`${metaPath}: invalid tableMode "${meta.tableMode}"`);
      }
    }
    if ('pattern' in meta && 'textPolicy' in meta) {
      const coherentTextPolicy = {
        'image-only': new Set(['baked-with-overlay', 'overlay-only']),
        'html-composite': new Set(['overlay-only']),
        'html-primary': new Set(['none']),
      };
      const allowed = coherentTextPolicy[meta.pattern];
      if (allowed && !allowed.has(meta.textPolicy)) {
        warnings.push(`${metaPath}: textPolicy "${meta.textPolicy}" is unusual for pattern "${meta.pattern}" (expected ${[...allowed].join(' | ')})`);
      }
    }
    if ('pattern' in meta && 'backgroundSource' in meta) {
      const coherentBackgroundSource = {
        'image-only': new Set(['none']),
        'html-composite': new Set(['raster', 'svg']),
        'html-primary': new Set(['none', 'svg']),
      };
      const allowed = coherentBackgroundSource[meta.pattern];
      if (allowed && !allowed.has(meta.backgroundSource)) {
        warnings.push(`${metaPath}: backgroundSource "${meta.backgroundSource}" is unusual for pattern "${meta.pattern}" (expected ${[...allowed].join(' | ')})`);
      }
    }
    if (
      meta.styleGenome
      && !existsSync(join(slideDir, meta.styleGenome))
      && !existsSync(join(skillDir, meta.styleGenome))
      && !existsSync(meta.styleGenome)
    ) {
      warnings.push(`${metaPath}: styleGenome path not found from slide dir, skill dir, or cwd (${meta.styleGenome})`);
    }
    if (meta.prompt && !existsSync(join(slideDir, meta.prompt)) && !existsSync(join(generatedDir, meta.prompt)) && !existsSync(meta.prompt)) {
      warnings.push(`${metaPath}: prompt path not found (${meta.prompt})`);
    }
    if (meta.decision !== 'generate-image' && meta.pattern !== 'html-primary' && meta.backgroundSource !== 'svg') {
      warnings.push(`${metaPath}: decision should be "generate-image" for generated raster assets`);
    }
    if (fullImageDeck) {
      const requiresRaster = meta.pattern === 'image-only' || (meta.pattern === 'html-composite' && meta.backgroundSource === 'raster');
      if (requiresRaster) {
        const webpPath = join(generatedDir, `${stem}.webp`);
        const pngPath = join(generatedDir, `${stem}.png`);
        const promptPath = join(generatedDir, `${stem}.prompt.md`);
        if (!existsSync(webpPath)) errors.push(`${metaPath}: full-image-deck raster slide is missing ${stem}.webp`);
        if (!existsSync(pngPath)) errors.push(`${metaPath}: full-image-deck raster slide is missing ${stem}.png`);
        if (!existsSync(promptPath)) errors.push(`${metaPath}: full-image-deck raster slide is missing ${stem}.prompt.md`);
      }
    }
    if (stem && meta.slug && !stem.includes(meta.slug) && !meta.slug.includes(stem.replace(/^slide-\d+-?/, ''))) {
      warnings.push(`${metaPath}: slug "${meta.slug}" does not appear to match file stem "${stem}"`);
    }
  } catch (error) {
    errors.push(`${metaPath}: invalid JSON (${error.message})`);
  }
}

// ===== --check-genome-content (追加・純粋な追加) =====
// prompt.md 本文が style-genome.json の仕様(promptSuffix 主要語 / motif / accent HEX /
// preamble)を反映しているかを照合する。不一致は strict 時 FAIL / 非 strict 時 WARN。
function loadGenomeForContent() {
  const projectStyleGenome = join(generatedDir, 'style-genome.json');
  const bundledStyleGenome = join(skillDir, 'assets', 'style-genome-kanagawa-comic-diagram.json');
  const path = existsSync(projectStyleGenome)
    ? projectStyleGenome
    : (existsSync(bundledStyleGenome) ? bundledStyleGenome : null);
  if (!path) return null;
  try {
    return JSON.parse(readFileSync(path, 'utf8'));
  } catch {
    return null;
  }
}

function genomeContentIssue(message) {
  if (requireStyleGenome) errors.push(message);
  else warnings.push(message);
}

function extractStyleKeywords(promptSuffix) {
  if (typeof promptSuffix !== 'string') return [];
  const seen = new Set();
  const out = [];
  for (const raw of promptSuffix.toLowerCase().match(/[a-z]{6,}/g) || []) {
    if (raw === 'style') continue;
    if (seen.has(raw)) continue;
    seen.add(raw);
    out.push(raw);
    if (out.length >= 3) break;
  }
  return out;
}

function runGenomeContentChecks() {
  const genome = loadGenomeForContent();
  const suffixKeywords = genome ? extractStyleKeywords(genome.promptSuffix) : [];
  const motifNames = genome && Array.isArray(genome.motifs) ? genome.motifs.map((m) => m.name) : [];
  const paletteByKey = genome && genome.palette ? genome.palette : {};
  const promptFiles = files.filter((file) => file.endsWith('.prompt.md'));

  for (const promptFile of promptFiles) {
    const stem = basename(promptFile, '.prompt.md');
    const promptPath = join(generatedDir, promptFile);
    let prompt;
    try {
      prompt = readFileSync(promptPath, 'utf8');
    } catch {
      continue;
    }
    const lower = prompt.toLowerCase();
    const head = prompt.slice(0, 400);

    // preamble は "STYLE LOCK" / "STYLE BIBLE" もしくは "Use STYLE GENOME" で始まる
    if (!/^\s*(?:STYLE LOCK|STYLE BIBLE|Use STYLE GENOME)/i.test(head)) {
      genomeContentIssue(`${promptPath}: genome-content: prompt must start with "STYLE LOCK" / "STYLE BIBLE" or "Use STYLE GENOME" preamble`);
    }

    // promptSuffix の主要語が本文に含まれるか(2語以上)
    if (suffixKeywords.length > 0) {
      const hits = suffixKeywords.filter((kw) => lower.includes(kw));
      if (hits.length < Math.min(2, suffixKeywords.length)) {
        genomeContentIssue(`${promptPath}: genome-content: missing style-genome promptSuffix keywords (expected some of ${suffixKeywords.join(', ')})`);
      }
    }

    const metaPath = join(generatedDir, `${stem}.meta.json`);
    let meta = null;
    if (existsSync(metaPath)) {
      try {
        meta = JSON.parse(readFileSync(metaPath, 'utf8'));
      } catch {
        meta = null;
      }
    }

    // meta.motifs があれば、その名称が prompt 本文または style genome に存在するか
    const motifs = meta && Array.isArray(meta.motifs) ? meta.motifs : [];
    for (const name of motifs) {
      if (!prompt.includes(name) && !motifNames.includes(name)) {
        genomeContentIssue(`${promptPath}: genome-content: motif "${name}" not found in prompt body or style genome`);
      }
    }

    // accent が HEX またはパレット名のとき、対応 HEX が prompt 本文に出現するか(WARN)
    if (meta && typeof meta.accent === 'string') {
      const accent = meta.accent.trim();
      let hex = null;
      if (/^#?[0-9a-fA-F]{6}$/.test(accent)) {
        hex = accent.startsWith('#') ? accent : `#${accent}`;
      } else if (paletteByKey[accent] && paletteByKey[accent].hex) {
        hex = paletteByKey[accent].hex;
      }
      if (hex && !lower.includes(hex.toLowerCase())) {
        warnings.push(`${promptPath}: genome-content: accent HEX ${hex} not found in prompt body`);
      }
    }
  }
}

// ===== D5: 実HTML層検証(index.html cross-check) =====
// 宣言(meta)と実装(index.html + styles.css)の cross-check。
// 主キャンバス class は意味属性 + 許容クラスの union で検出し、クラス名密結合を避ける。
//   許容: data-role="main-canvas" / .ai-slide-canvas(規定) / .slide-fullbg / .slide-bg(エイリアス)
// 検査:
//   (1) image-only meta が存在するのに index.html に主キャンバスが1つも無い → coverage 不足
//   (2) 主キャンバス img の object-fit が screen/print とも contain か(cover は D1 違反)
//   (3) meta.imageFit と CSS object-fit 実効値の一致(宣言 != 実装 を検出)
function readCss(slideRoot) {
  // index.html が link する styles.css(相対)を取り込み、@media print 内外を結合した
  // 全CSS文字列を返す。複数 stylesheet を許容。
  const indexPath = join(slideRoot, 'index.html');
  if (!existsSync(indexPath)) return { html: '', css: '' };
  const html = readFileSync(indexPath, 'utf8');
  let css = '';
  const linkRe = /<link\s+[^>]*rel\s*=\s*["']stylesheet["'][^>]*href\s*=\s*["']([^"']+)["'][^>]*>/gi;
  let lm;
  while ((lm = linkRe.exec(html)) !== null) {
    const href = lm[1];
    if (/^https?:/i.test(href) || /^\/\//.test(href)) continue;
    try {
      css += '\n' + readFileSync(join(slideRoot, href), 'utf8');
    } catch { /* missing stylesheet ignored */ }
  }
  // <style> インライン分も結合
  const styleRe = /<style[^>]*>([\s\S]*?)<\/style>/gi;
  let sm;
  while ((sm = styleRe.exec(html)) !== null) css += '\n' + sm[1];
  return { html, css };
}

function extractPrintCss(css) {
  // @media print { ... } をネスト対応で抽出して結合
  const out = [];
  const re = /@media\s+print\s*\{/g;
  let m;
  while ((m = re.exec(css)) !== null) {
    let depth = 1;
    let i = m.index + m[0].length;
    while (i < css.length && depth > 0) {
      if (css[i] === '{') depth++;
      else if (css[i] === '}') depth--;
      i++;
    }
    out.push(css.slice(m.index, i));
  }
  return out.join('\n');
}

// 主キャンバスセレクタ(union)。クラス名密結合回避。
const MAIN_CANVAS_SEL = /(?:ai-slide-canvas|slide-fullbg|slide-bg|\[data-role\s*=\s*["']?main-canvas["']?\])/;

function mainCanvasObjectFit(css) {
  // 主キャンバスセレクタを持つルール塊の object-fit 値集合を返す({contain, cover}等)。
  const fits = new Set();
  const ruleRe = /([^{}]+)\{([^{}]*)\}/g;
  let m;
  while ((m = ruleRe.exec(css)) !== null) {
    if (!MAIN_CANVAS_SEL.test(m[1])) continue;
    const fitM = m[2].match(/object-fit\s*:\s*([a-z-]+)/);
    if (fitM) fits.add(fitM[1]);
  }
  return fits;
}

function checkIndexHtmlLayer() {
  const { html, css } = readCss(slideDir);
  if (!html) {
    if (fullImageDeck) {
      warnings.push('D5: index.html not found; cannot cross-check main canvas class / object-fit against meta.imageFit');
    }
    return;
  }

  // 主キャンバスが HTML に存在するか(意味属性 + 許容クラス union)。
  const hasMainCanvasHtml = /class\s*=\s*["'][^"']*\b(?:ai-slide-canvas|slide-fullbg|slide-bg)\b[^"']*["']|data-role\s*=\s*["']main-canvas["']/.test(html);

  // image-only meta の枚数(主キャンバスを要求する宣言)。
  let imageOnlyCount = 0;
  for (const metaFile of metas) {
    try {
      const meta = JSON.parse(readFileSync(join(generatedDir, metaFile), 'utf8'));
      if (meta.pattern === 'image-only') imageOnlyCount += 1;
    } catch { /* ignore */ }
  }

  // (1) coverage: image-only 宣言があるのに主キャンバス実装が無い。
  if (imageOnlyCount > 0 && !hasMainCanvasHtml) {
    errors.push(`D5: ${imageOnlyCount} image-only meta declared but index.html has no main canvas (.ai-slide-canvas / .slide-fullbg / .slide-bg / [data-role=main-canvas]). Declared image-only but implemented as html-primary (coverage shortfall).`);
  }

  if (!hasMainCanvasHtml) return; // 主キャンバスが無ければ object-fit 検査は対象外

  // object-fit 実効値(screen 全体 + print)を抽出。
  const screenFits = mainCanvasObjectFit(css);
  const printCss = extractPrintCss(css);
  const printFits = mainCanvasObjectFit(printCss);

  // (2) screen/print いずれかで cover を持つと端切れ(D1)。
  if (screenFits.has('cover')) {
    errors.push('D5: main canvas img uses object-fit:cover on screen; full-image main canvas must be contain (no-crop).');
  }
  if (printFits.has('cover')) {
    errors.push('D5: main canvas img uses object-fit:cover in @media print; baked text/subject will be cropped on A4 letterbox. Use object-fit:contain !important.');
  }
  // 主キャンバスがあるのに contain 指定がどこにも無い(暗黙の初期値 fill 等)も警告。
  if (!screenFits.has('contain') && !printFits.has('contain')) {
    warnings.push('D5: main canvas img has no explicit object-fit:contain in screen or print CSS; default fit may crop or distort.');
  }

  // (3) meta.imageFit と CSS object-fit の cross-check。
  //   meta が imageFit=contain と宣言しているのに CSS が cover を含むと矛盾。
  for (const metaFile of metas) {
    let meta;
    try {
      meta = JSON.parse(readFileSync(join(generatedDir, metaFile), 'utf8'));
    } catch { continue; }
    if (meta.pattern !== 'image-only') continue;
    if (meta.imageFit === 'contain' && (screenFits.has('cover') || printFits.has('cover'))) {
      errors.push(`${join(generatedDir, metaFile)}: D5 cross-check: meta.imageFit="contain" but CSS main canvas uses object-fit:cover (declared != effective).`);
    }
  }
}

for (const webp of webps) {
  const stem = basename(webp, '.webp');
  const webpPath = join(generatedDir, webp);
  const pngPath = join(generatedDir, `${stem}.png`);
  const promptPath = join(generatedDir, `${stem}.prompt.md`);
  const metaPath = join(generatedDir, `${stem}.meta.json`);

  if (!existsSync(pngPath)) errors.push(`${webp}: missing PNG source (${stem}.png)`);
  if (!existsSync(promptPath)) errors.push(`${webp}: missing prompt file (${stem}.prompt.md)`);
  if (!existsSync(metaPath)) errors.push(`${webp}: missing meta file (${stem}.meta.json)`);
  if (statSync(webpPath).size === 0) errors.push(`${webp}: empty WebP file`);
  if (existsSync(webpPath)) {
    const type = detectImageType(readFileSync(webpPath));
    if (type !== 'webp') errors.push(`${webp}: extension is .webp but file signature is ${type}`);
  }
  // PNG ソースの署名検査(webp は上で署名検査済み・png にも同等の署名検査を追加)。
  checkPngSignature(pngPath, `${stem}.png`);

  if (existsSync(promptPath)) {
    const prompt = readFileSync(promptPath, 'utf8');
    const promptPreamble = prompt.slice(0, 800);
    if (fullImageDeck && !/(^|\n)\s*(?:Use STYLE GENOME:\s*\n\s*assets\/generated\/style-genome\.json|STYLE LOCK\s*(?:\(|:)|STYLE BIBLE\s*(?:\(|:|preamble)|STYLE GENOME:)/i.test(promptPreamble)) {
      errors.push(`${promptPath}: full-image-deck prompt must start with STYLE GENOME / STYLE LOCK / STYLE BIBLE preamble or assets/generated/style-genome.json reference`);
    }
    const allowsBakedText = /baked-with-overlay|画像内|baked text|text drawn in-image|Japanese text drawn in-image/i.test(prompt);
    const prohibitsText = /Do not include.*(?:readable text|letters|words|numbers|labels)|readable text|overlay-only|画像内テキストは禁止/is.test(prompt);
    if (!allowsBakedText && !prohibitsText) {
      warnings.push(`${promptPath}: prompt should explicitly prohibit readable text or declare baked-with-overlay`);
    }
  }

  if (existsSync(metaPath)) {
    validateMeta(metaPath, stem);
  }
}

for (const metaFile of metas) {
  const stem = basename(metaFile, '.meta.json');
  if (webps.includes(`${stem}.webp`)) continue;
  const metaPath = join(generatedDir, metaFile);
  validateMeta(metaPath, stem);
}

if (fullImageDeck) {
  const expected = expectedSlideCount();
  if (expected) {
    if (metas.length < expected) {
      errors.push(`full-image-deck coverage incomplete: ${metas.length}/${expected} slide meta files found in assets/generated`);
    }
  } else {
    warnings.push('full-image-deck coverage could not infer slide count from structure.md or index.html');
  }
}

// ===== full-image-deck: plan ベースの png/webp 署名検査 =====
// image-deck-plan.json の全スライド(slug)について、<slug>.png と <slug>.webp 双方の
// 署名(中身が本当に画像か)を検査する。webp ループは generatedDir の .webp だけを巡回するため、
// plan に在るのにファイルが欠落/テキスト化したスライドを取りこぼさないよう plan を正本に再検査する。
function checkFullImageDeckSignatures() {
  const planCandidates = [
    join(slideDir, 'image-deck-plan.json'),
    join(generatedDir, 'image-deck-plan.json'),
  ];
  const planPath = planCandidates.find((p) => existsSync(p));
  if (!planPath) return; // plan 不在は上流(D6)で既に FAIL 化済み。
  let plan;
  try {
    plan = JSON.parse(readFileSync(planPath, 'utf8'));
  } catch (error) {
    errors.push(`${planPath}: invalid JSON (${error.message})`);
    return;
  }
  const slides = Array.isArray(plan.slides) ? plan.slides : [];
  for (const slide of slides) {
    const slug = slide && typeof slide.slug === 'string' ? slide.slug : null;
    if (!slug) continue;
    const pngPath = join(generatedDir, `${slug}.png`);
    const webpPath = join(generatedDir, `${slug}.webp`);
    // PNG 署名検査(欠落も含めて検出)。
    if (!existsSync(pngPath)) {
      errors.push(`${slug}.png: full-image-deck plan slide is missing PNG asset`);
    } else {
      checkPngSignature(pngPath, `${slug}.png`);
    }
    // WebP 署名検査。
    if (!existsSync(webpPath)) {
      errors.push(`${slug}.webp: full-image-deck plan slide is missing WebP asset`);
    } else {
      const type = detectImageType(readFileSync(webpPath));
      if (type !== 'webp') {
        errors.push(`${slug}.webp: extension is .webp but file signature is ${type} (content is NOT a WebP; テキスト/壊れの可能性)`);
      }
    }
  }
}
if (fullImageDeck) {
  checkFullImageDeckSignatures();
}

// 第2弾(再現性): 曖昧語リンター + generation/styleReference の妥当性検証。
// gpt-image-2 は seed 非対応のため、曖昧語の排除と再現条件の妥当性が出力の安定に効く。
function runReproducibilityChecks() {
  const requireIntentContract = strictIntent || fullImageDeck;
  const genome = loadGenomeForContent();
  const replacements = (genome && genome.ambiguityReplacements && typeof genome.ambiguityReplacements === 'object') ? genome.ambiguityReplacements : {};
  // D13: builder の VAGUE_PROMPT_WORDS と同期し、量化曖昧語(various/several/appropriate 等)も検出する。
  // builder は plan 段階のフィールドを弾くが、生成後 prompt 本文にも混入させない両側ゲートにする。
  const baseBlacklist = ['beautiful', 'nice', 'good', 'cool', 'high quality', 'detailed', 'stunning', 'amazing', 'balanced', 'well-designed', 'various', 'several', 'some ', 'a few', 'appropriate', 'いい感じ', 'きれい', '適当', 'なんとなく', 'おしゃれ', 'かっこいい', '高品質', '良い感じ', 'バランス良く', '様々な', 'いくつかの', '複数の', '適切な'];
  // genome 自身のスタイル言語に含まれる語は正当な画風語なので除外し誤検出を防ぐ。
  // promptSuffix/negative/anchors/lockTiers に加え、prompt 本文へ注入される genome ガイダンス文
  // (tableAndMatrixRules/contentAdaptationRules/printReadinessRules/artStyle/flowLegendRule/motifs/compositionRules)
  // も対象に含める。例: tableAndMatrixRules.visualBalance に "balanced"、motif 説明文に "several"/"some" が
  // 入っていても誤検出しない(これらは curated な genome 言語で、ビルダーが本文へ注入する)。
  const genomeLang = [
    genome && genome.promptSuffix,
    genome && genome.negativePrompt,
    genome && genome.flowLegendRule,
    JSON.stringify((genome && genome.consistencyAnchors) || []),
    JSON.stringify((genome && genome.lockTiers) || {}),
    JSON.stringify((genome && genome.tableAndMatrixRules) || {}),
    JSON.stringify((genome && genome.contentAdaptationRules) || {}),
    JSON.stringify((genome && genome.printReadinessRules) || {}),
    JSON.stringify((genome && genome.artStyle) || {}),
    JSON.stringify((genome && genome.motifs) || []),
    JSON.stringify((genome && genome.compositionRules) || {}),
  ].join(' ').toLowerCase();
  const vagueWords = Array.from(new Set(baseBlacklist.concat(Object.keys(replacements)))).filter(function (w) { return w && !genomeLang.includes(String(w).toLowerCase()); });
  function intentIssue(msg) { if (strictIntent) errors.push(msg); else warnings.push(msg); }

  const promptFiles = files.filter(function (file) { return file.endsWith('.prompt.md'); });
  for (const promptFile of promptFiles) {
    let prompt;
    try { prompt = readFileSync(join(generatedDir, promptFile), 'utf8'); } catch (e) { continue; }
    const lower = prompt.toLowerCase();
    for (const word of vagueWords) {
      const w = String(word).toLowerCase();
      if (lower.includes(w)) {
        const suggest = replacements[word] || replacements[w];
        intentIssue(promptFile + ': vague word "' + word + '" reduces reproducibility; use a concrete visible attribute' + (suggest ? ' -> suggested: ' + suggest : ''));
      }
    }
    if (requireIntentContract) {
      const requiredPromptLines = [
        ['Purpose', /Purpose\s*\(why this slide exists\)\s*:/i],
        ['Audience takeaway', /Audience takeaway\s*\(one sentence the viewer should grasp\)\s*:/i],
        ['Background / context', /Background\s*\/\s*context\s*:/i],
        ['Layout', /Layout:\s*grid=.*zones=\[.*reading order=.*focal point=/is],
        ['Intended use', /Intended use:\s*.+for slide\s+\d+\s+of a deck\./i],
        ['Geometry lock', /Geometry lock:\s*.+/i],
      ];
      for (const [label, re] of requiredPromptLines) {
        if (!re.test(prompt)) {
          intentIssue(promptFile + ': missing prompt intent contract line: ' + label);
        }
      }
    }
  }

  const allowedQuality = new Set(['auto', 'low', 'medium', 'high']);
  const allowedInherit = new Set(['style-only', 'style-and-layout', 'full']);
  const metaFiles2 = files.filter(function (file) { return file.endsWith('.meta.json'); });
  for (const metaFile of metaFiles2) {
    let meta;
    try { meta = JSON.parse(readFileSync(join(generatedDir, metaFile), 'utf8')); } catch (e) { continue; }
    if (requireIntentContract) {
      for (const key of ['purpose', 'audienceTakeaway', 'background', 'intendedUse', 'layout', 'generation']) {
        if (!(key in meta)) intentIssue(metaFile + ': missing meta intent contract field "' + key + '"');
      }
      if (typeof meta.purpose === 'string' && meta.purpose.trim().length < 12) intentIssue(metaFile + ': purpose is too short to be reproducible');
      if (typeof meta.audienceTakeaway === 'string' && meta.audienceTakeaway.trim().length < 12) intentIssue(metaFile + ': audienceTakeaway is too short to be reproducible');
      if (typeof meta.background === 'string' && meta.background.trim().length < 20) intentIssue(metaFile + ': background is too short to describe context');
      if (meta.layout && typeof meta.layout === 'object') {
        const l = meta.layout;
        const zones = Array.isArray(l.zones) ? l.zones : [];
        const reading = Array.isArray(l.readingOrder) ? l.readingOrder : [];
        if (!l.grid) intentIssue(metaFile + ': layout.grid is required');
        if (zones.length < 2) intentIssue(metaFile + ': layout.zones must contain at least 2 zones');
        if (reading.length < 2) intentIssue(metaFile + ': layout.readingOrder must contain at least 2 areas');
        if (!l.focalPoint) intentIssue(metaFile + ': layout.focalPoint is required');
        if (!l.emphasis) intentIssue(metaFile + ': layout.emphasis is required');
      }
    }
    if (meta.generation && typeof meta.generation === 'object') {
      const g = meta.generation;
      if (g.quality && !allowedQuality.has(g.quality)) intentIssue(metaFile + ': generation.quality "' + g.quality + '" invalid (expected auto|low|medium|high)');
      if (g.size) {
        const mm = String(g.size).match(/^(\d+)x(\d+)$/);
        if (!mm) intentIssue(metaFile + ': generation.size "' + g.size + '" must be WxH (e.g. 2560x1440)');
        else if ((parseInt(mm[1], 10) % 16 !== 0) || (parseInt(mm[2], 10) % 16 !== 0)) intentIssue(metaFile + ': generation.size "' + g.size + '" - gpt-image-2 requires both sides divisible by 16');
      }
    }
    if (meta.styleReference && typeof meta.styleReference === 'object') {
      const sr = meta.styleReference;
      if (sr.inheritMode && !allowedInherit.has(sr.inheritMode)) intentIssue(metaFile + ': styleReference.inheritMode "' + sr.inheritMode + '" invalid (expected style-only|style-and-layout|full)');
      if (Array.isArray(sr.refSlugs) && sr.refSlugs.length > 15) intentIssue(metaFile + ': styleReference.refSlugs has ' + sr.refSlugs.length + ' (max 15)');
    }
    // D10: 支配色(60-30-10の主役色)の prompt 反映を契約化する。builder が meta.dominantAccentHex を
    // 出したスライドは、対応 prompt 本文に「Dominant accent for this slide ... <hex>」行が無ければ
    // 再現性が崩れる(palette 全色羅列への偶発一致ではなく意味照合)。multi/未知色は hex 無しで対象外。
    if (requireIntentContract && typeof meta.dominantAccentHex === 'string' && meta.dominantAccentHex.trim()) {
      const stem = basename(metaFile, '.meta.json');
      const promptPath = join(generatedDir, stem + '.prompt.md');
      if (existsSync(promptPath)) {
        let promptBody = '';
        try { promptBody = readFileSync(promptPath, 'utf8'); } catch (e) { promptBody = ''; }
        const hex = meta.dominantAccentHex.trim().toLowerCase();
        if (!/dominant accent for this slide/i.test(promptBody) || !promptBody.toLowerCase().includes(hex)) {
          intentIssue(metaFile + ': meta.dominantAccentHex ' + meta.dominantAccentHex + ' is not declared as a "Dominant accent for this slide" line in the prompt body (the 60-30-10 lead color must be explicit for reproducibility)');
        }
      }
    }

    // D12: illustrated-full-table は画像内に表を焼き込む。textPolicy=baked-with-overlay 固定で、
    // 各セルが prompt 本文へ verbatim 展開されているかを意味照合する(HTML のピンポイント重ねを使わない方針)。
    if (requireIntentContract && meta.tableMode === 'illustrated-full-table') {
      if (meta.textPolicy !== 'baked-with-overlay') {
        intentIssue(metaFile + ': tableMode=illustrated-full-table requires textPolicy=baked-with-overlay (the table is baked in-image, not HTML-overlaid)');
      }
      if (meta.generation && meta.generation.quality && meta.generation.quality !== 'high') {
        warnings.push(metaFile + ': illustrated-full-table renders dense in-image text; generation.quality should be "high" for legible cells');
      }
      const tc = meta.tableContent;
      if (!tc || typeof tc !== 'object' || !Array.isArray(tc.headers) || !Array.isArray(tc.rows)) {
        intentIssue(metaFile + ': tableMode=illustrated-full-table requires meta.tableContent {headers, rows}');
      } else {
        const stem = basename(metaFile, '.meta.json');
        const promptPath = join(generatedDir, stem + '.prompt.md');
        if (existsSync(promptPath)) {
          let body = '';
          try { body = readFileSync(promptPath, 'utf8'); } catch (e) { body = ''; }
          // D13: caption/note も画像内に焼くため verbatim 照合の対象に含める(builder の buildBakedTableLines と同値)。
          const cells = [...tc.headers, ...tc.rows.flat()];
          if (typeof tc.caption === 'string' && tc.caption.trim()) cells.push(tc.caption.trim());
          if (typeof tc.note === 'string' && tc.note.trim()) cells.push(tc.note.trim());
          const absent = cells.filter((c) => String(c).length > 0 && !body.includes(String(c)));
          if (absent.length > 0) {
            intentIssue(metaFile + ': illustrated-full-table cells/caption/note not found verbatim in prompt body (the table must be baked into the prompt): ' + absent.join(', '));
          }
          // D13: 手書き meta 対策。overlayText に全セル+caption+note が配列要素として完全一致で含まれること
          // (崩れ時の HTML fallback 正本)。builder の validateSlide と同値の検査をここでも行う。
          if (Array.isArray(meta.overlayText)) {
            const overlaySet = new Set(meta.overlayText.map((t) => String(t).trim()));
            const missingOverlay = cells.filter((c) => String(c).trim().length > 0 && !overlaySet.has(String(c).trim()));
            if (missingOverlay.length > 0) {
              intentIssue(metaFile + ': illustrated-full-table overlayText must contain every cell/caption/note as a verbatim array element (HTML fallback source of truth): ' + missingOverlay.join(', '));
            }
          }
        }
      }
    }
  }

  // D8: full-image-deck(複数ページ)で共有 styleReference.anchorSlug が無いとページ間ドリフトの危険。
  // gpt-image-2 は seed 非対応で参照画像チェーンが唯一の画素アンカーのため、デッキ運用時だけ推奨を可視化する
  // (schema 強制必須化はしない・単発差し替えの後方互換を保つ)。
  if (fullImageDeck) {
    let anchored = 0;
    for (const metaFile of metaFiles2) {
      let meta;
      try { meta = JSON.parse(readFileSync(join(generatedDir, metaFile), 'utf8')); } catch (e) { continue; }
      if (meta.styleReference && typeof meta.styleReference === 'object' && meta.styleReference.anchorSlug) anchored += 1;
    }
    if (metaFiles2.length >= 2 && anchored === 0) {
      warnings.push('multi-page full-image-deck without a shared styleReference.anchorSlug risks per-page style drift on seed-less gpt-image-2; set anchorSlug (usually slide-01) on every page');
    }
  }
}
// ===== --gas-check (opt-in・純粋な追加) =====
// GAS(Google Apps Script)は単一HTMLしか配信できず、<img src="assets/generated/...">のような
// 相対パス画像はホストされないため、GAS本番では全 broken になる。ローカルに画像実体があると
// 既存検証は緑判定するため、この相対パス参照を GAS非対応として可視化する。
// 既定は WARN(--gas-check 単独では落とさない=後方互換)。--strict 併用時のみ既存 strict 機構で FAIL 昇格。
function classifyImgRef(ref) {
  // data: は base64 自己完結、http(s): は外部URLで GAS でも配信可能。それ以外はローカル相対参照。
  const trimmed = String(ref).trim();
  if (trimmed === '') return 'empty';
  if (/^data:/i.test(trimmed)) return 'data';
  if (/^https?:/i.test(trimmed) || /^\/\//.test(trimmed)) return 'remote';
  return 'local';
}

function collectImgRefs(html) {
  // <img src> と <source srcset> の参照を全て収集する。srcset は "url 1x, url 2x" 形式を分解。
  const refs = [];
  const srcRe = /<img\s+[^>]*?\bsrc\s*=\s*["']([^"']+)["']/gi;
  let m;
  while ((m = srcRe.exec(html)) !== null) refs.push(m[1]);
  const srcsetRe = /<source\s+[^>]*?\bsrcset\s*=\s*["']([^"']+)["']/gi;
  while ((m = srcsetRe.exec(html)) !== null) {
    for (const candidate of m[1].split(',')) {
      const url = candidate.trim().split(/\s+/)[0];
      if (url) refs.push(url);
    }
  }
  return refs;
}

function loadImageManifest(dir) {
  const manifestPath = join(dir, 'assets', 'generated', 'image-asset-manifest.json');
  if (!existsSync(manifestPath)) return null;
  try {
    return JSON.parse(readFileSync(manifestPath, 'utf8'));
  } catch {
    return null;
  }
}

// manifest 上でローカル参照が「解決済み(GAS配信可能)」かを判定する。
// publicUrl 非空 or top-level assetBaseUrl 非空なら解決済みとみなす。
function isLocalRefResolved(manifest, ref) {
  if (!manifest) return false;
  const assetBaseUrl = typeof manifest.assetBaseUrl === 'string' ? manifest.assetBaseUrl.trim() : '';
  if (assetBaseUrl) return true;
  const filesMap = manifest.files && typeof manifest.files === 'object' ? manifest.files : {};
  // ref を manifest のキー("assets/generated/<name>.<ext>")へ正規化して照合する。
  const normalizedRef = normalize(ref).replace(/^\.\//, '');
  for (const key of Object.keys(filesMap)) {
    const normalizedKey = normalize(key).replace(/^\.\//, '');
    if (normalizedRef === normalizedKey || normalizedRef.endsWith(normalizedKey)) {
      const entry = filesMap[key];
      const publicUrl = entry && typeof entry.publicUrl === 'string' ? entry.publicUrl.trim() : '';
      return publicUrl.length > 0;
    }
  }
  return false;
}

// スタンドアロン GAS チェック。dir 配下のデプロイHTMLと manifest だけを参照し、
// {errors, warnings} を返す純粋関数。generatedDir 不在の早期パスからも、通常フローからも再利用する。
// strict=true(--strict 併用)のときだけ未解決ローカル参照を errors に振り分け、それ以外は warnings。
function runGasCheckStandalone(dir, strict = strictStyleGenome) {
  const localErrors = [];
  const localWarnings = [];
  // 少なくとも index.html。存在すればデプロイ用 HTML も併せて検査する。
  const deployHtmlNames = ['index.html', 'index.deploy.html', 'index-single.html'];
  const manifest = loadImageManifest(dir);
  const unresolvedLocal = new Set();
  let checkedAny = false;
  for (const name of deployHtmlNames) {
    const htmlPath = join(dir, name);
    if (!existsSync(htmlPath)) continue;
    checkedAny = true;
    let html;
    try {
      html = readFileSync(htmlPath, 'utf8');
    } catch {
      continue;
    }
    for (const ref of collectImgRefs(html)) {
      if (classifyImgRef(ref) !== 'local') continue;
      if (!isLocalRefResolved(manifest, ref)) unresolvedLocal.add(`${name} -> ${ref}`);
    }
  }
  if (!checkedAny) {
    localWarnings.push('gas-check: no deploy HTML found (index.html / index.deploy.html / index-single.html); nothing to check for GAS relative-path images.');
    return { errors: localErrors, warnings: localWarnings };
  }
  if (unresolvedLocal.size === 0) return { errors: localErrors, warnings: localWarnings };
  const list = Array.from(unresolvedLocal).join(', ');
  const remedy = 'node scripts/build-image-manifest.js <dir> でmanifest生成 -> 画像をホストし publicUrl記入 or build-single-html.js --inline-images でbase64化 -> 再ビルド';
  const message = `gas-check: ${unresolvedLocal.size} local relative-path image reference(s) will be broken on GAS (single-HTML only, no assets/ hosting): ${list}. 是正手順: ${remedy}`;
  // 既定 WARN。--strict 併用時のみ FAIL 昇格(後方互換のため既定では落とさない)。
  if (strict) localErrors.push(message);
  else localWarnings.push(message);
  return { errors: localErrors, warnings: localWarnings };
}

function runGasCheck() {
  const result = runGasCheckStandalone(slideDir, strictStyleGenome);
  for (const error of result.errors) errors.push(error);
  for (const warning of result.warnings) warnings.push(warning);
}

if (gasCheck) {
  runGasCheck();
}

if (checkGenomeContent) {
  runGenomeContentChecks();
}

// D5: 実HTML層 cross-check は主キャンバスがあれば常時実行(無ければ早期return)。
checkIndexHtmlLayer();

runReproducibilityChecks();

if (webps.length === 0) {
  if (fullImageDeck) {
    errors.push('full-image-deck requires at least one WebP image asset');
  }
  if (checkGenomeContent || gasCheck) {
    for (const warning of warnings) console.warn(`WARN: ${warning}`);
  }
  if (errors.length > 0) {
    for (const error of errors) console.error(`FAIL: ${error}`);
    process.exit(1);
  }
  console.log('PASS: no WebP AI image assets found.');
} else {
  for (const warning of warnings) console.warn(`WARN: ${warning}`);
  if (errors.length > 0) {
    for (const error of errors) console.error(`FAIL: ${error}`);
    process.exit(1);
  }
  console.log(`PASS: ${webps.length} AI image asset(s) validated.`);
}
