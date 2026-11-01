"use strict";
// 知見台帳（案件をまたいで学ぶための記録）。
// - record: finalize 済みの案件から、field path・source・分類名・回数・様式ラベルだけを 1 行にして追記する。
// - report: 台帳を集計し、件数が足りた傾向だけを提案にする。
// - suggest: 次回の intake-template に載せる「前回までの傾向（参考・要確認）」を返す。
// 書き込むのは ${FLYER_STUDIO_HOME:-~/.flyer-studio}/ledger/cases.jsonl だけ。
// intake-questions.json・preset・essence.json は読むだけで、自動では書き換えない（E3・nonGoals）。
const fs = require("node:fs"),
  os = require("node:os"),
  path = require("node:path"),
  crypto = require("node:crypto"),
  Ajv = require("ajv");

const ROOT = path.resolve(__dirname, "..");
const SCHEMA_FILE = path.join(ROOT, "schemas", "learn-record.schema.json");
const QUESTIONS_FILE = path.join(ROOT, "references", "intake-questions.json");
const ESSENCE_FILE = path.join(ROOT, "references", "essence.json");
const MAX_TEXT = 40;
const FIX_CLASSES = ["deterministic", "within-plan", "premise", "preference"];
const INTAKE_SOURCES = new Set([
  "answer",
  "document",
  "preset-reconfirmed",
  "placeholder",
  "proposal",
  "suggestion",
  "skipped",
]);
const PATH_RE = /^\/?[A-Za-z0-9_-]+(?:[./][A-Za-z0-9_-]+)*$/;
const SLUG_RE = /^[a-z][a-z0-9-]*$/;
const PRESET_RE = /^[a-z0-9][a-z0-9-]*$/;
const IMAGE_EXT_RE = /\.(?:png|jpe?g|gif|webp|svg|heic|tiff?|pdf|psd|ai)$/i;
// 形式が決まっていて、自由な値が入らないキー（16 桁 hex と ISO 時刻）。
const FORMAT_KEYS = new Set(["recordedAt", "caseKey", "finalizeSha"]);
const STYLE_KEY = "stylePreferences";

const isObj = (v) => v !== null && typeof v === "object" && !Array.isArray(v);
const arr = (v) => (Array.isArray(v) ? v : []);
const chars = (s) => [...s].length;
const sha256 = (data) => crypto.createHash("sha256").update(data).digest("hex");
const rate = (n, d) => (d ? Math.round((n / d) * 1000) / 1000 : 0);
const pct = (r) => Math.round(r * 100) + "%";

// 個人情報らしい文字列（メール・URL・電話番号や郵便番号のような数字列）。
function looksPersonal(s) {
  return (
    /[^\s@]+@[^\s@]+/.test(s) ||
    /[a-z][a-z0-9+.-]*:\/\//i.test(s) ||
    /\bwww\./i.test(s) ||
    /\.(?:com|net|org|jp|io|co)\b/i.test(s) ||
    /〒/.test(s) ||
    (s.match(/\d/g) || []).length >= 7
  );
}

// 読めない・壊れている入力は「無い」と同じに扱い、呼び出し側が missingInputs へ入れる。
function readOptional(file) {
  try {
    return JSON.parse(fs.readFileSync(file, "utf8"));
  } catch {
    return undefined;
  }
}

function ledgerPath(opts = {}) {
  let home =
    opts.home ||
    process.env.FLYER_STUDIO_HOME ||
    path.join(os.homedir(), ".flyer-studio");
  if (home === "~" || home.startsWith("~/"))
    home = path.join(os.homedir(), home.slice(1));
  const file = path.join(path.resolve(home), "ledger", "cases.jsonl");
  let existing = path.dirname(file);
  while (!fs.existsSync(existing)) existing = path.dirname(existing);
  const real = path.join(
    fs.realpathSync(existing),
    path.relative(existing, file),
  );
  const rootReal = fs.realpathSync(ROOT);
  if (real === rootReal || real.startsWith(rootReal + path.sep))
    throw Error(
      "知見台帳は plugin の中に置きません。FLYER_STUDIO_HOME を plugin の外にしてください",
    );
  return file;
}

let compiled;
function schemaValidator() {
  if (!compiled) {
    const ajv = new Ajv({ allErrors: true, strict: false });
    compiled = ajv.compile(JSON.parse(fs.readFileSync(SCHEMA_FILE, "utf8")));
  }
  return compiled;
}

