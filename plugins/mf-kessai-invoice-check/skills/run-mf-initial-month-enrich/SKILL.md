---
name: run-mf-initial-month-enrich
description: 年払い顧客の初回契約月をMFクラウド請求書から一括投入したいとき、取得担当が初回契約月の初期推定値をNotionへ補完したいときに使う。
disable-model-invocation: true
user-invocable: true
argument-hint: "[--plan] [--limit N]"
arguments: [plan, limit]
allowed-tools:
  - Read
  - Write
  - Bash(python3 *)
kind: run
prefix: run
effect: external-mutation
owner: team-platform
since: 2026-06-24
version: 0.1.0
source: doc/ClaudeCodeスキルの設計書/
source-tier: internal
last-audited: 2026-06-24
audit-trigger: official-update
feedback_contract: # per-skill 評価基準(SSOT=scripts/feedback_contract_ssot.py)
  max_iterations: 3
  criteria:
    - id: IN1
      loop_scope: inner
      text: 掛け払いの顧客名と MFクラウド請求書の partner 名が、別 ID をまたいで会社名正規化(法人格除去+全半角統一・mf_invoice_names.py の正本ロジック)で突合され、表記揺れのある取引先でも正しく名寄せされ誤マッチを生まないことを pytest(csv_match の名寄せ)で機械検証できる。
      verify_by: test
    - id: IN2
      loop_scope: inner
      text: 補完は差分のみ(Notion の `初回契約月` が空欄の顧客だけが対象で埋まった顧客は再取得しない)で、CSV 名寄せ経路は掛け払い顧客の確定リスト mfk-gap-verified.json 不在時に fail-closed で停止し、未検証の顧客集合に対する書き込みを防ぐことを機械検証できる。
      verify_by: test
    - id: OUT1
      loop_scope: outer
      text: スキル全体がユーザ目的(年払い顧客の初回契約月を最古発行月の初期推定値として一括投入し run-mf-invoice-check の年間契約抑制の誤検出を減らす・最終確定は人・MFクラウド請求書側は読み取り専用)を過不足なく満たし、CSV 軽量経路(OAuth 不要)と OAuth 無人経路の2経路および配布境界(コードは全員配布・実行は OAuth トークンを持つ取得担当のみ)が目的に対し適切に分離されていること。
      verify_by: elegant-review
---

# run-mf-initial-month-enrich

## Purpose & Output Contract

年払い顧客の管理列 `初回契約月` を、別製品 **MFクラウド請求書 (MoneyForward Cloud Invoice)** から各取引先の**最古発行月**を引いて **Notion DB に初期推定値として一括投入**する。`run-mf-invoice-check` の年間契約抑制 (`suppress_annual_period_gaps`) は埋まった `初回契約月` を読んで年払い顧客の発行漏れ誤検出を消すため、この補完で誤検出を減らせる。

> **このスキルは取得担当 1 名だけの任意作業です。** 一般メンバーには不要で、`初回契約月` は人が Notion に手で `YYYY-MM` を記入するだけでも本体は完結します (空でも発行漏れチェックは動き、年払い顧客は安全側で候補に残るだけ)。`disable-model-invocation: true` のため自動起動はされません。

**入力**: なし (Notion から `初回契約月` 空の顧客を自動抽出)。CSV 名寄せ経路 (経路1) では MFクラウド請求書からエクスポートした請求書一覧 CSV のパスを `mf_invoice_csv_match.py` に**位置引数**で渡す (`--csv` フラグではない)
**出力**: Notion DB の `初回契約月` (空欄の顧客のみ) が `YYYY-MM` の初期推定値で埋まる。一度埋めた顧客は次回以降の対象から外れる (差分のみ)
**完了条件**: 対象顧客 (初回契約月が空) の名寄せが完了し、最古発行月が取れた顧客の `初回契約月` が Notion に書き込まれた状態。最終確定 (最古発行月 ≠ 初回契約月の補正) は人が行う

## なぜ別スキルなのか

`run-mf-invoice-check` (MF掛け払い・APIキー・月次) とは**別製品・別認証**: 本スキルは MFクラウド請求書 (`invoice.moneyforward.com/api/v3`, **OAuth2**) を叩く。コードは全 install 者に配布されるが、**実行には OAuth トークン (Keychain `mf-invoice-oauth.<keychain-prefix>`) が必要で、それを持つ取得担当だけが実行できる**。トークンが無い人は (コードがあっても) 実行できないため、全員に OAuth を強制しない。

