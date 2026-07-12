---
name: harness-creator-spec-reflection
description: harness-creator 仕様の反映トレーサビリティ・マトリクス全46行(ID/仕様/絶対パス/何を強制/焼き先)を読む。R3 携帯基準と R4 検証(完全性証明)の正本。
kind: reference
owner: team-platform
since: 2026-06-29
source-tier: internal
---

# harness-creator 仕様 反映トレーサビリティ・マトリクス (§14 / 完全性の証明)

> 下記インベントリの**全 46 行** (指示インベントリ 43 行 + F8 install-portability + B4/B5 feedback-Notion 連携の追加 3 行) を収録 (漏れ 0)。`焼き先` = どのフェーズ / **inventory component エントリ** (旧 component frontmatter) / **index plugin_meta** (plugin 階層) に焼くか。パスは harness repo root 相対 (= 絶対)。位置/閾値を確認できない箇所は `未確認` を明示 (省略しない)。焼き先の P4/P6/P8 等は開発ライフサイクルの粗い段階名で、phase-lifecycle.md §8 の 13 フェーズ (P01-P13) へ写像される。

## カテゴリ1: 評価基準

| ID | harness-creator 仕様 | 絶対パス | 何を強制 | 焼き先 |
|---|---|---|---|---|
| A1 | 4 条件正本 | `plugins/harness-creator/skills/run-elegant-review/references/4-conditions.json` | C1 矛盾(contradiction_edges==0,critical) C2 漏れ(missing==0,high) C3 整合(diff==0,critical) C4 依存(cycles==0 AND dangling_refs==0,high)・ALL PASS・loop_limit=3・未達 escalate | P8 完了条件 + inventory component エントリ |
| A2 | run-elegant-review(elegance) | `plugins/harness-creator/skills/run-elegant-review/SKILL.md` | 30 思考法 全使用 or skip_reason・Phase1 リセット→Phase2 並列 3→Phase3 改善(write 此処のみ max_iter=3)・fail_counts 全 0 で PASS・proposer≠approver・force_pass 禁止 | P8 |
| A3 | verdict.schema | `plugins/harness-creator/skills/run-elegant-review/schemas/verdict.schema.json` | verdict{4 条件 PASS\|FAIL}+fail_counts+thought_method_coverage(total=30)+iteration_count(0-3)+status 必須 | P8 出力形式 |
| A4 | convergence-policy | `plugins/harness-creator/skills/run-elegant-review/references/convergence-policy.json` | all_conditions_score_min=0.85・delta_max_ratio=0.20・Δ<0.10・max_iterations=3・rubric_min_score=4・admission_control(sha 一致 skip)・loop_bounds(5/3/3) | P8 + §13-4 |
| A5 | assign-skill-design-evaluator | `plugins/harness-creator/skills/assign-skill-design-evaluator/` | fork 採点・threshold=80・severity weight high-20/med-10/low-3・rubric L0→L1→L2 deep-merge+rubric_hash・machine_checks(FM/BD/NM/PD/RG)・**L2 評価器固有 delta rule=PG-001(prompts 物理存在) PG-002(agents anchor 一致) BND-001(bundles 登録) REG-001(completeness+build-trace exit0)** (L2 rubric.json)・write-eval-log.py append | P6 評価基準 |
| A6 | L0 rubric (正本) | `plugins/harness-creator/skills/ref-skill-design-rubric/references/rubric.json` | (layer:L0 v1.3.0) FM-001..005(frontmatter) BD-001..004(body: Purpose&Output Contract/Gotchas/行数≤300/BD-004=description発動条件↔body手順の1:1整合 LLM judge) NM-001..003(naming dir==name) PD-001..002(本文≤100行→references) RG-001(rubric_hash 埋込) + 横断 AG/HK/CM/PC/PR/WF/KL 系・per-rule severity 閾値=未確認。**旧記載の PG/BND/REG 系 rule は L0 でなく L2 評価器固有 delta (→A5)** | P6/P7 |
| A7 | assign-plugin-package-evaluator | `plugins/harness-creator/skills/assign-plugin-package-evaluator/` | PKG-002..008(plugin.json/namespace/skill frontmatter/agent↔subagent_refs/hook↔実体/script 実在+shebang+x/settings INV-1..12)・skill-only は 003/005/006/007/008 N/A | P7 |
| A8 | lint-content-review.py | `scripts/lint-content-review.py` | SKILL.md 変更 skill に elegance-verdict.json+rubric-verdict.json が PASS・skill_md_sha256 一致(stale 検出)・feedback_loop 構造・criteria_evaluated が frontmatter criteria 全件突合・dogfooding 除外なし・exit1 ブロック | P6/P8 |
| A9 | content-review-protocol | `plugins/harness-creator/skills/run-build-skill/references/content-review-protocol.md` | 機械層(CI/lint)と LLM 層分離・Inner/Outer・Stop hook block 差し戻し・max_iter=3 超過 INCOMPLETE | P6/P8 |
| A10 | run-skill-rubric-governance | `plugins/harness-creator/skills/run-skill-rubric-governance/` | rubric 変更は Runbook 経由のみ・semver(minor 緩和/major 厳格)・猶予 major≥14d/minor≥7d・違反率 0.20×3release・承認ボード 4 ロール・bootstrap 最小 20 件 | P7 |
| A11 | assign-prompt-design-evaluator | `plugins/prompt-creator/skills/assign-prompt-design-evaluator/` | C1 Layer 整合 C2 依存方向 L7→L1 単方向 C3 再現性 C4 Self-Eval・4 パス Pass0-4・high1 件で全体 FAIL・fork 必須・空 findings 禁止 | P3/P4(prompt 層保有時) |

