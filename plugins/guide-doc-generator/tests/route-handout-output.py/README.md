# C19 `route-handout-output.py` 受入テスト (P04-C19-01 で赤に固定)

本ディレクトリは **実装より先に判定基準を固定する** ためのテスト群である。契約は全て
`plugin-plans/guide-doc-generator/briefs/script-brief-C19.json` の
`argv` / `stdout` / `stderr` / `exit_codes` / `write_scope` / `single_writer` /
`bundle_writers` / `algorithm` / `naming_rule` / `acceptance_checks` / `failure_modes` と、
`briefs/RESOLUTION-P03.md` の **Y-04** (同梱物の writer 割り当て) から起こしてある。
P05 の実装がテストを自分に都合よく書き換えられないよう、判定基準はここで確定させる。

## 実行

```bash
python3 -m unittest discover -s plugins/guide-doc-generator/tests/route-handout-output.py -p 'test_*.py'
```

Python 3.10+ の標準ライブラリのみ。repo ルートから実行する。

**P04 時点では全 113 件が赤で、内訳は failures のみ (errors 0 / ok 0)。** 赤の内容は
import 例外ではなく「実装が未存在」「依存成果物が未存在」という診断可能なアサーション失敗
(`_harness.require_script` / `_harness.require_file`) になっている。

## 検査の作り方 (3 つの原則)

1. **用途種別の語彙をテストへ列挙しない。** `doc_type` も `<種別>` の期待値も語彙正本
   `config/handout-purposes.json` (owner: C23) を読んで機械導出する
   (`_harness.any_doc_type` / `dir_token_of` / `unknown_doc_type` / `name_prefix`)。
   AC-C19-03 が script へ「語彙リテラル 0 件」を課している以上、その判定基準を持つ側が
   語彙を焼き付けたら基準が壊れる。
2. **実ファイルシステムへの書き込みは `tempfile.TemporaryDirectory` 内に閉じる。**
   既定出力先 (`config/handout-output.json` の `default_out_dir`) を使う経路は、
   `scripts/` と `config/` を tmp へ複製した fixture ツリー (`_harness.make_fixture_tree`)
   越しにしか実行しない。ユーザーの実出力先へは 1 バイトも書かない。
3. **同梱 4 点の固定名と writer は 1 箇所にだけ置く。** `_harness.BUNDLE_WRITERS` が
   `bundle_writers` (Y-04) の写しであり、各テストはそこから回す。stdout の各 present/absent
   行に writer id (`C11` / `C19` / `C19` / `C01`) が注記されていることを
   `test_bundle_presence.py::test_stdout_annotates_the_writer_of_each_item` が要求するので、
   **どの component が書いたものを検査しているかがテストからも生成物からも読める**。

## 契約 id の付け方

ブリーフの `acceptance_checks` は無番号の 20 件なので、**記載順に `AC-C19-01` 〜 `AC-C19-20`**
と番号を振って参照する。番号と原文の対応は下表のとおり。

| id | acceptance_checks の要旨 | 主に固定したファイル |
|---|---|---|
| AC-C19-01 | 解決 3 段と、3 段いずれも欠けたときだけ exit 2 | `test_out_dir_resolution.py` |
| AC-C19-02 | ソースに ObsidianMemo 等の環境固有絶対パス 0 件 | `test_source_invariants.py` |
| AC-C19-03 | ソースに用途語彙リテラル 0 件 + C23 `--audit-duplication` が exit 0 | `test_source_invariants.py` / `test_cross_component.py` |
| AC-C19-04 | ソースに現在時刻取得 0 件 | `test_source_invariants.py` |
| AC-C19-05 | 同一構成データ 2 回でディレクトリ名がバイト一致し連番を作らない | `test_determinism_and_collision.py` |
| AC-C19-06 | `date=2026/08/17` → 先頭が `2026-08-17-`、C18 の日付整合が exit 0 | `test_naming_and_slug.py` / `test_cross_component.py` |
| AC-C19-07 | ソースに `^\d{4}-\d{2}-\d{2}$` の date 検証 0 件 | `test_source_invariants.py` |
| AC-C19-08 | 語彙外 `doc_type` は exit 1 + stderr 1 行。`purpose` は照合対象外 | `test_vocabulary_boundary.py` |
| AC-C19-09 | C23 不在で exit 2 (語彙を推測して作らない) | `test_vocabulary_boundary.py` |
| AC-C19-10 | subprocess 0 件、C23 到達は importlib の 1 経路だけ | `test_vocabulary_boundary.py` |
| AC-C19-11 | 日本語のみの title でも slug が空にならず決定論 | `test_naming_and_slug.py` |
| AC-C19-12 | `../` や `/` を含む slug は exit 2、ルート外に作らない | `test_out_dir_resolution.py` |
| AC-C19-13 | 同梱 4 点のいずれかを欠くと `--check-only` が exit 1 + stderr 列挙 | `test_bundle_presence.py` |
| AC-C19-14 | `--check-only` 実行後にディレクトリが新規作成されない | `test_bundle_presence.py` |
| AC-C19-15 | `--assets-src` の 2 階層が相対構造ごと複製され、複製元が無変更 | `test_assets_and_config_placement.py` |
| AC-C19-16 | `--assets-src` 2 回目で内容が変化しない (冪等) | `test_assets_and_config_placement.py` |
| AC-C19-17 | `--place-config` で `handout-config.json` が `--config` とバイト一致 | `test_assets_and_config_placement.py` |
| AC-C19-18 | `--place-config` と `--check-only` の同時指定は exit 2 | `test_argv_and_exit_codes.py` |
| AC-C19-19 | 作成直後は exit 0、同ディレクトリの `--check-only` は exit 1 (順序矛盾を作らない) | `test_bundle_presence.py` |
| AC-C19-20 | C11 / C01 / C13 と突き合わせ、配置の実装が C19 にしかない | `test_cross_component.py` |

