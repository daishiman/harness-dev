#!/usr/bin/env python3
# /// script
# name: build-local-package
# purpose: 部品登録と参照・素材・版の整合を検査し、許可されたローカル導入キットを生成する
# inputs: argv: --check・--out・--write-composition のどれか、plugin-local登録簿と配布契約
# outputs: 検査JSON、終了コード、--out指定時の導入キット
# contexts: [C, E]
# network: false
# write-scope: --checkはnone。--write-composition は plugin-composition.yaml のみ。--out指定の新規出力dirと、その隣の同名zipのみ
# dependencies: []
# ///
"""個人用プラグインの自己完結検査と、両製品用ローカル導入キット生成。

部品の登録簿は references/registry.json、配布条件は references/package-contract.json が正本。harness 書式の
plugin-composition.yaml は登録簿から --write-composition で生成する写しで、--check が生成との一致を見る。
この検査は stage 名・指針 ID・必要ファイルを持たず、正本から読んで両方向に照合する。
"""
import argparse
import hashlib
import json
import posixpath
import re
from pathlib import Path
import shutil
import subprocess
import sys
import unicodedata

ROOT = Path(__file__).resolve().parent.parent
# repo専用で独立ローカルキットに含めない skill。harness の共有正本（harness-creator）の実体コピーを置き、
# repo では vendored SSOT の lint が正本との byte 一致を、ここでは名前だけを宣言する。
# 外した skill は登録簿・版・リンクの照合から外れる（キットに写らないものは照合しない）。入口の台帳
# （entry_points.skills）には plugin 内の skill として載せ、check_entry_points が実在と照合する。キットへ写すときは
# narrow_kit() が台帳の entry_points.skills と runtime_dependencies からも外す。
KIT_EXCLUDED_SKILLS = {'run-skill-feedback'}
# 外した skill の実行時だけが要る repo 側 plugin。キットの .claude-plugin/plugin.json の dependencies と、台帳の depends_on から外す。
# 登録簿の外部依存のうち外した skill だけが要るもの（harness-creator）は、定数ではなく needed_externals() が導いて同じく外す。
KIT_EXCLUDED_DEPENDENCIES = {'skill-governance-adapters'}
# plugin 直下の repo 用の台帳。artifact-delivery.json は harness の build-artifact-delivery.py が生成し lint-artifact-delivery.py
# が照合するもので、外す skill の入口も載る。キットへは写さない（各 skill の effect は SKILL.md の frontmatter が運ぶ）。
KIT_EXCLUDED_ROOT_FILES = {'artifact-delivery.json'}
# 入口の地図。repo では plugin 直下に SKILL.md を置かず（harness の skill 走査は plugins/*/SKILL.md を 0 件と定める）、
# 正本を references/kit-entry.md に置く。render_kit_entry() がリンクを plugin 直下からの相対に直し、
# narrow_kit()（package() が呼ぶ）がそれをキット直下の SKILL.md として書き出す。
KIT_ENTRY = 'references/kit-entry.md'
KIT_ENTRY_OUTPUT = 'SKILL.md'
EXCLUDE = {'node_modules', '.cache', '__pycache__', '.git', '.claude', 'development-plan', 'verification'}
# 配布キットへ写さない名前。package() の複写と、shipped() を通る全ての照合が同じ規則を使う。
# 写るものは名前によらず登録簿と照合する。ただしフォルダ単位で登録した場所は隠し名（'.' で始まる名前）を除く
# 中身を登録で信頼し、skills/<name>/ の中身は stage 検査が resources と照合する。.gitignore の除外対象はどれも既にここで外れる。
# ただし assets/ の素材画像は git 管理から外すだけで、キットへは写す（catalog の entries[].file で登録を照合する）。
BASE_IGNORE = shutil.ignore_patterns(*EXCLUDE, '*.tmp', '.DS_Store', '.gitignore')

def IGNORE(directory, names, root=None):
    ignored_names = BASE_IGNORE(directory, names)
    root = ROOT if root is None else root
    # skills/ 直下の宣言した名前だけを外す。symlink かどうかでは判定しない（symlink は check_kit_exclusions が止める）。
    if Path(directory).resolve() == (root / 'skills').resolve():
        ignored_names.update(KIT_EXCLUDED_SKILLS.intersection(names))
    # plugin 直下の名前だけを外す。同じ名前でも下のフォルダにあるものは写し、登録簿と照合する。
    if Path(directory).resolve() == Path(root).resolve():
        ignored_names.update(KIT_EXCLUDED_ROOT_FILES.intersection(names))
    return ignored_names
