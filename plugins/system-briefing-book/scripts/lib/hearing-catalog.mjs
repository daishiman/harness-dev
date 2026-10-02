/** Questions, interview rounds and design proposals have one source: hearing-catalog.json. */
import { readFileSync } from "node:fs";

const catalog = JSON.parse(readFileSync(new URL("../../assets/data/hearing-catalog.json", import.meta.url), "utf8"));
function freeze(value) {
  if (value && typeof value === "object") {
    Object.values(value).forEach(freeze);
    Object.freeze(value);
  }
  return value;
}

export const HEARING_SECTIONS = freeze(catalog.sections);
export const HEARING_QUESTIONS = freeze(catalog.questions);

const SECTION_PLACEHOLDERS = ["HEARING_PURPOSE_ROWS", "HEARING_SCREEN_ROWS", "HEARING_PLATFORM_ROWS", "HEARING_OPERATION_ROWS"];
const markdownCell = (value) => value.replace(/\|/g, "\\|").replace(/\r?\n/g, " ");

/** Empty answers stay undecided; a design proposal is never a recorded user answer. */
export function hearingTemplateValues() {
  return Object.fromEntries(HEARING_SECTIONS.map((section, i) => [
    SECTION_PLACEHOLDERS[i],
    HEARING_QUESTIONS.filter((question) => question.section === section.id)
      .map((question) => `| ${question.id} | ${markdownCell(question.question)} |  | 未定 |`).join("\n"),
  ]));
}
