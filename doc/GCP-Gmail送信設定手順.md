<!--
このセクションは既存ドキュメント「Google Sheets / Docs / Drive API を企業利用するための Google Cloud 設定手順」の末尾に追加する内容です。
あわせて、冒頭の「目次」に以下の行を追記してください。

  12. STEP 10: Gmail API の有効化
  13. STEP 11: ドメイン全体の委任に Gmail スコープを追加
  14. STEP 12: 操作対象アドレスの指定（指定アドレスのみ）
  15. メール（Gmail API）設定完了チェックリスト
-->

---

# メール（Gmail API）を使えるようにする設定

> **本セクションのスコープ**
>
> - Claude Code 等の外部 AI・サーバーから、**Workspace のメールボックスに対して Gmail API を操作**（送信／受信メールの取得・検索／メールボックス・ラベル情報の取得／既読・ラベル変更）できるようにするための **Google Cloud 上の設定作業のみ** を扱います
> - 本書 **STEP 1〜9 の完了を前提**とします（プロジェクト・サービスアカウント・JSON 鍵・DWD は作成済み）

Gmail API のために**新しいプロジェクトやサービスアカウントを作り直す必要はありません**。既存の成果物をそのまま使い、差分の 2 点だけを追加します。

| 既存ステップ | 完了済みの内容 | 本セクションでの扱い |
| --- | --- | --- |
| STEP 3 | Drive / Sheets / Docs API 有効化 | **STEP 10 で Gmail API を追加** |
| STEP 5・6 | サービスアカウント作成・JSON 鍵発行 | 流用（同じ鍵で操作可） |
| STEP 7 | DWD に Drive/Sheets/Docs スコープ登録 | **STEP 11 で Gmail スコープを追記** |

---

## STEP 10: Gmail API の有効化

> 既存 STEP 3（API 有効化）に **4 つ目の API** を足す作業です。`console.cloud.google.com` で行います。送信・取得・メールボックス情報のいずれを使う場合も、有効化するのはこの **Gmail API 1 つ**です。

### 10-1. 正しいプロジェクトを選択

1. `https://console.cloud.google.com/` を開く
2. 画面上部のプロジェクト選択ドロップダウンで、STEP 1 で作成したプロジェクト（例 `xl-claude-code`）が**選択中**であることを確認

### 10-2. API ライブラリを開く

**URL**: `https://console.cloud.google.com/apis/library`

または左サイドメニュー（≡）→ **「API とサービス」→「ライブラリ」**。

### 10-3. Gmail API を有効化

1. 検索ボックスに `Gmail API` と入力
2. 候補から **「Gmail API」**（提供元: Google Workspace カテゴリ）をクリック
3. API 詳細画面で青い **「有効にする」** ボタンをクリック
4. 「API が有効になりました」と表示されれば完了

> gcloud 派の同等コマンド:
> ```bash
> gcloud services enable gmail.googleapis.com --project=<プロジェクトID>
> ```

### 10-4. 有効化状態の確認

**URL**: `https://console.cloud.google.com/apis/dashboard`

「有効な API とサービス」一覧に **Gmail API** が（既存の Drive / Sheets / Docs と並んで）表示されていることを確認。

---

## STEP 11: ドメイン全体の委任に Gmail スコープを追加

> 既存 STEP 7（DWD 設定）の登録内容に **Gmail 用スコープを追記**します。Workspace 特権管理者（Super Admin）の作業です。本人が特権管理者でない場合、STEP 5-6 で控えた**クライアント ID（21 桁の数字）**と、下記で選んだスコープを渡して依頼してください。

### 11-1. 登録するスコープを決める（用途別）

やりたい操作に合うスコープを選びます。**送信・取得・変更を幅広く使うなら `gmail.modify` 一本**で足ります（完全削除以外すべて）。

| やりたいこと | 登録するスコープ |
| --- | --- |
| 送信だけ | `https://www.googleapis.com/auth/gmail.send` |
| 受信メールの取得・検索・**メールボックス情報（総数）・ラベル情報の取得** | `https://www.googleapis.com/auth/gmail.readonly` |
| 本文を読まずヘッダ/ラベルのみ取得 | `https://www.googleapis.com/auth/gmail.metadata` |
| 送信＋取得＋既読/ラベル変更（メール全般・推奨） | `https://www.googleapis.com/auth/gmail.modify` |
| 完全削除（ゴミ箱を経由しない消去）も必要 | `https://mail.google.com/` |

