# C13 `embed-assets.py` 受入テスト (P04-C13-01 で赤に固定)

本ディレクトリは **実装より先に判定基準を固定する** ためのテスト群である。P05 の実装が
テストを自分に都合よく書き換えられないよう、契約は全て
`plugin-plans/guide-doc-generator/briefs/script-brief-C13.json` の `argv` / `stdout` / `stderr` /
`exit_codes` / `algorithm` / `acceptance_checks` / `failure_modes` と、
`RESOLUTION-P03.md` Y-04 (責務境界) から起こしてある。

## 実行

```bash
python3 -m unittest discover -s plugins/guide-doc-generator/tests/embed-assets.py -p 'test_*.py'
```

Python 3.10+ の標準ライブラリのみ (`unittest`)。repo ルートから実行する。

**P04 時点では全 96 件が赤 (failures) が正しい状態。** 赤の内容は import 例外ではなく
「実装が未存在」という診断可能なアサーション失敗になっている (`_harness.require_script`)。
ブリーフ準拠の参照実装を一時ディレクトリへ置いて全 96 件が緑になることを確認済みで、
達成不能な基準は含まれていない。

## 固定した責務境界 (P03 Y-04)

C13 は **アセットの data URI 化だけ** を担う。次はいずれも C13 の責務ではなく、
`test_stdlib_boundary.py` の `ResponsibilityBoundaryTest` / `WriteScopeTest` が
「やっていないこと」を検査する。

| 越えてはならない境界 | 正しい owner |
|---|---|
| 素材原本を出力先 `assets/` へ複製する | C19 (`--assets-src`) |
| `handout-config.json` を出力先へ配置する | C19 (`--place-config`) |
| `img` / lightbox / DL ボタン / `.dl-hint` を HTML へ焼く | C11 |

## ファイルと契約 id の対応表

| ファイル | 契約 id | 赤で固定した内容 |
|---|---|---|
| `_harness.py` | (共通) | パス解決・`require_script`・素材バイト列の生成 (PNG/JPEG/GIF/WebP/SVG/PDF/ZIP/XLSX)・構成データ組み立て・data URI の分解・`tree_snapshot`。テストではない |
| `test_argv_contract.py` | argv / exit_codes / stdin / AC-C13-5 (`--max-bytes 0`) | 必須 flag 欠落・未知 flag・位置引数 → exit2。`--max-bytes` の 0 / 負数 / 非整数 (`abc` `1.5` `1e6` 空 前置空白) → exit2、`1` は契約上有効。`--assets-dir` が非ディレクトリ / 不在 → exit2。`--config` 不在 / 壊れた JSON / `src` の型不正 → exit1。既定 `--max-bytes` = 5242880 がサマリへ出る。`--out` 指定時は stdout 空・`--out` のバイト列 = stdout のバイト列・書き込み不能 → exit1。stdin を読まない |
| `test_image_embedding.py` | **AC-C13-1** (C5) | `data:image/png;base64,` で始まる `data_uri`・base64 復号が原本バイトと一致 (無加工)・`embed_status=embedded`・元のローカルパス文字列が `data_uri` 側に残らない・`source_bytes` / `encoded_chars` の併記・`embed_skip_reason` は付かない・`src` を data URI で上書きしない (C20 の逆抽出のため)・既存フィールド (`id` `kind` `alt` `role`) の保存・画像 5 形式が出現順のまま全件埋め込み・`asset_embedding` サマリの件数・正常時は WARN 0 行かつ stderr サマリは出る |
| `test_mime_table.py` | **AC-C13-2** (C7 の data URI 生成側) / algorithm 5・6 | xlsx / zip / pdf の MIME が自前対応表の値と一致・拡張子は小文字化して引く・未知拡張子は `application/octet-stream` + WARN 1 行で exit0 継続・拡張子とシグネチャが食い違う画像はシグネチャ由来 MIME を採用し WARN・一致する 5 形式では WARN 0 行・SVG は先頭空白を許容・**画像以外はシグネチャ判定しない** (中身が zip の pdf も `application/pdf`)・warning が `asset_embedding.warnings` に `{asset_id, reason, hint}` で残る |
| `test_oversize_warning.py` | **AC-C13-3** (C30) | skip があっても exit0・該当素材は `data_uri` なし / `embed_status=skipped-oversize` / `embed_skip_reason` / `source_bytes` / assets-dir 相対パスを持つ (絶対パスは書かない)・同一実行内の他素材は埋め込み済み・stderr に `WARN <asset_id>: <reason>; 代替手段: <hint>` が 1 素材 1 行で hint 非空・WARN は stdout を汚さない・サマリの `embedded_count` / `skipped_count` / `total_source_bytes` (skip 分を含む)・**累積合計は閾値ではない**・境界 (上限ちょうどは埋め込み / 1 バイト超過で skip)・skip でも `--out` は書かれる |
| `test_determinism.py` | **AC-C13-4** (C29) | 2 回実行の stdout / `--out` バイト一致・`PYTHONHASHSEED` を変えても出力不変 (走査順が出現順)・base64 payload に改行/空白なし (`encodebytes` 不使用) かつ標準アルファベットで復号可・`ensure_ascii=false` / `indent=2` / 末尾改行 1 個 / LF・**入力のキー順を保存** (固定順へ正規化しない)・同一素材の複数参照が同一 data URI (`./` 表記含む)・出力に絶対パスを漏らさない・サマリに時刻系フィールドを持たない |
| `test_input_violations.py` | **AC-C13-5** / algorithm 4 / failure_modes | 素材不在・素材がディレクトリ・読めない素材 → exit1 (warning へ格下げしない)。絶対パス・`../` 脱出・途中で潜る脱出・symlink (ファイル / ディレクトリ) 脱出 → exit2。assets-dir 内で閉じる `..` は正常に exit0 (偽陽性の固定)。exit1 / exit2 のいずれでも `--out` を作らず既存ファイルも書き換えない・テンポラリを残さない・assets-dir は成功時も失敗時も 1 バイトも変わらない |
| `test_stdlib_boundary.py` | **AC-C13-6** (C27) / write_scope / P03 Y-04 | import が `sys.stdlib_module_names` 内かつ AC-C13-6 の宣言集合 (argparse/base64/json/os/pathlib/sys) に収まる・Pillow / yaml / requests 等 0 件・**`mimetypes` / `subprocess` / `shutil` / 時刻系 / 通信系 0 件**・`encodebytes` 不使用で `b64encode` 使用・複製 API と HTML 断片と `handout-config.json` / `assets-src` / `place-config` への言及 0 件・再エンコード系 (`zlib` / `resize`) 0 件・stdout 実行はディスクへ 1 バイトも書かない・`--out` 実行で増えるファイルはちょうど 1 個・`assets/` を作らない・`--config` を書き換えない |

