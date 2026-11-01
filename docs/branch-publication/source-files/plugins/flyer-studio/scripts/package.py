#!/usr/bin/env python3
"""個人用プラグインの自己完結検査と、両製品用ローカル導入キット生成。

部品の登録簿は plugin-composition.yaml（中身は JSON）、配布条件は references/package-contract.json が正本。
この検査は stage 名・指針 ID・必要ファイルを持たず、正本から読んで両方向に照合する。
"""
import argparse
import hashlib
import json
import re
from pathlib import Path
import shutil
import subprocess
import sys
import unicodedata

ROOT = Path(__file__).resolve().parent.parent
EXCLUDE = {'node_modules', '.cache', '__pycache__', '.git', '.claude', 'development-plan', 'verification', 'artifact-delivery.json'}
# 配布キットへ写さない名前。package() の複写と、shipped() を通る全ての照合が同じ規則を使う。
# 写るものは名前によらず登録簿と照合する。ただしフォルダ単位で登録した場所は隠し名（'.' で始まる名前）を除く
# 中身を登録で信頼し、skills/<name>/ の中身は stage 検査が resources と照合する。.gitignore の除外対象はどれも既にここで外れる。
IGNORE = shutil.ignore_patterns(*EXCLUDE, '*.tmp', '.DS_Store', '.gitignore')
COMPOSITION = 'plugin-composition.yaml'
CONTRACT = 'references/package-contract.json'
REF_KEYS = ['subagent_refs', 'responsibility_refs', 'schema_refs', 'reference_refs']
LINK = re.compile(r'\]\(([^)\s]+)\)')
# HTML の参照属性（href・src）。配布する .html と、markdown の本文に書いた HTML の両方で見る。
ATTR = re.compile(r'''\b(?:href|src)\s*=\s*(["'])([^"']+)\1''', re.I)
CATALOG = 'assets/catalog.json'
GLOB = re.compile(r'[*?[]')

def ignored(root, path):
    """IGNORE で配布キットへ写らないか。copytree と同じく、途中のフォルダが外れればその中身も写らない。"""
    parts = path.relative_to(root).parts
    return any(part in IGNORE(str(root.joinpath(*parts[:i])), [part]) for i, part in enumerate(parts))

def shipped(root, folder=None):
    """配布キットへ写るパスを順に返す。写らないフォルダ（.claude・node_modules など）へは降りない。

    symlink のフォルダへも降りない。その中身は列挙されないまま copytree に写るので、check_symlinks が止める。
    """
    for path in sorted((folder or root).iterdir()):
        if not ignored(root, path):
            yield path
            if path.is_dir() and not path.is_symlink():
                yield from shipped(root, path)

def digest(p):
    return hashlib.sha256(p.read_bytes()).hexdigest()

def rel(root, path):
    """メッセージに出す root 相対のパス。root の外ならパスをそのまま出す。"""
    path, root = Path(path).resolve(), Path(root).resolve()
    return str(path.relative_to(root)) if path.is_relative_to(root) else str(path)

def load(p, root=ROOT):
    """JSON を読む。読めなければ、どのファイルかを root 相対のパスで示す ValueError にする。"""
    try:
        return json.loads(p.read_text(encoding='utf-8'))
    except ValueError as exc:
        raise ValueError('JSONとして読めない: ' + rel(root, p) + ' (' + str(exc) + ')') from None

def composition(root):
    file = root / COMPOSITION
    return load(file) if file.is_file() else None

def all_capabilities(comp):
    """ホスト公開面とskill内担当を合わせた、配布物の完全な登録簿。"""
    return comp.get('capabilities', []) + comp.get('internal_capabilities', [])

def all_dependencies(comp):
    """公開DAG・内部委任・正本で検査するFIX差し戻しの全辺。"""
    return comp.get('dependencies', []) + comp.get('internal_dependencies', []) + comp.get('revisionRoutes', [])

def read_catalog(root):
    """素材台帳の entries と、読めないときの理由を返す。理由は不在・JSON として読めない・形式違反で文言を分ける。"""
    file = root / CATALOG
    if not file.is_file():
        return None, '素材台帳なし: ' + CATALOG
    try:
        catalog = load(file, root)
    except ValueError as exc:
        return None, str(exc)
    entries = catalog.get('entries') if isinstance(catalog, dict) else None
    if not isinstance(entries, list):
        return None, '素材台帳の形式: ' + CATALOG + ' は entries 配列を持つ object にする'
    return entries, None

def catalog_entries(root):
    """素材台帳の entries。読めなければ None（理由は read_catalog が返す）。"""
    return read_catalog(root)[0]

def capability_file(root, cap):
    base = root / cap['ref']
    return base / 'SKILL.md' if cap.get('kind') == 'skill' else base.with_suffix('.md')

