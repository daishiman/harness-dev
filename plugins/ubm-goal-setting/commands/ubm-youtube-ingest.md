---
name: ubm-youtube-ingest
description: 北原さんの YouTube 取込を URL 単発 / 全量 backfill / 差分 sync のいずれかで手動起動・再実行・dry-run したいときに使う。自動同期の代替ではない。
argument-hint: "[--url URL | --backfill | --sync] [--source SOURCE] [--dry-run]"
allowed-tools: Read, Bash, Skill
disable-model-invocation: false
kind: command
version: 0.1.0
owner: harness-maintainers
---

# UBM YouTube 取込

北原さんの YouTube 動画のナレッジ取込を **手動で起動・再実行・dry-run** する入口コマンド。URL 単発 / 全量 backfill / scheduler と同じ差分 sync の 3 モードを、その場で回したいときに使う。取得契約・冪等性・全量性・fallback の実体は `run-ubm-youtube-ingest` スキルが所有し、本コマンドはその薄い運用面（アダプタ）に徹する。

## 位置づけ（自動性の代替ではない）

無人の定期取込は、本コマンドと **同一の one-shot**（`run-ubm-youtube-ingest` スキル内 `scripts/run-youtube-sync-oneshot.py`）を host scheduler が呼ぶことで実現する。本コマンドは自動同期を置き換えるものではなく、手動での確認・再実行・障害後リカバリ・dry-run 検証のための同じ機構への手動入口である。したがって手動 sync は scheduler の one-shot と **同じ idempotency key（`video_id`）と同じ cursor** を共有し、別系統の状態を作らない。

## 実行

`run-ubm-youtube-ingest` スキルを Skill ツールで起動し、その指示に従って実行する。

- 引数 `$ARGUMENTS` を解析し、下記「引数の排他検証」を通してからスキルの該当モードへそのまま引き渡す。
- モード指定（`--url` / `--backfill` / `--sync`）・`--source`・`--dry-run` はスキル側の同名フラグへ透過する。二重起動防止（lease）・cursor・retry・冪等性はスキル / one-shot 側の機構を尊重し、本コマンドで別の状態管理を持たない。

## 引数

- `--url URL`: 指定 1 本を単発でナレッジ化する。
- `--backfill`: required-primary（北原孝彦のコンサルティング）の全公開動画を、完全性ゲート（`check-youtube-backfill-completeness.py`）が緑になるまで取り込む。
- `--sync`: scheduler 起動相当の無人差分取込。新着のみを差分で取り込む（one-shot と同じ経路）。
- `--source SOURCE`: 対象ソースを明示指定する（未指定時はスキルの source registry の優先度に従う）。
- `--dry-run`: 検知・整形のみで **書き込みを一切行わない**（registry / 正規化ソース出力 / knowledge のいずれにも書かない）。

## 引数の排他検証

- `--url` / `--backfill` / `--sync` は **相互排他**。2 つ以上が同時指定された場合はスキルを起動せず、どのモードで実行したいのかを 1 つに絞るよう説明して停止する（例: 「`--backfill` と `--sync` が同時指定されています。全量取込なら `--backfill`、差分取込なら `--sync` のいずれか一方を指定してください」）。
- モード指定が 1 つも無い場合は、まず `--sync`（差分取込）を既定候補として提示しつつ、`--url` / `--backfill` を含む選択肢をユーザーに確認してから起動する。
- `--source` / `--dry-run` はモードと直交し、いずれのモードとも併用できる。

## 手動 sync と自動 one-shot の一致（不変則）

- 手動 sync（本コマンド `--sync`）と scheduler の自動 one-shot は、**同じ `video_id` を idempotency key** とし、**同じ cursor** を進める。同一動画を二度 ingest しない・二回目は 0 件・`temporary_failure` は次回 retry で回復する、という冪等性はどちらの経路でも同一に成立する。
- `--dry-run` はこの一致を壊さない。dry-run は cursor も registry も前進させず、書き込み 0 のまま「次に何が取り込まれるか」だけを提示する。

## 推奨タイミング

- 新しい動画を即座にナレッジ化したいとき（`--url`）。
- 過去分をまとめて漏れなく取り込みたい・取込漏れを是正したいとき（`--backfill`）。
- 自動同期の結果を手元で確認・再実行したい、または障害後にリカバリしたいとき（`--sync`、必要なら `--dry-run` で先に確認）。
