# Native surface operations

この runbook は `harness-creator` の capability を Claude Code と Codex の native
surface へ公開するときの運用正本である。surface の機械契約は
`native-surface-contract.md`、desired-set の唯一の owner は
`scripts/sync-native-surfaces.py` (C01) とする。

## Part 1 — 初めて使う人向け

Claude Code と Codex は、同じ道具を別々の入口から読む「2種類の道具箱」である。
Claude Code は `.claude/`、Codex は repo marketplace と plugin manifest を入口にする。
一方の置き方をもう一方へ推測コピーしてはいけない。

C01 は、repo に source が実在し project settings で enable な plugin だけを
local projection の desired-set にし、repo が所有する置き場所の不足や余分を検査・修復する。
trust は repo settings から観測できない別の runtime user gate であり、C01 が検証済みと推定しない。
普段のローカル修復は次の3段階で行う。

1. `make native-surfaces-dry-run` で変更予定を見る（無書込）。
2. managed projection の rollback evidence bundle を作る。
3. `make native-surfaces` で C01 apply → C01 check を続けて実行する。

CI は修復しない。`make native-surfaces-check` だけで drift を検出し、修復差分を開発者の
手元へ戻す。これにより CI が未レビューの生成差分を作って緑になることを防ぐ。

plugin の install / enable / hook trust / re-trust / uninstall はユーザーが製品 UI で行う。
build や SessionStart hook が代行してはならない。未実行の runtime 操作は失敗ではなく
`pending_user_gate` として記録し、local implementation の PASS と分ける。

## Part 2 — Operator / technical runbook

### 1. 不変条件と owner

- local projection desired-set: C01 が `repo-present ∩ project-enabled` から一度だけ導出する。
  install / hook trust は製品側の runtime activation gate として分離し、`pending_user_gate` で記録する。
- local repair: C01 `--apply` → 同じ C01 `--check`。旧
  `sync-skills-to-claude.sh --apply` を前後に混ぜない。
- CI: C01 `--check` のみ。CI 内で `--apply` しない。
- repo-owned writes: `.claude` managed projection、repo marketplace、plugin manifest など
  contract が許可した path のみ。
- forbidden writes: `~/.codex/config.toml`、`~/.claude/`、Codex/Claude trust store、
  `.agents/skills/beads`、推測 `.agents/{agents,commands,hooks}`。C01/C05 は global state を
  一切変更しない。
- supported kinds: `skill` / `hook`。Codex の Claude-style `agent` / `command` mapping は
  `unsupported/deferred` であり、silent success や推測 symlink を禁止する。

### 2. Preflight、projection evidence、local apply

repo root の clean/known worktree で実行する。先に変更予定を保存する。

```bash
make native-surfaces-dry-run
git status --short -- .claude .agents/plugins/marketplace.json plugins/harness-creator/.codex-plugin/plugin.json
```

apply 前に対象 surface が clean であることを確認する。これは rollback を C01 が作った
delta だけに限定し、user-owned の先行編集を巻き戻さないための必須 gate である。

```bash
evidence=.build/native-surfaces-projection-evidence
scope='.claude/skills .claude/agents .claude/commands .claude/settings.json .agents/plugins/marketplace.json plugins/harness-creator/.codex-plugin/plugin.json'
mkdir -p "$evidence"
git status --porcelain=v1 -- $scope > "$evidence/pre.status"
test ! -s "$evidence/pre.status"
python3 plugins/harness-creator/scripts/sync-native-surfaces.py \
  --repo-root . --dry-run --json > "$evidence/dry-run.json"
sha256sum "$evidence/dry-run.json" > "$evidence/dry-run.sha256"
```

preflight evidence を確認してから local repair を実行し、tracked delta と C01 が新規作成した
untracked path を別々に保存する。

