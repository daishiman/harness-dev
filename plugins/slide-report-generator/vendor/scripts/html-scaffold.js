#!/usr/bin/env node
/**
 * HTMLスケルトン生成スクリプト
 *
 * structure.md（構成案）からHTMLの骨組みを自動生成:
 * - スライドタイプに応じたHTML構造
 * - Kanagawa CSS変数・GSAPアニメーション設定
 * - ナビゲーション・印刷対応CSS
 *
 * 使用方法:
 *   node scripts/html-scaffold.js <structure-json-or-md> [output-path]
 *
 * オプション:
 *   --stdout  標準出力に出力（ファイル出力なし）
 *   --help    ヘルプを表示
 *
 * 例:
 *   node scripts/html-scaffold.js ./structure.json ./index.html
 *   node scripts/html-scaffold.js ./structure.md --stdout
 *   echo '{"title":"Test","slides":[...]}' | node scripts/html-scaffold.js
 */

import { readFileSync, writeFileSync, existsSync } from 'fs';
import { dirname, join, basename } from 'path';
import { parseArgs, hasFlag, EXIT_CODES, VALID_SLIDE_TYPES, isValidSlideType } from './utils.js';
// 配色の正本は style-builder の SPEC.colors だけにする。ここに色値を書くと、
// render-slide 経路と scaffold 経路で別々の配色が育ち、どちらも「動く」ので気付けない。
import styleBuilder from './style-builder.cjs';

const { SPEC } = styleBuilder;

/**
 * 角丸 (VGCONST_003: 面は 0px・図版のみ 2px) を style-builder が実際に出す CSS から
 * 実行時に採る。ここへ値を書き写すと正本が 2 つになり、片方だけ直しても骨格は
 * 出力できてしまう。採れないときは即座に落とす。
 */
const RADIUS = (() => {
  const css = styleBuilder.buildStyles();
  const pick = (name) => {
    const m = css.match(new RegExp('--' + name + ':\\s*([^;]+);'));
    if (!m) throw new Error(`style-builder の出力に --${name} が無い (角丸の正本が動いた)`);
    return m[1].trim();
  };
  return { surface: pick('radius'), figure: pick('radius-figure') };
})();

/**
 * Before/After の比率 (SR-4-03: 48% / 4% / 48%) を style-builder が実際に出す CSS
 * から実行時に採る。RADIUS と同じ理由で、ここへ 48% / 4% を書き写すと同じ規則に
 * 対する定義点が 2 つできる。決定論経路だけ直しても骨格経路は古い比率で出力できて
 * しまい、しかも見た目にしか出ないので誰も気付けない。採れないときは即座に落とす。
 *
 * 決定論経路の class 名は .compare-panel、骨格経路は .compare-item で異なるが、
 * 規則が定めているのは比率であって class 名ではないので値だけを借りる。
 */
const COMPARE = (() => {
  const css = styleBuilder.buildStyles();
  const pick = (selector, prop) => {
    const block = css.match(new RegExp('\\' + selector + '\\s*\\{[^}]*\\}'));
    if (!block) throw new Error(`style-builder の出力に ${selector} が無い (Before/After 比率の正本が動いた)`);
    const m = block[0].match(new RegExp(prop + ':\\s*([^;}]+)'));
    if (!m) throw new Error(`style-builder の ${selector} に ${prop} が無い (Before/After 比率の正本が動いた)`);
    return m[1].trim();
  };
  return { gap: pick('.compare-container', 'gap'), panel: pick('.compare-panel', 'width') };
})();

// コマンドライン引数
const { flags, positional } = parseArgs();

const showHelp = hasFlag(flags, 'help', 'h');
const stdoutMode = hasFlag(flags, 'stdout');
const inputPath = positional[0];
const outputPath = positional[1] || (inputPath ? join(dirname(inputPath), 'index.html') : null);

