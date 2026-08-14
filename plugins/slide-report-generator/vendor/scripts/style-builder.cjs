/**
 * style-builder.js — SR-ID 駆動 CSS 動的生成
 *
 * 入力: spec-values（spec-registry.md から固定化した値オブジェクト）
 * 出力: styles.css 全文（pagination.css を結合）
 *
 * 単位は vw / rem / mm のみ（SR-1-04, px 禁止）。
 */
'use strict';

const fs = require('fs');
const path = require('path');

/**
 * fontScale の下限。frame-contract.json typography.min_font_scale と同じ値を持つ。
 *
 * --fs-* のうち --font-scale が掛かる書体で最も小さいのは --fs-small = calc(1.4rem * var(--font-scale))
 * なので、面に出る最小の書体は 1.4 * fontScale rem になる。これが契約の engine 下限
 * (typography.min_rem_engine = 1.5625rem) を割ってはいけないので
 *   1.4 * fontScale >= 1.5625  ->  fontScale >= 1.1160714...
 * となり、小数第 2 位へ切り上げて 1.12 を下限とする。
 *
 * 実測: fontScale 1.0 で deck を render して 4 観測点に --strict を掛けると、
 * 1920x1080 / 2560x1080 で --fs-small 系の面が 24.2px、--fs-body 系が 25.9px に解決して
 * 下限 27.0px を割り、1440x900 でも同様に割る。1280x1024 では 16.1px / 17.3px となり
 * 絶対下限 18px も割るため、fontScale 1.0 は今回の変更以前から 1280x1024 では違法だった。
 * 現行の既定値 1.3 および実デッキで使われている 1.2 / 1.5 はいずれもこの下限を満たす。
 */
const MIN_FONT_SCALE = 1.12;

/**
 * spec-registry.md の値を一元管理（SR-ID 対応コメント付き）
 */
const SPEC = {
  // §1 寸法・単位
  aspectRatio: '16 / 9', // SR-1-01
  aspectRatioNum: '16 / 9', // 同じ比を calc() の乗数として使う (SR-1-01)
  aspectRatioInvNum: '9 / 16', // その逆数。calc() は連続する除算を掛け算に畳めないため別に持つ
  printWidth: '297mm', // SR-1-03
  printHeight: '210mm',
  // §2 カラー（Lotus White デフォルト）— SR-2-01..09
  colors: {
    bgDark: '#fafafa',
    fg: '#43436c',
    fgDim: '#727169',
    waveBlue: '#7E9CD8',
    springViolet: '#957FB8',
    sakuraPink: '#D27E99',
    waveAqua: '#7FB4CA',
    autumnYellow: '#DCA561',
    fujiGray: '#727169',
    accentBlueVivid: '#3B7DD8', // SR-2-04
    accentPinkVivid: '#D94B6E',
    accentAquaVivid: '#2EA88F',
    accentVioletVivid: '#7B4FBA',
    accentYellowVivid: '#F5A623',
  },
  // §3 フォント — SR-3-02..03
  fontScale: 1.3,
  fonts: {
    base: "'Noto Sans JP', sans-serif",
    mono: "'SF Mono', 'Fira Code', monospace",
  },
  // §1-06 スペーシング
  spacing: ['0.25rem', '0.5rem', '0.75rem', '1rem', '1.5rem', '2rem', '3rem', '4rem', '6rem'],
  // §6 GSAP
  // §7 印刷
  // §8 ナビ
  navTopPadding: '4rem',
  navArrowPadding: '3rem',
  navBottomPadding: '5rem',
};

function buildRootVars(spec) {
  const c = spec.colors;
  return `:root {
  /* §1 単位・基準 */
  --aspect-ratio: ${spec.aspectRatio};

  /* 版面 (stage) の実寸。意匠は 16:9 で定義されている (canvas 1280x720、
     frame-contract の type_area_ratio 0.770 = 1152x616 / 1280x720) ので、
     画面の縦横比に追随させず常に 16:9 を保ち、余った方向へ帯を出す。
     min() 1 本なので上限・下限の分岐は無い。画面が横長なら幅が、縦長なら
     高さが律速する。build-deck-html.js の .slide-area と同じ作法。 */
  --stage-w: min(100vw, calc(100vh * ${spec.aspectRatioNum}));
  --stage-h: calc(var(--stage-w) * ${spec.aspectRatioInvNum});
  /* 版面内で使う長さの基準。--su は stage 幅の 1%、--sv は stage 高の 1%。
     16:9 の画面では stage = 画面なので、それぞれ 1vw / 1vh と完全に一致する。
     版面の中身はこの 2 つ (と rem) だけで書き、vw / vh を直接参照しない。
     そうして初めて stage 内部の見え方が全画面で同一になり、契約の
     type_area_ratio 0.770 や fill_policy 0.48-0.88 が「固定値」として成立する。 */
  --su: calc(var(--stage-w) / 100);
  --sv: calc(var(--stage-h) / 100);

  /* §2 Kanagawa Lotus パレット (SR-2-01..03) */
  --bg-dark: ${c.bgDark};
  --fg: ${c.fg};
  --fg-dim: ${c.fgDim};
  --wave-blue: ${c.waveBlue};
  --spring-violet: ${c.springViolet};
  --sakura-pink: ${c.sakuraPink};
  --wave-aqua: ${c.waveAqua};
  --autumn-yellow: ${c.autumnYellow};
  --fuji-gray: ${c.fujiGray};

  /* §2 ビビッドアクセント (SR-2-04) */
  --accent-blue-vivid: ${c.accentBlueVivid};
  --accent-pink-vivid: ${c.accentPinkVivid};
  --accent-aqua-vivid: ${c.accentAquaVivid};
  --accent-violet-vivid: ${c.accentVioletVivid};
  --accent-yellow-vivid: ${c.accentYellowVivid};

  /* §2-09 シャドウ */
  --shadow-subtle: 0 calc(0.2 * var(--sv)) calc(0.6 * var(--sv)) rgba(0,0,0,0.06);
  --shadow-medium: 0 calc(0.4 * var(--sv)) calc(1.2 * var(--sv)) rgba(0,0,0,0.10);
  --shadow-prominent: 0 calc(0.8 * var(--sv)) calc(2.4 * var(--sv)) rgba(0,0,0,0.16);
  --shadow-elevated: 0 calc(1.2 * var(--sv)) calc(3.6 * var(--sv)) rgba(0,0,0,0.22);
  --glow-blue: 0 0 calc(1.6 * var(--sv)) rgba(59,125,216,0.35);
  --glow-pink: 0 0 calc(1.6 * var(--sv)) rgba(217,75,110,0.35);
  --glow-aqua: 0 0 calc(1.6 * var(--sv)) rgba(46,168,143,0.35);

  /* §3 フォント (SR-3-01..03) */
  --font-scale: ${spec.fontScale};
  --font-base: ${spec.fonts.base};
  --font-mono: ${spec.fonts.mono};
  --fs-title: calc(5rem * var(--font-scale));
  --fs-subtitle: calc(2.5rem * var(--font-scale));
  --fs-heading: calc(3rem * var(--font-scale));
  --fs-subheading: calc(2rem * var(--font-scale));
  --fs-body-lg: calc(1.8rem * var(--font-scale));
  --fs-body: calc(1.5rem * var(--font-scale));
  --fs-small: calc(1.4rem * var(--font-scale));

  /* §1-06 spacing scale */
${spec.spacing.map((v, i) => `  --space-${i + 1}: ${v};`).join('\n')}

  /* §8 ナビ余白 */
  --nav-top-padding: ${spec.navTopPadding};
  --nav-arrow-padding: ${spec.navArrowPadding};
  --nav-bottom-padding: ${spec.navBottomPadding};
  /* 浮遊ページネーション UI が実際に占める領域。各値は下の .pg-* 定義と対で、
     ここを変えずに .pg-* の位置だけ動かすと本文が下に潜り込む。
       下: pg-controls (bottom 4vh + btn 5vh) と pg-dots (bottom 1.6vh + dot 域) の外側
       右: pg-controls (right 1.6vw + btn 5vh)
       上: pg-counter (top 1.6vh + 高さ) / pg-section-nav */
  --pg-reserve-bottom: calc(calc(4 * var(--sv)) + calc(5 * var(--sv)) + calc(1.2 * var(--sv)));
  --pg-reserve-side: calc(calc(1.6 * var(--su)) + calc(5 * var(--sv)) + calc(1.2 * var(--sv)));
  --pg-reserve-top: calc(calc(1.6 * var(--sv)) + calc(4.2 * var(--sv)) + calc(1.2 * var(--sv)));
}
`;
}

