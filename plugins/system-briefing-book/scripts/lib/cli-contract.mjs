/**
 * スクリプト 5 本が共通で守る CLI の決まり (contract.md §7)。
 *
 * - 終了コード: 0=正常 / 1=検査で問題 / 2=使い方の誤り / 3=必要なツールがない
 * - stdout は JSON 1 個 (--quiet なら要約 1 行)。人向けのメッセージは stderr
 * - 使い方の誤りは {"status":"usage-error","message":...}、ツールが無いときは {"status":"tool-missing",...}
 *
 * 終わり方は process.exitCode に入れて自然に抜ける。macOS ではパイプへの書き込みが非同期なので、
 * process.exit() で急に止めると大きな JSON の後ろが切れることがある。
 */
import { realpathSync } from "node:fs";
import { fileURLToPath } from "node:url";

export const EXIT = Object.freeze({ OK: 0, FOUND: 1, USAGE: 2, TOOL: 3 });

/**
 * このファイルが node で直接起動されたか。テストが import したときは false。
 * Node は起動したファイルを実体のパスで読むので、argv[1] (リンクや /tmp を含むことがある) も実体にして比べる。
 */
export function isEntryPoint(importMetaUrl) {
  if (!process.argv[1]) return false;
  try {
    return realpathSync(process.argv[1]) === realpathSync(fileURLToPath(importMetaUrl));
  } catch {
    return false;
  }
}

/** 使い方の誤り (exit 2)。 */
export class UsageError extends Error {}

/** 必要なツールがない (exit 3)。 */
export class ToolMissing extends Error {}

/** Node 22 未満なら案内を出して exit 3。標準の WebSocket と fs の機能に 22 が要る。 */
export function requireNode22() {
  const major = Number(process.versions.node.split(".")[0]);
  if (major >= 22) return true;
  process.stderr.write(`Node.js 22 以上が必要です (今は ${process.versions.node})。setup.md の手順で入れ直してください\n`);
  process.stdout.write(`${JSON.stringify({ status: "tool-missing", message: `Node.js 22 以上が必要です (今は ${process.versions.node})` })}\n`);
  process.exitCode = EXIT.TOOL;
  return false;
}

/**
 * 引数を読む。spec は {name: "string" | "boolean" | "list"}。
 * list は次の "--" で始まる引数の手前までを集め、カンマ区切りも分ける (--only 01 02 / --only 01,02)。
 * 知らない名前・値の抜け・余った引数は UsageError。
 */
export function parseOptions(argv, spec, { positionals = 0 } = {}) {
  const options = {};
  const rest = [];
  for (let i = 0; i < argv.length; i += 1) {
    const arg = argv[i];
    if (!arg.startsWith("--")) {
      rest.push(arg);
      continue;
    }
    const eq = arg.indexOf("=");
    const name = eq === -1 ? arg.slice(2) : arg.slice(2, eq);
    const kind = spec[name];
    if (!kind) throw new UsageError(`知らない引数です: --${name}`);
    if (kind === "boolean") {
      if (eq !== -1) throw new UsageError(`--${name} に値は付けません`);
      options[name] = true;
      continue;
    }
    const values = [];
    if (eq !== -1) {
      values.push(arg.slice(eq + 1));
    } else if (kind === "string") {
      if (i + 1 >= argv.length || argv[i + 1].startsWith("--")) throw new UsageError(`--${name} の値がありません`);
      values.push(argv[(i += 1)]);
    } else {
      while (i + 1 < argv.length && !argv[i + 1].startsWith("--")) values.push(argv[(i += 1)]);
      if (!values.length) throw new UsageError(`--${name} の値がありません`);
    }
    if (kind === "string") {
      options[name] = values[0];
    } else {
      const split = values.flatMap((v) => v.split(",")).map((v) => v.trim()).filter(Boolean);
      options[name] = [...(options[name] || []), ...split];
    }
  }
  if (rest.length > positionals) throw new UsageError(`余分な引数があります: ${rest.slice(positionals).join(" ")}`);
  return { options, positionals: rest };
}

/** 結果を stdout に出す。quiet なら 1 行、そうでなければ字下げした JSON。 */
export function emitResult(result, quietLine = null) {
  process.stdout.write(quietLine === null ? `${JSON.stringify(result, null, 2)}\n` : `${quietLine}\n`);
}

/**
 * main を動かし、UsageError / ToolMissing を決まった JSON と終了コードにする。
 * main は終了コードを返す (Promise でもよい)。--help / -h なら usage を出して 0。
 */
export async function runCli(main, usage = "") {
  if (!requireNode22()) return;
  const argv = process.argv.slice(2);
  if (usage && (argv.includes("--help") || argv.includes("-h"))) {
    process.stdout.write(`${usage.trim()}\n`);
    process.exitCode = EXIT.OK;
    return;
  }
  try {
    process.exitCode = await main(argv);
  } catch (error) {
    if (error instanceof UsageError || error instanceof ToolMissing) {
      const usage = error instanceof UsageError;
      process.stderr.write(`${error.message}\n`);
      process.stdout.write(`${JSON.stringify({ status: usage ? "usage-error" : "tool-missing", message: error.message })}\n`);
      process.exitCode = usage ? EXIT.USAGE : EXIT.TOOL;
      return;
    }
    process.stderr.write(`${error?.stack || error}\n`);
    process.exitCode = EXIT.FOUND;
  }
}
