# mf-kessai-invoice-check テスト戦略 (SSOT)

> このファイルが**唯一の真実 (Single Source of Truth)**。今どこまで出来ていて・次に何を
> すれば良いかは、ここだけ見れば分かる状態を保つ。作業のたびに**随時更新**する。
> サブエージェントもこのファイルを起点に文脈を得る。
>
> **鉄則**: 進捗は自己申告でなく**機械事実**で記す。PASS の根拠は「pytest の exit code = 0」
> 「`ls`/`git status` の実出力」のみ。テスト件数や「やった」は、実コマンド出力を
> `/tmp/*.txt` に書き Read して確認した結果だけを書く (Bash 末尾 stdout は壊れることがある)。

最終更新: 2026-06-24

---

## 0. このプラグインが保証したいこと (なぜテストするか)

MoneyForward 掛け払いの**請求書発行漏れ**を毎月検知し、結果を Notion DB に**顧客ID単位で
冪等に**蓄積する。壊れると「発行漏れの見逃し」または「Notion 履歴の重複/破壊」に直結する。
よって守るべき不変条件は次の 3 つ:

- **I1 (検知正当性)**: 前月発行・今月未発行 → 発行漏れ候補。金額変動 → 検知。誤検知しない。
  金額変動の検知は、Notion 月次履歴 table の `前月金額` / `今月金額` 列 (schema の `fact_columns`、
  `notion_invoice_sink.TABLE_COLUMNS`) として**成果物に観測可能**である。すなわち「金額が変わった」
  という不変条件は、抽象的なログでなく Notion 上の 2 列の差分として人間が直接検証できる
  (table 行の `前月金額` ≠ `今月金額` が金額変動の根拠)。
- **I2 (冪等性)**: 同じ月を二度 sink しても Notion に行が重複しない。月が変わっても新規ページを
  作らず、顧客IDで既存ページを更新する。
- **I3 (移植性)**: 任意の install 先・本番環境で、手動セットアップ無しに動く (標準ライブラリのみ
  をランタイム依存とする)。

テストはこの I1/I2/I3 が**将来の変更で無言で壊れない**ことを保証するために存在する。

---

## 1. 現在のステータス (一目で分かる進捗表)

| Phase | 内容 | 状態 | 根拠 (機械事実) |
|---|---|---|---|
| P0 | 環境監査・dev 依存の導入 | ✅ 完了 | `requirements-dev.txt` 作成、6 パッケージ import OK (`/tmp/mfk_pipinstall.txt`) |
| P1 | 標準ローカルテスト基盤 | ✅ 完了 | `pytest.ini` (importlib+pythonpath)、sys.path 撤去、**41 passed / exit 0** をランダム順・並列・カバレッジで実証 (`/tmp/mfk_verify.txt`) |
| P2 | CI 配線 (再発防止の根本修正) | ✅ 完了 | `harness-creator-kit-ci.yml` に per-plugin pytest ステップ追加。ローカルでループ実証 (`/tmp/mfk_ci_sim.txt`、found=1/exit 0/YAML_OK) |
| P3 | この SSOT ドキュメント | ✅ 完了 (随時更新) | 本ファイル |
| P4 | L3 real_test (実 Notion 往復) | ✅ 完了 | `tests/test_real_notion.py` 作成。secrets 無しで **2 skipped / exit 0**、既存 41 は緑を実証 (`/tmp/mfk_l3.txt`)。`MFK_TEST_DATABASE_ID` を持つ運用者環境でのみ実 API 往復 |
| P5 | 自己検証ループ (別 SubAgent レビュー) | ✅ 完了 (ADEQUATE) | §6。round1 R2=FAIL→3死角是正→**round2 で別contextが M3/M4 再ミューテーションし検出を確認、overall=ADEQUATE**。45 passed |
| P6 | deprecated 列の移行 | ✅ 完了 | schema に `deprecated_properties` 宣言。build が whitelist 削除 (現行列は不削除の安全制約)、verify が residual を FAIL 化。`tests/test_db_migration.py` 7本。ミューテーションで検出力実証 (`/tmp/mfk_p6_mutation.txt`) |
| P7 | カバレッジ ≥80% 機械ゲート | ✅ 完了 | `pytest.ini` に `--cov-fail-under=80`。network 層 (api/keychain) も mock unit でカバーし **TOTAL 90% / 全モジュール≥80% / 114 passed・2 skipped / exit 0**。CI は plugin dir で pytest.ini を拾い自動強制 (他 plugin の pytest には波及しない)。新規 test: `test_mfk_api.py` / `test_mfk_keychain.py` / `test_build_notion_db.py` + `check_invoice_gaps` の main() dispatch |
| P8 | 参照専用 guard のテスト+カバレッジ算入 | ✅ 完了 | guard (`hooks/guard-mfk-readonly.py`) を従来カバレッジ対象外・無テストだった不整合を解消。`pytest.ini` の `--cov` に `--cov=hooks` を追加し guard を 80% ゲートの母数へ算入。`tests/test_guard_mfk_readonly.py` を新規作成 (30 本)。importlib で guard を module ロードし `main()` を in-process 実行 + 本番経路の subprocess 起動の両経路で境界を固定。**guard 単体 100% / TOTAL 92.93% / 183 passed・2 skipped / exit 0**。精度改善: 別ホスト宛て変更系の同一行共起による誤遮断を解消しつつ、ホスト不明断片は fail-closed で遮断 (遮断を弱めない)。WebFetch 等 非Bash tool の `method:"POST"` 取りこぼしも遮断強化 |
| P9 | enrich skill のテスト整備 + cov 算入 | ✅ 完了 | enrich skill (`skills/run-mf-initial-month-enrich/scripts`) が従来カバレッジ対象外・無テストだった非対称を解消。`pytest.ini` の `--cov` / `pythonpath` に enrich scripts を追加し 80% ゲートの母数へ算入。新規 unit test 5本 (`tests/test_mf_invoice_{names,api,oauth,csv_match,enrich}.py`) を network/Keychain 不要の monkeypatch で固定 (既存 `test_mfk_keychain.py`/`test_mfk_api.py` と同流儀)。security 回帰: `_kc_save` が secret を argv に載せず stdin 渡しすることを機械担保。`test_plugin_contract.py` の実行ビット smoke に enrich 実行エントリ4本を追加し RUNTIME_DIRS との片肺を解消。schema↔validate_rows の parity test (LS-05) も追加。**全 enrich モジュール≥80% (names 100% / oauth 99% / enrich 95% / api 93% / csv_match 90%) / TOTAL 94.23% / 260 passed・2 skipped / exit 0** (ランダム順でも緑) |

