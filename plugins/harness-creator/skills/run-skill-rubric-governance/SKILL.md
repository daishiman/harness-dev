---
name: run-skill-rubric-governance
description: rubric変更を提案するとき、rubric改正を施行するときに使う。
disable-model-invocation: false
user-invocable: true
allowed-tools: [Read, Write, Edit, Bash(python3 *), Bash(git *)]
kind: run
prefix: run
goal_seek:
  engine: inline
  fork: inline
owner: team-platform
since: 2026-05-17
version: 0.1.0
effect: local-artifact
reference_refs:
  - ref-domain-rubric-template
# auto-backfilled by backfill-source-tier.py (doc/21)
source: doc/ClaudeCodeスキルの設計書/
source-tier: internal
last-audited: 2026-05-19
audit-trigger: quarterly
responsibility_refs:
  - prompts/R1-govern.md
schema_refs:
  - schemas/output.schema.json
manifest: workflow-manifest.json
feedback_contract: # per-skill 評価基準(SSOT=scripts/feedback_contract_ssot.py)
  activation_state: semantic_evaluator_started
  max_iterations: 3
  criteria:
    - id: IN1
      loop_scope: inner
      text: rubric.json 改正後に compute-rubric-hash.py で rubric_hash を再計算し check-rubric-sync.py が exit 0(RUBRIC_DRIFT なし)で assign 側派生と版ずれゼロを確認している
      verify_by: script
    - id: IN2
      loop_scope: inner
      text: 提案の向き(add は厳格化 remove は緩和 modify は change.direction で宣言)を入れて diff-rubric-impact.py を流し 厳格化は合否変動率に関わらず required_bump を major とし 合否変動率が 30% 超なら猶予と board 招集の根拠に記録し 緩和は would_flip 0 で required_bump を提案の bump と minor の大きい方とし semver 規約(major厳格化 minor緩和 patch文言のみ)に整合した rubric_version へ更新している
      verify_by: lint
    - id: OUT1
      loop_scope: outer
      text: 提案者と承認者が同一でなく第三者レビュア tooling役を含む4ロール承認ボードが独立に発効を承認し proposer 非イコール approver を満たしている
      verify_by: evaluator
    - id: OUT2
      loop_scope: outer
      text: 猶予期間(major14日 minor7日 patch即時。would_flip 0 で承認者が緩和の根拠を確かめた minor は理由を残して0日)と旧ルール warning ダウングレードを governance log へ記録し発効後 git commit で log を closed に更新した到達状態が adequate である
      verify_by: elegant-review
artifact_delivery:
  contract: artifact-delivery-v1
  state_machine:
    initial: artifact_created
    states: [artifact_created, minimal_guard_passed, artifact_presented, user_choice_recorded, semantic_evaluator_started, handoff_complete]
    transitions:
      - {from: artifact_created, event: minimum_guard_pass, to: minimal_guard_passed}
      - {from: minimal_guard_passed, event: present_actual_artifact, to: artifact_presented}
      - {from: artifact_presented, event: record_user_choice, to: user_choice_recorded}
      - {from: user_choice_recorded, event: accept-as-is, to: handoff_complete}
      - {from: user_choice_recorded, event: "light|standard|detailed", to: semantic_evaluator_started}
      - {from: semantic_evaluator_started, event: improvement_complete, to: handoff_complete}
    pre_choice_forbidden: [semantic-evaluator, task-fork, subagent, multi-worker, revise-loop]
    accept_contexts: {evaluator: 0, improver: 0}
  release: explicit-only
  exhaustive: explicit-only
---

## Pre-choice usable artifact execution

Purpose & Output Contractの最小の実成果物をmain contextで作成する。effect別のparse/open・secret・irreversible・corrupt guardだけを実行し、現物path・digest・開き方を提示してからaccept-as-is/light/standard/detailedを記録する。accept-as-isはその場でhandoff完了とし、後続sectionを実行しない。

## Post-choice selected improvement execution

以下の既存workflow・goal-seek・評価・修正sectionはlight/standard/detailedが記録されて`semantic_evaluator_started`へ遷移した場合だけ実行する。release/exhaustiveは別の明示eventを必要とする。


# run-skill-rubric-governance

## Purpose & Output Contract

`ref-skill-design-rubric/references/rubric.json` の改正 Runbook（27章）。
提案 → 影響評価 → 猶予期間 → 発効 の4フェーズを1本のワークフローで管理。

