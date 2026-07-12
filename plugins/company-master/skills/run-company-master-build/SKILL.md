---
name: run-company-master-build
description: 企業情報の断片から信頼できる企業マスタ行を新規構築したいとき、確定した企業情報を Notion 企業マスタへ確度付きで登録したいときに使う。
disable-model-invocation: false
user-invocable: true
allowed-tools: [Read, Write, Edit, Bash(python3 *), Agent]
kind: run
prefix: run
effect: external-mutation
owner: harness maintainers
version: 0.1.0
since: 2026-06-09
role_suffix: generator
hierarchy_level: L1
rubric_refs: []
responsibility_refs:
  - ../../prompts/R1-resolve-identity.md
reference_refs:
  - ../../references/company-master-columns.md
  - ../../references/confirm-url-template.md
  - ../../references/data-sources.md
  - ../../references/notion-db-schema.json
  - ../../references/remarks-templates.md
  - ../../references/settings-hardening.json
  - ../../references/README-setup.md
script_refs:
  - ../../scripts/company_master.py
  - ../../scripts/bootstrap_plugin.py
  - ../../scripts/resolve_company.py
  - ../../scripts/enrich_company.py
  - ../../scripts/notion_upsert.py
  - ../../scripts/confirm_url.py
  - ../../scripts/backfill.py
  - ../../scripts/remarks.py
  - ../../scripts/validate_company_master.py
  - ../../scripts/postal_api.py
  - ../../scripts/postal_proxy.py
  - ../../scripts/normalize.py
  - ../../scripts/notion_config.py
source: plugins/company-master/references/data-sources.md
source-tier: internal
last-audited: 2026-06-09
audit-trigger: quarterly
feedback_contract: # per-skill 評価基準(SSOT=scripts/feedback_contract_ssot.py)
  max_iterations: 3
  criteria:
    - id: IN1
      loop_scope: inner
      text: "全行が計7列(会社名title+住所/郵便番号/法人番号/電話番号+『情報の確かさ』+『備考』。正式名称は会社名へ統合)構成で、空欄属性を持つ行は確度=『未確定(要確認)』かつ『備考』に remarks-templates.md 準拠の定型文言が入り、非空の郵便番号 `^\\d{3}-\\d{4}$`/電話ハイフン/住所都道府県起点/法人番号13桁の形式検証を満たすこと(scripts/validate_company_master.py が exit0 で機械判定)。"
      verify_by: script
    - id: IN2
      loop_scope: inner
      text: "誤値混入回避の非対称コスト原則を守り、upsert 一意キーは gBizINFO 確定13桁法人番号のみ・source_by_field の origin→確度ラベル上限を超える確度昇格(例 origin=web で『公的データで確認済み』)は FAIL とし、origin=web の項目は根拠 URL 非空であること(validate_company_master.py の fallback tier 機械照合で担保)。"
      verify_by: script
    - id: OUT1
      loop_scope: outer
      text: "高確度ソース(gBizINFO/日本郵便)で一意確定した値のみ自動確定し、一意確定不能は誤値を入れず空欄+要確認で人間裁定に委ねる設計が、業務横断で参照される信頼マスタの構築・維持という目的(automation bias による誤値固着の回避)を最適に反映していること。"
      verify_by: elegant-review
    - id: OUT2
      loop_scope: outer
      text: "断片入力からの新規構築(build)と既存行底上げ(backfill)の責務分離・確認用URLのページ本文出力(7列維持)・precondition gate の fail-closed が、起動独立性と SSOT plugin-root 集約の観点で過不足なく境界設定されていること。"
      verify_by: elegant-review
---

# run-company-master-build

## Purpose & Output Contract

入力 (法人番号/会社名/住所。複数時は **法人番号 > 会社名 > 住所** の優先順位) を resolve(同定)→enrich(属性補完) の 2 段で処理し、企業マスタ DB へ『情報の確かさ』付きで upsert する。出力先 DB ID はリテラル直書きせず `notion_config.get_db_id('company-master')` で解決する。解決順は **env `COMPANY_MASTER_NOTION_DATABASE_ID` → repo/plugin-root `.notion-config.json` → 同梱 `notion-config.fixed.json` の `databases.company-master.db_id`** (最下位フォールバック)。

> `notion-config.fixed.json` の `db_id` は **単独 install 自己完結のための意図的な既定値** (公開可・token 非含)。上位に `.notion-config.json` (per-repo・gitignore 原則で git 管理外) があればそれで上書きされる最下位フォールバックである。per-repo gitignore 原則との意図的差分として、本ファイルは単独配布で動かすための公開既定値として敢えて plugin に同梱コミットする (CRIT-01)。

