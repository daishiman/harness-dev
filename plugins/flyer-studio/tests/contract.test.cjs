"use strict";
const test = require("node:test"),
  assert = require("node:assert/strict"),
  fs = require("node:fs"),
  path = require("node:path"),
  os = require("node:os");
const P = require("../scripts/project.cjs"),
  { fixture, syntheticReview } = require("./fixture.cjs");
function temp() {
  return path.join(
    fs.mkdtempSync(path.join(os.tmpdir(), "flyer-test-")),
    "project",
  );
}
function mutated(fn) {
  const p = fixture(temp());
  fn(p);
  return P.validate(p);
}
const inputChecks = {};
// 例の JSON を入力 schema で検査する検証器。schema ごとに 1 度だけ作って使い回す。
function inputSchema(name) {
  const Ajv = require("ajv");
  return (inputChecks[name] ??= new Ajv({ allErrors: true }).compile(
    P.read(path.join(P.ROOT, "schemas", name + ".schema.json")),
  ));
}
test("preset なしの init は中立の既定値で、案件固有の値を持たない", () => {
  const d = temp();
  P.init(d);
  const p = P.load(d);
  const neutral = require("../scripts/design.cjs").contract.initDefaults;
  assert.equal(p.brief.count, neutral.variantCount);
  assert.equal(p.brief.whiteCount, neutral.whiteCount);
  assert.equal(p.brief.policy.maxChars, null);
  assert.deepEqual(p.brief.policy.axisGroups, []);
  assert.equal(p.brief.analysisMode, "new-from-brief");
  assert.equal(p.brief.preset, undefined);
  assert.equal(p.brief.title, "");
  assert.deepEqual(p.brief.purpose, { audience: "", benefit: "", action: "" });
  assert.equal(p.concepts.variants.length, neutral.variantCount);
  assert.equal(p.assets.entries.length, 0);
  assert.ok(
    Object.values(p.brief.confirmations).every((value) => value === false),
  );
  assert.ok(P.validate(p).fail > 0);
  assert.throws(() => P.init(d), /上書き/);
});
test("hyogo と hyogo-ai の preset は従来の兵庫の brief を同じ値で作る", () => {
  const example = P.read(P.ROOT + "/references/presets/hyogo-ai/brief.example.json");
  const briefs = ["hyogo", "hyogo-ai"].map((name) => {
    const d = temp();
    P.init(d, name);
    return P.load(d);
  });
  for (const p of briefs) {
    assert.equal(p.brief.count, 13);
    assert.equal(p.brief.whiteCount, 3);
    assert.equal(p.brief.policy.maxChars, 225);
    assert.equal(p.brief.policy.axisGroups.length, 6);
    assert.equal(p.concepts.variants.length, 13);
    assert.equal(p.concepts.variants.filter((v) => v.paper === "white").length, 3);
    for (const key of ["title", "hero", "copy", "copyGroups", "requiredRefs", "qrUrl", "page", "policy"])
      assert.deepEqual(p.brief[key], example[key], key);
    assert.deepEqual(p.brief.preset, {
      id: "hyogo-ai",
      knowledgeFiles: [
        "references/presets/hyogo-ai/case-notes.md",
        "references/presets/hyogo-ai/v13-feedback.md",
      ],
    });
    for (const file of p.brief.preset.knowledgeFiles)
      assert.ok(fs.existsSync(path.join(P.ROOT, file)), file);
    assert.deepEqual(p.brief.purpose, { audience: "", benefit: "", action: "" });
    assert.ok(Object.values(p.brief.confirmations).every((value) => value === false));
  }
  assert.deepEqual(briefs[0].brief, briefs[1].brief);
});
test("preset.json の brief は例の brief と一致し、未知の preset は拒否する", () => {
  const preset = P.preset("hyogo-ai");
  const example = P.read(P.ROOT + "/" + preset.briefExample);
  for (const [key, value] of Object.entries(preset.brief))
    assert.deepEqual(value, example[key], key);
  assert.equal(P.preset(), null);
  const d = temp();
  assert.throws(() => P.init(d, "unknown-case"), /未知の preset/);
  assert.equal(fs.existsSync(d), false);
});
test("preset.json の sceneExample は宣言があれば、その preset フォルダ内に実在し scene の schema に従う", () => {
  const presets = path.join(P.ROOT, "references", "presets");
  const dirs = fs.readdirSync(presets)
    .map((name) => path.join(presets, name))
    .filter((dir) => fs.existsSync(path.join(dir, "preset.json")));
  const problems = (dir, doc) => {
    if (doc.sceneExample === undefined) return [];
    if (typeof doc.sceneExample !== "string") return ["文字列ではない"];
    const file = path.resolve(P.ROOT, doc.sceneExample),
      rel = path.relative(dir, file);
    if (rel === "" || rel.startsWith("..") || path.isAbsolute(rel)) return ["preset の外: " + doc.sceneExample];
    if (!fs.statSync(file, { throwIfNoEntry: false })?.isFile()) return ["実在しない: " + doc.sceneExample];
    const check = inputSchema("scene");
    return check(P.read(file)) ? [] : ["schema: " + JSON.stringify(check.errors)];
  };
  const found = dirs.flatMap((dir) =>
    problems(dir, P.read(path.join(dir, "preset.json"))).map((m) => path.basename(dir) + ": " + m));
  assert.deepEqual(found, []);
  // 反例: 外へ出るパス（.. で抜けるものを含む）、無いパス、scene ではないファイルはそれぞれ拒否する。
  // .. を残すため path.join で正規化せず、文字列のまま繋ぐ。
  const dir = dirs[0],
    own = (name) => path.relative(P.ROOT, dir) + "/" + name;
  assert.match(problems(dir, { sceneExample: own("../../../examples/scene.example.json") })[0], /^preset の外: .*\.\./);
  assert.match(problems(dir, { sceneExample: "examples/scene.example.json" })[0], /^preset の外: /);
  assert.match(problems(dir, { sceneExample: own("missing.scene.json") })[0], /^実在しない: /);
  assert.match(problems(dir, { sceneExample: own("preset.json") })[0], /^schema: /);
});
test("hyogo-ai の素材は preset を選んだ案件だけが一覧・import・照合に使える", () => {
  const ids = (list) => new Set(list.map((e) => e.id));
  const shared = ids(P.catalog()),
    hyogo = ids(P.catalog("hyogo-ai"));
  for (const id of ["U01", "LOGO_SOURCE", "LOGO_PLACEMENT", "LOGO_PRINT", "F07", "REF01", "NEW01", "M01"]) {
    assert.equal(shared.has(id), false, id);
    assert.ok(hyogo.has(id), id);
  }
  assert.equal(shared.size, 0);
  assert.deepEqual(ids(P.catalog("hyogo")), hyogo);
  assert.throws(() => P.catalog("unknown-case"), /未知の preset/);
  const d = temp();
  P.init(d);
  for (const id of ["U01", "LOGO_PRINT", "REF01", "NEW01", "M01", "NEW05"])
    assert.throws(() => P.importAsset(d, { id }), /preset hyogo-ai 専用/);
  const selected = temp();
  P.init(selected, "hyogo-ai");
  assert.equal(P.importAsset(selected, { id: "M01" }).id, "M01");
  // A copied bundled photo loses the preset's approval and needs its own record.
  const r = mutated((p) => delete p.brief.preset);
  assert.ok(r.issues.some((i) => i.code === "photo-privacy-record"));
});
test("承認済み白黒の中央軸シーンが検査を通る", () => {
  const p = fixture(temp());
  const r = P.validate(p);
  assert.deepEqual(r.issues, []);
});
test("QRを除いた幅の中央90mmに寄せた文章を拒否", () => {
  const r = mutated((p) => {
    p.scene.variants[0].texts.find((t) => t.group === "venue").x -= 15;
  });
  assert.ok(r.issues.some((i) => i.code === "page-axis"));
});
test("全幅の中央軸はQR位置を変えても不変", () => {
  const r = mutated((p) => {
    p.scene.variants[0].qr.x = 12;
  });
  assert.equal(r.issues.filter((i) => i.code === "page-axis").length, 0);
});
test("軸なし方針では会場を中心から外した構図を許可", () => {
  const r = mutated((p) => {
    p.brief.policy.center = "none";
    delete p.brief.policy.axisGroups;
    p.scene.variants[0].texts.find((t) => t.group === "venue").x -= 15;
  });
  assert.equal(r.issues.filter((i) => i.code === "page-axis").length, 0);
  assert.equal(r.issues.filter((i) => i.code === "axis-groups").length, 0);
});
test("案件で指定した意味群だけを中心軸で検査", () => {
  const r = mutated((p) => {
    p.brief.policy.axisGroups = ["venue"];
    p.scene.variants[0].texts.find((t) => t.group === "price").x -= 15;
  });
  assert.equal(r.issues.filter((i) => i.code === "page-axis").length, 0);
  const v = mutated((p) => {
    p.brief.policy.axisGroups = ["venue"];
    p.scene.variants[0].texts.find((t) => t.group === "venue").x -= 15;
  });
  assert.ok(v.issues.some((i) => i.code === "page-axis"));
});
test("紙面に無い軸意味群・空の軸指定・軸なしとの矛盾を拒否", () => {
  for (const policy of [
    { axisGroups: ["venu"] },
    { axisGroups: [] },
    { center: "none", axisGroups: ["venue"] },
  ]) {
    const r = mutated((p) => Object.assign(p.brief.policy, policy));
    assert.ok(
      r.issues.some((i) => i.code === "axis-groups"),
      JSON.stringify(policy),
    );
  }
});
test("必須トーンの欠落と案数超過を拒否し、案件ごとに変更できる", () => {
  const r = mutated((p) => (p.concepts.variants[0].tone = "color"));
  assert.ok(r.issues.some((i) => i.code === "tone-range"));
  const over = mutated(
    (p) => (p.brief.policy.requiredTones = ["light", "dark", "color"]),
  );
  assert.ok(over.issues.some((i) => i.code === "tone-range"));
  const custom = mutated((p) => {
    p.brief.policy.requiredTones = ["dark"];
    p.concepts.variants[1].tone = "color";
  });
  assert.equal(custom.issues.filter((i) => i.code === "tone-range").length, 0);
});
test("色だけ違う構図を拒否", () => {
  const r = mutated(
    (p) =>
      (p.concepts.variants[1].signature = {
        ...p.concepts.variants[0].signature,
      }),
  );
  assert.ok(r.issues.some((i) => i.code === "diversity"));
});
test("写真の承認cropを外すと拒否", () => {
  const r = mutated((p) => delete p.scene.variants[0].photos[0].cropPx);
  assert.ok(r.issues.some((i) => i.code === "privacy-crop"));
});
test("参考人物画像を実素材として使うことを拒否", () => {
  const p = fixture(temp());
  assert.throws(
    () =>
      P.importAsset(p.dir, {
        id: P.catalog("hyogo-ai").find((e) => e.kind === "reference").id,
      }),
    /参照専用/,
  );
});
test("生成プロンプトだけで背景生成済みにはならない", () => {
  const r = mutated(
    (p) =>
      (p.assets.entries.find((e) => e.id === "M01").provenance = {
        mode: "generated",
        prompt: "test",
      }),
  );
  assert.ok(r.issues.some((i) => i.code === "background-provenance"));
});
test("過去の駅前表記・必須住所の欠落を拒否", () => {
  const r = mutated((p) => {
    p.brief.copy.building = "アスピア明石北館（明石駅前）";
    p.scene.variants[0].texts = p.scene.variants[0].texts.filter(
      (t) => t.ref !== "address",
    );
  });
  assert.ok(r.issues.some((i) => i.code === "forbidden-copy"));
  assert.ok(r.issues.some((i) => i.code === "copy-missing"));
});
test("配置した掲載文が空・空白だけなら、必須情報を載せたことにしない", () => {
  assert.equal(mutated(() => {}).issues.some((i) => i.code === "copy-empty"), false);
  for (const blank of ["", "　 ", ["", " "]]) {
    const r = mutated((p) => (p.brief.copy.brand = blank));
    assert.ok(r.issues.some((i) => i.code === "copy-empty" && i.id === "F07"), JSON.stringify(blank));
  }
});
test("非公開の新写真は確認記録なしでimportしない", () => {
  const d = temp();
  P.init(d);
  assert.throws(
    () =>
      P.importAsset(d, {
        id: "NEW",
        file: P.ROOT + "/assets/photos/U01.png",
        kind: "photo",
      }),
    /privacy/,
  );
});
test("プロジェクト外の相対パスを拒否", () =>
  assert.throws(() => P.inside(P.ROOT, "../secrets"), /範囲外/));