**入力**: `templates/proposal.json` を埋めた改正提案ファイル
**出力**: rubric.json のPR、 governance log（`$SKILL_DIR/log/*.jsonl`）

## Key Rules

1. **直接編集禁止**: rubric.json は本Runbook経由でのみ更新。
2. **semver**: minor=緩和（しきい値↓、ルール削除）、major=厳格化（ルール追加、weight↑）、patch=文言のみ。
   - **緩和**とは、合格とする値の集合を広げるだけで、今まで合格したものがすべて合格のままである変更をいう。そうでない変更は厳格化として扱う。文言だけの patch は判定を変えないので、緩和にも厳格化にも数えない。`diff-rubric-impact.py` は文言だけかを見分けず緩和の `required_bump` を最低 minor とするので、文言だけであることは承認者が rubric.json の差分で確かめる。
   - 提案は向きを宣言する。`change.type` が `add` なら厳格化、`remove` なら緩和。`modify` は `change.direction` に `relax`（緩和）か `tighten`（厳格化）を書く。
   - `diff-rubric-impact.py` は宣言を信じて見積もり、変更が緩和の定義を満たすかは確かめない。その判断の責任は提案者と承認者にある（`references/governance-board.md`）。
3. **猶予期間**: major は最低14日、minor は7日、patch は即時可。ただし緩和の minor で、`diff-rubric-impact.py` の `would_flip` が 0 であり、承認者が緩和の根拠を確かめたものは、猶予期間を 0 日にできる。その理由は governance log に残す（`references/version-rules.md`。23章「改正の段階」3 の、影響を受ける Skill が 0 なら猶予期間を置かないのと同じ考え）。
4. **影響評価必須**: `scripts/diff-rubric-impact.py` で過去 eval-log の合否変動率を測る（読むのは score ログ `eval-log/<plugin>/<date>-score.jsonl` で、governance log ではない）。
5. **承認ボード**: 提案者 / 第三者レビュア / 承認者 / tooling役 の4ロール（`references/governance-board.md`）。

## ゴールシーク実行

### ゴール (Goal)

提案された rubric 改正が「影響評価・猶予期間・rubric_hash 再計算・派生同期・版ずれ検証」を全通過し、`rubric.json` が正しい semver で発効され、governance log が closed として記録された状態。

### 目的・背景 (Why)

rubric は全 Skill 採点の SSOT であり、直接編集や手順抜けは採点基盤を破壊する。固定手順では提案種別（add/modify/remove）や bootstrap 有無に応じた分岐に脆いため、到達状態（発効＋検証通過＋log closed）をゴールとし、未達項目を都度埋める。

### 完了チェックリスト (Checklist)

- [ ] `resolve-skill-dirs.py` で SKILL_DIR が解決され `eval-log/skill-dirs.json` 出力済み
- [ ] `templates/proposal.json` が `change.type`（`modify` なら `change.direction` も）/ rule_id / bump / rationale / sunset_days を埋めた状態で存在
- [ ] 時系列違反率 (`lint-rubric-violation.py --log-dir eval-log --n 3 --threshold 0.20`) を評価し `trigger.json` 出力済み（score ログのレコード数が `--bootstrap-threshold`（既定 20）未満なら exit 3=pending を許容、bootstrap 時は `solo_operator_mode: true` を log 記録し major bump は禁止）
- [ ] ルール別違反集計 (`$SKILL_DIR/scripts/lint-rubric-violation.py --logs eval-log --rule $RULE_ID`) と差分影響評価 (`diff-rubric-impact.py --logs eval-log`) を実施済み
- [ ] bump が `diff-rubric-impact.py` の `required_bump` 以上である。厳格化の見積もり（`impact_model: worst_case_tightening`）では、`required_bump` は合否変動率に関わらず major（Key Rule 2）。合否変動率が 30% を超えたか（`exceeds_flip_rate_limit`）は bump を決めず、猶予期間と board 招集の根拠として governance log に記録する。緩和の見積もり（`relaxation_no_new_failures`）では would_flip が 0 で、`required_bump` は提案の bump と minor の大きい方（閾値や severity を変えるなら最低 minor）。下回ってよいのは文言だけの patch と緊急パッチ（`emergency: true`）だけで、承認者が rubric.json の差分で確かめる。`direction_source: assumed` は `modify` に `direction` が無く厳格化とみなした値なので、緩和の提案なら `direction` を書いて流し直す
- [ ] 猶予期間（major≥14日 / minor≥7日 / patch即時。Key Rule 3 の条件を満たす緩和の minor は 0 日）を governance log（jsonl 1行）に記録し（0 日にしたときはその理由も書く）、猶予期間を置くときは旧ルールを warning（severity→low）へダウングレード済み
- [ ] `rubric.json` 編集後 `rubric_version` を semver で bump 済み
- [ ] `compute-rubric-hash.py` で `rubric.normalized.json` と `rubric_hash` を再計算済み（27章§8.2。L0 の rubric.json に rubric_hash を書き込むので、ファイルの sha256 が変わる）
- [ ] その後で `assign-skill-design-evaluator/references/rubric.json` を deep-merge 同期し、その `rubric_hash` を L0 のファイルの sha256 にそろえ済み（先に同期すると、上の書き込みで RUBRIC_DRIFT になる）
- [ ] `check-rubric-sync.py` が exit 0（`RUBRIC_DRIFT:` でない）であることを確認済み
- [ ] 発効した版の節を `eval-log/rubric-versions.md` に27章§8.3 のひな形で追記済み（`hash: sha256:<hex>` を含む。値は `compute-rubric-hash.py` が出す正規化 JSON の hash で、ファイルの sha256 ではない。`sha256:` を付けないと巻き戻しの計画が hash を読めない）
- [ ] `git commit` 実行し governance log を closed に更新済み（rubric-versions.md への追記も同じ commit に入れる）

