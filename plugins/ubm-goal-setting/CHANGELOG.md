# Changelog

## 0.3.32 - 2026-09-03

`validate-goal-output.py` に **`--type` と本文タイトル見出しの不一致検出**、**`--peer` 層間整合チェック**、**`--help` の rc 修正** を追加。種別の取り違えと層をまたいだ値ズレが素通りしていた穴を塞いだ。

修正した問題:

- 同一の3ヶ月期報が `--type quarterly` でも `--type bimonthly` でも rc=0 で PASS していた。`TYPE_MAP` が両者を分岐キー `period` へ潰しており、以降の判定が元の `--type` を参照できず、タイトル見出しの検査が「3ヶ月の目標」「2ヶ月の目標」の両ラベルを無条件に受理していたため。
- `--help` が rc=2 を返していた。argparse が `--help` / `--version` で投げる `SystemExit(0)` を、例外ハンドラが一律 `return 2` に潰していたため。

契約の変更:

- **不一致は error（rc=1）**: `--type` に対応するタイトル見出しラベル（`weekly`=【1週間の目標】／`monthly`=【1ヶ月の目標】／`quarterly`=【3ヶ月の目標】／`bimonthly`=【2ヶ月の目標】）が本文と食い違う場合に FAIL する。エラー文は「引数側が旧種別」「ファイル側が旧種別」を書き分ける。
- **`--peer PATH`（任意・複数可）を新設**: 指定したときだけ他層のファイルを開き、期アンカー（今期の売上目標／今期の累計売上実績など）の3値を層間で突き合わせて **WARN** で報告する。`--peer` 未指定時のコードパスは従来と完全に同一で、既存の rc も変わらない。週報に存在しない期アンカーは `WEEKLY_EXEMPT_ANCHORS` で免除する。
- **`--help` は rc=0**: `SystemExit` ハンドラを `return 0 if e.code == 0 else 2` へ変更。不正な `--type` の rc=2 は不変。
- **読みの後方互換は維持**: 旧2ヶ月期報を `--type bimonthly` で再検証する経路は rc=0 のまま。`TYPE_MAP` のキー集合（argparse の `choices` の生成元）は不変。
- **内部整理**: `check_require_prefix` を `check_title_matches_type` へ統合。`Validator` は元の `--type` 値を `type_name` として保持する（第4引数・省略時は `kind` から逆引き）。script version 0.1.0 → 0.2.3。
- **テスト**: `tests/test_validate_goal_output.py` に期報の4パターン（quarterly×3ヶ月=PASS／bimonthly×2ヶ月=PASS／quarterly×2ヶ月=FAIL／bimonthly×3ヶ月=FAIL）、週報のラベル不一致、`--peer` の層間整合を追加。

不変（この修正で変えていないもの）:

- 種別別の必須見出し集合・NG表現・やらないこと3項目以上・プロジェクト別タスク方針。
- 不正な `--type` の rc=2。`--peer` 未指定時の検査内容と rc。

## 0.3.31 - 2026-09-03

期報を **2ヶ月目標から3ヶ月目標へ改定**。目標設定側（`run-ubm-goal-setting` / `info-collector` / `output-formatter` / `phase3-coordinator` / `/ubm-goal-setting`）の契約とドキュメントを3ヶ月へ統一した。

破壊的でない変更（後方互換あり）:

- **種別キーの改名**: `bimonthly` → `quarterly`。新規は `quarterly` を正とする。`bimonthly` は後方互換の別名として受理し続ける（`/ubm-goal-setting` の引数解釈・`validate-goal-output.py --type`・`workflow-manifest.json` の Phase0 gate・各 agent の入力契約）。`validate-goal-output.py` の `TYPE_MAP` は `quarterly` と `bimonthly` の両方を同一の分岐キー `period` へ写す。
- **ファイル命名**: 新規は `UBM - 3-月報（３ヶ月） - YYYY-MM-DD〜YYYY-MM-DD.md`。旧名 `UBM - 3-月報（２ヶ月） - …` と `UBM - 3-期報 - …` は読み取り・過去参照で受理を継続する（validator のファイル名チェックは `UBM - {1,2,3}-` プレフィックスと日付パターンのみを見るため旧名を弾かない）。

契約の変更:

- **期報の期間**: UBM の目標期間は月の最終月曜日起点。期報は対象3ヶ月分の月報期間の連結で、開始日=1ヶ月目の月報開始日／終了日=3ヶ月目の月報終了日（例: 7月・8月・9月分 → `2026-06-29〜2026-09-27`）。
- **ロールアップ元**: 月報2件 → **月報3件**。`info-collector` の quarterly 取得スコープを「直近3ヶ月の全週報 + 全月報（3件）+ 前回期報」へ変更。
- **validator**: 期報のサマリー見出しの必須判定を `## 【2ヶ月の目標】…` → `## 【3ヶ月の目標】…` へ変更。全角数字チェックの許容に `３ヶ月` を追加（`２ヶ月` は旧期報の後方互換で許容を継続）。なお本 branch で `validate-goal-output.py` に入った変更は 0.3.31 と 0.3.32 を合わせて 1 回の commit で、script version は `0.1.0 → 0.2.3` へ直行している（0.2.0 / 0.2.1 という中間状態は tree のどの commit にも存在しない。版数は 0.3.32 側にまとめて記録する）。
- **表示名**: 「期報（2ヶ月目標）」「2ヶ月目標」「２ヶ月」を3ヶ月へ統一。見出し名 `【今期の売上目標】` `【今期の累計売上実績】` 等は不変で、「今期」は3ヶ月を指す。

不変（この改定で変えていないもの）:

- 統一ハイブリッド21項目の構造・公式セクション順・採用案 A1（期報はヘッダーの `【今期の売上目標】` を出力しない）。
- プロジェクト別タスクの適用範囲（週報=任意／月報=必須／期報=禁止）。
- `weekly` / `monthly` の見出し集合・必須セクション・検証結果。

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
