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
effect: local-artifact
owner: team-platform
since: 2026-05-18
# context-budget: このスキルはヒアリングのみ。設計書は06章と13章だけを参照する。
# auto-backfilled by backfill-source-tier.py (doc/21)
source: doc/ClaudeCodeスキルの設計書/
source-tier: internal
last-audited: 2026-05-19
audit-trigger: quarterly
---

# run-skill-elicit

## Purpose & Output Contract

ユーザーの曖昧な要求を構造化し、`run-build-skill` へ渡す要件定義（brief）を作る。

**入力**: topic (任意。省略時は対話形式で確認)
**出力**: `eval-log/skill-brief.json` (固定パス。プロジェクトルート基準。`creator-kit/skills/run-skill-create/references/skill-brief-schema.json` に準拠)

含むフィールド:
```
skill_name        : <kebab-case>
prefix            : ref|run|wrap|assign|delegate              # 01a Step3 5 prefix
role_suffix       : null | generator|evaluator|contributor|delegate
kind              : run|ref|assign|wrap|delegate              # frontmatter kind (旧フィールド、prefixと一致が原則)
hierarchy_level   : L0|L1|L2                                  # 01a Step4b L0/L1/L2階層
trigger_conditions: [2〜3個の動詞ベース条件]
output_contract   : <成果物の形と完了条件>
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
open_questions    : [TODO(human)としてユーザーに返す未確定事項]
cross_platform    : true|false                              # Mac/Windows両対応か (11章・14章 cross-platform run-* 雛形)
os_preamble_required: true|false                           # OSプリアンブル (!`uname -s 2>/dev/null || ver`) 要否
```

**完了条件**: skill_name / prefix / hierarchy_level / trigger_conditions / output_contract / boundary が全て確定。`prefix=wrap` なら base_skill、`prefix=delegate` なら delegate_agent、`hierarchy_level=L2` なら rubric_refs も必須。

## Key Rules

1. **質問は最大5個まで**: 対話は5問以内で brief を完成させる。超過分は open_questions として残す。
2. **kind 確定チェック**: 辞書型(ref)か手順型(run/assign)かを最初に確認する。
3. **trigger 2〜3個**: description の Use when 句候補を2〜3個に絞る。
4. **open_questions**: 設計判断が分かれる細部は TODO(human) として明示して残す。
5. **handoff**: 完成した brief は `run-build-skill` の入力として引き渡す。

## Steps

### Step 1: topicの確認

topic が指定されていれば要約を1文に。指定なしなら「どんな作業を自動化したいですか？」と聞く。

### Onboarding mode（初学者向け3問）

設計用語に不慣れなユーザー向けの簡易モード。Step 2 の前にまずこの3問で意図を取る。
**設計用語（prefix / hierarchy_level / boundary）は直接質問しない**。これらは Step 5 の brief 確認画面でのみ開示する。

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

推定結果が複数候補に該当する場合は open_questions に積み、Step 2 の正式ウィザードで確定する。

### Step 2: prefix 判定ウィザード (5分岐)

01a Step3 の 5 prefix を**全て網羅する決定木**で順に確認 (1問ずつ):

1. 「このSkillは**知識参照のみ**ですか? (Read-only、副作用なし)」
   - Yes → `prefix=ref` 確定 → Step 2.5へ
2. 「**既存Skillの preset / 派生**として被せたいですか?」
   - Yes → `prefix=wrap` → `base_skill` を質問 → Step 2.5へ
3. 「**外部LLM / 別agent への委譲**が主目的ですか?」
   - Yes → `prefix=delegate` → `delegate_agent` を質問 → Step 2.5へ
4. 「**親Skillから呼ばれる内部worker** (forked context、artifact生成/採点/lint等) ですか?」
   - Yes → `prefix=assign` → Step 2.5へ
5. 上記いずれも No → `prefix=run` (user-invocable workflow) 確定