# 部品の登録簿（正本）。stage・revision・nonFixReturns・skill 内の agent まで、flyer の検査が読むものは全てここに置く。
REGISTRY = 'references/registry.json'
# harness 書式の部品宣言。render_composition() が登録簿と manifest から生成する写しで、手で直さない。
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
    return any(part in IGNORE(str(root.joinpath(*parts[:i])), [part], root=root) for i, part in enumerate(parts))

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

def registry(root):
    file = root / REGISTRY
    return load(file, root) if file.is_file() else None

# plain（引用なし）で書く形。文字で始まる語と、X.Y.Z の版だけを許す。数・日付・null・真偽・merge key に読まれる形
# （0b101・1_000.5・.inf・2026-10-31・<< など）は除く側の表では拾い漏れるので、許す側を決めて残りは引用する。
# 版を plain にするのは、release が版の行を引用なしで書き換えるため（引用すると上げた後に生成と byte で一致しない）。
# 流れ表記（[...]・{...}）の中でも崩れないよう ',' と '?' と括弧を、YAML が改行とみなす文字・制御文字・読めない文字も外す。
PLAIN = re.compile(r'''[^\W\d_][^:#,?\[\]{}'"\x00-\x1f\x7f-\x9f\u2028\u2029\ufffe\uffff]*|\d+(?:\.\d+){2,}''')
# 文字で始まっても、plain だと null・真偽に読まれる語。
NON_STRING_WORDS = re.compile(r'(?i)null|true|false|yes|no|on|off|y|n')
# 二重引用の中でも YAML が改行として畳む文字・そのままでは書けない文字。JSON の \\uXXXX は YAML の二重引用でも同じ文字を表す。
UNSAFE_IN_QUOTES = re.compile('[\x7f-\x9f\u2028\u2029\ufffe\uffff]')

def scalar(value):
    """YAML の 1 値。plain で書けない文字列は JSON の二重引用にする（JSON の文字列は YAML の二重引用としても読める）。"""
    if isinstance(value, bool):
        return 'true' if value else 'false'
    text = str(value)
    if PLAIN.fullmatch(text) and text == text.strip() and not NON_STRING_WORDS.fullmatch(text):
        return text
    return quoted(text)

def quoted(text):
    """常に二重引用で書く YAML の 1 値。"""
    return UNSAFE_IN_QUOTES.sub(lambda m: '\\u%04x' % ord(m.group()), json.dumps(str(text), ensure_ascii=False))

def flow(items):
    return '[' + ', '.join(scalar(v) for v in items) + ']'

def mapping(data, keys):
    return '{ ' + ', '.join(k + ': ' + scalar(data[k]) for k in keys) + ' }'

def needed_externals(root, reg):
    """登録簿の外部依存のうち、root の中身で要るもの。required_entry_points が全て実在しない KIT_EXCLUDED_SKILLS に当たるもの
    （キットで外した skill だけが要る依存）を落とす。キットの composition と package-contract.json の depends_on が同じ判定を使う。"""
    absent = {n for n in KIT_EXCLUDED_SKILLS if not (root / 'skills' / n / 'SKILL.md').is_file()}
    return {name: spec for name, spec in reg.get('external_dependencies', {}).items()
            if not (spec.get('required_entry_points') and set(spec['required_entry_points']) <= absent)}

