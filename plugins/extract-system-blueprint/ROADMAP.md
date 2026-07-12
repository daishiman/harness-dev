# ROADMAP

`extract-system-blueprint` plugin の短期 / 中期 / 長期ロードマップ。harness-creator 設計書 33 章 `change-governance` の運用方針に従い、各層は目標・成果物・成功指標 (KPI) を明示する。plan P13 (release) は PR/配布を soft note (評価ゲート化しない参考注記) に留めており、その残タスクを短期へ引き継ぐ。

## 短期 (本 PR 〜 次 1-2 スプリント) — P13 soft note の残タスク

**目標**: marketplace 登録前チェックリストを完走し、配布経路を確立する (登録は manual-user-gated=ユーザー承認後の人手作業)。**成果物**: (1) feature→main のマージ (make validate + pytest 緑前提)、(2) `.claude-plugin/marketplace.json` / `bundles.json` への登録エントリ (承認後。登録と同時に plugin.json / envelope-draft の `bundle_targets` を `["harness-full"]` へ復元する — bundles.json 未登録の間は `[]` で正直化)、(3) 登録完了までの現行経路 (リポジトリ clone + `.claude` symlink ローカル導入) の README 明記。**KPI**: PKG 検査 100% PASS、plugin-composition lint 100% PASS、install 後の namespace 起動 (`/extract-system-blueprint:extract-blueprint`) 成功。

## 中期 (3-6 ヶ月)

**目標**: 実 run の観測データで評価ループを回し、抽出忠実性を計測可能にする。**成果物**: EVALS.json baseline の実 run 更新、observability.metrics (fetch_budget_utilization_per_origin / fact_inference_gap_ratio / verdict_pass_rate) の request ledger からの集計経路、full_site multi-run resume の実サイト実証。**KPI**: verdict_pass_rate >= 80% (2 周以内)、鍵画面の静的観測被覆 100% (取得可能 field 全数・レンダリング必須 field は observation_gap 明示)、PASS 後の blueprint 手戻り修正 < 1 件/run。

## 長期 (6 ヶ月以降)

**目標**: 抽出→適用 (C14) の往復を自社開発サイクルへ常設し、レンズ roster と分析プロンプトの自己改善ループを確立する。**成果物**: apply-recommendations の採用実績 write-back (eval-log 経由) による expert-lens-roster / analyzer prompt の改訂パイプライン、対象システム種別 (SaaS/EC/メディア等) ごとの分析プリセット。**KPI**: apply-recommendations の自社採用率 >= 50%、レンズ改訂の四半期反映 >= 1 件、同一対象の再抽出における fact 差分検出率 (drift 検知) の運用開始。
