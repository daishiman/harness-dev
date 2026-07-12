# テストフィクスチャ規約（`.fixture` 拡張子戦略）

skill-creator の vitest テスト（`scripts/__tests__/`）が使うフィクスチャ命名規約と、ヘルパー仕様。

## 背景

- `scripts/__tests__/fixtures/<case>/SKILL.md` をリポジトリにコミットすると、Codex CLI / Claude Code の skill discovery がフィクスチャを「実スキル」として誤認識し、`scripts/quick_validate.js` の対象としてもピックアップされる。
- フィクスチャは意図的に invalid な YAML や境界値（≥1024文字 description, 64文字 name 等）を含むため、リポジトリに `SKILL.md` のまま残すと永続的に warning/error を出す。
- ⇒ フィクスチャは `SKILL.md.fixture` 拡張子で配置し、テスト実行時のみ `SKILL.md` に展開する。

## 命名規約

| 種別 | パス | コミット対象 |
| --- | --- | --- |
| フィクスチャ正本 | `scripts/__tests__/fixtures/<case>/SKILL.md.fixture` | ✅ コミットする |
| 一時展開ファイル | `scripts/__tests__/fixtures/<case>/SKILL.md` | ❌ コミット禁止（`.gitignore` 推奨） |
| 補助ファイル（schemas / agents / references 配下） | 通常通り `*.md` / `*.json` | ✅ コミットする |

> ルール: フィクスチャディレクトリ直下の `SKILL.md` という名前のファイルを成果物に残さない。サブディレクトリの `references/foo.md` 等は問題ない。

## ヘルパー仕様（`scripts/__tests__/helpers/load-fixture.js`）

```js
import { loadFixture } from "./helpers/load-fixture.js";

const { dir, cleanup } = loadFixture("valid-skill");
try {
  // dir/SKILL.md がテスト中だけ存在する
  const result = quickValidate(dir);
  expect(result.errors).toHaveLength(0);
} finally {
  cleanup(); // dir/SKILL.md を削除し、リポジトリ状態を復元
}
```

API:

| 名前 | 型 | 説明 |
| --- | --- | --- |
| `loadFixture(name)` | `(name: string) => { dir: string, cleanup: () => void }` | `fixtures/<name>/SKILL.md.fixture` を `fixtures/<name>/SKILL.md` にコピーし、cleanup 関数を返す。`SKILL.md.fixture` が存在しない場合（`empty-skill-md` 等）も cleanup を返す |
| `dir` | `string` | フィクスチャディレクトリの絶対パス |
| `cleanup()` | `() => void` | 一時 `SKILL.md` を削除する。エラー時にも必ず呼ぶ（`try/finally` 推奨） |

## テスト記述パターン

```js
import { describe, it, expect, afterEach } from "vitest";
import { loadFixture } from "./helpers/load-fixture.js";

describe("quick_validate", () => {
  let cleanups = [];
  afterEach(() => {
    cleanups.forEach((fn) => fn());
    cleanups = [];
  });

  it("detects long description", () => {
    const { dir, cleanup } = loadFixture("long-description");
    cleanups.push(cleanup);
    const result = quickValidate(dir);
    expect(result.errors).toContainEqual(expect.objectContaining({ rule: "R-04" }));
  });
});
```

## 新規フィクスチャ追加手順

1. `scripts/__tests__/fixtures/<new-case>/` を作成
2. `SKILL.md.fixture` をそこに配置（`SKILL.md` という名前にしない）
3. 必要に応じて `references/` / `agents/` / `schemas/` サブディレクトリを通常通り配置
4. テストで `loadFixture("<new-case>")` を呼び、必ず `cleanup()` する
5. `node scripts/quick_validate.js .claude/skills/skill-creator` を実行し、フィクスチャが skill discovery に拾われていないことを確認

## 既存フィクスチャ一覧

`scripts/__tests__/fixtures/` 配下の `<case>/SKILL.md.fixture` がフィクスチャ正本。invalid YAML / 境界値 / forbidden file 等を網羅。詳細は `codex_validation.test.js` / `quick_validate.test.js` のテストケース定義を参照。

## Playwright e2e fixture の分離規約（domain-per-file）

vitest の `.fixture` 拡張子戦略とは別軸の話として、Playwright e2e で使う fixture は **business domain 単位で file 分離する**ことを原則とする（出典: 07c-followup-002 attendance visual smoke / 2026-05-15）。

### File 配置と責務

| File | 責務 |
| --- | --- |
| `apps/web/playwright/fixtures/auth.ts` | standalone mock server / 認証 storageState / seed reset。全テストの single source of truth |
| `apps/web/playwright/fixtures/<domain>.ts`（例: `admin-meetings.ts`） | 該当 domain の seed builder（meeting 生成 / attendance 候補生成 など）。mock state を `POST /__mock/state` 等の HTTP control endpoint 経由で投入 |
| `apps/web/playwright/tests/<domain>.spec.ts` | domain fixture を import し、page object を介して assertion |

### 落とし穴

- 単一 `auth.ts` に全 domain seed builder を集中させると test 間の state drift が判定不能になる
- domain fixture が `page.route()` を独自に増やすと standalone mock との二重実装（INV-08 違反）。intercept は必ず standalone 側に閉じ、fixture は seed 投入 + clean-up のみ
- 新規 page を visual smoke 対象に加える際は **list / detail / mutation の三点 set** を standalone mock に同 wave で揃える（detail endpoint 後追いは cost が高い）

### page object 側との対応

page object helper method は visit 先 URL と 1:1 で揃え、複数 URL に跨る共通 selector を作らない。詳細は `.claude/skills/task-specification-creator/references/phase-11-screenshot-guide.md` § Page object と selector exposure の URL 1:1 規約 を参照。

## 変更履歴

| Version | Date | Changes |
| ------- | ---- | ------- |
| 1.0.0 | 2026-04-28 | 初版作成（`.fixture` 拡張子戦略の正本化、loadFixture ヘルパー仕様策定） |
| 1.1.0 | 2026-05-15 | Playwright e2e fixture の domain-per-file 分離規約を追加（07c-followup-002 由来） |
