# C10 `guard-handout-external-ref` 受入テスト (P04-C10-01)

実装 (`plugins/guide-doc-generator/hooks/guard-handout-external-ref.py`) より先に
判定基準を確定させ、赤で固定したテスト群。**P05 の実装側がここを自分に都合よく
書き換えて緑にすることは許されない**。契約を変えるときは先にブリーフを直す。

契約の正本は 2 つある。

| 何の契約か | 正本 |
| --- | --- |
| 適用範囲・入出力・exit code・打ち切り | `plugin-plans/guide-doc-generator/briefs/hook-brief-C10.json` |
| 外部参照 (CR-EXT) と絵文字 (CR-EMOJI) の判定規則 | `plugin-plans/guide-doc-generator/briefs/script-brief-C16.json#canonical_rules` |

**C10 は判定規則の独自定義を持たない** (P03 Y-02 / Y-03)。C16 の
`module_api.scan_external_references` / `scan_emoji` を再実行して結果を受け取り、
対象ファイルの同定と exit code への写像だけを行う。したがってこのテストにも
「何が外部参照か」「どのコードポイントが絵文字か」の列挙は置いていない。
期待値は C16 の戻り値そのものであり、`test_parity_with_c16.py` が実行時に
突き合わせる。規則が将来 C16 側で変わっても、このテストは規則の複製として腐らない。

## 実行

repo ルートから:

```bash
python3 -m unittest discover -s plugins/guide-doc-generator/tests/guard-handout-external-ref -p 'test_*.py'
```

Python 3.10+ の標準ライブラリのみ。現状は **196 tests / 196 failures / 0 errors (赤)**。
すべて「未実装: … が存在しない」で落ちる (errors ではなく failures として落ちる形に
してある)。実装が現れた時点で個々の assert が本来の契約を検査しはじめる。

## ファイル構成

| ファイル | 件数 | 役割 |
| --- | ---: | --- |
| `hb_c10.py` | — | 共通ハーネス (テストではない)。stdin 起動・stdout/stderr の観測・fixture・断言ヘルパ |
| `test_applies_to.py` | 43 | `applies_to.rule` の 5 条件 |
| `test_payload_contract.py` | 19 | `input_contract` と `fail_closed_scope` (a)(b) |
| `test_detection_d1_external.py` | 16 | D1 の block / pass と stderr 書式 |
| `test_detection_d2_emoji.py` | 24 | D2 の block と **旧 denylist 撤去の回帰** |
| `test_abort_and_budget.py` | 9 | `output_contract.abort` と `fail_closed_scope` (c) |
| `test_rule_delegation.py` | 15 | 規則の非複製・stdlib only・C16 解決不能時の soft fail |
| `test_parity_with_c16.py` | 62 | **AC-C16-11 と対をなす判定一致** |
| `test_no_side_effects.py` | 8 | write-scope none・冪等・登録面の一本化 |

素通し系のテストでは、入力に**必ず違反を含ませている**。清潔な HTML を渡すと
exit0 の理由が「対象外だから」か「違反が無いから」か切り分けられないため。

## 契約 id とテストの対応

### applies_to.rule (5 条件・上から順に評価し外れた時点で exit0)

| 条件 | 固定した境界 | テスト |
| --- | --- | --- |
| (1) tool_name | Write / Edit のみ。Bash / Read / Grep / **MultiEdit** / 小文字 `write` / 欠落 は素通し | `TestCondition1ToolName` |
| (2) パス取得 | `file_path` > `filePath` > `path` の順に最初の非空 str。優先順位・空文字・非 str・`tool_input` 欠落 | `TestCondition2PathExtraction` |
| (3) 拡張子 | `.html` 大小文字無視。`.htm` / `.md` / `.py` / `.json` / 拡張子なし / `.html.bak` は素通し | `TestCondition3Extension` |
| (4) マーカー | 同一ディレクトリの `handout-config.json`。親のみ・似た名前・deck の `index.html` は素通し | `TestCondition4ConfigMarker` |
| (5) ディレクトリ名 | `^\d{4}-\d{2}-\d{2}-`。ゼロ埋めなし・接頭でない・末尾ハイフンなしは素通し。**種別語彙は一切見ない** | `TestCondition5DirectoryName` |
| out_of_scope_examples | ブリーフの列挙をそのまま入力にする | `TestOutOfScopeExamples` |

### input_contract / fail_closed_scope

| 契約 | 固定した内容 | テスト |
| --- | --- | --- |
| stdin | 空 / 空白 / 壊れた JSON / 配列 / 文字列 / 数値 / null / `tool_input` が非 dict → 全て exit0。traceback を漏らさない | `TestMalformedStdin` |
| ペイロード形 | `tool_response` つき実物形・未知キー・cwd 相対パス | `TestPayloadShape` |
| 本文の出所 | **tool_input ではなく書込先の実ファイル**を読む (`content` / `new_string` が汚れていてもディスクが清潔なら素通し、逆も) | `TestBodyComesFromDisk` |
| (a) 判定不能 | パス取得不能・ペイロード不正 → exit0 | `TestCondition2PathExtraction` / `TestMalformedStdin` |
| (b) 読込不能 | 削除済み・ディレクトリ・権限不足・UTF-8 デコード不能 → 非ゼロ終了しない | `TestUnreadableTarget` |
| (c) 予算超過 | 8 MiB 超 → exit0 + systemMessage。閾値未満は完走して判定する | `TestOversizedFileAborts` / `TestUnderLimitIsInspected` |

