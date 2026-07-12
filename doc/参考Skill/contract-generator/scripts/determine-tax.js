#!/usr/bin/env node
/**
 * 税務判定スクリプト
 *
 * 契約情報から印紙税・源泉徴収・インボイス対応を機械的に判定する
 * 決定論的な処理（LLM不要）
 *
 * 使用方法:
 *   node determine-tax.js --input contract-info.json
 *   echo '{"契約期間":"1年","業務内容":["コンサル"]}' | node determine-tax.js --stdin
 */

const fs = require('fs');
const path = require('path');

// 源泉徴収対象業務の定義（所得税法204条1項）
const WITHHOLDING_TARGET_KEYWORDS = [
  'デザイン', 'design', 'イラスト', 'illustration',
  '著述', '執筆', 'ライティング', 'writing',
  '講演', '講師', 'セミナー', '研修',
  '写真', 'カメラマン', 'photography',
  '翻訳', '通訳', 'translation',
  '芸能', 'タレント', '俳優', '歌手',
  'モデル', 'modeling',
];

// 源泉徴収非対象業務
const NON_WITHHOLDING_KEYWORDS = [
  'コンサルティング', 'コンサル', 'consulting', 'アドバイザリー',
  'システム開発', 'プログラミング', 'エンジニアリング', '開発',
  'AI', '機械学習', 'データ分析',
];

/**
 * 契約期間を月数に変換
 */
function parseContractPeriod(period) {
  if (!period || typeof period !== 'string') return { months: 0, autoRenew: false };

  const autoRenew = /自動更新|更新あり|自動延長/.test(period);

  // 年単位
  const yearMatch = period.match(/(\d+)\s*年/);
  if (yearMatch) {
    return { months: parseInt(yearMatch[1]) * 12, autoRenew };
  }

  // 月単位
  const monthMatch = period.match(/(\d+)\s*(か月|ヶ月|カ月)/);
  if (monthMatch) {
    return { months: parseInt(monthMatch[1]), autoRenew };
  }

  // 日単位
  const dayMatch = period.match(/(\d+)\s*日/);
  if (dayMatch) {
    return { months: Math.ceil(parseInt(dayMatch[1]) / 30), autoRenew };
  }

  return { months: 0, autoRenew };
}

/**
 * 印紙税を判定
 */
function determineStampTax(data) {
  const result = {
    taxable: false,
    amount: 0,
    documentType: '非課税',
    reason: '',
    electronic: false,
  };

  // 電子契約の場合
  if (data.電子契約 === true || data.電子契約 === 'true') {
    result.electronic = true;
    result.reason = '電子契約のため印紙税不要';
    return result;
  }

  // 契約期間の解析
  const { months, autoRenew } = parseContractPeriod(data.契約期間);

  // 第7号文書の判定（継続的取引の基本契約）
  if (months > 3 || autoRenew) {
    result.taxable = true;
    result.amount = 4000;
    result.documentType = '第7号文書（継続的取引の基本契約書）';
    result.reason = months > 3
      ? `契約期間${months}か月（3か月超）`
      : '自動更新条項あり';
  } else if (months > 0) {
    result.reason = `契約期間${months}か月（3か月以内、更新なし）`;
  } else {
    result.reason = '契約期間が特定できないため、要確認';
  }

  return result;
}

/**
 * 源泉徴収を判定
 */
function determineWithholding(data) {
  const result = {
    required: false,
    rate: null,
    targetServices: [],
    reason: '',
  };

  // 業務内容の取得
  let services = [];
  if (Array.isArray(data.業務内容)) {
    services = data.業務内容;
  } else if (typeof data.業務内容 === 'string') {
    services = [data.業務内容];
  }

  const serviceText = services.join(' ').toLowerCase();

  // 対象業務のチェック
  const matchedTargets = WITHHOLDING_TARGET_KEYWORDS.filter(kw =>
    serviceText.includes(kw.toLowerCase())
  );

  // 非対象業務のチェック
  const matchedNonTargets = NON_WITHHOLDING_KEYWORDS.filter(kw =>
    serviceText.includes(kw.toLowerCase())
  );

  if (matchedTargets.length > 0) {
    result.required = true;
    result.rate = '10.21%';
    result.targetServices = matchedTargets;
    result.reason = `対象業務あり: ${matchedTargets.join(', ')}（所得税法204条1項）`;

    // 非対象業務も混在する場合の注意
    if (matchedNonTargets.length > 0) {
      result.reason += `（ただし ${matchedNonTargets.join(', ')} は非対象）`;
    }
  } else if (matchedNonTargets.length > 0) {
    result.reason = `非対象業務: ${matchedNonTargets.join(', ')}`;
  } else {
    result.reason = '業務内容から判定不能。個別確認を推奨';
  }

  return result;
}