test("中心ポリシーの上書きを入力契約で拒否", () => {
  const r = mutated((p) => (p.brief.policy.center = "exclude-qr"));
  assert.ok(r.issues.some((i) => i.code === "schema-brief"));
  assert.match(JSON.stringify(r), /center/);
});
test("希望していない表現形式を拒否", () => {
  const r = mutated(
    (p) => (p.concepts.variants[0].expression = "未確認の漫画"),
  );
  assert.ok(r.issues.some((i) => i.code === "expression"));
});
test("意味群の付け替えで中央軸検査を回避できない", () => {
  const r = mutated((p) => {
    const t = p.scene.variants[0].texts.find((t) => t.ref === "venue");
    t.group = "hero";
    t.x -= 15;
  });
  assert.ok(r.issues.some((i) => i.code === "copy-group"));
});
test("欠落した数値と単一案は入力契約で拒否", () => {
  const r = mutated((p) => {
    p.brief.count = 1;
    p.scene.variants[0].texts[0].x = "bad";
  });
  assert.ok(r.fail > 0);
});
test("公開条件の確認後も素材変更はSHAで検出", () => {
  const p = fixture(temp());
  fs.appendFileSync(p.dir + "/assets/M01.png", "changed");
  assert.ok(P.validate(p).issues.some((i) => i.code === "asset-hash"));
});

