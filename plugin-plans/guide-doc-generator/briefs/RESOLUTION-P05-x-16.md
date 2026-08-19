# RESOLUTION-P05-x-16 — C20 の stderr 契約が実装の診断コードを網羅していない

task: `P05-x-16` / consumes: `plugins/guide-doc-generator/scripts/extract-handout-config.py`,
`briefs/script-brief-C20.json` / write_scope: `plugin-plans/guide-doc-generator/briefs/`

## 1. 「stderr 契約の正本」はどのキーか

`script-brief-C20.json` のトップレベル `stderr` (1 個の文字列) が正本である。根拠:

1. 同 brief のトップレベルは `stdin` / `stdout` / `stderr` / `exit_codes` が並ぶ I/O 契約の節で、
   `stderr` の値だけが「1 行 1 件で先頭に診断コード」に続けて `<コード> <引数の型>` の
   書式一覧を列挙している。書式を宣言しているのはこのキーだけ。
2. 受入テストの正本参照がこのキーを名指ししている。
   `plugins/guide-doc-generator/tests/extract-handout-config.py/_harness.py:42` のコメントが
   `# 診断コード (script-brief-C20.json#stderr)` で、直下の 4 定数
   (`E_UNRECOVERABLE` / `W_HEURISTIC` / `E_ROUNDTRIP_DIFF` / `E_HTML_MALFORMED`) が
   このキーの列挙をそのまま写している。テストが写し取った先が正本である。

これ以外の箇所に現れる診断コードは説明文中の言及であって契約宣言ではない。とくに
`heuristic_fallback.class_map_completeness` / `recovery_limits` / `reporting` /
`never_guessed` / `algorithm` / `acceptance_checks` / `failure_modes` の各文は、
挙動を説明する散文の中でコード名に触れているにすぎない。

この区別が、単純な grep との食い違いを説明する。ファイル全文への grep では
`W-EXTRACT-CATALOG-DRIFT` が 1 件ヒットするが、その唯一の出現箇所は
`heuristic_fallback.class_map_completeness` の散文中であり、`stderr` 契約行には
無かった。`P05-x-13` の worker の報告 (「stderr 契約行に `W-EXTRACT-CATALOG-DRIFT`
自体が未記載」) が正しく、grep のヒット数と矛盾しない。

## 2. 乖離の実測

実装 `plugins/guide-doc-generator/scripts/extract-handout-config.py` が発火させ得るコードは
モジュール定数 (46-49 行) の 4 件 + roundtrip / malformed の 2 件:

| code | 実装での発火箇所 |
| --- | --- |
| `E-EXTRACT-UNRECOVERABLE` | `extractor.required_gaps` (1049 行) |
| `W-EXTRACT-HEURISTIC` | `extractor.heuristics` (1052 行) |
| `W-EXTRACT-OPTIONAL` | `extractor.optional_gaps` (1051 行) |
| `W-EXTRACT-CATALOG-DRIFT` | `self_check_catalog()` (264 / 266 行、起動時 Y-05) |
| `E-ROUNDTRIP-DIFF` | `--compare` の差分 (1061 行) |
| `E-HTML-MALFORMED` | `MalformedHtml` 捕捉 (1041 行) |

編集前の `stderr` 契約に載っていたのは 4 件のみで、**`W-EXTRACT-OPTIONAL` と
`W-EXTRACT-CATALOG-DRIFT` の 2 件が欠落**していた。起票時の想定 (欠落は
`W-EXTRACT-OPTIONAL` の 1 件) より 1 件多い。

## 3. 採った解

`stderr` の値だけを書き換え、欠けていた 2 件を書式つきで列挙へ加えた。あわせて
「この一覧が発火し得る診断コードの正本であり、下流 (C02 / C08) はここに載っている
コード名だけを分岐条件として参照する」ことと、E- / W- の exit code 上の扱いを明記した。

追加した書式は実装の出力文字列から採った (推測ではない)。

- `W-EXTRACT-OPTIONAL <JSON Pointer> <理由>` — 実装 1051 行
  `"%s %s %s" % (W_OPTIONAL, entry["pointer"], entry["reason"])`
- `W-EXTRACT-CATALOG-DRIFT <JSON Pointer> <照合表とカタログの過不足>` — 実装 264 / 266 行
  (`/parts <部品 ID> は照合表の鍵にあるがカタログに無い` / `... はカタログにあるが照合表に鍵が無い`)

severity と exit への影響も実装 (1094-1100 行) から確認した。

- `W-EXTRACT-OPTIONAL` / `W-EXTRACT-HEURISTIC`: 既定では exit 0 のまま。
  `--strict-fidelity` 指定時のみ exit 1 へ格上げ。
- `W-EXTRACT-CATALOG-DRIFT`: exit code に影響しない (起動時検査、抽出は続行)。

トップレベルキーの集合と順序は編集前後で完全一致 (26 キー)。他タスクが同ファイルへ
入れた `heuristic_fallback.class_map` の 18 行 (末尾が `TEXT`) /
`class_map_completeness` / `recovery_limits` は無変更。

## 4. 受入基準の実測

`acceptance_criterion`: 実装が発火させる診断コードの集合が `stderr` 契約の集合に包含されること。

```
impl     : E-EXTRACT-UNRECOVERABLE, W-EXTRACT-CATALOG-DRIFT, W-EXTRACT-HEURISTIC, W-EXTRACT-OPTIONAL
contract : E-EXTRACT-UNRECOVERABLE, E-HTML-MALFORMED, E-ROUNDTRIP-DIFF,
           W-EXTRACT-CATALOG-DRIFT, W-EXTRACT-HEURISTIC, W-EXTRACT-OPTIONAL
impl ⊆ contract : True
```

回帰なし。`tests/extract-handout-config.py` (152 tests) と `tests/run-handout-extract`
(46 tests) を編集前後で実行し、`FAIL:` / `ERROR:` 行の集合はいずれも空、差分なし。

## 5. grep 上の注意 (`E-EXTRACT-UN` / `W-EXTRACT-HE` の正体)

`grep -oE '\b[EW]-EXTRACT-[A-Z-]+'` を macOS の BSD grep でこのファイル (日本語を含む
UTF-8 の長行) へ掛けると `E-EXTRACT-UN` / `W-EXTRACT-HE` という途中で切れた一致が
余分に出る。**これはファイル内容ではなく grep 側の artifact** である。同じ正規表現から
`\b` を外すと消え、Python の `re.findall` でも 0 件。ファイル中にこれらの部分文字列は
実在しない。診断コードの棚卸しに `\b` 付き `grep -o` を使わないこと。

## 6. 本タスクで触れていない隣接事項

- `exit_codes["1"]` の文言は「`--strict-fidelity` 下での任意フィールドの復元不能」と
  書くだけでコード名 `W-EXTRACT-OPTIONAL` を挙げていない。`stderr` 以外の節であり
  本タスクでは触れていない。診断コード名の相互参照を揃えるなら別タスクが適切。
- `P05-x-21` が担当予定のマーカー語彙と chrome 境界の節には一切触れていない。
