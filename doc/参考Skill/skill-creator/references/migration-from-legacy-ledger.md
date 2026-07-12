# Migration from Legacy Skill Ledger to Fragment Form

旧 monolith な skill ledger（単一 `LOGS.md` / `SKILL-changelog.md` / `references/lessons-learned-*.md`）を、1 entry = 1 file の fragment 方式（Changesets パターン）へ移行する手順書。

## なぜ移行するのか

### 旧方式の問題

- skill ledger は append-only な単一 markdown だった。複数 worktree が同じファイルの末尾に同時 append すると、git の自動マージは「同一バイト位置への異なる行追加」を解決できず、毎回 conflict が発生していた。
- conflict のたびに先 merge した側の内容が「上書き」or「重複」する判断ミスが頻発し、ledger 自体が信頼できなくなる事故が複数回起きた。
- monolith ファイルは行数が肥大化（74 個の `lessons-learned-*.md` を 1 つにまとめると 5000 行超）し、Progressive Disclosure の 500 行ガードを破る原因にもなっていた。

### 新方式（fragment + render）

- ledger entry を 1 件ずつ独立したファイル（fragment）として `LOGS/`, `changelog/`, `lessons-learned/` 配下に配置する
- fragment 命名: `<YYYYMMDD>-<HHMMSS>-<escapedBranch>-<nonce>.md`（`escapedBranch` は `/` を `_` 置換、`nonce` は 8 hex）
- 同一 branch・同一秒の追記でも nonce が違うため別ファイルになる → git conflict 発生 0
- 集約読み出しは `pnpm skill:logs:render --skill <name> [--include-legacy]`
- 追記書き込みは `pnpm skill:logs:append --skill <name> --type log|changelog|lessons-learned --notes "..."`

## 移行手順（5 step）

### Step 1. monolith ledger を `_legacy.md` に rename

```bash
SKILL_DIR=".claude/skills/<your-skill>"

# LOGS.md → LOGS/_legacy.md
mkdir -p "$SKILL_DIR/LOGS"
git mv "$SKILL_DIR/LOGS.md" "$SKILL_DIR/LOGS/_legacy.md"

# SKILL-changelog.md → changelog/_legacy.md
mkdir -p "$SKILL_DIR/changelog"
git mv "$SKILL_DIR/SKILL-changelog.md" "$SKILL_DIR/changelog/_legacy.md"
```

### Step 2. references/lessons-learned-*.md を `lessons-learned/_legacy-*.md` に一括 rename

```bash
mkdir -p "$SKILL_DIR/lessons-learned"
for f in "$SKILL_DIR"/references/lessons-learned-*.md; do
  base=$(basename "$f" | sed 's|^lessons-learned-||')
  git mv "$f" "$SKILL_DIR/lessons-learned/_legacy-$base"
done
```

### Step 3. `.gitkeep` を配置

```bash
touch "$SKILL_DIR/LOGS/.gitkeep"
touch "$SKILL_DIR/changelog/.gitkeep"
touch "$SKILL_DIR/lessons-learned/.gitkeep"
git add "$SKILL_DIR/LOGS/.gitkeep" "$SKILL_DIR/changelog/.gitkeep" "$SKILL_DIR/lessons-learned/.gitkeep"
```

### Step 4. `scripts/log_usage.js` writer を fragment 経路へ差し替え

旧 writer:
```js
// ❌ 旧: LOGS.md に直接 append
fs.appendFileSync(path.join(skillDir, 'LOGS.md'), entry);
```

新 writer:
```js
// ✅ 新: writeLogFragment 経由
const { writeLogFragment } = require('../../../scripts/lib/fragment-path');
writeLogFragment({ skillDir, type: 'log', branch, author, body: entry });
```

または CLI 経由（推奨）:
```bash
pnpm skill:logs:append --skill <your-skill> --type log --notes "<entry summary>"
```

### Step 5. 検証

```bash
# 全 fragment（legacy 含む）を時系列集約
mise exec -- pnpm skill:logs:render --skill <your-skill> --include-legacy

# 新 fragment のみ
mise exec -- pnpm skill:logs:render --skill <your-skill>

# canonical 切替宣言を resource-map / quick-reference に追記したか
grep -n "LOGS/_legacy.md\|changelog/_legacy.md\|lessons-learned/_legacy" \
  "$SKILL_DIR"/indexes/*.md "$SKILL_DIR"/references/*.md 2>/dev/null
```

## 既存スキルからの相互参照（anchor 文例）

他スキルの SKILL.md / references から fragment 化済み skill の ledger を引用する場合:

```markdown
- 詳細履歴: [LOGS/](LOGS/)（旧 `LOGS.md` は `LOGS/_legacy.md` に退避）
- 集約: `pnpm skill:logs:render --skill <name> [--include-legacy]`
- 苦戦箇所: [lessons-learned/](lessons-learned/)（旧 `references/lessons-learned-*.md` は `lessons-learned/_legacy-*.md` に退避）
- legacy-ordinal-family-register: 旧 path → 新 path の逆引きは `references/legacy-ordinal-family-register.md` の Current Alias Overrides を参照
```

## チェックリスト

- [ ] `LOGS.md` / `SKILL-changelog.md` を `_legacy.md` に rename
- [ ] `references/lessons-learned-*.md` を `lessons-learned/_legacy-*.md` に一括 rename
- [ ] `LOGS/`, `changelog/`, `lessons-learned/` に `.gitkeep` 配置
- [ ] `scripts/log_usage.js` writer を fragment 経路に差し替え（または CLI 経由化）
- [ ] `indexes/resource-map.md` / `indexes/quick-reference.md` に canonical 切替宣言を追記
- [ ] `references/legacy-ordinal-family-register.md` の Current Alias Overrides に対応 entry を追加
- [ ] `pnpm skill:logs:render --skill <name> --include-legacy` が legacy + 新 fragment を時系列集約できることを確認
- [ ] 新 fragment 1 件以上（LOGS / changelog / lessons-learned のいずれか）を試験 append し、render に出ることを確認

## 注意事項

- `_legacy*.md` は **物理削除しない**（30 日 include window 終了後も履歴参照のため保持）
- 新規 entry を `_legacy*.md` に直接 append しないこと（writer 経路ガード CI で検出予定）
- nonce 衝突は writer 側で `scripts/lib/retry-on-collision.ts` が自動リトライするため通常気にしなくてよい
- escapedBranch の truncation は `scripts/lib/branch-escape.ts` が一元管理。writer 個別に実装しない

## 参照

- A-2 fragment 化タスク仕様: `docs/30-workflows/task-skill-ledger-a2-fragment/`
- 苦戦箇所まとめ: 各 skill の `lessons-learned/<2026-04-28 fragment>.md`
- 共通 lib: `scripts/lib/{branch-escape,fragment-path,front-matter,retry-on-collision,timestamp}.ts`
- CLI: `scripts/skill-logs-{render,append}.ts`
