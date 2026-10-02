# 保守の手引き

スキル自体を変えるときだけ読む。通常のレポート生成では読まない。

## 正本と責務

編集元は `aidd-agent-kit/skills/report-design-system/`、配布先は `.claude/skills/report-design-system/` と `.agents/skills/report-design-system/`。正本を編集し、`bash aidd-agent-kit/sync-project-mac.command` → `bash aidd-agent-kit/verify-codex-layout.sh` で反映・一致を確認する。配布先は直接編集しない。

- 外部への入口は `scripts/report.mjs`。通常は init・build、早期診断は check、依頼時の厳格検証だけ verify・done、実行部隊向け資料は hearing・handout を使う。個別スクリプトを別の公開経路にしない。
- 機械可読な正本は、レポートのセクション・情報量の段階・上限・列挙値・review の契約が `scripts/lib.mjs` と `scripts/check-llm.mjs`、実行部隊向け資料の質問・字数が `scripts/hearing.mjs`、資料の並びが `scripts/build-handout.mjs`。1回にユーザーへ聞く数の上限 `ASK_LIMIT` は、レポート (`prompts/analyst.md`) と資料 (`prompts/handout.md`) で共通なので `lib.mjs` に置く。prompt に転記した値は `selftest.mjs` が正本と照合する。
- `scripts/inputs.mjs` はCSV・JSON・D1 JSONの行読込と入力manifestの作成・hash検証の正本。`new-report.mjs`、生成された `analysis.mjs`、厳格証跡は同じ契約を使う。既存レポートを移すときは `writeInputManifest(reportDir, files)` に実際に読む全入力を渡して初回だけ記録し、分析では毎回 `readInputManifest(reportDir)` を通す。
- `scripts/new-report.mjs` と `scripts/profile-data.mjs` は初期化、`scripts/stats.mjs` は計算、`scripts/charts.mjs` と `scripts/compose.mjs` は表現部品を担う。
- 専門用語と図の読み方の説明文は `scripts/glossary.mjs` だけが持つ。用語 (`GLOSSARY`: 何の値か・どう読むかの2文と検出する書き方) と図の読み方 (`CHART_HOWTO`: `charts.mjs` の図の種類ごとに1文) が正本で、本文への用語マーク付けと用語集の組み立て (`markTerms` / `glossaryBlock`) も同じファイルが行う。説明は常時表示しない、実体は用語集の `<dd>` 1か所だけが持つ、という表示契約はファイル冒頭に書いてある。同じ文を `report.js` や雛形へ写さない。マークの密度 (読み手が視線を移すまとまりに同じ用語を何回出すか) は `markPolicy` で決める。
- 用語の表示・固定・閉じる操作は `jp-web-design/assets/reference/term-ui.js` が正本で、`sync-kit.mjs` が `assets/vendor/term-ui.js` へ取り込む。`lib.mjs` はそのローカルJSを `report.js` の前に埋め込むため、reportスキル単体で生成できる。図の値・印刷・目次は `report.js`、用語の見た目はvendor部品CSSが担う。レポート側で用語の状態機械や汎用CSSを再定義しない。
- `scripts/build-report.mjs` と `check-report.mjs` は通常 build の生成・静的検査、`verify-render.mjs` と `build-state.mjs` は依頼時だけの実描画・証跡を担う。
- `scripts/hearing.mjs` はヒアリングシートを担う (質問 `QUESTIONS`・シートの形式と読み取り・「AI が直すこと」と「ユーザーに聞くこと」の判定・現場向けの言い換え検査・レポートの打ち手と前の月のシートからの下書き)。どの欄をユーザーが決めるかは `QUESTIONS` の `decide` だけで決まる。`scripts/build-handout.mjs` はシートからの資料の生成と検査を担い、並びとチップの文言は `HANDOUT_KINDS` が正本。件数・欄の有無など生成器の形で決まることは検査せず、selftest が確かめる。
- `assets/` は雛形と埋め込み資産。雛形 (`template.src.html`) の構造契約は `check-report.mjs` が検査し `selftest.mjs` が同期を確かめる。vendor の出所と digest は `assets/vendor/SOURCE.json` が持つ。
- 配色の基本色はキット正本 `aidd-agent-kit/skills/jp-web-design/assets/standard/standard-color-system.css` だけが持つ。色を変えるときはキット側を直し、`sync-kit.mjs --kit <キット>` で `assets/vendor/` へ取り込み直す。レポート側に上書き層は置かない (`report.css` にも色の値を書かない)。取り込んだ基本色が文字として白地で読めるかは `check-report.mjs` の E03 が、役割トークンの検査ペアはキット側の `check-standard-contrast.mjs` が検査する。
- 通常変更のゲートは `scripts/smoke-test.mjs`。全変異・統計・図・証跡の回帰ゲートは `scripts/selftest.mjs` に分離し、必要な変更でだけ使う。

## 変更の流れ

1. 変える内容の正本を上の一覧で確かめ、そこだけを直す。prompt に転記した値を変えたら、同じ変更で転記と selftest の照合もそろえる。
2. 機械契約を変えたら、正常系だけでなく、欠落・不正値・依存切れの変異ケースを `selftest.mjs` に追加する。通常の文書変更では増やさない。
3. 文書は意図と使い方を説明する。人間の操作に不要な列挙・フィールドは機械正本のみに置く。
4. まず高速スモークを実行し、失敗の最初の1件から直す。
5. 検査器・統計・図・生成器・vendor 同期を変えた場合だけ全回帰を実行する。レポート雛形または描画を変えたときは、その後に実レンダリングを目視する。

```bash
S=aidd-agent-kit/skills/report-design-system/scripts
node $S/smoke-test.mjs
```

全回帰が必要な変更だけ実行する。`selftest.mjs` 内で vendor digest も検査するため、`sync-kit.mjs --verify` の重複実行は不要。

```bash
node $S/selftest.mjs
```

キットの更新を取り込む場合だけ、キットのルートを明示する。スクリプトに場所を推測させない。

```bash
node $S/sync-kit.mjs --kit <キットのルート> --check
node $S/sync-kit.mjs --kit <キットのルート>
node $S/selftest.mjs
```

## 追加時の判断

- 部品は `compose.mjs`、図は `charts.mjs`、統計手法は `stats.mjs` に置き、生成物側へ同じ実装を書かない。
- 図を増やすときは `CHART_HOWTO` にその図の読み方を1文足す (無いと `svgOpen` が例外で止まる)。専門用語を新しく使うときは `GLOSSARY` に足す。どちらも `glossary.mjs` の1か所だけ直す。
- HTML を出す生成器は、外枠 (`pageShell`)・見出し帯 (`secHead`)・エスケープ (`esc`)・見えている文 (`visibleText`)・書き出し (`writeAtomic`)・検査結果の表示 (`printResult`) を `lib.mjs` から使い、同じものを書き直さない。
- 統計手法は対象範囲の定番だけを追加し、既知値と失敗ケースを selftest へ入れる。因果推論や高度な予測を、記述・比較用の関数群へ混ぜない。
- 参照文書に巨大なプロンプトや別 workflow を貼り付けない。構造汚染の回帰は selftest の reference-integrity guard で止める。
