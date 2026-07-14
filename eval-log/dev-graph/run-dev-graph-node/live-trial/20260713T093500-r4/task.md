# R4: C02 mixed routing, repeated update, and feature boundary proof

Use `/Users/dm/dev/dev/個人開発/harness/.worktrees/task-20260712-134250-wt-7/eval-log/dev-graph/live-trial-fixtures/r4-node` only. Execute these observable skill boundaries, without direct Python/JQ mutation of `.dev-graph/state/graph.json`:

1. Invoke `Skill({skill:"dev-graph:run-dev-graph-node",args:"add --repo-root <repo> --input <five-artifact-batch>"})`. Create and route five new R4 inputs of kinds issue, task, specification, architecture, and document through C02. Each must get a canonical path/frontmatter/template and C11 must exit 0.
2. Invoke `Skill({skill:"dev-graph:run-dev-graph-node",args:"update --repo-root <repo> --input <same-five-artifact-batch>"})` a second time. Change titles/tags on the same five IDs and prove the same canonical paths/frontmatter identities remain, with no duplicate IDs.
3. Actually attempt a feature artifact through C02 and record its rejection. Then invoke `Skill({skill:"dev-graph:run-dev-graph-decompose",args:"R4 node-boundary feature --repo-root <repo>"})` so any feature creation goes through C14, not C02. Verify the graph remains C11-valid and every feature has an exact-13 package or remains non-published until that contract is met.

Write a machine-readable receipt under `<repo>/eval-log/r4-node-boundary-receipt.json` listing both C02 skill invocations, five stable IDs/paths, the direct-feature rejection, the C14 invocation, C11 exit, and duplicate count. Only if all are real and PASS write `{"status":"PASS","scenario":"node-mixed-routing-repeated-update"}` to `/Users/dm/dev/dev/個人開発/harness/.worktrees/task-20260712-134250-wt-7/eval-log/dev-graph/run-dev-graph-node/live-trial/20260713T093500-r4/out/status.json`; otherwise FAIL. End `DONE: <status>`.
