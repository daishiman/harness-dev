# Commit message template

```
<type>(<scope>): <short summary>

<body: なぜこの変更を入れたか。what より why を優先>

<footer:
  - BREAKING CHANGE: ...
  - Refs: #issue
  - Co-Authored-By: ...
>
```

## type の候補

- feat / fix / chore / docs / refactor / test / build / ci / perf / revert

## scope の例

- harness-creator / skill-intake / runtime / docs

## 制約

- 1 行目は 72 文字以内。
- body は本変更の "why" を 1-2 文で書く。
- TODO(human): 本リポジトリ固有の scope 一覧を確定する。
