# Spec Registry (SSoT) — presentation-slide-generator

<!-- css-route: hand-slide -->
<!-- この宣言より後ろの var() は hand-slide 経路の :root とだけ照合される (lint-contract-drift.py check G)。経路が違う例を載せるときは、その直前に別の css-route 宣言を置く -->

**目的**: 30以上の references / SKILL.md ベストプラクティス表 / agents / assets に散在する制約を**1ファイルに集約**し、LLMが暗記不要で参照可能な Single Source of Truth として機能させる。

**運用原則**:
- 各ルールに **SR-ID（SR-§番号-連番）** を付与。他ファイルからは ID で参照する（例: 「SR-6-02 に従う」）。
- 各ルールは **Why（理由）** と **実装値/コード** を併記する。
- 矛盾するルールは「現状」「将来形」を明示し、どちらを優先するかを SR-ID 単位で確定させる。
- 本ファイルが既存 references と矛盾する場合、**本ファイルが正**。既存 references は段階的に本ファイルへの参照リンク化する。
- **検査器の名前は書かないが、検査の不在は書く。**「どの実行体がその項目を見ているか」は実行体の側が変わっても文書が変わらないため、事実でない記述になって残る。一方「**その項目を判定して合否へ反映する実行体が現時点で無い**」は、書かなければ読み手が緑を合格と読む。**規則表に載っていることと、判定していることは別**であり、前者だけを見て後者と読むと緑が意味を失う。不在は SR-ID の側に明記し、参照する文書もそれを写す（明記できている例: SR-3-09）。

**索引**:
- §1 寸法・単位 / §2 カラー / §3 フォント / §4 レイアウト / §5 SVG設計 / §6 GSAP
- §7 印刷 / §8 ナビゲーション / §9 アクセシビリティ / §10 コードブロック
- §11 検証ID対応表 / §12 逆引き（提供していない・理由） / §13 逐語コンテンツの非画像化
- §14 記事/レポートの読書レイアウト（R1-R8）/ §15 図解の幾何・素材トークン（D0-D28・R9 溶け込み）
- §16 本文キーの整合（slideType ごと）/ §18 出力ファイルの構成
- §17 仕様本文がまだ無い SR の一覧（欠落台帳・規則は定めない。§17 は規則を定める節ではないため、規則節の後ろに置く。**編集上の約束であり、検査器はこの順序に依存していない**）

**媒体の別**: §1-§13 は原則 **slide** の契約（16:9 固定枠・ページネーション・GSAP）。**report** は連続スクロールの読み物であり、固定枠前提のルールを持ち込まない。report 固有の契約は §14 に集約する（色・フォント・図解の語彙は両媒体で共有）。

---

## §1 寸法・単位

| SR-ID | ルール | 値 / 実装 | Why |
|-------|--------|-----------|-----|
| SR-1-01 | スライドアスペクト比は **16:9 厳守** | `.slider__container { aspect-ratio: 16 / 9; }`、`.slide-area` にも `aspect-ratio: 16/9` を設定 | プロジェクター/PDF/任意ウィンドウサイズで崩れない一貫表示を保証 |
| SR-1-02 | 設計基準解像度は **1920×1080**（半分の 960×540 を SVG viewBox 標準とする） | `viewBox="0 0 960 540"` | 16:9 と整数倍関係を維持、座標計算が容易 |
| SR-1-03 | A4横印刷時の物理サイズは **297mm × 210mm**（固定） | `.slider__item { width: 297mm; height: 210mm; min-height: 210mm; max-height: 210mm; }` | 1ページ1スライドを強制し、コンテンツ量に依存しない |
| SR-1-04 | 単位ホワイトリスト = **mm / rem / vw / vh / %**。**px は原則禁止** | CSS 全般で px 直書き禁止 | デバイス非依存・印刷とのスケール一致 |
| SR-1-05 | px 例外: **SVG 内部の座標・font-size**、および GSAP 計算で必要な数値 | `<text font-size="14">`、`gsap.from(el, { x: -30 })` 等 | SVG 仕様上 rem 解決が不安定なため px 必須。詳細は SR-3-04 / SR-5-04 |
| SR-1-06 | スペーシングスケールは **8px ベース**（rem換算）の 9 段階を使用 | `--space-1: 0.25rem` … `--space-9: 6rem` | 一貫した余白リズム |
| SR-1-07 | **SR-1-04 の px 禁止が効くのは `slider-*` 体系の面だけ**。`assets/slide-templates/` のひな形 (`.srg-*` 体系) を使う面では **`frame-contract.json` / `slide-skeleton.css` の絶対 px が正本**で、SR-1-04 と `references/unit-system.md` §1-2 はそこへ適用しない | ひな形は 1280x720 の固定座標系を `transform: scale(--srg-fit)` 1 手段で画面へ合わせる設計。vw/vh へ置き換えると倍率が二重に掛かる | 2 体系が同じ面へ同時に効くと、どちらの寸法も守れない面ができる。**面がどちらの体系かは `.srg-slide` の有無で決まる** |

---

## §2 カラー

> 面に置いてよい色数・地/文字・アクセントの作り方の正本は `skills/run-slide-report-generate/references/visual-generation-rules.md` §1（VGCONST_001 / VGCONST_002）。本節の SR-ID は CSS 変数の定義方法と実装契約を持ち、色の値は style genome の palette 定義に従う。

| SR-ID | ルール | 値 / 実装 | Why |
|-------|--------|-----------|-----|
| SR-2-01 | デフォルトテーマは **インク・オン・ペーパー**（紙地にインク文字のライトモード）。1 面に置く色は 地 / 文字 / 反転面 の 3 つに限る | 地色・文字色は CSS 変数で定義し、値は style genome の `palette` 定義に従う（本表に hex を書かない）。色数の逐語正本は `skills/run-slide-report-generate/references/visual-generation-rules.md` VGCONST_001 | 印刷配布・明るい環境で最大の可読性。色数を固定すると面をまたいでも見え方が揃う |
| SR-2-02 | 基本カラー変数は CSS 変数で定義し、**カラーコード直書き禁止** | `var(--wave-blue)` 等を使用 | テーマ切替・量産時の一括変更を可能に |
| SR-2-03 | **アクセント変数の名前と数は css-route ごとに違う。本表に一覧を持たない** | 名前の正本はその経路の生成器（report / hand-slide 系は `vendor/scripts/html-scaffold.js` と `render-report.js`、det-slide 系は `vendor/scripts/style-builder.cjs`）。経路と産出元の対応は `scripts/lint-contract-drift.py` の `_VAR_ROUTE_SOURCES` | 経路が複数あるのに 1 つの一覧を本表へ写経すると、どの経路にも当てはまらない名前が残る。実際、旧記述の6種には生成器が定義しない名前が混在し、経路外の旧資産が第2の正本になっていた。旧資産は2026-08-26に削除済み。残る名前も経路間で共通ではないため、名前を数える前に経路を決める。旧6色はSR-2-04（高彩度アクセントを定義しない）とも矛盾していたので、SR-2-04を正とする |
| SR-2-04 | **高彩度のアクセント色を定義しない**。アクセントは色ではなく**反転面**（インク地に紙色文字）で作る | 反転面の CSS 変数は地色・文字色の入れ替えで定義する。図解の内部に限り単一色相の濃度段を使ってよい（段数・彩度・面積の上限は `skills/run-slide-report-generate/references/visual-generation-rules.md` VGCONST_002 が正本。本表へ写経しない） | 色を足して焦点を作ると面ごとに色相が増え、デッキ全体の統一が崩れる。反転は色数を増やさずに最大のコントラストを作れる |
| SR-2-04-alt | **アクセント色セットの切替という選択肢を持たない**。クライアント指定のトーンがある場合も色相を増やさず、style genome の `palette` 定義そのものを差し替えて対応する | `theme.accentSet` によるセット切替は行わない | 色相セットを増やすと 1 面の色数上限（SR-2-01 / VGCONST_001）を面ごとに超える |
| SR-2-05 | **1 面の強調は 1 箇所**。強調手段は反転面であって色ではない | 反転面は 1 面につき 1 個。面積の上限は VGCONST_002 が正本 | 焦点が複数あると視線の優先順位が消える |
| SR-2-06 | 面積配分は **60-30-10**。60=地、30=文字とパネル、10=反転面 | 反転面は 1 面に 1 個。面積の上限は `skills/run-slide-report-generate/references/visual-generation-rules.md` VGCONST_002 が正本（本表へ写経しない） | 強調が面積を超えると「強調」が「主色」に変わり、地が背景に見えなくなる |
| SR-2-07 | **意味を色で区別しない**。対比・前後・可否・重要度は 位置 / 順序 / ラベル / 罫 で示し、図解の内部では単一色相の濃度段で示す | 「課題は赤、解決は緑」のような色相の割り当てを持たない。濃度段の使い方は VGCONST_002 が正本 | 色相を意味に割り当てると面ごとに色数が増え、色覚特性による差でも意味が伝わらなくなる |
| SR-2-08 | SVG の `fill` / `stroke` も **CSS 変数を使用** | `<rect fill="var(--wave-blue)" />` | SVG 属性にカラーコード直書き禁止。**fallback の hex は書かない**（書くと色の定義点が 2 つになり、変数側を替えても fallback だけ旧色のまま残る。実際にこの行の fallback は `#7E9CD8` で、実装 `vendor/scripts/svg-kit.cjs` が出す `#4B6681` と食い違っていた） |
| SR-2-09 | **影とグロウを意匠手段として使わない**。深度・階層は**罫**で作る | 角丸は 0px（写真・図のみ例外）。囲みの既定は 1px の下罫。線の太さ・hairline の値は `skills/run-slide-report-generate/references/visual-generation-rules.md` VGCONST_003 / VGCONST_004 が正本（本表へ写経しない） | 影は紙に出ないうえ、Chrome 印刷では薄いグレーの塗りになる。罫なら画面と紙で同じ階層が出る |

---

## §3 フォント

