# 検証・受入条件・運用（全方式共通）

## 1. 必須テストケース（Better Auth実装）

実装完了前に以下の15ケースをすべて実行し、結果を報告する。

| No. | テスト | 期待結果 |
|---:|---|---|
| 1 | 未ログインで保護ページ | `/login`へ遷移 |
| 2 | Googleログイン成功 | 元の保護ページへ戻る |
| 3 | ログアウト | セッション終了、保護ページへ戻れない |
| 4 | 無効ドメイン（許可外hd） | ログイン拒否 |
| 5 | email_verified=false相当 | ログイン拒否 |
| 6 | suspendedユーザー | 重要APIは403 |
| 7 | 一般ユーザーでadmin API | 403 |
| 8 | adminでadmin API | 成功 |
| 9 | 他組織IDをURLへ指定 | 403（テナント境界） |
| 10 | 不正callbackUrl | 外部サイトへ遷移しない |
| 11 | Secret未設定 | デプロイ/起動が明確に失敗 |
| 12 | D1停止・上限想定 | 安全なエラー表示、無限リトライなし |
| 13 | Cookie削除 | 再ログイン要求 |
| 14 | リポジトリ内をClient Secretで検索 | 存在しない（Git履歴含む） |
| 15 | ログ確認 | Token・Cookie・Secretが出力されていない |

アカウント別テスト：
- 社内限定：許可Workspaceユーザー／同Workspaceの別ユーザー／無許可Workspaceユーザー／個人Gmail
- 外部公開：個人Gmail／Workspaceユーザー／Testing時のTest user外／suspended／初回／既存

## 2. セキュリティ受入条件（すべて満たすまで本番公開しない）

- [ ] Googleの`sub`を一意識別に使う（emailを主キーにしていない）
- [ ] `email_verified`を確認する
- [ ] 社内・企業限定は`hd`をサーバー側で確認する
- [ ] Googleスコープは`openid email profile`だけ
- [ ] SecretがCloudflare Secretsにあり、Gitとログにない
- [ ] JWTセッションは8時間以下を初期値とする
- [ ] 重要APIはD1でrole・statusを毎回確認
- [ ] 認可がすべてサーバー側にもある（UI制御だけになっていない）
- [ ] テナント境界テスト（No.9）に合格
- [ ] Open Redirectがない／CSRF保護を無効化していない
- [ ] Tokenをブラウザへ露出していない
- [ ] suspendedユーザーの重要操作を拒否できる
- [ ] 初回ログインユーザーを自動adminにしない

## 3. 無料枠受入条件

- [ ] Workers 100,000 req/日以内の想定
- [ ] D1 5M rows read/日・100k rows written/日・500MB/DB以内の想定
- [ ] 一覧APIにLIMIT／検索列にIndex
- [ ] ページ閲覧ごとのDB書き込みなし
- [ ] セッション読み取りコスト（D1 Rows Read）を見積もり済み
- [ ] 無限ポーリング・無限リトライなし（失敗時は指数バックオフ）
- [ ] 使用量確認手順あり／上限時の安全なエラー処理あり

## 4. 本番リリース手順

**手順1 Google**：本番プロジェクト作成 → Branding → Audience → 最小スコープ → 本番OAuth Client → 本番Origin/Callback登録 → ID/Secret取得 → （外部公開）Privacy Policy公開
**手順2 Cloudflare**：本番D1作成 → binding → Secrets登録 → 本番ドメイン → HTTPS確認 → migration適用 → デプロイ
**手順3 確認**：本番ログイン/ログアウト → 401/403 → ドメイン制限 → admin権限 → テナント分離 → ログに機密なし → D1 Metrics → Git履歴にSecretなし
**手順4 外部公開**：Audience `In production`へ → 検証手続き → サポート窓口 → 利用規約/Privacy Policy → アカウント削除導線 → Secretローテーション手順

## 5. トラブルシューティング早見表

| 症状 | 確認 |
|---|---|
| `redirect_uri_mismatch` | 登録URIと実URIの**完全一致**（http/https・www・大文字小文字・ポート・末尾スラッシュ・パス欠落） |
| `AccessDenied` | email_verified → hd → ALLOWED_HOSTED_DOMAINS → status → Audience(Internal/External) → Test users → Workspace管理者のアプリ制御 の順 |
| ローカルOK・本番NG | 本番Secret／開発用Client ID混入／本番Callback未登録／https／www有無／Hostヘッダー・trustHost／Binding取得方法／本番migration未適用 |
| D1上限超過 | MetricsでRows Read/Write確認 → 全表走査特定 → Index追加 → ページネーション → 重複呼び出し削減 → 不要書き込み停止 → 必要ならWorkers Paid。**[禁止] 無限リトライ** |

## 6. 運用

### 月次チェック
Workers Requests／D1 Rows Read・Written・Storage／認証失敗率／不審ドメインからの試行／suspended一覧／admin一覧／Google OAuth設定変更／依存パッケージ更新／Auth.js・Better Authのセキュリティ情報／Cloudflare・Googleの仕様変更／Privacy Policy整合／不要なTest users・OAuth Client・Secret

### Secretローテーション
**Client Secret漏えい時**：新Secret発行 → Cloudflare Secret更新 → デプロイ → ログインテスト → 旧Secret無効化 → Git履歴・ログ・共有先調査 → 影響記録
**AUTH_SECRET**：使用中バージョンの段階的ローテーション仕様に従う。緊急完全変更は既存JWT全無効化＝全ユーザー再ログインになることを事前に伝える

### ログ設計
出してよい例：
```ts
console.info("auth.signin.success", { userId: user.id, provider: "google", requestId });
```
**[禁止]**：Client Secret／AUTH_SECRET／ID・Access・Refresh Token／Cookie全文／Authorizationヘッダー／個人情報本文。メールをログに出す場合は目的と保持期間を明確に。原則は内部ユーザーID。

### XSS・追加ログイン方式
- OAuthプロフィール値（名前・画像URL・組織名）も外部入力として扱う。`dangerouslySetInnerHTML`回避、CSP設定
- Google以外のProviderを追加する際はアカウント乗っ取り防止の設計レビュー。**[禁止] `allowDangerousEmailAccountLinking`の安易な有効化**
- Google API利用トークンが必要になった場合：D1へ平文保存しない／暗号化と鍵管理を設計／最小スコープ／失効・再同意処理／連携解除UI／削除時のトークン破棄
