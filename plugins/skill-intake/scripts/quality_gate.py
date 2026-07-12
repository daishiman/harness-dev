#!/usr/bin/env python3
"""validate / completeness / contradictions + blocks coverage を統合する quality gate。"""

import json
import os
import sys
from pathlib import Path

from validate_intake import validate
from check_completeness import check, check_intent_contract
from detect_contradictions import detect

SCRIPT_DIR = Path(__file__).resolve().parent
# notion-db-schema.json (required プロパティの正本)。aggregator skill 配下。
SCHEMA_PATH = (
    SCRIPT_DIR.parent
    / 'references' / 'notion-db-schema.json'
)


def _load_required_props():
    """notion-db-schema.json から required==true のプロパティ名集合を返す。
    Notion 自動付与 (created_time) は publish が送らないため required から除外。"""
    try:
        with open(SCHEMA_PATH, 'r', encoding='utf-8') as f:
            schema = json.load(f)
    except Exception:
        return None
    props = schema.get('properties', {})
    req = set()
    for name, spec in props.items():
        if not (isinstance(spec, dict) and spec.get('required')):
            continue
        # created_time は Notion 側が自動付与。publish のプロパティ集合には含まれない。
        if spec.get('type') == 'created_time':
            continue
        req.add(name)
    return req


def check_db_match(intake, requested_db_id):
    """出力先一致: intake が解決する database_id と指定 (requested) が一致するか。
    requested が無ければ検査スキップ (ok)。"""
    if not requested_db_id:
        return {'ok': True, 'skipped': True, 'reason': 'no requested database_id'}
    # intake (context) 側が DB を直接持つことは無いため、解決経路 (notion_config) を参照。
    def _canon(v):
        try:
            sys.path.insert(0, str(SCRIPT_DIR))
            import notion_config as _nc
            return _nc.canonical_notion_id(v) or str(v or '').strip().lower()
        except Exception:
            return ''.join(ch for ch in str(v or '').lower() if ch in '0123456789abcdef')

    resolved = None
    try:
        sys.path.insert(0, str(SCRIPT_DIR))
        import notion_config as _nc
        resolved = _nc.get_db_id('hearing-sheet')
    except Exception as e:
        return {'ok': False, 'reason': f'db resolution failed: {e}'}
    if resolved is None:
        # --database-id が publish へも渡る場合は、それ自体が明示 target の正本。
        return {'ok': True, 'source': 'explicit_arg_only',
                'reason': 'no configured database_id; explicit requested database_id is the publish target',
                'requested': requested_db_id}
    ok = (_canon(resolved) == _canon(requested_db_id))
    return {'ok': ok, 'requested': requested_db_id, 'resolved': resolved,
            'reason': '' if ok else 'resolved database_id != requested'}


def check_property_completeness(intake):
    """プロパティ完全性: publish が送るプロパティ集合 ⊇ schema.required。
    送る集合の正本は render_notion_page.project_db_properties (publish と同経路)。"""
    required = _load_required_props()
    if required is None:
        return {'ok': False, 'reason': f'notion-db-schema.json unreadable at {SCHEMA_PATH}'}
    try:
        sys.path.insert(0, str(SCRIPT_DIR))
        from render_notion_page import project_db_properties
        sent = set(project_db_properties(intake).keys())
    except Exception as e:
        return {'ok': False, 'reason': f'project_db_properties failed: {e}'}
    missing = sorted(required - sent)
    return {'ok': len(missing) == 0, 'required': sorted(required),
            'missing': missing,
            'reason': '' if not missing else f'sent properties missing required: {missing}'}


def check_page_id_consistency(result_path, prev_page_id):
    """page_id 一致 (再公開時): notion-publish-result.json.page_id が前回値と一致。
    prev_page_id 未指定 (初回 create) は検査スキップ。"""
    if not prev_page_id:
        return {'ok': True, 'skipped': True, 'reason': 'initial create (no previous page_id)'}
    if not result_path or not os.path.exists(result_path):
        return {'ok': False, 'reason': f'previous page_id given but result file missing: {result_path}'}
    try:
        with open(result_path, 'r', encoding='utf-8') as f:
            data = json.load(f)
    except Exception as e:
        return {'ok': False, 'reason': f'result read error: {e}'}
    cur = data.get('page_id') or data.get('id')
    try:
        sys.path.insert(0, str(SCRIPT_DIR))
        import notion_config as _nc
        cur_norm = _nc.canonical_notion_id(cur)
        prev_norm = _nc.canonical_notion_id(prev_page_id)
    except Exception:
        cur_norm = cur
        prev_norm = prev_page_id
    ok = (cur_norm == prev_norm)
    return {'ok': ok, 'previous': prev_page_id, 'current': cur,
            'reason': '' if ok else 'page_id changed between publishes (would orphan page)'}