| SR-ID | ルール | 値 / 実装 | Why |
|-------|--------|-----------|-----|
| SR-3-01 | 本文フォントは **Noto Sans JP**、コードは **SF Mono / Fira Code** | `font-family: 'Noto Sans JP', sans-serif;` / `font-family: 'SF Mono', 'Fira Code', monospace;` | 日本語可読性とコード等幅性の両立 |
| SR-3-02 | フォントサイズは**基準 1 つからの等比派生**で作り、段ごとの実値を持たない。決定論 slide 経路の一括制御は `--font-scale` | 起点（`leadRem`）と比（`stepMajor` / `stepMinor`）は `vendor/scripts/style-builder.cjs` の `spec.typeScale` が正本。本表へ値を写経しない | 量産時にスライドごとサイズ調整可能。段ごとに実値を置くと 1 つ動かすたび全段を直すことになる |
| SR-3-03 | **型階層は天井 1 本と段差 2 種だけの単一系列で作る**。段の実体（変数名・段数・値）は生成器が持ち、本表は持たない。**個数が合っていることを適合の根拠にしない**。さらに**段の集合は経路ごとに別物**なので、自分が乗っている経路の段だけを使い、他経路の名前を借りない | 段の正本は経路ごとに、決定論 slide ＝ `vendor/scripts/style-builder.cjs`、ひな形 slide（`.srg-*`）＝ `assets/slide-templates/frame-contract.json`（`scripts/build-slide-skeleton-css.py` が生成する）、手書き slide ＝ [theme-style.md](theme-style.md) の `:root` ブロック、report ＝ `vendor/scripts/render-report.js`。**変数名も実値も本表へ写経しない**（写経すると生成器が動いたとき本表だけが古くなる） | 未定義の変数を `font-size` に指定すると宣言ごと無効になり、**指定したつもりで既定サイズのまま出る**。名前を借りた側は画面を見ても気づけない。個数で照合すると、集合が入れ替わっても数が同じなら気づけない |
| SR-3-04 | **画面表示の最小フォントは 1.4rem**（`--fs-small`）。それ以下は禁止 | UI テキスト・補足・キャプション含む | 50名規模プレゼン・スマホ視聴で可読性確保 |
| SR-3-05 | **SVG `<text>` は原則 14px 以上・下限 12px** | `svg-kit.cjs` の `MIN_FONT = 14`（原則）/ `MIN_FONT_SMALL = 12`（小バッジ・軸ラベルの例外）/ `validate-svg-diagram.py` の `MIN_FONT_PX = 12`（これ未満は D4 error）。3 つの数はそれぞれ原則・例外・禁止ラインで、同じものの重複定義ではない | 50名対面×プロジェクタで判読不能（約2-3mm相当）になるため |
| SR-3-06 | SVG `<text>` 内で **Font Awesome unicode（`&#xf...;`）使用禁止** | アイコンが必要なら `<foreignObject>` 内に `<i class="fa-solid ..."></i>` を置き、その div に `class="fo-card"` を付与（SR-6-04参照）。または Unicode emoji を直書き | CDN 未ロード時に PUA コードが全スライドで消失するリスク |
| SR-3-07 | 質問スライドの本文は **`--fs-subheading`** を使用（`--fs-heading` は大きすぎる） | `.question-badge ~ .main-message { font-size: var(--fs-subheading); }` | 質問の威圧感を抑え、思考誘導に適切 |
| SR-3-08 | **全スライドタイプの `h2` に CSS 定義必須**（特に `.slide-quote`, `.slide-message`, `.slide-list`, `.slide-cycle`, `.slide-flow`） | `.slide-TYPE h2 { font-size: var(--fs-heading); }` | 定義漏れがあると見出しが極小表示になる |
| SR-3-09 | **1 行が長いテキストは文節の切れ目で改行する**。改行位置は文字数ではなく、句読点・助詞など**文節の切れ目**で決める | 検査 ID は V-021（WARN）。**この規則を判定して合否へ反映している実行体は現時点で無い。**位置だけなら文字数を使わずに機械で見られるため試作を `scripts/validate-linebreak-position.mjs` に置いてあるが、受理集合が未確定なので**どの gate からも呼んでいない**（`--self-test` のみ動く）。折り返しそのものの破綻（切れ・最終行 1-2 文字）は描画後の `ui-quality-checklist.md` が見る。`validate-structure.js` は構成段階に `<br>` が現れないため skip する。実挿入は `auto-linebreak.js`（句読点 → 助詞 → 上限超過の優先順。`--max-chars` 既定 35 は道具の既定値であって仕様の数字ではない）で、挿入に使う語彙は `vendor/scripts/utils.js` の `LINEBREAK_RULES` | 単語・文節の途中で折り返すと読点のない位置で視線が切れ、1 行の意味が取れなくなる。位置は文字数を使わずに機械で見られるが、**長さ**が破綻かどうかは「その文字列がその書体でその箱の幅に入るか」で決まり、箱の幅は描画後にしか分からない。だから位置は静的に、長さは描画後に、と持ち場を分ける。受理集合が未確定なのは、挿入用の `LINEBREAK_RULES` が「どこに入れると良いか」の優先順位表であって「どこなら切ってよいか」の定義ではなく、受理基準へ転用すると母集合が足りないため。2026-08-14 に試作を既存 51 deck へ当てた実測では `<br>` 862 件中 471 件（54.6%）が違反判定になり、中身は体言止め・連用中止・連体形・閉じ括弧と、文節の切れ目として正しいものが大半だった。過半に出る警告は読まれなくなるので、受理集合（どの語尾を文節末と認めるか）が決まるまで配線しない。形態素解析を入れれば語彙も数値も発明せずに解けるが、依存を増やす判断は別途 |
| SR-3-10 | **書体ウェイトは 3 段のみ**。最も太い段はその面に 1 箇所だけ置く | 段の値・段数・出現回数の逐語正本は `skills/run-slide-report-generate/references/visual-generation-rules.md` VGCONST_005（本表へ写経しない）。決定論経路の実装は `--fw-body` / `--fw-label` / `--fw-lead` の 3 変数 | 段が 4 つ以上あると隣り合う段の差が判別できず、階層が増えたのに読み取れる順位は減る。最も太い段が複数あると面の第 1 位が同点になる |

---

## §4 レイアウト

| SR-ID | ルール | 値 / 実装 | Why |
|-------|--------|-----------|-----|
| SR-4-01 | 3層構造を厳守: `.slider` > `.slide-area` > `.slider__container` > `.slider__item` | HTML 構造の必須形 | 16:9 強制とアニメーション制御の前提 |
| SR-4-02 | スライド本体パディングは CSS 変数で制御 | `padding: var(--nav-top-padding) var(--nav-arrow-padding) var(--nav-bottom-padding);` | ナビ余白の一括カスタマイズ |
| SR-4-03 | **Before/After（比較）レイアウトは 2 パネル等幅 + 間隔は版面比。中央要素が無いときは 48% / 4% / 48%** | `.compare-container { display: flex; gap: 4%; } .compare-panel { width: 48%; }`。パネルの class は経路で 2 つあり、決定論経路が `.compare-panel`、骨格経路が `.compare-item`。**規則が定めているのは 2 パネルが等幅であることと間隔が版面比であることで、class 名でも特定の数値でもない**（html-scaffold.js の `COMPARE` 直前のコメントが同じことを書いている）。2 パネルだけなら等幅・版面比を満たす配分は 48/4/48 に定まるので、その場合は数値どおりを求める。**中央に第 3 要素（`.compare-vs`）を置く形も認める**。48+4+48 = 100 には第 3 要素の居場所が無く、中央要素を持つ deck は実在するので、誤りは規則の側だった。中央要素があるときに求めるのは、等幅であること・間隔が版面比であること・2 パネル幅と間隔の合計が 100% を超えないことの 3 つ。パネル幅を `max-width` や `flex` で決めるのは**どちらの場合も不可**（版面比でないので画面幅で比率が変わる）。コード比較（`.code-compare` / `.code-panel`）は同じ比率だが SR-10-05 の側で、この規則の対象ではない。検査 ID は V-001（FAIL）で、実行体は `scripts/validate-compare-ratio.mjs`（生成された deck の CSS を読む）。**比較レイアウトの面を持たない構成では V-001 は非該当**として skip する（対象が無いことと、対象があるのに誰も見ていないことを同じ扱いにすると、未検査の一覧がどの構成でも同じ 1 行になって読まれなくなる） | 視覚的バランス。**既知の未修正違反**（2026-08-14 実測 / 母集団 `05_Project/{スライド,レポート}/*/{index,report}.html` の 28 本）: 比較レイアウトを使う 16 本のうち **15 本が違反・計 32 件**。内訳は gap が版面比でない 13 本（2rem / 3rem / 8mm 等）・gap 宣言なし 2 本・パネル幅の `width` 宣言なし 15 本（うち 12 本は `max-width` の px 固定で幅が決まっている。実値は 400/420/480/500/550/600px と `max-width: 45%` / `none`、2 本は幅を決める宣言が皆無、1 本は `flex` / `min-width` のみ）。中央要素は 11 本が持ち、等幅違反と居場所なしは 0 本。通ったのは決定論エンジンの `slide-2026-08-15-AI質問会` 1 本のみ。**この 15 本は直さないと決めた**（8/15 本番デッキが凍結中で残りも出荷済みのため。見落としではない）。次に各 deck を触るときに直す |
| SR-4-04 | Before / After の区別は**色ではなく位置とラベル**で示す。強調したい側だけを反転面にする | 左＝Before、右＝After の位置固定 + 見出しラベル。反転にするのは片側のみ | 色相の割り当てを持たない（SR-2-07 と整合）。位置とラベルなら色覚特性や白黒印刷でも区別が残る |
| SR-4-05 | カードリスト（`.list-item`, `.ig-item`）は **`width: 100%; box-sizing: border-box;`** を必ず指定 | コンテナにも `width: 100%` | 指定漏れで左寄り半幅表示になるバグの防止 |
| SR-4-06 | 補足テキストは **最大 3 行 / `--fs-small` / opacity 0.7** | `.text-note { font-size: var(--fs-small); opacity: 0.7; -webkit-line-clamp: 3; }` | 主情報を阻害しない補助情報の規律 |
| SR-4-07 | 質問スライドは「**背景情報 → 質問**」の順で配置 | structure.md でこの順序を強制 | 文脈なしの質問は思考が起動しない |
| SR-4-08 | **図解の実装形式は問わない**（インライン `<svg>` / CSS・div で組む図解 / D3 mount のいずれでもよい）。ただし **`position: absolute` で配置するレイアウト図解は禁止**。形式によらず、図解は図解ブロックとして識別できる形で出す（`slide-diagram` 系 class・`data-v8-diagram` 属性・`data-d3-mount`） | 第 1 文は形式に要件を課さないので検査しない（許可の明示であって、判定する対象が無い）。第 2 文の検査 ID は V-029（WARN）だが、**これを判定して合否へ反映している実行体は現時点で無い。**「図解として使われている absolute」の識別は `scripts/validate-svg-diagram.py` の図解ブロック抽出を使えば発明せずに書けるが未実装。**V-029 を「実装済み」と書かないこと** | 形式を問わないのは、体系がすでに 3 形式を出して 3 形式とも検査しているため。(1) 決定論エンジンの `slide-timeline` 等は div で組む CSS 図解を出す。(2) `scripts/validate-svg-diagram.py:2664` は CSS/HTML 構成の図解へ D14-D16 を当て、コメントで「`<svg>` を 1 つも持たない図解はここでしか見られない」と明示している。SR-15-15 も `accent` 上限を SVG（D7）と CSS 図解（D16）の両方で見る。(3) D3 経路は `<script type="application/json" data-d3-mount>` を出す。2026-08-14 の実測でも既存 51 deck の図解の面 125 のうち 54（43%）がインライン `<svg>` を持たない CSS 図解だった。生成器が出していて検査器が見ているものを規則が禁じているなら、直すのは規則の側。**SVG の版番号は書かない。**版に固有の機能を要求も検査もしておらず、版を書くと判定する実行体の無い規則が 1 つ増えるうえ、版番号は写しの過程で数量と誤読された実績がある（実例は `vendor/scripts/validate-structure.js` の `V_DEFINITIONS` 直前の desc 規則と `tests/test_v_definitions_desc.py` の陽性対照に残してある） |
| SR-4-09 | **スライド ID 命名規約**: 物理順 ID は `slide-NNN`（schema 準拠）、論理順別名は `N` 接頭辞（NarrativeOrder）または `S` 接頭辞（SectionOrder）で別名指定可。`data-slide-id="N06"` のように HTML 属性へ二重持ちすることで、構成案の差し替えで物理順が変わっても論理参照が壊れない | `id="slide-006" data-narrative-id="N06"` 等。`N` = 全体ナラティブ通し、`S` = セクション内通し | 章再分割やスライド追加で物理順 ID 採番が再配布された際、references / structure.md / レビュー文書の相互リンクが破綻するのを防ぐ。SR-12-07 同期検証はこの両 ID を区別する |

---

## §5 SVG 設計

