---
name: assign-blueprint-fidelity-evaluator
description: run-extract-blueprint が生成した章別ブループリントの忠実性を独立 context で評価したいとき、事実/推測区別と粒度と被覆を検証し draft_hash に束縛した PASS/FAIL verdict をローカル品質ゲート (C01 の周回内の受入判定・差し戻し) へ渡したいときに使う。
disable-model-invocation: true
user-invocable: false
context: fork
agent: general-purpose
allowed-tools:
  - Read
  - Bash(python3 *)
  - Grep
  - Glob
kind: assign
prefix: assign
pair: run-extract-blueprint
effect: conversation-output
role_suffix: evaluator
owner: harness maintainers
since: 2026-07-11
version: 0.1.0
output_language: ja
deterministic_checks: [doc-emit.py, mermaid-validate.py, recount-palette-orphans.py]
responsibility_refs:
  - prompts/R1-evaluate.md
schema_refs:
  - schemas/verdict.schema.json
  - ../../schemas/system-blueprint.schema.json
  - ../../schemas/fact-inference-confidence.schema.json
manifest: workflow-manifest.json
feedback_contract: # per-skill 評価基準。verdict receipt の criteria_evaluated と突合
  max_iterations: 3
  criteria:
    - id: IN1
      loop_scope: inner
      text: 共有決定論ゲート (doc-emit.py --check-screens=C11 / mermaid-validate.py=C10) を C01 draft へ再実行し exit0 を確認し、非共有の recount-palette-orphans.py が観測色 palette 孤児 0 を C11 と独立の走査経路で再計数して一致することを検証する
      verify_by: script
      derived_from: [CL-6, CL-9]
    - id: OUT1
      loop_scope: outer
      text: 生成物が事実/推測/observation_gap を相互排他で区別し、レンズ由来主張が evidence_refs+confidence で接地し fact へ混入せず、ペルソナ偽装 fact が inference へ落ちており、最小スカフォールド骨子が追加ヒアリングなしで導出できる粒度であることを独立 context の評価が確認し draft_hash 束縛 verdict を発行する
      verify_by: evaluator
      derived_from: [CL-1, CL-2, CL-3, CL-4, CL-5, CL-7, CL-8, CL-10]
source: doc/ClaudeCodeスキルの設計書/
source-tier: internal
last-audited: 2026-07-11
audit-trigger: quarterly
---

# assign-blueprint-fidelity-evaluator

> extract-system-blueprint plugin の忠実性評価器 (L1 assign skill)。`run-extract-blueprint` (C01) が生成した章別ブループリント draft を **proposer と異なる独立 context (`context: fork`)** で評価し、`draft_hash` に束縛した verdict (PASS/FAIL) を `ESB_VERDICT_DIR` (既定 `.esb-verdict`) へ発行する。この verdict を C01 (run-extract-blueprint) が周回内の品質ゲート/差し戻し判定に消費し、PASS 以外の draft をローカル成果物として受理しない。verdict はローカル成果物の品質判定 (受入基準の充足確認) を意味する。パス解決は `$CLAUDE_PLUGIN_ROOT` 起点。

## Purpose & Output Contract

C01 draft (blueprint.json + 章別 md + 5 種 Mermaid + (取得された場合) 画面別 layout/overlay/annotated PNG + design-tokens.json + site coverage manifest + request ledger + sink-status.json) を入力に、生成者と同一 context の自己評価では見落とす **事実/推測の混同・粒度不足・被覆漏れ・レンズ主張の overfit・ペルソナ偽装** を独立に検出し、`draft_hash` に束縛した verdict を返す。生成物自体は改変せず、指摘は C01 への差し戻しに留める (proposer≠approver)。

**入力**: C01 draft ディレクトリ (`--draft-dir`)。`blueprint.json` (正本抽出) / 章別 md / `design-tokens.json` / `site-coverage-manifest.json` / `sink-status.json` (draft_hash 保持) / request ledger を含む。
**出力**:
- `${ESB_VERDICT_DIR:-.esb-verdict}/<draft_hash>.verdict.json` … `verdict ∈ {PASS, FAIL}` + `draft_hash` + `findings[]` (該当箇所 loc + 理由 + severity) + `observation_completeness` + `load_policy_result` + `gate_results` + `recount` + `reconstruction`。C01 (品質ゲート/差し戻し判定) がこの verdict を読む。
- 標準出力に verdict サマリ (日本語本文・JSON キー/enum は原文)。

