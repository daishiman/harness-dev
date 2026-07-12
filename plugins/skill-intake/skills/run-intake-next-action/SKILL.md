---
name: run-intake-next-action
description: harness-creator / plugin-dev-planner への引き渡しモードを判定したいとき、summary.json から A/B/C/D/E/P のいずれかを決定論的に確定したいときに使う。
allowed-tools:
  - Read
  - Write
  - Bash
  - AskUserQuestion
kind: run
user-invocable: true
effect: local-artifact
source: plugins/skill-intake
source-tier: internal
last-audited: 2026-05-24
prefix: run
audit-trigger: monthly
hierarchy_level: L1
rubric_refs: []
role_suffix: null
owner: team-platform
since: 2026-05-22
version: 0.1.0
responsibility_refs:
  - prompts/R1-main.md
schema_refs:
  - schemas/output.schema.json
manifest: workflow-manifest.json
feedback_contract: # per-skill 評価基準(SSOT=scripts/feedback_contract_ssot.py)
  max_iterations: 3
  criteria:
    - id: IN1
      loop_scope: inner
      text: scripts/decide-mode.py が references/mode-catalog.md 判定表から mode を決定論導出し、同一 4 入力(summary/purpose/options/kickoff)で 2 回連続実行した next-action.json の (mode, reason) が完全一致かつ reason に引いた mode / 判定条件を文字列で含み、schemas/output.schema.json(additionalProperties:false)で検証 exit 0 になる
      verify_by: script
    - id: IN2
      loop_scope: inner
      text: handoff 確定前に Notion 公開完了 precondition(notion-publish-result.json 存在 + notion-log.json.status=='published' + page_id 有り)を assert し不成立は exit 2 で停止(逸脱B封鎖)、入力欠落は exit 3、mode=D で split_candidates 空なら mode=E へ格下げし reason に理由を残す、を機械検証できる
      verify_by: lint
    - id: OUT1
      loop_scope: outer
      text: 本スキルが mode 判定と next-action.json 生成のみに責務を絞り、run-skill-create/run-build-skill 等のスキル生成スキルを起動せず(allowed-tools に Skill/Task を持たない)mode/handoff_phase を後続への推奨情報に留め、Notion 公開は実行せず完了を検証するだけ、Phase1 pattern 不一致時のみ AskUserQuestion を直列 1 問で追認する設計になっている
      verify_by: elegant-review
---

# run-intake-next-action

## Purpose & Output Contract

Phase 11 担当。`summary.json` / `purpose.json` / `options.json` / `kickoff.json` と Notion 公開ログから、引き渡しモード A/B/C/D/E (`run-skill-create` 向け) / P (`run-plugin-dev-plan` 向け plugin 規模構想) を **決定論的に**確定し、後続アクション (handoff_target + handoff phase) を確定する単一責務スキル。判定表 (`references/mode-catalog.md`) で引いた mode と判定条件を `reason` に必ず残し、Phase 1 暫定 `kickoff.json.pattern` と一致しない場合のみ AskUserQuestion で 1 問追認する。

**入力**: `output/<hint>/summary.json` / `purpose.json` / `options.json` / `kickoff.json`
**出力**: `output/<hint>/next-action.json` (`schemas/output.schema.json` 準拠、`additionalProperties:false`)

```json
{
  "mode": "A|B|C|D|E|P",
  "reason": "kickoff.pattern=B を採用",
  "multi_skill_suspicion": false,
  "split_candidates": [{"name": "...", "responsibility": "..."}],
  "confirmed_with_user": false,
  "handoff_target": "harness-creator|plugin-dev-planner",
  "harness_creator_handoff_phase": "Step 1 (elicit)"
}
```

**完了条件**: `mode` 確定 + `reason` に判定根拠 (引いた mode / 判定条件) 含む + (`pattern` 不一致時) `confirmed_with_user=true` + schema 検証 exit 0。

**完了レポートの人間向け次アクション (出力契約)**: `next-action.json` は schema 互換のため mode / handoff_target / phase のみを持つ。人間向け完了レポートには、次に実行する 1 コマンドを必ず併記する。mode P は `/plugin-dev-plan "<構想要約>" --intake-json output/<hint>/intake.json --next-action-json output/<hint>/next-action.json`、mode A-E は `harness_creator_handoff_phase` に対応する `run-skill-create` / `run-build-skill` 起動案内を出す。handoff 先 skill (`run-skill-create` / `run-plugin-dev-plan`) が実行環境に存在しない単独 install 時は、完了レポートに「Notion ページ共有までが完了形。推奨アクションは開発環境 (repo clone) 用」の 1 行を必ず含める (推奨が実行不能な環境で完了形を誤認させない)。