// 保存直前の fail-closed 検査。許可リスト外のキー・長い文字列・個人情報らしい値があれば止める。
// エラー文には値そのものを載せない（ログ経由で個人情報が漏れないようにする）。
function assertRecord(rec) {
  const validate = schemaValidator();
  if (!validate(rec))
    throw Error(
      "知見レコードが許可リストに合わないため保存を中止しました: " +
        validate.errors
          .map(
            (e) =>
              (e.instancePath || "/") +
              " " +
              e.message +
              (e.params?.additionalProperty
                ? " (" + e.params.additionalProperty + ")"
                : ""),
          )
          .join("; "),
    );
  const visit = (value, where, top) => {
    if (typeof value === "string") {
      if (FORMAT_KEYS.has(top)) return;
      if (chars(value) > MAX_TEXT)
        throw Error(`知見レコードに ${MAX_TEXT} 字を超える文字列があります: ${where}`);
      if (looksPersonal(value))
        throw Error("知見レコードに個人情報らしい値があるため保存を中止しました: " + where);
    } else if (Array.isArray(value)) {
      value.forEach((v, i) => visit(v, where + "/" + i, top));
    } else if (isObj(value)) {
      for (const [k, v] of Object.entries(value)) {
        const t = top ?? k;
        if (!FORMAT_KEYS.has(t) && (chars(k) > MAX_TEXT || looksPersonal(k)))
          throw Error("知見レコードに保存できないキーがあります: " + where);
        visit(v, where + "/" + k, t);
      }
    }
  };
  visit(rec, "", undefined);
  return rec;
}

const safePath = (p) =>
  typeof p === "string" && chars(p) <= MAX_TEXT && PATH_RE.test(p) && !looksPersonal(p)
    ? p
    : null;

function summarizeIntake(intake) {
  let dropped = 0;
  const keep = (p) => {
    const s = safePath(p);
    if (!s) dropped++;
    return s;
  };
  const asked = new Set(),
    late = new Set(),
    sources = {};
  let maxRound = 1;
  for (const [p, answer] of Object.entries(isObj(intake.answers) ? intake.answers : {})) {
    const key = keep(p);
    if (!key) continue;
    asked.add(key);
    const source = INTAKE_SOURCES.has(answer?.source) ? answer.source : "other";
    sources[key] = source;
    if (Number.isInteger(answer?.round)) maxRound = Math.max(maxRound, answer.round);
    // 2 回目以降に埋まった項目と、仮置きのままの項目を「1 回目で未確定」とみなす。
    if ((Number.isInteger(answer?.round) && answer.round > 1) || source === "placeholder")
      late.add(key);
  }
  for (const p of arr(intake.unresolved)) {
    const key = keep(p);
    if (!key) continue;
    asked.add(key);
    late.add(key);
    sources[key] = "unresolved";
  }
  for (const s of arr(intake.skipped)) {
    const key = keep(s?.path);
    if (!key) continue;
    asked.add(key);
    sources[key] ??= "skipped";
  }
  const rounds = Number.isInteger(intake.rounds) ? intake.rounds : maxRound;
  return {
    rounds: Math.min(20, Math.max(1, rounds, maxRound)),
    askedPaths: [...asked].sort(),
    unresolvedAfterRound1: [...late].sort(),
    sourcesByPath: Object.fromEntries(Object.entries(sources).sort()),
    droppedPaths: dropped,
  };
}

function fixCounts(value) {
  const out = Object.fromEntries(FIX_CLASSES.map((c) => [c, 0]));
  if (Array.isArray(value)) {
    for (const v of value) {
      const c = typeof v === "string" ? v : v?.fixClass;
      if (c in out) out[c]++;
    }
  } else if (isObj(value)) {
    for (const c of FIX_CLASSES) {
      if (Number.isInteger(value[c]) && value[c] > 0) out[c] += value[c];
      else if (value[c] === true) out[c]++;
    }
  }
  return out;
}

function summarizeCycles(ledger, premiseServes) {
  const byFixClass = Object.fromEntries(FIX_CLASSES.map((c) => [c, 0]));
  let used = 0,
    premiseReturns = 0;
  // 同じ所見・同じ画像の再提出は 1 回だけ数える（台帳は記録として残すが、傾向の集計では二重に数えない）。
  const seen = new Set();
  for (const entry of arr(ledger.entries)) {
    if (!isObj(entry)) continue;
    if (entry.consumed === true) used++;
    // Proposal rejections spend cycles, but are not evidence of an intake premise failure.
    if (entry.trigger === "analysis-review") continue;
    const key = String(entry.trigger) + "|" + String(entry.findingsDigest) + "|" + String(entry.renderDigest);
    if (seen.has(key)) continue;
    seen.add(key);
    const counts = fixCounts(entry.fixClasses);
    for (const c of FIX_CLASSES) byFixClass[c] += counts[c];
    if (counts.premise > 0) premiseReturns++;
  }
  const budget =
    Number.isInteger(ledger.budget) && ledger.budget >= 0 && ledger.budget <= 100
      ? ledger.budget
      : null;
  return { used, budget, byFixClass, premiseReturns, premiseServes };
}

