---
id: IDX0
title: skill-intake 開発計画 index (main)
plugin_meta:
  manifest:
    required: true
    path: .claude-plugin/plugin.json
    name_matches_folder: true
    no_todo_placeholders: true
    validate_plugin: true
  marketplace:
    default_personal: true
    policy:
      installation: AVAILABLE
      authentication: ON_INSTALL
      category: Productivity
    cachebuster_for_update: true
  distribution:
    distributable: true
    bundles: [xl-skills-full, xl-skills-intake]
    marketplace: true
  ci:
    workflow: governance-check
  pkg_contract:
    applicable: false
    reason: 既存 package.include/exclude 契約 (.claude-plugin/plugin.json) は本改善で変更しない。procedure 拡張は既存 skill 2 件 (C01/C03) の拡張と plugin-root script 2 件 (C02 新設/C04 拡張) のみで、新規 entry_point (commands/skills/agents/hooks) を追加しない
  governance:
    applicable: false
    reason: 本 plugin に専用 runbook は未整備であり、本改善はヒアリングスキーマ/決定論ゲートの拡張に閉じるためスコープ外
  ssot_dedup:
    lint: lint-intake-vendored-ssot
    references_config_assets: tracked
    note: references/handoff-contract.md は root が正本、skills/run-skill-intake/references/handoff-contract.md は pointer のまま (複製禁止 invariant を維持)。procedure 参照契約の追記は root 側のみに行う
  feedback_deploy:
    enabled: true
    deploy: run-skill-feedback
    notion_sink:
      config_key: improvement-request
      schema_ref: doc/notion-schema/improvement-request.schema.json
      resolution: notion_config
    portability: vendored
  harness_eval:
    evals_json: EVALS.json
    mechanical: required
    llm_eval: required
---

# skill-intake 開発計画 index (main)

> 既存 plugin `skill-intake` (version 0.1.2) への機能拡張構想「5 軸ヒアリング + purpose-excavator 8 技法に、現状実施手順 (as-is procedure) の構造化抽出軸と決定論フォールバックを追加し、purpose と procedure の両方を intake.json ハンドオフへ格納する」を、人間可読な 13 フェーズのライフサイクル (本 index + phase-01..13.md) と、機械可読な buildable component 目録 (`component-inventory.json`) の 2 軸直交で計画したもの。
> artifact_class=`existing-plugin-update` のため envelope-draft (plugin.json 新規生成) は本計画では生成しない (envelope-draft は artifact_class=plugin-plan 限定・`R3-emit-specs.md`)。本計画の成果物は downstream builder (`run-skill-create` 等) 向けの**仕様**であり、実コード改修は本 plan のスコープ外 (goal-spec constraints)。

## 基本定義
- **プラグイン slug**: `skill-intake` (既存 plugin。plan_dir=`plugin-plans/skill-intake/`・同一構想は常に同一出力先=再現性アンカー)。本計画確定後の実装 build で現行 version の PATCH bump を想定 (bump 前後の具体値の正本は P13)。
- **最上位目的 (purpose)**: 「skill-intake のヒアリング機構 (5 軸ヒアリング + purpose-excavator の 8 技法) に、ユーザーが現在実際に行っている手順 (as-is procedure) を構造化抽出する軸とそのフォールバック経路を追加し、本質的課題 (purpose) と具体化された手順 (procedure) の両方を後続ハンドオフ成果物へ格納できるようにすることで、ヒアリング担当とハーネス構築担当の間の情報乖離による構築のやり直しを解消する。ヒアリングの第一目的は一般的なヒアリング情報の収集ではなく、クライアントが本当に解決したい課題・問題・現状の流れ (フロー)・実行したいことを相手固有の具体性で抽出し、それらを解決できるハーネスの構築材料にすることである」(goal-spec.purpose 逐語)。
- **仕様駆動 (大前提)**: 要件の正本は `goal-spec.json` の checklist (C1〜C8)。本 index + 13 phase + `component-inventory.json` はその被覆であり、実装との乖離が出たら仕様を先に更新してから build へ戻す (spec-first)。
- **状態語彙の分離**: `goal-spec.checklist[].done=false` と各 phase frontmatter `status: 未実施` は、後段 build/受入がまだ完了していないことを示す。`run-plugin-dev-plan-progress.json` の `covered=true` / `status=planned-ready` は、計画仕様が C1-C8 を被覆し builder へ渡せる状態を示すだけで、build 後の受入 PASS を意味しない。
- **スコープ (含む)**: procedure 軸のヒアリング機構への追加設計 (詳細抽出+概略フォールバック)、決定論分岐閾値の設計、下流ハンドオフ (intake.json 相当) への purpose+procedure 両方格納ゲートの設計、既存目的抽出機構 (5 軸+8 技法) のギャップ分析と改善要否判定。
- **スコープ (含まない)**: 実装 (`run-intake-interview`/`skill-intake-purpose-excavator`/`run-intake-finalize` 等の実コード改修)、5 軸自体の優先順位・スキップ条件の変更、Notion 公開・Slack 通知・Keychain 認証まわりの既存契約変更 (goal-spec constraints)。

