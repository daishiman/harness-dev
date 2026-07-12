---
id: P01
phase_number: 1
phase_name: requirements
category: 要件
prev_phase: 0
next_phase: 2
status: 未実施
gate_type: none
entities_covered: []
applicability:
  applicable: true
  reason: ""
---

# P01 — requirements (要件定義)

## 目的
「システム構築 (Web/モバイル/タブレット/デスクトップ横断) に必要な仕様情報を、ユーザーとのヒアリングを通じて漏れなく収集し1つの仕様書へまとめるハーネス plugin」という構想を目的ドリブンに要件化し、後続フェーズが参照する `goal-spec.json` を確定させる。target_plugin_slug=`system-spec-harness` を固定し、対象プラットフォーム横断・網羅マトリクス機構 (C7)・設計知識反映・最新ドキュメント取得という外部依存/制約を開示する。

## 背景
DB・認証からUI-UX・セキュリティ・インフラ・バックエンド・フロントエンド・保守運用管理まで、システム構築に必要な情報は範囲が広く、単発の列挙やヒアリングだけでは抜け漏れが生じやすい。構想文中に列挙されたカテゴリは「一例」と明言されているため、個別カテゴリの過不足ではなくカテゴリ×プラットフォームの網羅マトリクス機構自体 (goal-spec C7) を本質要件として固定する必要がある。全 13 フェーズが参照する不変の goal-spec を最初に確定する。

## 前提条件
- プラグイン構想 1 件 (自然文 + 対象プラットフォーム追記) が入力として与えられている。
- 汎用の `run-goal-elicit` (harness-creator) が利用可能で、purpose/background/goal/checklist を `goal-spec.schema.json` で抽出できる (再実装しない)。
- このフェーズは特定 component へ紐づかない (責務は goal-spec 確定・target_plugin_slug 固定)。

## ドメイン知識
- 網羅マトリクス = システム構成カテゴリ×canonical platform id (`web`/`mobile`/`tablet`/`desktop-windows`/`desktop-linux`/`desktop-macos`) の全マスが「未収集/対象外/確定」のいずれかで埋まっている状態 (本 plan の goal 中核語・goal-spec C7 の実体)。カテゴリ表示4値はセル状態の真理値表から導出する。
- カテゴリ例示原則: DB/認証/UI-UX/セキュリティ/インフラ/バックエンド/フロントエンド/保守運用管理は「一例」であり、個別カテゴリの固定列挙ではなくマトリクス機構自体が要件。
- goal-spec は全 goal-seek 周回で不変のアンカー (target_plugin_slug/plan_dir を含め以降のフェーズが書き換えない)。
- 未決定事項は不足回答として再質問するだけでなく `needs_guidance` として扱う。最新公式根拠付き2〜3案（無料/低コスト案を含む）を目的適合で比較し、AI推奨はユーザー確認待ちにする。
- 設計知識の列挙はseed exampleであり上限ではない。referenceの価値は名称や要点ではなく、目的・背景・解決問題・適用/非適用・trade-off・goalへの寄与まで説明できる深度で判定する。
- 全responsibility promptはprompt-creator C1-C4/L5契約を受入対象とし、7層の見出し存在だけでPASSにしない。
- その他の plan 全体用語 (component_kind 等) は index `## ドメイン知識` を参照。

## 成果物
- `goal-spec.json` (purpose/background/goal/checklist(C1-C16)/constraints/handoff_targets/open_questions)。
- target_plugin_slug=`system-spec-harness` と plan_dir=`plugin-plans/system-spec-harness` の確定値。

## スコープ外
- component 分解・出力形式/ヒアリング機構独立性の設計判断 (P02 へ委譲)。
- ヒアリング機構の再実装 (`run-goal-elicit` を引用するのみ・再発明しない)。
- 実装・build (P05 と後段 builder の責務)。

## 完了チェックリスト
- [ ] `goal-spec.json` が purpose を非空で保持し、受入観点 (C1-C16) が purpose 語彙から導出されている。
- [ ] target_plugin_slug が ASCII kebab (`system-spec-harness`) で確定し以降のフェーズがそれを参照できる。
- [ ] `check-plugin-goal-spec.py` が exit0 (R1 goal-spec + plugin 固有アンカー充足)。
- [ ] goal-spec C9-C12 が上位概念、AI意思決定支援、open-world深い知識、prompt-creator準拠をそれぞれ独立criterionとして宣言する。
- [ ] goal-spec C13-C16 がdepends_on precedence DAGと型則、位相順消費、1 concern 1 doctrine authority+category全射、required-info最低形状/domain被覆/block停止/coverage certificateを独立criterionとして宣言する。

### 受入例 (満たす例 / 満たさない例)
- 満たす例: goal-spec.json の checklist が C1-C16 を持ち、C7のマトリクス、C9の上位概念、C10の意思決定支援、C11のdeep/open-world knowledge、C12のprompt品質、C13/C14の知識グラフDAG/位相順、C15のdoctrine anchor、C16の必須情報カタログ収集順序が独立criterionとして明記されている。
- 満たさない例: purpose が構想文の要約に留まり、対象プラットフォームの内訳が constraints に現れない / カテゴリ列挙が固定要件として書かれマトリクス機構 (C7) が欠落している。

### 事前解決済み判断
- 分岐点: 構想文中の列挙カテゴリ (DB/認証/UI-UX 等) を固定要件とするか → 判断: 「一例」と明言されているため例示扱いとし、網羅マトリクス機構 (C7) を本質要件に固定 (goal-spec constraints へ記録済み)。
- 分岐点: R1 自体がユーザーへ追加質問するか → 判断: しない (本構想文のみから goal-spec を確定・往復ヒアリングは build 後の C01 の責務)。

## 参照情報
- `references/purpose-driven-requirements.md` (目的ドリブン要件化の正本)。
- `schemas/plugin-goal-spec.schema.json` / `scripts/check-plugin-goal-spec.py`。
- 後続 P02 (この goal-spec を component 分解の入力とする)。
