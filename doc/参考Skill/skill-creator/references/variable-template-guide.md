# 変数・テンプレートガイド

> **読み込み条件**: 動的コード生成時、テンプレート変数設計時
> **相対パス**: `references/variable-template-guide.md`

---

## 概要

スキル内でのテンプレート変数の定義・使用方法。動的なコード生成を可能にする。

---

## 1. 変数の種類

### 1.1 ソース別分類

| ソース | 説明 | 例 |
|--------|------|-----|
| user | ユーザー入力 | スキル名、説明 |
| computed | 計算値 | タイムスタンプ、ハッシュ |
| environment | 環境変数 | API_KEY、NODE_ENV |
| config | 設定ファイル | プロジェクト設定 |
| runtime | 実行時情報 | CWD、プラットフォーム |

### 1.2 型別分類

| 型 | 説明 | 例 |
|----|------|-----|
| string | 文字列 | "my-skill" |
| number | 数値 | 3000 |
| boolean | 真偽値 | true |
| array | 配列 | ["a", "b"] |
| object | オブジェクト | { key: "value" } |
| path | ファイルパス | "/path/to/file" |
| url | URL | "https://example.com" |
| any | 任意 | 動的型 |

---

## 2. 変数定義スキーマ

### 2.1 基本構造

```json
{
  "variables": {
    "skillName": {
      "type": "string",
      "required": true,
      "pattern": "^[a-z0-9]+(-[a-z0-9]+)*$",
      "description": "スキル名（ハイフンケース）",
      "example": "my-skill"
    },
    "outputPath": {
      "type": "path",
      "required": false,
      "default": ".claude/skills/{{skillName}}",
      "description": "出力先パス"
    },
    "enableLogging": {
      "type": "boolean",
      "default": true,
      "description": "ログ出力を有効化"
    }
  }
}
```

### 2.2 グループ定義

```json
{
  "variables": { ... },
  "groups": [
    {
      "name": "api-config",
      "description": "API設定",
      "variables": ["apiUrl", "apiKey", "timeout"],
      "condition": "type === 'api-client'"
    },
    {
      "name": "git-config",
      "description": "Git設定",
      "variables": ["branch", "remote", "commitMessage"],
      "condition": "type === 'git-ops'"
    }
  ]
}
```

---

## 3. テンプレート構文

### 3.1 基本置換

```
{{variableName}}
```

**例**:
```javascript
// テンプレート
const skillName = "{{skillName}}";

// 変数: { skillName: "my-skill" }
// 結果
const skillName = "my-skill";
```

### 3.2 デフォルト値

```
{{variableName:defaultValue}}
```

**例**:
```javascript
// テンプレート
const timeout = {{timeout:30000}};

// 変数なし
// 結果
const timeout = 30000;
```

### 3.3 条件付きブロック

```
{{#if condition}}
  content
{{/if}}

{{#if condition}}
  content
{{else}}
  alternative
{{/if}}
```

**例**:
```javascript
// テンプレート
{{#if enableLogging}}
console.log("Starting...");
{{/if}}

// 変数: { enableLogging: true }
// 結果
console.log("Starting...");
```

### 3.4 ループ

```
{{#each items}}
  {{this}}
{{/each}}

{{#each items}}
  {{@index}}: {{this.name}}
{{/each}}
```

**例**:
```javascript
// テンプレート
const deps = [
{{#each dependencies}}
  "{{this}}",
{{/each}}
];

// 変数: { dependencies: ["axios", "lodash"] }
// 結果
const deps = [
  "axios",
  "lodash",
];
```

### 3.5 変換フィルター

```
{{variableName | filter}}
```

| フィルター | 説明 | 例 |
|------------|------|-----|
| uppercase | 大文字 | "MY_SKILL" |
| lowercase | 小文字 | "my_skill" |
| camelCase | キャメル | "mySkill" |
| pascalCase | パスカル | "MySkill" |
| snakeCase | スネーク | "my_skill" |
| kebabCase | ケバブ | "my-skill" |
| trim | 空白除去 | "trimmed" |
| slug | スラッグ化 | "my-skill" |

**例**:
```javascript
// テンプレート
const className = "{{skillName | pascalCase}}";
const CONST_NAME = "{{skillName | snakeCase | uppercase}}";

// 変数: { skillName: "my-skill" }
// 結果
const className = "MySkill";
const CONST_NAME = "MY_SKILL";
```

---

## 4. 実装例

### 4.1 変数置換関数 (Node.js)

```javascript
function replaceVariables(template, variables) {
  let result = template;

  // 基本置換: {{var}}
  result = result.replace(/\{\{(\w+)\}\}/g, (match, key) => {
    return variables[key] !== undefined ? variables[key] : match;
  });

  // デフォルト値: {{var:default}}
  result = result.replace(/\{\{(\w+):([^}]+)\}\}/g, (match, key, defaultVal) => {
    return variables[key] !== undefined ? variables[key] : defaultVal;
  });

  return result;
}

// 使用例
const template = `
const name = "{{skillName}}";
const timeout = {{timeout:30000}};
`;

const result = replaceVariables(template, { skillName: "my-skill" });
```

