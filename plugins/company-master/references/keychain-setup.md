# Keychain 鍵セットアップ (チームメンバー向けオンボーディング)

> このプラグインが使う秘密情報・設定は **env ファイルではなく macOS Keychain** に置く。本書は「自分の
> マシンでどの鍵を登録すればよいか」を**ロール別**にまとめた、チーム配布用の手順正本。背景や API キーの
> 取得方法は `japanpost-api-setup.md` (BYO / 日本郵便鍵取得)、送信元IPを固定できない例外運用は
> `postal-proxy-deploy.md` (中央プロキシ) を参照。

> **パスについて**: 本書の `security add-generic-password` / `find-generic-password`(鍵の登録・存在確認)は **パスに依存せず**、clone の有無に関わらずそのまま使える。一方 `python3 plugins/company-master/scripts/...`(doctor 等)は **repo を clone した開発者向け**の書き方。マーケットプレイスから install した通常利用者は、doctor を Code タブで「**doctor を実行して**」と日本語で頼む(プラグインが `$CLAUDE_PLUGIN_ROOT` で自己解決。[`japanpost-api-setup.md`](japanpost-api-setup.md) ⑥ と共通方針)。

## 配布モデル: BYO 直結が既定

> 当チームの既定は **BYO 直結 (Bring Your Own credentials)**。
> **各メンバーが自分の for Biz アカウント・`client_id`/`secret_key`・送信元IP を用意し、日本郵便 API を直接叩く**。
> 日本郵便のIP許可リストは「1鍵あたり最大10件」だが、BYO では**各メンバーが自分の鍵を持つ**ため、この10件制約は各自の鍵の中で完結し問題にならない。
>
> 送信元IPは既定で**自動検出**される (`doctor` が登録すべき IP を表示する)。**固定IP回線のメンバーは `egress_ip` に pin して `x-forwarded-for` を確定**させるのが堅牢 (下記 A-5)。
> どうしても送信元IPを固定できない／頻繁に変わる環境のメンバーだけ、**例外的に**中央プロキシ (`postal-proxy-deploy.md`) を使う。

## まず自分のロールを確認する

| ロール | 何をする人か | 実施する節 |
|---|---|---|
| **チームメンバー (BYO直結・既定)** | 各自のローカル Claude Code でこのプラグインを使う人 | **A** |
| **(例外) プロキシ運用者** | 送信元IPを固定できないメンバー向けに、固定IPサーバで中央プロキシ (`postal_proxy.py`) を立て鍵を集約する人 | **C**（+ デプロイは `postal-proxy-deploy.md`） |

---

## A. チームメンバーが自分の Keychain に登録する鍵 (BYO直結)

郵便番号は**自分の for Biz 鍵で直接取得**する。各メンバーは次を登録する。`-w` を**値なし**で実行すると
対話入力になり、トークンがコマンド履歴/ログに残らない（secret は必ずこの方式で貼り付ける）。

```bash
# 1. Notion 連携トークン (企業マスタDBへの書き込み用)
security add-generic-password -U -s notion-api-key.<keychain-prefix> -a <keychain-prefix> -w
#    ↑ 実行後プロンプトに Notion インテグレーショントークンを貼り付けて Enter

# 2. gBizINFO トークン (会社名/法人番号 → 正式名称・住所の取得用)
security add-generic-password -U -s gbizinfo-api-token.<keychain-prefix> -a <keychain-prefix> -w

# 3. 日本郵便 client_id (公開寄り。値を直接渡してよい)
security add-generic-password -U -s japanpost-da-api.<keychain-prefix> -a client_id -w '<あなたのclient_id>'

# 4. 日本郵便 secret_key (初回のみ表示。対話入力で履歴に残さない)
security add-generic-password -U -s japanpost-da-api.<keychain-prefix> -a secret_key -w
#    ↑ 実行後プロンプトに secret_key を貼り付けて Enter
```

> Keychain 命名規約: 日本郵便だけ**1サービス `japanpost-da-api.<keychain-prefix>` に複数アカウント** (`client_id` / `secret_key` / `egress_ip` …) をぶら下げる方式 (Notion/gBizINFO の `<service>.<keychain-prefix>` + account `<keychain-prefix>` 方式とは異なる)。この綴りは `scripts/notion_config.py` とフックに固定されているため**変更不可**。

### A-5. (固定IPなら推奨) 送信元IP を pin する

固定IP回線のメンバーは、**for Biz に登録したのと同じIP**を `egress_ip` に pin しておくと、自動検出の揺れに依存せず
`x-forwarded-for` が常にそのIPで送られる (バックグラウンド/cron 実行でも確実)。

```bash
security add-generic-password -U -s japanpost-da-api.<keychain-prefix> -a egress_ip -w '<for Biz に登録した固定IP>'
```

> 動的IPのメンバーは pin 不要 (既定の自動検出に任せる)。ただしIPが変わったら for Biz で再登録が要る (`doctor --probe` が不一致を検知)。固定できない環境はC節の中央プロキシを検討。

### 送信元IP を for Biz に登録する (BYO 必須)

各メンバーは**自分の送信元グローバルIP**を、自分の for Biz システムに登録する (最大10件)。登録すべきIPは:

```bash
python3 "${CLAUDE_PLUGIN_ROOT:-plugins/company-master}/scripts/company_master.py" doctor   # 「送信元IP」行に自動検出値が出る
```

