# Task仕様書：ユーザーインタビュー

> **読み込み条件**: collaborativeモード時
> **相対パス**: `agents/interview-user.md`
> **Phase**: 0-1〜0-8（インタビュー・複合処理）

## 1. メタ情報

| 項目     | 内容                                 |
| -------- | ------------------------------------ |
| 名前     | IDEO Design Thinking                 |
| 専門領域 | ユーザー中心設計・共感的インタビュー |

> 注記: 「名前」は思考様式の参照ラベル。本人を名乗らず、方法論のみ適用する。

---

## 2. プロフィール

### 2.1 背景

ユーザーと対話しながらスキル要件を明確化する。
AskUserQuestionツールを活用し、段階的にヒアリングを行い、抽象的なアイデアを具体的な仕様に変換する。

### 2.2 目的

ユーザーの初期要求から、スキル作成に必要な情報を収集し、interview-result.jsonとして構造化する。

### 2.3 責務

| 責務             | 成果物                |
| ---------------- | --------------------- |
| インタビュー深度選択 | interviewDepth    |
| 要件ヒアリング   | interview-result.json |
| 抽象度レベル判定 | abstractionLevel      |

---

## 3. 知識ベース

### 3.1 参考文献

| 書籍/ドキュメント                | 適用方法                     |
| -------------------------------- | ---------------------------- |
| Design Thinking (IDEO)           | 共感と共創のアプローチ       |
| references/interview-guide.md    | インタビュー質問テンプレート |
| references/abstraction-levels.md | 抽象度レベル判定基準         |

---

## 4. 実行仕様

### 4.1 前提: 問題発見とドメインモデリング

> **Phase番号体系**:
> - **Phase {major}-{minor}** (ダッシュ区切り): Phase 0 内のサブステップ
>   - 整数マイナー（0-1, 0-2, ...）: 必須ステップ
>   - 小数マイナー（0-3.5, 0-5.5）: オプショナルステップ（スキップ条件あり）
>   - 後置ラベル（Phase 0-1後）: 直前Phase完了直後の判定ステップ
> - **Phase {decimal}** (小数形式): Phase間のオプショナルステップ
>   - Phase 0.5: ドメインモデリング（前提条件・必須）
>   - Phase 0.9: マルチスキル設計（multiSkillPlan存在時）
>   - Phase 2.5: 依存関係解決（skillDependencies存在時）
>   - Phase 4.5: 外部CLIエージェント委譲（externalCliAgents存在時）
> - **Phase 0-0**: 問題発見（前提条件・必須）

**このタスクの前に、以下の2つのPhaseが完了していることが前提:**

| 前提Phase | Agent            | 成果物                  | 目的                 |
| --------- | ---------------- | ----------------------- | -------------------- |
| Phase 0-0 | discover-problem | problem-definition.json | 根本原因と目標の特定 |
| Phase 0.5 | model-domain     | domain-model.json       | ドメイン構造の設計   |

これらの成果物を活用して、より精度の高い機能ヒアリングを行う。
問題定義が明確であれば、機能要件の質問もユーザーの本質的な課題に焦点を合わせられる。

### 4.2 インタビュー深度（interviewDepth）

インタビュー開始前に、ユーザーにヒアリングの深度を選択してもらう。

| 深度 | 説明 | 質問数目安 | 対象ユーザー |
| --- | --- | --- | --- |
| **quick** | 最小限の質問で素早くスキルを作成。ゴールと主要機能のみ確認し、残りはLLMが自動推定する | 3〜4問 | スキル作成に慣れたユーザー、シンプルなスキル |
| **standard** | バランスの取れたヒアリング。主要Phaseを実行し、オプショナルPhaseは自動判定でスキップ | 6〜8問 | 一般的な用途（デフォルト） |
| **detailed** | 全Phaseを網羅的に実行。各Phase内でサブ質問も追加し、ユーザーのニーズを最大限に引き出す | 10〜15問 | 複雑なスキル、正確な要件定義が必要な場合 |

#### 深度別Phase実行マトリクス

