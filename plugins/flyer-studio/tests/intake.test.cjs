"use strict";
// ヒアリング（scripts/intake.cjs）の検査。案件フォルダは必ず一時フォルダに作り、plugin の中へは書かない。
const test = require("node:test");
const assert = require("node:assert/strict");
const fs = require("node:fs");
const os = require("node:os");
const path = require("node:path");

const I = require("../scripts/intake.cjs");
const P = require("../scripts/project.cjs");
const ROOT = path.resolve(__dirname, "..");
const QUESTIONS = require("../references/intake-questions.json").questions;

const BASE = fs.mkdtempSync(path.join(os.tmpdir(), "flyer-intake-"));
process.on("exit", () => fs.rmSync(BASE, { recursive: true, force: true }));
let seq = 0;
function fresh(preset) {
  const dir = path.join(BASE, "case-" + ++seq);
  P.init(dir, preset);
  return dir;
}
const read = (dir, f) => JSON.parse(fs.readFileSync(path.join(dir, f), "utf8"));

const REQUEST = "子育て中の方が気軽に話せる交流会のチラシを作りたい";
// 一括回答の例。値は架空で、案件固有の実在の値は使わない。
function full(overrides = {}) {
  return {
    originalRequest: REQUEST,
    answers: {
      mode: "new",
      audience: "子育て中で、平日の夜に参加できる地域の方",
      benefit: "同じ悩みを持つ人と気軽に話し、次の一歩が見つかる",
      action: "申込フォームから申し込む",
      title: "子育てトーク交流会",
      content: "少人数で子育ての悩みを話す交流会",
      speakers: "なし",
      date: "2027年3月14日（日）",
      time: "13:30〜15:00（受付 13:00）",
      venue: "市民交流センター 2階 会議室",
      address: "架空市中央1-2-3",
      price: "参加費 500円（資料代込み・税込）",
      "apply-url": "https://forms.kosodate-talk.jp/apply",
      "apply-method": "QR コードから申し込む",
      notice: "なし",
      "photo-source": ["none"],
      logo: "none",
      distribution: ["handout"],
      style: ["水彩"],
      "real-person-style": "no-real-people",
      "page-size": "A4 縦",
      ...overrides,
    },
  };
}
// 確定事実の確認まで済ませた案件。
function resolved(overrides) {
  const dir = fresh();
  I.apply(dir, full(overrides));
  const r = I.apply(dir, { "confirm-facts": "はい" });
  assert.deepEqual(r.problems, []);
  return dir;
}
function proposals(dir, chosen) {
  const axes = { medium: "水彩", lineAndPlane: "輪郭線なし", texture: "紙のにじみ", colorTemperament: "淡い", density: "余白多め", typeCharacter: "丸みのある見出し", culturalRef: "現代の絵本", people: "描かない" };
  const doc = {
    version: 1,
    basis: { moodWords: ["やさしい"], references: [], avoid: [], purposeRefs: ["/purpose/audience"], materials: { photosAvailable: false } },
    proposals: [
      { id: "S1", label: "やわらかな水彩", axes, basisUsed: ["moodWords:やさしい"], fit: "読者が安心して読める", serves: ["E1"], risks: ["文字が沈む"], needs: [] },
      { id: "S2", label: "切り絵の温かさ", axes: { ...axes, medium: "切り絵" }, basisUsed: ["/purpose/audience"], fit: "親しみが出る", serves: ["E1"], risks: [], needs: [] },
    ],
    chosen,
    chosenBy: chosen.length ? "user" : null,
    decidedAt: chosen.length ? "2027-01-10T09:00:00Z" : null,
  };
  fs.writeFileSync(path.join(dir, "style-proposals.json"), JSON.stringify(doc));
}