## カテゴリ2: 評価基準の量産先伝播

| ID | 仕様 | 絶対パス | 何を強制 | 焼き先 |
|---|---|---|---|---|
| B1 | feedback_contract_ssot.py(+vendoring) | `plugins/harness-creator/scripts/feedback_contract_ssot.py` | CRITERIA_ID_RE=`^(IN\|OUT\|C)[0-9]+$`・verify_by∈{lint,test,script,evaluator,elegant-review,live-trial,human}・loop_scope∈{inner,outer}各≥1・必須キー(id,loop_scope,text,verify_by)・FEEDBACK_LOOP_KINDS={run,wrap,delegate}・3 者ミラー解消 | P6 + inventory component エントリ |
| B2 | lint-feedback-contract.py | `scripts/lint-feedback-contract.py` | kind∈{run,wrap,delegate} の frontmatter に criteria 必須・SSOT 制約満たす・CI/pre-push fail-closed・skip_reason で N/A・フォールバック既定残存 WARN | P6 完了条件(verify) |
| B3 | run-build-skill Step1/3.5 | `plugins/harness-creator/skills/run-build-skill/` (+`templates/combinators/with-feedback-contract.patch`) | loop 系は Step1 で brief.goal/checklist から criteria を test-first 導出 → Step3.5 で SKILL.md frontmatter と build-trace 両方に固定・patch 注入 | P4/P6 |
| B4 | notion_config.py (per-project Notion DB 解決 SSOT) | `plugins/harness-creator/scripts/notion_config.py` | DB キー (論理名)=plan 宣言 / DB ID (具体値)=config 供給の二層分離・config は多段フォールバック解決 (env `NOTION_CONFIG_PATH` → repo-root `.notion-config.json` (gitignore) → plugin-root → 焼き込み `notion-config.fixed.json`。単独 install でも repo-root 非依存)・require_or_skip fail-closed・解決ロジックは名前参照のみ (planner 側で再実装/複製禁止) | inventory `plugin_level_surfaces.notion_config` + index `plugin_meta.feedback_deploy.notion_sink.resolution` |
| B5 | improvement-request.schema.json (改善要望 受け皿DB) | `doc/notion-schema/improvement-request.schema.json` | 量産先 feedback (run-skill-feedback→`notion-submit-improvement.py`) の Notion 受け皿 DB スキーマ・schema はパス参照で複製しない・feedback_deploy enabled 時に schema_ref 必須 | index `plugin_meta.feedback_deploy.notion_sink.schema_ref` |

## カテゴリ3: テスト / TDD / カバレッジ

