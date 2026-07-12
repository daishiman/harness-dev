# 29. 複数プロジェクト rubric 合成アーキテクチャ

## 目的

複数の rubric を `rubric_refs:` (YAML frontmatter 拡張) で **依存注入** し、多重継承的に合成して 1 つの評価基準を構築する。「複数プロジェクト / 案件 / タスクごとに必要情報を読みに行く」というユーザー要求の核心を、`assign-*-evaluator` を増やさずに **基準リソースの差し替え** だけで実現する。

## 出力 (このファイルが定義するもの)

- `rubric_refs:` frontmatter 仕様（多重指定、merge_strategy、conflict_policy）
- L0 (共通) / L1 (ドメイン) / L2 (プロジェクト) の 3 層階層モデル
- 決定論的合成アルゴリズム（deep-merge / strict / override / layered）
- rubric YAML schema 標準（version / rules / severity / check kind）
- 依存解決ロード順序と循環参照検出
- 同じ evaluator Skill で案件 A / B を切り替えるパターン
- 合成結果の hash 記録と eval-log への連携

## 禁則

- L0 (共通基準) をプロジェクトごとに改変しない（governance ボード承認のみ）。
- `merge_strategy: override` を最上位 L2 で濫用しない。
- rubric 間の循環参照を許容しない。
- evaluator が `rubric_refs:` を動的に書き換えない（Goodhart（評価基準を都合よく歪める罠） 防止、09 参照）。
- 不在 `rubric_refs` を silently スキップしない（必ず error / warn を起こす）。

## 読むべき関連章

| 章 | 役割 |
|---|---|
| [09-evaluation-orchestration.md](./09-evaluation-orchestration.md) | evaluator 契約、`rubric_refs:`、Goodhart（評価基準を都合よく歪める罠） 対策 |
| [03-yaml-frontmatter-reference.md](./03-yaml-frontmatter-reference.md) | 独自メタデータの強制方針、frontmatter 設計判断 |
| [23-meta-skill-architecture.md](./23-meta-skill-architecture.md) | 3 点セット、依存方向、rubric 正本の昇格条件 |
| [24-meta-skill-templates.md](./24-meta-skill-templates.md) | `ref-skill-design-rubric` の rubric.json 雛形 |
| [27-...governance...](./README.md) | rubric hash と eval-log の運用（governance 連携） |

## 1. 目的と位置付け

`assign-*-evaluator` が単一 rubric しか参照できないと、プロジェクト数 × ドメイン数だけ evaluator が増え、Skill 木が破綻する。

本章は **依存注入型クリーンアーキテクチャ** を rubric に適用する。

- evaluator は「rubric を評価する装置」であり、rubric そのものは持たない。
- rubric（評価基準）は **読み取り専用の合成可能リソース**（references/ または `ref-*` Skill）。
- 案件 / プロジェクト / タスクが増えても、**rubric を差し替える** だけで対応する。

つまり 23 章で示した「Skill は orchestration、基準は references」の原則を、**複数 rubric の合成** にまで拡張する。

## 2. `rubric_refs:` frontmatter 仕様

09 章では旧記法として単数形 `rubric_ref:` も許容していた。本章では新規設計を **複数指定可能な `rubric_refs:`** に統一し、合成ポリシーを明示する。

```yaml
---
name: assign-skill-design-evaluator
kind: evaluator
context: fork
user-invocable: false
rubric_refs:
  - ref-skill-design-rubric         # L0: 共通基準（必須）
  - references/project-x.yaml       # L2: 案件固有
  - references/security-rules.yaml  # L1: ドメイン特化
merge_strategy: deep-merge          # deep-merge | strict | override | layered
conflict_policy: most-specific-wins # most-specific-wins | error | warn-and-merge
---
```

| field | 型 | 意味 |
|---|---|---|
| `rubric_refs` | list[string] | 合成対象。`ref-*` Skill 名 または `references/*.yaml` への相対パス |
| `merge_strategy` | enum | 4 種類（§4 で定義）。省略時は `deep-merge` |
| `conflict_policy` | enum | 衝突時の挙動。省略時は `most-specific-wins` |

