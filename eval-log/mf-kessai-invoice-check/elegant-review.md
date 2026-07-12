# MF Kessai Invoice Check Elegant Review

Date: 2026-06-19
Scope: `plugins/mf-kessai-invoice-check/`

## Thought Reset

既存対策の正しさを前提にせず、plugin package を marketplace から任意ディレクトリに install するユーザー視点で再検証した。成果物削除ではなく、仕様・実装・配布契約・実行導線を新規観察した。

## Findings And Fixes

| ID | Finding | Risk | Fix |
|---|---|---|---|
| F1 | `plugin.json` が 36章 `bundle` 契約の `package_mode` / `entry_points` を明示していなかった | marketplace install 時の構成理解と機械検査が弱い | `package_mode: bundle`、skills/agents/hooks/commands/permissions を追加 |
| F2 | `references/package-contract.json` が無かった | PKG-001〜015 の状態を機械可読に追えない | package contract を追加し、pass/skip/not_applicable を明示 |
| F3 | README と responsibility prompt に repo 相対・skill CWD 前提のコマンドが残っていた | 任意 install path でユーザーが迷う | `$CLAUDE_PLUGIN_ROOT` 基準へ統一 |
| F4 | workflow manifest の command が `python3 scripts/...` 前提だった | orchestrator が skill directory 以外から実行すると失敗しうる | manifest command を `$CLAUDE_PLUGIN_ROOT/skills/...` へ変更 |
| F5 | install smoke 契約上の実行可能ビットがテストで固定されていなかった | ユーザーに手動 chmod を要求する退行が起きる | script/hook の executable bit を設定しテスト追加 |
| F6 | 可搬性・manifest 契約の回帰テストが不足していた | 仕様適合が人手レビュー頼みになる | `tests/test_plugin_contract.py` を追加 |

## 30 Thinking Methods Coverage

| # | Thinking method | Applied conclusion |
|---:|---|---|
| 1 | 批判的思考 | 「動く」ではなく install 契約と任意 path で疑った |
| 2 | 演繹思考 | 36章 bundle 必須キーから `plugin.json` 不足を導出 |
| 3 | 帰納的思考 | README/prompts の複数裸相対パスから可搬性リスクを一般化 |
| 4 | アブダクション | install 失敗の最善説明を path/cwd 前提の残存と推定 |
| 5 | 垂直思考 | 表層 README ではなく manifest/prompt/test まで掘った |
| 6 | 要素分解 | skill/agent/hook/lib/config/test/manifest に分解 |
| 7 | MECE | 配布契約・実行導線・安全性・検査自動化に分類 |
| 8 | 2軸思考 | 人間向け導線と機械向け契約の2軸で評価 |
| 9 | プロセス思考 | collect→verify→finalize→sink の順序と fail-closed を確認 |
| 10 | メタ思考 | SKILL 散文ではなく contract/test に固定する方針を採用 |
| 11 | 抽象化思考 | 「path 非依存」を `$CLAUDE_PLUGIN_ROOT` ルールへ抽象化 |
| 12 | ダブル・ループ思考 | repo 直下実行を前提にする運用前提自体を疑った |
| 13 | ブレインストーミング | manifest、README、prompt、workflow、test の改善案を列挙 |
| 14 | 水平思考 | 他 plugin の manifest 形式も比較対象にした |
| 15 | 逆説思考 | 「install 後に CWD が違うなら何が壊れるか」で検査 |
| 16 | 類推思考 | contract-generator/prompt-creator の manifest metadata を参考化 |
| 17 | if思考 | `$CLAUDE_PLUGIN_ROOT` 未使用、別 CWD、未 chmod の場合を想定 |
| 18 | 素人思考 | README の手順だけ見た導入者が迷う箇所を確認 |
| 19 | システム思考 | Plugin manifest、hook、subagent、Notion sink の連動を確認 |
| 20 | 因果関係分析 | 裸相対 path → 実行失敗 → verify/sink 未完了の因果を特定 |
| 21 | 因果ループ | 検査不足→退行→手動修正のループをテストで遮断 |
| 22 | トレードオン思考 | 大改造せず、契約明示と可搬性修正で安全性も上げた |
| 23 | プラスサム思考 | ユーザー導線と validator の両方を改善 |
| 24 | 価値提案思考 | 月次発行漏れ検知という価値を install 直後に使える状態へ寄せた |
| 25 | 戦略的思考 | 36章 PKG 契約に合わせ、将来 smoke/CI 接続しやすくした |
| 26 | why思考 | なぜ path 問題が起きるかを CWD/install 位置前提まで遡った |
| 27 | 改善思考 | 仕様不足を manifest/test/report に反映 |
| 28 | 仮説思考 | 「裸相対 path が主要リスク」という仮説を rg とテストで検証 |
| 29 | 論点思考 | 真の論点を API ロジックでなく marketplace install 可搬性に設定 |
| 30 | KJ法 | findings を F1〜F6 にグルーピング |