| ID | 仕様 | 絶対パス | 何を強制 | 焼き先 |
|---|---|---|---|---|
| C1 | harness-coverage-spec | `doc/harness-coverage-spec.md` | 6 種別(scripts/skills/agents/commands/hooks/docs)×二軸(mechanical/llm_eval)=12 軸各≥80%・kind 別パス(ref→source-traceability+ref-review / assign→evaluator verdict / loop→criteria 検証 test+content-review verdict)・水増し厳禁 | P6 |
| C2 | validate-harness-coverage.py | `scripts/validate-harness-coverage.py` | 12 セル全 met 時のみ spec_met=true・`--gate` exit1・新規 loop-kind は `make coverage-gate` で <80% exit1(ratchet) | P6 完了条件 |
| C3 | pytest 計測規約 | `sitecustomize.py` / `tests/test_scripts_smoke.py`(`.coveragerc`=**未確認**: harness-spec 記載だが repo root に未配置) | subprocess 行カバレッジ=pytest-cov+(parallel coverage 設定)+sitecustomize+COVERAGE_PROCESS_START・smoke import・非コード artifact は `eval-log/coverage/<type>/<key>.json`(実産物のみ)・network/secret は monkeypatch | P6 |
| C4 | run-build-skill 完了チェックリスト | `plugins/harness-creator/skills/run-build-skill/SKILL.md` | 同梱 scripts は tests/ に機能テスト+行カバレッジ≥80%・R1 に coverage 携帯必須・TDD(Red→Green)=未達チェックリスト項目→goal-seek で埋める→lint/test/verdict exit0/PASS | P4/P6 |

## カテゴリ4: ゴールシーク / 目的ドリブン

| ID | 仕様 | 絶対パス | 何を強制 | 焼き先 |
|---|---|---|---|---|
| D1 | goal-seek-paradigm | `plugins/harness-creator/skills/run-build-skill/references/goal-seek-paradigm.md` | loop 系は固定手順禁止・「## ゴールシーク実行」4 ブロック(ゴール 1 文+目的背景+二値チェックリスト+ループ)・AI 最尤ゴール推定・6 ステップ既定 5 周・SubAgent fork・達成判定=fresh agent PASS/FAIL(score 禁止・original_goal 正本) | P1 + 横断 |
| D2 | 中間成果物アンカー schema | `plugins/harness-creator/skills/run-build-skill/schemas/goal-seek-loop.schema.json` | 各周回末に `eval-log/<skill>-intermediate.jsonl` へ 5 要素(original_goal 不変 SHA256/current_goal_snapshot/delta/merged_directive/drift_signal 6 値)・次周回 Step2 必須入力・改竄検知停止 | 横断(§13-3) |
| D3 | run-goal-elicit(goal-spec) | `plugins/harness-creator/skills/run-goal-elicit/schemas/goal-spec.schema.json` | 曖昧要求→purpose/background/goal/checklist を `<PLAN_DIR>/goal-spec.json` (既定 `plugin-plans/<plugin-slug>/goal-spec.json`)・checklist 各{id:`^C[0-9]+$`,criterion,done,verify_by∈{reasoning,script,lint,test,human}}・target_plugin_slug/plan_dir 固定・max_loops=5・追加質問禁止・仮定明示 | P1(§13-1) |
| D4 | run-goal-seek | `plugins/harness-creator/skills/run-goal-seek/` | goal-spec 達成まで手順都度生成反復・決定論検査優先・max_loops5 超過で open_issues 停止・fork・handoff-goal-seek.json のみ親へ | 横断 |
| D5 | with-goal-seek + lint-goal-seek.py | `plugins/harness-creator/skills/run-build-skill/templates/combinators/with-goal-seek.patch` / `plugins/harness-creator/skills/run-build-skill/scripts/lint-goal-seek.py` | loop 系 default-ON(--no-goal-seek opt-out)・frontmatter goal_seek(engine=inline/fork)+配線節注入・lint は二値チェックリスト存在/曖昧語不在/配線節を violation・CI --self-test | P4/P5 |
| D6 | feedback-loop-deployment | `plugins/harness-creator/skills/run-build-skill/references/feedback-loop-deployment.md` | Stop hook decision:block で評価差し戻し・proposer≠approver・量産先に run-skill-feedback 実体配備(symlink 禁止)・lint-feedback-protocol.py --strict R1-R7・harness-creator 除外 | P8(§13-5) |

