# Changelog

## 0.2.0 - 2026-07-11

北原さん YouTube 全量/自動同期と相談 capability、根拠付き knowledge / harness artifact graph consult を **非後退（additive）** で追加。既存 capability A（21 項目目標設定）/ B（6 カテゴリ同期）の契約は不変。

新設 9 component:

- **skills** (2): `run-ubm-youtube-ingest`（URL 単発 / 厳格全量 / scheduler 無人差分の 3 モード・2-source registry・caption→承認済み ASR fallback・冪等 one-shot）/ `run-ubm-consult`（具体解を処方しないコーチング型・考え方フレーム提示・read-only グラフ consult）。
- **command** (1): `/ubm-youtube-ingest`（skill の薄い運用アダプタ。3 モード相互排他検証 + `--source` / `--dry-run` 透過。手動 sync は scheduler one-shot と同一 cursor / idempotency key を共有し別状態を作らない）。
- **agents** (2): `youtube-transcript-normalizer`（C01・provenance 5 要素を保った正規化）/ `knowledge-relation-extractor`（C08・根拠付き有方向辺の抽出）。
- **scripts** (4): `check-youtube-backfill-completeness.py`（C03・content/accountability 被覆分離の完全性ゲート）/ `index-harness-artifact-graph.py`（C05・計画×実成果物 read-only 突合 index）/ `validate-knowledge-graph.py`（C06・依存グラフ決定論再生成+検証）/ `consult-harness-artifact-graph.py`（C07・デュアルグラフ read-only consult）。

配線（非後退 additive）:

- `.claude-plugin/plugin.json` の `entry_points` に 2 skill / 2 agent / 1 command を追加。version 0.1.0→0.2.0。
- `knowledge/youtube-registry.json` / `knowledge-graph.json` / `harness-artifact-graph.json` は build では作らず、one-shot 初回実行・各 script 実行時に運用生成（`--dry-run` は初期化も含め書込 0）。
- pytest に youtube one-shot 冪等（OUT1）・backfill 完全性・graph 検証・harness index/consult のテストを追加。既存テストは不変。

学び (lessons):

- **全量性の分母は authoritative snapshot 起点で固定する**: registry 側の除外（`terminal_unavailable` / `waived`）で分母を縮められないようにし、「取得不能を除外して緑に見せる」握り潰しを完全性ゲート（C03）で封じた。`waived` はユーザー承認参照（`waiver_ref`）必須。
- **手動入口と自動 scheduler は同一 one-shot を共有する**: 別系統の状態（cursor / registry）を作らないことで、手動確認・障害リカバリと無人同期の冪等性が同じ機構で保証される。手動 `--sync` と scheduler は同じ `video_id` を idempotency key とする。
- **計画グラフと実成果物グラフを分けて突合する**: task-graph（これから作る計画）を実成果物と誤同定しないよう、C05 が provenance / freshness 付きで正規化 index を作り、C07 はそれを read-only で引くだけに徹する。
- **相談は非処方スタンスを不変条件として機械的に自己検証する**: 「具体解を出さない」「各ターン引き出し質問 ≥1」等を `feedback_contract`（IN1/OUT1）で検証し、逸脱時は該当 phase を再実行する。
- **transcript は untrusted data として封じる**: 文字起こし本文中の命令 / URL を実行対象にせず、provenance のみを制御領域（frontmatter）に置く。

marketplace: 本 plugin は `distributable:false` を維持し、`.claude-plugin/marketplace.json` / `bundles.json` に **未登録**（個人利用前提の非公開）。

## Unreleased - 2026-07-05

elegant-review (harness-creator 仕様準拠監査) による改善 (version 0.1.0 据置・dev 未リリース):

- F1: plugin-composition.yaml の責務プロンプト tier を schema enum 非含の `supporting` から `ref` へ是正 (C08-C12)。
- F2: run-ubm-knowledge-sync の劣化重複 `prompts/R1-knowledge-extract.md` を削除。抽出責務の 7層正本は agents/knowledge-extractor.md が単独所有し completeness_exempt 宣言と実体を一致化。
- F3: references/package-contract.json の pkg_checks に PKG-009〜015 を実走 ground truth で追記し false-green を解消。
- F4: 両 SKILL.md に knowledge_loop 記述子 (pattern=router-registry) を追加し自己記述を補完。
- F5: 両 workflow-manifest.json の宙吊り `gate_order` (G1/G2/G3 は phase gate に非存在) を削除。
- F6: router 非参照かつ entries=0 の空 tombstone 7 件 (principles/consultation/phase-advice/action-guides/mindset/case-studies/principles-business.json) を掃除。

## 0.1.0 - 2026-07-04

- Ported UBM goal-setting and review dialogue into one plugin with two run skills.
- Added UBM knowledge sync with registry-based MD5 detection and six-category extraction guidance.
- Added 10 agent prompts, 2 slash commands, 3 stdlib Python scripts, and the vault write-path guard hook.
- Seeded L1 curated knowledge JSON, shared schema/router, registry, and empty sync log.
- Added pytest coverage for deterministic scripts and write-path guard behavior.
