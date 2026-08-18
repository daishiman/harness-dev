---
name: run-handout-extract
prefix: run
kind: run
hierarchy: L1
description: 既存の単一 HTML から構成データを逆抽出したいとき、手書き HTML を再利用可能な構成データへ戻してテンプレート化したいときに使う。
version: 0.1.0
owner: harness maintainers
source: plugin-plans/guide-doc-generator/component-inventory.json#C02
user-invocable: true
output_language: ja
argument-hint: "<html-path> [--out <handout-config.json>] [--report <extract-report.json>]"
allowed-tools: [Read, Write, Bash, Glob, Grep, AskUserQuestion]
depends_on: [C11, C12, C16, C20]
combinators:
  - with-goal-seek
  - with-feedback-contract
goal_seek:
  engine: inline
  fork: subagent
  max_loops: 5
completeness_exempt:
  - "manifest: goal_seek.engine=inline は未達 checklist から実行局面を都度選ぶため、固定 phase の workflow-manifest.json は適用外。停止条件と配線は本文 ## ゴールシーク実行 を正本とする。"
responsibilities:
  - id: R1-scan
    prompt_required: true
    summary: "対象 HTML を決定論抽出器にかけ、復元できた部品と復元不能な箇所を切り分ける"
  - id: R2-complete
    prompt_required: true
    summary: "復元不能箇所 (lead-line や判断軸など HTML から一意に定まらない意味情報) の補完方針を判断し構成データを確定する"
  - id: R3-roundtrip
    prompt_required: true
    summary: "確定した構成データを再レンダリングし、元 HTML との構成データ等価を判定して逆抽出レポートを返す"
responsibility_refs:
  - prompts/R1-scan.md
  - prompts/R2-complete.md
  - prompts/R3-roundtrip.md
script_refs:
  - ../../scripts/extract-handout-config.py
  - ../../scripts/validate-handout-config.py
  - ../../scripts/render-handout.py
  - ../../scripts/verify-handout-selfcontained.py
schema_refs:
  - ../../schemas/handout-config.schema.json
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
---

# run-handout-extract

## Purpose & Output Contract

入力は既存の単一 HTML 1 ファイルだけである (読み取り専用。元 HTML は書き換えない)。

出力は構成データ JSON と逆抽出レポートに閉じる。

1. **構成データ JSON** — `--out` で指定したパス。書式と正規化の正本は C12 の
   `validate-handout-config.py` とスキーマであり、本 skill が独自の書式を作らない。
2. **逆抽出レポート** — `--report` で指定したパスの JSON と、それを利用者向けに整形した提示。
   次の要素を必ず含む。
   - 復元した部品一覧 (各部品の fidelity が exact か heuristic か、heuristic なら根拠)
   - 復元不能箇所と採った補完 (キーパス / 理由 / 補完方針)
   - round-trip 差分 (`E-ROUNDTRIP-DIFF` の JSON Pointer と expected / actual)

資料内容の書き換え・改善提案はしない。読み手に向けて文章を書き直すことも、部品構成を
「こうした方がよい」と提案することも本 skill の範囲外である。資料の生成は C07
(`/handout-build`) の責務であり、本 skill は構成データを出すところで止まる。

### ゴール (Goal)

既存の単一 HTML から構成データ JSON が復元され、その構成データを再レンダリングした HTML が
元 HTML と構成データ等価であることが round-trip テストで確認された状態。

### 目的・背景 (Why)

手書きで作られた過去の資料を資産化するには、HTML から構成データへ戻す経路が要る。
戻せて初めてテンプレートとして反復配布できる。

### 完了チェックリスト

- [ ] 既存 HTML の走査 (C20 を起動し、その診断出力を素材として受け取った)
- [ ] 構成データの復元 (`--out` の構成データが手元にある)
- [ ] 復元不能箇所の補完判断 (キーパスごとに補完方針を選び、レポートへ記録した)
- [ ] round-trip 等価の確認 (再レンダリングと構成データ等価の判定まで通した)
- [ ] 復元できなかった意味情報を、利用者が埋められる形で提示した

## 逆抽出の入出力契約

### R1-scan — 走査は C20 の単独責務

`extract-handout-config.py --html <入力 HTML> --out <構成データ> --report <レポート>` を
Bash で起動する。HTML の走査と部品同定は C20 が唯一の逆写像実装であり、本 skill は
自前で HTML を parse しない。タグを読んで意味を当てにいく処理を skill 側に持った時点で、
逆写像の実装が 2 つになり、どちらが正かを誰も判定できなくなる。

C20 の stderr は診断コードで始まる行の集まりであり、そのまま R2 の作業台にする。

