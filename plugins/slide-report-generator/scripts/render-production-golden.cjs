#!/usr/bin/env node
/**
 * render-production-golden.cjs — 本番語彙 (svgSpec) → 自己完結 HTML 断片
 *
 * 用途:
 *   node scripts/render-production-golden.cjs <svgspec.json> > out.html
 *
 * なぜ要るか:
 *   図解の入力には 3 系統の語彙がある。
 *     A 手書き    : nodes[] / relations[] をトップレベルに持つ   (*-input.json)
 *     B builder   : {builder, spec:{...}} をビルダーへ直接渡す   (*-spec.json)
 *     C 本番      : svgSpec {variant, nodes[](^n-), edges[], groups[]}
 *   ゴールデンは長らく B しか無く、**実運用が通る C の経路には基準線が
 *   1 本も無かった**。C は B の上に「射影 (projectXxx)」が 1 層乗る。
 *   射影が入力の情報を落としても、B のゴールデンは全部緑のままである。
 *   実際 projectLevels は edges[] を読み落としており、段間の依存が本番だけ
 *   丸ごと消えていた。この CLI は C の入力から本番と同じ経路で図を起こす。
 *
 * 契約:
 *   - vendor/scripts/render-report.js の renderReport をそのまま通す。
 *     射影も dispatch も本番と同一のコードを踏む (再実装しない)。
 *   - 出力は figure 1 個。前後の節・目次・スタイルは落とす。
 *   - 非決定要素 (時刻・乱数・環境変数・絶対パス) を出力へ入れない。
 */
'use strict';

const fs = require('fs');
const path = require('path');

const PLUGIN_ROOT = path.resolve(__dirname, '..');
const RENDER_REL = 'vendor/scripts/render-report.js';

function fail(msg) {
  process.stderr.write(`render-production-golden: ${msg}\n`);
  process.exit(2);
}

function commentSafe(s) {
  return String(s == null ? '' : s).replace(/--+/g, '-');
}

/** 1 節だけのレポートから figure を 1 個取り出す。節が無い/図が出ない場合は落とす。 */
function extractFigure(html) {
  const open = html.indexOf('<figure');
  if (open < 0) return null;
  const close = html.indexOf('</figure>', open);
  if (close < 0) return null;
  return html.slice(open, close + '</figure>'.length);
}

async function main() {
  const specPath = process.argv[2];
  const usage = 'usage: render-production-golden.cjs <svgspec.json>';
  if (!specPath || specPath === '--help' || specPath === '-h') {
    process.stdout.write(`${usage}\n`);
    return specPath ? 0 : 2;
  }
  if (!fs.existsSync(specPath)) fail(`spec が無い: ${specPath}`);

  let doc;
  try {
    doc = JSON.parse(fs.readFileSync(specPath, 'utf8'));
  } catch (e) {
    return fail(`spec が JSON として読めない (${e.message})`);
  }
  const svgSpec = doc.svgSpec;
  if (!svgSpec || typeof svgSpec !== 'object') {
    return fail('svgSpec が無い。この CLI は本番語彙 (C) 専用で、'
      + 'builder 語彙 (B) は render-diagram-golden.cjs が扱う');
  }

  const { renderReport } = await import(
    require('url').pathToFileURL(path.join(PLUGIN_ROOT, RENDER_REL)).href
  );
  const html = renderReport({
    meta: { title: doc.title || '図解ゴールデン', reportType: doc.reportType || 'internal-analysis' },
    sections: [{
      heading: doc.title || '図解',
      visual: { kind: 'svg', spec: svgSpec, caption: doc.caption || '', alt: doc.alt || doc.title || '' },
    }],
  });

  const figure = extractFigure(html);
  if (!figure) return fail('figure が出なかった (射影が素材不足に倒れた可能性がある)');

  const header = [
    '<!--',
    `  ${path.basename(specPath).replace(/-svgspec\.json$/, '-production-golden.html')}`
      + ` — variant=${commentSafe(svgSpec.variant)} の本番経路ゴールデン (自動生成)`,
    '',
    `  入力: ${path.basename(specPath)} (本番語彙 C: svgSpec)`,
    `  経路: ${RENDER_REL} の renderReport → 射影 → svg-structures.cjs`,
    '  生成: node scripts/render-production-golden.cjs <spec> > <golden>',
    '  検証: python3 scripts/validate-svg-diagram.py --check-grid --strict <golden>',
    '',
    '  builder 語彙 (B) のゴールデンと違い、ここには射影の 1 層が挟まる。',
    '  射影が入力を落とす欠陥は B のゴールデンでは原理的に捕まらない。',
    '-->',
  ].join('\n');

  process.stdout.write(`${header}\n${figure}\n`);
  return 0;
}

main().then((c) => process.exit(c || 0)).catch((e) => fail(e.stack || String(e)));
