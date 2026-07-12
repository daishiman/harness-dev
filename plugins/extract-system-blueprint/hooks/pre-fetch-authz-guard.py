#!/usr/bin/env python3
# /// script
# name: pre-fetch-authz-guard
# purpose: extract-system-blueprint の PreToolUse fail-closed 関門 (fetch-authz 単一述語)。対象 URL への
#          Bash/WebFetch フェッチ試行を C12(authz-classify) の AuthzEvidence と残予算 (request/byte/pages)
#          で照合し deny|unknown|期限切れ|予算超過なら exit2 遮断。非fetch は通過し、曖昧な入力は安全側
#          (deny) へ倒す。判定ロジックは C12 と同一モジュールを import して共有し重複実装しない。
#          run-scoping: ESB run 非アクティブ (ESB_RUN≠1 かつ .esb-authz 不在) 時は enforce せず exit0
#          素通し (co-install した兄弟 plugin を遮断しない)。
# inputs:
#   - stdin: Claude hook JSON (PreToolUse: {tool_name, tool_input})
#   - env: ESB_AUTHZ_DIR (AuthzEvidence/budget 置場) / CLAUDE_PROJECT_DIR (既定 .esb-authz 探索起点) /
#          ESB_RUN (run-scoping 明示宣言)
# outputs:
#   - stderr: BLOCK 理由 (deny/unknown/期限切れ/予算超過)
#   - exit: 0=許可 / 2=遮断(fail-closed)。stdin 解釈不能・曖昧入力も安全側で 2
# contexts: [C, E]
# network: false
# write-scope: none
# dependencies: []
# requires-python: ">=3.10"
# ///
"""PreToolUse fail-closed guard — 認可外・予算外フェッチを機械層で止める。

正本契約: plugin-plans/extract-system-blueprint/component-inventory.json の C08 エントリ
  (event=PreToolUse / matcher=`Bash|WebFetch` / exit_semantics=fail-closed-exit2 /
   単一述語=fetch-authz)。

判定ロジックの共有 (重複実装禁止・P08-x-02):
  取得可否 (allow|deny|unknown) と origin 単位 budget の意味づけは C12 (scripts/authz-classify.py)
  の SSOT である。本 hook は同スクリプトを importlib で読み込み ``decide()`` / ``_origin_of()`` /
  ``_host_of()`` を再利用する。C12 が書いた AuthzEvidence / request-budget JSON をそのまま
  読み、hook 側で allow/deny 規則を作り直さない (基準の乖離を防ぐ)。

状態ファイルの探索:
  C12 は AuthzEvidence を ``--evidence-out``、budget を ``--budget-out`` へ PLAN 成果物ディレクトリ
  配下に書く。本 hook は実行時に対象 origin へマップするため、以下の順で状態ディレクトリを探索し
  存在するものを全て走査する:
    1. env ``ESB_AUTHZ_DIR`` (evidence/budget)
    2. ``$CLAUDE_PROJECT_DIR/.esb-authz``
    3. ``$CWD/.esb-authz``
  evidence が無い origin へのフェッチは『認可の証跡が無い』=fail-closed で deny する。

fail-closed の一貫規律:
  取得可否を確定できない全ケース (証跡不在 / module 読込不能 / URL 解析不能 / budget 詳細欠落 /
  曖昧な tool 入力 / stdin 解釈不能) は exit2 で遮断する。明確に非fetch な操作 (URL を含まない
  Bash 等) だけを exit0 で通す。

run-scoping (co-install 副作用の除去):
  matcher (Bash|WebFetch) は session-global に発火するため、ESB run 外の正当な操作 (兄弟 plugin の
  外部 URL fetch) まで証跡不在=deny で遮断してしまう。そこで ESB run がアクティブなときだけ
  fetch-authz を enforce し、非アクティブ時は exit0 で素通しする。アクティブ判定は
  ``_esb_run_active()`` (env ESB_RUN=1 / ESB_AUTHZ_DIR の明示設定、または既定探索順での
  .esb-authz ディレクトリ発見) で行う。これは enforce スコープの切替のみで、アクティブ時の
  fail-closed 規律 (unknown→deny 等) は一切変えない。
"""
from __future__ import annotations

import importlib.util
import json
import os
import re
import sys
from pathlib import Path
from urllib.parse import urlsplit