- `E-EXTRACT-UNRECOVERABLE <キーパス> <理由>` — 復元できなかった箇所。R2 の入力そのもの。
- `W-EXTRACT-HEURISTIC <キーパス> <採用した推定と根拠>` — マーカー無しでクラス名から
  同定した部品。復元結果には含まれるが fidelity は heuristic である。
- `W-EXTRACT-OPTIONAL <キーパス> <理由>` — 任意フィールドの欠落。
- `W-EXTRACT-CATALOG-DRIFT <キーパス> <内容>` — C20 が起動時に行う自己整合検査
  (部品カタログと照合表の突き合わせ) の報告であり、対象 HTML の性質とは無関係に出る。
  逆抽出の失敗ではないので、レポート整形でこれを不合格の根拠にしない。
  一般に `W-` で始まる行は fail 扱いしない。fail の判定は exit code と `E-` 行で行う。

exit code の読み方は次のとおりで、これを取り違えると成果物を取りこぼす。

- exit 0 — 復元が必須フィールドの欠落なく通った。
- exit 1 — 必須フィールドの欠落あり。`--report` は書かれ、`E-EXTRACT-UNRECOVERABLE`
  由来の欠落であれば `--out` も穴を null にしたまま書かれる。どちらも R2 の素材として読む。
- exit 2 — 起動の失敗 (入力不在、`--html` と `--out` が同一実体など)。`--out` も `--report` も
  書かれないため、素材が無い。引数を直して起動し直す。

`--compare` を付けた起動は round-trip 不一致のときに `--out` を書かない。R2 の作業台として
`--out` を使う起動と、比較のための `--compare` つき起動を、同じ 1 回の起動に兼ねさせない。
両方が要るときは別々に起動する。

### R2-complete — 推測しない補完

復元不能箇所は黙って欠落させない。キーパスごとに キーパス / 理由 / 補完方針 の 3 点セットを
レポートへ記録する。補完方針は 推測値の充填 / 空のまま残置 / 利用者への確認 のいずれかを
明示的に選ぶ。選ばずに済ませることも、記録せずに埋めることもしない。

`lead_line` / `judgment_axis` / section goal / `reader` / `prior_knowledge_level` /
`essential_problem` / `doc_type` は、対応する `data-hb-*` マーカーが無い限り推測しない
(C20 の never_guessed 規則)。これらは HTML の見た目から一意に逆算できない意味情報であり、
位置や見出しからそれらしい値を当てにいくと、誤った意図が正しいものとして以後の資料へ固定化される。
マーカーが無い箇所は null のまま残し、補完方針を 利用者への確認 として人の判断へ返す。

推測で埋めた値と HTML から実際に読み取った値は、レポートの fidelity (exact / heuristic) で
必ず区別する。heuristic の根拠は `W-EXTRACT-HEURISTIC` の行をそのまま添える。区別を落とすと、
利用者はどこを見直せばよいか判断できなくなる。

確定した構成データは `validate-handout-config.py` にかける。FAIL のときは欠落キーパスを
そのまま提示し、検証を通すために値を捏造することはしない。穴の空いた構成データは書き出したうえで
「そのままでは生成に使えない」と明示し、空の構成データを成功として返さない。

現時点では、マーカーを備えた HTML から復元した構成データであっても C12 を通り切らない
キーパスが残っている (レンダラ側のマーカー契約に対応する印が無い意味情報と、表示書式や
既定値の扱いが検証側の要求と噛み合っていない箇所)。これは構造的な穴として別途起票済みであり、
本 skill が値を作って埋めることで隠さない。復元できなかったものは復元できなかったものとして
利用者へ返す。

### R3-roundtrip — 構成データ等価で判定する

確定した構成データを `render-handout.py` で再レンダリングし、`verify-handout-selfcontained.py`
で自己完結性を確認したうえで、元 HTML との等価を判定する。目視の見比べで代替しない。

判定は正規化後の構成データ等価で行う。比較の前に両側を C12 の正規化へ通し、比較対象射影は
provenance ブロックを除いた残りとする。provenance は実行環境と catalog 版に依存するため
意味的同一性に属さない。HTML のバイト一致は課さない。バイト一致が課されるのは同一構成データ
からの再生成だけである。

不一致は `E-ROUNDTRIP-DIFF` として JSON Pointer と expected / actual を全件提示し、
差分ありを等価と読める要約にしない。差分の件数を減らして見せることは、逆抽出の信頼性を
測る唯一の手掛かりを捨てることに等しい。

## ゴールシーク実行

### ゴールシークループ

