# GraphQL 統合パターン

> **読み込み条件**: GraphQL設計時
> **相対パス**: `references/integration-patterns-graphql.md`
> **親インデックス**: [integration-patterns.md](integration-patterns.md)

---

## 契約定義（Schema First）

```graphql
# schema.graphql

"""
スキル実行リクエスト
"""
input ExecuteSkillInput {
  """
  スキルID
  """
  skillId: ID!

  """
  入力パラメータ
  """
  input: JSON!

  """
  実行オプション
  """
  options: ExecuteOptionsInput
}

input ExecuteOptionsInput {
  """
  タイムアウト（ミリ秒）
  """
  timeout: Int = 30000

  """
  ドライラン（実行せずに検証のみ）
  """
  dryRun: Boolean = false
}

"""
スキル実行結果
"""
type ExecuteSkillPayload {
  """
  成功フラグ
  """
  success: Boolean!

  """
  実行結果
  """
  output: JSON

  """
  実行時間（ミリ秒）
  """
  duration: Int!

  """
  エラー情報
  """
  error: ExecutionError
}

type ExecutionError {
  code: String!
  message: String!
  path: [String!]
}

type Query {
  """
  スキル一覧取得
  """
  skills(
    first: Int = 20
    after: String
    filter: SkillFilterInput
  ): SkillConnection!

  """
  スキル詳細取得
  """
  skill(id: ID!): Skill
}

type Mutation {
  """
  スキル実行
  """
  executeSkill(input: ExecuteSkillInput!): ExecuteSkillPayload!

  """
  スキル作成
  """
  createSkill(input: CreateSkillInput!): CreateSkillPayload!
}

type Subscription {
  """
  スキル実行進捗
  """
  skillExecutionProgress(executionId: ID!): ExecutionProgress!
}
```

## TypeScript型生成（codegen）

```typescript
// codegen.ts（GraphQL Code Generator設定）
import type { CodegenConfig } from "@graphql-codegen/cli";

const config: CodegenConfig = {
  schema: "./schema.graphql",
  documents: ["src/**/*.graphql"],
  generates: {
    "./src/generated/graphql.ts": {
      plugins: [
        "typescript",
        "typescript-operations",
        "typescript-react-apollo",
      ],
      config: {
        strictScalars: true,
        scalars: {
          JSON: "Record<string, unknown>",
          DateTime: "string",
        },
        enumsAsTypes: true,
        avoidOptionals: {
          field: true,
          inputValue: false,
          object: false,
        },
      },
    },
  },
};

export default config;
```

## 型安全なクライアント使用例

```typescript
// hooks/useExecuteSkill.ts
import { useMutation, gql } from "@apollo/client";
import {
  ExecuteSkillMutation,
  ExecuteSkillMutationVariables,
} from "@/generated/graphql";

const EXECUTE_SKILL = gql`
  mutation ExecuteSkill($input: ExecuteSkillInput!) {
    executeSkill(input: $input) {
      success
      output
      duration
      error {
        code
        message
      }
    }
  }
`;

export function useExecuteSkill() {
  const [mutate, { loading, error }] = useMutation<
    ExecuteSkillMutation,
    ExecuteSkillMutationVariables
  >(EXECUTE_SKILL);

  const execute = async (skillId: string, input: Record<string, unknown>) => {
    const result = await mutate({
      variables: {
        input: {
          skillId,
          input,
          options: { timeout: 60000 },
        },
      },
    });

    if (result.data?.executeSkill.error) {
      throw new Error(result.data.executeSkill.error.message);
    }

    return result.data?.executeSkill;
  };

  return { execute, loading, error };
}
```

## 検証チェックリスト

```markdown
## GraphQL 検証チェックリスト

### スキーマ設計

- [ ] Schema Firstアプローチを採用している
- [ ] 全フィールドにドキュメントコメントがある
- [ ] Input型とPayload型が分離されている
- [ ] Nullable/Non-nullableが明示されている

### 型安全性

- [ ] codegenで型を自動生成している
- [ ] strictScalarsが有効になっている
- [ ] カスタムスカラーの型マッピングが定義されている

### パフォーマンス

- [ ] N+1問題対策（DataLoader）が実装されている
- [ ] クエリ深度制限が設定されている
- [ ] クエリ複雑度制限が設定されている
- [ ] Persisted Queriesが検討されている

### エラーハンドリング

- [ ] Union型でエラーを表現している（または error フィールド）
- [ ] エラーコードが標準化されている
- [ ] バリデーションエラーの詳細が返されている
```

---

## 関連リソース

- **パターン選択**: See [integration-patterns.md](integration-patterns.md)
- **API実装詳細**: See [api-integration-patterns.md](api-integration-patterns.md)
