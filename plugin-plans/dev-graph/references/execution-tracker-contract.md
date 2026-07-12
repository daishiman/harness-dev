# execution-tracker-contract

> dev-graph が管理する task ノードを「どの実行トラッカーで走らせるか」の契約 (正本)。
> 根拠: beads 公式 FAQ の使い分けガイダンス (人間チーム+Web UI = GitHub Issues / AIエージェントのオフライン・グラフ意味論・決定論的クエリ = bd)。
> 由来: `improvement-handoff-beads.json` EV-B06 により `references/execution-tracker-contract-draft.md` (draft) から正本化。

## 0. プランナー選定ルール (入口の二者択一)

構築対象で planner を選び、repo profile と task の実行主体で tracker を選ぶ。この2軸は直交する。plugin route は dev-graph を経由せず consumer projection を使い、system route は dev-graph へ batch 登録してから tracker binding を解決する。

| 構築対象 | プランナー | タスク仕様書 | beads 看板への反映経路 |
|---|---|---|---|
| **plugin 構築** (Claude Code plugin / skill / agent / hook) | plugin-dev-planner (`/plugin-dev-plan`) | `plugin-plans/<slug>/task-graph.json` + task-specs/ | §6 の consumer 直接投影。既定は task-state.json → bd 冪等 upsertで、dev-graphを経由しない |
| **システム構築** (アプリ / API / インフラ等の system 開発) | system-dev-planner (`/system-dev-plan`) | typed task spec (`SYS-<workstream>-<NNN>`) | system-dev-planner → dev-graph atomic 登録 → 本契約 §1-§5 (tracker_binding 解決) |

- 判定基準: 成果物が `plugins/<slug>/` 配下の Claude Code plugin 実体なら plugin ルート。導入先リポジトリのアプリケーション/システムコードなら system ルート。両方を含む構想は分割し、それぞれのプランナーへ投入する。
- 操作導線: plugin は `/plugin-dev-plan` → `/capability-build` → consumer tracker projection、system は `/system-dev-plan` → promotion → dev-graph batch registration → `dev-graph next/claim`。表示は beads-kanban または GitHub Projects、完了事実は §3/§6 の route 別 authority が決める。hook は加速器であり authority ではない。
- system ルートの task-graph mode build (`/capability-build`) が plugin を副生する場合も、タスク管理の所属は起点プランナー側に従う (二重登録禁止)。
- `external_ref` は両ルートで衝突しない prefix 規約 (plugin ルート=`<plan-slug>/<node-id>`、system ルート=graph_node_id (`tasks/<id>`)) を維持する。

## 1. 使い分け決定表 (repo プロファイル別の既定ポリシー)

repo の `.dev-graph/config.json` → `execution_tracker.mode` の既定を、新規リポジトリ立ち上げ時に本表で決める。
mode: `beads` = 実行タスクは bd のみ / `github` = GitHub Issues のみ / `both` = taskノード単位で tracker_binding を選択。

registration payloadの`tracker_binding="repo-config-default"` sentinelと`binding_intents[graph_node_id]`の解決ownerはC02。intentがexplicit `beads|github|none`ならrepo-config許容範囲と照合し、`auto`はmode=beads|githubだけで同値に解決する。mode=bothのautoは人/AI主体を機械判定できず誤投影になるためfail-closedし、明示intentを要求する。確定enumへ変換してからC11へ渡し、sentinelは永続化しない。

| repo プロファイル | execution_tracker.mode 既定 | GitHub ミラー (beads束縛タスク) |
|---|---|---|
| ソロ + AI エージェント開発の private repo (**既定**) | beads | 不要 (local_only) |
| 人間の協力者/レビュアーへ進捗共有する private repo | both | `bd github sync --push-only` で beads→GitHub 一方向ミラー |
| 外部コントリビュータを受け入れる public OSS repo | github | — (GitHub Issues が最初から正本) |
| 使い捨て実験/プロトタイプ repo | beads | 不要 (完了後は bd compact で要約保持) |

