"use strict";
// This contract checks whether design decisions and observations are present and
// traceable. It does not turn visual balance or testimony into a numeric proof.
const fs = require("node:fs");
const path = require("node:path");
const crypto = require("node:crypto");
const { isDeepStrictEqual } = require("node:util");
const Ajv = require("ajv");
const { inBox } = require("./geometry.cjs");
const ROOT = path.resolve(__dirname, "..");
const read = (relative) =>
  JSON.parse(fs.readFileSync(path.join(ROOT, relative), "utf8"));
const contract = read("references/design-contract.json");
const schema = (name) => read("schemas/" + name + ".schema.json");
const sha = (file) =>
  crypto.createHash("sha256").update(fs.readFileSync(file)).digest("hex");
const validDate = (value) =>
  /^\d{4}-\d{2}-\d{2}T/.test(value) && Number.isFinite(Date.parse(value));
const normalize = (value) =>
  String(value).normalize("NFKC").replace(/\s+/g, "").toLowerCase();
const colorKey = (value) =>
  String(value).trim().toLowerCase().replace(/\s/g, "");
const sameSet = (actual, expected) =>
  actual.length === expected.length &&
  new Set(actual).size === actual.length &&
  expected.every((key) => actual.includes(key));

function declaredColors(variant) {
  return [
    ...new Set(
      [
        variant.baseColor || (variant.paper === "white" ? "#fff" : "#080C10"),
        variant.ink || (variant.paper === "white" ? "#142A32" : "#FFFFFF"),
        ...(variant.texts || [])
          .filter((text) => text.color)
          .map((text) => text.color),
        ...(variant.fields || []).map((field) => field.color || "#E4ECE8"),
      ].map(colorKey),
    ),
  ];
}

function validateIntent(project, fail) {
  if (
    typeof project.brief.designer !== "string" ||
    !project.brief.designer.trim()
  ) {
    fail(
      "designer-identity",
      "制作担当者の実際のidentityをbrief.designerへ記録してください",
    );
  }
  const rejectedReasons = new Set();
  for (const concept of project.concepts.variants) {
    const variant = project.scene.variants.find(
      (item) => item.id === concept.id,
    );
    if (
      !sameSet(Object.keys(concept.signature || {}), contract.signatureKeys)
    ) {
      fail(
        "signature-keys",
        "signatureは共通契約の既知6要素だけを使用してください",
        concept.id,
      );
    }
    const intent = concept.designIntent;
    // The JSON schema reports missing/malformed values before this semantic step.
    if (!intent || !variant) continue;
    const groups = [...new Set(variant.texts.map((text) => text.group))];
    if (!sameSet(intent.readingOrder, groups)) {
      fail(
        "intent-reading-order",
        "readingOrderは実在する全text groupを重複なく含めてください",
        concept.id,
      );
    }
    if (
      !sameSet(
        intent.groups.map((item) => item.group),
        groups,
      )
    ) {
      fail(
        "intent-groups",
        "各text groupの役割と配置理由を重複なく記録してください",
        concept.id,
      );
    }
    const palette = intent.palette.map((item) => colorKey(item.color));
    if (new Set(palette).size !== palette.length) {
      fail(
        "intent-palette",
        "同じ宣言色の説明を重複させないでください",
        concept.id,
      );
    }
    for (const color of declaredColors(variant)) {
      if (!palette.includes(color))
        fail(
          "intent-palette",
          "宣言色の役割と理由がありません: " + color,
          concept.id,
        );
    }
    const page = {
      x: 0,
      y: 0,
      w: project.brief.page.width,
      h: project.brief.page.height,
    };
    for (const area of intent.whitespace) {
      if (!inBox(area, page))
        fail(
          "intent-whitespace",
          "意図する余白領域を紙面内に指定してください",
          concept.id,
        );
    }
    for (const alt of intent.rejectedAlternatives) {
      const key = normalize(alt.reason);
      if (rejectedReasons.has(key))
        fail(
          "intent-rejected",
          "不採用理由が他案と同文です。この案で比較した候補と理由を書いてください",
          concept.id,
        );
      rejectedReasons.add(key);
    }
  }
  validateFeedback(project, fail);
}

