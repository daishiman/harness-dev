# ワークフロー3本の設計

`assets/` にある3本をそのまま `.github/workflows/` に置けば動く。ここでは**なぜその形なのか**を書く。設定を変えたくなったとき、ここを読んでから変えること。

## 0. なぜ3本なのか

分ける基準は「工程」ではなく **壊せる範囲**。

| ワークフロー | 引き金 | 壊せるもの | 失敗したときの被害 |
|---|---|---|---|
| `ci.yml` | push / PR | **何も壊せない** | なし。赤くなるだけ |
| `deploy.yml` | main のCI成功後 | 動いているアプリ | 数分間おかしくなる。ロールバックで戻る |
| `migrate.yml` | **手動のみ** | データそのもの | **戻すのが難しい**。バックアップからの復旧が必要 |

壊せる範囲が違うものを同じ引き金にまとめない。「main に push したらマイグレーションも走る」は、押し間違いが即データ事故になる。

これ以上増やさない。ジョブを増やすほど依存関係インストールの重複と実行の切り上げが増え、どこで何が起きたか追えなくなる。

## 0.1 パッケージマネージャは固定しない

3本とも、冒頭で**ロックファイルを見てパッケージマネージャを判別**する。

| 見つかるファイル | 使うもの | インストール |
|---|---|---|
| `pnpm-lock.yaml` | pnpm | `pnpm install --frozen-lockfile` |
| `yarn.lock` + `.yarnrc.yml` | Yarn Berry (v2+) | `yarn install --immutable` |
| `yarn.lock` のみ | Yarn v1 | `yarn install --frozen-lockfile` |
| それ以外 | npm | `npm ci` |

判別の根拠に「設定ファイルの宣言」ではなく**ロックファイルの実在**を使う。宣言は書き換え忘れるが、ロックファイルは実際にインストールした事実の痕跡なのでズレようがない。

いずれも「ロックファイルの通りにしか入れない」形を選んでいる。`npm install` や素の `yarn install` はロックファイルを書き換えることがあり、CI とローカルで入るものがズレる。

共通処理は`assets/detect-pm.yml`を`.github/actions/detect-pm/action.yml`へ配置し、各workflowから`uses: ./.github/actions/detect-pm`で呼ぶ。判別・Node.js準備・依存関係installをコピー＆ペーストしない。

## 1. ci.yml

### 引き金

`push: [main]` と `pull_request`。両方入れる理由は役割が違うから。

- PR での実行 = **入る前に止める**（本来の目的）
- main での実行 = マージ後に壊れていないかの最終確認。PR を経ずに直接 push されたときの網

### 中身は型チェックとテストだけ

```yaml
- run: ${{ steps.pm.outputs.install }}
- run: ${{ steps.pm.outputs.run }} typecheck
- run: ${{ steps.pm.outputs.run }} test
```

これで「壊れたコードが main に入る」の大部分を止められる。本番ビルドや E2E は入れない（`cost-control.md` §3.4）。

`run` に `npm run` / `yarn run` / `pnpm run` のいずれかが入る。3種とも `<pm> run <スクリプト名>` が有効なので、この書き方に統一すればどれでも同じ形で通る。

### 1つのジョブにまとめる

型チェックとテストを別ジョブに分けると、`checkout` と依存関係のインストールを2回払う。並列で数十秒速くなるが、消費分は増え、ログも2箇所に散る。

### 必須チェックにする

CI を作っただけでは何も止まらない。**赤くてもマージできてしまう**。ブランチ保護で必須にして初めて機能する。

```bash
GITHUB_DEFAULT_BRANCH_API="$(node -p 'encodeURIComponent(process.argv[1])' "$GITHUB_DEFAULT_BRANCH")"
gh api -X PUT "repos/$GITHUB_REPOSITORY/branches/$GITHUB_DEFAULT_BRANCH_API/protection" \
  -f 'required_status_checks[strict]=true' \
  -f 'required_status_checks[contexts][]=verify' \
  -f 'enforce_admins=false' \
  -F 'required_pull_request_reviews=null' \
  -F 'restrictions=null'
```

`contexts` に入れる名前は**ジョブ名**（`jobs:` の直下のキー、ここでは `verify`）。ワークフロー名（`CI`）ではない。ここを間違えると永久に Pending になる。

一人開発なら `enforce_admins=false` にしておく。緊急時に自分で越えられる逃げ道を残す（越えたことがログに残るので、後から気づける）。

`required_pull_request_reviews=null` は「レビュー必須にしない」。一人なら自分でレビューはできない。

## 2. deploy.yml

### 引き金

`workflow_run`で、mainへのpushを検査した`CI`が成功した後だけ起動する。**PRのCI成功では動かさない**。job条件で`workflow_run.event == 'push'`と`conclusion == 'success'`を両方確認する。

