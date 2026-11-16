# フィードバック投入の Notion 設定

設定が見つからない場合だけ読む。設定値や token を会話へ書き出さない。

config path は NOTION_CONFIG_PATH → harness marker を持つ repo root → この skill を所有する plugin root の順に解決する。plugin root は manifest を持つ祖先であり、skill ディレクトリではない。

設定ファイルには keychain_service / keychain_account と databases.skill-list.db_id / databases.improvement-request.db_id を設定する。DB ID と integration のアクセス権は開発担当から受け取り、設定ファイルは commit しない。

token は macOS Keychain が既定。Keychain がない環境では INTAKE_ALLOW_ENV_TOKEN=1 を明示した場合だけ NOTION_TOKEN を使える。Keychain の service/account が設定にない場合は既存 tenant 設定から導出するため、HARNESS_TENANT_CONFIG などで対象を明示する。credential 自体は同梱しない。

DB の構造は同梱 schemas/skill-list.schema.json と schemas/improvement-request.schema.json が示す。DB の作成・対象プラグインの登録は開発担当の作業であり、この要望投入では自動実行しない。

引数確認には同梱 scripts/notion-submit-improvement.py の --dry-run を使う。これは外部通信も登録確認も行わない。本投入は SKILL.md の承認 wrapper だけを通す。