// 両評価stageの現行記録と、退避された reviews/ 配下の評価だけを読む。
const REVIEW_NAMES = ["visual-review.json", "pilot-review.json", "analysis-review.json"];
function reviewDocs(dir) {
  const files = REVIEW_NAMES.map((f) => path.join(dir, f));
  const walk = (d, depth) => {
    if (depth > 3 || files.length > 60) return;
    let entries;
    try {
      entries = fs.readdirSync(d, { withFileTypes: true });
    } catch {
      return;
    }
    for (const e of entries.sort((a, b) => a.name.localeCompare(b.name))) {
      const p = path.join(d, e.name);
      if (e.isDirectory()) walk(p, depth + 1);
      else if (e.isFile() && REVIEW_NAMES.includes(e.name)) files.push(p);
    }
  };
  walk(path.join(dir, "reviews"), 0);
  return files.map(readOptional).filter(isObj);
}

function preferenceCategory(note) {
  const c = isObj(note) ? note.category : undefined;
  if (c === undefined || c === null || c === "") return "uncategorized";
  return typeof c === "string" && chars(c) <= 24 && SLUG_RE.test(c) ? c : "other";
}

function summarizeReviews(docs) {
  const preferences = [],
    premiseServes = {};
  for (const doc of docs) {
    for (const item of [doc, ...arr(doc.items)]) {
      if (!isObj(item)) continue;
      for (const note of arr(item.preferenceNotes))
        preferences.push({ category: preferenceCategory(note) });
      for (const fix of arr(item.mandatoryFixes)) {
        if (!isObj(fix) || fix.fixClass !== "premise") continue;
        for (const id of arr(fix.serves))
          if (typeof id === "string" && /^E[1-9]$/.test(id))
            premiseServes[id] = (premiseServes[id] || 0) + 1;
      }
    }
  }
  return { preferences, premiseServes };
}

// 様式ラベルは短い分類名なので保存してよい。ただし切り詰めずに拒否する（fail-closed）。
function assertLabel(value) {
  if (typeof value !== "string")
    throw Error("様式ラベルは文字列だけを保存します。保存を中止しました");
  const label = value.trim();
  if (chars(label) > MAX_TEXT)
    throw Error(
      `様式ラベルが ${MAX_TEXT} 字を超えています（${chars(label)} 字）。切り詰めずに保存を中止しました。短いラベルにしてから記録してください`,
    );
  if (looksPersonal(label) || /[/\\@:\r\n\t]/.test(label) || IMAGE_EXT_RE.test(label))
    throw Error(
      "様式ラベルに連絡先・URL・ファイルパスらしい文字列があるため保存を中止しました",
    );
  return label;
}

function toLabels(value) {
  if (value === undefined || value === null) return undefined;
  const labels = (Array.isArray(value) ? value : [value]).map(assertLabel).filter(Boolean);
  return [...new Set(labels)];
}

function summarizeStyle(intake, proposalsDoc, brief, missing) {
  if (!isObj(intake) && !isObj(proposalsDoc) && !isObj(brief)) {
    missing.push("styleProposals");
    return null;
  }
  const answers = isObj(intake?.answers) ? intake.answers : {};
  const answer = answers[STYLE_KEY] ?? answers["/" + STYLE_KEY];
  const proposals = arr(proposalsDoc?.proposals).filter(isObj);
  const chosen = new Set(arr(proposalsDoc?.chosen));
  let source = null;
  // おまかせ（delegated）は intake 側では proposal と記録されるため、style-proposals.json の chosenBy を先に見る。
  if (proposalsDoc?.chosenBy === "delegated") source = "delegated";
  else if (["answer", "document"].includes(answer?.source)) source = "answer";
  else if (answer?.source === "proposal" || proposalsDoc?.chosenBy === "user") source = "proposal";
  if (!isObj(proposalsDoc) && source !== "answer") missing.push("styleProposals");
  const ranks = proposals.flatMap((p, i) => (chosen.has(p.id) ? [i + 1] : []));
  const labels =
    toLabels(answer?.value) ??
    (ranks.length ? toLabels(ranks.map((r) => proposals[r - 1].label)) : undefined) ??
    toLabels(brief?.[STYLE_KEY]) ??
    [];
  return {
    source,
    proposalsOffered: isObj(proposalsDoc)
      ? Math.min(20, proposals.length)
      : source === "answer"
        ? 0
        : null,
    chosenRank: source !== "answer" && ranks.length ? Math.min(20, ranks[0]) : null,
    labels,
  };
}

function summarizePaper(concepts, scene) {
  const variants = arr(concepts?.variants).length ? concepts.variants : arr(scene?.variants);
  if (!variants.length) return null;
  const paper = { white: 0, color: 0 };
  for (const v of variants) if (v?.paper in paper) paper[v.paper]++;
  return paper;
}

