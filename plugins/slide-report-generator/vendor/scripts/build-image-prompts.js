#!/usr/bin/env node
/**
 * build-image-prompts.js
 *
 * スタイルゲノム(style-genome.json / 仕様・お手本) と
 * image-deck-plan.json(per-slide 差分) を入力に、
 * 各スライドの prompt.md / meta.json を決定論的に機械展開するビルダー。
 *
 * 設計方針(SSoT: scratchpad/build-spec.md):
 * - 再現性 = 画風・配色・モチーフ・構図ルールという「仕様」を毎回確実にプロンプトへ反映すること。
 *   1px 一致や seed 完全固定は目的ではない。図解の中身はスライドごとに自由。
 * - プレースホルダ {{STYLE_BIBLE}} の手動展開を本スクリプトが埋めてチェーンを閉じる。
 *
 * v8.2.2 で追加(elegant-review・グループC):
 * - D6 builtBy マーカー: 生成 meta に builtBy:"build-image-prompts" を必ず付与し、
 *   手書き meta(マーカー無)を検証側が警告できるようにする(決定論チェーン強制)。
 * - D7 セーフエリア自動計算: genome の compositionRules.safeArea(% 表記)から
 *   2560x1440 基準で px を自動計算し、各 prompt.md / meta.json へ機械挿入する(手計算依存を解消)。
 * - D9 tableMode 推論ヒント: per-slide の tableHints(列数・数値精度・更新頻度・目的)から
 *   推奨 tableMode を補助推論し、表方針(正確な表/料金はHTML前面・概念比較は図解変換優先)を
 *   プロンプトへ織り込む。plan が tableMode を明示していればそれを尊重する(後方互換)。
 *
 * v8.2.3 で追加(reproducible-artifact-prompt):
 * - 画像生成プロンプトを「イラスト依頼」ではなく「スライド成果物仕様」として固定する。
 *   purpose / audienceTakeaway / background / intendedUse / layout / generation を plan 必須にし、
 *   目的・背景・構図・視線順・生成条件が空のまま codex/imagegen へ渡らないようにする。
 * - 曖昧語(beautiful/high quality/おしゃれ等)と短すぎる subject / diagramStructure を plan 段階で止め、
 *   100人中100人が同じ構成を読める程度の具体記述に寄せる。
 *
 * v8.2.4 で追加(elegant-review 第2弾):
 * - D10 支配色(accent)射影: per-slide accent を HEX 解決し「Dominant accent for this slide」行を
 *   本文へ機械展開する。従来 accent は schema 必須・meta 記録のみで本文に出ず、60-30-10 の主役色が
 *   未指定だった(全色羅列のみ)。meta.dominantAccentHex も併記し、validator が支配色の prompt 反映を
 *   偶発一致でなく意味照合できるようにする。あわせて量化曖昧語(various/several/appropriate 等)を
 *   VAGUE_PROMPT_WORDS に限定追加する(clean/simple は genome 画風語と衝突するため足さない)。
 * - D11 構造系スライドの負制約必須化: camera=structural(順序/向き/個数が効く図)は negativeSpecific を
 *   必須化(20字以上)。schema allOf と同値の assert を validateSlide にも置き、何を間違えてはいけないか
 *   (誤ノード数・逆向き・対称崩れ)を毎回宣言させる。
 *
 * v8.2.5 で追加(baked-table・D12):
 * - 画像内焼き込みテーブルモード illustrated-full-table を追加。従来の「画像は空枠だけ生成し
 *   実テキストはHTMLで重ねる(html-overlay-table)」運用は HTML 重ねがズレて空白枠+浮き表の二重表示
 *   になる不具合があった。gpt-image-2 は日本語+短い英数字のセル文字を verbatim に焼き込めるため、
 *   tableContent{headers, rows[][], monospaceColumns?, caption?, note?} を per-slide で受け取り、
 *   列数/行数明示・各セル verbatim 引用・罫線/整列/legible・行列増減禁止 の決定論テーブルブロックを
 *   本文へ展開する。textPolicy=baked-with-overlay 固定、overlayText に表全文を正本保持(崩れ時 fallback)。
 *   正確な料金/精密数値/長文/複数行コードは引き続き html-overlay-table / html-primary に寄せる。
 *
 * v8.2.6 で追加(elegant-review 再検証・D13):
 * - illustrated-full-table を negativeSpecific 必須化(表は行数/列数の取り違えが意味崩壊に直結する
 *   最も構造的な対象。camera=structural と同じく負制約を毎回宣言させる。schema allOf と同値)。
 * - overlayText の fallback 照合を「配列要素の完全一致(trim 後)」に厳格化し、caption/note も対象に含める。
 *   従来の部分一致(includes)は短セル("例"/"数秒")が無関係文字列に偶発一致して骨抜きになっていた。
 * - tableContent.monospaceColumns に列数を超えるインデックスが無いか範囲検査(0..cols-1)を追加。
 * - accent が "multi"/palette キー/HEX のいずれでもない場合に警告(D10 意味照合が静かにスキップされる
 *   タイポの抜け道を可視化。致命的ではない)。
 *
 * 使用方法:
 *   node scripts/build-image-prompts.js <slide-dir> [--plan <path>] [--genome <path>] \
 *        [--only slide-06,slide-15] [--check] [--source codex-image2]
 *
 *   --plan    既定: <slide-dir>/assets/generated/image-deck-plan.json
 *   --genome  既定: <slide-dir>/assets/generated/style-genome.json
 *             無ければ同梱 assets/style-genome-kanagawa-comic-diagram.json
 *   --only    指定 slug(または slide 番号)のみ再生成。カンマ区切り。
 *   --check   ファイルを書かず、生成結果と既存ファイルの差分サマリだけ出力(破壊しない)。
 *   --source  meta.json の source 値(既定: codex-image2)。
 *
 * 自己テスト(必須・冒頭コメント記載):
 *   1. テスト用 slide-dir を作り assets/generated/ に
 *      style-genome.json(= 同梱 kanagawa ゲノムのコピー)と
 *      image-deck-plan.json(= scripts/test-fixtures/image-deck-plan.sample.json)を置く。
 *   2. node scripts/build-image-prompts.js <test-deck>
 *   3. node scripts/validate-ai-image-assets.js <test-deck> --strict-style-genome --check-genome-content --strict-intent
 *      が PASS することを確認する。--strict-intent を付けないと D10(支配色)・D12(焼き込み表)の
 *      意味照合が発火しないため、自己テストでは必ず付ける。
 *   4. node scripts/test-schema-builder-equivalence.js が PASS することを確認する(D13)。
 *      schema allOf と本ファイルの validateSlide の「同値」二重宣言がドリフトしていないかを
 *      機械検証する回帰テスト。片方だけ編集して閾値・トリガが食い違うと FAIL する。
 */

import { existsSync, readFileSync, writeFileSync, mkdirSync } from 'fs';
import { dirname, join, isAbsolute, resolve } from 'path';
import { fileURLToPath } from 'url';

const skillDir = join(dirname(fileURLToPath(import.meta.url)), '..');

const VALUE_FLAGS = new Set(['plan', 'genome', 'only', 'source']);

const TEXT_POLICY_PROMPT = {
  'baked-with-overlay':
    'draw the specified short Japanese labels/headings inside the image, crisp and undistorted; overlayText remains the source of truth (HTML fallback on distortion).',
  'overlay-only':
    'do not draw any readable text in the image; all headings/labels are overlaid via HTML (overlayText is the source of truth).',
  'none': 'no in-image text concept (html-primary).',
};

const COHERENT_TEXT_POLICY = {
  'image-only': new Set(['baked-with-overlay', 'overlay-only']),
  'html-composite': new Set(['overlay-only']),
  'html-primary': new Set(['none']),
};