# ---------------------------------------------------------------------------
# C12 (authz-classify.py) を共有モジュールとして import。ハイフン名なので
# spec_from_file_location で読み込む。読込不能なら fetch 評価は
# fail-closed で deny する (evaluation logic を再実装しない)。
# ---------------------------------------------------------------------------
_HOOK_DIR = Path(__file__).resolve().parent
_PLUGIN_ROOT = _HOOK_DIR.parent
_AUTHZ_PATH = _PLUGIN_ROOT / "scripts" / "authz-classify.py"


def _load_authz_module():
    try:
        spec = importlib.util.spec_from_file_location("esb_authz_classify", _AUTHZ_PATH)
        if spec is None or spec.loader is None:
            return None
        module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(module)
        # 消費する共有 API が存在するか最小確認 (schema/契約 drift の早期検出)。
        # get_need_keys = budget need→remaining-key 写像の SSOT。欠落は写像 drift = fail-closed。
        for attr in ("decide", "_origin_of", "_host_of", "get_need_keys"):
            if not hasattr(module, attr):
                return None
        return module
    except Exception:  # noqa: BLE001 — import 失敗は理由不問で共有不能とみなす
        return None


_AUTHZ = _load_authz_module()

# tool 名の分類パターン。
_URL_RE = re.compile(r"https?://[^\s'\"<>`\\|)]+")

# request-budget.remaining の need→resource-key 写像は C12 (authz-classify) の
# BUDGET_NEED_KEYS / get_need_keys() が SSOT。ここで複製せず _AUTHZ.get_need_keys() を使う。

_LOCAL_HOSTS = {"localhost", "127.0.0.1", "0.0.0.0", "::1", "[::1]"}


# ---------------------------------------------------------------------------
# URL / host ユーティリティ (parse は共有 module 優先・fallback は stdlib)。
# ---------------------------------------------------------------------------
def _origin(url: str) -> str | None:
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


def _host(url: str) -> str | None:
    if _AUTHZ is not None:
        return _AUTHZ._host_of(url)
    try:
        host = urlsplit(url).hostname
    except ValueError:
        return None
    return host.lower() if host else None


def _is_local_host(host: str) -> bool:
    if not host:
        return False
    if host in _LOCAL_HOSTS or host.endswith(".local"):
        return True
    return host.startswith(("192.168.", "10.", "127.")) or host.startswith(("172.16.", "172.17.", "172.18.", "172.19."))


def _extract_url(tool_input: object) -> str | None:
    """tool_input から最初の http(s) URL を取り出す (直下キー→ネスト→文字列走査)。"""
    if not isinstance(tool_input, dict):
        return None
    for key in ("url", "uri", "href", "target", "address", "location"):
        val = tool_input.get(key)
        if isinstance(val, str) and val.startswith(("http://", "https://")):
            return val
    for val in tool_input.values():
        if isinstance(val, dict):
            got = _extract_url(val)
            if got:
                return got
        elif isinstance(val, str):
            match = _URL_RE.search(val)
            if match:
                return match.group(0)
    return None


# ---------------------------------------------------------------------------
# 状態ファイル (AuthzEvidence / budget) の探索・読込。
# ---------------------------------------------------------------------------
def _candidate_dirs(env_key: str, leaf: str) -> list[Path]:
    dirs: list[Path] = []
    seen: set[str] = set()

    def add(path: Path) -> None:
        key = str(path)
        if key not in seen:
            seen.add(key)
            dirs.append(path)

    env = os.environ.get(env_key)
    if env:
        add(Path(env))
    proj = os.environ.get("CLAUDE_PROJECT_DIR")
    if proj:
        add(Path(proj) / leaf)
    add(Path.cwd() / leaf)
    return dirs


def _iter_json(env_key: str, leaf: str):
    for directory in _candidate_dirs(env_key, leaf):
        if not directory.is_dir():
            continue
        for path in sorted(directory.glob("*.json")):
            try:
                obj = json.loads(path.read_text(encoding="utf-8"))
            except (OSError, json.JSONDecodeError):
                continue
            if isinstance(obj, dict):
                yield obj


