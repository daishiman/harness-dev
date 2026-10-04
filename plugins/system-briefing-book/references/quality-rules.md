# 品質の基準

打ち合わせ資料を 4 つの観点で確かめる: シンプルさ・正確さ・言葉・見た目。
数で決まるものは検査スクリプトが調べる。数で決まらないものは、作る人が目で確かめ、確認点では briefing-reviewer が別の目で確かめる。
シンプルさは、必要な業務・安全・運用の条件を保ちながら、重複と読む人が考える量を減らすこと。正確さや必要情報の保持を犠牲にしない。
ここに載せる検査コードは、判断が要るものだけ (メッセージだけでは直し方が決まらないもの)。ほかのコードは、スクリプトが出すメッセージが正本。

## しきい値

正本は plugin の `assets/data/quality-thresholds.json`。スクリプトはそこから読む。値はそのファイルで見る。

| キー | 超えたとき |
| --- | --- |
| `board.width` x `board.height` (PNG はその `board.scale` 倍) | 大きさが違うと BOARD-SIZE / PNG-SIZE (error) |
| `board.font_px_min` | 見えている文字がこれより小さいと FONT-SMALL (error) |
| `board.notes_note` | 注記がこの数を超えると NOTES-MANY (報告) |
| `board.text_chars_note` (型ごと) | 説明の字数が型の値を超えると TEXT-LONG (報告) |
| `docs.first_version_items_warn` | 最初の版でやることが多いと FIRST-VERSION-MANY |
| `docs.screens_warn` | SCREENS-MANY |
| `docs.pages_warn` | PAGES-MANY |
| `docs.data_map_sources` | 仕様書 4 章の根拠の `素材:` がこの数以上なのに data-map が無いと DATA-MAP-MISSING |

- 説明の字数は、ボードの文字から端末の絵 (いちばん外側の `.phone`・`.browser`) の中の文字を引いた数。本物らしい画面の中身は数えない。
- `board.text_chars_note` の根拠は、利用者が先に作った資料 (2 つ目の基準点) の説明の字数: overview 1201、screen-map 1107、画面 397〜643、data-map 1674、mechanism 1516。
- `board.font_px_min` の根拠は、いちばん小さい文字の大きさ: 先に作った資料で 10.5px、お手本で 11px。

検査の結果は 3 段に分かれる。

| 段 | 止まるか | 扱い |
| --- | --- | --- |
| error | 止まる | 直してから次へ進む |
| warn | validate は止まらない。render は止まる | そのまま渡さない。直し方はメッセージか、この文書の表で見る |
| 報告 (TEXT-LONG、NOTES-MANY) | 止まらない | 量の目安。読む人の判断に要るなら、超えたまま渡してよい。減らすときは「4. 見た目」の「量を減らすとき」を読む |

render-board-png.mjs は warn でも exit 1 になる。[execution-contract.md](execution-contract.md) の「3. 終了コード」を読む。

## 1. シンプルさ

最初の版は「こういうことがやれます」が伝わる最小のものにする。広げる案は 次に広げる候補 に分け、打ち合わせで深掘りする。

| 決まり | 数 | どこで確かめるか |
| --- | --- | --- |
| 最初の版でやること | 3 個から `docs.first_version_items_warn` 個を目安 | 要件定義 3.1、overview のボード (FIRST-VERSION-MANY) |
| 1 画面の主なボタン | 1 つ | phone / pc のボード (`.btn-primary` が 1 つ) |
| メニュー | 5 個まで | 仕様書 2.3、pc のボード |
| 1 ボードの注記 | `board.notes_note` 個を目安に | 全ボード (NOTES-MANY。報告だけ) |
| 1 ボードで伝えること | 1 つ | briefing.json の `message` (文は 2 つまで。2 文目は 1 文目の補足) |
| モーダル (画面に重ねて出す小窓) | 確かめと削除だけ。入力に使わない | 仕様書 2.6、phone / pc のボード |
| ボードの枚数 | [workflow.md](workflow.md) の「既定のページ構成」を読む | briefing.json の pages (PAGES-MANY) |
| 1 枚の端末 | 2 台まで | phone のボード |
| 次に広げる候補 | 4 個まで | 仕様書 8 章 |

