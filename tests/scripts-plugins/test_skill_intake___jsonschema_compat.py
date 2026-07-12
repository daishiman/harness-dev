"""_jsonschema_compat.py の最小 JSON Schema フォールバック検証器を網羅検証する。

対象 script:
  plugins/skill-intake/scripts/_jsonschema_compat.py

方針:
  - 純関数 / クラス (ValidationError / _type_ok / _resolve_ref / _matches /
    _iter_errors / _Validator / _Validators / validators / validate) を実ファイルから
    importlib でロードして直接呼ぶ。これは main を持たない純ライブラリなので subprocess 不要。
  - 各 schema キーワード (type/const/enum/pattern/min|maxLength/format/min|maximum/
    min|maxItems/items/properties/required/additionalProperties/allOf/if-then/$ref) の
    正常系 (エラー無し) と違反系 (期待 message + absolute_path) を実インスタンスで assert。
  - network / keychain / Notion 依存は無い純ローカル検証器なので stub 不要。tmp_path も不要
    (ファイル I/O が無い) で repo を汚染しない。
"""
import importlib.util
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[2]
SCRIPT = ROOT / "plugins" / "skill-intake" / "scripts" / "_jsonschema_compat.py"

_MOD_NAME = "jsonschema_compat_uut"


def _load():
    spec = importlib.util.spec_from_file_location(_MOD_NAME, SCRIPT)
    mod = importlib.util.module_from_spec(spec)
    # `@dataclass` + `from __future__ import annotations` の文字列注釈解決は
    # sys.modules[cls.__module__] を参照するため、exec_module 前に登録が必須。
    sys.modules[_MOD_NAME] = mod
    spec.loader.exec_module(mod)
    return mod


@pytest.fixture()
def MOD():
    return _load()


def _errs(MOD, instance, schema, root=None):
    return list(MOD._iter_errors(instance, schema, root if root is not None else schema, ()))


# ---------------------------------------------------------------------------
# ValidationError
# ---------------------------------------------------------------------------
def test_validation_error_str_and_path(MOD):
    e = MOD.ValidationError("boom", ("a", 0))
    assert str(e) == "boom"
    assert e.message == "boom"
    assert e.absolute_path == ("a", 0)


def test_validation_error_default_path_empty(MOD):
    e = MOD.ValidationError("x")
    assert e.absolute_path == ()


def test_validation_error_is_exception(MOD):
    with pytest.raises(MOD.ValidationError):
        raise MOD.ValidationError("raised")


# ---------------------------------------------------------------------------
# _type_ok — 全分岐
# ---------------------------------------------------------------------------
def test_type_ok_each_type(MOD):
    assert MOD._type_ok({}, "object") is True
    assert MOD._type_ok([], "array") is True
    assert MOD._type_ok("s", "string") is True
    assert MOD._type_ok(True, "boolean") is True
    assert MOD._type_ok(3, "integer") is True
    assert MOD._type_ok(3.5, "number") is True
    assert MOD._type_ok(3, "number") is True
    assert MOD._type_ok(None, "null") is True
    # 未知の type は常に True (寛容)
    assert MOD._type_ok("anything", "custom-type") is True


def test_type_ok_negatives(MOD):
    assert MOD._type_ok([], "object") is False
    assert MOD._type_ok({}, "array") is False
    assert MOD._type_ok(1, "string") is False
    assert MOD._type_ok(1, "boolean") is False
    # bool は integer / number として扱わない
    assert MOD._type_ok(True, "integer") is False
    assert MOD._type_ok(True, "number") is False
    # float は integer ではない
    assert MOD._type_ok(3.5, "integer") is False
    assert MOD._type_ok("x", "null") is False


# ---------------------------------------------------------------------------
# _resolve_ref
# ---------------------------------------------------------------------------
def test_resolve_ref_ok(MOD):
    root = {"$defs": {"foo": {"type": "string"}}}
    assert MOD._resolve_ref(root, "#/$defs/foo") == {"type": "string"}


def test_resolve_ref_escapes_tilde_and_slash(MOD):
    root = {"a/b": {"~x": {"type": "integer"}}}
    # ~1 -> "/", ~0 -> "~"
    assert MOD._resolve_ref(root, "#/a~1b/~0x") == {"type": "integer"}


