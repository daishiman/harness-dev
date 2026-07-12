# system-spec-harness

システム構築 (Web/モバイル/タブレット/デスクトップ横断) に必要な仕様情報を、ユーザーとの往復ヒアリングで漏れなく収集し、章立て仕様書ドキュメントセットへまとめるハーネス plugin。

---

## Part 1 — これは何をするもの? (前提知識なしで読める説明)

最初に決めるのは技術ではなく、**何のために作るか**です。このpluginは、本質的目的・背景・ゴール・測定可能な目標・成功基準・関係者・範囲・制約・具体的に実現したいことをAIとの対話で確定し、すべての技術要件をそのゴールへ結びます。

背景には、システム構築の論点が広く、一度に全部を思い出そうとすると**抜け漏れ**や「手段の目的化」が起きる問題があります。そこでAIが質問をくり返し、目的から具体要件までを段階的に埋めます。

迷って決められない事項は、AIが最新の公式情報から2〜3案を比較し、無料または低コスト案を必ず含めて、目的適合・総費用・安全性・運用負荷・ロックインを説明します。AIは推奨理由・注意点・確信度を示しますが、ユーザー確認前に勝手に確定しません。

やり方はこうです:
1. AIが目的・背景・ゴール・成功基準などの**上位概念**を確認します。
2. 次にデータベース、認証、画面、安全対策、運用などの**具体要件**を質問します。
3. 迷った事項は比較案とAI推奨を示し、ユーザー確認後だけ確定します。
4. 回答をカテゴリ×プラットフォームの**表 (マトリクス)**へ反映し、未決定を再質問します。
5. 全マスが確定または理由付き対象外になると、目的へのつながりを保った仕様書へまとめます。

表の縦は「カテゴリ (データベース・認証・UI/UX・セキュリティ・インフラ・バックエンド・フロントエンド・保守運用)」、横は「プラットフォーム (Web・モバイル・タブレット・Windows・Linux・macOS)」。全部のマスが埋まっているかを、コンピュータが自動でチェックするので「聞き忘れ」が起きません。

一度「決まった」と確定した内容は、うっかり上書きされないように**ロック**されます。変えたいときは「もう一度考え直す」と宣言してからにします。

---

## Part 2 — 運用者向け技術詳細

### アーキテクチャ (14 component)
- **skill×5**: `run-system-spec-elicit` (C01・foundation/decision/matrix writer) / `run-system-spec-doc-fetch` (C02・最新公式情報/knowledge qualification) / `run-system-spec-compile` (C03・深い知識を含む仕様書生成) / `ref-system-design-knowledge` (C04・open-world deep knowledge seed) / `assign-system-spec-completeness-evaluator` (C05・全観点独立評価)。
- **sub-agent×3**: `system-spec-hearing-auditor` (C06) / `system-spec-matrix-auditor` (C07) / `system-spec-doc-freshness-auditor` (C08) — C05 が独立 context で fork する監査。
- **slash-command×2**: `/spec-hearing-start` (C09) / `/spec-compile` (C10)。
- **hook×1**: `guard-confirmed-chapter-overwrite.py` (C11・確定章の誤上書きを PreToolUse で fail-closed 遮断)。
- **script×3** (plugin-root 共有決定論ゲート): `validate-coverage-matrix.py` (C12・マトリクス網羅性) / `validate-source-citation.py` (C13・出典記録) / `validate-knowledge-graph.py` (C14・知識依存グラフ、doctrine、必須情報の整合)。

### データフロー
`spec-state.json` (C01 出力・単一 writer=`apply-spec-transition.py`) → C02/C03/C05/C07 が消費。`fetched-references.json` (C02 出力) → C03/C08 が消費。`system-spec/*.md`+`index.md` (C03 出力・章 frontmatter が C11 判定ソース) → C05/C11 が参照。

### 動線
1. `/spec-hearing-start` で往復ヒアリング開始。`--resume` で中断再開、`--status` で充足状況のみ表示。
2. 5周ごとに状態保存+resume で継続 (未収集セルを完了扱いしない)。
3. `/spec-compile` は未取得・古い出典があればC02を自動連鎖し、公式情報を準備してから章立て仕様書を生成する。
4. コンパイル完了後にC05完成度評価が自動連鎖する。

### 導入手順
- **local / dev**: 本リポジトリを clone 済みなら `plugins/system-spec-harness/` がそのまま利用可能。skill/command は `.claude/` symlink 経由で有効化 (`build-claude-symlinks.py` + `make sync`)。hook 配線は `.claude-plugin/plugin.json` の `hooks.PreToolUse` を settings へ反映。
- **marketplace**: `AVAILABLE (distributable:true)`。ユーザー承認により配布可能を確定済み (commit `00cf8f7`)。`.claude-plugin/marketplace.json` へ登録され、`harness-full` bundle に含まれる (`plugin.json` の `bundles` / `bundle_targets`)。導入は marketplace 追加後に `/plugin install system-spec-harness` で有効化する。
- **CLI / Desktop**: marketplace 配布済みのため、marketplace を追加した CLI / Desktop から同一手順でインストールできる。

### 検証
`python3 -m pytest -q plugins/system-spec-harness` (375 passed)。決定論ゲートは `plugins/system-spec-harness/scripts/validate-coverage-matrix.py` / `plugins/system-spec-harness/scripts/validate-source-citation.py` / `plugins/system-spec-harness/scripts/validate-knowledge-graph.py` / deep knowledge validator / prompt-creator validators。詳細は `RUNBOOK.md` / `docs/evidence.md`。

### 改善要望の受け皿
`/run-skill-feedback system-spec-harness` で改善要望を投入できる (`plugin_meta.feedback_deploy` に配線・初回は Notion sink 設定が必要)。

> 設計判断の正本は `plugin-plans/system-spec-harness/phase-02-design.md`。本 README は導入と概観のみで、設計判断を複製しない (ドリフト防止)。