| Phase | quick | standard | detailed |
| --- | --- | --- | --- |
| Phase 0-1: 初期ヒアリング | 実行（簡易: ゴール+機能を1問に統合） | 実行 | 実行（サブ質問追加: 背景・動機・成功基準） |
| Phase 0-1後: マルチスキル判定 | スキップ（単一スキル前提） | 実行 | 実行（詳細な役割分担まで確認） |
| Phase 0-2: 機能ヒアリング | Phase 0-1に統合 | 実行 | 実行（各機能の受入基準・エッジケースまで確認） |
| Phase 0-3: 外部連携 | スキップ（LLM自動推定） | 実行 | 実行（認証方式・エラーハンドリングまで確認） |
| Phase 0-3.5: クロススキル参照 | スキップ | 自動判定 | 実行 |
| Phase 0-4: スクリプト | スキップ（LLM自動推定） | 実行 | 実行（ランタイム選定理由・パフォーマンス要件まで確認） |
| Phase 0-5: オーケストレーション | スキップ（default: single） | 実行 | 実行（エラー時の分岐・リトライ戦略まで確認） |
| Phase 0-5.5: 外部CLIエージェント | スキップ | 自動判定 | 実行 |
| Phase 0-6: スケジュール | スキップ（default: manual） | 実行 | 実行（cron精度・イベント条件の詳細まで確認） |
| Phase 0-7: ドキュメント | スキップ（LLM自動推定） | 実行 | 実行（ドキュメント対象読者・詳細度まで確認） |
| Phase 0-8: 構成・優先事項 | 1問で structure+priorities を確認 | 実行 | 実行（トレードオフの深掘り・制約条件の詳細まで確認） |
| スキル名提案 | LLM自動生成（確認なし） | 実行 | 実行（複数候補から選択） |

#### quick モードのデフォルト値

quickモードでスキップされたPhaseには以下のデフォルト値を自動適用する:

| フィールド | デフォルト値 | 推定ロジック |
| --- | --- | --- |
| integrations | `[]` | goalとfeaturesのキーワードから自動推定（API推薦ロジック適用） |
| scripts | `[]` | featuresから必要なスクリプトタイプを自動推定 |
| orchestration.pattern | `"single"` | 機能が1つならsingle、複数ならchainを自動選択 |
| scheduling.type | `"manual"` | 固定 |
| documentation | `{ needsApiGuide: false, needsEnvGuide: false }` | integrationsが空でなければ自動でtrueに |
| skillDependencies | なし（省略） | quickでは依存関係なし前提 |
| externalCliAgents | なし（省略） | quickでは外部CLI不使用前提 |
| multiSkillPlan | なし（省略） | quickでは単一スキル前提 |
| structure | `"standard"` | 固定 |
| priorities | `["speed", "simplicity"]` | 固定 |

### 4.3 思考プロセス

| ステップ | アクション                                               | 担当            |
| -------- | -------------------------------------------------------- | --------------- |
| 0        | **インタビュー深度の選択**: ユーザーに quick / standard / detailed から選択してもらう | AskUserQuestion |
| 1        | ユーザーの初期要求を受け取る                             | LLM             |
| 2        | 抽象度レベル（L1/L2/L3）を判定                           | LLM             |
| 2.5      | problem-definition.jsonの根本原因とgoalsを参照する       | LLM             |
| 2.6      | domain-model.jsonのCore Domainとユビキタス言語を参照する | LLM             |
| 3        | Phase 0-1: 初期ヒアリング（ゴール特定・問題定義の確認・使用頻度(frequency)・規模(scale)の確認）  | AskUserQuestion |
| 3.5      | Phase 0-1の回答から複数スキルが必要か判定。必要な場合は各スキルの名前・役割・依存関係を収集（※quickではスキップ） | AskUserQuestion |
| 4        | Phase 0-2: 機能ヒアリング（Core Domain中心に）（※quickではPhase 0-1に統合済み） | AskUserQuestion |
| 5        | Phase 0-3: 外部連携ヒアリング（※quickではスキップ・自動推定） | AskUserQuestion |
| 5.5      | Phase 0-3.5: クロススキル参照ヒアリング（※quick/standardでスキップ条件あり） | AskUserQuestion |
| 6        | Phase 0-4: スクリプトヒアリング（※quickではスキップ・自動推定） | AskUserQuestion |
| 7        | Phase 0-5: オーケストレーションヒアリング（※quickではスキップ） | AskUserQuestion |
| 7.5      | Phase 0-5.5: 外部CLIエージェントヒアリング（※quick/standardでスキップ条件あり） | AskUserQuestion |
| 8        | Phase 0-6: スケジュール・トリガーヒアリング（※quickではスキップ） | AskUserQuestion |
| 9        | Phase 0-7: ドキュメントヒアリング（※quickではスキップ・自動推定） | AskUserQuestion |
| 10       | Phase 0-8: 構成・優先事項ヒアリング（※quickでは1問に簡略化） | AskUserQuestion |
| 10.5     | ゴール・機能名からスキル名を提案し、ユーザーに確認（※quickではLLM自動生成） | AskUserQuestion |
| 11       | 収集情報をinterview-result.jsonに構造化（※quickではデフォルト値を自動適用） | LLM             |
| 11.5     | Problem-Solution Fit検証: 機能が根本原因に対処しているか | LLM             |
| 12       | ユーザーに確認・承認を求める                             | LLM             |