## カテゴリ5: 構造仕様 / 入力契約

| ID | 仕様 | 絶対パス | 何を強制 | 焼き先 |
|---|---|---|---|---|
| E1 | skill-brief.schema | `plugins/harness-creator/skills/run-skill-create/schemas/skill-brief.schema.json` | 必須 14 フィールド・optional `goal_seek` (engine 省略時は loop kind で task-graph 既定・inline/run-goal-seek 明示が opt-out)・skill_name pattern `^(ref\|run\|wrap\|assign\|delegate)-…$` max60・trigger_conditions 2-3 各≤80・boundary≤200・allOf(wrap→base_skill / delegate→delegate_agent / L2→rubric_refs≥1 / run・wrap・assign・delegate→goal+purpose_background+checklist / 全 prefix→kind 必須 / run・assign→responsibilities≥1 かつ prompt_required:true) | P4 inventory component エントリ (§3 は planner 内に節を持たない外部=`source` 設計書 `doc/ClaudeCodeスキルの設計書/` の章番号) |
| E2 | SKILL.md 構造仕様 | `plugins/harness-creator/skills/run-build-skill/SKILL.md`(+ governance-lint) | 本文≤300 行(P0-2)目安 170・description 発動条件のみ trigger2-3・dir 名==frontmatter.name・commonCore(name/description/kind/version/owner)・Python 標準ライブラリ正本(.sh/.js 新規禁止)・update 差分のみ・具体値直書き禁止({{PROJECT_ROOT}})・配置非依存($CLAUDE_PLUGIN_ROOT) | P4/P5 |
| E3 | run-build-skill Step0-12 カタログ | `plugins/harness-creator/skills/run-build-skill/SKILL.md` | kind 分岐→ヒアリング(criteria test-first)→テンプレ→references→trace+feedback_contract 固定→命名/構造 lint→fork 評価→ゲート(score≥80,high0,3 周)→subagent→prompt-creator→evaluator ペア→hook→knowledge loop→Notion→feedback 配備→content-review・ゴール駆動 | P4 |
| E4 | run-skill-create 7Step+4Gate | `plugins/harness-creator/skills/run-skill-create/SKILL.md` | Step1 elicit→Gate1→build→manifest/Gate2.5/bundle→P0lint(fail→build3 周)/Gate2→pkg-check→design-evaluate fork→elegant-review/Gate3→governance/Gate4→report・ゲート前必ず停止/承認・evaluator/governance は fork・P0 自動修正禁止・--fast 条件(1 ファイル≤30 行 kind∈{ref,wrap}) | P4/P8(投入先ゲート) |
| E5 | prompt-placement-convention + lint | `plugins/harness-creator/skills/run-build-skill/references/prompt-placement-convention.md` / `plugins/harness-creator/skills/run-build-skill/scripts/lint-prompt-placement.py` | prompts/<R-id>.md 正本・agents/<role>.md 薄いアダプタ+responsibility anchor・逆転禁止 exit1・ファイル名 regex・run/assign は prompts 必須・no-split threshold(第二消費者/機械検証/280 行超) | P3/P4 |
| E6 | prompt-creator 7 層 | `plugins/prompt-creator/skills/run-prompt-creator-7layer/references/seven-layer-markdown-template.md` | L1 基本定義→L2 ドメイン→L3 インフラ→L4 共通ポリシー→L5 エージェント(ゴール+完了チェックリスト 5-8+固定手順なし)→L6 オーケスト→L7 UI・依存方向 L7→L1 単方向・1 ファイル 1 責務 1agent・.md 既定 | P3/P4 prompt 設計 |

## カテゴリ6: ガバナンス / 配布 / 完全性

