# Changelog — x-longpost-creator

本 plugin の変更履歴。plugin 化を機に v1.0.0 から新規開始する。
移植元スキル（vault 内 `x-longpost-creator` v3.14.0）の履歴は移植していない。

## 1.2.2 — 2026-09-02

他の 20 plugin が満たしていた plugin 横断の規約を、本 plugin だけが満たしていなかったのを揃えた版である。機能の変更はない。

これらは plugin 総数を直書きしたテスト (`assert plugin_count == 20`) が件数の段階で先に落ちていたため、その先の中身の検査に一度も到達しておらず、追加当初から検出されていなかった。総数を 21 に直して初めて全項目が走った。

### 変更

- `skills/run-skill-feedback/` を配備した。全 plugin へ同一内容で配備される共通 skill で、正本は harness-creator が所有する。install 先には自分の plugin ディレクトリしか展開されず symlink は切れるため、実体コピーで持ち `runtime_dependencies` へ `owned-vendored` として所有者を明記する。あわせて `entry_points` / `plugin-composition.yaml` / `artifact-delivery.json` / README へ反映した
- `references/package-contract.json` を schema 準拠に直した。`package_mode` に schema の列挙に無い `standalone` を書いていたのを `bundle` にし、`runtime_dependencies` へ node / codex を `external-runtime` として書いていたのを取り下げた。この枠は「他 plugin が所有する capability」の申告先であり (schema の `owner` は plugin 名、`local_path` / `owner_route` は `skills/` パスに固定されている)、PATH 上の外部バイナリを書く場所ではない。node / codex の要件は `notes` へ移した
- 4 skill の実行手順にある `${CLAUDE_PLUGIN_ROOT}` を `${PLUGIN_ROOT:-${CLAUDE_PLUGIN_ROOT}}` へ揃え、frontmatter へ `runtime_root_policy: host-skill-path` と本文の Runtime root contract 節を追加した。Claude Code は `CLAUDE_PLUGIN_ROOT` を与えるが Codex は与えないため、二段構えにしないと Codex 側で解決できない

## 1.2.1 — 2026-09-01

「改善ループは利用者の選択より後にしか動かない」ことを、散文だけでなく frontmatter からも機械的に読み取れるようにした版である。

### 変更

- 4 skill の `feedback_contract` へ `activation_state: semantic_evaluator_started` を追加した。本文の「Post-choice selected improvement execution」節には元からそう書いてあったが、`lint-entrypoint-artifact-first.py` は frontmatter 側の宣言を見るため、宣言の無い `max_iterations > 0` は「選択前に回りうる改善ループ」として fail-closed で止まっていた。散文と機械宣言が食い違ったのであり、規定そのものは変えていない

## 1.2.0 — 2026-09-01

パターンAから X 5:2 と note 実 PNG 1280x670 のサムネイル2枚を必ず作る導線へ統一した。図解は明示指定時のみ optional である。

### 変更

- `build-visual-prompts.js` / `generate-images-codex.js` / `validate-visual-assets.js` の既定対象を2サムネイルに揃え、note の作業 PNG 自体を 1280x670 で生成・strict 検証するようにした
- サムネイル主文の下限を6文字にし、利用者が良いと判断した過去投稿の見本に合わせ、図形のみ控えめな紙工作風の質感と浅い影を許可した。人物、情報商材的意匠、文字の影、写真的な3Dは引き続き禁止する
- `lint-thumbnail-prompt.js --structure` に TL-11（構造データと画像内文言の一致）と TL-12（2サムネイル間の STYLE / TYPOGRAPHY / NEGATIVE 一致）を追加した
- `generate-images-codex.js` の meta にプロンプト・構造・参照画像・生成 PNG の SHA256、Codex セッション、executor/version、seed 非対応を記録するようにした
- `record-thumbnail-review.js` を追加した。指定作業フォルダの同じ絶対パスを Claude Code は `Read`、Codex は `view_image` で開き、5項目の PASS と画像 SHA256 を review receipt に結び付ける。`embed-visual-paths.js` は receipt と現物 hash が一致しなければ fail-closed で停止する

