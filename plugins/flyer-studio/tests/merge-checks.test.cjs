"use strict";
const test = require("node:test");
const assert = require("node:assert/strict");
const fs = require("node:fs");
const os = require("node:os");
const path = require("node:path");
const cp = require("node:child_process");
const crypto = require("node:crypto");

const source = process.env.FLYER_ACCEPTANCE_PROJECT;
const sha = (file) =>
  crypto.createHash("sha256").update(fs.readFileSync(file)).digest("hex");

function copiedPDFs(run) {
  const dir = fs.mkdtempSync(path.join(os.tmpdir(), "flyer-merge-test-"));
  try {
    const scene = JSON.parse(
      fs.readFileSync(path.join(source, "scene.json"), "utf8"),
    );
    const p = { scene };
    const rows = scene.variants.map((v) => {
      const original = path.join(source, "out", v.id, "print.pdf");
      const render = JSON.parse(
        fs.readFileSync(path.join(source, "out", v.id, "render.json"), "utf8"),
      );
      const dest = path.join(dir, "out", v.id);
      fs.mkdirSync(dest, { recursive: true });
      fs.copyFileSync(original, path.join(dest, "print.pdf"));
      return {
        id: v.id,
        pdfSha256: render.pdfSha256,
        pngSha256: render.pngSha256,
      };
    });
    const merge = (file, variants) =>
      cp.execFileSync(
        process.execPath,
        [
          path.resolve(__dirname, "../scripts/merge-pdf.cjs"),
          path.join(dir, "out", file),
          ...variants.map((v) => path.join(dir, "out", v.id, "print.pdf")),
        ],
        { stdio: "pipe" },
      );
    merge("all.pdf", scene.variants);
    const white = scene.variants.filter((v) => v.paper === "white");
    if (white.length) merge("white.pdf", white);
    return run({ dir, p, rows, merge });
  } finally {
    fs.rmSync(dir, { recursive: true, force: true });
  }
}

test(
  "結合した実PDFは全案・白案の順序とページ内容が一致すると通る",
  { skip: !source },
  () => {
    const { verifyCombined } = require("../scripts/merge-checks.cjs");
    copiedPDFs(({ dir, p, rows }) => {
      const result = verifyCombined(dir, p, rows);
      assert.equal(result.fail, 0, JSON.stringify(result.issues));
      assert.equal(result.dpi, 150);
      assert.equal(
        result.pages.length,
        p.scene.variants.length +
          p.scene.variants.filter((v) => v.paper === "white").length,
      );
      assert.ok(
        result.pages.every(
          (page) => page.pixelSha256 === page.sourcePixelSha256,
        ),
      );
      assert.equal(
        result.files.find((file) => file.file === "all.pdf").pageCount,
        p.scene.variants.length,
      );
      for (const row of rows)
        assert.equal(
          sha(path.join(dir, "out", row.id, "print.pdf")),
          row.pdfSha256,
        );
    });
  },
);

test(
  "結合した実PDFは逆順ページと元PDFのSHA不一致を拒否する",
  { skip: !source },
  () => {
    const { verifyCombined } = require("../scripts/merge-checks.cjs");
    copiedPDFs(({ dir, p, rows, merge }) => {
      assert.ok(rows.length >= 2, "逆順試験には異なる2案以上が必要");
      fs.rmSync(path.join(dir, "out", "all.pdf"));
      merge("all.pdf", [...p.scene.variants].reverse());
      const reversed = verifyCombined(dir, p, rows);
      assert.ok(reversed.fail > 0);
      assert.ok(
        reversed.issues.some((issue) => issue.code === "combined-page-content"),
      );
      const forged = rows.map((row, i) =>
        i ? row : { ...row, pdfSha256: "0".repeat(64) },
      );
      const changed = verifyCombined(dir, p, forged);
      assert.ok(
        changed.issues.some((issue) => issue.code === "combined-source-sha"),
      );
    });
  },
);

// Minimal vector fixture: no supplied photos or proprietary font outlines.
function type3PDF(color='0.09 0.22 0.2'){
 const content=color+' rg\nBT /F1 24 Tf 1 0 0 1 30.2399982 80 Tm (A) Tj ET\n';
 const glyph='1000 0 d0\n0 0 m\n1000 0 l\n0 -1000 l\nh f\n';
 const objects=['<< /Type /Catalog /Pages 2 0 R >>','<< /Type /Pages /Count 1 /Kids [3 0 R] >>','<< /Type /Page /Parent 2 0 R /MediaBox [0 0 200 200] /Resources << /Font << /F1 5 0 R >> >> /Contents 4 0 R >>',`<< /Length ${content.length} >>\nstream\n${content}endstream`,'<< /Type /Font /Subtype /Type3 /Name /F1 /FontMatrix [.00100000005 0 0 -.00100000005 0 0] /FontBBox [0 -1000 1000 0] /FirstChar 65 /LastChar 65 /Widths [1000] /Encoding << /Type /Encoding /Differences [65 /A] >> /CharProcs << /A 6 0 R >> /Resources << >> >>',`<< /Length ${glyph.length} >>\nstream\n${glyph}endstream`];
 let pdf='%PDF-1.4\n',offsets=[0];for(let i=0;i<objects.length;i++){offsets.push(Buffer.byteLength(pdf));pdf+=(i+1)+' 0 obj\n'+objects[i]+'\nendobj\n';}const xref=Buffer.byteLength(pdf);pdf+='xref\n0 '+(objects.length+1)+'\n0000000000 65535 f \n'+offsets.slice(1).map(n=>String(n).padStart(10,'0')+' 00000 n \n').join('')+'trailer\n<< /Size '+(objects.length+1)+' /Root 1 0 R >>\nstartxref\n'+xref+'\n%%EOF\n';return Buffer.from(pdf);
}

