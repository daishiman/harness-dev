# /// script
# name: test_plan_compose
# purpose: plan_compose を dry-run(build-plan) と確認0 auto-send が共有する単一 plan SSOT として固定する。assemble_plan が build-plan と同一の plan_hash/units/各カウントを決定論で生成し、canary が available_unit_count を限定前に保持し、compose_plan が fetch→assemble を一本道で通すことを検証する。
# inputs: []
# outputs: []
# contexts: [C]
# network: false
# write-scope: none
# dependencies: ["pytest"]
# requires-python: ">=3.9"
# ///
"""plan_compose のユニットテスト (dry-run / auto-send 共有 SSOT の決定論)。

- assemble_plan: 純関数の決定論 (同入力→同 plan) と build-plan.py が委譲した結果との一致
- canary: 送信可能 unit を安定順先頭 N に限定し available_unit_count は限定前を保持
- compose_plan: fetch_bodies_true/fetch_recipients_true → assemble_plan の一本道
"""
import importlib.util
import json
from pathlib import Path

from lib import notion_client as nc, notion_config, secrets, plan_build as pb, plan_compose as pc

PLUGIN_ROOT = Path(__file__).resolve().parents[1]
BP_PATH = PLUGIN_ROOT / "skills" / "run-notion-gmail-dry-run" / "scripts" / "build-plan.py"

# 決定論比較で除外する非決定フィールド (実行ごとに変わるため plan の同一性判定から外す)
_VOLATILE = {"campaign_id", "generated_at"}


def _load_build_plan():
    spec = importlib.util.spec_from_file_location("build_plan_under_test_pc", BP_PATH)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


def _body(pid="b1", subject="件名", body="本文", from_addr="f@x.com", cc_raw=""):
    return {"page_id": pid, "subject": subject, "from_addr": from_addr,
            "cc_raw": cc_raw, "body": body, "msg_target": True}


def _recip(pid, pro, name="名前", company="会社", hisho="", created="2026-06-23T09:00:00.000Z"):
    return {"page_id": pid, "name": name, "company": company,
            "pro_email": pro, "hisho_email": hisho, "created_time": created}


def _resolution(recips, skipped=None, suppressed=None, duplicate_dropped=None):
    return {"recipients": recips, "skipped": skipped or [],
            "suppressed": suppressed or [], "duplicate_dropped": duplicate_dropped or []}


def _stable(plan):
    """揮発フィールドを除いた決定論部分のみ残す。"""
    return {k: v for k, v in plan.items() if k not in _VOLATILE}


# ============ assemble_plan: 純関数の決定論 ============
def test_assemble_plan_is_deterministic_on_same_inputs():
    bodies = [_body()]
    res = _resolution([_recip("r1", "a@x.com"), _recip("r2", "b@y.com")])
    kw = dict(db1="db1", db2="db2", campaign_id="fixed", generated_at="2026-06-26T00:00:00+09:00")
    p1 = pc.assemble_plan(bodies, [], res, **kw)
    p2 = pc.assemble_plan([_body()], [], _resolution([_recip("r1", "a@x.com"), _recip("r2", "b@y.com")]), **kw)
    assert p1 == p2                       # 揮発値を固定すれば完全一致 (純関数)
    assert p1["count"] == 2
    assert p1["plan_hash"] == pb.plan_hash(p1["units"])


# ============ assemble_plan == build-plan (委譲 SSOT) ============
def test_assemble_plan_matches_build_plan_output(monkeypatch, tmp_path):
    bp = _load_build_plan()
    cfg = {"notion_gmail_send": {"source": {"body_db": "db1", "recipient_db": "db2"}}}
    monkeypatch.setattr(notion_config, "load_config", lambda path=None: cfg)
    monkeypatch.setattr(notion_config, "find_config_path", lambda path=None: None)
    monkeypatch.setattr(secrets, "get_notion_api_key", lambda: "key")
    monkeypatch.setattr(nc, "NotionClient", lambda key: object())
    bodies = [_body(pid="b1", subject="件名A", body="本文 {{会社名}}"),
              _body(pid="b2", subject="件名B", body="本文B")]
    recips = [_recip("r1", "a@x.com", company="X社"), _recip("r2", "b@y.com", company="Y社")]
    res = _resolution(recips)
    monkeypatch.setattr(nc, "fetch_bodies_true", lambda c, db: (bodies, []))
    monkeypatch.setattr(nc, "fetch_recipients_true", lambda c, db: res)

    out = tmp_path / "plan.json"
    monkeypatch.setattr("sys.argv", ["build_plan", "--out", str(out)])
    assert bp.main() == 0
    bp_plan = json.loads(out.read_text(encoding="utf-8"))

    # build-plan が委譲する pc.assemble_plan を直接呼び、決定論部分が一致することを固定する。
    direct = pc.assemble_plan(bodies, [], res, db1="db1", db2="db2")
    assert _stable(direct) == _stable(bp_plan)
    # 中核の決定論キーを名指しで再確認 (回帰時にどこが割れたか分かるよう冗長に)。
    for key in ("plan_hash", "count", "first_to", "body_true_count",
                "recipient_true_count", "available_unit_count"):
        assert direct[key] == bp_plan[key], key
    assert [u["content_hash"] for u in direct["units"]] == [u["content_hash"] for u in bp_plan["units"]]