def check_blocks(blocks):
    if isinstance(blocks, dict) and 'children' in blocks:
        arr = blocks['children']
    else:
        arr = blocks
    if not isinstance(arr, list):
        arr = []
    total = len(arr)
    mermaid = 0
    h2 = 0
    for b in arr:
        if not isinstance(b, dict):
            continue
        if b.get('type') == 'code' and isinstance(b.get('code'), dict) and b['code'].get('language') == 'mermaid':
            mermaid += 1
        if b.get('type') == 'heading_2':
            h2 += 1
    reasons = []
    if total < 20:
        reasons.append(f'blocks total {total} < 20')
    if mermaid < 1:
        reasons.append(f'mermaid code blocks {mermaid} < 1')
    if h2 < 5:
        reasons.append(f'heading_2 count {h2} < 5')
    return {'ok': len(reasons) == 0, 'total': total, 'mermaid': mermaid, 'h2': h2, 'reasons': reasons}


def _check_intent(intake):
    """§6 intent_contract の全 slot filled を検証。後方互換(段階移行): intent_contract
    未導入の旧 intake は migration_warn 扱いで gate を落とさない。新規 intake は canonical
    §6 で intent_contract=block のため必ず埋まり、未充足 slot があれば FAIL する。"""
    ci = check_intent_contract(intake)
    intent_missing = (not ci.get('ok')) and 'not found' in ci.get('reason', '')
    if intent_missing:
        return {'ok': True, 'migration_warn': True, 'reason': ci.get('reason', '')}
    return {
        'ok': ci.get('ok', False),
        'unfilled_slots': ci.get('unfilled_slots', []),
        'pending_probes': ci.get('pending_probes', []),
    }


def _extract_true_purpose(intake):
    """true_purpose を sections.3_purpose_excavator.true_purpose または
    sections.6_five_axes_summary.axes[axis_id="real_problem"].answer から取り出す (非空時のみ)。"""
    if not isinstance(intake, dict):
        return None
    sections = intake.get('sections')
    if not isinstance(sections, dict):
        return None
    pe = sections.get('3_purpose_excavator')
    if isinstance(pe, dict):
        tp = pe.get('true_purpose')
        if isinstance(tp, str) and tp.strip():
            return tp
    six = sections.get('6_five_axes_summary')
    if isinstance(six, dict) and isinstance(six.get('axes'), list):
        for ax in six['axes']:
            if isinstance(ax, dict) and str(ax.get('axis_id', '')).strip() == 'real_problem':
                a = ax.get('answer')
                if isinstance(a, str) and a.strip():
                    return a
    return None


def _extract_procedure(intake):
    """intake.json sections.6_five_axes_summary.procedure を取り出す (dict なら返す)。"""
    if not isinstance(intake, dict):
        return None
    sections = intake.get('sections')
    if isinstance(sections, dict):
        six = sections.get('6_five_axes_summary')
        if isinstance(six, dict) and isinstance(six.get('procedure'), dict):
            return six['procedure']
    return None


def _procedure_aware(intake):
    """intake が procedure 拡張パイプラインの成果物か (procedure 節 or
    validation.procedure_completeness の存在)。旧 intake は False。"""
    if _extract_procedure(intake) is not None:
        return True
    if isinstance(intake, dict):
        val = intake.get('validation')
        if isinstance(val, dict) and 'procedure_completeness' in val:
            return True
    return False


def check_procedure_gate(intake, require_procedure=False):
    """purpose と procedure の両方が非空で揃い、procedure 完全性検証 (C02) 結果が
    validation.procedure_completeness に格納され汚染なし (contamination.detected=false) で
    あることを検証する (goal-spec C3/C7)。判定ロジック自体は C02 に一元化し重複実装しない。

    後方互換: procedure-aware でない旧 intake は migration_warn で通す。ただし
    require_procedure=True (procedure パイプラインの明示宣言) では fail-closed で強制する。
    """
    aware = _procedure_aware(intake)
    if not aware and not require_procedure:
        return {'ok': True, 'migration_warn': True,
                'reason': 'procedure 節・validation.procedure_completeness とも不在 (procedure 導入前 intake)'}
    violations = []
    if _extract_true_purpose(intake) is None:
        violations.append('missing_purpose')
    if _extract_procedure(intake) is None:
        violations.append('missing_procedure')
    val = intake.get('validation') if isinstance(intake, dict) else None
    pc = val.get('procedure_completeness') if isinstance(val, dict) else None
    if not isinstance(pc, dict):
        violations.append('missing_procedure_validation')  # fail-closed
    else:
        contamination = pc.get('contamination')
        if isinstance(contamination, dict) and contamination.get('detected') is True:
            violations.append('to_be_contamination_detected')
        if pc.get('complete') is False:
            violations.append('missing_procedure')  # C02 が incomplete を記録済み (Phase9 迂回)
    return {'ok': len(violations) == 0, 'violations': sorted(set(violations))}