```bash
python3 plugins/harness-creator/scripts/sync-native-surfaces.py \
  --repo-root . --apply --json > "$evidence/apply.json"
python3 plugins/harness-creator/scripts/sync-native-surfaces.py \
  --repo-root . --check --json > "$evidence/check.json"
git diff --binary -- $scope > "$evidence/projection.patch"
git ls-files --others --exclude-standard -- $scope > "$evidence/created.paths"
git status --short -- $scope > "$evidence/post.status"
sha256sum "$evidence"/{apply.json,check.json,projection.patch,created.paths,post.status} \
  > "$evidence/artifacts.sha256"
```

`make native-surfaces` は最後の apply→check 2 command の短縮形である。check が non-zero
なら commit/completed に進まない。drift は apply→check を再実行し、conflict / parse /
race / timeout は report の原因を直してから再試行する。`skipped_not_installed` は generator
不在だけに使う。

### 3. Claude Code lifecycle

この repo の `harness-creator` は `distributable:false` の repo-local plugin である。
public marketplace install は行わず、clone 内の source を使う。

1. **install 相当**: repo に `plugins/harness-creator/` が存在し、manifest を review する。
2. **enable**: `.claude/settings.json` の project-local `enabledPlugins` で
   repo 正本 `.claude-plugin/marketplace.json.name` と一致する exact identity
   `harness-creator@skills` を有効にする。旧 marketplace identity は削除する。
3. **trust**: Claude Code が hook trust review を提示したら、現在の hook command と path を
   review してユーザー自身が承認する。自動承認は禁止。
4. `make native-surfaces` を実行し、新しい session で SessionStart の structured result を
   確認する。
5. hook 定義・command・manifest digest が変わった upgrade では、旧 trust を流用せず製品の
   review 画面で current definition を **re-trust** してから新 session を開始する。
6. **uninstall/disable**: まず `enabledPlugins` を user 操作で無効化し、C01
   dry-run → apply → check で scope 外になった managed projection だけを prune する。
   user value と未知 event は残す。

trust / re-trust / disable が未承認なら evidence state は `pending_user_gate` のままにする。

### 4. Codex lifecycle

Codex の repo-local discovery は `.agents/plugins/marketplace.json` から
`./plugins/harness-creator` を指す。公式手順では plugin browser から install し、新 session
で bundled capability を読み込む。hook は install/enable だけでは実行されず、current hook
definition の user trust が必要である。

1. `plugins/harness-creator/.codex-plugin/plugin.json` と `hooks/hooks.json`、repo marketplace
   entry を review する。
2. ChatGPT desktop / Codex の Plugins 画面、または Codex CLI の `/plugins` で repo
   marketplace の `harness-creator` を install する。
3. plugin を enable する。
4. hook trust review で command、event、plugin root を確認し、ユーザー自身が trust する。
5. 新しい chat/session を開始し、SessionStart が一度だけ C01 を呼ぶことを確認する。
6. upgrade で hook definition が変わった場合は current definition を re-trust し、新 session
   で再確認する。trust を自動移行しない。
7. uninstall は plugin browser の **Uninstall plugin** を使う。bundled connector は plugin
   uninstall 後も接続済みの場合があるため、該当する場合は ChatGPT 側で別途管理する。
   その後 C01 dry-run → apply → check で repo-owned managed projection の prune を確認する。

Codex が local plugin を cache から読むため、source 更新後は製品の refresh/reinstall 手順と
新 session が必要になる場合がある。install/enable/trust/re-trust/uninstall の実操作と
runtime smoke はすべて `pending_user_gate` であり、build completion から分離する。

公式導線:

- [Plugins: install / permissions / uninstall](https://learn.chatgpt.com/docs/plugins)
- [Build plugins: repo marketplace / manifest / hooks / trust](https://learn.chatgpt.com/docs/build-plugins)

### 5. State transition と current output 例

local source の実在、product での enable、hook trust、new-session runtime は別の事実である。
後ろの gate を前の gate の PASS から推定しない。

| current state | 入る条件 | 次の遷移 | 禁止する緑判定 |
|---|---|---|---|
| `spec_ready` | contract / plan / inventory が揃う | focused tests + C01 check | route done だけで runtime 完了 |
| `local_implementation_pass` | source、manifest、repo projection、tests/check が local PASS | product ごとの user gate | manifest 実在だけで enabled/trusted |
| `runtime_activation_pending` | install / enable / trust / new-session のいずれかが未検証 | ユーザーが製品 UI で実行し evidence 取得 | `pending_user_gate` を FAIL または PASS へ読み替え |
| `runtime_verified` | current digest に対する trust + new-session fire + rollback evidence | release observation | 古い trust evidence の流用 |

2026-07-13 の local current-fact 例:

| product | source present | enabled evidence | trust/runtime evidence | 判定 |
|---|---:|---:|---:|---|
| Claude Code | `plugins/harness-creator/.claude-plugin/plugin.json` present | project `.claude/settings.json` で enabled | current hook digest の trust/new-session はこの wave で未実行 | `local_implementation_pass` + runtime evidence pending |
| Codex | `.codex-plugin/plugin.json` + repo marketplace present | install/enable は repo から断定不可 | **hook trust pending (`pending_user_gate`)** | `runtime_activation_pending` |

wrong repository では `.build` を作らず C01 を呼ばない。stdout は公式 SessionStart fields のみで、
`skipped_wrong_repository` の構造化詳細を対象 repo に書かないため無音にする。

```json
{"continue":true,"suppressOutput":true,"hookSpecificOutput":{"hookEventName":"SessionStart"}}
```

warning 時も child stdout/stderr/report は stdout へ出さず、要約と remediation/log path だけを
`systemMessage` / `additionalContext` に出す。完全な内部 status、bounded `child_report`、redacted
session id / diagnostic は harness identity 確認後の
`.build/logs/auto-sync-on-session-start.jsonl` のみに保存し、1 MiB または7日で rotate、
backup は3世代までとする。

### 6. CI sequence

CI は次の read-only sequence だけを実行する。

```bash
make native-surfaces-check
test -z "$(git status --porcelain -- .claude .agents/plugins/marketplace.json plugins/harness-creator/.codex-plugin/plugin.json)"
```

CI で apply してから check すると、未反映 drift を生成して隠すため禁止する。check failure の
remediation はローカルの `make native-surfaces` と diff review で行う。

### 7A. Projection rollback / managed-only restore

runtime gate 前、または apply 後の diff が意図と異なる場合は、release rollback ではなく
**projection rollback** を行う。preflight が clean であったことを前提に、C01 apply が作った
tracked patch と `created.paths` だけを戻す。ディレクトリ全体の `rm -rf`、`.claude/settings.json`
全体の上書き、global/trust state の変更は禁止する。

```bash
evidence=.build/native-surfaces-projection-evidence
scope='.claude/skills .claude/agents .claude/commands .claude/settings.json .agents/plugins/marketplace.json plugins/harness-creator/.codex-plugin/plugin.json'
test -f "$evidence/projection.patch"
git apply -R --check "$evidence/projection.patch"
git apply -R "$evidence/projection.patch"
while IFS= read -r path; do
  test -n "$path" && rm -f -- "$path"
done < "$evidence/created.paths"
git status --porcelain=v1 -- $scope > "$evidence/rollback.status"
cmp "$evidence/pre.status" "$evidence/rollback.status"
python3 plugins/harness-creator/scripts/sync-native-surfaces.py \
  --repo-root . --dry-run --json > "$evidence/rollback-dry-run.json"
sha256sum "$evidence"/{rollback.status,rollback-dry-run.json} > "$evidence/rollback.sha256"
```

rollback 後の C01 `--dry-run` は source が現行 desired-set のままなら drift を示し得る。
それは rollback 失敗ではない。PASS evidence は `cmp pre.status rollback.status` と patch / created-path
の逆適用結果であり、再 apply は人間が dry-run を review してから選ぶ。

### 7B. Release rollback / source + activation

release 後に source contract 自体を戻す場合は projection rollback と混ぜない。git publish と
product lifecycle はどちらもユーザー承認 gate であり、本 runbook の検証で自動実行しない。

1. release commit の `changed path inventory` と下の release inventory が一致することを確認する。
2. 承認後に `git revert <release-commit>` で source を別 commit として戻す。history rewrite は行わない。
3. すでに activation 済みなら、Claude/Codex それぞれの UI で user が disable/uninstall する。
   trust store を script から削除・復元しない。
4. reverted source で C01 dry-run → apply → check、new session、projection inventory の差分を記録する。
5. `release-rollback/{git-revert.txt,c01-dry-run.json,c01-apply.json,c01-check.json,post.status,artifacts.sha256}`
   を evidence とし、runtime 未実行なら `pending_user_gate` を維持する。

#### Release file inventory (source / gate / docs / tests)

- root integration: `Makefile`, `.github/workflows/governance-check.yml`,
  `.agents/plugins/marketplace.json`, `scripts/build-claude-settings.py`,
  `scripts/build-claude-symlinks.py`, `tests/test_build_claude_settings.py`,
  `tests/test_build_claude_symlinks.py`
- plugin envelope/wiring: `plugins/harness-creator/.claude-plugin/plugin.json`,
  `plugins/harness-creator/.codex-plugin/plugin.json`, `plugins/harness-creator/hooks/hooks.json`,
  `plugins/harness-creator/plugin-composition.yaml`
- implementation/gates: `plugins/harness-creator/hooks/auto-sync-on-session-start.py`,
  `plugins/harness-creator/scripts/sync-native-surfaces.py`,
  `plugins/harness-creator/scripts/check-native-surface-parity.py`,
  `plugins/harness-creator/scripts/record-task-graph-knowledge.py`,
  `plugins/harness-creator/commands/capability-build.md`,
  `plugins/harness-creator/skills/run-build-skill/scripts/validate-route-build-reports.py`
- operations/contract: `plugins/harness-creator/README.md`,
  `plugins/harness-creator/references/native-surface-contract.md`,
  `plugins/harness-creator/references/native-surface-operations.md`
- focused regression: `plugins/harness-creator/tests/test_auto_sync_on_session_start.py`,
  `plugins/harness-creator/tests/test_check_native_surface_parity.py`,
  `plugins/harness-creator/tests/test_native_surface_repo_integration.py`,
  `plugins/harness-creator/tests/test_sync_native_surfaces.py`,
  `plugins/harness-creator/tests/test_record_task_graph_knowledge.py`,
  `plugins/harness-creator/tests/test_validate_route_build_reports.py`

`.claude/{skills,agents,commands}` と `.claude/settings.json` は C01 が生成する projection であり、source
release inventory とは分けて `projection-evidence/{pre,post,rollback}.status` に記録する。
`eval-log/harness-creator/build/route-*.json` は build evidence であり release source ではない。

### 8. Unsupported/deferred の再評価 trigger

Codex の `agent` / `command` は次のどれかが発生した時だけ再評価する。

- OpenAI 公式 plugin docs が agent/command の manifest field または plugin directory mapping
  を追加した。
- Codex release notes / current CLI の schema が、公式に同 surface を列挙した。
- repo の `native-surface-contract.md` に記録した `checked_at` / CLI version の refresh gate が
 到来し、公式 source の再確認で分類変更が必要になった。

再評価は structural change とし、`native-surface-contract.md` の source URL・checked_at・
classification、C02 negative tests、C01 desired-set、runbook を同じ change で更新し、人間承認を
得る。公式 mapping がない間は `unsupported/deferred` を維持し、推測実装しない。
