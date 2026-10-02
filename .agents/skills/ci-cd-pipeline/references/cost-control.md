# GitHub Actions にお金をかけない

## 1. まず、そもそも課金されるのか

| リポジトリ | Actions の料金 |
|---|---|
| **public** | **完全無料・無制限**。ここで悩む必要はない |
| private / Free プラン | 2,000 分/月 |
| private / Team | 3,000 分/月 |
| private / Enterprise | 50,000 分/月 |

無料枠は毎月1日にリセットされる。使い切っても請求は発生しない（支払い方法を登録していなければ、単にワークフローが動かなくなるだけ）。**最初に支払い方法を登録しないでおく**のが、意図しない課金を防ぐいちばん確実な方法。

## 2. 分の数え方（ここを間違えると倍払う）

課金されるのは**実行時間 × OS の倍率**。

| ランナー | 倍率 | 10分の実行で消費する分 |
|---|---|---|
| ubuntu-latest | 1倍 | 10分 |
| windows-latest | 2倍 | 20分 |
| macos-latest | **10倍** | **100分** |

さらに **1回の実行あたり切り上げ**。30秒のジョブでも1分として数えられる。

ここから2つの結論が出る。

- **ubuntu 以外を理由なく使わない**。macOS は iOS ビルドなど本当に必要なときだけ。
- **ジョブを細かく分けない**。3つのジョブに分けると、チェックアウトと依存関係のインストールを3回払い、切り上げも3回発生する。並列で速くはなるが、消費分は増える。

## 3. 削減手法（効く順）

### 3.1 concurrency で古い実行を打ち切る

```yaml
concurrency:
  group: ci-${{ github.ref }}
  cancel-in-progress: true
```

同じブランチに続けて push したとき、走っている古い実行を止める。連続 push が多いほど効く。**いちばん費用対効果が高い**。

ただし deploy と migrate には `cancel-in-progress: true` を付けないこと。デプロイの途中で打ち切られると、中途半端な状態が残る。

### 3.2 キャッシュを使う

```yaml
- uses: actions/setup-node@v7
  with:
    node-version: 20
    cache: ${{ steps.pm.outputs.name }}   # npm / yarn / pnpm のいずれか
```

インストールが毎回ネットワークから全部落とすのを防ぐ。依存関係の量にもよるが、1回あたり30秒〜1分縮む。キャッシュ自体の保存容量は10GBまで無料。

pnpm を使う場合だけ、`setup-node` **より前に** `pnpm/action-setup@v6` を置くこと。順番が逆だと `cache: pnpm` が「pnpm が見つからない」で落ちる。この順序は共通Composite Action（`assets/detect-pm.yml`）が一元管理するため、各workflowへ同じ処理を複製しない。

### 3.3 paths-ignore で無駄な起動を止める

```yaml
on:
  push:
    branches: [main]
    paths-ignore:
      - "**.md"
      - "docs/**"
      - ".github/ISSUE_TEMPLATE/**"
```

ドキュメントだけ直したときに CI を回さない。

**注意**: `paths-ignore` を必須チェック（branch protection の required status checks）に指定したワークフローに付けると、条件に合致しない PR で「チェックが永遠に完了しない」状態になり、マージできなくなる。必須にするワークフローには付けないこと。

### 3.4 CI で重いビルドをしない

`opennextjs-cloudflare build` は数分かかる。CI で通しても、deploy.yml がもう一度ビルドするので二重に払うだけで、追加で分かることは少ない。型チェックとテストで足りる。

### 3.5 timeout-minutes は「節約」ではなく「安全弁」

```yaml
timeout-minutes: 10
```

これは短くすれば安くなるものではない。**無限ループやハングしたジョブが6時間（既定値）走り続けて無料枠を丸ごと溶かす**のを防ぐためのもの。通常の実行時間の2〜3倍を設定する。短すぎると正常なジョブが落ちて、原因を探す時間のほうが高くつく。

### 3.6 self-hosted ランナーは慎重に

自分のマシンをランナーにすれば Actions の分は消費しない。ただし **public リポジトリでの self-hosted ランナーは危険**。fork から PR を送るだけで任意のコードを自分のマシンで実行させられる。public では使わない。

### 3.7 使っていないワークフローを消す

`schedule`（定期実行）を仕掛けたまま忘れると、誰も見ていない間に毎日消費し続ける。定期実行は原則入れない。

## 4. やらないほうがいいこと

| やりたくなること | なぜダメか |
|---|---|
| matrix で Node 18/20/22 を並べる | 実行数がそのまま3倍。動かす環境が1つなら1つでよい |
| larger runner（4-core 以上） | 倍率が上がる。無料枠の対象外 |
| ジョブを並列に分けて速くする | 速くはなるが消費分は増える。無料枠が目的なら逆効果 |
| GitHub Actions と Cloudflare Workers Builds を両方有効にする | **同じコミットで2回デプロイが走る**。無駄なだけでなく、どちらが最後に反映されたか分からなくなる。どちらか一方に決める |

## 5. 使用量の確認方法

`Settings → Billing and plans → Plans and usage` の Actions 欄。private リポジトリなら月初に一度見ておく。

コマンドでも取れる。

```bash
gh api "repos/$GITHUB_REPOSITORY/actions/workflows" --jq '.workflows[] | "\(.name)\t\(.state)\t\(.path)"'
```

止め忘れたワークフローがないかの確認に使う。
