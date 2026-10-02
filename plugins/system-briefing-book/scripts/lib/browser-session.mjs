/**
 * Chrome / Edge を探して headless で起動し、Chrome DevTools Protocol (CDP) で動かす。
 *
 * npm のライブラリは使わない。Chrome を `--remote-debugging-port=0` で起動し、stderr に出る
 * `DevTools listening on ws://...` を読んで、Node 22 標準の WebSocket でつなぐ。
 * タブは Target.createTarget で開き、attachToTarget({flatten:true}) の sessionId を付けて命令を送る。
 *
 * 終わりは Browser.close。5 秒で終わらなければ kill し、一時プロファイルは再試行つきで消す。
 * Windows でも黒い窓を出さない (windowsHide) し、shell は通さない。
 */
import { spawn } from "node:child_process";
import { accessSync, constants, mkdtempSync, rmSync, statSync } from "node:fs";
import { homedir, tmpdir } from "node:os";
import path from "node:path";

import { ToolMissing } from "./cli-contract.mjs";

export const LAUNCH_FLAGS = Object.freeze([
  "--headless=new",
  "--remote-debugging-port=0",
  "--no-first-run",
  "--no-default-browser-check",
  "--hide-scrollbars",
  "--force-color-profile=srgb",
]);
// 初回起動やウイルス対策ソフトの検査で遅れる PC があるため、起動待ちは 1 回の命令と同じ 60 秒まで待つ
const LAUNCH_TIMEOUT_MS = 60_000;
const COMMAND_TIMEOUT_MS = 60_000;
const CLOSE_TIMEOUT_MS = 5_000;

function isFile(file) {
  try {
    return statSync(file).isFile();
  } catch {
    return false;
  }
}

/** PATH から実行できるファイルを探す (Windows は PATHEXT も試す)。 */
function whichSync(name, env, platform) {
  const dirs = String(env.PATH ?? env.Path ?? "").split(platform === "win32" ? ";" : ":").filter(Boolean);
  const exts = platform === "win32" ? String(env.PATHEXT || ".EXE;.CMD;.BAT").split(";").filter(Boolean) : [""];
  for (const dir of dirs) {
    for (const ext of exts) {
      const file = path.join(dir, name + ext);
      if (!isFile(file)) continue;
      if (platform === "win32") return file;
      try {
        accessSync(file, constants.X_OK);
        return file;
      } catch {
        // 実行できないファイルは飛ばす
      }
    }
  }
  return null;
}

/** ブラウザの候補を探す順に並べる (Mac → Windows → PATH)。 */
export function browserCandidates({ platform = process.platform, env = process.env, home = homedir() } = {}) {
  const found = [];
  if (platform === "darwin") {
    for (const app of ["Google Chrome", "Microsoft Edge", "Chromium"]) {
      found.push(`/Applications/${app}.app/Contents/MacOS/${app}`);
      found.push(path.join(home, "Applications", `${app}.app`, "Contents", "MacOS", app));
    }
  } else if (platform === "win32") {
    for (const key of ["ProgramFiles", "ProgramFiles(x86)", "LocalAppData"]) {
      const root = env[key] ?? env[key.toUpperCase()];
      if (!root) continue;
      found.push(path.win32.join(root, "Google", "Chrome", "Application", "chrome.exe"));
      found.push(path.win32.join(root, "Microsoft", "Edge", "Application", "msedge.exe"));
    }
  }
  for (const name of ["google-chrome", "google-chrome-stable", "chromium", "chromium-browser", "microsoft-edge", "msedge"]) {
    const hit = whichSync(name, env, platform);
    if (hit) found.push(hit);
  }
  return found;
}

/**
 * 使うブラウザを決める。--browser → 環境変数 BRIEFING_BROWSER → 候補の順。
 * 見つからなければ ToolMissing (exit 3)。
 */
export function findBrowser(explicit, { env = process.env, candidates = null } = {}) {
  const wanted = explicit || env.BRIEFING_BROWSER;
  if (wanted) {
    if (isFile(wanted)) return wanted;
    throw new ToolMissing(`指定されたブラウザが見つかりません: ${wanted}`);
  }
  for (const file of candidates ?? browserCandidates({ env })) {
    if (isFile(file)) return file;
  }
  throw new ToolMissing("Google Chrome か Microsoft Edge が見つかりません。入れるか --browser で場所を指定してください (setup.md)");
}