- 選び方は既定案で決める。迷う所を利用者に何度も聞かず、既定案で進めて 決めること に回す (核心の 5 問の聞き足しは [hearing-guide.md](../skills/run-briefing-hearing/references/hearing-guide.md) の「聞き足しと促し方」を読む)。
- 広げる案 (「あれもできると良い」) は、要件定義 6 章の `あとで` と、仕様書 8 章の 次に広げる候補 に入れる。画面のボードには描かない。
- 名前を挙げて頼まれた機能 (「候補を出して選ばせたい」のような明示の要望) は、広げる案と扱わない。出どころ `要望` で ヒアリング.md に残し、要件定義 6 章の行に `(要望:Hxx)` を付ける。あとで に回すときは、9 章の 決めること に `要望:Hxx` を書いて利用者に聞く (REQUEST-MISSING、REQUEST-DEFERRED-NO-Q)。書き方は [document-structure.md](document-structure.md) を読む。
- 先々への備えは データだけ にする (消さずに残す / 分けて置く / 印を付ける)。備えのために、最初の版に画面・ボタン・メニューを足さない。
- 項目は打つ量を減らす方向で選ぶ。初期値で埋まる項目は初期値を入れておく。
- 収まらないときは、文字を小さくしない (FONT-SMALL)。文を短くするか、注記を減らすか、ページを分ける。
- 機能を足すか迷ったら目的と必要性を確かめる。必須の認証・権限・情報保護・復旧や明示の要望を、見た目の件数だけで外さない。画面で伝える量はまとめ方で減らし、仕様の必要条件は残す。

## 2. 正確さ

- 項目名・列名・画面名・件数や時間は、素材か聞き取りにあるものを使う。無い値は根拠を `例` にする。
- 人と会社の名前は、下の「名前と値の扱い (data_policy)」の表に従う。
- 画面の中の値 (端末の絵の中の名前・数・日付) も、同じ表に従う。
- 読めない素材を推測で埋めない。`決めること:Qxx` を付けて 9 章に Q を足す。
- 画面番号と画面名は、仕様書 1 章 → 3 章の見出し → briefing.json の pages → ボードの h1 で同じにする。
- 要件定義 3.1 と 6 章の `○` と overview のボードは、同じ数・同じ言い回しにする。

### 名前と値の扱い (data_policy)

案件ごとに、資料に素材の名前・値・画像をそのまま載せるかを 1 回だけ決める。briefing.json の `data_policy` に書く (聞くのは run-briefing の工程0)。

| 場所 | `source` 素材のまま (素材をくれた先方と、作る側だけで見る) | `masked` 伏せる (それ以外の人にも見せる) |
| --- | --- | --- |
| ボードの meta の札 | 置かない | `<span class="sample-flag">画面の中の名前と値は例です</span>` を置く |
| まとめ HTML の表紙の 1 文 | 素材の名前と数字をそのまま載せている、と書く | ボードの画面の中の名前と値は例だ、と書く |
| 人と会社の名前 | 素材のまま書いてよい | 役割の名前 (配車 A さん、取引先Y) |
| 画面の中の値 | 素材の値 | 素材の形をまねた例の値 |
| 製品名 | 素材に写っている既存ソフトの名前は書いてよい | 書かない (役割で書く) |
| 素材の画像 | そのまま切り出してよい | 実名が写るなら架空の図に描き直す |

- どちらでも、項目名・列名・画面名・件数や時間は、素材か聞き取りの値を使う。
- どちらでも、資料の渡し方は同じ ([execution-contract.md](execution-contract.md) の「5. 守ること」)。
- あとで方針を変えるときは、briefing.json の `data_policy` を直し、今あるボードの札を手で合わせる (`build-briefing-scaffold.mjs boards` は今あるボードを上書きしない)。
- お手本 (examples/sample-haisha) はいつも `masked`。名前はすべて架空。

判断が要る検査コードと直し方 (`validate-briefing-docs.mjs`、結果は `_check/docs.json`):