| ID | 仕様 | 絶対パス | 何を強制 | 焼き先 |
|---|---|---|---|---|
| F1 | P0 lint 8 本 | `plugins/skill-governance-lint/scripts/{lint-skill-name,lint-skill-description,lint-skill-tree,validate-frontmatter,lint-dependency-direction,lint-skill-dep-step7,lint-forbidden-deps,lint-manifest-contents}.py` | 全 exit0・TODO/未展開{{}}/英語仮文なし | P5 |
| F2 | validate-build-trace.py | `plugins/harness-creator/skills/run-build-skill/scripts/validate-build-trace.py` | source_docs/build_flow_coverage/doc_coverage/layer_decisions/reproducibility_gates の空欄拒否・prompt 配置 regex 照合・responsibility.id 集合==prompts ファイル名集合・--self-test | P5/P6 |
| F3 | validate-plugin-completeness.py | `scripts/validate-plugin-completeness.py` | MK-001..004(marketplace 登録/source 実在/basename 一致/distributable:false 登録残存) BD-001/002(bundle 登録)・distributable:false=実体保持非登録(未宣言 True)・NEVER_DISTRIBUTE=frozenset({harness-creator,prompt-creator,plugin-dev-planner}) denylist fail-closed・--fix append-only | P7 |
| F4 | bundles.json + marketplace.json | `.claude-plugin/bundles.json` / `.claude-plugin/marketplace.json` | bundles=harness-full(12 plugin)/harness-intake・marketplace plugins[]・harness-creator/prompt-creator 両方未掲載・install-bundle が cross-plugin 一括 install | P7 |
| F5 | PKG 契約(ref-pkg-contract) | `plugins/harness-creator/skills/ref-pkg-contract/` / `plugins/harness-creator/skills/run-plugin-package-check/scripts/validate-plugin-permissions.py` | PKG-001(公式 CLI ラッパー) 002-008(静的検査 7) 009(外部参照) 010-015(smoke/permission/runtime)・run-plugin-package-check に smoke-install/uninstall/upgrade+permissions | P7 |
| F6 | governance-check.yml(CI strict) | `.github/workflows/governance-check.yml` / `scripts/run-ci-checks.sh` | lint-script-naming/skill-description/dependency-direction/feedback-protocol --strict/content-review --all/feedback-contract --all/notion-relations/external-refs/plugin-completeness/ssot-duplication --strict/goal-seek --self-test/skill-completeness/frontmatter/plugin-lint-coverage/knowledge-loop・ローカル run-ci-checks.sh は **pytest 非包含**(push 前 pytest 直接実行要) | P5/P7 |
| F7 | lint-ssot-duplication.py | `plugins/harness-creator/skills/run-build-skill/scripts/lint-ssot-duplication.py` | DUP-SCHEMA-ID(exit1)/REDIRECT-FAT-BODY/DUP-REQUIRED-SET/DUP-PASSAGE(smell=warn,--strict fail)・両方残し禁止=上書き一本化 | P5/全体(SSOT) |
| F8 | install-portability | (焼き先=inventory component.placement_scope + plugin_meta) | plugin-root 共有 script は placement_scope=plugin-root で plugins/<slug>/scripts/ へ hoist・≥2 skill consumer の script は plugin-root 強制(check-runtime-portability)・cross-plugin SSOT は vendoring byte一致 or self-derive fail-soft(先行 project_skill_intake_standalone / project_harness_creator_install_portability の lint-runtime-portability)・build_target は plugin 内自己完結($CLAUDE_PLUGIN_ROOT) | P5/P7 |

## 補章: 漏れ検査 6 項目

