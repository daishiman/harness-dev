#!/usr/bin/env python3
# /// script
# name: authz-classify
# purpose: 対象URLの限定preflightでAuthzEvidence(robots応答/ToS判断根拠/認証要否/rate policy/取得時刻/policy version/ttl)を固定しallow|deny|unknownを判定、origin単位のrequest/byte/page budget(再試行非リセット)を発行、発見URLをin_scope/excluded+reasonへfail-closed分類しsingle|full_siteのcrawl_profile(瞬間負荷レバー不変・per-run有界・multi-run resume)を発行する安全ポリシーSSOT
# inputs:
#   - argv: --url URL --evidence-out FILE --budget-out FILE [--operator-policy FILE] [--crawl-mode single|full_site] [--discovered-urls FILE] [--coverage-manifest-in FILE] [--scope-manifest-out FILE]
# outputs:
#   - stdout: JSON {decision: allow|deny|unknown, authorized, origin, evidence_out, budget_out, scope_manifest_out}
#   - stderr: usage / policy-evidence-error
#   - exit: 0=allow / 1=deny(認可外: deny|unknown|根拠不在|期限切れ) / 2=usage
# contexts: [C, E]
# network: true
# write-scope: PLAN成果物ディレクトリ配下のAuthzEvidence/request-budget/scope-manifestのみ
# dependencies: []
# requires-python: ">=3.10"
# ///
"""authz-classify — extract-system-blueprint の取得前 安全ポリシー SSOT。

このスクリプトは C08(pre-fetch guard)/C09(fetch-snapshot)/C03(frontend analyzer)が
取得を始める前に必ず一度だけ通す関門である。3つの責務を1回の起動で果たす:

1. AuthzEvidence の固定と allow|deny|unknown 判定 (fail-closed)。
   限定 preflight(最大 ``preflight_max_requests`` リクエスト)で robots 応答・ToS 判断根拠・
   認証要否・rate policy・取得時刻・policy version・ttl を証跡へ固定し、根拠不在/期限切れ/
   unknown は deny する。

2. origin 単位の request-budget 発行。
   request/byte/page と総 origin byte 上限を持ち、再試行では
   リセットしない(``budget_reset_on_retry: false``)。coverage-manifest の ledger に消費が
   記録されていれば remaining = limits − consumed を導出する。

3. サイト全域被覆の scope 分類 SSOT と crawl_profile 発行。
   C09 が発見した URL 群を same-origin/承認済み related origin = in_scope、
   アフィリエイト/広告/外部SNS/トラッカー/utm付き外部リンク = excluded(reason 付き)へ
   fail-closed 分類(判定不能=excluded)し、single(既定=入口周辺)と full_site(全 in-scope 被覆)
   の crawl_profile を発行する。full_site でも瞬間負荷レバー(origin 並列1・最小間隔2000ms・
   Retry-After 尊重・有界 backoff・stop 条件)は一切緩めず、per-run 有界予算と multi-run resume で
   複数実行に分割して全 URL へ到達する。

ネットワークアクセスは preflight の robots 取得のみ。``--operator-policy`` に robots stub か
``offline: true`` を与えればネットワーク無しでも決定論的に走る(CI/オフライン fixture 用)。
DEFAULT_POLICY はこのスクリプトに焼き込まれた不変の安全ポリシーで、operator-policy が
override できるのは related_origins・per-run 予算(ユーザー承認付き)・stub 用の証跡素材に限る。
瞬間負荷レバーと budget 上限は operator-policy でも緩められない。
"""
from __future__ import annotations

import argparse
import json
import sys
import urllib.error
import urllib.request
import urllib.robotparser
from datetime import datetime, timedelta, timezone
from pathlib import Path
from urllib.parse import urlsplit

SCHEMA_VERSION = "1.0.0"
DEFAULT_POLICY_VERSION = "esb-authz-1.0.0"
USER_AGENT = "extract-system-blueprint-authz/1.0"
PREFLIGHT_TIMEOUT_SECONDS = 10

