> 本ファイルは cloudflare/skills（Apache-2.0）を基に改変しています。詳細は リポジトリルートの ATTRIBUTION.md を参照。

# turnstile-spin（Skill）

Cloudflare Turnstileをend-to-endで設定するSkill。Turnstile追加、CAPTCHA設定、formのbot対策を依頼されたときにloadする。

Turnstileの製品仕様と中核フローは[`developers.cloudflare.com/turnstile/spin`](https://developers.cloudflare.com/turnstile/spin/)を参照する。このbundleは、その中核フローへ日本語案内とAIDD固有のrepository所有権・秘密値・Account ID・package manager規律を重ねている。

Token種別はCloudflare公式の[Account API Token互換表](https://developers.cloudflare.com/fundamentals/api/get-started/account-owned-tokens/)を正本とする。Turnstileは現時点でAccount API Token非対応のため、widget管理には対象Accountだけへ`Account.Turnstile:Edit`を付けたuser-owned API tokenを使う。Workers/D1/R2のCI/CD用account-owned tokenとは共有しない。

## 構成

| File | 用途 |
|------|------|
| `SKILL.md` | agentが実行するmain wizard |
| `scripts/account-context.sh` | Account候補番号を完全なIDを表示せずprocess内で解決する共通helper |
| `scripts/auth-probe.sh` | Turnstile専用User API Tokenの種別・scopeを確認し、Account候補をマスク表示する |
| `scripts/widget-create.sh` | Cloudflare APIでTurnstile widgetを作成する |
| `scripts/fetch-secret.sh` | 既存widgetのsecretを取得するrecovery flow |
| `scripts/validate.sh` | wizard最後のdummy-siteverifyとhostname確認 |
| `scripts/persist-skill.sh` | 非管理repositoryだけへinstallし、AIDD管理runtimeを拒否する |
| `references/vanilla-html.md` | static / vanilla HTML project用code snippet |
| `references/nextjs-app.md` | Next.js App Router用code snippet |
| `references/nextjs-pages.md` | Next.js Pages Router用code snippet |
| `references/astro.md` | Astro用code snippet |
| `references/sveltekit.md` | SvelteKit用code snippet |
| `references/hugo.md` | Hugo用code snippet |
| `tests/validation.md` | PRDのassertionに対応するvalidation cases |

## Agentによるloadと保存

`github.com/cloudflare/skills`のbundleをloadするagentでは自動的に検出される。

次のcommandを使う前に、適用される`AGENTS.md`を必ず読む。AIDD管理repositoryでは`.claude/skills`と`.agents/skills`は生成runtimeであり、downloadやlinkの直接targetにしない。`AGENTS.md`で宣言された編集原本（このbundleでは`aidd-agent-kit/skills/turnstile-spin/`）を更新し、repositoryのsyncとverify commandを実行する。upstream版を比較する場合はtemporary directoryへ取得してdiffを確認する。

authoring ruleがない非管理repositoryに限り、repository-localへ直接installできる。

```sh
# Claude Code
mkdir -p .claude/skills/turnstile-spin && \
  curl -sSL https://developers.cloudflare.com/turnstile/spin.md \
  -o .claude/skills/turnstile-spin/SKILL.md

# Codex
mkdir -p .agents/skills/turnstile-spin && \
  curl -sSL https://developers.cloudflare.com/turnstile/spin.md \
  -o .agents/skills/turnstile-spin/SKILL.md

# またはskills bundle全体をinstallし、両clientからlinkする
git clone https://github.com/cloudflare/skills ~/.config/cloudflare-skills
ln -s ~/.config/cloudflare-skills/skills/turnstile-spin ~/.claude/skills/turnstile-spin
ln -s ~/.config/cloudflare-skills/skills/turnstile-spin ~/.agents/skills/turnstile-spin
```

他clientでは、そのclientが定めるSkill discovery locationを使う。repository所有権を先に判定し、直接persistするのは非管理repositoryだけとする。詳細は[`SKILL.md`](./SKILL.md)のStep 11を参照。

## Upstreamとの同期

upstreamの正本は`cloudflare-docs` repositoryの`src/content/docs/turnstile/spin.mdx`。製品仕様、API contract、公式連携手順はupstreamを優先する。

ただし、このbundleの日本語control planeと次のAIDD safety overlayはlocal正本であり、upstream取得で削除・上書きしない。

- `AGENTS.md`に従う編集原本 → sync → verify
- Token、widget secret、raw Account IDをchat/finalへ出さない
- Account候補はname、番号、masked IDだけを表示する
- 既存lockfileからpackage managerを選び、global installを勧めない
- Turnstile専用user-owned tokenをCI/CD用account-owned tokenと分離する

同期時はupstreamをtemporary directoryへ取得し、製品仕様の差分とlocal overlayを分けてreviewしてから編集原本へ適用する。AIDD管理runtimeへupstreamを直接fetchしない。

## 関連資料

- [Canonical docs page](https://developers.cloudflare.com/turnstile/spin/)
- [Account API Token compatibility matrix](https://developers.cloudflare.com/fundamentals/api/get-started/account-owned-tokens/) — Turnstile対応可否の正本
- [API token permissions](https://developers.cloudflare.com/fundamentals/api/reference/permissions/) — `Turnstile Edit`権限の正本
- [`cloudflare/skills`](https://github.com/cloudflare/skills) — Cloudflare agent skillsのroot index
- [Turnstile server-side validation](https://developers.cloudflare.com/turnstile/get-started/server-side-validation/) — 正式なsiteverify reference