## ドメイン知識
- **purpose (本質的課題)**: `skill-intake-purpose-excavator` の 8 技法 (5 Whys/JTBD/Magic Wand 等) が深掘りする「動詞+目的語」の真の目的 (既存概念)。
- **procedure (現状実施手順)**: 本改善で新設する概念。ユーザーが現在実際に行っている手順を順序付きステップ (各ステップの action/input/output/tool/frequency) として構造化したもの。
- **detailed mode / overview_fallback mode**: procedure 抽出の 2 経路。詳細抽出 (`procedure.steps[]`) が既定、手順化困難ユーザー向けに `difficulty_flag=true` + 概略情報 (`procedure.overview`: 工程数目安/関与者/頻度) へ決定論的に切り替わる経路がフォールバック (goal-spec C2/C6)。
- **決定論分岐**: 同一のユーザー回答パターン (2 連続抽象判定/未回答 vs 具体的な手順回答) を与えたとき常に同じ経路が選択されること (goal-spec C6)。既存 `validate-answer-abstraction.py` の抽象判定を procedure 軸へ拡張して閾値判定する。
- **2 軸直交**: ライフサイクル軸 (13 phase・人間可読) と成果物実体軸 (N=4 component・機械 SSOT) を二重に持たない。phase は `entities_covered: [C01, ...]` の id 参照のみで component に紐づく。`entities_covered` の記入規範は「その phase が実質仕様化する component のみ」の列挙であり、本 plan は全 phase が C01-C04 を横断的に扱う設計のため P02-P13 の全列挙が意図である。
- **component_kind (5 種のうち本計画で採用するのは skill/script の 2 種)**: 新規 sub-agent/slash-command/hook を新設しない理由は `component-inventory.json.derivation` を正本とする。
- **goal-spec constraints 内の決定記録**: goal-spec constraints の『R2/P02 解決済み事項:』prefix 付き項目は、制約ではなく解決済み決定の記録である (open_questions=[] 化に伴う退避先。goal-spec schema に決定記録専用フィールドが無いための散文規約であり、goal-spec 自体は変更しない)。
- **as-is 忠実性原則 (goal-spec C7/C8)**: ヒアリング担当の責務は相手固有の課題・問題・流れ・仕組みの as-is (現状) を平均回帰させず忠実に記録することに限定され、to-be (改善・最適化・理想手順) の設計は後続 build の責務である。to-be 専用の永続フィールドは新設せず (保存自体が to-be 設計の一形態となるリスクを回避)、`validate-procedure-completeness.py` (C02) の contamination check が as-is フィールドへの to-be 語彙混入を検出した場合は完全性判定を FAIL とする (C7)。加えてヒアリング担当は固有名詞・実例・頻度・関与者などの具体性を伴う深掘り質問で一般論・平均的回答への置換を防ぐ (C8)。

