# run-contract-generate セットアップ手順 (スキル内部参照用の技術要約)

> ⚠️ **セットアップ手順の正本は plugin 直下 `README.md`(Task 0-14)** です。Drive ID・SA メール・Keychain 命名規約・Slack 設定・トラブルシュートの完全版はそちらを参照してください。
> 本書は重複を避け、コマンドの最小列と、README に無い技術情報(CI/pre-commit 配線・template-mapping 二重定義注意)だけを残したスキル内部参照用の要約です。
> 環境依存値(Drive ID 等)は README.md と `google-config.json` に一本化し、本書には実値を複製しません(2 箇所以上にコピーすると更新時の整合崩壊リスクが上がるため)。

本スキルは Google Drive / Sheets へ **Service Account(SA)** でアクセスする。
API キー等の機密は **macOS Keychain** に保管し、環境依存ID は `google-config.json`(正本=`~/.config/contract-generator/`・ホーム配下で git 管理外)に置く。
以下を**一度だけ**実施すればよい(`<PROJECT_ID>` 等は自分の値に置換)。

> ⚠️ **手動コマンドを使う場合のみ**、作業ディレクトリ(cwd)を plugin ルートに固定する。
> 導入後の plugin 実体は `~/.claude` 配下(例 `~/.claude/plugins/contract-generator/`)、開発リポジトリなら `plugins/contract-generator/`。
> 以降の `python3 lib/...` / `cp skills/.../sample ...` は全てこの cwd 起点(plugin 直下 `README.md` Quickstart と同一起点)。
> 日常運用(対話駆動)では cwd は問われない(`$CLAUDE_PLUGIN_ROOT` 経由で解決)。
> ```bash
> cd <このリポジトリのパス>/plugins/contract-generator
> ```

> Keychain 命名規約(将来の Google Drive 連携でも一意・衝突なし):
> **service = `gdrive-service-account.<keychain-prefix>`** 固定、**account = `<用途>/<資格情報種別>`**。
> 本スキルは `account = contract-generate/service-account-json`。
> 例: 別連携を足すなら `account = invoice-sync/oauth-refresh-token` のように用途で分岐する。

---

## 0. 前提ツール(pip install は不要)

このスキルは **Python 標準ライブラリだけで動作**する(`pip install` 一切不要)。
.docx編集は `docx_lib`(zipfile+xml.etree)、Google Drive/Sheets は `urllib` REST、認証は gcloud CLI のトークン取得で実装済み。

```bash
python3 --version    # 3.11 以上であればOK
# gcloud CLI(認証トークン取得に使用・未導入なら) : https://cloud.google.com/sdk/docs/install
gcloud --version
```

## 1. GCP プロジェクトで API を有効化

```bash
gcloud config set project <PROJECT_ID>
gcloud services enable drive.googleapis.com sheets.googleapis.com
```

> Docs API は使わない(PDF は Drive の Google Docs 変換→export で生成するため)。

## 2. Service Account の作成と鍵の発行

```bash
# SA 作成
gcloud iam service-accounts create xl-contract-sa \
  --display-name "XL Contract Generator"

# SA の鍵(JSON)をローカルに一時発行
gcloud iam service-accounts keys create /tmp/xl-contract-sa.json \
  --iam-account "xl-contract-sa@<PROJECT_ID>.iam.gserviceaccount.com"

# SA のメールアドレスを控える(後でフォルダ/台帳の共有に使う)
echo "xl-contract-sa@<PROJECT_ID>.iam.gserviceaccount.com"
```

## 3. 鍵 JSON を Keychain に登録(平文ファイルは即削除)

```bash
# 鍵 JSON 全体を Keychain の generic-password として保存(-U で既存を上書き更新)
security add-generic-password \
  -s gdrive-service-account.<keychain-prefix> \
  -a "contract-generate/service-account-json" \
  -w "$(cat /tmp/xl-contract-sa.json)" \
  -U

# 一時ファイルを確実に削除
rm -P /tmp/xl-contract-sa.json
```

登録できたか確認(トークンはマスク表示):

```bash
CLAUDE_HOOK_INVOKED=1 python3 lib/keychain_get_secret.py \
  --service gdrive-service-account.<keychain-prefix> \
  --account "contract-generate/service-account-json" --check
# => OK {"ty... (len=...)
```

> 更新したいとき: 同じ `add-generic-password ... -U` を再実行すれば上書きされる。
> 削除したいとき: `security delete-generic-password -s gdrive-service-account.<keychain-prefix> -a "contract-generate/service-account-json"`

## 4. Drive フォルダ・管理台帳を SA に共有(編集者)

