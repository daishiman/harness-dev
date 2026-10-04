---
name: ci-cd-pipeline
description: >
  Cloudflare WorkersのCI(自動検査)とCD(自動デプロイ)を、Workers Buildsまたは外部CI/CDから案件に合う1経路だけ選び、無料枠に収まる最小構成で構築・運用するためのスキル。
  「CIを入れて」「CDを組んで」「自動デプロイしたい」「GitHub Actions」「ワークフロー」「テストを自動で回したい」
  「マージしたら勝手に公開されるようにして」「デプロイを自動化して」「CIが落ちた」「Actionsが失敗する」
  「デプロイの手作業をなくしたい」「Cloudflareの設定が分からない」「非エンジニア向け手順を作って」などの文脈で必ず使用する。
  デプロイ先が Cloudflare Workers の場合は
  Skill cloudflare-secure-deploy を併用する(D1マイグレーションの扱いが最重要)。ブランチ・PR・タグの規約は
  Skill solo-git-flow に従う。手動デプロイを繰り返している状況を見つけたら、依頼されていなくても
  このスキルの §0 を読んで導入可否を判断すること。
---

# ci-cd-pipeline — deploy経路を1つに絞る最小 CI/CD

手動デプロイは「人が正しく手順を踏んだ」という申告の上に成り立つ。申告は外れる。
**CI/CD の本質は自動化による時短ではなく、「言ったこと」と「実際に起きたこと」の乖離を機械が検出することにある。**

- 外部CI/CDのワークフロー全文(必要時だけ読む): `references/workflows.md`
- Node.js・パッケージマネージャ共通部品(npm / yarn / pnpm): `assets/detect-pm.yml` → `.github/actions/detect-pm/action.yml`
- 無料枠の実数と削減手法: `references/cost-control.md`
- 失敗パターンと対処: `references/troubleshooting.md`
- 外部CI/CDを選んだ場合の雛形: `assets/ci.yml` / `assets/deploy.yml` / `assets/migrate.yml`(必要なものだけ配置)
- 非エンジニア向けCloudflare設定票: `assets/cloudflare-credentials-guide.md.template`
- 設定票と秘密値非表示helperの生成: `scripts/generate-cloudflare-credentials-guide.mjs`
- 資格情報ガイド・helper・workflowの退行検査: `scripts/validate-cloudflare-credentials-guide.mjs`
- GitHub対象リポジトリの安全な自動検出: `scripts/detect-github-repository.mjs`
- 自動検出と停止診断の実動テスト: `scripts/test-auto-discovery.mjs`

---

## §0. 入れる前の判断

### 最初にdeploy責任者を1つ選ぶ

Cloudflare公式は、GitHub/GitLabで最小設定なら Workers Builds、外部統制が必要なら外部CI/CDとする。キットの既定スタックは D1 を含むため、**既定は外部CI/CD**(`mvp-first-development` §3 の「CI/CD」行が正本)。次の決定表でそれを具体化する。

| 条件 | 選ぶ経路 | 作るもの |
|---|---|---|
| D1 を使う(既定スタック)、独自test gate、GitHub Environment、厳密な承認、セルフホストGitHub/GitLab、または非対応Gitのいずれか | **外部CI/CD(既定)** | `migrate.yml` + `deploy.yml`(migration → deploy の順 = INV-7)。必要なworkflowだけ |
| DB を持たない・静的配信だけで、ホスト版GitHub/GitLab、独自test gateなし、厳密な承認なし | **Workers Builds** | CloudflareのGit連携 + 最小のbuild/deploy command。`.github/workflows` は追加しない |

**Workers Builds 採用後にスキーマ変更が入ったら**、マージ前に Builds の deploy を無効化 → `migrate.yml` + `deploy.yml` を設置 → 切替理由と復旧手順を記録して外部CI/CDへ切り替える(手元の `--remote` 適用で凌がない)。