# ---------------------------------------------------------------------------
# 焼き込みポリシー SSOT (component-inventory C12.load_policy と一致)。
# 瞬間負荷レバーと budget 上限は不変。operator-policy でも緩められない。
# ---------------------------------------------------------------------------
INSTANT_LOAD_LEVERS = {
    "max_concurrency_per_origin": 1,
    "min_interval_ms": 2000,
    "honor_retry_after": True,
    "backoff": {"initial_ms": 2000, "max_ms": 30000, "multiplier": 2.0, "bounded": True},
    "stop_conditions": [
        "budget_exhausted",
        "retry_after_exceeds_max_ms",
        "consecutive_errors>=3",
        "runtime_ceiling_reached",
    ],
    "unchanged_across_modes": True,
}

# single モード既定 runtime budget (静的 HTTP 取得のみ)。
SINGLE_RUNTIME = {
    "max_requests_per_origin": 30,
    "max_bytes": 10485760,          # 10 MiB
    "max_pages": 3,
}
# 総 origin byte 上限 = fetch byte。single のみ適用。
TOTAL_ORIGIN_BYTES_CEILING = SINGLE_RUNTIME["max_bytes"]  # 10 MiB

# full_site の per-run 予算(single のページ当たり密度からの導出値)。
FULL_SITE_PER_RUN = {
    "pages_per_run": 20,
    "requests_per_run": 200,           # 10 req/page × 20 頁
    "bytes_per_run": 33554432,         # 32 MiB
}
# 1 run の総 byte は fetch 床を超えない。
FULL_SITE_RUN_TOTAL_BYTES_MAX = FULL_SITE_PER_RUN["bytes_per_run"]

# request-budget.remaining の need→resource-key 写像 SSOT (crawl_mode 別)。
# build_budget が remaining へ書く実キーと一致させる唯一の定義。C08 hook (pre-fetch-authz-guard)
# など消費側はこの写像を import して共有し、budget schema 改名時に沈黙 mis-map しないようにする
# (写像の複製を各所へ焼き込まない)。
BUDGET_NEED_KEYS = {
    "single": {
        "request": "requests",
        "byte": "bytes",
        "page": "pages",
    },
    "full_site": {
        "request": "requests_per_run",
        "byte": "bytes_per_run",
        "page": "pages_per_run",
    },
}


def get_need_keys(crawl_mode: str) -> dict:
    """crawl_mode の need→remaining-key 写像を返す (未知 mode は single 既定・fail-closed)。"""
    return dict(BUDGET_NEED_KEYS.get(crawl_mode, BUDGET_NEED_KEYS["single"]))

PREFLIGHT_MAX_REQUESTS = 2
EVIDENCE_TTL_SECONDS = 86400
BUDGET_RESET_ON_RETRY = False
UPWARD_OVERRIDE_REQUIRES_USER_APPROVAL = True

# scope 分類のホスト系ヒューリスティクス(external を reason 付きで excluded)。
SOCIAL_HOST_MARKERS = (
    "facebook.com", "fb.com", "twitter.com", "x.com", "instagram.com", "linkedin.com",
    "youtube.com", "youtu.be", "tiktok.com", "pinterest.com", "threads.net", "reddit.com",
    "line.me", "note.com", "hatena.ne.jp", "t.co",
)
AD_HOST_MARKERS = (
    "doubleclick.net", "googlesyndication.com", "googleadservices.com", "adservice.google",
    "adnxs.com", "criteo.com", "taboola.com", "outbrain.com", "amazon-adsystem.com",
    "yads.c.yimg.jp", "ads.",
)
TRACKER_HOST_MARKERS = (
    "google-analytics.com", "googletagmanager.com", "analytics.", "hotjar.com",
    "segment.io", "segment.com", "mixpanel.com", "amplitude.com", "clarity.ms",
    "fullstory.com", "mouseflow.com", "matomo.", "newrelic.com", "sentry.io",
)
AFFILIATE_HOST_MARKERS = (
    "a8.net", "af.moshimo.com", "px.a8.net", "linksynergy.com", "rakuten-affiliate",
    "valuecommerce.com", "accesstrade.net", "amzn.to", "affiliate.",
)
UTM_PARAM_MARKERS = ("utm_source", "utm_medium", "utm_campaign", "utm_term", "utm_content", "gclid", "fbclid")


