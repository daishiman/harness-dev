# PKG-007と共通フィードバック配布の改善結果

**対象範囲の実装・検証を完了。4条件はすべてPASS。** 別コンテキストで思考リセットを経由し、9・9・12種を3担当へ分けて並列分析した。30種全件使用、省略0。利用者の「簡単に実行・短時間で完了・トークンを抑える」条件付き承認を受け、既存分析を再利用して対象差分だけを独立再評価した。

## 通常実行を重くしない設計

- 開発・配布時にPKG-007とbuild用lintを実行し、通常スキル起動へ追加のLLM評価・全プラグイン走査・検査ループを追加しない。
- 共通フィードバックの実行ファイル・schema・必要な参照資料を各配布物へ同梱。通常はhostが示す登録済み候補から対象だけを読み、全スキルの一括読込を要求しない。
- 設定ローダーは局所的な祖先manifest探索で配布元を解決する。Notion設定と既存の承認用プラグインは明示依存として扱う。
- 同一bytesの92コピーは4正本のレビュー証拠をハッシュ一致で再利用した。コピーごとのLLM再読は行わず、正本・評価記録・コピーのSHAを記録した。証拠が無かったtenant_runtimeだけ一度レビューした。

## 修正したこと

- PKG-007の対象を「全SKILL.mdの明示script_refs＋既存root直下scripts」に確定。本文・他の*_refsはこの検査の対象外と明示し、細則はcheck_pkg_007を正本にした。
- YAMLの宣言型、第一存在候補、解決後の配布内包含、通常ファイル、shebang、modeの実行ビットを機械判定。無効な第一候補を後ろの候補で救わず、同一実体は1findingへ集約する。
- helper判定をASTへ移し、PKG-006のroot token、不正hooks構造、読込失敗、symlink、CLI名を修復。単発評価・構造化fork入力・findingsの用語も統一。
- 共通フィードバックは正本＋22配布コピー（計23）へ同期。repo用lintはmanifestのbuild_validationへ明示移管し、IN1/IN2・実行属性・検証先の対応を開発時のR9で保証。
- 必要な実行属性を通常のchmodで修復。明示refreshは開発・配布時だけ使用し、コピー先symlinkを全書込前に拒否する。
- 承認wrapperは既存canonical配線を維持し、通常の承認・秘密解決の境界を変更しない。

## 検証結果

| 検証 | 結果 |
|---|---|
| 対象10テストファイル | **523 PASS、7.76秒** |
| PKG-007 | **23プラグイン・違反0件、約0.68秒** |
| 22配布コピーの明示更新 | 約0.13秒 |
| package gate | 23プラグイン、blocking 0（既存advisory 35） |
| content-review | 95スキル検証成功。APEと共通feedbackは独立genuine再評価 |
| 共通資産 | 330組byte一致 |
| feedback lint | R1〜R9、strict PASS |
| artifact-delivery | 23プラグインPASS |
| LLM coverage parity | 最新、83スキル・平均100% |
| harness coverage ratchet | PASS。閾値・floor・分母の変更なし |
| 30思考法と成果スキーマ | 30件一意・省略0、機械検証 |

修正前201参照の違反は、対象機械検査で0件となった。最初の失敗・途中の不合格・旧verdictは履歴に保存し、過去のSHAだけを付け替えてPASSにはしていない。実装者と承認者を分け、コードの外向きsymlink書込とwrapper配線の統合問題も修正・再確認した。

## 4条件

| 条件 | 判定 | 根拠 |
|---|---|---|
| C1 矛盾なし | PASS | catalog・36章・機械判定・R1のscopeと責務が一致。独立レビュー |
| C2 漏れなし | PASS | 30種全使用、宣言境界テスト、23配布物の検査、523テスト |
| C3 整合性あり | PASS | YAML・命名pattern・mode判定、330資産一致、両skillの正規verdict |
| C4 依存関係整合 | PASS | 配布内実体、隔離runtime、承認依存解決、同期前後の順序とsymlink拒否 |

## 実施していないこと・適用範囲

- Notionへの実投入・Keychainの実値取得は行っていない。隔離テストでは外部通信・外部processを遮断し、dry-runと失敗時停止を確認した。
- 全体の80%カバレッジ仕様には既存の未達軸が残る。今回の回帰gateはfloorを変更せず成功した。
- 公開、インストール、バージョン採番、commit/pushは行っていない。既存差分を保持している。

