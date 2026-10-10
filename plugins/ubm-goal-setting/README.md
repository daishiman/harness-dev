# ubm-goal-setting — 北原さん式ゴールセッティング

UBM（北原さん式ゴールセッティング）の**目標設定・振り返り対話**と**ナレッジ差分同期**を 1 つにした Claude Code プラグインです。`ObsidianMemo` の vault で運用していた資産（スキル / サブエージェント / フック / スクリプト / ナレッジ JSON 一式）を移植したものです。`distributable:false` の個人利用向けプラグインです。ローカルのリポジトリまたは個人用カタログから導入します。

このドキュメントは「初めて使う人がインストールし、`UBM_VAULT_ROOT` を設定して最初の目標設定を回せる状態にする」までの導入ガイドです。**日々の運用（入口コマンド詳細・検証コマンド・復旧手順）は [`RUNBOOK.md`](./RUNBOOK.md) が正本**で、本 README とは役割を分担しています（README=初見導入 / RUNBOOK=運用）。

---

正式保存の承認と実行は [guarded-publication-contract.md](references/guarded-publication-contract.md) が正本です。書き手は一時下書きだけを返し、親が検証済み差分を示してユーザー確認と中央guardの受領書を取得し、executeから正式反映します。

## 第1部 — これは何をするもの？（前提知識なしで読める説明）

**たとえ話**: 部活の顧問の先生（＝北原さん）が隣にいて、「今週は何をがんばる？」「先月は何がうまくいった？」と質問しながら、目標カードを一緒に作ってくれる道具です。

1. **目標設定・振り返り対話** (`/ubm-goal-setting`)
   - 「1 週間（週報）・1 ヶ月（月報）・3 ヶ月（期報）」の目標を、AI との短い対話で作ります。
   - できあがった目標は決まった型（**公式21ブロック**）のチェックに**合格しないと保存されません**。「頑張る」「意識する」のようなあいまいな言葉は機械が弾き、「誰に・何を・いつまでに・何件」まで具体化させます。
   - 目標には「**やらないこと**」も 3 つ以上書きます。やることを増やすより、迷いを減らすほうが行動につながるからです。

2. **ナレッジ同期** (`/ubm-knowledge-sync`)
   - 北原さんの新しい教え（動画の議事録・合宿の記録・月報へのフィードバックなど）を読み取り、**6 つの引き出し**（原則 / 相談 / フェーズ別アドバイス / 行動ガイド / マインドセット / 事例）に整理して貯めます。
   - 貯めた知識は、次の目標設定の対話で自動的に引き出されます。**学ぶ→貯める→次の目標に生かす**、が一つのサイクルになります。

**なぜこの 2 つがセットか**: 目標は「作って終わり」だと忘れます。毎週の振り返り→次の目標→新しい学びの取り込み、というループを回し続けるための道具だからです。

### さらにできること（新機能をやさしく・v0.2.0）

3. **相談にのってもらう** (`/ubm-consult`)
   - 目標設定や挑戦宣言を作る相談は対応する入口へ案内します。誘導だけでは保存せず、記録を希望した場合だけ保存同意を確認します。悩みごとを話すと、答え（「こうしなさい」）をズバッと教えるのではなく、**「こういう考え方があるよ。あなたの場合はどう当てはまる？」と、考え方（思考のフレーム）を一緒に見つけてくれる**道具です。
   - 答えを丸写しするより、自分の言葉で「じゃあ自分はこうしよう」と決めたことのほうが行動に移せる、という考え方に基づきます。だから最後は、**あなた自身の言葉**に整理して締めます。締め方もあなたが選べます。行動に移したいときは「今の状況→なりたい姿→足りないもの→次の一歩」、まだ整理したいだけのときは「見えてきたこと→まだ決めないこと→再開する条件」の形です。

