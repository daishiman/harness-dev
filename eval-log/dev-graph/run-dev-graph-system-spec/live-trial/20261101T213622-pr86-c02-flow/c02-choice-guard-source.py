"""Read-only fixture guard: reject recording C02 depth from a zero-node preview.

This guard never writes artifacts or supplies a verdict. The source's ordinary
pre-choice real writer remains allowed, as does post-choice delegated work.
"""
from pathlib import Path
import json, sys

def check(root, payload):
    if payload.get('tool_name') != 'Write':
        return None
    data=payload.get('tool_input') or {}
    path=Path(data.get('file_path',''))
    if not path.is_absolute(): path=root/path
    if path.resolve()!=root/'eval-log/run-dev-graph-node-artifact-delivery.json':
        return None
    try: content=json.loads(data.get('content',''))
    except (ValueError,TypeError): return None
    if not isinstance(content,dict): return None
    serialized=json.dumps(content,ensure_ascii=False)
    if 'standard' not in serialized and 'semantic_evaluator_started' not in serialized:
        return None
    try: graph=json.loads((root/'.dev-graph/state/graph.json').read_text())
    except (OSError,ValueError):
        return 'C02の現物graphを読めないため、選択前の実成果物を確認できません。sourceのC24固定rootとcanonical writerを確認してください。'
    if not isinstance(graph,dict) or not isinstance(graph.get('nodes'),list) or not graph['nodes']:
        return 'C02 sourceの選択前の最小成果物は実登録済みtyped node/packageです。dry-run preview/write_count0ではstandardを記録できません。C05完了を確認し、pre-choiceとして正規C02 writerで依頼対象の実nodeを作成・検査・提示してから選択を記録してください。post-choiceの未達writerはsource通りAgentへ委譲し、main直接addで代用しないでください。'
    return None

if __name__=='__main__':
    root=Path(sys.argv[1]).resolve()
    try: payload=json.load(sys.stdin)
    except (ValueError,TypeError): raise SystemExit(2)
    reason=check(root,payload)
    if reason:
        print(reason,file=sys.stderr)
        raise SystemExit(2)