// ヘルプ表示
if (showHelp) {
  console.log(`
HTMLスケルトン生成スクリプト

使用方法:
  node html-scaffold.js <structure-json-or-md> [output-path]
  echo '<json>' | node html-scaffold.js [output-path]

引数:
  <structure-json-or-md>  構成案ファイル（JSON/MD）または標準入力
  [output-path]           出力HTMLパス（省略時: 入力ファイルと同じディレクトリにindex.html）

オプション:
  --stdout  標準出力に出力（ファイル出力なし）
  --help    ヘルプを表示

入力形式（JSON）:
  {
    "title": "プレゼンタイトル",
    "slides": [
      { "type": "title", "message": "タイトル", "icon": "fa-robot" },
      { "type": "agenda", "message": "アジェンダ", "icon": "fa-list" },
      ...
    ]
  }

出力:
  - 16:9アスペクト比対応
  - Kanagawa CSS変数
  - GSAPアニメーション
  - キーボードナビゲーション
  - 印刷CSS

例:
  node html-scaffold.js ./structure.json ./slides/index.html
  node html-scaffold.js ./structure.md --stdout | pbcopy
`);
  process.exit(EXIT_CODES.SUCCESS);
}

/**
 * 入力を読み込み・パース
 */
async function readInput() {
  let content;

  if (inputPath) {
    if (!existsSync(inputPath)) {
      console.error(`❌ ファイルが見つかりません: ${inputPath}`);
      process.exit(EXIT_CODES.FILE_NOT_FOUND);
    }
    content = readFileSync(inputPath, 'utf-8');
  } else {
    // 標準入力から読み込み
    if (process.stdin.isTTY) {
      console.error('❌ 入力ファイルパスまたは標準入力を指定してください');
      process.exit(EXIT_CODES.ARGS_ERROR);
    }
    content = await new Promise((resolve) => {
      let data = '';
      process.stdin.setEncoding('utf-8');
      process.stdin.on('data', chunk => data += chunk);
      process.stdin.on('end', () => resolve(data));
    });
  }

  // JSONとして直接パース試行
  try {
    return JSON.parse(content);
  } catch {
    // Markdown内のJSONコードブロックを探す
    const jsonMatch = content.match(/```json\s*([\s\S]*?)\s*```/);
    if (jsonMatch) {
      try {
        return JSON.parse(jsonMatch[1]);
      } catch (e) {
        console.error(`❌ JSONパースエラー: ${e.message}`);
        process.exit(EXIT_CODES.ERROR);
      }
    }
    console.error('❌ 有効なJSON構造が見つかりません');
    process.exit(EXIT_CODES.ERROR);
  }
}

/**
 * スライドタイプに応じたHTML構造を生成
 */