Notion 列は **計7列のみ**: 会社名(title=gBizINFO登記名/正式名称を優先表示・無ければ入力通称) / 住所 / 郵便番号 / 法人番号 / 電話番号 の 5属性 + 『情報の確かさ』+ 『備考』。**正式名称は独立列を廃止し会社名タイトルへ統合する** (company_name 通称・official_name 登記名はともに record の `source_by_field` に provenance として保持するが DB 列は会社名 1 つ=表示層と出所層の分離)。`source`/`last_verified`/`確認用URL`/`正式名称` 列は追加しない。**確認用URL はページ本文に固定テンプレートで出力する** (`references/confirm-url-template.md` 正本・`scripts/confirm_url.py` が展開)。詳細は `references/company-master-columns.md` を正本とする。

高確度ソース (gBizINFO API / 日本郵便) で一意確定した値のみ自動確定し、一意確定できない項目は誤値を入れず空欄 + 『未確定(要確認)』で保留する (誤値混入回避の非対称コスト原則: 誤値 >> 空欄)。取得失敗項目は『備考』へ `references/remarks-templates.md` の定型テンプレート文言で原因を記録する (自由記述禁止・複数失敗は改行区切り)。

**per-field 出典 (確認用URLの全項目化)**: record は**全6属性**の取得由来を `source_by_field` (= `{field: {origin, url}}`, origin enum 5値 = `gbizinfo | japanpost | web | user_input | none`) で持ち、**ページ本文の確認用URLセクション**へ全属性の「取得由来 + 検証用URL」を固定テンプレートで記録する (gBizINFO 由来 = 法人詳細ページ URL、郵便番号 = 日本郵便 郵便番号検索の固定 URL、`web` 由来 = 根拠ページ URL **必須**、URL 無し由来 = 由来ラベルのみ)。`source_urls` は `source_by_field` から列順導出される派生値 (後方互換)。update/backfill の本文同期は既存セクションをパースした **URL 非減少マージ** (今回取得した出典のみ差し替え・既存出典 URL は喪失させない)。語彙・形式の正本は `references/confirm-url-template.md`、規則は `references/company-master-columns.md`。

## 境界

企業マスタの同定(resolve)と属性補完(enrich)・確度保持のみ。契約書生成 / 与信判断 / 有料企業DB契約は対象外。電話番号は形式チェックのみで正確性は非保証。

## 主要ルール

