"""Receipt-gated, deduplicated Slack publication notification tests."""
from __future__ import annotations

import importlib.util
import json
from pathlib import Path
from types import SimpleNamespace


ROOT = Path(__file__).resolve().parents[2]
PLUGIN = ROOT / "plugins" / "skill-intake"
NOTIFIER = PLUGIN / "scripts" / "post_publish_notify.py"


def load_notifier():
    spec = importlib.util.spec_from_file_location("skill_intake_post_publish_notify", NOTIFIER)
    assert spec and spec.loader
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def success_receipt(path: Path, *, event_id: str = "publish-event-123") -> Path:
    path.write_text(
        json.dumps({
            "status": "published",
            "exit_code": 0,
            "stage": "publish",
            "page_id": "page-1",
            "url": "https://www.notion.so/page-1",
            "mode": "update",
            "publish_event_id": event_id,
        }),
        encoding="utf-8",
    )
    return path


def test_hooks_manifest_does_not_attach_publish_notification_to_generic_bash():
    manifest = json.loads((PLUGIN / "hooks" / "hooks.json").read_text(encoding="utf-8"))
    post_tool_use = manifest["hooks"].get("PostToolUse", [])
    for group in post_tool_use:
        if group.get("matcher") == "Bash":
            commands = [hook.get("command", "") for hook in group.get("hooks", [])]
            assert not any("post-publish-notify" in command for command in commands)


def test_invalid_or_failed_receipt_never_reads_keychain_or_sends(tmp_path):
    module = load_notifier()
    receipt = tmp_path / "notion-log.json"
    receipt.write_text(json.dumps({"status": "failed", "exit_code": 1}), encoding="utf-8")
    calls: list[str] = []

    result = module.notify(
        receipt,
        hint="example",
        secret_reader=lambda: calls.append("keychain") or "https://hooks.slack.test/x",
        sender=lambda *_a, **_k: calls.append("send") or 200,
    )

    assert result["status"] == "skipped_invalid_receipt"
    assert calls == []
    assert not (tmp_path / ".post-publish-notifications").exists()


def test_malformed_and_non_object_receipts_are_invalid(tmp_path):
    module = load_notifier()
    malformed = tmp_path / "malformed.json"
    malformed.write_text("{broken", encoding="utf-8")
    assert module._read_success_receipt(malformed) is None
    non_object = tmp_path / "list.json"
    non_object.write_text("[]", encoding="utf-8")
    assert module._read_success_receipt(non_object) is None


def test_success_receipt_is_delivered_exactly_once(tmp_path):
    module = load_notifier()
    receipt = success_receipt(tmp_path / "notion-log.json")
    calls: list[tuple[str, str]] = []

    def send(webhook: str, text: str) -> int:
        calls.append((webhook, text))
        return 200

    first = module.notify(
        receipt,
        hint="customer-intake",
        secret_reader=lambda: "https://hooks.slack.test/services/redacted",
        sender=send,
    )
    second = module.notify(
        receipt,
        hint="customer-intake",
        secret_reader=lambda: "https://hooks.slack.test/services/redacted",
        sender=send,
    )

    assert first["status"] == "notified"
    assert second["status"] == "deduplicated"
    assert len(calls) == 1
    assert "customer-intake" in calls[0][1]
    assert "https://www.notion.so/page-1" in calls[0][1]
    marker = tmp_path / ".post-publish-notifications" / "publish-event-123.json"
    assert json.loads(marker.read_text(encoding="utf-8"))["status"] == "notified"


def test_notification_claim_prevents_concurrent_duplicate(tmp_path):
    module = load_notifier()
    receipt = success_receipt(tmp_path / "notion-log.json", event_id="publish-event-locked")
    claims = tmp_path / ".post-publish-notifications"
    claims.mkdir()
    (claims / "publish-event-locked.json").write_text(
        json.dumps({"status": "claimed"}), encoding="utf-8"
    )
    calls: list[str] = []
    result = module.notify(
        receipt,
        hint="customer-intake",
        secret_reader=lambda: "https://hooks.slack.test/services/redacted",
        sender=lambda *_a: calls.append("send") or 200,
    )
    assert result["status"] == "deduplicated"
    assert calls == []