**Why（理由）**: 単数 `rubric_ref:` のままだと、L0 共通基準と L2 案件固有を同時に渡せず、結局 evaluator を分裂させる動機が残る。リスト化＋合成ポリシー明示で「1 evaluator × N rubric」の単純化を達成する。

## 3. rubric 3 層階層モデル

```text
        ┌─────────────────────────────────────┐
        │ L0  共通基準 (Enterprise / Universal) │  ref-skill-design-rubric
        │  - 全 Skill 共通                     │  ref-company-quality-rules
        │  - 改正は governance ボード          │
        └─────────────────────────────────────┘
                     ▲ 依存
        ┌─────────────────────────────────────┐
        │ L1  ドメイン特化 (Domain（ドメイン）)             │  ref-security-rules
        │  - security / perf / a11y / API契約 │  ref-marketing-quality-rubric
        │  - 改正は domain owner              │
        └─────────────────────────────────────┘
                     ▲ 依存
        ┌─────────────────────────────────────┐
        │ L2  プロジェクト / 案件固有 (App)      │  references/project-x.yaml
        │  - 案件 / タスク固有 done 条件        │  references/<task>-criteria.yaml
        │  - 改正は project owner             │
        └─────────────────────────────────────┘
```

優先順位: **L2 > L1 > L0**（specific が勝つ）。

| 層 | 改正主体 | 置き場所 | 例 |
|---|---|---|---|
| L0 | governance ボード（23 章） | `.claude/skills/ref-*` | `ref-skill-design-rubric` |
| L1 | domain owner | `.claude/skills/ref-<domain>-*` | `ref-security-rules` |
| L2 | project owner | evaluator 配下 `references/*.yaml` | `references/project-x.yaml` |

**Why（理由） L0 ≠ L2**: 共通基準を案件単位で改変すると、案件 A の Goodhart（評価基準を都合よく歪める罠） が会社全体に伝播する。L0 と L2 を物理的に別ファイル / 別 Skill に分けることで、改正権限の混入を防ぐ。

## 4. 合成アルゴリズム（決定論的）

4 種類の `merge_strategy` を定義する。すべて **入力 rubric 列に対し決定論的** で、同じ入力なら同じ hash を返す。

### 4.1 deep-merge

key ごとに再帰マージ。leaf 値（scalar / list）は最 specific 側（リスト後方）を採用。

### 4.2 strict

衝突キーが 1 つでもあれば **失敗**。CI ゲートで「想定外の上書き」を検知したい時に使う。

### 4.3 override

最 specific 側（リスト末尾）で **全体置換**。L0 を完全に置き換えるため、原則 L2 末尾でのみ使用可。

### 4.4 layered

階層を維持し、**評価時に逐次適用**（合成しない）。各 rule は所属層の tag を保持する。findings に「L1 由来」「L2 由来」が出る。

### 4.5 疑似コード

```text
function compose(rubric_refs, merge_strategy, conflict_policy):
    loaded = []
    for ref in rubric_refs:
        r = load_rubric(ref)             # Skill 名 or path
        validate_schema(r)               # §5 schema 準拠か
        loaded.append((ref, r))

    detect_cycle(loaded)                 # §6 循環参照検出

    if merge_strategy == "layered":
        return Layered(loaded)           # 合成せず層を保持

    result = empty_rubric()
    for (ref, r) in loaded:              # 先頭 = L0、末尾 = L2 を想定
        for key, value in r.items():
            if key not in result:
                result[key] = value
                continue
            # 衝突
            if merge_strategy == "strict":
                raise ConflictError(ref, key)
            if merge_strategy == "override":
                result[key] = value
                continue
            # deep-merge
            if is_dict(value) and is_dict(result[key]):
                result[key] = deep_merge(result[key], value)
            else:
                if conflict_policy == "error":
                    raise ConflictError(ref, key)
                if conflict_policy == "warn-and-merge":
                    log_warn(ref, key)
                # most-specific-wins (default)
                result[key] = value      # specific (後方) を採用

    result["_composition_hash"] = sha256(canonical_json(loaded))
    return result
```

**Why（理由） 決定論**: hash を eval-log に記録する以上、同じ rubric_refs から同じ結果が得られる必要がある。dict 順序や YAML 解析の非決定性を排除するため、`canonical_json` で正規化してから hash を取る。

## 5. rubric YAML schema 標準

