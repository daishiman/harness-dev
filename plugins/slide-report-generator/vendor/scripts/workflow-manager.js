#!/usr/bin/env node
/**
 * presentation-slide-generator ワークフロー管理
 *
 * Phase間の移行を検証し、次のステップをガイド
 *
 * Usage:
 *   node workflow-manager.js <project-dir> [--check] [--next]
 *   node workflow-manager.js ./slide-2024-01-24-sample --check
 *   node workflow-manager.js ./slide-2024-01-24-sample --next
 */

import { readFileSync, existsSync, writeFileSync } from 'fs';
import { join, basename, dirname, resolve } from 'path';
import { spawnSync } from 'child_process';
import { fileURLToPath } from 'url';

const __dirname = dirname(fileURLToPath(import.meta.url));

// ==================================================
// Phase定義
//   P1 → P2 → P2.5(NEW: 仕様確定ゲート) → P3 → P3.5 → 完了
// ==================================================

const PHASES = {
  P0: { name: 'init', label: '初期化', next: 'P1' },
  P1: { name: 'hearing', label: 'ヒアリング', next: 'P2', agent: 'hearing-facilitator.md' },
  P2: { name: 'structure', label: '構成設計', next: 'P2_5', agent: 'structure-designer.md' },
  // Phase 2.5: 仕様確定ゲート（NEW）
  P2_5: {
    name: 'spec-gate',
    label: '仕様確定ゲート',
    next: 'P3',
    agent: 'structure-validator.md',
    approval: true,
    gate: { from: 'P2', to: 'P3' }
  },
  // 旧P2_5(D3設計)はオプションとして P2_D3 にリネーム
  P2_D3: { name: 'd3-design', label: 'D3設計', next: 'P2_5', agent: 'd3-diagram-designer.md', optional: true },
  P3: { name: 'html', label: 'HTML生成', next: 'P3_5', agent: 'html-generator.md', gate: { from: 'P3', to: 'P3_5' } },
  P3_5: { name: 'verify', label: 'UI検証', next: 'complete', agent: 'ui-quality-reviewer.md', gate: { from: 'P3_5', to: 'complete' } },
  P4: { name: 'modify', label: '修正', next: 'P3', agent: 'slide-modifier.md', approval: true }
};

// ==================================================
// Phase状態判定
// ==================================================

/**
 * プロジェクトディレクトリの状態からPhaseを判定
 */
function detectPhase(projectDir) {
  const files = {
    structureMd: join(projectDir, 'structure.md'),
    indexHtml: join(projectDir, 'index.html'),
    stylesCss: join(projectDir, 'styles.css'),
    scriptsJs: join(projectDir, 'scripts.js'),
    deployGuide: join(projectDir, 'deploy-guide.md'),
    approvedMarker: join(projectDir, '.approved'),
    validationReport: join(projectDir, 'validation-report.md'),
    workflowState: join(projectDir, '.workflow-state.json')
  };

  // 状態ファイルがあれば読み込み
  if (existsSync(files.workflowState)) {
    try {
      const state = JSON.parse(readFileSync(files.workflowState, 'utf-8'));
      return { phase: state.currentPhase, source: 'state-file', files };
    } catch (e) {
      // 状態ファイルが壊れている場合はファイル存在から判定
    }
  }

  // ファイル存在から判定
  const hasStructure = existsSync(files.structureMd);
  const hasHtml = existsSync(files.indexHtml);
  const hasDeployGuide = existsSync(files.deployGuide);
  const hasApproved = existsSync(files.approvedMarker);

  if (hasHtml && hasStructure && hasDeployGuide) {
    return { phase: 'complete', source: 'files', files };
  }
  if (hasHtml && hasStructure) {
    return { phase: 'P3_5', source: 'files', files };
  }
  if (hasStructure && hasApproved) {
    // P2.5 通過済み、P3 待ち
    return { phase: 'P3', source: 'files', files };
  }
  if (hasStructure) {
    // structure.md はあるが未承認 = P2.5 ゲート待ち
    return { phase: 'P2_5', source: 'files', files, needsApproval: true };
  }

  return { phase: 'P0', source: 'files', files };
}

/**
 * Phase完了条件を検証
 */
