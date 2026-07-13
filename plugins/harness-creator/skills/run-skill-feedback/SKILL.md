---
name: run-skill-feedback
description: 既存スキルへの「こう直してほしい」要望を受け取って Notion 改善要望 DB にプッシュしたいとき、利用者発端のフィードバックループを起動したいときに使う。
triggers:
  - "スキルや機能を改善したいとき"
  - "プラグイン・スキルへの要望や不満があるとき"
disable-model-invocation: false
user-invocable: true
argument-hint: "[plugin?] [skill-name?]"
arguments: [plugin, skill_name]
arguments-optional: [plugin, skill_name]
allowed-tools:
  - Read
  - Bash(python3 *)
  - Bash(security *)
  - Agent
  - Grep
  - Glob
kind: run
prefix: run
effect: external-mutation
owner: team-platform
since: 2026-05-25
version: 0.1.0
max_loops: 5
reference_refs:
  - plugins/harness-creator/skills/run-build-skill/references/goal-seek-paradigm.md
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
  max_iterations: 3
  criteria:
    - id: IN1
      loop_scope: inner
      text: 発火条件と同定フローと対話項目が skill-list.schema.json の feedback_protocol を唯一の正本として派生し lint-feedback-protocol が SKILL.md と派生物の整合を exit0 で通過する
      verify_by: lint
    - id: IN2
      loop_scope: inner
      text: token と DB ID は notion_config の require_or_skip 経由(CLI > env > per-repo config > Keychain)でのみ解決され Claude の応答や log や context に一切露出しない
      verify_by: lint
    - id: IN3
      loop_scope: inner
      text: 改善要望投入前に対象プラグインのスキル一覧 DB 登録を dry-run で確認し未登録なら投入せず中断するため孤児レコードが生成されない
      verify_by: script
    - id: OUT1
      loop_scope: outer
      text: 目的逆算の同定フローが省略されず利用者がプラグイン名やスキル名を知らない前提で目的ヒアリングと現状仕様提示を経て対象スキルが正しく同定され文脈ズレ要望を防ぐ設計になっている
      verify_by: elegant-review
    - id: OUT2
      loop_scope: outer
      text: 利用者発端のフィードバックループが摩擦最小で起動でき収集した構造化要望が improvement-request schema 準拠で時系列ログ性質(重複除去を AI 判定しない)を保つ妥当な対話設計である
      verify_by: evaluator
---

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
3. **対象プラグイン存在確認必須**: スキル一覧 DB に未登録なら `run-build-skill --notion-register` を案内して中断 (孤児レコード防止)。
4. **token / DB ID は notion-config SSOT 経由**: `plugins/harness-creator/scripts/notion_config.py` の `require_or_skip()` が解決順 (CLI 引数 > env `NOTION_TOKEN` / `NOTION_*_DATABASE_ID` > per-repo `.notion-config.json` > macOS Keychain slug-namespaced key) を一元管理。`scripts/notion-submit-improvement.py` は同 loader を import 済み。token / DB ID をコンテキストに乗せない。
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
- [ ] 対象プラグインがスキル一覧 DB に存在することを `--dry-run` で確認済み (未登録なら中断して案内)
- [ ] Notion 改善要望 DB に 1 ページが新規作成され URL が取得できている
- [ ] スキル一覧 DB との N:1 relation が貼られ `未対応要望数` rollup が増分している
- [ ] 完了通知に「起票者・担当者は Notion UI で人手追加」案内が含まれている
- [ ] token / DB ID は `notion_config.require_or_skip()` 経由 (CLI > env > per-repo `.notion-config.json` > Keychain slug-namespaced key の解決順) で取得しており context に露出していない

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

```bash
# 全 SKILL.md から name と description を取得
grep -r --include="SKILL.md" -E "^(name|description):" plugins/ | \
  awk -F: '{print $2}' | paste - -
```

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

```bash
# 確定したスキルの SKILL.md を Read
cat plugins/<plugin>/skills/<skill_name>/SKILL.md
```

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

### 対象プラグインの存在確認

```bash
# スキル一覧 DB に対象プラグインが登録済みか確認
python3 scripts/notion-submit-improvement.py --plugin <plugin> --dry-run \
  --title "<title>" --type <type> --desire "<desire>"
```

存在しない場合は `run-build-skill --notion-register` を先に走らせる旨を案内して中断。

### 改善要望投入

```bash
python3 scripts/notion-submit-improvement.py \
  --plugin "<plugin>" --skill-name "<skill_name>" \
  --title "<title>" --type "<type>" \
  --desire "<desire>" --background "<background>" \
  --priority "<priority>" --importance "<importance>" \
  --pr-url "<pr-url>"
```

token / DB ID は `notion_config.require_or_skip()` 経由 (CLI > env > per-repo `.notion-config.json` > Keychain slug-namespaced key の解決順)。`notion-submit-improvement.py` 内で自動解決され、unresolvable なら skip + 利用者通知。

### 完了通知

投入された Notion ページ URL を提示し、起票者・担当者プロパティは Notion UI 側で人手追加するよう案内 (people 型は API 経由でメール宛指定不可のため)。

## Gotchas

1. **identification_step を省略しない**: `plugin` 引数が渡されていても、目的確認と現状仕様提示を必ず実施する。省略すると「文脈ズレのフィードバック」や「誤ったスキルへの紐付け」が発生する。
2. **孤児レコード禁止**: 対象プラグインがスキル一覧 DB 未登録のまま要望だけ投入しない。必ず `--dry-run` で先に存在確認。
3. **token / DB ID を context に乗せない**: スクリプト内で `notion_config.require_or_skip()` (CLI > env > `.notion-config.json` > Keychain) 経由で取得し、Claude の応答や log に出力しない。
4. **重複除去を AI 判定しない**: 似た要望でも別レコードとして投入する (時系列ログ性質を破壊しない)。
5. **people 型を API で埋めない**: 起票者・担当者は UI 側案内のみ。API でメール宛指定はサポート外。
6. **発火条件・同定フロー追加は schema 経由**: `feedback_protocol` 直接編集 → lint 通過 → 派生物同期の順。SKILL.md / triggers の先行編集禁止。
7. **rollup 更新は Notion 側非同期**: 完了通知時に「rollup は数秒〜数分遅延あり」と添える。

## Additional Resources

- 上流: 利用者の口頭・Slack・PR コメントなど任意の発火源
- 下流 (人間ブリッジ): スキル一覧 DB の `未対応要望数` rollup は**人間の優先度判断シグナル**。着手要望を改善計画へ橋渡しする手順は `plugins/harness-creator/references/feedback-to-improvement-runbook.md` (E3 人間ブリッジ = Stage 2→3→6)。**本 skill / rollup は改善着手を自動発火せず、`/skill-improve` も Notion / rollup を読まない** (機械の自動 read-back は goal-spec 制約6 で意図的に回避)。
- スキーマ正本: `doc/notion-schema/improvement-request.schema.json`
- 物理スクリプト: `scripts/notion-submit-improvement.py`
- 設定ローダー: `plugins/harness-creator/scripts/notion_config.py`（token/DB ID 解決 SSOT）
- 1:1 で生成元を辿りたい場合は `紐づくヒアリングシート` → `Skillヒアリングシート` DB
