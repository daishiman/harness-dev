# Phase 2 findings 集約 (3 analyst・30思考法)

## thought_method_coverage
- logical-structural: 10/10 (skipped 0)
- meta-divergent: 9/9 (skipped 0)
- system-strategic: 11/11 (skipped 0)
- **合計 30/30 used + 0 skipped = CONST_002 充足**

## 収束した根本クラスタ（KJ法 / 3 analyst 一致）
1. **環境固有実値の git 拡散（根本・最優先）** — `.notion-config.json.example`(db_id 3件 + impersonate=no-reply@shonai.inc) と `ref-notion-gmail-send-spec/references/spec-detail.md`(DB見出しに実ID直書き) に本番固有値が焼き込まれ、コピーすれば他人の本番に刺さる。漏洩 + 承認付き誤送信の根。 [L-001/L-005, M-002/M-007, S-CAUSE-1/S-STRAT-1/S-SYS-1]
2. **安全な着地点の不在と危険な唯一導線（根本）** — config 不在 fail-closed(exit2) から前進する scaffold/init が無く、ConfigError と TL;DR の唯一の足場が「実値 example のコピー」。fail-closed の摩擦が危険回避策を強化する自己強化ループ(S-LOOP-1)。 [L-006/L-007/L-008/L-011/L-012, M-004/M-006, S-LOOP-1/S-PLUS-1]
3. **config 配置・名称・到達手段の文書間不整合（派生）** — 配置点(repo-root vs 作業フォルダ=$CLAUDE_PROJECT_DIR)・宛先DB名称(メール送信先_DB vs メール送信対象者DB)・doctor 到達手段が install 形態(marketplace/clone)で割れ、loader 実探索順(CLAUDE_PROJECT_DIR 優先)とも食い違う。 [L-002/L-009/L-010, M-005/M-008, S-IMPROVE-1]
4. **保護機構(.gitignore negation)の不発（派生）** — negation `!.notion-config.example.json` が実ファイル名 `.notion-config.json.example` と語順不一致で no-op。repo 規約は `<name>.example.json`(skill-intake/mf-kessai)で notion だけ逸脱。 [L-003, M-002, S-IMPROVE-1 D-B]
5. **参照正本/メタの文書衛生越境（派生）** — plugin.json description 約500字超 / ref-spec Gotchas に運用 snapshot 混在 / secrets.py の Notion service 名ハードコード(SA鍵は config 駆動なのに非対称)。 [L-004, S-HYPO-1 D-H, S-IMPROVE-1 D-F]

## 決定的な設計制約（meta M-007 negative_case）
- DB ID は「公開可」として既定値化しうるが、**`impersonate`（送信元アドレス）は成りすまし対象ドメインに直結し悪用余地が大きいため、既定値化せず config/Keychain 必須を維持**する。値の性質で二層化する。

## R-USER-1 への正しい応答（論点 S-RONTEN-1）
- 「README に設定方法を明記」は README §2 で字面上ほぼ充足済。追記だけでは漏洩・誤送信は解消しない。
- 真の論点は C(実値廃止) > A(scaffold) > B(文書整合)。README §2 を SSOT 正本とし、矛盾する .example/ConfigError 文言を §2 へ収束させる形で R-USER-1 を満たす。

## verdict（4条件・Phase 3 前の暫定）
- 矛盾なし: **FAIL** — S-VALUE-1(contradiction): 「安全」を謳う製品の初期既定が最も危険。配置場所の競合(L-002)。
- 漏れなし: **FAIL** — scaffold/init 欠落(L-007/L-008/M-004/S-PLUS-1)、R-USER-1 の実質要件(安全着地)未達。
- 整合性あり: **FAIL** — 配置/DB名称/命名規約のドリフト(L-009/L-003/S-IMPROVE-1)。
- 依存関係整合: **FAIL** — 完了チェックリスト先頭が config 存在に依存するのに生成工程ノードが欠落(L-011/S-SYS-1/M-008)。

## Phase 3 改善優先順位（system-strategic priority_ranking 採用）
1. 実値の git 同梱を全廃: `.example` と `spec-detail.md` を README §2 同形の placeholder へ [high・auto_fixable]
2. ConfigError/doctor を生成的 scaffold へ(`--init`): placeholder skeleton を $CLAUDE_PROJECT_DIR に生成して案内(fail-closed 維持) [high]
3. config 配置文言を「作業フォルダ($CLAUDE_PROJECT_DIR)直下」へ統一(ConfigError + .example + README) [high/medium]
4. gitignore negation を実効化(ファイル名を repo 規約 `.notion-config.example.json` へ改名 + 参照追従) [medium・auto_fixable]
5. 宛先DB名称を「メール送信先_DB」へ一本化 [medium/low]
6. spec-detail のDB見出し実ID placeholder化 + 運用 snapshot 分離 [medium]
7. plugin.json description 圧縮 [low]
8. secrets.py Notion service の config 化 or 規約明示(任意・低優先) [low]
