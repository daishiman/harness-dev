#!/usr/bin/env python3
"""intake 完全性の機械検証。

3 レイヤを提供する (後方互換を厳守):
  1. 5 軸 placeholder 検出 (check / AXES) ... quality_gate.py が import する既存契約。
  2. section_canonical_map の required_fields 検証 (check_section_completeness)。
  3. §6 intent_contract の slot filled 検証 (check_intent_contract)。
  4. 上記 3 種を集約 (check_all)。

CLI 既定は後方互換 (5 軸)。--mode canonical|intent|all で新検証を発火する。
exit 0=PASS, 1=FAIL, 2=入力エラー。
"""

import json
import re
import sys
from pathlib import Path

# ---------------------------------------------------------------------------
# 参照ファイルの既定パス (script からの相対解決。CWD 非依存)。
# ---------------------------------------------------------------------------
SCRIPT_DIR = Path(__file__).resolve().parent
REFS_DIR = SCRIPT_DIR.parent / 'references'
DEFAULT_CANONICAL_MAP = REFS_DIR / 'section_canonical_map.json'
DEFAULT_PROBE_TABLE = REFS_DIR / 'probe-pattern-table.json'

# ---------------------------------------------------------------------------
# 5 軸の内部 key (既存契約。quality_gate.py の 'placeholders' 出力と一致させる)。
# ---------------------------------------------------------------------------
AXES = ['output_target', 'info_source', 'share_target', 'true_problem', 'knowledge_assets']
AXIS_FALLBACK = {'output_target': 'output_destination'}

# canonical §6 axes enum (正本 = section_canonical_map.json §6 axes[].axis_id) ↔ 既存内部 key
# の双方向 alias 表。canonical enum を正とし、v2 five_axes.rows[] や §6 axes[] からの入力も
# 内部 key に写像できるようにする。日本語 name 写像 (AXIS_JA_TO_KEY) は従来通り維持。
#   canonical §6 axis_id : output_to / input_from / share_target / real_problem / knowledge_asset
#   既存内部 key         : output_target / info_source / share_target / true_problem / knowledge_assets
CANONICAL_TO_INTERNAL = {
    'output_to': 'output_target',
    'input_from': 'info_source',
    'share_target': 'share_target',
    'real_problem': 'true_problem',
    'knowledge_asset': 'knowledge_assets',
}
INTERNAL_TO_CANONICAL = {v: k for k, v in CANONICAL_TO_INTERNAL.items()}

# v2 five_axes.rows[] の日本語 name → 内部 key (validate_intake / convert_v1_to_v2_context と一致)。
AXIS_JA_TO_KEY = {
    '出力先': 'output_target',
    '情報源': 'info_source',
    '共有相手': 'share_target',
    '真の課題': 'true_problem',
    'ナレッジ資産': 'knowledge_assets',
}
PLACEHOLDER_PATTERNS = [
    re.compile(r'\bTBD\b', re.IGNORECASE),
    re.compile(r'未定'),
    re.compile(r'\?{2,}'),
    re.compile(r'^\s*[-—]\s*$'),
    re.compile(r'要確認'),
    re.compile(r'後で決め'),
]

# intent_contract の全 slot (input_spec/output_spec)。intent-contract.schema.json の
# required と一致させる正本。
INTENT_INPUT_SLOTS = ['sources', 'trigger', 'frequency', 'raw_materials']
INTENT_OUTPUT_SLOTS = ['sink', 'format', 'granularity', 'audience', 'cadence']


def axis_value_text(v):
    if v is None:
        return None
    if isinstance(v, str):
        return v
    if isinstance(v, dict) and isinstance(v.get('answer'), str):
        return v['answer']
    if isinstance(v, dict) and isinstance(v.get('content'), str):
        return v['content']
    return None


