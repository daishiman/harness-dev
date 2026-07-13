---
id: P05
phase_number: 5
phase_name: implementation
category: 実装
prev_phase: 4
next_phase: 6
status: 未実施
gate_type: tdd-green
entities_covered: [C01, C02]
applicability:
  applicable: true
  reason: ""
---

# P05 — implementation (実装・TDD Green)

## 目的
P04 で設計したテストケースを green にする最小実装を、C01 (run-plugin-dev-plan skill) と C02 (assign-plugin-plan-evaluator skill) の既存ファイルへの Edit 差分として行う。本 phase は計画 (L3) であり実コードは書かないが、後段 build (L4・run-skill-create の Edit mode) が従うべき実装設計をプローズで確定する。

## 背景
C1/C2/C3 はいずれも既存の決定論ゲート script への狭い拡張であり、新規ファイルは C3 の self-check script 1 本のみ。C6/C7/C10/C11 は新規 script 2 本 (いずれも C01 の scripts/ 配下)、C8/C12 は C02 の既存プロンプト/schema/rubric への拡張である。既存関数のシグネチャは全て後方互換 (デフォルト引数) で拡張し、既存呼び出し元 (SKILL.md の script_refs 起動・既存テスト) を壊さない。

## 前提条件
- P03 の design-gate を通過している。
- P04 のテストケース設計が確定している。

