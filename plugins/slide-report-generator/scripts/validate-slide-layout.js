#!/usr/bin/env node
/**
 * validate-slide-layout.js — 実描画レイアウト契約の検証ゲート。
 *
 * SVG 単体の幾何は scripts/validate-svg-diagram.py が静的に見る。こちらは
 * ブラウザで実際に描いてからでないと分からないもの、すなわち「要素どうしの
 * 位置関係」を見る。認知負荷は個々の部品でなく部品の重なり方で決まるため、
 * ここが読みやすさの実質的なゲートになる。
 *
 * 検査する 6 項目:
 *   L1 重なり     見出し・本文・図解・ページネーション帯が互いに重ならない
 *   L2 はみ出し   どの要素もスライド (印刷面) の外へ出ない
 *   L3 溢れ       スクロールしないと読めない要素がない (scrollHeight > clientHeight)
 *   L4 図解の面積 図解がスライド面積の 12% 以上ある (小さすぎる図は読ませる意味がない)
 *   L5 余白       主要要素どうしに最低 8px の間隔がある (接触は重なりと同じく読みにくい)
 *   L6 文字量     1 スライドの本文が 340 字以内 (1メッセージ1スライドの実効的な上限)
 *
 * 使い方:
 *   node scripts/validate-slide-layout.js <deck/index.html> [--viewport 1920x1080] [--strict]
 * 複数の viewport を試すには --viewport を繰り返す。既定は 1920x1080 と 1440x900 の 2 種。
 *
 * exit 0 = error 0 件、exit 1 = error あり。
 */
'use strict';

const path = require('path');
const fs = require('fs');

const PLUGIN_ROOT = path.dirname(__dirname);
const VENDOR = path.join(PLUGIN_ROOT, 'vendor');

// 接触も重なりと同じく読みにくいので、最低これだけは離す。
const MIN_GAP = 8;
// 重なり判定の許容。border-radius や字形のはみ出しを誤検知しないための余裕。
const OVERLAP_TOLERANCE = 2;
// 図解がこれより小さいと、載せる意味より場所を取る害の方が大きい。
const MIN_DIAGRAM_AREA_RATIO = 0.12;
// 1 スライド 1 メッセージを実際に守れる文字量の上限。
const MAX_BODY_CHARS = 340;

const SEVERITY = {
  L0: 'error',   // 対象 0 件・成果物でない入力は検査済みにしない
  L7: 'error',   // engine と skeleton は @page 契約が異なるため同一 deck に混在不可
  L1: 'error',   // 重なりは誤検知しにくく、読めなくなる直接の原因
  L2: 'error',   // 印刷・撮影で確実に切れる
  L3: 'error',   // スライドはスクロールできない前提の媒体
  L4: 'warning', // 意図的に小さい図 (補助的な記号) がありうる
  L5: 'warning', // 8px は目安で、詰めたい意匠もありうる
  L6: 'warning', // 密度は用途による (配布資料は濃くてよい)
};

function parseViewports(argv) {
  const out = [];
  argv.forEach((a, i) => {
    if (a === '--viewport' && argv[i + 1]) {
      const m = /^(\d+)x(\d+)$/.exec(argv[i + 1]);
      if (m) out.push({ width: Number(m[1]), height: Number(m[2]) });
    }
  });
  return out.length ? out : [{ width: 1920, height: 1080 }, { width: 1440, height: 900 }];
}

/** 2 矩形の重なり面積。接触未満は 0。 */
function overlapArea(a, b, tolerance) {
  const w = Math.min(a.right, b.right) - Math.max(a.left, b.left) - tolerance;
  const h = Math.min(a.bottom, b.bottom) - Math.max(a.top, b.top) - tolerance;
  return (w > 0 && h > 0) ? Math.round(w * h) : 0;
}

/** 2 矩形の最短間隔。重なっていれば 0。 */
function gapBetween(a, b) {
  const dx = Math.max(0, Math.max(a.left, b.left) - Math.min(a.right, b.right));
  const dy = Math.max(0, Math.max(a.top, b.top) - Math.min(a.bottom, b.bottom));
  return Math.round(Math.hypot(dx, dy));
}