def normalize_axes(intake):
    """v1 flat (5_axes.output_target) / v2 (five_axes.rows[]) / §6 axes[axis_id] を
    {内部key: text} に正規化。canonical §6 axes[].axis_id (enum) も alias で認識する。"""
    raw = (intake.get('5_axes') if isinstance(intake, dict) else None) or \
        (intake.get('five_axes') if isinstance(intake, dict) else None)
    # v2 canonical: axes は sections.6_five_axes_summary 配下に入る。
    if not raw and isinstance(intake, dict):
        sections = intake.get('sections')
        if isinstance(sections, dict) and isinstance(sections.get('6_five_axes_summary'), dict):
            raw = sections['6_five_axes_summary']
    raw = raw or {}

    # §6 canonical 形式: {"axes": [{"axis_id": "output_to", "answer": ...}, ...]}
    axes_list = raw.get('axes') if isinstance(raw, dict) else None
    if isinstance(axes_list, list):
        flat = {}
        for row in axes_list:
            if not isinstance(row, dict):
                continue
            key = CANONICAL_TO_INTERNAL.get(str(row.get('axis_id', '')).strip())
            if key:
                flat[key] = axis_value_text(row)
        if flat:
            return flat

    # v2 rows 形式: {"rows": [{"name": "出力先", "answer": ...}, ...]}
    rows = raw.get('rows') if isinstance(raw, dict) else None
    if isinstance(rows, list):
        flat = {}
        for row in rows:
            if not isinstance(row, dict):
                continue
            name = str(row.get('name', '')).strip()
            key = AXIS_JA_TO_KEY.get(name)
            # canonical axis_id が name として来ても認識
            if not key:
                key = CANONICAL_TO_INTERNAL.get(name)
            if key:
                flat[key] = axis_value_text(row)
        return flat

    # v1 flat 形式: {"output_target": ...} をそのまま。canonical enum key での直書きも写像。
    if isinstance(raw, dict):
        flat = {}
        for k, v in raw.items():
            key = CANONICAL_TO_INTERNAL.get(k, k)
            flat[key] = v
        return flat
    return {}


def is_placeholder(s):
    if not isinstance(s, str):
        return True
    v = s.strip()
    if len(v) < 4:
        return True
    return any(p.search(v) for p in PLACEHOLDER_PATTERNS)


def check(intake):
    """5 軸 placeholder 検出 (既存契約。戻り値キーは変更禁止)。"""
    axes = normalize_axes(intake)
    filled = {}
    placeholders = []
    count = 0
    for k in AXES:
        fb = AXIS_FALLBACK.get(k)
        if k in axes:
            raw = axes[k]
        elif fb and fb in axes:
            raw = axes[fb]
        else:
            raw = None
        text = axis_value_text(raw)
        ok = not is_placeholder(text)
        filled[k] = ok
        if ok:
            count += 1
        else:
            placeholders.append(k)
    return {
        'ok': count == len(AXES),
        'filled_axes': count,
        'total_axes': len(AXES),
        'detail': filled,
        'placeholders': placeholders,
    }


# ---------------------------------------------------------------------------
# 内部ヘルパ: intake から section / intent_contract を取り出す (v1/v2 両対応)。
# ---------------------------------------------------------------------------

def _get_sections_container(intake):
    """intake から section_key -> section_body の dict を取り出す。
    v2 は {"sections": {...}}、v1 は section_key を top-level に持つ場合がある。"""
    if not isinstance(intake, dict):
        return {}
    sections = intake.get('sections')
    if isinstance(sections, dict):
        return sections
    return intake


def _field_value(section_body, key):
    """section_body から required_field key の値を取り出す (str / dict.answer / dict.content)。"""
    if not isinstance(section_body, dict):
        return None
    if key not in section_body:
        return None
    return section_body[key]


def _is_field_placeholder(s):
    """required_field 用の placeholder 判定。5 軸の自由文と異なり enum (例: 'A') など
    短い正当値がありうるため、len<4 の長さヒューリスティックは適用しない。"""
    if not isinstance(s, str):
        return True
    v = s.strip()
    if not v:
        return True
    return any(p.search(v) for p in PLACEHOLDER_PATTERNS)


