# task-progress (live 実行状態・派生ビュー)

> `project-task-status.py` 生成の派生ビュー。構造の正本は `task-graph.json`、状態の正本は build dir の `task-state.json`。手書き編集しない (再生成で上書き)。build 異常終了時は最後の 投影時点のスナップショットで stale の可能性がある (最新は再投影で得る)。

- 凡例: ✓=done / ▶=running / ✗=blocked / ☐=pending / ⏳=未処理の発見タスク (外ループ待ち)
- 完了率: **0%** (0/51)
- 状態内訳: done=0 / running=0 / blocked=0 / pending=51
- route-report 数: 0

## このタスクの目的と、導入で得られる価値

### やさしい説明 (どなたでも)
- **これは何をするもの?**: 開発の『やりたいこと』から個々の作業までを 1 枚のタスク地図 (グラフ) で一元管理し、『次に何をやるべきか』『どれを同時に進められるか』『どこまで終わったか』を自動で示してくれる開発の司令塔ツールです。手元のメモ (Markdown) を正本にしつつ、Beads や GitHub とも重複なくつながります。
- **どんな困りごとを解決する?**: 複数の管理場所 (手元のメモ・Beads・GitHub) を全部『正しい』としてやり取りすると、同じ課題が二重に登録されたり、『終わった/終わってない』が食い違ったりします。dev-graph は『手元の地図だけを正本』と決め、他はそこから一方向に写すだけにすることで、この食い違いを起きなくします。
- **導入すると何がうれしい?**:
  - 「やりたいこと」を機能のまとまりに分け、依存関係つきで見える化できる
  - 「次にやるべき作業」を自動でおすすめしてくれる
  - 同時に進めても衝突しない作業を見つけて、並行作業を後押ししてくれる
  - 作業の完了を『PR がマージされた事実』だけで自動判定するので、完了の付け忘れが減る
  - 進み具合を、追加インストール不要でブラウザで開けるレポートとして見られる

### 技術的な詳細 (エンジニア向け)
- **本質的な問題・課題**: 複数の実行トラッカー (ローカル Markdown・Beads・GitHub Issues/Projects) を同時に正本扱いすると、二重起票・完了 authority の競合・並列作業の衝突が構造的に不可避になる。dev-graph はこれを『ローカル graph を唯一の正本／トラッカーは node 単位の一方向 projection／default branch へ merge された linked PR だけを完了事実 authority』とする非対称な権威設計で解く。さらに計画粒度を macro (feature 間依存のオーケストレーション) と micro (1 feature = P01..P13 の exact 13 タスク) の二層に分離し、粒度違いの計画と実行の混線を防ぐ。結果として『同期対象を増やすほど品質が下がる』多重 authority のアンチパターンを構造的に封じている。
- **導入すると何ができるようになるか**:
  - 自然文の構想を feature graph へ macro 分解し、機能間 depends_on つきで一元管理できる
  - 各 feature を system-dev-planner で exact-13 タスク仕様書へ細分解し、feature 配下へ all-or-none 登録できる
  - 依存 × 完了状態から ready-set (次に着手すべきタスク) を決定論的に算出・提示できる
  - リソーススコープ (touches) 重複を避けた並列バッチを識別し、複数 worktree の lease で作業衝突なく並行実行できる
  - node ごとに Beads か GitHub を単一 publication authority として重複なく投影できる
  - remote ancestor 確認済み PR merge を完了トリガーに、hook/scheduled reconciliation で eventual に完了収束できる
  - 追加ランタイム依存ゼロの静的 HTML (SVG + inline JS) でタスクグラフを可視化できる
  - issue/task/spec/architecture/doc を人間可読 Markdown のディレクトリ配置 + 差分更新 + schema 検証つきで安全に直接編集できる
- **責務境界・非目標**:
  - 実装コードは生成せず、管理 + 要件定義までを担い、実装は capability-build / task-graph build へ委譲する
  - 1 feature の exact-13 タスク仕様書生成は system-dev-planner (ミクロ層) へ委譲し、dev-graph はマクロ層に徹する
  - 仕様書・アーキテクチャの内容生成は system-spec-harness を引用し複製しない
  - task node ごとに Beads または GitHub を単一 authority とし双方向同期しない (Projects Status は local_to_project 一方向)
  - 完了 authority は PR merge のみとし、GitHub Projects の Done automation や Claude hook は fast path であって唯一の正本にしない
- **目的 (何をするか)**:
  - 構想・イシュー・仕様・アーキテクチャ・機能を 1 つのタスクグラフで第一級に一元管理する
  - 機能を macro 分解し、1 機能 = 13 タスクの細分解は system-dev-planner (ミクロ層) へ委譲する
  - 各タスクを Beads または GitHub の単一トラッカーへ重複なく投影する
  - 要件定義 → 実装 handoff → 次タスク推薦 → 複数 worktree 並列実行 → PR merge 後の完了収束までを担う
