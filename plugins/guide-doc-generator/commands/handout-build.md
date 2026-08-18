---
name: handout-build
description: "題材から単一 HTML の資料生成を手動起動する (--theme は構成データにテーマ欄が無い場合のみ有効で、採用値は同梱構成データへ書き戻されるため再現の単位は同梱構成データに閉じる)"
argument-hint: "[題材] [--config <config.json>] [--doc-type <種別>] [--out-dir <path>] [--theme <preset>] [--date <yyyy/mm/dd>]"
allowed-tools: [Read, Write, Bash, Skill]
disable-model-invocation: false
source: "plugin-plans/guide-doc-generator/component-inventory.json#C07"
output_language: ja
---

# /handout-build — 資料生成の起動入口

この command は薄い入口である。持つ責務は、引数のパース、経路 (対話 / 非対話) の
判定、単一正本を CLI が上書きしないことの矛盾検出、委譲先の起動、結果の提示に限る。
資料の内容にも HTML の組み立てにも一切関与しない (薄い入口)。判断も加工もしない。

skill へ渡す責務は、ヒアリング内容の設計判断、構成データの確定、プリセット解決、
決定論 script 列の実行順序、ゲート結果の集約、出力先ルーティングである。これらを
command 側で先取りしない。

## 引数の既定値と上書き規則

```json
{
  "id": "CR-HB-ARGS",
  "arguments": [
    {
      "name": "題材",
      "position": "positional",
      "required": false,
      "default": "なし (未指定かつ --config も無い場合はヒアリングで確定する)",
      "override_rule": "自然文の題材。対話開始のきっかけを渡すだけで、構成データの主題を上書きしない。--config と同時に指定された場合は矛盾として停止し、どちらを正とするか利用者に選ばせる"
    },
    {
      "name": "--config",
      "required": false,
      "default": "なし (未指定時はヒアリング駆動)",
      "override_rule": "検証済み / 未検証いずれの構成データ JSON でも受け付ける。指定されるとヒアリングを省略し R2-design 以降へ直行する。構成データに書かれた値は常に CLI フラグより強い正本であり、--doc-type / --theme / --date は構成データに当該欄が無い場合にのみ効く"
    },
    {
      "name": "--doc-type",
      "required": false,
      "default": "なし (未指定時はヒアリングで確定する。--config に用途種別欄があればそれが正)",
      "override_rule": "値の妥当性は resolve-handout-preset.py (C23) の語彙正本だけが判定する。command は語彙を持たず、判定もしない。混成用途は受け付けず、主用途 1 つとセクション追加で表現させる"
    },
    {
      "name": "--out-dir",
      "required": false,
      "default": "なし (未指定時は route-handout-output.py が既定出力先を決定論解決する)",
      "override_rule": "出力先の親ディレクトリだけを上書きする。配下の命名規則は上書きできず、常に route-handout-output.py (C19) が構成データから導出する"
    },
    {
      "name": "--theme",
      "required": false,
      "default": "なし (未指定時はデザイントークンの既定アクセント色)",
      "override_rule": "構成データにテーマ欄が無い場合のみ有効。採用値は同梱構成データへ書き戻される (実行者は render-handout.py (C11))。既存欄がある状態での指定は矛盾として停止する"
    },
    {
      "name": "--date",
      "required": false,
      "default": "なし (未指定かつ構成データにも日付欄が無いとき validate-handout-config.py --normalize が生成実行日を充填する)",
      "override_rule": "構成データに日付欄が無い場合のみ有効。値は正規化の入力として素通しで渡す。既存欄がある状態での指定は矛盾として停止する"
    }
  ]
}
```

### 題材 (positional)

対話を始めるきっかけだけを渡す最軽量の起動。題材と --config の同時指定は矛盾として
停止し、どちらを正とするか利用者に選ばせる。

### --config

Read で当該パスの存在と JSON としての読み取り可否だけを確認する。内容の妥当性判定は
しない (それは validate-handout-config.py (C12) の責務)。構成データに書かれた値は
常に CLI フラグより強い正本である。

### --doc-type

用途種別の語彙とプリセットの正本は resolve-handout-preset.py (C23) ただ一つであり、
この command 定義本文へ語彙を再列挙しない。候補提示が要る場合は
`resolve-handout-preset.py --list` の出力をそのまま使う。

