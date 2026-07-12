"""lint-config-version-sync.py の検出ロジック回帰テスト。

焼き込みconfig (baked-default config) の内容を変えたのに plugin version を bump し忘れると、
version 名でキーされる Claude Code plugin キャッシュ (設計書 36 章 PKG-012: 同一 version 再取得は
no-op) が更新されず、修正が配布先に届かず消費側が古い config で fail-closed し続ける
(mf-kessai-invoice-check の DB id 焼き込みで実際に発生した「毎回設定を聞かれる」症状)。
本 lint がその一手 (version bump) の欠落を機械検知する不変条件を、pytest で腐らせない。

検証する不変条件:
  ① 内容変更 × version 据え置き → config_changed_no_bump (真因・最重要)
  ② plugin.json ↔ marketplace.json version 不一致 → marketplace_version_mismatch
  ③ 未登録の焼き込みconfig → missing_lock_entry
  ④ 実在しない lockfile エントリ → stale_lock_entry
  ⑤ 内容 or version 変化 × lockfile 未再生成 → lockfile_stale
  ⑥ --write は ① / ② を拒否 (papering over 防止)、bump 後は許可
  ⑦ 実 repo の config-version-lock.json は現在 working tree と完全同期 (CI の番人)

import 経路: dash 入り script のため importlib.util.spec_from_file_location
(test_lint_readme_plugin_root_portability.py のパターンに倣う)。
"""
import importlib.util
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SCRIPT = ROOT / "scripts" / "lint-config-version-sync.py"
SPEC = importlib.util.spec_from_file_location("lint_config_version_sync", SCRIPT)
MOD = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(MOD)

REL = "plugins/p/x.default.json"


def _current(sha="aaa", version="0.1.0", plugin="p", rel=REL):
    return {rel: {"plugin": plugin, "version": version, "sha256": sha}}


def _lock(sha="aaa", version="0.1.0", plugin="p", rel=REL):
    return {"configs": {rel: {"plugin": plugin, "version": version, "sha256": sha}}}


def _kinds(current, lock, mkt):
    return sorted(k for k, _key, _msg in MOD.evaluate(current, lock, mkt))


# --------------------------------------------------------------------------
# 純関数 evaluate() の各不変条件
# --------------------------------------------------------------------------
def test_in_sync_no_violation():
    assert _kinds(_current(), _lock(), {"p": "0.1.0"}) == []


def test_config_changed_without_bump_is_flagged():
    # 真因: 内容(sha)が変わったのに version 据え置き。PR #57 と同型のミスをここで捕捉する。
    kinds = _kinds(_current(sha="bbb", version="0.1.0"),
                   _lock(sha="aaa", version="0.1.0"), {"p": "0.1.0"})
    assert kinds == ["config_changed_no_bump"]


def test_config_changed_with_bump_is_stale_not_bug():
    # 内容変更 + version bump 済 → 真因ではなく単なる lockfile 未再生成 (別種別)。
    kinds = _kinds(_current(sha="bbb", version="0.2.0"),
                   _lock(sha="aaa", version="0.1.0"), {"p": "0.2.0"})
    assert kinds == ["lockfile_stale"]


def test_version_bump_without_config_change_is_stale():
    kinds = _kinds(_current(sha="aaa", version="0.2.0"),
                   _lock(sha="aaa", version="0.1.0"), {"p": "0.2.0"})
    assert kinds == ["lockfile_stale"]


def test_missing_lock_entry():
    assert _kinds(_current(), {"configs": {}}, {"p": "0.1.0"}) == ["missing_lock_entry"]


def test_stale_lock_entry():
    assert _kinds({}, _lock(), {"p": "0.1.0"}) == ["stale_lock_entry"]


def test_marketplace_version_mismatch():
    # config は同期しているが plugin.json(0.1.1) と marketplace(0.1.0) が食い違う。
    kinds = _kinds(_current(sha="aaa", version="0.1.1"),
                   _lock(sha="aaa", version="0.1.1"), {"p": "0.1.0"})
    assert kinds == ["marketplace_version_mismatch"]


def test_marketplace_absent_plugin_skips_that_check():
    # marketplace 非掲載 (非配布) plugin は version 整合検査をスキップ (誤検出回避)。
    assert _kinds(_current(), _lock(), {}) == []


# --------------------------------------------------------------------------
# main() / --write の統合 (実ファイルで write 拒否とライフサイクルを検証)
# --------------------------------------------------------------------------
def _make_repo(root, version="0.1.0", body=None):
    (root / ".claude-plugin").mkdir(parents=True, exist_ok=True)
    (root / ".claude-plugin" / "marketplace.json").write_text(
        json.dumps({"plugins": [{"name": "p", "version": version}]}), encoding="utf-8")
    pdir = root / "plugins" / "p" / ".claude-plugin"
    pdir.mkdir(parents=True, exist_ok=True)
    (pdir / "plugin.json").write_text(
        json.dumps({"name": "p", "version": version}), encoding="utf-8")
    (root / "plugins" / "p" / "x.default.json").write_text(
        json.dumps(body or {"db_id": "AAA"}), encoding="utf-8")


def _bump(root, version):
    mk = root / ".claude-plugin" / "marketplace.json"
    mk.write_text(json.dumps({"plugins": [{"name": "p", "version": version}]}), encoding="utf-8")
    pj = root / "plugins" / "p" / ".claude-plugin" / "plugin.json"
    pj.write_text(json.dumps({"name": "p", "version": version}), encoding="utf-8")


def test_write_refuses_change_without_bump_then_allows_after_bump(tmp_path):
    root = tmp_path / "repo"
    root.mkdir()
    _make_repo(root, version="0.1.0", body={"db_id": "AAA"})

    # 初期シード → 成功。
    assert MOD.main(["--write", "--root", str(root)]) == 0
    lock_before = (root / MOD.LOCK_NAME).read_text(encoding="utf-8")

    # config の中身を変える (version はそのまま) → check は exit 1。
    (root / "plugins" / "p" / "x.default.json").write_text(
        json.dumps({"db_id": "BBB"}), encoding="utf-8")
    assert MOD.main(["--root", str(root)]) == 1

    # --write は真因 (config_changed_no_bump) を拒否し lockfile を書き換えない。
    assert MOD.main(["--write", "--root", str(root)]) == 1
    assert (root / MOD.LOCK_NAME).read_text(encoding="utf-8") == lock_before

    # version を bump すると --write が通り、以後 check も緑。
    _bump(root, "0.1.1")
    assert MOD.main(["--write", "--root", str(root)]) == 0
    assert MOD.main(["--root", str(root)]) == 0


def test_write_refuses_marketplace_mismatch(tmp_path):
    root = tmp_path / "repo"
    root.mkdir()
    _make_repo(root, version="0.1.0")
    assert MOD.main(["--write", "--root", str(root)]) == 0
    # plugin.json だけ bump (marketplace 据え置き) → 不整合で write 拒否。
    pj = root / "plugins" / "p" / ".claude-plugin" / "plugin.json"
    pj.write_text(json.dumps({"name": "p", "version": "0.1.1"}), encoding="utf-8")
    assert MOD.main(["--write", "--root", str(root)]) == 1


# --------------------------------------------------------------------------
# 実 repo の番人: 委員会が忘れても CI が config↔version の乖離を捕まえる
# --------------------------------------------------------------------------
def test_repo_lockfile_is_in_sync():
    current = MOD.build_current_state(MOD.ROOT)
    lock = MOD.load_lock(MOD.ROOT)
    mkt = MOD.read_marketplace_versions(MOD.ROOT)
    assert MOD.evaluate(current, lock, mkt) == []
