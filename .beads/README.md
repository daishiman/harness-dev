# Beads — AI ネイティブなイシュートラッキング

Beads へようこそ。このリポジトリはイシュートラッキングに **Beads** を使います。Beads は、コードと同じリポジトリの中で完結するよう設計された、モダンで AI ネイティブなツールです。

## Beads とは

Beads はリポジトリの中に住むイシュートラッカーで、AI コーディングエージェントや、イシューをコードの近くに置きたい開発者に最適です。Web UI は不要で、すべて CLI で完結し、git とシームレスに統合されます。

**詳細:** [github.com/steveyegge/beads](https://github.com/steveyegge/beads)

## クイックスタート

### 基本コマンド

```bash
# 新しいイシューを作成
bd create "ユーザー認証を追加する"

# イシュー一覧を表示
bd list

# イシューの詳細を表示
bd show <issue-id>

# イシューのステータスを更新
bd update <issue-id> --claim
bd update <issue-id> --status done

# Dolt リモートと同期
bd dolt push
```

### イシューの扱い方

Beads のイシューは次の性質を持ちます:
- **git ネイティブ**: Dolt データベースに保存され、バージョン管理とブランチが効く
- **AI フレンドリー**: CLI ファースト設計で AI コーディングエージェントと相性が良い
- **ブランチ対応**: ブランチのワークフローに追従できる
- **同期対応**: Dolt リモートでバックアップ・チーム共有ができる

## なぜ Beads か

✨ **AI ネイティブ設計**
- AI 支援開発のワークフローを前提に設計されている
- CLI ファーストのインターフェースで AI コーディングエージェントとシームレスに動く
- Web UI への文脈切り替えが不要

🚀 **開発者フォーカス**
- イシューがコードのすぐ隣、リポジトリの中に住む
- オフラインで動き、push 時に同期される
- 高速・軽量で作業の邪魔をしない

🔧 **git 統合**
- `bd dolt push` / `bd dolt pull` による Dolt ネイティブ同期
- ブランチ対応のイシュートラッキング
- Dolt ネイティブの three-way マージ解決

## Beads を始める

自分のプロジェクトで試すには:

```bash
# Beads をインストール
curl -sSL https://raw.githubusercontent.com/steveyegge/beads/main/scripts/install.sh | bash

# リポジトリで初期化
bd init

# 最初のイシューを作成
bd create "Beads を試す"
```

## 実行看板 (board) の起動方法

beads 束縛タスク (`tracker_binding=beads`) を「今どのタスクに着手するか」の観点で見る表示手段を **board** と呼びます。どの board を使うかは repo-config の `execution_tracker.beads.board` で 1 つ選びます。**どの board も完了 authority を持ちません**（完了の事実は「default branch を target にした linked PR が `merged=true`」だけです）。設計の正本は `plugins/dev-graph/references/execution-tracker-contract.md` の **§9** です。

| `board` 値 | 実体 | server モード | live 操作 | 用途 |
|---|---|---|---|---|
| `beads-kanban` | [doublej/beads-kanban](https://github.com/doublej/beads-kanban) | **必須** (`true`) | あり (drag) | live 操作・並べ替え・agent pane |
| `static-render` | dev-graph C05 `render-graph-html` | 不要 (embedded 可) | なし | 6 種 artifact 全体のゼロ依存スナップショット |
| `omb-board` | [oh-my-beads](https://github.com/AI-Driven-R-D-Dept/oh-my-beads) 同梱 board | 不要 (embedded 可) | あり (軽量) | 軽量 board |
| `none` | — | — | — | 看板を使わない |

> このリポジトリは現在 **embedded (`bd info` で `Mode: direct`)** です。`beads-kanban` だけが server モードを要求し、それ以外は embedded のまま使えます。

### A. beads-kanban (live 実行看板) — server モード必須

「タスクカードを手でドラッグして並べ替えたい」場合の live 看板です。

**前提: server モードが必須。** beads-kanban は `bd sql --json` で DB を読むため、bd を server モードで動かす必要があります。**embedded (direct) モードでは `bd sql` が使えません**:

```bash
bd info    # "Mode: direct" と出れば embedded → 看板を使うには server へ切替が必要
```

**起動手順:**

```bash
# 1. bd を server モードで (再)初期化して bd sql を露出させる
#    ※ これは再初期化操作です。data-safety ガードは `bd help init-safety` を参照。
#    接続先を変える場合は --server-host / --server-port / --server-user、
#    パスワードは BEADS_DOLT_PASSWORD 環境変数で渡す。
bd init --server

# 2. server の状態確認・明示起動 (lifecycle は bd dolt が管理)
bd dolt status        # 稼働確認
bd dolt start         # 明示起動 (必要時のみ・通常は自動起動)

# 3. bd sql が通ることを確認してから看板を起動 (外部依存・npx で都度取得)
bd sql --json "SELECT 1"
npx github:doublej/beads-kanban <repo-path>   # <repo-path> の指定は上流 README に従う

# 4. 表示された localhost の URL をブラウザで開く
```

- beads-kanban はソースを本リポジトリへ同梱・fork せず、`npx` で取得する **交換可能な外部依存**として扱います。
- 看板でのカード drag は `bd update --status` 相当の手動編集です。自動化 (PR close→task close カスケード) は看板を経由せず **bd CLI (C28 bridge) を直接**叩くため、看板の停止・オフラインは完了収束に影響しません (§9.3)。
- **運用注意 (LICENSE)**: beads-kanban は現時点で LICENSE ファイルを持たず、既定で全権利留保です。業務・再配布利用の前に上流ライセンスを確認してください。

### B. static-render (C05 render-graph-html) — ゼロ依存の静的スナップショット

外部依存も server も不要で、6 種 artifact 全体 (issues / tasks / specs / architecture / features / docs) の俯瞰スナップショットを 1 枚の自己完結 HTML (SVG + inline JS) として出力します。embedded のまま使えるため、**このリポジトリで今すぐ使える board はこれです**。

**起動手順 (推奨: dev-graph の skill 経由):**

```bash
# skill から実行 (既定出力先: .dev-graph/render/index.html)
/run-dev-graph-render --repo-root . --output .dev-graph/render/index.html

# もしくはスクリプトを直接実行
python3 plugins/dev-graph/scripts/render-graph-html.py --repo-root . --output .dev-graph/render/index.html

# 出力された HTML をブラウザで開く (localhost サーバ不要・ファイルを直接開ける)
open .dev-graph/render/index.html
```

- 出力は外部 CDN・追加 npm 依存を持たない単一 HTML/CSS/SVG です。リポジトリへコミットしても CI で生成しても成立します。
- live 操作 (手でのドラッグ) はできません。あくまで「その時点の全体像」を写したスナップショットです。
- graph は read-only で、HTML 以外の graph / content は変更しません。

### C. omb-board (oh-my-beads) — 軽量 board (embedded 可)

server モード不要の軽量な live board が欲しい場合の第三の選択肢です。oh-my-beads を導入し、同梱の board を起動します。**具体的な起動コマンドは上流 [oh-my-beads](https://github.com/AI-Driven-R-D-Dept/oh-my-beads) の README に従ってください** (embedded モードのままで動きます)。dev-graph はソースを同梱せず、交換可能な外部依存として扱います。

### D. none — 看板を使わない

`bd ready` / `bd list` などの CLI だけで運用し、board を使わない構成です。

### このリポジトリの看板方針

現状の既定方針は **`static-render`** です。理由:

- このリポジトリは embedded (`Mode: direct`)・ソロ + AI エージェント開発の private worktree であり、server 常駐や外部 npx 依存を持ち込まずゼロ依存で全体像を俯瞰できる `static-render` が最も摩擦が少ないため。
- カードを手でドラッグしながら回す live 操作が必要になった時点で `beads-kanban` へ切り替えます (その際は `bd init --server` による server モード再初期化と、上流 LICENSE の確認が前提)。
- いずれに切り替えても完了 authority は「PR `merged=true`」のままで変わりません (board は表示・操作層に過ぎません)。

## さらに詳しく

- **ドキュメント**: [github.com/steveyegge/beads/docs](https://github.com/steveyegge/beads/tree/main/docs)
- **クイックスタートガイド**: `bd quickstart` を実行
- **サンプル**: [github.com/steveyegge/beads/examples](https://github.com/steveyegge/beads/tree/main/examples)

---

*Beads: 思考の速度で動くイシュートラッキング* ⚡