- **フォーマット規約**: 郵便番号は〒なし・ハイフン込み 8文字 `NNN-NNNN`。電話番号はハイフン区切り。住所は都道府県起点に正規化。
- **確度4ラベル固定**: `公的データで確認済み | 公的データ取得 | ネット検索(要確認) | 未確定(要確認)`。英語コード値は使わない。
- **信頼キー (SSOT)**: upsert 一意キーは gBizINFO が確定返却した 13桁法人番号のみ。法人番号を持たない/取得不能な行は代替キー(正規化会社名+住所ハッシュ)で仮同定し『未確定(要確認)』として**新規追記のみ**。
- **認証**: 出力先 DB は `notion_config.get_db_id('company-master')`、token は `notion_config.get_token` で解決 (独自実装しない)。gBizINFO トークンは Keychain `gbizinfo-api-token.<keychain-prefix>` に保管しリクエストヘッダ `X-hojinInfo-api-token` で送信。郵便番号取得は日本郵便 addresszip API (Keychain `japanpost-da-api.<keychain-prefix>` の client_id/secret_key + 送信元IP の OAuth2/IP認証。送信元IPは既定で自動検出し、固定時のみ Keychain `japanpost-da-api.<keychain-prefix>`/`egress_ip`)。セットアップ手順は `../../references/japanpost-api-setup.md`。
- **precondition gate**: gBizINFO トークン未登録は fail-closed (exit 2。企業同定の必須入力)。`--upsert` / backfill 本実行では Notion token / DB ID も fail-closed。日本郵便 client_id・secret_key は郵便番号取得用の任意追加設定であり、未登録時は郵便番号だけ空欄 + 備考へ縮退して他項目の処理を継続する (**プロキシ経由なら `proxy_url` で代替**され client_id/secret_key はクライアントに不要)。**送信元IPは自動検出で解決するため gate に含めず**、登録IPとのズレは実行時に 401 で顕在化し `postal_api_unauthorized` 備考で surface する。障害時は取れた項目だけ書き、中間結果を JSONL 退避して次回リプレイ可能にする (縮退)。
- **live スキーマ preflight**: upsert / backfill は書き込み前に Notion API GET database の live スキーマを `references/notion-db-schema.json` (生成元正本: `company-master-columns.md` の7列定義) と照合し、必須7列の欠落・型不一致・『情報の確かさ』select 4オプション不一致・禁止列/余剰列 (旧『正式名称』列を含む)・API 不達は**書き込まず fail-closed** (構造化エラー)。プロセス内キャッシュで多重照会を回避する。
- **レート制限/リトライ**: Notion API の 429/5xx は `Retry-After` 尊重の指数バックオフで最大5回まで自動リトライし、上限超過は構造化エラー (`NotionAPIRetryExhausted`) で fail-closed。backfill は行単位縮退のため、レート超過・中断時も処理済み行は確定済み・失敗行は replay JSONL へ退避済みで、次回実行で再開できる。
- **郵便番号**: 日本郵便 addresszip API (V2 逆引き) で取得する。`scripts/postal_api.py` が構造化検索 (pref/city/town。town は素の町域→小字/大字を段階剥離した複数バリアント) → freeword → 市区町村一覧の最長前方一致の3段で照会し、`pick_best` / `pick_best_prefix` がマッチングレベル・最長一致・候補 zip 収束で一意確定したもののみ採用する (誤値を入れない)。一括 DL データは廃止。詳細な fallback tier 正本は `references/data-sources.md`。
- **責務分離 (Web検索)**: 電話番号・住所のみ入力時の会社名候補の Web 検索は **Claude が goal-seek ループで実施**し、結果 (値+URL) を `enrich_company.py --web-findings <json>` へ渡す。**Python は検索せず検証・整形のみ** (電話は `verify_phone` が市外局番×都道府県を軽量クロスチェック)。
- **フォールバック多段化 (fallback tier 正本 = `references/data-sources.md`)**: 一次手段で取得できない属性は tier 順 (tier1 gBizINFO 検索パターン複数化 → tier2 日本郵便 addresszip API → tier3 WebSearch → tier4 空欄+引き継ぎ) に**属性×許可段ホワイトリスト内**で試行する。**確度昇格禁止** (origin → 確度上限は validate (g) が機械照合)。enrich/resolve は `missing_fields[]` + `attempts[]` (`{field, source, pattern, result, reject_reason}`) を出力し、同一 `(source, pattern)` の再試行は機械スキップ・`MAX_ATTEMPTS_PER_FIELD=3` で有限停止する (日本郵便 `postal_api` の sub-attempts は1回の決定論呼び出しの完結スナップショットとして冪等に全件転記する。`note_attempt` の gap-driven dedup/上限は Web/agent 専用)。
- **信頼キー不変条項**: Web 検索由来の住所での再 resolve (`--address-provenance web`) は 2 要素一致でも**自動確定しない** (候補列挙へ降格・確度上限『ネット検索(要確認)』)。**再 resolve は最大 1 回**とし、再 resolve で得た法人番号が初回確定値と不一致なら自動確定禁止 (候補列挙 + 人間裁定へ)。
- **配布同梱依存**: 実行コードは標準ライブラリ優先。外部 Python ライブラリが必要な場合は plugin-root `vendor/` に同梱し、`scripts/bootstrap_plugin.py` で `sys.path` に追加する。ユーザーの手動 `pip install` を前提にしない。現状の Python 実装に外部依存はない。
- **プラグイン構成**: build/backfill の 2 Skill に加え、`commands/` (起動導線), `agents/` (SubAgent 分担), `hooks/` (機密ガード), plugin-root 集約の共有 `scripts/`・`references/`・`prompts/` (実装と SSOT・両 skill 共有), `vendor/` (同梱依存) を含む配布単位として扱う。manifest は `.claude-plugin/plugin.json`。

## ゴールシーク実行

> 固定手順は書かない。毎周「ゴール・目的/背景・チェックリスト」を読み、その時点で最適な手順を AI が生成・実行する。詳細は run-build-skill `references/goal-seek-paradigm.md`。
> 重い試行錯誤を伴う候補突合は、親セッションを汚さないよう Agent へ fork し、親へは最終成果物と要約のみ返す。

### ゴール (Goal)

業務横断で参照される信頼できる企業マスタが構築・維持された状態。各行は gBizINFO 確定の 13桁法人番号で一意同定され (取得不能時は代替キーで仮同定し『未確定(要確認)』)、6属性が『情報の確かさ』付きで保持され、フォーマット要件 (郵便番号8文字 / 電話ハイフン / 住所都道府県起点) を満たし、一意確定できない値は空欄 + 『未確定(要確認)』で保留され取得失敗原因が『備考』へ定型記録され、ネット検索由来値の根拠 URL が**ページ本文の確認用URLセクション**へ固定テンプレートで記録されている。計7列 (正式名称は会社名 title へ統合) + 確認用URLはページ本文。

### 目的・背景 (Why)

なぜ単なる6項目補完でなくマスタ構築か: 企業情報は断片的で散在し、複数業務 (契約/請求/与信参照) が同じ企業を参照する。行ごとに信頼できる一意同定(法人番号)と確度がないと業務間で食い違い、誤った企業情報のまま契約・請求すれば法的・金銭的リスクが発生する。ゆえに目的は『作業完了』ではなく『法人番号で一意同定され確度を保持した信頼マスタの構築・維持』。公的 API で確定できるものだけ自動確定し、不確実は空欄+要確認で人間裁定に委ね automation bias による誤値固着を防ぐ。取得元は即時取得可能な gBizINFO (経済産業省) を採用 (他系の公的ID発行は数週間規模で即時取得不可)。

### 完了チェックリスト (Checklist)

