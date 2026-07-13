---
id: P05
phase_number: 5
phase_name: implementation
category: 実装
prev_phase: 4
next_phase: 6
status: 未実施
gate_type: tdd-green
entities_covered: [C01, C02, C03, C04, C05, C06]
applicability:
  applicable: true
  reason: ""
---

# P05 — implementation (実装)

## 目的
全 6 component (C01〜C06) を後段 builder へ委譲して実体化し、P04 で設計した criteria を満たす (Green) 状態にする。build routing は `component-inventory.json` の依存 top-sort 順に実行する (phase 順 ≠ build 順)。

## 背景
build は phase 順ではなく component の依存 top-sort 順に走る。本改善では build 順序を **C04 (既存 hook の in-place 拡張・依存なし) と C06 (冪等 sink・依存なし) を先行させ、次に C05 (`depends_on: [C04]`・guard の SANCTIONED 拡張が完了して初めて生成可能) を build し、その後 C01 (`depends_on: [C05, C06]`) を build し、最後に C01 に依存する C02・C03 を build する** 順序 (C04, C06 → C05 → C01 → C02, C03) で確定する。C04 は新規生成でなく既存 203 行の hook (`R1-R3`/allowlist/`guard-mfk-readonly.py` 配線) を保全した Edit 差分適用 (`build_mode=extend-existing`) である点が他の component と異なる。手続き的な build 順は `handoff-run-plugin-dev-plan.json` の routes が SSOT であり、本フェーズはその実行結果 (到達状態) を宣言する。

## 前提条件
- P04 で C01/C05/C06 等の criteria が Red で確定している。
- `handoff-run-plugin-dev-plan.json` の routes が inventory 由来で用意されている (C04, C06 → C05 → C01 → C02/C03 の依存順)。
- 後段 builder (run-skill-create / run-build-skill / plugin-scaffold) が利用可能。

## ドメイン知識
build 順の不変条件 (inventory DAG の top-sort 順) と builder 種別の実行実体差は index/io-contract §9 を参照。本 plan 固有の差分: C05/C06 は `placement_scope=plugin-root` ゆえ `builder=plugin-scaffold` で `plugins/mf-kessai-invoice-check/scripts/` へ hoist される。C05 は `depends_on=[C04]` により、既存 guard の SANCTIONED_BASENAMES に `mfk_period_report.py` が追加され `_REINVENT_DEF_RE`/`_DOMAIN_RE` が拡張された後でなければ生成できない (新規 classify 系関数を持つため既存 guard に遮断される)。C04 の拡張は `build_args.preserve` (R1-R3/allowlist/guard-mfk-readonly.py 配線/plugin.json hooks 配線) を保持した Edit 差分として適用し、上書き破壊しない。C06 の実装は **単一恒久 report DB の既存確認 + 冪等上書き** (Design D) を実体化する: `report_toggle_block` を歴史的キー名のまま「出力先ブロック/見出し」として扱い、(1) トグル内既存 report DB (`in-block`)、(2) プレーン見出し2直下の既存 report DB (`under-heading`)、(3) ページ直下の既存 report DB (`page`)、(4) 未存在時のみ指定ページ『請求書発行チェック』(論理キー `report_parent_page`) 直下へ新規 DB (`page-created`) の順に解決する。Notion API は database 作成の親に block_id を指定できないため新規作成はページ直下だが、UI でトグル内または見出し直下に置かれた既存 DB は更新できる。同一対象月なら単一 report DB 内で行キー `(対象月, 取引先名, 商品名)` により既存行を更新して重複行を作らず、別月/過去 run の行は非破壊保持する。親ページ ID/出力先ブロック ID は具体値を実装・plan 双方に焼かず、実行時 config(`mf-kessai-config.default.json` 配布既定 + `.notion-config.json`/`.mf-kessai-config.json` 上書き)から解決する。DB 生成と 8 列スキーマ/列型写像は既存 `build_notion_db.py` の `build_property` を再利用し title(=各行=ページの作成/ページ名)プロパティ=取引先名・列順を [取引先名, 対象月, 漏れチェック, 商品名, 先月の金額, 今月の金額, 先月と今月の比較, コメント] に固定する。upsert は非破壊マージ(以前 run の行を削除しない=deleted 0・以前の情報が消えない)、HTTP は `notion_transport._req` を単一正本としテストは req 引数でモック差し替え可とする。GAP-NOTION-TOGGLE-PLACEMENT は Design D で解消済み(トグル配下への DB 直接生成は API 不能、link_to_page 索引方式も採用しない)。C05 は契約完了を既存 `has_end_basis`→`SUPPRESS_ENDED` verdict の消費で実装し(自由文を再パースしない・根拠なき終了月は REVIEW_ENDED_NO_BASIS を保全)、年契約正常化は既存 `SUPPRESS_ANNUAL`/`MATCH_ANNUAL` を一次源にする(12 ヶ月遡りは補強のみ)。C04 の再発明シグネチャは語幹前方一致で焼き C05 実関数名と byte 一致を取る(名前ゆらぎ回帰テストを追加)。