| ID | 仕様 | 絶対パス | 何を強制 | 焼き先 |
|---|---|---|---|---|
| G1 | knowledge-loop | `plugins/harness-creator/skills/ref-knowledge-loop/` / `plugins/harness-creator/skills/run-build-skill/templates/combinators/with-knowledge.patch` / `plugins/harness-creator/skills/run-build-skill/scripts/lint-knowledge-loop.py` | Loop A(生成物)/B(メタ)・3 段階検索・consult_at:[runtime]・KL-001..007・harness-creator 自身 dogfooding | P6(任意・brief.knowledge_loop) |
| G2 | combinator 体系 | `plugins/harness-creator/skills/run-build-skill/templates/combinators/` / `plugins/harness-creator/skills/run-build-skill/scripts/render-combinators.py` / `…/schemas/build-flags.schema.json` / `…/schemas/template-selection.schema.json` | with-{goal-seek,feedback-contract,knowledge,evaluator,assign-evaluator,hooks,subagent,ref,run,wrap,delegate}・build-flags + template-selection 正本 | P4 build 構成 |
| G3 | lint-skill-completeness.py | `plugins/skill-governance-lint/scripts/lint-skill-completeness.py` | kind 別必須資産(run→prompts+manifest / ref→references+prompts / wrap→scripts+schemas / assign→rubric+schemas+prompts / delegate→prompts+schemas)・**判定詳細=一部未確認** | P5 |
| G4 | compose-rubrics.py + check-rubric-sync.py | `plugins/skill-governance-automation/scripts/compose-rubrics.py` / `plugins/skill-governance-lint/scripts/check-rubric-sync.py` | deep-merge/strict/override/layered+循環検出+composition hash・L0 正本=`ref-skill-design-rubric/references/rubric.json`・**rule 閾値=未確認** | P6/P7 |
| G5 | quality-rubric(共通 5 次元ルブリック) | `plugins/harness-creator/references/quality-rubric.md`(実在確認済) | 全 SubAgent 共通の 5 次元自己採点(完全性0.25/一貫性0.20/深度0.25/検証可能性0.15/簡潔性0.15・各0-3点・15点満点・各次元2以上で PASS)・`scripts/quality_gate.py` で機械検証・harness-creator 系(生成 agent 含む)の正本 | P4/P8(各 SubAgent 出力前の自己採点ゲート) |
| G6 | harness 現状値 | `doc/harness-coverage-spec.md`(§6 ダッシュボード) | 仕様書には「≥80% を満たす設計」を要件化・**現状未達数値(scripts mechanical 等)は焼かない**(Goodhart 回避) | 制約 (§11 は planner 内に節を持たない外部=`source` 設計書の章番号。planner では SKILL.md 主要ルール6「現状数値非焼込」が相当) |

## 完全性自己点検

A1-A11(11) + B1-B5(5) + C1-C4(4) + D1-D6(6) + E1-E6(6) + F1-F8(8) + G1-G6(6) = **46 行**。指示インベントリ全項目と 1 対 1 (F8 install-portability は per-phase 転換で配布携帯性軸を、B4/B5 は feedback-Notion 連携の宣言スロットを追加)。**未確認** (= ファイルは実在するが内容深掘り未了) = `.coveragerc` 正確位置 / lint-skill-completeness 判定詳細 / compose-rubrics rule 閾値 / L0 rubric per-rule severity 重み (行内に明示・省略なし)。G5 quality-rubric は二段確認で実在＋内容確認済みのため未確認から除外。**L0 rubric の rule ID/family は 2026-06-30 elegant-review で実体照合済 (FM/BD/NM/PD/RG + 横断 AG/HK/CM/PC/PR/WF/KL)・旧 A6 の PG/BND/REG 記載は L2 評価器 delta の誤帰属だったため是正済 (tests/test_matrix_doc_integrity.py が再発を機械検出)**。

## 完全性の証明 (§14.1 / 全サーフェス列挙 → ラベル付け)

> 上記 46 行のうち 43 行は「指示インベントリ」と 1 対 1 (F8 install-portability は per-phase 転換で追加した配布携帯性規律、B4/B5 は feedback-Notion 連携で追加した宣言スロット規律) だが、それだけでは *分母が自己定義* で完全性を証明しない。
> ここでは **harness-creator の全サーフェス (skills 33 本 + 設計書の関連章) を独立列挙**し、各々を
> `反映済(行ID)` / `含意済(行IDに包含)` / `意図的除外(理由)` でラベル付けする。これにより「漏れていない」が
> 監査可能になる (循環論法の解消)。新規 skill/章が harness-creator に増えたら本表へ追記する運用とする。

### skills/ 全 33 本 (実体所有 30 本 + contract-generator への symlink 3 本)

> 注: `plugins/harness-creator/skills/` を `ls` すると 33 エントリだが、実体 `SKILL.md` (`-type f`) は **30 本**。残 3 件 (`run-contract-finalize`/`run-contract-generate`/`run-template-sync`) は `../../contract-generator/skills/` への **symlink** で、harness-creator が所有するのでなく共有参照する (下表で各々注記)。完全性証明の本質 (harness-creator サーフェスの欠落 0) は維持されるが、分母 33 は「所有 30 + symlink 3」の合算である。