function buildBase() {
  return `
/* ===== Reset & Base ===== */
* { box-sizing: border-box; margin: 0; padding: 0; }
/* 根を 1vw だけで決めると、書体は幅に、面の高さ (100vh から --pg-reserve-* を
   引いた残り) は高さに連動するので、画面の縦横比が変わるたびに縦の予算だけが
   置いていかれる。実測で 1440x900 -> 1920x1080 は幅 1.333 倍に対し有効高が
   745 -> 893px の 1.198 倍しかなく、字だけが 11% 大きくなって外側余白を食い、
   1920 でだけ slide-title の h1 が溢れ slide4/6/7 の L9 が割れていた。
   根を stage の実寸に置くと、この不整合は原理的に消える。stage は常に 16:9 な
   ので幅と高さは連動して動き、字も入れ物も同じ倍率で拡縮する。画面 (vw / vh)
   ではなく版面を基準にする、というのが要点で、画面の縦横比が何であれ stage
   内部の見え方は変わらない。個別の面に px を足すのではなく、単位系の側で揃える。
   係数を stage 高さの 1.6% に取るのは、これが min(1vw, 1.6vh) が 16:9 の画面で
   選んでいた値そのもの (1920x1080 で 17.28px) だからで、既存の実測値を動かさずに
   基準だけを画面から版面へ移せる。16:9 では stage 幅の 0.9% にも等しい。 */
html, body { width: 100%; height: 100%; background: var(--bg-dark); color: var(--fg); font-family: var(--font-base); font-size: calc(1.6 * var(--sv)); line-height: 1.6; }

/* ===== 3層構造 (SR-4-01) ===== */
/* .slider は画面いっぱいの器で、その中央へ 16:9 の stage を置く。画面が
   16:9 でなければ余った方向に帯が出る (レターボックス / ピラーボックス)。
   PowerPoint / Keynote / Google Slides と同じ挙動で、意匠を画面の形へ
   作り直さない。帯は .slider の地色で、stage の外側なので L9 の外側余白
   (region = stage) には数えられない。 */
.slider { position: relative; width: 100vw; height: 100vh; overflow: hidden; display: flex; align-items: center; justify-content: center; }
.slide-area { position: relative; width: var(--stage-w); height: var(--stage-h); aspect-ratio: var(--aspect-ratio); margin: auto; }
.slider__container { position: relative; width: 100%; height: 100%; aspect-ratio: var(--aspect-ratio); }
.slider__item {
  position: absolute; inset: 0;
  width: 100%; height: 100%;
  /* SR-4-02。浮遊 UI (pg-controls / pg-dots / pg-counter) は position:fixed で
     vh・vw 指定、一方この逃げは rem 固定だった。単位系が違うため画面の縦横比が
     変わると必ずどこかで衝突し、実測では 1440x900 で送りボタンと図解が
     556px² 重なった。max() で「rem の意匠」と「浮遊 UI の占有域」の大きい方を
     取り、どの比率でも重ならないことを保証する。 */
  padding:
    max(var(--nav-top-padding), var(--pg-reserve-top))
    max(var(--nav-arrow-padding), var(--pg-reserve-side))
    max(var(--nav-bottom-padding), var(--pg-reserve-bottom));
  opacity: 0; visibility: hidden;
  display: flex; flex-direction: column;
  background: var(--bg-dark);
}
.slider__item.is-active { opacity: 1; visibility: visible; }
/* justify-content: center は伸長ではなく配置。内容高は一切変わらず、残余高さの
   置き場所だけが上下へ分かれる。既定の flex-start では残余が必ず下へ偏り、
   frame-contract.json vertical_margin_policy.max_symmetry_delta (0.02) を
   構造的に満たせない。しかも上詰めは内容量と無関係なので、CONST_008 が許す
   直し方 (面の統合・分割、項目の増減) では動かせず、規約内に解の無い検査に
   なってしまう。CONST_008 の「残余は群の外側余白として残す」を既定で満たす。
   fill_policy.note_antipattern が禁じる伸長 (flex: 1 1 0 /
   grid-auto-rows: 1fr / align-content: stretch) とは別物で、充填率は動かない。
   safe を付けるのは、内容が面より高い面 (fill_policy 上限超え) で素の center を
   使うと溢れが上下へ二分され、上側の溢れが chrome の予約帯 (pg-counter /
   pg-progress) へ食い込んで L1 衝突・L2 はみ出しを新たに作るため。safe は
   溢れているときだけ flex-start へ退避するので、収まっている面だけが中央寄せに
   なる。溢れ自体は L3 と fill_policy 上限で別途落とす。 */
.slider__content { width: 100%; height: 100%; display: flex; flex-direction: column; justify-content: safe center; gap: var(--space-4); }

/* ===== 共通見出し (SR-3-08) ===== */
.slider__item h1 { font-size: var(--fs-title); font-weight: 800; line-height: 1.2; }
.slider__item h2 { font-size: var(--fs-heading); font-weight: 700; line-height: 1.3; }
.slider__item h3 { font-size: var(--fs-subheading); font-weight: 600; line-height: 1.35; }
.slider__item p { font-size: var(--fs-body); }
.text-note { font-size: var(--fs-small); opacity: 0.7; -webkit-line-clamp: 3; line-clamp: 3; } /* SR-4-06, SR-9-04 */

/* ===== :focus-visible (SR-9-02) ===== */
:focus-visible { outline: calc(0.3 * var(--sv)) solid var(--accent-blue-vivid); outline-offset: calc(0.2 * var(--sv)); }

/* ===== sr-only ===== */
.sr-only { position: absolute; width: 1px; height: 1px; padding: 0; margin: -1px; overflow: hidden; clip: rect(0,0,0,0); white-space: nowrap; border: 0; }
`;
}

