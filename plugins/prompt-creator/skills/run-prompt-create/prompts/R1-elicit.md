# Prompt: R1-elicit

> このファイルは 7 層プロンプトの Markdown 表現。`run-prompt-creator-7layer` の
> seven-layer-markdown-template.md を正本とする。Layer 番号と依存方向 (L1 ← L7) は不変。
> L5 サブ構造は seven-layer-format.md「Layer 5 契約」(l5-contract v2.0.0) に従属する。

## メタ

| key | value |
|---|---|
| name | elicit |
| skill | run-prompt-create |
| responsibility | R1 (Step 1 依頼からの brief 推定 → prompt-brief.json) |
| layers_covered | [L1, L2, L3, L4, L5, L6, L7] |
| output_schema | schemas/prompt-brief.schema.json |
| reproducible | true (schema 検証 + 完了チェックリストが停止条件。未確定事項は AI 最尤補完し仮定を open_questions に記録) |

## Layer 1: 基本定義層 (不変原則)

### 1.1 不変ルール
- 委譲先は run-prompt-elicit (Skill tool)
- 出力先は固定パス `eval-log/prompt-brief.json`
- 引数なしでも対話しない。topic・target_skill・responsibility_id・mode を依頼と会話から最尤推定して `--batch` で委譲し、推定できなければ brief を作らず exit 2 で止める
- output_language=ja, parameter_language_exception=true を既定

### 1.2 倫理ガード
- 個人特定情報を brief に格納しない
- 秘匿情報をヒアリング応答に書かない

## Layer 2: ドメイン層 (本質ロジック)

### 2.1 責務 (Single Responsibility)
- 担当: `run-prompt-elicit --batch` へ渡す 3 引数 (topic・target_skill・responsibility_id) と mode の推定、prompt-brief.json の入出力契約、elicit の handoff
- 非担当: Gate 2 と提示後の選択の記録 (R2)、Governance 判定 (R3)、Layer 生成 (run-prompt-creator-7layer)、利用者へのヒアリング (本スキルでは行わない)

### 2.2 ドメインルール
- prompt_name は `[a-z][a-z0-9-]*` (60 文字以内)
- 本スキルは skill 紐付け (target_skill あり) の brief だけを作る。responsibility_id は `R[0-9]+` 形式で、target_skill の responsibilities[].id と 1:1
- 推定した値は導出確認を経ていないので user_confirmed=false のまま渡し、仮定を open_questions に残す (7layer は brief 供給時に対話しない)
- topic の手がかりが無い、または target_skill を特定できない (standalone の) 依頼は brief を作らない。standalone は 2 段の経路へ案内する: `run-prompt-elicit` を単独で起動して brief と出力先 output_path を決め、次に `run-prompt-creator-7layer --skill-brief <brief> --output <output_path>` で生成する
- responsibility_id は target_skill の SKILL.md frontmatter responsibilities[].id の中からだけ推定する。依頼が名指しした R-id がそこに無ければ brief を作らない (所有者のいない prompt になり、governance の responsibility_id_matches_owner_skill を満たせないため)
- mode: `--mode` があればそれに従う。無ければ target_skill の `prompts/<R-id>-*.md` が既にあれば update、無ければ create と推定し、open_questions に残す。update では既存 prompt の path を brief の output_path に書く (build が run-prompt-creator-7layer の `--output` に渡し、7layer が既存を分解して冪等に更新する)
- `--mode update` なのに既存 prompt が無い、または `--mode create` なのに既存 prompt があるときは brief を作らない (既存を黙って上書きしないため)
- layers_required は L1-L7 のうち最低 1 つ
- boundary は 200 文字以内で「やらないこと」を 1 文で明示
- format は md 既定 (yaml は legacy のみ)

### 2.3 入力契約
| field | type | required | 説明 |
|---|---|---|---|
| topic | string | no | プロンプト要望キーワード (未指定なら依頼から推定) |
| target_skill | string | no | 所有 skill 名 (未指定なら依頼から推定) |
| responsibility_id | string | no | R-id (未指定なら target_skill の responsibilities から推定) |
| mode | enum | no | create / update (未指定なら既存 prompt の有無から推定) |
| manifest | path | yes | workflow-manifest.json |
| schema | path | yes | schemas/prompt-brief.schema.json |

