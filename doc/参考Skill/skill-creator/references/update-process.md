# 更新プロセス（§6.8）

> 18-skills.md §6 更新部分の要約
> **相対パス**: `references/update-process.md`
> **原典**: `docs/00-requirements/18-skills.md` §6.8

---

## モード別ワークフロー

### Mode: create（新規作成）

```
Phase 1: 分析（LLM Task）
analyze-request → extract-purpose → define-boundary
                            ↓
Phase 2: 設計（LLM Task + Script Validation）
select-anchors ─┐
                ├→ design-workflow → [validate-workflow]
define-trigger ─┘
                            ↓
Phase 3: 構造計画（LLM Task + Script Validation）
plan-structure → [validate-plan]
                            ↓
Phase 4: 生成（Script Task）
[init-skill] → [generate-skill-md] → [generate-agents] → [generate-scripts]
                            ↓
Phase 5: 検証（Script Task）
[validate-all]
                            ↓
Phase 6: フィードバック（Script Task）
[log-usage]
```

### Mode: update（既存スキル更新）

```
Phase 1: 差分分析
[detect-mode] → design-update → [validate-schema]
                            ↓
Phase 2: 更新計画
更新対象ファイルの特定 → 依存関係分析 → 更新順序決定
                            ↓
Phase 3: 生成・適用（Script Task）
[apply-updates] → [validate-all]
                            ↓
Phase 4: フィードバック（Script Task）
[log-usage]
```

### Mode: update（Phase 12 retrospective / spec_created 再監査）

