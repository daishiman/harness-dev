#!/usr/bin/env node
/**
 * スキルチェーン実行スクリプト
 * 用途: 複数スキルの連鎖実行（A→B→C）
 */

import { parseArgs } from 'node:util';
import { readFile } from 'node:fs/promises';
import { resolve, dirname } from 'node:path';
import { fileURLToPath } from 'node:url';
import { EXIT_CODES } from './utils.js';

const __dirname = dirname(fileURLToPath(import.meta.url));

// ====================
// 引数解析
// ====================
const { values: args } = parseArgs({
  options: {
    chain: { type: 'string', short: 'c' },
    input: { type: 'string', short: 'i' },
    'dry-run': { type: 'boolean', default: false },
    verbose: { type: 'boolean', short: 'v', default: false },
    help: { type: 'boolean', short: 'h', default: false },
  },
});

if (args.help) {
  console.log(`
Usage: execute_chain.js [options]

Options:
  -c, --chain <path>    チェーン定義ファイル（JSON/YAML）
  -i, --input <json>    入力データ（JSON文字列）
  --dry-run             実行せずにフローを確認
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

function resolveTemplate(template, context) {
  if (typeof template !== 'string') return template;
  return template.replace(/\{\{([^}]+)\}\}/g, (_, path) => {
    const value = path.split('.').reduce((obj, key) => obj?.[key], context);
    return value !== undefined ? JSON.stringify(value) : `{{${path}}}`;
  });
}

// ====================
// チェーン実行エンジン
// ====================
class ChainExecutor {
  constructor(chainDef, inputData) {
    this.chain = chainDef;
    this.context = {
      input: inputData,
      trigger: { data: inputData },
      context: chainDef.context || {},
      env: process.env,
    };
    this.results = {};
  }

  async execute() {
    log('info', 'Starting chain execution', { name: this.chain.name });

    const steps = this.chain.steps || this.chain.flow || [];

    for (const step of steps) {
      // 依存関係チェック
      if (step.depends_on) {
        for (const dep of step.depends_on) {
          if (!this.results[dep]) {
            throw new Error(`Dependency not satisfied: ${dep}`);
          }
        }
      }

      // 条件チェック
      if (step.condition) {
        const conditionMet = this.evaluateCondition(step.condition);
        if (!conditionMet) {
          log('info', 'Skipping step (condition not met)', { stepId: step.id });
          continue;
        }
      }

      // ステップ実行
      try {
        const result = await this.executeStep(step);
        this.results[step.id] = { status: 'success', output: result };
        this.context[step.id] = { output: result, status: 'success' };
      } catch (err) {
        log('error', 'Step failed', { stepId: step.id, error: err.message });
        this.results[step.id] = { status: 'failed', error: err.message };
        this.context[step.id] = { status: 'failed', error: err.message };

        // エラーハンドリング
        const errorHandling = this.chain.error_handling || {};
        if (errorHandling.on_step_error === 'abort') {
          throw new Error(`Chain aborted at step: ${step.id}`);
        }
      }
    }

    log('info', 'Chain execution completed', { name: this.chain.name });
    return this.results;
  }

  evaluateCondition(condition) {
    if (typeof condition === 'string') {
      const resolved = resolveTemplate(condition, this.context);
      try {
        // 安全な評価（実際の実装ではより安全な方法を使用）
        return Function(`"use strict"; return (${resolved})`)();
      } catch {
        return false;
      }
    }
    if (condition.expression) {
      return this.evaluateCondition(condition.expression);
    }
    return true;
  }

  async executeStep(step) {
    log('info', 'Executing step', { stepId: step.id, skill: step.skill });

    // 引数を解決
    const resolvedArgs = {};
    const inputMapping = step.input_mapping || step.args || {};

    for (const [key, template] of Object.entries(inputMapping)) {
      resolvedArgs[key] = JSON.parse(resolveTemplate(template, this.context));
    }

    if (args['dry-run']) {
      log('info', 'Dry run - would execute', {
        stepId: step.id,
        skill: step.skill,
        args: resolvedArgs
      });
      return { dryRun: true, args: resolvedArgs };
    }

    // 実際のスキル実行（ここでは模擬）
    // 実際の実装では、スキルを動的にロードして実行
    log('info', 'Step completed', { stepId: step.id });
    return { executed: true, args: resolvedArgs };
  }
}

// ====================
// メイン処理
// ====================
async function main() {
  if (!args.chain) {
    console.error('Error: --chain is required');
    process.exit(EXIT_CODES.ARGS_ERROR);
  }

  // チェーン定義を読み込み
  const chainPath = resolve(args.chain);
  const chainContent = await readFile(chainPath, 'utf-8');
  const chainDef = JSON.parse(chainContent);

  // 入力データを解析
  const inputData = args.input ? JSON.parse(args.input) : {};

  // チェーン実行
  const executor = new ChainExecutor(chainDef, inputData);
  const results = await executor.execute();

  console.log(JSON.stringify({ success: true, results }, null, 2));
}

main().catch(err => {
  console.error(JSON.stringify({ success: false, error: err.message }));
  process.exit(EXIT_CODES.ERROR);
});