function feedbackForVariant(project, variantId) {
  return (project.brief.feedback || []).filter(
    (entry) =>
      entry.variantIds === undefined ||
      entry.variantIds === "all" ||
      entry.variantIds.includes(variantId),
  );
}

function targetReferences(variant) {
  return new Set([
    "page",
    "background",
    ...(variant.qr ? ["qr"] : []),
    ...(variant.logo ? ["logo"] : []),
    ...variant.texts.map((text) => "text:" + text.id),
    ...variant.texts.map((text) => "group:" + text.group),
    ...(variant.photos || []).map((photo) => "photo:" + photo.asset),
    ...(variant.fields || []).map((_, index) => "field:" + index),
  ]);
}

function validateFeedback(project, fail) {
  if (project.brief.feedback === undefined) return;
  const ajv = new Ajv({ allErrors: true, strict: false });
  const validate = ajv.compile(schema("brief").properties.feedback);
  if (!validate(project.brief.feedback)) {
    fail(
      "feedback-schema",
      "フィードバックの入力が不足しています: " +
        ajv.errorsText(validate.errors),
    );
    return;
  }
  const ids = new Set();
  for (const entry of project.brief.feedback) {
    if (ids.has(entry.id))
      fail("feedback-id", "フィードバックIDが重複しています: " + entry.id);
    ids.add(entry.id);
    if (entry.kind === "required" && entry.decision === "decline") {
      fail(
        "feedback-required",
        "明示された必須指示は見送りにできません。両立不能なら未決のまま確認してください: " +
          entry.id,
      );
    }
    const roles = entry.analysis.map((analysis) => analysis.role);
    if (
      new Set(roles).size !== roles.length ||
      roles.some((role) => !contract.expertRoles.includes(role))
    ) {
      fail(
        "feedback-analysis",
        "既存3専門役のうち実際に分析した担当の観察を、役ごとに一度記録してください: " +
          entry.id,
      );
    }
    const variantIds =
      entry.variantIds === undefined || entry.variantIds === "all"
        ? project.scene.variants.map((variant) => variant.id)
        : entry.variantIds;
    for (const id of variantIds) {
      const variant = project.scene.variants.find(
        (candidate) => candidate.id === id,
      );
      if (!variant) {
        fail(
          "feedback-variant",
          "フィードバックの対象案がありません: " + entry.id + "/" + id,
        );
        continue;
      }
      const references = targetReferences(variant);
      for (const target of entry.targets)
        if (!references.has(target)) {
          fail(
            "feedback-target",
            "対象要素が案にありません。対象案か要素の指定を確認してください: " +
              entry.id +
              "/" +
              target,
            id,
          );
        }
    }
  }
}

function validateFeedbackChecks(project, item) {
  const entries = feedbackForVariant(project, item.id);
  const checks = item.feedbackChecks || [];
  if (
    !sameSet(
      checks.map((check) => check.feedbackId),
      entries.map((entry) => entry.id),
    )
  ) {
    throw Error("フィードバックの対象要求と最終評価が一致しません: " + item.id);
  }
  for (const entry of entries) {
    const check = checks.find((candidate) => candidate.feedbackId === entry.id);
    if (entry.decision === "pending" || check.verdict !== "PASS") {
      throw Error(
        "フィードバックが未決または未解決です: " + entry.id + "/" + item.id,
      );
    }
    if (
      !check.criteria.length ||
      check.criteria.some(
        (key) =>
          !contract.qualityDimensions.includes(key) ||
          item.criteria[key]?.verdict !== "PASS",
      )
    ) {
      throw Error(
        "フィードバックの評価証拠は、この案の合格したcriteriaを参照してください: " +
          entry.id,
      );
    }
    for (const analysis of entry.analysis) {
      if (
        !check.criteria.some((key) =>
          contract.expertDimensions[analysis.role].includes(key),
        )
      ) {
        throw Error(
          "分析した専門観点の新画像証拠がありません: " +
            entry.id +
            "/" +
            analysis.role,
        );
      }
    }
  }
}