const COHERENT_BACKGROUND_SOURCE = {
  'image-only': new Set(['none']),
  'html-composite': new Set(['raster', 'svg']),
  'html-primary': new Set(['none', 'svg']),
};

const DENSITY_LEVELS = new Set(['low', 'medium', 'high']);
const ROBOT_MASCOT_VARIANTS = new Set(['none', 'full-body', 'floating-head', 'upper-body-clipboard']);
const TABLE_MODES = new Set(['none', 'illustrated-mini-table', 'illustrated-full-table', 'html-overlay-table', 'diagram-translation', 'html-primary']);
// D12: 焼き込みテーブルのセル/見出しの最大文字数。これを超える表は崩れやすいため html 系へ誘導する。
const FULL_TABLE_CELL_MAXLEN = 14;
const IMAGE_FIT_MODES = new Set(['contain', 'cover-safe', 'html-composite-contain']);
const LAYOUT_GRIDS = new Set(['left-right', 'top-bottom', 'center-radial', 'grid-2x2', 'free']);
const LAYOUT_AREAS = new Set(['top', 'bottom', 'left', 'right', 'center', 'foreground', 'background']);

const VAGUE_PROMPT_WORDS = [
  'beautiful',
  'nice',
  'good',
  'cool',
  'high quality',
  'detailed',
  'stunning',
  'amazing',
  'balanced',
  'well-designed',
  'いい感じ',
  'きれい',
  '適当',
  'なんとなく',
  'おしゃれ',
  'かっこいい',
  '高品質',
  '良い感じ',
  'バランス良く',
  // D10: 量化曖昧語(数・量が不定)。clean/simple/minimal/modern 等は genome 画風語と衝突し
  // 誤検出するため足さない(builder の requireConcreteText には validator のような genomeLang 除外が無い)。
  'various',
  'several',
  'some ',
  'a few',
  'appropriate',
  '様々な',
  'いくつかの',
  '複数の',
  '適切な',
];

// このビルダーが生成した meta であることを示すマーカー(D6: 決定論チェーン強制)。
// 手書き meta(マーカー無)を検証側が警告できるよう、全 meta に必ず付与する。
const BUILDER_MARKER = 'build-image-prompts';

// D7: セーフエリア自動計算の基準(2560x1440)。手計算依存を解消する。
const SAFE_AREA_BASIS = { width: 2560, height: 1440 };
// genome に safeArea 値が無いときの既定(上下8% / 左右6%)。
const SAFE_AREA_DEFAULT_PERCENT = { vertical: 8, horizontal: 6 };

/**
 * genome の safeArea 表記から px 値を自動計算する(D7・要求E)。
 * compositionRules.safeArea は通常 "top/bottom 8%, left/right 6%" 形式の文字列。
 * パーセントが読めれば 2560x1440 基準で px 換算し、読めなければ既定(8%/6%)を使う。
 * 戻り値: { topBottomPercent, leftRightPercent, topBottomPx, leftRightPx, source }
 */
function computeSafeAreaPx(genome) {
  const c = genome.compositionRules || {};
  let vPct = SAFE_AREA_DEFAULT_PERCENT.vertical;
  let hPct = SAFE_AREA_DEFAULT_PERCENT.horizontal;
  let source = 'default';

  const raw = c.safeArea;
  if (raw && typeof raw === 'object') {
    // 数値オブジェクト形式 { topBottomPercent, leftRightPercent } 等にも将来対応。
    const v = Number(raw.topBottomPercent ?? raw.vertical);
    const h = Number(raw.leftRightPercent ?? raw.horizontal);
    if (Number.isFinite(v) && Number.isFinite(h)) {
      vPct = v;
      hPct = h;
      source = 'genome';
    }
  } else if (typeof raw === 'string' && raw.length > 0) {
    // "top/bottom 8%, left/right 6%" 形式をラベル付きで抽出。順序非依存。
    const vMatch = raw.match(/top\s*\/?\s*bottom[^0-9]*([0-9]+(?:\.[0-9]+)?)\s*%/i);
    const hMatch = raw.match(/left\s*\/?\s*right[^0-9]*([0-9]+(?:\.[0-9]+)?)\s*%/i);
    if (vMatch && hMatch) {
      vPct = Number(vMatch[1]);
      hPct = Number(hMatch[1]);
      source = 'genome';
    } else {
      // ラベルが無く数値が2つだけ並ぶ場合は [vertical, horizontal] の順とみなす。
      const nums = raw.match(/([0-9]+(?:\.[0-9]+)?)\s*%/g);
      if (nums && nums.length >= 2) {
        vPct = parseFloat(nums[0]);
        hPct = parseFloat(nums[1]);
        source = 'genome';
      }
    }
  }

  const topBottomPx = Math.round((SAFE_AREA_BASIS.height * vPct) / 100);
  const leftRightPx = Math.round((SAFE_AREA_BASIS.width * hPct) / 100);
  return {
    topBottomPercent: vPct,
    leftRightPercent: hPct,
    topBottomPx,
    leftRightPx,
    source,
  };
}

/**
 * D7: 各 prompt.md へ機械挿入するセーフエリア指示文を生成する。
 * 手計算した px をプロンプトへ埋め込み、object-fit:contain 前提を明記する。
 */
function safeAreaPromptLine(safe) {
  return (
    `Safe area (auto-computed from genome safeArea = top/bottom ${safe.topBottomPercent}% / left/right ${safe.leftRightPercent}% at 16:9 2560x1440): ` +
    `keep important subjects within safe margins: left/right ${safe.leftRightPx}px, top/bottom ${safe.topBottomPx}px; ` +
    `rendered with object-fit:contain in HTML, no important subject at outer edges.`
  );
}

/**
 * D9: 内容ヒント(列数・数値精度・更新頻度)から推奨 tableMode を補助推論する。
 * plan が tableMode を明示していればそれを尊重し、推論は補助ヒントとしてのみ返す。
 * 方針: 正確な表・料金は HTML 前面(html-overlay-table / html-primary)、
 *       概念比較は diagram-translation 優先、短い簡易表は illustrated-mini-table。
 * 戻り値: { recommended, reasons[] } または tableHints 不在時 null。
 */
function inferTableMode(slide) {
  const hints = slide.tableHints;
  if (!hints || typeof hints !== 'object') return null;
  const reasons = [];
  const columns = Number(hints.columns);
  const rows = Number(hints.rows);
  const precision = String(hints.numericPrecision || hints.precision || '').toLowerCase();
  const updateFreq = String(hints.updateFrequency || hints.updateFreq || '').toLowerCase();
  const purpose = String(hints.purpose || '').toLowerCase();

  let recommended = null;

  // 概念比較・判断軸は図解変換を優先(罫線を主役にしない)。
  if (/compar|concept|judg|axis|classif|比較|概念|判断|分類/.test(purpose)) {
    recommended = 'diagram-translation';
    reasons.push('purpose is conceptual comparison/judgment -> diagram-translation preferred');
  }

  // 正確な数値・料金・固有名詞、または頻繁更新は HTML 前面で正確性を担保。
  const precise = /exact|high|precise|price|fee|正確|料金|高/.test(precision);
  const volatile = /high|frequent|often|monthly|weekly|頻繁|高/.test(updateFreq);
  if (precise || volatile) {
    // 1文字の正確性が中心で大きい表は html-primary、世界観を残すなら html-overlay-table。
    if ((Number.isFinite(columns) && columns >= 5) || (Number.isFinite(rows) && rows > 8)) {
      recommended = 'html-primary';
      reasons.push('precise/volatile content with many columns/rows -> html-primary (HTML is source of truth)');
    } else {
      recommended = 'html-overlay-table';
      reasons.push('precise/volatile numbers/prices -> html-overlay-table (world-tone background + HTML real table on top)');
    }
  } else if (!recommended) {
    // 短語中心・小さい表は画像内ミニ表で世界観を保つ。
    if (Number.isFinite(columns) && columns <= 3 && Number.isFinite(rows) && rows <= 4) {
      recommended = 'illustrated-mini-table';
      reasons.push('short table within 3 columns x 4 rows -> illustrated-mini-table inside the diorama');
    } else if (Number.isFinite(rows) && rows > 5) {
      recommended = 'html-overlay-table';
      reasons.push('more than 5 rows -> html-overlay-table to keep readability');
    }
  }

  if (!recommended) return null;
  return { recommended, reasons };
}

