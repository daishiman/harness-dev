# UBMの内容評価と背景品質

この正本は、6つの `run-ubm-*` をレビューする親と独立evaluatorが参照する。UBMのL1は `skills/run-ubm-knowledge-sync/references/rubric.json` に置き、`skill-governance-config/config/rubric-registry.json` の `domain: ubm-goal-setting` で登録する。既存のL0→L1→L2合成を使い、KL-002の背景基準だけを適用する。severity・重み・閾値・他ルール・他5フィールドの品質基準は変えない。同じIDのcheckだけを合成するので、基準を二重に採点しない。

## 評価への注入

この作業ツリーでは、親が解決した絶対パスを使って次を実行する。

```bash
python3 "$PLUGIN_ROOT/scripts/evaluate-design-rubric.py" --repo-root "$HARNESS_ROOT" --target "$PLUGIN_ROOT/skills/<run-ubm-入口名>/SKILL.md"
```

runnerはUBMの実manifest・対象の帰属・登録済みL1の所在を確認して、既存の `render-findings-score.py` へL0、登録L1、既存L2の順で渡す。登録が無い・重複する・別ドメインの対象・L1の差替えは終了コード2で止める。インストール先でレビューする場合も、親は同じ登録済みL1と依存evaluatorの実パスを解決して、その3パスを既存CLIの `--rubric-refs` に渡す。registryの登録だけで自動注入されたとはみなさない。

親は実際に使ったrefs、各SHA、composition hashを評価証拠へ残す。他ドメインにこのL1を注入しない。未登録・未注入のschemaを暗黙のrubric overrideとして使わない。

## 背景の意味評価

現在の全エントリを対象とし、サンプルや固定件数で打ち切らない。背景は原文根拠の適用状況と、判断が必要になる理由・制約・比較・失敗条件を2〜5文で具体的に示す。抽象一文、同じ助言の言い直し、文字数を増やすだけの補強、原文に無い事実は不合格にする。固有の業種・特定数値・個人名・会社名は背景へ入れず、原文・出所の情報を保全する。

増補・再構成は既存カードの根拠あるフィールドか、実際に読んだ元資料から行う。旧背景全文、採用元、元資料を読んだ場合の該当箇所、before/after SHAを移行証拠へ残す。カードfieldから補っただけなら、未読の元資料まで照合済みと主張しない。根拠が足りなければFAILを維持する。

機械採点は6フィールドの実在を確認する。出力のsemantic pendingは独立評価への引き継ぎであり、機械だけで解消してはならない。evaluatorは実際の合成結果にあるKL-002.checkと全エントリを読んで意味品質を判定する。背景以外はL0の品質表でレベル2以上を確認する。静的設計のPASSをlive-trialや実利用者の受入れへ転用しない。