## 2 つの経路

### 1. CSV 名寄せ (推奨・軽量・OAuth 不要)

MFクラウド請求書 UI で請求書一覧を CSV エクスポートし、名寄せして報告する (書き込みはしない・検証用)。

```bash
python3 "$CLAUDE_PLUGIN_ROOT/skills/run-mf-initial-month-enrich/scripts/mf_invoice_csv_match.py" <CSVパス>
```

CSV 名寄せは掛け払い顧客リスト源として `mfk-gap-verified.json` (月次チェックの確定リスト) を必要とするため、先に `run-mf-invoice-check` を 1 度 collect→verify→finalize まで回しておくこと (不在なら fail-closed で停止する)。名寄せ精度の事前確認はこのスクリプトの出力 (マッチ/失敗 件数・名寄せ失敗社の一覧) で行える (配布対象外の OAuth probe に頼らない)。

### 2. OAuth API (無人運用向け)

初回 1 回トークンを取得し (`references/oauth-setup.md`)、未取得顧客だけを差分エンリッチする。

```bash
SK="$CLAUDE_PLUGIN_ROOT/skills/run-mf-initial-month-enrich/scripts"
python3 "$SK/mf_invoice_enrich.py" --plan        # 対象 (初回契約月が空) を表示のみ (MFトークン不要)
python3 "$SK/mf_invoice_enrich.py" --limit 20     # 実取得して Notion に書き込む (要 OAuth トークン)
```

`--plan` は Notion 側だけ見るドライラン。`--limit N` は初回の大量投入を分割する。

## Key Rules

1. **取得担当のみ・任意**: 一般メンバーは実行不要。`初回契約月` は人手記入 `YYYY-MM` が正本で、本スキルは初期推定値の一括投入を楽にする補助。
2. **別認証 (OAuth2)**: MF掛け払いの API キーは使えない (`401 token_rejected`)。トークンは Keychain `mf-invoice-oauth.<keychain-prefix>`。手順は `references/oauth-setup.md`。
3. **読み取り専用 (MFクラウド請求書側)**: `mf_invoice_api.py` は GET 専用 (`/partners`・`/billings`)。請求書の作成・更新はしない。書き込むのは Notion の `初回契約月` 列のみ。
4. **差分のみ**: `初回契約月` が空の顧客だけが対象。埋まった顧客は再取得しない (毎回ほぼゼロコスト)。
5. **名寄せ**: 掛け払いの顧客名 ↔ 請求書の partner 名で突合 (別 ID のため会社名正規化: 法人格除去 + 全半角統一)。
6. **最終確定は人**: 投入されるのは初期推定値 (最古発行月)。最古発行月 ≠ 初回契約月のケースは人が補正する。

## Gotchas

1. 出力先 (CSV 名寄せ結果) は `MFK_OUTPUT_DIR > CLAUDE_PROJECT_DIR > CWD` の `eval-log/` に解決される (`run-mf-invoice-check` と同じ)。
2. `mf_invoice_enrich.py` は本プラグインの `lib/notion_invoice_sink.py` / `lib/mfk_api.py` (Notion トークン・config) を再利用する。`$CLAUDE_PLUGIN_ROOT` 優先で解決するため install 位置に依存しない。
3. 認可コードは 10 分で失効。access_token は 1 時間 (refresh_token で自動更新)。詳細は `references/oauth-setup.md`。

## Additional Resources

- `references/oauth-setup.md` — OAuth2 アクセストークン取得手順 (正本)
- `scripts/mf_invoice_oauth.py` — トークン初回取得・refresh (Keychain `mf-invoice-oauth.<keychain-prefix>`)
- `scripts/mf_invoice_api.py` — MFクラウド請求書 API v3 GET クライアント
- `scripts/mf_invoice_enrich.py` — 差分エンリッチ本体 (Notion 書き込み)
- `scripts/mf_invoice_csv_match.py` — CSV 名寄せ (OAuth 不要の軽量経路)
- `$CLAUDE_PLUGIN_ROOT/skills/ref-mf-kessai-api/` — 初回契約月の使われ方 (年間契約抑制) の参照
