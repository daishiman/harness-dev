---
name: run-skill-feedback
description: 既存スキルへの「こう直してほしい」要望を受け取って Notion 改善要望 DB にプッシュしたいとき、利用者発端のフィードバックループを起動したいときに使う。
triggers:
  - "スキルや機能を改善したいとき"
  - "プラグイン・スキルへの要望や不満があるとき"
disable-model-invocation: true
user-invocable: true
argument-hint: "[plugin?] [skill-name?]"
arguments: [plugin, skill_name]
arguments-optional: [plugin, skill_name]
allowed-tools:
  - Read
  - Bash(python3 *)   # Keychain 参照は notion_config が python 内から security を呼ぶので Bash(security *) は不要
  - Agent
  - Grep
  - Glob
kind: run
prefix: run
effect: external-mutation
runtime_root_policy: host-skill-path
external_mutation_guard: {runtime_ref: "plugin:skill-governance-adapters/scripts/build-external-mutation-guard.py", flow: "preview-confirm-authorize-execute-v1"}
owner: team-platform
since: 2026-05-25
version: 0.1.0
max_loops: 5
reference_refs:
  - plugins/harness-creator/skills/run-build-skill/references/goal-seek-paradigm.md
  - plugins/harness-creator/skills/run-skill-feedback/references/notion-submit-contract.md
schema_refs:
  - doc/notion-schema/skill-list.schema.json
  - doc/notion-schema/improvement-request.schema.json
responsibility_refs:
  - scripts/notion-submit-improvement.py
  - scripts/lint-feedback-protocol.py
  - workflow-manifest.json
script_refs:
  - scripts/notion-submit-improvement.py
  - plugins/harness-creator/scripts/notion_config.py
  - scripts/lint-feedback-protocol.py
source: doc/ClaudeCodeスキルの設計書/
source-tier: internal
last-audited: 2026-05-25
audit-trigger: on-change
manifest: workflow-manifest.json
completeness_exempt:
  - "prompts: 対話手順は doc/notion-schema/skill-list.schema.json#feedback_protocol 正本 (Notion §7 と同一) から本文に展開している (初見実行の自己完結性のため)。整合は scripts/lint-feedback-protocol.py で発火条件と参照経路を検証。prompt-creator の R-id 単位 7 層プロンプトは適用外 (二重定義禁止 [[project_ssot_dedup_mechanism]])。"
feedback_contract: # per-skill 評価基準(SSOT=scripts/feedback_contract_ssot.py)。content-review verdict の criteria_evaluated と突合
  activation_state: semantic_evaluator_started
  max_iterations: 3
  criteria:
    - id: IN1
      loop_scope: inner
      text: 発火条件と同定フローと対話項目が skill-list.schema.json の feedback_protocol を唯一の正本として派生し lint-feedback-protocol が SKILL.md と派生物の整合を exit0 で通過する
      verify_by: lint
    - id: IN2
      loop_scope: inner
      text: token は Keychain 既定(env NOTION_TOKEN は INTAKE_ALLOW_ENV_TOKEN=1 明示時のみ)で DB ID は key 別 env > .notion-config.json の順に notion_config 経由でのみ解決され lint-feedback-protocol の R8 が submit script について秘密を受ける CLI 引数の不在と NOTION_* env 直読みの不在と Authorization ヘッダを argv へ載せないことと出力呼び出し(print/write/logging)へ token の値を渡さないことを AST で検査し加えて notion_config の解決順そのものを実呼び出しの返り値で pin することを exit0 で検証する(実行時に Claude が応答へ書き写す経路は機械検査の外で Gotcha 3 の責務)
      verify_by: lint
    - id: IN3
      loop_scope: inner
      text: 対象プラグインが未登録なら find_plugin_page が改善要望ページ作成前に exit2 で fail-closed し孤児レコードが生成されない
      verify_by: script
    - id: OUT1
      loop_scope: outer
      text: 目的逆算の同定フローが省略されず利用者がプラグイン名やスキル名を知らない前提で目的ヒアリングと現状仕様提示を経て対象スキルが正しく同定され文脈ズレ要望を防ぐ設計になっている
      verify_by: elegant-review
    - id: OUT2
      loop_scope: outer
      text: 利用者発端のフィードバックループが摩擦最小で起動でき収集した構造化要望が improvement-request schema 準拠で時系列ログ性質(重複除去を AI 判定しない)を保つ妥当な対話設計である
      verify_by: evaluator
