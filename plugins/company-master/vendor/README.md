# Bundled Python Dependencies

このディレクトリは、company-master プラグインで外部 Python ライブラリが必要になった場合の同梱先です。

**現状は外部依存ゼロ = `pip install` 不要は達成済み**。`vendor/` は将来用の空の受け皿で、**空が正常**です。repo-level CI の `scripts/lint-company-master-vendored-deps.py` (リポジトリ `scripts/` 配下) が「scripts 配下の import は stdlib・plugin 内部・vendor 同梱のいずれか」を機械検証し、未同梱の外部 import が混入したら CI で FAIL させてこの不変条件を強制します。単独 install された plugin 実行時にはこの lint script は同梱されませんが、配布物自体は標準ライブラリのみで動くため追加セットアップは不要です。

将来 `requests` などの外部ライブラリが必要になった場合は、この `vendor/` 配下に wheel 展開済みモジュールを置き、`scripts/bootstrap_plugin.py` 経由で `sys.path` に追加します (置いた時点で lint が同梱を認識して OK になります)。

運用ルール:

- ユーザーに `pip install ...` を依頼しない。
- ライセンスを確認してから `vendor/` に同梱する。
- 同梱したライブラリ名、バージョン、ライセンス、取得元 URL をこのファイルへ追記する。
- 決定論処理で足りる場合は、外部依存を追加せず標準ライブラリを優先する。
