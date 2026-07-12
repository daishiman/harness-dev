# elegant-review: notion-gmail-send (config 不在オンボーディング) — run 20260626T134045

## 結論
4条件すべて **PASS**（独立承認者 APPROVE）。30思考法 used=30/skipped=0。pytest 138 passed。退行なし。

## 課題
初回利用で `/run-notion-gmail-dry-run` 実行時、`.notion-config.json` 不在 → ConfigError → exit2 でデッドエンド。`.notion-config.json.example` に本番実 DB ID 3件 + 送信元 `no-reply@shonai.inc` が焼き込まれ、唯一の復旧導線が「実値 example のコピー」になっていた。

## 真因（3 analyst 収束）
- **根本①** 環境固有実値の git 拡散（example + spec-detail に本番 DB ID/impersonate）
- **根本②** 安全な着地点の不在（config 不在 fail-closed の復旧導線が実値コピー・scaffold 欠落。fail-closed の摩擦が危険回避策を強化する因果ループ）
- 派生③ config 配置/DB名称/到達手段の文書間ドリフト
- 派生④ `.gitignore` negation が実ファイル名と不一致（命名規約逸脱）
- 派生⑤ description 肥大 / spec-detail に運用 snapshot 混在

論点再設定: R-USER-1「README 明記」は §2 で字面充足済 → 追記だけでは漏洩/誤送信は解消しない。優先順 = C(実値廃止) > A(scaffold) > B(文書整合)。

## 採用方針（ユーザー決定）
案A: placeholder + 自動生成 scaffold。実値を git から全廃。impersonate は config/Keychain 必須維持（meta M-007: 送信元は DB ID より悪用余地大）。

## 改善（10ファイル +263/-40）
1. **placeholder SSOT** = `notion_config.py CONFIG_SKELETON` 一箇所から example / scaffold / ConfigError 印字を導出
2. example を placeholder 化 + `.notion-config.example.json` へ改名（repo 規約準拠で gitignore negation 実効化）
3. `write_skeleton` / `scaffold_target_path` + `setup_doctor.py --init`（不在時に placeholder 雛形を $CLAUDE_PROJECT_DIR へ生成・上書き拒否）
4. `build-plan.py` の config 不在を**誘導付き停止**へ（scaffold 案内 + 貼付用 JSON 印字・exit2 維持・送信しない）
5. spec-detail の実 DB ID → config 参照 / 運用 snapshot 一般化
6. README §2 を設定方法の唯一正本へ（scaffold 一次・3経路 A/B/C・env 明示）— R-USER-1 充足
7. config 配置文言「作業フォルダ($CLAUDE_PROJECT_DIR・clone は repo-root)」/ DB 名称「メール送信先_DB」へ統一
8. plugin.json description 534→266字
9. **再 leak 遮断テスト** `test_config_scaffold.py`（example==SKELETON / 実値マーカー不在 / scaffold / overwrite拒否）

## fail-closed 不変の保証
placeholder 値（`<…>`）は API 解決不能 → scaffold 生成直後でも実値を埋めるまで dry-run も送信もできない。承認済み plan / 人間承認ゲート / 冪等ログの三本柱は無改変。

## deferred（4条件を妨げない・意図的に未対応）
- `@shonai.inc`（spec-detail:38,115 / ref SKILL:161 の説明文）: 実装 SSOT `doc/仕様と検証メモ.md:319` が abstraction_variable と明示し同ドメインを一貫使用。plugin 側のみ抽象化すると SSOT とドリフト（新 C3）を生むため触らない。
- secrets.py の Notion service hardcode: low smell。config 化は preflight 波及でテストが揺れ、最小・クリーン方針に反する。

## 検証
proposer(orchestrator) ≠ approver(独立 general-purpose subagent)。承認者が git grep / pytest / check-ignore / コード読解で再導出し APPROVE。二段確認で deferred の正当性を実装 SSOT で裏取り。