function buildRecord(dir, meta) {
  const missing = [];
  const at = (name) => readOptional(path.join(dir, name));
  const intake = at("intake.json");
  if (!isObj(intake)) missing.push("intake");
  const cycleLedger = at("cycle-ledger.json");
  if (!isObj(cycleLedger)) missing.push("cycleLedger");
  const docs = reviewDocs(dir);
  if (!docs.length) missing.push("visualReview");
  const reviews = summarizeReviews(docs);
  let essenceRevisions = null;
  const revisions = at("essence-revisions.json");
  if (revisions !== undefined)
    essenceRevisions = Math.min(
      1000,
      (Array.isArray(revisions) ? revisions : arr(revisions?.revisions ?? revisions?.entries))
        .filter(isObj).length,
    );
  else if (fs.existsSync(path.join(dir, "essence-baseline.json"))) essenceRevisions = 0;
  else missing.push("essenceBaseline");
  const style = summarizeStyle(intake, at("style-proposals.json"), at("brief.json"), missing);
  const paper = summarizePaper(at("concepts.json"), at("scene.json"));
  if (!paper) missing.push("concepts");
  const preset = isObj(intake) && typeof intake.preset === "string"
    ? chars(intake.preset) <= MAX_TEXT && PRESET_RE.test(intake.preset)
      ? intake.preset
      : "other"
    : null;
  return {
    version: 1,
    recordedAt: (meta.now ? new Date(meta.now) : new Date()).toISOString(),
    caseKey: meta.caseKey,
    finalizeSha: meta.finalizeSha,
    preset,
    intake: isObj(intake) ? summarizeIntake(intake) : null,
    cycles: isObj(cycleLedger) ? summarizeCycles(cycleLedger, reviews.premiseServes) : null,
    essenceRevisions,
    preferences: docs.length ? reviews.preferences : null,
    style,
    paper,
    missingInputs: [...new Set(missing)],
  };
}

function readLedger(file) {
  let text;
  try {
    text = fs.readFileSync(file, "utf8");
  } catch (error) {
    if (error.code === "ENOENT") return { records: [], skipped: 0 };
    throw error;
  }
  const validate = schemaValidator();
  const records = [];
  let skipped = 0;
  for (const line of text.split("\n")) {
    if (!line.trim()) continue;
    try {
      const rec = JSON.parse(line);
      if (validate(rec)) records.push(rec);
      else skipped++;
    } catch {
      skipped++;
    }
  }
  return { records, skipped };
}

function record(dir, opts = {}) {
  dir = fs.realpathSync(path.resolve(dir));
  const deliveryFile = path.join(dir, "out", "delivery.json");
  let receipt, bytes;
  try {
    bytes = fs.readFileSync(deliveryFile);
    receipt = JSON.parse(bytes.toString("utf8"));
  } catch {
    throw Error(
      "finalize 済みではありません（out/delivery.json がありません）。finalize の後に learn-record を実行してください",
    );
  }
  if (receipt?.status !== "complete" || receipt.fail !== 0)
    throw Error(
      "finalize が完了していません（out/delivery.json が complete ではありません）。未完了の案件は台帳へ記録しません",
    );
  const caseKey = sha256(dir).slice(0, 16),
    finalizeSha = sha256(bytes).slice(0, 16);
  const file = ledgerPath(opts);
  const existing = readLedger(file).records.find(
    (r) => r.caseKey === caseKey && r.finalizeSha === finalizeSha,
  );
  if (existing)
    return { appended: false, reason: "already-recorded", ledger: file, record: existing, fail: 0 };
  const rec = assertRecord(buildRecord(dir, { caseKey, finalizeSha, now: opts.now }));
  fs.mkdirSync(path.dirname(file), { recursive: true, mode: 0o700 });
  fs.appendFileSync(file, JSON.stringify(rec) + "\n", { mode: 0o600 });
  return { appended: true, ledger: file, record: rec, fail: 0 };
}

// 質問 id・group との対応は references/intake-questions.json（A34 が正本）から読むだけ。
function questionIndex() {
  const doc = readOptional(QUESTIONS_FILE);
  const byPath = {};
  const add = (q, group) => {
    if (!isObj(q)) return;
    const p = q.briefPath ?? q.path;
    if (typeof p !== "string") return;
    byPath[p] = {
      id: typeof q.id === "string" ? q.id : null,
      group: typeof (q.group ?? group) === "string" ? (q.group ?? group) : null,
      label: typeof q.label === "string" ? q.label : null,
    };
  };
  const list = Array.isArray(doc) ? doc : arr(doc?.questions);
  for (const q of list) add(q);
  for (const g of arr(doc?.groups))
    for (const q of arr(g?.questions)) add(q, g?.id ?? g?.name);
  return { available: doc !== undefined, byPath };
}

function clauseNames() {
  const doc = readOptional(ESSENCE_FILE);
  return Object.fromEntries(
    arr(doc?.clauses).filter(isObj).map((c) => [c.id, c.name]),
  );
}

const insufficient = (cases) => ({ status: "insufficient", cases });
const supported = (n, d, o) => n >= o.minCases && rate(n, d) >= o.minRate;