## 検査の作り方 (3 つの原則)

1. **repo へバイナリ fixture を置かない。** 素材は `_harness` が実行時にバイト列から生成する
   (PNG は CRC 込みの実バイト、zip / xlsx は `zipfile` で生成)。シグネチャ判定を実バイトで検査するため。
2. **実 plugin ツリーへ 1 バイトも書かない。** 構成データも素材も `tempfile` の下に作り、
   assets-dir の read-only 契約は前後の `tree_snapshot` 比較で検査する。
3. **閾値をテストへ直書きしない。** 上限系は素材の実サイズから境界値を計算する
   (`len(small) + 1` 等)。唯一の直書きは argv 既定値 5242880 (`DEFAULT_MAX_BYTES`) と
   AC-C13-2 が名指しする 3 つの MIME 文字列で、いずれも `_harness` に 1 箇所だけ置いた。

## テストを書く際に判断した点 (ブリーフに明示が無い箇所)

- **素材参照の在り処。** C13 の algorithm 3 は「セクション要素および hero の画像参照フィールド」
  「資料単位/セクション単位の添付リスト」と書くが、C12 が確定する正規化済み構成データでは
  素材は資料直下の `assets[]` / `attachments[]` に集約され、セクション側は `asset_id` /
  `attachment_id` で参照するだけである (`script-brief-C12.json` の該当キー定義)。
  本テストは C12 のスキーマに従い `assets[]` / `attachments[]` を対象とした。
- **`attachments[].mime` との関係。** C12 のスキーマは `mime` を宣言フィールドとして持つが、
  AC-C13-2 は data URI の MIME を C13 自前表の値で判定する。両者が食い違うときにどちらを
  採用するかは書かれていないため、テストでは両者が一致する fixture だけを使い、
  この曖昧さに依存しない形にした。
- **skip 素材の相対パスを書くフィールド名。** algorithm 7 は「素材の assets-dir 相対パスを
  素材オブジェクトへ書く」とだけ言い、キー名を定めていない。テストは素材オブジェクト全体に
  相対パスが残り絶対パスが残らないことだけを検査し、キー名を固定していない。
- **`asset_embedding` の配置順。** 「構成データ直下」とだけあるため、キーの位置は検査せず
  存在と中身だけを固定した。入力キーの相対順が保存されることは別に検査している。
- **`__future__` import。** AC-C13-6 の列挙 6 モジュールに含まれないが依存ではないため、
  宣言集合の検査から除外した (`ALLOWED_IMPORTS`)。

## P05 が満たすべき成果物 (このテストが要求するもの)

- `plugins/guide-doc-generator/scripts/embed-assets.py` (C13) 1 ファイルのみ。
  他 component の成果物や宣言データには依存しないので、C13 単体で緑にできる。
