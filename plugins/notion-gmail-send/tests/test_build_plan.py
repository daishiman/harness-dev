# /// script
# name: test_build_plan
# purpose: dry-run build_plan が body_true_count/recipient_true_count を units 直積数と独立に記録することを検証する (finding E)。
# inputs: []
# outputs: []
# contexts: [C]
# network: false
# write-scope: none
# dependencies: ["pytest"]
# requires-python: ">=3.9"
# ///
"""build_plan の母数記録テスト。

本文ありだが宛先0 → 直積0・units0 でも body_true_count は本文行数を正しく保持し、
送信側 G2.body が「本文無し」と誤誘導しないための母数を plan に残すことを固定する。"""
import importlib.util
import json
from pathlib import Path

from lib import notion_client, notion_config, secrets

PLUGIN_ROOT = Path(__file__).resolve().parents[1]
BP_PATH = PLUGIN_ROOT / "skills" / "run-notion-gmail-dry-run" / "scripts" / "build-plan.py"


def _load_build_plan():
    spec = importlib.util.spec_from_file_location("build_plan_under_test", BP_PATH)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


def test_body_true_count_independent_of_units(monkeypatch, tmp_path):
    bp = _load_build_plan()
    cfg = {"notion_gmail_send": {"source": {"body_db": "db1", "recipient_db": "db2"}}}
    seen = {}
    def _load_config(path=None):
        seen["path"] = path
        return cfg
    monkeypatch.setattr(notion_config, "load_config", _load_config)
    monkeypatch.setattr(notion_config, "find_config_path", lambda path=None: None)
    monkeypatch.setattr(secrets, "get_notion_api_key", lambda: "key")
    monkeypatch.setattr(notion_client, "NotionClient", lambda key: object())
    # 本文 true 2件・宛先 true 0件 → 直積=0・units=0、しかし body_true_count は 2 であるべき
    bodies = [
        {"page_id": "b1", "subject": "件名1", "body": "本文1", "from_addr": "f@x.com", "cc_raw": ""},
        {"page_id": "b2", "subject": "件名2", "body": "本文2", "from_addr": "f@x.com", "cc_raw": ""},
    ]
    monkeypatch.setattr(notion_client, "fetch_bodies_true", lambda c, db: (bodies, []))
    monkeypatch.setattr(notion_client, "fetch_recipients_true",
                        lambda c, db: {"recipients": [], "skipped": [], "suppressed": [], "duplicate_dropped": []})

    out = tmp_path / "plan.json"
    explicit_config = tmp_path / ".notion-config.alt.json"
    explicit_config.write_text("{}", encoding="utf-8")
    monkeypatch.setattr("sys.argv", ["build_plan", "--out", str(out), "--config", str(explicit_config)])
    assert bp.main() == 0
    assert seen["path"] == str(explicit_config)

    plan = json.loads(out.read_text(encoding="utf-8"))
    assert plan["count"] == 0                 # 送信単位は0 (宛先がいない)
    assert plan["body_true_count"] == 2       # しかし本文 true 行数は保持される (no_body 誤誘導の母数を断つ)
    assert plan["recipient_true_count"] == 0
    assert plan["first_stage_count"] == 0