| コード | 重さ | 直し方 |
| --- | --- | --- |
| EVIDENCE-EMPTY / EVIDENCE-FORMAT | error | 根拠を `素材:<ファイル名>` / `聞き取り:Hxx` / `例` / `決めること:Qxx` のどれかに。書き方は [document-structure.md](document-structure.md) の「根拠の書き方」を読む |
| FIRST-VERSION-MANY / SCREENS-MANY / PAGES-MANY | warn | 重複をまとめ、優先順位と画面分割を確認する。必須の業務・安全・運用は残し、保留の理由を報告する。外す合意がある話だけ6章の `あとで` と8章へ回し、`要望` は9章のQで確認する |
| SCREEN-BOARD-MISSING | warn | 仕様書 1 章の画面ごとに phone か pc のボードを 1 枚置く。置けないほど多いときは、画面を減らす相談をする ([workflow.md](workflow.md) の「既定のページ構成」) |
| DATA-MAP-MISSING | warn | data-map のボードを足す |
| MATERIAL-UNUSED | warn | 素材フォルダの PDF・画像・CSV・文字のうち、どの根拠 (`素材:`) にもボードの `data-source` にも出ていないもの。使ったなら、使った所の根拠に `素材:<ファイル名>` を書く。使わないなら、ヒアリング.md 1 章に理由を書いた行を足し、出どころを `素材:<ファイル名>` にする (Excel は CSV に書き出したほうを見る) |
| REQUEST-MISSING / REQUEST-DEFERRED-NO-Q | warn | 上の「1. シンプルさ」の `要望` の決まりで直す |
| REQ-TAG-UNKNOWN / REQ-TAG-MISSING | error / warn | ボードの要件の札を 6 章の F 番号に合わせる ([page-patterns.md](page-patterns.md) の「判断材料の部品」) |
| DATA-ONE-MISSING / DATA-UNIT-MISSING | warn | 仕様書 4 章に `1 件 = …` の行と、型の単位を書く ([document-structure.md](document-structure.md) の「仕様書.md」) |
| SPEC-DETAIL-MISSING | warn | 仕様書の共通UI・画面固有情報・処理境界・安全対策・稼働構成・監視と復旧の不足。document-structure.md の「実装へ渡す情報の記入先」を参照し具体的な本文、使わない理由、または案とQ番号を記入する。空欄・コメント・裸の未定は記入済みとしない。旧資料にも不足を促すwarnとし、新規の必須errorにはしない |
| PLATFORM-ITEM-MISSING / PLATFORM-EMPTY | warn | 6 章に 7 行をそろえる。決まっていなければ方式を「案: <既定案> (Qxx)」と書き、要件定義 9 章に Q を置く ([writing-patterns.md](../skills/run-briefing-docs/references/writing-patterns.md) の「仕様書.md」の 6 章の型) |
| FUTURE-FIELD-MISSING | warn | 8 章の候補ごとに、字下げした `- 備え: 〜` と `- 時期: 次の版` (か `その先`) を置く。備えが無ければ「なし」と 1 文 |
| BOARD-REF-UNKNOWN / BOARD-REF-MISMATCH | error / warn | 仕様書の「ボード:」を pages の番号に合わせる (run-briefing-docs が直す) |
| BOARD-TITLE-MISMATCH / BOARD-TITLE-SCREEN | warn | ボードの h1 を pages の title (画面名) と同じにする |
| BOARD-LEAD-MISMATCH | warn | ボードの `.lead` を pages の message と同じ文にする。直すときは両方を直す ([board-copy.md](../skills/run-briefing-boards/references/board-copy.md)) |
| PLAIN-TERM | 語ごとに warn か error | 言い換えるか、要件定義 8 章に意味を書く。下の「3. 言葉」を読む |

SPEC-DETAIL-MISSING は記載の不足を調べるだけで、exit0やwarnが0でも内容の網羅性を保証しない。業務条件の変換と網羅性の正本は [document-structure.md](document-structure.md) の「業務回答から仕様へ変換する契約」と「実装へ渡す情報の記入先」。レビューでは回答1件から仕様・画面まで追い、根拠、案、未定、確認先Qが混ざらないかを確かめる。未確定の案とQは最終報告にも残す。

## 3. 言葉

