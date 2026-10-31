"use strict";
// 本質アンカー（規則 R2）。案件の最初に依頼文・purpose・確定事実を essence-baseline.json に 1 回だけ固定し、
// 以後の brief がそこから離れていないかを essence-check で確かめる。離れてよいのは、利用者が承認した変更を
// <project>/essence-revisions.json に {at, field, from, to, approvedBy:"user", reason} で残したときだけ。
// essence.json（本質の正本）は読むだけで書き換えない。依存は Node 標準と ajv だけ。
const fs = require("node:fs");
const path = require("node:path");
const crypto = require("node:crypto");
const Ajv = require("ajv");
const I = require("./intake.cjs");

const ROOT = path.resolve(__dirname, "..");
const ESSENCE = path.join(ROOT, "references", "essence.json");
const SCHEMA = path.join(ROOT, "schemas", "essence-baseline.schema.json");
const BASELINE = "essence-baseline.json";
const REVISIONS = "essence-revisions.json";
const PURPOSE = ["audience", "benefit", "action"];

const isObj = (v) => v !== null && typeof v === "object" && !Array.isArray(v);
const canon = (v) =>
  Array.isArray(v)
    ? v.map(canon)
    : isObj(v)
      ? Object.fromEntries(Object.keys(v).sort().map((k) => [k, canon(v[k])]))
      : v;
const same = (a, b) => JSON.stringify(canon(a ?? null)) === JSON.stringify(canon(b ?? null));
const readJSON = (p) => JSON.parse(fs.readFileSync(p, "utf8"));
const digest = (doc) => {
  const { sha256, ...rest } = doc;
  return crypto.createHash("sha256").update(JSON.stringify(canon(rest))).digest("hex");
};
let validateBaseline;
const schemaErrors = (doc) => {
  validateBaseline ??= new Ajv({ allErrors: true, strict: false }).compile(readJSON(SCHEMA));
  return validateBaseline(doc) ? null : validateBaseline.errors.map((e) => `${e.instancePath || "/"} ${e.message}`).join(", ");
};
const filled = (s) => typeof s === "string" && /\S/.test(s);

function clauses() {
  return readJSON(ESSENCE).clauses;
}

// 確定事実（must-fact）の場所。intake-questions.json の mustFact 質問のうち brief に場所を持つもの。
function factPaths(preset) {
  return I.questions(preset)
    .questions.filter((q) => q.mustFact && q.briefPath)
    .map((q) => q.briefPath);
}

// 依頼文・purpose・確定事実を固定する。intake.json があれば未解決が無いことを先に確かめ、回答から取る。
function baseline(dir, opts = {}) {
  dir = I.outsidePlugin(dir, "案件フォルダ");
  const file = path.join(dir, BASELINE);
  if (fs.existsSync(file))
    throw Error(`${BASELINE} は既にあります。基準は上書きできません。目的や事実を変えるときは利用者の承認を ${REVISIONS} に残してください（R2）`);
  const briefFile = path.join(dir, "brief.json");
  if (!fs.existsSync(briefFile)) throw Error("brief.json がありません。先に init と intake-apply を行ってください: " + dir);
  const brief = readJSON(briefFile);
  const request = filled(opts.request) ? opts.request.trim() : "";
  const intakeFile = path.join(dir, "intake.json");
  let source, originalRequest, purpose, mustFacts;
  if (fs.existsSync(intakeFile)) {
    I.assertResolved(dir);
    const rec = readJSON(intakeFile);
    if (request && filled(rec.originalRequest) && request !== rec.originalRequest)
      throw Error("--request が intake.json の最初の依頼文と違います。依頼文は最初の回答のときの文を使います");
    const value = (ptr) => (rec.answers[ptr] ? rec.answers[ptr].value : (I.getPointer(brief, ptr) ?? null));
    source = "intake";
    originalRequest = filled(rec.originalRequest) ? rec.originalRequest : request;
    purpose = Object.fromEntries(PURPOSE.map((k) => [k, value("/purpose/" + k)]));
    mustFacts = Object.fromEntries(
      factPaths(rec.preset).map((p) => [p, rec.skipped.some((s) => s.path === p) ? null : value(p)]),
    );
  } else {
    source = "brief";
    originalRequest = request;
    purpose = Object.fromEntries(PURPOSE.map((k) => [k, brief.purpose?.[k] ?? null]));
    mustFacts = Object.fromEntries(factPaths(brief.preset?.id ?? null).map((p) => [p, I.getPointer(brief, p) ?? null]));
  }
  if (!filled(originalRequest)) throw Error("最初の依頼文が必要です（--request に利用者の依頼文をそのまま渡すか、intake-apply の originalRequest に入れてください）");
  const missing = PURPOSE.filter((k) => !filled(purpose[k]));
  if (missing.length) throw Error("purpose（読者・価値・行動）が揃っていません: " + missing.join(", "));
  const doc = { version: 1, createdAt: new Date().toISOString(), originalRequest, purpose, mustFacts };
  doc.sha256 = digest(doc);
  const err = schemaErrors(doc);
  if (err) throw Error("essence-baseline の形が不正です: " + err);
  fs.writeFileSync(file, JSON.stringify(doc, null, 2) + "\n", { flag: "wx" });
  return { file, source, checked: PURPOSE.length + Object.keys(mustFacts).length, fail: 0 };
}

