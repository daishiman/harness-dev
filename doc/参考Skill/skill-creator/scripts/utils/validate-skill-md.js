// scripts/utils/validate-skill-md.js
// Codex SKILL.md 検証ルール R-01〜R-06 の共通バリデータ。
// generate_skill_md.js / init_skill.js / quick_validate.js から再利用される。

import { parse } from "yaml";

export const MAX_DESC_LENGTH = 1024;
export const MAX_ANCHORS = 5;
export const MAX_TRIGGER_KEYWORDS = 15;

/**
 * SKILL.md 全文を検証する。
 *
 * @param {string} content - SKILL.md の全文
 * @returns {{ ok: boolean, errors: string[], description: string|null, name: string|null }}
 */
export function validateSkillMdContent(content) {
  const errors = [];

  if (typeof content !== "string") {
    return { ok: false, errors: ["R-00: content が string ではありません"], description: null, name: null };
  }

  // R-06: BOM 検出
  if (content.charCodeAt(0) === 0xfeff) {
    errors.push("R-06: BOM 付き UTF-8 は frontmatter 認識不可");
  }

  // R-01: frontmatter 必須
  const m = content.match(/^---\n([\s\S]*?)\n---/);
  if (!m) {
    errors.push("R-01: YAML frontmatter (--- 区切り) が見つかりません");
    return { ok: false, errors, description: null, name: null };
  }

  const fmText = m[1];
  const parsed = parseFrontmatterYaml(fmText);
  if (!parsed.ok) {
    errors.push("R-07: YAML frontmatter 構文が壊れています: " + parsed.message);
    const fallbackDescription = extractDescription(fmText);
    if (
      fallbackDescription.kind === "string" &&
      typeof fallbackDescription.value === "string" &&
      fallbackDescription.value.trim().length > MAX_DESC_LENGTH
    ) {
      errors.push(
        `R-04: description が ${MAX_DESC_LENGTH} 文字を超えています (${fallbackDescription.value.trim().length}字)。Anchors を references/anchors.md へ、長尺 keywords を references/keywords.md / triggers.md へ退避してください。`,
      );
    }
    return { ok: false, errors, description: null, name: null };
  }

  const frontmatter = parsed.value;
  const name = frontmatter && typeof frontmatter === "object" ? frontmatter.name : undefined;
  const desc = frontmatter && typeof frontmatter === "object" ? frontmatter.description : undefined;

  if (typeof name === "undefined") {
    errors.push("R-05: name フィールドが見つかりません");
  } else if (typeof name !== "string" || !name.trim()) {
    errors.push("R-05: name フィールドは空でない string が必須です");
  }

  if (typeof desc === "undefined") {
    errors.push("R-02: description フィールドが見つかりません");
  } else if (!isStringObject(desc)) {
    errors.push("R-03: description が sequence 型です（string が必須）");
  }

  const normalizedDesc = typeof desc === "string" ? desc.trim() : null;
  if (typeof normalizedDesc === "string") {
    if (normalizedDesc.length > MAX_DESC_LENGTH) {
      errors.push(
        `R-04: description が ${MAX_DESC_LENGTH} 文字を超えています (${normalizedDesc.length}字)。Anchors を references/anchors.md へ、長尺 keywords を references/keywords.md / triggers.md へ退避してください。`,
      );
    }
  }

  return {
    ok: errors.length === 0,
    errors,
    description: normalizedDesc,
    name: typeof name === "string" ? name : null,
  };
}

function parseFrontmatterYaml(fmText) {
  try {
    return { ok: true, value: parse(fmText) };
  } catch (e) {
    return { ok: false, value: null, message: e.message };
  }
}

function isStringObject(value) {
  return typeof value === "string" || value instanceof String;
}

/**
 * frontmatter テキストから description フィールドを抽出する（簡易 YAML パーサ）。
 * literal block (|) / double-quoted scalar / plain scalar に対応。
 *
 * @param {string} fmText
 * @returns {{ kind: "string"|"sequence"|"missing"|"yaml-error", value: string|null, message?: string }}
 */
export function extractDescription(fmText) {
  return extractScalarField(fmText, "description");
}

/**
 * frontmatter テキストから単一 scalar フィールドを抽出する。
 * literal block (|) / double-quoted scalar / single-quoted scalar / plain scalar に対応。
 *
 * @param {string} fmText
 * @param {string} fieldName
 * @returns {{ kind: "string"|"sequence"|"missing"|"yaml-error", value: string|null, message?: string }}
 */
export function extractScalarField(fmText, fieldName) {
  const lines = fmText.split("\n");
  const fieldPattern = new RegExp(`^${fieldName}\\s*:`);
  const fieldPrefix = new RegExp(`^${fieldName}\\s*:\\s*`);
  const idx = lines.findIndex((l) => fieldPattern.test(l));
  if (idx === -1) {
    return { kind: "missing", value: null };
  }

  const head = lines[idx].replace(fieldPrefix, "");

  // sequence 型 (- で始まるブロック)
  if (head.trim() === "" && lines[idx + 1] && /^\s*-\s/.test(lines[idx + 1])) {
    return { kind: "sequence", value: null };
  }
  if (/^\s*-\s/.test(head)) {
    return { kind: "sequence", value: null };
  }

  // literal block: `|` または `|-`
  if (/^\|[-+]?\s*$/.test(head.trim())) {
    const collected = [];
    for (let i = idx + 1; i < lines.length; i++) {
      const line = lines[i];
      if (line.startsWith("  ")) {
        collected.push(line.replace(/^ {2}/, ""));
      } else if (line.trim() === "") {
        collected.push("");
      } else {
        break;
      }
    }
    return { kind: "string", value: collected.join("\n").trim() };
  }

  // double-quoted scalar
  if (head.startsWith('"')) {
    // 末尾のダブルクォートまで複数行を結合
    let buf = head;
    if (!isClosedDoubleQuoted(buf)) {
      for (let i = idx + 1; i < lines.length; i++) {
        buf += "\n" + lines[i];
        if (isClosedDoubleQuoted(buf)) break;
      }
    }
    try {
      return { kind: "string", value: JSON.parse(buf) };
    } catch (e) {
      return { kind: "yaml-error", value: null, message: e.message };
    }
  }

  // single-quoted scalar
  if (head.startsWith("'")) {
    const matched = head.match(/^'(.*)'\s*$/);
    if (matched) return { kind: "string", value: matched[1].replace(/''/g, "'") };
    return { kind: "yaml-error", value: null, message: "single-quoted scalar が閉じていません" };
  }

  // plain scalar
  return { kind: "string", value: head.trim() };
}

function isClosedDoubleQuoted(buf) {
  // 先頭の " を除き、エスケープされていない " で終わるか
  if (!buf.startsWith('"')) return false;
  let escaped = false;
  for (let i = 1; i < buf.length; i++) {
    const c = buf[i];
    if (escaped) {
      escaped = false;
      continue;
    }
    if (c === "\\") {
      escaped = true;
      continue;
    }
    if (c === '"') {
      return i === buf.length - 1;
    }
  }
  return false;
}
