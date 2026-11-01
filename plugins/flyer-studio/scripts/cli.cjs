#!/usr/bin/env node
"use strict";
const fs = require("node:fs"),
  path = require("node:path"),
  P = require("./project.cjs");
function args(argv) {
  const out = { command: argv.shift() || "help" };
  while (argv.length) {
    const k = argv.shift();
    if (!k.startsWith("--")) throw Error("不正な引数: " + k);
    if (!argv.length || argv[0].startsWith("--"))
      throw Error("引数の値が必要: " + k);
    out[k.slice(2)] = argv.shift();
  }
  return out;
}
async function doctor() {
  const R = require("./render.cjs"),
    deps = {};
  for (const n of Object.keys(require("../package.json").dependencies)) {
    try {
      deps[n] = require(n + "/package.json").version;
    } catch {
      deps[n] = "missing";
    }
  }
  let chrome = null;
  try {
    const b = await R.browser();
    chrome = b.version();
    await b.close();
  } catch {}
  const tools = Object.fromEntries(
    ["pdftoppm", "pdfinfo", "pdffonts"].map((n) => [
      n,
      R.command(n),
    ]),
  );
  return {
    node: process.version,
    dependencies: deps,
    browser: chrome,
    pdfTools: tools,
    imageGeneration:
      "ホストの画像生成/編集ツールを制作開始時に発見する。未接続ならユーザーへ確認。",
    fail: Number(
      Object.values(deps).includes("missing") ||
        !chrome ||
        Object.values(tools).some((v) => !v),
    ),
  };
}
function prompts(dir) {
  const p = P.load(dir),
    template = fs.readFileSync(P.ROOT + "/prompts/background.md", "utf8");
  const Ajv = require("ajv");
  const purposeSchema = P.read(P.ROOT + "/schemas/brief.schema.json").properties
    .purpose;
  const ajv = new Ajv({ allErrors: true, strict: false });
  const validatePurpose = ajv.compile(purposeSchema);
  if (!validatePurpose(p.brief.purpose)) {
    throw Error(
      "制作目的の読者・価値・行動を今回の内容で確認してください: " +
        ajv.errorsText(validatePurpose.errors),
    );
  }
  const folder = p.dir + "/prompts";
  fs.mkdirSync(folder, { recursive: true });
  const rows = p.concepts.variants.map((c) => {
    if (!c.name || !c.expression || !c.backgroundPrompt)
      throw Error("先に構図・表現形式・背景意図を具体化してください: " + c.id);
    const prompt = `${template}\n\n用途: ${p.brief.title}\n想定する読者: ${p.brief.purpose.audience}\n読者へ届ける価値: ${p.brief.purpose.benefit}\n促す行動: ${p.brief.purpose.action}\nこの読者が価値を理解し、促す行動へ進める読み順を支える背景にする。主題のための静かな領域と意味群を分ける余白を用意し、背景の装飾が目的を奪わないようにする。\n主題: ${p.brief.hero.join(" ")}\n構図案: ${c.name}\n表現形式: ${c.expression}\n配色系統: ${c.tone}\n背景の意図: ${c.backgroundPrompt}\n紙面: ${p.brief.page.width}×${p.brief.page.height}mm\n${c.paper === "white" ? "外向きの白グラデーション。紙の外縁は純白に溶け込む。" : "指定の暗色/配色を保ち、文字の可読領域を確保。"}\n文字、QR、支給ロゴは描かない。人物を含める場合は許可された表現範囲のみ。\n`;
    fs.writeFileSync(folder + "/" + c.id + "-background.md", prompt);
    return {
      id: c.id,
      file: "prompts/" + c.id + "-background.md",
      promptSha256: P.sha(folder + "/" + c.id + "-background.md"),
      status: "prompt-only-not-generated",
    };
  });
  P.write(folder + "/manifest.json", { items: rows });
  return {
    items: rows,
    message:
      "これはプロンプトのみ。画像生成ツールで実際に生成してからimportしてください。",
  };
}
const USAGE = [
  "doctor",
  "catalog [--preset NAME]",
  "init --project NEW_DIR [--preset NAME]",
  "import --project DIR --id ID [--file PATH --kind KIND] [--privacy FILE] [--provenance FILE]",
  "intake-template [--preset NAME] [--prefill FILE] [--suggestions FILE] [--out FILE]",
  "intake-apply --project DIR --answers FILE",
  "intake-residual --project DIR",
  "essence-baseline --project DIR [--request TEXT]",
  "essence-check --project DIR",
  "essence-revise --project DIR --field PTR --reason TEXT",
  "prompts --project DIR",
  "analysis-template --project DIR --sources FILE",
  "analysis-seal --project DIR",
  "analysis-validate --project DIR",
  "analysis-review-template --project DIR",
  "analysis-review-validate --project DIR",
  "validate --project DIR",
  "render --project DIR [--id 案ID]",
  "verify --project DIR",
  "pilot-review-template --project DIR",
  "review-template --project DIR",
  "cycle-status --project DIR",
  "finalize --project DIR",
  "learn-record --project DIR",
  "learn-report [--min-cases N] [--preset NAME]",
  "learn-suggest [--min-cases N] [--preset NAME]",
];
// 案件 dir を持たないコマンド（plugin 全体か、案件をまたぐ台帳を読む）。
const NO_PROJECT = ["help", "doctor", "catalog", "intake-template", "learn-report", "learn-suggest"];
// JSON を受ける引数は、ファイルパスか JSON 文字列のどちらでもよい（intake.cjs は文字列をパスとして読む）。
const json = (v) => (typeof v === "string" && /^\s*[{[]/.test(v) ? JSON.parse(v) : v);
async function main(argv = process.argv.slice(2)) {
  const a = args([...argv]),
    dir = a.project && path.resolve(a.project);
  if (!NO_PROJECT.includes(a.command) && !dir) throw Error("--project が必要");
  const minCases = Number(a["min-cases"]) > 0 ? Number(a["min-cases"]) : undefined;
  let result;
  switch (a.command) {
    case "help":
      console.log(
        "Flyer Studio（各コマンドの用途は references/runtime.md#コマンド一覧）\n" +
          USAGE.map((u) => "python3 scripts/build-flyer.py " + u).join("\n") +
          "\n\n新写真の import には --privacy FILE が必要。依存: npm ci。",
      );
      return;
    case "doctor":
      result = await doctor();
      break;
    case "catalog":
      result = P.catalog(a.preset).map((e) => ({
        id: e.id,
        kind: e.kind,
        label: e.label,
        usage: e.usage,
      }));
      break;
    case "init":
      result = { project: P.init(dir, a.preset) };
      break;
    case "import":
      result = P.importAsset(dir, {
        id: a.id,
        file: a.file,
        kind: a.kind,
        privacy: a.privacy && P.read(a.privacy),
        provenance: a.provenance && P.read(a.provenance),
      });
      break;
    case "intake-template":
      result = require("./intake.cjs").template({
        preset: a.preset,
        prefill: json(a.prefill),
        suggestions: json(a.suggestions),
        out: a.out && path.resolve(a.out),
      });
      break;
    case "intake-apply":
      if (!a.answers) throw Error("--answers FILE が必要");
      result = require("./intake.cjs").apply(dir, json(a.answers));
      break;
    case "intake-residual":
      result = require("./intake.cjs").residual(dir);
      break;
    case "essence-baseline":
      result = require("./essence.cjs").baseline(dir, { request: a.request });
      break;
    case "essence-check":
      result = require("./essence.cjs").check(dir);
      break;
    case "essence-revise":
      result = require("./essence.cjs").revise(dir, { field: a.field, reason: a.reason });
      break;
    case "prompts":
      result = prompts(dir);
      break;
    case "analysis-template":
      if (!a.sources) throw Error("--sources JSON が必要");
      result = require("./analysis.cjs").template(dir, P.read(a.sources));
      break;
    case "analysis-seal":
      result = require("./analysis.cjs").seal(dir);
      break;
    case "analysis-validate":
      result = require("./analysis.cjs").validate(dir);
      break;
    case "analysis-review-template":
      result = require("./analysis.cjs").reviewTemplate(dir);
      break;
    case "analysis-review-validate":
      // 評価者の検査は読取専用。FIXは呼出側の再発行・render・finalizeで記録する。
      result = require("./analysis.cjs").validateReview(dir);
      break;
    case "validate":
      result = P.validate(P.load(dir));
      break;
    case "render":
      result = await require("./render.cjs").render(dir, a.id);
      break;
    case "verify":
      result = require("./checks.cjs").verify(dir);
      break;
    case "pilot-review-template":
      result = { file: require("./checks.cjs").pilotReviewTemplate(dir) };
      break;
    case "review-template":
      result = { file: require("./checks.cjs").reviewTemplate(dir) };
      break;
    case "cycle-status":
      result = require("./checks.cjs").cycleStatus(dir);
      break;
    case "finalize":
      result = require("./checks.cjs").finalize(dir);
      break;
    case "learn-record":
      result = require("./learn.cjs").record(dir);
      break;
    case "learn-report":
      result = require("./learn.cjs").report({ minCases, preset: a.preset });
      break;
    case "learn-suggest":
      result = require("./learn.cjs").suggest({ minCases, preset: a.preset });
      break;
    default:
      throw Error("未対応command: " + a.command);
  }
  console.log(JSON.stringify(result, null, 2));
  if (result?.fail) process.exitCode = 1;
  return result;
}
if (require.main === module)
  main().catch((e) => {
    console.error(e.message);
    process.exitCode = 1;
  });
module.exports = { main, args, doctor, prompts };
