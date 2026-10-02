# 初心者向け案内の規約

## 原則

- 人間の作業を「GoogleでClient作成」「Terminalで1コマンド」「ログイン確認」の3つだけにする。
- 既存設定で不要な画面は説明せず、「初回設定が表示された場合だけ」とする。
- Client ID/Secretは一度だけ、OS共通の非表示Terminal入力へ貼らせる。
- 案内書に絶対パス、ユーザー名、Mac固有の操作、スキルの保存場所を含めない。
- ローカル保存、`.gitignore`、権限、Better Auth Secret生成、Wrangler登録は生成済みスクリプトへ任せる。
- SecretをAI、チャット、コマンド引数、環境変数、Git、ログ、画像へ渡さない。
- Redirect URIは生成済みの完全な値だけをコピーさせる。

## 必ず止める条件

- Google Cloud projectが不明。
- `Internal`が表示されない。
- Wranglerの対象WorkerまたはPages projectを特定できない。
- 実アカウントでのログイン確認が終わっていない。

止まった場合もSecretは受け取らず、エラーメッセージだけを依頼する。
