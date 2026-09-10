/**
 * svg-structures.cjs — 構造図ビルダー (v7.6.0 新設)
 *
 * 既存の svg-builder.cjs は「1タイプ1関数」で 27 種を持つが、
 * 参考にした図解体系にあって本リポジトリに無かった 10 種
 * (architecture / data-flow / er / sequence / state / swimlane /
 *  high-level / it-state / medallion / dp-integration) を、
 * svg-kit.cjs の §6 配置戦略の組合せとして実装する。
 *
 * 設計方針:
 *   - 図解タイプ = 配置戦略 × ノード語彙 × コネクタ語彙 の直積
 *   - 座標は入力から決定論的に決まる (同じ入力 → 同じ SVG)
 *   - 色は既存プラグインの CSS 変数のみを使う (新しい色を発明しない)
 *   - テキストは必ず kit.fitText / kit.wrapText を通す (文字数スライス禁止)
 *   - コネクタは直交エルボまたは同半径円弧のみ (斜め線を作らない)
 */
'use strict';

const kit = require('./svg-kit.cjs');
// svg-builder.cjs は svg-structures.cjs を参照しないので循環はしない。
// 共有するのは「寸法 (CANVAS)」「容量表 (CAPACITY)」「超過注記 (guard)」の 3 つ。
// ここを自前で持つと、統一寸法と「ほか N 件」の契約 (§2) が構造図だけ効かない。
const base = require('./svg-builder.cjs');

const T = kit.TOKENS;
const CANVAS = base.CANVAS;
const CAP = base.CAPACITY;

/* ------------------------------------------------------------------
 * 寸法の導出定数 (新しいマジックナンバーを置かない)
 * ---------------------------------------------------------------- */

/**
 * ノードの最小幅。
 * 日本語は kit.charWidth が全角 1.0em なので「1 字の幅 = フォントサイズ」。
 * ラベルを切り詰めない (契約 §3) 以上、幅が足りない図は「載せない」側へ倒す
 * しかないので、載せられる下限をここで一意に決める。
 *
 *   LABEL_CHARS  = 12 字 … 「データ基盤の統合」級の名詞句が 1 行で入る長さ
 *   MIN_LABEL_W  = MIN_FONT_SMALL(12) × 12 = 144
 *   NODE_PAD_X   = LABEL_GAP(8) + GRID(4) / 2 = 10 … node() の padX と同値
 *   MIN_NODE_W   = 144 + 10 × 2 = 164
 */
const LABEL_CHARS = 12;
const NODE_PAD_X = kit.LABEL_GAP + kit.GRID / 2;
const MIN_NODE_W = kit.MIN_FONT_SMALL * LABEL_CHARS + NODE_PAD_X * 2;

/** 入れ子の上限。外側 (CAPACITY) と同じく幾何から出す。CANVAS.w = 960 基準。 */
// (高さ) ゾーン内は縦積みなのでノード高で律速する。ゾーン本体高 = CANVAS.h.lg 720
// - 余白 40×2 - 見出し 26 - 内側 8×2 = 598、ノード高上限 96 + 間隔 16 →
// (598 + 16) / (96 + 16) = 5.48 … 箱は 96 未満へ縮むので下限 (MIN_FONT 14 の
// 2 行 + 上下padding = 56) で数え直すと (598 + 16) / (56 + 16) = 8.5 → 8。
// 現行の 6 はこの内側なので据置く (D11 の要素数を抑える方を優先)。
const ARCH_NODES_PER_ZONE = 6;
// (高さ) フィールド行 22px。カード高 = ヘッダ 34 + N×22 + 12 が 2 行入る必要があり、
// 2 × (34 + 22N + 12) + 行間 56 + 余白 96 <= CANVAS.h.md 540 → N <= 3.5。
// ただし ER は行数で lg 720 まで倒れるので 2 × (46 + 22N) + 152 <= 720 → N <= 5.9 → 6
const ER_FIELDS = 6;
// (幅) 工程列。レーン本体幅 = CANVAS.w 960 - 余白 40×2 - ヘッダ列 168 = 712、
// 列間 28、工程名は 2 行組みなので最小幅 92 → (712 + 28) / (92 + 28) = 6.16 → 幾何 6。
// 現行 4 は内側なので据置く
const SWIM_STEPS = 4;
// (幅) 段内の要素。有効幅 = 960 - 48×2 - 見出し列 140 = 724、要素間 24 →
// (724 + 24) / (92 + 24) = 6.4 → 幾何 6。現行 4 は内側なので据置く
const LEVEL_ITEMS = 4;
// (高さ) 層内の項目。項目高 32 + 間隔 8。層カード高は 92 + N×44 + 12 で作られ、
// H = 120 + boxH + 56 <= CANVAS.h.md 540 → boxH <= 364 → N <= 5.9 → 幾何 5。
// 現行 4 はこの内側で、層 4 本ぶんの幅 (160px) にも項目名が 2 行で入る
const MEDALLION_ITEMS = 4;

/* ------------------------------------------------------------------
 * 共通ヘルパ
 * ---------------------------------------------------------------- */

/** 入れ子の超過件数 (外側で残った分だけを数える。捨てた外側は二重に数えない) */
function nestedOver(list, pick, cap) {
  return (list || []).reduce((sum, it) => sum + Math.max(0, (pick(it) || []).filter(Boolean).length - cap), 0);
}

/** NODE_STYLES の種別 → 凡例の語 */
const STYLE_LEGEND = {
  focal: '焦点',
  plain: '処理',
  store: '保管・データ',
  external: '外部システム',
  input: '入力・利用者',
  optional: '任意・非同期',
  boundary: '境界',
};

/**
 * NODE_STYLES を 2 種類以上使う図の凡例項目を作る。
 * 1 種類しか使っていない図で凡例を出すと、区別のない塗りに意味があるように
 * 読ませてしまうので空を返す (呼出し側は高さ 0 として扱える)。
 *
 * 見本には NODE_STYLES の組をそのまま渡す。stroke の色だけを渡していた旧版は、
 * **図の中では破線で分かれている 2 種が、凡例では同じ色の四角**になっていた。
 * optional と boundary は輪郭色が同じで線種だけが違うので、色だけを渡すと
 * 凡例が 2 項目とも同じ絵になり、区別の根拠を語れない。
 */
function styleLegend(types) {
  const uniq = (types || []).filter((t, i, a) => t && kit.NODE_STYLES[t] && a.indexOf(t) === i);
  if (uniq.length < 2) return [];
  return uniq.map((t) => ({ label: STYLE_LEGEND[t] || t, style: kit.NODE_STYLES[t] }));
}

/**
 * 凡例帯を「下端 bottom に揃えて」描く。
 * legendStrip は罫線を y - LABEL_GAP に、行を y から rowH 刻みで描くので占有域は
 * legendHeight = LABEL_GAP + 行数 × rowH。下端を合わせる y は
 *   y = bottom - (legendHeight - LABEL_GAP)
 * viewBox 高は必ず legendHeight を先に足してから確定する (後付けは D1 error)。
 */
/**
 * 呼出し側が書いた凡例項目を、図が実際に使っている符号へ解決する。
 *
 * type を書いた項目は NODE_STYLES を引いて見本にする。呼出し側が color で
 * 直に色を書けるようにしていたが、**図はノード種別で描き、凡例は手書きの色で
 * 描く**ことになるので、両者が黙って食い違う。実際 data-flow の凡例は
 * 「入力・利用者」と「保管・データ」に同じ #6A6A68 を当てていて、3 分類を
 * 名乗りながら見た目は 2 分類だった。type を通す限りこの食い違いは起きない。
 *
 * type を持たない項目 (「実線の矢印は受け渡し」のような線種の説明) はそのまま
 * 通す。図の符号を語れるのは呼出し側だけなので、口は塞がない。
 */
function resolveLegendItems(items) {
  return (items || []).filter(Boolean).map((it) => {
    if (typeof it === 'string' || !it.type || !kit.NODE_STYLES[it.type]) return it;
    const { type, color, ...rest } = it;
    return { ...rest, style: kit.NODE_STYLES[type] };
  });
}

function legendAt(items, x, bottom, width) {
  const h = kit.legendHeight(items, width);
  if (!h) return '';
  return kit.legendStrip(items, x, bottom - (h - kit.LABEL_GAP), width);
}

/**
 * 箱に収めたテキストを「1 行 = 1 個の <text>」で描く (kit.fittedTextInBox の代替)。
 *
 * なぜ tspan で積まないか: validate-svg-diagram.py の D1 は <text> の bbox を
 * itertext() の連結長から概算する (契約 §4「D1 の測り方」)。折返しを tspan で
 * 表すと、実際には箱へ収まっている 2 行組が「連結した 1 行」として測られ、
 * 右端のカードでは必ず偽の「はみ出し」= error になる。行を <text> 単位へ分けると
 * 測り方 (1 要素 = 1 行) と描き方が一致する。座標も字形も tspan 版と同一。
 *
 * さらに、最小フォントでも入らず kit.fitText が省略記号で切り詰めた結果は
 * 描かない。日本語は述部が末尾に来るので途中で切ると図が本文と逆のことを
 * 言い始める (契約 §3「ラベルは切り詰めない」)。「入らないなら載せない」側へ倒す。
 * opts.dropIfTruncated は、切り落としても図の意味が壊れない副次テキストで
 * 明示するための注記であり、既定でも切り詰め結果は描かない。
 */