function reviewPolicyFingerprint() {
  const current = read("references/design-contract.json");
  const inputs = current.reviewPolicyFiles.map((relative) => {
    const absolute = path.resolve(ROOT, relative);
    if (!absolute.startsWith(ROOT + path.sep))
      throw Error("品質契約の範囲外参照: " + relative);
    if (!fs.existsSync(absolute))
      throw Error("品質契約のファイルがありません: " + relative);
    return [relative, sha(absolute)];
  });
  return crypto
    .createHash("sha256")
    .update(JSON.stringify(inputs))
    .digest("hex");
}

// Both review stages share R1's text and essence-clause contract.
// Image-specific classification and routing remain in classifyFixes.
function assertMandatoryFixes(fixes, label = "評価") {
  const clauses = new Set(read("references/essence.json").clauses.map((c) => c.id));
  if (!Array.isArray(fixes)) throw Error("必須修正は配列にしてください: " + label);
  for (const fix of fixes) {
    if (!fix || typeof fix.text !== "string" || !fix.text.trim())
      throw Error("必須修正には text が必要です: " + label);
    if (!Array.isArray(fix.serves) || !fix.serves.length || new Set(fix.serves).size !== fix.serves.length)
      throw Error("必須修正の serves に本質条項を1つ以上、重複なく指定してください: " + label);
    const unknown = fix.serves.filter((id) => !clauses.has(id));
    if (unknown.length)
      throw Error("必須修正の serves に本質条項（essence.json）に無い ID があります: " + label + "/" + unknown.join(","));
  }
}

// R1: a mandatory fix serves an essence clause and goes back where the
// workflow.md table says; a preference is only noted and never blocks a variant.
// Also used for FIX reviews, so the cycle ledger reads the same classification.
function classifyFixes(review) {
  for (const item of review?.items || [])
    if ((item?.mandatoryFixes || []).some((fix) => fix?.fixClass === "preference"))
      throw Error(
        "好み（preference）は必須修正にできません。preferenceNotes に記録してください: " +
          item.id,
      );
  const ajv = new Ajv({ allErrors: true, strict: false });
  const validate = ajv.compile(schema("visual-review"));
  if (!validate(review))
    throw Error(
      "目視レビュー契約に不足があります: " + ajv.errorsText(validate.errors),
    );
  const fixClasses = {},
    returnTo = new Set();
  let fixCount = 0,
    preferenceNotes = 0;
  for (const item of review.items) {
    if ((item.decision === "FIX") !== item.mandatoryFixes.length > 0)
      throw Error(
        "FIX の案には必須修正を 1 つ以上、それ以外は 0 件にしてください。好みだけなら preferenceNotes へ残します: " +
          item.id,
      );
    assertMandatoryFixes(item.mandatoryFixes, item.id);
    for (const fix of item.mandatoryFixes) {
      if (contract.fixRouting[fix.fixClass] !== fix.returnTo)
        throw Error(
          "修正の戻り先が分類と一致しません（workflow.md の表）: " +
            item.id + "/" + fix.fixClass + "→" + fix.returnTo,
        );
      fixClasses[fix.fixClass] = (fixClasses[fix.fixClass] || 0) + 1;
      returnTo.add(fix.returnTo);
      fixCount++;
    }
    for (const note of item.preferenceNotes) {
      if (note.category !== undefined && !contract.qualityDimensions.includes(note.category))
        throw Error(
          "preferenceNotes の category は " +
            contract.qualityDimensions.join("/") +
            " から選んでください: " + item.id,
        );
      preferenceNotes++;
    }
  }
  return { fixClasses, returnTo: [...returnTo], fixCount, preferenceNotes };
}