def frontmatter(file):
    """frontmatter のスカラーと '- ' の列だけを読む（YAML に依存しない）。"""
    match = re.match(r'^---\s*\n(.*?)\n---(?:\n|$)', file.read_text(encoding='utf-8'), re.S)
    if not match:
        return None
    fields, key = {}, None
    for line in match.group(1).splitlines():
        top = re.match(r'^([A-Za-z_][\w-]*):\s*(.*)$', line)
        if top:
            key, value = top.group(1), top.group(2).strip().strip('"\'')
            fields[key] = value if value else []
        elif key and isinstance(fields.get(key), list):
            item = re.match(r'^\s+-\s*([^#\n]+)', line)
            if item:
                fields[key].append(item.group(1).strip().strip('"\''))
    return fields

def as_list(value):
    return [value] if isinstance(value, str) else list(value or [])

def slug(text):
    """見出しのアンカー（記号を落とし、空白を '-' にする。GitHub と同じ規則）。"""
    kept = ''.join(c for c in text.strip().lower() if c in ' -_' or unicodedata.category(c)[0] in 'LNM')
    return kept.replace(' ', '-')

def resolve_ref(root, base, ref):
    """'path#見出し' の path が root 内に実在し、見出しがあれば markdown 見出しとしても実在するか。"""
    path, _, heading = ref.partition('#')
    target = (base / path).resolve()
    if not target.is_relative_to(root.resolve()) or not target.exists():
        return False
    if not heading:
        return True
    if not target.is_file():
        return False
    headings = re.findall(r'^#{1,6}\s+(.+?)\s*$', target.read_text(encoding='utf-8'), re.M)
    return slug(heading) in {slug(h) for h in headings}

def acyclic(nodes, edges):
    """edges[node] の先を全部片付けられた node から順に外し、全部外せれば循環なし。"""
    done = set()
    for _ in nodes:
        done.update(n for n in nodes if edges.get(n, set()) <= done)
    return done == set(nodes)

def check_manifest(root, name, base, workflow, refs):
    errors = []
    label = 'manifest(' + name + ')'
    if workflow.get('skill') != name or workflow.get('workflowId') != name:
        errors.append(label + ': skill/workflowId不一致')
    if 'maxImprovementCycles' in workflow:
        errors.append(label + ': cycle上限は design-contract の cycleBudget だけに置く')
    if workflow.get('revisionBudgetRef') and not resolve_ref(root, base, workflow['revisionBudgetRef']):
        errors.append(label + ': revisionBudgetRef参照切れ')
    phases = workflow.get('phases', [])
    resources = workflow.get('resources', [])
    phase_ids = {p['id'] for p in phases}
    resource_ids = {r.get('id') for r in resources}
    paths = set()
    for resource in resources:
        target = (base / resource.get('path', '')).resolve()
        if not target.is_relative_to(root.resolve()) or not target.is_file():
            errors.append('manifest参照切れ: ' + name + '/' + str(resource.get('id')))
        paths.add(target)
        if not set(resource.get('phaseIds', [])) <= phase_ids:
            errors.append(label + ': 未知のphase -> ' + str(resource.get('id')))
    for phase in phases:
        if not set(phase.get('resourceIds', [])) <= resource_ids:
            errors.append(label + ': 未知のresource -> ' + phase['id'])
    for target in sorted(refs - paths):
        errors.append(label + ': frontmatterの参照がresourcesに無い -> ' + str(target.relative_to(root.resolve())))
    for file in shipped(root, base):
        if file.is_file() and file.name not in ('SKILL.md', 'workflow-manifest.json') and file.resolve() not in paths:
            errors.append(label + ': resourcesに無いskill資産 -> ' + str(file.relative_to(root)))
    if not acyclic(phase_ids, {p['id']: set(p.get('dependsOn', [])) for p in phases}):
        errors.append('stage依存循環/参照切れ: ' + name)
    return errors

