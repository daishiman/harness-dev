---
name: vocabulary-tiers
description: 熟練度別の言い換え辞書 (30 語以上・3 階層)
type: reference
---

# 語彙難易度辞書（3 階層）

`user_profile.technical_level` に応じて、SubAgent 発話を自動変換する。

- 非技術者向け: **専門用語を完全排除**
- 中級向け: **括弧で簡易説明**
- 上級向け: **原語のまま**

完全非技術者の一律言い換えは `non-tech-vocabulary.md` を併用する（本辞書は階層変換、あちらは強制変換）。

## 変換テーブル（35 語以上）

| 原語 | 非技術 | 中級 | 上級 |
|------|--------|------|------|
| API | 外部サービス連携 | API（外部サービス連携） | API |
| OAuth | サービスへのログイン許可 | OAuth（ログイン許可） | OAuth |
| JSON | 設定情報 | JSON（設定情報） | JSON |
| YAML | 設定ファイル | YAML（設定ファイル） | YAML |
| Markdown | 整形メモ | Markdown（整形メモ） | Markdown |
| Webhook | 通知連絡口 | Webhook（通知連絡口） | Webhook |
| Cron | 定時起動 | Cron（定時起動） | Cron |
| RSS | 更新通知の購読 | RSS（更新購読） | RSS |
| MCP | AI と外部の橋渡し | MCP（AI 連携の橋渡し） | MCP |
| SVG | 画像（拡大 OK） | SVG（拡大可能画像） | SVG |
| PNG | 画像 | PNG | PNG |
| CLI | コマンド画面 | CLI（コマンド画面） | CLI |
| GUI | 普段の画面 | GUI（画面操作） | GUI |
| kebab-case | ハイフン区切り名 | kebab-case | kebab-case |
| camelCase | 大文字つなぎ名 | camelCase | camelCase |
| frontmatter | ファイル頭の設定 | frontmatter（ファイル頭の設定） | frontmatter |
| schema | 型の決まり | スキーマ（型の決まり） | schema |
| token | 鍵の文字列 | トークン（認証鍵） | token |
| endpoint | 接続先 | エンドポイント（接続先） | endpoint |
| payload | 送るデータ | ペイロード（送信データ） | payload |
| rate limit | 利用回数の上限 | レート制限 | rate limit |
| pagination | 続きを取る仕組み | ページング | pagination |
| polling | 定期確認 | ポーリング（定期確認） | polling |
| async | あとから処理 | 非同期 | async |
| sync | 同時に処理 | 同期 | sync |
| repository | 保管庫 | リポジトリ（保管庫） | repository |
| commit | 変更の保存 | コミット（変更保存） | commit |
| pull request | レビュー依頼 | PR（レビュー依頼） | PR |
| branch | 作業の枝分かれ | ブランチ | branch |
| migration | 移行作業 | マイグレーション | migration |
| deploy | 本番に出す | デプロイ（本番反映） | deploy |
| environment variable | 設定の値 | 環境変数 | env var |
| dependency | 必要な部品 | 依存ライブラリ | dependency |
| serialize | 文字列にする | シリアライズ | serialize |
| parse | 読み解く | パース（読み解く） | parse |
| regex | 文字パターン | 正規表現 | regex |
| Docker | アプリ箱詰め | Docker（コンテナ） | Docker |
| GitHub Actions | 自動実行の仕組み | GitHub Actions | GHA |
| Keychain | macOS の鍵保管庫 | Keychain（鍵保管庫） | Keychain |
| PAT | 個人アクセス鍵 | PAT（個人アクセス鍵） | PAT |

## 変換ルール

1. **非技術** プロファイル時は原語が出た瞬間に変換、原語は決して画面に出さない
2. **中級** 時は初出のみ括弧書き、2 回目以降は原語 OK
3. **上級** 時は変換せず原語＋必要なら詳細説明

## 例文比較（同じ内容を 3 レベルで）

### 非技術

> Google にログイン許可を一度していただければ、外部サービス連携の鍵が macOS の鍵保管庫に保管されて、定時起動で毎朝フォームの状況を取りに行きます。

### 中級

> OAuth（Google へのログイン許可）を一度通せば、API（外部サービス連携）の認証トークンが Keychain（鍵保管庫）に保存され、Cron（定時起動）で毎朝フォームの状況を取得します。

### 上級

> OAuth で取得した refresh_token を Keychain に保存し、Cron で毎朝 forms.responses.list を polling します。

## 自己拡張

ヒアリング中に未登録の専門用語が出たら、`skill-intake-self-updater` が草稿登録 → 月次レビューで採用。

## 注意

- 同義の登録（例: API と Web API）は重複させない
- 業界固有用語（医療・法律）は別ファイルで管理（本辞書は IT 一般）
- ブランド名（Google Forms 等）は変換しない
