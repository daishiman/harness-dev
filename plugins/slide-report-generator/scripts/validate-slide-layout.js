#!/usr/bin/env node
/**
 * validate-slide-layout.js — 実描画レイアウト契約の検証ゲート。
 *
 * SVG 単体の幾何は scripts/validate-svg-diagram.py が静的に見る。こちらは
 * ブラウザで実際に描いてからでないと分からないもの、すなわち「要素どうしの
 * 位置関係」を見る。認知負荷は個々の部品でなく部品の重なり方で決まるため、
 * ここが読みやすさの実質的なゲートになる。
 *
 * 検査する項目:
 *   L1 重なり     見出し・本文・図解・ページネーション帯が互いに重ならない
 *   L2 はみ出し   どの要素もスライド (印刷面) の外へ出ない
 *   L3 溢れ       スクロールしないと読めない要素がない (scrollHeight > clientHeight)
 *   L4 図解の面積 図解がスライド面積の 12% 以上ある (小さすぎる図は読ませる意味がない)
 *   L5 余白       主要要素どうしに最低 8px の間隔がある (接触は重なりと同じく読みにくい)
 *   L6 文字量     1 スライドの本文が 340 字以内 (1メッセージ1スライドの実効的な上限)
 *   L8 充填率     内容ブロックの外接矩形の和集合 / stage が契約のレンジに入る (面ごと・例外あり)
 *   L8-ink 中身   テキスト行 + media / 内容ブロック和集合。伸ばしただけの空カードを弾く
 *   L8-font 書体  充填率を書体の縮小で稼いでいない (書体の下限は系統ごとに正本が違う)
 *   L9 縦の残余   群の上下余白の合計比・上下の非対称・群内間隔が契約のレンジに入る
 *
 * L8 と L8-ink は対で効く。部材を伸ばして L8 を稼ぐと、中身は増えないので L8-ink が
 * 落ちる。片方だけでは「ピチピチだが中身は空」を止められない。
 *
 * --measure を付けると判定せず面ごとの実測値だけを出す (閾値を決める前に測るための口)。
 *
 * L8 / L9 の数値はこのファイルに持たない。assets/slide-templates/frame-contract.json の
 * fill_policy / vertical_margin_policy / typography が唯一の正本で、面種別の例外は
 * fill_policy.exceptions を、面 → 例外 kind の対応は assets/slide-templates/registry.json を引く。
 *
 * 使い方:
 *   node scripts/validate-slide-layout.js <deck/index.html> [--viewport 1920x1080] [--strict]
 * 複数の viewport を試すには --viewport を繰り返す。既定の観測点は frame-contract.json の
 * viewports.default が持つ (縦横比の両端を含む。選定根拠は同 key の note)。
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

// 面の余白率・充填率・書体下限の正本。ここでは読むだけで、値を持たない。
const CONTRACT_PATH = path.join(PLUGIN_ROOT, 'assets', 'slide-templates', 'frame-contract.json');
const REGISTRY_PATH = path.join(PLUGIN_ROOT, 'assets', 'slide-templates', 'registry.json');

function loadJson(p) {
  try {
    return JSON.parse(fs.readFileSync(p, 'utf8'));
  } catch (_) {
    return null;
  }
}

const SEVERITY = {
  L0: 'error',   // 対象 0 件・成果物でない入力は検査済みにしない
  L7: 'error',   // engine と skeleton は @page 契約が異なるため同一 deck に混在不可
  L1: 'error',   // 重なりは誤検知しにくく、読めなくなる直接の原因
  L2: 'error',   // 印刷・撮影で確実に切れる
  L3: 'error',   // スライドはスクロールできない前提の媒体
  L4: 'warning', // 意図的に小さい図 (補助的な記号) がありうる
  L5: 'warning', // 8px は目安で、詰めたい意匠もありうる
  L6: 'warning', // 密度は用途による (配布資料は濃くてよい)
  L8: 'warning', // 意図的な低密度面がありうる (--strict で fail へ昇格する)
  'L8-ink': 'warning', // 部材の中身の詰まり具合。L8 と対で見る
  'L8-font': 'error', // 書体を下限未満へ下げて充填率を稼ぐ抜け道は例外なく不可
  L9: 'warning', // 縦の置き場所は意匠の幅があり、面ごとの逸脱は説明可能なことがある
  // 描画時に付けた作者側のインライン custom property が、面をめくると消える形の欠陥。
  // 2026-08-14 に実物で起きた (gsap の clearProps: 'all' が style 属性ごと落とし、
  // --grid-cols / --fit-t / --fit-d が消えて列数と見出しの幅フィットが壊れた)。
  // 初期表示は正しいので、静的な HTML の検査でも初回スクショでも黙って通る。
  // 消えた = 描画時の指定が効かなくなるということなので警告では足りない。
  //
  // ただし error の意味は「宣言が消えた」であって「見た目が壊れた」ではない。
  // 消えた宣言と同じ結果を別の経路が保証していれば、error でも実害は出ない。
  // 実例 (2026-08-14 / slide-2026-08-15-AI質問会): 5 面で --grid-cols が消えて
  // error になったが、実際の列数は 1 つも変わらなかった。理由は 2 つで、
  //   - 3 列の面の指定値が 3 で、repeat(var(--grid-cols, 3), 1fr) の既定値と同値
  //   - 1 列の面は data-layout="stack" を持ち、属性側の
  //     .grid-container[data-layout="stack"] { grid-template-columns: 1fr } が
  //     変数と無関係に 1 列を保証していた
  // 赤が出たら、直す前にまず「めくった後の実際の見え方」を測ること。
  // 既定値と一致している / 別の宣言が同じ結果を保証している場合は、直すのは
  // 見た目のためではなく、次に値を変えたときに壊れないようにするためになる。
  // 急いで直す話ではないので、その区別を報告に書くこと。
  L10: 'error',
};

/**
 * L10 で保持を見るインライン custom property。
 * 実際にめくって消えたのを確認した 3 つだけを入れる。「作者が付けた宣言は
 * 遷移で消えてはいけない」を一般則として書きたくなるが、一般則にすると
 * gsap 自身が付ける transform / opacity まで拾って必ず落ちる。
 */
const TRANSITION_KEPT_PROPS = ['--grid-cols', '--fit-t', '--fit-d'];

/**
 * 既定の観測点はこのファイルに持たない。frame-contract.json の viewports.default が正本。
 * 画面の縦横比は外側 (根フォント・面のパディング) の単位系が切り替わる軸なので、
 * 観測点の選び方そのものが契約事項になる。選定根拠は同 key の note を参照。
 */
