---
name: non-tech-vocabulary
description: 完全非技術者向け一律言い換え辞書 (90 語以上)
type: reference
---

# 非技術者言い換え辞書

`vocabulary-tiers.md` が階層別変換を扱うのに対し、こちらは**完全非技術者向けの一律言い換え辞書**として動作する。図解・本文の用語強制変換に使う。

## 言い換えテーブル（90 語以上）

| 原語 | 言い換え |
|------|----------|
| API | 外部サービス連携 |
| API Key | サービス利用の鍵 |
| OAuth | サービスへのログイン許可 |
| OAuth Token | ログイン許可の鍵 |
| JSON | 設定情報 |
| YAML | 設定ファイル |
| XML | 構造付きテキスト |
| Markdown | 整形メモ |
| frontmatter | ファイル頭の設定 |
| MCP | AI と外部の橋渡し |
| Webhook | 通知連絡口 |
| Cron | 定時起動 |
| RSS | 更新通知の購読 |
| SVG | 拡大できる画像 |
| PNG | 普通の画像 |
| JPEG | 写真画像 |
| PDF | 印刷用文書 |
| CLI | コマンド画面 |
| GUI | 普段の画面 |
| kebab-case | ハイフン区切り名 |
| camelCase | 大文字つなぎ名 |
| snake_case | アンダー区切り名 |
| schema | 型の決まり |
| token | 鍵の文字列 |
| endpoint | 接続先 |
| URL | 場所のアドレス |
| URI | 場所のアドレス |
| payload | 送るデータ |
| header | 通信の付帯情報 |
| body | 通信の本文 |
| rate limit | 利用回数の上限 |
| quota | 利用枠 |
| pagination | 続きを取る仕組み |
| polling | 定期確認 |
| async | あとから処理 |
| sync | 同時に処理 |
| repository | 保管庫 |
| commit | 変更の保存 |
| pull request | レビュー依頼 |
| branch | 作業の枝分かれ |
| merge | 合流 |
| rebase | 順番付け直し |
| migration | 移行作業 |
| deploy | 本番に出す |
| environment variable | 設定の値 |
| dependency | 必要な部品 |
| serialize | 文字列にする |
| parse | 読み解く |
| regex | 文字パターン |
| Docker | アプリ箱詰め |
| container | 箱詰めアプリ |
| GitHub Actions | 自動実行の仕組み |
| webhook URL | 通知の届き先 |
| Bot Token | ロボットの鍵 |
| OAuth Scope | 許可する範囲 |
| client_id | サービス申込番号 |
| client_secret | サービスの秘密鍵 |
| refresh_token | 鍵の再発行用控え |
| access_token | 一時鍵 |
| OAuth callback | 認証完了の戻り口 |
| HTTP | サイト通信 |
| HTTPS | 安全なサイト通信 |
| HTTP status | 通信の結果コード |
| 200 OK | 成功 |
| 401 Unauthorized | 鍵が効かない |
| 403 Forbidden | 立入禁止 |
| 429 Rate Limited | 使いすぎでお休み |
| 500 Server Error | 向こうが故障 |
| Slack channel | スラックの部屋 |
| Discord channel | ディスコの部屋 |
| Notion page | ノーションのページ |
| Notion database | ノーションの一覧表 |
| Google Drive folder | グーグルの本棚の棚 |
| spreadsheet | 表 |
| sheet | 表のシート |
| row | 行 |
| column | 列 |
| cell | マス |
| query | 問い合わせ |
| filter | 絞り込み |
| sort | 並び替え |
| index | 索引 |
| cache | 一時保管 |
| log | 動作の記録 |
| debug | 不具合さがし |
| stack trace | エラーの足跡 |
| timeout | 時間切れ |
| retry | 再試行 |
| fallback | 代替手段 |
| Whisper | 音声→文字起こし AI |
| LLM | 大規模言語モデル（賢い AI） |
| embedding | 文章の特徴ベクトル |
| vector DB | 特徴で検索する保管庫 |
| RAG | 資料を引きながら答える AI |
| prompt | AI への指示文 |
| system prompt | AI への大前提指示 |
| context window | AI が一度に読める範囲 |
| Keychain | macOS の鍵保管庫 |
| PAT | 個人アクセス鍵 |
| Internal Integration | 社内連携アプリ |

## 自動変換ルール

```javascript
function rewriteForNonTech(text, dict) {
  let out = text;
  for (const [from, to] of Object.entries(dict)) {
    const re = new RegExp(`\\b${escapeRegex(from)}\\b`, 'gi');
    out = out.replace(re, to);
  }
  return out;
}
```

- 大文字小文字無視
- 単語境界考慮（`API` を `APIcation` 内で誤変換しないため）
- 一度変換した語は再変換しない（`設定情報` を再変換しない）

## 例文比較

### 変換前

> このスキルは Google Forms API に OAuth で接続し、JSON で取得した回答を Sheets に書き込みます。Cron で定時実行され、Webhook で通知します。

### 変換後（非技術者向け）

> このスキルは Google Forms の外部サービス連携にサービスへのログイン許可で接続し、設定情報で取得した回答を Sheets に書き込みます。定時起動で動き、通知連絡口で通知します。

## 例外

| 状況 | 例外扱い |
|------|----------|
| ブランド名（Google Forms 等） | 変換しない |
| 固有スキル名 | 変換しない |
| 引用ブロック | 変換しない |
| コードブロック内 | 変換しない |
| user_profile.technical_level === 上級 | 辞書全体を適用しない |

## 自己拡張

ヒアリング中に未登録の専門用語が検出されたら、`skill-intake-self-updater` が草稿として末尾に追加。人間レビューで採用・却下。

```javascript
if (!dict[term] && isTechnicalTerm(term)) {
  draftDict[term] = "（要言い換え検討）";
}
```