- 読む人は現場の担当者と発注側の責任者。技術に詳しくない人が読んで分かる言葉にする。
- [plain-language.md](plain-language.md) の語は言い換える。言い換えずに使う語は 要件定義 8 章に意味を書く (PLAIN-TERM)。
- 1 文は 60 字までを目安に。1 文に 1 つのことだけ書く。
- 「など」「適宜」「必要に応じて」で終えない。
- 画面の文言 (ボタン、項目名) は、仕様書の表とボードで同じにする。
- 製品名やサービス名は役割で書く (「会社の Google アカウント」は役割として扱ってよい)。`source` のときだけ、素材に写っている既存ソフトの名前は書いてよい (「2. 正確さ」の表)。

## 4. 見た目

配色と共通部品の正本は [design-contract.md](design-contract.md) に従う。

検査は `render-board-png.mjs` (結果は `_check/boards.json`)。BOARD-ATTR と BOARD-SCREENS-MISMATCH は validate-briefing-docs.mjs も調べる。検査を通ったあと、PNG を目で見る。

| コード | 重さ | 直し方 |
| --- | --- | --- |
| BOARD-SIZE / PNG-SIZE | error | `.board` の大きさを変えない。common.css の大きさのまま |
| CLIPPED | error | 文を短くする。枠を広げるのは最後の手段。わざと切るときだけ `data-clip-ok` |
| FONT-SMALL | error | 文字を小さくして収めない。文を短くするか、ページを分ける。端末の絵の中の文字も同じ |
| OVERLAP | warn | 重なった 2 つの位置をずらす。わざとなら `data-overlap-ok` |
| NO-SAMPLE-FLAG / SAMPLE-FLAG-UNNEEDED | warn | meta の札を briefing.json の `data_policy` に合わせる (「2. 正確さ」の表) |
| NOTES-MANY | 報告 | 止めない。同じ話の注記を 1 つにまとめる。外した話は 決めること か 仕様書へ |
| TEXT-LONG | 報告 | 止めない。減らすときは下の「量を減らすとき」に従う |
| BOARD-ATTR / BOARD-SCREENS-MISMATCH | error / warn | HTML の `data-board` `data-type` `data-screens` を briefing.json の pages に合わせる |

量を減らすとき (TEXT-LONG、NOTES-MANY):

- 量は目安。読む人の判断に要る中身なら、超えたまま渡してよい。
- 削ってよいもの: 同じ話の繰り返し、仕様書に書いた細かい決まり (ボードには仕様書の節を指す 1 行を残す)、飾りの言葉。
- 消してはいけないもの: 数字 (今の手間、件数、時間)、なぜ (理由)、だれ (使う人、確かめる人)、要件の札。
- 削った話の行き先: 仕様書の当てはまる節、要件定義 9 章の 決めること、別のページ。
- 削っても収まらないときは、文字を小さくせず、ページを分ける。

目で確かめること (検査では拾えない):

- いちばん大きく見えるものが、そのページの伝えることと合っている。
- 注記の番号が、指している場所に付いている。
- 文字が詰まっていない。余白が片寄っていない。
- 端末の中が本物の画面らしい。配置・ボタン・モーダル・アイコン・状態が仕様書2・3章と同じで、主操作が分かる。ボードにバックエンドの詳細を混ぜず、仕様書4〜7章に記録が残っている。
- 色だけで意味を伝えていない (注意の黄には言葉も添える)。
- 画面の地が白く、カードの縁に色帯が無い。CSS の側は tests/test_palette.py が見る。ボードの HTML に足した style は目で見る。

## 重さの決め方 (独立レビュー)

| 重さ | 目安 | 例 |
| --- | --- | --- |
| high | このまま渡すと誤解や手戻りが起きる | 件数を減らすため必須の業務や安全条件を落としている、素材と違う数字、`masked` なのに実名が写っている、名前を挙げて頼まれた機能が黙って落ちている |
| medium | 読む人が迷う | 注記の説明が 3 行、画面名がボードと文書で違う、専門用語が説明なしで残る、伝えることの根拠 (実物・数字・要件の札) が無いボード |
| low | 好みの範囲 | 言い回しの好み、余白の少しの片寄り |

high と medium は担当のスキルで直してから次へ進む。low は利用者に見せて任せる。
