# merged_directive (anchor)

## original_goal (不変)
plugins/skill-creator を「ハーネスクリエイター (harness-creator)」へ改名し、repo 全体の依存関係（symlink/vendoring/lint/CI/denylist/SSOT定数/テスト/ドキュメント）を抜け漏れなく追従させる。理由: このプラグインで構築しているのはスキルではなくハーネスだから。

## delta (2026-07-02 ユーザー追加指示)
「スキルを作る」概念と「ハーネスを作る」概念の両方をしっかり構築できる状態にする。

## 意味論境界ルール (確定・Phase 2/3 の判定基準)
1. **単体スキルを作る概念** → 「スキル / skill」表現を維持する。
   - 例: run-skill-create / run-build-skill 等、単一 skill を生成・改善・改名する系統。
2. **ハーネス全体を構築する概念**（skill/agent/hook/command/評価/統治の総体を作るメタ能力）→ 「ハーネス / harness」表現へ変更する。
   - plugin 名 skill-creator → harness-creator、日本語表記 スキルクリエイター → ハーネスクリエイター を含む。
3. 適用レベル: **ファイル名・ディレクトリ名・各内容（本文）・項目の内容のすべて**。機械的一括置換ではなく、各出現箇所の概念（単体スキル生成 or ハーネス全体構築）を判定して適用する。
4. 既存の harness 語（harness-coverage-spec / meta-harness 等 = 構築物総体の品質仕様）は「ハーネス全体」概念と同系であり、衝突ではなく統合先として整合させる。