function usage() {
  console.error(
    'Usage: node scripts/build-image-prompts.js <slide-dir> [--plan <path>] [--genome <path>] [--only slug,...] [--check] [--source <name>]'
  );
  process.exit(2);
}

function parseArgs(argv) {
  const flags = {};
  const positional = [];
  for (let i = 0; i < argv.length; i += 1) {
    const arg = argv[i];
    if (arg.startsWith('--')) {
      const eq = arg.indexOf('=');
      if (eq !== -1) {
        flags[arg.slice(2, eq)] = arg.slice(eq + 1);
      } else {
        const name = arg.slice(2);
        if (VALUE_FLAGS.has(name)) {
          flags[name] = argv[i + 1];
          i += 1;
        } else {
          flags[name] = true;
        }
      }
    } else {
      positional.push(arg);
    }
  }
  return { flags, positional };
}

function resolveFromCwd(value) {
  return isAbsolute(value) ? value : resolve(process.cwd(), value);
}

function resolveGenomePath(genomeFlag, generatedDir) {
  if (genomeFlag) {
    const explicit = resolveFromCwd(genomeFlag);
    if (!existsSync(explicit)) {
      console.error(`FAIL: genome not found: ${explicit}`);
      process.exit(1);
    }
    return explicit;
  }
  const projectLocal = join(generatedDir, 'style-genome.json');
  if (existsSync(projectLocal)) return projectLocal;
  const bundled = join(skillDir, 'assets', 'style-genome-kanagawa-comic-diagram.json');
  if (existsSync(bundled)) return bundled;
  console.error('FAIL: no style genome found (project-local or bundled)');
  process.exit(1);
  return null;
}

function readJson(path, label) {
  try {
    return JSON.parse(readFileSync(path, 'utf8'));
  } catch (error) {
    console.error(`FAIL: cannot read ${label} (${path}): ${error.message}`);
    process.exit(1);
    return null;
  }
}

function requireConcreteText(errs, where, key, value, minLength) {
  if (typeof value !== 'string' || value.trim().length < minLength) {
    errs.push(`${where}: "${key}" must be a concrete sentence (${minLength}+ chars)`);
    return;
  }
  const lower = value.toLowerCase();
  for (const word of VAGUE_PROMPT_WORDS) {
    if (lower.includes(String(word).toLowerCase())) {
      errs.push(`${where}: "${key}" contains vague word "${word}"; replace it with visible attributes, objects, positions, or constraints`);
    }
  }
}

function validateLayout(slide, errs, where) {
  const layout = slide.layout;
  if (!layout || typeof layout !== 'object' || Array.isArray(layout)) {
    errs.push(`${where}: missing required object "layout" (grid/zones/readingOrder/focalPoint/emphasis)`);
    return;
  }
  if (!LAYOUT_GRIDS.has(layout.grid)) {
    errs.push(`${where}: layout.grid "${layout.grid}" invalid (expected ${[...LAYOUT_GRIDS].join(' | ')})`);
  }
  if (!Array.isArray(layout.zones) || layout.zones.length < 2) {
    errs.push(`${where}: layout.zones must contain at least 2 zones so the composition is unambiguous`);
  }
  const zoneAreas = new Set();
  if (Array.isArray(layout.zones)) {
    for (const z of layout.zones) {
      if (!z || typeof z !== 'object') {
        errs.push(`${where}: layout.zones contains a non-object item`);
        continue;
      }
      if (!LAYOUT_AREAS.has(z.area)) {
        errs.push(`${where}: layout zone area "${z.area}" invalid (expected ${[...LAYOUT_AREAS].join(' | ')})`);
      } else {
        zoneAreas.add(z.area);
      }
      requireConcreteText(errs, where, `layout.zones[${z.area || '?'}].content`, z.content, 2);
    }
  }
  if (!Array.isArray(layout.readingOrder) || layout.readingOrder.length < 2) {
    errs.push(`${where}: layout.readingOrder must contain at least 2 areas`);
  } else {
    for (const area of layout.readingOrder) {
      if (!LAYOUT_AREAS.has(area)) {
        errs.push(`${where}: layout.readingOrder contains invalid area "${area}"`);
      } else if (zoneAreas.size > 0 && !zoneAreas.has(area)) {
        errs.push(`${where}: layout.readingOrder area "${area}" has no matching layout.zones entry`);
      }
    }
  }
  if (!LAYOUT_AREAS.has(layout.focalPoint)) {
    errs.push(`${where}: layout.focalPoint "${layout.focalPoint}" invalid (expected ${[...LAYOUT_AREAS].join(' | ')})`);
  } else if (zoneAreas.size > 0 && !zoneAreas.has(layout.focalPoint)) {
    errs.push(`${where}: layout.focalPoint "${layout.focalPoint}" has no matching layout.zones entry`);
  }
  requireConcreteText(errs, where, 'layout.emphasis', layout.emphasis, 6);
}

function validateGeneration(slide, errs, where) {
  const generation = slide.generation;
  if (!generation || typeof generation !== 'object' || Array.isArray(generation)) {
    errs.push(`${where}: missing required object "generation" (modelSnapshot/quality/size)`);
    return;
  }
  if (typeof generation.modelSnapshot !== 'string' || generation.modelSnapshot.trim().length < 1) {
    errs.push(`${where}: generation.modelSnapshot is required`);
  }
  if (!['auto', 'low', 'medium', 'high'].includes(generation.quality)) {
    errs.push(`${where}: generation.quality "${generation.quality}" invalid (expected auto | low | medium | high)`);
  }
  const size = String(generation.size || '');
  const match = size.match(/^(\d+)x(\d+)$/);
  if (!match) {
    errs.push(`${where}: generation.size "${size}" must be WxH (e.g. 2560x1440)`);
    return;
  }
  const width = Number(match[1]);
  const height = Number(match[2]);
  const long = Math.max(width, height);
  const short = Math.min(width, height);
  const pixels = width * height;
  if (width % 16 !== 0 || height % 16 !== 0) {
    errs.push(`${where}: generation.size "${size}" must have both sides divisible by 16`);
  }
  if (long / short > 3) {
    errs.push(`${where}: generation.size "${size}" exceeds 3:1 aspect ratio limit`);
  }
  if (pixels < 655360 || pixels > 8294400) {
    errs.push(`${where}: generation.size "${size}" must be between 655,360 and 8,294,400 pixels for reliable gpt-image-2 generation`);
  }
}

