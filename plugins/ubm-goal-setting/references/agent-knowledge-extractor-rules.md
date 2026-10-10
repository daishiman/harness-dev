# knowledge-extractor の決定論的実行ルール（Rule A〜F）

`agents/knowledge-extractor.md` の Layer 2.5「決定論的実行ルール」の本文の正本。knowledge-extractor は格納（Step 3）と `mode: "update"` / `mode: "full"` の処理を始める前にこのファイルを Read し、判断を全てこのルールに従わせる。どのルールが必須でどれが推奨かは、エージェント側の「ルール重要度分類」の表にある。ここで「Step N」と書くのは `${PLUGIN_ROOT}/references/agent-knowledge-extractor-steps.md` の Step N を指す。`knowledge/` と書くのは、親が渡した一時 `knowledge_dir` のコピーを指す。

## Rule A: 格納先ファイル決定アルゴリズム

```
入力: エントリの tags (例: ["外交", "接点", "フォロー", "メッセージ"])
      カテゴリ名 (例: "action-guides")

Step A-1: router.json の routing_rules[カテゴリ名] を Read
Step A-2: 各サブトピックファイルに対してスコアを計算
  score[ファイル名] = count(entry.tags ∩ routing_rule[ファイル名].tags)
  例:
    action-guides-relationship.json → tags: ["外交","接点","フォロー","メッセージ",...] → score: 4
    action-guides-content.json      → tags: ["発信","SNS","コンテンツ",...]           → score: 0
Step A-3: 最大スコアのファイルを格納先に決定
  タイ（同スコア）の場合: subcategory_counts が大きいファイルを優先
  全スコアが 0 の場合: default: true のファイルを使用
Step A-4: 格納先ファイルが存在しない場合 → schema.json を参照して新規作成
```

## Rule B: サブトピック名決定アルゴリズム

新ファイルが必要な時、以下のタグ→英語名マッピングテーブルに従って命名する。

**マッピングテーブル（優先順位順に照合）**:

| タグクラスター（日本語） | サブトピック名 | 対象カテゴリ |
|------------------------|-----------|------------|
| 外交, 接点, フォロー, メッセージ, アポ, 個別連絡, 訪問 | `relationship` | `action-guides`, `principles`, `case-studies` |
| 発信, SNS, コンテンツ, 投稿, 広告, YouTube, ブログ, 情報発信 | `content` | `action-guides` |
| 組織, 人材, 採用, 管理職, チーム, 階層, 定着, 育成, ルール, 報連相 | `organization` | `consultation`, `case-studies`, `phase-advice` |
| 売上, 集客, 商品, 価格, マーケティング, 成約, 追客 | `sales` | `consultation` |
| ビジネスモデル, 事業転換, 方針, 構造, フェーズ転換, 差別化 | `business-model` | `consultation` |
| 0to1, 0→1, 初顧客, 初報酬, モニター, 無料, 起業初期 | `0to1` | `phase-advice` |
| 1to10, 1→10, 再現性, 個人売上, 安定, 外交量 | `1to10` | `phase-advice` |
| 10to100, 10→100, 組織化, スケール, チーム構築 | `10to100` | `phase-advice` |
| 信頼, 相談, 紹介, 人, 繋がり, コミュニティ, 感謝 | `relationship` | `principles` |
| 姿勢, 在り方, 考え方, マインド, 思考, 覚悟, 本気, 自分 | `mindset` | `principles` |
| 事業, 成長, 選択, 集中, 判断, 戦略, フォーカス | `business-growth` | `principles` |
| 成功, 達成, 関係構築成功, 売上増加, 受注 | `success` | `case-studies` |
| 失敗, 転落, 挫折, 立て直し, ゼロから, 減収 | `failure` | `case-studies` |
| 自信, 不安, 完璧主義, 迷い, 怖い, 自己評価, 焦り, 比較 | `self-doubt` | `mindset` |
| 責任, 覚悟, 主語, 向き合い, 思考転換, 経営 | `accountability` | `mindset` |

