"use strict";

// Plugin 内の Unicode 境界をここに固定する。RegExp は global state を持つため、
// 実行ごとに生成して利用者間で lastIndex を共有しない。
const EMOJI_PATTERN = "\\p{Extended_Pictographic}(?:️|‍\\p{Extended_Pictographic})*";

function findEmoji(text) {
  return String(text).match(new RegExp(EMOJI_PATTERN, "gu")) || [];
}

function findEmojiByLine(text) {
  const hits = [];
  String(text).split("\n").forEach((line, index) => {
    const emoji = findEmoji(line);
    if (emoji.length > 0) hits.push({ line: index + 1, emoji });
  });
  return hits;
}

function collectStringLeaves(value, field = "") {
  if (typeof value === "string") return [{ field: field || "$", value }];
  if (Array.isArray(value)) {
    return value.flatMap((item, index) => collectStringLeaves(item, `${field}[${index}]`));
  }
  if (value && typeof value === "object") {
    return Object.entries(value).flatMap(([key, item]) =>
      collectStringLeaves(item, field ? `${field}.${key}` : key));
  }
  return [];
}

function findDisallowedSymbols(text, allowedSymbols) {
  const allowed = new Set(allowedSymbols);
  return [...String(text)].filter((character) => {
    if (allowed.has(character)) return false;
    if (findEmoji(character).length > 0) return false;
    return /\p{S}/u.test(character);
  });
}

function validateVisualTextLeaves(value, textRules) {
  const violations = [];
  for (const leaf of collectStringLeaves(value)) {
    for (const word of textRules.forbiddenWords) {
      if (leaf.value.includes(word)) {
        violations.push({
          field: leaf.field,
          rule: "VA-C05",
          detail: `禁止語「${word}」を含む: "${leaf.value}"`,
        });
      }
    }

    const emoji = findEmoji(leaf.value);
    if (emoji.length > 0) {
      violations.push({
        field: leaf.field,
        rule: "VA-C06",
        detail: `絵文字を含む: ${emoji.join(" ")}`,
      });
    }

    const symbols = [...new Set(findDisallowedSymbols(leaf.value, textRules.allowedSymbols))];
    if (symbols.length > 0) {
      violations.push({
        field: leaf.field,
        rule: "VA-C08",
        detail: `未許可の記号を含む: ${symbols.join(" ")}。許可: ${textRules.allowedSymbols.join(" ")}`,
      });
    }
  }
  return violations;
}

module.exports = {
  collectStringLeaves,
  findEmoji,
  findEmojiByLine,
  validateVisualTextLeaves,
};
