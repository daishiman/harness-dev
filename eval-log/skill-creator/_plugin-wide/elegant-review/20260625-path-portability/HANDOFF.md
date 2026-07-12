# HANDOFF — skill-creator パス portability 改善（再開用）

> 日付: 2026-06-25 / run-id: 20260625-path-portability / 状態: **途中（PR #43 OPEN、未確定事項あり）**
> このセッションは**ツール出力の混線 + Write→Bash の I/O 不整合**が頻発したため、SHA や一覧の数字は**再確認前提**で読むこと。

## 0. 一行サマリ
skill-creator を marketplace install 先非依存に修正し PR #43 を出した。install 実テストで修正の有効性を実証。ただし「配布される dangling symlink の正確な全数」が未確定のまま残っている。

## 1. 背景・目的
- ユーザー要望: skill-creator は不特定多数が任意の場所に install する marketplace 配布前提。絶対パス依存を排し、配置場所に依存せず動くようにする。
- 派生1: 他プラグインにも install 先依存がないか徹底監査。
- 派生2: 実際に install して動くか検証。

## 2. 完了したこと

### A. skill-creator portability 修正（= PR #43 の中身）
elegant-review (30 思考法 / 4 条件) で検証 → 4 条件全 PASS → ユーザー承認済み。修正:
- `skills/run-plugin-package-check/scripts/validate-plugin-permissions.py`: `REPO_ROOT = parents[5]` 固定を `_resolve_repo_root()`（`$CLAUDE_PROJECT_DIR → __file__.parents[5] → cwd`、各段で `plugins/` 存在確認、`len(parents)>5` で IndexError ガード）に置換。`--plugin-dir` 追加（install で検査対象を直接指定）。
- `skills/run-plugin-package-check/scripts/aggregate-pkg-findings.py`: 同型 `_resolve_repo_root()` を **vendoring**（共通モジュール化は単独 install 時の helper dangling を招くため不採用）。
- `skills/run-plugin-package-check/SKILL.md`: 「パス解決の 2 層ポリシー」節を追加（層① install runtime=階層非依存必須 / 層② dev/CI=`parents[5]` 可だが境界明示条件）。install 用 `--plugin-dir` 例。
- `skills/run-build-skill/references/build-steps.md`: `CLAUDE_PLUGIN_ROOT` 自動設定前提と dev 専用 fallback の注記。
- `tests/skill-creator/test_runtime_resolution.py`: portability 契約テスト（過去 session の untracked を本実装で緑化。HEAD は `--plugin-dir` で unrecognized=赤）。
- 検証: install 環境シミュレーション PASS / `test_runtime_resolution.py` 4 passed / plugin_package 関連 10 passed。
- 成果物: 同ディレクトリの `findings.json`（4 条件 verdict・10 findings・思考法 coverage 30/30）, `phase1-inventory.md`, `phase2-findings.md`, `shared_state.md`。

### B. 全プラグイン横断 install 依存監査（5 プラグイン × 11 パターン）
- ハードコード絶対パス **0 件** / 設定 json・yaml の絶対パス **0 件** / `parents[N]` repo_root 導出は skill-creator のみ（本 PR で対処）。
- plugin.json hooks は全て `$CLAUDE_PLUGIN_ROOT`。層① hook（hook-guard-readonly / hook-guard-skillgen）はパス非依存。
- mf-kessai / skill-intake の本体は notion_config.py を **vendoring 実体化済み**。prompt-creator / contract-generator は Python なし。
- `.notion-config.json` は gitignore（dev 専用 per-repo 設定、配布されない）。mf-kessai の `scripts/notion_config.py` 等の symlink 残骸は **untracked（配布されない・無害）**。
- ⚠️ **symlink のカウントは信用しないこと**（下記 4 参照）。

### C. 実 install テスト（= ユーザーの「install して試せるか」への回答）
- `git archive feature/install-path-portability:plugins/skill-creator`（gitignore 除外の実配布物 2.6MB）を本物の install パス `~/.claude/plugins/cache/<mp>/skill-creator/1.1.0/` 風に展開。
- ✅ plugin.json 存在 / ✅ `hook-cache-refresh.py` を install 先で実行 exit 0（plugin-root 解決 OK）/ ✅ 修正本体 `validate-plugin-permissions.py --plugin-dir <install先>` が JSON 正常返却。
- → **install は成立し、portability 修正は install 環境で effective** と実証。
- テスト環境: `scratchpad/inst/`（再現は `scratchpad/audit2.sh` `list_syms.py` 等参照、ただし scratchpad は I/O 不整合が出やすい）。

