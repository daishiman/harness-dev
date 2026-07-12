---
name: run-skill-elicit
description: Skill要望をbrief.jsonに固めたいとき、対話形式でrequirementsを収集したいときに使う。
disable-model-invocation: false
user-invocable: true
argument-hint: "[topic?]"
arguments: [topic]
allowed-tools:
  - Read
  - Write
kind: run
prefix: run
effect: local-artifact
owner: team-platform
since: 2026-05-18
version: 0.1.0
# context-budget: このスキルはヒアリングのみ。設計書は06章と13章だけを参照する。
# auto-backfilled by backfill-source-tier.py (doc/21)
source: doc/ClaudeCodeスキルの設計書/
source-tier: internal
last-audited: 2026-05-19
audit-trigger: quarterly
responsibility_refs:
  - prompts/R1-elicit.md
schema_refs:
  - ../run-skill-create/schemas/skill-brief.schema.json
manifest: workflow-manifest.json
feedback_contract: # per-skill 評価基準(SSOT=scripts/feedback_contract_ssot.py)
  max_iterations: 3
  criteria:
    - id: IN1
      loop_scope: inner
      text: eval-log/skill-brief.json が固定パスに出力され skill-brief.schema.json に準拠し必須フィールド skill_name prefix hierarchy_level trigger_conditions output_contract boundary が全て確定している
      verify_by: lint
    - id: IN2
      loop_scope: inner
      text: prefix が ref run wrap assign delegate の5分岐決定木で確定し条件付き必須(wrap は base_skill delegate は delegate_agent L2 は rubric_refs)が埋まり trigger_conditions が動詞ベース2〜3個に収まっている
      verify_by: lint
    - id: OUT1
      loop_scope: outer
      text: 既出回答から導出可能な値を再質問せず AI が埋め設計用語を直接質問せず対話を5問以内に収め判断が分かれる細部のみ open_questions(escalate)へ退避しユーザーへ代理決定していない
      verify_by: elegant-review
---

# run-skill-elicit

## Purpose & Output Contract

ユーザーの曖昧な要求を構造化し、`run-build-skill` へ渡す要件定義（brief）を作る。

**入力**: topic (任意。省略時は対話形式で確認)
**出力**: `eval-log/skill-brief.json` (固定パス。プロジェクトルート基準。正本スキーマ `../run-skill-create/schemas/skill-brief.schema.json` に準拠)

含むフィールド:
```
skill_name        : <kebab-case>
prefix            : ref|run|wrap|assign|delegate              # 01a Step3 5 prefix
role_suffix       : null | generator|evaluator|contributor|delegate
kind              : run|ref|assign|wrap|delegate              # frontmatter kind (旧フィールド、prefixと一致が原則)
hierarchy_level   : L0|L1|L2                                  # 01a Step4b L0/L1/L2階層
trigger_conditions: [2〜3個の動詞ベース条件]
output_contract   : <成果物の形と完了条件>
goal              : <達成すべき最終状態を観測可能な完了形1文で>        # ゴールシーク用 (実行系で推奨)
purpose_background: <なぜこのゴールか (目的・背景)>                     # ゴールシーク用
checklist         : [ゴール達成の受入基準 (二値判定可能)]              # ゴールシーク用 (実行系で推奨)
key_constraints   : [制約事項]
boundary          : <このSkillが「やらない」ことを1文で>     # 01 設計思想 Boundary要素
deterministic_checks: [script/hook/CIへ寄せる決定論的検査]
external_systems  : [MCP/API/CLI候補の外部システム]
needs_independent_context: true|false                       # Subagent/Agent Team要否
needs_lifecycle_enforcement: true|false                     # Hook要否
cli_tools         : [利用予定CLI]
mcp_tools         : [利用予定MCP tool/resource]
placement_candidates: [Skill|Subagent|Agent Team|Hook|MCP|CLI|API|script]
base_skill        : null | <wrap対象のbase Skill名>          # prefix=wrap時必須
delegate_agent    : null | <委譲先agent ID>                  # prefix=delegate時必須
rubric_refs       : [L0/L1の参照rubric Skill名]              # L2時必須
open_questions    : [OPEN_QUESTION(escalate)としてユーザーに返す未確定事項]
cross_platform    : true|false                              # Mac/Windows両対応か (11章・14章 cross-platform run-* 雛形)
os_preamble_required: true|false                           # OSプリアンブル (!`uname -s 2>/dev/null || ver`) 要否
knowledge_loop    : null | {pattern, categories, source_kind} # Loop A: 生成スキルにナレッジ蓄積/検索/§12機構を組み込むか (with-knowledge combinator)
consult_build_knowledge: true|false                         # Loop B: 作成時に harness-creator 蓄積知見を参照するか (既定 true)
```

