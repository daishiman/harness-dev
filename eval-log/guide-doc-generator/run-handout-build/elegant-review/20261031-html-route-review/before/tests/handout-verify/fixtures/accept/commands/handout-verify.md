---
name: handout-verify
description: "既存の資料 HTML に自己完結性 (C16)・a11y と印刷 (C17)・言語と日付 (C18)・語りの一貫性 (C22) の 4 ゲートを手動で掛け、pass / fail / error / not-run の 4 状態で集約する"
argument-hint: "<html-path> [--config <config.json>] [--out-dir <path>] [--only <gate,...>] [--json-report <dir>]"
allowed-tools: [Read, Bash]
disable-model-invocation: false
source: "plugin-plans/guide-doc-generator/component-inventory.json#C09"
output_language: ja
---

# /handout-verify — 検証ゲート 4 面の集約入口

この command は read-only の集約入口である。資料の生成 (C07) も逆抽出 (C08) も
構成データの正規化 (C12 --normalize) も行わない。検査対象の HTML と構成データを
書き換えることはなく、書き出すのは `--json-report` で指示されたファイルだけである。

## 引数の既定値と上書き

| 引数 | 既定値 | 上書き規則 |
|---|---|---|
| `html-path` (positional, 必須) | なし | 検証対象の単一 HTML ファイル。全ゲートへ `--html` として同じ値が渡る。ディレクトリを渡された場合は展開せず停止する |
| `--config` | なし。未指定なら language / narrative の 2 ゲートが not-run になる | 正規化済み構成データを指す。この command は正規化を行わない |
| `--out-dir` | なし。未指定なら html-path の親ディレクトリを language ゲートへ渡す | ディレクトリ名の `<YYYY-MM-DD>` と構成データ日付フィールドの一致検査に使う |
| `--only` | なし。未指定なら 4 ゲート全実行 | gate_id をカンマ区切りで指定する。未知の gate_id は停止する |
| `--json-report` | なし。未指定なら各 script の stdout / stderr のみを集約する | 各ゲートの JSON と集約サマリをこのディレクトリへ置く |

## ゲート 4 面と起動する script

script は `${HB_ROOT:-$CLAUDE_PLUGIN_ROOT}/scripts/<script>.py` として解決し、Bash で順に起動する。

| gate_id | component | script | argv |
|---|---|---|---|
| selfcontained | C16 | `verify-handout-selfcontained.py` | `--html` `--json-report` |
| a11y-print | C17 | `verify-handout-a11y-print.py` | `--html` `--json-report` |
| language | C18 | `verify-handout-language.py` | `--html` `--config` `--out-dir` `--json-report` |
| narrative | C22 | `verify-handout-narrative.py` | `--html` `--config` `--json-report` |

## 集約規則 (単一正本)

ゲート結果の 4 状態分類と全体 verdict の規則は、この command が持つ単一正本
`CR-GATE-AGG` である (P03 Y-07)。C01 `run-handout-build` の R4-verify は自前で
集約せずこの command を起動し、同一の 4 ゲート実行結果に対しては必ず同一の
verdict を受け取る。not-run を pass 側へ畳む経路は存在させない。

- exit 0 -> pass
- exit 1 -> fail
- exit 2 -> error (検査器自体の異常。資料の合格の証拠にはならないので fail 側へ倒す)
- 実行しなかった / できなかったゲート -> not-run (理由必須)

```json
{
  "id": "CR-GATE-AGG",
  "owner": "C09 /handout-verify",
  "gate_faces": {
    "selfcontained": "C16",
    "a11y-print": "C17",
    "language": "C18",
    "narrative": "C22"
  },
  "states": ["pass", "fail", "error", "not-run"],
  "not_run_reasons": [
    "config-missing",
    "config-not-normalized",
    "excluded-by-only",
    "script-absent"
  ],
  "verdict_table": [
    {"when": {"any_state": ["fail", "error"]}, "verdict": "fail"},
    {"when": {"only_used": true}, "verdict": "partial"},
    {"when": {"any_state": ["not-run"]}, "verdict": "incomplete"},
    {"when": {"all_states": ["pass"]}, "verdict": "pass"}
  ]
}
```

## 縮退時の挙動

- `html-path` 未指定 / 不在 / ディレクトリ指定: 1 ゲートも実行せず停止する。空の集約結果を pass として返さない
- `--config` 未指定: selfcontained / a11y-print は実行し、language / narrative は not-run (config-missing)。全体 verdict は incomplete
- `--config` が未正規化: `validate-handout-config.py --strict` (書き込みなし) で検出し、language / narrative を not-run (config-not-normalized) とする。この command 側で正規化して通すことはしない
- script が見つからない: 当該ゲートを not-run (script-absent) とし、解決を試みたパス (HB_ROOT / CLAUDE_PLUGIN_ROOT / __file__ 相対) を提示する
- `--only` で除外したゲート: not-run (excluded-by-only)。成功時でも全体 verdict は pass ではなく partial に固定する
- `--only` に未知の gate_id: 1 ゲートも実行せず停止し、有効な gate_id 一覧を示す
- あるゲートが落ちても後続ゲートを止めずに全ゲートを走らせる (fail-fast にしない)

## 報告

報告には必ず 4 ゲート全部を行として出す。実行しなかったゲートを表から省かない。
各行に gate_id / 状態 / 理由または違反件数 / 該当箇所 (行番号・section id・キーパス) を出す。

`--json-report` 指定時は各ゲートの JSON を `<gate_id>.json` として、集約サマリを
`summary.json` として同ディレクトリへ置く。集約サマリは全体 `verdict` と 4 面の
`gates` 状態一覧を含む。

全体が pass でない場合は次の一手を案内する。fail は該当箇所の修正を、
config-missing による not-run は `/handout-build` が出力ディレクトリへ同梱した
構成データを `--config` に渡すことを示す。この command 自身は生成も修正も行わない。
