# elegant-review レポート — company-master 郵便番号 第二波ハードニングの観測性バグ

- run-id: `20260625-postal-koaza-hardening`
- 対象: `plugins/company-master`（郵便番号 postal_code 逆引き経路とその下流: postal_api → enrich → validate → docs）
- 起点: ユーザー報告「`山形県鶴岡市北京田字下鳥ノ巣23番地1` の小字付き住所で日本郵便 API が404→郵便番号が取れない。町域『北京田』まで削れば 997-0053」。本体は committed `_town_variants` で解決済のため、本レビューは**未コミット第二波**（MAX除外/validate厳格化/docs同期）の独立検証。

## 結論: 4条件 全 PASS（独立 approver APPROVE・107 passed/0 failed）

| 条件 | 判定 |
|---|---|
| 矛盾なし (contradiction) | PASS |
| 漏れなし (omission) | PASS |
| 整合性あり (inconsistency) | PASS |
| 依存関係整合 (dependency_break) | PASS |

## フェーズ実行（30思考法・SubAgent並列）

- **Phase 1 思考リセット**（`elegant-reset-observer`・read-only）: 先入観なし fresh read で「pattern名 `structured_town_trimmed` 衝突で sub-attempts が縮約されうる」懸念を観察。`shared_state.md` 生成。
- **Phase 2 並列多角分析**（3 SubAgent 同時・互いに非参照）: 論理構造(10法)/メタ発想(9法)/システム戦略(11法)=30思考法を網羅。**3者独立に同一の観測性バグを確証**。修正案は pattern一意化/dedup免除/identity拡張/スナップショットの4系統に発散。
- **Phase 3 改善実行**（`elegant-improvement-executor`）: オーケストレータが論点を整理し最もエレガントな **C4 冪等スナップショット置換** を決定・実装。
- **独立承認**（proposer≠approver の別 context SubAgent）: 実 `postal_api.lookup_postal` を駆動して修正前 HIT=0→修正後 HIT=1 を実測し APPROVE。

## 真因（観測性バグ・値は正しい）

`_town_variants` の i≥1 バリアントは `lookup_postal`(postal_api.py:400-404) で**全て同名 pattern `structured_town_trimmed`** にラベルされる。一方 enrich の `note_attempt` は `(field, source, pattern)` で dedup する。よって `大字北京田字下鳥ノ巣`（4バリアント）で lookup は value=997-0053 を**正しく**返すのに、enrich の監査ログ(attempts)では後段の **hit が先行 miss に潰され postal_code が miss と誤記録**される。これは未コミット第二波が新たに掲げた「japanpost sub-attempts 全件保持」という不変条件そのものに反する。値は正しいため誤値混入はなく、純粋な**観測性バグ**（hit を miss と誤表示→人間が「取れなかった」と誤解し不要な手作業を誘発）。

### 実行による確証（修正前）
```
lookup_postal("山形県鶴岡市大字北京田字下鳥ノ巣1") → value=997-0053
 内部attempts = [pref_city_town:miss, town_trimmed:miss, town_trimmed:miss, town_trimmed:hit]
 note_attempt 転記後 = [pref_city_town:miss, town_trimmed:miss]   ← hit 消失=miss 誤記録
```

## 採用修正 C4（冪等スナップショット置換）と棄却した他案

japanpost の postal sub-attempts は「1回の決定論 `lookup_postal` 呼び出しが生む完結した順序付きスナップショット」。よって enrich では gap-driven dedup を介さず**冪等にスナップショット置換**（既存 `field==postal_code & source==japanpost` 行を除去→postal_api の attempts を verbatim 全件 append）するのが正しい意味論。

| 案 | 棄却理由 |
|---|---|
| C1 pattern連番化 | pattern 語彙 churn・既存テスト2本破壊・設計意図（後方互換で pattern 名据置）に反する |
| C2 note_attempt dedup免除 | cross-pass で japanpost miss が二重記録（2パス目 postal 再照会で累積） |
| C3 identity に town 追加 | note_attempt 汎用契約を全 field 侵食・3箇所 churn |
| **C4 冪等スナップショット**（採用） | within-pass hit保持・cross-pass重複なし・pattern据置・note_attempt汎用維持・「全件保持」が literally 真。副産物: note_attempt の MAX除外を revert でき japanpost 特例を transcription 1箇所へ集約 |

## 変更（観測性修正スコープ・4ファイル）

1. `scripts/enrich_company.py`: postal transcription を冪等スナップショット置換へ。`note_attempt` の japanpost MAX除外ガードと docstring を**汎用形へ revert**（dead code/smell 化を防止）。docstring を冪等転記の記述へ更新。
2. `references/data-sources.md` / `skills/run-company-master-build/SKILL.md`: tier2/郵便番号節の「MAX 上限対象外で全件保持」を「**1回の決定論呼び出しの完結スナップショットを冪等に全件転記**（gap-driven dedup/上限は Web/agent 専用）」へ同期。
3. `tests/test_company_master.py`: 実バグ経路を踏む回帰テスト2件追加（`test_enrich_keeps_town_trimmed_hit_after_leading_misses` = 同一 pattern miss→hit で hit 保持・RED→GREEN／`test_enrich_japanpost_snapshot_not_duplicated_cross_pass` = 2パス非重複）。既存 `test_enrich_preserves_all_japanpost_sub_attempts` は verbatim extend で green 維持。

`postal_api.py` は**完全無変更**（pick_best/_format_postal/pattern名 intact = 誤値非混入は緩んでいない）。

## エンドツーエンド検証

- 報告ケース `山形県鶴岡市北京田字下鳥ノ巣23番地1` → 997-0053、enrich.attempts に hit 残存。
- 核心 `大字北京田字下鳥ノ巣1` → 4 sub-attempts を verbatim 転記・hit 残存（修正前は hit=0）。
- 全 107 passed（独立 approver も自走実測で 107/0）。

## 残課題（deferred・transparency）

- **RELEASE-01**: ユーザーはインストール済み 0.1.0（修正前）を踏んだ＝worktree との乖離が現場失敗の真因。コード修正後 version bump + PR で配布しないと価値が届かない。SKILL.md 変更につき content-review verdict を独立 SubAgent で現 SHA genuine 再生成すること。
- **DEFER-01**: gBizINFO レスポンスに郵便番号があれば tier0 直取りで逆引き（脆い形態素処理）の発火頻度を下げられる（確度上限/URL規約再設計を伴う別タスク）。
- **DEFER-02**: 見落とし住所クラス（複数字/京都通り名/漢数字丁目/無番地）。誤値でなく空欄縮退クラス。negative-case ハーネスで「悪化させない」を先に保証する方針。
- **DEFER-03**: 誤値非混入が zip 収束依存で town identity 非依存。pick_best に「採用 town が元 town の包含関係」ゲートを足せば構造二重化（実害確証なし smell）。
- **smell**: `JAPANPOST_VERIFY_URL` が postal_api.py:72 と validate_company_master.py に**リテラル二重定義**（値一致で矛盾なし・将来ドリフト防止に単一 SSOT import 推奨）。

## エレガンスの根拠

japanpost の postal sub-attempts の本質（決定論の完結スナップショット）に意味論を合わせ、汎用 `note_attempt`（web/agent の gap-driven 台帳）から japanpost 特例を引き剥がして 1 箇所へ集約。誤値非混入の核（postal_api / pick_best）は一切触らず、監査ログの忠実性のみ回復。非対称コスト原則（誤値0）を不変に保ったまま観測性を回復する最小・局所の修正。
