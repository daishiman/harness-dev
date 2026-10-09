#!/usr/bin/env python3
# /// script
# name: youtube_provider
# version: 0.1.0
# purpose: YouTube 取得の 取得元 中立アダプタ I/F。list_channel_videos(cursor)/fetch_transcript(video_id)
#          の 2 メソッドと 型付きエラー (QuotaExceeded/AuthRequired/TemporaryFailure/TerminalUnavailable)
#          だけを契約として固定し、実 取得元(YouTube Data API / 字幕取得ツール等)は 実行時に接続 する。
#          テスト用に JSON 検証用データ 駆動の FixtureProvider を同梱し、無人 1回きりの実行 を疎通確認可能にする。
# inputs:
#   - FixtureProvider: JSON 検証用データ (channels/transcripts/errors) を Path で受ける
# outputs:
#   - Page(videos, next_cursor) / Transcript(video_id, origin, coverage, spans)
#   - 取得不能は 型付きエラー を raise (1回きりの実行 が 台帳 状態へ写像する)
# contexts: [E]
# network: false  (検証用データ 取得元 のみ同梱。実 取得元 は 実行時に接続 し network はその実装が持つ)
# write-scope: none
# dependencies: []
# requires-python: ">=3.9"
# ///
"""取得元 中立の YouTube 取得アダプタ契約 + 検証用データ 取得元。

取得契約・自動性・fallback を skill 内で確定し、具体 取得元 製品だけを 実行時に接続 する
(boundary 指示)。caption を第一取得源とし、caption 不在で承認済み ASR にフォールバックする
判断は 取得元 実装が origin=caption|asr として返し、本 I/F はそれを不変で運ぶ。

注: `from __future__ import annotations` は使わない。dataclass 定義があるこのモジュールは
smoke テストが importlib (sys.modules 非登録) でロードするため、文字列アノテーション化すると
dataclasses の InitVar 判定が cls.__module__ 解決で AttributeError になる。
"""
import json
from dataclasses import dataclass, field
from pathlib import Path
from typing import Optional


# --- typed errors (1回きりの実行 が状態へ決定論写像する分類) --------------------
class ProviderError(Exception):
    """取得元 由来エラーの基底。"""


class QuotaExceeded(ProviderError):
    """API 利用量の上限 超過。当該 実行 は打ち切り、次 実行周期 で再開する (再試行可能・実行 単位)。"""


class AuthRequired(ProviderError):
    """認証/認可が必要。無人継続不可のため 実行 を停止し 警告を通知 する (要人間対応)。"""


class TemporaryFailure(ProviderError):
    """一時取得失敗 (ネットワーク断等)。video を temporary_failure に置き次 実行 で 再試行 する。"""


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


# --- 取得元 I/F ---------------------------------------------------------
class YouTubeProvider:
    """取得元 中立契約。実 取得元 はこの 2 メソッドと 型付きエラー 分類だけを満たせばよい。"""

    def list_channel_videos(self, channel: str, cursor: Optional[str] = None) -> Page:  # noqa: D401
        raise NotImplementedError

    def fetch_transcript(self, video_id: str) -> Transcript:
        raise NotImplementedError


class FixtureProvider(YouTubeProvider):
    """JSON 検証用データ 駆動の 取得元。無人 1回きりの実行 をネットワークなしで疎通確認するためのもの。

    検証用データ schema (references/provider-adapter-contract.md が正本):
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
            # 未同定 ソース (第2アカウント pending) は空ページを返し required-primary を止めない。
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
    """取得元 名から実体を返す。検証用データ のみ同梱、実 取得元 は 実行時に接続 (未実装は明示 raise)。"""
    if name == "fixture":
        return FixtureProvider(Path(opts["fixture"]))
    raise NotImplementedError(
        f"provider '{name}' は late-bind 対象です。取得契約 (list_channel_videos/fetch_transcript/"
        "typed error) を満たす実装を注入してください。references/provider-adapter-contract.md 参照。"
    )