### ゴールシークループ

正本 `../run-build-skill/references/goal-seek-paradigm.md` の 6 ステップ（現状評価→手順生成→実行→検証→Anchor Step→反復/差し戻し）に従う。本スキル固有差分:

- 対象ファイル: `ref-skill-design-rubric/references/rubric.json`（直接編集禁止・本 Runbook 経由のみ）、`templates/proposal.json`、governance log（`$SKILL_DIR/log/*.jsonl`）
- 固定パス/閾値: 違反率閾値 0.20 / 連続 3 release、厳格化は常に major で、合否変動率 30% 超なら猶予と board 招集の根拠にする（緩和は would_flip 0）、bootstrap 最小件数 20、猶予 major14/minor7/patch0 日（would_flip 0 で承認者が緩和の根拠を確かめた minor は 0 日）
- 検証は `## 検証` 系スクリプト（`lint-rubric-violation.py` / `diff-rubric-impact.py` / `check-rubric-sync.py`）へ寄せ、決定論的に `[x]` 判定する
- 規定周回を超えても未達なら残項目を承認ボード（`references/governance-board.md` の 4 ロール）へ差し戻す

### 局面カタログ (順序は都度判断)

- 出力先解決: `python3 plugins/harness-creator/skills/run-build-skill/scripts/resolve-skill-dirs.py --skill-dir-name run-skill-rubric-governance > eval-log/skill-dirs.json`
- 提案を探す: 手書きの改正提案は `$SKILL_DIR/proposals/` に置く。SessionEnd hook（`scripts/aggregate-evals.py`）の自動ドラフト `<date>-rubric-update.md` は plugin の外の `$CLAUDE_PROJECT_DIR/.claude/state/harness-creator/proposals/` に書かれる（書けなければ `$XDG_STATE_HOME` か `~/.claude/state` の `harness-creator/proposals/`。`HARNESS_CREATOR_PROPOSALS_DIR` があればそこだけ）。`$SKILL_DIR/proposals/` には書かないが、以前の版が書いた分が残っていることがある。両方の置き場を一度に見るには `python3 "$SKILL_DIR/scripts/aggregate-evals.py" --list-proposals`（JSON。`generated: true` が自動ドラフト）。環境変数を前に付けずに呼べる。`CLAUDE_PROJECT_DIR` が無ければ cwd と git の作業ツリーの root を project とみなして読むので、見た置き場は出力の `dirs` で確かめる
- 影響評価コマンド群:
  ```bash
  python3 plugins/skill-governance-lint/scripts/lint-rubric-violation.py --log-dir eval-log --n 3 --threshold 0.20 --out eval-log/trigger.json
  python3 "$SKILL_DIR/scripts/lint-rubric-violation.py" --logs eval-log --rule "$RULE_ID"
  python3 "$SKILL_DIR/scripts/diff-rubric-impact.py" --proposal proposal.json --logs eval-log
  ```
  `--logs` には score ログのある場所を渡す。2 つの script は配下の `*-score.jsonl` を再帰で読み（plugin を絞るなら `eval-log/<plugin>`）、`$SKILL_DIR/log` の governance log は読まない。
  `diff-rubric-impact.py` は提案の向き（Key Rule 2）で見積もりの模型を選び、出力の `impact_model` に出す。厳格化（`add`、`modify` と `tighten`）は、改正した rule が全レコードで新たに発火する最悪の場合として severity の重みを score に足し、合格から不合格に変わるレコードを数える（`worst_case_tightening`）。緩和（`remove`、`modify` と `relax`）は、合格から不合格に変わるレコードが定義上 0 件なので `would_flip` は 0（`relaxation_no_new_failures`）。`modify` に `direction` が無いとき（`change.type` も `direction` も無いときも同じ）は、黙って緩和にはせず厳格化とみなして見積もり、`direction_source: assumed` と stderr の警告で知らせる。`required_bump` は、厳格化なら合否変動率に関わらず `major`（Key Rule 2）、緩和なら提案の bump と `minor` の大きい方（patch の緩和は minor に上げる）。提案の bump が `required_bump` に届かないときは stderr に警告を出す。合否変動率が `flip_rate_limit`（0.30）を超えたかは `exceeds_flip_rate_limit` に出す。`change.type` や `change.direction` の値が不正なとき、`add`・`remove` と食い違う `direction` を書いたとき、bump が無いか `major`・`minor`・`patch` 以外のときは exit 2。