// plan の各スライドを検証(スキーマと同じ規約をビルダー側でも assert する)
function validateSlide(slide, motifNames, layoutNames, paletteKeys) {
  const errs = [];
  const where = `slide ${slide.slide ?? '?'} (${slide.slug ?? 'no-slug'})`;
  for (const key of [
    'slide',
    'slug',
    'pattern',
    'textPolicy',
    'backgroundSource',
    'camera',
    'accent',
    'subject',
    'diagramStructure',
    'motifs',
    'overlayText',
    'purpose',
    'audienceTakeaway',
    'background',
    'intendedUse',
    'layout',
    'generation',
    'reason',
    'alt',
  ]) {
    if (slide[key] === undefined || slide[key] === null) {
      errs.push(`${where}: missing required field "${key}"`);
    }
  }
  if (!['image-only', 'html-composite', 'html-primary'].includes(slide.pattern)) {
    errs.push(`${where}: invalid pattern "${slide.pattern}"`);
  }
  if (!['baked-with-overlay', 'overlay-only', 'none'].includes(slide.textPolicy)) {
    errs.push(`${where}: invalid textPolicy "${slide.textPolicy}"`);
  }
  if (!['raster', 'svg', 'none'].includes(slide.backgroundSource)) {
    errs.push(`${where}: invalid backgroundSource "${slide.backgroundSource}"`);
  }
  if (!['default', 'structural'].includes(slide.camera)) {
    errs.push(`${where}: invalid camera "${slide.camera}" (expected default | structural)`);
  }
  // D13: accent のタイポ検出(警告)。"multi" / palette キー / HEX のいずれでもない文字列は
  // 支配色 HEX が解決されず(resolveDominantAccent が hex=null)、validator の D10 意味照合が静かに
  // スキップされる抜け道になる。意図的な multi と事故的な未知文字列を分離するため可視化する(致命的ではない)。
  if (typeof slide.accent === 'string') {
    const acc = slide.accent.trim();
    const isHex = /^#?[0-9a-fA-F]{6}$/.test(acc);
    const isKnownKey = paletteKeys instanceof Set && paletteKeys.has(acc);
    if (acc && acc !== 'multi' && !isHex && !isKnownKey) {
      console.warn(`WARN: ${where}: accent "${acc}" is not "multi", a palette key, or a HEX color; the dominant-accent reproducibility check (D10) will be skipped for this slide (possible typo)`);
    }
  }
  // pattern x textPolicy 整合
  const allowedTp = COHERENT_TEXT_POLICY[slide.pattern];
  if (allowedTp && !allowedTp.has(slide.textPolicy)) {
    errs.push(
      `${where}: textPolicy "${slide.textPolicy}" not allowed for pattern "${slide.pattern}" (expected ${[...allowedTp].join(' | ')})`
    );
  }
  // pattern x backgroundSource 整合
  const allowedBg = COHERENT_BACKGROUND_SOURCE[slide.pattern];
  if (allowedBg && !allowedBg.has(slide.backgroundSource)) {
    errs.push(
      `${where}: backgroundSource "${slide.backgroundSource}" not allowed for pattern "${slide.pattern}" (expected ${[...allowedBg].join(' | ')})`
    );
  }
  // baked-with-overlay は bakedText 必須
  if (slide.textPolicy === 'baked-with-overlay' && (!Array.isArray(slide.bakedText) || slide.bakedText.length === 0)) {
    errs.push(`${where}: textPolicy=baked-with-overlay requires non-empty bakedText`);
  }
  // overlayText 必須
  if (!Array.isArray(slide.overlayText) || slide.overlayText.length === 0) {
    errs.push(`${where}: overlayText must be a non-empty array`);
  }
  // motifs は genome の motifs[].name の部分集合
  if (Array.isArray(slide.motifs)) {
    for (const name of slide.motifs) {
      if (!motifNames.has(name)) {
        errs.push(`${where}: motif "${name}" is not defined in style genome motifs[]`);
      }
    }
  }
  if (slide.densityLevel && !DENSITY_LEVELS.has(slide.densityLevel)) {
    errs.push(`${where}: invalid densityLevel "${slide.densityLevel}" (expected low | medium | high)`);
  }
  if (slide.robotMascot && !ROBOT_MASCOT_VARIANTS.has(slide.robotMascot)) {
    errs.push(`${where}: invalid robotMascot "${slide.robotMascot}"`);
  }
  if (slide.tableMode && !TABLE_MODES.has(slide.tableMode)) {
    errs.push(`${where}: invalid tableMode "${slide.tableMode}"`);
  }
  // D9: tableHints は任意。存在する場合はオブジェクトであることだけ assert する(中身は補助推論用)。
  if (slide.tableHints !== undefined && (typeof slide.tableHints !== 'object' || Array.isArray(slide.tableHints) || slide.tableHints === null)) {
    errs.push(`${where}: tableHints must be an object when present`);
  }
  if (slide.imageFit && !IMAGE_FIT_MODES.has(slide.imageFit)) {
    errs.push(`${where}: invalid imageFit "${slide.imageFit}" (expected contain | cover-safe | html-composite-contain)`);
  }
  if (slide.layoutTemplate && layoutNames.size > 0 && !layoutNames.has(slide.layoutTemplate)) {
    errs.push(`${where}: layoutTemplate "${slide.layoutTemplate}" is not defined in style genome compositionRules.layoutTemplates`);
  }
  requireConcreteText(errs, where, 'purpose', slide.purpose, 12);
  requireConcreteText(errs, where, 'audienceTakeaway', slide.audienceTakeaway, 12);
  requireConcreteText(errs, where, 'background', slide.background, 20);
  requireConcreteText(errs, where, 'intendedUse', slide.intendedUse, 20);
  requireConcreteText(errs, where, 'subject', slide.subject, 40);
  requireConcreteText(errs, where, 'diagramStructure', slide.diagramStructure, 40);
  validateLayout(slide, errs, where);
  validateGeneration(slide, errs, where);
  // コード系は image-only / baked-with-overlay 不可(既存 V-043 と整合)
  const codeLike = /code/i.test(slide.slug || '') || /code/i.test(slide.type || slide.slideType || '');
  if (codeLike && (slide.pattern === 'image-only' || slide.textPolicy === 'baked-with-overlay')) {
    errs.push(`${where}: code-type slide cannot use image-only / baked-with-overlay (use html-composite/html-primary)`);
  }
  if (Array.isArray(slide.bakedText)) {
    for (const text of slide.bakedText) {
      if (String(text).trim().length > 18) {
        errs.push(`${where}: bakedText "${text}" is too long for reliable in-image text; use 1-4 short words and put long text in overlayText`);
      }
    }
  }
  // D11: camera=structural(順序/向き/個数が効く図)は主題正しさの負制約 negativeSpecific を必須化する。
  // schema allOf と同値(トリガ camera=structural・最小20字)。schema 検証を経ない builder 単体実行でも守る。
  if (slide.camera === 'structural' && (typeof slide.negativeSpecific !== 'string' || slide.negativeSpecific.trim().length < 20)) {
    errs.push(`${where}: camera=structural slide requires negativeSpecific (20+ chars) stating what must NOT be drawn (wrong element count, wrong direction, broken symmetry)`);
  }
  // D12: illustrated-full-table の追加契約。schema allOf と同値の二重宣言(builder 単体実行でも守る)。
  // tableContent 必須・列行整合・セル短語(<=14字)・textPolicy=baked-with-overlay・overlayText に全セル(fallback正本)。
  if (slide.tableMode === 'illustrated-full-table') {
    const tc = slide.tableContent;
    if (!tc || typeof tc !== 'object' || Array.isArray(tc)) {
      errs.push(`${where}: tableMode=illustrated-full-table requires object "tableContent" {headers, rows}`);
    } else {
      const cols = Array.isArray(tc.headers) ? tc.headers.length : 0;
      if (cols < 1) errs.push(`${where}: tableContent.headers must be a non-empty array`);
      if (!Array.isArray(tc.rows) || tc.rows.length < 1) {
        errs.push(`${where}: tableContent.rows must be a non-empty array`);
      } else {
        tc.rows.forEach((r, i) => {
          if (!Array.isArray(r) || r.length !== cols) {
            errs.push(`${where}: tableContent.rows[${i}] must have exactly ${cols} cell(s) to match headers`);
          }
        });
      }
      const allCells = [
        ...(Array.isArray(tc.headers) ? tc.headers : []),
        ...((Array.isArray(tc.rows) ? tc.rows : []).flat()),
      ];
      for (const cell of allCells) {
        if (String(cell).length > FULL_TABLE_CELL_MAXLEN) {
          errs.push(`${where}: tableContent cell "${cell}" exceeds ${FULL_TABLE_CELL_MAXLEN} chars; baked tables need short cells. Fix: set this slide's tableMode to "html-overlay-table" (keep the full table in overlayText as a front HTML layer) or shorten the cell. See references/style-genome-packaging.md table section.`);
        }
      }
      // D13: monospaceColumns は 0..cols-1 の範囲内であること(列数を超えるインデックスは
      // 存在しない列を指す不整合な焼き込み指示になるため止める。schema は draft-07 で動的上限を
      // 表現できないため builder 側 assert を正本にする)。
      if (Array.isArray(tc.monospaceColumns)) {
        for (const idx of tc.monospaceColumns) {
          if (!Number.isInteger(idx) || idx < 0 || idx >= cols) {
            errs.push(`${where}: tableContent.monospaceColumns index ${idx} is out of range (expected 0..${cols - 1} for ${cols} column(s))`);
          }
        }
      }
      // D13: overlayText に全セル + caption/note が fallback 正本として含まれること(崩れ時 HTML 表示できる)。
      // 部分一致(includes)は短セル("例"/"数秒")が無関係文字列に偶発一致して骨抜きになるため、
      // overlayText の配列要素との完全一致(trim 後)で判定する。caption/note も画像内に焼くので対象に含める。
      const fallbackCells = [...allCells];
      if (typeof tc.caption === 'string' && tc.caption.trim()) fallbackCells.push(tc.caption.trim());
      if (typeof tc.note === 'string' && tc.note.trim()) fallbackCells.push(tc.note.trim());
      if (Array.isArray(slide.overlayText) && fallbackCells.length > 0) {
        const overlaySet = new Set(slide.overlayText.map((t) => String(t).trim()));
        const missing = fallbackCells.filter((c) => String(c).trim().length > 0 && !overlaySet.has(String(c).trim()));
        if (missing.length > 0) {
          errs.push(`${where}: overlayText must contain every table cell, caption, and note as a verbatim array element (fallback source of truth); missing: ${missing.join(', ')}`);
        }
      }
    }
    if (slide.textPolicy !== 'baked-with-overlay') {
      errs.push(`${where}: tableMode=illustrated-full-table requires textPolicy=baked-with-overlay (the table is in-image text)`);
    }
    // D13: 表は行数/列数の取り違えが意味崩壊に直結する最も構造的な対象。camera=structural と同じく
    // negativeSpecific を必須化し、行列の増減/結合/順序入替を毎回宣言させる(schema allOf と同値)。
    if (typeof slide.negativeSpecific !== 'string' || slide.negativeSpecific.trim().length < 20) {
      errs.push(`${where}: tableMode=illustrated-full-table requires negativeSpecific (20+ chars) stating the row/column count must not change and no merged, dropped, added, reordered, or garbled cells`);
    }
  }
  return errs;
}

