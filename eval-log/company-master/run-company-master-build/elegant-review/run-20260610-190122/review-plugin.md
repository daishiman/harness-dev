# elegant-review レポート: plugins/company-master (scope_mode=plugin)

- run-id: run-20260610-190122 / 実施日: 2026-06-10 / loop_count: 2 (max 3)
- 検証観点: (a) skill-creator 仕様準拠 (b) 単一 skill 構成の妥当性 (c) 再現性 (100人実行で同一結果) の機械的担保 (d) ユーザー要求充足
- フロー: Phase 1 思考リセット (elegant-reset-observer) → Phase 2 並列分析 3 SubAgent (30 思考法、used=30 / skipped=0) → Phase 3 改善実行 3 executor (A: plugin 内、B: Makefile/CI/settings 配線、C: agents リネーム) × 2 周
- 承認: proposer ≠ approver — 独立 SubAgent が evidence 抜き取り検証+検証コマンド再実行のうえ **approve** (discrepancies 0)

## verdict

| 条件 | 判定 | 根拠 |
|---|---|---|
| C1 矛盾なし | **PASS** | 検出5件 (9列vs8列+本文 / 会社名のみ自動確定 / .codex-plugin 幻影 / 二段防御宣言vs実態 / dogfooding 断絶) 全解消 |
| C2 漏れなし | **PASS** | 必須要求充足を確認。検出欠落 (lint被覆/hook pytest/script_refs/カバレッジ表/upsertゲート/KEN_ALL版/README読者) 全解消。残は強化提案のみ |
| C3 整合性あり | **PASS** | docstring 残骸/confirm-url 経路非対称/agents 命名/hook 旧世代パターン 全統一。make lint PASS |
| C4 依存関係整合 | **PASS** | CI 配線/REPLAY_LOG root 起点/symlink 再生成/旧名参照 0 件。pytest 22 passed |

## 主要な質問への結論

1. **skill-creator 仕様準拠か**: 構造 (SKILL.md frontmatter・goal-seek・references/scripts/prompts・agents 薄アダプタ・plugin-composition) は仕様準拠だったが、**準拠を検証する機械層が company-master を被覆していなかった** (frontmatter lint が skill-creator 固定・CI 未配線)。Makefile 3 lint + creator-kit-ci + governance-check 4 step を配線し、機械検証で PASS する状態にした。
2. **skill 1 個で良いか (責務分離)**: **分割不要 (reject)**。resolve/enrich/upsert の 3 責務は単一ゴールに直列従属し独立起動の業務的意味がなく、agents 3 体+責務マッピングが既に事実上の責務分離を達成している。contract-generator が複数 skill なのは業務段階 (下書き/確定) が独立起動するためで前提が異なる。真の問題は分割ではなく backfill/agent 経路の検証非対称であり、これは upsert 内蔵 validate ゲートで解消した。
3. **100 人中 100 人が同一結果か**: 二層に分けて担保。①決定論層 (正規化・検証 a-h・8 列構築・備考/確認用URL テンプレ・upsert 判定) は pytest 22 件+byte 一致テンプレ+lint/CI で機械保証。②非決定論層 (Web 検索由来の補完・gBizINFO データの時点差) は原理的に完全同一化できないため、確度日本語ラベル (ネット検索(要確認) 等)+備考定型文+検証ゲートで「同じ品質契約」を機械強制し、誤値>>空欄の原則を全経路 (wrapper/agent/backfill) で貫徹させた。今回の修正前はこの保証に穴があった (会社名のみ自動確定・backfill 検証迂回・hook fail-open・cwd 相対パス・KEN_ALL 版未記録) — すべて封鎖済み。
4. **ユーザー要求の反映**: 確度 4 日本語ラベル / 備考テンプレ / 確認用 URL / gBizINFO 採用 = 充足確認。列構成は「9 列」要求に対し「DB 8 列+確認用 URL はページ本文」を 2026-06-10 にユーザー承認、設計判断ログ#6 へ証跡追記済み。

## 実施した改善 (22 ファイル相当・3 executor)

**コード (contradiction/dependency_break 解消)**
- resolve_company.py: 自動確定を「法人番号一致 or 会社名+住所 2 要素一致」に厳格化 (address 必須化)
- backfill.py: PATCH 前 validate ゲート+違反行 deferred 退避 (VERT-01 解消)、REPLAY_LOG を root 起点解決、ken_all_cache_mtime 記録
- notion_upsert.py: upsert() 内に validate_record_gate 内蔵 (全呼出経路で検証 PASS を機械強制)、confirm-url 経路を _safe_confirm_url_children へ統一
- hooks/hook-guard-secret.py: JSON 解釈不能→exit 2 fail-closed、フラグ検出を正規表現化 (連結フラグ耐性)、settings-hardening.json に -g 系 deny 追加 (計 7 件)
- notion_config.py: skill-intake 残骸 docstring/dangling 参照を修正

