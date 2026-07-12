---
name: prompt-placement-convention
description: harness-creator が生成する skill 配下に責務単位 prompt を再現性高く格納するためのディレクトリ・命名規約。SKILL.md 本文には載せず、skill 配下サブディレクトリで物理的に隔離する。
type: reference
version: 1.0.0
---

# Skill 配下 prompt 配置規約

## 適用範囲

本規約は brief.kind に応じて適用度合いを切り替える。Phase 3 で確定 (2026-05-21)。

| brief.kind | 責務単位 7 層 prompt | brief.responsibilities[] |
|---|---|---|
| `run` | **必須** | 1 件以上 (空配列禁止) |
| `assign` | **必須** | 1 件以上 (空配列禁止) |
| `ref` | 既定 skip (`prompt_creator_policy: skip`) | 空配列許容 |
| `wrap` | 既定 skip (`prompt_creator_policy: skip`) | 空配列許容 |
| `delegate` | 既定 skip (`prompt_creator_policy: skip`) | 空配列許容 |

`ref/wrap/delegate` で明示的に prompt 生成したい場合は brief に `prompt_creator_policy: required` を立てて override する。

### 単一責務デフォルト補完

`brief.responsibilities[]` が省略された場合、harness-creator は次の単一責務エントリで補完する:

```yaml
responsibilities:
  - id: "R1"
    name: "<skill 名>"
    prompt_required: false
```

`kind ∈ {run, assign}` で `prompt_required: false` のままだと PG-001 で fail する。run/assign は必ず 1 件以上の `prompt_required: true` を持つこと。


prompt-creator が brief.responsibilities[] ごとに生成する 7 層 YAML を、**各 skill のサブディレクトリ** に格納する規約。再現性 (同 brief → 同パス → 同 sha256) を機械検証できる形に固定する。

## 配置パス

正規パスパターン:

```
plugins/<plugin-name>/skills/<skill-name>/prompts/<responsibility-id>.md
```

例 (`.md` 既定。`.yaml` は legacy 後方互換):

```
plugins/skill-intake/skills/run-intake-interview/prompts/R1-main.md
plugins/skill-intake/skills/run-intake-finalize/prompts/R1-main.md
plugins/prompt-creator/skills/run-prompt-creator-7layer/prompts/R1.md
```

正規表現 (`validate-build-trace.py` が照合):

```
^plugins/[a-z][a-z0-9-]*/skills/(ref|run|wrap|assign|delegate)-[a-z0-9]+(-[a-z0-9]+)*/prompts/R[0-9]+(-[a-z0-9]+(-[a-z0-9]+)*)?\.(md|yaml)$
```

## ディレクトリ規約

| 項目 | 値 | 根拠 |
|---|---|---|
| ディレクトリ名 | `prompts/` (固定) | `agents/` は plugin 直下既存ディレクトリ。SubAgent 実体 (`agents/*.md`) と責務単位 prompt 生成物 (`prompts/<R-id>.md` 既定) を物理的に分離するため別名 |
| ディレクトリ階層 | 1 階層のみ (ネスト禁止) | lint-skill-tree.py 第 13 条に準拠 |
| ファイル名 | `<responsibility.id>.md` 既定 (`.yaml` legacy) | brief.responsibilities[].id (R1, R2, ...) と 1:1 対応 |
| 拡張子 | `.md` 既定 (`.yaml` は legacy 後方互換) | seven-layer-format.md 正本フォーマット |
| インデックス | `prompts/index.json` (任意) | 全 prompt (`.md` 既定 / `.yaml` legacy) の sha256 + responsibility メタを一覧。`build-trace.json` への突合補助。任意生成 |

## 命名規則の根拠

