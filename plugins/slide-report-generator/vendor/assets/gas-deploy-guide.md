# GASデプロイ手順

## 概要

生成したHTMLプレゼンテーションをGoogle Apps Script (GAS) を使用してウェブアプリとして公開する手順。

---

## 1. Google Apps Script プロジェクト作成

1. [Google Drive](https://drive.google.com) を開く
2. 「新規」→「その他」→「Google Apps Script」をクリック
3. プロジェクト名を設定（例：「MyPresentation」）

---

## 2. コード設定

### 2.1 コード.gs の設定

`コード.gs` に以下を貼り付け：

```javascript
function doGet() {
  return HtmlService.createHtmlOutputFromFile('index')
    .setTitle('プレゼンテーション')
    .setXFrameOptionsMode(HtmlService.XFrameOptionsMode.ALLOWALL)
    .addMetaTag('viewport', 'width=device-width, initial-scale=1');
}
```

### 2.2 HTMLファイルの作成

1. 左側のファイル一覧で「+」をクリック
2. 「HTML」を選択
3. ファイル名を `index` に設定（.html は自動付与）
4. 生成されたHTMLコードをすべて貼り付け

---

## 3. デプロイ

### 3.1 新しいデプロイの作成

1. 右上の「デプロイ」ボタンをクリック
2. 「新しいデプロイ」を選択
3. 歯車アイコンをクリック
4. 「ウェブアプリ」を選択

### 3.2 デプロイ設定

| 設定項目 | 値 |
|----------|-----|
| 説明 | 任意（例：「プレゼン v1.0」） |
| 次のユーザーとして実行 | 「自分」 |
| アクセスできるユーザー | 「全員」 |

### 3.3 デプロイ実行

1. 「デプロイ」ボタンをクリック
2. 初回は承認が必要
   - 「アクセスを承認」をクリック
   - Googleアカウントでログイン
   - 「詳細」→「〇〇（安全ではないページ）に移動」
   - 「許可」をクリック
3. 表示されたURLをコピー

---

## 4. 画像の扱い

### 4.1 警告：相対パス画像はGASで表示されない

GASは単一HTMLファイルしか配信できず、`<img src="assets/generated/...">` のような相対パス画像はGAS環境に存在しないため、手順通りに貼ると**全画像がbrokenになる**。画像を含むデッキは、必ず下記いずれかの方式で処理してからGASに貼ること。

### 4.2 方式の自動判定

まず画像マニフェストを生成し、サイズレポートで方式を判定する。

```bash
node scripts/build-image-manifest.js <slide-dir>
```

- 画像合計が約340KB以下（おおむね2〜3枚）→ **方式A（base64自己完結）が利用可能**
- 約340KB超 → **方式B（外部URL参照）が必須**

base64は実バイトの約1.37倍に膨張する。WebP1枚平均約184KBはbase64化後で約252KBになるため、500KB上限では2枚程度が限界。全面画像デッキ（数十枚規模）は方式B一択となる。

### 4.3 方式A：base64自己完結（軽量デッキ・合計約340KB以下）

画像をbase64でHTMLに埋め込み、外部依存ゼロの単一HTMLを生成する。

```bash
node scripts/build-single-html.js <slide-dir> --inline-images --full-image-deck --output=index.deploy.html
```

- 生成された `index.deploy.html` を `index` としてGASに貼る（§2.2の手順）。
- 500KBを超過した場合はビルドがFAILするので、方式Bに切り替える。
- メリット：外部ホスティング不要・オフライン表示可能。

### 4.4 方式B：外部ホスティング＋絶対URL参照（推奨・全面画像デッキ向け）

画像をGAS外のホスティングに置き、HTML内の相対パスを絶対URLに差し替える。HTML自体は軽量に保てるため500KB上限を気にしなくてよい。

**Google Drive直リンクの場合：**

1. `assets/generated` 配下の画像（webp/png）をGoogle Driveにアップロードする。
2. 各画像を「リンクを知る全員（閲覧者）」で共有する。
3. 各画像の直リンクURLを取得し、マニフェストの対応する `files[...].publicUrl` に個別記入する。Driveは1ファイル1URLでURLをファイル名から導出できないため、`publicUrl` を1枚ずつ書く必要がある。
4. 相対パスを絶対URLに差し替えたHTMLを生成する。

```bash
node scripts/build-deck-html.js <slide-dir> --manifest=assets/generated/image-asset-manifest.json --output=index.deploy.html
```

**GitHub Pages / CDNの場合：**

URLが「ベースURL＋ファイル名」で導出できるため、マニフェストの `assetBaseUrl` にベースURLをまとめて記入するか、コマンドで直接指定する。

```bash
node scripts/build-deck-html.js <slide-dir> --asset-base-url=<ベースURL> --output=index.deploy.html
```

- 生成された `index.deploy.html` を `index` としてGASに貼る。
- 注意：Drive直リンクは多数画像のホットリンクでレート制限やURL不安定の可能性がある。安定運用にはGitHub PagesやCDNが望ましい。

### 4.5 デプロイ前チェック

GASに貼る前に、相対パス画像が残っていないか（brokenにならないか）を確認する。

```bash
node scripts/validate-ai-image-assets.js <slide-dir> --gas-check
```

### 4.6 画像が変更される場合の運用

| 変更の種類 | GAS側の対応 |
|-----------|------------|
| 同一URLで上書き（Driveで同じファイルを差し替え／同名でホスティング上書き） | **再デプロイ不要**（HTMLが変わらないため自動反映） |
| URLが変わる | マニフェストの `publicUrl` を更新 → `build-deck-html.js` を再実行して `index.deploy.html` を再生成 → GASに貼り直し「新バージョン」でデプロイ |

マニフェストは各画像の `sha256` を保持するため、どの画像が変わったかを機械的に追跡できる。

---

## 5. アクセス方法

### 5.1 URL形式

```
https://script.google.com/macros/s/{SCRIPT_ID}/exec
```

### 5.2 共有方法

- URLをそのまま共有可能
- QRコードに変換して配布も可能
- スマートフォン/タブレットでもアクセス可能

---

## 6. 操作方法

| 操作 | 方法 |
|------|------|
| 次のスライド | →キー / スペースキー / 右ボタン |
| 前のスライド | ←キー / 左ボタン |
| スライドジャンプ | 下部ドットをクリック |

---

## 7. 更新方法

### 7.1 コンテンツの更新

1. GASプロジェクトを開く
2. `index.html` を編集
3. 「デプロイ」→「デプロイを管理」
4. 鉛筆アイコンをクリック
5. 「バージョン」を「新バージョン」に変更
6. 「デプロイ」をクリック

### 7.2 URLについて

- 同じURLで更新内容が反映される
- URLは変更されない

---

## 8. トラブルシューティング

### 8.1 アクセスできない

| 原因 | 対処法 |
|------|--------|
| デプロイされていない | 「デプロイ」→「新しいデプロイ」を実行 |
| 権限設定が不適切 | アクセスできるユーザーを「全員」に設定 |
| URLが古い | 「デプロイを管理」で最新URLを確認 |

### 8.2 表示が崩れる

| 原因 | 対処法 |
|------|--------|
| CDNがブロックされている | 社内ネットワークの場合はIT部門に確認 |
| ブラウザの問題 | 別のブラウザで試す |
| キャッシュの問題 | ブラウザのキャッシュをクリア |

### 8.3 アニメーションが動作しない

| 原因 | 対処法 |
|------|--------|
| JavaScriptエラー | ブラウザの開発者ツールでコンソールを確認 |
| GSAPの読み込み失敗 | ネットワーク接続を確認 |

---

## 9. 制限事項

| 項目 | 制限 |
|------|------|
| HTMLファイルサイズ | 最大500KB（base64インライン時は画像込みで500KB以内・超過は§4方式Bの外部URL参照） |
| 実行時間 | 最大6分 |
| 同時アクセス数 | 制限なし（Google側で管理） |
| カスタムドメイン | 不可（script.google.com のみ） |

---

## 10. セキュリティ考慮事項

- 「全員」に公開する場合、URLを知っている人は誰でもアクセス可能
- 機密情報を含むプレゼンは「特定のユーザー」設定を推奨
- URLの取り扱いに注意
