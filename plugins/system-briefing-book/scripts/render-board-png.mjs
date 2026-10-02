#!/usr/bin/env node
/**
 * render-board-png — ボード HTML を検査してから PNG とまとめ用の WebP にする。
 *
 * 順番: 静的検査 (色の直書き・外部参照・置換子) → ブラウザで DOM 検査 → PNG と WebP → 切り出し。
 * ブラウザ (Chrome / Edge) は 1 つだけ起動し、Chrome DevTools Protocol で直接動かす。
 * assets/data/quality-thresholds.json の board (width・height・scale) の大きさのタブで開き、同じ描画から PNG と WebP (品質 82) を撮る。
 * ほかのボードで使う画面 (data-export) は幅 520 の PNG に切り出す。切り出すあいだは、その中の
 * 番号の印 (.mk) を隠す (縮小した画面に元のボードの番号が写り込まないように)。
 * 切り出した画面を使うボードは、切り出し元のボードより後に描く (依存の段ごとに処理する)。
 *
 * 使い方:
 *   node scripts/render-board-png.mjs --dir <打ち合わせ資料> [--only NN ...] [--check-only] [--browser <path>]
 *        [--jobs 3] [--timeout 90] [--allow-warn] [--quiet]
 *   ブラウザは --browser → 環境変数 BRIEFING_BROWSER → 決まった場所 → PATH の順に探す。
 *
 * 書く場所: <dir>/NN_*.png, <dir>/_src/book/NN_*.webp, <dir>/_src/assets/export/<name>.png, <dir>/_check/boards.json。
 *           --check-only のときは何も書かない (結果は stdout だけ)。
 * stdout: JSON {status, summary, check, errors[], boards[]} (--quiet で要約 1 行)
 * 検査の重さは error・warn・報告 (notices) の 3 段。量 (説明の字数 TEXT-LONG・注記の数 NOTES-MANY) は報告だけで、
 * status にも exit にも効かない。説明の字数は端末の絵 (.phone・.browser) の中を数えない。
 * exit: 0=問題なし / 1=error あり (--allow-warn が無ければ warn だけでも 1) / 2=使い方の誤り / 3=ブラウザか Node が無い・古い・しきい値のファイルが読めない
 */
import { readFileSync } from "node:fs";
import path from "node:path";
import { pathToFileURL } from "node:url";

import { findBrowser, launchBrowser } from "./lib/browser-session.mjs";
import {
  DATA_POLICIES,
  DEVICE_TYPES,
  PAGE_TYPES,
  expandHome,
  isDir,
  isFile,
  loadJson,
  loadThresholds,
  sha256,
  threshold,
  thresholdTable,
  writeAtomic,
  writeJson,
} from "./lib/briefing-files.mjs";
import { EXIT, ToolMissing, UsageError, emitResult, isEntryPoint, parseOptions, runCli } from "./lib/cli-contract.mjs";
import { dependencyReceipt, htmlRefs, externalRef } from "./lib/resource-refs.mjs";
import { imageSize } from "./lib/image-size.mjs";
import { validateDesignTokens } from "./lib/design-tokens.mjs";

export { findBrowser };

const USAGE = `
使い方:
  render-board-png.mjs --dir <打ち合わせ資料> [--only NN ...] [--check-only] [--browser <path>]
                       [--jobs 3] [--timeout 90] [--allow-warn] [--quiet]
`;