function sectionUnresolved(cases, q, o) {
  const base = cases.filter((r) => r.intake);
  if (base.length < o.minCases) return insufficient(base.length);
  const stats = new Map();
  const stat = (p) => {
    if (!stats.has(p)) stats.set(p, { asked: 0, unresolved: 0 });
    return stats.get(p);
  };
  for (const r of base) {
    const asked = new Set(r.intake.askedPaths);
    for (const p of r.intake.unresolvedAfterRound1) asked.add(p);
    for (const p of asked) stat(p).asked++;
    for (const p of r.intake.unresolvedAfterRound1) stat(p).unresolved++;
  }
  const byPath = [...stats]
    .filter(([, s]) => s.unresolved > 0)
    .map(([p, s]) => ({
      path: p,
      questionId: q.byPath[p]?.id ?? null,
      group: q.byPath[p]?.group ?? null,
      unresolved: s.unresolved,
      asked: s.asked,
      rate: rate(s.unresolved, s.asked),
      supported: supported(s.unresolved, s.asked, o),
    }))
    .sort((a, b) => b.rate - a.rate || b.unresolved - a.unresolved || a.path.localeCompare(b.path));
  const groups = {};
  for (const s of byPath) {
    const g = s.group ?? "(group 不明)";
    groups[g] = (groups[g] || 0) + s.unresolved;
  }
  const proposals = byPath
    .filter((s) => s.supported)
    .map((s) => ({
      id: "a:" + s.path,
      section: "a",
      kind: "intake-sheet-wording-or-order",
      applyTo: "references/intake-questions.json",
      target: { path: s.path, questionId: s.questionId, group: s.group },
      evidence: { cases: s.unresolved, of: s.asked, rate: s.rate },
      text: `質問 ${s.questionId ? s.questionId + "（" + s.path + "）" : s.path} は 1 回目のヒアリングで未確定になりやすい（${s.unresolved}/${s.asked} 件・${pct(s.rate)}）。一括シートでの聞き方（答えの例・選択肢・資料の添付を促す一文）を足すか、同じ group の中で前へ出すかを検討する。`,
    }));
  return { status: "ok", cases: base.length, byPath, byGroup: groups, proposals };
}

function sectionRounds(cases, o) {
  const base = cases.filter((r) => r.intake);
  if (base.length < o.minCases) return insufficient(base.length);
  const distribution = {};
  for (const r of base) distribution[r.intake.rounds] = (distribution[r.intake.rounds] || 0) + 1;
  const total = base.reduce((n, r) => n + r.intake.rounds, 0);
  const many = base.filter((r) => r.intake.rounds >= 3).length;
  const proposals = supported(many, base.length, o)
    ? [
        {
          id: "b:rounds",
          section: "b",
          kind: "intake-residual-batching",
          applyTo: "references/intake-questions.json",
          evidence: { cases: many, of: base.length, rate: rate(many, base.length) },
          text: `追加の聞き直しが 2 回以上になった案件が ${many}/${base.length} 件ある。不足分は 1 ラウンドにまとめる前提なので、1 回目の一括シートで漏れやすい質問（(a)）を先に見直す。`,
        },
      ]
    : [];
  return {
    status: "ok",
    cases: base.length,
    distribution,
    mean: Math.round((total / base.length) * 100) / 100,
    proposals,
  };
}

function sectionFixClasses(cases, o, names) {
  const base = cases.filter((r) => r.cycles);
  if (base.length < o.minCases) return insufficient(base.length);
  const totals = Object.fromEntries(FIX_CLASSES.map((c) => [c, 0]));
  const serves = {};
  for (const r of base) {
    for (const c of FIX_CLASSES) totals[c] += r.cycles.byFixClass[c];
    for (const [id, n] of Object.entries(r.cycles.premiseServes)) serves[id] = (serves[id] || 0) + n;
  }
  const premiseCases = base.filter((r) => r.cycles.premiseReturns > 0).length;
  const premiseRate = rate(premiseCases, base.length);
  const top = Object.entries(serves).sort((a, b) => b[1] - a[1]);
  const proposals = [];
  if (supported(premiseCases, base.length, o)) {
    const clauseText = top.length
      ? "結び付いた本質条項は " +
        top.map(([id, n]) => `${id}（${names[id] ?? "名称不明"}）${n} 件`).join("・") +
        "。"
      : "どの本質条項に結び付くかは記録されていない（visual-review の serves を残すと特定できる）。";
    proposals.push({
      id: "c:premise",
      section: "c",
      kind: "intake-premise-check",
      applyTo: "references/intake-questions.json",
      evidence: { cases: premiseCases, of: base.length, rate: premiseRate, serves: Object.fromEntries(top) },
      text: `改善の途中で前提（premise）へ戻った案件が ${premiseCases}/${base.length} 件ある。${clauseText}ヒアリングの 1 回目で、その条項に関わる前提（読者と行動・必須事実の出典・公開範囲など）を確かめる問いを一括シートへ入れるか検討する。`,
    });
  }
  return {
    status: "ok",
    cases: base.length,
    totals,
    usedMean: Math.round((base.reduce((n, r) => n + r.cycles.used, 0) / base.length) * 100) / 100,
    premiseCases,
    premiseRate,
    premiseServes: Object.fromEntries(top),
    proposals,
  };
}