function generateSlideHtml(slide, index) {
  const slideNum = index + 1;
  const type = slide.type || 'message';
  const message = slide.message || '';
  const icon = slide.icon || 'fa-circle';

  // 共通ラッパー
  const wrapper = (content) => `
    <!-- スライド ${slideNum}: ${type} -->
    <div class="slider__item slide-${type}" data-type="${type}">
      <div class="slide-area">
        <div class="slider__content">
${content}
        </div>
      </div>
    </div>`;

  // タイプ別テンプレート
  switch (type) {
    case 'title':
      return wrapper(`
          <div class="slide-title">
            <i class="fa-solid ${icon} slide-icon"></i>
            <h1>${message}</h1>
            <p class="subtitle"><!-- サブタイトル --></p>
          </div>`);

    case 'agenda':
      return wrapper(`
          <h2><i class="fa-solid ${icon}"></i> ${message}</h2>
          <ul class="agenda-list">
            <li class="agenda-item" data-section="1">セクション1</li>
            <li class="agenda-item" data-section="2">セクション2</li>
            <li class="agenda-item" data-section="3">セクション3</li>
          </ul>`);

    case 'section':
      return wrapper(`
          <div class="section-header">
            <span class="section-number">Section ${slideNum}</span>
            <h2><i class="fa-solid ${icon}"></i> ${message}</h2>
          </div>`);

    case 'list':
      return wrapper(`
          <h2><i class="fa-solid ${icon}"></i> ${message}</h2>
          <ul class="content-list">
            <li>項目1</li>
            <li>項目2</li>
            <li>項目3</li>
          </ul>`);

    case 'compare':
      return wrapper(`
          <h2><i class="fa-solid ${icon}"></i> ${message}</h2>
          <div class="compare-container">
            <div class="compare-item compare-left">
              <h3>左側タイトル</h3>
              <ul><li>特徴1</li><li>特徴2</li></ul>
            </div>
            <div class="compare-item compare-right">
              <h3>右側タイトル</h3>
              <ul><li>特徴1</li><li>特徴2</li></ul>
            </div>
          </div>`);

    case 'flow':
      return wrapper(`
          <h2><i class="fa-solid ${icon}"></i> ${message}</h2>
          <div class="flow-container">
            <div class="flow-step"><span class="step-num">1</span><span class="step-text">ステップ1</span></div>
            <div class="flow-arrow">→</div>
            <div class="flow-step"><span class="step-num">2</span><span class="step-text">ステップ2</span></div>
            <div class="flow-arrow">→</div>
            <div class="flow-step"><span class="step-num">3</span><span class="step-text">ステップ3</span></div>
          </div>`);

    case 'stats':
      return wrapper(`
          <h2><i class="fa-solid ${icon}"></i> ${message}</h2>
          <div class="stats-container">
            <div class="stat-item">
              <span class="stat-value">100%</span>
              <span class="stat-label">ラベル1</span>
            </div>
            <div class="stat-item">
              <span class="stat-value">50+</span>
              <span class="stat-label">ラベル2</span>
            </div>
          </div>`);

    case 'quote':
      return wrapper(`
          <blockquote class="slide-quote">
            <i class="fa-solid fa-quote-left quote-icon"></i>
            <p>${message}</p>
            <cite>— 出典</cite>
          </blockquote>`);

    case 'point-cards':
      return wrapper(`
          <h2><i class="fa-solid ${icon}"></i> ${message}</h2>
          <div class="point-cards-container">
            <div class="point-card">
              <i class="fa-solid fa-lightbulb card-icon"></i>
              <h3>ポイント1</h3>
              <p>説明文</p>
            </div>
            <div class="point-card">
              <i class="fa-solid fa-chart-line card-icon"></i>
              <h3>ポイント2</h3>
              <p>説明文</p>
            </div>
            <div class="point-card">
              <i class="fa-solid fa-users card-icon"></i>
              <h3>ポイント3</h3>
              <p>説明文</p>
            </div>
          </div>`);

    case 'cycle':
      return wrapper(`
          <h2><i class="fa-solid ${icon}"></i> ${message}</h2>
          <div class="cycle-container">
            <div class="cycle-item" data-position="top">Step 1</div>
            <div class="cycle-item" data-position="right">Step 2</div>
            <div class="cycle-item" data-position="bottom">Step 3</div>
            <div class="cycle-item" data-position="left">Step 4</div>
            <div class="cycle-center">中心</div>
          </div>`);

    default:
      // 汎用メッセージスライド
      return wrapper(`
          <h2><i class="fa-solid ${icon}"></i> ${message}</h2>
          <div class="content-body">
            <p><!-- コンテンツ --></p>
          </div>`);
  }
}

/**
 * HTMLテンプレート全体を生成
 */