各 rubric ファイルは以下の最小 schema に従う。

```yaml
version: 1
layer: L0 | L1 | L2          # 階層タグ（自己申告だが lint で検証）
id: ref-skill-design-rubric  # rubric 自身の ID
rules:
  - id: SKL-001
    severity: P0 | P1 | P2
    check: machine | llm | human
    script_ref: scripts/lint-name.py   # check=machine の時のみ
    prompt_ref: prompts/check-name.md  # check=llm の時のみ
    message: "..."
    rationale: "Why（理由） this rule exists"
```

| field | 必須 | 意味 |
|---|---|---|
| `version` | yes | schema バージョン。互換性ない変更で bump |
| `layer` | yes | L0/L1/L2。merge の時の specificity 解決に使用 |
| `id` | yes | rubric 識別子。composition hash の入力 |
| `rules[].id` | yes | rule 識別子。findings に出る |
| `rules[].severity` | yes | P0 deterministic / P1 common / P2 domain（09 §評価4層） |
| `rules[].check` | yes | 評価方式。machine なら script、llm なら prompt、human なら governance |

**Why（理由） `check` を 3 値に**: P0 で落とせるものを LLM に投げると sycophancy が起きる（09 章）。`check: machine` の rule は composition 後に必ず scripts/ で実行される、というルールを schema で強制する。

## 6. 依存解決とロード順序

### 6.1 SKILL.md 読込時アルゴリズム

```text
1. evaluator の frontmatter から rubric_refs を取得
2. 各 ref を topological-sort
   - ref-* Skill 名 → `.claude/skills/<name>/rubric.json` を解決
   - references/*.yaml → evaluator の skill ディレクトリからの相対パスを解決
3. 各 rubric の `layer` を確認し、L0 → L1 → L2 順に並べる
   - 同一層内では rubric_refs の記述順を採用
4. composition (§4 アルゴリズム) を実行
5. 結果を in-memory rubric として evaluator に渡す
```

### 6.2 循環参照検出

rubric ファイル自体に `extends: [...]` を持たせる派生形を許す場合、有向グラフを構築し DFS で back-edge を検出する。検出時は **fail-fast**。

```text
ref-A.yaml: extends: [ref-B]
ref-B.yaml: extends: [ref-A]    # 循環 → load 時に CycleError
```

### 6.3 不在 `rubric_refs` のエラーハンドリング

