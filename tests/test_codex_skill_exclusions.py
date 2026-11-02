"""Per-invocation catalog filtering: argv/config validation only, no LLM."""
from __future__ import annotations
import hashlib
import importlib.util
import json
from pathlib import Path
import tomllib

import pytest

SCRIPT=Path(__file__).resolve().parents[1]/"plugins/harness-creator/skills/run-skill-live-trial/scripts/manage-codex-live-trial.py"


def case(tmp_path):
    spec=importlib.util.spec_from_file_location("codex_exclusions_test",SCRIPT)
    module=importlib.util.module_from_spec(spec);spec.loader.exec_module(module)
    fx=tmp_path/"fx";fx.mkdir();work=tmp_path/"work";work.mkdir();provider=tmp_path/"provider";provider.mkdir()
    source=tmp_path/"外部 catalog"/"SKILL.md";source.parent.mkdir();source.write_text("unrelated skill")
    cfg={"repo_root":str(fx),"workdir":str(work),"skill_dir":str(provider),"loaded_provider_roots":[str(provider)],
         "codex_executable":"/usr/bin/true","native_skill_exclusions":[{"path":str(source),"sha256":hashlib.sha256(source.read_bytes()).hexdigest()}]}
    return module,cfg,source


@pytest.mark.parametrize("session",[None,"exact-native-session"])
def test_only_pinned_unrelated_catalog_paths_are_disabled_in_exec_and_resume(tmp_path,session):
    module,cfg,source=case(tmp_path)
    argv=module.codex_argv(cfg,session)
    override=next(value for value in argv if value.startswith("skills.config="))
    assert tomllib.loads(override)=={"skills":{"config":[{"path":str(source),"enabled":False}]}}
    assert argv[-1]=="-" and "--ignore-user-config" in argv
    assert argv[argv.index("--sandbox")+1]=="workspace-write"
    if session:assert argv[-3:]==["resume",session,"-"]
    del cfg["native_skill_exclusions"]
    assert module.native_skill_exclusion_argv(cfg)==[]


@pytest.mark.parametrize("failure",["relative","not_skill","missing","digest","duplicate","provider","workspace","mutable_alias","projection"])
def test_filter_rejects_drift_or_disabling_allowed_sources(tmp_path,failure):
    module,cfg,source=case(tmp_path);item=cfg["native_skill_exclusions"][0]
    if failure=="relative":item["path"]="relative/SKILL.md"
    elif failure=="not_skill":item["path"]=str(source.with_name("OTHER.md"));Path(item["path"]).write_text("unrelated skill")
    elif failure=="missing":source.unlink()
    elif failure=="digest":source.write_text("changed content")
    elif failure=="duplicate":cfg["native_skill_exclusions"].append(dict(item))
    elif failure in {"provider","workspace"}:
        path=Path(cfg["skill_dir"] if failure=="provider" else cfg["repo_root"])/"SKILL.md"
        path.write_bytes(source.read_bytes());item["path"]=str(path)
    elif failure=="mutable_alias":
        path=Path(cfg["repo_root"])/"SKILL.md";path.symlink_to(source);item["path"]=str(path)
    elif failure=="projection":
        receipt=tmp_path/"projection.json";receipt.write_text(json.dumps({"skills":[{"project_path":str(Path(cfg["repo_root"])/".agents/skills/example/SKILL.md"),"source_path":str(source)}]}));cfg["projection_receipt_file"]=str(receipt)
    with pytest.raises(ValueError):module.codex_argv(cfg)


def test_exclusion_path_anonymization_keeps_private_bytes_and_json_valid(tmp_path):
    module,cfg,source=case(tmp_path)
    raw=json.dumps({"argv":module.codex_argv(cfg)},ensure_ascii=True).encode()
    original=raw[:];alias="catalog-exclusion-001/SKILL.md"
    public=module.public_bytes(raw,[],{str(source):alias})
    assert raw==original and str(source) not in public.decode()
    assert "\\u5916" not in public.decode() and alias in public.decode()
    assert json.loads(public)["argv"][-1]=="-"
