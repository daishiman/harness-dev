#!/usr/bin/env node
/**
 * build-deck-html.js
 *
 * 役割: 全面画像デッキ(full-image-deck)の **自己完結 index.html** を
 *       image-deck-plan.json + 各 slide-NN-slug.meta.json から決定論生成する。
 *
 * 対応パターン(plan.slides[].pattern):
 *   - image-only      : 生成画像を主キャンバス(.ai-slide-canvas)に contain で全面表示。
 *   - html-composite  : 背景に生成画像(.ai-slide-canvas)、前面に .visual-overlay として
 *                       実HTMLコードブロック(overlayCode)または実HTML表(tableHtml)を重ねる。
 *                       コード/表は判読性・コピー可・印刷品質のため画像に焼かずHTMLで描く
 *                       (references/full-image-deck-method.md §7.6.1 コード非画像化原則)。
 *   - html-primary    : 画像なし。overlayCode/tableHtml のみを前面表示(背景は無地)。
 *
 * 背景(実運用の事故・2026-06-26):
 *   styles.css / scripts.js を別ファイルにすると環境によって消失し
 *   「スライドが切り替わらない・ページ送りが効かない」事故が起きた。
 *   そこで CSS と JS を <style>/<script> として index.html へインライン化した
 *   自己完結HTMLを既定にする(§6.9.1)。
 *
 * 再現性: 同じ plan.json + meta(alt) から毎回同一の index.html を生成する
 *   (LLM 非依存の決定論ビルダー)。CSS/JS は本スクリプト内の固定テンプレート。
 *
 * 使い方:
 *   node scripts/build-deck-html.js <slide-dir> [--manifest=<path>] [--asset-base-url=<URL>] [--output=<filename>]
 *   入力: <slide-dir>/assets/generated/image-deck-plan.json
 *         <slide-dir>/assets/generated/slide-NN-{slug}.meta.json (alt 取得)
 *   出力: <slide-dir>/<output> (既定 index.html・自己完結・CSS/JS インライン)
 *
 * 画像の外部URL化(GASデプロイ用):
 *   GAS の HtmlService は相対パス参照(assets/generated/<name>.<ext>)の画像を
 *   読めない。--manifest または --asset-base-url を指定すると、picture の
 *   src/srcset を image-asset-manifest.json をSSoTとして外部URLへ差し替える。
 *   URL解決順: (1) files[relPath].publicUrl 非空ならそれ、
 *   (2) else assetBaseUrl(または --asset-base-url)非空なら
 *       assetBaseUrl 末尾スラッシュ除去 + '/' + basename(relPath)、
 *   (3) else 相対パスのまま(外部モードでは未解決として stderr 警告 + 終了コード1)。
 *   --manifest/--asset-base-url を使うときは --output=index.deploy.html 等で
 *   ローカル用 index.html と分けるのが望ましい。
 *   ローカル/印刷はデフォルト(オプション未指定)の相対パスを使う。
 *   --manifest と --asset-base-url を未指定なら現状どおり相対パス(後方互換)。
 *   --manifest のパスは絶対 or slide-dir 基準の相対。
 *
 * 自己テスト:
 *   1. node --check scripts/build-deck-html.js (構文)
 *   2. node scripts/build-deck-html.js <deck> 生成 -> evaluate-deck.js で動作可能=○ 確認。
 *   3. playwright で開きページ送り・コード表示・全画像表示をスクショ目視。
 */

import { readFileSync, writeFileSync, existsSync } from 'fs';
import { join, basename, isAbsolute } from 'path';

// CLI 引数を解釈する。位置引数 slide-dir + 名前付き --manifest/--asset-base-url/--output。
function parseArgs(argv) {
  const args = { slideDir: null, manifest: null, assetBaseUrl: null, output: 'index.html' };
  for (const a of argv) {
    if (a.startsWith('--manifest=')) args.manifest = a.slice('--manifest='.length);
    else if (a.startsWith('--asset-base-url=')) args.assetBaseUrl = a.slice('--asset-base-url='.length);
    else if (a.startsWith('--output=')) args.output = a.slice('--output='.length);
    else if (!args.slideDir) args.slideDir = a;
  }
  return args;
}

