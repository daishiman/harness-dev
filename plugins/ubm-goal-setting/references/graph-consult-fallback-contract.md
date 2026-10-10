# `graph-consult-fallback-contract.md` — グラフ参照のフォールバック契約（正本）

`consult-harness-artifact-graph.py`（C07）を読み取り専用で引く全利用側が従う **穏当な代わりの手段への切り替えの唯一の正本**。
以前は `info-collector`（C05 エージェント）/ R3-frame-consult プロンプト / `consult-frames.md` / README / `run-ubm-consult` の SKILL.md の
5 箇所に散文で重複し（「いずれか不在なら飛ばす」対「不在/終了コード 2 のとき飛ばす」）表現が揺れていた。本ファイルへ一本化し、
各所は 1 行参照＋最小要約に置換する。

## 利用側

- `agents/info-collector.md` Step 3-E（目標設定 Phase1-2-collect のデュアルパス追加経路）
- `skills/run-ubm-consult/prompts/R3-frame-consult.md`（相談のフレーム出典裏取り）
- `skills/run-ubm-consult/references/consult-frames.md`（出典の引き方）
- `skills/run-ubm-consult/SKILL.md`（`## 守ること`／`## つまずきやすい点`）
- `README.md`（相談・デュアルグラフ節）

## 契約（決定論・4 状態）

C07 は **ナレッジグラフ必須 / harness の成果物グラフ任意** で、利用側は結果を次の 4 状態に写像する。

| 状態 | 条件 | 挙動 |
|---|---|---|
| **参照の実行** | `knowledge-graph.json` が存在し健全 | C07 を実行し、ヒットをルーターのデュアルパスの結果に併合する。`harness-artifact-graph.json` があれば `--harness-artifact-graph` に渡して併用し、無ければ渡さない。 |
| **harness の成果物グラフだけ不在 → ナレッジ単独の参照** | ナレッジグラフは存在するが `harness-artifact-graph.json` が不在 | `--harness-artifact-graph` を **省略**して C07 を実行する（harness の成果物グラフは運用生成物ゆえ不在があり得る）。C07 は harness の成果物グラフを空扱いにしナレッジ単独で参照する。出力 `sources.harness_artifact_graph.status == "absent"`。**飛ばさない**。 |
| **ナレッジグラフ不在 → 飛ばす** | `knowledge-graph.json` が不在 | C07 を呼ばず飛ばし、`router.json` → `knowledge/*.json` の Read デュアルパス（既存経路）だけで続行する。 |
| **破損 → WARN して飛ばす** | いずれかのグラフが壊れている（スキーマ不正・端点の無い辺・JSON 解析不能）＝ C07 が **終了コード 2** | 「不在」と区別し WARN を残して飛ばし、ルーターのデュアルパスへ切り替える。終了コード 2 は使い方の誤り/入力不正・壊れた索引を意味する。 |

- **ヒット0件は正常**: トピック不一致による空のヒット（終了コード 0・`zero_hit=true`）は飛ばすのでも WARN でもなく正常結果。ルーターのデュアルパスの結果があればそれを使い、両方ヒット0件なら `consult_evidence` にその旨を記す。
- **`edges=0`（退化グラフ）もヒット0件と同じく正常扱い**: ナレッジグラフに辺が 1 本も無い場合も終了コード 0 の正常系だが、C07 は出力 `warnings[]` に `"graph-edges-empty"` を記録し、利用側は `consult_evidence.warnings` へそのまま転記する（初回の辺の過去分の埋め戻しが未実施であるシグナル。手順はプラグイン直下 RUNBOOK の「辺の過去分の初回埋め戻し」）。
- **不明なら通す（fail-open）のではない**: ナレッジグラフ不在で飛ばすのは「グラフ経路を諦めて既存の Read デュアルパスへ落ちる」だけであり、目標設定・相談の本体機能は `router.json` + `knowledge/*.json` で常に成立する（グラフは既存に足すだけの補完経路）。
- **パストラバーサル（上位ディレクトリへの抜け出し）のガード**: グラフのパスは親スキルが解決し、`references/agent-root-contract.md` に従って検証した `PLUGIN_ROOT` 基点の絶対パスで渡す。Read/Bash の引数には展開済みの絶対パスを使い、未設定の環境変数から推測しない。パスに `..` を含めない（含むと終了コード 2）。

## 終了コードの写像（正本）

| C07 の終了コード | 意味 | 利用側の扱い |
|---|---|---|
| 0 | 正常（ヒット0件を含む） | ヒットを採用（空ならルーターのデュアルパスのみ） |
| 2 | 使い方の誤り・入力不正・壊れた索引（`broken index`） | 破損とみなし WARN して飛ばす → ルーターのデュアルパス |

`--harness-artifact-graph` の **省略は終了コード 0**（使い方の誤りではない）。ナレッジグラフの引数の欠落は終了コード 2。

## 非後退

- 本契約は既存の機能 A（目標設定 公式21ブロック）/ B（`knowledge-sync` 6 カテゴリ）の成果物・ナレッジ実データを変更しない（既存に足すだけ）。
- グラフ実ファイル（`knowledge-graph.json` / `harness-artifact-graph.json`）の**正は運用時再生成**（`validate-knowledge-graph.py`（C06）/ `index-harness-artifact-graph.py`（C05）の実行）であり、git には同梱しない（再生成可能な派生スナップショットのため `.gitignore` で誤コミットを遮断済み）。`knowledge/*.json` の変更後は再生成して鮮度を保つ。なお辺の永続ストア `knowledge-relations.json`（レビュー昇格の編集先=正本）は派生でないため追跡対象。
