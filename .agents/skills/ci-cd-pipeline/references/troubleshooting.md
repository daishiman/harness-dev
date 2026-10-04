# うまくいかないときに見るところ

## 1. デプロイしたのに反映されない

### 1.1 まだ古いアイソレータが生きている

Cloudflare Workers は新しいコードを配った後も、**すでに起動している古いプロセス（アイソレータ）がしばらく残る**。数十秒〜1〜2分。

デプロイ直後に1回叩いて古い内容が返ってきても、それは失敗ではない。

- 30秒待ってから1回目
- 90秒空けて2回目
- **2回とも新しければ合格**

1回目だけ見て「反映された」と判断しない。1回目だけ見て「失敗した」とも判断しない。

### 1.2 そもそも別のものをデプロイしている

`wrangler deploy` は **git のコミットではなく、いまの作業ツリーの中身**をビルドする。

つまり:

- コミットしていない変更があれば、**それも一緒に本番へ出る**
- 逆に、他のブランチにあるはずの修正は入らない

CI からデプロイすればこの問題は構造的に消える（クリーンなチェックアウトしか存在しないため）。手元からデプロイするときは、必ず直前に確認する。

```bash
git status --porcelain   # 何も出ないこと
git diff --stat          # 何も出ないこと
```

特定のコミットを確実に出したいなら、切り離したワークツリーを作る。

```bash
git worktree add --detach /tmp/deploy-src <commit>
cd /tmp/deploy-src && <インストール> && <実行コマンド> deploy
# 例: pnpm install --frozen-lockfile && pnpm run deploy
#     npm ci && npm run deploy
```

### 1.3 「main にマージした」が実は嘘だった

「main にマージしました」と報告されたコミットが、実はローカルブランチにしかない、というのは実際に起きる。

```bash
git log origin/main --oneline -5      # リモートの main を見る（ローカルの main ではない）
git branch -r --contains <commit>     # そのコミットがどのリモートブランチにあるか
```

CI を入れると、main に入っていないものは deploy が起動しないので、これも自然に防げる。

## 2. デプロイが失敗する

### 2.1 認証エラー（Authentication error / code 10000）

| 原因 | 確認方法 |
|---|---|
| シークレット名・scopeの違い | `gh secret list --env production --repo "$GITHUB_REPOSITORY"`で確認。Deploy/Migrate jobに`environment: production`が必要 |
| トークンの権限不足 | Cloudflare ダッシュボードでトークンの権限を確認（Workers Scripts:Edit / D1:Edit / R2:Edit） |
| トークンの期限切れ | 作成時に有効期限を設定していると切れる |
| fork からの PR | **fork の PR にはシークレットが渡らない**。仕様であり、正しい動作 |

シークレットの値をログに出して確認しようとしないこと。GitHub は自動でマスクするが、加工した文字列（Base64 にする、先頭数文字だけ出すなど）はマスクを回避してしまい、そのまま public なログに残る。

### 2.1.1 Account違い（code 7003 / object identifier invalid）

チーム用共有Accountと個人Accountの両方に所属していると起きやすい。新規構築はチーム用Accountを既定にするが、既存Worker/D1/R2がある場合はその所有Accountと`wrangler.jsonc`を先に照合する。

```bash
pnpm wrangler whoami
pnpm wrangler r2 bucket list
```

別Accountへ同名リソースを作って解決しない。チーム移行が必要なら別タスクとして停止する。

### 2.1.2 workerdのplatform/CPU不一致

`You installed workerd on another platform`、`workerd-darwin-64`、`workerd-darwin-arm64`が出た場合、別環境の`node_modules`が残っている。`pnpm-workspace.yaml`の`supportedArchitectures`を確認してから入れ直す。

```bash
pnpm install --force --frozen-lockfile
pnpm wrangler --version
```

lockfileを削除したり、別package managerへ切り替えたりしない。

### 2.1.3 R2が画面に見えない

`wrangler whoami`とブラウザのAccountを照合し、`r2 bucket list`を見る。本当に存在しない場合も診断中に勝手に作らず、対象Account・bucket名・課金有無を示して承認後だけ作成する。Worker binding経由なら`r2.dev`とCustom Domainは無効のままにする。

### 2.2 ビルドは通るのに本番で落ちる

「新しい列を読むアプリ」を「まだ列がないDB」に対して出したときに起きる典型。順番が逆になっている。

**必ず マイグレーション → デプロイ の順**。

途中で止めるなら「マイグレーション済み・アプリは古いまま」で止める。列が増えただけなら古いアプリはその列を知らないだけで動き続ける。

### 2.3 アセットサイズの上限

Workers には配布物のサイズ上限がある。急に落ち始めたら、大きな画像やフォントを足していないか確認する。

```bash
du -sh .open-next/assets/* | sort -h | tail -20
```

## 3. CI が落ちる

### 3.1 ローカルでは通るのに CI で落ちる

