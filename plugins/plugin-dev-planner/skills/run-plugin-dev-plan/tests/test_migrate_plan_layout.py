from __future__ import annotations

import importlib.util
import json
import sys
from pathlib import Path

import pytest

SCRIPTS = Path(__file__).resolve().parent.parent / "scripts"
sys.path.insert(0, str(SCRIPTS))


def _load(stem):
    spec = importlib.util.spec_from_file_location(stem.replace("-", "_"), SCRIPTS / f"{stem}.py")
    m = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(m)
    return m


mpl = _load("migrate-plan-layout")
cpl = _load("check-plan-ledger")


def _flat_plan(tmp_path, slug="myslug", files=("phase-01.md", "index.md")) -> Path:
    old = tmp_path / "plugin-plans" / slug
    old.mkdir(parents=True)
    for name in files:
        (old / name).write_text(f"# {name}\n", encoding="utf-8")
    return old


def _tree(root: Path) -> dict:
    """root 配下の dir と file の中身を相対 path で写し取る (止まったとき何も動いていないことの比較用)。"""
    return {
        str(p.relative_to(root)): (p.read_bytes() if p.is_file() else "<dir>")
        for p in sorted(root.rglob("*"))
    }


def _plan_dirs_exist(tmp_path: Path, old: Path) -> None:
    """台帳の各 entry の plan_dir (repo-root 相対) が実在する dir を指すこと。"""
    ledger = json.loads((old / "plan-ledger.json").read_text(encoding="utf-8"))
    for entry in ledger["entries"]:
        assert (tmp_path / entry["plan_dir"]).is_dir(), entry


# ─────────── 受入例: flat → cycle スコープ移行 ───────────
def test_migrate_moves_files_and_writes_ledger(tmp_path):
    old = _flat_plan(tmp_path)
    result = mpl.migrate(old, "myslug", "20260705-abc")

    target = old / "20260705-abc"
    # ファイルが cycle スコープ配下へ移動
    assert (target / "phase-01.md").is_file()
    assert (target / "index.md").is_file()
    assert not (old / "phase-01.md").exists()
    assert set(result["moved"]) == {"phase-01.md", "index.md"}
    assert result["cycle_id"] == "20260705-abc"

    # plan-ledger.json は slug 直下 (cycle スコープ外) に残る
    ledger_path = old / "plan-ledger.json"
    assert Path(result["ledger_path"]) == ledger_path
    assert ledger_path.is_file()
    assert not (target / "plan-ledger.json").exists()

    ledger = json.loads(ledger_path.read_text(encoding="utf-8"))
    entry = ledger["entries"][-1]
    assert entry["cycle_id"] == "20260705-abc"
    assert entry["status"] == "active"
    assert entry["plan_dir"] == "plugin-plans/myslug/20260705-abc"
    assert entry["summary"]
    # validate_ledger が exit0 相当 (違反なし)
    assert cpl.validate_ledger(ledger) == []


def test_migrate_creates_new_ledger_when_absent(tmp_path):
    old = _flat_plan(tmp_path)
    assert not (old / "plan-ledger.json").exists()
    mpl.migrate(old, "myslug", "20260705-abc")
    assert (old / "plan-ledger.json").is_file()


# ─────────── 同時 active 重複拒否 ───────────
def test_migrate_rejects_second_active(tmp_path):
    old = _flat_plan(tmp_path)
    mpl.migrate(old, "myslug", "20260705-abc")  # 1 件目 active
    # 別 cycle を再度 active で足そうとすると同時 active 重複で ValueError
    (old / "phase-02.md").write_text("# next\n", encoding="utf-8")
    before = _tree(old)
    with pytest.raises(ValueError) as ei:
        mpl.migrate(old, "myslug", "20260706-def", status="active")
    assert "active" in str(ei.value)
    # 台帳の検証は動かす前に行うので、止まったとき何も動いていない
    assert _tree(old) == before
    assert not (old / "20260706-def").exists()


def test_migrate_second_cycle_ok_when_prior_finished(tmp_path):
    old = _flat_plan(tmp_path)
    mpl.migrate(old, "myslug", "20260705-abc", status="finished")  # 1 件目 finished
    (old / "phase-02.md").write_text("# next\n", encoding="utf-8")
    # 既存が finished なら新規 active は同時 active 重複にならない
    result = mpl.migrate(old, "myslug", "20260706-def", status="active")
    assert result["cycle_id"] == "20260706-def"
    ledger = json.loads((old / "plan-ledger.json").read_text(encoding="utf-8"))
    assert cpl.validate_ledger(ledger) == []
    # 前の cycle の dir は動かず、今回の cycle には flat に残っていたファイルだけが入る
    assert result["moved"] == ["phase-02.md"]
    assert sorted(p.name for p in (old / "20260705-abc").iterdir()) == ["index.md", "phase-01.md"]
    assert sorted(p.name for p in (old / "20260706-def").iterdir()) == ["phase-02.md"]
    _plan_dirs_exist(tmp_path, old)


