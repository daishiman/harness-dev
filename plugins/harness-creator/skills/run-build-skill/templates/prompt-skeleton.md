---
name: {{CAPABILITY_NAME}}
description: {{PROMPT_TRIGGERS}}
kind: prompt
version: 0.1.0
owner: {{OWNER}}
since: "{{DATE}}"
layers:
  - {index: 1, title: 基本定義層, ref: "#layer-1"}
  - {index: 2, title: ドメイン定義層, ref: "#layer-2"}
  - {index: 3, title: インフラストラクチャ定義層, ref: "#layer-3"}
  - {index: 4, title: 共通ポリシー層, ref: "#layer-4"}
  - {index: 5, title: エージェント定義層, ref: "#layer-5"}
  - {index: 6, title: オーケストレーション層, ref: "#layer-6"}
  - {index: 7, title: ユーザーインタラクション層, ref: "#layer-7"}
self_evaluation: {{SELF_EVAL_REF}}
contract:
  intent: {{PROMPT_INTENT}}
  interface:
    invocation: {{INVOCATION_PATTERN}}
    output_shape: {{OUTPUT_SHAPE}}
  invariant:
    - Layer 1〜7 と Layer 5 の5.1〜5.4契約を満たす
    - 固定の推論手順ではなく目的・背景・達成ゴール・停止条件を宣言する
    - 本文の生成と検証をprompt-creatorで行い、未展開placeholderを完了扱いにしない
---

<!-- metadata-only scaffold: この殻だけは完成したpromptではない。 -->
<!-- run-prompt-creator-7layer が seven-layer-format.md 準拠の本文を生成する。
     新規形式はMarkdown。生成したLayer見出しへ上のrefと対応するidを付ける。
     本ファイルに本文骨格を再掲せず、Layer 5の5.1〜5.4とLayer 7を正本から生成する。
     validate-prompt.py、verify-completeness.py、lint-agent-prompt-content.pyがPASSし、
     prompt_provenanceをtraceへ記録するまでbuild完了ではない。 -->
