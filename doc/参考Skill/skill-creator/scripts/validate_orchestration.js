#!/usr/bin/env node
/**
 * オーケストレーション検証スクリプト
 * 用途: オーケストレーション定義の構文・整合性チェック
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
    config: { type: 'string', short: 'c' },
    schema: { type: 'string', short: 's' },
    verbose: { type: 'boolean', short: 'v', default: false },
    help: { type: 'boolean', short: 'h', default: false },
  },
});

if (args.help) {
  console.log(`
Usage: validate_orchestration.js [options]

Options:
  -c, --config <path>   オーケストレーション定義ファイル
  -s, --schema <path>   検証用スキーマ（オプション）
  -v, --verbose         詳細ログを出力
  -h, --help            ヘルプを表示
`);
  process.exit(EXIT_CODES.SUCCESS);
}

// ====================
// 検証ルール
// ====================
const validators = {
  // 基本構造の検証
  validateStructure(config) {
    const errors = [];
    const warnings = [];

    if (!config.name) {
      errors.push('Missing required field: name');
    }

    if (!config.flow && !config.steps && !config.tasks) {
      errors.push('Missing required field: flow, steps, or tasks');
    }

    return { errors, warnings };
  },

  // フロー/ステップの検証
  validateFlow(config) {
    const errors = [];
    const warnings = [];
    const steps = config.flow || config.steps || [];
    const stepIds = new Set();

    for (const step of steps) {
      // ID重複チェック
      if (stepIds.has(step.id)) {
        errors.push(`Duplicate step ID: ${step.id}`);
      }
      stepIds.add(step.id);

      // 必須フィールドチェック
      if (!step.id) {
        errors.push('Step missing required field: id');
      }
      if (!step.skill) {
        errors.push(`Step ${step.id}: missing required field: skill`);
      }
    }

    // 依存関係の検証
    for (const step of steps) {
      if (step.depends_on) {
        for (const dep of step.depends_on) {
          if (!stepIds.has(dep)) {
            errors.push(`Step ${step.id}: unknown dependency: ${dep}`);
          }
        }
      }
    }

    // 循環依存の検証
    const cyclicDeps = this.detectCyclicDependencies(steps);
    if (cyclicDeps.length > 0) {
      errors.push(`Cyclic dependencies detected: ${cyclicDeps.join(' -> ')}`);
    }

    return { errors, warnings };
  },

  // 循環依存の検出
  detectCyclicDependencies(steps) {
    const graph = new Map();
    for (const step of steps) {
      graph.set(step.id, step.depends_on || []);
    }

    const visited = new Set();
    const recStack = new Set();
    const path = [];

    const dfs = (node) => {
      if (recStack.has(node)) {
        const cycleStart = path.indexOf(node);
        return [...path.slice(cycleStart), node];
      }
      if (visited.has(node)) return [];

      visited.add(node);
      recStack.add(node);
      path.push(node);

      for (const neighbor of (graph.get(node) || [])) {
        const cycle = dfs(neighbor);
        if (cycle.length > 0) return cycle;
      }

      path.pop();
      recStack.delete(node);
      return [];
    };

    for (const step of steps) {
      const cycle = dfs(step.id);
      if (cycle.length > 0) return cycle;
    }

    return [];
  },

  // 並列実行の検証
  validateParallel(config) {
    const errors = [];
    const warnings = [];
    const parallel = config.parallel || [];

    for (const group of parallel) {
      if (!group.id) {
        errors.push('Parallel group missing required field: id');
      }
      if (!group.skills || group.skills.length < 2) {
        errors.push(`Parallel group ${group.id}: must have at least 2 skills`);
      }

      // 集約戦略の検証
      const validStrategies = ['all', 'any', 'first', 'merge'];
      if (group.aggregate && !validStrategies.includes(group.aggregate)) {
        errors.push(`Parallel group ${group.id}: invalid aggregate strategy: ${group.aggregate}`);
      }
    }

    return { errors, warnings };
  },

  // スケジュールの検証
  validateSchedule(config) {
    const errors = [];
    const warnings = [];
    const schedule = config.schedule;

    if (!schedule) return { errors, warnings };

    if (schedule.type === 'cron' && !schedule.cron) {
      errors.push('Schedule type is cron but cron expression is missing');
    }

    if (schedule.cron) {
      // 簡易的なcron式検証
      const cronParts = schedule.cron.split(' ');
      if (cronParts.length !== 5) {
        errors.push(`Invalid cron expression: ${schedule.cron} (expected 5 parts)`);
      }
    }

    if (!schedule.timezone) {
      warnings.push('No timezone specified for schedule, will use system default');
    }

    return { errors, warnings };
  },

  // トリガーの検証
  validateTriggers(config) {
    const errors = [];
    const warnings = [];
    const triggers = config.triggers || [];

    const validTypes = ['webhook', 'file_watch', 'git', 'http_poll', 'websocket', 'manual'];

    for (const trigger of triggers) {
      if (!trigger.type) {
        errors.push('Trigger missing required field: type');
      } else if (!validTypes.includes(trigger.type)) {
        errors.push(`Invalid trigger type: ${trigger.type}`);
      }

      // Webhook固有の検証
      if (trigger.type === 'webhook') {
        if (!trigger.path && !trigger.webhook?.path) {
          errors.push('Webhook trigger missing required field: path');
        }
      }

      // ファイル監視固有の検証
      if (trigger.type === 'file_watch') {
        if (!trigger.paths && !trigger.file_watch?.paths) {
          errors.push('File watch trigger missing required field: paths');
        }
      }
    }

    return { errors, warnings };
  },

  // エラーハンドリングの検証
  validateErrorHandling(config) {
    const errors = [];
    const warnings = [];
    const errorHandling = config.on_error || config.error_handling;

    if (!errorHandling) {
      warnings.push('No error handling defined');
      return { errors, warnings };
    }

    const validStrategies = ['abort', 'retry', 'skip', 'fallback', 'continue'];
    const strategy = errorHandling.strategy || errorHandling.on_step_error;

    if (strategy && !validStrategies.includes(strategy)) {
      errors.push(`Invalid error handling strategy: ${strategy}`);
    }

    if (strategy === 'fallback' && !errorHandling.fallback_skill && !errorHandling.fallback_step) {
      errors.push('Fallback strategy specified but no fallback_skill or fallback_step defined');
    }

    return { errors, warnings };
  },

  // テンプレート変数の検証
  validateTemplateVariables(config) {
    const errors = [];
    const warnings = [];
    const steps = config.flow || config.steps || [];
    const stepIds = new Set(steps.map(s => s.id));

    const templatePattern = /\{\{([^}]+)\}\}/g;

    for (const step of steps) {
      const argsStr = JSON.stringify(step.args || step.input_mapping || {});
      let match;

      while ((match = templatePattern.exec(argsStr)) !== null) {
        const varPath = match[1];
        const parts = varPath.split('.');
        const root = parts[0];

        // 参照先が有効かチェック
        if (stepIds.has(root)) {
          // 前のステップを参照している場合、依存関係があるかチェック
          if (!step.depends_on?.includes(root)) {
            const stepIndex = steps.findIndex(s => s.id === step.id);
            const refIndex = steps.findIndex(s => s.id === root);
            if (refIndex >= stepIndex) {
              warnings.push(`Step ${step.id}: references ${root} but no explicit dependency`);
            }
          }
        }
      }
    }

    return { errors, warnings };
  },
};

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

  // 全バリデーターを実行
  const allErrors = [];
  const allWarnings = [];

  for (const [name, validator] of Object.entries(validators)) {
    if (typeof validator === 'function') {
      const { errors, warnings } = validator.call(validators, config);
      allErrors.push(...errors.map(e => `[${name}] ${e}`));
      allWarnings.push(...warnings.map(w => `[${name}] ${w}`));
    }
  }

  // 結果を出力
  const result = {
    valid: allErrors.length === 0,
    errors: allErrors,
    warnings: allWarnings,
    summary: {
      errorCount: allErrors.length,
      warningCount: allWarnings.length,
    },
  };

  if (args.verbose) {
    console.log(JSON.stringify(result, null, 2));
  } else {
    if (result.valid) {
      console.log('✅ Orchestration definition is valid');
      if (allWarnings.length > 0) {
        console.log(`⚠️  ${allWarnings.length} warning(s):`);
        allWarnings.forEach(w => console.log(`   - ${w}`));
      }
    } else {
      console.log('❌ Orchestration definition has errors:');
      allErrors.forEach(e => console.log(`   - ${e}`));
    }
  }

  process.exit(result.valid ? EXIT_CODES.SUCCESS : EXIT_CODES.ERROR);
}

main().catch(err => {
  console.error(JSON.stringify({ success: false, error: err.message }));
  process.exit(EXIT_CODES.ERROR);
});