def check_policy_coverage(root, comp, entries):
    """stage が読む DD 本文・関連節・判断契約が鮮度指紋の対象に含まれるか。"""
    contract_file = root / 'references/design-contract.json'
    if not contract_file.is_file():
        return []
    contract, errors = load(contract_file), []
    scopes = {'analysisPolicyFiles': {'analyze', 'analysis-review'}, 'reviewPolicyFiles': {'review'}}
    caps = [c for c in all_capabilities(comp) if c.get('kind') == 'skill']
    for key, stages in scopes.items():
        applicable = [c for c in caps if c.get('stage') in stages]
        if not applicable:
            continue
        files = contract.get(key)
        if not isinstance(files, list) or not files:
            errors.append('規範集合がありません: ' + key)
            continue
        expected = set()
        for entry in entries:
            if {use.split(':')[0] for use in entry.get('usedBy', [])} & stages:
                expected.add(entry.get('path', ''))
                expected.update(ref.partition('#')[0] for ref in entry.get('relatedSections', []))
        # stage の判断契約と入力schemaは既存frontmatterを参照し、新たな台帳へ複写しない。
        for cap in applicable:
            skill = capability_file(root, cap)
            fm = frontmatter(skill) if skill.is_file() else {}
            for refkey in ['reference_refs', 'schema_refs']:
                for ref in as_list((fm or {}).get(refkey)):
                    target = (skill.parent / ref.partition('#')[0]).resolve()
                    if target.is_relative_to(root.resolve()):
                        expected.add(str(target.relative_to(root.resolve())))
        workflow = comp.get('implementation', {}).get('workflow')
        if workflow:
            expected.add(workflow.partition('#')[0])
        for missing in sorted(expected - set(files)):
            errors.append('規範集合の被覆漏れ: ' + key + ' -> ' + missing)
    # 専門本文の役ごとの節は、当該 usedBy の DD 本文または関連節から到達させる。
    # 役か参照を宣言したのに本文が root 内に無ければ、接続の照合を飛ばさずに止める。
    expert = contract.get('expertSourcesRef')
    source = (root / expert).resolve() if isinstance(expert, str) and expert else None
    if (expert or contract.get('expertRoles')) and not (source and source.is_relative_to(root.resolve()) and source.is_file()):
        errors.append('専門知見の本文の参照切れ: expertSourcesRef -> ' + str(expert))
    elif expert:
        headings = re.findall(r'^#{1,6}\s+(.+?)\s*$', source.read_text(encoding='utf-8'), re.M)
        for role in contract.get('expertRoles', []):
            required = {expert + '#' + slug(h) for h in headings if h.startswith(role + ' ')}
            indexed = set()
            for entry in entries:
                if 'review:' + role not in entry.get('usedBy', []):
                    continue
                indexed.add(entry.get('path', '') + ('#' + slug(entry['section']) if entry.get('section') else ''))
                indexed.update(entry.get('relatedSections', []))
            if not required or not required <= indexed:
                errors.append('専門知見の索引接続漏れ: review:' + role)
    return errors

def check_stage_contracts(root=ROOT):
    """登録簿の skill ごとに frontmatter・参照・manifest・指針 ID の整合を検査する。"""
    comp = composition(root)
    if comp is None:
        return ['登録簿なし: ' + COMPOSITION]
    errors = []
    skills = {Path(c['ref']).name: c.get('stage') for c in all_capabilities(comp) if c.get('kind') == 'skill'}
    stages = set(skills.values())
    if None in stages or len(stages) != len(skills):
        errors.append('stage名の欠落/重複')
    index_ref = comp.get('implementation', {}).get('knowledgeIndex', '')
    if not index_ref or not (root / index_ref).is_file():
        return errors + ['指針ID正本なし: ' + index_ref]
    entries = load(root / index_ref).get('entries', [])
    ids = [entry.get('id') for entry in entries]
    if not ids or len(ids) != len(set(ids)) or not all(re.fullmatch(r'DD\d{2}', str(i)) for i in ids):
        errors.append('指針IDの欠落/重複/形式違反')
    contract_file = root / 'references/design-contract.json'
    contract = load(contract_file) if contract_file.is_file() else {}
    budget = contract.get('cycleBudget')
    # 契約が名指す索引も、ここで照合する登録簿の索引と同じファイルにする。食い違えば、検査した索引と契約の索引が別物になる。
    named = contract.get('knowledgeIndex', index_ref)
    if not isinstance(named, str) or (root / named).resolve() != (root / index_ref).resolve():
        errors.append('design-contract の knowledgeIndex が登録簿と不一致: ' + str(named))
    if comp.get('revisionBudget', {}).get('maxCycles', budget) != budget:
        errors.append('revisionBudget.maxCycles が cycleBudget と不一致')
    used_by, targets = {}, set()
    for entry in entries:
        ref = entry.get('path', '') + ('#' + entry['section'] if entry.get('section') else '')
        if not resolve_ref(root, root, ref):
            errors.append('指針参照切れ: ' + str(entry.get('id')))
        if ref in targets:
            errors.append('指針の参照先が重複: ' + str(entry.get('id')))
        targets.add(ref)
        for related in entry.get('relatedSections', []):
            if not resolve_ref(root, root, related):
                errors.append('指針の関連節参照切れ: ' + str(entry.get('id')) + ' -> ' + related)
        used_by[entry.get('id')] = {use.split(':')[0] for use in entry.get('usedBy', [])}
        for use in sorted(used_by[entry.get('id')] - stages):
            errors.append('usedByの未知のstage: ' + str(entry.get('id')) + ' -> ' + use)

    def check_doc(file, expected, stage):
        rel = str(file.relative_to(root))
        fm = frontmatter(file)
        if fm is None:
            errors.append('frontmatterなし: ' + rel)
            return set()
        if fm.get('name') != expected:
            errors.append('frontmatter name不一致: ' + rel)
        targets = set()
        for key in REF_KEYS:
            for value in as_list(fm.get(key)):
                if resolve_ref(root, file.parent, value):
                    targets.add((file.parent / value.partition('#')[0]).resolve())
                else:
                    errors.append('stage参照切れ: ' + rel + ' -> ' + value)
        for value in as_list(fm.get('knowledge_refs')):
            if value not in used_by:
                errors.append('未知の指針ID: ' + value)
            elif stage not in used_by[value]:
                errors.append('usedByに無い指針: ' + rel + ' -> ' + value)
        return targets

    for name, stage in skills.items():
        base = root / 'skills' / name
        if not (base / 'SKILL.md').is_file():
            errors.append('stage skillなし: ' + name)
            continue
        refs = check_doc(base / 'SKILL.md', name, stage)
        # SKILL の goal_seek.max_loops は工程全体の cycle 予算を指すと宣言しているので、値の食い違いを止める。
        loops = re.search(r'^goal_seek:[ \t]*\n(?:[ \t]+.*\n)*?[ \t]+max_loops:\s*(\d+)', (base / 'SKILL.md').read_text(encoding='utf-8'), re.M)
        if loops and int(loops.group(1)) != budget:
            errors.append('goal_seek.max_loops が cycleBudget と不一致: ' + name)
        for agent in sorted(base.glob('agents/*.md')):
            refs |= check_doc(agent, agent.stem, stage)
        manifest = base / 'workflow-manifest.json'
        if not manifest.is_file():
            errors.append('stage manifestなし: ' + name)
            continue
        errors.extend(check_manifest(root, name, base, load(manifest), refs))
    errors.extend(check_policy_coverage(root, comp, entries))
    return errors