checkoutは`github.event.workflow_run.head_sha`を明示し、CIが検査したcommitとデプロイ対象を一致させる。`workflow_dispatch`も残すが、mainだけを許可し、手動経路ではtypecheck/testを再実行してCIを迂回させない。

### production Environment

DeployとMigrateのjobへ`environment: production`を付ける。`CLOUDFLARE_API_TOKEN`と`CLOUDFLARE_ACCOUNT_ID`はRepository secretではなく、このEnvironment secretへ登録する。`APP_URL`だけは公開情報なのでRepository variable。

EnvironmentのDeployment branches and tagsはmainだけにする。これにより、手動実行で作業ブランチを選んでも本番secretとデプロイへ進めない。

### なぜ CI からのデプロイが安全なのか

`wrangler deploy` は git のコミットではなく**その場の作業ツリー**をビルドする。手元から流すと:

- コミットしていない実験コードが本番に出る
- 「main にマージした」と思っていたものが実はローカル止まりで、出ていない

CI のランナーは毎回まっさらなチェックアウトしか持たない。作業ツリー＝コミットが常に一致する。**この問題が構造的に消える**のが、CD を入れるいちばん大きな理由。

### concurrency は打ち切らない

```yaml
concurrency:
  group: deploy-production
  cancel-in-progress: false
```

`ci.yml` と違い `false`。デプロイの途中で打ち切られると、配布が中途半端な状態で残りうる。待たせる。

### デプロイ後のスモークテスト

配ったあと、実際に本番を叩いて生きているか見る。ここで効いてくるのが**アイソレータの残留**。

Cloudflare Workers は新しいコードを配った後も、すでに起動している古いプロセスがしばらく残る（数十秒〜1〜2分）。だから:

- 30秒待ってから1回目
- 90秒空けて2回目
- **2回とも通って初めて合格**

1回目だけ見ると、古いプロセスが返した正常応答を「成功」と誤読する。逆に古い内容が返っただけで「失敗」とも誤読する。

### 失敗しても自動で戻さない

スモークが落ちたらワークフローは赤くする。しかし `wrangler rollback` は自動実行しない。「本当に壊れている」のか「まだ古いだけ」なのかを機械は区別できないため。人が判断する。

## 3. migrate.yml

### 手動のみ

`workflow_dispatch` だけ。push では絶対に動かさない。

jobには`environment: production`を付け、同EnvironmentのCloudflare secretとmain限定ポリシーを使う。

### confirm: APPLY

```yaml
inputs:
  confirm:
    description: 本番DBを変更します。よければ APPLY と入力してください
    required: true
```

```yaml
- if: ${{ inputs.confirm != 'APPLY' }}
  run: exit 1
```

本来は GitHub の Environments に「実行前に承認者の承認を必要とする」設定があるが、**private リポジトリ + Free プランでは使えない**。public リポジトリなら使えるので、public ならそちらを併用してもよい。

いずれにせよ、押し間違いで本番のデータ構造が変わるのを防ぐ一段が要る。

### 順番は絶対

**マイグレーション → デプロイ**。

逆にすると、新しいアプリがまだ存在しない列を読みにいって本番が落ちる。

途中で止めるなら「マイグレーション済み・アプリは古いまま」で止める。列が増えただけなら、古いアプリはその列を知らないだけで動き続ける。**これは安全な中断点**であり、実際に本番作業を分割するときはここで区切る。

### バックアップは先。取れなければ進まない

```yaml
- name: バックアップ取得
  run: ${{ steps.pm.outputs.run }} db:backup
- name: バックアップを保管
  if: always()
  uses: actions/upload-artifact@v7
```

`if: always()` を付けているのは、後続が失敗してもバックアップだけは残すため。

Artifact は public リポジトリでも認証なしでは落とせないが、**リポジトリの書き込み権限を持つ人は全員取得できる**。個人情報を含むデータベースを扱うときは、保管期間を短くする（既定90日 → 14日）か、Artifact に残さず別の安全な場所へ出す判断もありうる。

## 4. 変えるときの判断

| 変えたくなったこと | 判断 |
|---|---|
| ステージング環境も作りたい | `deploy.yml` を複製せず、`environment` を入力に取る形にする。2本に増やすと片方だけ直す事故が起きる |
| デプロイ前に承認を挟みたい | public なら Environments の required reviewers。private + Free なら `workflow_dispatch` 化して手動にする |
| Slack に通知したい | 入れてよい。ただし Webhook URL はシークレットに。ログに出さない |
| テストが遅いので並列化したい | まず遅いテストを特定する。並列化は消費分を増やす。原因が1本のテストなら、そこを直すほうが安い |
| Cloudflare の Workers Builds も使いたい | **併用しない**。同じコミットで2回デプロイが走り、どちらが最後か分からなくなる |
| チーム用と個人用のCloudflare Accountがある | 新規はチーム用Accountを既定。既存リソースが個人側なら複製せず移行タスクへ分ける |
