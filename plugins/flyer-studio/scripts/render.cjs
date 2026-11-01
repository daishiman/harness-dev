"use strict";
const fs = require("node:fs"),
  path = require("node:path"),
  cp = require("node:child_process");
const P = require("./project.cjs");
const { parseColor } = require("./contrast.cjs");
function command(name) {
  const r = cp.spawnSync(
    process.platform === "win32" ? "where" : "which",
    [name],
    { encoding: "utf8" },
  );
  return r.status === 0 ? r.stdout.trim().split(/\r?\n/)[0] : null;
}
async function browser() {
  const { chromium } = require("playwright-core");
  if (process.env.FLYER_BROWSER)
    return chromium.launch({
      executablePath: process.env.FLYER_BROWSER,
      headless: true,
    });
  try {
    return await chromium.launch({ channel: "chrome", headless: true });
  } catch {
    return chromium.launch({ headless: true });
  }
}
function data(file) {
  const ext = path.extname(file).toLowerCase();
  const mime = {
    ".png": "image/png",
    ".jpg": "image/jpeg",
    ".jpeg": "image/jpeg",
    ".webp": "image/webp",
    ".svg": "image/svg+xml",
  }[ext];
  if (!mime) throw Error("画像形式: " + ext);
  return "data:" + mime + ";base64," + fs.readFileSync(file).toString("base64");
}
function pos(f) {
  return `left:${f.x}mm;top:${f.y}mm;width:${f.w}mm;${f.h !== undefined ? "height:" + f.h + "mm;" : ""}`;
}
function safeColor(c, fallback) {
  c = c || fallback;
  parseColor(c);
  return c;
}
function num(v, defaultValue) {
  return Number.isFinite(v) ? v : defaultValue;
}
function photoHTML(p, v) {
  return (v.photos || [])
    .map((f, i) => {
      const e = p.assets.entries.find((e) => e.id === f.asset),
        fade = num(f.fadeMm, 8);
      if (fade < 2) throw Error("写真の境界はfadeMm>=2");
      const widthPct = (fade / f.w) * 100,
        heightPct = (fade / f.h) * 100;
      let style =
        "object-fit:cover;object-position:" +
        P.esc(f.objectPosition || "center") +
        ";";
      if (f.cropPx) {
        const [x, y, w, h] = f.cropPx,
          [sw, sh] = e.dimensionsPx || [];
        if (!sw || !sh) throw Error("cropに元画像寸法が必要");
        style += `object-view-box:inset(${(y / sh) * 100}% ${((sw - x - w) / sw) * 100}% ${((sh - y - h) / sh) * 100}% ${(x / sw) * 100}%);`;
      }
      return `<div class="art photo" data-photo="${P.esc(f.asset)}" style="${pos(f)}overflow:hidden;mask-image:linear-gradient(to right,transparent,#000 ${widthPct}%,#000 ${100 - widthPct}%,transparent)"><div style="width:100%;height:100%;mask-image:linear-gradient(to bottom,transparent,#000 ${heightPct}%,#000 ${100 - heightPct}%,transparent)"><img alt="選択した写真" style="width:100%;height:100%;${style}" src="${data(P.inside(p.dir, e.file))}"></div></div>`;
    })
    .join("");
}
async function html(p, v, logoUri) {
  const { brief: b } = p,
    W = b.page.width,
    H = b.page.height,
    ink = safeColor(v.ink, v.paper === "white" ? "#142A32" : "#FFFFFF"),
    bg = p.assets.entries.find((e) => e.id === v.background.asset),
    fonts = {
      sans: '"Hiragino Sans","Yu Gothic","Noto Sans CJK JP",sans-serif',
      serif: '"Hiragino Mincho ProN","Yu Mincho","Noto Serif CJK JP",serif',
      display: '"Arial", "Hiragino Sans",sans-serif',
      ...(p.brief.fonts || {}),
    };
  for (const val of Object.values(fonts))
    if (/[{}<>;\\]/.test(val)) throw Error("font stackが不正");
  const fontCSS = (b.fontFiles || [])
    .map((f) => {
      const e = p.assets.entries.find((e) => e.id === f.asset);
      if (e?.kind !== "font" || !f.family || /[{}<>;\\"']/.test(f.family))
        throw Error("fontFiles設定を確認");
      const ext = path.extname(e.file).slice(1),
        mime = {
          ttf: "font/ttf",
          otf: "font/otf",
          woff: "font/woff",
          woff2: "font/woff2",
        }[ext];
      return `@font-face{font-family:'${f.family}';font-weight:${num(f.weight, 400)};src:url(data:${mime};base64,${fs.readFileSync(P.inside(p.dir, e.file)).toString("base64")});font-display:block}`;
    })
    .join("");
  const fields = (v.fields || [])
    .map(
      (f) =>
        `<div class="art" style="${pos(f)}background:radial-gradient(ellipse closest-side,${safeColor(f.color, "#E4ECE8")} 0%,transparent 100%);opacity:${num(f.opacity, 0.3)}"></div>`,
    )
    .join("");
  const ts = v.texts
    .map((t) => {
      if (parseColor(t.color || ink)[3] <= 0.01)
        throw Error("文字を透明にできません: " + t.id);
      const text = P.resolvedText(b, t),
        lines = Array.isArray(text) ? text : String(text).split("\n"),
        turned = t.rotation !== undefined ? num(t.rotation, 0) : null;
      return `<div class="txt" data-id="${P.esc(t.id)}" data-group="${P.esc(t.group || "hero")}"${turned === null ? "" : ` data-rotation="${turned}"`} style="${pos(t)}color:${safeColor(t.color, ink)};font-family:${P.esc(fonts[t.font])};font-weight:${num(t.weight, 400)};font-size:${t.size}pt;line-height:${num(t.lineHeight, 1.3)};text-align:${t.align};letter-spacing:${num(t.tracking, 0)}em;writing-mode:${t.writingMode || "horizontal-tb"};text-orientation:${t.textOrientation || "mixed"};${t.layout === "row" ? "display:flex;justify-content:space-between;gap:2mm;" : ""}${turned === null ? "" : `transform-origin:50% 50%;transform:rotate(${turned}deg);`}">${lines.map((s, i) => `<span class="line" style="${t.layout === "row" ? "flex:1;text-align:center;" : ""}${t.lineWeights?.[i] !== undefined ? "font-weight:" + num(t.lineWeights[i], 400) + ";" : t.group === "apply" && i > 0 ? "font-weight:400;" : ""}">${P.esc(s)}</span>`).join("")}</div>`;
    })
    .join("");
  let logo = "";
  if (v.logo) {
    const f = v.logo,
      e = p.assets.entries.find((e) => e.id === f.asset);
    logo = `<img class="logo" alt="ロゴ" style="${pos(f)}object-fit:contain" src="${logoUri || data(P.inside(p.dir, e.file))}">`;
  }
  let qr = "";
  if (b.qrUrl?.trim()) {
    const svg = await require("qrcode").toString(b.qrUrl, {
      type: "svg",
      errorCorrectionLevel: "Q",
      margin: 4,
      color: { dark: "#000000", light: "#FFFFFF" },
    }), q = v.qr;
    qr = `<div class="qrhalo" style="left:${q.x - 3}mm;top:${q.y - 3}mm;width:${q.size + 6}mm;height:${q.size + 6}mm;background:#fff;filter:blur(1.8mm);opacity:${v.paper === "white" ? 1 : 0.15}"></div><div class="qr" style="left:${q.x}mm;top:${q.y}mm;width:${q.size}mm;height:${q.size}mm">${svg}</div>`;
  }
  const edge = b.page.whiteEdge,
    white =
      v.paper === "white"
        ? `<div class="art edge" style="inset:0;background:linear-gradient(to right,#fff ${edge}mm,transparent ${edge + 10}mm,transparent calc(100% - ${edge + 10}mm),#fff calc(100% - ${edge}mm)),linear-gradient(to bottom,#fff ${edge}mm,transparent ${edge + 10}mm,transparent calc(100% - ${edge + 10}mm),#fff calc(100% - ${edge}mm))"></div>`
        : "";
  return `<!doctype html><html lang="ja"><meta charset="utf-8"><title>${P.esc(v.id + " " + b.title)}</title><style>${fontCSS}@page{size:${W}mm ${H}mm;margin:0}*{box-sizing:border-box;print-color-adjust:exact;-webkit-print-color-adjust:exact}html,body{margin:0;padding:0}.page{position:relative;width:${W}mm;height:${H}mm;overflow:hidden;background:${safeColor(v.baseColor, v.paper === "white" ? "#fff" : "#080C10")}}.art,.txt,.qr,.logo,.qrhalo{position:absolute}.art{z-index:0}.txt{z-index:2}.line{display:block;white-space:nowrap}.qrhalo{z-index:1}.qr{z-index:3;background:#fff}.qr svg{display:block;width:100%;height:100%}.logo{z-index:3}.raster{position:absolute;inset:0;width:100%;height:100%}</style><main class="page"><img class="art" style="inset:0;width:100%;height:100%;object-fit:cover" src="${data(P.inside(p.dir, bg.file))}" alt="生成した背景">${photoHTML(p, v)}${fields}${white}${ts}${logo}${qr}</main></html>`;
}
function evaluateLayout() {
  const root = document.querySelector(".page").getBoundingClientRect(),
    scale =
      root.width /
      parseFloat(document.querySelector(".page").style.width || "210"),
    pxPerMm = root.width / Number(document.documentElement.dataset.width);
  const frame = (e) => {
    if (!e) return null;
    const r = e.getBoundingClientRect();
    return {
      x: (r.x - root.x) / pxPerMm,
      y: (r.y - root.y) / pxPerMm,
      w: r.width / pxPerMm,
      h: r.height / pxPerMm,
    };
  };
  const measure = (e) => ({
    frame: frame(e),
    lines: [...e.querySelectorAll(".line")].map((s) => {
      const r = document.createRange();
      r.selectNodeContents(s);
      const b = r.getBoundingClientRect();
      return {
        text: s.textContent,
        x: (b.x - root.x) / pxPerMm,
        y: (b.y - root.y) / pxPerMm,
        w: b.width / pxPerMm,
        h: b.height / pxPerMm,
      };
    }),
  });
  const texts = [...document.querySelectorAll(".txt")].map((e) => {
    const t = {
      id: e.dataset.id,
      group: e.dataset.group,
      computedColor: getComputedStyle(e).color,
      ...measure(e),
    };
    if (e.dataset.rotation === undefined) return t;
    // A turned block reports page bounds as above; local holds the same block
    // measured unturned, so overflow and glyph sampling follow the real line.
    const transform = e.style.transform;
    e.style.transform = "none";
    t.rotation = Number(e.dataset.rotation);
    t.local = measure(e);
    e.style.transform = transform;
    return t;
  });
  return {
    texts,
    images: [...document.images].map((i) => ({
      loaded: i.complete && i.naturalWidth > 0,
    })),
    qr: frame(document.querySelector(".qr")),
    viewBox: CSS.supports("object-view-box", "inset(10%)"),
  };
}
async function rasterLogo(p, v, B, out) {
  if (!v.logo) return;
  const e = p.assets.entries.find((e) => e.id === v.logo.asset);
  if (!e.file.toLowerCase().endsWith(".svg")) return;
  const width = 1600,
    height = Math.ceil((width * v.logo.h) / v.logo.w),
    page = await B.newPage({
      viewport: { width, height },
      deviceScaleFactor: 1,
    });
  try {
    await page.route("http://**", (r) => r.abort());
    await page.route("https://**", (r) => r.abort());
    await page.setContent(
      `<html><style>html,body{margin:0;background:transparent}img{width:${width}px;height:${height}px;object-fit:contain}</style><img src="${data(P.inside(p.dir, e.file))}">`,
    );
    await page.evaluate(async () => document.images[0].decode());
    await page.screenshot({
      path: out + "/logo-raster.png",
      omitBackground: true,
    });
    P.write(out + "/logo-raster.json", {
      asset: e.id,
      sourceSha256: e.sha256,
      renderedSha256: P.sha(out + "/logo-raster.png"),
      width,
      height,
      method: "native-browser-transparent-raster",
    });
    return data(out + "/logo-raster.png");
  } finally {
    await page.close();
  }
}
function assertFrozen(dir, frozen) {
  require("./essence.cjs").assertCurrent(dir);
  const current = P.load(dir);
  if (P.fingerprint(current) !== frozen || P.validate(current).fail)
    throw Error("描画中に入力/engineが変更されました。完了を破棄して再描画してください");
  require("./analysis.cjs").assertApproved(dir, current);
}
async function render(dir, only) {
  const p = P.load(dir);
  try {
    require("./essence.cjs").assertCurrent(p.dir);
  } catch (error) {
    P.write(p.dir + "/out/delivery.json", { status: "pending", fail: 1, reason: error.message });
    throw error;
  }
  const valid = P.validate(p);
  if (valid.fail) throw Error(JSON.stringify(valid, null, 2));
  // A new render starts a cycle: count the FIX it answers before the images change.
  require("./checks.cjs").recordCycles(p.dir);
  const approval = require("./analysis.cjs").assertApproved(p.dir, p);
  if ((p.brief.feedback || []).some(entry => entry.decision === "pending"))
    throw Error("未決のフィードバック要求は分析へ戻してください");
  require("./checks.cjs").assertPilotOrder(p, only, approval);
  const frozen = P.fingerprint(p);
  const tool = command("pdftoppm");
  if (!tool)
    throw Error("PDF画像検証にpdftoppmが必要です。doctorを確認してください");
  const B = await browser(),
    results = [];
  try {
    for (const v of p.scene.variants.filter((v) => !only || v.id === only)) {
      const out = p.dir + "/out/" + v.id;
      fs.mkdirSync(out, { recursive: true });
      const page = await B.newPage({
        viewport: {
          width: Math.round((p.brief.page.width * 96) / 25.4),
          height: Math.round((p.brief.page.height * 96) / 25.4),
        },
        deviceScaleFactor: 3,
      });
      await page.route("http://**", (r) => r.abort());
      await page.route("https://**", (r) => r.abort());
      const logoUri = await rasterLogo(p, v, B, out);
      const source = await html(p, v, logoUri);
      fs.writeFileSync(out + "/source.html", source);
      const errors = [];
      page.on("pageerror", (e) => errors.push(e.message));
      await page.setContent(source, { waitUntil: "load" });
      await page.evaluate(
        (w) => (document.documentElement.dataset.width = w),
        p.brief.page.width,
      );
      await page.evaluate(async () => {
        await document.fonts.ready;
        await Promise.all([...document.images].map((i) => i.decode()));
      });
      const layout = await page.evaluate(evaluateLayout);
      layout.errors = errors;
      P.write(out + "/layout.json", layout);
      await page.screenshot({ path: out + "/browser.png" });
      // ラスタ化するのは背景・写真だけ。本文・ロゴ・QRは独立したまま印刷する。
      await page.addStyleTag({
        content: ".txt,.qr,.logo,.qrhalo{visibility:hidden!important}",
      });
      await page.screenshot({ path: out + "/artwork.png" });
      await page.evaluate(
        (url) => {
          document.querySelectorAll(".art").forEach((e) => e.remove());
          const img = document.createElement("img");
          img.className = "raster";
          img.src = url;
          document.querySelector(".page").prepend(img);
          document.querySelectorAll("style").forEach((s) => {
            if (s.textContent.includes("visibility:hidden!important"))
              s.remove();
          });
        },
        data(out + "/artwork.png"),
      );
      await page.evaluate(async () =>
        Promise.all([...document.images].map((i) => i.decode())),
      );
      await page.pdf({
        path: out + "/print.pdf",
        preferCSSPageSize: true,
        printBackground: true,
      });
      fs.writeFileSync(out + "/print.html", await page.content());
      await page.close();
      cp.execFileSync(
        tool,
        [
          "-r",
          "350",
          "-singlefile",
          "-png",
          out + "/print.pdf",
          out + "/print",
        ],
        { stdio: "pipe" },
      );
      assertFrozen(p.dir, frozen);
      const report = {
        id: v.id,
        fingerprint: frozen,
        // checks.verify judges staleness per variant, so a change to another
        // variant leaves this render valid; a common change still voids it.
        variantFingerprint: P.fingerprint(p, v.id),
        pdfSha256: P.sha(out + "/print.pdf"),
        pngSha256: P.sha(out + "/print.png"),
        browserSha256: P.sha(out + "/browser.png"),
        layoutSha256: P.sha(out + "/layout.json"),
        artworkSha256: P.sha(out + "/artwork.png"),
        chrome: B.version(),
        createdAt: new Date().toISOString(),
      };
      P.write(out + "/render.json", report);
      results.push(report);
    }
    assertFrozen(p.dir, frozen);
  } catch (error) {
    for (const v of p.scene.variants.filter(v => !only || v.id === only))
      fs.rmSync(p.dir + "/out/" + v.id + "/render.json", { force: true });
    P.write(p.dir + "/out/delivery.json", { status: "pending", fail: 1, reason: error.message });
    throw error;
  } finally {
    await B.close();
  }
  return results;
}
module.exports = { render, html, browser, command, assertFrozen };
