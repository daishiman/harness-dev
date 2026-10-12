# info-collector の収集手順

`agents/info-collector.md` の思考プロセスで使う、収集の Step ごとの詳しい手順の正本。info-collector は収集を始める前にこのファイルを Read し、各 Step をこの手順どおりに行う。並べ方は `agents/info-collector.md` の「実行原則」、検索の受け渡しと意味選択の契約（Step 3-B・3-C）とサマリーの生成（Step 4）は `agents/info-collector.md` の本文にある。

## Step 1: 過去目標ファイルの収集

**並列実行**: Step 2/3.5/3.7/3.8/3.9 と同時に実行可能（Step 3 は本 Step の課題を待つ）

1. `Glob: $UBM_VAULT_ROOT/05_Project/UBM/目標設定/UBM - *.md` で一覧取得
2. goal_typeに応じてフィルタリング（`agents/info-collector.md` の「ビジネスルール（取得スコープ）」参照）
3. 該当ファイルをReadで読み込み（複数ファイルは並列Read）、目標値・実績値・行動変化を抽出
4. **プロジェクト別タスクの抽出**: 前回月報（`monthly` 時）の【プロジェクト別タスク】セクションがある場合、各プロジェクト名・目的・タスク（[ ]/[x]）・サブプロジェクトを抽出。完了/未完了の比率と、未完了のまま繰り越されているタスクをリストアップする。未完了[ ]のタスクは当月月報への繰越供給候補として明示する
5. **習慣目標の抽出（`weekly` のみ）**: 前回週報に【習慣目標】セクションがある場合、3原則（30分切替・大物分散・粒度の粗さ）の各チェック項目の達成状況を抽出
6. **継承文脈フィールドの抽出**: `weekly` は『現在の月報』、`monthly`/`quarterly`/`yearly` は『現在の期報』から今期文脈10種（period_sales_target/period_sales_cumulative/business_partner_count/grid_partner_count/grid_partner_goal/last_academy_date/next_academy_date/next_sparring_date/sparring_target_state/sparring_deliverables）を抽出する。grid_partner_goalは半角数字または未設定 `null`。取得不可の項目は[要ヒアリング]を付与する。`yearly` で現在の期報が無ければ10種すべてに[要ヒアリング]を付与する（前回の1年目標は抽出元にしない。1年層での10種の必須度は `skills/run-ubm-goal-setting/references/data-contract.md` §3.1.3 の「1年層（yearly）の扱い」の段落で未決のままで、1年目標がこの10種を持つ保証が無く、初回は前回の1年目標そのものが無い）

**完了条件**: 前回の目標と実績の数値、プロジェクト別タスクの継続状況、習慣目標の達成状況（`weekly` のみ）、継承文脈フィールドが抽出済みまたは[要ヒアリング]付与済みである

## Step 2: 合宿情報の収集（最重要）

**並列実行**: Step 1/3.5/3.7/3.8/3.9 と同時に実行可能（Step 3 は本 Step の課題を待つ）

1. `Bash: ls $UBM_VAULT_ROOT/05_Project/UBM/合宿/ | sort | tail -1` で最新ディレクトリ取得
2. 最新ディレクトリ内の全.mdファイルを並列Read（特に相談内容.md、事業相談の全体議事録.md優先）
3. 抽出: 事業方針、具体的アクション、克服すべき課題、数値目標
4. 鮮度チェック: 合宿日が3ヶ月以上前→[鮮度注意]マーク付与
5. `quarterly` の場合: 対象期間（3ヶ月）内の合宿を全て読み込み、方針の変化を時系列記録
6. `yearly` の場合: 対象期間（暦の1年）内の合宿を全て読み込み、方針の変化を時系列記録（1年層は方向を決める層なので、合宿の方針変化を落とさない）

**完了条件**: 合宿アドバイスが4観点で整理されている、またはエラーマーク付与済み

## Step 3: ナレッジの参照（本文に置かない節）

