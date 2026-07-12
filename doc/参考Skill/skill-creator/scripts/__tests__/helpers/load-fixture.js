// scripts/__tests__/helpers/load-fixture.js
// テストフィクスチャ (`SKILL.md.fixture`) を一時 `SKILL.md` にコピーするヘルパー。
// Codex CLI の SKILL.md 検証から除外するため、リポジトリ上のフィクスチャは
// `.fixture` 拡張子で配置し、テスト実行時のみ `SKILL.md` を生成する。

import { copyFileSync, unlinkSync, existsSync } from "fs";
import { join, dirname } from "path";
import { fileURLToPath } from "url";

const __dirname = dirname(fileURLToPath(import.meta.url));
const FIXTURES_DIR = join(__dirname, "..", "fixtures");

/**
 * フィクスチャの SKILL.md.fixture を一時 SKILL.md にコピーする。
 * source が存在しないフィクスチャ（empty-skill-md 等）でも cleanup を返す。
 *
 * @param {string} name - fixtures/ 配下のディレクトリ名
 * @returns {{ dir: string, cleanup: () => void }}
 */
export function loadFixture(name) {
  const dir = join(FIXTURES_DIR, name);
  const src = join(dir, "SKILL.md.fixture");
  const dst = join(dir, "SKILL.md");

  if (existsSync(src)) {
    copyFileSync(src, dst);
  }

  return {
    dir,
    cleanup: () => {
      if (existsSync(dst)) unlinkSync(dst);
    },
  };
}