function validatePhase(projectDir, phase) {
  const files = {
    structureMd: join(projectDir, 'structure.md'),
    indexHtml: join(projectDir, 'index.html'),
    deployGuide: join(projectDir, 'deploy-guide.md')
  };

  const issues = [];
  const warnings = [];

  switch (phase) {
    case 'P2':
      if (!existsSync(files.structureMd)) {
        issues.push('structure.md が存在しません');
      } else {
        const content = readFileSync(files.structureMd, 'utf-8');
        if (!content.includes('## スライド一覧') && !content.includes('### スライド一覧')) {
          warnings.push('structure.md に「スライド一覧」セクションがありません');
        }
        if (!content.includes('### 各スライド詳細') && !content.includes('## 各スライド詳細')) {
          warnings.push('structure.md に「各スライド詳細」セクションがありません');
        }
      }
      break;

    case 'P2_5':
      // Phase 2.5 仕様確定ゲート - phase-gate.js で詳細検証
      if (!existsSync(files.structureMd)) {
        issues.push('structure.md が存在しません（Phase 2 へ差し戻し）');
      }
      if (!existsSync(join(projectDir, '.approved'))) {
        issues.push('.approved マーカー未取得（structure-validator 経由でユーザー承認必要）');
      }
      if (!existsSync(join(projectDir, 'validation-report.md'))) {
        warnings.push('validation-report.md が未生成（structure-validator が出力）');
      }
      break;

    case 'P3':
      if (!existsSync(files.indexHtml)) {
        issues.push('index.html が存在しません');
      } else {
        const content = readFileSync(files.indexHtml, 'utf-8');
        if (!content.includes('slide-area')) {
          issues.push('index.html に slide-area 要素がありません（16:9必須）');
        }
        if (!content.includes('aspect-ratio')) {
          warnings.push('index.html に aspect-ratio 設定がない可能性があります');
        }
      }
      break;

    case 'P3_5':
    case 'complete':
      // HTML⇔structure.md同期チェック
      if (existsSync(files.indexHtml) && existsSync(files.structureMd)) {
        const htmlContent = readFileSync(files.indexHtml, 'utf-8');
        const structureContent = readFileSync(files.structureMd, 'utf-8');

        // スライド数の簡易チェック
        const htmlSlideCount = (htmlContent.match(/slider__item/g) || []).length;
        const structureSlideCount = (structureContent.match(/^##+ スライド\d+/gm) || []).length
          || (structureContent.match(/^\| \d+ \|/gm) || []).length;

        if (htmlSlideCount > 0 && structureSlideCount > 0 && htmlSlideCount !== structureSlideCount) {
          warnings.push(`スライド数の不一致: HTML=${htmlSlideCount}, structure.md=${structureSlideCount}`);
        }
      }
      break;
  }

  return { valid: issues.length === 0, issues, warnings };
}

// ==================================================
// 次のPhaseガイダンス
// ==================================================

function getNextSteps(currentPhase) {
  const phaseInfo = PHASES[currentPhase];
  if (!phaseInfo) {
    return ['現在のPhaseを特定できません。structure.md または index.html を確認してください。'];
  }

  const steps = [];

  switch (currentPhase) {
    case 'P0':
      steps.push('1. Task: agents/hearing-facilitator.md を起動');
      steps.push('2. ユーザーからタイトル・目的・対象者・発表時間を収集');
      steps.push('3. 収集完了後、Phase 2 へ');
      break;

    case 'P1':
      steps.push('1. Task: agents/structure-designer.md を起動');
      steps.push('2. ヒアリング結果から structure.md を生成');
      steps.push('3. 完了後、Phase 2.5 (仕様確定ゲート) へ');
      steps.push('【D3使用時】agents/d3-diagram-designer.md も並行起動');
      break;

    case 'P2':
      steps.push('1. structure.md を完成させる');
      steps.push('2. Phase 2.5 (仕様確定ゲート) に進む');
      steps.push('   node scripts/phase-gate.js . --from P2 --to P3');
      break;

    case 'P2_5':
      steps.push('🚪 Phase 2.5: 仕様確定ゲート（NEW）');
      steps.push('1. Task: agents/structure-validator.md を起動');
      steps.push('2. node scripts/validate-structure.js ./structure.md で V-001〜V-030 検証');
      steps.push('3. PASS なら validation-report.md を生成しユーザー承認を取得');
      steps.push('4. 承認時に touch .approved を実行');
      steps.push('5. node scripts/phase-gate.js . --from P2 --to P3 で最終ゲートチェック');
      steps.push('   ※FAIL の場合は Phase 2 に差し戻し');
      break;

    case 'P3':
      steps.push('1. Task: agents/html-generator.md を起動');
      steps.push('2. index.html + styles.css + scripts.js + deploy-guide.md を生成');
      steps.push('3. node scripts/phase-gate.js . --from P3 --to P3_5 で確認');
      break;

    case 'P3_5':
      steps.push('1. UI検証結果を確認');
      steps.push('2. 問題なければ完了');
      steps.push('3. 問題あれば修正後、再検証');
      break;

    case 'P4':
      steps.push('⚠️ 修正案のユーザー承認が必要です');
      steps.push('1. 修正内容を確認');
      steps.push('2. 承認後、Phase 3 へ戻り再生成');
      break;

    case 'complete':
      steps.push('✅ プレゼンテーション生成完了');
      steps.push('- node scripts/log_usage.js --result success でログ記録');
      steps.push('- 修正が必要な場合は Phase 4 へ');
      break;
  }

  return steps;
}

// ==================================================
// メイン処理
// ==================================================

function main() {
  const args = process.argv.slice(2);
  const projectDir = args.find(a => !a.startsWith('--')) || '.';
  const checkOnly = args.includes('--check');
  const showNext = args.includes('--next');
  const verbose = args.includes('--verbose') || args.includes('-v');

  if (!existsSync(projectDir)) {
    console.error(`エラー: ディレクトリが存在しません: ${projectDir}`);
    process.exit(1);
  }

  console.log(`\n📁 プロジェクト: ${basename(projectDir)}`);
  console.log('─'.repeat(50));

  // Phase検出
  const { phase, source, files, needsApproval } = detectPhase(projectDir);
  const phaseInfo = PHASES[phase] || { label: phase };

  console.log(`\n📍 現在のPhase: ${phase} (${phaseInfo.label})`);
  if (needsApproval) {
    console.log('   ⚠️  ユーザー承認待ち');
  }

  // 検証
  if (checkOnly || verbose) {
    console.log('\n🔍 Phase検証:');
    const validation = validatePhase(projectDir, phase);

    if (validation.issues.length > 0) {
      console.log('   ❌ 問題:');
      validation.issues.forEach(i => console.log(`      - ${i}`));
    }
    if (validation.warnings.length > 0) {
      console.log('   ⚠️  警告:');
      validation.warnings.forEach(w => console.log(`      - ${w}`));
    }
    if (validation.valid && validation.warnings.length === 0) {
      console.log('   ✅ 問題なし');
    }

    // --check 時、現在のPhaseに紐づく phase-gate.js を起動
    const gateInfo = phaseInfo.gate;
    if (checkOnly && gateInfo) {
      console.log(`\n🚪 Phase Gate 実行: ${gateInfo.from} → ${gateInfo.to}`);
      const gateScript = join(__dirname, 'phase-gate.js');
      const gate = spawnSync('node', [
        gateScript, projectDir,
        '--from', gateInfo.from,
        '--to', gateInfo.to
      ], { stdio: 'inherit' });

      if (gate.status === 1) {
        console.log(`\n⛔ ゲート不合格: ${gateInfo.from === 'P2' ? 'Phase 2 (structure-designer)' : '前フェーズ'} に差し戻してください`);
        process.exit(1);
      } else if (gate.status === 2) {
        console.log('\n⚠️  ゲート条件付き合格');
        process.exit(2);
      }
    }
  }

  // 次のステップ
  if (showNext || !checkOnly) {
    console.log('\n📋 次のステップ:');
    const steps = getNextSteps(phase);
    steps.forEach(s => console.log(`   ${s}`));
  }

  // ファイル状態
  if (verbose) {
    console.log('\n📄 ファイル状態:');
    Object.entries(files).forEach(([key, path]) => {
      if (key !== 'workflowState') {
        const exists = existsSync(path);
        console.log(`   ${exists ? '✅' : '❌'} ${basename(path)}`);
      }
    });
  }

  console.log('\n');
}

main();