`algorithm` 由来の契約は本文中に `algorithm N` として docstring へ書いてある
(2 = 正規化ゲート / 3 = 日付の純変換 / 4 = 語彙照合 / 5 = slug / 6 = 解決 4 段 /
7 = 脱出検査 / 8 = 衝突解決 / 9 = mkdir と来歴 / 9b = assets 複製 / 9c = config 配置 /
10 = 同梱 4 点の存在検査と writer 注記 / 11 = `--json-report`)。

## ファイルと固定した内容

| ファイル | 主な契約 id | 固定した内容 |
|---|---|---|
| `_harness.py` | (共通) | パス解決・語彙正本からの機械導出・正規化済み構成データ fixture・fixture ツリー生成・stdout / `--json-report` の緩い解釈。テストではない |
| `test_argv_and_exit_codes.py` | AC-C19-18 / exit_codes 2 | `--config` 必須・未知引数 / 読めない config / 非 JSON → exit 2・正規化マーカー (`provenance.normalized_by`) 欠落 → exit 2・`date` / `doc_type` 欠落 → exit 2・`yyyy-mm-dd` や `2026/8/17` は非受理・stdin を読まない・`--place-config` + `--check-only` → exit 2 かつ無書込・`--json-report` は指定 1 ファイルのみ |
| `test_out_dir_resolution.py` | AC-C19-01 / 12 | `--out-dir` > `HB_OUT_DIR` > `default_out_dir` の優先順・`~` と環境変数の展開・3 段欠落 / 空値 → exit 2・解決段が stdout と `--json-report` の双方に記録される・`../` / `/` / 絶対パス slug → exit 2 で外に作らない・symlink ルートでも realpath 配下・ルート解決不能 → exit 2 |
| `test_naming_and_slug.py` | AC-C19-06 / 11 | `<date>-<dir_token>-<slug>` の 3 セグメント・日付は `date.replace('/','-')` の純変換で構成データに追従・`<種別>` は語彙正本の `dir_token` (全語彙で回す)・明示 slug は無加工採用・日本語 title でも非空かつ決定論・禁止文字 / 連続ハイフン / 前後のハイフンとドットの除去・40 文字切り・NFKC + 小文字化・空になったときだけ `topic-<hash8>`・`assets/` と `.handout-route.json` の生成 |
| `test_vocabulary_boundary.py` | AC-C19-08 / 09 / 10 | 語彙外 `doc_type` → exit 1 で stderr 1 行かつ無作成・alias を `<種別>` に使わない・`purpose` は照合せず命名にも漏れない・C23 不在 / 壊れた C23 / カタログ不在 → exit 2 かつ無作成・カタログの `dir_token` 変更が命名へ伝播する (語彙が正本にしかない証明)・ソースに subprocess 0 件で `spec_from_file_location` は 1 回だけ |
| `test_bundle_presence.py` | AC-C19-13 / 14 / 19 | 作成直後は `handout.html` / `README.md` が absent でも exit 0・stdout の 4 行に present/absent と writer id・`--place-config` 無しなら `handout-config.json` は absent・`--check-only` は無書込で、揃えば exit 0 / 1 点欠けるごとに exit 1 + 列挙・複数欠落を一度に列挙・同ディレクトリで通常 exit 0 / 検査 exit 1・既存ファイルを消さない・4 点以外の余剰は判定に影響しない・`assets` がファイルなら exit 1・`index.html` は本体を満たさない (hook 誤発火の回避) |
| `test_assets_and_config_placement.py` | AC-C19-15 / 16 / 17 | 2 階層の相対構造ごと複製・複製元無変更・冪等・内容差分は上書き・未指定なら空 `assets/`・複製元不在 / ファイル → exit 2・`assets/` の外へ出る symlink (ファイル / ディレクトリ) は辿らず exit 2・バイナリを加工しない・`handout-config.json` は固定名でバイト一致 (CRLF 混じりでもそのまま)・既定は配置しない・冪等・`--config` の隣へ書かない・出力先の直下エントリは 3 点だけ |
| `test_determinism_and_collision.py` | AC-C19-05 / collision_rule | 2 回実行で同名再利用かつ stdout バイト一致・命名がルートに依存しない・sha256 不一致は `-2`・既存を破壊しない・来歴消失は連番へ倒す・最小未使用連番・99 超で exit 1 かつ無作成・来歴に config の sha256・`--check-only` は衝突解決しない |
| `test_source_invariants.py` | AC-C19-02 / 03 / 04 / 07 / C27 | 環境固有絶対パス 0 件・語彙 slug / dir_token / alias のリテラル 0 件・現在時刻 API と `datetime` / `time` の import 0 件・`\d{4}-\d{2}-\d{2}` の検証 0 件かつ `\d{4}/\d{2}/\d{2}` は存在・import が全て stdlib・ネットワーク API 0 件 |
| `test_cross_component.py` | AC-C19-20 / AC-C19-03 後半 / AC-C19-06 後半 | C13 に配置実装が無い・C11 が `handout-config.json` を書かない・C01 が `--place-config` / `--assets-src` を C19 へ渡す・日付派生を他 component が持たない・C23 `--audit-duplication` が exit 0・C19 が作った名前を C18 が日付整合違反にしない |