| SR-ID | ルール | 値 / 実装 | Why |
|-------|--------|-----------|-----|
| SR-5-01 | viewBox は **16:9 系（960×540 等）**または図解形状に応じた専用値（円形=正方形）を使用 | `viewBox="0 0 960 540"` 等 | 解像度独立・座標計算容易 |
| SR-5-02 | viewBox 算出式: `幅 = カード幅×N + gap×(N-1) + 左右マージン×2` | structure.md の SVG 設計メモに必須記載 | 100人中100人が同じ図解を再現できる精度 |
| SR-5-03 | **テキスト 1 行最大文字数 = floor(カード有効幅 / font-size px) × 0.75**（安全マージン） | 例: 有効幅 200px / 14px → 14文字 × 0.75 ≒ 10文字 | 自動折返し不可な SVG `<text>` での溢れ防止 |
| SR-5-04 | SVG `<text>` の改行は `<tspan>` で明示。`dy = font-size × 1.5` | `<tspan x="100" dy="20">…</tspan>` | SVG は自動改行しないため |
| SR-5-05 | 矢印マーカーは `<defs>` に定義し id で参照する。**系列色を矢印へ割り当てない**（`references/diagram-style-tokens.md` §2 使用制限 4 と同じ規則）。**名前と数の一覧を本表に持たない** | 正本は `vendor/scripts/svg-kit.cjs` の `arrowMarkers()`。base は役割名と色名が混在したキー群で、さらに `extraColors` を受けるので**数は固定でない**。id はスライド合成時に `render-slide.cjs` が面ごとの接尾辞を付ける。同名 id の衝突は SR-15-20 / D23 の担当 | 旧記述は「色別 5 種（blue/aqua/pink/yellow/violet = `SERIES` の順）」だったが、実測（2026-08-14）で**一覧としても規則としても成立していなかった**。(1) `arrowMarkers()` の base は 9 キー（muted / accent / link / ink / blue / aqua / pink / yellow / violet）で、5 つはその一部でしかない。(2) `extraColors` があるので数は固定されない。(3) `violet` は `VAR_VIOLET` = `SERIES[0]` を指し `blue` と同じ値なので、**id が 2 つあっても見分けは 1 つ**。(4) 系列色の矢印は使用制限 4 が禁じており、**定義が在ることと使ってよいことは別**である。`SERIES` は同日 5 枠から 4 枠になったが、**5 を 4 に直してもこの 4 点はどれも直らず**、「合っているように見える」分だけ悪くなる。矢印が系列の意味を運ぶと凡例が矢印にも必要になり凡例が膨らむ |
| SR-5-06 | グラデーション・フィルターは `<defs>` 内で定義し ID 参照 | `<linearGradient id="grad-blue-pink">` 等 | 再利用性とパフォーマンス |
| SR-5-07 | SVG 設計メモには 12 項目（viewBox / 各座標 / カードサイズ / フォント / 最大文字数 / 最大行数 / 改行位置 / padding / gap / 接続線 / アクセント / 文字数検証）を **すべて** 明記 | structure.md テンプレ準拠 | 実装ブレを排除 |

### §5-a 収まり計算の手順（SR-5-02 / SR-5-03 / SR-5-04 の適用ガイド）

上の SR-ID が規則の正本で、本節は「その規則をどの順に当てるか」だけを持つ。
計算の結果「入らない」と分かったあと、**幅を伸ばす / 文言を縮める / そもそも載せない** のどれで吸収するかの分類は
`skills/ref-diagram-system/references/label-japanese.md` にある。計算と吸収先の判断は層が違うので、両方を続けて読む。

1. **カード有効幅** = カード幅 − (左padding + 右padding) − アイコン領域幅
   例: 幅260px / padding 12px×2 / アイコン円 r=14+余白8px = 36px → 有効幅 200px
2. **1 行最大文字数** = SR-5-03。日本語 1 文字幅は font-size px とほぼ等しいものとして扱う。
   SVG 内 `<text>` は px 値で制御する（SR-1-05）。標準値: タイトル 28px / サブタイトル 22px / 本文 18px /
   補足・ラベル 14px / 注記 13px / 小バッジ・軸ラベル 12px（12px は SR-3-05 の例外枠のみ）。
3. **必要行数** = ceil(文字数 / 1行最大文字数)。最大行数を超えたらテキストのリライトかカード拡大。
4. **改行位置**の優先順位: ①読点「、」の直後 ②助詞（を・が・に・で・は・と）の直後
   ③意味の切れ目（主語と述語、修飾語と被修飾語の間） ④最大文字数に達する位置（強制改行・非推奨）。
   実装は SR-5-04（`<tspan>` + `dy = font-size × 1.5`）。

**よく使う viewBox パターン**（SR-5-01 / SR-5-02 の計算済み値）

| レイアウト | viewBox | 計算根拠 |
|---|---|---|
| 1×3カード(260px) | `0 0 860 440` | 260×3 + 24×2 + 28×2 = 860 |
| 1×4カード(190px) | `0 0 840 300` | 190×4 + 16×3 + 22×2 = 852→840 |
| 1×5カード(170px) | `0 0 960 420` | 170×5 + 14×4 + 27×2 = 960 |
| 2カラム対比(380px) | `0 0 860 480` | 380×2 + 40 + 20×2 = 860 |
| 円形サイクル | `0 0 700 700` | 中心(350,350)、半径220 + ノード幅80 |
| 同心円 | `0 0 700 500` | 中心(350,230)、最大半径220 + 余白 |
| ロジックツリー | `0 0 900 600` | ルート幅260 + 子ノード260×3 + gap |
| 縦型プロセス | `0 0 600 600` | 幅 = 進捗バー8 + gap + カード460 + 余白 |

**structure.md 出力後の自己検証**: SR-5-07 の 12 項目が全 SVG スライドに揃っているかを見る。
不足の典型は ⑦改行位置と ⑫文字数検証で、この 2 つが無いと実装時に溢れる。
形状ごとのチェックは §15-a の D0-D28（機械検査）が正本で、目視チェックリストを別に持たない。

---

## §6 GSAP アニメーション

| SR-ID | ルール | 値 / 実装 | Why |
|-------|--------|-----------|-----|
| SR-6-01 | **`scale: 0` および `scale: 0.5` 禁止**。最小 `scale: 0.8` | `gsap.from(el, { scale: 0.8, ... })` または `x: -30 / y: 30` で代替 | 残留 transform で要素消失するバグの防止 |
| SR-6-02 | **`clearProps: 'all'` は `content.children` のみに適用**。`content.querySelectorAll('*')` は禁止 | `gsap.set(content.children, { clearProps: 'all' })` | `*` 適用は SVG fill/stroke 属性と foreignObject レイアウトを破壊する |
| SR-6-03 | `clearProps` は updateSlide() と leaveAnimation() の onComplete の両方で適用 | 両ライフサイクルでリセット | 残留スタイルを完全除去 |
| SR-6-04 | **foreignObject 内 div には `class="fo-card"`（または `fo-card--row`）を付与**。インライン style のみのレイアウトは禁止 | CSS 側で `.fo-card { ... }` を定義 | clearProps に消されないクラスベース防御 |
| SR-6-05 | イージングは **3 種以上** 使い分け | `power2.out` / `back.out(1.7)` / `power1.inOut` / `elastic.out(1, 0.3)` / `power3.inOut` から組合せ | 単調 ease の繰り返しを防ぎ表現に階調 |
| SR-6-06 | スライド遷移は `duration: 0.25, ease: 'power3.inOut'`、enter は `'-=0.15'` で並行開始 | scripts.js 標準値 | 高速・スムーズの体感 |
| SR-6-07 | leave アニメーションは enter より短く（duration 0.15-0.2、stagger 0.03-0.05） | 退場は素早く | 切替の俊敏感 |
| SR-6-08 | `prefers-reduced-motion` 検出時は duration/stagger を 0 倍率にするグローバル変数を scripts.js 冒頭で定義 | `const prefersReducedMotion = window.matchMedia('(prefers-reduced-motion: reduce)').matches;` | アクセシビリティ必須対応 |

---

## §7 印刷

| SR-ID | ルール | 値 / 実装 | Why |
|-------|--------|-----------|-----|
| SR-7-01 | `@page { size: A4 landscape; margin: 0; }` | 余白なし・A4 横 | 配布資料としての一貫サイズ |
| SR-7-02 | `.slider__item` は **width/height/min-height/max-height すべて 297mm × 210mm 固定** | SR-1-03 と同一 | コンテンツ量に関係なく1ページ1スライド |
| SR-7-03 | 枠線・margin 禁止（`border: none; margin: 0;`） | A4 フルサイズ印刷 | 見た目のロスを排除 |
| SR-7-04 | **印刷時 GSAP インラインスタイルを必ずリセット** | `@media print { .slider__content, .slider__content > *, .slider__content * { visibility: visible !important; opacity: 1 !important; transform: none !important; } }` | リセット忘れでスライドが空白になる事故防止 |
| SR-7-05 | 印刷時はナビ系を非表示 | `.progress-bar, .navigation, .slide-counter, .dot-pagination, .agenda-indicator { display: none !important; }` | 配布資料に不要 |
| SR-7-06 | 色再現を強制 | `* { -webkit-print-color-adjust: exact !important; print-color-adjust: exact !important; }` | 背景色・アクセント色の保持 |
| SR-7-07 | `data-hidden="true"` のスライドは印刷から除外（display:none + height:0） | スキップスライド対応 | 完成版/ドラフト併存時の柔軟性 |
| SR-7-08 | **印刷=画面の同一比率を保つ**（padding/font-size/gap/border-radius は画面と同比率） | 印刷専用に padding/font 等を極端縮小しない | 視覚的整合性。SR-7-09 の矛盾を参照 |
| SR-7-09 | **【既知の矛盾】** 現実装の `print-layout.md` は印刷時にフォントサイズ縮小を多用している（例: `.slide-title .title-main { font-size: 3rem; }`）。一方 SKILL.md ベストプラクティスは「印刷=画面同じレイアウト」を要求 | **現状**: 縮小許容（`@media print` 内のフォント縮小は既存実装互換のため許容）。**将来形**: vw/`--font-scale` 統一で印刷時も画面と同じレイアウトに収束させる（縮小ゼロ化）。新規生成では SR-7-08 を優先しつつ、レガシー互換のため fallback として縮小ルールを残してよい | A4 物理サイズ（297mm）と画面 vw 換算の差を吸収する暫定策。新規スライドは vw + `--font-scale` で印刷でも崩れない設計を目指す |
| SR-7-10 | shadow は印刷で除去（`box-shadow: none !important`） | カード系のみ | インクコスト削減・視認性 |
| SR-7-11 | **SR-7-01 の `margin: 0` が効くのは `slider-*` 体系の面だけ**。ひな形 (`.srg-*`) を使う deck では `slide-skeleton.css` の `@page { size: A4 landscape; margin: 21.47mm 0 }` が正本で、SR-7-01 を重ねて書かない | `@page` はカスケードで後に書いた側が勝つため、連結順で印刷結果が変わる。**`@page` 宣言は成果物全体でちょうど 1 つ**に保つ | 重ねると 21.47mm のレターボックス帯が消え、1280x720 が A4 からはみ出す |
| SR-7-12 | **1 つの成果物に `slider-*` 面と `.srg-*` 面を混ぜない**。検出は `python3 scripts/validate-slide-skeleton.py --deck <html>` の **SK12-mixed-system**（同一 HTML に `slider__item` と `srg-slide`/`data-slide-skeleton` が同居したら FAIL）。**vendor の `validate-print.js` は混在を見ない** — P01/P02/P03/P06 はいずれも `slider-*` 体系の存在を測る述語で、`.srg-*` deck へ `slider__item` を足すと P03 がむしろ緑へ転じる。印刷が要るなら面をどちらか一方の体系へ寄せる (engine 出力へ手で足す面は `slider-*` で書く)。**`.srg-*` deck に `validate-print.js` を当てて赤が出るのは仕様どおり**で (印刷契約は `slide-skeleton.css` の `@page` 側が持つ・SR-7-11)、それを混在の証拠にも出荷不可の根拠にもしない | `@page` は成果物に 1 つしか効かない (SR-7-11) 一方、必要な帯幅は体系ごとに違う: `slider-*` は 297x210mm を版面いっぱいに使うので `margin: 0`、`.srg-*` は 1280x720 を zoom 0.8769 で 297x167.06mm へ落とすので `margin: 21.47mm 0`。**どちらを選んでももう一方の面が崩れる** (margin: 0 なら srg 面が版面上寄りに 43mm ずれ、21.47mm なら slider 面が版面から 43mm はみ出す) | 混在は画面・印刷を問わず成果物単位で禁止する。engine deckはslider体系、純手書きdeckはsrg体系のどちらか一方を選ぶ |

---

## §8 ナビゲーション