**Workers Builds と外部CI/CDのdeployを両方有効にすることは禁止**。既存経路がある場合は、設定・実行履歴・対象ブランチを読み取ってから継続可否を決める。別経路を追加する前に既存deployを無効化し、切替理由と復旧手順を記録する。

公式根拠:

- <https://developers.cloudflare.com/workers/ci-cd/>
- <https://developers.cloudflare.com/workers/ci-cd/builds/>
- <https://developers.cloudflare.com/workers/ci-cd/builds/git-integration/>
- <https://developers.cloudflare.com/workers/ci-cd/external-cicd/github-actions/>

### GitHubの操作対象を最初に確定する

owner/repoやremote名を手入力・固定値で決めない。現在のgit remote、現在ブランチの追跡remote、`gh repo view`を照合する読み取り専用helperを使う。

```bash
node <skill>/scripts/detect-github-repository.mjs
```

- `status: ok`: `recommended.repository`、`recommended.remote`、`recommended.default_branch`を以後の`GITHUB_REPOSITORY`、`GIT_REMOTE`、`GITHUB_DEFAULT_BRANCH`として採用する。候補比較の質問はせず、非エンジニアには「このリポジトリを使います」と推奨値を短く提示して進む。
- `status: multiple`: 認証情報を除いた候補だけを示してremoteを1つ選んでもらい、`--remote <選択名>`で再実行する。remote URLをチャットへ貼らせない。
- `status: unconfigured`: 既存GitHubリポジトリへ接続するか、新規作成するかだけを質問する。remoteの追加やリポジトリ作成は外部状態を変えるため、承認前に実行しない。
- `status: gh_auth_required`: 所有者本人に`gh auth login`を依頼する。認証コードやTokenを受け取らない。

helperはremote URLに埋め込まれたuserinfoを出力せず、GitHubとして正規化できたowner/repoだけを候補表示する。以後の`gh`操作には必ず`--repo "$GITHUB_REPOSITORY"`を付け、作業フォルダの推測に戻らない。

### 手動デプロイが実際に生む事故(実例)

| 事故 | 何が起きたか | CI/CD があれば |
|---|---|---|
| **申告と実態の乖離** | 「main にマージした」と報告されたコミットが、実はローカルブランチ止まり。**本番だけがリポジトリから再現できない状態**が数日続いた | main への push でしかデプロイが走らないため、構造的に起こらない |
| **作業ツリー混入** | `wrangler deploy` は git のコミットではなく**手元の作業ツリー**をビルドする。未コミットの実験コードが本番に混ざり得る | CI は clean checkout。混ざりようがない |
| **検証の申告** | 「テスト201件通過」が口頭報告のみで、実際に走ったかは誰も確認できない | 実行ログが残り、落ちればマージできない |
| **手順の抜け** | バックアップ→マイグレーション→デプロイ→検証の8手順を毎回人が踏む。1つ飛ばしても気づかない | 順序がコードとして固定される |

### 自動deployを止めるべき場合

| 状況 | 理由 |
|---|---|
| リリースごとの明示承認が必須 | Workers Buildsの自動deployではなく、外部CI/CDの承認/手動deployを選ぶ |
| migrationや破壊的操作をdeployと分離できていない | 先に外部CI/CDでバックアップ・手動migration・deployの順を固定する |
| 本番が1つで、壊れると業務が即停止するが回復手順がない | 先にロールバックとスモーク確認を用意し、それまで自動deployは無効にする |

テストがまだないことは、Workers Buildsのclean checkoutからdeployする価値を消さない。その場合は独自`ci.yml`を作らず、固定した業務ロジックができた時点でtesting-excellenceに従ってテストを追加する。**迷ったら、D1 を使う案件は外部CI/CD、DB を持たない案件だけ Workers Builds から始める。**

---

## §1. お金をかけない(最優先の設計制約)

### まず自分のリポジトリがどちらか確認する

```bash
gh repo view "$GITHUB_REPOSITORY" --json isPrivate -q '.isPrivate'
```