**完了条件 (verdict=PASS の必要十分)**: 共有決定論ゲート (C10 mermaid-validate / C11 doc-emit `--check-screens`) が全 exit0 **かつ** 非共有 recount-palette-orphans.py が観測色 palette 孤児 0 を C11 と一致で再計数 **かつ** high severity finding 0 **かつ** observation_completeness の無言欠落 0 **かつ** load-policy (対象 origin 並列 1・request/byte budget) 充足 **かつ** 最小スカフォールド逆テストで top-level 必須欠落 0・未回答質問 0。1 つでも欠ければ FAIL。

**禁則**: 生成物 (blueprint/draft/対象 origin) を改変しない (Write/Edit は持たない)。verdict を draft_hash から切り離して発行しない。実名 prompt が名前を含むだけで PASS にしない (evidence_refs+confidence・fact 非混入・high 主張の複数直接根拠を要求)。共有ゲートだけに依存せず必ず非共有の再計数経路を 1 本通す (common-mode 誤り排除)。

## Key Rules

1. **proposer ≠ approver**: C01 と context を共有しない `context: fork` の独立評価。生成者が見落とす混同/粒度不足/被覆漏れを非対称に検出するのが存在理由。自己評価の追認 (Sycophancy) を機構で排除する。
2. **verdict は draft_hash 束縛**: receipt に評価対象の `draft_hash` を必ず含める。C01 は verdict=PASS かつ draft_hash 一致のときだけ draft を周回内で受理し次段へ進める。hash 不一致 draft は品質ゲートで差し戻される。
3. **共有ゲート + 非共有再計数の二経路**: C10/C11 は C01 自己検証と同一ロジック (基準統一)。ただし共有は common-mode 誤りを排除しないため、`recount-palette-orphans.py` が blueprint.json を C11 と**独立の走査経路**で再計数し観測色 palette 孤児 0 を照合する。共有ゲートが 0 でも再計数が孤児を検出したら FAIL (C11 の見落とし捕捉)。
4. **anti-overfit (実名 prompt 構造検査)**: C03-C06/C13 の実プロンプトに inventory.prompt_contract の実名見出し・cross-lens conflicts・neutral synthesis・非模倣/非推薦 guard が存在するかを構造検査する。ただし名前の出現だけで PASS にせず、レンズ由来推測が evidence_refs+confidence で接地し fact へ混入せず、high 主張が複数の直接根拠を持つことを判定する。
5. **fact ≠ inference ≠ gap の相互排他**: fact は provenance 必須でレンズ解釈を含めない。inference は claim+evidence_refs(≥1)+confidence 必須。observation_gap は not_observed|blocked+reason で inference へ昇格させない。この三値が混同されていたら FAIL。
6. **ペルソナ偽装 → inference or FAIL**: 実在個人/組織を代弁する主張 (「〜氏はこう設計する」等) が fact レーンに混入していたら、根拠つき inference へ落ちているか (evidence_refs+confidence) を確認し、fact のままなら FAIL。
7. **決定論優先・改変禁止**: 判定は script (C10/C11/recount/emit-verdict) を先に通し、LLM 意味判断はその後。被評価物を一切書き換えない (Goodhart 対策)。verdict の PASS/FAIL は emit-verdict.py が gate 結果と findings へ決定論規則を適用して出す (採点者が恣意的に決めない)。

## ゴールシーク実行

> 本 skill は評価系 (kind=assign)。Goal + 完了チェックリストで採点網羅性を担保するが、達成までの **runtime goal-seek loop は配線しない** (一度の read-only 採点で完結する)。正本: `../../../harness-creator/skills/run-build-skill/references/goal-seek-paradigm.md`「評価系 (assign-*-evaluator) の扱い」。評価→改善のループは C01 の feedback_contract / content-review が回す (評価器自身ではない)。

### ゴール (Goal)

C01 draft の章別ドキュメント群が、事実と根拠つき推測を相互排他で明示区別し、AI へ渡した際に追加ヒアリングなしで自社版スカフォールドの雛形生成へ着手できる粒度 (事実 + 根拠つき推測 + 確度 + 主要画面のスクリーンショット/細かなレイアウト) であることを、proposer と異なる独立 context で判定し、`draft_hash` に束縛した verdict を `ESB_VERDICT_DIR` へ発行した状態。

### 目的・背景 (Why)

生成者 (run-extract-blueprint) と同一 context で自己評価すると、事実/推測の混同や粒度不足を見落とす。proposer≠approver の原則で独立に評価し、C01 が PASS 以外の draft を周回内で受理しないことで、忠実でない draft をローカル成果物として確定させない。機械層の C10/C11 共有は基準統一のためで common-mode 誤りは排除しないため、非共有の再計数経路を最低 1 本持つ。

### 完了チェックリスト (Checklist)

