# ハーネス・カバレッジ仕様 (Harness Coverage Spec)

> ステータス (2026-10-10 更新, `make harness-coverage` が唯一の現状値正本): 全12軸 (6種別×2軸) 計測済。
> CI (harness-creator-kit-ci.yml) では `make coverage-gate` と `make harness-coverage` が **WARN (非ブロック)**、`make harness-ratchet` (floor 回帰ガード, §4-4) が **blocking** で配線済。
> **総合 `spec_met=false` (未達軸あり)**。達成軸数・未達内訳は drift するため本 doc に現状の数値を焼かず (数値は §6 の日付つきスナップショットにだけ置く)、
> 確定値は常に `python3 scripts/validate-harness-coverage.py` (= `make harness-coverage`) の出力を唯一の正とする。
> 数値は一切水増ししない (未計測=未計測、低カバレッジ=低カバレッジで報告 / Goodhart 回避)。全て genuine な実テスト/実レビューで到達。
>
> 注 (elegant-review 2026-06-30 / MD-03): 旧 header は「達成 12/12・spec_met=true・gate 配線済」と
> 断定していたが、body (§6/§8) の FAIL 記述および実 CI に gate 未配線だった事実と矛盾していた。
> header を機械出力 SSOT へ委譲し断定数値を除去 (status drift の構造的封じ込め)。

> 用語注記 (2026-07-02): 本 spec の「ハーネス」は構築物総体 (scripts/skills/agents/commands/hooks/docs) の品質装具を指す。
> plugin 固有名 `harness-creator` はこの総体を**構築する**メタ能力であり同系譜の概念 — 本 spec は
> harness-creator が構築するハーネスの品質最低条件を定義する関係にある。境界規約 (改名の経緯含む) は CONVENTIONS.md「用語規約」を参照。

## 1. 仕様 (Requirement)

ハーネス仕様を満たす**最低条件**として、テストカバレッジ **80% 以上** を課す。
対象は「LLM が書く内容」を含む全 artifact 種別:

| 種別 | 含むもの |
|---|---|
| scripts | `scripts/*.py`, `plugins/*/scripts/*.py`, `plugins/*/skills/*/scripts/*.py` |
| skills | `plugins/*/skills/*/SKILL.md`(本文/prompts/ゴールシーク) |
| agents | `plugins/*/agents/*.md`(サブエージェント) |
| commands | `plugins/*/commands/*.md`(スラッシュコマンド) |
| hooks | `plugins/*/hooks/*.md` (hooks ディレクトリ直下の Markdown。validator `measure_md_type("hooks", "hooks")` の実際の数え方。2026-10-10 時点の実体は `plugins/skill-intake/hooks/README.md` の 1 件)。`hooks.json` で配線される hook スクリプト (`plugins/*/hooks/*.py`・`*.sh`) はこの軸にも scripts 軸にも入らない集計対象外 (§8 残課題) |
| docs | `doc/**/*.md`(設計書・参照)。ただしパスに「参考Skill」「Agent Skill大全」を含む外部参考資料は除外 (validator の `DOC_EXTERNAL_REFERENCE`) |

## 2. 二軸 (Two Axes) — **両方** で 80% 以上

機械的確認だけでは不十分。LLM が評価した内容でも 80% を満たすこと。

| 軸 | 定義 | 計測 |
|---|---|---|
| **mechanical(機械的)** | 行カバレッジ / criteria-test 被覆 / artifact 単位の test・fixture 存在率 | `pytest --cov`(scripts) / `validate-llm-coverage.py`(skills criteria+checklist) / artifact 別 lint |
| **llm_eval(LLM性能評価)** | LLM 評価器 (content-review elegance/rubric, assign-skill-design-evaluator, run-elegant-review) の verdict=PASS かつ score>=80% である artifact の割合 | content-review verdict 集計 / evaluator rubric score |

### skill の kind 別カバレッジパス (除外でなく kind 適合の検証)

skill は sub-kind ごとに「何を検証すれば品質を担保したことになるか」が異なる。**どの kind も検証ゼロ(全ゲート除外)にしない**:

| sub-kind | mechanical | llm_eval |
|---|---|---|
| run/wrap/delegate (loop) | criteria 検証テスト (inner=lint exit0 / outer=verdict PASS) | content-review (elegance+rubric) verdict=PASS |
| assign (評価系) | 同梱 scripts の行カバレッジ | evaluator verdict=PASS |
| **ref (辞書型/参照型)** | **source-traceability**: `source`/`source-tier`/`last-audited`/`audit-trigger` 充足 | **ref-review verdict**: 参照内容が `source` と整合 (`eval-log/coverage/skills/<plugin>__<skill>.json` の `llm_eval.verdict=PASS`) |

ref は behavioral criteria を持たないため criteria/content-review からは除外されるが、**代わりに source-traceability + ref-review が必須カバレッジ**。「除外」は「無検証」ではなく「kind に適した別検証へ振り替え」を意味する。harness-creator (run-build-skill) はビルド時にこの kind 別パスを毎回適用する。