# ─────────── cycle_id / status バリデーション ───────────
def test_migrate_rejects_bad_cycle_id(tmp_path):
    old = _flat_plan(tmp_path)
    with pytest.raises(ValueError) as ei:
        mpl.migrate(old, "myslug", "bad")
    assert "cycle_id" in str(ei.value)


def test_migrate_rejects_bad_status(tmp_path):
    old = _flat_plan(tmp_path)
    with pytest.raises(ValueError) as ei:
        mpl.migrate(old, "myslug", "20260705-abc", status="wip")
    assert "status" in str(ei.value)


def test_migrate_custom_summary(tmp_path):
    old = _flat_plan(tmp_path)
    mpl.migrate(old, "myslug", "20260705-abc", summary="独自サマリ")
    ledger = json.loads((old / "plan-ledger.json").read_text(encoding="utf-8"))
    assert ledger["entries"][-1]["summary"] == "独自サマリ"


# ─────────── main (CLI 経路 + exit code) ───────────
def test_main_exit0_and_json_stdout(tmp_path, capsys):
    old = _flat_plan(tmp_path)
    rc = mpl.main(["--old-plan-dir", str(old), "--slug", "myslug", "--cycle-id", "20260705-abc"])
    assert rc == 0
    out = json.loads(capsys.readouterr().out)
    assert out["cycle_id"] == "20260705-abc"
    assert (old / "20260705-abc" / "phase-01.md").is_file()


def test_main_exit1_on_bad_cycle_id(tmp_path):
    old = _flat_plan(tmp_path)
    rc = mpl.main(["--old-plan-dir", str(old), "--slug", "myslug", "--cycle-id", "bad"])
    assert rc == 1


def test_main_exit1_on_duplicate_active(tmp_path):
    old = _flat_plan(tmp_path)
    mpl.main(["--old-plan-dir", str(old), "--slug", "myslug", "--cycle-id", "20260705-abc"])
    (old / "phase-02.md").write_text("# next\n", encoding="utf-8")
    rc = mpl.main(["--old-plan-dir", str(old), "--slug", "myslug", "--cycle-id", "20260706-def"])
    assert rc == 1


def test_main_exit2_on_missing_required_arg(tmp_path):
    with pytest.raises(SystemExit) as ei:
        mpl.main(["--slug", "myslug"])
    assert ei.value.code == 2


# ─────────── 止まるときは動かす前に止まる ───────────
def _cli(old: Path, cycle_id: str, *extra: str, slug: str = "myslug") -> int:
    return mpl.main(["--old-plan-dir", str(old), "--slug", slug, "--cycle-id", cycle_id, *extra])


@pytest.mark.parametrize(
    "ledger_text",
    [
        "{not json",  # JSON として読めない
        "[]",  # root が object でない
        '{"schema_version": "1.0", "entries": {}}',  # entries が配列でない (以前は AttributeError の traceback)
        '{"schema_version": "1.0", "entries": [{"cycle_id": "bad"}]}',  # 既存 entry が不正
    ],
)
def test_broken_ledger_stops_before_moving(tmp_path, capsys, ledger_text):
    old = _flat_plan(tmp_path)
    (old / "plan-ledger.json").write_text(ledger_text, encoding="utf-8")
    before = _tree(old)
    assert _cli(old, "20260705-abc") == 1
    assert _tree(old) == before
    assert "Traceback" not in capsys.readouterr().err


def test_ledger_path_that_is_a_dir_stops_before_moving(tmp_path):
    old = _flat_plan(tmp_path)
    (old / "plan-ledger.json").mkdir()
    before = _tree(old)
    assert _cli(old, "20260705-abc") == 1
    assert _tree(old) == before


def test_move_failure_restores_moved_files(tmp_path, monkeypatch):
    """2 件目の移動で落ちたら、1 件目を元の場所へ戻し、作った cycle の dir も残さない。"""
    old = _flat_plan(tmp_path)
    before = _tree(old)
    real_move = mpl.shutil.move
    calls = []

    def flaky_move(src, dst):
        calls.append(src)
        if len(calls) == 2:
            raise OSError("disk full (test)")
        return real_move(src, dst)

    monkeypatch.setattr(mpl.shutil, "move", flaky_move)
    with pytest.raises(OSError):
        mpl.migrate(old, "myslug", "20260705-abc")
    assert _tree(old) == before


def test_ledger_write_failure_restores_moved_files(tmp_path, monkeypatch):
    """すべて動かした後で台帳の書き込みに失敗しても、ファイルを戻し台帳は書かない。"""
    old = _flat_plan(tmp_path)
    before = _tree(old)

    def boom(path, ledger):
        raise OSError("write failed (test)")

    monkeypatch.setattr(mpl, "_write_ledger", boom, raising=False)
    with pytest.raises(OSError):
        mpl.migrate(old, "myslug", "20260705-abc")
    assert _tree(old) == before


