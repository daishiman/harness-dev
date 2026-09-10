# C15 `build-icon-sprite.py` 受入テスト (P04-C15-01 で赤に固定)

本ディレクトリは **実装より先に判定基準を固定する** ためのテスト群である。P05 の実装が
テストを自分に都合よく書き換えられないよう、契約は全て次の正本から起こしてある。

| 正本 | ここから起こした内容 |
|---|---|
| `plugin-plans/guide-doc-generator/briefs/script-brief-C15.json` | argv / stdout / stderr / exit_codes / algorithm 1-13 / icon_set_source / acceptance_checks / failure_modes / write_scope / single_writer |
| `plugin-plans/guide-doc-generator/briefs/script-brief-C16.json` | detections **SC-05** (canonical_rules CR-EMOJI) / **SC-06** / **SC-07** |
| `plugin-plans/guide-doc-generator/briefs/script-brief-C11.json` | `html_attribute_contract` (`data-hb-kind` の語彙正本) / algorithm 9 (symbols_svg を無加工で埋め込む) / `module_api` 相当の `build_sprite(config, icon_set)` |
| `plugin-plans/guide-doc-generator/briefs/RESOLUTION-P03.md` | Y-03 (絵文字判定の正本は CR-EMOJI。ブロック denylist は廃止) / 正本一覧 |

## 実行

```bash
python3 -m unittest discover -s plugins/guide-doc-generator/tests/build-icon-sprite.py -p 'test_*.py'
```

Python 3.10+ の標準ライブラリのみ (`unittest`)。repo ルートから実行する。

**P04 時点では全 123 件が赤 (failures) が正しい状態。** 赤の内容は import 例外ではなく
「実装が未存在」という診断可能なアサーション失敗になっている (`_harness.require_script`)。
`setUpClass` で例外を投げる構造も使っていない。

ブリーフ準拠の参照実装を scratchpad へ置いて全 123 件が緑になることを確認済みで、
達成不能な基準は含まれていない (参照実装は repo へ置いていない)。

## C15 と C16 の関係 (テスト設計上いちばん重要な点)

C11 は C15 が返した `symbols_svg` を **無加工で** `<body>` 直後へ置く
(`script-brief-C11.json` algorithm 9)。したがって **C16 が生成 HTML に課す SC-06 / SC-07 は、
そのまま C15 の出力へ課される**。C16 の実装有無に依存させないため、SC-05 / SC-06 / SC-07 の
判定は C16 ブリーフの detections 本文から `_harness` 側へ写し
(`find_emoji` / `assert_sc06_style` / `assert_sc07_pairing`)、C15 の出力へ掛けている。

- **SC-06** のスコープは `data-hb-kind="icon"`。`mascot` / `decor` は様式検査の対象外。
  ただし `data-hb-kind` を **持たない** `<svg>` / `<symbol>` は「分類不能」として違反に計上される
  ため、sprite の外枠 `<svg width="0" height="0">` にも属性が要る (下記 gaps G-01)。
- **SC-07** は「定義 D と参照 U の 1:1」。C15 の出力に `<use>` は含まれない (参照は C11 が
  `use_href` から書く) ので、C15 側で保証すべきは **symbol 定義集合 == 参照表 (`used`) の
  `symbol_id` 集合** である。`test_c16_contract.py` では C11 の埋め込みを最小構成で再現した
  HTML を組み立て、D と U が実際に 1:1 になることまで見ている。
- **SC-05** は二層規則。**Unicode ブロック丸ごとの denylist を実装すると
  `NonEmojiSymbolsPassTest` が落ちる** ようにしてある (下記 gaps G-03)。

## ファイルと契約 id の対応表

