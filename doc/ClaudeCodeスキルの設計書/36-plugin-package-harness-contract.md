# 36. Plugin Package Harness Contract

最終更新: 2026-05-23

## 目的

Harness Creator が量産する成果物は単独 Skill ではなく **plugin package**（`plugins/<plugin-name>/` 一式）である。本章は、その plugin package を「`/plugin install <plugin>` 一発で、必要な Skill / Agent / Hook / script / settings / config が齟齬なく揃って動く」状態に到達させるための **同梱契約（harness contract）** を正本として定義する。

具体的には次の 3 つを正本として固定する。

1. **`package_mode`**: 配布形態の閉じた列挙（`bundle` / `skill-only`）と、それぞれの正本パス・適用ゲートの差分
2. **PKG-001〜017**: package completeness check の閉じた ID 列挙（P0 静的検査 / Phase 1 smoke / Phase 2 出荷前 gate / 予約）
3. **Install UX Contract**: ユーザー視点で plugin install から最初の Skill 起動までに発生すべき / 発生してはならない事象の列挙

本章は 23 章案 D' で確立した plugin アーキテクチャ、34 章 Phase 0/1/2 ロードマップ、27 章 rubric governance、35 章 meta-harness observables の上に乗る派生章であり、これら 4 章との片道リンクを必ず双方向に閉じる（§関連章 参照）。

---

## 正本の分担

| 領域 | 正本 | 本章で扱うこと |
|---|---|---|
| plugin 物理レイアウト | `34-plugin-governance-roadmap.md` | Phase 0/1/2 ゲートが参照する PKG ID の提供 |
| settings 派生マージ | `34a-settings-merge-spec.md` | package 同梱判定（PKG-003 と §4 名前空間共有） |
| eval-log パス | `27-rubric-governance-runbook.md` §3.1 | PKG gate の eval-log 保存規約に従う |
| PKG fail の観測軸 | `35-meta-harness-feedback-loop.md` `pkg_check_failed` | failure_mode を発火させる側として定義 |
| PKG ID 改廃 governance | `27-rubric-governance-runbook.md` §4.1 | 本章は改廃の **対象**、決裁は 27 章 |
| 命名規約 | `06-classification-and-naming.md` 第17条 | plugin 名は配置パス、Skill 名は kebab-case |
| 配布レイヤー時系列 | `25-meta-skill-runbook.md` 配布レイヤー表 | 現行（creator-kit）⇔ Phase 2 以降（plugin package）の対応 |

**自己制約**: 本章は PKG ID の **意味と検査内容** を正本として持つが、ID 改廃（新設 / 分割 / 削除 / 意味変更）の **決裁経路** は 27 章 §4.1 に従う。本章単独で ID を増減することはできない。

---

## §`package_mode`

`package_mode` は plugin package の配布形態を表す閉じた列挙であり、`plugins/<plugin-name>/references/package-contract.json` の最上位キーとして宣言する。公式 CLI が読む `.claude-plugin/plugin.json` には harness 専用キーを置かない。

| `package_mode` | 配布意図 | 正本パス（Skill 本文） | 適用 PKG ID | 用途 |
|---|---|---|---|---|
| `bundle` | 公開配布。install UX を満たす plugin package | `plugins/<plugin-name>/skills/<skill-name>/SKILL.md`（一次） | PKG-001〜010 必須、PKG-011〜015 出荷前必須 | 新規量産の既定値。**新規 plugin はこちらを選ぶ** |
| `skill-only` | legacy / dev-only / migration exception | `.claude/skills/<skill-name>/SKILL.md`（一次。`plugins/...` 側があれば派生） | PKG-002 / PKG-004 のみ任意適用、それ以外は適用対象外（下の PKG 一覧の「適用 `package_mode`」列と `ref-pkg-contract/references/pkg-id-catalog.yaml` の `package_modes`） | 下記 3 例外に限定 |

### `skill-only` 適用範囲（恒久例外 3 種）

| 例外 | 説明 | 参照 |
|---|---|---|
| legacy | creator-kit 時代に作られた既存資産で plugin 化未着手のもの。Phase 2 移行前の暫定状態 | 25 章 配布レイヤー表 |
| dev-only | 設計書 dogfooding など、配布物ではなく自己検査用 artifact | 26 章 §dogfooding と `skill-only` モードの関係 |
| migration | Phase 2 移行作業中の一時的な並走状態。期限付きで `bundle` へ収束させる | 34 章 Phase 2 ゲート |

