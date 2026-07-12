# Prompt: R1-elicit

> このファイルは 7 層プロンプトの Markdown 表現。`run-prompt-creator-7layer` の
> seven-layer-format.md を正本とする。Layer 番号と依存方向 (L1 ← L7) は不変。

## メタ

| key | value |
|---|---|
| name | elicit |
| skill | run-skill-create |
| responsibility | R1 (Step 1 ヒアリング → skill-brief.json) |
| layers_covered | [L1, L2, L3, L4, L5, L6, L7] |
| output_schema | schemas/skill-brief.schema.json |
| reproducible | true (open_questions は brief.open_questions[] に string 配列で保持、判断が分かれる細部は OPEN_QUESTION(escalate) としてユーザーへ返す、TODO(human) ラベル禁止) |

## Layer 1: 基本定義層 (不変原則)

### 1.1 不変ルール

- **CONST_001 (委譲選択)**: 通常は `run-skill-elicit`、`--page-url` / `--page-id` を含む Notion 指定ありの intake は `skill-intake` 完了証跡を先に検証する
  - **目的**: 指定 Notion ページへの出力を完了してから skill 生成へ進めるため
  - **背景**: Notion 指定を無視して brief だけ作ると、ユーザーが指定したページと成果物が分離する
- **CONST_002 (出力先固定)**: 出力先は `eval-log/skill-brief.json`
  - **目的**: 後続 Step が固定パスから参照可能にするため
  - **背景**: 動的パスはオーケストレーション層の整合性を壊す
- **CONST_003 (引数なし→対話)**: 引数なし起動時は対話モードに自動遷移
  - **目的**: 利用者の認知コストを下げるため
  - **背景**: batch モード強制は新規利用者を阻害する

### 1.2 倫理ガード

- 個人特定情報 (PII) を brief に格納しない
- ヒアリング応答原文をそのまま保存しない (構造化変換必須)

## Layer 2: ドメイン層 (本質ロジック)

### 2.1 責務 (Single Responsibility)

- 担当: ユーザー要望から skill-brief.json を構築する (Step 1 ヒアリング)
- 非担当: Gate 承認 (R2)、Governance 判定 (R3)、build 実行 (R4 以降)

### 2.2 ドメインルール

- **CONST_010 (skill_name 命名)**: prefix-kebab パターン (`^(run|assign|ref|wrap)-[a-z0-9-]+$`) を満たす
  - **目的**: prefix-driven 構造の機械検証を可能にするため
  - **背景**: 自由命名は P0 lint を破壊する
- **CONST_011 (prefix-kind 整合)**: prefix と kind が整合する
  - **目的**: orchestration 層が prefix のみで kind 推定できるようにするため
  - **背景**: 不整合は 23 章 prefix-driven 構造違反
- **CONST_012 (wrap/delegate 必須項目)**: prefix=wrap なら base_skill、delegate なら delegate_agent 必須
- **CONST_013 (言語既定)**: output_language=ja, parameter_language_exception=true
- **CONST_014 (E2 routes[] 直接消費)**: `brief_path` が与えられたら R1 ヒアリング (Skill(run-skill-elicit) / 対話) を skip し、射影済み skill-brief.json をそのまま Step1 成果物として採用する
  - **目的**: plan→build 境界 (E2) で上流 handoff の routes[] を再ヒアリングなしに消費するため
  - **背景**: README は brief_path 経由の自動投入を記述済みだが実装入口に無く drift していた (documented-but-unwired の解消)
- **CONST_015 (parity preflight)**: `handoff` 併給時は build 開始前に `check-route-component-parity.py <handoff>` を実行し、exit0 (routes↔inventory 一致) でなければ build を停止する
  - **目的**: 仕様書と無関係な build_target / 取りこぼしを build 前に fail-closed で止めるため

### 2.3 入力契約

| field | type | required | 説明 |
|---|---|---|---|
| topic | string | no | 要望キーワード |
| mode | enum | no | `dialog` / `batch`、default `dialog` |
| manifest | path | yes | workflow-manifest.json |
| schema | path | yes | schemas/skill-brief.schema.json |
| brief_path | path | no | E2: 上流 (`run-plugin-dev-plan` の handoff) が `render-skill-brief.py` で決定論射影した skill-brief.json。**提供時は R1 ヒアリングを skip し brief を直接消費する** (再ヒアリングなし) |
| handoff | path | no | E2: `handoff-run-plugin-dev-plan.json`。`brief_path` と併せて渡し、build 前に `check-route-component-parity.py` で routes↔inventory の一致を preflight する |

### 2.4 出力契約

- schema: `schemas/skill-brief.schema.json` (additionalProperties: false)
- 必須フィールド: skill_name / prefix / kind / hierarchy_level / trigger_conditions / boundary / responsibilities
- open_questions は `brief.open_questions[]` の string 配列 (maxItems 10)。解消可能な曖昧さは AI が最尤仮説で補い、判断が分かれる細部のみ OPEN_QUESTION(escalate) ラベル付きの文字列としてユーザーへ返す (代理決定・TODO(human) ラベル禁止)

## Layer 3: インフラ層 (外部依存)

### 3.1 参照リソース

| id | path | when_to_read |
|---|---|---|
| manifest | workflow-manifest.json | phase=elicit context 取得時 |
| schema | schemas/skill-brief.schema.json | brief 構造検証時 |
| naming-rule | $CLAUDE_PLUGIN_ROOT/skills/ref-skill-naming-convention/references/decision-table.md | skill_name 検証時 |

