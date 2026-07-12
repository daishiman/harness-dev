# elegant-review レポート: prompt-creator 宣言型転換 (run 20260702T065933)

- 対象: `plugins/prompt-creator` (plugin scope)
- 要求: 命令型 (固定手順列挙) のプロンプト構造を、ゴール定義+評価基準+受け入れチェックリスト中心の**宣言型**へ転換し、宣言型プロンプトを再現性高く量産できる仕組みにする。7 層構造は維持。改善実施は skill-creator 機構 (goal-seek paradigm / feedback_contract / lint 群) 経由。
- 判定: **4 条件 (矛盾なし/漏れなし/整合性あり/依存関係整合) 全 PASS**、status=complete、human_review_required=false。

## 実行経緯

| Phase | 内容 |
|---|---|
| 1 思考リセット | `elegant-reset-observer` が先入観破棄のうえ全ファイル俯瞰。核心観測=「自己言及ギャップ」(生成物にはゴールシークを強制、自身は命令型) |
| 2 並列分析 | 3 analyst が 30 思考法 (A2=10/A3=9/A4=11) を全適用、findings 43 件 (A2 系は A2-13 欠番の 15 件)。3 体が独立に同一結論へ収束: **rubric (C3-004/C4-001) が命令型構造を合格条件化し、宣言型生成物を FAIL させて命令型へ引き戻す自己強化ループ**が根本欠陥 |
| 3 改善 (直列 Wave) | 依存順序固定: Wave 1 正本確定 → Wave 2 rubric 書換 → Wave 3a/3b/3c 並列 (orchestrator/elicit+agents+root/worker+機械層) → Wave 3.5 evaluator+残ギャップ → 独立 content-review が実バグ検出 → Wave 3.6 修正 |
| 4 検証 | 機械 4 条件判定+30 思考法カバレッジ検証 (validate-paradigm-coverage exit 0) |

## 主要成果

1. **l5-contract v2.0.0** (seven-layer-format.md「Layer 5 契約」節): 5.2 ゴール定義 / 5.3 完了チェックリスト (停止条件) / 5.4 実行方式 (6 ステップ+Anchor)。旧「5.2 推論手順 / 5.3 自己検証 checklist」は廃止。テンプレ・rubric・lint・prompts の 4 者が従属。
2. **rubric v2.0.0**: 手順の具体性でなく「成果状態+検証可能チェックリスト+機械アンカー (schema/script_refs)」を再現性根拠に。数量レンジ (3-7 ステップ/5-8 項目) 全廃。曖昧語検査はチェックリスト項目内に限定しゴールシーク正準文言を allowlist 化。
3. **宣言型材料の契約化**: prompt-brief.schema.json に goals[]/checklist[] (required)/purpose/background/user_confirmed。standalone モードは if/then/else 条件分岐で機械検証と両立。evaluation_priorities は enum SSOT (日本語 5 値・最大 2)。
4. **dogfooding 達成**: 自プロンプト 6 本+SKILL.md 4 本+agents 3 体を宣言型へ転換。機械 baseline: **before 6/6 FAIL → after 6/6 PASS** (verify-completeness、同一コマンド列)。
5. **機械ガード**: verify-completeness 検出強化 (「推論手順/手順/Steps」配下の連番列挙を FAIL)+--layers+failfast、self-scan 自己適用テスト (中央 pytest 配線、回帰を exit 非 0 遮断)、parity テスト (lint-agent-prompt-section 双方向互換)、worker 内蔵 phase-design-gate (呼出経路非依存の C1-C4 評価)、Phase 4-C 中間アンカー (goal-seek-loop schema 正本参照)。
6. **経路一本化**: ヒアリングは run-prompt-elicit へ委譲一本化。brief 供給時は Phase 1-3 の全ユーザー対話 skip を invariant 化。dangling 参照は全数修正。

## 独立検証 (proposer ≠ approver の内訳)

- content-review verdict 8 件 (4 skill × elegance/rubric) を独立レビュアー 3+1 体が現 SHA で genuine 再生成。**elicit レビュアーが実バグ (standalone×schema 両立不能, high) を検出し FAIL** → Wave 3.6 修正 → iteration 2 で全 8 件 PASS (レビュアーは executor 未提示の負例まで独自追加し 8/8 機械検証)。
- 中央 pytest: **5876 passed / 4 skipped** (最終状態)。plugin lint (skill-tree/frontmatter/feedback-contract/agent-prompt-section ほか) 全 exit 0。

## Deferred (いずれも condition_signal=smell、PASS 非阻害)

| id | 内容 | 理由 |
|---|---|---|
| A3-05 | 評価・統治機構が skill-creator 系と二重系 → 一重化 | 宣言型転換と独立の大規模再編。prompt 固有検査 (C1/C2) は独自維持が正当 |
| A3-10 | 新規小型 prompt 向け fast-new 軽量経路 | 量産実績が立ってから判断 |

## 成果物一覧 (本 run ディレクトリ)

shared_state.md / findings-phase2-*.json ×3 / before-machine-baseline.txt / after-machine-baseline.txt / pre-phase3.patch / findings.json (schema 準拠・30 paradigm) / verdict.json / review-plugin.md (本書)