**2026-07-10 実運用フィードバック是正 (4 要件・本 P05 で C05/C06 へ差分適用)**:
- (要件1 継続発行=権威ある月契約正常) C05 は `STATE_CONTINUED`(今月あり×前月あり)を必ず `GAP_OK`(正常✓)で emit する(両月に請求=定義上の月契約であり年契約ではない)。C06 sink は `period_diff`『継続発行』を `_STRUCTURAL_NORMAL_MARKERS` へ加え、cross-run safe guard(前 run の要対応☐保持)を bypass する権威ある正常事由に含める。これにより `reliable_issued` 未確定(legacy/verdict-issued 行)でも継続発行の正常✓が確実に反映され『金額あるのにチェックが入らない』を根治する。**`period_diff` の正常マーカー語彙(『継続発行』等)は C05 定数を単一 SSOT とし、C06 の `_STRUCTURAL_NORMAL_MARKERS` は同定数を参照して byte 一致させる(C05=正本・C06=参照・回帰テストで byte 一致固定=マーカー drift 封鎖)。列7『先月と今月の比較』の表示テキスト(例『先月比 +11,000円(新規発行)』)とカテゴリ状態トークン(period_diff)の関係は、状態トークンが categorical 完全一致 (=『継続発行』) で marker 判定に使われ、表示テキストは人間可読の付随説明として prefix にトークンを含む契約とする(marker 判定はトークンの完全一致で行い自由文の部分一致に依存しない)。ただし『権威ある正常』の主張範囲は発行の存在に限定し、金額 drift(過少請求等)は REVIEW_* としてコメント注記に留め正常✓は据え置く。**
- (要件2 出力先の確実な着地) C06 `resolve_report_db` に明示 DB pin 経路(config `report_database_id`・ビュー/DB URL 許容)を step 0 として最優先で追加し、未設定時のみ現行の構造的同定(`in-block`→`under-heading`→`page`→title 前方一致)へ fallback する。明示 pin なし かつ 既存 report DB 未発見時は `page-created`(phantom DB)を安易に作らず警告して停止し、新規作成は明示 opt-in 時のみ許す。config two-layer 分離は保ち plan/実装に具体 ID を焼かず論理キー `report_database_id` を宣言する。
- (要件3 要マスタ登録=正常✓) C05 `_orphan_rows`(MF実績あり×請求確認シートに契約なし)の `gap_check` を `GAP_ACTION`→`GAP_OK`(正常✓)へ反転し、コメント『要マスタ登録(シートへ契約追加 or MF顧客ID登録で名寄せ恒久化)』を保持する。請求確認シートの『契約なし』を漏れ(要対応)扱いしない。
- (要件4 フローチャート SSOT+安全網) C05 の 4 状態分類はユーザー提供フローチャートに一致することを確認し、両月なしでも `_classify_both_absent`(月払い×アクティブ×2ヶ月以上未発行・年契約/完了/トライアル/対象外除外)の要対応 surface を『先月・今月・12ヶ月以内』の請求問題確認の安全網として維持する。

## 成果物
- 全 6 component (C01〜C06) の実体 (skill/sub-agent/slash-command/hook/script×2) が build_target に生成された状態。
- `envelope-draft/plugin.json` を基にした plugin manifest 更新 (entry_points への新 3 component 追加・version bump)。

## スコープ外
- カバレッジ拡充・テスト網羅 (P06)。
- purpose 受入判定 (P07)。
- builder 自体の改修 (harness-creator 側の責務・gap は `open_issues` へ起票)。

## 完了チェックリスト
- [ ] 依存 top-sort 順 (C04, C06 → C05 → C01 → C02/C03) で全 component が build され、C01 の criteria が Green (受入テスト PASS) になる。
- [ ] build 実体パスが inventory の build_target と一致する。
- [ ] C04 が既存 R1-R3/allowlist を保全したまま `mfk_period_report.py` を SANCTIONED へ追加する Edit 差分として拡張され、C05/C06 が `plugins/mf-kessai-invoice-check/scripts/` へ実体化され単一 skill 配下へ退化していない。
- [ ] C06 が **明示 pin (config `report_database_id`) を step0 で最優先**し、未設定時のみ指定ブロック/見出し周辺の既存 report DB を `in-block` → `under-heading` → `page` の順に確認して更新する。**明示 pin なし かつ 既存 DB 未発見時は phantom を作らず警告停止**し、`page-created`(指定ページ『請求書発行チェック』直下への単一恒久 DB 新規作成)は明示 opt-in 時のみ行う(要件2)。DB は [取引先名, 対象月, 漏れチェック, 商品名, 先月の金額, 今月の金額, 先月と今月の比較, コメント] の 8 列固定で、行キー `(対象月, 取引先名, 商品名)` による非破壊 upsert を行い、旧 7 列 DB には `対象月` 列を PATCH 追加する。`--apply` は `--verified` 必須で未指定 exit2 とする。
- [ ] (2026-07-10 要件1) C05 が `STATE_CONTINUED` を `GAP_OK` で emit し、C06 が `period_diff`『継続発行』を `_STRUCTURAL_NORMAL_MARKERS` に含め、前 run が要対応☐だった継続発行行が今 run で正常✓へ確実に反映されることをテストで確認する。
- [ ] (2026-07-10 要件2) C06 が config `report_database_id` の明示 pin を step 0 で最優先し、未設定時のみ構造的同定へ fallback、明示 pin なし+未発見時は phantom DB を作らず警告停止することをテストで確認する。
- [ ] (2026-07-10 要件3) C05 `_orphan_rows` が要マスタ登録行を `GAP_OK`(正常✓)で emit しコメントに要マスタ登録指示を保持することをテストで確認する。
- [ ] (2026-07-10 要件4) C05 の 4 状態分類がフローチャートに一致し、両月なしの月払い×アクティブ×2ヶ月以上未発行 surface が安全網として維持されることをテストで確認する。

## 参照情報
- `handoff-run-plugin-dev-plan.json` (build routing・`open_issues` の GAP-C04-EXTEND/GAP-SCRIPT-BUILDER) / `component-inventory.json` (依存 DAG)。
- 対象 component C01〜C06。後続 P06 (test-run)。
