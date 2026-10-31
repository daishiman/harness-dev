"use strict";
const fs = require("node:fs"),
  path = require("node:path"),
  crypto = require("node:crypto");
const ROOT = path.resolve(__dirname, "..");
const D = require("./design.cjs");
const { overlap, inBox, rotatedBox } = require("./geometry.cjs");
const { parseColor } = require("./contrast.cjs");
const read = (p) => JSON.parse(fs.readFileSync(p, "utf8"));
const sha = (p) =>
  crypto.createHash("sha256").update(fs.readFileSync(p)).digest("hex");
const hash = (o) =>
  crypto.createHash("sha256").update(JSON.stringify(o)).digest("hex");
const write = (p, o) => {
  fs.mkdirSync(path.dirname(p), { recursive: true });
  fs.writeFileSync(p, JSON.stringify(o, null, 2) + "\n");
};
const esc = (s) =>
  String(s).replace(
    /[&<>"']/g,
    (c) =>
      ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" })[
        c
      ],
  );
function inside(root, rel) {
  if (typeof rel !== "string" || !rel || path.isAbsolute(rel))
    throw Error("相対パスが必要: " + rel);
  const p = path.resolve(root, rel);
  if (p !== root && !p.startsWith(root + path.sep))
    throw Error("範囲外パス: " + rel);
  let parent = p;
  while (!fs.existsSync(parent)) parent = path.dirname(parent);
  const real = fs.realpathSync(parent),
    rr = fs.realpathSync(root);
  if (real !== rr && !real.startsWith(rr + path.sep))
    throw Error("範囲外symlink: " + rel);
  return p;
}
const PRIVACY_KEYS = [
  "ownerFace",
  "otherFaces",
  "child",
  "personalDeviceScreens",
  "unrelatedEventMarks",
];
const privacyComplete = (p) =>
  p?.reviewed === true &&
  PRIVACY_KEYS.every((k) => typeof p[k] === "string" && p[k].trim());
