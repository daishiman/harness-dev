# Native Surface Contract (harness-creator)

Claude Code と Codex の公式 native loading surface を authoritative に固定する契約。
`check-native-surface-parity.py` (C02) がこの文書内の canonical JSON block を決定論
parse し、repo 実測との parity・supported/unsupported 分類・trust 前提・artifact digest
freshness を read-only 検査する正本。

Product 間の実行可能な共通意味論は `plugins/harness-creator/native-surfaces.toml`
を単一正本とする。event / matcher / command / owner / `delivery=plugin|project` を
ここから Claude/Codex 各 adapter へ写像し、1 hook に必ず1つの delivery owner だけを
割り当てる。Codexの同一 project layerで `.codex/hooks.json` と inline `[hooks]` を
併用しない。plugin delivery の hook を project layer にも配線しない。

- **source of truth**: 本文の surface/ownership/failure taxonomy は
  `plugin-plans/harness-creator-hook-agents-sync/` の P01 要件・index・goal-spec で
  vetted 済みの事実を写像したもの。推測は載せない (native-first)。
- **checked_at**: 2026-07-13 / **Codex CLI 実測 version**: 0.144.1
- **公式参照**:
  - https://learn.chatgpt.com/docs/build-plugins#plugin-structure
  - https://learn.chatgpt.com/docs/build-plugins#marketplace-metadata
  - https://learn.chatgpt.com/docs/hooks#where-codex-looks-for-hooks

## Native surface 対照表

| capability/surface | Claude Code | Codex | 分類 |
|---|---|---|---|
| repo skill | `.claude/skills` projection | `.agents/skills` または plugin `skills/` | confirmed |
| project hook | `.claude/settings.json` | `.codex/hooks.json` / `.codex/config.toml` | confirmed (project owner) |
| plugin hook | `.claude-plugin/plugin.json` inline | `.codex-plugin/plugin.json` + `hooks/hooks.json` | confirmed (install/enable/trust 必須) |
| plugin discovery | Claude plugin manifest | `.agents/plugins/marketplace.json` の `source.path=./plugins/<slug>` → plugin install | confirmed |
| Claude-style agent | `.claude/agents` | 公式 plugin file mapping 未確認 | unsupported/deferred |
| Claude-style command | `.claude/commands` | 公式 plugin file mapping 未確認 | unsupported/deferred |

推測 `.agents/{agents,commands,hooks}` symlink と推測 TOML hook merge は surface に含めない。
検出したら fail-closed (exit 3)。

Codex plugin の hook 正本は plugin root の `hooks/hooks.json`。manifest の
`hooks` を省略しても Codex がこの default path を検出する。明示する場合は
`./hooks/hooks.json` とし、plugin root 外への path escape は invalid layout とする。
Codex manifest の `skills` は実在する `./skills/` だけを許可する。
`hooks/hooks.json` は `hooks.SessionStart[].hooks[]` の command schema を満たし、
`auto-sync-on-session-start.py` の実行 path は plugin root 内に限る。

repo marketplace は plugin 名に一致する単一 entry が
`source={"source":"local","path":"./plugins/<slug>"}` を持つ。各 entry は
`policy.installation` (`NOT_AVAILABLE|AVAILABLE|INSTALLED_BY_DEFAULT`)、
`policy.authentication` (`ON_INSTALL|ON_USE`)、非空 `category` を必ず持つ。

## State ownership 対照表

| state | owner | 自動書込 |
|---|---|---|
| `.claude` managed projection | repo generator | fingerprint 差分時のみ可 |
| `plugins/harness-creator/native-surfaces.toml` | common hook-delivery + Codex discovery-entry semantic SSOT | build/update 時のみ可 |
| `.codex/hooks.json` | project adapter (foreign/Beads hooks preserve) | common SSOT の project-delivery 差分のみ可 |
| `.codex/config.toml` | project adapter | `[features].hooks=true` の managed key のみ可 |
| `plugins/harness-creator/.codex-plugin` / `hooks` | plugin source | build/update 時のみ可 |
| `.agents/plugins/marketplace.json` | project adapter (foreign entries preserve) | common SSOT に明示された entry のみ可 |
| `.agents/skills/beads` | bd/tool | 禁止 |
| `~/.codex/config.toml` / trust store | user/product | 禁止 |
| worktree lock/log | worktree-local | bounded write 可 |

## Activation / trust 境界

- **Claude projection selection**: repo 内に source が実在し、repo marketplace name と組み合わせた
  exact `plugin@marketplace` identity が project `.claude/settings.json#enabledPlugins` で true の
  plugin だけを managed source とする。slug-only 照合で foreign marketplace の同名 plugin を選択しない。
  repo settings は current hook digest の trust 状態を公開しないため、trust をローカル
  projection selection の検証済み条件とは主張しない。全 `plugins/*` の無条件 apply は禁止する。