**宣言層**
- SKILL.md: .codex-plugin 言及削除 / script_refs 3 件追記 / カバレッジ表に「会社名のみ」行 / 設計判断ログ#6 ユーザー承認証跡 / 二段防御を「動的層 fail-closed 単独完結」へ再定義 / VERT-01 解消済み化
- README.md: トークン登録の既定を「聞かれてから渡す」方式へ昇格、冒頭に対象読者と DB 差し替え手順を明記

**配線 (機械担保)**
- Makefile: company-master 向け lint 3 種 (name/description/frontmatter) 追加
- creator-kit-ci.yml: vendored-deps lint step / governance-check.yml: conformance 4 step 追加
- .claude/settings.json: deny 7 件マージ+enabledPlugins に company-master@xl-skills (dogfooding 解消、ユーザー承認済み)
- agents 3 ファイルを company-master-*.md へリネーム (frontmatter name と一致)、参照更新+symlink 再生成

**テスト**: tests/test_company_master.py 9→22 件 (name-only 非確定 / backfill 退避 / upsert ゲート / hook block・allow・bypass / ken_all 版 / REPLAY_LOG root)

## 第3ラウンド追補 (2026-06-10、ユーザー指示「残課題も全て改善」+実トークン設定済み)

当初「次 PR 提案」とした残課題をすべて実装し、実トークンで実機検証まで完了した。

**実装 (Executor D: plugin 内 / Executor E: repo 横断、並列)**
1. Notion live スキーマ preflight: columns.md 由来の references/notion-db-schema.json を新設し、notion_upsert.py の preflight (8列存在・型一致・select 4値完全一致・禁止列・API不達 = すべて fail-closed) を upsert/backfill 両経路へ配線
2. plugin 横断 lint 被覆メタ検査: scripts/lint-plugin-lint-coverage.py 新設 (marketplace.json SSOT・allowlist 理由必須+stale 検査)。contract-generator を全被覆へ編入、skill-intake は frontmatter enum 違反 (effect: notion-mutation) を allowlist 追跡。Makefile+CI 2系統配線
3. vendored drift lint: lint-company-master-vendored-deps.py に関数単位 AST 比較を統合 (共通9関数=正本一致・拡張2関数=ホワイトリスト・双方向)
4. setup doctor: company_master.py doctor (Keychain 2鍵/DB ID 解決経路/Notion 到達+preflight/settings deny の4診断)
5. レート制限: 429/5xx 指数バックオフ (最大5試行・Retry-After 尊重・枯渇 fail-closed)、backfill は退避継続を確認
6. DEDUCT-01/A4-VALUE-01/A4-SYSTEM-01 文書一本化: data-sources.md V1 一本化、columns.md に保守的確度設計の意図明記、open_issues 更新

**実機検証 (実トークン)**
- doctor 実走: live DB の実 drift (正式名称・情報の確かさ・備考 3列不在+電話番号 phone_number 型) を fail-closed で正しく検出
- live DB 整備: 正本8列へ非破壊整備 (『正式な会社名』→『正式名称』rename+型変更+2列追加) → preflight/doctor 全 OK
- gBizINFO 疎通: V1=HTTP 200、V2=HTTP 404 → **「V2 優先」の旧文書記述自体が誤りで実装 (V1) が正と実証** (DEDUCT-01 完全解消)
- E2E: 法人番号入力→resolve (公的データで確認済み)→enrich (KEN_ALL 逆引き不能は誤値でなく空欄+備考に倒れることを実証)→validate PASS→upsert created→8列+本文確認用URL節を確認→テスト行 archive (業務 DB を汚さない)

**最終残課題 (実装対象外)**
- KEN_ALL 一意確定率のチューニング (フェイルセーフは実機実証済み、性能改善は実測蓄積待ち)
- skill-intake の frontmatter enum 違反 (他 plugin 実体。メタ検査 allowlist が追跡し stale 検査が掃除を強制)
- hook の Bash 変数間接バイパス (原理的限界として受容方針を SKILL.md に明文化済み、静的層 deny が深層防御)

## 検証コマンド (全 PASS、第3ラウンド後)

- python3 -m pytest tests/test_company_master.py tests/test_plugin_lint_coverage.py -q → 52 passed
- python3 scripts/lint-company-master-vendored-deps.py (drift AST チェック含む) → OK
- python3 scripts/lint-plugin-lint-coverage.py → ok (5 plugins × 3 lint kinds)
- make lint → exit 0
- python3 scripts/build-claude-symlinks.py --check → noop=76 conflict=0
- python3 plugins/company-master/scripts/company_master.py doctor → FAIL なし (実トークン)
- validate-paradigm-coverage.py findings.json → OK: all 30 paradigms covered
