#!/usr/bin/env python3
# /// script
# name: youtube_provider
# version: 0.2.0
# purpose: YouTube 取得の、取得元に依存しないアダプタ I/F。list_channel_videos(cursor)/fetch_transcript(video_id)
#          の 2 メソッドと型付きのエラー (QuotaExceeded/AuthRequired/TemporaryFailure/TerminalUnavailable)
#          だけを契約として固定し、実際の取得元 (YouTube Data API・字幕取得ツールなど) は後から差し込む。
#          テスト用に JSON の fixture で動く FixtureProvider を同梱し、無人の1回きりの実行をネットワークなしで確かめられるようにする。
# inputs:
#   - FixtureProvider: JSON の fixture (channels/transcripts/errors/list_errors) のパス
# outputs:
#   - Page(videos, next_cursor) / Transcript(video_id, origin, coverage, spans)
#   - 取得できないときは型付きのエラーを raise する (1回きりの実行が台帳の状態へ写像する)。
#     fixture が無い・壊れている・形が違うときも ProviderError を raise する
# contexts: [E]
# network: false  (同梱は fixture の取得元だけ。実際の取得元は後から差し込み、network はその実装が持つ)
# write-scope: none
# dependencies: []
# requires-python: ">=3.9"
# ///
"""取得元に依存しない YouTube 取得アダプタの契約と、fixture の取得元。

取得契約・自動性・切り替えはスキル内で確定し、具体的な取得元の製品だけを後から差し込む
(境界の指示)。字幕を第一の取得源とし、字幕が無いときに承認済みの ASR へ切り替える判断は
取得元の実装が origin=caption|asr として返し、この I/F はそれをそのまま運ぶ。

注: `from __future__ import annotations` は使わない。dataclass 定義があるこのモジュールは
smoke テストが importlib (sys.modules 非登録) でロードするため、文字列アノテーション化すると
dataclasses の InitVar 判定が cls.__module__ 解決で AttributeError になる。
"""
import json
from dataclasses import dataclass, field
from pathlib import Path
from typing import Optional


# --- 型付きのエラー (1回きりの実行が状態へ決定論で写像する分類) ----------------
class ProviderError(Exception):
    """取得元に由来するエラーの基底。fixture の欠落・破損・形の違いもこの型で出す。"""


class QuotaExceeded(ProviderError):
    """API の利用枠の超過。その実行は打ち切り、次の周期で再開する (再試行できる・実行単位)。"""


class AuthRequired(ProviderError):
    """認証/認可が必要。無人では続けられないので実行を止めて警告する (要人間対応)。"""


class TemporaryFailure(ProviderError):
    """一時的な取得失敗 (ネットワーク断など)。動画を temporary_failure に置き、次の実行で再試行する。"""


class TerminalUnavailable(ProviderError):
    """恒久的な取得不能 (非公開・削除・字幕無効かつ ASR 不許可)。terminal_unavailable に確定する。"""


ERROR_BY_NAME = {
    "QuotaExceeded": QuotaExceeded,
    "AuthRequired": AuthRequired,
    "TemporaryFailure": TemporaryFailure,
    "TerminalUnavailable": TerminalUnavailable,
}


# --- 値オブジェクト -------------------------------------------------------
@dataclass(frozen=True)
class Page:
    """list_channel_videos の 1 ページ。videos は動画メタ dict の並び、next_cursor は続きが無ければ None。"""

    videos: list = field(default_factory=list)
    next_cursor: Optional[str] = None


@dataclass(frozen=True)
class Transcript:
    """fetch_transcript の返り。origin=caption|asr、spans は {t, text} の並び。"""

    video_id: str
    origin: str
    coverage: float
    spans: list = field(default_factory=list)


# --- 取得元の I/F ---------------------------------------------------------
class YouTubeProvider:
    """取得元に依存しない契約。実際の取得元はこの 2 メソッドと型付きのエラーの分類だけを満たせばよい。"""

    def list_channel_videos(self, channel: str, cursor: Optional[str] = None) -> Page:  # noqa: D401
        raise NotImplementedError

    def fetch_transcript(self, video_id: str) -> Transcript:
        raise NotImplementedError


def _require(condition: bool, message: str) -> None:
    if not condition:
        raise ProviderError(f"fixture の形が違う: {message}")