```
Phase 1: 入口固定
task-specification-creator/phase-11-12-guide → spec-update-workflow → primary target file list 固定
                            ↓
Phase 2: concern 分離
system spec / screenshot evidence / unassigned formalize / skill update + mirror に lane 分割
監査 lane は並列実行してよいが、編集は単一 owner が直列適用する。read-only audit だけなら AskUserQuestion は開始条件にしない。実際に skill create/update/improve-prompt を実行する場合は SKILL.md の AskUserQuestion 制約を維持する。
                            ↓
Phase 3: 実更新
.claude 正本 / outputs / docs/30-workflows/unassigned-task / workflow-<feature>.md / current canonical set / artifact inventory / legacy register / topic-map を同一ターンで更新
                            ↓
Phase 3.5: stale fact cleanup
テスト件数 / coverage / out-of-scope 注記 / planned wording / 日付を current facts へそろえ、phase-12 成果物と未タスク指示書の記述ドリフトを消す
`spec_created` workflow は root が `completed-tasks/` 配下でも status を勝手に `completed` へ上げず、implementation guide Part 2 は「current contract + target delta」で書いて future sync target の棚上げで終わらせない
code wave が後から入った `spec_created` task では screenshot `N/A` / Step 2 `N/A` を据え置かず、shared / IPC / preload / renderer の current fact を見て evidence policy を再分類する
                            ↓
Phase 3.6: blocker / backlog dedup
targeted suite PASS と wider suite blocker を分離し、既存 `docs/30-workflows/unassigned-task/` / `completed-tasks/unassigned-task/` を検索して重複 formalize を防ぐ
implementation anchor を追記する docs-only close-out では target source path の実在確認を先に行い、duplicate source / ID collision は `current diff` と `wider governance baseline` を分離して記録する
                            ↓
Phase 3.7: screenshot / compliance hardening
placeholder-only evidence を排除し、`TC-ID ↔ png ↔ screenshot-coverage.md ↔ metadata JSON` の current workflow 完結性、implementation guide Part 2 の型/使用例/エラー/設定充足、compliance-check の実測値根拠を同時に監査
close-out remediation follow-up を同一 wave で解消した場合は、新規 remediation workflow を増やさず source / parent workflow の evidence を直接 current facts へ戻し、未完了 open set だけを `docs/30-workflows/unassigned-task/` に残す
完了移管した follow-up は `docs/30-workflows/completed-tasks/unassigned-task/` へ移し、documentation changelog / system spec summary / backlog / completed ledger の open/done 記述を同じ粒度にそろえる
                            ↓
Phase 3.8: skill feedback promotion
Phase 12 `skill-feedback-report.md` の提案を「記録しただけ」で閉じず、task-specification-creator / aiworkflow-requirements / skill-creator の該当 reference へ昇格するか、昇格しない根拠を documentation changelog に残す
各苦戦箇所は `symptom / cause / recurrence condition / 5-minute resolution / evidence path / promoted-to or no-op reason` に分解する。routing は `task-specification-creator/references/phase12-skill-feedback-promotion.md` に従い、workflow/template gap は task-specification-creator、domain implementation lesson は aiworkflow-requirements、skill authoring/update-process gap は skill-creator に置く。
implementation-spec-to-skill sync audit may conclude no direct skill edit is needed, but the no-op is valid only when `skill-feedback-report.md` names the no-op reason, evidence path, and the owning skill/reference that already covers the case.
cron / release / incident response など運用 runbook 系の docs-only task では、runtime 操作を成功扱いにせず、runbook artifact inventory と domain lesson を aiworkflow-requirements に昇格する。09b のように candidate follow-up が複数出る場合は、既存 `docs/30-workflows/unassigned-task/` を先に検索して formalized / delegated / existing related / candidate を分ける。
mirror parity は `.agents/skills/<skill>` が存在する場合のみ必須。存在しない mirror を前提に PASS を書かず、N/A 理由を `documentation-changelog.md` に残す。
Implementation spec-to-skill sync is complete only when workflow outputs, system spec summary, updated skill reference/asset, and mirror diff/N/A evidence all point to the same current contract.
approval-gated NON_VISUAL implementation では、placeholder evidence と runtime evidence の分離、Phase 13 user approval gate、外部 GET 正本の扱いをテンプレ側へ反映する
適用先 reference（task-specification-creator 配下、Phase 12 retrospective で同時更新する正本セット）:
  - `.claude/skills/task-specification-creator/references/phase-11-non-visual-alternative-evidence.md`
  - `.claude/skills/task-specification-creator/references/phase-12-spec.md`
  - `.claude/skills/task-specification-creator/references/quality-gates.md`
  - `.claude/skills/task-specification-creator/references/spec-update-workflow.md`
  - `.claude/skills/task-specification-creator/references/phase-template-phase13.md`
  - `.claude/skills/task-specification-creator/references/phase-template-phase13-detail.md`
                            ↓
Phase 4: 検証
verify-all-specs → validate-phase-output → verify-unassigned-links --source → audit --diff-from HEAD / --target-file → generate-index.js → validate-structure.js → quick_validate / validate_all → mirror sync（mirror directory が存在する場合のみ）→ diff -qr（対象 skill ごとの差分ゼロ出力を evidence に残す）
                            ↓
Phase 5: フィードバック
log-usage + LOGS.md + skill feedback report
```

### Mode: improve-prompt（プロンプト改善）

```
Phase 1: 分析（Script Task）
[detect-mode] → [analyze-prompt]
                            ↓
Phase 2: 改善設計（LLM Task）
improve-prompt → [validate-schema]
                            ↓
Phase 3: 生成・適用（Script Task）
[apply-updates] → [validate-all]
                            ↓
Phase 4: フィードバック（Script Task）
[log-usage]
```

---

## 更新トリガー

| トリガー           | 説明                                        | 推奨モード        |
| ------------------ | ------------------------------------------- | ----------------- |
| フィードバック蓄積 | LOGS.md に改善点が蓄積                      | update            |
| 仕様変更           | 参照書籍の新版、API変更、ドメイン知識の更新 | update            |
| プロンプト最適化   | Task仕様書の明確化・効率化                  | improve-prompt    |
| パフォーマンス問題 | スキルの実行効率が低下                      | improve-prompt    |
| 使用パターン変化   | 想定外の使用方法が主流に                    | update            |
| 依存スキル更新     | 依存先スキルの変更による影響                | update            |
| Phase 12 再監査    | docs-heavy / `spec_created` task の実更新漏れ | update          |