| 状況 | conflict_policy 関係なく |
|---|---|
| ref-* Skill が存在しない | `FATAL: missing rubric "<name>"` で evaluator 起動失敗 |
| references/*.yaml が存在しない | 同上 |
| schema (§5) に違反 | `FATAL: rubric schema violation` |

**Why（理由） fail-fast**: 不在 rubric を warning で通過させると、案件固有ルールが消えたまま evaluator が「passed」を返す。これは Goodhart（評価基準を都合よく歪める罠） より悪い「見えない緩和」になる。

## 7. プロジェクト切替パターン

### 7.1 同じ evaluator で案件 A / B

`assign-skill-design-evaluator` の SKILL.md は固定。プロジェクトごとに L2 だけ差し替える。

```yaml
# project A
rubric_refs:
  - ref-skill-design-rubric
  - references/project-a.yaml
```

```yaml
# project B
rubric_refs:
  - ref-skill-design-rubric
  - references/project-b.yaml
```

evaluator の本体・契約・出力スキーマは共通。**Skill は増やさず、references/ のファイルだけ増える**。

### 7.2 context-dependent な rubric 選択

タスクメタデータ（例: `task.yaml` の `project:` フィールド）から、orchestrator が動的に `rubric_refs:` を組み立てて evaluator に渡すパターン。

```text
run-execute-task
  ├── task.yaml に project: x が書かれている
  ├── rubric_refs := [ref-skill-design-rubric, references/project-x.yaml]
  └── Skill(assign-skill-design-evaluator rubric_refs=...)
```

これにより「タスクを見て必要情報を読みに行く」という要求を、**rubric 合成 1 段** で実現できる。

## 8. 合成結果のキャッシュと hash 記録

合成は決定論的なので、入力 (rubric_refs + merge_strategy + conflict_policy + 各 rubric の内容 hash) が同一なら結果も同一。

### 8.1 in-memory キャッシュ

evaluator は実行ごとに合成する。同一プロセス内では composition_hash で memoize してよい。

### 8.2 eval-log 記録（27 章 governance 連携）

evaluator は JSON 出力に **使われた rubric の合成 hash** を必ず含める。

```json
{
  "score": 82,
  "passed": true,
  "rubric": {
    "composition_hash": "sha256:abcd...",
    "components": [
      { "ref": "ref-skill-design-rubric", "hash": "sha256:1111..." },
      { "ref": "references/project-x.yaml", "hash": "sha256:2222..." }
    ],
    "merge_strategy": "deep-merge",
    "conflict_policy": "most-specific-wins"
  }
}
```

`xl-skills/eval-log/<date>-score.jsonl` に追記され、後で「どの案件のどの rubric 構成で何点取ったか」を再現できる。

**Why（理由） hash を必須にするか**: rubric を後から差し替えても、過去の score がどの基準で出たかが分からなくなると、回帰検知も governance も成立しない（23 章観測ログと同じ理由）。

## 9. クリーンアーキテクチャとの対応

| 層 | クリーンアーキテクチャ | 本章 rubric 層 | 依存方向 |
|---|---|---|---|
| L0 | エンタープライズ (Entity) | 共通基準 | 何にも依存しない |
| L1 | ドメイン (Use Case) | ドメイン特化 | L0 にのみ依存 |
| L2 | アプリケーション (Interface / Frameworks) | プロジェクト固有 | L0 / L1 にのみ依存 |

**一方向依存** (L2 → L1 → L0、逆向き禁止):

- L0 は L1 / L2 の存在を知らない（プロジェクト名が L0 に出現してはならない）。
- L1 は L0 を参照するが、L2 を参照しない（domain（ドメイン） rubric（評価基準） に project_x のキーが出ない）。
- L2 は L0 / L1 を上書き / 拡張するが、別の L2 を参照しない（案件 A と案件 B は独立）。

evaluator は L2 〜 L0 を **依存注入** されるだけで、自分から能動的に rubric を取りに行かない。これにより evaluator は「rubric の選択責任」を負わず、純粋な評価装置になる。

## 10. アンチパターン

| アンチパターン | 何が起きるか | 対処 |
|---|---|---|
| **rubric 間の循環参照** | load 時に無限ループ、または非決定的合成 | §6.2 cycle detection を fail-fast 化 |
| **L0 をプロジェクトごとに改変** | 案件 A の緩和が全社に伝播、Goodhart（評価基準を都合よく歪める罠） 拡散 | L0 は ref-* Skill にして read-only + governance 承認制 |
| **`merge_strategy: override` の濫用** | L0 / L1 が事実上消える、共通基準が形骸化 | override は L2 末尾の 1 ファイルに限定、CI で出現数を計測 |
| **不在 `rubric_refs` の silently スキップ** | 案件固有ルールが消えても passed が出る | §6.3 fail-fast |
| **evaluator が rubric_refs を動的書換** | Goodhart（評価基準を都合よく歪める罠）の極致（自分に都合のいい rubric を選ぶ） | rubric_refs は SKILL.md frontmatter で **静的に固定**、書換禁止 |
| **L2 内で別 L2 を参照** | プロジェクト間結合が発生、独立性が崩壊 | L2 は L0 / L1 のみ参照可、lint で強制 |
| **schema 不一致の rubric を混ぜる** | 合成結果が壊れる、評価不能 | §5 schema バージョンを load 時に validate |
| **composition_hash を log に残さない** | 過去 score の再現性が消える、回帰検知不能 | §8.2 出力 JSON に hash 必須化 |

## 関連章への影響

| 章 | 影響 |
|---|---|
| 09 | 新規設計は `rubric_refs:` に統一。既存 Skill の単数 `rubric_ref:` は旧記法としてだけ許容 |
| 23 | 3 点セットの「rubric 正本の昇格条件」に L0/L1/L2 の階層を追加 |
| 24 | `assign-skill-design-evaluator` の frontmatter 雛形に `rubric_refs:` 例を追記 |
| 25 | runbook に「案件追加時は references/<project>.yaml を 1 枚追加、evaluator は変えない」を明記 |
| 27 (governance) | eval-log に composition_hash を残す要件を統合 |
