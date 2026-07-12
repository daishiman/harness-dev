# Skill Factory 再現性契約

`run-build-skill` は、単一の Skill を作るだけでなく、Skill / SubAgent / Hook / script / config を横展開できる量産基盤として動く。個別案件の具体値は成果物へ直書きせず、必ず変数・rubric・adapter・trace に分離する。

## 必須モデル

### 1. Rubric Composition Model (設計書29)

- L0 共通基準、L1 ドメイン基準、L2 案件基準を `rubric_refs` で合成する。
- evaluator 本体は変更せず、L1 は `plugins/skill-governance-config/config/rubric-registry.json`、L2 は対象 Skill の `references/` に置く。
- trace には `rubric_composition_model` として `ordered_refs`, `merge_strategy`, `conflict_policy`, `composition_hash_evidence` を残す。
- 不在の rubric を黙って無視しない。未適用なら `N/A` と理由を残す。

### 2. Paradigm Analogy Model (設計書30)

- 新規パターンは既存パラダイムへ類推して配置判断する。
- 例: evaluator は linter/test runner、hook は pre-commit、adapter は Hexagonal Architecture の outbound adapter、SubAgent は subprocess / bounded context。
- trace には `paradigm_analogy_model` として `primary_analogy`, `matched_skill_concept`, `limits`, `placement_decision` を残す。
- 類推は理解の足場であり、最終判断は 03/05/09/16/17 などの正本仕様で検証する。

### 3. Output Routing Model (設計書31)

- タスクロジックと出力先を分離し、workflow Skill は payload と `task_kind` だけを生成する。
- 出力先は `ref-output-routing` と `scripts/adapters/dispatch.py` に委譲する。
- trace には `output_routing_model` として `task_kind`, `payload_schema_version`, `route_ref`, `adapter_registry_ref`, `fallback`, `secret_boundary` を残す。
- Notion / Sheets / Slack / HTTP などの具体先は config example では `{{...}}` 変数にし、secret は `keychain:{{SECRET_NAMESPACE}}-<service>/<account>` 参照だけにする。

### 4. Variable Template Contract

再利用成果物に残してよい具体値は、パラメーター名、JSON key、frontmatter key、CLI引数名だけである。説明文、プロンプト、SubAgent手順、config example では次の変数を使う。

| 変数 | 意味 | 既定値 |
|---|---|---|
| `{{PROJECT_ROOT}}` | 対象プロジェクトのルート | 実行時 cwd |
| `{{KIT_ROOT}}` | creator-kit のルート | `{{PROJECT_ROOT}}/creator-kit` |
| `{{DOC_ROOT}}` | 設計書ルート | `{{PROJECT_ROOT}}/doc` |
| `{{SKILL_NAME}}` | 生成対象 Skill 名 | 入力値 |
| `{{KIND}}` | `run/ref/assign/wrap/delegate` | 入力値 |
| `{{DOMAIN}}` | L1 rubric 解決用ドメイン | 未指定 |
| `{{TASK_KIND}}` | 出力routing用タスク種別 | 未指定 |
| `{{OUTPUT_ROUTE}}` | routing route 名 | `{{TASK_KIND}}` |
| `{{SECRET_NAMESPACE}}` | Keychain service 接頭辞 | 利用プロジェクトで指定 |
| `{{OWNER}}` | 所有者 | 利用プロジェクトで指定 |
| `{{PYTHON_CMD}}` | Python起動コマンド | `python3` |
| `{{RUNTIME_SHELL}}` | 実行 shell | `bash` または `powershell` |

## 量産ゲート

1. `source_docs` に実際に読んだ 29/30/31 章を記録する。
2. `doc_coverage` に `29-multi-project-rubric-composition`、`30-paradigm-analogy-map`、`31-output-routing-adapter-architecture` を記録する。
3. `variable_contract` に使った変数、既定値、不適用条件、証跡を記録する。
4. `reproducibility_gates` は `lint` / `evaluator` / `elegant_review` / `governance` をすべて `PASS` または理由付き `N/A` にする。

## アンチパターン

- 案件固有 DB ID、固定 URL、固定チャンネル名、固定 owner を template / prompt / SubAgent に直書きする。
- L1 ドメイン差分のために evaluator を複製する。
- 出力先ごとに workflow Skill を分岐させる。
- 類推だけを根拠にして公式仕様・設計書の検証を省く。
