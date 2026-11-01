"use strict";
const fs = require("node:fs");
const P = require("../scripts/project.cjs");
const D = require("../scripts/design.cjs");
function fixture(dir) {
  P.init(dir, "hyogo");
  const b = P.read(dir + "/brief.json");
  b.designer = "fixture-author";
  // Explicit mode: analysis gates have dedicated behavioral tests.
  b.analysisMode = "new-from-brief";
  b.purpose = {
    audience:
      "会社のAI導入を進める担当者を優先し、個人のAI活用に関心がある人も対象にする",
    benefit:
      "実例トークと質問を通じて、自社や自分がAI活用を始める着手点を理解する",
    action: "Peatixの詳細を確認して交流会へ申し込む",
  };
  b.count = 2;
  b.whiteCount = 1;
  b.stylePreferences = ["写真"];
  for (const k of Object.keys(b.confirmations)) b.confirmations[k] = true;
  P.write(dir + "/brief.json", b);
  for (const id of ["U01", "LOGO_PRINT", "LOGO_PLACEMENT"])
    P.importAsset(dir, { id });
  for (const id of ["M01", "M02"])
    P.importAsset(dir, {
      id,
      provenance: {
        mode: "reuse-approved",
        confirmed: true,
        reason:
          "既存承認素材で描画経路だけを試験。新規背景生成の実行ではない。",
      },
    });
  const text = (ref, y, size, group = "hero", extra = {}) => ({
    id: ref,
    ref,
    x: 12,
    y,
    w: 186,
    size,
    group,
    align: group === "hero" ? "left" : "center",
    font: "sans",
    weight: 400,
    lineHeight: 1.2,
    ...extra,
  });
  const variants = ["F07", "F11"].map((id, i) => ({
    id,
    paper: i ? "white" : "color",
    baseColor: i ? "#FFFFFF" : "#090B0D",
    ink: i ? "#162D34" : "#FFFFFF",
    background: { asset: i ? "M02" : "M01" },
    photos: [
      {
        asset: "U01",
        x: 12,
        y: i ? 69 : 31,
        w: 186,
        h: 90,
        cropPx: [0, 240, 1477, 590],
        fadeMm: 10,
      },
    ],
    logo: {
      asset: i ? "LOGO_PLACEMENT" : "LOGO_PRINT",
      x: 155,
      y: 10,
      w: 43,
      h: 14,
    },
    qr: { x: 166, y: 253, size: 32 },
    protectedRegions: [{ x: 135, y: i ? 92 : 40, w: 27, h: 30 }],
    fields: [],
    texts: [
      text("brand", 12, 12, "hero", { w: 135, weight: 700 }),
      text("lead", 30, 24, "hero", { weight: 700 }),
      text("main", 43, i ? 60 : 58, "hero", {
        font: i ? "sans" : "serif",
        weight: 700,
      }),
      text("listen", 83, 23, "hero", { font: i ? "sans" : "serif" }),
      text("answer", 131, 56, "hero", {
        font: i ? "sans" : "serif",
        weight: 700,
      }),
      text("trio", 162, 16, "speakers", { weight: 700 }),
      text("speakers", 173, 11, "speakers", { layout: "row", weight: 700 }),
      text("question1", 186, 10.5, "questions", { weight: 700 }),
      text("question2", 194, 10.5, "questions", { weight: 700 }),
      text("personal", 202, 10.5, "questions"),
      text("date", 216, 26, "event", { font: "display", weight: 700 }),
      text("time", 231, 13, "event", { weight: 700 }),
      text("venue", 243, 12, "venue", { weight: 700 }),
      text("building", 251, 8.5, "venue"),
      text("address", 259, 8.5, "venue"),
      text("price", 270, 14, "price", { weight: 700 }),
      text("notice", 281, 8.5, "notice"),
      text("apply", 239, 8.5, "apply", {
        x: 166,
        w: 32,
        align: "center",
        weight: 700,
      }),
    ],
  }));
  // Native F07 acceptance exercises preserved vertical introduction + horizontal answer.
  const f07 = variants[0];
  Object.assign(f07.texts.find(t => t.ref === "lead"), { x: 174, y: 28, w: 14, h: 82, size: 21, writingMode: "vertical-rl", textOrientation: "mixed" });
  Object.assign(f07.texts.find(t => t.ref === "main"), { x: 148, y: 40, w: 15, h: 72, size: 25, writingMode: "vertical-rl", textOrientation: "upright" });
  Object.assign(f07.texts.find(t => t.ref === "listen"), { x: 120, y: 108, w: 78, size: 21 });
  Object.assign(f07.photos[0], { w: 120, h: 90 });
  f07.protectedRegions = [{ x: 90, y: 42, w: 24, h: 30 }];
  variants[0].fields = [
    { x: 0, y: 68, w: 125, h: 52, color: "#090B0D", opacity: 0.98 },
  ];
  variants[1].fields = [
    { x: 4, y: 72, w: 100, h: 35, color: "#FFFFFF", opacity: 0.98 },
  ];
  P.write(dir + "/scene.json", { version: 1, variants });
  P.write(dir + "/concepts.json", {
    variants: variants.map((v, i) => ({
      id: v.id,
      paper: v.paper,
      tone: i ? "light" : "dark",
      expression: "写真",
      name: i ? "白外縁・中央軸の描画検証" : "黒背景・中央軸の描画検証",
      signature: {
        hero: i ? "太ゴシックの横組" : "明朝の縦導入と横回答",
        photo: i ? "中央に場を見せる" : "上部へ場を広げる",
        type: i ? "角ゴシック主体" : "明朝と角ゴシック",
        flow: i ? "縦方向の明快な階層" : "余韻を持つ階層",
        information: i ? "軽やかな濃淡" : "暗色の連続領域",
        background: i ? "紙白へ溶ける" : "金と黒の質感",
      },
      designIntent: designIntent(v, i),
      backgroundPrompt: "描画経路試験のため既存背景再利用を明示",
    })),
  });
  return P.load(dir);
}
function designIntent(variant, index) {
  const groups = [
    {
      group: "hero",
      purpose: "参加者が相談会の主題と参加価値を最初に理解する",
      placementReason:
        "左上の小さな内容名から大きな対話コピーへ進み、右上ロゴとは役割を分ける",
    },
    {
      group: "speakers",
      purpose: "実例を話す三人の登壇者を同格として紹介する",
      placementReason:
        "写真の下へ三人の名前を同じ幅と太さで並べ、単独講演との誤解を避ける",
    },
    {
      group: "questions",
      purpose: "会社の導入課題から個人の相談まで参加対象を伝える",
      placementReason:
        "登壇者の次に質問を中央のまとまりで並べ、開催条件への移行前に内容を理解させる",
    },
    {
      group: "event",
      purpose: "参加を決める日付と開始終了の時刻をまとめる",
      placementReason:
        "質問群の後に十分な間隔を取り、大きな日付と従属する時刻を近づける",
    },
    {
      group: "venue",
      purpose: "会場名と建物および所在地を一つの意味群にする",
      placementReason:
        "開催時刻の直下へ会場と小さな住所を紙面中央でまとめ、QRの左へ軸を逃がさない",
    },
    {
      group: "price",
      purpose: "参加費と含まれる条件を参加判断に必要な強さで示す",
      placementReason:
        "住所の次に料金を中央へ置き、日時の主役数字より控えめなサイズにする",
    },
    {
      group: "notice",
      purpose: "必要な注意を本文と区別して料金の近くで読ませる",
      placementReason:
        "料金の下に読める最小サイズ以上で置き、最下端の安全域を残す",
    },
    {
      group: "apply",
      purpose: "読み終えた人が申込のQRと詳細先をひとまとまりで認識する",
      placementReason:
        "右下のQR直上に短い申込案内を置き、中央の開催情報から独立した行動群にする",
    },
  ];
  return {
    readingOrder: groups.map((item) => item.group),
    groups,
    palette: D.declaredColors(variant).map((color) => ({
      color,
      role:
        color.toLowerCase() === variant.ink.toLowerCase()
          ? "本文と主題の文字"
          : "背景と写真を支える濃淡面",
      reason: index
        ? "純白の外縁へつなぐ背景と濃い文字を対比し、写真のある紙面でも読み順を支える"
        : "黒い背景と白い文字を対比し、写真の臨場感より主題が先に読めるようにする",
    })),
    whitespace: [
      {
        x: 0,
        y: 0,
        w: 10,
        h: 297,
        purpose:
          "左端の安全余白を通して、主題と下部情報が用紙端へ迫る圧迫感を避ける",
      },
      {
        x: 12,
        y: 208,
        w: 186,
        h: 6,
        purpose:
          "相談内容の質問群と開催条件の日時群の間を空け、意味の切り替わりを示す",
      },
    ],
    balanceReason: index
      ? "上部は左側の太い主題と右上のロゴを対置し、中央の写真から下部の開催情報へ重さを戻す。右下QRがあっても開催情報の軸は105mmを維持する"
      : "上部の左側の明朝コピーと右側の人物・ロゴを対置し、暗い背景でつなぐ。下部の中央情報群と右下QRの独立した役割を保ち、無理由な横ずれを作らない",
    imageRelationship: index
      ? "公開可能な登壇の場面を中央に広げ、顔の保護領域を避けてコピーを置く。写真の外周を紙白へ薄く戻し、太いゴシックの主題と場の空気を統合する"
      : "公開可能な登壇の場面を上部へ広げ、右側の顔の保護領域を空ける。写真と黒い背景の境界を薄くつなぎ、明朝の主題が自然に読める位置関係にする",
    rejectedAlternatives: [
      index
        ? {
            candidate: "写真を全面に敷く",
            reason:
              "白外縁と紙白の静けさが失われ、太いゴシックの主題と写真の明暗が競合する",
          }
        : {
            candidate: "下部に黒帯を追加",
            reason:
              "暗い背景の中で帯が二重の区切りになり、写真から開催情報への連続が切れる",
          },
    ],
  };
}
// Unit-test attestations only. Never write this as a real project's visual review.
function syntheticReview(project, checks) {
  // A synthetic render record before the review, unless a real render wrote one.
  for (const row of checks.rows) {
    const file = project.dir + "/out/" + row.id + "/render.json";
    if (fs.existsSync(file)) continue;
    fs.mkdirSync(project.dir + "/out/" + row.id, { recursive: true });
    P.write(file, { id: row.id, pngSha256: row.pngSha256, createdAt: "2026-10-21T00:00:00Z" });
  }
  const review = D.reviewTemplate(project, checks);
  review.reviewer = "unit-independent-reviewer";
  review.reviewedAt = new Date().toISOString();
  const observations = [
    {
      summary:
        "黒背景の明朝主題から中央の開催情報へ進み、右下QRとの役割分担を確認する単体試験用の所見",
      balance:
        "左上の明朝コピーと右側の人物の重さを対置し、下部の情報軸が紙面中央に戻る構成を確認する",
      color:
        "暗い背景の上の白い文字と右下の白いQRが競合し過ぎず、主題の輪郭が保たれることを観察する",
      hierarchy:
        "上部の大きな明朝の主題を先に読み、その下の三名と質問群を経て日時へ進む順序を確認する",
      spacing:
        "下部の質問終端と日付の間に切替の余白があり、会場の住所が親の会場名へ帰属することを確認する",
      integration:
        "上部の写真の周囲が黒い背景へ薄くなり、顔の保護領域へ文字が入らず主題と統合していることを確認する",
    },
    {
      summary:
        "白外縁と太いゴシック主題の階層を軸に、中央写真から下部の条件を辿れるか確認する試験用の所見",
      balance:
        "左側の太い主題を右上ロゴと中央写真が支え、白い外縁を保ったまま下部の情報が中央に集まる構成を確認する",
      color:
        "紙白の外縁と濃い青緑の文字を対比し、中央の写真領域に続く情報の可読性が維持されることを観察する",
      hierarchy:
        "太いゴシックの大きな主題が最も強く見え、その後に三人の名前と日付が段階を持って読めることを確認する",
      spacing:
        "白い下部で住所と会場が離れず、質問群から日時へ進む間隔が群の中より広く取られていることを確認する",
      integration:
        "中央の登壇写真の端が白い背景へ自然につながり、人物の顔と太い主題が互いを隠していないことを確認する",
    },
  ];
  const refs = {
    balance: "/balanceReason",
    color: "/palette/0",
    hierarchy: "/readingOrder",
    spacing: "/whitespace/0",
    integration: "/imageRelationship",
  };
  review.items.forEach((item, index) => {
    for (const flag of [
      "viewedFull",
      "viewedThumbnail",
      "viewedDetails",
      "privacyChecked",
      "axisChecked",
      "worldviewChecked",
    ])
      item[flag] = true;
    const order = project.concepts.variants.find((v) => v.id === item.id)
      .designIntent.readingOrder;
    item.readingTest = {
      firstRead: "聞ける人が、ここにいる。",
      firstGroup: order[0],
      nextRead: "万壽本 大嗣",
      nextGroup: order[1],
      hesitation: "",
      audienceCue: "会社のAI導入に迷う人へ向けた問いを上部の主題直後で読めた",
    };
    for (const check of item.preservationChecks || []) {
      check.verdict = "PASS";
      check.observation =
        item.id + "の新画像でも保持点「" + check.strength + "」が縮小像で読めることを確認した";
    }
    item.decision = "PASS";
    item.observations = observations[index].summary;
    for (const key of D.contract.qualityDimensions)
      item.criteria[key] = {
        verdict: "PASS",
        confidence: "high",
        region: { x: 10, y: 10, w: 190, h: 277 },
        observation: observations[index][key],
        intentRef: refs[key],
      };
    // Lenses beyond the escalation are accepted as an optional addition.
    for (const key of D.contract.expertRoles)
      item.expertReviews[key] = {
        reviewer: review.reviewer,
        verdict: "PASS",
        criteria: [...D.contract.expertDimensions[key]],
      };
  });
  return review;
}
module.exports = { fixture, syntheticReview };