### Step 2.5: role_suffix 判定 (assign-*の場合のみ)

prefix=assign の場合のみ:
「内部役割は何ですか? `generator/evaluator/contributor/delegate` から選択してください」
→ `role_suffix` を確定。
prefix=run の場合は原則 `role_suffix=null` とし、生成者・評価者・委譲者を分けたい場合は `assign-*` または `delegate-*` へ責務分割する。

### Step 2.6: hierarchy_level 判定

「このSkillは **L0 (共通基準) / L1 (技術・ドメイン特化) / L2 (案件固有)** のどれですか?」
- L2 を選んだ場合: 「参照する L0/L1 の rubric Skill 名を列挙してください」→ `rubric_refs` 確定。
- L2 で rubric_refs が空のままなら open_questions に積む。

### Step 3: trigger 抽出

「このスキルをいつ呼びますか？ 動詞ベースで2〜3個の状況を教えてください」
→ ユーザーの回答から trigger_conditions を2〜3個に整理。

### Step 4: output contract 確認

「完了したとき、何が出力されていればOKですか？ ファイル名・フォーマット・完了条件を教えてください」

### Step 4.5: Boundary (責務境界) 確認

01 設計思想の 5要素モデル必須項目: 「このSkillが**やらないこと**を1文で教えてください」
→ `boundary` に格納。SRP / Bounded Context を明示する。

### Step 4.6: Layering 入力確認

05章の配置判断を brief に固定する。決定論的検査、外部システム、独立context要否、lifecycle強制要否、CLI/MCP候補を短く確認し、`placement_candidates` に Skill/Subagent/Agent Team/Hook/MCP/CLI/API/script の候補を残す。該当なしは空配列または false として明示する。

**Agent Team / Subagent 連動 hint の決定論的設定**（19章 factory 障害 #6 対応）:

| `placement_candidates` に含まれる値 | brief に追加するフィールド | build 側へ渡る効果 |
|---|---|---|
| `Subagent` | `needs_independent_context: true`, `with_subagent_hint: true` | run-build-skill に `--with-subagent` フラグを推奨 |
| `Agent Team` | `needs_independent_context: true`, `with_subagent_hint: true`, `agent_team_required: true` | run-build-skill が 17 章 (Agent Teams) を必ず読む。`TaskCompleted` hook 配線も build skeleton に含める |
| `Hook` | `with_hooks: true`, `needs_lifecycle_enforcement: true` | run-build-skill に `--with-hooks` フラグを推奨。10 章を category=subagent-hook-integration で必ず読む |

これにより `scripts/resolve-brief-to-category.py` が決定論的に 17 章 / 10 章を読むべき category として返し、LLM 主観依存を排除する。

### Step 4.7: クロスプラットフォーム確認 (11章 / 14章)

「このSkillは **Mac と Windows の両方** で動作する必要がありますか？」
- **Yes** → `cross_platform=true` / `os_preamble_required=true` を brief に設定。
  run-build-skill は 11章 cross-platform `run-*` 雛形を採用し、14章 OS プリアンブル (``!`uname -s 2>/dev/null || ver` ``) を本文先頭に挿入する。
- **No（Macのみ）** → `cross_platform=false` / `os_preamble_required=false` (既定値のまま)。

> この質問は1問扱い。5問上限にカウントされる。prefix=ref や副作用なしの Skill では通常 No でよい。

### Step 5: brief 生成 (JSON)

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

- `references/brief-template.md` — skill-brief の人間可読雛形 (参考用)
- `../run-skill-create/references/skill-brief-schema.json` — JSON 出力スキーマ正本
- `01a-build-flow.md` Step3 — 5 prefix 判定の正本表
- `06-classification-and-naming.md` — prefix / role-suffix 判定の詳細
- `29-multi-project-rubric-composition.md` — L0/L1/L2 階層と rubric_refs 一方向依存
- `13-checklists.md` — trigger / output contract のチェック
