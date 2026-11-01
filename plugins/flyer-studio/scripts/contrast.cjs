"use strict";
const fs = require("node:fs");
const { PNG } = require("pngjs");

// One parser for the palette accepted by the renderer. Transparent paint may be
// used in fields, but never as the visible text color.
function parseColor(value) {
  const v = String(value).trim().toLowerCase();
  const names = {
    white: [255, 255, 255, 1],
    black: [0, 0, 0, 1],
    transparent: [0, 0, 0, 0],
  };
  if (names[v]) return names[v];
  if (/^#(?:[\da-f]{3,4}|[\da-f]{6}|[\da-f]{8})$/.test(v)) {
    let h = v.slice(1);
    if (h.length < 5) h = [...h].map((c) => c + c).join("");
    return [0, 2, 4]
      .map((i) => parseInt(h.slice(i, i + 2), 16))
      .concat(h.length === 8 ? parseInt(h.slice(6), 16) / 255 : 1);
  }
  const match = v.match(/^rgba?\(([^()]+)\)$/);
  if (match) {
    const parts = match[1].split(/[,\s/]+/).filter(Boolean);
    if (parts.length === 3 || parts.length === 4) {
      const nums = parts.map((s, i) => {
        if (!/^[+-]?(?:\d+(?:\.\d*)?|\.\d+)%?$/.test(s)) return NaN;
        return (
          Number(s.replace("%", "")) *
          (s.endsWith("%") ? (i < 3 ? 2.55 : 0.01) : 1)
        );
      });
      if (nums.length === 3) nums.push(1);
      if (
        nums.every(
          (n, i) => Number.isFinite(n) && n >= 0 && n <= (i < 3 ? 255 : 1),
        )
      )
        return nums;
    }
  }
  throw Error("対応する色形式を指定してください: " + value);
}

function luminance(rgb) {
  return rgb
    .map((c) => c / 255)
    .map((c) => (c <= 0.04045 ? c / 12.92 : ((c + 0.055) / 1.055) ** 2.4))
    .reduce((sum, c, i) => sum + c * [0.2126, 0.7152, 0.0722][i], 0);
}

function contrast(fg, bg) {
  const blended = fg.slice(0, 3).map((n, i) => n * fg[3] + bg[i] * (1 - fg[3]));
  const a = luminance(blended),
    b = luminance(bg);
  return (Math.max(a, b) + 0.05) / (Math.min(a, b) + 0.05);
}

function layoutMetrics(layout) {
  const groups = new Map();
  for (const t of layout.texts) {
    for (const line of t.lines.filter((l) => l.text?.trim())) {
      const old = groups.get(t.group);
      const bounds = {
        x: line.x,
        y: line.y,
        right: line.x + line.w,
        bottom: line.y + line.h,
      };
      groups.set(
        t.group,
        old
          ? {
              x: Math.min(old.x, bounds.x),
              y: Math.min(old.y, bounds.y),
              right: Math.max(old.right, bounds.right),
              bottom: Math.max(old.bottom, bounds.bottom),
            }
          : bounds,
      );
    }
  }
  const bounds = [...groups].map(([group, b]) => ({
    group,
    x: b.x,
    y: b.y,
    w: b.right - b.x,
    h: b.bottom - b.y,
    centerX: (b.x + b.right) / 2,
  }));
  const ordered = [...bounds].sort((a, b) => a.y - b.y);
  return {
    semanticGroups: bounds,
    verticalGaps: ordered
      .slice(1)
      .map((b, i) => ({
        from: ordered[i].group,
        to: b.group,
        mm: b.y - ordered[i].y - ordered[i].h,
      })),
    interpretation:
      "Measured bounds and gaps are diagnostics, not a beauty score. Compare intentional asymmetry and whitespace with the final image.",
  };
}

function inspectContrast(p, variant, layout, out) {
  const artwork = PNG.sync.read(fs.readFileSync(out + "/artwork.png"));
  const issues = [],
    warnings = [],
    samples = [];
  const { width, height } = p.brief.page;
  for (const text of layout.texts) {
    const declared = variant.texts.find((t) => t.id === text.id);
    const fg = parseColor(
      text.computedColor ||
        declared.color ||
        variant.ink ||
        (variant.paper === "white" ? "#142A32" : "#FFFFFF"),
    );
    if (fg[3] <= 0.01)
      issues.push({
        code: "text-invisible",
        detail: text.id + ": text alpha is zero or effectively zero",
      });
    for (const [index, line] of text.lines.entries()) {
      if (!line.text?.trim()) continue;
      const ratios = [];
      // Sample background-only artwork, so glyph pixels cannot inflate contrast.
      for (let row = 0; row < 3; row++)
        for (let col = 0; col < 9; col++) {
          const x = Math.max(
            0,
            Math.min(
              artwork.width - 1,
              Math.floor(
                ((line.x + (line.w * (col + 0.5)) / 9) / width) * artwork.width,
              ),
            ),
          );
          const y = Math.max(
            0,
            Math.min(
              artwork.height - 1,
              Math.floor(
                ((line.y + (line.h * (row + 0.5)) / 3) / height) *
                  artwork.height,
              ),
            ),
          );
          const k = (y * artwork.width + x) * 4;
          ratios.push(
            contrast(fg, [
              artwork.data[k],
              artwork.data[k + 1],
              artwork.data[k + 2],
            ]),
          );
        }
      ratios.sort((a, b) => a - b);
      const target =
        declared.size >= 18 || (declared.size >= 14 && declared.weight >= 700)
          ? 3
          : 4.5;
      const item = {
        id: text.id,
        line: index,
        min: ratios[0],
        median: ratios[13],
        max: ratios.at(-1),
        suggestedRatio: target,
      };
      samples.push(item);
      if (item.max <= 1.2)
        issues.push({
          code: "text-invisible",
          detail:
            text.id + ": sampled text/background colors are indistinguishable",
        });
      else if (item.min < target)
        warnings.push({
          code: "text-contrast-risk",
          detail: text.id + ": inspect the final image, especially over photos",
          ...item,
        });
    }
  }
  return {
    issues,
    warnings,
    samples,
    metrics: layoutMetrics(layout),
    limitation:
      "Sparse sRGB samples are a screen diagnostic, not print accessibility certification. Mixed backgrounds and optical balance require image review.",
  };
}

module.exports = { parseColor, contrast, inspectContrast, layoutMetrics };