def test_notification_lost_claim_race_does_not_send(tmp_path, monkeypatch):
    module = load_notifier()
    receipt = success_receipt(tmp_path / "notion-log.json", event_id="publish-event-race")
    monkeypatch.setattr(module, "_claim", lambda *_a: False)
    sends: list[str] = []
    result = module.notify(
        receipt,
        secret_reader=lambda: "https://hooks.slack.test/services/redacted",
        sender=lambda *_a: sends.append("send") or 200,
    )
    assert result["status"] == "deduplicated" and sends == []


def test_ambiguous_transport_failure_is_recorded_and_not_replayed(tmp_path):
    module = load_notifier()
    receipt = success_receipt(tmp_path / "notion-log.json", event_id="publish-event-failed")
    attempts: list[str] = []

    def fail_after_attempt(*_args):
        attempts.append("attempt")
        raise RuntimeError("ambiguous remote acceptance")

    first = module.notify(
        receipt,
        hint="customer-intake",
        secret_reader=lambda: "https://hooks.slack.test/services/redacted",
        sender=fail_after_attempt,
    )
    second = module.notify(
        receipt,
        hint="customer-intake",
        secret_reader=lambda: "https://hooks.slack.test/services/redacted",
        sender=fail_after_attempt,
    )
    assert first["status"] == "delivery_failed"
    assert second["status"] == "deduplicated"
    assert attempts == ["attempt"]


def test_read_webhook_uses_helper_without_exposing_secret(tmp_path, monkeypatch):
    module = load_notifier()
    helper = tmp_path / "keychain.py"
    helper.write_text("# fixture\n", encoding="utf-8")
    monkeypatch.setattr(module, "KEYCHAIN_SCRIPT", helper)
    calls = []

    def fake_run(argv, **kwargs):
        calls.append((argv, kwargs))
        return SimpleNamespace(returncode=0, stdout="https://hooks.slack.test/redacted\n")

    monkeypatch.setattr(module.subprocess, "run", fake_run)
    assert module.read_webhook() == "https://hooks.slack.test/redacted"
    assert "--print-unsafe" in calls[0][0]
    monkeypatch.setattr(
        module.subprocess,
        "run",
        lambda *_a, **_k: SimpleNamespace(returncode=1, stdout="must-not-return"),
    )
    assert module.read_webhook() is None


def test_read_webhook_missing_or_timeout_is_optional(tmp_path, monkeypatch):
    module = load_notifier()
    monkeypatch.setattr(module, "KEYCHAIN_SCRIPT", tmp_path / "missing.py")
    assert module.read_webhook() is None
    helper = tmp_path / "keychain.py"
    helper.write_text("# fixture\n", encoding="utf-8")
    monkeypatch.setattr(module, "KEYCHAIN_SCRIPT", helper)
    monkeypatch.setattr(
        module.subprocess,
        "run",
        lambda *_a, **_k: (_ for _ in ()).throw(module.subprocess.TimeoutExpired("keychain", 5)),
    )
    assert module.read_webhook() is None


def test_send_slack_posts_json_and_main_is_nonfatal(tmp_path, monkeypatch, capsys):
    module = load_notifier()
    captured = {}

    class Response:
        status = 200

        def __enter__(self):
            return self

        def __exit__(self, *_args):
            return False

    def fake_urlopen(request, timeout):
        captured["request"] = request
        captured["timeout"] = timeout
        return Response()

    monkeypatch.setattr(module.urllib.request, "urlopen", fake_urlopen)
    assert module.send_slack("https://hooks.slack.test/redacted", "hello") == 200
    assert json.loads(captured["request"].data) == {"text": "hello"}
    assert captured["timeout"] == 8

    receipt = success_receipt(tmp_path / "notion-log.json", event_id="publish-event-main")
    monkeypatch.setattr(module, "notify", lambda path, hint=None: {"status": "deduplicated"})
    assert module.main(["--receipt", str(receipt), "--hint", "h"]) == 0
    assert json.loads(capsys.readouterr().err) == {"status": "deduplicated"}
