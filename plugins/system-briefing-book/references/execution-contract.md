# 動かし方の約束

Claude Code と Codex、Mac と Windows のどれでも、同じスクリプトを同じ引数で呼び、同じ結果を得るための約束。

## 1. どちらのホストでも同じ呼び方

- スキルの手順はどれも、plugin の `scripts/` にある Node のスクリプト (`.mjs`) を呼ぶだけ。ホストごとの別の道具を使わない。npm の部品は使わないので `npm install` は要らない。
- 呼び方は 1 つにそろえる。

```bash
node "${PLUGIN_ROOT:-${CLAUDE_PLUGIN_ROOT}}/scripts/<名前>.mjs" <引数>
```

- 引数のパスはすべて絶対パスにし、`"` で囲む (日本語や空白を含むため)。
- スクリプトは自分の場所から plugin の場所を決める (`import.meta.url` の 1 つ上)。今いるフォルダ (cwd) には左右されない。

### PLUGIN_ROOT の決め方

| ホスト | 決め方 |
| --- | --- |
| Claude Code | `CLAUDE_PLUGIN_ROOT` をそのまま使う |
| Codex | ホストが示した `SKILL.md` の絶対パスから上へたどり、`.claude-plugin/plugin.json` (か `.codex-plugin/plugin.json`) を持つフォルダを `PLUGIN_ROOT` にする |
| どちらでも | 今いるフォルダから推測しない。`<PLUGIN_ROOT>` のような置き換え前の文字をそのまま shell に渡さない。shell を呼ぶたびに、決めた絶対パスを `PLUGIN_ROOT` に入れる |

```bash
# ホストが示したパスから解決した PLUGIN_ROOT を使用する (個人の配置先を固定しない)
node "$PLUGIN_ROOT/scripts/validate-briefing-docs.mjs" --dir "/path/to/素材/打ち合わせ資料" --stage all
```

### ホストの違いが出る所

| 所 | Claude Code | Codex |
| --- | --- | --- |
| 入口 | `/briefing-build`、`/briefing-revise`、Skill run-briefing | `$run-briefing new ...` / `$run-briefing revise ...` |
| 質問 | AskUserQuestion | 同じ形の質問を文で出す (選択肢、先頭が「(おすすめ)」) |
| 独立レビュー | Skill assign-briefing-evaluator (fork) が briefing-reviewer を動かす | 別の会話 (別のエージェント) で briefing-reviewer.md の内容を渡す |
| PNG を目で見る | Read で PNG を開く | 画像を開ける道具で開く |

どちらでも、書くファイル、通す検査、止まる確認点は同じ。

## 2. スクリプトと引数

| スクリプト | 呼ぶスキル | 主な引数 |
| --- | --- | --- |
| build-briefing-scaffold.mjs | run-briefing、run-briefing-boards | `init --materials <素材> --title <タイトル> [--out] [--palette] [--date] [--data-policy source\|masked] [--refresh-css]` / `boards --dir <資料>` |
| validate-briefing-docs.mjs | ほぼ全スキル | `--dir <資料> [--stage hearing\|requirements\|spec\|pages\|all]` |
| extract-source-crop.mjs | run-briefing-boards | `--src <pdf\|画像> [--page N] [--dpi 200] (--box x,y,w,h \| --rel x,y,w,h) --out <png> [--max-width 1600]` / `--info` |
| render-board-png.mjs | run-briefing-boards、assign-briefing-evaluator | `--dir <資料> [--only NN ...] [--browser <path>] [--check-only] [--allow-warn]` |
| build-briefing-book.mjs | run-briefing-book | `--dir <資料> [--out <file>] [--allow-stale]` |
| compare-briefing-profile.mjs | run-briefing | `--dir <資料> [--profile <json>]` (基準点は `assets/data/target-profile.json`) |
| count-csv-columns.mjs | run-briefing-boards | `--src <csv> [--encoding auto\|utf-8\|shift_jis]` |

- 結果は stdout に JSON 1 個。人向けの言葉は stderr。`--quiet` で要約 1 行。
- 検査の中身は `_check/` に残る (materials.json、docs.json、boards.json、book.json、profile.json)。count-csv-columns.mjs は stdout だけで、ファイルを書かない。

## 3. 終了コード

| コード | 意味 | スキルがすること |
| --- | --- | --- |
| 0 | 正常 | 次へ進む |
| 1 | 検査で問題あり | `_check/*.json` の errors を見て直し、もう一度通す |
| 2 | 使い方の誤り (引数、フォルダが無い) | 呼び方を直す。直せないときは止まって伝える |
| 3 | 必要な道具かファイルが無い (Node 22 以上、ブラウザ、PDF の道具、plugin の `assets/data/quality-thresholds.json` か `assets/templates/book.html`) | 下の「入れるもの」を利用者に伝えて止まる。勝手に入れない。plugin の中のファイルが読めないときは plugin を入れ直す |

