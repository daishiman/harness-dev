# ubm-goal-setting — 北原さん式ゴールセッティング

UBM（北原さん式ゴールセッティング）の**目標設定・振り返り対話**と**ナレッジ差分同期**を 1 つにした Claude Code プラグインです。ObsidianMemo vault で運用していた資産（skill / sub-agent / hook / script / knowledge JSON 一式）を移植したもので、**個人利用前提**（`distributable:false`・公開 marketplace 非掲載）です。

このドキュメントは「初めて使う人がインストールし、`UBM_VAULT_ROOT` を設定して最初の目標設定を回せる状態にする」までの導入ガイドです。**日々の運用（入口コマンド詳細・検証コマンド・復旧手順）は [`RUNBOOK.md`](./RUNBOOK.md) が正本**で、本 README とは役割を分担しています（README=初見導入 / RUNBOOK=運用）。

---

## Part 1 — これは何をするもの？（前提知識なしで読める説明）

**たとえ話**: 部活の顧問の先生（＝北原さん）が隣にいて、「今週は何をがんばる？」「先月は何がうまくいった？」と質問しながら、目標カードを一緒に作ってくれる道具です。

1. **目標設定・振り返り対話** (`/ubm-goal-setting`)
   - 「1 週間（週報）・1 ヶ月（月報）・2 ヶ月（期報）」の目標を、AI との短い対話で作ります。
   - できあがった目標は決まった型（**21 項目**）のチェックに**合格しないと保存されません**。「頑張る」「意識する」のようなあいまいな言葉は機械が弾き、「誰に・何を・いつまでに・何件」まで具体化させます。
   - 目標には「**やらないこと**」も 3 つ以上書きます。やることを増やすより、迷いを減らすほうが行動につながるからです。

2. **ナレッジ同期** (`/ubm-knowledge-sync`)
   - 北原さんの新しい教え（動画の議事録・合宿の記録・月報へのフィードバックなど）を読み取り、**6 つの引き出し**（原則 / 相談 / フェーズ別アドバイス / 行動ガイド / マインドセット / 事例）に整理して貯めます。
   - 貯めた知識は、次の目標設定の対話で自動的に引き出されます。**学ぶ→貯める→次の目標に生かす**、が一つのサイクルになります。

**なぜこの 2 つがセットか**: 目標は「作って終わり」だと忘れます。毎週の振り返り→次の目標→新しい学びの取り込み、というループを回し続けるための道具だからです。

### さらにできること（新機能をやさしく・v0.2.0）

3. **相談にのってもらう** (`/ubm-consult`)
   - 悩みごとを話すと、答え（「こうしなさい」）をズバッと教えるのではなく、**「こういう考え方があるよ。あなたの場合はどう当てはまる？」と、考え方（思考のフレーム）を一緒に見つけてくれる**道具です。
   - 答えを丸写しするより、自分の言葉で「じゃあ自分はこうしよう」と決めたことのほうが行動に移せる、という考え方に基づきます。だから最後は必ず「今の状況→なりたい姿→足りないもの→次の一歩」の形で、**あなた自身の言葉**に整理して締めます。

4. **YouTube の学びを「地図」にする** (`/ubm-youtube-ingest`)
   - 北原さんの YouTube 動画の文字起こしを読み取り、教えを 6 つの引き出し（ナレッジ同期と同じ引き出し）に貯めます。
   - さらに、貯めた教え同士の「これはあれの土台」「これはあれを支える」というつながりを線でつなぎ、**知識の地図（グラフ）**にします。ひとつの話題から、関係する話題を線をたどって引けるようになります。
   - たくさんの動画を一本ずつ手で入れるのは大変なので、（1）URL を 1 本ずつ・（2）過去分をまとめて全部・（3）新しく増えた分だけ自動で、の 3 つの入れ方を選べます。同じ動画を二重に入れない仕組み（動画 ID を目印にする）が入っているので、何度実行しても散らかりません。