新規 plugin で `package_mode: skill-only` を選ぶことは禁止（CI block 対象）。例外 3 種のいずれかに該当することを `references/package-contract.json` の `package_mode_exception` フィールドに記録すること（`legacy` / `dev-only` / `migration` の閉列挙）。

### `bundle` での正本パスとの関係

`bundle` mode では、開発作業の書き換え先は常に `plugins/<plugin-name>/skills/<skill-name>/SKILL.md`。`.claude/skills/<skill-name>/` は `build-claude-symlinks.py`（34 章 Phase 0）が生成する **symlink 派生表現** にすぎず、人間も AI もここを直接編集してはならない（24 章 §正本パスのレイヤー優先順位）。

---

## §Install UX Contract

`bundle` mode plugin が満たすべき install UX を以下に固定する。`skill-only` mode には適用しない。

### 必須事象（install 後 60 秒以内に観測可能であること）

1. `/plugin install <plugin>` 実行後、追加の手動コピー・symlink 操作なしで以下が完了する
   - `plugins/<plugin-name>/skills/*` 配下の全 Skill が `/skill list` に列挙される
   - `plugins/<plugin-name>/agents/*` 配下の全 Agent が `Agent` tool の `subagent_type` で参照可能になる
   - `plugins/<plugin-name>/hooks/*` 配下の hook が settings に反映される（hook 名・event の一覧が `claude hook list` 相当で確認できる）
   - `plugins/<plugin-name>/scripts/*` が実行可能ビットつきで配置される
2. plugin が宣言する `permissions` は plugin スコープ内でのみ有効化される（34 章 公式制約 b）
3. plugin が参照する全パスが plugin root 配下に閉じている（34 章 公式制約 e）

### 禁止事象（install 直後〜初回 Skill 起動までに発生してはならない）

1. plugin 外（`scripts/` `adapters/` `.claude/config/` 等）への参照解決失敗
2. 他 plugin と名前空間が衝突した状態でのサイレント上書き（PKG-003 で fail させる）
3. ユーザーに手動で `chmod +x` / `ln -s` / `cp` を要求するエラー
4. `.claude/settings.json` への直接書き込み（必ず Layer2 settings 断片からの派生生成経路を通る、34a 章 §2）

### 計測点

Install UX Contract の達成は PKG-010 install smoke（後述）で機械検証する。Smoke は `eval-log/<plugin>/pkg-010/<YYYY-MM-DD>-<run>.{json,log}` に保存され（27 章 §3.1）、fail は 35 章 `pkg_check_failed` failure_mode として観測カウントされる。

---

## §PKG-001〜017 一覧

PKG ID は閉じた列挙であり、本表に存在しない ID は **存在しないものとして扱う**。新設・分割・削除・意味変更は 27 章 §4.1 governance を経由する。

「実装」列の path は `plugins/harness-creator/skills/` からの相対。`<plugin>` は検査する plugin の名前で、`--plugin <plugin>` は省けない（省くと exit 2）。install 先で plugin の dir を直に渡すときは、validate-plugin-package.py と validate-plugin-permissions.py に `--plugin-dir <dir>` を使う。

### Phase 0 P0 静的検査（PKG-001〜009、必須）