## 1.1.2 — 2026-09-01

機能の変更はない。1.1.0 の内容をリリース記録（`marketplaces/local/plugin-fingerprints.json`）へ初めて登録した版である。

`build-plugin-release.py` は「記録に無い」ことを「内容が変わった」とみなして patch を進めるため、初登録では必ず番号が1つ動く。さらに fingerprint は本 CHANGELOG も対象に含むので、登録後に履歴を書き足すとまた差分になる。そのため版番号は**先に**この見出しへ書き、その状態で登録を1回だけ走らせて収束させている。1.1.0 と 1.1.1 は記録に載る前の番号であり、配布されていない。

## 1.1.0 — 2026-08-31

長文投稿の冒頭に置く図解と、X・note のサムネイルを Codex Image2 で生成する経路を追加した。既存の長文投稿・短文投稿の挙動は変えていない。

### 追加

- skill `run-x-visual-generate`。確定した長文投稿パターンAの論理構造を三分割へ再編し、図解（16:9）・X サムネイル（5:2）・note サムネイル（1280x670）の3枚を生成して投稿ファイルの該当欄へ差し込む
- 画風と版面の references 4 本。機械可読正本 `references/visual-spec.json`（kind・生成/納品寸法・比率・横断 text rule）と、意味説明の `references/diagram-style-canon.md` / `references/icon-vocabulary.md` / `references/thumbnail-specs.md`
- prompts 3 本。`x-longpost-analyze-visual-structure.md`（本文 → `visual-structure.json`）、`x-longpost-design-diagram-prompt.md` / `x-longpost-design-thumbnail-prompt.md`（構造データ → 5 ブロック構成の生成プロンプト）
- scripts 4 本。`build-visual-prompts.js`（構造データの制約検証と meta 生成）、`generate-images-codex.js`（codex 経由の生成と PNG 署名による回収）、`validate-visual-assets.js`（PNG の IHDR から寸法と color type を直読し比率と背景の不透明性を検証）、`embed-visual-paths.js`（投稿ファイルへの冪等な差し込み）
- `tests/scripts-plugins/test_x_longpost_creator__visual_pipeline.py`（64 ケース）。制約違反を1点ずつ注入するケースと無課金の偽 Codex 統合ケースで、検証器が実際に止め、session 画像を指定先へ回収できることを確かめる。生成 meta・画像検証・説明表が `visual-spec.json` と一致することも直接検査する
- env `XLP_IMAGE_DIR`（投稿固有の作業先として明示）と `XLP_ATTACHMENT_DIR`（最終添付先。未設定時は `${XLP_VAULT_ROOT}/02_Configs/Extra`）
- `references/thumbnail-style-canon.md`。サムネイル2種（5:2 と 1280x670）の画風・配色・禁止事項の正本。絶対ルール TS-01〜TS-12、インパクトを装飾ではなく余白と要素削減で作る4手段、情報商材的意匠の名指し禁止リスト6分類、サムネイル固有の退化7種を持つ
- `scripts/lint-thumbnail-prompt.js`。サムネイル2種の `.prompt.txt` を**画像生成の前**に検証する（TL-01〜TL-10）。5ブロックの充足、palette の hex 指定、図解 STYLE の混入、人物禁止、情報商材的意匠6分類、透過禁止、余白と枠線、canvas 比率、引用日本語の本数と字数、絵文字と禁止語を見る
- `scripts/lib/png-background.js`。PNG の IDAT を zlib で展開して四隅（各辺から 2% 内側）の画素を採り、背景色を機械判定する。フィルタ解除は 5 種すべてを実装。対応範囲外（bit depth 8 以外・インタレース・パレット）は判定せず WARN に留める
- `visual-spec.json` に `palettes`（`diagram` / `thumbnail`）と、kind ごとの `palette` / `styleCanon` / `background` を追加した。配色の差し替えはこの1ファイルで完結する
- `assets/reference-images/`（`manifest.json` + `README.md`）と `scripts/lib/reference-images.js`。画風の見本画像を kind ごとに `codex exec -i` で添付する。線の太さ・塗りの密度・簡略度は数値へ落とすと窮屈になるため、文章の canon ではなく絵で渡す。宣言だけあって実体が無い見本は毎回 WARN として出力と `meta.json` の `referenceImages` に記録し、`--require-reference-images` で FAIL へ昇格できる。置き場は `XLP_REFERENCE_IMAGE_DIR` で差し替えられる
- 図解の見本 `diagram-sample-01.png`（対比2列＋具体例3列）と `diagram-sample-02.png`（BEFORE / HOW / AFTER の縦3列）を実体として同梱。利用者自身の過去の生成物のうち canon に合致するものを構造型が重ならないように2枚選び、出典を `manifest.json` の `source` に記録した。サムネイルの見本 `thumbnail-sample-x.png` / `thumbnail-sample-note.png` も同じ投稿から採り、X と note で同じ配色・同じ図形語彙のまま版面だけが変わる例（TS-12）として対にした。`diagram-icon-sheet.png` のみ未配置で、既定では WARN として毎回報告される

