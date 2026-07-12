/**
 * template-engine.js — Mustache subset (依存ゼロ)
 *
 * 対応:
 *   {{var}}        : HTMLエスケープ済み変数展開（ネストキー対応 a.b.c）
 *   {{{var}}}      : 生HTML（エスケープなし）
 *   {{#array}}...{{/array}}  : 配列繰り返し（要素は context として展開、{{.}} は要素自身）
 *   {{#cond}}...{{/cond}}    : 真値ブロック（配列以外でも truthy なら1回展開）
 *   {{^cond}}...{{/cond}}    : 反転ブロック（falsy で1回展開）
 *   {{>partial}}   : partials マップから部分テンプレを取り出して再帰展開
 *   {{!comment}}   : コメント（空文字に置換）
 *
 * SR-12-08: 出力は分離されるが、ここでは断片HTMLを生成するのみ。
 */
'use strict';

function escapeHtml(str) {
  if (str === null || str === undefined) return '';
  return String(str)
    .replace(/&/g, '&amp;')
    .replace(/</g, '&lt;')
    .replace(/>/g, '&gt;')
    .replace(/"/g, '&quot;')
    .replace(/'/g, '&#39;');
}

function lookup(ctxStack, key) {
  if (key === '.') return ctxStack[ctxStack.length - 1];
  const parts = key.split('.');
  // dotted lookup from innermost ctx
  for (let i = ctxStack.length - 1; i >= 0; i--) {
    let v = ctxStack[i];
    let ok = true;
    for (const p of parts) {
      if (v && typeof v === 'object' && p in v) {
        v = v[p];
      } else {
        ok = false;
        break;
      }
    }
    if (ok) return v;
  }
  return undefined;
}

/**
 * Tokenize template into a flat list, then build a tree.
 */
function tokenize(tpl) {
  const re = /\{\{([!#^/>{]?)\s*([^}]+?)\s*\}?\}\}/g;
  const tokens = [];
  let last = 0;
  let m;
  while ((m = re.exec(tpl)) !== null) {
    if (m.index > last) tokens.push({ type: 'text', value: tpl.slice(last, m.index) });
    const sigil = m[1];
    const name = m[2].trim();
    if (sigil === '!') {
      // comment
    } else if (sigil === '#') {
      tokens.push({ type: 'section', name });
    } else if (sigil === '^') {
      tokens.push({ type: 'inverted', name });
    } else if (sigil === '/') {
      tokens.push({ type: 'end', name });
    } else if (sigil === '>') {
      tokens.push({ type: 'partial', name });
    } else if (sigil === '{') {
      tokens.push({ type: 'raw', name });
    } else {
      tokens.push({ type: 'var', name });
    }
    last = re.lastIndex;
  }
  if (last < tpl.length) tokens.push({ type: 'text', value: tpl.slice(last) });
  return tokens;
}

function buildTree(tokens) {
  const root = { type: 'root', children: [] };
  const stack = [root];
  for (const t of tokens) {
    const top = stack[stack.length - 1];
    if (t.type === 'section' || t.type === 'inverted') {
      const node = { ...t, children: [] };
      top.children.push(node);
      stack.push(node);
    } else if (t.type === 'end') {
      stack.pop();
    } else {
      top.children.push(t);
    }
  }
  return root;
}

function renderNode(node, ctxStack, partials) {
  if (node.type === 'root') {
    return node.children.map((c) => renderNode(c, ctxStack, partials)).join('');
  }
  if (node.type === 'text') return node.value;
  if (node.type === 'var') {
    return escapeHtml(lookup(ctxStack, node.name));
  }
  if (node.type === 'raw') {
    const v = lookup(ctxStack, node.name);
    return v === null || v === undefined ? '' : String(v);
  }
  if (node.type === 'partial') {
    const p = partials[node.name];
    if (!p) return '';
    return render(p, ctxStack[ctxStack.length - 1], partials, ctxStack);
  }
  if (node.type === 'section') {
    const v = lookup(ctxStack, node.name);
    if (!v) return '';
    if (Array.isArray(v)) {
      return v
        .map((item) => {
          const newCtx = item !== null && typeof item === 'object' ? item : item;
          return node.children
            .map((c) => renderNode(c, [...ctxStack, newCtx], partials))
            .join('');
        })
        .join('');
    }
    if (typeof v === 'object') {
      return node.children.map((c) => renderNode(c, [...ctxStack, v], partials)).join('');
    }
    return node.children.map((c) => renderNode(c, ctxStack, partials)).join('');
  }
  if (node.type === 'inverted') {
    const v = lookup(ctxStack, node.name);
    const falsy = !v || (Array.isArray(v) && v.length === 0);
    if (!falsy) return '';
    return node.children.map((c) => renderNode(c, ctxStack, partials)).join('');
  }
  return '';
}

function render(template, context, partials, parentStack) {
  const tokens = tokenize(template);
  const tree = buildTree(tokens);
  const stack = parentStack ? [...parentStack] : [context];
  if (parentStack && context !== parentStack[parentStack.length - 1]) stack.push(context);
  return renderNode(tree, stack, partials || {});
}

module.exports = { render, escapeHtml };