def render_composition(root=ROOT):
    """登録簿と manifest から、harness 書式の plugin-composition.yaml を作る。

    載せるのは harness が読む面だけ（名前・版・説明・owner・contract・eval_sinks・公開面・依存の DAG・外部依存）。
    capabilities は登録簿の skill・plugin 直下の agent と、実在する KIT_EXCLUDED_SKILLS。
    dependencies は依存の DAG だけで、revision（FIX の戻り）を外し、skill 内の agent の端はその skill へ寄せる。
    external_dependencies は needed_externals が絞る。版と名前は manifest が正本なので、release が manifest と一緒に上げた版と
    ここで一致する。

    """
    reg = registry(root)
    if reg is None:
        raise ValueError('登録簿なし: ' + REGISTRY)
    contract = load(root / CONTRACT, root)
    manifest = load(root / contract['manifests'][0], root)
    excluded = sorted(n for n in KIT_EXCLUDED_SKILLS if (root / 'skills' / n / 'SKILL.md').is_file())
    caps = [c for c in reg.get('capabilities', []) if c.get('kind') == 'skill' or c['ref'].startswith('agents/')]
    caps += [{'kind': 'skill', 'ref': 'skills/' + n, 'tier': 'core'} for n in excluded]
    caps.sort(key=lambda c: (c['kind'] != 'skill', c['ref']))
    def lift(ref):
        parts = ref.split('/')
        return '/'.join(parts[:2]) if parts[0] == 'skills' and len(parts) > 2 else ref
    edges = []
    for dep in reg.get('dependencies', []):
        if dep.get('type') == 'revision':
            continue
        edge = {'from': lift(dep['from']), 'to': lift(dep['to']), 'type': dep['type']}
        if edge['from'] != edge['to'] and edge not in edges:
            edges.append(edge)
    externals = needed_externals(root, reg)
    interface = reg.get('contract', {}).get('interface', {})
    lines = [
        '# 生成物。正本は ' + REGISTRY + ' で、scripts/build-local-package.py --write-composition が書き直す。手で直さない。',
        'name: ' + scalar(manifest['name']),
        'description: ' + scalar(reg.get('description') or manifest['description']),
        'kind: plugin-composition',
        'version: ' + scalar(manifest['version']),
        'owner: ' + scalar(reg.get('owner', 'harness maintainers')),
        '',
        'contract:',
        '  intent: ' + scalar(reg.get('contract', {}).get('intent', '')),
        '  interface:',
        '    inputs: ' + flow(interface.get('inputs', [])),
        '    outputs: ' + flow(interface.get('outputs', [])),
        '  invariant:',
        *('    - ' + quoted(v) for v in reg.get('contract', {}).get('invariant', [])),
        '',
        'capabilities:',
        *('  - ' + mapping(c, ['kind', 'ref', 'tier']) for c in caps),
        '',
        'dependencies:' + ('' if edges else ' []'),
        *('  - ' + mapping(e, ['from', 'to', 'type']) for e in edges),
    ]
    if externals:
        lines += ['', 'external_dependencies:']
        for name, spec in externals.items():
            lines += ['  ' + scalar(name) + ':', '    version: ' + quoted(spec['version']), '    relation: ' + scalar(spec['relation']),
                      '    required_entry_points: ' + flow(spec.get('required_entry_points', []))]
    lines += ['', 'eval_sinks: ' + flow(reg.get('eval_sinks', []))]
    return '\n'.join(lines) + '\n'

def check_composition(root=ROOT):
    """plugin-composition.yaml が登録簿からの生成と一致するか。登録簿の不備は check_registry が別に示す。"""
    file = root / COMPOSITION
    try:
        expected = render_composition(root)
    except (ValueError, OSError, KeyError):
        expected = None
    if expected is None or not file.is_file() or file.read_text(encoding='utf-8') != expected:
        return [COMPOSITION + ' が ' + REGISTRY + ' からの生成と不一致（--write-composition で書き直す）']
    return []

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

def doc_links(text, markdown):
    """本文の相対リンク候補。markdown はコードフェンスの外の [文](リンク) と href/src を、HTML は href/src を返す。"""
    if markdown:
        text = re.sub(r'```.*?```', '', text, flags=re.S)
    return (LINK.findall(text) if markdown else []) + [m[1] for m in ATTR.findall(text)]

def render_kit_entry(root=ROOT):
    """references/kit-entry.md を、plugin 直下の SKILL.md として読める本文にする。

    コードフェンスの外の [文](リンク) と href/src のうち、相対パスのものを plugin 直下からの相対へ直す。
    スキーム付き・'//' 始まり・'#' だけのリンクはそのまま。plugin の外へ出るリンクは書き出さずに止める。
    """
    source = root / KIT_ENTRY
    parent = posixpath.dirname(KIT_ENTRY)

    def move(link):
        if re.match(r'[a-z][a-z0-9+.-]*:', link, re.I) or link.startswith(('//', '#')):
            return link
        path, sep, rest = link.partition('#')
        moved = posixpath.normpath(posixpath.join(parent, path))
        if moved == '..' or moved.startswith('../'):
            raise ValueError('入口の地図のリンクが plugin の外を指す: ' + KIT_ENTRY + ' -> ' + link)
        return moved + sep + rest

    def link_sub(match):
        return '](' + move(match.group(1)) + ')'

    def attr_sub(match):
        whole, start = match.group(0), match.start(0)
        return whole[:match.start(2) - start] + move(match.group(2)) + whole[match.end(2) - start:]

    parts = re.split(r'(```.*?```)', source.read_text(encoding='utf-8'), flags=re.S)
    return ''.join(part if i % 2 else ATTR.sub(attr_sub, LINK.sub(link_sub, part)) for i, part in enumerate(parts))

