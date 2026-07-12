---
name: run-intake-option-catalog
aliases:
  - ref-intake-option-catalog
description: 外部連携カタログを参照して候補を選択肢化したいとき、purpose.json を基に options.json を生成したいときに使う。
allowed-tools:
  - Read
  - Write
  - AskUserQuestion
kind: run
prefix: run
user-invocable: true
disable-model-invocation: false
effect: local-artifact
source: plugins/skill-intake
source-tier: internal
last-audited: 2026-05-24
audit-trigger: monthly
hierarchy_level: L1
rubric_refs: []
owner: team-platform
since: 2026-05-22
version: 0.1.0
responsibility_refs:
  - prompts/R1-search-summarize.md
schema_refs: []
manifest: references/resource-map.yaml
feedback_contract: # per-skill 評価基準(SSOT=scripts/feedback_contract_ssot.py)
  max_iterations: 3
  criteria:
    - id: IN1
      loop_scope: inner
      text: "生成された options.json が selected_integrations と rejected の2配列を持つ形式で、各 selected 候補に tier ∈ {required, optional}/id/name が付与され、rejected 全項目が空でない reason を持つことを lint で機械検証できる(reason 空文字は fail)。"
      verify_by: lint
    - id: IN2
      loop_scope: inner
      text: "selected_integrations の全 id が plugin 共有 references/integration-catalog.md に実在するカタログ項目であり、カタログ外(新規提案)の id が混入していないことを lint で機械検証できる。"
      verify_by: lint
    - id: OUT1
      loop_scope: outer
      text: "スキル全体がユーザ目的(purpose.json の verb_object に親和する連携を読み取り専用カタログから過不足なく引き当て、tier=required を漏れなく確定させ後続 phase の責務分離を崩さない)を最適に反映し、カタログ参照と options.json 生成のみへ責務が最小化されていること。"
      verify_by: elegant-review
    - id: OUT2
      loop_scope: outer
      text: "対話可能な実行環境で purpose.json とカタログから導出した候補を AskUserQuestion で1問ずつ直列提示し、実ユーザーの selected / rejected 回答と却下 reason を取得して options.json へ反映できることを live trial 証拠で確認する。"
      verify_by: live-trial
---

# run-intake-option-catalog

## Purpose & Output Contract

Phase 6 担当の **連携選択肢生成 run skill**。orchestrator (`run-skill-intake`) から Skill tool で委譲され、`purpose.json` の `true_purpose.verb_object` を起点に外部連携候補 (Slack / Notion / Gmail / Drive / Linear 等) を静的カタログから引き当て、ユーザー選択を経て `options.json` を生成する。カタログ自体は読み取り専用で、本 skill の write は `options.json` 生成に限る。

**入力**: `purpose.json`, `references/integration-catalog-pointer.md` 経由の integration カタログ
**出力**: `output/<hint>/options.json` (`selected_integrations` / `rejected` 配列)
**任意フィールド (mode P 判定入力)**: `plugin_scale` (boolean: ヒアリング中に plugin 規模構想 (hook/command 等複数コンポーネント) が明示されたとき true) / `component_requests[]` (string[]: ユーザーが要望したコンポーネント種別 (skill/hook/command/agent/mcp 等))。Phase 11 `run-intake-next-action` の decide-mode.py が mode P 判定入力として読む。
**完了条件**: tier=required の連携が全て選択または除外 (reason 付き) で確定し、ユーザーが選択肢確認に応答済み。
**性質**: run kind。責務プロンプトは `prompts/R1-search-summarize.md`、参照カタログは `references/` 配下に閉じる。カタログの書き換えは行わない (write は `options.json` のみ)。

## Key Rules

1. **カタログ参照のみ**: 新規連携の追加・カタログ書き換えは行わず、読み取り専用で振る舞う。
2. **必須/任意 tier の明示**: 各候補に `tier ∈ {required, optional}` を必ず付与する。
3. **rejected の理由必須**: ユーザーが除外した候補には `reason` を必ず記録する (空文字禁止)。
4. **新規連携の提案禁止**: カタログ外の連携が要るときは別 phase で skill 拡張を提起する (本 skill で勝手に拡張しない)。

## ゴールシーク実行

**Goal**: purpose.json から導出した verb_object に対し、tier=required 連携が全て確定し reason 付きで rejected も埋まった `options.json` を生成する。

**Why**: Phase 6 で連携選択が漏れると後続 phase (実装計画・タスク仕様化) が空中分解し、orchestrator (`run-skill-intake`) 以降が options.json を消費できなくなるため。tier=required を必ず明示・確定させることで、後段の責務分離 (実装 skill / 評価 skill) が崩れない。

**Checklist** (上から順にチェックし、未充足があればその項目に戻る反復構造):

- [ ] `purpose.json` の `true_purpose.verb_object` と `time_freed_intent` を抽出済み
- [ ] `references/integration-catalog-pointer.md` 経由で plugin 共有 `references/integration-catalog.md` を読み、verb_object に親和する候補を列挙済み
- [ ] 各候補に `tier`, `id`, `name` を付与し、tier=required の候補が漏れなく含まれているか確認済み
- [ ] AskUserQuestion で候補をユーザー提示し、selected / rejected の判断を取得済み
- [ ] rejected 全項目に空でない `reason` が記録済み (tier=required を除外する場合も理由必須)
- [ ] `output/<hint>/options.json` を `{ "selected_integrations": [...], "rejected": [...] }` 形式で書き出し済み
- [ ] 出力が purpose.json の verb_object と整合し、新規連携 (カタログ外) を提案していないことを自己確認済み

期待出力例:

```json
{
  "selected_integrations": [{"id": "notion-publish", "name": "Notion 公開", "tier": "required"}],
  "rejected": [{"id": "slack-notify", "reason": "通知不要"}]
}
```

## Gotchas

1. **tier=required も除外可、ただし reason 必須**: 必須連携は提示するが、ユーザーが明示的に除外する場合は理由を残し下流 skill に判断材料を渡す。
2. **カタログ外候補の誘惑**: verb_object に近い連携がカタログに無い場合でも本 skill では補完せず、別 phase (skill 拡張要求) として上げる。
3. **pointer 経由の参照**: `integration-catalog.md` は plugin 共有 `references/` にあるため必ず `integration-catalog-pointer.md` を経由し、直接ハードコード参照しない。
4. **責務の最小化**: カタログ参照と `options.json` 生成のみを担い、連携の実行・認証・公開は他 phase に委譲する (write は `options.json` に限定)。

## Additional Resources

- `references/integration-catalog-pointer.md` — plugin 共有 references/integration-catalog.md への参照ガイド
- `references/tier-criteria.md` — required / optional の判定基準