test("白外縁0mmと安全域を超える外縁を拒否", () => {
  for (const edge of [0, 11]) {
    const r = mutated((p) => (p.brief.page.whiteEdge = edge));
    assert.ok(r.fail > 0);
  }
});
test("新写真は各公開項目の確認内容が必要", () => {
  const d = temp();
  P.init(d);
  const file = P.ROOT + "/assets/photos/U01.png";
  assert.throws(
    () =>
      P.importAsset(d, {
        id: "CUSTOM",
        file,
        kind: "photo",
        privacy: { reviewed: true },
      }),
    /ownerFace/,
  );
  const privacy = {
    reviewed: true,
    ownerFace: "本人顔出し承諾済み",
    otherFaces: "画像内に他者なし",
    child: "写っていない",
    personalDeviceScreens: "写っていない",
    unrelatedEventMarks: "クロップで除外済み",
  };
  assert.equal(
    P.importAsset(d, { id: "CUSTOM", file, kind: "photo", privacy }).privacy
      .ownerFace,
    privacy.ownerFace,
  );
});
test("同梱写真の台帳から承認crop条件を削除しても拒否", () => {
  const r = mutated(
    (p) => delete p.assets.entries.find((e) => e.id === "U01").requiredCropPx,
  );
  assert.ok(r.issues.some((i) => i.code === "photo-catalog-policy"));
});
test("同梱写真の顔の公開条件を変更しても拒否", () => {
  const r = mutated(
    (p) =>
      (p.assets.entries.find((e) => e.id === "U01").privacy.otherFaces =
        "allowed"),
  );
  assert.ok(r.issues.some((i) => i.code === "photo-catalog-policy"));
});
test("QRとロゴ・被写体保護領域の重なりを拒否", () => {
  let r = mutated(
    (p) =>
      (p.scene.variants[0].logo = {
        ...p.scene.variants[0].logo,
        x: 166,
        y: 253,
        w: 32,
        h: 32,
      }),
  );
  assert.ok(r.issues.some((i) => i.code === "qr-logo-collision"));
  r = mutated((p) =>
    p.scene.variants[0].protectedRegions.push({ x: 166, y: 253, w: 32, h: 32 }),
  );
  assert.ok(r.issues.some((i) => i.code === "qr-subject-collision"));
});
test("ロゴ枠への写真の誤指定を拒否", () => {
  const r = mutated((p) => (p.scene.variants[0].logo.asset = "U01"));
  assert.ok(r.issues.some((i) => i.code === "logo-kind"));
});