function parseViewports(argv) {
  const out = [];
  argv.forEach((a, i) => {
    if (a === '--viewport' && argv[i + 1]) {
      const m = /^(\d+)x(\d+)$/.exec(argv[i + 1]);
      if (m) out.push({ width: Number(m[1]), height: Number(m[2]) });
    }
  });
  if (out.length) return out;
  const contract = loadJson(CONTRACT_PATH);
  const list = (contract && contract.viewports && Array.isArray(contract.viewports.default))
    ? contract.viewports.default.filter((v) => Number(v.width) > 0 && Number(v.height) > 0)
    : [];
  if (!list.length) {
    // 契約を読めないまま既定値を持ち出すと、検査器が自前の数値で走ってしまう。
    console.error('frame-contract.json の viewports.default を読めない。--viewport で明示するか契約を直す。');
    process.exit(1);
  }
  return list.map((v) => ({ width: Number(v.width), height: Number(v.height) }));
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

/**
 * 「新しい面集合は旧 union の部分集合なので指摘は増えない」という保証は、
 * この定義のときに限る。面のセレクタを 1 つでも足せば成立しない。
 * この保証を根拠に「今後も指摘は増えない」と読まないこと。
 *
 * 面集合の唯一の定義。ページ側へ 1 度だけ注入し、面を数える / 選ぶ / is-active を
 * 付け替える の 3 箇所すべてがこれを呼ぶ (綴りを 2 つに分けない)。
 *
 * 面のクラスがあるものを優先し、無いときだけ [data-slide] へ落ちる。
 * 4 セレクタの union で数えてはいけない: [data-slide] はページネーションのドット等
 * 面でない要素にも付いており、実測で 30 面の deck が 55 と数えられた
 * (存在しない面について充填率を判定し、type=? の 0.0% 警告を量産していた)。
 */
const FACE_SET_DEF = `window.__srgFaces = function () {
  const q = (s) => Array.prototype.slice.call(document.querySelectorAll(s));
  const item = q('.slider__item');
  if (item.length) return item;
  const srg = q('.srg-slide');
  if (srg.length) return srg;
  const skeleton = q('[data-slide-skeleton]');
  if (skeleton.length) return skeleton;
  return q('[data-slide]');
};`;

/** ブラウザ側で 1 スライドぶんの実測値を集める。 */
function collectSlide(arg) {
  const { index, contract, registryMap } = arg;
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
  const el = window.__srgFaces()[index];
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
  //
  // 既知の取りこぼし (偽陽性・閾値では直せない):
  //   日本語の行末で閉じ括弧・句読点は「ぶら下げ」で枠の外へ半角ぶん出る。ぶら下がった
  //   ぶんは描画上は隣へはみ出さないが、scrollWidth はその送り幅を足して返すため、
  //   実際には収まっている行が横方向の溢れとして鳴る。全角 1 文字ぶんの送りが
  //   おおよそ 27px あるので、閾値 12px では拾えない。
  //   実例: 9/12 デッキ slide3 の「実演（事前申込4名）」が 2560x1080 で 14px 検出。
  //   セル 678-1242 / 見出し枠 712-1216 / 行のインク 712-1230 で、はみ出しぶんは
  //   カードの padding 25.92px に吸われて隣のカードには届いていない (次のセルは 1259 から)。
  //   同種で slack 未満のものが slide4 / 10 / 11 / 13 にもあり、旧エンジンの出荷済み
  //   HTML でも 3px 出ている。つまりレターボックス化で生じた退行ではない。
  //   閾値を上げれば本物の横溢れを見逃すので、ここは触らない。判別するには
  //   Range#getClientRects で行のインク幅を採り scrollWidth と突き合わせる必要がある。
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

  const type = el.getAttribute('data-type') || el.getAttribute('data-slide-type') || '?';
  const skeleton = el.getAttribute('data-slide-skeleton') || '';

  // --- L8 / L9 の実測 -------------------------------------------------------
  const slideBox = box(el);

  // 面 → 例外 kind。ひな形名が最優先 (media_override で載せ替わった面はここで分かる)、
  // 次に写像表、最後に slideType の接頭辞落とし。どれも contract の exceptions に
  // 実在する key だけを採る。対応が無ければ既定レンジ。
  const exceptions = (contract.fill_policy && contract.fill_policy.exceptions) || {};
  const kindFor = () => {
    const cands = [];
    // 面が自分で宣言した例外が最優先。決定論経路 (engine) は写像表の kind しか
    // 持てないので、ひな形を使わない面が例外を名乗る唯一の口がこれになる。
    const declared = el.getAttribute('data-fill-exception');
    if (declared) cands.push(declared);
    if (skeleton) cands.push(skeleton.replace(/^layout-/, ''));
    const mapped = registryMap[type] && registryMap[type].skeleton;
    if (mapped) cands.push(String(mapped).replace(/^layout-/, ''));
    cands.push(String(type).replace(/^(slide|diagram)-/, ''));
    for (const c of cands) if (Object.prototype.hasOwnProperty.call(exceptions, c)) return c;
    return null;
  };
  let kind = kindFor();

  // stage は実物があればそれ、無ければ contract の比で面から割り出す
  // (engine 系の deck に .srg-slide__stage は無いが、chrome の取り分は同じ契約に従う)。
  const stageEl = el.querySelector('.srg-slide__stage');
  const cv = contract.canvas;
  const st = contract.stage;
  const sx = slideBox.width / cv.width;
  const sy = slideBox.height / cv.height;
  const stage = (stageEl && visible(stageEl)) ? box(stageEl) : {
    left: slideBox.left + st.x * sx,
    top: slideBox.top + st.y * sy,
    right: slideBox.left + (st.x + st.width) * sx,
    bottom: slideBox.top + (st.y + st.height) * sy,
    width: st.width * sx,
    height: st.height * sy,
  };
  const stageArea = Math.max(0, stage.width) * Math.max(0, stage.height);

  const inChrome = (node) => !!(node && node.closest
    && node.closest('[data-chrome],.slider-footer,.slider-header,.pg-controls,.pg-dots,.pg-counter,.pg-progress,.pg-section-nav'));

  // 面積比 (L8 / L8-ink) から外すのは chrome だけ。見出し・リードも面を占める部材で
  // あり、これを外すと表紙・章扉のように見出しが本体の面が 0 付近になって測れない。
  // 見出しを外すのは縦の残余 (L9) の「群」の定義だけで、そちらは別の excludeSel。
  const excludeSel = 'h1,h2,h3,.slide-lead,.srg-slide__lead,.srg-slide__title,.srg-slide__note';
  const outOfGroup = (node) => !node || inChrome(node);

  const clip = (r) => ({
    left: Math.max(r.left, stage.left), top: Math.max(r.top, stage.top),
    right: Math.min(r.right, stage.right), bottom: Math.min(r.bottom, stage.bottom),
  });
  const usable = (r) => r.right - r.left > 1 && r.bottom - r.top > 1;

  const MEDIA_SEL = 'svg,img,canvas,video,picture,table,pre,.mermaid,.d3-mount';

  // svg は viewBox の中身を要素矩形の中でレターボックス配置するので、要素矩形は
  // 「描かれた面積」ではない。図が小さく隅に寄っていても要素矩形が stage を覆っていれば
  // 過密と誤判定され、しかも block_ink まで満点になって空きが見えなくなる (背景画像で
  // 面を塞いだのと同じ穴の media 版)。描画の外接矩形 (getBBox を画面座標へ写したもの)
  // を要素矩形で切って使い、求まらないときだけ従来どおり要素矩形へ倒す。
  const paintBox = (e) => {
    const r = box(e);
    if (!e.tagName || e.tagName.toLowerCase() !== 'svg' || typeof e.getBBox !== 'function') return r;
    let bb = null;
    try { bb = e.getBBox(); } catch (_) { return r; }
    if (!bb || !(bb.width > 0) || !(bb.height > 0)) return r;
    const m = typeof e.getScreenCTM === 'function' ? e.getScreenCTM() : null;
    if (!m) return r;
    const xs = [];
    const ys = [];
    const corners = [[bb.x, bb.y], [bb.x + bb.width, bb.y],
      [bb.x, bb.y + bb.height], [bb.x + bb.width, bb.y + bb.height]];
    for (const [ux, uy] of corners) {
      xs.push(m.a * ux + m.c * uy + m.e);
      ys.push(m.b * ux + m.d * uy + m.f);
    }
    const p = {
      left: Math.max(r.left, Math.min(...xs)), top: Math.max(r.top, Math.min(...ys)),
      right: Math.min(r.right, Math.max(...xs)), bottom: Math.min(r.bottom, Math.max(...ys)),
    };
    return (p.right - p.left > 1 && p.bottom - p.top > 1) ? p : r;
  };

  // インク (テキスト行ボックス + media)。テキストは要素の外接矩形ではなく Range の
  // 行ボックスを採る。伸びただけの空スロットにインクは無い、という区別がここで付く。
  const inkRects = [];
  const walker = document.createTreeWalker(el, NodeFilter.SHOW_TEXT);
  let tn;
  let minFontPx = Infinity;
  let minFontWhere = '';
  while ((tn = walker.nextNode())) {
    if (!tn.nodeValue || !tn.nodeValue.trim()) continue;
    const parent = tn.parentElement;
    if (!parent || !visible(parent) || inChrome(parent)) continue;
    // SVG の中の文字は viewBox で拡縮されるので、computed font-size は CSS px では
    // なくユーザ単位。ここで比べると必ず食い違う。図の文字寸法は
    // validate-svg-diagram.py が静的に見ている。
    if (!parent.closest('svg')) {
      const fs = parseFloat(getComputedStyle(parent).fontSize) || 0;
      if (fs > 0 && fs < minFontPx) {
        minFontPx = fs;
        minFontWhere = (tn.nodeValue || '').trim().slice(0, 16);
      }
    }
    if (outOfGroup(parent)) continue;
    const range = document.createRange();
    range.selectNodeContents(tn);
    for (const rc of range.getClientRects()) {
      if (rc.width <= 1 || rc.height <= 1) continue;
      const c = clip(rc);
      if (usable(c)) inkRects.push(c);
    }
  }
  // media (図・表・コードなどの「面の主役の矩形」)。入れ子は最も外側だけ。
  const mediaEls = [...el.querySelectorAll(MEDIA_SEL)]
    .filter(visible)
    .filter((e) => !outOfGroup(e))
    .filter((e) => !e.parentElement || !e.parentElement.closest(MEDIA_SEL));
  for (const m of mediaEls) {
    const c = clip(paintBox(m));
    if (usable(c)) inkRects.push(c);
  }
  // CSS 背景で敷いた画像も media。要素としては空の div なので上の走査には入らないが、
  // 見る側にとっては img と同じ「面の主役の矩形」。これを数えないと背景画像の面は
  // 文字ぶんだけの充填率になり、全面画像の面が構造的に下限割れになる。
  // 階調 (linear-gradient 等) は装飾なので除く。実画像 = url() のものだけを採る。
  // ただし算入できるのは塗り面積が要素矩形と一致すると確定できるとき (cover /
  // 100% 100%) だけ。45% のような部分敷きは画像の実寸が分からないと塗り面積が
  // 出せないので、要素矩形で代用すると装飾の一枚で面が全面画像に化ける。確定
  // できないものは数えない (過小に倒す。過大に倒すと例外扱いで検査ごと素通りする)。
  let bgFullBleed = false;
  let bgPartial = 0;
  const bgImageRects = [];
  for (const e of [...el.querySelectorAll('*')].filter(visible).filter((x) => !outOfGroup(x))) {
    const cs = getComputedStyle(e);
    const bg = cs.backgroundImage;
    if (!bg || bg === 'none' || !bg.includes('url(')) continue;
    const size = (cs.backgroundSize || '').trim();
    if (size !== 'cover' && size !== '100% 100%') { bgPartial++; continue; }
    const c = clip(box(e));
    if (!usable(c)) continue;
    inkRects.push(c);
    bgImageRects.push(c);
    if ((c.right - c.left) * (c.bottom - c.top) > 0.9 * stageArea) bgFullBleed = true;
  }
  // stage をほぼ覆う背景画像を持つ面は、定義上 fill = 1.0 の全面画像。面積比の規定が
  // 成立しないので、面が自分で名乗っていなくても image-full として扱う。
  if (!kind && bgFullBleed && Object.prototype.hasOwnProperty.call(exceptions, 'image-full')) {
    kind = 'image-full';
  }

  // 内容ブロック (カード・帯・ステップ・リスト項目・media) の外接矩形。
  // 「部材」の見分けは背景・枠・影という視覚的な実体の有無で付ける。単なる入れ物
  // (レイアウト用の div) は素通りして中の部材まで降りる。stage をほぼ覆う大きさの
  // ものは部材ではなく入れ物なので、これも降りる (でないと面全部が 1 部材になる)。
  const blockRects = [];
  const isPart = (e) => {
    if (e.matches(MEDIA_SEL) || e.matches('li')) return true;
    const cs = getComputedStyle(e);
    if (cs.backgroundImage && cs.backgroundImage !== 'none') return true;
    if (cs.backgroundColor && !/^rgba\(0, 0, 0, 0\)$|^transparent$/.test(cs.backgroundColor)) return true;
    if (['Top', 'Right', 'Bottom', 'Left'].some((s) => parseFloat(cs[`border${s}Width`]) > 0)) return true;
    if (cs.boxShadow && cs.boxShadow !== 'none') return true;
    return false;
  };
  const collectParts = (node) => {
    let added = false;
    for (const child of [...node.children]) {
      if (!visible(child) || outOfGroup(child)) continue;
      const r = clip(paintBox(child));
      if (!usable(r)) continue;
      const coversStage = (r.right - r.left) * (r.bottom - r.top) > 0.9 * stageArea;
      if (isPart(child) && !coversStage) {
        blockRects.push(r);
        added = true;
        continue;
      }
      if (collectParts(child)) {
        added = true;
      } else if ((child.textContent || '').trim() && !coversStage) {
        // 部材の体裁は無いが文字を持つ末端 (素の段落など) は、それ自体が部材。
        blockRects.push(r);
        added = true;
      }
    }
    return added;
  };
  collectParts((stageEl && visible(stageEl)) ? stageEl : el);
  // 背景画像の矩形は部材でもある。stage をほぼ覆うものは collectParts が入れ物として
  // 素通りするので、ここで入れ直す (全面画像の面が「文字ぶんだけ」にならないように)。
  for (const c of bgImageRects) blockRects.push(c);

  // 重なりぶんを二重に数えないよう、座標圧縮で和集合面積を出す。
  // 座標は実数のまま扱う。矩形の辺を整数へ丸めると、辺 1 本あたり最大 0.5px の誤差が
  // 面積へ乗り、しかも箱が縮む観測点ほど同じ 0.5px の比重が上がるので、同一の deck を
  // 別の画面幅で測ったときに比が食い違う。これは面の性質ではなく検査器が持ち込んだ
  // ノイズで、閾値ぎりぎりの面の合否をそれだけで裏返しうる。走査線は辺の値そのものを
  // 境界に使い、区間の中点が矩形に含まれるかで塗りを判定するだけなので、座標が整数で
  // ある必要はない (中点は相異なる 2 つの境界の間に必ず厳密に入る)。
  const unionArea = (rects) => {
    if (!rects.length) return 0;
    const rs = rects.map((r) => ({
      left: r.left, top: r.top, right: r.right, bottom: r.bottom,
    }));
    const xs = [...new Set(rs.flatMap((r) => [r.left, r.right]))].sort((a, b) => a - b);
    const ys = [...new Set(rs.flatMap((r) => [r.top, r.bottom]))].sort((a, b) => a - b);
    let area = 0;
    for (let i = 0; i < xs.length - 1; i++) {
      for (let j = 0; j < ys.length - 1; j++) {
        const cx = (xs[i] + xs[i + 1]) / 2;
        const cy = (ys[j] + ys[j + 1]) / 2;
        if (rs.some((r) => r.left <= cx && cx <= r.right && r.top <= cy && cy <= r.bottom)) {
          area += (xs[i + 1] - xs[i]) * (ys[j + 1] - ys[j]);
        }
      }
    }
    return area;
  };
  const inkArea = unionArea(inkRects);
  const blockArea = unionArea(blockRects);
  // stage_fill = 部材が面を占める割合 (詰め込み過多・空白過多を見る)。
  // block_ink  = 部材の中身の詰まり具合 (伸ばしただけの空カードを弾く)。
  // 伸長で stage_fill を稼ぐと block_ink が落ちる、という関係で抜け道を塞ぐ。
  const fillRatio = stageArea > 0 ? blockArea / stageArea : 0;
  const blockInkRatio = blockArea > 0 ? inkArea / blockArea : 0;

  // L9 縦方向の残余。基準は「本文の列 (見出しを含む) が stage の中でどこに置かれて
  // いるか」。見出しを stage から先に差し引いて残りの中で測ると、列ごと中央へ寄せても
  // 見出し下の間隔は動かないので上余白が変わらず、中央寄せが検出できない。つまり
  // 面を正しく直しても赤が消えない = 規約内に解が無い検査になる。列全体を 1 つの塊と
  // して stage に対して測れば、中央寄せはそのまま delta = 0 として出る。
  // 群の内部の一体感 (近接) だけは見出しを含めない「群」で測る (見出し下の間隔は
  // title_block_height の意匠であって、群が割れて見える原因ではない)。
  let main = el.querySelector('.srg-slide__main') || el.querySelector('.slider__content') || el;
  const childBlocks = (parent) => [...parent.children].filter(visible).filter((e) => !inChrome(e))
    .filter((e) => !e.matches(excludeSel));
  let blocks = childBlocks(main);
  // 中身が 1 個だけで、しかも親とほぼ同じ高さなら、それは群ではなく入れ物。
  // 入れ物を群として測ると余白は常に 0 付近になり、この検査は何も見なくなる。
  for (let depth = 0; depth < 4 && blocks.length === 1; depth++) {
    const only = blocks[0];
    const inner = childBlocks(only);
    if (!inner.length) break;
    if (box(only).height < box(main).height * 0.9) break;
    main = only;
    blocks = inner;
  }
  // 見出し・リード・脚注も列の一部。stage の内側にあるものだけを列の範囲に入れる
  // (帯やナビは chrome として既に外してある)。
  const outside = [...el.querySelectorAll(excludeSel)].filter(visible).filter((e) => !inChrome(e))
    .map(box)
    .filter((b) => b.bottom > stage.top && b.top < stage.bottom);
  let vertical = null;
  if (blocks.length) {
    // 列の範囲は要素矩形で採る。列がどこに置かれているかは CSS の箱の配置そのもので、
    // 描画の外接矩形ではない。ここへ描画矩形を混ぜると、見出しは要素矩形 (領域の上端に
    // 密着)・図は描画矩形 (レターボックスのぶん縮む) となり、要素として上下対称に
    // 置かれた図が「下だけ余っている」と出る。図の中身の偏りは列の対称性ではないので
    // 下の mediaSkew で別に測る。
    const bs = blocks.map(box);
    const colTops = [...bs.map((b) => b.top), ...outside.map((b) => b.top)];
    const colBottoms = [...bs.map((b) => b.bottom), ...outside.map((b) => b.bottom)];
    const groupTop = Math.min(...colTops);
    const groupBottom = Math.max(...colBottoms);
    // 基準領域は「その面が実際に本文へ渡している領域」。ひな形経路は stage 要素そのもの、
    // engine 経路は面のパディングボックス (chrome の取り分を padding で確保している)。
    // 契約由来の stage 矩形を engine 経路へ当てると、面の padding と契約 chrome の差が
    // 全面に同じ量の非対称として出てしまい、面をどう直しても消えない赤になる。
    // 領域は deck 内で一定なので、見出しの大小で厳しさが変わる問題は起きない。
    const contentRegion = () => {
      if (stageEl && visible(stageEl)) return box(stageEl);
      const cs = getComputedStyle(el);
      const b = box(el);
      return {
        top: b.top + (parseFloat(cs.paddingTop) || 0),
        bottom: b.bottom - (parseFloat(cs.paddingBottom) || 0),
        left: b.left + (parseFloat(cs.paddingLeft) || 0),
        right: b.right - (parseFloat(cs.paddingRight) || 0),
      };
    };
    const region = contentRegion();
    const regionTop = region.top;
    const regionBottom = region.bottom;
    const regionH = regionBottom - regionTop;
    if (regionH > 1) {
      const topMargin = groupTop - regionTop;
      const bottomMargin = regionBottom - groupBottom;
      // 近接の原則。群を段 (縦に重ならない塊) へまとめ、段どうしの間隔を段の高さで
      // 割る。間隔が段の高さに近づくと、群は 1 つでなく複数に割れて見える。
      const rows = [];
      for (const b of [...bs].sort((p, q) => p.top - q.top)) {
        const last = rows[rows.length - 1];
        if (last && b.top < last.bottom) {
          last.top = Math.min(last.top, b.top);
          last.bottom = Math.max(last.bottom, b.bottom);
        } else {
          rows.push({ top: b.top, bottom: b.bottom });
        }
      }
      let proximity = null;
      if (rows.length >= 2) {
        const gaps = [];
        for (let k = 1; k < rows.length; k++) gaps.push(rows[k].top - rows[k - 1].bottom);
        const heights = rows.map((r) => r.bottom - r.top).sort((p, q) => p - q);
        const medianH = heights[Math.floor(heights.length / 2)];
        const maxGap = Math.max(...gaps);
        if (medianH > 1) {
          proximity = { ratio: maxGap / medianH, gap: Math.round(maxGap), rowH: Math.round(medianH), rows: rows.length };
        }
      }
      // 上下差の分母は stage.height 固定。見出しを差し引いた残り (regionH) を分母に
      // すると、見出しの大きい面ほど同じ 2% が数 px まで縮み、面ごとに厳しさが変わる
      // 検査になる。契約の note_formula も stage.height 基準。
      // さらに、面座標で grid.base (4px) に満たない差は設計格子で表せないので不問。
      const deltaPx = Math.abs(topMargin - bottomMargin);
      const gridBase = (contract.grid && contract.grid.base) || 0;
      const deltaCanvasPx = sy > 0 ? deltaPx / sy : deltaPx;
      // 図そのものの偏り。svg は viewBox の中身を要素矩形の中へレターボックス配置する
      // ので、要素が領域に対して対称に置かれていても中身は上下どちらかへ寄れる。列を
      // 要素矩形で測る以上その偏りは列の対称性には現れないため、要素矩形の中の上下の
      // 余りとして別に測る。許容は列と同じ max_symmetry_delta を使う (どちらも面の
      // 高さに対する上下差なので、新しい閾値を増やさずに済む)。
      let mediaSkew = null;
      for (const m of mediaEls) {
        const mb = box(m);
        const pb = paintBox(m);
        const d = Math.abs((pb.top - mb.top) - (mb.bottom - pb.bottom));
        if (!(d >= 1) || mb.bottom - mb.top < 1) continue;
        if (!mediaSkew || d > mediaSkew.px) {
          mediaSkew = {
            px: d,
            top: Math.round(pb.top - mb.top),
            bottom: Math.round(mb.bottom - pb.bottom),
            tag: m.tagName.toLowerCase(),
          };
        }
      }
      if (mediaSkew) {
        const skewCanvasPx = sy > 0 ? mediaSkew.px / sy : mediaSkew.px;
        mediaSkew.ratio = skewCanvasPx < gridBase ? 0 : mediaSkew.px / regionH;
        mediaSkew.px = Math.round(mediaSkew.px);
      }
      vertical = {
        // 1px 未満の食い違いは丸めの残りなので 0 とする (-0.0% と出さない)。
        outerRatio: Math.abs(regionH - (groupBottom - groupTop)) < 1
          ? 0 : (regionH - (groupBottom - groupTop)) / regionH,
        symmetryDelta: deltaCanvasPx < gridBase ? 0 : deltaPx / regionH,
        symmetryDeltaPx: Math.round(deltaPx),
        topMargin: Math.round(topMargin),
        bottomMargin: Math.round(bottomMargin),
        regionH: Math.round(regionH),
        blocks: blocks.length,
        proximity,
        mediaSkew,
      };
    }
  }

  // 横方向の残余。縦と対称の指標だが、まだ判定には使わない (--measure で出すだけ)。
  // 分布を取るために 2 通りを並べて測る。(1) 列 = 部材の矩形の外接範囲。縦と同じ採り方。
  // (2) インク = テキスト行ボックスと media の外接範囲。横は縦と事情が違い、部材の箱は
  // 幅いっぱいに伸びるのが普通なので、(1) はほぼ常に 0 付近になって「右半分が空」を
  // 検出できない。中身がどこまで広がっているかは (2) にしか出ない。どちらを正本に
  // するかは分布を見てから決める (根拠なく閾値を足さない)。
  let horizontal = null;
  {
    const hregion = (stageEl && visible(stageEl)) ? box(stageEl) : (() => {
      const cs = getComputedStyle(el);
      const b = box(el);
      return {
        left: b.left + (parseFloat(cs.paddingLeft) || 0),
        right: b.right - (parseFloat(cs.paddingRight) || 0),
      };
    })();
    const regionW = hregion.right - hregion.left;
    const span = (rects) => (rects.length ? {
      left: Math.min(...rects.map((r) => r.left)),
      right: Math.max(...rects.map((r) => r.right)),
    } : null);
    const bSpan = span(blockRects);
    const iSpan = span(inkRects);
    const measureSide = (s) => {
      if (!s || !(regionW > 1)) return null;
      const lm = s.left - hregion.left;
      const rm = hregion.right - s.right;
      return {
        outer: (regionW - (s.right - s.left)) / regionW,
        sym: Math.abs(lm - rm) / regionW,
        left: Math.round(lm),
        right: Math.round(rm),
      };
    };
    const hb = measureSide(bSpan);
    const hi = measureSide(iSpan);
    if (hb || hi) horizontal = { block: hb, ink: hi, regionW: Math.round(regionW) };
  }

  // 書体の下限は系統で正本が違う。ひな形経路は絶対座標 1280x720 の面なので
  // canvas 座標へ正規化して typography.min と比べる。engine 経路は rem 基準で
  // viewport に追従しないため、正規化すると大きい画面ほど不当に小さく出る。
  // そちらは CSS px のまま root font-size 基準の下限と比べる。
  const isSkeleton = !!(stageEl || skeleton || el.matches('.srg-slide'));
  const rootFontPx = parseFloat(getComputedStyle(document.documentElement).fontSize) || 16;
  const minFontRaw = Number.isFinite(minFontPx) ? minFontPx : null;

  return {
    type, skeleton, kind, isSkeleton, rootFontPx,
    slide: slideBox, heads, bodies, figs, bands, overflowing, bodyChars,
    fillRatio, blockInkRatio, stageArea: Math.round(stageArea),
    inkArea: Math.round(inkArea), blockArea: Math.round(blockArea),
    blockCount: blockRects.length,
    bgPartial,
    minFontPx: minFontRaw,
    minFontCanvasPx: (minFontRaw !== null && sx > 0) ? minFontRaw / sx : minFontRaw,
    minFontWhere,
    vertical,
    horizontal,
  };
}

async function run() {
  const argv = process.argv.slice(2);
  const target = argv.find((a) => !a.startsWith('--')
    && !/^\d+x\d+$/.test(a));
  const strict = argv.includes('--strict');
  // 値を決める前に実測を見るための口。判定はせず、面ごとの実測値だけを出す。
  const measure = argv.includes('--measure');
  const viewports = parseViewports(argv);
  if (!target) {
    console.error('usage: validate-slide-layout.js <deck/index.html> [--viewport WxH] [--strict] [--measure]');
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

  const contract = loadJson(CONTRACT_PATH);
  if (!contract || !contract.fill_policy || !contract.vertical_margin_policy) {
    console.error(`ERROR [L0] ${CONTRACT_PATH}: 面の寸法契約が読めない (L8/L9 は契約が唯一の正本)`);
    process.exit(1);
  }
  const registryMap = (loadJson(REGISTRY_PATH) || {}).map || {};
  const fp = contract.fill_policy;
  const vp2 = contract.vertical_margin_policy;
  const fontMin = contract.typography && contract.typography.min;
  const fontMinRem = contract.typography && contract.typography.min_rem_engine;
  const inkMin = fp.min_block_ink_ratio;

  const { configurePluginLocalPlaywright } = require(path.join(VENDOR, 'scripts', 'playwright-runtime.js'));
  configurePluginLocalPlaywright();
  const { chromium } = require(path.join(VENDOR, 'node_modules', 'playwright'));

  let errors = 0;
  let warnings = 0;
  let slidesChecked = 0;
  let detectedSystem = 'none';
  // L10 用。面が取れない deck (混在・0 件) はめくる前提が成り立たないので走らせない。
  let transitionSkipped = false;
  let transitionProbes = 0;
  const report = (code, where, message) => {
    if (measure) return; // 実測だけを見たいときに判定行を混ぜない
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
      // 注入は goto のたびに必要 (ページ遷移で window は捨てられる)。viewport 切替で
      // リロードを挟む変更を入れるなら、その直後にも同じ 1 行が要る。入れ忘れると
      // window.__srgFaces is not a function で落ちる。
      // 落ちるのは意図した設計。素の querySelector へ戻すと、綴りが再び各所へ散り、
      // 片方だけ直された状態が黙って通ってしまう (それが今回直した不具合)。
      await page.evaluate(FACE_SET_DEF);
      const systems = await page.evaluate(() => ({
        engine: document.querySelectorAll('[data-slide],.slider__item').length,
        skeleton: document.querySelectorAll('.srg-slide,[data-slide-skeleton]').length,
        slides: window.__srgFaces().length,
      }));
      if (systems.engine > 0 && systems.skeleton > 0) {
        detectedSystem = 'mixed';
        report('L7', `${path.basename(path.dirname(file))} ${vp.width}x${vp.height}`,
          'engine (slider-*) と skeleton (.srg-*) が同一 deck に混在している');
        transitionSkipped = true;
        await page.close();
        break;
      }
      detectedSystem = systems.engine > 0 ? 'engine' : (systems.skeleton > 0 ? 'skeleton' : 'none');
      const count = systems.slides;
      if (count === 0) {
        report('L0', `${path.basename(path.dirname(file))} ${vp.width}x${vp.height}`,
          'slide 要素が 0 件のためレイアウトを検査できない');
        transitionSkipped = true;
        await page.close();
        break;
      }
      slidesChecked += count;
      for (let i = 0; i < count; i++) {
        // 1 枚だけを表示状態にしてから測る (非表示スライドは矩形が 0 になる)
        await page.evaluate((n) => {
          window.__srgFaces().forEach((el, j) => {
            if (el.matches('[data-slide],.slider__item')) el.classList.toggle('is-active', j === n);
          });
        }, i);
        await page.waitForTimeout(60);
        const r = await page.evaluate(collectSlide, { index: i, contract, registryMap });
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

        const exc = r.kind ? fp.exceptions[r.kind] : null;

        if (measure) {
          const v = r.vertical;
          console.log([
            where,
            `stage_fill=${r.fillRatio.toFixed(3)}`,
            `block_ink=${r.blockInkRatio.toFixed(3)}`,
            `blocks=${r.blockCount}`,
            `block_px=${r.blockArea} ink_px=${r.inkArea} stage_px=${r.stageArea}`,
            `min_font=${r.minFontPx === null ? '-' : r.minFontPx.toFixed(1)}px root=${r.rootFontPx}px`,
            `system=${r.isSkeleton ? 'skeleton' : 'engine'}`,
            `kind=${r.kind || '-'}`,
            `bg_partial=${r.bgPartial}`,
            v ? `outer=${v.outerRatio.toFixed(3)} sym=${v.symmetryDelta.toFixed(3)} sym_px=${v.symmetryDeltaPx}`
              + `${v.proximity ? ` prox=${v.proximity.ratio.toFixed(2)}` : ''}`
              + `${v.mediaSkew ? ` fig_skew=${v.mediaSkew.ratio.toFixed(3)} fig_skew_px=${v.mediaSkew.px}` : ''}` : 'outer=-',
            (() => {
              const h = r.horizontal;
              if (!h) return 'h=-';
              const f = (o) => (o ? `${o.outer.toFixed(3)}/${o.sym.toFixed(3)} (左${o.left} 右${o.right})` : '-');
              return `h_block=${f(h.block)} h_ink=${f(h.ink)}`;
            })(),
          ].join(' '));
          continue;
        }

        // L8-font 書体の下限。充填率より先に見る。書体を縮めれば充填率は
        // いくらでも作れるので、ここを通さずに L8 の合格を認めない。
        if (r.isSkeleton) {
          if (fontMin && r.minFontCanvasPx !== null && r.minFontCanvasPx < fontMin - 0.5) {
            report('L8-font', where, `本文の最小書体が ${r.minFontCanvasPx.toFixed(1)}px (面座標換算) で `
              + `typography.min=${fontMin}px を割っている`
              + `${r.minFontWhere ? ` (「${r.minFontWhere}」)` : ''}。書体の縮小で充填率を作らない`);
          }
        } else if (r.minFontPx !== null) {
          // engine 経路は下限が二重になる。rem 相対の下限 (note_engine) は
          // 書体が root に追従するので、箱ごと縮んだときは比が保たれて黙る。
          // 絶対下限 typography.min を併せて掛け、どちらか一方でも割ったら指摘する。
          if (fontMinRem) {
            const floor = fontMinRem * r.rootFontPx;
            if (r.minFontPx < floor - 0.5) {
              report('L8-font', where, `本文の最小書体が ${r.minFontPx.toFixed(1)}px で `
                + `engine 経路の下限 ${fontMinRem}rem (=${floor.toFixed(1)}px) を割っている`
                + `${r.minFontWhere ? ` (「${r.minFontWhere}」)` : ''}。書体の縮小で充填率を作らない`);
            }
          }
          if (fontMin && r.minFontPx < fontMin - 0.5) {
            report('L8-font', where, `本文の最小書体が ${r.minFontPx.toFixed(1)}px で `
              + `typography.min=${fontMin}px を割っている`
              + `${r.minFontWhere ? ` (「${r.minFontWhere}」)` : ''}。`
              + `rem 相対の下限は箱と一緒に縮むので、絶対値の下限を別に見る`);
          }
        }

        // L8 充填率 (面ごと。deck 平均では判定しない)
        // この面に効いている充填率のレンジ。L9 の外側余白の許容はここから写す。
        const fillLo = exc && typeof exc.min === 'number' ? exc.min : fp.min_stage_fill_ratio;
        const fillHi = exc && typeof exc.max === 'number' ? exc.max : fp.max_stage_fill_ratio;
        let fillReported = false;
        if (r.stageArea > 0) {
          if (exc && exc.exempt) {
            // image-full は定義上 fill = 1.0。面積比の規定が成立しない。
          } else {
            const lo = fillLo;
            const hi = fillHi;
            const applied = exc ? `例外 kind=${r.kind}` : '既定';
            if (r.fillRatio < lo || r.fillRatio > hi) {
              fillReported = true;
              report('L8', where, `充填率 ${(r.fillRatio * 100).toFixed(1)}% が許容 `
                + `${(lo * 100).toFixed(0)}-${(hi * 100).toFixed(0)}% の外 (${applied}, `
                + `target ${(fp.target_stage_fill_ratio * 100).toFixed(0)}%)。`
                + `${r.fillRatio < lo ? '下限割れは面の統合か項目の追加で直す (スロットの伸長では直さない)'
                  : '上限超えは面の分割か項目の削減で直す'}`);
            }
            // 部材の中身の詰まり具合。stage_fill を伸長で稼ぐとここが落ちる。
            if (inkMin && r.blockArea > 0 && r.blockInkRatio < inkMin) {
              report('L8-ink', where, `部材の中身が ${(r.blockInkRatio * 100).toFixed(1)}% しかない `
                + `(下限 ${(inkMin * 100).toFixed(0)}%)。部材を伸ばして充填率を作らず、`
                + '中身を足すか部材を小さくする');
            }
          }
        }

        // L9 縦方向の残余配分。全面画像の面は本文の群が無いので見ない。
        if (r.vertical && !(exc && exc.exempt)) {
          const v = r.vertical;
          // 近接は既定の内容面にだけ課す。低密度が契約で認められている面 (表紙・
          // 章扉・引用) は、離すこと自体が意匠なので群の一体感を要求しない。
          if (!exc && v.proximity && v.proximity.ratio > vp2.max_proximity_gap_ratio) {
            report('L9', where, `群内の間隔が段の高さの ${(v.proximity.ratio * 100).toFixed(0)}% あり `
              + `許容 ${(vp2.max_proximity_gap_ratio * 100).toFixed(0)}% を超える `
              + `(間隔 ${v.proximity.gap}px / 段の高さ ${v.proximity.rowH}px / ${v.proximity.rows} 段)。`
              + '群が割れて見える');
          }
          // 外側余白の許容は充填率のレンジを高さ比へ写したもの (残余 = 1 - 充填)。
          // 契約の既定値は既定レンジを写した値だが、例外 kind の面はその kind の
          // レンジから写す。写さないと、低密度が契約で認められている面 (表紙・章扉・
          // メッセージ) が「余白が多すぎる」で必ず赤くなり、面の側に直しようがない。
          // 列が領域から溢れている面は、余白が「負」になる。これは余白の配分の問題では
          // なく溢れそのもので、L2 / L3 が既に error として出している。負の余白から出した
          // 比率を「非対称」「余白が足りない」と言い直しても、直し方は溢れを直すこと 1 つ
          // しかない。溢れている間は縦の残余の指摘を出さない。
          const columnOverflows = v.topMargin < 0 || v.bottomMargin < 0;
          // 例外 kind は既定レンジと写したレンジの和 (広い方) を採る。例外は要求を緩める
          // ためのものなので、置き換えにすると「低密度が認められた面は低密度でなければ
          // ならない」という逆向きの縛りになる (よく埋まったメッセージ面が赤くなる)。
          const outerLo = exc
            ? Math.min(vp2.min_outer_margin_ratio, Math.max(0, 1 - fillHi))
            : vp2.min_outer_margin_ratio;
          const outerHi = exc
            ? Math.max(vp2.max_outer_margin_ratio, Math.max(0, 1 - fillLo))
            : vp2.max_outer_margin_ratio;
          // 充填率で既に指摘した面は、同じ事実 (内容が少ない / 多い) を高さ比で言い直す
          // だけになる。列が面の幅いっぱいなら残余 = 1 - 充填で連動するので、2 本出しても
          // 直し方は 1 つしかない。密度は L8 に寄せ、L9 は L8 が黙っているとき (列が細い・
          // 縦だけ詰まっている) だけ独立に言う。
          if (!fillReported && !columnOverflows && (v.outerRatio < outerLo || v.outerRatio > outerHi)) {
            report('L9', where, `群の外側余白の合計が高さの ${(v.outerRatio * 100).toFixed(1)}% で `
              + `許容 ${(outerLo * 100).toFixed(0)}-${(outerHi * 100).toFixed(0)}% の外 `
              + `(上 ${v.topMargin}px / 下 ${v.bottomMargin}px / 有効高 ${v.regionH}px / ブロック ${v.blocks} 件)`);
          }
          if (!columnOverflows && v.symmetryDelta > vp2.max_symmetry_delta) {
            report('L9', where, `群の上下余白が非対称 delta=${(v.symmetryDelta * 100).toFixed(1)}% `
              + `(stage 高さ比。許容 ${(vp2.max_symmetry_delta * 100).toFixed(0)}% 以下。`
              + `上 ${v.topMargin}px / 下 ${v.bottomMargin}px / 差 ${v.symmetryDeltaPx}px)`);
          }
          // 図の中身の偏り。列の対称性とは別の事実 (要素は対称に置かれているのに
          // 描画だけ寄っている) なので、同じ面で両方出ても言い直しにはならない。
          if (v.mediaSkew && v.mediaSkew.ratio > vp2.max_symmetry_delta) {
            report('L9', where, `図 (${v.mediaSkew.tag}) の中身が枠の中で上下に偏っている `
              + `delta=${(v.mediaSkew.ratio * 100).toFixed(1)}% `
              + `(許容 ${(vp2.max_symmetry_delta * 100).toFixed(0)}% 以下。`
              + `枠の中の余り 上 ${v.mediaSkew.top}px / 下 ${v.mediaSkew.bottom}px / 差 ${v.mediaSkew.px}px)。`
              + '図の側で上下中央へ寄せる');
          }
        }
      }
      await page.close();
    }

    // L10 めくった後の保持。
    // ここまでの検査は is-active を付け替えて測っているだけで、遷移そのものは
    // 一度も走っていない。実際にめくると onComplete の clearProps が動き、
    // 描画時に付けたインライン custom property が巻き添えで消えることがある
    // (2026-08-14 の実例)。初期表示は正しいので、この形の欠陥は初期表示だけを
    // 見る検査を全部すり抜ける。だから初期表示の検査を置き換えるのではなく足す。
    //
    // 見るのは保持だけで、行数や矩形は測り直さない。消えれば描画時の指定が
    // 効かなくなるので、行数を測らなくてもこの形の欠陥は捕まる。全面の再測定は
    // 実行時間が跳ねる割に、同じ 1 つの原因を面の数だけ言い直すことにしかならない。
    // 経路は 1 本 (viewport は先頭のみ・往路で全面を 1 回ずつ離れ、最後に先頭へ戻る)。
    //
    // めくり方は「キーを押す」。window.Pagination.goTo を呼ぶ書き方にすると通らない。
    // 生成される deck には slider が 2 つ載っていて (render-slide が埋める
    // window.__renderSlide と、asset の pagination.js が作る window.Pagination)、
    // キー操作は前者を動かす。API を直に叩くと後者だけが動いて、実際に壊れた側の
    // onComplete が一度も走らないまま緑になる (この検査を書いたときに実際に起きた。
    // clearProps: 'all' へ戻した deck が PASS した)。利用者と同じ入口から入ること。
    if (!measure && detectedSystem === 'engine' && !transitionSkipped) {
      const page = await browser.newPage({ viewport: viewports[0] });
      await page.goto(`file://${file}`);
      await page.waitForTimeout(300);
      const props = TRANSITION_KEPT_PROPS;
      const setup = await page.evaluate((ps) => {
        const items = Array.from(document.querySelectorAll('[data-slide],.slider__item'));
        const before = [];
        document.querySelectorAll('[style]').forEach((el) => {
          const got = ps.filter((p) => el.style.getPropertyValue(p) !== '');
          if (!got.length) return;
          const id = String(before.length);
          // 遷移後に同じ要素を引き当てるための目印。style を消す欠陥を見るので、
          // 目印は style でなく属性側に置く。
          el.setAttribute('data-srg-probe', id);
          const item = el.closest('[data-slide],.slider__item');
          const vals = {};
          got.forEach((p) => { vals[p] = el.style.getPropertyValue(p); });
          before.push({ id, slide: item ? items.indexOf(item) + 1 : 0, vals });
        });
        return { probes: before.length, total: items.length, before };
      }, props);
      const activeIndex = () => page.evaluate(() => {
        const items = Array.from(document.querySelectorAll('[data-slide],.slider__item'));
        return items.findIndex((el) => el.classList.contains('is-active'));
      });
      const deck = path.basename(path.dirname(file));
      if (setup.probes > 0) {
        transitionProbes = setup.probes;
        await page.click('body', { position: { x: 5, y: 5 } }).catch(() => {});
        let moved = 0;
        for (let n = 1; n < setup.total; n++) {
          await page.keyboard.press('ArrowRight');
          // 固定の待ちだけにすると、遷移中のキーが握り潰された回を取りこぼす。
          for (let t = 0; t < 40 && (await activeIndex()) !== n; t++) await page.waitForTimeout(50);
          await page.waitForTimeout(320); // onComplete (clearProps) が走り終わるまで
          if ((await activeIndex()) === n) moved++;
        }
        await page.keyboard.press('Home');
        for (let t = 0; t < 40 && (await activeIndex()) !== 0; t++) await page.waitForTimeout(50);
        await page.waitForTimeout(320);
        const res = await page.evaluate((rec) => {
          const lost = [];
          rec.forEach((r) => {
            const el = document.querySelector(`[data-srg-probe="${r.id}"]`);
            if (!el) { lost.push({ slide: r.slide, prop: '(要素そのもの)', was: '', now: '' }); return; }
            Object.keys(r.vals).forEach((p) => {
              const now = el.style.getPropertyValue(p);
              if (now !== r.vals[p]) lost.push({ slide: r.slide, prop: p, was: r.vals[p], now });
            });
          });
          return lost;
        }, setup.before);
        if (moved === 0) {
          // 1 面も動かなかったなら、めくった後を見ていない。0 件を保持の証跡にしない。
          report('L10', `${deck} ${viewports[0].width}x${viewports[0].height}`,
            `インライン custom property が ${setup.probes} 件あるのに、キー操作で面が `
            + '一度も切り替わらず、めくった後を確認できない');
          transitionProbes = 0;
        }
        // 同じ 1 つの原因を要素の数だけ並べない。面と property で 1 行にまとめる。
        const seen = new Set();
        res.forEach((x) => {
          const key = `${x.slide} ${x.prop}`;
          if (seen.has(key)) return;
          seen.add(key);
          const n = res.filter((y) => y.slide === x.slide && y.prop === x.prop).length;
          report('L10', `${deck} ${viewports[0].width}x${viewports[0].height} slide${x.slide}`,
            `めくった後に ${x.prop} が失われている (${n} 件。描画時 "${x.was}" -> 遷移後 `
            + `"${x.now}")。遷移の onComplete が作者側のインライン宣言まで消している`
            + ' (gsap の clearProps を対象・プロパティとも絞る)');
        });
      }
      await page.close();
    }
  } finally {
    await browser.close();
  }

  // --measure は判定を出していないので、合否として読める語を出さない (0 件を PASS と
  // 読み違えると、測っただけの結果が検査を通った証跡として使われる)。
  if (measure) {
    console.log(`slide layout contract: system=${detectedSystem} slides_checked=${slidesChecked} `
      + `viewports=${viewports.length} -> MEASURE ONLY (判定していない)`);
    process.exit(0);
  }
  const failed = errors > 0 || (strict && warnings > 0);
  // transition= は「めくった後の保持を何件見たか」。0 のまま通るのは検査していない
  // ことなので、件数を出しておく (engine 経路で 0 なら描画時のインライン宣言が無い)。
  console.log(`slide layout contract: system=${detectedSystem} slides_checked=${slidesChecked} `
    + `transition=${transitionProbes} `
    + `viewports=${viewports.length} errors=${errors} `
    + `warnings=${warnings} -> ${failed ? 'FAIL' : 'PASS'}`);
  process.exit(failed ? 1 : 0);
}

run().catch((err) => {
  console.error(`ERROR [L0] ${err && err.message ? err.message : err}`);
  process.exit(1);
});