class UsageError(Exception):
    """argv/入力ファイル不正など、exit 2 (usage) に対応する回復不能な入力エラー。"""


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


def _load_json_file(path_str: str, label: str) -> dict | list:
    path = Path(path_str)
    if not path.is_file():
        raise UsageError(f"{label} not found: {path_str}")
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise UsageError(f"{label} is not valid JSON: {exc}")


def _write_json(path_str: str, obj: dict) -> str:
    path = Path(path_str)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(obj, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    return path.as_posix()


def _origin_of(url: str) -> str | None:
    """scheme://host[:port] を返す。scheme か host が無ければ None (fail-closed)。"""
    try:
        parts = urlsplit(url)
    except ValueError:
        return None
    if parts.scheme not in ("http", "https") or not parts.hostname:
        return None
    host = parts.hostname.lower()
    if parts.port:
        return f"{parts.scheme}://{host}:{parts.port}"
    return f"{parts.scheme}://{host}"


def _host_of(url: str) -> str | None:
    try:
        host = urlsplit(url).hostname
    except ValueError:
        return None
    return host.lower() if host else None


# ---------------------------------------------------------------------------
# preflight + AuthzEvidence
# ---------------------------------------------------------------------------
def _fetch_robots(origin: str) -> dict:
    """robots.txt を1リクエストで取得する。副作用: ネットワーク。

    返り値は http_status(int|None)・text(str|None)・error(str|None)。呼び出し側で
    ステータスに応じ allow/restricted/no_robots/unknown を判定する。
    """
    url = origin.rstrip("/") + "/robots.txt"
    req = urllib.request.Request(url, headers={"User-Agent": USER_AGENT})
    try:
        with urllib.request.urlopen(req, timeout=PREFLIGHT_TIMEOUT_SECONDS) as resp:
            raw = resp.read(1_000_000)  # robots は小さい。上限で暴走防止。
            return {"http_status": resp.status, "text": raw.decode("utf-8", "replace"), "error": None}
    except urllib.error.HTTPError as exc:
        return {"http_status": exc.code, "text": None, "error": f"http {exc.code}"}
    except (urllib.error.URLError, OSError, ValueError) as exc:
        return {"http_status": None, "text": None, "error": str(exc)}


def _robots_evidence(origin: str, target_url: str, policy: dict, offline: bool) -> tuple[dict, int]:
    """robots 証跡を返す。(robots_dict, network_request_count)。

    operator-policy が robots stub を持つか offline なら network を触らない。それ以外は
    実 robots を1リクエストで取得する(preflight_max_requests=2 未満)。
    """
    stub = policy.get("robots") if isinstance(policy.get("robots"), dict) else None
    if stub is not None:
        allowed = stub.get("target_path_allowed")
        return (
            {
                "source": "operator_policy_stub",
                "http_status": stub.get("http_status"),
                "target_path_allowed": allowed,
                "crawl_delay_ms": stub.get("crawl_delay_ms"),
                "raw_excerpt": (stub.get("raw_excerpt") or "")[:2000],
                "status": _robots_status_from_allowed(allowed),
            },
            0,
        )
    if offline:
        # offline かつ stub 不在 = 証跡を固定できない → unknown (fail-closed で後段が deny)。
        return (
            {
                "source": "offline_no_stub",
                "http_status": None,
                "target_path_allowed": None,
                "crawl_delay_ms": None,
                "raw_excerpt": "",
                "status": "unknown",
            },
            0,
        )

    fetched = _fetch_robots(origin)
    status_code = fetched["http_status"]
    if status_code == 200 and fetched["text"] is not None:
        parser = urllib.robotparser.RobotFileParser()
        parser.parse(fetched["text"].splitlines())
        allowed = parser.can_fetch(USER_AGENT, target_url)
        delay = parser.crawl_delay(USER_AGENT)
        return (
            {
                "source": "network",
                "http_status": 200,
                "target_path_allowed": bool(allowed),
                "crawl_delay_ms": int(delay * 1000) if delay is not None else None,
                "raw_excerpt": fetched["text"][:2000],
                "status": "allow" if allowed else "restricted",
            },
            1,
        )
    if status_code in (401, 403):
        # robots 自体が要認証/禁止 = 制限あり扱い。
        return ({"source": "network", "http_status": status_code, "target_path_allowed": False,
                 "crawl_delay_ms": None, "raw_excerpt": "", "status": "restricted"}, 1)
    if status_code is not None and 400 <= status_code < 500:
        # 404/410 等 = robots 不在 = 制限なし (RFC 慣行: allow all)。
        return ({"source": "network", "http_status": status_code, "target_path_allowed": True,
                 "crawl_delay_ms": None, "raw_excerpt": "", "status": "no_robots"}, 1)
    # 5xx / タイムアウト / 接続不能 = 一時的に判定不能 → unknown。
    return ({"source": "network", "http_status": status_code, "target_path_allowed": None,
             "crawl_delay_ms": None, "raw_excerpt": "", "status": "unknown",
             "error": fetched.get("error")}, 1)


def _robots_status_from_allowed(allowed) -> str:
    if allowed is True:
        return "allow"
    if allowed is False:
        return "restricted"
    return "unknown"


def build_authz_evidence(url: str, origin: str, policy: dict, offline: bool,
                         cached_evidence: dict | None) -> tuple[dict, int]:
    """AuthzEvidence を固定し preflight リクエスト数を返す。

    cached_evidence(coverage-manifest 由来)が新鮮な間、offline かつ stub 不在なら再利用する。
    期限切れ再利用は後段の decide() が deny する。
    """
    now = _now()

    # offline かつ stub 不在で cached があれば再利用 (fail-closed: 期限は decide が検査)。
    stub_present = isinstance(policy.get("robots"), dict)
    if offline and not stub_present and cached_evidence:
        ev = dict(cached_evidence)
        ev["source"] = "reused_cached"
        ev["reused_at"] = _iso(now)
        return ev, 0

    robots, req_count = _robots_evidence(origin, url, policy, offline)

    tos = policy.get("tos") if isinstance(policy.get("tos"), dict) else {}
    tos_decision = str(tos.get("decision", "unknown")).lower()
    if tos_decision not in ("allow", "deny", "unknown"):
        tos_decision = "unknown"

    # 認証要否: operator 明示 > robots 401/403 > 既定 False。
    if "auth_required" in policy:
        auth_required = bool(policy["auth_required"])
    elif robots.get("http_status") in (401, 403):
        auth_required = True
    else:
        auth_required = False

    crawl_delay_ms = robots.get("crawl_delay_ms")
    effective_min_interval = max(INSTANT_LOAD_LEVERS["min_interval_ms"], crawl_delay_ms or 0)

    evidence = {
        "schema_version": SCHEMA_VERSION,
        "policy_version": str(policy.get("policy_version") or DEFAULT_POLICY_VERSION),
        "url": url,
        "origin": origin,
        "fetched_at": _iso(now),
        "ttl_seconds": EVIDENCE_TTL_SECONDS,
        "expires_at": _iso(now + timedelta(seconds=EVIDENCE_TTL_SECONDS)),
        "preflight_requests_used": req_count,
        "preflight_max_requests": PREFLIGHT_MAX_REQUESTS,
        "robots": robots,
        "tos": {"decision": tos_decision, "basis": str(tos.get("basis", "not_provided"))},
        "auth_required": auth_required,
        "rate_policy": {
            "min_interval_ms": effective_min_interval,
            "honor_retry_after": INSTANT_LOAD_LEVERS["honor_retry_after"],
            "max_concurrency_per_origin": INSTANT_LOAD_LEVERS["max_concurrency_per_origin"],
        },
        "source": robots.get("source", "network"),
    }
    return evidence, req_count


def decide(evidence: dict, policy: dict) -> tuple[str, str]:
    """evidence から allow|deny|unknown と理由を導く (fail-closed)。

    優先順位: 期限切れ deny > operator hard deny > robots 制限 deny > ToS deny >
    認証要求 deny > 証跡不在/unknown > operator allow(unknown のみ昇格) > allow。
    robots/ToS の deny は operator の allow override では覆せない(安全側)。
    """
    now = _now()
    expires = _parse_iso(evidence.get("expires_at", ""))
    if expires is not None and expires <= now:
        return "deny", "evidence_expired"

    override = str(policy.get("decision_override") or "").lower()
    if override == "deny":
        return "deny", "operator_decision_override_deny"

    robots = evidence.get("robots", {})
    robots_status = robots.get("status", "unknown")
    if robots_status == "restricted" or robots.get("target_path_allowed") is False:
        return "deny", "robots_disallow"

    if evidence.get("tos", {}).get("decision") == "deny":
        return "deny", "tos_prohibits"

    if evidence.get("auth_required") and not bool(policy.get("allow_auth_walled")):
        return "deny", "auth_required"

    # ここまで来ても robots が unknown(証跡固定できず)なら fail-closed。
    if robots_status == "unknown" or robots.get("target_path_allowed") is None:
        if override == "allow":
            return "allow", "operator_attested_allow_over_unknown"
        return "unknown", "evidence_unresolved"

    return "allow", "robots_and_tos_clear"


# ---------------------------------------------------------------------------
# request-budget 発行
# ---------------------------------------------------------------------------
def _ledger_for_origin(coverage: dict | None, origin: str) -> dict:
    if not isinstance(coverage, dict):
        return {}
    ledger = coverage.get("request_ledger")
    if isinstance(ledger, dict):
        entry = ledger.get(origin)
        if isinstance(entry, dict):
            return entry
    return {}


def _remaining(limit: int, consumed_key: str, ledger: dict) -> int:
    consumed = ledger.get(consumed_key, 0)
    try:
        consumed = int(consumed)
    except (TypeError, ValueError):
        consumed = 0
    return max(0, limit - max(0, consumed))


def build_budget(origin: str, crawl_mode: str, policy: dict, evidence: dict,
                 coverage: dict | None, authorized: bool) -> dict:
    """origin 単位 request-budget を発行する。

    ``budget_reset_on_retry: false`` を honor し、coverage の ledger に消費があれば
    remaining = limits − consumed を導出する(再試行で満額へ戻さない)。deny 時は
    granted=False で全 remaining=0 を発行し、path は必ず存在させる(監査可能に)。
    """
    ledger = _ledger_for_origin(coverage, origin)
    budget: dict = {
        "schema_version": SCHEMA_VERSION,
        "policy_version": evidence.get("policy_version", DEFAULT_POLICY_VERSION),
        "origin": origin,
        "crawl_mode": crawl_mode,
        "issued_at": _iso(_now()),
        "granted": bool(authorized),
        "evidence_ref": {"url": evidence.get("url"), "expires_at": evidence.get("expires_at")},
        "preflight_max_requests": PREFLIGHT_MAX_REQUESTS,
        "budget_reset_on_retry": BUDGET_RESET_ON_RETRY,
        "upward_override_requires_user_approval": UPWARD_OVERRIDE_REQUIRES_USER_APPROVAL,
        "instant_load_levers": INSTANT_LOAD_LEVERS,
    }

    if crawl_mode == "single":
        limits = dict(SINGLE_RUNTIME)
        budget["limits"] = limits
        budget["total_origin_bytes_ceiling"] = TOTAL_ORIGIN_BYTES_CEILING
        if authorized:
            # 総 origin byte 残量: ledger に total_bytes があれば優先、無ければ
            # fetch byte 消費を ceiling から引く (静的 HTTP のみ。browser 不使用のため
            # screenshot 予算は適用しない)。
            if "total_bytes" in ledger:
                total_bytes_remaining = _remaining(TOTAL_ORIGIN_BYTES_CEILING, "total_bytes", ledger)
            else:
                total_bytes_remaining = _remaining(TOTAL_ORIGIN_BYTES_CEILING, "bytes", ledger)
            budget["remaining"] = {
                "requests": _remaining(limits["max_requests_per_origin"], "requests", ledger),
                "bytes": _remaining(limits["max_bytes"], "bytes", ledger),
                "pages": _remaining(limits["max_pages"], "pages", ledger),
                "total_origin_bytes": total_bytes_remaining,
            }
    else:  # full_site
        per_run = dict(FULL_SITE_PER_RUN)
        per_run_note = None
        override = policy.get("per_run_override")
        if isinstance(override, dict):
            if override.get("approved_by_user") is True:
                for k in ("pages_per_run", "requests_per_run", "bytes_per_run"):
                    if isinstance(override.get(k), int) and override[k] > 0:
                        per_run[k] = override[k]
                per_run_note = "per_run_override applied (approved_by_user=true)"
            else:
                per_run_note = "per_run_override ignored: per_run_default_override_requires_user_approval"
        budget["limits"] = per_run
        budget["run_total_bytes_max"] = per_run["bytes_per_run"]
        budget["total_origin_bytes_ceiling"] = None  # full_site では適用しない
        budget["total_origin_bytes_ceiling_note"] = (
            "not applied in full_site; per-run budget governs. run total byte <= bytes_per_run"
        )
        budget["per_run_default_override_requires_user_approval"] = True
        if per_run_note:
            budget["per_run_override_note"] = per_run_note
        if authorized:
            budget["remaining"] = {
                "requests_per_run": _remaining(per_run["requests_per_run"], "requests", ledger),
                "pages_per_run": _remaining(per_run["pages_per_run"], "pages", ledger),
                "bytes_per_run": _remaining(per_run["bytes_per_run"], "bytes", ledger),
            }

    if not authorized:
        budget["remaining"] = {"denied": True}
    return budget


# ---------------------------------------------------------------------------
# scope 分類 + crawl_profile
# ---------------------------------------------------------------------------
def _normalize_origins(values) -> set[str]:
    out: set[str] = set()
    if isinstance(values, list):
        for v in values:
            o = _origin_of(str(v))
            if o:
                out.add(o)
    return out


def _has_utm(url: str) -> bool:
    lowered = url.lower()
    return any(marker in lowered for marker in UTM_PARAM_MARKERS)


def _host_matches(host: str, markers: tuple[str, ...]) -> bool:
    return any(marker in host for marker in markers)


def classify_url(url: str, target_origin: str, related_origins: set[str]) -> tuple[bool, str]:
    """1 URL を (in_scope: bool, reason: str) へ fail-closed 分類する。

    判定不能(parse 不能 / scheme・host 欠落)は excluded。same-origin と承認済み
    related origin のみ in_scope。それ以外の外部 origin は social/ad/tracker/affiliate/
    utm_external/external_origin の reason 付きで excluded。
    """
    origin = _origin_of(url)
    if origin is None:
        return False, "undecidable_unparseable"
    if origin == target_origin:
        return True, "same_origin"
    if origin in related_origins:
        return True, "approved_related_origin"
    host = _host_of(url) or ""
    if _host_matches(host, SOCIAL_HOST_MARKERS):
        return False, "external_social"
    if _host_matches(host, AD_HOST_MARKERS):
        return False, "external_ad"
    if _host_matches(host, TRACKER_HOST_MARKERS):
        return False, "external_tracker"
    if _host_matches(host, AFFILIATE_HOST_MARKERS):
        return False, "external_affiliate"
    if _has_utm(url):
        return False, "external_utm_link"
    return False, "external_origin"


def _extract_urls(raw) -> list[str]:
    """discovered-urls / coverage manifest から URL 文字列一覧を抽出する。

    受理する形: ["url", ...] / {"urls": [...]} / {"discovered": [...]} /
    [{"url": ...}, ...] / in_scope・pending が {url,reason} の配列。
    """
    urls: list[str] = []

    def add(item):
        if isinstance(item, str):
            urls.append(item)
        elif isinstance(item, dict) and isinstance(item.get("url"), str):
            urls.append(item["url"])

    if isinstance(raw, list):
        for it in raw:
            add(it)
    elif isinstance(raw, dict):
        for key in ("discovered", "discovered_urls", "urls", "pending", "in_scope", "unclassified"):
            seq = raw.get(key)
            if isinstance(seq, list):
                for it in seq:
                    add(it)
    return urls


def build_scope_manifest(target_url: str, target_origin: str, crawl_mode: str, policy: dict,
                         discovered_raw, coverage: dict | None) -> dict:
    """scope 分類結果 + crawl_profile + resume 状態を持つ manifest を組む。

    多重実行時は coverage-manifest-in の covered を除外し、pending ∪ 未分類 discovered を
    再投入して分類する。full_site は pending を pages_per_run で有界に this_run/deferred へ割る。
    """
    related = _normalize_origins(policy.get("related_origins"))

    covered: list[str] = []
    prior_pending: list[str] = []
    prior_ledger = None
    prior_run_index = 0
    if isinstance(coverage, dict):
        covered = [u for u in _extract_urls({"urls": coverage.get("covered", [])})]
        prior_pending = _extract_urls({"pending": coverage.get("pending", [])})
        prior_ledger = coverage.get("request_ledger")
        prior_run_index = coverage.get("run_index", 0) if isinstance(coverage.get("run_index"), int) else 0

    covered_set = set(covered)
    discovered = _extract_urls(discovered_raw) if discovered_raw is not None else []

    # 分類対象 = discovered ∪ prior_pending − covered。順序は安定(初出順)。
    candidates: list[str] = []
    seen: set[str] = set()
    for u in list(discovered) + list(prior_pending):
        if u in covered_set or u in seen:
            continue
        seen.add(u)
        candidates.append(u)

    in_scope: list[dict] = []
    excluded: list[dict] = []
    for u in candidates:
        keep, reason = classify_url(u, target_origin, related)
        (in_scope if keep else excluded).append({"url": u, "reason": reason})

    in_scope_urls = [e["url"] for e in in_scope]

    if crawl_mode == "single":
        # 入口周辺: 入口 URL + in_scope を max_pages で有界化。
        this_run: list[str] = []
        for u in [target_url] + in_scope_urls:
            if u not in this_run:
                this_run.append(u)
            if len(this_run) >= SINGLE_RUNTIME["max_pages"]:
                break
        deferred = [u for u in in_scope_urls if u not in this_run]
        profile = {
            "mode": "single",
            "instant_load_levers_unchanged": True,
            "max_pages": SINGLE_RUNTIME["max_pages"],
            "note": "既定=入口周辺。full_site は全 in-scope 被覆へ切替(--crawl-mode full_site)",
        }
    else:
        pages_per_run = FULL_SITE_PER_RUN["pages_per_run"]
        override = policy.get("per_run_override")
        if isinstance(override, dict) and override.get("approved_by_user") is True and isinstance(override.get("pages_per_run"), int):
            pages_per_run = max(1, override["pages_per_run"])
        this_run = in_scope_urls[:pages_per_run]
        deferred = in_scope_urls[pages_per_run:]
        profile = {
            "mode": "full_site",
            "instant_load_levers_unchanged": True,
            "pages_per_run": pages_per_run,
            "multi_run_resume": True,
            "resume_state": "site coverage manifest + request ledger + cache",
            "per_run_default_override_requires_user_approval": True,
            "note": "瞬間負荷レバー不変のまま複数 run に分割して全 in-scope URL へ到達する",
        }

    next_pending = deferred  # 今 run 未消化の in_scope は次 run へ持ち越し。
    manifest = {
        "schema_version": SCHEMA_VERSION,
        "policy_version": str(policy.get("policy_version") or DEFAULT_POLICY_VERSION),
        "target_url": target_url,
        "target_origin": target_origin,
        "crawl_mode": crawl_mode,
        "generated_at": _iso(_now()),
        "crawl_profile": profile,
        "in_scope": in_scope,
        "excluded": excluded,
        "counts": {"in_scope": len(in_scope), "excluded": len(excluded), "candidates": len(candidates)},
        "resume": {
            "multi_run_resume": crawl_mode == "full_site",
            "run_index": prior_run_index + 1,
            "covered": covered,
            "this_run": this_run,
            "pending": next_pending,
            "request_ledger": prior_ledger if isinstance(prior_ledger, dict) else {},
        },
    }
    return manifest


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------
def _parse_args(argv: list[str]) -> argparse.Namespace:
    ap = argparse.ArgumentParser(
        prog="authz-classify",
        description="取得前 安全ポリシー SSOT: AuthzEvidence 発行 + allow/deny/unknown 判定 + budget 発行 + scope 分類",
        add_help=True,
    )
    ap.add_argument("--url", required=True)
    ap.add_argument("--evidence-out", required=True)
    ap.add_argument("--budget-out", required=True)
    ap.add_argument("--operator-policy", default=None)
    ap.add_argument("--crawl-mode", choices=["single", "full_site"], default="single")
    ap.add_argument("--discovered-urls", default=None)
    ap.add_argument("--coverage-manifest-in", default=None)
    ap.add_argument("--scope-manifest-out", default=None)
    return ap.parse_args(argv)


def run(argv: list[str]) -> tuple[int, dict]:
    args = _parse_args(argv)

    origin = _origin_of(args.url)
    if origin is None:
        raise UsageError(f"--url must be an http(s) URL with a host: {args.url}")

    policy: dict = {}
    if args.operator_policy:
        loaded = _load_json_file(args.operator_policy, "--operator-policy")
        if not isinstance(loaded, dict):
            raise UsageError("--operator-policy root must be a JSON object")
        policy = loaded
    offline = bool(policy.get("offline"))

    coverage: dict | None = None
    if args.coverage_manifest_in:
        loaded = _load_json_file(args.coverage_manifest_in, "--coverage-manifest-in")
        if not isinstance(loaded, dict):
            raise UsageError("--coverage-manifest-in root must be a JSON object")
        coverage = loaded

    discovered_raw = None
    if args.discovered_urls:
        discovered_raw = _load_json_file(args.discovered_urls, "--discovered-urls")

    cached_evidence = coverage.get("evidence") if isinstance(coverage, dict) and isinstance(coverage.get("evidence"), dict) else None
    evidence, _req = build_authz_evidence(args.url, origin, policy, offline, cached_evidence)
    decision, reason = decide(evidence, policy)
    evidence["decision"] = decision
    evidence["decision_reason"] = reason
    authorized = decision == "allow"

    budget = build_budget(origin, args.crawl_mode, policy, evidence, coverage, authorized)

    evidence_path = _write_json(args.evidence_out, evidence)
    budget_path = _write_json(args.budget_out, budget)

    scope_path = None
    if args.scope_manifest_out:
        manifest = build_scope_manifest(args.url, origin, args.crawl_mode, policy, discovered_raw, coverage)
        scope_path = _write_json(args.scope_manifest_out, manifest)

    result = {
        "decision": decision,
        "authorized": authorized,
        "reason": reason,
        "origin": origin,
        "crawl_mode": args.crawl_mode,
        "policy_version": evidence["policy_version"],
        "evidence_out": evidence_path,
        "budget_out": budget_path,
        "scope_manifest_out": scope_path,
    }
    return (0 if authorized else 1), result


def main(argv: list[str] | None = None) -> int:
    argv = list(sys.argv[1:] if argv is None else argv)
    try:
        rc, result = run(argv)
    except UsageError as exc:
        sys.stderr.write(f"usage: {exc}\n")
        return 2
    except SystemExit as exc:  # argparse の --help / 引数不足
        return 2 if exc.code not in (0, None) else int(exc.code or 0)
    except (OSError, ValueError) as exc:
        sys.stderr.write(f"policy-evidence-error: {exc}\n")
        return 2
    sys.stdout.write(json.dumps(result, ensure_ascii=False, indent=2) + "\n")
    return rc


if __name__ == "__main__":
    raise SystemExit(main())