frontmatter の `goal_seek.engine: inline` / `fork: subagent` / `max_loops: 5` を実行契約とする。
固定手順は使わず、未達 checklist と担当 `prompts/<R-id>.md` からその周回の操作を都度組み立てる。
R1-scan → R2-complete → R3-roundtrip を素直な依存順とし、各周回で IN1 を、周回の完了後に
OUT1 を評価する。

### ゴールシーク配線

- 元のゴールを `eval-log/guide-doc-generator/run-handout-extract-goal-spec.json` へ、各 checklist の
  status と evidence を `eval-log/guide-doc-generator/run-handout-extract-progress.json` へ記録する。
- 未達 responsibility を担当する `prompts/<R-id>.md` を読み、分離 context へ fork する。
  利用者の判断が要る境界 (復元不能箇所の補完方針、`--out` の既存ファイル上書き) だけ
  `AskUserQuestion` を使う。
- inner ループ: R2 の確定結果を `validate-handout-config.py` にかける。FAIL なら欠落キーパスを
  素材に R1 の読み落としか R2 の補完判断へ戻る。値を作って通すことはしない。
- outer ループ: R3 の round-trip 判定。等価でなければ差分の JSON Pointer から R1 / R2 の
  どちらの取りこぼしかを切り分けて戻る。
- 各周回末に `eval-log/guide-doc-generator/run-handout-extract-intermediate.jsonl` へ
  `original_goal`、`original_goal_hash`、`current_goal_snapshot`、`delta_from_original`、
  `merged_directive_for_next`、`drift_signal` を append-only で記録する。次周回は直前の
  `merged_directive_for_next` を必須入力にする。
- 上限周回で未達が残れば完了扱いにせず、progress と blocker を親へ handoff する。

### ゴールシーク検証

各周回後に次を実行し、中間成果物の欠落と goal drift と hash 不一致を fail-closed にする。

```bash
python3 - "eval-log/guide-doc-generator/run-handout-extract-goal-spec.json" "eval-log/guide-doc-generator/run-handout-extract-intermediate.jsonl" <<'PY'
import hashlib, json, sys
goal = json.load(open(sys.argv[1], encoding='utf-8'))
rows = [json.loads(line) for line in open(sys.argv[2], encoding='utf-8') if line.strip()]
required_keys = {'original_goal','original_goal_hash','current_goal_snapshot','delta_from_original','merged_directive_for_next','drift_signal'}
expected = hashlib.sha256(goal['original_goal'].encode('utf-8')).hexdigest()
assert rows, 'intermediate.jsonl is empty'
for row in rows:
    assert required_keys <= row.keys(), required_keys - row.keys()
    assert row['original_goal'] == goal['original_goal']
    assert row['original_goal_hash'] == expected
PY
```

## Criteria acceptance

- **IN1** (inner / script): 逆抽出した構成データを `validate-handout-config.py` にかけて
  通っており、通らない場合は欠落キーパスが提示され、復元不能箇所が補完方針つきで
  レポートへ列挙されている。
- **OUT1** (outer / test): 復元した構成データを再レンダリングした HTML が元 HTML と
  構成データ等価であることを round-trip テストが確認した。等価でない場合は差分を全件
  提示したうえで未達として返す。

## Gotchas

- `W-` で始まる診断行を失敗として数えない。とくに C20 の自己整合検査に由来する
  `W-EXTRACT-CATALOG-DRIFT` は対象 HTML と無関係に出続けるため、これを根拠に
  逆抽出を失敗と報告すると利用者が原因を追えなくなる。
- exit 1 で終わった起動の成果物を捨てない。`--report` と (欠落由来なら) `--out` は残っており、
  それが R2 の作業台である。exit 2 のときだけ成果物が無い。
- 復元されない範囲を「復元された」と読める形で提示しない。ナビ・ヒーロー枠・アイコン sprite・
  CSS 変数・JS・footer・メモ UI は構成データから決定論生成されるものであり、復元対象ではない。
  これらが復元結果に部品として現れたらレンダラ側かマーカー側の不整合である。
- 逆抽出した構成データを資料生成へ回すのは利用者の判断である。次の一手として
  `/handout-build --config <出力パス>` を案内するに留め、本 skill が生成へ進まない。
- 出力ディレクトリ名を自前で組み立てない。日付と種別と主題からのディレクトリ名の決定は
  C19 の単独責務であり、本 skill は `--out` で指示されたパスへ書くだけである。
- 部品 id と用途語彙と粒度の値域を本文へ書き写さない。正本はそれぞれカタログ・用途語彙・
  構成データスキーマにある。