def check_fix_routing(root, comp):
    """FIX の戻り関係を契約・工程表・登録簿で照合し、通常の依存と区別する。"""
    errors = []
    file = root / 'references/design-contract.json'
    routes = load(file).get('fixRouting', {}) if file.is_file() else {}
    routes = {k: v for k, v in routes.items() if k != 'notes'}
    revisions = [d for d in all_dependencies(comp) if d.get('type') == 'revision']
    if not routes:
        return ['fixRouting の無い revision 関係'] if revisions else []
    skills = {Path(c['ref']).name: c['ref'] for c in all_capabilities(comp) if c.get('kind') == 'skill'}
    stages = {c.get('stage'): c['ref'] for c in all_capabilities(comp) if c.get('kind') == 'skill'}
    producer = stages.get('create')
    expected = {(producer, skills.get(target), fix) for fix, target in routes.items() if skills.get(target) != producer}
    actual = [(d.get('from'), d.get('to'), d.get('fixClass')) for d in revisions]
    if producer is None or any(target not in skills for target in routes.values()) or set(actual) != expected or len(actual) != len(set(actual)):
        errors.append('revision 関係が fixRouting と不一致')
    workflow = root / 'references/workflow.md'
    cells = [line.strip().strip('|').split('|') for line in workflow.read_text(encoding='utf-8').splitlines() if line.strip().startswith('|')] if workflow.is_file() else []
    for fix, target in routes.items():
        rows = [row for row in cells if len(row) >= 3 and row[0].strip() == fix]
        names = re.findall(r'\brun-[a-z-]+\b', rows[0][2]) if len(rows) == 1 else []
        if not names or names[0] != target:
            errors.append('workflow 改善表が fixRouting と不一致: ' + fix)
    # 新規案件の前提FIXを、存在しない元画像の分析へ送らない。
    expected_modes = {(stages.get('intake'), stages.get('analyze')): 'source-artifact',
                      (stages.get('intake'), producer): 'new-from-brief',
                      (producer, stages.get('analyze')): 'source-artifact'}
    for pair, mode in expected_modes.items():
        forward = [d for d in all_dependencies(comp) if (d.get('from'), d.get('to')) == pair and d.get('type') == 'calls']
        if None in pair or len(forward) != 1 or forward[0].get('analysisMode') != mode or forward[0].get('fixClass') is not None or re.search(r'fixClass\s*=\s*premise', forward[0].get('condition', '')):
            errors.append('通常呼出の analysisMode/前提分岐が不一致: ' + str(pair))
    return errors

def check_non_fix_returns(root, comp):
    """cycle を消費しない差し戻し（nonFixReturns）を、FIX の revision 辺と混ぜずに置いているか。"""
    returns = comp.get('nonFixReturns', [])
    if not isinstance(returns, list) or not all(isinstance(r, dict) for r in returns):
        return ['非FIXの差し戻しの形式: nonFixReturns は object の配列にする']
    skills = {c['ref'] for c in all_capabilities(comp) if c.get('kind') == 'skill'}
    errors = []
    for item in returns:
        trigger = str(item.get('trigger'))
        if 'fixClass' in item:
            errors.append('非FIXの差し戻しが fixClass を持つ: ' + trigger)
        if item.get('consumesCycle') is not False:
            errors.append('非FIXの差し戻しが cycle を消費する: ' + trigger)
        for key in ('from', 'to'):
            if item.get(key) not in skills:
                errors.append('非FIXの差し戻しの部品が未登録: ' + str(item.get(key)))
        # 空の参照は resolve_ref では root そのものへ解決してしまうので、先に止める。
        for key in ('step', 'source'):
            ref = item.get(key)
            if not (isinstance(ref, str) and ref and resolve_ref(root, root, ref)):
                errors.append('非FIXの差し戻しの参照切れ: ' + str(ref))
    for dep in all_dependencies(comp):
        if 'consumesCycle' in dep or 'trigger' in dep:
            errors.append('dependencies に非FIXの差し戻しが混入: ' + str(dep.get('from')) + '→' + str(dep.get('to')))
    return errors

