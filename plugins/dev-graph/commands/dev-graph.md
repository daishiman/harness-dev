---
name: dev-graph
description: システム開発を要件定義から運用まで毎回同じ手順で進めたいとき、init/spec/decompose/plan/requirements/node/next/worktree/status/sync/render の11 verbを正規 capability へ dispatch したいときに使う。
kind: command
version: 0.1.0
owner: harness maintainers
source: plugin-plans/dev-graph/component-inventory.json#C09
argument-hint: "<init|spec|decompose|plan|requirements|node|next|worktree|status|sync|render> [args] | plan --feature-id ID --feature-context RELATIVE_JSON"
allowed-tools: [Read, Bash, Skill]
disable-model-invocation: false
---

# /dev-graph

## dispatcher の基本ルール

`/dev-graph` は最初の token を verb（動作を表す語）として厳密に解釈します。未知の verb、依存 plugin／script の不在、repository root の誤りを検出した場合は、候補一覧を返して停止します。似たコマンドを推測して実行することはありません。引数は選択した Skill/script へそのまま引き継ぎ、shell 文字列として再評価しません。

成果物の保存先は、次の3系統です。

- **content root**: repository 直下の `issues/`、`tasks/`、`specs/`、`architecture/`、`features/`、`docs/`、`system-spec/`
- **`.dev-graph/`**: グラフ状態、cache、lock、plan、描画結果などの内部データ
- **`eval-log/`**: 各 command の実行記録・評価ログ

「副作用なし」は、グラフや文書を書き換えず、結果を表示するだけという意味です。ただし `next` と `status` も評価記録として `eval-log/` は更新します。

## 11 verb の役割・出力先・dispatch 先

| # | verb | そこで何をするか | 主な出力先 | dispatch |
|---|---|---|---|---|
| 1 | `init` | dev-graph を初期化し、作業グラフ（タスク依存関係図）の土台を用意する。冪等（べきとう＝何度実行しても同じ状態） | content root 6個（`issues/ tasks/ specs/ architecture/ features/ docs/`）＋ `.dev-graph/`。`system-spec/` は `spec` が用意する | Skill `run-dev-graph-init` |
| 2 | `spec` | システム仕様（作るものの仕様書）を作成し、確定仕様・設計を dev-graph へ取り込む | `system-spec/` ＋ `specs/` ＋ `architecture/` ＋ `.dev-graph/state/graph.json` | Skill `run-dev-graph-system-spec`（system-spec-harness を引用） |
| 3 | `decompose` | 大きな構想を feature、architecture、機能間依存へマクロ分解する | `features/` ＋ `architecture/` ＋ `.dev-graph/state/graph.json` | Skill `run-dev-graph-decompose` |
| 4 | `plan` | 着手可能になった1 feature を実行可能なタスク仕様書へ分解する | `.dev-graph/staging/` → `.dev-graph/plans/`。昇格後は `tasks/<feature>/` | external Skill `run-system-dev-plan` |
| 5 | `requirements` | 確定仕様と feature package から実装要件を導出し、準備完了時だけ次工程へ handoff（引き継ぎ）する | 要件定義書 ＋ `--handoff-target` で指定した capability-build／task-graph | Skill `run-dev-graph-requirements` |
| 6 | `node` | 上位 command が自動登録しない node（1作業単位）を正規 path へ atomic（全部成功か全部失敗か）で追加・差分更新する | 種類別 content root ＋ `.dev-graph/state/graph.json` | Skill `run-dev-graph-node` |
| 7 | `next` | 依存、resource 競合、lease を満たす、次に着手できる作業 batch を算出する | 画面表示 ＋ `eval-log/`。グラフへの副作用なし | Skill `run-dev-graph-schedule` |
| 8 | `worktree` | worktree（作業用に複製したディレクトリ）の占有権を管理する | git 共通ディレクトリ配下の `dev-graph/leases.json` と `events.json`。claim 時は graph に実行 context も記録 | `scripts/manage-worktree-lease.py` |
| 9 | `status` | node を条件検索し、依存・確定・完了状態を確認する | 画面表示 ＋ `eval-log/`。グラフへの副作用なし | Skill `run-dev-graph-status` |
| 10 | `sync` | dev-graph と Beads／GitHub Issues／PR を突き合わせ、再実行で差分0へ収束させる | `.dev-graph/state/graph.json` ＋ Beads DB／GitHub。lifecycle 収束時は `tasks/` も更新 | Skill `run-dev-graph-sync` |
| 11 | `render` | dev-graph を、外部 CDN 不要の静的 HTML と SVG へ可視化する | `--out` で指定した repository 内の HTML | Skill `run-dev-graph-render` |