> `gmail.modify` は `gmail.send` と `gmail.readonly` を包含します。`modify` を登録するなら両者の併記は不要です。

### 11-2. API 制御ページを開く

1. `https://admin.google.com/` に**特権管理者**でログイン
2. 左メニュー **「セキュリティ」→「アクセスとデータ管理」→「API の制御」**
   - 直リンク: `https://admin.google.com/ac/owl/domainwidedelegation`
3. ページ下部 **「ドメイン全体の委任」** →「**ドメイン全体の委任を管理**」をクリック

### 11-3. 既存のサービスアカウント行を編集

1. 一覧から、STEP 7 で登録済みの**クライアント ID（21 桁の数字）**の行を探す
2. その行の **︙（その他）→「編集」** をクリック（既存スコープを残したまま追記するため、新規追加ではなく**編集**を選ぶ）

### 11-4. Gmail スコープを追記

OAuth スコープ欄（カンマ区切り）に、既存の Drive/Sheets/Docs スコープを**残したまま**、末尾に STEP 11-1 で選んだ Gmail スコープを追加します。

**メール全般を使う場合（`gmail.modify`）の記入例**:

```
https://www.googleapis.com/auth/drive,https://www.googleapis.com/auth/spreadsheets,https://www.googleapis.com/auth/documents,https://www.googleapis.com/auth/gmail.modify
```

> 既存 3 スコープの末尾に `,https://www.googleapis.com/auth/gmail.modify` を足すだけでも構いません。

### 11-5. 「承認」をクリック

一覧のクライアント ID 行に、追加した Gmail スコープを含む全スコープが表示されれば完了。

> **注意**: スコープは API 側の要求スコープと**完全一致**で照合されます。反映には**数分〜最大 1 時間**かかるため、直後にエラーが出ても待ってから確認してください。

---

## STEP 12: 操作対象アドレスの指定（指定アドレスのみ）

Gmail API は「**どのメールボックスを操作するか**」を impersonate（なりすまし）対象として指定します。本構成では **指定したメールアドレス 1 つ（または明示した数個）のみ**を対象にします。

### 12-1. 対象アドレスを決める

| 項目 | 内容 |
| --- | --- |
| 対象アドレス | 操作したい実在の Workspace ユーザー（例 `automation@your-domain.co.jp`） |
| 条件 | 実ユーザー or 共有メールボックスで、Gmail が有効なライセンス |

このアドレスを**開発側に「impersonate 対象はこのアドレスのみ」**として引き渡します。

### 12-2. 必要なら新規アカウントを作成

`admin.google.com` →「ディレクトリ」→「ユーザー」→「新しいユーザーを追加」でアカウントを作成（Gmail を有効化）。

> **設定上の注意**: DWD は管理コンソール上では「ドメイン内の任意ユーザーを impersonate できる」状態として承認されます（対象アドレスを管理画面で 1 つに限定する機能はありません）。そのため「指定アドレスのみ」は **対象アドレスを明示して運用で固定**することで担保します。鍵が全メールボックスへの入口になる点は変わらないため、JSON 鍵の管理は厳格に（既存 STEP 6-3 と同様）。

---

## メール（Gmail API）設定完了チェックリスト

### Cloud Console 側
- ☐ 既存プロジェクト選択中で **Gmail API を有効化**した
- ☐ API ダッシュボードに Gmail API が表示された

### Workspace 管理コンソール側
- ☐ 用途に合う Gmail スコープを決めた（メール全般なら `gmail.modify`、取得のみなら `gmail.readonly`）
- ☐ DWD の既存クライアント ID 行に **Gmail スコープを追記**した
- ☐ 既存の Drive/Sheets/Docs スコープを**消さずに**残した
- ☐ 「承認」後、一覧に追加した Gmail スコープが表示された
- ☐ **操作対象アドレス（指定アドレス）**が実在し Gmail 有効

以上で、メール（Gmail API）を使えるようにする Google Cloud 側の設定は完了です。
