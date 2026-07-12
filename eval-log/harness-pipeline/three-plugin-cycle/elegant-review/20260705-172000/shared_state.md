# shared_state.md (Phase1→Phase2 ファンアウト中継)

**親context破棄宣言**: 過去のreview結論・MEMORY・既存judgeを一切参照せず、今ディスク上の一次証跡のみをfreshに観察した。対象=skill-intake / plugin-dev-planner / harness-creator の依存チェーン+フィードバックサイクル。検証軸=(1)3プラグイン依存の正当性(2)plannerがharness情報を「引用(遅延参照)」でstale回避(3)サイクル一巡の成立性(4)harness-creatorのhooks/dir不在の意味。

## データフロー全体像
skill-intake ─(intake.json)→ plugin-dev-planner ─(handoff routes[])→ harness-creator ─(build)→ 実プラグイン。
- E1境界: intake→goal-spec (handoff-contract.md / mode P で planner推奨・自動起動せず)
- E2境界: plan→build (/capability-build --handoff --route-id / render-skill-brief射影 / C08 parity)
- E3境界: feedback→improvement (Notion台帳→人間ブリッジ→emit-improvement-handoff→--mode update)
- provenance chain 5ノード: intake.json → goal-spec(source_intake) → plan → build handoff → 改善成果物(source_improvement)。**Notionはchainに含めず「人間可視の優先度台帳」**。

## フィードバックサイクル (Stage 0-6)
0配備(機械) 1収集→Notion(機械/利用者) 2トリアージ(人間) 3ブリッジ→improvement-handoff(人間) 4改善計画 --mode update(機械) 5改善構築 capability-build(機械) 6クローズ Notion完了(人間)。

## 「引用(参照)」設計の実装 (三層)
1. path/ID引用: reference_refs cross-plugin相対パス + harness-creator-spec-reflection.md 46行マトリクス(絶対パス+rule-ID+要約)
2. 鮮度台帳: upstream-pins.json (path+sha256+verified_at+matrix_rows) を check-upstream-pins.py がin-repo hash再計算fail-closed / standalone disclosure-only
3. 複製限定+parity: specfm.py 二重保持+value parity test。schema/notion_configは名前参照のみ(再実装禁止)

## hooks非対称の実像
- skill-intake: hooks/ dir(5) + plugin.json配線。cross-cutting guard型
- plugin-dev-planner: hooks/ dir(2) + 配線。hook-validate-plugin-plan / enforce-provenance-chain
- harness-creator: **hooks/ dir無し。だが plugin.json に最も厚いhooks配線**。各hookは個別skill内 scripts/ に co-locate。加えて harness-creatorは他plugin向けhookのビルダーでもある

## Phase2で検証すべき9論点 (断定せず)
E1 hook配置規約の断層: planner io-contract の hook build_target=plugins/<slug>/hooks/<name>.py vs harness-creator実体=skill内scripts/ co-locate
E2 provenance hook発火経路: enforce-provenance-chain.py matcher Bash|Task が --mode update dispatch経路を被覆するか
E3 run-skill-feedback symlink配備: planner plugin.json主張(symlink)と実在(Glob検出=harness-creator1件のみ)の整合
E4 引用鮮度がcurrentか: upstream-pins.json verified_at=2026-07-02中心のdrift負債
E5 stale回避の実質: 「自動追従」でなく「drift検出+手動是正」の意味差
E6 E2 consumer受理配線: harness-creatorがroutes[]を実際読む配線(render-skill-brief/route-build-report復路)の閉性
E7 サイクル機械closure: Stage2/3/6人間工程、機械gateはStage4 provenanceのみ。Stage6クローズ強制gate不在
E8 依存宣言の非対称: planner→harness depends_on明示 vs intake→planner宣言なし
E9 配布境界と引用: standalone install時 pin disclosure-only劣化、repo-bundled invariant機械強制の有無