**必須前提 (precondition gate)**: skill 生成 (`run-skill-create`) へ進む handoff を確定する前に、**Notion 公開完了が必須前提**である。`scripts/decide-mode.py` は `output/<hint>/notion-publish-result.json` が存在し `notion-log.json.status=="published"` (かつ `page_id` 有り) であることを assert し、不成立なら **exit 2** で停止して未公開のまま skill 生成へ横流れさせない (逸脱B封鎖)。CI / dry-run のみ `--allow-skip` で緩和可。

## Key Rules

1. **決定論判定**: `scripts/decide-mode.py` が `references/mode-catalog.md` 判定表から `mode` を導出する。LLM 勘の介在禁止。同点時のみタイブレークで LLM が選び `reason` に記録。
2. **Phase 1 突合の追認は不一致時のみ**: `kickoff.json.pattern` と一致なら AskUserQuestion 省略、不一致なら 1 問のみ (並列禁止)。mode P は pattern 軸 (A-E enum) の外のため常に不一致となり、追認 1 問を必発とする (意図済み)。
3. **D 格下げ規則**: `mode=D` で `split_candidates` が空のままなら `mode=E` に格下げし、`reason` に格下げ理由を残す。
4. **E は再ヒアリング扱い**: `mode=E` 確定時は `harness_creator_handoff_phase="P1-kickoff (re-intake)"` を必ず指定。
4b. **P は plugin-dev-planner 行き**: `mode=P` (plugin 規模構想: `plugin_scale=true` 宣言 / `component_requests[]` に hook/command 等の非 skill 種別 / skill 系 2 件以上、正本は `references/mode-catalog.md`「mode P 判定条件」) は `handoff_target="plugin-dev-planner"` とし、intake.json を `run-plugin-dev-plan` R1 の構想材料として推奨する (渡す § は plugin-root 正本 `plugins/skill-intake/references/handoff-contract.md`「plugin-dev-planner 分岐 (mode P)」参照)。P の `split_candidates[]` は planner R2 へ渡す任意の初期候補であり、空でも D のような格下げはしない。mode A-E は `handoff_target="harness-creator"`。
5. **固有名詞の非転記**: `split_candidates[*].responsibility` に個人名・社名・固有プロダクト名を残さない (variable_abstraction)。
6. **schema 準拠**: 出力は `schemas/output.schema.json` の `additionalProperties:false` を満たす。前置き・後書き禁止。
7. **責務単一・生成は起動禁止**: 本スキルは mode 判定と `next-action.json` 生成のみ。`run-skill-create` / `run-build-skill` / `capability-build` 等のスキル生成スキルを **起動しない (allowed-tools に Skill/Task を持たないので構造的にも不可)**。`mode` / `harness_creator_handoff_phase` は後続への**推奨情報**であり、本スキルや呼び出し元がそれを自動実行することは意図しない (実行はユーザーの明示的な別アクション)。ただし Notion 公開「完了」は推奨を出す必須前提として **検証** する (Rule 8、公開の実行はしないが未公開での横流れは封じる)。
8. **Notion 公開完了の precondition 検証**: `decide-mode.py` は handoff 確定前に `output/<hint>/notion-publish-result.json` 存在 + `notion-log.json.status=="published"` + `page_id` 有りを assert する。不成立なら exit 2 で停止 (逸脱B封鎖)。CI/dry-run のみ `--allow-skip` で緩和。

## ゴールシーク実行

### ゴール (Goal)

4 つの intake JSON から引き渡すモード A/B/C/D/E (`run-skill-create` 向け) / P (`run-plugin-dev-plan` 向け) が決定論的に確定し、`reason` (引いた mode / 判定条件) と `handoff_target` と `confirmed_with_user` が機械検証可能な `next-action.json` が schema 準拠で出力された状態になっている。

### 目的・背景 (Why)

モードが曖昧なまま後続 `run-skill-create` が起動すると、責務分割 (D) と生成パス (A/B/C) が破綻する。判定の属人化を `references/mode-catalog.md` 判定表 + `scripts/decide-mode.py` で機構的に防ぎ、Phase 1 の暫定 pattern と乖離した場合のみユーザー追認を取ることで、再現可能性と意図上書き防止を両立する。固定手順では入力欠落・判定表ヒットなし・split 候補欠落など実行時文脈に脆いため、未達条件を都度埋めるゴールシーク方式を採る。

### 完了チェックリスト (Checklist)

