# Prompt: R1-elicit

> このファイルは 7 層プロンプトの Markdown 表現。`run-prompt-creator-7layer` の
> seven-layer-markdown-template.md を正本とする。Layer 番号と依存方向 (L1 ← L7) は不変。
> L5 サブ構造は seven-layer-format.md「Layer 5 契約」(l5-contract v2.0.0) に従属する。

## メタ

| key | value |
|---|---|
| name | elicit |
| skill | run-prompt-create |
| responsibility | R1 (Step 1 ヒアリング → prompt-brief.json) |
| layers_covered | [L1, L2, L3, L4, L5, L6, L7] |
| output_schema | schemas/prompt-brief.schema.json |
| reproducible | true (schema 検証 + 完了チェックリストが停止条件。未確定事項は AI 最尤補完し仮定を open_questions に記録) |

## Layer 1: 基本定義層 (不変原則)

### 1.1 不変ルール
- 委譲先は run-prompt-elicit (Skill tool)
- 出力先は固定パス `eval-log/prompt-brief.json`
- 引数なし起動時は対話モードに入る
- output_language=ja, parameter_language_exception=true を既定

### 1.2 倫理ガード
- 個人特定情報を brief に格納しない
- 秘匿情報をヒアリング応答に書かない

## Layer 2: ドメイン層 (本質ロジック)

### 2.1 責務 (Single Responsibility)
- 担当: `run-prompt-elicit` への委譲契約、prompt-brief.json の入出力契約、Gate 1 接続
- ヒアリング質問の正本: `run-prompt-elicit/prompts/R1-interview.md`
- 非担当: Gate 承認 (R2)、Governance 判定 (R3)、Layer 生成 (run-prompt-creator-7layer)

### 2.2 ドメインルール
- prompt_name は `[a-z][a-z0-9-]*` (60 文字以内)
- responsibility_id は `R[0-9]+` 形式 (owner skill の responsibilities[].id と 1:1)。skill 紐付け (target_skill あり) 時のみ必須、standalone (target_skill なし) では混入禁止 (schema if/then/else が機械正本)
- layers_required は L1-L7 のうち最低 1 つ
- boundary は 200 文字以内で「やらないこと」を 1 文で明示
- format は md 既定 (yaml は legacy のみ)

### 2.3 入力契約
| field | type | required | 説明 |
|---|---|---|---|
| topic | string | no | プロンプト要望キーワード |
| target_skill | string | no | 所有 skill 名 |
| responsibility_id | string | no | R-id |
| mode | string | no | dialog / batch |
| manifest | path | yes | workflow-manifest.json |
| schema | path | yes | schemas/prompt-brief.schema.json |

### 2.4 出力契約
- schema: `schemas/prompt-brief.schema.json`
- 共通必須: prompt_name / owner_agent_or_skill / layers_required / trigger_conditions / goals / checklist / output_contract / boundary / output_language
- モード別必須 (schema if/then/else): skill 紐付け時は target_skill + responsibility_id、standalone 時は output_path (target_skill / responsibility_id はキーごと省く)
- goals は観測可能な成果状態 (完了形)、checklist は item+judgement (第三者 YES/NO 判定基準) で収集する (L5 5.2/5.3 の宣言型材料)
- 未確定事項は AI 最尤仮説で補完し、補完した仮定を open_questions に記録する (人間差し戻しマーカーを brief に生成しない)

## Layer 3: インフラ層 (外部依存)

### 3.1 参照リソース
| id | path | when_to_read |
|---|---|---|
| manifest | workflow-manifest.json | phase: elicit 確認時 |
| schema | schemas/prompt-brief.schema.json | brief 構造検証時 |
| target | brief.target_skill 配下 SKILL.md | responsibilities 突合時 |

### 3.2 外部ツール / API
- Skill(run-prompt-elicit, args=topic)
- AskUserQuestion (dialog mode)

## Layer 4: 共通ポリシー層