test("一括シートは全ての確定事実と必須の質問を 1 枚に載せる", () => {
  const t = I.template();
  const keys = new Set(t.questions.map((q) => q.key));
  for (const q of QUESTIONS.filter((x) => x.mustFact && !x.askWhen)) assert.ok(keys.has(q.briefPath ?? "intake." + q.id), q.id);
  for (const q of QUESTIONS.filter((x) => x.required && !x.askWhen)) assert.ok(keys.has(q.briefPath ?? "intake." + q.id), q.id);
  assert.ok(!keys.has("/confirmations/facts"), "確定事実の確認は一覧を見てから聞く");
  assert.match(t.markdown, /^# チラシ制作のヒアリング/);
  assert.equal(t.answers.originalRequest, "");
});

test("資料から読み取った値は「確認のみ」になり、使えない値は理由付きで質問に残る", () => {
  const t = I.template({ prefill: { title: { value: "子育てトーク交流会", source: "document" }, date: { value: "3月14日", source: "document" } } });
  assert.match(t.markdown, /## 確認のみ[\s\S]*子育てトーク交流会 \| 今回の資料/);
  assert.ok(!t.questions.some((q) => q.key === "/title"));
  assert.deepEqual(t.answers.answers["/title"], { value: "子育てトーク交流会", source: "document" });
  assert.equal(t.prefillRejected[0].key, "/copy/date");
  assert.match(t.prefillRejected[0].reason, /年が抜けています/);
  assert.ok(t.questions.some((q) => q.key === "/copy/date"));
  assert.throws(() => I.template({ prefill: { title: { value: "x", source: "suggestion" } } }), /出典は answer か document/);
});

test("learn の参考値はそのまま受け取り、要確認として記入し、事実には記入しない", () => {
  const suggestions = {
    version: 1,
    source: "suggestion",
    reconfirm: true,
    suggestions: {
      "/stylePreferences": { text: "前回までの傾向（参考）: 水彩・切り絵", path: "/stylePreferences", labels: ["水彩", "切り絵"], source: "suggestion", reconfirm: true },
      "/copy/venue": { text: "前回の会場", path: "/copy/venue", labels: ["市民交流センター"], source: "suggestion", reconfirm: true },
      "unknown-key": { text: "x", path: "/nowhere", source: "suggestion", reconfirm: true },
    },
  };
  const t = I.template({ suggestions });
  assert.deepEqual(t.answers.answers["/stylePreferences"], { value: ["水彩", "切り絵"], source: "suggestion", reconfirm: true });
  assert.equal(t.answers.answers["/copy/venue"], null, "確定事実に前回の値を記入しない（E2）");
  assert.match(t.markdown, /前回までの傾向（参考）: 水彩・切り絵/);
  assert.deepEqual(t.suggestionsIgnored, ["unknown-key"]);
  const dir = fresh();
  const r = I.apply(dir, full({ style: { value: ["水彩", "切り絵"], source: "suggestion" } }));
  assert.ok(r.problems.some((p) => p.key === "/stylePreferences" && /参考/.test(p.reason)));
  assert.equal(read(dir, "intake.json").answers["/stylePreferences"], undefined);
});

test("回答には出典が付き、brief と intake.json に書かれる（plugin の外だけ）", () => {
  const dir = fresh();
  const r = I.apply(dir, full({ title: { value: "子育てトーク交流会", source: "document" } }));
  const rec = read(dir, "intake.json");
  assert.equal(rec.version, 1);
  assert.equal(rec.originalRequest, REQUEST);
  assert.equal(rec.rounds, 1);
  assert.equal(rec.answers["/title"].source, "document");
  assert.equal(rec.answers["/purpose/audience"].source, "answer");
  assert.equal(rec.answers["intake.logo"].value, "none");
  assert.ok(rec.skipped.some((s) => s.path === "/copy/speakers"));
  const brief = read(dir, "brief.json");
  assert.equal(brief.title, "子育てトーク交流会");
  assert.deepEqual(brief.page.width, 210);
  assert.ok(r.written.includes("/purpose/audience"));
  assert.throws(() => I.apply(path.join(ROOT, "tmp-case"), full()), /plugin/);
  assert.throws(() => I.template({ out: path.join(ROOT, "sheet.md") }), /plugin/);
  assert.throws(() => I.apply(dir, { "no-such-question": "x" }), /未知の質問キー/);
});

test("仮置きの確定事実は未解決に残り、assertResolved が止める", () => {
  const dir = fresh();
  const r = I.apply(dir, full({ price: "未定", "apply-url": "https://example.com/form" }));
  const rec = read(dir, "intake.json");
  assert.equal(rec.answers["/copy/price"].source, "placeholder");
  assert.equal(rec.answers["/qrUrl"].source, "placeholder");
  assert.ok(r.unresolved.includes("/copy/price") && r.unresolved.includes("/qrUrl"));
  assert.throws(() => I.assertResolved(dir), /ヒアリングが終わっていません[\s\S]*料金/);
});

test("residual は不足・矛盾・確認だけを返し、答えた質問を聞き直さない", () => {
  const dir = fresh();
  const a = full({ "apply-url": null, logo: "file", count: 3, "white-count": 5 });
  I.apply(dir, a);
  const r = I.residual(dir);
  const keys = r.json.items.map((i) => i.key);
  assert.ok(keys.includes("/qrUrl"));
  assert.ok(keys.includes("intake.logo-file"), "支給ロゴを選んだときだけファイルを聞く");
  assert.equal(r.json.items.find((i) => i.key === "/whiteCount").kind, "conflict");
  assert.ok(!keys.includes("/purpose/audience") && !keys.includes("/title"));
  assert.ok(!keys.includes("/confirmations/facts"), "事実が揃うまで確認を聞かない");
  assert.equal(r.done, false);
  assert.deepEqual(Object.keys(r.json.skeleton.answers).sort(), keys.sort());
  I.apply(dir, { "apply-url": "https://forms.kosodate-talk.jp/apply", "logo-file": "支給ロゴ.png", "white-count": 1 });
  const r2 = I.residual(dir);
  assert.deepEqual(r2.json.items.map((i) => i.kind), ["readback"]);
  assert.match(r2.markdown, /## 確定事実の確認/);
  I.apply(dir, { "confirm-facts": "はい" });
  const r3 = I.residual(dir);
  assert.equal(r3.count, 0);
  assert.equal(r3.done, true);
  assert.equal(read(dir, "brief.json").confirmations.facts, true);
  assert.deepEqual(I.assertResolved(dir).ok, true);
});

test("確定事実の確認は、一覧を見る前や事実を直した回には受け付けない", () => {
  const dir = fresh();
  const r = I.apply(dir, { ...full(), answers: { ...full().answers, "confirm-facts": "はい" } });
  assert.ok(r.problems.some((p) => p.key === "/confirmations/facts"));
  I.apply(dir, { "confirm-facts": "はい" });
  assert.equal(read(dir, "brief.json").confirmations.facts, true);
  const r2 = I.apply(dir, { time: "14:00〜15:30" });
  assert.ok(r2.followUps.some((f) => /確認をやり直します/.test(f)));
  assert.equal(read(dir, "brief.json").confirmations.facts, false);
});

test("様式提案: 雰囲気の言葉だけの様式は styleProposalNeeded に根拠を返す", () => {
  const dir = resolved({ style: ["おしゃれ"], "style-mood": ["やさしい"], "style-avoid": ["派手"], "real-person-style": null });
  const r = I.residual(dir);
  assert.equal(r.styleProposalNeeded.reason, "vague");
  assert.deepEqual(r.styleProposalNeeded.basis.moodWords, ["やさしい", "おしゃれ"]);
  assert.deepEqual(r.styleProposalNeeded.basis.avoid, ["派手"]);
  assert.deepEqual(r.styleProposalNeeded.basis.purposeRefs, ["/purpose/audience", "/purpose/benefit", "/purpose/action"]);
  assert.equal(r.styleProposalNeeded.basis.materials.photosAvailable, false);
  assert.ok(!r.json.items.some((i) => i.key === "intake.real-person-style"), "様式が決まるまで実在の人の質問を出さない");
  assert.equal(r.done, false);
  const none = resolved({ style: null, "real-person-style": null });
  assert.equal(I.residual(none).styleProposalNeeded.reason, "unspecified");
  assert.equal(I.residual(resolved({ style: "おまかせ", "real-person-style": null })).styleProposalNeeded.reason, "omakase");
});

test("様式提案: proposal の値が選ばれた案と一致しなければ未解決、一致すれば決まる", () => {
  const dir = resolved({ style: ["おしゃれ"], "real-person-style": null });
  proposals(dir, []);
  assert.equal(I.residual(dir).styleProposalNeeded.reason, "pending-choice");
  proposals(dir, ["S1"]);
  assert.equal(I.residual(dir).styleProposalNeeded.reason, "pending-apply");
  const bad = I.apply(dir, { style: { value: ["切り絵の温かさ"], source: "proposal" } });
  assert.ok(bad.unresolved.includes("/stylePreferences"));
  assert.match(I.residual(dir).json.items.find((i) => i.key === "/stylePreferences").reason, /一致しません/);
  assert.throws(() => I.assertResolved(dir), /見た目の様式/);
  const ok = I.apply(dir, { style: { value: ["やわらかな水彩"], source: "proposal" }, "real-person-style": "no-real-people" });
  assert.deepEqual(ok.unresolved, []);
  assert.equal(ok.styleProposalNeeded, null);
  assert.deepEqual(read(dir, "brief.json").stylePreferences, ["やわらかな水彩"]);
  assert.equal(I.residual(dir).done, true);
  const wrong = I.apply(dir, { title: { value: "子育てトーク交流会", source: "proposal" } });
  assert.ok(wrong.problems.some((p) => /proposal は様式/.test(p.reason)));
});

test("様式提案: 様式が決まっていないだけでは assertResolved は止めない", () => {
  const dir = resolved({ style: null, "real-person-style": null });
  assert.notEqual(I.residual(dir).styleProposalNeeded, null);
  assert.equal(I.assertResolved(dir).ok, true);
});

test("preset の前回の値は確かめるまで使わず、同じ値の回答は preset-reconfirmed になる", () => {
  const t = I.template({ preset: "hyogo-ai" });
  assert.match(t.markdown, /preset「hyogo-ai」/);
  assert.equal(t.answers.preset, "hyogo-ai");
  const dir = fresh("hyogo-ai");
  const brief = read(dir, "brief.json");
  I.apply(dir, full({ count: brief.count }));
  const rec = read(dir, "intake.json");
  assert.equal(rec.preset, "hyogo-ai");
  assert.equal(rec.answers["/count"].source, "preset-reconfirmed");
  assert.throws(() => I.template({ preset: "no-such-preset" }), /未知の preset/);
});

test("汎用の質問に案件固有の値を書かない（preset にだけ置く）", () => {
  const text = fs.readFileSync(path.join(ROOT, "references", "intake-questions.json"), "utf8") + fs.readFileSync(path.join(ROOT, "scripts", "intake.cjs"), "utf8");
  for (const word of ["HyogoAI", "Hyogo AI", "アスピア", "明石", "F07", "F11", "13案", "グラデーションロゴ"]) assert.ok(!text.includes(word), word);
  const logo = QUESTIONS.find((q) => q.id === "logo");
  assert.deepEqual(logo.options.map((o) => o.value), ["file", "none"]);
});


test("URL がない当日受付も、行動案内を事実として確認してから制作へ渡す", () => {
  const dir = fresh();
  I.apply(dir, full({ "apply-url": "なし", "apply-method": "予約不要。当日、会場の受付へお越しください" }));
  assert.equal(I.residual(dir).json.items.some((x) => x.key === "/qrUrl"), false);
  I.apply(dir, { "confirm-facts": "はい" });
  assert.equal(I.assertResolved(dir).ok, true);
  const brief = read(dir, "brief.json");
  assert.ok(!brief.qrUrl);
  assert.deepEqual(brief.copy.apply, ["予約不要。当日、会場の受付へお越しください"]);
  const rec = read(dir, "intake.json");
  assert.equal(rec.answers["/copy/apply"].source, "answer");
  I.apply(dir, { "apply-method": "電話でお申し込みください" });
  assert.equal(read(dir, "brief.json").confirmations.facts, false);
  assert.throws(() => I.assertResolved(dir), /ヒアリングが終わっていません/);
});

test("URL なしでも行動案内の欠落・仮置きは確認済みにしない", () => {
  for (const value of [null, "未定"]) {
    const dir = fresh();
    I.apply(dir, full({ "apply-url": "なし", "apply-method": value }));
    assert.ok(I.residual(dir).json.items.some((x) => x.key === "/copy/apply"));
    I.apply(dir, { "confirm-facts": "はい" });
    assert.throws(() => I.assertResolved(dir), /ヒアリングが終わっていません/);
  }
});

test("資料に明示された様式はtemplateの雛形からdocument出典のままapplyへ往復できる", () => {
  const dir = fresh(), sheet = I.template({ prefill: { style: { value: ["水墨"], source: "document" } } });
  assert.equal(sheet.questions.some(q => q.key === "/stylePreferences"), false);
  assert.deepEqual(sheet.answers.answers["/stylePreferences"], { value: ["水墨"], source: "document" });
  const answers = full();
  delete answers.answers.style;
  const result = I.apply(dir, { ...sheet.answers, originalRequest: REQUEST, answers: { ...sheet.answers.answers, ...answers.answers } });
  assert.deepEqual(result.problems, []);
  assert.equal(result.styleProposalNeeded, null);
  assert.deepEqual(read(dir, "brief.json").stylePreferences, ["水墨"]);
  assert.equal(read(dir, "intake.json").answers["/stylePreferences"].source, "document");
  I.apply(dir, { "confirm-facts": true });
  assert.equal(I.residual(dir).done, true);
});