- 発効: `compute-rubric-hash.py --rubric plugins/harness-creator/skills/ref-skill-design-rubric/references/rubric.json` → assign 側の派生 rubric.json を同期し `rubric_hash` を L0 のファイルの sha256 にそろえる → `check-rubric-sync.py`（exit 0 確認）→ `eval-log/rubric-versions.md` に版の節を追記 → `git commit`
- 巻き戻しの計画（違反率が悪化したときだけ。完了条件ではない）: 下の「巻き戻し」を参照

### 巻き戻し（違反率が悪化したときだけ）

1 release 後に違反率が悪化したら、`rollback-to-stable.py` で巻き戻しの計画を出す（27章§9）。この script は計画を出すだけで、書き込まない。

- **選ぶ版**: `--rubric` と同じ `rubric_id` の節で、rubric_version（現行版）より古い正式版のうち、`violation_rate_avg` が `freeze.violation_rate_ceiling` 以下で、日付が最も新しいもの。rubric-versions.md には別の rubric の版も並ぶので、`rubric_id` の行が無い節は、どの rubric の版か確かめられず候補にしない（安全側。27章§8.3 のひな形は各節に `- rubric_id: <id> / hash: ...` を書く）。プレリリース、暦に無い日付の版、同じ版の見出しが2つある版（1.3 と 1.3.0 は同じ版）も候補にしない。`--rubric` の rubric.json が無いと exit 2。
- **前提**: `--versions-md` に渡せる版の記録は、2026-10-11 時点で repo に無い。置き場所の `eval-log/rubric-versions.md`（27章§8.3）はまだ作っていない（発効の手順で版の節を追記したときに作る）ので、下のコマンドは `versions-md not found` で exit 1 になる。`ref-skill-design-rubric/references/CHANGELOG.md` は版の見出しを読めるが、`rubric_id`・`hash:`・`violation_rate_avg` の行が無く、渡しても全部の版が候補から外れて exit 1 になるので代わりにならない。候補にする版の節は、巻き戻しを考える時点で手で書く。27章§8.3 のひな形（`## <版> (YYYY-MM-DD)` と `- rubric_id: <id> / hash: sha256:<hex>`。hash は、その版を発効した commit の L0 に `compute-rubric-hash.py --dry-run` を流した値）に、`- violation_rate_avg: <0〜1>` の行を足す。ひな形にこの行は無く、計算して書く仕組みも無い（出し方は下）。skill-governance-lint の `lint-rubric-violation.py` が出すのは release ごと・rule ごとの違反率で、版ごとの値は出さない。
- **violation_rate_avg の出し方**（L0 の版ごと）:
  1. その版で採点した score ログを集める。`eval-log/*/*-score.jsonl` のうち、`rubric.rubric_hash` が「その版を発効した commit の L0 rubric.json のファイル sha256」（`python3 -c "import hashlib,subprocess,sys; print(hashlib.sha256(subprocess.run(['git','show',sys.argv[1]],capture_output=True,check=True).stdout).hexdigest())" <commit>:<L0 のパス>`）と同じ行。`rubric.rubric_version` では絞らない。これは合成後の rubric の版で、most-specific-wins により assign 側（L2）の版が出るので、L0 の版と対応しない（2026-10-11 時点の score ログでは、L0 1.3.0 で採点した 16 レコードが 1.2.0・1.3.0・1.3.1 に分かれる）。rubric-versions.md の `hash:` は正規化 JSON の hash なので、これとも照合できない。発効した commit が repo に無い版は値を出せないので、行を書かない（2026-10-11 時点、1.6.0 を commit する前に commit 済みの L0 の版は 1.3.0 と 1.5.0 だけ）。
  2. レコードごとの違反率は「findings に出た `rubric_item_id` の異なり数 ÷ そのレコードの `coverage.applicable_rules`」。分母は評価器がその kind に当てた rule の数で、L0 の rule 数ではない（kind=skill では 24。L0 の 41 rule のうち 21 は skill に当たらず、assign 側の 4 rule が加わる）。`coverage` の無いレコードは数えず、外した件数を節に注記する（`composition_hash` は rubric の絶対パスも hash に含むので、置き場所が違うと同じ rubric でも値が変わり、合成を再現して分母を出すことはできない）。
  3. `violation_rate_avg` はレコードの違反率の平均。全レコードの `coverage.applicable_rules` が等しいときだけ、rule ごとの違反率の平均と同じ値になる（kind や assign 側の rubric が違うレコードが混ざると一致しない）。
  4. ceiling とは平均だけでなく最大でも比べる。rule ごとの違反率（その rule が findings に出たレコード数 ÷ レコード数）の最大が ceiling を超える版には、平均が ceiling 以下でも `violation_rate_avg` の行を書かない。`rollback-to-stable.py` は平均しか比べず、値の行が無い版は候補にしないので、この除外は値を書く段で行う。平均だけで比べると、毎回違反する rule が 1 つあっても 1/24 ≈ 0.042 で ceiling 0.05 を下回ってしまう。
  - 例: L0 1.3.0（ファイル sha256 `6e1843e5…`）の 16 レコードのうち `coverage` のある 14 レコードの平均は 0.0774（L0 の rule 数 41 で割ると 0.0453 になり、ceiling を下回ってしまう）。PD-002 はこの 14 レコードすべてに出ていて最大が 1.0 なので、どちらで見ても候補にしない。
