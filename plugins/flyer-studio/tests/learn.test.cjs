"use strict";
// 知見台帳（scripts/learn.cjs）の検査。台帳は必ず一時フォルダへ書き、利用者の ~/.flyer-studio には触れない。
const test = require("node:test");
const assert = require("node:assert/strict");
const fs = require("node:fs");
const os = require("node:os");
const path = require("node:path");

const BASE = fs.mkdtempSync(path.join(os.tmpdir(), "flyer-learn-"));
process.env.FLYER_STUDIO_HOME = path.join(BASE, "home-default");
process.on("exit", () => fs.rmSync(BASE, { recursive: true, force: true }));

const L = require("../scripts/learn.cjs");
const ROOT = path.resolve(__dirname, "..");

// 台帳に入ってはいけない事実値・個人情報・自由記述。
const FORBIDDEN = [
  "山田太郎",
  "090-1234-5678",
  "090-1111-2222",
  "https://example.com",
  "example.com",
  "taro@example.com",
  "市民会館",
  "2026年3月15日",
  "依頼メモ",
  "もっと赤く",
  "やさしい春の雰囲気",
  "sample-photo.png",
  "水彩の柔らかい表現",
];

let seq = 0;
function freshHome() {
  const home = path.join(BASE, "home-" + ++seq);
  process.env.FLYER_STUDIO_HOME = home;
  return home;
}
const ledgerFile = (home) => path.join(home, "ledger", "cases.jsonl");
const lines = (home) =>
  fs.existsSync(ledgerFile(home))
    ? fs.readFileSync(ledgerFile(home), "utf8").split("\n").filter(Boolean)
    : [];
const write = (file, value) => {
  fs.mkdirSync(path.dirname(file), { recursive: true });
  fs.writeFileSync(file, JSON.stringify(value, null, 2) + "\n");
};

const PROPOSALS = [
  { id: "S1", label: "水彩", basisUsed: ["moodWords"], fit: "やさしい春の雰囲気に合う" },
  { id: "S2", label: "切り絵", basisUsed: ["references"], fit: "参考の形を生かす" },
  { id: "S3", label: "レトロ印刷", basisUsed: ["avoid"], fit: "にぎやかさを抑える" },
];

// finalize 済みの最小案件を作る。omit に挙げたファイルは作らない。
function makeCase(o = {}) {
  const dir = fs.mkdtempSync(path.join(BASE, "case-"));
  const omit = new Set(o.omit || []);
  if (!omit.has("delivery"))
    write(path.join(dir, "out", "delivery.json"), {
      status: "complete",
      fail: 0,
      fingerprint: o.fingerprint || "a".repeat(64),
      ...(o.delivery || {}),
    });
  const style = o.style ?? "answer";
  const styleAnswer =
    style === "answer"
      ? { value: o.styleLabel ?? ["切り絵"], source: "answer", round: 1 }
      : { value: o.styleLabel ?? (style === "delegated" ? "水彩" : "切り絵"), source: "proposal", round: 1 };
  if (!omit.has("intake"))
    write(path.join(dir, "intake.json"), {
      version: 1,
      originalRequest: "依頼メモ: 山田太郎 090-1234-5678 https://example.com/event",
      preset: o.preset ?? "hyogo-ai",
      rounds: o.rounds ?? 2,
      answers: {
        "event.date": { value: "2026年3月15日", source: "answer", round: 1 },
        "venue.name": { value: "市民会館 大ホール", source: "document", round: 1 },
        "contact.phone": { value: "090-1234-5678", source: "answer", round: 2 },
        "organizer.name": { value: "山田太郎", source: "answer", round: 1 },
        "contact.url": { value: "https://example.com/event", source: "placeholder", round: 1 },
        "taro@example.com": { value: "x", source: "answer", round: 1 },
        stylePreferences: styleAnswer,
      },
      unresolved: o.unresolved ?? ["audience.age"],
      skipped: [{ path: "sponsor.logo", reason: "後日 山田太郎さんから" }],
    });
  if (!omit.has("cycleLedger"))
    write(path.join(dir, "cycle-ledger.json"), {
      version: 1,
      budget: 3,
      entries: [
        {
          cycle: 1,
          at: "2026-10-23T00:00:00Z",
          trigger: "visual-review",
          findingsDigest: "f".repeat(16),
          renderDigest: "e".repeat(16),
          fixClasses: o.premise === false ? { deterministic: 2 } : { deterministic: 1, premise: 1 },
          consumed: true,
          reason: "山田太郎の名前を大きくする",
        },
      ],
    });
  if (!omit.has("visualReview"))
    write(path.join(dir, "visual-review.json"), {
      items: [
        {
          mandatoryFixes: [
            { text: "山田太郎の名前を大きく", fixClass: "premise", serves: ["E1"], returnTo: "run-analyze-flyer" },
          ],
          preferenceNotes: [{ text: "もっと赤く 090-1111-2222" }, { text: "余白", category: "spacing" }],
        },
      ],
    });
  if (!omit.has("essenceBaseline")) write(path.join(dir, "essence-baseline.json"), { purpose: "x" });
  if (!omit.has("concepts"))
    write(path.join(dir, "concepts.json"), {
      variants: [{ paper: "white", expression: "水彩の柔らかい表現 https://example.com" }, { paper: "color" }],
    });
  if (style !== "answer" && !omit.has("styleProposals"))
    write(path.join(dir, "style-proposals.json"), {
      version: 1,
      basis: {
        moodWords: ["やさしい春の雰囲気で子どもが喜ぶ感じ"],
        references: ["refs/sample-photo.png"],
        avoid: [],
        purposeRefs: ["E1"],
        materials: { photosAvailable: false },
      },
      proposals: PROPOSALS,
      chosen: [style === "delegated" ? "S1" : o.chosen || "S2"],
      chosenBy: style === "delegated" ? "delegated" : "user",
      decidedAt: "2026-10-23T00:00:00Z",
    });
  return dir;
}

