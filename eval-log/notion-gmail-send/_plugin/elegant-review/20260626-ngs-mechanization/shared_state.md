# shared_state（Phase 1 → Phase 2 ファンアウト中継: 再発防止の仕組み化レビュー）

## 200字要約
症状＝notion-gmail-send がマーケットプレイス非表示。直接修正（marketplace.json への14件目登録・bundles.json登録・validate-plugin-completeness.py に MK-001/002/003 追加・CI3面 hard 配線）は確認できた。最重要 fresh 観察＝**生成層（skill-creator）に新形式 plugin.json plugin を marketplace.json/bundles.json へ登録する機械機構が存在しない**。Gate2.5 の build-manifest-registration-plan.py は legacy manifest.json 専用で、plugin.json 形式は早期 return しルートの2 SSOTに触れない。検証＝検出(CI lint)はできるが生成時の自動登録(予防)が無い可能性。

## 親 context 非参照宣言
本 Phase 1 は親 context の先行要約・結論を参照せず、対象ファイルを初見で Read した観察のみに基づく。前回レビュー成果物は独立検証対象として扱い、正解と決めつけない。

## 観察した全関連ファイル（絶対パス + 1行役割）
- .claude-plugin/marketplace.json — プラグイン一覧 SSOT。plugins[] 14件、notion-gmail-send は末尾に登録済（修正済）
- .claude-plugin/bundles.json — install 用バンドル定義。xl-skills-full に notion-gmail-send 登録済（修正済）
- plugins/notion-gmail-send/.claude-plugin/plugin.json — 対象 plugin manifest。bundle_targets/bundles で xl-skills-full を自己宣言、entry_points.skills=6
- scripts/validate-plugin-completeness.py — 実体ディレクトリ起点で marketplace(MK-001/002/003)+bundles(BD-001) 双方向登録を fail-closed 検査（修正で MK 系追加済）
- scripts/run-ci-checks.sh — pre-push/手動の機械チェック SSOT。validate-plugin-completeness を hard 配線（修正済）
- .github/workflows/governance-check.yml — CI。validate-plugin-completeness を continue-on-error:false で配線（修正済）
- Makefile — lint ターゲットで validate-plugin-completeness 配線（修正済）
- scripts/lint-plugin-lint-coverage.py — marketplace.json を起点に lint 被覆を巡回するメタ lint（起点が marketplace のため未登録 plugin は巡回対象外＝自己強化ループの構造要素）
- plugins/skill-creator/skills/run-build-skill/SKILL.md — Capability 生成本体。ルート marketplace.json/bundles.json 登録ステップは本文に無い
- plugins/skill-creator/skills/run-build-skill/references/build-steps.md — Phase G「登録」は alias/commit のみ言及、marketplace/bundles 登録手順なし
- plugins/skill-creator/skills/run-skill-create/SKILL.md — 量産 orchestrator。Gate2.5「plugin/marketplace登録判定」を build-manifest-registration-plan.py に委譲（自動更新禁止・人間承認後 --apply）
- plugins/skill-creator/skills/run-skill-create/workflow-manifest.json — step3 gate2.5=manifest-register / step3.5=bundle-register（後者は command/delegateSkill ともに null、artifact 宣言のみで実行機構なし）
- plugins/skill-governance-automation/scripts/build-manifest-registration-plan.py — Gate2.5 の実体。legacy manifest.json 専用。plugin.json 形式は status:ok/proposals:{} で早期 return。ルート .claude-plugin/ を一切操作しない
- plugins/skill-creator/skills/run-plugin-package-check/SKILL.md — PKG-001〜015 出荷前検査 orchestrator。marketplace/bundles 登録検査は完了条件・チェックリストに無い
- plugins/skill-creator/skills/ref-pkg-contract/references/pkg-id-catalog.yaml — PKG 機械可読カタログ。marketplace.json/bundles.json 登録検査の PKG ID は存在しない
- plugins/skill-creator/skills/assign-plugin-package-evaluator/scripts/validate-plugin-package.py — PKG-002〜008 実装。marketplace.json/bundles.json は対象外

## 検証すべき仮説（断定せず独立検証対象）
- H1: 非表示の直接原因＝marketplace.json plugins[] に notion-gmail-send 未登録。修正で14件目登録され解消したか
- H2: MK-001/002/003 が実体起点で fail-closed 検出し CI3面に hard 配線され再発を機械検出できるか
- H3（核心）: 生成層 skill-creator が新 plugin 量産時にルート marketplace.json/bundles.json 登録を強制する機械ゲートが存在するか／無いか。Gate2.5 は legacy manifest.json 専用で plugin.json 形式は早期 return し2 SSOTを操作しない＝予防(生成時自動登録)が無く検出(CI lint)のみで成立しているか
- H4: workflow-manifest.json step3.5 bundle-register は command/delegateSkill とも null で実行機構なし＝手作業依存でないか
- H5: PKG harness に marketplace/bundles 登録検査が無く出荷前 package check で登録漏れを捕捉しない設計か。検出が validate-plugin-completeness.py（PKG外独立 lint）に一本化されている整合性
- H6: lint-plugin-lint-coverage.py が marketplace 起点巡回のため未登録 plugin が被覆メタ検査の対象外になる「漏れが漏れを隠す」構造が MK-001 追加後も残存しないか
- H7: 検出 lint(MK-001) は実体ディレクトリ存在が前提。生成 orchestrator のゲート順序と CI/pre-push 発火タイミングが整合し、生成直後に必ず検出されるか

## 第一印象の懸念点（観察事実のみ・原因断定なし）
- O1: marketplace.json plugins[] 14件で notion-gmail-send が末尾に登録済
- O2: validate-plugin-completeness.py は MK-001/002/003/BD-001 を実体起点で全 plugin ループ検査
- O3: 同検査器が run-ci-checks.sh・governance-check.yml(continue-on-error:false)・Makefile の3面配線
- O4: run-ci-checks.sh の MK/BD 検査は run()（hard）で即 fail-closed
- O5: build-manifest-registration-plan.py は plugin.json 形式で proposals:{} 早期 return、ルート marketplace.json/bundles.json を読み書きしない（KIT_DIR=skill-creator plugin 内）
- O6: run-build-skill 本文・build-steps.md Phase G「登録」に marketplace/bundles 登録ステップなし
- O7: workflow-manifest.json step3.5 bundle-register は artifact 宣言のみ・command null
- O8: PKG harness に marketplace/bundles 登録検査の PKG ID が無い
- O9: lint-plugin-lint-coverage.py は marketplace.json を巡回起点にする＝marketplace 未登録 plugin は被覆判定対象外
- O10: 前回改善表(F1-F5)に生成層への登録機構配線が含まれない＝検出は追加・予防は未着手の可能性
- O11: plugin.json の bundle_targets と bundles が同一値(xl-skills-full)で重複宣言＝バンドル登録 SSOT 二重化の兆候
