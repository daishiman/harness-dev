#!/usr/bin/env node
/**
 * render-diagram-golden.cjs — 構造図ビルダーの spec → 自己完結 HTML 断片
 *
 * 用途:
 *   node scripts/render-diagram-golden.cjs <spec.json> [--skeleton slide|report] > out.html
 *
 * なぜ要るか:
 *   vendor/scripts/svg-structures.cjs の 10 ビルダーは render-slide.cjs / render-report.js
 *   の中からしか呼べず、「この入力からこの SVG が出る」を単体で再現する経路が無かった。
 *   ゴールデン (examples/diagram-goldens/builders/) はこの CLI の出力そのものであり、
 *   ここが唯一の生成手段であることが、ゴールデンが手作業で化粧されていないことの保証になる。
 *
 * 契約:
 *   - vendor/ は require するだけで一切書き換えない。ビルダーが返した <svg> は
 *     1 バイトも加工せずそのまま埋める (ゴールデンは現状出力の忠実な記録である)。
 *   - 外枠 (figure の class / data 属性 / figcaption の class) は
 *     assets/diagram-templates/ の骨格ファイルから実行時に読み取る。骨格が動けば
 *     再生成した瞬間に追随する (ここへ転記すると二重管理になる)。
 *   - 非決定要素 (時刻・乱数・環境変数・絶対パス) を出力へ入れない。
 *     同じ spec からは常にバイト同一の HTML が出る。
 */
'use strict';

const fs = require('fs');
const path = require('path');

const PLUGIN_ROOT = path.resolve(__dirname, '..');
const SKELETON_DIR = path.join(PLUGIN_ROOT, 'assets', 'diagram-templates');
const STRUCT_REL = 'vendor/scripts/svg-structures.cjs';
const struct = require(path.join(PLUGIN_ROOT, STRUCT_REL));

/**
 * ビルダーごとの引数の取り出し方。
 * キー名は render-slide.cjs の dispatch (c.zones / c.stages / c.entities …) と揃える。
 * 揃えないと、この CLI で通った spec が実運用の経路では別物になる。
 */
const BUILDERS = {
  buildArchitecture: { args: ['zones'], optKeys: ['links'] },
  buildDataFlow: { args: ['stages'], optKeys: ['legend'] },
  buildEr: { args: ['entities'], optKeys: ['relations'] },
  buildSequence: { args: ['actors', 'messages'], optKeys: [] },
  buildState: { args: ['states', 'transitions'], optKeys: [] },
  buildSwimlane: { args: ['lanes'], optKeys: ['stepLabels'] },
  buildHighLevel: { args: ['levels'], optKeys: [] },
  buildItState: { args: ['rows'], optKeys: ['columns'] },
  buildMedallion: { args: ['tiers'], optKeys: [] },
  buildDpIntegration: { args: ['hub', 'spokes'], optKeys: [] },
};

function fail(msg) {
  process.stderr.write(`render-diagram-golden: ${msg}\n`);
  process.exit(2);
}

function parseArgv(argv) {
  const out = { specPath: null, skeleton: null };
  for (let i = 0; i < argv.length; i++) {
    const a = argv[i];
    if (a === '--skeleton') {
      out.skeleton = argv[++i];
    } else if (a.startsWith('--skeleton=')) {
      out.skeleton = a.slice('--skeleton='.length);
    } else if (a === '--help' || a === '-h') {
      out.help = true;
    } else if (a.startsWith('-')) {
      fail(`未知のオプション ${a}`);
    } else if (!out.specPath) {
      out.specPath = a;
    } else {
      fail(`spec は 1 つだけ指定する (余分: ${a})`);
    }
  }
  return out;
}

/** HTML の属性値を素朴に読む (骨格は自分たちが書いた固定書式なのでこれで足りる) */
function attrOf(tagText, name) {
  const m = new RegExp(`${name}="([^"]*)"`).exec(tagText);
  return m ? m[1] : null;
}

/**
 * 骨格から外枠だけを取り出す。
 * 骨格本文の長い解説コメントは持ち込まない (ゴールデンは読み物ではなく基準線で、
 * 解説の写しが増えると骨格を直したときに古い写しが残る)。
 */
function readSkeleton(kind) {
  const file = path.join(SKELETON_DIR, `diagram-skeleton-${kind}.html`);
  if (!fs.existsSync(file)) fail(`骨格が無い: ${file}`);
  const text = fs.readFileSync(file, 'utf8');
  const figOpen = /<figure\b[^>]*>/.exec(text);
  if (!figOpen) fail(`骨格に figure 開始タグが無い: ${file}`);
  const capOpen = /<figcaption\b[^>]*>/.exec(text);
  if (!capOpen) fail(`骨格に figcaption 開始タグが無い: ${file}`);
  return {
    rel: path.posix.join('assets', 'diagram-templates', `diagram-skeleton-${kind}.html`),
    figureClass: attrOf(figOpen[0], 'class') || 'srg-diagram',
    figureWidth: attrOf(figOpen[0], 'data-figure-width'),
    captionClass: attrOf(capOpen[0], 'class') || 'srg-diagram__caption',
    hasLabelSpan: /class="srg-diagram__label"/.test(text),
  };
}