function type3Project(t) {
  const dir = fs.mkdtempSync(path.join(os.tmpdir(), "flyer-type3-merge-"));
  t.after(() => fs.rmSync(dir, { recursive: true, force: true }));
  const rows = ["F01", "F02"].map((id, index) => {
    fs.mkdirSync(path.join(dir, "out", id), { recursive: true });
    const file = path.join(dir, "out", id, "print.pdf");
    fs.writeFileSync(file, type3PDF(index ? "0.7 0.1 0.2" : "0.09 0.22 0.2"));
    return { id, pdfSha256: sha(file) };
  });
  return { dir, rows, p: { scene: { variants: [{ id: "F01", paper: "color" }, { id: "F02", paper: "white" }] } } };
}

test("page-copy merge preserves high precision Type3 FontMatrix and source files", async (t) => {
  const { mergePDF } = require("../scripts/merge-pdf.cjs");
  const { PDFDocument, PDFName } = require("pdf-lib");
  const { dir, rows } = type3Project(t);
  const files = rows.map(row => path.join(dir, "out", row.id, "print.pdf"));
  const output = path.join(dir, "out", "all.pdf");
  await mergePDF(output, files);
  const merged = await PDFDocument.load(fs.readFileSync(output));
  assert.equal(merged.getPageCount(), 2);
  for (const page of merged.getPages()) {
    const font = page.node.Resources().lookup(PDFName.of("Font")).lookup(PDFName.of("F1"));
    const matrix = font.lookup(PDFName.of("FontMatrix"));
    assert.equal(matrix.get(0).asNumber(), 0.00100000005);
    assert.equal(matrix.get(3).asNumber(), -0.00100000005);
  }
  for (const row of rows) assert.equal(sha(path.join(dir, "out", row.id, "print.pdf")), row.pdfSha256);
});

test("page-copy merge matches every real Type3 page pixel without tolerance", { skip: cp.spawnSync("pdftoppm", ["-v"]).status !== 0 }, async (t) => {
  const { mergePDF } = require("../scripts/merge-pdf.cjs");
  const { verifyCombined } = require("../scripts/merge-checks.cjs");
  const { dir, rows, p } = type3Project(t);
  const files = rows.map(row => path.join(dir, "out", row.id, "print.pdf"));
  await mergePDF(path.join(dir, "out", "all.pdf"), files);
  cp.execFileSync(process.execPath, [path.resolve(__dirname, "../scripts/merge-pdf.cjs"), path.join(dir, "out", "white.pdf"), files[1]], { stdio: "pipe" });
  const result = verifyCombined(dir, p, rows);
  assert.equal(result.fail, 0, JSON.stringify(result.issues));
  assert.equal(result.pages.length, 3);
  assert.ok(result.pages.every(page => page.pixelSha256 === page.sourcePixelSha256));
  await mergePDF(path.join(dir, "out", "all.pdf"), [...files].reverse());
  assert.ok(verifyCombined(dir, p, rows).issues.some(issue => issue.code === "combined-page-content"));
});

test("merge rejects overwriting a source PDF and leaves an existing output intact on failure", async (t) => {
  const { mergePDF } = require("../scripts/merge-pdf.cjs");
  const { dir, rows } = type3Project(t);
  const input = path.join(dir, "out", "F01", "print.pdf");
  await assert.rejects(() => mergePDF(input, [input]), /入力|同じ/);
  assert.equal(sha(input), rows[0].pdfSha256);
  const output = path.join(dir, "out", "existing.pdf");
  fs.writeFileSync(output, "keep existing output until merge succeeds");
  await assert.rejects(() => mergePDF(output, [path.join(dir, "missing.pdf")]));
  assert.equal(fs.readFileSync(output, "utf8"), "keep existing output until merge succeeds");
});

test("merge rejects a source changed while its pages are copied", async (t) => {
  const { mergePDF } = require("../scripts/merge-pdf.cjs");
  const { dir } = type3Project(t);
  const input = path.join(dir, "out", "F01", "print.pdf");
  const output = path.join(dir, "out", "all.pdf");
  const pending = mergePDF(output, [input]);
  fs.appendFileSync(input, "\n% changed after read\n");
  await assert.rejects(() => pending, /結合中.*変更/);
  assert.equal(fs.existsSync(output), false);
});