## P05 が満たすべき成果物 (このテストが要求するもの)

- `plugins/guide-doc-generator/scripts/route-handout-output.py` (C19)
- `plugins/guide-doc-generator/config/handout-output.json` (既定出力先の宣言データ。`default_out_dir` キー)
- `plugins/guide-doc-generator/config/handout-purposes.json` と
  `plugins/guide-doc-generator/scripts/resolve-handout-preset.py` (C23。語彙の単一正本)
- `test_cross_component.py` のみ追加で C11 `render-handout.py` / C13 `embed-assets.py` /
  C01 `skills/run-handout-build/SKILL.md` / C18 `verify-handout-language.py` に依存する。
  writer 一意性と単一正本の性質上、C19 単体では緑にできない意図した結合である。

## テストを書く際に判断した点 (ブリーフに明示が無い箇所)

- **正規化マーカーの具体名**。C19 のブリーフは「`normalized: true` 相当のフィールド」としか
  書いていない。正本である C12 の `normalize_algorithm` が
  `provenance.normalized_by = 'validate-handout-config.py'` を付与するので、fixture は
  これを載せ、未正規化は `provenance` 自体の欠落として表現した (どの実装でも exit 2 になる形)。
- **stdout の行書式**。ブリーフは「絶対パス 1 行 + present/absent 一覧」としか定めていない。
  1 行目 = 絶対パス だけを厳格に固定し、残りは「同梱物名を含む行に `present` / `absent` の
  片方と writer id が現れる」という緩い解釈にした (`_harness.bundle_lines`)。
- **`--json-report` のキー構造**。未定義なので、構造を仮定せず値を平坦化して
  解決パス・同梱物名・解決段が含まれることだけを検査する (`_harness.flatten_strings`)。
- **解決段の記録語**。段の名前が未定義なので、段ごとに許容語の集合を持たせた
  (`_harness.STAGE_TOKENS`)。
- **既定出力先を差し替える手段**。C19 には C23 の `HB_ROOT` に相当する上書きが定義されて
  いない。環境変数を発明せず、`scripts/` + `config/` を tmp へ複製したツリー越しに起動する
  方式にした。これは「script が自身の位置から相対で config と C23 を解決する」という
  ブリーフの記述だけに依存する。
- **連番の書式**。`collision_rule` の `-2 / -3 …` をそのまま `<name>-2` として固定した。