### 変更

- `run-x-longpost-create` に Step 8（Phase 4 への引き継ぎ）を追加した。画像生成を明示した別セッションでは pre-choice に図解1枚だけを生成・提示し、light / standard / detailed 選択後だけサムネイル2枚と最終 embed へ進む
- 同 SKILL.md の絵文字の判定境界の表を `ref-x-longpost-canon` への参照へ置き換えた（同じ表が 2 箇所にあったため。Step 8 の追記余地はこの重複削除から作った）
- 同 SKILL.md のリソース一覧にあった本数（agents 11 本 / scripts 10 本 / references 14 本）を実態へ修正した

### 修正

- **指定フォルダに回収した画像を現物表示するホスト境界と、実投稿の添付規則が未定義だった**。`generate-images-codex.js` と `validate-visual-assets.js` が回収済み PNG の絶対パスを返し、Claude Code は `Read`、Codex は `view_image` で同じ実体を開いた後にだけ `artifact_presented` とする契約を追加した。また、実運用のX投稿405画像参照と直近投稿を確認し、3つの固定欄、一意 basename の `![[...]]`、`02_Configs/Extra` の添付実体という構造に合わせた。`embed-visual-paths.js --attachment-dir` は投稿 basename + kind の一意名で配置するため、投稿間で `diagram.png` が上書きされない。
- **透過背景を機械検査していなかった**（live-trial で実際に発生）。`validate-visual-assets.js` は PNG 署名・寸法・比率しか見ておらず、生成系が「純白背景」を「背景を描かない」と解釈してアルファ付きで返した note サムネイルが緑で通っていた。この画像は白いビューアでは正常に見えるので目視もすり抜け、貼り先がダークテーマになって初めて黒地に黒文字で全文が消える。IHDR の color type（4 / 6）を読んで `has-alpha` で FAIL にし、`diagram-style-canon.md` の VS-02 に不透明の要件を、§5 に退化パターンとして追加し、図解プロンプトの NEGATIVE に不透明の明示を入れた。失敗理由は `reasons` 配列で複数返すようにした（透過と比率が同時に立つとき、片方だけ直して再生成しても緑にならないため）
- **`nestedType` が `T1` `T4` `null` のときの LAYOUT 追記規則が欠けていた**（live-trial で発覚）。`T2` `T3` の規則しか書かれておらず、残りの型では追記内容が実行者の判断に委ねられ、同じ構造データから毎回違う版面が出る状態だった。`x-longpost-design-diagram-prompt.md` に「何も追記しない」と理由つきで明示した
- `x-longpost-design-thumbnail-prompt.md` の note サムネイルの LAYOUT が生成寸法ではなく納品寸法を canvas に指定していたため、比率指定へ揃えた。kind・生成/納品寸法・比率の実体は `visual-spec.json` に閉じ、prompt と script は参照する
- `validate-headings.js --file` に F4（Aの Markdown 見出しとBの先頭タイトルを除き、空白・改行正規化後の本文が同値）と F5（Bの非空本文行が1文1行）を追加した。既存テンプレートを scratch の正規 basename へ展開し、違反候補を正規配置へ昇格させない統合テストを追加した
- `generate-images-codex.js` は `XLP_CODEX_BIN`（既定 `codex`）を課金ループ前に preflight し、shell 文字列ではなく executable + argv で起動する。stdin は ignore、stdout/stderr はログ fd へ接続し、実行不能時は dry-run を含め retry なし exit 2 とした
- 図解 prompt は pre-choice diagram-only、サムネイル prompt は post-choice thumbnails-only に統一し、旧3件一括処理の記述を除去した
- **サムネイルが図解の画風規範を継承していたため、利用者のサムネイル要件を表現できなかった**。旧 TP-C02 は「STYLE ブロックは図解と完全に同一の文字列を使う」と定め、`thumbnail-specs.md` は「VS-02 から VS-10 をそのまま適用する」としていたが、これは利用者の指定（人物を使わない・背景は優しい白っぽい色・情報商材的でないインパクト）と、VS-02（純白背景）・VS-03（人物は黒塗りシルエット）で正面から矛盾する。どちらかを曲げるのではなく、目的の違う2つの正本へ分けた。図解は「理解させる絵」、サムネイルは「足を止める絵」であり、目的が違えば最適な画風も違う。配色はいったんオフホワイト #F7F5F1 / 墨黒 #1A1A1A / 深い藍 #2F4858 に確定したが、後述のとおり実測値へ寄せ直した（いずれも 2026-08-31）。旧 TH-04「図解と同じアイコン絵柄を使う」は人物禁止と両立しないため廃止し、3枚の統一感は線の太さ・簡略度の粒度で作る方針へ変えた
- **「情報商材屋っぽくない」「インパクトがある」が規範に表現されていなかった**。否定形と抽象語のままでは拡散モデルに伝わらないため、前者は禁止する具体物6分類（文字の装飾・配色・記号・数字の煽り・版面・語り口）へ、後者は「装飾を足す」ではなく「余白・要素削減・主文の極大化・色を1箇所」の4手段へ翻訳した。両者は `lint-thumbnail-prompt.js` の TL-05 が NEGATIVE ブロックの充足として機械検証する
- **背景色を機械検査していなかった**。規範に純白（図解）とオフホワイト（サムネイル）の2つの指定が並存する以上、生成系はどちらへも転ぶ。サムネイルが純白で返っても単体では正常に見えるので目視では捕まらないが、貼り先の白い UI と地続きになって画像の輪郭が消える。`validate-visual-assets.js` が `background-too-white` / `background-not-white` / `background-too-dark` で FAIL にする
- 課金前のゲートを2層にした。従来は構造データ（`build-visual-prompts.js`）だけが生成前の関門で、プロンプト文が規範を満たしているかは生成後の目視に委ねられていた。画像を見てから直すループは1周ごとに課金と十数分がかかるが、プロンプト文の検査は0秒0円で同じ制約を止められる
- **`generate-images-codex.js` の起動指示文が kind によらず「純白背景・白黒」を強制しており、サムネイルの規範を上書きしていた**。`x-longpost-design-thumbnail-prompt.md` と `lint-thumbnail-prompt.js` の TL-03 が図解 palette の混入をプロンプト文から排除しても、その後段の起動指示文が同じ指定を書き戻していたため、オフホワイト背景と藍アクセントは一度も生成へ届いていなかった。指示文を `visual-spec.json` の palette から kind ごとに組み立てる形へ直し、サムネイル側には人物禁止も載せた。回帰テストは指示文の分岐を潰す変異注入で検出力を実測している
- 画風の見本画像が正本として保存されておらず、線の太さや簡略度が canon の文章からしか伝わらなかった。この2つは数値へ落とすと窮屈になり、絵で渡すほうが正確である。`codex exec -i` で見本を添付する経路を作り、見本は複製の対象ではないこと（構図・文言・個々のアイコンを写さない）を指示文で明示した
- **サムネイルの配色を、規範の机上値から利用者が実際に良いと判断した生成物の実測値へ寄せ直した**。旧規範はオフホワイト #F7F5F1 / 深い藍 #2F4858 の1アクセントだったが、実物を測ると背景 #F8F3E6、アクセントは**役割の違う2色**（セージ #C1C2A0 が構造の線・台・輪、テラコッタ #D87C45 が補助句の帯1枚で文字は白）だった。規範を実物へ合わせないと、見本画像と canon が食い違ったまま両方が生成へ渡り、生成が割れる。TS-05 を「1色だけ」から「色数ではなく役割を固定する」へ書き換えた。彩度の低い色が構造を担い、高彩度を1枚に閉じ込めるので、2色でも視線の着地点は1つに保たれる
- 生成の起動指示文で「アクセントは1色だけ」と言うと、どちらの色を捨てるかを生成系が勝手に決めてしまう。`describeAppearance` はセージとテラコッタを**用途つきで**別々に指示するようにした
- `lint-thumbnail-prompt.js` の TL-02 が検査するロールを `palette` から導くようにした（`paletteRoles`）。旧実装は背景・文字・アクセントをコード側に並べていたため、規範に色が増えても検査だけが取り残され、「規範にはあるがプロンプトには書かれていない色」が課金前の関門を素通りしていた。palette の全 hex について、その1色だけを STYLE から落とすと必ず TL-02 が挙がることをテストで固定した

