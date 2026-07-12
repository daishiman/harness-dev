# rollback / drift 生成仕様 (phase2-04)

本書は仕様書 `doc/migration/phase2/04-rollback-and-drift-specification.md` Section 7.1〜7.5 を集約した executable spec である。Phase2-06 (実行) はここで凍結された CLI 契約・テンプレ・gate を参照する。

## 1. rollback.template.sh のテンプレート構造 (5 steps)

`eval-log/task/phase2-04/rollback.template.sh` を正本とする。実行時に gen-rollback.py が `<PLUGIN>` / `<SNAPSHOT_ID>` / `<MOVED_PATHS>` を置換し、`rollback-<plugin>.sh` を生成する。テンプレは以下 5 step を含む:

- Step 1: `.claude/skills` および `.claude/agents` のうち `plugins/<PLUGIN>/` を指す symlink を削除 (build CLI が再生成する前提)
- Step 2: `plugins/<PLUGIN>/` を `git restore --staged --worktree`。未追跡なら `rm -rf` でフォールバック
- Step 3: creator-kit/ 内の移動元 `MOVED_PATHS[]` を 1 件ずつ `git restore`
- Step 4: `eval-log/task/phase2-04/snapshots/<PLUGIN>/settings.before.json` を `.claude/settings.json` に復元 (一次パス。phase2-06 配下は後方互換のフォールバック。両者欠落時は exit 1)
- Step 5: `scripts/build-claude-symlinks.py --check` と `scripts/build-claude-settings.py --check` で per-plugin の整合確認 (Phase 全体の drift 検査は `drift-check.sh` が担当する)

placeholder はコメント内および環境変数/配列リテラル内に閉じ込められており、テンプレ単体で `bash -n` PASS する。`MOVED_PATHS_PLACEHOLDER` は gen-rollback.py が `MOVED_PATHS=(...)` 行ごと差し替える固定パターンであり、テンプレ実装と一致する。

## 2. snapshot から script への写像アルゴリズム

```
input:
  - plugin name (partition-plan.json の plugin エントリ)
  - moved files list (partition-plan.json の当該 plugin の files[].rel)
  - pre-state snapshot dir (一次): eval-log/task/phase2-04/snapshots/<plugin>/
      * settings.before.json
      * settings.before.sha256       (settings.before.json の sha256、改竄検査用)
      * git-status.before.txt        (git status -s の保存)
      * claude-symlinks.before.txt   (find .claude -type l の保存)
output:
  - rollback-<plugin>.sh (chmod +x, bash -n PASS)
algorithm:
  1. snapshot ヘッダ (plugin 名, snapshot_id=<git rev-parse HEAD>+UTC) をテンプレへ注入
  2. moved files list を Bash 配列リテラルに整形し MOVED_PATHS_PLACEHOLDER パターンを置換
     (テンプレ側の `MOVED_PATHS=("${MOVED_PATHS_PLACEHOLDER:-}")` 行を `MOVED_PATHS=(...)` に書き換える)
  3. settings.before.json への参照パスをハードコード (Step 4)
  4. .claude/ 派生 symlink 削除行 (Step 1) は plugin 名のみで一意決定
  5. build CLI --check 行 (Step 5) は固定
  6. snapshot 4 ファイルの存在および settings.before.sha256 と settings.before.json の sha256 一致を gate として検査。不整合なら exit 1
  7. 生成後 `bash -n` を gate として実行。失敗時 exit 2
```

## 3. 失敗時復旧フロー (番号付き、5 項目以上)

1. 投入対象 plugin の `rollback-<plugin>.sh` を実行し、pre-state へ巻き戻す
2. `drift-check.sh eval-log/task/phase2-06/<plugin>/post-rollback/` を実行し exit 0 を確認
3. `git status -s` が pre-state snapshot (`git-status.before.txt`) と一致することを確認
4. `find .claude -type l | sort` が `claude-symlinks.before.txt` と一致することを確認
5. settings user section の sha256 が pre-state hash と一致することを確認 (差異があれば手動調査)
6. 失敗 plugin を `migration-order.json` から除外、または原因修正してから再投入する
7. 必要なら phase2-02 `partition-plan.json` の境界を見直し、P0_breaking 手続きを起動する
8. 上記すべて緑になってから Phase2-06 を再開する

