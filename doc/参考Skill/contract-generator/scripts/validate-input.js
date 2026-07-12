#!/usr/bin/env node
/**
 * 契約情報入力検証スクリプト
 *
 * 収集した契約情報が必須項目を満たしているかを検証する
 * 決定論的な検証処理（LLM不要）
 *
 * 使用方法:
 *   node validate-input.js --input contract-info.json
 *   echo '{"甲":{"名称":"株式会社ABC"}}' | node validate-input.js --stdin
 */

const { readFileSync } = require('fs');
const { resolve } = require('path');

// 必須フィールド定義
const REQUIRED_FIELDS = {
  '甲.名称': { label: '甲（発注者）の名称', critical: true },
  '甲.住所': { label: '甲（発注者）の住所', critical: true },
  '乙.名称': { label: '乙（受注者）の名称', critical: true },
  '乙.住所': { label: '乙（受注者）の住所', critical: true },
  '業務内容': { label: '業務内容', critical: true },
  '支払条件': { label: '支払条件', critical: true },
  '契約期間': { label: '契約期間', critical: true },
};

// 推奨フィールド定義
const RECOMMENDED_FIELDS = {
  '甲.資本金': { label: '甲の資本金（下請法判定用）' },
  '乙.インボイス登録': { label: 'インボイス登録状況' },
  '事業類型': { label: '事業類型（AI/IT/コンサル等）' },
  '契約類型.準委任': { label: '準委任契約の業務' },
  '契約類型.請負': { label: '請負契約の業務' },
  'AI利用有無': { label: 'AI利用の有無' },
  '自動更新': { label: '自動更新の有無' },
};

/**
 * ネストされたオブジェクトから値を取得
 */
function getNestedValue(obj, path) {
  const keys = path.split('.');
  let value = obj;
  for (const key of keys) {
    if (value === undefined || value === null) return undefined;
    value = value[key];
  }
  return value;
}

/**
 * 値が有効かどうかを判定
 */
function isValidValue(value) {
  if (value === undefined || value === null) return false;
  if (typeof value === 'string' && value.trim() === '') return false;
  if (Array.isArray(value) && value.length === 0) return false;
  return true;
}

/**
 * 契約情報を検証
 */
function validateInput(data) {
  const results = {
    valid: true,
    errors: [],
    warnings: [],
    summary: {},
  };

  // 必須フィールドの検証
  console.log('\n📋 必須フィールドの検証');
  console.log('─'.repeat(50));

  for (const [path, config] of Object.entries(REQUIRED_FIELDS)) {
    const value = getNestedValue(data, path);
    const isValid = isValidValue(value);

    results.summary[path] = { valid: isValid, value };

    if (isValid) {
      console.log(`✅ ${config.label}: ${typeof value === 'string' ? value.substring(0, 30) : JSON.stringify(value)}`);
    } else {
      results.valid = false;
      results.errors.push({ field: path, label: config.label, critical: config.critical });
      console.log(`❌ ${config.label}: 未入力`);
    }
  }

  // 推奨フィールドの検証
  console.log('\n📝 推奨フィールドの検証');
  console.log('─'.repeat(50));

  for (const [path, config] of Object.entries(RECOMMENDED_FIELDS)) {
    const value = getNestedValue(data, path);
    const isValid = isValidValue(value);

    results.summary[path] = { valid: isValid, value };

    if (isValid) {
      console.log(`✅ ${config.label}: ${typeof value === 'string' ? value.substring(0, 30) : JSON.stringify(value)}`);
    } else {
      results.warnings.push({ field: path, label: config.label });
      console.log(`⚠️ ${config.label}: 未入力（推奨）`);
    }
  }

  // 追加の整合性チェック
  console.log('\n🔍 整合性チェック');
  console.log('─'.repeat(50));

  // AI利用有無と事業類型の整合性
  const aiUsage = getNestedValue(data, 'AI利用有無');
  const businessType = getNestedValue(data, '事業類型');

  if (businessType === 'AI事業' && aiUsage !== true && aiUsage !== 'true') {
    results.warnings.push({ field: 'AI利用有無', message: 'AI事業なのにAI利用が未指定です' });
    console.log(`⚠️ AI事業なのにAI利用有無が未指定です`);
  } else {
    console.log(`✅ 事業類型とAI利用有無の整合性`);
  }

  // 支払条件のフリーランス新法準拠チェック（簡易）
  const paymentTerms = getNestedValue(data, '支払条件');
  if (paymentTerms && typeof paymentTerms === 'string') {
    const has60Days = /60日|六十日|翌月末|翌々月/.test(paymentTerms);
    if (has60Days) {
      console.log(`✅ 支払条件にフリーランス新法対応の記載あり`);
    } else {
      results.warnings.push({ field: '支払条件', message: '60日以内の支払を確認してください' });
      console.log(`⚠️ 支払条件: 60日以内の支払を確認してください`);
    }
  }

  return results;
}

/**
 * 結果サマリーを表示
 */
function showSummary(results) {
  console.log('\n' + '═'.repeat(50));
  console.log('📊 検証結果サマリー');
  console.log('═'.repeat(50));

  const errorCount = results.errors.length;
  const warningCount = results.warnings.length;

  if (results.valid) {
    console.log('\n✅ 検証成功: 必須フィールドはすべて入力されています');
  } else {
    console.log('\n❌ 検証失敗: 以下の必須フィールドが不足しています');
    results.errors.forEach(e => console.log(`  - ${e.label}`));
  }

  if (warningCount > 0) {
    console.log('\n⚠️ 推奨フィールドの不足:');
    results.warnings.forEach(w => {
      if (w.message) {
        console.log(`  - ${w.label}: ${w.message}`);
      } else {
        console.log(`  - ${w.label}`);
      }
    });
  }

  console.log(`\n結果: ${errorCount}エラー, ${warningCount}警告`);
  console.log('═'.repeat(50));

  return results.valid;
}

/**
 * メイン処理
 */
function main() {
  const args = process.argv.slice(2);

  console.log('═'.repeat(50));
  console.log('📝 契約情報入力検証ツール');
  console.log('═'.repeat(50));

  let data;

  if (args.includes('--stdin')) {
    // 標準入力から読み込み
    const input = readFileSync(0, 'utf-8');
    try {
      data = JSON.parse(input);
    } catch (e) {
      console.error('❌ JSON解析エラー:', e.message);
      process.exit(1);
    }
  } else if (args.includes('--input')) {
    const inputIndex = args.indexOf('--input');
    const filePath = args[inputIndex + 1];
    if (!filePath) {
      console.error('❌ --input オプションにはファイルパスが必要です');
      process.exit(2);
    }
    try {
      const content = readFileSync(resolve(filePath), 'utf-8');
      data = JSON.parse(content);
    } catch (e) {
      console.error('❌ ファイル読み込みエラー:', e.message);
      process.exit(1);
    }
  } else {
    console.log('\n使用方法:');
    console.log('  node validate-input.js --input <JSONファイル>');
    console.log('  echo \'{"甲":{"名称":"ABC"}}\' | node validate-input.js --stdin');
    console.log('\n必須フィールド:');
    Object.entries(REQUIRED_FIELDS).forEach(([path, config]) => {
      console.log(`  - ${path}: ${config.label}`);
    });
    process.exit(0);
  }

  const results = validateInput(data);
  const passed = showSummary(results);

  // 結果をJSONで出力（パイプライン用）
  if (args.includes('--json')) {
    console.log('\n[JSON出力]');
    console.log(JSON.stringify(results, null, 2));
  }

  process.exit(passed ? 0 : 1);
}

main();