- **まだ無いもの**: 27章§9 の表は「自動 rollback・PostToolUse」とするが、hook にはつないでいない。`freeze.consecutive_runs`（連続 run 数）による安定版の凍結判定も無い。
- **計画の後**: 承認を得てから、計画の `steps` に従う。対象の版を発効した commit の L0 rubric.json と、assign 側の派生 rubric.json（`assign-skill-design-evaluator/references/rubric.json`）を一組で戻す（版の名前だけを書き換えない。片方だけ戻すと `check-rubric-sync.py` が RUBRIC_DRIFT になる。ref-skill-design-rubric に templates/ は無い）。steps の 2 つ目は、戻した L0 に `compute-rubric-hash.py --dry-run --rubric <L0>` を流し（書き込まない）、出た hash を計画の `target_hash`（rubric-versions.md に記録した hash）と照合する。`--dry-run` を外すと L0 に rubric_hash を書き込んでファイルの sha256 が変わり、一組で戻した assign 側と合わず RUBRIC_DRIFT になる（rubric_hash を持たない版を戻したとき）。書き込んで再計算するなら、発効の手順と同じく assign 側の `rubric_hash` を L0 の新しいファイル sha256 にそろえてから `check-rubric-sync.py` を流す。

```bash
python3 plugins/skill-governance-automation/scripts/rollback-to-stable.py \
  --rubric plugins/harness-creator/skills/ref-skill-design-rubric/references/rubric.json \
  --versions-md eval-log/rubric-versions.md
```

