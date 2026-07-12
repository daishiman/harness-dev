# 13. チェックリスト

## 実装主体タグの凡例

本チェックリストの各項目に「誰が確認するか」を付与する。検証エンジン（23 自己進化ループ）はこの分類を起点に自動化を進める。機械検証や eval-log へ接続する項目は、実装時に stable ID を付けて参照を固定する。

| タグ | 意味 | 実装例 |
|---|---|---|
| `[Lint]` | 機械的に検出可能。`scripts/lint-*.{sh,py,ps1}` で実装 | name 形式、frontmatter スキーマ、ファイル名 |
| `[Hook]` | Claude Code の lifecycle hook で守る。PreToolUse / PostToolUse / PreCompact | permissions、危険操作、compaction 前 handoff |
| `[人]` | 人間レビューが必須。lint/hook で代替不能 | 表現品質、業務妥当性、命名のセマンティクス |
| `[人+Lint]` | 機械検出が一次、人間判断が最終 | description の冗長性、命令の理由付け |

タグは「誰が最終責任を持つか」を示す。`[Lint]` は検出、`[Hook]` は阻止、`[人]` は裁定、`[人+Lint]` は検出後の裁定を意味する。

## 作成前

- [ ] `[Lint]` 元情報パスが実在する
- [ ] `[人]` 元記事・画像・公式 docs の取得日を記録した
- [ ] `[人]` 公式 docs の `llms.txt` または What's New で更新差分を確認した
- [ ] `[人]` Skill ではなく Hook / CI / CLI / MCP / API で解くべき項目を除外した

## 新規 Skill 設計

- [ ] `[人]` 何の問題を解く Skill か 1 文で言える
- [ ] `[人]` 決定論で解くべき処理を Skill に入れていない
- [ ] `[人]` 副作用の有無を判定した
- [ ] `[人]` 辞書型 / ワークフロー型を決めた
- [ ] `[人+Lint]` Purpose（目的） / Trigger（発動条件） / Shape（成果物の形） / Role（役割）を埋めた
- [ ] `[Lint]` prefix が決定木と一致している（第1〜2条）
- [ ] `[人+Lint]` `description` が発動条件になっている
- [ ] `[人]` output contract（契約） がある
- [ ] `[人+Lint]` 補助ファイルの案内がある
- [ ] `[Lint]` 危険な副作用に `disable-model-invocation: true` がある

## Frontmatter（先頭メタ情報）

- [ ] `[Lint]` `name` は lower-case / hyphen 形式（第3条）
- [ ] `[Lint]` `description` + `when_to_use` の合算が 1,536 文字 cap を意識して短い
- [ ] `[人+Lint]` **description の発動条件が 2〜3 個** (1 個は不足、4 個以上は冗長・重複)
- [ ] `[人]` **description が動詞 / 手順ベースで「いつ呼ぶか」を記述している** (名詞羅列ではない)
- [ ] `[人]` **description に本文の動作詳細（採点する／JSON で返す／段数・出力形式）が混入していない**
- [ ] `[人+Lint]` `when_to_use` は冗長でない
- [ ] `[人]` `argument-hint` と `arguments` は必要時だけ使う
- [ ] `[人]` `allowed-tools` を deny と誤解していない
- [ ] `[Lint]` `context: fork` には explicit task がある
- [ ] `[Lint]` `user-invocable: false` と `disable-model-invocation: true` の併用事故がない（第4条）
- [ ] `[Lint]` `base:` / `pair:` / `kind:` など独自 metadata が lint 可能
- [ ] `[人]` `ref-*` を到達不能設定にしていない。Read 経由専用ならその旨を明記した

## 本文