// Past reviews of this project: reviews/<label>/ archives (oldest first), then
// the current root files. archiveReview is the only writer of the archive.
const REVIEW_FILES = ["pilot-review.json", "visual-review.json"];
function reviewHistory(project) {
  if (!project?.dir) return [];
  const archive = path.join(project.dir, "reviews");
  const dirs = [
    ...(fs.existsSync(archive)
      ? fs.readdirSync(archive).sort().map((name) => path.join(archive, name))
      : []),
    project.dir,
  ];
  return dirs
    .flatMap((dir) => REVIEW_FILES.map((name) => path.join(dir, name)))
    .filter((file) => fs.existsSync(file))
    .map((file) => ({
      file: path.relative(project.dir, file),
      sha256: sha(file),
      review: JSON.parse(fs.readFileSync(file, "utf8")),
    }));
}
function archiveReview(project, name, label) {
  if (!REVIEW_FILES.includes(name) || !/^[A-Za-z0-9_-]{1,48}$/.test(String(label)))
    throw Error("退避できるのは pilot-review.json か visual-review.json で、label は英数字です");
  const from = path.join(project.dir, name),
    to = path.join(project.dir, "reviews", label, name);
  if (!fs.existsSync(from)) return null;
  if (fs.existsSync(to))
    throw Error("退避先に既存のレビューがあります: " + path.relative(project.dir, to));
  fs.mkdirSync(path.dirname(to), { recursive: true });
  fs.renameSync(from, to);
  return path.relative(project.dir, to);
}
const priorItems = (history, id) =>
  history.flatMap((entry) => entry.review.items || []).filter((prev) => prev?.id === id);
const fixedBefore = (history, id, pngSha256) =>
  priorItems(history, id).some((prev) => prev.pngSha256 === pngSha256 && prev.decision === "FIX");

// MD-11: a lens is required only where expertEscalation says so (R3, nonGoals):
// a low-confidence criterion, an earlier FIX on that variant, or the user's request.
function requiredExperts(project, item, history) {
  const rule = contract.expertEscalation;
  const requested = project.brief[rule.briefRequestKey] || [];
  const unknown = requested.filter((role) => !contract.expertRoles.includes(role));
  if (unknown.length)
    throw Error("brief." + rule.briefRequestKey + " に未知の専門役があります: " + unknown.join(","));
  const prior = priorItems(history, item.id);
  return contract.expertRoles.filter(
    (role) =>
      requested.includes(role) ||
      prior.some((prev) => rule.priorVerdicts.includes(prev.expertReviews?.[role]?.verdict)) ||
      contract.expertDimensions[role].some(
        (key) =>
          rule.criterionConfidence.includes(item.criteria?.[key]?.confidence) ||
          prior.some((prev) => rule.priorVerdicts.includes(prev.criteria?.[key]?.verdict)),
      ),
  );
}

