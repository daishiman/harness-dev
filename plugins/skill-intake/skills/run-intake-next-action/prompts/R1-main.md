# Prompt: R1-deterministic-mode-decision

> このファイルは 7 層プロンプトの Markdown 表現。`run-prompt-creator-7layer` の
> seven-layer-format.md を正本とする。Layer 番号と依存方向 (L1 ← L7) は不変。

## メタ

| key | value |
|---|---|
| name | main |
| skill | run-intake-next-action |
| responsibility | R1-deterministic-mode-decision (1 prompt = 1 責務 = 1 agent) |
| layers_covered | [L1, L2, L3, L4, L5, L6, L7] |
| output_schema | schemas/output.schema.json |
| reproducible | true (mode-catalog 判定表からの導出は決定論的) |

## Layer 1: 基本定義層 (不変原則)

### 1.1 不変ルール
- mode 判定は `references/mode-catalog.md` の判定表のみから導出する (LLM 勘禁止)。
- 暫定 pattern と一致するときはユーザー確認を省略する (不一致時のみ確認)。

### 1.2 倫理ガード
- ユーザー意図を上書きしない (split_candidates は提案であり強制ではない)。

## Layer 2: ドメイン層 (本質ロジック)

### 2.1 責務 (Single Responsibility)
- 担当: Notion 公開完了を確認したうえで、summary/purpose/options/kickoff の 4 入力から引き渡しモード (A-E: harness-creator 行き / P: plugin-dev-planner 行き) と `handoff_target` を**判定し推奨として記録する**。
- 非担当 (起動禁止): skill 本体生成 (`run-skill-create` / `run-build-skill` / `capability-build`)、ヒアリング深掘り、Notion 公開。これらを Skill/Task で起動しない。mode は推奨であり実行に移さない。

### 2.2 ドメインルール
- mode は A〜E + P の 6 値のみ (A-E: `handoff_target="harness-creator"` / P: `handoff_target="plugin-dev-planner"`)。
- mode P (plugin 規模構想) は `plugin_scale: true` の明示宣言 / `component_requests[]` に非 skill コンポーネント種別 (hook/command 等) / skill 系 2 件以上、のいずれかで確定し、**D/E 判定より先に評価する** (正本: `references/mode-catalog.md`「mode P 判定条件」)。
- 単一スキルに収まらない responsibility 群が見つかれば `multi_skill_suspicion=true`、`split_candidates[]` に責務記述付きで列挙。
- 不一致確認は AskUserQuestion 1 問のみ (並列禁止)。

### 2.3 入力契約

| field | type | required | 説明 |
|---|---|---|---|
| summary | resource://intake/summary.json | yes | Gate A サマリ |
| purpose | resource://intake/purpose.json | yes | true_purpose |
| options | resource://intake/options.json | yes | 外部連携選定結果 |
| kickoff | resource://intake/kickoff.json | yes | 暫定 pattern を含む |

### 2.4 出力契約
- schema: `schemas/output.schema.json` (additionalProperties:false)
- 必須フィールド: `mode`, `reason`, `multi_skill_suspicion`, `confirmed_with_user`, `handoff_target`, `harness_creator_handoff_phase` (schema required と逐語一致。`split_candidates[]` は任意フィールド)

## Layer 3: インフラ層 (外部依存)

### 3.1 参照リソース

| id | path | when_to_read |
|---|---|---|
| mode-catalog | references/mode-catalog.md | 4 JSON を読み終えて判定表に入力するとき |
| pattern-rules | references/pattern-recognition-rules-pointer.md | kickoff の pattern と mode を突合するとき |
| handoff-contract | plugins/skill-intake/references/handoff-contract.md (plugin-root 正本) | mode P 確定時に plugin-dev-planner へ渡す § を確認するとき |

### 3.2 外部ツール / API
- `scripts/decide-mode.py` (mode 決定論判定・Notion 公開 precondition gate 内包)
- AskUserQuestion (不一致時のみ 1 問)

## Layer 4: 共通ポリシー層

### 4.1 失敗時挙動
- Notion 公開 precondition 未充足 (notion-publish-result.json 不在 / notion-log.json.status≠"published" / page_id 無し) → exit 2 (stderr に BLOCK 理由)。CI/dry-run のみ `--allow-skip` + `INTAKE_ALLOW_SKIP_PUBLISH_GATE=1` で緩和。
- 入力 JSON 不在・不正 → exit 3。
- mode 判定は該当行なしでも停止しない (decide-mode.py 実挙動): `kickoff.pattern` を既定採用し (verb_object 空→E / 連結語→D / plugin 徴候→P で上書き)、A-E/P 以外の未知 pattern は handoff 表引きの KeyError で異常終了する。「該当行なし→exit 2 / stderr 欠落条件」のフォールバックは未実装。

### 4.2 観測 / ロギング
- next-action.json に `reason` (判定表のどの行を引いたか) を必ず残す。

### 4.3 セキュリティ
- 個人名・社名はそのまま split_candidates に転記しない (variable_abstraction を保つ)。

### 4.4 最大反復回数
- チェックリスト充足ループ上限: **3 回** (判定 → 確認取得 → schema 検証の最大往復数)。上限到達で mode 未確定の場合は exit 2 で中断。

## Layer 5: エージェント層 (ゴール駆動の実行主体)

