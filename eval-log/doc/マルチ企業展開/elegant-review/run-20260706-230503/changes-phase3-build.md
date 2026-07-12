# Phase 3 改善記録 — 構築手順.md

- worker: 構築手順.md 担当(elegant-review Phase 3)
- 対象ファイル: `doc/マルチ企業展開/構築手順.md` のみ(他ファイル編集なし)
- findings: `eval-log/doc/マルチ企業展開/elegant-review/run-20260706-230503/findings.json`

## 適用修正一覧(対応 finding: paradigm_id/issue)

| # | 箇所 | 修正内容 | 対応 finding |
|---|---|---|---|
| 1 | Phase 1 項目 3(新設) | 取込項目に `scripts/`(検証ゲート用 lint 群: lint-legacy-plugin-name / lint-config-version-sync 等)を明記。旧 3→4、4→5 に繰り下げ | 20/issue3 (C4 low) |
| 2 | Phase 2 冒頭 | 「実値移動の順序(正)」を追加: tenant へコピー → 一致検証 → core から除去(移管計画 §6 Step 5→6 と同順)。逆順禁止を明記 | 9/issue1 (C4 med), 20/issue1 (C1 med) |
| 3 | Phase 2 冒頭 | 「baseline 取得」を追加: genericize 前に各 doctor 出力を取得・保存し、Phase 6-1 の比較対象にする | 主対応 7(6-1 受け入れ基準の成立要件) |
| 4 | Phase 2-1 | 見出しを「SSOT 化」に変更。「集約」を「SSOT 1 実装 + 各 plugin へ vendored 配置 + lint-intake-vendored-ssot.py 方式の同期 lint」に修正(CONVENTIONS.md 層A 自己完結規約との衝突解消)。vendored 箇所数を「現 2 箇所(skill-creator / skill-intake、実測)・Phase 1 取込後 4 箇所」と時点明示 | 19/issue1 (C4 med), 16/issue1 (C1 low) |
| 5 | Phase 2-1 | keychain_prefix 供給順の正本をテナント仕様 §4 への参照に変更。「有効テナントの発見方法(HARNESS_TENANT env / symlink 実体パス逆引き、優先順位はテナント仕様 §6)」と「Phase 2-3 マージ後〜Phase 4 完成前の暫定運用(HARNESS_KEYCHAIN_PREFIX 手動 export)」を明記 | 7/issue3 (C3 low), 20/issue2 (C4 med) |
| 6 | Phase 2-2 | 「照合 3 DB」→「出力 1 DB + 照合 2 DB」に用語修正。退避値はテナント仕様 §4-1 の対応行(env / overlay role)と 1 対 1 で揃えること、特に mf-kessai `database_id` の再注入経路必須を明記 | 6/issue1 (C2 med), 6/issue2 (C3 low) |
| 7 | Phase 2-3 | party_a env 改名(PARTY_A_JSON_PATH 正準 / XL_PARTY_A_JSON_PATH 期限付 alias、正本はテナント仕様 §4-3)を退避対象に明示。impersonate/google-sa の受け皿を `gmail-config.json`(契約はテナント仕様 §5)と明示。google-config(spreadsheet_id / 出力フォルダ ID / slack_channel)と Slack Bot Token keychain 名(現 `skills-slack`)を退避対象に追記 | 11/issue1 (C3 med), 27/issue2 (C1 med), 24/issue1 (C2 **high**), 3/issue1 (C2 med) |
| 8 | Phase 2-4 | lint 検査パターンに大小無視の `xl[-_]`(bare xl- と XL_ 接頭辞)を追加。正当例外は期限付き allowlist と明記 | 15/issue1 (C2 med), 27/issue1 (C3 med), 2/issue1 (C1 med) |
| 9 | Phase 2-5 | 前提資産(Makefile ターゲット / config-version-lock.json / 同 lint)が Phase 1 取込で到来している前提を注記(移管計画 §6 Step 2 参照) | 17/issue3 (C4 med, 構築手順側の分) |
| 10 | Phase 2 完了確認 | 「判定は lint のみ、目視 grep は補助」と役割宣言。grep を lint 仕様に整合(`-i` 付き、`-e 'xl[-_]'`、対象に installers / .claude-plugin 追加、実ヒットを隠す `grep -v placeholder` を除去) | 8/issue1 (C2 low), 15/issue1 |
| 11 | Phase 3 項目 1・2・5 | _template / tenants/xlocal の内容物と commit する/しないリストに gmail-config(.example).json / google-config(.example).json を追加 | 3/issue1 (C2 med), 18/issue1 (C2 **high**, 構築手順側の分), 24/issue1 (C2 **high**) |
| 12 | Phase 3 項目 3 | 既存 Keychain エントリが旧 service 名のまま残り新名称 `<purpose>.xlocal` への再登録が必要になること(移行支援は Phase 4)を言及 | 29/issue1 (C2 med) |
| 13 | Phase 3 項目 4 | 有効化競合時の優先順位の正本をテナント仕様 §6(NOTION_CONFIG_PATH > HARNESS_TENANT > symlink)への参照で明記 | 7/issue1 (C2 med), 17/issue1 (C2 med)(いずれも構築手順側の分) |
| 14 | Phase 4 tenant-build | 「旧 service 名からの移行支援(旧エントリ検出 → 新名称再登録コマンド提示 → 旧エントリ削除案内)」を仕様追記 | 29/issue1 (C2 med) |
| 15 | Phase 5 冒頭 | 導入者ペルソナ(macOS + Claude Code を使えるエンジニア、Keychain は macOS 前提、CI/Linux は env fallback、非技術者はスコープ外)を 1 段落追加 | 29/issue2 (C2 low) |
| 16 | Phase 5 項目 1 | bundle 二案併記を「tenant.json.enabled_bundles から tenant-build が導出する生成方式」に一本化。core bundles.json への企業別 bundle 追加案は README §4 分離線違反 + lint 検査対象への企業名書き込みを理由に棄却と明記。完了確認も「core の bundle 定義は不変」に整合 | 13/issue1 (C1 med) |
| 17 | Phase 6-1 | 前提条件に「Keychain 新名称への再登録完了(Phase 4 移行支援使用)」を追加。受け入れ基準の比較対象を「Phase 2 冒頭で保存した baseline」に接続 | 29/issue1 (C2 med), 主対応 12 |
| 18 | Phase 6-2 | demo-corp 設定を「tenant.json に keychain_prefix、notion-config.json にダミー DB ID」と書き分け。基準 2 に tenant-doctor の解決値ダンプ(dry-run)モードによる機械照合手順を追記。「2 社目で最低 1 plugin の e2e」を任意ゲートとして追記(未実施時の証明範囲限定も明記) | 2/issue2 (C3 low), 28/issue2 (C2 low), 12/issue1 (C2 low) |
| 19 | Phase 7 前提条件 | xl-skills 変更凍結宣言(凍結日時・基準 commit 記録)+ 切替前の差分再同期レビュー(手順正本は移管計画 §6)を追加 | 21/issue1 (C2 **high**, 構築手順側の分) |
| 20 | Phase 7 項目 2・4 | symlink 既定に決着(mirror はツール互換問題が実測された場合のみの代替、1 行)。tenant 側からの貢献フロー(harness への PR → リリース後 symlink 経由で全 tenant へ伝播)を追記 | 22/issue1 (C1 low), 23/issue1 (C2 low) |
| 21 | Phase 7 | 「cutover / rollback」節を新設: cutover 判定条件(Phase 6 全緑 + 並行検証)と rollback 手順(退避実体コピーへ戻し xl-skills 単独運用へ復帰、退避物保持) | 25/issue1 (C2 med) |