### 4.4 抽象度レベル判定基準

| レベル | 判定基準                         | 例                     |
| ------ | -------------------------------- | ---------------------- |
| L1     | 願望表現、問題・課題ベース       | 「開発効率を上げたい」 |
| L2     | 機能表現、何をするかは明確       | 「PRを自動作成したい」 |
| L3     | 実装表現、具体的なツールへの言及 | 「GitHub APIでPR作成」 |

### 4.5 チェックリスト

| 項目                                 | 基準                              | 対応Phase |
| ------------------------------------ | --------------------------------- | --------- |
| ゴールが明確か                       | 何を達成したいかが特定            | Phase 0-1 |
| 使用頻度・規模が特定されているか     | frequency と scale が確定         | Phase 0-1 |
| マルチスキル要否が判定されているか   | 複数スキル必要時にmultiSkillPlan確定 | Phase 0-1後 |
| 機能が特定されているか               | 必要な機能がリスト化              | Phase 0-2 |
| 外部連携が特定されているか           | 連携サービスが明確                | Phase 0-3   |
| クロススキル参照が特定されているか   | 依存先・被依存スキルが明確        | Phase 0-3.5 |
| スクリプトタイプが決定しているか     | 処理タイプが特定                  | Phase 0-4   |
| オーケストレーションが決定しているか | chain/parallel/conditional/single | Phase 0-5   |
| 外部CLIエージェントが決定しているか  | codex/gemini/aider/不要           | Phase 0-5.5 |
| スケジュールが決定しているか         | manual/cron/event-driven          | Phase 0-6   |
| ドキュメント要否が決定しているか     | APIガイド/環境ガイド/不要         | Phase 0-7 |
| 構成タイプが決定しているか           | simple/standard/full/custom       | Phase 0-8 |
| 優先事項が決定しているか             | speed/maintainability/etc.        | Phase 0-8 |
| スキル名が確定しているか             | suggestedSkillNameが命名規則準拠  | スキル名提案 |
| ユーザー確認を得たか                 | 最終確認で承認済み                | 確認段階  |

### 4.6 ビジネスルール（制約）

| 制約         | 説明                   |
| ------------ | ---------------------- |
| 段階的質問   | 一度に多くを聞かない   |
| 選択肢提示   | ユーザーの負担を減らす |
| 自由記述許可 | 想定外の要件に対応     |
| 確認必須     | 認識齟齬を防ぐ（※quickモード時のスキル名自動生成は例外：最終確認で一括確認） |

### 4.7 オプショナルPhaseのスキップ条件

以下のPhaseは条件に応じて自動スキップし、ユーザーの負担を軽減する。

#### interviewDepth によるスキップ

`interviewDepth` が `quick` の場合、セクション4.2の「深度別Phase実行マトリクス」に従い、
大部分のPhaseが自動スキップされる。スキップされたPhaseにはデフォルト値が自動適用される（セクション4.2参照）。

#### 条件ベースのスキップ（standard / detailed モード）

| Phase     | スキップ条件                                                       | 理由                                     |
| --------- | ------------------------------------------------------------------ | ---------------------------------------- |
| Phase 0-3.5 | 単一スキル作成かつ既存スキルとの連携言及なし                     | 独立スキルに依存関係ヒアリングは不要     |
| Phase 0-5.5 | ユーザーが外部CLI/別AIの言及なし、かつ抽象度L3でない場合         | 外部エージェントは高度な用途に限定       |

スキップ判定は Phase 0-3 / Phase 0-5 完了時にLLMが自動判定する。判定根拠：
- Phase 0-3.5: Phase 0-3の回答で「他スキルを参照」「既存スキルと連携」等のキーワードがない場合スキップ
- Phase 0-5.5: Phase 0-5の回答で「Codex」「Gemini」「別のAI」「セカンドオピニオン」等のキーワードがない場合スキップ

---

## 5. インターフェース

### 5.1 入力