- [ ] top-level が `system-blueprint.schema.json` 準拠で必須項目を欠かず、重要 fact 欠測 0・未回答質問 0 で、最小スカフォールド骨子が導出可能である <!-- CL-1 -->
- [ ] 主要画面の visual formation 全カテゴリ (identity/geometry/layout/paint(caret/accent/selection/scrollbar/text-decoration 色・色値の正準表現)/typography(font provider/src)/media/effects/pseudo-elements/state(cursor)/motion/responsive/a11y/tokens) と画面→region→主要 element の coverage manifest が (WebFetch+C09 静的 snapshot および取得できた C15 browser-render の範囲で) 網羅され、screenshot・番号付き注釈 overlay・computed layout は browser-render 取得時のみ評価し、ブラウザ不在時は observation_gap+reason=browser-unavailable として妥当で、未取得 field が無言欠落でなく not_observed+reason で、鍵画面が取得手段の範囲で観測されている <!-- CL-2 -->
- [ ] 合成 design-tokens.json (palette + type/spacing/radius/shadow(elevation)/breakpoint/z-layer scale + theme 別 color set + document brand 色) が観測色を漏れなく被覆 (観測色の palette 孤児 0)、light/dark 両テーマ対応時は両 color set が揃い、色値が正準表現 (hex8+gamut) で保持されている <!-- CL-3 -->
- [ ] content/essence 被覆: verbatim コピー fact (見出し/CTA/本文/meta・OGP) の欠落が理由付き gap であり、C13 content-intent 推測 (価値提案/キーメッセージ/想定読者/トーン&ボイス/CTA 意図/JTBD 仮説) が全て evidence_refs+confidence で接地し、C06 essence 章 (本質的問題(JTBD)/読者/価値提案/キーメッセージ/トーン/positioning) が fact と区別されている <!-- CL-4 -->
- [ ] tech/nonfunctional 被覆: tech_signals と nonfunctional_baseline が既取得 response からの fact として observed_scope 付きで記録され未観測が理由付き gap であり、tech_stack.identified[] の named 同定が全て signal fact への evidence_refs+confidence で接地し fact レーンへ混入していない <!-- CL-5 -->
- [ ] 被覆の深さ・広さ (R5): feature_map(fact)/user_journeys(推測) が区別され、security_observations→security_design が OWASP 観点で受動観測のみ (侵入/脆弱性スキャン言及 0) で接地し、delivery_topology が header fact に接地し、cwv_field_sample が scope_note 付き fact で、compliance_surfaces が記録され、site_inventory coverage が無言欠落なく full_site で pending を残したまま完全被覆と偽装していない <!-- CL-6 -->
- [ ] C03-C06/C13 実プロンプトに実名見出し・cross-lens conflicts・neutral synthesis・非模倣/非推薦 guard が存在し、名前出現だけで PASS せずレンズ由来推測が evidence_refs+confidence・fact 非混入・high の複数直接根拠を満たす (anti-overfit) <!-- CL-7 -->
- [ ] ペルソナ偽装 fact が inference へ落ちている (evidence_refs+confidence) <!-- CL-8 -->
- [ ] 共有決定論ゲート (mermaid-validate.py=C10 / doc-emit.py --check-screens=C11) が exit0 で、非共有 recount-palette-orphans.py が観測色 palette 孤児 0 を C11 と独立経路で再計数し一致した (common-mode 破り) <!-- CL-9 -->
- [ ] request ledger が低負荷 policy (対象 origin 並列 1・最小間隔・request/screenshot/byte budget・Retry-After・停止条件) を満たし、`emit-verdict.py` が draft_hash 束縛 verdict (PASS/FAIL) を ESB_VERDICT_DIR へ発行した <!-- CL-10 -->

### 採点フロー (局面カタログ・順序は都度判断)

下記は固定順序ではなく、未達チェックリスト項目に応じて選ぶ採点局面群。詳細手順・入出力契約は `prompts/R1-evaluate.md` を正本とする。評価は改変せず read-only、ループは回さない。

### 局面: 共有決定論ゲートの再実行 (C10/C11)

C01 draft へ共有ゲートを**再実行**して基準統一を確認する。

```bash
python3 "$CLAUDE_PLUGIN_ROOT/scripts/mermaid-validate.py" --docs-dir <draft-dir>
python3 "$CLAUDE_PLUGIN_ROOT/scripts/doc-emit.py" --check-screens --extraction <draft-dir>/blueprint.json --out-dir <draft-dir>
```

### 局面: 非共有の再計数 (common-mode 破り)

C11 と独立の走査経路で観測色 palette 孤児を数え直し、共有ゲートの結果と照合する。