artifact_delivery:
  contract: artifact-delivery-v1
  state_machine:
    initial: artifact_created
    states: [artifact_created, minimal_guard_passed, artifact_presented, user_choice_recorded, semantic_evaluator_started, handoff_complete]
    transitions:
      - {from: artifact_created, event: minimum_guard_pass, to: minimal_guard_passed}
      - {from: minimal_guard_passed, event: present_actual_artifact, to: artifact_presented}
      - {from: artifact_presented, event: record_user_choice, to: user_choice_recorded}
      - {from: user_choice_recorded, event: accept-as-is, to: handoff_complete}
      - {from: user_choice_recorded, event: "light|standard|detailed", to: semantic_evaluator_started}
      - {from: semantic_evaluator_started, event: improvement_complete, to: handoff_complete}
    pre_choice_forbidden: [semantic-evaluator, task-fork, subagent, multi-worker, revise-loop]
    accept_contexts: {evaluator: 0, improver: 0}
  release: explicit-only
  exhaustive: explicit-only
---

## Runtime root contract

- `runtime_root_policy: host-skill-path` を適用する。
- Claude Codeでは `CLAUDE_PLUGIN_ROOT` をplugin rootとして使用する。
- Codexではホストが提示したこの `SKILL.md` のabsolute pathから、plugin manifestを持つ祖先を上方探索して論理 `PLUGIN_ROOT` を解決する。
- `cwd` からplugin rootを推測せず、literal placeholderをshellへ渡さない。各shell invocation内で解決済みabsolute pathを `PLUGIN_ROOT` に設定する。
- `prompts/` 配下はこのowner Skill契約を継承する。

## Pre-choice usable artifact execution

Purpose & Output Contractの最小の実成果物またはremote mutation previewをmain contextで作成する。effect別のparse/open・secret・irreversible・corrupt guardだけを実行し、現物path・digest・開き方またはpreview receiptを提示してからaccept-as-is/light/standard/detailedを記録する。accept-as-isはmutationを実行せずhandoff完了とし、後続sectionを実行しない。

## Post-choice selected improvement execution

以下の既存workflow・goal-seek・評価・修正sectionおよびexternal mutation safety wrapperはlight/standard/detailedが記録されて`semantic_evaluator_started`へ遷移した場合だけ実行する。actual mutationはcanonical preview→hook-confirm→authorize→execute wrapperだけを通し、release/exhaustiveは別の明示eventを必要とする。

<!-- external-mutation-guard-cli:v1 -->
### Canonical external mutation receipt flow (mandatory)

Never execute the external mutation argv directly. Replace every angle-bracket placeholder
with the reviewed value from this run; the central CLI fails closed on missing/invalid values.

```bash
python3 "${PLUGIN_ROOT:-${CLAUDE_PLUGIN_ROOT}}/../skill-governance-adapters/scripts/build-external-mutation-guard.py" preview --project-root "$PWD" --entrypoint-ref "plugin:<PLUGIN_NAME>/skills/<SKILL_NAME>/SKILL.md" --target-scope "<TARGET_SCOPE>" --diff-summary "<DIFF_SUMMARY>" --side-effect-summary "<SIDE_EFFECT_SUMMARY>" --command-json '<MUTATION_ARGV_JSON>'
```

Present that official preview output to the user. Only the exact user reply printed by `preview`
may trigger the registered `hook-confirm` producer. Then use the two returned receipt paths:

```bash
python3 "${PLUGIN_ROOT:-${CLAUDE_PLUGIN_ROOT}}/../skill-governance-adapters/scripts/build-external-mutation-guard.py" authorize --project-root "$PWD" --preview-receipt "<PREVIEW_RECEIPT_PATH>" --confirmation-receipt "<CONFIRMATION_RECEIPT_PATH>"
python3 "${PLUGIN_ROOT:-${CLAUDE_PLUGIN_ROOT}}/../skill-governance-adapters/scripts/build-external-mutation-guard.py" execute --project-root "$PWD" --authorization-receipt "<AUTHORIZATION_RECEIPT_PATH>" --command-json '<MUTATION_ARGV_JSON>'
```

Do not use an auto-approval flag or invoke the mutation command outside this receipt flow.
<!-- /external-mutation-guard-cli:v1 -->