// image-asset-manifest.json を読む。slide-dir 基準の相対 or 絶対パス。
// 壊れていれば null を返し、呼び出し側で warning 扱いにする。
function loadManifest(manifestArg, slideDir) {
  if (!manifestArg) return null;
  const p = isAbsolute(manifestArg) ? manifestArg : join(slideDir, manifestArg);
  if (!existsSync(p)) {
    console.error('WARN: manifest が見つかりません(相対パスで続行): ' + p);
    return null;
  }
  try {
    return JSON.parse(readFileSync(p, 'utf8'));
  } catch (e) {
    console.error('WARN: manifest を JSON として読めません(相対パスで続行): ' + p);
    return null;
  }
}

// 相対パス relPath を外部URLへ解決する。契約の解決順(publicUrl -> assetBaseUrl -> 相対)。
// 解決できれば絶対URL文字列、できなければ null を返す(呼び出し側で未解決を集計)。
function resolveAssetUrl(relPath, manifest, assetBaseUrl) {
  const fileEntry = manifest && manifest.files ? manifest.files[relPath] : null;
  if (fileEntry && typeof fileEntry.publicUrl === 'string' && fileEntry.publicUrl !== '') {
    return fileEntry.publicUrl;
  }
  // assetBaseUrl は CLI 指定を優先し、無ければ manifest トップの assetBaseUrl。
  let base = assetBaseUrl;
  if ((base === null || base === '') && manifest && typeof manifest.assetBaseUrl === 'string') {
    base = manifest.assetBaseUrl;
  }
  if (base) {
    return base.replace(/\/+$/, '') + '/' + basename(relPath);
  }
  return null;
}

