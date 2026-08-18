# guide-doc-generator

初心者・非エンジニア向けのレクチャー資料や導入ガイドを、**外部依存ゼロの単一 HTML ファイル**として生成するプラグインです。

出来上がるのは `.html` が 1 つだけ。画像も CSS も JavaScript もその中に入っているので、メールに添付しても、USB で渡しても、ネットに繋がっていない会議室で開いても、見た目が崩れません。ブラウザの印刷から A4 の紙にもそのまま出せます。

## この plugin が引き受ける仕事

資料づくりには「中身を考える仕事」と「形を保つ仕事」があります。この plugin は**形を保つ仕事だけ**を機械へ寄せます。

| あなた (と AI) がやること | この plugin がやること |
|---|---|
| 誰に何を伝えるかを決める | その中身を単一 HTML へ組み上げる |
| 難しい言葉の言い換えを決める | 言い換えが本文の初出に付いているか検査する |
| 順番と例を決める | 抽象と具体が交互に出ているか検査する |
| — | 外部 URL・絵文字の混入を止める |
| — | 画面読み上げ対応と A4 印刷の崩れを検査する |
| — | 出力先のフォルダ名を日付と主題から決める |

中身を組み立てる段階には AI が入りますが、**構成データから HTML を作る段階には AI を一切入れません**。ここに AI を挟むと、同じ入力から同じ HTML が出る保証が消えて、「昨日と同じものをもう一度作る」ができなくなるためです。

### 用語

- **構成データ** — 資料の中身と部品の選び方を書いた JSON ファイルのこと。この plugin の唯一の入力正本で、生成も検証も逆抽出もこの 1 つの形だけを見ます。
- **data URI** — 画像や添付ファイルを文字列に変換して HTML の中へ直接埋め込む書き方のこと。これのおかげで外部ファイルが不要になります。
- **round-trip (逆抽出)** — 出来上がった HTML から構成データを取り出し、それでもう一度生成しても同じ資料になること。
- **ゲート** — 生成物が条件を満たすかを機械で判定する検査のこと。この plugin には 4 つあります。

## インストール

2 通りあります。どちらでも同じものが入ります。

### A. marketplace から入れる (通常はこちら)

```bash
claude
```

Claude Code を起動したら、次を順に実行します。

```
/plugin marketplace add daishiman/harness-dev
/plugin install guide-doc-generator@skills
```

すでに marketplace を追加済みなら 2 行目だけで足ります。更新は次のとおりです。

```
/plugin marketplace update skills
/plugin update guide-doc-generator
```

### B. リポジトリを clone してローカルで使う (開発者向け)

```bash
git clone https://github.com/daishiman/harness-dev.git
cd harness-dev
make sync
```

`make sync` が `.claude/` 配下へ skills / agents / commands を展開します。展開後は marketplace 経由と同じスラッシュコマンドが使えます。

clone 版で `/plugin` からも入れたい場合は、リポジトリの中にローカル marketplace を組み立てられます。

```bash
python3 scripts/build-local-marketplace.py
```

生成された `marketplaces/local` を `/plugin marketplace add ./marketplaces/local` で追加します。

### C. 書込ガードを有効にする (任意・手作業)

生成した資料を後から手で編集したとき、うっかり外部 URL や絵文字が混ざるのを書込直後に知らせる hook があります。**この登録だけは自動では入りません。** 導入環境の `.claude/settings.json` (プロジェクト単位) か `~/.claude/settings.json` (利用者単位) の `hooks.PostToolUse` へ次を足してください。

```json
{
  "matcher": "Write|Edit",
  "hooks": [
    {
      "type": "command",
      "command": "python3 \"${HB_ROOT:-${CLAUDE_PLUGIN_ROOT}}/hooks/guard-handout-external-ref.py\"",
      "timeout": 10
    }
  ]
}
```

plugin 側の manifest には意図的に書いていません。manifest と settings.json の両方に置くと 1 回の書込で 2 回発火するためで、登録面を settings.json の 1 か所に寄せています。

なお登録しなくても資料の正しさは守られます。この hook は水際の早期通知であって、最終的な判定は生成時の 4 つのゲート (後述) が持つ二重防御の外側です。発火するのは「`YYYY-MM-DD-` で始まるフォルダの中にあり、同じ階層に `handout-config.json` がある `.html`」だけで、それ以外のファイルには何もしません。

### 動作要件

- Python 3.10 以上 (標準ライブラリのみ。追加の pip install は不要です)
- Claude Code

画像の自動生成だけは `slide-report-generator` plugin に任せています。入っていなくても資料は完成します — 画像の生成手順だけが skip され、その理由が報告に残ります。

## 使いかた

### 1. 題材を言って作る (いちばん短い道)

```
/handout-build 生成AIで月次集計を頼めるようになる勉強会の資料
```

このあと、対話で次を聞かれます。答えるだけで構成データが組み上がります。

- 誰が読むか / その人はどこまで知っているか
- 読み終えたら何ができるようになってほしいか
- どの業務に紐づくか / 何分の資料か
- 覚えてほしいこと / 覚えなくていいこと

最後に、出力先のフォルダのパスと、4 ゲートの結果が表示されます。