| SR-ID | ルール | 値 / 実装 | Why |
|-------|--------|-----------|-----|
| SR-8-01 | **ページネーションは 5 個区切りマイルストーン方式**（標準） | `.pg-dots__item:nth-child(5n) { width: 1.2vh; height: 1.2vh; }` | 25 枚超でも現在位置が一目で分かる |
| SR-8-02 | 色だけで区切りを示すことは禁止（寸法差を必須とする） | `nth-child(5n)` で幅・高さを通常ドットより大きくする | 色覚やグレースケール出力に依存せず位置を示す |
| SR-8-03 | **セクション目次ナビ（section-nav）を常時表示** | スライド左上 `.agenda-indicator` または上部 `.section-nav` | 構造把握を補助 |
| SR-8-04 | **`.section-nav__item.active[data-section="X"]` は HTML の全 data-section 値を網羅** | opening / lecture / demo / ws / summary / closing 等すべて 1対1 で CSS 定義 | 1つでも欠けるとナビ色が表示されない |
| SR-8-05 | セクション色分けは代替案（オプション）。基本は SR-8-01 とセクションナビの併用 | `.pagination .dot[data-section="X"]` は無くてよい | 役割分担の明確化 |
| SR-8-06 | 左右矢印は `var(--nav-arrow-padding)`（既定 3rem）で配置 | `position: fixed; padding: 0 var(--nav-arrow-padding)` | 量産時の余白一括調整 |

---

## §9 アクセシビリティ

| SR-ID | ルール | 値 / 実装 | Why |
|-------|--------|-----------|-----|
| SR-9-01 | **WCAG 2.1 AA 準拠**（コントラスト比 4.5:1 以上） | 本文前景で最小になるのは `--fg-muted` on 地（`paper`）= **5.02:1**。この値は `paper` に連動するので、`paper` を動かしたら引き直す。色の正本は `style-builder.cjs SPEC.colors` | 視覚障害含む全ユーザー可読性 |
| SR-9-02 | `:focus-visible` を全インタラクティブ要素に適用 | `:focus-visible { outline: 3px solid var(--ink, #141412); outline-offset: 2px; }` | キーボード操作可視性 |
| SR-9-03 | `prefers-reduced-motion` 対応必須 | CSS: `@media (prefers-reduced-motion: reduce) { *, *::before, *::after { animation-duration: 0.01ms !important; transition-duration: 0.01ms !important; } }` ＋ JS は SR-6-08 | 前庭障害・乗り物酔い配慮 |
| SR-9-04 | **UI テキスト（ナビ・ラベル・キャプション）の opacity は 0.6 以上**。ただし **`--fg-muted` に opacity を掛けない**。薄くするなら `--ink` から下げる | `.text-note { opacity: 0.7; }` 等 | 0.3 等は読めない。`--fg-muted` を除外するのは、SR-9-01 の下限に対する余裕が **0.5 しかない**ため。0.6 を掛けると AA を割る。**別々に読めば両方正しく、組み合わせたときだけ壊れる**ので、どちらの検査器も鳴らない |
| SR-9-05 | `aria-label` を SVG 図解に必須 | `<svg role="img" aria-label="図解の説明">` | スクリーンリーダー対応 |
| SR-9-06 | `sr-only` クラスと `aria-live` を適切に使用 | スライド遷移通知等 | 動的コンテンツのアクセシビリティ |

---

## §10 コードブロック

| SR-ID | ルール | 値 / 実装 | Why |
|-------|--------|-----------|-----|
| SR-10-01 | **コードブロックの縦上限は面の高さの 60%（全回統一・px 直書き禁止）** | `.code-block { max-height: calc(60 * var(--sv)); overflow-y: auto; }`。`--sv` は面の高さの 1%（`style-builder.cjs`）。`--sv` を持たない LLM 経路は面の高さ（`--slide-max-height`）の 60% を書く（同じ寸法） | 視覚的一貫性。px 固定にすると画面比率で面に対する占有率が変わる。旧値 420px は 1920x1080 で内容枠の 54% しか使わず、コード面の充填率が 10 行で 0.548 に頭打ちして `fill_policy.exceptions.code` の下限へ何行書いても届かなかった |
| SR-10-02 | フォントは SF Mono / Fira Code（Noto Sans JP は禁止） | `font-family: var(--font-mono, 'SF Mono', 'Fira Code', monospace)` | 等幅表示 |
| SR-10-03 | 共通スタイル: `font-size: 1.5625rem; line-height: 1.7; padding: calc(1.8519 * var(--sv)) calc(1.25 * var(--su)); border-radius: calc(0.625 * var(--su));` | `style-builder.cjs` の `.code-block` | 可読性。`1.5625rem` は `typography.min` の 18px を面座標で表した値（18 / 11.52）。旧値 `1.4rem` は最小の観測点 1280x1024 で 16.1px となり `typography.min` を割っていた。余白も px でなく面単位で書く |
| SR-10-04 | ヘッダー行（`#`）は太字、変数（`{変数}`）は下線 + 太字 | 色相を増やさず、font-weight と text-decoration の組で区別 | 色覚・グレースケールに依存しない簡易構文強調 |
| SR-10-05 | Before/After コードブロックは横並び 48% / 4% / 48%（SR-4-03 と整合）。縦上限は SR-10-01 と同じ | `.code-compare { display: flex; gap: 4%; } .code-panel { width: 48%; max-height: calc(60 * var(--sv)); }` | 比較しやすさ。左右に並ぶぶん横は 48% だが、縦は片側と同じだけ与えてよい。旧値 280px は使える縦の 36% しか使わず、比較したい 2 つのコードがどちらも数行で切れていた |
| SR-10-06 | Before は通常面 + 「Before」ラベル、After は反転面 + 「After」ラベル | SR-4-04 と整合し、色だけで意味を担わせない | 意味と強調順位の一貫 |

> §10 の数値は `vendor/scripts/style-builder.cjs` が正本で、本表はそれを読者へ示す唯一の写しである。両者のずれは `scripts/lint-contract-drift.py` のチェック F（生成器定数 ↔ 正本文書）が検出する。**他の文書は §10 の数値を書き写さず SR-ID で参照する**（F へ登録できない場所に数値を置くと、同じ値が複数箇所に別の顔で残る）。

---

## §11 検証 ID 対応表（S1-S26 × SR-ID）

UI 品質レビュー（`agents/ui-quality-reviewer.md`）の検証項目 S1-S26 が、本 SSoT のどの SR-ID を根拠とするかを示す。

| 検証ID | 検証内容 | 参照 SR-ID |
|--------|----------|------------|
| S1 | CSS/JS分離（インライン禁止） | SR-12-08（agents/html-generator） |
| S2 | 外部ファイル参照存在 | SR-12-08 |
| S3 | 質問スライド配置順序 | SR-4-07 |
| S4 | 質問スライドフォント = fs-subheading | SR-3-07 |
| S5 | slide-area 3層構造 | SR-4-01 |
| S6 | 16:9 アスペクト比 | SR-1-01 |
| S7 | 印刷カード比率（画面同等）。**面の体系を先に判別する** | SR-7-08 / **体系の分岐: SR-1-07, SR-7-11, SR-7-12** |
| S8 | 印刷 A4 フルサイズ（枠なし）。**`margin: 0` は `slider-*` 面の合格条件であって全体の合格条件ではない** — `.srg-*` 面は `margin: 21.47mm 0` が正しい | SR-7-01, SR-7-03 / **体系の分岐: SR-7-11, SR-7-12** |
| S9 | ページネーション 5個区切り | SR-8-01 |
| S10 | 各面の強調は反転面 1 個 | SR-2-05 |
| S11 | イージング3種以上 | SR-6-05 |
| S12 | アクセシビリティ基本（focus/reduced/sr-only/aria） | SR-9-02, SR-9-03, SR-9-05, SR-9-06 |
| S13 | UI テキスト opacity 0.6 以上 | SR-9-04 |
| S14 | 視覚階層（L1/L3 サイズ差 2倍以上） | SR-3-03（fs スケール） |
| S15 | CARP 原則（近接・対比） | SR-1-06, SR-2-05 |
| S16 | 60-30-10 配色 | SR-2-06 |
| S17 | clearProps 安全パターン | SR-6-02, SR-6-03 |
| S18 | foreignObject CSS 保護（fo-card） | SR-6-04 |
| S19 | A4 印刷仕様準拠（mm/rem/vw、px禁止）。**面の体系を先に判別する** (`.srg-slide` があれば絶対 px と `margin: 21.47mm 0` が正しく、px 直書きを違反にしない) | SR-1-03, SR-1-04, SR-7-01〜03 / **体系の分岐: SR-1-07, SR-7-11, SR-7-12** |
| S20 | コンテンツ完全性（structure.md ⇔ HTML 一致） | SR-12-08 |
| S21 | ソース情報反映 | SR-12-08 |
| S22 | SVG テキスト最小 12px（原則 14px） | SR-3-05 |
| S23 | SVG 内 FA unicode 禁止 | SR-3-06 |
| S24 | 全スライドタイプ h2 CSS 定義 | SR-3-08 |
| S25 | section-nav HTML/CSS 整合 | SR-8-04 |
| S26 | code-block の縦上限統一（面の高さの 60%） | SR-10-01 |

---

## §12 逆引き（提供していない）

**実行体 → 参照すべき SR-ID の逆引き表は、ここには置かない。**

手で書いた逆引き表は実行体と同期しない。以前ここにあった表は、名前の挙がったファイルこそ全て実在したが、実行体が実際に持つ SR-ID と一致する行が 1 つも残っていなかった。大半のファイルは SR-ID を 1 つも含まず、含む数本も宣言と実測が重ならなかった。表が古いのではなく、手書きの表という形式が保てないことの結果なので、書き直しても同じところへ戻る。

逆引きの元データは各実行体が機械可読な形で自分の中に持っている。必要になったらそこから生成する:

- `vendor/scripts/validate-structure.js` — `V_DEFINITIONS`（V-ID と対応する SR-ID）
- `scripts/validate-compare-ratio.mjs` — ファイル冒頭の宣言と `--json` 出力の `rule` / `vid`
- `vendor/scripts/check-consistency.js` — 各 suggestion 文字列の先頭に付く SR-ID
- `vendor/scripts/style-builder.cjs` — CSS ブロックごとの SR-ID コメント

生成器はまだ無い。**無い間は「逆引きは提供していない」が正しい状態であって、表が欠けているのではない。**手で表を書き足して埋めないこと。

### SR-12-XX（agent/script 由来の運用制約）

以下は逆引きではなく、agent / script 固有の運用制約そのものの定義。

| SR-ID | ルール | 値 / 実装 | Why |
|-------|--------|-----------|-----|
| SR-12-01 | バッチ並列生成時、`slider__item` の数 = structure.md のスライド数 | 一致しない場合は差し戻し | コンテンツ完全性（S20） |
| SR-12-02 | バッチ並列生成時、`nth-child(5n)` が styles.css に存在 | SR-8-01 の機械検証 | ページネーション標準化 |
| SR-12-03 | バッチ並列生成時、`.slider__content *` が `@media print` 内に存在 | SR-7-04 の機械検証 | GSAP リセット保証 |
| SR-12-04 | バッチ並列生成時、`scale: 0` が scripts.js に存在しない | SR-6-01 の機械検証 | 残留 transform 防止 |
| SR-12-05 | CDN は GSAP 3.12.2 / FontAwesome 6.5.1 / Noto Sans JP のみ使用可（任意で Bootstrap Icons / Material Symbols） | 他 CDN は許可しない | セキュリティと一貫性 |
| SR-12-06 | 写真・画像素材は **WebP 形式推奨**。PNG/JPG は変換してから使用 | `vendor/scripts/convert-to-webp.js` 利用 | ファイルサイズ削減 |
| SR-12-07 | index.html ⇔ structure.md は**常に同期**。HTML 修正時は必ず structure.md も更新 | `vendor/scripts/sync-checker.js` で検証 | 二重管理の破綻防止 |
| SR-12-08 | **CSS / JS はインライン禁止・外部ファイル分離**（`<link>` / `<script src>`） | GAS デプロイ用 1 ファイル化は `vendor/scripts/build-single-html.js` で生成 | 保守性・差分レビュー容易性 |

---

