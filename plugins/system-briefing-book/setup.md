# system-briefing-book setup

## しくみをひとことで

プラグインに入っているのは道具 (手順書、ひな形、検査スクリプト) だけです。案件の素材と、できあがった資料は、素材フォルダの中の `打ち合わせ資料/` にだけ置かれます。案件が変わっても、資料どうしが混ざることはありません。

## 必要なもの

| もの | Mac | Windows |
| --- | --- | --- |
| Node 22 以上 | `node --version` で確認 | `node --version` で確認 |
| ブラウザ | Google Chrome (Microsoft Edge でも可) | Microsoft Edge (最初から入っています) か Google Chrome |
| PDF の道具 (無くてもよい) | `pdftoppm` (PDF から直接切り出すときだけ) | 使いません |

スクリプトは Node に最初から入っている機能だけで動きます。`npm install` や `pip install` は要りません。

## 1. Node を確かめる

`node --version` が `v22` 以上なら、そのまま 2 へ進みます。入っていないか古いときだけ、次のどちらかで入れます。

Mac:

```bash
brew install node
```

Windows (PowerShell):

```powershell
winget install OpenJS.NodeJS.LTS
```

Homebrew や winget を使わない場合は、nodejs.org の LTS 版のインストーラーでも同じです。

PDF から直接切り出したいとき、Mac では `brew install poppler` で `pdftoppm` が入ります。入れない場合や Windows では、PDF のページを画像 (PNG) で保存してから素材として渡してください。`pdftoppm` が無いまま PDF を渡すと、その案内を出して止まります (終了コード 3)。

## 2. ブラウザを確かめる

ボードの PNG 化と画像の切り出しは、Chrome か Edge を画面なしで動かして行います。探す順は [references/execution-contract.md](references/execution-contract.md) の「ブラウザの探し方」を読んでください。

見つからないときは、パスを環境変数で教えます。

```bash
export BRIEFING_BROWSER="/Applications/Google Chrome.app/Contents/MacOS/Google Chrome"
```

```powershell
$env:BRIEFING_BROWSER = "C:\Program Files (x86)\Microsoft\Edge\Application\msedge.exe"
```

## 3. 動くか試す

お手本を作業用の場所へ写して、PNG 化とまとめまで通します。プラグインの中は書き換えません。

Mac:

```bash
P="${CLAUDE_PLUGIN_ROOT:-plugins/system-briefing-book}"
WORK="$(mktemp -d)"
cp -R "$P/examples/sample-haisha" "$WORK/"
node "$P/scripts/validate-briefing-docs.mjs" --dir "$WORK/sample-haisha/打ち合わせ資料" --stage all
node "$P/scripts/render-board-png.mjs" --dir "$WORK/sample-haisha/打ち合わせ資料"
node "$P/scripts/build-briefing-book.mjs" --dir "$WORK/sample-haisha/打ち合わせ資料"
open "$WORK/sample-haisha/打ち合わせ資料/配車表の読み取り_打ち合わせ資料.html"
```

Windows (PowerShell。`$P` には、`.claude-plugin\plugin.json` があるプラグインのフォルダを入れます):

```powershell
$P = "C:\path\to\system-briefing-book"
$WORK = Join-Path $env:TEMP "briefing-try"
New-Item -ItemType Directory -Force $WORK | Out-Null
Copy-Item -Recurse "$P\examples\sample-haisha" $WORK
node "$P\scripts\validate-briefing-docs.mjs" --dir "$WORK\sample-haisha\打ち合わせ資料" --stage all
node "$P\scripts\render-board-png.mjs" --dir "$WORK\sample-haisha\打ち合わせ資料"
node "$P\scripts\build-briefing-book.mjs" --dir "$WORK\sample-haisha\打ち合わせ資料"
Start-Process "$WORK\sample-haisha\打ち合わせ資料\配車表の読み取り_打ち合わせ資料.html"
```

最後の行でまとめ HTML が開きます。途中で止まったときは、終了コードの意味を [references/execution-contract.md](references/execution-contract.md) の「3. 終了コード」で読んでください。

## Mac と Windows の違い

- 文字の幅: Mac と Windows では使う文字が違い、同じボードでも折り返しが変わります。どうするかは [references/execution-contract.md](references/execution-contract.md) の「文字」を読んでください。
- ファイル名: 日本語のファイル名とフォルダ名のまま使えます。Windows ではパスを `"` で囲んでください。
- 終わらないブラウザ: スクリプトはブラウザに終了を伝え、5 秒たっても残っていれば止めます。そのまま待ってください。

## 守ること

- 素材には実名や実データが入ります。資料にそのまま載せるかは、最初に聞くデータの方針 (素材のまま / 伏せる) で決まります。
- 先方に渡すのは `<タイトル>_打ち合わせ資料.html` の 1 ファイルです。外部への参照がないので、メールやチャットでそのまま渡せます。公開リンクを作るサービスや、関係のない外部のサービスへは上げません。