**完了条件**: skill_name / prefix / hierarchy_level / trigger_conditions / output_contract / boundary が全て確定。`prefix=wrap` なら base_skill、`prefix=delegate` なら delegate_agent、`hierarchy_level=L2` なら rubric_refs も必須。

## Key Rules

1. **質問は最大5個まで**: 対話は5問以内で brief を完成させる。超過分は open_questions として残す。
2. **kind 確定チェック**: 辞書型(ref)か手順型(run/assign)かを最初に確認する。
3. **trigger 2〜3個**: description の Use when 句候補を2〜3個に絞る。
4. **open_questions**: 設計判断が分かれる細部は OPEN_QUESTION(escalate) として明示して残す (TODO(human) ラベル使用は禁止)。
5. **handoff**: 完成した brief は `run-build-skill` の入力として引き渡す。

## ゴールシーク実行

### ゴール (Goal)

ユーザーの曖昧な要求が、`schemas/skill-brief.schema.json` 準拠の `eval-log/skill-brief.json` として構造化され、必須フィールド (skill_name/prefix/hierarchy_level/trigger_conditions/output_contract/boundary、条件付き base_skill/delegate_agent/rubric_refs) が確定し、`run-build-skill` へ渡せる状態になっている。

### 目的・背景 (Why)

build へ渡る brief の品質が後工程全体の質を決める。曖昧さは AI が最尤仮説で補い、判断が分かれる細部のみ open_questions に残す。質問の連打や手順固定はユーザー負担を増やすため、未確定フィールドを最小問数で埋めるゴールへ収束させる。

### 完了チェックリスト (Checklist)

- [ ] `eval-log/skill-brief.json` が固定パス (プロジェクトルート基準) に Write 出力され、`schemas/skill-brief.schema.json` (`../run-skill-create/schemas/skill-brief.schema.json`) を満たす
- [ ] 必須フィールド skill_name / prefix / hierarchy_level / trigger_conditions / output_contract / boundary が全て確定
- [ ] prefix は 5 分岐 (ref/run/wrap/assign/delegate) を全網羅した決定木で確定 (wrap/delegate の聞き忘れなし)。`prefix=wrap`→base_skill、`prefix=delegate`→delegate_agent、`hierarchy_level=L2`→rubric_refs (空は禁止) も埋まっている
- [ ] trigger_conditions が動詞ベース 2〜3 個に整理されている (4 個以上は不可)
- [ ] 実行系 (prefix≠ref) の場合 goal / purpose_background / checklist が brief に埋め込まれている (判定不能表現・手順そのものは項目化しない)。ref は skip
- [ ] placement_candidates と決定論的 hint (Subagent/Agent Team→needs_independent_context/with_subagent_hint、Hook→needs_lifecycle_enforcement/with_hooks。いずれも正本スキーマ定義済み boolean) が設定されている
- [ ] cross_platform / os_preamble_required が確認済み
- [ ] ナレッジループ要否を判定済み (ref-knowledge-loop の5条件に1つ以上該当→`knowledge_loop.pattern` 設定、非該当→null)。`consult_build_knowledge` (既定true) の場合は蓄積知見を参照し設計へ反映している
- [ ] 対話は 5 問以内に収め、超過・判断分岐する細部は open_questions (OPEN_QUESTION(escalate) ラベル) に記録されている

### ゴールシークループ

正本 `../run-build-skill/references/goal-seek-paradigm.md` の 6 ステップ (現状評価→手順生成→実行→検証→Anchor Step→反復/差し戻し) に従う。本スキル固有の差分:

- **未達評価の単位は brief フィールド**: チェックリスト未充足フィールドを、下記「局面カタログ」を参考に 1 問ずつ (連打禁止) 埋める。スキーマ違反 (必須欠落) があれば再質問。
- **仮想ヒアリング**: 既出回答から導出できる値は質問せず AI が埋め、不足のみ open_questions へ。設計用語 (prefix/hierarchy_level/boundary) は直接質問せず brief 確認画面でのみ開示。
- **handoff**: 完成 brief を `run-build-skill` / `run-skill-create` の入力へ引き渡す。
- 出力先: `mkdir -p eval-log` 後 `eval-log/skill-brief.json` を Write。
- **重複回避**: 汎用タスク用 `run-goal-elicit` / `goal-spec.json` は呼ばない。本スキルの checklist は brief 内文字列配列に直接埋め込む。

