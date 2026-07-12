# Phase 1 俯瞰レポート (elegant-reset-observer, 2026-07-04 run 20260704-192038)

対象: plugin-plans/skill-intake/ (全21ファイル)

## FILE_INVENTORY
- index.md: 計画正面玄関。plugin_meta frontmatter+基本定義/ドメイン知識/インフラ(core 6ゲート・surface採否表)/環境ポリシー/13 phase一覧/完了チェックリスト/受入確認表
- goal-spec.json: 要件正本。purpose/background/goal/checklist C1-C8/constraints 12件(うち4件は「R2/P02解決済み事項」)/max_loops=5/open_questions=[]
- component-inventory.json: buildable 4 component の機械SSOT。derivation/各componentのchecklist/feedback_contract/quality_gates/plugin_level_surfaces
- handoff-run-plugin-dev-plan.json: builder向けroutes(top-sort C01→C02→C03→C04)+envelope n/a+open_issue GAP-SCRIPT-BUILDER
- phase-01〜13: 13 phase仕様書(requirements/design/design-review/test-design/implementation/test-run/acceptance/refactoring/qa/final-review/evidence/documentation/release)
- run-plugin-dev-plan-progress.json: iteration=2・C1-C8全covered・10ゲートPASS・status=planned-ready
- run-plugin-dev-plan-intermediate.jsonl: goal-seek 2周回アンカー
- plan-findings.json: R4独立evaluator verdict=PASS・11 gate結果・findings4件
- elegant-review-20260704.md: 前回elegant-review。適用済みfindings8件・30思考法トレース・4条件PASS

## FIRST_IMPRESSIONS (18件)
1. [contradiction] phase-13-release.md:19「run-skill-create/run-plugin-dev-plan は本改善では不要、build 実行者自身が C01-C04 を直接実装」 vs handoff routes の C01/C03 builder=run-skill-create、index.md:73「skill route (C01/C03) は run-skill-create へ渡す」。builder 契約が正面衝突
2. [omission] handoff:19,54 build_args.brief_path が briefs/skill-brief-C01.json / C03.json を参照するが plan_dir 配下に briefs/ 不在
3. [inconsistency] index.md:73「script route (C02/C04) は plugin-scaffold が消費」と無条件記述 vs handoff open_issues GAP-SCRIPT-BUILDER「plugin-scaffold は contract-only で単独実行実体未整備」。index に gap 言及なし
4. [inconsistency] スキーマ名の揺れ: phase-01:28 は run-intake-interview/schemas/output.schema.json、phase-01:44(G3)/phase-08:35 は「interview.schema.json」別名参照。後者は plan 内定義に存在しない
5. [inconsistency] true_purpose のフィールドパス二重表現: interview.json 側 five_axes.rows[name="真の課題"].content vs intake.json 側 sections.6_five_axes_summary.axes[axis_id="real_problem"].answer。rows[name]↔axes[axis_id] 対応の明示なし
6. [dependency] C01.deterministic_checks に C02 の validate-procedure-completeness.py が含まれるが C01.depends_on=[]。build DAG は C02.depends_on=[C01] で runtime 消費方向と逆。C01 build 時点で C02 未存在期間の扱い未記述
7. [inconsistency] phase-05:35 C03「成功時のみ C02 stdout を intake.json.validation.procedure_completeness へ格納」 vs phase-05:36/phase-06:32 C04「validation.procedure_completeness.contamination.detected=true → exit 1」。成功時のみ格納なら contamination=true が intake.json に載る経路が仕様上存在しない
8. [inconsistency] index.md:72「同梱決定論ゲート core 6 起動」 vs progress.json verification_status 10本 / plan-findings.json gate_results 11本。core 6 と残り4-5本の関係が index に記載なし
9. [smell] ID 名前空間衝突(1): phase-01 ギャップ G1-G7 vs plan-findings.json gate_results id G1-G11。同一略号 G が別概念
10. [smell] ID 名前空間衝突(2): elegant_review 条件 C1-C4 vs goal-spec checklist C1-C8。index.md:89 が「別名前空間」注記で回避
11. [smell] goal-spec.json constraints[8..11] に「R2/P02 解決済み事項」4件。constraint と decision の意味論混合
12. [inconsistency] phase-11:30「feedback_contract.criteria の verify_by: live-trial に相当」 vs component-inventory の全 criteria verify_by は script/test/elegant-review のみで live-trial 不在
13. [smell] phase-13 frontmatter next_phase: 14 が存在しない phase を指す。番兵規約の説明が plan 内に無い
14. [smell] P02-P13 の entities_covered が一律 [C01,C02,C03,C04] 全列挙。orphan 検出が実質無条件 PASS になる構造
15. [dependency] elegant-review-20260704.md と plan-findings.json (R4) の時系列・優先関係がどちらにも明記なし
16. [inconsistency] component-inventory C01.output_contract「sheet.md への procedure 節追記」 vs phase-05:33(4)「sheet.md/sheet.json は runtime 出力物、実装制御点は question-plan.json 等」。旧表現が inventory 側に残存
17. [omission] contamination check は to-be-vocabulary-patterns.md 語彙照合方式だが、語彙集に無い表現の検出限界への言及が phase-04/05/11 に無い
18. [dependency] gate_type 語彙と §5 section 床の正本が plan 外 (plugin-dev-planner の specfm.PHASE_BODY_SECTIONS/GATE_SCRIPTS)。plan 単独では語彙妥当性を検証できない。tdd-green が P05 (実行なし) で P06 が gate_type=none の名目性

## 親セッションで取得済みのベースライン機械検証 (事実)
- check-plugin-goal-spec.py plugin-plans/skill-intake/goal-spec.json → OK
- verify-plan-coverage.py plugin-plans/skill-intake/component-inventory.json → FAIL: C02 (plugins/skill-intake/scripts/validate-procedure-completeness.py) 計画にあって実体なし (plan は build 前 planned-ready 状態である点に注意)