function cameraStringFor(slide, genome) {
  const cam = genome.artStyle.camera || {};
  return cam[slide.camera] || cam.default || '';
}

function metaCameraLabel(slide) {
  return slide.camera === 'structural' ? '微俯瞰15度' : '30度アイソメ';
}

/**
 * D10: per-slide accent(支配色)を解決し、プロンプト本文へ射影する1行と meta 記録用 HEX を返す。
 * accent は schema 必須だが従来 buildPrompt 本文に出ず、60-30-10 の主役色が未指定だった。
 * 解決規則(優先順):
 *   (1) "multi"            -> 1ゾーン1アクセント + 1色が60%を担う指示(単一HEXは無いので hex=null)
 *   (2) palette キー名     -> genome.palette[accent].{name,hex}
 *   (3) #RRGGBB / RRGGBB  -> その HEX をそのまま
 *   (4) 未知の文字列       -> 文字列そのまま(HEX アンカー無し)
 * 戻り値: { hex, line }。hex は meta.dominantAccentHex として記録し validator が意味照合に使う。
 * buildPrompt / buildMeta から同一入力で呼ぶため純粋関数にする。
 */
function resolveDominantAccent(slide, genome) {
  const accent = typeof slide.accent === 'string' ? slide.accent.trim() : '';
  if (!accent) return { hex: null, line: null };
  if (accent === 'multi') {
    return {
      hex: null,
      line: 'Dominant accent for this slide: multi-accent - assign one accent color per zone, but one single color must still carry the 60% so the page is not evenly multicolored.',
    };
  }
  const pal = genome.palette && genome.palette[accent];
  if (pal && typeof pal === 'object' && typeof pal.hex === 'string') {
    return {
      hex: pal.hex,
      line: `Dominant accent for this slide (the 10-percent lead color in the 60-30-10 split): ${pal.name || accent} ${pal.hex}; every other palette color stays subordinate.`,
    };
  }
  if (/^#?[0-9a-fA-F]{6}$/.test(accent)) {
    const hex = accent.startsWith('#') ? accent : `#${accent}`;
    return {
      hex,
      line: `Dominant accent for this slide (the 10-percent lead color in the 60-30-10 split): ${hex}; every other palette color stays subordinate.`,
    };
  }
  return {
    hex: null,
    line: `Dominant accent for this slide (the 10-percent lead color in the 60-30-10 split): ${accent}; every other palette color stays subordinate.`,
  };
}

/**
 * D12: illustrated-full-table のとき、tableContent から「見出し+全行を verbatim に画像内へ焼く」
 * 決定論テーブルブロック(英語の行配列)を組む。
 * 再現性の要点(外部リサーチ準拠): 列数/行数を数値で明示、各セルを二重引用で verbatim 指定、
 * 罫線/整列/legible を機能語で要求、行列の増減/重複/捏造を禁止、配色は genome の palette/accent から解決。
 * gpt-image-2 は seed 非対応なので、再現性はこの逐語固定 + quality=high + 参照画像チェーンで担保する。
 */
function buildBakedTableLines(slide, genome, dominantAccent) {
  const tc = slide.tableContent;
  if (!tc || typeof tc !== 'object' || !Array.isArray(tc.headers) || !Array.isArray(tc.rows)) return [];
  const cols = tc.headers.length;
  const rowCount = tc.rows.length;
  const q = (s) => `"${String(s)}"`;
  const surfaceHex = (genome.palette && genome.palette.surface && genome.palette.surface.hex) || '#E8E8EC';
  const inkHex = (genome.palette && genome.palette.ink && genome.palette.ink.hex) || '#0B2A55';
  const headerFill = dominantAccent && dominantAccent.hex ? dominantAccent.hex : 'the slide dominant accent';
  const lines = [];
  lines.push(
    `In-image baked table (illustrated-full-table): draw a real, readable table INSIDE the image as a rounded isometric card; do NOT leave an empty frame and do NOT rely on an HTML overlay for the cells. The table has exactly ${cols} column(s) and ${rowCount} body row(s) plus 1 header row.`
  );
  lines.push(
    `Header row, left to right, drawn verbatim in double quotes exactly as written (do not translate, do not add or drop characters): ${tc.headers.map(q).join(' | ')}.`
  );
  tc.rows.forEach((r, i) => {
    const cells = Array.isArray(r) ? r : [];
    lines.push(`Row ${i + 1}, left to right, verbatim: ${cells.map(q).join(' | ')}.`);
  });
  if (Array.isArray(tc.monospaceColumns) && tc.monospaceColumns.length > 0) {
    lines.push(
      `Render column(s) ${tc.monospaceColumns.join(', ')} (0-indexed) in a monospace style for commands/identifiers; keep the other columns in the normal navy label face.`
    );
  }
  lines.push(
    `Table styling (match the deck world so it does not look like a flat HTML widget): cell and panel surface ${surfaceHex}; uniform deep-navy ${inkHex} outlines and ruled grid lines; rounded corners 8-18px; soft single shadow from the upper-left; the header row fill uses ${headerFill}; place two or three faint props (clipboard, document, small monitor) behind the card so it reads as part of the isometric diorama.`
  );
  lines.push(
    `Table legibility: every cell text must be large, crisp and fully readable; never render tiny, cramped, cut-off, or garbled cells; left-align text within each cell and keep all columns and rows on a strict even grid. Keep all ${cols} column(s) and ${rowCount} body row(s) present; never add, merge, split, drop, or reorder columns or rows; never invent extra cells or placeholder text.`
  );
  if (typeof tc.caption === 'string' && tc.caption.trim()) {
    lines.push(`Caption under the table, verbatim: "${tc.caption.trim()}".`);
  }
  if (typeof tc.note === 'string' && tc.note.trim()) {
    lines.push(`Note near the table, verbatim: "${tc.note.trim()}".`);
  }
  return lines;
}