## 1.0.1 — 2026-08-31

elegant-review による構造是正。機能挙動は変えていない。

### 変更

- `agents/` を `prompts/` へリネームした。11 本は frontmatter を持たず Task で起動される sub-agent ではなく、各 skill が Read で読み込む phase 別のプロンプト文書である。`lint-plugin-composition.py` が `agents/*.md` を無条件に agent public surface とみなすため、`kind: prompt` の宣言と両立させるにはディレクトリ名も実態に合わせる必要があった（`ubm-goal-setting` の `prompts/*.md` と同じ形）
- `scripts/` 10 本と `assets/` 1 本を skill 配下から plugin ルート直下へ移した。`lint-skill-tree` 第 10 条が `skills/*/scripts/` を `.py` / `.sh` に限るため（先行例: `slide-report-generator`）。副産物として、他 skill が `run-x-longpost-create` の内部を直接参照するクロススキル参照が解消された
- 共有 references 6 本を plugin ルート `references/` へ移した
- `plugin-composition.yaml` の `dependencies` を正本スキーマ（Capability 間 DAG）へ書き直し、32 本のエッジと `kind: script` 10 本を宣言した
- `SKILL.md`（run-x-longpost-create）本文を 446 行から 298 行へ縮めた。削ったのは正本と重複していた 3 セクションのみで、ワークフロー図 2 本は `references/workflow-diagrams.md` へ移設した（削除ではない）

