#!/usr/bin/env node

/**
 * JSONスキーマ検証スクリプト
 *
 * 入力JSONがスキーマに準拠しているかを検証します。
 *
 * 使用例:
 *   node scripts/validate_schema.js --input .tmp/purpose.json --schema schemas/purpose.json
 *
 * 終了コード:
 *   0: 検証成功
 *   1: 一般的なエラー
 *   2: 引数エラー
 *   3: ファイル不在
 *   4: 検証失敗
 */

import { readFileSync, existsSync } from "fs";
import { join } from "path";
import {
  EXIT_CODES,
  getArg,
  hasArg,
  resolvePath,
  getSkillDir,
} from "./utils.js";

const SKILL_DIR = getSkillDir(import.meta.url);

function showHelp() {
  console.log(`
JSONスキーマ検証スクリプト

Usage:
  node validate_schema.js --input <json-path> --schema <schema-path>

Options:
  --input <path>   検証するJSONファイルのパス（必須）
  --schema <path>  スキーマJSONファイルのパス（必須、相対パス可）
  --verbose        詳細な検証結果を表示
  -h, --help       このヘルプを表示

Examples:
  node scripts/validate_schema.js --input .tmp/purpose.json --schema schemas/purpose.json
  node scripts/validate_schema.js --input output.json --schema schemas/trigger.json --verbose
`);
}

function resolveSchemaPath(p) {
  if (p.startsWith("/")) {
    return p;
  }
  // schemas/ で始まる場合はスキルディレクトリからの相対パス
  if (p.startsWith("schemas/")) {
    return join(SKILL_DIR, p);
  }
  return resolvePath(p);
}

function validateType(value, type) {
  if (type === "string") return typeof value === "string";
  if (type === "number") return typeof value === "number";
  if (type === "integer") return Number.isInteger(value);
  if (type === "boolean") return typeof value === "boolean";
  if (type === "array") return Array.isArray(value);
  if (type === "object")
    return typeof value === "object" && value !== null && !Array.isArray(value);
  if (type === "null") return value === null;
  return true;
}

function validateSchema(data, schema, path = "") {
  const errors = [];

  // type検証
  if (schema.type) {
    const types = Array.isArray(schema.type) ? schema.type : [schema.type];
    const isValid = types.some((t) => validateType(data, t));
    if (!isValid) {
      errors.push(
        `${path || "root"}: 型が不正です。期待: ${types.join("|")}, 実際: ${typeof data}`,
      );
      return errors;
    }
  }

  // enum検証
  if (schema.enum && !schema.enum.includes(data)) {
    errors.push(
      `${path || "root"}: 値が許可されていません。許可値: ${schema.enum.join(", ")}`,
    );
  }

  // pattern検証（文字列のみ）
  if (schema.pattern && typeof data === "string") {
    const regex = new RegExp(schema.pattern);
    if (!regex.test(data)) {
      errors.push(
        `${path || "root"}: パターンに一致しません。パターン: ${schema.pattern}`,
      );
    }
  }

  // minLength/maxLength検証（文字列のみ）
  if (typeof data === "string") {
    if (schema.minLength !== undefined && data.length < schema.minLength) {
      errors.push(
        `${path || "root"}: 文字数が最小値未満です。最小: ${schema.minLength}, 実際: ${data.length}`,
      );
    }
    if (schema.maxLength !== undefined && data.length > schema.maxLength) {
      errors.push(
        `${path || "root"}: 文字数が最大値超過です。最大: ${schema.maxLength}, 実際: ${data.length}`,
      );
    }
  }

  // minItems/maxItems検証（配列のみ）
  if (Array.isArray(data)) {
    if (schema.minItems !== undefined && data.length < schema.minItems) {
      errors.push(
        `${path || "root"}: 要素数が最小値未満です。最小: ${schema.minItems}, 実際: ${data.length}`,
      );
    }
    if (schema.maxItems !== undefined && data.length > schema.maxItems) {
      errors.push(
        `${path || "root"}: 要素数が最大値超過です。最大: ${schema.maxItems}, 実際: ${data.length}`,
      );
    }

    // items検証
    if (schema.items) {
      data.forEach((item, index) => {
        errors.push(...validateSchema(item, schema.items, `${path}[${index}]`));
      });
    }
  }

  // object検証
  if (typeof data === "object" && data !== null && !Array.isArray(data)) {
    // required検証
    if (schema.required) {
      for (const reqProp of schema.required) {
        if (!(reqProp in data)) {
          errors.push(
            `${path || "root"}: 必須プロパティが不足しています: ${reqProp}`,
          );
        }
      }
    }

    // properties検証
    if (schema.properties) {
      for (const [propName, propSchema] of Object.entries(schema.properties)) {
        if (propName in data) {
          errors.push(
            ...validateSchema(data[propName], propSchema, `${path}.${propName}`),
          );
        }
      }
    }

    // additionalProperties検証
    if (schema.additionalProperties === false && schema.properties) {
      const allowedProps = new Set(Object.keys(schema.properties));
      for (const propName of Object.keys(data)) {
        if (!allowedProps.has(propName)) {
          errors.push(
            `${path || "root"}: 許可されていないプロパティです: ${propName}`,
          );
        }
      }
    }
  }

  return errors;
}

