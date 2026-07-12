---
name: ubm-knowledge-sync
description: ナレッジソースの差分検知→抽出→分割チェックの同期を手動起動したいときに使う。
argument-hint: "[--all] [--since YYYY-MM-DD] [--dry-run]"
allowed-tools: Read, Bash, Skill
disable-model-invocation: false
kind: command
version: 0.1.0
owner: harness-maintainers
---

# UBM ナレッジ同期

UBM ナレッジソース（YouTube 議事録・合宿記録・月報 FB・セミナー等）の新規追加・更新を検知し、内容別 JSON ファイル（6カテゴリ）へ反映する入口コマンド。北原さんの最新の教えを取り込み、目標設定の品質を継続的に向上させる。

## 実行

`run-ubm-knowledge-sync` スキルを Skill ツールで起動し、その指示に従って実行する。

- 抽出対象からは `05_Project/UBM/目標設定/`（ユーザー自身の目標記録＝北原ナレッジ非該当）を除外する。
- 引数 `$ARGUMENTS` をスキルへ引き渡す。

## 引数

- 引数なし: 未処理ファイルのみ同期（`knowledge/registry.json` の MD5 ハッシュと照合）
- `--all`: 全ファイル再構築（mode:full）
- `--since YYYY-MM-DD`: 指定日以降の更新のみ
- `--dry-run`: 検知のみで書き込みは行わない

## 推奨タイミング

`05_Project/UBM/` に新しいファイル（YouTube 議事録・合宿記録・月報 FB・セミナー記録）を追加した後に実行する。