- [ ] 入力種別 (法人番号/会社名/住所) を検出し、複数種は法人番号>会社名>住所の優先順位で resolve 経路を選択した
- [ ] 住所のみ入力時は会社名を推定せず候補列挙し、対話は一覧提示・backfill は要確認保留にした
- [ ] gBizINFO API で正式名称・所在地・13桁法人番号を取得した (信頼キーの唯一の供給源)
- [ ] 自動確定は法人番号一致 or 会社名+住所2要素一致時のみとし、一意確定不能は『未確定(要確認)』で空欄保留し備考に原因を定型記録した
- [ ] 取得できない属性は `data-sources.md` の fallback tier 表の**定義済み全段 (許可段ホワイトリスト内) を試行し尽くしてから**空欄保留し、`missing_fields[]` / `attempts[]` を記録した (確度昇格なし・同一 `(source,pattern)` 再試行なし)
- [ ] Web 由来住所での再 resolve は最大1回・自動確定なし (法人番号が初回と不一致なら候補列挙へ降格) を守った
- [ ] 住所→郵便番号を日本郵便 addresszip API (`data-sources.md` tier2 の3段フォールバック・一意確定のみ採用) で `NNN-NNNN`・『公的データ取得』で出力した
- [ ] 電話番号は Claude が Web 検索し結果を `--web-findings` で渡し、Python(`verify_phone`)が市外局番×都道府県をクロスチェック、不整合・未取得は空欄+要確認にし備考へ定型記録した
- [ ] 住所を都道府県起点に正規化し、会社名(通称)と正式名称(登記名)を `source_by_field` provenance で保持した(DB 列は会社名 title へ統合=正式名称(official_name)を優先表示。別 DB 列で保持する不変条件は撤回)
- [ ] 取得失敗項目は『備考』へ `remarks-templates.md` の定型文言で記録し、複数失敗は改行区切りで列挙した
- [ ] 全6属性の取得由来 (`source_by_field`: origin enum 5値) を**ページ本文の確認用URLセクション**へ固定テンプレートで記録した (`web` 由来は根拠 URL 必須・既存出典は URL 非減少マージで保持)
- [ ] `notion_config.get_db_id('company-master')` で解決した DB へ信頼キーで upsert、キー欠落時は代替キーで新規追記のみにした
- [ ] 全行に『情報の確かさ』列が付与され、空欄属性を持つ行は『未確定(要確認)』かつ備考に原因が定型記録されている