## §13 逐語コンテンツの非画像化（コード専用ページ）

| SR-ID | ルール | 値 / 実装 | Why |
|-------|--------|-----------|-----|
| SR-13-01 | **正確性必須・逐語コンテンツ（コード・数式・精密数値表）は画像化しない。コード系 slideType（`slide-code` / `slide-code-compare`）は aiVisual で image-only / baked-with-overlay 不可** | image-only デッキ・全面AI画像化デッキを含むどの場合でも、コードは実HTMLコードブロック（`.code-block` / `.code-compare-body`）で描画する「コード専用ページ」とする。`aiVisual` を持たない純HTMLコードページが正規デフォルト。世界観背景が必要な場合のみ `aiVisual` は `pattern: html-composite` / `backgroundSource: svg`（推奨）または `raster` / `textPolicy: overlay-only` に限定。機械検証は V-043（`vendor/scripts/validate-structure.js`）と `schemas/structure.schema.json` の slide allOf if/then。 | AI画像はコードを正確に再現できず（誤字・崩れ・コピー不可・印刷で判読不能）、逐語の正確性が損なわれる。実HTMLなら構文ハイライト・選択コピー・印刷品質を保てる |

---

## §14 記事 / レポートの読書レイアウト契約

**適用範囲**: `mode=report` の成果物（`vendor/scripts/render-report.js` が生成する HTML）。スライド（§1-§10）とは媒体の契約が異なるため独立した節にしている。**スライドは「1画面 = 1メッセージの固定枠」、記事は「連続スクロールの読み物」**であり、前者の 16:9 固定・ページネーションを後者へ持ち込んではならない。

| SR-ID | ルール | 値 / 実装 | Why |
|-------|--------|-----------|-----|
| SR-14-01 | 本文の可読幅は **全角 40 字**を正本とする | `--report-measure: 40em`（`.report-section > p / ul / ol` に適用）。**`ch` は使わない** | `ch` は数字 0 の字幅＝半角基準で、日本語の行長指定に使うと約半分の見積りになる。`em` なら全角 1 字 = 1em で一致する。40 字は日本語組版の上限帯（35-45）の中央で、視線の戻り距離が長すぎず、細切れにもならない |
| SR-14-02 | ページ全体の実効幅配分は **sidebar 16rem + gap 3rem + 本文 40em**、上限 1160px | `--report-sidebar-w: 16rem`, `--report-page-max: 1160px` | 広げすぎると本文右の空白だけが増え「空白 > 本文」の逆転が起きる。図解が横へ伸びる余地（本文幅の約 1.5 倍）で頭打ちにする |
| SR-14-03 | グラフィカル block（narrative / stat / visual / table / key-point）は**可読幅の制限を受けず全幅**を使う | `max-width` は `p / ul / ol` にのみ適用 | 図・表は「読む」のでなく「見る」ため、行長の制約が当たらない。狭めると細部が潰れる |
| SR-14-04 | 段落は**文（句点）単位の行ブロック**へ組む | `splitSentences()` → `<span class="report-sent">`、`.report-sent { display: block; }` | 句点をまたいで次の文が行の途中から始まると、話題の切り替わりを字面から拾い直すことになる。文頭が必ず行頭に来れば、視線を左端へ戻した瞬間に次の文だと分かる。`<br>` を使わないのは、自然折り返しと二重になって段落が縦に間延びするため |
| SR-14-05 | 文の分割は **inlineMd の前（生テキスト）**に行う。括弧の内側の句点では切らない | `OPEN`/`CLOSE` の深さを数え、深さ 0 のときだけ文末を認める。`。」` `!?` は前の文へ含める。半角 `.` は文末として扱わない | 装飾後の HTML を割ると `<strong>` や `<a>` をまたいで閉じタグを失う。括弧内で切ると引用が分断され係り先を失う。半角 `.` は `Node.js` / `1.5倍` と区別できない |
| SR-14-06 | **目次は既定 ON**。明示的に `meta.toc: false` を書いた文書と、節が 1 つの文書のみ非表示 | `const wantToc = meta.toc !== false && sections.length >= 2;` | 読み物として成立させるには「全体像」と「任意の節へ飛べる手段」が常に要る。節が 1 つなら目次は情報を足さない |
| SR-14-07 | 目次は**常時追従**（sticky）。狭画面（≤900px）でも static に落とさない | `.report-toc--sidebar { position: sticky; top: calc(var(--report-topbar-h) + var(--space-4)); max-height: calc(100vh - ...); overflow-y: auto; }`。狭画面は `.report-sidebar { display: contents; }` で包含ブロックを `.report-layout` へ移す | static にすると読み進めた先から他の節へ移動できず（先頭へ戻る操作が要る）、読み物として辿れなくなる。**sticky は親の box の中でしか動かない**ため、内容ぶんの高さしか持たない器が親だと移動余地ゼロで即座に流れ去る |
| SR-14-08 | 目次は `details/summary` で**畳める** | `<details class="report-toc__box" open>`。既定は開。summary の既定マーカーは消し `▾ / ▸` を代替表示 | 狭画面で追従させると本文の可読域を食うため、読者が畳める必要がある。マーカーを消したまま代替が無いと畳めることに気付けない |
| SR-14-09 | **追従ヘッダー**を常時表示し、文書名・現在節・読了進捗を出す | `.report-topbar { position: sticky; top: 0; height: var(--report-topbar-h); }`、`--report-topbar-h: 3.25rem`。現在節は `[data-report-here]`、進捗は `[data-report-progress]`（`reportTopbarScript()` が更新） | スクロールで文書冒頭の `.report-header` が消えると「いま何を読んでいるか」の手掛かりが失われる。帯を薄く保つのは、追従 UI が縦を食うほど本文の可視行数が減るため |
| SR-14-10 | 浮遊 UI（追従ヘッダー・sidebar 目次）は **print で非表示** | `@media print { .report-topbar { display: none !important; } .report-sidebar { display: none !important; } }` | 紙にはスクロールが無く、追従 UI は意味を持たないうえ本文領域を奪う |
| SR-14-11 | sticky 要素の `top` と、アンカー遷移の `scroll-margin-top` は**同じ基準（`--report-topbar-h`）**から導く | `.report-section[id] { scroll-margin-top: calc(var(--report-topbar-h) + var(--space-4)); }` | 基準がずれると、目次から飛んだ節の見出しが帯の下に潜って読めない |
| SR-14-12 | 節ごとに**図解を先、本文を後**に置く | 縦積み: `narrative → visual → body`。2 列: `grid-template-columns: 1fr 1.1fr` で visual が左 | 読者はまず図で全体像を掴み、分からなかった箇所だけを本文で補える。逆順だと全体像を持たないまま文章を頭から処理し、図に辿り着く頃に本文で組み立てた理解と突き合わせ直す二度手間が生じる |
| SR-14-13 | 図解が明示されていない節は、**その節の本文が持つ構造からのみ**図解を導出する | `deriveVisualFromBody()`: ordered-list/task-list → chevron、bullet-list → value-stack、stat-tile 2 件以上 → bar、段落列 → stepper（各段落の**最初の文をそのまま**ノードラベルにする）。導出できる構造が無ければ図解を作らない | 外部知識で補ったり一般論の図を当てると、図と本文が食い違って読者を誤らせる。要約を機械生成すると本文に無い主張が図に載るが、本文の文を抜き出すだけならその危険がない。**無理に作らない方が正しい** |
| SR-14-14 | **追従 UI は本文を覆わず、画面の縦 25% を超えて占めない** | `--report-topbar-h: 3.25rem`。狭画面（≤900px）では `reportTopbarScript()` が目次 `<details>` の `open` を外して既定で畳む。検査は R8（`validate-report-layout.js` の `NAV_OCCUPANCY_MAX = 25`） | 到達性のための UI が本文の面積を奪うと、読むために設けた道具が読むことを妨げる。狭画面では sidebar 目次が本文の上へ回り込むため、開いたままだと目次リンクで飛んだ見出しが目次の背後へ着地する。**畳んだ状態を既定にし、開くのは読者の意思**とする |

### §14-a 記事レイアウトの機械検証（R1-R8 → SR-ID）

実描画での検証は `scripts/validate-report-layout.js`（Playwright・4 viewport: 1440/1024/768 screen + 658 print）。

| 検証ID | 検証内容 | 深刻度 | 参照 SR-ID |
|--------|----------|--------|------------|
| R1 | 節内の見出し・本文・図解が重なっていない | error | SR-14-03, SR-14-12 |
| R2 | 文書全体・コンテナからの横はみ出しが無い | error | SR-14-02 |
| R3 | 本文 1 行の行長が全角 24-45 字（目標 40 字） | warning | SR-14-01 |
| R4 | 図解幅がコンテナ幅の 55% 以上（600px 未満の画面は除外） | warning | SR-14-03 |
| R5 | 見出しの上余白 > 下余白（近接の原則）。**文書フロー全体**で測る | warning | — |
| R6 | `overflow: hidden` の中で内容が切れていない | error | — |
| R7 | 追従ヘッダーと目次が**実際にスクロール後も画面内に残る** | warning | SR-14-07, SR-14-09 |
| R8 | 追従 UI が本文を覆っておらず、画面の縦 25% 以下に収まっている | warning | SR-14-14 |

R7 の目次不在は**節が 2 つ以上のときだけ**報告する（SR-14-06 が 1 節文書の目次を認めないため、無条件に警告すると仕様通りの文書が落ちる）。R8 は R1（重なり）が拾えない範囲を埋める: R1 は `scroll=0` の一回測定なので、**スクロールして初めて本文の上へ来る sticky 要素**はどのペアにも入らない。

R5 は節スコープでは原理的に発火しない（見出しは節の先頭にあり、上の比較対象が取れない）ため、節をまたいだ 1 本の並びを作ってから前後を取る。R7 は computed style が `sticky` でも祖先の `overflow` で無効化されるため、**宣言でなく実際にスクロールした結果**を測る。

---

## §15 図解の幾何・素材トークン

SR-15-01〜04 は線幅、SR-15-05〜08 は幾何（矢じり・入射・canvas・凡例）、SR-15-09〜11 は上限と検査の作法。

