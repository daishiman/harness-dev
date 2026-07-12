# Phase 12 Action Bridge テンプレート

> **読み込みタイミング**: Phase 12 再監査後、次アクションへ落とし込むとき
> **出力先（推奨）**: `docs/30-workflows/skill-import-agent-system/tasks/task-00-unified-implementation-sequence/task-xxxx-phase12-action-bridge.md`
> **目的**: 監査結果を「優先度・並列計画・担当・成果物」に即時変換し、実行順を固定する

---

## テンプレート本体

````markdown
# {{TASK_ID}} Phase 12 Action Bridge

## 0. メタ情報

| 項目 | 内容 |
| --- | --- |
| 対象タスク | {{TASK_ID}} |
| 作成日 | {{DATE}} |
| 目的 | 監査結果を次アクションへ変換し、着手順を固定する |
| ステータス | draft / ready / done |

---

## 1. 監査サマリー（事実のみ）

| 区分 | 件数 | 代表例 |
| --- | --- | --- |
| baseline（既存） | {{BASELINE_COUNT}} | {{BASELINE_EXAMPLE}} |
| current（今回差分） | {{CURRENT_COUNT}} | {{CURRENT_EXAMPLE}} |
| Phase 12 必須成果物不足 | {{MISSING_COUNT}} | {{MISSING_EXAMPLE}} |

---

## 2. 実行方針（なぜこの順序か）

- Why: {{WHY_THIS_ORDER}}
- 方針: 先に「再発防止効果が大きいもの」、次に「依存を持つもの」、最後に「低リスク改善」
- 完了定義:
  - `outputs/phase-12/` 必須成果物5点が揃う
  - `verify-unassigned-links.js` PASS
  - `detect-unassigned-tasks --scan {{SCOPE}}` で current 起因の未処理が0件

---

## 3. 実行シーケンス（Wave計画）

| Wave | 実行形態 | 優先度 | タスクID | 担当(SubAgent) | 依存 |
| --- | --- | --- | --- | --- | --- |
| Wave 1 | 並列 | P1 | {{TASK_A}} | SubAgent-A | なし |
| Wave 1 | 並列 | P1 | {{TASK_B}} | SubAgent-B | なし |
| Wave 2 | 直列 | P2 | {{TASK_C}} | SubAgent-C | Wave 1 完了 |
| Wave 3 | 直列 | P3 | {{TASK_D}} | SubAgent-D | Wave 2 完了 |

---

## 4. SubAgent責務分割

| SubAgent | スコープ | 入力 | 出力 |
| --- | --- | --- | --- |
| SubAgent-A | {{SCOPE_A}} | {{INPUT_A}} | {{OUTPUT_A}} |
| SubAgent-B | {{SCOPE_B}} | {{INPUT_B}} | {{OUTPUT_B}} |
| SubAgent-C | {{SCOPE_C}} | {{INPUT_C}} | {{OUTPUT_C}} |
| Lead | 統合/検証 | 全SubAgent成果物 | 最終反映 + 検証ログ |

---

## 5. 成果物マッピング（outputs必須）

| 成果物 | パス |
| --- | --- |
| implementation-guide.md | `{{OUTPUT_DIR}}/implementation-guide.md` |
| documentation-changelog.md | `{{OUTPUT_DIR}}/documentation-changelog.md` |
| spec-update-summary.md | `{{OUTPUT_DIR}}/spec-update-summary.md` |
| unassigned-task-detection.md | `{{OUTPUT_DIR}}/unassigned-task-detection.md` |
| skill-feedback-report.md | `{{OUTPUT_DIR}}/skill-feedback-report.md` |

---

## 6. 苦戦箇所と先回り対策

| 苦戦箇所 | リスク | 先回り対策 |
| --- | --- | --- |
| {{STRUGGLE_1}} | {{RISK_1}} | {{COUNTERMEASURE_1}} |
| {{STRUGGLE_2}} | {{RISK_2}} | {{COUNTERMEASURE_2}} |
| {{STRUGGLE_3}} | {{RISK_3}} | {{COUNTERMEASURE_3}} |

---

## 7. 観点チェック（漏れ防止）

- 水平/垂直/システム思考: 影響範囲の抜け漏れがないか
- Why/因果ループ思考: 表面課題の根因まで対策できているか
- 2軸/トレードオン/プラスサム思考: 優先度と実行順に矛盾がないか
- 改善/ダブルループ思考: 同じ失敗を防ぐ運用変更まで入っているか

---

## 8. 実行チェックリスト

- [ ] task-00 配下へ action-bridge を配置
- [ ] Wave と担当を固定（並列可能箇所を明記）
- [ ] `outputs/phase-12/` 必須5成果物を出力
- [ ] `task-workflow.md` / `lessons-learned.md` / `SKILL.md` / `LOGS.md` を同期更新
- [ ] 検証コマンド結果を記録（baseline/current分離）

````

---

## 記入ガイド

1. 監査結果は「baseline / current」で必ず分離する。
2. Wave 1 は依存なしタスクだけを置く。
3. outputs は Phase 12 の5成果物を固定し、不足時は完了扱いにしない。
4. 苦戦箇所は「症状」ではなく「再発条件」まで書く。
