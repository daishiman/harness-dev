---
description: 自動チェックと自動公開のしくみ(CI/CD)をリポジトリに導入する(GitHub Actions・費用は最小限)
argument-hint: [対象リポジトリのパス。省略時は現在のフォルダ]
---

Skill `ci-cd-pipeline` をロードし、その手順に従って CI/CD を導入してください。

## 対象

$ARGUMENTS

## 実行ルール

- 必ず最初に Skill ツールで `ci-cd-pipeline` をロードする。記憶で進めない。
- **導入前に §0 の判断を自分で行う**。導入しないほうがよい状況(まだ公開していない・テストが1本もない)では、質問で止めず、導入しないという結論、根拠、先に整える最小成果物を提示する。作ることが目的ではない。
- `ci-cd-pipeline/assets/detect-pm.yml`を`.github/actions/detect-pm/action.yml`へ配置する。CI・Deploy・Migrateはこの共通部品でパッケージマネージャ(npm / yarn / pnpm)をロックファイルから自動判別するため、判定処理を各workflowへコピーしたり固定したりしない。
- `package.json` の `scripts` を実際に読み、ワークフローが呼ぶスクリプト名(`typecheck` / `test` / `deploy` / `db:backup` / `db:migrate:remote` / `cf-typegen`)が**実在するか確認する**。無いものは、そのステップを削るか、スクリプトを追加するかを判断して伝える。
- repo、package manager、Wrangler package、Worker/D1/R2名、固定本番URL、既存secret名を先に自動発見する。調査コマンドを利用者へ丸投げしない。
- 複数Cloudflare Accountがある新規構築では、チーム用共有Accountを推奨し既定選択する。個人Accountは明示指定時だけ使う。既存リソースが個人側なら複製せず移行判断で止める。料金プラン変更は承認なしに行わない。
- `ci-cd-pipeline`のgeneratorで、プロジェクト固有の`docs/cloudflare-credentials-setup.md`と秘密値非表示helperを生成する。画面名だけの案内で終えない。
- **認証情報(Cloudflare APIトークン等)の作成は代行しない**。Account API Tokenのクリック先・最小権限・単一チームAccount限定を案内し、利用者本人には生成済みhelperを1回実行してもらう。Tokenをチャットへ貼らせない。
- GitHubの`CLOUDFLARE_*`は`production` Environment secret、`APP_URL`はRepository variableへ登録する。workflow jobの`environment: production`とmain限定を検証する。
- 既存Worker secretは通常セットアップで上書きしない。ローテーションは影響を説明して明示承認後だけ行う。
- スモークテストは**先に手元で流して通ることを確認してから** CI に入れる。CI の中でしか試せない状態にしない。
- **わざとテストを1つ壊して CI が赤くなることを確認する手順を飛ばさない**。ここを飛ばすと「設定したつもりで何も検査していない」状態に気づけない。確認後は必ず元に戻す。
- ブランチ保護の必須チェックに指定する名前は**ジョブ名**であってワークフロー名ではない。間違えると永久に Pending になる。
- 既に `.github/workflows/` に何かある場合は**上書きしない**。中身を読み、差分と重複(特に Cloudflare Workers Builds との二重デプロイ)を分析し、安全で重複のない構成を1つ選んでパッチを作る。認証情報や本番公開など本人しか決められない境界だけを、成果物の提示後に確認する。

## 完了後に報告すること

非エンジニアが読める言葉で、次の順に書く。

1. **これから何が自動になるか**(例: 「コードを直すと自動で検査され、問題があれば公開されません」)
2. **ご自身にやっていただくこと**(認証情報の登録手順。ここだけは代行できない理由も一言添える)
3. **費用**(公開リポジトリなら無料。非公開なら月何分の枠に対してどれくらい使う見込みか)
4. **自動にしなかったこと**と、その理由(データベースの形の変更は手動のまま/失敗しても自動では元に戻さない)
5. 技術的な詳細はその後ろに置く
