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
- 操作導線: plugin は `/plugin-dev-plan` → `/capability-build` → consumer tracker projection、system は `/system-dev-plan` → promotion → dev-graph batch registration → `dev-graph next/claim`。表示は strandkanban (旧称 beads-kanban) または GitHub Projects、完了事実は §3/§6 の route 別 authority が決める。hook は加速器であり authority ではない。
- system ルートの task-graph mode build (`/capability-build`) が plugin を副生する場合も、タスク管理の所属は起点プランナー側に従う (二重登録禁止)。
- `external_ref` は両ルートで衝突しない prefix 規約 (plugin ルート=`<plan-slug>/<node-id>`、system ルート=graph_node_id (`tasks/<id>`)) を維持する。
- **機械 router (route-dev-planner)**: 本 §0 の二者択一を構想文から機械判定して dispatch する独立 router skill。判定シグナルと dispatch 契約の正本は `plugin-plans/route-dev-planner/route-dev-planner-contract.md`。本表 (§0) は router の decision table 正本を兼ね、router 不在・低信頼時は本表を人間/orchestrator が読んで従うフォールバックを維持する (router は fail-open せず、曖昧な構想は分割を促す)。

## 1. 使い分け決定表 (repo プロファイル別の既定ポリシー)

repo の `.dev-graph/config.json` → `execution_tracker.mode` の既定を、新規リポジトリ立ち上げ時に本表で決める。
mode: `beads` = 実行タスクは bd のみ / `github` = GitHub Issues のみ / `both` = taskノード単位で tracker_binding を選択。

registration payloadの`tracker_binding="repo-config-default"` sentinelと`binding_intents[graph_node_id]`の解決ownerはC02。intentがexplicit `beads|github|none`ならrepo-config許容範囲と照合し、`auto`はmode=beads|githubだけで同値に解決する。mode=bothのautoは人/AI主体を機械判定できず誤投影になるためfail-closedし、明示intentを要求する。確定enumへ変換してからC11へ渡し、sentinelは永続化しない。

**判定軸は repository の公開範囲ではなく「実行タスクを誰が起票し誰が読むか」である** (2026-08-15 是正)。public/private は課題の authority を決めない。

| repo プロファイル (判定軸 = 起票主体と読み手) | execution_tracker.mode 既定 | GitHub ミラー (beads束縛タスク) |
|---|---|---|
| ソロ + AI エージェント開発 (public/private を問わない) (**既定**) | beads | 不要 (local_only) |
| 人間の協力者/レビュアーへ進捗共有する repo | both | `bd github sync --push-only` で beads→GitHub 一方向ミラー |
| 外部コントリビュータが GitHub 上で起票する OSS repo | github | — (GitHub Issues が最初から正本) |
| 使い捨て実験/プロトタイプ repo | beads | 不要 (完了後は bd compact で要約保持) |