def _load_authz_state() -> tuple[dict[str, dict], dict[str, dict]]:
    """origin→最新 AuthzEvidence / origin→最新 budget を索引化して返す。"""
    evidences: dict[str, dict] = {}
    budgets: dict[str, dict] = {}
    for obj in _iter_json("ESB_AUTHZ_DIR", ".esb-authz"):
        origin = obj.get("origin")
        if not isinstance(origin, str):
            continue
        if "robots" in obj and "url" in obj:  # AuthzEvidence 形
            prev = evidences.get(origin)
            if prev is None or str(obj.get("fetched_at", "")) >= str(prev.get("fetched_at", "")):
                evidences[origin] = obj
        elif "granted" in obj and "remaining" in obj:  # request-budget 形
            prev = budgets.get(origin)
            if prev is None or str(obj.get("issued_at", "")) >= str(prev.get("issued_at", "")):
                budgets[origin] = obj
    return evidences, budgets


# ---------------------------------------------------------------------------
# run-scoping: ESB run がアクティブなときだけ fetch-authz を enforce する。
# ---------------------------------------------------------------------------
def _esb_run_active() -> bool:
    """ESB run のアクティブ判定 (enforce スコープの切替のみ・deny 規律は不変)。

    matcher は session-global に発火するため、run 外の正当な操作 (兄弟 plugin の外部 fetch) を
    証跡不在で遮断しないよう、ESB run の状態表面が確認できるときだけ述語評価へ進む。以下の
    いずれかで真:
      (a) env ESB_RUN=1 (orchestrator の明示宣言)
      (b) env ESB_AUTHZ_DIR が設定済み (ESB 状態置場の明示指定)
      (c) 既定探索順 (_candidate_dirs) で .esb-authz ディレクトリを発見
          (= C12 が run 開始時に発行する AuthzEvidence / budget の置場が存在)
    (b)(c) は enforce 側 (安全側) へ倒す拡張で、遮断が緩む方向には働かない。アクティブ時の
    deny/allow 挙動はこの関数の下流で従来どおり不変。
    """
    if os.environ.get("ESB_RUN") == "1":
        return True
    if os.environ.get("ESB_AUTHZ_DIR"):
        return True
    if any(directory.is_dir() for directory in _candidate_dirs("ESB_AUTHZ_DIR", ".esb-authz")):
        return True
    return False


# ---------------------------------------------------------------------------
# 述語: fetch-authz
# ---------------------------------------------------------------------------
def _budget_has(remaining: dict, crawl_mode: str, need: str) -> tuple[bool, str]:
    # need→remaining-key 写像は C12 の SSOT を共有 import する (hook 側で複製しない)。
    keymap = _AUTHZ.get_need_keys(crawl_mode) if _AUTHZ is not None else {"request": "requests"}
    key = keymap.get(need, keymap.get("request", "requests"))
    val = remaining.get(key)
    if not isinstance(val, int):
        return False, f"remaining.{key} 欠落"
    if val <= 0:
        return False, f"remaining.{key}=0"
    return True, ""


def _budget_ok(budget: dict, need: str) -> tuple[bool, str]:
    if not budget.get("granted"):
        return False, "budget granted=false"
    remaining = budget.get("remaining")
    if not isinstance(remaining, dict) or remaining.get("denied"):
        return False, "budget remaining=denied"
    return _budget_has(remaining, str(budget.get("crawl_mode", "single")), need)


def _eval_fetch_origin(origin: str, need: str) -> tuple[bool, str]:
    """origin 単位で AuthzEvidence(decide 再評価)と残予算を照合する。"""
    if _AUTHZ is None:
        return False, "authz module 読込不能 (fail-closed)"
    evidences, budgets = _load_authz_state()
    evidence = evidences.get(origin)
    if evidence is None:
        return False, f"AuthzEvidence 不在: {origin}"
    decision, reason = _AUTHZ.decide(evidence, {})
    if decision != "allow":
        return False, f"authz={decision} ({reason}): {origin}"
    budget = budgets.get(origin)
    if budget is None:
        return False, f"request-budget 不在: {origin}"
    ok, why = _budget_ok(budget, need)
    if not ok:
        return False, f"予算超過 {why}: {origin}"
    return True, f"authorized ({origin}, need={need})"