- 本表はソロ AI エージェント開発を主とする運用の既定 (ユーザー委任により確定)。迷った場合は beads を選ぶ (公式 FAQ: AI エージェント実行は bd 優位)。
- mode=both はtask単位の`tracker_binding_intent=beads|github|none`を必須とし、`auto`を禁止する。mode=beads|githubでは`auto`を同じbindingへ決定論解決できる。
- Beads mirrorをGitHub Projectsへ載せる場合、Projectsはviewer-onlyとしGitHub native auto-add/Doneだけを使う。custom fieldを双方向管理したいtaskは`tracker_binding=github`を選ぶ。
- mode 変更 (migration): mode を変更しても既存ノードの `tracker_binding` は自動変更しない (新 mode は新規ノードにのみ適用する)。既存束縛の移行は dry-run manifest 付きの明示 migration として実行する。旧 tracker 側の issue は `close --reason=migrated` で収束させる。

## 2. 状態写像表 (正本 = dev-graph node.status)

| dev-graph node.status | bd status | GitHub Issue state |
|---|---|---|
| draft | (未起票) | (未起票) |
| active (未着手・ready) | open | open |
| active (claim 済み) | in_progress | open + assignee |
| blocked | blocked | open |
| done | closed | closed |
| closed | closed | closed |
| tombstoned | closed (`close --reason=tombstoned`) | closed |

- tombstoned の bd 写像は `bd close --reason=tombstoned`。bd 側の tombstone status は実在するが delete 系操作でのみ遷移するため bridge は行わない (C28 は破壊操作を呼ばない)。
- bd status 語彙の出典: bd v1.1.0 組込み status = open/in_progress/blocked/closed/deferred (+hooked/tombstone)。
- parity突合対象はstatusと依存edge exact-set (`dev-graph depends_on` ↔ bd `blocks`)。priority/assignee/labelsはbd側自由領域とする。statusまたはedge差分はC03の手動確認フローへ回し、解消までready推薦から除外する。
- 写像は冪等 projection として C28 bd-bridge / C12 gh-bridge が適用する。逆方向の書込み (bd 側の手動 close を dev-graph へ取り込む等) は C03 sync / C26 reconciliation の突合で検出し、自動上書きせず manual conflict へ回す。

## 3. system/dev-graph route の完了カスケード契約 (完了忘れ防止)

事実 authority は1つ: **remoteの現在default branchをtargetにしたlinked PRがmerged=true (merge_commit_shaで照合)**。GitHub bindingはclosing reference、Beads bindingはPR本文の`dev-graph: <graph_node_id>` markerまたは同じPR番号の`gh:pr` gateをlinkage証拠に使う。PR close未mergeはどちらも完了ではない。

```
PR merged (事実 authority)
  ├─ [remote fast path] GitHub linked-issue auto-close / Projects built-in Done / bd gates gh:pr
  └─ [修復経路] C26 reconcile-github-lifecycle:
        completion transactionをevent keyで開始
          → node lifecycleをC26がrestricted patch
          → task仕様書frontmatterをC02単一writerで更新
          → tracker_binding=beadsだけC28がbd close (外部writeは最後)
```

- 発火: C25 hook (SessionStart = merge-back 後のローカル回収 / PostToolUse = git push・gh pr merge 検出時の即時収束)。配線は plugin hooks/hooks.json 共有既定 + `.claude/settings.json` fallback、二重登録禁止。
- 各stepは`pending|applied|pending_retry`を持つ同一event-key receiptで再開可能にする。local graphとtask Markdownを先に確定し、bd close/Projects repairなど外部writeは最後に行う。途中失敗で既適用stepを巻き戻さない。
- C12が返すremote `defaultBranchRef{name,target.oid}` とlocal branch名が一致し、`git merge-base --is-ancestor <merge_commit_sha> HEAD`が成功するclean worktreeだけがdurable完了を書ける。behind/diverged/dirtyならpendingのままにする。
- `gh:pr` gateのcloseはPR番号・merge SHA・graph_node_idを照合できる場合だけexpected fast pathとして受理する。根拠のないbd手動closeはconflictで、gateとC26の二重closeは冪等no-opにする。
- PR close (未 merge) は done にしない (既存 github-lifecycle-contract の authority を維持)。

