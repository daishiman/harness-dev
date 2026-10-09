# 正規形の言語と構造識別子

既存13プラグインの正規言語は維持する。日本語化した ubm-goal-setting の本文を英語へ戻さず、他の既存プラグインを一括翻訳しない。新規生成は ja/en を明示指定し、更新時の auto は対象の正規見出しから継承する。指定のない新規スキルは既存 output_language の既定 ja に従う。

日本語の表示見出しと英語の表示見出しは同じ構造IDの正規表現。スキーマのキー、メタ表のキー、Layer N、responsibility ID、Anchorのデータキーは言語非依存の識別子として維持する。本文は選んだ言語で書き、同一ファイルの目的・実行時ルート・選択前後の定型見出しやagentの2注入節を混在させない。既存定型の移行はマーカー付き生成ブロックだけを置換する。

agentは読み取り専用の助言役（advisor）と書き込み・検査役（writer）の2型で、共通の7層骨格を使う。許可ツールと役割の禁止事項を一致させ、Layer5は目的・背景・達成ゴール・完了チェックリスト・実行方式を持つ。決定論の操作制約はLayer3、依存順序と受渡しはLayer6で保持する。

生成器: build-subagent.py --language auto|ja|en --role auto|advisor|writer。スキル骨格: render-combinators.py --language ja|en|auto（autoは --target-skill 必須）、--has-prompts は実際にpromptsを所有するときだけ指定する。

## 配布の表示文

Codexの新規表示の既定値を日本語にする場合、`.codex-plugin-overrides.json` に `output_language: "ja"` を指定する。enも指定できる。既存プラグインは未指定なら従来のenを維持し、対象に既存interfaceがある場合はそのdisplayName/defaultPromptを優先する。schemaのcategory/capabilities値は構造識別子を維持する。

package-contract の codex_alternatives の purpose は表示文として同じlocaleで生成する。日本語の定型は「Claude のコマンド {name} を、所有する Codex スキルの経路から使えるようにする。」「Claude のエージェント {name} を、所有する Codex スキルの経路から使えるようにする。」。command/agent名とowner_routeの構造キーは訳さない。日本語の既存対象を更新するときに、この定型へそろえる。

## 生成・照合で使う表示名

| 構造上の役割 | en | ja |
|---|---|---|
| purpose_output_contract | Purpose & Output Contract | 目的と出力契約 |
| runtime_root | Runtime root contract | 実行時のルートの決め方 |
| pre_choice | Pre-choice usable artifact execution | 選ぶ前の実成果物の作成 |
| post_choice | Post-choice selected improvement execution | 選んだ深さでの改善の実行 |
| key_rules | Key Rules | 守ること |
| prompt_templates | Prompt Templates | プロンプトの型 |
| self_evaluation | Self-Evaluation | 自己採点 |
| assigned_agent | Assigned agent | 担当エージェント |
| goal_definition | Goal definition | ゴール定義 |
| completion_checklist | Completion checklist | 完了チェックリスト |
| achievement_goal | Achievement goal | 達成ゴール |

これは表示名の対応であり、Layer番号やschema keyを訳す指示ではない。上の2型骨格と各lintの正規見出しの行一致を保つ。
