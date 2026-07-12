#!/usr/bin/env python3
# /// script
# name: youtube_provider
# version: 0.1.0
# purpose: YouTube 取得の provider 中立アダプタ I/F。list_channel_videos(cursor)/fetch_transcript(video_id)
#          の 2 メソッドと typed error (QuotaExceeded/AuthRequired/TemporaryFailure/TerminalUnavailable)
#          だけを契約として固定し、実 provider(YouTube Data API / 字幕取得ツール等)は late-bind する。
#          テスト用に JSON fixture 駆動の FixtureProvider を同梱し、無人 one-shot を疎通確認可能にする。
# inputs:
#   - FixtureProvider: JSON fixture (channels/transcripts/errors) を Path で受ける
# outputs:
#   - Page(videos, next_cursor) / Transcript(video_id, origin, coverage, spans)
#   - 取得不能は typed error を raise (one-shot が ledger 状態へ写像する)
# contexts: [E]
# network: false  (fixture provider のみ同梱。実 provider は late-bind し network はその実装が持つ)
# write-scope: none
# dependencies: []
# requires-python: ">=3.9"
# ///
"""provider 中立の YouTube 取得アダプタ契約 + fixture provider。

取得契約・自動性・fallback を skill 内で確定し、具体 provider 製品だけを late-bind する
(boundary 指示)。caption を第一取得源とし、caption 不在で承認済み ASR にフォールバックする
判断は provider 実装が origin=caption|asr として返し、本 I/F はそれを不変で運ぶ。

注: `from __future__ import annotations` は使わない。dataclass 定義があるこのモジュールは
smoke テストが importlib (sys.modules 非登録) でロードするため、文字列アノテーション化すると
dataclasses の InitVar 判定が cls.__module__ 解決で AttributeError になる。
"""
import json
from dataclasses import dataclass, field
from pathlib import Path
from typing import Optional


# --- typed errors (one-shot が状態へ決定論写像する分類) --------------------
class ProviderError(Exception):
    """provider 由来エラーの基底。"""


class QuotaExceeded(ProviderError):
    """API quota 超過。当該 run は打ち切り、次 cadence で再開する (retryable・run 単位)。"""


class AuthRequired(ProviderError):
    """認証/認可が必要。無人継続不可のため run を停止し alert する (要人間対応)。"""


class TemporaryFailure(ProviderError):
    """一時取得失敗 (ネットワーク断等)。video を temporary_failure に置き次 run で retry する。"""


class TerminalUnavailable(ProviderError):
    """恒久取得不能 (非公開/削除/字幕無効かつ ASR 不許可)。terminal_unavailable に確定する。"""


ERROR_BY_NAME = {
    "QuotaExceeded": QuotaExceeded,
    "AuthRequired": AuthRequired,
    "TemporaryFailure": TemporaryFailure,
    "TerminalUnavailable": TerminalUnavailable,
}


# --- 値オブジェクト -------------------------------------------------------
@dataclass(frozen=True)
class Page:
    """list_channel_videos の 1 ページ。videos は動画メタ dict の並び、next_cursor は続き無し=None。"""

    videos: list = field(default_factory=list)
    next_cursor: Optional[str] = None


@dataclass(frozen=True)
class Transcript:
    """fetch_transcript の返り。origin=caption|asr、spans は {t, text} の並び。"""

    video_id: str
    origin: str
    coverage: float
    spans: list = field(default_factory=list)


# --- provider I/F ---------------------------------------------------------
class YouTubeProvider:
    """provider 中立契約。実 provider はこの 2 メソッドと typed error 分類だけを満たせばよい。"""

    def list_channel_videos(self, channel: str, cursor: Optional[str] = None) -> Page:  # noqa: D401
        raise NotImplementedError

    def fetch_transcript(self, video_id: str) -> Transcript:
        raise NotImplementedError


class FixtureProvider(YouTubeProvider):
    """JSON fixture 駆動の provider。無人 one-shot をネットワークなしで疎通確認するためのもの。

    fixture schema (references/provider-adapter-contract.md が正本):
      {
        "channels": {"<handle>": {"pages": [{"videos": [meta...], "next_cursor": "..."|null}, ...]}},
        "transcripts": {"<video_id>": {"origin": "caption"|"asr", "coverage": 0..1, "spans": [{"t","text"}]}},
        "errors": {"<video_id>": "TemporaryFailure"|"TerminalUnavailable"|...},
        "list_errors": {"<handle>": "QuotaExceeded"|...}   (任意)
      }
    """

    def __init__(self, fixture_path: Path):
        self._data = json.loads(Path(fixture_path).read_text(encoding="utf-8"))

    def list_channel_videos(self, channel: str, cursor: Optional[str] = None) -> Page:
        list_errors = self._data.get("list_errors", {})
        if channel in list_errors:
            raise ERROR_BY_NAME.get(list_errors[channel], ProviderError)(
                f"list_channel_videos({channel}): {list_errors[channel]}"
            )
        chan = self._data.get("channels", {}).get(channel)
        if chan is None:
            # 未同定 source (第2アカウント pending) は空ページを返し required-primary を止めない。
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
            raise ERROR_BY_NAME.get(errors[video_id], ProviderError)(
                f"fetch_transcript({video_id}): {errors[video_id]}"
            )
        t = self._data.get("transcripts", {}).get(video_id)
        if t is None:
            raise TerminalUnavailable(f"fetch_transcript({video_id}): 字幕も ASR も取得不能")
        return Transcript(
            video_id=video_id,
            origin=t.get("origin", "caption"),
            coverage=float(t.get("coverage", 1.0)),
            spans=list(t.get("spans", [])),
        )


def get_provider(name: str, **opts) -> YouTubeProvider:
    """provider 名から実体を返す。fixture のみ同梱、実 provider は late-bind (未実装は明示 raise)。"""
    if name == "fixture":
        return FixtureProvider(Path(opts["fixture"]))
    raise NotImplementedError(
        f"provider '{name}' は late-bind 対象です。取得契約 (list_channel_videos/fetch_transcript/"
        "typed error) を満たす実装を注入してください。references/provider-adapter-contract.md 参照。"
    )