def check_registry(root=ROOT):
    """登録簿から実在へ、実在から登録簿へ、の両方向で登録漏れと参照切れを検査する。"""
    comp = composition(root)
    if comp is None:
        return ['登録簿なし: ' + COMPOSITION]
    errors = []
    caps = all_capabilities(comp)
    refs = {c['ref'] for c in caps}
    known = set()
    for cap in caps:
        file = capability_file(root, cap)
        if not file.is_file():
            errors.append('登録された部品が無い: ' + cap['ref'])
        known.add(file.resolve())
    routing_errors = check_fix_routing(root, comp)
    errors.extend(routing_errors)
    errors.extend(check_non_fix_returns(root, comp))
    edges = {}
    for dep in all_dependencies(comp):
        if dep.get('type') not in {'calls', 'reads', 'delegates', 'revision'}:
            errors.append('未知の依存type: ' + str(dep.get('type')))
        if dep.get('from') not in refs or dep.get('to') not in refs:
            errors.append('未登録の部品への依存: ' + str(dep.get('from')) + ' -> ' + str(dep.get('to')))
        # 正本・工程表と一致した revision だけを依存DAGから除外する。
        if dep.get('type') != 'revision' or routing_errors:
            edges.setdefault(dep.get('from'), set()).add(dep.get('to'))
    if not acyclic(refs, edges):
        errors.append('部品の依存循環')
    impl = comp.get('implementation', {})
    declared = [impl.get(k) for k in ('owner', 'entrypoint', 'workflow', 'knowledgeIndex')]
    declared += [comp.get('revisionBudget', {}).get('rules'), comp.get('contract', {}).get('interface', {}).get('stageArtifacts')]
    # 宣言は実在だけを確かめる。owner のようにフォルダを指す宣言は、中身を信頼する理由にしない。
    for ref in filter(None, declared):
        if not resolve_ref(root, root, ref):
            errors.append('登録簿の参照切れ: ' + ref)
        target = (root / ref.partition('#')[0]).resolve()
        if target.is_file():
            known.add(target)
    # 登録簿そのもの・評価の書き先・配布契約の必要ファイルと manifest も登録済みとして扱う。評価の書き先は root 内のファイルとして実在させる。
    for sink in comp.get('eval_sinks', []):
        if not (resolve_ref(root, root, sink) and (root / sink).is_file()):
            errors.append('評価の書き先が無い: ' + str(sink))
    contract = load(root / CONTRACT) if (root / CONTRACT).is_file() else {}
    for item in [COMPOSITION, *comp.get('eval_sinks', []), *contract.get('required_files', []), *contract.get('manifests', [])]:
        known.add((root / item).resolve())
    # フォルダ単位の登録は attached_resources の '/' 終わりと、package.json の scripts が名指しするフォルダだけ。
    folders = []
    # 登録済みの package.json が scripts で実行するもの。直下のフォルダの中を指す語だけを見て、
    # 実在するファイルはそのファイルを、glob（npm test の tests/*.test.cjs など）は glob を含まない最も深い親を、
    # 名指ししたフォルダはそのフォルダを登録する。'..' でそのフォルダの外へ出る語は登録しない。
    npm = (root / 'package.json').resolve()
    if npm in known and npm.is_file():
        for command in load(npm).get('scripts', {}).values():
            for word in command.split():
                parts = word.split('/')
                top = (root / parts[0]).resolve()
                if len(parts) < 2 or top.parent != root.resolve() or not top.is_dir():
                    continue
                fixed = parts[:next((i for i, p in enumerate(parts) if GLOB.search(p)), len(parts))]
                target = root.joinpath(*fixed).resolve()
                if not target.is_relative_to(top):
                    continue
                if target.is_file() and fixed == parts:
                    known.add(target)
                elif target.is_dir():
                    folders.append(target)
    for items in impl.get('attached_resources', {}).values():
        for item in items:
            target = (root / item).resolve()
            if item.endswith('/'):
                folders.append(target)
            else:
                known.add(target)
            if not (target.is_dir() if item.endswith('/') else target.is_file()):
                errors.append('登録された資産が無い: ' + item)
    # 退役は配布から外した記録で、移行先は root 内のファイルにする。旧パスに残ったファイルは、
    # 登録扱いで照合を素通りして写るので止める（登録には入れて、同じファイルを「登録簿に無い」で二重に数えない）。
    for retired in comp.get('retired', []):
        replaced = retired.get('replacedBy', '')
        if not (resolve_ref(root, root, replaced) and (root / replaced).is_file()):
            errors.append('退役の移行先が無い: ' + str(retired.get('path')))
        if (root / retired['path']).exists():
            errors.append('退役したファイルが残っている: ' + retired['path'])
        known.add((root / retired['path']).resolve())

    # 素材は catalog の entries[].file と、別名が指す実ファイルで登録する。形式の検査と、別名が正規側と同じファイルを
    # 指すかの検査は check_asset_catalog が受け持つ（ここで「登録簿に無い」と二重に数えない）。
    assets = (root / 'assets').resolve()
    for entry in catalog_entries(root) or []:
        provenance = entry.get('provenance') if isinstance(entry, dict) else None
        history = provenance.get('aliases') if isinstance(provenance, dict) else None
        for item in [entry, *(history if isinstance(history, list) else [])]:
            file = item.get('file') if isinstance(item, dict) else None
            target = (assets / file).resolve() if isinstance(file, str) else None
            if target and target.is_relative_to(assets) and target.is_file():
                known.add(target)

    def registered(path):
        """名指しの登録か、フォルダ単位の登録の中か。フォルダ単位の登録でも隠し名は信頼しない。"""
        path = path.resolve()
        return path in known or any(path.is_relative_to(f) and not any(p.startswith('.') for p in path.relative_to(f).parts) for f in folders)
    # 登録済み skill のうち、check_stage_contracts が SKILL.md と manifest を読み、
    # check_manifest が中身を resources と照合するフォルダ。ここだけは降りずに任せる。
    staged = {(root / 'skills' / Path(c['ref']).name).resolve() for c in caps if c.get('kind') == 'skill'}
    staged = {base for base in staged if (base / 'SKILL.md').is_file() and (base / 'workflow-manifest.json').is_file()}
    # 任せたフォルダの中でも、skill 付きの agent は resources とは別に capabilities に載っていなければならない。
    for path in sorted((root / 'skills').glob('*/agents/*.md')):
        if path.parent.parent.resolve() in staged and not ignored(root, path) and not registered(path):
            errors.append('登録簿に無い: ' + str(path.relative_to(root)))
    marks = [*known, *folders]

    # 写るものは root から降りて照合する。登録済みのものを含むフォルダとフォルダ単位の登録は中へ降り、
    # 子にも同じ規則を当てる（フォルダ単位の登録の中に置いた隠し名もここで見つかる）。未登録はその場所で 1 回だけ報告する。
    def walk(folder):
        for path in sorted(folder.iterdir()):
            if ignored(root, path) or path.resolve() in staged:
                continue
            if path.is_dir() and (registered(path) or any(p.is_relative_to(path.resolve()) for p in marks)):
                walk(path)
            elif not registered(path):
                errors.append('登録簿に無い: ' + str(path.relative_to(root)))
    walk(root)
    return errors

