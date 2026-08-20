# External mutation guard contract v1

`build-external-mutation-guard.py` is the sole executable receipt flow for artifact-delivery external mutations.

1. `preview` prints the normalized target scope, exact argv, expected diff and side-effect summary before the challenge, then binds all four review fields in a sealed preview receipt without executing the argv.
2. The user submits the printed `CONFIRM EXTERNAL MUTATION <challenge>` line. The registered `UserPromptSubmit` hook runs `hook-confirm` and creates a confirmation receipt bound to that preview.
3. `authorize` validates both sealed receipts and their digest binding, then atomically consumes that preview/confirmation pair. Replay and concurrent authorization have exactly one winner.
4. `execute` consumes the authorization once and executes only argv whose canonical digest matches the preview. A successful execution seals a completion receipt for the preview.
5. The registered `PreToolUse(Bash)` hook allows a central guard invocation only when the entire command is exactly one canonical `preview`, `authorize`, or `execute` call. Shell operators, trailing commands, missing/duplicate flags and unknown flags fail closed.
6. The hook blocks recognized direct remote-mutation commands. Once a live preview creates project-local pending guard context, it blocks every other Bash command until the bound flow completes successfully or the preview expires; this includes otherwise-unrecognized mutation programs.

The exact enforcement scope is `recognized-bash-remote-mutations-and-all-bash-during-pending-guard-context`. Before a preview exists, the classifier is defense in depth rather than a complete shell or Python semantic interpreter: an unknown program cannot be identified as an external mutation from the Bash string alone. Outside Claude Code's registered `PreToolUse(Bash)` event (including direct terminal execution and other tool providers), this hook provides no enforcement. Entrypoints therefore must create the preview before mutation work and route the mutation through `execute`; projections must not claim broader coverage.
