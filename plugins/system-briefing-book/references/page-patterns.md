# ページの型とボードの部品

打ち合わせ資料のボード (1 枚 = 1 ページ) は、下の 7 種類の型だけで組む。
雛形は plugin の `assets/templates/board-<型>.html`、部品の見た目は `assets/css/common.css`、色は `tokens.css` にある。見た目の既定は aidd-agent-kit の jp-web-design (標準カラーとその規範) で、組み立て方は [standard-attribution.md](../assets/css/standard-attribution.md) にある。

## 1 枚のボードの決まり

- 大きさは [quality-thresholds.json](../assets/data/quality-thresholds.json) の `board.width` x `board.height`。PNG はその `board.scale` 倍。
- ボードは直感的に分かる画面構成・操作・状態に絞る。処理境界・保存方式・認証の内部処理・安全対策・稼働構成は仕様書4〜7章へ残す。必要なら仕様節を指す短い1行を添える。
- 伝えることは 1 つ。briefing.json の `message` (文は 2 つまで。2 文目は 1 文目の補足) が、いちばん大きく見える所に出ている。
- 見出しは kicker・h1・lead の 3 段。
  - kicker: 「区分 ・ 順番」。h1 と同じ言葉にしない (KICKER-SAME)。雛形 (`build-briefing-scaffold.mjs boards`) が型から入れる。文字の正本は同じスクリプトの `KICKERS` と `kickerFor`。
  - h1: ページの題。phone / pc は仕様書の画面名と同じにする。
  - lead: briefing.json の `message` をそのまま使う (雛形が入れる)。言い換えたくなったら message のほうを直す。
- meta に案件名を置く。briefing.json の `data_policy` が `masked` のときだけ、続けて `<span class="sample-flag">画面の中の名前と値は例です</span>` を置く。雛形 (`build-briefing-scaffold.mjs boards`) が `{{SAMPLE_FLAG}}` を埋める。名前と値の扱いは [quality-rules.md](quality-rules.md) の「名前と値の扱い (data_policy)」を読む。
- 色・文字・余白は `var(--...)` だけ。`#1a2b3c` や `rgb()` を書くと RAW-COLOR で止まる。
- jp-web-design の規範に従う。画面の地は白。カードの縁に色帯を付けない (分類と状態はチップ・点・進捗バーと言葉で示す。ナビの選択線と表の選択行の左線は可)。アイコンを自作しない。リンクは色と下線。数字は `--font-num` で桁をそろえる。注目させる色の面は 1 枚に 1〜2 か所まで。
- 外の URL (画像、フォント、スクリプト) を読まない。画像は `_src/assets/` に置く。
- スクリプトを書かない。PNG にするとき動かないため。

## 骨組み

```html
<div class="board" data-board="02" data-type="phone" data-screens="S01">
  <header class="board-head">
    <div>
      <div class="kicker">画面 1 / 4 ・ スマホ</div>
      <h1>配車表を送る</h1>
      <div class="lead">紙を撮って送るだけ。入れるのは日付だけで、それも最初から入っている。</div>
    </div>
    <div class="meta">配車表の読み取り<br><span class="sample-flag">画面の中の名前と値は例です</span></div>
  </header>
  <main class="board-body">
    <div class="stage"> 図や画面 </div>
    <aside class="notes">
      <div class="reqs"><span class="req" data-req="F01">F01 配車表を撮って送る</span></div>
      <ol class="marks">
        <li data-mark="1" data-kind="can"><b>ひとこと</b><span class="sub">説明 1〜2 行</span></li>
      </ol>
    </aside>
  </main>
</div>
```

- お手本 `examples/sample-haisha/打ち合わせ資料/_src/02_s01-send.html` の頭の部分。お手本は `masked` なので札がある。
- `.board` は 1 個だけ。`data-board` はページ番号 (2 桁)、`data-type` は型、`data-screens` は画面番号 (複数は `S02 S03`)。
- `data-board` `data-type` `data-screens` は briefing.json の pages と同じにする。no と type がずれると BOARD-ATTR (error)、screens がずれると BOARD-SCREENS-MISMATCH (warn)。

## 注記 (notes)

| data-kind | 表示 | 書くこと |
| --- | --- | --- |
| `can` | できること | 使う人が画面でできること |
| `how` | しくみ | 操作後に何が表示され、状態がどう変わるか。内部実装は書かない |
| `ask` | 決めること | 打ち合わせで決めたいこと。`<span class="q">Q03</span>` に 要件定義.md 9 章の番号 |