def test_canary_limits_units_bound_to_plan_hash(monkeypatch, tmp_path):
    bp = _load_build_plan()
    cfg = {"notion_gmail_send": {"source": {"body_db": "db1", "recipient_db": "db2"}}}
    monkeypatch.setattr(notion_config, "load_config", lambda path=None: cfg)
    monkeypatch.setattr(notion_config, "find_config_path", lambda path=None: None)
    monkeypatch.setattr(secrets, "get_notion_api_key", lambda: "key")
    monkeypatch.setattr(notion_client, "NotionClient", lambda key: object())
    bodies = [{"page_id": "b1", "subject": "件名", "body": "本文", "from_addr": "f@x.com", "cc_raw": ""}]
    recips = [
        {"page_id": "r1", "name": "A", "company": "X", "pro_email": "a@x.com", "hisho_email": "", "created_time": "2026-06-23T09:03:00.000Z"},
        {"page_id": "r2", "name": "B", "company": "Y", "pro_email": "b@y.com", "hisho_email": "", "created_time": "2026-06-23T09:02:00.000Z"},
        {"page_id": "r3", "name": "C", "company": "Z", "pro_email": "c@z.com", "hisho_email": "", "created_time": "2026-06-23T09:01:00.000Z"},
    ]
    monkeypatch.setattr(notion_client, "fetch_bodies_true", lambda c, db: (bodies, []))
    monkeypatch.setattr(notion_client, "fetch_recipients_true",
                        lambda c, db: {"recipients": recips, "skipped": [], "suppressed": [], "duplicate_dropped": []})

    out = tmp_path / "plan.json"
    monkeypatch.setattr("sys.argv", ["build_plan", "--out", str(out), "--canary", "1"])
    assert bp.main() == 0

    plan = json.loads(out.read_text(encoding="utf-8"))
    assert plan["count"] == 1
    assert len(plan["units"]) == 1
    assert plan["available_unit_count"] == 3
    assert plan["canary_limit"] == 1
    assert plan["canary_applied"] is True


def test_db_overrides_do_not_require_config(monkeypatch, tmp_path):
    bp = _load_build_plan()
    def _load_config(path=None):
        raise AssertionError("both --db1 and --db2 were provided; config must not be loaded")
    monkeypatch.setattr(notion_config, "load_config", _load_config)
    monkeypatch.setattr(notion_config, "find_config_path", lambda path=None: None)
    monkeypatch.setattr(secrets, "get_notion_api_key", lambda: "key")
    monkeypatch.setattr(notion_client, "NotionClient", lambda key: object())
    bodies = [{"page_id": "b1", "subject": "件名", "body": "本文", "from_addr": "f@x.com", "cc_raw": ""}]
    recips = [{"page_id": "r1", "name": "A", "company": "X", "pro_email": "a@x.com",
               "hisho_email": "", "created_time": "2026-06-23T09:03:00.000Z"}]
    seen = {}
    def _fetch_bodies(client, db):
        seen["db1"] = db
        return bodies, []
    def _fetch_recipients(client, db):
        seen["db2"] = db
        return {"recipients": recips, "skipped": [], "suppressed": [], "duplicate_dropped": []}
    monkeypatch.setattr(notion_client, "fetch_bodies_true", _fetch_bodies)
    monkeypatch.setattr(notion_client, "fetch_recipients_true", _fetch_recipients)

    out = tmp_path / "plan.json"
    monkeypatch.setattr("sys.argv", ["build_plan", "--db1", "body-db", "--db2", "recipient-db", "--out", str(out)])
    assert bp.main() == 0

    plan = json.loads(out.read_text(encoding="utf-8"))
    assert seen == {"db1": "body-db", "db2": "recipient-db"}
    assert plan["source"] == {"body_db": "body-db", "recipient_db": "recipient-db"}
    assert plan["count"] == 1


def test_placeholder_config_stops_before_notion_fetch(monkeypatch, tmp_path):
    bp = _load_build_plan()
    monkeypatch.setattr(notion_config, "load_config", lambda path=None: notion_config.CONFIG_SKELETON)
    monkeypatch.setattr(notion_config, "find_config_path", lambda path=None: tmp_path / ".notion-config.json")
    monkeypatch.setattr(secrets, "get_notion_api_key",
                        lambda: (_ for _ in ()).throw(AssertionError("Notion key must not be read")))
    monkeypatch.setattr(notion_client, "NotionClient",
                        lambda key: (_ for _ in ()).throw(AssertionError("Notion client must not be created")))

    out = tmp_path / "plan.json"
    monkeypatch.setattr("sys.argv", ["build_plan", "--out", str(out)])
    assert bp.main() == 2
    assert not out.exists()