function sectionPreferences(cases, o) {
  const base = cases.filter((r) => Array.isArray(r.preferences));
  if (base.length < o.minCases) return insufficient(base.length);
  const byCase = {},
    notes = {};
  for (const r of base) {
    for (const c of new Set(r.preferences.map((p) => p.category))) byCase[c] = (byCase[c] || 0) + 1;
    for (const p of r.preferences) notes[p.category] = (notes[p.category] || 0) + 1;
  }
  const byCategory = Object.entries(byCase)
    .map(([category, n]) => ({ category, cases: n, notes: notes[category], rate: rate(n, base.length) }))
    .sort((a, b) => b.cases - a.cases || a.category.localeCompare(b.category));
  const proposals = [];
  for (const s of byCategory) {
    if (!supported(s.cases, base.length, o)) continue;
    if (s.category === "uncategorized" || s.category === "other")
      proposals.push({
        id: "d:" + s.category,
        section: "d",
        kind: "review-data-quality",
        applyTo: "prompts/visual-review.md",
        evidence: { cases: s.cases, of: base.length, rate: s.rate },
        text: `分類の無い好みの所見が ${s.cases}/${base.length} 件ある。preferenceNotes に category を付けると、どの観点の好みが多いかを読めるようになる。`,
      });
    else
      proposals.push({
        id: "d:" + s.category,
        section: "d",
        kind: "intake-preference-question",
        applyTo: "references/intake-questions.json",
        evidence: { cases: s.cases, of: base.length, rate: s.rate },
        text: `「${s.category}」の好みが ${s.cases}/${base.length} 件で記録された。汎用の規則へは昇格させず（essence の nonGoals）、ヒアリングで好みとして先に確かめる問いを足すか検討する。`,
      });
  }
  return { status: "ok", cases: base.length, byCategory, proposals };
}

function sectionEssence(cases, o) {
  const base = cases.filter((r) => Number.isInteger(r.essenceRevisions));
  if (base.length < o.minCases) return insufficient(base.length);
  const revised = base.filter((r) => r.essenceRevisions > 0).length;
  const proposals = supported(revised, base.length, o)
    ? [
        {
          id: "e:essence",
          section: "e",
          kind: "intake-purpose-first",
          applyTo: "references/intake-questions.json",
          evidence: { cases: revised, of: base.length, rate: rate(revised, base.length) },
          text: `目的や確定事実が途中で変わった案件が ${revised}/${base.length} 件ある。1 回目の一括シートで、読者・届ける価値・促す行動と必須事実を確かめてから先へ進む問い方を検討する。`,
        },
      ]
    : [];
  return {
    status: "ok",
    cases: base.length,
    revisedCases: revised,
    rate: rate(revised, base.length),
    revisions: base.reduce((n, r) => n + r.essenceRevisions, 0),
    proposals,
  };
}

function sectionStyleSource(cases, o) {
  const base = cases.filter((r) => r.style?.source);
  if (base.length < o.minCases) return insufficient(base.length);
  const bySource = { answer: 0, proposal: 0, delegated: 0 };
  const ranks = {};
  for (const r of base) {
    bySource[r.style.source]++;
    if (r.style.source !== "answer" && r.style.chosenRank)
      ranks[r.style.chosenRank] = (ranks[r.style.chosenRank] || 0) + 1;
  }
  const notVerbalized = bySource.proposal + bySource.delegated;
  const ranked = Object.values(ranks).reduce((a, b) => a + b, 0);
  const lowerRank = ranked - (ranks[1] || 0);
  const proposals = [];
  if (supported(notVerbalized, base.length, o))
    proposals.push({
      id: "f:not-verbalized",
      section: "f",
      kind: "intake-style-question",
      applyTo: "references/intake-questions.json",
      evidence: { cases: notVerbalized, of: base.length, rate: rate(notVerbalized, base.length) },
      text: `様式を言葉にできず、提案から選んだかおまかせにした案件が ${notVerbalized}/${base.length} 件ある。様式の質問で、雰囲気の言葉・参考にしたい物・おまかせでも答えられることを先に示し、1 回目の回答の直後に提案を出す流れを検討する。`,
    });
  if (supported(lowerRank, ranked, o))
    proposals.push({
      id: "f:rank",
      section: "f",
      kind: "style-proposal-order",
      applyTo: "skills/run-intake-flyer/SKILL.md",
      evidence: { cases: lowerRank, of: ranked, rate: rate(lowerRank, ranked) },
      text: `提案の 1 番目以外が選ばれた案件が ${lowerRank}/${ranked} 件ある。提案の並べ方（利用者の情報への合い方の順）を見直す。`,
    });
  return {
    status: "ok",
    cases: base.length,
    bySource,
    notVerbalizedRate: rate(notVerbalized, base.length),
    chosenRank: ranks,
    proposals,
  };
}