- 1 ボード `board.notes_note` 個を目安にする。超えると NOTES-MANY (報告。止まらない)。
- `<b>` はひとこと (20 字まで目安)、`.sub` は説明 (2 行まで)。種類のラベルは CSS が出すので HTML に書かない。
- `ask` の `.sub` は「案: <9 章の案>。<なぜか、どう確かめるか>」。言い回しのお手本は run-briefing-boards の [board-copy.md](../skills/run-briefing-boards/references/board-copy.md)。
- 画面の中の場所を指すときは、場所の要素に `anchor` を付け、その中に `<i class="mk" style="right:..;top:..">1</i>` を置く。番号は注記の `data-mark` とそろえる (MARK-MISMATCH)。
- どの注記にも印を置く (置き忘れも MARK-MISMATCH)。
- 要件定義 9 章のまだ決まっていない Q は、話の出てくるボードの右に `ask` で置く。1 つの Q を何枚に置いてもよい。出てくるボードが無い Q は 9 章だけでよい。
- 印どうしが重なると MARK-OVERLAP。位置を少しずらす。

## 端末の画像を他のボードで使う (data-export)

- phone / pc のボードで、端末の枠に `data-export="s01-send"` を付ける (英小文字・数字・`-`。ファイル名の slug と同じにする)。
- render-board-png.mjs がその部分を幅 520 の PNG にして `_src/assets/export/s01-send.png` に置く。
- overview や screen-map では `<img src="assets/export/s01-send.png">` で使う。手で描き直さない。
- 同じ名前を 2 か所に付けない (EXPORT-DUP)。使う名前を付け忘れると EXPORT-UNKNOWN。

## 判断材料の部品

読む人が判断するための材料 (今の手間の数字、本物の紙、CSV の列の区分、要件の札) を置く部品。色は CSS が付けるので、HTML には色を書かない。`style` に書いてよいのは `flex:<数>` だけ。

| 部品 | 置く型 | HTML の形 | 数 |
| --- | --- | --- | --- |
| 今の手間の数字 | overview | `<div class="facts"><div class="fact"><b>40 枚</b><span>月に書く配車表</span><small>聞き取り:H02</small></div>…</div>` | 3 個まで |
| 要件の札 | phone、pc (mechanism と future でも置いてよい) | `<div class="reqs"><span class="req" data-req="F01">F01 写真を送る</span>…</div>` を `aside.notes` の先頭 (`ol.marks` の前) に置く | そのボードの画面に当たる 要件定義 6 章の行すべて |
| 列の区分の棒 | data-map | `<div class="bar"><span class="seg" data-kind="paper" style="flex:9">紙から 9</span>…</div><ul class="legend"><li data-kind="paper">紙から読む</li>…</ul>` | 区分は下の 5 つ |
| 素材の印 | どの型でも | 素材の紙や画面を見せる要素 (img かその枠) に `data-source="<素材のファイル名>"` | 素材を見せる所すべて |

- `.fact` の `<small>` は根拠。書き方は [document-structure.md](document-structure.md) の「根拠の書き方」と同じ。
- `.req` の `data-req` は 要件定義 6 章の F 番号。6 章に無い番号は REQ-TAG-UNKNOWN (error)。6 章で 最初の版 `○` の行に札が無いと REQ-TAG-MISSING。札の言葉は 6 章の できること を短くしたもの。
- 列の区分 (`data-kind`): `paper` 紙から読む / `auto` しくみが入れる / `fixed` いつも同じ値 / `blank` 空欄のまま / `ask` 決めること。`flex` の数は列の数。
- 列の数は `count-csv-columns.mjs` で数える (空の列、いつも同じ値の列、それ以外)。紙から読むか、しくみが入れるか、決めることかは、素材と聞き取りから作る人が決める。
- 素材の印は、`data_policy` が `masked` で素材を架空の図に描き直したときも、元の素材のファイル名を書く。

## 7 種類の型

### overview 全体図

- 何のページか: このシステムで「こういうことがやれます」を 1 枚で見せる。
- 中身:
  - できること 3〜5 個。数と言い回しは 要件定義.md の 3.1 と同じ。
  - 全体の流れ 3〜6 段。人の段は `chip.person`、しくみの段は `.step.system` と `chip.system`。
  - 今の手間の数字 (`.facts`) を 3 個まで。聞き取りか素材にある数だけを使う。
  - 素材の紙の小さな絵を置くときは、`data-source` を付ける。
  - 画面の小さな絵は `.thumb-ph` の代わりに `<img src="assets/export/<名前>.png">` を置いてよい。
- 置かないもの: 広げる案 (仕様書 8 章へ)。