```bash
python3 "$CLAUDE_SKILL_DIR/scripts/recount-palette-orphans.py" --blueprint <draft-dir>/blueprint.json
```

### 局面: 意味判定 (fact/inference/被覆/anti-overfit/ペルソナ)

`prompts/R1-evaluate.md` に従い、blueprint.json と章別 md、C03-C06/C13 の実プロンプトを Read し、三値排他・evidence 接地・被覆・実名 prompt 構造 (anti-overfit)・ペルソナ偽装・最小スカフォールド逆テストを判定して findings JSON を組み立てる。

### 局面: verdict 発行 (draft_hash 束縛)

gate 結果 + 再計数 + findings を集約 assessment JSON にまとめ、`emit-verdict.py` が決定論規則で PASS/FAIL を確定して receipt を書く。

```bash
python3 "$CLAUDE_SKILL_DIR/scripts/emit-verdict.py" --assessment <assessment.json> \
  --draft-hash "$(python3 -c 'import json,sys;print(json.load(open(sys.argv[1]))["draft_hash"])' <draft-dir>/sink-status.json)" \
  --out-dir "${ESB_VERDICT_DIR:-.esb-verdict}"
```

## Gotchas

1. **draft_hash の出所**: 評価対象 hash は C01 の `sink-status.json` の `draft_hash`。C02 が別途 hash を再導出すると C11 のロジックを共有してしまうため、C01 が固定した hash に束縛する (照合の非共有性は palette 再計数で担保)。
2. **共有ゲートだけで PASS にしない**: C10/C11 が exit0 でも、非共有 recount が孤児を検出したら FAIL。common-mode 誤り (両者同一バグ) を破るのが再計数の唯一の目的。
3. **改変禁止**: Write/Edit を持たず、blueprint/draft を書き換えない。指摘は findings に載せ C01 へ差し戻す。
4. **ループを回さない**: assign は一発採点。未達は verdict=FAIL + findings で C01 へ返し、改善ループは C01 側 feedback_contract が回す。
5. **fork でも中間ファイルは draft-dir に置かない**: verdict receipt は `ESB_VERDICT_DIR` のみ、assessment は一時領域。被評価物ディレクトリを汚さない。
6. **plugin schema は contract 参照**: `../../schemas/system-blueprint.schema.json` 等は plugin-scaffold 所有で未 build のことがある。schema_refs は契約参照であり、実体不在時も verdict.schema.json (本 skill 直下) を出力正本とする。
7. **recount のゼロ件は被覆の証明ではない**: `observed_count=0` は palette 孤児 0 を自明に満たすだけで、画面被覆を証明しない。観測可能な鍵画面があるのに screens が空なら `key_screen_gaps` または high finding として FAIL にする。

## ハンドオフ

- **上流 (被評価物)**: `run-extract-blueprint` (C01) が draft と `sink-status.json` (draft_hash) を成果物ディレクトリへ出す。C02 はこれを Read のみで消費。
- **下流 (品質ゲート)**: C01 (run-extract-blueprint) が周回内で `ESB_VERDICT_DIR` の verdict receipt (verdict=PASS + draft_hash 一致) を読み、PASS の draft だけをローカル成果物として受理する。verdict≠PASS/hash 不一致は有界差し戻し。
- **下流適用**: C02 PASS 済 blueprint は `run-blueprint-apply` (C14) が自社適用 recommendations の入力に使う。

## Additional Resources

- `prompts/R1-evaluate.md` — 単一責務 (忠実性評価) の 7 層 prompt (l5-contract v2.0.0)。
- `schemas/verdict.schema.json` — verdict receipt の出力正本 (verdict/draft_hash/findings/observation_completeness/load_policy_result/gate_results/recount/reconstruction)。
- `scripts/recount-palette-orphans.py` — C11 と独立の走査経路で観測色 palette 孤児を再計数する common-mode 破り検査。
- `scripts/emit-verdict.py` — gate 結果 + findings へ決定論規則を適用し draft_hash 束縛 verdict を ESB_VERDICT_DIR へ発行。
- `references/evaluation-rubric.md` — 三値排他・evidence 接地・anti-overfit・被覆・ペルソナの採点観点。
- `references/resource-map.yaml` — Progressive Disclosure 読み順。
- `$CLAUDE_PLUGIN_ROOT/scripts/` — 共有ゲート `mermaid-validate.py` (C10) / `doc-emit.py` (C11)。
- `$CLAUDE_PLUGIN_ROOT/skills/run-extract-blueprint/` (C01) — verdict receipt を周回内の品質ゲート/差し戻し判定で読む消費側。
