> 本ファイルは cloudflare/skills（Apache-2.0）を基に改変しています。詳細は リポジトリルートの ATTRIBUTION.md を参照。

# Skill validation cases

These cases match the assertions in the Turnstile Spin PRD. Run them after editing this skill to confirm an agent loading it can still execute the wizard end-to-end.

## Test 1 — Dummy siteverify returns a structured error

Step 10's `validate.sh` sends a deliberately-invalid token directly to `challenges.cloudflare.com/turnstile/v0/siteverify` using the captured secret. The expected response is `success: false` with `error-codes: ["invalid-input-response"]`. Anything else means the secret is wrong or the widget is misconfigured.

```sh
curl -s -X POST "https://challenges.cloudflare.com/turnstile/v0/siteverify" \
  -H "Content-Type: application/x-www-form-urlencoded" \
  --data-urlencode "secret=${TURNSTILE_SECRET}" \
  --data-urlencode "response=XXXX.DUMMY.TOKEN.XXXX" | \
  jq -e '.success == false and (.["error-codes"] | index("invalid-input-response"))'
```

Expected exit code: 0.

## Test 2 — Hostname configuration without exposing Account ID

```sh
CLOUDFLARE_ACCOUNT_INDEX=1 TURNSTILE_SECRET="${TURNSTILE_SECRET}" \
  bash scripts/validate.sh \
  --account-index 1 \
  --sitekey "${SITEKEY}" \
  --expected-domains example.com
```

Expected exit code: 0 and `hostname_check: "ran"`. The complete Account ID must not appear in stdout, stderr, or shell history.

## Test 3 — Telemetry marker is in every written snippet

After the wizard completes, grep the written files:

```sh
rg -l 'data-action="turnstile-spin-v2"' <(echo "$WRITTEN_FILES")
```

Expected: every written file matches. If a snippet was written without the marker, the wizard skipped the Step 9 contract (or the agent edited the template). Re-run.

## Test 4 — Skill persists through the right ownership path

After Step 11 in an unmanaged repository:

```sh
test -f .claude/skills/turnstile-spin/SKILL.md \
  || test -f .agents/skills/turnstile-spin/SKILL.md \
  || test -f .cursor/rules/turnstile-spin.md \
  || test -f .opencode/skills/turnstile-spin/SKILL.md \
  || test -f .github/copilot/skills/turnstile-spin.md \
  || test -f .windsurf/rules/turnstile-spin.md
```

Expected exit code: 0. In an AIDD-managed repository, do not use this direct-persistence assertion: update `aidd-agent-kit/skills/turnstile-spin/`, run the repository sync, and verify that the managed runtime matches its manifest instead.

## Test 5 — Turnstile token type stays separate from CI/CD

The shared guard must reject account-owned tokens and accept user-owned tokens before any API call.

```sh
bash -c '
  . scripts/account-context.sh
  CLOUDFLARE_API_TOKEN=cfat_example
  ! turnstile_require_user_api_token
  CLOUDFLARE_API_TOKEN=cfut_example
  turnstile_require_user_api_token
'
```

Expected exit code: 0. These are non-secret fixture strings. Production tokens must never be printed or saved.

## Running all cases

```sh
CLOUDFLARE_ACCOUNT_INDEX=1 SITEKEY=... TURNSTILE_SECRET=... CLOUDFLARE_API_TOKEN=... \
  bash tests/run-all.sh
```

(`run-all.sh` is not bundled with this skill; the cases above are intended to be wired into the consuming agent's own test harness, or run by hand after a deploy.)