4. **YouTube の学びを「地図」にする** (`/ubm-youtube-ingest`)
   - 北原さんの YouTube 動画の文字起こしを読み取り、教えを 6 つの引き出し（ナレッジ同期と同じ引き出し）に貯めます。
   - さらに、貯めた教え同士の「これはあれの土台」「これはあれを支える」というつながりを線でつなぎ、**知識の地図（グラフ）**にします。ひとつの話題から、関係する話題を線をたどって引けるようになります。
   - たくさんの動画を一本ずつ手で入れるのは大変なので、（1）URL を 1 本ずつ・（2）過去分をまとめて全部・（3）新しく増えた分だけ自動で、の 3 つの入れ方を選べます。同じ動画を二重に入れない仕組み（動画 ID を目印にする）が入っているので、何度実行しても散らかりません。

### 毎日の振り返りと挑戦宣言

5. **その日の振り返りをジャーナルにする** (`/ubm-journal`)
   - 今日やったことを会話で振り返り、下書きを検証してから Obsidian のデイリーノート（`02_Configs/Daily/{YYYY-MM-DD}.md`）へ保存し、保存後も再検証します。

6. **挑戦宣言と企画をつくる** (`/ubm-challenge`)
   - 北原さんへ提出する「挑戦宣言と企画」を、会話で引き出しながらあなた自身の言葉でまとめ、vault（`05_Project/UBM/挑戦宣言/`）に保存して提出用テキストを表示します。

**これらの関係**: YouTube とナレッジ同期で学びを取り込んで地図にし、相談で考え方として引き出し、目標設定と挑戦宣言で行動に落とし、日次ジャーナルで毎日の行動を振り返る。**「学ぶ→つなぐ→引き出す→動く→振り返る」**がひとつのループになります。次回の目標設定では直近の挑戦宣言を読み取り専用の文脈として参照し、今回の目標への採用は対話で確認します。

---

## インストール（ローカル導入）

配布契約の正本は `references/package-contract.json` の `distribution.distributable:false`。公開カタログへの掲載は行わず、以下のローカル導入を使います。インストールはコピーで、更新時のキャッシュキーは plugin.json の version です。

### 方法 A — harness のリポジトリ内で使う（開発・レビュー向け・最短）

リポジトリをクローンし、リポジトリのルートで `.claude/` のシンボリックリンクを展開します（`harness-creator` と同じプロジェクト単位の方式）。

```bash
git clone https://github.com/OWNER/harness.git
cd harness
make sync   # plugins/ubm-goal-setting/ の skills/commands/agents を .claude/ へシンボリックリンクで展開
```

このリポジトリを開いた Claude Code のセッションで `/ubm-goal-setting` などがそのまま使えます。

### 方法 B — vault の作業フォルダなどリポジトリ外で使う（ローカルのマーケットプレイス追加経由）

個人用のローカルのマーケットプレイスのカタログを作り、そこからインストールします（公開カタログには載せません）。

```bash
# 1. 個人用カタログを作る (プラグインの実体はクローン済みの harness をシンボリックリンクで参照)
mkdir -p ~/ubm-marketplace/.claude-plugin ~/ubm-marketplace/plugins
ln -s /path/to/harness/plugins/ubm-goal-setting ~/ubm-marketplace/plugins/ubm-goal-setting
cat > ~/ubm-marketplace/.claude-plugin/marketplace.json <<'JSON'
{
  "name": "ubm-local",
  "owner": { "name": "personal" },
  "plugins": [
    { "name": "ubm-goal-setting", "source": "./plugins/ubm-goal-setting" }
  ]
}
JSON
```

Claude Code（CLI / デスクトップ版共通）のチャット欄で:

```
/plugin marketplace add ~/ubm-marketplace
/plugin install ubm-goal-setting@ubm-local
```

**完了確認**: `/plugin` の一覧に `ubm-goal-setting` が有効（`enabled`）で表示され、`/ubm-goal-setting` が補完に出れば成功です。書き込み保護フック（後述）は `hooks/hooks.json` に定義されていて、インストールと同時に有効化されます。

