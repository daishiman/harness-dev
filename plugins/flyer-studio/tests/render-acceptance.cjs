#!/usr/bin/env node
"use strict";
const path = require("node:path"),
  { fixture } = require("./fixture.cjs"),
  R = require("../scripts/render.cjs"),
  C = require("../scripts/checks.cjs");
(async () => {
  if (!process.argv[2])
    throw Error(
      "新しい出力先を指定: node tests/render-acceptance.cjs /absolute/path/to/new-smoke",
    );
  const dir = path.resolve(process.argv[2]);
  fixture(dir);
  require("../scripts/essence.cjs").baseline(dir, { request: "既存背景を明示再利用する描画経路の試験" });
  await R.render(dir);
  const v = C.verify(dir);
  console.log(JSON.stringify(v, null, 2));
  if (v.fail) throw Error("描画検査を解消してください");
  console.log("目視台帳: " + C.reviewTemplate(dir));
  console.log(
    "既存背景を明示再利用した2案の描画経路試験です。新しい背景の生成試験ではありません。全案print.pngを実見してから目視台帳を更新し、受入試験へ進んでください。",
  );
})().catch((e) => {
  console.error(e.message);
  process.exitCode = 1;
});