## 証跡

- [機械検査と所要時間](validation/final-pkg007-and-cost.json)
- [対象テスト](validation/final-target-tests.log)
- [最終ゲート](validation/final-gates.json)
- [APE独立評価](independent-review-summary.md)
- [コピーの評価証拠再利用](coverage-proof-reuse.json)
- [最終判定](verdict.json)

## 初回30思考法の観測（修正前の履歴）

| 思考法 | 修正前の観測 |
|---|---|
| 批判的思考 | catalogは参照元を未列挙。SKILLはscript_refsを具体化するが対象集合の合意が必要。 |
| 演繹思考 | root直下走査ではsymlink実体のplugin内包含を検査せず外向き参照を通す。 |
| 帰納的思考 | 既存142テストは成功。参照宣言・優先順位・broken symlinkの回帰テストは無い。 |
| アブダクション | import専用とshebangは併存する。用途だけで明示script_refsを免除しない。 |
| 垂直思考 | 第一候補が不正な場合のfallbackを固定し、後の有効候補で隠さない。 |
| 要素分解 | catalogの+xビットとos.access(X_OK)は判定対象が異なる。 |
| MECE | 明示参照とroot走査は和集合。同一実体の重複を集約する必要。 |
| 2軸思考 | 明示/自由記述と配布内/外の2軸で責務を分離する。009の許可は007の免除ではない。 |
| プロセス思考 | 不正YAMLや型の崩れを参照なし扱いしない。入力読込不能と契約違反を区別する。 |
| メタ思考 | 現行は機械と評価者の分担が明文化され、root走査だけが直ちに契約矛盾とはいえない。 |
| 抽象化思考 | 宣言抽出・候補解決・配布内包含・実行属性の4責務へ分解する。 |
| ダブル・ループ思考 | SKILLの単発採点とR1の反復指示が相反し、反復上限の参照先も無い。 |
| ブレインストーミング | 代替6案:現行維持、明示refs機械化、型付きrefs、隔離配布検査、全文候補lint、期限付き例外。明示refsを推奨。 |
| 水平思考 | 存在ファイルの再帰走査だけでは欠けた宣言参照を検出できない。 |
| 逆説思考 | 未参照helper除外と参照helperの実行属性必須は意図的な非対称。 |
| 類推思考 | 依存宣言は配布物の充足と別。参照許可だけではimport依存を解決できない。 |
| if思考 | 外部・skill配下・注釈・helper・symlink等の境界で受入検証を行う。 |
| 素人思考 | fork入力がtarget_pluginのみという契約とpkg_ids/optionsを受け付ける契約が相反。 |
| システム思考 | submit→notion_config→tenant_runtimeとlint→schema/upsert/全pluginsは別依存系。現物69参照は配布内で未解決。 |
| 因果関係分析 | submitをそのままコピーするとROOT/plugins/harness-creator/scriptsを二重に探す。配置とimportを一緒に修復する。 |
| 因果ループ | 静的属性だけを修復するとimport依存が残る。現物129参照の実行権と3参照のshebang欠落も必要。 |
| トレードオン思考 | 正本と配布自己完結性は生成コピーと一致検査で両立できる。 |
| プラスサム思考 | repo全体lintは開発側に残す。利用者のruntimeへ不要なrepo依存を持ち込まない。 |
| 価値提案思考 | 利用者の価値は投入可能性。対話資料・preview・失敗原因の説明を優先する。 |
| 戦略的思考 | repo-bundled限定と単独配布の提供範囲を明確に分ける。 |
| why思考 | 動かない→import先不存在→repo配置前提→script_refsだけでコピー範囲決定→参照実在と依存閉包を同一視。 |
| 改善思考 | 注釈の無い明示pathは機械へ移し、同じ規則の文章改訂を繰り返さない。 |
| 仮説思考 | 3本bytecopy仮説は隔離実行でnotion_configのModuleNotFoundErrorとなる。 |
| 論点思考 | PKG適合・repo-only可否・standalone実行可否は別論点。009の許可を007に転用しない。 |
| KJ法 | 参照検査、import/root、対話資料、guard/設定、開発lintの5群に分類し、提供元と検証責任を割り当てる。 |

Beads: harness-zb7q。