# run-skill-feedback

> **配布注記**: 本 skill の `script_refs` / `schema_refs` は repo-root 配置 (`scripts/`, `doc/notion-schema/`) に依存する。distribution: repo-bundled 前提 (単独配布非対応)。

## Purpose & Output Contract

利用者が既存スキルに対して「こう直してほしい」と感じた瞬間に発火し、構造化フィードバックを Notion 改善要望 DB へ N:1 relation 付きでプッシュする。スキル一覧の `未対応要望数` rollup が自動更新され、優先度判断シグナルになる。

**責務境界**: 本 skill の責務は「要望の**収集**と優先度シグナル化」まで。収集した要望を実際の改善 (plugin-dev-planner の改善計画 → harness 再構築) へ繋ぐのは**人間ブリッジ** (`plugins/harness-creator/references/feedback-to-improvement-runbook.md` Stage 2-3)。本 skill も `未対応要望数` rollup も改善着手を自動発火しない (fail-open 回避のため Notion は機械 SSOT にしない設計)。

**前提**: 利用者はプラグイン名・スキル名を知らない。「何をしようとしていたか」という目的から逆算して対象を同定してから要望を収集する。

## 発火条件 (SSOT)

発火条件・対話項目・状態遷移は `doc/notion-schema/skill-list.schema.json` の `feedback_protocol` を唯一の正本 (SSOT) とする。本 SKILL.md / `scripts/notion-upsert-plugin.py` / Notion スキル一覧ページ本文 §7 の三者は全てこの正本から派生する。整合の保証範囲: 発火条件・参照経路は `scripts/lint-feedback-protocol.py` で機械検証、対話文面の逐語一致は対象外 (正本変更時は本文を手動同期する)。

具体的な発火条件 (schema `feedback_protocol.firing_conditions` 抜粋):
- プラグインを使って「ここが分かりにくい」と感じた
- 「こう直してほしい」「この挙動はバグでは」と思った
- プロンプト出力品質に不満 / ドキュメントの誤記を見つけた
- 新機能・挙動変更の要望が浮かんだ

発火条件の追加・変更は **schema を編集 → lint 通過 → 派生物 (triggers / SKILL.md / 本文) を同期** の順で行うこと。

**入力**:
- `plugin` (任意): 対象プラグイン名。省略時は identification_step で目的から逆算して同定する
- `skill_name` (任意): プラグイン内の個別スキル名。省略時も identification_step で同定する

**出力**: Notion 改善要望 DB の新規ページ 1 件 (URL を返す)

**冪等性**: 改善要望はタイトルが重複しても別レコードとして扱う(時系列ログとしての性質)。重複除去は人手で実施。

## Key Rules

1. **SSOT 厳守**: 発火条件・同定フロー・対話項目は `doc/notion-schema/skill-list.schema.json` の `feedback_protocol` を唯一の正本とし、本 SKILL.md / スクリプト / Notion 本文の三者は派生のみ。
2. **目的逆算同定を必ず先行させる**: `plugin` 引数があっても identification_step を省略しない。目的確認と現状仕様の提示を経てから要望収集へ進むこと (孤児・文脈ズレ防止)。
3. **存在確認は本投入内の fail-closed に委ねる**: 未登録プラグインは `find_plugin_page()` が改善要望ページ作成**前**に exit 2 で止めるため孤児レコードは出ない。**`--dry-run` は引数を印字して return するだけで Notion に触れないので登録確認には使えない** (未登録でも必ず成功する)。exit 2 (未登録) を見たら `run-build-skill --notion-register` を案内して中断。**exit 3 は別事象**で、登録操作では解決しない — token の有効期限・integration の DB 共有・ネットワークを確認させる。切り分けは query か create かではなく**原因が誰の手元にあるか**: exit 2 = 入力が Notion 側の実体と噛み合っていない (未登録・config 不在) ので利用者が直せる、exit 3 = API へ到達/認可できない (401/403/5xx・curl 失敗) ので直せない。**改善要望ページ作成 (`POST /v1/pages`) の失敗も exit 3** に入る。詳細は `references/notion-submit-contract.md` §3-§4。
4. **token / DB ID は notion-config SSOT 経由**: `plugins/harness-creator/scripts/notion_config.py` が解決順を一元管理する。token は **Keychain 既定** (env `NOTION_TOKEN` は `INTAKE_ALLOW_ENV_TOKEN=1` 明示時のみ)、DB ID は key 別 env (`NOTION_DB_SKILL_LIST` / `NOTION_DB_IMPROVEMENT_REQUEST`) > `.notion-config.json`、config path は env `NOTION_CONFIG_PATH` > repo-root > plugin-root。**CLI 引数で token / DB ID を渡す経路は無い**。token / DB ID をコンテキストに乗せない。詳細は `references/notion-submit-contract.md` §1。
5. **重複除去は人手**: 時系列ログ性質を保つため AI は重複判定せず投入する。
6. **people 型は UI で人手追加**: API 経由でメール宛指定不可のため起票者/担当者は完了通知時に案内。