## インフラ
- **実行環境**: 新設/拡張 script は Python 標準ライブラリのみ (既存 skill-intake の stdlib-only 規約を継承・.sh/.js 新規禁止)。lint/検証は repo-root cwd 前提、skill 資産は self-relative 参照。
- **同梱決定論ゲート (機械正本=`specfm.GATE_SCRIPTS`)**: core 6 起動 — verify-index-topsort (§9 section 床+phase 完全性+DAG) / detect-unassigned / check-spec-frontmatter / check-spec-gates / check-spec-matrix-coverage (--self-test + PLAN の 2 起動) / check-surface-inventory (5 種 component_kind 検討証跡+plugin-level surface 採否)。core 6 は生成時必須ゲートであり、これに加えて評価時ゲート 4 本 (check-build-handoff / check-requirements-coverage / check-runtime-portability / check-plugin-goal-spec) を実行する (実行記録は `run-plugin-dev-plan-progress.json` の verification_status / `plan-findings.json` の gate_results)。
- **gate_type の名目性**: 各 phase frontmatter の `gate_type` (tdd-green/evidence 等) は build 後ライフサイクルで有効化される specfm 予約語彙であり、plan 状態 (`status: 未実施`) では名目である (P05 の tdd-green は「P05 仕様を満たす実装が P06 のテストを green にする」後段条件を指し、P06 の gate_type=none はテスト実行にゲートが無いことを意味しない)。
- **build の始め方 (consumer 手順・宣言のみ)**: 後段 builder は `handoff-run-plugin-dev-plan.json` の routes を top-sort 順 (C01→C02→C03→C04) に消費する。skill route (C01/C03) は既存 skill への **Edit 差分** (`--mode update` 相当・全書き換え禁止) として `run-skill-create` へ渡す (`brief_path` は `render-skill-brief.py` が inventory から build 時に決定論射影する出力先宣言であり、build 前の `briefs/` 不在は正常)。script route (C02/C04) は plugin-root scaffold (`plugin-scaffold`) が消費する (plugin-scaffold は contract-only で単独実行実体未整備。実体は handoff open_issues `GAP-SCRIPT-BUILDER` の fallback=`run-build-skill` フロー内代替生成に従う)。
- **コンポーネント目録の所在**: buildable な実体 (skill×2 (C01 拡張/C03 拡張) / script×2 (C02 新設/C04 拡張) = 計 4) は `component-inventory.json` が唯一の SSOT。build_target・依存 DAG (C01→C02→C03→C04)・quality_gates・harness_coverage・feedback_contract を目録側が保持する。
- **Plugin-level surfaces (採否は `component-inventory.json.plugin_level_surfaces` が正本)**:

  | surface | 判定 | 根拠 (要約) |
  |---|---|---|
  | manifest | required | version bump のみ、entry_points 変更なし |
  | composition | required | 既存 component 列挙は不変、procedure 拡張は既存エントリ配下 |
  | harness_eval | required | C01/C03 の既存 EVALS entry へ procedure criteria (IN1/OUT1) と as-is 忠実性 criteria (IN2/OUT2, goal-spec C7/C8) を追記 |
  | references_config_assets | required | root `references/handoff-contract.md` へ procedure→build 参照契約を追加 (goal-spec C5)。加えて run-intake-interview 配下へ新規 `references/to-be-vocabulary-patterns.md` (contamination 判定語彙集) を追加 (goal-spec C7) |
  | schemas | required | root `references/intake.schema.json` の `sections.6_five_axes_summary.procedure` と root `validation.procedure_completeness` を追加 |
  | vendor | omitted | 既存 vendor (jinja2/markupsafe) の範囲内で完結、新規依存なし |
  | mcp_app_connector | omitted | テキストヒアリングの範囲に留まり新規 MCP/connector 不要 |
  | notion_config | omitted | Notion 公開・DB 契約は本改善のスコープ外 (goal-spec constraints) |