**この 4 つの関係**: YouTube から学びを取り込んで地図にし、相談で考え方として引き出し、目標設定で行動に落とす。**「学ぶ→つなぐ→引き出す→動く」**がひとつのループになります。

---

## インストール（ローカル導入）

本プラグインは `distributable:false` のため、**公開カタログ（`.claude-plugin/marketplace.json`）には掲載していません**。リモートの `/plugin marketplace add OWNER/harness` からは導入**できず**、clone したローカル repo を起点に導入します。

### 方法 A — harness repo 内で使う（開発・レビュー向け・最短）

repo を clone し、repo root で `.claude/` symlink を展開します（`harness-creator` と同じ project-local 方式）。

```bash
git clone https://github.com/OWNER/harness.git
cd harness
make sync   # plugins/ubm-goal-setting/ の skills/commands/agents を .claude/ へ symlink 展開
```

この repo を開いた Claude Code セッションで `/ubm-goal-setting` などがそのまま使えます。

### 方法 B — vault 作業フォルダなど repo 外で使う（ローカル marketplace add 経由）

個人用のローカル marketplace カタログを作り、そこから install します（公開カタログには載せません）。

```bash
# 1. 個人用カタログを作る (plugin 実体は clone 済み harness を symlink 参照)
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

Claude Code（CLI / Desktop 共通）のチャット欄で:

```
/plugin marketplace add ~/ubm-marketplace
/plugin install ubm-goal-setting@ubm-local
```

**完了確認**: `/plugin` の一覧に `ubm-goal-setting` が enabled で表示され、`/ubm-goal-setting` が補完に出れば成功です。書き込み保護 hook（後述）は plugin manifest の `hooks` ブロック経由で install と同時に有効化されます。

**新機能（v0.2.0）の追加依存はありません（stdlib のみ）**: YouTube 取込・相談・グラフ生成/consult の各 script は Python 標準ライブラリだけで動きます（`requires-python: ">=3.9"`）。install に追加の pip パッケージや外部サービス登録は不要です。具体の YouTube provider だけは運用時に late-bind する設計で、build 時点では fixture provider で受入テストが回ります。上記の方法 A / B いずれの導入でも、これらの入口（`/ubm-youtube-ingest`・`/ubm-consult`）は同じ symlink 展開で有効化されます。

---

## 初回設定 — `UBM_VAULT_ROOT` 環境変数

`UBM_VAULT_ROOT` は **Obsidian vault（生ソース置き場）の root パス**です。次の 3 つに使われます。

| 用途 | パス（`UBM_VAULT_ROOT` 配下） |
|---|---|
| 目標設定ファイルの保存先 | `05_Project/UBM/目標設定/` |
| Daily ノートの embed 参照更新 | `02_Configs/Templates/Daily.md` |
| ナレッジ差分検知のソース | `05_Project/UBM/` 配下の `.md` 全般 |

シェルの profile に export を追記します（パスは自分の vault に合わせる）:

```bash
# ~/.zshrc など
export UBM_VAULT_ROOT="$HOME/dev/dev/ObsidianMemo"
```

**未設定でも壊れません（縮退動作）**: 北原ナレッジ本体（28 JSON + router）は plugin に**同梱済み**（L1 curated シード）のため、install 直後・vault 未接続でも目標設定対話の知識参照は機能します。vault 未接続時のナレッジ同期は「検知 0 件」の正常終了になります。vault を接続すると、目標の保存・Daily 更新・差分同期の全機能が有効になります。

**フィードバック設定（任意）**: 本プラグインの機能自体は Notion を使いません。改善要望ループ（`run-skill-feedback`）を使う場合のみ、設置先 repo root の `.notion-config.json` に improvement-request DB の ID を設定します（論理キーは plan 宣言・実 DB ID はローカル設定の二層）。

---

## 最初の一歩

```
/ubm-goal-setting weekly     # 週報の目標設定を対話で作成 (5〜8分)
/ubm-knowledge-sync --dry-run  # ナレッジ差分の検知だけ試す (書き込みなし)
```

引数なしの `/ubm-goal-setting` は、どの種別（週報/月報/期報）かの確認から始まります。

---

## 新機能タスク集（YouTube 取込・相談・グラフ）— v0.2.0

version 0.2.0 で追加した 2 skill / 1 command と 4 script の実行例です。**各 script は repo root から実行**します（例のパスは repo-root 相対）。運用手順・scheduler 設定・失敗時確認の正本は [`RUNBOOK.md`](./RUNBOOK.md)。

### (a) YouTube URL 単発取込

指定 1 本の動画をその場でナレッジ化します。

```
/ubm-youtube-ingest --url https://www.youtube.com/watch?v=XXXX
/ubm-youtube-ingest --url https://www.youtube.com/watch?v=XXXX --dry-run   # 検知・整形のみ（書き込み 0）
```

`--url` / `--backfill` / `--sync` は相互排他です。`--dry-run` は registry・正規化ソース・knowledge のいずれにも書きません。

### (b) 全量バックフィル

required-primary（北原孝彦のコンサルティング）の全公開動画を、完全性ゲートが緑になるまで取り込みます。

```
/ubm-youtube-ingest --backfill
```

`FULL_BACKFILL_PASS` は `ingested == discovered_total` かつ `temporary_failure == 0` かつ `unapproved_unavailable == 0` のときだけ成立します（取得不能を除外して分母を縮める擬似 PASS は禁止）。ゲートの直接確認コマンドは RUNBOOK の「完全性ゲート」節。

### (c) scheduler 無人差分同期

新着だけを差分で取り込みます。手動入口（`--sync`）と scheduler 自動実行は**同じ one-shot・同じ cursor・同じ idempotency key（`video_id`）**を共有し、別系統の状態を作りません。

手動（その場で確認・再実行・障害リカバリ）:

```
/ubm-youtube-ingest --sync
/ubm-youtube-ingest --sync --dry-run   # 次に何が入るかだけ確認
```

無人（host scheduler が呼ぶ one-shot 本体）:

```bash
python3 plugins/ubm-goal-setting/skills/run-ubm-youtube-ingest/scripts/run-youtube-sync-oneshot.py \
  --registry plugins/ubm-goal-setting/knowledge/youtube-registry.json \
  --channel <handle> \
  --source-out "$UBM_VAULT_ROOT/05_Project/UBM/YouTube" \
  --mode sync
