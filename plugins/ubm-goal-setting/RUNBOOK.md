正式先を更新するスキル経由の操作は `references/guarded-publication-contract.md` に従い、親の中央guard executeから行う。無人oneshotのスケジューラ運用は独立した既存運用であり、スキル経由で新規起動・設定しない。

# ubm-goal-setting 運用手順書

## 目的

この運用手順書は、`ubm-goal-setting` プラグインの個人利用運用で確認すべき入口、環境変数、保護境界、検証コマンドをまとめる。

## 入口

- `/ubm-goal-setting [weekly|monthly|quarterly]`: 目標設定・振り返り対話を生成し、`references/validation-gates.md` の表に従い下書きと保存後のファイルを検証する。期報は 3 ヶ月。旧値 `bimonthly` は `quarterly` の後方互換の別名として受理する。
- `/ubm-knowledge-sync [--all] [--since YYYY-MM-DD] [--dry-run]`: L2 の vault のソースの差分を検知し、ナレッジ JSON を同期する。
- `/ubm-youtube-ingest [--url URL | --backfill | --sync] [--source SOURCE] [--dry-run]` (v0.2.0): 北原さん YouTube を 3 モード（URL 単発 / 厳格全量 / スケジューラによる無人差分）で手動起動・再実行・試し実行する。手動の同期はスケジューラの1回きりの実行と同一の最終実行の記録（`cursor`） / 冪等キー（`video_id`）を共有する。モード（`--url`/`--backfill`/`--sync`）は相互排他。
- `/ubm-consult "[相談内容]"` (v0.2.0): 具体解を処方せず考え方（思考フレーム）を提示するコーチング型相談。本コマンドは `run-ubm-consult` スキルを `Skill` ツールで起動する（スキルは `disable-model-invocation: false`。コマンドからの起動を推奨の入口とする）。挑戦宣言を作る相談は `/ubm-challenge` へ、目標設定そのものは `/ubm-goal-setting`（`run-ubm-goal-setting`）へ委譲する。
- `/ubm-challenge "[挑戦の仮タイトル]"`: 挑戦宣言と企画を会話で引き出し、vault に保存して提出用テキストを表示する。保存先と検査は `skills/run-ubm-challenge/references/challenge-format.md` と `SKILL.md` の C6-C7 が正本。本コマンドは `run-ubm-challenge` スキルを `Skill` ツールで起動する（スキルは `disable-model-invocation: false`。コマンドからの起動を推奨の入口とする）。

## 環境変数

- `UBM_VAULT_ROOT`: L2 の vault の生ソースと、`Daily.md` の埋め込みの更新先のルート。未設定または未接続でも L1 の精選ナレッジはプラグイン同梱のシードから読める。
- `CLAUDE_PLUGIN_ROOT`: フックとスキルのスクリプトを自分の位置からの相対で解決するのに使うプラグインのルート。

## 書き込み保護

`hooks/ubm-write-path-guard.py` は `UBM_VAULT_ROOT` 配下の `Write`/`Edit`/`MultiEdit` だけを検査する。

許可する vault への書き込み (正本は `hooks/ubm-write-path-guard.py` の `ALLOWED_PREFIXES` / `ALLOWED_EXACT`):

- 前方一致 7 件: `05_Project/`・`02_Configs/Daily/`・`.claude/{skills,agents,commands,rules,prompts}/`
- 完全一致 1 件: `02_Configs/Templates/Daily.md`

各スキルが実際に書く範囲はこれより狭く、その境界は各スキルの規則が守る (例: 目標設定は `05_Project/UBM/目標設定/` と `Daily.md` の埋め込みの行だけ、相談記録は vault へ書かない)。

保護対象外:

- vault 外のプラグイン同梱 `knowledge/*.json`
- `UBM_VAULT_ROOT` 未設定時の任意のパス
- `Read` など書き込みをしないツール

## 検証

