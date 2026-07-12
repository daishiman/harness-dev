# Task 04 INV to CLI Mapping

| INV | CLI 側の保証手段 |
|---|---|
| INV-1 user 管理値保存 | マージ前後で user 管理値の正規化 JSON SHA256 を比較、相違なら exit 2。`--print-user-section-hash` は同じ抽出規則を外部検証用に公開する。 |
| INV-2 決定的生成 | plugin を辞書順で読み、同一入力なら同一 plan と同一 settings 出力にする。 |
| INV-3 冪等性 | 2 回連続実行後の `--check` が exit 0 になる契約にする。 |
| INV-4 plugin 名辞書順 | `--plugins-dir` 配下を plugin name で sort して処理する。 |
| INV-5 衝突 ERROR | 同一 event x matcher x command を複数 plugin が出したら書き込まず exit 2。 |
| INV-6 未知キー保存 | 未知 top-level key と管理メタデータ外の user 管理値を保存する。 |
| INV-7 JSON 正規化 | 生成管理領域は indent=2、ensure_ascii=False、schema 順、末尾改行で出力する。 |
| INV-8 原子的書き込み | 同一ディレクトリ tempfile に書き、全検証後に os.rename で置換する。失敗時は target を維持する。 |
| INV-9 グローバル名前空間一意性 | plugin / skill / agent / command / hook / permission の namespace preflight を実行し、衝突なら exit 2。 |
| INV-10 settings 構造検証 | 生成後 JSON の `permissions` / `hooks` 型、hook event、hook command entry を検査する。 |
| INV-11 permissions マージ安全性 | 完全一致は dedupe、同一 rule の decision 競合は自動解決せず exit 2。 |
| INV-12 plan 完全性 | `--dry-run --json` の plan に `namespace`, top-level `conflicts`, `settings`, `invariants_checked` を必須化する。 |