### detection_rules

| 契約 | 固定した内容 | テスト |
| --- | --- | --- |
| D1-external-url-attr | CDN script / Google Fonts link / protocol-relative / 外部 a@href / `@import` で exit2 | `TestD1Block` |
| D1 (境界) | **text node の URL は違反にしない**・data URI・ページ内アンカー・名前空間 URI・mailto/tel は素通し | `TestD1Pass` |
| D2-emoji | 層 1 単独 / 国旗 / 層 2 + VS16 / キーキャップ / 属性値内 / 数値文字参照 で exit2、stderr に `U+XXXX` | `TestD2Block` |
| D2 (回帰) | **★ ☆ ✔ © ® ™ ♪ ■ ▶ ⚙ (VS16 なし) を殺さない**。約物一式・VS1-15・孤立 ZWJ も pass | `TestD2SymbolRegression` |

`TestD2SymbolRegression` が落ちるということは、hook が CR-EMOJI ではなく
Unicode ブロックの denylist を持ってしまったということである (P03 Y-03 の再発)。

### output_contract

| 契約 | 固定した内容 | テスト |
| --- | --- | --- |
| pass | exit 0 / stdout・stderr とも無出力 | `assertPassSilently` (全ファイル) |
| block | exit 2 / stderr 先頭が `[guard-handout-external-ref] BLOCKED:` / 違反ごとに 1 行 / 行番号 / **抜粋 120 文字以内** / stdout は空 | `TestD1Block` |
| abort | exit 0 / stdout に systemMessage JSON が **1 行だけ** / BLOCKED 見出しを出さない / 合格 (無出力) と観測上区別できる | `TestOversizedFileAborts` / `TestAbortIsDistinguishableFromPass` |

### rule_delegation (P03 Y-02 / Y-03 の再発防止)

| 契約 | 固定した内容 | テスト |
| --- | --- | --- |
| 規則の非複製 | hook 本体 (コメント・docstring を除いた実行部) にスキーム文字列・絵文字コードポイント・URL 属性名の列挙が 0 件 | `TestNoRuleDuplication` |
| 一本化 | `scan_external_references` / `scan_emoji` / `spec_from_file_location` / `verify-handout-selfcontained.py` を参照している | `TestNoRuleDuplication` |
| C42 の非重複 | 用途種別 slug 8 語と日本語語彙が 0 件。`handout-purposes.json` も読まない | `TestNoPurposeVocabulary` |
| C27 | 標準ライブラリのみ import (`ast` で解析し `sys.stdlib_module_names` と照合) | `TestStdlibOnly` |
| if_import_fails | C16 が同居しない偽 plugin root へ hook を複製して起動 → exit0 + systemMessage・traceback なし | `TestImportFailureIsSoft` |
| 実行時可搬性 | HB_ROOT / CLAUDE_PLUGIN_ROOT 未設定でも `__file__` 相対で自己解決する。HB_ROOT 指定でも解決する | `TestSelfResolution` |
| **invariant** | 20 fixture で C10 の block 有無と C16 の `scan_*` 戻り値が全件一致し、絵文字違反のコードポイント集合も完全一致 | `test_parity_with_c16.py` (AC-C16-11 と対) |

### その他

| 契約 | 固定した内容 | テスト |
| --- | --- | --- |
| write-scope: none | exit2 でもファイルを消さず書き換えず、新規ファイルも作らない | `TestWriteScopeNone` |
| 決定論 | 同一入力を 2 回実行して (rc, stdout, stderr) がバイト一致 | `TestIdempotent` |
| 登録面の一本化 | 同梱 `hooks/hooks.json` と `.claude-plugin/plugin.json#hooks` に C10 の登録が無い (二重発火の防止) | `TestSingleRegistrationSurface` |

## 意図的に検査していないこと

- **PostToolUse の上位停止セマンティクス**。検証対象は exit code と stderr の 2 点のみ
  (`open_questions` の 2 番目に従い、Claude 側の停止挙動には依存しない)。
- **MultiEdit の検査**。`matcher` が `Write|Edit` である以上、MultiEdit は素通しが正しい挙動として
  固定してある。変えるなら先に `component-inventory.json` の matcher を変えること
  (`open_questions` の 1 番目)。
- **3 秒の実行時間予算**。閾値が実測由来でない仮置きであり (`open_questions` の 3 番目)、
  時間依存のテストは環境で不安定になるため、打ち切り契約はサイズ側 (8 MiB) だけで固定した。
  時間側の打ち切りも同じ systemMessage 経路を通る契約なので、経路自体は
  `TestOversizedFileAborts` が押さえている。
- **C16 側の detection 網羅** (SC-01..SC-09 の個別挙動)。C10 の責務ではない。
  `plugins/guide-doc-generator/tests/verify-handout-selfcontained.py/` が持つ。
