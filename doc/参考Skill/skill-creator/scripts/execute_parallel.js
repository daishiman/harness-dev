#!/usr/bin/env node
/**
 * 並列実行スクリプト
 * 用途: 複数スキルの同時実行と結果集約
 */

import { parseArgs } from 'node:util';
import { readFile } from 'node:fs/promises';
import { resolve } from 'node:path';
import { EXIT_CODES } from './utils.js';

// ====================
// 引数解析
// ====================
const { values: args } = parseArgs({
  options: {
    config: { type: 'string', short: 'c' },
    input: { type: 'string', short: 'i' },
    'dry-run': { type: 'boolean', default: false },
    verbose: { type: 'boolean', short: 'v', default: false },
    help: { type: 'boolean', short: 'h', default: false },
  },
});

if (args.help) {
  console.log(`
Usage: execute_parallel.js [options]

Options:
  -c, --config <path>   並列実行定義ファイル（JSON）
  -i, --input <json>    入力データ（JSON文字列）
  --dry-run             実行せずに確認
  -v, --verbose         詳細ログを出力
  -h, --help            ヘルプを表示
`);
  process.exit(EXIT_CODES.SUCCESS);
}

// ====================
// ユーティリティ
// ====================
function log(level, message, data = {}) {
  if (level === 'debug' && !args.verbose) return;
  const timestamp = new Date().toISOString();
  console.log(JSON.stringify({ timestamp, level, message, ...data }));
}

function sleep(ms) {
  return new Promise(resolve => setTimeout(resolve, ms));
}

// ====================
// 並列実行エンジン
// ====================
class ParallelExecutor {
  constructor(config, inputData) {
    this.config = config;
    this.inputData = inputData;
    this.results = [];
  }

  async execute() {
    log('info', 'Starting parallel execution', { name: this.config.name });

    const { tasks, config: execConfig = {} } = this.config;
    const maxConcurrency = execConfig.max_concurrency || 10;
    const failFast = execConfig.fail_fast || false;
    const timeout = execConfig.timeout || 300000; // 5分

    // タスクをチャンクに分割して同時実行数を制御
    const chunks = this.chunkArray(tasks, maxConcurrency);

    const startTime = Date.now();
    let hasError = false;

    for (const chunk of chunks) {
      if (hasError && failFast) break;
      if (Date.now() - startTime > timeout) {
        throw new Error('Parallel execution timed out');
      }

      const chunkResults = await Promise.allSettled(
        chunk.map(task => this.executeTask(task))
      );

      for (let i = 0; i < chunkResults.length; i++) {
        const result = chunkResults[i];
        const task = chunk[i];

        if (result.status === 'fulfilled') {
          this.results.push({
            id: task.id,
            status: 'success',
            output: result.value,
          });
        } else {
          this.results.push({
            id: task.id,
            status: 'failed',
            error: result.reason?.message || 'Unknown error',
          });

          if (task.required !== false && failFast) {
            hasError = true;
          }
        }
      }
    }

    // 結果を集約
    const aggregated = this.aggregate();
    log('info', 'Parallel execution completed', {
      name: this.config.name,
      total: tasks.length,
      success: this.results.filter(r => r.status === 'success').length,
      failed: this.results.filter(r => r.status === 'failed').length,
    });

    return aggregated;
  }

  chunkArray(array, size) {
    const chunks = [];
    for (let i = 0; i < array.length; i += size) {
      chunks.push(array.slice(i, i + size));
    }
    return chunks;
  }

  async executeTask(task) {
    log('info', 'Executing task', { taskId: task.id, skill: task.skill });

    const taskTimeout = task.timeout || 30000;
    const retryConfig = this.config.config?.retry || {};

    // リトライロジック
    let lastError;
    const maxAttempts = retryConfig.enabled ? (retryConfig.max_attempts || 1) : 1;

    for (let attempt = 1; attempt <= maxAttempts; attempt++) {
      try {
        if (args['dry-run']) {
          log('info', 'Dry run - would execute task', { taskId: task.id });
          return { dryRun: true, taskId: task.id };
        }

        // タイムアウト付き実行
        const result = await Promise.race([
          this.runTask(task),
          new Promise((_, reject) =>
            setTimeout(() => reject(new Error('Task timeout')), taskTimeout)
          ),
        ]);

        log('info', 'Task completed', { taskId: task.id, attempt });
        return result;
      } catch (err) {
        lastError = err;
        log('warn', 'Task attempt failed', {
          taskId: task.id,
          attempt,
          error: err.message
        });

        if (attempt < maxAttempts) {
          await sleep(retryConfig.delay || 1000);
        }
      }
    }

    throw lastError;
  }

  async runTask(task) {
    // 実際のスキル実行（ここでは模擬）
    // 実際の実装では、スキルを動的にロードして実行
    return { executed: true, taskId: task.id, args: task.args };
  }

  aggregate() {
    const { aggregation = {} } = this.config;
    const strategy = aggregation.strategy || 'all';
    const includeFailed = aggregation.include_failed || false;

    const successResults = this.results.filter(r => r.status === 'success');
    const targetResults = includeFailed ? this.results : successResults;

    switch (strategy) {
      case 'all':
        return targetResults;

      case 'merge':
        const mergeStrategy = aggregation.merge_strategy || 'shallow';
        return this.mergeResults(targetResults, mergeStrategy);

      case 'first':
        return targetResults[0] || null;

      case 'any':
        return successResults[0] || null;

      default:
        return targetResults;
    }
  }

  mergeResults(results, strategy) {
    if (results.length === 0) return {};

    const outputs = results.map(r => r.output || {});

    switch (strategy) {
      case 'shallow':
        return Object.assign({}, ...outputs);

      case 'deep':
        return this.deepMerge(outputs);

      case 'array':
        // 同じキーの値を配列に統合
        const merged = {};
        for (const output of outputs) {
          for (const [key, value] of Object.entries(output)) {
            if (!merged[key]) merged[key] = [];
            if (Array.isArray(value)) {
              merged[key].push(...value);
            } else {
              merged[key].push(value);
            }
          }
        }
        return merged;

      default:
        return Object.assign({}, ...outputs);
    }
  }

  deepMerge(objects) {
    const result = {};
    for (const obj of objects) {
      for (const [key, value] of Object.entries(obj)) {
        if (typeof value === 'object' && value !== null && !Array.isArray(value)) {
          result[key] = this.deepMerge([result[key] || {}, value]);
        } else {
          result[key] = value;
        }
      }
    }
    return result;
  }
}

// ====================
// メイン処理
// ====================
async function main() {
  if (!args.config) {
    console.error('Error: --config is required');
    process.exit(EXIT_CODES.ARGS_ERROR);
  }

  // 設定を読み込み
  const configPath = resolve(args.config);
  const configContent = await readFile(configPath, 'utf-8');
  const config = JSON.parse(configContent);

  // 入力データを解析
  const inputData = args.input ? JSON.parse(args.input) : {};

  // 並列実行
  const executor = new ParallelExecutor(config, inputData);
  const results = await executor.execute();

  console.log(JSON.stringify({ success: true, results }, null, 2));
}

main().catch(err => {
  console.error(JSON.stringify({ success: false, error: err.message }));
  process.exit(EXIT_CODES.ERROR);
});