- [ ] **Notion 公開完了 precondition を充足**: `output/<hint>/notion-publish-result.json` 存在 + `notion-log.json.status=="published"` + `page_id` 有り。不成立なら exit 2 で停止し skill 生成へ進めていない (CI/dry-run のみ `--allow-skip` 緩和)
- [ ] `summary.json` / `purpose.json` / `options.json` / `kickoff.json` の 4 入力を Read 済みで、欠落時は exit 3 を返している
- [ ] `scripts/decide-mode.py` が `references/mode-catalog.md` の判定表 1 行から `mode` を導出し、`reason` にその引いた mode / 判定条件を文字列で含めている
- [ ] `kickoff.json.pattern` と `mode` が一致時は AskUserQuestion を発行せず `confirmed_with_user=false` のまま、不一致時は AskUserQuestion 1 問で `confirmed_with_user=true` を埋めている
- [ ] `mode=D` のとき `split_candidates[]` の各要素に `name` と `responsibility` 文字列が存在する。空のまま残ったら `mode=E` に格下げし `reason` に格下げ理由を追記している
- [ ] `mode=E` のとき `harness_creator_handoff_phase` が `P1-kickoff (re-intake)` になっている
- [ ] `handoff_target` が mode P で `plugin-dev-planner`、mode A-E で `harness-creator` になっている (schema の allOf 条件)
- [ ] handoff 先 skill が環境に存在しない単独 install 時、完了レポートに「Notion ページ共有までが完了形。推奨アクションは開発環境 (repo clone) 用」の 1 行を含めている
- [ ] 完了レポートに人間がそのまま実行できる次アクションを 1 コマンドで併記している (mode P は `/plugin-dev-plan "<構想要約>" --intake-json output/<hint>/intake.json --next-action-json output/<hint>/next-action.json`)
- [ ] `split_candidates[*].responsibility` に個人名・社名・固有プロダクト名が転記されていない
- [ ] `output/<hint>/next-action.json` が `schemas/output.schema.json` で検証 exit 0 (manifest `P4-emit` の `validate-next-action` hook)
- [ ] 同一入力 4 ファイルで 2 回連続実行した `next-action.json` の `(mode, reason)` が完全一致 (determinism)

### ゴールシークループ

未充足チェック項目を特定 → 該当局面の解消手順を立案 → 実行 → チェックリストで自己評価 → 全項目充足まで反復。固定の Step 順序は持たない。`workflow-manifest.json` の `phases[]` (`P1-load` / `P2-mode-decide` / `P3-confirm-if-diff` / `P4-emit`) は局面カタログ (順序は都度判断) として扱う。逸脱時は `prompts/R1-main.md` Layer 4.1 の exit code 規約 (exit 2=Notion 公開 precondition 未充足、exit 3=入力欠落・不正) に従いエスカレーション。最大反復回数は親オーケストレーター (`run-skill-intake`) のループ上限に従う。

## Gotchas

1. **判定表ヒットなしでも停止しない (decide-mode.py 実挙動)**: 該当行なしでも exit せず `kickoff.pattern` を既定採用する (verb_object 空→E / 連結語→D / plugin 徴候→P で上書き)。A-E/P 以外の未知 pattern は handoff 表引きの KeyError で異常終了する。exit 2 は Notion 公開 precondition 未充足時のみで、「ヒットなし→exit 2 / stderr 欠落条件」の停止は未実装。
2. **AskUserQuestion 並列禁止**: 不一致追認は 1 問ずつ。複数項目を 1 回でまとめない。
3. **schema 違反は exit 3**: `additionalProperties:false` を満たさない追加キーを出力に混ぜない。
4. **D の split は提案であり強制ではない**: ユーザーが単一スキル維持を選んだ場合は `multi_skill_suspicion=true` のまま `mode` を `A/B/C` に確定し直し、`reason` に上書き理由を残す。
5. **後続 phase 文言の固定**: `harness_creator_handoff_phase` は `references/mode-catalog.md` の右列文言を逐語コピー (drift 防止)。
6. **再ヒアリングループ防止**: `mode=E` が 2 回連続で出た場合は親 aggregator に escalate (本スキル単独でループしない)。

## Additional Resources

- `workflow-manifest.json` — `P1-load` / `P2-mode-decide` / `P3-confirm-if-diff` / `P4-emit` の機械可読定義 (`dependsOn` / `exitHook` / `fatal_exit_codes`)
- `prompts/R1-main.md` — R1-deterministic-mode-decision 責務プロンプト (7 層構造、`@next-action-advisor` agent)
- `schemas/output.schema.json` — `next-action.json` 出力契約 (`additionalProperties:false`)
- `references/mode-catalog.md` — A/B/C/D/E/P と handoff_target / handoff phase の対応表 (drift 防止の正本)
- `references/pattern-recognition-rules-pointer.md` — Phase 1 pattern 突合ルール集約 pointer
- `references/resource-map.yaml` — 参照ファイル一覧 (先読み用)
- `scripts/decide-mode.py` — 決定論判定ロジック (`--kickoff` / `--purpose` / `--options` / `--summary` / `--out` / `--allow-skip`)。冒頭で Notion 公開完了 precondition gate を実行 (不成立=exit 2)
- 親スキル: `run-skill-intake` (P11 委譲元。phase id は workflow-manifest.json の P11-next-action が正本)
- 後続スキル: `run-skill-create` (mode A-E) / `run-plugin-dev-plan` (mode P) — 本スキル出力 `next-action.json` の `mode` / `handoff_target` を受領
