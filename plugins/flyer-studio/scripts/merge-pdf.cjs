#!/usr/bin/env node
"use strict";
// Copy PDF pages as PDF objects. Re-rendering or decimal rounding can change Type3 glyph edges.
const fs = require("node:fs");
const path = require("node:path");
const crypto = require("node:crypto");
const { PDFDocument } = require("pdf-lib");
const hash = bytes => crypto.createHash("sha256").update(bytes).digest("hex");

async function mergePDF(output, inputs) {
  if (typeof output !== "string" || !Array.isArray(inputs) || !inputs.length)
    throw Error("出力PDFと1件以上の入力PDFが必要です");
  const destination = path.resolve(output);
  const destinationReal = fs.existsSync(destination) ? fs.realpathSync(destination) : destination;
  const files = inputs.map(input => fs.realpathSync(path.resolve(input)));
  if (files.includes(destinationReal) || files.includes(destination))
    throw Error("入力PDFと出力PDFを同じファイルにできません");

  // Freeze bytes before the first asynchronous boundary.
  const snapshots = files.map(file => {
    const bytes = fs.readFileSync(file);
    return { file, bytes, sha256: hash(bytes) };
  });
  const merged = await PDFDocument.create();
  const sources = [];
  for (const { file, bytes, sha256 } of snapshots) {
    const source = await PDFDocument.load(bytes, { updateMetadata: false });
    if (!source.getPageCount()) throw Error("入力PDFにページがありません: " + file);
    const pages = await merged.copyPages(source, source.getPageIndices());
    for (const page of pages) merged.addPage(page);
    sources.push({ file, sha256, pages: pages.length });
  }
  const bytes = await merged.save({ useObjectStreams: false, updateFieldAppearances: false });
  for (const source of sources)
    if (hash(fs.readFileSync(source.file)) !== source.sha256)
      throw Error("結合中に入力PDFが変更されました: " + source.file);

  fs.mkdirSync(path.dirname(destination), { recursive: true });
  const temporary = destination + "." + crypto.randomBytes(8).toString("hex") + ".tmp";
  try {
    fs.writeFileSync(temporary, bytes, { flag: "wx" });
    fs.renameSync(temporary, destination);
  } finally {
    fs.rmSync(temporary, { force: true });
  }
  return { file: destination, pageCount: merged.getPageCount(), pdfSha256: hash(bytes), method: "pdf-lib-copyPages", sources };
}

if (require.main === module) {
  const [output, ...inputs] = process.argv.slice(2);
  mergePDF(output, inputs)
    .then(result => console.log(JSON.stringify(result)))
    .catch(error => { console.error(error.message); process.exitCode = 1; });
}
module.exports = { mergePDF };