# ---------------------------------------------------------------------------
# tool 分類 → 述語 dispatch
# ---------------------------------------------------------------------------
def _evaluate_bash(command: str) -> tuple[int, str]:
    urls = _URL_RE.findall(command or "")
    if not urls:
        return 0, "bash: 外部 URL 無し (通過)"

    external_origins: list[str] = []
    for url in urls:
        host = _host(url) or ""
        if _is_local_host(host):
            continue
        origin = _origin(url)
        if origin is None:
            return 2, "fetch-authz(bash): URL 解析不能"
        external_origins.append(origin)

    for origin in dict.fromkeys(external_origins):  # 安定順・重複除去
        ok, why = _eval_fetch_origin(origin, "request")
        if not ok:
            return 2, "fetch-authz(bash): " + why

    return 0, "bash: authorized"


def evaluate(tool_name: object, tool_input: object) -> tuple[int, str]:
    """(exit_code, message) を返す。0=許可 / 2=遮断。"""
    name = tool_name if isinstance(tool_name, str) else ""
    ti = tool_input if isinstance(tool_input, dict) else {}

    # --- fetch-authz: WebFetch ---
    if name == "WebFetch":
        url = _extract_url(ti)
        if not url:
            return 2, "fetch-authz: WebFetch に url 不在 (fail-closed)"
        origin = _origin(url)
        if origin is None:
            return 2, "fetch-authz: WebFetch 先 URL 解析不能"
        ok, why = _eval_fetch_origin(origin, "request")
        return (0, why) if ok else (2, "fetch-authz: " + why)

    # --- fetch-authz: Bash (外部 URL fetch) ---
    if name == "Bash":
        return _evaluate_bash(ti.get("command") or "")

    # matcher 外 tool は素通し (契約: 非fetch は通過)。
    return 0, "対象外 tool (通過)"


# ---------------------------------------------------------------------------
# entrypoint
# ---------------------------------------------------------------------------
def main(argv: list[str] | None = None) -> int:
    argv = list(sys.argv[1:] if argv is None else argv)
    if "--self-test" in argv:
        return _self_test()

    try:
        raw = sys.stdin.read()
        data = json.loads(raw) if raw.strip() else {}
    except (json.JSONDecodeError, ValueError):
        sys.stderr.write("pre-fetch-authz-guard: hook payload 解釈不能 (fail-closed)\n")
        return 2
    if not isinstance(data, dict):
        sys.stderr.write("pre-fetch-authz-guard: hook payload が object でない (fail-closed)\n")
        return 2

    # run-scoping ゲート: ESB run 非アクティブなら enforce しない (co-install した兄弟 plugin の
    # 正当な操作を証跡不在で遮断しない)。アクティブ時の fail-closed 挙動はこの下で従来どおり。
    if not _esb_run_active():
        return 0

    code, message = evaluate(data.get("tool_name"), data.get("tool_input"))
    if code != 0:
        sys.stderr.write(f"pre-fetch-authz-guard BLOCK [{data.get('tool_name')}]: {message}\n")
    return code


