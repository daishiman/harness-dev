# Abstraction Contract — run-notion-intake-publish

本 skill は **Notion** 専用の公開 / 再公開 wrapper (初回 publish は workflow-manifest
P10 委譲、再公開は update 専用) だが、別 sink (Confluence / DocBase /
Backlog Wiki 等) に量産流用できるよう、以下の変数を差し替え点として定義する。

| 変数 | 既定値 | 用途 |
|---|---|---|
| `sink_pipeline_script` | `plugins/skill-intake/scripts/intake_publish_pipeline.py` | render → quality_gate → publish の単一発火点 |
| `verify_schema_script` | `plugins/skill-intake/scripts/verify_notion_schema.py` | 公開先 DB / space のスキーマ整合検査 |
| `verify_assets_script` | `plugins/skill-intake/scripts/verify_notion_assets.py` | All-or-Nothing アセット検査 |
| `secret_keychain_label` | `notion-intake-token` | Keychain ラベル (sink ごとに 1 ラベル) |
| `manifest_filename` | `notion-manifest.json` | sink 別アセット manifest 名 |
| `intake_filename` | `intake.json` | aggregator 出力の正本ファイル名 (固定) |
| `output_dir_pattern` | `output/<hint>/` | 入出力ルート (hint = skill-name slug) |
| `on_schema_conflict` | `skip-warn` | DB スキーマ差分時の挙動 ∈ {skip-warn, fail, auto-migrate} |

## 流用時のチェックリスト

1. `sink_pipeline_script` 側で render/quality/publish を 1 プロセスに束ねたか
   (本 skill は責務を分割しない契約のため、複数 script 呼びは禁止)。
2. Secret は環境変数で渡さず必ず Keychain helper 経由か。
3. `verify_*_script` が exit !=0 で **publish 前** に止まるか。
4. `manifest_filename` 等は output_contract に必ず明記したか。