- [ ] `[Lint]` **SKILL.md 本文 300 行以下** (HumanLayer "Writing a good CLAUDE.md" 由来の hard cap、08 参照)
- [ ] `[人]` 設計書 Markdown と生成対象 `SKILL.md` の行数規律を混同していない（設計書は300行超過可）
- [ ] `[人]` 先頭 30 行で目的・出力・禁則が分かる
- [ ] `[人]` 一般知識の写経がない
- [ ] `[人]` プロジェクト固有情報に寄っている
- [ ] `[人]` 強い命令には理由がある
- [ ] `[人]` Gotchas（落とし穴）は短く検証可能
- [ ] `[Lint]` 長い表や例は補助ファイルに分離 (300 行超過分は `references/` `examples/` へ)

## 評価

- [ ] `[人]` ワークフロー型に evaluator が必要か判断した
- [ ] `[Lint]` generator / evaluator が同一 context でない (`context: fork` 検証)
- [ ] `[人]` evaluator は artifact だけを評価する
- [ ] `[Hook]` evaluator は rubric を編集できない (PreToolUse で `references/rubric.*` への Write を deny)
- [ ] `[Lint]` evaluator は `rubric_refs` を持ち、本文に評価軸をハードコードしていない
- [ ] `[Lint]` `rubric_refs` / `reference_refs` / `script_refs` の参照先が存在し、循環していない
- [ ] `[Lint]` `script_refs` の script 名が 28 章の `<verb>-<target>-<scope>.py` 形式に従っている
- [ ] `[Hook]` evaluator は `rubric_refs` / `reference_refs` を実行中に書き換えない
- [ ] `[Lint]` JSON output がある
- [ ] `[Lint]` threshold と retry 条件が明確

## 依存方向

- [ ] `[Lint]` `run-*` / `assign-*` から `ref-*` / `references/` / `scripts/` への一方向依存になっている
- [ ] `[Lint]` `ref-*` / `references/` が `run-*` / `assign-*` を呼び出していない
- [ ] `[Lint]` scripts が Skill 本文や Skill 名をハードコードしていない
- [ ] `[Lint]` L0 company → L1 domain/project → L2 task の順序で reference / rubric が列挙されている
- [ ] `[人]` domain 固有性は evaluator ではなく rubric/reference に分離されている

## 運用

- [ ] `[人]` 同じ失敗が Gotcha に留まっていない
- [ ] `[人+Lint]` lint / Hook / CI へ昇格すべき規則を抽出した
- [ ] `[Hook]` permissions deny が必要な操作を確認した
- [ ] `[Hook]` Hook で守るべき lifecycle event を確認した
- [ ] `[人]` compaction 後に重要ルールが残る
- [ ] `[Hook]` handoff / context reset で再開できる（PreCompact hook 検証）

## Permissions / Hooks

- [ ] `[Lint]` Bash wildcard rules が広すぎない
- [ ] `[Lint]` compound command を単純 wildcard だけで許可していない
- [ ] `[人]` `disableAutoMode` / `disableBypassPermissionsMode` が必要な環境か判断した
- [ ] `[Lint]` PreToolUse は `hookSpecificOutput.permissionDecision` を使っている
- [ ] `[Lint]` policy enforcement hook は exit code 2 または structured JSON decision を使っている
- [ ] `[Lint]` HTTP hook で block する場合は 2xx + JSON decision を返す

## クロスプラットフォーム (Mac / Windows 両対応)