**照合手順**:
1. エントリの `tags` と各行のタグクラスターの共通数を計算
2. 最も共通数が多い行のサブトピック名を採用（かつ「対象カテゴリ」が一致）
3. どれにもマッチしない場合: エントリの `tags[0]`〜`[2]` を英語に直訳して `-` で繋ぐ

**最終ファイル名**: `{category}-{subtopic}.json`。既存ファイルを分割するときは `router.json` の `growth_rules.new_file_naming`（`{category}-{existing_topic}-{new_subtopic}.json`）に従う

## Rule C: ID採番アルゴリズム

```
入力: カテゴリ名 (例: "principles" → プレフィックス "PR")

Step C-1: router.json の categories[カテゴリ名].files を取得
Step C-2: 全ファイルを Read し、全エントリの id を収集
  例: ["PR-001", "PR-003", "PR-007", "PR-012"]
Step C-3: 最大番号 + 1 を新しいIDとして採番
  例: max(1, 3, 7, 12) + 1 = 13 → "PR-013"
Step C-4: 3桁ゼロ埋めで統一 (PR-001 / PR-013 / PR-099 / PR-100)
```

**カテゴリ別プレフィックス対応表**:
| カテゴリ | プレフィックス |
|---------|-------------|
| `principles` | PR |
| `consultation` | CP |
| `phase-advice` | PA |
| `action-guides` | AG |
| `mindset` | MS |
| `case-studies` | CS |

## Rule D: `router.json` 更新順序

エントリ書き込みのたびに**必ず以下の順序で全フィールドを更新**する:

```
新サブトピックファイル作成時のみ（エントリ追加より前に実行）:
  0a. categories[category].files に新ファイル名を追加
  0b. categories[category].subcategory_counts[新ファイル名] = 0
  0c. routing_rules[category][新ファイル名] = {topic, tags, default} を追加

エントリ追加のたびに毎回:
  1. categories[category].subcategory_counts[格納先ファイル名] += 1  ← 暫定カウント
  2. categories[category].entry_count = sum(subcategory_counts の全値)
  3. total_entries = sum(全カテゴリの entry_count)
  4. last_sync = 処理日付 (YYYY-MM-DD)

  ※ Step 4 で全エントリを再集計して「確定値」に上書きする。
     上記の += 1 は暫定値であり、最終値は Step 4 の再集計が正とする。
```

## Rule E: 新サブトピックファイル作成判断基準

```
条件 1: あるファイルのエントリ数 > 25 (growth_rules.entry_threshold)
        ※ 根拠: 25件を超えると目標設定エージェントが検索時に「関連性低いエントリ」を
                多く参照するコストが上がる経験則。運用後に見直し可能。
条件 2: かつ、そのファイル内エントリの tags を分析した結果、
        70%以上が「現在のsubtopic名と異なる共通サブテーマ」を持つ
        ※ 根拠: 過半数（50%超）では分割が早すぎる。80%以上では遅すぎる。
                70%は「明確なサブテーマが存在する」と判断できる中間値。運用後に見直し可能。

→ 両方満たす場合のみ新ファイルを作成

例:
  consultation-organization.json (26エントリ) を分析:
    - 採用・育成タグ: 19件 (73%) → "hiring" サブテーマが明確
    - 組織構造タグ:   7件 (27%)
  → consultation-hiring.json を新設
     routing_rules に Rule B に従い tags を設定
     旧ファイルから該当エントリを移行
```

## Rule F: `mode` 別処理フロー

`detect-knowledge-updates.py` の出力ステータス（`NEW`/`MODIFIED`）から `mode` を自動決定する。

| 入力ステータス | `mode` | 意味 |
|-------------|------|------|
| `NEW` | `new` | `registry.json` に存在しない新規ファイル |
| `MODIFIED` | `update` | ハッシュが変化した更新ファイル |
| `--all` オプション | `full` | 全ファイル強制再構築（通常は使用禁止） |

### `mode: "new"` — 新規ファイル処理