## 3. 現在の Git 状態（SHA は混線のため要再確認）
- `feature/install-path-portability`: portability 2 コミット。**push 済み**（リモート SHA = ローカル = `e7a9c9f9` で一致確認）。**PR #43 OPEN**（`gh pr view 43` で実在確認済み。※先に報告した「PR #40」は混線の偽で実在しない）。PR 本文はインライン要約版。
- `feature/feedback-contract-propagation`: `main` + 評価基準伝播の WIP コミット（`5e21f4e` 相当、77 ファイル）。**未 push**。これは別テーマ（PR #39 系）なので portability とは分離済み。
- `main`（ローカル）: 評価基準伝播まで含む土台。
- ブランチ分けは `stash`/`reset --hard` を使わず `switch -c` + `branch -f` で非破壊実施済み。

## 4. 未解決・未確定（再開時の最優先）

### ★ 最重要: 配布される dangling symlink の正確な全数が未確定
- 監査中に「contract 系 3 本」と報告したが**過少**と判明。install テストで `run-notion-fidelity-guard`（skill-intake への symlink）など**見落とし**を発見。
- `git ls-files -s plugins | awk '$1=="120000"'` で 9 本前後出たが、混線で重複・偽名（`notion-config.json` 等）が混入し**正確な数を確定できなかった**。
- 確実に言えるのは「skill-creator/skills 配下に他プラグイン（contract-generator, skill-intake）への symlink が複数あり、git 追跡され配布物に入り、単独 install で dangling になる」こと。
- **再開アクション**: 混線の少ない環境で次を実行し正確化 →
  `git ls-files -s plugins/skill-creator | awk '$1=="120000"{print $4}' | sort -u`
  各 symlink の参照先は `git cat-file -p <blob>` で確認。dangling 対処方針（A: skill-creator から外す / B: vendoring / C: 同梱配布前提を明記）をユーザーと決める。前回 contract 系は「スコープ外」判断だったが範囲が広いと判明したので再検討。

### 残り hook の install テスト
- 確認済み: hook-cache-refresh, validate-plugin-permissions。
- 未テスト: preflight-git-commit / check-review-trigger / lint-capability-manifest / diff-rubric-impact / auto-record-lesson / hook-notify-skill-end / preload-context-map。install 先で `CLAUDE_PLUGIN_ROOT=<install先>` 設定の上 `echo '{}' | python3 <hook>` を実行し Traceback/ModuleNotFound/FileNotFound が出ないか確認。

### PR #43 本文の差し替え（任意）
- 充実版本文の素案は `scratchpad/pr-body.md`（I/O 不整合で読めない場合あり）。`gh pr edit 43 --body-file` で差し替え可。gh が不安定なら手動。

## 5. 環境問題（再開時の必須注意）
- このセッションで **ツール出力混線**（同一行の重複・偽の行/SHA/ファイル名の出現）と **Write→Bash の I/O 不整合**（書いた直後のファイルが「存在しない」になる）が頻発。
- 干渉源の一部は最初に起動した非同期エージェント `reset-observer`（shutdown 済み。直後に find/grep が安定したが完全には解消せず）。
- **対処の鉄則**: ①出力は「1 コマンド 1 事実・最小」②検証は porcelain でなく plumbing（`git diff-tree --name-only -r`, `git ls-files`, `git cat-file`, `find`）③外向き操作（push/PR）は**操作の出力を信じず結果を別コマンドで独立確認**（PR は `gh pr view <n>` が GraphQL で解決するか）④複数 `echo` のまとめを避ける。
- **再開は新しいセッションを強く推奨**（環境リフレッシュで混線が消える可能性大）。

## 6. 次アクション候補（優先順）
1. dangling symlink の完全棚卸し（§4 ★）→ 対処方針決定。
2. 残り hook の install テスト（§4）。
3. PR #43 の CI 確認（`gh pr checks 43`）→ レビュー → main へ merge。
4. PR #43 本文を充実版へ差し替え（任意）。
5. mf-kessai の untracked symlink 残骸の掃除（任意・配布に影響なし）。
6. 評価基準伝播 WIP（`feature/feedback-contract-propagation`）の扱いを別途判断（push して別 PR にするか）。

## 7. 関連ファイル
- 本ディレクトリ: `eval-log/skill-creator/_plugin-wide/elegant-review/20260625-path-portability/` … findings.json / phase1-inventory.md / phase2-findings.md / shared_state.md / pre-phase3.patch / 本 HANDOFF.md
- install テスト環境: `scratchpad/inst/`（再現用）, `scratchpad/audit2.sh`（11 パターン監査スクリプト）
- メモリ: `project_skill_creator_path_portability_2026_06_25`（2 層ポリシー）, `feedback_output_mixing_plumbing_recheck`（混線対処）