def check_kit_entry(root=ROOT):
    """入口の地図を、キット直下の SKILL.md として書き出したときに読めるか。

    正本（references/kit-entry.md）が無い plugin では何もしない（実 plugin では配布契約の required_files が存在を求める）。
    書き出した本文の name が plugin 名と一致し、リンクが plugin 直下から解決することを確かめる。plugin 直下に
    SKILL.md があるとき（書き出し済みのキット）は、正本から書き出したものと一致しなければ止める。
    """
    if not (root / KIT_ENTRY).is_file():
        return []
    try:
        text = render_kit_entry(root)
    except ValueError as exc:
        return [str(exc)]
    errors = []
    match = re.match(r'^---\s*\n(.*?)\n---(?:\n|$)', text, re.S)
    name = re.search(r'^name:\s*(\S+)\s*$', match.group(1), re.M) if match else None
    if not name or name.group(1).strip('"\'') != root.name:
        errors.append('入口の地図の name が plugin 名と不一致: ' + KIT_ENTRY)
    for link in doc_links(text, True):
        if re.match(r'[a-z][a-z0-9+.-]*:', link, re.I) or link.startswith('//'):
            continue
        path, _, heading = link.partition('#')
        path = path.partition('?')[0] or KIT_ENTRY_OUTPUT
        if not resolve_ref(root, root, path + ('#' + heading if heading and path.endswith('.md') else '')):
            errors.append('入口の地図のリンク切れ（キット直下）: ' + KIT_ENTRY + ' -> ' + link)
    written = root / KIT_ENTRY_OUTPUT
    if written.exists() and (not written.is_file() or written.read_text(encoding='utf-8') != text):
        errors.append('plugin 直下の ' + KIT_ENTRY_OUTPUT + ' が ' + KIT_ENTRY + ' の書き出しと不一致')
    return errors

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
    caps = [c for c in comp.get('capabilities', []) if c.get('kind') == 'skill']
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
    comp = registry(root)
    if comp is None:
        return ['登録簿なし: ' + REGISTRY]
    errors = []
    skills = {Path(c['ref']).name: c.get('stage') for c in comp.get('capabilities', []) if c.get('kind') == 'skill'}
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
    revisions = [d for d in comp.get('dependencies', []) if d.get('type') == 'revision']
    if not routes:
        return ['fixRouting の無い revision 関係'] if revisions else []
    skills = {Path(c['ref']).name: c['ref'] for c in comp.get('capabilities', []) if c.get('kind') == 'skill'}
    stages = {c.get('stage'): c['ref'] for c in comp.get('capabilities', []) if c.get('kind') == 'skill'}
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
        forward = [d for d in comp.get('dependencies', []) if (d.get('from'), d.get('to')) == pair and d.get('type') == 'calls']
        if None in pair or len(forward) != 1 or forward[0].get('analysisMode') != mode or forward[0].get('fixClass') is not None or re.search(r'fixClass\s*=\s*premise', forward[0].get('condition', '')):
            errors.append('通常呼出の analysisMode/前提分岐が不一致: ' + str(pair))
    return errors

def check_non_fix_returns(root, comp):
    """cycle を消費しない差し戻し（nonFixReturns）を、FIX の revision 辺と混ぜずに置いているか。"""
    returns = comp.get('nonFixReturns', [])
    if not isinstance(returns, list) or not all(isinstance(r, dict) for r in returns):
        return ['非FIXの差し戻しの形式: nonFixReturns は object の配列にする']
    skills = {c['ref'] for c in comp.get('capabilities', []) if c.get('kind') == 'skill'}
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
    for dep in comp.get('dependencies', []):
        if 'consumesCycle' in dep or 'trigger' in dep:
            errors.append('dependencies に非FIXの差し戻しが混入: ' + str(dep.get('from')) + '→' + str(dep.get('to')))
    return errors