| SR-ID | ルール | 値 / 実装 | Why |
|-------|--------|-----------|-----|
| SR-15-01 | 全ビルダーは線幅を `kit.STROKE` トークンから取る。数値直書き禁止 | `vendor/scripts/svg-kit.cjs` の `STROKE`。`svg-builder.cjs` / `svg-structures.cjs` から `kit.STROKE.*` で参照 | 太さが 1 種類だと全部が同じ強さで主張し、視線の順序が生まれない。**太さ = 情報の重要度**として読ませる |
| SR-15-02 | 線幅は**役割名 <!-- count: strokeRole -->6 つが <!-- count: strokeTier -->3 段（1.25 / 2 / 3）へ落ちる**。名前の数と段の数は一致しない | `primary: 3`（主コネクタ）/ `secondary: 2`（副コネクタ）/ `node: 2`（ノード輪郭）/ `axis: 2`（軸・基準線）/ `hairline: 1.25`（補助罫・グリッド）/ `band: 24`（ゲージの帯。面として読ませる値なので太さの段には数えない） | 役割ごとに名前を固定することで、別々のビルダーが作った図解でも太さの意味が一貫する。段を 3 に閉じたのは、かつて `node` に当てていた 1.5 が `secondary` の 2 と比 1.33 しかなく、**名前の上では別でも目には分かれていなかった**ため。名前が 6 で段が 3 なのは欠落ではない。一致させようとして段を増やすと、また見分けの付かない段が生まれる |
| SR-15-03 | **最も細い線でも 1.25 を下回らない** | `STROKE.hairline = 1.25`。検査は D9（`validate-svg-diagram.py` の `MIN_STROKE_WIDTH`、同値を両方で保つ） | SVG は必ず縮小表示される（viewBox 1080 の図が記事本文幅 804px なら約 0.75 倍）。`stroke-width: 1` は実効 0.7px となり、非 Retina で 1 デバイスピクセルを割ってアンチエイリアスで灰色に溶ける。印刷（A4 実本文幅 174mm）でも同様に潰れる。**「細ければ上品」ではない** |
| SR-15-04 | `stroke-width: 0` は「線を引かない」の表明として D9 の対象外 | `if (sw is not None and 0 < sw < MIN_STROKE_WIDTH)` | 塗りだけの図形（filledStyle 等）に太さの下限を課しても意味がない |
| SR-15-05 | **矢じり（marker）の形状は 1 箇所が正本**。`markerUnits="strokeWidth"` 固定 | `vendor/scripts/svg-kit.cjs` の `MARKER = { w: 8, h: 6, refX: 7, refY: 3 }`。経路方向への張り出し `overhang = w - refX`、実 px は `kit.markerOverhangPx(線幅) = overhang × stroke-width`。`<defs>` は必ず `kit.markerDefs` / `kit.arrowMarkers` を通す | 以前は svg-kit（8×6 / refX=7）と svg-builder（10×8 / refX=9）が別々に marker を定義しており、同じレポートの中でも経路によって矢じりの大きさと「先端がどこか」が変わっていた。さらに `ringArcPath` の端点補正は `refX` に依存するため、形状が二重定義だと補正量が必ずどちらか片方で間違う。値は `_CONSTANT_PAIRS` が本表と実装で突合する |
| SR-15-06 | **コネクタは宛先の辺へ、外向き法線と逆向きに入射させない** | `kit.INCIDENCE_RULE`（左辺←右向き / 右辺←左向き / 上辺←下向き / 下辺←上向き）。経路は `kit.safeElbow` が屈曲順を自動選択し `incidence: 'ok' \| 'degraded'` を申告する。`degraded` の線は引かない。1→多は `kit.trunkPaths` で軸平行のトランクへ束ね、同一辺の取付本数は `kit.fanCapacity(辺長)` を超えない | 矢じりは経路方向へ `overhang`（SR-15-05）ぶん張り出すため、逆向きに入射させると矢の胴体が矩形の内側へ埋没し、読者には矢頭しか見えない。**図の向き＝主張の向き**が伝わらなくなる。取付間隔の下限 `FAN_MIN_GAP` は `snap(MARKER.h × STROKE.primary)` の導出値で、独立した仕様値ではない（実装の内部量として採番しない） |
| SR-15-07 | 図解の viewBox は **幅固定・高さ 3 段の階段**から選ぶ | `vendor/scripts/svg-builder.cjs` の `CANVAS`（幅は SR-1-02 と同じ 960、高さは `sm` / `md`（= SR-1-02 の 16:9）/ `lg` の 3 段）。必要高からの選択は `CANVAS.height(needed)`。`lg` で足りない量は段を増やさず、載せる件数を減らして解決する（SR-15-10） | 高さを内容ごとに自由に決めると、記事に並べたとき図ごとに拡大率が変わり、同じ 14px の文字が図によって違う大きさで表示される。連作として読めなくなる。SR-5-01 の「図解形状に応じた専用値」を、この 3 段に限定して運用する |
| SR-15-08 | **凡例は高さを確定してから viewBox 高を決める**。位置は図の外・下端の水平ストリップ | `kit.legendHeight(items, 幅)` → `CANVAS.height(必要高 + 凡例高)` → `kit.legendStrip()` の順。`NODE_STYLES` を 2 種以上使う図には凡例を付ける | 日本語ラベルは英字の 1.6-2 倍幅になるので 1 行前提で書くと必ず折り返す。viewBox 高を先に固定して凡例を後付けすると、折返しが起きた瞬間に **D1（はみ出し・error）**を踏む。図中に浮かせないのは、凡例が図の一部と誤読されるため |
| SR-15-09 | 成果物側の**複雑度上限 = `max(CAPACITY) × COMPLEXITY_FACTOR`**。密度が語彙である型は `COMPLEXITY_RELAX` 倍まで緩める | `scripts/validate-svg-diagram.py` の `COMPLEXITY_FACTOR = 4` / `COMPLEXITY_RELAX = 1.5`。`max(CAPACITY)` は `svg-builder.cjs` から実行時抽出。検査は D11 | `CAPACITY` はビルダー関数の入口に効く上限で、agent が SVG を直接書く LLM 経路には一切効かない。同じ上限を成果物側でも見て両経路の採点を揃える。係数 4 は「ノード本体／付属図形／コネクタ／付随ラベル・凡例」の 4 群に由来し、決定論経路で描ける最も密な図は必ず通る。**`CAPACITY` に 1 つ大きな値を置くと全図の上限が緩む** |
| SR-15-10 | **容量上限の宣言が無い variant は採用しない（fail-closed）** | `vendor/scripts/render-report.js` の `fitsCapacity`。上限は `CAPACITY` と決定表 `rows[].result.capacity` の**厳しい方**を採り、どちらにも無ければ不採用。ビルダー直呼び側の `guard()` は従来どおり超過分を「ほか N 件」と注記する | 以前は `cap === 0` を無制限と読んでいたため、`CAPACITY` への登録漏れが静かに通り、超過分が注記なしで消えた図が出ていた。**登録漏れは黙って通るのでなく、その variant が選ばれなくなる**のが正しい帰結 |
| SR-15-11 | **D10 / D13 の許可集合と D11 の上限を検査器へ写経しない**（実装から実行時抽出する） | `scripts/validate-svg-diagram.py` の `_allowed_palette()`（`svg-kit.cjs` の `TOKENS` / `SERIES`）、`_allowed_families()`（同 `textBlock` の既定スタック）、`_capacity_max()`（`svg-builder.cjs` の `CAPACITY`）。抽出に失敗したら「検査できない」と 1 度だけ warning を出す | 許可集合を検査器へ写すと、パレットや書体スタックを差し替えた日に**検査器だけが古い値を許し続ける**。値の正本を 1 つに保つのが唯一の防ぎ方。抽出失敗を黙って素通りさせないのは、検査が沈黙するより vendor が壊れている事実を出した方がよいため |
| SR-15-12 | **CSS/HTML で組んだ図解も同じ契約で採点する**。検出標識は `data-v8-diagram` 属性か `diagram-` / `slide-diagram-` / `chart-` / `d3-` で始まる class トークン | `scripts/validate-svg-diagram.py` の `extract_diagram_blocks()`。入れ子は外側 1 件へ畳み、`<svg>` しか中身が無いブロックは D0-D28 の担当として返さない。検出規約の説明は `references/diagram-layout-contract.md` §D-7 | D0-D18 は `<svg>` 断片しか抽出しないため、div と span で組んだ図解は 1 件も検査に掛からず素通りしていた。決定論経路は `render-slide.cjs` のテンプレートに守られるが、agent が HTML を直接書く経路には防具が無い。**検査対象を見つけられない検査は、存在しないのと同じ**である |
| SR-15-13 | **CSS 図解の「4px グリッド」は「`--space-*` 以外の間隔値を書かない」と読み替える** | 検査は D14。刻みの正本は `svg-kit.cjs` の `GRID`、間隔スケールの正本は `style-builder.cjs` の `SPEC.spacing` 9 段。どちらも検査器が実行時抽出する（SR-15-11 と同じ作法） | slide の `html` は `font-size: 1vw` なので rem は画面幅に比例し、**px グリッドという概念自体が成立しない**。px 直書きの寸法にだけ `GRID` の倍数を課し、間隔は段の集合で縛る。線幅・不透明度・フォントは `diagram-layout-contract.md` §D-1「グリッドの適用外」により対象外 |
| SR-15-14 | **複雑度予算 21 項目の値は `diagram-layout-contract.md` §D-2 の表が正本**。検査器へ写経しない | 検査は D15（`_complexity_budget()` が §D-2 の 4 列表を実行時パース）。CSS 図解では #1 ノード / #2 コネクタ / #4 注釈 / #20 凡例 / #21 フォント階層、SVG では #4（`font-style="italic"` の `<text>` 数）/ #21 を数える | これらは既存実装のどこにも定義が無い新規の値なので、契約文書が正本になる（`_CONSTANT_PAIRS` へ登録できる相手の実装が存在しない）。表を検査器へ写せば、上限を直した日に検査器だけが古い値で採点し続ける。表の 4 列構造を壊すと抽出が空になり「検査できない」warning が出るので、沈黙ではなく気付ける形で失敗する |
| SR-15-15 | **`accent` の個数上限は SVG（D7）と CSS 図解（D16）の両方で見る** | D16 は `svg-kit.cjs` の `TOKENS.accent` / `accentTint` から「その色を名指す綴り」（CSS 変数名・hex・rgb 三つ組）を抽出し、要素の `style` / `fill` / `stroke` / `class` に現れる件数を数える。上限は §D-2 #3 | CSS 図解の accent は `border-color` などへ accent 系の CSS 変数名で書かれ、D7 の `ACCENT_TOKENS` 名寄せでは 1 件も当たらない。**焦点が複数ある図は、経路が違っても等しく読めない** |
| SR-15-16 | **コネクタ `<path>` の斜め直線セグメントを禁じる**（`<line>` を見る D5 の path 版） | 検査は D17。`C` / `S` / `Q` / `A` は `diagram-layout-contract.md` §D-3 原則 1・原則 3 が語彙として認めている（bridge 弧・昇格弧・放射状）ので見ない。放射状型・チャート型は D5 と同じく型申告で例外＝**無出力**（warning へ降格ではない）。D5 側は `<line>` に加え矢じり付き `<polyline>` / `<polygon>` も見る（矢じりの無いデータ線・レーダー多角形・矢羽根の輪郭はコネクタではないため対象外。`polygon` の閉じ辺は見ない） | 決定論経路の `kit.safeElbow()` を通れば斜めは出ないが、LLM 手書き経路は `M x1 y1 L x2 y2` を直接書ける。斜め線が要ると感じたときに直すべきは線の形ではなく**ノードの配置**であり、D5 が `<line>` だけを見ていた間、`<path>` で書かれた斜めコネクタは全て素通りしていた |
| SR-15-17 | **図解が成果物の中で浮かないこと（R9 溶け込み）も機械で見る** | `scripts/validate-report-visual.py` の `_check_r9_blend()`（検査 ID `figure-text-duplication` = C25 の (p)）と `_check_r9_occupancy()`（`visual-occupancy` = (q)）。数値は `references/diagram-layout-contract.md` §D-4-1 / §D-4-2 の R9-* 表から実行時に読む。severity は warn（`--strict` で fail 昇格） | 単体で完璧に美しい図が、成果物の中では「貼り付けられた別物」に見えることがある。日本語は分かち書きが無いので、重複は形態素でなくラベルの完全一致件数と文字 n-gram の重なり率で近似する。**面積比 R9-1 の実測は静的解析では測れない**ので `validate-report-layout.js` の責務として残し、ここは figure に*宣言された*寸法（R9-3 / R9-5）だけを見る。宣言が無ければ何も言わない |
| SR-15-18 | **文字はそれを包む箱と canvas に収まる（文字量と図解サイズの依存関係）** | 検査は D18。文字幅は `vendor/scripts/svg-kit.cjs` の `charWidth()` を実行時に構文解析して取り込む（係数を本 registry へ転記しない。作法は SR-15-11 / SR-15-13 と同じ）。canvas は viewBox ± 4px 超過で error、箱は `幅 − 16px`（左右 8px）超過で warning。背景板（viewBox の 80% 以上）・不透明マスク矩形・`transform` 配下は箱として見ない。人間向けの目安式と解決優先順は `diagram-layout-contract.md` §D-8 | 文字が図解に収まらなければ UI/UX が崩れ、図解の意味が無くなる。決定論経路の `kit.fitText` は内寸を `幅 − 24px` で見積もるため D18（`幅 − 16px`）より常に厳しく、構造上 D18 を通る。D18 が鳴るのは手書き経路か `fitText` を通さず直に `<text>` を置いた箇所だけである |

