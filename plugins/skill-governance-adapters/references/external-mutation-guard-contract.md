# External mutation guard contract v1

`build-external-mutation-guard.py` is the sole executable receipt flow for artifact-delivery external mutations.

1. `preview` prints the normalized target scope, exact argv, expected diff and side-effect summary before the challenge, then binds all four review fields in a sealed preview receipt without executing the argv.
2. The user submits the printed `CONFIRM EXTERNAL MUTATION <challenge>` line. The registered `UserPromptSubmit` hook runs `hook-confirm` and creates a confirmation receipt bound to that preview. A challenge that matches no live preview creates no receipt and does not block the prompt.
3. `authorize` validates both sealed receipts and their digest binding, then atomically consumes that preview/confirmation pair. Replay and concurrent authorization have exactly one winner.
4. `execute` consumes the authorization once and executes only argv whose canonical digest matches the preview. A successful execution seals a completion receipt for the preview.
5. The registered `PreToolUse(Bash)` hook allows a central guard invocation only when the entire command is exactly one canonical `preview`, `authorize`, `authorize-intent`, `execute` or `cancel` call of a trusted guard copy. Shell operators, trailing commands, missing/duplicate flags and unknown flags fail closed. The canonical form is one simple command of unquoted words, single-quoted literals and double-quoted strings whose only expansions are `$NAME`/`${NAME}`; unquoted `$NAME` (word splitting and globbing in bash, empty-word elision in zsh), unquoted newlines, carriage returns, redirections (including `|&`, `&>`, `>|`, `<&`), globs, brace expansion, comments, unquoted backslashes, `\$`/`` \` `` inside double quotes, and every other expansion disqualify the call, because the shell would not read it as the same token list.
   - The first word is a bare `python3` (or `python3.X`) looked up through `PATH`; an interpreter path or wrapper such as `env` fails closed.
   - The second word is a literal path: it must not start with `-` (a Python option such as `-c…` or `-X…`), `~` or `=` (shell expansions), and must not contain `$` (the hook cannot see the shell's value). Resolved from the hook payload's `cwd`, its real path must equal one of the trusted copies: the running guard's own plugin `scripts/` or `hooks/` copy, or `plugins/skill-governance-adapters/{scripts,hooks}/build-external-mutation-guard.py` under that `cwd`. Use the absolute path printed by `extract-plugin-root.py skill-governance-adapters`.
   - The basename alone proves nothing. `python3 '-c…;1/build-external-mutation-guard.py'`, `python3 -Xdev/build-external-mutation-guard.py` and a same-named file anywhere else fail closed even when byte-identical, because Python puts the script's directory first on `sys.path`.
6. The hook blocks recognized direct remote-mutation commands. Once a live preview creates project-local pending guard context, it blocks every other Bash command until the bound flow completes successfully, is cancelled, or the preview expires; this includes otherwise-unrecognized mutation programs. A preview retired by a key rotation (see 署名の鍵) is no longer pending.

## 署名の鍵

receipt の封は `.artifact-delivery/external-mutation/.guard-key-local` の 32 byte の鍵で作る HMAC-SHA256 である。鍵は checkout ごとに作る秘密で、`.gitignore` の `.artifact-delivery/external-mutation/.guard-key*` により repo にも plugin の配布物にも載らない。鍵は利用者ごとの directory ではなく project の状態 directory に置く。Codex の workspace-write sandbox は workspace の外へ書けないので、外に置くと Codex から preview を作れないためである。

- 旧名 `.guard-key` の鍵は commit `cf93ab33` で公開 repo に載ったため、誰でもその鍵で封を作れる。guard は旧名を一切読まない。名前を変えたので、公開済みの鍵を信用しないことが読み込み処理の形で決まり、旧ファイルを消し忘れても信用は戻らない。
- 鍵を作れるのは `preview` と意図の付与 (`hook-confirm` が intent receipt を封じるとき) だけである。初回は `mkstemp` で 0600 の一時ファイルに書いて fsync し、`os.link` で置く。同時に作ろうとした process は先に置かれた鍵を読み直すので、鍵は常に 1 つに決まる。
- 鍵を作る直前に、その時点の `preview-*.json` 全部の名前と sha256 を `key-rotation-<id>.json` に記録し、新しい鍵で封じる。この記録は `expires_at == issued_at` で発行するので、許可としては決して通らない。pending の判定は、新しい鍵で検証できない preview のうち、名前と sha256 が退役記録と一致するものだけを飛ばす。記録の後で書き換えた preview や、記録に無い preview は今までどおり Bash を止める。
- 鍵が無いときは、検証できる未解決の preview も存在し得ないので pending ではない。`authorize`・`authorize-intent`・`execute`・`cancel` と確認の受付は鍵を作らず、`guard key is missing` で exit 2 の fail closed になる。直接の remote mutation の遮断は鍵の有無と関係なく効く。

### 移行

更新前の guard (skill-governance-adapters 0.1.17 以前) は、状態 directory があって `.guard-key` を読めないと、すべての Bash を止める。この変更を pull すると git が他の checkout の `.guard-key` を作業ツリーから消すので、古い guard が動いているセッションでは Bash が止まる。

1. pull したら、開いている Claude Code / Codex のセッションを閉じる。新しいセッションの起動時に plugin が更新される。自動更新を切っている場合は、利用者の端末で `claude plugin update skill-governance-adapters@harness-local` を実行する。
2. 古いセッションが止まった場合は、利用者の端末から `git show <pull 前の commit>:.artifact-delivery/external-mutation/.guard-key > .artifact-delivery/external-mutation/.guard-key` で旧鍵を一時的に戻し、上の 1 を行う。新しい guard は旧鍵を読まないので、戻しても信用は広がらない。
3. 更新前に作った未完了の preview は、新しい鍵では確認できない。最初の preview で退役し、Bash を止めなくなる。必要な操作は preview から作り直す。

## 実行元の指定

登録したhook commandで`hook-confirm --runtime codex`と`pretool --runtime codex`を明示した場合だけCodexとして処理する。省略時は既存のClaude動作を維持し、未知のruntimeは拒否する。native hookの原JSONは変換せず、確認・意図receiptの`producer`を署名時にそれぞれ`codex-user-prompt-submit` / `claude-code-user-prompt-submit`として記録する。payloadのruntime自己申告から実行元を決めない。

両ホストのshell hookは`Bash`と`tool_input.command`を使う。Codexでも実際のUserPromptSubmitと信頼済みhookを通す必要があり、controllerが確認receiptを代作してはならない。既存のpreview・nonce・署名・期限・一回性・exact argvによる認可は共通である。Codexのhook信頼は利用者の許可を得て正規の`/hooks`から設定し、未信頼の定義を自動で有効化しない。

## Intent grants (typed challenge の代替経路)

The typed challenge is one way to prove a human asked for the mutation; it is not the property itself. A natural-language request submitted through the same registered `UserPromptSubmit` event proves the same thing, so `hook-confirm` also seals an `intent` receipt when the prompt matches a declared intent pattern.

- `preview` classifies its argv into an `action_class`. Only `github-pr-write` (`gh pr create|edit|comment|ready`), `github-issue-write` (`gh issue create|edit|comment|close|reopen`) and `beads-issue-write` (`bd create|update|close|reopen|dep add`) are auto-grantable. Everything else — `gh pr merge`, `gh api`, `curl`, campaign sends, Notion publishes, unclassified argv — records `action_class: null` and still requires the typed challenge.
- `authorize-intent` accepts a preview only when its `action_class` is auto-grantable, is covered by the grant's `granted_classes`, and the preview was issued **after** the grant. The grant is single-use: an `intent-claim` write-once file makes replay fail closed.
- Every other property is unchanged. The preview is still printed for review, the executed argv still has to match the preview digest, the authorization is still consumed exactly once, and the completion receipt still records what ran.

## Cancelling a preview

`cancel` seals a `cancellation` receipt for a preview that will not be executed. `_has_pending_guard_context` treats a preview as resolved by either a successful completion or a cancellation, so an abandoned preview no longer blocks every other Bash command until its 15-minute TTL expires.

The exact enforcement scope is `recognized-bash-remote-mutations-and-all-bash-during-pending-guard-context`. Before a preview exists, the classifier is defense in depth rather than a complete shell or Python semantic interpreter: an unknown program cannot be identified as an external mutation from the Bash string alone. Outside Claude Code's registered `PreToolUse(Bash)` event (including direct terminal execution and other tool providers), this hook provides no enforcement. The project's guard copy is trusted on the same `cwd` basis as the pending context; edits made to it through non-Bash tools are outside this hook's scope. Entrypoints therefore must create the preview before mutation work and route the mutation through `execute`; projections must not claim broader coverage.