function buildPrompt(slide, genome, safe) {
  const a = genome.artStyle;
  const c = genome.compositionRules;
  // palette には実色エントリ({name,hex})のほかに chapterDominantColors(object) や
  // glowUsage(string) など非色メタが混在する。name/hex を持つ実色だけを展開し、
  // "undefined undefined" の混入を防ぐ。
  const paletteStr = Object.values(genome.palette)
    .filter((p) => p && typeof p === 'object' && typeof p.name === 'string' && typeof p.hex === 'string')
    .filter((p) => p && typeof p === 'object' && p.name && p.hex)
    .map((p) => `${p.name} ${p.hex}`)
    .join(', ');

  const motifByName = new Map((genome.motifs || []).map((m) => [m.name, m]));
  const motifStr = slide.motifs
    .map((name) => {
      const m = motifByName.get(name);
      return m ? `${name} (${m.appearance})` : name;
    })
    .join('; ');

  const policyText = TEXT_POLICY_PROMPT[slide.textPolicy] || TEXT_POLICY_PROMPT.none;
  const cameraStr = cameraStringFor(slide, genome);

  const hasBaked = Array.isArray(slide.bakedText) && slide.bakedText.length > 0;
  const bakedLine = hasBaked ? `Japanese labels baked into the image: ${slide.bakedText.join(' / ')}.` : '';
  const correctText = (hasBaked ? slide.bakedText : slide.overlayText).join(' / ');
  const layoutTemplate = slide.layoutTemplate || 'content-adapted';
  const densityLevel = slide.densityLevel || 'medium';
  const figures = slide.figures || 'use people only when semantically useful; avoid decorative humans';
  const robotMascot = slide.robotMascot || 'none';
  // D9: plan が tableMode を明示していればそれを尊重し、無ければ tableHints から補助推論する。
  const tableHint = inferTableMode(slide);
  const tableMode = slide.tableMode || (tableHint ? tableHint.recommended : 'none');
  const imageFit = slide.imageFit || (slide.pattern === 'html-composite' ? 'html-composite-contain' : 'contain');
  const printIntent = slide.printIntent || 'all important subjects must remain inside safe margins and fit inside the full 16:9 HTML slide without cropping';

  // promptSuffix は既に "Style:" 始まり。二重に "Style:" を付けない。
  const suffix = String(genome.promptSuffix || '').trim();
  const styleLine = /^style:/i.test(suffix) ? suffix : `Style: ${suffix}`;

  let negative = String(genome.negativePrompt || '').trim();
  if (slide.negativeSpecific) negative += ` Slide-specific: ${slide.negativeSpecific}`;

  const adaptationPrinciple = genome.contentAdaptationRules?.principle
    || 'Adapt the visual content to the slide message; do not copy a fixed reference composition.';
  const tableRule = tableMode !== 'none'
    ? (genome.tableAndMatrixRules?.modes?.[tableMode] || tableMode)
    : null;
  const visualBalance = genome.tableAndMatrixRules?.visualBalance || '';
  const printRule = genome.printReadinessRules?.imageCanvas || '';

  // 用途宣言(MODE setter)。OpenAI 画像生成は用途明示で仕上げモード・密度・精度が固定される。
  // 値が無い行は出さない方針だが、用途宣言と幾何固定は再現性 must のため既定値で必ず展開する。
  const intendedUse = slide.intendedUse || 'presentation infographic / explanatory diagram';
  // アイソメ幾何の計測可能制約(GEOMETRY LOCK)。genome に明示があればそれ、無ければ既定の軸測投影制約。
  const geometryLock = (a.camera && a.camera.geometry)
    || 'isometric, 30-degree axonometric projection, equal scale on all axes, no perspective foreshortening.';

  const lines = [];
  lines.push('STYLE LOCK (keep identical on every page):');
  lines.push(`- Art style: ${a.family}, ${a.rendering}. ${a.line}; ${a.corners}. ${a.shadow}. ${a.background}.`);
  lines.push(`- Camera: ${a.camera.default}; structural slides (order/direction/count matter) use ${a.camera.structural}.`);
  lines.push(`- Palette (${genome.styleName}): ${paletteStr}. 60-30-10 rule, one dominant accent per image.`);
  lines.push(
    `- Composition: ${c.aspect} (${c.targetResolution}). Keep safe margins ${c.safeArea} clear for overlay text. ${c.density}. ${c.titlePlacement}.`
  );
  lines.push(`- In-image text policy: ${policyText}`);
  lines.push(`- Content adaptation: ${adaptationPrinciple}`);
  lines.push(`- Print / HTML fit: ${printRule || printIntent}`);
  // MODE(用途宣言)を STYLE LOCK 直後に必ず展開する(再現性 must)。
  lines.push(`Intended use: ${intendedUse} for slide ${slide.slide} of a deck.`);
  // GEOMETRY LOCK を展開(再現性 must)。
  lines.push(`Geometry lock: ${geometryLock}`);
  if (slide.styleReference && typeof slide.styleReference === 'object') {
    const sr = slide.styleReference;
    const refs = [];
    if (sr.anchorSlug) refs.push('ref-1=' + sr.anchorSlug);
    if (Array.isArray(sr.refSlugs)) sr.refSlugs.forEach(function (rs, i) { refs.push('ref-' + (i + 2) + '=' + rs); });
    if (refs.length > 0) {
      lines.push('Reference images (image-to-image style anchor, actual image files attached at generation time): ' + refs.join(', '));
      const mode = sr.inheritMode || 'style-only';
      if (mode === 'style-and-layout') {
        lines.push('Inherit from references: palette, navy outline style, isometric geometry, motif rendering, and the overall zone layout of ref-1. Change only the subject described below; keep framing; no extra elements; do not copy the reference subject.');
      } else if (mode === 'full') {
        lines.push('Closely match ref-1 overall; vary only the explicitly described differences; do not introduce new logos, text, or props.');
      } else {
        lines.push('Inherit from references: palette, navy outline style, isometric geometry, motif rendering only. Change only the subject described below; keep framing; no extra elements; do not copy the reference subject.');
      }
      if (Array.isArray(sr.preserve) && sr.preserve.length > 0) lines.push('Preserve from reference exactly: ' + sr.preserve.join('; ') + '.');
      if (Array.isArray(sr.change) && sr.change.length > 0) lines.push('Change vs reference: ' + sr.change.join('; ') + '.');
    }
  }
  if (genome.lockTiers && typeof genome.lockTiers === 'object') {
    if (Array.isArray(genome.lockTiers.tier1) && genome.lockTiers.tier1.length > 0) {
      lines.push('- Lock tier 1 (never change): ' + genome.lockTiers.tier1.join('; ') + '.');
    }
    if (Array.isArray(genome.lockTiers.tier2) && genome.lockTiers.tier2.length > 0) {
      lines.push('- Maintain (tier 2): ' + genome.lockTiers.tier2.join('; ') + '.');
    }
  }
  lines.push('');
  lines.push(`Layout template: ${layoutTemplate}. Density level: ${densityLevel}.`);
  lines.push(`Figures: ${figures}. AI robot mascot: ${robotMascot}.`);
  if (tableRule) {
    let tableLine = `Table / matrix handling: ${tableMode}. ${tableRule} ${visualBalance}`;
    // D9: 表方針を必ずプロンプトへ織り込む(正確な表・料金はHTML前面、概念比較は図解変換優先)。
    tableLine += ' Policy: exact tables / prices / volatile numbers belong on a front HTML layer (html-overlay-table or html-primary); conceptual comparisons are translated into diagrams (diagram-translation) rather than ruled grids.';
    if (tableHint && !slide.tableMode) {
      tableLine += ` Auto-recommended from table hints: ${tableHint.recommended} (${tableHint.reasons.join('; ')}).`;
    }
    lines.push(tableLine);
  }
  lines.push(`Image fit contract: ${imageFit}. Design the composition so it works with object-fit: contain in the HTML slide; do not place important subjects at the outer edges.`);
  // D7: 自動計算したセーフエリア px をプロンプトへ機械挿入(手計算依存を解消)。
  lines.push(safeAreaPromptLine(safe));
  lines.push(`Print intent: ${printIntent}.`);
  lines.push('');
  // per-slide の目的・聴衆理解・背景を本文へ常時展開する。
  // validateSlide() が欠損を止めるため、ここで出ない場合はビルド前に FAIL している。
  lines.push(`Purpose (why this slide exists): ${slide.purpose}`);
  lines.push(`Audience takeaway (one sentence the viewer should grasp): ${slide.audienceTakeaway}`);
  lines.push(`Background / context: ${slide.background}`);
  // 構図(LAYOUT)の構造化語彙を固定展開する(再現性 must: 配置・読み順・主役・強調)。
  if (slide.layout && typeof slide.layout === 'object') {
    const l = slide.layout;
    const parts = [];
    if (l.grid) parts.push(`grid=${l.grid}`);
    if (Array.isArray(l.zones) && l.zones.length > 0) {
      const zoneStr = l.zones.map((z) => `${z.area}:${z.content}`).join('; ');
      parts.push(`zones=[${zoneStr}]`);
    }
    if (Array.isArray(l.readingOrder) && l.readingOrder.length > 0) {
      parts.push(`reading order=${l.readingOrder.join(' > ')}`);
    }
    if (l.focalPoint) parts.push(`focal point=${l.focalPoint}`);
    if (l.emphasis) parts.push(`emphasis=${l.emphasis}`);
    if (parts.length > 0) {
      lines.push(`Layout: ${parts.join('; ')}.`);
    }
  }
  // D10: per-slide 支配色(accent)を本文へ射影する。Layout 直後に 60-30-10 の主役色を1行明示する。
  const dominantAccent = resolveDominantAccent(slide, genome);
  if (dominantAccent.line) lines.push(dominantAccent.line);
  // D12: illustrated-full-table のとき、見出し+全行を verbatim に焼き込む決定論テーブルブロックを展開する。
  // 画像内に表ごと焼き込み、HTML のピンポイント重ね(位置ズレの原因)を使わない方針。
  if (tableMode === 'illustrated-full-table' && slide.tableContent) {
    for (const tl of buildBakedTableLines(slide, genome, dominantAccent)) lines.push(tl);
  }
  lines.push('');
  lines.push(slide.subject);
  lines.push(slide.diagramStructure);
  if (genome.lockTiers && Array.isArray(genome.lockTiers.tier3) && genome.lockTiers.tier3.length > 0) {
    lines.push('Variable details (may differ per slide, tier 3): ' + genome.lockTiers.tier3.join('; ') + '.');
  }
  if (bakedLine) { lines.push(bakedLine); lines.push('Spell out brand names and difficult words letter by letter; wrap each literal label in quotes exactly as written; do not translate or add characters.'); }
  lines.push(`Required motifs from style genome: ${motifStr}.`);
  // S3: フロー矢印が複数意味を持つ時、色->意味の凡例を描く(genome.flowLegendRule)。
  const flowMotifs = (slide.motifs || []).some(function (n) { return /flow|arrow|path/i.test(n); });
  if (flowMotifs && genome.flowLegendRule) {
    lines.push('Flow legend: ' + genome.flowLegendRule);
  }
  lines.push(`Camera: ${cameraStr}.`);
  lines.push('');
  lines.push(styleLine);
  // 全ページ共通の制約アンカー(繰り返し句)。genome に定義があれば末尾付近で必ず再掲する(再現性 should)。
  if (Array.isArray(genome.consistencyAnchors) && genome.consistencyAnchors.length > 0) {
    lines.push(`Consistency anchors (repeat every page): ${genome.consistencyAnchors.join('; ')}.`);
  }
  lines.push('');
  lines.push(`Negative: ${negative}`);
  lines.push('');
  lines.push('<!--');
  lines.push('参考情報(生成には使わない):');
  lines.push(`- 画像内に描く日本語テキスト(正テキスト): ${correctText}`);
  lines.push(`- aspect: ${c.aspect} / 推奨解像度: ${c.targetResolution}`);
  lines.push(`- safeArea(自動計算 source=${safe.source}): 上下 ${safe.topBottomPx}px(${safe.topBottomPercent}%) / 左右 ${safe.leftRightPx}px(${safe.leftRightPercent}%) @ 2560x1440`);
  lines.push('- generation: model=' + ((slide.generation && slide.generation.modelSnapshot) || 'gpt-image-2-2026-04-21') + ', quality=' + ((slide.generation && slide.generation.quality) || 'high') + ', size=' + ((slide.generation && slide.generation.size) || '2560x1440') + ' (gpt-image-2 has no seed; reproducibility via prompt invariance + reference images + eval)');
  lines.push(`- ファイル出力名: ${slide.slug}.png`);
  lines.push('-->');
  return `${lines.join('\n')}\n`;
}