| SR-15-19 | **描かれた結果の破綻（線の重なり）も機械で見る**。線が箱の辺へ溶ける（D19）／別々の線が同一直線上で重なる（D20）／線が箱の内側を貫く（D21） | 検査は D19 / D20 / D21。判定は「軸平行セグメントどうしの共線かつ区間重複が 12px 以上」。12px 未満は端点が辺へ着地しただけの正常な接続として黙る。D21 は**他の矩形を内包する矩形（レーン帯・グループ枠）を対象外**にする（帯を横切るのは正当な語彙）。`transform` 配下・入れ子座標系は座標から実位置を測れないので見送る | D0-D18 は「必要な情報が載っているか」「座標が規約通りか」を見るが、**値が全て正しくても描かれた結果だけが壊れる**欠陥が実在した（2026/8, `high-level` 図。分岐の横走りが宛先の上辺と重なって線が枠へ溶け、同じ段間を走る複数本が同じ高さで折れて 2 本が 1 本に見えた）。壊れているのは要素間の**重なりという関係**なので、要素を 1 つずつ見る検査では原理的に捕まらない。ここを覆うまで、この型は作例のスクリーンショット目視だけが頼りだった |

| SR-15-20 | **文書内参照は 1 文書の中で正しい相手へ届く**。同名 `id` が 2 箇所以上で定義されていない（D22）／参照先が自分の SVG か共有 defs にある（D23） | 検査は D22 / D23。D23 が見る参照は `url(#id)` と、id をそのまま書く形の `aria-labelledby` / `aria-describedby` / `href="#id"`。後者は SVG の外の見出しを指す正当な用途があり `check_document()` からは見えないので、**別の SVG にしかない時だけ出し、どこにも無い時は黙る**（`url(#...)` は SVG 外を指す用途が無いので両方出す）。どちらも 1 ファイルを丸ごと見る `check_document()` の担当で、SVG を 1 つずつ見る `check_svg()` では原理的に捕まらない。対象は `arrow-*` に限らず **`id` 全般**（`marker` / `clipPath` / `linearGradient` / `filter` / `pattern` / `mask` は同じ罠を踏む）。`marker-start` / `marker-mid` / `marker-end` の参照は D3 の担当なので D23 では重ねて見ない。`<svg width="0" height="0">` のように**描画要素を持たない共有 defs 置き場**（`defs` / `style` / `title` / `desc` / `metadata` 以外の子を持たない SVG）への参照は正当として黙る（この SVG は何も描かないので面の切替に影響されない）。深刻度は error | スライド HTML は全面の SVG を 1 文書へ同居させるが、各面のビルダーは自分の defs を「その図の中で一意」な名前（`arrow-blue` 等）で書く。個々の SVG としては正しく D3 も通る。それでもブラウザは `url(#arrow-blue)` を**文書内で最初に現れる定義**へ解決するため、2 面目以降の参照は 1 面目の marker を指す。面の切替は `visibility:hidden` なので、その marker は隠れており、**線は引かれているのに矢じりだけが描かれない**（2026/8 に実在。1 面目以外の全面で発生していたが D0-D21 は 1 件も鳴らなかった）。壊れているのは SVG どうしの**名前空間という関係**であり、要素や図を 1 つずつ見る検査では捕まらない |

| SR-15-21 | **別の呼び名で呼び分けた 2 つの系列が、同じ（塗り, 線色, 線幅, 線種）の組へ落ちてはならない**。呼び名の数と、図の上で見分けが付く見た目の数は一致していること | 検査コードは D24。比較する組は 4 要素。正本は `scripts/validate-svg-diagram.py` の `_sign_tuple()`。呼び名の取り出しは同 `_paint_tokens()`（`var(--wave-blue, #4B6681)` なら `--wave-blue`、変数名が無ければ生の値）。同値の判定は CIEDE2000 < 5.0（`DE_EQUIVALENT`）で、半透明は紙へ合成してから比べる | 区別を運ぶのは色 1 つではなく組である。CSS 変数は値を 1 つしか運べないので、色だけを見る検査は「濃度を使い回して 2 系列に同じ見た目を配る」を緑のまま通す。役割（塗り / 線）を鍵に含めるのは、1 つの図形が持つ塗りの名前と線の名前を 2 系列と数えないため。含めないと、塗りと線を別名で書くすべての図形が自分自身と衝突する。同じ呼び名が複数の見た目で使われている図は系列の器ではないので、単射性の対象から外す。`fill` 属性が無いことは「解決できない」ではなく「その channel を名指していない」なので `none` として比較に載せる。ここを外すと `fill` を書かない `<line>`/`<path>`、つまりコネクタのほぼ全部が符号系の検査を素通りする。**凡例の見本を対象から外す理由**: 凡例の見本 (`data-legend`) は単射性の対象から外す。見本は系列そのものではなく系列の見本で、意味を運ぶのは隣の文字である。外さないと、見本を系列と別の綴りで書いた図が「2 系列が衝突している」と読まれる。綴りが違うだけで同じ色であることは正常で、D28 が濃度で照合して許している側なので、D24 だけが咎めると 2 つの規則が食い違う |

| SR-15-22 | **`stroke-dasharray` は実線 / `4 3` / `12 4` の 3 語彙の中にあること**。それ以外の破線を新しく作らない | 検査コードは D25。`DASH_VOCAB = frozenset({"4 3", "12 4"})`（`scripts/validate-svg-diagram.py`）。実装側の対応物は `vendor/scripts/svg-kit.cjs` の `DASH = {fine: "4,3", long: "12,4"}`。**正本は検査側の `DASH_VOCAB`** | 周期は実線 / 7 / 16 で、比が 1 : 2.29 になる組しか残していない。`4 4`（周期 8）を残すと `4 3`（周期 7）と周期差が 1 しかなく、並べても区別が成立しない。語彙を閉じるのは選択肢を減らすためではなく、増やすと必ず「別の名前だが見分けの付かない線種」が生まれるためである |

| SR-15-23 | **破線を付けた図形は、その破線が走る最短の辺に 3 周期分の長さを持つこと**。持てない寸法の図形は線種でなく塗りの濃度で区別する | 検査コードは D26。`DASH_MIN_PERIODS = 3` / `DASH_MIN_EDGE = 21`（`scripts/validate-svg-diagram.py`）。必要長は周期 × 3 で、`4 3` は 21px、`12 4` は 48px。svg-kit 側の `DASH_MIN_SIDE = {fine: 21, long: 48}` は同じ導出の写しで、**正本は検査側の 2 定数**（`DASH_MIN_EDGE` は最も細かい `4 3` が 3 周期入る辺長として置いた下限） | **なぜ 3 周期か**: 2 周期では「破線」ではなく「線が 1 回切れた」に見える。切れ目が 1 つの線は、欠けた実線とも、別の図形に隠された実線とも読める。破線であることが**線そのものの性質として**読み取れる最小が 3 周期。ここを 2 に下げると、細いバーの短辺に付いた破線が実線と混ざり、符号としては消えているのに検査は緑になる。数字を動かす人はこの「1 回切れただけの線」を先に見てほしい。**最短辺で測る理由**: 破線は図形の輪郭を一周する。長辺で 3 周期入っていても短辺が 4px なら、その 2 辺は実線に見える。読者は輪郭のどこを見るか選べないので、成立の判定は最短辺で行う |

| SR-15-24 | **線種を運べない寸法の図形だけで構成された図は、塗りの系列を 5 つ以上要求しないこと** | 検査コードは D27。`SERIES_SUPPLY_NO_DASH = 4`（`scripts/validate-svg-diagram.py`）。供給の 4 段は paper `#F7F6F3` / tone-2 `#9BADBF` / fg-muted `#6A6A68` / ink `#141412`。細いかどうかの判定は `DASH_MIN_EDGE`（SR-15-23 と同じ定数）。供給の数え上げも CIEDE2000 < 5.0 で行うため、綴りが 5 通りでも読者に 4 段としか見えないなら供給を超えていないと判定する | **なぜ 5 で鳴るのか**: 符号の語彙は 形・線・濃淡 の 3 つ。短辺が 21px 未満の図形は線種を運べないので、そこで使えるのは濃淡だけになる。濃淡の段は今日測った 4 段で尽きている。**測定値**: 隣り合う段の ΔE2000 は 21.09 / 25.25 / 28.28 で、これ以上の段を挟むと隣接差が今の 1/2 以下になり、面として並べたときに読み分けられない。つまり 4 は「4 つ用意した」ではなく「4 つしか作れない」。5 つ目の塗りを要求した時点で、どう配っても 2 つが同じ濃度帯へ入る。**D24 との違い**: D24 は配った結果の衝突を見る。D27 は配る前に供給が尽きていることを言う。D27 が鳴っている図は、色を選び直しても直らない（図形の寸法か図解の型を変えるしかない）ので、別コードで分けている。**供給を塗りだけで数える理由**: 線しか持たない細い図形は罫であって系列の器ではなく、濃度 4 段を食い合う相手にならないためである。**凡例の見本を数えない理由**: 凡例の見本は供給の数え上げからも外す。見本の帯は短辺 21px 未満なので細い図形として計上され、凡例を持つ図ほど供給が食われて枯渇しやすくなる |

| SR-15-25 | **凡例の見本が語る符号は、その図の中に実在すること**。図に無い区別を凡例が説明していてはならない | 比較する組は（塗り, 線色, 線種）の **3 つ**で、線幅は比較に含めない。色は綴りでなく濃度で照合する（`_same_density()` = CIEDE2000 < `DE_EQUIVALENT` 5.0）。正本は `scripts/validate-svg-diagram.py` の `_check_legend_truth()`。凡例の識別は `data-legend` 属性。凡例が無い図と、凡例しか無い断片は対象外。検査コードは D28 | 凡例は「この見た目はこの意味だ」という主張であって、図そのものではない。見本と系列は別々に組み立てられるので、片方だけ直した日に静かにずれる。ずれた凡例は読者に「無い区別を探せ」と指示することになり、色を見比べる時間をまるごと無駄にさせる。図が正しくても説明が嘘なら図は読めない。D24 が図の内部の単射性を見るのに対し、D28 はその逆向き（説明 → 図）を見る。**線幅を比較から外した理由**: 凡例の見本は帯や短い線という決まった寸法で描かれ、その線幅は寸法に合わせた表示上の値になる。図の中の主コネクタが 3 でも、凡例の見本が 1.5 で描かれるのは体裁として正しい。ここで幅の一致まで求めると、検査は凡例の**主張**ではなく凡例の**体裁**を測ることになり、正しい凡例が赤くなる。線幅は符号の材料ではあるが、凡例が運ぶ主張の一部ではない。**したがって D24 が 4 要素・D28 が 3 要素であることは意図であり、揃えるべき不整合ではない**。**対象外を 2 つ持つ理由**: 凡例が無い図と、凡例しか無い断片は対象にしない。後者を鳴らすと、凡例だけを単体で描き出したテスト用の SVG が全部赤くなる。**綴りでなく濃度で照合する理由**: 色を綴りで照合すると、見本が `rgba(20,20,18,0.98)`・系列が `#141412` のように書き方だけ違う図が「凡例が図に無い符号を語っている」と鳴る。実際には同じ色が図にあり、読者は何も探していない。しかも偽の赤が出る先は凡例なので、見本を別の書き方で組んだ**正しく作られた凡例ほど鳴りやすい** |

**D24 から D28 の 5 件は、いずれも severity が warning である。**既存資産にどれだけ違反が眠っているか読めない側の検査で、error にすると出荷経路が今日止まる。ただしゴールデンは `--strict` で回すため、そこでは warning も落ちる。**新しい図が穴を持ったまま入ることはなく、既存の図を今日中に直すことも強制されない**、という非対称を意図して選んでいる。上の 5 行には severity を書かない（同じ文が 5 箇所にあると、後で 1 つだけ直されて残り 4 つが古くなる）。なお 5 件の中で error へ昇格する候補が近い順は **D26 → D24** である。D26 は「破線が走る辺に 3 周期入るか」という幾何の判定で、人が見て解釈する余地がない。入らなければ実線に見えるという事実は図の意図と無関係に成立する。D24 がそれに次ぐのは、衝突そのものは事実でも、`fallback` の無い `var()` を解決できず比較から外した図形が残るため、検出が漏れる側に倒れているからである。D25・D27・D28 は語彙や供給の設計判断を含むので、この 2 つより後になる。