def _value_present(v):
    """required_field の値が『存在し placeholder でない』か。
    array/object は非空、str は非 placeholder、数値/bool は存在で present とみなす。"""
    if v is None:
        return False
    if isinstance(v, str):
        return not _is_field_placeholder(v)
    if isinstance(v, (list, dict)):
        return len(v) > 0
    if isinstance(v, bool):
        return True
    if isinstance(v, (int, float)):
        return True
    return True


def _load_json(path):
    return json.loads(Path(path).read_text(encoding='utf-8'))


def check_section_completeness(intake, canonical_map_path=DEFAULT_CANONICAL_MAP):
    """section_canonical_map の各 section の required_fields を走査し、
    absence_behavior=block の field が intake 側に存在し placeholder でないか検証する。
    欠落を {section_key, missing_field, absence_behavior} で列挙して返す。"""
    cmap = _load_json(canonical_map_path)
    sections = _get_sections_container(intake)
    missing = []
    checked = 0
    for section in cmap.get('sections', []):
        skey = section.get('section_key')
        body = sections.get(skey) if isinstance(sections, dict) else None
        for field in section.get('required_fields', []):
            behavior = field.get('absence_behavior', cmap.get('policies', {})
                                 .get('absence_behavior_default', 'block'))
            if behavior != 'block':
                continue
            checked += 1
            fkey = field.get('key')
            val = _field_value(body, fkey)
            if not _value_present(val):
                missing.append({
                    'section_key': skey,
                    'missing_field': fkey,
                    'absence_behavior': behavior,
                })
    return {
        'ok': len(missing) == 0,
        'blocking_fields_checked': checked,
        'missing_count': len(missing),
        'missing': missing,
    }


def _find_intent_contract(intake):
    """intake から §6 intent_contract を取り出す (v2 sections / v1 flat 両対応)。"""
    sections = _get_sections_container(intake)
    if isinstance(sections, dict):
        sixth = sections.get('6_five_axes_summary')
        if isinstance(sixth, dict) and isinstance(sixth.get('intent_contract'), dict):
            return sixth['intent_contract']
    if isinstance(intake, dict):
        for holder in (intake.get('five_axes'), intake.get('5_axes'),
                       intake.get('6_five_axes_summary'), intake):
            if isinstance(holder, dict) and isinstance(holder.get('intent_contract'), dict):
                return holder['intent_contract']
    return None


def check_intent_contract(intake, probe_table_path=DEFAULT_PROBE_TABLE):
    """§6 intent_contract の input_spec/output_spec 全 slot が filled か検証する。
    未充足 slot と、その pending_probe (probe-pattern-table.json 参照) の probe_id を列挙。"""
    contract = _find_intent_contract(intake)
    if contract is None:
        return {
            'ok': False,
            'reason': 'intent_contract not found in §6 (6_five_axes_summary.intent_contract)',
            'unfilled_slots': [
                f'input_spec.{s}' for s in INTENT_INPUT_SLOTS
            ] + [
                f'output_spec.{s}' for s in INTENT_OUTPUT_SLOTS
            ],
            'pending_probes': [],
        }

    # probe-pattern-table から target_slot -> probe_id 逆引き表を作る。
    probe_by_slot = {}
    probe_order = []
    try:
        table = _load_json(probe_table_path)
        probe_order = table.get('probe_order', [])
        for p in table.get('probes', []):
            slot = p.get('target_slot')
            pid = p.get('probe_id')
            if slot and pid and slot not in probe_by_slot:
                probe_by_slot[slot] = pid
    except Exception:
        probe_by_slot = {}

    input_spec = contract.get('input_spec') if isinstance(contract.get('input_spec'), dict) else {}
    output_spec = contract.get('output_spec') if isinstance(contract.get('output_spec'), dict) else {}
    slot_status = contract.get('slot_status') if isinstance(contract.get('slot_status'), dict) else {}

    unfilled = []
    pending = []

    def _slot_filled(spec, field, slot_path):
        # slot_status に filled=false があれば未充足を明示。無ければ値の存在で判定。
        st = slot_status.get(slot_path)
        if isinstance(st, dict) and st.get('filled') is False:
            return False
        if isinstance(st, dict) and st.get('filled') is True:
            # 値も伴っているか二重確認 (契約は値と provenance の両立を要求)。
            return _value_present(spec.get(field))
        return _value_present(spec.get(field))

    for field in INTENT_INPUT_SLOTS:
        slot_path = f'input_spec.{field}'
        if not _slot_filled(input_spec, field, slot_path):
            unfilled.append(slot_path)
            pid = probe_by_slot.get(slot_path)
            if pid:
                pending.append(pid)
    for field in INTENT_OUTPUT_SLOTS:
        slot_path = f'output_spec.{field}'
        if not _slot_filled(output_spec, field, slot_path):
            unfilled.append(slot_path)
            pid = probe_by_slot.get(slot_path)
            if pid:
                pending.append(pid)

    # pending を probe_order の決定論順に整列 (build-intent.py と同一規約)。
    order_index = {pid: i for i, pid in enumerate(probe_order)}
    pending.sort(key=lambda pid: order_index.get(pid, len(order_index)))

    return {
        'ok': len(unfilled) == 0,
        'total_slots': len(INTENT_INPUT_SLOTS) + len(INTENT_OUTPUT_SLOTS),
        'unfilled_count': len(unfilled),
        'unfilled_slots': unfilled,
        'pending_probes': pending,
    }


