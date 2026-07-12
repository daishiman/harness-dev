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
「procedure (現状実施手順) 軸をヒアリング機構へ追加し、purpose と procedure の両方を下流ハンドオフへ格納する」という goal-spec (`plugin-plans/skill-intake/goal-spec.json`) を要件として固定し、既存の目的抽出機構 (5 軸ヒアリング + purpose-excavator 8 技法) について手順情報との接続漏れ・抽出粒度の甘さを含む既知のギャップを洗い出し、各ギャップの改善要否を本 phase で明記する (goal-spec C4)。加えて、ヒアリングの第一目的は一般的な情報収集ではなく「クライアントが本当に解決したい課題・問題・現状の流れ・実行したいこと」を相手固有の具体性で抽出しハーネス構築材料にすることであるという追加指示 (goal-spec C7/C8) を要件として固定し、平均回帰 (LLM がもっともらしい一般論へ丸め込むこと) のリスクと as-is/to-be 混同のリスクをギャップとして洗い出す。

## 背景
現状 `run-intake-interview` の 5 軸 (出力先/情報源/共有相手/真の課題/ナレッジ資産) と `skill-intake-purpose-excavator` の 8 技法 (5 Whys/JTBD/Magic Wand 等) は「真の目的 (動詞+目的語)」の深掘りを機構化しているが、`interview.json`/`intake.schema.json` のいずれにも「今どういう手順で実施しているか」を構造的に聞き取り記録する軸・出力フィールドが存在しない。そのため「今現状やっているものをハーネス化したい」という構想では、現状手順が `intake.json` に載らないまま `run-skill-create`/`run-plugin-dev-plan` へハンドオフされ、ハーネス構築側が手順を推測して作り、ユーザーの想定と異なる成果物になる手戻りが繰り返し発生している (goal-spec background)。

## 前提条件
- `goal-spec.json` (purpose/background/goal/checklist C1-C8/constraints/open_questions) が確定済みで本 phase 以降の不変アンカーである (C7/C8 は追加ユーザー指示に基づく差分反映済み)。
- 既存アーキテクチャが判読済み: `run-skill-intake` (orchestrator, 11 phase) → P1 `run-intake-kickoff` → P2 `skill-intake-assumption-challenger` (SubAgent) → P3 `skill-intake-user-profiler` (SubAgent) → P4 `run-intake-interview` (5 軸ヒアリング) → P5 `skill-intake-purpose-excavator` (SubAgent, 条件付き) → P6 `run-intake-option-catalog` → P7 `run-intake-visualize` → P8 `skill-intake-summarizer` (SubAgent) → P9 `run-intake-finalize` (集約・intake.{md,json} 生成) → P10 `run-notion-intake-publish` → P11 `run-intake-next-action`。
- 既存の抽象回答判定機構 `validate-answer-abstraction.py` + `abstract-answer-patterns.md` (`plugins/skill-intake/skills/run-intake-interview/`) が判読済みで、procedure 軸への拡張再利用対象として特定済み。
- `interview.json` スキーマ (`run-intake-interview/schemas/output.schema.json`) と `intake.schema.json` (plugin-root `references/`, schema_version 2.0.0) の両方が判読済みで、procedure の格納先を `interview.json.procedure` と `intake.json.sections.6_five_axes_summary.procedure` として特定済み。

## ドメイン知識
- **purpose (本質的課題)** と **procedure (現状実施手順)** の用語定義は index `## ドメイン知識` を参照 (差分なし)。
- 既存 4 SubAgent (assumption-challenger/user-profiler/purpose-excavator/summarizer) はいずれも「起動独立性 (context_fork=true・workflow-manifest.json 駆動の固定順次起動) × 非 adversarial でない独立判断 (仮説検証/客観推定/バイアス回避レビュー)」という共通パターンを持つ。procedure 抽出はユーザーが既に認識している手順の直接的事実収集であり、この分離パターンに該当しない (新規 SubAgent 非新設の判断根拠、`component-inventory.json.derivation` に詳細)。

## 成果物
- 既存目的抽出機構のギャップ一覧 (下表) と各項目の改善要否決定 (goal-spec C4 の完了成果物)。
- goal-spec checklist C1-C8 が本 plan のどの phase で操作化されるかの対応表 (下記、後段 P07 RTM の入力)。

**ギャップ一覧と改善要否**:

| # | ギャップ | 改善要否 |
|---|---|---|
| G1 | 5 軸 (出力先/情報源/共有相手/真の課題/ナレッジ資産) に procedure/手順軸が存在しない | 要改善 (本サイクル対応): C01 (`run-intake-interview`) を拡張し 6 本目の procedure 軸を新設する |
| G2 | purpose-excavator の 8 技法は「なぜ (why)」の深掘りに特化し、「どう (how) = 現状手順」の構造化再構成機構を持たない | 改善不要 (本サイクル見送り): procedure 抽出は非 adversarial な直接聴取であり 8 技法の対象外。将来 procedure 自体の深掘り (なぜその手順を選んでいるか) が要件化された場合に再検討 |
| G3 | `interview.json` の `intent_contract.slot_status` (9 固定スロット) に procedure 用スロットが存在しない | 要改善: `interview.schema.json` へ新規トップレベル `procedure` object を追加する (既存 9 スロットは変更しない・P02 で形状確定) |
| G4 | `intake.schema.json` (0_executive_summary〜11_artifact_index) に procedure フィールドが存在せず下流へ渡せない | 要改善: root `references/intake.schema.json` の既存 `sections.6_five_axes_summary` へ `procedure` property を追加し、13 番目 section は新設しない (`plugin_level_surfaces.schemas`) |
| G5 | 既存 `references/handoff-contract.md` に procedure→build 参照契約がなく、ハーネス構築側が手順情報を無視して build へ進める経路が残る | 要改善: root `references/handoff-contract.md` へ procedure 参照契約を追加する (`plugin_level_surfaces.references_config_assets`, goal-spec C5) |
| G6 | 既存ヒアリング機構 (5 軸 + procedure 軸) は LLM 駆動であるため、相手固有の課題・手順・仕組みをもっともらしい平均的・一般的な回答へ丸め込む (平均回帰) リスクが明示的に対策されていない | 要改善 (本サイクル対応): C01 のプロンプト層へ「一般化・正規化せず追加質問で具体化を促す」指示を追加し、C02 の contamination check と組み合わせて防御する (goal-spec C8) |
| G7 | as-is (現状の事実) と to-be (改善提案・理想手順) がフィールドレベルで分離されておらず、ヒアリング担当側の解釈・一般化・最適化提案が as-is フィールドへ混入する経路が塞がれていない | 要改善 (本サイクル対応): to-be 専用フィールドは新設せず (ヒアリング段階で to-be 設計を行わない goal-spec constraints)、as-is フィールドへの to-be 語彙混入を C02 拡張の contamination check で検出・FAIL させる (goal-spec C7) |

**C1-C8 の phase 操作化対応表**:

| checklist id | 操作化される phase |
|---|---|
| C1 (詳細抽出+validate PASS) | P02 (スキーマ形状設計) / P04 (テスト設計) / P05 (実装仕様) / P06 (テスト実行) |
| C2 (概略フォールバック) | P02 (閾値設計) / P04 / P05 / P11 (手動 trial) |
| C3 (purpose+procedure 両方揃うまで進めないゲート) | P02 (ゲート設計) / P05 (実装仕様) / P06 |
| C4 (既存機構ギャップ洗い出し) | P01 (本 phase、上表で完了) |
| C5 (handoff-contract.md 参照契約追加) | P02 / P12 (文書化) |
| C6 (決定論分岐) | P02 (閾値ルール確定) / P04 (境界値テスト設計) |
| C7 (as-is/to-be フィールド分離+混入検証ゲート) | P01 (本 phase、G7 で完了) / P02 (contamination check 設計) / P04 (混入検出テスト設計) / P05 (C02 実装仕様) |
| C8 (相手固有の具体性記録) | P01 (本 phase、G6 で完了) / P02 (質問設計・記録指示) / P05 (C01 プロンプト層実装仕様) / P07 (RTM, reasoning) |

## スコープ外
- procedure スキーマの具体的形状確定・DAG 設計 (P02 へ委譲)。
- 実装・build (P05 は「実装仕様」であり実コード改修そのものは行わない。実改修は後段 `run-skill-create` 等へ委譲)。
- 5 軸自体の優先順位・スキップ条件の変更 (goal-spec constraints によりスコープ外)。

## 完了チェックリスト
- [ ] ギャップ一覧 (G1-G7) が存在し、各項目に改善要否が明記されている (goal-spec C4、G6/G7 は C7/C8 由来)。
- [ ] goal-spec checklist C1-C8 の全項目が本 plan 内のいずれかの phase に対応付けられている (上表)。
- [ ] `goal-spec.json` の purpose/checklist/constraints が本 phase 内で逐語引用され、以降のフェーズが書き換えない不変アンカーとして扱われている。

## 参照情報
- `plugin-plans/skill-intake/goal-spec.json` (本 plan の不変アンカー)。
- `plugins/skill-intake/skills/run-skill-intake/SKILL.md` (orchestrator 契約)。
- `plugins/skill-intake/skills/run-intake-interview/references/abstract-answer-patterns.md` / `scripts/validate-answer-abstraction.py` (procedure 軸拡張の再利用対象)。
- `plugins/skill-intake/skills/run-intake-interview/schemas/output.schema.json` / `plugins/skill-intake/references/intake.schema.json` (拡張対象スキーマ)。
- 後続 P02 (このギャップ一覧・対応表を component 分解の入力とする)。