function sectionStyleLabels(cases, o) {
  const base = cases.filter((r) => r.style?.labels?.length);
  if (base.length < o.minCases) return insufficient(base.length);
  const counts = {};
  for (const r of base) for (const l of r.style.labels) counts[l] = (counts[l] || 0) + 1;
  const byLabel = Object.entries(counts)
    .map(([label, n]) => ({ label, cases: n, rate: rate(n, base.length) }))
    .sort((a, b) => b.cases - a.cases || a.label.localeCompare(b.label));
  // 傾向は suggest の初期候補にだけ使う。様式の既定値や規則にはしない（参考値は既定の様式や規則にしない）。
  return {
    status: "ok",
    cases: base.length,
    byLabel,
    trends: byLabel.filter((s) => s.cases >= o.minCases).map((s) => s.label),
    proposals: [],
  };
}

function options(opts) {
  const n = Number(opts.minCases);
  const r = Number(opts.minRate);
  return {
    minCases: Number.isInteger(n) && n >= 1 ? n : 3,
    minRate: Number.isFinite(r) && r >= 0 && r <= 1 ? r : 0.3,
  };
}

function cases(opts) {
  const file = ledgerPath(opts);
  const { records, skipped } = readLedger(file);
  // append-only なので、同じ案件は後ろの行（最新の finalize）だけを数える。
  const latest = new Map();
  for (const r of records) latest.set(r.caseKey, r);
  let list = [...latest.values()];
  if (opts.preset !== undefined) {
    const preset = opts.preset === "none" || opts.preset === "" ? null : opts.preset;
    list = list.filter((r) => r.preset === preset);
  }
  return { file, skipped, list };
}

const SECTION_TITLES = {
  unresolvedRound1: "(a) 1 回目のヒアリングで未確定になりやすい質問",
  rounds: "(b) 追加ラウンド数の分布",
  fixClasses: "(c) 修正の分類と前提へ戻る頻度",
  preferences: "(d) 好み（preference）の傾向",
  essenceRevisions: "(e) 目的・確定事実が途中で変わる頻度",
  styleSource: "(f) 様式を言葉にできなかった割合",
  styleLabels: "(g) 採択された様式ラベルの傾向",
};

// 上位 2 件と「その他」にまとめて見せる（少数の偏りを一般化しないため）。
function topAndRest(rows) {
  const out = rows.slice(0, 2).map(([name, n, extra]) => `- ${name}: ${n} 件${extra}`);
  const rest = rows.slice(2);
  if (rest.length)
    out.push(`- その他（${rest.length} 種類）: ${rest.reduce((a, [, n]) => a + n, 0)} 件`);
  return out;
}

function sectionLines(key, s) {
  if (s.status === "insufficient")
    return [`件数不足（${s.cases} 件）。傾向は提案にしない。`];
  switch (key) {
    case "unresolvedRound1":
      return s.byPath.length
        ? s.byPath.slice(0, 10).map(
            (p) =>
              `- ${p.questionId ? p.questionId + " " : ""}\`${p.path}\` ${p.unresolved}/${p.asked} 件（${pct(p.rate)}）${p.supported ? "" : " ※件数不足のため提案しない"}`,
          )
        : ["1 回目で未確定になった質問はない。"];
    case "rounds":
      return [
        "- " +
          Object.entries(s.distribution)
            .map(([k, n]) => `${k} 回: ${n} 件`)
            .join(" / ") +
          `（平均 ${s.mean} 回）`,
      ];
    case "fixClasses":
      return [
        "- " + FIX_CLASSES.map((c) => `${c}: ${s.totals[c]}`).join(" / "),
        `- 前提へ戻った案件: ${s.premiseCases}/${s.cases} 件（${pct(s.premiseRate)}）・消費 cycle の平均 ${s.usedMean}`,
      ];
    case "preferences":
      return s.byCategory.length
        ? topAndRest(s.byCategory.map((c) => [c.category, c.cases, `（所見 ${c.notes}）`]))
        : ["好みの所見はない。"];
    case "essenceRevisions":
      return [`- 変更があった案件: ${s.revisedCases}/${s.cases} 件（${pct(s.rate)}）・変更の合計 ${s.revisions} 回`];
    case "styleSource":
      return [
        `- 様式名を指定: ${s.bySource.answer} 件 / 提案から選択: ${s.bySource.proposal} 件 / おまかせ: ${s.bySource.delegated} 件（言葉にできなかった割合 ${pct(s.notVerbalizedRate)}）`,
      ];
    case "styleLabels":
      return [
        ...topAndRest(s.byLabel.map((l) => [l.label, l.cases, ""])),
        s.trends.length
          ? `- 次回の提案の初期候補（learn-suggest が「参考・要確認」として返す）: ${s.trends.join("・")}`
          : "- 初期候補にできるほど件数のある様式はまだない。",
      ];
    default:
      return [];
  }
}