| | GitHub Actions の料金 |
|---|---|
| **public(公開)リポジトリ** | **完全に無料・無制限**。以下のコスト対策は不要(入れておいて損はない) |
| **private(非公開)リポジトリ** | Free プランで **月2,000分**。超えると課金。§1の対策が効いてくる |

### private の場合に効く7つの対策(効果の大きい順)

| # | 対策 | 効果 |
|---|---|---|
| 1 | **`runs-on: ubuntu-latest` のみ使う** | macOS は**10倍**、Windows は**2倍**の消費。macOS で 200分回すと 2,000分を使い切る。ここを間違えると他の対策が全部無意味になる |
| 2 | **`concurrency` で古い実行をキャンセル** | 連続 push したとき、古い実行が最後まで走るのを止める。実測で3〜4割減ることがある |
| 3 | **CI で重いビルドをしない** | 型チェックとテストは1〜2分、本番ビルド(OpenNext等)は5分以上かかることがある。ビルドは CD 側で1回だけ実行すれば足りる |
| 4 | **`paths-ignore` でドキュメントのみの変更を除外** | README や docs だけの変更で CI を回さない |
| 5 | **依存関係をキャッシュ** | `actions/setup-node` の `cache:` にパッケージマネージャ名を渡すとインストールが数十秒短縮 |
| 6 | **`timeout-minutes` を必ず設定** | **これは節約ではなく安全弁**。無限ループしたジョブは既定で6時間走り続け、無料枠を1回で溶かす。CI は 10分、CD は 20分を上限に |
| 7 | **ジョブを分割しすぎない** | ジョブごとに checkout と install が走り、その時間も課金される。3分のジョブ1本 > 2分のジョブ2本 |

**使ってはいけないもの**: matrix ビルド(複数バージョン検証は個人開発では過剰)、larger runners(無料枠の対象外)、スケジュール実行の cron(気づかないうちに毎日消費する)。

### Cloudflare 側の無料枠

| | 無料枠 |
|---|---|
| Workers リクエスト | 10万/日 |
| Workers Builds(Cloudflare 内蔵CI) | 月300分 |

**GitHub Actions と Cloudflare Workers Builds を両方有効にしない。** 両方が反応して二重にデプロイが走り、どちらの成果物が本番か分からなくなる。§0の決定表で選んだ経路だけを有効にする。Workers Builds を選んだら外部のdeploy workflowを置かず、外部CI/CDを選んだら Cloudflare 側の自動deployを無効にする。

---

## §2. 選んだ経路の最小構成

### A. Workers Builds(DB なし・静的配信の案件のみ)

- GitHub/GitLab の対象repositoryとproduction branchをCloudflareに接続し、build commandとdeploy commandを必要最小限にする。
- push→build→version/deployとpreview URLの履歴はWorkers Builds側を正本とする。同じbranchに反応する`deploy.yml`は作らない。
- 独自test gateやD1 migrationが必要になったら、Buildsに継ぎ足して複雑化せず、§0で外部CI/CDへ切り替える。

### B. 外部CI/CD(該当案件だけ)

| ファイル | 作る条件 | 何をするか | 壊すもの |
|---|---|---|---|
| `ci.yml` | 独自のmerge gateが必要 | 型チェック → テスト → (必要なら)ビルド | **なし**(検査だけ) |
| `deploy.yml` | 外部CI/CDがdeploy責任者 | 検査済みSHAをビルド → 本番公開 → スモークテスト | **本番アプリ** |
| `migrate.yml` | **D1 migrationがある場合だけ** | 手動起動でバックアップ → DB構造変更 | **本番データ** |

一律に3本作らない。壊せる対象と独自gateの有無から必要なworkflowだけを配置し、詳細はこの経路を選んだ時点で `references/workflows.md` を読む。

### なぜマイグレーションを自動化しないのか

DBの構造変更は**元に戻せない**(列を消したら中身も消える)。CD に混ぜると、PR をマージした瞬間に本番データの構造が変わる。