ファイル全体を読み込んでナレッジを抽出し、全エントリを JSON に追加する。
重複チェック（同 `content` が既存なら `source` 追記のみ）を適用。

### `mode: "update"` — 更新ファイルの上書き処理

**差分のみ処理は行わない。既存エントリを全削除→全再処理する（上書き方式）。**
理由: 変更・削除・修正に対して古いエントリが残ると矛盾が生じるため。

```
Step U-1: registry.json から対象ファイルの処理済み情報を取得
  → file_path, extracted_entry_ids, entries_extracted を確認
  → extracted_entry_ids の有無で Step U-2 の方式を決定

Step U-2: 既存エントリの全削除（分散配置に完全対応した3方式）

  方式の判定（MECE: 3ケースで漏れなく重複なく網羅）:
  ┌─────────────────────────────────────────────────┐
  │ extracted_entry_ids が null        → Case B   │
  │ extracted_entry_ids が [] (空配列) → Case C   │
  │ extracted_entry_ids が非空配列     → Case A   │
  └─────────────────────────────────────────────────┘

  ■ Case A: extracted_entry_ids が非空配列の場合（追跡済みファイル・推奨パス）
    A-1: registry.json から extracted_entry_ids リストを取得
         例: ["PR-013", "CP-007", "AG-005", "MS-003"]
    A-2: router.json の categories[*].files で全 JSON ファイルリストを取得
    A-3: 各ファイルを Read し、id が extracted_entry_ids に含まれるエントリを全削除
         → 複数カテゴリ・複数ファイルに分散していても確実に削除
    A-4: 削除した各ファイルを Write で上書き保存
    A-5: router.json の subcategory_counts / entry_count を削除分だけ減算
    A-6: 完了チェック: 削除件数 == extracted_entry_ids.length
         → 不一致（ID が見つからなかった）: warnings に記録して続行

  ■ Case B: extracted_entry_ids が null の場合（旧形式のファイル・フルスキャン）
    B-1: router.json の categories[*].files で全 JSON ファイルリストを取得
    B-2: 全ファイルを順次 Read し、source.file が対象ファイルパスと一致する
         エントリを全て特定（カテゴリをまたいで網羅的にスキャン）
    B-3: 特定した全エントリを削除した上で Write で上書き保存
    B-4: router.json の subcategory_counts / entry_count を削除分だけ減算

  ■ Case C: extracted_entry_ids が [] の場合（前回の処理でエントリ0件だった）
    → 前回の処理でエントリが抽出されなかった、または全削除済みの可能性がある
    → Case B と同様に source.file フルスキャンで残存エントリを確認・削除
    → 発見・削除した場合は「不整合が修復された」として warnings に記録

  ■ 共通: 削除後の整合性確認（Case A/B/C 共通）
    → router.json の total_entries を全カテゴリの subcategory_counts から再集計
    → 再集計値 ≠ 現在値 の場合は再集計値で上書き修正

Step U-3: ファイル全体を再処理（Step 2/3 の通常フローを実行）
  → 重複チェックは不要（Step U-2 で削除済みのため）
Step U-4: ソース単位の確定手順を実行
  → ナレッジ JSON 確定 → ルーター再集計 → 冪等キー付き sync-log 追記 → registry.json の順を守る
  → file_hash を新しいハッシュで上書き
  → entries_extracted を今回の抽出件数で上書き
  → extracted_entry_ids を今回の新規エントリIDで上書き
  → deleted_entry_ids を Step U-2 で削除したIDリストで記録
  → processed_date を今日の日付で更新
```

### `mode: "full"` — 全件再構築（通常使用禁止）

```
Step F-1: 全 knowledge/*.json の entries 配列を [] にリセット（entry_count = 0）
Step F-2: router.json の全カテゴリのエントリカウントを 0 にリセット
Step F-3: registry.json の files 配列を [] にリセット
Step F-4: 全ファイルを mode: "new" として順次処理
```

使用条件: スキーマ変更・カテゴリ再設計時のみ。日常の同期には `--all` ではなくデフォルト（差分検知）を使用する。