SA はあなたのファイルを**共有された分しか**見られない。共有対象(ひな形/出力親/個人/法人フォルダ・管理台帳)の各 ID と権限の一覧は **plugin 直下 `README.md` Task 5 の共有表が正本**。そこに記載の各 ID を **SA メール(`xl-contract-sa@<PROJECT_ID>.iam.gserviceaccount.com`)に「編集者」**(ひな形のみ閲覧者でも可)で共有する。

> 機微情報(乙住所/代表者/口座)を含むため、共有相手は最小限にすること(「全般アクセス」は「制限付き」のまま、SA メールだけを追加する)。

## 5. `google-config.json` を作成(ホーム配下・git管理外)

`references/google-config.sample.json` をコピーして、`~/.config/contract-generator/google-config.json` を作る(cwd=`plugins/contract-generator/`。コマンドは plugin 直下 `README.md` Task 10 と同一。ホーム配下なのでプラグイン更新で消えない。旧リポジトリルートの `.google-config.json` も後方互換で読める):

```bash
CONFIG_DIR="${XDG_CONFIG_HOME:-$HOME/.config}/contract-generator"; mkdir -p "$CONFIG_DIR"
cp skills/run-contract-generate/references/google-config.sample.json "$CONFIG_DIR/google-config.json"
# プレースホルダ(<SPREADSHEET_ID> 等の環境依存ID)と slack_channel を自分の値に置換。
```

> keychain_service / keychain_account / slack_keychain_* は命名規約で固定の既定値のため置換不要(本書「Keychain 命名規約」節が正本)。

## 6. 疎通確認

```bash
python3 lib/config_auth.py --check
# => 先頭が「OK config=<path>」、続けて「gcloudトークン取得・Sheets台帳/個人/法人フォルダ到達OK(REST)」と「Slack: <状態>」を表示すれば成功
```

## 7. 実行

```bash
# 個人・法人の「作成指示◯」かつ未完了行をすべて生成 (draft フェーズ)
python3 lib/engine.py --phase draft --type all

# まず安全に検証(台帳書込・Drive保存をしない)
python3 lib/engine.py --phase draft --type all --dry-run

# 特定行のみ
python3 lib/engine.py --phase draft --type individual --row 3
```

---

## トラブルシュート

| 症状 | 原因 / 対処 |
|---|---|
| `Keychain lookup failed` | 手順3未実施 / service・account 名の綴り違い |
| `403 insufficient permissions` | 手順4のSA共有漏れ。対象ID(フォルダ/台帳)をSAメールに共有 |
| `API has not been used` | 手順1の API 有効化漏れ |
| 生成Docに `●`/`XXXX` が残る | 台帳の対応列が空。`validate.py` の必須非空チェックを確認 |
| 黄色が出ない/消えない | Docs版=黄色維持、PDF版=黄色除去。`docx_fill.py` の二系統出力を確認 |

---

## CI / pre-commit 配線

本プラグインの自己検査入口は `plugins/contract-generator/scripts/run-tests.sh` に集約済み (manifest lint + lib AST parse + check_intermediate dry-run + import smoke + 設定SSOT lint + template mapping scan の 6 段。最後の scan は config 存在時のみ実行)。
リポジトリ全体の CI からは下記のように呼び出す。重い yml 構造変更は本作業のスコープ外で、雛形提示に留める。

### GitHub Actions (.github/workflows/contract-generator.yml の matrix job 例)

```yaml
jobs:
  contract-generator-selftest:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4
      - uses: actions/setup-python@v5
        with:
          python-version: "3.11"
      - name: contract-generator self-test
        run: bash plugins/contract-generator/scripts/run-tests.sh
```

### pre-commit (.pre-commit-config.yaml の entry 例)

```yaml
repos:
  - repo: local
    hooks:
      - id: contract-generator-selftest
        name: contract-generator self-test
        entry: bash plugins/contract-generator/scripts/run-tests.sh
        language: system
        pass_filenames: false
        files: ^plugins/contract-generator/
```

> WHY: `scripts/lint-plugin-manifest.py` を CI / pre-commit から直接呼ぶと引数 (`--plugin-root`) 知識が外部に漏れ Loop B (改善の改善) が切れる。
> `run-tests.sh` に集約することで CI 側は entry を 1 行知れば済み、検査追加もシェル側で吸収できる。

### template-mapping.json と甲固定値の二重定義注意

- 甲 (発注者) 固定値の正本は `lib/config_auth.load_party_a()` (= `references/party_a-readme.md` の 4 層フォールバック)。
- `template-mapping.json` の `fields[]` に甲 4 列 (甲名称=name / 甲住所=address / 甲代表者役職=title / 甲代表者氏名=rep_name) を追記する場合、値そのものではなく **`{{party_a.*}}` 参照** で書くこと。値直書きは SSOT 違反となる。代表者は役職と氏名に分けて差込むため合成形 `representative` は使わない。