function fittedLines(text, box, opts = {}) {
  if (!text) return '';
  const fit = kit.fitText(text, box.w, box.h, opts);
  if (fit.truncated) return '';
  const anchor = opts.anchor || 'middle';
  const padX = opts.padX != null ? opts.padX : 12;
  const ax = anchor === 'start' ? box.x + padX
    : anchor === 'end' ? box.x + box.w - padX
      : box.x + box.w / 2;
  const blockH = (fit.lines.length - 1) * fit.lineHeight;
  // textBlock は「1 行だけ渡すと y + fontSize*0.35 が baseline」なので、
  // 行ごとの y をここで逆算して渡す (baseline の算術は kit 側と同一)。
  const top = box.y + box.h / 2 - blockH / 2;
  return fit.lines
    .map((ln, i) => kit.textBlock({
      x: ax, y: top + i * fit.lineHeight, lines: [ln],
      fontSize: fit.fontSize, lineHeight: fit.lineHeight, anchor,
      fill: opts.fill || T.ink, weight: opts.weight != null ? opts.weight : 700,
    }))
    .join('');
}

/** 文字列 / オブジェクトどちらの item でも表示名を取り出す */
function nameOf(it) {
  if (it == null) return '';
  if (typeof it === 'string') return it;
  return it.label || it.name || it.text || it.title || '';
}

/** 補助説明 (sublabel) を取り出す */
function subOf(it) {
  if (!it || typeof it === 'string') return '';
  return it.sublabel || it.desc || it.description || it.detail || '';
}

/** item.type から NODE_STYLES を引く。未知 type は plain */
function styleOf(it, fallback = 'plain') {
  const type = (it && typeof it === 'object' && it.type) || fallback;
  if (it && typeof it === 'object' && (it.focal || it.accent)) return kit.NODE_STYLES.focal;
  return kit.NODE_STYLES[type] || kit.NODE_STYLES[fallback] || kit.NODE_STYLES.plain;
}

/**
 * ノード1個 (矩形 + 名前 + 補助説明) を描画する。
 * 名前と補助説明で箱を上下に分け、それぞれ独立に fit させる。
 */
function node(box, it, opts = {}) {
  const st = opts.style || styleOf(it, opts.fallbackType);
  const name = nameOf(it);
  const sub = subOf(it);
  const parts = [kit.nodeRect(box, st, { radius: opts.radius })];
  if (sub) {
    const nameH = Math.round(box.h * 0.58);
    parts.push(fittedLines(name, { x: box.x, y: box.y, w: box.w, h: nameH }, {
      fill: st.text || T.ink, weight: 700, maxFont: opts.maxFont || 16, padX: 10, padY: 4,
    }));
    // 補助説明は「入るなら載せる」。最小フォントでも入らないなら省略記号で切らず
    // 丸ごと落とす (契約 §3)。名前のほうは落とすと空の箱になり、ノードが何なのか
    // 分からなくなるので落とさない。
    parts.push(fittedLines(sub, { x: box.x, y: box.y + nameH - 2, w: box.w, h: box.h - nameH }, {
      fill: T.muted, weight: 500, maxFont: 12, minFont: kit.MIN_FONT_SMALL, padX: 10, padY: 2,
      dropIfTruncated: true,
    }));
  } else {
    parts.push(fittedLines(name, box, {
      fill: st.text || T.ink, weight: 700, maxFont: opts.maxFont || 16, padX: 10, padY: 6,
    }));
  }
  return parts.join('\n  ');
}

/** 箱の各辺中央 (コネクタの取付点) */
function port(box, side, fan) {
  // fan = {index, count}。同じ辺に複数のコネクタが着くとき取り付け位置を等間隔に
  // 散らす。散らさないと線が重なり、どの矢印がどこへ向かうのか読めなくなる。
  // count<=1 なら fanAttach は辺の中央を返すので、従来の呼び出しと同じ結果になる。
  const count = (fan && fan.count > 1) ? fan.count : 1;
  const index = count > 1 ? fan.index : 0;
  const px = kit.fanAttach(box.x, box.w, index, count);
  const py = kit.fanAttach(box.y, box.h, index, count);
  switch (side) {
    case 'left': return { x: box.x, y: py };
    case 'right': return { x: box.x + box.w, y: py };
    case 'top': return { x: px, y: box.y };
    default: return { x: px, y: box.y + box.h };
  }
}

/** 直交コネクタ 1 本 (marker つき) */
function connector(from, to, opts = {}) {
  const color = opts.color || T.muted;
  const dash = opts.dashed ? ` stroke-dasharray="${kit.DASH.fine}"` : '';
  // コネクタは図解の主張そのもの。1.2 は縮小表示で灰色に溶けるので
  // 既定を STROKE.secondary に上げる (根拠は svg-kit.cjs の STROKE 定義)。
  const width = opts.width || kit.STROKE.secondary;
  // axis は「最初にどちらへ折れるか」の希望。実際の屈曲順は safeElbow が
  // 「矢じりが宛先の辺へ正対して入る」側 (INCIDENCE_RULE) を選び直す。
  // 希望どおりに折ると矢の胴体が箱に埋まり、向き = 主張の向きが読めなくなる。
  const first = opts.axis === 'v' ? 'v' : 'h';
  const r = kit.safeElbow(from, to, opts.srcBox, opts.dstBox, { first, mid: opts.mid });
  // incidence === 'degraded' は「どちらの屈曲順でも正対入射にできない配置」
  // (箱が重なる・宛先の辺の外側に発点が無い)。ここで線を捨てると素材が黙って
  // 消えてしまう (契約 §2) ので、線は引いたうえで補助線の細さへ落とし、
  // 「本線ではない」ことを太さの階層で伝える。
  const w = r.incidence === 'degraded' ? kit.STROKE.hairline : width;
  return `<path d="${r.d}" fill="none" stroke="${color}" stroke-width="${w}"${dash} marker-end="${kit.arrowUrl(color)}"/>`;
}

/** ゾーン/レーンの見出し帯 */
function bandLabel(box, text, opts = {}) {
  if (!text) return '';
  return fittedLines(text, box, {
    fill: opts.fill || T.muted, weight: 700, maxFont: opts.maxFont || 13,
    minFont: kit.MIN_FONT_SMALL, padX: 6, padY: 2, anchor: opts.anchor,
  });
}

/** SVG を組み立てる共通の外枠 */
/**
 * 出所行の帯の高さ。文字 1 行 + 上下の余白 (LABEL_GAP) で導出する。
 * 28 は 4 の倍数なので viewBox 高もグリッド上に留まる。
 */
const PROV_H = kit.MIN_FONT_SMALL + kit.LABEL_GAP * 2;

/**
 * 出所・時点を図の**内側**へ 1 行で置く。
 *
 * figcaption に書いた出所は、図が単独で引用・スクリーンショットされた瞬間に
 * 消える (契約 §冒頭「figcaption にしか無い情報は、無いのと同じ」)。
 * ここは既存レイアウトの外へ帯を足す形にしてある。builder の領域計算に
 * 一切触れないので、重なりが起きえない。
 */
function provenanceBand(width, y, opts) {
  const line = [opts.source, opts.asOf].filter(Boolean).join('・');
  if (!line) return { height: 0, body: '' };
  return {
    height: PROV_H,
    body: `<g data-provenance="1">${kit.textBlock({
      x: 40, y: y + kit.LABEL_GAP + kit.MIN_FONT_SMALL / 2,
      lines: [line], fontSize: kit.MIN_FONT_SMALL, lineHeight: kit.MIN_FONT_SMALL,
      fill: T.muted, weight: 500, anchor: 'start', maxWidth: width - 80,
    })}</g>`,
  };
}

/**
 * 呼出し側が明示した凡例を図の下へ足す。
 *
 * builder が自前で作る凡例 (styleLegend) は塗り分けの凡例しか作れない。
 * 実線=同期 / 破線=非同期 のように**線種**で意味を分けた図はそれでは
 * 読み解けないので、kind を持つ項目を外から渡せる口をここに開ける。
 * 出所帯と同じく既存レイアウトの外へ足すので重なりが起きえない。
 */
function explicitLegendBand(width, y, opts) {
  const items = Array.isArray(opts.legendItems) ? opts.legendItems.filter(Boolean) : [];
  if (!items.length) return { height: 0, body: '' };
  const inner = width - 80;
  const h = kit.legendHeight(items, inner);
  if (!h) return { height: 0, body: '' };
  return { height: h, body: kit.legendStrip(items, 40, y + kit.LABEL_GAP, inner) };
}

function frame(width, height, body, opts = {}) {
  const legend = explicitLegendBand(width, height, opts);
  const prov = provenanceBand(width, height + legend.height, opts);
  const extra = [legend.body, prov.body].filter(Boolean);
  return kit.svgRoot({
    width, height: height + legend.height + prov.height,
    className: opts.className,
    ariaLabel: opts.ariaLabel || opts.title || '図解',
    desc: opts.desc,
    body: `${kit.arrowMarkers(opts.extraColors || [])}\n  ${body}${extra.length ? `\n  ${extra.join('\n  ')}` : ''}`,
  });
}

/* ------------------------------------------------------------------
 * 1. architecture — zone × box × elbow
 * ---------------------------------------------------------------- */

/**
 * システム構成図。ゾーン (論理グループ) を横に並べ、各ゾーン内はノードを縦積みする。
 * @param {Array} zones [{ label, nodes: [{label, sublabel, type}] }]
 * @param {object} opts { links: [{from, to, label, dashed}] } from/to はノード名
 */