def check_registry(root=ROOT):
    """登録簿から実在へ、実在から登録簿へ、の両方向で登録漏れと参照切れを検査する。"""
    comp = registry(root)
    if comp is None:
        return ['登録簿なし: ' + REGISTRY]
    errors = []
    caps = comp.get('capabilities', [])
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
    for dep in comp.get('dependencies', []):
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
    for item in [REGISTRY, COMPOSITION, *comp.get('eval_sinks', []), *contract.get('required_files', []), *contract.get('manifests', [])]:
        known.add((root / item).resolve())
    # 入口の地図の書き出し先（キット直下の SKILL.md）。中身が正本の書き出しと一致するかは check_kit_entry が見る。
    if (root / KIT_ENTRY).is_file():
        known.add((root / KIT_ENTRY_OUTPUT).resolve())
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
        for link in doc_links(file.read_text(encoding='utf-8'), file.suffix == '.md'):
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

def check_kit_exclusions(root=ROOT):
    """キットから外す skill は実体のフォルダで置く。

    外した名前は shipped() に現れないので check_symlinks では見えない。共有正本への symlink に戻ると、
    repo の外（plugin cache）で解決できなくなるため、ここで止める。
    """
    errors = []
    for name in sorted(KIT_EXCLUDED_SKILLS):
        path = root / 'skills' / name
        if path.is_symlink():
            errors.append('キット除外skillがsymlink: skills/' + name + ' -> ' + str(path.readlink()))
        elif path.exists() and not (path / 'SKILL.md').is_file():
            errors.append('キット除外skillにSKILL.mdが無い: skills/' + name)
    return errors

def check_versions(root, version, contract):
    """plugin manifest の版を正として、評価・manifest・frontmatter の版が揃っているか。

    登録簿は版を持たない。plugin-composition.yaml の版は manifest から生成するので、check_composition が一致を見る。
    """
    sources = {p: load(root / p).get('version') for p in contract['manifests'] + ['package.json', 'EVALS.json']}
    lock = root / 'package-lock.json'
    locked = load(lock) if lock.is_file() else {}
    sources['package-lock.json'] = locked.get('version')
    sources['package-lock.json#packages[""].version'] = locked.get('packages', {}).get('', {}).get('version')
    for file in sorted(root.glob('skills/*/workflow-manifest.json')):
        if not ignored(root, file):
            sources[str(file.relative_to(root))] = load(file).get('version')
    for file in sorted([*root.glob('skills/*/SKILL.md'), *root.glob('skills/*/agents/*.md'), *root.glob('agents/*.md')]):
        if ignored(root, file):
            continue
        fm = frontmatter(file) or {}
        if 'version' in fm:
            sources[str(file.relative_to(root))] = fm['version']
    return ['版の不一致: ' + p + ' = ' + str(v) for p, v in sources.items() if v != version]

def check_entry_points(root, contract):
    """入口の台帳を、登録簿から導いた集合と照合する。

    entry_points は harness の台帳（package-contract.schema.json）で、skills は登録簿の全 skill に
    KIT_EXCLUDED_SKILLS のうち実在するものを足した集合、agents は top-level の agent。
    user_invocable_skills は利用者が直接呼べる skill（frontmatter の user-invocable が false でないもの）。
    """
    caps = (registry(root) or {}).get('capabilities', [])
    def invocable(cap):
        file = capability_file(root, cap)
        return file.is_file() and (frontmatter(file) or {}).get('user-invocable', 'true') != 'false'
    skills = [c for c in caps if c.get('kind') == 'skill']
    excluded = {n for n in KIT_EXCLUDED_SKILLS if (root / 'skills' / n / 'SKILL.md').is_file()}
    expected = {
        'entry_points.skills': sorted({Path(c['ref']).name for c in skills} | excluded),
        'entry_points.agents': sorted(Path(c['ref']).name for c in caps if c.get('kind') == 'agent' and c['ref'].startswith('agents/')),
        'user_invocable_skills': sorted(Path(c['ref']).name for c in skills if invocable(c)),
    }
    declared = {
        'entry_points.skills': contract.get('entry_points', {}).get('skills', []),
        'entry_points.agents': contract.get('entry_points', {}).get('agents', []),
        'user_invocable_skills': contract.get('user_invocable_skills', []),
    }
    return ['入口の不一致: ' + k for k, v in expected.items() if sorted(declared[k]) != v]

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
    errors = check_stage_contracts() + check_registry() + check_composition() + check_links() + check_entry_points(ROOT, contract)
    manifests = [load(ROOT / p) for p in contract['manifests']]
    for key in ['name', 'version', 'description', 'author']:
        if len({json.dumps(m.get(key), sort_keys=True) for m in manifests}) != 1:
            errors.append('manifestの不一致: ' + key)
    if manifests[0]['name'] != ROOT.name:
        errors.append('plugin名とフォルダ名の不一致')
    errors += check_versions(ROOT, manifests[0]['version'], contract)
    errors += check_symlinks(ROOT)
    errors += check_kit_exclusions(ROOT)
    errors += check_kit_entry(ROOT)
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

