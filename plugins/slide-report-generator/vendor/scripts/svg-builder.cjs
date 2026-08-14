/**
 * svg-builder.js — 決定論 SVG 生成
 *
 * SR-1-02: viewBox は 960×540 系（または図解形状用の正方形）
 * SR-3-05: SVG <text> 最小 13px
 * SR-2-08: fill/stroke は CSS 変数 + フォールバック
 * SR-3-06: SVG <text> 内に Font Awesome unicode 禁止
 *
 * v7.5.0:
 *   - buildMindmap: ラベルを外円の外側にリーダー線で配置、文字切れ解消
 *   - buildCycle: viewBox を横長化、左に description 用キャプション領域、
 *                 各ノード半径を文字数に応じて拡大
 *   - buildVs: 真の Before/After 2カラム比較ビルダーを新規追加
 *              （diagram-vs / diagram-comparison-1 用）
 *
 * v7.6.0 (図解崩れの構造的修正):
 *   - svg-kit.cjs (決定論レイアウトカーネル) に全面依存
 *   - svgText: 文字数スライス廃止 → 実測幅 + 禁則処理つき折返し
 *   - buildCycle: 端点と円弧の半径不一致を解消 (矢印の向き崩れの根治)
 *   - item.color / item.focal / opts.palette を全ビルダーで尊重
 *   - カード高さを内容量から算出 (固定 cardH の廃止)
 *   - buildSnake: 欠落していたコネクタを追加
 *   配色・見た目は既存を維持する (色の追加・変更はしない)
 */
'use strict';

const kit = require('./svg-kit.cjs');

const MIN_FONT = 14; // SR-3-05 実用最小
const VAR_BLUE = kit.VAR_BLUE;
const VAR_PINK = kit.VAR_PINK;
const VAR_AQUA = kit.VAR_AQUA;
const VAR_YELLOW = kit.VAR_YELLOW;
const VAR_VIOLET = kit.VAR_VIOLET;
// 既存と同一の並び (色替えを起こさないため順序を変えない)
const COLOR_PALETTE = [VAR_BLUE, VAR_AQUA, VAR_PINK, VAR_YELLOW, VAR_VIOLET];

/**
 * 図解キャンバスの標準寸法。**viewBox の正本はここ 1 箇所**。
 *
 * なぜ揃えるか: SVG は本文幅へ合わせて必ず縮小表示される。viewBox 幅が図ごとに
 * 違うと図ごとに実効倍率が変わり、`STROKE.primary`(2.5) が或る図では 1.9px、
 * 別の図では 1.3px で描かれる。線幅と文字サイズの階層 (契約 §1.1 / SR-15) は
 * 「同じ倍率で見比べられる」ことが前提なので、倍率が揺れた時点で階層が意味を失う。
 *
 * 幅 960 の根拠 (実測): 変更前の全ビルダーの viewBox 幅を数えると
 * 960 が 7 件で最多 (720=6 / 540=4 / 1200=2 / 1080=1 / 1100=1)。
 * かつ spec-registry SR-1-02「設計基準解像度 1920×1080 の半分 960×540 を
 * viewBox 標準とする」/ SR-5-01 とも一致する。実測の最頻値と規約が同じ値を
 * 指しているので、これを正本にすると座標系の書き換えが最小で済む。
 *
 * 高さを階段にする理由: 高さを内容量で連続可変にすると縦横比が図ごとに変わり、
 * 幅を揃えた意味が消える (縮小率は幅で決まるが、読者が受け取る「密度」は面積で
 * 決まるため)。幅からアスペクト比で導いた 3 段だけを許し、内容量からは
 * 「どの段か」だけを決定論的に選ぶ。値は GRID(4) へ snap する。
 *   sm = snap(w * 3/8)  = 360  横一列・帯 (8:3)
 *   md = snap(w * 9/16) = 540  標準 (16:9 = SR-1-02 の 960×540)
 *   lg = snap(w * 3/4)  = 720  縦積み・環状 (4:3)
 */
/**
 * 半径・余白のように「上限を超えてはいけない」量を GRID(4) へ丸める。
 * kit.snap は最近傍なので上へ丸まることがあり、上限ぎりぎりの導出値に使うと
 * 1〜2px はみ出す (D1)。切り下げ側の丸めはここに一本化する。
 */
const gridFloor = (v) => Math.floor(v / kit.GRID) * kit.GRID;

const CANVAS = {
  w: 960,
  h: {
    sm: kit.snap((960 * 3) / 8),
    md: kit.snap((960 * 9) / 16),
    lg: kit.snap((960 * 3) / 4),
  },
  /**
   * 必要高 needed を満たす最小の標準高。lg でも足りない量は呼出し側が
   * 「載せない」(契約 §2) 側で解決する責務なので、ここでは lg で頭打ちにする。
   */
  height(needed) {
    const steps = [CANVAS.h.sm, CANVAS.h.md, CANVAS.h.lg];
    return steps.find((s) => s >= needed) || CANVAS.h.lg;
  },
};

/**
 * i 番目の要素の色を決める。
 * これまでは COLOR_PALETTE[i % 5] 固定で、item 側の color / focal 指定を
 * 完全に無視していた (「特性や色が反映されない」の原因)。
 */
function colorOf(it, i, opts = {}) {
  if (it && typeof it === 'object') {
    if (it.color) return it.color;
    if (it.fill) return it.fill;
    if (it.focal === true || it.accent === true) return kit.TOKENS.accent;
  }
  const palette = Array.isArray(opts.palette) && opts.palette.length ? opts.palette : COLOR_PALETTE;
  return palette[i % palette.length];
}

/**
 * 入力配列の正規化: null/undefined を除去する。
 * 以前は minCount まで空要素を push して「最低3件」を満たしていたが、これは
 * データが 1 件のときにラベルの無い箱を 2 つ捏造することであり、読者は
 * 「存在しない要素がある」と読んでしまう。足りない件数はそのまま描く。
 */
function normItems(items) {
  return Array.isArray(items) ? items.filter((x) => x != null) : [];
}
/** ラベル抽出（string|object 両対応） */
function getLabel(it) {
  if (it == null) return '';
  if (typeof it === 'string') return it;
  return it.label || it.text || it.name || '';
}

