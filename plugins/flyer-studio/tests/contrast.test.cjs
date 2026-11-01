"use strict";
const test = require("node:test"),
  assert = require("node:assert/strict");
const {
  parseColor,
  contrast,
  layoutMetrics,
} = require("../scripts/contrast.cjs");

test("CSS color parser preserves alpha and rejects invalid hex", () => {
  assert.deepEqual(parseColor("#fff0"), [255, 255, 255, 0]);
  assert.deepEqual(parseColor("#00000000"), [0, 0, 0, 0]);
  assert.deepEqual(parseColor("rgba(0,0,0,0)"), [0, 0, 0, 0]);
  assert.deepEqual(parseColor("transparent"), [0, 0, 0, 0]);
  assert.throws(() => parseColor("#12345"));
  assert.throws(() => parseColor("rgba(0,0,0,2)"));
});

test("invisible paint and same-color backgrounds have no contrast", () => {
  assert.equal(contrast([255, 255, 255, 0], [0, 0, 0]), 1);
  assert.equal(contrast([255, 255, 255, 1], [255, 255, 255]), 1);
  assert.equal(contrast([0, 0, 0, 1], [255, 255, 255]), 21);
});

test("layout diagnostics measure actual glyph groups rather than frame centers", () => {
  const layout = {
    texts: [
      { group: "hero", lines: [{ text: "主題", x: 10, y: 10, w: 100, h: 20 }] },
      { group: "event", lines: [{ text: "日時", x: 60, y: 50, w: 80, h: 10 }] },
    ],
  };
  const r = layoutMetrics(layout);
  assert.equal(r.semanticGroups[0].centerX, 60);
  assert.deepEqual(r.verticalGaps, [{ from: "hero", to: "event", mm: 20 }]);
  assert.match(r.interpretation, /not a beauty score/);
});