// SS-1/R4: a variant whose inputs, image and yardstick are unchanged keeps its
// earlier independent PASS instead of being judged again. Chains point at the original.
function reusable(history, id, variantFingerprint, pngSha256, policy, designer) {
  if (fixedBefore(history, id, pngSha256)) return null;
  for (const entry of [...history].reverse()) {
    const r = entry.review,
      prev = (r.items || []).find((candidate) => candidate?.id === id);
    if (
      !prev ||
      prev.decision !== "PASS" ||
      prev.variantFingerprint !== variantFingerprint ||
      prev.pngSha256 !== pngSha256 ||
      r.reviewPolicyFingerprint !== policy ||
      r.mode === "self-review" ||
      !normalize(r.reviewer || "") ||
      normalize(r.reviewer) === designer
    )
      continue;
    return prev.reusedFrom
      ? structuredClone(prev)
      : { ...structuredClone(prev), reusedFrom: { file: entry.file, sha256: entry.sha256 } };
  }
  return null;
}
function reusedSource(item, history, policy, designer) {
  const { reusedFrom, ...own } = item;
  // Content-addressed: the source may have been archived since (file is a hint).
  const source = history.find((entry) => entry.sha256 === reusedFrom.sha256);
  const prev = source?.review.items?.find((candidate) => candidate?.id === item.id);
  if (!prev || prev.reusedFrom || !isDeepStrictEqual(own, prev))
    throw Error("再利用したレビューの元が見つからないか、元の所見と一致しません: " + item.id);
  const r = source.review;
  if (r.reviewPolicyFingerprint !== policy)
    throw Error("目視レビューが古いです。再利用元の品質基準が最新と異なります: " + item.id);
  if (fixedBefore(history, item.id, item.pngSha256))
    throw Error("同じ画像に FIX が出ているため、以前の PASS を再利用できません: " + item.id);
  const reviewer = normalize(r.reviewer || "");
  if (!reviewer || reviewer === designer || r.mode === "self-review" || !validDate(r.reviewedAt))
    throw Error("独立レビュー未達です。再利用元が制作担当とは別の担当の記録ではありません: " + item.id);
  return { reviewer, mode: r.mode, reviewedAt: r.reviewedAt };
}

// SS-8: the review must postdate the render it says it looked at.
function assertSeenAfterRender(project, row, reviewedAt) {
  const file = path.join(project.dir || "", "out", row.id, "render.json");
  const render = project.dir && fs.existsSync(file) ? JSON.parse(fs.readFileSync(file, "utf8")) : null;
  if (!render || render.pngSha256 !== row.pngSha256 || !(Date.parse(render.createdAt) < Date.parse(reviewedAt)))
    throw Error(
      "実見が描画より前か、描画記録（out/" + row.id + "/render.json）と画像が一致しません。最新の描画を見てから記録してください: " +
        row.id,
    );
}
// SS-8: a new image described with the previous image's words was not looked at again.
function assertNotCopied(item, history) {
  const same = (a, b) => typeof a === "string" && normalize(a) === normalize(b);
  for (const prev of priorItems(history, item.id))
    if (
      prev.pngSha256 !== item.pngSha256 &&
      (same(prev.observations, item.observations) ||
        contract.qualityDimensions.every((key) =>
          same(prev.criteria?.[key]?.observation, item.criteria[key].observation),
        ))
    )
      throw Error("前回の画像の観察文を新しい画像へ転記しています。新しい画像を見て書き直してください: " + item.id);
}

