---
name: spec-drift-triage
description: 指定 issue の spec-drift トリアージ (影響判定) を手動起動する
kind: command
version: 0.1.0
owner: harness maintainers
since: 2026-07-13
argument-hint: "[--issue NUMBER]"
allowed-tools: Read, Bash, Skill
disable-model-invocation: false
entrypoint: run-spec-drift-triage
---

# /spec-drift-triage

`$ARGUMENTS` を `--issue NUMBER` としてパースし、指定 issue の spec-drift トリアージ (影響判定) を**手動起動**する薄いラッパ。判定ロジックは一切持たず、対象 issue の全未triage完全 diff の再構成→hunk 構造化→4 軸+semantics 影響判定は **C01 skill (`run-spec-drift-triage`)** へ委譲する。本 command の責務は「対象 issue の確定と skill 起動」だけであり、影響あり/なしの判定・提案・適用は行わない (提案・適用は C02、独立 verdict は C03 の責務)。
Marketplace から install した場合の呼び出し名は通常 `/spec-drift-guardian:spec-drift-triage`。

## 振る舞い

1. **入力パース**: `$ARGUMENTS` から `--issue NUMBER` を取り出す。
   - `NUMBER` は対象 GitHub issue 番号 (spec-drift 検知で起票済みのもの) を 1 件指定する。
   - `--issue` が無い / 番号が数値でない場合は argument-hint (`[--issue NUMBER]`) を表示し、**判定を行わず停止**する。issue 未指定時は「どの spec-drift issue をトリアージするか」を利用者に確認する案内を出す (例: `bd`/`gh issue list` などで対象 issue 番号を確認し `--issue <番号>` を付けて再実行する旨)。

2. **委譲起動 (C01)**: `Skill(run-spec-drift-triage, args="--issue <NUMBER>")` を起動する。
   - パス解決はすべて `$CLAUDE_PLUGIN_ROOT` 起点とし、本 command 側では scripts/schemas/references への直接パスを組み立てない (C11 aggregate → C08 parse → C09 map → triage の決定論段と参照解決は C01 skill が担う)。
   - C01 は対象 issue に紐づく全未triage完全 diff を `complete=true`/digest 一致で再構成し、hunk 単位に構造化した上で artifact kind/path と name/type/required/enum/semantics 各軸の before/after/evidence を判定し、`triage-report` schema 準拠のレポートを `$CLAUDE_PROJECT_DIR/.spec-drift/<issue>/triage-report.json` へ emit する。
   - 完全性を証明できない入力 (truncated preview 等) は C01 が fail-closed で拒否する。本 command はその結果をそのまま提示するだけで、判定を上書きしない。

3. **完了提示**: C01 が返す triage-report のパスと要約 (対象 issue、commit pair、影響ありと判定された artifact/軸の有無) をそのまま提示する。本 command は可否を判定しない (薄いラッパ)。

## 引数

| 引数 | 説明 |
|---|---|
| `--issue NUMBER` | トリアージ対象の spec-drift issue 番号 (必須)。C01 への passthrough |

## 失敗時

- `--issue` 未指定 / 番号が非数値: argument-hint を表示し、対象 issue 番号の確認方法を案内して停止する。
- C01 が入力の完全性を証明できず fail-closed: C01 の理由をそのまま提示して停止する (本 command 側で判定を代替しない)。

## 注意

- 本 command は起動の薄いラッパ。影響判定の設計品質は C01 skill (`run-spec-drift-triage`) が担い、独立 verdict は C03、提案・適用は C02 が担う。command 単体では影響有無を判定しない。
- 検知 (fetch/diff/issue 起票) は既存 workflow / ref-yaml-spec-fetcher の責務であり、本 command では再実装しない。