test("目視台帳は文字列false・不正日時・重複IDを拒否", () => {
  const C = require("../scripts/checks.cjs"),
    p = fixture(temp());
  const checks = {
    fingerprint: "a".repeat(64),
    rows: p.scene.variants.map((v, i) => ({
      id: v.id,
      pngSha256: String(i + 1).repeat(64),
    })),
  };
  const base = syntheticReview(p, checks);
  assert.doesNotThrow(() => C.validateReview(base, checks, p));
  for (const key of [
    "viewedFull",
    "viewedThumbnail",
    "viewedDetails",
    "privacyChecked",
    "axisChecked",
    "worldviewChecked",
  ]) {
    const review = structuredClone(base);
    review.items[0][key] = "false";
    assert.throws(() => C.validateReview(review, checks, p));
  }
  const invalidDate = structuredClone(base);
  invalidDate.reviewedAt = "not-a-date";
  assert.throws(() => C.validateReview(invalidDate, checks, p));
  const twice = structuredClone(base);
  twice.items[1].id = twice.items[0].id;
  assert.throws(() => C.validateReview(twice, checks, p));
});
test("初見の読み順は設計意図と照合し、自己申告で通さない", () => {
  const C = require("../scripts/checks.cjs"),
    p = fixture(temp());
  const checks = {
    fingerprint: "a".repeat(64),
    rows: p.scene.variants.map((v, i) => ({
      id: v.id,
      pngSha256: String(i + 1).repeat(64),
    })),
  };
  const base = syntheticReview(p, checks);
  const order = p.concepts.variants[0].designIntent.readingOrder;
  const swapped = structuredClone(base);
  Object.assign(swapped.items[0].readingTest, { firstRead: "万壽本 大嗣", firstGroup: order[1], nextRead: "聞ける人が、ここにいる。", nextGroup: order[0] });
  assert.throws(() => C.validateReview(swapped, checks, p), /最初と異なります/);
  const unknown = structuredClone(base);
  unknown.items[0].readingTest.nextGroup = "headline";
  assert.throws(() => C.validateReview(unknown, checks, p), /別々の群/);
  const jumped = structuredClone(base);
  Object.assign(jumped.items[0].readingTest, { nextRead: "会社のAI導入、何から始める？", nextGroup: order[2] });
  assert.throws(() => C.validateReview(jumped, checks, p), /理由・迷い/);
  jumped.items[0].readingTest.hesitation =
    "登壇者名より先に右下の質問へ目が移り、人物写真の視線が質問側を向いていた";
  assert.doesNotThrow(() => C.validateReview(jumped, checks, p));
  const invented = structuredClone(base);
  invented.items[0].readingTest.firstRead = "AI相談会のご案内";
  assert.throws(() => C.validateReview(invented, checks, p), /掲載文にありません/);
  const partial = structuredClone(base);
  partial.items[0].readingTest.firstRead = "ここにいる";
  assert.doesNotThrow(() => C.validateReview(partial, checks, p));
  const noAudience = structuredClone(base);
  noAudience.items[0].readingTest.audienceCue = "確認済み";
  assert.throws(() => C.validateReview(noAudience, checks, p), /目視レビュー契約|誰に向けた/);
});
test("分析で保持すると決めた点を新画像で確認しないと合格しない", () => {
  const C = require("../scripts/checks.cjs"),
    p = fixture(temp());
  const checks = {
    fingerprint: "a".repeat(64),
    rows: p.scene.variants.map((v, i) => ({
      id: v.id,
      pngSha256: String(i + 1).repeat(64),
    })),
  };
  const id = p.scene.variants[0].id;
  const strength = "縦の導入コピーと横の主題が直交して視線を止める構成";
  P.write(p.dir + "/analysis.json", {
    variants: [{ id, preservedStrengths: [strength] }],
  });
  const base = syntheticReview(p, checks);
  assert.deepEqual(
    base.items[0].preservationChecks.map((c) => c.strength),
    [strength],
  );
  assert.equal(base.items[1].preservationChecks, undefined);
  assert.doesNotThrow(() => C.validateReview(base, checks, p));
  const missing = structuredClone(base);
  delete missing.items[0].preservationChecks;
  assert.throws(() => C.validateReview(missing, checks, p), /保持確認が一致/);
  const fix = structuredClone(base);
  fix.items[0].preservationChecks[0].verdict = "FIX";
  assert.throws(() => C.validateReview(fix, checks, p), /保持点が新画像/);
  const extra = structuredClone(base);
  extra.items[1].preservationChecks = [
    { strength, verdict: "PASS", observation: "分析に無い保持点を後から足した記録" },
  ];
  assert.throws(() => C.validateReview(extra, checks, p), /保持確認が一致/);
});
test("各案は比較して採らなかった候補と理由を持ち、他案の理由を流用しない", () => {
  const none = mutated(
    (p) => (p.concepts.variants[0].designIntent.rejectedAlternatives = []),
  );
  assert.ok(none.issues.some((i) => i.code === "schema-concepts"));
  const copied = mutated(
    (p) =>
      (p.concepts.variants[1].designIntent.rejectedAlternatives = structuredClone(
        p.concepts.variants[0].designIntent.rejectedAlternatives,
      )),
  );
  assert.ok(copied.issues.some((i) => i.code === "intent-rejected"));
});