/** ブラウザ側で 1 スライドぶんの実測値を集める。 */
function collectSlide(index) {
  const box = (el) => {
    const b = el.getBoundingClientRect();
    return {
      left: b.left, top: b.top, right: b.right, bottom: b.bottom,
      width: b.width, height: b.height,
    };
  };
  const visible = (el) => {
    const cs = getComputedStyle(el);
    if (cs.display === 'none' || cs.visibility === 'hidden') return false;
    if (Number(cs.opacity) === 0) return false;
    const b = el.getBoundingClientRect();
    return b.width > 1 && b.height > 1;
  };
  const el = document.querySelectorAll('[data-slide],.srg-slide,[data-slide-skeleton]')[index];
  if (!el) return null;

  const pick = (sel, role) => [...el.querySelectorAll(sel)]
    .filter(visible)
    .map((e) => ({ role, text: (e.textContent || '').trim().slice(0, 24), ...box(e) }));

  // 帯 (ページネーション・ヘッダ/フッタ) はスライドの外に置かれるので document から拾う
  const bands = [...document.querySelectorAll(
    '.slider-footer,.slider-header,.pg-controls,.pg-dots,.pg-counter,.pg-progress,.pg-section-nav',
  )].filter(visible).map((e) => ({ role: `帯(${e.className.split(/\s+/)[0]})`, text: '', ...box(e) }));

  const heads = pick('h1,h2,h3', '見出し');
  const bodies = pick('.slider__content > p, .slider__content > ul, .slide-lead, .srg-slide__main p, .srg-slide__main ul, .srg-slide__main ol', '本文');
  const figs = [...el.querySelectorAll('svg, img, .d3-mount, .mermaid')]
    .filter(visible)
    // 図解の中の svg (入れ子) は個別に数えず、最も外側だけを見る
    .filter((e) => !e.parentElement.closest('svg'))
    .map((e) => ({ role: '図解', text: '', ...box(e) }));

  // 溢れは HTML のブロック要素だけを見る。
  //   - SVG 内部の要素に scrollHeight を当てても意味がない (クリップは viewBox の責務で、
  //     そちらは validate-svg-diagram.py の C1 が静的に見ている)
  //   - 行送りのある要素は descender のぶん scrollHeight が数 px 常に大きい。
  //     閾値を小さく取ると全見出しが鳴り続け、本物の溢れが埋もれる。
  const OVERFLOW_SLACK = 12;
  const overflowing = [...el.querySelectorAll('*')].filter(visible).filter((e) => {
    if (e.namespaceURI !== 'http://www.w3.org/1999/xhtml') return false;
    if (e.closest('svg')) return false;
    const cs = getComputedStyle(e);
    if (cs.overflowY === 'auto' || cs.overflowY === 'scroll') return false; // 意図的
    if (cs.overflowX === 'auto' || cs.overflowX === 'scroll') return false;
    return e.scrollHeight - e.clientHeight > OVERFLOW_SLACK
      || e.scrollWidth - e.clientWidth > OVERFLOW_SLACK;
  }).slice(0, 3).map((e) => ({
    tag: e.tagName.toLowerCase(),
    cls: (typeof e.className === 'string' ? e.className : '').split(/\s+/)[0],
    over: Math.max(e.scrollHeight - e.clientHeight, e.scrollWidth - e.clientWidth),
  }));

  const bodyChars = bodies.reduce((n, b) => n + b.text.length, 0)
    + [...el.querySelectorAll('.slider__content > p, .slider__content > ul, .srg-slide__main p, .srg-slide__main ul, .srg-slide__main ol')]
      .reduce((n, e) => n + (e.textContent || '').trim().length, 0);

  return {
    type: el.getAttribute('data-type') || el.getAttribute('data-slide-type') || '?',
    slide: box(el), heads, bodies, figs, bands, overflowing, bodyChars,
  };
}

