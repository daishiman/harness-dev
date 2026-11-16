"""Genuine functional tests for plugins/harness-creator/scripts/install-codex-plugin.py.

この helper は、明示依頼された local / Git marketplace の plugin を Codex CLI へ登録・install し、
receipt を返す。ここでは、2 段めの承認を機械で守る境目を固定する。

- `--approved-plugin` を渡したとき、入れる集合 (install_order) が承認した集合と違えば、
  `plugin add` を 1 度も呼ばずに exit 3 で止まる。local は CLI を呼ぶ前、Git は snapshot を
  読んだ後に照合する。
- Git source に `--approved-plugin` を渡すときは、`--ref` に 40 桁の commit SHA が要る。
- snapshot の実際の commit (install metadata の revision と、snapshot root の git HEAD) が
  固定した SHA と違えば、`plugin add` を呼ばずに止まる。2 つの出所が食い違えば止まる。
- すでに固定した SHA にある snapshot は upgrade しない。
- 成功時の receipt に、approved_plugins・install_order・resolved_revision が載る。
- 固定した SHA の checkout に未 commit の変更 (untracked を含む) があれば止まる。install metadata は数えない。
  revision が文字列でないなど証拠が壊れていても止まる。
- add の後に snapshot の commit を読み直し、動いていれば止まる。add の前の list に無く、
  入れる集合にも無い plugin が現れたら止まる (前から入っていた plugin は数えない)。
- 途中で止まっても traceback にせず、phase・added_plugins・failed_plugin・unexpected_plugins を
  載せた receipt を exit 3 で返す。非 UTF-8 の CLI 出力やファイル、型の違う field も同じ。
- version が同じでも runtime の中身が source と違えば stale_runtime で exit 1 にする。依存の側だけが
  stale でも、top-level の verified は全件の集計なので false になる。
- 依存が循環しても、top-level の plugin は要求した plugin になる。
- 1 回だけの引数の重複と、空の --codex-home は exit 2 にする。

Codex CLI は tmp_path に置いた偽の `codex` で置き換える。偽の CLI は受け取った argv を
log に 1 行ずつ書くので、「何も入れずに止まった」ことを log から確かめられる。
fixture はすべて tmp_path の下に作り、repo と利用者の ~/.codex には触れない。
"""
import importlib.util
import json
import os
import subprocess
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[2]
SCRIPT = ROOT / "plugins" / "harness-creator" / "scripts" / "install-codex-plugin.py"

_SPEC = importlib.util.spec_from_file_location("install_codex_plugin_t1", SCRIPT)
ICP = importlib.util.module_from_spec(_SPEC)
_SPEC.loader.exec_module(ICP)

SHA_A = "a" * 40
SHA_B = "b" * 40
GIT_SOURCE = "https://example.invalid/owner/marketplace.git"

_FAKE_CODEX = """\
import json
import os
import sys

args = sys.argv[1:]
log_path = os.environ["FAKE_CODEX_LOG"]
prior = []
if os.path.exists(log_path):
    with open(log_path, encoding="utf-8") as fh:
        prior = [json.loads(line) for line in fh.read().splitlines()]
with open(log_path, "a", encoding="utf-8") as fh:
    fh.write(json.dumps(args) + "\\n")
with open(os.environ["FAKE_CODEX_CONFIG"], encoding="utf-8") as fh:
    cfg = json.load(fh)


def writes(event):
    # 副作用を真似る: upgrade や add の間に snapshot のファイルを書き換える
    for path, text in cfg.get("writes", {}).get(event, []):
        with open(path, "w", encoding="utf-8") as fh:
            fh.write(text)


def emit(out):
    if isinstance(out, dict) and "__raw_hex__" in out:
        sys.stdout.buffer.write(bytes.fromhex(out["__raw_hex__"]))
        sys.exit(0)
    print(json.dumps(out))


if args == ["--version"]:
    print(cfg.get("version", "codex-cli 0.0.0-test"))
    sys.exit(0)
if args[:3] == ["plugin", "marketplace", "add"]:
    out = cfg["marketplace_add"]
elif args[:3] == ["plugin", "marketplace", "list"]:
    out = cfg["marketplace_list"]
elif args[:3] == ["plugin", "marketplace", "upgrade"]:
    writes("upgrade")
    out = cfg.get("marketplace_upgrade", {})
elif args[:2] == ["plugin", "add"]:
    if args[2] in cfg.get("fail_add", []):
        print("plugin add failed: " + args[2], file=sys.stderr)
        sys.exit(1)
    writes("add")
    out = cfg.get("plugin_add", {}).get(args[2], {"pluginId": args[2]})
elif args[:2] == ["plugin", "list"]:
    added_before = any(call[:2] == ["plugin", "add"] for call in prior)
    out = cfg.get("plugin_list_after_add", cfg["plugin_list"]) if added_before else cfg["plugin_list"]
else:
    print("unexpected command: " + " ".join(args), file=sys.stderr)
    sys.exit(9)
emit(out)
"""