### 局面カタログ (順序は都度判断)

未達フィールドに応じて以下を使い分ける。番号は参照用であり固定実行順ではない。

#### 蓄積知見の参照 (Loop B / build-time)

`consult_build_knowledge` が true (既定) のとき、topic が分かった直後に harness-creator 自身の蓄積知見を検索し、過去の設計判断・パラダイム・落とし穴を当ヒアリングの初期仮説に反映する (質問を増やさず AI 内部で活用する)。

```bash
# パスはプロジェクトルート基準 (eval-log/ 出力と同じ規約)
python3 plugins/harness-creator/skills/run-build-skill/templates/knowledge-skeleton/scripts/search_knowledge.py \
  --dir plugins/harness-creator/knowledge/ --query "<topic と要求の要約>" --limit 5
```

- ストアは harness-creator 自身の `plugins/harness-creator/knowledge/` (正本)。スクリプトは複製せずテンプレ正本を `--dir` 指定で実行する (SSOT)。
- 上位ヒットは prefix 推定・boundary・既知の落とし穴回避の根拠として使う。ユーザーには結論のみ brief 確認画面で開示する。
- 採否は brief 完成後に記録する (下記「活用ログ記録」)。検索 0 件・スクリプト不在でも `consult_build_knowledge=false` 相当で続行 (ヒアリングを止めない)。

#### topic 確認
topic 指定ありなら要約を 1 文に。なしなら「どんな作業を自動化したいですか？」。

#### Onboarding mode（初学者向け3問）

設計用語に不慣れなユーザー向けの簡易モード。prefix 判定ウィザードの前にまずこの3問で意図を取る。
**設計用語（prefix / hierarchy_level / boundary）は直接質問しない**。これらは brief 生成時の確認画面でのみ開示する。

- **Q1（What）**: 何を自動化したいですか？ 自然言語で1行どうぞ。
- **Q2（Who）**: 誰がこれを呼びますか？
  - (a) 自分のみ
  - (b) チームで共有
  - (c) Claude が自動で（人手を介さず）
- **Q3（Side-effect）**: 副作用はありますか？
  - (a) read-only（ファイル参照のみ、書き込みなし）
  - (b) 軽い書き込み（ローカルファイル生成・更新）
  - (c) 強い書き込み・外部呼び出し（API実行・外部agent委譲・破壊的操作）

#### Decision tree（裏側で prefix を自動推定）

Q2/Q3 の組み合わせから prefix を推定する。ユーザーには結果のみを brief 確認画面で提示する。

1. **Q3=(a) read-only かつ Q2=(c) Claude自動** → `ref-`（知識参照、`disable-model-invocation` は文脈次第）
2. **Q3=(a) read-only かつ Q2=(a)/(b)** → `ref-`（ユーザー直呼びが必要なら `run-*-cheatsheet` に分離）
3. **Q3=(b) 軽い書き込み かつ Q2=(a)/(b)** → `run-`（user-invocable workflow）
4. **Q3=(b) 軽い書き込み かつ Q2=(c) Claude自動 かつ「親Skillから呼ばれる」** → `assign-*-generator`
5. **Q3=(b) 軽い書き込み かつ「採点・検証が主目的」（write 不要）** → `assign-*-evaluator`
6. **Q3=(c) 強い書き込み かつ「既存Skillに preset を被せる」** → `wrap-`（base_skill を追問）
7. **Q3=(c) 強い書き込み かつ「別 agent / 別 context へ委譲」** → `delegate-`（delegate_agent を追問）
8. **Q3=(c) 強い書き込み かつ上記以外** → `run-`（user-invocable workflow）

推定結果が複数候補に該当する場合は open_questions に積み、prefix 判定ウィザードで確定する。

#### prefix 判定ウィザード (5分岐)

01a Step3 の 5 prefix を**全て網羅する決定木**で順に確認 (1問ずつ):

1. 「このSkillは**知識参照のみ**ですか? (Read-only、副作用なし)」
   - Yes → `prefix=ref` 確定 → role_suffix 判定へ
2. 「**既存Skillの preset / 派生**として被せたいですか?」
   - Yes → `prefix=wrap` → `base_skill` を質問
3. 「**外部LLM / 別agent への委譲**が主目的ですか?」
   - Yes → `prefix=delegate` → `delegate_agent` を質問
