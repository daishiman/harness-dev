---
name: run-ubm-journal
description: 日次ジャーナルを作りたいとき、今日やったことを会話で振り返りながら Obsidian の Daily へ構造化した新規ファイルを生成したいときに使う。
disable-model-invocation: true
user-invocable: true
argument-hint: "[YYYY-MM-DD]"
arguments: [date]
allowed-tools:
  - Read
  - Write
  - Edit
  - Bash
  - Glob
  - Grep
  - Task
  - AskUserQuestion
kind: run
prefix: run
effect: external-mutation
external_mutation_guard: {runtime_ref: "plugin:skill-governance-adapters/scripts/build-external-mutation-guard.py", flow: "preview-confirm-authorize-execute-v1"}
owner: harness-maintainers
since: 2026-08-17
version: 0.6.0
subagent_refs:
  - journal-composer
schema_refs:
  - references/output-format.md
script_refs:
  - scripts/build-journal-context.py
  - scripts/validate-journal-output.py
reference_refs:
  - references/resource-map.yaml
  - references/output-format.md
  - references/interview-map.md
  - references/daily-habits.json
  - references/principle-checklist.md
source: ユーザーの既存 Obsidian Daily 運用 (02_Configs/Daily/) の仕組み化
source-tier: internal
last-audited: 2026-08-17
audit-trigger: quarterly
feedback_contract:
  activation_state: semantic_evaluator_started
  max_iterations: 3
  criteria:
    - id: IN1
      loop_scope: inner
      text: validate-journal-output.py が保存前に骨格15ブロック・目標4階層・3ジャーナル×3小節・未置換プレースホルダを検証し違反0件であることを確認する。
      verify_by: script
    - id: IN2
      loop_scope: inner
      text: 通し番号は build-journal-context.py の journal_number をそのまま使い、LLM が推測した番号を書かないことを --expected-number 照合で確認する。
      verify_by: script
    - id: OUT1
      loop_scope: outer
      text: 実際の対話でジャーナルを生成し、ユーザーが語った固有名詞・数値・時刻が欠落せず該当セクションへ振り分けられていることを受入テストが確認する。
      verify_by: test
    - id: OUT2
      loop_scope: outer
      text: run-skill-live-trial で対話を実走し、Phase0 の文脈解決から Phase1-3 のヒアリング、Phase4 整形、Phase5 検証 PASS までを自走完遂して Daily 配下にジャーナルが実生成されることを実行証拠で確認する。
      verify_by: live-trial
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
runtime_root_policy: host-skill-path
---

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


# run-ubm-journal

## Runtime root contract

- `runtime_root_policy: host-skill-path` を適用する。
- Claude Codeでは `CLAUDE_PLUGIN_ROOT` をplugin rootとして使用する。
- Codexではホストが提示したこの `SKILL.md` のabsolute pathから、plugin manifestを持つ祖先を上方探索して論理 `PLUGIN_ROOT` を解決する。
- `cwd` からplugin rootを推測せず、literal placeholderをshellへ渡さない。各shell invocation内で解決済みabsolute pathを `PLUGIN_ROOT` に設定する。
- `prompts/` 配下はこのowner Skill契約を継承する。

その日の振り返りを会話で行い、`$UBM_VAULT_ROOT/02_Configs/Daily/{YYYY-MM-DD}.md` へ構造化された
日次ジャーナルを生成する。チェックリストを読み上げるのではなく、「今日は何をやりましたか」から
自然に会話を進め、返ってきた話をジャーナルの各セクションへ振り分ける。

## Purpose & Output Contract

- **ゴール**: 対象日のジャーナル1件が `references/output-format.md` の骨格で生成され、
  `validate-journal-output.py` が PASS した状態。
- **出力契約**: `02_Configs/Daily/{YYYY-MM-DD}.md` 1ファイル + バリデーション結果（PASS/FAIL）。
- **境界**: 入力=前回ジャーナル / 最新の週報・月報・期報 / 対話回答。出力=日次ジャーナル1件のみ。
  週報・月報・期報そのものの更新は `run-ubm-goal-setting` へ委譲する（このスキルは読むだけ）。
- **フォーマットは器であって目的ではない**: テンプレートの穴埋めではなく、その日やったことを
  構造的にまとめることが目的。分類見出しはその日の実態に合わせて命名してよい。

## End-to-End Flow