| 原因 | 対処 |
|---|---|
| ロックファイルと実際に入っているバージョンがズレている | CI は「ロックファイルの通りにしか入れない」形で実行する（`npm ci` / `yarn install --frozen-lockfile`（Berry は `--immutable`）/ `pnpm install --frozen-lockfile`）。ローカルでも同じコマンドで再現するか試す。ここで落ちるならロックファイルのコミット漏れ |
| ロックファイルが2種類ある | `package-lock.json` と `pnpm-lock.yaml` が両方あると、判別が意図と違うほうを選ぶ。移行の残骸は消す |
| 生成される型定義が無い | `cloudflare-env.d.ts` のような自動生成ファイルは `.gitignore` されているのが普通で、CI のチェックアウトには存在しない。手元には残っているので気づけない。症状は `Property 'DB' does not exist on type 'CloudflareEnv'`。型チェックの前に `cf-typegen`（＝`wrangler types`）を走らせる。Cloudflare の認証情報は不要。**手元で確かめるには、そのファイルを一時的に退避してから型チェックする** |
| ファイル名の大文字小文字 | macOS は区別しないが Linux は区別する。`import "./Foo"` と `foo.ts` は Linux で落ちる |
| コミットされていないファイルに依存している | `.gitignore` で除外したファイルをテストが読んでいないか。`git clone` した直後の状態でテストが通るかを確認する |
| 時刻・タイムゾーン | ランナーは UTC。日付を跨ぐテストが落ちる |

### 3.2 CI が落ちないほうがおかしい

導入直後に必ずやること: **わざとテストを1つ壊して、CI が赤くなるのを確認する**。

```bash
git switch -c ci-check
# テストの期待値を1つ書き換える
git commit -am "確認用: わざと壊す" && git push -u "$GIT_REMOTE" ci-check
# → PR を作り、CI が赤くなることを目で見る
git push "$GIT_REMOTE" --delete ci-check   # 確認できたら消す
```

これをやらないと「設定したつもりで、実は何もチェックしていない」ことに気づけない。**表示されているから効いている、とは限らない。**

### 3.3 必須チェックがずっと Pending のままマージできない

`paths-ignore` を付けたワークフローを required status checks に指定すると起きる。条件に合致しない PR ではワークフロー自体が起動しないため、チェックが永久に完了しない。

必須にするワークフローに `paths-ignore` を付けないこと。

## 4. 元に戻したい

### 4.1 アプリを戻す

```bash
npx wrangler deployments list
npx wrangler rollback [deployment-id]
```

即座に前のバージョンに戻る。**ただしデータベースは戻らない。**

### 4.2 データベースを戻す

自動では戻せない。バックアップから復旧する。

```bash
# 事前に取っていたバックアップ（migrate.yml の Artifact にも残っている）
npx wrangler d1 execute hr-evaluation-db --remote --file=backup.sql
```

**マイグレーションを戻すのは、適用するより何倍も難しい**。だから migrate.yml は手動実行のみにし、実行前に必ずバックアップを取る設計にしている。

### 4.3 戻す判断は人がする

スモークテストが失敗したらワークフローは赤くする。しかし**ロールバックを自動で実行しない**。

理由: 「本当に壊れている」のか「まだアイソレータが古いだけ」なのかを機械は区別できない。自動ロールバックは、正常なデプロイを勝手に巻き戻す事故を生む。人が判断する。

### 4.4 secretはコードrollbackで戻らない

`AUTH_PASSWORD`等を更新すると旧パスワードは使えず、`SESSION_SECRET`等を更新すると既存セッションが無効になる。通常セットアップでは`wrangler secret list`を先に確認し、同名があれば上書きしない。

戻す必要がある場合は、パスワードマネージャー等に保存した旧値を所有者が再登録する。値がなければ新しく発行し、全利用者の再ログイン等の影響を受け入れる。Workerコードのrollbackでは解決しない。

### 4.5 API Tokenを紛失・漏えいした

- 紛失: 値は再表示できない。新Tokenを作り、Deploy成功後に旧Tokenを削除する。
- 漏えい疑い: Git履歴修正より先に即時失効。Actionsを止め、Audit Logsとdeployment履歴を確認してから新Tokenへ交換する。

## 5. 調べ方

```bash
gh run list --repo "$GITHUB_REPOSITORY" --limit 10             # 直近の実行一覧
gh run view --repo "$GITHUB_REPOSITORY" <run-id> --log-failed  # 失敗したステップのログだけ
gh run watch --repo "$GITHUB_REPOSITORY"                       # 実行中のものを追いかける
gh secret list --repo "$GITHUB_REPOSITORY"                     # 登録済みシークレットの「名前」（値は見られない）
npx wrangler deployments list             # 本番に出ているバージョンの履歴
npx wrangler tail                         # 本番のログをその場で見る
```

## 6. 依頼者に伝えるときの言葉

| 技術的な言い方 | 伝わる言い方 |
|---|---|
| アイソレータが古い | 反映に1〜2分かかることがあります |
| CI が赤い | 自動チェックで問題が見つかったので、公開は止まっています |
| ロールバックした | 直前の正常だった状態に戻しました |
| マイグレーションを適用した | データベースの形を新しくしました。中のデータは消えていません |
| シークレットが未設定 | 接続に必要なパスワードのようなものが未登録です。ご本人に登録していただく必要があります |