## Four Conditions

| Condition | Result | Evidence |
|---|---|---|
| 矛盾なし | PASS | `plugin.json` / workflow / prompt command を `$CLAUDE_PLUGIN_ROOT` に統一 |
| 漏れなし | PASS | skills 3、agent 1、hook 1、commands、permissions、package contract を manifest 化 |
| 整合性あり | PASS | JSON parse、pytest、plugin completeness が PASS |
| 依存関係整合 | PASS | `validate-plugin-completeness.py` で hook/asset/bundle 整合 OK |

## Verification

- `pytest -q plugins/mf-kessai-invoice-check/tests` -> 26 passed
- `python3 scripts/validate-plugin-completeness.py` -> OK: 12 plugin(s) complete
- `python3 -m json.tool` for plugin manifest, package contract, workflow manifest -> OK

---

## Addendum: Transaction-Date Month And End-Month Safety

Date: 2026-06-30
Scope: `plugins/mf-kessai-invoice-check/`

### Thought Reset

「6月分の請求書」を発行日ではなく取引日で捉える、という定義を正本として再確認した。あわせて、自由文や同一取引先伝播から `契約終了月` が根拠なく入ると請求漏れを隠すため、終了月の自動推定を疑って見直した。

### Findings And Fixes

| ID | Finding | Risk | Fix |
|---|---|---|---|
| A1 | `run-mf-invoice-check` が `issue_date` 当月で取得していた | 取引日 6/30・発行日 7月の6月分を取りこぼす | 対象月初〜翌月末を over-fetch し `/transactions.date` で対象月へ絞る |
| A2 | `run-mf-invoice-reconcile` の R1 prompt / schema / README が発行日基準に読めた | 実装済みの取引日基準を LLM 実行で戻す | `transaction.date` 基準、`issue_date` は取得窓と明記 |
| A3 | 自由文 `（2605終了）` を契約終了月として推定していた | 契約終了情報がない行を終了扱いし請求漏れを隠す | `契約終了月` は明示列のみ採用 |
| A4 | writeback/backfill が空欄の `契約終了月` を補完・伝播し得た | 同一取引先の継続契約へ終了月が漏れる | 機械は `契約終了月` を書かない。契約開始日の空欄補完のみ維持 |

### 30 Thinking Methods Coverage