- **Codex plugin hook activation**: marketplace registration は discovery であり activation ではない。
  install/enable 後も user hook trust が必要。build は trust を自動承認せず、
  runtime evidence は `pending_user_gate` とする (GATE-CODEX-INSTALL-TRUST)。

## Failure taxonomy

- `skipped_not_installed`: generator 不在**のみ**。
- `warning` / `completion_blocked`: drift / conflict / parse / race / timeout。成功へ畳まない。
- unsupported kind: silent PASS 禁止。parity report に unsupported と明示する。

## Artifact digest freshness

`goal-spec.json` / `component-inventory.json` / `handoff-run-plugin-dev-plan.json` /
`task-graph.json` / `plan-findings.json` の digest parity が崩れたら PASS を拒否する
(stale な component/route 数を根拠に PASS しない)。

## Canonical contract (machine-readable)

C02 は以下の fenced JSON block のみを決定論 parse する (prose は人間向け)。block は
1 個だけ・キー順は下記固定・不在/複数/JSON parse 不能は invalid contract = exit 3。

```json
{
  "schema_version": "1.0",
  "checked_at": "2026-07-13",
  "codex_cli_version": "0.144.1",
  "sources": [
    "https://learn.chatgpt.com/docs/build-plugins#plugin-structure",
    "https://learn.chatgpt.com/docs/build-plugins#marketplace-metadata",
    "https://learn.chatgpt.com/docs/hooks#where-codex-looks-for-hooks"
  ],
  "activation_semantics": {
    "claude_projection_selection": "repo_present_exact_project_identity_enabled",
    "codex_plugin_activation": "install_enable_then_user_hook_trust",
    "codex_trust_mutation": "forbidden_user_gated"
  },
  "confirmed_kinds": ["skill", "hook"],
  "unsupported_kinds": ["agent", "command"],
  "surfaces": [
    {
      "key": "repo_skill",
      "classification": "confirmed",
      "claude": ".claude/skills",
      "codex": ".agents/skills",
      "owner": "repo-generator",
      "write_policy": "fingerprint-diff-only",
      "verification": "repo-owned skill は .agents/skills、plugin-owned skill は plugin skills/ の単一 native owner で読まれ、他 .agents 推測配置を作らない"
    },
    {
      "key": "project_hook",
      "classification": "confirmed",
      "claude": ".claude/settings.json",
      "codex": ".codex/hooks.json|.codex/config.toml",
      "owner": "project",
      "write_policy": "managed-block-only",
      "verification": "project hook は project owner のみ書込"
    },
    {
      "key": "plugin_hook",
      "classification": "confirmed",
      "claude": ".claude-plugin/plugin.json",
      "codex": ".codex-plugin/plugin.json+hooks/hooks.json",
      "owner": "plugin-source",
      "write_policy": "build-or-update-only",
      "trust_required": true,
      "verification": "install/enable/trust 済みのみ発火・未trustで非実行"
    },
    {
      "key": "plugin_discovery",
      "classification": "confirmed",
      "claude": "claude-plugin-manifest",
      "codex": ".agents/plugins/marketplace.json",
      "owner": "repo",
      "write_policy": "explicit-entry-only",
      "verification": "marketplace の named entry が source.path=./plugins/<slug> で plugin root を指す"
    },
    {
      "key": "agent",
      "classification": "unsupported",
      "claude": ".claude/agents",
      "codex": null,
      "owner": "none",
      "write_policy": "none",
      "verification": "silent projection 禁止・parity report に unsupported 明示"
    },
    {
      "key": "command",
      "classification": "unsupported",
      "claude": ".claude/commands",
      "codex": null,
      "owner": "none",
      "write_policy": "none",
      "verification": "silent projection 禁止・parity report に unsupported 明示"
    }
  ],
  "forbidden_codex_surfaces": [
    ".agents/agents",
    ".agents/commands",
    ".agents/hooks",
    "guessed-toml-hook-merge"
  ],
  "state_ownership": [
    {"state": ".claude-managed-projection", "owner": "repo-generator", "auto_write": "fingerprint-diff-only"},
    {"state": "plugins/harness-creator/.codex-plugin", "owner": "plugin-source", "auto_write": "build-or-update-only"},
    {"state": ".agents/plugins/marketplace.json", "owner": "repo", "auto_write": "explicit-entry-only"},
    {"state": ".agents/skills/beads", "owner": "bd-tool", "auto_write": "forbidden"},
    {"state": "~/.codex/config.toml", "owner": "user-product", "auto_write": "forbidden"},
    {"state": "worktree-lock-log", "owner": "worktree-local", "auto_write": "bounded"}
  ],
  "failure_taxonomy": {
    "skipped_not_installed": "generator-absent-only",
    "not_collapsible_to_success": ["drift", "conflict", "parse", "race", "timeout"]
  },
  "digest_inputs": [
    "goal-spec.json",
    "component-inventory.json",
    "handoff-run-plugin-dev-plan.json",
    "task-graph.json",
    "plan-findings.json"
  ]
}
```
