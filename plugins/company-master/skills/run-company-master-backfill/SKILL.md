---
name: run-company-master-backfill
description: 固定 Notion 企業マスタ DB の空欄列を既存行から一括補完するとき、『要確認』行を確度付きで底上げ再取得するときに使う。
disable-model-invocation: false
user-invocable: true
allowed-tools: [Read, Write, Edit, Bash(python3 *), Agent]
kind: run
prefix: run
effect: external-mutation
owner: harness maintainers
version: 0.1.0
since: 2026-06-18
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
  - ../../scripts/backfill.py
  - ../../scripts/enrich_company.py
  - ../../scripts/notion_upsert.py
  - ../../scripts/resolve_company.py
  - ../../scripts/confirm_url.py
  - ../../scripts/remarks.py
  - ../../scripts/validate_company_master.py
  - ../../scripts/postal_api.py
  - ../../scripts/postal_proxy.py
  - ../../scripts/normalize.py
  - ../../scripts/notion_config.py
source: plugins/company-master/references/data-sources.md
source-tier: internal
last-audited: 2026-06-18
audit-trigger: quarterly
feedback_contract: # per-skill 評価基準(SSOT=scripts/feedback_contract_ssot.py)
  max_iterations: 3
  criteria:
    - id: IN1
      loop_scope: inner
      text: 補完対象を「空欄列を持つ行」または『ネット検索(要確認)』/『未確定(要確認)』行のみに限定し、既存非空セルが PATCH 前後で不変であること(backfill.py が既存値を読み空欄列のみ PATCH 対象化・tests/test_company_master.py の backfill ケースで機械検証)。
      verify_by: test
    - id: IN2
      loop_scope: inner
      text: PATCH 前に validate_enriched (= validate_company_master.validate_row) を実行し、7列構成(正式名称は会社名 title へ統合)・郵便番号8文字・電話ハイフン・住所都道府県起点・確度4ラベル enum・origin→確度上限・信頼キーに違反する行は PATCH せず deferred + replay JSONL へ退避すること(validate_company_master.py が実判定)。
      verify_by: script
    - id: IN3
      loop_scope: inner
      text: 各行の空欄列を埋めるのに必要な API (gBizINFO / 日本郵便 addresszip) だけを起動し全項目を無条件再取得しないこと、Web 検索が要る列は needs_web_search (page_id + missing_fields + attempts) に列挙し 2 パス目で attempts に無い (source, pattern) のみ許可段ホワイトリスト内で試行すること(backfill.py の 2 パス制御・REQUIRE_REVERIFY_CERTAINTIES 正本で担保)。
      verify_by: script
    - id: OUT1
      loop_scope: outer
      text: 既存 Notion 行起点の空欄補完という起動が、断片入力からの新規構築 (run-company-master-build) と入力契約・実行タイミングで混線せず疎結合し、誤値 >> 空欄 の非対称コスト原則 (取得不能は空欄+『未確定(要確認)』+備考定型記録) と URL 非減少マージを満たして「既存マスタの品質を後から底上げする」目的を最適に反映していること。
      verify_by: elegant-review
---

# run-company-master-backfill

> 本 skill は `run-company-master-build` と **同一プラグイン (company-master) の共有 SSOT** (plugin-root の `scripts/` `references/` `prompts/`) を `../../` で参照する。7列定義(正式名称は会社名 title 統合)・確度4ラベル・信頼キー・検証 (`validate_company_master`) は build と完全共有し、本 skill 固有は「既存 Notion 行を起点にした空欄補完の制御」に限る。新規企業の断片入力からの同定構築は build skill の責務 (本 skill では扱わない)。

## Purpose & Output Contract

**既に存在する** Notion 企業マスタ DB の行を起点に、空欄列または『ネット検索(要確認)』/『未確定(要確認)』の行**だけ**を補完対象にして、企業マスタを確度付きで底上げする。新規行の作成 (断片入力 → resolve → 構築) は対象外であり、それは `run-company-master-build` が担う。

