# codex 接続仕様

## 前提

- `codex` CLI がローカルにインストール済み。`scripts/check-codex-installed.py` で確認する (`which codex && codex --version`)。
- 認証は CLI 側に委ねる (OpenAI API Key を `OPENAI_API_KEY` 環境変数で渡す)。本 Skill は credential を扱わない。
- 公式呼出契約は `doc/参考Skill/harness-creator/references/external-cli-agents-guide.md` の `codex` セクションを正本とする。

## 呼び出し形式

非インタラクティブモードで `--prompt` にレビュー指示・`--context-file` に request JSON、stdout を response として保存する。subcommand は提供されないため `--prompt` 直接指定。

```bash
codex --prompt "$(cat plugins/harness-creator/skills/delegate-codex-skill-review/prompts/R2-codex-review.md)" \
      --context-file eval-log/delegate-codex-request.json \
      --output-format text \
      --approval-mode yolo \
      > eval-log/delegate-codex-response.json
```

- `--prompt`: R2 プロンプト本文 (system + user を Markdown で連結)。
- `--context-file`: `R1-delegate.md` が生成した request JSON。`io-contract.schema.json` の `input` セクションに準拠。
- `--output-format text`: stdout を response JSON として受領 (パイプ先で schema 検証)。
- `--approval-mode yolo`: 委譲先での確認プロンプトを抑止 (read-only review のため)。

## 認証方式

- `OPENAI_API_KEY` を環境変数で渡す。本 Skill は値を読まず、ユーザー環境の設定に委ねる。
- credential を `eval-log/` に書き出さない (response JSON に混入しないこと)。

## I/O 契約

`schemas/io-contract.schema.json` を正本とする。input/output いずれも JSON。response は stdout から取得し、保存前に schema バリデーションを行う。

## 失敗時の挙動

- codex 未導入 -> verdict=skipped で正常終了 (`check-codex-installed.py` が exit 2)。
- codex タイムアウト -> 1 回までリトライ。それでも失敗なら verdict=skipped, severity=warn。
- 応答が schema 違反 -> verdict=fail (codex 側の責務不全として記録)。
