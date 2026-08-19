---
name: handout-extract
description: "既存の単一 HTML から構成データの逆抽出と round-trip 判定を手動起動する"
argument-hint: "<html-path> [--out <config.json>]"
allowed-tools: [Read, Write, Bash, Skill]
disable-model-invocation: false
source: "plugin-plans/guide-doc-generator/component-inventory.json#C08"
output_language: ja
---

# /handout-extract — 逆抽出の起動入口

この command は薄い入口である。持つ責務は、入力パスの検証、出力先の既定解決と上書き確認、
round-trip の粒度の限界の事前開示、委譲先の起動、復元された範囲と復元されなかった範囲を
区別したままの結果提示に限る。

この command は HTML の解釈にも構成データの補完にも関与しない。skill へ渡す責務は、HTML の走査と部品同定、復元不能箇所の補完方針の判断、構成データの確定、再レンダリングと構成データ等価の判定、逆抽出レポートの作成である。

## 引数の既定値と上書き規則

- `html-path` — 必須の positional。逆抽出対象の単一 HTML ファイルパス。guide-doc-generator が生成した HTML でも手書き HTML でも受け付ける。
- Read はこの入力 HTML の存在確認にだけ使う。中身の意味づけはしない。
- `--out <config.json>` — 任意。既定は入力 HTML と同じディレクトリの handout-config.json。
- `--out` を指定しても変わるのは構成データ JSON の書き出し先だけであり、逆抽出レポートは `--out` と同じディレクトリへ併置する。
- 既存ファイルがある場合は黙って上書きせず、上書きしてよいかを確認する。手で補完した意味情報は再逆抽出では戻らないため、上書きは不可逆な損失になりうる。

引数解決の規則は次の宣言を単一正本とし、`preconditions` を first-match で評価する。散文と
食い違った場合はこの宣言が正しい。

```json
{
  "id": "CR-EXTRACT-ARGS",
  "owner": "C08 /handout-extract",
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

1. `$ARGUMENTS` を `<html-path> [--out <config.json>]` としてパースし、上の `CR-EXTRACT-ARGS` で解決する。html-path が無い / 存在しない / ディレクトリの場合は委譲先を起動せず停止する。
2. 停止するときは解決したパスと期待する形 (単一 HTML ファイル) を示す。ディレクトリは展開せず停止し、どの HTML を正とするかを command が推測しない。
3. round-trip の粒度の限界を、起動時に結果提示より先に宣言する (下の「round-trip の粒度」)。
4. `Skill(run-handout-extract, args="$ARGUMENTS")` を起動し、`$ARGUMENTS` をそのまま渡す。command 側で引数を作り替えない。
5. 走査 (R1-scan) から復元不能箇所の補完方針の判断 (R2-complete)、構成データの確定と round-trip 判定 (R3-roundtrip) までは委譲先 skill の責務である。
6. 委譲チェーンの extract-handout-config.py / validate-handout-config.py / render-handout.py / verify-handout-selfcontained.py は、委譲先が Bash 経由で起動する。command はその判定を代行しない。
7. 構成データ JSON のパス、逆抽出レポートのパス、round-trip 判定の結果と差分の内訳を提示する。

## round-trip の粒度

等価判定は正規化後の構成データ等価で行い、HTML のバイト一致は判定しない (空白と属性順で差が出るため)。

バイト一致が課されるのは同一構成データからの再生成のみである。

比較の実行主体は委譲先 skill の再レンダリング比較 (R3-roundtrip) であり、この command は比較方式を選ばない。

## 復元される範囲とされない範囲

HTML から一意に定まる構造は復元される: セクションの並び / 部品種別 / 見出し / 埋め込みアセット /
アイコン参照 / 日付表記 / テーマのアクセント定義。

HTML から一意に定まらない意味情報は復元できないか、復元しても元の意図と一致する保証がない: 各セクションの lead-line と判断軸 / セクション goal / 資料全体の目的・背景・ゴール / 用語言い換え宣言 / 読者と前提知識レベル / 本質的課題。

復元不能箇所は黙って欠落させない。逆抽出レポートへ「どのキーパスが / なぜ復元できなかったか / どの補完方針を採ったか」を組にして列挙させる。補完方針は推測値の充填・空のまま残置・利用者への確認のいずれかを明示し、推測で埋めた値と HTML から読み取った値をレポート上で必ず区別する。

人が埋める必要のある項目が残ることは、逆抽出の失敗ではない。埋めるべきキーパスと理由を利用者へ渡すところまでがこの入口の仕事である。

## 縮退

- 委譲先 skill run-handout-extract が見つからない場合は停止し、解決を試みたパスを示す。逆抽出の成功として返さない。
- 委譲チェーンの script (extract-handout-config.py ほか) が不在の場合も同様に停止し、解決を試みたパスを示す。検査を省いて成功と報告しない。

## 失敗時の扱い

- 部品構造を同定できない場合は、抽出できた範囲までの構成データと同定不能だった領域の一覧を返す。空の構成データを成功として返さない。部分成功は部分成功として提示する。
- round-trip で構成データ等価にならない場合は、差分のキーパスと両側の値を提示して FAIL とする。差分ありを等価扱いにしない。
- 逆抽出結果が validate-handout-config.py で FAIL の場合は、FAIL の事実と欠落キーパスを提示する。構成データは書き出したうえで、そのままでは生成に使えないことを明示する。値を捏造して通すことはしない。
- 委譲先が exit≠0 で終わっても、既に書き出された構成データと逆抽出レポートを捨てず、そのパスを提示する。どの exit code で何が残るかの正本は extract-handout-config.py (C20) と run-handout-extract (C02) 側にあり、この command では再解釈しない。
- `W-` で始まる診断行は失敗として数えない。fail の判定は exit code と `E-` で始まる行で行う。

## 境界

- 資料の生成は行わない (C07 の責務)。構成データを出すところで止まる。
- 検証 (C09 `/handout-verify`) は兼ねない。ゲート結果の状態分類と全体 verdict の規則は C09 が持つ単一正本であり、この command では再解釈しない。
- 資料内容の書き換えはしない。改善提案もしない。
- 出力ディレクトリ名を自前で組み立てない。命名の導出は route-handout-output.py (C19) の単独責務であり、この command は `--out` で指示されたパスへ書き出すだけである。
- 逆抽出した構成データを資料生成へ回す場合の次の一手は `/handout-build --config <出力パス>` である。生成へ進むかどうかは利用者の判断であり、この command は案内に留まる。
