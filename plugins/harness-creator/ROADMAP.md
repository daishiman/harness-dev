# ROADMAP

`harness-creator` plugin の短期 / 中期 / 長期ロードマップ。設計書 33 章 `change-governance` の運用方針に従い、各層は目標・成果物・成功指標 (KPI) を明示する。

## 短期 (本 PR 〜 次 1-2 スプリント)

**目標**: governance/feedback hook を 7 種 target_type へ配線完了し、改善ループを自走させる基盤を確立する — **済 (CHANGELOG [Unreleased] Added に記録・版番号確定待ち)**。7 種 hook 配線 (7/7)・lessons-learned 自動記録パイプライン (`auto-record-lesson.py` PostToolUse 配線)・CHANGELOG.md の運用開始 (各 PR で Unreleased セクションを更新する運用ルール) はいずれも達成済み。**継続運用 KPI**: lessons 自動記録の取りこぼし率 < 5%、CHANGELOG 更新率 100% (governance ラベル付き PR 基準)。

### 意図的 deferred (2026-07-02 elegant-review `20260702-declarative-skillcreator`)

宣言型化レビューで理由付き残置とした項目 (正本: `eval-log/harness-creator/_plugin/elegant-review/20260702-declarative-skillcreator/verdict.json` の `deferred[]`)。(1) verdict 鮮度の tree-hash 化 (references のみ変更の PR merge が re-audit trigger)、(2) canonical-registry.json (正本誤読の観測時に採用)、(3) exemptions.json 完全版 (escape 追加時に段階導入)、(4) compute-dogfooding-metrics.py の SessionEnd 配線 (書込先を state 領域へ変更してから)、(5) knowledge/usage-log.jsonl 生成 (consult 実運用の定着後)、(6) handoff-`<step>`.json 存在検証 lint (次回 gate 変更時に同時配線)、(7) script-frontmatter の CI 配線 (既存違反の棚卸し後、`lint-matrix.json` の `ci_exclusion_reason` に記録)。

### 意図的 deferred (2026-07-02 まんべんなく生成レビュー)

build-plan 決定論導出 (`validate-build-plan.py`)・criteria roster 動的探索・llm-coverage CI fail-closed 化の追補で理由付き残置とした項目。(8) 投入系 Sink Contract の combinator/テンプレ化 (`with-sink.patch`): 現状は build-plan notes + Step 3 の必須参照指示 (prompt 層)。投入系 skill の次回生成時に patch 化して機械層へ昇格、(9) per-skill EVALS.json の生成・検査: 現状 plugin 単位のみ。friction anomaly (aggregate-evals) の運用実績を見て skill 単位へ展開、(10) build-plan の CI 静的面: brief が build 時 (eval-log/) にのみ存在するため CI 一括適用は不可 (`lint-matrix.json` の `ci_exclusion_reason` に記録)。committed brief の保存規約を導入すれば静的化可能。

### 意図的 deferred (2026-07-02 elegant-review `20260702T160010-anti-goodhart`)

anti-goodhart 統合 (run-skill-live-trial / run-skill-iter-improve 新設 + Gate D 配線) で理由付き残置とした項目。(11) **D13 P1 パイロットゲート**: live-trial パイロット 2-3 件の判定表 (静的レビュー判定 vs 実走判定の対照) を `eval-log/<plugin>/<skill>/live-trial/` へ記録するまで `scripts/lint-live-trial-verdict.py` は record-only WARN 運用。P1 完了条件はこの判定表の記録、(12) **D13 P3 常設化 go/no-go**: workflow-manifest `live-acceptance` phase の `default_on` 昇格と lint の `--enforce` 昇格は、パイロット判定表の乖離率 (静的 PASS × 実走 FAIL の発生率) で go/no-go 判定する、(13) **D7 verify_by ratchet (P2)**: **実装済 (2026-07-02 前倒し)** — acceptance_tier=live 導出 (正本 `derive_acceptance_tier`) の loop 実行系 skill へ outer criteria の `verify_by: live-trial` 最低1件を repo-root `scripts/lint-feedback-contract.py` が ratchet 強制。既存 20 skill は `scripts/live-trial-criteria-baseline.json` で WARN 免除 (追記禁止・縮小のみ)。一括 backfill はパイロット実績後のまま残置、(14) **D14 trial-scenarios hook 拡張**: シナリオコーパスの hook 収集 (A3-009) は verdict の `scenario_origin` (synthetic|replay) フィールドのみ実装済。replay コーパス自動採取の hook 拡張は live-trial 運用定着後に検討。

## 中期 (3-6 ヶ月)

**目標**: composition manifest の plugin 横断採用と review→executor の自動チェインにより、改善サイクルを人手介入最小で回す。**成果物**: 全 plugin での `plugin-composition.yaml` 採用、review エージェントから executor エージェントへの自動 handoff 機構、EVALS 結果から rubric 改訂 PR を生成する feedback パイプライン。**KPI**: composition manifest 採用率 100% (全 plugin)、review→executor 自動チェインの収束率 (max 3 周回内) >= 80%、EVALS→rubric PR の月次マージ数 >= 2 本。

## 長期 (6 ヶ月以降)

**目標**: target_type 7 種を composition manifest 上で宣言的に運用し、cross-plugin 依存と dogfooding 状況を可視化する自己改善基盤を確立する。**成果物**: 7 種すべてを宣言できる composition schema、cross-plugin 依存グラフの自動可視化 UI、dogfooding ダッシュボード (自己適用率・rubric 充足率・lessons 反映率)。**KPI**: composition schema 7 種網羅率 100%、依存グラフ生成の自動更新頻度 >= 週次、dogfooding 自己適用率 >= 90%・rubric 充足率 >= 85%。