出力先 DB ID は build と同じく `notion_config.get_db_id('company-master')` で解決する (env `COMPANY_MASTER_NOTION_DATABASE_ID` → repo/plugin-root `.notion-config.json` → 同梱 `notion-config.fixed.json` の順)。Notion 列 (計7列・正式名称は会社名 title 統合) / 確度4ラベル / 信頼キー (gBizINFO 13桁法人番号) / 確認用URL本文テンプレートは `../../references/company-master-columns.md` ほか共有 references を正本とする (build と単一 SSOT・二重定義しない)。

**既存非空セルは上書きしない。** 補完するのは空欄列と要確認行のみ。取得不能な項目は誤値を入れず空欄 + 『未確定(要確認)』を維持し、原因を『備考』へ `../../references/remarks-templates.md` の定型文言で記録する。ネット検索由来値の根拠 URL は**ページ本文の確認用URLセクション**へ固定テンプレートで記録し、既存セクションは **URL 非減少マージ** (今回取得分のみ差し替え・既存出典 URL を喪失させない) で同期する。

## 境界

固定 Notion 企業マスタ DB の**既存行の空欄補完のみ**。新規企業の断片 (会社名/住所/法人番号) からの同定・新規追記は `run-company-master-build` に委譲する。契約書生成 / 与信判断 / 有料企業DB契約は対象外。

**build → backfill のハンドオフ契約**: build skill が空欄 + 『未確定(要確認)』/『ネット検索(要確認)』で残した行が、本 skill の入力契約 (再取得対象) となる。両 skill は新たな状態列を設けず、既存の『情報の確かさ』列と各セルの空欄状態を介して疎結合する (contract-generator が台帳ステータス列で draft→finalize を疎結合するのと同型・状態の SSOT は Notion DB 自身)。再取得対象とする確度ラベル集合は `../../scripts/backfill.py` の `REQUIRE_REVERIFY_CERTAINTIES` を正本とする。

## 主要ルール

### build と共有するルール (正本は共有 references・二重定義しない)

- **フォーマット規約**: 郵便番号 `NNN-NNNN` 8文字 / 電話番号ハイフン区切り / 住所都道府県起点 (`../../references/company-master-columns.md`)。
- **確度4ラベル固定**: `公的データで確認済み | 公的データ取得 | ネット検索(要確認) | 未確定(要確認)` (英語コード値禁止)。
- **信頼キー (SSOT)**: upsert 一意キーは gBizINFO 確定 13桁法人番号のみ。未確定行は代替キー (正規化会社名+住所ハッシュ) で**既存行を誤更新せず**扱う。
- **live スキーマ preflight**: 書き込み前に Notion live スキーマを `../../references/notion-db-schema.json` と照合し、必須7列の欠落・型不一致・select 4オプション不一致・禁止列/余剰列 (旧『正式名称』列を含む)・API 不達は**書き込まず fail-closed**。
- **precondition gate / 認証**: Notion token・gBizINFO トークン未登録は fail-closed (exit 2)。日本郵便鍵 (client_id・secret_key) は郵便番号取得用の任意追加設定であり、未設定時は郵便番号だけ空欄 + 備考へ縮退して他項目の補完を継続する。**プロキシ経由は `proxy_url` 代替**でローカル鍵を不要にする (`backfill.precondition_gate` が単発 upsert と対称化済)。送信元IPは自動検出で解決するため gate に含めない。token は `notion_config` で解決 (独自実装しない・Keychain のみ・平文出力禁止)。
- **フォールバック多段化 / 確度昇格禁止 / 信頼キー不変条項**: `../../references/data-sources.md` の fallback tier 表に従い、属性×許可段ホワイトリスト内のみ試行する。origin → 確度上限は `validate_company_master` (g) が機械照合する。

### backfill 固有のルール