**新機能（v0.2.0）の追加依存はありません（標準ライブラリのみ）**: YouTube 取込・相談・グラフ生成/参照の各スクリプトは Python 標準ライブラリだけで動きます（`requires-python: ">=3.9"`）。インストールに追加の `pip` パッケージや外部サービス登録は不要です。具体的な YouTube の取得元だけは運用時に後から結び付ける設計で、ビルドの時点では `fixture` の取得元で受入テストが回ります。上記の方法 A / B いずれの導入でも、これらの入口（`/ubm-youtube-ingest`・`/ubm-consult`）は同じシンボリックリンクの展開で有効化されます。

---

CLI の例では、`PLUGIN_ROOT` を使うプラグインの絶対パス（例: `/path/to/harness/plugins/ubm-goal-setting`）としてシェルごとに設定してください。スキル経由では host の SKILL パスから親が解決します。

## 初回設定 — `UBM_VAULT_ROOT` 環境変数

`UBM_VAULT_ROOT` は **Obsidian の vault（生ソース置き場）のルートのパス**です。次の用途に使われます。

| 用途 | パス（`UBM_VAULT_ROOT` 配下） |
|---|---|
| 目標設定ファイルの保存先 | `05_Project/UBM/目標設定/` |
| 挑戦宣言と企画の保存先 | `05_Project/UBM/挑戦宣言/` |
| 日次ジャーナルの保存先 | `02_Configs/Daily/{YYYY-MM-DD}.md` |
| デイリーノートの埋め込み参照の更新 | `02_Configs/Templates/Daily.md` |
| ナレッジ差分検知のソース | `05_Project/UBM/` 配下の `.md`。利用者自身の記録を置く `目標設定/` と `挑戦宣言/` は検知しない（除外の正本は `skills/run-ubm-knowledge-sync/scripts/detect-knowledge-updates.py` の `EXCLUDED_SUBDIRS`） |

シェルの設定ファイルに `export` を追記します（パスは自分の vault に合わせる）:

```bash
# ~/.zshrc など
export UBM_VAULT_ROOT="$HOME/dev/dev/ObsidianMemo"
```

**未設定でも壊れません（縮退動作）**: 北原ナレッジ本体（router が列挙する6カテゴリの分割 JSON + ルーター）はプラグインに**同梱済み**（L1 の精選シード）のため、インストール直後・vault 未接続でも目標設定対話の知識参照は機能します。vault 未接続時のナレッジ同期は「検知 0 件」の正常終了になります。vault を接続すると、目標・挑戦宣言・日次ジャーナルの保存、デイリーノートの更新、差分同期の全機能が有効になります。

**フィードバック設定（任意）**: 本プラグインの機能自体は Notion を使いません。改善要望ループ（`run-skill-feedback`）を使う場合のみ、設置先のリポジトリのルートの `.notion-config.json` に改善要望（`improvement-request`）DB の ID を設定します（論理キーは計画での宣言・実 DB ID はローカル設定の二層）。

---

## 最初の一歩

```
/ubm-goal-setting weekly     # 週報の目標設定を対話で作成 (5〜8分)
/ubm-knowledge-sync --dry-run  # ナレッジ差分の検知だけ試す (書き込みなし)
```

引数なしの `/ubm-goal-setting` は、どの種別（週報/月報/期報）かの確認から始まります。種別の引数は `weekly` / `monthly` / `quarterly`（期報＝3 ヶ月）です。旧値 `bimonthly` も後方互換で受理されます。

---

## 新機能タスク集（YouTube 取込・相談・グラフ）— v0.2.0

バージョン 0.2.0 で追加した 2 スキル / 1 コマンドと 4 スクリプトの実行例です。**各スクリプトはリポジトリのルートから実行**します（例のパスはリポジトリのルートからの相対）。運用手順・スケジューラ設定・失敗時確認の正本は [`RUNBOOK.md`](./RUNBOOK.md)。

### (a) YouTube URL 単発取込

指定 1 本の動画をその場でナレッジ化します。

```
/ubm-youtube-ingest --url https://www.youtube.com/watch?v=XXXX
/ubm-youtube-ingest --url https://www.youtube.com/watch?v=XXXX --dry-run   # 検知・整形のみ（書き込み 0）
```