function esc(s) {
  return String(s)
    .replace(/&/g, '&amp;')
    .replace(/</g, '&lt;')
    .replace(/>/g, '&gt;')
    .replace(/"/g, '&quot;');
}

// html-composite / html-primary の前面レイヤ(.visual-overlay)を生成する。
// overlayText の先頭を見出し、overlayCode を IDE暗パネルのコードブロック、
// tableHtml を Kanagawa配色のHTML表として描く。コード/表は画像に焼かずHTMLで描く。
function renderOverlay(s) {
  let inner = '';
  if (Array.isArray(s.overlayText) && s.overlayText.length > 0) {
    inner += '<div class="slide-heading">' + esc(s.overlayText[0]) + '</div>';
  }
  if (s.overlayCode && typeof s.overlayCode === 'object') {
    const oc = s.overlayCode;
    inner += '<div class="code-block">';
    if (oc.filename) inner += '<div class="filename">' + esc(oc.filename) + '</div>';
    inner += '<pre><code>' + esc(oc.code || '') + '</code></pre>';
    inner += '</div>';
  }
  if (s.tableHtml && typeof s.tableHtml === 'object') {
    const t = s.tableHtml;
    inner += '<table class="data-table"><thead><tr>';
    for (const h of (t.headers || [])) inner += '<th>' + esc(h) + '</th>';
    inner += '</tr></thead><tbody>';
    for (const row of (t.rows || [])) {
      inner += '<tr>';
      for (const c of (row || [])) inner += '<td>' + esc(c) + '</td>';
      inner += '</tr>';
    }
    inner += '</tbody></table>';
  }
  // overlayText の2行目以降を注記として下に添える
  if (Array.isArray(s.overlayText) && s.overlayText.length > 1) {
    inner += '<div class="overlay-notes">';
    for (let i = 1; i < s.overlayText.length; i += 1) {
      inner += '<span class="overlay-note">' + esc(s.overlayText[i]) + '</span>';
    }
    inner += '</div>';
  }
  return '<div class="visual-overlay">' + inner + '</div>';
}

const CSS = [
  ":root{",
  "  --accent-blue:#7E9CD8;--accent-aqua:#7AA89F;--accent-yellow:#DCA561;--accent-violet:#957FB8;--accent-pink:#D27E99;",
  "  --ink:#2D2D2D;--backdrop:#15161d;--nav-band-height:9vh;",
  "}",
  "*{box-sizing:border-box;}",
  "html,body{margin:0;padding:0;height:100%;background:var(--backdrop);font-family:'Noto Sans JP',-apple-system,BlinkMacSystemFont,'Hiragino Kaku Gothic ProN',Meiryo,sans-serif;color:var(--ink);}",
  ".deck{position:fixed;inset:0;display:flex;flex-direction:column;align-items:center;justify-content:center;overflow:hidden;}",
  ".slide-area{position:relative;width:min(100vw,calc((100vh - var(--nav-band-height)) * 16 / 9));height:min(56.25vw,calc(100vh - var(--nav-band-height)));aspect-ratio:16/9;margin-block:auto;container-type:size;background:#FAFAFA;box-shadow:0 1.2vh 4vh rgba(0,0,0,0.45);}",
  ".slider{position:absolute;inset:0;}",
  ".slider__item{position:absolute;inset:0;opacity:0;visibility:hidden;transition:opacity .45s ease;}",
  ".slider__item.is-active{opacity:1;visibility:visible;}",
  ":where(.ai-slide-canvas,.slide-fullbg,.slide-bg,[data-role=\"main-canvas\"]),",
  ":where(.ai-slide-canvas,.slide-fullbg,.slide-bg,[data-role=\"main-canvas\"]) img{display:block;width:100%;height:100%;object-fit:contain;}",
  ".visual-overlay{position:absolute;inset:0;display:flex;flex-direction:column;align-items:center;justify-content:center;gap:2.4cqh;padding:5cqh 5cqw;z-index:1;}",
  ".slide-heading{font-size:3.4cqh;font-weight:700;color:#0B2A55;background:rgba(255,255,255,.72);padding:.8cqh 2.4cqw;border-radius:1cqh;backdrop-filter:blur(3px);text-align:center;max-width:90cqw;}",
  ".code-block{background:#1F1F28;border:0.35cqh solid #0B2A55;border-radius:1.2cqh;box-shadow:0 1cqh 3cqh rgba(0,0,0,.45);max-width:86cqw;max-height:64cqh;overflow:auto;}",
  ".code-block .filename{background:#2A2A37;color:#7E9CD8;font-family:'SF Mono',Menlo,Consolas,monospace;font-size:1.7cqh;padding:.8cqh 1.8cqw;border-bottom:1px solid #0B2A55;border-radius:1.2cqh 1.2cqh 0 0;}",
  ".code-block pre{margin:0;padding:1.6cqh 2cqw;overflow:auto;}",
  ".code-block code{font-family:'SF Mono',Menlo,Consolas,monospace;font-size:2cqh;line-height:1.55;color:#DCD7BA;white-space:pre;display:block;}",
  ".data-table{border-collapse:collapse;background:rgba(255,255,255,.94);border-radius:1cqh;overflow:hidden;box-shadow:0 1cqh 3cqh rgba(0,0,0,.25);font-size:2.1cqh;max-width:92cqw;}",
  ".data-table th{background:#7E9CD8;color:#fff;padding:1.2cqh 2.2cqw;text-align:left;font-weight:700;white-space:nowrap;}",
  ".data-table td{padding:1cqh 2.2cqw;border-top:1px solid #E8E8EC;color:#2D2D2D;}",
  ".data-table tr:nth-child(even) td{background:rgba(232,232,236,.55);}",
  ".overlay-notes{display:flex;flex-wrap:wrap;gap:1.2cqw 1.6cqw;justify-content:center;max-width:90cqw;}",
  ".overlay-note{font-size:1.7cqh;color:#0B2A55;background:rgba(255,255,255,.66);padding:.5cqh 1.4cqw;border-radius:.8cqh;backdrop-filter:blur(2px);}",
  ".nav{position:static;flex:0 0 var(--nav-band-height);width:100%;min-height:var(--nav-band-height);display:flex;align-items:center;justify-content:center;gap:1.4vh;padding:1vh 1.8vh;background:rgba(20,21,28,.72);backdrop-filter:blur(8px);z-index:10;}",
  ".nav__btn{appearance:none;border:none;background:rgba(255,255,255,.12);color:#fff;width:3.6vh;height:3.6vh;border-radius:50%;font-size:2.2vh;line-height:1;cursor:pointer;display:flex;align-items:center;justify-content:center;transition:background .2s ease;}",
  ".nav__btn:hover{background:rgba(255,255,255,.28);}",
  ".nav__btn:focus-visible{outline:2px solid var(--accent-blue);outline-offset:2px;}",
  ".nav__dots{display:flex;align-items:center;gap:.9vh;flex-wrap:wrap;justify-content:center;max-width:70vw;}",
  ".nav__dot{width:1vh;height:1vh;border-radius:50%;background:rgba(255,255,255,.32);border:none;padding:0;cursor:pointer;transition:transform .2s ease,background .2s ease;}",
  ".nav__dot:hover{background:rgba(255,255,255,.6);}",
  ".nav__dot.is-active{background:var(--accent-blue);transform:scale(1.5);}",
  ".nav__dot:nth-child(5n){width:1.4vh;height:1.4vh;background:rgba(220,165,97,.7);}",
  ".nav__dot:nth-child(5n).is-active{background:var(--accent-yellow);}",
  ".nav__counter{color:rgba(255,255,255,.88);font-size:1.7vh;font-variant-numeric:tabular-nums;min-width:6vh;text-align:center;}",
  "@media print{",
  "  @page{size:A4 landscape;margin:0;}",
  "  html,body{width:297mm;min-height:210mm;background:#fff;height:auto;-webkit-print-color-adjust:exact;print-color-adjust:exact;}",
  "  body > *:not(.slider):not(.deck):not(script):not(style){display:none !important;visibility:hidden !important;}",
  "  .deck{position:static;display:block;overflow:visible;}",
  "  .slide-area{width:100%;height:auto;box-shadow:none;container-type:inline-size;}",
  "  .slider{position:static;}",
  "  .slider__item{position:relative;inset:auto;opacity:1 !important;visibility:visible !important;width:100%;aspect-ratio:16/9;background:#FAFAFA;page-break-after:always;break-after:page;display:flex;align-items:center;justify-content:center;}",
  "  .slider__item:last-child{page-break-after:auto;break-after:auto;}",
  "  .slider__item::after{content:attr(data-slide) \" / \" attr(data-total);display:none;}",
  "  :where(.ai-slide-canvas,.slide-fullbg,.slide-bg,[data-role=\"main-canvas\"]) img{width:100%;height:100%;object-fit:contain !important;print-color-adjust:exact;-webkit-print-color-adjust:exact;}",
  "  .visual-overlay{position:absolute;inset:0;display:flex !important;}",
  "  .code-block{print-color-adjust:exact;-webkit-print-color-adjust:exact;}",
  "  .nav{display:none !important;}",
  "}",
].join("\n");

const JS = [
  "(function(){",
  "  'use strict';",
  "  var slides=Array.prototype.slice.call(document.querySelectorAll('.slider__item'));",
  "  var total=slides.length;",
  "  var dotsWrap=document.getElementById('dots');",
  "  var counter=document.getElementById('counter');",
  "  var prevBtn=document.getElementById('prevBtn');",
  "  var nextBtn=document.getElementById('nextBtn');",
  "  var current=0;",
  "  var dots=[];",
  "  if(dotsWrap){",
  "    for(var i=0;i<total;i++){",
  "      var d=document.createElement('button');",
  "      d.className='nav__dot';d.type='button';d.setAttribute('role','tab');",
  "      d.setAttribute('aria-label',(i+1)+'枚目へ');",
  "      (function(idx){d.addEventListener('click',function(){go(idx);});})(i);",
  "      dotsWrap.appendChild(d);dots.push(d);",
  "    }",
  "  }",
  "  function render(){",
  "    for(var i=0;i<total;i++){",
  "      var active=i===current;",
  "      slides[i].classList.toggle('is-active',active);",
  "      if(dots[i]){dots[i].classList.toggle('is-active',active);dots[i].setAttribute('aria-selected',active?'true':'false');}",
  "    }",
  "    if(counter)counter.textContent=(current+1)+' / '+total;",
  "  }",
  "  function go(idx){current=(idx+total)%total;render();}",
  "  function next(){go(current+1);}",
  "  function prev(){go(current-1);}",
  "  if(nextBtn)nextBtn.addEventListener('click',next);",
  "  if(prevBtn)prevBtn.addEventListener('click',prev);",
  "  document.addEventListener('keydown',function(e){",
  "    if(e.key==='ArrowRight'||e.key==='PageDown'||e.key===' '){next();e.preventDefault();}",
  "    else if(e.key==='ArrowLeft'||e.key==='PageUp'){prev();e.preventDefault();}",
  "    else if(e.key==='Home'){go(0);}",
  "    else if(e.key==='End'){go(total-1);}",
  "  });",
  "  var startX=null;",
  "  var area=document.querySelector('.slide-area');",
  "  if(area){",
  "    area.addEventListener('touchstart',function(e){startX=e.touches[0].clientX;},{passive:true});",
  "    area.addEventListener('touchend',function(e){",
  "      if(startX===null)return;",
  "      var dx=e.changedTouches[0].clientX-startX;",
  "      if(Math.abs(dx)>40){dx<0?next():prev();}",
  "      startX=null;",
  "    },{passive:true});",
  "    area.addEventListener('click',function(e){",
  "      if(e.target.closest('.code-block')||e.target.closest('.data-table'))return;",
  "      var rect=area.getBoundingClientRect();",
  "      if(e.clientX>rect.left+rect.width*0.5){next();}else{prev();}",
  "    });",
  "  }",
  "  render();",
  "})();",
].join("\n");

function main() {
  const args = parseArgs(process.argv.slice(2));
  const slideDir = args.slideDir;
  if (!slideDir) {
    console.error('Usage: node scripts/build-deck-html.js <slide-dir> [--manifest=<path>] [--asset-base-url=<URL>] [--output=<filename>]');
    process.exit(2);
  }
  const genDir = join(slideDir, 'assets', 'generated');
  const planPath = join(genDir, 'image-deck-plan.json');
  if (!existsSync(planPath)) {
    console.error('FAIL: image-deck-plan.json not found: ' + planPath);
    process.exit(1);
  }
  // 外部URLモードの判定: --manifest または --asset-base-url のいずれか指定で有効。
  // 未指定なら従来どおり相対パス出力(後方互換)。
  const externalMode = (args.manifest !== null) || (args.assetBaseUrl !== null);
  const manifest = loadManifest(args.manifest, slideDir);
  const unresolved = [];

  const plan = JSON.parse(readFileSync(planPath, 'utf8'));
  const slides = plan.slides.slice().sort((a, b) => a.slide - b.slide);
  const total = slides.length;
  const title = esc(plan.deck && plan.deck.title ? plan.deck.title : 'スライド');

  let items = '';
  let composite = 0;
  for (let i = 0; i < slides.length; i += 1) {
    const s = slides[i];
    const metaPath = join(genDir, s.slug + '.meta.json');
    let alt = '';
    if (existsSync(metaPath)) {
      try { alt = JSON.parse(readFileSync(metaPath, 'utf8')).alt || ''; } catch (e) { alt = ''; }
    }
    const active = i === 0 ? ' is-active' : '';
    const type = s.slug.replace(/^slide-\d+[a-z]?-/, '');
    const pattern = s.pattern || 'image-only';
    const hasOverlay = (pattern === 'html-composite' || pattern === 'html-primary')
      && (s.overlayCode || s.tableHtml || (Array.isArray(s.overlayText) && s.overlayText.length > 0));

    let body = '';
    if (pattern !== 'html-primary') {
      // 既定は相対パス。外部モード時のみ URL 解決順で絶対URLへ差し替える。
      let webpSrc = 'assets/generated/' + s.slug + '.webp';
      let pngSrc = 'assets/generated/' + s.slug + '.png';
      if (externalMode) {
        const webpUrl = resolveAssetUrl(webpSrc, manifest, args.assetBaseUrl);
        const pngUrl = resolveAssetUrl(pngSrc, manifest, args.assetBaseUrl);
        if (webpUrl) webpSrc = webpUrl; else unresolved.push(webpSrc);
        if (pngUrl) pngSrc = pngUrl; else unresolved.push(pngSrc);
      }
      body += '\n        <picture class="ai-slide-canvas"><source srcset="' + esc(webpSrc) + '" type="image/webp"><img src="' + esc(pngSrc) + '" alt="' + esc(alt) + '"></picture>';
    }
    if (hasOverlay) {
      body += '\n        ' + renderOverlay(s);
      composite += 1;
    }
    items += '\n      <section class="slider__item' + active + '" data-slide="' + s.slide + '" data-type="' + esc(type) + '" data-total="' + total + '">'
      + body
      + '\n      </section>';
  }

  const html = '<!DOCTYPE html>\n'
    + '<html lang="ja">\n'
    + '<head>\n'
    + '<meta charset="UTF-8">\n'
    + '<meta name="viewport" content="width=device-width, initial-scale=1.0">\n'
    + '<title>' + title + '</title>\n'
    + '<link rel="preconnect" href="https://fonts.googleapis.com">\n'
    + '<link rel="preconnect" href="https://fonts.gstatic.com" crossorigin>\n'
    + '<link href="https://fonts.googleapis.com/css2?family=Noto+Sans+JP:wght@400;500;700;900&display=swap" rel="stylesheet">\n'
    + '<style>\n' + CSS + '\n</style>\n'
    + '</head>\n'
    + '<body>\n'
    + '<div class="deck">\n'
    + '  <div class="slide-area" data-deck-mode="full-image">\n'
    + '    <div class="slider" id="slider" data-deck-mode="full-image">\n'
    + items + '\n\n'
    + '    </div>\n'
    + '  </div>\n\n'
    + '  <nav class="nav" aria-label="スライドナビゲーション">\n'
    + '    <button class="nav__btn" id="prevBtn" aria-label="前のスライド" type="button">&#8249;</button>\n'
    + '    <div class="nav__dots" id="dots" role="tablist" aria-label="スライド一覧"></div>\n'
    + '    <button class="nav__btn" id="nextBtn" aria-label="次のスライド" type="button">&#8250;</button>\n'
    + '    <span class="nav__counter" id="counter">1 / ' + total + '</span>\n'
    + '  </nav>\n'
    + '</div>\n'
    + '<script>\n' + JS + '\n</script>\n'
    + '</body>\n'
    + '</html>\n';

  const outName = args.output || 'index.html';
  writeFileSync(join(slideDir, outName), html);
  const modeLabel = externalMode ? 'external-url' : 'relative-path';
  console.log(outName + ' written: ' + total + ' slides (' + composite + ' html-composite overlay), self-contained, ' + modeLabel);

  // 外部モードで未解決(相対のまま残る)画像があれば、GAS で壊れる事故を黙って
  // 通さない。stderr に列挙し終了コード1で失敗させる(サイレント失敗禁止)。
  if (externalMode && unresolved.length > 0) {
    console.error('FAIL: 外部URLモードで未解決の画像が ' + unresolved.length + ' 件あります(publicUrl/assetBaseUrl 未設定):');
    for (const u of unresolved) console.error('  - ' + u);
    console.error('対処: image-asset-manifest.json の publicUrl を埋めるか --asset-base-url を指定してください。');
    process.exit(1);
  }
}

main();
