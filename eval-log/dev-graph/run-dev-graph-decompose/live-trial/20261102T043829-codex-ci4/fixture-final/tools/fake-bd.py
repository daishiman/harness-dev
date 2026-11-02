#!/usr/bin/env python3
import json,sys
from pathlib import Path
root=Path(__file__).resolve().parent.parent
args=sys.argv[1:]
with (root/'fake-bd-calls.jsonl').open('a') as f:f.write(json.dumps({'argv':args})+'\n')
if args==['version']:print('bd version 1.4.2 (readonly fixture)')
elif args==['where','--json']:print(json.dumps({'database_path':'fixture-readonly://codex/.beads/beads.db','prefix':'gm4b','schema_version':'1'}))
else:print('fixture external/write operation denied',file=sys.stderr);raise SystemExit(4)
