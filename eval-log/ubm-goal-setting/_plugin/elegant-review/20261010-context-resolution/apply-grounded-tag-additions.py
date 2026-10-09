#!/usr/bin/env python3
"""Apply independently identified tag repairs after background-stage freeze."""
import argparse
import copy
import hashlib
import json
from pathlib import Path
from jsonschema import Draft202012Validator, FormatChecker


def sha(value):
    return hashlib.sha256(value).hexdigest()


def stable(value):
    return json.dumps(value,ensure_ascii=False,sort_keys=True,separators=(',',':')).encode()


def apply(root,run,write=False):
    root = root.resolve()
    run = run.resolve()
    knowledge=root/'plugins/ubm-goal-setting/knowledge'
    inventory=run/'independent-tag-insufficiency-inventory.json'
    findings=json.loads(inventory.read_text())['findings']
    originals={row['id']:row for row in json.loads((run/'knowledge-context-draft.json').read_text())['records']}
    schema=json.loads((knowledge/'schema.json').read_text())['knowledge_entry_schema']
    validator=Draft202012Validator(schema,format_checker=FormatChecker())
    documents={}
    before_bytes={}
    records=[]
    for finding in findings:
        path=(root/finding['path']).resolve(strict=True)
        if not path.is_relative_to(knowledge.resolve()) or path.suffix!='.json':
            raise ValueError('tag repair target escapes knowledge directory')
        if path not in documents:
            before_bytes[path]=path.read_bytes();documents[path]=json.loads(before_bytes[path])
        cards=[e for e in documents[path]['entries'] if e['id']==finding['id']]
        if len(cards)!=1:raise ValueError('repair id missing or duplicated')
        card=cards[0]
        if card['tags']!=finding['tags_before']:raise ValueError('tags changed after independent finding')
        preserved={k:v for k,v in card.items() if k!='tags'}
        additions=[];evidence=[]
        for candidate in finding['possible_additions']:
            word=candidate['word']
            if word in card['tags'] or word in additions:continue
            verified=[]
            for item in candidate['grounded_in_existing_card_fields']:
                actual=originals[card['id']]['old_background'] if item['field']=='background' else card.get(item['field'])
                if actual==item['value'] and isinstance(actual,str) and word in actual:
                    verified.append(dict(field=item['field'],value=actual,sha256=sha(actual.encode())))
            if not verified:raise ValueError(f'{card["id"]}: proposed word lacks original field evidence: {word}')
            additions.append(word);evidence.append(dict(word=word,original_field_evidence=verified))
            if len(additions)==3:break
        if not additions:raise ValueError('no verified concrete-word addition')
        old=copy.deepcopy(card['tags']);card['tags'].extend(additions)
        assert {k:v for k,v in card.items() if k!='tags'}==preserved
        records.append(dict(id=card['id'],path=str(path.relative_to(root)),old_tags=old,new_tags=card['tags'],added=additions,evidence=evidence,non_tag_fields_sha256=sha(stable(preserved)),semantic_status='candidate repaired; independent adequacy review required'))
    files=[]
    for path,document in documents.items():
        validator.validate(document)
        old=json.loads(before_bytes[path])
        assert document['entry_count']==old['entry_count'] and len(document['entries'])==len(old['entries'])
        assert [e['id'] for e in document['entries']]==[e['id'] for e in old['entries']]
        output=(json.dumps(document,ensure_ascii=False,indent=2)+'\n').encode()
        files.append(dict(path=str(path.relative_to(root)),before_sha256=sha(before_bytes[path]),after_sha256=sha(output)))
    if write:
        # Preflight all files and proposed additions before the first mutation.
        for path,data in before_bytes.items():
            if path.read_bytes()!=data:raise ValueError('knowledge changed during preflight')
        for path,document in documents.items():path.write_text(json.dumps(document,ensure_ascii=False,indent=2)+'\n')
    result=dict(inventory_sha256=sha(inventory.read_bytes()),applied=write,repaired_entries=len(records),files=files,records=records,all_other_fields_preserved=True,no_semantic_pass_fabricated=True)
    (run/('knowledge-tag-migration.json' if write else 'knowledge-tag-plan.json')).write_text(json.dumps(result,ensure_ascii=False,indent=2)+'\n')
    return dict(applied=write,repaired_entries=len(records),file_count=len(files))


if __name__=='__main__':
    parser=argparse.ArgumentParser();parser.add_argument('--root',type=Path,required=True);parser.add_argument('--run',type=Path,required=True);parser.add_argument('--apply',action='store_true');args=parser.parse_args()
    print(json.dumps(apply(args.root.resolve(),args.run.resolve(),args.apply)))
