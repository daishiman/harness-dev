#!/usr/bin/env node
/**
 * 取引基本契約書 検証スクリプト
 *
 * 契約書の必須項目チェック、法的整合性検証、フォーマット確認を行う
 *
 * 使用方法:
 *   node validate-contract.js <契約書ファイルパス>
 *   node validate-contract.js --check-template
 */

const { readFileSync, existsSync } = require('fs');
const { resolve } = require('path');

// 必須条項チェックリスト（全27条対応）
const REQUIRED_CLAUSES = [
  // 第1章 総則
  { id: 'purpose', name: '目的', pattern: /第\d+条[（(]目的[）)]|目的.*本契約/, critical: true },
  { id: 'definitions', name: '定義', pattern: /第\d+条[（(]定義[）)]|定義.*本契約/, critical: false },
  { id: 'individual-contract', name: '個別契約', pattern: /個別契約|個別.*契約/, critical: true },
  // 第3章 納入・検収
  { id: 'delivery', name: '納入・検収', pattern: /納入|検収|引渡/, critical: true },
  // 第4章 報酬・支払
  { id: 'payment', name: '報酬・支払', pattern: /報酬|支払|対価/, critical: true },
  // 第5章 知的財産権
  { id: 'intellectual-property', name: '知的財産権', pattern: /知的財産|著作権|特許/, critical: true },
  { id: 'copyright-27-28', name: '著作権法27条・28条', pattern: /第27条.*第28条|27条.*28条|翻案権|二次的著作物/, critical: true },
  { id: 'moral-rights', name: '著作者人格権', pattern: /著作者人格権|不行使/, critical: true },
  // 第6章 責任
  { id: 'warranty', name: '契約不適合責任', pattern: /契約不適合|瑕疵担保|追完請求/, critical: true },
  { id: 'warranty-scope', name: '追完請求範囲限定', pattern: /目的達成を妨げる場合|目的達成.*妨げ/, critical: false },
  { id: 'warranty-method', name: '追完方法の乙選択', pattern: /追完の方法は乙が選択|追完.*乙.*選択/, critical: false },
  { id: 'damages', name: '損害賠償', pattern: /損害賠償|賠償責任/, critical: true },
  // 第7章 秘密保持
  { id: 'confidentiality', name: '秘密保持', pattern: /秘密保持|秘密情報|機密/, critical: true },
  // 第8章 契約期間・解除
  { id: 'termination', name: '契約期間・解除', pattern: /契約期間|解除|終了/, critical: true },
  // 第9章 反社会的勢力の排除
  { id: 'anti-social', name: '反社会的勢力排除', pattern: /反社会的勢力|暴力団|反社/, critical: true },
  // 第10章 一般条項（v2.9.0で追加）
  { id: 'assignment-prohibition', name: '権利義務の譲渡禁止', pattern: /権利義務.*譲渡|契約上の地位.*移転/, critical: true },
  { id: 'survival', name: '存続条項', pattern: /存続条項|残存条項|終了後.*有効/, critical: false },
  { id: 'consultation', name: '協議条項', pattern: /協議.*解決|誠意.*協議/, critical: false },
  { id: 'severability', name: '分離独立', pattern: /分離独立|一部.*無効.*残部|条項.*無効.*存続/, critical: false },
  { id: 'governing-law', name: '準拠法', pattern: /準拠法.*日本法|日本法.*準拠/, critical: true },
  { id: 'jurisdiction', name: '合意管轄', pattern: /合意管轄|専属的管轄|管轄裁判所/, critical: true },
];

// フリーランス新法チェック項目
const FREELANCE_LAW_CHECKS = [
  { id: 'payment-60days', name: '支払期日60日以内', pattern: /60日|六十日/, warning: '支払期日が60日以内であることを確認してください' },
  { id: 'termination-30days', name: '解約予告30日前', pattern: /30日前|三十日前/, warning: '6か月以上の契約の場合、30日前予告が必要です' },
  { id: 'conditions-disclosure', name: '取引条件明示', pattern: /取引条件|業務内容.*報酬.*支払期日/, warning: '取引条件の明示が必要です' },
];

// AI特有条項チェック
const AI_SPECIFIC_CHECKS = [
  { id: 'ai-usage', name: 'AI利用説明', pattern: /AI|人工知能|生成AI|ChatGPT|Claude/, recommended: true },
  { id: 'hallucination', name: 'ハルシネーション免責', pattern: /ハルシネーション|誤情報|不正確/, recommended: true },
  { id: 'prompt-ip', name: 'プロンプト権利', pattern: /プロンプト|入力データ/, recommended: true },
];