リポジトリのルートから実行する。`python3` は**どれを指しているかで結果が変わる**。`pytest` が入っていないインタプリタでは `No module named pytest` で `rc=1` になり、テストが1件も走らない（この環境では `/usr/bin/python3` がそれに当たる）。先に次を確認し、`rc=0` を返すインタプリタのパスを以降の `python3` の位置に使う。

```bash
python3 -c "import pytest" ; echo $?   # 0 なら以降の python3 をそのまま使える
# 0 以外なら pytest が入っている別インタプリタを探して、そのパスを以降の python3 の位置に置く
# （例: /usr/local/bin/python3 -c "import pytest" ; echo $?）
```

終了コードは値そのものを読む。`pytest` は `0`=全通過 / `3`=収集エラー / `5`=収集0件。`| tail` `| grep` を挟むとパイプ末尾の終了コードしか読めないので、`cmd > out.txt 2>&1; rc=$?` の形で取る。件数はこの出力に出たものを正とし、README などの本文に書き写さない。

```bash
python3 -m pytest plugins/ubm-goal-setting/tests -q
python3 plugins/ubm-goal-setting/skills/run-ubm-knowledge-sync/scripts/check-knowledge-split.py --dir plugins/ubm-goal-setting/knowledge
python3 -m json.tool plugins/ubm-goal-setting/.claude-plugin/plugin.json >/dev/null
python3 -m json.tool plugins/ubm-goal-setting/EVALS.json >/dev/null
```

## YouTube 同期（スケジューラ / 冪等な1回きりの実行）— v0.2.0

無人の定期取込は、手動コマンド（`/ubm-youtube-ingest`）と**同一の1回きりの実行**（`skills/run-ubm-youtube-ingest/scripts/run-youtube-sync-oneshot.py`）をホストのスケジューラが呼ぶことで実現する（常駐プロセスでなく、実行権の占有を伴う1回きりの実行による、環境を選ばない設計）。手動の同期とスケジューラは同じ最終実行の記録（`cursor`） / 冪等キー（`video_id`）を共有し、別系統の状態を作らない。

1回きりの実行の起動（リポジトリのルートから）:

```bash
python3 plugins/ubm-goal-setting/skills/run-ubm-youtube-ingest/scripts/run-youtube-sync-oneshot.py \
  --registry plugins/ubm-goal-setting/knowledge/youtube-registry.json \
  --channel <handle> \
  --source-out "$UBM_VAULT_ROOT/05_Project/UBM" \
  --mode sync --max-retries 3 --lease-ttl 900
```

- **取得元**: `--provider` の既定は `fixture`（受入テスト用）。具体的な YouTube の取得元は運用時に後から結び付ける設計で、`fixture` の経路（`--provider fixture --fixture <file>`）で冪等性を検証する。
- **正規化ソースの配置**: `--source-out` は `detect-knowledge-updates.py` が `source_type=youtube` として検知できる vault 配下（`05_Project/UBM/` 配下）にする。1回きりの実行は出所情報を保った欠落のない保存に徹し、意味抽出（C08→C06）は下流の R3 が担う。
- **書込境界**: 1回きりの実行の書き込み範囲は `--registry` と `--source-out` 配下のみ。`--dry-run` は登録簿の初期化も含め書込 0。プラグイン同梱の `knowledge/*.json` / 登録簿は vault 外ゆえ `ubm-write-path-guard` の対象外（vault 側の資産への書込のみフックが検査する）。

`cron` の設定例（毎時 05 分に差分同期・リポジトリのルートへ `cd`）:

```cron
5 * * * * cd /path/to/harness && UBM_VAULT_ROOT="$HOME/dev/dev/ObsidianMemo" python3 plugins/ubm-goal-setting/skills/run-ubm-youtube-ingest/scripts/run-youtube-sync-oneshot.py --registry plugins/ubm-goal-setting/knowledge/youtube-registry.json --channel <handle> --source-out "$UBM_VAULT_ROOT/05_Project/UBM" --mode sync >> "$HOME/.ubm-youtube-sync.log" 2>&1
```

