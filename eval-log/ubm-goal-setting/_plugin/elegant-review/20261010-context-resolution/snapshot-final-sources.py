#!/usr/bin/env python3
"""Capture scoped current bytes against the original filesystem baseline, never Git."""
import hashlib,json
from datetime import datetime,timezone
from pathlib import Path

ROOT=Path(__file__).resolve().parents[5]
RUN=Path(__file__).resolve().parent
OLD=RUN.parent/'20261009-full-resolution'

def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()

def capture():
 baseline_dir=Path(json.loads((OLD/'baseline.json').read_text())['snapshot_dir'])
 baseline=json.loads((baseline_dir/'hashes.json').read_text())
 previous=json.loads((OLD/'source-changes.json').read_text())
 names=set(baseline)|set(previous['current_source_sha256'])|{v['path'] for v in previous['unbaselined_files']}
 for base in (ROOT/'plugins/ubm-goal-setting',):
  for p in base.rglob('*'):
   if p.is_file() and not p.is_symlink() and not ({'__pycache__','.pytest_cache'} & set(p.parts)) and p.suffix!='.pyc':names.add(str(p.relative_to(ROOT)))
 current={name:sha(ROOT/name) for name in sorted(names) if (ROOT/name).is_file()}
 changes=[{'path':name,'before_sha256':digest,'after_sha256':current.get(name),'change':'modified' if name in current else 'deleted'} for name,digest in sorted(baseline.items()) if current.get(name)!=digest]
 additions=[{'path':name,'sha256':digest,'baseline_available':False} for name,digest in current.items() if name not in baseline]
 result={'snapshot_taken_at':datetime.now(timezone.utc).isoformat(),'comparison':'Original task-start filesystem snapshot; no Git read or mutation. Observed changes are not attributed solely to this agent. Knowledge was excluded from original baseline: use staged migration preimages/provenance, not a fabricated initial SHA.','baseline_file_count':len(baseline),'previous_manifest_baseline_count':previous['baseline_file_count'],'baseline_count_note':'Current count is derived directly from original hashes.json; any earlier manifest count is retained as history, not reused as an asserted count.','changed_files':changes,'modified_count':sum(c['change']=='modified' for c in changes),'deleted_count':sum(c['change']=='deleted' for c in changes),'unbaselined_files':additions,'current_source_sha256':current,'current_snapshot_sha256':hashlib.sha256(json.dumps(current,sort_keys=True).encode()).hexdigest(),'knowledge_migration_evidence':[str(p.relative_to(ROOT)) for p in sorted(RUN.glob('knowledge-*-migration.json'))]+[str(RUN.relative_to(ROOT)/'knowledge-tag-refinement.json')]}
 (RUN/'source-changes.json').write_text(json.dumps(result,ensure_ascii=False,indent=2)+'\n')
 print(json.dumps({k:result[k] for k in ('baseline_file_count','modified_count','deleted_count','current_snapshot_sha256')}))

if __name__=='__main__':capture()
