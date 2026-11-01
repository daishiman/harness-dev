---
name: handout-build
description: 題材から単一 HTML の資料生成を手動起動する (--theme は構成データにテーマ欄が無い場合のみ有効で、採用値は同梱構成データへ書き戻されるため再現の単位は同梱構成データに閉じる)
argument-hint: "[題材] [--config <config.json>] [--doc-type <種別>] [--out-dir <path>] [--theme <preset>] [--date <yyyy/mm/dd>]"
allowed-tools: [Read, Write, Bash, Skill]
disable-model-invocation: false
---

<!--
  これはテスト用の受入例 fixture であって実装ではない。
  contract_lib.check_command がこのファイルに対して違反 0 件を返すことを
  test_contract_checker.py が固定する。実装 (commands/handout-build.md) は
  この文面をコピーする必要はなく、同じ契約を満たしていればよい。
-->

# handout-build

`$ARGUMENTS` を分解して run-handout-build へ委譲する。command はここで
判断も加工もしない。

## 引数

```json
{
  "id": "CR-HB-ARGS",
  "arguments": [
    {
      "name": "題材",
      "position": "positional",
      "required": false,
      "default": "なし (未指定かつ --config も無い場合はヒアリングで確定する)",
      "override_rule": "自然文の題材。--config と同時に指定された場合は矛盾として停止する"
    },
    {
      "name": "--config",
      "required": false,
      "default": "なし (未指定時はヒアリング駆動)",
      "override_rule": "指定されるとヒアリングを省略し R2-design 以降へ直行する。構成データの値が CLI 側の指定より優先される"
    },
    {
      "name": "--doc-type",
      "required": false,
      "default": "なし (未指定時はヒアリングで確定する)",
      "override_rule": "値の妥当性は resolve-handout-preset.py (C23) の語彙正本だけが判定する。command は語彙を持たない"
    },
    {
      "name": "--out-dir",
      "required": false,
      "default": "なし (未指定時は route-handout-output.py が既定出力先を決定論解決する)",
      "override_rule": "出力先の親ディレクトリだけを上書きする (配下の命名は route-handout-output.py が決める)"
    },
    {
      "name": "--theme",
      "required": false,
      "default": "なし (未指定時はデザイントークンの既定アクセント色)",
      "override_rule": "構成データにテーマ欄が無い場合のみ有効。既存欄があるときの指定は矛盾として停止する"
    },
    {
      "name": "--date",
      "required": false,
      "default": "なし (未指定かつ構成データにも日付欄が無いとき validate-handout-config.py --normalize が実行日を充填する)",
      "override_rule": "構成データに日付欄が無い場合のみ有効。値は正規化の入力として素通しで渡す"
    }
  ]
}
```

### --config

Read で当該パスの存在と JSON としての読み取り可否だけを確認する。内容の妥当性
判定はしない (それは validate-handout-config.py の責務)。構成データに書かれた値は
常に CLI フラグより強い正本である。

### --doc-type

用途種別の語彙とプリセットの正本は resolve-handout-preset.py (C23) ただ一つで、
command 定義本文に語彙を再列挙しない。候補提示が要る場合は
`resolve-handout-preset.py --list` の出力を使う。

### --out-dir

出力先の親ディレクトリだけを上書きする。その配下に作られる
`<YYYY-MM-DD>_<主題slug>/` の命名規則自体は上書きできない。命名は常に
route-handout-output.py (C19) が構成データから導出する。

### --theme

構成データにテーマ欄が無い場合のみ有効。採用されたテーマ名は出力先へ同梱される
構成データへ書き戻される (書き戻しの実行者は render-handout.py (C11))。したがって
バイト一致再現の単位は同梱構成データ 1 点であり、構成データ + 起動引数ではない。

### --date

受理形式は正本の yyyy/mm/dd を主とし、yyyy-mm-dd / yyyy/m/d / yyyy-m-d も素通しで
そのまま渡す。書式判定と整形は C12 が行い、command は判定しない。command も委譲先
skill も自前で現在日を取得しない (日付解決の単一 writer は
validate-handout-config.py --normalize のみ)。

## 手順

1. `$ARGUMENTS` をパースして 6 引数へ分解する。未知フラグは推測解釈せず停止する。
2. 経路を判定する。--config あり = 非対話経路 (ヒアリング省略)、--config なし =
   既定のヒアリング駆動経路 (R19)。対話は既定経路であって唯一経路ではない。
   題材と --config の同時指定は矛盾として停止する。
3. --config 指定時のみ、Read で存在と読み取り可否を確認する。
4. --theme / --date / --doc-type が構成データの既存欄と衝突する場合は停止する。
5. `Skill(run-handout-build, args="$ARGUMENTS")` を起動する
   (委譲先 build_target: plugins/guide-doc-generator/skills/run-handout-build/)。
6. 委譲先が返す生成レポートを提示する。
7. --theme を採用した場合は書き戻しの事実を伝える。

## 停止条件

- 題材も --config も無い: エラーにせず、委譲先 skill のヒアリング (R1-elicit) を
  そのまま開始する。これは誤用ではなく正規の入口。
- --config のパスが存在しない、または JSON として読めない: 委譲先を起動せず停止し、
  解決したパスを表示する。
- --doc-type が語彙正本に無い: C23 の exit≠0 を受けて停止し、候補提示を案内する。
- --theme / --date / --doc-type が構成データの既存欄と衝突: 停止して衝突箇所の
  キーパスと両方の値を示す。黙って無視も上書きもしない。
- 検証ゲートのいずれかが exit≠0: 生成物を残したまま FAIL を明示し、どのゲートが
  落ちたかを提示する。成功と読める要約を書かない。
- 出力先が 4 段のいずれでも解決できない (--out-dir 未指定・環境変数 HB_OUT_DIR 未設定・
  構成データの default_out_dir 不在): C19 の exit 2 を受けて停止し、解決を試みた 3 段を
  順に示したうえで --out-dir の指定または HB_OUT_DIR の設定を案内する。command 側で
  出力先を推測して既定を作らない。
- slide-report-generator (画像生成の委譲先) が不在: 画像生成ステップのみ skip され
  たことを skip 理由つきで報告し、他のステップは完走させる (fail-soft)。

## 報告

委譲先が返す生成レポートを加工せずそのまま提示する。

- 出力ディレクトリのパス
- 同梱 4 点 (資料 HTML・構成データ JSON・素材・README) の有無
- 適用部品
- 埋め込みサイズと warning
- 各ゲートの結果

--theme を採用した場合は「以後の再現は同梱構成データ 1 点で足り、--theme の再指定は
不要」と明示的に伝える。

## 境界

command が持つ責務は引数のパース、経路の判定、単一正本を CLI が上書きしないことの
矛盾検出、委譲先の起動、結果の提示に限る。skill へ渡す責務はヒアリング内容の設計
判断、構成データの確定、プリセット解決、決定論 script 列の実行順序、ゲート結果の
集約、出力先ルーティングである。command は資料の内容にも HTML の組み立てにも一切
関与しない (薄い入口)。
