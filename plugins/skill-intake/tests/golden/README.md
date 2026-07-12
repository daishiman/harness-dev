# skill-intake golden test

目的: **同一入力 -> 同一出力**(誰が実行しても同じヒアリングシートに収束する)ことを機械保証する CI ゲート。

doc/impl drift (C3) と再現性欠如を防ぐため、以下 2 ゲートを検証する。

| ゲート | 内容 | 合格条件 |
|---|---|---|
| G1 冪等性 | `fixtures/sample-answers.json` を `build-intent.py` に 3 回通す | `intent_contract` 部の sha256 が 3 回とも一致 |
| G2 完全性 | `fixtures/sample-intake.json` を `check_completeness.py --mode all` に通す | section required_fields + §6 intent_contract 全充足で exit 0 |

## 実行

```
python3 plugins/skill-intake/tests/golden/run-golden.py
```

exit 0 = PASS / exit 1 = FAIL。結果 JSON を stdout に出力する。

## 構成

- `fixtures/sample-answers.json` : 全 9 intent slot を充足する代表回答 1 件。
- `fixtures/sample-intake.json` : 全 section の block 必須項目 + §6 intent_contract を充足する代表 intake 1 件。
- `run-golden.py` : 単体で CI (例: `ci_dogfooding_retest.py`) から呼び出せる自己完結スクリプト。CI 設定は本ディレクトリでは変更しない (orchestrator 委譲)。