**次にやること (next action)**: 全フェーズ (P0–P9) 完了。enrich skill のテスト整備 + カバレッジ母数算入まで含めて完了。**260 passed / 2 skipped / exit 0 / TOTAL coverage 94.23%** (enrich を母数算入後・ランダム順でも緑。`cd plugins/mf-kessai-invoice-check && python3 -m pytest`)。
[PR #37](https://github.com/OWNER/harness/pull/37) 作成済 (`feat/mf-kessai-testing-hardening`→main)。
pre-push で CI 等価 `run-ci-checks.sh` が PASS を通過。残: GitHub Actions の CI 緑確認 → マージ。

---

## 2. テストの 3 層構造 (何を・どの層で守るか)

| 層 | 名前 | 対象 | ネットワーク | 速度 | 実体 |
|---|---|---|---|---|---|
| L1 | Unit | 純関数・ファイル操作 (diff 判定 / 出力先解決 / table 行構築) | 不要 | 即時 | `tests/test_invoice_diff.py`, `test_check_invoice_gaps.py`, `test_notion_invoice_sink.py` (fake store) |
| L2 | Contract | plugin manifest / schema / package 契約 | 不要 | 即時 | `tests/test_plugin_contract.py` |
| L3 | Real | 実 Notion DB への verify→upsert→read-back→再実行冪等 | 必要 | 数秒 | `tests/test_real_notion.py` (secrets 無しで skip)。§5 |

- L1/L2 は**毎 push で必ず緑**であるべき (API 不要なので CI で常時実行)。
- L3 は secrets があるときだけ走る (無ければ `pytest.mark.skip`)。本番同等の往復で I2 冪等性を
  実証する。mock では捕まえられない「実 API のレスポンス形・ページネーション・型」を守る。

カバレッジ方針 (**2026-06-24 更新**): **全モジュール行カバレッジ ≥80% を機械ゲート化**
(`pytest.ini` の `--cov-fail-under=80`)。当初はネットワーク層 (api/keychain) を L3 担保とし
「L1 では原理的に届かない」としていたが、`urllib`/`subprocess` を mock した unit test で
**契約** (doseq エンコード / カーソルページネーションの after 追従 / KeychainError の exit_code
44・9 / mask が生値を出さない 等) を固定し、検出力を保ったまま L1 で到達させた。

**hooks 算入 (2026-06-24)**: 従来 `--cov` の母数は `lib` + 2 scripts ディレクトリのみで、
参照専用 guard (`hooks/guard-mfk-readonly.py`) は**カバレッジ対象外かつ無テスト**だった
(90% 主張の母数に guard が入っていない不整合)。`pytest.ini` に `--cov=hooks` を追加し guard を
80% ゲートの母数へ算入。あわせて `tests/test_guard_mfk_readonly.py` (30 本) を新規作成し、
guard を **100% カバー**。これにより「参照専用を仕組みで担保する第1層」自体が回帰テストで
守られ、無言で緩む変更を CI が赤くする。

実測 (CI 等価 `cd plugins/mf-kessai-invoice-check && python3 -m pytest`、hooks 算入後):
`mfk_invoice_diff` 100% / `guard-mfk-readonly` 100% / `build_notion_db` 99% / `mfk_keychain` 98% /
`mfk_api` 96% / `verify_db_schema` 94% / `check_invoice_gaps` 90% / `notion_invoice_sink` 85% /
**TOTAL 92.93%** (P8 時点)。

**enrich 算入 (P9, 2026-06-24)**: enrich skill の5モジュールを母数に追加し unit test で担保:
`mf_invoice_names` 100% / `mf_invoice_api` 93% / `mf_invoice_oauth` 99% /
`mf_invoice_csv_match` 90% / `mf_invoice_enrich` 95% (全て≥80%)。
**enrich 算入後 TOTAL 94.23% / 260 passed・2 skipped / exit 0** (ランダム順でも緑)。

トレードオフ (記録): mock は実 API のレスポンス形・ページネーション・型までは保証しない
(それは L3 real_test の責務)。**mock unit (契約固定) と L3 real (実 API 往復) を二層で持つ**
ことで「速い回帰検出力」と「実 API 契約遵守」を両取りする。行カバレッジ数値の最大化を
目的化せず (Goodhart 回避)、各 mock テストは必ず意味のある assertion を伴う。

**enrich を母数へ算入 (P9, Goodhart 回避の徹底)**: enrich skill (`run-mf-initial-month-enrich`)
の5モジュールは従来 `--cov` の母数外で、テストもゼロだった。これは「対象を母数から外せば
TOTAL% が見かけ上高く出る」典型の Goodhart リスクであり、enrich を `--cov` に追加して
母数を正直化した。追加した enrich の各 unit test も数値稼ぎでなく、`norm` の名寄せ収束・
`_get` の 401/429 リトライ・`_kc_save` の secret 非露出 (argv 不混入)・CSV 名寄せの
VERIFIED fail-closed といった**契約を必ず意味ある assertion で固定**している。

---

## 3. どう自動化したか (一個ずつ目視しない仕組み)

- **ローカル**: `cd plugins/mf-kessai-invoice-check && python3 -m pytest tests/ -q`。exit code が
  唯一の合否。pytest-randomly が毎回**実行順をランダム化**し順序依存バグを自動検出。
  `-n auto` (xdist) で並列。`--cov-fail-under=80` (pytest.ini) が 80% 未満で exit 1 にする
  **機械ゲート** (単なる可視化でなく合否条件)。
- **CI** (`.github/workflows/harness-creator-kit-ci.yml`): `plugins/*/tests` を**総当り**で pytest 実行。
  新規 plugin が `tests/` を足せば自動で CI 対象になり「配線忘れで無言腐敗」を構造的に封じる。
  dev 依存は `requirements-dev.txt` 一枚を SSOT として install。
- **再発防止の原理**: 「人間が一個ずつ叩いて目視」を、CI の exit code 門番に置換した。壊れた
  変更は PR の時点で赤くなり、マージできない。

---

## 4. 検証規律 (捏造を防ぐルール)

1. 合否は **exit code のみ**。「N passed」の見た目では判断しない。
2. Bash の末尾 stdout は壊れることがある → **結果は `/tmp/*.txt` に書き出し Read** して確認。
3. 「やった」は **`git status` / `ls` の実出力**で裏取りしてから書く。SubAgent の自己申告報告は
   `git diff` / exit code で二段確認する (形式パターン検出と実装意図は区別できない)。
4. 自作スクリプトで検証しない。**業界標準** (pytest, pytest-randomly, coverage) を使う。

---

## 5. L3 real_test (実装済み: `tests/test_real_notion.py`)

目的: mock では守れない「実 Notion API との契約」と「I2 冪等性の往復実証」を守る。

実装した手順 (サンドボックス DB に対して):
1. schema verify: サンドボックス DB に集約モデルの必須事実列が揃うことを実 API で確認。
2. 合成テスト行 (顧客ID=`__mfk_l3_test__<uuid>`, 対象年月=`2099-01`) を `upsert` → Notion を
   read-back し、顧客IDページ・本文 table の当月行・今月金額セルが期待通りか検証。
3. **同じ顧客・同じ月を金額だけ変えて再 upsert** → `created==0/updated==1` (新規ページを作らない)、
   ページが一意のまま、当月行が重複せず既存行が更新される (I2 冪等性) ことを実 API で確認。
4. 後始末: 作成した顧客ページを `archived=True` で必ずアーカイブ (finally)。

安全弁: 専用サンドボックス DB を環境変数 `MFK_TEST_DATABASE_ID` で受け取る。未設定なら
`pytest.skip` (本番 DB は決して使わない)。`NOTION_API_KEY`/Keychain が引けなくても skip。
→ secrets を持つ運用者環境でのみ実行され、CI / 一般環境では無言で skip する
(実証: `41 passed, 2 skipped, exit 0` / `/tmp/mfk_l3.txt`)。

---

## 6. 自己検証ループ (別 SubAgent によるレビュー)

proposer ≠ approver の原則 (テストを書いた本人が「十分」と自己承認しない)。独立 context の
レビュア SubAgent に次を判定させる:

- **R1 (機械事実)**: 主張する pytest 結果は実際に再現するか (exit 0 / 件数)。
- **R2 (妥当性)**: テストは I1/I2/I3 を実際に守っているか。アサーションが緩く偽 PASS していないか。
- **R3 (検出力)**: 故意にロジックを壊したらテストが落ちるか (ミューテーション的観点)。

判定が「不足」なら指摘を是正し、再レビュー (最大 3 周)。「十分」なら完了。結果は本 §1 表に反映。

### レビュー履歴

**round 1 — overall: INADEQUATE (R1 PASS / R3 PASS / R2 FAIL)**

独立レビュアが 4 ミューテーションを /tmp 複製で実施し、I2 冪等性の**死角を実証**した:

| ミューテーション | 結果 (round1) | 意味 |
|---|---|---|
| `detect_gaps` の差集合反転 | 4 failed (検出) | I1 検知に検出力あり |
| `_find_page` 戻り値を None 固定 | 2 failed (検出) | I2 顧客ID冪等に検出力あり |
| `_all_block_children` を先頭1ページのみに退化 | **0 failed (未検出)** | ページネーション境界が未カバー |
| `_find_page` の `len>1`→`len>99` | **0 failed (未検出)** | 顧客ID重複検出が未カバー |

→ 是正 (3 gap + I3 強化):
- `test_find_page_raises_on_duplicate_customer_id` (顧客ID重複 → RuntimeError)
- `test_upsert_paginates_beyond_100_rows_no_duplicate` (132ヶ月履歴の2ページ目を再sink→重複追記しない。fake store を 100件/ページ分割に拡張)
- `test_upsert_same_month_updates_correct_row_in_multirow_table` (多行tableで正しい月行だけ更新)
- `test_runtime_imports_are_stdlib_or_in_plugin_only` (I3 移植性の AST ガード)

→ 是正後の検出力を**自前のミューテーション再試行で実証** (`/tmp/mfk_mutation_proof.txt`):
先頭ページ退化 → `paginates_beyond` が exit1 で**検出**、`len>99` → `duplicate_customer` が exit1 で**検出**、
period_ym 一致破壊 → multirow/pagination が exit1 で**検出**。round1 で素通りした死角が塞がった。
フルスイート **45 passed / 2 skipped / exit 0**。

**round 2 — overall: ADEQUATE (R1 PASS / R2 PASS / R3 PASS)**

同レビュアが独立 context で M3/M4 を /tmp 複製に再注入し、今度は対応テストが**落ちる**(検出される)
ことを確認。追加で M5 (period 一致 `==`→`!=`) → multirow テスト検出、M6 (`import requests` 混入) →
I3 AST ガードが `{'lib/mfk_invoice_diff.py': ['requests']}` を正確に指摘、いずれも検出力を実証。
`concrete_gaps` 空。**自己検証ループ収束 (proposer ≠ approver を満たし完了)**。

---

## 7. deprecated 列移行 (P6, 実装済み)

データモデルを顧客ID集約へ変えた結果、旧『月次サマリ行』モデルの列
(レコード種別 / 発行漏れ件数 / 金額変動件数 / チェック件数合計) と、個別行入力と整合しない
全体集計列 (全体トータル) は未使用になった。

- schema (`notion-db-schema.json`) に `deprecated_properties` を宣言。
- `build_notion_db.ensure_schema`: 既存 DB にこれらの列があれば `properties.{name}=null` で
  **whitelist 削除**。安全制約として **schema の現行 properties に含まれる名前は決して削除しない**
  (誤削除防止。`tests/test_db_migration.py::test_build_never_deletes_a_current_schema_column` で担保)。
- `verify_db_schema`: 旧列が残存していれば **residual として FAIL (exit 1)**。掃除漏れを drift 検知。
- 回帰: `tests/test_db_migration.py` (7本)。build 削除を無効化 / verify residual 判定を無視する
  ミューテーションで対応テストが落ちる (検出力) ことを実証済み (`/tmp/mfk_p6_mutation.txt`)。
