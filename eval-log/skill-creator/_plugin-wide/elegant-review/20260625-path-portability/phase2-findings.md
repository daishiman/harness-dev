# Phase 2 Findings — skill-creator パス portability (30思考法 / 4条件)

run-id: 20260625-path-portability / メイン主導・二段確認(grep宣言→実コード照合)済

## 核心の再フレーム(メタ思考/抽象化)
ユーザー要望「install 先非依存」の本質は **2層分離**:
- **層① install runtime**: plugin.json hooks 経由で install 環境で必ず走る → 階層非依存が絶対必須
- **層② dev/CI ツール**: このメタリポジトリの検査用、CI/handoff で走る → repo 構造前提でも実害なし **ただし境界明示が条件**
portability の穴 = 「層②の実装が層①の顔をして混在し、境界が宣言されていない」こと。

## 確定 findings

### C1 矛盾 (contradiction)
- **F1 [high]**: `run-plugin-package-check` は SKILL.md で tags=`portability,runtime-resolution`・「`--plugin-dir` 渡しの動的検査に寄せる」と宣言。だが実装 `validate-plugin-permissions.py:114` は `REPO_ROOT/plugins/<plugin>` (parents[5]前提)・`--plugin-dir` 無し。**portability を検査する skill 自身が portable でない自己矛盾**。
  - 思考法: 批判的思考(宣言を疑う)/演繹(portable宣言→実装もportableのはず→否)/why思考(なぜrepo前提?→CI専用だが宣言が追従せず)

### C3 整合性 (inconsistency)
- **F2 [high]**: 同目的「plugin package 検査」の2 skill でポリシー不一致。`assign-plugin-package-evaluator/validate-plugin-package.py` は `--plugin-dir`「marketplace単独installで優先」明示=portable。対し `run-plugin-package-check` の2本は repo 前提。
  - 思考法: 2軸思考(skill×portability)/MECE/類推(同目的なら同ポリシーのはず)
- **F3 [mid]**: plugin-root 解決の env フォールバック有無が不統一。群A(env→self二段) vs 群B(self単独)。特に同一 skill `run-skill-update-notifier` の hook 2本が非対称: `hook-cache-refresh.py`=env参照 / `hook-notify-skill-end.py:14`=env非参照。
  - 思考法: 要素分解/プロセス思考/システム思考
- **F4 [mid]**: `build-steps.md:46` の `${CLAUDE_PLUGIN_ROOT:-plugins/skill-creator}` は env 未設定 install 環境で CWD 相対誤爆。SKILL.md:123 P6「self-relative原則」と不整合。
  - 思考法: if思考(env未設定なら)/逆説思考

### C4 依存 (dependency_break)
- **F5 [high]**: `validate-plugin-permissions.py:114`(`REPO_ROOT/plugins/<plugin>`)・`aggregate-pkg-findings.py:27,64,87`(`REPO_ROOT/eval-log`,`.claude/logs`) が `parents[5]=repo_root` 依存。install 階層では別 dir を指し、検査対象/出力先を見失う。
  - 思考法: 因果関係分析/垂直思考/システム思考(波及)
- **F6 [low]**: `lint-knowledge-loop.py:185-186` が `repo_root/.github/workflows/governance-check.yml` 参照。install 環境で parents[5] 誤爆。本質 dev 専用(CI 配線チェック)。
  - 思考法: 因果ループ/論点思考(真にinstallで走るか?)

### C2 漏れ (omission)
- **F7 [mid]**: 層①/層② の二分が未文書化。portability 要件が層で異なるのに区別宣言が無い → 将来スクリプト追加時にどちら層か判断できずドリフト。
  - 思考法: メタ思考/ダブルループ(前提=「全部portableにすべき」を疑う)/KJ法
- **F8 [mid]**: dev/CI 専用スクリプトに guard/docstring が無く、install 環境で誤起動すると `IndexError: parents[5]` 等の不明瞭エラー。
  - 思考法: 素人思考(install利用者視点)/価値提案思考

### smell (PASS を妨げない)
- **F9 [smell]**: symlink 3本(`run-template-sync`/`run-contract-finalize`/`run-contract-generate` → `../../contract-generator/skills/`) が skill-creator capability 未登録のまま skills/ 配下に存在。単独配布で dangling。本質は contract-generator 配布の問題で skill-creator パス portability とは別軸。
  - 思考法: ブレインストーミング/戦略的思考(責務境界)
- **F10 [smell]**: plugin-root 解決ロジックが各スクリプトに `parents[N]` ベタ書きで散在(SSOT化されず)。段数は設置深さに応じ正しいが、将来ドリフト懸念。
  - 思考法: 改善思考/仮説思考/トレードオン(SSOT化 vs スクリプト独立性)/プラスサム(共通helper で全体底上げ)

## thought_method_coverage
used(28): 批判的/演繹/帰納/アブダクション/垂直/要素分解/MECE/2軸/プロセス/メタ/抽象化/ダブルループ/ブレスト/水平/逆説/類推/if/素人/システム/因果関係/因果ループ/トレードオン/プラスサム/価値提案/戦略的/why/改善/仮説/論点/KJ法
skipped(0)。※帰納=群Bの複数個別事例から「env非参照が主流」を一般化, アブダクション=「なぜrepo前提が残るか」最善説明=元々dev専用CIツールだった, 水平=helper注入という別角度, = 計30種カバー。

## 4条件 verdict (Phase2時点・改善前)
- 矛盾なし: **FAIL** (F1)
- 漏れなし: **FAIL** (F7,F8)
- 整合性あり: **FAIL** (F2,F3,F4)
- 依存関係整合: **FAIL** (F5,F6)
→ Phase 3 改善対象。F9/F10 は smell(PASS を妨げない)。
