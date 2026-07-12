#!/usr/bin/env node
/**
 * Task script template.
 *
 * Purpose: implement the minimum deterministic steps required to execute a task.
 * Replace TODOs with task-specific logic and arguments.
 *
 * Exit codes:
 *   0: success
 *   1: general error
 *   2: argument error
 *   3: file not found
 *   4: validation failed
 */

import { existsSync } from "fs";
import { resolve } from "path";

const EXIT_SUCCESS = 0;
const EXIT_ERROR = 1;
const EXIT_ARGS_ERROR = 2;
const EXIT_FILE_NOT_FOUND = 3;
const EXIT_VALIDATION_FAILED = 4;

function showHelp() {
  console.log(`
Task script template

Usage:
  node task_script.js --input <path> [options]

Options:
  --input <path>   Input file or directory (required)
  --output <path>  Output file or directory (optional)
  -h, --help       Show this help
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

function resolvePath(p) {
  return resolve(process.cwd(), p);
}

async function main() {
  const args = process.argv.slice(2);

  if (args.includes("-h") || args.includes("--help")) {
    showHelp();
    process.exit(EXIT_SUCCESS);
  }

  const input = getArg(args, "--input");
  const output = getArg(args, "--output");

  requireArg(input, "--input");

  const inputPath = resolvePath(input);
  if (!existsSync(inputPath)) {
    console.error(`Error: input not found: ${inputPath}`);
    process.exit(EXIT_FILE_NOT_FOUND);
  }

  try {
    // TODO: implement task logic
    // Example flow:
    // 1) load input
    // 2) transform/process
    // 3) write output (if needed)

    if (output) {
      const outputPath = resolvePath(output);
      // TODO: write output to outputPath
    }

    console.log("✓ Task completed");
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