| Phase | 責務 | 実行体 |
|---|---|---|
| Phase0-resolve | 対象日を確定し `build-journal-context.py` で番号・目標4階層・週報引き継ぎ・warnings を取得 | 本 skill（Bash） |
| Phase1-open | 「今日は何をやりましたか」で対話を開き、事実を出しきる | 本 skill |
| Phase2-deepen | 気づき・うまくいかなかったこと・時間の使い方・お金の動きを掘る | 本 skill |
| Phase3-fill | 埋まっていない枠（感謝・禁止事項・タスク）と**未確認の固定習慣**を、週報の呼び水を使って補う | 本 skill |
| Phase4-compose | 収集内容を骨格へ整形し Markdown を組み立てる | `journal-composer`（Task） |
| Phase5-validate | `validate-journal-output.py` で検証、違反があれば最大3回修正して保存 | 本 skill + script |

**所要時間目安**: 5〜10分。

## Phase0: 文脈解決（必ず最初に実行する）

```bash
python3 "${PLUGIN_ROOT:-${CLAUDE_PLUGIN_ROOT}}/skills/run-ubm-journal/scripts/build-journal-context.py" \
  --vault-root "$UBM_VAULT_ROOT" --date "{YYYY-MM-DD}"
```

- 対象日は引数 `$ARGUMENTS` があればそれ、無ければ **今日**（ファイル日付＝見出し日付＝振り返る日）。
- `journal_number` をそのまま使う。**番号を自分で数えない・推測しない。**
- `warnings` は対話の切り口として使う（例: 1年目標の期間満了、期報の期間ズレ、当日タスク未検出）。
- `existing_file.write_mode` を**必ず先に見る**。ジャーナルは Write で全置換されるため、
  ここを飛ばすと利用者の既存ファイルが消える。
  - `new`: そのまま新規作成して進む。
  - `regenerate`: 同じ日のジャーナルを作り直す。番号を維持し、更新であることを伝えてから進む。
  - `blocked`: **Write せず停止する。** 対象ファイルに別日の内容が入っている。
    どうするか（別名で作る／既存を退避する／中止する）を必ずユーザーへ確認してから動く。

## Phase1-3: 対話

`references/interview-map.md` の問い→セクション対応表に沿って進める。

- **開き方**: 「今日は何をやりましたか？」。列挙が出たら、時間をかけた順・人が関わった順に掘る。
- **翌日以降の視点**: 「昨日やったことで気づいたことはありますか？」で効果性の材料を取る。
- **週報の呼び水**: `weekly_report.day_tasks` を「今日はこれが入っていましたが、どうなりましたか？」
  の形で提示する。丸ごと転記はしない。
- **固定習慣（毎日必須）**: Phase0 の `daily_habits`（6項目: Gridノート / 23時就寝 / ストレッチ /
  計画外の動画視聴 / ジャーナル / SNS投稿）は**毎回必ず確認する**。ただし頭から順に読み上げず、
  Phase1-2 で自然に出た項目は拾って済ませ、**Phase3 で残った分だけを2〜3問に束ねて**聞く。
  達成/未達のどちらであれ痕跡を残す。ただし H01 が見るのは各習慣の `search_scopes` が
  指すセクションの中だけなので、`interview-map.md` の「落とす先」列のセクションへ書く
  （本文のどこかにあればよい、ではない）。痕跡ゼロは Phase5 で H01 違反になる。
- **週次習慣目標**: 週報の習慣目標4群は独立セクションにせず、会話から達成状況を推し量って
  行動・時間・お金の各ジャーナルへ事実として織り込む（`references/interview-map.md` 参照）。
- **目標セクションだけは自動**: 1年/2ヶ月/1ヶ月/1週間目標と残日数は Phase0 の結果をそのまま使い、
  ユーザーに確認を求めない。ただし `warnings` に期間ズレ・満了があるときだけ確認する。

## Phase4-5: 整形と検証

- `journal-composer` サブエージェントへ、Phase0 の context JSON と対話で得た内容を渡して整形させる。
- 保存後に必ず検証する:

```bash
python3 "${PLUGIN_ROOT:-${CLAUDE_PLUGIN_ROOT}}/skills/run-ubm-journal/scripts/validate-journal-output.py" \
  --file "$UBM_VAULT_ROOT/02_Configs/Daily/{YYYY-MM-DD}.md" \
  --expected-number {journal_number} --expected-date {YYYY-MM-DD}
```