function buildSlideTypes() {
  return `
/* ===== slide-title ===== */
.slide-title { justify-content: center; align-items: center; text-align: center; }
/* slide-hero h1 と同じ理由。行送り 1.2 (.slider__item h1 の既定) はこの書体の
   字面 (実測で約 1.32em) より狭く、行ボックスから溢れる。1440x900 では丸めで
   隠れていたが 1920x1080 では 15px 露出した (根が 19.2px へ上がり字面も比例して
   伸びるのに対し、面の高さは 745->893 の 1.2 倍しか伸びないため)。章扉なので
   縦の余りは十分あり、字を小さくせず行送りを字面へ合わせる。 */
.slide-title h1 { font-size: var(--fs-title); margin-bottom: var(--space-4); line-height: 1.35; }
.slide-title .subtitle { font-size: var(--fs-subtitle); color: var(--accent-blue-vivid); }

/* ===== slide-message (SR-3-08) ===== */
.slide-message { justify-content: center; align-items: center; text-align: center; }
.slide-message h2 { font-size: var(--fs-heading); margin-bottom: var(--space-3); color: var(--accent-blue-vivid); }
.slide-message .main-message { font-size: var(--fs-subheading); }

/* ===== slide-list ===== v7.5.0: 視覚階層強化（icon色ローテ + 見出し/補足のサイズ差） */
.slide-list h2 { font-size: var(--fs-heading); margin-bottom: var(--space-4); }
.slide-list .list { display: flex; flex-direction: column; gap: var(--space-3); width: 100%; }
.slide-list .list-item {
  width: 100%; box-sizing: border-box; /* SR-4-05 */
  padding: var(--space-3) var(--space-4);
  border-left: calc(0.5 * var(--su)) solid var(--accent-blue-vivid);
  background: rgba(59,125,216,0.06);
  border-radius: calc(0.6 * var(--su));
  box-shadow: var(--shadow-subtle);
  font-size: var(--fs-body-lg);
  /* 段組みを縦から横へ変えている。縦だと i (Font Awesome) が 1 行を占有するが、
     アイコンは ::before の content なのでテキストノードが無く、L8-ink の走査に
     一切数えられない。つまり 1 項目あたり約 43px の「インクの無い高さ」が積まれ、
     4 項目で面が 47px 溢れて chrome 帯 (pg-controls) に食い込みつつ、面積比だけ
     90.6% に見えて中身は 14.5% という状態になっていた。横並びにすると同じ文字量が
     半分以下の高さに収まり、block が減って ink はそのままなので block_ink が上がる。
     desc の flex-basis を可変にしてあるので、幅が足りない面では従来どおり次の行へ
     折り返す (縮んで読めなくなるのではなく行が増える方へ倒す)。 */
  display: flex; flex-flow: row wrap; align-items: baseline;
  column-gap: var(--space-4); row-gap: calc(0.4 * var(--su));
  transition: box-shadow 0.18s ease, transform 0.18s ease;
}
.slide-list .list-item:hover { box-shadow: var(--shadow-prominent, var(--shadow-medium)); transform: translateY(calc(-0.1 * var(--su))); }
.slide-list .list-item > i { color: var(--accent-blue-vivid); font-size: var(--fs-subheading); flex: 0 0 auto; }
.slide-list .list-item:nth-child(5n+1) { border-left-color: var(--accent-blue-vivid); }
.slide-list .list-item:nth-child(5n+2) { border-left-color: var(--accent-aqua-vivid); }
.slide-list .list-item:nth-child(5n+3) { border-left-color: var(--accent-yellow-vivid); }
.slide-list .list-item:nth-child(5n+4) { border-left-color: var(--accent-pink-vivid); }
.slide-list .list-item:nth-child(5n+5) { border-left-color: var(--accent-violet-vivid); }
.slide-list .list-item:nth-child(5n+1) > i { color: var(--accent-blue-vivid); }
.slide-list .list-item:nth-child(5n+2) > i { color: var(--accent-aqua-vivid); }
.slide-list .list-item:nth-child(5n+3) > i { color: var(--accent-yellow-vivid); }
.slide-list .list-item:nth-child(5n+4) > i { color: var(--accent-pink-vivid); }
.slide-list .list-item:nth-child(5n+5) > i { color: var(--accent-violet-vivid); }
.slide-list .list-label { font-size: calc(2.8rem * var(--font-scale, 1)); font-weight: 800; color: var(--fg, #43436c); line-height: 1.35; flex: 0 0 auto; }
.slide-list .list-desc { font-size: var(--fs-subheading); font-weight: 500; color: var(--fg-muted, #54546d); line-height: 1.45; opacity: 0.92; flex: 1 1 20rem; }

/* ===== slide-compare (SR-4-03..04) ===== */
.slide-compare h2 { font-size: var(--fs-heading); margin-bottom: var(--space-4); }
.compare-container { display: flex; gap: 4%; width: 100%; }
.compare-panel { width: 48%; padding: var(--space-4); border-radius: calc(0.8 * var(--su)); box-shadow: var(--shadow-medium); }
.compare-panel--before { border-top: calc(0.6 * var(--su)) solid var(--accent-pink-vivid); background: rgba(217,75,110,0.05); }
.compare-panel--after { border-top: calc(0.6 * var(--su)) solid var(--accent-aqua-vivid); background: rgba(46,168,143,0.05); }
.compare-panel h3 { margin-bottom: var(--space-3); }

/* ===== slide-flow ===== */
.slide-flow h2 { font-size: var(--fs-heading); margin-bottom: var(--space-4); }
.flow-container { display: flex; align-items: center; gap: var(--space-3); width: 100%; flex-wrap: wrap; }
.flow-step { flex: 1; min-width: calc(14 * var(--su)); padding: var(--space-3); background: var(--accent-blue-vivid); color: #fff; border-radius: calc(0.6 * var(--su)); text-align: center; font-size: var(--fs-body); box-shadow: var(--shadow-medium); }
.flow-arrow { font-size: var(--fs-heading); color: var(--accent-blue-vivid); }

/* ===== slide-timeline ===== */
.slide-timeline h2 { font-size: var(--fs-heading); margin-bottom: var(--space-4); }
.timeline { position: relative; padding-left: var(--space-5); }
.timeline::before { content: ""; position: absolute; left: calc(0.6 * var(--su)); top: 0; bottom: 0; width: calc(0.2 * var(--su)); background: var(--accent-blue-vivid); }
/* 日付を上の行ではなく左の列へ出す。縦積みのままだと 1 項目が 3 行になり、
   行数ぶんの高さを使いきってしまうので書体を上げられず、実測で本文の字幅が
   135-571px しか無いのに矩形は 1261px 全幅を張る (面積比だけ 0.767 で高く出て、
   右半分は空) という状態になっていた。日付を列へ逃がして 1 行ぶん空けた高さを
   書体へ回すと、同じ高さのまま文字が横へ伸びて右の空きが埋まり、ink も増える。
   列の 1fr は横方向の配分で、fill_policy.note_antipattern が禁じる縦の伸長
   (grid-auto-rows: 1fr 等) とは別物。行は auto のままで内容が高さを決める。 */
.timeline-item {
  position: relative; padding-bottom: var(--space-4);
  display: grid;
  grid-template-columns: minmax(0, 14rem) minmax(0, 1fr);
  grid-template-rows: auto auto;
  column-gap: var(--space-4);
  align-items: baseline;
}
.timeline-item > .timeline-date { grid-column: 1; grid-row: 1 / 3; }
.timeline-item > .timeline-title,
.timeline-item > .timeline-desc { grid-column: 2; }
.timeline-item::before { content: ""; position: absolute; left: calc(-1.4 * var(--su)); top: calc(0.4 * var(--su)); width: calc(1.2 * var(--su)); height: calc(1.2 * var(--su)); border-radius: 50%; background: var(--accent-blue-vivid); }
/* 既定の行送り 1.6 (body) のままだと 4 件で群が 609px になり、面の上下に
   17px ずつしか残らない (L9 下限 12% 割れ)。行送りは ink に効かない
   (行矩形の高さは字面で決まる) ので、詰めた分はそのまま block だけが減り、
   外側余白が戻って block_ink も上がる。 */
.timeline-date { font-size: var(--fs-small); color: var(--accent-blue-vivid); font-weight: 700; line-height: 1.35; }
.timeline-title { font-size: calc(2.6rem * var(--font-scale, 1)); font-weight: 700; line-height: 1.35; }
.timeline-desc { font-size: calc(1.9rem * var(--font-scale, 1)); line-height: 1.45; }

/* ===== slide-table ===== v7.5.1: zebra/border強化 + Lotus調 */
.slide-table h2 { font-size: var(--fs-heading); margin-bottom: var(--space-4); }
.slide-table table {
  width: 100%; border-collapse: separate; border-spacing: 0;
  font-size: var(--fs-body);
  border: calc(0.1 * var(--su)) solid rgba(67,67,108,0.18);
  border-radius: calc(0.6 * var(--su)); overflow: hidden;
  box-shadow: var(--shadow-subtle);
  background: rgba(255,250,240,0.5);
}
.slide-table th, .slide-table td {
  padding: var(--space-2) var(--space-3); text-align: left;
  border-bottom: calc(0.1 * var(--su)) solid rgba(67,67,108,0.15);
  border-right: calc(0.1 * var(--su)) solid rgba(67,67,108,0.10);
  vertical-align: top;
  line-height: 1.5;
}
.slide-table th:last-child, .slide-table td:last-child { border-right: none; }
.slide-table tbody tr:last-child td { border-bottom: none; }
.slide-table th {
  background: var(--accent-blue-vivid); color: #fff; font-weight: 700;
  border-bottom: calc(0.15 * var(--su)) solid var(--accent-blue-vivid);
}
.slide-table tbody tr:nth-child(even) td {
  background: rgba(59,125,216,0.05);
}

/* ===== slide-code (SR-10-01..04) ===== */
.slide-code h2 { font-size: var(--fs-heading); margin-bottom: var(--space-3); }
/* 字も箱も面 (--su / --sv) で決める。箱の側だけ px だと、面が縮んだとき箱は縮まず
   字だけが小さくなり、同じコードでも見える行数が面ごとに変わる。実測 (--measure) で
   stage_fill が 1280x1024 0.775 / 1440x900 0.700 / 1920x1080 0.548 と割れていたのが
   これで、SR-1-04 の px 禁止にも反していた。1920x1080 の面 (--su 19.2px /
   --sv 10.8px) での実寸を保つ換算に置く。
     padding 上下   20px =  20 / 10.8 =  1.8519 --sv (縦なので --sv)
     padding 左右   24px =  24 / 19.2 =  1.25  --su (横なので --su)
     border-radius  12px =  12 / 19.2 =  0.625 --su
   縦を --sv、横を --su と軸で分けるのは、印刷 (297x210mm) では stage が 16:9 で
   なくなり 2 つの比が一致しなくなるため。画面側は常に 16:9 なのでどちらでも同じ。
   面単位にしても行が余計に切れることはない。字も箱も同じ --sv 由来で動くので、
   収まる行数はどの面でも一定になる (それがこの修正の目的)。

   max-height は 420px 相当 (38.889 --sv) をやめて 60 --sv に上げた。1920 の面で
   実測すると、内容枠 894.3px から h2 (87.6px)・その下余白 (12.96px)・行間
   (17.28px) を引いた残りは 776.5px = 71.9 --sv あるのに、420px の箱はその 54% しか
   使わず、コードが主役の面で 356px が常に空いたままだった。充填率も 10 行で 0.548 に
   頭打ちになり、fill_policy.exceptions.code の下限へ行数をいくら増やしても届かない。
   60 --sv はこの engine が pyramid / circle / cycle / diagram / chart / mermaid の
   主役要素へ既に使っている値で、コード面だけが例外だった。h2 が 2 行へ折り返しても
   (175.2px) 残りは 688.9px あるので 648px の箱は収まる。

   font-size 1.5625rem は typography.min の 18px を面座標で表した値
   (18 / 11.52 = 1.5625)。1.4rem では最小の観測点 1280x1024 で 16.1px となり
   typography.min を割っていた。--font-scale は掛けない (下の .code-panel pre も同じ。
   意図か事故かは未確認で、frame-contract.json の typography.note_font_scale_code に
   申し送りとして残してある)。 */
.code-block { max-height: calc(60 * var(--sv)); overflow-y: auto; font-family: var(--font-mono); font-size: 1.5625rem; line-height: 1.7; padding: calc(1.8519 * var(--sv)) calc(1.25 * var(--su)); border-radius: calc(0.625 * var(--su)); background: #1F1F28; color: #DCD7BA; }
.code-block .hl-header { color: var(--accent-blue-vivid); font-weight: 700; }
.code-block .hl-var { background: rgba(245,166,35,0.25); color: var(--accent-yellow-vivid); padding: 0 0.2em; border-radius: 0.2em; }

/* ===== slide-code-compare (SR-10-05..06) ===== */
.slide-code-compare h2 { font-size: var(--fs-heading); margin-bottom: var(--space-3); }
.code-compare { display: flex; gap: 4%; width: 100%; }
/* 上の .code-block と同じ理由で面単位にし、max-height も同じ 60 --sv へ揃える。
   280px 相当 (25.926 --sv) では、左右に並ぶパネルが使える縦 776.5px のうち 36% しか
   使わず、比較したい 2 つのコードがどちらも数行で切れていた。左右に並ぶぶん横幅は
   48% しかないので、縦は .code-block と同じだけ与えてよい。width 48% と gap 4% は
   無次元なのでそのままで面に追随する。 */
.code-panel { width: 48%; max-height: calc(60 * var(--sv)); overflow-y: auto; border-radius: calc(0.8 * var(--su)); box-shadow: var(--shadow-medium); }
.code-panel__header { padding: var(--space-2) var(--space-3); color: #fff; font-weight: 700; font-size: var(--fs-small); }
.code-panel--before .code-panel__header { background: var(--accent-pink-vivid); }
.code-panel--after .code-panel__header { background: var(--accent-aqua-vivid); }
.code-panel pre { margin: 0; padding: var(--space-3); font-family: var(--font-mono); font-size: 1.5625rem; line-height: 1.7; background: #1F1F28; color: #DCD7BA; }

/* ===== slide-pyramid ===== */
.slide-pyramid h2 { font-size: var(--fs-heading); margin-bottom: var(--space-4); }
.slide-pyramid .pyramid-svg { width: 100%; max-height: calc(60 * var(--sv)); }

/* ===== slide-circle ===== */
.slide-circle h2 { font-size: var(--fs-heading); margin-bottom: var(--space-4); }
.slide-circle .circle-svg { width: 100%; max-height: calc(60 * var(--sv)); }

/* ===== slide-grid ===== v7.5.0: アクセント上部ボーダー + アイコン色ローテ + ホバー */
.slide-grid h2 { font-size: var(--fs-heading); margin-bottom: var(--space-4); }
.grid-container { display: grid; grid-template-columns: repeat(var(--grid-cols, 3), 1fr); gap: var(--space-4); width: 100%; }
/* 既定は「2 段以上でも溢れない詰まった寸法」。1 段の面だけを data-rows="1" で
   拡大する (下の定義)。逆向き (既定を大きくして多段だけ縮める) にすると、
   段数の判定が届かなかったときに 2 段目が stage を溢れて error 側へ倒れるため。
   段数は render-slide.cjs が枚数と列数から確定させて data-rows へ出している。 */
.grid-cell {
  padding: var(--space-3) var(--space-5);
  background: rgba(255,250,240,0.7);
  border-radius: calc(0.6 * var(--su));
  box-shadow: var(--shadow-subtle);
  font-size: var(--fs-body-lg);
  border-left: calc(0.45 * var(--su)) solid var(--accent-blue-vivid);
  display: flex; flex-direction: column; gap: var(--space-2);
  transition: box-shadow 0.18s ease, transform 0.18s ease;
}
.grid-cell:hover { box-shadow: var(--shadow-prominent, var(--shadow-medium)); transform: translateY(calc(-0.15 * var(--su))); }
/* アイコンは Font Awesome の ::before なので DOM 上にテキストノードが無く、
   validate-slide-layout.js の ink 走査 (TreeWalker + Range の行ボックス) に
   一切数えられない。つまり大きくすると block (カード高) だけが伸びて ink は
   増えず、block_ink を押し下げる。面を埋めるためにここを大きくしてはいけない。
   増やす高さは行矩形が付いてくる側 (title / desc の font-size) へ寄せる。 */
.grid-cell > i { font-size: calc(1.8rem * var(--font-scale, 1)); color: var(--accent-blue-vivid); }
.grid-cell:nth-child(5n+1) { border-left-color: var(--accent-blue-vivid); }
.grid-cell:nth-child(5n+2) { border-left-color: var(--accent-aqua-vivid); }
.grid-cell:nth-child(5n+3) { border-left-color: var(--accent-yellow-vivid); }
.grid-cell:nth-child(5n+4) { border-left-color: var(--accent-pink-vivid); }
.grid-cell:nth-child(5n+5) { border-left-color: var(--accent-violet-vivid); }
.grid-cell:nth-child(5n+1) > i { color: var(--accent-blue-vivid); }
.grid-cell:nth-child(5n+2) > i { color: var(--accent-aqua-vivid); }
.grid-cell:nth-child(5n+3) > i { color: var(--accent-yellow-vivid); }
.grid-cell:nth-child(5n+4) > i { color: var(--accent-pink-vivid); }
.grid-cell:nth-child(5n+5) > i { color: var(--accent-violet-vivid); }
/* ink は Range.getClientRects() で採る。返る行矩形の高さは line-height ではなく
   書体の実寸で決まり、実測でも font-size の約 1.44 倍で一定だった
   (44.9px -> 65px / 48.7px -> 70px、line-height は 1.3 と 1.25 で別)。
   つまり line-height を広げても block (カード高) だけが伸びて ink は増えない。
   面を埋めるぶんは line-height ではなく font-size 側で取り、行間は詰めておく。 */
/* 折り返しが起きたときに最終行へ 1 文字だけ残る (「参加はこち」/「ら」) のを防ぐ。
   text-wrap: balance は行の最大幅を揃える方向で割るので 3 文字 / 3 文字になる。
   word-break: auto-phrase も試したが、文節ごとに割るため説明文が 4 行 (実測で
   217/217/217/326px) に散り、かえって行数と高さが増えたので入れていない。
   未対応環境では
   既定の折り返しに戻るだけで、寸法は下の font-size 側で 1 行に収まるよう
   取ってあるため、効かなくても溢れない。面積比と ink 比はこの見た目の破綻を
   検出できない (font-size を上げると block も ink も一緒に上がるため) ので、
   ここを触ったら数値ではなくスクリーンショットで確認すること。 */
.grid-cell-title { font-size: calc(2.4rem * var(--font-scale, 1)); font-weight: 800; color: var(--fg, #43436c); line-height: 1.2; text-wrap: balance; }
.grid-cell-desc { font-size: calc(2.1rem * var(--font-scale, 1)); font-weight: 500; color: var(--fg-muted, #54546d); line-height: 1.4; text-wrap: balance; }
/* 上の rem 値と下の data-rows="1" の値は「この面ならこれくらい」の設計値であって、
   文字列が入るかどうかは見ていない。設計値だけで決めると、セル幅が変わったときや
   文字列が長い面で熟語が割れる。実際 data-rows="1" の 3.3rem は 1 段の面を大きく
   見せる意図で入った値だが、--font-scale が掛かる形なので fontScale 1.3 の deck では
   74.13px に解決し、内寸 520px のセルに 8 文字が入らなくなっていた
   (2 段の面でも 10 文字の見出しが割れる)。
   そこで設計値は上限としてだけ使い、セル幅に入らなければ下げる。分母 --fit-t /
   --fit-d は面内で最も長い文字列の幅 (em) で、render-slide.cjs が出す。
   100cqi はセルの内寸そのもの (container-type: inline-size の inline 方向)。
   見出しは 100cqi (1 行に収める)、説明は 190cqi (2 行まで許す) で割る。見出しは
   語で読ませるものなので割れた時点で意味が壊れるが、説明は文なので 2 行に流れて
   正しい。1 行に収めようとして説明だけ極端に小さくすると、今度は面が空く
   (実測: 説明も 1 行に収める版では 1 段 3 枚の面で stage_fill が 0.40 まで落ちた。
   190cqi にすると 0.65 前後に戻り、見出しは 1 行のまま)。3 行以上は 190cqi の
   上限側で自動的に止まる。
   下限 1.5625rem は frame-contract.json の typography.min_rem_engine で、ここで
   独自の下限を決めない。下限に当たった文字列は縮まずに折り返す。
   1 行 1 項目へ倒した data-layout="stack" は見出し列が 31% で 100cqi と一致しない
   ため対象外。実測でも stack の面は旧エンジン・新エンジンのどちらでも全行 1 行に
   収まっており、直す対象が無い。
   ここを触ったら、行数が増えていないことを実描画の行矩形 (Range#getClientRects)
   で数えて確かめること。font-size と面積比は連動して動くので L8 では検出できない。 */
.grid-cell { container-type: inline-size; }
.grid-container:not([data-layout="stack"]) .grid-cell-title {
  font-size: clamp(1.5625rem, calc(100cqi / var(--fit-t, 8)), calc(2.4rem * var(--font-scale, 1)));
}
.grid-container:not([data-layout="stack"]) .grid-cell-desc {
  font-size: clamp(1.5625rem, calc(190cqi / var(--fit-d, 14)), calc(2.1rem * var(--font-scale, 1)));
}
/* 履歴 (次にここを触る人へ): この data-rows="1" ブロックは、書かれてから
   letterbox 対応の日まで一度も適用されたことがない。旧エンジンは grid の
   コンテナに data-rows 属性自体を出しておらず、セレクタが常に外れていた =
   実質の死にコードだった。letterbox で属性が出るようになって初めて表に出た
   結果、3.3rem は誰の目にも触れないまま fontScale 1.3 と掛かって 74.13px に
   解決し、見出しが折り返した (1 段の面 49.92 -> 74.13px = +48.5%、
   2 段の面 49.92 -> 53.91px = +8.0%)。
   つまり「letterbox が壊した」のではなく「letterbox が初めて実行させた」。
   下の rem 値は今も設計値であって検証値ではない。上の clamp で
   セル幅の上限に押さえてあるので折り返しは起きないが、rem を上げ下げした
   ときの見え方は誰も確かめていない前提で扱うこと。
   1 段しか無い面は、カードの高さがそのまま面の高さになるので、既定のままだと
   面の下半分が丸ごと空く (実測 stage_fill 0.31-0.37)。padding と書体を一段上げて
   中身ごと大きくする。grid-auto-rows: 1fr / align-content: stretch で面積だけ
   稼ぐと block_ink が落ちる (= fill_policy.note_antipattern の伸長) ので採らない。
   ここを触ったら stage_fill と block_ink が両方上がることを
   validate-slide-layout.js --measure で確認すること。
   左右の padding は上下と別に詰めてある。実測で 1 段のカードは内寸 369px、
   見出し 3.5rem は 1 文字 65.5px なので 6 文字 (393px) が入らず、「参加はこちら」が
   5 文字 + 1 文字に割れていた。左右を 1 段落として内寸を 383px まで戻し、
   見出しを 3.3rem (61.7px) にすると 6 文字 370px が 1 行に収まる。 */
.grid-container[data-rows="1"] .grid-cell { padding: var(--space-6) var(--space-4); gap: var(--space-3); }
.grid-container[data-rows="1"] .grid-cell > i { font-size: calc(2.4rem * var(--font-scale, 1)); }
.grid-container[data-rows="1"]:not([data-layout="stack"]) .grid-cell-title {
  font-size: clamp(1.5625rem, calc(100cqi / var(--fit-t, 8)), calc(3.3rem * var(--font-scale, 1)));
  line-height: 1.25;
}
.grid-container[data-rows="1"]:not([data-layout="stack"]) .grid-cell-desc {
  font-size: clamp(1.5625rem, calc(190cqi / var(--fit-d, 14)), calc(2.9rem * var(--font-scale, 1)));
  line-height: 1.45;
}
/* 説明が長い面を 1 行 1 項目へ倒す (structure の content.layout = "stack")。
   3 列のままだと 1 行あたり 10 字前後で折り返し、見出しまで語中で割れる
   (実測「データ整 / 理・分析」「企画・ネーミング・キ / ャッチコピー」)。
   横一列にすれば折返しが消え、視線も上から下の 1 方向で済む。 */
/* grid-template-columns: 1fr は列を 1 本にするだけで、行を残余まで引き伸ばす
   grid-auto-rows: 1fr / align-content: stretch とは別物。行高は中身で決まるので
   fill_policy.note_antipattern の「伸長で充填率を作る」には当たらない。 */
/* 長さはすべて rem で書く。版面では root font-size が calc(1.6 * var(--sv)) なので
   rem 自体が面の単位であり、vh を書くと画面比率で見え方が変わってしまう。 */
/* 行の高さは cards の枚数ぶんだけ積み上がるので、寸法は schema の上限 6 枚が
   入る側で取る。実測: 上下 padding 1.5rem / gap 2.8 --sv だと 5 枚で
   slider__content を 80px (1920x1080) 溢れて L3 の error になった。 */
.grid-container[data-layout="stack"] { grid-template-columns: 1fr; gap: clamp(0.9rem, calc(2.0 * var(--sv)), 2rem); align-content: center; }
/* 見出し列は 31%。26% では実測 430px しか取れず、8 字の見出し「データ整理・分析」
   (2.8rem x font-scale 1.3 = 1 字 63px で 504px) が語中で割れた。31% は 1920x1080 で
   534px なので 1 行に収まる。34% まで広げると今度は説明列が 953px に痩せ、18 字の
   「報告書・提案書・議事録の下書きを作成」(972px) が折り返した。31% はこの両側から
   挟んで決めた値で、上下いずれにも動かす余地はほぼ無い。 */
/* 下限を 0 にしてあるのは、見出しが短い面で列が痩せても desc 側が伸びるだけで
   崩れないから。列幅を % で書くのは、面 (16:9 のステージ) に対する割合であって
   画面比率では変わらないため。実測: 1920x1080 と 1280x1024 のどちらでも
   slide6 / slide7 の見出し・説明はすべて 1 行に収まる。 */
.grid-container[data-layout="stack"] .grid-cell {
  display: grid;
  grid-template-columns: 3.6rem minmax(0, 31%) 1fr;
  align-items: center;
  column-gap: 1.8rem;
  row-gap: 0;
  padding: 1.1rem 1.8rem;
  text-align: left;
}
.grid-container[data-layout="stack"] .grid-cell > i { font-size: calc(2.1rem * var(--font-scale, 1)); justify-self: center; }
.grid-container[data-layout="stack"] .grid-cell-title { line-height: 1.25; }
.grid-container[data-layout="stack"] .grid-cell-desc { margin: 0; }
/* 段数が少ない stack 面は縦に余る。既定の 2.4rem/2.1rem のままだと slide6 (3 段) で
   充填率 43.6% と L8 の下限 48% を割った (実測)。埋め方は padding ではなく字面で
   取る。padding は block だけを増やして ink を増やさないので block_ink を押し下げる
   (.grid-cell > i と同じ理由)。 */
/* data-rows で段数別に分けるのは、上の
   .grid-container[data-rows="1"] が 1 段の面を拡大しているのと同じ考え方。
   4 段以上は既定のままにする。5 段の slide7 は既定でも slider__content の
   高さぎりぎりで、ここを上げると L3 の溢れ側へ倒れるため。 */
/* 値は 2.8rem / 2.2rem で止めてある。ここから上げると充填率は下限を越えるが
   (実測 2.9rem / 2.3rem で warnings 24 まで戻る)、その分は見出しが 2 行に折り返して
   稼いだ ink であり、この rule が消そうとしている折返しそのものを呼び戻す。
   1 行を保てる最大が 2.8rem / 2.2rem で、そのとき slide6 の充填率は 47.3% と
   下限 48% を 0.7pt 割る。折返しを消す方を採り、warning 1 件 x 4 観測点は残す。 */
.grid-container[data-layout="stack"][data-rows="1"] .grid-cell-title,
.grid-container[data-layout="stack"][data-rows="2"] .grid-cell-title,
.grid-container[data-layout="stack"][data-rows="3"] .grid-cell-title { font-size: calc(2.8rem * var(--font-scale, 1)); }
.grid-container[data-layout="stack"][data-rows="1"] .grid-cell-desc,
.grid-container[data-layout="stack"][data-rows="2"] .grid-cell-desc,
.grid-container[data-layout="stack"][data-rows="3"] .grid-cell-desc { font-size: calc(2.2rem * var(--font-scale, 1)); }
/* slide-flow / slide-circle / slide-diagram-vs / slide-diagram-mindmap SVG を画面いっぱいに */
.slide-flow .slider__content,
.slide-diagram-cycle .slider__content,
.slide-diagram-vs .slider__content,
.slide-diagram-mindmap .slider__content { display: flex; flex-direction: column; }
.slide-flow svg,
.slide-diagram-cycle svg.cycle-svg,
.slide-diagram-vs svg.vs-svg,
.slide-diagram-mindmap svg { width: 100%; max-height: calc(70 * var(--sv)); height: auto; flex: 1; }

/* ===== slide-highlight ===== */
.slide-highlight { justify-content: center; align-items: center; text-align: center; }
.slide-highlight .highlight-num { font-size: calc(8rem * var(--font-scale)); font-weight: 900; color: var(--accent-yellow-vivid); }
.slide-highlight .highlight-label { font-size: var(--fs-subheading); }

/* ===== slide-icon-grid ===== */
.slide-icon-grid h2 { font-size: var(--fs-heading); margin-bottom: var(--space-4); }
.ig-container { display: grid; grid-template-columns: repeat(var(--ig-cols, 3), 1fr); gap: var(--space-3); width: 100%; }
.ig-item { width: 100%; box-sizing: border-box; padding: var(--space-3); text-align: center; background: rgba(59,125,216,0.05); border-radius: calc(0.8 * var(--su)); box-shadow: var(--shadow-subtle); }
.ig-icon { font-size: calc(3rem * var(--font-scale)); color: var(--accent-blue-vivid); margin-bottom: var(--space-2); }
.ig-label { font-size: var(--fs-body); font-weight: 700; }

/* ===== slide-process ===== */
.slide-process h2 { font-size: var(--fs-heading); margin-bottom: var(--space-4); }
.process-container { display: flex; flex-direction: column; gap: var(--space-3); }
.process-item { display: flex; align-items: center; gap: var(--space-3); padding: var(--space-3); background: rgba(59,125,216,0.05); border-radius: calc(0.6 * var(--su)); }
.process-num { width: calc(3 * var(--su)); height: calc(3 * var(--su)); border-radius: 50%; background: var(--accent-blue-vivid); color: #fff; display: flex; align-items: center; justify-content: center; font-weight: 900; font-size: var(--fs-body-lg); flex-shrink: 0; }

/* ===== slide-quote (SR-3-08) ===== */
.slide-quote { justify-content: center; align-items: center; text-align: center; }
.slide-quote h2 { font-size: var(--fs-heading); margin-bottom: var(--space-3); }
.slide-quote blockquote { font-size: var(--fs-subheading); font-style: italic; max-width: 80%; line-height: 1.5; }
.slide-quote cite { display: block; margin-top: var(--space-3); font-size: var(--fs-body); opacity: 0.7; }

/* ===== slide-hero ===== */
.slide-hero { justify-content: center; align-items: center; text-align: center; background: linear-gradient(135deg, var(--accent-blue-vivid), var(--accent-violet-vivid)); color: #fff; }
/* 行送り 1.2 (.slider__item h1 の既定) だと、この字面 (実測で約 1.32em) が
   行ボックスに収まらず 16px 溢れる。字を小さくするのではなく行送りを字面に
   合わせる (表紙なので縦の余りは十分ある)。 */
.slide-hero h1 { font-size: calc(7rem * var(--font-scale)); line-height: 1.35; }
.slide-hero .hero-sub { font-size: var(--fs-subtitle); opacity: 0.9; }

/* ===== slide-cycle (SR-3-08) ===== */
.slide-cycle h2 { font-size: var(--fs-heading); margin-bottom: var(--space-4); }
.slide-cycle .cycle-svg { width: 100%; max-height: calc(60 * var(--sv)); }

/* ===== diagram-* / chart-* / d3-* 共通 ===== */
.slide-diagram h2, .slide-chart h2, .slide-d3 h2 { font-size: var(--fs-heading); margin-bottom: var(--space-4); }
.slide-diagram svg, .slide-chart svg { width: 100%; max-height: calc(60 * var(--sv)); }
.slide-d3 .d3-mount { width: 100%; height: calc(60 * var(--sv)); }

/* ===== ビジュアルの縦寸は「残った空き」で決める (SR-4-02 の実効化) =====
   上の 60vh / 70vh は見出しの行数を知らない固定値で、h2 が 2 行になると
   nav-top(4rem) + 見出し + 60vh + nav-bottom(5rem) が 100vh を超え、
   あふれた図解がページネーション帯へせり出す。ここで残余割当に上書きする。

   セレクタを [class*=] にしているのは、.slide-diagram が完全一致であり
   slide-diagram-architecture のような派生タイプに 1 つも効かないため。 */
.slider__item[class*="slide-diagram"] > .slider__content > svg,
.slider__item[class*="slide-chart"] > .slider__content > svg,
.slider__item[class*="slide-flow"] > .slider__content > svg,
.slider__item[class*="slide-cycle"] > .slider__content > svg,
.slider__item[class*="slide-pyramid"] > .slider__content > svg,
.slider__item[class*="slide-circle"] > .slider__content > svg {
  /* 伸びない・縮むだけ。旧値 flex: 1 1 auto は grow が 1 で、図が残余の高さを
     必ず食い切るため群の外側余白が構造的に 0 になっていた (実測 slide-circle の
     L9 が上 0px / 下 0px)。fill_policy.note_antipattern が禁じる伸長そのもので、
     しかも充填率は図の実寸でなく枠の消費で稼がれる。縮む側 (shrink) は残余に
     収めるために要るので残す。 */
  flex: 0 1 auto;
  /* flex item の既定 min-height:auto は「内容より小さくならない」を意味し、
     これがある限り max-height を書いても縮まずにはみ出す。0 にして初めて
     残余に収まる。この 1 行が実際の効き所。 */
  min-height: 0;
  /* 旧値 100% は「残余いっぱい」で、上の grow と対で外側余白を 0 にしていた。
     60vh は .slide-circle / .slide-pyramid 側の既定と同じ値で、見出しと合わせて
     群が面の 86% に収まる (実測 1440x900・1920x1080 とも外側余白 13.9%)。
     残余が 60vh より狭い面では 100% 側が選ばれて溢れを防ぐ。 */
  max-height: min(100%, calc(60 * var(--sv)));
  width: 100%;
  height: auto;
  /* SVG 自身のアスペクト比を保ったまま残余の中央へ置く */
  object-fit: contain;
}
/* d3 のマウント先も同様に残余へ従わせる (60vh 固定を上書き) */
.slider__item[class*="slide-d3"] > .slider__content > .d3-mount {
  flex: 1 1 auto; min-height: 0; height: auto;
}
/* 見出しと本文は縮まない側に固定する。これが無いと flex が見出しを潰し、
   「図解は収まったが見出しが読めない」という逆の破綻になる。 */
.slider__content > h1,
.slider__content > h2,
.slider__content > h3,
.slider__content > .slide-lead { flex: 0 0 auto; }

/* ===== foreignObject card (SR-6-04) ===== */
.fo-card { width: 100%; height: 100%; display: flex; flex-direction: column; align-items: center; justify-content: center; padding: calc(0.8 * var(--su)); box-sizing: border-box; font-family: var(--font-base); }
.fo-card--row { flex-direction: row; }
`;
}

