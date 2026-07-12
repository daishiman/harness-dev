# changes-phase3-spec.md

worker: improvement-executor(前半) + exec-spec(後半)。両者とも編集完了後の報告段階で接続エラー停止。本ログは orchestrator が適用済み diff の実測に基づき代筆。

## 適用修正(テナント仕様.md)

### 前半(improvement-executor)
1. §1 ツリーに gmail-config(.example).json / google-config(.example).json の4行追加(帰納 C2 / 価値提案 C2)
2. §2 例: enabled_bundles を実在名 "skills-full" に修正+実在の fail-closed 検証注記(why思考 C4 / 改善思考 C3)
3. §2 例に overlays.google_config slot 追加、party_a 注記に §4-3 参照付与
4. §2 例に notes フィールド(実値の出所記録)追加(if思考 C2: バックアップ・復元経路)
5. §2 表: keychain_prefix 一意性(tenant-init 重複拒否 / tenant-doctor 横断検査)(if思考 C2 low)、enabled_bundles 実在要件、overlays.gmail_config / overlays.google_config / notes 行追加(帰納 C2)
6. §3 例に japanpost-da-api purpose 追加(要素分解 C2 low)、slack-bot-token purpose 追加(価値提案 C2 high)
7. §3 gdrive account を実測値 "contract-generate/service-account-json" に修正(垂直思考 C1)+ (service,account) 両一致規則を明記

### 後半(exec-spec)
8. §4 冒頭: keychain_prefix 供給順の正本化(HARNESS_KEYCHAIN_PREFIX → 有効テナント tenant.json → fail-closed)(MECE C3)
9. §4-1: 列名を「env 不在時のフォールバック先」に変更し層分類を明記(帰納 C3 low)、mf-kessai `database_id` 行(MFK_DATABASE_ID、Phase 2 新設)を追加し構築手順 §2-2 と1対1対応(要素分解 C2)
10. §4-2: slack-bot-token 行(規約外 service 互換)追加(価値提案 C2 high)
11. §4-3: PARTY_A_JSON_PATH 正準/XL_PARTY_A_JSON_PATH 期限付 alias(WARN 付き)、alias 撤去条件(Phase 6 全緑後の schema_version bump 時)、tenant-build 両名エクスポート(演繹 C1 / 抽象化 C3 / 改善 C1)
12. §5: google-config.json 契約新設 — 必須キーは現実装 config_auth.py::REQUIRED_KEYS 実測(spreadsheet_id / templates_folder_id / individual_folder_id / corporate_folder_id + slack_channel + Keychain 参照名)。example のみ commit・実値 gitignore・fail-closed(価値提案 C2 high)
13. §5: overlay 実値ファイルの drift 検査契約(example の必須キー集合 ⊆ 実値のキー集合を tenant-doctor が検査)(水平思考 C2)
14. §5: overlay slot 追加時の更新チェックリスト(同一 commit で 6 箇所更新)(アブダクション C2: 根本原因対策)
15. §5: doc 29/03/23 を相対リンク化(素人思考 C4 low)
16. §6: 有効化競合の優先順位(NOTION_CONFIG_PATH > HARNESS_TENANT > symlink)+ 不一致時 tenant-doctor FAIL(MECE C2 / if思考 C2)
17. §7: gmail-config / google-config の example(commit)・実値(gitignore)4行追加(帰納 C2)

## 残置(人間判断待ち)
- §5 gmail-config.json の必須キー契約: TODO(human) を残置(227行目、全体で1つのみ)。設計判断(impersonate の単一/複数、委任ドメインの持ち方、fail-closed 規則)を人間が記入する