def test_resolve_ref_unsupported_external(MOD):
    with pytest.raises(MOD.ValidationError) as ei:
        MOD._resolve_ref({}, "http://x/schema.json")
    assert "unsupported $ref" in str(ei.value)


def test_resolve_ref_unresolved_missing_key(MOD):
    with pytest.raises(MOD.ValidationError) as ei:
        MOD._resolve_ref({"$defs": {}}, "#/$defs/missing")
    assert "unresolved $ref" in str(ei.value)


def test_resolve_ref_unresolved_non_dict_mid(MOD):
    # 途中が dict でない
    with pytest.raises(MOD.ValidationError) as ei:
        MOD._resolve_ref({"a": [1, 2]}, "#/a/0")
    assert "unresolved $ref" in str(ei.value)


def test_resolve_ref_points_to_non_schema(MOD):
    with pytest.raises(MOD.ValidationError) as ei:
        MOD._resolve_ref({"a": "scalar"}, "#/a")
    assert "does not point to schema object" in str(ei.value)


# ---------------------------------------------------------------------------
# _matches
# ---------------------------------------------------------------------------
def test_matches_true_false(MOD):
    assert MOD._matches("hi", {"type": "string"}, {}) is True
    assert MOD._matches(5, {"type": "string"}, {}) is False


# ---------------------------------------------------------------------------
# _iter_errors — non-dict schema は何も出さない
# ---------------------------------------------------------------------------
def test_iter_errors_non_dict_schema_yields_nothing(MOD):
    assert _errs(MOD, "x", True) == []
    assert _errs(MOD, "x", None) == []


# ---------------------------------------------------------------------------
# $ref
# ---------------------------------------------------------------------------
def test_iter_errors_ref_resolves_and_validates(MOD):
    root = {"$defs": {"s": {"type": "string"}}, "$ref": "#/$defs/s"}
    assert _errs(MOD, "ok", {"$ref": "#/$defs/s"}, root) == []
    errs = _errs(MOD, 1, {"$ref": "#/$defs/s"}, root)
    assert len(errs) == 1
    assert "is not of type" in errs[0].message


# ---------------------------------------------------------------------------
# allOf
# ---------------------------------------------------------------------------
def test_iter_errors_allof_aggregates(MOD):
    schema = {"allOf": [{"type": "string"}, {"minLength": 3}]}
    assert _errs(MOD, "abcd", schema) == []
    errs = _errs(MOD, "ab", schema)
    assert any("shorter than minLength" in e.message for e in errs)


def test_iter_errors_allof_none_is_safe(MOD):
    # allOf が None でも `or []` で守られる
    assert _errs(MOD, "x", {"allOf": None}) == []


# ---------------------------------------------------------------------------
# if / then
# ---------------------------------------------------------------------------
def test_iter_errors_if_then_applies_then(MOD):
    schema = {
        "if": {"properties": {"kind": {"const": "a"}}},
        "then": {"required": ["extra"]},
    }
    # kind==a で if 一致 -> then 適用 -> extra 必須違反
    errs = _errs(MOD, {"kind": "a"}, schema)
    assert any("'extra' is a required property" in e.message for e in errs)
    # kind!=a なら if 不一致 -> then 不適用 -> エラー無し
    assert _errs(MOD, {"kind": "b"}, schema) == []


def test_iter_errors_if_then_missing_then_default(MOD):
    # then 不在 (.get("then", {})) でも例外にならない
    schema = {"if": {"const": "a"}}
    assert _errs(MOD, "a", schema) == []


# ---------------------------------------------------------------------------
# const / enum
# ---------------------------------------------------------------------------
def test_iter_errors_const(MOD):
    assert _errs(MOD, "v", {"const": "v"}) == []
    errs = _errs(MOD, "w", {"const": "v"})
    assert len(errs) == 1
    assert "is not equal to const" in errs[0].message


def test_iter_errors_enum(MOD):
    assert _errs(MOD, "b", {"enum": ["a", "b"]}) == []
    errs = _errs(MOD, "z", {"enum": ["a", "b"]})
    assert len(errs) == 1
    assert "is not one of" in errs[0].message


# ---------------------------------------------------------------------------
# type — single / list / mismatch stops further checks
# ---------------------------------------------------------------------------
def test_iter_errors_type_single_ok_and_fail(MOD):
    assert _errs(MOD, "x", {"type": "string"}) == []
    errs = _errs(MOD, 1, {"type": "string"})
    assert len(errs) == 1
    assert "is not of type 'string'" in errs[0].message


