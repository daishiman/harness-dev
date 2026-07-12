---
description: 収集済み仕様情報を章立て仕様書ドキュメントセットへコンパイルする。コンパイル完了後に C05 完成度評価を起動する
argument-hint: "[--out-dir DIR]"
allowed-tools: Read, Bash, Skill
disable-model-invocation: false
name: spec-compile
kind: command
version: 0.1.0
owner: team-platform
since: 2026-07-11
entrypoint: run-system-spec-compile
---

# /spec-compile

`$ARGUMENTS` を `run-system-spec-compile` (C03) に渡し、foundation/decisions/確定セル/出典を章立て仕様書へコンパイルする。**完了後にC05を自動連鎖し、上位概念trace・意思決定・matrix・deep knowledge・鮮度・prompt品質をfail-closed評価する**。

Marketplace から install した場合の呼び出し名は通常 `/system-spec-harness:spec-compile`。

## 振る舞い (3 段フロー)

### 0 段目: 出典の自動準備 (C02)

- `targets[]`またはdecision evidence候補があり、対応する`fetched-references.json`が無い/古い/不足する場合は、ユーザーに別commandを要求せず`run-system-spec-doc-fetch`を自動起動する。
- C02が公式sourceを取得できない場合だけ、未確認targetと理由を示して停止する。対象が空なら`references: []`として継続する。

### 1 段目: 入力健全性の確認 → 仕様書ドキュメントセット生成 (C03)

1. **入力健全性ゲート (生成前・read-only)**: 収集マトリクスと**上位概念 (requirements_foundation U1-U9)・意思決定 (decisions)・出典記録**が生成に足る状態かを決定論検証する。違反 (exit1) があればコンパイルへ進まず、`spec-hearing-start` での追加収集 (foundation 未確定なら R0-foundation の完了) を案内して停止する (壊れた入力で章立てを組まない fail-closed)。下記「入力健全性ゲートの実行コード」を参照。
2. **コンパイル本体**: `Skill(run-system-spec-compile, args="$ARGUMENTS")` を呼ぶ。C03 が確定済みマトリクスと出典を章立て構造 (`system-spec/*.md` + 目次 `index.md`) へ写像し、各章に出典参照 (`fetched-references.json` の source_url) を紐づける。章立ての構造・出典差込み・書込みの正本ロジックはすべて C03 が所有し、本 command は引数受け渡しと 2 段連鎖の指揮のみを担う。`--out-dir DIR` はそのまま `$ARGUMENTS` として C03 へ渡り、出力先ディレクトリを差し替える。

### 2 段目: 完成度評価の自動連鎖起動 (C05)

3. **自動連鎖**: コンパイル正常終了時だけC05を独立contextで起動し、scoring-rubricの全観点を評価する。失敗・中断時は評価対象がないため起動しない。
4. C05 の verdict をユーザーへ提示する。不足観点があれば、どのカテゴリ/章を追加ヒアリングすべきかを C05 出力に沿って案内する。

## コンパイル前提: 出典取得 (C02 run-system-spec-doc-fetch)

`targets[]`やdecision候補がある場合は0段目がC02を自動連鎖し、`fetched-references.json`を用意してからgateを再実行する。通常動線は`/spec-hearing-start`→`/spec-compile`だけで完走し、内部skillの手動起動を利用者へ要求しない。対象が空なら空referencesで継続する。

## 入力健全性ゲートの実行コード

コンパイル前に、収集マトリクスの充足と出典記録の全件対応を決定論検証する (書き込みは一切しない)。

```bash
SSH="${CLAUDE_PLUGIN_ROOT:-plugins/system-spec-harness}"
SPEC_DIR="${CLAUDE_PROJECT_DIR:-.}/system-spec"  # spec-state.json の正本位置 (SSOT・hook 保護対象と同一)
# 収集マトリクスの網羅性 (未収集セル 0) + 上位概念 U1-U9・decisions・goalトレース (C9/C10) を一括検証
# --require-foundation は requirements_foundation の U1-U9 (値ありまたは明示 N/A) と
# validate_decisions (options 2-3件・free/low-cost 1件以上・user_decision 契約・goalトレース) も走らせる
python3 "$SSH/scripts/validate-coverage-matrix.py" --matrix "$SPEC_DIR/spec-state.json" --require-complete --require-foundation
# 取得対象一覧 ↔ fetched-references.json の出典を全件突合 (形式・全件・host 一致)
python3 "$SSH/scripts/validate-source-citation.py" --targets "$SPEC_DIR/spec-state.json" --references "$SPEC_DIR/fetched-references.json"
```

- 両者 exit0 = 章立てコンパイルに足る入力健全性 (網羅性 + 上位概念確定 + 意思決定契約 + 出典突合) を満たす。1 段目のコンパイル本体 (C03) へ進む。
- coverage/foundation gate exit1 (`VIOLATION:` あり):
  - `requirements_foundation:` 系違反 = 上位概念 (U1-U9) が未確定または未承認 (`confirmed` でない)。`spec-hearing-start` で **R0-foundation** を完了 (U1-U9 を値または明示 N/A で確定・U1/U2/U3 は値必須・ユーザー承認 `approval_ref` 付き) してから再実行するよう案内してコンパイルを中止する (C03 は起動しない)。
  - `decisions:` 系違反 = 意思決定 (C10) の options 2-3件/free・low-cost 候補/user_decision 契約違反。R5-decision-guide で decision record を整えてから再実行を案内する。
  - 未収集セル残り (matrix 系違反) = 収集不足。`spec-hearing-start` での追加収集を案内してコンパイルを中止する (C03 は起動しない)。
- citation gate exit1 (`VIOLATION:` あり):
  - `対象 target_id の参照欠落` = commandがC02を自動起動して取得し、再ゲートする。
  - `targets: 対象 target_id が空` (references は非空) = orphan 参照 → `spec-state.json` の `targets[]` を `apply-spec-transition.py set-targets` で整備するか、不要な参照を除去する。
  - host 不一致・必須フィールド欠落 = `run-system-spec-doc-fetch` で公式ソースを取り直す。
- citation gate exit2: targets/decision候補があればC02を自動起動し、空なら空referencesで継続する。

## 引数

| 引数 | 説明 |
|---|---|
| (なし) | 既定出力先 (`system-spec/`) へコンパイル → C05 完成度評価を自動連鎖 |
| `--out-dir DIR` | 章立て仕様書ドキュメントセットの出力先を `DIR` に指定 (`$ARGUMENTS` として C03 へ透過) |

## 注意

- 本commandはC02自動準備→C03コンパイル→C05評価を指揮する。
- 入力健全性ゲートはどのモードでも副作用なし (read-only)。`spec-state.json` 未生成なら先に `spec-hearing-start` で往復ヒアリングを完了させ、上位概念 (U1-U9) が未確定なら R0-foundation を先に確定させ、`fetched-references.json` 未生成 (かつ `targets` あり) なら先に `run-system-spec-doc-fetch` で出典を取得する旨を案内する (`targets` 空なら空 references で継続)。
- 完成度評価 (C05) はコンパイル成功時のみ自動起動する。生成物が無い状態で評価を走らせない (fail-closed)。