function buildMeta(slide, genome, sourceName, safe) {
  const c = genome.compositionRules;
  const imageFit = slide.imageFit || (slide.pattern === 'html-composite' ? 'html-composite-contain' : 'contain');
  // D9: plan 明示が無ければ tableHints から推論した tableMode を採用する(prompt と同一ロジック)。
  const tableHint = inferTableMode(slide);
  const tableMode = slide.tableMode || (tableHint ? tableHint.recommended : 'none');
  const defaults = {
    layoutTemplate: slide.layoutTemplate || 'content-adapted',
    densityLevel: slide.densityLevel || 'medium',
    figures: slide.figures || 'use people only when semantically useful; avoid decorative humans',
    robotMascot: slide.robotMascot || 'none',
    tableMode,
    imageFit,
    printIntent: slide.printIntent || 'all important subjects must remain inside safe margins and fit inside the full 16:9 HTML slide without cropping',
  };
  const meta = {
    slide: slide.slide,
    slug: slide.slug,
    asset: `${slide.slug}.png`,
    source: sourceName,
    // D6: 決定論ビルダー由来であることのマーカー。手書き meta(マーカー無)を検証側が警告できる。
    builtBy: BUILDER_MARKER,
    decision: 'generate-image',
    seed: null,
    aspect: c.aspect,
    resolution: c.targetResolution,
    alt: slide.alt,
    overlayText: slide.overlayText,
    reason: slide.reason,
    accent: slide.accent,
    camera: metaCameraLabel(slide),
    pattern: slide.pattern,
    textPolicy: slide.textPolicy,
    backgroundSource: slide.backgroundSource,
    styleGenome: 'assets/generated/style-genome.json',
    prompt: `assets/generated/${slide.slug}.prompt.txt`,
    motifs: slide.motifs,
    // D7: 自動計算したセーフエリア px を meta にも記録し、印刷検証や HTML 側が参照できるようにする。
    safeAreaPx: {
      top: safe.topBottomPx,
      bottom: safe.topBottomPx,
      left: safe.leftRightPx,
      right: safe.leftRightPx,
      basis: `${SAFE_AREA_BASIS.width}x${SAFE_AREA_BASIS.height}`,
      source: safe.source,
    },
    ...defaults,
  };
  if (Array.isArray(slide.bakedText) && slide.bakedText.length > 0) {
    meta.bakedText = slide.bakedText;
  }
  // D9: 推論ヒントの根拠を meta に残す(plan 明示時は recommended を参考値として併記)。
  if (tableHint) {
    meta.tableModeRecommended = tableHint.recommended;
    meta.tableModeReasons = tableHint.reasons;
  }
  if (slide.tableHints && typeof slide.tableHints === 'object') {
    meta.tableHints = slide.tableHints;
  }
  // 目的・聴衆理解・背景・用途・構図を meta に常時記録する。
  // prompt 本文へ展開した再現性要素を meta にも残し、検証や HTML 側が参照できるようにする。
  meta.purpose = slide.purpose;
  meta.audienceTakeaway = slide.audienceTakeaway;
  meta.background = slide.background;
  meta.intendedUse = slide.intendedUse;
  meta.layout = slide.layout;
  meta.generation = {
    modelSnapshot: (slide.generation && slide.generation.modelSnapshot) || 'gpt-image-2-2026-04-21',
    quality: (slide.generation && slide.generation.quality) || 'high',
    size: (slide.generation && slide.generation.size) || '2560x1440',
  };
  // D10: 支配色 HEX を meta に記録し、validator が「Dominant accent」行の prompt 反映を意味照合できるようにする。
  // accent=multi や未知文字列は単一 HEX が無いため記録しない(その場合 validator は意味照合をスキップする)。
  const dominantAccent = resolveDominantAccent(slide, genome);
  if (dominantAccent.hex) meta.dominantAccentHex = dominantAccent.hex;
  // D11: per-slide 負制約も meta に記録する。evaluate-image-consistency が per-slide rubric の
  // 「Must NOT show」基準として参照し、構造系スライドの構図崩れ(誤ノード数等)を採点できるようにする。
  if (typeof slide.negativeSpecific === 'string' && slide.negativeSpecific.trim()) {
    meta.negativeSpecific = slide.negativeSpecific;
  }
  // D12: 焼き込みテーブル本文を meta に記録し、validator が prompt 本文へのセル verbatim 展開を意味照合できるようにする。
  if (slide.tableContent && typeof slide.tableContent === 'object' && !Array.isArray(slide.tableContent)) {
    meta.tableContent = slide.tableContent;
  }
  if (slide.styleReference && typeof slide.styleReference === 'object') {
    meta.styleReference = slide.styleReference;
  }
  return meta;
}

