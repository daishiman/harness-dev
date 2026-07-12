# elegant-review レポート: notion-gmail-send（plugin scope）

- run-id: `20260625T234836-ngs-marketplace`
- 症状: notion-gmail-send が Claude Code マーケットプレイス一覧に表示されない
- 結果: **4 条件全 PASS / status: complete / iteration 1 で収束**

## 真因（3 エージェント独立検証で一致）
直接原因はルート `.claude-plugin/marketplace.json` の `plugins[]`（13 件）への notion-gmail-send 未登録。
真因は plugin 公開の SSOT が 3 集合（実体ディレクトリ / marketplace.json / bundles.json）に分かれているのに、**実体起点で全集合の登録を強制する機械ゲートが無い**こと。bundles 漏れ検査器 `validate-plugin-completeness.py`（BD-001）は実装済だが CI 未配線で腐り、marketplace 漏れ検査器は不在だった。`lint-plugin-lint-coverage.py` が marketplace を起点に巡回する設計のため、未登録 plugin は検査集合に入らず永久に見逃される「漏れが漏れを隠す」自己強化ループに陥っていた。

## 30 思考法カバレッジ
- 論理構造系 10 / メタ発想系 9 / システム戦略系 11 = **計 30、skip 0**
- 当初の単一仮説（marketplace 登録漏れ）を独立 fan-out が超え、KJ 法で第 2 の登録漏れ（bundles.json 矛盾）と構造欠陥（双方向整合 lint 不在）を追加発見

## 改善内容（ユーザー選択: フル）
| finding | 修正 | ファイル |
|---|---|---|
| F1 (critical/omission) | marketplace.json plugins[] へ登録（14 件目・他と同形式・簡潔 description） | .claude-plugin/marketplace.json |
| F2 (high/contradiction) | bundles.json xl-skills-full へ登録（plugin.json 宣言との矛盾解消） | .claude-plugin/bundles.json |
| F3 (medium/smell) | marketplace description を 111 字の簡潔版に（core value 文頭） | .claude-plugin/marketplace.json |
| F4 (high/dependency_break) | marketplace↔plugins 双方向整合検査 MK-001/002/003 を追加（実体起点・既存 BD-001 と対称） | scripts/validate-plugin-completeness.py |
| F5 (high/omission) | 検査器を 3 CI surface に hard 配線（自己強化ループを機械遮断） | scripts/run-ci-checks.sh, Makefile, .github/workflows/governance-check.yml |

## 4 条件判定（独立 approver）
- C1 矛盾なし: PASS（plugin.json bundle 宣言 ⇔ bundles.json 一致、MK-003 で name 三者一致を機械保証）
- C2 漏れなし: PASS（14 plugin 全てが marketplace+bundles 登録、validator `OK: 14 plugin(s) complete`）
- C3 整合性あり: PASS（description 粒度統一、loader が既存と対称設計）
- C4 依存関係整合: PASS（検査器→CI が hard、未存在時 fail-open しないガード確認）

## 検証
- `python3 scripts/validate-plugin-completeness.py` → exit 0（14 plugin complete）
- 負例テスト: marketplace から notion-gmail-send 除去 → MK-001 発火・exit 1（検査器がオオカミ少年でなく実機能）
- proposer（executor）≠ approver（独立 general-purpose SubAgent, APPROVE）

## 残リスク / deferred
- marketplace 表示はローカルでは marketplace 再 add／キャッシュ更新で反映。リモート公開（public repo の一覧）への反映は push が必要（未コミット状態）
- notion-gmail-send の entry_points.skills(6) と skills/ 実体(7=run-skill-feedback symlink) の差は本タスク前から存在する既存設計事項（スコープ外・MK/BD 検査では FAIL しない）