test("finalize 済みの案件を記録すると、一時 HOME の台帳へ 1 行追加される", () => {
  const home = freshHome();
  const result = L.record(makeCase());
  assert.equal(result.appended, true);
  assert.equal(result.ledger, ledgerFile(home));
  assert.equal(lines(home).length, 1);
  assert.equal(fs.statSync(ledgerFile(home)).mode & 0o777, 0o600);
  const rec = JSON.parse(lines(home)[0]);
  assert.equal(rec.version, 1);
  assert.match(rec.caseKey, /^[a-f0-9]{16}$/);
  assert.equal(rec.preset, "hyogo-ai");
  assert.equal(rec.intake.rounds, 2);
  assert.deepEqual(rec.intake.unresolvedAfterRound1, ["audience.age", "contact.phone", "contact.url"]);
  assert.equal(rec.intake.sourcesByPath["sponsor.logo"], "skipped");
  assert.deepEqual(rec.cycles.byFixClass, { deterministic: 1, "within-plan": 0, premise: 1, preference: 0 });
  assert.equal(rec.cycles.premiseReturns, 1);
  assert.deepEqual(rec.cycles.premiseServes, { E1: 1 });
  assert.equal(rec.essenceRevisions, 0);
  assert.deepEqual(rec.preferences, [{ category: "uncategorized" }, { category: "spacing" }]);
  assert.deepEqual(rec.paper, { white: 1, color: 1 });
  assert.deepEqual(rec.missingInputs, []);
});

test("同じ案件を同じ finalize のまま再記録しても行は増えない（冪等）", () => {
  const home = freshHome();
  const dir = makeCase();
  L.record(dir);
  const again = L.record(dir);
  assert.equal(again.appended, false);
  assert.equal(again.reason, "already-recorded");
  assert.equal(lines(home).length, 1);
});

test("finalize をやり直すと新しい行になるが、report は同じ案件を 1 件として数える", () => {
  const home = freshHome();
  const dir = makeCase();
  L.record(dir);
  write(path.join(dir, "out", "delivery.json"), { status: "complete", fail: 0, fingerprint: "b".repeat(64) });
  assert.equal(L.record(dir).appended, true);
  assert.equal(lines(home).length, 2);
  assert.equal(L.report().json.cases, 1);
});

test("finalize されていない案件は記録しない", () => {
  const home = freshHome();
  assert.throws(() => L.record(makeCase({ omit: ["delivery"] })), /finalize 済みではありません/);
  assert.throws(
    () => L.record(makeCase({ delivery: { status: "pending", fail: 1, reason: "x" } })),
    /finalize が完了していません/,
  );
  assert.equal(lines(home).length, 0);
});