### 失敗時の確認（再試行 / 警告 / 実行権の占有）

1回きりの実行は標準出力に同期の報告（JSON・正本形式は `skills/run-ubm-youtube-ingest/references/sync-report-format.md`）を出す。スケジューラのログでは以下を確認する:

- **`temporary_failure`**: `alerts` に `[temporary_failure] <video_id> (attempt N)`。次回の実行で自動で再試行され、復旧すると `ingested` に計上される（`attempts` が増える）。`--max-retries`（既定 3）超過は `[retry_exhausted]`。
- **`quota` / `auth`**: `stopped_reason` が `quota` / `auth`。穏当な停止（終了コード 0）でスケジューラは次の実行周期で再開する。`alerts` に `[quota]` / `[auth]`。
- **実行権の占有（lease）**: スケジューラの二重発火時、期限切れでない実行権の占有を持つ実行が居れば `stopped_reason=lease_held` で何もしない（終了コード 0）。`--lease-ttl`（既定 900 秒）を運用の実行周期に合わせる。
- **冪等性**: 同一動画は `already_ingested` に写像され二度取り込まれない（冪等キー=`video_id`）。二回目の実行は `ingested=0`。

### 完全性ゲート（`--backfill`）

`--backfill` の全量性は正となるスナップショット（`--video-list`）を分母に固定して機械判定する:

```bash
python3 plugins/ubm-goal-setting/skills/run-ubm-youtube-ingest/scripts/check-youtube-backfill-completeness.py \
  --channels <handle> \
  --video-list <snapshot.json> \
  --registry plugins/ubm-goal-setting/knowledge/youtube-registry.json
```

`FULL_BACKFILL_PASS` は `ingested==discovered_total` かつ `temporary_failure==0` かつ `unapproved_unavailable==0`（終了コード 0）。除外による分母縮小・重複 ID・ページ送りの欠落・免除の参照の欠落は終了コード 1、使い方の誤り/入力不正は終了コード 2。

## グラフの検証（ナレッジ / harness の成果物）— v0.2.0

ナレッジの依存グラフの決定論再生成 + 検証:

```bash
python3 plugins/ubm-goal-setting/scripts/validate-knowledge-graph.py \
  --knowledge-dir plugins/ubm-goal-setting/knowledge \
  --graph-out plugins/ubm-goal-setting/knowledge/knowledge-graph.json
```

自己ループ禁止・`depends_on` の非循環・根拠≥1・確信度 0..1・`review_status` 必須を検査（終了コード 0=OK / 1=違反 / 2=使い方の誤り）。PASS 時のみ `knowledge-graph.json` を書く。宙に浮いた辺（端点のエントリ不在）だけは違反でなく縮退で、`knowledge-relations-quarantine.json` へ WARN 付きで自動退避し残辺で生成を継続する（「復旧」参照）。辺が 1 本も無い退化グラフ（`edges=0`）は終了コード 0 のまま標準エラー出力の WARN で表面化する。

### 辺の過去分の初回埋め戻し（既存のコーパスへの辺の初回適用）

C08（`knowledge-relation-extractor`）の発火点は取込の R3 / 同期の Phase5（いずれも差分駆動）のみのため、**既存のコーパスには辺が付かず `knowledge-relations.json` 不在（`edges=0` の退化グラフ）のまま**になる。初回は次の手順で過去分を埋め戻す:

1. `knowledge-relation-extractor` を `Task` で起動し、既存の全ナレッジのエントリから根拠付き辺候補 JSON（読み取り専用の出力）を得る。
2. 候補を一時ファイルへ書き出す（例: `eval-log/ubm-goal-setting/relations-candidate.json`）。
3. 候補の冪等な統合（`knowledge-relations.json` へ永続化）と `knowledge-graph.json` の再生成は同一コマンドで行う:

```bash
python3 plugins/ubm-goal-setting/scripts/validate-knowledge-graph.py \
  --knowledge-dir plugins/ubm-goal-setting/knowledge \
  --merge-relations <候補ファイル> \
  --graph-out plugins/ubm-goal-setting/knowledge/knowledge-graph.json
```