/** promise と時間切れの早いほう。時計は必ず止める (止めないと Node が終わらない)。 */
function withTimeout(promise, ms, message) {
  let timer;
  const timeout = new Promise((_, reject) => {
    timer = setTimeout(() => reject(new Error(message)), ms);
  });
  return Promise.race([promise, timeout]).finally(() => clearTimeout(timer));
}

function removeProfile(dir) {
  try {
    rmSync(dir, { recursive: true, force: true, maxRetries: 10, retryDelay: 200 });
  } catch (error) {
    process.stderr.write(`一時フォルダを消せませんでした (あとで消してください): ${dir} (${error.code || error.message})\n`);
  }
}

/** Chrome を起動して CDP につなぐ。 */
export async function launchBrowser(executable, { timeoutMs = LAUNCH_TIMEOUT_MS } = {}) {
  if (typeof WebSocket !== "function") {
    throw new ToolMissing(`この Node.js (${process.versions.node}) には WebSocket がありません。Node.js 22 以上を入れてください`);
  }
  const profile = mkdtempSync(path.join(tmpdir(), "briefing-browser-"));
  const child = spawn(executable, [...LAUNCH_FLAGS, `--user-data-dir=${profile}`, "about:blank"], {
    stdio: ["ignore", "ignore", "pipe"],
    windowsHide: true,
    shell: false,
  });
  let endpoint;
  try {
    endpoint = await withTimeout(
      new Promise((resolve, reject) => {
        let text = "";
        child.once("error", (error) => reject(new ToolMissing(`ブラウザを起動できません: ${executable} (${error.code || error.message})`)));
        child.once("exit", (code) => reject(new Error(`ブラウザがすぐに終わりました (終了コード ${code}): ${text.trim().slice(-300)}`)));
        child.stderr.on("data", (chunk) => {
          if (endpoint) return;
          text += chunk;
          const match = text.match(/DevTools listening on (ws:\/\/\S+)/);
          if (match) resolve(match[1]);
        });
      }),
      timeoutMs,
      `ブラウザが ${Math.round(timeoutMs / 1000)} 秒たっても起動しません: ${executable}`,
    );
  } catch (error) {
    child.kill("SIGKILL");
    removeProfile(profile);
    throw error;
  }
  child.stderr.resume(); // 読み続けないと stderr が詰まって Chrome が止まる
  const session = new BrowserSession(child, profile);
  try {
    await session.connect(endpoint);
  } catch (error) {
    await session.close();
    throw error;
  }
  return session;
}

export class BrowserSession {
  #ws = null;
  #nextId = 0;
  #pending = new Map();
  #listeners = new Set();
  #closed = false;

  constructor(child, profile) {
    this.child = child;
    this.profile = profile;
    this.exited = new Promise((resolve) => {
      if (child.exitCode !== null || child.signalCode !== null) resolve();
      else child.once("exit", () => resolve());
    });
  }

  connect(url) {
    return withTimeout(
      new Promise((resolve, reject) => {
        const ws = new WebSocket(url);
        ws.onopen = () => resolve();
        ws.onerror = (event) => reject(new Error(`ブラウザにつなげません: ${event?.message || url}`));
        ws.onclose = () => this.#failAll(new Error("ブラウザとの接続が切れました"));
        ws.onmessage = (event) => this.#receive(event.data);
        this.#ws = ws;
      }),
      LAUNCH_TIMEOUT_MS,
      "ブラウザにつなげません (時間切れ)",
    );
  }

  #receive(data) {
    let message;
    try {
      message = JSON.parse(typeof data === "string" ? data : Buffer.from(data).toString("utf8"));
    } catch {
      return;
    }
    if (message.id !== undefined) {
      const waiter = this.#pending.get(message.id);
      if (!waiter) return;
      this.#pending.delete(message.id);
      if (message.error) waiter.reject(new Error(`${waiter.method}: ${message.error.message}`));
      else waiter.resolve(message.result ?? {});
      return;
    }
    for (const listener of this.#listeners) listener(message);
  }

  #failAll(error) {
    for (const waiter of this.#pending.values()) waiter.reject(error);
    this.#pending.clear();
  }

