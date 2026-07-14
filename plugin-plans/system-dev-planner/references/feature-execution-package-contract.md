# Feature execution package contract

## 0. 要件レビュー結論

- **真の論点**: 大きなfeatureの設計・順序管理と、そのfeatureを実装する小taskの実行管理が同じノード粒度に混在していたこと。
- **価値性 PASS**: Dev Graphではfeature単位、Beadsではepic→13 childで見られ、次に何を実行するかの認知コストを下げる。
- **実現性 PASS**: 新componentを増やさず、既存schema/template/C02/C11/C14/C26/C28の契約拡張で実現する。
- **整合性 PASS**: feature間edgeとfeature内task edge、feature statusとtask status、macro writerとmicro producerを分離する。
- **運用性 PASS**: exact-set receipt、12/14件negative gate、feature rollup、Beads epic表示、follow-up feature返却でresume/auditできる。
- **強化ループ**: feature scope明確化→13 taskの具体性向上→実行/evidence精度向上→feature acceptance判断精度向上。
- **バランスループ**: 追加作業発見→14件目を禁止→phase Editまたはfeature candidateへ戻す→package肥大化と責務混線を抑制。

## 1. 責務と粒度

system-dev-planner の 1 run は、dev-graph が管理する **1つの feature** だけを実装可能な小タスクへ変換する。runtime output は「13 lifecycle文書 + 可変N task」ではなく、**Phase 1〜13に1件ずつ対応する、ちょうど13個の実行タスク仕様書**である。各ファイルは説明文書ではなく、dev-graph/Beadsへ登録してclaim・実行・完了できるtask nodeそのものとする。

| 層 | 所有者 | 正本 | 行わないこと |
|---|---|---|---|
| マクロ | dev-graph | program goal、feature、architecture、feature間depends_on、feature進捗 | feature内の13 taskを設計しない |
| ミクロ | system-dev-planner | 1 featureの13 phase task specs、feature内task DAG、handoff | featureを新設・分割しない、別feature taskを直接参照しない |
| 実行投影 | dev-graph C02/C28/C12 | task status/linkage/claim/completion receipt | plan内容やfeature scopeを再定義しない |

## 2. 固定出力形状

1 featureにつき次を1 packageとしてatomic promotionする。

- `feature-package.json`: `feature_package_id`、`parent_feature`、feature input digest、13 taskのexact-set。
- `task-specs/phase-01-requirements.md` … `task-specs/phase-13-release-deploy.md`: ちょうど13個。
- `workstream-inventory.json`: 13 task entry。配列順と`phase_ref`はP01…P13のexact order。
- `task-graph.json`: 13 task nodeと機能内depends_on edgeのみ。
- `system-build-handoff.json`、`atomic-promotion-receipt.json`、`dev-graph-registration.json`。

別の「13 lifecycle phase documents」は生成しない。13 task specs自体がlifecycleを実行する。各taskは同じ`feature_package_id`と`parent_feature`を持つ。

## 3. 13 taskの固定写像

| phase_ref | task responsibility |
|---|---|
| P01 | requirements baseline |
| P02 | architecture and workstream design |
| P03 | independent design review |
| P04 | test-first design |
| P05 | implementation |
| P06 | test execution |
| P07 | feature acceptance |
| P08 | refactoring/migration。不要でも`N/A: reason`を成果として実行する |
| P09 | quality/security/operational assurance |
| P10 | independent final review |
| P11 | reproducible evidence |
| P12 | documentation/runbook/handover |
| P13 | release/deploy/close-out。実デプロイ不要でも`N/A: reason`とclose-out receiptを持つ |

P08/P13もnode自体を省略しない。適用外判断を行う小タスクとして残すため、常に13件である。

## 4. 機能内DAG

- baselineはP01→P02→…→P13の前方依存。`task.depends_on`は同じ`parent_feature`かつ同じ`feature_package_id`内だけを参照する。
- 並列化できる場合は直前phaseへの不要なedgeを減らしてよいが、edgeは常に小さいphase_refから大きいphase_refへ向く。循環、後方edge、別feature task参照は禁止する。
- feature間依存はtaskへコピーしない。dev-graphのfeature A→feature Bを正本とし、B packageのP01 ready gateがA feature doneを参照する派生条件だけを持つ。
- 13件未満・14件以上、phase_ref重複/欠落、parent/package不一致はpromotion前にfail-closedする。

## 5. 発見タスクの扱い

実行中に追加作業を見つけても、同一packageへ14件目を追加しない。

- 既存phaseの責務内なら該当task specをEdit更新する。
- 当該featureのacceptance達成に必須だが独立責務なら、dev-graphへfollow-up feature candidateとして返し、マクロ層でscope/dependencyを再判定する。
- 単なる障害・調査メモはBeads child issueにしてよいが、canonical 13-node DAGの一部にはしない。

## 6. Dev Graph・Beadsへの登録

- C02は13 nodeをall-or-none登録し、`expected_count=applied_count=13`、P01..P13 exact-set、共通`parent_feature`/`feature_package_id`をreceiptで証明する。
- Beads profileではfeatureをepic、13 phase taskをそのchild issueとして投影する。task dependencyはbd `blocks`へ写像する。
- GitHub profileではfeatureをMilestoneまたはProject feature item、13 taskをIssueとして投影できる。外部表示は完了authorityではなく、feature完了は13 task全doneから機械導出する。

## 7. 完了条件

featureをdoneへroll upできるのは、登録receiptがexact 13を証明し、そのP01..P13全taskがdoneで、feature acceptanceがP07/P10/P11のevidenceから満たされた場合だけ。子task欠落、余分なcanonical task、未完了phase、acceptance evidence欠落ではfail-closedする。