const EXPORT_WIDTH = 520;
const WEBP_QUALITY = 82;
const EXPORT_NAME = /^[a-z0-9]+(?:-[a-z0-9]+)*$/;
const EXPORT_REF = /assets\/export\/([^"'()\s>]+?)\.png/;
const EXPORT_ATTR = /data-export\s*=\s*["']([^"']*)["']/g;
const HTML_COMMENT = /<!--[\s\S]*?-->/g;
// Python の \b と \w は Unicode の文字を見るので、同じ判定になるように文字の種類で書く
const WORD = "[\\p{L}\\p{N}_]";
const COLOUR = new RegExp(
  `#[0-9a-fA-F]{3,8}(?!${WORD})|(?<!${WORD})(?:rgba?|hsla?|hwb|lab|lch|oklab|oklch)\\s*\\(|` +
    `(?<![-\\p{L}\\p{N}_])(?:white|black|red|blue|green|gray|grey|yellow|orange)(?![-\\p{L}\\p{N}_])`,
  "iu",
);

/**
 * ページの中で動かす DOM 検査。T (しきい値) と policy (briefing.json の data_policy。無い・不正なら null) を受け取り、
 * {errors, warnings, info, images, exports} を返す。
 */
const CHECK_JS = String.raw`
(async function (T, policy) {
  var TOL = 1, LIMIT = 25, FONT_LIMIT = 5;
  var R = { errors: [], warnings: [], info: {} };
  function add(level, code, message, where) {
    (level === 'error' ? R.errors : R.warnings).push({ code: code, message: message, where: where || null });
  }
  var cache = new Map();
  function cs(el) { var s = cache.get(el); if (!s) { s = getComputedStyle(el); cache.set(el, s); } return s; }
  function desc(el) {
    var s = el.tagName.toLowerCase();
    if (el.id) s += '#' + el.id;
    if (el.classList && el.classList.length) s += '.' + Array.prototype.slice.call(el.classList, 0, 3).join('.');
    var t = (el.textContent || '').replace(/\s+/g, ' ').trim();
    if (t) s += ' 「' + (t.length > 24 ? t.slice(0, 24) + '…' : t) + '」';
    return s;
  }
  function hiddenEl(el) {
    if (cs(el).visibility === 'hidden') return true;
    for (var e = el; e && e.nodeType === 1; e = e.parentElement) {
      if (cs(e).display === 'none' || cs(e).opacity === '0') return true;
    }
    return false;
  }
  function clipFrom(start, board) {
    for (var e = start; e && e !== board; e = e.parentElement) {
      var s = cs(e);
      if (s.overflowX !== 'visible' || s.overflowY !== 'visible') return e;
    }
    return null;
  }
  function exceeds(r, c) {
    return r.left < c.left - TOL || r.top < c.top - TOL || r.right > c.right + TOL || r.bottom > c.bottom + TOL;
  }
  function amount(r, c) {
    return Math.round(Math.max(c.left - r.left, c.top - r.top, r.right - c.right, r.bottom - c.bottom));
  }
  function hasUp(el, attr, board) {
    for (var e = el; e && e !== board.parentElement; e = e.parentElement) if (e.hasAttribute(attr)) return true;
    return false;
  }
  function run() {
    var boards = document.querySelectorAll('.board');
    if (boards.length !== 1) add('error', 'BOARD-COUNT', 'class="board" の要素が ' + boards.length + ' 個あります (1 個にする)');
    var board = boards[0];
    if (!board) return R;
    var br = board.getBoundingClientRect();
    R.info.board = { x: br.left, y: br.top, w: br.width, h: br.height,
      no: board.getAttribute('data-board'), type: board.getAttribute('data-type'), screens: board.getAttribute('data-screens') };
    if (Math.abs(br.width - T.width) > 0.5 || Math.abs(br.height - T.height) > 0.5 || Math.abs(br.left) > 0.5 || Math.abs(br.top) > 0.5) {
      add('error', 'BOARD-SIZE', 'ボードは左上 (0,0) に ' + T.width + 'x' + T.height + ' で置きます (今は ' +
        Math.round(br.left) + ',' + Math.round(br.top) + ' に ' + Math.round(br.width) + 'x' + Math.round(br.height) + ')');
    }
    Array.prototype.forEach.call(document.body.children, function (el) {
      if (el === board || el.contains(board) || /^(SCRIPT|STYLE|LINK|TEMPLATE|NOSCRIPT|META)$/.test(el.tagName)) return;
      var r = el.getBoundingClientRect();
      if (r.width > 0 && r.height > 0) add('warn', 'OUTSIDE-BOARD', 'ボードの外に要素があります (画像に写りません)', desc(el));
    });

    // はみ出し (ボードの外) と 切れ (overflow で隠れる)。data-clip-ok の中は切れてよい
    var reported = new Set(), counts = {};
    function upReported(el) { for (var e = el; e && e !== board; e = e.parentElement) if (reported.has(e)) return true; return false; }
    function geo(code, el, msg) {
      reported.add(el);
      counts[code] = (counts[code] || 0) + 1;
      if (counts[code] <= LIMIT) add('error', code, msg, desc(el));
    }
    function checkRect(el, r, clipStart) {
      if (r.width < 0.5 || r.height < 0.5 || upReported(el)) return;
      var c = clipFrom(clipStart, board);
      if (c) {
        var cr = c.getBoundingClientRect();
        if (exceeds(r, cr)) {
          if (!hasUp(el, 'data-clip-ok', board)) geo('CLIPPED', el, desc(c) + ' の枠から ' + amount(r, cr) + 'px はみ出して切れています');
          return;
        }
      }
      if (exceeds(r, br)) geo('OUT-OF-BOARD', el, 'ボードの外へ ' + amount(r, br) + 'px はみ出しています');
    }
    var all = Array.prototype.slice.call(board.querySelectorAll('*'));
    all.forEach(function (el) {
      if (hiddenEl(el)) return;
      checkRect(el, el.getBoundingClientRect(), el.parentElement);
    });
    var walker = document.createTreeWalker(board, NodeFilter.SHOW_TEXT, null), range = document.createRange();
    while (walker.nextNode()) {
      var n = walker.currentNode, p = n.parentElement;
      if (!p || !n.nodeValue.trim() || hiddenEl(p)) continue;
      range.selectNodeContents(n);
      var rects = range.getClientRects();
      for (var i = 0; i < rects.length; i++) checkRect(p, rects[i], p);
    }
    Object.keys(counts).forEach(function (code) {
      if (counts[code] > LIMIT) add('error', code, 'ほかに ' + (counts[code] - LIMIT) + ' か所あります');
    });

    // 文字の大きさ。transform で縮めた枠の中は見た目の px にする。端末の絵の中も外も見る
    function shrink(el) {
      var k = 1;
      for (var e = el; e && e !== board.parentElement; e = e.parentElement) {
        var m = cs(e).transform;
        var v = m && m !== 'none' ? m.match(/matrix(?:3d)?\(([^,]+),([^,]+)/) : null;
        if (v) k *= Math.hypot(parseFloat(v[1]), parseFloat(v[2]));
      }
      return k;
    }
    var fontMin = null, smallSeen = new Set();
    var fonts = document.createTreeWalker(board, NodeFilter.SHOW_TEXT, null);
    while (fonts.nextNode()) {
      var tn = fonts.currentNode, tp = tn.parentElement;
      if (!tp || !tn.nodeValue.trim() || hiddenEl(tp)) continue;
      var tr = tp.getBoundingClientRect();
      if (tr.width < 1 || tr.height < 1) continue;
      var px = Math.round(parseFloat(cs(tp).fontSize) * shrink(tp) * 10) / 10;
      if (fontMin === null || px < fontMin) fontMin = px;
      if (px >= T.font_px_min || smallSeen.has(tp)) continue;
      smallSeen.add(tp);
      if (smallSeen.size <= FONT_LIMIT) add('error', 'FONT-SMALL', '文字が ' + px + 'px です (' + T.font_px_min + 'px 以上にする)', desc(tp));
    }
    if (smallSeen.size > FONT_LIMIT) add('error', 'FONT-SMALL', 'ほかに ' + (smallSeen.size - FONT_LIMIT) + ' か所あります');
    R.info.font_px_min = fontMin;

    // 重なり (絶対配置どうし)。番号の印などは重ねて置くものなので数えない。data-overlap-ok の中も数えない
    var abs = [];
    all.forEach(function (el) {
      var pos = cs(el).position;
      if (pos !== 'absolute' && pos !== 'fixed') return;
      if (el.matches('.mk, .anchor, .island, .homebar') || el.closest('[data-overlap-ok]') || hiddenEl(el)) return;
      var r = el.getBoundingClientRect();
      if (r.width >= 1 && r.height >= 1) abs.push([el, r]);
    });
    for (var a = 0; a < abs.length; a++) {
      for (var b = a + 1; b < abs.length; b++) {
        var A = abs[a], B = abs[b];
        if (A[0].contains(B[0]) || B[0].contains(A[0])) continue;
        var w = Math.min(A[1].right, B[1].right) - Math.max(A[1].left, B[1].left);
        var h = Math.min(A[1].bottom, B[1].bottom) - Math.max(A[1].top, B[1].top);
        if (w > 1 && h > 1) add('warn', 'OVERLAP', desc(A[0]) + ' と ' + desc(B[0]) + ' が重なっています (わざとなら data-overlap-ok)');
      }
    }

    // 見出し
    var head = board.querySelector('header.board-head');
    var h1s = board.querySelectorAll('h1');
    if (!head) add('error', 'NO-HEAD', 'header.board-head がありません');
    if (h1s.length === 0) add('error', 'NO-TITLE', 'h1 (ボードの題) がありません');
    if (h1s.length > 1) add('error', 'TITLE-DUP', 'h1 が ' + h1s.length + ' 個あります (1 個にする)');
    R.info.title = h1s.length ? h1s[0].textContent.replace(/\s+/g, ' ').trim() : '';
    function headText(sel) { var e = head && head.querySelector(sel); return e ? e.textContent.trim() : ''; }
    if (!headText('.kicker')) add('error', 'NO-KICKER', '.kicker (ボードの種類と順番) がありません');
    else if (headText('.kicker').replace(/\s+/g, '') === R.info.title.replace(/\s+/g, '')) {
      add('warn', 'KICKER-SAME', '.kicker が h1 と同じ言葉です (kicker は「区分 ・ 順番」にする)');
    }
    if (!headText('.lead')) add('warn', 'NO-LEAD', '.lead (伝えたいこと 1 文) がありません');
    // 「例です」の札は伏せる資料 (masked) だけに置く。data_policy が無い・不正なら見ない (validate が止める)
    var flag = board.querySelector('.sample-flag');
    if (policy === 'masked' && !flag) add('warn', 'NO-SAMPLE-FLAG', '「画面の中の名前と値は例です」(.sample-flag) がありません');
    if (policy === 'source' && flag) add('warn', 'SAMPLE-FLAG-UNNEEDED', '素材のまま載せる資料 (data_policy が source) に「例です」の札 (.sample-flag) があります (外す)');

    // 注記と番号。注記の数は報告だけ (notices に入れるのは呼び出し側)
    var lis = Array.prototype.slice.call(board.querySelectorAll('aside.notes ol.marks > li'));
    R.info.notes = lis.length;
    var noteMarks = [], kinds = { can: 0, how: 0, ask: 0 };
    lis.forEach(function (li, i) {
      var kind = li.getAttribute('data-kind');
      if (!(kind in kinds)) add('error', 'NOTE-KIND', (i + 1) + ' 個目の注記の data-kind が can / how / ask ではありません: ' + kind, desc(li));
      else kinds[kind]++;
      if (!li.querySelector(':scope > b')) add('error', 'NOTE-KIND', (i + 1) + ' 個目の注記に <b> (ひとこと) がありません', desc(li));
      if (li.hasAttribute('data-mark')) {
        var m = li.getAttribute('data-mark').trim();
        if (noteMarks.indexOf(m) >= 0) add('error', 'MARK-MISMATCH', '注記の番号 ' + m + ' が 2 回あります', desc(li));
        noteMarks.push(m);
      }
    });
    R.info.kinds = kinds;
    var mks = Array.prototype.slice.call(board.querySelectorAll('.mk'));
    var mkNums = [];
    mks.forEach(function (mk) {
      var t = mk.textContent.trim();
      if (mkNums.indexOf(t) < 0) mkNums.push(t);
      if (!mk.closest('.anchor')) add('warn', 'MARK-ANCHOR', '番号 ' + t + ' が .anchor の中にありません (位置がずれやすい)', desc(mk));
    });
    mkNums.forEach(function (t) { if (noteMarks.indexOf(t) < 0) add('error', 'MARK-MISMATCH', '画面の番号 ' + t + ' に対応する注記がありません'); });
    // 画面の印も配置先もない一覧ボードでは、注記の番号は通し番号。型名には依存しない。
    var listOnly = mks.length === 0 && !board.querySelector('.anchor');
    if (!listOnly) noteMarks.forEach(function (t) { if (mkNums.indexOf(t) < 0) add('error', 'MARK-MISMATCH', '注記の番号 ' + t + ' が画面に置かれていません'); });
    for (var x = 0; x < mks.length; x++) {
      for (var y = x + 1; y < mks.length; y++) {
        var p = mks[x].getBoundingClientRect(), q = mks[y].getBoundingClientRect();
        if (Math.min(p.right, q.right) - Math.max(p.left, q.left) > 2 && Math.min(p.bottom, q.bottom) - Math.max(p.top, q.top) > 2) {
          add('warn', 'MARK-OVERLAP', '番号 ' + mks[x].textContent.trim() + ' と ' + mks[y].textContent.trim() + ' が重なっています');
        }
      }
    }

    // 説明の字数 = ボード全体から、いちばん外側の端末の絵 (.phone・.browser) の中を引いた数。量は報告だけ
    function chars(el) { return (el.innerText || '').replace(/\s+/g, '').length; }
    var device = 0;
    Array.prototype.forEach.call(board.querySelectorAll('.phone, .browser'), function (el) {
      if (el.parentElement && el.parentElement.closest('.phone, .browser')) return;
      if (el.getClientRects().length) device += chars(el); // 描かれていない枠は board の innerText にも入らない
    });
    R.info.device_chars = device;
    R.info.text_chars = chars(board) - device;

    // 画像と切り出し
    R.images = Array.prototype.slice.call(document.images).filter(function (img) { return board.contains(img); }).map(function (img) {
      return { src: img.getAttribute('src') || '', ok: img.complete && img.naturalWidth > 0 };
    });
    var names = [];
    R.exports = Array.prototype.slice.call(board.querySelectorAll('[data-export]')).map(function (el) {
      var r = el.getBoundingClientRect(), name = el.getAttribute('data-export');
      if (names.indexOf(name) >= 0) add('error', 'EXPORT-DUP', 'data-export="' + name + '" が 2 回あります', desc(el));
      names.push(name);
      if (exceeds(r, br)) add('error', 'EXPORT-OUT', 'data-export="' + name + '" がボードからはみ出しています', desc(el));
      return { name: name, x: r.left - br.left, y: r.top - br.top, w: r.width, h: r.height };
    });
    return R;
  }
  if (document.fonts && document.fonts.ready) await document.fonts.ready;
  await new Promise(function (resolve) { setTimeout(resolve, 0); });
  try { return run(); } catch (e) { return { fatal: String((e && e.stack) || e) }; }
})`;

/** 描画が落ち着くまで 2 フレーム待つ (フレームが来ない環境でも 300ms で進む)。 */
const SETTLE_JS = `new Promise(function (resolve) {
  var done = false; function end() { if (!done) { done = true; resolve(true); } }
  requestAnimationFrame(function () { requestAnimationFrame(end); });
  setTimeout(end, 300);
})`;
const MARKS_STYLE_ID = "__briefing_hide_export_marks";
const HIDE_EXPORT_MARKS_JS = `(function () {
  var s = document.createElement('style');
  s.id = '${MARKS_STYLE_ID}';
  s.textContent = '[data-export] .mk { visibility: hidden !important; }';
  (document.head || document.documentElement).appendChild(s);
  return ${SETTLE_JS};
})()`;
const SHOW_EXPORT_MARKS_JS = `(function () {
  var s = document.getElementById('${MARKS_STYLE_ID}');
  if (s) s.remove();
  return true;
})()`;

const issue = (code, message, where = null) => ({ code, message, where });

const BOARD_KEYS = ["width", "height", "scale", "font_px_min", "notes_note"];

/** ボードのしきい値。正本は assets/data/quality-thresholds.json の board。足りなければ止める (exit 3)。 */
function boardThresholds() {
  const loaded = loadThresholds();
  return {
    ...Object.fromEntries(BOARD_KEYS.map((key) => [key, threshold(loaded, "board", key)])),
    text_chars_note: thresholdTable(loaded, "board", "text_chars_note", PAGE_TYPES),
  };
}

/** 色の直書き・外部参照・置換子を HTML の文字から探す。返り値は {errors, warnings}。 */
export function staticCheck(source) {
  const text = source.replace(HTML_COMMENT, ""); // 雛形の説明コメントにある例 (data-export="..." など) は数えない
  const errors = [];
  const warnings = [];
  const found = [];
  for (const [, inner] of text.matchAll(/<style[^>]*>([\s\S]*?)<\/style>/gi)) {
    const block = inner.replace(/\/\*[\s\S]*?\*\//g, "");
    for (const [, prop, value] of block.matchAll(/([-\p{L}\p{N}_]+)\s*:\s*([^;{}]+)/gu)) {
      if (COLOUR.test(value)) found.push(`<style> ${prop.trim()}: ${value.trim().slice(0, 40)}`);
    }
  }
  for (const [, attr, value] of text.matchAll(/(?<![\p{L}\p{N}_])(style|fill|stroke|color|bgcolor)\s*=\s*"([^"]*)"/giu)) {
    if (COLOUR.test(value)) found.push(`${attr}="${value.trim().slice(0, 40)}"`);
  }
  for (const item of found.slice(0, 10)) {
    errors.push(issue("RAW-COLOR", "色を直接書いています。tokens.css の var(--...) を使います", item));
  }
  if (found.length > 10) errors.push(issue("RAW-COLOR", `ほかに ${found.length - 10} か所あります`));
  const external = htmlRefs(source).filter(({ value, attr }) => externalRef(value) || attr === "@import").map(({ value }) => value);
  for (const ref of external.slice(0, 10)) {
    errors.push(issue("EXTERNAL-REF", "外の URL を読み込んでいます。素材は _src/assets/ に置きます", ref.slice(0, 80)));
  }
  const placeholders = [...new Set([...text.matchAll(/\{\{[A-Z_]+\}\}/g)].map((m) => m[0]))].sort();
  if (placeholders.length) errors.push(issue("PLACEHOLDER", "雛形の置換子が残っています", placeholders.join(" ")));
  return { errors, warnings };
}

/**
 * 切り出しの依存で段に分ける。返り値は {levels: ボードの配列の配列, deps: Map<no, Set<no>>}。
 * 名前の誤り・重複・切り出し元の無い参照・輪は、それぞれのボードの errors / warnings に足す。
 */
export function orderLevels(boards, exportDir) {
  const provider = new Map();
  for (const board of boards) {
    for (const name of board.exports) {
      if (!EXPORT_NAME.test(name)) board.errors.push(issue("EXPORT-NAME", "data-export は英小文字・数字・- にします", name));
      if (provider.has(name) && provider.get(name) !== board) {
        board.errors.push(issue("EXPORT-DUP", `data-export="${name}" が ${provider.get(name).file} にもあります`, name));
      }
      if (!provider.has(name)) provider.set(name, board);
    }
  }
  const deps = new Map(boards.map((b) => [b.no, new Set()]));
  for (const board of boards) {
    for (const name of board.refs) {
      const src = provider.get(name);
      if (src === undefined) {
        if (isFile(path.join(exportDir, `${name}.png`))) {
          board.warnings.push(issue("EXPORT-ORPHAN", `${name}.png を切り出すボードがありません (古い画像のままです)`, name));
        } else {
          board.errors.push(issue("EXPORT-UNKNOWN", `assets/export/${name}.png を切り出すボード (data-export="${name}") がありません`, name));
        }
      } else if (src !== board) {
        deps.get(board.no).add(src.no);
      }
    }
  }
  const levels = [];
  const placed = new Set();
  let remaining = [...boards];
  while (remaining.length) {
    const level = remaining.filter((b) => [...deps.get(b.no)].every((no) => placed.has(no)));
    if (!level.length) {
      for (const board of remaining) board.errors.push(issue("EXPORT-CYCLE", "切り出しの参照が輪になっています"));
      levels.push(remaining);
      break;
    }
    levels.push(level);
    for (const b of level) placed.add(b.no);
    remaining = remaining.filter((b) => !placed.has(b.no));
  }
  return { levels, deps };
}

/** --only で選んだボードが使う切り出し画像の元ボードも選ぶ。 */
export function selectWithSources(boards, deps) {
  const byNo = new Map(boards.map((b) => [b.no, b]));
  const todo = boards.filter((b) => b.selected).map((b) => b.no);
  while (todo.length) {
    for (const src of deps.get(todo.pop()) ?? []) {
      const board = byNo.get(src);
      if (board && !board.selected) {
        board.selected = true;
        todo.push(src);
      }
    }
  }
}

/**
 * briefing.json の pages からボードを読む。HTML が無いものは runErrors (BOARD-MISSING) に入れる。
 * dataPolicy は data_policy の値 (source / masked 以外なら null)。
 */
export function loadBoards(base, only) {
  let briefing;
  try {
    briefing = JSON.parse(readFileSync(path.join(base, "briefing.json"), "utf8"));
  } catch (error) {
    throw new UsageError(`briefing.json が読めません: ${error.message}`);
  }
  const pages = briefing && typeof briefing === "object" && !Array.isArray(briefing) ? briefing.pages : null;
  if (!Array.isArray(pages) || !pages.length) throw new UsageError("briefing.json の pages が空です (先にページ構成を決める)");
  const boards = [];
  const runErrors = [];
  for (const page of pages) {
    if (!page || typeof page !== "object" || Array.isArray(page)) continue;
    const no = page.no == null ? "" : String(page.no);
    const file = page.file == null ? "" : String(page.file);
    const htmlPath = path.join(base, "_src", file);
    if (!file.endsWith(".html") || !isFile(htmlPath)) {
      runErrors.push(issue("BOARD-MISSING", `ボード HTML がありません: _src/${file}`, no));
      continue;
    }
    const raw = readFileSync(htmlPath);
    const text = raw.toString("utf8");
    const live = text.replace(HTML_COMMENT, "");
    boards.push({
      no,
      file,
      stem: path.basename(file, ".html"),
      path: htmlPath,
      page,
      text,
      sha: sha256(raw),
      exports: [...live.matchAll(EXPORT_ATTR)].map((m) => m[1]),
      refs: [...new Set([...live.matchAll(new RegExp(EXPORT_REF.source, "g"))].map((m) => m[1]))].sort(),
      errors: [],
      warnings: [],
      notices: [],
      dom: {},
      png: null,
      webp: null,
      pngSize: null,
      exportFiles: [],
      selected: only === null || only.has(no),
    });
  }
  if (only) {
    const known = new Set(boards.map((b) => b.no));
    const unknown = [...only].filter((no) => !known.has(no)).sort();
    if (unknown.length) throw new UsageError(`--only の番号が pages にありません: ${unknown.join(", ")}`);
  }
  const dataPolicy = DATA_POLICIES.includes(briefing.data_policy) ? briefing.data_policy : null;
  return { boards, runErrors, dataPolicy };
}

function boardStatus(board) {
  return board.errors.length ? "ng" : board.warnings.length ? "warn" : "ok";
}

function sameScreens(attr, screens) {
  const a = String(attr ?? "").split(/\s+/).filter(Boolean).sort();
  const b = (Array.isArray(screens) ? screens : []).map(String).sort();
  return a.length === b.length && a.every((v, i) => v === b[i]);
}

/** DOM 検査の結果を pages と突き合わせ、ボードの errors / warnings に足す。 */
function applyDomResult(board, ctx) {
  const dom = board.dom;
  if (dom.fatal) {
    board.errors.push(issue("CHECK-FAILED", dom.fatal));
    return;
  }
  board.errors.push(...(dom.errors ?? []));
  board.warnings.push(...(dom.warnings ?? []));
  const info = dom.info?.board ?? {};
  const page = board.page;
  // コード名は validate-briefing-docs.mjs の checkBoard と同じ
  if (info.no !== board.no) {
    board.errors.push(issue("BOARD-ATTR", `data-board が pages の no と違います: ${info.no ?? ""} / ${board.no}`));
  }
  if (info.type !== page.type) {
    board.errors.push(issue("BOARD-ATTR", `data-type が pages の type と違います: ${info.type ?? ""} / ${page.type ?? ""}`));
  }
  if (DEVICE_TYPES.includes(page.type) && !sameScreens(info.screens, page.screens)) {
    board.warnings.push(issue("BOARD-SCREENS-MISMATCH", "data-screens が pages の screens と違います"));
  }
  for (const image of dom.images ?? []) {
    if (image.ok) continue;
    const m = EXPORT_REF.exec(image.src ?? "");
    if (m && ctx.checkOnly && ctx.providers.has(m[1])) {
      board.warnings.push(issue("EXPORT-NOT-RENDERED", "切り出し画像がまだありません (PNG を作ると直ります)", image.src));
    } else {
      board.errors.push(issue("BROKEN-IMAGE", "画像が読めません", image.src ?? null));
    }
  }
  // 量は報告だけ (status と exit に効かない)
  const T = ctx.thresholds;
  const chars = dom.info?.text_chars;
  const charsNote = T.text_chars_note[page.type];
  if (typeof chars === "number" && typeof charsNote === "number" && chars > charsNote) {
    board.notices.push(issue("TEXT-LONG", `説明が ${chars} 字あります (${page.type} の目安は ${charsNote} 字まで。端末の絵の中は数えない)`));
  }
  const notes = dom.info?.notes;
  if (typeof notes === "number" && notes > T.notes_note) {
    board.notices.push(issue("NOTES-MANY", `注記が ${notes} 個あります (目安は ${T.notes_note} 個まで)`));
  }
}

/** data-export の画面を幅 520 で撮る。撮るあいだは中の番号の印 (.mk) を隠し、終わったら戻す。 */
async function captureExports(page, board, T, exportDir) {
  const items = (board.dom.exports ?? []).filter((item) => EXPORT_NAME.test(item.name ?? ""));
  if (!items.length) return [];
  const origin = board.dom.info?.board ?? { x: 0, y: 0 };
  const px = (v) => Math.round(v * T.scale) / T.scale; // 端を画面の画素にそろえる
  const made = [];
  await page.evaluate(HIDE_EXPORT_MARKS_JS);
  try {
    for (const item of items) {
      const x0 = Math.max(0, px(origin.x + item.x));
      const y0 = Math.max(0, px(origin.y + item.y));
      const x1 = Math.min(T.width, px(origin.x + item.x + item.w));
      const y1 = Math.min(T.height, px(origin.y + item.y + item.h));
      if ((x1 - x0) * T.scale < 2 || (y1 - y0) * T.scale < 2) {
        board.errors.push(issue("EXPORT-EMPTY", `data-export="${item.name}" の大きさが 0 です`, item.name));
        continue;
      }
      const full = (x1 - x0) * T.scale;
      const scale = full > EXPORT_WIDTH ? EXPORT_WIDTH / full : 1;
      const data = await page.screenshot({ clip: { x: x0, y: y0, width: x1 - x0, height: y1 - y0, scale } });
      const size = imageSize(data);
      writeAtomic(path.join(exportDir, `${item.name}.png`), data);
      made.push({ name: item.name, png: `_src/assets/export/${item.name}.png`, size: size ? [size.width, size.height] : null });
    }
  } finally {
    await page.evaluate(SHOW_EXPORT_MARKS_JS).catch(() => {});
  }
  return made;
}

/** 1 枚を開いて検査し、--check-only でなければ PNG・WebP・切り出しを書く。 */
async function processBoard(board, ctx) {
  const T = ctx.thresholds;
  const page = await ctx.session.newPage({ width: T.width, height: T.height, scale: T.scale });
  try {
    let opened = true;
    try {
      await page.goto(pathToFileURL(board.path).href, ctx.timeoutMs);
      const dom = await page.evaluate(`${CHECK_JS}(${JSON.stringify(T)}, ${JSON.stringify(ctx.dataPolicy)})`, {
        timeoutMs: ctx.timeoutMs,
      });
      board.dom = dom && typeof dom === "object" ? dom : { fatal: "ブラウザでの検査に失敗しました (検査の結果を読めませんでした)" };
    } catch (error) {
      opened = false;
      board.dom = { fatal: `ブラウザでの検査に失敗しました (${error.message})` };
    }
    applyDomResult(board, ctx);
    if (ctx.checkOnly) return;
    if (!opened) {
      board.errors.push(issue("RENDER-FAILED", "PNG を作れませんでした (ページを開けません)"));
      return;
    }
    // 撮影は 1 枚ずつ、そのタブを前に出してから (裏のタブは描画が止まることがある)
    await ctx.exclusive(async () => {
      await page.send("Page.bringToFront");
      await page.evaluate(SETTLE_JS);
      const clip = { x: 0, y: 0, width: T.width, height: T.height };
      const png = await page.screenshot({ clip });
      const size = imageSize(png);
      const expected = [Math.trunc(T.width * T.scale), Math.trunc(T.height * T.scale)];
      if (!size || size.width !== expected[0] || size.height !== expected[1]) {
        const got = size ? `${size.width}x${size.height}` : "読めない画像";
        board.errors.push(issue("PNG-SIZE", `PNG が ${got} です (${expected[0]}x${expected[1]} のはず)`));
        return;
      }
      const webp = await page.screenshot({ clip, format: "webp", quality: WEBP_QUALITY });
      writeAtomic(path.join(ctx.outDir, `${board.stem}.png`), png);
      board.png = `${board.stem}.png`;
      board.pngSha = sha256(png);
      board.pngSize = [size.width, size.height];
      writeAtomic(path.join(ctx.outDir, "_src", "book", `${board.stem}.webp`), webp);
      board.webp = `_src/book/${board.stem}.webp`;
      board.webpSha = sha256(webp);
      board.dependencies = dependencyReceipt(board.path, ctx.outDir);
      if (!board.dom.fatal) board.exportFiles = await captureExports(page, board, T, ctx.exportDir);
    });
  } finally {
    await page.close();
  }
}

/** 最大 limit 個ずつ並べて動かす。 */
async function runPool(items, limit, task) {
  let next = 0;
  const worker = async () => {
    while (next < items.length) {
      const item = items[next];
      next += 1;
      await task(item);
    }
  };
  await Promise.all(Array.from({ length: Math.max(1, Math.min(limit, items.length)) }, worker));
}

/** 前の処理が終わってから fn を動かす (撮影を 1 つずつにする)。 */
function makeExclusive() {
  let chain = Promise.resolve();
  return (fn) => {
    const result = chain.then(fn);
    chain = result.catch(() => {});
    return result;
  };
}

/** タイムゾーンつきの ISO 時刻 (秒まで)。 */
function localIsoSeconds(date = new Date()) {
  const pad = (n) => String(Math.trunc(Math.abs(n))).padStart(2, "0");
  const offset = -date.getTimezoneOffset();
  const sign = offset >= 0 ? "+" : "-";
  return (
    `${date.getFullYear()}-${pad(date.getMonth() + 1)}-${pad(date.getDate())}` +
    `T${pad(date.getHours())}:${pad(date.getMinutes())}:${pad(date.getSeconds())}` +
    `${sign}${pad(offset / 60)}:${pad(offset % 60)}`
  );
}

/**
 * _check/boards.json の中身を作る。--only で通さなかったボードは前回の結果を残す。
 * --check-only のときは書かない (呼び出し側が決める)。
 */
function buildReport(base, boards, runErrors, browser, checkOnly) {
  const old = new Map();
  const previous = loadJson(path.join(base, "_check", "boards.json"), null);
  if (previous && Array.isArray(previous.boards)) {
    for (const entry of previous.boards) if (entry && typeof entry === "object") old.set(String(entry.no), entry);
  }
  const now = localIsoSeconds();
  const entries = [];
  for (const board of boards) {
    if (!board.selected) {
      if (old.has(board.no)) entries.push(old.get(board.no));
      continue;
    }
    const info = board.dom?.info ?? {};
    const png = board.png ?? (checkOnly ? old.get(board.no)?.png ?? null : null);
    const webp = board.webp ?? (checkOnly ? old.get(board.no)?.webp ?? null : null);
    entries.push({
      no: board.no,
      file: board.file,
      png,
      webp,
      type: board.page.type ?? null,
      screens: board.page.screens || [],
      size: board.pngSize,
      notes: info.notes ?? null,
      text_chars: info.text_chars ?? null,
      device_chars: info.device_chars ?? null,
      font_px_min: info.font_px_min ?? null,
      title: info.title ?? null,
      status: boardStatus(board),
      html_sha256: board.sha,
      png_sha256: board.pngSha ?? null,
      webp_sha256: board.webpSha ?? null,
      dependencies: board.dependencies ?? null,
      checked: now,
      mode: checkOnly ? "check-only" : "render",
      errors: board.errors,
      warnings: board.warnings,
      notices: board.notices,
      exports: board.exportFiles.length ? board.exportFiles : board.exports.map((name) => ({ name })),
    });
  }
  const selected = boards.filter((b) => b.selected);
  const summary = {
    errors: selected.reduce((n, b) => n + b.errors.length, 0) + runErrors.length,
    warnings: selected.reduce((n, b) => n + b.warnings.length, 0),
    notices: selected.reduce((n, b) => n + b.notices.length, 0),
    boards: selected.length,
    ok: selected.filter((b) => boardStatus(b) === "ok").length,
    warn: selected.filter((b) => boardStatus(b) === "warn").length,
    ng: selected.filter((b) => boardStatus(b) === "ng").length,
    png: selected.filter((b) => b.png).length,
  };
  return { schema: "briefing-boards-check-v1", updated: now, browser, summary, errors: runErrors, boards: entries };
}

function parsePositive(value, name, fallback, parse) {
  if (value === undefined) return fallback;
  const number = parse(value);
  if (!Number.isFinite(number) || number <= 0) throw new UsageError(`--${name} は正の数にします: ${value}`);
  return number;
}

export async function main(argv) {
  const { options } = parseOptions(argv, {
    dir: "string",
    only: "list",
    "check-only": "boolean",
    browser: "string",
    jobs: "string",
    timeout: "string",
    "allow-warn": "boolean",
    quiet: "boolean",
  });
  if (!options.dir) throw new UsageError("--dir を指定してください (打ち合わせ資料フォルダ)");
  const jobs = parsePositive(options.jobs, "jobs", 3, (v) => (/^\d+$/.test(v) ? Number(v) : NaN));
  const timeoutSec = parsePositive(options.timeout, "timeout", 90, Number);
  const checkOnly = Boolean(options["check-only"]);
  const base = expandHome(options.dir);
  if (!isDir(base)) throw new UsageError(`フォルダがありません: ${base}`);
  const only = options.only?.length ? new Set(options.only) : null;
  const { boards, runErrors, dataPolicy } = loadBoards(base, only);
  const tokensPath = path.join(base, "_src", "tokens.css");
  const tokenCode = isFile(tokensPath) ? "TOKENS-INVALID" : "TOKENS-MISSING";
  const tokenErrors = isFile(tokensPath)
    ? validateDesignTokens(readFileSync(tokensPath, "utf8"))
    : ["tokens.css がありません。build-briefing-scaffold.mjs init --refresh-css で briefing.json の palette から作り直してください"];
  const browser = tokenErrors.length ? null : findBrowser(options.browser);

  const thresholds = boardThresholds();
  const exportDir = path.join(base, "_src", "assets", "export");
  for (const board of boards) Object.assign(board, staticCheck(board.text));
  const { levels, deps } = orderLevels(boards, exportDir);
  selectWithSources(boards, deps);
  const providers = new Set(boards.flatMap((b) => b.exports));

  if (tokenErrors.length) {
    for (const board of boards.filter((b) => b.selected)) {
      board.errors.push(...tokenErrors.map((message) => issue(tokenCode, message, "_src/tokens.css")));
    }
    if (!boards.some((b) => b.selected)) runErrors.push(...tokenErrors.map((message) => issue(tokenCode, message, "_src/tokens.css")));
  } else {
    let session;
    try {
      session = await launchBrowser(browser);
    } catch (error) {
      if (error instanceof ToolMissing) throw error;
      throw new ToolMissing(`ブラウザを起動できません: ${error.message}`);
    }
    const ctx = {
      session,
      thresholds,
      dataPolicy,
      checkOnly,
      timeoutMs: Math.round(timeoutSec * 1000),
      outDir: base,
      exportDir,
      providers,
      exclusive: makeExclusive(),
    };
    try {
      for (const level of levels) {
        const todo = level.filter((b) => b.selected);
        await runPool(todo, jobs, async (board) => {
          try {
            await processBoard(board, ctx);
          } catch (error) {
            // 1 枚の失敗で全体を止めない
            board.errors.push(issue("RENDER-FAILED", `処理中に失敗しました: ${error.message}`));
          }
        });
        for (const board of todo) {
          process.stderr.write(
            `[${board.no}] ${board.file}: ${boardStatus(board)} (error ${board.errors.length} / warn ${board.warnings.length})\n`,
          );
        }
      }
    } finally {
      await session.close();
    }
  }

  const report = buildReport(base, boards, runErrors, browser, checkOnly);
  if (!checkOnly) writeJson(path.join(base, "_check", "boards.json"), report);
  const summary = report.summary;
  const lines = runErrors.map((item) => `error ${item.code} ${item.message}`);
  for (const board of boards) {
    if (!board.selected) continue;
    for (const [level, items] of [["error", board.errors], ["warn ", board.warnings], ["note ", board.notices]]) {
      for (const item of items) {
        lines.push(`${level} ${item.code} _src/${board.file} ${item.message}${item.where ? ` @ ${item.where}` : ""}`);
      }
    }
  }
  if (lines.length) process.stderr.write(`${lines.join("\n")}\n`);
  const failed = summary.errors > 0 || (summary.warnings > 0 && !options["allow-warn"]);
  const status = summary.errors ? "ng" : summary.warnings ? "warn" : "ok";
  const quietLine =
    `boards: ${status} ${summary.boards} 枚 (ok ${summary.ok} / warn ${summary.warn} / ng ${summary.ng}) ` +
    `PNG ${summary.png} 枚 error ${summary.errors} 件 / warn ${summary.warnings} 件 / note ${summary.notices} 件`;
  emitResult(
    {
      status,
      summary,
      check: checkOnly ? null : "_check/boards.json",
      errors: runErrors,
      boards: boards
        .filter((b) => b.selected)
        .map((b) => ({
          no: b.no,
          file: b.file,
          status: boardStatus(b),
          png: b.png,
          webp: b.webp,
          exports: b.exportFiles.map((e) => e.name),
          errors: b.errors,
          warnings: b.warnings,
          notices: b.notices,
        })),
    },
    options.quiet ? quietLine : null,
  );
  return failed ? EXIT.FOUND : EXIT.OK;
}

if (isEntryPoint(import.meta.url)) {
  runCli(main, USAGE);
}