def check_links(root=ROOT):
    """配布する markdown と HTML の相対リンクが、root 内のファイルと見出しへ解決するか。

    markdown はコードフェンスの外の [文](リンク) と href/src を、HTML は href/src を見る。スキーム付きと '//' 始まりは外部として見ない。
    '?' 以降は外す。'#' の見出しは markdown への参照のときだけ照合し、それ以外への参照はファイルの実在だけを見る。
    """
    errors = []
    for file in shipped(root):
        if file.suffix not in ('.md', '.html') or not file.is_file():
            continue
        text = file.read_text(encoding='utf-8')
        if file.suffix == '.md':
            text = re.sub(r'```.*?```', '', text, flags=re.S)
        links = (LINK.findall(text) if file.suffix == '.md' else []) + [m[1] for m in ATTR.findall(text)]
        for link in links:
            if re.match(r'[a-z][a-z0-9+.-]*:', link, re.I) or link.startswith('//'):
                continue
            path, _, heading = link.partition('#')
            path = path.partition('?')[0] or file.name
            if not resolve_ref(root, file.parent, path + ('#' + heading if heading and path.endswith('.md') else '')):
                errors.append('本文リンク切れ: ' + str(file.relative_to(root)) + ' -> ' + link)
    return errors

def check_symlinks(root=ROOT):
    """配布対象の symlink を、リンク先が root の内でも外でも止める。

    copytree はリンク先の中身を写し、shipped() はリンクしたフォルダへ降りず、登録簿の照合はリンク先の実体で済ませる。
    どれもリンクそのものを見ないので、黙って写る前にここで検査エラーにする。
    """
    return ['配布対象のsymlink: ' + str(p.relative_to(root)) + ' -> ' + str(p.readlink()) for p in shipped(root) if p.is_symlink()]

def check_versions(root, version, contract):
    """plugin manifest の版を正として、登録簿・評価・manifest・frontmatter の版が揃っているか。"""
    sources = {p: load(root / p).get('version') for p in contract['manifests'] + ['package.json', COMPOSITION, 'EVALS.json']}
    lock = root / 'package-lock.json'
    locked = load(lock) if lock.is_file() else {}
    sources['package-lock.json'] = locked.get('version')
    sources['package-lock.json#packages[""].version'] = locked.get('packages', {}).get('', {}).get('version')
    for file in sorted(root.glob('skills/*/workflow-manifest.json')):
        sources[str(file.relative_to(root))] = load(file).get('version')
    for file in sorted([*root.glob('skills/*/SKILL.md'), *root.glob('skills/*/agents/*.md'), *root.glob('agents/*.md')]):
        fm = frontmatter(file) or {}
        if 'version' in fm:
            sources[str(file.relative_to(root))] = fm['version']
    return ['版の不一致: ' + p + ' = ' + str(v) for p, v in sources.items() if v != version]