の値をそのまま for Biz に登録するのが確実 (固定IPなら A-5 で pin した値と一致する)。

### 登録できたか確認 (中身は表示しない)

```bash
security find-generic-password -s notion-api-key.<keychain-prefix>    -a <keychain-prefix>   >/dev/null 2>&1 && echo "Notion: OK"      || echo "Notion: 未登録"
security find-generic-password -s gbizinfo-api-token.<keychain-prefix> -a <keychain-prefix>   >/dev/null 2>&1 && echo "gBizINFO: OK"    || echo "gBizINFO: 未登録"
security find-generic-password -s japanpost-da-api.<keychain-prefix>            -a client_id    >/dev/null 2>&1 && echo "client_id: OK"   || echo "client_id: 未登録"
security find-generic-password -s japanpost-da-api.<keychain-prefix>            -a secret_key   >/dev/null 2>&1 && echo "secret_key: OK"  || echo "secret_key: 未登録"
```

登録後、Claude Code のチャットで「**doctor を実行して**」と言えば総合診断が走る（`company_master.py doctor`）。
「**郵便番号取得モード: BYO 直結**」と表示され FAIL が無ければ完了。`doctor --probe` で実 API 疎通 (登録IPとのズレ) まで確認できる。
あとは「〇〇社の郵便番号を取得して」で使える。

---

## C. (例外) プロキシ運用者がプロキシサーバ側に登録する鍵

> 送信元IPを固定できないメンバーがいる場合の**例外運用**。固定IPサーバで中央プロキシを立て、そのメンバーは
> `proxy_url`/`proxy_token` だけ登録する (日本郵便の鍵を持たない)。デプロイ全体は `postal-proxy-deploy.md` が正本。

固定IPサーバ上で実施。**日本郵便の本物の鍵はここだけに置く**。

```bash
# 日本郵便 for Biz で取得した本番システムの鍵
security add-generic-password -U -s japanpost-da-api.<keychain-prefix> -a client_id  -w 'for Biz の client_id'
security add-generic-password -U -s japanpost-da-api.<keychain-prefix> -a secret_key -w          # 対話入力 (初回のみ表示)
# プロキシ利用メンバーに配る通行トークン (各メンバーの proxy_token に同じ値を入れてもらう)
security add-generic-password -U -s japanpost-da-api.<keychain-prefix> -a proxy_token -w
```

プロキシ利用メンバー側 (BYO の代わりに):

```bash
security add-generic-password -U -s japanpost-da-api.<keychain-prefix> -a proxy_url   -w 'https://<チームのプロキシ>/addresszip'
security add-generic-password -U -s japanpost-da-api.<keychain-prefix> -a proxy_token -w          # 管理者から共有された値
```

- このサーバの**固定送信元IP**を for Biz に登録する（`doctor` の「送信元IP」行に表示される IP）。
- Keychain の無い Linux/コンテナでは env で供給する（`postal-proxy-deploy.md`）:
  `COMPANY_MASTER_JAPANPOST_CLIENT_ID` / `COMPANY_MASTER_JAPANPOST_SECRET_KEY` / `COMPANY_MASTER_POSTAL_PROXY_TOKEN`。

---

## (補助) Mac で自分の送信元(グローバル)IP を調べる

for Biz に登録する／`egress_ip` に pin するのは「**外から見える出口(グローバル)IP**」。Mac での調べ方:

```bash
# ① 送信元グローバルIP (for Biz 登録・egress_ip pin 用はこれ)
curl -s https://api.ipify.org; echo
#   別サービスでも可:  curl -s https://ifconfig.me; echo  /  curl -s https://checkip.amazonaws.com

# ② プラグインの自動検出値を表示 (doctor の「送信元IP」行に同じ IP が出る)
python3 "${CLAUDE_PLUGIN_ROOT:-plugins/company-master}/scripts/company_master.py" doctor
```

注意:
- **LAN内の私的IP は使えない**。`ipconfig getifaddr en0`(Wi-Fi) や「システム設定 > ネットワーク」に出る `192.168.x.x` / `10.x.x.x` は**ルータ内部の私的IP**で、日本郵便ゲートウェイには届かない。登録すべきは上記①の**グローバルIP**。
- **家庭/オフィス回線は動的のことが多い**（ISP が定期的に変える）。① を時間をおいて2回実行して変われば動的。動的なら IP 変動のたび for Biz 再登録が要る (固定できない環境はC節の中央プロキシ)。
- プラグインは既定で①を**自動検出**して `x-forwarded-for` に使うので、BYO でも「自分のIPを毎回調べて env に入れる」必要はない（固定IPなら A-5 で pin するとさらに確実）。

## セキュリティ (重要)

- **日本郵便の `secret_key` は他人に配らない**（各メンバーが自分の鍵を持つ。プロキシ運用時はプロキシ1台のみ）。`proxy_token` は身内チーム内で共有可（漏れたら作り直す）。
- これらの鍵の**平文出力**（`security find-generic-password ... -w`）・**削除**（`delete-generic-password`）は、`hooks/hook-guard-secret.py`（動的層）と `references/settings-hardening.json`（静的層）の二段防御が `notion-api-key.<keychain-prefix>` / `gbizinfo-api-token.<keychain-prefix>` / `japanpost-da-api.<keychain-prefix>` の3サービスについて機械的に block する。**登録 (`add`) は許容**。
- 値をコマンド引数に直書きすると履歴に残るため、secret は `-w` を空にした**対話入力**を使う。