- **既存非空セル不可侵**: 既に値が入っているセルは決して上書きしない。補完対象は空欄列と『ネット検索(要確認)』/『未確定(要確認)』の行に限定する。
- **空欄列ごとの最小 API 起動**: 行の空欄列を検出し、その列を埋めるのに必要な API (gBizINFO / 日本郵便API) だけを起動する。全項目を無条件に再取得しない。
- **2 パス運用 (Web 検索が必要な行)**: backfill は決定論で埋められる列 (法人番号→gBizINFO 属性・住所→日本郵便API 郵便番号) を **1 パス目**で自走補完し、Web 検索が要る列 (電話番号等) は出力 `needs_web_search` (page_id + `missing_fields` + `attempts`) に列挙する。Claude が許可段ホワイトリスト内で Web 検索し、`attempts` に**無い** `(source, pattern)` のみ試行のうえ `backfill --web-findings '{"<page_id>": {"phone": {...}}}'` で **2 パス目**を投入する。
- **行単位縮退 + リプレイ**: backfill は行単位で確定/退避する。Notion API の 429/5xx は `Retry-After` 尊重の指数バックオフで最大5回リトライし、上限超過・中断時も処理済み行は確定済み・失敗行は replay JSONL へ退避済みで次回再開できる。`validate_enriched` (= `validate_company_master.validate_row`) を PATCH 前に実行し、違反行は PATCH せず deferred + replay 退避へ回す (単発 upsert と対称の検証ゲート)。
- **`--dry-run`**: 副作用を抑えて対象行の選定だけ確認する。
- **`--migrate-company-title` (移行モード・opt-in)**: 既存登録行の会社名 title (通称) を登記名へ移行する。正式名称列を物理削除した後はページ上の値から登記名を復元できないため、**法人番号 (13桁) を持つ行を再 resolve (gBizINFO) して登記名を取得**し、`official_name(登記名) ≠ 既存 title` のときだけ title を上書きする (title のみ既存非空保護を解除。住所/郵便/法人番号/電話の保護と alt_key は不変。既に登記名なら冪等 no-op)。法人番号なし行・登記名を確定できない行は通称のまま触らない。`--dry-run` 併用で対象を確認でき、**live への実行はユーザー判断** (既定 OFF・通称 title を保持)。

## ゴールシーク実行

> 固定手順は書かない。毎周「ゴール・目的/背景・チェックリスト」を読み、その時点で最適な手順を AI が生成・実行する。詳細は run-build-skill `references/goal-seek-paradigm.md`。
> 重い候補突合・Web 検索は親セッションを汚さないよう Agent (`company-master-enrich-attributes`) へ fork し、親へは最終成果物と要約のみ返す。

### ゴール (Goal)

固定 Notion 企業マスタ DB の既存行のうち、空欄列を持つ行・要確認行が、**既存非空セルを破壊せず**、空欄列ごとに必要 API のみで確度付きに底上げされ、フォーマット要件 (郵便番号8文字 / 電話ハイフン / 住所都道府県起点) を満たし、一意確定できない値は空欄 + 『未確定(要確認)』のまま保留され取得失敗原因が『備考』へ定型記録され、ネット検索由来値の根拠 URL がページ本文の確認用URLセクションへ URL 非減少マージで記録された状態。

### 目的・背景 (Why)

なぜ build と別 skill か: build は「断片情報から信頼マスタ行を 1 回で**新規構築**する」起動であり、backfill は「**既に存在するマスタ**の品質を後から底上げする」起動である。入力起点 (Notion DB の既存行 ⇄ ユーザーが渡す断片) も実行タイミング (運用中の定期メンテ ⇄ 新規登録時) も独立し、backfill は 2 パス Web 検索という固有の goal-seek 制御を持つ。両者を 1 skill に束ねると「既存行起点」と「断片起点」の入力契約が混線するため、起動の独立性に従って skill を分けた (実装 scripts は plugin-root で共有し二重実装しない)。誤値混入回避の非対称コスト原則 (誤値 >> 空欄) と automation bias 回避は build と共有する。

### 完了チェックリスト (Checklist)