### 5.1 担当 agent
- `@next-action-advisor` (非対話バッチ、確認時のみ AskUserQuestion を 1 回起動、context-fork 不要)

### 5.2 ゴール定義
- 目的: Notion 公開完了後に、4 入力 (summary / purpose / options / kickoff) から引き渡しモード (A-E: harness-creator / P: plugin-dev-planner) と `handoff_target` を再現可能に確定する。
- 背景: mode が曖昧だと後続 harness-creator が誤起動し、責務分割や生成パスが破綻する。判定の属人化を機構で防ぐ必要がある。
- 達成ゴール: next-action.json (output.schema.json 準拠) が決定論的に確定し、判定根拠 (reason) とユーザー確認状態 (confirmed_with_user) が機械検証可能な状態。

### 5.3 完了チェックリスト (ゴール到達の停止条件)
- [ ] `notion-log.json.status=="published"` かつ `notion-publish-result.json` に page_id があることを確認した。未公開なら exit 2 で停止し、harness-creator へ進めていない
- [ ] mode が mode-catalog.md 判定表のいずれか 1 行から決定論的に導出されている (LLM 勘の介在ゼロ)
- [ ] reason に判定表の引いた行 id / 条件が文字列として含まれている
- [ ] pattern と mode が一致時は確認を省略、不一致時のみ AskUserQuestion 1 問で `confirmed_with_user` を埋めている
- [ ] `mode=D` のとき `split_candidates[]` の各要素に `name` と `responsibility` 文字列が存在する。空なら `mode=E` に格下げし `reason` に格下げ理由を追記している (mode P は `multi_skill_suspicion=true` かつ `split_candidates=[]` が正常出力 — SKILL.md Rule 4b どおり格下げしない)
- [ ] `harness_creator_handoff_phase` が decide-mode.py の handoff 表と逐語一致している — A: `Step 1 (elicit)` / B: `Step 1 (elicit --mode update)` / C: `Step 1 (elicit --mode update, prompt-only)` / D: `Step 1 (elicit, split first)` / E: `P1-kickoff (re-intake)` / P: `R1 (elicit-goal)`
- [ ] `handoff_target` が mode P で `plugin-dev-planner`、mode A-E で `harness-creator` になっている (schema allOf 条件)
- [ ] 同一 (summary, purpose, options, kickoff) 入力で next-action.json の (mode, reason) が 2 回連続実行で完全一致 (determinism)
- [ ] 個人名・社名が split_candidates に転記されていない (variable_abstraction)

### 5.4 実行方式
- 固定手順を持たない。未充足チェック項目を特定→解消手順を都度立案→実行→チェックリストで自己評価→全項目充足まで反復 (上限: Layer 4 最大反復回数)。
- 逸脱時: ループ上限到達、または Notion 公開 precondition 未充足・入力欠落の場合は Layer 4.1 の exit code 規約 (exit 2 / exit 3) に従いエスカレーション。

## Layer 6: オーケストレーション層

### 6.1 上位 skill との接続
- 呼び出し元: `run-skill-intake` (現行 orchestrator) の Notion 公開完了後 phase (Phase 11)
- 後続 phase: harness-creator 引き渡しは **mode の「推奨」を出すのみ**。本スキルも呼び出し元 (intake orchestrator) も `run-skill-create` を自動起動しない。実際のスキル生成はユーザーが別途明示的に開始する独立アクションであり、intake ワークフローはこの推奨提示で完結・停止する。

### 6.2 並列性
- AskUserQuestion は 1 問ずつ。並列起動禁止。

## Layer 7: UI / 提示層

### 7.1 ユーザー提示形式
- next-action.json (output.schema.json 準拠)

### 7.2 言語
- 本文: 日本語 (mode コード A-E/P や schema key は英語のまま)

---

## Self-Evaluation

next-action.json 生成後に以下を自己確認する。未達があれば対応 exit code を返すこと。

| 観点 | 確認内容 | 判定 |
|---|---|---|
| 公開前提確認 | notion-log.json.status=="published" かつ page_id が存在することを確認した | PASS/FAIL |
| 判定根拠 | mode が mode-catalog.md の判定表 1 行から導出され reason に行 id が含まれている | PASS/FAIL |
| 起動禁止遵守 | `run-skill-create` 等のスキル生成 skill を起動していない | PASS/FAIL |
| 変数化 | 個人名・社名が split_candidates に転記されていない | PASS/FAIL |
| schema 適合 | next-action.json が output.schema.json (additionalProperties:false) に適合 | PASS/FAIL |

---

## 出力指示 (LLM 実行時に読む箇所)

LLM はここから下の指示のみを実行し、Layer 1〜7 はコンテキストとして参照する。

`{{summary_json_path}}`, `{{purpose_json_path}}`, `{{options_json_path}}`, `{{kickoff_json_path}}` を読み、最初に `notion-log.json.status=="published"` と `notion-publish-result.json.page_id` を検証せよ。未充足なら exit 2 で停止し、harness-creator 引き渡しを確定しない。公開済みなら mode-catalog.md の判定表から mode と reason を導出せよ。pattern と mode が不一致の場合のみ AskUserQuestion を 1 問発行し、確認結果を `confirmed_with_user` に記録せよ。出力は `schemas/output.schema.json` 準拠の JSON のみとし、前置き・後書きを含めないこと。
