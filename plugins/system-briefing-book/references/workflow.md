# 出力フォルダと版の決まり

各スキルが共通で使う決まり (出力フォルダ、書いてよいスキル、既定のページ構成、版) をまとめる。入口は skills/run-briefing。

- L1 の選択所有と L2 の通常生成: [execution-contract.md](execution-contract.md) の「6. 通常生成と確認の選択所有」が正本。
- 工程の順番と止まる所: [run-briefing の SKILL.md](../skills/run-briefing/SKILL.md) の「工程 (new)」を読む。
- 確認点と確認の深さ: 同じファイルの「確認点の進め方」を読む。深さごとに見る観点は [assign-briefing-evaluator の SKILL.md](../skills/assign-briefing-evaluator/SKILL.md) の「深さ」を読む。
- 打ち合わせのあとの直し (revise): 同じく run-briefing の SKILL.md の「工程 (revise)」を読む。

## 出力フォルダ

既定は `<素材フォルダ>/打ち合わせ資料/`。

```
打ち合わせ資料/
  briefing.json            案件の設定 (タイトル、読む人、配色、データ方針、ページ一覧)。版は持たない
  ヒアリング.md             聞き取り記録 (run-briefing-hearing だけが書く)
  要件定義.md               何をするか。2 行目「版: vX.Y」が版の唯一の正
  仕様書.md                 どう動くか
  変更点.md                 版ごとの変更 (v0.2 から中身が入る)
  _src/tokens.css           配色 (ボードの言葉 + jp-web-design の標準カラー + 案件の上書き。init が作る。手で直さない)
  _src/common.css           ボードの部品
  _src/NN_<slug>.html       ボード
  _src/assets/              切り出した素材画像、架空の図
  _src/assets/export/       ボードから切り出した端末画像 (自動)
  _src/book/                まとめ HTML に入れる軽い画像 (WebP、PNG と同時に自動で作る)
  NN_<slug>.png             ボードの PNG (大きさは quality-thresholds.json の board)
  _check/                   検査結果 (materials / docs / boards / book / review-<stage>) と確認点の選択 (choices)
  <タイトル>_打ち合わせ資料.html   まとめ。先方に渡すのはこれ 1 つ
```

| ファイル | 書いてよいスキル |
| --- | --- |
| 変更点.md、briefing.json の palette と data_policy (palette を変えたら init を `--refresh-css` で回し直す) | run-briefing |
| ヒアリング.md | run-briefing-hearing |
| 要件定義.md、仕様書.md | run-briefing-docs |
| `_src/` (init が作る tokens.css と common.css を除く)、PNG、briefing.json の pages | run-briefing-boards |
| まとめ HTML | run-briefing-book |
| `_check/review-<stage>.json`、`_check/choices.json` | run-briefing (assign-briefing-evaluator の返事と確認点で選んだ深さを保存) |

## 既定のページ構成

下の表で決まる。数の目安は assets/data/quality-thresholds.json の `docs` にある。
型の表示名は scripts/lib/briefing-files.mjs の `TYPE_LABEL` と同じ言葉にしてある。

| 順 | 型 | 置くか |
| --- | --- | --- |
| 00 | overview 全体図 | 必ず |
| 01 | screen-map 画面の一覧と流れ | 必ず |
| 02〜07 | phone 画面 (スマホ) / pc 画面 (PC) | 仕様書 1 章の画面 (= 最初の版の画面) を 1 枚に 1 つずつ。`docs.screens_warn` 枚まで |
| 必要なとき | data-map データの対応 | 仕様書 4 章の根拠の `素材:` が `docs.data_map_sources` 個以上のとき |
| 必要なとき | mechanism しくみ | 仕様書 5 章の自動の処理が 2 個以上つながって画面に出ないとき。または、名前を挙げて頼まれた機能 (`要望`) が あとで に回ったとき (8 章の候補のしくみを描く) |
| 必要なとき | future 将来の広げ方 | ヒアリング H06 で「先々の広げ方を 1 枚のボードでも見せる」を選んだとき |

- 画面は外さずに、すべてボードにする。仕様書 1 章の画面にボードが無いと SCREEN-BOARD-MISSING。
- 画面が `docs.screens_warn` を超えると SCREENS-MANY。画面を減らす相談を利用者とする。外す画面は 要件定義 6 章で `あとで` に回し、`要望` の機能なら 9 章に Q を置く。
- ページの上限は 2 + 6 + 2 + 1 = 11 枚 (`docs.pages_warn`)。超えると PAGES-MANY。
- 画面の共通ルールと裏側のしくみは仕様書 2 章と 6 章に、次に広げる候補は仕様書 8 章に書く。ボードにはしない。
- 決めることだけを集めたボードは作らない。置き方は [page-patterns.md](page-patterns.md) の「注記 (notes)」を読む。