| ファイル | 契約 id | 赤で固定した内容 |
|---|---|---|
| `_harness.py` | (共通) | パス解決・`require_script`・アイコンセット正本と構成データの組み立て・SVG のタグ収集 (`html.parser`)・**CR-EMOJI / SC-06 / SC-07 の判定実装**・一時 plugin ツリーの生成・`tree_snapshot`。テストではない |
| `test_argv_and_exit_codes.py` | argv / stdin / stdout / exit_codes / algorithm 1・12 / **AC-C15-6** | `--config` 必須・未知 flag・位置引数 → exit 2。`--format` の enum が 3 語で閉じている (`Both` `json` 空 は exit 2)・未指定の既定が `both`。stdin を読まない。`--format=symbols` は raw SVG (JSON ではない)・`manifest` は `used` のみで `symbols_svg` を含まない。`--config` / `--icon-set` の不在・ディレクトリ指定・JSON 構文エラー → exit 2 で stdout を汚さない。参照 0 件 → exit 0 / `symbols_svg` 空文字列 / `used` 空配列 / **空の `<defs>` すら出さない**・`unused_in_set` は正本定義順 |
| `test_used_icon_extraction.py` | **AC-C15-1** (C11) / algorithm 5・7・9・10・11 | 3 参照で symbol ちょうど 3 件・正本の他 38 語が 1 件も混入しない。走査キーは宣言された 7 種すべて (`nav.icon` / `hero.goal_chips[].icon` / `sections[].icon` / `blocks[].icon` / `items` / `cards` / `tabs`)。**本文中の語彙同名文字列や `icon_hint` のような別キーは拾わない** (ヒューリスティック全文検索の禁止)。`ref_count` / `ref_paths` がキーパス形式 (`sections[0].blocks[0].items[0].icon`) かつ入力順の深さ優先。`paths` の順序保存・`title` は持つものだけに出る |
| `test_icon_style_sc06.py` | **AC-C15-2** (C10) / **SC-06** / algorithm 4・9 / failure_modes | 全 symbol が `viewBox="0 0 24 24"` / `fill="none"` / `stroke="currentColor"` / `stroke-linecap="round"` / `stroke-linejoin="round"`。**様式は正本側の同名フィールドで上書きされない** (正本が `viewBox="0 0 20 20"` を持っていても出力へ漏れない)。`stroke_width` だけが正本由来。全 symbol が `data-hb-kind="icon"`・外枠 `<svg>` も分類済みで **値は `icon` 以外** (外枠は viewBox を持たないため icon 分類だと SC-06 で落ちる)。外枠は `width=0 height=0 aria-hidden style=position:absolute` + `<defs>` 1 個。属性順 (id → viewBox → fill → stroke → stroke-width → linecap → linejoin) を部分列として固定。`stroke_width` 範囲外は **strict で exit 1 / 非 strict は warning + exit 0**、境界 2.2 と 2.6 は両方通り 2.1 / 2.7 は落ちる |
| `test_symbol_use_sc07.py` | **SC-07** / algorithm 8 / failure_modes | 定義集合と参照表が順序込みで 1:1・未使用 symbol / 未定義参照 / 重複が構造的に発生しない・同名を 6 回参照しても symbol は 1 件で `ref_count=6`。id は `hbic-{name}` で連番もハッシュも使わない (C20 の逆抽出のため)。正本内の name 重複 → exit 1 / stderr に重複名と配列 index (**未使用のアイコンでも落とす**) |
| `test_emoji_policy_sc05.py` | **AC-C15-3** / **SC-05 (CR-EMOJI)** / algorithm 4・13 / failure_modes | stdout / stderr / `symbols_svg` / exit 1 の診断すべてで層 1 絵文字 0 件。正本の `title` に 👉 ✅ 国旗 ✨ / 層 2 + VS16 (`⚙️`) / キーキャップ (`1️⃣`) → exit 1 + コードポイント併記。**回帰: ★ ☆ ✔ © ♪ ■ ▶ → と日本語約物は通す** (`✔` U+2714 と `→` U+2192 は旧ブロック denylist に入る値なので、denylist 実装だとここで落ちる)。`html.escape(quote=True)` によるエスケープ |
| `test_determinism.py` | **AC-C15-4** (C29) / algorithm 7・13 | セクション順だけ入れ替えた 2 入力で `symbols_svg` の sha256 が一致・**並びは正本 icons 配列の定義順への射影** (参照順でも辞書順でもない)・参照表の順も同じ。2 回実行のバイト一致・`PYTHONHASHSEED` 非依存・cwd 非依存・3 つの `--format` すべてで決定論。`ensure_ascii=False` / `indent=2` / `sort_keys=False` (キー順は stdout 契約の宣言順) / LF のみ / `symbols_svg` は 2 スペースインデントでタブなし。絶対パスと時刻系フィールドを出さない |
| `test_input_violations.py` | **AC-C15-5** / algorithm 4・6 / failure_modes / write_scope | 未定義アイコン → exit 1 で stderr に名前・参照キーパス・`difflib` の近似候補 (`checkk` → `check`)・**既定アイコンへ黙って落とす経路が無い** (exit 1 時に sprite を出さない)・未定義が複数あれば全件報告。正本の name 字種違反 (`Check` `check_mark` `チェック` `check mark` `check.svg` 空文字) → exit 1、`arrow-right` `step-1` `x9` は通る。`paths` 空配列 → exit 1。**正本の検査は走査より前に効く** (未使用アイコンの違反も落とす)。成功時の stderr に正本の読み込み経路が出る。`icon` の型不正・トップレベル配列の構成データを黙って読み飛ばさない。**write_scope=none**: 成功・失敗いずれでもディレクトリが 1 バイトも変わらず、正本を書き戻さない |
| `test_plugin_resolution.py` | **AC-C15-7** / algorithm 2 | 一時 plugin ツリー (`.claude-plugin/plugin.json` + `assets/icons/` + `scripts/`) を tempdir に作り、環境変数なしで `__file__` 相対の自己解決が効いて exit 0。`HB_ROOT` が 1 段目・`CLAUDE_PLUGIN_ROOT` が 2 段目として採られる (別 `set_version` を置いて採用側を判別)。`--icon-set` 明示指定が解決に優先する。1 段目が不在でも打ち切らず次段へ落ちる。4 段すべて外れたら **exit 1 ではなく exit 2** で、stderr に `HB_ROOT` / `CLAUDE_PLUGIN_ROOT` / `plugin.json` / `__file__` の 4 経路が列挙される。実装に絶対パスの直書きが無い |
| `test_stdlib_and_boundary.py` | **AC-C15-9** (C27) / **AC-C15-10** / single_writer / write_scope | 全 import が `sys.stdlib_module_names` 内・`yaml` は文字列としても 0 件・宣言集合のうち `json` `sys` `argparse` `difflib` が実際に使われる・`subprocess` / 通信系 0 件・`random` / `time` / `datetime` / `glob` など非決定論モジュール 0 件。**語彙 41 語の文字列リテラルが 0 件**で、正本へ足した未知語 (`brand-new-icon`) が script 無改修で認識され、正本から消せば未定義になる。`build_sprite(config, icon_set)` と `main()` の二層構造と `__main__` ガード。境界: HTML 文書の生成をしない・`<use>` を生成しない (C11 の責務)・書き込みモードの `open` / `write_text` / `mkdir` / `shutil` を持たない |
| `test_c16_contract.py` | **AC-C15-8** / SC-05 / SC-06 / SC-07 / CR-EXT | C11 の埋め込みを最小構成で再現した HTML に対し、SC-06 (分類漏れなし・様式適合)・SC-07 (D と U が過不足なく一致し重複なし)・SC-05 (絵文字 0) が成立する。sprite に外部参照スキームが無い (CR-EXT)。`use_href` は fragment 形のみで外部ファイル参照形にしない。**参照 0 件の空 sprite でも C16 の検査を通る**。様式が正しい入力では `--strict-style` の有無で stdout が変わらない (C01 / C16 が常に strict で呼ぶ経路の同値性) |