カスケードの書込み分担 (writer 対応表):

| 書込み対象 | writer |
|---|---|
| completion transaction / graph node lifecycle projection | C26 (restricted writer + step receipt owner) |
| task 仕様書 frontmatter (tasks/*.md) | C02 (単一 writer) |
| beads close / retry | C28 (C26 receiptの未適用stepだけを実行) |
| カスケード起動 | C03 sync (C25 hook は発火のみで書かない) |
| feature 完了 rollup (features/*.md) | C26 が導出 → C02 (単一 writer) が書込み (§8.2) |

- feature ノードの完了 (配下 task が全 done → `feature.status=done`) は本カスケードの feature 拡張として §8.2 が正本定義する (task→feature の一方向・機械導出・手動 done 昇格は fail-closed)。§3 のカスケードは task ノードの完了事実を確定し、その完了が親 feature を完成させたかは §8.2 が同一 transaction 内で評価する。

## 4. 二重起票禁止 (単一 publication authority)

- `tracker_binding=beads` のtaskノードは`github_publication.mode=local_only`を強制する。GitHub mirrorが必要なら **`bd github sync --push-only`** だけがIssue publication authorityで、bidirectional defaultは使わない。C12はIssue create/update/closeを行わない。
- push-only結果のmirror Issue identityは`beads_linkage.github_mirror`へread-only projectionとして保存し、PR marker/Projects auto-add照合に使う。`issue_linkage`はGitHub-authority task専用のままにする。
- Beads mirrorのProjectsはnative auto-add/Doneによるviewer-only。C12 custom-field 3-way同期対象外で、管理custom fieldsが必要ならGitHub bindingを選ぶ。
- `tracker_binding=github` のtaskはbdへprojectionせず、`github_publication.mode`を`issue|issue_and_projects`に限定する。`github + local_only`は禁止する。
- 仕様書・アーキテクチャ・ドキュメント系 artifact (task 以外) は本契約の対象外 (従来どおり dev-graph + GitHub)。

## 5. worktree 並列実行との対応

- Beads bindingではC28の`bd update <id> --claim`をtask所有権authorityとし、C27はworktree identity/resource_scope reservationの追加制約に限定する。GitHub bindingではC27 leaseがtask claim authorityとなる。
- claim sagaは`preflight → C27 reservation → C28 atomic claim → C02 execution_context projection`の順。C28失敗時はreservationを解放し、C02失敗時は`pending_reconcile`として同じclaim transactionを再開する。
- C28 preflightはlinked worktreeが同一Beads workspace/database identityを解決していることを検証する。dependency projectionがpending_retryならready集合は`bd ready ∩ dev-graph DAG ready`に限定する。
- lease 解放・merge-back 後は default branch 側の C25 SessionStart 発火で最終収束 (§3 カスケード)。
- resource_scope 重複回避 (並列バッチのファイル競合防止) は beads に存在しない dev-graph 固有価値として ready-set 委譲後も dev-graph 側で適用する。
- bd DB の共有単位は bd 側の責務。bridge は同一 repo 内の worktree から同一 bd DB が見えることを preflight で確認する。`bd dolt push/pull` は dev-graph component の責務外 (利用者/orchestrator 所有) で、stale DB での突合は報告のみとする。

## 6. plugin ルートの beads 直接投影 (plugin-dev-planner 系・dev-graph 非経由)

plugin構築taskはdev-graphに登録せずtask-graph実行状態からtrackerへ直接投影する。既定Beads projectionはfollow-up `harness-c1h`が実装ownerで、未完了ならprojection capabilityは**unavailableとしてfail-closed**し、plan validation PASSとruntime利用可能を混同しない。

- **正本と単一 writer (既存ドクトリン維持)**: canonical 構造 = `task-graph.json` (writer: derive-task-graph.py・state は pending seed 固定)。runtime 状態 = `task-state.json` (単独 writer: consumer `/capability-build`)。**beads 投影は task-graph-status.json 等と同格の「consumer 所有の追加投影」**として置き、producer (plugin-dev-planner) は書かない。
- **完了authority**: PR非対象nodeはconsumer `task-state.json`のdone+local evidenceで完了できる。PR管理対象nodeはbuild doneだけではcloseせず、`gh:pr` gateまたはmerged PR evidence後にdoneへ進める。closed-unmergedはopen/blockedのまま。
- **投影規則**: task-graph.json の component-build/direct-task ノード + task-state.json の状態/evidenceを読み、bd issueを冪等upsertする。冪等キー=`external_ref="<plan-slug>/<node-id>"`。`depends_on`→`bd dep add`、`parent_of`→`--parent`。
- **逆流禁止**: beads 側での手動 close は task-state.json に書き戻さない (parity 突合で差分検出し報告のみ)。ready の正本は依存 DAG からの computed であり、`bd ready` は同型の派生ビュー。
- **実装の置き場 (follow-up)**: harness-creator の TG-C09 (`project-task-status.py`) と並置の投影スクリプト (例 `project-task-beads.py`) として実装する。本契約はその仕様書を兼ねる。
- **投影先と対象境界**: 投影先は plan_dir が属する repo の bd DB。`external_ref` を持つ issue のみが投影管理対象で、手動起票 issue には触れない。prefix は bd 側 repo 設定に従う。follow-up の起票先: harness-creator plan (未起票の間は本契約が唯一の仕様。bd issue harness-c1h で追跡中)。

## 7. upstream 変動耐性 (beads / beads-kanban は日々更新される前提)

beads 本体・beads-kanban の更新に設計が引きずられないよう、結合面を最小化し 1 点に集約する。

- **単一チョークポイント (anti-corruption layer)**: bd 呼び出しは bridge (C28 bd-bridge / plugin ルートの project-task-beads.py) のみが行う。skill/hook/agent からの bd 直接呼び出しを設計上禁止し、upstream の CLI 変更は bridge 1 箇所の修正で吸収する。
- **安定 surface のみに依存**: 依存してよいのは(a)`--json`、(b)JSONL export/import、(c)`external_ref`/`metadata`、(d)`bd github sync --push-only`/`bd gate gh:pr`の公開CLI。`bd sql`、`.beads/`直接read/write、beads-kanban HTTP APIには依存しない。
- **version pin + 受容 window**: bridge は preflight で `bd version` を検査し、受容 window **>=1.1.0 <2.0.0** 外なら fail-closed で明示エラーを返す (system-dev-planner plan の system-spec-source-pin.json と同型の pin 運用。window 更新は本契約の Edit 差分 + bridge の定数更新で行う)。既知の将来破壊への先回り: bd v2.0 で JSON envelope (`{"schema_version":1,"data":...}`) が既定化予定のため、bridge のパーサは envelope 有無の両形式を受容する。
- **beads-kanban は交換可能な viewer**: bd CLI 経由で読み書きするローカル viewer であり、本契約は結合しない (看板 UI の更新・置換・廃止は契約に影響しない)。本契約が保証するのは「bd の issue/依存/状態が正しい」ことまで。
- **drift 検出**: bridge preflight の失敗 (window 外 / --json 形状不一致) は同期を停止して報告する (silent degradation 禁止)。正本 (task-state.json / dev-graph node) は bd 停止中も無傷で、bridge 復旧後の冪等 upsert で追いつける。

## 8. 二層モデル (マクロ/ミクロ棲み分け・feature 完了カスケード) — 正本

dev-graph=マクロ層 (機能単位の保持 + 実行オーケストレーション) と system-dev-planner=ミクロ層 (1 feature→13 タスク仕様書 + 機能内依存 DAG) の棲み分け、および feature 完了の機械導出をここで正本化する。§0 のプランナー選定 (構築対象での planner 二者択一) とは直交する軸で、**本節がマクロ/ミクロ模型の durable な単一正本** (improvement-handoff-macro.json は transient な入力物であり正本にしない)。両 plan の index はマクロ/ミクロ模型の正本として本 §8 を参照する。

### 8.1 二層の責務境界

- **マクロ (dev-graph)**: `artifact_kind=feature` ノードが purpose/goal/scope_in/scope_out/acceptance/architecture_refs を第一級に保持し、機能間依存を feature ノード間の `depends_on` で表す。C14 が自然文の want を feature + architecture + 機能間 depends_on へマクロ分解する (13 タスク仕様書へは踏み込まない)。
- **ミクロ (system-dev-planner)**: ready feature (機能間 depends_on 充足) ごとに C14 が run-system-dev-plan を Skill 呼出し (自動)、または人間の `/system-dev-plan` (手動フォールバック) で起動し、feature を消費して 13 lifecycle タスク仕様書 + 機能内依存 DAG を生成する。promoted task は `parent_feature`=当該 feature として C02 単一 writer 経由で atomic 登録する。
- **一方向**: `want → C14 マクロ分解 → ready feature → per-feature planning (自動/手動) → promoted task (parent_feature) → tracker 投影`。feature の生成は dev-graph のみ、program 全体の goal/scope は goal-spec が保持する (feature は機能単位に閉じる)。
- **ゼロ段 fast path**: feature 文脈を持たない単発 task は `parent_feature=null` で features/ を経由せず直接登録できる。マクロ層の ceremony (feature 6 フィールド記入) を trivial case へ課さない。

### 8.2 feature 完了ロールアップ (機械導出・§3 の feature 拡張)

- **完了 authority は機械導出**: `feature.status=done` は「配下 task (parent_feature=当該 feature) が全て done」のときだけ成立する computed projection。task 完了 (§3 カスケード) と同じ machine-authority ドクトリンを feature 層へ転写し、人/LLM による feature.status の手動 done 昇格は fail-closed (§3 の PR-merge=完了事実と同型で、feature は子集約が事実)。
- **writer と発火**: C26 が §3 の task 完了 transaction 内で「当該 task.parent_feature の配下 task 集合が全 done か」を評価し、成立時に feature completion rollup を restricted patch で導出、C02 単一 writer が features/*.md frontmatter を更新する。task→feature の一方向 (feature を close しても配下 task を一括 close する逆流はしない)。
- **tombstone/close 方向**: active な配下 task を残したままの feature close/tombstone は fail-closed (先に子 task の収束を要求)。C11 が parent_feature 実在検査と併せて計上する。

### 8.3 層分離の依存検査

- task の `depends_on` 先は同一 parent_feature 内の task に限る。機能間依存は feature ノード間 depends_on で表し、task が別 feature の task を直接指す層越え参照は C11 が違反計上する (feature-only 非循環検査をすり抜ける層越え循環の封鎖)。related_nodes (順序なし関連) はこの制約の対象外。

### 8.4 sub-feature 非対応 (二層固定)

- feature の親子 (feature.parent_feature) は構造的に不可 (schema が `artifact_kind=feature` で parent_feature=null を強制)。本モデルは意図的に二層固定で、巨大 feature は scope_in/scope_out で機能境界を切り直すか複数 feature へ分けて機能間 depends_on で表現する (epic→story→task の 3 階層は導入しない)。要件が 3 階層を要するようになった場合は本 §8.4 の Edit 差分 + schema 拡張で明示的に解禁する。

### 8.5 feature の tracker 投影 (任意・repo profile 依存)

- **既定 (solo AI / beads / local_only)**: feature は外部 tracker へ投影せず、C05 render が feature 単位の子 task 進捗 (X/Y) を集約表示することで「機能単位の実行オーケストレーション」を可視化する (epic 投影 surface は不要)。
- **github/both profile**: feature を GitHub Milestone (配下 Issue を進捗つきで束ねる native epic) または beads `--parent` epic へ投影してよい。投影は task 投影 (§4/§6) と同じ単一 authority 規律に従い、feature 完了は 8.2 の子集約が正本で、Milestone/epic の close は表示であって完了 authority にしない。

### 8.6 architecture_refs の解決境界

- C14 は per-feature planning 起動時に feature.architecture_refs を **解決済み lineage-pinned content** として feature context へ同梱する。system-dev-planner は architecture ノード id を dereference せず、system-spec-harness を独立に再引用もしない (cross-plugin read と二重引用の回避・MS-03/MM-12)。