function revisions(dir) {
  const file = path.join(dir, REVISIONS);
  if (!fs.existsSync(file)) return { list: [], ignored: [] };
  const doc = readJSON(file);
  const raw = Array.isArray(doc) ? doc : Array.isArray(doc?.revisions) ? doc.revisions : Array.isArray(doc?.entries) ? doc.entries : null;
  if (!raw) throw Error(`${REVISIONS} は承認記録の配列か {revisions:[...]} にしてください`);
  const list = [],
    ignored = [];
  raw.forEach((r, i) => {
    const ok = isObj(r) && typeof r.field === "string" && "from" in r && "to" in r && r.approvedBy === "user" && filled(r.reason) && filled(r.at) && !Number.isNaN(Date.parse(r.at));
    (ok ? list : ignored).push(ok ? r : { index: i, reason: "field・from・to・at・approvedBy:\"user\"・reason が揃っていません" });
  });
  list.sort((a, b) => Date.parse(a.at) - Date.parse(b.at));
  return { list, ignored };
}

// 現在の brief と基準を比べ、承認記録でたどれない差分を fail にする。
function check(dir) {
  dir = I.outsidePlugin(dir, "案件フォルダ");
  const file = path.join(dir, BASELINE);
  if (!fs.existsSync(file)) throw Error(`${BASELINE} がありません。ヒアリングの後に essence-baseline を実行してください`);
  const base = readJSON(file);
  const drift = [];
  const err = schemaErrors(base);
  if (err) drift.push({ field: BASELINE, from: null, to: null, reason: "基準の形が不正です: " + err });
  if (base.sha256 !== digest(base)) drift.push({ field: BASELINE, from: base.sha256 ?? null, to: digest(base), reason: "基準が作成後に書き換えられています" });
  const briefFile = path.join(dir, "brief.json");
  if (!fs.existsSync(briefFile)) throw Error("brief.json がありません: " + dir);
  const brief = readJSON(briefFile);
  const { list, ignored } = revisions(dir);
  const fields = [
    ...PURPOSE.map((k) => ["/purpose/" + k, base.purpose?.[k] ?? null]),
    ...Object.entries(isObj(base.mustFacts) ? base.mustFacts : {}),
  ];
  const approved = [];
  for (const [field, from] of fields) {
    const now = I.getPointer(brief, field) ?? null;
    if (same(from, now)) continue;
    let v = from;
    for (const r of list) if (r.field === field && same(r.from, v)) v = r.to;
    if (same(v, now)) approved.push(field);
    else drift.push({ field, from, to: now, reason: "利用者の承認記録（essence-revisions.json）がない変更です" });
  }
  return { fail: drift.length, drift, approved, ignored, checked: fields.length };
}

// 描画と納品で同じ関門を使う。既存の回答があれば未解決を先に止め、
// 新旧いずれの案件でも明示作成された基準と現在値の一致を必須にする。
function assertCurrent(dir) {
  dir = I.outsidePlugin(dir, "案件フォルダ");
  const intakeGate = fs.existsSync(path.join(dir, "intake.json")) ? I.assertResolved(dir) : null;
  if (!fs.existsSync(path.join(dir, BASELINE)))
    throw Error(`${BASELINE} がありません。依頼文と確定した brief を確認し、essence-baseline --request で基準を明示作成してください。自動では作成しません`);
  const result = check(dir);
  if (result.fail)
    throw Error("本質アンカー（essence-baseline.json）から利用者の承認が無い変更があります。essence-check で確かめてください: " + result.drift.map((d) => d.field).join(", "));
  return { intakeGate, essenceGate: { checked: result.checked, approved: result.approved } };
}

// 利用者が承認した変更を 1 件記録する（R2）。brief を先に直してから呼ぶ。from は承認の連鎖でたどった直前の値、to は今の brief の値。
// 承認したかどうかは記録できないので、利用者が会話で明示的に承認したときだけ呼ぶ。
function revise(dir, opts = {}) {
  dir = I.outsidePlugin(dir, "案件フォルダ");
  if (!filled(opts.reason)) throw Error("--reason に利用者が承認した理由を書いてください");
  const base = readJSON(path.join(dir, BASELINE));
  const tracked = [...PURPOSE.map((k) => "/purpose/" + k), ...Object.keys(isObj(base.mustFacts) ? base.mustFacts : {})];
  if (!tracked.includes(opts.field)) throw Error("基準にない項目です（purpose と確定事実だけ）: " + opts.field + "。候補: " + tracked.join(", "));
  const { list } = revisions(dir);
  let from = opts.field.startsWith("/purpose/") ? (base.purpose?.[opts.field.slice(9)] ?? null) : base.mustFacts[opts.field];
  for (const r of list) if (r.field === opts.field && same(r.from, from)) from = r.to;
  const to = I.getPointer(readJSON(path.join(dir, "brief.json")), opts.field) ?? null;
  if (same(from, to)) throw Error("brief の値が承認済みの値と同じです。先に brief.json を直してください: " + opts.field);
  const entry = { at: new Date().toISOString(), field: opts.field, from, to, approvedBy: "user", reason: opts.reason.trim() };
  const file = path.join(dir, REVISIONS);
  const doc = fs.existsSync(file) ? readJSON(file) : { revisions: [] };
  (Array.isArray(doc) ? doc : doc.revisions).push(entry);
  fs.writeFileSync(file, JSON.stringify(doc, null, 2) + "\n");
  return { file, entry, fail: 0 };
}

module.exports = { baseline, check, revise, clauses, assertCurrent };