Step 3 の依存・router の読み込み・Step 3-B（決定論の重み付き検索）・Step 3-C（候補の意味選択）・Step 3-E の起動条件・Step 3 の完了条件は `agents/info-collector.md` の本文にある。ここには、その前後で使う節を置く。

### Step 3-A: ユーザー入力の多層抽象化（検索前に必ず実行）

Step 1・2 から取得したユーザーの具体的な訴え・課題を、3つの抽象レイヤーに変換する。

**Layer 0（具体）**: ユーザーの言葉そのまま
例: 「外交件数が月5件しかできていない」「売上目標に届かない」

**Layer 1（課題キー）**: `router.json` の `abstraction_layers.concept_mapping` を使って by_issue キーに変換
```
ユーザー言葉の主要キーワード → concept_mapping → by_issue キー
例: "外交", "件数" → ["外交不足", "関係構築"]
    "売上", "未達" → ["売上追求型", "マインドセット"]
```

**Layer 2（メタテーマ）**: `abstraction_layers.meta_themes` を参照し、Layer 1 のキーが属するメタテーマを特定
```
by_issue "外交不足" → メタテーマ "行動量・先行指標の問題", "関係構築・接点の問題"
by_issue "売上追求型" → メタテーマ "売上・成果の誤認", "行動量・先行指標の問題"
```

**出力**: `{layer0_keywords: [...], layer1_issues: [...], layer2_themes: [...]}`

### Step 3-D: 概念抽出と翻訳（従来の上位概念抽出）

順位付き候補から意味的に選んだエントリについて以下を実行:

1. **上位概念の抽出**（ここが最重要）:
   - 各エントリの `intent` と `background` から**普遍的な原則**を読み取る
   - 「タグが合わないから使えない」ではなく「この原則の本質はXXで、ユーザー状況Yでは△△になる」と翻訳する
   - 翻訳例: entry.intent "行動量の不足が本質原因と理解させ、量を規定させること"
            → 概念: "成果に直結する先行指標を特定し量を固定する"
            → ユーザー翻訳: "（業種）の（具体的な指標）を（数値）/週と決める"
2. 候補のうち `consultation` カテゴリのものから類似構造（状況→課題→アドバイス）を選び、概念を抽出
3. 候補のうち `principles` カテゴリのものから引用候補をリストアップ（`quote`+`expression` フィールド活用）

### Step 3-E の詳細（グラフ索引の参照）

起動条件は `agents/info-collector.md` の「Step 3-E: グラフ索引の参照（候補の追加ID探索・オプション）」にある（正本は `references/graph-consult-fallback-contract.md`）。

決定論の重み付き検索に加え、C06/C05 が生成した検証済みグラフが存在する場合は、`consult-harness-artifact-graph.py`（C07）を読み取り専用で引き、Layer 1 の課題キーに関連するナレッジと、それを支える実成果物（`planned`/`built`/`verified`/`stale`）を **出典の参照付き**で取得する。ルーターのタグ一致では拾えない関係辺・依存構造を補完する経路。

- **`query-type` の使い分け**:
  - `local`: Layer 1 の課題キー1つに直接マッチするナレッジ/成果物と隣接辺を `depth` の上限まで
  - `global`: 課題テーマがどのカテゴリ／成果物の状態に広がるかの俯瞰（カテゴリ／クラスタ単位）
  - `relationship`: 2概念間（例: `売上 -> 外交`）の関係のパス探索。`topic` を区切り（`->` / `::` / `|`）で割る
- **呼び出し例**（Bash。パスは `$PLUGIN_ROOT` 基点の絶対パスを使い `..` を含めない＝パストラバーサル（上位ディレクトリへの抜け出し）のガードに適合。`--harness-artifact-graph` は存在時のみ付ける）:

```bash
python3 "$PLUGIN_ROOT/scripts/consult-harness-artifact-graph.py" \
  --topic "外交不足" \
  --knowledge-graph "$PLUGIN_ROOT/knowledge/knowledge-graph.json" \
  --harness-artifact-graph "$PLUGIN_ROOT/knowledge/harness-artifact-graph.json" \
  --query-type local --depth 2
# harness-artifact-graph.json が無い場合は --harness-artifact-graph 行を省く (ナレッジ単独の参照)
```

- **出力の扱い**: 標準出力の JSON は `zero_hit` フラグ・`hits.knowledge`（`nodes`/`edges`/`associations`）・`hits.harness`（`nodes`/`edges`）・`sources.knowledge_graph.sha256`・`sources.harness_artifact_graph`（併用時は `sha256`、省略時は `status:"absent"`）を含む。ヒットは **ID/パス/ハッシュのポインタ**でありナレッジ本文ではないため、関連IDを特定したら親へIDの追加検索を依頼し、その候補の `source_ref` を別途 Read して概念抽出（Step 3-D）へ渡す。辺は逐語の根拠を返さず `evidence_count` のみ（秘密情報/PII の本文は返さない）。
- **終了コード**: `0`=正常（ヒット0件・harness のグラフ省略を含む）／`2`=使い方の誤り・入力不正・壊れた索引。終了コード 2（グラフ破損など）は本ステップをスキップ扱いにし、重み付き検索の候補で続行する（正本の「破損 → WARN して飛ばす」に対応）。

### 補助資料の参照（有効なrouterの検索結果がzero_hitの場合のみ）

候補のJSONに未登録の資料は知識IDの引用・usageに数えず、補助資料の出所を明示する。router不在・破損ではこの経路へ逃げず停止する。

1. `$UBM_VAULT_ROOT/05_Project/UBM/動画教材/` からTier 1ファイルを先頭200行読み込み
   - UBM - vol.1_商品づくりロードマップ.md
   - UBM - vol.2_商品販売ロードマップ.md
   - UBM - 選択と集中.md
   - vol.3は1→10以降のフェーズのみ
2. `$UBM_VAULT_ROOT/05_Project/UBM/月報フィードバック/` を読み込み
3. `$UBM_VAULT_ROOT/05_Project/UBM/YouTube/` から課題に応じたファイルを最大2本選択:
   - 外交不足/迷い → 「人が集まってくる思考」/「迷ったら川上を見ろ」【優先度1】
   - 前回と同パターン → 「ビジネスモデル根本的見直し」/「目標がブレる起業家」【優先度2】
   - 行動量はあるが成果なし → 「有望な若手がパンク」【優先度3】
   - 10→100戦略 → 「法律の間を潜り抜ける勝ち筋」【優先度4】
   - Grepで関連キーワード検索→前後30行抽出（全読みしない）

## Step 3.7: ジャーナル収集（週報のみ）

**並列実行**: Step 1/2/3/3.5 と同時に実行可能
**スキップ条件**: `goal_type` が `monthly` / `quarterly` / `yearly` の場合はスキップ（週報に圧縮済みのため不要）

1. 対象期間（start_date〜end_date）から日付リストを生成（例: 2026-03-30〜2026-04-05 → 7日分）
2. `Glob: $UBM_VAULT_ROOT/02_Configs/Daily/YYYY-MM-DD.md` で各日付のファイル存在を確認
3. 存在するファイルを並列Readで読み込み
4. 各ジャーナルから以下を抽出:
   - **行動のジャーナル**: 現状確認（何をしたか）、効果性評価（成果があったか）、改善方法
   - **時間のジャーナル**: 時間配分の現状、効果性評価、改善方法
   - **お金のジャーナル**: 売上・見込み活動の現状、効果性評価、改善方法
5. Obsidian の埋め込み構文 `![[filename#section]]` が含まれる場合、参照先の実ファイル内容として認識
6. セクションが全て空（テンプレートのみ）のジャーナルはスキップ

**完了条件**: 対象期間の行動実績・時間配分・課題・気づきがリストアップされている

## Step 3.8: 直近の相談からの引き継ぎの参照（相談→目標設定のループ辺・無ければ飛ばす）

