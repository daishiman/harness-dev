---
name: agent-template
description: SubAgent の7層本文と発話・自己採点の2節を、生成元と既存lintへ接続する契約参照。
type: reference
version: 1.0.0
---

# SubAgent 生成契約

本文構造の正本は prompt-creator の `references/subagent-hybrid-format.md` と `references/seven-layer-format.md`。生成用の骨格は `../templates/agent-skeleton.md`、決定論の派生実装は `../scripts/build-subagent.py` とする。本書に骨格全文を再掲しない。

## 骨格と役割

- frontmatter は CapabilityManifest の `kindAgent` と commonCore を満たす。tools は最小権限。advisor は読み取り専用、writer は親が許可した保存範囲だけ書ける。
- 本文は Layer 1〜7。その後に、言語に応じた `## プロンプトの型` / `## Prompt Templates` と `## 自己採点` / `## Self-Evaluation` を置く。旧 Purpose / Inputs / Outputs 等の9セクション骨格は新規生成に使用しない。
- Layer 5 は 5.1 担当エージェント、5.2 ゴール定義（目的・背景・達成ゴール）、5.3 完了チェックリスト、5.4 実行方式。固定の推論手順は置かない。
- 入力・絶対パスの出所と元Skillの操作制約を Layer 3、依存順序・出力・検証・残る未達の引き継ぎを Layer 6 に保持する。
- 日本語・英語の見出し方針は `ja-contract-policy.md` に従う。Layer番号・構造IDは翻訳しない。

### tools 宣言

正本は `capability-manifest.schema.json` の `kindAgent` で、`lint-capability-manifest.py`・`validate-frontmatter.py`・`lint-agent-prompt-content.py --mode agent` が同じ規則で検査する。`tools` と `tools-inherit` はどちらか一方だけを書く。

| 書き方 | 意味 | 判定 |
|---|---|---|
| `tools: Read, Glob, Grep` | allowlist。Claude Code の実形式で `build-subagent.py` の出力形 | ✅ |
| `tools: [Read, Glob, Grep]` (block 配列も可) | 同じ allowlist の配列形 | ✅ |
| `tools: Read` | allowed-tools が無いときの既定。全ツール継承を既定にしない | ✅ |
| `tools` を省き `tools-inherit: true` | 全ツール継承 (実行時に見つかる MCP ツールを含む)。ツール名を前もって列挙できない agent 用。`build-subagent.py --tools-inherit` を明示したときだけ出す | ✅ |
| advisor で `tools-inherit: true` | 全ツール継承は書き込みの道具を含むので、読み取り専用の advisor では使えない (`build-subagent.py` は exit 2) | ❌ |
| `tools` も `tools-inherit` も無い / 両方ある | 宣言漏れ / 矛盾 | ❌ |
| `tools: inherit` | Claude Code は値をツール名として読むため全継承にならない | ❌ |

## prompt-creator 連携

起動条件は `run-build-skill/SKILL.md` Step 0・Step 7.5 と `validate-build-trace.py` の現在の resolved policy / provenance 契約を正本とする。本書に別の kind 別既定値表を置かない。

- agent または prompt 本文を生成・更新する build は prompt-creator を経由し、`prompt_provenance` に invocation・契約参照・content lint PASS を記録する。実行していない invocation を true にしない。
- `brief.responsibilities[]` の R-id を1責務1ファイルで処理する。新規は Markdown、配置は `prompt-placement-convention.md`。IDとstemは完全一致し、slug は responsibility.id に含める。
- harness-creator が7層の実行骨格と `<!-- responsibility: <id> -->` anchor を用意し、prompt-creator は owner_agent がある場合だけ発話・自己採点の2節を充填する。anchor と本文の構造を壊さない。
- 責務プロンプトの WHAT/WHY の正本は `prompts/<R-id>.md`。agent は WHERE/WHO の実行アダプタ。責務プロンプトをリダイレクトだけの空殻にしない。
- prompt を生成しないことが現契約で許される build でも、agent の発話・自己採点には実用的な内容を置く。未展開 placeholder を完了扱いにしない。

## 検証

- `lint-agent-prompt-content.py --mode agent` が7層と Layer 5 契約を検査する。
- `lint-agent-prompt-section.py` が発話・自己採点の両節を検査する。自動実行 agent は `(対話なし: 自動実行 agent)` を明記する。
- `--strict-coverage --brief <brief.json>` は対象 responsibility の anchor と本文の充足を検査する。
- `validate-build-trace.py` は責務ID・path・SHA・prompt_provenance を突合する。FAIL は停止して原因を親へ返す。生成物だけの自己PASSで代替しない。

## 命名規則

agent 名と配下構造は命名lint、description は description lint、CapabilityManifest は frontmatter validator を正本とする。生成元と配布物の差分を検査してから引き継ぐ。