function generateFullHtml(data) {
  const title = data.title || 'プレゼンテーション';
  const slides = data.slides || [];

  const slidesHtml = slides.map((slide, i) => generateSlideHtml(slide, i)).join('\n');

  return `<!DOCTYPE html>
<html lang="ja">
<head>
  <meta charset="UTF-8">
  <meta name="viewport" content="width=device-width, initial-scale=1.0">
  <title>${title}</title>
  <!-- FontAwesome -->
  <link rel="stylesheet" href="https://cdnjs.cloudflare.com/ajax/libs/font-awesome/6.5.1/css/all.min.css">
  <!-- GSAP -->
  <script src="https://cdnjs.cloudflare.com/ajax/libs/gsap/3.12.2/gsap.min.js"><\/script>
  <style>
    /* ===== CSS Variables (値の出どころは style-builder の SPEC.colors) ===== */
    :root {
      /* §2 インク・オン・ペーパー (VGCONST_001)。面に出る色はこの 3 値だけ */
      --paper: ${SPEC.colors.paper};
      --ink: ${SPEC.colors.ink};
      --paper-on-ink: ${SPEC.colors.paper};
      --fg-muted: ${SPEC.colors.inkMuted};
      --hairline: ${SPEC.colors.hairline};
      /* 地・面・文字の別名。render-slide の styles.css と同じ名前で同じ値を指す */
      --bg-dark: var(--paper);
      --bg-dim: var(--paper);
      --bg-highlight: var(--paper);
      --bg-card: var(--paper);
      --sumi-ink: var(--paper);
      --fg: var(--ink);
      /* --fg-dim は値を持たない後方互換の別名。この濃度に値を代入しているのは
         上の --fg-muted 1 行だけで、本ファイルの CSS 規則はそちらを直接参照する。
         生成済み HTML が古い名前を持つ可能性のためだけに残してある。
         新しい記述でこの名前を使わないこと。増える区別は 1 つも無い。 */
      --fg-dim: var(--fg-muted);
      /* §2 濃度段 (VGCONST_002)。図解の内部でだけ使う単一色相 3 段 */
      --tone-1: ${SPEC.colors.tone1};
      --tone-2: ${SPEC.colors.tone2};
      --tone-3: ${SPEC.colors.tone3};
      /* 角丸 (VGCONST_003)。面は 0、図版のみ 2px。値は style-builder の出力から採る */
      --radius: ${RADIUS.surface};
      --radius-figure: ${RADIUS.figure};
      /* 旧色相名の別名。生成済み HTML がこの名前で参照しているので名前は残すが、
         色相へ意味を割り当てる運用は廃した (強調は地の反転で作る)。
         --spring-violet と --fuji-gray はここから落とした。前者は --wave-blue と、
         後者は --fg-dim と同じ値を指す別名で、名前が 2 つある状態そのものが
         「区別がある」という誤った主張になっていた。参照側も同じ便で寄せてある。 */
      --wave-blue: var(--tone-3);
      --sakura-pink: var(--ink);
      --wave-aqua: var(--tone-2);
      --autumn-yellow: var(--tone-1);
      /* Layout */
      --slide-max-width: 1920px;
      --slide-max-height: 1080px;
      /* Font Sizes */
      --fs-title: 3.5rem;
      --fs-h2: 2.5rem;
      --fs-h3: 2rem;
      --fs-body: 1.6rem;
      --fs-small: 1.4rem;
    }

    /* ===== Base Styles ===== */
    * { margin: 0; padding: 0; box-sizing: border-box; }
    html, body {
      height: 100%;
      font-family: 'Noto Sans JP', sans-serif;
      background: var(--bg-dark);
      color: var(--fg);
      overflow: hidden;
    }

    /* ===== 16:9 Slide Area ===== */
    .slide-area {
      width: 100%;
      height: 100%;
      max-width: var(--slide-max-width);
      max-height: var(--slide-max-height);
      aspect-ratio: 16 / 9;
      margin: 0 auto;
      display: flex;
      align-items: center;
      justify-content: center;
    }

    /* ===== Slider ===== */
    .slider {
      width: 100%;
      height: 100vh;
      overflow: hidden;
      position: relative;
    }
    .slider__container {
      display: flex;
      height: 100%;
      transition: transform 0.5s ease;
    }
    .slider__item {
      min-width: 100%;
      height: 100%;
      display: flex;
      align-items: center;
      justify-content: center;
      background: var(--bg-dark);
    }
    .slider__content {
      width: 90%;
      max-width: 1600px;
      padding: 2rem;
      visibility: hidden;
    }
    .slider__item.active .slider__content {
      visibility: visible;
    }

    /* ===== Typography ===== */
    h1 { font-size: var(--fs-title); margin-bottom: 1rem; }
    h2 { font-size: var(--fs-h2); margin-bottom: 1.5rem; color: var(--wave-blue); }
    h3 { font-size: var(--fs-h3); margin-bottom: 1rem; }
    p, li { font-size: var(--fs-body); line-height: 1.8; }

    /* ===== Navigation ===== */
    .nav-arrows {
      position: fixed;
      bottom: 2rem;
      right: 2rem;
      display: flex;
      gap: 1rem;
      z-index: 100;
    }
    .nav-arrow {
      width: 50px;
      height: 50px;
      border-radius: 50%;
      background: var(--bg-dim);
      border: 2px solid var(--wave-blue);
      cursor: pointer;
      display: flex;
      align-items: center;
      justify-content: center;
      transition: all 0.3s;
    }
    .nav-arrow:hover {
      background: var(--wave-blue);
      color: var(--bg-dark);
    }
    .page-indicator {
      position: fixed;
      bottom: 2rem;
      left: 50%;
      transform: translateX(-50%);
      font-size: var(--fs-small);
      color: var(--fg-muted);
    }

    /* ===== Slide Types ===== */
    .slide-title { text-align: center; }
    .slide-icon { font-size: 4rem; color: var(--wave-blue); margin-bottom: 1rem; display: block; }

    /* SR-4-03 の 48%/4%/48%。gap を絶対長 (2rem) にすると比率が画面幅で変わる。
       justify-content:center は幅を持つ子には効かないので置かない。 */
    .compare-container { display: flex; gap: ${COMPARE.gap}; width: 100%; }
    .compare-item { width: ${COMPARE.panel}; flex: none; padding: 2rem; background: var(--bg-dim); border-radius: var(--radius); }

    .flow-container { display: flex; align-items: center; justify-content: center; gap: 1rem; flex-wrap: wrap; }
    .flow-step { padding: 1.5rem 2rem; background: var(--bg-dim); border-radius: var(--radius); text-align: center; }
    .flow-arrow { font-size: 2rem; color: var(--wave-blue); }

    .stats-container { display: flex; gap: 3rem; justify-content: center; }
    .stat-item { text-align: center; }
    .stat-value { display: block; font-size: 4rem; font-weight: bold; color: var(--wave-blue); }
    .stat-label { font-size: var(--fs-body); color: var(--fg-muted); }

    .point-cards-container { display: flex; gap: 2rem; justify-content: center; }
    .point-card { flex: 1; padding: 2rem; background: var(--bg-dim); border-radius: var(--radius); text-align: center; }
    .card-icon { font-size: 2.5rem; color: var(--wave-blue); margin-bottom: 1rem; }

    /* ===== Print Styles ===== */
    @media print {
      .slider { height: auto; overflow: visible; }
      .slider__container { flex-direction: column; transform: none !important; }
      .slider__item { min-height: 100vh; page-break-after: always; }
      .slider__content { visibility: visible !important; }
      .nav-arrows, .page-indicator { display: none; }
    }
  </style>
</head>
<body>
  <div class="slider">
    <div class="slider__container">
${slidesHtml}
    </div>
  </div>

  <!-- Navigation -->
  <div class="nav-arrows">
    <button class="nav-arrow nav-prev" onclick="prevSlide()">
      <i class="fa-solid fa-chevron-left"></i>
    </button>
    <button class="nav-arrow nav-next" onclick="nextSlide()">
      <i class="fa-solid fa-chevron-right"></i>
    </button>
  </div>
  <div class="page-indicator">
    <span class="current-page">1</span> / <span class="total-pages">${slides.length}</span>
  </div>

  <script>
    // Slide Navigation
    let currentSlide = 0;
    const totalSlides = ${slides.length};
    const container = document.querySelector('.slider__container');
    const items = document.querySelectorAll('.slider__item');

    function goToSlide(index) {
      if (index < 0) index = 0;
      if (index >= totalSlides) index = totalSlides - 1;
      currentSlide = index;
      container.style.transform = \`translateX(-\${currentSlide * 100}%)\`;
      items.forEach((item, i) => item.classList.toggle('active', i === currentSlide));
      document.querySelector('.current-page').textContent = currentSlide + 1;
      animateSlide();
    }

    function nextSlide() { goToSlide(currentSlide + 1); }
    function prevSlide() { goToSlide(currentSlide - 1); }

    // Keyboard Navigation
    document.addEventListener('keydown', (e) => {
      if (e.key === 'ArrowRight' || e.key === ' ') nextSlide();
      if (e.key === 'ArrowLeft') prevSlide();
      if (e.key === 'Home') goToSlide(0);
      if (e.key === 'End') goToSlide(totalSlides - 1);
    });

    // GSAP Animation
    function animateSlide() {
      const content = items[currentSlide].querySelector('.slider__content');
      if (!content) return;
      gsap.fromTo(content.children,
        { opacity: 0, y: 30 },
        { opacity: 1, y: 0, duration: 0.5, stagger: 0.1, ease: 'power2.out' }
      );
    }

    // Initialize
    goToSlide(0);
  <\/script>
</body>
</html>`;
}

// メイン処理
(async () => {
  const data = await readInput();

  if (!data.slides || !Array.isArray(data.slides)) {
    console.error('❌ slides配列が必要です');
    process.exit(EXIT_CODES.VALIDATION_FAILED);
  }

  const html = generateFullHtml(data);

  if (stdoutMode) {
    console.log(html);
  } else {
    writeFileSync(outputPath, html, 'utf-8');
    console.log(`✅ HTMLスケルトンを生成しました: ${outputPath}`);
    console.log(`   スライド数: ${data.slides.length}枚`);
    console.log(`   タイトル: ${data.title || '（未設定）'}`);
  }

  process.exit(EXIT_CODES.SUCCESS);
})();