### 追加

- `skills/run-x-longpost-create/references/resource-map.yaml`（Progressive Disclosure の機械可読索引）
- `tests/scripts-plugins/test_x_longpost_creator__log_usage_parity.py`（CJS/ESM 二重実装の等価性を 6 CLI ケースで機械保証）
- `ref-x-longpost-canon` へ絵文字の判定器に関する注記。`\p{Extended_Pictographic}` は処理系で範囲が異なり、星印のように実行時定義が分かれる文字がある。検査は必ず `check-no-emoji.js` を通す

## 1.0.0 — 2026-08-31

移植元スキル v3.14.0 の全内容を harness plugin へ移植した初版。

### 追加

- skill 4 本
  - `run-x-longpost-create` — 長文投稿の生成統括（Phase 0〜3.5）
  - `run-x-multipost-create` — 文字起こしから短文投稿 8 本
  - `run-x-shortpost-optimize` — 任意の文章 1 本を短文投稿へ最適化（4 フェーズ）
  - `ref-x-longpost-canon` — 正本の所在一覧と、移植時に解消した重複・矛盾の記録
- `prompts/` 11 本（`x-longpost-` prefix）。Task で起動する sub-agent ではなく、各 skill が Read で読み込む phase 別のプロンプト文書
- references 13 本 + `output-config.json`（skill 横断で共有する 6 本は plugin ルートの `references/`、`run-x-longpost-create` 固有の 7 本と `output-config.json` は `skills/run-x-longpost-create/references/`）
- scripts 10 本（`.js` 9 本 + `log_usage.mjs` 1 本）/ assets 1 本（実体は `skills/run-x-longpost-create/` 配下に一元化）

