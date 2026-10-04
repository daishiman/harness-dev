/**
 * ボード HTML を読むための小さな HTML 読み取り (npm 依存なし)。
 *
 * ボードは雛形から作る素直な HTML なので、ブラウザと同じ厳密さは要らない。決めごと:
 * - script と style の中身は文字として扱わない (生のまま読み飛ばす)。コメント・<!doctype>・<?...?> は捨てる
 * - タグ名と属性名は小文字にそろえ、属性の値と本文の実体参照 (&amp; &#12354; など) は戻す
 * - 閉じタグは、開いている要素を内側からさかのぼって同じ名前のところで閉じる。対応が無ければ無視する
 * - <li> の中で次の <li>、<p> の中で次の <p> が始まったら前のほうを閉じる (閉じタグの書き忘れに強くする)
 */

const RAW_TEXT_TAGS = new Set(["script", "style"]);
export const VOID_TAGS = new Set(["area", "base", "br", "col", "embed", "hr", "img", "input", "link", "meta", "source", "track", "wbr"]);

const NAMED_ENTITIES = {
  amp: "&", lt: "<", gt: ">", quot: '"', apos: "'", nbsp: " ", copy: "©", reg: "®", trade: "™",
  times: "×", divide: "÷", plusmn: "±", deg: "°", yen: "¥", middot: "·", bull: "•", hellip: "…",
  mdash: "—", ndash: "–", lsquo: "‘", rsquo: "’", ldquo: "“", rdquo: "”", laquo: "«", raquo: "»",
  larr: "←", rarr: "→", uarr: "↑", darr: "↓", harr: "↔", ensp: " ", emsp: " ", thinsp: " ",
  zwj: "‍", zwnj: "‌", shy: "­", sect: "§", para: "¶", check: "✓", cross: "✗",
};
// セミコロンなしでも戻す古い書き方 (ブラウザと Python の html.unescape が戻すもののうち、よく出るもの)
const LEGACY_ENTITIES = new Set(["amp", "lt", "gt", "quot", "nbsp", "copy", "reg"]);

/** 実体参照を文字に戻す。知らない名前はそのまま残す。 */
export function decodeEntities(text) {
  if (!text.includes("&")) return text;
  return text.replace(/&(#[xX][0-9a-fA-F]+|#\d+|[A-Za-z][A-Za-z0-9]*)(;?)/g, (whole, body, semi) => {
    if (body[0] === "#") {
      const code = body[1] === "x" || body[1] === "X" ? Number.parseInt(body.slice(2), 16) : Number.parseInt(body.slice(1), 10);
      if (!Number.isFinite(code) || code <= 0 || code > 0x10ffff || (code >= 0xd800 && code <= 0xdfff)) return "�";
      return String.fromCodePoint(code);
    }
    if (!Object.hasOwn(NAMED_ENTITIES, body)) return whole;
    if (!semi && !LEGACY_ENTITIES.has(body)) return whole;
    return NAMED_ENTITIES[body];
  });
}