function buildPrint() {
  return `
/* ===== §7 印刷 (SR-7-01..10) ===== */
@page { size: A4 landscape; margin: 0; }
@media print {
  * { -webkit-print-color-adjust: exact !important; print-color-adjust: exact !important; box-shadow: none !important; }
  /* グラデ文字(background-clip:text)は印刷で塗りつぶし矩形になり読めなくなるため通常色に戻す */
  .gradient-text,
  [style*="-webkit-background-clip: text"], [style*="background-clip: text"] {
    background: none !important;
    -webkit-background-clip: border-box !important; background-clip: border-box !important;
    -webkit-text-fill-color: var(--accent-primary, #1F6FEB) !important; color: var(--accent-primary, #1F6FEB) !important;
  }
  /* SR-7-09 Chrome 拡張・外部 UI 非表示（slider 直系のみ表示） */
  body > *:not(.slider):not(script):not(style) { display: none !important; visibility: hidden !important; width: 0 !important; height: 0 !important; overflow: hidden !important; }
  /* 印刷の版面は 297x210mm の full-bleed (SR-1-03)。画面側の 16:9 レターボックス
     はここでは効かせず、stage の実寸を紙面へ差し替える。--su は 2.97mm、--sv は
     2.1mm となり、これは変更前の 1vw / 1vh と同値なので印刷結果は動かない。
     font-size は上書きしない (validate-print P05)。 */
  :root { --stage-w: 297mm; --stage-h: 210mm; }
  html, body { width: 297mm; height: auto; background: #fff; }
  /* 画面では stage を中央へ置くために flex にしているが、印刷では面が縦に
     連なるので block へ戻す (flex のままだと面が横一列に並ぶ)。 */
  .slider { width: 297mm; height: auto; overflow: visible; display: block; }
  .slide-area, .slider__container { width: 297mm; height: 210mm; }
  /* SR-7-08 スライド番号動的化（attr(data-total) を使用） */
  .slider__item { counter-increment: slide-num; }
  .slider__item::after { content: counter(slide-num) " / " attr(data-total); }
  .slider__item {
    position: relative; inset: auto;
    width: 297mm; height: 210mm; min-height: 210mm; max-height: 210mm; /* SR-1-03, SR-7-02 */
    border: none; margin: 0; padding: 8mm; /* SR-7-03 / SR-7-11 印刷パディング */
    page-break-after: always; break-after: page;
    opacity: 1 !important; visibility: visible !important;
    box-shadow: none !important; /* SR-7-10 */
    isolation: isolate; /* SR-7-08 印刷時 z-index 競合回避 */
  }
  /* 最終面だけ強制改ページを外す。.slider-footer は position: absolute で下端が
     794px になり、印刷ページ高 793.688px を 0.3px 超える。最終面の break-after: page
     と合わさると、その 0.3px のために content stream 93 バイトの空白ページが 1 枚
     増える (面数 16 のデッキが 17 ページになる)。footer を印刷で隠せば消えるが、
     footer は紙面にも要るので改ページ側を外す。
     .slide-area { overflow: hidden } で切ってはいけない。祖先が clip すると子孫の
     page-break-after が効かなくなり、全面が 2 ページに潰れる。 */
  .slider__item:last-child { page-break-after: auto; break-after: auto; }
  /* SR-7-04 GSAP リセット */
  .slider__content, .slider__content > *, .slider__content * {
    visibility: visible !important;
    opacity: 1 !important;
    transform: none !important;
  }
  /* SR-7-05 ナビ非表示 */
  .pg-progress, .pg-controls, .pg-counter, .pg-dots, .pg-section-nav,
  .progress-bar, .navigation, .slide-counter, .dot-pagination, .agenda-indicator {
    display: none !important;
  }
  /* SR-7-07 hidden slides */
  [data-hidden="true"] { display: none !important; height: 0 !important; }
}

/* ===== §9 prefers-reduced-motion (SR-9-03) ===== */
@media (prefers-reduced-motion: reduce) {
  *, *::before, *::after {
    animation-duration: 0.01ms !important;
    transition-duration: 0.01ms !important;
  }
}
`;
}