### 4.2 条件・ループ対応版 (Node.js)

```javascript
function processTemplate(template, variables) {
  let result = template;

  // if/else 処理
  result = result.replace(
    /\{\{#if\s+(\w+)\}\}([\s\S]*?)(?:\{\{else\}\}([\s\S]*?))?\{\{\/if\}\}/g,
    (match, condition, ifContent, elseContent = "") => {
      return variables[condition] ? ifContent : elseContent;
    }
  );

  // each 処理
  result = result.replace(
    /\{\{#each\s+(\w+)\}\}([\s\S]*?)\{\{\/each\}\}/g,
    (match, arrayName, content) => {
      const arr = variables[arrayName] || [];
      return arr.map((item, index) => {
        let itemContent = content;
        itemContent = itemContent.replace(/\{\{this\}\}/g,
          typeof item === 'object' ? JSON.stringify(item) : item);
        itemContent = itemContent.replace(/\{\{@index\}\}/g, index);
        if (typeof item === 'object') {
          Object.keys(item).forEach(key => {
            itemContent = itemContent.replace(
              new RegExp(`\\{\\{this\\.${key}\\}\\}`, 'g'),
              item[key]
            );
          });
        }
        return itemContent;
      }).join('');
    }
  );

  // フィルター処理
  result = result.replace(
    /\{\{(\w+)\s*\|\s*(\w+)\}\}/g,
    (match, key, filter) => {
      const value = variables[key];
      if (value === undefined) return match;
      return applyFilter(value, filter);
    }
  );

  // 基本置換
  result = result.replace(/\{\{(\w+)\}\}/g, (match, key) => {
    return variables[key] !== undefined ? variables[key] : match;
  });

  return result;
}

function applyFilter(value, filter) {
  const str = String(value);
  switch (filter) {
    case 'uppercase': return str.toUpperCase();
    case 'lowercase': return str.toLowerCase();
    case 'camelCase': return toCamelCase(str);
    case 'pascalCase': return toPascalCase(str);
    case 'snakeCase': return toSnakeCase(str);
    case 'kebabCase': return toKebabCase(str);
    case 'trim': return str.trim();
    default: return str;
  }
}

function toCamelCase(str) {
  return str.replace(/-([a-z])/g, (g) => g[1].toUpperCase());
}

function toPascalCase(str) {
  const camel = toCamelCase(str);
  return camel.charAt(0).toUpperCase() + camel.slice(1);
}

function toSnakeCase(str) {
  return str.replace(/-/g, '_');
}

function toKebabCase(str) {
  return str.replace(/_/g, '-').toLowerCase();
}
```

---

## 5. スキル内での使用パターン

### 5.1 スクリプト生成時

```javascript
// generate_dynamic_code.js での使用例
import { readFileSync, writeFileSync } from "fs";

function generateScript(templatePath, outputPath, variables) {
  const template = readFileSync(templatePath, "utf-8");
  const code = processTemplate(template, variables);
  writeFileSync(outputPath, code, "utf-8");
}

// 使用
generateScript(
  "assets/api-client-node.js",
  "scripts/fetch-data.js",
  {
    skillName: "data-fetcher",
    apiUrl: "https://api.example.com",
    enableLogging: true,
    dependencies: ["axios"]
  }
);
```

### 5.2 SKILL.md生成時

```javascript
// generate_skill_md.js での使用例
const skillTemplate = `
# {{skillName | pascalCase}}

## 概要

{{description}}

## ワークフロー

{{#each phases}}
### {{this.name}}
{{this.description}}
{{/each}}

## 実行条件

{{#if requiresApiKey}}
- API_KEY環境変数が必要
{{/if}}
`;
```

---

## 6. ベストプラクティス

### すべきこと

| 推奨事項 | 理由 |
|----------|------|
| 変数名は明確に | 可読性向上 |
| デフォルト値を設定 | 欠損時の安全性 |
| 型を明示 | 検証可能 |
| グループ化 | 関連変数の整理 |
| 例を提供 | 使用方法の明確化 |

### 避けるべきこと

| アンチパターン | 問題 |
|----------------|------|
| 未定義変数をそのまま | テンプレートリテラルが残る |
| 複雑なネスト | 可読性低下 |
| 型変換の省略 | 実行時エラー |

---

## 関連リソース

- **スキーマ**: See [schemas/variable-definition.json](.claude/skills/skill-creator/schemas/variable-definition.json)
- **タイプカタログ**: See [script-types-catalog.md](script-types-catalog.md)