# ---------------------------------------------------------------------------
# 内蔵スモークテスト (network なし・一時 fixture)
# ---------------------------------------------------------------------------
def _self_test() -> int:
    import tempfile

    if _AUTHZ is None:
        sys.stderr.write(f"self-test: authz module を読み込めない: {_AUTHZ_PATH}\n")
        return 1

    failures: list[str] = []
    total = 0

    def check(label: str, got: int, want: int) -> None:
        nonlocal total
        total += 1
        mark = "ok" if got == want else "FAIL"
        if got != want:
            failures.append(f"{label}: got exit {got}, want {want}")
        sys.stdout.write(f"  [{mark}] {label} (exit={got}, want={want})\n")

    def run_payload(payload: dict) -> int:
        code, _msg = evaluate(payload.get("tool_name"), payload.get("tool_input"))
        return code

    authz_dir = Path(tempfile.mkdtemp(prefix="esb-authz-"))
    os.environ["ESB_AUTHZ_DIR"] = str(authz_dir)
    # 既定探索先の混入を避ける (self-test を決定論化)。
    os.environ.pop("CLAUDE_PROJECT_DIR", None)

    url = "https://example.com/pricing"
    origin = "https://example.com"
    allow_policy = {
        "robots": {
            "http_status": 200,
            "target_path_allowed": True,
            "crawl_delay_ms": 0,
            "raw_excerpt": "User-agent: *\nAllow: /",
        }
    }
    # C12 の実 producer 関数で genuine な allow evidence+budget を生成 (schema 一致検証)。
    evidence, _req = _AUTHZ.build_authz_evidence(url, origin, allow_policy, offline=True, cached_evidence=None)
    decision, reason = _AUTHZ.decide(evidence, allow_policy)
    evidence["decision"], evidence["decision_reason"] = decision, reason
    budget = _AUTHZ.build_budget(origin, "single", allow_policy, evidence, None, decision == "allow")

    def write_json(directory: Path, name: str, obj: dict) -> None:
        (directory / name).write_text(json.dumps(obj, ensure_ascii=False, indent=2), encoding="utf-8")

    # (1) allow: evidence+budget 揃い → 通過
    write_json(authz_dir, "example.evidence.json", evidence)
    write_json(authz_dir, "example.budget.json", budget)
    check("fetch allow → 通過", run_payload({"tool_name": "WebFetch", "tool_input": {"url": url}}), 0)

    # (2) 未知 origin: evidence 不在 → 遮断
    check(
        "fetch 未知origin → 遮断",
        run_payload({"tool_name": "WebFetch", "tool_input": {"url": "https://other.example.org/x"}}),
        2,
    )

    # (3) deny evidence → 遮断
    deny_policy = {"robots": {"http_status": 200, "target_path_allowed": False, "raw_excerpt": "Disallow: /"}}
    deny_ev, _ = _AUTHZ.build_authz_evidence(url, origin, deny_policy, offline=True, cached_evidence=None)
    d_dec, d_reason = _AUTHZ.decide(deny_ev, deny_policy)
    deny_ev["decision"], deny_ev["decision_reason"] = d_dec, d_reason
    write_json(authz_dir, "example.evidence.json", deny_ev)
    check("fetch deny(robots) → 遮断", run_payload({"tool_name": "WebFetch", "tool_input": {"url": url}}), 2)

    # (4) 期限切れ evidence → 遮断
    expired_ev = dict(evidence)
    expired_ev["expires_at"] = "2000-01-01T00:00:00Z"
    write_json(authz_dir, "example.evidence.json", expired_ev)
    check("fetch 期限切れ → 遮断", run_payload({"tool_name": "WebFetch", "tool_input": {"url": url}}), 2)

    # (5) 予算枯渇 → 遮断 (evidence は allow に戻す)
    write_json(authz_dir, "example.evidence.json", evidence)
    exhausted = json.loads(json.dumps(budget))
    exhausted["remaining"]["requests"] = 0
    write_json(authz_dir, "example.budget.json", exhausted)
    check("fetch 予算枯渇 → 遮断", run_payload({"tool_name": "WebFetch", "tool_input": {"url": url}}), 2)

    # (6) 非fetch Bash → 通過
    check("bash(非fetch) → 通過", run_payload({"tool_name": "Bash", "tool_input": {"command": "ls -la /tmp"}}), 0)

    # (7) bash 内 外部 URL fetch (budget 復帰) → 通過
    write_json(authz_dir, "example.budget.json", budget)
    check(
        "bash(外部URL fetch) → 通過",
        run_payload({"tool_name": "Bash", "tool_input": {"command": f"curl -s {url}"}}),
        0,
    )

    # (8) 空 tool_name payload → 対象外扱いで通過 (evaluate 直呼びの健全性)
    check("空 tool_name → 通過", run_payload({}), 0)

    # (9) budget need→remaining-key 写像を C12 と import 共有 (複製除去・drift 検出)
    #     get_need_keys() の写像先が build_budget の remaining キー集合に含まれる (schema 改名で失敗)
    for mode in ("single", "full_site"):
        b = _AUTHZ.build_budget(origin, mode, allow_policy, evidence, None, True)
        remaining_keys = set(b.get("remaining", {}))
        mapped = set(_AUTHZ.get_need_keys(mode).values())
        check(f"need-key import一致 ({mode})", 0 if mapped <= remaining_keys else 1, 0)

    sys.stdout.write(
        f"\nself-test: {'PASS' if not failures else 'FAIL'} "
        f"({total - len(failures)}/{total} ケース緑)\n"
    )
    for line in failures:
        sys.stdout.write(f"  - {line}\n")
    return 0 if not failures else 1


if __name__ == "__main__":
    raise SystemExit(main())