function buildArchitecture(zones, opts = {}) {
  const list = (zones || []).filter(Boolean).slice(0, CAP.buildArchitecture);
  if (!list.length) return base.emptyState(opts);
  const W = CANVAS.w, M = 40;
  // ゾーンは入口 (input) / 処理 (plain) / 保管 (store) を塗り分けるので凡例が要る。
  // 高さは凡例の実測高を足してから CANVAS の階段で確定する (後付けは D1 error)。
  const legend = styleLegend(['input', 'plain', 'store']);
  const legendH = kit.legendHeight(legend, W - M * 2);
  // 内容量から高さを決める (連続可変にせず sm/md/lg の階段から選ぶ)。
  //   必要高 = 余白 40×2 + ゾーン見出し 28 + 内側 8×2 + n×96 + (n-1)×16 + 凡例
  // n は最も段数の多いゾーンのノード数 (ARCH_NODES_PER_ZONE で頭打ち)
  const maxNodes = Math.max(1, ...list.map((z) => Math.min(ARCH_NODES_PER_ZONE, ((z && z.nodes) || []).filter(Boolean).length)));
  const H = CANVAS.height(M * 2 + 28 + 16 + maxNodes * 96 + (maxNodes - 1) * 16 + legendH);
  const region = kit.area(M, M, W - M * 2, H - M * 2 - legendH);
  // ゾーン幅はノード数に比例させる (ノードが多い層を広く取る)
  const sizes = list.map((z) => Math.max(1, ((z && z.nodes) || []).length));
  const zoneBoxes = kit.zoneLayout(sizes, region, { gap: 36, labelH: 28 });
  const body = [];
  const nodeBox = new Map();

  zoneBoxes.forEach((z, zi) => {
    const zone = list[zi];
    const nodes = ((zone && zone.nodes) || []).filter(Boolean).slice(0, ARCH_NODES_PER_ZONE);
    body.push(`<rect x="${kit.num(z.x)}" y="${kit.num(z.y)}" width="${kit.num(z.w)}" height="${kit.num(z.h)}" fill="none" stroke="${T.rule}" stroke-width="${kit.STROKE.hairline}" stroke-dasharray="${kit.DASH.fine}"/>`);
    body.push(bandLabel(z.label, nameOf(zone) || `ゾーン${zi + 1}`));
    if (!nodes.length) return;
    const inner = kit.area(z.body.x + 12, z.body.y + 8, z.body.w - 24, z.body.h - 16);
    const boxes = kit.columnLayout(nodes.length, inner, { gap: 16 });
    // columnLayout はゾーン全高を等分するため、ノードが 1-2 個のゾーンで箱が縦に
    // 伸びすぎ、名前と補足が離れて 1 つの塊に見えなくなる。高さに上限を設け、
    // 余った縦の空きはゾーン内の中央そろえで吸収する。
    const NODE_H_MAX = 96;
    const h = kit.snap(Math.min(NODE_H_MAX, boxes[0].h));
    const gap = 16;
    const blockH = nodes.length * h + (nodes.length - 1) * gap;
    const top = inner.y + Math.max(0, (inner.h - blockH) / 2);
    boxes.forEach((b, i) => {
      const box = { x: b.x, y: kit.snap(top + i * (h + gap)), w: b.w, h };
      body.push(node(box, nodes[i], { fallbackType: zi === 0 ? 'input' : (zi === zoneBoxes.length - 1 ? 'store' : 'plain') }));
      nodeBox.set(nameOf(nodes[i]), box);
    });
  });

  // 明示 links が無ければ、隣接ゾーンの先頭ノード同士を鎖状につなぐ
  const links = (opts.links && opts.links.length)
    ? opts.links
    : zoneBoxes.slice(0, -1).map((_, zi) => ({
      from: nameOf(((list[zi] || {}).nodes || [])[0]),
      to: nameOf(((list[zi + 1] || {}).nodes || [])[0]),
    }));
  // 1 つのノードへ複数の依存が集まる図なので、辺の中央へ全部着けると終端が
  // 同じ点になり、矢じりが重なって「何本入ってきたか」が読めなくなる。
  // 辺ごとの本数を先に数えて散らす (buildState と同じ規律)。
  const archUse = new Map();
  const archSeen = new Map();
  const archKey = (name, side) => `${name}|${side}`;
  const archPlan = [];
  for (const l of links) {
    const a = nodeBox.get(l.from), b = nodeBox.get(l.to);
    if (!a || !b) continue;
    const rightward = b.x >= a.x + a.w;
    const p = {
      l, a, b, rightward,
      fromSide: rightward ? 'right' : 'left',
      toSide: rightward ? 'left' : 'right',
    };
    archPlan.push(p);
    for (const [name, side] of [[l.from, p.fromSide], [l.to, p.toSide]]) {
      const k = archKey(name, side);
      archUse.set(k, (archUse.get(k) || 0) + 1);
    }
  }
  const archFan = (name, side) => {
    const k = archKey(name, side);
    const index = archSeen.get(k) || 0;
    archSeen.set(k, index + 1);
    return { index, count: archUse.get(k) || 1 };
  };
  for (const p of archPlan) {
    const { l, a, b, rightward } = p;
    const from = port(a, p.fromSide, archFan(l.from, p.fromSide));
    const to = port(b, p.toSide, archFan(l.to, p.toSide));
    body.push(connector(from, to, { color: l.external ? T.link : T.muted, dashed: l.dashed, axis: 'h', srcBox: a, dstBox: b }));
    // ラベルは発ノード直後へ置く。中点に置くと日本語の幅で隣のゾーン枠に乗る
    if (l.label) body.push(kit.arrowLabel(l.label, from.x, from.y, { anchor: 'start', dir: rightward ? 'right' : 'left', side: 'above' }));
  }
  body.push(legendAt(legend, M, H - M / 2, W - M * 2));
  return frame(W, H, body.filter(Boolean).join('\n  '), { ...opts, className: 'architecture-svg' });
}

/* ------------------------------------------------------------------
 * 2. data-flow — row × box × labeled elbow
 * ---------------------------------------------------------------- */

/**
 * データフロー図。段を横一列に並べ、段間のコネクタに「何が流れるか」を書く。
 * @param {Array} stages [{ label, sublabel, via }] via = 次段への矢印ラベル
 */
function buildDataFlow(stages, opts = {}) {
  const list = (stages || []).filter(Boolean).slice(0, CAP.buildDataFlow);
  if (!list.length) return base.emptyState(opts);
  const W = CANVAS.w, M = 48;
  // 段は input / plain / store を塗り分けるので凡例が要る (契約 §1.2)。
  // opts.legend が来ればそれを優先する (呼出し側の語のほうが具体的なため)。
  // ただし見本の絵は resolveLegendItems を通す。語だけを呼出し側から取り、
  // 符号は図と同じ NODE_STYLES から引くことで、凡例と図が別々に動けなくする。
  const legend = (opts.legend && opts.legend.length)
    ? resolveLegendItems(opts.legend)
    : styleLegend(['input', 'plain', 'store']);
  const legendH = kit.legendHeight(legend, W - M * 2);
  // 必要高 = 段の上端 120 + 段高 140 + 下余白 M + 凡例 → 階段で確定
  const H = CANVAS.height(120 + 140 + M + legendH);
  // 矢印ラベルは段と段の隙間に置く。隙間を固定値にすると、日本語ラベルが長い図で
  // 必ず箱にかぶる。最長ラベルの実測幅から隙間を決め、段が痩せすぎない上限で止める。
  const labelFs = 13;
  const maxLabelW = list.slice(0, -1).reduce(
    (mx, s) => Math.max(mx, kit.measureText(String((s && s.via) || ''), labelFs)), 0
  );
  // 段が痩せないよう、隙間の合計は描画幅の 4 割までに抑える。その範囲で足りるなら
  // ラベルを 1 行で置ける幅を取り、足りない段数のときだけ 2 行折返しに委ねる。
  const spanW = W - M * 2;
  const gapCap = list.length > 1 ? (spanW * 0.4) / (list.length - 1) : 88;
  const gap = kit.snap(Math.min(Math.max(88, gapCap), Math.max(88, Math.ceil(maxLabelW) + 28)));
  const boxes = kit.rowLayout(list.length, kit.area(M, 120, W - M * 2, 140), { gap });
  const body = [];
  boxes.forEach((b, i) => {
    body.push(node(b, list[i], { fallbackType: i === 0 ? 'input' : (i === list.length - 1 ? 'store' : 'plain') }));
    if (i < boxes.length - 1) {
      const from = port(b, 'right');
      const to = port(boxes[i + 1], 'left');
      body.push(connector(from, to, { axis: 'h', srcBox: b, dstBox: boxes[i + 1] }));
      const via = (list[i] && list[i].via) || '';
      // 折返し幅は隙間より内側に収める (隙間より広く許すと必ず箱へ乗り上げる)
      if (via) body.push(kit.arrowLabel(via, (from.x + to.x) / 2, from.y, { side: 'above', maxWidth: gap - 20, fontSize: labelFs }));
    }
  });
  body.push(legendAt(legend, M, H - M / 2, W - M * 2));
  return frame(W, H, body.filter(Boolean).join('\n  '), { ...opts, className: 'dataflow-svg' });
}

/* ------------------------------------------------------------------
 * 3. er — grid × field-list box × elbow
 * ---------------------------------------------------------------- */

/**
 * ER 図。エンティティを格子に並べ、フィールド一覧を持つ箱として描く。
 * @param {Array} entities [{ name, fields: ['id: number', ...] }]
 * @param {object} opts { relations: [{from, to, label}] }
 */
