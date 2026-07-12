# company-master 導入・使い方ガイド(Claude Desktop 版)

> **このドキュメントについて**
>
> このプラグインを使い始めるために **あなたが行う作業を、上から順にこなすだけ** で完了するようまとめています。
> 専門知識は不要です。**操作はすべて Claude Desktop アプリの「Code」タブの中だけで完結**します(ターミナル.app を別アプリとして開く必要はありません)。一部の登録・確認では、**貼り付けるだけの定型コマンド**を Code タブに打ち込みます(自分でコマンドを考える必要はありません)。
> API キー(トークン)は macOS の Keychain(キーチェーン)に保管し、ファイルには平文で残しません。
>
> 各ステップには「**こう表示されれば成功**」の確認方法を添えています。違うときは「[9. うまくいかないとき](#9-うまくいかないとき)」を見てください。

> **どこに書き込まれるか(対象読者)**
>
> 記録先は **tenant 社内の共有 Notion 一覧表(設定済み)** です。社内で使う方は、このまま読み進めれば設定不要でその表に書き込まれます。
> **自分の別の Notion で使いたい方**は、同じ7列の一覧表を自分で用意し(列の作り方: [`company-master-columns.md`](references/company-master-columns.md))、書き込み先を切り替えられます(Claude に「出力先の Notion データベースを ○○ に変えて」と頼むか、設定値 `COMPANY_MASTER_NOTION_DATABASE_ID` / `.notion-config.json` で指定。詳細: [`README-setup.md`](references/README-setup.md))。
>
> | 使い方 | Notion DB ID | Notion 側で必要なこと |
> |---|---|---|
> | 社内共有DBを使う | 入力不要(同梱既定値) | 自分の Integration を共有DBの Connections に追加できる権限を持つ人に依頼、または自分で追加 |
> | 自分のDBを使う | `COMPANY_MASTER_NOTION_DATABASE_ID` か `.notion-config.json` で指定 | 同じ7列を作り、自分の Integration をそのDBに接続 |
>
> 401/403 が出る場合は、トークン登録だけでなく **Notion DB 側の Connections に Integration が追加されているか** を確認してください。

---

> **最初の5分でやること(TL;DR・急ぐ人向け)**
>
> 1. **Claude Desktop** を開いてサインインし、上部の **「Code」タブ** を選ぶ(作業フォルダは何でも構いません。**このリポジトリを clone して開く必要はありません**)
> 2. Code タブのチャット欄に `/plugin marketplace add OWNER/harness` → `/plugin install company-master@harness`(詳細は [6章](#6-ステップb-プラグインのインストールcode-タブで実行))
> 3. Code タブで「**Notion のトークンを Keychain に登録して**」「**gBizINFO のトークンを Keychain に登録して**」と頼む(聞かれたらトークンを貼る。[5章](#5-ステップa-事前準備すべて-code-タブで実行))
> 4. ブラウザで、書き込み先 Notion DB に自分の Integration を **「接続(Connections)」**([5-4](#5-4-notion-のデータベースに連携を接続するブラウザでクリック操作))
> 5. Code タブで「**company-master の doctor を実行して**」→ FAIL が無ければ準備完了([8章](#8-最初の動作確認おすすめ))
> 6. 「**株式会社サンプルを調べて。まだ Notion に書き込まないで**」で試し、良ければ「**Notion に登録して**」
>
> 郵便番号の自動取得(日本郵便API)は **任意の追加機能** です。まずは上の2トークンだけで始められます。
> **先回りのコツ**: 上の 3 で使う **gBizINFO トークンは申請→メール発行待ち**(数時間〜即日)があります。**いちばん最初に [gBizINFO 利用申請](https://info.gbiz.go.jp/hojin/APIManual) だけ済ませて**おくと、待つ間に 1・2 を進められます。

> **このガイドの前提(パスについて・必読)**
>
> このプラグインは **マーケットプレイスから install** して使います(下記6章)。install するとスクリプトは Claude の管理領域(`$CLAUDE_PLUGIN_ROOT` 配下)に自動展開され、**パスは自動で解決されます**。
> そのため、診断や実行は **Code タブで「○○して」と日本語で頼むだけ** で済みます。**`plugins/company-master/...` のようなパスを自分で手打ちする必要はありません**(本ガイドが各所で「チャットで頼む」を一次手段にしているのはこのためです)。
> 一部に出てくる `! python3 plugins/company-master/...` という手打ち例は、**このリポジトリを自分で clone して開いた開発者向けの補足**です。clone していない通常の利用者は、その下に併記した「チャットで頼む」方法を使ってください。

---

## 1. このプラグインでできること(概要)

**会社名・住所・法人番号のどれか一部だけ** を伝えると、足りない企業情報を自動で調べて **Notion の一覧表(企業マスタ)** に整えて記録します。

調べてくれる情報と取得元:

| Notion の列 | 内容 | どこから取るか |
|---|---|---|
| 会社名 | 登記上の正式な社名(取れたとき)。取れなければあなたが入力した通称 | gBizINFO(経済産業省) / 入力 |
| 住所 | 都道府県から始まる住所 | gBizINFO |
| 郵便番号 | `123-4567` の8文字 | 日本郵便データ |
| 法人番号 | 13桁の番号 | gBizINFO |
| 電話番号 | ハイフン区切り | ネット検索 |
| 情報の確かさ | その行がどれくらい信頼できるか(下記4種) | 自動判定 |
| 備考 | 取れなかった項目の理由(定型文) | 自動記録 |

(「会社名」列は、登記上の正式名称が取れたときはそれを表示し、取れなかったときだけあなたの入力した通称を表示します=**正式名称は会社名列にまとめ、独立した「正式名称」列は作りません**。上記の7列に加えて、ネット検索した値の**根拠ページURL**は各企業の **Notion ページ本文**に「確認用URL（手動検証用）」として固定の見出し付きで自動記録されます。DB の列は7列のままに保ちます。)

「情報の確かさ」は次の4つのいずれかが入ります(専門用語は使いません):

- **公的データで確認済み** … 一番信頼できる
- **公的データ取得** … 公的データから取得
- **ネット検索(要確認)** … ネット検索由来。念のためページ本文の確認用URLで確認を
- **未確定(要確認)** … 確実に分からなかった(空欄)。間違った値は入れません

> このプラグインは **間違った値を入れるくらいなら空欄にする** 方針です。一度で取得できなかった項目も、**複数の手段 (公的データの別の引き方 → ネット検索) を自動で順に試し**、それでも分からなかった項目だけを空欄 + 「備考」(どの手段を試したか付き) で人間に引き継ぎます。空欄の理由は「備考」に、ネット検索した値の確認先は**ページ本文の「確認用URL」**に残るので、後から人の目で確認できます。

### 2つの使い方
- **(A) チャットで聞く** … Claude Desktop の Code タブに「この会社を調べて」と話しかける
- **(B) Notion の空欄をまとめて補完** … すでに会社名や住所が入っている行の、空いている項目だけ埋める

---

## 2. 全体の流れ(やることは4つ)

```
[ステップ0] Claude Desktop を用意   … アプリを入れて Code タブを開く (一度だけ。作業フォルダは何でも可)
        ↓
[ステップB] インストール           … マーケットプレイスからプラグインを入れる (一度だけ・約2分)
        ↓
[ステップA] 事前準備               … トークンを登録し、Notion とつなぐ (一度だけ・約10分 ※gBizINFO トークンの発行待ちは別途数時間〜即日)
        ↓
[ステップC] 使う                  … Code タブで会社情報を集める (毎回)
```

> **大事な前提その1(導入方法)**: このプラグインのような独自プラグインは、Claude Desktop の「設定(Settings)→ Extensions」画面からは追加できません(あの画面は公式ストアのプラグイン専用です)。
> 代わりに **Code タブのチャット欄にコマンドを打ち込んで** 追加します(6章)。本ガイドはその方法を案内します。
>
> **大事な前提その2(clone は不要)**: 本ガイドの既定は、**GitHub の公開リポジトリをマーケットプレイスとして登録する**方法です。各メンバーは **リポジトリを自分のPCに clone する必要はありません**。Code タブで開くフォルダも、このリポジトリである必要はなく**何でも構いません**。
>
> **順番について**: 先に **install(ステップB)** を済ませてから **事前準備(ステップA)** を行うと、トークン登録の確認や doctor 診断をプラグイン経由でそのまま実行できてスムーズです(このため上の図ではB→Aの順にしています)。

---

## 3. 事前に準備するもの(チェックリスト)

- [ ] **Mac**(macOS) … **本ガイドは Mac 専用**です(鍵の保管に macOS のキーチェーン/`security` コマンドを使うため。Windows / Linux の方は社内の管理者にご相談ください)
- [ ] **Claude Desktop アプリ**と、**Pro / Max / Team / Enterprise いずれかのプラン**(Code 機能に必要)
- [ ] **Notion のアカウント**と、情報を貯める **データベース(一覧表)**
  - 出力先のデータベースは **このプラグインに既定で設定済み**です(ID 入力は不要)
- [ ] **Notion の API トークン**(`ntn_` で始まる文字列。[My integrations](https://www.notion.so/my-integrations) で「New integration」を作ると発行)
- [ ] **gBizINFO の API トークン**([gBizINFO 利用申請](https://info.gbiz.go.jp/hojin/APIManual)。無料・数時間〜即日でメール)

> トークン2つ(Notion・gBizINFO)が手元にそろってから事前準備(5章)へ進んでください。
> **gBizINFO は申請から発行までメール待ち**(数時間〜即日)があります。**いちばん最初に申請だけ済ませておく**と、待っている間に Claude Desktop の用意・install・Notion トークン登録を進められて無駄がありません。
>
> **郵便番号の自動取得は任意の追加機能**です。日本郵便 API の鍵(+送信元IP の登録)は後からでも追加できます。**まずは上の2トークンだけで始められます**(日本郵便の鍵が無くても他の項目は埋まり、郵便番号だけ空欄になります)。送信元IPの登録などやや専門的な設定が要るので、必要になってから手順 5-2.5 で追加するのがおすすめです。

---

## 4. ステップ0: Claude Desktop を用意する

1. ブラウザで **https://claude.com/download** を開き、**Claude Desktop(Mac 版)** をダウンロードして、アプリを **アプリケーション** フォルダに入れる
2. アプリを起動し、**自分の Anthropic アカウントでサインイン**する
3. 画面上部の **「Code」タブ** をクリックする(ここが、設定や操作を打ち込む場所です)
4. **「Select folder(フォルダを選択)」** をクリックし、**作業用のフォルダを1つ選ぶ**
   - **どのフォルダでも構いません**(空のフォルダを新規作成して選んでもOK)。プラグイン本体は次の6章で**マーケットプレイスからダウンロード**するので、**このリポジトリを clone して開く必要はありません**
   - (補足)もし開発者として既にこのリポジトリを clone 済みなら、そのルートフォルダ(直下に `.claude-plugin/marketplace.json` がある)を選んでも構いません
5. 「このフォルダを信頼しますか?」と聞かれたら **信頼(Trust)** を選ぶ

> これ以降の「Code タブのチャット欄に〜と入力」という指示は、この画面下部の入力欄に文字を打って Enter する操作を指します。
> **次は順番に注意**: 本ガイドは先に **6章(インストール)** を済ませ、その後 **5章(事前準備)** に進むとスムーズです(install 後ならトークン確認や doctor をプラグイン経由でそのまま実行できます)。以下は章番号順に並んでいますが、**6章 → 5章 → 7章** の順で読み進めてください。

---

## 5. ステップA: 事前準備(すべて Code タブで実行)

> **チームで配布する場合**: 「どの鍵を Keychain に入れるか」をロール別にまとめた配布用の正本が
> [`references/keychain-setup.md`](references/keychain-setup.md) にあります。
> 当チームの郵便番号取得は **BYO 直結が既定**で、**各メンバーが自分の for Biz アカウント・`client_id`/`secret_key`・送信元IP を持ち、日本郵便 API を直接叩きます**(以下 5-2.5 の手順)。固定IP回線のメンバーは `egress_ip` を pin すると確実。送信元IPを固定できない/頻繁に変わるメンバーだけ、例外的に中央プロキシ(`proxy_url`/`proxy_token` のみ登録)を使います。
> Mac で自分の送信元(グローバル)IP を調べる方法も同書に記載。

### 5-1. Notion のトークンを登録

Code タブのチャット欄に、**トークンを書かずに** 次のように頼みます(Enter):

```
Notion のトークンを Keychain に登録して。サービス名は notion-api-key.<keychain-prefix>、アカウントは harness
```

Claude が「トークンを教えてください」と聞いてきたら、そのときだけトークン(`ntn_` で始まる文字列)を貼り付けて渡してください。

> こうすると、指示メッセージにトークン平文を含めずに登録できます。
> エラーが出ずに「登録しました」と返れば成功です。
>
> **(代替・上級者向け)** 1行で済ませたい場合は、次を貼り付けても登録できます(**トークン平文がチャット履歴に残る**点に注意。`<...>` を自分のトークンに置き換え):
> `! security add-generic-password -s notion-api-key.<keychain-prefix> -a <keychain-prefix> -w '<NOTION_INTEGRATION_TOKEN>' -T '' -U`
> (行頭の `!` は「このコマンドをそのまま実行して」という意味です)

### 5-2. gBizINFO のトークンを登録

同じように、トークンを書かずに頼みます:

```
gBizINFO のトークンを Keychain に登録して。サービス名は gbizinfo-api-token.<keychain-prefix>、アカウントは harness
```

聞かれたら、申請して届いた gBizINFO トークンを貼り付けて渡してください。

> **(代替・上級者向け)** `! security add-generic-password -s gbizinfo-api-token.<keychain-prefix> -a <keychain-prefix> -w '<GBIZINFO_API_TOKEN>' -T '' -U`(平文がチャット履歴に残る点に注意)

### 5-2.5. 日本郵便 郵便番号API のキーを登録(郵便番号を自動取得する場合)

住所から郵便番号を自動で取得するには、日本郵便「郵便番号・デジタルアドレスAPI」の **2つの鍵** が要ります。**当チームの既定はこの BYO 直結**(各メンバーが自分の鍵で直接取得する方式)。鍵の取り方〜送信元IP登録までの詳しい背景は [`references/japanpost-api-setup.md`](references/japanpost-api-setup.md) にあります。ここでは **何を・どこに登録するか** だけ案内します。

#### 登録する鍵は2つ(どちらも日本郵便 for Biz の「システム情報」画面で取得)

| 鍵 | 日本語名 | これは何か | 注意 |
|---|---|---|---|
| `client_id` | クライアントID | あなたのシステムを識別するID | 公開寄り(秘密度は低め) |
| `secret_key` | クライアントシークレット | 認証に使う**秘密の鍵** | **初回登録時にしか表示されません**。取り逃すと再発行が必要 |

> どちらも **macOS の Keychain(キーチェーン)** に保存します(ファイルや env には平文で残しません)。
> 保存先の決まり(全員これで統一):
> - **サービス名**: `japanpost-da-api.<keychain-prefix>`(Notion 用 `notion-api-key.<keychain-prefix>` / gBizINFO 用 `gbizinfo-api-token.<keychain-prefix>` と同じ `.<keychain-prefix>` 名前空間)
> - **アカウント名**: `client_id` と `secret_key`(=鍵の名前そのもの)

#### 登録方法(おすすめ: チャットで頼む)

5-1・5-2 と同じ要領で、Code タブのチャット欄に **鍵を書かずに** 頼みます(Enter)。まず client_id:

```
日本郵便のクライアントIDを Keychain に登録して。サービス名は japanpost-da-api.<keychain-prefix>、アカウントは client_id
```

Claude が「IDを教えてください」と聞いてきたら、そのとき client_id を貼り付けて渡します。続けて secret_key も同じように:

```
日本郵便のクライアントシークレットを Keychain に登録して。サービス名は japanpost-da-api.<keychain-prefix>、アカウントは secret_key
```

聞かれたら、for Biz で取得した secret_key(初回のみ表示された値)を貼り付けて渡してください。

> こうすると、指示メッセージに鍵の平文を含めずに登録できます。エラーなく「登録しました」と返れば成功です。
>
> **(代替・上級者向け)** 自分でコマンドを打つ場合(secret_key は `-w` を**空**にすると対話入力になり、履歴に平文が残りません):
> ```
> ! security add-generic-password -U -s japanpost-da-api.<keychain-prefix> -a client_id  -w '<あなたのclient_id>'
> ! security add-generic-password -U -s japanpost-da-api.<keychain-prefix> -a secret_key -w
> ```
> (行頭の `!` は「このコマンドをそのまま実行して」の意味。2行目は実行後に出るプロンプトに secret_key を貼り付け)

#### 送信元IP を日本郵便 for Biz に登録する(BYO で必須)

鍵を登録したら、Code タブで「**company-master の doctor を実行して**」と頼みます(※この節は **6章の install 完了後** に実施してください。doctor はプラグインのスクリプトを使うため)。表示された結果の「送信元IP」行に**あなたの送信元IP**が出ます。その IP を日本郵便 for Biz の「システム情報」で**送信元IP**として登録してください(最大10件)。

- **固定IP回線なら**、for Biz に登録したのと同じIPを `egress_ip` として pin しておくと、毎回そのIPで送られて確実です(自動検出の揺れに左右されない):
  `! security add-generic-password -U -s japanpost-da-api.<keychain-prefix> -a egress_ip -w '<for Biz に登録した固定IP>'`
- 動的IP(自宅/オフィスの一般回線)なら pin 不要(既定の自動検出に任せる)。IPが変わったら for Biz で再登録します(`doctor --probe` がズレを検知)。送信元IPをどうしても固定できない環境だけ、例外的に中央プロキシ([`references/postal-proxy-deploy.md`](references/postal-proxy-deploy.md))を使います。

> 鍵が未設定でも他の機能は動きます。その場合は郵便番号だけ空欄+備考になります。Code タブで「**company-master の doctor --probe を実行して**」と頼めば、実際に郵便番号を引けるか(本番接続・登録IPとのズレ)を確認できます。
> `[OK] 接続先: 本番 ...` かつ `[OK] 日本郵便 API 実疎通: テスト検索 OK ...`(stub 注記なし)が出れば本番で取得できる状態です。

### 5-3. 登録できたか確認(トークンの中身は表示しません)

Code タブのチャット欄に次を貼り付けて Enter:

```
! security find-generic-password -s notion-api-key.<keychain-prefix> -a <keychain-prefix> >/dev/null 2>&1 && echo "Notion: 登録OK" || echo "Notion: 未登録"; security find-generic-password -s gbizinfo-api-token.<keychain-prefix> -a <keychain-prefix> >/dev/null 2>&1 && echo "gBizINFO: 登録OK" || echo "gBizINFO: 未登録"; security find-generic-password -s japanpost-da-api.<keychain-prefix> -a client_id >/dev/null 2>&1 && echo "日本郵便: 登録OK" || echo "日本郵便: 未登録(郵便番号は空欄になります)"
```

> **すべて「登録OK」** と出れば成功です(日本郵便は郵便番号取得を使う場合のみ必須)。
> 途中で Mac の許可ポップアップが出たら **「常に許可」** を選ぶと、次回から出ません。

### 5-4. Notion のデータベースに連携を「接続」する(ブラウザでクリック操作)

トークン登録だけでは Notion 側が書き込みを許可していません。下記をクリックで接続します。社内共有DBで自分に接続権限がない場合は、DB管理者に「この Integration を Connections に追加してください」と依頼してください。

1. ブラウザで、情報を貯める **Notion のデータベース(一覧表)のページ** を開く
2. 右上の **「…」(三点メニュー)** をクリック
3. **「コネクト(Connections)」→「接続を追加」** を選ぶ
4. 手順 3 で作った **自分の Integration(連携)** を選んで追加

> これを忘れると、後で「権限がありません(401/403)」エラーになります。

### 5-5. (任意)安全設定を有効にする

トークンが誤って画面に出たり削除されたりするのを防ぐ追加設定です。
**未設定でも守られます**: プラグインに同梱の動的ガード(`hooks/hook-guard-secret.py`)が単独で、トークンの平文出力・誤削除を機械的にブロックします(install 時に自動で有効)。
さらに静的な防御層(`settings.json` の deny リスト)も足したい場合は、Code タブで「**company-master の安全設定(settings-hardening)を適用して**」と頼んでください(プラグイン同梱の `references/settings-hardening.json` を `$CLAUDE_PLUGIN_ROOT` から読み取り、あなたの `.claude/settings.json` へマージする手順を案内します)。背景: [`references/README-setup.md`](references/README-setup.md)。

---

## 6. ステップB: プラグインのインストール(Code タブで実行)

> Claude Desktop の **設定画面ではなく、Code タブのチャット欄** で行います(独自プラグインは設定画面から追加できないため)。

### 6-1. マーケットプレイスを登録する(GitHub の公開リポジトリ・clone 不要)

Code タブのチャット欄に次を入力して Enter:

```
/plugin marketplace add OWNER/harness
```

> これは **GitHub 上の公開リポジトリ** `OWNER/harness` をマーケットプレイスとして登録するコマンドです(`owner/repo` の短縮形)。**リポジトリを自分のPCに clone する必要はありません**。
> うまくいかないときは、フル URL でも登録できます: `/plugin marketplace add https://github.com/OWNER/harness`
>
> <details><summary>(上級者・開発者向け)このリポジトリを clone 済みの場合</summary>
>
> 既にローカルに clone してそのフォルダを Code タブで開いているなら、ローカルをマーケットプレイス登録することもできます:
> `/plugin marketplace add .`(`.` は Code タブで開いているフォルダ。直下に `.claude-plugin/marketplace.json` が必要)
> </details>

### 6-2. プラグインをインストール

```
/plugin install company-master@harness
```

> 画面の指示に従って許可すればインストールされます。
> メニューから選びたい場合は、`/plugin` だけ入力すると一覧メニューが開きます。

### 6-3. 入ったか確認

```
/plugin list
```

> 一覧に **`company-master`** が表示されれば成功です。
> (配布対象のプラグインをまとめて入れたい場合は、`/plugin install <name>@harness` を 1 つずつ繰り返してください。`/install-bundle harness-full`（clone 環境の project-local command）や `bash scripts/install-bundle.sh harness-full` といった bundle 一括導入は、harness-creator が配布対象外のため **repo を clone した開発環境でのみ**使えます。company-master を単独で使うならこの手順は不要です。)

### 6-4. プラグインを読み込み直す

```
/reload-plugins
```

> インストール直後や更新後は、このコマンドで現在の Code タブに反映します。読み込み後、`/plugin list` または `/plugin` の Installed 画面で `company-master` の commands / skills が表示されることを確認してください。

---

## 7. ステップC: 使い方(毎回・Code タブで)

### 7-1. いちばん簡単: チャットで話しかける

Code タブの入力欄に、ふつうの言葉で伝えるだけです。

| やりたいこと | 話しかけ例 |
|---|---|
| 会社を調べて Notion に登録 | 「株式会社サンプルを調べて企業マスタに登録して」 |
| 住所だけ分かっている | 「東京都千代田区丸の内1-1 の会社を調べて」 |
| 法人番号から調べる | 「法人番号 1234567890123 の会社情報を埋めて」 |

> 同じ名前の会社が複数見つかった場合や住所だけで1社に絞れない場合は、Claude が **候補一覧を出して「どれですか?」と聞きます**。選ぶだけでOKです。確実に決められないものは無理に登録せず「未確定(要確認)」で保留します。

### 7-2. コマンドで実行する

Code タブの入力欄に:

```
/company-master:company-master --name "株式会社サンプル" --address "東京都千代田区..." --upsert
```

- `--name`(会社名) / `--address`(住所) / `--hojin-bango`(法人番号)のいずれかを指定
- **`--upsert` を付けたときだけ Notion に書き込みます**。付けないと「調べるだけ(書き込まない)」
- まず `--upsert` なしで確認 → 良ければ `--upsert` 付きで本登録、が安全です
- plugin 由来のコマンドは名前空間付きです。もし `/company-master` で動かない場合は `/company-master:company-master` を使ってください

### 7-3. Notion の空欄をまとめて補完する(backfill)

```
/company-master:company-master-backfill --dry-run
```

- `--dry-run` は **書き込まず、対象行だけ確認** するお試しモード
- 想定どおりなら `--dry-run` を外して本実行
- すでに値が入っているセルは **上書きしません**(空欄だけ埋めます)

### 7-4. 結果の見方

- **「情報の確かさ」** が「ネット検索(要確認)」「未確定(要確認)」の行は、人の目で確認すると安心
- **ページ本文の「確認用URL（手動検証用）」** … ネット検索で調べた値の根拠ページ。企業ページを開くと本文に出ます。クリックして正誤を確認できます
- **「備考」** … 取れなかった項目の理由が定型文で入ります(例:「【取得失敗】電話番号: …」)

---

## 8. 最初の動作確認(おすすめ)

いきなり本登録せず、まず doctor と1社の「書き込みなし」で試すと安心です。

1. Code タブで「company-master の doctor を実行して」と伝える
2. FAIL があれば表示された次アクションを直す。WARN/SKIP は内容を確認する(日本郵便未設定の WARN は郵便番号だけ空欄になるという意味)
3. 郵便番号も自動取得したい場合は「company-master の doctor --probe を実行して」と伝え、本番接続と実疎通を確認する
4. Code タブで「`株式会社サンプル` を調べて。まだ Notion には書き込まないで」と伝える
5. 出てきた結果(正式名称・住所・郵便番号など)が正しそうか目で確認する
6. 問題なければ「では Notion に登録して」と伝える(または `--upsert` 付きで実行)
7. Notion のデータベースに行が追加され、各列が埋まっていることを確認する

---

## 9. うまくいかないとき

まずは **一括診断 (doctor)** を実行すると、どこでつまずいているかを 1 回でまとめて確認できます。Code タブのチャット欄に:

```
company-master の doctor(セットアップ診断)を実行して
```

> これだけで OK です(プラグインが `$CLAUDE_PLUGIN_ROOT` 配下の正しいパスで doctor を実行します)。
> (このリポジトリを clone 済みの開発者は、`! python3 "$CLAUDE_PLUGIN_ROOT/scripts/company_master.py" doctor` を直接実行してもOK。clone していない通常利用者は**手打ちせず**上のチャット指示を使ってください。`! python3 plugins/company-master/...` という素のパスは clone した人の作業フォルダでしか動きません)

> doctor は「トークン2つの登録 / 書き込み先データベースの設定 / Notion への接続と列構成の一致 / 安全設定の適用」を順に点検し、各項目を **OK / WARN / FAIL / SKIP** と「次に何をすべきか」付きで日本語表示します(トークンの中身は表示しません)。FAIL の項目だけ、表示された次アクションを実施してください。

| 症状 | 原因と対処 |
|---|---|
| 設定(Settings)画面にプラグインが見つからない | 独自プラグインは設定画面からは追加できません。**Code タブで** 手順 6 のコマンドを使ってください |
| `/plugin marketplace add OWNER/harness` でエラー | ネット接続を確認のうえ、フル URL を試す: `/plugin marketplace add https://github.com/OWNER/harness`。GitHub の公開リポジトリなので認証は不要 |
| `/plugin marketplace add .`(開発者向け)でエラー | clone 済みの人向けのローカル方式。`.` の代わりにフォルダのフルパスを指定するか、Code タブで開いているフォルダ直下に `.claude-plugin/marketplace.json` があるか確認。**通常はリモート方式(上の行)を使えば clone 不要** |
| `/company-master` が動かない | plugin 由来コマンドは名前空間付きになるため、`/company-master:company-master` または `/company-master:company-master-backfill` を使う。インストール直後なら `/reload-plugins` も実行 |
| `! python3 plugins/company-master/...` が `No such file or directory` で失敗 | clone していない人が**リポジトリ相対パスを手打ち**すると出ます(マーケットプレイス導入ではスクリプトは別の場所に展開されます)。**手打ちせず**、Code タブで「**doctor を実行して**」「**会社を調べて**」のように日本語で頼んでください(プラグインが正しいパスで実行します) |
| `gBizINFO トークン不在` で止まる | 手順 5-2 が未実施、または綴り違い。手順 5-3 の確認で「登録OK」になるか確認 |
| Notion で「権限がありません(401/403)」 | 手順 5-4 の「接続」が未実施。データベースに Integration を接続したか確認 |
| トークンを入れ直したい | 手順 5-1 / 5-2 と同じ手順をもう一度行えば上書き登録されます |
| `BLOCKED: ... find-generic-password -w` と出る | 安全装置が「トークンの中身の表示」を止めた正常動作です。中身を画面に出す必要はありません |
| 実行中に Mac の許可ポップアップが出る | キーチェーンへのアクセス確認です。「常に許可」を選ぶと次回から出ません |
| 同名の会社が多すぎる/住所だけで絞れない | 仕様どおりです。候補から選ぶか、保留(未確定)のまま後で確認してください |
| 郵便番号がいつも空欄で、備考に「日本郵便APIの認証に失敗」と出る | 日本郵便 addresszip API の鍵未登録か、送信元IPが for Biz 登録値とズレています。[`references/japanpost-api-setup.md`](references/japanpost-api-setup.md) の手順で client_id/secret_key を Keychain `japanpost-da-api.<keychain-prefix>` に登録し、Code タブで「**doctor を実行して**」と頼んで表示される送信元IPを日本郵便 for Biz に登録してください(IPは自動検出。固定したいときだけ Keychain `egress_ip` に pin)。「**doctor --probe を実行して**」で実疎通と登録IPとのズレを確認できます |
| 郵便番号が空欄で、備考に「日本郵便APIへの通信に失敗」と出る | ネットワーク不達か日本郵便側の一時障害です。時間をおいて再実行してください。誤った郵便番号は入れず空欄+備考で保留する設計です |
| 送信元IPを固定できない / 頻繁に変わる | 当チームの既定は **BYO 直結**(各メンバーが自分の for Biz 鍵+送信元IP)。固定IP回線なら `egress_ip` を pin すれば安定します。**どうしても送信元IPを固定できないメンバーだけ**、例外的に**鍵と固定IPを1台に集約する中央プロキシ**を立て、そのメンバーは `proxy_url`/`proxy_token` だけ設定します。手順: [`references/postal-proxy-deploy.md`](references/postal-proxy-deploy.md) |

---

## 10. 技術的な詳細(エンジニア向け)

- セットアップのコマンド詳細・トラブルシュート: [`references/README-setup.md`](references/README-setup.md)
- 仕様(何を・どう処理するか)の正本: [`skills/run-company-master-build/SKILL.md`](skills/run-company-master-build/SKILL.md)
- Notion の列定義: [`references/company-master-columns.md`](references/company-master-columns.md)
- 取得元(gBizINFO / 日本郵便 / ネット検索)と確かさの基準: [`references/data-sources.md`](references/data-sources.md)

> 改善要望は Code タブで「`company-master` の○○を直してほしい」と**ふつうの言葉で伝えてください**(単独インストールでもこれだけで投入できます)。
> (開発者が repo を clone し harness-creator を使う環境では `/run-skill-feedback company-master` でも投入できます。`run-skill-feedback` は harness-creator 側に同梱されており、harness-creator は配布対象外 (`distributable: false`) のため、company-master を配布 install しただけのユーザはこのスラッシュコマンドを使えません。)

---

## 出典(Claude Desktop / プラグインの最新仕様)

- [Claude Code Docs — Desktop application](https://code.claude.com/docs/en/desktop)
- [Claude Code Docs — Get started with the desktop app](https://code.claude.com/docs/en/desktop-quickstart)
- [Claude Code Docs — Discover and install prebuilt plugins through marketplaces](https://code.claude.com/docs/en/discover-plugins)
- [Claude Code Docs — Create and distribute a plugin marketplace](https://code.claude.com/docs/en/plugin-marketplaces)
- [Claude Code Docs — Plugins reference](https://code.claude.com/docs/en/plugins-reference)
