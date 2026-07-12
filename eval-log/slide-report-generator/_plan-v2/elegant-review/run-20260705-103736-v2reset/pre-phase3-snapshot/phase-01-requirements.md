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
既存 build 済 `plugins/slide-report-generator/`(23 component・289 files)の 16 sub-agent に集中した手続き知識・HTML/CSS規範・評価rubricの過重を解消し、skill 配下 references/scripts または plugin-root SSOT へ責務を再配置する後継設計 (`slide-report-generator-v2`) の要件を、既存機能を変えずに確定する。target_plugin_slug は既存と同一の `slide-report-generator` に固定し、plan_dir のみ `-v2` サフィックスで分離する。

## 背景
実測 (`wc -l plugins/slide-report-generator/agents/*.md`・2026-07-05 09:31 JST・component-inventory.json no_split_threshold.measured_at 参照) で 16 sub-agent (計 7,623行・html-generator.md 990行/structure-designer.md 682行/ui-quality-reviewer.md 672行/layout-optimizer.md 578行ほか平均476行) に手続き知識・評価rubricが直書きされる一方、3 skill (run-slide-report-generate/run-cross-deck-review/run-slide-report-modify) は SKILL.md 単体構成 (計413行) で references/・scripts/ を一切持たず progressive disclosure が機能していない。plugin-root references/ 51ファイル (直下46+feedback/5) も平置きで帰属が resource-map.md 頼み(散文・機械検証不能)になっている。これは repo 配置原則 (prompts/references=SSOT 正本・agents=薄いアダプタ) と逆転しており、機能追加でなく responsibility rebalance (責務再均衡) が真の目的である。既存 `plugin-plans/slide-report-generator/` (13 phase・build 完了済) は温存し、本計画は後継の再設計として独立生成する。

## 前提条件
- 既存 build 済 `plugins/slide-report-generator/`(23 component)の実ソース(agents/*.md の行数実測・skills/*/SKILL.md・references/*)が参照可能である。
- 既存 `plugin-plans/slide-report-generator/component-inventory.json`(23 component の build 軸 SSOT)と `index.md` が read-only 参照テンプレートとして利用できる。
- R1(goal-elicit)で確定済みの `goal-spec.json`(purpose/background/goal/checklist C1-C7/constraints/open_questions)が変更不可の入力として存在する。
- このフェーズは特定 component へ紐づかない(責務は goal-spec 確定・target_plugin_slug/plan_dir 固定の再確認)。

## ドメイン知識
- responsibility rebalance = 機能追加ではなく、既に存在する手続き知識・rubric・帰属情報の「置き場所」を repo 配置原則 (SSOT 正本=prompts/references・agents=薄いアダプタ) に沿って是正すること。
- no-split threshold = 分離 (sub-agent→skill) を無条件の善としない。分割判定は「分離コスト<分離便益」の観点で component ごとに根拠を残す(goal-spec constraints 由来)。
- 変更対象外の境界 = vendor Node engine (byte維持) と意匠/技術コア SSOT (schemas/vendor) は本計画の再設計対象外。再設計対象は agent⇔skill 間の情報配置境界のみ(goal-spec C7)。
- その他の plan 全体用語(component_kind / 5 種 buildable / 2 軸直交等)は index `## ドメイン知識` を参照。

## 成果物
- `goal-spec.json`(R1 確定済み・本フェーズでは再確認のみ・改変しない)。
- target_plugin_slug=`slide-report-generator` と plan_dir=`plugin-plans/slide-report-generator-v2` の確定値(既存 plan_dir との衝突回避が意図された暫定命名であることの明記)。
- 既存 23 component の実測根拠(sub-agent 行数分布・skill 構成比較)が要件の測定基盤として確立された状態。

## スコープ外
- component 分解・no-split threshold の個別判定(P02 へ委譲)。
- 実プラグインの build・既存ファイルの削除・上書き(本計画は L3 のみ・build 適用は後段の別セッションに委譲)。
- 既存 `plugin-plans/slide-report-generator/` とその build 成果物の変更(温存対象)。

## 完了チェックリスト
- [ ] `goal-spec.json` が purpose/background/goal/checklist(C1-C7)/constraints/open_questions を非空で保持し、責務再均衡という真の目的が purpose 語彙から読み取れる。
- [ ] target_plugin_slug が既存 plugin と同一の `slide-report-generator` に固定され、plan_dir のみ `plugin-plans/slide-report-generator-v2` で分離されている。
- [ ] 16 sub-agent の実測行数分布(baseline cluster 328-342行 / 過重 410-990行・measured_at=2026-07-05 09:31 JST)が要件の測定基盤として記録されている。
- [ ] `check-plugin-goal-spec.py` が exit0(R1 goal-spec + 再現性アンカー plan_dir==specfm.plan_output_dir 充足)。
- [ ] build 着工時に `wc -l plugins/slide-report-generator/agents/*.md` を再実測し、component-inventory.json の no_split_threshold.measured_at / measured_baseline_cluster を最新値へ更新してから P02 以降の判定を確定する(並行 build セッションによる数値陳腐化の再発防止)。

## 参照情報
- `goal-spec.json`(R1 確定済み正本)。
- `plugin-plans/slide-report-generator/component-inventory.json` / `index.md`(read-only 参照テンプレート)。
- `schemas/plugin-goal-spec.schema.json` / `scripts/check-plugin-goal-spec.py`。
- 後続 P02(この goal-spec を component 再配置設計の入力とする)。
