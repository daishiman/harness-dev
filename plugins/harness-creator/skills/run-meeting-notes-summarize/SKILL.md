---
name: run-meeting-notes-summarize
description: 会議メモ (Markdown 1 本) から決定事項と宿題を抜き出したいとき、宿題の担当者・期限を表に整理したいときに使う。
disable-model-invocation: false
user-invocable: true
argument-hint: "<meeting-notes.md> [--out <summary.md>]"
arguments: [notes_path]
arguments-optional: [out]
allowed-tools:
  - Read
  - Write
  - Bash(python3 *)
kind: run
prefix: run
effect: local-artifact
runtime_root_policy: host-skill-path
owner: team-platform
since: 2026-11-15
version: 0.1.0
max_loops: 3
script_refs:
  - scripts/render-minutes-table.py
  - scripts/validate-inline-goal-seek-anchor.py
source: user-request
source-tier: internal
last-audited: 2026-11-15
audit-trigger: on-change
combinators: [with-feedback-contract]
feedback_contract:
  activation_state: semantic_evaluator_started
  max_iterations: 3
  criteria:
    - id: IN1
      loop_scope: inner
      text: render-minutes-table.py が担当者または期限の欠落した宿題を未定と表示し要確認節へ列挙し既存の出力先を上書きせず exit2 で停止する
      verify_by: script
    - id: IN2
      loop_scope: inner
      text: 出力表の全行がメモ内の行番号を根拠として持ちメモに書かれていない担当者や期限が表に現れない
      verify_by: evaluator
    - id: OUT1
      loop_scope: outer
      text: 決定事項と宿題の区別基準が検討中や保留の記述を除外し一文に両方を含む記述を双方へ載せる設計で利用者が表だけで会議の結論と次の作業を把握できる
      verify_by: elegant-review
---

# run-meeting-notes-summarize

## Runtime root contract

`SKILL_ROOT` = host が示した本 SKILL.md の実在する絶対ディレクトリ。`scripts/` はここから解決し、cwd から推測しない。環境変数が空なら連結しない。

## Purpose & Output Contract

**入力**: 会議メモの Markdown ファイル 1 本 (`notes_path`)。
**出力**: 次の 2 表を含む Markdown (会話に提示。`--out` 指定時はそのファイルにも書く)。

1. **決定事項** — `| # | 決定事項 | 根拠 |`
2. **宿題** — `| # | 内容 | 担当者 | 期限 | 根拠 |`

根拠はメモ内の行番号 (`L12` 形式)。メモに書かれていない担当者・期限は推測で埋めず `未定` と書き、表の下の「要確認」に列挙する。元メモは変更しない。

## ゴールシーク実行

固定手順は書かず、ゴール+チェックリストへ向け都度手順を生成・反復する。正本は harness-creator plugin の `skills/run-build-skill/references/goal-seek-paradigm.md` (出典表記)。

### ゴール (Goal)

指定した会議メモ 1 本の決定事項と宿題が、根拠行番号付きの 2 表と「要確認」節にまとめられ、利用者に提示された状態になっている。

### 目的・背景 (Why)

会議後に「何が決まり、誰がいつまでに何をするか」をすぐ共有できるようにするため。メモの書き方は会議ごとに違うため、固定手順ではなく未達項目から都度埋める。

### 完了チェックリスト (Checklist)

- [ ] `notes_path` が存在する空でない Markdown であることを Read で確認済み (違えば理由を伝えて停止)
- [ ] 結論が確定した記述 (「決定」「合意」「承認」「〜とする」「〜で進める」) が決定事項として全件抽出され、検討中・案・保留は含まれていない
- [ ] 後で誰かが行う作業 (「TODO」「宿題」「AI」「- [ ]」「〜さんが〜する」) が宿題として全件抽出されている
- [ ] 各項目に根拠行番号が付き、担当者・期限はメモの表記どおりで推測値が入っていない
- [ ] `render-minutes-table.py` が exit 0 で 2 表を出力した (exit 1 は入力 JSON を直して再実行、exit 2 は利用者に別の出力先を確認)
- [ ] 出力 Markdown を会話に提示し、`--out` 指定時はそのパスを伝えた

