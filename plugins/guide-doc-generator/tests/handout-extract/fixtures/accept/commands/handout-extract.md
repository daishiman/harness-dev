---
name: handout-extract
description: 既存の単一 HTML から構成データの逆抽出と round-trip 判定を手動起動する
argument-hint: "<html-path> [--out <config.json>]"
allowed-tools: [Read, Write, Bash, Skill]
disable-model-invocation: false
---

# /handout-extract

既存の単一 HTML を run-handout-extract skill へ渡し、構成データ JSON と逆抽出レポートを得るための薄い入口である。

## 引数

- `html-path` — 必須の positional。逆抽出対象の単一 HTML ファイルパス。Read はこの入力 HTML の存在確認にだけ使う。
- `--out <config.json>` — 任意。既定は入力 HTML と同じディレクトリの handout-config.json。逆抽出レポートは --out と同じディレクトリへ併置する。
- `--out` の既定を上書きしても、変わるのは構成データ JSON の書き出し先だけである。
- 既存ファイルがある場合は黙って上書きせず、上書きしてよいかを確認する。

引数解決の規則 (機械可読な単一正本):

```json
{
  "id": "CR-EXTRACT-ARGS",
  "positional": ["html-path"],
  "flags": {
    "--out": { "required": false, "default": "{html_dir}/handout-config.json" }
  },
  "report_placement": "{out_dir}",
  "preconditions": [
    { "when": { "positional_present": false }, "action": "stop", "reason": "html-path-missing" },
    { "when": { "html_path": "missing" }, "action": "stop", "reason": "html-path-not-found" },
    { "when": { "html_path": "dir" }, "action": "stop", "reason": "html-path-is-directory" },
    { "when": { "out_exists": true }, "action": "confirm-overwrite" }
  ]
}
```

## 手順

1. $ARGUMENTS を `<html-path> [--out <config.json>]` としてパースする。html-path が無い / 存在しない / ディレクトリの場合は委譲先を起動せず停止し、解決したパスと期待する形 (単一 HTML ファイル) を示す。ディレクトリは展開せず停止する。
2. round-trip の粒度の限界を起動時に先に宣言する。等価判定は正規化後の構成データ等価で行い、HTML のバイト一致は判定しない。バイト一致が課されるのは同一構成データからの再生成のみである。
3. `Skill(run-handout-extract, args="$ARGUMENTS")` を起動し、$ARGUMENTS をそのまま渡す。走査 (R1-scan) → 復元不能箇所の補完判断 (R2-complete) → round-trip 判定 (R3-roundtrip) は skill の責務であり、HTML の走査と部品同定は skill へ渡す。
4. この command は HTML の解釈にも構成データの補完にも関与しない。判定は委譲チェーンの extract-handout-config.py / validate-handout-config.py / render-handout.py / verify-handout-selfcontained.py が Bash 経由で行う。

## 復元される範囲とされない範囲

HTML から一意に定まる構造は復元される: セクションの並び / 部品種別 / 見出し / 埋め込みアセット / アイコン参照 / 日付表記 / テーマのアクセント定義。

HTML から一意に定まらない意味情報は復元できない: 各セクションの lead-line と判断軸 / セクション goal / 資料全体の目的・背景・ゴール / 用語言い換え宣言 / 読者と前提知識レベル / 本質的課題。

復元不能箇所は黙って欠落させない。逆抽出レポートへ「どのキーパスが / なぜ復元できず / どの補完方針を採ったか」の 3 点セットで列挙する。補完方針は推測値の充填・空のまま残置・利用者への確認のいずれかを明示し、推測で埋めた値と HTML から読み取った値をレポート上で必ず区別する。

## 縮退

- 委譲先 skill run-handout-extract が見つからない場合は停止し、解決を試みたパスを示す。逆抽出の成功として返さない。
- 委譲チェーンの script (extract-handout-config.py ほか) が不在の場合も同様に停止し、解決を試みたパスを示す。

## 失敗時の扱い

- 部品構造を同定できない場合は、抽出できた範囲までの構成データと同定不能だった領域の一覧を返す。空の構成データを成功として返さない。部分成功は部分成功として提示する。
- round-trip で構成データ等価にならない場合は、差分のキーパスと両側の値を提示して FAIL とする。差分ありを等価扱いにしない。
- 逆抽出結果が validate-handout-config.py で FAIL の場合は、FAIL の事実と欠落キーパスを提示する。構成データは書き出したうえで、そのままでは生成に使えないことを明示する。値を捏造して通すことはしない。

## 境界

- 資料の生成は行わない (C07 の責務)。構成データを出すところで止まる。
- 4 面ゲートの検証 (C09 /handout-verify) は兼ねない。
- 資料内容の書き換えはしない。改善提案もしない。
- 逆抽出した構成データを資料生成へ回す場合の次の一手は `/handout-build --config <出力パス>` である。