## ドメイン知識
- **C1 実装設計**: `check-runtime-portability.py` へ `_target_plugin_slug(plan_dir: Path) -> str | None` ヘルパーを新設する (`<plan_dir>/goal-spec.json` を読み `target_plugin_slug` キーを返す・ファイル不在/キー欠落/JSON parse error は None を返し例外を投げない fail-soft 設計)。`check_inventory(data, target_plugin_slug=None)` のシグネチャへ `target_plugin_slug` を追加し、非 None のときのみ新チェック (R) を実行する: 各 component の `build_target` が `plugins/<slug>/` 形式のとき `<slug>` が `target_plugin_slug` と不一致なら violation を追加する (`plugins/` 始まりでない build_target は既存 (Q) が別途捕捉するため (R) の対象外)。`main()` から `_target_plugin_slug(Path(args.plan_dir))` を呼び `check_inventory` へ渡す (CLI 引数は追加しない・既存の 1 引数起動 `check-runtime-portability.py <PLAN_DIR>` のまま)。
- **C2 実装設計**: `check-build-handoff.py` へ `_load_inventory_components(plan_dir: Path) -> list[dict]` を新設する (`<plan_dir>/component-inventory.json` の `components[]` を返す・不在/parse error は空 list を返す fail-soft)。`ENTRY_POINT_KEY_BY_KIND = {"skill": "skills", "sub-agent": "agents", "slash-command": "commands"}` を定数として追加する。`_check_manifest_entry_points_coverage(entry_points: dict, comps: list[dict], prefix: str) -> list[str]` を新設し、`comps` のうち component_kind が `ENTRY_POINT_KEY_BY_KIND` に存在するものについて、対応する entry_points リストへ component の `name`/`skill_name` が含まれるかを検査し、未網羅の component id を violation として返す。`_check_manifest_draft(path, target_plugin_slug, prefix, comps=None)` へ `comps` 引数を追加し (既定 None=既存動作維持)、`comps` が非 None のときのみ `_check_manifest_entry_points_coverage` を呼ぶ。`_check_envelope()` から `_load_inventory_components(plan_dir)` を呼び出し結果を `_check_manifest_draft` へ渡す。
- **C3 実装設計**: 新規 `scripts/check-harness-coverage-selfcheck.py` を run-plugin-dev-plan skill 内部に追加する。`subprocess.run(["python3", "scripts/validate-harness-coverage.py", "--json"], cwd=repo_root, capture_output=True)` でレポートを取得し (repo-root cwd 前提は既存 CI 規約と同一)、出力中の `plugin-dev-planner` 行を抽出して 6 種別 (mechanical/llm_eval の対を含む) が全て測定/宣言されている (欠落キーが無い) ことを検査する。現状の達成率数値は判定に使わず「軸が宣言されているか」の構造検証に限定する (Goodhart 回避・環境ポリシー準拠)。`.github/workflows/governance-check.yml` の plugin-dev-planner conformance block へ本 script の呼び出しを 1 ステップ追記する (repo-level 編集のため handoff.open_issues に gap として記録し build 時に人手/別 PR で反映する)。`tests/test_ci_integration.py` へ `test_governance_check_has_harness_coverage_selfcheck` を追加し、追記されたステップ文字列の存在を固定する。
- **後方互換の担保**: C1/C2 いずれも新規引数はデフォルト値で無効化されるため、既存呼び出し元 (SKILL.md 記載の起動コマンド・他 plan に対する既存テスト) の挙動は変化しない。C3/C6/C7/C10/C11 は完全新規ファイルのため既存コードへの影響が無い。C8/C12 は既存プロンプト手順への追記のみで既存 step の削除・変更は行わない。
- **C6/C7 実装設計**: 新規 `scripts/check-generative-fidelity.py` を run-plugin-dev-plan skill 内部に追加する。`AMBIGUOUS_VOCAB_DENYLIST = ("適切に", "しっかり", "うまく", "品質を高める", "なるべく", "できるだけ", "効果的に", "柔軟に", "十分に", "必要に応じて")` を定数として定義する (P02 で確定した 10 語)。`detect_ambiguous_vocab(text: str) -> list[str]` が部分文字列一致 (`if word in text`) で該当語を列挙する (C6)。`classify_denylist_context(location, line_text) -> "violation" | "ignored_context"` を新設し、denylist 定義そのもの、コード/定数名、`満たさない例` 配下の否定例本文は ignored_context として構造化結果へ記録するが exit 判定対象に含めない。`detect_uncustomized_sections(phase_body: dict[str, str]) -> list[str]` が `specfm._PHASE_SECTION_HINT` の各節本文と対応する生成本文を `.strip()` 後に `==` 比較し、一致した節名を列挙する (C7)。呼び出し元 `main(plan_dir)` は phase 本文 8 節と component-inventory.json の goal/checklist/criterion 文字列を走査し、検出結果を WARN (denylist violation) / FAIL (未カスタマイズ) / ignored_context の構造化 JSON として stdout へ出す (exit0=violation/FAIL 0 件、exit1=1 件以上、既存 script 群と同じ exit 規約)。
- **C10/C11 実装設計**: 新規 `scripts/check-downstream-harness.py` を run-plugin-dev-plan skill 内部に追加する。`REDUCED_REQUIREMENT_PHASES = ("P03", "P07", "P09", "P10")` を定数として定義する (P02 で確定した適用強度分類)。各 phase ファイルの `## 完了チェックリスト` 節本文を `check-spec-frontmatter.py` と同じ最小 Markdown パーサ (specfm 経由) で取得し、`### 受入例` と `### 事前解決済み判断` の見出し行の存在を正規表現 (`^### 受入例` / `^### 事前解決済み判断`、複数行モード) で検出する。`REDUCED_REQUIREMENT_PHASES` に含まれる phase は見出しの存在のみを検査し (簡略形可)、それ以外の phase は見出し直下に非空の箇条書き本文が最低 1 行あることまで検査する (フル要件)。欠落は phase id 付きで violation として返す。
- **C8/C12 実装設計**: `assign-plugin-plan-evaluator/prompts/R1-evaluate.md` の既存 step 4 (「C1/C2-004 を LLM 意味判定」) の直後に、C8 (生成された phase 本文について下流 builder AI が追加質問なしで実行着手できる具体度を genuine 判定し、曖昧箇所を具体的に指摘する) と C12 (C10/C11 で検出された受入例・事前解決済み判断のサブ節が実際に下流実行者の追加質問を防ぐ実効性を持つかを genuine 判定する) の 2 判定ステップを追記する。判定結果は `plan-findings.json` の `findings[]` へ `bucket: "layer-a-generative-fidelity"` (C8) / `bucket: "layer-b-downstream-harness"` (C12) の新規 bucket として記録する (`conditions` の C1-C4 構造は変更しない)。`assign-plugin-plan-evaluator/schemas/plan-rubric.json` の `semantic_checks` へ既存 S1/S2 と同型の新規エントリ (`id: S3` = layer-a-generative-fidelity, `id: S4` = layer-b-downstream-harness、いずれも `runner: llm-only`) を追加する。`deterministic_gates`/`conditions` は変更しないため `test_gate_parity.py` の 9 parity テストへの影響は無い。

