# skill-intake scripts 命名規約解消計画

> **本計画は計画のみ**。実 rename は別 PR で `lint-script-naming.py` の PENDING/VIOLATION リストと併せて段階適用する。

## 規約

`verb-target[-scope].py` 形式。許可 prefix: `emit-` / `aggregate-` / `lint-` / `build-` / `wrap-` / `assign-` / `run-` / `ref-` / `delegate-` / `install-` / `capability-`。

skill-intake 配下のスクリプトは多くが「intake 処理パイプライン部品」なので、prefix としては実行系 `run-` か変換系 `build-`、検査系 `lint-`、データ抽出系 `aggregate-` のいずれかが妥当。Notion 公開系は外部発火責務 `emit-` を採用。

## マッピング (37 本 = plugin 直下 34 本 + `skills/<name>/scripts/` 配下 3 本)

### Keychain (1)
| 現行 | 新名 | prefix 根拠 |
|---|---|---|
| keychain_get_secret.py | `wrap-keychain-secret.py` | OS Keychain を script で薄ラップ |

### Notion 公開系 (8)
| 現行 | 新名 |
|---|---|
| publish_notion_page.py | `emit-notion-page.py` |
| render_notion_page.py | `build-notion-page-render.py` |
| dry_render_notion.py | `build-notion-page-render-dryrun.py` |
| create_notion_database.py | `emit-notion-database.py` |
| prepare_notion_assets.py | `build-notion-assets.py` |
| verify_notion_assets.py | `lint-notion-assets.py` |
| verify_notion_schema.py | `lint-notion-schema.py` |
| notion_http.py | `wrap-notion-http.py` |

### Render / 図解 (7)
| 現行 | 新名 |
|---|---|
| render_to_svg.py | `build-svg-from-mermaid.py` |
| render_to_image.py | `build-image-from-svg.py` |
| render-intake-final.py | `build-intake-final-render.py` |
| compose_diagram.py | `build-diagram-compose.py` |
| select_diagram_type.py | `assign-diagram-type.py` |
| select_diagrams_per_section.py | `assign-diagrams-per-section.py` |
| optimize_layout.py | `build-diagram-layout.py` |

### 品質ゲート / lint 系 (10)
| 現行 | 新名 |
|---|---|
| validate_intake.py | `lint-intake-output.py` |
| validate_intake_schema.py | `lint-intake-schema.py` |
| validate_mermaid.py | `lint-mermaid.py` |
| check_completeness.py | `lint-intake-completeness.py` |
| cross_check.py | `lint-intake-cross-check.py` |
| detect_contradictions.py | `lint-intake-contradictions.py` |
| enforce_visualization_rules.py | `lint-visualization-rules.py` |
| quality_gate.py | `lint-intake-quality-gate.py` |
| lint_subagent_seven_layer.py | `lint-subagent-seven-layer.py` (verb prefix 整形のみ) |
| extract_open_questions.py | `aggregate-open-questions.py` |

### intake 構築・データ抽出 (5)
| 現行 | 新名 |
|---|---|
| analyze_user_intent.py | `aggregate-user-intent.py` |
| convert_md_to_json.py | `build-intake-json-from-md.py` |
| convert_v1_to_v2_context.py | `build-intake-v2-context.py` |
| intake_publish_pipeline.py | `emit-intake-publish.py` |
| measure_value_realized.py | `aggregate-value-realized.py` |

### self-update / dogfooding (3)
| 現行 | 新名 |
|---|---|
| update_question_bank.py | `build-question-bank.py` |
| ci_dogfooding_retest.py | `lint-dogfooding-retest.py` |
| dogfooding_regression.py | `lint-dogfooding-regression.py` |

### その他 (3)
| 現行 | 新名 |
|---|---|
| append_eval_log.py | `emit-eval-log.py` |
| m3_deprecation_reverse_index.py | `aggregate-m3-deprecation-reverse-index.py` |
| render_v2_adapter.py | `wrap-render-v2.py` |

### skill 配下の局所 script (3, VIOLATION)
| 現行 | 新名 |
|---|---|
| skills/run-intake-next-action/scripts/decide-mode.py | `assign-intake-mode.py` |
| skills/run-intake-visualize/scripts/verify-visuals.py | `lint-intake-visuals.py` |
| skills/run-intake-interview/scripts/check-five-axes-coverage.py | `lint-intake-five-axes-coverage.py` |

## 段階適用手順 (Change Governance 33 章)

1. **PR-A: 内部参照リネーム**: 全 SKILL.md / workflow-manifest.json / hooks/README.md / .claude-plugin/plugin.json / scripts/README.md で旧名→新名へ参照を一括更新 (script ファイル本体は未 rename)。
2. **PR-B: ファイル名 rename**: `git mv` で 37 本を実 rename。`lint-script-naming.py` の PENDING / VIOLATION リストを同時更新。
3. **PR-C: 古い PENDING 登録を削除**: `lint-script-naming.py` から skill-intake の PENDING エントリを除去し OK へ遷移。

各 PR で `lint-script-naming.py` exit 0、`lint-external-refs.py` exit 0、CI smoke (Notion sandbox 公開) を grееn にすることが merge 条件。

## 影響範囲注意点

- `intake_publish_pipeline.py --revise --page-id` を呼び出す箇所が複数 (commands/intake-publish.md, commands/intake-revise.md, skills/run-notion-intake-publish, skills/run-intake-revise) — PR-A で全箇所を整合更新する必要あり
- `keychain_get_secret.py` は agents/skill-intake-notion-publisher.md frontmatter コメントでも引用されているため、PR-A 対象
- `publish_notion_page.py` は plugin.json の Hook 経路にも参照されている可能性あり、要 grep 全件