def check_entry_points(root, contract):
    """全skillの登録とtop-level agentを照合する。直接起動の可否は各frontmatterで制限する。"""
    caps = all_capabilities(composition(root) or {})
    expected = {
        'skills': sorted(Path(c['ref']).name for c in caps if c.get('kind') == 'skill'),
        'agents': sorted(Path(c['ref']).name for c in caps if c.get('kind') == 'agent' and c['ref'].startswith('agents/')),
    }
    return ['入口の不一致: entry_points.' + k for k, v in expected.items() if sorted(contract['entry_points'].get(k, [])) != v]

def check_asset_catalog(root=ROOT):
    """素材の境界・用途・案件隔離・正規ID/別名・別名が指す実ファイルを検査する。"""
    errors, ids, shas = [], set(), set()
    assets = (root / 'assets').resolve()
    entries, problem = read_catalog(root)
    if entries is None:
        return [problem]
    for entry in entries:
        if not isinstance(entry, dict):
            errors.append('素材エントリの形式: ' + str(entry))
            continue
        label = str(entry.get('id'))
        aliases = entry.get('aliases', [])
        if not isinstance(aliases, list) or not all(isinstance(a, str) and a for a in aliases):
            errors.append('素材別名の形式: ' + label)
            aliases = []
        for identifier in [entry.get('id'), *aliases]:
            if not isinstance(identifier, str) or not identifier or identifier in ids:
                errors.append('素材ID/別名の重複・欠落: ' + label)
            if isinstance(identifier, str):
                ids.add(identifier)
        sha, file_ref = entry.get('sha256'), entry.get('file')
        if not isinstance(sha, str) or not isinstance(file_ref, str) or not file_ref:
            errors.append('素材SHA/境界: ' + label)
            continue
        if sha in shas:
            errors.append('素材SHAの重複: ' + label)
        shas.add(sha)
        path = (assets / file_ref).resolve()
        if not path.is_relative_to(assets) or not path.is_file() or digest(path) != sha:
            errors.append('素材SHA/境界: ' + label)
        if entry.get('kind') in ['example', 'reference'] and entry.get('usage') != 'reference-only':
            errors.append('参照素材の用途: ' + label)
        privacy = entry.get('privacy', {})
        if not isinstance(privacy, dict) or type(privacy.get('containsPeople')) is not bool:
            errors.append('素材privacy.containsPeopleは真偽値: ' + label)
        # provenance と preset は形が崩れていても例外で止めず、どの素材の何が崩れたかを返す。
        provenance = entry.get('provenance', {})
        if not isinstance(provenance, dict):
            errors.append('素材provenanceの形式: ' + label)
            provenance = {}
        preset = entry.get('preset')
        if provenance.get('project') and not preset:
            errors.append('案件素材のpreset欠落: ' + label)
        if preset:
            file = (root / 'references/presets' / preset / 'preset.json').resolve() if isinstance(preset, str) else None
            base = (root / 'references/presets').resolve()
            found, why = None, ''
            if file and file.is_relative_to(base) and file.is_file():
                try:
                    found = load(file, root)
                except ValueError as exc:
                    why = ' (' + str(exc) + ')'
            if not isinstance(found, dict) or found.get('id') != preset:
                errors.append('素材preset参照切れ: ' + label + why)
        history = provenance.get('aliases', [])
        if not isinstance(history, list) or not all(isinstance(e, dict) and isinstance(e.get('id'), str) and isinstance(e.get('file'), str) for e in history) or {e['id'] for e in history} != set(aliases):
            errors.append('素材別名の履歴欠落: ' + label)
            continue
        # 別名は正規側と同じ実ファイルを指す。SHA が同じでも別のパスなら、同じ画像を二重に同梱している。
        # 正規側のファイルの境界・実在・SHA は上で照合済みなので、ここでは別名の記録の SHA とパスが正規側と一致するかだけを見る。
        for original in history:
            if original.get('sha256') != sha or (assets / original['file']).resolve() != path:
                errors.append('素材別名が指す実ファイル/SHA: ' + label)
    return errors