/**
 * メイン: spec + pagination.css 結合 → styles.css 全文
 */
function buildStyles({ specOverride = {}, paginationCssPath } = {}) {
  const spec = { ...SPEC, ...specOverride, colors: { ...SPEC.colors, ...(specOverride.colors || {}) } };
  // fontScale の下限を fail-closed で守る。下回る値を通すと --fs-small / --fs-body が
  // typography.min_rem_engine を割る CSS を生成してしまい、後段の layout 検証でしか気付けない。
  const fsNum = Number(spec.fontScale);
  if (!Number.isFinite(fsNum) || fsNum < MIN_FONT_SCALE) {
    throw new Error(
      `[style-builder] fontScale=${spec.fontScale} は下限 ${MIN_FONT_SCALE} を下回る。` +
        `--fs-small = calc(1.4rem * fontScale) が typography.min_rem_engine (1.5625rem) を割るため CSS を生成しない。`
    );
  }
  let paginationCss = '';
  if (paginationCssPath && fs.existsSync(paginationCssPath)) {
    paginationCss = fs.readFileSync(paginationCssPath, 'utf8');
  }
  return [
    '/* ===================================================================',
    '   styles.css — render-slide.js 自動生成 (spec-registry.md SR-ID 駆動)',
    '   単位: vw / rem / mm のみ (SR-1-04)。px は禁止。',
    '   ===================================================================*/',
    buildRootVars(spec),
    buildBase(),
    buildSlideTypes(),
    buildPrint(),
    buildV8Layer(),
    '/* ===== pagination.css 結合 ===== */',
    paginationCss,
  ].join('\n');
}