**並列実行**: Step 1/2/3/3.5/3.7/3.9 と同時に実行可能
**目的**: `run-ubm-consult`（相談スキル）の帰結（次の一歩）を目標設定対話へ機械的に引き継ぎ、「相談で考え方を整理→目標設定で行動に落とす」ループを閉じる。

1. 正本パス規約は `$PLUGIN_ROOT/skills/run-ubm-consult/references/session-record-format.md`。読む入口は **`project_root/eval-log/ubm-goal-setting/run-ubm-consult/latest.json`**（セッション ID 別の記録へのポインタ）。
2. `latest.json` 不在、保存同意なし、期限切れ、`outcome != consult_completed` は正常としてスキップする。ポインタの `path` が `sessions/<session_id>/handoff.json` 配下を外れる場合は拒否する。
3. 有効な記録から以下だけを抽出する。複数件が必要なら `index.jsonl` から同意済み・期限内の最新 N=3 を明示選択する:
   - `issue_statement`
   - `user_solution.text`（出所情報が `role=user` のターンであると検証済み）
   - `closure.type=action` の `closure.next_step`（`reflection` は行動候補にしない）
4. これらを「直近の相談からの引き継ぎ」として構造化サマリーに載せる。**あくまで文脈の引き継ぎであり、目標そのものではない**（目標設定は Phase 3 で対話生成する）。相談の次の一歩が今回の目標種別（`weekly`/`monthly`/`quarterly`/`yearly`）に合致する場合は、行動目標の候補として Phase 3 へ渡す。
5. 読み取り専用。本 Step は `eval-log` へ書き込まない（`ubm-write-path-guard` の対象外のパスだが、そもそも参照専用）。

**完了条件**: 同意済み・期限内の `consult_completed` の記録があれば `issue_statement` / `user_solution` / 任意の `next_step` が引き継がれている、または[相談履歴なし/同意なし/対象外]でスキップ済みである

## Step 3.9: 直近の挑戦宣言の参照（読み取り専用）

Step 1/2/3/3.5/3.7/3.8 と並列実行可能。`$UBM_VAULT_ROOT/05_Project/UBM/挑戦宣言/UBM - 挑戦宣言 - *.md` を Glob し、ファイル名の宣言日が対象期間の終了日以前のものから直近1件を Read する。不在は [挑戦宣言なし] でスキップ。形式と field の正本は `$PLUGIN_ROOT/skills/run-ubm-challenge/references/challenge-format.md`。

目的・確定した目標・行うこと・報告周期を、source_path/declared_on と元の文を保って構造化サマリーの「挑戦宣言からの文脈」へ載せる。保留/未確定の欄は候補へ昇格させない。Phase3 で利用者が今回の目標として確認するまでは文脈にとどめる。ユーザーの記録を北原ナレッジの引用や更新ソースとして扱わない。ファイルを更新しない。

この1件は1年層の到達点の出所にもなる（`agents/info-collector.md` の「ビジネスルール（取得スコープ）」にある、1年層の到達点を種別を問わず集める規則）。挑戦宣言は `## 【今年の最重要数字】` の注記を持たないので、`●目標ーその目的に近づくための数値的な目標` の箇条書きのうち、月間売上か継続コンサル人数と読み取れる数値目標だけを、元の文と source_path を付けて「1年層の到達点」へ載せる。読み取れない項目は推測で埋めない。

**完了条件**: 出所付きの文脈か [挑戦宣言なし] を返す。

## Step 3.5: UBMルート直下ファイルの確認

**並列実行**: Step 1/2/3/3.7 と同時に実行可能

1. `Glob: $UBM_VAULT_ROOT/05_Project/UBM/minutes - *.md` と `$UBM_VAULT_ROOT/05_Project/UBM/UBM - *.md`（2つのGlobを並列実行）
2. 最新1-2件を並列Readし、目標設定に関連する情報があれば抽出

**完了条件**: 直近のセミナー・イベント情報を確認済み
