"""Publication/recollection boundaries only; no LLM or real acceptance is run."""
from __future__ import annotations

import hashlib
import importlib.util
import json
import os
import shutil
from pathlib import Path

import pytest


SCRIPT = Path(__file__).resolve().parents[1]/"plugins/harness-creator/skills/run-skill-live-trial/scripts/manage-codex-live-trial.py"


def load():
    spec=importlib.util.spec_from_file_location("codex_collection_test",SCRIPT)
    module=importlib.util.module_from_spec(spec);spec.loader.exec_module(module)
    return module


def test_internal_absolute_and_relative_links_publish_with_target_bytes_and_original_metadata(tmp_path):
    module=load();source=tmp_path/"fx";source.mkdir()
    directory=source/"results";directory.mkdir();(directory/"report.txt").write_text("actual result")
    (source/"current").symlink_to(directory)
    (source/"report").symlink_to("results/report.txt")
    before=module.tree_inventory(source)
    snapshot=tmp_path/"snapshot";receipt=module.snapshot_fixture(source,snapshot)
    assert module.tree_inventory(source)==before
    assert (snapshot/"current/report.txt").read_text()=="actual result"
    assert not Path(os.readlink(snapshot/"current")).is_absolute()
    assert (snapshot/"report").read_text()=="actual result"
    assert receipt["links"][0]["original_target_sha256"]==hashlib.sha256(os.fsencode(str(directory))).hexdigest()
    assert receipt["source_inventory"]==before
    assert receipt["original_fixture_modified"] is False


@pytest.mark.parametrize("target",["escape","missing","secret"])
def test_publication_rejects_true_escape_missing_and_excluded_secret_targets(tmp_path,target):
    module=load();source=tmp_path/"fx";source.mkdir()
    outside=tmp_path/"outside";outside.write_text("private")
    if target=="escape": (source/"link").symlink_to(outside)
    elif target=="missing": (source/"link").symlink_to(source/"missing")
    else:
        key=source/".guard-key";key.write_text("private key")
        (source/"link").symlink_to(key)
    before=module.tree_inventory(source)
    with pytest.raises(ValueError): module.snapshot_fixture(source,tmp_path/"snapshot")
    assert module.tree_inventory(source)==before


def failed_collection(tmp_path):
    module=load();fx=tmp_path/"fx";private=tmp_path/"private";work=tmp_path/"public"
    for path in (fx,private,work):path.mkdir()
    (fx/"eval-log").mkdir();(fx/"results").mkdir();(fx/"results/result.txt").write_text("result")
    (fx/"current").symlink_to(fx/"results")
    (work/"out").mkdir();(work/"out/status.json").write_text('{"status":"PASS"}')
    task=tmp_path/"task.md";task.write_text("original immutable task")
    shutil.copyfile(task,work/"task.md")
    cfg={"run_id":"original-run", "repo_root":str(fx), "private_dir":str(private),"workdir":str(work),
         "task_file":str(task),"target_skill":"demo:run-demo","skill_dir":str(tmp_path/"provider"),
         "scenario_file":str(tmp_path/"scenario.json"),"scenario_id":"original-scenario"}
    config=tmp_path/"config.json";config.write_text(json.dumps(cfg));cfg["_config_file"]=str(config)
    raw='{"type":"session_meta","payload":{"id":"synthetic-collection-only"}}\n'
    original=private/"native-original.jsonl";original.write_text(raw)
    fixed=private/"raw-at-collection";fixed.mkdir();(fixed/"transcript.jsonl").write_text(raw)
    (work/"transcript.jsonl").write_text(raw)
    shutil.copytree(fx,work/"fixture-final",symlinks=True)
    state={"runtime":"codex","run_id":"original-run","status":"DONE","collected":False,
           "session_id":"synthetic-collection-only","native_rollout":str(original),"turns":[],"responses":[],
           "started_at_unix":1000.0,"elapsed":2.3,"behavior_sha256":"0"*64,
           "config_sha256":module.digest(config)}
    module.dump(private/"runner-state.json",state)
    module.dump(private/"collection-failure-observation.json",{
        "state":"failed_collection_preserved_no_retry","actor_collected":False,"evidence_freeze_exists":False,
        "original_fixed_raw_main":str(fixed/"transcript.jsonl"),"original_fixed_raw_sha256":module.digest(fixed/"transcript.jsonl"),
        "partial_public_main_sha256":module.digest(work/"transcript.jsonl")})
    return module,cfg,state