`--url` / `--backfill` / `--sync` は相互排他です。`--dry-run` は登録簿・正規化ソース・ナレッジのいずれにも書きません。

### (b) 全量バックフィル

`required-primary`（北原孝彦のコンサルティング）の全公開動画を、完全性ゲートが緑になるまで取り込みます。

```
/ubm-youtube-ingest --backfill
```

`FULL_BACKFILL_PASS` は `ingested == discovered_total` かつ `temporary_failure == 0` かつ `unapproved_unavailable == 0` のときだけ成立します（取得不能を除外して分母を縮める擬似 PASS は禁止）。ゲートの直接確認コマンドは RUNBOOK の「完全性ゲート」節。

### (c) スケジューラによる無人の差分同期

新着だけを差分で取り込みます。手動入口（`--sync`）とスケジューラの自動実行は**同じ1回きりの実行・同じ最終実行の記録（`cursor`）・同じ冪等キー（`video_id`）**を共有し、別系統の状態を作りません。

手動（その場で確認・再実行・障害リカバリ）:

```
/ubm-youtube-ingest --sync
/ubm-youtube-ingest --sync --dry-run   # 次に何が入るかだけ確認
```

無人（ホストのスケジューラが呼ぶ1回きりの実行の本体）:

```bash
python3 "${PLUGIN_ROOT:?absolute plugin root required}"/skills/run-ubm-youtube-ingest/scripts/run-youtube-sync-oneshot.py \
  --registry "${PLUGIN_ROOT:?absolute plugin root required}"/knowledge/youtube-registry.json \
  --channel <handle> \
  --source-out "$UBM_VAULT_ROOT/05_Project/UBM/YouTube" \
  --mode sync
```

スケジューラの `cron` 設定例・再試行/警告・実行権の占有（lease）の確認は [`RUNBOOK.md`](./RUNBOOK.md) の「YouTube 同期（スケジューラ / 冪等な1回きりの実行）」節が正本です。

### (d) 相談（`/ubm-consult`）

具体解を処方せず、考え方（思考フレーム）を選択肢＋適用視点で引き出し、解決策はユーザー自身の言葉で言語化します。

```
/ubm-consult "最近チームの動きが鈍い。どう考えればいい？"
```

起動は `/ubm-consult "相談内容"` コマンドから行います。コマンドは `run-ubm-consult` スキルを `Skill` ツールで起動します（スキルは `disable-model-invocation: false` なので、コマンドから呼べます）。週報/月報/期報の目標そのものを作りたい場合は `/ubm-goal-setting`（`run-ubm-goal-setting`）へ誘導されます（責務境界）。

### (e) ナレッジグラフの再生成・検証

6 カテゴリのナレッジと `knowledge-relation-extractor`（C08）の根拠付き辺から、依存グラフを決定論再生成・検証します。

```bash
python3 "${PLUGIN_ROOT:?absolute plugin root required}"/scripts/validate-knowledge-graph.py \
  --knowledge-dir "${PLUGIN_ROOT:?absolute plugin root required}"/knowledge \
  --graph-out "${PLUGIN_ROOT:?absolute plugin root required}"/knowledge/knowledge-graph.json
```

参照整合・自己ループ禁止・`depends_on` の非循環・根拠≥1・確信度 0..1・`review_status` 必須を検査し、PASS 時のみ `knowledge-graph.json` を書きます（終了コード 0=OK / 1=違反 / 2=使い方の誤り）。

### (f) 計画と実成果物の突合グラフ（harness の成果物グラフ）の生成と参照

計画（`task-graph`/`handoff`）と実成果物（`task-state`/`route-report`/`build-trace`/実在する `build_target`）を読み取り専用で突合して索引を作り、その正規化グラフを読み取り専用で引きます。

索引の生成:

```bash
python3 "${PLUGIN_ROOT:?absolute plugin root required}"/scripts/index-harness-artifact-graph.py \
  --plan-glob "plugin-plans/ubm-goal-setting/*" \
  --plugin-root "${PLUGIN_ROOT:?absolute plugin root required}" \
  --out "${PLUGIN_ROOT:?absolute plugin root required}"/knowledge/harness-artifact-graph.json
```

参照（書込なし）:

```bash
python3 "${PLUGIN_ROOT:?absolute plugin root required}"/scripts/consult-harness-artifact-graph.py \
  --topic "youtube ingest 全量性" \
  --knowledge-graph "${PLUGIN_ROOT:?absolute plugin root required}"/knowledge/knowledge-graph.json \
  --harness-artifact-graph "${PLUGIN_ROOT:?absolute plugin root required}"/knowledge/harness-artifact-graph.json \
  --query-type local --depth 2
```

参照は該当0件を正常終了（終了コード 0）とします。`--knowledge-graph` は必須、`--harness-artifact-graph` は任意で、省略するとナレッジグラフだけの参照（出力 `sources.harness_artifact_graph.status="absent"`）になります。ナレッジグラフ自体が未生成のときは飛ばします（代わりの手段の正本＝[`references/graph-consult-fallback-contract.md`](./references/graph-consult-fallback-contract.md)）。`--query-type` は `local|global|relationship`、`--depth` は 1..5 です。

> 運用時生成: `knowledge/youtube-registry.json`（登録台帳）・`knowledge/knowledge-graph.json`（C06）・`knowledge/harness-artifact-graph.json`（C05）はビルドでは作らず、上記コマンド / 1回きりの実行の初回実行時に生成されます（`--dry-run` は初期化も含め書込 0）。

---

## 第2部 — 技術説明（運用者向け）

### Phase0-5 の全体の流れ（目標設定）

`run-ubm-goal-setting` スキルは次の Phase を順に実行します（正本: スキルの `SKILL.md`）。

| 段階 | 責務 | 実行体 |
|---|---|---|
| Phase0-init | 種別（`weekly`/`monthly`/`quarterly`）と実行日を確定 | 本スキル / `AskUserQuestion` |
| Phase1-2-collect | 過去目標・合宿情報・ナレッジ・ジャーナルを並列収集 | `info-collector` サブエージェント |
| Phase2b-review | 振り返り時に既存目標を再評価（検査項目は `agents/goal-reviewer.md` の「レビューフレームワーク（13項目 + 北原視点）」節が正本。件数・内訳は本 README に書かず、その節を見てください） | `goal-reviewer` サブエージェント |
| Phase3-dialogue | step1〜5 対話（現状振り返り→ギャップ→目標→行動計画→最終確認） | `phase3-coordinator` + 責務プロンプト `prompts/R1-R5` |
| Phase4-format | テンプレート整形 + コンテンツ品質チェック（項目は `agents/output-formatter.md` の品質チェックリスト節が正本） | `output-formatter` サブエージェント |
| Phase5-validate | `validate-goal-output.py` で **公式21ブロック**を決定論検証（最大 3 回改善） | スクリプト |
| Phase6-daily-update | `Daily.md` の種別に該当する埋め込みのみ最新目標へ置換 | 本スキル |

公式 21 ブロック（出力構造）の定義正本は `skills/run-ubm-goal-setting/references/output-formats.md` + `data-contract.md`、保存前コンテンツ検証の項目は `agents/output-formatter.md` の品質チェックリスト節が正本です（件数は本 README に書かず、その節を見てください）。

### 日次ジャーナルの末尾ブロック（`/ubm-journal`）

`run-ubm-journal` スキルは対話で集めた内容を `02_Configs/Daily/{YYYY-MM-DD}.md` へ整形しますが、本文の後ろに**対話では聞かない固定ブロックを 2 つ**置きます（正本: スキルの `references/output-format.md`）。

| ブロック | 設問の正本 | 生成時の扱い |
|---|---|---|
| `# フェーズ別 課題チェックシート` | 前回ジャーナル | 対話で読み上げない。チェック状態を継承 |
| `# 原理原則 チェックシート` | `skills/run-ubm-journal/references/principle-checklist.md` | 対話で読み上げない。チェック状態を継承 |

