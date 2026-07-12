# CHANGELOG

本ファイルは [Keep a Changelog](https://keepachangelog.com/ja/1.1.0/) に準拠し、`extract-system-blueprint` plugin の変更履歴を記録する。harness-creator 設計書 33 章 `change-governance` に紐付き、SemVer に従う。

## [0.2.0] - 2026-07-11

**破壊的変更 (配布前): MCP 接続と Notion 公開を全廃し、ローカル完結ハーネスへ縮約。** 初回 build (0.1.0・未公開) は browser-runtime MCP による実行時観測 (screenshot/JS 後 DOM/computed style) と、C02 PASS 後の Notion (`system-blueprint-catalog`) 公開を持っていたが、本バージョンで両者を撤去した。ブラウザがレンダリングした情報 (JS 実行後 DOM・viewport screenshot) は **MCP を使わずローカル headless Chrome/Chromium を Bash 経由 subprocess 起動する `scripts/browser-render.py` (C15)** で取得する (= MCP サーバー接続ではない・任意依存)。ブラウザバイナリが無い環境では browser-render が exit 3 (browser-unavailable) を返し、該当観測を `observation_gap` として記録して **WebFetch + 静的 HTTP snapshot (stdlib: html.parser + urllib)** のみで続行する (progressive enhancement)。成果物は**ローカル完結** (md + json + 5 種 Mermaid + rendered DOM/screenshot + (取得時) layout/overlay + 合成 design-tokens + サイト被覆 manifest + request ledger)。C02 の独立 verdict は Notion 公開ゲートではなくローカル draft の品質ゲート (proposer≠approver) となった。

### Added (0.2.0)

- **MCP 非依存の browser 取得 (C15 `scripts/browser-render.py`)**: browser-runtime MCP の代替。ローカル headless Chrome/Chromium を Bash 経由で起動し JS 実行後 DOM + viewport screenshot を取得する。C12 の `decide()` を import 共有して二重 fail-closed し、C08 fetch-authz hook の認可境界内で走る。バイナリ不在は exit 3 で graceful 縮退。remote font 由来の headless ハングは `--disable-remote-fonts --virtual-time-budget` で回避。self-test + pytest (test_browser_render.py) で認可 fail-closed・graceful 縮退・偽バイナリ経路を固定。

### Removed (0.2.0)

- **Notion 公開一式**: R4-publish 段階・`prompts/R4-publish.md`・`scripts/notion-upload-lifecycle.py`・`references/notion-config.md`・`references/notion-file-upload.md`・doc-emit の `--notion-payload-out`/`--notion-file-upload-manifest-out` 出力と `sink_receipts` (schema/検査)・plugin.json の Notion `permissions.network`/`secrets`(Keychain)/`notion` tag。
- **MCP 接続**: browser-runtime / notion の mcp_tools 宣言、C08 hook matcher の `mcp__browser-runtime.*`/`mcp__notion.*` 分岐と publish-gate 述語、`scripts/shrink-screenshot.py` (screenshot 縮小)。C08 は fetch-authz 単一述語 (matcher=`Bash`|`WebFetch`) へ。

## [0.1.0] - 2026-07-11

初回 build (未公開)。plugin-plans/extract-system-blueprint (14 component) の全 build 完了と、30 思考法 elegant-review / content-review の指摘反映を含む。この時点では browser-runtime MCP 観測と C02 PASS 後の Notion 公開を備えていた (0.2.0 で撤去)。

### Added

- **抽出パイプライン (C01 run-extract-blueprint)**: 参考システムの公開 URL 1 件から、認可 preflight (C12 authz-classify.py)→低負荷取得 (C09 fetch-snapshot.py)→5 方向分析 (C03-C06/C13 analyzer fan-out)→章別文書化 (C11 doc-emit.py + C10 mermaid-validate.py)→独立品質 verdict、を接続する orchestrator skill。C09 は保存済み HTML と linked CSS から `static-observation.json` を emit し、C03 がそれを provenance 付き fact 化する。fact/inference/observation_gap の相互排他分離 (`schemas/fact-inference-confidence.schema.json`) で C2 を構造担保する。
- **静的観測と欠測の正直化**: 実ピクセル描画・CWV (LCP/CLS/INP/TTFB)・JS 実行後 DOM・computed 幾何 (`bounding_box_px`)・hover/focus state は stdlib で取得不能なため、捏造せず `observation_gap` (`observation_status: blocked`, reason=`static-analysis-only`) として記録する。
- **独立品質評価 (C02 assign-blueprint-fidelity-evaluator)**: proposer≠approver の独立 context 評価。共有決定論ゲート再実行+非共有 `recount-palette-orphans.py` (common-mode 破り) で draft_hash 束縛の品質 verdict を発行し、下流 C14 の apply 入力ゲートとする (外部公開ゲートではない)。
- **自社適用 (C14 run-blueprint-apply)**: PASS 済 blueprint と自社コンテキストから採用/回避/差別化の 3 分類 apply-recommendations をローカル導出する下流 skill (network 0)。
- **fail-closed 機械層 (C08 pre-fetch-authz-guard)**: 単一 PreToolUse hook の fetch-authz 単一述語 (matcher=`Bash`|`WebFetch`) で、認可外/予算外 fetch を exit2 遮断する。
- **サイト全域被覆**: crawl_mode=single/full_site の二態。瞬間負荷レバー (origin 並列 1・最小間隔 2000ms・Retry-After 尊重) は両モード不変で、full_site は per-run 有界予算 + multi-run resume で全 URL へ到達する。budget は request/byte/page で計上する。

### Changed (elegant-review / content-review 反映)

- **C14 workflow-manifest.json 新設**: R1-ground→R2-recommend→R3-emit の実 phase 構成と実在 resources を C01/C02 と同 schema で射影し、SKILL.md frontmatter へ `manifest:` を追加 (3 skill の manifest 被覆を完全化)。
- **validate-goal-seek-anchor.py を plugin-root scripts/ へ hoist**: `skills/` 直下は skill ディレクトリのみとする配置規約へ整合し、C01/C14 の参照を更新。対象 JSONL 不在時の「OK: 0 rows」fail-open を exit 1 の fail-closed へ変更 (呼び出し配線上、不在=配線バグ)。
- **plugin-composition.yaml の実態同期**: scripts capability を実体と集合一致へ、C02→recount-palette-orphans.py (非共有)・C01/C14→validate-goal-seek-anchor.py の実消費 edge を dependencies へ追加。
- **agents 5 体の prose dangling 解消**: 実在しない `prompts/R-*.md` への authoring source 言及を「共有 anchor は frontmatter source: の R2-analyze.md・本ファイル自身が実効 7 層 SSOT」の事実へ修正。
- **ESB_RUN 配線の実効化 (C08 run-scoping)**: PreToolUse hook は別プロセスで spawn され Bash セッション内 `export ESB_RUN=1` を継承しないため、run-scoping のアクティブ化正本を「R1 冒頭の combined call = `mkdir -p .esb-authz && authz-classify` の単一 Bash 呼び (呼び時点は dir 不在=非アクティブで素通り、完了時に dir+evidence が揃い以後の全 tool call を enforce)」へ差し替え。`mkdir` 単独先行は分割禁止 (dir 発見で hook が即アクティブ化し、evidence の唯一の producer である C12 呼び自身が evidence 不在 deny で遮断される bootstrap deadlock)。bootstrap liveness は test_guard.py で回帰固定。
- **bundle_targets の正直化**: `.claude-plugin/bundles.json` への登録が manual-user-gated で保留中のため、plugin.json / envelope-draft の `bundle_targets` を `[]` へ変更 (distributable:true は維持)。登録時に `["harness-full"]` へ復元する手順は ROADMAP 短期に明記。
- **文書契約の明確化**: runbook へ network 統制の実効層 (C08 hook exit2) と宣言層 (plugin.json permissions.network) の区別を明記。command の budget 非リセット保証を「同一 out-dir 内」へ scope 限定。C09 の canonical_url 正規化規則と observation_snapshot_id の run 間安定性スコープを契約化。

## [Unreleased]

- marketplace/bundles 登録 (manual-user-gated。ROADMAP.md 短期を参照)。