test("電話番号・氏名・URL・事実値・自由記述は台帳へ入らない", () => {
  const home = freshHome();
  L.record(makeCase({ style: "proposal" }));
  const raw = fs.readFileSync(ledgerFile(home), "utf8");
  for (const word of FORBIDDEN) assert.equal(raw.includes(word), false, "台帳に含まれている: " + word);
  const rec = JSON.parse(raw);
  assert.equal(rec.intake.askedPaths.includes("taro@example.com"), false);
  assert.equal(rec.intake.droppedPaths, 1);
  assert.equal("expression" in rec, false);
});

test("許可リスト外のキー・長い文字列・個人情報らしい値は保存前に止める（fail-closed）", () => {
  freshHome();
  const { record: rec } = L.record(makeCase());
  assert.doesNotThrow(() => L.assertRecord(structuredClone(rec)));
  assert.throws(() => L.assertRecord({ ...rec, phone: "x" }), /許可リスト/);
  assert.throws(
    () => L.assertRecord({ ...rec, intake: { ...rec.intake, originalRequest: "依頼" } }),
    /許可リスト/,
  );
  assert.throws(() => L.assertRecord({ ...rec, preset: "a".repeat(41) }), /許可リスト/);
  assert.throws(
    () => L.assertRecord({ ...rec, style: { ...rec.style, labels: ["切り絵 090-1234-5678"] } }),
    /個人情報/,
  );
  assert.throws(
    () =>
      L.assertRecord({
        ...rec,
        intake: { ...rec.intake, sourcesByPath: { ...rec.intake.sourcesByPath, "example.com": "answer" } },
      }),
    /保存できないキー/,
  );
});

test("入力ファイルが欠けていても記録でき、欠けたものは missingInputs に残る", () => {
  const home = freshHome();
  const all = ["intake", "cycleLedger", "visualReview", "essenceBaseline", "concepts", "styleProposals"];
  const result = L.record(makeCase({ omit: all, style: "proposal" }));
  assert.equal(result.appended, true);
  const rec = result.record;
  assert.deepEqual([...rec.missingInputs].sort(), [...all].sort());
  for (const key of ["preset", "intake", "cycles", "essenceRevisions", "preferences", "style", "paper"])
    assert.equal(rec[key], null, key);
  assert.equal(lines(home).length, 1);
});

test("台帳を plugin の中に置く設定は拒否し、何も作らない", () => {
  const inside = path.join(ROOT, "tmp-learn-ledger");
  assert.throws(() => L.record(makeCase(), { home: inside }), /plugin の中に置きません/);
  assert.equal(fs.existsSync(inside), false);
});

test("件数が minCases 未満なら提案せず insufficient として件数だけ返す", () => {
  freshHome();
  L.record(makeCase());
  L.record(makeCase());
  const { json, markdown } = L.report();
  assert.equal(json.cases, 2);
  assert.equal(json.minCases, 3);
  for (const s of Object.values(json.sections)) assert.deepEqual(s, { status: "insufficient", cases: 2 });
  assert.deepEqual(json.proposals, []);
  assert.equal(json.autoApply, false);
  assert.match(markdown, /件数不足（2 件）/);
  assert.match(markdown, /提案はありません/);
});

