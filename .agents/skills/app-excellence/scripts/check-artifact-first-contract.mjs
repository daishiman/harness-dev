#!/usr/bin/env node

import { readFile } from 'node:fs/promises'
import { fileURLToPath } from 'node:url'
import { join } from 'node:path'

const kitRoot = fileURLToPath(new URL('../../..', import.meta.url))
const artifactContractPath = 'skills/app-excellence/references/artifact-first-delivery.md'

const contracts = [
  {
    path: 'skills/app-excellence/SKILL.md',
    required: ['artifact-first-delivery.md', '成果物先行', '全層trace', 'catalog-default-contract.md']
  },
  {
    path: 'skills/app-excellence/references/03-feature-decomposition.md',
    required: ['全層traceと要件フラグ(単一の正本)', '入力 → 保存 → 再読込 → 更新 → 失敗回復', 'catalog adoption', 'DOM/JSX/HTML']
  },
  {
    path: 'skills/app-excellence/assets/T3-feature-map.md',
    required: ['UI action', 'DB schema/migration', 'catalog adoption', 'E2E証拠(保存→再読込→更新→失敗回復)']
  },
  {
    path: 'skills/app-excellence/assets/T2-experience-spec.md',
    required: ['catalog-default判定', 'catalog-default-contract.md', 'docs/product/design-profile.json', 'profile version', 'REPORT_ONLY(理由', 'NON_VISUAL(理由', '@hiraga-meta version']
  },
  {
    path: 'skills/app-excellence/assets/T4-release-readiness.md',
    required: ['catalog-default conformance', 'v0 minimum・v1 full', 'docs/product/design-conformance.json', 'REPORT_ONLY']
  },
  {
    path: 'skills/app-excellence/references/05-quality-gates.md',
    required: ['catalog-default-contract.md', 'v0でminimum baseline', 'v1でfull conformance', 'NON_VISUAL(理由)']
  },
  {
    path: 'skills/app-excellence/references/01-requirements.md',
    required: ['証拠から再構成', '可逆な仮説']
  },
  {
    path: 'skills/mvp-first-development/SKILL.md',
    required: ['事前質問ゼロ', '成果物への差分', '技術を聞かない自動裁定(単一の正本)', '技術情報を質問しないだけでなく可視DOMへも出さず', 'catalog-default-contract.md', 'T2 provenance→T3 adoption→T4 conformance']
  },
  {
    path: 'skills/jp-web-design/SKILL.md',
    required: ['代表画面', '質問より先', 'references/information-design.md', 'references/catalog-default-contract.md']
  },
  {
    path: 'skills/jp-web-design/references/information-design.md',
    required: ['文章とフローの認知負荷', '3操作・30秒', '常設の補足説明', '参照カタログの説明文・サンプル固有文言']
  },
  {
    path: 'skills/jp-web-design/assets/reference/README.md',
    required: ['コピーしない', 'references/information-design.md', 'catalog-default-contract.md']
  },
  {
    path: 'skills/app-excellence/references/04-build-standards.md',
    required: ['全層traceは内部の受入証拠', '参照カタログの説明文・サンプル固有文言・デバッグ注記をコピーしない', 'references/catalog-default-contract.md', 'references/typography-numerals.md', 'references/hiraga-color-system.md', '役割トークン']
  },
  {
    path: 'skills/ux-design/SKILL.md',
    required: ['推奨案を1つ', '成果物への差分']
  },
  {
    path: 'agents/app-orchestrator.md',
    required: ['Evidence → Decide → Draft → Validate → Diff', '事前質問ゼロ', '全層traceと要件フラグ', '文章とフローの認知負荷', '参照カタログの説明文・サンプル固有文言・デバッグ注記', 'catalog-default consumer contract', 'references/catalog-default-contract.md', 'references/hiraga-color-system.md', 'DOM/JSX/HTML', 'v0で同契約のminimum baseline', 'v1でfull conformance']
  },
  {
    path: 'codex/agents/app-orchestrator.toml',
    required: ['成果物先行', '本人しか決められない境界']
  },
  {
    path: 'codex/workflow-skills/build-app/SKILL.md',
    required: ['質問で止めず', '成果物先行', 'catalog-default入口契約', 'NON_VISUAL(理由)']
  },
  {
    path: 'codex/workflow-skills/improve-app/SKILL.md',
    required: ['最有力の1件', '成果物への差分', 'catalog-default入口契約', 'DOM/JSX/HTML', '通常の新画面追加']
  },
  {
    path: 'commands/build-app.md',
    required: ['Evidence → Decide → Draft → Validate → Diff', '空欄の質問票ではなく']
  },
  {
    path: 'commands/improve-app.md',
    required: ['最有力の1件', '成果物への差分']
  },
  {
    path: 'commands/undo-app.md',
    required: ['非破壊の差分プレビュー', '一点だけ承認']
  },
  {
    path: 'skills/design-judgment/SKILL.md',
    required: ['内部診断', '成果物のどこを変えたいか']
  },
  {
    path: 'skills/better-auth-google-gate/SKILL.md',
    required: ['通常は事前質問ゼロ', 'secret-freeの実装']
  },
  {
    path: 'skills/turnstile-spin/SKILL.md',
    required: ['成果物先行フロー', '利用者へ選択を丸投げせず']
  }
]

