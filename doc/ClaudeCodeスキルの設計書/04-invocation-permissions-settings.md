# 04. 呼び出し制御・Permissions・Settings の設計判断

## このファイルの責務

invocation control / permissions / settings の **設計判断・防御戦略・scope 運用ノウハウ** を保持する。公式の rule syntax 表・permission mode 一覧・settings scope 一覧・`skillOverrides` 値の表は記載しない。

**更新責務マトリクス**: 公式 syntax / mode / scope の追加変更は `16` のみ更新。本ファイルは「どの場面で何を選ぶか」「sandbox とどう組み合わせるか」が変わったときだけ更新する。

→ Invocation control の表: [16-official-skills-complete-reference.md §13](./16-official-skills-complete-reference.md#13-invocation-control)
→ Restrict skill access (`Skill(...)` syntax): [§20](./16-official-skills-complete-reference.md#20-restrict-claudes-skill-access)
→ `skillOverrides`: [§21](./16-official-skills-complete-reference.md#21-override-skill-visibility-from-settings)
→ Dynamic shell execution の無効化: [§17](./16-official-skills-complete-reference.md#17-dynamic-context-injection)

## 設計判断 1: `disable-model-invocation: true` をいつ使うか

**使うべき場面**:

- deploy / send message / commit / push
- production mutation
- heavy billing / expensive operation
- Read 経由でしか使わない `ref-*`

**避けるべき場面**:

- 親 Skill から `Skill(child)` で呼ぶ internal Skill
- `assign-*-evaluator` / `assign-*-generator`（subagent から preload したい）

**Why（理由）**: `disable-model-invocation: true` は subagent preload も同時に止めるため、internal worker に付けると親 Skill から協調できなくなる。

## 設計判断 2: `user-invocable: false` の意味

**使うべき場面**: internal evaluator / generator / parent Skill からのみ呼ぶ worker / slash menu に出しても意味がない reference。

**注意**: `/` menu から隠すだけで Claude からは呼べる。programmatic invocation を止めるものではない。**access 制御と勘違いしない**こと。

## 設計判断 3: `allowed-tools` と `permissions` の使い分け

| 項目 | `allowed-tools`（frontmatter） | `permissions`（settings） |
|---|---|---|
| 場所 | Skill frontmatter | settings / `/permissions` |
| 役割 | active 中の **承認省略** | tool access の allow / ask / deny |
| deny できるか | No | Yes |

**設計則**: 「禁止」は必ず `permissions.deny` で書く。`allowed-tools` を絞っても禁止にはならない。

## 設計判断 4: permission rule の限界と防御の重ね方

公式 rule syntax（→ [16 §20](./16-official-skills-complete-reference.md#20-restrict-claudes-skill-access) と Claude Code permissions docs）には次の落とし穴がある。

- **compound command は文字列全体として match される**ため、`Bash(pnpm *)` だけで安全境界は作れない（例: `pnpm install && rm -rf /` は match してしまう）。
- `ls`, `cat`, `pwd`, `grep` 等の read-only command は prompt なしで実行され得る。**prompt 強制が必要なら明示的に `ask` / `deny` を追加**する。
- 危険 command の検査は `PreToolUse` hook と必ず併用する。

**防御戦略（多層）**:

1. permission deny: restricted resource への試行自体を止める。
2. sandbox: prompt injection で Bash が走っても filesystem / network 到達範囲を制限。
3. PreToolUse hook: 決定論的な pattern 検査で残りの抜けを塞ぐ。

explicit deny rules は sandboxed Bash でも優先される。

## 設計判断 5: settings scope 運用

公式 scope 優先順位（Managed > CLI > Local > Project > User、deny は scope を超えて優先）を前提に:

- **dangerous Skill を local で off** したいときは `skillOverrides: "off"` を `.claude/settings.local.json` に。
- **shared repo の noisy Skill** は `"name-only"` で description を context から外す。
- **組織強制** したいルールは Managed 以外に書かない（個人で上書きされるため）。
- Plugin skills は `skillOverrides` の対象外。`/plugin` で管理する。

## 設計判断 6: `auto` / `bypassPermissions` の禁止

managed settings で危険 mode を禁止する設計:

```json
{
  "permissions": {
    "disableAutoMode": "disable",
    "disableBypassPermissionsMode": "disable"
  }
}
```

**用途**: 組織管理環境 / production repository で permission prompts を必須化。

## 設計判断 7: Skill shell execution の無効化判断

`!` dynamic injection を無効化する `disableSkillShellExecution: true`（→ [16 §17](./16-official-skills-complete-reference.md#17-dynamic-context-injection)）は、user / project / plugin / additional-directory source の shell command を policy disabled marker に置換する。

**判断**: untrusted plugin / contributor からの Skill を受け入れる環境では true にする。managed / bundled skills は対象外なので、組織管理 Skill は引き続き動く。

## 設計判断 8: Skill 設計に関係する settings

公式 key のうち Skill 設計と直接関係するもの:

| key | 関係 |
|---|---|
| `permissions` | tool allow / ask / deny |
| `hooks` | lifecycle automation（→ [10](./10-subagents-hooks-integration.md)） |
| `disableAllHooks` | hooks 全体停止 |
| `allowedHttpHookUrls` | HTTP hooks の宛先制限 |
| `httpHookAllowedEnvVars` | HTTP hook header interpolation の env 制限 |
| `allowManagedHooksOnly` | managed hooks 以外を block |
| `includeGitInstructions` | built-in git instructions を外し、自前 git Skill に寄せる |
| `agent` | main thread を named subagent として実行 |
| `availableModels` | model 選択肢制限 |
| `allowedMcpServers` / `deniedMcpServers` | MCP 利用制御 |
| `skillOverrides` | Skill visibility |
| `disableSkillShellExecution` | dynamic shell execution 無効化 |
| `teammateMode` | Agent Teams display mode（→ [17](./17-agent-teams-reference.md)） |

## 権限とHookの併用パターン

`permissions` と Hook は **責務が異なる** ため、片方だけで守ろうとせず役割分担する。

### 責務分離

| 観点 | `permissions` | Hook (`PreToolUse` 等) |
|---|---|---|
| 性質 | 宣言的・静的 | 動的・文脈依存 |
| 判定基準 | tool 名 / 引数文字列 match | session state / 引数解析 / 外部参照 |
| 強み | settings に明示でき監査しやすい / `disableAllHooks` でも生存 | compound command や文脈条件まで踏み込める |
| 弱み | compound command 文字列 match の限界（→ 設計判断 4） | hook 設定漏れ・disable で素通り |

### 競合時の優先順位

1. **`permissions.deny`** は最優先。Hook の allow では **bypass できない**（公式: blocking hook は allow rule より優先するが、deny rule は上書き不可）。
2. **blocking Hook（`PreToolUse` 等の deny / exit 2）** は `permissions.allow` を **上書き** する。「allow rule で素通りさせたい場面に追加検査を入れる」用途で機能する。
3. 同イベント内で複数 Hook が登録されているときは登録順 fail-fast。

### 推奨構成（二段防御）

- 一段目: `permissions.deny` に「絶対禁止」を書く（hook 無効化されても生存）。
- 二段目: `PreToolUse` hook で「文脈次第の危険」を deterministic に判定。
- `PostToolUse` は audit / 通知のみ。access 制御の責務には置かない。
- テンプレ群（`run.md` / `wrap.md` / `delegate.md`）に permissions プレースホルダが組み込まれ、`validate-frontmatter.py` が副作用ありスキルの `permissions` 有無を警告する。

詳細フロー（決定木 / 競合パターン分類 / アンチパターン）は [10 §設計判断 7 Hook競合解決の意思決定フロー](./10-subagents-hooks-integration.md#設計判断-7-hook競合解決の意思決定フロー) を参照。