def _write_json(path: Path, payload: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload), encoding="utf-8")


def _marketplace(root: Path, name: str = "mk") -> Path:
    """plugin a が b に依存する marketplace を作る (a の閉包は b → a の順)。"""
    _write_json(root / ".agents" / "plugins" / "marketplace.json", {
        "name": name,
        "plugins": [
            {"name": "a", "source": {"source": "local", "path": "./plugins/a"}},
            {"name": "b", "source": {"source": "local", "path": "./plugins/b"}},
            {"name": "c", "source": {"source": "local", "path": "./plugins/c"}},
        ],
    })
    for plugin in ("a", "b", "c"):
        _write_json(root / "plugins" / plugin / ".codex-plugin" / "plugin.json",
                    {"name": plugin, "version": "1.0.0"})
    _write_json(root / "plugins" / "a" / "references" / "package-contract.json",
                {"plugin_name": "a", "depends_on": ["b"]})
    return root


def _installed(root: Path, names, marketplace: str = "mk") -> dict:
    return {"installed": [
        {"pluginId": f"{n}@{marketplace}", "installed": True, "enabled": True,
         "version": "1.0.0", "source": {"path": str(root / "plugins" / n)}}
        for n in names
    ]}


class FakeCodex:
    def __init__(self, tmp_path: Path, monkeypatch):
        self.bin = tmp_path / "fake-bin"
        self.bin.mkdir()
        exe = self.bin / "codex"
        exe.write_text(f"#!{sys.executable}\n" + _FAKE_CODEX, encoding="utf-8")
        exe.chmod(0o755)
        self.log = tmp_path / "codex-calls.jsonl"
        self.config = tmp_path / "codex-config.json"
        monkeypatch.setenv("PATH", str(self.bin) + os.pathsep + os.environ.get("PATH", ""))
        monkeypatch.setenv("FAKE_CODEX_LOG", str(self.log))
        monkeypatch.setenv("FAKE_CODEX_CONFIG", str(self.config))
        self.configure({})

    def configure(self, cfg: dict) -> None:
        self.config.write_text(json.dumps(cfg), encoding="utf-8")

    def calls(self) -> list:
        if not self.log.is_file():
            return []
        return [json.loads(line) for line in self.log.read_text(encoding="utf-8").splitlines()]

    def plugin_adds(self) -> list:
        return [c for c in self.calls() if c[:2] == ["plugin", "add"]]

    def upgrades(self) -> list:
        return [c for c in self.calls() if c[:3] == ["plugin", "marketplace", "upgrade"]]


@pytest.fixture
def codex(tmp_path, monkeypatch):
    return FakeCodex(tmp_path, monkeypatch)


def _run(capsys, argv, codex_home: Path):
    code = ICP.main([*argv, "--codex-home", str(codex_home)])
    return code, json.loads(capsys.readouterr().out)


def _git_snapshot_fixture(tmp_path: Path, codex: FakeCodex, *, revision: str,
                          already_added: bool = False) -> Path:
    snapshot = _marketplace(tmp_path / "snapshot")
    _write_json(snapshot / ICP._INSTALL_METADATA, {"revision": revision})
    codex.configure({
        "marketplace_add": {"marketplaceName": "mk", "alreadyAdded": already_added},
        "marketplace_list": {"marketplaces": [{"name": "mk", "root": str(snapshot)}]},
        "plugin_list": _installed(snapshot, ["a", "b"]),
    })
    return snapshot


# ---------- 承認した集合との照合 (純関数) ----------

def test_check_approved_set_none_means_no_check():
    ICP._check_approved_set(("b", "a"), None)