| # | Thinking method | Applied conclusion |
|---:|---|---|
| 1 | 批判的思考 | 「当月発行」表現を疑い、6月分の定義を取引日に固定 |
| 2 | 演繹思考 | 6月分=取引日6/30なら `issue_date` 6月末絞りは不成立 |
| 3 | 帰納的思考 | 複数文書の発行日表現から再発リスクを一般化 |
| 4 | アブダクション | 2605終了混入の最善説明を自由文推定・伝播経路と推定 |
| 5 | 垂直思考 | README から collect、writeback、DB1 生成まで掘った |
| 6 | 要素分解 | 月帰属、終了月推定、書き戻し、伝播を分解 |
| 7 | MECE | 取得、判定、保存、シート反映の責務を分離 |
| 8 | 2軸思考 | 正確性と非破壊性の2軸で終了月自動化を評価 |
| 9 | プロセス思考 | over-fetch → transaction filter → diff の順に固定 |
| 10 | メタ思考 | LLM prompt が旧定義を再導入しないよう文書も修正 |
| 11 | 抽象化思考 | `issue_date` を取得窓、`transaction.date` を帰属軸に抽象化 |
| 12 | ダブル・ループ思考 | 終了月を機械補完すべきという前提を撤回 |
| 13 | ブレインストーミング | filter修正、文書修正、補完停止、テスト追加を列挙 |
| 14 | 水平思考 | 旧 check と reconcile の両コマンドを横断比較 |
| 15 | 逆説思考 | 「終了月を入れるほど安全」という逆を検証し危険と判断 |
| 16 | 類推思考 | 開始日は補完可、終了日は空欄が意味を持つという違いを整理 |
| 17 | if思考 | 発行日7/1、取引日7/1、取引日欠落の境界を想定 |
| 18 | 素人思考 | 「6月分」という業務語を発行月ではなく役務月として読んだ |
| 19 | システム思考 | MF API、Notionシート、DB1/DB2、writeback の波及を確認 |
| 20 | 因果関係分析 | 自由文終了推定 → 終了扱い → 対象外 → 請求漏れの因果を特定 |
| 21 | 因果ループ | 誤補完が翌月以降の判定入力になり続けるループを遮断 |
| 22 | トレードオン思考 | 終了月自動補完の便利さを捨て、請求漏れ防止を優先 |
| 23 | プラスサム思考 | 開始日補完は残し、終了月だけ止めて運用負荷と安全を両立 |
| 24 | 価値提案思考 | 経理が見る「6月分」の正確性を主価値に戻した |
| 25 | 戦略的思考 | 将来のコマンド差異をなくすため旧 check も取引日基準化 |
| 26 | why思考 | なぜ 2605 が入るかを自由文 parse と writeback まで遡った |
| 27 | 改善思考 | 最小修正でフィルタ・文書・補完停止・回帰テストを追加 |
| 28 | 仮説思考 | `（YYMM終了）` parse が原因という仮説を rg とコードで検証 |
| 29 | 論点思考 | 真の論点を発行日表示ではなく取引月帰属と終了月根拠に設定 |
| 30 | KJ法 | findings を A1〜A4 にグルーピング |

### Four Conditions

| Condition | Result | Evidence |
|---|---|---|
| 矛盾なし | PASS | README / SKILL / R1 prompt / schema を `transaction.date` 基準へ統一 |
| 漏れなし | PASS | 旧 check と reconcile の両方、終了月推定・writeback・backfill を対象化 |
| 整合性あり | PASS | `契約終了月` は明示列のみ、機械書込なしに統一 |
| 依存関係整合 | PASS | collect 出力は既存 `detect_gaps` に synthetic billing として接続し、DB/writeback 契約を維持 |

### Verification

- `pytest -q --no-cov plugins/mf-kessai-invoice-check/tests` -> 506 passed, 2 skipped

---

# Addendum: 再発明事故 + 商品照合精度 の3本柱レビュー (2026-06-30)

Scope: `plugins/mf-kessai-invoice-check/` の未コミット修正セット（自然文起動の回復 / 再発明の機械遮断 / 商品照合精度の回復）。

## 思考リセット・俯瞰 (Phase 1) と並列多角分析 (Phase 2)

事故: ユーザーが自然文で照合を頼んだら、AI が正規エンジンを使わず自前 `reconcile_judgments.py` を書き、判定 `classify()` を `TODO(human)` で人間に丸投げした。
根本原因: (A) `run-mf-invoice-reconcile/SKILL.md` が `disable-model-invocation: true` で自然文起動を殺していた（plugin 全 run 系のブランケット既定 true を最新 skill が継承） / (B) 自作を止める機械層が無かった（prose の「自作禁止」は出力スタイルの TODO(human) 規約に上書きされる）。

3本柱: 柱1=SKILL.md `disable-model-invocation` true→false（安全は dry-run 既定 + `--apply` の `--verified` 必須ゲートで担保）/ 柱2=`hooks/guard-mfk-no-reinvent.py`（PreToolUse exit 2 で R1 TODO(human)・R2 再実装・R3 Bash 迂回を遮断）/ 柱3=`sheet_to_master`+`mfk_reconcile._expected_categories` が集約元商品集合を保持し代表商品への退化を防止。

論理構造・メタ発想・システム戦略の3エージェントが独立 context で 30 思考法を適用し、findings を収束。

## 最重要結論: 柱3 は偽の発行漏れ（赤）を生まない (YES/NO = NO)

