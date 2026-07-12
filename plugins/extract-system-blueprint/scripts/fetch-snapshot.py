#!/usr/bin/env python3
# /// script
# name: fetch-snapshot
# purpose: C12(authz-classify)がallowしたAuthzEvidenceとrequest budgetを必須入力に、対象URLの静的/SSR
#          HTTP応答・header・同一origin resource参照を取得して再利用可能なsnapshotへ保存する決定論
#          ユーティリティ。瞬間負荷レバー(origin並列1・最小間隔2000ms・Retry-After尊重・有界backoff)を
#          honorし、budget消費をledgerへ記録(再試行で非リセット)する。redirectはsame-originのみ追従し
#          (load_policy.same_origin_redirects_only)、cross-origin redirect(wwwサブドメイン含む)は追従を
#          拒否してobservation_gapとして記録する(fail-closed・本文非保存)。加えてサイト全域被覆のURL
#          discovery(sitemap/robots Sitemap指令/取得HTMLのsame-originリンクグラフ→discovered_urls fact
#          台帳)と、response header由来のsecurity観測fact(Set-Cookie属性Secure/HttpOnly/SameSite・CSP
#          全文・HSTS等)採取を行う。cache再利用+multi-run resume(coverage manifest連携)に対応し、
#          429/403/robots-deny/予算超過/unstable-responseで停止する。加えて取得済みHTML/CSSをstdlib
#          (html.parser)で静的解析しstatic-observation fact(DOM構造/見出し/nav・link/form/meta/宣言色font)を
#          採取、レンダリング必須の観測(実スクショ/CWV/JS実行後DOM/computed幾何)はobservation_gap(blocked)
#          として記録しC03へ引き渡す。判定ロジックはC12を同一モジュールとしてimportして共有し重複実装しない。
# inputs:
#   - argv: --url URL --out-dir DIR --authz-evidence FILE --request-budget FILE
#           [--discover-urls] [--discovered-urls-out FILE] [--coverage-manifest-in FILE]
#           [--coverage-manifest-out FILE] [--max-assets N] [--no-assets]
#           [--fixture-map FILE] [--self-test]
# outputs:
#   - stdout: JSON {url, authorized, snapshot paths, request_ledger path, discovered_urls path,
#             observation_gap_count, stopped}
#   - stderr: deny|unknown / 予算超過 / 429|403 / fetch失敗 等の violation
#   - exit: 0=OK(primary取得成功) / 1=認可外URL・primary fetch失敗 / 2=usage
# contexts: [C, E]
# network: true
# write-scope: --out-dir 配下および --discovered-urls-out/--coverage-manifest-out で指定した PLAN 成果物
#              ファイルのみ (対象 origin へは GET のみ・書込まない)
# dependencies: []
# requires-python: ">=3.10"
# ///
"""fetch-snapshot — extract-system-blueprint の認可済み低負荷取得 + URL discovery ユーティリティ。

このスクリプトは C12 (authz-classify.py) が発行した AuthzEvidence と request-budget を必須入力に取り、
対象 URL を『瞬間負荷レバーを緩めない』形で取得して再利用可能な snapshot へ保存する。責務は 4 つ:

1. 認可の消費 (fail-closed)。
   AuthzEvidence を C12 の ``decide()`` で再評価し allow 以外 (deny/unknown/期限切れ) は取得を一切
   始めずに exit 1 で止める。evidence.origin / budget.origin / URL の origin が一致しない、budget が
   granted=false な場合も認可外として止める。判定ロジックは C12 と同一モジュールを import して共有し
   (P08-x-02)、hook (C08) と同じく allow/deny 規則を作り直さない。

2. 低負荷取得 (瞬間負荷レバー不変)。
   origin 並列 1・最小間隔 2000ms・Retry-After 尊重・有界指数 backoff・max_retries=1 を honor し、
   request/byte/page の消費を budget から減算しながら ledger へ累積記録する
   (``budget_reset_on_retry: false``: 再試行は budget を満額へ戻さない)。予算枯渇・403・429・
   unstable-response で停止する。redirect は same-origin (scheme+host+port 厳密一致・www サブドメインも
   別 origin) のみ追従する (``same_origin_redirects_only``)。cross-origin redirect は追従を拒否し、
   当該 URL を observation_gap (reason=``cross-origin-redirect-blocked``・redirect 先 origin 記録) として
   snapshot record へ残す — AuthzEvidence の無い別 origin の応答本文は保存しない (fail-closed)。

3. snapshot + provenance と static 観測 fact (security + DOM/CSS)。
   HTML/HTTP header/同一 origin static asset を取得し、URL・取得時刻・sha256・http_status・header を
   provenance として固定する。header 由来の security fact (Set-Cookie の Secure/HttpOnly/SameSite・
   CSP 全文・HSTS・X-Frame-Options 等) と、取得済み HTML/CSS を stdlib (html.parser) で静的解析した
   static-observation fact (DOM 構造/見出し/nav・link/form/meta・OGP・JSON-LD/宣言色・font/a11y) を
   採取する。これらは応答から直接観測した fact であり推測を足さない。実スクリーンショット・CWV・
   JS 実行後 DOM・computed 幾何はレンダリングが必須で捏造できないため observation_gap (blocked) とする。

4. サイト全域被覆の URL discovery と multi-run resume。
   robots の Sitemap 指令・sitemap.xml の <loc>・取得 HTML の same-origin リンクグラフから連なる URL を
   discovered_urls fact 台帳へ書き出す (C12 の scope 分類入力になる)。coverage manifest を介した cache
   再利用 (fresh な snapshot は再取得せず budget を消費しない) と、cumulative request ledger の持ち越しで
   複数 run に分けて全 URL へ到達する。

ネットワークは対象 origin への GET のみ。``--fixture-map`` に URL→応答の写像を与えれば network 無しで
決定論的に走る (CI/オフライン fixture・``--self-test`` 用)。実サイトへのアクセスは C08 hook が
AuthzEvidence と残予算で機械的に gate する。
"""
from __future__ import annotations

import argparse
import hashlib
import html.parser
import importlib.util
import json
import re
import sys
import time
from datetime import datetime, timezone
from email.utils import parsedate_to_datetime
from pathlib import Path
from urllib.parse import urljoin, urlsplit

import urllib.error
import urllib.request

SCHEMA_VERSION = "1.0.0"
USER_AGENT = "extract-system-blueprint-fetch/1.0"
FETCH_TIMEOUT_SECONDS = 15

# component-inventory C09.load_policy の焼き込みミラー (正本 = C12 発行 budget file の
# instant_load_levers)。budget に levers が無い旧 fixture 向けの fallback。
DEFAULT_MAX_RESPONSE_BYTES = 5_242_880       # 5 MiB
DEFAULT_MIN_INTERVAL_MS = 2000
DEFAULT_MAX_RETRIES = 1
DEFAULT_CACHE_TTL_SECONDS = 86400
DEFAULT_BACKOFF = {"initial_ms": 2000, "max_ms": 30000, "multiplier": 2.0}
DEFAULT_MAX_ASSETS = 8
MAX_SITEMAPS_PER_RUN = 3
SITEMAP_LOC_RE = re.compile(r"<loc>\s*([^<\s][^<]*?)\s*</loc>", re.IGNORECASE)

# budget.remaining の resource キー (crawl_mode 別)。need→キーの写像 (C12 build_budget と一致)。
_REMAINING_KEYS = {
    "single": {"requests": "requests", "bytes": "bytes", "pages": "pages"},
    "full_site": {"requests": "requests_per_run", "bytes": "bytes_per_run", "pages": "pages_per_run"},
}
# coverage manifest の request_ledger に累積で書くキー (C12 _ledger_for_origin が読む)。
_LEDGER_KEY = {"requests": "requests", "bytes": "bytes", "pages": "pages"}


# ---------------------------------------------------------------------------
# C12 (authz-classify.py) を共有モジュールとして import。ハイフン名なので
# spec_from_file_location で読み込む (C08 hook と同方式)。読込不能なら認可判定を
# fail-closed で deny する (evaluation logic を再実装しない)。
# ---------------------------------------------------------------------------
_SCRIPT_DIR = Path(__file__).resolve().parent
_AUTHZ_PATH = _SCRIPT_DIR / "authz-classify.py"


def _load_authz_module():
    try:
        spec = importlib.util.spec_from_file_location("esb_authz_classify", _AUTHZ_PATH)
        if spec is None or spec.loader is None:
            return None
        module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(module)
        for attr in ("decide", "_origin_of", "_host_of"):
            if not hasattr(module, attr):
                return None
        return module
    except Exception:  # noqa: BLE001 — import 失敗は理由不問で共有不能とみなす
        return None


_AUTHZ = _load_authz_module()


class UsageError(Exception):
    """argv/入力ファイル不正など、exit 2 (usage) に対応する回復不能な入力エラー。"""


class AuthzDenied(Exception):
    """認可外 (deny/unknown/期限切れ/origin不一致/granted=false)。exit 1。"""


class StopFetching(Exception):
    """crawl 停止条件 (429/403/robots-deny/budget-exhausted/unstable-response)。

    reason は component-inventory C09.load_policy.stop_on と対応する安定した文字列。
    """

    def __init__(self, reason: str, detail: str = "") -> None:
        super().__init__(f"{reason}: {detail}" if detail else reason)
        self.reason = reason
        self.detail = detail


class _TransientError(Exception):
    """接続不能/タイムアウト等の一時的失敗。max_retries まで backoff 再試行する。"""


class CrossOriginRedirect(Exception):
    """same_origin_redirects_only 違反 (redirect 先が別 origin)。追従せず fail-closed。

    C09 load_policy の ``same_origin_redirects_only: true`` を施行する。origin は
    scheme+host+port の厳密一致で判定し、www サブドメインも別 origin とする。該当 URL は
    observation_gap (reason=``cross-origin-redirect-blocked``) として記録し本文は保存しない。
    """

    def __init__(self, url: str, redirect_target: str, target_origin: str | None, status: int) -> None:
        super().__init__(f"cross-origin redirect blocked: {url} -> {redirect_target}")
        self.url = url
        self.redirect_target = redirect_target
        self.target_origin = target_origin
        self.status = status