## 4. 検証ログ保存パス規約 (DoD-5)

pre-state snapshot は phase2-04 配下を一次とし、phase2-06 の plugin 投入ログは同じ snapshot を参照する (循環依存解消):

- 一次 snapshot:
  - `eval-log/task/phase2-04/snapshots/<plugin>/settings.before.json`
  - `eval-log/task/phase2-04/snapshots/<plugin>/settings.before.sha256`
  - `eval-log/task/phase2-04/snapshots/<plugin>/git-status.before.txt`
  - `eval-log/task/phase2-04/snapshots/<plugin>/claude-symlinks.before.txt`
- phase2-06 投入ログ (drift / post-rollback):
  - `eval-log/task/phase2-06/<plugin>/drift-symlink.json`
  - `eval-log/task/phase2-06/<plugin>/drift-settings.json`
  - `eval-log/task/phase2-06/<plugin>/post-rollback/*.json`

他パスへの書き出しは禁止 (本仕様で凍結)。phase2-04 fixture 検証時は `eval-log/task/phase2-04/snapshots/<sample-plugin>/` を fixture 元として明示する。

## 5. pre-state snapshot 取得手順と fixture/sandbox 検証方針 (DoD-7)

### 5.1 pre-state snapshot 取得手順

plugin 投入直前 (Phase2-06 Step 直前) に以下を実行する:

```
SNAP="eval-log/task/phase2-04/snapshots/<plugin>"
mkdir -p "$SNAP"
cp .claude/settings.json "$SNAP/settings.before.json"
git status -s > "$SNAP/git-status.before.txt"
find .claude -type l | sort > "$SNAP/claude-symlinks.before.txt"
sha256sum "$SNAP/settings.before.json" > "$SNAP/settings.before.sha256"
```

これら 4 ファイル (settings.before.json / settings.before.sha256 / git-status.before.txt / claude-symlinks.before.txt) が揃っていない、または sha256 不一致の状態で plugin 投入を行うことを禁止する (gen-rollback.py は欠落・不一致時に exit 1)。

### 5.2 fixture / sandbox 検証方針

本番リポジトリへ適用する前に、`tests/fixtures/phase2-rollback/<plugin>/` 配下に sandbox を構築し、`eval-log/task/phase2-04/snapshots/<sample-plugin>/` を fixture 元として以下を検証する:

- fixture の sandbox 上で `gen-rollback.py --plugin <name> --out /tmp/r.sh` を実行 → `bash -n /tmp/r.sh` PASS
- sandbox 上で plugin 投入を模擬 → `rollback-<plugin>.sh` 実行 → 復旧 gate (下記) を満たすことを確認
- fixture は最小 1 plugin 分 (例: skill-governance-lint) を必須とし、7 plugin 全てを optional に拡張可能

### 5.3 復旧 gate

`rollback-<plugin>.sh` 実行後、以下 3 条件すべて満たさなければ「復旧失敗」と判定する:

1. `git status -s` の出力が `git-status.before.txt` と完全一致
2. `find .claude -type l | sort` の出力が `claude-symlinks.before.txt` と完全一致
3. `.claude/settings.json` の user section (`jq '.user // .'`) の sha256 が pre-state hash と一致

この gate は Phase2-06 の `bash -n` チェックに加えて、本番投入の自動回帰として組み込む。

## 6. ツール契約参照 (凍結)

- `scripts/build-claude-symlinks.py --check --json`: 出力スキーマ `{summary:{conflict:int}, plan:[{action:str,...}]}`
- `scripts/build-claude-settings.py --check --json`: 出力スキーマ `{conflicts:[...], invariants_checked:[...]}` (length >= 12)
- スキーマ変更時は本仕様を再策定する (P0_breaking)