def test_iter_errors_type_list_union(MOD):
    schema = {"type": ["string", "null"]}
    assert _errs(MOD, "x", schema) == []
    assert _errs(MOD, None, schema) == []
    errs = _errs(MOD, 5, schema)
    assert len(errs) == 1


def test_iter_errors_type_mismatch_short_circuits(MOD):
    # type が合わなければ後続の文字列制約等は評価されない (return)
    schema = {"type": "string", "minLength": 100}
    errs = _errs(MOD, 5, schema)
    assert len(errs) == 1  # type エラー 1 件のみ (minLength は評価されない)


# ---------------------------------------------------------------------------
# string: pattern / minLength / maxLength / format(date-time, uri)
# ---------------------------------------------------------------------------
def test_iter_errors_pattern(MOD):
    assert _errs(MOD, "abc123", {"pattern": r"\d+"}) == []
    errs = _errs(MOD, "abc", {"pattern": r"\d+"})
    assert "does not match pattern" in errs[0].message


def test_iter_errors_minmax_length(MOD):
    assert _errs(MOD, "abc", {"minLength": 2, "maxLength": 5}) == []
    assert "shorter than minLength" in _errs(MOD, "a", {"minLength": 2})[0].message
    assert "longer than maxLength" in _errs(MOD, "abcdef", {"maxLength": 3})[0].message


def test_iter_errors_format_date_time(MOD):
    assert _errs(MOD, "2026-06-24T03:00:00Z", {"format": "date-time"}) == []
    assert _errs(MOD, "2026-06-24T03:00:00+00:00", {"format": "date-time"}) == []
    errs = _errs(MOD, "not-a-date", {"format": "date-time"})
    assert "is not a valid date-time" in errs[0].message


def test_iter_errors_format_uri(MOD):
    assert _errs(MOD, "https://example.com/x", {"format": "uri"}) == []
    # scheme も netloc も無い
    assert "is not a valid uri" in _errs(MOD, "just-text", {"format": "uri"})[0].message
    # scheme はあるが netloc が無い
    assert "is not a valid uri" in _errs(MOD, "mailto:", {"format": "uri"})[0].message


def test_iter_errors_unknown_format_ignored(MOD):
    assert _errs(MOD, "anything", {"format": "email"}) == []


# ---------------------------------------------------------------------------
# number: minimum / maximum (bool 除外)
# ---------------------------------------------------------------------------
def test_iter_errors_minimum_maximum(MOD):
    assert _errs(MOD, 5, {"minimum": 1, "maximum": 10}) == []
    assert "less than minimum" in _errs(MOD, 0, {"minimum": 1})[0].message
    assert "greater than maximum" in _errs(MOD, 11, {"maximum": 10})[0].message
    assert _errs(MOD, 2.5, {"minimum": 2.0, "maximum": 3.0}) == []


def test_iter_errors_bool_not_treated_as_number(MOD):
    # bool は数値制約の対象外 (isinstance ... and not bool)
    assert _errs(MOD, True, {"minimum": 5}) == []


# ---------------------------------------------------------------------------
# array: minItems / maxItems / items
# ---------------------------------------------------------------------------
def test_iter_errors_min_max_items(MOD):
    assert _errs(MOD, [1, 2], {"minItems": 1, "maxItems": 3}) == []
    assert "is too short" in _errs(MOD, [], {"minItems": 1})[0].message
    assert "is too long" in _errs(MOD, [1, 2, 3], {"maxItems": 2})[0].message


def test_iter_errors_items_per_element_with_path(MOD):
    schema = {"items": {"type": "integer"}}
    assert _errs(MOD, [1, 2, 3], schema) == []
    errs = _errs(MOD, [1, "bad", 3], schema)
    assert len(errs) == 1
    assert errs[0].absolute_path == (1,)
    assert "is not of type 'integer'" in errs[0].message


def test_iter_errors_items_non_dict_ignored(MOD):
    # items がスキーマ dict でない (例: list 形式) 場合はスキップ
    assert _errs(MOD, [1, 2], {"items": [{"type": "integer"}]}) == []