## 成果物
- C1: `check-runtime-portability.py` の Edit 差分設計 (ヘルパー新設 + シグネチャ拡張 + 新チェック (R))。
- C2: `check-build-handoff.py` の Edit 差分設計 (ヘルパー新設 2 件 + シグネチャ拡張)。
- C3: 新規 `check-harness-coverage-selfcheck.py` + `governance-check.yml` 1 ステップ追記設計 (open_issues 起票)。
- C6/C7: 新規 `check-generative-fidelity.py` (denylist 検出 + フォールバック完全一致検出)。
- C10/C11: 新規 `check-downstream-harness.py` (受入例/事前解決済み判断サブ節検出・縮小要件 phase 分岐)。
- C8/C12: `R1-evaluate.md` への 2 判定ステップ追記 + `plan-rubric.json` への semantic_checks (S3/S4) 追記設計。

## スコープ外
- 実 `plugins/plugin-dev-planner/` への実コード反映 (L4 build・本 plan の対象外)。
- `.github/workflows/governance-check.yml` の実編集 (plugins/ 外・component 化せず open_issues で gap として建て付け、実編集は build 時の別 PR/手動反映に委ねる)。
- `plan-findings.schema.json` の `conditions` 構造変更 (C8/C12 は findings[] の新規 bucket に留め、schema 自体は変更しない)。

## 完了チェックリスト
- [ ] C1 の実装設計が `_target_plugin_slug`/`check_inventory` の後方互換シグネチャ拡張として確定している。
- [ ] C2 の実装設計が `_load_inventory_components`/`_check_manifest_entry_points_coverage`/`ENTRY_POINT_KEY_BY_KIND` として確定している。
- [ ] C3 の実装設計が新規 self-check script + governance-check.yml 1 ステップ追記 (open_issues 経由) として確定している。
- [ ] C6/C7 の実装設計が `check-generative-fidelity.py` の denylist 定数 + 完全一致検出関数として確定している。
- [ ] C6 の ignored_context 分類が実装設計に含まれ、denylist 説明文や満たさない例が自己誤検出されない。
- [ ] C10/C11 の実装設計が `check-downstream-harness.py` の縮小要件 phase 定数 + サブ見出し検出関数として確定している。
- [ ] C8/C12 の実装設計が `R1-evaluate.md` 追記ステップ + `plan-rubric.json` semantic_checks (S3/S4) 追記として確定し、conditions/schema 構造を変更しないことが明示されている。
- [ ] 全設計が既存呼び出し元・既存テストへ破壊的変更を持たないことが明示されている。

### 受入例 (満たす例 / 満たさない例)
- 満たす例: C1-C12 全てについて、新規/拡張対象ファイル名・関数名・シグネチャ・検出ロジックが具体的に (プレースホルダなしで) 記述されている。
- 満たさない例: 「C6/C7 を適切に実装する」のように対象ファイルや関数名が特定されないまま実装設計が完了扱いになっている。

### 事前解決済み判断
- 分岐点: C8/C12 の判定結果をどこへ記録するか (新規 conditions 追加 vs 新規 findings bucket) → 判断: 新規 findings bucket (`plan-findings.schema.json` の `conditions` は additionalProperties:false + required 固定であり `test_evaluate_plan.py` の既存アサーションを壊さないため)。

## 参照情報
- `phase-04-test-design.md`。
- `plugins/plugin-dev-planner/skills/run-plugin-dev-plan/scripts/check-runtime-portability.py`。
- `plugins/plugin-dev-planner/skills/run-plugin-dev-plan/scripts/check-build-handoff.py`。
- `scripts/validate-harness-coverage.py` / `.github/workflows/governance-check.yml`。
- `plugins/plugin-dev-planner/skills/run-plugin-dev-plan/scripts/specfm.py` (`_PHASE_SECTION_HINT`)。
- `plugins/plugin-dev-planner/skills/assign-plugin-plan-evaluator/prompts/R1-evaluate.md` / `schemas/plan-findings.schema.json` / `schemas/plan-rubric.json`。
- 後続 P06 (test-run)。
