# phase2-02 thinking coverage

## 4 conditions

| 条件 | 判定 | 根拠 |
|---|---|---|
| 矛盾なし | PASS | `verdict_tentative` / `files[].rel` / 第17条 regex に統一 |
| 漏れなし | PASS | migrate-to-plugin 59件を files[].rel と exactly 1 回一致させる |
| 整合性あり | PASS | partition-plan v1 / target map / confirmed inventory / dependency graph を同一 schema で生成 |
| 依存関係整合 | PASS | runtime inter-partition refs と migration order reasons を分離 |

## 30 paradigms

- [x] 批判的思考: 旧 verdict 前提を疑い、実 JSON の verdict_tentative を入力契約に固定した。
- [x] 演繹思考: 06章第17条と phase2 README から、kebab-case・既存 plugin 非衝突・全 migrate rel 網羅を必須条件として導出した。
- [x] 帰納的思考: migrate 59件が config/scripts のみである事実から、skill prefix 分類ではなく files[].rel 主キーが妥当と判断した。
- [x] アブダクション: 後続 03/06 の破綻原因を、target_plugin 未確定と payload schema 不足と推定し派生成果物を追加した。
- [x] 垂直思考: 01 -> 02 -> 03/06 の入力契約を深掘りし、confirmed-inventory と dependency graph まで落とした。
- [x] 要素分解: 資産を rel / kind / target_plugin / partition / depends_on / exceptions に分解した。
- [x] MECE: 全 migrate rel を files[].rel と exactly 1 回一致させ、重複・欠落を禁止した。
- [x] 2軸思考: 資産種別(config/script) x 責務(config/adapter/hook/lint/secret/migration/automation)で分類した。
- [x] プロセス思考: Step 7.1-7.10 と DoD-1-12 の順序を、生成 -> 検証 -> README -> 承認に整列した。
- [x] メタ思考: 「plugin 分割」自体の入力が旧スキーマに引きずられていないかを検査した。
- [x] 抽象化思考: skill 固有ではなく plugin payload file という抽象で config/scripts を扱えるようにした。
- [x] ダブル・ループ思考: prefix 分割の前提を捨て、実 inventory に合わせた domain/cohesion 型へ判断基準を更新した。
- [x] ブレインストーミング: domain/cohesion、lifecycle/prefix、single-runtime-plugin の3案を列挙した。
- [x] 水平思考: path prefix ではなく責務・rollback 粒度・将来再利用性からも分類を見た。
- [x] 逆説思考: 境界外参照ゼロを最優先するなら単一 plugin 案もあり得るため、却下理由を残した。
- [x] 類推思考: monorepo package 分割と同様、cohesion と coupling のバランスで境界を決めた。
- [x] if思考: 03/06 実行時に target_plugin が null のままだった場合を想定し、target map を追加した。
- [x] 素人思考: 実行者が迷わないよう、README 更新・承認 JSON 必須 field・中学生説明を明確化した。
- [x] システム思考: 02 を Phase 2 下流タスク全体の入力契約として扱った。
- [x] 因果関係分析: verdict フィールド不一致が空集合 plan と DoD 偽陽性につながる因果を除去した。
- [x] 因果ループ: 境界漏れ -> 06 失敗 -> 02 再策定のループを集合一致検証で遮断した。
- [x] トレードオン思考: cohesion、coupling、migration cost、rollback blast radius、user value、future reuse を同時評価した。
- [x] プラスサム思考: 人間承認を残しつつ、判断材料を matrix と JSON にして下流自動化にも価値を出した。
- [x] 価値提案思考: 価値を「安全に量産移行できる決定済み入力契約」と定義した。
- [x] 戦略的思考: 03/04/05 並列着手の前提として、境界・依存・判断根拠を先に固定した。
- [x] why思考: なぜ破綻するかを追い、根本原因を資産分類と plugin payload 設計の混同に置いた。
- [x] 改善思考: DoD を 7 件から 12 件へ拡張し、偽陽性を減らした。
- [x] 仮説思考: domain/cohesion 型なら現 inventory に適合し、後続 migration cost も許容可能という仮説を採用した。
- [x] 論点思考: 論点を JSON契約、資産網羅、命名、依存、判断根拠、承認証跡に絞った。
- [x] KJ法: SubAgent 指摘を JSON契約・資産網羅・参照検証・移行順序・判断基準・命名に分類した。