**性能評価基準 (重要)**: llm_eval 軸は「評価器が内容の質を採点し、その合格率/スコアが 80% 以上」を要求する。
単なる存在チェック (機械的) と区別し、内容の妥当性を LLM が判定した結果で 80% を担保する。

## 3. 判定 (Compliance)

`validate-harness-coverage.py` が 種別×二軸 = 12 セルを集計し、**全セルが instrumented かつ met** のときのみ
`spec_met=true`。未計測セルが1つでもあれば `spec_met=false`(未計測を緑に偽装しない / Goodhart 回避)。

> 「これら全てを満たさないなら、ハーネス仕様も不十分」(ユーザー基準) を `spec_met` で機械表現する。

## 4. 強制 (Enforcement) — 計測+WARN → 段階的 gate

1. **計測+WARN(現在)**: `make coverage` / `make llm-coverage` / `make harness-coverage` が全 artifact を計測し
   80% 未満を WARN 表示 (緑を壊さない ratchet baseline)。
2. **新規 gate(fail-closed)**: `make coverage-gate`(= `validate-llm-coverage.py --gate-new --since LLM_COV_SINCE`)が
   `LLM_COV_SINCE` 以降に since された新規 loop-kind skill を <80% で exit1。新規生成物から必達。
3. **既存 ratchet**: 既存 artifact は backfill で段階的に 80% へ底上げ。`spec_met=true` で完了。
4. **回帰ガード (blocking)**: `make harness-ratchet` (= `validate-harness-coverage.py --ratchet`) が各軸の現値を `eval-log/harness-coverage-floor.json` の floor と比べ、下回る軸があれば exit 1 (CI で blocking)。floor は改善時に `--update-floor` で引き上げ、下げない。

## 5. 自動化 (量産先への伝播)

harness-creator (run-build-skill) はビルド時に **全 kind で本仕様を毎回満たす** ことを完了チェックリストで
強制する (SKILL.md 完了チェックリスト + R1-scaffold ドメインルール)。kind 別:
- loop (run/wrap/delegate): [[feedback_contract]] criteria + criteria 検証テスト + content-review verdict
- ref (辞書型): source-traceability(source/source-tier/last-audited/audit-trigger) + ref-review verdict
- assign: evaluator verdict / 全 kind: 同梱 scripts の機能テスト ≥80%

新規スキルは `coverage-gate` で 80% 必達 (ratchet)。「ref は除外」ではなく「ref に適した別検証へ振替」
を徹底し、辞書型スキルが品質ゲートから抜け落ちないようにする。

## 6. 現状ダッシュボード (2026-06-24 時点のスナップショット。現値は `make harness-coverage`)

本節 (下位の小節を含む) の数値はすべて 2026-06-24 時点の記録であり、本 doc で数値を置くのは本節だけである。

| 種別 | mechanical | llm_eval |
|---|---|---|
| scripts | 56.5% (subprocess+import smoke+機能テスト57本) | **87.2% ✅** (179本 code-review, PASS+実バグ7修正) |
| skills | **91.5% ✅** (criteria 検証テスト tests/criteria/) | **81.2% ✅** (非ref=content-review / ref=ref-review verdict, ref も計測対象に) |
| agents | **100.0% ✅** | **82.4% ✅** (deep-verify→実欠陥修正後) |
| commands | **100.0% ✅** | **88.9% ✅** (deep-verify→実欠陥修正後) |
| hooks | **100.0% ✅** | **100.0% ✅** (README に検証ゲート script 追記) |
| docs | **100.0% ✅** (44本 doc-review 記録) | **84.1% ✅** (44本中 37 PASS, 実欠陥7検出) |

**総合 (2026-06-24): FAIL (ハーネス仕様 未達)**。12軸中 **計測済 12 / 達成 11**。残 **1 軸 = scripts mechanical (56.5%, network系HTTPモック要)**。

注: hooks 軸は当時も今も `plugins/*/hooks/*.md` (README 1 件) だけの値で、hook スクリプトの品質は表さない (§1・§8)。

### ref(辞書型)スキルの genuine 計測化 (2026-06-24)
ref を「除外」から「ref-review verdict(source-traceability)で計測」へ昇格。13 ref skill をレビューし
**4 PASS / 9 FAIL** = ref スキルに広範な実欠陥を確認 (resource-map の prompt 名 dangling[8件・修正済] /
upstream rubric pointer の references/ 欠落[rubric governance 横断・follow-up] / rubric version 1.2.0 vs
1.3.0 drift / 条番号ずれ / TODO(human) 残存)。harness-creator は今後 ref ビルド時に source-traceability +
ref-review を必須化 (§kind 別パス)。skills llm_eval = (非ref 35 PASS + ref 4 PASS)/48 = 81.2%。