4. 「**親Skillから呼ばれる内部worker** (forked context、artifact生成/採点/lint等) ですか?」
   - Yes → `prefix=assign`
5. 上記いずれも No → `prefix=run` (user-invocable workflow) 確定

#### role_suffix 判定 (assign-*の場合のみ)

prefix=assign の場合のみ:
「内部役割は何ですか? `generator/evaluator/contributor/delegate` から選択してください」
→ `role_suffix` を確定。
prefix=run の場合は原則 `role_suffix=null` とし、生成者・評価者・委譲者を分けたい場合は `assign-*` または `delegate-*` へ責務分割する。

#### hierarchy_level 判定

「このSkillは **L0 (共通基準) / L1 (技術・ドメイン特化) / L2 (案件固有)** のどれですか?」
- L2 を選んだ場合: 「参照する L0/L1 の rubric Skill 名を列挙してください」→ `rubric_refs` 確定。
- L2 で rubric_refs が空のままなら open_questions に積む。

#### trigger 抽出

「このスキルをいつ呼びますか？ 動詞ベースで2〜3個の状況を教えてください」
→ ユーザーの回答から trigger_conditions を2〜3個に整理。

#### output contract 確認

「完了したとき、何が出力されていればOKですか？ ファイル名・フォーマット・完了条件を教えてください」

#### ゴール・チェックリスト抽出 (実行系のみ / ゴールシーク)

`prefix` が `ref` 以外（実行系）の場合、固定手順の代わりにゴールシークで動かすため、以下を brief に固定する（詳細 `../run-build-skill/references/goal-seek-paradigm.md`）:

- **goal**: output_contract の完了条件を「観測可能な完了形 1 文」に言い換える。
- **purpose_background**: なぜそのゴールか（topic とユーザー回答から要約）。
- **checklist**: ゴール達成の受入基準を二値判定可能な項目で 1 件以上。output_contract / key_constraints から導出してよい。

判定不能な表現（「丁寧に」等）や手順そのもの（「Edit で X」）はチェック項目にしない。新規質問は増やさず、既出回答から AI が導出する（不足のみ open_questions）。`ref` の場合はこの局面を skip。

> **重複回避**: ここで埋める `goal`/`checklist` は **skill-brief.json 内に直接埋め込む**（文字列配列の checklist）。汎用タスク用の `run-goal-elicit` / `goal-spec.json` は**呼ばない**。両者は対象（Skill 生成 vs 汎用タスク）も checklist 型も異なる別系統。

#### Boundary (責務境界) 確認

01 設計思想の 5要素モデル必須項目: 「このSkillが**やらないこと**を1文で教えてください」
→ `boundary` に格納。SRP / Bounded Context を明示する。

#### Layering 入力確認

05章の配置判断を brief に固定する。決定論的検査、外部システム、独立context要否、lifecycle強制要否、CLI/MCP候補を短く確認し、`placement_candidates` に Skill/Subagent/Agent Team/Hook/MCP/CLI/API/script の候補を残す。該当なしは空配列または false として明示する。

**Agent Team / Subagent 連動 hint の決定論的設定**（19章 factory 障害 #6 対応）:

| `placement_candidates` に含まれる値 | brief に追加するフィールド | build 側へ渡る効果 |
|---|---|---|
| `Subagent` | `needs_independent_context: true`, `with_subagent_hint: true` | run-build-skill に `--with-subagent` フラグを推奨。`agent-teams` category を必ず読む |
| `Agent Team` | `needs_independent_context: true`, `with_subagent_hint: true` | 上記に加え `placement_candidates` に `Agent Team` を残す。run-build-skill が 17 章 (Agent Teams) を必ず読み、`TaskCompleted` hook 配線も build skeleton に含める |
| `Hook` | `needs_lifecycle_enforcement: true`, `with_hooks: true` | run-build-skill に `--with-hooks` フラグを推奨。10 章を category=subagent-hook-integration で必ず読む |

これら 3 フィールド (`needs_independent_context` / `needs_lifecycle_enforcement` / `with_subagent_hint` / `with_hooks`) は全て正本スキーマ `../run-skill-create/schemas/skill-brief.schema.json` に boolean として定義済みであり、`additionalProperties:false` 下でも valid。`scripts/resolve-brief-to-category.py` の `CONDITIONAL_CATEGORIES` がこれらを読んで決定論的に 17 章 / 10 章を読むべき category として返し、LLM 主観依存を排除する。

