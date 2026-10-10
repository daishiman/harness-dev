# インラインのゴールシークの共通アンカー契約

この契約は run-ubm の6スキルで共有する。各スキルの `goal_seek.progress` / `intermediate` / `handoff` と fork、周回上限、本文検査、task-graph の検査は各スキル固有の契約とする。

## 初回固定と記録

1. 最初の周回前に、ユーザーの依頼と対象を表す空でない文字列 `original_goal` を確定する。後続の回答で補う目標値とは別の、今回の依頼のアンカーである。
2. UTF-8 の文字列に `hashlib.sha256(original_goal.encode("utf-8")).hexdigest()` を適用し、進捗ファイルの `original_goal_hash` へ固定する。以後、original_goal と hash は変えない。
3. 各周回の終わりに、中間ファイル（intermediate.jsonl）へ次の `required_keys` を持つ1行を追記する。全行の original_goal は初回と同じ値とし、直前の merged_directive_for_next を次回の必須入力にする。

必須キーの正本は `scripts/validate-inline-goal-seek-anchor.py` の `REQUIRED_KEYS`（`iteration`, `original_goal`, `current_goal_snapshot`, `delta_from_original`, `merged_directive_for_next`, `drift_signal`）。本文を短縮してキーを省略しない。

## 完了前の検証

親は host から解決した絶対 `project_root` を起点に、各 SKILL frontmatter の progress / intermediate を展開する。consult の session_id などのプレースホルダーも確定値で展開し、絶対 `progress_path` / `intermediate_path` を渡す。plugin_root は「実行時のルートの決め方」で解決する。

```bash
python3 "$PLUGIN_ROOT/scripts/validate-inline-goal-seek-anchor.py" "$progress_path" "$intermediate_path"
```

共通 validator が検査するのは進捗/中間ファイルの実在、JSONL が空でないこと、全行の必須キー、空でなく全行で不変の original_goal、進捗の original_goal_hash と UTF-8 SHA-256 の一致。本文の内容・日付・保存パスと受領書の対応・周回上限・task-graph の依存順を検査したとは扱わない。本文と受領書の検証は各スキルの専用ゲートで行う。

終了コード `0` のときだけアンカー合格。`1` は契約違反（証跡不在も含む）、`2` は usage / IO / JSON の誤り。どちらも完了を阻止し、原因を報告する。hash を取り直して検査を通す修正は禁止する。手順を実行せず「正本と同じ」と宣言するだけで完了しない。
