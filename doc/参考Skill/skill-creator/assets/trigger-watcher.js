#!/usr/bin/env node
/**
 * ファイル監視トリガーテンプレート
 * 用途: ファイル変更を検知してスキルを起動
 */

import { watch } from 'node:fs';
import { readFile } from 'node:fs/promises';
import { resolve, basename } from 'node:path';
import { spawn } from 'node:child_process';

// ====================
// 設定
// ====================
const CONFIG = {
  // 監視対象パス（glob対応したい場合は chokidar を使用）
  watchPaths: ['{{watch_paths}}'],  // 例: ['./data/*.csv', './input/*.json']

  // 監視イベント
  events: ['{{events}}'],  // 例: ['change', 'rename']

  // 実行するスキル
  skillPath: '{{skill_path}}',

  // デバウンス時間（ms）
  debounce: {{debounce_ms}},  // 例: 1000

  // 無視パターン
  ignorePatterns: [
    /node_modules/,
    /\.git/,
    /\.DS_Store/,
    /~$/,  // 一時ファイル
  ],
};

// ====================
// 状態管理
// ====================
let debounceTimer = null;
let pendingEvents = [];

// ====================
// ヘルパー関数
// ====================
function log(level, message, data = {}) {
  const timestamp = new Date().toISOString();
  console.log(JSON.stringify({ timestamp, level, message, ...data }));
}

function shouldIgnore(filename) {
  return CONFIG.ignorePatterns.some(pattern => pattern.test(filename));
}

async function executeSkill(eventData) {
  return new Promise((resolve, reject) => {
    log('info', 'Executing skill', { skill: CONFIG.skillPath, event: eventData });

    const child = spawn('node', [CONFIG.skillPath], {
      env: {
        ...process.env,
        TRIGGER_EVENT: JSON.stringify(eventData),
      },
      stdio: ['pipe', 'pipe', 'pipe'],
    });

    let stdout = '';
    let stderr = '';

    child.stdout.on('data', (data) => { stdout += data; });
    child.stderr.on('data', (data) => { stderr += data; });

    child.on('close', (code) => {
      if (code === 0) {
        log('info', 'Skill completed successfully', { stdout: stdout.trim() });
        resolve({ success: true, stdout, stderr });
      } else {
        log('error', 'Skill failed', { code, stderr: stderr.trim() });
        reject(new Error(`Skill exited with code ${code}`));
      }
    });

    child.on('error', (err) => {
      log('error', 'Failed to execute skill', { error: err.message });
      reject(err);
    });
  });
}

function handleEvent(eventType, filename) {
  if (shouldIgnore(filename)) {
    log('debug', 'Ignoring file', { filename });
    return;
  }

  log('info', 'File event detected', { eventType, filename });

  // イベントをキューに追加
  pendingEvents.push({
    type: eventType,
    filename,
    timestamp: Date.now(),
  });

  // デバウンス処理
  if (debounceTimer) {
    clearTimeout(debounceTimer);
  }

  debounceTimer = setTimeout(async () => {
    const events = [...pendingEvents];
    pendingEvents = [];

    try {
      await executeSkill({
        events,
        triggeredAt: new Date().toISOString(),
      });
    } catch (err) {
      log('error', 'Skill execution failed', { error: err.message });
    }
  }, CONFIG.debounce);
}

// ====================
// メイン処理
// ====================
function startWatching() {
  log('info', 'Starting file watcher', {
    paths: CONFIG.watchPaths,
    events: CONFIG.events,
    debounce: CONFIG.debounce,
  });

  const watchers = [];

  for (const watchPath of CONFIG.watchPaths) {
    const resolvedPath = resolve(watchPath);

    try {
      const watcher = watch(resolvedPath, { recursive: true }, (eventType, filename) => {
        if (filename && CONFIG.events.includes(eventType)) {
          handleEvent(eventType, filename);
        }
      });

      watcher.on('error', (err) => {
        log('error', 'Watcher error', { path: resolvedPath, error: err.message });
      });

      watchers.push(watcher);
      log('info', 'Watching path', { path: resolvedPath });
    } catch (err) {
      log('error', 'Failed to watch path', { path: resolvedPath, error: err.message });
    }
  }

  // Graceful shutdown
  process.on('SIGINT', () => {
    log('info', 'Shutting down...');
    watchers.forEach(w => w.close());
    process.exit(0);
  });

  process.on('SIGTERM', () => {
    log('info', 'Shutting down...');
    watchers.forEach(w => w.close());
    process.exit(0);
  });
}

// ====================
// エントリポイント
// ====================
startWatching();