class FixtureProvider(YouTubeProvider):
    """JSON の fixture で動く取得元。無人の1回きりの実行をネットワークなしで確かめるためのもの。

    fixture の schema (references/provider-adapter-contract.md が正本):
      {
        "channels": {"<handle>": {"pages": [{"videos": [meta...], "next_cursor": "..."|null}, ...]}},
        "transcripts": {"<video_id>": {"origin": "caption"|"asr", "coverage": 0..1, "spans": [{"t","text"}]}},
        "errors": {"<video_id>": "TemporaryFailure"|"TerminalUnavailable"|...},
        "list_errors": {"<handle>": "QuotaExceeded"|...}   (任意)
      }
    読み込み時に形を確かめ、読めない・形が違う fixture は ProviderError にする (traceback にしない)。
    """

    def __init__(self, fixture_path: Path):
        try:
            data = json.loads(Path(fixture_path).read_text(encoding="utf-8"))
        except (OSError, ValueError, RecursionError) as exc:
            raise ProviderError(f"fixture を読めない: {fixture_path}: {type(exc).__name__}: {exc}") from exc
        _require(isinstance(data, dict), "トップが object でない")
        for key in ("channels", "transcripts", "errors", "list_errors"):
            _require(isinstance(data.get(key, {}), dict), f"{key} が object でない")
        for handle, chan in data.get("channels", {}).items():
            _require(isinstance(chan, dict) and isinstance(chan.get("pages", []), list),
                     f"channels[{handle!r}].pages が配列でない")
            cursors = []
            for page in chan.get("pages", []):
                _require(isinstance(page, dict) and isinstance(page.get("videos", []), list),
                         f"channels[{handle!r}] のページが object でないか videos が配列でない")
                _require(all(isinstance(v, dict) for v in page.get("videos", [])),
                         f"channels[{handle!r}] の videos の要素が object でない")
                cursor = page.get("next_cursor")
                _require(cursor is None or isinstance(cursor, str), f"channels[{handle!r}] の next_cursor が文字列でない")
                if cursor is not None:
                    cursors.append(cursor)
            # 同じ next_cursor が 2 回あると、続きのページを一意に決められない。
            _require(len(cursors) == len(set(cursors)), f"channels[{handle!r}] の next_cursor が重複している")
        self._data = data

    @staticmethod
    def _raise_named(name: object, context: str) -> None:
        if not isinstance(name, str):
            raise ProviderError(f"{context}: エラー名が文字列でない ({name!r})")
        raise ERROR_BY_NAME.get(name, ProviderError)(f"{context}: {name}")

    def list_channel_videos(self, channel: str, cursor: Optional[str] = None) -> Page:
        list_errors = self._data.get("list_errors", {})
        if channel in list_errors:
            self._raise_named(list_errors[channel], f"list_channel_videos({channel})")
        chan = self._data.get("channels", {}).get(channel)
        if chan is None:
            # 未同定のソース (第2アカウントの pending) は空ページを返し、required-primary を止めない。
            return Page(videos=[], next_cursor=None)
        pages = chan.get("pages", [])
        idx = 0 if cursor is None else self._page_index_after(pages, cursor)
        if idx >= len(pages):
            return Page(videos=[], next_cursor=None)
        page = pages[idx]
        return Page(videos=list(page.get("videos", [])), next_cursor=page.get("next_cursor"))

    @staticmethod
    def _page_index_after(pages: list, cursor: str) -> int:
        for i, page in enumerate(pages):
            if page.get("next_cursor") == cursor:
                return i + 1
        return len(pages)

    def fetch_transcript(self, video_id: str) -> Transcript:
        errors = self._data.get("errors", {})
        if video_id in errors:
            self._raise_named(errors[video_id], f"fetch_transcript({video_id})")
        t = self._data.get("transcripts", {}).get(video_id)
        if t is None:
            raise TerminalUnavailable(f"fetch_transcript({video_id}): 字幕も ASR も取得不能")
        _require(isinstance(t, dict), f"transcripts[{video_id!r}] が object でない")
        _require(isinstance(t.get("spans", []), list), f"transcripts[{video_id!r}].spans が配列でない")
        try:
            coverage = float(t.get("coverage", 1.0))
        except (TypeError, ValueError) as exc:
            raise ProviderError(f"fixture の形が違う: transcripts[{video_id!r}].coverage が数値でない") from exc
        return Transcript(
            video_id=video_id,
            origin=t.get("origin", "caption"),
            coverage=coverage,
            spans=list(t.get("spans", [])),
        )


def get_provider(name: str, **opts) -> YouTubeProvider:
    """取得元の名前から実体を返す。同梱は fixture だけで、実際の取得元は後から差し込む (未実装は明示 raise)。

    fixture のパスが無いときは ProviderError を raise する。
    """
    if name == "fixture":
        fixture = opts.get("fixture")
        if not fixture:
            raise ProviderError("fixture の取得元には fixture のパス (fixture=...) が要る")
        return FixtureProvider(Path(fixture))
    raise NotImplementedError(
        f"provider '{name}' は後から差し込む対象です。取得契約 (list_channel_videos/fetch_transcript/"
        "型付きのエラー) を満たす実装を注入してください。references/provider-adapter-contract.md 参照。"
    )