仕様書の「ボード:」行はこの並びで振る。確認点3 で並びが変わったら run-briefing-docs がその行だけ書き直す。

## 版の決まり

- 版の正は 要件定義.md の 2 行目「版: vX.Y」の 1 か所だけ。
- 仕様書.md の「版:」は要件定義.md と同じ。ずれると validate と book が止まる。「更新日:」も同じにする (ずれると validate が止まる)。
- 新しく作ったときは v0.1。打ち合わせのあとの直しごとに 2 桁目を 1 つ上げる (v0.1 → v0.2)。
- 変更点.md の一番上の版見出し (`## v0.2 (YYYY-MM-DD)`) は 要件定義.md の版と同じ。v0.1 では中身が無くてよい。
- まとめ HTML の版は 要件定義.md から読む。briefing.json は版を持たない。

## 再現の測り方

構造の一致と、高再現の受入は分ける。この節を共通の正本とし、新しい停止ゲートは追加しない。

| 基準 | 目的と限界 | 受入方法 |
| --- | --- | --- |
| `examples/sample-haisha/` (v0.2、4画面) | 架空の素材で章立て・ボード・言葉の型を学ぶ。学習は次版候補。参考の6画面を再現したものではない | 既存の validate / render / book と目視で、型の動作を確認 |
| `assets/data/target-profile.json` | 6画面の参考から採った数と形。意味・参考版・初版範囲・画像の一致を証明しない | compare-briefing-profile の `_check/profile.json` を差の表として提示 |
| 利用者が指定した参考の実物 | 意味・版・範囲・視覚を保つ再現の対象 | 下記の対応表と実物比較を、既存の確認点と最終報告に含める |

比較結果の `comparison` は `structure-only`。`same` は現在の全ページの計測と構造指標がそろった場合だけで、高再現の合格ではない。`diff` は差または無効な材料、`incomplete` は差が検出されていないが計測不足の状態。`missing` は材料指標の不一致、`invalid` は空・明示的な非表示・素材／表示画像の不在などの内訳、`measurements.unavailable` は未計測・古い・無効な測定の内訳。render / book と共通の `resource-refs.mjs` で HTML・CSS の再帰参照・画像等の依存 SHA を照合する。参照していない assets の追加では計測を古く扱わない。旧計測に依存 receipt がない場合は `unverified-dependencies` として再描画を要する。未計測を一致へ読み替えない。差・未計測でもこの報告スクリプトは exit 0。

字数は並べるだけで合わせない。HTML の静的検査では CSS で隠れた内容・画像の中身・意味までは判定できないため、`fidelity.status` は常に `not-assessed`。高再現の受入には次を別に記録する。

1. **参考版**: 参考の文書名・版・日付・案件内の相対参照を記録する。版がない場合はファイルのハッシュ等で固定する。出力側の版とは分ける。配車参考の確認済み対象は「配車表 読み取りシステム 要件定義(打ち合わせ用 v0.4)」、作成日 2026-10-01、6画面と画像00〜09。profile自体にこの版の完全な内容は保存されていない。別版を使う場合はその実物を再確認する。
2. **意味と範囲**: 参考の全画面・機能を、出力の要件番号・仕様節・ボード番号・初版／次版に対応づける。配車では [case-haisha.md](case-haisha.md) の3項目を必ず含める。未対応や範囲変更は理由・確認先を明記し、未合意なら「未受入」とする。初版機能を無断で次版に移さない。合意済みの差は「差を承認した派生版」と報告する。
3. **視覚**: 現在の入力で render と book を通し、参考の対応画像と出力 PNG を並べ、同じ表示倍率で主操作・文字・画像・注記・数量を照合する。必要な領域は画像差分でも確認し、配色やフォント差の許容理由を記録する。単一 HTML を開いて表示と画像埋込を確認する。構造指標だけでこの照合を代替しない。
4. **記録**: 新たなゲートや必須ファイルを増やさず、要件定義の根拠と既存の確認点報告（レビューを行った場合はその記録）に、参考版・対応表・画像比較の対象と結果・未受入点を残す。最終報告で構造結果と高再現の受入結果を別々に伝える。参考がない通常生成では高再現は「対象外」、参考が未提供なら「未検証」とする。