- **`R[0-9]+`**: brief.responsibilities[].id の正規表現と同一 (正本 `../../run-skill-create/schemas/skill-brief.schema.json` `pattern: "^R[0-9]+$"`)
- **`prompts/` の選択理由**: 
  - `agents/` は `plugins/<plugin>/agents/` として既存 plugin 直下に確保済み (SubAgent .md 用)
  - skill 内部の責務 prompt は **skill 単位の成果物** であり、skill ディレクトリ配下に隔離するのが SRP に適う
  - `templates/` (kind 別正本) と区別: templates は生成入力、prompts は生成出力

## 正本の向き (canonical direction) と禁止アンチパターン

責務単位 7 層プロンプトの **SSOT 正本は常に `prompts/<R-id>.md` 側**に置く。`agents/*.md` は 9 セクション骨格 + `<!-- responsibility: <id> -->` anchor を持つ **実行アダプタ**であり、本文は prompts/ の anchor 配下に充填/参照する(`agent-template.md#prompt-creator-連携` の双方向責務契約)。向きを一意に固定する:

| 役割 | 置くもの | 置かないもの |
|---|---|---|
| `prompts/<R-id>.md` | 7 層本文の SSOT 正本(生成出力) | リダイレクトのみの空殻 |
| `agents/<role>.md` | frontmatter / 9 セクション骨格 / anchor / 起動指示 | 7 層本文の正本(prompts の重複コピー) |

### 禁止アンチパターン: PROMPT-REDIRECT-INVERSION

`prompts/<R-id>.md` を `moved_to:` 等のリダイレクトで**空殻化**し、7 層本文を `agents/*.md` 側へ**正本として移送**する構成(過去の「SSOT 統合方針 A」型)は **禁止**。理由:

- 規約の SRP 根拠(本節冒頭・命名規則の根拠 L76-78「prompts=生成出力」)と**向きが逆転**する。
- 再現性検証(同 brief → 同パス → 同 sha256、anchor coverage)の対象である prompts/ が空になり、`validate-build-trace.py` / `lint-agent-prompt-section.py --strict-coverage` が**無意味化**する。
- DRY を理由に統合する場合でも、prompts(責務契約=WHAT/WHY)と agents(実行アダプタ=WHERE/WHO)は**別レイヤーで重複ではない**ため、統合の動機自体が誤り。dedup は同一 reuse_surface 内(prompts 同士 / agents 同士)に限る。

**機械検査**: `scripts/lint-prompt-placement.py`(本 references と同一 skill 配下、canonical。ファイル名 regex は `validate_build_trace_shim` 経由で SSOT 共有)が kind ∈ {run, assign} の `prompts/<R-id>.md` について (a) リダイレクト空殻でない(7 層本文を持つ)、(b) ファイル名が `R[0-9]+...` regex 適合、を検査し、違反を `PROMPT-REDIRECT-INVERSION` / `PROMPT-FILENAME-FORMAT` として exit 1 で弾く。`harness-creator-kit-ci.yml` が全 PR で全プラグインを走査する。

## SKILL.md との関係

- **SKILL.md には prompts/ ディレクトリの内容を直接転記しない** (ユーザー要件)
- SKILL.md の `## Additional Resources` 節に「`prompts/<id>.md` (`.md` 既定 / `.yaml` legacy) — prompt-creator が生成する責務単位 7 層プロンプト (validate-build-trace.py で sha256 検証)」のような **案内 1 行のみ** 追加可
- SKILL.md は責務単位 prompt の内容を一切重複させない (300 行制約 + DRY)

## 資産分離の no-split threshold

SKILL.md 本文から新規資産ファイル (scripts/ prompts/ references/ 等) を切り出すのは、次の **いずれか** が成立する場合のみ:

- **(a) 第二消費者が存在**: 切り出し先ファイルを SKILL.md 以外 (他 skill / CI / lint / agent) が参照する
- **(b) 機械検証の対象**: sha256 突合や lint の検査対象として独立ファイルパスが必要
- **(c) 300 行 cap 逼迫**: SKILL.md が 280 行を超え cap (300 行) に逼迫している