- 本表はソロ AI エージェント開発を主とする運用の既定 (ユーザー委任により確定)。迷った場合は beads を選ぶ (公式 FAQ: AI エージェント実行は bd 優位)。
- **public repository は 3 行目の条件を満たさない** — 公開されていても起票が owner と AI エージェントだけなら 1 行目 (beads / local_only) を選ぶ。public だからという理由だけで `github` を選ぶと、正本が bd にあるまま GitHub 側へ大量の投影が残り、以後は乖離するだけの死蔵 issue になる (HarnessHub 実例: `github_mirror=bd_github_push_only` の放置で open 490 件中 444 件が完了済み/役目終了となり、`HarnessHub-mx65` で `none` へ退役)。public repo で外部からの報告窓口が必要な場合も、mode は beads のままで GitHub Issues を「外部受付と CI 通知の入口」として併用でき、受け付けた報告を bd へ起票し直せばよい。
- **push-only ミラーは逆流路を持たない** — `github_mirror=bd_github_push_only` は bd→GitHub の一方向で、bd 側の close は GitHub へ伝わらない。採用するなら定期 reconcile を運用に組み込むこと。組み込めないなら `none` を選ぶ。乖離は運用の怠慢ではなく設定の構造的帰結として単調増加する。
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
- parity突合対象はstatusと依存edge exact-set (`dev-graph depends_on` ↔ bd `blocks`)。priority/assignee/labelsはbd側自由領域 (= dev-graph側に対応する正本を持たず突合しない) とする。statusまたはedge差分はC03の手動確認フローへ回し、解消までready推薦から除外する。
- **自由領域=突合対象外であって、bridge 迂回の許可ではない**。C10 guard は `bd` の mutation サブコマンドを field で選り分けず全面遮断するため、自由領域 3 field の書込経路も C28 `bd-bridge.py --op update` の `--priority` / `--assignee` / `--labels` に一本化する。guard を field 単位で緩める案は、フラグの並び・短縮形・後続コマンド連結で fail-closed が破れるため採らない (HarnessHub-dc7)。
- `--labels` は `bd update --set-labels` への置換転送のみを受ける (add/remove の部分適用は、同一 run の適用順で最終状態が変わり receipt から再現できないため受けない)。空文字は拒否する: strings フラグの空値が全消去か空 label 1 件かは bd の公開 surface に規定が無く、§7 の「安定 surface のみに依存」に反するため。
- guard の粒度はサブコマンド単位なので `bd update --help` のような read も遮断される。help は `bd help update` を使う (`bd show` / `bd list` / `bd ready` は遮断されない)。
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

## 7. upstream 変動耐性 (beads / strandkanban は日々更新される前提)

beads 本体・strandkanban (旧称 beads-kanban) の更新に設計が引きずられないよう、結合面を最小化し 1 点に集約する。

- **単一チョークポイント (anti-corruption layer)**: bd 呼び出しは bridge (C28 bd-bridge / plugin ルートの project-task-beads.py) のみが行う。skill/hook/agent からの bd 直接呼び出しを設計上禁止し、upstream の CLI 変更は bridge 1 箇所の修正で吸収する。
- **安定 surface のみに依存**: 依存してよいのは(a)`--json`、(b)JSONL export/import、(c)`external_ref`/`metadata`、(d)`bd github sync --push-only`/`bd gate gh:pr`の公開CLI。`bd sql`、`.beads/`直接read/write、strandkanban HTTP APIには依存しない。
- **version pin + 受容 window**: bridge は preflight で `bd version` を検査し、受容 window **>=1.1.0 <2.0.0** 外なら fail-closed で明示エラーを返す (system-dev-planner plan の system-spec-source-pin.json と同型の pin 運用。window 更新は本契約の Edit 差分 + bridge の定数更新で行う)。既知の将来破壊への先回り: bd v2.0 で JSON envelope (`{"schema_version":1,"data":...}`) が既定化予定のため、bridge のパーサは envelope 有無の両形式を受容する。
- **strandkanban は採用した実行看板 (API 非結合は維持)**: ユーザー決定 (2026-07-12) により beads 束縛タスクの標準 live 看板として doublej/strandkanban を採用する (採用決定時の旧称は beads-kanban。2026-07-17 に旧新両 URL の全 ref 一致で同一リポジトリの改名と確認済み。詳細は §9)。ただし結合面は bd CLI の安定 surface に限り、strandkanban の HTTP API・内部 schema・DB ファイルには依存しない (看板 UI の更新・置換・廃止は契約に影響しない)。本契約が保証するのは「bd の issue/依存/状態が正しい」ことまでで、看板は bd を読む表示・手動編集層にすぎず完了 authority を持たない (§3)。
- **drift 検出**: bridge preflight の失敗 (window 外 / --json 形状不一致) は同期を停止して報告する (silent degradation 禁止)。正本 (task-state.json / dev-graph node) は bd 停止中も無傷で、bridge 復旧後の冪等 upsert で追いつける。

## 8. 二層モデル (マクロ/ミクロ棲み分け・feature 完了カスケード) — 正本

dev-graph=マクロ層 (機能単位の保持 + 実行オーケストレーション) と system-dev-planner=ミクロ層 (1 feature→P01..P13 exact 13 executable task specs + 13-node機能内DAG) の棲み分け、およびfeature完了の機械導出をここで正本化する。§0のプランナー選定とは直交する。