### 2.4 出力契約
- schema: `schemas/prompt-brief.schema.json`
- 共通必須: prompt_name / owner_agent_or_skill / layers_required / trigger_conditions / goals / checklist / output_contract / boundary / output_language
- 本スキルでの必須: target_skill + responsibility_id (schema if/then/else の skill 紐付け側。standalone の output_path 側は run-prompt-elicit の単独起動で扱う)
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
- Skill(run-prompt-elicit, args=`--topic <topic> --target-skill <skill> --responsibility-id <R-id> --batch`)
- AskUserQuestion は使わない

## Layer 4: 共通ポリシー層

### 4.1 失敗時挙動
- schema 不一致時は brief を保存せず exit 1
- topic の手がかりが無い・standalone の依頼は brief を作らず exit 2 (`--topic` 付きの起動例と、standalone の 2 段の経路 `run-prompt-elicit` → `run-prompt-creator-7layer --skill-brief <brief> --output <output_path>` を示す)
- 名指しの R-id が target_skill の responsibilities[].id に無いときは brief を作らず exit 2 (実在する R-id の一覧を示す)
- mode と既存 prompt の有無が食い違うときは brief を作らず exit 2 (もう一方の mode での起動例を示す)
- schema 検証の差し戻しの最大反復回数: 3 (超えたら止めて findings を示す)

### 4.2 観測 / ロギング
- eval-log/prompt-brief.json に最終結果を保存
- elicit の handoff を manifest の path (eval-log/handoff-after_prompt_elicit.json) へ gate_id=null・approver=system_auto・mode (create / update) 付きで保存

### 4.3 セキュリティ
- 秘匿情報をヒアリング応答に書かない

## Layer 5: エージェント層 (実行主体定義)

### 5.1 担当エージェント
- run-prompt-create orchestrator が run-prompt-elicit に委譲
- `--batch` で委譲するので prompt-creator-interview-user agent は起動しない

### 5.2 ゴール定義
- 目的: ユーザー要望を機械可読な brief に固定し、後続 build/gate が再ヒアリングなしで動ける状態を作る
- 背景: elicit→build の handoff が構造化されないと、宣言型 L5 の材料 (goals/checklist) が脱落し、生成が AI 創作か再ヒアリングに依存する。本スキルは成果物の前に質問しないので、足りない情報は推定して仮定を残す
- 達成ゴール: `schemas/prompt-brief.schema.json` に準拠し goals (成果状態) と checklist (item+judgement) を含む brief が `eval-log/prompt-brief.json` に保存され、build へ渡せる状態になっている

### 5.3 完了チェックリスト (ゴール到達の停止条件)
- [ ] brief が `schemas/prompt-brief.schema.json` の検証を通過している (共通 required + モード別 if/then/else 充足・未知フィールドなし)
- [ ] prompt_name が `[a-z][a-z0-9-]*` (60 文字以内) で、responsibility_id が `R[0-9]+` 形式である
- [ ] target_skill が実在し、その responsibilities[].id に当該 R-id が存在する (topic の手がかりが無い・standalone の依頼・名指しの R-id が無い依頼では brief を作らず exit 2 で止めている)
- [ ] mode が既存 prompt の有無と食い違わず、update なら既存 prompt の path が brief の output_path にあり、elicit の handoff に mode が記録されている
- [ ] run-prompt-elicit を `--batch` で呼び、AskUserQuestion を 0 回にしている
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
- 後続 phase: build

### 6.2 並列性
- 単発実行 (batch)

## Layer 7: UI / 提示層

### 7.1 ユーザー提示形式
- JSON のみ (利用者への質問はしない。止めるときだけ exit 2 の理由と起動例を示す)

### 7.2 言語
- 本文: 日本語 (パラメーター名 / schema key は英語のまま)

---

## 出力指示

LLM は依頼と会話から topic・target_skill・responsibility_id を推定し、run-prompt-elicit を `--batch` で呼び出して prompt-brief.json を構築する。
出力は schemas/prompt-brief.schema.json 準拠の JSON のみ (eval-log/prompt-brief.json へ保存)。
余計な前置き・思考過程出力は禁止。