# ============ canary: 先頭 N 限定・available_unit_count は限定前 ============
def test_canary_limits_units_but_keeps_available_count():
    bodies = [_body()]
    recips = [_recip("r1", "a@x.com"), _recip("r2", "b@y.com"), _recip("r3", "c@z.com")]
    plan = pc.assemble_plan(bodies, [], _resolution(recips), db1="db1", db2="db2", canary=1)
    assert plan["count"] == 1                    # 送信は先頭1件のみ
    assert len(plan["units"]) == 1
    assert plan["available_unit_count"] == 3     # 母数は限定前を保持
    assert plan["canary_limit"] == 1
    assert plan["canary_applied"] is True
    # plan_hash は限定後 units から算出される (承認は限定後の1件にバインド)
    assert plan["plan_hash"] == pb.plan_hash(plan["units"])


def test_canary_at_or_above_available_is_not_applied():
    bodies = [_body()]
    recips = [_recip("r1", "a@x.com"), _recip("r2", "b@y.com")]
    plan = pc.assemble_plan(bodies, [], _resolution(recips), db1="db1", db2="db2", canary=5)
    assert plan["count"] == 2                     # 送信可能数 <= canary なので限定なし
    assert plan["available_unit_count"] == 2
    assert plan["canary_applied"] is False


def test_canary_selects_stable_prefix():
    # canary は安定順 (content_hash 昇順) の先頭を選ぶ → 取得順序に依らず決定論
    bodies = [_body()]
    recips = [_recip("r1", "a@x.com"), _recip("r2", "b@y.com"), _recip("r3", "c@z.com")]
    p_fwd = pc.assemble_plan(bodies, [], _resolution(recips), db1="db1", db2="db2", canary=1)
    p_rev = pc.assemble_plan(bodies, [], _resolution(list(reversed(recips))), db1="db1", db2="db2", canary=1)
    assert p_fwd["units"][0]["content_hash"] == p_rev["units"][0]["content_hash"]


# ============ compose_plan: fetch→assemble の一本道 ============
def test_compose_plan_threads_fetch_into_assemble(monkeypatch):
    bodies = [_body()]
    res = _resolution([_recip("r1", "a@x.com"), _recip("r2", "b@y.com")])
    seen = {}

    def _fetch_bodies(client, db):
        seen["db1"] = db
        return bodies, []

    def _fetch_recipients(client, db):
        seen["db2"] = db
        return res

    monkeypatch.setattr(nc, "fetch_bodies_true", _fetch_bodies)
    monkeypatch.setattr(nc, "fetch_recipients_true", _fetch_recipients)

    plan = pc.compose_plan(object(), "body-db", "recipient-db")
    assert seen == {"db1": "body-db", "db2": "recipient-db"}    # 受け取った db を素通しで渡す
    assert plan["source"] == {"body_db": "body-db", "recipient_db": "recipient-db"}
    assert plan["count"] == 2
    # compose と assemble の決定論部分は一致する (同じ取得データを同じロジックへ通すため)
    direct = pc.assemble_plan(bodies, [], res, db1="body-db", db2="recipient-db")
    assert _stable(plan) == _stable(direct)


def test_compose_plan_passes_canary(monkeypatch):
    bodies = [_body()]
    recips = [_recip("r1", "a@x.com"), _recip("r2", "b@y.com"), _recip("r3", "c@z.com")]
    monkeypatch.setattr(nc, "fetch_bodies_true", lambda c, db: (bodies, []))
    monkeypatch.setattr(nc, "fetch_recipients_true", lambda c, db: _resolution(recips))
    plan = pc.compose_plan(object(), "db1", "db2", canary=2)
    assert plan["count"] == 2 and plan["available_unit_count"] == 3 and plan["canary_applied"] is True
