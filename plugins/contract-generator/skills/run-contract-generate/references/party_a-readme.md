# party_a (甲) 固定値 — 正本への参照

> **このファイルはスタブです。** 甲(発注者)固定値の仕様・優先順位・スキーマ・上書き手順の**正本は
> plugin 直下 [`references/party_a-readme.md`](../../../references/party_a-readme.md)** に一本化しています
> (`config_auth.py` 同梱の `references/party_a.default.json` と同じ場所に置くため)。
> 重複記載は整合崩壊の元なので、ここには skill 固有の補足のみを書きます。

## この skill (run-contract-generate) 固有の補足

- 取得は **`lib/config_auth.load_party_a()` を直接呼ぶ**(`lib/ledger.get_party_a()` は同関数への薄い委譲エイリアス)。台帳 (Google Sheets) に甲列は作らない。
- 差込は `template-mapping.json` の `common.fixed_values` に置いた `{{party_a.name|address|title|rep_name}}` を `docx_fill` が `load_party_a()` の戻り値で解決する。
- 甲代表者は**役職 (`title`) と氏名 (`rep_name`) を別 run に分けて差込む**設計。合成形 `{{party_a.representative}}` は差込に使わない(`template-mapping.json` の `_party_a_representative_note` 参照)。

優先順位・スキーマ・上書きコマンドは正本を参照してください。
