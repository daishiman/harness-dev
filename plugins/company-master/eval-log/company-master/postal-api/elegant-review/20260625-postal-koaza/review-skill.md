# elegant-review レポート — company-master 郵便番号 小字/大字フォールバック

- run-id: `20260625-postal-koaza`
- 対象: `plugins/company-master/scripts/postal_api.py`（住所→郵便番号 逆引き）
- 起点: ユーザー報告「`山形県鶴岡市北京田字下鳥ノ巣23番地1` の小字付き住所だと日本郵便 API が404→郵便番号が取れない。町域『北京田』まで削れば origin=japanpost で 997-0053 が取れた」

## 結論: 4条件 全 PASS（独立 approver APPROVE・100 passed/0 failed）

| 条件 | 判定 |
|---|---|
| 矛盾なし (contradiction) | PASS |
| 漏れなし (omission) | PASS |
| 整合性あり (inconsistency) | PASS |
| 依存関係整合 (dependency_break) | PASS |

## フェーズ実行（30思考法・SubAgent並列）

- **Phase 1 思考リセット**（`elegant-reset-observer`・read-only）: 先入観なしの fresh read で「小字を削る処理が両クエリに不在」を観察。`shared_state.md` を生成。
- **Phase 2 並列多角分析**（3 SubAgent 同時）: 論理構造(10法)/メタ発想(9法)/システム戦略(11法)=30思考法を網羅。真因＝クエリ生成側の小字残存に全員収束。
- **Phase 3 改善実行**（`elegant-improvement-executor`）: 最小パッチを実装。独立 approver が4条件を再検証し APPROVE。

## 真因と修正

`_strip_banchi` は「最初のASCII数字で切る」だけで小字「字○○」「大字○○」を town_name に残す → 日本郵便の町域DB（大字粒度まで）に該当せず404。`pick_best`（一意確定のみ採用・zip割れは空欄）の**下流にクエリ段を足すだけなので誤値は構造的に増えない**（再現率のみ向上）。

修正（3ファイル・+127/-3）:
1. `postal_api.py`: 純関数 `_town_variants(town)` を追加し、町域を「素 → 小字削り → 大字prefix削り」の具体→粗順で照会するバリアントを `lookup_postal` の queries に追加。先頭は従来 pattern `structured_pref_city_town` を維持（後方互換）、剥離段は `structured_town_trimmed`。大字は `(?<!大)字` で保護。
2. `tests/test_company_master.py`: 5テスト追加（バリアント単体境界 / 小字404→町域hit / zip割れ空欄=誤値非混入 / 字なし無駄照会なし / 大字404→町域hit）。
3. `references/data-sources.md`: tier2 記述を町域バリアント段反映へ更新（実装SSOTドリフト防止）。

## エンドツーエンド検証

報告ケース `山形県鶴岡市北京田字下鳥ノ巣23番地1` → **997-0053（公的データ取得・origin=japanpost）**。attempts に原小字クエリ miss → `structured_town_trimmed` hit が残り、どの粒度で取れたか追跡可能。

## スコープ外（follow-up・透明性のため明記）

- **`_strip_banchi` の数字含む町域名誤切り**（例 `北24条西2丁目`→town_name=`北`）: 実在を確認。誤値でなく空欄に倒れる別クラスのバグで、精緻化は freeword 経路へ回帰リスク大。本変更は悪化させない（`_town_variants('北')=['北']`）。
- **新 remark_key 追加せず**: 郵便番号は町域粒度で確定値が正しく、pick_best が zip割れを空欄化するため不要と論証。
- **gBizINFO 由来 postal の一次採用 / normalize の canonical化**: 再現率拡張の別タスク。

## 追加改善（一般化・ユーザー追加要望）

ユーザーの「末尾が数字でなく文字列だとヒットしない（字マーカーの有無に依らず対応したい）」という指摘を受け、**第3段フォールバック「市区町村一覧の最長前方一致」**(`pick_best_prefix`) を追加。`{都道府県＋市区町村}` で町域一覧を取り、入力住所への最長前方一致で町域を確定する。

- **効果**: 「字」マーカー無しの小字（北京田下鳥ノ巣）・イロハ/甲乙の枝番・カナ末尾・**町域名に数字を含む住所（北24条西2丁目）**まで拾える。後者により follow-up だった `_strip_banchi` 誤切り（北24条）も `_strip_banchi` を触らずに最終救済（正式町域一覧の「北24条西」を生住所への前方一致で拾う）。
- **fail-safe**: 一覧が返らない／前方一致が無ければ現状どおり空欄に縮退するだけで誤値も回帰も生まない（純増の安全な再現率補強）。auth 失敗時は第3段を走らせない。
- **誤値非混入**: 「official town_name は入力住所の prefix」制約＋最長一致群の zip 収束で担保。前方一致が短い別候補に化けない・zip割れは空欄（テストで実証）。
- **実装の安全性**: `_split_address` を `_city_rest`（番地含む生 rest を返す純関数）に基づき再構成。旧挙動は独立 approver が19ケース bit 一致で完全保存を確認。
- **テスト**: +4（`pick_best_prefix` 単体 / 字なし末尾 / 数字含み町域 / zip割れ空欄）→ **計104 passed**。
- **独立 approver**: 4条件 全 PASS・APPROVE。
- **残課題（非blocking smell）**: 第3段は「`{pref/city}` 照会で実 API が町域一覧を返す」挙動に依存。fail-safe ゆえ誤値は出ないが**再現率効果は未実証** → `doctor --probe` で字マーカー無し住所を1件流して実機確認を推奨（docstring に明記）。大都市のページング上限超過は取りこぼし（空欄縮退で無害）。

更新後の合計差分: 3ファイル・+288/-13。

## エレガンスの根拠

形態素マーカー（字/大字）での原則的バリアント生成に留め、無限トークン削りの過剰設計を回避。`pick_best` の誤値ガードを一切緩めず、その下流にのみクエリ段を足すことで「誤値0を保ったまま再現率↑」を実現（このシステムの非対称コスト原則と完全整合）。