# ---------------------------------------------------------------------------
# 小さなユーティリティ
# ---------------------------------------------------------------------------
def _now() -> datetime:
    return datetime.now(timezone.utc)


def _iso(dt: datetime) -> str:
    return dt.astimezone(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def _parse_iso(value: str) -> datetime | None:
    if not value:
        return None
    try:
        text = value.strip()
        if text.endswith("Z"):
            text = text[:-1] + "+00:00"
        dt = datetime.fromisoformat(text)
        return dt if dt.tzinfo else dt.replace(tzinfo=timezone.utc)
    except (ValueError, TypeError):
        return None


def _safe_int(value, default: int = 0) -> int:
    try:
        v = int(value)
    except (TypeError, ValueError):
        return default
    return v


def _load_json_file(path_str: str, label: str) -> dict | list:
    path = Path(path_str)
    if not path.is_file():
        raise UsageError(f"{label} not found: {path_str}")
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise UsageError(f"{label} is not valid JSON: {exc}")


def _write_json(path: Path, obj: dict) -> str:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(obj, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    return path.as_posix()


def _origin_of(url: str) -> str | None:
    if _AUTHZ is not None:
        return _AUTHZ._origin_of(url)
    try:
        parts = urlsplit(url)
    except ValueError:
        return None
    if parts.scheme not in ("http", "https") or not parts.hostname:
        return None
    host = parts.hostname.lower()
    return f"{parts.scheme}://{host}:{parts.port}" if parts.port else f"{parts.scheme}://{host}"


def _url_key(url: str) -> str:
    """URL を衝突しにくい短い安全名 (snapshot ファイル名) へ写す。"""
    return hashlib.sha1(url.encode("utf-8")).hexdigest()[:16]


# ---------------------------------------------------------------------------
# HTML リンク/asset 抽出・sitemap/robots 解析
# ---------------------------------------------------------------------------
class _LinkExtractor(html.parser.HTMLParser):
    """取得 HTML から遷移リンクと static asset 参照を採取する (fact 素材)。"""

    def __init__(self) -> None:
        super().__init__(convert_charrefs=True)
        self.links: list[tuple[str, str]] = []   # (href, kind)
        self.assets: list[tuple[str, str]] = []   # (src, kind)

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        d = {k: (v or "") for k, v in attrs}
        if tag == "a" and d.get("href"):
            self.links.append((d["href"], "a"))
        elif tag == "iframe" and d.get("src"):
            self.links.append((d["src"], "iframe"))
        elif tag == "form" and d.get("action"):
            self.links.append((d["action"], "form"))
        elif tag == "link" and d.get("href"):
            rel = d.get("rel", "").lower()
            if "stylesheet" in rel:
                self.assets.append((d["href"], "stylesheet"))
            else:
                self.links.append((d["href"], "link"))
        elif tag == "script" and d.get("src"):
            self.assets.append((d["src"], "script"))
        elif tag == "img":
            src = d.get("src") or d.get("data-src")
            if src:
                self.assets.append((src, "img"))
        elif tag == "source":
            if d.get("src"):
                self.assets.append((d["src"], "source"))
            elif d.get("srcset"):
                first = d["srcset"].split(",")[0].strip().split(" ")[0]
                if first:
                    self.assets.append((first, "source"))


def _parse_html(base_url: str, body: bytes) -> tuple[list[str], list[tuple[str, str]]]:
    """(same+external 絶対リンク一覧, [(絶対 asset URL, kind), ...]) を返す。壊れた HTML は許容。"""
    parser = _LinkExtractor()
    try:
        parser.feed(body.decode("utf-8", "replace"))
    except (ValueError, AssertionError):
        pass  # html.parser が壊れた markup で投げても採取済み分を使う
    links: list[str] = []
    for href, _kind in parser.links:
        absu = _absolutize(base_url, href)
        if absu:
            links.append(absu)
    assets: list[tuple[str, str]] = []
    for src, kind in parser.assets:
        absu = _absolutize(base_url, src)
        if absu:
            assets.append((absu, kind))
    return links, assets


def _absolutize(base_url: str, ref: str) -> str | None:
    ref = (ref or "").strip()
    if not ref or ref.startswith(("#", "mailto:", "tel:", "javascript:", "data:")):
        return None
    try:
        absu = urljoin(base_url, ref)
    except ValueError:
        return None
    return absu if absu.startswith(("http://", "https://")) else None


def _parse_sitemap(body: bytes) -> list[str]:
    text = body.decode("utf-8", "replace")
    return [m.group(1).strip() for m in SITEMAP_LOC_RE.finditer(text) if m.group(1).strip()]


def _robots_sitemap_dirs(robots_text: str) -> list[str]:
    out: list[str] = []
    for line in (robots_text or "").splitlines():
        s = line.strip()
        if s.lower().startswith("sitemap:"):
            url = s.split(":", 1)[1].strip()
            if url.startswith(("http://", "https://")):
                out.append(url)
    return out


# ---------------------------------------------------------------------------
# security 観測 fact (header 由来・推測なし)
# ---------------------------------------------------------------------------
def _samesite(cookie_lower: str) -> str | None:
    m = re.search(r"samesite=([a-z]+)", cookie_lower)
    return m.group(1) if m else None


def security_facts(url: str, headers: dict[str, str], set_cookies: list[str]) -> dict:
    """response header から観測できる security 属性を fact として抽出する。"""
    def has(name: str) -> str | None:
        return headers.get(name)

    cookies = []
    for raw in set_cookies:
        low = raw.lower()
        name = raw.split("=", 1)[0].strip()
        cookies.append({
            "name": name,
            "secure": "secure" in low,
            "http_only": "httponly" in low,
            "same_site": _samesite(low),
        })

    return {
        "url": url,
        "source": "http_header",
        "kind": "fact",
        "observed_at": _iso(_now()),
        "transport_https": url.startswith("https://"),
        "hsts": has("strict-transport-security"),
        "content_security_policy": has("content-security-policy"),
        "content_security_policy_report_only": has("content-security-policy-report-only"),
        "x_frame_options": has("x-frame-options"),
        "x_content_type_options": has("x-content-type-options"),
        "referrer_policy": has("referrer-policy"),
        "permissions_policy": has("permissions-policy"),
        "cross_origin_opener_policy": has("cross-origin-opener-policy"),
        "server": has("server"),
        "x_powered_by": has("x-powered-by"),
        "set_cookies": cookies,
        "cookie_count": len(cookies),
    }


# ---------------------------------------------------------------------------
# 静的 DOM/HTML/CSS 観測 ("ブラウザ確認" の stdlib Python 実装・外部ライブラリ非依存)
#
# urllib は JS を実行できずレンダリングもしないため、取得済み HTML/CSS から静的に観測できる
# fact (DOM 構造/見出し/nav・link/form/meta・OGP・JSON-LD/宣言色・font/a11y semantic) だけを
# 採取する。実ピクセルスクリーンショット・computed 幾何・CWV・JS 実行後 DOM 等は
# レンダリングエンジンが必須で捏造できないため observation_gap(blocked, reason=static-analysis-only)
# として記録し、fact/inference へ昇格させない (三値分離契約)。
# ---------------------------------------------------------------------------
# レンダリングエンジンが必須で stdlib では取得不能な観測カタログ (捏造禁止・gap 化する)。
RENDERING_ONLY_GAPS = [
    ("screenshot", "実ピクセルスクリーンショット/annotated raster はレンダリングエンジンが必要"),
    ("computed_geometry", "bounding_box_px/解決後レイアウト座標は computed style が必要 (宣言値のみ静的採取)"),
    ("resolved_color", "cascade 解決後の実効色は computed style が必要 (宣言色のみ静的採取)"),
    ("cwv_field_sample", "LCP/CLS/INP/TTFB はブラウザ実測が必要"),
    ("post_js_dom", "JS 実行後 DOM / SPA 画面遷移は script 実行が必要"),
    ("interaction_state", "hover/focus/active 等の状態観測はブラウザ操作が必要"),
]

_HEADING_TAGS = {"h1", "h2", "h3", "h4", "h5", "h6"}
_LANDMARK_TAGS = {"header", "nav", "main", "footer", "aside", "section", "article", "form"}
_HEX_RE = re.compile(r"#([0-9a-fA-F]{3,8})\b")
_RGB_RE = re.compile(r"rgba?\(\s*(\d{1,3})\s*,\s*(\d{1,3})\s*,\s*(\d{1,3})\s*(?:,\s*([0-9.]+)\s*)?\)")
_FONT_RE = re.compile(r"font-family\s*:\s*([^;{}\"']+)", re.IGNORECASE)


def _canon_hex(h: str) -> str | None:
    """#rgb / #rgba / #rrggbb / #rrggbbaa を hex8 (#rrggbbaa) へ正規化する。"""
    h = h.lower()
    if len(h) == 3:
        return f"#{h[0]*2}{h[1]*2}{h[2]*2}ff"
    if len(h) == 4:
        return f"#{h[0]*2}{h[1]*2}{h[2]*2}{h[3]*2}"
    if len(h) == 6:
        return f"#{h}ff"
    if len(h) == 8:
        return f"#{h}"
    return None


def _canon_rgb(m: "re.Match") -> str | None:
    try:
        r, g, b = (max(0, min(255, int(m.group(i)))) for i in (1, 2, 3))
    except (TypeError, ValueError):
        return None
    a = m.group(4)
    av = 255 if a in (None, "") else max(0, min(255, round(float(a) * 255)))
    return f"#{r:02x}{g:02x}{b:02x}{av:02x}"


def _extract_declared_colors(text: str) -> list[str]:
    out: list[str] = []
    for m in _HEX_RE.finditer(text or ""):
        c = _canon_hex(m.group(1))
        if c:
            out.append(c)
    for m in _RGB_RE.finditer(text or ""):
        c = _canon_rgb(m)
        if c:
            out.append(c)
    return out


def _extract_declared_fonts(text: str) -> list[str]:
    out: list[str] = []
    for m in _FONT_RE.finditer(text or ""):
        fam = m.group(1).strip().split(",")[0].strip().strip("'\"")
        if fam and not fam.lower().startswith("var(") and not fam.lower().startswith("inherit"):
            out.append(fam)
    return out


class _StaticObserver(html.parser.HTMLParser):
    """保存済み HTML を静的解析し観測 fact 素材を採取する (browser 不使用・stdlib による静的 HTTP 観測)。

    単一 capture スロットで最外の関心要素のテキストを拾う best-effort 実装。href/属性系は
    starttag で確定採取し、テキスト (見出し/リンク文言/title/JSON-LD/inline CSS) は非破壊で
    近似採取する (nested 時は外側優先)。壊れた markup でも採取済み分を残す。
    """

    def __init__(self) -> None:
        super().__init__(convert_charrefs=True)
        self.lang: str | None = None
        self.title_parts: list[str] = []
        self.meta: dict[str, str] = {}
        self.og: dict[str, str] = {}
        self.json_ld: list[str] = []
        self.headings: list[tuple[int, str]] = []
        self.links: list[dict] = []
        self.forms: list[dict] = []
        self.scripts: list[str] = []
        self.stylesheets: list[str] = []
        self.inline_styles: list[str] = []
        self.style_blocks: list[str] = []
        self.tag_counts: dict[str, int] = {}
        self.landmarks: set[str] = set()
        self.roles: list[str] = []
        self.aria_attr_count = 0
        self.images_total = 0
        self.images_with_alt = 0
        self.theme_color: str | None = None
        self.color_scheme: str | None = None
        self.favicon: str | None = None
        self.generator: str | None = None
        self._depth = 0
        self._max_depth = 0
        self._capture: str | None = None
        self._buf: list[str] = []
        self._ld_capture = False
        self._active_link: dict | None = None

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        d = {k: (v or "") for k, v in attrs}
        self.tag_counts[tag] = self.tag_counts.get(tag, 0) + 1
        self._depth += 1
        self._max_depth = max(self._max_depth, self._depth)
        if tag in _LANDMARK_TAGS:
            self.landmarks.add(tag)
        if d.get("role"):
            self.roles.append(d["role"])
        self.aria_attr_count += sum(1 for k in d if k.startswith("aria-"))
        if d.get("style"):
            self.inline_styles.append(d["style"])

        if tag == "html" and d.get("lang") and self.lang is None:
            self.lang = d["lang"]
        elif tag == "meta":
            name = (d.get("name") or "").lower()
            prop = (d.get("property") or "").lower()
            content = d.get("content") or ""
            if name and content:
                self.meta[name] = content
                if name == "theme-color":
                    self.theme_color = content
                elif name == "color-scheme":
                    self.color_scheme = content
                elif name == "generator":
                    self.generator = content
            if prop.startswith("og:") and content:
                self.og[prop] = content
        elif tag == "link":
            rel = (d.get("rel") or "").lower()
            href = d.get("href") or ""
            if "stylesheet" in rel and href:
                self.stylesheets.append(href)
            if "icon" in rel and href and self.favicon is None:
                self.favicon = href
        elif tag == "script":
            if d.get("src"):
                self.scripts.append(d["src"])
            if (d.get("type") or "").lower() == "application/ld+json":
                self._ld_capture = True
                self._buf = []
        elif tag == "img":
            self.images_total += 1
            if d.get("alt"):
                self.images_with_alt += 1
        elif tag == "form":
            self.forms.append({
                "action": d.get("action", ""),
                "method": (d.get("method") or "get").lower(),
                "inputs": [],
            })
        elif tag in ("input", "select", "textarea", "button") and self.forms:
            self.forms[-1]["inputs"].append({
                "tag": tag,
                "type": d.get("type") or ("textarea" if tag == "textarea" else tag),
                "name": d.get("name") or d.get("id") or "",
                "required": "required" in d,
            })

        if tag == "a" and d.get("href"):
            link = {"href": d["href"], "text": ""}
            self.links.append(link)
            if self._capture is None:
                self._capture, self._active_link, self._buf = "a", link, []
        elif tag in _HEADING_TAGS and self._capture is None:
            self._capture, self._buf = tag, []
        elif tag == "title" and self._capture is None:
            self._capture, self._buf = "title", []
        elif tag == "style" and self._capture is None:
            self._capture, self._buf = "style", []

    def handle_data(self, data: str) -> None:
        if self._ld_capture or self._capture:
            self._buf.append(data)

    def handle_endtag(self, tag: str) -> None:
        if self._depth > 0:
            self._depth -= 1
        if self._ld_capture and tag == "script":
            text = "".join(self._buf).strip()
            if text:
                self.json_ld.append(text)
            self._ld_capture, self._buf = False, []
            return
        if self._capture is None or self._capture != tag:
            return
        text = "".join(self._buf).strip()
        if tag in _HEADING_TAGS:
            self.headings.append((int(tag[1]), text))
        elif tag == "title" and text:
            self.title_parts.append(text)
        elif tag == "style" and text:
            self.style_blocks.append(text)
        elif tag == "a" and self._active_link is not None:
            self._active_link["text"] = text
        self._capture, self._buf, self._active_link = None, [], None


def static_observe(url: str, final_url: str | None, http_status, content_type,
                   body: bytes, css_texts: list[str]) -> dict:
    """1 ページ分の静的観測 fact を組む (fact/observation_status=observed)。"""
    obs = _StaticObserver()
    try:
        obs.feed(body.decode("utf-8", "replace"))
    except (ValueError, AssertionError):
        pass  # 壊れた markup でも採取済み分を使う

    style_sources = obs.inline_styles + obs.style_blocks + list(css_texts)
    colors: dict[str, int] = {}
    fonts: dict[str, int] = {}
    for chunk in style_sources:
        for c in _extract_declared_colors(chunk):
            colors[c] = colors.get(c, 0) + 1
        for f in _extract_declared_fonts(chunk):
            fonts[f] = fonts.get(f, 0) + 1

    base = final_url or url
    target_origin = _origin_of(url)
    internal: list[dict] = []
    external: list[dict] = []
    for link in obs.links:
        absu = _absolutize(base, link["href"])
        if not absu:
            continue
        entry = {"href": absu, "text": (link.get("text") or "")[:200]}
        (internal if _origin_of(absu) == target_origin else external).append(entry)

    return {
        "url": url,
        "final_url": final_url,
        "observed_at": _iso(_now()),
        "observation_status": "observed",
        "source": "static-html-analysis",
        "method": "stdlib:html.parser+urllib",
        "http_status": http_status,
        "content_type": content_type,
        "document": {
            "title": (" ".join(obs.title_parts).strip() or None),
            "lang": obs.lang,
            "meta": obs.meta,
            "open_graph": obs.og,
            "json_ld_count": len(obs.json_ld),
            "generator": obs.generator,
        },
        "document_brand": {
            "theme_color": obs.theme_color,
            "color_scheme": obs.color_scheme,
            "favicon": obs.favicon,
        },
        "headings": [{"level": lvl, "text": txt[:300]} for lvl, txt in obs.headings],
        "dom_outline": {
            "tag_counts": obs.tag_counts,
            "max_depth": obs._max_depth,
            "landmarks": sorted(obs.landmarks),
        },
        "links": {
            "internal": internal,
            "external": external,
            "internal_count": len(internal),
            "external_count": len(external),
        },
        "forms": obs.forms,
        "tech_signals": {
            "scripts": obs.scripts,
            "stylesheets": obs.stylesheets,
            "meta_generator": obs.generator,
        },
        "a11y": {
            "roles": sorted(set(obs.roles)),
            "aria_attr_count": obs.aria_attr_count,
            "images_total": obs.images_total,
            "images_with_alt": obs.images_with_alt,
        },
        "declared_tokens": {
            "colors": [{"canonical_hex8": c, "usage_count": n}
                       for c, n in sorted(colors.items(), key=lambda kv: (-kv[1], kv[0]))],
            "fonts": [{"family": f, "usage_count": n}
                      for f, n in sorted(fonts.items(), key=lambda kv: (-kv[1], kv[0]))],
        },
    }


# ---------------------------------------------------------------------------
# budget tracker — remaining は C12 が prior run を差し引いた純残量。
# ---------------------------------------------------------------------------
class Budget:
    NEEDS = ("requests", "bytes", "pages")

    def __init__(self, budget_doc: dict, prior_ledger: dict | None) -> None:
        self.granted = bool(budget_doc.get("granted"))
        self.crawl_mode = str(budget_doc.get("crawl_mode", "single"))
        self.reset_on_retry = bool(budget_doc.get("budget_reset_on_retry", False))
        keymap = _REMAINING_KEYS.get(self.crawl_mode, _REMAINING_KEYS["single"])
        remaining = budget_doc.get("remaining")
        remaining = remaining if isinstance(remaining, dict) else {}
        self.denied = bool(remaining.get("denied"))
        self.remaining: dict[str, int] = {}
        for need in self.NEEDS:
            val = remaining.get(keymap[need])
            self.remaining[need] = val if isinstance(val, int) and val >= 0 else 0
        prior = prior_ledger if isinstance(prior_ledger, dict) else {}
        self.prior_ledger = dict(prior)  # 他 consumer (C03 静的観測等) のキーを保全
        self.prior = {need: _safe_int(prior.get(_LEDGER_KEY[need])) for need in self.NEEDS}
        self.consumed = {need: 0 for need in self.NEEDS}

    def ensure(self, *needs: str) -> None:
        """指定 resource の残量が無ければ budget-exhausted で停止する (消費前 gate)。"""
        for need in needs:
            if self.remaining.get(need, 0) <= 0:
                raise StopFetching("budget-exhausted", need)

    def consume(self, need: str, amount: int = 1) -> None:
        self.remaining[need] = self.remaining.get(need, 0) - amount
        self.consumed[need] += amount

    def has(self, need: str) -> bool:
        return self.remaining.get(need, 0) > 0

    def cumulative_ledger(self) -> dict:
        """coverage manifest へ書く累積 ledger (prior + this run)。他キーは保全する。"""
        entry = dict(self.prior_ledger)
        for need in self.NEEDS:
            entry[_LEDGER_KEY[need]] = self.prior[need] + self.consumed[need]
        return entry


# ---------------------------------------------------------------------------
# fetch 抽象 (Real=urllib / Fixture=写像)。停止/再試行ロジックは基底で共有し
# fixture でも 403/429/backoff の分岐をテストできる。
# ---------------------------------------------------------------------------
class FetchResult:
    __slots__ = ("status", "headers", "set_cookies", "body", "truncated", "final_url")

    def __init__(self, status: int, headers: dict[str, str], set_cookies: list[str],
                 body: bytes, truncated: bool, final_url: str) -> None:
        self.status = status
        self.headers = headers
        self.set_cookies = set_cookies
        self.body = body
        self.truncated = truncated
        self.final_url = final_url


def _parse_retry_after(headers: dict[str, str]) -> float | None:
    raw = headers.get("retry-after")
    if not raw:
        return None
    raw = raw.strip()
    if raw.isdigit():
        return float(raw)
    try:
        when = parsedate_to_datetime(raw)
    except (TypeError, ValueError, IndexError):
        return None
    if when is None:
        return None
    if when.tzinfo is None:
        when = when.replace(tzinfo=timezone.utc)
    return max(0.0, (when - _now()).total_seconds())


_REDIRECT_STATUSES = (301, 302, 303, 307, 308)


def _check_redirect_origin(allowed_origin: str | None, current_url: str, newurl: str, status: int) -> None:
    """redirect 先 origin が allowed_origin と厳密一致しなければ CrossOriginRedirect を投げる。

    allowed_origin/redirect 先 origin が解決不能な場合も追従しない (fail-closed)。
    """
    target_origin = _origin_of(newurl)
    if allowed_origin is None or target_origin is None or target_origin != allowed_origin:
        raise CrossOriginRedirect(current_url, newurl, target_origin, status)


class _SameOriginRedirectHandler(urllib.request.HTTPRedirectHandler):
    """same_origin_redirects_only=true (C09 load_policy) を urllib redirect 層で施行する。

    urllib 既定の HTTPRedirectHandler は cross-origin redirect も黙って追従するため、
    redirect_request で追従前に origin を検査し、不一致なら CrossOriginRedirect で拒否する。
    同一 origin redirect は urllib 既定どおり追従 (上限 max_redirections も既定のまま)。
    """

    def __init__(self, allowed_origin: str | None) -> None:
        self.allowed_origin = allowed_origin

    def redirect_request(self, req, fp, code, msg, headers, newurl):
        _check_redirect_origin(self.allowed_origin, req.full_url, newurl, code)
        return super().redirect_request(req, fp, code, msg, headers, newurl)


class Fetcher:
    """min-interval + Retry-After + 有界 backoff + stop 条件を honor する取得ループ。"""

    def __init__(self, *, min_interval_ms: int, backoff: dict, honor_retry_after: bool,
                 max_retries: int, max_body_bytes: int) -> None:
        self.min_interval_ms = max(0, min_interval_ms)
        self.backoff = backoff
        self.honor_retry_after = honor_retry_after
        self.max_retries = max(0, max_retries)
        self.max_body_bytes = max_body_bytes
        self._last_monotonic: float | None = None
        self.network_requests = 0
        self.retries_used = 0

    def fetch(self, url: str) -> FetchResult:
        self._respect_interval()
        attempt = 0
        while True:
            try:
                res = self._do_request(url)
            except _TransientError as exc:
                if attempt < self.max_retries:
                    attempt += 1
                    self.retries_used += 1
                    self._sleep(self._backoff_seconds(attempt))
                    continue
                raise StopFetching("unstable-response", f"{url}: {exc}")
            status = res.status
            if status == 403:
                raise StopFetching("403", url)
            if status == 429:
                retry_after = _parse_retry_after(res.headers) if self.honor_retry_after else None
                cap = self.backoff.get("max_ms", DEFAULT_BACKOFF["max_ms"]) / 1000.0
                if attempt < self.max_retries and retry_after is not None and retry_after <= cap:
                    attempt += 1
                    self.retries_used += 1
                    self._sleep(retry_after)
                    continue
                raise StopFetching("429", url)
            if 500 <= status < 600:
                if attempt < self.max_retries:
                    attempt += 1
                    self.retries_used += 1
                    self._sleep(self._backoff_seconds(attempt))
                    continue
                raise StopFetching("unstable-response", f"{url}: http {status}")
            return res

    def _backoff_seconds(self, attempt: int) -> float:
        initial = self.backoff.get("initial_ms", DEFAULT_BACKOFF["initial_ms"])
        mult = self.backoff.get("multiplier", DEFAULT_BACKOFF["multiplier"])
        cap = self.backoff.get("max_ms", DEFAULT_BACKOFF["max_ms"])
        return min(cap, initial * (mult ** max(0, attempt - 1))) / 1000.0

    def _respect_interval(self) -> None:
        if self._last_monotonic is None or self.min_interval_ms <= 0:
            return
        elapsed_ms = (time.monotonic() - self._last_monotonic) * 1000.0
        wait_ms = self.min_interval_ms - elapsed_ms
        if wait_ms > 0:
            self._sleep(wait_ms / 1000.0)

    def _sleep(self, seconds: float) -> None:
        if seconds > 0:
            time.sleep(seconds)

    def _do_request(self, url: str) -> FetchResult:  # pragma: no cover - 抽象
        raise NotImplementedError


class RealFetcher(Fetcher):
    def _do_request(self, url: str) -> FetchResult:
        self.network_requests += 1
        opener = urllib.request.build_opener(_SameOriginRedirectHandler(_origin_of(url)))
        req = urllib.request.Request(url, headers={"User-Agent": USER_AGENT, "Accept": "*/*"})
        try:
            with opener.open(req, timeout=FETCH_TIMEOUT_SECONDS) as resp:
                result = self._read(resp, resp.status, resp.geturl())
        except urllib.error.HTTPError as exc:
            # 403/429/5xx は status を持つ応答として返し、fetch() の停止/再試行分岐へ委ねる。
            result = self._read(exc, exc.code, url)
        except (urllib.error.URLError, OSError, ValueError) as exc:
            raise _TransientError(str(exc))
        finally:
            self._last_monotonic = time.monotonic()
        return result

    def _read(self, resp, status: int, final_url: str) -> FetchResult:
        raw = resp.read(self.max_body_bytes + 1) if hasattr(resp, "read") else b""
        truncated = len(raw) > self.max_body_bytes
        body = raw[: self.max_body_bytes]
        msg = getattr(resp, "headers", None)
        headers = {k.lower(): v for k, v in (msg.items() if msg else [])}
        set_cookies = list(msg.get_all("Set-Cookie") or []) if msg else []
        return FetchResult(status, headers, set_cookies, body, truncated, final_url)


class FixtureFetcher(Fetcher):
    """URL→{status,headers,body,set_cookie} 写像から応答を返す。network も sleep もしない。

    redirect (30x + location) は RealFetcher と同じ same-origin 施行込みで追従し、
    cross-origin redirect の拒否分岐を network 無しでテストできる。
    """

    _MAX_REDIRECTS = 10  # urllib HTTPRedirectHandler.max_redirections と同値

    def __init__(self, fixtures: dict, **kwargs) -> None:
        super().__init__(**kwargs)
        self.fixtures = fixtures if isinstance(fixtures, dict) else {}

    def _do_request(self, url: str) -> FetchResult:
        self.network_requests += 1
        self._last_monotonic = time.monotonic()
        allowed_origin = _origin_of(url)
        current = url
        for _hop in range(self._MAX_REDIRECTS):
            entry = self.fixtures.get(current)
            if entry is None:
                raise _TransientError(f"no fixture: {current}")
            status = _safe_int(entry.get("status"), 200)
            headers = {str(k).lower(): str(v) for k, v in (entry.get("headers") or {}).items()}
            if status in _REDIRECT_STATUSES and headers.get("location"):
                newurl = urljoin(current, headers["location"])
                _check_redirect_origin(allowed_origin, current, newurl, status)
                current = newurl
                continue
            set_cookies = [str(c) for c in (entry.get("set_cookie") or [])]
            body_raw = entry.get("body", "")
            body = body_raw.encode("utf-8") if isinstance(body_raw, str) else bytes(body_raw or b"")
            truncated = len(body) > self.max_body_bytes
            return FetchResult(status, headers, set_cookies, body[: self.max_body_bytes], truncated, current)
        raise _TransientError(f"redirect loop: {url}")

    def _respect_interval(self) -> None:  # fixture は無負荷 → interval 不要
        return

    def _sleep(self, seconds: float) -> None:  # fixture は決定論・高速
        return


# ---------------------------------------------------------------------------
# snapshot 取得 (cache 再利用込み)
# ---------------------------------------------------------------------------
class Run:
    """1 回の取得 run の状態。snapshot/discovery/ledger を集約する。"""

    def __init__(self, *, url: str, origin: str, out_dir: Path, evidence: dict, budget: Budget,
                 fetcher: Fetcher, coverage_in: dict | None, cache_ttl: int) -> None:
        self.url = url
        self.origin = origin
        self.out_dir = out_dir
        self.evidence = evidence
        self.budget = budget
        self.fetcher = fetcher
        self.coverage_in = coverage_in if isinstance(coverage_in, dict) else {}
        self.cache_ttl = cache_ttl
        self.bodies_dir = out_dir / "bodies"
        self.snapshots_dir = out_dir / "snapshots"
        self.snapshots: list[dict] = []
        self.security: list[dict] = []
        self.discovered: dict[str, dict] = {}
        self.covered: list[str] = []
        self.events: list[dict] = []
        self.observation_gaps: list[dict] = []
        self.stopped: dict | None = None
        self._prior_snapshots = self.coverage_in.get("snapshots") if isinstance(self.coverage_in.get("snapshots"), dict) else {}

    # -- cache -------------------------------------------------------------
    def _cached(self, url: str) -> dict | None:
        entry = self._prior_snapshots.get(url)
        if not isinstance(entry, dict):
            return None
        fetched = _parse_iso(str(entry.get("fetched_at", "")))
        if fetched is None or (_now() - fetched).total_seconds() > self.cache_ttl:
            return None
        body_path = entry.get("body_path")
        if not body_path or not Path(body_path).is_file():
            return None
        return entry

    # -- fetch -------------------------------------------------------------
    def fetch(self, url: str, *, is_page: bool) -> tuple[FetchResult | None, dict]:
        """URL を取得 (or cache 再利用) し snapshot を積む。返り値 (result|None, record)。

        cache hit 時は budget を消費しない。cross-origin redirect 拒否時は result=None・
        record は observation_gap (本文非保存・requests のみ消費)。
        """
        cached = self._cached(url)
        if cached is not None:
            body = Path(cached["body_path"]).read_bytes()
            snap = dict(cached)
            snap["from_cache"] = True
            self.snapshots.append(snap)
            if url not in self.covered:
                self.covered.append(url)
            self.events.append({"url": url, "action": "cache_hit"})
            return FetchResult(_safe_int(cached.get("http_status"), 200),
                               cached.get("headers") or {}, cached.get("set_cookie") or [],
                               body, bool(cached.get("truncated")), url), snap

        needs = ("requests", "bytes", "pages") if is_page else ("requests", "bytes")
        self.budget.ensure(*needs)
        try:
            result = self.fetcher.fetch(url)   # StopFetching を投げうる
        except CrossOriginRedirect as exc:
            # same_origin_redirects_only 施行: 初回 request は発生済みなので requests のみ
            # 消費し、別 origin の応答本文は保存しない (bytes/pages 非消費)。
            self.budget.consume("requests", 1)
            return None, self._record_observation_gap(url, exc)
        self.budget.consume("requests", 1)
        self.budget.consume("bytes", len(result.body))
        if is_page:
            self.budget.consume("pages", 1)

        snap = self._persist(url, result)
        self.snapshots.append(snap)
        self.security.append(security_facts(result.final_url, result.headers, result.set_cookies))
        if url not in self.covered:
            self.covered.append(url)
        self.events.append({"url": url, "action": "fetched", "http_status": result.status,
                            "bytes": len(result.body)})
        return result, snap

    def _record_observation_gap(self, url: str, exc: CrossOriginRedirect) -> dict:
        """cross-origin redirect 拒否を observation_gap として記録する (本文非保存)。"""
        gap = {
            "url": url,
            "origin": _origin_of(url),
            "observation_gap": True,
            "reason": "cross-origin-redirect-blocked",
            "redirect_target": exc.redirect_target,
            "redirect_origin": exc.target_origin,
            "http_status": exc.status,
            "observed_at": _iso(_now()),
            "body_saved": False,
        }
        self.observation_gaps.append(gap)
        self.events.append({"url": url, "action": "observation_gap",
                            "reason": "cross-origin-redirect-blocked",
                            "redirect_origin": exc.target_origin})
        return gap

    def _persist(self, url: str, result: FetchResult) -> dict:
        key = _url_key(url)
        self.bodies_dir.mkdir(parents=True, exist_ok=True)
        body_path = self.bodies_dir / f"{key}.body"
        body_path.write_bytes(result.body)
        digest = hashlib.sha256(result.body).hexdigest()
        snapshot = {
            "url": url,
            "final_url": result.final_url,
            "origin": _origin_of(url),
            "fetched_at": _iso(_now()),
            "http_status": result.status,
            "headers": result.headers,
            "set_cookie": result.set_cookies,
            "content_type": result.headers.get("content-type"),
            "body_sha256": digest,
            "body_bytes": len(result.body),
            "truncated": result.truncated,
            "body_path": body_path.as_posix(),
            "from_cache": False,
            "provenance": {
                "fetcher": "urllib",
                "user_agent": USER_AGENT,
                "policy_version": self.evidence.get("policy_version"),
                "authz_expires_at": self.evidence.get("expires_at"),
            },
        }
        _write_json(self.snapshots_dir / f"{key}.json", snapshot)
        return snapshot

    # -- discovery ---------------------------------------------------------
    def _add_discovered(self, url: str, source: str) -> None:
        norm = url.strip()
        if not norm.startswith(("http://", "https://")):
            return
        entry = self.discovered.get(norm)
        origin = _origin_of(norm)
        if entry is None:
            self.discovered[norm] = {
                "url": norm,
                "origin": origin,
                "same_origin": origin == self.origin,
                "sources": [source],
            }
        elif source not in entry["sources"]:
            entry["sources"].append(source)

    def discover(self, primary: FetchResult) -> None:
        """primary HTML のリンク + robots Sitemap 指令 + sitemap.xml から URL を台帳化する。"""
        links, assets = _parse_html(self.url, primary.body)
        for link in links:
            self._add_discovered(link, "html_link")
        for asset_url, _kind in assets:
            self._add_discovered(asset_url, "asset_ref")

        robots_excerpt = ""
        robots = self.evidence.get("robots")
        if isinstance(robots, dict):
            robots_excerpt = str(robots.get("raw_excerpt") or "")
        sitemap_urls = _robots_sitemap_dirs(robots_excerpt)
        if not sitemap_urls:
            sitemap_urls = [self.origin.rstrip("/") + "/sitemap.xml"]

        fetched = 0
        for sm in sitemap_urls:
            if fetched >= MAX_SITEMAPS_PER_RUN or not self.budget.has("requests") or not self.budget.has("bytes"):
                break
            self._add_discovered(sm, "sitemap_ref")
            try:
                res, _snap = self.fetch(sm, is_page=False)
            except StopFetching as stop:
                self.stopped = {"reason": stop.reason, "detail": stop.detail, "phase": "sitemap"}
                return
            if res is not None and res.status == 200:
                for loc in _parse_sitemap(res.body):
                    self._add_discovered(loc, "sitemap")
            fetched += 1

    # -- assets ------------------------------------------------------------
    def fetch_assets(self, primary: FetchResult, max_assets: int) -> None:
        """primary HTML が参照する same-origin static asset を予算内で snapshot する。"""
        if max_assets <= 0:
            return
        _links, assets = _parse_html(self.url, primary.body)
        seen: set[str] = set()
        count = 0
        for asset_url, _kind in assets:
            if count >= max_assets:
                break
            if asset_url in seen or _origin_of(asset_url) != self.origin:
                continue
            seen.add(asset_url)
            if not self.budget.has("requests") or not self.budget.has("bytes"):
                self.stopped = self.stopped or {"reason": "budget-exhausted", "detail": "assets", "phase": "assets"}
                return
            try:
                self.fetch(asset_url, is_page=False)
            except StopFetching as stop:
                self.stopped = {"reason": stop.reason, "detail": stop.detail, "phase": "assets"}
                return
            count += 1

    # -- 静的観測 ("ブラウザ確認" の stdlib 実装) --------------------------
    def build_static_observation(self) -> dict:
        """取得済み page snapshot を stdlib 静的解析し static-observation fact を組む。

        HTML snapshot (content_type html or primary URL) を _StaticObserver で解析し、
        同一 origin stylesheet snapshot の本文を color/font 抽出へ供給する。レンダリング
        必須の観測は rendering_gaps に blocked として明示する (捏造しない)。
        """
        css_texts: list[str] = []
        for snap in self.snapshots:
            ct = (snap.get("content_type") or "").lower()
            body_path = snap.get("body_path")
            if "css" in ct and body_path and Path(body_path).is_file():
                css_texts.append(Path(body_path).read_text(encoding="utf-8", errors="replace"))

        pages: list[dict] = []
        for snap in self.snapshots:
            ct = (snap.get("content_type") or "").lower()
            body_path = snap.get("body_path")
            is_html = "html" in ct or snap.get("url") == self.url
            if not is_html or not body_path or not Path(body_path).is_file():
                continue
            pages.append(static_observe(
                snap["url"], snap.get("final_url"), snap.get("http_status"),
                snap.get("content_type"), Path(body_path).read_bytes(), css_texts,
            ))

        agg_colors: dict[str, int] = {}
        agg_fonts: dict[str, int] = {}
        for page in pages:
            for c in page["declared_tokens"]["colors"]:
                agg_colors[c["canonical_hex8"]] = agg_colors.get(c["canonical_hex8"], 0) + c["usage_count"]
            for f in page["declared_tokens"]["fonts"]:
                agg_fonts[f["family"]] = agg_fonts.get(f["family"], 0) + f["usage_count"]

        return {
            "schema_version": SCHEMA_VERSION,
            "target_url": self.url,
            "target_origin": self.origin,
            "generated_at": _iso(_now()),
            "source": "static-html-analysis",
            "method": "stdlib:html.parser+urllib (static HTTP only, no external libraries)",
            "page_count": len(pages),
            "pages": pages,
            "declared_tokens": {
                "colors": [{"canonical_hex8": c, "usage_count": n}
                           for c, n in sorted(agg_colors.items(), key=lambda kv: (-kv[1], kv[0]))],
                "fonts": [{"family": f, "usage_count": n}
                          for f, n in sorted(agg_fonts.items(), key=lambda kv: (-kv[1], kv[0]))],
            },
            "rendering_gaps": [
                {"category": cat, "observation_status": "blocked",
                 "reason": "static-analysis-only", "note": note}
                for cat, note in RENDERING_ONLY_GAPS
            ],
        }


# ---------------------------------------------------------------------------
# levers / budget の読み出し
# ---------------------------------------------------------------------------
def _levers(budget_doc: dict, evidence: dict) -> dict:
    levers = budget_doc.get("instant_load_levers")
    levers = levers if isinstance(levers, dict) else {}
    rate = evidence.get("rate_policy") if isinstance(evidence.get("rate_policy"), dict) else {}
    min_interval = max(
        _safe_int(levers.get("min_interval_ms"), DEFAULT_MIN_INTERVAL_MS),
        _safe_int(rate.get("min_interval_ms"), 0),
    )
    backoff = levers.get("backoff") if isinstance(levers.get("backoff"), dict) else DEFAULT_BACKOFF
    honor = levers.get("honor_retry_after", rate.get("honor_retry_after", True))
    return {
        "min_interval_ms": min_interval or DEFAULT_MIN_INTERVAL_MS,
        "backoff": backoff,
        "honor_retry_after": bool(honor),
        "max_retries": _safe_int(budget_doc.get("max_retries"), DEFAULT_MAX_RETRIES),
    }


def _prior_ledger_for_origin(coverage: dict | None, origin: str) -> dict:
    if not isinstance(coverage, dict):
        return {}
    ledger = coverage.get("request_ledger")
    if isinstance(ledger, dict) and isinstance(ledger.get(origin), dict):
        return ledger[origin]
    return {}


# ---------------------------------------------------------------------------
# CLI / run
# ---------------------------------------------------------------------------
def _parse_args(argv: list[str]) -> argparse.Namespace:
    ap = argparse.ArgumentParser(
        prog="fetch-snapshot",
        description="C12 認可済み低負荷取得 + URL discovery + security fact 採取 + multi-run resume",
        add_help=True,
    )
    ap.add_argument("--url")
    ap.add_argument("--out-dir")
    ap.add_argument("--authz-evidence")
    ap.add_argument("--request-budget")
    ap.add_argument("--discover-urls", action="store_true")
    ap.add_argument("--discovered-urls-out", default=None)
    ap.add_argument("--coverage-manifest-in", default=None)
    ap.add_argument("--coverage-manifest-out", default=None)
    ap.add_argument("--max-assets", type=int, default=DEFAULT_MAX_ASSETS)
    ap.add_argument("--no-assets", action="store_true")
    ap.add_argument("--fixture-map", default=None)
    ap.add_argument("--self-test", action="store_true")
    return ap.parse_args(argv)


def _build_fetcher(args: argparse.Namespace, levers: dict, budget_doc: dict) -> Fetcher:
    max_body = _safe_int(budget_doc.get("max_response_bytes"), DEFAULT_MAX_RESPONSE_BYTES)
    kwargs = dict(min_interval_ms=levers["min_interval_ms"], backoff=levers["backoff"],
                  honor_retry_after=levers["honor_retry_after"], max_retries=levers["max_retries"],
                  max_body_bytes=max_body)
    if args.fixture_map:
        fixtures = _load_json_file(args.fixture_map, "--fixture-map")
        if not isinstance(fixtures, dict):
            raise UsageError("--fixture-map root must be a JSON object {url: response}")
        return FixtureFetcher(fixtures, **kwargs)
    return RealFetcher(**kwargs)


def run(argv: list[str]) -> tuple[int, dict]:
    args = _parse_args(argv)
    for required in ("url", "out_dir", "authz_evidence", "request_budget"):
        if not getattr(args, required):
            raise UsageError(f"--{required.replace('_', '-')} is required")

    origin = _origin_of(args.url)
    if origin is None:
        raise UsageError(f"--url must be an http(s) URL with a host: {args.url}")

    if _AUTHZ is None:
        raise AuthzDenied(f"authz module (C12) 読込不能 → fail-closed: {_AUTHZ_PATH}")

    evidence = _load_json_file(args.authz_evidence, "--authz-evidence")
    budget_doc = _load_json_file(args.request_budget, "--request-budget")
    if not isinstance(evidence, dict) or not isinstance(budget_doc, dict):
        raise UsageError("--authz-evidence / --request-budget root must be a JSON object")

    # (1) 認可の消費: C12 の decide を共有して再評価 (fail-closed)。
    decision, reason = _AUTHZ.decide(evidence, {})
    if decision != "allow":
        raise AuthzDenied(f"authz={decision} ({reason}): {origin}")
    if evidence.get("origin") != origin:
        raise AuthzDenied(f"evidence.origin ({evidence.get('origin')}) != url origin ({origin})")
    if budget_doc.get("origin") != origin:
        raise AuthzDenied(f"budget.origin ({budget_doc.get('origin')}) != url origin ({origin})")
    if not budget_doc.get("granted"):
        raise AuthzDenied(f"request-budget granted=false: {origin}")

    coverage_in = None
    if args.coverage_manifest_in:
        loaded = _load_json_file(args.coverage_manifest_in, "--coverage-manifest-in")
        if not isinstance(loaded, dict):
            raise UsageError("--coverage-manifest-in root must be a JSON object")
        coverage_in = loaded

    budget = Budget(budget_doc, _prior_ledger_for_origin(coverage_in, origin))
    levers = _levers(budget_doc, evidence)
    fetcher = _build_fetcher(args, levers, budget_doc)
    cache_ttl = _safe_int(evidence.get("ttl_seconds"), DEFAULT_CACHE_TTL_SECONDS)

    out_dir = Path(args.out_dir)
    run_state = Run(url=args.url, origin=origin, out_dir=out_dir, evidence=evidence, budget=budget,
                    fetcher=fetcher, coverage_in=coverage_in, cache_ttl=cache_ttl)

    # (2) primary 取得。停止/失敗は exit 1 (fetch失敗) だが outputs は書いて監査可能にする。
    primary_failed: str | None = None
    primary: FetchResult | None = None
    try:
        budget.ensure("requests", "pages")
        primary, _snap = run_state.fetch(args.url, is_page=True)
    except StopFetching as stop:
        run_state.stopped = {"reason": stop.reason, "detail": stop.detail, "phase": "primary"}
        primary_failed = f"primary fetch stopped ({stop.reason}): {stop.detail}"
    if primary is None and primary_failed is None:
        # same_origin_redirects_only 拒否: 本文の無い primary は取得失敗として exit 1 (fail-closed)。
        gap = run_state.observation_gaps[-1]
        primary_failed = f"primary fetch blocked (cross-origin-redirect-blocked): {gap['redirect_target']}"

    # (3) discovery + asset snapshot (primary 成功時のみ・停止は graceful)。
    if primary is not None and run_state.stopped is None:
        if args.discover_urls:
            run_state.discover(primary)
        if not args.no_assets and run_state.stopped is None:
            run_state.fetch_assets(primary, args.max_assets)

    # (4) outputs を書き出す。
    result = _emit_outputs(args, run_state, evidence, budget, decision, primary_failed)

    if primary_failed:
        return 1, result
    return 0, result


def _emit_outputs(args: argparse.Namespace, run_state: Run, evidence: dict, budget: Budget,
                  decision: str, primary_failed: str | None) -> dict:
    out_dir = run_state.out_dir
    out_dir.mkdir(parents=True, exist_ok=True)

    discovered_list = sorted(run_state.discovered.values(), key=lambda e: e["url"])
    discovered_doc = {
        "schema_version": SCHEMA_VERSION,
        "target_url": run_state.url,
        "target_origin": run_state.origin,
        "generated_at": _iso(_now()),
        "counts": {
            "discovered": len(discovered_list),
            "same_origin": sum(1 for e in discovered_list if e["same_origin"]),
            "external": sum(1 for e in discovered_list if not e["same_origin"]),
        },
        "discovered": discovered_list,
    }
    discovered_path = _write_json(Path(args.discovered_urls_out) if args.discovered_urls_out
                                  else out_dir / "discovered-urls.json", discovered_doc)

    security_path = _write_json(out_dir / "security-facts.json", {
        "schema_version": SCHEMA_VERSION,
        "target_origin": run_state.origin,
        "generated_at": _iso(_now()),
        "facts": run_state.security,
    })

    ledger_doc = {
        "schema_version": SCHEMA_VERSION,
        "origin": run_state.origin,
        "crawl_mode": budget.crawl_mode,
        "generated_at": _iso(_now()),
        "budget_reset_on_retry": budget.reset_on_retry,
        "consumed_this_run": budget.consumed,
        "cumulative": budget.cumulative_ledger(),
        "remaining_after": dict(budget.remaining),
        "retries_used": run_state.fetcher.retries_used,
        "network_requests": run_state.fetcher.network_requests,
        "events": run_state.events,
        "stopped": run_state.stopped,
    }
    ledger_path = _write_json(out_dir / "request-ledger.json", ledger_doc)

    snapshot_index_path = _write_json(out_dir / "snapshot-index.json", {
        "schema_version": SCHEMA_VERSION,
        "target_url": run_state.url,
        "snapshots": run_state.snapshots,
        "observation_gaps": run_state.observation_gaps,
    })

    static_observation = run_state.build_static_observation()
    static_observation_path = _write_json(out_dir / "static-observation.json", static_observation)

    coverage_out_path = None
    if args.coverage_manifest_out:
        coverage_out_path = _write_json(Path(args.coverage_manifest_out),
                                        _build_coverage_out(run_state, evidence, budget))

    return {
        "url": run_state.url,
        "origin": run_state.origin,
        "authorized": decision == "allow",
        "decision": decision,
        "snapshot_count": len(run_state.snapshots),
        "observation_gap_count": len(run_state.observation_gaps),
        "snapshot_index": snapshot_index_path,
        "static_observation": static_observation_path,
        "static_page_count": static_observation["page_count"],
        "request_ledger": ledger_path,
        "discovered_urls": discovered_path,
        "discovered_count": len(discovered_list),
        "security_facts": security_path,
        "coverage_manifest_out": coverage_out_path,
        "stopped": run_state.stopped,
        "primary_failed": primary_failed,
    }


def _build_coverage_out(run_state: Run, evidence: dict, budget: Budget) -> dict:
    """次 run の C12 が resume に使う coverage manifest を組む。

    request_ledger[origin] は cumulative (prior+this run)、evidence は cache 再利用用、
    snapshots は cache 再利用用の索引 (prior と今 run を url でマージ) を持つ。
    """
    coverage = run_state.coverage_in
    prior_run_index = _safe_int(coverage.get("run_index"), 0)
    prior_covered = coverage.get("covered") if isinstance(coverage.get("covered"), list) else []

    ledger = coverage.get("request_ledger")
    ledger = dict(ledger) if isinstance(ledger, dict) else {}
    ledger[run_state.origin] = budget.cumulative_ledger()

    snapshots_index = dict(run_state._prior_snapshots)
    for snap in run_state.snapshots:
        snapshots_index[snap["url"]] = {
            "fetched_at": snap["fetched_at"],
            "http_status": snap.get("http_status"),
            "body_sha256": snap.get("body_sha256"),
            "body_path": snap.get("body_path"),
            "headers": snap.get("headers", {}),
            "set_cookie": snap.get("set_cookie", []),
            "truncated": snap.get("truncated", False),
        }

    covered = list(dict.fromkeys([str(u) for u in prior_covered] + run_state.covered))
    discovered_urls = sorted(run_state.discovered.keys())

    return {
        "schema_version": SCHEMA_VERSION,
        "target_url": run_state.url,
        "target_origin": run_state.origin,
        "crawl_mode": budget.crawl_mode,
        "generated_at": _iso(_now()),
        "run_index": prior_run_index + 1,
        "request_ledger": ledger,
        "covered": covered,
        "pending": coverage.get("pending", []) if isinstance(coverage.get("pending"), list) else [],
        "evidence": evidence,
        "snapshots": snapshots_index,
        "discovered": discovered_urls,
        "stopped": run_state.stopped,
    }


def main(argv: list[str] | None = None) -> int:
    argv = list(sys.argv[1:] if argv is None else argv)
    if "--self-test" in argv:
        return _self_test()
    try:
        rc, result = run(argv)
    except UsageError as exc:
        sys.stderr.write(f"usage: {exc}\n")
        return 2
    except AuthzDenied as exc:
        sys.stderr.write(f"authz-denied: {exc}\n")
        return 1
    except SystemExit as exc:  # argparse
        return 2 if exc.code not in (0, None) else int(exc.code or 0)
    except (OSError, ValueError) as exc:
        sys.stderr.write(f"fetch-error: {exc}\n")
        return 1
    sys.stdout.write(json.dumps(result, ensure_ascii=False, indent=2) + "\n")
    return rc


# ---------------------------------------------------------------------------
# 内蔵スモークテスト (network なし・一時 fixture)
# ---------------------------------------------------------------------------
def _self_test() -> int:
    import tempfile

    if _AUTHZ is None:
        sys.stderr.write(f"self-test: authz module (C12) を読み込めない: {_AUTHZ_PATH}\n")
        return 1

    failures: list[str] = []
    total = 0

    def check(label: str, cond: bool, detail: str = "") -> None:
        nonlocal total
        total += 1
        mark = "ok" if cond else "FAIL"
        if not cond:
            failures.append(f"{label}: {detail}")
        sys.stdout.write(f"  [{mark}] {label}{(' — ' + detail) if (detail and not cond) else ''}\n")

    workdir = Path(tempfile.mkdtemp(prefix="esb-fetch-selftest-"))
    url = "https://example.com/"
    origin = "https://example.com"

    allow_policy = {
        "robots": {
            "http_status": 200,
            "target_path_allowed": True,
            "crawl_delay_ms": 0,
            "raw_excerpt": "User-agent: *\nAllow: /\nSitemap: https://example.com/sitemap.xml",
        }
    }
    evidence, _req = _AUTHZ.build_authz_evidence(url, origin, allow_policy, offline=True, cached_evidence=None)
    dec, rea = _AUTHZ.decide(evidence, allow_policy)
    evidence["decision"], evidence["decision_reason"] = dec, rea
    budget = _AUTHZ.build_budget(origin, "single", allow_policy, evidence, None, dec == "allow")

    def write(path: Path, obj) -> str:
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(json.dumps(obj, ensure_ascii=False, indent=2), encoding="utf-8")
        return path.as_posix()

    ev_path = write(workdir / "evidence.json", evidence)
    bg_path = write(workdir / "budget.json", budget)

    html_body = (
        "<html lang='ja'><head>"
        "<title>Acme</title>"
        "<meta name='generator' content='AcmeCMS'>"
        "<meta property='og:title' content='Acme Home'>"
        "<link rel='stylesheet' href='/style.css'>"
        "<link rel='icon' href='/favicon.ico'>"
        "<script src='/app.js'></script>"
        "<style>body{background:#ffffff;color:#111;font-family:Inter, sans-serif}</style>"
        "</head><body>"
        "<h1 style='color:#FF0000'>Welcome</h1>"
        "<a href='/about'>about</a>"
        "<a href='/pricing'>pricing</a>"
        "<a href='https://twitter.com/acme'>social</a>"
        "<form action='/submit' method='post'><input type='email' name='e' required></form>"
        "<img src='/logo.png' alt='logo'>"
        "</body></html>"
    )
    fixtures = {
        url: {"status": 200, "headers": {
            "content-type": "text/html; charset=utf-8",
            "strict-transport-security": "max-age=63072000",
            "content-security-policy": "default-src 'self'",
            "x-frame-options": "DENY",
        }, "set_cookie": ["sid=abc; Secure; HttpOnly; SameSite=Lax"], "body": html_body},
        "https://example.com/sitemap.xml": {"status": 200, "headers": {"content-type": "application/xml"},
                                            "body": "<urlset><url><loc>https://example.com/pricing</loc></url>"
                                                    "<url><loc>https://example.com/contact</loc></url></urlset>"},
        "https://example.com/style.css": {"status": 200, "headers": {"content-type": "text/css"}, "body": "body{}"},
        "https://example.com/app.js": {"status": 200, "headers": {"content-type": "text/javascript"}, "body": "1;"},
        "https://example.com/logo.png": {"status": 200, "headers": {"content-type": "image/png"}, "body": "PNG"},
    }
    fx_path = write(workdir / "fixtures.json", fixtures)

    def invoke(extra: list[str], out_sub: str) -> tuple[int, dict]:
        out_dir = workdir / out_sub
        argv = ["--url", url, "--out-dir", out_dir.as_posix(),
                "--authz-evidence", ev_path, "--request-budget", bg_path,
                "--fixture-map", fx_path] + extra
        try:
            rc, res = run(argv)
        except AuthzDenied:
            return 1, {}
        except (UsageError, ValueError, OSError):
            return 2, {}
        return rc, res

    # (1) allow + discover + assets → exit 0, snapshot/discovery/security 揃う
    rc, res = invoke(["--discover-urls", "--coverage-manifest-out", (workdir / "cov1.json").as_posix()], "run1")
    check("allow primary+discover → exit 0", rc == 0, f"rc={rc}")
    check("primary snapshot 取得", res.get("snapshot_count", 0) >= 1, str(res.get("snapshot_count")))
    check("discovery: sitemap+link 台帳化", res.get("discovered_count", 0) >= 4, str(res.get("discovered_count")))
    ledger = json.loads(Path(res["request_ledger"]).read_text())
    check("budget 消費を ledger 記録", ledger["consumed_this_run"]["requests"] >= 1, str(ledger["consumed_this_run"]))
    sec = json.loads(Path(res["security_facts"]).read_text())["facts"]
    primary_sec = next((f for f in sec if f["url"].rstrip("/") == url.rstrip("/")), None)
    check("security fact: HSTS/CSP/cookie 属性", bool(primary_sec) and primary_sec["hsts"] is not None
          and primary_sec["set_cookies"] and primary_sec["set_cookies"][0]["secure"], str(primary_sec))
    disc = json.loads(Path(res["discovered_urls"]).read_text())
    ext = [e for e in disc["discovered"] if not e["same_origin"]]
    check("discovery: external link も台帳へ (C12 が分類)", any("twitter.com" in e["url"] for e in ext), str(ext))

    # (1b) 静的観測 ("ブラウザ確認" の stdlib 実装): DOM/見出し/form/宣言色 fact + レンダリング gap
    so = json.loads(Path(res["static_observation"]).read_text())
    p0 = so["pages"][0] if so.get("pages") else {}
    check("static観測: primary を DOM 静的解析 (h1 採取)",
          so.get("page_count", 0) >= 1 and any(h["level"] == 1 for h in p0.get("headings", [])),
          str(so.get("page_count")))
    check("static観測: form/input 採取",
          any(f["action"] == "/submit" and any(i["name"] == "e" and i["required"] for i in f["inputs"])
              for f in p0.get("forms", [])),
          str(p0.get("forms")))
    check("static観測: 宣言色/font トークン (inline+style block)",
          any(c["canonical_hex8"] == "#ff0000ff" for c in so["declared_tokens"]["colors"])
          and any("Inter" in f["family"] for f in so["declared_tokens"]["fonts"]),
          str(so["declared_tokens"]))
    check("static観測: レンダリング必須は gap(blocked) 明示",
          any(g["category"] == "screenshot" and g["observation_status"] == "blocked"
              for g in so.get("rendering_gaps", [])),
          str([g["category"] for g in so.get("rendering_gaps", [])]))

    # (2) deny evidence → exit 1 (取得を始めない)
    deny_policy = {"robots": {"http_status": 200, "target_path_allowed": False, "raw_excerpt": "Disallow: /"}}
    deny_ev, _ = _AUTHZ.build_authz_evidence(url, origin, deny_policy, offline=True, cached_evidence=None)
    d_dec, d_rea = _AUTHZ.decide(deny_ev, deny_policy)
    deny_ev["decision"], deny_ev["decision_reason"] = d_dec, d_rea
    deny_ev_path = write(workdir / "deny-ev.json", deny_ev)
    rc_deny, _ = run_capture(["--url", url, "--out-dir", (workdir / "deny").as_posix(),
                              "--authz-evidence", deny_ev_path, "--request-budget", bg_path,
                              "--fixture-map", fx_path])
    check("deny evidence → exit 1", rc_deny == 1, f"rc={rc_deny}")

    # (3) 期限切れ evidence → exit 1
    expired = dict(evidence)
    expired["expires_at"] = "2000-01-01T00:00:00Z"
    exp_path = write(workdir / "expired-ev.json", expired)
    rc_exp, _ = run_capture(["--url", url, "--out-dir", (workdir / "exp").as_posix(),
                             "--authz-evidence", exp_path, "--request-budget", bg_path,
                             "--fixture-map", fx_path])
    check("期限切れ evidence → exit 1", rc_exp == 1, f"rc={rc_exp}")

    # (4) 予算枯渇 (remaining.requests=0) → exit 1 (primary 前に停止)
    exhausted = json.loads(json.dumps(budget))
    exhausted["remaining"]["requests"] = 0
    exh_path = write(workdir / "exh-budget.json", exhausted)
    rc_exh, res_exh = run_capture(["--url", url, "--out-dir", (workdir / "exh").as_posix(),
                                   "--authz-evidence", ev_path, "--request-budget", exh_path,
                                   "--fixture-map", fx_path])
    check("予算枯渇 → exit 1", rc_exh == 1, f"rc={rc_exh}")

    # (5) primary 403 → exit 1, stop reason 403
    fx403 = dict(fixtures)
    fx403[url] = {"status": 403, "headers": {}, "body": "forbidden"}
    fx403_path = write(workdir / "fx403.json", fx403)
    rc403, res403 = run_capture(["--url", url, "--out-dir", (workdir / "f403").as_posix(),
                                 "--authz-evidence", ev_path, "--request-budget", bg_path,
                                 "--fixture-map", fx403_path])
    stop403 = (res403 or {}).get("stopped") or {}
    check("primary 403 → exit 1 + stop=403", rc403 == 1 and stop403.get("reason") == "403", f"rc={rc403} stop={stop403}")

    # (6) discovery 中 429 → graceful (primary 成功なので exit 0)、stopped 記録
    fx429 = dict(fixtures)
    fx429["https://example.com/sitemap.xml"] = {"status": 429, "headers": {"retry-after": "99999"}, "body": ""}
    fx429_path = write(workdir / "fx429.json", fx429)
    rc429, res429 = run_capture(["--url", url, "--out-dir", (workdir / "f429").as_posix(),
                                 "--authz-evidence", ev_path, "--request-budget", bg_path,
                                 "--discover-urls", "--no-assets", "--fixture-map", fx429_path])
    stop429 = (res429 or {}).get("stopped") or {}
    check("discovery 429 → graceful exit 0 + stopped", rc429 == 0 and stop429.get("reason") == "429",
          f"rc={rc429} stop={stop429}")

    # (7) cache 再利用: cov1 を coverage-in に渡すと primary は from_cache・budget 非消費
    rc_cache, res_cache = run_capture(["--url", url, "--out-dir", (workdir / "cache").as_posix(),
                                       "--authz-evidence", ev_path, "--request-budget", bg_path,
                                       "--coverage-manifest-in", (workdir / "cov1.json").as_posix(),
                                       "--fixture-map", fx_path, "--no-assets"])
    if rc_cache == 0 and res_cache:
        led_cache = json.loads(Path(res_cache["request_ledger"]).read_text())
        cache_events = [e for e in led_cache["events"] if e.get("action") == "cache_hit"]
        check("cache 再利用: primary from_cache・request 非消費",
              bool(cache_events) and led_cache["consumed_this_run"]["requests"] == 0,
              f"consumed={led_cache['consumed_this_run']}")
    else:
        check("cache 再利用: primary from_cache・request 非消費", False, f"rc={rc_cache}")

    # (8) multi-run resume: cov1 の cumulative ledger が持ち越される
    rc_res, res_res = run_capture(["--url", "https://example.com/pricing",
                                   "--out-dir", (workdir / "resume").as_posix(),
                                   "--authz-evidence", _rewrite_evidence(workdir, "https://example.com/pricing", origin, allow_policy),
                                   "--request-budget", _rewrite_budget(workdir, origin, allow_policy, "cov1.json"),
                                   "--coverage-manifest-in", (workdir / "cov1.json").as_posix(),
                                   "--coverage-manifest-out", (workdir / "cov2.json").as_posix(),
                                   "--fixture-map", _pricing_fixture(workdir, fixtures)])
    if rc_res == 0:
        cov2 = json.loads((workdir / "cov2.json").read_text())
        led = cov2["request_ledger"][origin]
        cov1 = json.loads((workdir / "cov1.json").read_text())
        led1 = cov1["request_ledger"][origin]
        check("multi-run resume: cumulative ledger 単調増加",
              led["requests"] > led1["requests"] and cov2["run_index"] == cov1["run_index"] + 1,
              f"run1={led1['requests']} run2={led['requests']}")
    else:
        check("multi-run resume: cumulative ledger 単調増加", False, f"rc={rc_res}")

    # (9) C12 との schema 往復: cov2 を C12 が読み remaining を派生できる (drift 検出)
    check("C12 shared decide が allow を返す", _AUTHZ.decide(evidence, {})[0] == "allow")

    # (10) cross-origin redirect (www サブドメイン含む) → 追従拒否 + observation_gap + 本文非保存
    fx_red = dict(fixtures)
    fx_red[url] = {"status": 301, "headers": {"location": "https://www.example.com/"}, "body": ""}
    fx_red_path = write(workdir / "fx-redirect.json", fx_red)
    rc_red, res_red = run_capture(["--url", url, "--out-dir", (workdir / "redirect").as_posix(),
                                   "--authz-evidence", ev_path, "--request-budget", bg_path,
                                   "--no-assets", "--fixture-map", fx_red_path])
    idx_red = json.loads(Path(res_red["snapshot_index"]).read_text()) if res_red else {}
    gaps = idx_red.get("observation_gaps") or []
    check("cross-origin redirect → 拒否 + observation_gap + 本文非保存",
          rc_red == 1 and len(gaps) == 1
          and gaps[0]["reason"] == "cross-origin-redirect-blocked"
          and gaps[0]["redirect_origin"] == "https://www.example.com"
          and res_red.get("snapshot_count") == 0
          and not (workdir / "redirect" / "bodies").exists(),
          f"rc={rc_red} gaps={gaps}")

    # (11) 同一 origin redirect → 従来どおり追従して成功
    fx_same = dict(fixtures)
    fx_same[url] = {"status": 302, "headers": {"location": "/home"}, "body": ""}
    fx_same["https://example.com/home"] = {"status": 200, "headers": {"content-type": "text/html"},
                                           "body": "<html><body>home</body></html>"}
    fx_same_path = write(workdir / "fx-same-redirect.json", fx_same)
    rc_same, res_same = run_capture(["--url", url, "--out-dir", (workdir / "same-redirect").as_posix(),
                                     "--authz-evidence", ev_path, "--request-budget", bg_path,
                                     "--no-assets", "--fixture-map", fx_same_path])
    idx_same = json.loads(Path(res_same["snapshot_index"]).read_text()) if res_same else {}
    snaps_same = idx_same.get("snapshots") or []
    check("same-origin redirect → 追従して snapshot 取得",
          rc_same == 0 and len(snaps_same) == 1
          and snaps_same[0]["final_url"] == "https://example.com/home"
          and not (idx_same.get("observation_gaps") or []),
          f"rc={rc_same} snaps={[(s.get('url'), s.get('final_url')) for s in snaps_same]}")

    sys.stdout.write(
        f"\nself-test: {'PASS' if not failures else 'FAIL'} ({total - len(failures)}/{total} ケース緑)\n"
    )
    for line in failures:
        sys.stdout.write(f"  - {line}\n")
    return 0 if not failures else 1


def run_capture(argv: list[str]) -> tuple[int, dict]:
    """self-test 補助: run() を例外を吸収して (rc, result) で返す。"""
    try:
        return run(argv)
    except AuthzDenied:
        return 1, {}
    except (UsageError, ValueError, OSError):
        return 2, {}


def _rewrite_evidence(workdir: Path, url: str, origin: str, policy: dict) -> str:
    ev, _ = _AUTHZ.build_authz_evidence(url, origin, policy, offline=True, cached_evidence=None)
    d, r = _AUTHZ.decide(ev, policy)
    ev["decision"], ev["decision_reason"] = d, r
    p = workdir / "resume-ev.json"
    p.write_text(json.dumps(ev, ensure_ascii=False), encoding="utf-8")
    return p.as_posix()


def _rewrite_budget(workdir: Path, origin: str, policy: dict, coverage_name: str) -> str:
    coverage = json.loads((workdir / coverage_name).read_text())
    ev, _ = _AUTHZ.build_authz_evidence("https://example.com/pricing", origin, policy, offline=True, cached_evidence=None)
    d, _r = _AUTHZ.decide(ev, policy)
    budget = _AUTHZ.build_budget(origin, "single", policy, ev, coverage, d == "allow")
    p = workdir / "resume-budget.json"
    p.write_text(json.dumps(budget, ensure_ascii=False), encoding="utf-8")
    return p.as_posix()


def _pricing_fixture(workdir: Path, fixtures: dict) -> str:
    fx = dict(fixtures)
    fx["https://example.com/pricing"] = {"status": 200, "headers": {"content-type": "text/html"},
                                         "body": "<html><body><a href='/about'>a</a></body></html>"}
    p = workdir / "pricing-fixtures.json"
    p.write_text(json.dumps(fx, ensure_ascii=False), encoding="utf-8")
    return p.as_posix()


if __name__ == "__main__":
    raise SystemExit(main())
