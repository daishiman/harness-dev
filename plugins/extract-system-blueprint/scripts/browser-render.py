#!/usr/bin/env python3
# /// script
# name: browser-render
# purpose: MCP 非依存でブラウザがレンダリングした情報 (JS 実行後 DOM・viewport screenshot) を取得する
#          決定論ユーティリティ。ローカルの headless Chrome/Chromium バイナリを subprocess (CLI) で
#          起動する = MCP サーバー接続ではない。C12(authz-classify) の AuthzEvidence と request budget を
#          必須入力に取り、allow 以外 (deny/unknown/期限切れ) は取得を一切行わず fail-closed する
#          (判定ロジックは C12 を import 共有し重複実装しない)。ブラウザバイナリが解決できない環境では
#          exit 3 + status=browser-unavailable を返し、呼び出し側 (C03) は該当観測を observation_gap
#          (blocked, reason=browser-unavailable) として記録して静的 HTTP 観測へ縮退する (graceful)。
#          瞬間負荷レバー: 1 起動 = 1 navigation・min_interval 尊重・subprocess timeout・remote font 由来の
#          ハング回避 (--disable-remote-fonts --virtual-time-budget)。budget 消費は ledger へ記録する。
# inputs:
#   - argv: --url URL --out-dir DIR --authz-evidence FILE --request-budget FILE
#           [--screenshot] [--viewport WxH] [--timeout SEC] [--browser-bin PATH]
#           [--request-ledger FILE] [--self-test]
#   - env: ESB_BROWSER_BIN (明示バイナリパス。--browser-bin より優先度低)
# outputs:
#   - stdout: JSON {url, status, browser_bin, rendered_dom_path, screenshot_path, notes}
#   - stderr: deny|unknown / バイナリ不在 / 起動失敗 等の violation
#   - exit: 0=OK / 1=認可外・起動失敗 / 2=usage / 3=browser-unavailable (graceful 縮退シグナル)
# contexts: [C, E]
# network: true
# write-scope: --out-dir 配下および --request-ledger で指定した PLAN 成果物ファイルのみ
# dependencies: []
# requires-python: ">=3.10"
# ///
"""browser-render — MCP を使わずローカル headless Chrome/Chromium でレンダリング情報を取得する。

browser-runtime MCP を廃した後の rendered-observation 取得経路。ローカルにインストール済みの
Chrome/Chromium バイナリを CLI (subprocess) で叩くだけで、MCP サーバーへは一切接続しない。
呼び出しは C03 が ``Bash(python3 browser-render.py --url ...)`` で行い、URL は C08 fetch-authz hook の
認可境界内に入る (hook が Bash コマンドの URL を捕捉して AuthzEvidence を検査する)。本 script 自身も
C12 の ``decide()`` を import 共有して二重に fail-closed する。

バイナリが無い環境 (CI・最小コンテナ等) では exit 3 (browser-unavailable) を返し、C03 は該当観測を
observation_gap として記録して静的 HTTP 観測のみで続行する。これによりブラウザの有無に関わらず
plugin は動作し、ある時だけ rendered fact が増える (progressive enhancement)。
"""
from __future__ import annotations

import argparse
import importlib.util
import json
import os
import shutil
import subprocess
import sys
import time
from pathlib import Path
from urllib.parse import urlsplit

_SCRIPT_DIR = Path(__file__).resolve().parent
_AUTHZ_PATH = _SCRIPT_DIR / "authz-classify.py"

# 解決を試みる Chrome/Chromium バイナリ名 (優先順)。Playwright を使う場合も
# `playwright install` 済みの chromium 実体はこれらの which で拾えることが多い。
_BROWSER_CANDIDATES = (
    "chromium",
    "chromium-browser",
    "google-chrome",
    "google-chrome-stable",
    "chrome",
    "chrome-headless-shell",
)

# remote font 由来の headless ハング (30s+) を避ける共通フラグ。
_COMMON_FLAGS = (
    "--headless=new",
    "--disable-gpu",
    "--no-sandbox",
    "--disable-remote-fonts",
    "--hide-scrollbars",
)