function buildEr(entities, opts = {}) {
  const list = (entities || []).filter(Boolean).slice(0, CAP.buildEr);
  if (!list.length) return base.emptyState(opts);
  const W = CANVAS.w, M = 48;
  const cols = Math.min(3, list.length);
  const rows = Math.ceil(list.length / cols);
  const headH = 36, fieldH = 24;
  const maxFields = Math.max(...list.map((e) => ((e && e.fields) || []).filter(Boolean).slice(0, ER_FIELDS).length), 1);
  const cardH = headH + maxFields * fieldH + 12;
  // 必要高 = 余白 48×2 + 行数 × カード高 + 行間 56 → 階段で確定する。
  // 格子は確定した H の内側で組み直すので、余りは行間として散る
  const H = CANVAS.height(M * 2 + rows * cardH + (rows - 1) * 56);
  const cells = kit.gridLayout(list.length, kit.area(M, M, W - M * 2, H - M * 2), { cols, gapX: 56, gapY: 56 });
  const body = [];
  const boxOf = new Map();
  cells.forEach((cell, i) => {
    const e = list[i];
    const box = { x: cell.x, y: cell.y, w: cell.w, h: cardH };
    boxOf.set(nameOf(e), box);
    body.push(kit.nodeRect(box, kit.NODE_STYLES.plain));
    // 見出し帯。**強調ではなく濃度段**で作る。実体の数だけ帯が並ぶので、ここを
    // 強調色にすると 1 図に強調が実体数だけ現れ、「どれが焦点か」を言わない図になる。
    // 帯の役目は実体名と列の並びを分けることだけなので、紙の次の濃度段を当てる。
    body.push(`<rect x="${kit.num(box.x)}" y="${kit.num(box.y)}" width="${kit.num(box.w)}" height="${headH}" fill="${T.tone2}"/>`);
    body.push(`<line x1="${kit.num(box.x)}" y1="${kit.num(box.y + headH)}" x2="${kit.num(box.x + box.w)}" y2="${kit.num(box.y + headH)}" stroke="${T.rule}" stroke-width="${kit.STROKE.hairline}"/>`);
    body.push(fittedLines(nameOf(e), { x: box.x, y: box.y, w: box.w, h: headH }, { fill: T.ink, weight: 700, maxFont: 15, padX: 8, padY: 2 }));
    ((e && e.fields) || []).filter(Boolean).slice(0, ER_FIELDS).forEach((f, fi) => {
      const fy = box.y + headH + 6 + fi * fieldH;
      body.push(fittedLines(String(f), { x: box.x + 6, y: fy, w: box.w - 12, h: fieldH }, {
        fill: T.muted, weight: 500, maxFont: 12, minFont: kit.MIN_FONT_SMALL, padX: 4, padY: 1,
      }));
    });
  });
  for (const r of (opts.relations || [])) {
    const a = boxOf.get(r.from), b = boxOf.get(r.to);
    if (!a || !b) continue;
    const sameRow = Math.abs(a.y - b.y) < 4;
    const from = sameRow ? port(a, b.x > a.x ? 'right' : 'left') : port(a, b.y > a.y ? 'bottom' : 'top');
    const to = sameRow ? port(b, b.x > a.x ? 'left' : 'right') : port(b, b.y > a.y ? 'top' : 'bottom');
    body.push(connector(from, to, { axis: sameRow ? 'h' : 'v', color: T.muted, srcBox: a, dstBox: b }));
    // 関係名は発側の直後へ。中点は 2 枚のカードの間で、他の関係線と重なりやすい
    if (r.label) {
      const dir = sameRow ? (b.x > a.x ? 'right' : 'left') : (b.y > a.y ? 'down' : 'up');
      body.push(kit.arrowLabel(r.label, from.x, from.y, { anchor: 'start', dir, side: sameRow ? 'above' : 'right' }));
    }
  }
  return frame(W, H, body.filter(Boolean).join('\n  '), { ...opts, className: 'er-svg' });
}

/* ------------------------------------------------------------------
 * 4. sequence — column(actors) × lifeline × horizontal arrow
 * ---------------------------------------------------------------- */

/**
 * シーケンス図。アクターを上端に並べ、縦のライフラインへ時系列のメッセージを引く。
 * @param {Array} actors ['ユーザー', 'API', 'DB']
 * @param {Array} messages [{ from, to, label, dashed }]
 */
function buildSequence(actors, messages, opts = {}) {
  const acts = (actors || []).filter(Boolean).slice(0, CAP.buildSequence);
  const msgs = (messages || []).filter(Boolean).slice(0, (base.CAPACITY_ARGS.buildSequence || [])[1] || 10);
  if (acts.length < 2) return base.emptyState(opts);
  const W = CANVAS.w, M = 48, headH = 56, step = 62;
  // 端点をアクターへ引き当てられないメッセージ (綴り違い・自分宛て) は線にならない。
  // **描けるものだけを先に確定する。** 入力の添字で行の y を決めると、落ちた
  // ぶんだけ空行が残り、読者からは「間隔に意味がある」ようにも「何かが
  // 消えた」ようにも見える。高さも描く本数から決める (空行ぶん間延びしない)。
  const nameIndex = (n) => acts.findIndex((a) => nameOf(a) === n);
  const drawn = msgs
    .map((m) => ({ m, a: nameIndex(m.from), b: nameIndex(m.to) }))
    .filter((e) => e.a >= 0 && e.b >= 0 && e.a !== e.b);
  // 先頭アクターだけ input で塗り分けるので、2 語彙 = 凡例が要る (契約 §1.2)
  const legend = styleLegend(['input', 'plain']);
  const legendH = kit.legendHeight(legend, W - M * 2);
  // 必要高 = 上余白 + ヘッダ 56 + 先頭メッセージまでの間 24 + 本数 × 62 + 下余白 + 凡例
  const H = CANVAS.height(M + headH + 24 + Math.max(1, drawn.length) * step + M + legendH);
  const lifeBottom = H - M - legendH;
  const heads = kit.rowLayout(acts.length, kit.area(M, M, W - M * 2, headH), { gap: 40 });
  const body = [];
  const laneX = heads.map((b) => b.x + b.w / 2);
  heads.forEach((b, i) => {
    body.push(node(b, acts[i], { fallbackType: i === 0 ? 'input' : 'plain', maxFont: 15 }));
    // ライフライン (凡例帯の手前で止める。重ねると凡例が図の一部に見える)
    body.push(`<line x1="${kit.num(laneX[i])}" y1="${kit.num(b.y + b.h)}" x2="${kit.num(laneX[i])}" y2="${kit.num(lifeBottom)}" stroke="${T.rule}" stroke-width="${kit.STROKE.hairline}" stroke-dasharray="${kit.DASH.fine}"/>`);
  });
  drawn.forEach(({ m, a, b }, i) => {
    const y = M + headH + 40 + i * step;
    const x1 = laneX[a], x2 = laneX[b];
    const color = m.external ? T.link : T.muted;
    body.push(`<line x1="${kit.num(x1)}" y1="${kit.num(y)}" x2="${kit.num(x2)}" y2="${kit.num(y)}" stroke="${color}" stroke-width="${kit.STROKE.secondary}"${m.dashed ? ` stroke-dasharray="${kit.DASH.fine}"` : ''} marker-end="${kit.arrowUrl(color)}"/>`);
    if (m.label) body.push(kit.arrowLabel(m.label, (x1 + x2) / 2, y, { side: 'above', maxWidth: Math.abs(x2 - x1) - 16 }));
  });
  body.push(legendAt(legend, M, H - M / 2, W - M * 2));
  return frame(W, H, body.filter(Boolean).join('\n  '), { ...opts, className: 'sequence-svg' });
}

/* ------------------------------------------------------------------
 * 5. state — row/grid × box × elbow (+ 自己遷移は円弧)
 * ---------------------------------------------------------------- */

/**
 * 状態遷移図。
 * @param {Array} states [{ label, sublabel, focal }]
 * @param {Array} transitions [{ from, to, label }]
 */