| ID | 名称 | 検査内容 | 実装 | 適用 `package_mode` |
|---|---|---|---|---|
| PKG-001 | `claude plugin validate --strict` 通過 | 公式 CLI の strict validate が exit 0 | `run-plugin-package-check/scripts/run-plugin-validate-strict.sh --plugin <plugin>`（公式 CLI ラッパー） | `bundle` |
| PKG-002 | `plugin.json` frontmatter 完備 | `.claude-plugin/plugin.json` の `name` / `version` / `description` と、`references/package-contract.json` の `package_mode` / `entry_points` の必須キー充足 | `assign-plugin-package-evaluator/scripts/validate-plugin-package.py --plugin <plugin> --check pkg-002` | `bundle` `skill-only` |
| PKG-003 | package 単位の名前空間衝突検査 | 同一 marketplace 内で `skill-name` / `agent-name` / `hook-name` / `permission-name` の衝突なし。34a §4 と名前空間定義を共有 | `assign-plugin-package-evaluator/scripts/validate-plugin-package.py --plugin <plugin> --check pkg-003` | `bundle` |
| PKG-004 | SKILL.md frontmatter 完備 | 03 章 frontmatter 必須キー、`responsibility_refs` / `schema_refs` / `manifest` を含む | `assign-plugin-package-evaluator/scripts/validate-plugin-package.py --plugin <plugin> --check pkg-004`（repo の clone では `scripts/validate-frontmatter.py --skills-dir plugins/<plugin>/skills` も使える） | `bundle` `skill-only` |
| PKG-005 | Agent definition 整合 | `plugins/<plugin>/agents/*.md` の name と SKILL.md `subagent_refs` が一致 | `assign-plugin-package-evaluator/scripts/validate-plugin-package.py --plugin <plugin> --check pkg-005` | `bundle` |
| PKG-006 | Hook registration 整合 | `plugins/<plugin>/hooks/*.{py,sh}` が settings 断片の `hooks` 配列で全て参照されている。逆方向に未登録 hook ファイルがない | `assign-plugin-package-evaluator/scripts/validate-plugin-package.py --plugin <plugin> --check pkg-006` | `bundle` |
| PKG-007 | script 存在 + 実行可能 | 対象は SKILL.md の明示 `script_refs` と plugin root 直下の `scripts/*.{py,sh}`。plugin 内に実在し、shebang と `+x` ビットを持つ。本文・他の `*_refs` は対象外（PKG-009 等の別責務）。実行規則の正本は `validate-plugin-package.py` の `check_pkg_007` | `assign-plugin-package-evaluator/scripts/validate-plugin-package.py --plugin <plugin> --check pkg-007` | `bundle` |
| PKG-008 | settings 断片 lint | `plugins/<plugin>/settings/*.json` が 34a 章 INV-1〜12 を満たし、Layer3 派生で衝突を発生させない | `assign-plugin-package-evaluator/scripts/validate-plugin-package.py --plugin <plugin> --check pkg-008` | `bundle` |
| PKG-009 | 外部参照ゼロ | SKILL.md が plugin root 外を参照しない（34 章 公式制約 e）。例外は `references/package-contract.json` の宣言（`depends_on` の plugin、`runtime_dependencies` の owned-vendored の写し（正本と byte が同じとき）、`repo_refs`（repo clone の中にだけある資産。参照ごとに実在を確かめ、使われていない宣言は fail））と、lint の既定の許可 prefix（`.claude/`・`eval-log/`・`references/`・`scripts/`）。既定の許可 prefix は宣言なしで通り、実在も確かめない。pass は「宣言の無い外部参照が無い」ことだけを示し、名指しした path が解決できることは示さない | `run-plugin-package-check/scripts/lint-pkg-009.py --skills-dir plugins/<plugin>/skills --fail-on-external` | `bundle` |

### Phase 1 install smoke（PKG-010、必須）

| ID | 名称 | 検査内容 | 実装 |
|---|---|---|---|
| PKG-010 | install smoke | local marketplace から `/plugin install` を擬似実行し、§Install UX Contract「必須事象」3 項目と「禁止事象」4 項目を観測する。実行ログは `eval-log/<plugin>/pkg-010/` に保存 | `run-plugin-package-check/scripts/smoke-plugin-install.sh --plugin <plugin>` |

### Phase 2 出荷前 gate（PKG-011〜015、必須）

| ID | 名称 | 検査内容 | 実装 |
|---|---|---|---|
| PKG-011 | uninstall 完全性 | `/plugin uninstall <plugin>` 後に plugin 由来の symlink / settings 断片 / hook 登録が残存しない | `run-plugin-package-check/scripts/smoke-plugin-uninstall.sh --plugin <plugin>` |
| PKG-012 | upgrade 冪等性 | 同一 version の re-install が no-op であり、異なる version の install が破壊的変更を起こさない | `run-plugin-package-check/scripts/smoke-plugin-upgrade.sh --plugin <plugin>` |
| PKG-013 | permission scope 検証（4 sub-check） | `package_mode: bundle` plugin が宣言する permission が plugin スコープ内で閉じていることを 4 観点で検査（§PKG-013 分割表 参照） | `run-plugin-package-check/scripts/validate-plugin-permissions.py --plugin <plugin> --check 013a`（013b〜013d も同じ形） |
| PKG-014 | runtime contract 検証 | SKILL.md 宣言の `kind` / `combinator` と実 runtime 挙動が一致（28 章 script execution model） | `assign-plugin-package-evaluator/scripts/validate-plugin-package.py --plugin <plugin> --check pkg-014` |
| PKG-015 | rubric 違反率しきい値 | 当該 plugin の直近 release で 27 章 rubric 違反率が governance 設定値を下回る。履歴 bootstrap 中は明示 `not_applicable` | `run-plugin-package-check/scripts/run-pkg-015.py --plugin <plugin> --log-dir <log-dir> --out <pkg-log>` |