外部CI/CDでD1を使う場合、`migrate.yml` は `workflow_dispatch`(手動起動)にし、**確認文字列の入力を必須**にする:

```yaml
on:
  workflow_dispatch:
    inputs:
      confirm:
        description: '本番DBを変更します。実行するには APPLY と入力'
        required: true
```

```yaml
      - name: 確認文字列の検証
        if: inputs.confirm != 'APPLY'
        run: echo "::error::confirm に APPLY と入力してください" && exit 1
```

**GitHub の Environments による承認機能(required reviewers)は、Free プランの private リポジトリでは使えない。** public リポジトリか、Pro / Team / Enterprise が必要。したがって Free + private では上記の**確認文字列が唯一の安全弁**になる。ここを省略しない。

### 適用順序(絶対)

**マイグレーション適用(migrate.yml) → コードのデプロイ(deploy.yml)**

逆にすると、新しい構造を前提としたコードが古いDBに当たって全面エラーになる。列を削除する場合は2段階に分ける(新コードを先に出して旧列を誰も見ていない状態にしてから、削除を適用する)。

---

## §3. Cloudflare Accountとシークレット(外部CI/CDを選んだ場合だけ)

Workers Builds を選んだ場合は本節のGitHub Environment・API Token helperを導入せず、CloudflareのGit連携とBuilds設定に従う。以下はGitHub Actions等の外部CI/CDがdeployする案件だけの詳細である。

### Account選択の既定

Cloudflareでは1ユーザーが複数Accountへ所属できる。新規の自社アプリで「チーム用共有Account」と「個人Account」の両方がある場合、**チーム用Accountを既定選択**する。個人Accountは利用者が明示指定した場合だけ使う。

優先順:

1. 既存`wrangler.jsonc`と既存Worker/D1/R2の所有Account（勝手に複製しない）
2. 新規構築なら複数メンバーが参加するチーム用Account
3. 個人Accountは明示指定時のみ

既存リソースが個人側にありチーム運用へ変えたい場合は、同名リソースを作らず**移行タスクとして停止**する。料金プラン変更も承認なしに行わない。Cloudflare公式の名称はAccountであり、「チーム用Account」と特定の有料プラン名を混同しない。

### AIが先に行うこと

secretを依頼する前に、repo・package manager・Wrangler実行package・Worker/D1/R2名・固定本番URLをコードから発見する。`wrangler whoami`、リソース一覧、R2公開状態、GitHub Environment/variable/secretの**名前だけ**をread-only確認する。

不足R2/D1/Workerの作成、`wrangler login`、既存Worker secretの更新は外部状態を変えるため無条件実行しない。必要性と対象を示し、利用者の承認または所有者操作へ渡す。

### 所有者に残す操作

API Token値をAIへ渡させない。AIは次を必ず生成する。

1. `docs/cloudflare-credentials-setup.md`（画面名、入力値、成功条件、停止条件、復旧まで含む）
2. `.cloudflare/setup-production.mjs`（秘密値を非表示入力し、ファイル・ログ・引数へ残さない）

生成例:

```bash
node <skill>/scripts/generate-cloudflare-credentials-guide.mjs \
  --auto \
  --account-name "<既存所有Accountの表示名>"
```

`--auto`（または完全な無引数起動）は、GitHub owner/repoと既定ブランチ、git管理下の単一Wrangler設定、lockfileからpackage manager、Worker/D1/R2名、Wrangler設定またはGitHub Repository variableの`APP_URL`を読み取り専用で検出する。monorepoではWrangler設定ディレクトリをpackage managerの`--dir` / `--prefix` / `--cwd`で固定するため、repository rootからhelperを実行しても対象設定を見失わない。workerd再導入コマンドも同じpackage managerから生成し、lockfileを壊さない。

