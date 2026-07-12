# 郵便番号 中央プロキシ デプロイ手順 (不特定多数・多拠点配布向け)

> 利用者の送信元IPがバラバラで日本郵便のIP許可リスト(1鍵あたり最大10件)に収まらない場合、各クライアントが
> 直接日本郵便を叩く方式は API 仕様上成立しない。**鍵と固定送信元IPをプロキシ1台に集約**し、各クライアントは
> `proxy_url`(+任意 `proxy_token`)だけ設定して郵便番号を引く。実装は `scripts/postal_proxy.py`(標準ライブラリのみ)。

> **対象読者**: 本書は **送信元IPを固定できないチーム向けの例外運用**を立てる「プロキシ運用者」だけが読む上級者向け手順。プロキシ運用者は**サーバ上にこのリポジトリ(または該当スクリプト)を配置して**起動するため、以下の `python3 plugins/company-master/scripts/...` は **そのチェックアウト先からの相対パス**として実行する(一般の利用者は本書を読む必要はなく、Code タブで使うだけ)。クライアント側の設定は §「クライアント側設定」の `security ...`(パス非依存)のみ。

## 全体像

```
[多拠点の各クライアント (鍵なし・IP登録なし)]
   plugin: Keychain japanpost-da-api.<keychain-prefix>/proxy_url(+proxy_token) のみ
        │  POST {pref_name/city_name/town_name または freeword}  (+ Bearer proxy_token)
        ▼
[あなたのプロキシ 1台 (固定グローバルIP)]
   postal_proxy.py: Keychain japanpost-da-api.<keychain-prefix>/client_id,secret_key を保持
   日本郵便に登録する送信元IP = このサーバの出口IP 1件
        │  token 発行 (x-forwarded-for=自IP) → addresszip 代行
        ▼
[日本郵便 addresszip API]   ← 登録IPはプロキシの1件だけでよい
```

ポイント: **日本郵便への登録(鍵1組 + 送信元IP)はプロキシ側で1回だけ**。クライアントは無限に増えてよい。

## サーバ側セットアップ

1. **固定グローバルIPの実行環境を用意**: VPS、または Cloud Run + Cloud NAT(固定IP)、固定IPの出る FaaS 等。出口IPが安定することが必須(日本郵便に登録するIPになる)。
2. **日本郵便 for Biz 登録**: client_id/secret_key を取得し、**このサーバの出口IP**を送信元IPとして登録する(手順は `references/japanpost-api-setup.md`)。出口IPは `curl -s https://api.ipify.org` か、プロキシ起動後 `python3 scripts/postal_api.py` の自動検出ログで確認できる。
3. **鍵をサーバ側 Keychain (または env) に保存**:
   ```bash
   # macOS のサーバなら Keychain
   security add-generic-password -U -s japanpost-da-api.<keychain-prefix> -a client_id  -w '<client_id>'
   security add-generic-password -U -s japanpost-da-api.<keychain-prefix> -a secret_key -w
   # Linux コンテナ等 Keychain が無い環境は env (秘密管理機構経由を推奨)。
   # 下記 2 変数は notion_config.get_japanpost_credentials が Keychain 不在時に読む正式フォールバック。
   export COMPANY_MASTER_JAPANPOST_CLIENT_ID='<client_id>'
   export COMPANY_MASTER_JAPANPOST_SECRET_KEY='<secret_key>'   # シークレットマネージャ/マウント経由で供給推奨
   ```
   > Linux/コンテナで Keychain が無い場合、`notion_config._keychain_password` は None を返し、`get_japanpost_credentials` は env `COMPANY_MASTER_JAPANPOST_CLIENT_ID` / `COMPANY_MASTER_JAPANPOST_SECRET_KEY` を正式フォールバックとして読む(本参照実装は macOS Keychain を優先するが、これらの env を Keychain 不在時の解決経路として明示サポートする)。シークレットマネージャ等から env / マウントで供給する運用に合わせること。
4. **通行トークンを設定 (公開環境では必須)**: 無認証だと誰でも叩ける踏み台になる。
   ```bash
   security add-generic-password -U -s japanpost-da-api.<keychain-prefix> -a proxy_token -w '<長いランダム文字列>'
   # または env: export COMPANY_MASTER_POSTAL_PROXY_TOKEN='<...>'
   ```
5. **レート制限 (任意)**: `POSTAL_PROXY_RATE_PER_MIN`(既定60/分/IP)。本格運用は前段に WAF / API Gateway を置く。
6. **起動**:
   ```bash
   python3 plugins/company-master/scripts/postal_proxy.py --port 8080
   # GET /healthz で死活確認、POST /addresszip が検索エンドポイント
   ```

## クライアント側設定 (各ユーザ)

各ユーザは**日本郵便の鍵もIP登録も不要**。プロキシの URL(+トークン)を Keychain に入れるだけ:

```bash
security add-generic-password -U -s japanpost-da-api.<keychain-prefix> -a proxy_url   -w 'https://your-proxy.example.com/addresszip'
security add-generic-password -U -s japanpost-da-api.<keychain-prefix> -a proxy_token -w '<サーバと同じトークン>'   # プロキシが認証する場合
```

`proxy_url` が設定されていれば `postal_api.lookup_postal` は自動でプロキシ経由になる(`company_master.py doctor` が「郵便番号取得モード: 中央プロキシ経由」と表示)。`doctor --probe` でプロキシ経由の実疎通を確認できる。

## 確認

```bash
# クライアントから
python3 plugins/company-master/scripts/company_master.py doctor --probe
#   → 「郵便番号取得モード: 中央プロキシ経由」+「日本郵便 API 実疎通: ... OK」
```

## 留意

- **鍵はクライアントに配らない**。クライアントが持つのは proxy_url と(任意の)proxy_token のみ。
- 郵便番号検索は公開データだが、無認証プロキシは踏み台化・コスト増を招く。`proxy_token` + レート制限で必ず保護する。
- 出口IPが変わると日本郵便側で 401 になる。固定IP環境を使い、変わったら for Biz で再登録する。
- プロキシは `postal_api` の token 発行/IP認証/addresszip 呼び出しをそのまま再利用するため、直叩きと挙動が一致する(二重実装なし)。
