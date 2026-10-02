// ヘッドレスChromeの起動と DevTools Protocol 接続。外部依存を使わず Node の WebSocket だけで話す。
// 呼び出し側は globalThis.WebSocket を用意しておく（Node 20 は --experimental-websocket）。

import { spawn } from 'node:child_process'
import { access, mkdtemp, readFile, rm } from 'node:fs/promises'
import { constants } from 'node:fs'
import { tmpdir } from 'node:os'
import { join } from 'node:path'
import { setTimeout as delay } from 'node:timers/promises'

const chromeCandidates = [
  process.env.CHROME_BIN,
  '/Applications/Google Chrome.app/Contents/MacOS/Google Chrome',
  '/Applications/Chromium.app/Contents/MacOS/Chromium',
  '/usr/bin/google-chrome',
  '/usr/bin/google-chrome-stable',
  '/usr/bin/chromium',
  '/usr/bin/chromium-browser'
].filter(Boolean)

export async function findChrome(purpose) {
  for (const candidate of chromeCandidates) {
    try {
      await access(candidate, constants.X_OK)
      return candidate
    } catch {}
  }
  throw new Error(`Chrome/Chromium was not found. Set CHROME_BIN to run ${purpose}.`)
}

function connect(webSocketUrl) {
  return new Promise((resolveConnect, rejectConnect) => {
    const socket = new WebSocket(webSocketUrl)
    const pending = new Map()
    const eventWaiters = new Map()
    let nextId = 1
    socket.addEventListener('open', () => {
      resolveConnect({
        send(method, params = {}) {
          return new Promise((resolveCommand, rejectCommand) => {
            const id = nextId++
            pending.set(id, { resolveCommand, rejectCommand })
            socket.send(JSON.stringify({ id, method, params }))
          })
        },
        waitFor(method) {
          return new Promise((resolveEvent) => {
            const queue = eventWaiters.get(method) || []
            queue.push(resolveEvent)
            eventWaiters.set(method, queue)
          })
        },
        close() { socket.close() }
      })
    }, { once: true })
    socket.addEventListener('error', () => rejectConnect(new Error(`Could not connect to ${webSocketUrl}`)), { once: true })
    socket.addEventListener('message', (event) => {
      const message = JSON.parse(String(event.data))
      if (message.id) {
        const command = pending.get(message.id)
        if (!command) return
        pending.delete(message.id)
        if (message.error) command.rejectCommand(new Error(`${message.error.message} (${message.error.code})`))
        else command.resolveCommand(message.result)
        return
      }
      const queue = eventWaiters.get(message.method)
      const resolveEvent = queue?.shift()
      if (resolveEvent) resolveEvent(message.params)
    })
  })
}

async function devToolsPort(profileDir, errors) {
  const portFile = join(profileDir, 'DevToolsActivePort')
  for (let attempt = 0; attempt < 120; attempt += 1) {
    try {
      const [port] = (await readFile(portFile, 'utf8')).trim().split(/\r?\n/)
      if (port) return port
    } catch {}
    await delay(100)
  }
  throw new Error(`Chrome DevTools did not start: ${errors.join('').slice(-1600)}`)
}

// 使い捨てプロファイルで Chrome を起動し、空タブに接続した client を返す。close() で後始末まで行う。
export async function launchChrome({ purpose, tempPrefix }) {
  const chrome = await findChrome(purpose)
  const tempRoot = await mkdtemp(join(tmpdir(), tempPrefix))
  const profileDir = join(tempRoot, 'profile')
  const chromeErrors = []
  const chromeProcess = spawn(chrome, [
    '--headless=new', '--disable-gpu', '--no-sandbox', '--no-first-run', '--disable-background-networking',
    '--disable-component-update', '--allow-file-access-from-files', '--remote-allow-origins=*',
    '--remote-debugging-port=0', `--user-data-dir=${profileDir}`, 'about:blank'
  ], { stdio: ['ignore', 'ignore', 'pipe'] })
  chromeProcess.stderr.on('data', (chunk) => chromeErrors.push(String(chunk)))
  let client
  const close = async () => {
    client?.close()
    // Chrome は終了処理中もプロフィールへ書き込むため、終了を待ってから消す（待ちすぎないよう上限付き）。
    if (chromeProcess.exitCode === null) {
      const exited = new Promise((resolve) => chromeProcess.once('exit', resolve))
      chromeProcess.kill('SIGTERM')
      await Promise.race([exited, new Promise((resolve) => setTimeout(resolve, 2000))])
    }
    await rm(tempRoot, { recursive: true, force: true, maxRetries: 5, retryDelay: 100 })
  }
  try {
    const port = await devToolsPort(profileDir, chromeErrors)
    const targetResponse = await fetch(`http://127.0.0.1:${port}/json/new?about%3Ablank`, { method: 'PUT' })
    if (!targetResponse.ok) throw new Error(`Could not create Chrome target: ${targetResponse.status}`)
    const target = await targetResponse.json()
    client = await connect(target.webSocketDebuggerUrl)
    return { client, close }
  } catch (error) {
    await close()
    throw error
  }
}

export async function evaluate(client, expression) {
  const result = await client.send('Runtime.evaluate', { expression, awaitPromise: true, returnByValue: true })
  if (result.exceptionDetails) throw new Error(result.exceptionDetails.exception?.description || result.exceptionDetails.text || 'Browser evaluation failed')
  return result.result.value
}
