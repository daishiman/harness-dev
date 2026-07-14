# R4: C19 qualified dependency flow proof

Use `/Users/dm/dev/dev/個人開発/harness/.worktrees/task-20260712-134250-wt-7/eval-log/dev-graph/live-trial-fixtures/r4-system-spec`, whose final spec-state and official-reference fixture exist but generated Markdown was removed. Invoke `Skill({skill:"dev-graph:run-dev-graph-system-spec",args:"--repo-root <repo> --resume"})`.

The following four qualified Skill calls must each load successfully and execute their owned flow in order; any `Unknown skill` or direct-script fallback is an immediate FAIL:

1. `system-spec-harness:run-system-spec-elicit` in resume mode to validate/complete the final matrix.
2. `system-spec-harness:run-system-spec-doc-fetch` to consume and validate the provided official reference records without inventing sources.
3. `system-spec-harness:run-system-spec-compile` to regenerate the removed system-spec Markdown set.
4. `system-spec-harness:assign-system-spec-completeness-evaluator` in forked context to produce a current PASS report.

Then invoke qualified `dev-graph:run-dev-graph-node` for the C02 import/update. Require coverage, source-citation, completeness, and C11 gates all exit 0; imported specification/architecture nodes must have complete source_lineage, confirmed evidence, evaluator evidence and readiness. Persist an import receipt in the fixture.

Only if all qualified Skill tool results succeeded and all gates pass, write `{"status":"PASS","scenario":"system-spec-qualified-lineage"}` to `/Users/dm/dev/dev/個人開発/harness/.worktrees/task-20260712-134250-wt-7/eval-log/dev-graph/run-dev-graph-system-spec/live-trial/20260713T093500-r4/out/status.json`; otherwise FAIL. End `DONE: <status>`.