dev-graph 自身の Skill を使う `init / spec / decompose / requirements / node / next / status / sync / render` は、実行ごとに `eval-log/run-dev-graph-<verb>-*.json(l)` へログを残します。外部 Skill の `plan` と純 script の `worktree` は、この eval-log 契約の対象外です。`system-spec` という単独 verb は存在しません（`spec` が system-spec-harness を引用します）。

## なぜこの順番なのか

| # | verb | 前工程との依存関係 |
|---|---|---|
| 1 | `init` | content root と `.dev-graph/` が無ければ、後続の登録先が存在しない |
| 2 | `spec` | 初期化済みの保存先へ確定仕様と設計を登録し、「何を作るか」を固める |
| 3 | `decompose` | 確定仕様を入力に、大きな構想を feature と architecture へ分解する |
| 4 | `plan` | `decompose` が生成した ready feature を実行タスクへ計画する。未分解の大構想は直接受けない |
| 5 | `requirements` | `plan` が生成した feature package と確定仕様から実装要件を導出する |
| 6 | `node` | 1〜5が自動登録しない成果物を、単一 writer（書き込み窓口）から追加・更新する |
| 7 | `next` | 組み上がったグラフから、依存・競合・lease を考慮した着手候補を出す |
| 8 | `worktree` | `next` が示した作業を claim し、実作業の占有権を確保する |
| 9 | `status` | 着手中 node の依存・確定・完了状態を監視する |
| 10 | `sync` | 実作業の結果を Beads／GitHub と同期し、状態を収束させる |
| 11 | `render` | 任意の時点で、現在の依存グラフを静的 HTML にする |

`init → spec → decompose → plan → requirements` は、前工程の出力を次工程が使う一方向パイプラインです。`node → next → worktree → status → sync` は開発中に繰り返す運用ループで、`render` は随時実行できます。

## 共通 preflight

1. 呼出し元repository rootを`--repo-root`、`CLAUDE_PROJECT_DIR`、現在地の順で1回だけ確定する。
2. `next/status/render/worktree list`は`resolve-repo-context.py --mode read`、`node/sync/worktree claim|heartbeat|park|release|reclaim`は`--mode write`で実行する。上流 verb（`init/spec/decompose/plan/requirements`）は dispatch 先 Skill が自身の contract で context 解決と検証を行う。
3. configの`local_state.graph`を正規graph pathとして使い、以後cwdから再解決しない。
4. write操作は`--dry-run`が指定されたらgraph/content/external writeを0件にする。

## verb契約

### init

`run-dev-graph-init`を呼ぶ。content root 6個と`.dev-graph/`を冪等に用意し、既存のgraph/contentを破壊しない。`system-spec/`は`spec`が用意する。

### spec

`run-dev-graph-system-spec`を呼ぶ（system-spec-harnessの正規entrypointを引用）。確定仕様・設計を`source_lineage`付きでdev-graphへ取り込み、dev-graph内に同等のelicit/compile実装を複製しない。

### decompose

`run-dev-graph-decompose`を呼ぶ（macro feature only）。確定仕様を入力に、大きな構想をfeature・architecture・機能間依存へ分解する。

### plan

external Skill `run-system-dev-plan`へdispatchする。大きな未分解構想を直接受けず、`decompose`が生成したready featureを`--feature-id`とcaller-repository相対JSON `--feature-context`で要求する。両者のid/digestが一致しなければ停止する。

### requirements