### 8.1 二層の責務境界

- **マクロ (dev-graph)**: `artifact_kind=feature` ノードが purpose/goal/scope_in/scope_out/acceptance/architecture_refs を第一級に保持し、機能間依存を feature ノード間の `depends_on` で表す。C14 が自然文の want を feature + architecture + 機能間 depends_on へマクロ分解する (13 タスク仕様書へは踏み込まない)。
- **ミクロ (system-dev-planner)**: ready featureごとに自動/手動で起動し、別phase文書を作らずP01..P13に1件ずつ対応するexact 13 executable task specsを生成する。全taskは共通`parent_feature`/`feature_package_id`を持ちC02がatomic登録する。
- **一方向**: `want → C14 マクロ分解 → ready feature → per-feature planning (自動/手動) → promoted task (parent_feature) → tracker 投影`。feature の生成は dev-graph のみ、program 全体の goal/scope は goal-spec が保持する (feature は機能単位に閉じる)。
- **ゼロ段 fast path**: feature 文脈を持たない単発 task は `parent_feature=null` で features/ を経由せず直接登録できる。マクロ層の ceremony (feature 6 フィールド記入) を trivial case へ課さない。

### 8.2 feature 完了ロールアップ (機械導出・§3 の feature 拡張)

- **完了 authority は機械導出**: `feature.status=done` はregistration receiptがP01..P13 exact 13を証明し、その13 taskが全done、かつP07/P10/P11のacceptance/final-review/evidenceがfeature acceptanceを満たすときだけ成立する。12/14件、phase欠落/重複、余分なcanonical childではdoneにしない。
- **writer と発火**: C26 が §3 の task 完了 transaction 内で「当該 task.parent_feature の配下 task 集合が全 done か」を評価し、成立時に feature completion rollup を restricted patch で導出、C02 単一 writer が features/*.md frontmatter を更新する。task→feature の一方向 (feature を close しても配下 task を一括 close する逆流はしない)。
- **tombstone/close 方向**: active な配下 task を残したままの feature close/tombstone は fail-closed (先に子 task の収束を要求)。C11 が parent_feature 実在検査と併せて計上する。

### 8.3 層分離の依存検査

- taskの`depends_on`先は同一`parent_feature`かつ同一`feature_package_id`内に限り、phase_refの小さいtaskから大きいtaskへの前方edgeだけを許す。機能間依存はfeatureノード間depends_onだけで表す。

### 8.4 sub-feature 非対応 (二層固定)

- feature の親子 (feature.parent_feature) は構造的に不可 (schema が `artifact_kind=feature` で parent_feature=null を強制)。本モデルは意図的に二層固定で、巨大 feature は scope_in/scope_out で機能境界を切り直すか複数 feature へ分けて機能間 depends_on で表現する (epic→story→task の 3 階層は導入しない)。要件が 3 階層を要するようになった場合は本 §8.4 の Edit 差分 + schema 拡張で明示的に解禁する。

### 8.5 feature の tracker 投影 (任意・repo profile 依存)

- **beads profile (既定)**: C28がfeatureをBeads epic、P01..P13 taskをそのchild issueへ投影し、blocks edgeを機能内DAGから写像する。C05も13件中X/Yを表示する。epic closeはexact 13 rollup後の表示projectionでありauthorityではない。
- **github/both profile**: featureをGitHub MilestoneまたはProject feature item、13 taskをIssueへ投影してよい。外部closeは表示であって完了authorityにしない。

### 8.6 architecture_refs の解決境界

- C14 は per-feature planning 起動時に feature.architecture_refs を **解決済み lineage-pinned content** として feature context へ同梱する。system-dev-planner は architecture ノード id を dereference せず、system-spec-harness を独立に再引用もしない (cross-plugin read と二重引用の回避・MS-03/MM-12)。

### 8.7 追加作業

実行中に追加作業を発見しても14件目のcanonical child taskを追加しない。既存phase責務内ならtask specをEditし、独立した価値/責務ならdev-graphへ新しいfeature candidateとして返す。調査メモ等をBeads child issueにしてもcanonical 13-node DAGには含めない。ミクロ正本=`plugin-plans/system-dev-planner/references/feature-execution-package-contract.md`。

## 9. 実行看板 (strandkanban) の採用と C05 静的 render の役割分担 — 正本

ユーザー決定 (2026-07-12) により、beads 束縛タスクの live 実行看板として **doublej/strandkanban** (採用決定時の旧称 beads-kanban。GitHub redirect で旧 URL も到達可) を標準採用する。ただし自動化・完了 authority は §3/§6/§7 のとおり bd CLI + PR merge に置き、看板は表示・手動編集層に限定する (看板は「今どのタスクを触るか」の human live surface、authority ではない)。

### 9.1 採用範囲と前提

- **対象**: `execution_tracker.mode=beads|both` の repo における、beads 束縛タスク (`tracker_binding=beads`) の live 看板。
- **前提 (bd は embedded のままでよい)**: strandkanban 0.5.x は `bd export` / `bd update` / `bd create` 等の安定 CLI surface (§7) で読み書きし、`bd sql` を使わない (v0.5.0 実装確認 2026-07-17)。したがって bd の server モード運用は**不要**で、embedded (`server_mode=false`) のままでよい。旧版が `bd sql --json` で読んでいた時期の「`board=beads-kanban` のとき `server_mode=true` 必須」という repo-config schema の条件付き制約は撤廃済み (歴史的経緯としてここに記録)。
- **起動手順 (npx 直接起動は不可)**: `npx github:doublej/strandkanban <path>` の直接起動は、npm が git 依存の devDependencies (vite / @sveltejs/kit 等) を prune するため v0.5.0 時点で失敗する。正規手順は clone + install: `git clone https://github.com/doublej/strandkanban` → `bun install` (または npm install。better-sqlite3 のビルドに native toolchain 必要) → `bin/strand <対象repoパス>` で起動 (空きポート自動選択・HTTPS 自己署名)。
- **運用注意 (LICENSE)**: strandkanban の上流ライセンスは導入時点で未確認 (LICENSE 無しの場合は既定で全権利留保)。業務/再配布利用の前に上流ライセンスを確認する。dev-graph はソースを同梱・fork せず、外部依存 (交換可能) として扱う。上流廃止時は §9.2 の C05 render または omb-board へ無改修で切替できる。

### 9.2 strandkanban (live 看板) と C05 render-graph-html (静的 render) の役割分担

| 観点 | strandkanban (live 看板) | C05 render-graph-html (静的 render) |
|---|---|---|
| 対象 | beads 束縛 task ノードのみ (bd issue)。board / table / **依存グラフ** / grid の 4 ビュー内蔵 | 6 種 artifact 全グラフ (issues/tasks/specs/architecture/features/docs) |
| 更新 | live (ドラッグ=`bd update --status`) | スナップショット (commit / CI 生成) |
| 依存 | Node 18+/Bun + SvelteKit dev server 常駐 (bd は embedded 可) | ゼロ依存 (単一 HTML/CSS/SVG) |
| 用途 | 人間の実行看板・手動編集・agent pane・優先順位操作・タスク依存 DAG の live 確認 | 機能横断の俯瞰 (仕様・アーキ・feature 含む)・共有・履歴 diff・オフライン閲覧 |
| 完了 authority | 持たない (表示のみ・§3) | 持たない (表示のみ) |

両者は競合せず補完関係。「今どのタスクに着手すべきか」の live 操作とタスク依存 DAG の確認は strandkanban、「機能横断の全体像スナップショット」(仕様→feature→task の上流含む) は C05 が担う。どちらも完了 authority ではなく、authority は PR merged=true (§3)。feature 進捗 (13 件中 X/Y) は両者に現れる (C05=§8.5 集約表示、strandkanban=epic→13 child issue の live 表示)。

### 9.3 自動化は看板を経由しない (bd CLI 直結)

- PR close→task close→ローカル反映の自動化 (§3 カスケード / C25 hook) は bd CLI (C28 bridge) と PR fact を直接叩き、strandkanban を経由しない。看板は結果を表示するだけ。
- したがって看板の起動有無・オフライン・停止は完了収束に影響しない (§7 の drift 耐性と同一設計)。CI/headless 環境で SvelteKit を起動できなくても、bd + C05 render で運用は成立する。

## 10. parity manifest の由来必須化と unmapped 分類 (C28 ready / C16 schedule の停止条件) — 正本

C28 `bd-bridge.py --op ready --parity-manifest` が受け取る manifest は graph の snapshot であり、tracker 側の事実ではない。snapshot に由来がないと、古い snapshot が `edge_parity.confirmed=true` を主張しても下流が stale を機械判定できず、消えた/増えた node を黙って無視した ready-set が出る。以下を必須契約とする。

**manifest スキーマ (必須フィールド)**

| フィールド | 型 | 意味 |
|---|---|---|
| `generated_at` | RFC3339 UTC (`YYYY-MM-DDThh:mm:ssZ`) | snapshot を作った時刻 |
| `source_graph_digest` | `sha256:<64 lowercase hex>` | 素にした graph の canonical digest |
| `nodes[]` | object[] | `graph_node_id` / `bd_issue_id` / `graph_status` / `depends_on` |
| `graph_node_ids[]` | string[] | snapshot 時点で graph に実在した node id の全集合 (`nodes[]` の投影対象に限らない) |

- `source_graph_digest` の算出式は C16 schedule-graph の canonical digest と同一 (`json.dumps(graph, ensure_ascii=False, sort_keys=True, separators=(",", ":"))` の sha256)。整形差で stale 判定が揺れないよう、バイト列 digest ではなく canonical digest を使う。
- 由来欠落・形式違反は C28 が fail-closed で拒否する。素性のない snapshot を流通させない。
- manifest の生成 authority は `scripts/build-parity-manifest.py` の単一経路とする。手書き・部分編集・他 script からの直接書込は認めない。generator は canonical graph だけを読み tracker を読まない。tracker を読んで manifest を作ると、C28 は「自分で作った答え」を採点することになり parity 検査が空虚になる。
- generator は `tracker_binding=beads` かつ `beads_linkage.bd_issue_id` を持つ node を **status で間引かず全件** 投影する。`done`/`closed` を省くと、それらを依存に持つ `active` node が `parity manifest dependency lacks a Beads linkage` で conflicts へ落ち、ready-set が再び空になる。作業候補の絞り込みは C16 `is_schedulable` が graph 側の事実として独立に行う。
- 投影できなかった node は receipt の `unlinked` (起票前 = `beads_linkage` 不在) と `dependency_gaps` (依存先が manifest 外) に理由つきで残す。件数だけで「起票前」と「Beads 未束縛依存」を判別できるようにするため。`BRIDGE_STATUS_MAP` が写せない status は黙って除外せず fail-closed で停止する (除外すると下流で `parity_manifest_missing` という誤った owner の札が付く)。
- manifest は C16 の手順 (`run-dev-graph-schedule`) が `--op ready` の直前に同 generator で作り直す。前回の manifest を使い回すと、その間の graph 変更が stale として停止するだけで ready-set は得られない。
- C28 は検証した由来を receipt の `parity_provenance` に載せ、C16 schedule-graph が graph 実体の canonical digest と突合する。不一致は「stale snapshot」として schedule を停止する (node 単位の parity 再照合は manifest に載った node しか見ないため、snapshot 生成後に追加/削除された node は原理的に捕まらない)。
- 停止時の回復手順は manifest の再生成であり、`source_graph_digest` の書き換えではない。digest だけを現在値へ合わせる修正は stale 検出を恒久的に無効化するため禁止する。

**unmapped 分類 (reason exact-set)**

| reason | 意味 | 対処 owner |
|---|---|---|
| `external_ref_absent` | `bd ready` 候補が dev-graph の `external_ref` を持たない = graph 管理外の bd 課題 | 対処不要 (可視化のみ)。graph 管理下へ移すなら C02 で node 化する |
| `graph_node_missing` | `external_ref` が指す node が `graph_node_ids` に無い = graph から消えた node への宙に浮いた参照 (orphan) | C02 で node を復元するか、失効しているなら C28 `--op close` で bd 側を閉じる。**manifest の再生成では解消しない** |
| `parity_manifest_missing` | `external_ref` が指す node は graph に実在するのに manifest の `nodes[]` に無い = 投影の取りこぼし | `build-parity-manifest.py` で manifest を再生成 / linkage 修復 |
| `dependency_unsatisfied` | C16 schedule の対象かつ schedulable だが、未完了の `depends_on` があるため ready-set から除外された node | `source: "schedule-graph"` と `blocking_depends_on: string[]` を確認し、列挙された上流 node の完了を待つ |

- C28 は理由別件数を `unmapped_summary` として receipt に載せる。件数だけで「管理外が何件・取りこぼしが何件」を判別できるようにするため。
- C16 schedule-graph は C28 の `unmapped` / `conflicts` を自身の `unmapped` へ `source: "bd-bridge"` 付きで引き継ぐ。schedule の判定には使わないが、report から消すことは silent drop にあたるため禁止する。
- C16 schedule-graph は選択範囲内かつ schedulable な node の依存だけを評価し、未充足時は `external_ref`、`reason: "dependency_unsatisfied"`、`blocking_depends_on`、`source: "schedule-graph"` を `unmapped[]` に載せる。選択範囲外・非 schedulable の除外と条件分岐を分離し、依存未充足として誤報告してはならない。

**graph → tracker の片方向走査が作る盲点と、逆方向の全数検査**

C03 sync (`reconcile-github-lifecycle.py`) も C28 manifest 生成 (`build-parity-manifest.py`) も `lint-open-residue.py` も、走査の起点は例外なく graph の node である。したがって **node が graph から消えた瞬間、その node を指していた bd issue は全ての検査の視界から同時に外れる**。issue は `external_ref: dev-graph:<消えた node>` を抱えたまま open で残り、GC/削除のたびに orphan が積み上がる。

- C28 の `graph_node_missing` は、`bd ready` の候補になった orphan だけを可視化する。ready に上がらない orphan (closed 済み・依存で blocked 等) は原理的に捕まらないため、**分類の精緻化だけでは検査として完結しない**。
- 運用時の棚卸しは C28 `--op orphan-audit` が担う。全 bd issue を canonical graph と突合し、参照先の無い issue に `restore_node` / `merge_pending` / `repoint_or_close` の処分 owner を付けて全件返す (read-only)。node を物理削除する前は `--op removal-preflight` で、人が選んだ処分 (`cancel_deletion` / `close_issue_first` / `detach_external_ref_first`) が Beads へ反映済みかを確認する。bridge はどちらでも自動 close / detach をしない。
- 品質ゲートとしての全数突合は `scripts/lint-orphan-external-ref.py` が担う。bd export を起点に graph を引き、参照先が実在しない issue を `closed_residue` (履歴の残骸) / `merge_pending` (他 ref に node 実在) / `node_restorable` (md 実体あり = C02 復元) / `true_orphan` (実体なし = 処分要) へ仕分け、非クローズの残置を fail-closed で遮断する。
- 既知の未処分 orphan は repository 側データの shrink-only baseline (既定は repo-root 相対の `scripts/dev-graph-orphan-baseline.json`、`--baseline` で別 path も指定できる) に凍結し、**新規発生のみ**を違反とする。baseline を増やす変更は「orphan を生み続ける経路を塞ぐ」という目的そのものを無効化するため認めない。処分が済んだ行は lint 出力の `resolved_baseline_entries[]` に現れ、削除を督促する (残すと同じ参照が再発しても違反にならない穴になる)。
- baseline を plugins/ 側へ焼き込まないのは仕組み/ナレッジ境界による。`plugins/dev-graph/` は他 repo へ持ち出せる portable な仕組みであり、特定 repo の node id を抱えると持ち出した先で意味を失う。既知 orphan は repo 固有ナレッジなので repo 側データとして入力で受け渡す。
- 本 lint は bd の live 状態 (Dolt DB) を要求するのでローカル品質ゲートで実行する。`.beads/issues.jsonl` は受動エクスポートであり状態判定の正本ではないため読まない。