def test_check_approved_set_equal_sets_pass_in_any_order():
    ICP._check_approved_set(("b", "a"), ("a", "b"))


@pytest.mark.parametrize("approved, needle", [
    (("a",), "unapproved=['b']"),
    (("a", "b", "c"), "approved_but_not_in_closure=['c']"),
])
def test_check_approved_set_mismatch_names_the_difference(approved, needle):
    with pytest.raises(ICP.InstallError) as exc:
        ICP._check_approved_set(("b", "a"), approved)
    assert "no plugin was added" in str(exc.value)
    assert needle in str(exc.value)


# ---------- local source ----------

def test_local_approved_mismatch_stops_before_any_cli_call(tmp_path, codex, capsys):
    root = _marketplace(tmp_path / "repo")
    code, report = _run(capsys, ["--source", str(root), "--plugin", "a",
                                 "--approved-plugin", "a"], tmp_path / "home")
    assert code == 3
    assert report["status"] == "invalid"
    assert "unapproved=['b']" in report["error"]
    # local の集合は CLI を変える前に決まるので、marketplace add すら呼ばない
    assert codex.calls() == []


def test_local_approved_superset_also_stops(tmp_path, codex, capsys):
    root = _marketplace(tmp_path / "repo")
    code, report = _run(capsys, ["--source", str(root), "--plugin", "a",
                                 "--approved-plugin", "a", "--approved-plugin", "b",
                                 "--approved-plugin", "c"], tmp_path / "home")
    assert code == 3
    assert "approved_but_not_in_closure=['c']" in report["error"]
    assert codex.calls() == []


def test_local_approved_equal_installs_closure_in_order(tmp_path, codex, capsys):
    root = _marketplace(tmp_path / "repo")
    codex.configure({
        "marketplace_add": {"marketplaceName": "mk"},
        "plugin_list": _installed(root, ["a", "b"]),
    })
    code, report = _run(capsys, ["--source", str(root), "--plugin", "a",
                                 "--approved-plugin", "b", "--approved-plugin", "a"],
                        tmp_path / "home")
    assert code == 0, report
    assert report["verified"] is True
    assert report["install_order"] == ["b", "a"]
    assert report["dependency_closure"] == ["b"]
    assert report["approved_plugins"] == ["b", "a"]
    assert report["resolved_revision"] is None
    assert [c[2] for c in codex.plugin_adds()] == ["b@mk", "a@mk"]


def test_local_without_approved_keeps_previous_behaviour(tmp_path, codex, capsys):
    root = _marketplace(tmp_path / "repo")
    codex.configure({
        "marketplace_add": {"marketplaceName": "mk"},
        "plugin_list": _installed(root, ["a", "b"]),
    })
    code, report = _run(capsys, ["--source", str(root), "--plugin", "a"], tmp_path / "home")
    assert code == 0, report
    assert report["approved_plugins"] is None
    assert len(codex.plugin_adds()) == 2


def test_local_ref_is_rejected(tmp_path, codex, capsys):
    root = _marketplace(tmp_path / "repo")
    code, report = _run(capsys, ["--source", str(root), "--plugin", "a",
                                 "--ref", SHA_A], tmp_path / "home")
    assert code == 3
    assert "--ref is valid only for Git" in report["error"]
    assert codex.calls() == []


def test_duplicate_approved_names_are_rejected(tmp_path, codex, capsys):
    root = _marketplace(tmp_path / "repo")
    code, report = _run(capsys, ["--source", str(root), "--plugin", "a",
                                 "--approved-plugin", "a", "--approved-plugin", "a"],
                        tmp_path / "home")
    assert code == 3
    assert "duplicate" in report["error"]
    assert codex.calls() == []


# ---------- Git source: SHA の固定 ----------

@pytest.mark.parametrize("ref", [None, "main", "a" * 39, "a" * 41, "g" * 40, "v1.0.0"])
def test_git_approved_requires_40_hex_ref(tmp_path, codex, capsys, ref):
    argv = ["--source", GIT_SOURCE, "--plugin", "a", "--approved-plugin", "a",
            "--approved-plugin", "b"]
    if ref is not None:
        argv += ["--ref", ref]
    code, report = _run(capsys, argv, tmp_path / "home")
    assert code == 3
    assert "40-hex commit SHA" in report["error"]
    assert codex.calls() == []