`run-dev-graph-requirements`を呼ぶ。確定仕様とfeature packageから実装要件を導出し、readiness充足時だけ`--handoff-target`で指定したcapability-build/task-graphへhandoffする。

### node

`run-dev-graph-node`を呼び、preview後に`build-graph-node.py`の`add|update|bind-github|link-github`へ検証済みJSONを渡す。更新は許可されたfieldの`node_patch`と、見出し単位の`set_sections`／`append_sections`だけで行い、本文を全書換しない。`graph_node_id`は不変で、`artifact_kind`からcontent rootを決める。graphとcontentは単一transactionで書き、失敗時はrollbackする。exact-13 feature package（P01..P13）はbuild-graph-nodeでは受けず、`register-package.py`がall-or-noneで登録する。

### next

`run-dev-graph-schedule`を呼ぶ。git共通ディレクトリの`dev-graph/leases.json`を`--leases`のsnapshotとして渡す。Beads bindingでは同じ周回で`build-parity-manifest.py`と`bd-bridge.py --op ready`を実行し、edge parity確認済み候補だけを`--ready-source bd-bridge --ready-json`で渡す。GitHub/noneは`--ready-source self`でlocal graphから計算する。ready payloadに`parity_provenance`があれば、その`source_graph_digest`が現graphのcanonical digestと一致しないsnapshotではscheduleを停止する。`--scope`と`--max-parallel`をそのまま渡す。

### worktree

許可操作は`claim|heartbeat|park|release|reclaim|list`だけ。必ず`--repo-root <root>`を付け、public formを次の正準flagへ一度だけ変換する。位置引数をscriptへそのまま渡さない。

| public form | script form |
|---|---|
| `worktree list` | `manage-worktree-lease.py --op list` |
| `worktree claim <id> --branch <name> --session-id <session>` | `manage-worktree-lease.py --op claim --graph-node-id <id> --branch <name> --session-id <session>` |
| `worktree heartbeat <id> --session-id <session>` | `manage-worktree-lease.py --op heartbeat --graph-node-id <id> --session-id <session>` |
| `worktree park <id> --session-id <session>` | `manage-worktree-lease.py --op park --graph-node-id <id> --session-id <session>` |
| `worktree release <id> --session-id <session>` | `manage-worktree-lease.py --op release --graph-node-id <id> --session-id <session>` |
| `worktree reclaim <id>` | `manage-worktree-lease.py --op reclaim --graph-node-id <id>` |

`claim`は`graph_node_id`、`session_id`、正準branch `devgraph/<graph_node_id>`を要求する。`reclaim`は期限切れleaseだけを明示的に`released`へ遷移させる。lease正本は`git rev-parse --git-common-dir`で得た共通dirの`dev-graph/`に限定し、`.dev-graph/locks/`は使わない。

### status

`run-dev-graph-status`を呼ぶ。filterは`id/kind/project/domain/status/tag/keyword`のAND条件とし、結果0件も成功とする。結果には依存・completion・tracker linkage・execution contextを含める。書込み先はrepository内の`eval-log/`配下だけを許可する。

### sync

`run-dev-graph-sync`を呼ぶ。bindingごとの単一authorityを守り、GitHub bindingは`gh-bridge.py`と`diff-github-issues.py`／`diff-github-project-fields.py`、Beads bindingは`bd-bridge.py`が担う。last-synced snapshotとの3-way差分を作り、close/deleteは物理削除せずclosed/tombstonedへ収束させ、Projectsの部分失敗はalias単位`pending_retry`として残す。同一状態の2回目は`changes=0`で、GitHubの両計画は`converged=true`を完了条件にする。PR完了は`reconcile-github-lifecycle.py`でdefault branchへのmergeと`required_pull_requests=all|any`を検証した場合だけ採用する。

### render

`run-dev-graph-render`を呼ぶ。`render-graph-html.py`へ検証済みgraph、repository内の`--out`、任意のregistration receipt（`--receipt`、複数可）を渡す。出力HTMLはSVG/CSS/JSをinline化し、外部`script/link`参照を0件にする。