## 検査の作り方 (3 つの原則)

1. **実 plugin ツリーへ 1 バイトも書かない。** アイコンセット正本も構成データも一時 plugin ツリーも
   `tempfile` の下に作る。C15 自身が `write_scope=none` なので、テスト側も同じ制約で書いた。
   read-only 契約は前後の `tree_snapshot` 比較で検査している。
2. **語彙と閾値をテストへ直書きしない。** アイコン名は `_harness.VOCABULARY` に 1 箇所だけ置き
   (AC-C15-10 の grep 対象そのもの)、境界値は `STROKE_WIDTH_MIN/MAX` から計算する。
   決定論テストでは語彙外の名前 (`zeta` / `alpha` / `mid`) をあえて使い、
   「並び順が辞書順でも参照順でもなく正本定義順である」ことを見分けられるようにした。
3. **C16 の判定をテスト側に写して掛ける。** C16 の実装完了を待たずに producer↔consumer 契約を
   固定するため。C16 側が実装されたら AC-C16-* が同じ性質を検査側から二重に確認する。

## gaps (ブリーフ間で食い違っており、判断してテストへ落とした点)

以下は **P05 の実装者ではなく plan 側で決着させるべき** 事項である。テストは各項目の
「採用した解釈」で赤を固定してあるので、plan 側の決着が別解になった場合はテストの
該当箇所を直す必要がある。