- [ ] `notion_config.get_db_id('company-master')` で解決した DB の live スキーマを `notion-db-schema.json` と preflight 照合し、不一致・API 不達なら書き込まず fail-closed にした
- [ ] 補完対象を「空欄列を持つ行」または『ネット検索(要確認)』/『未確定(要確認)』の行に限定し、既存非空セルを上書き対象から除外した
- [ ] 各行の空欄列を検出し、その列を埋めるのに必要な API (gBizINFO / 日本郵便API) **だけ**を起動した (全項目の無条件再取得をしていない)
- [ ] 法人番号が既にある行は gBizINFO で属性 (正式名称/住所) を、住所がある行は日本郵便 addresszip API で郵便番号を、決定論で 1 パス目補完した
- [ ] Web 検索が要る列 (電話番号等) は 1 パス目出力 `needs_web_search` (page_id + `missing_fields` + `attempts`) に列挙し、2 パス目で許可段ホワイトリスト内・`attempts` に無い `(source, pattern)` のみ検索し `--web-findings` で再投入した
- [ ] フォールバックは `data-sources.md` fallback tier の許可段ホワイトリスト内のみ・確度昇格なし・同一 `(source, pattern)` 再試行なしを守った
- [ ] PATCH 前に `validate_enriched` (= `validate_company_master.validate_row`) を実行し、違反行は PATCH せず deferred + replay 退避へ回した
- [ ] 取得不能な値は空欄 + 『未確定(要確認)』を維持し `remarks-templates.md` の定型文言で備考へ原因記録した (複数失敗は改行区切り)
- [ ] ネット検索由来値の根拠 URL をページ本文の確認用URLセクションへ URL 非減少マージで記録した (既存出典 URL を喪失させていない)
- [ ] Notion API 429/5xx は指数バックオフで最大5回リトライし、上限超過・中断時も処理済み行は確定・失敗行は replay JSONL へ退避し次回再開可能にした
- [ ] `--dry-run` 指定時は副作用を抑えて対象行の選定のみ確認した

### ゴールシークループ

1. 未達 `[ ]` を特定 → 2. 手順を都度生成 (固定化禁止) → 3. 実行 → 4. チェックリスト再評価し `[x]` 更新 → 全 `[x]` まで反復。規定周回で未達なら replay JSONL へ退避し差し戻す。

### ゴールシーク配線

- backfill の行単位中間結果・失敗行は `backfill.py` の REPLAY_LOG (repo-root、非 repo 環境では plugin-root 直下) に退避し、次回実行で再開する (cwd 相対禁止)。
- SubAgent dispatch: 属性補完 (Web 検索含む) は `../../agents/company-master-enrich-attributes.md`、Notion 反映は `../../agents/company-master-notion-upsert.md` を使う。同定が必要な行 (会社名/住所のみで法人番号未確定) は `../../agents/company-master-resolve-identity.md` を使う。
- 重い候補突合・Web 検索は該当 SubAgent へ fork し、親へは最終成果物と要約のみ返す。

## 検証 (deterministic checks)

build と同一の `../../scripts/validate_company_master.py <records.json>` が実判定する (7列構成(正式名称は会社名 title 統合)・郵便番号8文字・電話ハイフン・住所都道府県起点・確度4ラベル enum・空欄行は『未確定(要確認)』+ 備考定型文言・per-field 出典 origin enum・確度昇格 FAIL・信頼キー)。backfill 固有の不変条件は「既存非空セルが PATCH 前後で不変」であり、`backfill.py` が既存値を読み取り空欄列のみを PATCH 対象にすることで担保する (テストは `tests/test_company_master.py` の backfill ケース)。

## 責務マッピング

| 責務 | 実装 | prompt |
|---|---|---|
| backfill-entrypoint | `../../commands/company-master-backfill.md` | — |
| executable-wrapper | `../../scripts/company_master.py` (`backfill` サブコマンド) | — |
| dependency-bootstrap | `../../scripts/bootstrap_plugin.py` | — |
| notion-driven-backfill | `../../scripts/backfill.py` (空欄列選定・2パス制御・行単位縮退・replay) | — |
| resolve-identity (法人番号未確定行) | `../../scripts/resolve_company.py` / `../../agents/company-master-resolve-identity.md` | `../../prompts/R1-resolve-identity.md` |
| enrich-attributes | `../../scripts/enrich_company.py` / `../../agents/company-master-enrich-attributes.md` | — (決定論処理 + Web検索結果入力) |
| notion-master-upsert | `../../scripts/notion_upsert.py` / `../../agents/company-master-notion-upsert.md` | — |
| confirm-url-render | `../../scripts/confirm_url.py` (`../../references/confirm-url-template.md` 正本) | — |
| secret-guard | `../../hooks/hook-guard-secret.py` | — |

