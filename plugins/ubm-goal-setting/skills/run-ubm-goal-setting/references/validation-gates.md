# 目標設定の決定論ゲート

回す条件、引数、終了コード、検査対象の解決と順序の正本はこのファイルとする。output-formatter と親スキルは実行前に Read する。

## 入力の出所と保存前後の対象

- `plugin_root` / `project_root` / `vault_root`: 親が `references/agent-root-contract.md` に従って解決し Task へ渡す絶対パス。
- `goal_type` / `target_period`: Phase0 で確定した種別と開始日〜終了日。bimonthly は quarterly の別名。
- `peer_paths`: info-collector が対象期間と同じ期に属する期報・月報・任意の週報を選び、絶対パスと各ファイルの対象期間を返した辞書。存在しない層は null と理由を記録する。複数候補があり対象期間を特定できなければ親へ差し戻す。単に更新日時が最新という理由で別の期を混ぜない。
- `draft_path`: output-formatter が Bash で一度作成・解決した一時ディレクトリの下の絶対パス。Write とすべての保存前検査で同じ値を使う。未展開の `$TMPDIR` や `${TMPDIR:-/tmp}` を Write へ渡さない。
- `final_path`: 命名規則と vault_root から解決した正式保存先。入力と対象範囲を確認してから書く。

保存前の `file_path = draft_path`。`gate_paths = peer_paths` の複製を作り、**作成中の goal_type の層だけを draft_path に置換する**。例えば初めての月報でも既存の同じ期の期報＋作成中の月報で照合する。作成中の期報がある場合はその下書きが期アンカーの正本で、古い期報を代わりに検査しない。quarterly_path / monthly_path / weekly_path はこの辞書から得る。保存先に既存ファイルがあるかだけで適用条件を決めない。

下書きの全ゲートが合格したら書き手は下書きSHA256と受領書を親へ返す。親が `references/guarded-publication-contract.md` の中央guard executeで final_path へ保存する。保存後は file_path と作成中層を final_path に置換して同じゲートを再実行し、実際の保存内容の合格を確認してから受領書を返す。保存後の検査失敗は完了扱いせず親へ報告し、Daily.md を更新しない。peer ファイルは参照用で勝手に変更しない。不一致の修復に peer の変更が必要なら親へ差し戻す。

## 決定論ゲート

| スクリプト | 回す条件 | 引数 | rc の意味 | rc=3 の扱い |
|---|---|---|---|---|
| `validate-goal-output.py` | 常に | `--file "{{file_path}}" --type "{{goal_type}}"` | `0`=エラー0件（警告は rc を上げない）/ `1`=エラーまたは不在ファイル / `2`=引数の誤り | 返さない |
| `validate-goal-linkage.py` | 常に | `--file "{{file_path}}"` | `0`=未解決0件 / `1`=未解決参照 / `2`=引数・入力不正 / `3`=照合対象0件 | 合格扱いしない |
| `validate-cross-level.py` | gate_paths に期報と月報が揃うとき（作成中の下書きも含む）。揃わなければ `not_applicable` と欠けた層・理由を記録 | `--quarterly "{{quarterly_path}}" --monthly "{{monthly_path}}"`。週報があれば `--weekly "{{weekly_path}}"` も渡す | `0`=全一致 / `1`=不一致・抽出不可 / `2`=引数・入力不正 / `3`=抽出0件 | 合格扱いしない |

表の順に実行する。出力を保存し終了コードを直後に取る（`| tail` 等を挟まない）。すべてのパスとプレースホルダーを確定値へ展開してから起動する。

```bash
python3 "$PLUGIN_ROOT/skills/run-ubm-goal-setting/scripts/<スクリプト>" <展開済み引数> > "$gate_log" 2>&1
rc=$?
```

`rc=1` の本文違反はユーザーが確定した内容を変えない範囲で最大3回修復する。`rc=2` は実行環境・引数・入力を直すまで停止し、本文の修復ループを回さない。`rc=3` は対象を抽出できなかった理由を報告し、完了扱いしない。月報も1ファイルなので各検査は保存前/保存後に各1回ずつ当てる。

cross-level のアンカー種類/分母は週報の有無で変わらず、週報を省略すると比較する層が1つ減る。期アンカーの値は作成中の期報または同じ期の既存期報を正とする。

## 受領書

実行した各行の rc の値そのもの、絶対パスを含む実行引数、保存前/保存後の区別を返す。不適用は rc ではなく `not_applicable` と欠けた層・理由を返す。「PASS」の語だけを返さない。正式保存パスは1件。共通ゴールシークアンカーの検証は `references/goal-seek-anchor-contract.md` を参照し、このゲートが代行したとは扱わない。
