# 19. Troubleshooting

## Skill が発動しない

確認:

1. `SKILL.md` が skill directory 直下にある。
2. directory が discovery 対象にある。
3. session 開始後に top-level skills directory を新規作成したなら再起動した。
4. `description` の key use case が user prompt と一致している。
5. `disable-model-invocation: true` を付けていない。
6. `paths` が対象 file と一致している。
7. `skillOverrides` で `"off"` や `"user-invocable-only"` にしていない。

## Skill が誤発動する / 取りこぼす

**重要な根本原因**: `description` に動作説明（採点する／JSON で返す／2 段階レビュー 等）が混じると、Claude は本文を読まず description の短縮版だけで動作する。結果として (a) 動作詳細の中の語句が user 発話と部分一致して誤発動が増え、同時に (b) 本文に書いた多段処理や禁則が読まれず取りこぼしが起きる、という矛盾した症状が同時発生する。外部事例では、description に動作詳細を書いた Skill が本文の多段処理を一部しか実行せず、`Use when ...` 形式の発動条件だけに直したところ本文を読むようになった。description は「いつ呼ぶか」だけに絞り、動作詳細は本文へ移すこと。

Sample expansion: obra/superpowers writing-skills の事例では、description の `code review between tasks` を `Use when executing implementation plans with independent tasks` に直している（原典 L496-500）。

修正:

- `description` を狭める / 動作説明を本文へ移す。
- 発動条件を 2〜3 個に揃える（1 個＝鍵不足、4 個以上＝重複・処理混入）。
- `when_to_use` に境界条件を書く。
- `paths` で対象 file を制限する。
- 近い Skill と prefix / purpose を分ける。
- `skillOverrides: "name-only"` で description を隠す。

## description が切れる

原因:

- `description` + `when_to_use` は 1,536 文字 cap。

対策:

- key use case を先頭に置く。
- trigger phrase を 2 個前後に絞る。
- 手順・出力形式・例は本文へ移す。

## 危険操作が止まらない

原因:

- `allowed-tools` を deny と誤解している。
- permissions deny がない。
- Hook が exit 1 で終了していて block していない。

対策:

- `permissions.deny` を追加する。
- `PreToolUse` hook で command を検査し、block は exit 2 または structured decision にする。
- dangerous workflow は `disable-model-invocation: true` にする。

## 評価が甘い

原因:

- generator と evaluator が同じ context。
- evaluator が generator の意図を知っている。
- score だけで findings がない。

対策:

- `context: fork` evaluator を作る。
- artifact / file 経由で渡す。
- evaluator に rubric を編集させない。
- JSON output に `score`, `passed`, `findings`, `required_fixes` を入れる。

## Agent Team がうまく動かない

確認:

- `CLAUDE_CODE_EXPERIMENTAL_AGENT_TEAMS=1` が有効。
- task が Agent Team に値する複雑さを持つ。
- teammates に十分な context を spawn prompt で渡した。
- same-file edits が起きないよう ownership を分けた。
- lead が teammate 完了前に終了していない。

## Factory 型ワークフロー障害テンプレート

Skill factory / generator / evaluator などの量産フローを回す際に起きる障害を、特定プロジェクト名ではなく変数で扱う。汎用 Skill 障害ではなく **factory レイヤ** の障害として分離して列挙する。

### Factory 変数辞書

| 変数 | 意味 | sample expansion |
|---|---|---|
| `{{factory_skill_name}}` | factory 全体を代表する Skill | `harness-creator` |
| `{{create_skill}}` | 作成・更新を担う Skill | `run-skill-create` |
| `{{build_skill}}` | build を担う Skill | `run-build-skill` |
| `{{elicit_skill}}` | brief / 要件収集を担う Skill | `run-skill-elicit` |
| `{{handoff_file}}` | handoff JSON | `eval-log/handoff-<step>.json` |
| `{{handoff_schema_path}}` | handoff schema の正本 | `plugins/harness-creator/skills/run-skill-create/schemas/handoff.schema.json` |
| `{{trace_file}}` | build trace | `eval-log/skill-build-trace.json` |
| `{{evaluator_skill}}` | 評価を担う Skill | `assign-skill-design-evaluator` |
| `{{context_log_path}}` | context mode を記録する証跡 | `eval-log/docs/<NN>-*.json` |
| `{{fast_mode_resolver}}` | fast mode 判定 script | `scripts/resolve-fast-mode.py` |
| `{{frontmatter_validator}}` | frontmatter 検証 script | `validate-frontmatter.py` |
| `{{dependency_linter}}` | 依存方向 lint script | `lint-dependency-direction.py` |
| `{{category_resolver}}` | brief から category への写像 script | `scripts/resolve-brief-to-category.py` |
| `{{trace_validator}}` | trace 検証 script | `validate-build-trace.py` |
| `{{runtime_skills_dir}}` | runtime 側 Skill directory | `.claude/skills/` |
| `{{source_skills_dir}}` | source / canonical 側 Skill directory | `creator-kit/skills/` |
| `{{migration_phase}}` | 移行フェーズ名 | `Phase 0` |

Sample expansion: `{{factory_skill_name}}=harness-creator`, `{{create_skill}}=run-skill-create`, `{{build_skill}}=run-build-skill`, `{{elicit_skill}}=run-skill-elicit`。

### 1. P0 lint 3 周ループ上限到達 (`governance_decision: loop_exceeded`)

症状:

- Step 4a の lint 失敗 → Step 2 build 戻り → 再 lint 失敗 が 3 周連続で発生する。
- 同一 finding が繰り返し出続け、LLM 判断による自動修正で収束しない。

根本原因:

- パラダイム前提（`kind` 選択、命名、配置先など設計判断層）の誤りを、構文層の lint で修正しようとしている。
- brief の `kind` / `prefix` / `hierarchy_level` の整合が初期から崩れている。

対策:

- 3 周到達時は `handoff-after_lint.json` の `state.required_fixes` を `TODO(human)` として提示する。
- `resume_command` を明示し、`Skill({{create_skill}}, args=[<topic>, --mode=update, --resume-from=lint])` で再開可能にする。
- 設計前提誤りの可能性を Step 5 (elegant-review) に上申してから停止する。

### 2. handoff JSON 破損による resume 失敗

症状:

- PostCompact 後に `Skill({{create_skill}}, args=[--resume-from=<step>])` を実行すると `{{handoff_file}}` が読めず復元できない。
- `schemas/handoff.schema.json` の必須フィールド (`step`, `gate_id`, `approver`, `artifacts`, `next_phase`) のいずれかが欠落している。

根本原因:

- handoff 保存中に bash kill されたか、`{{runtime_skills_dir}}` と `{{source_skills_dir}}` の二重配置で schema パスがずれた。
- handoff schema の正本が両方の skill ディレクトリに存在し、validator が古い方 (references/handoff-schema.json は redirect stub) を読んだ。

対策:

- 正本は `{{handoff_schema_path}}` 1 箇所に統一し、`{{runtime_skills_dir}}` 側は symlink にする。
- `validate-handoff.py` を resume 前に実行し、schema 違反なら強制的に Gate 1 (brief 確認) からやり直す。
- handoff 書き出しを atomic にする (`*.tmp` に書いて `mv`)。

### 3. `--fast` モード誤判定 (条件不一致で fast を黙って解除する仕様の罠)

症状:

- `--fast` を付けて起動したのに Step 4b/5 まで走った。
- 逆に大規模変更なのに Step 5 が skip された。

根本原因:

- fast 条件 (1 ファイル変更 / `<=30` 行 / `kind ∈ {ref, wrap}` / evaluator pair 不要) のいずれかが満たされていないが、ユーザーには警告されない（黙って解除する仕様）。
- 判定が Step 4a と Step 5 の 2 箇所で行われ、間に Step 2 戻りが入ると条件評価がずれる。

対策:

- fast 判定を `{{fast_mode_resolver}}` に集約し、Step 4a / Step 5 の両方が同一スクリプト出力を参照する。
- 判定結果を `{{trace_file}}` の `fast_mode_resolution` フィールドに記録し、`{requested, resolved, reason}` の 3 値で後追い可能にする。
- 解除時は黙らず ユーザーに 1 行で通知する (`fast mode requested but resolved=false: <reason>`)。

### 4. `context: fork` evaluator 起動失敗 (同 context 評価による偽陽性)

症状:

- `{{evaluator_skill}}` が PASS と返したのに、人間レビューでは明白な誤りが残っている。
- evaluator 出力が generator の主張をそのまま追認している (sycophancy)。

根本原因:

- `context: fork` 指定漏れで、generator と同 context で evaluator が動いた。
- `skills:` で evaluator skill を preload している場合、`disable-model-invocation: true` の evaluator は preload 不可（17 章参照）。

対策:

- evaluator の SKILL.md frontmatter に `context: fork` が必ずあることを `{{frontmatter_validator}}` で強制する。
- evaluator skill には `disable-model-invocation: true` を入れず、parent skill から明示 `Skill(...)` 呼び出しで起動する。
- `{{context_log_path}}` に `context_mode: fork|inline` を記録し、`fork` 以外はガバナンスで否認する。

### 5. `{{runtime_skills_dir}}` と `{{source_skills_dir}}` 二重配置のパス不一致

症状:

- lint が一方では PASS、もう一方では FAIL になる。
- handoff / schema 参照先が build 時と resume 時で食い違う。

根本原因:

- `{{migration_phase}}` 移行中の二重配置で、`SKILLS_DIR` 環境変数が指す先が不明瞭。
- schema / template / hook の正本が `{{source_skills_dir}}` 側にあると規約で決めているが、`{{runtime_skills_dir}}` 側に古い派生が残っている。

対策:

- `SKILLS_DIR="${CLAUDE_SKILLS_DIR:-{{source_skills_dir}}}"` を厳守し、`{{runtime_skills_dir}}` を symlink 化する。
- `{{dependency_linter}}` に「`{{runtime_skills_dir}}` 内ファイルが `{{source_skills_dir}}` を参照することは可、逆は不可」のルールを追加する。
- 移行完了後は `{{runtime_skills_dir}}` を `{{migration_phase}}` 終了の commit で symlink 一括化する。

### 6. resource-map.yaml の category 未網羅による設計書参照漏れ

症状:

- `{{build_skill}}` が 17 章 (Agent Teams) や 19 章 (Troubleshooting) を読まずに設計判断する。
- `{{trace_file}}` の `context_map_decision` は埋まっているが、生成スキルが Agent Team / hook 連携を欠く。

根本原因:

- `resource-map.yaml` に `agent-teams` / `troubleshooting` カテゴリのエントリがない。
- task category の判定が LLM 主観で、brief の field 値からの決定論的写像が定義されていない。

対策:

- `resource-map.yaml` に `agent-teams` (keywords: `agent-team`, `teammate`, `task-list`, `subagent`, `with-subagent`) と `troubleshooting` (keywords: `error`, `failure`, `loop`, `fast-mode`, `handoff`) のカテゴリを追加する。
- brief → category の決定論的写像を `{{category_resolver}}` に外部化する (kind / prefix / hierarchy_level → category 配列)。
- `{{trace_validator}}` で `context_map_decision.category` が resource-map.yaml に列挙された category のいずれかに一致することを assert する。