### 2. 用途を指定する

用途種別を先に決めておくと、その用途に合ったセクションの骨格から始まります。

```
/handout-build 新入社員向けの経費精算ガイド --doc-type onboarding
```

選べる用途種別の一覧は次のコマンドで出ます。README にはあえて書き写していません — 語彙の正本は `config/` 側の 1 か所だけに置き、増減したときに README が古いまま残る経路を作らないためです (この規律は `resolve-handout-preset.py --audit-duplication` が機械で見張っています)。

```bash
HB="${HB_ROOT:-${CLAUDE_PLUGIN_ROOT:-plugins/guide-doc-generator}}"
python3 "$HB/scripts/resolve-handout-preset.py" --list
```

### 3. 構成データを直接渡す (対話なし)

すでに構成データがあるなら、ヒアリングを飛ばして生成だけできます。同じ資料をもう一度作るときや、自動実行に組み込むときはこちらです。

```
/handout-build --config ./handout-config.json
```

構成データに書かれた値は常に `--doc-type` / `--theme` / `--date` より優先されます。両方に書くと、黙って片方を捨てず**その場で停止**します。

### 4. 出来上がったものを検証する

```
/handout-verify ./20260818-lecture-monthly-close/handout.html --config ./20260818-lecture-monthly-close/handout-config.json
```

4 つのゲートが `pass` / `fail` / `error` / `not-run` の 4 状態で報告されます。`--config` を渡さないと言語ゲートと語りゲートが実行できず `not-run` になります。**`not-run` は `pass` ではありません** — 表から省かれることもありません。

### 5. 既存の HTML から構成データを取り出す

```
/handout-extract ./既存の資料.html --out ./handout-config.json
```

この plugin が作った HTML なら、ほぼそのまま構成データへ戻ります。手書きの HTML でも構造は取り出せますが、書き手の意図 (各セクションの狙い・判断軸・用語の言い換え) は HTML に残っていないため復元できません。**復元できなかった項目は空欄のまま、「どの項目が / なぜ復元できなかったか」の一覧付きで返します。** 推測で埋めた値と HTML から読んだ値はレポート上で必ず区別されます。

取り出した構成データはそのまま `/handout-build --config` へ渡せます。

## 出力されるもの

出力先のフォルダは日付と主題から自動で決まります。出力先のルートは **`--out-dir` > 環境変数 `HB_OUT_DIR` > `config/handout-output.json` の `default_out_dir`** の順に強く、いずれも無ければエラーで止まります (勝手な場所へは書きません)。

配布時の既定値は `./handout-output` (コマンドを実行したフォルダの直下) です。**いつも同じ場所へ貯めたい場合は環境変数を設定してください。**

```bash
# 例: Obsidian の資料フォルダへ固定する (~/.zshrc などに書く)
export HB_OUT_DIR="$HOME/dev/dev/ObsidianMemo/05_Project/資料作成"
```

`config/handout-output.json` を書き換える方法もありますが、そのファイルは配布物なので、**個人の絶対パスは環境変数側に置くことを推奨します** (他の人が install したときに知らない場所へ書きに行くのを防ぐため)。

```
2026-08-18-lecture-monthly-close/
├── handout.html          ← 配布するのはこれ 1 つ
├── handout-config.json   ← 再生成に使う構成データ (採用テーマも書き戻される)
└── gate-summary.json     ← 4 ゲートの結果
```

`handout.html` が持っている機能は次のとおりです。

- 常に横に出ている目次 (スクロールしても消えません)
- 画像をクリックすると拡大表示
- 読みながら書けるメモ欄 (ブラウザに保存され、Markdown で書き出せます)
- 添付ファイルのダウンロードボタン (ファイル本体も HTML の中に入っています)
- 絵文字を使わない SVG アイコン (フォントが無い環境でも図記号が化けません)

## 構成データを自分で書く

最小の例が `examples/minimal-config.json` にあります。そのまま生成できることを確認済みです。

```bash
HB="${HB_ROOT:-${CLAUDE_PLUGIN_ROOT:-plugins/guide-doc-generator}}"
python3 "$HB/scripts/validate-handout-config.py" --config "$HB/examples/minimal-config.json" --normalize --out ./normalized.json
python3 "$HB/scripts/render-handout.py" --config ./normalized.json --out ./handout.html
```

`--normalize` は、書き忘れた既定値 (日付・詳しさ・根拠の深さなど) を埋めて、正式な形へ整えます。**生成に渡すのは正規化した後のファイル**です。

### セクションと部品

資料は「セクション」の並びで、各セクションは「部品」の並びです。使える部品は 20 種類あります。