def _load_authz_module():
    try:
        spec = importlib.util.spec_from_file_location("esb_authz_classify", _AUTHZ_PATH)
        if spec is None or spec.loader is None:
            return None
        module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(module)
        for attr in ("decide", "_origin_of"):
            if not hasattr(module, attr):
                return None
        return module
    except Exception:  # noqa: BLE001 — 読込失敗は理由不問で共有不能とみなす
        return None


_AUTHZ = _load_authz_module()


class UsageError(Exception):
    pass


class AuthzDenied(Exception):
    pass


def resolve_browser_bin(explicit: str | None) -> str | None:
    """ブラウザバイナリを --browser-bin → env ESB_BROWSER_BIN → PATH 探索の順で解決する。"""
    for cand in (explicit, os.environ.get("ESB_BROWSER_BIN")):
        if cand:
            p = Path(cand)
            if p.is_file() and os.access(p, os.X_OK):
                return str(p)
            found = shutil.which(cand)
            if found:
                return found
    for name in _BROWSER_CANDIDATES:
        found = shutil.which(name)
        if found:
            return found
    return None


def _parse_viewport(value: str) -> tuple[int, int]:
    try:
        w, h = value.lower().split("x", 1)
        return max(320, int(w)), max(240, int(h))
    except (ValueError, AttributeError) as exc:
        raise UsageError(f"--viewport は WxH 形式 (例 1280x900): {value!r}") from exc