function escapeHtml(s) {
  return String(s == null ? '' : s)
    .replace(/&/g, '&amp;')
    .replace(/</g, '&lt;')
    .replace(/>/g, '&gt;');
}

/** HTML コメント内へ安全に置ける文字列 (二重ハイフンは SVG/XML コメントを壊す) */
function commentSafe(s) {
  return String(s == null ? '' : s).replace(/--+/g, '-');
}

function indent(text, pad) {
  return text.split('\n').map((ln) => (ln.length ? pad + ln : ln)).join('\n');
}

function main() {
  const opt = parseArgv(process.argv.slice(2));
  const usage = 'usage: render-diagram-golden.cjs <spec.json> [--skeleton slide|report]';
  if (opt.help) {
    process.stdout.write(`${usage}\n`);
    return 0;
  }
  if (!opt.specPath) fail(usage);
  if (!fs.existsSync(opt.specPath)) fail(`spec が無い: ${opt.specPath}`);

  let doc;
  try {
    doc = JSON.parse(fs.readFileSync(opt.specPath, 'utf8'));
  } catch (e) {
    return fail(`spec が JSON として読めない (${e.message})`);
  }

  const builderName = doc.builder;
  const def = BUILDERS[builderName];
  if (!def) {
    return fail(`builder が未知: ${JSON.stringify(builderName)}。`
      + `使えるのは ${Object.keys(BUILDERS).join(' / ')}`);
  }
  const spec = doc.spec || {};

  // --skeleton > spec.surface > 'slide' の順で決める。
  const kind = opt.skeleton || doc.surface || 'slide';
  if (kind !== 'slide' && kind !== 'report') fail(`--skeleton は slide か report (受領: ${kind})`);
  const sk = readSkeleton(kind);

  const diagramId = doc.diagramId || (kind === 'report' ? 'f1' : 'd1');
  // ariaLabel はビルダーが <title> と aria-label の両方へ入れる。title を書かない
  // spec でも図が無名にならないよう、ビルダー既定の「図解」へ落ちるに任せる。
  const opts = { ariaLabel: doc.title || spec.title || undefined };
  if (doc.desc) opts.desc = doc.desc;
  for (const k of def.optKeys) {
    if (spec[k] !== undefined) opts[k] = spec[k];
  }
  const args = def.args.map((k) => spec[k]);
  const svg = struct[builderName](...args, opts);

  // ---- 外枠を組む ----
  const figAttrs = [
    `class="${sk.figureClass}"`,
    `data-diagram-id="${escapeHtml(diagramId)}"`,
  ];
  if (sk.figureWidth) figAttrs.push(`data-figure-width="${escapeHtml(doc.figureWidth || sk.figureWidth)}"`);

  const captionBody = [];
  if (sk.hasLabelSpan && doc.figureLabel) {
    captionBody.push(`<span class="srg-diagram__label">${escapeHtml(doc.figureLabel)}</span>`);
  }
  if (doc.caption) captionBody.push(escapeHtml(doc.caption));

  const header = [
    '<!--',
    `  ${path.basename(opt.specPath).replace(/-spec\.json$/, '-golden.html')} — ${commentSafe(builderName)} のゴールデン (自動生成)`,
    '',
    `  入力: ${path.basename(opt.specPath)}`,
    `  骨格: ${sk.rel}`,
    `  ビルダー: ${STRUCT_REL} の ${builderName}`,
    '  生成: node scripts/render-diagram-golden.cjs '
      + `<spec> --skeleton ${kind} > <golden>`,
    `  検証: python3 scripts/validate-svg-diagram.py --check-grid --strict <golden>`,
    '',
    '  svg 要素はビルダーの戻り値をそのまま埋めている (加工しない)。',
    '  骨格が持つ aria-labelledby の代わりに、ビルダーが出す <title> と aria-label が',
    '  アクセシブル名になる。これは骨格からの意図的な差で、ゴールデンは',
    '  「今のビルダーが実際に出すもの」を記録する側に倒している。',
    '-->',
  ].join('\n');

  const parts = [
    header,
    `<figure ${figAttrs.join('\n        ')}>`,
    '',
    indent(svg, '  '),
    '',
    `  <figcaption id="${escapeHtml(diagramId)}-caption" class="${sk.captionClass}">`,
    captionBody.length ? `    ${captionBody.join('\n    ')}` : '',
    '  </figcaption>',
    '',
    '</figure>',
  ].filter((p) => p !== '');

  process.stdout.write(`${parts.join('\n')}\n`);
  return 0;
}

main();