---

## 更新タイプ別リスク

### Type A: コンテンツ更新（低リスク）

| 対象                                   | 使用モード     | 使用スクリプト   |
| -------------------------------------- | -------------- | ---------------- |
| 誤字修正、説明文の改善、参照書籍の追加 | update         | apply_updates.js |

### Type B: 構造更新（中リスク）

| 対象                                             | 使用モード     | 使用スクリプト          |
| ------------------------------------------------ | -------------- | ----------------------- |
| セクション追加、ワークフロー変更、スクリプト追加 | update         | apply_updates.js --backup |

### Type C: プロンプト改善（中リスク）

| 対象                                   | 使用モード     | 使用スクリプト        |
| -------------------------------------- | -------------- | --------------------- |
| agents/*.mdの明確化、具体化、効率化    | improve-prompt | analyze_prompt.js    |

### Type D: 破壊的更新（高リスク）

| 対象                                                | 使用モード | 使用スクリプト            |
| --------------------------------------------------- | ---------- | ------------------------- |
| name変更、description大幅変更、ディレクトリ構造変更 | update     | apply_updates.js --backup |

---

## 使用スクリプト一覧

| スクリプト            | 用途                     | モード           |
| --------------------- | ------------------------ | ---------------- |
| `detect_mode.js`     | モード判定               | 全モード         |
| `analyze_prompt.js`  | プロンプト分析           | improve-prompt   |
| `apply_updates.js`   | 更新適用                 | update, improve  |
| `validate_all.js`    | 全体検証                 | 全モード         |
| `log_usage.js`       | フィードバック記録       | 全モード         |

---

## 実行コマンド例

### update モード

```bash
# 1. モード判定
node scripts/detect_mode.js --request "スキルを更新" --skill-path .claude/skills/my-skill

# 2. 更新適用（dry-run）
node scripts/apply_updates.js --plan .tmp/update-plan.json --dry-run

# 3. 更新適用（実行）
node scripts/apply_updates.js --plan .tmp/update-plan.json --backup

# 4. 検証
node scripts/validate_all.js .claude/skills/my-skill

# 5. フィードバック記録
node scripts/log_usage.js --result success --phase update
```

### update モード（Phase 12 retrospective）

```bash
# 1. primary target と guide を先に固定
rg -n "primary target|spec_created|screenshot fallback" \
  .claude/skills/task-specification-creator/references/phase-11-12-guide.md \
  .claude/skills/task-specification-creator/references/spec-update-workflow.md

# 2. workflow 単位の証跡を閉じる
node .claude/skills/task-specification-creator/scripts/verify-unassigned-links.js \
  --source docs/30-workflows/<workflow>/outputs/phase-12/unassigned-task-detection.md
node .claude/skills/task-specification-creator/scripts/audit-unassigned-tasks.js --json --diff-from HEAD
node .claude/skills/task-specification-creator/scripts/audit-unassigned-tasks.js \
  --json --target-file docs/30-workflows/unassigned-task/<task>.md

# 3. canonical navigation と structure を閉じる
node .claude/skills/aiworkflow-requirements/scripts/generate-index.js
node .claude/skills/aiworkflow-requirements/scripts/validate-structure.js

# 4. mirror sync 後に差分確認
rsync -a .claude/skills/<skill>/ .agents/skills/<skill>/
diff -qr .claude/skills/<skill> .agents/skills/<skill>

# 5. stale fact cleanup を閉じる
rg -n "実施予定|後続タスク|N/A|予定|202[0-9]-[0-9]{2}-[0-9]{2}" \
  docs/30-workflows/<workflow>/outputs/phase-12 \
  docs/30-workflows/unassigned-task/<task>.md

# 6. 更新した skill を構造検証
node scripts/quick_validate.js .claude/skills/skill-creator
node scripts/validate_all.js .claude/skills/skill-creator
```

### improve-prompt モード

```bash
# 1. プロンプト分析
node scripts/analyze_prompt.js --skill-path .claude/skills/my-skill --verbose

# 2. 改善計画確認
cat .tmp/prompt-analysis.json

# 3. 更新適用（LLMが生成した改善をapply）
node scripts/apply_updates.js --plan .tmp/update-plan.json --backup

# 4. 検証
node scripts/validate_all.js .claude/skills/my-skill
```

---

## 関連リソース

- **新規作成プロセス**: See [creation-process.md](creation-process.md)
- **フィードバック**: See [feedback-loop.md](feedback-loop.md)
- **品質基準**: See [quality-standards.md](quality-standards.md)
## 2026-03-26 追補: docs-heavy follow-up への code hardening 混入

- close-out / spec sync 専用 workflow にコード変更が入った場合は、`outputs/phase-12/*.md` の narrative と source workflow 本文を先に current facts へ戻す。
- internal contract hardening は「新仕様追加」ではなく「existing contract の hardening current facts」として system spec へ追記する。
- carry-forward していた follow-up を同ターンで解消したら、completed ledger / unassigned detection / quick-reference を 0 件状態へそろえる。
- compile gate PASS と env-blocked test は別行で記録し、`typecheck PASS + Vitest blocker` のように境界を明示する。
- Step 2 domain spec が no-op でも、Step 1 の completed ledger / lessons / LOGS / SKILL history / source unassigned status は no-op にしない。
- public IPC shape が不変でも、internal contract・source provenance・owner boundary・runtime helper class が current fact として増えた場合は Step 2 を no-op にしない。
- authority injection・shared auth mode service・decision vocabulary・reason source of truth のいずれかを composition root で変更した場合も internal hardening とみなし、Step 2 / lessons / skill feedback を更新する。
- handler / consumer テストの期待値は実体 enum と同じ語彙へ合わせ、`integrated_api` / `terminal_handoff` のような canonical vocabulary と reason source 単一化を summary に残す。
- Phase 12 root evidence を手編集した後は `rg "\\*\\*\\* Add File:|\\*\\*\\* Begin Patch|\\*\\*\\* End Patch"` で patch marker 混入を監査し、artifact existence だけで false green にしない。

## 2026-05-01 追補: Phase 12 skill feedback promotion

Phase 12 由来のスキル更新は、`skill-feedback-report.md` に記録して終わらせない。次の最小ゲートを通す。

| 観点 | 必須確認 |
| --- | --- |
| metadata | `description` は短く保ち、詳細な Anchors / Trigger / 履歴は本文または `references/` に退避する |
| line budget | `SKILL.md` と主要 reference は 500 行以内を目安にし、超過時は classification-first で分割する |
| generated files | README / CHANGELOG / samples を慣性で増やさず、既存 `LOGS.md` / `SKILL-changelog.md` / `references/resource-map.md` の正本関係を優先する |
| changelog sync | 既存スキルの `references/` 追加・既存 reference 補強・Trigger 更新を行ったら、**同一 wave** で対象スキルの `SKILL-changelog.md` に 1 行追加し、`SKILL.md` 内最新 3 件履歴も同期する。reference 追加のみで SKILL-changelog を更新しないのは fail。 |
| SubAgent lanes | 入力、責務、出力、編集可否、依存関係を明示し、監査は read-only、編集は owner が直列化する |
| cross-runtime contract | Claude Code / Codex / 外部CLIで実行差が出る場合は、実行境界と検証コマンドを reference に残す |

補助パスの skill 実装を参照する場合は、丸ごとコピーしない。既存 UBM 側の read-only audit 例外や resource-map 導線を優先し、取り込む要素を `Promote / Defer / Reject` で明示する。
