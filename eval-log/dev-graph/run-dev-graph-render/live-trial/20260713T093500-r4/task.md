# R4: C05 exact-13 receipt plus browser-render proof

Use `/Users/dm/dev/dev/個人開発/harness/.worktrees/task-20260712-134250-wt-7/eval-log/dev-graph/live-trial-fixtures/r4-render`.

1. Invoke `Skill({skill:"dev-graph:run-dev-graph-node",args:"register-package --repo-root <repo> --package system-plan/LT-FEATURE-001/feature-package.json"})` and use the pinned plugins' real `register-package.py` with the provided `dev-graph-registration.json`. It must write the immutable `dev-graph-registration-receipt.json` and atomically apply exact 13/13 tasks; C11 must exit 0.
2. Invoke `Skill({skill:"dev-graph:run-dev-graph-render",args:"--repo-root <repo>"})` and generate a self-contained HTML with no external script/link. The feature progress and displayed source digest/count must match the immutable registration receipt.
3. Actually render the HTML through macOS Quick Look WebKit using `qlmanage -t -s 1400 -o <repo>/render-proof <html>` (parsing HTML alone is failure). Verify the resulting PNG signature, nonzero dimensions/bytes, and record its SHA-256 in `<repo>/render-proof/browser-render-receipt.json`.

Only if registration=13/13, C11=0, HTML/receipt values agree, and browser PNG exists, write `{"status":"PASS","scenario":"render-exact13-browser-proof"}` to `/Users/dm/dev/dev/個人開発/harness/.worktrees/task-20260712-134250-wt-7/eval-log/dev-graph/run-dev-graph-render/live-trial/20260713T093500-r4/out/status.json`; otherwise FAIL. End `DONE: <status>`.