#### PKG-013 分割表（permission scope 4 sub-check）

| sub-ID | 検査対象 |
|---|---|
| PKG-013a | tool permissions（Bash 等の許可コマンド範囲が plugin スコープ宣言を超えない） |
| PKG-013b | file system permissions（読み書き対象が plugin root 配下に閉じる） |
| PKG-013c | network permissions（外部通信先の allowlist が plugin manifest 宣言と一致） |
| PKG-013d | MCP / external integration permissions（Notion / Drive / Gmail 等の scope が manifest と一致） |

### 予約 ID（PKG-016〜017）

| ID | 状態 |
|---|---|
| PKG-016 | **予約**。意味は未確定。34 章 Phase 2 ゲートを clear する前に本章で確定すること |
| PKG-017 | **予約**。意味は未確定。34 章 Phase 2 ゲートを clear する前に本章で確定すること |

予約 ID を実装する際は、ID 新設として 27 章 §4.1 governance を通すこと。「予約済み」状態のままで Phase 3 へは進めない。

---

## §`references/package-contract.json` schema

PKG ID 群と配布の宣言を機械可読化した契約。`plugins/<plugin>/references/package-contract.json` として各 plugin に配置する。

**機械の正本は `plugins/harness-creator/skills/ref-pkg-contract/schemas/package-contract.schema.json`**。下の例はその骨格で、`package_mode` と `pkg_checks` の意味を説明するために載せている。正本には、ほかに `plugin_name`・`entry_points`・`distribution`・`codex_distribution`・`depends_on`・`repo_refs`・`runtime_dependencies`・`codex_alternatives` がある。key の追加や pattern の変更は正本で行い、この例は正本に合わせて写すだけにする。

### schema の骨格（JSON Schema draft 2020-12。正本からの抜粋）

```json
{
  "$schema": "https://json-schema.org/draft/2020-12/schema",
  "$id": "https://harness/schemas/package-contract.json",
  "type": "object",
  "required": ["package_mode", "plugin_name", "entry_points", "distribution", "depends_on", "runtime_dependencies", "codex_alternatives", "pkg_checks"],
  "properties": {
    "package_mode": {
      "enum": ["bundle", "skill-only"]
    },
    "package_mode_exception": {
      "enum": ["legacy", "dev-only", "migration"],
      "description": "package_mode が skill-only の場合のみ必須"
    },
    "pkg_checks": {
      "type": "object",
      "patternProperties": {
        "^PKG-(00[1-9]|01[0-2]|013[a-d]|01[4-5]|01[6-7])$": {
          "type": "object",
          "required": ["status", "last_run_at"],
          "properties": {
            "status": { "enum": ["pass", "fail", "skip", "not_applicable"] },
            "last_run_at": { "type": "string", "format": "date-time" },
            "eval_log_path": { "type": "string" },
            "skip_reason": { "type": "string" },
            "findings_count": { "type": "integer", "minimum": 0 }
          },
          "allOf": [
            {
              "if": { "properties": { "status": { "enum": ["skip", "not_applicable"] } } },
              "then": { "required": ["skip_reason"] }
            }
          ]
        }
      },
      "additionalProperties": false
    }
  },
  "allOf": [
    {
      "if": { "properties": { "package_mode": { "const": "skill-only" } } },
      "then": { "required": ["package_mode_exception"] }
    }
  ]
}
```

`pkg_checks` の key は、PKG-013 を 013a〜d に展開した形だけを受ける。素の `PKG-013` は記録の key にできない。PKG-016/017 は予約 ID なので pattern では受けるが、意味が決まるまでは記録しない。

### validator

contract 専用の validator script は置いていない。今は次の 2 つで確かめる。

- `tests/test_package_contract_schema.py`: 全 plugin の `package-contract.json` を正本 schema（draft 2020-12）で検証する。あわせて、catalog の PKG ID の集合と schema の pattern が受ける集合が一致することも確かめる。
- `make plugin-package-check`（`scripts/validate-plugin-packages.py`）: 全 plugin に PKG-002〜008 を回す advisory のラッパー。PKG-002 が contract の `package_mode`/`entry_points` を見る。PKG-002/004 は今は非ブロッキング。

### `status: not_applicable`

dogfooding artifact（26 章）など `skill-only` 例外時に PKG-002 / PKG-004 以外を適用しないケースは、各 PKG ID に `status: "not_applicable"` と `skip_reason` を明示する。`skip` は「実行予定だが今回省略」、`not_applicable` は「契約上対象外」と意味を分けること。

---

## §現状との差分