  /** CDP の命令を送り、結果を待つ。sessionId を付けるとそのタブへの命令になる。 */
  send(method, params = {}, sessionId = undefined, timeoutMs = COMMAND_TIMEOUT_MS) {
    if (!this.#ws || this.#ws.readyState !== 1) return Promise.reject(new Error(`${method}: ブラウザにつながっていません`));
    const id = (this.#nextId += 1);
    const reply = new Promise((resolve, reject) => this.#pending.set(id, { resolve, reject, method }));
    this.#ws.send(JSON.stringify(sessionId ? { id, method, params, sessionId } : { id, method, params }));
    return withTimeout(reply, timeoutMs, `${method}: ${Math.round(timeoutMs / 1000)} 秒たっても返事がありません`).finally(
      () => this.#pending.delete(id),
    );
  }

  /** イベントを 1 つ待つ。待ち始めてから命令を送ること (順番を逆にすると取りこぼす)。 */
  waitForEvent(method, sessionId, timeoutMs = COMMAND_TIMEOUT_MS) {
    let listener;
    const event = new Promise((resolve) => {
      listener = (message) => {
        if (message.method === method && message.sessionId === sessionId) resolve(message.params ?? {});
      };
      this.#listeners.add(listener);
    });
    return withTimeout(event, timeoutMs, `${method} を待ちましたが来ませんでした`).finally(() => this.#listeners.delete(listener));
  }

  /** 新しいタブを開く。width x height (CSS px) で deviceScaleFactor = scale。 */
  async newPage({ width, height, scale = 1 }) {
    const { targetId } = await this.send("Target.createTarget", { url: "about:blank" });
    const { sessionId } = await this.send("Target.attachToTarget", { targetId, flatten: true });
    const page = new BrowserPage(this, targetId, sessionId);
    await page.send("Page.enable");
    await page.send("Runtime.enable");
    await page.send("Emulation.setDeviceMetricsOverride", { width, height, deviceScaleFactor: scale, mobile: false });
    return page;
  }

  /** ブラウザを閉じる。5 秒で終わらなければ kill。一時プロファイルを消す。何度呼んでもよい。 */
  async close() {
    if (this.#closed) return;
    this.#closed = true;
    if (this.#ws && this.#ws.readyState === 1) {
      try {
        await this.send("Browser.close", {}, undefined, CLOSE_TIMEOUT_MS);
      } catch {
        // 返事が無くても下で終わりを待つ
      }
    }
    try {
      await withTimeout(this.exited, CLOSE_TIMEOUT_MS, "close");
    } catch {
      this.child.kill("SIGKILL");
      await withTimeout(this.exited, CLOSE_TIMEOUT_MS, "kill").catch(() => {});
    }
    try {
      this.#ws?.close();
    } catch {
      // すでに閉じている
    }
    this.child.stderr?.destroy();
    removeProfile(this.profile);
  }
}

export class BrowserPage {
  constructor(session, targetId, sessionId) {
    this.session = session;
    this.targetId = targetId;
    this.sessionId = sessionId;
  }

  send(method, params = {}, timeoutMs = COMMAND_TIMEOUT_MS) {
    return this.session.send(method, params, this.sessionId, timeoutMs);
  }

  /** url を開き、load と document.fonts.ready を待つ。 */
  async goto(url, timeoutMs = COMMAND_TIMEOUT_MS) {
    const loaded = this.session.waitForEvent("Page.loadEventFired", this.sessionId, timeoutMs);
    loaded.catch(() => {}); // navigate が先に失敗したときに未処理の reject にしない
    const result = await this.send("Page.navigate", { url }, timeoutMs);
    if (result.errorText) throw new Error(`ページを開けません: ${result.errorText}`);
    await loaded;
    await this.evaluate("document.fonts.ready.then(() => true)");
  }

  /** 式を評価して値 (JSON にできるもの) を返す。Promise なら待つ。 */
  async evaluate(expression, { timeoutMs = COMMAND_TIMEOUT_MS } = {}) {
    const result = await this.send("Runtime.evaluate", { expression, awaitPromise: true, returnByValue: true }, timeoutMs);
    if (result.exceptionDetails) {
      const detail = result.exceptionDetails;
      throw new Error(`ブラウザの中でエラー: ${detail.exception?.description || detail.text}`);
    }
    return result.result?.value;
  }

  /** 画面を撮る。clip は CSS px。出来上がりの大きさは clip × deviceScaleFactor × clip.scale。 */
  async screenshot({ clip, format = "png", quality } = {}) {
    const params = { format, captureBeyondViewport: false, fromSurface: true };
    if (clip) params.clip = { scale: 1, ...clip };
    if (quality !== undefined && format !== "png") params.quality = quality;
    const { data } = await this.send("Page.captureScreenshot", params);
    return Buffer.from(data, "base64");
  }

  async close() {
    try {
      await this.session.send("Target.closeTarget", { targetId: this.targetId }, undefined, CLOSE_TIMEOUT_MS);
    } catch {
      // ブラウザごと閉じるので無視してよい
    }
  }
}
