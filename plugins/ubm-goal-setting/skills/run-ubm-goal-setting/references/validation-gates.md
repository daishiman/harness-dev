# 目標設定の決定論ゲート

回す条件、引数、終了コード、検査対象の解決と順序の正本はこのファイルとする。output-formatter と親スキルは実行前に Read する。

## 入力の出所と保存前後の対象

- `plugin_root` / `project_root` / `vault_root`: 親が `references/agent-root-contract.md` に従って解決し Task へ渡す絶対パス。
- `goal_type` / `target_period`: Phase0 で確定した種別と開始日〜終了日。種別は4層 `yearly` / `quarterly` / `monthly` / `weekly`（bimonthly は quarterly の別名）。種別定義の正本は `references/data-contract.md` §1.0。
- `peer_paths`: info-collector が対象期間と同じ期に属する期報・月報・任意の週報・任意の1年目標を選び、絶対パスと各ファイルの対象期間を返した辞書。存在しない層は null と理由を記録する。複数候補があり対象期間を特定できなければ親へ差し戻す。単に更新日時が最新という理由で別の期を混ぜない。1年目標は対象期間を含む1年のものを選ぶ（1年層は暦の1年で切るため、下位3層と開始日が揃わないのが正常）。
- `draft_path`: output-formatter が Bash で一度作成・解決した一時ディレクトリの下の絶対パス。Write とすべての保存前検査で同じ値を使う。未展開の `$TMPDIR` や `${TMPDIR:-/tmp}` を Write へ渡さない。
- `final_path`: 命名規則と vault_root から解決した正式保存先。入力と対象範囲を確認してから書く。

保存前の `file_path = draft_path`。`gate_paths = peer_paths` の複製を作り、**作成中の goal_type の層だけを draft_path に置換する**。例えば初めての月報でも既存の同じ期の期報＋作成中の月報で照合する。作成中の期報がある場合はその下書きが期アンカーの正本で、古い期報を代わりに検査しない。yearly_path / quarterly_path / monthly_path / weekly_path はこの辞書から得る。保存先に既存ファイルがあるかだけで適用条件を決めない。作成中が1年目標（`goal_type = yearly`）の場合も同じで、その下書きが到達点アンカーの正本になり、既存の1年目標を代わりに検査しない。

下書きの全ゲートが合格したら書き手は下書きSHA256と受領書を親へ返す。親が `references/guarded-publication-contract.md` の中央guard executeで final_path へ保存する。保存後は file_path と作成中層を final_path に置換して同じゲートを再実行し、実際の保存内容の合格を確認してから受領書を返す。保存後の検査失敗は完了扱いせず親へ報告し、Daily.md を更新しない。peer ファイルは参照用で勝手に変更しない。不一致の修復に peer の変更が必要なら親へ差し戻す。

## 決定論ゲート

| スクリプト | 回す条件 | 引数 | rc の意味 | rc=3 の扱い |
|---|---|---|---|---|
| `validate-goal-output.py` | 常に | `--file "{{file_path}}" --type "{{goal_type}}"` | `0`=エラー0件（警告は rc を上げない）/ `1`=エラー / `2`=引数の誤り・`--file` や `--peer` が無い・UTF-8 で読めない・語彙契約を読めない | 返さない |
| `validate-goal-linkage.py` | 常に | `--file "{{file_path}}"` | `0`=未解決0件 / `1`=未解決参照 / `2`=引数・入力不正 / `3`=照合対象0件 | 合格扱いしない |
| `validate-cross-level.py` | gate_paths に期報と月報が揃うとき（作成中の下書きも含む）。揃わなければ `not_applicable` と欠けた層・理由を記録 | `--quarterly "{{quarterly_path}}" --monthly "{{monthly_path}}"`。週報があれば `--weekly "{{weekly_path}}"`、1年目標があれば `--yearly "{{yearly_path}}"` も渡す | `0`=全一致 / `1`=不一致・抽出不可 / `2`=引数・入力不正 / `3`=抽出0件 | 合格扱いしない |

### `--type yearly` のゲート

`goal_type = yearly` でも回す行は上表の3行と同じで、引数の当てはめだけが変わる。