function diffSummary(label, nextContent, path) {
  if (!existsSync(path)) return `NEW      ${label}`;
  const prev = readFileSync(path, 'utf8');
  if (prev === nextContent) return `UNCHANGED ${label}`;
  const prevLines = prev.split('\n').length;
  const nextLines = nextContent.split('\n').length;
  return `CHANGED  ${label} (lines ${prevLines} -> ${nextLines})`;
}

function matchesOnly(slide, onlySet) {
  if (!onlySet) return true;
  if (onlySet.has(slide.slug)) return true;
  if (onlySet.has(String(slide.slide))) return true;
  const padded = `slide-${String(slide.slide).padStart(2, '0')}`;
  if (onlySet.has(padded)) return true;
  // slug が onlySet のいずれかを含む / 含まれる場合も許容
  for (const token of onlySet) {
    if (slide.slug && (slide.slug === token || slide.slug.startsWith(token))) return true;
  }
  return false;
}

function main() {
  const { flags, positional } = parseArgs(process.argv.slice(2));
  const slideDir = positional[0];
  if (!slideDir) usage();

  const generatedDir = join(slideDir, 'assets', 'generated');
  const planPath = flags.plan ? resolveFromCwd(flags.plan) : join(generatedDir, 'image-deck-plan.json');
  if (!existsSync(planPath)) {
    console.error(`FAIL: plan not found: ${planPath}`);
    process.exit(1);
  }
  const genomePath = resolveGenomePath(flags.genome, generatedDir);
  const onlySet = flags.only
    ? new Set(
        String(flags.only)
          .split(',')
          .map((s) => s.trim())
          .filter(Boolean)
      )
    : null;
  const checkMode = Boolean(flags.check);
  const sourceName = flags.source ? String(flags.source) : 'codex-image2';

  const plan = readJson(planPath, 'plan');
  const genome = readJson(genomePath, 'genome');

  if (!Array.isArray(plan.slides) || plan.slides.length === 0) {
    console.error('FAIL: plan.slides must be a non-empty array');
    process.exit(1);
  }
  if (!genome.artStyle || !genome.palette || !genome.compositionRules) {
    console.error('FAIL: style genome missing artStyle / palette / compositionRules');
    process.exit(1);
  }

  const motifNames = new Set((genome.motifs || []).map((m) => m.name));
  const layoutNames = new Set(Object.keys(genome.compositionRules.layoutTemplates || {}));
  // D13: accent タイポ検出用の palette キー集合(validateSlide が "multi"/palette キー/HEX 以外を警告)。
  const paletteKeys = new Set(Object.keys(genome.palette || {}));

  // D7: セーフエリア px を genome から一度だけ自動計算し、全スライドへ機械挿入する。
  const safe = computeSafeAreaPx(genome);
  console.log(
    `SAFE-AREA: top/bottom ${safe.topBottomPercent}% -> ${safe.topBottomPx}px, left/right ${safe.leftRightPercent}% -> ${safe.leftRightPx}px (source=${safe.source}, basis ${SAFE_AREA_BASIS.width}x${SAFE_AREA_BASIS.height})`
  );

  // 全スライドを先に検証(1件でも不正なら全体を止める)
  const allErrors = [];
  for (const slide of plan.slides) {
    allErrors.push(...validateSlide(slide, motifNames, layoutNames, paletteKeys));
  }
  if (allErrors.length > 0) {
    for (const e of allErrors) console.error(`FAIL: ${e}`);
    process.exit(1);
  }

  const targets = plan.slides.filter((slide) => matchesOnly(slide, onlySet));
  if (targets.length === 0) {
    console.error('FAIL: no slides matched (check --only)');
    process.exit(1);
  }

  if (!checkMode) {
    mkdirSync(generatedDir, { recursive: true });
  }

  let written = 0;
  for (const slide of targets) {
    const promptMd = buildPrompt(slide, genome, safe);
    const meta = buildMeta(slide, genome, sourceName, safe);
    const metaJson = `${JSON.stringify(meta, null, 2)}\n`;
    const promptPath = join(generatedDir, `${slide.slug}.prompt.txt`);
    const metaPath = join(generatedDir, `${slide.slug}.meta.json`);

    if (checkMode) {
      console.log(diffSummary(`${slide.slug}.prompt.txt`, promptMd, promptPath));
      console.log(diffSummary(`${slide.slug}.meta.json`, metaJson, metaPath));
    } else {
      writeFileSync(promptPath, promptMd, 'utf8');
      writeFileSync(metaPath, metaJson, 'utf8');
      console.log(`OK  wrote ${slide.slug}.prompt.txt + ${slide.slug}.meta.json`);
      written += 2;
    }
  }

  if (checkMode) {
    console.log(`CHECK: ${targets.length} slide(s) compared (no files written).`);
  } else {
    console.log(`DONE: ${targets.length} slide(s), ${written} file(s) written to ${generatedDir}`);
  }
}

main();