def test_recollection_keeps_original_partial_raw_fixture_and_clock_and_binds_new_publication(tmp_path,monkeypatch):
    module,cfg,state=failed_collection(tmp_path)
    monkeypatch.setattr(module,"verify_pin",lambda *_:None)
    work,private,fx=Path(cfg["workdir"]),Path(cfg["private_dir"]),Path(cfg["repo_root"])
    originals={"partial":module.tree_inventory(work),"raw":module.tree_inventory(private/"raw-at-collection"),
               "fixture":module.tree_inventory(fx)}
    result=module.collect(cfg,recollect=True)
    publication=module.collection_workdir(cfg,result)
    assert publication!=work and publication.name==work.name+"-publication-recovery"
    assert module.tree_inventory(work)==originals["partial"]
    assert module.tree_inventory(private/"raw-at-collection")==originals["raw"]
    assert module.tree_inventory(fx)==originals["fixture"]
    assert result["run_id"]==state["run_id"] and result["elapsed"]==state["elapsed"]
    assert result["started_at_unix"]==state["started_at_unix"]
    assert (publication/"fixture-final/current/result.txt").read_text()=="result"
    poll=json.loads((publication/"poll-state.json").read_text())
    assert poll=={"elapsed":3,"started_at_unix":1000.0,"observed_at_unix":1002.3}
    calls=[]
    class Finalizer:
        @staticmethod
        def main(args):calls.append(args);return 7
    monkeypatch.setattr(module,"sibling",lambda name:Finalizer)
    assert module.finalize(cfg,None,[],True)==7
    assert calls[0][calls[0].index("--workdir")+1]==str(publication)
    assert calls[0][calls[0].index("--transcript")+1]==str(publication/"transcript.jsonl")
    with pytest.raises(ValueError):module.collect(cfg,recollect=True)


@pytest.mark.parametrize("change",["raw","partial","fixture"])
def test_recollection_rejects_changed_originals_before_creating_publication(tmp_path,monkeypatch,change):
    module,cfg,_state=failed_collection(tmp_path)
    monkeypatch.setattr(module,"verify_pin",lambda *_:None)
    if change=="raw":target=Path(cfg["private_dir"])/"raw-at-collection/transcript.jsonl"
    elif change=="partial":target=Path(cfg["workdir"])/"fixture-final/results/result.txt"
    else:target=Path(cfg["repo_root"])/"results/result.txt"
    target.write_text("changed")
    state_before=module.state_path(cfg).read_bytes()
    with pytest.raises(ValueError):module.collect(cfg,recollect=True)
    assert module.state_path(cfg).read_bytes()==state_before
    assert not Path(cfg["workdir"]).with_name("public-publication-recovery").exists()


def test_finalizer_rejects_changed_publication_link_after_freeze(tmp_path,monkeypatch):
    module,cfg,_state=failed_collection(tmp_path)
    monkeypatch.setattr(module,"verify_pin",lambda *_:None)
    state=module.collect(cfg,recollect=True);work=module.collection_workdir(cfg,state)
    link=work/"fixture-final/current";link.unlink();link.symlink_to(".")
    with pytest.raises(ValueError,match="link drift"):module.finalize(cfg,None,[],True)


def add_fixed_child(module,cfg,state):
    identity="12345678-1234-5678-9abc-123456789abc"
    raw=Path(cfg["private_dir"])/"raw-at-collection"
    rows=[{"type":"session_meta","payload":{"id":state["session_id"]}},
          {"type":"response_item","payload":{"type":"function_call","call_id":"spawn","name":"spawn_agent","arguments":"{}"}},
          {"type":"response_item","payload":{"type":"function_call_output","call_id":"spawn","output":json.dumps({"agent_id":identity})}}]
    text="".join(json.dumps(row)+"\n" for row in rows)
    for path in (raw/"transcript.jsonl",Path(state["native_rollout"]),Path(cfg["workdir"])/"transcript.jsonl"):path.write_text(text)
    child=raw/"transcript/subagents"/(identity+".jsonl");child.parent.mkdir(parents=True)
    child.write_text(json.dumps({"type":"session_meta","payload":{"id":identity,"parent_thread_id":state["session_id"]}})+"\n")
    public=Path(cfg["workdir"])/"transcript/subagents"/child.name;public.parent.mkdir(parents=True);shutil.copyfile(child,public)
    observation=Path(cfg["private_dir"])/"collection-failure-observation.json"
    value=json.loads(observation.read_text());value["original_fixed_raw_sha256"]=module.digest(raw/"transcript.jsonl");value["partial_public_main_sha256"]=module.digest(Path(cfg["workdir"])/"transcript.jsonl")
    module.dump(observation,value)
    return child