## 設計判断ログ

1. **なぜ build と別 skill か (起動独立性)**: 入力起点が「既存 Notion 行」(build は「ユーザーが渡す断片」)、実行タイミングが「運用中メンテ」(build は「新規登録時」) と独立し、2 パス Web 検索という固有 goal-seek を持つため、起動の独立性に従って分割した。詳細は build SKILL.md「設計判断ログ #1」と対。
2. **なぜ実装を共有するか (二重実装回避)**: backfill は resolve/enrich/upsert を 100% 再利用し、独自実装は「空欄列選定 + 2 パス制御 + 行単位縮退」(= `backfill.py`) のみ。共有実装 (scripts) と SSOT (references / prompts) は plugin-root に集約し `../../` で参照する。これにより build と backfill が確度・7列・信頼キー・検証で乖離しない (単一 SSOT)。
3. **なぜ既存非空セルを不可侵にするか**: backfill は「人が確認済みの値」を含む運用中 DB を対象にするため、自動処理で既存値を上書きすると人手の確定を破壊しうる。空欄列のみ補完 + 要確認行のみ再取得とし、誤値 >> 空欄の非対称コスト原則を運用面でも徹底する。

## 追加リソース

> 共有 SSOT (scripts / references / prompts) は plugin-root に集約され、build skill と共有する。本 skill 固有は `references/resource-map.yaml` のみ。

- `../../references/` — 7列定義 / 確認用URLテンプレート / データソース・確度 / 備考テンプレート (build と共有)
- `../../prompts/R1-resolve-identity.md` — resolve 同定判断の7層 prompt 正本 (build と共有)
- `../../scripts/backfill.py` — 本 skill の中核実装 (空欄列選定・2パス制御・replay)
- `../../scripts/notion_config.py` — DB ID・token・gBizINFO トークン解決の vendored SSOT
- `../../commands/company-master-backfill.md` — slash command 起動導線
- `../../agents/` — SubAgent 分担定義 (resolve / enrich / notion-upsert)
- `references/resource-map.yaml` — 本 skill 固有のリソース索引

## セキュリティと権限

本 Skill は `effect: external-mutation` (Notion 書き込み + 外部 API 照会)。二段防御は build と共有する。静的層 deny ルールは `../../references/settings-hardening.json` (利用者が `.claude/settings.json` へマージ)、動的層は `../../hooks/hook-guard-secret.py` (plugin.json 配線) が 3鍵 (`notion-api-key.<keychain-prefix>` / `gbizinfo-api-token.<keychain-prefix>` / `japanpost-da-api.<keychain-prefix>` (secret_key・proxy_token 等)) の平文出力・誤削除を fail-closed で遮断する。トークンは Keychain のみで扱い生値を端末に出さない。

## Gotchas

- `<keychain-prefix>` は文字列リテラルではない。tenant descriptor の `keychain_prefix` を `tenant_runtime.credential_ref()` が解決した service/account を使い、tenant 間で資格情報を共有しない。
- `--migrate-company-title` は既存非空セル不可侵の唯一の opt-in 例外で、上書き可能なのは gBizINFO で登記名を再取得できた会社名 title だけ。住所・郵便番号・法人番号・電話番号は引き続き不可侵とする。

## open_issues

backfill 固有の未解消は build SKILL.md「open_issues」と共有する (日本郵便 addresszip API の一意確定率実測・実 API 疎通確認 / backfill 冷却 TTL)。backfill 冷却 TTL (同一行の過剰な再 backfill を抑える間隔) は別 PR で管理する。