const ATTR_RE = /([^\s"'<>/=]+)(?:\s*=\s*(?:"([^"]*)"|'([^']*)'|([^\s"'=<>`]+)))?/g;

function parseAttrs(source) {
  const attrs = {};
  ATTR_RE.lastIndex = 0;
  for (let m = ATTR_RE.exec(source); m; m = ATTR_RE.exec(source)) {
    const name = m[1].toLowerCase();
    if (Object.hasOwn(attrs, name)) continue; // ブラウザと同じく最初の値を使う
    const raw = m[2] ?? m[3] ?? m[4];
    attrs[name] = raw === undefined ? null : decodeEntities(raw);
  }
  return attrs;
}

/** 開きタグの終わりの > を探す (引用符の中の > は飛ばす)。見つからなければ -1。 */
function findTagEnd(text, from) {
  let quote = null;
  for (let i = from; i < text.length; i += 1) {
    const ch = text[i];
    if (quote) {
      if (ch === quote) quote = null;
    } else if (ch === '"' || ch === "'") {
      quote = ch;
    } else if (ch === ">") {
      return i;
    }
  }
  return -1;
}

/**
 * HTML を {type:"start", tag, attrs, selfClosing} / {type:"end", tag} / {type:"text", text} の並びにする。
 * 文字はタグとタグの間ごとに 1 つ (Python の HTMLParser(convert_charrefs=True) と同じ区切り)。
 */
export function tokenizeHtml(text) {
  const tokens = [];
  let i = 0;
  let textStart = 0;
  const flush = (end) => {
    if (end > textStart) tokens.push({ type: "text", text: decodeEntities(text.slice(textStart, end)) });
  };
  while (i < text.length) {
    const lt = text.indexOf("<", i);
    if (lt === -1) break;
    const next = text[lt + 1] ?? "";
    if (text.startsWith("<!--", lt)) {
      flush(lt);
      const end = text.indexOf("-->", lt + 4);
      i = textStart = end === -1 ? text.length : end + 3;
      continue;
    }
    if (next === "!" || next === "?") {
      flush(lt);
      const end = text.startsWith("<![CDATA[", lt) ? text.indexOf("]]>", lt) : text.indexOf(">", lt);
      i = textStart = end === -1 ? text.length : end + (text.startsWith("<![CDATA[", lt) ? 3 : 1);
      continue;
    }
    if (next === "/") {
      const m = /^<\/([A-Za-z][^\t\n\r\f />\x00]*)[^>]*>/.exec(text.slice(lt, lt + 256));
      if (!m) {
        i = lt + 1;
        continue;
      }
      flush(lt);
      tokens.push({ type: "end", tag: m[1].toLowerCase() });
      i = textStart = lt + m[0].length;
      continue;
    }
    if (!/[A-Za-z]/.test(next)) {
      i = lt + 1;
      continue;
    }
    const end = findTagEnd(text, lt + 1);
    if (end === -1) break;
    flush(lt);
    const inner = text.slice(lt + 1, end);
    const name = /^[A-Za-z][^\t\n\r\f />\x00]*/.exec(inner)[0];
    const tag = name.toLowerCase();
    const rest = inner.slice(name.length);
    const selfClosing = /\/\s*$/.test(rest);
    tokens.push({ type: "start", tag, attrs: parseAttrs(rest.replace(/\/\s*$/, "")), selfClosing });
    i = textStart = end + 1;
    if (RAW_TEXT_TAGS.has(tag) && !selfClosing) {
      const close = new RegExp(`</${tag}\\s*>`, "i").exec(text.slice(i));
      const stop = close ? i + close.index : text.length;
      if (stop > i) tokens.push({ type: "raw", tag, text: text.slice(i, stop) });
      if (close) tokens.push({ type: "end", tag });
      i = textStart = close ? stop + close[0].length : text.length;
    }
  }
  flush(text.length);
  return tokens;
}

/** 要素の節。children には節か文字列が入る。 */
function makeNode(tag, attrs, parent) {
  return { tag, attrs, children: [], parent };
}

/** HTML を木にする。script / style の中身は木に入れない。返り値は tag="#root" の節。 */
export function parseHtmlTree(text) {
  const root = makeNode("#root", {}, null);
  let cur = root;
  for (const token of tokenizeHtml(text)) {
    if (token.type === "start") {
      if ((token.tag === "li" && cur.tag === "li") || (token.tag === "p" && cur.tag === "p")) cur = cur.parent;
      const attrs = {};
      for (const [k, v] of Object.entries(token.attrs)) attrs[k] = v ?? "";
      const node = makeNode(token.tag, attrs, cur);
      cur.children.push(node);
      if (!VOID_TAGS.has(token.tag) && !token.selfClosing) cur = node;
    } else if (token.type === "end") {
      let node = cur;
      while (node !== root && node.tag !== token.tag) node = node.parent;
      if (node !== root) cur = node.parent;
    } else if (token.type === "text") {
      cur.children.push(token.text);
    }
  }
  return root;
}

/** 子孫の要素を文書順に返す (自分は含めない)。 */
export function* iterNodes(node) {
  for (const child of node.children) {
    if (typeof child === "string") continue;
    yield child;
    yield* iterNodes(child);
  }
}

export function classesOf(node) {
  return new Set((node.attrs.class || "").split(/\s+/).filter(Boolean));
}

/** 要素の中の文字をつなぎ、空白を 1 つにまとめる。 */
export function textOf(node) {
  const parts = [];
  const walk = (n) => {
    for (const child of n.children) {
      if (typeof child === "string") parts.push(child);
      else walk(child);
    }
  };
  walk(node);
  return parts.join("").replace(/\s+/g, " ").trim();
}