## 環境ポリシー
- **品質基準**: 全 buildable component (C01-C04) が quality_gates (p0_lint(kind別)/build_trace/elegant_review の4条件 no_contradiction/no_missing/consistent/dependency_integrity/content_review verdict/evaluator≥80,high0) + harness_coverage (min≥80/kind_pass) を携帯する。elegant_review の C1-C4 は goal-spec checklist C1-C8 とは別名前空間の評価条件である。
- **proposer≠approver**: P03 (design-review) / P10 (final-review) は提案者と別 context の approver が承認する (design-gate/final-gate)。
- **現状値非焼込**: 「procedure 完全性判定が exit0 になる設計」を要件化し、harness 現状未達数値は component エントリへ焼かない (Goodhart 回避)。
- **実装スコープ外の徹底**: 本計画の 13 phase は全て「downstream builder 向けの仕様」として記述し、実コードの差分そのものは含めない (実改修は build フェーズで `run-skill-create` 等が担う)。
- **エスカレーション**: ゲート未達は `goal-spec.max_loops=5` まで findings を反映し再実行、超過時は `open_issues` に残し差し戻す。

## フェーズ一覧

1. P01 — requirements (要件) / 仕様確定・build未実施
2. P02 — design (設計) / 仕様確定・build未実施
3. P03 — design-review (レビュー) / 仕様確定・build未実施
4. P04 — test-design (テスト) / 仕様確定・build未実施
5. P05 — implementation (実装) / 仕様確定・build未実施
6. P06 — test-run (テスト) / 仕様確定・build未実施
7. P07 — acceptance-criteria (判定) / 仕様確定・build未実施
8. P08 — refactoring (改善) / 仕様確定・build未実施
9. P09 — quality-assurance (品質) / 仕様確定・build未実施
10. P10 — final-review (レビュー) / 仕様確定・build未実施
11. P11 — evidence (検証) / 仕様確定・build未実施
12. P12 — documentation (文書) / 仕様確定・build未実施
13. P13 — release (完了) / 仕様確定・build未実施

## 完了チェックリスト
- [ ] 基本定義 (plugin slug / purpose / スコープ) が宣言されている。
- [ ] ドメイン知識 (purpose/procedure 概念・2 軸直交・決定論分岐) が宣言されている。
- [ ] インフラ (実行環境 / core scripts / 目録所在 / surface 採否) が宣言されている。
- [ ] 環境ポリシー (品質基準 / proposer≠approver / 実装スコープ外の徹底) が宣言されている。
- [ ] 13 フェーズ (P01..P13) が phase_number 昇順で全存在し、各 phase 本文が §5 section 床 (`specfm.PHASE_BODY_SECTIONS` の宣言型 8 節) を満たす。
- [ ] 要件 C1: procedure 構造化抽出 (`steps[]` 各要素の action/input/output/tool/frequency 非空) がスキーマ拡張の validate PASS 設計として C01/C02 に明記されている。
- [ ] 要件 C2: 手順化困難ユーザー向けフォールバック (`difficulty_flag` + `overview` 概略情報) が C01 に明記されている。
- [ ] 要件 C3: purpose+procedure 両方が揃うまで下流ハンドオフへ進めないゲートが C03 (skill)/C04 (script 拡張) に明記されている。
- [ ] 要件 C4: 既存目的抽出機構 (5 軸+8 技法) のギャップ一覧と各ギャップの改善要否が P01 に明記されている。
- [ ] 要件 C5: `references/handoff-contract.md` への procedure→build 参照契約追加が `plugin_level_surfaces.references_config_assets` に明記されている。
- [ ] 要件 C6: 決定論分岐閾値 (2 連続抽象判定/未回答→フォールバック) が C01 の checklist/feedback_contract に明記されている。
- [ ] 要件 C7: as-is (相手の課題・問題・流れ・仕組みの忠実記録) と to-be (改善・最適化提案) のフィールドレベル分離、および as-is フィールドへの to-be 語彙混入検証ゲート (contamination check) が C01 の checklist/responsibilities/feedback_contract と C02 の purpose/outputs/exit_codes に明記されている。
- [ ] 要件 C8: 『解決したい課題・問題』『現状の流れ・仕組み』『実行したいこと』を相手固有の具体性 (固有名詞・実例・頻度・関与者) で記録する質問設計・一般論置換防止指示が C01 の checklist/responsibilities/feedback_contract (OUT2) に明記されている。
- [ ] 各 component (C01-C04) が ≥1 phase の `entities_covered` に出現する (orphan 0 件)。
- [ ] 同梱決定論ゲート (core 6 起動) + 評価時ゲート 4 本 (check-build-handoff / check-requirements-coverage / check-runtime-portability / check-plugin-goal-spec) の計 10 ゲートが全 exit0。