# ---------------------------------------------------------------------------
# object: required / properties recursion / additionalProperties
# ---------------------------------------------------------------------------
def test_iter_errors_required_with_path(MOD):
    schema = {"required": ["a", "b"]}
    assert _errs(MOD, {"a": 1, "b": 2}, schema) == []
    errs = _errs(MOD, {"a": 1}, schema)
    assert len(errs) == 1
    assert errs[0].absolute_path == ("b",)
    assert "'b' is a required property" in errs[0].message


def test_iter_errors_required_none_safe(MOD):
    assert _errs(MOD, {}, {"required": None}) == []


def test_iter_errors_properties_recursion_path(MOD):
    schema = {"properties": {"inner": {"type": "string"}}}
    assert _errs(MOD, {"inner": "ok"}, schema) == []
    errs = _errs(MOD, {"inner": 5}, schema)
    assert errs[0].absolute_path == ("inner",)


def test_iter_errors_properties_absent_key_skipped(MOD):
    # properties に定義はあるが instance に無いキーは (required でない限り) スキップ
    schema = {"properties": {"opt": {"type": "string"}}}
    assert _errs(MOD, {}, schema) == []


def test_iter_errors_additional_properties_false(MOD):
    schema = {"properties": {"a": {}}, "additionalProperties": False}
    assert _errs(MOD, {"a": 1}, schema) == []
    errs = _errs(MOD, {"a": 1, "b": 2}, schema)
    assert len(errs) == 1
    assert errs[0].absolute_path == ("b",)
    assert "additional property 'b' is not allowed" in errs[0].message


def test_iter_errors_additional_properties_true_allowed(MOD):
    # additionalProperties が False 以外 (既定) は追加プロパティ許容
    schema = {"properties": {"a": {}}, "additionalProperties": True}
    assert _errs(MOD, {"a": 1, "b": 2}, schema) == []


def test_iter_errors_nested_combo(MOD):
    # 複合スキーマで複数違反が同時に出る
    schema = {
        "type": "object",
        "required": ["name", "tags"],
        "properties": {
            "name": {"type": "string", "minLength": 2},
            "tags": {"type": "array", "items": {"type": "string"}, "minItems": 1},
        },
        "additionalProperties": False,
    }
    instance = {"name": "x", "tags": [], "junk": 1}
    errs = _errs(MOD, instance, schema)
    msgs = [e.message for e in errs]
    assert any("shorter than minLength" in m for m in msgs)
    assert any("is too short" in m for m in msgs)
    assert any("additional property 'junk'" in m for m in msgs)


# ---------------------------------------------------------------------------
# _Validator / _Validators / validators
# ---------------------------------------------------------------------------
def test_validator_iter_errors(MOD):
    v = MOD._Validator({"type": "string"})
    assert list(v.iter_errors("ok")) == []
    errs = list(v.iter_errors(5))
    assert len(errs) == 1


def test_validator_check_schema_ok(MOD):
    # dict なら例外なし (None を返す)
    assert MOD._Validator.check_schema({"type": "string"}) is None


def test_validator_check_schema_rejects_non_dict(MOD):
    with pytest.raises(MOD.ValidationError) as ei:
        MOD._Validator.check_schema(["not", "a", "dict"])
    assert "schema must be an object" in str(ei.value)


def test_validators_validator_for_returns_class(MOD):
    cls = MOD.validators.validator_for({"type": "string"})
    assert cls is MOD._Validator
    # 取得したクラスでインスタンス化し検証できる
    v = cls({"type": "integer"})
    assert list(v.iter_errors(3)) == []


def test_module_level_validators_singleton(MOD):
    assert isinstance(MOD.validators, MOD._Validators)


# ---------------------------------------------------------------------------
# validate — top-level entry
# ---------------------------------------------------------------------------
def test_validate_passes_silently(MOD):
    # 違反が無ければ None を返し例外を投げない
    assert MOD.validate({"a": "x"}, {"properties": {"a": {"type": "string"}}}) is None


def test_validate_raises_first_error(MOD):
    with pytest.raises(MOD.ValidationError) as ei:
        MOD.validate({"a": 1}, {"required": ["a", "b"]})
    # 最初の違反 (b 必須) が送出される
    assert "'b' is a required property" in str(ei.value)


def test_validate_raises_for_type_mismatch(MOD):
    with pytest.raises(MOD.ValidationError) as ei:
        MOD.validate(5, {"type": "string"})
    assert "is not of type 'string'" in str(ei.value)
