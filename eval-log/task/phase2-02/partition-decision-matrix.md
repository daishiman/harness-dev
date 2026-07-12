# phase2-02 partition decision matrix

| strategy | selected | cohesion | coupling | migration_cost | rollback_blast_radius | user_value | future_reuse | reason |
|---|---:|---:|---:|---:|---:|---:|---:|---|
| A domain/cohesion | true | 5 | 3 | 3 | 3 | 4 | 5 | config/scripts の実 inventory に合い、責務境界を説明できる |
| B lifecycle/prefix | false | 1 | 2 | 2 | 2 | 2 | 2 | 現 migrate 対象に skills がないため prefix 分類が空振りする |
| C single-runtime-plugin | false | 2 | 5 | 5 | 1 | 3 | 2 | 境界外参照リスクは下げるが rollback blast radius が大きい |

selected: A domain/cohesion
rejected: B lifecycle/prefix, C single-runtime-plugin
