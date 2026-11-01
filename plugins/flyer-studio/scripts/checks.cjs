"use strict";
const fs = require("node:fs"),
  path = require("node:path"),
  cp = require("node:child_process"),
  P = require("./project.cjs");
const { overlap, inBox, rotatePoint } = require("./geometry.cjs");
const D = require("./design.cjs");
const { verifyCombined } = require("./merge-checks.cjs");
const { inspectContrast, parseColor, contrast } = require("./contrast.cjs");
function whiteEdge(png, mm, wmm, hmm) {
  const x = Math.floor((mm / wmm) * png.width),
    y = Math.floor((mm / hmm) * png.height);
  let bad = 0;
  for (let j = 0; j < png.height; j++)
    for (let i = 0; i < png.width; i++) {
      if (i >= x && i < png.width - x && j >= y && j < png.height - y) continue;
      const k = (j * png.width + i) * 4;
      if (Math.min(png.data[k], png.data[k + 1], png.data[k + 2]) < 250) bad++;
    }
  return bad;
}
// inspectContrast samples each line's page bounds, which for a turned line
// also cover background beside the glyphs and can hide an invisible line.
// Sample the unturned line grid turned about the block center instead.
function turnedInvisible(p, v, l, out) {
  const turned = l.texts.filter((t) => t.local);
  if (!turned.length) return [];
  const { PNG } = require("pngjs"),
    art = PNG.sync.read(fs.readFileSync(out + "/artwork.png")),
    { width, height } = p.brief.page;
  return turned
    .filter((t) => {
      const declared = v.texts.find((x) => x.id === t.id),
        fg = parseColor(t.computedColor || declared.color || v.ink || (v.paper === "white" ? "#142A32" : "#FFFFFF")),
        f = t.local.frame,
        center = { x: f.x + f.w / 2, y: f.y + f.h / 2 };
      return t.local.lines.filter((line) => line.text?.trim()).some((line) => {
        let max = 0;
        for (let row = 0; row < 3; row++)
          for (let col = 0; col < 9; col++) {
            const q = rotatePoint({ x: line.x + (line.w * (col + 0.5)) / 9, y: line.y + (line.h * (row + 0.5)) / 3 }, center, t.rotation),
              x = Math.max(0, Math.min(art.width - 1, Math.floor((q.x / width) * art.width))),
              y = Math.max(0, Math.min(art.height - 1, Math.floor((q.y / height) * art.height))),
              k = (y * art.width + x) * 4;
            max = Math.max(max, contrast(fg, [art.data[k], art.data[k + 1], art.data[k + 2]]));
          }
        return max <= 1.2;
      });
    })
    .map((t) => t.id);
}
// ids limits the run to pilot variants; that partial record never replaces the
// all-variant checks.json that finalize reads.
function verify(dir, ids) {
  const p = P.load(dir),
    base = P.validate(p),
    rows = [],
    issues = [...base.issues],
    { PNG } = require("pngjs"),
    jsqr = require("jsqr");
  if (base.fail) return { fail: base.fail, issues, rows };
  for (const v of p.scene.variants.filter((v) => !ids || ids.includes(v.id))) {
    const out = p.dir + "/out/" + v.id,
      local = [];
    let contrastAudit;
    const fail = (code, detail) => local.push({ id: v.id, code, detail });
    try {
      const r = P.read(out + "/render.json"),
        l = P.read(out + "/layout.json"),
        b = p.brief.page;
      // Only this variant's inputs and the common ones decide staleness, so
      // editing one variant leaves the others' renders valid. A record without
      // variantFingerprint is held to the whole-project fingerprint.
      if (
        r.variantFingerprint
          ? r.variantFingerprint !== P.fingerprint(p, v.id)
          : r.fingerprint !== P.fingerprint(p)
      )
        fail(
          "stale-input",
          "入力か描画処理が更新されています。再描画してください",
        );
      for (const [n, key] of [
        ["print.pdf", "pdfSha256"],
        ["print.png", "pngSha256"],
        ["browser.png", "browserSha256"],
        ["layout.json", "layoutSha256"],
        ["artwork.png", "artworkSha256"],
      ])
        if (P.sha(out + "/" + n) !== r[key]) fail("stale-output", n);
      const safe = {
        x: b.safe,
        y: b.safe,
        w: b.width - 2 * b.safe,
        h: b.height - 2 * b.safe,
      };
      const lines = l.texts.flatMap((t) =>
        t.lines.filter((x) => x.text?.trim()).map((x) => ({ ...x, id: t.id })),
      );
      for (const t of lines)
        if (!inBox(t, safe)) fail("text-safe", "文字の見切れ/安全域: " + t.id);
      // A turned block is compared unturned: its page bounds would hide overflow.
      for (const t of l.texts) {
        const { frame, lines } = t.local || t;
        for (const line of lines)
          if (
            line.x < frame.x - 0.3 ||
            line.x + line.w > frame.x + frame.w + 0.3 ||
            line.y < frame.y - 0.3 ||
            line.y + line.h > frame.y + frame.h + 0.3
          )
            fail("text-overflow", t.id);
      }
      for (let i = 0; i < lines.length; i++)
        for (let j = i + 1; j < lines.length; j++)
          if (lines[i].id !== lines[j].id && overlap(lines[i], lines[j], 0.7))
            fail("text-collision", lines[i].id + "/" + lines[j].id);
      for (const t of lines) {
        if (l.qr && overlap(t, l.qr, 0.5)) fail("qr-collision", t.id);
        for (const r of v.protectedRegions || [])
          if (overlap(t, r, 0.5)) fail("subject-collision", t.id);
        if (v.logo && overlap(t, v.logo, 0.5)) fail("logo-collision", t.id);
      }
      if (l.images.some((i) => !i.loaded) || l.errors.length)
        fail("browser", "画像未読込/ブラウザエラー");
      if (v.photos?.some((f) => f.cropPx) && !l.viewBox)
        fail("crop-support", "ブラウザが承認cropに対応していません");
      const png = PNG.sync.read(fs.readFileSync(out + "/print.png"));
      if (p.brief.qrUrl?.trim()) {
        if (!l.qr) fail("qr-missing", "PDF描画元にQR枠がありません");
        const qf = v.qr,
          qx = Math.floor((qf.x / b.width) * png.width),
          qy = Math.floor((qf.y / b.height) * png.height),
          qw = Math.ceil((qf.size / b.width) * png.width),
          qh = Math.ceil((qf.size / b.height) * png.height),
          crop = new PNG({ width: qw, height: qh });
        PNG.bitblt(png, crop, qx, qy, qw, qh, 0, 0);
        const q = jsqr(new Uint8ClampedArray(crop.data), crop.width, crop.height);
        if (q?.data !== p.brief.qrUrl)
          fail("qr-decode", "PDF由来画像の申込QR枠を読めません");
      } else if (l.qr) fail("qr-without-url", "URLが無い案件にQR枠が残っています");
      if (
        v.paper === "white" &&
        whiteEdge(png, b.whiteEdge, b.width, b.height) > 0
      )
        fail("white-edge", "外周の白が維持されていません");
      if (p.concepts.variants.find((x) => x.id === v.id).tone === "dark") {
        let dark = 0;
        for (let k = 0; k < png.data.length; k += 4)
          if ((png.data[k] + png.data[k + 1] + png.data[k + 2]) / 3 < 80)
            dark++;
        if (dark / (png.width * png.height) < 0.2)
          fail(
            "dark-tone",
            "黒系と指定されていますが暗い領域が紙面の20%未満です",
          );
      }
      contrastAudit = inspectContrast(p, v, l, out);
      for (const issue of contrastAudit.issues) fail(issue.code, issue.detail);
      for (const id of turnedInvisible(p, v, l, out))
        fail("text-invisible", id + ": sampled turned-line colors are indistinguishable");
      const pdffonts = require("./render.cjs").command("pdffonts");
      if (pdffonts) {
        const fontRows = cp
          .execFileSync(pdffonts, [out + "/print.pdf"], { encoding: "utf8" })
          .split("\n")
          .slice(2)
          .filter((x) => x.trim());
        if (
          !fontRows.length ||
          fontRows.some((x) => !/\byes\s+yes\s+(yes|no)\s+\d+\s+\d+/.test(x))
        )
          fail("fonts", "フォント埋込を確認してください");
      } else fail("pdffonts", "フォント埋込検査にpdffontsが必要");
      const info = require("./render.cjs").command("pdfinfo");
      if (info) {
        const s = cp.execFileSync(info, [out + "/print.pdf"], {
            encoding: "utf8",
          }),
          size = s.match(/Page size:\s+([\d.]+) x ([\d.]+)/);
        if (
          !/Pages:\s+1\b/.test(s) ||
          !size ||
          Math.abs(Number(size[1]) - (b.width * 72) / 25.4) > 1 ||
          Math.abs(Number(size[2]) - (b.height * 72) / 25.4) > 1
        )
          fail("pdf-size", "1ページの指定サイズではありません");
      } else fail("pdfinfo", "PDF寸法検査にpdfinfoが必要");
      rows.push({
        id: v.id,
        variantFingerprint: P.fingerprint(p, v.id),
        pngSha256: r.pngSha256,
        pdfSha256: r.pdfSha256,
        contrast: contrastAudit,
        warnings: contrastAudit?.warnings || [],
        issues: local,
        fail: local.length,
      });
    } catch (e) {
      fail("render-missing", e.message);
      rows.push({ id: v.id, issues: local, fail: local.length });
    }
    issues.push(...local);
  }
  const result = {
    fingerprint: P.fingerprint(p),
    rows,
    issues,
    fail: issues.length,
  };
  P.write(p.dir + "/out/" + (ids ? "pilot-checks.json" : "checks.json"), result);
  return result;
}
// Pilot IDs name output variants. Renamed outputs cannot inherit a pilot by guesswork.
// A new-from-brief project has no analysis.json and so no executionPlan.
function pilotPlan(p, approval) {
  if (approval.mode !== "source-artifact") return null;
  const pilot = P.read(p.dir + "/analysis.json").executionPlan?.pilotVariantIds;
  if (!pilot) return null;
  const missing = pilot.filter((id) => !p.scene.variants.some((v) => v.id === id));
  if (missing.length)
    throw Error("先行試作案IDが出力案にありません。分析案と出力案のIDを揃えてください: " + missing.join(", "));
  return pilot;
}
// Each pilot row is judged by its own fingerprint, so editing a variant that is
// not a pilot keeps the pilot PASS; a common change (analysis, brief, engine)
// still voids it. Rows without variantFingerprint fall back to the whole project.
function pilotChecks(p, pilot) {
  const checks = P.read(p.dir + "/out/pilot-checks.json");
  const stale = (row) =>
    row.variantFingerprint
      ? row.variantFingerprint !== P.fingerprint(p, row.id)
      : checks.fingerprint !== P.fingerprint(p);
  if (
    checks.fail ||
    checks.rows.some(stale) ||
    [...checks.rows.map((row) => row.id)].sort().join() !== [...pilot].sort().join()
  )
    throw Error("先行試作案の機械検査が未完了か古いです。pilot-review-templateで再検査してください");
  for (const row of checks.rows) {
    const out = p.dir + "/out/" + row.id;
    const r = P.read(out + "/render.json");
    if (
      (r.variantFingerprint || r.fingerprint) !== (row.variantFingerprint || checks.fingerprint) ||
      r.pngSha256 !== row.pngSha256 ||
      P.sha(out + "/print.png") !== row.pngSha256
    )
      throw Error("先行試作案の画像が機械検査後に変わりました: " + row.id);
  }
  return checks;
}
// A pilot proves the prescription on a few variants before it spreads: the rest
// may be rendered only after the pilot images pass the same independent review.
function assertPilotOrder(p, only, approval) {
  const pilot = pilotPlan(p, approval);
  const targets = only ? [only] : p.scene.variants.map((v) => v.id);
  if (!pilot || targets.every((id) => pilot.includes(id))) return null;
  try {
    return D.validateReview(P.read(p.dir + "/pilot-review.json"), pilotChecks(p, pilot), p);
  } catch (error) {
    throw Error("先行試作案の独立PASS前に残りの案へ展開できません: " + error.message);
  }
}
function pilotReviewTemplate(dir) {
  const p = P.load(dir),
    pilot = pilotPlan(p, require("./analysis.cjs").assertApproved(p.dir, p));
  if (!pilot) throw Error("executionPlanに先行試作案がありません");
  const checks = verify(dir, pilot);
  if (checks.fail) throw Error("先行試作案の機械検査を先に解消してください");
  return renewReview(p, "pilot-review.json", checks);
}
function reviewTemplate(dir) {
  const p = P.load(dir),
    checks = verify(dir);
  if (checks.fail) throw Error("機械検査を先に解消してください");
  return renewReview(p, "visual-review.json", checks);
}
// SS-8/SS-9: a re-review starts from a fresh ledger for the new images. The
// previous record is counted in the cycle ledger, then moved to reviews/<label>/
// (never overwritten), so unchanged variants are pre-filled from it.
function renewReview(p, name, checks) {
  recordCycles(p.dir);
  const stamp = new Date().toISOString().replace(/[-:.]/g, "");
  let label = stamp;
  for (let n = 1; fs.existsSync(path.join(p.dir, "reviews", label, name)); n++)
    label = stamp + "-" + n;
  D.archiveReview(p, name, label);
  const file = p.dir + "/" + name;
  P.write(file, D.reviewTemplate(p, checks));
  return file;
}
function validateReview(review, checks, project) {
  return D.validateReview(review, checks, project);
}
// R4: cycle-ledger.json counts the improvement cycles of the whole project.
// It is derived from the review records on every call, so calling it from
// several commands is idempotent: each FIX record adds one entry keyed by its
// own SHA, and an archived copy is not counted twice. A FIX on images already
// counted (no new render, so no new cycle) and a PASS that only notes
// preferences are recorded with consumed=false. Visual classes and routes come
// from D.classifyFixes; proposal decisions come from A.classifyReview and have no
// inferred visual fixClass.
const LEDGER = "cycle-ledger.json";
const ISO = /^\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}(\.\d+)?(Z|[+-]\d{2}:\d{2})$/;
const schemaCache = {};
function schemaErrors(name, value) {
  if (!schemaCache[name]) {
    const ajv = new (require("ajv"))({ allErrors: true, strict: false });
    schemaCache[name] = { ajv, validate: ajv.compile(D.schema(name)) };
  }
  const { ajv, validate } = schemaCache[name];
  return validate(value) ? null : ajv.errorsText(validate.errors);
}
const words = (s) => String(s ?? "").normalize("NFKC").replace(/\s+/g, " ").trim();
const digestOf = (rows) => P.hash(rows.map((row) => JSON.stringify(row)).sort());
const list = (value) => (Array.isArray(value) ? value : []);
function visualRecord(entry) {
  const r = entry.review,
    items = list(r?.items),
    fixed = items.filter((item) => item?.decision === "FIX");
  if (!fixed.length && !items.some((item) => list(item?.preferenceNotes).length)) return null;
  let cls = null;
  try {
    cls = D.classifyFixes(r);
  } catch (error) {
    // An unfinished PASS draft spends nothing. The current FIX must name its
    // route before anyone acts on it; an archived one is history that cannot
    // be edited, so it is counted without classes instead of blocking.
    if (!fixed.length) return null;
    if (path.dirname(entry.file) === ".")
      throw Error(
        "FIX の目視レビューを分類できないため cycle 台帳へ記録できません（" +
          entry.file + "）。記録を直してください: " + error.message,
      );
  }
  return {
    fix: fixed.length > 0,
    trigger: "visual-review",
    at: r.reviewedAt,
    findingsDigest: fixed.length
      ? digestOf(fixed.flatMap((item) =>
          list(item.mandatoryFixes).map((f) => [item.id, words(f?.text ?? f), f?.fixClass ?? null, [...list(f?.serves)].sort()])))
      : digestOf(items.flatMap((item) => list(item?.preferenceNotes).map((note) => [item.id, words(note?.text ?? note)]))),
    renderDigest: digestOf(items.map((item) => [item?.id, item?.pngSha256])),
    fixClasses: cls ? { ...cls.fixClasses, ...(cls.preferenceNotes ? { preference: cls.preferenceNotes } : {}) } : {},
    returnTo: cls ? cls.returnTo : [],
    source: { file: entry.file, sha256: entry.sha256 },
  };
}
function analysisRecord(dir, { allowLegacyAnalysis = false } = {}) {
  const file = path.join(dir, "analysis-review.json");
  if (!fs.existsSync(file)) return null;
  const r = P.read(file), preferences = list(r?.preferenceNotes);
  if (r?.decision === "pending" && !list(r.mandatoryFixes).length && !preferences.length) return null;
  const legacy = r?.decision === "FIX" && list(r.mandatoryFixes).length > 0 && r.mandatoryFixes.every(fix => typeof fix === "string" && fix.trim());
  let classification;
  if (legacy) {
    if (!allowLegacyAnalysis)
      throw Error("旧文字列形式の提案FIXには serves が無く分類できません。原記録を変更せず analysis-review-template で退避し、新しい型で独立再評価してください");
    const errors = schemaErrors("analysis-review", { ...r, mandatoryFixes: [] });
    if (errors || r.returnTo !== "run-analyze-flyer")
      throw Error("旧提案評価を安全に退避できません。必須項目か戻り先が不明です: " + (errors || r.returnTo));
    classification = { fix: true };
  } else classification = require("./analysis.cjs").classifyReview(r);
  if (!classification.fix && !preferences.length) return null;
  return {
    fix: classification.fix,
    ...(legacy ? { legacyReason: "旧い提案FIXを原文のまま退避。serves・4条件との整合は不明なので分類せず、過去の差戻し1回だけを数える" } : {}),
    trigger: "analysis-review",
    at: r.reviewedAt,
    findingsDigest: classification.fix
      ? digestOf([
          ...r.mandatoryFixes.map(fix => ["fix", words(fix?.text ?? fix), [...list(fix?.serves)].sort()]),
          ...Object.keys(r.checks).filter(key => r.checks[key].verdict === "FIX").map(key => ["check", key]),
        ])
      : digestOf(preferences.map(note => ["preference", words(note.text)])),
    renderDigest: digestOf([[r.analysisSha256, r.sourceFingerprint]]),
    fixClasses: {},
    returnTo: classification.fix ? [r.returnTo] : [],
    source: { file: "analysis-review.json", sha256: P.sha(file) },
  };
}
function readLedger(dir) {
  const file = path.join(dir, LEDGER);
  const ledger = fs.existsSync(file)
    ? P.read(file)
    : { version: 1, budget: D.contract.cycleBudget, entries: [] };
  const errors = schemaErrors("cycle-ledger", ledger);
  if (errors) throw Error("cycle-ledger.json の形が不正です: " + errors);
  return ledger;
}
function recordCycles(dir, options = {}) {
  dir = path.resolve(dir);
  const file = path.join(dir, LEDGER),
    ledger = readLedger(dir),
    known = new Set(ledger.entries.map((entry) => entry.source.sha256));
  const records = [analysisRecord(dir, options), ...D.reviewHistory({ dir }).map(visualRecord)]
    .filter((record) => record && !known.has(record.source.sha256))
    .filter((record, i, all) => all.findIndex((other) => other.source.sha256 === record.source.sha256) === i)
    .map((record) => ({ ...record, at: ISO.test(record.at || "") ? record.at : new Date().toISOString() }))
    .sort((a, b) => Date.parse(a.at) - Date.parse(b.at));
  let consumed = ledger.entries.filter((entry) => entry.consumed).length;
  for (const { fix, legacyReason, ...record } of records) {
    const earlier = ledger.entries.filter((entry) => entry.trigger === record.trigger);
    const reason = !fix
      ? "好み（preference）だけの所見。記録だけで cycle を消費しない（R4）"
      : earlier.some((e) => e.findingsDigest === record.findingsDigest && e.renderDigest === record.renderDigest)
        ? "同じ所見・同じ画像の再提出。進捗として数えない（R4）"
        : earlier.some((e) => e.consumed && e.renderDigest === record.renderDigest)
          ? "数えた評価と同じ画像への所見の追記。新しい描画が無いので新しい cycle ではない（R4）"
          : null;
    if (!reason) consumed++;
    ledger.entries.push({
      cycle: consumed,
      ...record,
      consumed: !reason,
      reason:
        reason || legacyReason ||
        (record.returnTo.length
          ? "FIX: " + record.returnTo.join("・") + " へ戻す"
          : "FIX（退避済みで分類できない旧い記録）。戻り先は不明だが cycle は数える"),
    });
  }
  ledger.budget = D.contract.cycleBudget;
  const errors = schemaErrors("cycle-ledger", ledger);
  if (errors) throw Error("cycle-ledger.json の形が不正なため保存できません: " + errors);
  if (records.length || !fs.existsSync(file)) P.write(file, ledger);
  return ledger;
}
// Over budget means the run ends INCOMPLETE; the number comes only from
// design-contract.json, not from the copy kept in the ledger.
function cycleSummary(ledger) {
  const budget = D.contract.cycleBudget,
    consumed = ledger.entries.filter((entry) => entry.consumed).length;
  return { consumed, budget, remaining: Math.max(0, budget - consumed), entries: ledger.entries.length, over: consumed > budget };
}
function cycleStatus(dir) {
  const summary = cycleSummary(recordCycles(dir));
  return { ...summary, file: path.join(path.resolve(dir), LEDGER), fail: Number(summary.over) };
}
// The open findings an INCOMPLETE run hands back.
function unresolvedFixes(p) {
  const out = [];
  for (const name of ["analysis-review.json", "pilot-review.json", "visual-review.json"]) {
    const file = p.dir + "/" + name;
    if (!fs.existsSync(file)) continue;
    const r = P.read(file);
    if (name === "analysis-review.json") {
      if (r?.decision === "FIX")
        for (const fix of r.mandatoryFixes || []) out.push({ source: name, text: fix?.text ?? fix, ...(fix?.serves ? { serves: fix.serves } : {}), returnTo: r.returnTo });
      continue;
    }
    for (const item of r?.items || [])
      if (item?.decision === "FIX")
        for (const fix of item.mandatoryFixes || [])
          out.push({ source: name, id: item.id, text: fix?.text, fixClass: fix?.fixClass, returnTo: fix?.returnTo });
  }
  return out;
}
// Order: hearing resolved → mandatory essence anchor kept → cycle budget.
function deliveryGates(p) {
  const gates = require("./essence.cjs").assertCurrent(p.dir);
  return { ...gates, cycles: cycleSummary(recordCycles(p.dir)) };
}
// Never leave a delivery behind unless finalize completes: no earlier complete
// receipt, and no combined files that could pass for one.
function withdrawDelivery(p, receipt) {
  for (const name of ["all.pdf", "white.pdf", "index.html", "combined-checks.json"])
    fs.rmSync(p.dir + "/out/" + name, { force: true });
  P.write(p.dir + "/out/delivery.json", receipt);
}
function finalize(dir) {
  const p = P.load(dir);
  try {
    const gates = deliveryGates(p);
    if (gates.cycles.over) {
      const receipt = {
        status: "INCOMPLETE",
        fail: 1,
        reason:
          "改善 cycle の予算を超えました（消費 " + gates.cycles.consumed + " / 予算 " + gates.cycles.budget +
          "）。未解決の所見を添えて返します",
        intakeGate: gates.intakeGate,
        essenceGate: gates.essenceGate,
        cycles: gates.cycles,
        unresolved: unresolvedFixes(p),
        limitations: ["納品物は作っていない。予算の数え方は references/workflow.md#改善と納品"],
      };
      withdrawDelivery(p, receipt);
      return receipt;
    }
    return finalizeChecked(p, gates);
  } catch (error) {
    withdrawDelivery(p, { status: "pending", fail: 1, reason: error.message });
    throw error;
  }
}
// 白系 PDF を結合する案。納品 index の白系 PDF リンクも同じ規則で出し、無い PDF へリンクしない。
const whiteVariants = (p) => p.scene.variants.filter((variant) => variant.paper === "white");
// 納品 index の HTML。brief・scene・concepts だけから組み、ファイルも外部 tool も読まない。
function deliveryIndex(p) {
  const esc = P.esc, whites = whiteVariants(p);
  return `<!doctype html><html lang="ja"><meta charset="utf-8"><meta name="viewport" content="width=device-width"><title>${esc(p.brief.title)}</title><style>body{font-family:system-ui;max-width:1400px;margin:32px auto;padding:0 24px;background:#edf0ef;color:#162b32}main{display:grid;grid-template-columns:repeat(auto-fit,minmax(240px,1fr));gap:24px}img{width:100%;height:auto}article{background:white;padding:12px}a{color:#164e76}h2{font-size:18px}</style><h1>${esc(p.brief.title)}</h1><p>${p.brief.page.width}×${p.brief.page.height}mm・実際のサイズ100%。<a href="all.pdf">全案PDF</a>${whites.length ? ' ／ <a href="white.pdf">白系PDF</a>' : ""}</p><main>${p.scene.variants.map((v) => `<article><a href="${v.id}/print.pdf"><img alt="${esc(v.id)}" src="${v.id}/print.png"></a><h2>${esc(v.id + " " + p.concepts.variants.find((c) => c.id === v.id).name)}</h2><a href="${v.id}/print.pdf">印刷用PDF</a> ／ <a href="${v.id}/print.png">PNG</a></article>`).join("")}</main></html>`;
}
function finalizeChecked(p, gates) {
  // Freeze only the inputs and approved deliverables, not directory timestamps:
  // a new diagnostic file may be written while external PDF tools are running.
  const startFingerprint = P.fingerprint(p);
  const analysisGate = require("./analysis.cjs").assertApproved(p.dir, p);
  const reviewFile = p.dir + "/visual-review.json";
  const reviewSha256 = P.sha(reviewFile);
  const artifactFiles = p.scene.variants.flatMap((v) =>
    ["render.json", "print.pdf", "print.png", "browser.png", "layout.json", "artwork.png"]
      .map((name) => p.dir + "/out/" + v.id + "/" + name),
  );
  const artifactHashes = new Map(artifactFiles.map((file) => [file, P.sha(file)]));
  const c = verify(p.dir);
  if (c.fail) throw Error("機械検査が失敗しています: " + c.fail);
  if (c.fingerprint !== startFingerprint)
    throw Error("完了検査中に入力が変更されました。再検査してください");
  const review = P.read(reviewFile);
  const approval = validateReview(review, c, p);
  const merger = path.join(__dirname, "merge-pdf.cjs");
  const pdfs = c.rows.map((row) => p.dir + "/out/" + row.id + "/print.pdf");
  cp.execFileSync(process.execPath, [merger, p.dir + "/out/all.pdf", ...pdfs], { stdio: "pipe" });
  const whites = whiteVariants(p);
  if (whites.length)
    cp.execFileSync(process.execPath, [
      merger,
      p.dir + "/out/white.pdf",
      ...whites.map((variant) => p.dir + "/out/" + variant.id + "/print.pdf"),
    ], { stdio: "pipe" });
  else fs.rmSync(p.dir + "/out/white.pdf", { force: true });
  const combinedReview = verifyCombined(p.dir, p, c.rows);
  P.write(p.dir + "/out/combined-checks.json", combinedReview);
  if (combinedReview.fail)
    throw Error(
      "結合PDFの再検査が失敗しています: " +
        JSON.stringify(combinedReview.issues),
    );
  fs.writeFileSync(p.dir + "/out/index.html", deliveryIndex(p));
  // verify itself runs external children. Reload after its last child so a
  // change during merging, pixel comparison, or this final verification cannot
  // inherit the earlier approval or leave a complete receipt.
  const freshChecks = verify(p.dir);
  if (freshChecks.fail)
    throw Error("完了検査中の鮮度再検査が失敗しています: " + freshChecks.fail);
  const fresh = P.load(p.dir);
  if (freshChecks.fingerprint !== startFingerprint || P.fingerprint(fresh) !== startFingerprint)
    throw Error("完了検査中に入力が変更されました。再描画・再評価してください");
  if (P.validate(fresh).fail)
    throw Error("完了検査中に入力素材または契約が変更されました。再検査してください");
  const freshAnalysisGate = require("./analysis.cjs").assertApproved(fresh.dir, fresh);
  if (P.hash(freshAnalysisGate) !== P.hash(analysisGate))
    throw Error("完了検査中に提案評価の承認が変わりました。再検査してください");
  // The gates are read again last: a hearing answer, an essence edit or a new
  // review record during finalize must not inherit the earlier decision.
  const freshGates = deliveryGates(fresh);
  if (freshGates.cycles.over || P.hash(freshGates) !== P.hash(gates))
    throw Error("完了検査中にヒアリング・本質アンカー・cycle 台帳のどれかが変わりました。再検査してください");
  if (P.sha(reviewFile) !== reviewSha256)
    throw Error("完了検査中に目視レビューが変更されました。再評価してください");
  validateReview(P.read(reviewFile), freshChecks, fresh);
  for (const [file, digest] of artifactHashes)
    if (P.sha(file) !== digest)
      throw Error("完了検査中に個別成果物が変更されました: " + path.relative(p.dir, file));
  for (const file of combinedReview.files)
    if (P.sha(p.dir + "/out/" + file.file) !== file.pdfSha256)
      throw Error("完了検査中に結合成果物が変更されました: " + file.file);
  const receipt = {
    status: "complete",
    fingerprint: c.fingerprint,
    reviewPolicyFingerprint: approval.reviewPolicyFingerprint,
    approval,
    analysisGate,
    intakeGate: gates.intakeGate,
    essenceGate: gates.essenceGate,
    cycles: gates.cycles,
    combinedReview,
    reviewSha256,
    combinedSha256: P.sha(p.dir + "/out/all.pdf"),
    rows: c.rows.map((r) => ({ id: r.id, pngSha256: r.pngSha256 })),
    limitations: ["実機印刷・集客効果はこの検査に含まない"],
    fail: 0,
  };
  P.write(p.dir + "/out/delivery.json", receipt);
  return receipt;
}
module.exports = {
  verify,
  reviewTemplate,
  pilotReviewTemplate,
  assertPilotOrder,
  finalize,
  deliveryIndex,
  validateReview,
  recordCycles,
  cycleSummary,
  cycleStatus,
  renewReview,
  overlap,
  whiteEdge,
};