| id | 名前 | 使いどころ |
|---|---|---|
| B01 / B02 | sticky ナビ / ヒーロー | 資料全体に 1 つ。自動で入ります |
| B03 | ステップ行 | 順番のある手順 |
| B04 | トリオカード | 並列な 3 点 |
| B05 | 比較表 | 選択肢の違い |
| B06 | 二択グリッド | どちらかを選ぶ場面 |
| B07 | 特徴カード | 特徴の列挙 |
| B08 | 選択マップ | 条件による分岐 |
| B09 | チェック行 | 事前準備の確認 |
| B10 | アコーディオン | 読み飛ばしてよい詳細 |
| B11 | プロンプト箱 | そのまま貼れる指示文 |
| B12 | DL ボタン | 添付ファイルの配布 |
| B13 | タブ | 環境別の手順 |
| B14 | フロー | 処理の流れ |
| B15 | 選択チップ | 頻度・規模などの選択肢 |
| B16 | アクションアイテム行 | 担当と期限つきの宿題 |
| B17 | ハンズオン手順 | その場で手を動かす手順 |
| DIAGRAM | 概念図解 | 関係の図示 (SVG を自動生成) |
| IMG | 画像 + lightbox | 実画面のスクリーンショット |
| TEXT | 素テキスト段落 | 地の文 |

部品 id の正本は `config/handout-parts.json` です。この README を含め、他の場所に一覧を持ちません — 追加や改名はそのファイル 1 つを直します。

### 通しやすくするコツ

検査に落ちやすいのは次の 3 つです。理由も併せて書いておきます。

1. **難しい言葉は、本文の初出のすぐ後に括弧で言い換える。** `glossary` に登録しただけでは通りません。読み手は用語集を先に読まないからです。
2. **前提知識が `none` の資料は、最初に実画面を出す。** この場合 `presentation_order` は自動で `demo_first` になり、セクション先頭に置けるのはスクリーンショット (IMG) か `live_demo: true` の B17 だけになります。説明から入ると、読み手は何の話か分からないまま文字を追うことになります。
3. **本編の各セクションは、全体ゴールと具体業務の両方に紐づける。** `ties_to` に `"goal"` (または `"focus_theme:0"`) と `"target_task:<id>"` を両方入れます。どちらか欠けると「何のためにこの節があるのか」が読み手に伝わりません。

## 4 つのゲート

| ゲート | 見ているもの | 落ちたときの意味 |
|---|---|---|
| selfcontained | 外部 URL と絵文字の混入 | オフラインで開くと崩れる / フォント次第で図記号が化ける |
| a11y-print | 画面読み上げ対応と A4 印刷 | 読み上げで意味が取れない / 紙で切れる |
| language | 用語の言い換えと日付表記 | 初心者が読めない語が残っている |
| narrative | ゴールの連なりと提示順 | 節と全体ゴールの筋道が切れている |

個別に叩くこともできます。

```bash
HB="${HB_ROOT:-${CLAUDE_PLUGIN_ROOT:-plugins/guide-doc-generator}}"
python3 "$HB/scripts/verify-handout-selfcontained.py" --html ./handout.html
python3 "$HB/scripts/verify-handout-a11y-print.py"    --html ./handout.html
python3 "$HB/scripts/verify-handout-language.py"      --html ./handout.html --config ./normalized.json
python3 "$HB/scripts/verify-handout-narrative.py"     --html ./handout.html --config ./normalized.json
```

`W-` で始まる行は警告で、失敗には数えません。失敗は終了コードと `E-` / `FAIL` の行で判定します。

なお、書き込み時に働く hook が 1 つ入っています。資料 HTML へ外部 URL や絵文字が混ざった書き込みが起きると、その場で検出して知らせます。判定規則は selfcontained ゲートと同じものを呼んでいるので、hook と最終ゲートの判定が食い違うことはありません。

## 困ったとき

| 症状 | 見るところ |
|---|---|
| `E-SECTION-UNTIED-GOAL` / `E-SECTION-UNTIED-TASK` | セクションの `ties_to` に `"goal"` と `"target_task:<id>"` を両方入れる |
| `E-ATTAINMENT-UNREACHED` | どのセクションの `attainment_step` も宣言した到達段に届いていない |
| `LANG-01 FAIL` | その語の初出の直後に括弧書きの言い換えを入れる |
| `NAR-07 FAIL` | `demo_first` の資料で説明から始めている。先頭を IMG か `live_demo: true` の B17 にする |
| 画像が生成されない | `slide-report-generator` が未導入。資料は完成しているので、画像だけ後から差せる |
| スクリプトが見つからない | `HB_ROOT` を plugin のディレクトリへ設定する。Claude Code の中からは自動で解決される |

## 中を知りたい人向け

| 場所 | 中身 |
|---|---|
| `schemas/handout-config.schema.json` | 構成データの形の正本 |
| `schemas/ROUNDTRIP-CONTRACT.md` | 逆抽出で何を等価とみなすかの裁定 |
| `config/handout-parts.json` | 部品 id の語彙の正本 |
| `config/handout-purposes.json` | 用途種別とプリセットの正本 |
| `config/handout-output.json` | 既定出力先と素材サイズ上限 |
| `plugin-composition.yaml` | 公開 capability と不変条件の宣言 |
| `tests/` | 4 スイート 836 件 (Python 標準 unittest のみ) |

テストは次で回せます。

```bash
HB="${HB_ROOT:-${CLAUDE_PLUGIN_ROOT:-plugins/guide-doc-generator}}"
for d in "$HB"/tests/*/; do (cd "$d" && python3 -m unittest discover -q); done
```
