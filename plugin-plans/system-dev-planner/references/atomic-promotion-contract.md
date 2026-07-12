# Atomic promotion contract

## Staging

C01/C04 は caller repository の config が示す `.dev-graph/staging/<run_id>/` だけへ 13 phase、N task specs、workstream inventory、task graph、system-build handoff draft を生成する。各ファイルの SHA-256 と canonical manifest digest を `staging-manifest.json` に記録する。

## Promotion gates

次を全て満たさない限り C11 は exit 2 で停止する。

1. C08 が `implementation_readiness=complete`。
2. C12 (`validate-system-plan.py`) が実行する deterministic validation (schema 準拠/DAG 非循環/placeholder 残存/未解決参照) が全 PASS し、validation report を判定入力として提出している。
3. C02/C05 の独立4条件評価が全 PASS。
4. evaluator が記録した `evaluated_digest` と staging canonical digest が一致する。
5. repo identity と全 realpath containment が staging 作成時の pin と一致する。
6. published destination が別 filesystem でなく、atomic rename が利用可能。

## Commit point

同じ repo filesystem 内の一時名へ fsync 済み成果物を置き、published generation directory へ rename する。その後 `promoted_at` RFC3339 timestampを含むimmutable receiptを書き、`current.json` pointerをatomic replaceする。失敗時は旧 current を維持し、partial generation を dev-graph へ渡さない。

## Registration

promotion receipt の `published_digest` と `dev-graph-registration.json` の `source_digest` は同一でなければならない。dev-graph は receipt 後の task specs だけを `tasks/` graph node として登録する。登録 request は repo-relative `file_path`、stable `graph_node_id`、depends_on、resource_scope、acceptance、verification、source_lineage を持つ。

登録はplan内のN taskを1 batchとして扱い、全nodeのschema/path/dependency/tracker bindingを先に検証してからC02の単一transactionでall-or-none commitする。成功時は`dev-graph-registration-receipt.json`へ`expected_count=applied_count=N`、正確な`registered_node_ids`、`source_digest`、commit後`graph_revision`を記録する。1件でも失敗した場合は`status=aborted, applied_count=0`とし、promotion済みgenerationは保持するがL4 handoffを出さない。再実行はper-node `graph_node_id+source_lineage.source_digest`とbatch `source_digest`で冪等でなければならない。