演繹: `_expected_categories` への集約元商品集合の追加は期待カテゴリ集合を**単調拡大するだけ**。`find_mf_match` の `scoped_candidates`（mfk_reconcile.py:711-715）は上位集合化し、MATCH を no_supply→GAP へ反転させる経路は存在しない。fail-soft（期待集合が空なら会社+金額照合へ）も成立。golden GAP=17 不変（test_mfk_reconcile.py）が経験的に裏づけ。3エージェントが同結論へ独立収束。

## Phase 3 改善（実装済み・本 PR）

| ID | Finding | 条件 | 対応 |
|---|---|---|---|
| A1 | 柱1 が将来 `true` へ回帰すると事故Aが無検知で再発（回帰防止テスト不在） | C1 矛盾 | `test_reconcile_is_model_invocable_from_natural_language` を追加し `disable-model-invocation: false` を事故リンク付きで機械固定 |
| A2 | `商品一覧`/`_source_products` が同一リストの二重保持（無印キーは DB1 非永続で命名規約に逸脱） | C3 整合性 | 規約準拠の `_source_products` 一本へ SSOT 統一。`商品一覧` 廃止。非永続の不変条件を sheet_to_master / _expected_categories に明記し依存断線#5 の文書ギャップも閉じた |
| A3 | guard の射程限界（信号語依存=偽陰性・構造的 backstop 不在）が未明記。allowlist が R2 のみ掛かる非対称が docstring と不一致 | C3 整合性 | guard docstring に readonly 同等の射程限界を正直明記。「正本でも R1 TODO(human) は遮断」をテスト固定 |
| A4 | README L83 が「ふだんの言葉で頼むだけで全部動く」と全体約束するが check/db-setup/enrich は `true`（自然文非起動） | C1 矛盾 | README を「reconcile 主フローのみ自然文自動起動・他は明示スラッシュ」へ正確化 |

## Deferred（実データ検証が必要・本 PR では実装しない）

| ID | Finding | 理由 |
|---|---|---|
| D1 | カテゴリのハードフィルタ起因の残存偽GAP（柱3 とは独立の既存機構）: 会社供給はあるが全明細が期待外カテゴリ（例 `other`）に落ちると金額一致でも `no_supply→GAP`（mfk_reconcile.py:781-783）。`category()` 値域に `other` 等があるが `_expected_categories` 値域は非網羅 | カテゴリフィルタを soft-prefer へ変更する案は core 照合の挙動変更で、本番 2606 データでの GAP=17 の内訳検証が必須。trial/thinktank は点パッチ済。盲目的変更は回避 |
| D2 | parity lint（README 一言テーブル掲載 skill ⟹ `disable-model-invocation:false`）の CI 配線 | systemic 再発の単一レバレッジだが、現状は A1 の reconcile 回帰テストで主因を固定済。governance 拡張は別 PR |
| D3 | 商品照合語彙のハードコード（5語彙）→ シート商品名トークン直接含有への一般化、および一致強度（商品+金額 vs 金額のみ）の WARN 可視化 | 機能拡張。未知商品の出現時に金額のみ照合へ縮退する点の改善だが、現要件は充足。enhancement として保留 |

## Four Conditions

| Condition | Result | Evidence |
|---|---|---|
| 矛盾なし | PASS | A1（frontmatter 回帰固定）+ A4（README 正確化）で「自然文起動の約束 vs 設定」の矛盾を解消 |
| 漏れなし | PASS | 事故の根本原因 A（柱1）/ B（柱2）+ 業務価値（柱3）を網羅。残存リスク D1-D3 は明示起票し silent な取りこぼしを排除 |
| 整合性あり | PASS | A2（SSOT 一本化）+ A3（guard 射程の正直化・allowlist 非対称の明記）で命名規約・文書・実装を整合 |
| 依存関係整合 | PASS | `_source_products` 非永続の不変条件を明記し、将来の DB1 由来 reconcile 経路に対する潜在断線#5 を文書化 |

## Verification

- `python3 -m pytest -q`（cwd=`plugins/mf-kessai-invoice-check/`）→ 593 passed, 2 skipped / TOTAL coverage 95.50%
- 二段確認: 柱3 安全性の「NO」結論は報告を鵜呑みにせず `mfk_reconcile.py:711-790` のコード経路を辿って演繹的に確認