`# 原理原則 チェックシート`（原理原則の設問 11 件）は**ジャーナル生成のたびに必ず末尾へ出力**されます。ヒアリング項目ではないので設問を 1 件ずつ確認することはせず、器として出すだけです。**チェック状態は前回ジャーナルから引き継がれ、対話の中で変わったと分かった項目だけが更新されます**（毎日ゼロに戻るわけではありません）。前回ジャーナルが無い初回だけ、正本のテンプレを全て未チェックで出します。設問の文言・順序・階層は生成側で書き換えません。`validate-journal-output.py` が `K01`（設問見出しの欠落）/ `K02`（チェックボックス行なし）で保存前に検査します。

### 挑戦宣言と企画（`/ubm-challenge`）

北原さんへ提出する「挑戦宣言と企画」（目的・数値目標・挑戦・リスク回避5理由・行うこと5つ・定期報告）を会話で引き出し、vault に保存して LINE 等へ貼れる提出用テキストを表示します。
AI は聞き手と `challenge-advisor`（読み取り専用エージェント）の2役です。聞き手が問いを聞き、ユーザーが答えるたびに（軽微（light）を除く）助言役が答えに紐づく北原ナレッジを探して深掘りの問いか方向の助言を1つ返し、聞き手がそれを聞いて要約確認で欄を確定します。欄の値はすべてユーザーの言葉から取ります。
正本はスキルの `references/challenge-format.md`（出力・合格条件）と `references/question-map.md`（対話）です。

### デュアルパス検索（ナレッジ参照）

`info-collector` は `knowledge/router.json` を索引に、3 レイヤーを**並列**で検索します: Path A=具体キーワード（`quick_lookup.by_issue` の `tags`）/ Path B=課題キー・フェーズキー / Path C=メタテーマ（`abstraction_layers`）。全パスのヒットを重複除去して該当 `knowledge/*.json` だけを `Read` し、複数パスに同時ヒットしたエントリを高優先で統合します（ルーターが列挙する全カテゴリ JSON の総当たり読み込みをしない）。

### 差分同期の仕組み（ナレッジ同期）

`run-ubm-knowledge-sync` は次の 3 層データ構造を前提に動きます。

- **L1 精選**（プラグイン同梱シード）: 6 カテゴリの分割 JSON + `router.json`。新規インストール直後から機能する知識本体。
- **L2 vault の生ソース**（`UBM_VAULT_ROOT` で外部解決）: YouTube 議事録・合宿記録・月報 FB 等の生ソース。
- **L3 帳簿**（プラグイン同梱・書き換え可）: `registry.json`（処理済み台帳・処理済みソースの実台帳）/ `sync-log.jsonl`（追記のみの同期ログ・空開始）/ `assets/kitahara-principles-db.md`。

同期フロー: `detect-knowledge-updates.py` が L2 の `.md` を `registry.json` の **MD5 ハッシュと照合**して `NEW`/`MODIFIED` を検知 → `knowledge-extractor` サブエージェントが内容別 6 カテゴリへ分類し `knowledge/*.json` + `router.json`/`registry.json` を更新（最大 20 ファイル/バッチの 1 トランザクション扱い）→ `check-knowledge-split.py` が 500 行閾値の肥大を機械検査。`MODIFIED` は `extracted_entry_ids` を辿って旧エントリを削除してから再抽出します。

### 書き込み保護（不明なら止めるフック）

`hooks/ubm-write-path-guard.py` が `PreToolUse`（`Write|Edit|MultiEdit`）で `UBM_VAULT_ROOT` 配下への書き込みを検査し、許可は前方一致 7 件（`05_Project/`・`02_Configs/Daily/`・`.claude/{skills,agents,commands,rules,prompts}/`）と完全一致 1 件（`02_Configs/Templates/Daily.md`）で、それ以外は終了コード 2 で遮断します。vault 外（プラグイン同梱の `knowledge/` 等）と `UBM_VAULT_ROOT` 未設定時は保護対象外です。判定不能な入力は**遮断側に倒します**（fail-closed）。