// Approval, template generation and review validation share the same mapping.
// A renamed or removed original with strengths must never become an empty list.
function preservationByOutput(project) {
  const file = project.dir ? path.join(project.dir, "analysis.json") : "";
  if (!file || !fs.existsSync(file)) return {};
  const analysis = JSON.parse(fs.readFileSync(file, "utf8"));
  return require("./analysis.cjs").resolvePreservations(
    analysis,
    (project.scene?.variants || []).map((variant) => variant.id),
  );
}
function evidenceTemplate() {
  return {
    verdict: "pending",
    confidence: "",
    region: { x: 0, y: 0, w: 0, h: 0 },
    observation: "",
    intentRef: "",
  };
}
const expertTemplate = (key) => ({
  reviewer: "",
  verdict: "pending",
  criteria: [...contract.expertDimensions[key]],
});
// Archive the previous review with archiveReview first: unchanged variants are
// then pre-filled from it (reusedFrom) and only changed ones are judged again.
function reviewTemplate(project, checks) {
  const preservation = preservationByOutput(project);
  const { fingerprint } = require("./project.cjs");
  const policy = reviewPolicyFingerprint(),
    designer = normalize(project.brief.designer || ""),
    history = reviewHistory(project);
  return {
    fingerprint: checks.fingerprint,
    reviewPolicyFingerprint: policy,
    reviewer: "",
    reviewedAt: "",
    mode: "independent-reviewer-lenses",
    items: checks.rows.map((row) => {
      const variantFingerprint = fingerprint(project, row.id);
      const reused = reusable(history, row.id, variantFingerprint, row.pngSha256, policy, designer);
      if (reused) return reused;
      const item = freshItem(project, row, variantFingerprint, preservation[row.id] || []);
      item.expertReviews = Object.fromEntries(
        requiredExperts(project, item, history).map((key) => [key, expertTemplate(key)]),
      );
      return item;
    }),
  };
}
function freshItem(project, row, variantFingerprint, strengths) {
  return {
    id: row.id,
    pngSha256: row.pngSha256,
    variantFingerprint,
    viewedFull: false,
    viewedThumbnail: false,
    viewedDetails: false,
    readingTest: {
      firstRead: "",
      firstGroup: "",
      nextRead: "",
      nextGroup: "",
      hesitation: "",
      audienceCue: "",
    },
    privacyChecked: false,
    axisChecked: false,
    worldviewChecked: false,
    observations: "",
    criteria: Object.fromEntries(
      contract.qualityDimensions.map((key) => [key, evidenceTemplate()]),
    ),
    expertReviews: {},
    ...(feedbackForVariant(project, row.id).length
      ? {
          feedbackChecks: feedbackForVariant(project, row.id).map(
            (entry) => ({
              feedbackId: entry.id,
              verdict: "pending",
              criteria: [],
            }),
          ),
        }
      : {}),
    ...(strengths.length
      ? {
          preservationChecks: strengths.map(
            (strength) => ({ strength, verdict: "pending", observation: "" }),
          ),
        }
      : {}),
    mandatoryFixes: [],
    preferenceNotes: [],
    decision: "pending",
  };
}

function pointerValue(intent, pointer) {
  const parts = pointer
    .slice(1)
    .split("/")
    .map((part) => part.replace(/~1/g, "/").replace(/~0/g, "~"));
  let value = intent;
  for (const part of parts) {
    if (!value || typeof value !== "object" || !Object.hasOwn(value, part))
      return undefined;
    value = value[part];
  }
  return value;
}
function concreteObservation(value) {
  if (typeof value !== "string" || [...value.trim()].length < 12) return false;
  return !/^(ok|pass|問題なし|確認済み|良好|合格|大丈夫|looks?good)[。.!！]*$/i.test(
    normalize(value),
  );
}
function validateEvidence(evidence, intent, roots, page, label) {
  if (
    evidence.verdict !== "PASS" ||
    !concreteObservation(evidence.observation)
  ) {
    throw Error(
      "目視レビュー未達: " + label + "。位置と具体的な観察を記録してください",
    );
  }
  if (!inBox(evidence.region, page))
    throw Error("目視レビュー領域が紙面外です: " + label);
  if (
    !roots.some(
      (root) =>
        evidence.intentRef === root ||
        evidence.intentRef.startsWith(root + "/"),
    ) ||
    pointerValue(intent, evidence.intentRef) === undefined
  ) {
    throw Error("目視レビューの設計意図参照が不正です: " + label);
  }
}

// Read words must match a printed text of that group, so the intended answer
// cannot be copied without looking. Lazy require: project.cjs requires this file.
function readFromGroup(project, variantId, group, read) {
  const { resolvedText } = require("./project.cjs");
  const plain = (value) => normalize(value).replace(/[\p{P}\p{S}]/gu, "");
  const target = plain(read);
  const variant = project.scene.variants.find((v) => v.id === variantId);
  return (variant?.texts || [])
    .filter((text) => text.group === group)
    .flatMap((text) => [resolvedText(project.brief, text)].flat())
    .map(plain)
    .some((printed) => printed.length > 1 && (target.includes(printed) || printed.includes(target)));
}

