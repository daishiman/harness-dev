# graph-consult-fallback-contract.md — グラフ consult フォールバック契約（正本）

`consult-harness-artifact-graph.py`（C07）を read-only で引く全 consumer が従う **graceful fallback の唯一の正本**。
以前は info-collector（C05 agent）/ R3-frame-consult prompt / consult-frames.md / README / run-ubm-consult SKILL.md の
5 箇所に散文で重複し（「いずれか不在なら skip」vs「不在/exit2 のとき skip」）表現が揺れていた。本ファイルへ一本化し、
各所は 1 行参照＋最小要約に置換する。

## consumer

- `agents/info-collector.md` Step 3-E（目標設定 Phase1-2-collect のデュアルパス追加経路）
- `skills/run-ubm-consult/prompts/R3-frame-consult.md`（相談のフレーム出典裏取り）
- `skills/run-ubm-consult/references/consult-frames.md`（出典の引き方）
- `skills/run-ubm-consult/SKILL.md`（Key Rules / Gotchas）
- `README.md`（相談・デュアルグラフ節）

## 契約（決定論・4 状態）

C07 は **knowledge graph 必須 / harness artifact graph 任意** で、consumer は結果を次の 4 状態に写像する。

| 状態 | 条件 | 挙動 |
|---|---|---|
| **consult 実行** | `knowledge-graph.json` が存在し健全 | C07 を実行し、hit を router デュアルパスの結果に併合する。`harness-artifact-graph.json` があれば `--harness-artifact-graph` に渡して併用し、無ければ渡さない。 |
| **harness 単独不在 → knowledge 単独 consult** | knowledge graph は存在するが `harness-artifact-graph.json` が不在 | `--harness-artifact-graph` を **省略**して C07 を実行する（harness graph は運用生成物ゆえ不在があり得る）。C07 は harness を空扱いにし knowledge 単独で consult する。出力 `sources.harness_artifact_graph.status == "absent"`。**skip しない**。 |
| **knowledge 不在 → skip** | `knowledge-graph.json` が不在 | C07 を呼ばず skip し、`router.json` → `knowledge/*.json` の Read デュアルパス（既存経路）だけで続行する。 |
| **破損 → WARN して skip** | いずれかのグラフが壊れている（スキーマ不正・dangling・JSON 解析不能）＝ C07 が **exit 2** | 「不在」と区別し WARN を残して skip し、router デュアルパスへ fallback する。exit2 は usage/入力不正・壊れた index を意味する。 |

- **zero-hit は正常**: topic 不一致による空 hit（exit 0・`zero_hit=true`）は skip でも WARN でもなく正常結果。router デュアルパスの結果があればそれを使い、両方 zero-hit なら consult_evidence にその旨を記す。
- **edges=0（退化グラフ）も zero-hit 正常扱い**: knowledge graph に辺が 1 本も無い場合も exit 0 の正常系だが、C07 は出力 `warnings[]` に `"graph-edges-empty"` を記録し、consumer は `consult_evidence.warnings` へそのまま転記する（初回 edge backfill 未実施のシグナル。手順は plugin 直下 RUNBOOK の「初回 edge backfill」）。
- **fail-open ではない**: knowledge 不在の skip は「グラフ経路を諦めて既存の Read デュアルパスへ落ちる」だけであり、目標設定・相談の本体機能は router.json + `knowledge/*.json` で常に成立する（グラフは additive な補完経路）。
- **path traversal ガード**: グラフパスは `$CLAUDE_PLUGIN_ROOT` 基点の絶対パスで渡し `..` を含めない（含むと exit2）。

## exit コードの写像（正本）

| C07 exit | 意味 | consumer の扱い |
|---|---|---|
| 0 | 正常（zero-hit 含む） | hit を採用（空なら router デュアルパスのみ） |
| 2 | usage・入力不正・壊れた index（broken index） | 破損とみなし WARN して skip → router デュアルパス |

`--harness-artifact-graph` の **省略は exit0**（usage エラーではない）。knowledge graph 引数の欠落は exit2。

## 非後退

- 本契約は既存 capability A（目標設定 21 項目）/ B（knowledge-sync 6 カテゴリ）の成果物・knowledge 実データを変更しない（additive）。
- グラフ実ファイル（`knowledge-graph.json` / `harness-artifact-graph.json`）の**正は運用時再生成**（`validate-knowledge-graph.py`（C06）/ `index-harness-artifact-graph.py`（C05）の実行）であり、git には同梱しない（再生成可能な派生 snapshot のため .gitignore で誤コミットを遮断済み）。`knowledge/*.json` の変更後は再生成して鮮度を保つ。なお辺の永続ストア `knowledge-relations.json`（レビュー昇格の編集先=正本）は派生でないため追跡対象。