def test_main_exit1_without_traceback_when_move_fails(tmp_path, monkeypatch, capsys):
    old = _flat_plan(tmp_path)
    before = _tree(old)

    def broken_move(src, dst):
        raise OSError("permission denied (test)")

    monkeypatch.setattr(mpl.shutil, "move", broken_move)
    assert _cli(old, "20260705-abc") == 1
    assert "permission denied" in capsys.readouterr().err
    assert _tree(old) == before


# ─────────── 引数の誤り (exit 2) と二重の移行 ───────────
def test_nonexistent_old_plan_dir_is_usage_error_and_creates_nothing(tmp_path):
    missing = tmp_path / "typo" / "myslug"
    assert _cli(missing, "20260705-abc") == 2
    assert not (tmp_path / "typo").exists()


def test_slug_must_match_old_plan_dir_name(tmp_path):
    old = _flat_plan(tmp_path, slug="realslug")
    before = _tree(old)
    assert _cli(old, "20260705-abc", slug="other") == 2
    assert _tree(old) == before
    # plan_slug で正規化した名前が dir 名と合えば通る
    assert _cli(old, "20260705-abc", slug="RealSlug") == 0
    _plan_dirs_exist(tmp_path, old)


def test_old_plan_dir_outside_plugin_plans_is_usage_error(tmp_path):
    # 台帳の plan_dir は plugin-plans/<slug>/<cycle_id> と書くので、別の親の下の dir は実在しない path を残す
    old = tmp_path / "elsewhere" / "myslug"
    old.mkdir(parents=True)
    (old / "index.md").write_text("# index\n", encoding="utf-8")
    before = _tree(tmp_path)
    assert _cli(old, "20260705-abc") == 2
    assert _tree(tmp_path) == before


@pytest.mark.parametrize("target", ["finish", "finish/done-slug"])
def test_finish_area_is_usage_error_and_untouched(tmp_path, target):
    """完了 plan の置き場 plugin-plans/finish/ は、--slug finish でも finish/<slug> でも動かさない。"""
    done = tmp_path / "plugin-plans" / "finish" / "done-slug"
    done.mkdir(parents=True)
    (done / "index.md").write_text("# done\n", encoding="utf-8")
    old = tmp_path / "plugin-plans" / target
    before = _tree(tmp_path)
    assert _cli(old, "20260705-abc", slug=old.name) == 2
    assert _tree(tmp_path) == before


def test_same_cycle_id_twice_is_rejected(tmp_path):
    old = _flat_plan(tmp_path)
    mpl.migrate(old, "myslug", "20260705-abc", status="finished")
    (old / "phase-02.md").write_text("# next\n", encoding="utf-8")
    before = _tree(old)
    with pytest.raises(ValueError) as ei:
        mpl.migrate(old, "myslug", "20260705-abc", status="finished")
    assert "20260705-abc" in str(ei.value)
    assert _tree(old) == before
    ledger = json.loads((old / "plan-ledger.json").read_text(encoding="utf-8"))
    assert [e["cycle_id"] for e in ledger["entries"]] == ["20260705-abc"]


def test_nothing_left_to_migrate_is_rejected(tmp_path):
    """flat に移すファイルが残っていない 2 回目は、前の cycle を動かさず空の cycle も作らない。"""
    old = _flat_plan(tmp_path)
    mpl.migrate(old, "myslug", "20260705-abc", status="finished")
    before = _tree(old)
    assert _cli(old, "20260706-def") == 1
    assert _tree(old) == before
    _plan_dirs_exist(tmp_path, old)


def test_unregistered_cycle_dir_is_not_moved(tmp_path):
    """cycle_id の形の dir は台帳に無くても cycle スコープとみなし、flat のファイルとして動かさない。"""
    old = _flat_plan(tmp_path)
    (old / "20260601-older").mkdir()
    (old / "20260601-older" / "phase-01.md").write_text("# older\n", encoding="utf-8")
    result = mpl.migrate(old, "myslug", "20260705-abc")
    assert sorted(result["moved"]) == ["index.md", "phase-01.md"]
    assert (old / "20260601-older" / "phase-01.md").read_text(encoding="utf-8") == "# older\n"


def test_name_clash_in_existing_cycle_dir_stops_before_moving(tmp_path):
    """移動先に同じ名前があるときは上書きせず、動かす前に止まる。"""
    old = _flat_plan(tmp_path)
    (old / "20260705-abc").mkdir()
    (old / "20260705-abc" / "index.md").write_text("# keep\n", encoding="utf-8")
    before = _tree(old)
    assert _cli(old, "20260705-abc") == 1
    assert _tree(old) == before
