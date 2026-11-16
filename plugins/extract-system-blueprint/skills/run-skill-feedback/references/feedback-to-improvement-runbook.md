# フィードバック→改善 ブリッジ runbook (E3 人間ブリッジ)

Notion 改善要望 DB に溜まった利用者フィードバックを、`plugin-dev-planner` の改善計画へ橋渡しする手順書。
`run-skill-feedback` が収集した要望 (Stage 1) と、`run-plugin-dev-plan --mode update` の改善還流 (Stage 4) を繋ぐ **Stage 2→3→6 の人間工程**を定義する。

> **この橋は「機械の自動 read-back」ではなく「人間が 1 コマンド起点で渡す」設計。**
> 理由: Notion は BYO config 依存で fail-open になりやすく、機械が改善要望 DB を直接 query して plan 再生成を自動発火すると (a) 疎結合 (片方向依存) が壊れ、(b) 時系列ログ DB の再消費事故 (dedup 無し) を招く。
> 一次証跡: `plugin-plans/finish/harness-creator/goal-spec.json` 制約6「改善還流は Notion 改善要望 DB への直接 read-back を避ける」。
> したがって Notion は**人間可視の優先度台帳**に留め、改善着手は `source-kind=manual` の人間ブリッジ経由とする。

## パイプライン全景

```
[0] 配備   harness-creator build → 各 plugin に run-skill-feedback 同梱 (default-ON)
[1] 収集   利用者 /run-skill-feedback → Notion 改善要望 DB に1件 (対応ステータス=未着手) + 未対応要望数 rollup↑
[2] トリアージ ← 本 runbook   rollup + 優先度/重要度 で着手要望を選ぶ (人間)
[3] ブリッジ   ← 本 runbook   要望を findings 化 → emit-improvement-handoff (source-kind=manual)
[4] 改善計画   /plugin-dev-plan --mode update --out-dir <plan_dir> --improvement-handoff <handoff> → 改善用タスク仕様書再生成
[5] 改善構築   handoff routes → /capability-build で harness 改善
[6] クローズ ← 本 runbook   Notion 対応ステータス→完了 に更新 (人間)
```

Stage 0-1 は `run-skill-feedback/SKILL.md` と `references/feedback-loop-deployment.md`、Stage 4-5 は `references/pipeline-boundary-contract.md` (E3) が正本。本 runbook は **その間の人間工程 (2/3/6) のオーナーと手順**を定める。

## 担い手モデル (二役設計・正直な役割分担)

このサイクルは**二役の協働ループ**であり、単一人物が端から端まで回す設計ではない。「非エンジニアがサイクルを回す」の実像は「収集は非エンジニア・改善還流は開発担当」の分担である。

| 役割 | 担い手 | 実行 UX | 担当 Stage |
|---|---|---|---|
| **収集 (フィードバック投入)** | 非エンジニア (利用者) | 会話 UX (`/run-skill-feedback <plugin>`) | Stage 0-1 (配備済み skill で要望を Notion 改善要望 DB へ 1 件投入) |
| **改善還流 (要望→改善→クローズ)** | 開発担当 (対象 plugin owner) | CLI / slash command | Stage 2 トリアージ・Stage 3 ブリッジ・Stage 4 `--mode update`・Stage 6 クローズ |

- 非エンジニアの責務は**フィードバック投入まで** (会話で要望を残す)。改善計画の再生成・build・クローズは CLI 操作を要するため開発担当が担う。
- この分担を隠さず明示することで、「非エンジニアが 1 人で改善まで完結する」という誤読を避ける。Notion 改善要望 DB は両役の受け渡し面 (非エンジが書き込み、開発担当が Stage 2 で読む優先度台帳) として機能する。
- 会話フロントの新設はしない (ユーザー確定)。還流工程は本 runbook の CLI 手順で開発担当が実行する。

## Stage 2 — トリアージ (誰が・いつ)

- **オーナー**: 対象 plugin の owner (`SKILL.md` frontmatter `owner`)、既定は開発担当。
- **トリガ**: Notion 改善要望 DB の `未対応要望数` rollup が閾値を超えた / 定期レビュー / 高優先度要望の起票通知。
- **操作**: 改善要望 DB を `優先度` 降順・`対応ステータス=未着手` で絞り、着手する要望を 1 件選ぶ。複数を 1 サイクルで束ねてよい (findings[] は複数要望を格納できる)。

> `未対応要望数` rollup は**人間の優先度判断シグナル**であって、機械が着手を自動決定する配線ではない。`/skill-improve` や `emit-improvement-handoff` は Notion を読まない。橋渡しは必ずこの Stage 2-3 の人間工程を経る。

## Stage 3 — ブリッジ (要望 → improvement-handoff)

- **オーナー**: Stage 2 と同一 (対象 plugin owner。トリアージで着手を決めた担当が継続する)。

1. 対象の Notion 改善要望ページを開き、次を書き写す。
   - `やってほしいこと` → findings[].summary
   - `背景・困っていること` / 具体対応 → findings[].recommendation
   - `優先度`/`重要度` → findings[].severity (高→high / 中→medium / 低→low)
   - `対象スキル名` → findings[].target_ref
   - ページ URL → `--source-ref` かつ `--origin-request-ref` (起点追跡)

