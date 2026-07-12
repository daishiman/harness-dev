# party_a SSOT (甲固定値の単一情報源)

甲 (発注者) の固定値は本プラグイン全体で**ハードコード禁止**。`lib/config_auth.load_party_a()` を経由して取得する。

## 優先順位 (4 層)

| 優先 | 経路 | 用途 |
|---|---|---|
| 1 | 環境変数 `PARTY_A_JSON_PATH` 指定の JSON ファイル | 一時上書き / テスト |
| 2 | `~/.config/contract-generator/party_a.json` | ユーザ環境固有(正本・google-config.json と同居) |
| 3 | `~/.config/tenant/party_a.json` | 後方互換(旧運用者) |
| 4 | `references/party_a.default.json` (プラグイン同梱) | デフォルト = サンプル株式会社 |

上の層から順に解決し、最初に見つかったものを採用する (マージはしない)。

## スキーマ

```json
{
  "name": "サンプル株式会社",
  "address": "山形県鶴岡市北京田字下鳥ノ巣23-1",
  "representative": "代表取締役 坂本 大典",
  "title": "代表取締役",
  "rep_name": "坂本 大典"
}
```

## 上書き方法

### 一時 (環境変数)

```bash
export PARTY_A_JSON_PATH=/tmp/party_a-override.json
```

### 永続 (ユーザ環境)

```bash
CONFIG_DIR="${XDG_CONFIG_HOME:-$HOME/.config}/contract-generator"; mkdir -p "$CONFIG_DIR"
cp plugins/contract-generator/references/party_a.default.json "$CONFIG_DIR/party_a.json"
# 値を編集(ホーム配下なのでプラグイン更新で消えない)
```

## 差込テンプレ変数 (template-mapping.json 連動)

差込時は `{{party_a.name}}` `{{party_a.address}}` `{{party_a.representative}}` `{{party_a.title}}` `{{party_a.rep_name}}` の形で参照する。`docx_fill` 側は `config_auth.load_party_a()` が返す dict をテンプレ変数に展開する。