def test_git_uppercase_sha_is_accepted_as_pinned(tmp_path, codex, capsys):
    _git_snapshot_fixture(tmp_path, codex, revision=SHA_A)
    code, report = _run(capsys, ["--source", GIT_SOURCE, "--plugin", "a",
                                 "--ref", SHA_A.upper(), "--approved-plugin", "a",
                                 "--approved-plugin", "b"], tmp_path / "home")
    assert code == 0, report
    assert report["resolved_revision"] == SHA_A
    # Codex への引数と receipt の ref も、照合と同じ小文字の綴りにそろう
    assert report["ref"] == SHA_A
    add = next(c for c in codex.calls() if c[:3] == ["plugin", "marketplace", "add"])
    assert add[add.index("--ref") + 1] == SHA_A


def test_git_pinned_and_matching_snapshot_installs(tmp_path, codex, capsys):
    _git_snapshot_fixture(tmp_path, codex, revision=SHA_A)
    code, report = _run(capsys, ["--source", GIT_SOURCE, "--plugin", "a", "--ref", SHA_A,
                                 "--approved-plugin", "a", "--approved-plugin", "b"],
                        tmp_path / "home")
    assert code == 0, report
    assert report["resolved_revision"] == SHA_A
    assert report["ref"] == SHA_A
    assert report["revision_evidence"]["install_metadata_revision"] == SHA_A
    assert report["install_order"] == ["b", "a"]
    assert [c[2] for c in codex.plugin_adds()] == ["b@mk", "a@mk"]
    add = next(c for c in codex.calls() if c[:3] == ["plugin", "marketplace", "add"])
    assert add[add.index("--ref") + 1] == SHA_A


def test_git_snapshot_at_other_commit_stops_before_plugin_add(tmp_path, codex, capsys):
    _git_snapshot_fixture(tmp_path, codex, revision=SHA_B)
    code, report = _run(capsys, ["--source", GIT_SOURCE, "--plugin", "a", "--ref", SHA_A,
                                 "--approved-plugin", "a", "--approved-plugin", "b"],
                        tmp_path / "home")
    assert code == 3
    assert "not at the pinned commit" in report["error"]
    assert f"snapshot={SHA_B}" in report["error"]
    assert codex.plugin_adds() == []


def test_git_snapshot_without_revision_evidence_stops(tmp_path, codex, capsys):
    snapshot = _git_snapshot_fixture(tmp_path, codex, revision=SHA_A)
    (snapshot / ICP._INSTALL_METADATA).unlink()
    code, report = _run(capsys, ["--source", GIT_SOURCE, "--plugin", "a", "--ref", SHA_A,
                                 "--approved-plugin", "a", "--approved-plugin", "b"],
                        tmp_path / "home")
    assert code == 3
    assert "snapshot=None" in report["error"]
    assert codex.plugin_adds() == []


def test_git_closure_differs_from_approved_stops_before_plugin_add(tmp_path, codex, capsys):
    _git_snapshot_fixture(tmp_path, codex, revision=SHA_A)
    code, report = _run(capsys, ["--source", GIT_SOURCE, "--plugin", "a", "--ref", SHA_A,
                                 "--approved-plugin", "a"], tmp_path / "home")
    assert code == 3
    assert "unapproved=['b']" in report["error"]
    assert codex.plugin_adds() == []


def test_git_already_added_at_pinned_commit_is_not_upgraded(tmp_path, codex, capsys):
    _git_snapshot_fixture(tmp_path, codex, revision=SHA_A, already_added=True)
    code, report = _run(capsys, ["--source", GIT_SOURCE, "--plugin", "a", "--ref", SHA_A,
                                 "--approved-plugin", "a", "--approved-plugin", "b"],
                        tmp_path / "home")
    assert code == 0, report
    assert codex.upgrades() == []


def test_git_already_added_elsewhere_is_upgraded_then_rechecked(tmp_path, codex, capsys):
    # upgrade しても snapshot が固定した SHA に来なければ、何も入れずに止まる
    _git_snapshot_fixture(tmp_path, codex, revision=SHA_B, already_added=True)
    code, report = _run(capsys, ["--source", GIT_SOURCE, "--plugin", "a", "--ref", SHA_A,
                                 "--approved-plugin", "a", "--approved-plugin", "b"],
                        tmp_path / "home")
    assert code == 3
    assert len(codex.upgrades()) == 1
    assert "not at the pinned commit" in report["error"]
    assert codex.plugin_adds() == []