async function main() {
  const args = process.argv.slice(2);

  if (hasArg(args, "-h", "--help")) {
    showHelp();
    process.exit(EXIT_CODES.SUCCESS);
  }

  const verbose = args.includes("--verbose");
  const inputPath = getArg(args, "--input");
  const schemaPath = getArg(args, "--schema");

  if (!inputPath) {
    console.error("Error: --input は必須です");
    process.exit(EXIT_CODES.ARGS_ERROR);
  }

  if (!schemaPath) {
    console.error("Error: --schema は必須です");
    process.exit(EXIT_CODES.ARGS_ERROR);
  }

  const resolvedInput = resolvePath(inputPath);
  const resolvedSchema = resolveSchemaPath(schemaPath);

  if (!existsSync(resolvedInput)) {
    console.error(`Error: 入力ファイルが存在しません: ${resolvedInput}`);
    process.exit(EXIT_CODES.FILE_NOT_FOUND);
  }

  if (!existsSync(resolvedSchema)) {
    console.error(`Error: スキーマファイルが存在しません: ${resolvedSchema}`);
    process.exit(EXIT_CODES.FILE_NOT_FOUND);
  }

  try {
    const data = JSON.parse(readFileSync(resolvedInput, "utf-8"));
    const schema = JSON.parse(readFileSync(resolvedSchema, "utf-8"));

    const errors = validateSchema(data, schema);

    if (errors.length === 0) {
      console.log(`✓ 検証成功: ${inputPath}`);
      if (verbose) {
        console.log(`  スキーマ: ${schemaPath}`);
        console.log(
          `  データ: ${JSON.stringify(data, null, 2).substring(0, 200)}...`,
        );
      }
      process.exit(EXIT_CODES.SUCCESS);
    } else {
      console.error(`✗ 検証失敗: ${inputPath}`);
      console.error(`  スキーマ: ${schemaPath}`);
      console.error(`  エラー数: ${errors.length}`);
      errors.forEach((err) => console.error(`    - ${err}`));
      process.exit(EXIT_CODES.VALIDATION_FAILED);
    }
  } catch (err) {
    if (err instanceof SyntaxError) {
      console.error(`Error: JSONの解析に失敗しました: ${err.message}`);
    } else {
      console.error(`Error: ${err.message}`);
    }
    process.exit(EXIT_CODES.ERROR);
  }
}

main().catch((err) => {
  console.error(`Error: ${err.message}`);
  process.exit(EXIT_CODES.ERROR);
});