### 品質ゲート

- `validate-goal-output.py`: 統一ハイブリッド構造の公式21ブロック・NG 表現・やらないこと 3 項目以上（月報・期報の独立セクション）・逆算チェーン（C1〜C6）・シンプルさ上限（S1〜S3）を保存前に決定論検証。
- `validate-goal-linkage.py`: 一本筋（成果目標 ↔ 行動目標のグループ見出し）を両方向で照合する。照合規則は `validate-goal-output.py` と共用して二重に実装せず、上乗せするのは「1つの行動が複数の成果目標を指す `・` 区切りと、支える行動の無い成果目標を `rc=1` にする」「免除を `（土台）`／`（関係維持）` に限る」「月報の管理用グループだけを照合する」「分母0を `rc=3` にする」だけ（正本は `references/output-formats.md`「一本筋の照合は validate-goal-output.py と validate-goal-linkage.py で分担する」）。
- `validate-cross-level.py`: 期報・月報・週報を同時に読み、期アンカー8種が三層で一致しているかを照合する（`rc=1` で停止。単一ファイルの検査では層をまたぐズレを検出できないため）。
- `tests/`（`pytest`）: スクリプト / フックの機能テスト + ナレッジ台帳整合 + 手本（`golden-sample`）の回帰。**件数は本 README に書きません。** `RUNBOOK.md` の「検証」節の手順で実行し、その出力の件数と終了コードを見てください（`0`=全通過 / `3`=収集エラー / `5`=収集0件）。
- `EVALS.json`: 機械的な検査（`mechanical`）13 本と受入基準（`criteria-test`）の配線宣言。実行手順は `RUNBOOK.md` の「検証」節。

### YouTube 取込パイプライン（取込→正規化→抽出→辺→検証）— v0.2.0

`run-ubm-youtube-ingest` スキルは 2 ソースの登録簿（`required-primary`＝北原孝彦のコンサルティング / 第2ソース＝`pending-identification`）を分母に、4 つの段階を回します（正本: スキルの `SKILL.md` + `workflow-manifest.json`）。

| 段階 | 責務 | 実行体 |
|---|---|---|
| R1-source-mode | `--url`/`--backfill`/`--sync` とソースの優先度を確定（第2ソースが保留中でも `required-primary` を止めない） | 本スキル |
| R2-fetch-normalize | 正となる動画一覧をページ送りで最後までたどり、字幕を第一・**承認済み**の ASR を代わりの手段として取得し正規化 | `youtube-transcript-normalizer`（C01） |
| R3-extract-graph | 6 カテゴリ抽出 → 根拠付き有方向辺 → グラフ検証 | `knowledge-extractor` / `knowledge-relation-extractor`（C08）+ `validate-knowledge-graph.py`（C06） |
| R4-sync-reconcile | 最終実行の記録（`cursor`）/実行権の占有/再試行/警告を持つ冪等な1回きりの実行をスケジューラから実行し、台帳と報告を更新 | `scripts/run-youtube-sync-oneshot.py` |

不変則: **冪等キー = `video_id`**（同一動画を二度取り込まない・二回目 0 件）。**全量性は分母を縮めない**（取得不能を除外した擬似 PASS を禁止、`waived` は承認参照 `waiver_ref` 必須）。**文字起こしは信頼できないデータ**（本文中の命令/URL を実行しない。出所情報は制御領域=フロントマター、本文はデータ領域に封じる）。**実行権の占有**でスケジューラの二重発火を何もしない処理にする。全モードで `--dry-run` は書込 0。C03 完全性ゲート（`check-youtube-backfill-completeness.py`）は `content_coverage`（実際に取り込んだ割合）と `accountability_coverage`（承認除外控除後）を分離算出し、`FULL_BACKFILL_PASS` を機械判定します。