Wrangler設定があることだけでは、Cloudflare上に既存resourceがある証明にならない。`--auto`のAccount modeは新規構築として`team`を既定にする。AIがread-only照合でWorker/D1/R2の既存所有先を確認できた場合だけ`--account-mode existing`を渡し、その所有先を優先する。teamかpersonalかを客観判定できない既存Accountをteamと表示しない。明示的な個人利用だけ`personal`を選ぶ。Account名はAccount IDから推測せず、不足として停止して表示名だけを求める。Wrangler設定やD1/R2、lockfile、`APP_URL`が複数・不一致なら候補と対応する明示引数を示して生成前に停止する。

自動検出で決められない値を明示する場合の完全指定例:

```bash
node <skill>/scripts/generate-cloudflare-credentials-guide.mjs \
  --app-name "<アプリ名>" \
  --repo "$GITHUB_REPOSITORY" \
  --worker "<worker>" \
  --d1 "<database_name>" \
  --r2 "<bucket>" \
  --app-url "https://<production-origin>" \
  --account-name "<チーム用Account名>" \
  --account-mode team \
  --wrangler-command-json '["pnpm","--filter","<package>","exec","wrangler"]' \
  --install-command-json '["pnpm","install","--force","--frozen-lockfile"]' \
  --auth-password-secret AUTH_PASSWORD \
  --session-secret SESSION_SECRET
```

存在しないD1/R2/Worker secretの引数は省く。既存出力を更新するときは、AIが差分を確認した後だけ`--force`を使う。

生成後とSkill更新時は次を必ず通す。

```bash
node <skill>/scripts/validate-cloudflare-credentials-guide.mjs
node <skill>/scripts/test-auto-discovery.mjs
node .cloudflare/setup-production.mjs --dry-run
```

所有者はチーム用Accountで**account-owned API Token**を作り、生成済みhelperを1回実行する。継続的CI/CDを個人の在籍や権限に依存させないため、`My Profile > API Tokens`のuser tokenは既定にしない。

Token権限は使用機能だけに限定する。

| 種別 | 権限 | 必要な理由 |
|---|---|---|
| Account | Account Settings : Read | 対象Account確認 |
| Account | Workers Scripts : Edit | デプロイ |
| Account | D1 : Edit | `migrate.yml`を使う場合だけ |
| Account | Workers R2 Storage : Edit | R2を使う場合だけ |

Account Resourcesはチーム用Account1件に限定し、全Account・全Zone・Global API Key・R2 API Tokenを使わない。

GitHubへの登録先はRepository secretではなく、`production` **Environment secret**で固定する。

```bash
gh secret set CLOUDFLARE_API_TOKEN --env production --repo "$GITHUB_REPOSITORY"
gh secret set CLOUDFLARE_ACCOUNT_ID --env production --repo "$GITHUB_REPOSITORY"
gh secret list --env production --repo "$GITHUB_REPOSITORY"
```

`deploy.yml`と`migrate.yml`のjobには`environment: production`が必要。これがないとEnvironment secretを読めない。

Worker secret(`wrangler secret list` → 既存secretを通常セットアップで上書きしない → 更新はローテーション扱いで所有者が明示実行)の手順と停止条件は`cloudflare-secure-deploy` §2・§10に従う。CI/CDで扱うのは上記のGitHub Environment secretだけである。

### やってはいけないこと

- ワークフローファイルにトークンを直接書く(**public リポジトリなら世界中に公開される**)
- `echo ${{ secrets.X }}` でログに出す(ログは残る。GitHub のマスク機能は加工した値には効かない)
- フォークからの PR で secrets を使う(`pull_request` トリガーではフォークに secrets は渡らない仕様。これは正しい挙動なので回避しようとしない)

---

## §4. 外部CIの原則(独自gateが必要な場合だけ)

### 落ちないCIは存在しないのと同じ

CI の価値は**マージを止めること**にある。「落ちても無視してマージ」を1度でも許すと、次からは誰も見なくなる。

導入したら**ブランチ保護を必ず設定する**(これをしないと CI は単なる飾りになる):