def gate(intake, requested_db_id=None, result_path=None, prev_page_id=None,
         require_procedure=False):
    v = validate(intake)
    c = check(intake)
    d = detect(intake)
    pc = check_property_completeness(intake)
    dbm = check_db_match(intake, requested_db_id)
    pid = check_page_id_consistency(result_path, prev_page_id)
    ic = _check_intent(intake)
    proc = check_procedure_gate(intake, require_procedure=require_procedure)
    checks = {
        'validate_intake': {'ok': v['ok'], 'errors': v['errors']},
        'check_completeness': {'ok': c['ok'], 'placeholders': c['placeholders'], 'filled_axes': c['filled_axes']},
        'detect_contradictions': {'ok': d['ok'], 'count': d['count']},
        'property_completeness': pc,
        'db_match': dbm,
        'page_id_consistency': pid,
        'intent_contract': ic,
        'procedure_gate': proc,
    }
    ok = (v['ok'] and c['ok'] and d['ok'] and pc['ok'] and dbm['ok']
          and pid['ok'] and ic['ok'] and proc['ok'])
    return {'status': 'PASS' if ok else 'FAIL', 'checks': checks}


def parse_flag_args(argv):
    out = {'positional': []}
    i = 0
    while i < len(argv):
        a = argv[i]
        if a == '--intake':
            i += 1
            out['intake'] = argv[i]
        elif a == '--blocks':
            i += 1
            out['blocks'] = argv[i]
        elif a == '--out':
            i += 1
            out['out_file'] = argv[i]
        elif a == '--database-id':
            i += 1
            out['database_id'] = argv[i]
        elif a == '--result-path':
            i += 1
            out['result_path'] = argv[i]
        elif a == '--prev-page-id':
            i += 1
            out['prev_page_id'] = argv[i]
        elif a == '--require-procedure':
            out['require_procedure'] = True
        elif a.startswith('--'):
            raise ValueError(f'unknown option: {a}')
        else:
            out['positional'].append(a)
        i += 1
    return out


def main(argv):
    try:
        args = parse_flag_args(argv[1:])
    except Exception as e:
        sys.stderr.write(f'argument error: {e}\n')
        return 2
    intake_file = args.get('intake') or (args['positional'][0] if args['positional'] else None)
    out_file = args.get('out_file') or (args['positional'][1] if len(args['positional']) > 1 else None)
    if not intake_file:
        sys.stderr.write('usage: quality_gate.py [--intake] <intake.json> [--blocks <blocks.json>] [--out <out.json>]\n')
        return 2
    try:
        with open(intake_file, 'r', encoding='utf-8') as f:
            data = json.load(f)
    except Exception as e:
        sys.stderr.write(f'input error: {e}\n')
        return 2
    # --database-id 指定時は出力先一致 (check_db_match) を発火させ、指定 DB と
    # 解決 DB の不一致を publish 前に FAIL させる (逸脱A: 別DB出力の防波堤)。
    # --result-path + --prev-page-id 指定時は page_id 一貫性 (check_page_id_consistency) を
    # 発火させ、再公開で別ページに化ける (orphan 化) のを publish 前に FAIL させる。
    r = gate(data, requested_db_id=args.get('database_id'),
             result_path=args.get('result_path'),
             prev_page_id=args.get('prev_page_id'),
             require_procedure=args.get('require_procedure', False))

    # procedure ゲート違反は stderr に列挙する (purpose/procedure 欠落・validation 欠落・to-be 汚染)。
    pgate = r['checks'].get('procedure_gate', {})
    if not pgate.get('ok', True):
        for violation in pgate.get('violations', []):
            sys.stderr.write(f'procedure-gate: {violation}\n')

    blocks_failed = False
    if args.get('blocks'):
        try:
            with open(args['blocks'], 'r', encoding='utf-8') as f:
                blocks = json.load(f)
        except Exception as e:
            sys.stderr.write(f'--blocks read error: {e}\n')
            return 2
        bc = check_blocks(blocks)
        r['checks']['blocks_coverage'] = {
            'ok': bc['ok'], 'total': bc['total'], 'mermaid': bc['mermaid'],
            'heading_2': bc['h2'], 'reasons': bc['reasons'],
        }
        if not bc['ok']:
            for reason in bc['reasons']:
                sys.stderr.write(f'blocks-coverage: {reason}\n')
            r['status'] = 'FAIL'
            blocks_failed = True

    text = json.dumps(r, ensure_ascii=False, indent=2)
    if out_file:
        with open(out_file, 'w', encoding='utf-8') as f:
            f.write(text + '\n')
    else:
        sys.stdout.write(text + '\n')
    if r['status'] == 'PASS':
        return 0
    if blocks_failed:
        return 2
    return 1


if __name__ == '__main__':
    sys.exit(main(sys.argv))