| id | 何が食い違っているか | なぜ問題か | 採用した解釈 |
|---|---|---|---|
| **G-01** | `script-brief-C15.json` algorithm 9 が定める symbol の属性列に **`data-hb-kind` が無い**。一方 C16 SC-06 と C11 `html_attribute_contract` は「全 svg/symbol に必ず付ける。未分類は違反」と定める | C11 は `symbols_svg` を無加工で埋め込む契約 (C11 algorithm 9) なので、C15 が付けなければ生成 HTML の全 symbol が SC-06 の「分類不能」で FAIL する。C16 ブリーフの `false_positive_risk` も「C11/C15 の brief 側と属性名を一致させる必要がある」と書いており、C15 側が未追随のまま残っている | 各 `<symbol>` に `data-hb-kind="icon"` を要求する。**外枠 `<svg>` にも属性を要求するが、値は `icon` 以外** (`mascot` / `decor` / `figure` のいずれか) とした。外枠は `viewBox` を持たないため `icon` 分類にすると SC-06 の様式検査で自分自身が落ちるため。外枠に与えるべき具体値は plan で確定させたい |
| **G-02** | 同 algorithm 9 は「属性順は上記で固定する」と書くが、G-01 で必要になる `data-hb-kind` の挿入位置を定めていない | 属性順が決まらないと C29 のバイト一致再現性の基準が実装者ごとにぶれる | ブリーフが列挙する 7 属性が **その相対順で現れること** を部分列として固定し、`data-hb-kind` の位置は問わない。plan で位置を確定させれば厳密順へ強められる |
| **G-03** | `script-brief-C15.json` algorithm 4 は絵文字判定を **ブロック denylist** (`U+1F300-1FAFF` / `U+2600-27BF` / `U+2190-21FF` / `U+FE0F`) で書いている。しかし絵文字判定の単一正本は C16 の **CR-EMOJI (二層規則)** であり、`RESOLUTION-P03.md` Y-03 が「ブロック丸ごとの denylist は用いない」と確定させている | C15 の記述どおりに実装すると、`✔` (U+2714) や `→` (U+2192) を含む `title` が exit 1 になる。CR-EMOJI はこれらを明示的に通すので、C15 だけが偽陽性を出す構造になる (Y-03 が C10 hook で解消したのと同じ欠陥) | **CR-EMOJI を採用**した。`✔` `→` `★` `©` `♪` `■` `▶` と日本語約物は通し、層 1 と「層 2 + VS16」だけを落とす。C15 ブリーフ algorithm 4 の denylist 記述は CR-EMOJI への委譲記述へ書き換えるべき |
| **G-04** | `assets/icons/icon-set.json` の **writer が宣言されていない**。plan 全体で当ファイルに言及するのは C15 ブリーフだけで、`component-inventory.json` にも `script-brief-C19.json` の `bundle_writers` にも現れない | 正本が存在しないと C15 は `--icon-set` 明示指定でしか動かず、AC-C15-7 の自己解決経路が実運用で成立しない (P03 Y-04 の「存在検査だけがあって書き手がいない」と同型) | テストは正本を **tempdir に作って渡す** 形にし、実 plugin ツリーの `assets/icons/icon-set.json` に依存しない。誰が同梱するかは plan で決着させたい |
| **G-05** | algorithm 2 の 3 段目「候補直下の `.claude-plugin/plugin.json` を読み name 照合」の **「候補」が何を指すか** が定義されていない (cwd か、その祖先か、既定の探索列か) | 実装者ごとに探索範囲が変わり、AC-C15-7 の「見つからない場合のみ exit 2」の境界が定まらない | 3 段目の探索範囲そのものは検査していない。代わりに **「4 段すべて外れたら exit 2 で 4 経路が stderr に列挙される」** ことと **「1 段目が不在でも打ち切らず次段へ落ちる」** ことだけを固定した |
| **G-06** | `build_sprite(config, icon_set)` の **戻り値 `SpriteResult` の形** が C11 ブリーフに型名としてしか現れない | C11 が読むフィールド名が決まらない | CLI の stdout 契約 (`symbols_svg` / `used` / `unused_in_set` / `set_version`) と同一の形とみなし、`build_sprite` については **存在と引数名だけ**を固定した。戻り値の形は CLI 側の検査で間接的に固定される |
