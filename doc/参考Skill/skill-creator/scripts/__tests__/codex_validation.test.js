// scripts/__tests__/codex_validation.test.js
// Codex SKILL.md 検証ルール R-01〜R-06 の RED → GREEN テスト。
// タスク: TASK-SKILL-CODEX-VALIDATION-001 / Phase 4 RED + Phase 6 拡張テスト

import { describe, it, expect } from "vitest";
import { mkdtempSync, readFileSync, existsSync, writeFileSync } from "fs";
import { execFileSync } from "child_process";
import { dirname, join, resolve } from "path";
import { tmpdir } from "os";
import { fileURLToPath } from "url";
import { parse } from "yaml";

import {
  validateSkillMdContent,
  extractDescription,
  MAX_DESC_LENGTH,
  MAX_ANCHORS,
  MAX_TRIGGER_KEYWORDS,
} from "../utils/validate-skill-md.js";
import {
  toDoubleQuotedScalar,
  normalizeWhitespace,
  escapeForScalar,
} from "../utils/yaml-escape.js";

const __dirname = dirname(fileURLToPath(import.meta.url));

function projectRoot() {
  let dir = __dirname;
  for (let i = 0; i < 20; i++) {
    if (existsSync(join(dir, "package.json")) && existsSync(join(dir, "pnpm-workspace.yaml"))) {
      return dir;
    }
    dir = dirname(dir);
  }
  return process.cwd();
}

const ROOT = projectRoot();

// ============================================================================
// R-01〜R-06 単体テスト
// ============================================================================

describe("validateSkillMdContent (R-01〜R-06)", () => {
  it("R-01: frontmatter 欠如 → ok=false", () => {
    const r = validateSkillMdContent("# no frontmatter\nbody");
    expect(r.ok).toBe(false);
    expect(r.errors.some((e) => e.includes("R-01"))).toBe(true);
  });

  it("R-02: description 欠如 → ok=false", () => {
    const r = validateSkillMdContent("---\nname: foo\n---\nbody");
    expect(r.ok).toBe(false);
    expect(r.errors.some((e) => e.includes("R-02"))).toBe(true);
  });

  it("R-03: description が sequence → ok=false", () => {
    const r = validateSkillMdContent(
      "---\nname: foo\ndescription:\n  - item1\n  - item2\n---\n",
    );
    expect(r.ok).toBe(false);
    expect(r.errors.some((e) => e.includes("R-03"))).toBe(true);
  });

  it("R-04: description 1025 字 → ok=false", () => {
    const long = "x".repeat(1025);
    const r = validateSkillMdContent(`---\nname: foo\ndescription: "${long}"\n---\n`);
    expect(r.ok).toBe(false);
    expect(r.errors.some((e) => e.includes("R-04"))).toBe(true);
  });

  it("R-04 boundary: description 1024 字 → ok=true", () => {
    const exact = "x".repeat(MAX_DESC_LENGTH);
    const r = validateSkillMdContent(`---\nname: foo\ndescription: "${exact}"\n---\n`);
    expect(r.ok, JSON.stringify(r.errors)).toBe(true);
  });

  it("R-05: name 欠如 → ok=false", () => {
    const r = validateSkillMdContent("---\ndescription: hello world\n---\n");
    expect(r.ok).toBe(false);
    expect(r.errors.some((e) => e.includes("R-05"))).toBe(true);
  });

  it("R-05: name 空文字 → ok=false", () => {
    const r = validateSkillMdContent('---\nname: ""\ndescription: hello world\n---\n');
    expect(r.ok).toBe(false);
    expect(r.errors.some((e) => e.includes("R-05"))).toBe(true);
  });

  it("R-06: BOM 付き UTF-8 → エラー検出", () => {
    const r = validateSkillMdContent("﻿---\nname: foo\ndescription: bar\n---\n");
    expect(r.errors.some((e) => e.includes("R-06"))).toBe(true);
  });

  it("R-07: frontmatter 全体の YAML 構文エラー → ok=false", () => {
    const r = validateSkillMdContent("---\nname: [\ndescription: bar\n---\n");
    expect(r.ok).toBe(false);
    expect(r.errors.some((e) => e.includes("R-07"))).toBe(true);
  });

  it("plain scalar の description を string として抽出", () => {
    const r = validateSkillMdContent("---\nname: foo\ndescription: hello world\n---\n");
    expect(r.ok).toBe(true);
    expect(r.description).toBe("hello world");
  });

  it("literal block の description を改行込み string として抽出", () => {
    const content = "---\nname: foo\ndescription: |\n  line one.\n  line two.\n---\n";
    const r = validateSkillMdContent(content);
    expect(r.ok).toBe(true);
    expect(r.description).toBe("line one.\nline two.");
  });
});