const forbidden = [
  ['skills/jp-web-design/SKILL.md', '作り始める前に次を選択式で確認する'],
  ['skills/ux-design/SKILL.md', '実装前に選択肢の比較表'],
  ['agents/app-orchestrator.md', '今回はどれから?'],
  ['codex/workflow-skills/build-app/SKILL.md', '3点だけを確認する'],
  ['codex/workflow-skills/improve-app/SKILL.md', '1件を選んでもらう'],
  ['commands/build-app.md', '3点を確認してから起動する'],
  ['commands/improve-app.md', '今回はどれから進めますか?'],
  ['commands/undo-app.md', '3件以内の選択式'],
  ['skills/turnstile-spin/SKILL.md', 'Proceed?'],
  ['skills/turnstile-spin/SKILL.md', 'Ask "yes" / "show"'],
  ['skills/app-excellence/references/04-build-standards.md', '日本語本文13〜14px'],
  ['skills/app-excellence/references/04-build-standards.md', 'ページタイトル19px(SP17px)'],
  ['skills/app-excellence/references/04-build-standards.md', 'IBM Plex Sans'],
  ['skills/app-excellence/references/04-build-standards.md', 'JetBrains Mono'],
  ['agents/app-orchestrator.md', 'hiraga-color-system.css` をそのままコピー'],
  ['skills/app-excellence/assets/T2-experience-spec.md', 'hiraga-color-tokens.json の version'],
  ['skills/app-excellence/assets/T2-experience-spec.md', 'managed-default / explicit-adoption']
]

let failed = false

function pass(message) {
  console.log(`PASS ${message}`)
}

function fail(message) {
  failed = true
  console.error(`FAIL ${message}`)
}

for (const contract of contracts) {
  const fullPath = join(kitRoot, contract.path)
  const body = await readFile(fullPath, 'utf8')
  for (const marker of contract.required) {
    if (body.includes(marker)) {
      pass(`${contract.path}: ${marker}`)
    } else {
      fail(`${contract.path}: missing ${marker}`)
    }
  }
}

for (const [path, phrase] of forbidden) {
  const body = await readFile(join(kitRoot, path), 'utf8')
  if (body.includes(phrase)) {
    fail(`${path}: legacy or duplicated phrase remains: ${phrase}`)
  } else {
    pass(`${path}: legacy or duplicated phrase absent: ${phrase}`)
  }
}

const artifactContract = await readFile(join(kitRoot, artifactContractPath), 'utf8')
const priorityHeading = artifactContract.indexOf('## 0. 適用優先順位')
const loopHeading = artifactContract.indexOf('## 1. 基本ループ')
if (priorityHeading >= 0 && priorityHeading < loopHeading) {
  pass(`${artifactContractPath}: priority contract precedes autonomy loop`)
} else {
  fail(`${artifactContractPath}: priority contract must precede autonomy loop`)
}

const semanticContracts = [
  {
    label: 'explicit constraints override general autonomy',
    pattern: /一般的な自律進行[\s\S]{0,260}システム・開発者[\s\S]{0,260}AGENTS\.md[\s\S]{0,260}Skill[\s\S]{0,260}ユーザーの明示指示/
  },
  {
    label: 'analysis, edit, phase, and approval boundaries are preserved',
    pattern: /分析限定、編集禁止、段階ゲート、承認境界はこの契約より優先する/
  },
  {
    label: 'diagnostic artifacts are valid before root cause is known',
    pattern: /未確定なら再現fixture、診断instrumentation、原因範囲縮小レポートを先に作り、推測パッチを急がない/
  },
  {
    label: 'phase gates block later phases when explicitly required',
    pattern: /分析完了や承認を次工程の条件[\s\S]{0,100}段階ゲートを満たすまで進まない/
  }
]

for (const contract of semanticContracts) {
  if (contract.pattern.test(artifactContract)) {
    pass(`${artifactContractPath}: ${contract.label}`)
  } else {
    fail(`${artifactContractPath}: ${contract.label}`)
  }
}

const contradictoryPhrases = [
  '安全確認を口実に、ローカル分析・実装・検証まで止める',
  '実装は可逆なローカル環境・作業ブランチ・previewまで自律的に進める。',
  'CI/不具合 | 再現条件、根因、最小パッチ、対応する回帰検査'
]

for (const phrase of contradictoryPhrases) {
  if (artifactContract.includes(phrase)) {
    fail(`${artifactContractPath}: contradictory legacy phrase remains: ${phrase}`)
  } else {
    pass(`${artifactContractPath}: contradictory legacy phrase absent`)
  }
}

if (failed) process.exitCode = 1