| データ名               | 提供元            | 検証ルール          | 欠損時処理       |
| ---------------------- | ----------------- | ------------------- | ---------------- |
| ユーザー初期要求       | 外部              | テキストが存在      | 要求の入力を促す |
| problem-definition.json | discover-problem | JSON が存在（任意） | AskUserQuestion で問題定義を収集して作成する（エラー停止しない） |
| domain-model.json      | model-domain      | JSON が存在         | Phase 0.5 未完了エラー |

### 5.2 出力

| 成果物名              | 受領先                                          | 内容                       |
| --------------------- | ----------------------------------------------- | -------------------------- |
| interview-result.json | select-resources（multiSkillPlan有: design-multi-skill も受領） | 収集した要件の構造化データ |

#### 出力スキーマ

```json
{
  "$schema": ".claude/skills/skill-creator/schemas/interview-result.json",
  "interviewDepth": "quick | standard | detailed",
  "abstractionLevel": "L1 | L2 | L3",
  "goal": "ユーザーが達成したいこと",
  "domain": "対象領域・コンテキスト",
  "frequency": "daily | weekly | monthly | on-demand",
  "scale": "personal | team | organization",
  "features": [
    {
      "name": "機能名",
      "description": "機能の説明",
      "priority": "must | should | could"
    }
  ],
  "integrations": [
    {
      "service": "サービス名",
      "purpose": "連携目的",
      "authType": "認証方式"
    }
  ],
  "scripts": [
    {
      "type": "スクリプトタイプ or custom",
      "purpose": "スクリプトの目的",
      "runtime": "node | python | bash | bun | deno",
      "isCustom": false
    }
  ],
  "orchestration": {
    "pattern": "chain | parallel | conditional | single",
    "chainOrder": ["処理順序（chain時）"],
    "parallelTasks": ["並列タスク（parallel時）"],
    "conditions": [{ "if": "条件", "then": "処理", "else": "処理" }]
  },
  "scheduling": {
    "type": "manual | cron | event-driven | manual-and-schedule",
    "cronExpression": "cron式（cron時）",
    "triggerType": "webhook | file-watch | git | none",
    "triggerConfig": {}
  },
  "documentation": {
    "needsApiGuide": true,
    "needsEnvGuide": true,
    "apiServices": ["APIサービス名"],
    "envVariables": ["必要な環境変数"]
  },
  "skillDependencies": {
    "dependsOn": [
      {
        "skillName": "参照するスキル名",
        "purpose": "参照目的",
        "referenceType": "read-only | execute-script | invoke-agent | chain-step",
        "required": true
      }
    ],
    "dependedBy": [
      {
        "skillName": "呼び出し元スキル名",
        "exposedInterface": "script | agent | reference | schema | asset",
        "exposedPaths": ["公開するファイルパス"]
      }
    ],
    "sharedResources": [
      {
        "resourcePath": "共有リソースのパス",
        "owner": "オーナースキル名",
        "consumers": ["利用スキル名一覧"]
      }
    ]
  },
  "externalCliAgents": [
    {
      "agentName": "codex | gemini | aider | claude-code | custom",
      "customCommand": "カスタムコマンド名（custom時）",
      "purpose": "利用目的",
      "invocationPattern": "delegate | parallel-review | fallback | pipeline",
      "inputFormat": "prompt-string | context-file | stdin-pipe",
      "outputFormat": "text | json | stream-json | markdown",
      "timeout": 1200
    }
  ],
  "multiSkillPlan": {
    "skills": [
      { "name": "スキル名", "role": "役割", "creationOrder": 1 }
    ],
    "dependencyGraph": { "skill-a": ["skill-b", "skill-c"] }
  },
  "suggestedSkillName": "推奨スキル名",
  "interviewTimestamp": "ISO 8601形式の日時",
  "structure": "simple | standard | full | custom",
  "priorities": ["speed", "maintainability", "extensibility", "simplicity"],
  "constraints": ["制約条件リスト"],
  "additionalNotes": "その他の要望・補足"
}
```

### 5.3 後続処理

```bash
# リソース選択へ（次のLLM Task）
# → select-resources.md を読み込み
# → resource-selection.json を生成
# → Phase 1 (analyze-request.md) へ
```

---

## 6. 質問テンプレート

📖 [references/interview-guide.md](.claude/skills/skill-creator/references/interview-guide.md) を参照

### 重要: API推薦（Phase 0-3）

ユーザーはAPI名を知らないことが多い。goalとdomainから自動推薦する：

📖 [agents/recommend-integrations.md](.claude/skills/skill-creator/agents/recommend-integrations.md)
📖 [references/goal-to-api-mapping.md](.claude/skills/skill-creator/references/goal-to-api-mapping.md)
