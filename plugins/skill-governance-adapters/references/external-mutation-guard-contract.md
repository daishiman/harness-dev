# External mutation guard contract v1

`build-external-mutation-guard.py` is the sole executable receipt flow for artifact-delivery external mutations.

1. `preview` prints the normalized target scope, exact argv, expected diff and side-effect summary before the challenge, then binds all four review fields in a sealed preview receipt without executing the argv.
2. The user submits the printed `CONFIRM EXTERNAL MUTATION <challenge>` line. The registered `UserPromptSubmit` hook runs `hook-confirm` and creates a confirmation receipt bound to that preview. A challenge that matches no live preview creates no receipt and does not block the prompt.
3. `authorize` validates both sealed receipts and their digest binding, then atomically consumes that preview/confirmation pair. Replay and concurrent authorization have exactly one winner.
4. `execute` consumes the authorization once and executes only argv whose canonical digest matches the preview. A successful execution seals a completion receipt for the preview.
5. The registered `PreToolUse(Bash)` hook allows a central guard invocation only when the entire command is exactly one canonical `preview`, `authorize`, or `execute` call. Shell operators, trailing commands, missing/duplicate flags and unknown flags fail closed.
6. The hook blocks recognized direct remote-mutation commands. Once a live preview creates project-local pending guard context, it blocks every other Bash command until the bound flow completes successfully or the preview expires; this includes otherwise-unrecognized mutation programs.

## Intent grants (typed challenge の代替経路)

The typed challenge is one way to prove a human asked for the mutation; it is not the property itself. A natural-language request submitted through the same registered `UserPromptSubmit` event proves the same thing, so `hook-confirm` also seals an `intent` receipt when the prompt matches a declared intent pattern.

- `preview` classifies its argv into an `action_class`. Only `github-pr-write` (`gh pr create|edit|comment|ready`), `github-issue-write` (`gh issue create|edit|comment|close|reopen`) and `beads-issue-write` (`bd create|update|close|reopen|dep add`) are auto-grantable. Everything else — `gh pr merge`, `gh api`, `curl`, campaign sends, Notion publishes, unclassified argv — records `action_class: null` and still requires the typed challenge.
- `authorize-intent` accepts a preview only when its `action_class` is auto-grantable, is covered by the grant's `granted_classes`, and the preview was issued **after** the grant. The grant is single-use: an `intent-claim` write-once file makes replay fail closed.
- Every other property is unchanged. The preview is still printed for review, the executed argv still has to match the preview digest, the authorization is still consumed exactly once, and the completion receipt still records what ran.

## Cancelling a preview

`cancel` seals a `cancellation` receipt for a preview that will not be executed. `_has_pending_guard_context` treats a preview as resolved by either a successful completion or a cancellation, so an abandoned preview no longer blocks every other Bash command until its 15-minute TTL expires.

The exact enforcement scope is `recognized-bash-remote-mutations-and-all-bash-during-pending-guard-context`. Before a preview exists, the classifier is defense in depth rather than a complete shell or Python semantic interpreter: an unknown program cannot be identified as an external mutation from the Bash string alone. Outside Claude Code's registered `PreToolUse(Bash)` event (including direct terminal execution and other tool providers), this hook provides no enforcement. Entrypoints therefore must create the preview before mutation work and route the mutation through `execute`; projections must not claim broader coverage.
