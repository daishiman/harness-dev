# まずここから(START HERE)

このキットを受け取った方が最初に読むファイルです。下の3手順で「最初の1本」を作れる状態になります。所要時間は約5分です。

## Mac
1. `aidd-agent-kit.zip` をダブルクリックして展開し、できた `aidd-agent-kit` フォルダを開く
2. `install-mac.command` をダブルクリックする(「検証できませんでした」と出て開けないときは `manual-mac.md` の STEP 2)
3. 最後に「続けて開発環境セットアップを実行しますか?」と出たら Enter を押す(`setup-env-mac.command` が動きます)

## Windows
1. ZIP を右クリック → プロパティ → 「ブロックの解除」にチェック → OK。そのあと右クリック → 「すべて展開」
2. できたフォルダの `install-windows.bat` をダブルクリックする(青い画面が出たら「詳細情報」→「実行」)
3. 最後に「続けて開発環境セットアップを実行しますか?」と出たら Enter を押す(`setup-env-windows.bat` が動きます)

## 次にすること
Claude Code と Codex を起動し直して、作りたいものを普通の言葉で頼みます。

    Claude Code: /build-app 社員の勤怠を管理するアプリを作って
    OpenAI Codex: $build-app 社員の勤怠を管理するアプリを作って

手順3の最後に「基本セットアップ完了 / 変更系MCPは必要時に認証」と出ていれば、そのまま始められます。Cloudflare の認証は必要になったときにエージェントが案内します。

## 困ったら
- `manual-mac.md` / `manual-windows.md`(ブラウザで読むなら同名の `.html`)の「うまくいかないとき」
- 入ったものの診断: `doctor-codex-layout.sh`(読み取り専用で、何も消しません)

## このフォルダの他のファイルは読まなくて大丈夫です
`skills/` `agents/` `commands/` `codex/` はエージェントが読む中身です。`README.md` `CODEX-PLACEMENT.md` `INVARIANTS.md` `CHANGELOG.md` は開発者向けです。
