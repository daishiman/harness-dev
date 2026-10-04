---
name: setup-cicd
description: GitHub Actionsの自動チェック、Cloudflareのチーム用Account設定、非エンジニア向け資格情報登録、自動公開を安全に導入する。Codexで「CI/CDを設定」「Cloudflareを設定」「自動デプロイ」「$setup-cicd」と依頼されたときに使用する。
---

# Set up CI/CD

1. 最初に `$ci-cd-pipeline` を使用し、Cloudflare Workersなら続けて`$cloudflare-secure-deploy`と`$wrangler`を使用する。記憶だけで進めない。
2. 対象パスの指定がなければ現在の作業フォルダを対象にする。
3. 同スキルの導入可否判定を自分で行う。未公開またはテストが1本もない場合は質問で止めず、導入しない結論、根拠、先に作る最小成果物を提示する。
4. `ci-cd-pipeline/assets/detect-pm.yml`を`.github/actions/detect-pm/action.yml`へ配置し、CI・Deploy・Migrateから同じ部品を呼ぶ。パッケージマネージャー（npm・yarn・pnpm）はロックファイルから自動判別し、雛形へ同じ判定処理をコピーしない。
5. `package.json` の `scripts` を実際に読み、ワークフローが呼ぶ `typecheck`・`test`・`deploy`・`db:backup`・`db:migrate:remote`・`cf-typegen` が実在するか確認する。無い処理は、ステップを削るかスクリプトを追加するかを判断し、その理由を伝える。
6. 既存の `.github/workflows/` を上書きしない。実ファイルを読み、差分、重複、特に Cloudflare Workers Builds との二重デプロイを分析し、安全で重複のない構成を1つ選んでパッチを作る。
7. `ci-cd-pipeline/scripts/detect-github-repository.mjs`を最初に実行し、現在のgit remote・追跡remote・`gh repo view`からGitHubのowner/repo/remoteを自動発見する。`status: ok`なら`recommended`を採用し、対象を短く提示してそのまま進む。質問するのは`multiple`・`unconfigured`・`gh_auth_required`のときだけとし、資格情報を含むremote URLやTokenを貼らせない。続いてpackage manager、Wrangler package、Worker/D1/R2名、固定本番URL、既存secret名、Cloudflare/GitHubの状態を自動発見する。利用者へ調査コマンドを丸投げしない。
8. 複数Cloudflare Accountがある新規構築ではチーム用共有Accountを推奨し、既定選択する。個人Accountは明示指定時だけ。既存リソースが個人側なら勝手に複製せず移行判断で停止する。料金プラン変更は承認を得る。
9. `ci-cd-pipeline`のgeneratorを`--auto`で実行し、検出済みの推奨値から`docs/cloudflare-credentials-setup.md`と`.cloudflare/setup-production.mjs`を生成する。Wrangler設定の存在だけで既存resourceと判定せず、read-only照合で所有先を確認できた場合だけ`--account-mode existing`を渡す。未作成なら既定の`team`、利用者が明示した場合だけ`personal`にする。一意に決められない項目だけ明示引数で補い、推測しない。画面名だけの抽象案内は禁止し、クリック先、入力値、成功表示、停止条件、復旧を含める。
10. API Token作成と秘密値入力は所有者本人に残す。Tokenをチャットへ貼らせず、生成済みhelperを1回実行してもらう。AIは値でなく登録名だけを再確認する。既存Worker secretはローテーション承認なしに上書きしない。
11. `CLOUDFLARE_*`は`production` Environment secret、`APP_URL`はRepository variableへ登録する。Deploy/Migrate jobの`environment: production`とmain限定を検証する。
12. スモークテストは先にローカルで通してからCIへ入れる。
13. テストを意図的に1つ失敗させてCIが赤くなることを確認し、確認後は必ず元に戻す。この検証を省略しない。
14. ブランチ保護の必須チェックにはワークフロー名ではなくジョブ名を指定する。永久に Pending となる設定を作らない。
15. DeployはmainのCI成功後に自動起動させ、対象SHA一致、30秒後・90秒後のsmokeまで監視する。手動実行でもテストを迂回させない。
16. 完了後は非エンジニア向けに、自動になったこと、利用者自身が行うことと代行できない理由、費用、自動化しなかったことと理由、技術的詳細の順で報告する。

通常は `Evidence → Decide → Draft → Validate → Diff` で進め、比較案の選択を利用者へ委ねない。質問してよいのは認証情報、課金、公開、本番データ変更など本人しか決められない境界だけであり、その場合もローカル検証済みの成果物を先に示す。