- **背景・前提**:
  - ローカル仕様・Beads・GitHub を無条件に双方向同期すると、二重起票と完了 authority 競合が生じる
  - そこで Markdown/graph をローカル正本、Beads か GitHub を node 単位の一方向 projection、GitHub Projects を人間向け表示に役割分担する
  - 完了事実は default branch へ merge された linked PR だけを authority とする
  - 実装コード生成は既存の capability-build / task-graph build へ委譲する
- **到達状態 (Goal)**: dev-graph の 13 phase ファイル + index + component-inventory + handoff が決定論ゲートで検証可能な状態になっている

## タスクの依存関係 (何が何に依存して進むか)
> 全 51 タスク・192 依存エッジ。各フェーズの詳細は下記チェックリスト、完全な関係は HTML レポートを参照。
- 起点タスク (依存なしで最初に着手可能): `D01`

## P01
> 🎯 何のため: 何を作るか — 要件と作業方針を固める
- ☐ `D01` 要件とhybrid directory policyを確定する
- ☐ `P01` requirements

## P02
> 🎯 何のため: どう作るか — 構成・データ・依存を設計する
- ☐ `D02` component・schema・routing設計を確定する
- ☐ `P02` design

## P03
> 🎯 何のため: 設計を独立レビューで検証する
- ☐ `D03` 独立設計レビュー契約を確定する
- ☐ `P03` design-review

## P04
> 🎯 何のため: 検証方法 (テスト) を先に設計する
- ☐ `D04` 後段buildのテスト設計を確定する
- ☐ `P04` test-design

## P05
> 🎯 何のため: 各部品を実際に作る (実装)
- ☐ `B-C01` run-dev-graph-init の後段build routeを実行可能にする
- ☐ `B-C02` run-dev-graph-node の後段build routeを実行可能にする
- ☐ `B-C03` run-dev-graph-sync の後段build routeを実行可能にする
- ☐ `B-C04` run-dev-graph-requirements の後段build routeを実行可能にする
- ☐ `B-C05` run-dev-graph-render の後段build routeを実行可能にする
- ☐ `B-C06` dev-graph-integrity-auditor の後段build routeを実行可能にする
- ☐ `B-C07` dev-graph-sync-conflict-verifier の後段build routeを実行可能にする
- ☐ `B-C08` dev-graph-requirements-verifier の後段build routeを実行可能にする
- ☐ `B-C09` dev-graph の後段build routeを実行可能にする
- ☐ `B-C10` guard-graph-schema の後段build routeを実行可能にする
- ☐ `B-C11` validate-graph-schema.py の後段build routeを実行可能にする
- ☐ `B-C12` gh-bridge.py の後段build routeを実行可能にする
- ☐ `B-C13` render-graph-html.py の後段build routeを実行可能にする
- ☐ `B-C14` run-dev-graph-decompose の後段build routeを実行可能にする
- ☐ `B-C15` run-dev-graph-schedule の後段build routeを実行可能にする
- ☐ `B-C16` schedule-graph.py の後段build routeを実行可能にする
- ☐ `B-C17` dev-graph-parallel-safety-verifier の後段build routeを実行可能にする
- ☐ `B-C18` run-dev-graph-status の後段build routeを実行可能にする
- ☐ `B-C19` system-spec-harness連携routeを実行可能にする
- ☐ `B-C24` resolve-repo-context.py routeを実行可能にする
- ☐ `B-C25` reconcile-task-lifecycle hook routeを実行可能にする
- ☐ `B-C26` reconcile-github-lifecycle.py routeを実行可能にする
- ☐ `B-C27` manage-worktree-lease.py routeを実行可能にする
- ☐ `B-C28` bd-bridge.py routeを実行可能にする
- ☐ `B-C29` register-package.py を first-class script component として登録・検証網へ組込む
- ☐ `D14` dev-graph runtime意味契約とcriteria-test証跡を修復する
- ☐ `P05` implementation

## P06
> 🎯 何のため: 作った部品を動かして検証する
- ☐ `D06` 後段buildのharness検証契約を確定する
- ☐ `P06` test-run

## P07
> 🎯 何のため: 合格ライン (受け入れ基準) を定める
- ☐ `D07` purpose由来AC matrixを確定する
- ☐ `P07` acceptance-criteria

## P08
> 🎯 何のため: 重複を整理し保守しやすくする
- ☐ `D08` SSOT refactoring契約を確定する
- ☐ `P08` refactoring

## P09
> 🎯 何のため: 全体の品質ゲートを通す
- ☐ `D09` plan-scoped QA gateを実行する
- ☐ `P09` quality-assurance

## P10
> 🎯 何のため: 最終レビューで仕上がりを確認する
- ☐ `D10` 独立final reviewを実行する
- ☐ `P10` final-review

## P11
> 🎯 何のため: 検証した証拠を残す
- ☐ `D11` L3 evidenceとL4 pending evidenceを分離する
- ☐ `P11` evidence

## P12
> 🎯 何のため: 使い方・導入手順を文書化する
- ☐ `D12` README/setup文書契約を確定する
- ☐ `P12` documentation

## P13
> 🎯 何のため: リリースしてよいか判定する
- ☐ `D13` plan release判定を確定する
- ☐ `P13` release