function escapeXml(s) {
  return String(s == null ? '' : s)
    .replace(/&/g, '&amp;')
    .replace(/</g, '&lt;')
    .replace(/>/g, '&gt;')
    .replace(/"/g, '&quot;');
}

/**
 * 矢印マーカー定義 (SR-5-05)
 *
 * 形状の正本は kit.MARKER の 1 箇所だけにする。以前はここが独自に
 * viewBox 10×8 / refX=9 / markerUnits 既定 (strokeWidth) の marker を定義し、
 * svg-kit.arrowMarkers は 8×6 / refX=7 を定義していた。同じレポートの中でも
 * 生成経路によって矢じりの大きさと「先端がどこか」が変わるうえ、
 * kit.ringArcPath / markerOverhangPx の端点補正は refX に依存するため、
 * 形状が二重定義だと補正量が必ずどちらか片方で間違う。
 * 名前 (blue/pink/... と muted/accent/link/soft/ink) は arrowMarkers が
 * そのまま出すので、既存の url(#arrow-blue) 等の参照はすべて解決し続ける。
 */
function defs() {
  return kit.arrowMarkers();
}

/**
 * テキスト wrapping for SVG (SR-5-03..04)
 *
 * v7.6.0: 文字数スライスを廃止。全角/半角の実測幅と禁則処理にもとづく
 * svg-kit.wrapText を使う。maxChars は後方互換のため受け取り続けるが、
 * 内部では「全角 maxChars 文字ぶんの幅」に換算して幅ベースで扱う。
 *
 * @param {number} maxWidth 折返し幅(px)。指定時は maxChars より優先
 * @param {number} maxLines 行数上限。超過分は末尾を省略記号にする
 */
/**
 * 折返し済みの行を「1 行 = 1 個の <text>」で描く。
 *
 * なぜ tspan で積まないか: validate-svg-diagram.py の D1 は <text> の bbox を
 * itertext() の連結長から概算する (契約 §4「D1 の測り方」)。折返しを tspan で
 * 表すと、実際には 2 行に折れて箱へ収まっている文が「1 行ぶんの連結長」として
 * 測られ、右端・左端のカードでは必ず偽の「はみ出し」= error になる。
 * 行を <text> 単位に分けると、測り方 (1 要素 = 1 行) と描き方が一致する。
 * 出力される字形・座標は tspan 版と同一で、見た目は変わらない。
 */
function svgTextLines(x, firstY, lines, lineHeight, attrs) {
  return (lines || [])
    .filter((ln) => ln !== undefined && ln !== null && ln !== '')
    .map((ln, i) =>
      `<text x="${x}" y="${kit.num(Number(firstY) + i * lineHeight)}" text-anchor="${attrs.anchor}" fill="${attrs.fill}" font-size="${attrs.fontSize}" font-weight="${attrs.weight}" font-family="'Noto Sans JP', sans-serif">${escapeXml(ln)}</text>`)
    .join('');
}

function svgText({
  x, y, text, fontSize = MIN_FONT, anchor = 'middle',
  fill = 'var(--fg, #43436c)', weight = 600,
  maxChars = 0, maxWidth = 0, maxLines = 0,
}) {
  if (!text) return '';
  const width = maxWidth > 0 ? maxWidth : (maxChars > 0 ? maxChars * fontSize : 0);
  let lines = [String(text)];
  if (width > 0) {
    // 契約 §3「ラベルは切り詰めない」。日本語は述部が末尾に来るので途中で切ると
    // 否定・条件が落ちて図が本文と逆の主張になる。ellipsis を切って
    // 「入り切らないなら載せない」側へ倒す (切れた文を出すより無い方が安全)。
    const wrapped = kit.wrapText(text, width, fontSize, { maxLines, ellipsis: false });
    if (wrapped.truncated) return '';
    lines = wrapped.lines;
  }
  const dy = Math.round(fontSize * 1.5);
  return svgTextLines(x, y, lines, dy, { anchor, fill, fontSize, weight });
}

/**
 * 箱に収まるようフォントサイズごと自動調整して描画する。
 * 固定 fontSize + 固定カード寸法の組み合わせが「変な位置での改行」と
 * 「はみ出し」を生んでいたため、寸法が決まっている箇所はこちらを使う。
 */
function svgTextFit(text, box, opts = {}) {
  if (!text) return '';
  const fit = kit.fitText(text, box.w, box.h, {
    padX: opts.padX != null ? opts.padX : 12,
    padY: opts.padY != null ? opts.padY : 8,
    minFont: opts.minFont || MIN_FONT,
    maxFont: opts.maxFont || 20,
    maxLines: opts.maxLines || 0,
    singleLineFloor: opts.singleLineFloor || 0,
  });
  // 契約 §3。kit.fitText は minFont でも入らないと最後の手段として末尾に「…」を
  // 付けて返す。切れたラベルは図の主張を反転させうるので、ここで描かない側へ倒す。
  if (fit.truncated) return '';
  const anchor = opts.anchor || 'middle';
  const padX = opts.padX != null ? opts.padX : 12;
  // anchor に応じて基準 x を箱の左端/中央/右端へ寄せる (左寄せ見出しでも収容判定は同じ)
  const ax = anchor === 'start' ? box.x + padX
    : anchor === 'end' ? box.x + box.w - padX
      : box.x + box.w / 2;
  const cy = box.y + box.h / 2;
  const blockH = (fit.lines.length - 1) * fit.lineHeight;
  const firstY = cy - blockH / 2 + fit.fontSize * 0.35;
  return svgTextLines(ax, firstY, fit.lines, fit.lineHeight, {
    anchor,
    fill: opts.fill || '#fff',
    fontSize: fit.fontSize,
    weight: opts.weight != null ? opts.weight : 700,
  });
}

/**
 * 横フロー: 要素 3-7
 */
function buildHorizontalFlow(items, opts = {}) {
  // v7.5.0: ステップカード下に desc キャプションを描画
  const n = Math.min(7, items.length);
  const W = CANVAS.w;
  const margin = 40;
  const gap = 20;
  // 等分割の丸め残りを末尾カードに吸収させる (Σ幅 + Σ隙間 === 有効幅 を厳密に保つ)。
  // Math.floor で割ると必ず数 px 余り、その余りが常に右端の外側へ落ちていた。
  const track = kit.distributeTrack(margin, W - margin * 2, kit.evenWeights(n), gap);
  const cardW = track.length ? track[0].size : 0;
  const itemList = items.slice(0, n);
  const hasDesc = itemList.some((it) => it && typeof it === 'object' && (it.desc || it.description));
  // カード高さを最長ラベルの必要行数から決める (固定 130 の廃止)。
  // 文字量に対して箱が足りないと「変なところで改行」に見えるため、
  // 箱の側を内容へ合わせる。
  const labelW = cardW - 20;
  const neededH = itemList.reduce((mx, it) => {
    const t = typeof it === 'string' ? it : ((it && (it.label || it.text)) || '');
    const lines = kit.wrapText(t, labelW, 18).lines.length;
    return Math.max(mx, 56 + lines * 27);
  }, 110);
  const cardH = kit.snap(Math.min(190, neededH));
  const cy = 40 + cardH / 2;
  // キャプションの最大行数を先に確定してから viewBox 高の段を選ぶ (後付けは D1 error)
  const descLines = hasDesc ? itemList.reduce((mx, it) => {
    const d = (it && typeof it === 'object') ? (it.desc || it.description || '') : '';
    return d ? Math.max(mx, kit.wrapText(d, cardW - 8, 15, { maxLines: 4, ellipsis: false }).lines.length) : mx;
  }, 0) : 0;
  // 必要高 = カード下端 + (キャプション基準線 40 + 行数 × 行送り 22) + 下余白 margin
  const H = CANVAS.height(cy + cardH / 2 + (descLines ? 40 + descLines * 22 : 0) + margin);
  const cards = itemList.map((it, i) => {
    const x = track[i].pos;
    const cw = track[i].size;
    const color = colorOf(it, i, opts);
    const isObj = it && typeof it === 'object';
    const label = typeof it === 'string' ? it : (isObj ? (it.label || it.text || '') : '');
    const num = isObj && it.number ? it.number : (i + 1);
    const textBox = { x, y: cy - cardH / 2 + 50, w: cw, h: cardH - 58 };
    return `<g>
      <rect x="${x}" y="${cy - cardH / 2}" width="${cw}" height="${cardH}" rx="14" ry="14" fill="${color}" opacity="0.92"/>
      <circle cx="${x + 28}" cy="${cy - cardH / 2 + 28}" r="18" fill="#fff" opacity="0.95"/>
      ${svgText({ x: x + 28, y: cy - cardH / 2 + 34, text: String(num), fontSize: 18, fill: color, weight: 800 })}
      ${svgTextFit(label, textBox, { fill: '#fff', weight: 700, maxFont: 20, padX: 10, padY: 2 })}
    </g>`;
  });
  // 説明キャプション
  const captions = hasDesc ? itemList.map((it, i) => {
    const x = track[i].pos;
    const cw = track[i].size;
    const desc = (it && typeof it === 'object') ? (it.desc || it.description || '') : '';
    if (!desc) return '';
    // 実測幅 + 禁則処理つき折返し (旧: 文字数固定スライス + 末尾1文字削り)
    // 4 行に入り切らない説明は契約 §3 に従って切らずに落とす
    const wrapped = kit.wrapText(desc, cw - 8, 15, { maxLines: 4, ellipsis: false });
    if (wrapped.truncated) return '';
    const lines = wrapped.lines;
    // 色は既存の副次テキスト変数へ統一 (--fg-muted は style-builder が出力しない綴り)
    return svgTextLines(x + cw / 2, cy + cardH / 2 + 40, lines, 22, {
      anchor: 'middle', fill: kit.TOKENS.muted, fontSize: 15, weight: 500,
    });
  }).join('\n  ') : '';
  const arrows = [];
  for (let i = 0; i < n - 1; i++) {
    const ax = track[i].pos + track[i].size;
    const ax2 = track[i + 1].pos;
    arrows.push(`<line x1="${ax}" y1="${cy}" x2="${ax2}" y2="${cy}" stroke="${VAR_BLUE}" stroke-width="${kit.STROKE.primary}" marker-end="url(#arrow-blue)"/>`);
  }
  return `<svg viewBox="0 0 ${W} ${H}" role="img" aria-label="${escapeXml(opts.ariaLabel || '横フロー図')}" xmlns="http://www.w3.org/2000/svg">
  ${defs()}
  ${arrows.join('\n  ')}
  ${cards.join('\n  ')}
  ${captions}
</svg>`;
}

/**
 * サイクル: 3-8 要素を円周配置
 */
function buildCycle(items, opts = {}) {
  // v7.5.0: 右にサイクル、左にキャプションカード
  const n = Math.min(8, items.length);
  const R = 200;
  const rNodeMax = 78;
  // 左キャプション（subtext / description / caption から拾う）。
  // viewBox 高を決める前に必要行数を確定させる。高さを先に固定してから文章を
  // 流し込むと、折返しが増えた瞬間にカードが下端を突き抜ける (D1 error)。
  const caption = opts.subtext || opts.description || opts.caption || '';
  const heading = opts.headline || opts.lead || '';
  // 円の左端 = cx - R - rNodeMax = W - 24 - 2*(R + rNodeMax) = 540。
  // キャプションカードは左余白 24 から始まるので、幅は 540 - 24 - 隙間 36 = 480。
  const captionX = 40, captionW = 480;
  const hasCaption = Boolean(caption || heading);
  const headFs = 26;
  const bodyFs = 18;
  const textW = captionW - 48;
  const hLines = heading ? kit.wrapText(heading, textW, headFs).lines : [];
  const bLines = caption ? kit.wrapText(caption, textW, bodyFs).lines : [];
  const headBlockH = hLines.length ? hLines.length * (headFs * 1.4) + 18 : 0;
  const bodyBlockH = bLines.length ? (bLines.length - 1) * (bodyFs * 1.5) + bodyFs : 0;
  const cardTop = 60;
  const cardPadTop = 40; // y(=100) - cardTop
  const cardPadBottom = 28;
  const cardH = cardPadTop + headBlockH + bodyBlockH + cardPadBottom;
  const step = (2 * Math.PI) / n;
  const angles = Array.from({ length: n }, (_, i) => -Math.PI / 2 + step * i);
  // 節点半径と外接矩形は横半径に依存するので、横半径を決める探索の中で引き直す。
  // 節点半径は隣接する節点の中心間距離の 4 割を上限にすると、節点が重ならず弧を
  // 描く余地も必ず残る (n=8 でも成立)。真円では中心間距離が 2R sin(step/2) に
  // なり、旧実装と同じ値を返す。n = 1 は隣接節点が無く距離が定義できないので
  // 上限をそのまま使う (旧実装では sin(step/2)=0 で半径 0 の節点になり、ラベル箱も
  // 0 幅になって文字が省略記号だけに潰れていた)。
  // 描画の実寸はリングの外接矩形ではなく「節点群の外接矩形」で決まる。n が奇数だと
  // 上下・左右の張り出しが揃わない (n=3 なら上は -R-rNode、下は +R sin(30 度)+rNode)。
  // n > 1 では弧が節点間を一周ぶん繋ぐので、描画は節点の外接矩形に加えてリング
  // 全体を含む (n=3 の下端は節点ではなく弧の +R で決まる)。
  const geomFor = (rx) => {
    const px = (a) => rx * Math.cos(a);
    const py = (a) => R * Math.sin(a);
    let minDist = Infinity;
    for (let i = 0; n > 1 && i < n; i++) {
      const j = (i + 1) % n;
      minDist = Math.min(minDist, Math.hypot(px(angles[i]) - px(angles[j]), py(angles[i]) - py(angles[j])));
    }
    const rNode = n > 1 ? Math.min(rNodeMax, Math.round(minDist * 0.4)) : rNodeMax;
    const arcExtX = n > 1 ? rx : 0;
    const arcExtY = n > 1 ? R : 0;
    return {
      rNode,
      ext: {
        minX: Math.min(-arcExtX, ...angles.map((a) => px(a) - rNode)),
        maxX: Math.max(arcExtX, ...angles.map((a) => px(a) + rNode)),
        minY: Math.min(-arcExtY, ...angles.map((a) => py(a) - rNode)),
        maxY: Math.max(arcExtY, ...angles.map((a) => py(a) + rNode)),
      },
    };
  };
  // 16:9 / 16:10 の面に真円を置くと左右が必ず余る (実測で右に 314px 空き、
  // h_ink 0.245)。viewBox を外接矩形ちょうどまで詰めても、図が縦横 1.05:1 である
  // 以上これ以上は埋まらない。キャプションが無いときは節点を楕円上へ配置して、
  // 図の縦横比そのものを面へ寄せる。目標 1.9 は「面の残余 (1440x900 で 1282x540、
  // 1920x1080 で 1724x648) に対し高さ律速のまま充填率が下限 0.48 を超える最小値
  // 1.57」に余裕を見た値。面の比 (2.37 / 2.66) までは広げない (図が平たくなり
  // すぎる)。キャプション有りの側は左のカードが横を埋めるので真円のまま保つ
  // (カード幅 480 が真円前提の cx から逆算されているため、動かすと重なる)。
  // 中心節点の有無は横半径を決める前に要る (下の楕円化を分岐させるため)。
  // 値の解釈自体は描画位置と無関係なので、ここで確定させても図は変わらない。
  const centerSpec = opts.center && typeof opts.center === 'object' ? opts.center
    : (typeof opts.center === 'string' && opts.center ? { label: opts.center } : null);
  const centerLabel = centerSpec ? getLabel(centerSpec) : '';
  const TARGET_ASPECT = 1.9;
  let rx = R;
  // 中心節点があるときは楕円化しない。中心から各節点までの距離が
  // sqrt((RX cos a)^2 + (RY sin a)^2) で方向によって変わるため、「3 つが等しく中心へ
  // 添う」という図の主張が距離の不均等として出てしまう (n=3 の実測: 楕円は
  // RX=434 RY=200 に収束し、上の節点まで 200.0px・左右の節点まで 388.9px と
  // 1.94 倍の開きになる。真円ならどの向きも 200.0px)。中心を持たない
  // 循環図は「順に回る」ことしか言わないので、横へ伸びても意味は壊れない。
  // 充填率はこのぶん落ちるが、それは面の側で解く (fill_policy.note_antipattern)。
  if (!hasCaption && n > 1 && !centerLabel) {
    // 節点半径が横半径に依存し、その節点半径が外接矩形を動かすので閉じた式が
    // 無い。目標比との比率を掛ける反復で十分収束する (実測 6 回で 0.1% 以内)。
    for (let i = 0; i < 6; i++) {
      const g = geomFor(rx);
      const aspect = (g.ext.maxX - g.ext.minX) / (g.ext.maxY - g.ext.minY);
      rx = Math.min(R * 2.6, Math.max(R, rx * (TARGET_ASPECT / aspect)));
    }
    rx = Math.round(rx);
  }
  const RX = rx, RY = R;
  const { rNode, ext } = geomFor(RX);
  // viewBox の余白は左右上下とも 24 で固定する。ここを 8 まで詰めると図の実寸を
  // 変えないまま面積比だけが上がるが、frame-contract の note_antipattern は
  // 「充填率の下限割れは面の統合か項目の追加で直す」と定めており、余白を削って
  // 数値を作るのはその意図に反する。充填率が足りないときは中身を足す側で解く。
  const pad = 24;
  const ringW = (ext.maxX - ext.minX) + 2 * pad;
  const ringH = (ext.maxY - ext.minY) + 2 * pad;
  // キャプションが無い deck では左半分が丸ごと空き、リングだけが右へ寄っていた
  // (実測: viewBox 0 0 960 720 に対し描画 bbox が x=406.8-909.2)。viewBox は
  // 描画を記述するものなので、キャプションを載せないときは左の予約帯も
  // CANVAS の段丸めも畳み、節点群の外接矩形ちょうどにする。こうすると
  // preserveAspectRatio の既定 (xMidYMid meet) が面の中央へ置き、かつ図が
  // 面の高さいっぱいまで拡大される (viewBox が実寸より広いと図だけ縮む)。
  const W = hasCaption ? CANVAS.w : ringW;
  // 高さ: 節点群の実寸と、キャプションカードの下端 (cardTop + cardH + 下余白 40)
  // の大きい方。キャプション無しなら段丸めせず実寸をそのまま使う。
  const H = hasCaption
    ? CANVAS.height(Math.max(ringH, cardTop + cardH + 40))
    : ringH;
  // 円は右端へ寄せる。中心 x = W - (右の張り出し + 余白) で、節点の右端が
  // ちょうど余白ぶんだけ内側に入る。キャプション無しのときはこの式がそのまま
  // 外接矩形の中心を返し、左右・上下の余白が等しくなる。
  // キャプション有りの側は既存の座標をそのまま保つ (キャプション帯の幅 480 は
  // この cx から逆算した値なので、ここを動かすとカードとリングが重なる)。
  const cx = hasCaption ? W - (R + rNodeMax + 24) : W - (ext.maxX + pad);
  const cy = hasCaption ? H / 2 : -ext.minY + pad;
  // 節点に載せる文字の上限は節点半径から引く。固定値だと半径が変わっても文字が
  // 追随しないため、n が増えて節点が縮んだときは箱だけ小さくなり、節点が大きい図
  // では文字だけ小さいまま残る (実測: 旧出荷版と節点半径は同じ r=78 / r=104 なのに、
  // ラベルは旧 29 / 40 に対し現行は 18 / 26 で、1920x1080 の実描画で 55px 対 32px)。
  // 係数は旧の値を当時の半径で割った比の平均。ラベルは 29/78=0.372 と 40/104=0.385
  // の平均で 0.378、副ラベルは 19/78=0.244 と 25/104=0.240 の平均で 0.242。
  // 従来の固定値は下限として残す。maxFont は上限でしかなく、箱に入らなければ
  // svgTextFit が下げるので、上へ外れても文字が溢れることはない。
  const LABEL_FONT_RATIO = 0.378;
  const SUB_FONT_RATIO = 0.242;
  const fontCap = (r, ratio, floor) => Math.max(floor, Math.round(r * ratio));
  const nodes = [];
  const arrows = [];
  // 節点中心 P と、リング円上で角度 delta だけ離れた点 Q の距離は 2R sin(delta/2)。
  // これが rNode に等しくなる delta が「リング円が節点円から抜け出る角度」であり、
  // 弧はこの delta のぶん節点中心から離した位置で始め・終える。
  //   旧実装1: 端点を半径 (R - rNode - 6) の円上に置きながら円弧コマンドには半径 R を
  //            書いていたため SVG 側で半径が補正され、接線方向がずれて矢じりが崩れた。
  //   旧実装2: 半径は揃えたが delta/2 しか離さなかったため、矢じりの先端が節点円の
  //            内側に入り、後から描く円に隠れて矢印そのものが消えていた。
  // 楕円では媒介変数の角度あたりの進み |dP/da| が角度ごとに違うので、px で決まる
  // 量 (節点半径・隙間・矢じりの張り出し) はすべてこの局所速度で角度へ換算する。
  // 真円では速度が R 一定になり、下の 3 つは旧実装と同じ値を返す。
  const speedAt = (a) => Math.hypot(RX * Math.sin(a), RY * Math.cos(a));
  const deltaAt = RX === RY
    ? () => 2 * Math.asin(Math.min(0.999, rNode / (2 * R)))
    : (a) => rNode / speedAt(a);
  // 矢じりは線の終端より先へ張り出す。その長さは marker の形状 (kit.MARKER) と
  // 線幅から一意に決まるので、実 px を kit.markerOverhangPx に委ねる。ここに
  // 数値を直書きすると marker 形状を変えた瞬間に補正だけが古い値のまま残る。
  const overhangAt = (a) => kit.markerOverhangPx(kit.STROKE.primary) / speedAt(a);
  // 節点との視覚的な隙間 11px (矢羽根が円縁に潰されない距離)。真円 R=200 では
  // 旧実装の定数 0.055 rad と一致する。
  const gapAt = (a) => 11 / speedAt(a);
  for (let i = 0; i < n; i++) {
    const a = -Math.PI / 2 + step * i;
    const x = cx + RX * Math.cos(a);
    const y = cy + RY * Math.sin(a);
    const it = items[i] || {};
    const color = colorOf(it, i, opts);
    const label = getLabel(it);
    // 副ラベル。ラベルが「何を指すか」だけを言うのに対し、副ラベルは「読者が何を
    // 書けばよいか」を言う (背景 -> いまの状況)。両方あって初めて図が指示になる。
    const sub = typeof it === 'object' && it ? (it.desc || it.sub || '') : '';
    // 円に内接する概ねの矩形へ自動フィット (円内で文字が溢れない)
    const inner = { x: x - rNode * 0.78, y: y - rNode * 0.72, w: rNode * 1.56, h: rNode * 1.44 };
    // 副ラベルがあるときは内接矩形を上下に割る。上下比 0.56 / 0.44 は、下に置く
    // 副ラベルの方が字数が多く 2 行になりやすいぶんを見込んだ値。
    const labelBox = sub ? { ...inner, h: inner.h * 0.56 } : inner;
    const subBox = { ...inner, y: inner.y + inner.h * 0.56, h: inner.h * 0.44 };
    // 節点は弧より後に描いて端点のわずかな食い込みを隠す。ただし塗りが半透明だと
    // 弧が円内を横切って見えてしまうため、不透明な下敷きを 1 枚敷いてから塗る。
    nodes.push(`<circle cx="${x.toFixed(1)}" cy="${y.toFixed(1)}" r="${rNode}" fill="${kit.TOKENS.paper}"/>
      <circle cx="${x.toFixed(1)}" cy="${y.toFixed(1)}" r="${rNode}" fill="${color}" opacity="0.92"/>
      ${svgTextFit(label, labelBox, { fill: '#fff', weight: 700, maxFont: fontCap(rNode, LABEL_FONT_RATIO, 18), minFont: 13, singleLineFloor: 14, padX: 6, padY: 4 })}${sub ? `
      ${svgTextFit(sub, subBox, { fill: '#fff', weight: 500, maxFont: fontCap(rNode, SUB_FONT_RATIO, 14), minFont: 12, singleLineFloor: 12, padX: 6, padY: 3 })}` : ''}`);
    const a2 = a + step;
    const start = a + deltaAt(a) + gapAt(a);
    const end = a2 - deltaAt(a2) - gapAt(a2) - overhangAt(a2);
    // 1 件だけのサイクルは循環しない。step が 2π になり自分自身へ戻る弧を
    // 描いてしまうため、2 件以上のときだけ矢印を出す。
    if (n > 1 && end > start) {
      const sx = cx + RX * Math.cos(start);
      const sy = cy + RY * Math.sin(start);
      const ex = cx + RX * Math.cos(end);
      const ey = cy + RY * Math.sin(end);
      const largeArc = end - start > Math.PI ? 1 : 0;
      // 両端は同じ楕円上にあるので、半径に RX RY を書けばその楕円弧そのものになる。
      arrows.push(`<path d="M${sx.toFixed(2)},${sy.toFixed(2)} A ${RX} ${RY} 0 ${largeArc} 1 ${ex.toFixed(2)},${ey.toFixed(2)}" fill="none" stroke="${VAR_BLUE}" stroke-width="${kit.STROKE.primary}" marker-end="url(#arrow-blue)"/>`);
    }
  }
  // 中心節点。structure.schema.json の content_slide-circle は center を必須に
  // していながら、ここが受け取らないため描画に出ていなかった。schema が受け取ると
  // 宣言した値は描くか、宣言をやめるかのどちらかしかない。
  // 半径は「中心から最も近い節点中心までの距離 - 節点半径 - 隙間 18」。この式は
  // 節点と必ず離れる最大値を返すので、n や楕円率が変わっても重ならない。
  // 中心は節点群の外接矩形の内側に必ず収まるため viewBox は変わらない
  // (= center を持たない既存 deck と、持つ deck の図の寸法が同じままになる)。
  let centerBlock = '';
  if (centerLabel && n > 0) {
    const minNodeDist = Math.min(...angles.map((a) => Math.hypot(RX * Math.cos(a), RY * Math.sin(a))));
    const rCenter = Math.round(minNodeDist - rNode - 18);
    // 半径が 40 を割ると中心円に 12px の文字が入らない。入らない箱を描くと
    // svgTextFit が契約 §3 で文字を落とし、意味の無い丸だけが残るので描かない。
    if (rCenter >= 40) {
      const cSub = centerSpec.desc || centerSpec.sub || '';
      const cInner = { x: cx - rCenter * 0.78, y: cy - rCenter * 0.72, w: rCenter * 1.56, h: rCenter * 1.44 };
      const cLabelBox = cSub ? { ...cInner, h: cInner.h * 0.56 } : cInner;
      const cSubBox = { ...cInner, y: cInner.y + cInner.h * 0.56, h: cInner.h * 0.44 };
      // 中心は「衛星の色を束ねる場所」なので、節点の配色を持たせず紙色 + 輪郭に
      // する。色を付けると 4 つ目の要素に見え、サイクルの数え方が狂う。
      centerBlock = `<circle cx="${cx.toFixed(1)}" cy="${cy.toFixed(1)}" r="${rCenter}" fill="${kit.TOKENS.paper}"/>
      <circle cx="${cx.toFixed(1)}" cy="${cy.toFixed(1)}" r="${rCenter}" fill="none" stroke="${kit.TOKENS.muted}" stroke-width="${kit.STROKE.primary}"/>
      ${svgTextFit(centerLabel, cLabelBox, { fill: kit.TOKENS.ink, weight: 700, maxFont: fontCap(rCenter, LABEL_FONT_RATIO, 26), minFont: 16, singleLineFloor: 18, padX: 8, padY: 6 })}
      ${cSub ? svgTextFit(cSub, cSubBox, { fill: kit.TOKENS.muted, weight: 400, maxFont: fontCap(rCenter, SUB_FONT_RATIO, 16), minFont: 12, singleLineFloor: 12, padX: 8, padY: 4 }) : ''}`;
    }
  }
  let captionBlock = '';
  if (heading || caption) {
    const y = 100;
    const bodyStartY = y + headBlockH;
    captionBlock = `<g>
      <rect x="${captionX - 16}" y="${cardTop}" width="${captionW}" height="${cardH}" rx="14" fill="#FFFFFF" stroke="${VAR_BLUE}" stroke-width="${kit.STROKE.node}"/>
      <rect x="${captionX - 16}" y="${cardTop}" width="6" height="${cardH}" fill="${VAR_BLUE}"/>
      ${heading ? svgTextLines(captionX, y, hLines, headFs * 1.4, { anchor: 'start', fill: '#43436c', fontSize: headFs, weight: 800 }) : ''}
      ${caption ? svgTextLines(captionX, bodyStartY, bLines, bodyFs * 1.5, { anchor: 'start', fill: '#54546d', fontSize: bodyFs, weight: 500 }) : ''}
    </g>`;
  }
  return `<svg viewBox="0 0 ${W} ${H}" class="cycle-svg" role="img" aria-label="${escapeXml(opts.ariaLabel || 'サイクル図')}" xmlns="http://www.w3.org/2000/svg">
  ${defs()}
  ${captionBlock}
  ${arrows.join('\n  ')}${centerBlock ? `
  ${centerBlock}` : ''}
  ${nodes.join('\n  ')}
</svg>`;
}

/**
 * ピラミッド: 3-5 層
 */
function buildPyramid(items, opts = {}) {
  const n = Math.min(5, items.length);
  const W = CANVAS.w;
  // 1 層の最小高 = 日本語 2 行 (MIN_FONT × LINE_HEIGHT_RATIO ≒ 21) + 上下パディング
  // ≒ 88px。必要高 = 上下余白 40*2 + n * 88 から段を選ぶ。
  const H = CANVAS.height(80 + n * 88);
  const top = 40, bottom = H - 40;
  const layerH = (bottom - top) / n;
  // 底辺は有効幅 (W - 左右余白 160*2) いっぱい、頂点はその 1/4 に細める
  const wBase = W - 320;
  const widthAt = (i) => wBase / 4 + ((i + 1) / n) * (wBase * 3 / 4);
  const layers = items.slice(0, n).map((it, i) => {
    const y = top + i * layerH;
    const w = widthAt(i);
    const x = (W - w) / 2;
    // 下段ほど濃い既存配色を保つため、パレット添字だけ逆順にして colorOf へ渡す
    const color = colorOf(it, n - 1 - i, opts);
    const label = typeof it === 'string' ? it : it.label || it.text || '';
    const fontSize = Math.max(MIN_FONT, Math.min(22, Math.floor(layerH / 3)));
    return `<g>
      <rect x="${x.toFixed(1)}" y="${y.toFixed(1)}" width="${w.toFixed(1)}" height="${(layerH - 6).toFixed(1)}" rx="6" fill="${color}" opacity="0.92"/>
      ${svgTextFit(label, { x, y, w, h: layerH - 6 }, { fill: '#fff', weight: 700, maxFont: fontSize, padX: 24 })}
    </g>`;
  });
  return `<svg viewBox="0 0 ${W} ${H}" class="pyramid-svg" role="img" aria-label="${escapeXml(opts.ariaLabel || 'ピラミッド図')}" xmlns="http://www.w3.org/2000/svg">
  ${defs()}
  ${layers.join('\n  ')}
</svg>`;
}

/**
 * 階層: 3-4 階層（縦ツリー風）
 */
function buildHierarchy(items, opts = {}) {
  const n = Math.min(4, items.length);
  const W = CANVAS.w;
  // 1 階層の最小高 = 見出し 1 行 (20px) + 上下パディング + 階層間の空き 30px ≒ 110px
  const H = CANVAS.height(n * 110 + 40);
  const layerH = H / n;
  // 最上段は有効幅 (W - 左右余白 160*2) いっぱい、下の階層ほど 80px ずつ狭める
  const wTop = W - 320;
  const layers = items.slice(0, n).map((it, i) => {
    const y = i * layerH + 20;
    const w = wTop - i * 80;
    const x = (W - w) / 2;
    const color = colorOf(it, i, opts);
    const label = typeof it === 'string' ? it : it.label || it.text || '';
    const fontSize = Math.max(MIN_FONT, 20);
    return `<g>
      <rect x="${x}" y="${y}" width="${w}" height="${layerH - 30}" rx="10" fill="${color}" opacity="0.9"/>
      ${svgTextFit(label, { x, y, w, h: layerH - 30 }, { fill: '#fff', weight: 700, maxFont: fontSize, padX: 24 })}
    </g>`;
  });
  return `<svg viewBox="0 0 ${W} ${H}" role="img" aria-label="${escapeXml(opts.ariaLabel || '階層図')}" xmlns="http://www.w3.org/2000/svg">
  ${defs()}
  ${layers.join('\n  ')}
</svg>`;
}

/** 棒グラフ */
function buildBarChart(data, opts = {}) {
  const W = CANVAS.w, H = CANVAS.h.md;
  const padL = 80, padB = 60, padT = 30, padR = 30;
  const innerW = W - padL - padR, innerH = H - padT - padB;
  const list = data.slice(0, CAPACITY.buildBarChart);
  const max = Math.max(...list.map((d) => d.value)) || 1;
  const bw = innerW / list.length * 0.6;
  const gap = innerW / list.length;
  const bars = list.map((d, i) => {
    const h = (d.value / max) * innerH;
    const x = padL + i * gap + (gap - bw) / 2;
    const y = padT + innerH - h;
    const color = COLOR_PALETTE[i % COLOR_PALETTE.length];
    return `<g>
      <rect x="${x.toFixed(1)}" y="${y.toFixed(1)}" width="${bw.toFixed(1)}" height="${h.toFixed(1)}" rx="4" fill="${color}"/>
      ${svgText({ x: x + bw / 2, y: y - 8, text: String(d.value), fontSize: MIN_FONT, fill: 'var(--fg, #43436c)', weight: 700 })}
      ${svgText({ x: x + bw / 2, y: padT + innerH + 24, text: d.label, fontSize: MIN_FONT, fill: 'var(--fg, #43436c)' })}
    </g>`;
  });
  return `<svg viewBox="0 0 ${W} ${H}" role="img" aria-label="${escapeXml(opts.ariaLabel || '棒グラフ')}" xmlns="http://www.w3.org/2000/svg">
  ${defs()}
  <line x1="${padL}" y1="${padT + innerH}" x2="${padL + innerW}" y2="${padT + innerH}" stroke="${VAR_BLUE}" stroke-width="${kit.STROKE.axis}"/>
  <line x1="${padL}" y1="${padT}" x2="${padL}" y2="${padT + innerH}" stroke="${VAR_BLUE}" stroke-width="${kit.STROKE.axis}"/>
  ${bars.join('\n  ')}
</svg>`;
}

/** 円グラフ */
function buildPieChart(data, opts = {}) {
  const W = CANVAS.w, H = CANVAS.h.md;
  const cx = W / 2, cy = H / 2;
  // 半径はラベル環 (r + LABEL_RING 30) と文字高 (MIN_FONT の行送り ≒ 21) が
  // 上下に収まる範囲: r + 30 + 21 <= H/2。CANVAS の段が変わっても追随するよう
  // 直書きせず H から導き、上限を割らないよう切り下げで 4px グリッドへ寄せる。
  const r = gridFloor(H / 2 - 30 - Math.round(MIN_FONT * 1.5));
  const list = data.slice(0, CAPACITY.buildPieChart);
  const total = list.reduce((s, d) => s + d.value, 0) || 1;
  let acc = -Math.PI / 2;
  const slices = list.map((d, i) => {
    const a1 = acc;
    const a2 = acc + (d.value / total) * Math.PI * 2;
    acc = a2;
    const x1 = cx + r * Math.cos(a1), y1 = cy + r * Math.sin(a1);
    const x2 = cx + r * Math.cos(a2), y2 = cy + r * Math.sin(a2);
    const large = a2 - a1 > Math.PI ? 1 : 0;
    const color = COLOR_PALETTE[i % COLOR_PALETTE.length];
    const am = (a1 + a2) / 2;
    const lx = cx + (r + 30) * Math.cos(am);
    const ly = cy + (r + 30) * Math.sin(am);
    const pct = Math.round((d.value / total) * 100);
    return `<g>
      <path d="M${cx},${cy} L${x1.toFixed(1)},${y1.toFixed(1)} A${r},${r} 0 ${large} 1 ${x2.toFixed(1)},${y2.toFixed(1)} z" fill="${color}" opacity="0.92"/>
      ${svgText({ x: lx, y: ly + 5, text: `${d.label} ${pct}%`, fontSize: MIN_FONT, fill: 'var(--fg, #43436c)', weight: 700 })}
    </g>`;
  });
  return `<svg viewBox="0 0 ${W} ${H}" role="img" aria-label="${escapeXml(opts.ariaLabel || '円グラフ')}" xmlns="http://www.w3.org/2000/svg">
  ${slices.join('\n  ')}
</svg>`;
}

/* ============================================================
 * 追加ビルダー（v7.1: 73 slideType 拡張用）
 * すべて決定論・vw/CSS変数準拠・SR-3-05 (min 13px) 厳守。
 * ============================================================ */

/** 縦フロー（ステップ縦並び） */
function buildVerticalFlow(items, opts = {}) {
  const n = Math.min(8, items.length);
  const W = CANVAS.w;
  const gap = 18, marginY = 30;
  // 縦積みのカードは幅いっぱいにすると 1 行が長すぎて視線が横に流れる。
  // 幅の 60% を本文段とし、左右は等分の余白にする (viewBox 幅は統一のまま)。
  const cardW = kit.snap(W * 0.6);
  const marginX = (W - cardW) / 2;
  const list = items.slice(0, n);
  // カード高さを内容量から決める (固定 64 では2行以上のラベルが溢れていた)
  const rawCardH = kit.snap(list.reduce((mx, it) => {
    const t = typeof it === 'string' ? it : ((it && (it.label || it.text)) || '');
    const lines = kit.wrapText(t, cardW - 32, 18).lines.length;
    return Math.max(mx, 24 + lines * 27);
  }, 64));
  // 最大の標準高でも収まらない量は、カード高の方を詰めて収める (viewBox は階段のまま)。
  // 上限 = (lg - 上下余白 - 隙間の合計) / n
  const cardCap = kit.snap(Math.max(48, (CANVAS.h.lg - marginY * 2 - (n - 1) * gap) / n));
  const cardH = Math.min(rawCardH, cardCap);
  const H = CANVAS.height(marginY * 2 + n * cardH + (n - 1) * gap);
  const cards = list.map((it, i) => {
    const y = marginY + i * (cardH + gap);
    const c = colorOf(it, i, opts);
    const label = typeof it === 'string' ? it : it.label || it.text || '';
    return `<g><rect x="${marginX}" y="${y}" width="${cardW}" height="${cardH}" rx="12" fill="${c}" opacity="0.92"/>
      ${svgTextFit(label, { x: marginX, y, w: cardW, h: cardH }, { fill: '#fff', weight: 700, maxFont: 18, padX: 16 })}</g>`;
  });
  // 矢印は「順序・因果がある」という主張。素材にその根拠が無い場合 (本文の段落を
  // ただ並べた導出図など) は connector:false で消す。無い含意を図が足さないため。
  const arrows = [];
  for (let i = 0; opts.connector !== false && i < n - 1; i++) {
    const y1 = marginY + (i + 1) * cardH + i * gap;
    const y2 = y1 + gap;
    arrows.push(`<line x1="${W / 2}" y1="${y1}" x2="${W / 2}" y2="${y2}" stroke="${VAR_BLUE}" stroke-width="${kit.STROKE.primary}" marker-end="url(#arrow-blue)"/>`);
  }
  return `<svg viewBox="0 0 ${W} ${H}" role="img" aria-label="${escapeXml(opts.ariaLabel || '縦フロー図')}" xmlns="http://www.w3.org/2000/svg">
  ${defs()}
  ${arrows.join('\n  ')}
  ${cards.join('\n  ')}
</svg>`;
}

/** 同心円（concentric） */
function buildConcentric(rings, opts = {}) {
  const n = Math.min(5, rings.length);
  const W = CANVAS.w, H = CANVAS.h.md, cx = W / 2, cy = H / 2;
  // 最外円は上下が律速。maxR = H/2 - 上下余白 40 = 276 → 4px 寄せで 276
  const maxR = kit.snap(H / 2 - 40);
  const items = rings.slice(0, n).map((r, i) => {
    const radius = maxR * (1 - i / n);
    const c = colorOf(r, i, opts);
    const label = typeof r === 'string' ? r : r.label || r.text || '';
    // ラベル帯は円の上端寄り。弦の長さに収まる幅だけを使って折返す
    const bandW = radius * 1.5;
    // 帯の高さは「隣の円の上端まで」= maxR/n。1 行 (MIN_FONT×1.5 = 21) しか置けない
    // 高さだと内側の小さい円でラベルが幅に入らず落ちるので、2 行ぶん
    // (21×2 + 上下パディング 2×2 = 46) を許すこの高さまで広げる。
    const bandH = kit.snap(maxR / n);
    return `<circle cx="${cx}" cy="${cy}" r="${radius.toFixed(1)}" fill="${c}" opacity="${(0.25 + 0.15 * i).toFixed(2)}" stroke="${c}" stroke-width="${kit.STROKE.secondary}"/>
      ${svgTextFit(label, { x: cx - bandW / 2, y: cy - radius + 6, w: bandW, h: bandH }, { fill: kit.TOKENS.ink, weight: 700, maxFont: 16, padX: 4, padY: 2 })}`;
  });
  return `<svg viewBox="0 0 ${W} ${H}" role="img" aria-label="${escapeXml(opts.ariaLabel || '同心円図')}" xmlns="http://www.w3.org/2000/svg">
  ${items.join('\n  ')}
</svg>`;
}

/** Venn図 (2 or 3 circles) */
function buildVenn(circles, opts = {}) {
  const n = Math.min(3, circles.length);
  const W = CANVAS.w, H = CANVAS.h.md, cx = W / 2, cy = H / 2;
  // 3 円配置の縦方向が律速。上円中心 (cy - 90) の上にラベル帯 46 + 隙間 6 と
  // 上端余白 8 が要るので r <= cy - 90 - 52 - 8。H の段に追随させる。
  const r = gridFloor(cy - 90 - 52 - 8);
  let positions;
  if (n === 2) positions = [{ x: cx - 100, y: cy }, { x: cx + 100, y: cy }];
  else positions = [{ x: cx, y: cy - 90 }, { x: cx - 100, y: cy + 76 }, { x: cx + 100, y: cy + 76 }];
  // ラベルは円の外側へ逃がす。3円のときは下2つを円の下へ置き、上円のラベルと衝突させない
  const labelBox = (p, i) => (n === 3 && i > 0)
    ? { x: p.x - r, y: p.y + r + 6, w: r * 2, h: 46 }
    : { x: p.x - r, y: p.y - r - 52, w: r * 2, h: 46 };
  const parts = positions.slice(0, n).map((p, i) => {
    const c = colorOf(circles[i], i, opts);
    const it = circles[i];
    const label = typeof it === 'string' ? it : it.label || it.text || '';
    return `<circle cx="${p.x}" cy="${p.y}" r="${r}" fill="${c}" opacity="0.45"/>
      ${svgTextFit(label, labelBox(p, i), { fill: kit.TOKENS.ink, weight: 700, maxFont: 16, padX: 4 })}`;
  });
  // 以前は viewBox 原点を負にしてラベル帯ぶんの余白を作っていたが、原点が図ごとに
  // 違うと他の図と座標系を突き合わせられない。半径の方をラベル帯込みで解いてある
  // ので、原点 0,0 の標準キャンバスに素直に収まる。
  return `<svg viewBox="0 0 ${W} ${H}" role="img" aria-label="${escapeXml(opts.ariaLabel || 'ベン図')}" xmlns="http://www.w3.org/2000/svg">
  ${parts.join('\n  ')}
</svg>`;
}

/**
 * マトリクス 2x2
 *
 * v7.7.0: 象限ごとに系列色でベタ塗りして白抜き文字を載せる文法をやめた。
 * 4 象限すべてが等しく強い面になるため「どこから読むか」が読者任せになり、
 * さらに白抜き文字は系列色 (SERIES) の明度がまちまちなので象限によって
 * コントラストが変わっていた。kit.NODE_STYLES の文法 (白地 + 罫 + 焦点 1 点) へ
 * 寄せ、文字は常に TOKENS.ink にする (白地 #FFFFFF ↔ ink #43436C で AA 以上)。
 */
function buildMatrix(quadrants, opts = {}) {
  const W = CANVAS.w, H = CANVAS.h.md;
  const cells = [];
  const cw = W / 2, ch = H / 2;
  const labels = quadrants.slice(0, CAPACITY.buildMatrix);
  // 焦点は 1 つだけ (契約 §1.2 / D7)。明示指定が無ければ「両軸とも高い」右上 (i=1)。
  // 2x2 は i%2 が列・floor(i/2) が行なので i=1 が右上になる。
  let focalIdx = labels.findIndex((it) => it && typeof it === 'object' && (it.focal || it.accent));
  if (focalIdx < 0) focalIdx = 1;
  for (let i = 0; i < 4; i++) {
    const x = (i % 2) * cw, y = Math.floor(i / 2) * ch;
    const it = labels[i] || '';
    const st = i === focalIdx ? kit.NODE_STYLES.focal : kit.NODE_STYLES.plain;
    const label = typeof it === 'string' ? it : it.label || it.text || '';
    const box = { x: x + 4, y: y + 4, w: cw - 8, h: ch - 8 };
    cells.push(`${kit.nodeRect(box, st, { radius: 10 })}
      ${svgTextFit(label, box, { fill: st.text || kit.TOKENS.ink, weight: 700, maxFont: 18, padX: 20 })}`);
  }
  return `<svg viewBox="0 0 ${W} ${H}" role="img" aria-label="${escapeXml(opts.ariaLabel || 'マトリクス図')}" xmlns="http://www.w3.org/2000/svg">
  ${cells.join('\n  ')}
</svg>`;
}

/**
 * ファネル
 *
 * v7.7.0: 段ごとの系列色ベタ塗り + 白抜き文字 (opacity 0.9) をやめる。
 * ファネルが読ませたいのは「段を下るほど絞られる」という**幅の変化**であって
 * 段の色ではない。全段が濃い面だと幅の差が色の差に埋もれ、さらに白抜き文字の
 * コントラストが段ごとに変わっていた。kit.NODE_STYLES の文法へ寄せ、
 * 焦点は「最終到達段」1 つだけに置く (契約 §1.2 / D7)。
 */
function buildFunnel(items, opts = {}) {
  const n = Math.min(6, items.length);
  const W = CANVAS.w;
  // 1 段の最小高 = 日本語 2 行 (16px の行送り 24) + 上下パディング ≒ 80px
  const H = CANVAS.height(60 + n * 80);
  const top = 30, bot = H - 30;
  const lh = (bot - top) / n;
  // 上辺は有効幅 (W - 左右余白 160*2)、下辺はその 1/3 まで絞る
  const wTop = W - 320, wBot = Math.round((W - 320) / 3);
  const layers = [];
  for (let i = 0; i < n; i++) {
    const t = i / n, t2 = (i + 1) / n;
    const w1 = wTop - (wTop - wBot) * t;
    const w2 = wTop - (wTop - wBot) * t2;
    const y1 = top + i * lh, y2 = y1 + lh - 4;
    const x1 = (W - w1) / 2, x2 = (W - w2) / 2;
    const it = items[i];
    const label = getLabel(it);
    const st = i === n - 1 ? kit.NODE_STYLES.focal : kit.NODE_STYLES.plain;
    const dash = st.dash ? ` stroke-dasharray="${st.dash}"` : '';
    // 台形の最小辺 (下辺 w2) を折返し幅にする。上辺基準だと下端で文字がはみ出す
    layers.push(`<polygon points="${x1.toFixed(1)},${y1.toFixed(1)} ${(x1 + w1).toFixed(1)},${y1.toFixed(1)} ${(x2 + w2).toFixed(1)},${y2.toFixed(1)} ${x2.toFixed(1)},${y2.toFixed(1)}" fill="${st.fill}" stroke="${st.stroke}" stroke-width="${st.strokeWidth}"${dash}/>
      ${svgTextFit(label, { x: (W - w2) / 2, y: y1, w: w2, h: lh - 4 }, { fill: st.text || kit.TOKENS.ink, weight: 700, maxFont: 16, padX: 16 })}`);
  }
  return `<svg viewBox="0 0 ${W} ${H}" role="img" aria-label="${escapeXml(opts.ariaLabel || 'ファネル図')}" xmlns="http://www.w3.org/2000/svg">
  ${layers.join('\n  ')}
</svg>`;
}

/** シェブロン (右向き矢印連結) */
function buildChevron(items, opts = {}) {
  const n = Math.min(7, items.length);
  const W = CANVAS.w, H = CANVAS.h.sm, M = 20;
  // 帯そのものの高さは従来どおり 220px。標準高 (sm) の中央へ置く
  const bandH = 220;
  const bandTop = (H - bandH) / 2, bandBot = bandTop + bandH, bandMid = H / 2;
  const segW = (W - M * 2) / n;
  const arrow = 30;
  const segs = [];
  for (let i = 0; i < n; i++) {
    const x = M + i * segW;
    const it = items[i];
    const c = colorOf(it, i, opts);
    const label = getLabel(it);
    const x2 = x + segW - 4;
    const points = [
      `${x},${bandTop}`,
      `${x2 - arrow},${bandTop}`,
      `${x2},${bandMid}`,
      `${x2 - arrow},${bandBot}`,
      `${x},${bandBot}`,
      `${x + arrow},${bandMid}`,
    ].join(' ');
    // 折返し幅は矢羽根 (arrow) を除いた矩形部分だけ。頂点側へ文字が乗るのを防ぐ
    segs.push(`<polygon points="${points}" fill="${c}" opacity="0.92"/>
      ${svgTextFit(label, { x: x + arrow, y: bandTop, w: segW - 4 - arrow * 2, h: bandH }, { fill: '#fff', weight: 700, maxFont: 16, padX: 6 })}`);
  }
  return `<svg viewBox="0 0 ${W} ${H}" role="img" aria-label="${escapeXml(opts.ariaLabel || 'シェブロン図')}" xmlns="http://www.w3.org/2000/svg">
  ${segs.join('\n  ')}
</svg>`;
}

/** スネーク（折り返しフロー） */
function buildSnake(items, opts = {}) {
  items = normItems(items);
  const n = Math.min(8, items.length);
  const W = CANVAS.w;
  const cols = Math.min(4, Math.ceil(n / 2));
  const rows = Math.ceil(n / cols);
  // 1 行の最小高 = 箱 (日本語 2 行 + パディング ≒ 100) + 行間の折返し線 40
  const H = CANVAS.height(40 + rows * 140);
  const cw = (W - 60) / cols, ch = (H - 40) / rows;
  const boxW = cw - 30, boxH = ch - 20;
  const boxes = [];
  const cells = [];
  for (let i = 0; i < n; i++) {
    const r = Math.floor(i / cols);
    const c0 = i % cols;
    const col = r % 2 === 0 ? c0 : cols - 1 - c0;
    const x = 30 + col * cw + 15;
    const y = 20 + r * ch + 10;
    const it = items[i];
    const color = colorOf(it, i, opts);
    const label = getLabel(it);
    cells.push({ x, y, row: r });
    boxes.push(`<rect x="${x}" y="${y}" width="${boxW}" height="${boxH}" rx="10" fill="${color}" opacity="0.9"/>
      ${svgTextFit(label, { x, y, w: boxW, h: boxH }, { fill: '#fff', weight: 700, maxFont: 16, padX: 12 })}`);
  }
  // コネクタ: 同一行は水平 (行の向きに従う)、行が変わるときは折返し辺で縦に落とす
  const links = [];
  for (let i = 0; i < n - 1; i++) {
    const a = cells[i], b = cells[i + 1];
    const stroke = kit.TOKENS.muted;
    if (a.row === b.row) {
      const rightward = b.x > a.x;
      const x1 = rightward ? a.x + boxW : a.x;
      const x2 = rightward ? b.x : b.x + boxW;
      const cyLine = a.y + boxH / 2;
      links.push(`<line x1="${x1}" y1="${cyLine}" x2="${x2}" y2="${cyLine}" stroke="${stroke}" stroke-width="${kit.STROKE.secondary}" marker-end="url(#arrow-muted)"/>`);
    } else {
      // 折返しは同じ列の上下を結ぶ直交線 (斜め線を作らない)
      const cxLine = a.x + boxW / 2;
      links.push(`<line x1="${cxLine}" y1="${a.y + boxH}" x2="${cxLine}" y2="${b.y}" stroke="${stroke}" stroke-width="${kit.STROKE.secondary}" marker-end="url(#arrow-muted)"/>`);
    }
  }
  return `<svg viewBox="0 0 ${W} ${H}" role="img" aria-label="${escapeXml(opts.ariaLabel || 'スネークフロー図')}" xmlns="http://www.w3.org/2000/svg">
  ${defs()}
  ${links.join('\n  ')}
  ${boxes.join('\n  ')}
</svg>`;
}

/** スロープグラフ (左右2点比較) */
function buildSlope(left, right, opts = {}) {
  // 左右の端に日本語ラベル (MIN_FONT × 8 字 = 112) + 隙間 8 + 端余白 8 が要るので
  // padX = 128。上下は端点マーカー (r=6) とラベル帯 (32) の半分ぶんで 50。
  const W = CANVAS.w, H = CANVAS.h.md, padX = 128, padY = 50;
  const items = (left || []).slice(0, CAPACITY.buildSlope).map((l, i) => ({
    label: l.label || (typeof l === 'string' ? l : ''),
    leftV: typeof l === 'object' ? l.value : l,
    rightV: right && right[i] ? (typeof right[i] === 'object' ? right[i].value : right[i]) : 0,
  }));
  const all = items.flatMap((d) => [Number(d.leftV) || 0, Number(d.rightV) || 0]);
  const max = Math.max(...all, 1);
  const lines = items.map((d, i) => {
    const c = colorOf(d, i, opts);
    const y1 = padY + (1 - (Number(d.leftV) || 0) / max) * (H - padY * 2);
    const y2 = padY + (1 - (Number(d.rightV) || 0) / max) * (H - padY * 2);
    return `<line x1="${padX}" y1="${y1.toFixed(1)}" x2="${W - padX}" y2="${y2.toFixed(1)}" stroke="${c}" stroke-width="${kit.STROKE.primary}"/>
      <circle cx="${padX}" cy="${y1.toFixed(1)}" r="6" fill="${c}"/>
      <circle cx="${W - padX}" cy="${y2.toFixed(1)}" r="6" fill="${c}"/>
      ${/* ラベル箱は padX の設計どおり左余白 8 から線の手前 (padX - LABEL_GAP 8) まで。
            有効幅 = 128 - 8 - 8 = 112 = MIN_FONT(14) × 8 字。内側パディングを足すと
            この 112 を割り込んで 8 字が入らなくなるため padX は 0 にする */''}
      ${svgTextFit(d.label, { x: 8, y: Math.max(0, Math.min(H - 32, y1 - 16)), w: padX - 16, h: 32 }, { fill: kit.TOKENS.ink, weight: 600, maxFont: 14, anchor: 'end', padX: 0, padY: 2 })}`;
  });
  return `<svg viewBox="0 0 ${W} ${H}" role="img" aria-label="${escapeXml(opts.ariaLabel || 'スロープグラフ')}" xmlns="http://www.w3.org/2000/svg">
  ${lines.join('\n  ')}
</svg>`;
}

/** バタフライチャート (左右ミラー水平棒) */
function buildButterfly(left, right, opts = {}) {
  const items = (left || []).slice(0, CAPACITY.buildButterfly).map((l, i) => ({
    label: l.label || (typeof l === 'string' ? l : ''),
    l: Number(typeof l === 'object' ? l.value : l) || 0,
    r: Number((right && right[i]) ? (typeof right[i] === 'object' ? right[i].value : right[i]) : 0) || 0,
  }));
  const W = CANVAS.w;
  const bh = 28, gap = 28;
  // 必要高 = 上余白 30 + 件数 × (棒 + 隙間) + 下余白 20。ラベルは棒の上の隙間に入る
  const H = CANVAS.height(30 + items.length * (bh + gap) + 20);
  const cx = W / 2, max = Math.max(...items.flatMap((d) => [d.l, d.r]), 1);
  const bars = items.map((d, i) => {
    const y = 30 + i * (bh + gap);
    const lw = (d.l / max) * (cx - 80);
    const rw = (d.r / max) * (cx - 80);
    return `<rect x="${cx - lw}" y="${y}" width="${lw}" height="${bh}" rx="4" fill="${VAR_BLUE}" opacity="0.9"/>
      <rect x="${cx}" y="${y}" width="${rw}" height="${bh}" rx="4" fill="${VAR_PINK}" opacity="0.9"/>
      ${svgText({ x: cx, y: y - 6, text: d.label, fontSize: 14, fill: 'var(--fg, #43436c)', weight: 700 })}`;
  });
  return `<svg viewBox="0 0 ${W} ${H}" role="img" aria-label="${escapeXml(opts.ariaLabel || 'バタフライチャート')}" xmlns="http://www.w3.org/2000/svg">
  <line x1="${cx}" y1="20" x2="${cx}" y2="${H - 20}" stroke="${VAR_BLUE}" stroke-width="${kit.STROKE.axis}"/>
  ${bars.join('\n  ')}
</svg>`;
}

/** マインドマップ（中心ノード + 放射枝）
 *  v7.5.0: 横長 viewBox、ラベルは外円の外側にリーダー線で配置し、文字切れを解消
 */
function buildMindmap(center, branches, opts = {}) {
  const W = CANVAS.w, H = CANVAS.h.md, cx = W / 2, cy = H / 2;
  const branchList = (branches || []).filter(Boolean);
  const n = Math.min(8, Math.max(3, branchList.length));
  // R + ノード半径 38 + ラベル行 (16px × 最大3行 ≒ 48) の半分が H/2 に収まる範囲
  const R = 200;       // 中心 → ノード中心の半径
  const rNode = 38;    // ノード円半径（ラベルは外置）
  const rCenter = 78;  // 中心円半径
  const parts = [];
  // 中心円
  parts.push(`<circle cx="${cx}" cy="${cy}" r="${rCenter}" fill="${VAR_BLUE}"/>
    ${svgText({ x: cx, y: cy + 6, text: center || '', fontSize: 18, fill: '#fff', weight: 800 })}`);
  for (let i = 0; i < n; i++) {
    const a = (2 * Math.PI * i) / n - Math.PI / 2;
    const cosA = Math.cos(a), sinA = Math.sin(a);
    const x = cx + R * cosA, y = cy + R * sinA;
    const it = branchList[i];
    const c = colorOf(it, i, opts);
    const label = typeof it === 'string' ? it : (it && (it.label || it.text || it.name)) || '';
    // 中心からノードへの線（中心円・ノード円ぶんを差し引く）
    const lx1 = cx + rCenter * cosA, ly1 = cy + rCenter * sinA;
    const lx2 = x - rNode * cosA, ly2 = y - rNode * sinA;
    // ラベル位置（ノードの外側）
    const labelDist = rNode + 14;
    const lx = x + labelDist * cosA, ly = y + labelDist * sinA;
    // テキストアンカー: 右半分は start、左半分は end、上下は middle
    let anchor = 'middle';
    if (cosA > 0.3) anchor = 'start';
    else if (cosA < -0.3) anchor = 'end';
    // 折返し幅: 側方ラベルは外周までの残り、上下ラベルは隣接枝とぶつからない幅
    const labelW = anchor === 'middle' ? 220 : Math.max(120, (anchor === 'start' ? W - 20 - lx : lx - 20));
    // 契約 §3: 3 行に入り切らない枝ラベルは切らずに落とす
    const wrappedLabel = kit.wrapText(label, labelW, 16, { maxLines: 3, ellipsis: false });
    const wrapped = wrappedLabel.truncated ? [] : wrappedLabel.lines;
    const lineH = 22;
    // 複数行が中心側へ食い込まないよう、行ブロックをラベル基準点で縦中央にそろえる
    const textY = ly + 5 + (sinA > 0.5 ? 8 : sinA < -0.5 ? -2 : 0) - ((wrapped.length - 1) * lineH) / 2;
    parts.push(`<line x1="${lx1.toFixed(1)}" y1="${ly1.toFixed(1)}" x2="${lx2.toFixed(1)}" y2="${ly2.toFixed(1)}" stroke="${c}" stroke-width="${kit.STROKE.primary}"/>
      <circle cx="${x.toFixed(1)}" cy="${y.toFixed(1)}" r="${rNode}" fill="${c}" opacity="0.95"/>
      ${svgTextLines(Number(lx.toFixed(1)), Number(textY.toFixed(1)), wrapped, lineH, { anchor, fill: kit.TOKENS.ink, fontSize: 16, weight: 700 })}`);
  }
  return `<svg viewBox="0 0 ${W} ${H}" class="mindmap-svg" role="img" aria-label="${escapeXml(opts.ariaLabel || 'マインドマップ')}" xmlns="http://www.w3.org/2000/svg">
  ${parts.join('\n  ')}
</svg>`;
}

/** v7.5.0: Before/After 2カラム比較ビルダー
 *  diagram-vs / diagram-comparison-1 用。左=Before(赤系)、右=After(緑/青系)。
 *  入力: leftItems, rightItems, opts: { leftLabel, rightLabel, leftTitle, rightTitle }
 */
function buildVs(leftItems, rightItems, opts = {}) {
  const W = CANVAS.w;
  const gap = 60;
  const leftX = 40;
  // 2 カラム等分: 有効幅 (W - 左右余白 80) から中央の隙間を引いて 2 等分する
  const colW = (W - leftX * 2 - gap) / 2;
  const rightX = leftX + colW + gap;
  const headerH = 70;
  const padX = 24;
  const itemGap = 12;
  const topY = 60;
  const bottomPad = 28;
  const lItems = (leftItems || []).slice(0, CAPACITY.buildVs);
  const rItems = (rightItems || []).slice(0, CAPACITY.buildVs);
  const leftLabel = opts.leftLabel || 'Before';
  const rightLabel = opts.rightLabel || 'After';
  const leftTitle = opts.leftTitle || opts.leftHeading || '悪い例';
  const rightTitle = opts.rightTitle || opts.rightHeading || '良い例';
  const leftColor = VAR_PINK;
  const rightColor = VAR_AQUA;
  // 項目テキストの実測折返しから行高を決める (旧: itemH=56 固定 + 22文字で強制省略)
  const itemFs = 17;
  const itemTextW = colW - padX * 2 - 56 - 16;
  const itemLines = (it) => {
    const t = typeof it === 'string' ? it : ((it && (it.label || it.text)) || '');
    // 契約 §3: 3 行に入り切らない項目は切らずに落とす
    const w = kit.wrapText(t, itemTextW, itemFs, { maxLines: 3, ellipsis: false });
    return w.truncated ? [] : w.lines;
  };
  const maxLineCount = [...lItems, ...rItems].reduce((mx, it) => Math.max(mx, itemLines(it).length), 1);
  // 左右で行高を揃えないと2カラムの項目がずれるため、最大行数を両カラム共通の itemH にする
  const rawItemH = kit.snap(Math.max(56, 26 + maxLineCount * (itemFs + 8)));
  const maxItems = Math.max(lItems.length, rItems.length, 1);
  // 最大の標準高でも入らない量は行高の方を詰める。上限は
  //   (lg - 上余白 topY - 下余白 40 - ヘッダー - 上部余白22 - 下部余白 - 隙間合計) / 件数
  const itemCap = kit.snap(Math.max(56,
    (CANVAS.h.lg - topY - 40 - headerH - 22 - bottomPad - Math.max(0, maxItems - 1) * itemGap) / maxItems));
  const itemH = Math.min(rawItemH, itemCap);
  // 動的カード高さ: ヘッダー + 上部余白22 + 項目数*itemH + (項目数-1)*itemGap + 下部余白
  const cardH = headerH + 22 + maxItems * itemH + Math.max(0, maxItems - 1) * itemGap + bottomPad;
  const H = CANVAS.height(topY + cardH + 40);

  function column(x, items, color, label, title, isLeft) {
    const blocks = [];
    // カード背景: 純白 + 薄ボーダー（var() を使わずハードコード）
    blocks.push(`<rect x="${x}" y="${topY}" width="${colW}" height="${cardH}" rx="16" fill="${kit.TOKENS.paper}" stroke="${kit.TOKENS.rule}" stroke-width="${kit.STROKE.node}"/>`);
    // ヘッダー（カラー）
    blocks.push(`<rect x="${x}" y="${topY}" width="${colW}" height="${headerH}" rx="16" fill="${color}" opacity="0.92"/>`);
    blocks.push(`<rect x="${x}" y="${topY + headerH - 16}" width="${colW}" height="16" fill="${color}" opacity="0.92"/>`);
    // バッジ
    blocks.push(`<rect x="${x + 20}" y="${topY + 14}" width="86" height="32" rx="16" fill="${kit.TOKENS.white}" opacity="0.95"/>`);
    blocks.push(svgText({ x: x + 63, y: topY + 36, text: label, fontSize: 16, fill: color, weight: 800 }));
    // タイトル: バッジ右端からカード右端までに収める
    blocks.push(svgTextFit(title, { x: x + 116, y: topY + 10, w: colW - 116 - 20, h: headerH - 20 }, { fill: kit.TOKENS.white, weight: 800, maxFont: 22, anchor: 'start', padX: 8 }));
    // 項目
    items.forEach((it, i) => {
      const y = topY + headerH + 22 + i * (itemH + itemGap);
      const lines = itemLines(it);
      blocks.push(`<rect x="${x + padX}" y="${y}" width="${colW - padX * 2}" height="${itemH}" rx="10" fill="${kit.TOKENS.paper2}" stroke="${kit.TOKENS.rule}" stroke-width="${kit.STROKE.node}"/>`);
      blocks.push(`<rect x="${x + padX}" y="${y}" width="6" height="${itemH}" fill="${color}"/>`);
      // アイコン円
      blocks.push(`<circle cx="${x + padX + 32}" cy="${y + itemH / 2}" r="14" fill="${color}" opacity="0.18"/>`);
      blocks.push(svgText({ x: x + padX + 32, y: y + itemH / 2 + 5, text: isLeft ? '×' : '○', fontSize: 18, fill: color, weight: 800 }));
      // ラベル: 実測折返し + 禁則。複数行は行ブロックを縦中央に置く
      const lineH = itemFs + 8;
      const firstY = y + itemH / 2 - ((lines.length - 1) * lineH) / 2 + itemFs * 0.35;
      blocks.push(svgTextLines(x + padX + 56, Number(firstY.toFixed(1)), lines, lineH, {
        anchor: 'start', fill: kit.TOKENS.ink, fontSize: itemFs, weight: 600,
      }));
    });
    return blocks.join('\n  ');
  }

  // 中央 VS マーク
  const vsX = leftX + colW + gap / 2;
  const vsCy = topY + cardH / 2;
  const vsBlock = `<circle cx="${vsX}" cy="${vsCy}" r="34" fill="#FFFFFF" stroke="${VAR_VIOLET}" stroke-width="${kit.STROKE.primary}"/>
    ${svgText({ x: vsX, y: vsCy + 8, text: 'VS', fontSize: 22, fill: VAR_VIOLET, weight: 900 })}`;

  return `<svg viewBox="0 0 ${W} ${H}" class="vs-svg" role="img" aria-label="${escapeXml(opts.ariaLabel || 'Before/After 比較')}" xmlns="http://www.w3.org/2000/svg">
  ${defs()}
  ${column(leftX, lItems, leftColor, leftLabel, leftTitle, true)}
  ${column(rightX, rItems, rightColor, rightLabel, rightTitle, false)}
  ${vsBlock}
</svg>`;
}

/** 折れ線グラフ */
function buildLineChart(data, opts = {}) {
  const W = CANVAS.w, H = CANVAS.h.md, padL = 60, padR = 30, padT = 30, padB = 50;
  const innerW = W - padL - padR, innerH = H - padT - padB;
  const list = data.slice(0, CAPACITY.buildLineChart);
  const max = Math.max(...list.map((d) => d.value), 1);
  const stepX = list.length > 1 ? innerW / (list.length - 1) : innerW;
  const pts = list.map((d, i) => `${(padL + i * stepX).toFixed(1)},${(padT + innerH - (d.value / max) * innerH).toFixed(1)}`);
  const dots = list.map((d, i) => {
    const x = padL + i * stepX;
    const y = padT + innerH - (d.value / max) * innerH;
    // 端の目盛りラベルを中央そろえにすると、軸端 (x = padL / padL+innerW) を中心に
    // ラベル幅の半分だけ viewBox の外へ出る。右端は padR(30) しか余白がなく、
    // 日本語 6 字 = MIN_FONT(14) * 6 = 84px の半分 42px > 30 で必ずはみ出す (D1)。
    // 端だけ寄せ方を変えて、軸端から内側へ描く。
    const anchor = i === 0 ? 'start' : (i === list.length - 1 ? 'end' : 'middle');
    // 折返し幅は隣のラベルとぶつからない範囲 = 目盛り間隔 - ラベル間隔
    const maxWidth = Math.max(MIN_FONT * 2, stepX - kit.LABEL_GAP);
    return `<circle cx="${x.toFixed(1)}" cy="${y.toFixed(1)}" r="5" fill="${VAR_BLUE}"/>
      ${svgText({ x, y: padT + innerH + 22, text: d.label, fontSize: MIN_FONT, fill: 'var(--fg, #43436c)', anchor, maxWidth, maxLines: 2 })}`;
  });
  return `<svg viewBox="0 0 ${W} ${H}" role="img" aria-label="${escapeXml(opts.ariaLabel || '折れ線グラフ')}" xmlns="http://www.w3.org/2000/svg">
  <line x1="${padL}" y1="${padT + innerH}" x2="${padL + innerW}" y2="${padT + innerH}" stroke="${VAR_BLUE}" stroke-width="${kit.STROKE.axis}"/>
  <line x1="${padL}" y1="${padT}" x2="${padL}" y2="${padT + innerH}" stroke="${VAR_BLUE}" stroke-width="${kit.STROKE.axis}"/>
  <polyline points="${pts.join(' ')}" fill="none" stroke="${VAR_BLUE}" stroke-width="${kit.STROKE.primary}"/>
  ${dots.join('\n  ')}
</svg>`;
}

/** レーダー（多角形グラフ） */
function buildRadarChart(axes, series, opts = {}) {
  const W = CANVAS.w, H = CANVAS.h.md, cx = W / 2, cy = H / 2;
  // R + ラベル環 30 + 文字高 (MIN_FONT の行送り ≒ 21) <= H/2。円グラフと同じ導出。
  const R = gridFloor(H / 2 - 30 - Math.round(MIN_FONT * 1.5));
  const axList = axes.slice(0, CAPACITY.buildRadarChart);
  const n = axList.length;
  const polyAxes = axList.map((a, i) => {
    const ang = -Math.PI / 2 + (2 * Math.PI * i) / n;
    const x = cx + R * Math.cos(ang), y = cy + R * Math.sin(ang);
    const lx = cx + (R + 30) * Math.cos(ang), ly = cy + (R + 30) * Math.sin(ang);
    return `<line x1="${cx}" y1="${cy}" x2="${x.toFixed(1)}" y2="${y.toFixed(1)}" stroke="${VAR_AQUA}" stroke-width="${kit.STROKE.hairline}"/>
      ${svgText({ x: lx, y: ly + 5, text: a, fontSize: 14, fill: 'var(--fg, #43436c)', weight: 700 })}`;
  }).join('\n  ');
  // 系列は色でしか見分けられないので COLOR_PALETTE の色数を超えて重ねない
  const polys = (series || []).slice(0, COLOR_PALETTE.length).map((s, si) => {
    const c = COLOR_PALETTE[si % COLOR_PALETTE.length];
    const pts = (s.values || []).slice(0, n).map((v, i) => {
      const ang = -Math.PI / 2 + (2 * Math.PI * i) / n;
      const r = (Math.max(0, Math.min(100, v)) / 100) * R;
      return `${(cx + r * Math.cos(ang)).toFixed(1)},${(cy + r * Math.sin(ang)).toFixed(1)}`;
    }).join(' ');
    return `<polygon points="${pts}" fill="${c}" opacity="0.4" stroke="${c}" stroke-width="${kit.STROKE.secondary}"/>`;
  }).join('\n  ');
  return `<svg viewBox="0 0 ${W} ${H}" class="radar-svg" role="img" aria-label="${escapeXml(opts.ariaLabel || 'レーダーチャート')}" xmlns="http://www.w3.org/2000/svg">
  ${polyAxes}
  ${polys}
</svg>`;
}

/** ゲージ（半円） */
function buildGauge(value, opts = {}) {
  const W = CANVAS.w, H = CANVAS.h.sm, cx = W / 2, cy = H - 60;
  // 半円の半径は「上に帯 (STROKE.band=24) の半分ぶんの逃がしを残す」条件で決まる。
  //   cy - r - band/2 >= 上余白 40  →  r <= cy - 52。
  // 旧値 280 はこの式へ H=360 ではなく 420 を入れた誤りで、cy=300 の実際には
  // 弧の頂点が y=20、帯の外縁が y=8 まで来て上へ張り付いていた。
  const r = kit.snap(cy - 52);
  const v = Math.max(0, Math.min(100, Number(value) || 0));
  const ang = Math.PI * (1 - v / 100);
  const x = cx + r * Math.cos(ang), y = cy - r * Math.sin(ang);
  // 値の弧は左端から最大でも半周 (180 度) しか進まないので、large-arc-flag は
  // 常に 0。ここを v > 50 で 1 にすると 180 度超の側、つまり同じ半径で中心の
  // 違うもう一方の弧が選ばれ、トラックから外れた位置に別半径のように見える弧が
  // 描かれる (見出しの高さまで伸びて分断されて見えていたのはこれ)。
  const large = 0;
  return `<svg viewBox="0 0 ${W} ${H}" role="img" aria-label="${escapeXml(opts.ariaLabel || 'ゲージ')}" xmlns="http://www.w3.org/2000/svg">
  <path d="M${cx - r},${cy} A${r},${r} 0 0 1 ${cx + r},${cy}" fill="none" stroke="${VAR_AQUA}" stroke-width="${kit.STROKE.band}" opacity="0.3"/>
  <path d="M${cx - r},${cy} A${r},${r} 0 ${large} 1 ${x.toFixed(1)},${y.toFixed(1)}" fill="none" stroke="${VAR_BLUE}" stroke-width="${kit.STROKE.band}"/>
  ${svgText({ x: cx, y: cy - 30, text: `${v}%`, fontSize: 36, fill: 'var(--fg, #43436c)', weight: 800 })}
</svg>`;
}

/** スキャッター */
function buildScatterChart(data, opts = {}) {
  const W = CANVAS.w, H = CANVAS.h.md, padL = 60, padR = 30, padT = 30, padB = 50;
  const innerW = W - padL - padR, innerH = H - padT - padB;
  const list = data.slice(0, CAPACITY.buildScatterChart);
  const xs = list.map((d) => d.x || 0), ys = list.map((d) => d.y || 0);
  const xMax = Math.max(...xs, 1), yMax = Math.max(...ys, 1);
  const dots = list.map((d, i) => {
    const x = padL + ((d.x || 0) / xMax) * innerW;
    const y = padT + innerH - ((d.y || 0) / yMax) * innerH;
    const c = COLOR_PALETTE[i % COLOR_PALETTE.length];
    return `<circle cx="${x.toFixed(1)}" cy="${y.toFixed(1)}" r="6" fill="${c}" opacity="0.85"/>`;
  });
  return `<svg viewBox="0 0 ${W} ${H}" role="img" aria-label="${escapeXml(opts.ariaLabel || '散布図')}" xmlns="http://www.w3.org/2000/svg">
  <line x1="${padL}" y1="${padT + innerH}" x2="${padL + innerW}" y2="${padT + innerH}" stroke="${VAR_BLUE}" stroke-width="${kit.STROKE.axis}"/>
  <line x1="${padL}" y1="${padT}" x2="${padL}" y2="${padT + innerH}" stroke="${VAR_BLUE}" stroke-width="${kit.STROKE.axis}"/>
  ${dots.join('\n  ')}
</svg>`;
}

/** 単純垂直タイムライン (1列) */
function buildVerticalTimeline(events, opts = {}) {
  const n = Math.min(8, events.length);
  const W = CANVAS.w;
  const cx = 100;
  const textX = cx + 30;
  // 本文段は幅の 60% に留める。viewBox 幅いっぱいに流すと 1 行が長すぎて
  // 視線が横に流れ、縦の時間軸が読めなくなる。
  const textW = kit.snap(W * 0.6);
  const list = events.slice(0, n);
  // 各イベントの行数から必要な段送りを求める (旧: 80px 固定で長文が次項目へ重なっていた)
  const wrapped = list.map((e) => {
    const date = e.date || '';
    const label = e.label || (typeof e === 'string' ? e : '');
    // 契約 §3: 3 行に入り切らない出来事は切らずに落とす
    const w = kit.wrapText(`${date}  ${label}`.trim(), textW, 16, { maxLines: 3, ellipsis: false });
    return w.truncated ? [] : w.lines;
  });
  const rawStep = kit.snap(Math.max(80, 34 + Math.max(...wrapped.map((l) => l.length)) * 24));
  // 最大の標準高でも入らない量は段送りの方を詰める (上下余白 40 + 40 を確保)
  const stepCapPx = kit.snap(Math.max(80, (CANVAS.h.lg - 80) / n));
  const step = Math.min(rawStep, stepCapPx);
  const H = CANVAS.height(40 + n * step + 40);
  const items = list.map((e, i) => {
    const y = 40 + i * step;
    const c = colorOf(e, i, opts);
    const lineH = 24;
    const firstY = y + 5 - ((wrapped[i].length - 1) * lineH) / 2;
    return `<circle cx="${cx}" cy="${y}" r="14" fill="${c}"/>
      ${svgTextLines(textX, Number(firstY.toFixed(1)), wrapped[i], lineH, { anchor: 'start', fill: kit.TOKENS.ink, fontSize: 16, weight: 700 })}`;
  });
  return `<svg viewBox="0 0 ${W} ${H}" role="img" aria-label="${escapeXml(opts.ariaLabel || '縦タイムライン')}" xmlns="http://www.w3.org/2000/svg">
  <line x1="${cx}" y1="20" x2="${cx}" y2="${H - 20}" stroke="${VAR_BLUE}" stroke-width="${kit.STROKE.primary}"/>
  ${items.join('\n  ')}
</svg>`;
}

/** ガント（バー期間） */
function buildGantt(tasks, opts = {}) {
  const n = Math.min(8, tasks.length);
  // 1 行 = 棒 32 + 行間 18 = 50。必要高 = 上余白 padT + n*50 + 下余白 40
  const W = CANVAS.w, H = CANVAS.height(40 + n * 50 + 40), padL = 200, padR = 30, padT = 40;
  const innerW = W - padL - padR;
  const allEnds = tasks.map((t) => Number(t.end) || 0);
  const max = Math.max(...allEnds, 1);
  const bars = tasks.slice(0, n).map((t, i) => {
    const y = padT + i * 50;
    const x = padL + (Number(t.start) || 0) / max * innerW;
    const w = ((Number(t.end) || 0) - (Number(t.start) || 0)) / max * innerW;
    const c = colorOf(t, i, opts);
    // タスク名は軸左の帯 (padL - 30) に収める。溢れると SVG 左端の外へ消えていた
    return `<rect x="${x.toFixed(1)}" y="${y}" width="${Math.max(20, w).toFixed(1)}" height="32" rx="6" fill="${c}" opacity="0.92"/>
      ${svgTextFit(t.label || '', { x: 10, y, w: padL - 30, h: 32 }, { fill: kit.TOKENS.ink, weight: 700, maxFont: 14, anchor: 'end', padX: 4, padY: 2 })}`;
  });
  return `<svg viewBox="0 0 ${W} ${H}" role="img" aria-label="${escapeXml(opts.ariaLabel || 'ガントチャート')}" xmlns="http://www.w3.org/2000/svg">
  <line x1="${padL}" y1="${padT - 10}" x2="${padL}" y2="${H - 10}" stroke="${VAR_BLUE}" stroke-width="${kit.STROKE.axis}"/>
  ${bars.join('\n  ')}
</svg>`;
}

/** スター（5角形ノード強調） */
function buildStar(items, opts = {}) {
  const W = CANVAS.w, H = CANVAS.h.md, cx = W / 2, cy = H / 2;
  const n = Math.min(7, items.length);
  // R + ノード半径 50 + 上下余白 36 <= H/2。余白 36 は矢じり相当の逃がし
  // (GRID 4 の 9 倍) で、H の段が変わっても比率でなく実寸で確保する。
  const nodeR = 50;
  const R = gridFloor(H / 2 - nodeR - 36);
  const nodes = items.slice(0, n).map((it, i) => {
    const a = -Math.PI / 2 + (2 * Math.PI * i) / n;
    const x = cx + R * Math.cos(a), y = cy + R * Math.sin(a);
    const c = colorOf(it, i, opts);
    const label = typeof it === 'string' ? it : it.label || '';
    // ノード円に内接する正方形 (辺 = nodeR*√2) を折返し領域にする
    const inner = nodeR * Math.SQRT2;
    return `<line x1="${cx}" y1="${cy}" x2="${x.toFixed(1)}" y2="${y.toFixed(1)}" stroke="${c}" stroke-width="${kit.STROKE.secondary}"/>
      <circle cx="${x.toFixed(1)}" cy="${y.toFixed(1)}" r="${nodeR}" fill="${c}" opacity="0.9"/>
      ${svgTextFit(label, { x: x - inner / 2, y: y - inner / 2, w: inner, h: inner }, { fill: '#fff', weight: 700, maxFont: 14, padX: 2, padY: 2 })}`;
  });
  return `<svg viewBox="0 0 ${W} ${H}" class="star-svg" role="img" aria-label="${escapeXml(opts.ariaLabel || 'スター図')}" xmlns="http://www.w3.org/2000/svg">
  <circle cx="${cx}" cy="${cy}" r="40" fill="${VAR_YELLOW}"/>
  ${nodes.join('\n  ')}
</svg>`;
}

/**
 * 価値スタック（積層四角）。
 * buildPyramid は「上が狭い」形なので、積み上げの語彙では先頭項目を土台 (下) に
 * 置きたい。ただし入力を反転すると図の読み順が本文の並びと逆になり、読者が
 * 突き合わせたときに対応が取れない。順序の一致を優先して反転しない。
 */
function buildValueStack(items, opts = {}) {
  return buildPyramid(items, opts);
}

/** AIDMA / FABE 縦カラム */
function buildVerticalColumns(items, opts = {}) {
  return buildVerticalFlow(items, opts);
}

/** クロックパイ（時計風円グラフ） */
function buildClockPie(data, opts = {}) {
  return buildPieChart(data, opts);
}

/**
 * 各ビルダーが 1 枚に載せられる件数の上限。関数内の Math.min(N, len) と同じ値を
 * 持つ (下の整合テストで一致を検査する)。上限そのものは配置の都合で決まるが、
 * 超過分を黙って捨てると読者は「全部が描かれている」と信じてしまうため、
 * ここを表に出して注記の材料にする。
 */
const CAPACITY = {
  buildHorizontalFlow: 7,
  buildCycle: 8,
  buildPyramid: 5,
  buildHierarchy: 4,
  buildVerticalFlow: 8,
  buildConcentric: 5,
  buildVenn: 3,
  buildFunnel: 6,
  buildChevron: 7,
  buildSnake: 8,
  buildVerticalTimeline: 8,
  buildGantt: 8,
  buildStar: 7,
  // 委譲型ビルダー。自分では Math.min を書かず別ビルダーへ丸投げするため、
  // 委譲先の上限をここで継承する。書き忘れると cap=0 になり guard の
  // 「ほか N 件」注記が付かず、超過分が黙って消える。
  buildValueStack: 5,        // → buildPyramid
  buildVerticalColumns: 8,   // → buildVerticalFlow
  buildMatrix: 4,            // quadrants.slice(0, 4)
  buildMindmap: 8,           // branches の Math.min(8, ...)
  // --- v7.7.0 追加: グラフ系の登録漏れを塞ぐ -------------------------------
  // どれも cap=0 で素通しになっており、超過分が注記なしで消えていた。
  //
  // 上限の決め方は 2 つだけ。
  //  (a) 等分割型 … N <= (有効幅 + 間隔) / (最小要素幅 + 間隔)。日本語 1 字の幅は
  //      kit.charWidth で全角 1.0em なので「最小フォント × 想定字数」が最小幅。
  //  (b) 色識別型 … 要素を色でしか見分けられない図は COLOR_PALETTE の色数が上限。
  //      6 件目から色が一巡し、凡例が引けなくなる。
  //
  // どちらの幾何も 8 を超える値を許すが、CAPACITY の**最大値**は
  // validate-svg-diagram.py D11 の複雑度上限 (最大値 × COMPLEXITY_FACTOR 4) の
  // 基準でもある。1 つでも大きな値を置くと全図の複雑度上限が緩むため、
  // 幾何上限が 8 を超える型は既存の縦積み型 (buildVerticalFlow = 8) に揃える。
  // 以下の数値は CANVAS.w = 960 / h = {sm 360, md 540, lg 720} で計算している。
  //
  // (a) 軸ラベル帯 innerW = 960 - padL 80 - padR 30 = 850、ラベル最小幅は
  //     MIN_FONT(14) × 6 字 = 84 → 850 / 84 = 10.1 → 幾何 10、D11 の都合で 8
  buildBarChart: 8,
  // (a) innerW = 960 - 60 - 30 = 870、同じ 84 → 10.4 → 幾何 10、同上で 8
  buildLineChart: 8,
  // (a) 点にラベルが無いので幅では律速しない。重なり (点直径 12 + 離隔 5 = 17px) は
  //     innerW 870 に対し 51 件まで許すが、それは「読める散布図」ではない。
  //     他チャートと同じ 8 に揃え、D11 の上限を押し上げない
  buildScatterChart: 8,
  // (b) 扇は色でしか見分けられない。COLOR_PALETTE.length = 5
  buildPieChart: 5,
  buildClockPie: 5,          // → buildPieChart
  // (a) 軸ラベルはラベル環 (R 216 + 30 = 246) の円周 2π×246 = 1546 に並ぶ。隣接
  //     ラベルが重ならない条件は 1546 / N >= MIN_FONT(14) × 8 字 = 112 → N <= 13.8
  //     → 幾何 13、同上で 8。系列 (第2引数) は (b) で 5 (CAPACITY_ARGS 参照)
  buildRadarChart: 8,
  // (a) 左端ラベルは縦に積む。ラベル帯 32 + 間隔 8 = 40 刻みで
  //     (H md 540 - padY*2 100 + 8) / 40 = 11.2 → 幾何 11、同上で 8
  buildSlope: 8,
  // (a) 1 行 = 棒 28 + 隙間 28 = 56。(lg 720 - 上余白 30 - 下余白 20 + 28) / 56 = 12.4
  //     → 幾何 12、同上で 8
  buildButterfly: 8,
  // (a) 縦積み。カード領域 = lg 720 - topY 60 - 下 40 - ヘッダ 70 - 22 - 28 = 500。
  //     項目高 itemH は 2 行前提の 76 から下限 56 まで自動で詰まるので、
  //     幾何は (500 + 12) / (76 + 12) = 5.8 と (500 + 12) / (56 + 12) = 7.5 の間。
  //     現行の 6 はこの範囲に収まり、12 字ラベル 6 件が実測でも落ちない
  buildVs: 6,
  // --- v7.7.0 追加: svg-structures.cjs の 10 種 ------------------------------
  // 契約 §2「新しいビルダーを足したら必ず CAPACITY へ 1 行足す」の未履行分。
  // 10 種すべてが cap=0 のまま `.slice(0, N)` で黙って捨てていた。
  //
  // 導出に使う共通量:
  //   日本語 1 字の幅 = フォントサイズ (kit.charWidth の全角 1.0em)。
  //   構造図のノードは高さ 72-140px あり 2 行以上組めるので、律速するのは
  //   「12 字を 2 行で組む幅」の方。
  //   MIN_NODE_W2 = MIN_FONT_SMALL(12) × 6 字 + 左右パディング 10×2 = 92
  //   (svg-structures.cjs の MIN_NODE_W = 164 は同じ 12 字を 1 行で組む幅で、
  //    1 行しか置けない帯ラベルの側で使う)
  //
  // (a) 等分割型  N <= (有効幅 + 間隔) / (最小要素幅 + 間隔)
  // (b) レーン型  N <= (有効高 + レーン間隔) / (レーン高 + レーン間隔)
  // (c) 環状型    2π/N > 2·asin(rNode/(2R)) + FAN_MIN_GAP/R
  //
  // (a) ゾーン帯。有効幅 = CANVAS.w 960 - 余白 40×2 = 880、ゾーン間隔 36、
  //     ゾーン最小幅 = 92 + ゾーン内側余白 12×2 = 116 →
  //     (880 + 36) / (116 + 36) = 6.02 → 幾何 6。現行 4 は内側なので据置き
  //     (ゾーン内のノード数 ARCH_NODES_PER_ZONE = 6 との積が D11 に効くため)
  buildArchitecture: 4,
  // (a) 段を横一列。有効幅 = 960 - 48×2 = 864、段間隔は矢印ラベルを置くため 88 →
  //     (864 + 88) / (92 + 88) = 5.28 → 幾何 5。現行 4 は内側なので据置き
  buildDataFlow: 4,
  // (a) 3 列 × 2 行の格子。列幅 = (864 - 56×2)/3 = 250 >= 92 なので幅は律速せず、
  //     行数は 2 行で CANVAS.h.md に収まる → 3×2 = 6
  buildEr: 6,
  // (a) アクターを上端に横並び。(864 + 40) / (92 + 40) = 6.8 → 幾何 6。現行 5 は内側。
  //     メッセージ (第2引数) は縦方向: (lg 720 - 上余白 48 - ヘッダ 56 - 24 - 下余白 48)
  //     / step 54 = 10.0 → 10 (CAPACITY_ARGS 参照)
  buildSequence: 5,
  // (a) 3 列 × 2 行の格子 = 6 (列幅 250 >= 92)。遷移 (第2引数) は
  //     「状態 6 × 辺 4 ÷ 端点 2 = 12」で、1 辺あたり fanCapacity(96) = 5 本まで
  //     取り付く余地がある (CAPACITY_ARGS 参照)
  buildState: 6,
  // (b) レーン高 116 + レーン間隔 12。有効高 = CANVAS.h.lg 720 - 余白 40×2 - 工程見出し 24
  //     → (616 + 12) / (116 + 12) = 4.9 → 4
  buildSwimlane: 4,
  // (b) 段。段高 110 + 段間 48 → (CANVAS.h.lg 720 - 48×2 + 48) / (110 + 48) = 4.25 → 4
  //     (段内の要素数は LEVEL_ITEMS = 4 で別に律速する)
  buildHighLevel: 4,
  // (b) 行高 96 + 行間 8。有効高 = CANVAS.h.lg 720 - 40×2 - ヘッダ 40 = 600 →
  //     (600 + 8) / (96 + 8) = 5.8 → 5
  buildItState: 5,
  // (a) 層を横一列。層間 76 → (864 + 76) / (92 + 76) = 5.6 → 幾何 5。現行 4 は内側
  buildMedallion: 4,
  // (c) R = hubW/2 118 + nodeW/2 94 + 逃がし 20 + 最低線長 36 = 268。
  //     ノード外接半径 rNode = √(94² + 36²) = 100.66 →
  //     2·asin(100.66/536) = 0.3778 rad、離隔角 = FAN_MIN_GAP 16 / 268 = 0.0597 rad。
  //     2π/N > 0.4375 → N < 14.4 → 幾何 14 だが、D11 の都合 (上記) で 8 に留める
  buildDpIntegration: 8,
};

/**
 * 配列引数を 2 本以上取るビルダーの、引数位置ごとの上限。
 *
 * guard は既定で「最も長い配列 − CAPACITY」を隠れた件数にするが、それだと
 * buildSequence(actors, messages) のように役割の違う配列を 2 本取る型で
 * 上限の小さい方 (actors) の超過が、上限の大きい方 (messages) の件数に
 * 埋もれて数えられない。位置ごとに上限を持たせ、超過を足し合わせる。
 *
 * CAPACITY 側は「その図の代表的な上限」を単一の整数で持ち続ける
 * (validate-svg-diagram.py の _capacity_max がここを整数として読むため)。
 */
const CAPACITY_ARGS = {
  // (軸, 系列)。軸は等分割型で 8、系列は色識別型で COLOR_PALETTE.length
  buildRadarChart: [8, COLOR_PALETTE.length],
  // (左, 右) はミラーなので同じ上限
  buildSlope: [8, 8],
  buildButterfly: [8, 8],
  buildVs: [6, 6],
  // (アクター, メッセージ)。役割が違うので別々に数える
  buildSequence: [5, 10],
  // (状態, 遷移)。遷移は「状態 6 × 辺 4 ÷ 端点 2」
  buildState: [6, 12],
};

/** 「データがない」を図解として明示する。空の枠に矢印だけが浮くのを防ぐ。 */
function emptyState(opts = {}) {
  const W = CANVAS.w, H = CANVAS.h.sm;
  const label = opts.emptyLabel || '表示できるデータがありません';
  const aria = escapeXml(opts.ariaLabel || label);
  return `<svg class="diagram-svg diagram-empty" viewBox="0 0 ${W} ${H}" role="img" aria-label="${aria}" xmlns="http://www.w3.org/2000/svg">
${defs()}
<rect x="40" y="40" width="${W - 80}" height="${H - 80}" rx="16" fill="${kit.TOKENS.paper}" stroke="${kit.TOKENS.rule}" stroke-width="${kit.STROKE.secondary}" stroke-dasharray="8 6"/>
${svgText({ x: W / 2, y: H / 2 + 6, text: label, fontSize: 18, fill: kit.TOKENS.muted, weight: 700 })}
</svg>`;
}

/** 上限で描き切れなかった件数を図の隅に明記する (黙って捨てない)。 */
function overflowNote(svgStr, hidden) {
  if (!hidden || hidden < 1) return svgStr;
  const vb = /viewBox="([\d.\s-]+)"/.exec(svgStr);
  if (!vb) return svgStr;
  const [, , w, h] = vb[1].trim().split(/\s+/).map(Number);
  if (!isFinite(w) || !isFinite(h)) return svgStr;
  const text = `ほか ${hidden} 件`;
  const tw = Math.ceil(kit.measureText(text, 13)) + 20;
  const x = w - tw - 16, y = h - 34;
  const note = `<g class="diagram-overflow"><rect x="${x}" y="${y}" width="${tw}" height="24" rx="12" fill="${kit.TOKENS.paper}" stroke="${kit.TOKENS.rule}"/>${svgText({ x: x + tw / 2, y: y + 16, text, fontSize: 13, fill: kit.TOKENS.muted, weight: 700 })}</g>`;
  return svgStr.replace(/<\/svg>\s*$/, `${note}</svg>`);
}

/**
 * ビルダーを入力の端に対して安全にする。
 *   - 配列で渡された入力がすべて空 → 矢印だけが浮いた図でなく「データなし」を描く
 *   - 上限を超えた → 描けた件数はそのまま、隠れた件数を隅に明記する
 * 配列を 1 つも取らないビルダー (buildGauge など) は素通しする。
 *
 * @param {object} [opts]
 *   - argCaps: 引数位置ごとの上限 (既定は CAPACITY_ARGS[name])
 *   - hidden: (args) => number。入れ子構造 (ゾーン内のノード、レーン内の工程) を
 *     持つ型は、外側の件数だけ数えても内側で捨てた分が漏れる。数え方を
 *     知っているビルダー側から渡してもらう。
 */
function guard(name, fn, opts = {}) {
  const cap = CAPACITY[name] || 0;
  const argCaps = opts.argCaps || CAPACITY_ARGS[name] || null;
  const countHidden = typeof opts.hidden === 'function' ? opts.hidden : null;
  return function guarded(...args) {
    const arrays = args.filter(Array.isArray);
    if (arrays.length && arrays.every((a) => a.filter((x) => x != null).length === 0)) {
      return emptyState(args[args.length - 1] || {});
    }
    const out = fn.apply(this, args);
    const live = (a) => a.filter((x) => x != null).length;
    let hidden = 0;
    if (argCaps) {
      // 引数位置ごとに超過を数えて合計する (役割の違う配列の超過を埋もれさせない)
      args.forEach((a, i) => {
        if (!Array.isArray(a) || argCaps[i] == null) return;
        hidden += Math.max(0, live(a) - argCaps[i]);
      });
    } else if (cap) {
      const longest = arrays.reduce((mx, a) => Math.max(mx, live(a)), 0);
      hidden += Math.max(0, longest - cap);
    }
    if (countHidden) hidden += Math.max(0, countHidden(args) || 0);
    return overflowNote(out, hidden);
  };
}

const RAW_BUILDERS = {
  buildHorizontalFlow,
  buildVerticalFlow,
  buildCycle,
  buildPyramid,
  buildHierarchy,
  buildBarChart,
  buildPieChart,
  buildLineChart,
  buildRadarChart,
  buildGauge,
  buildScatterChart,
  buildConcentric,
  buildVenn,
  buildMatrix,
  buildFunnel,
  buildChevron,
  buildSnake,
  buildSlope,
  buildButterfly,
  buildMindmap,
  buildVs,
  buildVerticalTimeline,
  buildGantt,
  buildStar,
  buildValueStack,
  buildVerticalColumns,
  buildClockPie,
};

module.exports = Object.assign(
  // CANVAS / guard / overflowNote / CAPACITY_ARGS を公開するのは svg-structures.cjs が
  // 同じ表と同じ注記機構を使うため。構造図側が自前の viewBox と自前の切り捨てを
  // 持つと、統一した寸法と「ほか N 件」の契約 (§2) がそこだけ効かなくなる。
  { defs, emptyState, CAPACITY, CAPACITY_ARGS, CANVAS, guard, overflowNote },
  Object.fromEntries(Object.entries(RAW_BUILDERS).map(([k, fn]) => [k, guard(k, fn)])),
);