def test_git_without_approved_and_branch_ref_keeps_previous_behaviour(tmp_path, codex, capsys):
    _git_snapshot_fixture(tmp_path, codex, revision=SHA_B)
    code, report = _run(capsys, ["--source", GIT_SOURCE, "--plugin", "a", "--ref", "main"],
                        tmp_path / "home")
    assert code == 0, report
    assert report["ref"] == "main"
    assert report["resolved_revision"] == SHA_B
    assert report["approved_plugins"] is None


# ---------- snapshot の commit を実物から読む ----------

def _git(cwd: Path, *args: str) -> str:
    return subprocess.run(
        ["git", "-C", str(cwd), "-c", "user.email=t@example.invalid", "-c", "user.name=t",
         "-c", "commit.gpgsign=false", "-c", "core.hooksPath=/dev/null", *args],
        check=True, capture_output=True, text=True,
    ).stdout.strip()


@pytest.fixture
def git_snapshot(tmp_path):
    repo = tmp_path / "snap"
    repo.mkdir()
    _git(repo, "init", "-q")
    _git(repo, "commit", "-q", "--allow-empty", "-m", "init")
    return repo, _git(repo, "rev-parse", "HEAD")


def test_snapshot_revision_reads_git_head_when_no_metadata(git_snapshot):
    repo, head = git_snapshot
    rev = ICP._snapshot_revision(repo)
    assert rev == {"revision": head, "install_metadata_revision": None, "git_head": head,
                   "git_dirty": False}


def test_snapshot_revision_agreeing_sources(git_snapshot):
    repo, head = git_snapshot
    _write_json(repo / ICP._INSTALL_METADATA, {"revision": head.upper()})
    assert ICP._snapshot_revision(repo)["revision"] == head


def test_snapshot_revision_disagreeing_sources_stop(git_snapshot):
    repo, head = git_snapshot
    other = SHA_B if head != SHA_B else SHA_A
    _write_json(repo / ICP._INSTALL_METADATA, {"revision": other})
    with pytest.raises(ICP.InstallError) as exc:
        ICP._snapshot_revision(repo)
    assert "disagrees" in str(exc.value)


def test_snapshot_revision_ignores_head_of_enclosing_repository(git_snapshot):
    repo, _head = git_snapshot
    nested = repo / "nested-snapshot"
    nested.mkdir()
    rev = ICP._snapshot_revision(nested)
    assert rev["git_head"] is None
    assert rev["revision"] is None


# ---------- Git source: 正の側の e2e (upgrade の後と、git HEAD だけの固定) ----------

_PINNED_ARGS = ["--plugin", "a", "--approved-plugin", "a", "--approved-plugin", "b"]


def test_git_upgrade_brings_snapshot_to_pinned_commit_then_installs(tmp_path, codex, capsys):
    # alreadyAdded で snapshot は SHA_B。upgrade が SHA_A へ動かせば、そのまま入る
    snapshot = _git_snapshot_fixture(tmp_path, codex, revision=SHA_B, already_added=True)
    cfg = json.loads(codex.config.read_text(encoding="utf-8"))
    cfg["writes"] = {"upgrade": [[str(snapshot / ICP._INSTALL_METADATA),
                                  json.dumps({"revision": SHA_A})]]}
    codex.configure(cfg)
    code, report = _run(capsys, ["--source", GIT_SOURCE, "--ref", SHA_A, *_PINNED_ARGS],
                        tmp_path / "home")
    assert code == 0, report
    assert len(codex.upgrades()) == 1
    assert report["resolved_revision"] == SHA_A
    assert report["revision_evidence"]["rechecked_after_plugin_add"] is True
    assert [c[2] for c in codex.plugin_adds()] == ["b@mk", "a@mk"]