正本の `governance-params.json` は repo root の `references/governance-params.json`（27章§11 の置き場所で、`--params` の既定。作業ディレクトリ基準）だが、まだ無い。`--params` を省くと、警告を出して既定の ceiling 0.05 を使う（`params_source: "default"`）。作るときは同じディレクトリの `references/governance-params.json.example`（freeze 10 / 0.05）を写す。repo にはほかに 2 つある。`plugins/skill-governance-config/config/governance-params.json.example` は freeze の値は同じだが、`solo_operator_mode.enabled` の既定が false で `bootstrap_mode` を持つ。`plugins/prompt-creator/skills/run-prompt-create/references/governance-params.json` は run-prompt-create の自動承認用の実ファイルで、`freeze` を持たないので ceiling の出どころにしない。

## Gotchas

- **patchで内容変更は禁則**: 文言のみ。閾値や severity 変更は最低 minor。`diff-rubric-impact.py` も緩和の `required_bump` を最低 minor にする。
- **assign 側 override をrebaseし忘れる事故**: deep-merge の most-specific-wins が壊れる（29章）。
- **score ログがない**: `--logs` の配下に score を持つレコード（`*-score.jsonl`）が 1 件も無いと、`diff-rubric-impact.py` と `$SKILL_DIR/scripts/lint-rubric-violation.py` は結果を出さずに exit 2 で止まる（`--logs "$SKILL_DIR/log"` のように governance log を渡したときも同じ）。score の無いレコードは数えず、件数を出力の `skipped_no_score` に出す。
- **緊急パッチ**: high severity の誤検出固定は patch 例外（log に `emergency: true`）。
- **時系列違反率は release を区別しないと発火しない**: `plugins/skill-governance-lint/scripts/lint-rubric-violation.py` は、`passed` を持たない finding を違反として数え、「違反したレコードの数 ÷ その release のレコードの数」を rule ごとに出す。ただし今の score ログは全レコードが `release: "local"` なので、連続 N release の条件を満たせず、breached は空のままになる。`write-eval-log.py` は入力 JSON の `release` を使い、無ければ環境変数 `RELEASE_VERSION`、それも無ければ `"local"` を入れる。版や日付で区別するには、評価 JSON に `"release": "<版>"` を入れて `python3 plugins/skill-governance-automation/scripts/write-eval-log.py --input <評価 JSON>` で記録する（環境変数を前に付ける形は先頭が python3 でなく、この Skill の allowed-tools の外なので使わない。`--list-proposals` が環境変数なしで project の state を読むのも同じ理由）。そう記録するまでは、招集の判断は score ログの findings を直接見て行う。

## Additional Resources

- `templates/proposal.json` — 改正提案テンプレ
- `plugins/skill-governance-lint/scripts/lint-rubric-violation.py` — **時系列違反率検出（連続 N×閾値超 → trigger.json）正本（27章§3.2）**
- `$SKILL_DIR/scripts/lint-rubric-violation.py` — ルール別違反集計（`--logs` 配下の score ログの findings を rule ごとに数える。release は区別しない）
- `$SKILL_DIR/scripts/diff-rubric-impact.py` — 差分影響評価
- `plugins/skill-governance-automation/scripts/compute-rubric-hash.py` — rubric_hash 再計算（27章§8.2）
- `plugins/skill-governance-automation/scripts/notify-if-governance-trigger.py` — 招集通知（27章§3.4）。どの hooks.json にも登録しておらず、手で呼ぶ。exit は 0（未知の引数だけ 2）
- `plugins/skill-governance-automation/scripts/rollback-to-stable.py` — 現行版より古く violation_rate_avg が ceiling 以下の最新の版への巻き戻し計画（書き込みはしない。27章§9）
- `plugins/skill-governance-automation/scripts/doc-to-skill-adapter.py` — 設計書を Skill artifact 化して自己採点する起動装置（26章）
- `references/governance-board.md` — ボード構成
- `references/version-rules.md` — semver規約
- 27章: `{{PROJECT_ROOT}}/doc/ClaudeCodeスキルの設計書/27-rubric-governance-runbook.md`
- 26章: `{{PROJECT_ROOT}}/doc/ClaudeCodeスキルの設計書/26-meta-skill-dogfooding.md`
- 28章: `{{PROJECT_ROOT}}/doc/ClaudeCodeスキルの設計書/28-script-execution-model.md`
- `plugins/harness-creator/skills/run-build-skill/scripts/resolve-skill-dirs.py` — SKILL_DIR 解決スクリプト