// v8.0.0: schemaVersion=8.0.0 のときに render-slide.cjs が付与する
// data-* / CSS 変数を解釈するスタイル層 (SR-V8-COLOR / SR-V8-PAGE / SR-V8-COVER)
function buildV8Layer() {
  return `
/* ===== v8.0.0 拡張レイヤ (schemaVersion=8.0.0 のみ作動) ===== */

/* per-slide CSS 変数フォールバック (SR-V8-COLOR) */
.slider__item { --accent-primary: var(--accent-blue-vivid); --accent-secondary: var(--accent-aqua-vivid); --accent-pagination: var(--accent-primary); }

/* 背景バリアント (SR-V8-PAGE) */
.slider__item[data-bg="default"] { background: var(--bg-dark); }
.slider__item[data-bg="tint"]    { background: linear-gradient(135deg, rgba(255,255,255,0) 0%, color-mix(in srgb, var(--accent-primary) 8%, transparent) 100%), var(--bg-dark); }
.slider__item[data-bg="gradient"]{ background: linear-gradient(135deg, color-mix(in srgb, var(--accent-primary) 18%, var(--bg-dark)) 0%, var(--bg-dark) 60%, color-mix(in srgb, var(--accent-secondary) 14%, var(--bg-dark)) 100%); }
.slider__item[data-bg="dark"]    { background: #1F1F28; color: #DCD7BA; }
.slider__item[data-bg="dark"] h2,
.slider__item[data-bg="dark"] h3 { color: var(--accent-primary); }
.slider__item[data-bg="image"]   { background: var(--bg-image, none) center/cover no-repeat, var(--bg-dark); }

/* per-slide ナビ非表示 (例: 表紙) */
.slider[data-pg-style] .slider__item[data-pg-hide="true"] ~ * { /* placeholder */ }
.slider__item[data-pg-hide="true"] + .pg-controls,
.slider__item.is-active[data-pg-hide="true"] ~ .pg-section-nav,
.slider__item.is-active[data-pg-hide="true"] ~ .pg-dots { opacity: 0; pointer-events: none; }

/* ヘッダ・フッタ (SR-V8-PAGE) */
.slider-header { position: absolute; top: 0; left: 0; right: 0; height: calc(3 * var(--sv)); padding: 0 calc(2 * var(--su)); display: flex; align-items: center; gap: calc(1 * var(--su)); font-size: var(--fs-small); color: var(--fg); opacity: 0.7; z-index: 5; }
.slider-header__logo { color: var(--accent-blue-vivid); }
.slider-header__event { margin-left: auto; }
.slider-footer { position: absolute; bottom: 0; left: 0; right: 0; height: calc(2.6 * var(--sv)); padding: 0 calc(2 * var(--su)); display: flex; align-items: center; justify-content: space-between; font-size: var(--fs-small); color: var(--fg); opacity: 0.6; z-index: 5; }
.slider-footer__center { text-align: center; flex: 1; }

/* ページネーションスタイル切替 (SR-V8-PAGE) */
.slider[data-pg-style="none"] .pg-controls,
.slider[data-pg-style="none"] .pg-dots,
.slider[data-pg-style="none"] .pg-section-nav { display: none; }
.slider[data-pg-style="numeric"] .pg-dots { display: none; }
.slider[data-pg-style="bar"] .pg-dots { display: none; }
.slider[data-pg-style="section-dots"] .pg-dots { display: none; }

/* cover variant (SR-V8-COVER) — テンプレ未対応時のフォールバック表示 */
.slider__item[data-v8-cover="hero-icon"] .slider__content,
.slider__item[data-v8-cover="hero-image"] .slider__content,
.slider__item[data-v8-cover="centered-large"] .slider__content { text-align: center; }
.slider__item[data-v8-cover] h1 { color: var(--accent-primary); }

/* index variant (SR-V8-INDEX) */
.slider__item[data-v8-index="stepper"] .list-item { counter-increment: v8step; position: relative; padding-left: calc(4 * var(--su)); }
.slider__item[data-v8-index="stepper"] .list-item::before { content: counter(v8step); position: absolute; left: calc(1 * var(--su)); top: 50%; transform: translateY(-50%); width: calc(2.4 * var(--su)); height: calc(2.4 * var(--su)); border-radius: 50%; background: var(--accent-primary); color: var(--bg-dark); display: flex; align-items: center; justify-content: center; font-weight: 700; }

/* diagram マーカー (SR-V8-DIAGRAM) — 共通枠 */
.slider__item[data-v8-diagram] .diagram-legend { display: flex; flex-wrap: wrap; gap: calc(1 * var(--su)); justify-content: center; margin-top: calc(1 * var(--su)); font-size: var(--fs-small); }
.slider__item[data-v8-diagram] .diagram-legend__item { display: inline-flex; align-items: center; gap: calc(0.4 * var(--su)); }
.slider__item[data-v8-diagram] .diagram-legend__dot { width: calc(0.8 * var(--su)); height: calc(0.8 * var(--su)); border-radius: 50%; }
.slider__item[data-v8-diagram] .diagram-annotation { display: inline-flex; align-items: center; gap: calc(0.4 * var(--su)); padding: calc(0.4 * var(--su)) calc(0.8 * var(--su)); border-radius: calc(0.4 * var(--su)); font-size: var(--fs-small); margin-top: calc(1 * var(--su)); background: color-mix(in srgb, var(--accent-primary) 12%, transparent); }
.slider__item[data-v8-diagram] .diagram-annotation--warning { background: color-mix(in srgb, var(--accent-pink-vivid) 18%, transparent); }
.slider__item[data-v8-diagram] .diagram-annotation--tip { background: color-mix(in srgb, var(--accent-yellow-vivid) 18%, transparent); }
`;
}

module.exports = { buildStyles, SPEC, buildV8Layer };