def _git_checkout_fixture(tmp_path: Path, codex: FakeCodex, *, already_added: bool = False):
    """snapshot root そのものが git checkout で、install metadata を持たない形。"""
    snapshot = _marketplace(tmp_path / "checkout")
    _git(snapshot, "init", "-q")
    _git(snapshot, "add", "-A")
    _git(snapshot, "commit", "-q", "-m", "snapshot")
    codex.configure({
        "marketplace_add": {"marketplaceName": "mk", "alreadyAdded": already_added},
        "marketplace_list": {"marketplaces": [{"name": "mk", "root": str(snapshot)}]},
        "plugin_list": _installed(snapshot, ["a", "b"]),
    })
    return snapshot, _git(snapshot, "rev-parse", "HEAD")


def test_git_head_alone_satisfies_pin(tmp_path, codex, capsys):
    snapshot, head = _git_checkout_fixture(tmp_path, codex)
    code, report = _run(capsys, ["--source", GIT_SOURCE, "--ref", head, *_PINNED_ARGS],
                        tmp_path / "home")
    assert code == 0, report
    assert report["resolved_revision"] == head
    assert report["revision_evidence"]["install_metadata_revision"] is None
    assert report["revision_evidence"]["git_head"] == head
    assert report["revision_evidence"]["git_dirty"] is False
    assert len(codex.plugin_adds()) == 2


def test_git_untracked_install_metadata_is_not_dirty(tmp_path, codex, capsys):
    # Codex が書く install metadata は checkout の外の物なので、dirty と見なさない
    snapshot, head = _git_checkout_fixture(tmp_path, codex)
    _write_json(snapshot / ICP._INSTALL_METADATA, {"revision": head})
    code, report = _run(capsys, ["--source", GIT_SOURCE, "--ref", head, *_PINNED_ARGS],
                        tmp_path / "home")
    assert code == 0, report
    assert report["revision_evidence"]["install_metadata_revision"] == head


@pytest.mark.parametrize("change", ["modify", "untracked"])
def test_git_dirty_checkout_at_pinned_commit_stops_before_plugin_add(
    tmp_path, codex, capsys, change
):
    snapshot, head = _git_checkout_fixture(tmp_path, codex)
    if change == "modify":
        _write_json(snapshot / "plugins" / "b" / ".codex-plugin" / "plugin.json",
                    {"name": "b", "version": "1.0.0", "hooks": "./hooks/evil.json"})
    else:
        (snapshot / "plugins" / "b" / "extra.sh").write_text("echo x\n", encoding="utf-8")
    code, report = _run(capsys, ["--source", GIT_SOURCE, "--ref", head, *_PINNED_ARGS],
                        tmp_path / "home")
    assert code == 3
    assert "uncommitted changes" in report["error"]
    assert report["phase"] == "snapshot-check"
    assert report["added_plugins"] == []
    assert codex.plugin_adds() == []


def test_git_metadata_and_head_disagree_stops_before_upgrade(tmp_path, codex, capsys):
    snapshot, head = _git_checkout_fixture(tmp_path, codex, already_added=True)
    other = SHA_B if head != SHA_B else SHA_A
    _write_json(snapshot / ICP._INSTALL_METADATA, {"revision": other})
    code, report = _run(capsys, ["--source", GIT_SOURCE, "--ref", head, *_PINNED_ARGS],
                        tmp_path / "home")
    assert code == 3
    assert "disagrees" in report["error"]
    assert codex.upgrades() == []
    assert codex.plugin_adds() == []


def test_git_snapshot_moving_during_plugin_add_is_reported(tmp_path, codex, capsys):
    snapshot = _git_snapshot_fixture(tmp_path, codex, revision=SHA_A)
    cfg = json.loads(codex.config.read_text(encoding="utf-8"))
    cfg["writes"] = {"add": [[str(snapshot / ICP._INSTALL_METADATA),
                              json.dumps({"revision": SHA_B})]]}
    codex.configure(cfg)
    code, report = _run(capsys, ["--source", GIT_SOURCE, "--ref", SHA_A, *_PINNED_ARGS],
                        tmp_path / "home")
    assert code == 3
    assert "changed while plugins were added" in report["error"]
    assert report["phase"] == "post-install-verify"
    assert report["added_plugins"] == ["b@mk", "a@mk"]


def test_git_metadata_revision_of_wrong_type_stops(tmp_path, codex, capsys):
    snapshot = _git_snapshot_fixture(tmp_path, codex, revision=SHA_A)
    _write_json(snapshot / ICP._INSTALL_METADATA, {"revision": 42})
    code, report = _run(capsys, ["--source", GIT_SOURCE, "--ref", SHA_A, *_PINNED_ARGS],
                        tmp_path / "home")
    assert code == 3
    assert "revision must be a non-empty string" in report["error"]
    assert codex.plugin_adds() == []