### ゴールシークループ

正本 6 ステップ (現状評価→手順生成→実行→検証→Anchor Step→反復) に従う。Anchor Step では各周回末に中間成果物スナップショットを eval-log に記録し、original_goal からのドリフトを検知する。本スキル固有差分: 未達評価の単位はチェックリスト項目。抽出漏れや誤分類に気付いたら下の局面カタログから該当局面だけをやり直す。

### ゴールシーク配線

- **ルート**: host の作業ディレクトリを絶対 `project_root` として固定する。`SKILL_ROOT` は上の Runtime root contract で解決する。
- **progress**: `project_root/eval-log/run-meeting-notes-summarize-progress.json`。初回に空でない依頼文 `original_goal` を固定し、UTF-8 の `hashlib.sha256(original_goal.encode("utf-8")).hexdigest()` を `original_goal_hash` に保存する。目標の変更や hash の取り直しで検査を通さない。
- **中間成果物**: `project_root/eval-log/run-meeting-notes-summarize-intermediate.jsonl`。初回 iteration=0 と各周回末に append する。`required_keys` は同梱 validator の `REQUIRED_KEYS`（`iteration`, `original_goal`, `current_goal_snapshot`, `delta_from_original`, `merged_directive_for_next`, `drift_signal`）が正本。
- **goal-spec**: `project_root/eval-log/goal-spec.json`。初回の依頼とチェックリストを記録する。各周回の手順生成には初回の `original_goal` と直前の `merged_directive_for_next` を必須入力として渡し、単独で再導出しない。
- **コンテキスト分離**: 1 ファイルの要約なので fork せず main context で実行する。
- **打ち切り**: `max_loops: 3` で必ず停止する。未達条件は progress の `open_issues` に記録しユーザーへ返す。未達を完了として扱わない。

### ゴールシーク検証

毎周回末と完了報告前に、上のルートから絶対 `progress_path` / `intermediate_path` を解決して以下を実行する。validator は生成元 `run-build-skill/templates/goal-seek-runtime/scripts/validate-inline-goal-seek-anchor.py` と byte 一致で同梱される（`lint-vendored-ssot.py` が一致を強制する）。

```bash
python3 "$SKILL_ROOT/scripts/validate-inline-goal-seek-anchor.py" "$progress_path" "$intermediate_path"
```

終了コード 0 だけをアンカー合格とし、1 は契約違反、2 は IO/JSON/引数の誤りとして停止する。検査を実行せずに合格を宣言しない。表の内容の正しさは完了チェックリストで確認する。

## 局面カタログ (順序は都度判断)

### 抽出

メモ全体を読み、決定事項と宿題を分ける。「〜することに決定し、A さんが対応」は両方に 1 件ずつ載せる。担当者は `@名前`・`名前さん`・`担当: 名前` などメモの表記をそのまま使う。期限の相対表現 (「来週金曜」) はメモの日付が分かれば `YYYY-MM-DD` に変換して元表記を括弧で残し、分からなければ元表記のまま。

### 整形

抽出結果を次の JSON にして整形スクリプトに渡す:

```json
{"source": "<notes_path>", "decisions": [{"text": "...", "lines": "L12"}],
 "actions": [{"text": "...", "owner": "田中", "due": "2026-11-20", "lines": "L20-21"}]}
```

```bash
python3 "$SKILL_ROOT/scripts/render-minutes-table.py" --input <items.json> [--out <summary.md>]
```

スクリプトは担当者・期限の欠落を `未定` にし、「要確認」節を自動生成する。exit 0=成功 / 1=入力不正 / 2=出力先が既に存在 (上書きしない)。

## Gotchas

- 担当者・期限を推測で埋めない。迷ったら `未定` にして「要確認」へ回す。
- 入力は 1 ファイルのみ。複数メモの統合は対象外。
- 元メモは変更しない。

## Example

`examples/sample-notes.md` → `examples/sample-summary.md`