def _load_json(path: str, flag: str) -> dict:
    try:
        return json.loads(Path(path).read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise UsageError(f"{flag} を読めない/JSON でない: {exc}") from exc


def _authorize(url: str, evidence_path: str, budget_path: str) -> None:
    """C12 の decide() で AuthzEvidence を再評価し allow 以外は fail-closed で止める。"""
    if _AUTHZ is None:
        raise AuthzDenied(f"authz module (C12) 読込不能 → fail-closed: {_AUTHZ_PATH}")
    evidence = _load_json(evidence_path, "--authz-evidence")
    budget = _load_json(budget_path, "--request-budget")
    decision, reason = _AUTHZ.decide(evidence, {})
    if decision != "allow":
        raise AuthzDenied(f"AuthzEvidence が allow でない ({decision}): {reason}")
    if budget.get("granted") is not True:
        raise AuthzDenied("request budget が granted=true でない")


def _min_interval_sleep(budget_path: str) -> None:
    """budget の min_interval_ms を尊重して瞬間負荷レバーを緩めない。"""
    try:
        budget = json.loads(Path(budget_path).read_text(encoding="utf-8"))
        ms = int(((budget.get("load_policy") or {}).get("min_interval_ms")) or 0)
    except (OSError, json.JSONDecodeError, TypeError, ValueError):
        ms = 0
    if ms > 0:
        time.sleep(min(ms, 5000) / 1000.0)


def _run_browser(bin_path: str, extra: list[str], url: str, timeout: int) -> subprocess.CompletedProcess:
    return subprocess.run(
        [bin_path, *_COMMON_FLAGS, "--virtual-time-budget=4000", *extra, url],
        capture_output=True, text=True, timeout=timeout,
    )


def render(args) -> int:
    if not args.url or not args.out_dir or not args.authz_evidence or not args.request_budget:
        raise UsageError("--url --out-dir --authz-evidence --request-budget は必須")
    if _AUTHZ is not None and _AUTHZ._origin_of(args.url) is None:
        raise UsageError(f"URL の origin を解決できない: {args.url}")

    _authorize(args.url, args.authz_evidence, args.request_budget)

    bin_path = resolve_browser_bin(args.browser_bin)
    if bin_path is None:
        payload = {
            "url": args.url,
            "status": "browser-unavailable",
            "browser_bin": None,
            "rendered_dom_path": None,
            "screenshot_path": None,
            "notes": "ローカルに Chrome/Chromium バイナリが見つからない。C03 は該当観測を "
                     "observation_gap(blocked, reason=browser-unavailable) として静的 HTTP 観測へ縮退する。",
        }
        sys.stdout.write(json.dumps(payload, ensure_ascii=False, indent=2) + "\n")
        return 3

    out_dir = Path(args.out_dir)
    (out_dir / "rendered").mkdir(parents=True, exist_ok=True)
    host = urlsplit(args.url).hostname or "page"
    slug = host.replace(".", "_")

    _min_interval_sleep(args.request_budget)
    notes: list[str] = []
    started = time.monotonic()

    # (1) JS 実行後 DOM を dump-dom で取得。
    dom_rel = f"rendered/{slug}.rendered.html"
    dom_path = out_dir / dom_rel
    try:
        dom = _run_browser(bin_path, ["--dump-dom"], args.url, args.timeout)
    except subprocess.TimeoutExpired:
        sys.stderr.write(f"browser dump-dom timeout ({args.timeout}s): {args.url}\n")
        return 1
    if dom.returncode != 0:
        sys.stderr.write(f"browser dump-dom 失敗 (exit {dom.returncode}): {dom.stderr.strip()[:400]}\n")
        return 1
    dom_path.write_text(dom.stdout, encoding="utf-8")

    # (2) screenshot (任意)。
    shot_rel = None
    if args.screenshot:
        w, h = _parse_viewport(args.viewport)
        shot_rel = f"rendered/{slug}.screenshot.png"
        shot_path = out_dir / shot_rel
        _min_interval_sleep(args.request_budget)
        try:
            shot = _run_browser(
                bin_path,
                [f"--screenshot={shot_path}", f"--window-size={w},{h}"],
                args.url, args.timeout,
            )
        except subprocess.TimeoutExpired:
            sys.stderr.write(f"browser screenshot timeout ({args.timeout}s): {args.url}\n")
            return 1
        if shot.returncode != 0 or not shot_path.is_file():
            sys.stderr.write(f"browser screenshot 失敗 (exit {shot.returncode}): {shot.stderr.strip()[:400]}\n")
            shot_rel = None
            notes.append("screenshot 取得に失敗 (DOM は取得済み)")

    elapsed_ms = int((time.monotonic() - started) * 1000)

    # budget ledger へ navigation 消費を追記 (再試行で非リセット)。
    if args.request_ledger:
        ledger_path = Path(args.request_ledger)
        try:
            ledger = json.loads(ledger_path.read_text(encoding="utf-8")) if ledger_path.is_file() else {}
        except (OSError, json.JSONDecodeError):
            ledger = {}
        entry = ledger.setdefault("browser_render", [])
        entry.append({"url": args.url, "rendered": True, "screenshot": bool(shot_rel), "elapsed_ms": elapsed_ms})
        ledger_path.parent.mkdir(parents=True, exist_ok=True)
        ledger_path.write_text(json.dumps(ledger, ensure_ascii=False, indent=2), encoding="utf-8")

    payload = {
        "url": args.url,
        "status": "ok",
        "browser_bin": bin_path,
        "rendered_dom_path": dom_rel,
        "screenshot_path": shot_rel,
        "elapsed_ms": elapsed_ms,
        "notes": notes,
    }
    sys.stdout.write(json.dumps(payload, ensure_ascii=False, indent=2) + "\n")
    return 0


def _self_test() -> int:
    """実ブラウザ非依存の自己テスト: バイナリ解決・graceful 縮退・認可 fail-closed・偽バイナリ経路。"""
    import tempfile

    failures: list[str] = []

    def check(label: str, ok: bool) -> None:
        if not ok:
            failures.append(label)

    if _AUTHZ is None:
        sys.stderr.write(f"self-test: authz module (C12) を読み込めない: {_AUTHZ_PATH}\n")
        return 1

    with tempfile.TemporaryDirectory() as td:
        tmp = Path(td)
        url = "https://example.com/"
        origin = "https://example.com"
        policy = {"robots": {"http_status": 200, "target_path_allowed": True}}
        evidence, _ = _AUTHZ.build_authz_evidence(url, origin, policy, offline=True, cached_evidence=None)
        dec, rea = _AUTHZ.decide(evidence, policy)
        evidence.update(decision=dec, decision_reason=rea)
        budget = _AUTHZ.build_budget(origin, "single", policy, evidence, None, dec == "allow")
        ev_path = tmp / "authz.json"
        bud_path = tmp / "budget.json"
        ev_path.write_text(json.dumps(evidence), encoding="utf-8")
        bud_path.write_text(json.dumps(budget), encoding="utf-8")

        # (1) バイナリ不在 → browser-unavailable (exit 3) で graceful 縮退
        os.environ.pop("ESB_BROWSER_BIN", None)
        ns = argparse.Namespace(
            url=url, out_dir=str(tmp / "out"), authz_evidence=str(ev_path),
            request_budget=str(bud_path), screenshot=False, viewport="1280x900",
            timeout=30, browser_bin=str(tmp / "no-such-bin"), request_ledger=None,
        )
        rc = render(ns)
        check("バイナリ不在 → exit 3 (browser-unavailable)", rc == 3)

        # (2) 偽ブラウザバイナリで dump-dom + screenshot 経路が成立する
        fake = tmp / "fake-chrome.sh"
        fake.write_text(
            "#!/usr/bin/env bash\n"
            "shot=\"\"\n"
            "for a in \"$@\"; do case \"$a\" in --screenshot=*) shot=\"${a#--screenshot=}\";; esac; done\n"
            "if [ -n \"$shot\" ]; then printf 'PNG' > \"$shot\"; else printf '<html><body>rendered</body></html>'; fi\n",
            encoding="utf-8",
        )
        fake.chmod(0o755)
        ns2 = argparse.Namespace(
            url=url, out_dir=str(tmp / "out2"), authz_evidence=str(ev_path),
            request_budget=str(bud_path), screenshot=True, viewport="1280x900",
            timeout=30, browser_bin=str(fake), request_ledger=str(tmp / "ledger.json"),
        )
        rc2 = render(ns2)
        check("偽ブラウザで dump-dom+screenshot → exit 0", rc2 == 0)
        check("rendered DOM が保存される", (tmp / "out2" / "rendered" / "example_com.rendered.html").is_file())
        check("screenshot が保存される", (tmp / "out2" / "rendered" / "example_com.screenshot.png").is_file())
        check("ledger に browser_render が記録される",
              "browser_render" in json.loads((tmp / "ledger.json").read_text()))

        # (3) deny な evidence → AuthzDenied で fail-closed (decide() が実際に deny 評価する policy で作る)
        deny_policy = {"robots": {"http_status": 200, "target_path_allowed": False}}
        deny_ev, _ = _AUTHZ.build_authz_evidence(url, origin, deny_policy, offline=True, cached_evidence=None)
        d_dec, d_rea = _AUTHZ.decide(deny_ev, deny_policy)
        deny_ev.update(decision=d_dec, decision_reason=d_rea)
        (tmp / "deny.json").write_text(json.dumps(deny_ev), encoding="utf-8")
        ns3 = argparse.Namespace(
            url=url, out_dir=str(tmp / "out3"), authz_evidence=str(tmp / "deny.json"),
            request_budget=str(bud_path), screenshot=False, viewport="1280x900",
            timeout=30, browser_bin=str(fake), request_ledger=None,
        )
        denied = False
        try:
            render(ns3)
        except AuthzDenied:
            denied = True
        check("deny evidence → AuthzDenied (fail-closed)", denied)

    total = 6
    sys.stdout.write(
        f"self-test: {'PASS' if not failures else 'FAIL'} ({total - len(failures)}/{total} ケース緑)\n"
    )
    for line in failures:
        sys.stdout.write(f"  - {line}\n")
    return 0 if not failures else 1


def _parse_args(argv):
    ap = argparse.ArgumentParser(
        description="MCP 非依存の headless Chrome/Chromium レンダリング取得 (JS 後 DOM + screenshot)",
    )
    ap.add_argument("--url")
    ap.add_argument("--out-dir")
    ap.add_argument("--authz-evidence")
    ap.add_argument("--request-budget")
    ap.add_argument("--screenshot", action="store_true")
    ap.add_argument("--viewport", default="1280x900")
    ap.add_argument("--timeout", type=int, default=30)
    ap.add_argument("--browser-bin", default=None)
    ap.add_argument("--request-ledger", default=None)
    ap.add_argument("--self-test", action="store_true")
    return ap.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    args = _parse_args(list(sys.argv[1:] if argv is None else argv))
    if args.self_test:
        return _self_test()
    try:
        return render(args)
    except UsageError as exc:
        sys.stderr.write(str(exc) + "\n")
        return 2
    except AuthzDenied as exc:
        sys.stderr.write(f"BLOCK fetch-authz: {exc}\n")
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