2. findings JSON を作る (1 ファイルに複数要望可)。
   ```json
   [
     {
       "id": "REQ-1",
       "severity": "high",
       "summary": "<やってほしいこと>",
       "recommendation": "<具体的にどう直すか>",
       "target_ref": "plugins/<plugin>/skills/<skill>/SKILL.md"
     }
   ]
   ```

3. improvement-handoff に正規化する (E3 emitter = PB-C09)。`--origin-request-*` で起点 Notion 要望を provenance に刻む。
   ```bash
   python3 plugins/harness-creator/scripts/emit-improvement-handoff.py \
     --source-kind manual \
     --source-ref "<Notion 改善要望ページ URL>" \
     --origin-request-kind notion-improvement-request \
     --origin-request-ref "<Notion 改善要望ページ URL>" \
     --target-plugin-slug <対象 plugin slug> \
     --plan-dir plugin-plans/<対象 plugin slug> \
     --findings findings.json \
     --prev-goal-spec plugin-plans/<対象 plugin slug>/goal-spec.json \
     -o improvement-handoff.json
   ```

4. planner に渡して改善計画を再生成する (E3 consumer = PB-C01)。`--out-dir` は handoff の `plan_dir` と同じ値を指定する。
   ```bash
   /plugin-dev-plan "<対象 plugin の改善>" \
     --mode update \
     --out-dir plugin-plans/<対象 plugin slug> \
     --improvement-handoff improvement-handoff.json
   ```
   provenance 検証の primary gate は planner skill が `--mode update` 時に実行する **inline 検証ブロック**で、そこが `check-intake-consumption.py` / `check-provenance-chain.py` を `--marker-dir <PLAN_DIR>` 付きで走らせ、pass marker (`<PLAN_DIR>/.gate/<gate>.pass`・goal-spec digest pin) を**自己生成**しつつ chain 断裂なし (PB-C05) を検証する。**人間が事前に marker を手作りする必要はない**。`enforce-provenance-chain` hook (PB-C11) は、この inline gate を bypass した dispatch を止める **defense-in-depth backstop** で、既存 marker の存在と digest 一致を確認する (matcher `Bash|Task` の被覆範囲に限る)。

## Stage 4-5 — 計画→構築 (既存契約)

- planner が `findings[]` を反映し `source_improvement` を goal-spec に記録 → 改善用タスク仕様書 (plan) と `handoff-run-plugin-dev-plan.json` を再生成。
- `/capability-build --handoff <handoff> --route-id <Cxx>` で harness-creator がハーネスを改善構築 (E2)。
- 詳細は `references/pipeline-boundary-contract.md` の E3/E2 節。

## Stage 6 — クローズ (帰路を人間が閉じる)

- **オーナー**: Stage 2 と同一 (対象 plugin owner。改善を還流した担当がクローズまで見届ける)。
- 改善が反映されたら、起点の Notion 改善要望ページの `対応ステータス` を `完了` に手動更新する (people/status は Notion UI 側で人手更新。API での people 指定はサポート外)。
- improvement-handoff の `provenance.origin_request.ref` に起点ページ URL が記録されているため、「どの要望がどの改善で閉じたか」を後から追跡できる (要望→改善→クローズの帰路)。

> **backlog (将来追加)**: クローズ完全性の機械可視化 — emit 済みで未クローズの改善要望を検出する orphan-detector と、`source-ref` キーの dedup は現状人手依存。closure の抜け (emit したが Stage 6 を忘れた要望) を機械で棚卸しする仕組みは future work として登録し、本サイクルでは構築しない。

## in-place 改善 (/skill-improve) との棲み分け

`/skill-improve <capability-path>` は `run-elegant-review` を起動して対象を**その場で直接パッチ**する経路であり、**この Notion ブリッジとは別系統**。以下に注意する。

- `/skill-improve` は Notion 改善要望 DB も rollup も読まない。Notion 起点の改善は必ず本 runbook (Stage 3) を経ること。
- `/skill-improve` は in-place パッチのみで `--mode update` の plan 再生成には到達しないため、plan-backed plugin では改善後に plan がドリフトしうる。plan を正本として維持したい改善は本 runbook 経由 (Stage 3-4) を用いる。

## 関連

- `references/pipeline-command-reference.md` — 全段のコマンド表記・実態・用途の一覧
- `references/pipeline-boundary-contract.md` — E3 境界契約 (改善→plan) の正本
- `plugins/harness-creator/skills/run-skill-feedback/SKILL.md` — Stage 0-1 (収集)
- `plugins/harness-creator/skills/run-build-skill/references/feedback-loop-deployment.md` — Stage 0 (配備)
- `plugins/harness-creator/scripts/emit-improvement-handoff.py` — Stage 3 emitter (PB-C09)
- `plugins/plugin-dev-planner/skills/run-plugin-dev-plan/schemas/improvement-handoff.schema.json` — handoff スキーマ (provenance.origin_request)
- `doc/notion-schema/improvement-request.schema.json` — Notion 改善要望 DB スキーマ