function buildState(states, transitions, opts = {}) {
  const list = (states || []).filter(Boolean).slice(0, CAP.buildState);
  if (!list.length) return base.emptyState(opts);
  // 遷移も上限を持つ。上限 12 の出どころは「状態 6 × 辺 4 ÷ 端点 2」で、
  // 端点の数だけで決まる (辺の容量からは出ていない)。
  // 以前ここには「1 辺に取り付けられる本数は fanCapacity(96) = 5 本」と
  // 添えてあったが、現行の FAN_MIN_GAP 20 では 3 本である。96 は箱の高さなので
  // これは縦辺の容量で、横辺 (列幅 約 250) は 11 本入る。律速は縦辺のみ
  const trs = (transitions || []).filter(Boolean).slice(0, (base.CAPACITY_ARGS.buildState || [])[1] || 12);
  const W = CANVAS.w, M = 48;
  // focal 指定の状態があるときだけ 2 語彙になるので、そのときだけ凡例を出す
  const legend = styleLegend(list.some((s) => s && (s.focal || s.accent)) ? ['focal', 'plain'] : ['plain']);
  const legendH = kit.legendHeight(legend, W - M * 2);
  // 必要高 = 格子の上端 112 + 行数 × (箱 96 + 行間 72) - 行間 + 下余白 + 凡例
  const rowN = Math.ceil(list.length / Math.min(3, list.length));
  const H = CANVAS.height(112 + rowN * 96 + (rowN - 1) * 72 + M + legendH);
  const cols = Math.min(3, list.length);
  const cells = kit.gridLayout(list.length, kit.area(M, 112, W - M * 2, H - 112 - M - legendH), { cols, gapX: 96, gapY: 72 });
  const body = [];
  const boxOf = new Map();
  cells.forEach((cell, i) => {
    const box = { x: cell.x, y: cell.y, w: cell.w, h: Math.min(96, cell.h) };
    boxOf.set(nameOf(list[i]), box);
    body.push(node(box, list[i]));
  });
  // 辺ごとの本数を先に数える。状態遷移は 1 つの状態に複数の出入りが集まるため、
  // 数えずに辺の中央へ全部着けると線が重なって行き先が読めなくなる。
  const sideOf = (a, b, sameRow, end) => (end === 'from'
    ? (sameRow ? (b.x > a.x ? 'right' : 'left') : (b.y > a.y ? 'bottom' : 'top'))
    : (sameRow ? (b.x > a.x ? 'left' : 'right') : (b.y > a.y ? 'top' : 'bottom')));
  // 経路の種別を先に決める。行内で間の状態を跨ぐ遷移を直線で結ぶと、途中の箱を
  // 線が貫き「その状態を経由する」と誤読される。行の外の帯へ迂回させる。
  const allBoxes = [...boxOf.values()];
  const rowsY = [...new Set(allBoxes.map((b) => b.y))].sort((p, q) => p - q);
  const rowBottomOf = (y) => {
    const b = allBoxes.find((v) => Math.abs(v.y - y) < 4);
    return b ? b.y + b.h : y;
  };
  const bandOf = (y) => {
    const next = rowsY.find((v) => v > y + 4);
    return [rowBottomOf(y), next != null ? next : H - M - legendH];
  };
  const skipsABox = (a, b) => {
    const lo = Math.min(a.x + a.w, b.x + b.w);
    const hi = Math.max(a.x, b.x);
    return allBoxes.some((c) => c !== a && c !== b
      && Math.abs(c.y - a.y) < 4 && c.x >= lo - 0.5 && c.x + c.w <= hi + 0.5);
  };
  const plans = [];
  for (const t of trs) {
    const a = boxOf.get(t.from), b = boxOf.get(t.to);
    if (!a || !b) continue;
    if (a === b) { plans.push({ t, a, b, kind: 'self' }); continue; }
    const sameRow = Math.abs(a.y - b.y) < 4;
    if (sameRow && skipsABox(a, b)) {
      plans.push({ t, a, b, kind: 'detour', fromSide: 'bottom', toSide: 'bottom' });
      continue;
    }
    plans.push({
      t, a, b, kind: sameRow ? 'direct' : 'fold',
      fromSide: sideOf(a, b, sameRow, 'from'),
      toSide: sideOf(a, b, sameRow, 'to'),
    });
  }

  const useCount = new Map();
  const useSeen = new Map();
  const key = (name, side) => `${name}|${side}`;
  for (const p of plans) {
    if (p.kind === 'self') continue;
    for (const [name, side] of [[p.t.from, p.fromSide], [p.t.to, p.toSide]]) {
      const k = key(name, side);
      useCount.set(k, (useCount.get(k) || 0) + 1);
    }
  }
  const nextFan = (name, side) => {
    const k = key(name, side);
    const index = useSeen.get(k) || 0;
    useSeen.set(k, index + 1);
    return { index, count: useCount.get(k) || 1 };
  };

  for (const p of plans) {
    if (p.kind === 'self') continue;
    // 迂回の足は辺の中央を避ける。中央は上下段の連絡が使う位置なので、同じ列に
    // 並んだ箱どうしで縦の走りが同じ x に乗り、重なって本数が読めなくなる。
    const fan = (name, side) => {
      const f = nextFan(name, side);
      return p.kind === 'detour' ? { index: f.index, count: Math.max(2, f.count) } : f;
    };
    p.from = port(p.a, p.fromSide, fan(p.t.from, p.fromSide));
    p.to = port(p.b, p.toSide, fan(p.t.to, p.toSide));
  }

  // 行間の帯を使う経路 (行を跨ぐ折れ・行内の迂回) は、既定の中点で折れると
  // 全部が同じ高さで横走りし、重なった区間で 2 本が 1 本に見える。帯の中へ
  // 1 本ずつ車線を切る。横移動の長い線ほど行に近い車線に置き、交差を減らす。
  const banded = plans.filter((p) => p.kind === 'fold' || p.kind === 'detour');
  const byBand = new Map();
  banded.forEach((p) => {
    const k = Math.min(p.a.y, p.b.y);
    if (!byBand.has(k)) byBand.set(k, []);
    byBand.get(k).push(p);
  });
  byBand.forEach((group, k) => {
    const [top, bottom] = bandOf(k);
    const lanes = group.filter((p) => Math.abs(p.to.x - p.from.x) >= 0.5);
    lanes.sort((x, y) => Math.abs(y.to.x - y.from.x) - Math.abs(x.to.x - x.from.x));
    lanes.forEach((p, i) => {
      p.lane = top + Math.round(((bottom - top) * (i + 1)) / (lanes.length + 1) / 4) * 4;
    });
  });

  for (const p of plans) {
    const { t, a, b } = p;
    if (p.kind === 'self') {
      // 自己遷移: 箱の上辺へ半円を回す (斜め線を作らない)
      const x = a.x + a.w / 2, y = a.y;
      body.push(`<path d="M${kit.num(x - 20)},${kit.num(y)} A20,20 0 1 1 ${kit.num(x + 20)},${kit.num(y)}" fill="none" stroke="${T.muted}" stroke-width="${kit.STROKE.secondary}" marker-end="${kit.arrowUrl(T.muted)}"/>`);
      if (t.label) body.push(kit.arrowLabel(t.label, x, y - 22, { side: 'above' }));
      continue;
    }
    const sameRow = p.kind !== 'fold';
    if (p.kind === 'detour') {
      // 迂回は経路の都合であって遷移の種別ではない。以前はここだけ別トークンを
      // 当てていたが、**読者は色差を意味差として読む**ので「この遷移だけ別種」と
      // 誤って主張していた。迂回していることは経路の形が既に示している。
      const d = kit.detourPath(p.from.x, p.from.y, p.to.x, p.to.y, p.lane != null ? p.lane : bandOf(a.y)[0] + 24);
      body.push(`<path d="${d}" fill="none" stroke="${T.muted}" stroke-width="${kit.STROKE.secondary}" marker-end="${kit.arrowUrl(T.muted)}"/>`);
    } else {
      body.push(connector(p.from, p.to, {
        axis: sameRow ? 'h' : 'v', srcBox: a, dstBox: b, mid: p.lane,
      }));
    }
    // 契機ラベルは発ノードの直後 (anchor:'start')。遷移は 1 つの状態から複数出るので
    // 中点に置くと束の中央でラベル同士が重なり、どの契機がどの線かが読めなくなる。
    if (t.label) {
      const dir = p.kind === 'detour' ? 'down'
        : (sameRow ? (b.x > a.x ? 'right' : 'left') : (b.y > a.y ? 'down' : 'up'));
      body.push(kit.arrowLabel(t.label, p.from.x, p.from.y, {
        anchor: 'start', dir, side: sameRow && p.kind !== 'detour' ? 'above' : 'right',
        canvasW: W, canvasH: H,
      }));
    }
  }
  body.push(legendAt(legend, M, H - M / 2, W - M * 2));
  return frame(W, H, body.filter(Boolean).join('\n  '), { ...opts, className: 'state-svg' });
}

/* ------------------------------------------------------------------
 * 6. swimlane — lane × box × elbow
 * ---------------------------------------------------------------- */

/**
 * 置かれた升目のどれとどれを線で結ぶかを決める。**宣言された順序からしか引かない。**
 *
 * 以前の既定は `order` 未指定のとき位置の連番 (`レーン番号 × 工程数 + 列`) を
 * 順序として使っていた。すると order を一つも書いていない入力 — 表から起こした
 * レーン図や、edges を持つ svgSpec の投影 — に対して、図が
 * 「レーン 1 の全工程が終わってからレーン 2 が始まる」と主張してしまう。
 * 入力のどこにもそう書かれていないので、それは読者への嘘である。
 *
 * @param {Array} placed [{id, lane, step, order, box}]
 * @param {Array} links  opts.links。[{from, to, label, dashed}] を step の id で指す明示辺
 * @returns {Array<[number, number, string, boolean]>} placed の添字ペア + ラベル + 破線か
 */
function swimlanePairs(placed, links) {
  // (1) 明示辺。両端が解決できるものだけを引く (部分宣言はその部分だけが正しい)。
  if (Array.isArray(links) && links.length) {
    const byId = new Map();
    placed.forEach((p, i) => { if (p.id != null && !byId.has(p.id)) byId.set(p.id, i); });
    const out = [];
    links.forEach((l) => {
      if (!l) return;
      const a = byId.get(l.from), b = byId.get(l.to);
      if (a != null && b != null && a !== b) out.push([a, b, l.label || '', l.dashed === true]);
    });
    if (out.length) return out;
  }
  // (2) order の明示。書かれている升目だけを昇順に鎖へ繋ぐ。
  const ordered = placed
    .map((p, i) => ({ i, o: p.order }))
    .filter((x) => x.o != null)
    .sort((a, b) => a.o - b.o);
  if (ordered.length >= 2) {
    return ordered.slice(0, -1).map((x, k) => [x.i, ordered[k + 1].i]);
  }
  // (3) 宣言が何も無いとき。工程列 (step) は入力が持っている順序軸なので、
  //     同じレーンの中でだけ列の昇順に繋ぐ。レーンをまたぐ順序は入力に無い。
  //     レーン間の受け渡しを見せたいなら order か links を書くこと。
  const byLane = new Map();
  placed.forEach((p, i) => {
    if (!byLane.has(p.lane)) byLane.set(p.lane, []);
    byLane.get(p.lane).push({ i, step: p.step });
  });
  const out = [];
  [...byLane.keys()].sort((a, b) => a - b).forEach((k) => {
    const row = byLane.get(k).sort((a, b) => a.step - b.step);
    for (let j = 0; j < row.length - 1; j += 1) out.push([row[j].i, row[j + 1].i]);
  });
  return out;
}

/**
 * スイムレーン図。担当 (レーン) × 工程 (ステップ) の格子。
 * @param {Array} lanes [{ label, steps: [{id, label, step, order}] }] step は 0 始まりの列位置
 * @param {Object} opts opts.links = [{from, to}] で step の id を指す明示辺
 */
