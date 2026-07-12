---
name: company-master
description: 会社名・住所・法人番号から企業マスタを補完し、必要に応じて固定 Notion DB へ upsert する。
argument-hint: "--name <会社名> [--address <住所>] | --address <住所> | --hojin-bango <13桁> [--upsert] [--web-findings '<json>']"
allowed-tools: Read, Bash, Skill
entrypoint: run-company-master-build
---

# /company-master

`$ARGUMENTS` を `run-company-master-build` に渡し、企業の同定、属性補完、検証、Notion 反映を実行する。
Marketplace から install した場合の呼び出し名は通常 `/company-master:company-master`。

## 振る舞い

1. 入力種別を `法人番号 > 会社名 > 住所` の優先順位で解釈する。
2. `run-company-master-build` が gBizINFO / 日本郵便API / Web 検索結果を統合する。
3. `--upsert` 指定時だけ固定 Notion 企業マスタ DB に書き込む。
4. 取得不能な値は空欄にし、備考へ定型文言、ネット検索由来値の根拠URLはページ本文の確認用URLセクションへ残す。

## 実行コード

決定論処理だけを直接実行する場合は、プラグイン配下のラッパを使う。

```bash
python3 "${CLAUDE_PLUGIN_ROOT:-plugins/company-master}/scripts/company_master.py" --name "株式会社サンプル" --address "東京都..." --upsert
```