4. 標準出力の `OK: knowledge-graph validated (... edges=N ...)` で **`edges>0`** を確認する（標準エラー出力に `WARN: ... edges=0` が出る間は過去分の埋め戻しが未完了）。

統合は正規キー（`source_id`, `target_id`, `relation_type`）で冪等（先に書いたものを優先）のため、同じ候補での再実行は安全に不変となる。

### 辺レビューの昇格（`pending_review` → `approved`）

C08 由来の辺は `review_status: "pending_review"` で統合される。昇格の編集先は **`knowledge/knowledge-relations.json`（辺の永続ストア＝正本）** であり、`knowledge-graph.json`（派生・再生成で上書きされる）は直接編集しない。昇格基準:

- `evidence` の逐語が出典（`source_ref` が指すエントリ / ソース原文）と一致していること（要約・言い換えは不可）。
- 辺の向きが正しいこと（`depends_on` は依存する側→される側、`derived_from` は派生物→原典）。

昇格後は `validate-knowledge-graph.py` でグラフを再生成する。統合は先に書いたものを優先するため、`approved` 済みの状態が後続の同期の候補で上書きされることはない。コーパス増加時は全量再抽出でなく、**新規/変更エントリを起点にした増分抽出**（該当エントリのみを抽出エージェントへ渡す）を推奨する。

harness の成果物グラフの索引の生成と、読み取り専用の参照:

```bash
python3 plugins/ubm-goal-setting/scripts/index-harness-artifact-graph.py \
  --plan-glob "plugin-plans/ubm-goal-setting/*" \
  --plugin-root plugins/ubm-goal-setting \
  --out plugins/ubm-goal-setting/knowledge/harness-artifact-graph.json

python3 plugins/ubm-goal-setting/scripts/consult-harness-artifact-graph.py \
  --topic "youtube ingest 全量性" \
  --knowledge-graph plugins/ubm-goal-setting/knowledge/knowledge-graph.json \
  --harness-artifact-graph plugins/ubm-goal-setting/knowledge/harness-artifact-graph.json \
  --query-type local --depth 2
```

参照は該当0件も正常終了（終了コード 0）。`--knowledge-graph` は必須、`--harness-artifact-graph` は任意。**harness の成果物グラフだけ不在なら `--harness-artifact-graph` を省いてナレッジグラフだけの参照に落ち**、ナレッジグラフも不在のときだけ `run-ubm-consult` / `info-collector` は `router.json` のデュアルパスへ切り替える（代わりの手段の契約の正本＝`references/graph-consult-fallback-contract.md`）。

### harness の成果物グラフの再生成（定常手順・鮮度の基準）

`harness-artifact-graph.json`（C05）は「これから作る計画」と「実成果物」を突合した索引であり、**プラグインをビルド/レビューして実成果物（`task-state` / `route-report` / `build-trace` / 実在する `build_target`）が変わるたびに陳腐化する**。次のタイミングで `index-harness-artifact-graph.py` を再実行して再生成する:

- **ビルド / レビュー完了後**（コンポーネントの追加・状態遷移 `planned`→`built`→`verified` が起きたら必ず）。
- **参照前に鮮度確認**: 生成から時間が経っている場合は再生成してから参照する。目安の鮮度の基準は **7 日**（それより古い索引は `state`/`stale_reasons` が実態とずれている可能性があるため再生成推奨）。
- 再生成しない間は harness の成果物グラフを **省略してナレッジグラフだけで参照** しても良い（誤同定した古い索引を引くより安全）。C06 `knowledge-graph.json` はナレッジの実データが変わったとき再生成する。

```bash
# ビルド/レビュー後の再生成（再掲）
python3 plugins/ubm-goal-setting/scripts/index-harness-artifact-graph.py \
  --plan-glob "plugin-plans/ubm-goal-setting/*" \
  --plugin-root plugins/ubm-goal-setting \
  --out plugins/ubm-goal-setting/knowledge/harness-artifact-graph.json
```