function buildSwimlane(lanes, opts = {}) {
  const list = (lanes || []).filter(Boolean).slice(0, CAP.buildSwimlane);
  if (!list.length) return base.emptyState(opts);
  // 工程列も上限を持たせる。従来は無制限で、列が増えるほど 1 マスが痩せて
  // 日本語ラベルが MIN_NODE_W (164px) を割り込み、fitText が最小フォントでも
  // 収まらず黙って行を落としていた。
  const stepCount = Math.min(SWIM_STEPS, Math.max(
    1,
    ...list.map((l) => ((l && l.steps) || []).reduce((mx, s, i) => Math.max(mx, (s && s.step != null ? s.step : i) + 1), 0))
  ));
  const W = CANVAS.w, M = 40;
  const laneH = 116;
  // 必要高 = 余白 40×2 + 工程見出し 24 + レーン数 × 116 + レーン間 12
  const H = CANVAS.height(M * 2 + 24 + list.length * laneH + (list.length - 1) * 12);
  const { lanes: laneBoxes, cells } = kit.laneLayout(list.length, stepCount, kit.area(M, M + 24, W - M * 2, H - M * 2 - 24), { headerW: 168, laneGap: 12, stepGap: 28 });
  const body = [];
  // 工程見出し
  for (let s = 0; s < stepCount; s++) {
    const c = cells.find((x) => x.step === s);
    if (!c) continue;
    const head = ((opts.stepLabels || [])[s]) || `工程${s + 1}`;
    body.push(bandLabel({ x: c.x, y: M - 4, w: c.w, h: 22 }, head));
  }
  const placed = [];
  laneBoxes.forEach((lane, li) => {
    body.push(`<rect x="${kit.num(lane.x)}" y="${kit.num(lane.y)}" width="${kit.num(lane.w)}" height="${kit.num(lane.h)}" fill="${li % 2 === 0 ? T.paper : T.paper2}" stroke="${T.rule}" stroke-width="${kit.STROKE.hairline}"/>`);
    body.push(bandLabel(lane.header, nameOf(list[li]), { maxFont: 15, fill: T.ink }));
    const steps = ((list[li] && list[li].steps) || []).slice(0, stepCount);
    steps.forEach((s, si) => {
      const col = s && s.step != null ? s.step : si;
      const cell = cells.find((c) => c.lane === li && c.step === col);
      if (!cell) return;
      const box = { x: cell.x + 8, y: cell.y + 16, w: cell.w - 16, h: cell.h - 32 };
      body.push(node(box, s, { maxFont: 15 }));
      placed.push({
        id: s && s.id != null ? s.id : null,
        lane: li, step: col,
        order: (s && s.order != null) ? s.order : null,
        box,
      });
    });
  });
  // 宣言された順序だけをコネクタにする (位置から順序を作らない)。
  // 同じ辺へ入る線と出る線を両方とも辺の中央へ着けると、レーンを往復する区間で
  // 2 本が同じ直線に乗り、行って戻ったことが 1 本に見える (受け渡しの回数が
  // 読めない)。辺ごとの本数を先に数え、辺上へ散らしてから引く。
  const links = swimlanePairs(placed, opts.links).map(([ai, bi, label, dashed]) => {
    const a = placed[ai].box, b = placed[bi].box;
    const sameLane = Math.abs(a.y - b.y) < 4;
    return {
      ai, bi, a, b, sameLane, label, dashed,
      fromSide: sameLane ? 'right' : (b.y > a.y ? 'bottom' : 'top'),
      toSide: sameLane ? 'left' : (b.y > a.y ? 'top' : 'bottom'),
    };
  });
  const sideKey = (idx, side) => `${idx}|${side}`;
  const sideCount = new Map();
  const sideSeen = new Map();
  links.forEach((l) => {
    for (const k of [sideKey(l.ai, l.fromSide), sideKey(l.bi, l.toSide)]) {
      sideCount.set(k, (sideCount.get(k) || 0) + 1);
    }
  });
  const fanOf = (k) => {
    const index = sideSeen.get(k) || 0;
    sideSeen.set(k, index + 1);
    return { index, count: sideCount.get(k) || 1 };
  };
  links.forEach((l) => {
    const from = port(l.a, l.fromSide, fanOf(sideKey(l.ai, l.fromSide)));
    const to = port(l.b, l.toSide, fanOf(sideKey(l.bi, l.toSide)));
    // 差戻し・再送のように「同じ向きの受け渡しではない」辺は、宣言があれば線種で
    // 分ける。ラベルだけに任せると、線を目で追う読者にはすべて同じ受け渡しに見える。
    // 推測はしない (位置から逆流を割り出さない)。宣言された辺だけを破線にする。
    body.push(connector(from, to, { axis: l.sameLane ? 'h' : 'v', srcBox: l.a, dstBox: l.b, dashed: l.dashed }));
    // 帯をまたぐ線には「何を渡したか」を載せる (契約 §2.4)。
    // 『渡した』だけでは、待ちが発生した理由も差し戻しの単位も読めない。
    // 同一レーン内は同じ担当の連続作業なので受け渡し物が無く、書かない。
    if (l.label && !l.sameLane) {
      const my = (from.y + to.y) / 2;
      body.push(kit.arrowLabel(l.label, (from.x + to.x) / 2, my, {
        side: 'above', maxWidth: Math.max(80, Math.abs(to.x - from.x) + l.a.w),
      }));
    }
  });
  return frame(W, H, body.filter(Boolean).join('\n  '), { ...opts, className: 'swimlane-svg' });
}

/* ------------------------------------------------------------------
 * 7. high-level — level × band × elbow
 * ---------------------------------------------------------------- */

/**
 * 全体像 (概観) 図。段ごとに任意個の要素を置き、段間を縦にひとつなぎにする。
 * @param {Array} levels [{ label, items: [...] }]
 */