# ---------- 途中で止まったときの receipt ----------

def test_second_plugin_add_failure_reports_what_was_added(tmp_path, codex, capsys):
    root = _marketplace(tmp_path / "repo")
    codex.configure({
        "marketplace_add": {"marketplaceName": "mk"},
        "plugin_list": _installed(root, ["a", "b"]),
        "fail_add": ["a@mk"],
    })
    code, report = _run(capsys, ["--source", str(root), "--plugin", "a"], tmp_path / "home")
    assert code == 3
    assert report["phase"] == "plugin-add"
    assert report["added_plugins"] == ["b@mk"]
    assert report["failed_plugin"] == "a@mk"
    assert report["marketplace"] == "mk"


def test_unexpected_plugin_id_shape_is_a_receipt_not_a_traceback(tmp_path, codex, capsys):
    root = _marketplace(tmp_path / "repo")
    codex.configure({
        "marketplace_add": {"marketplaceName": "mk"},
        "plugin_list": _installed(root, ["a", "b"]),
        "plugin_add": {"b@mk": {"pluginId": ["b@mk"]}},
    })
    code, report = _run(capsys, ["--source", str(root), "--plugin", "a"], tmp_path / "home")
    assert code == 3
    assert "unexpected pluginId" in report["error"]
    assert report["added_plugins"] == ["b@mk"]
    assert "failed_plugin" not in report


def test_non_utf8_cli_output_is_a_receipt_not_a_traceback(tmp_path, codex, capsys):
    root = _marketplace(tmp_path / "repo")
    codex.configure({"marketplace_add": {"__raw_hex__": "7b22ff227d"}})
    code, report = _run(capsys, ["--source", str(root), "--plugin", "a"], tmp_path / "home")
    assert code == 3
    assert "not UTF-8" in report["error"]
    assert report["phase"] == "marketplace"
    assert report["added_plugins"] == []


def test_plugin_outside_install_set_appearing_after_add_stops(tmp_path, codex, capsys):
    root = _marketplace(tmp_path / "repo")
    codex.configure({
        "marketplace_add": {"marketplaceName": "mk"},
        "plugin_list": _installed(root, []),
        "plugin_list_after_add": _installed(root, ["a", "b", "c"]),
    })
    code, report = _run(capsys, ["--source", str(root), "--plugin", "a"], tmp_path / "home")
    assert code == 3
    assert report["unexpected_plugins"] == ["c@mk"]
    assert report["added_plugins"] == ["b@mk", "a@mk"]


def test_plugin_already_installed_before_add_is_not_unexpected(tmp_path, codex, capsys):
    root = _marketplace(tmp_path / "repo")
    codex.configure({
        "marketplace_add": {"marketplaceName": "mk"},
        "plugin_list": _installed(root, ["a", "b", "c"]),
    })
    code, report = _run(capsys, ["--source", str(root), "--plugin", "a"], tmp_path / "home")
    assert code == 0, report
    assert "unexpected_plugins" not in report


# ---------- runtime が source と食い違う (stale) ----------

def test_runtime_with_same_version_but_other_content_is_stale(tmp_path, codex, capsys):
    root = _marketplace(tmp_path / "repo")
    runtime = tmp_path / "cache" / "b"
    _write_json(runtime / ".codex-plugin" / "plugin.json", {"name": "b", "version": "1.0.0"})
    (runtime / "old-file.txt").write_text("left from an older build\n", encoding="utf-8")
    listing = _installed(root, ["a", "b"])
    listing["installed"][1]["source"] = {"path": str(runtime)}
    codex.configure({
        "marketplace_add": {"marketplaceName": "mk"},
        "plugin_list": listing,
        "plugin_add": {"b@mk": {"pluginId": "b@mk", "installedPath": str(runtime)}},
    })
    code, report = _run(capsys, ["--source", str(root), "--plugin", "a"], tmp_path / "home")
    assert code == 1, report
    assert report["status"] == "stale_runtime"
    # stale なのは依存の b だけ。要求した a の値で top-level の集計を上書きしない
    assert report["plugin"] == "a"
    assert report["verified"] is False
    assert report["verification_status"] == "stale_runtime"
    stale = next(item for item in report["artifacts"] if item["plugin"] == "b")
    assert stale["verification_status"] == "stale_runtime"
    assert stale["activation"]["runtime"] == "stale"
    assert stale["source_digest"] != stale["runtime_digest"]
    assert "build-plugin-release.py" in report["next_action"]