### screen-map 画面の一覧と流れ

- 仕様書 1 章の画面番号・画面名・端末と同じものを、使う順に並べる。`docs.screens_warn` 画面まで。
- 矢印のラベルは「何をすると次へ進むか」(例: 「送る」)。
- `.shot .thumb-ph` は、各画面のボードの `data-export` の切り出し画像に置き換える。画面はすべて phone か pc のボードがあるので、どの画面も切り出しを使える。render は端末のボードを先に描いてからこのボードを描く。

### phone 画面 (スマホ)

- 1 枚に 1〜2 台 (`.phone-wrap` を写す)。3 台以上にしない。
- 部品: `.island` `.status` `.mbar` (アドレス欄)、`.site-head` (上の帯)、`.app-body`、`.ptitle` (画面の題)、`.field` (`.lab` 項目名、`.input` 入力欄、`.why` 補足)、`.app-foot` (`.btn.btn-primary` 主なボタン 1 つ、`.hint`)、`.homebar`。
- 項目名とボタンの文言は 仕様書 3 章の項目表・操作表と同じにする。
- 画面の中の値は「名前と値の扱い (data_policy)」に従う (`source` は素材の値、`masked` は素材の形をまねた例の値)。項目表の「例」とそろえる。
- 要件の札 (`.reqs`) を `aside.notes` の先頭に置く。

### pc 画面 (PC)

- 骨組みは 上の帯 (ヘッダー) / 左のメニュー / 本文 / 下の帯 (フッター)。仕様書 2 章に合わせる。
- 左のメニューは 5 個まで。今の画面に `.on`。
- 主なボタンは 1 つ (`.btn-primary`)。ほかは `.btn-secondary` か `.btn-quiet`。
- 他のボードで使う画面は `.browser` に `data-export` を付ける。
- 画面の中の値と要件の札は phone と同じ。

### data-map データの対応

- 紙や CSV と画面の対応を見せる。必要なときだけ置く (置く条件は [workflow.md](workflow.md) の「既定のページ構成」を読む)。
- 左に素材の切り出し (`extract-source-crop.mjs` で作り、`.thumb-ph.paper` を置き換える)。`data-source` を付ける。`masked` で実名が写るときは架空の図に描き直す。
- 右に 1 項目 1 行で「素材の欄 → 画面の項目」と根拠。15 行まで。
- 書き出す列の区分を、列の区分の棒 (`.bar` と `.legend`) で見せる。
- 読み取れない欄は `.mrow.warn` にし、`決めること:Qxx` を付ける。

### mechanism しくみ

- 必要なときだけ置く (置く条件は [workflow.md](workflow.md) の「既定のページ構成」を読む)。
- 利用者が理解する動作と状態を3〜5段で見せる (例: 写真を送る → 読み取り中 → 確認待ち → 確認済み)。処理の呼出し関係や保存の構成図にしない。
- 各段に「だれが (人 / しくみ)」と、見える入力・結果を置く。R番号の技術的な詳細を転記せず、画面上の変化に結びつける。
- 描くのは、仕様書 5 章の決まり (R 番号) か、8 章の候補 (あとで に回した `要望` のしくみ) のどちらか。
  - 5 章のとき: 段は R 番号とそろえる。
  - 8 章の候補のとき: 段は 8 章の候補の動きにそろえる。kicker は、雛形が入れた「見えない部分」を「次の版の候補」に書き換え、残った「見えない部分」のボードの番号を数え直す (1 枚だけなら番号を外す)。`ask` の注記を置いてよい (要件定義 9 章の Q 番号を付ける)。

### future 将来の広げ方

- 置くのは、ヒアリングの「先々、広げたいことはありますか」で「先々の広げ方を 1 枚のボードでも見せる」を選んだときだけ。既定では置かない。
- `.steps` の 3 段: 最初の版 → 次の版 → その先。候補は 仕様書 8 章の 時期 で振り分け、合わせて 4 個まで。
- 最初の版の段には、要件定義3.1の操作と得られる結果を置く。備えのデータ設計は仕様書8章に残し、画面やボタンを足さない。
- 次の版・その先の段は、候補ごとに名前と利用者ができること1文。仕様書8章と範囲をそろえ、備えの技術的詳細は転記しない。
- 注記は 3 個まで。要件の札は置いてよい。

## 迷ったとき

- 型に収まらない図を描きたくなったら、まず 7 種類のどれかで言えないかを考える。
- 1 枚に収まらないときは、文字を小さくせず、ページを分けるか注記を減らす。
- 広げる案 (仕様書 8 章の候補) は、画面のボードに描かない。
