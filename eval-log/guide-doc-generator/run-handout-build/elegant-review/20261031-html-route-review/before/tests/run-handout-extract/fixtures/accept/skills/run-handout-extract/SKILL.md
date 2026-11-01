---
name: run-handout-extract
prefix: run
kind: run
hierarchy: L1
description: 既存の単一 HTML から構成データを逆抽出したいとき、手書き HTML をテンプレート化したいときに使う。
output_language: ja
source: plugin-plans/guide-doc-generator/component-inventory.json#C02
allowed-tools: [Read, Write, Bash]
depends_on: [C11, C12, C16, C20]
combinators:
  - with-goal-seek
  - with-feedback-contract
goal_seek:
  engine: inline
  fork: subagent
  max_loops: 5
responsibilities:
  - id: R1-scan
    prompt_required: true
    summary: "対象 HTML を決定論抽出器にかけ、復元できた部品と復元不能な箇所を切り分ける"
  - id: R2-complete
    prompt_required: true
    summary: "復元不能箇所の補完方針を判断し構成データを確定する"
  - id: R3-roundtrip
    prompt_required: true
    summary: "確定した構成データを再レンダリングし、構成データ等価を判定して逆抽出レポートを返す"
responsibility_refs:
  - prompts/R1-scan.md
  - prompts/R2-complete.md
  - prompts/R3-roundtrip.md
script_refs:
  - ../../scripts/extract-handout-config.py
  - ../../scripts/validate-handout-config.py
  - ../../scripts/render-handout.py
  - ../../scripts/verify-handout-selfcontained.py
feedback_contract:
  criteria:
    - id: IN1
      loop_scope: inner
      text: "逆抽出した構成データが validate-handout-config.py を通り、復元不能箇所が補完方針つきでレポートへ列挙される"
      verify_by: script
    - id: OUT1
      loop_scope: outer
      text: "復元した構成データを再レンダリングした HTML が元 HTML と構成データ等価であることを round-trip テストが確認する"
      verify_by: test
    - id: OUT2
      loop_scope: outer
      text: "実在の手書き HTML 1 本を与えた実起動で、元 HTML を 1 バイトも書き換えず、復元不能箇所が補完方針つきでレポートへ列挙され、資料内容の書き換えや部品構成の改善提案を出力に含めないことを実走の痕跡で確認する"
      verify_by: live-trial
---

# run-handout-extract

## Purpose & Output Contract

既存の単一 HTML を構成データへ戻し、別テーマの新規資料の出発点にできる状態を作る。

出力は 2 つだけである。

1. **構成データ JSON** — `--out` で指定したパスに 1 ファイル。書式は C12 の規約に従う。
2. **逆抽出レポート** — `--report` で指定したパスに 1 ファイル。次の 3 要素を必ず含む。
   - 復元した部品一覧 (各部品の fidelity が exact か heuristic か)
   - 復元不能箇所と採った補完 (キーパス / 理由 / 補完方針)
   - round-trip 差分 (JSON Pointer / expected / actual)

資料内容の書き換え・改善提案はしない。資料の生成は C07 (`/handout-build`) の責務であり、
本 skill は構成データを出すところで止まる。

### ゴール (Goal)

既存の単一 HTML から構成データ JSON が復元され、その構成データを再レンダリングした HTML が
元 HTML と構成データ等価であることが round-trip テストで確認された状態。

### 目的・背景 (Why)

手書きで作られた過去の資料を資産化するには、HTML から構成データへ戻す経路が要る。
戻せて初めてテンプレートとして反復配布できる。

### 完了チェックリスト

- [ ] 既存 HTML の走査
- [ ] 構成データの復元
- [ ] 復元不能箇所の補完判断
- [ ] round-trip 等価の確認

## ゴールシーク実行

### ゴールシークループ

R1-scan → R2-complete → R3-roundtrip を 1 周とし、OUT1 が満たされるまで最大 5 周する。

**R1-scan.** `extract-handout-config.py --html <入力> --out <構成データ> --report <レポート>` を
Bash で起動する。HTML の走査と部品同定は C20 が唯一の実装であり、本 skill は
自前で HTML を parse しない。C20 の stderr に出る `W-EXTRACT-HEURISTIC` (クラス名推定で
復元した部品) と `E-EXTRACT-UNRECOVERABLE` (復元できなかったキーパス) を、
そのまま R2 の作業台として受け取る。

**R2-complete.** 復元不能箇所ごとに補完方針を 1 つ選び、レポートへ キーパス / 理由 / 補完方針 の
3 点セットで記録する。補完方針は 推測値の充填 / 空のまま残置 / 利用者への確認 のいずれかであり、
黙って欠落させることはしない。`lead_line` / `judgment_axis` / section goal / `reader` /
`prior_knowledge_level` / `essential_problem` / `doc_type` は、`data-hb-*` マーカーが無い限り推測しない
(C20 の never_guessed 規則)。推測しない箇所は null のまま残す。
推測で埋めた値と HTML から実際に読み取った値は、レポートの fidelity (exact / heuristic) で必ず区別する。

**R3-roundtrip.** 確定した構成データを `render-handout.py` で再レンダリングし、
`verify-handout-selfcontained.py` で自己完結性を確認したうえで、元 HTML との等価を判定する。
判定は正規化後の構成データ等価で行う。比較対象射影は provenance ブロックを除いた残りであり、
HTML のバイト一致は課さない (バイト一致が課されるのは同一構成データからの再生成だけである)。
不一致は `E-ROUNDTRIP-DIFF` として JSON Pointer と expected / actual を全件出し、
差分ありを等価と読める要約にしない。

### ゴールシーク配線

- inner ループ: R2 の確定結果を `validate-handout-config.py` にかける。FAIL のときは
  欠落キーパスを提示し、検証を通すために値を捏造することはしない。穴の空いた構成データは
  書き出したうえで「そのままでは生成に使えない」と明示し、空の構成データを成功として返さない。
- outer ループ: R3 の round-trip 判定。EQUIVALENT でなければ R1 の読み落としか R2 の補完誤りへ戻る。

### ゴールシーク検証

各周の終わりに IN1 と OUT1 の充足を判定し、未充足なら次周へ入る。5 周で未達なら
未達のまま結果を返す (通ったことにしない)。

## Criteria acceptance

- **IN1** (inner / script): `validate-handout-config.py` が exit 0 を返し、復元不能箇所が
  補完方針つきでレポートへ列挙されていること。
- **OUT1** (outer / test): round-trip テストが構成データ等価を確認したこと。
- **OUT2** (outer / live-trial): 実起動で元 HTML を書き換えず、復元不能箇所が補完方針つきで
  レポートへ列挙され、改善提案を出力に含めないことを確認したこと。

## Gotchas

- 逆抽出結果を `/handout-build --config <出力パス>` へ渡すのは利用者の判断であり、
  本 skill が生成まで進めることはない。
- `data-hb-generated="true"` の部分木 (nav / hero / sprite / footer / メモ UI) は
  C20 が読み飛ばす。復元された構成データにこれらが parts として現れたら C11 側のバグである。