| skill | ラベル | 根拠 |
|---|---|---|
| assign-plugin-package-evaluator | 反映済 A7 | PKG 評価 |
| assign-skill-design-evaluator | 反映済 A5 | fork 採点 |
| delegate-codex-skill-review | 含意済 A2 | elegant-review の Codex 委譲 (Phase3 限定) |
| ref-claude-code-skill-spec | 含意済 E1/E2 | skill spec/frontmatter は skill-brief schema(E1)+SKILL.md 構造(E2)。全 frontmatter フィールド確定は下流 run-build-skill |
| ref-cross-platform-runtime (22章) | 意図的除外 (部分含意 E2) | E2「Python 標準ライブラリ正本(.sh/.js 新規禁止)」+ script kind `stdlib_only` でクロスOS リスクを実用上カバー。生成物が Python stdlib 主体ゆえ .ps1/path 固有規律は焼かない。OS 依存が出る構想時は script spec の `purpose`/`inputs` に明記 |
| ref-domain-rubric-template | 含意済 A6/G4 | ドメイン rubric テンプレ/compose-rubrics |
| ref-domain-task-spec-rubric | 含意済 A5/A6 | run-skill-create rubric_refs |
| ref-knowledge-loop | 反映済 G1 | knowledge loop (opt-in) |
| ref-output-routing (31章) | 意図的除外 (部分含意 E1) | 出力契約は skill-brief 14 の `output_contract` で携帯。31章 routing adapter は build 段階の実装詳細で計画タスク仕様書には焼かない。出力先が論点になる構想は spec の `output_contract` に明記 |
| ref-pkg-contract | 反映済 F5 | PKG 契約 |
| ref-skill-design-rubric | 反映済 A6 | L0 rubric 正本 (唯一の upstream) |
| ref-skill-glossary | 意図的除外 | 人間可読の用語集。生成タスク仕様書へ焼く"規律"でない (参照資料) |
| ref-skill-naming-convention (06章) | 含意済 E1/E2 | skill_name pattern regex は E1 allOf、prefix/kebab は E2 に包含 |
| ref-task-context-map | 意図的除外 | context budget 索引。実 build 時の参照資料で計画規律でない |
| ref-yaml-spec-fetcher | 意図的除外 | 外部 YAML spec 取得ユーティリティ。本計画ドメインに無関係 |
| run-build-skill | 反映済 C4/E3/F2/B3/D1/D5 | build Step カタログ/criteria 固定/trace 等 多数行が参照 |
| run-contract-finalize | 意図的除外 (symlink→contract-generator) | 業務委託契約ドメインの別 skill。plugin 量産規律でない。実体は contract-generator 所有 |
| run-contract-generate | 意図的除外 (symlink→contract-generator) | 同上 |
| run-elegant-review | 反映済 A2 | 30 思考法 elegance |
| run-goal-elicit | 反映済 D3 | goal-spec |
| run-goal-seek | 反映済 D4 | ゴールシーク反復 |
| run-migrate-audit | 意図的除外 | 移行監査の運用 skill。生成規律でない |
| run-plugin-package-check | 反映済 F5/A7 | PKG smoke/permission |
| run-skill-create | 反映済 E4 | 7Step+4Gate (後段投入先) |
| run-skill-elicit | 含意済 E3/E4 | brief ヒアリング (run-skill-create Step1) |
| run-skill-feedback | 反映済 D6 | feedback 配備 |
| run-skill-iter-improve | 意図的除外 (部分含意 D4/D6) | 実走 eval 駆動の反復改善ループ。goal-seek(D4)/feedback 配備(D6) の改善思想に連なるが、harness-creator 自身の品質改善運用機構であり生成タスク仕様書へ焼く計画規律でない |
| run-skill-live-trial | 意図的除外 | 対象 skill を本物の claude セッション(tmux)で実走させる受け入れ評価機構。harness-creator の実走品質検証運用で、計画生成段階の規律でない |
| run-skill-rename | 意図的除外 (update で別扱い) | 改名は `--mode update` の運用で、計画生成段階の規律でない |
| run-skill-rubric-governance | 反映済 A10 | rubric governance runbook |
| run-skill-update-notifier | 意図的除外 | 更新通知の運用 skill。生成規律でない |
| run-template-sync | 意図的除外 (symlink→contract-generator) | テンプレ同期の運用。生成規律でない。実体は contract-generator 所有 |
| wrap-git-commit-safe | 意図的除外 | git commit ラッパー。生成規律でない (PR/commit は最終仕様書が言及・本スキル責務外) |