## ゴールシーク実行

固定手順は書かず、ゴール+チェックリストへ向け都度手順を生成・反復する。正本: `../run-build-skill/references/goal-seek-paradigm.md`。

### ゴール (Goal)

利用者の「こう直してほしい」要望が、`doc/notion-schema/improvement-request.schema.json` 準拠の構造化フィードバックとして Notion 改善要望 DB にプッシュされ、スキル一覧 DB の `未対応要望数` rollup が更新され、起票完了通知 (ページ URL + 人手追加項目案内) がユーザーに返された状態になっている。

### 目的・背景 (Why)

利用者発端のフィードバックループを摩擦最小で起動するため。要望は時系列ログとして 1:N で集約し、優先度判断シグナル (`未対応要望数` rollup) に直結させる。固定手順では「対象プラグイン未登録」「token 未設定」などの実行時文脈に脆いため、未達条件を局面カタログから都度埋める。

### 完了チェックリスト (Checklist)

- [ ] 「どんな作業をしていたか」をユーザーに聞き、目的から対象プラグイン・スキルを同定済み
- [ ] 同定したスキルの SKILL.md を Read し、現状仕様をユーザーに提示して文脈確認済み
- [ ] 要望タイトル / 種別 / 内容 / 優先度 / 重要度 が `feedback_protocol` 必須項目として収集済み
- [ ] 本投入が exit 0 かつ `[CREATED]` 行を出している (exit 2 + `[ERR] スキル一覧に ... 存在しません` なら未登録。案内して中断)
- [ ] Notion 改善要望 DB に 1 ページが新規作成され `[CREATED]` の page id から URL を組み立てて提示できている
- [ ] スキル一覧 DB との N:1 relation が貼られ `未対応要望数` rollup が増分している
- [ ] 完了通知に「起票者・担当者は Notion UI で人手追加」案内が含まれている
- [ ] token / DB ID は `notion_config.require_or_skip()` 経由 (token=Keychain 既定 / DB ID=key 別 env > `.notion-config.json`) で取得しており context に露出していない
- [ ] `[SKIP] skill-list / improvement-request db_id missing` (exit 0 の fail-open) を成功と誤読していない

### ゴールシークループ

正本 6 ステップ (現状評価→手順生成→実行→検証→Anchor Step→反復) に従う。Anchor Step では各周回末に中間成果物スナップショットを eval-log に記録し、original_goal からのドリフトを検知する。本スキル固有差分: 未達評価の単位はチェックリスト項目。投入失敗 (404/401/schema 違反) 時は原因を `feedback_protocol` SSOT に照らして特定し再実行。下記局面は順序固定ではなく未達条件から都度選ぶ。

### ゴールシーク配線

- **progress ログ**: `eval-log/run-skill-feedback-intermediate.jsonl`（周回ごとに append）
- **goal-spec**: `eval-log/goal-spec.json`（初回起動時に original_goal を記録）
- **コンテキスト分離**: 多フェーズ実行時は SubAgent へ fork（allowed-tools: Agent）
- **打ち切り**: `max_loops: 5` を超えたら open_issues に記録して human_review へ差し戻す
- **ドリフト検知**: 各周回末に original_goal_hash と現 goal-spec の hash を比較し乖離 > 閾値なら Anchor Step を発火する

## 局面カタログ (順序は都度判断)

### 対象スキルの同定 (目的ヒアリング)

ユーザーはプラグイン名・スキル名を知らない前提で、以下の順で進める。

**Step 1 — 目的を聞く**

まず自由形式で一言聞く:

> 「どんな作業をしているときに、どんなことを感じましたか？」
>
> （例: 契約書を作ろうとしたら途中で止まった / スキルを作ろうとしたら出力がおかしかった）

**Step 2 — 全スキルを収集してマッチング**

Grep ツールで全 SKILL.md の frontmatter を集める (allowed-tools に `Bash(grep *)` は無い。シェルへ落とさない):

- Grep: `pattern="^(name|description):"`, `glob="plugins/*/skills/*/SKILL.md"`, `output_mode="content"`, `-n=true`

> glob を `**/SKILL.md` にしない。ワークスペース全体では 229 件ヒットし、その大半は `.claude/skills/` への projection・`.worktrees/` 配下・plan 生成物で、**同一スキルが別パスで何度も現れる**。候補提示の段で同じ名前が並ぶと利用者は選べない。`plugins/*/skills/*/SKILL.md` に絞っても、量産プラグインへ配備された `run-skill-feedback` のように 1 スキルが複数プラグイン下に現れる正当な重複は残る (実体 94 に対し 116 ヒット) ので、**候補は name で名寄せしてから 1〜3 件に絞る**。



ユーザーの回答のキーワード（動詞・対象物・症状）とスキルの description を照合し、候補を 1〜3 件に絞る。

**Step 3 — 候補を提示して確認**

候補が 1 件の場合:
> 「○○（〜〜するためのスキル）のことでしょうか？」

候補が複数の場合:
> 「以下のどれに当てはまりますか？
> 1. ○○ — 〜〜するためのスキル
> 2. △△ — 〜〜するためのスキル」

確定したら `plugin` と `skill_name` を内部で設定する。絞れない場合は全スキル一覧を要約して選ばせる。

**Step 4 — 対象スキルの現状仕様を提示**

Read ツールで確定したスキルの SKILL.md を開く (`Bash(cat *)` は allowed-tools に無い):

- Read: `plugins/<plugin>/skills/<skill_name>/SKILL.md` (Read ツールの引数はワークスペース相対で解決する。`${VAR}` は shell 経由でないので展開されず、リテラルのまま渡って必ず失敗する — 変数を書かない)


Purpose & Output Contract を 2〜3 行に要約してユーザーへ提示:

> 「現在の仕様: 〜〜するためのスキルです。この仕様についての要望ですか？」

ユーザーが「違う」と言ったら Step 1 に戻る。

### 要望収集 (対話)

同定完了後、以下を順に質問して構造化する:

1. **要望タイトル** (30字目安、何を直したいかを1行で)
2. **要望種別**: `バグ` / `機能追加` / `プロンプト改善` / `ドキュメント` / `挙動変更` の中から1つ
3. **やってほしいこと**: "こう直してほしい" を一段落で — 現状仕様と対比させて聞くと明確になる
4. **背景・困っていること**: なぜそれが必要か (任意)
5. **優先度**: `高` / `中` / `低` (デフォルト中)
6. **重要度**: `高` / `中` / `低` (デフォルト中)
7. **関連 PR/コミット URL** (任意)

### 投入引数の目視確認 (任意)

```bash
# 引数の型・必須項目を印字するだけ。Notion へは一切アクセスしない
python3 ${HARNESS_ROOT:-.}/scripts/notion-submit-improvement.py --plugin <plugin> --dry-run \
  --title "<title>" --type <type> --desire "<desire>"
```

**これは登録確認ではない** (未登録プラグインでも必ず成功する)。スキル一覧 DB への登録有無は
次の本投入が `find_plugin_page()` で判定し、未登録ならページ作成前に exit 2 で止まる。
その時に `run-build-skill --notion-register` を先に走らせる旨を案内して中断する。

### 改善要望投入

```text
Construct <MUTATION_ARGV_JSON> as a JSON string array with the resolved python3 executable, the resolved notion-submit-improvement.py path, and these values: plugin, skill-name, title, type, desire, background, priority, importance, and pr-url.
This is input to the canonical receipt flow above; never execute the submit script directly.
```

token / DB ID は `notion_config.require_or_skip()` 経由で自動解決される (token=Keychain 既定 / DB ID=key 別 env > `.notion-config.json`)。**unresolvable なら skip ではなく fail-closed**: stderr に `[notion_config] FATAL:` を出して exit 2 で停止する (silent-skip 禁止)。緩和は `allow_skip=True` を渡した呼び出しのみで、本 script は渡さない。