### 多エージェント backfill で発見・修正した実バグ (genuine LLM 評価の価値)
deep-verify / code-review は機械 lint を通る実バグを多数検出。修正済: agents/commands 12件 (dangling/schema虚偽/enum drift/placement) + run-intake-revise effect enum + re-evaluate-on-rubric-bump のパス2重バグ (parents[2]→[1] + references/ 欠落でコア機能が常に no-op だった)。未修正で FAIL 記録に正直に残置 (follow-up, 移行絡みで複雑): check-rubric-sync / lint-template-variables (creator-kit 移行でデータファイル取り残し) / build-claude-settings (hook event allowlist stale) / notifier-check (TODO(human) 未実装) / check-five-axes-coverage (argv ガード皆無)。

### scripts mechanical が 80% に届かない理由 (honest)
network/Notion/keychain 系のスクリプトは実 API を叩かないと残行に到達しない (副作用回避方針で意図的に未到達)。80% には HTTP モック層の大規模導入が必要 = 別プロジェクト規模。import smoke + 純関数 + エラー経路は genuine に網羅済。
(skills llm_eval の ref-kind は content-review 対象外 [lint-content-review EXEMPT_KINDS={ref}] のため、ref は ref-review verdict で計測する (§2 kind 別パス)。)

### 多エージェント deep-verify の決定的発見 (llm_eval 軸)
strict 二段検証(owner skill / schema / 参照実在 / placement invariant 照合)で、初回の甘い LLM レビュー
(26/27 PASS)を排除すると genuine PASS は agents 8/17・commands 6/9。**harness 自身の agents/commands に
12件の実欠陥**を検出: dangling 参照(quality-rubric.md)、schema 虚偽(「未整備」主張だが schema 実在・配線済)、
schema 非適合(required 欠落/余剰キーで validate FAIL)、owner-flow 矛盾、placement invariant 違反(agents が
prompts SSOT を薄くミラーせず矛盾重複)。多くが既知 memory (prompt-creator dangling / skill-intake schema drift)
と一致。**機械 lint は通るが意味照合では実バグがある** = これが「LLM が評価して 80%」を課した本質的価値。
genuine 80% 到達 = これら実欠陥の修正 (テスト追加では届かない)。

## 7. 計測機構 (配線済)

- `pytest-cov` + `.coveragerc`(parallel) + `sitecustomize.py`(`coverage.process_startup`): subprocess 起動スクリプトの行カバレッジ回収。`make coverage` が `COVERAGE_PROCESS_START` 込みで実行。
- `tests/test_scripts_smoke.py`: 全スクリプトの import smoke (module-body を genuine に実行。import 不可=設計 smell として理由付き skip)。
- `scripts/validate-llm-coverage.py` / `scripts/validate-harness-coverage.py` (自身も行カバレッジで dogfood)。
- coverage レコード規約: 非コード artifact は `eval-log/coverage/<type>/<key>.json`(`mechanical:bool` / `llm_eval:{verdict,score}`)。実テスト/実レビューの産物のみ登録 (空宣言禁止)。
- gate: `make coverage-gate`(新規 skill fail-closed) / `validate-harness-coverage --gate`(spec 全体) / `make harness-ratchet`(floor 回帰ガード, CI blocking)。生成契約 R1 に coverage 携帯を必須化。

## 8. 達成への follow-up (残課題。未達軸と現値は `make harness-coverage` の出力を正とする)

**未達軸** (どの軸が未達かは `make harness-coverage` の `spec_met` と各軸の `met` で確かめる。本節には数値を置かない):
- [ ] **scripts mechanical**: network/Notion/keychain 系スクリプトの HTTP モック層導入が必要 (別プロジェクト規模)。それ以外の lint/builder/hook は機能テストで網羅済。
- [ ] **docs**: 設計書の doc-review 記録 (`eval-log/coverage/docs/`) を本文の更新に追従させる。本文を直したら記録は独立レビューで取り直す (sha256 不一致の記録は無効)。
- [ ] **hooks の集計対象**: validator は hooks を `plugins/*/hooks/*.md` だけで数え、`hooks.json` で配線された hook スクリプト (`plugins/*/hooks/*.py`・`*.sh`) は scripts 軸にも hooks 軸にも入らない。hooks 軸の値は hook スクリプトの品質を表さない。validator の対象を hook スクリプトへ広げるかは別途判断する (本 spec の §1 は現行の数え方を正として記述)。

**内容 follow-up (verdict の PASS 率で達成した軸でも、個別の欠陥は残置)**:
- [ ] ref の実欠陥 (upstream rubric pointer の references/ 欠落 = rubric governance 横断 / rubric version drift / 条番号ずれ)。
- [ ] docs の実欠陥: creator-kit→plugins 移行への設計書の追従 (32・34 章は 2026-10-10 に追従。他の章の状況は各章の coverage 記録を参照)。
- [ ] rubric governance pathing (references/ 欠落) と rubric version drift の同期 (run-skill-rubric-governance 手順)。