```bash
GITHUB_DEFAULT_BRANCH_API="$(node -p 'encodeURIComponent(process.argv[1])' "$GITHUB_DEFAULT_BRANCH")"
gh api -X PUT "repos/$GITHUB_REPOSITORY/branches/$GITHUB_DEFAULT_BRANCH_API/protection" \
  -f 'required_status_checks[strict]=true' \
  -f 'required_status_checks[contexts][]=verify' \
  -F 'enforce_admins=false' \
  -F 'required_pull_request_reviews=null' \
  -F 'restrictions=null'
```

`verify`は`assets/ci.yml`の`jobs:`直下にあるジョブ名である。ワークフロー名`CI`や別名`ci`を指定すると必須チェックが永久にPendingになるため、コピー先の実ファイルでもジョブ名が一致することを確認する。

- `enforce_admins=false` にする理由: 個人開発では緊急時に自分で回避できる逃げ道を残す。ただし**使ったら理由を記録する**。
- `required_pull_request_reviews=null`: レビュアーが自分だけなので承認は要求しない(solo-git-flow §0-5 と整合)。

**ブランチ保護は private リポジトリの Free プランでは使えない。** その場合は「CI が緑になってからマージする」を運用ルールとして守る。

### CI に入れるもの / 入れないもの

| 入れる | 理由 |
|---|---|
| 型チェック(`tsc --noEmit`) | 最も速く最も多くのバグを捕まえる。1分未満 |
| テスト | 壊れたことの検出。これが無いなら CI を入れる意味が薄い |
| 依存の脆弱性検査(`npm audit` / `pnpm audit --audit-level high` 等) | 数秒。ただし**警告どまりにする**(上流の更新待ちで作業が止まるのを防ぐ) |

| 入れない | 理由 |
|---|---|
| 本番ビルド | 遅い。型チェックで大半は捕まる。CD 側で1回やれば足りる |
| E2Eテスト(ブラウザ自動操作) | 遅く不安定。落ちる理由がコードでないことが多く、無視される文化を生む |
| Lint の自動修正コミット | CI がコードを書き換えると履歴が汚れ、手元と食い違う。**検査のみ**にする |

---

## §5. 外部CDの原則

### CD が構造的に解決する問題

`wrangler deploy` は git のコミットではなく**その場のファイル**をビルドして公開する。手動デプロイでは、手元に未コミットの変更があればそれが本番に混ざる。だから手動運用では毎回 `git worktree add --detach <commit>` で使い捨てフォルダを作る必要があった。

**CI 上では clean checkout なので、この問題は消える。** これが CD を入れる最大の実利で、時短ではない。

### デプロイ後は必ず検証する(スキップ禁止)

デプロイ完了 ≠ 動いている。**公開直後に必ず本番URLを叩いて確認する。**

**待機時間を必ず入れる。** Cloudflare Workers は旧バージョンの実行環境(isolate)を数十秒〜1〜2分保持する。実測で、デプロイ直後は20画面中15画面が古い応答を返し、2分後に全て新しくなった事例がある。

1回だけの確認では次の2つが**両方**起こり得る:
- 直っているのに「直っていない」と誤判定する
- 壊れているのに古い正常応答を見て「大丈夫」と誤判定する

したがって **30秒待つ → 1回目 → 90秒待つ → 2回目** の二段構えにする。

### 失敗したときに戻せること

戻し方のコマンド(`wrangler deployments list` / `wrangler rollback`、versions による段階配信)は`cloudflare-secure-deploy` §8が正本で、ここでは複製しない。CI/CD固有の規律は次の1点。

**スモークテストが落ちたらワークフローを失敗させる。** 「デプロイは成功したがアプリは壊れている」を緑で通さない。自動ロールバックはせず、人が原因を確認して対象変更を`git revert`し、mainのCI成功後に同じDeploy経路で戻す。`wrangler rollback`はCI/CDを待てない緊急時のみに限定する。

---

## §6. 導入手順

### A. Workers Builds