### §15-a 図解の機械検証（D0-D28）

人間向けの入口は `references/diagram-layout-contract.md`（語彙 3 表・容量・ラベル方針・
D1 の意図的な検出漏れの理由をまとめてある）。値の正本は本ファイル。

`scripts/validate-svg-diagram.py`。HTML 埋め込み時は `<script>`/`<style>` の中身を同じ長さの空白へ潰してから走査する（Mermaid バンドル JS 内の文字列リテラルを図解として誤検出しないため。長さを保つのはタグ位置＝親 class の探索を壊さないため）。

検査コードは **D 接頭辞**（Diagram）。同じ `scripts/` の `validate-report-visual.py` も C1.. を使うため、番号だけで参照すると別の検査を指す。**agent プロンプトや references から参照するときは必ず `D9` / `validate-report-visual C8` のように出自ごと書く。**

| 検証ID | 検証内容 | 深刻度 | 参照 SR-ID |
|--------|----------|--------|------------|
| D0 | SVG として parse できる | error | — |
| D1 | 図形・文字が viewBox の外へ出ていない | error | SR-1-02 |
| D2 | 座標に NaN / undefined / Infinity が混入していない | error | — |
| D3 | `marker-end` / `marker-start` の参照先が同じ SVG 内で定義されている | error | — |
| D4 | `font-size` が 12px 未満でない | error | SR-3-05 |
| D5 | `<line>` と矢じり付き `<polyline>` / `<polygon>` は水平か垂直（放射状・チャート型は型申告で例外＝無出力） | warning | SR-15-16 |
| D6 | 矩形の座標・寸法が 4px グリッド上（既定オフ。`--check-grid`） | warning | SR-5 系 |
| D7 | 強調色の面塗りが 1 図あたり 2 件以下 | warning | SR-2-05 |
| D8 | `<text>` に Font Awesome の PUA コードがない | error | SR-3-06 |
| D9 | `stroke-width` が 1.25 以上（`0` は対象外） | warning | SR-15-03 |
| D10 | 色がパレット（`TOKENS` / `SERIES`）由来で、純黒でない | warning | SR-2-02, SR-2-08, SR-15-11 |
| D11 | 1 図の要素数（ノード相当＋コネクタ）が複雑度上限以内 | warning | SR-15-09 |
| D12 | `<script>` / 外部 http(s) 参照 / `@import` / 外部フォントが無い | error | SR-3-06 |
| D13 | `font-family` が `textBlock` の既定スタック内（総称ファミリは許可） | warning | SR-3-01, SR-15-11 |
| D14 | CSS 図解の間隔が `--space-*` 由来・px 寸法が `GRID` の倍数 | warning | SR-15-12, SR-15-13 |
| D15 | 注釈・凡例・ノード/コネクタ・フォント階層が複雑度予算以内 | warning | SR-15-14 |
| D16 | CSS 図解の `accent` 色を持つ要素が 2 件以下（D7 の CSS 版） | warning | SR-15-15 |
| D17 | コネクタ `<path>` に斜めの直線セグメントが無い（D5 の path 版） | warning | SR-15-16 |
| D18 | 文字が viewBox に収まり（error）、ラベル箱の内寸（幅 − 16px）にも収まる（warning） | error / warning | SR-15-18 |
| D19 | コネクタの直線区間が箱の辺と同一直線上を 12px 以上走っていない | warning | SR-15-19 |
| D20 | 別々のコネクタの直線区間が同一直線上で 12px 以上重なっていない | warning | SR-15-19 |
| D21 | コネクタの直線区間が箱（帯・枠を除く）の内側を 12px 以上貫いていない | warning | SR-15-19 |
| D22 | 1 ファイル内で SVG の `id` が重複していない（`arrow-*` に限らず `id` 全般） | error | SR-15-20 |
| D23 | 文書内参照（`url(#id)` / `aria-labelledby` / `aria-describedby` / `href="#id"`）の参照先が自分の SVG か共有 defs 置き場にある（`marker-*` は D3 の担当） | error | SR-15-20 |
| D24 | 呼び分けた 2 系列が同じ（塗り, 線色, 線幅, 線種）の組へ落ちていない（符号の単射性） | warning | SR-15-21 |
| D25 | `stroke-dasharray` が実線 / `4 3` / `12 4` の語彙内にある | warning | SR-15-22 |
| D26 | 破線を付けた図形が、破線の走る最短辺に 3 周期分の長さを持つ | warning | SR-15-23 |
| D27 | 線種を運べない細い図形だけの図が、塗りの系列を供給の 4 段より多く要求していない | warning | SR-15-24 |
| D28 | 凡例の見本が語る符号（塗り, 線色, 線種）が図の中に実在する | warning | SR-15-25 |

D0-D9 が**幾何と可読性**を見るのに対し、D10-D13 は**素材**（色・密度・外部依存・書体）を見る。素材の検査が別に要るのは、ビルダー関数の入口にある上限やトークン表が決定論経路にしか効かず、agent が SVG を直接書く LLM 経路を素通りするため。D10-D13 の判定値は検査器へ写経せず実装から実行時抽出する（SR-15-11）。走査範囲も D1 と異なり、`<defs>` / `<marker>` 等のローカル座標系の中身も含めて SVG 全体を見る（座標系の別は素材の除外理由にならない）。

未登録の検証 ID は **fail-closed で error** として扱う（深刻度の指定漏れを黙って通さない）。**D12 は `SEVERITY` 表へあえて登録していない**。根拠は D8（SR-3-06）と同一で error に固定したい検査であり、明示登録しても挙動は変わらないが、登録すると未登録経路を通る検査が 0 件になり fail-closed 機構が一度も使われない飾りになる。**登録漏れではなく、この機構の生きた検証である**（`diagram-layout-contract.md` §4 に後任向けの注意を置いてある）。

---

## §16 本文キーの整合（slideType ごと）

**適用範囲**: `structure.json` の各 slide。テンプレートが本文として読む `content` キーの名前は slideType ごとに決まっており、名前が違えば検証を通っても本文が空で描画される。

| SR-ID | ルール | 値 / 実装 | Why |
|-------|--------|-----------|-----|
| SR-16-01 | **各 slideType は、そのテンプレートが読む `content` の本文キーを持つ**（例: `slide-message` は `content.main`。`content.message` では本文が出ない） | 表は `vendor/scripts/validate-structure.js` の `TEMPLATE_BODY_KEYS`（長い名 17 型）。機械検証は V-044。表の値は「テンプレートのプレースホルダ名」ではなく「`render-slide.cjs` が読む源のキー」で、派生キー（`svg` / `headers` / `gridRows` 等）は render 側が計算するため両者は一致しない。表とテンプレートのずれは `tests/test_template_body_keys.py` が render して検出する | `vendor/scripts/templates/` には短縮名（`message.html.tpl`）と長い名（`slide-message.html.tpl`）が対で置かれ、`loadTemplate` は slideType そのままの名前を先に引くので旧世代の deck は短縮名テンプレートへ落ちる（どちらも現役）。ところが対の間で本文キーの名前が違うものがあり（`message` は `{{message}}` / `slide-message` は `{{main}}`）、短縮名の書き方のまま slideType だけ長い名にすると、汎用のテキスト有無検査は通るのに本文が空の `<p class="main-message"></p>` が出る。描画してからでないと気付けず、充填率の統計も 0.000 の面で汚れる |

---

## §18 出力ファイルの構成

| SR-ID | ルール | 値 / 実装 | Why |
|-------|--------|-----------|-----|
| SR-0-01 | **生成した deck は CSS と JS を HTML から分離して出力する**（`index.html` にインライン `<style>` を置かない。インライン `<script>` も置かない。ただし `src=` を持つもの と `type="application/json"` は分離済み／データとして許す） | 判定は `vendor/scripts/phase-gate.js:162-171`（Gate 2 = `P3->P3_5`）。構成段階の `validate-structure.js` V-020 はこの Gate へ委ねる。**ただし既定経路ではこの Gate は選ばれない**（下記） | インライン化すると 1 ファイルに 3 言語が混ざり、CSS 側の検査器（`validate-visual-generation.py` / `lint-contract-drift.py` の css-route）が読む対象を失う。分離は見た目の作法ではなく、**後段の検査が届く前提** |

> **この規則は既定の経路では判定されていない**（実測 2026-08-14）。`vendor/scripts/workflow-manager.js` の `detectPhase()` は**ファイルの存在**で phase を決めるため、`index.html` があれば P3_5 と判定され、`P3->P3_5` の Gate 2 は選ばれない。逆に `index.html` が無ければ Gate 2 の検査対象そのものが無い。**規則を評価できる状態と、Gate が選ばれる状態が排他になっている。**唯一の抜け道である `.workflow-state.json` は、このプラグイン内に**書く箇所が無く**、出荷済みの実 deck にも 1 件も存在しない。実行体は在るので `no-checker` ではないが、**在ることと通ることは別**である。配線の修正は 8/15 の凍結明けまで見送り（`references/known-unfixed.md` K-005）。

---

## §17 仕様本文がまだ無い SR の一覧（欠落台帳）

**ここは規則を定める節ではない。**`vendor/scripts/validate-structure.js` の `V_DEFINITIONS` が `sr:` で名指ししているのに、この spec-registry のどこにも規則行が無い SR-ID を並べる。検査 ID の側には名前があるが、その名前が指す規則本文が存在しない状態で、V-001 と同じ形（規則はあるが誰も見ていない）の裏返しにあたる。

2026-08-14 時点で **6 種 / 参照している V-ID は 9 件**（SR-0-01 は §18 へ規則行として出たので、この表から消えた）。本文が書かれた SR はこの表から消え、該当する節へ規則行として移る。**この表の行数が減らないなら、台帳が増えているだけである。**

| SR-ID | 参照している V-ID | 本文をどこに書けば消えるか |
|-------|------------------|--------------------------|
| SR-0-02 | V-025（FAIL / 構成の基本的な妥当性） | 行き先未定。**規則名と実装の食い違いは名前を実装へ寄せて決着済み**。`V-025` の desc は「標準 CSS クラス名のみ使用」から、実装が実際に見ている 3 つ（slideType が有効・JSON schema 適合・基本構造エラーなし）の受け皿を兼ねる説明へ変更した（`vendor/scripts/validate-structure.js`。旧 desc の行き先と分割候補は同ファイルのコメントに残っている）。残るのは本文をどの節へ置くか |
| SR-V8-COVER | V-031 / V-032（FAIL） | v8 拡張フィールドのデータ整合を扱う節が要る。候補は §16（本文キーの整合）で、「データが自分自身と食い違わない」という主題が近い。寄せるか新節を立てるかは未決 |
| SR-V8-INDEX | V-033 / V-034（FAIL） | 同上 |
| SR-V8-DIAGRAM | V-035 / V-036（FAIL） | 同上 |
| SR-V8-PAGE | V-037（FAIL） | 同上 |
| SR-V8-COLOR | V-038（WARN） | 同上 |

各 V-ID が実際に何を見ているかは `V_DEFINITIONS` の `desc` にある。**それを規則本文の代わりに読まないこと。**desc は検査の説明であって、なぜその規則があるかを持たない。加えて desc は実装とずれることがある（SR-0-02 は実際にずれていて、名前を実装へ寄せて直した）。

---

## 改訂方針

- **本ファイルが正本**。既存 references / SKILL.md ベストプラクティス表との矛盾は本ファイルで明示し、`SR-7-09` のように現状/将来形を記録する。
- 新規ルール追加時は対応する §に SR-ID を採番し、`Why` と `実装値` を必ず併記する。
- ルール削除時は SR-ID を欠番化し（再利用しない）、`§11` の検証 ID 対応表も更新する。
- 既存 references の段階的移行: 各 reference の冒頭に「正本: spec-registry.md SR-X-XX 参照」を追記し、本ファイルの該当 SR-ID へ誘導する（後続タスク）。
