# FEATURE-1 要件定義・readiness・handoff候補

状態: artifact_created。選択前の候補であり、handoffは未発行。今回の独立評価・三gate検証は未実施。

## 対象と入力

対象はFEATURE-1、packageはfeature-package/feat、P01〜P13の13 task。宛先はcapability-build/task-graph build。
固定source_digest: sha256:df0004510031618ff0b0d6f485eb6a9973f84c4e60ec09c51e24e4cf13f89282。

- [feature入力](../features/feature.json)
- [原ゴール](../goal-spec.json)
- [確定仕様入口](../system-spec/index.md)
- [確定状態](../system-spec/spec-state.json)
- [要件原本](../system-spec/requirements.md)
- [architecture](../architecture/system.md)
- [architecture graph](../architecture/graph.json)
- [package](../.dev-graph/plans/generations/feature-package-feat/df0004510031618ff0b0d6f485eb6a9973f84c4e60ec09c51e24e4cf13f89282/feature-package.json)
- [13 phase DAG](../.dev-graph/plans/generations/feature-package-feat/df0004510031618ff0b0d6f485eb6a9973f84c4e60ec09c51e24e4cf13f89282/task-graph.json)
- [C02登録receipt](../.dev-graph/state/registration-receipts/positive.json)
- [graph snapshot入力](../.dev-graph/state/graph.json)

## 要件定義と追跡

Linux/macOS向けPython標準ライブラリのみのローカルCLI。1ファイルpathを受け、成功時はASCII十進整数とLFのみ、exit 0。失敗時はstdout空、stderr説明、exit 2。

|要件|観測可能な契約|source|system task|
|---|---|---|---|
|AC01|空UTF-8入力は0とLF|system-spec/requirements.md AC01|P01/P04/P05/P06/P07|
|AC02|末尾改行あり・なしの2行をともに2と数える|同 AC02|P01/P04/P05/P06/P07|
|AC03|日本語2行をUTF-8 strictで2と数える|同 AC03|P02/P04/P05/P06/P07|
|AC04|LF・CRLF・単独CRをuniversal newlineで扱う|同 AC04|P02/P04/P05/P06/P07|
|AC05|不存在・directory・権限拒否は説明とexit 2、traceback無し|同 AC05|P01/P04/P05/P06/P07|
|AC06|不正UTF-8は説明とexit 2、traceback無し|同 AC06|P01/P04/P05/P06/P07|
|AC07|引数0件・2件以上はstderr usage、exit 2|同 AC07|P01/P04/P05/P06/P07|
|AC08|入力bytes不変、network・DB・認証・外部service無し|同 AC08|P02/P03/P09/P10|
|AC09|行iteratorで逐次処理、カウンタ以外は1行分の追加メモリ|同 AC09|P02/P03/P05/P09/P10|

P08は挙動維持の整理、P11は検証証跡manifest、P12は利用・保守説明、P13はローカルZIP配布と仕様反映を担う。各phaseの正本task文書はpackage内task_spec_pathsから参照する。新しいtask specは生成しない。
stdin・複数ファイル・再帰探索・GUI・HTTP・Windows保証・pip公開・クラウドdeployは対象外。

## readiness matrix（入力値・未検証）

|対象|入力に記録された状態|今回の判定|
|---|---|---|
|FEATURE-1 / architecture-system|confirmed / pass / complete|未検証|
|SYS-P01〜SYS-P13|confirmed / pass / complete|未検証|
|C02 receipt|13件登録、上記source_digest|binding未実施|
|system-dev-planner owner|上流package存在|今回native適用・独立評価待ち|
|C11/C02/system-plan三gate|入力証跡のみ|未実施|

5 artifact kindを横断する確認ではfeature・task・architectureの入力を参照し、issue/specification等の適用有無とC19 lineage closureは選択後の独立監査で確認する。存在しないnodeやlineageを補作しない。

## 条件付きhandoff契約

handoff_countは現時点0。graph snapshot digestはbinding取得待ちであり、source_digestと混同しない。
system-dev-planner:run-system-dev-planのnative適用で既存packageのidempotencyとlineageを維持し、その後requirementsへ戻る。
validate-readiness-binding.pyとguard-requirements-handoff.pyがともにexit 0、同一graph.digest、graph.digest_match=trueの場合のみatomic emitする。
handoffはguard.handoffの全対象、FEATURE-1、package reference、固定source_digest、graph snapshot digest、上記AC01〜AC09を保持する。
incomplete/pending/fail/staleやmissing_sectionsは正規reportの全件をsurfaceし、handoffを保留する。

## 実行境界

この成果物は要件資料のみ。実装source fileを生成しない。入力のsynthetic upstream findingsは今回の独立評価に数えない。外部mutation・plugin installは行わない。