def narrow_kit(plugin, source=ROOT):
    """IGNORE で写したキットの plugin（plugin）を、外した skill と、それだけが要る依存を宣言しない形に直す。

    package() が複写の直後に呼ぶ。素材の検査（check）は通さないので、テストは素材の無い写しにも当てられる。
    source は入口の地図の正本を読む repo 側の plugin。
    """
    # キットの部品宣言を、写した中身から作り直す（外した skill と、それだけが要る外部依存が落ちる）。
    (plugin / COMPOSITION).write_text(render_composition(plugin), encoding='utf-8')
    # 入口の地図を、リンクを直してキット直下の SKILL.md として書き出す（正本の references/kit-entry.md もキットに写る）。
    if (source / KIT_ENTRY).is_file():
        (plugin / KIT_ENTRY_OUTPUT).write_text(render_kit_entry(source), encoding='utf-8')
    # キットに写さない skill だけが要る依存を、キットの manifest から外す（独立キットの marketplace では解決できない）。
    manifest = plugin / '.claude-plugin/plugin.json'
    if manifest.is_file():
        data = load(manifest)
        kept = [d for d in data.get('dependencies', []) if (d.get('name') if isinstance(d, dict) else d) not in KIT_EXCLUDED_DEPENDENCIES]
        if kept:
            data['dependencies'] = kept
        else:
            data.pop('dependencies', None)
        manifest.write_text(json.dumps(data, ensure_ascii=False, indent=2) + '\n', encoding='utf-8')
    # 入口の台帳からも、キットに写さない skill を外す。check_entry_points は外した skill を実在するときだけ
    # 期待に足すので、台帳に残すとキットの中の --check が入口の不一致で落ちる。repo の台帳はそのまま残る。
    # 同じ台帳の runtime_dependencies から外した skill の項目を、depends_on から manifest と同じ KIT_EXCLUDED_DEPENDENCIES と
    # キットの composition から落ちた外部依存（外した skill だけが要る plugin）を外し、キットが解決できない依存を宣言しない。
    ledger = plugin / CONTRACT
    if ledger.is_file():
        data = load(ledger, plugin)
        points = data.get('entry_points', {})
        points['skills'] = [n for n in points.get('skills', []) if n not in KIT_EXCLUDED_SKILLS]
        if 'runtime_dependencies' in data:
            data['runtime_dependencies'] = [d for d in data['runtime_dependencies'] if d.get('required_entry_point') not in KIT_EXCLUDED_SKILLS]
        if 'depends_on' in data:
            reg = registry(plugin) or {}
            dropped = KIT_EXCLUDED_DEPENDENCIES | (set(reg.get('external_dependencies', {})) - set(needed_externals(plugin, reg)))
            data['depends_on'] = [n for n in data['depends_on'] if n not in dropped]
        ledger.write_text(json.dumps(data, ensure_ascii=False, indent=2) + '\n', encoding='utf-8')

def package(out):
    report = check()
    if report['fail']:
        raise ValueError(json.dumps(report, ensure_ascii=False))
    out = Path(out).expanduser().resolve()
    if out.exists() or out.is_relative_to(ROOT) or Path(str(out) + '.zip').exists():
        raise ValueError('既存出力やプラグイン内へは書きません。新しい出力先を指定してください')
    plugin = out / 'plugins/flyer-studio'
    shutil.copytree(ROOT, plugin, ignore=IGNORE)
    narrow_kit(plugin)
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
    group.add_argument('--write-composition', action='store_true', help=REGISTRY + ' から ' + COMPOSITION + ' を書き直す')
    args = parser.parse_args()
    try:
        if args.write_composition:
            (ROOT / COMPOSITION).write_text(render_composition(ROOT), encoding='utf-8')
            result = {'written': COMPOSITION, 'fail': 0}
        else:
            result = check() if args.check else package(args.out)
        print(json.dumps(result, ensure_ascii=False, indent=2))
        return 1 if result['fail'] else 0
    except (ValueError, OSError, KeyError) as exc:
        print(str(exc), file=sys.stderr)
        return 1

if __name__ == '__main__':
    sys.exit(main())
