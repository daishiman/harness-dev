# changes-phase3-readme.md

worker: exec-readme(編集完了後に接続エラーで停止。本ログは orchestrator が適用済み diff の実測に基づき代筆)

## 適用修正(7件、指示 1-7 全対応)

1. §5 再利用マップ: 「所在」列を追加し、config-version-lock.json + lint-config-version-sync.py を「xl-skills にあり Phase 1 で取り込む(現 harness に不在)」と明示。notion_config.py の 4層解決は「現存2箇所 / company-master・harness-creator 分は未取込」と時点明示。lint-intake-vendored-ssot.py 行を新設(vendored+SSOT 同期規約、物理集約はしない)。doctor 行も現存/未取込を区別(批判的思考 C1 / メタ思考 C1 / システム思考 C1 対応)
2. §2 「36 箇所以上」に再現コマンド(git grep 集計: 70ファイル/265ヒット)と「Phase 2 の lint-tenant-isolation.py 新設時に再計測」を併記(批判的思考 C2)
3. §3 「なぜ harness か」棄却代替案2件と理由を追記(メタ思考 C2)。「仮説の境界」(fork せず opt-in 機能フラグ+判断記録)を追記(仮説思考 C2)
4. §4 ツリー: tenants/_template に gmail-config.example.json / google-config.example.json、tenants/xlocal に実値 gitignore 注記を追加(帰納的思考 C2 の README 分)
5. §1 決定表: 「本 repo が private であること」前提条件行を追加、public 化時は tenants/ 別 private repo 分離と併記(素人思考 C2)
6. ドキュメント一覧の下に Phase↔Step↔PR の3列対応表を新設(KJ法 C4)
7. §2 末尾に 2 社目見込み(未確定でも構造化自体を投資根拠とする)1行(逆説思考 C2 low)

また「doc 29/03/23」の内部番号参照を相対リンクに置換(素人思考 C4 low)。

## skip

- なし(README 担当分は全件適用)