- [ ] `[人]` Skill が Mac でも Windows でも同一の入出力契約で動く
- [ ] `[Lint]` 追加ライブラリ導入ゼロ (`pip install` / `npm i` / `brew install` を要求していない)
- [ ] `[Lint]` Python を使う場合、import は標準ライブラリのみ
- [ ] `[Lint]` 呼び出す CLI は OS 標準同梱ホワイトリスト (22 章) の範囲内
- [ ] `[Lint]` OS プリアンブル ``!`uname -s 2>/dev/null || ver` `` を本文先頭付近に置いた
- [ ] `[Lint]` `<important if="os=mac">` / `<important if="os=windows">` の分岐がある
- [ ] `[人]` OS 未判定時にユーザーへ問い合わせるフォールバック文面がある
- [ ] `[Lint]` パス区切りを `/` / `\` で hardcode せず `pathlib` / `Join-Path` を使っている
- [ ] `[Hook]` OS 情報を長期記憶・設定ファイルへ書き込んでいない (PC 切替リスク)

## Agent Teams

- [ ] `[人]` Agent Team が本当に必要で、Subagent で足りない理由がある
- [ ] `[人]` 3〜5 teammates から始める計画になっている
- [ ] `[Lint]` 5〜6 tasks / teammate を超えていない
- [ ] `[人]` same-file edit が起きないよう file ownership を分けた
- [ ] `[Lint]` task dependencies が定義されている
- [ ] `[人]` nested teams を前提にしていない
- [ ] `[人]` lead が cleanup する手順がある

## 命名規約条文（第1〜16条）の遵守

06 の法律的命名規則に対応するチェック項目。

- [ ] `[Lint]` 第1条: prefix が 5 種のいずれかで始まる
- [ ] `[Lint]` 第2条: domain segment が 1〜3 個ある（segment 数 2〜5）
- [ ] `[Lint]` 第3条: kebab-case のみ
- [ ] `[Lint]` 第4条: `user-invocable: true` の Skill が `run-*`/`wrap-*`/`delegate-*` で始まる
- [ ] `[Lint]` 第5条: `assign-*` の末尾が role-suffix（`-evaluator` 等）
- [ ] `[Hook]` 第6条: 改名時に CHANGELOG.md 更新と alias 設置（PR 検証）
- [ ] `[Lint]` 第7条: prefix + 第1 domain segment の組で重複なし
- [ ] `[Lint]` 第8条: ディレクトリ名が予約語彙集合内
- [ ] `[Lint]` 第9条: ファイル名が kebab-case（許可された大文字慣習を除く）
- [ ] `[Lint]` 第10条: scripts/ 配下が動詞先頭
- [ ] `[Lint]` 第11条: references/ 配下が名詞先頭
- [ ] `[Lint]` 第12条: examples/ 配下が case-id 形式
- [ ] `[Lint]` 第13条: references/ が 3 ファイル以上なら resource-map.yaml が存在
- [ ] `[人]` 第14条: `_drafts/` 配下は実験用と判断した
- [ ] `[人]` 第15条: 改正時の影響評価と猶予期間が PR に記載されている
- [ ] `[人+Lint]` 第16条: 例外宣言 `name-policy-exception` が明示されている

## 検証エンジン実装の優先順位

P0 は 4条件を機械判定へ近づける最小ゲートである。P0 が未実装の場合、4条件は「設計上PASS」または「暫定PASS」と表記し、「機械検証PASS」と呼ばない。P1/P2 は運用強化ゲートとして段階的に追加する。

- [ ] **P0**: `scripts/lint-skill-name.{sh,py}` が第1〜5,7条を検出する
- [ ] **P0**: `scripts/lint-skill-tree.{sh,py}` が第8〜13条を検出する
- [ ] **P0**: `creator-kit/scripts/lint-skill-tree.py` の `check_os_preamble` が、`cross_platform: true` または `os_preamble_required: true` の Skill に ``!`uname -s 2>/dev/null || ver` `` があることを検出する
- [ ] **P0/P1**: `scripts/validate-build-trace.py` が `eval-log/skill-build-trace.json` の `doc_coverage.ch14_dynamic_injection` / `ch15_official_spec_checked` / `ch16_frontmatter_spec` を検出する
- [ ] **P1**: PreToolUse hook が evaluator から rubric.* への Write を deny する
- [ ] **P1**: PreCompact hook が handoff file を生成する
- [ ] **P1**: `lint-skill-description.py R6` が `assign-*` evaluator の `rubric_refs` 欠落を検出する
- [ ] **P1**: `creator-kit/scripts/lint-manifest-contents.py` が `yaml-spec-cache.md` の `last_fetched` 30 日超過を WARNING にする
- [ ] **P2**: CI workflow が改名・改正手続き（第6・15条）を検証する
- [ ] **P2**: `poll-llms-txt.yml` が `https://code.claude.com/docs/llms.txt` 目次の週次チャーンを `eval-log/spec-drift.json` に記録する（record-only・Issue は起票しない）
- [ ] **P2**: `update-yaml-spec.yml` が実仕様ページ群（skills / settings / sub-agents / hooks / permissions / agent-teams / commands / plugins など）と製品 CHANGELOG の変更を検知し `references/spec-diff-history.md` へ差分記録して dedup 付き spec-drift Issue を起票する（監視対象の正本は `scripts/build-yaml-spec-cache.py` の `SOURCES`）
- [ ] **P2**: 自己進化ループ（23 章）が rubric 違反率を集計する

