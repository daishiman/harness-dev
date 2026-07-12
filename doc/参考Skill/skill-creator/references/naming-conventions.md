# 命名規則・参照形式（§9-10）

> 18-skills.md §9-10 の要約
> **相対パス**: `references/naming-conventions.md`
> **原典**: `docs/00-requirements/18-skills.md` §9-10

---

## §9 命名規則

### 9.1 スキル名

| 規則                       | パターン                                  |
| -------------------------- | ----------------------------------------- |
| ハイフンケース             | `{{domain}}-{{topic}}`                    |
| 具体的で明確               | 曖昧な単語（optimization, utils）を避ける |
| 動詞+名詞 または 名詞+名詞 | `{{verb}}-{{noun}}` / `{{noun}}-{{noun}}` |
| 最大64文字                 | 簡潔に                                    |

**良い例**:

| 名前                    | 説明                 |
| ----------------------- | -------------------- |
| `skill-creator`         | 動詞+名詞、明確      |
| `database-migration`    | 名詞+名詞、具体的    |
| `code-review-checklist` | 名詞+名詞+名詞、詳細 |
| `api-documentation`     | 名詞+名詞、明確      |

**悪い例**:

| 名前                                                | 問題点                |
| --------------------------------------------------- | --------------------- |
| `mySkill`                                           | キャメルケース        |
| `SKILL_CREATOR`                                     | スネークケース/大文字 |
| `optimization`                                      | 曖昧                  |
| `utils`                                             | 曖昧                  |
| `this-is-a-very-long-skill-name-that-exceeds-limit` | 64文字超過            |

### 9.2 ファイル名

Skill 更新時も classification-first で責務を切る。新規 reference は内容を表す semantic filename を使い、旧 ordinal / legacy filename を残す場合は legacy register または近接 changelog に current path を明記する。mirror が存在する場合は rename と同じ wave で同期する。

| ファイル種別 | 命名規則                                                 |
| ------------ | -------------------------------------------------------- |
| スクリプト   | `{{verb}}_{{target}}.py` または `{{verb}}_{{target}}.js` |
| 参照資料     | `{{topic}}.md` または `{{domain}}.md`                    |
| アセット     | `{{purpose}}.{{ext}}` または `{{asset-name}}/`           |

**スクリプト例**:

| ファイル名              | 説明               |
| ----------------------- | ------------------ |
| `init_skill.js`         | 初期化スクリプト   |
| `validate_structure.py` | 構造検証スクリプト |
| `log_usage.js`          | 使用記録スクリプト |

**参照資料例**:

| ファイル名             | 説明                 |
| ---------------------- | -------------------- |
| `core-principles.md`   | 設計原則             |
| `workflow-patterns.md` | ワークフローパターン |
| `skill-structure.md`   | スキル構造           |

**アセット例**:

| ファイル名           | 説明                         |
| -------------------- | ---------------------------- |
| `skill-template.md`  | SKILL.md テンプレート        |
| `output-format.json` | 出力フォーマット定義         |
| `boilerplate/`       | ボイラープレートディレクトリ |

---

## §10 ファイル参照形式

### 10.1 相対パスの記述規則

**SKILL.md からの相対パス形式を使用**:

| 参照対象   | パス形式                 |
| ---------- | ------------------------ |
| スクリプト | `scripts/{{file}}.js`    |
| 参照資料   | `references/{{file}}.md` |
| アセット   | `assets/{{file}}`        |
| Task仕様書 | `agents/{{file}}.md`     |

### 10.2 SKILL.md での参照記述形式

```markdown
## Resources

- **{{リソース1名}}**: See [references/{{resource-1}}.md](references/{{resource-1}}.md)
- **{{リソース2名}}**: See [references/{{resource-2}}.md](references/{{resource-2}}.md)

## Scripts

- `scripts/{{script-1}}.js`: {{スクリプト1の説明}}
- `scripts/{{script-n}}.js`: {{スクリプトNの説明}}

## Tasks

| Task          | 起動タイミング | 入力      | 出力       |
| ------------- | -------------- | --------- | ---------- |
| {{task-name}} | {{timing}}     | {{input}} | {{output}} |
```

### 10.3 禁止される参照形式

| 形式                 | 問題点                                 |
| -------------------- | -------------------------------------- |
| スキル名のみ         | パスが不明確で読み込みできない         |
| 絶対パス             | 環境依存（ユーザーごとにパスが異なる） |
| `../` を含む相対パス | 曖昧さが生じ、正確なパス解決ができない |

**禁止例**:

```markdown
<!-- ❌ スキル名のみ -->

See skill-creator for details.

<!-- ❌ 絶対パス -->

See /Users/dm/.claude/skills/skill-creator/SKILL.md

<!-- ❌ 親ディレクトリ参照 -->

See ../other-skill/references/shared.md
```

**正しい例**:

```markdown
<!-- ✓ 相対パス -->

See [references/skill-structure.md](references/skill-structure.md)

<!-- ✓ 同一スキル内の参照 -->

**Task仕様**: `agents/analyze-requirements.md` を参照

<!-- ✓ スクリプト参照 -->

`scripts/init_skill.js`: スキルディレクトリ初期化
```

---

## 正規表現パターン

### スキル名の検証

```javascript
const SKILL_NAME_PATTERN = /^[a-z0-9]+(-[a-z0-9]+)*$/;

function isValidSkillName(name) {
  return name.length <= 64 && SKILL_NAME_PATTERN.test(name);
}
```

### 禁止パターンの検出

```javascript
const FORBIDDEN_PATTERNS = [
  /^\//, // 絶対パス
  /\.\.\//, // 親ディレクトリ
  /^[A-Z]/, // 大文字始まり（Windowsパス）
];

function hasForbiddenPath(content) {
  return FORBIDDEN_PATTERNS.some((pattern) => pattern.test(content));
}
```

---

## 命名のベストプラクティス

### すべきこと

| プラクティス           | 例                                 |
| ---------------------- | ---------------------------------- |
| 具体的な名前を使用     | `database-migration` > `db-util`   |
| 動詞または名詞で始める | `create-component`, `code-review`  |
| ドメインを接頭辞に     | `electron-security`, `react-hooks` |

### 避けるべきこと

| アンチパターン   | 例                                      |
| ---------------- | --------------------------------------- |
| 曖昧な単語       | `helper`, `utility`, `common`, `misc`   |
| 略語の乱用       | `cfg` → `config`, `mgmt` → `management` |
| 数字のみの識別子 | `skill-1`, `v2-skill`                   |

---

## 関連リソース

- **構造仕様**: See [skill-structure.md](skill-structure.md) - §3
- **品質基準**: See [quality-standards.md](quality-standards.md) - §8