const intersects = overlap;
const idOK = (id) => /^[A-Za-z][A-Za-z0-9_-]{0,48}$/.test(id);
// A preset is chosen by id or alias; an unknown name fails before any file is written.
function preset(name) {
  if (name == null) return null;
  const root = ROOT + "/references/presets";
  const found = fs
    .readdirSync(root)
    .map((id) => root + "/" + id + "/preset.json")
    .filter((file) => fs.existsSync(file))
    .map(read)
    .find((p) => p.id === name || (p.aliases || []).includes(name));
  if (!found) throw Error("未知の preset です: " + name);
  return found;
}
function init(dir, presetName) {
  dir = path.resolve(dir);
  if (fs.existsSync(dir))
    throw Error(
      "既存ディレクトリは上書きしません。新しい出力先を指定してください",
    );
  const chosen = preset(presetName);
  fs.mkdirSync(dir, { recursive: true });
  const neutral = D.contract.initDefaults;
  const brief = {
    version: 1,
    designer: "",
    title: "",
    hero: [],
    copy: {},
    copyGroups: {},
    requiredRefs: [],
    forbiddenText: [],
    qrUrl: "",
    count: neutral.variantCount,
    whiteCount: neutral.whiteCount,
    stylePreferences: [],
    page: structuredClone(neutral.page),
    policy: structuredClone(neutral.policy),
    ...(chosen ? read(ROOT + "/" + chosen.briefExample) : {}),
    ...(chosen ? structuredClone(chosen.brief) : {}),
  };
  // Only the case that chose the preset reads its knowledge files.
  if (chosen)
    brief.preset = { id: chosen.id, knowledgeFiles: [...chosen.knowledgeFiles] };
  // Existing artwork switches this to source-artifact at analysis-template.
  brief.analysisMode = neutral.analysisMode;
  // Purpose belongs to this request, including when event facts use a preset.
  brief.purpose = { audience: "", benefit: "", action: "" };
  brief.confirmations = {
    facts: false,
    assets: false,
    privacy: false,
    referenceUse: false,
    styles: false,
  };
  write(dir + "/brief.json", brief);
  write(dir + "/assets.json", { entries: [] });
  write(dir + "/concepts.json", {
    variants: Array.from({ length: brief.count }, (_, i) => ({
      id: "F" + String(i + 1).padStart(2, "0"),
      paper: i >= brief.count - brief.whiteCount ? "white" : "color",
      tone:
        i >= brief.count - brief.whiteCount
          ? "light"
          : i === 0
            ? "dark"
            : "color",
      expression: "",
      name: "",
      signature: Object.fromEntries(
        D.contract.signatureKeys.map((key) => [key, ""]),
      ),
      designIntent: {
        readingOrder: [],
        groups: [],
        palette: [],
        whitespace: [],
        balanceReason: "",
        imageRelationship: "",
        rejectedAlternatives: [{ candidate: "", reason: "" }],
      },
      backgroundPrompt: "",
      background: null,
    })),
  });
  write(dir + "/scene.json", { version: 1, variants: [] });
  return dir;
}
// Case-specific assets carry `preset`; a case sees the shared ones plus those of the preset it chose.
const bundledAssets = () => read(ROOT + "/assets/catalog.json").entries;
const presetOnly = (e, presetId) => e.preset !== undefined && e.preset !== presetId;
function catalog(presetName) {
  const id = preset(presetName)?.id;
  return bundledAssets().filter((e) => !presetOnly(e, id));
}
function importAsset(dir, { id, file, kind, privacy, provenance }) {
  if (!idOK(id)) throw Error("素材IDが不正です");
  const list = read(dir + "/assets.json");
  if (list.entries.some((e) => e.id === id))
    throw Error("素材IDが重複しています");
  let e;
  if (file) {
    if (!["photo", "logo", "background", "reference", "font"].includes(kind))
      throw Error("kindが必要");
    if (kind === "photo" && !privacyComplete(privacy))
      throw Error(
        "新写真はprivacy.reviewed=trueと、ownerFace/otherFaces/child/personalDeviceScreens/unrelatedEventMarks各項目の確認記録が必要（対象なしも明記）",
      );
    e = {
      id,
      kind,
      label: id,
      usage: kind === "reference" ? "reference-only" : "selectable",
      privacy: privacy || {},
      provenance: provenance || {},
      file: "",
    };
    file = path.resolve(file);
  } else {
    e = structuredClone(bundledAssets().find((e) => e.id === id || e.aliases?.includes(id)));
    if (!e) throw Error("素材がありません: " + id);
    if (e.id !== id) {
      const alias = e.provenance?.aliases?.find((entry) => entry.id === id);
      if (!alias) throw Error("素材の別名の来歴がありません: " + id);
      e = { ...e, ...alias, id, preset: e.preset };
    }
    if (presetOnly(e, read(dir + "/brief.json").preset?.id))
      throw Error("この素材は preset " + e.preset + " 専用です: " + id);
    if (e.usage === "reference-only")
      throw Error("参照専用の画像は掲載素材としてimportできません");
    file = inside(ROOT + "/assets", e.file);
    if (e.kind === "photo") e.privacy = { ...e.privacy, reviewed: true };
  }
  const ext = path.extname(file).toLowerCase(),
    allowed =
      e.kind === "font"
        ? [".ttf", ".otf", ".woff", ".woff2"]
        : [".png", ".jpg", ".jpeg", ".webp", ".svg"];
  if (!allowed.includes(ext)) throw Error("対応素材形式ではありません");
  const dest = "assets/" + id + ext;
  fs.mkdirSync(dir + "/assets", { recursive: true });
  fs.copyFileSync(file, inside(dir, dest));
  e.file = dest;
  e.sha256 = sha(inside(dir, dest));
  if (provenance) e.provenance = provenance;
  list.entries.push(e);
  write(dir + "/assets.json", list);
  return e;
}
function load(dir) {
  dir = path.resolve(dir);
  return {
    dir,
    brief: read(dir + "/brief.json"),
    assets: read(dir + "/assets.json"),
    concepts: read(dir + "/concepts.json"),
    scene: read(dir + "/scene.json"),
  };
}
function resolvedText(b, t) {
  if (typeof t.ref === "string") {
    const r = b.copy[t.ref];
    if (typeof r !== "string" && !Array.isArray(r))
      throw Error("copy参照がありません: " + t.ref);
    return r;
  }
  if (typeof t.text === "string" || Array.isArray(t.text)) return t.text;
  throw Error("textかrefが必要");
}
function flattenedText(b, v) {
  return v.texts
    .flatMap((t) => {
      const x = resolvedText(b, t);
      return Array.isArray(x) ? x : [x];
    })
    .join("");
}
// Single-use is opt-in and applies to a full published phrase/group, not every copy token.
function singleUsePlans(brief, fail) {
  const normalize = value => (Array.isArray(value) ? value.join("") : value).normalize("NFKC").replace(/\s/gu, "");
  const plans = [];
  for (const ref of brief.singleUseRefs || []) {
    const value = brief.copy[ref];
    if (typeof value !== "string" && !Array.isArray(value)) {
      fail("single-use-ref", "単一使用のcopy参照がありません: " + ref);
      continue;
    }
    const phrase = normalize(value);
    if ([...phrase].length < 6) {
      fail("single-use-value", "単一使用は6文字以上の掲載文/配列の意味群全体を指定してください。短い値は対象外にできます: " + ref);
      continue;
    }
    plans.push({ ref, phrase, normalize });
  }
  return plans;
}
function validateSingleUse(brief, variant, plans, fail) {
  for (const { ref, phrase, normalize } of plans) {
    const refs = variant.texts.filter(text => text.ref === ref).length;
    if (refs !== 1) fail("single-use-count", "単一使用refは各案で1回必要です: " + ref + " (" + refs + "回)", variant.id);
    let occurrences = 0;
    for (const text of variant.texts) {
      let block;
      try { block = normalize(resolvedText(brief, text)); } catch { continue; }
      for (let from = 0, at; (at = block.indexOf(phrase, from)) !== -1; from = at + phrase.length) occurrences++;
    }
    if (occurrences !== 1) fail("single-use-literal", "掲載文の直接再掲/欠落を確認してください: " + ref + " (正規化後 " + occurrences + "回)", variant.id);
  }
}
// Only text turns, about the center of its declared box, so h is required.
// Static checks use the turned box's axis-aligned bounds: the same shape the
// browser measures after the CSS transform.
function validateRotation(t, v, page, centerGroups, fail) {
  const r = t.rotation;
  if (!Number.isFinite(r) || r === 0 || Math.abs(r) > 90 || !Number.isFinite(t.h) || !(t.h > 0))
    fail("rotation-metric", "回転は-90〜90度(0は書かない)で、回転中心を決める正のh(mm)が必要です: " + t.id, v.id);
  else if ([t.x, t.y, t.w].every(Number.isFinite) && t.w > 0) {
    const box = rotatedBox(t, r),
      safe = { x: page.safe, y: page.safe, w: page.width - 2 * page.safe, h: page.height - 2 * page.safe },
      fixed = [
        ...(v.qr ? [{ x: v.qr.x, y: v.qr.y, w: v.qr.size, h: v.qr.size }] : []),
        ...(v.logo ? [v.logo] : []),
        ...(v.protectedRegions || []),
      ];
    if (!inBox(box, safe)) fail("rotation-safe", "回転後の文字枠が安全域を出ます: " + t.id, v.id);
    if (fixed.some((f) => overlap(box, f, 0.5)))
      fail("rotation-collision", "回転後の文字枠がQR・ロゴ・被写体保護領域と重なります: " + t.id, v.id);
  }
  if (t.writingMode === "vertical-rl") fail("rotation-vertical", "縦組の文字は回転できません: " + t.id, v.id);
  if (centerGroups.has(t.group)) fail("rotation-axis", "中心軸の意味群の文字は回転できません: " + t.id, v.id);
}
function validate(p) {
  const { brief: b, assets: a, concepts: c, scene: s, dir } = p,
    issues = [];
  const fail = (code, detail, id) =>
    issues.push({ code, detail, ...(id ? { id } : {}) });
  const Ajv = require("ajv"),
    ajv = new Ajv({ allErrors: true, strict: false });
  ajv.addSchema(D.schema("design-intent"), "design-intent.schema.json");
  for (const [name, value] of [
    ["brief", b],
    ["concepts", c],
    ["scene", s],
  ]) {
    const v = ajv.compile(read(ROOT + "/schemas/" + name + ".schema.json"));
    if (!v(value)) fail("schema-" + name, ajv.errorsText(v.errors));
  }
  if (issues.length) return { fail: issues.length, issues };
  if (b.version !== 1 || s.version !== 1) fail("version", "対応バージョンは1");
  if (
    !Number.isInteger(b.count) ||
    b.count < 2 ||
    b.count > 30 ||
    !Number.isInteger(b.whiteCount) ||
    b.whiteCount < 0 ||
    b.whiteCount > b.count
  )
    fail("count", "countは比較のため2〜30、whiteCountは0〜count");
  // No case-specific fallback: the brief states its own axis groups and tones.
  const axisGroups = b.policy.center === "none" ? [] : (b.policy.axisGroups ?? []);
  const requiredTones = b.policy.requiredTones ?? [];
  if (b.policy.center === "none" && b.policy.axisGroups?.length)
    fail("axis-groups", "center=noneでは中心軸の意味群を指定できません");
  if (b.policy.center === "whole-page" && !axisGroups.length)
    fail("axis-groups", "全幅中心を使う意味群を1つ以上指定してください");
  if (requiredTones.length > b.count)
    fail("tone-range", "必須トーン数が案数を超えています");
  if (
    !b.page ||
    ![b.page.width, b.page.height, b.page.safe, b.page.whiteEdge].every(
      Number.isFinite,
    ) ||
    b.page.width <= 0 ||
    b.page.height <= 0 ||
    b.page.safe < 4 ||
    b.page.whiteEdge < 4 ||
    b.page.whiteEdge > b.page.safe ||
    b.page.safe * 2 >= Math.min(b.page.width, b.page.height)
  )
    fail("page", "紙面寸法と安全域を確認");
  if (
    !b.policy ||
    !Number.isFinite(b.policy.maxChars) ||
    b.policy.maxChars < 1 ||
    !Number.isFinite(b.policy.minFontPt) ||
    b.policy.minFontPt < 6 ||
    !Number.isFinite(b.policy.axisToleranceMm) ||
    b.policy.axisToleranceMm < 0 ||
    b.policy.axisToleranceMm > 2
  )
    fail("type-policy", "文字量・最小サイズ・中心許容差を確認");
  for (const k of ["facts", "assets", "privacy", "referenceUse", "styles"])
    if (b.confirmations?.[k] !== true) fail("confirmation", "未確認: " + k);
  if (!Array.isArray(b.stylePreferences) || !b.stylePreferences.length)
    fail("style-preferences", "表現形式の希望を確認してください");
  const hasQr = Boolean(b.qrUrl?.trim());
  if (hasQr) {
    try {
      if (!["https:", "http:"].includes(new URL(b.qrUrl).protocol)) throw Error();
    } catch {
      fail("qr-url", "HTTP(S)の申込URLを確認してください");
    }
  } else {
    const guidance = b.copy?.apply;
    const lines = Array.isArray(guidance) ? guidance : [guidance];
    if (!lines.length || lines.some((line) => typeof line !== "string" || !line.trim()) || !b.requiredRefs.includes("apply"))
      fail("apply-guidance", "URLが無い案件は確定した申込・来場案内をcopy.applyに書き、requiredRefsへapplyを含めてください");
  }
  if (
    !b.title?.trim() ||
    !Array.isArray(b.hero) ||
    !b.hero.length ||
    b.hero.some((t) => typeof t !== "string" || !t.trim())
  )
    fail("brief", "タイトル・主題が必要");
  if (!Array.isArray(b.requiredRefs) || !b.requiredRefs.length)
    fail("required", "必須copyキーを指定");
  for (const ref of b.requiredRefs || [])
    if (!b.copyGroups?.[ref])
      fail("copy-group", "必須情報の意味群を定義: " + ref);
  if (c.variants?.length !== b.count || s.variants?.length !== b.count)
    fail("variants", "案数がbriefと一致しません");
  const singleUse = singleUsePlans(b, fail);
  const ids = s.variants?.map((v) => v.id) || [];
  if (new Set(ids).size !== ids.length || ids.some((id) => !idOK(id)))
    fail("ids", "案IDが重複/不正");
  if (
    new Set((c.variants || []).map((v) => v.id)).size !== b.count ||
    ids.some((id) => !c.variants.some((v) => v.id === id))
  )
    fail("concept-ids", "構図案IDとシーンIDが一致しません");
  if (s.variants?.filter((v) => v.paper === "white").length !== b.whiteCount)
    fail("white-count", "白背景案数が不一致");
  for (const tone of requiredTones)
    if (!(c.variants || []).some((v) => v.tone === tone))
      fail("tone-range", "必須トーンの案がありません: " + tone);
  const amap = new Map();
  for (const e of a.entries || []) {
    if (amap.has(e.id) || !idOK(e.id)) fail("asset-id", "素材ID重複/不正");
    amap.set(e.id, e);
    try {
      if (sha(inside(dir, e.file)) !== e.sha256)
        fail("asset-hash", "素材が変更されました: " + e.id);
    } catch (err) {
      fail("asset-path", err.message);
    }
  }
  // A bundled photo's approval holds only in cases that may use it.
  const bundled = catalog(b.preset?.id);
  for (const e of a.entries || []) {
    if (e.kind !== "photo") continue;
    const source = bundled.find(
      (x) => (x.id === e.id || x.aliases?.includes(e.id)) && x.kind === "photo" && x.sha256 === e.sha256,
    );
    if (source) {
      if (
        JSON.stringify(e.requiredCropPx) !==
          JSON.stringify(source.requiredCropPx) ||
        Object.entries(source.privacy).some(([k, v]) => e.privacy?.[k] !== v)
      )
        fail(
          "photo-catalog-policy",
          "同梱写真の承認条件を変更できません: " + e.id,
        );
    } else if (!privacyComplete(e.privacy))
      fail(
        "photo-privacy-record",
        "新写真の人物・子供・端末画面・イベント表示の確認記録が不足: " + e.id,
      );
  }
  const centerGroups = new Set(axisGroups);
  const usedGroups = new Set(
    (s.variants || []).flatMap((v) => (v.texts || []).map((t) => t.group)),
  );
  for (const g of axisGroups)
    if (!usedGroups.has(g))
      fail("axis-groups", "中心軸の意味群が紙面に存在しません: " + g);
  for (const v of s.variants || []) {
    const id = v.id,
      concept = c.variants.find((k) => k.id === id);
    if (!concept) continue;
    if (concept.paper !== v.paper || !["white", "color"].includes(v.paper))
      fail("paper", "背景種別が不一致", id);
    if (!["light", "dark", "color"].includes(concept.tone))
      fail("tone", "toneはlight/dark/color", id);
    if (
      !concept.expression?.trim() ||
      !b.stylePreferences?.includes(concept.expression)
    )
      fail("expression", "ヒアリングで選んだ表現形式を指定", id);
    const sig = concept.signature || {};
    if (
      D.contract.signatureKeys.some(
        (k) => typeof sig[k] !== "string" || !sig[k].trim(),
      ) ||
      !concept.name?.trim()
    )
      fail("concept", "構図6要素と名前を具体化してください", id);
    const bg = amap.get(v.background?.asset);
    if (!bg || bg.kind !== "background")
      fail("background", "背景画像が必要", id);
    else {
      const pr = bg.provenance || {};
      if (pr.mode === "generated") {
        if (
          !pr.tool ||
          !pr.prompt ||
          !pr.generatedAt ||
          !pr.outputSha256 ||
          pr.outputSha256 !== bg.sha256
        )
          fail(
            "background-provenance",
            "実際の生成ツール・プロンプト・時刻・出力SHAを記録",
            id,
          );
      } else if (pr.mode !== "reuse-approved" || pr.confirmed !== true)
        fail(
          "background-new",
          "新生成または明示された既存背景の再利用確認が必要",
          id,
        );
    }
    if (!Array.isArray(v.texts) || !v.texts.length) {
      fail("texts", "文字配置がありません", id);
      continue;
    }
    const blockIds = v.texts.map((t) => t.id);
    if (
      new Set(blockIds).size !== blockIds.length ||
      blockIds.some((id) => !idOK(id))
    )
      fail("text-ids", "文字IDが重複/不正", id);
    for (const t of v.texts) {
      try {
        if (
          parseColor(
            t.color || v.ink || (v.paper === "white" ? "#142A32" : "#FFFFFF"),
          )[3] <= 0.01
        )
          fail("text-invisible", "透明な文字色は使用できません: " + t.id, id);
      } catch (error) {
        fail("text-color", error.message, id);
      }
      if (t.ref && b.copyGroups?.[t.ref] && t.group !== b.copyGroups[t.ref])
        fail(
          "copy-group",
          "意味群の変更で配置規則を回避できません: " + t.ref,
          id,
        );
      if (
        ![t.x, t.y, t.w, t.size].every(Number.isFinite) ||
        t.w <= 0 ||
        t.size < b.policy.minFontPt
      )
        fail("text-metric", "位置・幅・最小文字サイズを確認: " + t.id, id);
      if (
        centerGroups.has(t.group) &&
        (t.align !== "center" ||
          Math.abs(t.x + t.w / 2 - b.page.width / 2) > b.policy.axisToleranceMm)
      )
        fail("page-axis", "紙面全体の中心に配置: " + t.id, id);
      if (t.rotation !== undefined) validateRotation(t, v, b.page, centerGroups, fail);
      if (t.writingMode === "vertical-rl" && (!(t.h > 0) || !Number.isFinite(t.h) || t.layout === "row"))
        fail("vertical-metric", "縦組には正のh(mm)とlines構成が必要です: " + t.id, id);
      if (!["left", "center", "right"].includes(t.align))
        fail("align", "文字揃えが不正", id);
      if (!["sans", "serif", "display"].includes(t.font))
        fail("font-role", "fontはsans/serif/display", id);
      try {
        if (![resolvedText(b, t)].flat().join("").trim())
          fail("copy-empty", "掲載文が空です: " + t.id, id);
      } catch (e) {
        fail("copy-ref", e.message, id);
      }
    }
    for (const ref of b.requiredRefs || [])
      if (!v.texts.some((t) => t.ref === ref))
        fail("copy-missing", "必須情報: " + ref, id);
    validateSingleUse(b, v, singleUse, fail);
    let text = "";
    try {
      text = flattenedText(b, v);
    } catch {}
    const n = text.normalize("NFC").replace(/\s/g, "").length;
    if (n > b.policy.maxChars)
      fail("copy-volume", "字数" + n + " > " + b.policy.maxChars, id);
    const normalize = (t) => String(t).normalize("NFC").replace(/\s/g, "");
    if (!(b.hero || []).every((h) => normalize(text).includes(normalize(h))))
      fail("hero-missing", "最優先の主題が欠落", id);
    for (const f of b.forbiddenText || [])
      if (normalize(text).includes(normalize(f))) fail("forbidden-copy", f, id);
    for (const f of v.photos || [])
      if (amap.get(f.asset)?.kind !== "photo")
        fail("photo-kind", "photosにはphoto素材を指定: " + f.asset, id);
    if (v.logo && amap.get(v.logo.asset)?.kind !== "logo")
      fail("logo-kind", "logoにはlogo素材を指定", id);
    const frames = [...(v.photos || []), ...(v.logo ? [v.logo] : [])];
    for (const f of frames) {
      const e = amap.get(f.asset);
      if (!e || e.usage === "reference-only")
        fail("asset-use", "使えない素材: " + f.asset, id);
      if (e?.kind === "photo" && e.privacy?.reviewed !== true)
        fail("photo-privacy", "写真の公開範囲を確認: " + f.asset, id);
      if (
        e?.requiredCropPx &&
        JSON.stringify(f.cropPx) !== JSON.stringify(e.requiredCropPx)
      )
        fail("privacy-crop", "承認cropが必須: " + f.asset, id);
      if (![f.x, f.y, f.w, f.h].every(Number.isFinite) || f.w <= 0 || f.h <= 0)
        fail("frame", "素材寸法を確認", id);
    }
    if ([...frames, v.qr, ...(v.fields || []), ...(v.protectedRegions || [])].some((f) => f?.rotation !== undefined))
      fail("unsupported-rotation", "回転できるのは文字だけです", id);
    for (const r of v.protectedRegions || [])
      if (![r.x, r.y, r.w, r.h].every(Number.isFinite) || r.w <= 0 || r.h <= 0)
        fail("protected-frame", "保護領域の寸法が不正", id);
    if (
      v.photos?.length &&
      (!Array.isArray(v.protectedRegions) || !v.protectedRegions.length)
    )
      fail(
        "face-protection",
        "写真の顔など文字を重ねない領域を指定してください",
        id,
      );
    if (
      hasQr && (!v.qr ||
      ![v.qr.x, v.qr.y, v.qr.size].every(Number.isFinite) ||
      v.qr.size < 22)
    )
      fail("qr-frame", "QR寸法は22mm以上", id);
    if (!hasQr && v.qr) fail("qr-without-url", "URLが無い案件はQR枠を指定しないでください", id);
    if (
      v.logo &&
      (v.logo.x < b.page.safe ||
        v.logo.y < b.page.safe ||
        v.logo.x + v.logo.w > b.page.width - b.page.safe ||
        v.logo.y + v.logo.h > b.page.height - b.page.safe)
    )
      fail("logo-safe", "ロゴを安全域内に配置", id);
    for (const r of v.protectedRegions || [])
      if (v.logo && intersects(v.logo, r))
        fail(
          "logo-subject-collision",
          "ロゴが被写体保護領域と重なっています",
          id,
        );
    if (v.qr) {
      const q = { x: v.qr.x, y: v.qr.y, w: v.qr.size, h: v.qr.size };
      if (v.logo && intersects(q, v.logo))
        fail("qr-logo-collision", "QRとロゴが重なっています", id);
      for (const r of v.protectedRegions || [])
        if (intersects(q, r))
          fail(
            "qr-subject-collision",
            "QRが被写体保護領域と重なっています",
            id,
          );
    }
    if (
      v.qr &&
      (v.qr.x < b.page.safe ||
        v.qr.y < b.page.safe ||
        v.qr.x + v.qr.size > b.page.width - b.page.safe ||
        v.qr.y + v.qr.size > b.page.height - b.page.safe)
    )
      fail("qr-safe", "静寂域を含むQRを安全域内に", id);
  }
  D.validateIntent(p, fail);
  for (let i = 0; i < (c.variants || []).length; i++)
    for (let j = i + 1; j < c.variants.length; j++) {
      const x = c.variants[i],
        y = c.variants[j];
      if (
        D.contract.signatureKeys.filter(
          (k) => x.signature[k] !== y.signature?.[k],
        ).length < 3
      )
        fail("diversity", "3要素以上の構図差が必要: " + x.id + "/" + y.id);
    }
  return { fail: issues.length, issues };
}
// common: inputs every variant depends on (brief, analysis, assets, norms,
// engine). A change there invalidates all variants. variants[id]: common plus
// that variant's concept and scene entry, so editing one variant leaves the
// others' renders and reviews valid.
function fingerprints(p) {
  const common = hash({
    brief: p.brief,
    presetKnowledge: (p.brief.preset?.knowledgeFiles || []).map((f) => [f, sha(ROOT + "/" + f)]),
    analysisArtifacts: ["analysis.json", "analysis-review.json"].map(n => [n, fs.existsSync(p.dir + "/" + n) ? sha(p.dir + "/" + n) : null]),
    assets: p.assets,
    concepts: { ...p.concepts, variants: undefined },
    scene: { ...p.scene, variants: undefined },
    engine: [
      "project.cjs",
      "render.cjs",
      "checks.cjs",
      "design.cjs",
      "geometry.cjs",
      "contrast.cjs",
      "merge-checks.cjs",
      "merge-pdf.cjs",
      "analysis.cjs",
      "essence.cjs",
      "intake.cjs",
    ].map((n) => [n, sha(__dirname + "/" + n)]),
    schemas: ["brief", "concepts", "scene", "design-intent", "analysis", "analysis-review"].map((n) => [
      n,
      sha(ROOT + "/schemas/" + n + ".schema.json"),
    ]),
    designContract: sha(ROOT + "/references/design-contract.json"),
    dependencies: sha(ROOT + "/package-lock.json"),
  });
  const ids = [...new Set([...p.scene.variants, ...p.concepts.variants].map((v) => v.id))];
  const variants = Object.fromEntries(
    ids.map((id) => [
      id,
      hash({
        common,
        concept: p.concepts.variants.find((v) => v.id === id) || null,
        scene: p.scene.variants.find((v) => v.id === id) || null,
      }),
    ]),
  );
  return { common, variants };
}
// Without id: the whole project (any change). With id: that variant only.
function fingerprint(p, id) {
  const f = fingerprints(p);
  if (id === undefined) return hash(f);
  if (!f.variants[id]) throw Error("案の指紋がありません: " + id);
  return f.variants[id];
}
module.exports = {
  ROOT,
  read,
  write,
  sha,
  hash,
  esc,
  inside,
  idOK,
  init,
  catalog,
  importAsset,
  load,
  resolvedText,
  flattenedText,
  validate,
  preset,
  fingerprints,
  fingerprint,
};
