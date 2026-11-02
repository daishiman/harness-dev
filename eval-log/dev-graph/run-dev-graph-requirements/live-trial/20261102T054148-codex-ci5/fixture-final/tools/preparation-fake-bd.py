#!/usr/bin/env python3
import json,sys
from pathlib import Path
root=Path(__file__).resolve().parent
with (root/'preparation-tracker-calls.jsonl').open('a') as f: f.write(json.dumps(sys.argv)+'\n')
print('unexpected tracker call while preparing tracker=none fixture',file=sys.stderr)
raise SystemExit(2)