2026-11-15 時点での実装ギャップを以下に列挙する。本表は実装進捗に応じて更新する。path は `plugins/harness-creator/skills/` からの相対（repo root の script は `scripts/` から書く）。

| 項目 | 現状 | 必要対応 | 起票先 |
|---|---|---|---|
| `assign-plugin-package-evaluator/scripts/validate-plugin-package.py` | PKG-002〜008 / PKG-014 の `--check` 対応済み | PKG ID 別 sub-command と findings JSON を維持 | 34 章 Phase 0 タスク |
| `run-plugin-package-check/scripts/run-plugin-validate-strict.sh` | 実装済み | 公式 CLI の版上げに追従する | 34 章 Phase 0 タスク |
| `run-plugin-package-check/scripts/smoke-plugin-{install,uninstall,upgrade}.sh` | 実装済み | Phase 1/2 gate として維持 | 34 章 Phase 1/2 ゲート |
| `run-plugin-package-check/scripts/validate-plugin-permissions.py` | 実装済み（013a〜d） | PKG-013 4 sub-check を維持 | 34 章 Phase 2 ゲート |
| 全 plugin の `references/package-contract.json` | 23 plugin すべてに配置済み。`tests/test_package_contract_schema.py` が schema で検証 | 新しい plugin でも配置を保つ | Phase 0 lint 化 |
| PKG-004 の適用 | harness-creator に `--check pkg-004` を走らせると fail（P1 の findings が 35 件） | SKILL.md の frontmatter を 03 章の必須キーにそろえるか、PKG-004 の要求を見直す | 27 章 §4.1 governance |
| PKG-016 / PKG-017 意味確定 | 未確定 | Phase 2 clear 前に本章で確定 | 27 章 §4.1 governance |
| 35 章 `pkg_check_failed` observable 配線 | `run-plugin-package-check/scripts/aggregate-pkg-findings.py` が fail 時に `.claude/logs/meta-harness.jsonl` へ `pkg_check_failed` を 1 行追記する。35 章 collector がこの行を拾うかは未確認 | collector の入力に `meta-harness.jsonl` が入っているかを確かめる | 35 章 collect → classify ステップ |

---

## §関連章（双方向リンク）

| 章 | 本章との関係 | 逆方向リンク |
|---|---|---|
| 24 メタスキルテンプレ | 正本パスの `bundle` / `skill-only` 切替を依存 | 24 章 §正本パスのレイヤー優先順位 |
| 25 メタスキルランブック | 配布レイヤー時系列で `manifest` 二義性を解消 | 25 章 §配布レイヤーの時系列分離 |
| 26 dogfooding | `skill-only` の dev-only 恒久例外を受ける | 26 章 §dogfooding と `skill-only` モードの関係 |
| 27 rubric governance | PKG ID 改廃の決裁経路、eval-log パス規約 | 27 章 §3.1 PKG gate 用 eval-log パス、§4.1 PKG ID 改廃 governance |
| 28 script execution model | PKG-014 runtime contract 検証の根拠 | 28 章 |
| 33 change governance | PKG ID 変更は P0_breaking として扱う境界 | 33 章 MECE 表 |
| 34 plugin governance roadmap | Phase 0/1/2 ゲートが本章の PKG ID を参照 | 34 章 Phase 0/1/2 タスク |
| 34a settings merge spec | PKG-003 と §4 名前空間共有 | 34a 章 §4 |
| 35 meta-harness FB ループ | PKG fail → `pkg_check_failed` failure_mode の閉ループ | 35 章 §observables、§PKG gate 連動の閉ループ |

---

## §更新ルール

1. PKG ID の新設・分割・削除・意味変更は本章を正本として行うが、**決裁は 27 章 §4.1 governance を経由**する（自己制約）
2. `package_mode` の列挙値変更は P0_breaking として 33 章 proposal を作成する
3. `references/package-contract.json` schema の破壊的変更（required 追加、enum 削除、`pkg_checks` パターン変更）は P0_breaking として 33 章 proposal を作成する
4. Install UX Contract の必須事象 / 禁止事象の追加・削除は P0_breaking として 33 章 proposal を作成する。**ユーザー観測仕様であり、サイレント変更を禁止**
5. 予約 ID（PKG-016 / 017）を実装する際は ID 新設として §更新ルール 1 に従う。予約状態のまま Phase 3 へ進まない
6. 本章で `eval-log` パスを再定義しない。27 章 §3.1 を一意の正本とする
7. 本章で 35 章 failure_mode 列挙を再定義しない。35 章 observables.json を一意の正本とする