> **注**: brief の `with_subagent_hint` / `with_hooks` は boolean の **build フラグ推奨シグナル** であり、`run-build-skill/schemas/build-flags.schema.json` の同名 object 型フラグ (`{enabled, ...}`) とは別レイヤーの別物。Agent Team は専用 boolean を設けず `placement_candidates: ["Agent Team", ...]` で表現する (resolve は Subagent/Agent Team いずれも `agent-teams` category へ同一に解決するため、片肺の死にフィールドを作らない)。

#### クロスプラットフォーム確認 (11章 / 14章)

「このSkillは **Mac と Windows の両方** で動作する必要がありますか？」
- **Yes** → `cross_platform=true` / `os_preamble_required=true` を brief に設定。
  run-build-skill は 11章 cross-platform `run-*` 雛形を採用し、14章 OS プリアンブル (``!`uname -s 2>/dev/null || ver` ``) を本文先頭に挿入する。
- **No（Macのみ）** → `cross_platform=false` / `os_preamble_required=false` (既定値のまま)。

> この質問は1問扱い。5問上限にカウントされる。prefix=ref や副作用なしの Skill では通常 No でよい。

#### ナレッジループ要否判定 (Loop A)

作成する Skill 自身が「知見を蓄積し実行時に検索して使う」必要があるかを判定する。正本判定は `../ref-knowledge-loop` の「knowledge/ を追加する5条件」(外部素材依存 / ペルソナ再現 / 知識10件以上 / 継続的蓄積 / 精度優先検索)。1つ以上該当する場合のみ `knowledge_loop` を設定する。

- 該当する → `knowledge_loop.pattern` を判定 (ウィザードは ref-knowledge-loop のパターン選択フロー):
  - 継続的に外部素材から蓄積 → `router-registry` (`source_kind` も確認: 議事録/動画/教材等)
  - 固定知識・ペルソナ再現 → `index-search`
  - 初期 `categories` 案 (kebab-case) を 1〜数件ヒアリングまたは AI 導出。
- 該当しない (静的 `references/` で足りる) → `knowledge_loop: null` (既定)。質問を増やさない。
- 設定時、build 側は `--with-knowledge <pattern>` フラグで `with-knowledge.patch` と `knowledge-skeleton/<pattern>/` を注入する。

#### 活用ログ記録 (Loop B / §12)

brief 確定後、Loop B 検索を行っていた場合は採否を記録し、harness-creator 自身の知見品質改善サイクル (§12) を回す。

```bash
python3 plugins/harness-creator/skills/run-build-skill/templates/knowledge-skeleton/scripts/record_usage.py --record \
  --dir plugins/harness-creator/knowledge/ --query "<topic 要約>" \
  --matched-ids "<検索ヒットid,...>" --used-ids "<実際に設計へ反映したid,...>" \
  --satisfaction helpful|neutral|unhelpful
```

検索を行わなかった (`consult_build_knowledge=false` / ヒット0件) 場合はスキップしてよい。

#### brief 生成 (JSON)

`eval-log/skill-brief.json` を Write で出力。プロジェクトルート基準の固定パス。スキーマ違反 (必須フィールド欠落) があれば再質問する。

```bash
# 出力先固定: eval-log/skill-brief.json
mkdir -p eval-log
# brief を JSON で書き出し (Writeツール経由)
echo "eval-log/skill-brief.json を生成。run-build-skill / run-skill-create に渡してください。"
```

## Gotchas

- **質問の連打禁止**: 1回のやり取りで複数の質問を並べない。1問ずつ確認する。
- **5 prefix を必ず全分岐網羅**: wrap/delegate を聞き忘れない (01a Step3 CE要件)。
- **副作用×採点の重複ケース**: 副作用ありかつ採点ありなら、`run-* (orchestrator) + assign-*-evaluator` に分割することを推奨し open_questions に明記。
- **trigger 過剰**: 4個以上は冗長。2〜3個に絞る (lint-skill-description.py の R1 と rubric FM-003 の合意値)。
- **L2 で rubric_refs 空は禁止**: L2 案件固有Skill は必ず L0/L1 の rubric を参照する (01a Step4b 一方向依存)。
- **wrap/delegate 必須フィールド**: base_skill / delegate_agent を埋め忘れない。
- **設計判断を代理決定しない**: 判断が分かれる細部はユーザーに返す（open_questions）。

## Additional Resources

- 索引正本 = frontmatter `schema_refs` (skill-brief.schema.json 正本) と `references/resource-map.yaml` (brief-template / ref-knowledge-loop / knowledge Loop B ストア / 設計書 01a Step3・06・29・13 の read_when 付き一覧)。