test("3 件以上で同じ質問が 1 回目に未確定なら、聞き方・順序の見直しを提案する", () => {
  freshHome();
  for (let i = 0; i < 3; i++) L.record(makeCase());
  const { json, markdown } = L.report();
  assert.equal(json.sections.unresolvedRound1.status, "ok");
  const a = json.proposals.find((p) => p.id === "a:audience.age");
  assert.ok(a, "audience.age の提案が無い");
  assert.deepEqual(a.evidence, { cases: 3, of: 3, rate: 1, counter: 0 });
  assert.equal(json.sections.rounds.distribution["2"], 3);
  const c = json.proposals.find((p) => p.id === "c:premise");
  assert.ok(c, "前提へ戻る頻度の提案が無い");
  assert.match(c.text, /E1/);
  assert.ok(json.proposals.some((p) => p.id === "d:uncategorized"));
  assert.ok(json.proposals.some((p) => p.id === "d:spacing" && /昇格させず/.test(p.text)));
  assert.match(markdown, /## \(a\) 1 回目のヒアリングで未確定になりやすい質問/);
  assert.match(markdown, /\*\*提案\*\*.*反例 0 件/);
  // 閾値を上げれば同じ台帳でも提案しない。
  assert.equal(L.report({ minCases: 4 }).json.proposals.length, 0);
});

test("壊れた行や許可リストに合わない行は数えずに skippedLines へ回す", () => {
  const home = freshHome();
  L.record(makeCase());
  fs.appendFileSync(ledgerFile(home), "not json\n" + JSON.stringify({ version: 1, extra: true }) + "\n");
  const { json } = L.report();
  assert.equal(json.cases, 1);
  assert.equal(json.skippedLines, 2);
});

test("suggest は事実値を返さず、参考値は suggestion・要確認として返す", () => {
  freshHome();
  assert.equal(L.suggest().insufficient, true);
  assert.deepEqual(L.suggest().suggestions, {});
  for (let i = 0; i < 3; i++) L.record(makeCase());
  const s = L.suggest();
  assert.equal(s.source, "suggestion");
  assert.equal(s.reconfirm, true);
  assert.equal(s.insufficient, false);
  const raw = JSON.stringify(s);
  for (const word of FORBIDDEN) assert.equal(raw.includes(word), false, "suggest に含まれている: " + word);
  const values = Object.values(s.suggestions);
  assert.ok(values.length > 0);
  for (const v of values) {
    assert.equal(v.source, "suggestion");
    assert.equal(v.reconfirm, true);
    assert.equal("value" in v, false);
  }
  assert.ok(values.some((v) => v.path === "audience.age"));
});

test("様式: 提案から 2 番目を選ぶと source=proposal・chosenRank=2・その label だけを記録する", () => {
  const home = freshHome();
  const { record: rec } = L.record(makeCase({ style: "proposal" }));
  assert.deepEqual(rec.style, { source: "proposal", proposalsOffered: 3, chosenRank: 2, labels: ["切り絵"] });
  const raw = fs.readFileSync(ledgerFile(home), "utf8");
  for (const word of ["refs/", "sample-photo", "やさしい春", "basis", "moodWords"])
    assert.equal(raw.includes(word), false, word);
});

test("様式: おまかせは delegated、様式名の指定は answer として記録し、answer では提案ファイル欠落を数えない", () => {
  freshHome();
  const delegated = L.record(makeCase({ style: "delegated" })).record;
  assert.deepEqual(delegated.style, { source: "delegated", proposalsOffered: 3, chosenRank: 1, labels: ["水彩"] });
  const answered = L.record(makeCase({ style: "answer" })).record;
  assert.deepEqual(answered.style, { source: "answer", proposalsOffered: 0, chosenRank: null, labels: ["切り絵"] });
  assert.equal(answered.missingInputs.includes("styleProposals"), false);
  const missing = L.record(makeCase({ style: "proposal", omit: ["styleProposals"] })).record;
  assert.equal(missing.style.source, "proposal");
  assert.equal(missing.style.proposalsOffered, null);
  assert.ok(missing.missingInputs.includes("styleProposals"));
});

test("様式: 40 字を超えるラベルやパスらしいラベルは切り詰めずに拒否し、台帳へ書かない", () => {
  const home = freshHome();
  assert.throws(() => L.record(makeCase({ styleLabel: ["あ".repeat(41)] })), /40 字を超えています（41 字）/);
  assert.throws(() => L.record(makeCase({ styleLabel: "refs/sample-photo.png" })), /ファイルパス/);
  assert.throws(() => L.record(makeCase({ styleLabel: "photo.png" })), /ファイルパス/);
  assert.equal(lines(home).length, 0);
  assert.doesNotThrow(() => L.record(makeCase({ styleLabel: ["あ".repeat(40)] })));
});

test("様式: report は言葉にできなかった割合 (f) と採択ラベルの傾向 (g) を出し、suggest は参考候補として返す", () => {
  freshHome();
  L.record(makeCase({ style: "answer" }));
  L.record(makeCase({ style: "proposal" }));
  L.record(makeCase({ style: "proposal" }));
  L.record(makeCase({ style: "delegated" }));
  const { json, markdown } = L.report();
  const f = json.sections.styleSource;
  assert.equal(f.status, "ok");
  assert.deepEqual(f.bySource, { answer: 1, proposal: 2, delegated: 1 });
  assert.equal(f.notVerbalizedRate, 0.75);
  assert.ok(json.proposals.some((p) => p.id === "f:not-verbalized"));
  const g = json.sections.styleLabels;
  assert.deepEqual(g.byLabel[0], { label: "切り絵", cases: 3, rate: 0.75 });
  assert.deepEqual(g.trends, ["切り絵"]);
  assert.match(markdown, /## \(f\) 様式を言葉にできなかった割合/);
  assert.match(markdown, /## \(g\) 採択された様式ラベルの傾向/);
  const style = Object.values(L.suggest().suggestions).find((v) => v.path === "stylePreferences");
  assert.ok(style, "様式の参考候補が無い");
  assert.deepEqual(style.labels, ["切り絵"]);
  assert.match(style.text, /前回までに選ばれた様式（参考・要確認）: 切り絵/);
  assert.match(style.text, /おまかせ/);
  assert.equal(style.source, "suggestion");
  assert.equal(style.reconfirm, true);
});

test("様式: 件数が minCases 未満なら (f)(g) は insufficient で、suggest も様式を返さない", () => {
  freshHome();
  L.record(makeCase({ style: "proposal" }));
  L.record(makeCase({ style: "delegated" }));
  const { json } = L.report();
  assert.deepEqual(json.sections.styleSource, { status: "insufficient", cases: 2 });
  assert.deepEqual(json.sections.styleLabels, { status: "insufficient", cases: 2 });
  assert.equal(Object.values(L.suggest().suggestions).some((v) => v.path === "stylePreferences"), false);
});

test("同じ所見・同じ画像の再提出は、FIX の傾向に二重に数えない", () => {
  const home = freshHome();
  const dir = makeCase();
  const file = path.join(dir, "cycle-ledger.json");
  const ledger = JSON.parse(fs.readFileSync(file, "utf8"));
  ledger.entries.push({ ...ledger.entries[0], cycle: 1, at: "2026-10-23T01:00:00Z", consumed: false, reason: "同じ所見・同じ画像の再提出" });
  fs.writeFileSync(file, JSON.stringify(ledger));
  L.record(dir);
  const rec = JSON.parse(lines(home)[0]);
  assert.equal(rec.cycles.used, 1);
  assert.deepEqual(rec.cycles.byFixClass, { deterministic: 1, "within-plan": 0, premise: 1, preference: 0 });
  assert.equal(rec.cycles.premiseReturns, 1);
});

test("資料で明示された様式は出典documentを保持し、集計では明示指定answerへ数える", () => {
  freshHome();
  const dir = makeCase({ style: "answer" }), file = path.join(dir, "intake.json");
  const intake = JSON.parse(fs.readFileSync(file, "utf8"));
  intake.answers["/stylePreferences"] = { ...intake.answers.stylePreferences, source: "document" };
  delete intake.answers.stylePreferences;
  write(file, intake);
  const rec = L.record(dir).record;
  assert.deepEqual(rec.style, { source: "answer", proposalsOffered: 0, chosenRank: null, labels: ["切り絵"] });
  assert.equal(rec.missingInputs.includes("styleProposals"), false);
  assert.equal(JSON.parse(fs.readFileSync(file, "utf8")).answers["/stylePreferences"].source, "document");
});

test("新旧の提案差戻しはcycleを維持し、前提崩れの統計と提案を増やさない", () => {
  freshHome();
  for (let i = 0; i < 3; i++) {
    const dir = makeCase({ omit: ["visualReview"] }), file = path.join(dir, "cycle-ledger.json");
    const ledger = JSON.parse(fs.readFileSync(file, "utf8"));
    ledger.entries[0].trigger = "analysis-review";
    ledger.entries[0].fixClasses = i === 0 ? {} : { premise: 2 };
    write(file, ledger);
    const rec = L.record(dir).record;
    assert.equal(rec.cycles.used, 1);
    assert.equal(rec.cycles.premiseReturns, 0);
    assert.deepEqual(rec.cycles.byFixClass, { deterministic: 0, "within-plan": 0, premise: 0, preference: 0 });
    assert.deepEqual(rec.cycles.premiseServes, {});
  }
  const report = L.report().json;
  assert.equal(report.sections.fixClasses.premiseCases, 0);
  assert.equal(report.proposals.some(proposal => proposal.id === "c:premise"), false);
});
test("提案レビューの好みは既存の好み集計へ入り、前提崩れとは分けて記録される", () => {
  freshHome();
  const dir = makeCase({ omit: ["visualReview"] });
  write(path.join(dir, "analysis-review.json"), {
    decision: "PASS", mandatoryFixes: [], preferenceNotes: [{ text: "背景をもう少し落ち着かせたい好み" }],
  });
  const rec = L.record(dir).record;
  assert.deepEqual(rec.preferences, [{ category: "uncategorized" }]);
});