severity high のうち構築手順.md に修正を要する 3 件(18/issue1・21/issue1・24/issue1 の構築手順側)はすべて適用済み。

## skip と理由

| finding | 理由 |
|---|---|
| README.md 系(1/issue1-2, 10/issue1-2, 12/issue1 の README 側, 15/issue2, 16/issue1 の README 側, 19/issue2, 28/issue1, 18/issue2-3, 30/issue2) | 担当外ファイル。別 worker が対応 |
| テナント仕様.md 系(2/issue1 の仕様側, 3/issue2, 4/issue1, 5/issue1, 6/issue3, 7/issue1 の仕様側, 11/issue1 の仕様側, 14/issue1, 17/issue1 の仕様側, 17/issue4, 24/issue1-2 の仕様側, 26/issue1, 27 の仕様側) | 担当外ファイル。構築手順側は正本参照で接続済み(重複追記禁止の制約に従い、規則本文は書かない) |
| 移管計画.md 系(7/issue2, 9/issue2, 17/issue3 の移管計画側, 21/issue1 の Step 6.5, 30/issue1-2) | 担当外ファイル |
| 17/issue2(gitignore 実値のバックアップ・復元手順) | 規定の正本はテナント仕様 §7 側(tenant.json notes 規定 or private repo 方針)であり、全 worker 共通の整合決定・主対応 14 項目に含まれない。構築手順への重複追記は制約違反のため skip |
| variable_abstraction `@shonai.inc`(構築手順 Phase 2-3) | 当該行は「退避すべき焼き込み実値のインベントリ」であり、具体値の特定自体が手順の内容。findings 自身が「doc は lint allowlist 対象」と注記しており、抽象化すると退避対象が特定不能になるため保持 |
| variable_abstraction `~/dev/dev/xlocal/xl-skills` / `daishiman/meta-skill-creator` | 構築手順.md 内の残存は Phase 7 完了確認の `test -L ~/dev/dev/xlocal/...` のみで、実行者のローカル環境検証コマンドとして具体パスが必要。README 側の直書きは別 worker 担当 |

## 検証

- `grep -c 'TODO(human)' 構築手順.md` → 0(新設なし)
- 見出し体系(Phase 0-7 / 2-1〜2-5 / 6-1〜6-2)・トーン維持を全文 Read で確認
- 他文書からの参照整合: テナント仕様 §4「本節が正本。構築手順 Phase 2-1 はここを参照する」/ README §5 の lint-intake-vendored-ssot 行と本修正が噛み合うことを grep で確認
- 事実実測: vendored `notion_config.py` は現 2 箇所(find で確認)、`scripts/lint-intake-vendored-ssot.py` 実在、bundles.json は `skills-full`/`skills-minimal`/`skills-intake`(中立名済み)

convergence_status: **converged**(担当スコープ内。残リスク: doc/マルチ企業展開/ は Git 未追跡のため diff レビュー不可 → コミット時に全文レビュー推奨)
