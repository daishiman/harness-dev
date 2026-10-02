# AI開発エージェントキット

**バージョン 1.11.0**

Claude Code と OpenAI Codex の両方に、「プロの開発ノウハウ集(共通スキル20個)」と「開発を自動で進める司令塔(app-orchestrator)」を同時に追加するキットです。

> **このファイルはエージェント・開発者向けです。** キットを受け取って使い始める方は [`START-HERE.md`](START-HERE.md) を読んでください(3手順で終わります)。手順の詳細とつまずいたときの対処は `manual-mac.md` / `manual-windows.md` にあります。

## 何ができるか

```text
Claude Code: /build-app 社員の勤怠を管理するアプリを作って
OpenAI Codex: $build-app 社員の勤怠を管理するアプリを作って
```

まず業務に必要な機能一式がそろった「最初の1本」を最短で公開し、その後は `/improve-app`(`$improve-app`)で1機能ずつ育て、失敗したら `/undo-app`(`$undo-app`)で1つ前の状態へ戻します。要件の整理からデザイン・開発・公開・品質チェックまでを、決められた手順で進めます。

## 導入の全体像

- **インストール先はユーザー全体(グローバル)** です。ホームフォルダ(Mac: `~/`、Windows: `C:\Users\(あなたの名前)\`)に入り、どのフォルダで作業していても使えます。特定のプロジェクトの中には何も置きません。
- **インストールは2本立て** です。`install-*` はキット本体(スキル・エージェント・コマンド)を配るだけで、Cloudflare との連携(MCP)は `setup-env-*` が登録します。`install-*` は `setup-env-*` が未実行なら、その場で続けて実行するか尋ねます。
- 状態は3段階です。`install-*` 完了で「kit installed」、`setup-env-*` で user scope 登録と docs 接続まで済むと「MCP registered」(ここが基本セットアップ完了)、変更系 MCP を実際に使う時だけ対象1件が「auth_pending」→「ready」になります。

### 事前に必要なもの

- **Claude Code または OpenAI Codex** がインストール済みで、サインインが完了していること(インストーラーは両方の設定を同時に用意します)
- **Node.js 22 以上と pnpm**。無くてもキットのインストールはできますが、アプリ開発を始める前に必要です。`setup-env-*` が両方入れます(パッケージマネージャは pnpm に統一、npm は使いません)
- **GitHub CLI (`gh`) と GitHub へのサインイン**(`gh auth login`)。プルリクエストの作成・確認・反映に使います。GitHub MCP は必須ではありません

| お使いのPC | インストーラー | 開発環境セットアップ | マニュアル |
|---|---|---|---|
| Mac | `install-mac.command` | `setup-env-mac.command` | `manual-mac.md` / `manual-mac.html` |
| Windows | `install-windows.bat` | `setup-env-windows.bat` | `manual-windows.md` / `manual-windows.html` |

## Cloudflare 連携(MCP)

`setup-env-*` は Claude Code と Codex の両方へ次の3つを **user scope(ユーザー全体)** で登録します。この配置 scope は「どこから MCP を使えるか」の設定で、Cloudflare OAuth の認可 scope とは別です。

| 名前 | URL | 用途 |
|---|---|---|
| `cloudflare-bindings` | `https://bindings.mcp.cloudflare.com/mcp` | Workers・D1・R2 などのリソース操作 |
| `cloudflare-docs` | `https://docs.mcp.cloudflare.com/mcp` | 公式ドキュメントの検索(認証不要) |
| `cloudflare-observability` | `https://observability.mcp.cloudflare.com/mcp` | 公開後のログ・エラーの確認 |

MCP と wrangler CLI のどちらを使うか、`.mcp.json` の残骸や `[Conflicting scopes]` をどう直すかの裁定は [`skills/wrangler/references/mcp-vs-cli-routing.md`](skills/wrangler/references/mcp-vs-cli-routing.md) 冒頭の5行が唯一の正本です。要約すると、調査と仕様確認は MCP、deploy・secret・migration は CLI 既定、MCP の user scope 登録はエージェントと `setup-env-*` が代行し、OAuth 認可と git 未追跡の `.mcp.json` の修正だけ本人が行います。変更系 MCP は必要になったときに対象1件だけ認証します。

## Codex の配置と scope の役割

Codex への配置は、スキル(`SKILL.md`)が `.agents/skills/<名前>/`、custom agent(`.toml`)が `.codex/agents/` の2種類だけです。探索範囲・書込 scope・編集原本・TOML/Hooks の方針・反映手順は [`CODEX-PLACEMENT.md`](CODEX-PLACEMENT.md) が正本です。

**scope の役割裁定:** 配布物は user scope(グローバル)一本です。このキット開発リポジトリ自身の project scope 反映(`.claude` / `.agents` / `.codex`)は CI と `sync-project-*` の検査対象であり、開発機で user scope と併存すると `doctor-codex-layout.sh` が内容差を警告するのは想定内です(project scope を CI の一時 fixture に降格する案は次 PR で検討)。利用者が `sync-project-*` を実行する必要はありません。

配置の診断は `./aidd-agent-kit/doctor-codex-layout.sh` で行えます。読み取り専用で、同内容の二重導入は警告、内容差や project `.codex/skills` の誤配置は NG、CI では `--strict` で重複警告も NG になります。利用者所有のファイルは自動削除しません。

**縮小時に消してはならない規則**は [`INVARIANTS.md`](INVARIANTS.md) に INV-id で列挙しています。削減 PR は参照元から INV-id が消えていないことを確認してからマージします。

## インストール先

| 対象 | Mac | Windows |
|---|---|---|
| Claude Code | `~/.claude/` | `C:\Users\(あなたの名前)\.claude\` |
| Codex のスキル | `~/.agents/skills/` | `C:\Users\(あなたの名前)\.agents\skills\` |
| Codex のcustom agent・任意の旧互換prompt | `~/.codex/` | `C:\Users\(あなたの名前)\.codex\` |

```text
.claude/            skills/(共通スキル) agents/app-orchestrator.md commands/(4コマンド)
.agents/skills/     (共通スキル) app-orchestrator/ build-app/ improve-app/ undo-app/ setup-cicd/
.codex/             agents/app-orchestrator.toml  prompts/(--legacy-prompts 指定時だけ)
```

`aidd-agent-kit.LICENSE` / `aidd-agent-kit.NOTICE` / `aidd-agent-kit.ATTRIBUTION.md` は `.claude/`・`.codex/` の直下と `.agents/skills/` の直下へ配置します(Apache License 2.0 の 4(a)。3つは別ツリーなのでそれぞれに添えます)。

- 既存の同名項目だけを `backup-YYYYMMDD-HHMMSS/` へ退避してから上書きし、このキットが入れていないスキルや設定には触れません。
- 書き込み先がシンボリックリンクの場合、インストーラーは処理を中断します(リンク先の無関係なフォルダを書き換えないための安全装置)。案内に従ってリンクを一時退避してから再実行してください。

## 収録内容

### エージェント(司令塔) — 1個

| 名前 | 役割 |
|---|---|
| app-orchestrator | 要件整理→デザイン→開発→公開→品質チェックを順番に進める司令塔 |

Codex では `.codex/agents/app-orchestrator.toml` を custom agent として、同じ scope の `$app-orchestrator` を内部実行用 Skill として導入します。利用者の入口は `$build-app` / `$improve-app` です。`$app-orchestrator` は一般のアプリ依頼から暗黙起動しません。

### コマンドワークフロー — 4個

| Claude Code / Codex | 役割 |
|---|---|
| `/build-app` / `$build-app` | 新しいアプリを最初から公開まで作る |
| `/improve-app` / `$improve-app` | 公開済みのアプリに機能追加・改善を1件ずつ行う |
| `/undo-app` / `$undo-app` | 直前の変更を取り消して、アプリを1つ前の状態に戻す |
| `/setup-cicd` / `$setup-cicd` | Workers Buildsまたは外部CI/CDを選び、自動チェックと自動公開を導入する |

Claude Code の custom `/command` に対応する Codex の標準機能は `$skill` です。`AGENTS.md` は毎回読む常設指示で、`$skill` や custom agent の代替ではありません。Codex custom prompts(`/prompts:build-app` など)は公式に非推奨のため標準では生成せず、移行期間だけ `--legacy-prompts` を付けて導入します。

```text
Mac:     bash install-mac.command --legacy-prompts
Windows: install-windows.bat --legacy-prompts
```

### 共通スキル(開発ノウハウ集) — 20個

スキルは **エージェントが必要な場面で自動的に読む知識** です。利用者が名前を指定して呼ぶ必要はありません。各スキルの `description` が起動条件の正本で、下表の「どういう時に使うか」はその要約です。

読まれ方は3種類あります。**「盛りすぎ」に見えても、実際に毎回読まれるのは「常時」だけです。**

| 印 | 読まれ方 |
|---|---|
| **常時** | その工程に入ったら必ず読む。利用者が話題に出さなくても適用される |
| **条件** | 要件に該当する要素(ログイン・メール送信・リアルタイム等)があるときだけ読む |
| **任意** | 既定では読まない。要件で明示された場合か、app-orchestrator が指示した場合だけ読む |

#### 1. 進め方の土台 — 3個

| スキル | どういう時に使うか | 読まれ方 |
|---|---|---|
| app-excellence | 「アプリを作って」「要件定義」「仕様を決めたい」「リリースしていいか判断して」。要件→設計→実装→品質ゲート→リリース判定の手順ゲート全体を仕切る | 常時 |
| mvp-first-development | 「とりあえず形にして」「まず動くものを」「社内ツールを早く」。非エンジニア相手の会話の型、決めること/決めなくていいことの仕分け、残課題の管理 | 常時(新規の要件定義時に app-excellence とセット) |
| solo-git-flow | 「ブランチ切って」「コミットして」「PR出して」「Issue立てて」「前の状態に戻して」。`gh` CLI で Issue→PR→リリースタグ→取り消しまで一貫管理 | 常時(変更管理) |

#### 2. 画面・体験の設計 — 3個

順番が決まっています。**【入口】design-judgment →【実体】ux-design →【素材】jp-web-design** です。

| スキル | どういう時に使うか | 読まれ方 |
|---|---|---|
| design-judgment | 【入口】「AIっぽい」「テンプレート感」「もっと洗練させたい」「管理画面をレビューして」。UI の新規設計・リニューアル・レビューの着手時に最初に開き、次にどれを読むか決める | 常時(UI 着手時) |
| ux-design | 【実体】機能設計・画面フロー・フォーム設計・UX改善。業務構造の診断(中心対象・最頻操作・装飾除去テスト)からエラー回復・下書き保存・情報設計・検収まで | 条件(画面がある案件) |
| jp-web-design | 【素材】色(平賀カラー既定・ライトのみ / 明示指定時のみPop)、旧配色の自動移行、タイポと数値表記、レスポンシブ4段、部品の HTML/CSS、モーション、a11y。実装時と見た目のレビュー時 | 条件(同上) |

#### 3. 実装の基盤(Cloudflare) — 4個

| スキル | どういう時に使うか | 読まれ方 |
|---|---|---|
| cloudflare | 製品選択のルーター。Workers / KV / D1 / R2 / Workers AI などどれを使うか未確定なとき、対象 Account の確定が要るとき | 条件 |
| wrangler | `wrangler` コマンドを実行する前に構文と安全規則を確認する。MCP と CLI の使い分けの正本もここ | 条件(Workers 案件では実質常時) |
| workers-best-practices | Worker のコードを書く・レビューする。streaming、floating promise、global state、secrets、bindings、observability の anti-pattern 検査 | 条件 |
| durable-objects | チャット・マルチプレイ・予約など、状態を持つリアルタイム機能 | 条件 |

#### 4. 機能の追加 — 4個

| スキル | どういう時に使うか | 読まれ方 |
|---|---|---|
| better-auth-google-gate | 「ログイン機能」「Googleでログイン」「社員だけに限定」「権限管理」。遮断だけなら Cloudflare Access、アプリ内 identity/role/session が要るなら Better Auth という決定表の正本 | 条件(ログイン要件があれば必ず) |
| cloudflare-email-service | メールの送受信。到達性、SPF/DKIM/DMARC、Email Routing、wrangler の email 設定 | 条件 |
| turnstile-spin | 問い合わせフォームのボット対策。widget 作成からサーバー側 siteverify の接続まで | 条件 |
| llm-api-integration | 「AIで読み取り」「PDFから抽出」「自動分類」「チャットボット」。APIキー管理、コスト最適化、利用量ダッシュボードの設計 | 任意(AI 要件が明示されたとき) |

#### 5. 公開と自動化 — 2個

| スキル | どういう時に使うか | 読まれ方 |
|---|---|---|
| cloudflare-secure-deploy | 「デプロイして」「公開して」「本番反映」「マイグレーション適用」。D1 の移行順序を含む公開手順の正本 | 常時(公開先が Workers なら) |
| ci-cd-pipeline | 「自動デプロイしたい」「マージしたら勝手に公開されるように」「CIが落ちた」。Workers Builds か外部 CI/CD を1経路だけ選ぶ。手動デプロイの繰り返しを見つけたら依頼が無くても導入可否を判断する | 条件 |

#### 6. 品質と検査 — 4個

| スキル | どういう時に使うか | 読まれ方 |
|---|---|---|
| testing-excellence | 「テストして」「動作確認して」「TDDで進めて」。v1 までは「壊れたら困る順」の最小テスト、v1 到達後の固定化段階では TDD サイクル | 常時(段階で強度が変わる) |
| launch-security | 「セキュリティチェックして」「リリースしていい?」「無料枠に収めたい」「重い」。認証・入力・API・決済・機密データを触った直後とデプロイ前は、明示が無くても適用される | 常時(公開前) |
| web-perf | 表示速度の監査。Chrome DevTools MCP で Core Web Vitals(LCP / INP / CLS)を計測し、render-blocking などを特定 | 任意 |
| llm-cost-simulator | 「このアプリの API コストはいくら」。コードから LLM 呼び出しを洗い出し、件数・DAU 規模で試算してレポートと計算機を出す | 任意 |

#### 読まれる順番(`/build-app` の場合)

```text
要件を決める    app-excellence + mvp-first-development
      ↓
画面を設計する  design-judgment →(必要なら)ux-design → jp-web-design
      ↓
実装する        wrangler / workers-best-practices
                + 要件しだいで better-auth-google-gate・durable-objects・
                  cloudflare-email-service・turnstile-spin・llm-api-integration
      ↓
検査する        testing-excellence → launch-security
      ↓
公開する        cloudflare-secure-deploy   (変更管理は全工程で solo-git-flow)
      ↓
育てる          /improve-app で1機能ずつ。必要になった時点で ci-cd-pipeline・
                web-perf・llm-cost-simulator を足す
```

最初の1本では「常時」の8個前後しか読まれません。残りは要件に該当したときだけ登場します。

## 更新するとき

新しいバージョンの ZIP を展開し、同じようにインストーラーを実行するだけです。後からインストールしたキットの内容が常に正として上書きされ、上書き前のファイルは `backup-(日時)` へ退避されます。インストーラーは `.claude` と `.codex` に導入バージョンと manifest を作り、新しいキットに含まれなくなった古いスキル・コマンド・エージェントをバックアップへ移動して整理します。対象はキットが入れたものだけで、ご自身で追加した項目や各スキルの `knowledge/` は消えません。

## アンインストールするとき

`.claude`、`.agents/skills`、`.codex` から次を削除してください。`backup-YYYYMMDD-HHMMSS/` に元のファイルが残っていれば、そこから戻せます。

- `.claude/skills/` と `.agents/skills/` の中の、[共通スキル](#共通スキル開発ノウハウ集--20個)の6表にある20フォルダ
- `.claude/agents/app-orchestrator.md`、`.claude/commands/` の4ファイル(`build-app` `improve-app` `undo-app` `setup-cicd`)
- `.agents/skills/app-orchestrator/` と4つのコマンドスキル
- `.codex/agents/app-orchestrator.toml`。`--legacy-prompts` を使った場合だけ `.codex/prompts/` 内の4ファイル
- 3ツリー直下の `aidd-agent-kit.LICENSE` / `aidd-agent-kit.NOTICE` / `aidd-agent-kit.ATTRIBUTION.md`、および `.claude` と `.codex` の `aidd-agent-kit.version` / `aidd-agent-kit.manifest`

## フォルダ構成

```
aidd-agent-kit/
├── START-HERE.md            ← 利用者の唯一の入口(3手順)
├── manual-mac.md / .html    ← Mac用の手順詳細と Q&A(html は md から生成)
├── manual-windows.md / .html← Windows用の手順詳細と Q&A(html は md から生成)
├── install-mac.command / install-windows.bat      ← インストーラー
├── setup-env-mac.command / setup-env-windows.bat  ← Node.js + pnpm + Cloudflare連携
├── sync-project-mac.command / sync-project-windows.bat ← 管理者専用(下記)
├── verify-codex-layout.sh   ← Codex配置と原本一致の自動検査
├── doctor-codex-layout.sh   ← scope衝突(user/project二重導入)の診断
├── scripts/                 ← package-kit.sh、gen-manual-html.mjs、Mac/Windowsの検査、CI用smoke test
│   └── lib/self-heal.sh     ← install-mac と setup-env-mac が共有する自己修復処理
├── skills/ agents/ commands/ codex/ ← エージェントが読む中身(編集原本)
├── README.md                ← このファイル(エージェント・開発者向け)
├── CODEX-PLACEMENT.md       ← Codexの配置と反映元の正本
├── INVARIANTS.md            ← 縮小時に消してはならない規則
├── CHANGELOG.md             ← 変更履歴
├── LICENSE / NOTICE / ATTRIBUTION.md ← Apache License 2.0 と帰属表示
├── VERSION / NODE_MIN_MAJOR ← バージョンと必要な Node.js の最低メジャー版(各1ファイルが正本)
└── .gitattributes           ← Windows用ファイルの改行コード指定
```

## 管理者向け: `sync-project-*`(通常は使いません)

`sync-project-mac.command` / `sync-project-windows.bat` は、このキットを内包するリポジトリ自身へ project scope で反映する管理者専用の手段です。反映先はキットの親ディレクトリに固定されており、任意のプロジェクトは指定できません。キットを使いたいだけなら `install-*` と `setup-env-*` の2つで完結します。手順と検証は [`CODEX-PLACEMENT.md`](CODEX-PLACEMENT.md#反映手順) を参照してください。

## 保守者向け: 配布ZIPを作る

リポジトリのルートで次を実行します。出力先は `dist/aidd-agent-kit.zip` で、Git で管理中のファイルと Git が無視していない未追跡ファイルだけが入ります。

```bash
bash aidd-agent-kit/scripts/package-kit.sh --check  # 一時ZIPの生成・展開検証まで行い、distは更新しない
bash aidd-agent-kit/scripts/package-kit.sh          # 検査してZIP作成
node aidd-agent-kit/scripts/gen-manual-html.mjs     # manual-*.md から manual-*.html を再生成
```

manual の正本は `manual-*.md` です。`.html` は生成物なので直接編集せず、md を直してから再生成してコミットします(検査がコミット済み html と生成結果の一致を確認します)。GitHub Actions では `aidd-agent-kit-zip` artifact として保存され、同じ ZIP に対する macOS / Windows 実機ジョブが合格したら配布可能です。

## 変更履歴

現在の版は冒頭のバージョン表記(正本は `VERSION`)のとおりです。版ごとの変更点は [`CHANGELOG.md`](CHANGELOG.md) を参照してください。

## ライセンス

本キットは [`github.com/cloudflare/skills`](https://github.com/cloudflare/skills)(Apache License 2.0)由来のファイルを含みます。詳細は `LICENSE` / `NOTICE` / `ATTRIBUTION.md` を参照してください。この3ファイルは配布 ZIP に同梱され、インストール時に `.claude/` と `.codex/` へ `aidd-agent-kit.LICENSE` などの名前で配置されます。

---

株式会社TierMind