1. Cloudflareの Workers & Pages から対象Workerの **Settings > Builds** を開き、ホスト版GitHub/GitLab repositoryを1件接続する。
2. Worker名とWrangler設定の`name`、root directory、production branch、build/deploy commandを既存プロジェクトに合わせる。
3. pushでbuild/deployが1回だけ走り、build history・version・preview URL・active deploymentの対応を確認する。
4. Git provider側のcheck/commit statusを確認し、外部のdeploy workflowが同じpushで走っていないことを確認する。

### B. 外部CI/CD

以下は外部CI/CDを選んだ場合だけ実行する。D1がなければ`migrate.yml`のコピーと設定は省く。

```bash
# 1. 必要な雛形だけ置く
mkdir -p .github/workflows .github/scripts .github/actions/detect-pm
# 独自merge gateが必要な場合だけ:
cp <skill>/assets/ci.yml .github/workflows/ci.yml
# 外部CI/CDがdeploy責任者なので:
cp <skill>/assets/deploy.yml .github/workflows/deploy.yml
# D1 migrationがある場合だけ:
cp <skill>/assets/migrate.yml .github/workflows/migrate.yml
cp <skill>/assets/detect-pm.yml .github/actions/detect-pm/action.yml
cp <skill>/assets/smoke.sh    .github/scripts/smoke.sh
chmod +x .github/scripts/smoke.sh   # ワークフローは bash 経由で呼ぶので必須ではないが、手元で試しやすくなる

# 2. プロジェクトに合わせて書き換える
#    - パッケージマネージャ(npm/yarn/pnpm)は共通Actionがロックファイルから自動判別するので変更不要
#    - Nodeバージョンと、呼んでいるスクリプト名が package.json の scripts と
#      一致しているかは必ず確認する(typecheck / test / deploy / db:backup / db:migrate:remote)
#    - migrate.yml の <DB名> を実際の D1 データベース名に置き換える
#    - cf-typegen スクリプトがないプロジェクトでは ci.yml と deploy.yml の該当ステップを削除する
#      （逆に、cloudflare-env.d.ts のような「生成される型定義」を .gitignore しているなら、
#        型チェックの前にそれを作るステップが要る。無いと CI だけが必ず落ちる）

# 3. スモークテストを手元で流して通ることを確認する(CI に入れる前にやる)
APP_URL=https://<本番URL> bash .github/scripts/smoke.sh
#    CI の中でしか試せない状態にすると、直すたびに push して数分待つことになる

# 4. AIがCloudflare Account/リソース/GitHub設定をread-only診断する
#    新規構築はチーム用Accountを既定にし、個人Accountへは自動で進まない

# 5. 非エンジニア向け作業票と秘密値非表示helperを生成する(§3)

# 6. 本番URLを Variables に登録する(シークレットではない。公開情報)
gh variable set APP_URL --body "https://<本番URL>" --repo "$GITHUB_REPOSITORY"

# 7. 所有者がAccount API Tokenを作り、生成済みhelperを1回実行する
#    AIへtokenを貼らない

# 8. 独自CI gateがある場合はCIだけ先に有効化する。deployはmain反映まで走らず、
#    D1 migrationは手動起動以外で走らないことを確認する

# 9. 実際に PR を出して CI が緑になることを確認する
gh pr create --repo "$GITHUB_REPOSITORY" ...
gh run list --repo "$GITHUB_REPOSITORY" -L 3
gh run watch --repo "$GITHUB_REPOSITORY"  # 実行中のジョブを追う

# 10. わざと失敗させて、赤くなることを確認する(重要)
#    落ちないことを確認しただけでは「本当に検査しているか」が分からない

# 11. 独自merge gateが必要な場合だけブランチ保護を設定する(§4)

# 12. CI成功後の自動CDを有効化する。workflow_runのSHAがmainと一致するまで見届ける
```

**手順10を飛ばさない。** テストを1つわざと壊して CI が赤くなるのを見るまで、その CI は「動いているように見えるだけ」かもしれない。今回の対象プロジェクトでは、回答期間の設定が画面に表示されるのに判定にまったく使われていないという不具合が実在した。**表示されているから効いている、とは限らない。**