### 4.1 失敗時挙動
- schema 不一致時は brief を保存せず exit 1
- ゴールシークループ/差し戻しの最大反復回数: 3 (SKILL.md Gate 1 の否認上限と同値。超過時は停止し findings 提示)

### 4.2 観測 / ロギング
- eval-log/prompt-brief.json に最終結果を保存
- handoff-after_prompt_elicit.json を Gate 1 通過時に保存

### 4.3 セキュリティ
- 秘匿情報をヒアリング応答に書かない

## Layer 5: エージェント層 (実行主体定義)

### 5.1 担当 agent
- run-prompt-create orchestrator が run-prompt-elicit に委譲
- 内部で prompt-creator-interview-user agent を context:fork で起動

### 5.2 ゴール定義
- 目的: ユーザー要望を機械可読な brief に固定し、後続 build/gate が再ヒアリングなしで動ける状態を作る
- 背景: elicit→build の handoff が構造化されないと、宣言型 L5 の材料 (goals/checklist) が脱落し、生成が AI 創作か再ヒアリングに依存する
- 達成ゴール: `schemas/prompt-brief.schema.json` に準拠し goals (成果状態) と checklist (item+judgement) を含む brief が `eval-log/prompt-brief.json` に保存され、Gate 1 提示可能になっている

### 5.3 完了チェックリスト (ゴール到達の停止条件)
- [ ] brief が `schemas/prompt-brief.schema.json` の検証を通過している (共通 required + モード別 if/then/else 充足・未知フィールドなし)
- [ ] prompt_name が `[a-z][a-z0-9-]*` (60 文字以内) で、skill 紐付け時は responsibility_id が `R[0-9]+` 形式である
- [ ] skill 紐付け時は target_skill が実在しその responsibilities[].id に当該 R-id が存在し、standalone 時は output_path がユーザー指定で確定し R-id が混入していない
- [ ] goals の全項目が観測可能な成果状態 (完了形) で書かれ、手順列挙を含まない
- [ ] checklist の全項目が item+judgement を持ち、第三者が YES/NO で判定できる
- [ ] trigger_conditions が非空で、各項目 80 文字以内 (要素原子性) である
- [ ] boundary が 200 文字以内で「やらないこと」を 1 文で明示している
- [ ] format=md (既定) または明示理由付きで yaml/json/xml である
- [ ] output_language=ja, parameter_language_exception=true である
- [ ] 未確定事項が AI 最尤仮説で補完され、補完した仮定が open_questions に記録されている (人間差し戻しマーカーが brief に存在しない)

### 5.4 実行方式
- 固定手順を持たない (l5-contract v2.0.0)。5.2 ゴール定義と 5.3 完了チェックリストを唯一の指針とし、現状評価 → 手順を都度立案 → 実行 → 検証 → 中間成果物アンカー記録 → 全項目充足まで反復する (6 ステップ・Step 5=Anchor。上限: Layer 4 の最大反復回数)
- 決定論操作 (Skill(run-prompt-elicit) 委譲・schema 検証・Write 先) は Layer 3 のツール定義と Layer 6 の接続契約に従う
- 不足情報はユーザーへ追加質問せず AI 最尤仮説で補完し、仮定を open_questions に記録する

## Layer 6: オーケストレーション層

### 6.1 上位 skill との接続
- 呼び出し元: run-prompt-create (Step 1)
- 後続 phase: gate-review (Gate 1)

### 6.2 並列性
- 単発実行 (対話 / batch どちらでも)

## Layer 7: UI / 提示層

### 7.1 ユーザー提示形式
- 対話モード: AskUserQuestion 連鎖
- batch モード: JSON のみ

### 7.2 言語
- 本文: 日本語 (パラメーター名 / schema key は英語のまま)

---

## 出力指示

LLM は run-prompt-elicit を呼び出し、ユーザー要望から prompt-brief.json を構築する。
出力は schemas/prompt-brief.schema.json 準拠の JSON のみ (eval-log/prompt-brief.json へ保存)。
余計な前置き・思考過程出力は禁止。