判定は exit code と標準出力で行う: `[CREATED]` 行があれば成功、`[ERR] スキル一覧に ...` (exit 2) は未登録、`[SKIP] skill-list / improvement-request db_id missing` は **exit 0 だが未投入** なので成功と数えない。一覧は `references/notion-submit-contract.md` §4。

### 完了通知

script は `[CREATED] ... -> <page_id>` を印字する (URL は出さない)。`https://www.notion.so/<page_id からハイフンを除いた 32 桁>` を組み立てて提示し、起票者・担当者プロパティは Notion UI 側で人手追加するよう案内 (people 型は API 経由でメール宛指定不可のため)。

## Gotchas

1. **identification_step を省略しない**: `plugin` 引数が渡されていても、目的確認と現状仕様提示を必ず実施する。省略すると「文脈ズレのフィードバック」や「誤ったスキルへの紐付け」が発生する。
2. **`--dry-run` を存在確認と誤用しない**: 実装は引数を印字して return するだけで Notion に触れないため、未登録プラグインでも通る。孤児レコードを防いでいるのは本投入内の `find_plugin_page()` → exit 2 (ページ作成前) であって dry-run ではない。
3. **token / DB ID を context に乗せない**: スクリプト内で `notion_config.require_or_skip()` (token=Keychain 既定、env は `INTAKE_ALLOW_ENV_TOKEN=1` 時のみ / DB ID=key 別 env > `.notion-config.json`) 経由で取得し、Claude の応答や log に出力しない。**lint が守るのはソース側の 5 点だけ** (`lint-feedback-protocol.py` R8: 秘密を受ける CLI 引数の不在 / `NOTION_*` env 直読みの不在 / `-H "Authorization: …"` を argv へ載せないこと / 出力呼び出し (`print`・`*.write`・logging) へ token の**値**を渡さないこと (AST 走査なので複数行 print や stderr も対象) / `notion_config` の解決順を実呼び出しで pin)。**argv 禁止は「ps から見える」以上の理由がある** — `CalledProcessError.__str__()` が cmd 全体を含むため、例外を `{e}` で整形する print が一つあるだけで token が stdout へ出る (実際に踏んだ)。だから `curl --config -` で stdin から渡す。**実行時に Claude が応答へ書き写す経路は機械検査の外**なので、値そのものを会話へ引用しないのは実行者の責務として残る (lint 緑=秘密が漏れていない、と読み替えない)。
4. **重複除去を AI 判定しない**: 似た要望でも別レコードとして投入する (時系列ログ性質を破壊しない)。
5. **people 型を API で埋めない**: 起票者・担当者は UI 側案内のみ。API でメール宛指定はサポート外。
6. **発火条件・同定フロー追加は schema 経由**: `feedback_protocol` 直接編集 → lint 通過 → 派生物同期の順。SKILL.md / triggers の先行編集禁止。
7. **rollup 更新は Notion 側非同期**: 完了通知時に「rollup は数秒〜数分遅延あり」と添える。
8. **exit 0 = 投入成功ではない**: `require_or_skip` が検査するのは `improvement-request` の db_id だけで、`skill-list` の db_id 欠落は `[SKIP] ...` を出して **exit 0** で抜ける (唯一の fail-open 経路)。完了通知は必ず `[CREATED]` 行の実在で判定する。

## Additional Resources

- 上流: 利用者の口頭・Slack・PR コメントなど任意の発火源
- 下流 (人間ブリッジ): スキル一覧 DB の `未対応要望数` rollup は**人間の優先度判断シグナル**。着手要望を改善計画へ橋渡しする手順は `plugins/harness-creator/references/feedback-to-improvement-runbook.md` (E3 人間ブリッジ = Stage 2→3→6)。**本 skill / rollup は改善着手を自動発火せず、`/skill-improve` も Notion / rollup を読まない** (機械の自動 read-back は goal-spec 制約6 で意図的に回避)。
- スキーマ正本: `doc/notion-schema/improvement-request.schema.json`
- 物理スクリプト: `scripts/notion-submit-improvement.py`
- 設定ローダー: `plugins/harness-creator/scripts/notion_config.py`（token/DB ID 解決 SSOT）
- 1:1 で生成元を辿りたい場合は `紐づくヒアリングシート` → `Skillヒアリングシート` DB