function buildHighLevel(levels, opts = {}) {
  const list = (levels || []).filter(Boolean).slice(0, CAP.buildHighLevel);
  if (!list.length) return base.emptyState(opts);
  const W = CANVAS.w, M = 48;
  // 先頭段だけ focal なので 2 語彙 = 凡例が要る (契約 §1.2)
  const legend = styleLegend(['focal', 'plain']);
  const legendH = kit.legendHeight(legend, W - M * 2);
  // 必要高 = 余白 48×2 + 段数 × 箱 108 + 段間 48 + 凡例
  const H = CANVAS.height(M * 2 + list.length * 108 + (list.length - 1) * 48 + legendH);
  // 段内の要素も上限を持たせる。従来は無制限で、5 件を超えると 1 マスが
  // MIN_NODE_W (164px) を割り込み、日本語ラベルが最小フォントでも入らなくなる。
  // 入力の実件数と、画布に載る件数を別々に持つ。片方だけにすると、下の
  // 「上下の件数が一致する段」判定がクランプ後の値を比べてしまい、7 件の段と
  // 9 件の段がどちらも 4 になって「一致」と読まれる。存在しない 1:1 対応を
  // 4 本の線として断言することになる。
  const rawCounts = list.map((l) => ((l && l.items) || []).filter(Boolean).length);
  const counts = rawCounts.map((n) => Math.min(LEVEL_ITEMS, Math.max(1, n)));
  const rows = kit.levelLayout(counts, kit.area(M + 140, M, W - M * 2 - 140, H - M * 2 - legendH), { gapY: 48, gapX: 24 });
  const body = [];
  rows.forEach((row, li) => {
    // 段の見出しは左側の余白へ縦位置を合わせて置く
    body.push(bandLabel({ x: M, y: row[0].y, w: 124, h: row[0].h }, nameOf(list[li]) || `第${li + 1}層`, { maxFont: 14, fill: T.ink }));
    const items = ((list[li] && list[li].items) || []).filter(Boolean);
    const boxes = row.map((cell) => ({ x: cell.x, y: cell.y, w: cell.w, h: Math.min(108, cell.h) }));
    boxes.forEach((box, i) => body.push(node(box, items[i], { fallbackType: li === 0 ? 'focal' : 'plain' })));
    if (li >= rows.length - 1) return;
    const below = rows[li + 1].map((cell) => ({ x: cell.x, y: cell.y, w: cell.w, h: Math.min(108, cell.h) }));
    const belowNames = ((list[li + 1] && list[li + 1].items) || []).filter(Boolean).map((it) => nameOf(it));
    // 横走りは段間の空きの中央へ立てる。宛先の上辺で走らせると枠線と同一直線に
    // なり、線が枠へ溶けて消え、矢じりも横向きのまま辺へ刺さる。
    const rowBottom = boxes[0].y + boxes[0].h;
    const trunkY = Math.round((rowBottom + below[0].y) / 8) * 4;

    // 段間の帰属は「入力が宣言したときだけ」引く。items[i].to に次段の label か
    // 添字を書く。宣言が無いまま添字で代用すると、入力に無い依存を図が断言する。
    // 情報が欠ける欠陥より、無い情報を描く欠陥のほうが重い。
    const resolveRef = (ref) => {
      if (typeof ref === 'number') return (ref >= 0 && ref < below.length) ? ref : -1;
      const j = belowNames.indexOf(String(ref));
      return j < below.length ? j : -1;
    };
    const edges = [];
    let declared = false;
    boxes.forEach((box, i) => {
      const to = items[i] && items[i].to;
      const refs = Array.isArray(to) ? to : (to == null ? null : [to]);
      if (!refs || !refs.length) return;
      declared = true;
      refs.forEach((r) => { const j = resolveRef(r); if (j >= 0) edges.push([i, j]); });
    });
    // 慣行の成立条件は「入力の件数が一致し、かつどちらの段も切り詰められて
    // いない」こと。クランプ後の描画件数で比べると、溢れた段どうしが偶然
    // 同じ上限値に丸められただけで一致と判定される。
    const intact = rawCounts[li] <= LEVEL_ITEMS && rawCounts[li + 1] <= LEVEL_ITEMS;
    if (!declared && intact && rawCounts[li] === rawCounts[li + 1] && boxes.length === below.length) {
      // 件数が一致する段に限り「上下同位置が対応」という慣行が成立する
      boxes.forEach((_, i) => edges.push([i, i]));
      declared = true;
    }

    // 一部だけが to を宣言した段では、宣言された辺だけを引き、宣言の無い項目
    // には何も引かない。ここで残りへトランクを足すと、2 つの文法 (項目の帰属と
    // 段の帰属) が同じ段に同居して、線の意味が読者から確定できなくなる。
    // 「線が無い = 関係が無い」と読まれる危険は残るが、無い関係を描く危険より
    // 軽い。宣言を全項目へ揃えるのは入力側の責務である。

    if (!declared || !edges.length) {
      // 個々の帰属が宣言されていない。段が段に支えられているという段レベルの
      // 事実だけを 1 本のトランクで描き、項目ごとの依存先は主張しない。
      const last = boxes[boxes.length - 1];
      const trunkX = Math.round((boxes[0].x + last.x + last.w) / 2);
      const dsts = below.map((b, i) => port(b, 'top', { index: i, count: below.length }));
      kit.trunkPaths({ x: trunkX, y: rowBottom }, dsts, trunkX, trunkY).forEach((seg) => {
        // 幹には矢じりを付けない。付けると母線の途中に向きが生えて、
        // 「どこが終点か」が読めなくなる。終点は枝の先だけである。
        const marker = seg.arrow ? ` marker-end="${kit.arrowUrl(T.muted)}"` : '';
        body.push(`<path d="${seg.d}" fill="none" stroke="${T.muted}" stroke-width="${kit.STROKE.secondary}"${marker}/>`);
      });
      return;
    }

    // 同じ辺に複数本が着くと重なって本数が読めない。発側・着側とも辺上で散らす。
    const outTotal = boxes.map((_, i) => edges.filter((e) => e[0] === i).length);
    const inTotal = below.map((_, j) => edges.filter((e) => e[1] === j).length);
    const outSeen = boxes.map(() => 0);
    const inSeen = below.map(() => 0);
    const drawn = edges.map(([i, j]) => {
      const box = boxes[i], dst = below[j];
      return {
        box, dst,
        from: port(box, 'bottom', { index: outSeen[i]++, count: outTotal[i] }),
        to: port(dst, 'top', { index: inSeen[j]++, count: inTotal[j] }),
      };
    });
    // 横走りの高さを本数分の車線へ散らす。全部を中点で折ると、区間が重なった
    // 2 本が 1 本に見えて本数が読めない。長く走る線ほど発側に近い車線へ置くと
    // 交差が減る。真下へ落ちる線は折れないので車線を消費しない。
    const bends = drawn.filter((e) => Math.abs(e.to.x - e.from.x) >= 0.5);
    bends.sort((a, b) => Math.abs(b.to.x - b.from.x) - Math.abs(a.to.x - a.from.x));
    const gap = below[0].y - rowBottom;
    bends.forEach((e, k) => {
      e.mid = rowBottom + Math.round((gap * (k + 1)) / (bends.length + 1) / 4) * 4;
    });
    drawn.forEach((e) => {
      body.push(connector(e.from, e.to, {
        axis: 'v', color: T.muted, srcBox: e.box, dstBox: e.dst, mid: e.mid,
      }));
    });
  });
  body.push(legendAt(legend, M, H - M / 2, W - M * 2));
  return frame(W, H, body.filter(Boolean).join('\n  '), { ...opts, className: 'highlevel-svg' });
}

/* ------------------------------------------------------------------
 * 8. it-state — matrix × cell (現状 → 課題 → あるべき姿)
 * ---------------------------------------------------------------- */

/**
 * 現状 / 課題 / あるべき姿 の対比表。
 * @param {Array} rows [{ label, current, issue, target }]
 */
function buildItState(rows, opts = {}) {
  const list = (rows || []).filter(Boolean).slice(0, CAP.buildItState);
  if (!list.length) return base.emptyState(opts);
  const headers = opts.columns || ['現状', '課題', 'あるべき姿'];
  const W = CANVAS.w, M = 40, headerH = 40, headerW = 180;
  const rowH = 96;
  // 最終列だけ focal なので 2 語彙 = 凡例が要る (契約 §1.2)
  const legend = styleLegend(['plain', 'focal']);
  const legendH = kit.legendHeight(legend, W - M * 2);
  // 必要高 = 余白 40×2 + 列見出し 40 + 行数 × 96 + 行間 8 + 凡例
  const H = CANVAS.height(M * 2 + headerH + list.length * rowH + (list.length - 1) * 8 + legendH);
  const { cells, colHeaders, rowHeaders } = kit.matrixLayout(list.length, headers.length,
    kit.area(M, M, W - M * 2, H - M * 2 - legendH), { headerW, headerH, gap: 8 });
  const body = [];
  colHeaders.forEach((h, i) => body.push(bandLabel(h, headers[i], { maxFont: 15, fill: T.ink })));
  rowHeaders.forEach((h, i) => body.push(bandLabel(h, nameOf(list[i]), { maxFont: 14, fill: T.ink })));
  const keys = ['current', 'issue', 'target'];
  cells.forEach((cell) => {
    const r = list[cell.row];
    const key = keys[cell.col] || keys[keys.length - 1];
    // 列の値は「意味キー (current/issue/target)」でも「並び (cells/values/items)」でも渡せる。
    // 呼び出し側の書き方を 1 つに強制すると、素直に書いたデータが黙って空欄になる。
    const positional = (r && (r.cells || r.values || r.items)) || [];
    const value = r && (r[key] != null ? r[key] : positional[cell.col]);
    // あるべき姿の列だけ焦点扱いにして、視線の着地点をひとつに保つ
    const st = cell.col === headers.length - 1 ? kit.NODE_STYLES.focal : kit.NODE_STYLES.plain;
    body.push(kit.nodeRect(cell, st));
    body.push(fittedLines(nameOf(value) || String(value || ''), cell, {
      fill: T.ink, weight: 600, maxFont: 15, padX: 12, padY: 8,
    }));
  });
  body.push(legendAt(legend, M, H - M / 2, W - M * 2));
  return frame(W, H, body.filter(Boolean).join('\n  '), { ...opts, className: 'itstate-svg' });
}

/* ------------------------------------------------------------------
 * 9. medallion — column × band × 昇格円弧
 * ---------------------------------------------------------------- */

/**
 * メダリオン (段階的な品質向上) 図。層を横に並べ、層間に昇格の弧を描く。
 * @param {Array} tiers [{ label, sublabel, items: [...] }]
 */
function buildMedallion(tiers, opts = {}) {
  const list = (tiers || []).filter(Boolean).slice(0, CAP.buildMedallion);
  if (!list.length) return base.emptyState(opts);
  const W = CANVAS.w, M = 48;
  // 最終層だけ focal、層内の項目は store なので 3 語彙 = 凡例が要る (契約 §1.2)
  const legend = styleLegend(['plain', 'focal', 'store']);
  const legendH = kit.legendHeight(legend, W - M * 2);
  // 段の高さは中身から決める。固定 280px だと、名前と補足だけの層で箱の下 2/3 が
  // 空白になり「何か入るはずの欄が抜けている」ように見えてしまう。
  const maxItems = Math.min(MEDALLION_ITEMS, Math.max(0, ...list.map((t) => ((t && t.items) || []).filter(Boolean).length)));
  const hasSub = list.some((t) => subOf(t));
  const boxH = kit.snap(maxItems ? 92 + maxItems * 44 + 12 : (hasSub ? 96 : 64));
  // 必要高 = 弧の帯 120 + カード高 + 下余白 56 + 凡例
  const H = CANVAS.height(120 + boxH + 56 + legendH);
  const boxes = kit.rowLayout(list.length, kit.area(M, 120, W - M * 2, boxH), { gap: 76 });
  const body = [];
  boxes.forEach((b, i) => {
    const tier = list[i];
    const st = i === list.length - 1 ? kit.NODE_STYLES.focal : kit.NODE_STYLES.plain;
    body.push(kit.nodeRect(b, st));
    body.push(fittedLines(nameOf(tier), { x: b.x, y: b.y + 10, w: b.w, h: 40 }, { fill: T.ink, weight: 800, maxFont: 18, padX: 10, padY: 2 }));
    const sub = subOf(tier);
    if (sub) body.push(fittedLines(sub, { x: b.x, y: b.y + 50, w: b.w, h: 34 }, { fill: T.muted, weight: 500, maxFont: 12, minFont: kit.MIN_FONT_SMALL, padX: 10, padY: 2 }));
    const items = ((tier && tier.items) || []).filter(Boolean).slice(0, MEDALLION_ITEMS);
    if (items.length) {
      const inner = kit.columnLayout(items.length, kit.area(b.x + 12, b.y + 92, b.w - 24, b.h - 104), { gap: 8 });
      inner.forEach((ib, ii) => {
        body.push(kit.nodeRect(ib, kit.NODE_STYLES.store));
        body.push(fittedLines(nameOf(items[ii]), ib, { fill: T.ink, weight: 600, maxFont: 13, minFont: kit.MIN_FONT_SMALL, padX: 8, padY: 4 }));
      });
    }
    // 昇格の弧: 隣接カードの上辺どうしを結ぶ (層の中身を横切らない)。
    // 旧実装は「直線 + 円弧 + 直線」を右辺→左辺に貼っており、矢じりが左辺へ
    // 斜めに食い込んで向きが読めなかった。overArcPath は端点の接線が鉛直なので
    // 上辺へ正対して着地する (INCIDENCE_RULE.top を満たす)。
    if (i < boxes.length - 1) {
      const n = boxes[i + 1];
      // 帯の上端 = カード上端 - 弧の逃がし 60 (LABEL_GAP 8 の倍数。ラベル 2 行 +
      // 矢じりの張り出しが入る高さ)。kit 側で Math.max(0, …) にクランプされる
      const bandTop = b.y - 60;
      const x1 = b.x + b.w / 2, x2 = n.x + n.w / 2;
      body.push(`<path d="${kit.overArcPath(x1, b.y, x2, n.y, bandTop)}" fill="none" stroke="${T.muted}" stroke-width="${kit.STROKE.secondary}" marker-end="${kit.arrowUrl(T.muted)}"/>`);
      const via = (tier && tier.via) || '';
      // ラベルは弧の頂点の外側 (上)。頂点上に重ねると曲線と文字が交差する
      if (via) {
        const apex = kit.overArcApex(x1, b.y, x2, n.y, bandTop);
        body.push(kit.arrowLabel(via, apex.x, apex.y, { side: 'above', maxWidth: x2 - x1 - 24 }));
      }
    }
  });
  body.push(legendAt(legend, M, H - M / 2, W - M * 2));
  return frame(W, H, body.filter(Boolean).join('\n  '), { ...opts, className: 'medallion-svg' });
}