async function run() {
  const argv = process.argv.slice(2);
  const target = argv.find((a) => !a.startsWith('--')
    && !/^\d+x\d+$/.test(a));
  const strict = argv.includes('--strict');
  const viewports = parseViewports(argv);
  if (!target) {
    console.error('usage: validate-slide-layout.js <deck/index.html> [--viewport WxH] [--strict]');
    process.exit(2);
  }
  const file = path.resolve(target);
  if (!fs.existsSync(file)) {
    console.error(`ERROR [L0] ${target}: ファイルが無い`);
    process.exit(1);
  }
  if (!fs.statSync(file).isFile() || path.extname(file).toLowerCase() !== '.html') {
    console.error(`ERROR [L0] ${target}: deck の実 HTML ファイルを指定すること`);
    process.exit(1);
  }

  const { configurePluginLocalPlaywright } = require(path.join(VENDOR, 'scripts', 'playwright-runtime.js'));
  configurePluginLocalPlaywright();
  const { chromium } = require(path.join(VENDOR, 'node_modules', 'playwright'));

  let errors = 0;
  let warnings = 0;
  let slidesChecked = 0;
  let detectedSystem = 'none';
  const report = (code, where, message) => {
    const sev = SEVERITY[code] || 'error';
    if (sev === 'error') errors++; else warnings++;
    console.error(`${sev.toUpperCase()} [${code}] ${where}: ${message}`);
  };

  const browser = await chromium.launch();
  try {
    for (const vp of viewports) {
      const page = await browser.newPage({ viewport: vp });
      await page.goto(`file://${file}`);
      await page.waitForTimeout(300);
      const systems = await page.evaluate(() => ({
        engine: document.querySelectorAll('[data-slide],.slider__item').length,
        skeleton: document.querySelectorAll('.srg-slide,[data-slide-skeleton]').length,
        slides: document.querySelectorAll('[data-slide],.srg-slide,[data-slide-skeleton]').length,
      }));
      if (systems.engine > 0 && systems.skeleton > 0) {
        detectedSystem = 'mixed';
        report('L7', `${path.basename(path.dirname(file))} ${vp.width}x${vp.height}`,
          'engine (slider-*) と skeleton (.srg-*) が同一 deck に混在している');
        await page.close();
        break;
      }
      detectedSystem = systems.engine > 0 ? 'engine' : (systems.skeleton > 0 ? 'skeleton' : 'none');
      const count = systems.slides;
      if (count === 0) {
        report('L0', `${path.basename(path.dirname(file))} ${vp.width}x${vp.height}`,
          'slide 要素が 0 件のためレイアウトを検査できない');
        await page.close();
        break;
      }
      slidesChecked += count;
      for (let i = 0; i < count; i++) {
        // 1 枚だけを表示状態にしてから測る (非表示スライドは矩形が 0 になる)
        await page.evaluate((n) => {
          document.querySelectorAll('[data-slide],.srg-slide,[data-slide-skeleton]').forEach((el, j) => {
            if (el.matches('[data-slide],.slider__item')) el.classList.toggle('is-active', j === n);
          });
        }, i);
        await page.waitForTimeout(60);
        const r = await page.evaluate(collectSlide, i);
        if (!r) continue;
        const where = `${path.basename(path.dirname(file))} ${vp.width}x${vp.height} slide${i + 1}(${r.type})`;
        const content = [...r.heads, ...r.bodies, ...r.figs];

        // L1 重なり (コンテンツどうし / コンテンツと帯)
        for (let a = 0; a < content.length; a++) {
          for (let b = a + 1; b < content.length; b++) {
            const area = overlapArea(content[a], content[b], OVERLAP_TOLERANCE);
            if (area) {
              report('L1', where, `${content[a].role}${content[a].text ? `「${content[a].text}」` : ''} と `
                + `${content[b].role}${content[b].text ? `「${content[b].text}」` : ''} が ${area}px² 重なっている`);
            }
          }
        }
        for (const band of r.bands) {
          for (const c of content) {
            const area = overlapArea(band, c, OVERLAP_TOLERANCE);
            if (area) report('L1', where, `${band.role} と ${c.role} が ${area}px² 重なっている`);
          }
        }

        // L2 はみ出し
        for (const c of content) {
          const dx = Math.round(Math.max(0, c.right - r.slide.right, r.slide.left - c.left));
          const dy = Math.round(Math.max(0, c.bottom - r.slide.bottom, r.slide.top - c.top));
          if (dx > 1 || dy > 1) {
            report('L2', where, `${c.role} がスライド外へ ${dx ? `横 ${dx}px ` : ''}${dy ? `縦 ${dy}px` : ''} はみ出している`);
          }
        }

        // L3 溢れ
        for (const o of r.overflowing) {
          report('L3', where, `<${o.tag}${o.cls ? ` class="${o.cls}"` : ''}> の内容が ${o.over}px 溢れている`
            + ' (スライドはスクロールできない)');
        }

        // L4 図解の面積
        const slideArea = r.slide.width * r.slide.height;
        for (const f of r.figs) {
          const ratio = (f.width * f.height) / slideArea;
          if (slideArea > 0 && ratio < MIN_DIAGRAM_AREA_RATIO) {
            report('L4', where, `図解がスライド面積の ${(ratio * 100).toFixed(1)}% しかない `
              + `(${(MIN_DIAGRAM_AREA_RATIO * 100).toFixed(0)}% 未満は読ませる意味より場所を取る害が勝つ)`);
          }
        }

        // L5 余白 (重なっていない組だけを見る)
        for (let a = 0; a < content.length; a++) {
          for (let b = a + 1; b < content.length; b++) {
            if (overlapArea(content[a], content[b], OVERLAP_TOLERANCE)) continue;
            const gap = gapBetween(content[a], content[b]);
            if (gap < MIN_GAP) {
              report('L5', where, `${content[a].role} と ${content[b].role} の間隔が ${gap}px しかない`
                + ` (最低 ${MIN_GAP}px)`);
            }
          }
        }

        // L6 文字量
        if (r.bodyChars > MAX_BODY_CHARS) {
          report('L6', where, `本文が ${r.bodyChars} 字ある (1 スライド 1 メッセージの上限 ${MAX_BODY_CHARS} 字)`
            + '。分割するか図解へ逃がす');
        }
      }
      await page.close();
    }
  } finally {
    await browser.close();
  }

  const failed = errors > 0 || (strict && warnings > 0);
  console.log(`slide layout contract: system=${detectedSystem} slides_checked=${slidesChecked} viewports=${viewports.length} errors=${errors} `
    + `warnings=${warnings} -> ${failed ? 'FAIL' : 'PASS'}`);
  process.exit(failed ? 1 : 0);
}

run().catch((err) => {
  console.error(`ERROR [L0] ${err && err.message ? err.message : err}`);
  process.exit(1);
});