def check_all(intake, canonical_map_path=DEFAULT_CANONICAL_MAP,
              probe_table_path=DEFAULT_PROBE_TABLE):
    """5 軸 / section / intent_contract を集約する。"""
    five = check(intake)
    sections = check_section_completeness(intake, canonical_map_path)
    intent = check_intent_contract(intake, probe_table_path)
    return {
        'ok': five['ok'] and sections['ok'] and intent['ok'],
        'five_axes': five,
        'sections': sections,
        'intent_contract': intent,
    }


def main(argv):
    mode = 'axes'
    positional = []
    canonical_map_path = DEFAULT_CANONICAL_MAP
    probe_table_path = DEFAULT_PROBE_TABLE
    i = 1
    while i < len(argv):
        a = argv[i]
        if a == '--mode':
            i += 1
            if i >= len(argv):
                sys.stderr.write('error: --mode requires a value\n')
                return 2
            mode = argv[i]
        elif a == '--canonical-map':
            i += 1
            if i >= len(argv):
                sys.stderr.write('error: --canonical-map requires a value\n')
                return 2
            canonical_map_path = argv[i]
        elif a == '--probe-table':
            i += 1
            if i >= len(argv):
                sys.stderr.write('error: --probe-table requires a value\n')
                return 2
            probe_table_path = argv[i]
        elif a.startswith('--'):
            sys.stderr.write(f'error: unknown option: {a}\n')
            return 2
        else:
            positional.append(a)
        i += 1

    if not positional:
        sys.stderr.write(
            'usage: check_completeness.py [--mode axes|canonical|intent|all] <intake.json>\n')
        return 2
    if mode not in ('axes', 'canonical', 'intent', 'all'):
        sys.stderr.write(f'error: invalid --mode: {mode}\n')
        return 2

    try:
        data = _load_json(positional[0])
    except Exception as e:
        sys.stderr.write(f'input error: {e}\n')
        return 2

    try:
        if mode == 'axes':
            r = check(data)
        elif mode == 'canonical':
            r = check_section_completeness(data, canonical_map_path)
        elif mode == 'intent':
            r = check_intent_contract(data, probe_table_path)
        else:  # all
            r = check_all(data, canonical_map_path, probe_table_path)
    except Exception as e:
        sys.stderr.write(f'check error: {e}\n')
        return 2

    sys.stdout.write(json.dumps(r, ensure_ascii=False, indent=2) + '\n')
    return 0 if r['ok'] else 1


if __name__ == '__main__':
    sys.exit(main(sys.argv))
