# ssot-dedup-procedure

> harness-creator 横断パターン。「全プラグイン重複解析 → 変更対象特定 → 上書き更新で一本化」を再現性高く量産するための手順正本 (ANTI-DUP-001)。
>
> **read_when** (G9, plugin-level resource-map):
> - harness-creator 自身 or 生成 plugin を改善する前 (編集着手前の事前解析)
> - 「似た内容でどちらを採用すべきか曖昧」な重複を検出・解消する時
> - redirect 宣言と本文が乖離した schema / reference を見つけた時
> - 情報が肥大化・点在して SSOT が崩れている疑いがある時
>
> 正本: `plugins/harness-creator/references/resource-map.yaml#ssot-dedup-procedure`

## 鉄則 (両方残し禁止)

重複・冗長・似た情報を見つけたら、**正本 1 つ + 残りは薄い参照 (redirect)** へ一本化する。「念のため両方残す」は禁止 — 二重定義は片方更新で必ず矛盾し、どちらが正かの判断コストを後続に永久に転嫁する。**新規追加でも keep-both でもなく、上書き更新**で潰す。

## 3 フェーズ手順 (elegant-review Phase 1→2→3 に接続)

```
[Phase 1 解析]            [Phase 2 特定]              [Phase 3 一本化]
プラグイン全体を    ──▶  正本を 1 つ決定し      ──▶  正本以外を $ref/参照に
機械 + 多角で重複検出      変更対象を列挙              上書き縮約・再 lint
  │                          │                          │
  ▼                          ▼                          ▼
lint-ssot-duplication.py  「どちらが正本か」判断      keep-both 禁止・
+ 30 思考法 (read-only)    (型互換性・被参照数)        DUP-SCHEMA-ID=0 確認
```

### Phase 1: 全プラグイン重複解析 (read-only, 編集前)

```bash
python3 plugins/harness-creator/skills/run-build-skill/scripts/lint-ssot-duplication.py --plugin-dir plugins/<plugin>
```

| 検出ルール | severity | 意味 |
|---|---|---|
| `DUP-SCHEMA-ID` | ERROR (exit 1) | 同一 `$id` が複数ファイル — どちらが正本か曖昧 (最優先解消) |
| `REDIRECT-FAT-BODY` | WARN | redirect 宣言なのに `properties` 再掲 — 宣言と中身が乖離 |
| `DUP-REQUIRED-SET` | WARN | 同一 required(≥4) 集合 — 同一成果物の二重定義疑い |
| `DUP-PASSAGE` | WARN | 6 行窓の本文がファイル間で一致 — 参照化すべき再掲 (`templates/` は伝搬例外で除外) |

機械検出に加え、`run-elegant-review` の 30 思考法 Phase 2 (3 SubAgent 並列) で「似て非なる/統合すべき/分離すべき」の意味判断を補う。

### Phase 2: 正本決定と変更対象特定

「どちらを正本にするか」は次の優先規則で決める:

1. **被参照数が多い方** (workflow-manifest.json の resourceId / `$ref` 先) を正本
2. **機械可読・制約が強い方** (allOf / pattern を持つ schema) を正本 — 弱い方に合わせない
3. **型が非互換なら統合せず用途分離** — 例: `goal-spec.json` の `checklist` (構造化オブジェクト) と `skill-brief.json` の `checklist` (文字列配列) は混用・相互変換禁止。境界を明文化して **両者を別物として残す** (これは keep-both 例外でなく「別成果物」)

### Phase 3: 上書き一本化 (write は Phase 3 のみ)

- 正本以外の schema は **`$ref` + `x-canonical-redirect` + `x-redirect-note` のみ**の薄い stub に上書き (properties/required/allOf を再掲しない)
- 削除が権限拒否される場合は **薄い redirect への上書きで代替** — dangling 参照を残さず、移行履歴を `x-redirect-note` に自己記述できる利点もある
- reference/prompt の散文重複は「正本パス + 1 行案内」に縮約
- 再 lint して `DUP-SCHEMA-ID=0` (必須) / WARN 解消を確認

## コンテキスト分離 (必須)

多周回す解析・改善ループは親セッションを汚さないよう **SubAgent (`Agent`) または Agent Team に fork** し、親へは最終成果物と要約のみ返す。詳細は `run-build-skill/references/goal-seek-paradigm.md` の「コンテキスト分離」節。

## proposer ≠ approver

一本化の提案者と承認者を同一 context にしない (23 章)。Phase 3 の改善は別 SubAgent の評価か人間レビューを通す。

## 適用先

- `run-build-skill` Step 4 lint (生成時に対象 plugin を `--plugin-dir` 解析)
- `run-elegant-review` Phase 1/2 (重複・冗長・正本曖昧を最優先 finding 化)
- harness-creator 自己改善 (本手順で自身の plugin を周期解析)
- CI 継続強制: `governance-check.yml` が `lint-ssot-duplication.py --plugin-dir plugins/harness-creator --strict` を blocking 実行 (build Step4 は早期警告、CI が最終強制)

## アンチパターン

- 「念のため両方残す」(keep-both) — 二重定義・判断コスト転嫁
- 弱い側スキーマに合わせて正本を緩める (制約退化)
- 型非互換な checklist を無理に統合 (高リスク変換)
- redirect 宣言だけして本文を残す (`REDIRECT-FAT-BODY` = 偽の一本化)

## 関連

- `run-build-skill/scripts/lint-ssot-duplication.py` — 機械検出正本
- `run-build-skill/references/goal-seek-paradigm.md` — コンテキスト分離
- `orchestrate-gate-pattern.md` — Gate B (elegance lint) との責務直交
- 25 章 §runbook Step 4 / 5.5 / 27 章 §3.1 eval-log 規約