# ---------- 受け取ったファイルの形が不正 (local は CLI を呼ぶ前に止まる) ----------

def test_package_contract_plugin_name_of_wrong_type_stops(tmp_path, codex, capsys):
    root = _marketplace(tmp_path / "repo")
    _write_json(root / "plugins" / "a" / "references" / "package-contract.json",
                {"plugin_name": ["a"], "depends_on": ["b"]})
    code, report = _run(capsys, ["--source", str(root), "--plugin", "a"], tmp_path / "home")
    assert code == 3
    assert "plugin_name mismatch" in report["error"]
    assert codex.calls() == []


def test_marketplace_source_path_with_nul_stops(tmp_path, codex, capsys):
    root = _marketplace(tmp_path / "repo")
    path = root / ".agents" / "plugins" / "marketplace.json"
    payload = json.loads(path.read_text(encoding="utf-8"))
    payload["plugins"][0]["source"]["path"] = "./plugins/a\u0000x"
    _write_json(path, payload)
    code, report = _run(capsys, ["--source", str(root), "--plugin", "a"], tmp_path / "home")
    assert code == 3
    assert "NUL" in report["error"]
    assert codex.calls() == []


def test_non_utf8_marketplace_file_stops(tmp_path, codex, capsys):
    root = _marketplace(tmp_path / "repo")
    (root / ".agents" / "plugins" / "marketplace.json").write_bytes(b'{"name": "\xff"}')
    code, report = _run(capsys, ["--source", str(root), "--plugin", "a"], tmp_path / "home")
    assert code == 3
    assert "cannot read Codex marketplace" in report["error"]
    assert codex.calls() == []


# ---------- 依存の循環: top-level は要求した plugin を名乗る ----------

@pytest.mark.parametrize("requested", ["a", "b"])
def test_dependency_cycle_top_level_is_the_requested_plugin(tmp_path, codex, capsys, requested):
    root = _marketplace(tmp_path / "repo")
    _write_json(root / "plugins" / "b" / "references" / "package-contract.json",
                {"plugin_name": "b", "depends_on": ["a"]})
    codex.configure({
        "marketplace_add": {"marketplaceName": "mk"},
        "plugin_list": _installed(root, ["a", "b"]),
    })
    code, report = _run(capsys, ["--source", str(root), "--plugin", requested],
                        tmp_path / "home")
    assert code == 0, report
    assert report["cycle_groups"] == [["a", "b"]]
    assert report["install_order"] == ["a", "b"]
    assert report["plugin"] == requested
    assert report["plugin_id"] == f"{requested}@mk"
    assert report["runtime_path"] == str((root / "plugins" / requested).resolve())
    assert report["dependency_closure"] == [n for n in ("a", "b") if n != requested]


# ---------- 引数 ----------

def test_missing_required_arguments_exit_2(capsys):
    with pytest.raises(SystemExit) as exc:
        ICP.main(["--plugin", "a"])
    assert exc.value.code == 2


@pytest.mark.parametrize("extra", [
    ["--ref", SHA_A, "--ref", SHA_B],
    ["--plugin", "c"],
    ["--source", "owner/other"],
    ["--codex-home", "/x", "--codex-home", "/y"],
])
def test_single_value_arguments_given_twice_exit_2(tmp_path, codex, capsys, extra):
    with pytest.raises(SystemExit) as exc:
        ICP.main(["--source", GIT_SOURCE, "--plugin", "a", *extra])
    assert exc.value.code == 2
    assert "only once" in capsys.readouterr().err
    assert codex.calls() == []


@pytest.mark.parametrize("value", ["", "   "])
def test_empty_codex_home_exit_2(tmp_path, codex, capsys, value):
    with pytest.raises(SystemExit) as exc:
        ICP.main(["--source", GIT_SOURCE, "--plugin", "a", "--codex-home", value])
    assert exc.value.code == 2
    assert codex.calls() == []
