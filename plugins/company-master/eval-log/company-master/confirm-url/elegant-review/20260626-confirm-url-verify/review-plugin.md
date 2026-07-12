# elegant-review レポート — company-master 確認用URL/会社名統合の二段検証

- run_id: `20260626-confirm-url-verify`
- scope: plugin (company-master, 未コミット変更)
- 位置づけ: 他AI実装 (`20260626-confirm-url-name-merge`) が R1-R5 を「全PASS」と主張した改善を、**思考リセット後に30思考法で多角検証 + 実装文脈で二段確認**し、矛盾なく完了したかを判定・残バグを改善する。

## ユーザー要件 (R1-R5) と検証結果

| 要件 | 結果 | 根拠 |
|---|---|---|
| R1 郵便番号=固定 `https://www.post.japanpost.jp/` | ✅ PASS | `postal_api.py:73` 単一定義・`validate:295` で固定URL必須・`enrich:307` 参照 |
| R2 電話番号=無料Web検索URL | ✅ PASS | `enrich_company.py:103` `PHONE_SEARCH_BASE` Google完全一致検索・有料DB生成経路0件 |
| R3 会社名(title)=正式名称 | ✅ PASS | `notion_upsert.py:305` `title=official_name or company_name` (新規/補完/移行とも official 優先) |
| R4 正式名称プロパティ削除 | ✅ PASS (**live実測**) | live DB GET=正式名称列なし・会社名=title型・`preflight_schema` PASS。コード(forbidden登録)と整合・矛盾なし |
| R5 本文に余計記述なし | ✅ PASS (**修正後**) | 正式名称bullet/会社名:ユーザー入力 とも forward/backward 両辺で抑止 |

## 検証で発見し改善した実バグ (3独立アナリスト合議 → orchestrator二段確認 → 独立approver REJECT補正)

### [HIGH] クラスタ2 — 既存『正式名称: URL』bullet が再同期で復活・会社名へ重複
- 真因: `parse_bullet` が `正式名称→会社名` リマップを欠く (build_entries/normalize は実装済の片肺)。`merge_entries` が独立正式名称bulletを保持し official_name URL が会社名/正式名称の2 bulletへ重複。
- 修正: `parse_bullet` に `_canon_attribute` を適用 → merge が会社名へ dedup。

### [HIGH] クラスタ1 — `--migrate-company-title` が確定行を0件選定 (no-op) / SKILL.md記述と乖離
- 真因: 正式名称列を物理削除した後、`row_from_page` の `official_name` が title へフォールバックし `company_name` と一致 → 旧トリガ `official != company` が常時 False。R4(列削除)が D6(移行)のトリガ信号を消滅させた依存破綻。テストも `fields` 直接構築で false-green。
- 修正: 移行選定を `hojin_bango`(13桁)保有でトリガ → 再 resolve で登記名取得、冪等判定(official≠title)は `patch_empty_cells` に委譲。`row_from_page`/SKILL.md docstring を正直化。false-green テストを `row_from_page` 経由へ是正。

### [HIGH] R5対称穴 — 既存『会社名: ユーザー入力（URLなし）』が再同期で復活 (独立approverが捕捉)
- 真因: 会社名抑止が `build_entries` の **dict経路のみ**。再同期は `merge_entries` が stale な会社名no-url entryを保持→**list経路**(抑止なし)で再描画し禁止bulletが復活。forward抑止/backward無抑止の片肺。
- 修正: 抑止述語 `_company_bullet_suppressed` を**SSOT化**し dict/list 両経路へ適用。回帰テスト2件追加 (stale会社名非復活 / url有会社名は保持)。

### [LOW] 文言整合 — confirm-url-template.md の R5抑止条件を精密化 (user_input→user_input/none・backward辺も明記)

## 4条件 判定

| 条件 | 判定 | 根拠 |
|---|---|---|
| C1 矛盾なし | PASS | SSOT単一定義健全。前run archive(spec D4/不変条件56)と現schemaの表面ねじれは履歴成果物のみで runtime矛盾なし(live削除済+forbidden+preflight 三者整合)。 |
| C2 漏れなし | PASS (修正後) | R1-R5 全反映。R5 backward辺の2穴(正式名称/会社名:ユーザー入力)を塞いだ。doc追従(columns/data-sources/SKILL/README/schema/validate)済。 |
| C3 整合性あり | PASS | 抑止述語SSOT化で forward/backward 同一規律。select/list 経路の dedup規律一致。 |
| C4 依存関係整合 | PASS | 移行依存を resolveベースへ寄せ no-op を解消。preflight/validate/upsert 依存健全。 |

## 残課題 / 申し送り (PR化時)
- [medium・PR時] 編集した `SKILL.md`(run-company-master-backfill)の content-review verdict が stale-sha。PR化時は独立SubAgentで**現SHA genuine 再生成**が必要(SHA書換は偽装・禁止)。
- [low] 前run eval-log archive は履歴ゆえ非改変。本run findings/verdict が現状(forbidden追加+live削除済=整合)を記録し supersede。
- [info] 移行モードは opt-in。live 既存行の通称→登記名 移行実行はユーザー判断 (コードは対応済・dry-run併用可)。

## テスト
- `tests/test_company_master.py`: **123 passed** (baseline 118 + 新規5)。
- 横断退行: company/confirm/backfill/upsert/enrich/postal/validate スコープ 1061 passed/1 skipped (approver round1 実測)。