## 受入の根拠

- C16: 週報/月報/期報を生成し、`validate-goal-output.py --type weekly|monthly|quarterly` が PASS すること。
- C17: 既知の更新済みソースで `NEW`/`MODIFIED` を検知し、`knowledge-extractor` が6カテゴリ分類と `router.json` / `registry.json` 同期を完了すること。
- C04: `UBM_VAULT_ROOT` 配下の許可外のパスへの `Write`/`Edit`/`MultiEdit` が終了コード 2 で阻止されること。

## 復旧

- `UBM_VAULT_ROOT` が未接続の場合、ナレッジ同期は 0件の報告として正常終了する。vault を接続して再実行する。
- `check-knowledge-split.py` が 500行超過を検知した場合、25エントリ基準でサブテーマを設計し、`{category}-{subtopic}.json` へ分割する。
- 目標設定出力が検証に失敗した場合、未展開 `{{...}}`、全角数字、差分の `+/-`、やらないこと3項目（月報・期報）、種別別必須見出し、逆算チェーン（C1〜C6: 売上貢献の式の明示と検算・実行完了型・突合・成果グループ見出しでの紐づけ）を優先して直す。
- (v0.2.0) `youtube-registry.json` 未存在時、1回きりの実行は `required-primary` + 保留中の第2ソースで自動初期化する（`--dry-run` は初期化も書込まない）。破損した登録簿は上書きしない（終了コード 1）ため、破損時はバックアップから復旧して再実行する。
- (v0.2.0) `--backfill` の完全性ゲートが終了コード 1 の場合、標準エラー出力の `pending` / `temporary_failure` / `unapproved_unavailable` / 免除の欠落 / 重複 ID / ページ送りの欠落 の動画 ID を確認し、除外で分母を縮めず取得を再試行する。承認済み除外は `waiver_ref` を付ける。
- (v0.2.0) `validate-knowledge-graph.py` が終了コード 1 の場合、標準エラー出力の違反（自己ループ / 根拠の欠落 / 確信度の範囲外 / `review_status` 欠落 / 循環）を確認し、C08（`knowledge-relation-extractor`）の辺の引き継ぎを修正して再生成する。`related` は無方向連想（循環の対象外）である点に注意する。
- (v0.2.0) 宙に浮いた辺（端点のエントリ不在）は終了コード 1 にならず、WARN 付きで `knowledge/knowledge-relations-quarantine.json` へ自動退避され `knowledge-relations.json` から除去された上で、残辺によりグラフの再生成が継続する（エントリ削除でグラフが恒久的に止まらない縮退）。**確認**: 隔離ファイルの `edges[]` を見る。**復旧**: 対象エントリを復活（または辺の端点の ID を実在するエントリへ修正）し、該当辺を隔離ファイルから `knowledge-relations.json` の `edges[]` へ戻して `validate-knowledge-graph.py` で再検証・再生成する。**破棄**: 辺自体が無効なら隔離ファイルから該当辺を削除する（隔離ファイルはグラフ生成に影響しない退避先のため放置しても機能劣化はないが、棚卸しで空に保つ）。

## 共通の入力と検証の正本

- Task のルート入力と停止条件: `references/agent-root-contract.md`。
- 共通アンカーの初回固定・全周回の記録・完了前の検証: `references/goal-seek-anchor-contract.md`。
- 目標の下書き/同じ期の peer 選択と保存前後のゲート: `skills/run-ubm-goal-setting/references/validation-gates.md`。
- YouTube の source_out/dest_root は正規化ソースの親ルート。出力時に YouTube/ を1回だけ付加する。
- --since は指定日より後の同一ハッシュも再処理する追加条件。差分は日付に関係なく対象。
- 日次ジャーナルは下書き検証→Daily保存→再検証。相談の誘導は既定非永続、記録希望時だけ保存同意を確認。
