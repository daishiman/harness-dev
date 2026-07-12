# 変数テンプレート契約

`run-elegant-review` は、対象固有の改善をそのまま再利用成果物へ埋め込まない。必ず次の順序で抽象化する。

1. 具体値を観察する。
2. 具体値をテンプレート変数へ写像する。
3. 変数の意味、既定値、必須性、適用しない条件を記録する。
4. 由来は `source_trace` に残す。
5. Skill / SubAgent / script / config へ反映する時は変数名を使う。

## 標準変数

| 変数 | 意味 | 既定値 |
|---|---|---|
| `{{PROJECT_ROOT}}` | 対象プロジェクトのルート | 実行時 cwd |
| `{{KIT_ROOT}}` | creator-kit のルート | `{{PROJECT_ROOT}}/creator-kit` |
| `{{target_type}}` | 対象種別 | `custom` |
| `{{target_path}}` | 対象パス | 入力値 |
| `{{review_workspace}}` | レビュー作業領域 | OS別一時ディレクトリ |
| `{{owner}}` | 所有者 | 利用プロジェクトで指定 |
| `{{os_kind}}` | 実行OS | `unknown` |
| `{{external_executor}}` | 外部実行環境 | `none` |
| `{{DOC_ROOT}}` | 参照設計書のルート | `{{PROJECT_ROOT}}/doc` |
| `{{SOURCE_REGISTRY}}` | 出典 registry / source map | `{{DOC_ROOT}}/source-registry.json` |
| `{{SOURCE_CANONICAL_PATH}}` | 正本ソースのパスまたはURL | `internal` |
| `{{runtime_shell}}` | 実行 shell | `bash` または `powershell` |
| `{{python_cmd}}` | Python 起動コマンド | `python3` または `python` |
| `{{path_style}}` | パス表記 | `posix` または `windows` |
| `{{secret_backend}}` | secret backend 名 | `keychain` / `xdg` / `base64-file` / `env` |
| `{{install_mode}}` | kit 展開方式 | `symlink` または `copy` |

各変数は `name`, `meaning`, `default`, `required`, `not_applicable_when` を持つ。
`not_applicable_when` が空の変数は横展開時に過剰適用されやすいため、review 出力では必ず不適用条件を明示する。

## findings で使う分類

| フィールド | 用途 |
|---|---|
| `finding_scope` | 一回限りの指摘か、横展開する設計知かを分ける |
| `source_tier` | 根拠の強さを示す |
| `trace_evidence` | 具体的な由来を示す |
| `migration_bucket` | `doc/20` の移行先分類へ接続する |
| `reuse_surface` | skill / template / script-frontmatter / hook / config / governance-log / adapter / rubric / reference / none のどこへ昇格するかを示す（正本は `schemas/findings.schema.json` の enum、本列挙は転記） |
| `runtime_variant` | `doc/22` のOS差分へ接続する |
| `dependency_assumption` | stdlib-only / optional-cli などの前提を示す |
| `negative_case` | 適用しない条件を明示する |
| `re_audit_trigger` | 再監査する契機を示す |

## 禁止

- 実プロジェクト名、個人名、固定絶対パス、固定API URL、固定ownerを reusable な成果物へ直書きしない。
- 具体値を消さない。`source_trace` に証跡として残す。
- `{{...}}` をパラメーター名として使う場合、本文説明は日本語で書く。