/**
 * インボイス対応を判定
 */
function determineInvoice(data) {
  const result = {
    registered: null,
    registrationNumber: null,
    transitionalMeasure: false,
    action: '',
  };

  const status = data.乙?.インボイス登録 || data.インボイス登録;

  if (status === '登録済み' || status === true || status === 'true') {
    result.registered = true;
    result.registrationNumber = data.乙?.登録番号 || data.登録番号 || '要確認';
    result.action = '登録番号を契約書・請求書に記載';
  } else if (status === '未登録' || status === false || status === 'false') {
    result.registered = false;
    result.transitionalMeasure = true;
    result.action = '経過措置（80%控除→50%→0%）を適用。発注者に説明推奨';
  } else {
    result.action = 'インボイス登録状況を確認してください';
  }

  return result;
}

/**
 * 税務判定を実行
 */
function determineTax(data) {
  console.log('\n📊 税務判定実行');
  console.log('─'.repeat(50));

  const stampTax = determineStampTax(data);
  const withholding = determineWithholding(data);
  const invoice = determineInvoice(data);

  // 結果表示
  console.log('\n【印紙税】');
  if (stampTax.electronic) {
    console.log(`  ✅ 不要（電子契約）`);
  } else if (stampTax.taxable) {
    console.log(`  💰 ${stampTax.amount.toLocaleString()}円（${stampTax.documentType}）`);
    console.log(`  📝 理由: ${stampTax.reason}`);
  } else {
    console.log(`  ✅ 非課税`);
    console.log(`  📝 理由: ${stampTax.reason}`);
  }

  console.log('\n【源泉徴収】');
  if (withholding.required) {
    console.log(`  ⚠️ 対象（税率: ${withholding.rate}）`);
    console.log(`  📝 理由: ${withholding.reason}`);
  } else {
    console.log(`  ✅ 非対象`);
    console.log(`  📝 理由: ${withholding.reason}`);
  }

  console.log('\n【インボイス】');
  if (invoice.registered === true) {
    console.log(`  ✅ 登録済み`);
    console.log(`  📝 アクション: ${invoice.action}`);
  } else if (invoice.registered === false) {
    console.log(`  ⚠️ 未登録（経過措置適用）`);
    console.log(`  📝 アクション: ${invoice.action}`);
  } else {
    console.log(`  ❓ 未確認`);
    console.log(`  📝 アクション: ${invoice.action}`);
  }

  return {
    印紙税: stampTax,
    源泉徴収: withholding,
    インボイス: invoice,
  };
}

/**
 * メイン処理
 */
function main() {
  const args = process.argv.slice(2);

  console.log('═'.repeat(50));
  console.log('💴 税務判定ツール');
  console.log('═'.repeat(50));

  let data;

  if (args.includes('--stdin')) {
    const input = fs.readFileSync(0, 'utf-8');
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
      const content = fs.readFileSync(path.resolve(filePath), 'utf-8');
      data = JSON.parse(content);
    } catch (e) {
      console.error('❌ ファイル読み込みエラー:', e.message);
      process.exit(1);
    }
  } else {
    console.log('\n使用方法:');
    console.log('  node determine-tax.js --input <JSONファイル>');
    console.log('  echo \'{"契約期間":"1年"}\' | node determine-tax.js --stdin');
    console.log('\n判定項目:');
    console.log('  - 印紙税: 契約期間・自動更新から第7号文書該当性を判定');
    console.log('  - 源泉徴収: 業務内容から所得税法204条該当性を判定');
    console.log('  - インボイス: 登録状況から対応方針を提示');
    process.exit(0);
  }

  const results = determineTax(data);

  // 結果をJSONで出力
  if (args.includes('--json')) {
    console.log('\n═'.repeat(50));
    console.log('[JSON出力]');
    console.log(JSON.stringify(results, null, 2));
  }

  console.log('\n═'.repeat(50));
  console.log('※ 本判定は一般的な基準に基づくものです。');
  console.log('  複雑なケースは税理士にご確認ください。');
  console.log('═'.repeat(50));
}

main();