- `validate-goal-output.py --file "{{file_path}}" --type yearly`: 必須見出し23件（逐語一覧の正本は `references/output-formats.md`「1年目標（1年）フォーマット」）、【今年の最重要数字】の存在、【今年やらないこと（明確に排除するもの）】3項目以上、**【プロジェクト別タスク】の不在**（存在したら FAIL）を検査する。`--type` と本文のタイトル見出し `## 【1年の目標】…` の不一致は error（種別の取り違え検出）なので、`--type` は推測せず Phase0 の確定値を渡す。
- `validate-goal-linkage.py --file "{{file_path}}"`: 他種別と同じ。1年目標は提出用セクションを持たないため `SKIP` は出ない。
- `validate-cross-level.py`: 下記「cross-level の4層実行」。**作成中が1年目標なら、`--yearly` に下書きパスを渡す**（既存の1年目標ではなく下書きが到達点アンカーの正本）。

### cross-level の4層実行

```bash
python3 "$PLUGIN_ROOT/skills/run-ubm-goal-setting/scripts/validate-cross-level.py" \
  --yearly "{{yearly_path}}" --quarterly "{{quarterly_path}}" \
  --monthly "{{monthly_path}}" --weekly "{{weekly_path}}" \
  > "$gate_log" 2>&1
rc=$?
```

- `--quarterly` と `--monthly` は必須、`--yearly` と `--weekly` は任意。
- **1年目標が存在する期では必ず `--yearly` を渡す（運用契約）。** 渡さないと到達点アンカー2件（`月間売上到達点` / `継続コンサル人数`・`requires_level="yearly"`）は照合されず、出力に `[未照合]` と `未照合のアンカー N 件` が印字されたまま rc=0 で通る。これは「照合して一致していた」ではない。受領書には `--yearly` を渡したかどうかと、出力の `照合対象 N 件中 不一致 M 件（抽出不可 K 件）` の行、未照合件数をそのまま書く。
- 1年目標が未作成の期では `--yearly` を省略してよい（この2件が `[未照合]` になるのが正常）。その場合も省略した事実と未照合件数を受領書に残す。
- アンカーの一覧・置き場・継承の形は `references/data-contract.md` §3.1.3「四層横断照合（validate-cross-level.py）の対象一覧」を正本とする。

表の順に実行する。出力を保存し終了コードを直後に取る（`| tail` 等を挟まない）。すべてのパスとプレースホルダーを確定値へ展開してから起動する。

```bash
python3 "$PLUGIN_ROOT/skills/run-ubm-goal-setting/scripts/<スクリプト>" <展開済み引数> > "$gate_log" 2>&1
rc=$?
```

`rc=1` の本文違反はユーザーが確定した内容を変えない範囲で最大3回修復する。`rc=2` は実行環境・引数・入力を直すまで停止し、本文の修復ループを回さない。`rc=3` は対象を抽出できなかった理由を報告し、完了扱いしない。月報も1ファイルなので各検査は保存前/保存後に各1回ずつ当てる。

cross-level のアンカー種類/分母は週報の有無で変わらず、週報を省略すると比較する層が1つ減る。期アンカーの値は作成中の期報または同じ期の既存期報を正とする。

**`--yearly` の有無は分母そのものを変える。** 到達点アンカー2件は `requires_level="yearly"` なので、`--yearly` を省略すると比較する層が減るのではなく**照合対象から外れる**（`照合対象 N 件` の N が 2 小さくなり、代わりに未照合件数が出る）。到達点の値は作成中の1年目標または同じ1年の既存1年目標を正とする。

## 受領書

実行した各行の rc の値そのもの、絶対パスを含む実行引数、保存前/保存後の区別を返す。不適用は rc ではなく `not_applicable` と欠けた層・理由を返す。「PASS」の語だけを返さない。cross-level は `--yearly` を渡したかどうかと未照合件数も返す（rc=0 だけでは到達点アンカーを照合したか判別できない）。正式保存パスは1件。共通ゴールシークアンカーの検証は `references/goal-seek-anchor-contract.md` を参照し、このゲートが代行したとは扱わない。