## 受入確認

> 計画 (上記) が満たすのは「各 component が評価基準を携帯し決定論ゲートを通る」こと。**組み上がった実装が当初 purpose を満たすか**は build 後に下記で確認する。plan は受入基準を**契約として焼く**だけで、実行は後段 build (`run-skill-create` の harness criteria-test)。purpose の正本 = `goal-spec.purpose`。

| 受入観点 (goal-spec checklist 由来) | 確認の見方 (build 後) | 焼き先 |
|---|---|---|
| C1: 手順を言語化できるユーザーの詳細抽出が構造化 JSON として validate PASS する | detailed モードの会話 trial 後、interview.json の procedure.steps[] が拡張スキーマの validate を PASS | C01 の IN1 criterion + `validate-procedure-completeness.py` (C02) |
| C2: 手順化困難ユーザーへの概略フォールバックが停止せず進む | 未回答/抽象回答を連続入力した trial で `difficulty_flag=true` + overview 収集へ切り替わり停止しない | C01 の R2-procedure-fallback 責務 + P11 手動 trial |
| C3: purpose/procedure いずれか欠落時に下流ハンドオフへ進めない | 片方を欠落させた入力で intake.json が生成されず Phase10/11 (ひいては run-skill-create/run-plugin-dev-plan) へ進めない | C03 の OUT1 criterion + `quality_gate.py` (C04) |
| C4: 既存目的抽出機構のギャップが洗い出され改善要否が明記される | P01 のギャップ一覧 (G1-G7) と各項目の改善要否記載を確認 | P01 requirements 本文 |
| C5: handoff-contract.md に procedure→build 参照契約が追加される | `references/handoff-contract.md` に `sections.6_five_axes_summary.procedure` 参照行が存在 | `plugin_level_surfaces.references_config_assets` |
| C6: 決定論分岐が同一入力で常に同一経路を選ぶ | 同一回答パターンを複数回入力し常に同じ経路 (detailed/overview_fallback) が選ばれることを受入テストが確認 | C01 の OUT1 criterion |
| C7: as-is/to-be がフィールドレベルで分離され as-is フィールドに解釈・一般化・最適化提案が混入していない | 自発的な改善提案を含む入力 (trial シナリオ 5) を与え、as-is フィールドに to-be 語彙が記録されず contamination check が混入なしと判定することを確認 | C01 の IN2 criterion + `validate-procedure-completeness.py` (C02) の contamination check |
| C8: 『解決したい課題・問題』『現状の流れ・仕組み』『実行したいこと』が相手固有の具体性で記録され一般論置換がない | 抽象的・一般論的な回答 (trial シナリオ 4) に対し、正規化・要約せず追加質問で固有名詞・実例・頻度・関与者を引き出すまで深掘りすることを独立レビューが確認 | C01 の OUT2 criterion (verify_by=elegant-review) |

build 後、C01/C03 の `feedback_contract.criteria` が criteria-test として実行され、上表の受入が PASS して初めて「purpose を満たす拡張が出来た」と確定する。`EVALS.json` の `llm_eval` はこの受入が評価系に配線されていることを宣言する。