### 設計書 関連章 (46 行が直接引用しないが関連)

| 章 | ラベル | 根拠 |
|---|---|---|
| 04-invocation-permissions-settings (最小権限/allowed-tools) | **意図的除外=下流委譲** | `allowed-tools`/最小権限/`model`/`disable-model-invocation` は skill-brief.schema にも無く、**下流 `run-build-skill` が確定する責務**。slash-command/sub-agent kind は構造契約に `allowed-tools`/`tools` を持つため計画段階でも宣言する。skill kind は brief 段階で持たない (生成 SKILL.md で下流付与) |
| 10-subagents-hooks-integration | 含意済 (component-domain) | sub-agent/hook component_kind 契約 + `--with-subagent`/`--with-hooks` |
| 17-agent-teams-reference | 含意済 (component-domain) | 本スキルの fork 設計が利用。生成 plugin の team 化は sub-agent component に包含 |
| 34a-settings-merge-spec | 意図的除外 (部分含意) | hook の `settings_wiring` で部分カバー。plugin settings merge は plugin_meta 外。設定 merge が論点の構想時は `plugin_meta` 拡張 |
| 22-cross-platform-runtime / 31-output-routing | 上表 ref-* と同根拠 | (再掲なし) |

**結論**: harness-creator の全 skill/関連章は {反映済 / 含意済 / 意図的除外+理由} のいずれかに分類済み = **未分類の漏れ 0 を列挙で証明**。意図的除外は理由付きで監査可能。

**機械保証の射程 (粒度の正直開示・over-claim 回避)**: 「完全性の証明」の担保は、マトリクスが上流を参照する **3 つの様式 (引用 / 数値 / 意味 gloss)** ごとに機構を分ける三層方式 + 分母ゲートから成る:

| 粒度 | 何を保証 | 機械ゲート |
|---|---|---|
| **skill 列挙 (= 分母)** | harness-creator の skill 増減で本表の追記/削除漏れを検出 | `tests/test_matrix_doc_integrity.py::test_completeness_proof_enumerates_all_harness_creator_skills` |
| **46 行 ID 集合** | 46 行 table と本文行 ID の drift・OP/conditional/N-A 入替 | `check-spec-matrix-coverage.py --self-test` |
| **層1: 引用 (path / rule-ID)** | 引用先の実在 (上流改名/移動/削除の無音 stale 化)。原則はこの引用形=コピー焼込禁止 | `test_matrix_rows_cite_real_rubric_rule_ids` / `test_matrix_rows_cite_existing_plugin_paths` |
| **層2: 数値 (表示用複製)** | 可読性のため複製した閾値・lint 集合が上流実体と値一致 (SKILL_P0_LINTS↔`plugins/skill-governance-lint/scripts/` 実体 glob、A1/A4 行数値↔引用先 JSON 値)。複製は specfm 冒頭の二重保持台帳 + parity test 同時追加が条件 | `tests/test_schema_parity.py` / `tests/test_matrix_doc_integrity.py` |
| **層3: 意味 gloss (ラベル faithfulness)** | 意味の正否そのものは機械化しない (Goodhart 回避)。代わりに上流契約ファイルを hash pin し、**不一致時に event-driven 再監査を発火** (カレンダー time-bomb でなく実変更駆動) | `references/upstream-pins.json` + `scripts/check-upstream-pins.py` (in-repo=hash 再計算 fail-closed) + 不一致時の人手再監査・独立 SubAgent 二段確認 (`audit-trigger: quarterly` は補助) |

つまり「列挙・ID・参照先存在・複製数値の値 parity」までは機械保証し、「意味ラベルの faithfulness」は upstream-pins の hash 不一致を発火点とする event-driven 再監査 + 四半期監査と二段確認で担保する (claim はこの射程を超えて言い切らない)。新規 skill/章が harness-creator に増えたら本表へ追記する運用は、上記 skill 列挙ゲートが追記漏れを機械検出して補強する。
