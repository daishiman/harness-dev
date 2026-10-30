# Flyer Studio

誰に何をしてもらいたいか（読者・価値・行動）と確定事実を少ない往復で聞き取り、公開条件と印刷品質を守ったチラシを作り、作った者とは別の担当が最新の完成画像で合否を確かめるローカル用プラグインです。AI は目的・制約・評価基準から次の行動を選び、固定の書体・pt・座標を全案件へ当てはめません。

6 skill は、資料の解釈と候補の比較、実際の制作、別担当の独立評価、納品完了案件からの改善仮説を分担します。AI が既存の Agent・Ref（担当の契約）・Knowledge（指針）・Schema（成果物の型）を使う共通の進め方は [stage-common](references/stage-common.md#共通の判断手順) にまとめています。

写真・漫画・墨絵など、どんな様式にも対応します。イメージが言葉にならなくても、AI が回答や支給資料・素材から読み取った根拠つきの様式案を出すので、選ぶか任せるだけで進められます。

## 入口

| 入口 | 使うとき |
|---|---|
| `/flyer-studio:run-intake-flyer` | 新しく作る。全質問を 1 枚で聞き、不足と矛盾だけを追加で確認する |
| `/flyer-studio:run-analyze-flyer` | 既存のチラシを診断して改善する |
| `/flyer-studio:run-create-flyer` | 確認済みの案件や承認済みの提案から制作を続ける |
| `/flyer-studio:run-learn-flyer` | 納品後に傾向を記録し、次の案件の参考にする |

提案の評価と完成画像の評価は、制作とは別 context（独立した作業単位）の担当が行います。工程と FIX（修正指示）の戻り先は [workflow](references/workflow.md)、責務の境界と正本の地図は [architecture](references/architecture.md)。

## 準備

```bash
npm ci --ignore-scripts
python3 scripts/build-flyer.py doctor
claude --plugin-dir .
```

この README のある dir が PLUGIN_ROOT。Node.js 22 以降、Chrome か Playwright Chromium、Poppler の pdftoppm・pdfinfo・pdffonts を使います。ブラウザを明示する場合は FLYER_BROWSER に実行ファイルの絶対パスを指定します。[INSTALL](INSTALL.md) に両ホストのローカル導入方法があります。作成と検査でグローバル設定・信頼設定・外部同期を変更しません。

## 設計と素材

判断に必要な指針は [指針索引](references/design-knowledge-index.json)（DD で始まる ID の一覧）から必要な分だけ読みます。著名作家の人格や作品の模写は生成しません。案数などの汎用の既定は少数案（[design-contract](references/design-contract.json) の initDefaults）。選択した preset の値・案件知見は preset.json の knowledgeFiles を通して使い、一般案件へ文言・書体・座標を強制しません。各案の構図差と保持点を説明し、色だけを変える方式にしません。

[素材一覧](assets/index.html)から今回の写真・ロゴ・参照を選び、公開範囲と必須 crop（切り抜き範囲）を確認します。原本を残して加工物を分け、未公開素材を外部へ送りません。コマンドはすべて `python3 scripts/build-flyer.py <command>` で、一覧と案件ファイルは [runtime](references/runtime.md)。

## 完成と検証

個別 PDF・PNG、一覧 HTML、全案 PDF・白案がある場合の白案 PDF、編集元と、事実・素材・生成・分析・評価・検査の記録を出します。機械検査と、新しい PDF 由来の画像の独立実見で合否を決め、改善 cycle の予算内で届かなければ INCOMPLETE（未完）のまま返します。機械 PASS・点数・専門役名で美観を自動保証せず、実機印刷・集客効果・別ホストでの実行の未実施は区別します。

```bash
npm test
python3 scripts/build-local-package.py --check
claude plugin validate .
```

## スキル自体への改善要望

このrepository内では共通の `/flyer-studio:run-skill-feedback` から改善要望を伝えられます。harness-creator が所有する共有部品の実体コピーを `skills/run-skill-feedback/` に置きます（install 先には自分の plugin フォルダしか展開されないため、共有部品への symlink では切れます）。正本とのbyte一致はrepositoryの検査（vendored SSOT の lint）が保ちます。利用者が要望収集を依頼した場合だけ起動し、認証や送信は共有部品の契約に従います。単独ローカルキットには含めません。外す skill は `scripts/build-local-package.py` の `KIT_EXCLUDED_SKILLS` で名前を宣言し、キットの `references/package-contract.json` の entry_points.skills と runtime_dependencies からも外します。その skill だけが要る依存もキットの宣言から外す（`KIT_EXCLUDED_DEPENDENCIES` は `.claude-plugin/plugin.json` の dependencies と `references/package-contract.json` の depends_on から、harness-creator への外部依存は `plugin-composition.yaml` と depends_on から）ので、キットはチラシ制作の6skillを自己完結で配布します。