> 既存 Notion 行の空欄一括補完 (backfill) は本 skill の責務外。`run-company-master-backfill` skill が担当する (起動独立性で分割・設計判断ログ #1)。
- [ ] 外部依存障害時は取れた項目だけ書き、中間結果を JSONL 退避して次回リプレイ可能にした

### ゴールシークループ

1. 未達 `[ ]` を特定 → 2. 手順を都度生成 (固定化禁止) → 3. 実行 → 4. チェックリスト再評価し `[x]` 更新 → 全 `[x]` まで反復。規定周回で未達なら open_issues に差し戻す。

### ゴールシーク配線

- 周回状態と中間成果物は **repo-root (非 repo 環境では plugin-root) 直下**の `eval-log/run-company-master-build-intermediate.jsonl` に追記する (cwd 相対禁止。`backfill.py` の REPLAY_LOG と同じ root 解決規則)。各周回末に不変アンカー `original_goal` (上記ゴール文の原文) と差分、次周回の必須入力 `merged_directive_for_next` を記録し、次周回の入力とする (集約化ドリフト圧縮)。
- SubAgent dispatch は責務単位で固定する: resolve は `company-master-resolve-identity`、属性補完は `company-master-enrich-attributes`、Notion 反映は `company-master-notion-upsert` を使う。
- 重い候補突合は該当 SubAgent へ fork し、親へは最終成果物と要約のみ返す。

### ゴールシーク検証

各周回末に中間成果物 JSONL の整合を機械検証する。`required_keys` (= `original_goal`, `merged_directive_for_next`, `delta`) が全て存在し、`original_goal_hash` が初回の `hashlib.sha256(original_goal)` と一致することを確認する (ゴール改竄検出)。不一致なら周回を停止し差し戻す。

```bash
python3 - <<'PY'
import hashlib, json, pathlib, subprocess
try:
    root = pathlib.Path(subprocess.check_output(
        ["git", "rev-parse", "--show-toplevel"], text=True).strip())
except Exception:
    root = pathlib.Path.cwd()  # 非 repo 環境は plugin-root を cwd にして実行する
p = root / "eval-log/run-company-master-build-intermediate.jsonl"
required_keys = {"original_goal", "merged_directive_for_next", "delta"}
rows = [json.loads(l) for l in p.read_text(encoding="utf-8").splitlines() if l.strip()] if p.exists() else []
if rows:
    base = hashlib.sha256(rows[0]["original_goal"].encode("utf-8")).hexdigest()
    assert all(required_keys <= set(r) for r in rows), "missing required_keys"
    assert all(hashlib.sha256(r["original_goal"].encode("utf-8")).hexdigest() == base for r in rows), "original_goal_hash drift"
print("goal-seek intermediate OK")
PY
```

## 検証 (deterministic checks)

- 非空の郵便番号は `^\d{3}-\d{4}$` (8文字) に一致 (空欄行は非適用)。
- 非空の電話番号はハイフンを含む数字列 (形式のみ・正確性は非保証)。
- 非空の住所は都道府県名で始まる。非空の法人番号は 13桁数字。
- 全行に『情報の確かさ』列があり値が 4ラベルのいずれか (英語enum値は0件)。
- いずれかの属性が空欄の行は『未確定(要確認)』かつ『備考』に `remarks-templates.md` 準拠の定型文言が入っている。
- per-field 出典 (後方互換 gating): `source_by_field` がある新形式 record は全6属性に origin (enum 5値) があり `origin=web` は url 非空。さらに fallback tier 機械照合 (正本 `data-sources.md`): origin → 確度ラベル上限 (確度昇格は FAIL) と属性×許可段ホワイトリスト (例: postal_code の origin=web は FAIL)。旧形式は『ネット検索(要確認)』行の `source_urls` 非空検査へ縮退。計7列構成である (正式名称は会社名 title へ統合・official_name は provenance のみ)。
- upsert 一意キーは gBizINFO 確定 13桁法人番号に従う (空/未確定法人番号でのキー衝突なし)。

上記 (a)-(h) は `scripts/validate_company_master.py <records.json>` が実判定する (違反は非0終了 + 理由出力)。備考の定型文言検査は `references/remarks-templates.md` を正本に照合する。

## 責務マッピング

| 責務 | 実装 | prompt |
|---|---|---|
| interactive-entrypoint | `../../commands/company-master.md` | — |
| executable-wrapper | `../../scripts/company_master.py` | — |
| dependency-bootstrap | `../../scripts/bootstrap_plugin.py` | — |
| resolve-identity | `../../scripts/resolve_company.py` / `../../agents/company-master-resolve-identity.md` | `../../prompts/R1-resolve-identity.md` |
| enrich-attributes | `../../scripts/enrich_company.py` / `../../agents/company-master-enrich-attributes.md` | — (決定論処理 + Web検索結果入力) |
| notion-master-upsert | `../../scripts/notion_upsert.py` / `../../agents/company-master-notion-upsert.md` | — |
| confirm-url-render | `../../scripts/confirm_url.py` (`../../references/confirm-url-template.md` 正本) | — |
| secret-guard | `../../hooks/hook-guard-secret.py` | — |

> 既存 Notion 行の backfill (空欄列選定・2パス制御) は `run-company-master-backfill` skill が担当し、実装 `../../scripts/backfill.py` を共有する。本 skill の責務マッピングには含めない (二重定義回避・SSOT は backfill skill 側)。

### 実行経路 × 入力種別カバレッジ (PROC-01 / AXIS-01)

ラッパ (`../../scripts/company_master.py`) は **決定論の直列実行** (resolve→enrich→upsert を順に呼ぶ)、agent 経路は **Web 検索を含む goal-seek 制御** (候補突合を親から fork) を担う。入力種別ごとの到達経路は以下。

| 入力種別 | 到達経路 | 補足 |
|---|---|---|
| 法人番号 | wrapper 自走完結 | gBizINFO で 13桁キー直接確定。Web 検索不要 |
| 会社名+住所 | wrapper 自走完結 (2要素一致時) / 一致不成立は候補列挙のみ | 自動確定は会社名+住所2要素一致のみ。不成立は『未確定(要確認)』 |
| 会社名のみ | wrapper 経由 `resolve_by_name(address=None)` → 候補列挙のみ | **自動確定不可** (単一ヒットでも 2要素一致が成立し得ない)。候補から選ぶか住所を追加入力して再実行 |
| 住所のみ | Claude 介入必須 (Web 検索) → 候補列挙のみ | 会社名を推定確定せず候補列挙。確定は人間裁定 |

> 「Notion 既存行の空欄 backfill」経路 (空欄列選定・2パス Web 検索・既存非空セル保護) は `run-company-master-backfill` skill のカバレッジへ移管した。本 skill のカバレッジは断片入力からの新規構築に限る。

## 設計判断ログ

なぜ現在の構成 (build/backfill の 2 skill + 共有 SSOT を plugin-root 集約・実体 prompt は R1 のみ・空 vendor・二段防御を references 配布) かの記録。

1. **なぜ build と backfill の 2 skill か (起動独立性で分割)**: resolve / enrich / upsert は単一ゴール『信頼マスタ行を1回で構築』への直列従属で、単一 SSOT (法人番号キー / 7列 + 確認用URL本文 / 確度4ラベル) を共有するため **1 skill (本 run-company-master-build) に束ねる**。enrich と upsert は resolve 出力に強結合し独立起動の意味を持たない。一方 backfill は「断片入力からの新規構築」ではなく「**既存 Notion マスタの空欄を起点に底上げする**」別用途で、入力起点 (Notion DB ⇄ 断片情報) も実行タイミングも独立し、2 パス Web 検索という固有の goal-seek を持つため **run-company-master-backfill として独立 skill に切り出す** (contract-generator の draft/finalize が独立起動ゆえ別 skill なのと同型)。resolve/enrich/upsert を skill 分割しないのは上記の直列従属ゆえで、「分割のための分割」を避ける判断。**2026-06-10 reject を覆す差分論証**: 当時は「command/agent 層で物理分離済みゆえ新規 skill 分割は不要」と判断したが、`disable-model-invocation: false` 下では LLM 自動起動の分岐点は command でなく **skill description** であり、command 分離だけでは「新規構築」と「既存底上げ」の起動意図を Claude が自律選択できない。起動意図の分離には skill 昇格が必要、という差分が 2026-06-18 の backfill 昇格を正当化する (前提として build description から backfill 責務文言を除去し新規構築へ純化済み)。**分割の真の判定軸 = 「起動独立性 × LLM 自律 dispatch 要否」の合成**: backfill は Claude が文脈から自律起動すべき責務 (skill) だが、doctor は決定論保守で人間の明示実行で足りる (LLM 判断ループ無し → `company_master.py` のサブコマンド止まり) という非対称をこの軸が一貫説明する。
2. **なぜ共有実装を plugin-root に集約したか (dangling 根絶)**: backfill skill は resolve/enrich/upsert の実装 (scripts)・7列定義/確度/備考テンプレート (references)・R1 同定 prompt を build skill と 100% 共有する。これらを build skill 配下に残したまま backfill skill から参照すると skill 間相対参照の dangling リスクが残るため、**共有 scripts / references / prompts を plugin-root に集約**し、両 skill が `../../`・agents が `../` で参照する単一 SSOT とした。skill 配下に残すのは skill 固有の `references/resource-map.yaml` のみ。flat import (`import notion_config` 等) のため集約後も script 内部の import は不変 (移設の影響は参照層のみ)。なお `company_master.py` は build/backfill 両 skill の**共有 wrapper** で backfill サブコマンド (`run_backfill`) も提供するため、build の `script_refs` にも `backfill.py` を**推移的依存**として宣言する (物理依存は実在するため宣言する一方、論理責務としての backfill 制御の正本は backfill skill 側であり責務マッピングには非掲載とする二層表現)。
3. **なぜ vendor 空が正常か**: 全 script が標準ライブラリのみで動作し外部依存ゼロのため、`vendor/` は将来用の空の受け皿で空が正常 (B1 lint が空の正当性を機械強制)。
4. **なぜ prompt 実体が R1 のみか**: resolve は会社名/住所の曖昧候補突合という LLM 判断ループを持つため 7 層 prompt (R1) が要る。enrich / upsert は決定論 (日本郵便API 逆引き・形式検証・キー突合) + Web 検索結果入力で LLM 判断ループを持たないため 7 層 prompt 不要。
5. **なぜ二段防御を references 配布か**: plugin は repo の `.claude/settings.json` を直接配布・上書きできないため、静的層 deny ルールは `references/settings-hardening.json` として配布し利用者がマージする (詳細は「セキュリティと権限」節)。動的層 hook は plugin.json で常時配線される。
6. **なぜ確認用URLを DB プロパティ列でなくページ本文へ出すか**: 確認用URLは手動検証専用で行の検索・突合キーにならないため、DB 列にすると冗長な追加列を招く。本文へ固定テンプレート (`confirm-url-template.md` 正本・`confirm_url.py` 展開) で出すことで DB を 7 列に保ち、create/update/backfill 全経路で 100% 同一テンプレートを冪等保証する (remarks-templates.md と同型の SSOT パターン)。当初要求『9列』からの差分 (確認用URLをページ本文化、さらに 2026-06-26 に正式名称を会社名 title へ統合し 7列化) は**ユーザー承認済み**。
7. **なぜ中央プロキシ (postal_proxy.py) を optional-server として用意したか (配布モデル正本の確定)**: 日本郵便の送信元IP許可リストは 1鍵あたり最大10件のため、送信元IPを固定できない/拠点数>10 の環境では各クライアントが自IPを登録する BYO が IP 件数上限に達しうる。この例外ケース向けに**鍵 (client_id/secret_key) と固定送信元IPをサーバ1台に集約**する中央プロキシ (`scripts/postal_proxy.py`、標準ライブラリのみ・`postal_api` の token 発行/IP 認証/addresszip 呼び出しを再利用し直叩きと挙動一致) を `optional-postal-proxy-server` として用意し、該当クライアントだけ `proxy_url` (+任意 `proxy_token`) を設定する。**配布モデルの正本 = BYO 直結が既定 (各自が自分の `client_id`/`secret_key` + 送信元IP で日本郵便 API を直接叩く)、中央プロキシは送信元IPを固定できない/拠点数>10 で IP 上限に達する場合の例外オプトイン** (2026-06-18 にプロキシ既定で決定後、**2026-06-24 にチーム判断で BYO 直結既定へ反転**。実装 `company_master.py` が BYO 既定で動作する側を正とする)。プロキシのデプロイ/設定の正本手順は `references/postal-proxy-deploy.md`、BYO の正本は `references/japanpost-api-setup.md`。`get_postal_proxy_url` が設定されていれば `postal_api.lookup_postal` は自動でプロキシ経由になる (鍵/IP はクライアントに不要)。

## 追加リソース

> 共有 SSOT (scripts / references / prompts) は **plugin-root に集約**し、build・backfill 両 skill が `../../` で参照する。skill 固有は `references/resource-map.yaml` のみ。詳細は設計判断ログ #1・#2。

- `../../references/` — 7列定義 + 確認用URL本文 / 確認用URLテンプレート / データソース・確度 / 備考テンプレート (plugin-root 集約・両 skill 共有)
- `../../references/confirm-url-template.md` — 確認用URL ページ本文の固定テンプレート正本 (`../../scripts/confirm_url.py` が展開)
- `../../references/README-setup.md` — Keychain 3鍵登録 (notion-api-key.<keychain-prefix> / gbizinfo-api-token.<keychain-prefix> / japanpost-da-api.<keychain-prefix>)・settings-hardening マージ・`--upsert` 挙動のセットアップ手順
- `../../references/settings-hardening.json` — 二段防御の静的層 deny ルール (利用者が `.claude/settings.json` へマージ)
- `../../prompts/R1-resolve-identity.md` — resolve 同定判断の7層 prompt 正本 (build・backfill 共有)
- `../../scripts/notion_config.py` — DB ID・token・gBizINFO トークン解決の vendored SSOT
- `../../commands/` — slash command 相当の薄い起動導線
- `../../agents/` — SubAgent 分担定義 (resolve / enrich / notion-upsert)
- `../../scripts/` — プラグイン同梱の安定実行エントリポイント (resolve/enrich/upsert/backfill 等の実装正本)
- `../../vendor/` — 外部 Python ライブラリ同梱先 (現状は空、標準ライブラリのみ)
- `references/resource-map.yaml` — 本 skill 固有のリソース索引 (唯一 skill 配下に残す reference)

## セキュリティと権限

本 Skill は `effect: external-mutation` (Notion 書き込み + 外部 API 照会)。設計書04章の二段防御に従う。

- **静的層**: plugin は repo の `.claude/settings.json` を直接配布・上書きできないため、deny ルールは `references/settings-hardening.json` として同梱配布し、**利用者が repo の `.claude/settings.json` (または `settings.local.json`) の `permissions.deny` へマージ**して有効化する (マージ手順は `references/settings-hardening.json` の `_doc` および `references/README-setup.md`)。3鍵 (`notion-api-key.<keychain-prefix>` / `gbizinfo-api-token.<keychain-prefix>` (account=`<keychain-prefix>`) / `japanpost-da-api.<keychain-prefix>` (account=`secret_key` / `proxy_token` 等)) の平文出力 (`find-generic-password ... -w` / `--print-unsafe`) と誤削除 (`delete-generic-password`) を静的に deny する。
- **動的層**: `PreToolUse` hook (`hooks/hook-guard-secret.py`, plugin.json 配線) が同 3鍵 (japanpost-da-api.<keychain-prefix> の `secret_key` / `proxy_token` を含む) を含む Bash コマンドの平文出力 (`-w`/`-g`/`--print-unsafe`、連結フラグも正規表現で検出) と誤削除 (`delete-generic-password`) を文脈依存で動的ブロックする (`GUARD_ACCOUNTS` が静的層と対称)。hook JSON を解釈できない入力は **fail-closed (exit 2)** で遮断する。

トークンは Keychain のみで扱い生値を端末に出さない。防御の成立条件は**動的層が fail-closed で単独完結**することであり、静的層 (マージ任意・先回り防御) は深層防御 (defense in depth) の追加層と位置づける。

## Gotchas

- `<keychain-prefix>` は文字列リテラルではない。tenant descriptor の `keychain_prefix` を `tenant_runtime.credential_ref()` が解決した service/account を使い、tenant 間で資格情報を共有しない。
- live DB に旧『正式名称』列や未定義の余剰列が残る場合、preflight は書き込み前に fail-closed となる。列を黙って無視して処理を続行しない。

## open_issues (別PR・API疎通後)

以下は品質バグ / 設計矛盾として特定済みのもの。**実データ・API トークン無しでは検証困難なものは別 PR に分離**する (offline で検証可能と判明したものはその時点で対処し解消済みを明記する)。

1. **郵便番号逆引きの一意確定律速 (A4-SYSTEM-01)** — **日本郵便 addresszip API へ移行済み (2026-06-18)**: 旧方式 (郵便番号データの一括 DL + 大口事業所個別番号の第二索引) を廃し、日本郵便公式 API (V2) の逆引きへ一本化した (`scripts/postal_api.py`)。現行は構造化検索 (pref/city/town。小字/大字の段階剥離を含む) → freeword → 市区町村一覧の最長前方一致の3段で照会し、`pick_best` / `pick_best_prefix` が一意確定したもののみ採用する (誤値を入れない非対称コスト原則)。残課題は実 API キー登録後の一意確定率実測のみ (`doctor --probe` + dry-run で実測蓄積後に別 PR)。
2. **backfill が validate_row を迂回 (VERT-01)** — **解消済み (2026-06-10)**: `validate_row` は純 offline 決定論で API 疎通不要と判明したため本 PR で対処した。`backfill.py` は PATCH 前に `validate_enriched` (= `validate_company_master.validate_row`) を実行し、違反行は PATCH せず deferred + replay 退避へ回す (単発 upsert と対称の検証ゲート)。offline 回帰テストを `tests/test_company_master.py` に追加済み。
3. **gBizINFO 実装 V1 固定 vs data-sources.md の V2 優先記述の矛盾 (DEDUCT-01)** — **完全解消 (2026-06-10 実トークン疎通で実証)**: `references/data-sources.md` を実装 (V1 採用・正本 `resolve_company.py` の `GBIZINFO_BASE`) に一本化したうえ、実トークンで V1=HTTP 200 / V2=HTTP 404 を確認した。`https://info.gbiz.go.jp/hojin/v2/` は存在せず「V2 優先」の旧記述自体が誤りだったため、移行判断は不要 (V1 が唯一の動作エンドポイント)。
4. **derive_overall_certainty の保守的設計の意図明記 (A4-VALUE-01)** — **解消済み (2026-06-10)**: 『情報の確かさ』値域節 (`references/company-master-columns.md`) に「最も弱い属性に合わせる保守的設計=非対称コスト原則の意図的反映であり、確度を高く見せる方向の変更は禁止」を明記した。
5. **日本郵便 addresszip API への移行 — 完了 (2026-06-18)**: 旧方式の郵便番号一括 zip 直 DL (全国版 + 大口事業所個別番号版) はプログラムから HTTP 404 で遮断されていた (bot 対策/配信障害)。これを根本解消するため郵便番号取得を日本郵便公式 API (V2 逆引き) へ全面移行した。認証は OAuth2 client_credentials (Keychain `japanpost-da-api.<keychain-prefix>`) + 送信元IP認証 (`x-forwarded-for`。既定は自動検出、固定時のみ Keychain `egress_ip`)。失敗時の縮退: 認証失敗 (401/403) → 空欄 + 備考 `postal_api_unauthorized` / 通信失敗 → `postal_api_unavailable` / 一意確定不能 → `postal_code`。`doctor --probe` が token 発行 + テスト検索で登録IPとのズレを検知する。セットアップ手順は `references/japanpost-api-setup.md`。残課題は実 API キー登録後の疎通確認のみ。

6. **配布モデルの確定 (BYO 直結既定)** — **戦略決定済み (2026-06-18 → 2026-06-24 反転)**: 当初 (2026-06-18) は送信元IP許可リスト上限 (1鍵最大10件) を理由に中央プロキシ既定で決定したが、**2026-06-24 にチーム判断で BYO 直結既定へ反転**した。**正本 = BYO 直結 (各自が `client_id`/`secret_key` + 送信元IP を登録し直接叩く・`references/japanpost-api-setup.md`) が既定、中央プロキシ (鍵と固定IPをサーバ集約・`scripts/postal_proxy.py` / 手順 `references/postal-proxy-deploy.md`) は送信元IPを固定できない/拠点数>10 で IP 上限に達する場合の例外オプトイン**。実装 (`company_master.py` の郵便番号取得モード表示・`notion_config.get_postal_proxy_url`) が BYO 既定側で一致。配線は `notion_config.get_postal_proxy_url/get_postal_proxy_token` + `plugin-composition.yaml` の `postal_proxy` capability 宣言で完了済み。残課題はプロキシ実 deploy 後の疎通確認のみ (別 PR)。

未解消は 1・5 の実 API キー登録後の疎通確認・一意確定率実測、および 6 のプロキシ実 deploy 後の疎通確認のみ (`doctor --probe` + dry-run で蓄積後に別 PR)。なお 2026-06-10 に実トークンで E2E を実証済み (当時は8列構成): doctor 全 OK → live DB を当時の正本へ整備 → 法人番号入力で resolve(公的データで確認済み)→enrich→validate PASS→upsert created (本文確認用URL節を確認) → テスト行 archive (郵便番号の addresszip 移行は 2026-06-18)。2026-06-26 に正式名称列を会社名 title へ統合し 7列化 (live 列の物理削除はユーザー実施)。
