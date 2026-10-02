"""schemas/briefing.schema.json: 正本のスキーマとスクリプトの決まりがずれていないか。"""
from __future__ import annotations

import copy
import json

import pytest

from conftest import PAGES, PLUGIN_ROOT, node_eval, run_script

SCHEMA = json.loads((PLUGIN_ROOT / "schemas" / "briefing.schema.json").read_text(encoding="utf-8"))
VALID = {
    "schema": "briefing-v1", "title": "写真で記録",
    "readers": ["現場の担当者", "発注側の責任者", "開発する人"],
    "palette": "standard", "materials": "..", "data_policy": "masked", "book": {"include_hearing": False},
    "pages": PAGES,
}


def validator_class():
    """jsonschema が無ければ、それを使うテストだけ飛ばす。"""
    return pytest.importorskip("jsonschema").Draft202012Validator


def errors_of(data: dict) -> list[str]:
    return [e.message for e in validator_class()(SCHEMA).iter_errors(data)]


def test_schema_itself_is_valid() -> None:
    validator_class().check_schema(SCHEMA)


def test_valid_examples_pass() -> None:
    assert errors_of(VALID) == []
    fresh = dict(VALID, pages=[])
    fresh.pop("book")
    assert errors_of(fresh) == [], "init 直後 (pages が空、book なし) も通る"
    assert errors_of(dict(VALID, palette="../配色/tokens-company.css")) == []


@pytest.mark.parametrize("change", [
    lambda d: d["pages"][1].update(screens=[]),                 # phone は画面が 1 つ以上
    lambda d: d["pages"][2].update(screens=[]),                 # pc も同じ
    lambda d: d["pages"][0].update(file="00_Overview.html"),    # slug は英小文字
    lambda d: d["pages"][0].update(no="0"),                     # no は 2 桁
    lambda d: d["pages"][0].update(type="summary"),             # 型は PAGE_TYPES のどれか
    lambda d: d["pages"][0].update(message=" "),                # 空の 1 文
    lambda d: d["pages"][1].update(screens=["画面1"]),           # 画面番号は S01 の形
    lambda d: d["pages"][0].update(extra=1),                    # 知らない項目
    lambda d: d.update(schema="briefing-v2"),
    lambda d: d.update(palette="blue"),
    lambda d: d.update(readers=[]),
    lambda d: d["book"].update(include_hearing="yes"),
    lambda d: d.pop("data_policy"),                             # data_policy は必ず書く
    lambda d: d.update(data_policy="public"),                   # source か masked
])
def test_invalid_examples_fail(change) -> None:
    data = copy.deepcopy(VALID)
    change(data)
    assert errors_of(data), data


def test_schema_matches_script_rules() -> None:
    page = SCHEMA["$defs"]["page"]["properties"]
    rules = node_eval(
        'import * as files from "./lib/briefing-files.mjs";\n'
        'import * as validate from "./validate-briefing-docs.mjs";\n'
        "console.log(JSON.stringify([files, validate].map((m) => ({\n"
        "  types: m.PAGE_TYPES, file: m.FILE_RE.source, screen: m.SCREEN_ID.source, devices: m.DEVICE_TYPES,\n"
        "  policies: m.DATA_POLICIES,\n"
        "}))));"
    )
    then = SCHEMA["$defs"]["page"]["if"]["properties"]["type"]["enum"]
    for name, rule in zip(("lib/briefing-files", "validate-briefing-docs"), rules):
        assert rule["types"] == page["type"]["enum"], name
        assert rule["file"].replace(r"(\d{2})", r"\d{2}") == page["file"]["pattern"], name
        assert rule["screen"] == page["screens"]["items"]["pattern"], name
        assert set(rule["devices"]) == set(then), name
        assert rule["policies"] == SCHEMA["properties"]["data_policy"]["enum"], name
    keys = node_eval(
        'import { BOOK_KEYS, BRIEFING_KEYS, PAGE_KEYS } from "./validate-briefing-docs.mjs";\n'
        "console.log(JSON.stringify([BRIEFING_KEYS, BOOK_KEYS, PAGE_KEYS]));"
    )
    assert keys == [list(SCHEMA["properties"]), list(SCHEMA["properties"]["book"]["properties"]), list(page)]


def test_book_labels_cover_every_type() -> None:
    labels = node_eval(
        'import { TYPE_LABEL } from "./lib/briefing-files.mjs";\n'
        "console.log(JSON.stringify(Object.keys(TYPE_LABEL)));"
    )
    assert labels == SCHEMA["$defs"]["page"]["properties"]["type"]["enum"]


def test_scaffold_output_matches_schema(tmp_path) -> None:
    (tmp_path / "素材").mkdir()
    rc, out, err = run_script("build-briefing-scaffold", "init", "--materials", str(tmp_path / "素材"),
                              "--title", "写真で記録", "--date", "2026-10-01")
    assert rc == 0, err
    data = json.loads((tmp_path / "素材" / "打ち合わせ資料" / "briefing.json").read_text(encoding="utf-8"))
    assert errors_of(data) == []