### 変更（移植時の決着）

移植元では同じ規定が複数箇所に実体で重複し、値が食い違っていた。以下 8 件を確定させた。詳細と根拠は `ref-x-longpost-canon` の「移植時に解消した重複・矛盾」を参照。

1. **長文の文字数レンジを 1800〜2200 に統一** — 移植元は「2000文字以上」「1800〜2500」「1800〜2200」の 3 通りが併存していた
2. **禁止表現リストの正本を `references/title-guidelines.md` §3.3 に一本化** — タイトル用（§3.3.1）と本文用（§3.3.2）へ分割し、4 箇所にあった実体を参照へ置換
3. **制約 ID を agent 別プレフィックスで一意化** — `CONST_007` が 4 つの agent で別の意味に使われていたため `TR-` / `MP-` / `SP-` / `IC-` を付与
4. **短文投稿エージェントを 1 本へ統合** — `create-short-post` と `short-post-optimizer` が同一責務で並存していたため後者へ吸収し、2 つの呼び出しモード（独立実行 / 長文フロー内）を §4.5 に規定
5. **見出し2の個数を 3〜8 個に確定** — `validate-headings.js` の check ID H5 の実装値を正本とし、常に `--strict-h2-count` を付けて FAIL 扱いにする
6. **`emoji-selection-guide.md` を `heading-title-guide.md` へ改名** — v3.3.0 の絵文字全面禁止で中身は見出しタイトル作成ガイドへ改訂済みだったが、ファイル名だけ旧名で残っていた
7. **出力先の実パスを plugin から全廃し env のみで解決** — 解決順は `XLP_OUTPUT_DIR` → `XLP_VAULT_ROOT` の 2 段のみで、既定値へのフォールバックは持たない。どちらも未設定なら `generate-filename.js` が終了コード 1 で停止する（fail-closed）。00ネタファイルは `XLP_NETA_FILE` で指定する
8. **重複・冗長ファイルを整理** — `output-template-legacy.md` / `references/changelog.md` / `LOGS.md` は移植せず、`log_usage.mjs` のみ ESM 環境向けとして同梱

### 既知の制約

- `distributable: false`。特定の書き手のスタイルゲノムと個人 vault の運用前提（00ネタファイル・Obsidian テンプレート）に依存するため、公開 marketplace の配布対象にしない
- 実行前に `XLP_OUTPUT_DIR` または `XLP_VAULT_ROOT` の設定が要る。未設定では出力に到達できない（fail-closed。既定値へのフォールバックは意図的に持たない）
- scripts は Node.js v18 以上に依存する（移植時に Python 化せず、そのまま移植する判断）
