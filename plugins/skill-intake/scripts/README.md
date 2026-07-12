# skill-intake scripts

本ディレクトリの責務: `run-skill-intake` および sibling skill `run-notion-intake-publish` から呼ばれる**決定論処理を担う Python 3 スクリプト集**。LLM 判断に依存せず、入力に対して常に同じ出力を返すロジックのみを置く (Script First 原則)。macOS 標準 `/usr/bin/python3` で動作する。最終 Markdown レンダリング用の `jinja2` は plugin 配下 `vendor/python` に同梱し、JSON Schema 検証は `scripts/_jsonschema_compat.py` の標準ライブラリ fallback を使う。

**配置**: 本ディレクトリ (plugin 直下 `plugins/skill-intake/scripts/`) と個別 skill 配下 (`skills/<name>/scripts/`) の 2 箇所に分かれる。データファイル `notion_limits.json` はスクリプトではない。

## カテゴリ別一覧

### Keychain 系 (1 本)

| スクリプト | サマリ |
|---|---|
| `keychain_get_secret.py` | macOS Keychain から Notion トークンを取得する唯一の経路。exit 44 で未登録を表現。 |

### Notion 系 (9 本)

| スクリプト | サマリ |
|---|---|
| `notion_http.py` | Notion REST API v1 への薄い wrapper。Notion-Version / Authorization を 1 箇所に閉じ込める。 |
| `validate-notion-ready.py` | 固定DB / config / Keychain token / 任意の read-only API 接続を一括確認し、PASS 済みなら API キー再質問を不要にする。 |
| `create_notion_database.py` | `--mode=create|sync` で DB を作成または既存 DB を期待スキーマへ寄せる。create は `--parent-page` / `.notion-config.json#parent_page` を必須解決し、`--dry-run` で非 mutation 検証可能。 |
| `verify_notion_schema.py` | 期待スキーマと現状 DB を突き合わせ、過不足を `eval-log/notion-conflicts.json` に出力。 |
| `prepare_notion_assets.py` | `visuals/` を走査し SHA-256 付き `notion-manifest.json` を生成。 |
| `verify_notion_assets.py` | PNG 欠損・空ファイル・hash 不一致を MUST ゲート検証 (All-or-Nothing)。 |
| `render_notion_page.py` | `intake.json` から Notion ブロック JSON (`notion-blocks.json`) を組み立てる。 |
| `publish_notion_page.py` | Notion REST `POST /v1/pages` を実発火し、URL を返す。 |
| `smoke_notion_publish.py` | 検証用 Notion ページへの実接続 publish smoke を安全に準備/実行する。既定は非 mutation、`--execute` 時のみ更新。 |

### 品質ゲート系 (11 本)

| スクリプト | サマリ |
|---|---|
| `validate_intake.py` | intake.json のスキーマ検証 (`handoff-contract.md` 準拠)。 |
| `validate_intake_schema.py` | intake-final-context.json (v2) の JSON Schema 検証。 |
| `check_completeness.py` | 5 軸 (出力先・情報源・共有相手・真の課題・ナレッジ資産) 充足判定。 |
| `cross_check.py` | intake.md と intake.json の整合検証。 |
| `detect_contradictions.py` | SubAgent 出力間の矛盾検出。 |
| `extract_open_questions.py` | 未解決質問の抽出。 |
| `quality_gate.py` | 5 次元ルブリック自己採点 PASS/FAIL 判定。 |
| `measure_value_realized.py` | 真の課題言語化スコア (0-100) 採点。 |
| `lint_subagent_seven_layer.py` | SubAgent prompt の 7 層構造遵守を静的検査。 |
| `analyze_user_intent.py` | ユーザ入力から意図カテゴリを推定し question-bank 適用順を決める。 |
| `append_eval_log.py` | 各 phase の評価結果を `eval-log/` に追記 (構造化ログ)。 |

### 図解系 (8 本)

| スクリプト | サマリ |
|---|---|
| `select_diagram_type.py` | セクション種別から最適な図解タイプを選択。 |
| `select_diagrams_per_section.py` | セクションごとの図解配置を 1〜3 図で決定。 |
| `compose_diagram.py` | Mermaid / SVG 構文を生成 (テンプレ展開)。 |
| `validate_mermaid.py` | Mermaid 構文検証 (失敗時は再生成を最大 2 回試行)。 |
| `enforce_visualization_rules.py` | 非エンジニア対応マスト 8 ルール強制。 |
| `optimize_layout.py` | 図解レイアウト最適化 (ノード配置調整)。 |
| `render_to_svg.py` | Mermaid → SVG 変換。 |
| `render_to_image.py` | Mermaid (.mmd) → PNG (mmdc 必須) + 静的 SVG (.svg) → 同梱 PNG (`assets/cvis-*.png`) コピー配置 (不在時 cairosvg fallback、両不可は exit 3)。Notion は SVG ネイティブ表示不可。 |

### 取得・レンダリング系 (5 本)

| スクリプト | サマリ |
|---|---|
| `convert_md_to_json.py` | intake.md から intake.json への derive 検証。 |
| `convert_v1_to_v2_context.py` | v1 intake.json を v2 intake-final-context.json へ変換 (後方互換 migration)。repo 保守者専用・配布除外 (`package.exclude`)。 |
| `render_v2_adapter.py` | v2 context を既存 renderer 互換形式へ正規化する adapter。repo 保守者専用・配布除外 (`package.exclude`)。 |
| `render-intake-final.py` | intake-final-context.json から §0〜§11 完全版 Markdown を生成 (Jinja2 + JSON Schema 検証)。 |
| `dry_render_notion.py` | Notion API を叩かず blocks JSON のみ生成する dry-run。 |

### self-update 系 (2 本)

| スクリプト | サマリ |
|---|---|
| `update_question_bank.py` | question-bank.md にパッチ適用 (`--apply` / `--rollback <hint>`)。 |
| `m3_deprecation_reverse_index.py` | M3 マイグレーションの非推奨項目を逆引き index 化し、self-updater 経由で警告。repo 保守者専用・配布除外 (`package.exclude`)。 |

### dogfooding / pipeline 系 (3 本)

| スクリプト | サマリ |
|---|---|
| `intake_publish_pipeline.py` | intake → fidelity guard → publish を結ぶ orchestration (CLI entry)。 |
| `ci_dogfooding_retest.py` | CI 上で fixtures を再走させ regression を検出。 |
| `dogfooding_regression.py` | ローカル dogfooding 結果と baseline を比較し差分を報告。 |

## 依存

- **Python 3.9 以上** (macOS 標準 `/usr/bin/python3` 可)
- **Python package**: `jinja2` は `vendor/python` に同梱済み。通常利用者の手動 `pip install` は不要。
- **Vendor 検査**: `python3 scripts/validate-plugin-vendor.py` が `"ok": true` を返すこと。
- 認証情報は必ず `keychain_get_secret.py` 経由で取得。環境変数・`.env`・コミット履歴に平文を残さない。
