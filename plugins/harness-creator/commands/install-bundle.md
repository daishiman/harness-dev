---
description: harness の plugin bundle を 1 コマンドで一括 install する。Claude Code 公式に依存解決機構がないため、bundles.json の定義に従って関連 plugin を順次 install する。
argument-hint: "<bundle-name>  例: skills-full / skills-intake"
allowed-tools: Read, Bash
name: install-bundle
kind: command
version: 0.1.0
owner: team-platform
since: 2026-05-24
---

# /install-bundle

`$ARGUMENTS` で指定された bundle 名に対応する plugin 群を `.claude-plugin/bundles.json` から解決し、`.claude-plugin/marketplace.json.name` と組み合わせた exact identity `/plugin install <name>@<marketplace>` で導入する。

## 振る舞い

1. リポジトリルートの `.claude-plugin/bundles.json` を読み、`$ARGUMENTS` と一致する `bundles[].name` を探す。見つからなければ利用可能 bundle 一覧を表示して停止する。
2. `.claude-plugin/marketplace.json.name` を検証し、一致 bundle の `plugins[]` を順に `/plugin install <plugin>@<marketplace>` で install する。marketplace 名を固定値にしない。
3. 既に install 済みのものはスキップしたことを報告する。
4. 全 install 成功後、C01 `sync-native-surfaces.py --apply` → `--check` を実行する。共通 `native-surfaces.toml` は hook delivery と Codex discovery entry を所有し、plugin manifests/marketplace と結合して repo-owned の `.claude/settings.json`、`.codex/hooks.json`、`.codex/config.toml`、`.agents/plugins/marketplace.json` を製品別に同期する。非公式な `.agents/settings.json` は作らない。
5. 完了後に `/plugin list` と Codex `/hooks` を案内し、欠落 plugin と current hook trust をユーザが確認する。trust は自動承認しない。

## 引数

| 引数 | 説明 |
|---|---|
| `skills-full` | `bundles.json` に列挙された全配布対象 plugin (推奨) |
| `skills-intake` | 非エンジニア向け intake パイプライン (skill-intake + skill-governance-secrets) |

## 失敗時

- bundle 名不一致: bundles.json の `name` 一覧を表示し停止
- 個別 plugin install 失敗: 残りの plugin install は継続し、最後に失敗 plugin を集約して再試行コマンドを提示
- native settings apply/check 失敗: install 成功と settings 同期未完了を分けて報告し、`make native-surfaces` で再試行する。apply だけの成功で完了扱いしない。
- `.claude-plugin/bundles.json` または `.claude-plugin/marketplace.json` が無い: marketplace ルートに居ない可能性を案内 (`pwd` を実行させる)

## 注意

- Claude Code 公式 plugin manifest には依存宣言フィールドがないため、本コマンドが「依存解決」の代替を担う。
- 新規 plugin を追加する際は `bundles.json` の該当 bundle に必ず登録する。これは `assign-skill-design-evaluator` の rubric で評価される。
- **本コマンドは harness-creator に同梱**されており、harness-creator は配布対象外 (`distributable: false`)。そのため `/plugin install` だけで使う配布ユーザは本コマンドを持たない。bundle の一括導入は **repo を clone した開発環境** (本スラッシュコマンド) または `scripts/install-bundle.sh <bundle>` (CLI フォールバック) を使う。配布ユーザは各 plugin を marketplace 正本から解決した `/plugin install <name>@<marketplace>` で個別に導入する。
- bundles.json に登録されるのは配布対象 plugin のみ。harness-creator / prompt-creator 自体は非配布のため、どの bundle にも含まれない (clone 環境では `.claude/` symlink 経由で利用)。
- PR 準備では install をやり直さず `make native-surfaces-pr-ready` を使い、repo-owned 設定を apply→check した差分を review 対象に含める。このコマンド自体は commit/push/PR を行わない。