### --out-dir

出力先の親ディレクトリだけを上書きする。その配下に作られる
`<YYYY-MM-DD>-<種別>-<主題slug>/` の命名規則自体は上書きできず、命名は常に
route-handout-output.py (C19) が構成データから導出する。command は命名を組み立てない。

### --theme

構成データにテーマ欄が無い場合のみ有効。採用されたテーマ名は出力先へ同梱される
構成データへ書き戻される (書き戻しの実行者は render-handout.py (C11) であり、
command ではない)。したがってバイト一致再現の単位は同梱構成データただ一つであって、
構成データと起動引数の組ではない。

### --date

受理形式は正本の yyyy/mm/dd を主とし、C12 が寛容に受ける yyyy-mm-dd / yyyy/m/d /
yyyy-m-d も素通しでそのまま渡す。書式判定と正本形式への整形は C12 が行い、command は
判定しない。command も委譲先 skill も自前で現在日を取得しない (日付解決の単一 writer は
`validate-handout-config.py --normalize` のみ)。なおディレクトリ名に現れる
`<YYYY-MM-DD>` は C19 が導く命名専用の派生表現で、表示の正本表現とは別概念である。

## 手順

1. `$ARGUMENTS` をパースし、上の `CR-HB-ARGS` に並ぶ各引数へ分解する。未知フラグは
   推測解釈せず停止する。
2. 経路を判定する。--config あり = 非対話経路 (ヒアリング省略で R2-design 以降へ直行)、
   --config なし = 既定のヒアリング駆動経路 (R19)。対話は既定経路であって唯一経路ではない。
   題材と --config の同時指定は矛盾として停止する。
3. --config 指定時のみ、Read で存在と読み取り可否を確認する。中身は見ない。
4. --theme / --date / --doc-type が指定されていて、構成データに対応する欄が既にある
   場合は上書きせず停止する。
5. `Skill(run-handout-build, args="$ARGUMENTS")` を起動し、ヒアリング (R1-elicit) から
   構成設計 (R2-design)、決定論レンダリング、ゲート実行と出力先ルーティングまでを委譲
   する。委譲先 build_target は plugins/guide-doc-generator/skills/run-handout-build/ である。
   command はこの間、判断も加工もしない。
6. 委譲先が返した生成レポートを提示する。
7. --theme を採用した場合は書き戻しの事実を伝える。

## 停止条件と縮退時の挙動

- 題材も --config も無い起動: エラーにせず、委譲先 skill のヒアリング (R1-elicit) を
  そのまま開始する。引数なし起動は誤用ではなく正規の入口である。
- --config のパスが存在しない、または JSON として読めない: 委譲先を起動せず停止し、
  解決したパスを表示する。ヒアリング経路へ暗黙にフォールバックしない。
- --doc-type が語彙正本に無い: C23 の exit≠0 を受けて停止し、
  `resolve-handout-preset.py --list` による候補提示を案内する。command は語彙判定を
  代行しない。
- --theme / --date / --doc-type が構成データの既存欄と衝突: 停止して衝突箇所の
  キーパスと両方の値を示し、構成データ側を正として編集するか当該フラグを外すよう
  案内する。黙って無視も上書きもしない。
- 検証ゲートのいずれかが exit≠0: 生成物を残したまま FAIL を明示し、どのゲートが落ちた
  かと該当箇所を提示する。成功と読める要約を書かない。状態分類と全体判定の規則は
  `/handout-verify` (C09) が持つ単一正本に従い、この command では再解釈しない。
- slide-report-generator (画像生成の委譲先) が不在: 画像生成ステップのみ skip された
  ことを skip 理由つきで報告し、他のステップは完走させる (fail-soft)。任意依存の不在で
  全体を止めないが、skip を黙って落とさない。

## 報告

委譲先が返す生成レポートを加工せずそのまま提示する。

- 出力ディレクトリのパス
- 同梱物 (資料 HTML・構成データ JSON・素材・README) の有無
- 適用部品
- 埋め込みサイズと warning
- 各ゲートの結果

--theme を採用した場合は「採用テーマは同梱構成データへ書き戻された。以後の再現は
同梱構成データだけで足り、--theme の再指定は不要」と明示的に伝える。
