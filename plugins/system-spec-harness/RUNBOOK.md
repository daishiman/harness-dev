# system-spec-harness Runbook

## Purpose
システム構築 (Web/モバイル/タブレット/デスクトップ横断) の仕様情報を往復ヒアリングで漏れなく収集し、章立て複数 Markdown + index の仕様書ドキュメントセットへまとめるハーネスの運用手順。

## Entry Points
- `/spec-hearing-start [--resume] [--status]` — 往復ヒアリングを起動 (C09→C01)。`--status` は収集マトリクス充足状況のみ表示。
- `/spec-compile [--out-dir DIR]` — 収集済み仕様を章立て仕様書へコンパイルし (C10→C03)、完了後に完成度評価 (C05) を自動連鎖。
- Skill: `run-system-spec-elicit` / `run-system-spec-doc-fetch` / `run-system-spec-compile` / `ref-system-design-knowledge` / `assign-system-spec-completeness-evaluator`。

## Environment
- Python 標準ライブラリのみ (.sh/.js 新規禁止・scripts 内 yaml import 禁止)。
- スクリプト起動は repo-root cwd 前提、skill 資産は self-relative 参照。
- 中間成果物: `spec-state.json` (収集マトリクス+質疑ログ) / `fetched-references.json` (出典記録) / `system-spec/*.md` + `index.md` (仕様書ドキュメントセット)。
- 最新公式ドキュメント取得は WebSearch/WebFetch のみ (MCP 連携は将来拡張・GAP-MCP-DOCFETCH)。

## Write Protection
- `spec-state.json` の確定状態は C01/C03 所有の単一 transition writer のみが変更する。
- 確定済み章 (`system-spec/` 章 frontmatter `status: confirmed`) への Write/Edit/Bash は `hooks/guard-confirmed-chapter-overwrite.py` (PreToolUse・fail-closed exit2) が補助防御で遮断する。
- 確定セルの再オープンは C01 R4-reopen 経由のみ。再オープン状態のセル対応章は hook が通す。

## Verification
- 収集マトリクス網羅性 (C7): `python3 scripts/validate-coverage-matrix.py --matrix spec-state.json [--require-complete]`。
- 出典記録 (C5): `python3 scripts/validate-source-citation.py --targets <targets.json> --references fetched-references.json`。
- 独立監査: `system-spec-hearing-auditor` (聞き漏れ/誘導/早期停止) / `system-spec-matrix-auditor` (マトリクス状態) / `system-spec-doc-freshness-auditor` (公式サイト再照合)。
- 完成度評価: `assign-system-spec-completeness-evaluator` が3観点 (網羅性/設計知識反映/出典) で PASS/FAIL 判定。
- テスト: `python3 -m pytest plugins/system-spec-harness/tests -q`。

## Acceptance Evidence
- 受入観点 (C1-C12) の plugin 内正本は `docs/evidence.md` (C1-C12 受入 Matrix) と `EVALS.json`。計画側正本 `plugin-plans/system-spec-harness/phase-07-acceptance-criteria.md` は repo-only (配布物には含まれず単独 install 環境では非解決)。
- 6周超サンプル対話で5周目に状態保存+resume が働くこと (C3)。
- 生成仕様書がカテゴリ別収集状態 (未着手/収集中/確定/対象外+理由) を各章に明示すること (C1)。

## Recovery
- ヒアリング中断: `/spec-hearing-start --resume` で `hearing_progress` から再開。
- マトリクス不整合: validate-coverage-matrix.py の VIOLATION を解消してから再コンパイル。
- 誤った確定: C01 R4-reopen で根拠付き再オープンしてから修正 (直接編集は hook が拒否)。
- 改善要望: `/run-skill-feedback system-spec-harness` で投入。

## Governance Operations

### knowledge_candidates の curated 昇格手順
project-local な `knowledge_candidates[]` (C01 `spec-state.json`) を C04 の curated catalog へ昇格させる運用。形状と status 遷移の正本は `skills/ref-system-design-knowledge/references/open-world-knowledge-lifecycle.md` と C01 `references/spec-state-contract.md`。
- **承認者 (approver)**: C04 curated catalog の保守担当。候補の起票者 (C01/C02 実行者) 自身は承認できない (proposer≠approver)。
- **昇格トリガ**: candidate が `deepened` に到達し、汎用性 (複数 project へ再利用可能)・既存カード非重複・deep-card 必須意味項目充足・一次/公式資料あり・freshness policy ありの 5 条件を全て満たしたとき。`set-knowledge-candidate` で `status:"promoted"` へ進める際に `curation_ref` (承認記録と curated 配置先) を必須付与する。自動昇格は禁止。
- **棚卸し周期**: 四半期ごと (次回 2026-10-11)、および `card.freshness.review_by` 到来時・破壊的変更/標準改訂/security advisory/vendor EOL/価格改定の即時トリガ時。棚卸しで未確認の候補は `stale` と明示し、最新推奨の根拠に使わない。重複候補は新設せず既存 curated カードへ統合する。

### 初回実運用後の EVALS 再評価 (baseline 更新)
`EVALS.json` の各 `evaluations[]` は現在 `verdict:"baseline"` (build 直後の初期宣言・findings 空)。
- **トリガ**: 初回の実 `/spec-compile` 実行 (実プロジェクトでの初回コンパイル+C05 完成度評価) 完了後。
- **手順**: C05 が返した観点別スコアと総合判定を、対応する skill の `evaluations[]` エントリへ実測 verdict (`pass`/`fail`) と findings で追記し、`baseline` 行はそのまま履歴として残す (上書きしない)。`docs/evidence.md` の C1-C12 受入 Matrix の状態列と齟齬がないか照合する。
- **期限**: 初回実運用から 2 週間以内、遅くとも 2026-08-11 までに baseline を実測 verdict へ更新する。未実施の間は EVALS の合否は build 時点の baseline であり実運用の受入根拠にしない。
