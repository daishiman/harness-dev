/* slide-skeleton.js を Node 上で「実行して」挙動を確かめるための最小 DOM 代替。
 *
 * なぜ本物のブラウザを使わないか: この JS が守るべき契約は
 *   (1) 溢れている間だけ font-size を下げる
 *   (2) 下限 18px で必ず止まる
 *   (3) 止まったら data-autofit-floored / data-overflow を立てる
 *   (4) 何度呼んでも同じ状態へ収束する (冪等)
 * の 4 つで、いずれも「scrollHeight と clientHeight の大小」だけで決まる。
 * ブラウザの実レイアウトは不要で、その大小関係を再現できる模型があれば足りる。
 * 代わりに Playwright 依存も CI 時間もゼロで、失敗が決定論になる。
 *
 * 使い方: node skeleton-js-harness.js <slide-skeleton.js のパス>
 *         結果を JSON で stdout へ出す (テスト側が読む)。
 */
'use strict';

const fs = require('fs');

const LINE_HEIGHT = 1.5;   // 行送り。scrollHeight 模型の唯一の定数

/* --- 最小の要素模型 ------------------------------------------------------ */

class El {
  constructor(opts) {
    opts = opts || {};
    this.attrs = Object.assign({}, opts.attrs);
    this.children = [];
    this.parentElement = null;
    this.clientWidth = opts.clientWidth || 0;
    this.clientHeight = opts.clientHeight || 0;

    // 初期 font-size。autofit はここを起点に下げていく。
    this.baseFontSize = opts.baseFontSize || 32;
    // 本文の行数。「その font-size なら何 px 必要か」の入力になる。
    this.contentUnits = opts.contentUnits || 0;

    this._fontSize = null;
    this.style = {
      setProperty: (k, v) => { this.attrs['style:' + k] = v; },
      removeProperty: (k) => {
        if (k === 'font-size') this._fontSize = null;
        else delete this.attrs['style:' + k];
      },
      set fontSize(v) { /* replaced below */ },
    };
    Object.defineProperty(this.style, 'fontSize', {
      get: () => (this._fontSize == null ? '' : this._fontSize + 'px'),
      set: (v) => { this._fontSize = parseFloat(v); },
    });
  }

  get fontSize() { return this._fontSize == null ? this.baseFontSize : this._fontSize; }

  /* 本文の高さ = 行数 × font-size × line-height。
     この 1 式が「どんな溢れ方を再現できるか」を決める模型の心臓部で、
     判定に必要な性質だけを満たす最小形を選んでいる:

       - 単調: font-size を下げれば scrollHeight は必ず縮む。非単調だと
         autofit のループが下限まで無駄走りする挙動しか試せなくなる。
       - 下限で救えない面が作れる: 行数を大きくすれば font-size = 18 でも
         clientHeight を超える (契約 2・3 の入力)。
       - 数 step で収まる面も作れる (契約 1 の入力)。

     折り返しは**あえて模型化しない**。折り返しを入れると高さが clientWidth に
     依存し、縮小すると行数が減るぶん高さが階段状・非単調に動きうる。
     この JS の判断は「scrollHeight > clientHeight か」の連鎖だけなので、
     折り返しの忠実さは契約の判定に寄与せず、模型を壊すリスクだけが増える。 */
  get scrollHeight() {
    return this.contentUnits * this.fontSize * LINE_HEIGHT;
  }

  setAttribute(k, v) { this.attrs[k] = String(v); }
  removeAttribute(k) { delete this.attrs[k]; }
  getAttribute(k) { return k in this.attrs ? this.attrs[k] : null; }
  hasAttribute(k) { return k in this.attrs; }

  append(child) { child.parentElement = this; this.children.push(child); return child; }

  /* 対応するのは実装が実際に使う 2 つのセレクタだけ ('.srg-slide' と '[data-autofit]')。
     汎用セレクタエンジンを書くと、模型の方が本体より複雑になる。 */
  querySelectorAll(sel) {
    const out = [];
    const match = (el) => {
      if (sel === '.srg-slide') return (el.attrs.class || '').split(/\s+/).includes('srg-slide');
      if (sel === '[data-autofit]') return el.hasAttribute('data-autofit');
      return false;
    };
    const walk = (el) => { el.children.forEach((c) => { if (match(c)) out.push(c); walk(c); }); };
    walk(this);
    return out;
  }
}

/* --- document / window の代替 -------------------------------------------- */

function makeEnv(root) {
  const listeners = {};
  const doc = {
    readyState: 'complete',
    querySelectorAll: (s) => root.querySelectorAll(s),
    addEventListener: (t, fn) => { (listeners[t] = listeners[t] || []).push(fn); },
    fonts: null,
  };
  const win = {
    addEventListener: (t, fn) => { (listeners[t] = listeners[t] || []).push(fn); },
  };
  return { doc, win, listeners, fire: (t) => (listeners[t] || []).forEach((fn) => fn()) };
}

/* --- 実行 ----------------------------------------------------------------- */

function run(jsPath) {
  const deck = new El({ attrs: { class: 'srg-deck' }, clientWidth: 640, clientHeight: 360 });

  // (a) 1 step 下げれば収まる面 / (b) 下限でも収まらない面 の 2 つを並べる。
  const easy = deck.append(new El({ attrs: { class: 'srg-slide' } }));
  const easyBody = easy.append(new El({
    attrs: { 'data-autofit': '' }, clientHeight: 300, baseFontSize: 32, contentUnits: 10,
  }));

  const hard = deck.append(new El({ attrs: { class: 'srg-slide' } }));
  const hardBody = hard.append(new El({
    attrs: { 'data-autofit': '' }, clientHeight: 100, baseFontSize: 32, contentUnits: 400,
  }));

  const env = makeEnv(deck);
  const src = fs.readFileSync(jsPath, 'utf8');
  const fn = new Function('document', 'window', 'getComputedStyle',
    'requestAnimationFrame', 'cancelAnimationFrame', src + '\n;return window.SRGSkeleton;');
  const api = fn(
    env.doc, env.win,
    (el) => ({ fontSize: el.fontSize + 'px' }),
    (cb) => { cb(); return 1; },
    () => {},
  );

  const snap = () => ({
    easyFontSize: easyBody.fontSize,
    easyFloored: easyBody.hasAttribute('data-autofit-floored'),
    easyOverflow: easy.hasAttribute('data-overflow'),
    hardFontSize: hardBody.fontSize,
    hardFloored: hardBody.hasAttribute('data-autofit-floored'),
    hardOverflow: hard.hasAttribute('data-overflow'),
    fit: easy.attrs['style:--srg-fit'],
  });

  const first = snap();
  api.apply(env.doc);            // 2 回目: 冪等性の確認
  const second = snap();

  return { first, second, contentModelImplemented: hardBody.scrollHeight > 0 };
}

process.stdout.write(JSON.stringify(run(process.argv[2]), null, 2) + '\n');