// フォーマットチェック
const FORMAT_CHECKS = [
  { id: 'title', name: '契約書タイトル', pattern: /^#\s+.*契約書|取引基本契約書/ },
  { id: 'parties', name: '当事者記載', pattern: /甲.*乙|発注者.*受注者/ },
  { id: 'date', name: '契約日', pattern: /年.*月.*日|令和.*年/ },
  { id: 'signatures', name: '署名欄', pattern: /記名押印|署名|印/ },
];

/**
 * 契約書を検証
 */
function validateContract(content) {
  const results = {
    passed: [],
    failed: [],
    warnings: [],
    recommendations: [],
    score: 0,
    maxScore: 0,
  };

  // 必須条項チェック
  console.log('\n📋 必須条項チェック');
  console.log('─'.repeat(50));

  for (const clause of REQUIRED_CLAUSES) {
    results.maxScore += clause.critical ? 10 : 5;

    if (clause.pattern.test(content)) {
      results.passed.push(clause);
      results.score += clause.critical ? 10 : 5;
      console.log(`✅ ${clause.name}`);
    } else {
      results.failed.push(clause);
      const marker = clause.critical ? '❌' : '⚠️';
      console.log(`${marker} ${clause.name} ${clause.critical ? '【必須】' : '【推奨】'}`);
    }
  }

  // フリーランス新法チェック
  console.log('\n📜 フリーランス新法対応チェック');
  console.log('─'.repeat(50));

  for (const check of FREELANCE_LAW_CHECKS) {
    if (check.pattern.test(content)) {
      console.log(`✅ ${check.name}`);
    } else {
      results.warnings.push(check);
      console.log(`⚠️ ${check.name}: ${check.warning}`);
    }
  }

  // AI特有条項チェック
  console.log('\n🤖 AI事業特有条項チェック');
  console.log('─'.repeat(50));

  for (const check of AI_SPECIFIC_CHECKS) {
    if (check.pattern.test(content)) {
      console.log(`✅ ${check.name}`);
    } else {
      results.recommendations.push(check);
      console.log(`💡 ${check.name}【推奨】`);
    }
  }

  // フォーマットチェック
  console.log('\n📄 フォーマットチェック');
  console.log('─'.repeat(50));

  for (const check of FORMAT_CHECKS) {
    if (check.pattern.test(content)) {
      console.log(`✅ ${check.name}`);
    } else {
      console.log(`⚠️ ${check.name}`);
    }
  }

  return results;
}

/**
 * 結果サマリーを表示
 */
function showSummary(results) {
  const percentage = Math.round((results.score / results.maxScore) * 100);

  console.log('\n' + '═'.repeat(50));
  console.log('📊 検証結果サマリー');
  console.log('═'.repeat(50));

  console.log(`\nスコア: ${results.score}/${results.maxScore} (${percentage}%)`);

  // スコアバー
  const filled = Math.round(percentage / 5);
  const bar = '█'.repeat(filled) + '░'.repeat(20 - filled);
  console.log(`[${bar}]`);

  // 評価
  let grade, message;
  if (percentage >= 90) {
    grade = 'A';
    message = '優秀：契約書として高品質です';
  } else if (percentage >= 70) {
    grade = 'B';
    message = '良好：いくつかの改善点があります';
  } else if (percentage >= 50) {
    grade = 'C';
    message = '要改善：重要な条項が不足しています';
  } else {
    grade = 'D';
    message = '不十分：大幅な見直しが必要です';
  }

  console.log(`\n評価: ${grade}`);
  console.log(`💬 ${message}`);

  // 重要な不足項目
  const criticalFailures = results.failed.filter(c => c.critical);
  if (criticalFailures.length > 0) {
    console.log('\n⚠️ 重要な不足項目:');
    criticalFailures.forEach(c => console.log(`  - ${c.name}`));
  }

  // 警告
  if (results.warnings.length > 0) {
    console.log('\n📝 法令対応の確認事項:');
    results.warnings.forEach(w => console.log(`  - ${w.warning}`));
  }

  console.log('\n' + '═'.repeat(50));

  return percentage >= 70;
}

/**
 * テンプレートの存在確認
 */
function checkTemplate() {
  const templatePath = resolve(__dirname, '../assets/contract-template.md');

  console.log('\n📋 テンプレートチェック');
  console.log('─'.repeat(50));

  if (existsSync(templatePath)) {
    console.log(`✅ テンプレートが存在します: ${templatePath}`);

    const content = readFileSync(templatePath, 'utf-8');
    console.log(`   ファイルサイズ: ${content.length} 文字`);

    // テンプレートの検証
    console.log('\n📄 テンプレート内容検証');
    validateContract(content);

    return true;
  } else {
    console.log(`❌ テンプレートが見つかりません: ${templatePath}`);
    return false;
  }
}

/**
 * メイン処理
 */
function main() {
  const args = process.argv.slice(2);

  console.log('═'.repeat(50));
  console.log('📜 取引基本契約書 検証ツール');
  console.log('═'.repeat(50));

  if (args.includes('--check-template')) {
    checkTemplate();
    return;
  }

  if (args.length === 0) {
    console.log('\n使用方法:');
    console.log('  node validate-contract.js <契約書ファイルパス>');
    console.log('  node validate-contract.js --check-template');
    console.log('\nオプション:');
    console.log('  --check-template  テンプレートファイルを検証');
    process.exit(1);
  }

  const filePath = resolve(args[0]);

  if (!existsSync(filePath)) {
    console.error(`❌ ファイルが見つかりません: ${filePath}`);
    process.exit(1);
  }

  console.log(`\n検証対象: ${filePath}`);

  const content = readFileSync(filePath, 'utf-8');
  const results = validateContract(content);
  const passed = showSummary(results);

  process.exit(passed ? 0 : 1);
}

main();
