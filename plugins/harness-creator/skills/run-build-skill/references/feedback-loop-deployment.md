# feedback-loop 配備 (default-ON)

量産プラグインに `run-skill-feedback` を 100% 再現性で同梱する仕組みの詳細。SKILL.md Step 11.5 から参照される。

## 5 層設計

| 層 | 目的 | 実装 |
|----|------|------|
| L1 SSOT 同期 | 発火条件文言の正本一本化 | `doc/notion-schema/skill-list.schema.json#feedback_protocol` を `notion-upsert-plugin.py` の `_load_feedback_protocol()` 経由で全派生物が引く |
| L2 周知 | 発火経路 (`/run-skill-feedback <plugin>`) を量産先で見える化 | `plugin.json` description / README / commands / agents いずれかに記載 |
| L3 配備 | 量産先に skill を物理配置 | phase `feedback-deploy` が `<target-plugin>/skills/run-skill-feedback` を実体コピーで冪等配備 |
| L4 強制 | 周知/配備の有無を CI で機械検査 | `scripts/lint-feedback-protocol.py --strict` の R6 (周知) / R7 (配備存在) |
| L5 検証 | schema / SKILL.md / upsert 三者整合 | 同 lint の R1-R5 (offline、NOTION_TOKEN 不要) |

## 配備フロー

```
brief.kind ∈ {run, ref, assign, delegate, wrap}
  └─ build pipeline (workflow-manifest.json)
       └─ phase: feedback-deploy (default_on: true, dependsOn: trace-write)
            └─ scripts/render-combinators.py apply_feedback_loop(<plugin>)
                 └─ <target-plugin>/skills/run-skill-feedback
                      (実体コピー。plugin 境界を越える symlink は marketplace bundle 同梱時のみ禁止 — 下記「禁止」節の例外参照)
```

harness-creator 自身は自動除外 (正本側への自己コピーは不要)。

acceptance_tier=live と導出される新規 skill (正本 `scripts/validate-build-plan.py` の `derive_acceptance_tier`) は OUT criteria に `verify_by: live-trial` を最低1件携帯すること — repo-root `scripts/lint-feedback-contract.py` が ratchet 強制する (baseline=`scripts/live-trial-criteria-baseline.json` は既存 skill の WARN 免除のみで追記禁止)。

## opt-out

`brief.no_feedback_loop: true` または CLI `--no-feedback-loop` 指定時のみ skip。

- trace.layer_decisions に理由 (drift リスクを引き受ける明示的判断) を必須記録。
- CI で R7 が WARN になり、`--strict` で fail。

## dogfooding 境界 (SSOT)

harness-creator 自身 (生成器メタプラグイン) への除外/非除外は **機構ごとに非対称**。制御リテラル `"harness-creator"` を散在させず、`scripts/feedback_contract_ssot.py` の述語を全 consumer が import 共有する (唯一の正本)。

| 機構 | harness-creator | SSOT 述語 | 理由 |
|------|---------------|-----------|------|
| Stop hook decision:block (`run-elegant-review/scripts/check-review-trigger.py`) | **除外** | `is_stop_block_exempt` | 自己編集セッションの自己ブロック=評価不能 (無限ループ) を回避 |
| feedback-loop 配備/周知 — 実体コピー (`render-combinators.py apply_feedback_loop`) / R6・R7 (`lint-feedback-protocol.py`) | **除外** | `is_feedback_deploy_exempt` | 生成器自身が `run-skill-feedback` の正本。自己コピーは不要 |
| content-review verdict — CI/pre-push (`lint-content-review.py`) | **非除外** | `is_content_review_exempt` (常に False) | dogfooding 対象。自己改善の品質も機械強制する |
| iter-improve (実走 eval 駆動の反復改善) が harness-creator 自身 / エンジン閉包 (`run-elegant-review`・convergence-policy・content-review 経路・`feedback_contract_ssot.py`) を対象とする場合 | **被験体コピー必須** | `requires_subject_copy` | エンジンが自分自身を実走改善すると評価器と被験体が同一閉包になり自己確証する。1 周完結の elegant-review self-review は従来通り直接編集可 |

除外プラグインを足す / 意味を変える際は SSOT 述語だけを編集すれば全 consumer に伝播する。

## 禁止

- plugin 境界を越える symlink (**distributable な量産先が run-skill-feedback を marketplace bundle に同梱する場合のみ**): `plugins/<plugin>/skills/run-skill-feedback -> ../../harness-creator/...` 等は、install 時に symlink 先が bundle 外なら dangling するため禁止 (この経路の配備は実体コピー `apply_feedback_loop()` に一本化する)。
  - **例外 (repo 内メタ plugin)**: `distributable:false` または `package.exclude` で run-skill-feedback を bundle から除外し marketplace install の対象にしない repo 内メタ plugin は、harness-creator SSOT への symlink を許容する (bundle に同梱されず dangling しない・DRY で正本一本化)。実例: `plugin-dev-planner` (distributable:false) / `skill-intake` (`package.exclude: skills/run-skill-feedback/**`) は `skills/run-skill-feedback -> ../../harness-creator/skills/run-skill-feedback` の symlink 実体を保持する。本禁止規約が対象とするのは「distributable な量産先の bundle 同梱」であって、これら除外済みメタ plugin ではない。
- 手動コピー: `cp -r ...` 等。配備は `apply_feedback_loop()` に一本化し、drift は lint/CI で検出する。
- 量産先 SKILL.md での `feedback_protocol` 文言再定義: SSOT を持たない drift の温床。
- 発火条件追加を SKILL.md / triggers 先行編集で行うこと: 必ず schema → lint → 派生物同期の順。
- live-trial / iter-improve の量産先配備: 実行 acceptance はローカル開発環境限定 (composition invariant に明記)。本節の配備対象は `run-skill-feedback` のみ。

## 関連

- `workflow-manifest.json` phase `feedback-deploy`
- `schemas/build-flags.schema.json#no_feedback_loop`
- `scripts/render-combinators.py apply_feedback_loop()`
- `/scripts/lint-feedback-protocol.py` (top-level、R1-R7)
- `plugins/harness-creator/skills/run-skill-feedback/SKILL.md`