- FAIL なら違反コードに従って修正し、最大3回まで再検証する。3回で収束しなければ違反を残したまま
  完了扱いにせず、残件をユーザーへ報告する。

## Key Rules

- **番号は決定論**: `journal_number` はスクリプト値のみ。同日再生成時は番号を維持する。
- **日付3点一致**: ファイル名の日付・見出しの日付・振り返る対象日は常に同じ。
- **数値は半角**: 「25万円」ではなく `250,000`。件数・日数・時刻も具体値で書く。
- **精神論を書かない**: 「頑張る」「意識する」は打ち手として不可 → 誰に・何を・いつまで・何件 へ。
- **要約しすぎない**: ユーザーが出した固有名詞・数値・時刻・相手の発言はそのまま残す。
  1項目1事実に分解し、冗長な言い回しだけを削る。
- **3小節を混ぜない**: 「現状を確認する」に評価や改善案を書かない。事実／解釈／打ち手を分離する。
- **継承値は書き換えない**: 人生の究極目的・フェーズ別課題チェックシート・原理原則チェックシートは
  前回から引き継ぎ、ユーザーが変更を申し出た項目だけ更新する。
- **原理原則チェックシートは毎回出す**: `# 原理原則 チェックシート`（11 設問）は省略・要約・抜粋をしない。
  前回ジャーナルの状態をそのまま写し、対話で変化があったチェック状態だけを更新する。
  前回に本ブロックが無ければ `references/principle-checklist.md` のテンプレートを未チェックで書き出す。
  **対話（Phase1-3）では読み上げない**。11 設問を聞き取りに足すとジャーナル対話が倍の長さになって
  毎日の運用が続かない。Phase4 の生成時に器として出すだけで要求は満たされる。

## Gotchas

- **保存先の書込許可**: `ubm-write-path-guard` hook は vault 配下で `02_Configs/Daily/` を許可済み。
  `02_Configs/` の他のパスへは書けない（fail-closed）。
- **`UBM_VAULT_ROOT` 未設定**: Phase0 が exit 2 になる。vault パスをユーザーに確認してから再実行する。
  Phase0 の exit 2 は「引数不正・vault 解決不能・Daily 不在・daily-habits.json 破損」の総称なので、
  stderr の 1 行目を必ず読んでから対処すること。
- **週報が当日を含まない**: 週をまたいだ直後は直近週報を参照する（`covers_target: false` の warning）。
  1週間目標の残日数は `0日（期間終了・次週分の週報は未作成）` と書く。
- **1年目標の対応レポートは存在しない**: 前回ジャーナルからの継承のみ。満了していたら対話で確認する。
- **フェーズ別課題チェックシートは本文の外**: `## 【お金のジャーナル】` の後、レベル1見出しとして置く。
- **チェックシート2種を取り違えない**: `# フェーズ別 課題チェックシート`（0→1 / 1→10 / 10→100）と
  `# 原理原則 チェックシート`（11 設問）は別ブロックで、どちらも `- [ ]` の塊なので見た目では区別できない。
  順序は必ずフェーズ別 → 原理原則（ファイル末尾）。原理原則の本文に水平線 `---` を入れると、
  翌日の継承がそこで打ち切られて以降の設問が静かに消える。

## Additional Resources

- **scripts**: `scripts/build-journal-context.py`（番号・目標・週報引き継ぎの決定論解決）/
  `scripts/validate-journal-output.py`（保存前バリデーション）。
- **references**: `references/resource-map.yaml`（どの Phase でどれを開くかの索引。迷ったら最初に見る）/
  `references/output-format.md`（骨格の正本）/ `references/interview-map.md`（問い→セクション対応）/
  `references/daily-habits.json`（毎日固定の習慣6項目の正本。項目を増減するときはここだけを編集し、
  `keywords` と `search_scopes`（H01 が検査するセクション）を必ず併記する。`search_scopes` を
  書き忘れた習慣は検査不能として H02 違反になる）/
  `references/principle-checklist.md`（`# 原理原則 チェックシート` 11 設問の正本テンプレートと出力規則。
  設問を増減するときはこのファイルと `validate-journal-output.py` の `PRINCIPLE_SECTIONS` を同時に直す）。
- **assets**: `assets/golden-sample.md`（バリデータ PASS の見本 / Few-shot）。
- **agents**: `journal-composer`（plugin 直下 `agents/`）。