function toMarkdown(json) {
  const lines = [
    "# 知見台帳レポート",
    "",
    `- 対象: ${json.cases} 件（同じ案件は最新の記録だけ数える）・読めなかった行: ${json.skippedLines}`,
    `- 提案にするのは ${json.minCases} 件以上かつ ${pct(json.minRate)} 以上の傾向だけ。`,
    "- intake-questions.json と preset は自動で書き換えない。採用する提案だけ、人が読んで手で反映する。",
  ];
  for (const [key, s] of Object.entries(json.sections)) {
    lines.push("", "## " + SECTION_TITLES[key], "", ...sectionLines(key, s));
    for (const p of s.proposals || [])
      lines.push(
        `- **提案** ${p.text}（根拠 ${p.evidence.cases}/${p.evidence.of} 件・反例 ${p.evidence.counter} 件・反映先の候補: \`${p.applyTo}\`）`,
      );
  }
  if (!json.proposals.length) lines.push("", "提案はありません。");
  return lines.join("\n") + "\n";
}

function report(opts = {}) {
  const o = options(opts);
  const { file, skipped, list } = cases(opts);
  const q = questionIndex();
  const sections = {
    unresolvedRound1: sectionUnresolved(list, q, o),
    rounds: sectionRounds(list, o),
    fixClasses: sectionFixClasses(list, o, clauseNames()),
    preferences: sectionPreferences(list, o),
    essenceRevisions: sectionEssence(list, o),
    styleSource: sectionStyleSource(list, o),
    styleLabels: sectionStyleLabels(list, o),
  };
  const json = {
    version: 1,
    generatedAt: new Date().toISOString(),
    ledger: file,
    minCases: o.minCases,
    minRate: o.minRate,
    preset: opts.preset ?? null,
    cases: list.length,
    skippedLines: skipped,
    questionsAvailable: q.available,
    sections,
    proposals: Object.values(sections).flatMap((s) => s.proposals || []),
    autoApply: false,
  };
  // 反例（傾向に当てはまらなかった案件の数）を必ず添え、採否を人が判断できるようにする。
  for (const p of json.proposals) p.evidence.counter = p.evidence.of - p.evidence.cases;
  return { json, markdown: toMarkdown(json), fail: 0 };
}

// intake-template へ渡す参考値。値（事実）は返さず、傾向の説明とラベルだけを返す。
function suggest(opts = {}) {
  const r = report(opts).json;
  const q = questionIndex();
  const suggestions = {};
  // path は brief の field path（どの質問への参考か）で、回答の値ではない。
  const entry = (text, extra = {}) => ({ text, ...extra, source: "suggestion", reconfirm: true });
  const a = r.sections.unresolvedRound1;
  if (a.status === "ok")
    for (const s of a.byPath.filter((x) => x.supported))
      suggestions[s.questionId ?? s.path] = entry(
        `前回までの傾向（参考・要確認）: 1 回目で未確定になりやすい項目です（${s.unresolved}/${s.asked} 件）。資料や確定済みの情報があれば最初に添えてください。`,
        { path: s.path },
      );
  const styleKey = q.byPath[STYLE_KEY]?.id ?? q.byPath["/" + STYLE_KEY]?.id ?? STYLE_KEY;
  const labels = r.sections.styleLabels.status === "ok" ? r.sections.styleLabels.trends.slice(0, 3) : [];
  const unspoken = arr(r.sections.styleSource.proposals).some((p) => p.id === "f:not-verbalized");
  if (labels.length || unspoken)
    suggestions[styleKey] = entry(
      [
        labels.length
          ? `前回までに選ばれた様式（参考・要確認）: ${labels.join("・")}。今回も同じとは限らないので確かめてください。`
          : "",
        unspoken ? "様式名が浮かばなければ、雰囲気の言葉・参考にしたい物・おまかせでも答えられます。" : "",
      ].join(""),
      { path: STYLE_KEY, labels },
    );
  return {
    version: 1,
    source: "suggestion",
    reconfirm: true,
    minCases: r.minCases,
    cases: r.cases,
    insufficient: r.cases < r.minCases,
    note: "確定値ではありません。intake-template では「前回までの傾向」として表示し、利用者が確かめた内容だけを回答として保存してください。",
    suggestions,
    fail: 0,
  };
}

module.exports = { record, report, suggest, assertRecord, ledgerPath, looksPersonal };