---

## ⑥ 網羅性確認パターン（A2/C2 パッチ）

新規 Skill を作成・更新するたびに以下の網羅性チェックを実施する。

- [ ] `[人+Lint]` **スキル一覧の網羅性**: `lint-skill-tree.py` で全スキルが SKILL.md を持つことを確認
- [ ] `[Lint]` **責務マトリクス更新**: 23章の責務マトリクスに新スキルを追加した
- [ ] `[人]` **既存スキルとの重複チェック**: 同じ責務を持つスキルが既に存在しないか確認
- [ ] `[人]` **DAGサイクル検査**: `lint-dependency-direction.py` でサイクルなし・方向違反なしを確認
- [ ] `[人]` **ref-yaml-spec-fetcher との整合**: 新スキルの frontmatter フィールドが最新仕様と一致するか確認

## ⑩ 更新フロー実装パターン（A2/C2 パッチ）

既存スキルを更新（--mode update）する際のチェックリスト。

- [ ] `[人]` **update か create か**: 既存スキルへの増分改修は `run-build-skill --mode update`。新規なら `--mode create`。
- [ ] `[人]` **バックアップ確認**: `SKILL.md.bak` が作成されていることを確認（Step 2 の自動バックアップ）
- [ ] `[Lint]` **差分適用のみ**: `--mode update` では Write で全書き換えしない。Edit で差分適用。
- [ ] `[人]` **aliases 更新**: 破壊的変更（frontmatter.name 変更）がある場合は `run-skill-rename` を使う
- [ ] `[人]` **CHANGELOG 更新**: 重要な変更は `references/CHANGELOG.md` に記録する
- [ ] `[Lint]` **lint 再検証**: 更新後に Step 4 の lint を必ず再実行する
- [ ] `[人]` **評価再実行**: score 変動の可能性がある更新は `assign-skill-design-evaluator` を再実行する

## 運用強化ゲート（P1/P2 追加）

- [ ] **[Hook] P1**: `PostToolUse` — `rubric.json` 更新検知時に `re-evaluate-on-rubric-bump.py` が自動再評価を起動。違反率 30% 超でアラート出力。

## prefix 駆動型内部構造ゲート（23a 連動）

- [ ] `workflow-manifest.json` が存在し phases[] が宣言されているか (`run-*`)
- [ ] `schemas/` の各 .json に `$schema` / `$id` / `title` / `required` / `additionalProperties:false` があるか
- [ ] `prompts/<R-id>.yaml` が `responsibility_refs` と一対一対応しているか
- [ ] `rubric.json` が `references/rubric.json` 配下にあるか (`ref-*`, `assign-*`)
- [ ] `EVALS.json` / `changelog/` / `lessons-learned/` の蓄積基盤があるか (plugin 直下)
- [ ] SKILL.md 行数が prefix 別目標以下か (run≤180 / ref≤120 / assign≤150 / delegate≤120 / wrap≤100)

