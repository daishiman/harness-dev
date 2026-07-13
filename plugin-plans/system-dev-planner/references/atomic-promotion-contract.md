# Atomic promotion contract

## Staging

C01/C04 はcaller repositoryの`.dev-graph/staging/<run_id>/`だけへ、1 featureの`feature-package.json`、P01..P13に対応するexact 13 task specs、13-entry workstream inventory、13-node task graph、system-build handoff draftを生成する。別の13 phase文書セットや可変N taskは生成しない。各ファイルのSHA-256とcanonical manifest digestを`staging-manifest.json`に記録する。

## Promotion gates

次を全て満たさない限り C11 は exit 2 で停止する。

1. C08 が `implementation_readiness=complete`。
2. C12 (`validate-system-plan.py`) が実行する deterministic validation (schema 準拠/DAG 非循環/placeholder 残存/未解決参照) が全 PASS し、validation report を判定入力として提出している。
3. C02/C05 の独立4条件評価が全 PASS。
4. evaluator が記録した `evaluated_digest` と staging canonical digest が一致する。
5. repo identity と全 realpath containment が staging 作成時の pin と一致する。
6. published destination が別 filesystem でなく、atomic rename が利用可能。

## Commit point

同じ repo filesystem 内の staging generation に、`promoted_at` RFC3339 timestampを含む immutable receiptと registration/findings を書き、全ファイルと directory entry を fsync する。その後 published generation directory へ1回だけ atomic rename し、`current.json` pointerをatomic replaceする。rename 前の失敗では旧 current/published を維持し、rename 後の pointer 更新失敗は immutable receipt と promotion intent を照合して冪等回復する。partial generation は dev-graph へ渡さない。

## Registration

promotion receiptの`published_digest`とregistrationの`source_digest`は同一でなければならない。dev-graphはreceipt後のexact 13 task specsだけを登録する。requestは共通`parent_feature`/`feature_package_id`とP01..P13 exact-setを持つ。

登録は13 taskを1 batchとして扱い、schema/path、P01..P13 exact-set、同一parent/package、機能内dependency、tracker bindingを先に検証してからC02の単一transactionでall-or-none commitする。成功時は`registered_at`、`expected_count=applied_count=13`、正確な`node_ids`/`phase_refs`、`source_digest`、`graph_revision_before`・`graph_revision_after`・`graph_digest_after`をreceiptへ記録する。1件でも失敗した場合は0件commitとし、成功receiptを発行しない。