---

## §7. 運用

| やること | 頻度 |
|---|---|
| `gh run list --repo "$GITHUB_REPOSITORY" -L 5` で直近の結果を見る | PR を出したとき |
| 落ちた CI を放置しない | 即時。1件放置すると全体が形骸化する |
| Dependabot の PR を処理する | 週1回。**放置された Dependabot の失敗が並んでいるリポジトリは、CI 全体が信用されていない証拠** |
| ワークフローの実行時間を確認する | 月1回。private なら消費分も(`gh api "repos/$GITHUB_REPOSITORY/actions/timing"`) |

---

## §8. やってはいけないこと

| 禁止 | 理由 |
|---|---|
| CI が赤いままマージする | 1回許すと二度と見られなくなる |
| ワークフローに認証情報を直書き | public なら即漏洩、private でも履歴に永久に残る |
| DBの構造変更を自動デプロイに混ぜる | 元に戻せない変更が、マージした瞬間に本番データへ及ぶ |
| 外部CI/CDで `timeout-minutes` を書かない | 暴走ジョブが既定6時間走り、無料枠を1回で溶かす |
| 外部CI/CDで macOS ランナー | Linux の10倍消費する。個人開発で必要になる場面はほぼ無い |
| デプロイ後の検証を省く | 「デプロイ成功」はファイルが届いたことしか意味しない |
| スモークテストを1回だけにする | 旧バージョンの実行環境が残っており、古い応答で誤判定する |
| CI にコードの自動修正をさせる | 手元と食い違い、原因不明の差分が生まれる |

---

## §9. 検収チェックリスト

- [ ] §0の決定表で Workers Builds / 外部CI/CD のどちらか1つを記録した
- [ ] 同じproduction branchに反応するdeploy経路が1つだけで、二重deployがない
- [ ] 複数Accountならチーム用Accountを既定選択し、個人Accountを暗黙選択していない
- [ ] 選定経路のbuild/deploy履歴、対象commit、active deploymentが対応する
- [ ] デプロイ後、間隔を空けた2回のスモーク確認に成功した
- [ ] 戻し方(`wrangler rollback`)を実際に試した、または手順を記録した

**Workers Buildsを選んだ場合だけ**:

- [ ] ホスト版GitHub/GitLabの対象repository・production branch・root directory・commandが正しい
- [ ] Git provider側のcheck/commit statusとWorkers Buildsのbuild historyを確認した
- [ ] 外部のdeploy workflowが同じpushで走らない

**外部CI/CDを選んだ場合だけ**:

- [ ] GitHub案件ではowner/repo/remoteをhelperで検出し、`status: ok`の推奨値を全GitHub操作で共用した
- [ ] 必要なworkflowだけを配置し、全ジョブに`timeout-minutes`、対象ジョブに`concurrency`がある
- [ ] 非エンジニア向け設定票/helperを生成し、Secretは本人が必要最小権限で登録した
- [ ] GitHub Environmentが必要な案件は`production`をmainだけに限定し、workflow jobがそれを参照する
- [ ] 独自CI gateが必要な案件は、わざと失敗させてmergeが止まることを確認した
- [ ] D1がある場合だけ手動migration jobと確認文字列を用意し、migration → deployの順を守った
- [ ] Cloudflare側の自動deployを無効にした

---

## §10. 関連スキル

| スキル | 使う場面 |
|---|---|
| `solo-git-flow` | ブランチ名・コミット・PR・タグの規約。CI/CD のトリガーはここで決めた規約に従う |
| `cloudflare-secure-deploy` | Cloudflare へのデプロイ手順・D1の鉄則・wrangler設定。CD の中身はこちらが正 |
| `testing-excellence` | CI で回すテストの書き方。テストが無いなら先にこちら |
| `launch-security` | 公開前の監査。CI に組み込むより、リリース判定として人が回す方が実効的 |