validate-briefing-docs・build-briefing-book・build-briefing-scaffold は warn だけなら exit 0。render-board-png だけは warn でも exit 1 にする (見た目の崩れを最初の版に残さない)。独立レビューで検査だけするときは `--allow-warn` を付けて exit 0 にし、warn は指摘として読む。
render-board-png の報告 (`notices`。TEXT-LONG・NOTES-MANY) は exit に効かない。compare-briefing-profile は基準点との差があっても exit 0 (差は表で返す)。

## 4. Mac と Windows

### 入れるもの

| もの | Mac | Windows |
| --- | --- | --- |
| Node | 22 以上。`node --version` | 22 以上。`node --version` |
| ブラウザ | Google Chrome か Microsoft Edge | Microsoft Edge (最初から入っている) か Google Chrome |
| PDF の道具 (PDF を切り出すときだけ、無くてもよい) | `brew install poppler` で入る `pdftoppm` | 使わない。PDF のページを画像 (PNG) で保存して渡す |

ブラウザを使うのは render-board-png.mjs と extract-source-crop.mjs だけ。build-briefing-scaffold.mjs、validate-briefing-docs.mjs、build-briefing-book.mjs、compare-briefing-profile.mjs、count-csv-columns.mjs は Node だけで動く。

### ブラウザの探し方

render-board-png.mjs と extract-source-crop.mjs は、`--browser <パス>` → 環境変数 `BRIEFING_BROWSER` → いつもの置き場所 の順で探し、最初に見つかったものを使う。
いつもの置き場所の一覧は `scripts/lib/browser-session.mjs` の `browserCandidates` を読む。

見つからないと exit 3。場所を環境変数で教える。

```bash
export BRIEFING_BROWSER="/Applications/Google Chrome.app/Contents/MacOS/Google Chrome"
```

```powershell
$env:BRIEFING_BROWSER = "C:\Program Files (x86)\Microsoft\Edge\Application\msedge.exe"
```

### 文字

- Mac はヒラギノ、Windows は游ゴシック UI かメイリオで描かれる (tokens.css の `--font-ui`。jp-web-design と同じ束)。
- 文字の幅が違うため、同じボードでも折り返しが変わる。資料を作った PC で PNG と検査を通す。別の PC で作り直したときも通し直す。
- Windows で CLIPPED が出たら、文字を小さくせず (小さくすると FONT-SMALL で止まる) 文を短くする。

### ファイル名とパス

- 日本語のファイル名・フォルダ名のまま使える。パスは必ず `"` で囲む。
- まとめ HTML のファイル名に使えない文字 (`\ / : * ? " < > |`) は `_` に置き換わる。
- まとめ HTML を開く: Mac は `open "<ファイル>"`。Windows の PowerShell は `Start-Process "<ファイル>"`、コマンドプロンプトは `start "" "<ファイル>"`。

## 5. 守ること

- 素材には実名や実データが入る。資料にそのまま載せるかは briefing.json の `data_policy` で決まる ([quality-rules.md](quality-rules.md) の「名前と値の扱い (data_policy)」)。
- 先方にまとめ HTML を渡すのはよい。資料を、公開リンクを作るサービスや、関係のない外部のサービスへ上げない。
- スクリプトは外へ通信しない。ボードもまとめ HTML も外の URL を読まない (EXTERNAL-REF で止まる)。
- plugin の中 (`assets/`、`examples/`) を書き換えない。試すときは作業用の場所へ写してから。

## 6. 通常生成と確認の選択所有

この節を L1/L2 共通の実行契約の正本とする。通常生成の工程を、任意の独立レビューの選択待ちにしない。

- L1 `run-briefing` が確認点1〜3の現物提示と `_check/choices.json` の選択を所有する。状態遷移は確認点ごとに適用する。`accept-as-is` はその確認点のレビューを完了し、次の通常工程へ進む。資料全体の生成を打ち切らない。
- L2 `run-briefing-hearing`・`run-briefing-docs`・`run-briefing-boards`・`run-briefing-book` は、呼ばれた通常生成と既存の検査を選択前から実行する。main context で順に進める。単独呼出しでは成果物と検査結果を報告して終了し、確認の深さを独自に聞かない。必要な入力の聞き取りは通常生成に含む。
- `light` / `standard` / `detailed` の選択で開始するのは独立レビューとその指摘に基づく改善だけ。確認点の選択前に evaluator・task fork・subagent・multi-worker・評価起点の反復を開始しない。通常の検査エラー修正や明示された revise を独立レビュー扱いにしない。
- L2 は選択を保存・再要求しない。親が選んだレビューの対象として呼ばれた場合だけ、その対象範囲の指摘を直して親に返す。`assign-briefing-evaluator` は親が渡した深さを使う。
- 工程5の描画と工程6のまとめは、既存検査を通れば自動で進む。release / exhaustive の自動昇格は行わない。

実行場所と終了コードは本書の1・3節を参照し、各スキルには固有の例外だけを書く。