/* ------------------------------------------------------------------
 * 10. dp-integration — ring × box × radial (ハブ&スポーク統合)
 * ---------------------------------------------------------------- */

/**
 * 統合基盤図。中央のハブへ周辺システムが接続する構図。
 * @param {object|string} hub  中央 (統合基盤)
 * @param {Array} spokes [{ label, sublabel, direction: 'in'|'out'|'both' }]
 */
function buildDpIntegration(hub, spokes, opts = {}) {
  const list = (spokes || []).filter(Boolean).slice(0, CAP.buildDpIntegration);
  if (!list.length) return base.emptyState(opts);
  // ハブは focal、周辺は plain なので 2 語彙 = 凡例が要る (契約 §1.2)。
  // 加えて向き (受信 / 送信 / 双方向) をスポークの色と線種で分けているので、その語も出す。
  const W = CANVAS.w, M = 48;
  // 向きの見本は kind:'line' で描く。塗りの四角で出していたが、図の中で向きを
  // 運んでいるのは線なので、**凡例が図に無い符号 (色の面) を説明する**状態だった。
  // 出す項目は実際に使われている向きだけに絞る。使われていない向きを常に並べると、
  // 読者は図の中に無い線を探すことになる。逆に both を落とすと、破線のスポークが
  // 凡例に無い符号として残る。
  const dirsUsed = new Set(list.map((s) => (s && s.direction) || 'in'));
  const DIR_LEGEND = [
    { key: 'in', label: 'ハブへ入る', color: T.muted, kind: 'line' },
    { key: 'out', label: 'ハブから出る', color: T.link, kind: 'line' },
    { key: 'both', label: '双方向', color: T.muted, kind: 'dashed', dash: kit.DASH.fine },
  ];
  const legend = styleLegend(['focal', 'plain']).concat(
    DIR_LEGEND.filter((d) => dirsUsed.has(d.key)).map(({ key, ...it }) => it)
  );
  const legendH = kit.legendHeight(legend, W - M * 2);
  // 必要高 = リング直径 2R(536) + ノード高 72 + 上下の逃がし 20×2 + 凡例。
  // md 540 には入らないので lg 720 へ倒れる (536 + 72 + 40 + 凡例 ≒ 676)
  const H = CANVAS.height(2 * (120 + 94 + 20 + 36) + 72 + 40 + legendH);
  const cx = W / 2, cy = kit.snap((H - legendH) / 2);
  const nodeW = 188, nodeH = 72;
  const hubW = 240, hubH = 120;
  // リング半径は「最も窮屈な水平方向」から決める。ハブ半幅 + ノード半幅 + 両端の
  // 逃がし + 線として見える最低長 (36px) を確保しないと、左右のスポークが
  // 矢羽根だけになって流れの向きが読めなくなる。
  const R = hubW / 2 + nodeW / 2 + 20 + 36;
  const ring = kit.ringLayout(list.length, { cx, cy, radius: R, nodeW, nodeH });
  const body = [];
  const hubBox = { x: cx - hubW / 2, y: cy - hubH / 2, w: hubW, h: hubH };
  ring.forEach((p, i) => {
    const s = list[i];
    const box = { x: p.x, y: p.y, w: p.w, h: p.h };
    // スポーク: ハブ辺 → ノード辺の真の半径線 (斜め直線はこの型の明示的な例外)
    const ux = Math.cos(p.theta), uy = Math.sin(p.theta);
    const dHub = kit.boxRayDistance(ux, uy, hubW / 2, hubH / 2);
    const dNode = kit.boxRayDistance(ux, uy, nodeW / 2, nodeH / 2);
    // ハブ辺／ノード辺からの逃がし。矢羽根 (marker) は終点より手前に描かれるため、
    // ここが小さすぎると矢じりが箱の縁に貼りついて向きが読めなくなる。
    const gap = 10;
    const dir = (s && s.direction) || 'in';
    const inner = { x: cx + (dHub + gap) * ux, y: cy + (dHub + gap) * uy };
    const outer = { x: cx + (R - dNode - gap) * ux, y: cy + (R - dNode - gap) * uy };
    const color = dir === 'out' ? T.link : T.muted;
    const a = dir === 'out' ? inner : outer;
    const b = dir === 'out' ? outer : inner;
    body.push(`<line x1="${kit.num(a.x)}" y1="${kit.num(a.y)}" x2="${kit.num(b.x)}" y2="${kit.num(b.y)}" stroke="${color}" stroke-width="${kit.STROKE.secondary}"${dir === 'both' ? ` stroke-dasharray="${kit.DASH.fine}"` : ''} marker-end="${kit.arrowUrl(color)}"/>`);
    body.push(node(box, s, { maxFont: 15 }));
  });
  // ハブは最後に描いてスポークの微小なはみ出しを隠す
  body.push(kit.nodeRect(hubBox, kit.NODE_STYLES.focal));
  body.push(fittedLines(nameOf(hub) || '統合基盤', { x: hubBox.x, y: hubBox.y + 8, w: hubBox.w, h: 52 }, { fill: T.ink, weight: 800, maxFont: 20, padX: 12, padY: 4 }));
  const hubSub = subOf(hub);
  if (hubSub) body.push(fittedLines(hubSub, { x: hubBox.x, y: hubBox.y + 62, w: hubBox.w, h: 44 }, { fill: T.muted, weight: 500, maxFont: 13, minFont: kit.MIN_FONT_SMALL, padX: 12, padY: 4 }));
  body.push(legendAt(legend, M, H - M / 2, W - M * 2));
  return frame(W, H, body.filter(Boolean).join('\n  '), { ...opts, className: 'integration-svg' });
}

/**
 * 公開する 10 種はすべて base.guard を通す。
 * guard は「配列が全部空なら emptyState」「上限を超えた分は『ほか N 件』を隅に
 * 明記」を担う。入れ子 (ゾーン内ノード・レーン内工程など) は外側の件数だけでは
 * 数えられないので、数え方を知っているここから hidden コールバックで渡す。
 * 外側で既に捨てた要素の中身は二重に数えない (nestedOver は残った分だけを見る)。
 */
const RAW = {
  buildArchitecture,
  buildDataFlow,
  buildEr,
  buildSequence,
  buildState,
  buildSwimlane,
  buildHighLevel,
  buildItState,
  buildMedallion,
  buildDpIntegration,
};

const HIDDEN = {
  buildArchitecture: ([zones]) =>
    nestedOver((zones || []).filter(Boolean).slice(0, CAP.buildArchitecture), (z) => z && z.nodes, ARCH_NODES_PER_ZONE),
  buildEr: ([entities]) =>
    nestedOver((entities || []).filter(Boolean).slice(0, CAP.buildEr), (e) => e && e.fields, ER_FIELDS),
  buildSwimlane: ([lanes]) =>
    nestedOver((lanes || []).filter(Boolean).slice(0, CAP.buildSwimlane), (l) => l && l.steps, SWIM_STEPS),
  buildHighLevel: ([levels]) =>
    nestedOver((levels || []).filter(Boolean).slice(0, CAP.buildHighLevel), (l) => l && l.items, LEVEL_ITEMS),
  buildMedallion: ([tiers]) =>
    nestedOver((tiers || []).filter(Boolean).slice(0, CAP.buildMedallion), (t) => t && t.items, MEDALLION_ITEMS),
};

module.exports = Object.assign(
  Object.fromEntries(
    Object.entries(RAW).map(([k, fn]) => [k, base.guard(k, fn, HIDDEN[k] ? { hidden: HIDDEN[k] } : {})])
  ),
  {
    // 合成の部品も公開する (別の図解タイプを組む際の語彙)
    node,
    port,
    connector,
    frame,
    // 入れ子の上限も外から読めるようにする (上流の variant 選定が参照する)
    NESTED_CAPACITY: {
      buildArchitecture: ARCH_NODES_PER_ZONE,
      buildEr: ER_FIELDS,
      buildSwimlane: SWIM_STEPS,
      buildHighLevel: LEVEL_ITEMS,
      buildMedallion: MEDALLION_ITEMS,
    },
    MIN_NODE_W,
  },
);