```

scheduler の cron 設定例・retry/alert・lease の確認は [`RUNBOOK.md`](./RUNBOOK.md) の「YouTube Sync（scheduler / 冪等 one-shot）」節が正本です。

### (d) 相談（`/ubm-consult`）

具体解を処方せず、考え方（思考フレーム）を選択肢＋適用視点で引き出し、解決策はユーザー自身の言葉で言語化します。

```
/ubm-consult "最近チームの動きが鈍い。どう考えればいい？"
```

起動は `/ubm-consult "相談内容"` コマンドから行います。`run-ubm-consult` スキルは `disable-model-invocation: true` のため「相談したい」「壁打ち」といった**発話だけでは自動起動しません**（コマンドが唯一の入口）。週報/月報/期報の目標そのものを作りたい場合は `/ubm-goal-setting`（`run-ubm-goal-setting`）へ誘導されます（責務境界）。

### (e) knowledge graph 再生成/検証

6 カテゴリ knowledge と `knowledge-relation-extractor`（C08）の根拠付き辺から、依存グラフを決定論再生成・検証します。

```bash
python3 plugins/ubm-goal-setting/scripts/validate-knowledge-graph.py \
  --knowledge-dir plugins/ubm-goal-setting/knowledge \
  --graph-out plugins/ubm-goal-setting/knowledge/knowledge-graph.json