// The reviewer records what was actually read before opening the intent; the
// comparison is done here, not self-declared, so a mismatch cannot pass.
function validateReadingTest(test, intent, id, project) {
  const groups = new Set((intent.groups || []).map((g) => g.group));
  if (
    !groups.has(test.firstGroup) ||
    !groups.has(test.nextGroup) ||
    test.firstGroup === test.nextGroup
  )
    throw Error("初見で読めた意味群は設計意図の別々の群で記録してください: " + id);
  if (!readFromGroup(project, id, test.firstGroup, test.firstRead) || !readFromGroup(project, id, test.nextGroup, test.nextRead))
    throw Error("初見で読めた文言がその意味群の掲載文にありません。見えた語をそのまま記録してください: " + id);
  if (!concreteObservation(test.audienceCue))
    throw Error("誰に向けた案内と分かった手掛かりを、初見の語や図像で記録してください: " + id);
  if (test.firstGroup !== intent.readingOrder[0])
    throw Error(
      "初見で最初に読めた意味群が設計意図の最初と異なります。構図を直すか意図を見直してください: " +
        id,
    );
  if (
    test.nextGroup !== intent.readingOrder[1] &&
    !concreteObservation(test.hesitation)
  )
    throw Error(
      "2番目に読めた意味群が意図と異なる理由・迷いを記録してください: " + id,
    );
}