def check():
    contract = load(ROOT / CONTRACT)
    errors = check_stage_contracts() + check_registry() + check_links() + check_entry_points(ROOT, contract)
    manifests = [load(ROOT / p) for p in contract['manifests']]
    for key in ['name', 'version', 'description', 'author']:
        if len({json.dumps(m.get(key), sort_keys=True) for m in manifests}) != 1:
            errors.append('manifestの不一致: ' + key)
    if manifests[0]['name'] != ROOT.name:
        errors.append('plugin名とフォルダ名の不一致')
    errors += check_versions(ROOT, manifests[0]['version'], contract)
    errors += check_symlinks(ROOT)
    entries = catalog_entries(ROOT) or []
    errors += check_asset_catalog(ROOT)
    for p in contract['required_files']:
        if not (ROOT / p).is_file():
            errors.append('必要ファイルなし: ' + p)
    # Gallery HTML is a generated offline view, not a second editable catalog.
    gallery = subprocess.run([sys.executable, '-I', str(ROOT / 'scripts/build-asset-gallery.py'), '--check'], capture_output=True, text=True)
    if gallery.returncode:
        errors.append('素材一覧がcatalog正本と一致しません')
    if contract['distribution']['distributable'] is not False:
        errors.append('個人素材入りの公開配布は禁止')
    return {'plugin': manifests[0]['name'], 'version': manifests[0]['version'], 'assets': len(entries), 'errors': errors, 'fail': len(errors)}

def package(out):
    report = check()
    if report['fail']:
        raise ValueError(json.dumps(report, ensure_ascii=False))
    out = Path(out).expanduser().resolve()
    if out.exists() or out.is_relative_to(ROOT) or Path(str(out) + '.zip').exists():
        raise ValueError('既存出力やプラグイン内へは書きません。新しい出力先を指定してください')
    plugin = out / 'plugins/flyer-studio'
    shutil.copytree(ROOT, plugin, ignore=IGNORE)
    # harnessにだけ必要な観測runtimeを単独キットへ持ち込まない。
    # 制作機能の依存はpackage-lock.jsonで携行し、それ以外の依存宣言は保持する。
    contract = load(plugin / CONTRACT)
    repo_only = set(contract.get('repository_runtime_dependencies', []))
    if repo_only:
        manifest_path = plugin / '.claude-plugin/plugin.json'
        manifest = load(manifest_path)
        dependencies = [d for d in manifest.get('dependencies', [])
                        if (d if isinstance(d, str) else d.get('name')) not in repo_only]
        if dependencies:
            manifest['dependencies'] = dependencies
        else:
            manifest.pop('dependencies', None)
        manifest_path.write_text(json.dumps(manifest, ensure_ascii=False, indent=2) + '\n', encoding='utf-8')
        contract['depends_on'] = [d for d in contract.get('depends_on', []) if d not in repo_only]
        contract.pop('repository_runtime_dependencies', None)
        contract.pop('repository_runtime_reason', None)
        (plugin / CONTRACT).write_text(json.dumps(contract, ensure_ascii=False, indent=2) + '\n', encoding='utf-8')
    # repositoryの中央ポリシー投影は単独ホストの実行資産ではない。
    # 兄弟pluginへの観測メタデータをキットへ持ち込まず、必要ファイル台帳も同期する。
    contract['required_files'] = [p for p in contract.get('required_files', []) if p != 'artifact-delivery.json']
    (plugin / CONTRACT).write_text(json.dumps(contract, ensure_ascii=False, indent=2) + '\n', encoding='utf-8')
    catalogs = {
        '.claude-plugin/marketplace.json': {'name': 'flyer-studio-local', 'owner': {'name': 'harness maintainers'}, 'metadata': {'description': '個人素材を含むFlyer Studioのローカル導入キット'}, 'plugins': [{'name': 'flyer-studio', 'source': './plugins/flyer-studio'}]},
        '.agents/plugins/marketplace.json': {'name': 'flyer-studio-local', 'interface': {'displayName': 'Flyer Studio（ローカル）'}, 'plugins': [{'name': 'flyer-studio', 'source': {'source': 'local', 'path': './plugins/flyer-studio'}, 'policy': {'installation': 'AVAILABLE', 'authentication': 'ON_INSTALL'}, 'category': 'Productivity'}]}
    }
    for name, data in catalogs.items():
        p = out / name
        p.parent.mkdir(parents=True, exist_ok=True)
        p.write_text(json.dumps(data, ensure_ascii=False, indent=2) + '\n', encoding='utf-8')
    rows = [{'file': str(p.relative_to(out)), 'sha256': digest(p)} for p in sorted(out.rglob('*')) if p.is_file()]
    (out / 'kit-manifest.json').write_text(json.dumps({'private_assets': True, 'files': rows}, ensure_ascii=False, indent=2) + '\n', encoding='utf-8')
    archive = Path(shutil.make_archive(str(out), 'zip', root_dir=out.parent, base_dir=out.name))
    return {'directory': str(out), 'archive': str(archive), 'sha256': digest(archive), 'files': len(rows), 'global_settings_changed': False, 'fail': 0}

def main():
    parser = argparse.ArgumentParser(description=__doc__)
    group = parser.add_mutually_exclusive_group(required=True)
    group.add_argument('--check', action='store_true')
    group.add_argument('--out')
    args = parser.parse_args()
    try:
        result = check() if args.check else package(args.out)
        print(json.dumps(result, ensure_ascii=False, indent=2))
        return 1 if result['fail'] else 0
    except (ValueError, OSError, KeyError) as exc:
        print(str(exc), file=sys.stderr)
        return 1

if __name__ == '__main__':
    sys.exit(main())