```

参照整合・self-loop 禁止・`depends_on` の DAG 非循環・evidence≥1・confidence 0..1・review_status 必須を検査し、PASS 時のみ `knowledge-graph.json` を書きます（exit 0=OK / 1=違反 / 2=usage）。

### (f) harness artifact graph index/consult

計画（task-graph/handoff）と実成果物（task-state/route-report/build-trace/実在 build_target）を read-only 突合して index を作り、その正規化グラフを read-only で引きます。

index 生成:

```bash
python3 plugins/ubm-goal-setting/scripts/index-harness-artifact-graph.py \
  --plan-glob "plugin-plans/ubm-goal-setting/*" \
  --plugin-root plugins/ubm-goal-setting \
  --out plugins/ubm-goal-setting/knowledge/harness-artifact-graph.json
```

consult（書込なし）:

```bash
python3 plugins/ubm-goal-setting/scripts/consult-harness-artifact-graph.py \
  --topic "youtube ingest 全量性" \
  --knowledge-graph plugins/ubm-goal-setting/knowledge/knowledge-graph.json \
  --harness-artifact-graph plugins/ubm-goal-setting/knowledge/harness-artifact-graph.json \
  --query-type local --depth 2
```

consult は zero-hit を正常終了（exit 0）とします。`--knowledge-graph` は必須、`--harness-artifact-graph` は任意で、省略すると knowledge 単独 consult（出力 `sources.harness_artifact_graph.status="absent"`）になります。knowledge graph 自体が未生成のときは skip します（fallback 正本＝[`references/graph-consult-fallback-contract.md`](./references/graph-consult-fallback-contract.md)）。`--query-type` は `local|global|relationship`、`--depth` は 1..5 です。

> 運用時生成: `knowledge/youtube-registry.json`（登録台帳）・`knowledge/knowledge-graph.json`（C06）・`knowledge/harness-artifact-graph.json`（C05）は build では作らず、上記コマンド / one-shot の初回実行時に生成されます（`--dry-run` は初期化も含め書込 0）。

---

## Part 2 — 技術説明（運用者向け）

### Phase0-5 ワークフロー（目標設定）

`run-ubm-goal-setting` skill は次の Phase を順に実行します（正本: skill の `SKILL.md`）。

| Phase | 責務 | 実行体 |
|---|---|---|
| Phase0-init | 種別（weekly/monthly/bimonthly）と実行日を確定 | 本 skill / AskUserQuestion |
| Phase1-2-collect | 過去目標・合宿情報・ナレッジ・journal を並列収集 | `info-collector` sub-agent |
| Phase2b-review | 振り返り時に既存目標を 8 項目で再評価 | `goal-reviewer` sub-agent |
| Phase3-dialogue | step1〜5 対話（現状振り返り→ギャップ→目標→行動計画→最終確認） | `phase3-coordinator` + 責務プロンプト `prompts/R1-R5` |
| Phase4-format | テンプレート整形 + 15 項目コンテンツ品質チェック | `output-formatter` sub-agent |
| Phase5-validate | `validate-goal-output.py` で **21 項目**を決定論検証（最大 3 回改善） | script |
| Phase6-daily-update | `Daily.md` の種別該当 embed のみ最新目標へ置換 | 本 skill |

21 項目（出力構造）の定義正本は `skills/run-ubm-goal-setting/references/output-formats.md` + `data-contract.md`、15 項目（保存前コンテンツ検証）は `output-formatter` prompt の品質チェックリスト節です。

### デュアルパス検索（ナレッジ参照）

`info-collector` は `knowledge/router.json` を索引に、3 レイヤーを**並列**で検索します: Path A=具体キーワード（`quick_lookup.by_issue` の tags）/ Path B=課題キー・フェーズキー / Path C=メタテーマ（`abstraction_layers`）。全パスのヒットを重複除去して該当 `knowledge/*.json` だけを Read し、複数パスに同時ヒットしたエントリを高優先でマージします（全 28 JSON の総当たり読み込みをしない）。

### 差分同期の仕組み（ナレッジ同期）

`run-ubm-knowledge-sync` は次の 3 層データ構造を前提に動きます。

- **L1 curated**（plugin 同梱シード）: 6 カテゴリ 28 JSON + `router.json`。fresh-install 直後から機能する知識本体。
- **L2 raw vault sources**（`UBM_VAULT_ROOT` で外部解決）: YouTube 議事録・合宿記録・月報 FB 等の生ソース。
- **L3 bookkeeping**（plugin 同梱・mutable）: `registry.json`（処理済み台帳・初期値 67 ソース）/ `sync-log.jsonl`（append-only 同期ログ・空開始）/ `assets/kitahara-principles-db.md`。

同期フロー: `detect-knowledge-updates.py` が L2 の `.md` を `registry.json` の **MD5 ハッシュと照合**して NEW/MODIFIED を検知 → `knowledge-extractor` sub-agent が内容別 6 カテゴリへ分類し `knowledge/*.json` + `router.json`/`registry.json` を更新（最大 20 ファイル/バッチの 1 トランザクション扱い）→ `check-knowledge-split.py` が 500 行閾値の肥大を機械検査。MODIFIED は `extracted_entry_ids` を辿って旧エントリを削除してから再抽出します。

### 書き込み保護（fail-closed hook）

`hooks/ubm-write-path-guard.py` が PreToolUse（`Write|Edit|MultiEdit`）で `UBM_VAULT_ROOT` 配下への書き込みを検査し、許可 2 パス（`05_Project/UBM/目標設定/` 配下・`02_Configs/Templates/Daily.md`）以外は exit 2 で遮断します。vault 外（plugin 同梱 `knowledge/` 等）と `UBM_VAULT_ROOT` 未設定時は保護対象外です。判定不能な入力は**遮断側に倒します**（fail-closed）。

### 品質ゲート

- `validate-goal-output.py`: 統一ハイブリッド構造 21 項目・NG 表現・やらないこと 3 項目以上を保存前に決定論検証。
- `tests/`（pytest 44 件）: script×3 / hook×1 の機能テスト + knowledge 台帳整合 + golden-sample 回帰。
- `EVALS.json`: mechanical lint 13 本と受入基準（criteria-test）の配線宣言。実行手順は `RUNBOOK.md` の Verification 節。

### YouTube 取込パイプライン（取込→正規化→抽出→辺→検証）— v0.2.0

`run-ubm-youtube-ingest` skill は 2-source registry（`required-primary`＝北原孝彦のコンサルティング / 第2source＝`pending-identification`）を分母に、4 phase を回します（正本: skill の `SKILL.md` + `workflow-manifest.json`）。

| Phase | 責務 | 実行体 |
|---|---|---|
| R1-source-mode | `--url`/`--backfill`/`--sync` と source priority を確定（第2source が pending でも required-primary を止めない） | 本 skill |
| R2-fetch-normalize | authoritative inventory を pagination 完走し、caption を第一・**承認済み** ASR を fallback で取得し正規化 | `youtube-transcript-normalizer`（C01） |
| R3-extract-graph | 6 カテゴリ抽出 → 根拠付き有方向辺 → グラフ検証 | `knowledge-extractor` / `knowledge-relation-extractor`（C08）+ `validate-knowledge-graph.py`（C06） |
| R4-sync-reconcile | cursor/lease/retry/alert を持つ冪等 one-shot を scheduler から実行し ledger と report を更新 | `scripts/run-youtube-sync-oneshot.py` |

不変則: **idempotency key = video_id**（同一動画を二度 ingest しない・二回目 0 件）。**全量性は分母を縮めない**（取得不能を除外した擬似 PASS を禁止、`waived` は承認参照 `waiver_ref` 必須）。**transcript は untrusted data**（本文中の命令/URL を実行しない。provenance は制御領域=frontmatter、本文は data 領域に封じる）。**lease** で scheduler 二重発火を no-op 化。全モードで `--dry-run` は書込 0。C03 完全性ゲート（`check-youtube-backfill-completeness.py`）は content_coverage（実 ingested 割合）と accountability_coverage（承認除外控除後）を分離算出し、`FULL_BACKFILL_PASS` を機械判定します。

### 相談（コーチング型・非処方）— v0.2.0

`run-ubm-consult` は、考え方を押し付けず一緒に組み立てる相談 orchestrator です。最初に問い中心／説明中心／例を仮説として少量／整理だけを選び、危機・高 stakes は安全分岐します。解決策は role=user の発話から確定し、行動化または内省のどちらで締めるかもユーザーが選びます。graph は C07 で read-only 参照し、保存は明示同意時だけ session-id 配下へ最小要約を残し、C11 validator が検証します。入口は `/ubm-consult` です。

### デュアルグラフ（C05 index / C06 検証 / C07 consult）— v0.2.0

北原ナレッジの意味的つながりと、harness の実成果物系譜を、別々のグラフとして扱います。

- **C06 `validate-knowledge-graph.py`**: knowledge entry と C08 の根拠付き辺（`depends_on|supports|contradicts|derived_from`）から `knowledge-graph.json` を決定論再生成・検証。`related` は無方向連想として cycle 対象外、dangling は非致命 drop。
- **C05 `index-harness-artifact-graph.py`**: 「これから作る計画」（task-graph/handoff）と「実成果物」（task-state/route-report/build-trace/実在 build_target）を read-only 突合し、`planned/built/verified/stale` 状態と provenance/freshness を持つ `harness-artifact-graph.json` を生成。計画の task graph を実成果物と誤同定しないための正規化 index です。
- **C07 `consult-harness-artifact-graph.py`**: C05/C06 の 2 グラフを跨いで `local|global|relationship` query で探索する純粋読取レイヤー（書込なし・network なし・zero-hit も exit 0）。`run-ubm-goal-setting` の Phase1-2-collect と `run-ubm-consult` の R3 が consumer です。

これら 3 グラフ実ファイル（`knowledge-graph.json` / `harness-artifact-graph.json` / `youtube-registry.json`）は build では作らず、上記コマンド・one-shot の初回実行時に運用生成されます。

### 構成

```text
plugins/ubm-goal-setting/
├── skills/run-ubm-goal-setting/     # 目標設定 skill (+ scripts/validate-goal-output.py + prompts/R1-R5 対話プロンプト正本)
├── skills/run-ubm-knowledge-sync/   # ナレッジ同期 skill (+ detect/check scripts)
├── agents/                          # sub-agent 5 本 (info-collector/goal-reviewer/phase3-coordinator/output-formatter/knowledge-extractor)
├── commands/                        # /ubm-goal-setting, /ubm-knowledge-sync, /ubm-youtube-ingest, /ubm-consult
├── hooks/ubm-write-path-guard.py    # 書き込み保護 (PreToolUse)
├── knowledge/                       # L1 curated 28 JSON + router/schema/registry/sync-log
├── tests/                           # pytest 44 件
├── EVALS.json / plugin-composition.yaml / RUNBOOK.md / CHANGELOG.md
├── .claude-plugin/plugin.json       # 公式 plugin manifest (hooks 配線)
└── references/package-contract.json # harness metadata (distributable:false, entry_points)
```

---

## 次に読むもの

- 運用・検証・復旧: [`RUNBOOK.md`](./RUNBOOK.md)
- 変更履歴: [`CHANGELOG.md`](./CHANGELOG.md)
- 設計判断・受入基準の由来: `plugin-plans/ubm-goal-setting/`（13 phase 計画 + component inventory）
