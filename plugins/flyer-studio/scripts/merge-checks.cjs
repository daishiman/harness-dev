"use strict";
const fs = require("node:fs");
const os = require("node:os");
const path = require("node:path");
const cp = require("node:child_process");
const crypto = require("node:crypto");
const { PNG } = require("pngjs");

const DPI = 150;
const hash = (bytes) => crypto.createHash("sha256").update(bytes).digest("hex");
const sha = (file) => hash(fs.readFileSync(file));
const run = (tool, args) =>
  cp.execFileSync(tool, args, {
    encoding: "utf8",
    stdio: ["ignore", "pipe", "pipe"],
    timeout: 60000,
    maxBuffer: 4 * 1024 * 1024,
    env: { ...process.env, LC_ALL: "C" },
  });

function pageCount(file) {
  const match = run("pdfinfo", [file]).match(/^Pages:\s+(\d+)\s*$/m);
  if (!match || Number(match[1]) < 1)
    throw Error("PDFのページ数を取得できません");
  return Number(match[1]);
}

function pixelSha(file, page, temp, name) {
  const prefix = path.join(temp, name);
  // 同じ内容のpdfunite前後でもAA境界に単画素差が生じるため、比較用描画は両側ともAAを無効にする。
  // 許容差や色の丸めは使わず、この固定描画条件の全RGBA画素を厳密に照合する。
  run("pdftoppm", [
    "-r",
    String(DPI),
    "-f",
    String(page),
    "-l",
    String(page),
    "-singlefile",
    "-aa",
    "no",
    "-aaVector",
    "no",
    "-png",
    file,
    prefix,
  ]);
  const png = PNG.sync.read(fs.readFileSync(prefix + ".png"));
  // PNG圧縮やメタデータではなく、描画したサイズとRGBA画素を比較する。
  const h = crypto.createHash("sha256");
  h.update(`${png.width}x${png.height}:rgba8:`);
  h.update(png.data);
  return h.digest("hex");
}

function verifyCombined(dir, p, rows) {
  const result = {
    fail: 0,
    issues: [],
    pages: [],
    files: [],
    dpi: DPI,
    rasterOptions: { textAntialias: false, vectorAntialias: false },
    method: "pdfinfo+pdftoppm-decoded-pixels",
  };
  const fail = (code, detail, extra = {}) =>
    result.issues.push({ code, detail, ...extra });
  const variants = p?.scene?.variants;
  if (!Array.isArray(variants) || !variants.length || !Array.isArray(rows)) {
    fail("combined-input", "結合検査に案と個別PDF検査結果が必要です");
    result.fail = result.issues.length;
    return result;
  }
  const ids = variants.map((v) => v.id);
  if (
    ids.some(
      (id) =>
        typeof id !== "string" || !/^[A-Za-z][A-Za-z0-9_-]{0,48}$/.test(id),
    ) ||
    new Set(ids).size !== ids.length ||
    rows.length !== ids.length ||
    new Set(rows.map((row) => row.id)).size !== ids.length ||
    rows.some((row) => !ids.includes(row.id))
  ) {
    fail("combined-input", "結合順の案IDと個別PDF検査結果が一致しません");
    result.fail = result.issues.length;
    return result;
  }
  const sourceRows = new Map(rows.map((row) => [row.id, row]));
  const sources = new Map();
  let temp;
  try {
    temp = fs.mkdtempSync(path.join(os.tmpdir(), "flyer-merge-check-"));
    for (const [index, id] of ids.entries()) {
      const file = path.join(dir, "out", id, "print.pdf");
      const row = sourceRows.get(id);
      try {
        if (
          !/^[a-f0-9]{64}$/.test(row.pdfSha256 || "") ||
          sha(file) !== row.pdfSha256
        ) {
          fail(
            "combined-source-sha",
            "結合元PDFが個別検査時のSHAと一致しません",
            { id },
          );
          continue;
        }
        if (pageCount(file) !== 1) {
          fail("combined-source-pages", "結合元PDFは1案1ページが必要です", {
            id,
          });
          continue;
        }
        sources.set(id, {
          pixelSha256: pixelSha(file, 1, temp, "source-" + index),
          pdfSha256: row.pdfSha256,
          pngSha256: row.pngSha256,
        });
      } catch (error) {
        fail(
          "combined-source-read",
          error.code === "ENOENT"
            ? "結合元PDFまたはPDF検査ツールがありません"
            : "結合元PDFの実描画検査に失敗しました",
          { id },
        );
      }
    }
    // 元PDFへの証拠の鎖が成立しないときは結合成果の合格を返さない。
    if (result.issues.length) {
      result.fail = result.issues.length;
      return result;
    }
    const white = variants.filter((v) => v.paper === "white").map((v) => v.id);
    const combined = [{ file: "all.pdf", ids }];
    if (white.length) combined.push({ file: "white.pdf", ids: white });
    for (const entry of combined) {
      const file = path.join(dir, "out", entry.file);
      try {
        const info = {
          file: entry.file,
          pdfSha256: sha(file),
          pageCount: pageCount(file),
          expectedIds: entry.ids,
          matchedPages: 0,
        };
        result.files.push(info);
        if (info.pageCount !== entry.ids.length) {
          fail("combined-page-count", "結合PDFのページ数が案数と一致しません", {
            file: entry.file,
            expected: entry.ids.length,
            actual: info.pageCount,
          });
          continue;
        }
        for (const [index, id] of entry.ids.entries()) {
          const source = sources.get(id);
          const actual = pixelSha(
            file,
            index + 1,
            temp,
            entry.file.replace(".pdf", "") + "-" + index,
          );
          const page = {
            file: entry.file,
            page: index + 1,
            id,
            pixelSha256: actual,
            sourcePixelSha256: source.pixelSha256,
            sourcePdfSha256: source.pdfSha256,
            sourcePngSha256: source.pngSha256,
          };
          result.pages.push(page);
          if (actual !== source.pixelSha256) {
            fail(
              "combined-page-content",
              "結合PDFのページ順または描画内容が個別承認済みPDFと一致しません",
              { file: entry.file, page: index + 1, id },
            );
          } else info.matchedPages++;
        }
        if (sha(file) !== info.pdfSha256)
          fail("combined-output-changed", "検査中に結合PDFが変更されました", {
            file: entry.file,
          });
      } catch (error) {
        fail(
          "combined-read",
          error.code === "ENOENT"
            ? "結合PDFまたはPDF検査ツールがありません"
            : "結合PDFの実描画検査に失敗しました",
          { file: entry.file },
        );
      }
    }
    for (const id of ids) {
      if (
        sha(path.join(dir, "out", id, "print.pdf")) !==
        sources.get(id).pdfSha256
      ) {
        fail("combined-source-sha", "検査中に結合元PDFが変更されました", {
          id,
        });
      }
    }
  } catch {
    fail("combined-runtime", "結合PDF検査を完了できませんでした");
  } finally {
    if (temp) fs.rmSync(temp, { recursive: true, force: true });
  }
  result.fail = result.issues.length;
  return result;
}

module.exports = { verifyCombined };