function validateReview(review, checks, project) {
  if (!project)
    throw Error("制作担当と設計意図を含むprojectが目視検査に必要です");
  const preservationById = preservationByOutput(project);
  validateFeedback(project, (code, detail) => {
    throw Error(detail);
  });
  classifyFixes(review);
  const policy = reviewPolicyFingerprint();
  if (
    review.fingerprint !== checks.fingerprint ||
    review.reviewPolicyFingerprint !== policy
  ) {
    throw Error(
      "目視レビューが古いです。入力・画像と最新の品質基準を確認してください",
    );
  }
  if (!validDate(review.reviewedAt)) throw Error("目視レビューの実施日時が不正です");
  const designer = normalize(project.brief.designer || "");
  const reviewer = normalize(review.reviewer);
  if (
    !designer ||
    !reviewer ||
    designer === reviewer ||
    review.mode === "self-review"
  ) {
    throw Error(
      "独立レビュー未達です。制作担当とは別の担当者による確認を待つか、人へ確認を依頼してください",
    );
  }
  if (
    !sameSet(
      review.items.map((item) => item.id),
      checks.rows.map((row) => row.id),
    )
  ) {
    throw Error("目視レビューの案IDが全案と一致しません");
  }
  const { fingerprint } = require("./project.cjs");
  const history = reviewHistory(project),
    reusedItems = [];
  const seen = new Map();
  const page = {
    x: 0,
    y: 0,
    w: project.brief.page.width,
    h: project.brief.page.height,
  };
  for (const row of checks.rows) {
    const item = review.items.find((candidate) => candidate.id === row.id);
    const intent = project.concepts.variants.find(
      (candidate) => candidate.id === row.id,
    )?.designIntent;
    if (
      !intent ||
      item.pngSha256 !== row.pngSha256 ||
      item.decision !== "PASS" ||
      item.mandatoryFixes.length ||
      [
        "viewedFull",
        "viewedThumbnail",
        "viewedDetails",
        "privacyChecked",
        "axisChecked",
        "worldviewChecked",
      ].some((key) => item[key] !== true)
    ) {
      throw Error("目視レビュー不合格: " + row.id);
    }
    if (item.variantFingerprint !== fingerprint(project, row.id))
      throw Error("目視レビューが古いです。この案の入力が変わりました: " + row.id);
    // Who judged this item: the reused source keeps its own reviewer and mode.
    const by = item.reusedFrom
      ? reusedSource(item, history, policy, designer)
      : { reviewer, mode: review.mode };
    if (item.reusedFrom) reusedItems.push(row.id);
    else {
      assertSeenAfterRender(project, row, review.reviewedAt);
      assertNotCopied(item, history);
    }
    if (!concreteObservation(item.observations))
      throw Error("目視レビューの全体所見が不足しています: " + row.id);
    const roles = Object.keys(item.expertReviews);
    if (!sameSet(Object.keys(item.criteria), contract.qualityDimensions) || roles.some((key) => !contract.expertRoles.includes(key)))
      throw Error("目視レビューの必須観点が不足しているか、未知の専門知見レンズがあります: " + row.id);
    const missing = requiredExperts(project, item, history).filter((key) => !roles.includes(key));
    if (missing.length)
      throw Error(
        "昇格条件（確信度 low・前回 FIX・利用者の指定）に当たる専門知見レビューがありません: " +
          row.id + "/" + missing.join(","),
      );
    const remember = (key, value) => {
      let normalized = normalize(value);
      for (const candidate of checks.rows)
        normalized = normalized.replaceAll(normalize(candidate.id), "");
      normalized = normalized.replace(/[\p{P}\p{S}]/gu, "");
      if (seen.has(key + ":" + normalized))
        throw Error(
          "案ごとの観察が同文です。各画像の位置と相違を確認してください: " +
            row.id +
            "/" +
            key,
        );
      seen.set(key + ":" + normalized, row.id);
    };
    remember("summary", item.observations);
    validateReadingTest(item.readingTest, intent, row.id, project);
    const expected = preservationById[row.id] || [];
    const preservation = item.preservationChecks || [];
    if (
      !sameSet(
        preservation.map((check) => check.strength),
        expected,
      )
    )
      throw Error("分析の保持点と目視の保持確認が一致しません: " + row.id);
    for (const check of preservation) {
      if (check.verdict !== "PASS" || !concreteObservation(check.observation))
        throw Error(
          "保持点が新画像で確認できていません: " + row.id + "/" + check.strength,
        );
      remember("preservation/" + check.strength, check.observation);
    }
    for (const key of contract.qualityDimensions) {
      validateEvidence(
        item.criteria[key],
        intent,
        contract.intentRoots[key],
        page,
        row.id + "/" + key,
      );
      remember("criteria/" + key, item.criteria[key].observation);
    }
    validateFeedbackChecks(project, item);
    const experts = [];
    for (const key of roles) {
      const evidence = item.expertReviews[key];
      if (
        evidence.verdict !== "PASS" ||
        !sameSet(evidence.criteria, contract.expertDimensions[key])
      ) {
        throw Error(
          "専門知見レンズの必須観点が未達です: " + row.id + "/" + key,
        );
      }
      const identity = normalize(evidence.reviewer);
      if (!identity || identity === designer)
        throw Error("専門知見レビューの担当者が制作担当と同じです: " + key);
      if (
        by.mode === "independent-reviewer-lenses" &&
        identity !== by.reviewer
      ) {
        throw Error(
          "同一独立レビュアーの3知見レンズとして担当者を正直に記録してください",
        );
      }
      experts.push(identity);
    }
    if (
      by.mode === "independent-agents" &&
      new Set(experts).size !== experts.length
    ) {
      throw Error(
        "3専門担当を利用したmodeでは各専門担当を別のidentityで記録してください",
      );
    }
  }
  return {
    mode: review.mode,
    reviewer: review.reviewer,
    reviewPolicyFingerprint: review.reviewPolicyFingerprint,
    reusedItems,
  };
}

module.exports = {
  contract,
  schema,
  declaredColors,
  validateIntent,
  feedbackForVariant,
  reviewPolicyFingerprint,
  reviewTemplate,
  validateReview,
  classifyFixes,
  assertMandatoryFixes,
  reviewHistory,
  archiveReview,
  requiredExperts,
};