test("同じSHAの素材は正規ID一件となり、別名は画像を二重に持たず出所の記録を残す", () => {
  const catalog = P.catalog("hyogo-ai");
  assert.equal(new Set(catalog.map(e => e.sha256)).size, catalog.length);
  const d = temp(); P.init(d, "hyogo-ai");
  for (const [canonical, alias] of [["REF04", "NEW05"], ["REF02", "NEW06"], ["REF01", "NEW07"]]) {
    const entry = catalog.find(e => e.id === canonical);
    assert.ok(entry.aliases.includes(alias));
    assert.equal(catalog.some(e => e.id === alias), false);
    // 別名は正規側の画像を指し、どこから来たかは元の出所パスで追える。
    const record = entry.provenance.aliases.find(e => e.id === alias);
    assert.equal(record.file, entry.file);
    assert.equal(record.sha256, entry.sha256);
    assert.match(record.provenance.relativeSource, new RegExp("(^|/)" + alias + "\\.png$"));
    assert.equal(typeof entry.privacy.containsPeople, "boolean");
    assert.throws(() => P.importAsset(d, { id: alias }), /参照専用/);
  }
  // 台帳が指す実ファイルは、別名の分も含めて同じSHAにつき一つ。台帳に無いファイルは package の検査が配布を止める。
  const files = new Map();
  for (const e of P.read(path.join(P.ROOT, "assets", "catalog.json")).entries)
    for (const item of [e, ...(e.provenance?.aliases || [])]) {
      assert.equal(P.sha(path.join(P.ROOT, "assets", item.file)), item.sha256, item.id);
      files.set(item.sha256, new Set([...(files.get(item.sha256) || []), item.file]));
    }
  assert.deepEqual([...files.values()].filter((s) => s.size > 1).map((s) => [...s]), []);
});
test("中立のbriefとsceneの例は入力schemaに従い、案件素材を含まない", () => {
  for (const name of ["brief", "scene"]) {
    const data = P.read(path.join(P.ROOT, "examples", name + ".example.json"));
    const check = inputSchema(name);
    assert.ok(check(data), JSON.stringify(check.errors));
    assert.doesNotMatch(JSON.stringify(data), /Hyogo|兵庫|明石|peatix|LOGO_PRINT|U01/);
  }
});
test("中立のbriefとsceneの例は組み合わせると、URLなしの申込導線・主題・必須情報の検査を通る", () => {
  const D = require("../scripts/design.cjs");
  const ex = (name) => P.read(path.join(P.ROOT, "examples", name + ".example.json"));
  // 例は案の記録と素材を持たない。案の記録は例の scene から作り、背景の仮置きは fixture の承認済み
  // 背景へ差し替え、例が使わない素材は外す。残る指摘は例そのものに由来するので、どれも許さない
  // （検査が増えれば、例も自動でその対象になる）。
  const codes = (edit = () => {}) =>
    mutated((p) => {
      const concept = p.concepts.variants.find((v) => v.paper === "color"),
        backdrop = p.scene.variants.find((v) => v.paper === "color").background.asset;
      p.brief = { ...ex("brief"), stylePreferences: [concept.expression] };
      for (const k of Object.keys(p.brief.confirmations)) p.brief.confirmations[k] = true;
      p.scene = ex("scene");
      for (const v of p.scene.variants) {
        assert.match(v.background.asset, /^GENERATE_BACKGROUND_/);
        v.background.asset = backdrop;
      }
      const used = new Set(p.scene.variants.flatMap((v) => [v.background.asset, v.logo?.asset, ...(v.photos || []).map((f) => f.asset)]));
      p.assets.entries = p.assets.entries.filter((e) => used.has(e.id));
      p.concepts.variants = p.scene.variants.map((v) => {
        const groups = [...new Set(v.texts.map((t) => t.group))],
          intent = structuredClone(concept.designIntent);
        return {
          ...structuredClone(concept),
          id: v.id,
          signature: Object.fromEntries(D.contract.signatureKeys.map((k) => [k, v.id + "の" + k])),
          designIntent: {
            ...intent,
            readingOrder: groups,
            groups: groups.map((g) => ({
              group: g,
              purpose: v.id + "の" + g + "群が読み手に伝える内容",
              placementReason: v.id + "の" + g + "群を例の位置へ置く理由",
            })),
            palette: D.declaredColors(v).map((color) => ({ color, role: "例の宣言色", reason: v.id + "の例が宣言した色の役割と理由" })),
            rejectedAlternatives: intent.rejectedAlternatives.map((a) => ({ ...a, reason: v.id + "で比べて見送った理由: " + a.reason })),
          },
        };
      });
      edit(p);
    }).issues.map((i) => i.code);
  assert.deepEqual(codes(), []);
  // 反例: 案ごとの検査が実際に走っていれば、申込案内を抜いた例・空の見出しは落ちる。
  assert.ok(codes((p) => p.scene.variants.forEach((v) => (v.texts = v.texts.filter((t) => t.ref !== "apply")))).includes("copy-missing"));
  assert.ok(codes((p) => delete p.brief.copy.apply).includes("apply-guidance"));
  assert.ok(codes((p) => (p.brief.copy.title = "")).includes("copy-empty"));
  // 背景の仮置きや案の記録のずれも、許す一覧が無いので起きれば落ちる。
  assert.ok(codes((p) => (p.scene.variants[0].background.asset = "GENERATE_BACKGROUND_01")).includes("background"));
  assert.ok(codes((p) => p.concepts.variants[1].designIntent.readingOrder.pop()).includes("intent-reading-order"));
});
test("汎用の文書は特定presetの中身へMarkdownリンクしない", () => {
  const presets = path.join(P.ROOT, "references", "presets");
  const ids = fs.readdirSync(presets, { withFileTypes: true }).filter((e) => e.isDirectory()).map((e) => e.name);
  const intoPreset = (file, body) =>
    [
      ...body.matchAll(/\]\(\s*<?([^)\s>]+)>?[^)]*\)/g),
      ...body.matchAll(/^\s{0,3}\[[^\]]+\]:\s*<?(\S+?)>?(?:\s|$)/gm),
    ]
      .map((m) => m[1])
      .filter((t) => !/^[a-z][a-z0-9+.-]*:/i.test(t) && !t.startsWith("#"))
      .filter((t) => {
        const rel = path.relative(presets, path.resolve(path.dirname(file), decodeURI(t.split(/[#?]/)[0])));
        return rel !== "" && !rel.startsWith("..") && !path.isAbsolute(rel) && ids.includes(rel.split(path.sep)[0]);
      });
  // 走査するのは配布キットへ写る .md のうち preset の中身を除いたもの。何が写るかの正本は
  // scripts/build-local-package.py の shipped() で、除外規則をここへ写さない（新しいフォルダは既定で走査に入る）。
  const listed = require("node:child_process").spawnSync("python3", ["-I", "-B", "-c", [
    "import importlib.util, json",
    "spec = importlib.util.spec_from_file_location('flyer_package', 'scripts/build-local-package.py')",
    "m = importlib.util.module_from_spec(spec); spec.loader.exec_module(m)",
    "print(json.dumps([str(p.relative_to(m.ROOT)) for p in m.shipped(m.ROOT) if p.suffix == '.md' and p.is_file()]))",
  ].join("\n")], { cwd: P.ROOT, encoding: "utf8" });
  assert.equal(listed.status, 0, listed.stderr);
  const files = JSON.parse(listed.stdout)
    .map((f) => path.join(P.ROOT, f))
    .filter((f) => path.relative(presets, f).startsWith(".."));
  const bad = files.flatMap((f) => {
    const body = fs.readFileSync(f, "utf8").replace(/^(```|~~~)[^\n]*\n[\s\S]*?^\1/gm, "").replace(/`[^`\n]*`/g, "");
    return intoPreset(f, body).map((t) => path.relative(P.ROOT, f) + " → " + t);
  });
  assert.ok(files.length > 0 && ids.length > 0);
  assert.ok(files.some((f) => path.dirname(f) === path.join(P.ROOT, "prompts")), "prompts/*.md も走査する");
  assert.deepEqual(bad, []);
  // 反例: presets/ 自体への案内は許し、preset の中身への直リンクは参照定義でも検出する。
  const doc = path.join(P.ROOT, "references", "architecture.md");
  assert.deepEqual(intoPreset(doc, "[一覧](presets/)"), []);
  assert.equal(intoPreset(doc, "[本文](presets/" + ids[0] + "/preset.json#notes)").length, 1);
  assert.equal(intoPreset(doc, "[本文]: ./presets/" + encodeURI(ids[0]) + "/").length, 1);
});
test("presetの無い素材は参照専用か、人物を含まないものに限る", () => {
  const catalog = P.read(path.join(P.ROOT, "assets", "catalog.json"));
  // 根拠となる方針: preset は案件素材の閉じ込め、containsPeople は未確認も人物ありとして扱う安全側の判定。
  assert.ok(catalog.policies.preset && catalog.policies.containsPeople);
  const hasPreset = (e) => typeof e.preset === "string" && e.preset !== "";
  const allowed = (e) =>
    hasPreset(e) || e.usage === "reference-only" || e.privacy?.containsPeople === false;
  assert.equal(allowed({ usage: "selectable", privacy: { containsPeople: true } }), false);
  for (const preset of [null, ""])
    assert.equal(allowed({ preset, usage: "selectable", privacy: { containsPeople: true } }), false, String(preset));
  assert.equal(allowed({ usage: "selectable", privacy: {} }), false);
  assert.deepEqual(catalog.entries.filter((e) => !allowed(e)).map((e) => e.id), []);
});

for (const policyFile of [
  "references/design-rules.md",
  "skills/assign-flyer-evaluator/references/review-contract.md",
  "references/workflow.md",
]) test("判断本文だけの変更で分析承認と完成レビューが失効する: " + policyFile, t => {
  const A = require("../scripts/analysis.cjs"), D = require("../scripts/design.cjs");
  const dir = fs.mkdtempSync(path.join(os.tmpdir(), "flyer-policy-freshness-"));
  t.after(() => fs.rmSync(dir, { recursive: true, force: true }));
  fs.writeFileSync(path.join(dir, "source.png"), "synthetic original image; not visual evidence");
  A.template(dir, {
    producer: "synthetic-analysis-producer",
    purpose: { audience: "近隣の読者", benefit: "活動の参加方法が分かる", action: "案内を確認する" },
    constraints: ["元の案内の意味を変更しない"], requirements: [{ id: "R01", text: "案内の位置を保持する", kind: "required" }],
    sources: [{ id: "F07", file: path.join(dir, "source.png") }],
  });
  const analysis = A.read(path.join(dir, "analysis.json")), variant = analysis.variants[0];
  variant.observations = [{ region: { x: 10, y: 10, w: 50, h: 50 }, observation: "上部の主題と下部の参加案内が別の群に分かれている", refIds: ["DD03"] }];
  variant.preservedStrengths = ["主題から参加案内へ進む群のつながりを保持する"];
  variant.decisions = [{ requirementId: "R01", candidate: "案内の位置を維持して文字の間隔を比較する", decision: "adopt", reason: "主題と参加案内の役割を維持して読めるようにする", targets: ["text:guide"], refIds: ["DD03"] }];
  variant.nextActions = ["案内の位置を維持して間隔を比較する"];
  A.write(path.join(dir, "analysis.json"), analysis);
  A.reviewTemplate(dir);
  const approved = A.read(path.join(dir, "analysis-review.json"));
  Object.assign(approved, { reviewer: "synthetic-independent-analyst", reviewedAt: new Date().toISOString(), decision: "PASS", returnTo: "run-create-flyer" });
  for (const check of Object.values(approved.checks)) Object.assign(check, { verdict: "PASS", evidence: "元画像の領域と保持する案内の位置を要求に照らして確認した" });
  A.write(path.join(dir, "analysis-review.json"), approved);
  assert.equal(A.validateReview(dir).fail, 0);
  const project = fixture(path.join(dir, "native"));
  const checks = { fingerprint: "a".repeat(64), rows: project.scene.variants.map((v, i) => ({ id: v.id, pngSha256: String(i + 1).repeat(64) })) };
  const review = syntheticReview(project, checks);
  assert.doesNotThrow(() => D.validateReview(review, checks, project));
  const analysisBefore = A.policyFingerprint(), reviewBefore = D.reviewPolicyFingerprint();
  const originalRead = fs.readFileSync, target = path.resolve(P.ROOT, policyFile);
  // One body's bytes change in memory; keep every other file and the working tree intact.
  t.mock.method(fs, "readFileSync", function(file, ...args) {
    const bytes = Reflect.apply(originalRead, fs, [file, ...args]);
    if (typeof file !== "string" || path.resolve(file) !== target) return bytes;
    return Buffer.isBuffer(bytes) ? Buffer.concat([bytes, Buffer.from("\n規範本文の変更\n")]) : bytes + "\n規範本文の変更\n";
  });
  assert.notEqual(A.policyFingerprint(), analysisBefore);
  assert.notEqual(D.reviewPolicyFingerprint(), reviewBefore);
  assert.throws(() => A.validateReview(dir), /規範|古い/);
  assert.throws(() => D.validateReview(review, checks, project), /古い|品質基準/);
});