def first_failed_publication(module,cfg):
    work,raw=module.publication_paths(cfg,1)
    work.mkdir();raw.mkdir()
    shutil.copyfile(module.state_path(cfg),raw/"runner-state-before.json")
    shutil.copyfile(Path(cfg["private_dir"])/"raw-at-collection/transcript.jsonl",raw/"transcript.jsonl")
    shutil.copyfile(Path(cfg["workdir"])/"transcript.jsonl",work/"transcript.jsonl")
    shutil.copyfile(Path(cfg["workdir"])/"task.md",work/"task.md")
    log=Path(cfg["private_dir"])/"recollect.stderr.log"
    log.write_text("[ERROR] native rollout filename and metadata identity differ\n")
    return work,raw,log


def test_fixed_uuid_child_alias_is_checked_before_publication_and_collected_without_live_name_relaxation(tmp_path,monkeypatch):
    module,cfg,state=failed_collection(tmp_path);child=add_fixed_child(module,cfg,state)
    monkeypatch.setattr(module,"verify_pin",lambda *_:None)
    # The existing live discovery rule remains strict; only fixed aliases differ.
    with pytest.raises(ValueError,match="filename"):module._first_metadata(child,fresh=True)
    result=module.collect(cfg,recollect=True)
    work=module.collection_workdir(cfg,result)
    assert (work/"transcript/subagents"/child.name).read_bytes()==child.read_bytes()
    receipt=json.loads((work/"collection-recovery-receipt.json").read_text())
    assert receipt["fixed_native_validation"]["format_errors"]==[]
    assert receipt["collected_at_unix"]>receipt["execution_observed_at_unix"]==1002.3


def test_bad_fixed_child_alias_is_rejected_before_new_attempt_directory(tmp_path,monkeypatch):
    module,cfg,state=failed_collection(tmp_path);child=add_fixed_child(module,cfg,state)
    child.rename(child.with_name("aaaaaaaa-aaaa-aaaa-aaaa-aaaaaaaaaaaa.jsonl"))
    monkeypatch.setattr(module,"verify_pin",lambda *_:None)
    with pytest.raises(ValueError,match="fixed child snapshot filename"):
        module.collect(cfg,recollect=True)
    work,raw=module.publication_paths(cfg,1)
    assert not work.exists() and not raw.exists()


def test_second_explicit_publication_ordinal_keeps_all_failed_originals_and_uses_new_binding(tmp_path,monkeypatch):
    module,cfg,_state=failed_collection(tmp_path)
    first,first_raw,log=first_failed_publication(module,cfg)
    before=module.tree_inventory(first),module.tree_inventory(first_raw)
    monkeypatch.setattr(module,"verify_pin",lambda *_:None)
    state=module.collect(cfg,recollect=True,publication_ordinal=2,previous_failure_logs=[log])
    work=module.collection_workdir(cfg,state)
    assert work.name.endswith("-publication-recovery-2")
    assert (module.tree_inventory(first),module.tree_inventory(first_raw))==before
    receipt=json.loads((work/"collection-recovery-receipt.json").read_text())
    assert receipt["publication_ordinal"]==2
    assert receipt["previous_failed_attempts"][0]["failure_log_sha256"]==module.digest(log)
    assert state["elapsed"]==2.3 and state["started_at_unix"]==1000.0
    assert (Path(cfg["private_dir"])/"raw-at-recollection-2/previous-failure-001.log").read_bytes()==log.read_bytes()


@pytest.mark.parametrize("failure",["skip","no_log","frozen","raw_drift"])
def test_new_publication_requires_verified_unfrozen_prior_ordinals_and_logs(tmp_path,monkeypatch,failure):
    module,cfg,_state=failed_collection(tmp_path)
    first,first_raw,log=first_failed_publication(module,cfg)
    if failure=="frozen":(first/"evidence-freeze.json").write_text("{}")
    if failure=="raw_drift":(first_raw/"transcript.jsonl").write_text("changed")
    ordinal=3 if failure=="skip" else 2
    logs=[] if failure=="no_log" else [log]
    monkeypatch.setattr(module,"verify_pin",lambda *_:None)
    before=module.state_path(cfg).read_bytes()
    with pytest.raises(ValueError):module.collect(cfg,recollect=True,publication_ordinal=ordinal,previous_failure_logs=logs)
    work,raw=module.publication_paths(cfg,ordinal)
    assert not work.exists() and not raw.exists()
    assert module.state_path(cfg).read_bytes()==before