// ============================================================================
// extractDescription（簡易 YAML パーサ）
// ============================================================================

describe("extractDescription", () => {
  it("missing → kind: missing", () => {
    expect(extractDescription("name: foo").kind).toBe("missing");
  });

  it("sequence (ブロック形式) → kind: sequence", () => {
    expect(extractDescription("description:\n  - a\n  - b").kind).toBe("sequence");
  });

  it("double-quoted の改行を含む文字列を JSON.parse でデコード", () => {
    const r = extractDescription('description: "a\\nb"');
    expect(r.kind).toBe("string");
    expect(r.value).toBe("a\nb");
  });
});

// ============================================================================
// yaml-escape ヘルパー
// ============================================================================

describe("yaml-escape", () => {
  it("normalizeWhitespace: 改行を半角空白に", () => {
    expect(normalizeWhitespace("a\nb\n\nc")).toBe("a b c");
  });

  it("normalizeWhitespace: Tab を半角空白に", () => {
    expect(normalizeWhitespace("a\tb")).toBe("a b");
  });

  it("normalizeWhitespace: 連続空白を 1 個に", () => {
    expect(normalizeWhitespace("a   b")).toBe("a b");
  });

  it("escapeForScalar: ダブルクォート escape", () => {
    expect(escapeForScalar('a"b')).toBe('a\\"b');
  });

  it("escapeForScalar: バックスラッシュ escape", () => {
    expect(escapeForScalar("a\\b")).toBe("a\\\\b");
  });

  it("toDoubleQuotedScalar: 改行含み文字列を 1 行 double-quoted に", () => {
    expect(toDoubleQuotedScalar("a\nb")).toBe('"a b"');
  });

  it("toDoubleQuotedScalar: 危険文字を含む文字列を安全に", () => {
    expect(toDoubleQuotedScalar('a "b" c')).toBe('"a \\"b\\" c"');
  });
});

// ============================================================================
// 既存実 SKILL.md の Codex 検証準拠（Lane A 完了後 PASS）
// ============================================================================

describe("既存実 SKILL.md は R-01〜R-05 PASS", () => {
  for (const name of ["aiworkflow-requirements", "automation-30", "skill-creator"]) {
    it(`${name}/SKILL.md は valid`, () => {
      const file = resolve(ROOT, ".claude/skills", name, "SKILL.md");
      if (!existsSync(file)) return;
      const content = readFileSync(file, "utf-8");
      const r = validateSkillMdContent(content);
      expect(r.ok, `errors: ${r.errors.join("; ")}`).toBe(true);
    });
  }
});

// ============================================================================
// 件数上限定数（C-3 Anchors / Trigger 退避）
// ============================================================================

describe("件数上限定数", () => {
  it(`MAX_DESC_LENGTH = ${MAX_DESC_LENGTH}`, () => expect(MAX_DESC_LENGTH).toBe(1024));
  it(`MAX_ANCHORS = ${MAX_ANCHORS}`, () => expect(MAX_ANCHORS).toBe(5));
  it(`MAX_TRIGGER_KEYWORDS = ${MAX_TRIGGER_KEYWORDS}`, () =>
    expect(MAX_TRIGGER_KEYWORDS).toBe(15));
});

describe("generate_skill_md.js integration", () => {
  it("summary / trigger の改行・コロン・引用符を YAML parse 可能に出力する", () => {
    const dir = mkdtempSync(join(tmpdir(), "skill-md-gen-"));
    const planPath = join(dir, "plan.json");
    const outputPath = join(dir, "generated-skill", "SKILL.md");
    writeFileSync(
      planPath,
      JSON.stringify({
        skillName: "generated-skill",
        workflow: {
          summary: 'line one\nline: two "quoted"',
          trigger: {
            description: 'use when: value\nnext "line"',
            keywords: ["alpha", "beta"],
          },
          anchors: [
            { name: "Anchor One", application: "app: area", purpose: 'purpose "quoted"' },
          ],
        },
      }),
      "utf-8",
    );

    execFileSync(
      "node",
      [resolve(ROOT, ".claude/skills/skill-creator/scripts/generate_skill_md.js"), "--plan", planPath, "--output", outputPath],
      { cwd: ROOT, stdio: "pipe" },
    );

    const content = readFileSync(outputPath, "utf-8");
    const frontmatter = content.match(/^---\n([\s\S]*?)\n---/)[1];
    const parsed = parse(frontmatter);
    expect(parsed.description).toContain('line: two "quoted"');
    expect(validateSkillMdContent(content).ok).toBe(true);
  });
});
