#!/usr/bin/env node
/**
 * Validator script template.
 *
 * Purpose: enforce constraints (length, schema, structure, quality) deterministically.
 * Replace TODOs with task-specific checks.
 *
 * Exit codes:
 *   0: success
 *   1: general error
 *   2: argument error
 *   3: file not found
 *   4: validation failed
 */

import { readFileSync, existsSync } from "fs";
import { resolve } from "path";

const EXIT_SUCCESS = 0;
const EXIT_ERROR = 1;
const EXIT_ARGS_ERROR = 2;
const EXIT_FILE_NOT_FOUND = 3;
const EXIT_VALIDATION_FAILED = 4;

function showHelp() {
  console.log(`
Validator script template

Usage:
  node validate.js --file <path> [options]

Options:
  --file <path>       Target file to validate (required)
  --max-chars <n>     Max characters allowed (optional)
  --min-chars <n>     Min characters required (optional)
  -h, --help          Show this help
`);
}

function getArg(args, name) {
  const index = args.indexOf(name);
  return index !== -1 && args[index + 1] ? args[index + 1] : null;
}

function requireArg(value, name) {
  if (!value) {
    console.error(`Error: ${name} is required`);
    process.exit(EXIT_ARGS_ERROR);
  }
}

function parseIntArg(value, name) {
  if (value == null) {
    return null;
  }
  const parsed = Number.parseInt(value, 10);
  if (Number.isNaN(parsed) || parsed < 0) {
    console.error(`Error: ${name} must be a non-negative integer`);
    process.exit(EXIT_ARGS_ERROR);
  }
  return parsed;
}

async function main() {
  const args = process.argv.slice(2);

  if (args.includes("-h") || args.includes("--help")) {
    showHelp();
    process.exit(EXIT_SUCCESS);
  }

  const fileArg = getArg(args, "--file");
  requireArg(fileArg, "--file");

  const maxChars = parseIntArg(getArg(args, "--max-chars"), "--max-chars");
  const minChars = parseIntArg(getArg(args, "--min-chars"), "--min-chars");

  if (maxChars == null && minChars == null) {
    console.error("Error: provide at least one constraint (--max-chars or --min-chars)");
    process.exit(EXIT_ARGS_ERROR);
  }

  const filePath = resolve(process.cwd(), fileArg);
  if (!existsSync(filePath)) {
    console.error(`Error: file not found: ${filePath}`);
    process.exit(EXIT_FILE_NOT_FOUND);
  }

  try {
    const content = readFileSync(filePath, "utf-8");
    const length = content.length;

    if (maxChars != null && length > maxChars) {
      console.error(`Validation failed: length ${length} exceeds max ${maxChars}`);
      process.exit(EXIT_VALIDATION_FAILED);
    }

    if (minChars != null && length < minChars) {
      console.error(`Validation failed: length ${length} is below min ${minChars}`);
      process.exit(EXIT_VALIDATION_FAILED);
    }

    // TODO: add task-specific checks (schema validation, structure checks, etc.)

    console.log(`✓ Validation passed (length: ${length})`);
    process.exit(EXIT_SUCCESS);
  } catch (err) {
    console.error(`Error: ${err.message}`);
    process.exit(EXIT_ERROR);
  }
}

main().catch((err) => {
  console.error(`Error: ${err.message}`);
  process.exit(EXIT_ERROR);
});