いずれも不成立なら **インライン維持が正** (資産極少スキルへの責務分離は過剰分割であり実施しない)。適合例: `run-goal-seek` — 検証ロジックを SKILL.md `## 検証` にインライン保持し、検査ロジックの SSOT は `lint-goal-seek --self-test` と共有する。

### INLINE-SSOT-TETHER 原則

正本が別ファイルに存在する内容を SKILL.md にインライン埋め込みする場合 (初見実行の自己完結性などが目的)、次の 2 点を必須とする:

1. 正本との一致 (または整合) を機械照合する lint が存在すること
2. SKILL.md 側にその lint 名を明記すること

適合例: `run-goal-seek` (インライン検証コードの SSOT を `lint-goal-seek --self-test` と明記)。要改善例: `run-skill-feedback` (feedback_protocol 正本の対話手順を本文展開しているが、逐語一致は lint 対象外のため保証範囲を SKILL.md に明示する)。

## kind 別必須資産と充足手段 (人間向け要約)

kind ごとに必須資産カテゴリが定まる (run→prompts / ref→references+prompts / wrap→scripts+schemas / assign→rubric・schemas+prompts / delegate→prompts+schemas)。各カテゴリは次の 4 手段のいずれかで充足する:

1. ローカル実在、2. `*_refs` による共有正本参照、3. `completeness_exempt:` の理由付き免除、4. prompts 限定の `prompt_creator_policy: skip` / `use_prompt_creator: false`。

正確な定義と判定ロジックは `plugins/skill-governance-lint/scripts/lint-skill-completeness.py` の docstring を正本とする (本節は要約のみ。全文転記は二重定義 drift を生むため禁止)。

## 再現性保証

| 検証項目 | 検証主体 | 失敗時の挙動 |
|---|---|---|
| パスが正規表現にマッチ | `validate-build-trace.py` | exit 1 (trace.prompt_generation_model.per_responsibility[].layer_yaml_path) |
| responsibility.id 集合 == prompts/*.yaml ファイル名集合 | `validate-build-trace.py` | exit 1 (anchor_coverage 相当) |
| 同 brief で 2 回生成して sha256 一致 | `validate-build-trace.py` + dogfooding test | escalation 非 none 必須 |
| SubAgent.md anchor 集合 == prompts/*.yaml ファイル名集合 | `lint-agent-prompt-section.py --strict-coverage --brief <brief>` | exit 1 |

## 既存実装との橋渡し

`run-prompt-creator-7layer` SKILL.md は出力先を `plugins/<plugin>/agents/prompts/<role>.yaml` と既定しているが、本規約導入以降は次のように切替:

| brief.responsibilities[] の有無 | 出力先 |
|---|---|
| 1 件以上あり | `plugins/<plugin>/skills/<skill>/prompts/<R-id>.yaml` (本規約) |
| 空配列 (ref/wrap で legacy) | `plugins/<plugin>/agents/prompts/<role>.yaml` (旧来パス、後方互換) |

切替は `--responsibility-id <R-id>` 引数で明示する。旧来パスは deprecated とし、`prompt-creator-trace.json` に `path_convention: "skill-local-v1" | "agents-legacy"` を必須記録する。

## 検証コマンド例

```bash
# 配置確認
ls plugins/skill-intake/skills/run-intake-interview/prompts/

# 再現性ハッシュ確認
sha256sum plugins/*/skills/*/prompts/*.yaml

# trace との突合
python3 plugins/harness-creator/skills/run-build-skill/scripts/validate-build-trace.py \
  eval-log/skill-build-trace.json
```

## 関連参照

- `../../run-skill-create/schemas/skill-brief.schema.json#responsibilities` — id 仕様 (正本)
- `reproducibility-trace-schema.md#prompt_generation_model` — per_responsibility[].layer_yaml_path
- `agent-template.md#prompt-creator-連携` — SubAgent.md 側 anchor 規約
- `plugins/prompt-creator/skills/run-prompt-creator-7layer/SKILL.md` — 出力フォーマット (7 層 YAML)