### 相談（コーチング型・非処方）— v0.2.0

`run-ubm-consult` は、考え方を押し付けず一緒に組み立てる相談の進行役です。最初に問い中心／説明中心／例を仮説として少量／整理だけを選び、危機・重大な判断は安全分岐します。解決策は `role=user` の発話から確定し、行動化または内省のどちらで締めるかもユーザーが選びます。グラフは C07 で読み取り専用で参照し、保存は明示同意時だけ `session-id` 配下へ最小要約を残し、C11 の検査スクリプトが検証します。入口は `/ubm-consult` です。

### デュアルグラフ（C05 索引 / C06 検証 / C07 参照）— v0.2.0

北原ナレッジの意味的つながりと、harness の実成果物系譜を、別々のグラフとして扱います。

- **C06 `validate-knowledge-graph.py`**: ナレッジのエントリと C08 の根拠付き辺（`depends_on|supports|contradicts|derived_from`）から `knowledge-graph.json` を決定論再生成・検証。`related` は無方向連想として循環の対象外、宙に浮いた辺は致命的とせず除外。
- **C05 `index-harness-artifact-graph.py`**: 「これから作る計画」（`task-graph`/`handoff`）と「実成果物」（`task-state`/`route-report`/`build-trace`/実在する `build_target`）を読み取り専用で突合し、`planned/built/verified/stale` 状態と出所情報/鮮度を持つ `harness-artifact-graph.json` を生成。計画のタスクグラフを実成果物と誤同定しないための正規化された索引です。
- **C07 `consult-harness-artifact-graph.py`**: C05/C06 の 2 グラフを跨いで `local|global|relationship` の問い合わせで探索する純粋読取レイヤー（書込なし・ネットワーク通信なし・該当0件も終了コード 0）。`run-ubm-goal-setting` の Phase1-2-collect と `run-ubm-consult` の R3 が利用側です。

これら 3 グラフ実ファイル（`knowledge-graph.json` / `harness-artifact-graph.json` / `youtube-registry.json`）はビルドでは作らず、上記コマンド・1回きりの実行の初回実行時に運用生成されます。

### 構成

```text
plugins/ubm-goal-setting/
├── skills/run-ubm-goal-setting/     # 目標設定スキル (+ scripts/validate-goal-output.py + prompts/R1-R5 対話プロンプト正本)
├── skills/run-ubm-knowledge-sync/   # ナレッジ同期スキル (+ detect/check の各スクリプト)
├── skills/run-ubm-journal/          # 日次ジャーナルスキル (+ build-journal-context / validate-journal-output)
├── skills/run-ubm-challenge/        # 挑戦宣言と企画スキル (+ validate-challenge-output + question-map 対話正本)
├── agents/                          # サブエージェント 9 本 (info-collector/goal-reviewer/phase3-coordinator/output-formatter/knowledge-extractor/knowledge-relation-extractor/youtube-transcript-normalizer/journal-composer/challenge-advisor)
├── commands/                        # /ubm-goal-setting, /ubm-knowledge-sync, /ubm-youtube-ingest, /ubm-consult, /ubm-journal, /ubm-challenge
├── hooks/ubm-write-path-guard.py    # 書き込み保護 (PreToolUse)
├── knowledge/                       # L1 精選の分割 JSON + router/schema/registry/sync-log
├── tests/                           # pytest（件数は RUNBOOK.md の手順の出力で見る）
├── EVALS.json / plugin-composition.yaml / RUNBOOK.md / CHANGELOG.md
├── .claude-plugin/plugin.json       # 公式のプラグインの定義ファイル (hooks 配線)
└── references/package-contract.json # harness のメタデータ (distributable:false, entry_points)
```

---

## 次に読むもの

- 運用・検証・復旧: [`RUNBOOK.md`](./RUNBOOK.md)
- 変更履歴: [`CHANGELOG.md`](./CHANGELOG.md)
- 設計判断・受入基準の由来: `plugin-plans/ubm-goal-setting/`（13 段階の計画 + コンポーネント一覧）
