"""youtube_provider.py の FixtureProvider と get_provider の契約。

壊れた・形の違う fixture は読み込みの時点で ProviderError にする。KeyError・TypeError・
AttributeError を呼び出し側へ漏らすと、1回きりの実行が traceback で終わり lease が残る。
fixture は tmp_path 内で自作し、ネットワークには出ない。
"""
from __future__ import annotations

import json
from importlib.util import module_from_spec, spec_from_file_location
from pathlib import Path

import pytest

PLUGIN_ROOT = Path(__file__).resolve().parents[1]
PROVIDER = PLUGIN_ROOT / "skills/run-ubm-youtube-ingest/scripts/youtube_provider.py"


@pytest.fixture(scope="module")
def yp():
    spec = spec_from_file_location("youtube_provider_under_test", PROVIDER)
    module = module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def write(tmp_path: Path, data) -> Path:
    path = tmp_path / "fx.json"
    path.write_text(data if isinstance(data, str) else json.dumps(data), encoding="utf-8")
    return path


def test_valid_fixture_pages_and_transcript(yp, tmp_path):
    fx = write(tmp_path, {
        "channels": {"@c": {"pages": [
            {"videos": [{"video_id": "v1"}], "next_cursor": "p2"},
            {"videos": [{"video_id": "v2"}], "next_cursor": None},
        ]}},
        "transcripts": {"v1": {"origin": "asr", "coverage": 0.5, "spans": [{"t": "00:00:01", "text": "x"}]}},
    })
    provider = yp.get_provider("fixture", fixture=str(fx))
    first = provider.list_channel_videos("@c")
    assert [v["video_id"] for v in first.videos] == ["v1"] and first.next_cursor == "p2"
    second = provider.list_channel_videos("@c", first.next_cursor)
    assert [v["video_id"] for v in second.videos] == ["v2"] and second.next_cursor is None
    tr = provider.fetch_transcript("v1")
    assert (tr.origin, tr.coverage, len(tr.spans)) == ("asr", 0.5, 1)
    with pytest.raises(yp.TerminalUnavailable):
        provider.fetch_transcript("missing")


@pytest.mark.parametrize("opts", [{}, {"fixture": None}, {"fixture": ""}])
def test_fixture_provider_without_path_raises_provider_error(yp, opts):
    with pytest.raises(yp.ProviderError):
        yp.get_provider("fixture", **opts)


def test_unknown_provider_is_not_implemented(yp):
    with pytest.raises(NotImplementedError):
        yp.get_provider("youtube-data-api")


@pytest.mark.parametrize("content", [
    "{broken",
    "[]",
    {"channels": []},
    {"transcripts": []},
    {"channels": {"@c": {"pages": {}}}},
    {"channels": {"@c": {"pages": ["page"]}}},
    {"channels": {"@c": {"pages": [{"videos": ["v1"]}]}}},
    {"channels": {"@c": {"pages": [{"videos": [], "next_cursor": 2}]}}},
    # 同じ next_cursor が 2 回あると続きのページを決められず、ページ送りが止まらない。
    {"channels": {"@c": {"pages": [
        {"videos": [], "next_cursor": "p"}, {"videos": [], "next_cursor": "p"},
    ]}}},
])
def test_malformed_fixture_raises_provider_error(yp, tmp_path, content):
    with pytest.raises(yp.ProviderError):
        yp.FixtureProvider(write(tmp_path, content))


def test_missing_or_non_utf8_fixture_raises_provider_error(yp, tmp_path):
    with pytest.raises(yp.ProviderError):
        yp.FixtureProvider(tmp_path / "missing.json")
    bad = tmp_path / "bad.json"
    bad.write_bytes(b"\xff\xfe")
    with pytest.raises(yp.ProviderError):
        yp.FixtureProvider(bad)


@pytest.mark.parametrize("transcript", [
    "caption text",
    {"spans": "not a list"},
    {"coverage": "full"},
])
def test_malformed_transcript_raises_provider_error(yp, tmp_path, transcript):
    provider = yp.FixtureProvider(write(tmp_path, {"transcripts": {"v1": transcript}}))
    with pytest.raises(yp.ProviderError):
        provider.fetch_transcript("v1")


@pytest.mark.parametrize("name, expected", [
    ("QuotaExceeded", "QuotaExceeded"),
    ("AuthRequired", "AuthRequired"),
    ("TemporaryFailure", "TemporaryFailure"),
    ("TerminalUnavailable", "TerminalUnavailable"),
    ("SomethingNew", "ProviderError"),
    (["QuotaExceeded"], "ProviderError"),
])
def test_named_errors_map_to_typed_provider_errors(yp, tmp_path, name, expected):
    provider = yp.FixtureProvider(write(tmp_path, {
        "errors": {"v1": name}, "list_errors": {"@c": name},
    }))
    for call in (lambda: provider.fetch_transcript("v1"), lambda: provider.list_channel_videos("@c")):
        with pytest.raises(yp.ProviderError) as info:
            call()
        assert type(info.value).__name__ == expected


def test_text_has_no_mistranslated_fixture_word():
    text = PROVIDER.read_text(encoding="utf-8")
    assert "検証用データ" not in text
