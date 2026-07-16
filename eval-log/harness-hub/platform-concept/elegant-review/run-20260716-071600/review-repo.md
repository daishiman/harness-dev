# elegant-review レポート: doc/harness-hub-platform-concept.md

- run_id: run-20260716-071600
- 実施日: 2026-07-16
- 対象: doc/harness-hub-platform-concept.md (Harness Hub プラットフォーム構想、decision proposal)
- 前回 run: run-20260715-r2 (Beads harness-ny2、CLOSED)

## 実行サマリー

| Phase | 担当 | 結果 |
|---|---|---|
| 1 思考リセット・素観察 | elegant-reset-observer (context fork) | shared_state.md + raw_observations.json 生成 |
| 2 並列多角的分析 | logical-structural / meta-divergent / system-strategic の3並列 | 30 思考法 30/30 使用 (skip 0)、findings 71 件 (high 14 / medium 39 / low 18) |
| 3 改善実行 | elegant-improvement-executor → 独立 approver 検証 | 71 件全件解消、iteration 1 で収束 |

## Phase 2 検出時の 4 条件

| 条件 | 検出時 | 改善後 (独立検証) |
|---|---|---|
| C1 矛盾なし | PARTIAL (violation 1) | **PASS** |
| C2 漏れなし | FAIL (violation 45) | **PASS** |
| C3 整合性あり | FAIL (violation 9) | **PASS** |
| C4 依存関係整合 | FAIL (violation 14) | **PASS** |

## 主要改善 (high 14 件の代表)

1. **意思決定手続きの欠落** → ヘッダに Decision requested (承認対象・承認者・判断基準・期限・却下時) を追加
2. **中心前提「障壁は2」の出典欠如** → 未検証前提と明示し仮説 H0 として §19 へ接続
3. **§7.2 状態機械と MVP スコープの依存断絶** → MVP 状態機械サブセット (Yellow/Red→Needs Fix、Approval Pending は Stage 2 で開放) を明記
4. **web_app deploy の実行主体未確定** → 作者 local session の wrangler CLI 実行に確定、§6 図に実行境界 subgraph を追加
5. **Green 自動公開の判定不能** → §9 に機械判定規則と境界語の暫定定義、instructions 高リスクパターン検出 (Yellow 降格) を追加
6. **§19 仮説の合否基準欠如** → H0〜H10 の表形式 (検証手段・判定指標・合格ライン・判定時期) へ再構成
7. **MVP に Hub 認証が欠落** → 既存 IdP/SSO への委譲を明記

## ユーザー要件の反映 (2026-07-16 セッション中の追加指示)

- **R1 (CLI 主経路)**: Cloudflare への deploy は MCP でなく wrangler CLI / API のスクリプト実行を主経路に変更。MCP は「不採用 (不要ツール混入)」として §16.1 代替案比較に降格。HH-D13 新設
- **R2 (Cloudflare DB)**: D1 を標準、KV・R2 と合わせ顧客 Workspace 内 provision。HH-D14 新設
- **R3 (配布モデル)**: URL 型 marketplace (`/plugin marketplace add <URL>`) の公式仕様と制約 (marketplace.json のみ取得、相対パス source 不可) を §8.1 に明記。完全 Git レス配布は R2/Workers + Bootstrap Installer 経路。Stage 0 technical gate に検証項目化
- **R3 追補 (claude-code-guide 公式裏取りによる訂正)**: plugin 本体 source は Git ベースのみ対応 (GitHub / `.git` 終尾 git URL / git-subdir)。**npm・HTTPS 直配信は非対応**。private Git は利用者認証 (PAT/SSH) が必要で不変条件 (GitHub アカウント不要) と衝突するため、認証なし読み取り可能な git 経路が確保できない場合は Bootstrap Installer を使う。third-party marketplace は既定で自動更新無効 (手動 update 導線を前提に設計)。§8.1 / §14 Stage 0 を修正済み
- **R4 (harness-creator 接続)**: harness-creator 製 harness が Publisher の第一の入力である旨を §15 に明記

注: 本 run はドキュメントの検討・改訂のみ。デプロイ・実装は実行していない (対象ドキュメントの Scope 宣言どおり)。

## 残存リスク (residual_risks)

- 合格ライン等の数値はすべて仮置き (文書内に仮置きと更新条件を明示済み)。Stage 0 実測で更新する
- §2.2 の障壁前提と西山モデル原典は一次資料が存在せず、H0 検証へ委譲 (H0 不成立なら構想棚上げ)
- URL 型 marketplace の認証ヘッダー挙動・wrangler での非エンジニア公開完了性は文書裏取りのみで実機未検証 (Stage 0 の gate)
- Mermaid 図はレンダラーでの構文検証未実施

## 検証記録

- validate-paradigm-coverage.py findings.json → OK (30/30)
- validate-paradigm-coverage.py --phase-order → OK (Phase 1→2→3 順序整合)
- 独立 approver (別 SubAgent context) → approve: true (high 14 全件解消・R1〜R4 反映・新規欠陥は low 2 件のみ→本 run 内で修正済み)
- emit-observable.py → {"emitted": false, "reason": "all_pass"}
- proposer ≠ approver: 充足 (executor と approver は別 context)

## ロールバック情報

- pre-phase3.patch は tracked ファイルのみ捕捉。対象ドキュメントは untracked のため patch 外だが、改訂前全文 (836 行、blob 4ebab851) は前回 run (run-20260715-r2) 時点の内容としてセッション記録から復元可能
