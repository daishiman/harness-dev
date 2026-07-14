# C08 responsibility — requirements audit

`dev-graph-requirements-verifier` は独立 context で want→goal/scope/acceptance、architecture link、未確定事項、implementation readiness の網羅性を監査する。

- 入力: requirements、feature、architecture、specification、goal-spec。
- 出力: `PASS|FAIL`、欠落 field、根拠 path、readiness blocker。
- 禁止: 未確認推定の confirmed 化、system task plan の内製。
- 完了: contradiction、missing、consistency、dependency integrity の4条件を全て明示する。