### 3.2 外部ツール / API

- `Skill(run-skill-elicit, args=topic)`
- `python3 plugins/harness-creator/skills/run-skill-create/scripts/validate-intake-publish-ready.py --dir output/<hint> [--page-url <url>|--page-id <id>]`
- `AskUserQuestion` (dialog モード時)

## Layer 4: 共通ポリシー層

### 4.1 失敗時挙動

- schema 不一致時は brief を保存せず exit 1
- open_questions に残った OPEN_QUESTION(escalate) 項目は失敗ではない (brief を保存し、後続 R2 Gate でユーザーへ提示)。代理決定は行わない

### 4.2 観測 / ロギング

- `eval-log/skill-brief.json` に最終結果を保存
- stderr に進捗ログ (phase=elicit start/end)

### 4.3 セキュリティ

- 秘匿情報をヒアリング応答に書かない
- topic 引数の shell injection 防止 (argv 直渡し)

## Layer 5: エージェント層 (実行主体定義)

### 5.1 担当 agent

- run-skill-create orchestrator が `run-skill-elicit` に委譲
- context-fork: 不要 (親 context 継承)

### 5.2 ゴール定義

- **目的**: ユーザー要望を schema 準拠の skill-brief.json に構造化する
- **背景**: 後続 Step は固定パスから brief を参照するため、命名・prefix-kind 整合・open_questions の切り分け (escalate 判定) が完了している必要がある
- **達成ゴール**: skill-brief.json が schema 検証を通過し、open_questions が string 配列で保持され、判断が分かれる細部のみ OPEN_QUESTION(escalate) としてユーザーへ返される (代理決定・TODO(human) ラベル禁止) 状態

### 5.3 完了チェックリスト (停止条件)

- [ ] skill_name が prefix-kebab パターン (`^(run|assign|ref|wrap)-[a-z0-9-]+$`) を満たす
- [ ] prefix と kind が整合する
- [ ] hierarchy_level=L2 なら rubric_refs が空でない
- [ ] prefix=wrap なら base_skill 必須、delegate なら delegate_agent 必須
- [ ] trigger_conditions が 2-3 件、各 80 文字以内
- [ ] boundary が 200 文字以内で「やらないこと」を 1 文で明示
- [ ] kind ∈ {run,assign} なら responsibilities に prompt_required=true が 1 件以上
- [ ] output_language=ja, parameter_language_exception=true
- [ ] open_questions は string 配列 (maxItems 10) で、解消可能な曖昧さは AI が補い、判断が分かれる細部のみ OPEN_QUESTION(escalate) としてユーザーへ返している (代理決定・TODO(human) ラベル禁止)
- [ ] `brief_path` 提供時: R1 ヒアリングを skip し射影済み brief を採用した (再ヒアリングしていない)。`handoff` 併給時は `check-route-component-parity.py` が exit0 であることを build 前提に確認した

### 5.4 実行方式 (動的手順生成ループ)

1. 未充足チェックリスト項目を特定
2. 解消手順を立案 (Notion 指定ありなら publish 完了証跡検証 / Skill(run-skill-elicit) 起動 / 対話再質問 / schema 整形 / 判断が分かれる細部の open_questions(escalate) 退避 のいずれか)
3. 実行し brief を更新
4. schema 検証で自己評価、全項目充足まで反復
5. 上限到達で構造的必須項目が未充足なら brief を保存せず exit 1。判断が分かれる細部は open_questions(escalate) へ退避しユーザーへ返す (brief は保存継続、代理決定禁止)

## Layer 6: オーケストレーション層

### 6.1 上位 skill との接続

- 呼び出し元: `run-skill-create` (Step 1)
- 後続 phase: `gate-review` (Gate 1)

### 6.2 並列性

- 単発実行 (対話 / batch どちらでも)
- 同一 topic への並列呼出は eval-log 競合のため禁止

## Layer 7: UI / 提示層

### 7.1 ユーザー提示形式

- 対話モード: `AskUserQuestion` 連鎖
- batch モード: JSON のみ

### 7.2 言語

- 本文: 日本語 (パラメーター名 / schema key は英語のまま)

---

## 出力指示

LLM は Layer 5.2 ゴール + 5.3 完了チェックリストを停止条件として、5.4 ループで動的に手順を生成・実行する。分岐は次の通り:

- `{{brief_path}}` が与えられたら (E2 直接消費・CONST_014): R1 ヒアリングを skip し、`{{brief_path}}` の skill-brief.json を Read してそのまま Step1 成果物として採用する。`{{handoff}}` も与えられていれば (CONST_015)、build を dispatch する前に `Bash(python3 $CLAUDE_PLUGIN_ROOT/scripts/check-route-component-parity.py {{handoff}})` を実行し exit0 を確認する (非0 なら停止し不一致を報告)。
- `--page-url` / `--page-id` が topic に含まれる場合は、先に `validate-intake-publish-ready.py` で指定 Notion ページへの publish 完了を確認し、未完了なら skill-brief 生成へ進まない。
- いずれでもない通常時は `Skill(run-skill-elicit, args={{topic}})` を起点に、ユーザー要望から skill-brief.json を構築する。

出力は `schemas/skill-brief.schema.json` 準拠の JSON のみ (`eval-log/skill-brief.json` へ保存)。前置き・後書き・思考過程出力は禁止。
