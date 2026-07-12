---
name: run-mf-initial-month-enrich
description: 年払い顧客の初回契約月をMFクラウド請求書から一括投入したいとき、取得担当が初回契約月の初期推定値をNotionへ補完したいときに使う。
argument-hint: "[--plan] [--limit N]"
allowed-tools: Read, Bash, Skill
entrypoint: run-mf-initial-month-enrich
---

# /run-mf-initial-month-enrich

`$ARGUMENTS` を `run-mf-initial-month-enrich` スキルに渡し、別製品 MF クラウド請求書から各取引先の最古発行月を引いて `初回契約月` の初期推定値を Notion に一括投入する任意スキル。
Marketplace から install した場合の呼び出し名は通常 `/mf-kessai-invoice-check:run-mf-initial-month-enrich`。

> **取得担当のみ**: 実行には OAuth トークン (Keychain `mf-invoice-oauth.<keychain-prefix>`) が必須で、持つ人だけが実行できる。一般メンバーには不要 (本体の発行漏れチェックは OAuth 無しで動く)。投入されるのは初期推定値で、最終確定は人が行う。

## 振る舞い

1. `Skill(run-mf-initial-month-enrich, args="$ARGUMENTS")` を呼ぶ。
2. CSV 名寄せ (推奨・API 不要) か OAuth API のいずれかで、未取得顧客だけを差分エンリッチする。書き込みは `初回契約月` 列のみ (どちらも読み取り GET)。
3. `--plan` で対象表示、`--limit N` で書き込み。

## 実行コード

詳細は `skills/run-mf-initial-month-enrich/SKILL.md` と `references/oauth-setup.md` を参照。
