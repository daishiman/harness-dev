#!/usr/bin/env python3
"""Correct independently identified background defects; preserve original evidence."""
import copy,hashlib,json
from pathlib import Path
from jsonschema import Draft202012Validator,FormatChecker
ROOT=Path(__file__).resolve().parents[5];RUN=Path(__file__).resolve().parent;KB=ROOT/'plugins/ubm-goal-setting/knowledge'
sha=lambda b:hashlib.sha256(b).hexdigest()
stable=lambda v:json.dumps(v,ensure_ascii=False,sort_keys=True,separators=(',',':')).encode()
drafts={e['id']:e for e in json.loads((RUN/'knowledge-context-draft.json').read_text())['records']}
validator=Draft202012Validator(json.loads((KB/'schema.json').read_text())['knowledge_entry_schema'],format_checker=FormatChecker())
explicit={
'PR-358':('技術職から独立した経営者が、技術そのものを自分の価値と捉えている場面である。経営者の役割は技術の提供自体ではなく、地域の困りごとを解決するために技術を使うことにある。この認識がないと技術を提供する現場から出ず、地域の困りごとに目を向けられなくなる。',['content','background']),
'AG-189':('傷つくことを避けて関わりを浅くしてしまう場面である。傷つかないために関わりを減らす対応と、耐性を獲得して自分を上げる対応には違いがある。助言は関わりを減らすことではなく、耐性を獲得して失わない基準値まで自分を上げることを周りへの優しさとして位置づけている。',['not_recommended','recommended','intent','rationale']),
'AG-196':('指導が施策の話に終始してしまう場面である。周りに誰がいて何があり、どうなりたいのかを可視化しないまま施策や数値目標から入ると、指導の起点となる人の配置が捉えられない。人間相関図を出させるのは、この前提を明らかにして本質的なイノベーションにつなげるためである。',['recommended','not_recommended','intent','rationale']),
'AG-204':('目的が日々の行動から切り離されている場面である。目的を年に数回だけ確認する対応では、目的への接触が日次にならず、毎日の前進に必要な目的意識を持ち続けるための習慣が欠ける。毎日目的意識に触れることが、日々の前進を起こすための条件になる。',['not_recommended','recommended','intent','rationale']),
'MS-125':('新規が入らず紹介も出ないときに、赤字を埋めるために新規顧客を取ろうとしている場面である。赤字を埋めることだけを目的にすると、自分の欠損を埋めることに閉じてしまい、相手から見て応じる理由がない。人が集まる生き方をして富を分配するために経営するという考え方では、目的が相手の側にあり、働きかけが相手にとって意味を持つ。',['trigger','before','after','why_the_shift_matters']),
'MS-130':('成果が出ない時期が続いたり、周囲と比べて遅れていると感じたりして、豊かさが環境や運で決まると考えている場面である。うまくいかない理由を外側に置くと、打ち手が自分の側に戻ってこない。毎日の前進を意識しているかどうかへ目を向けると、今日から自分で動かせるものが明確になる。',['trigger','before','after','why_the_shift_matters']),
'MS-133':('同業の店舗数が増え、技術だけでは差がつかなくなった場面である。自分の価値を技術の精度だけに置く考え方から、町の困りごとを解決するために技術を使う考え方への転換が必要になる。この転換がないと技術を提供する現場から出られず、技術が失われたときに事業ごと回らなくなる。',['trigger','before','after','why_the_shift_matters']),
}
replacements={
'PA-010':[('延べで数十人規模の顧客','既存顧客'),('過去に接した数十人','過去に接した顧客')],
'AG-052':[('往復の交通費が数百円で','移動費を抑えながら')],
'AG-131':[('一人数千円の会','費用のかかる会食')],
'AG-212':[('確立していないと','自分の志が確立していないと')],
'MS-004':[('行動量が半減する','行動量が減る')],
}
ids=set(explicit)|set(replacements)|{'CP-094'};docs={};records=[]
for p in KB.glob('*.json'):
 d=json.loads(p.read_text());matches=[e for e in d.get('entries',[]) if e['id'] in ids]
 if not matches:continue
 before_bytes=p.read_bytes()
 for card in matches:
  old=copy.deepcopy(card);identifier=card['id'];source_fields=[]
  if identifier in explicit:
   card['background'],source_fields=explicit[identifier]
  elif identifier=='CP-094':
   sentence='相手の意欲不足として片づけると、こちらの改善点が見えなくなる。'
   assert sentence==drafts[identifier]['old_background']
   card['background']+=sentence;source_fields=['background','problem','advice','key_insight']
  else:
   for original,replacement in replacements[identifier]:
    assert original in card['background'];card['background']=card['background'].replace(original,replacement)
   source_fields=['background']
  assert {k:v for k,v in old.items() if k!='background'}=={k:v for k,v in card.items() if k!='background'}
  evidence=[]
  for field in source_fields:
   value=drafts[identifier]['old_background'] if field=='background' else old[field]
   evidence.append({'field':field,'original_value':value,'sha256':sha(stable(value))})
  records.append({'id':identifier,'path':str(p.relative_to(ROOT)),'before_card':old,'before_background':old['background'],'after_background':card['background'],'before_card_sha256':sha(stable(old)),'after_card_sha256':sha(stable(card)),'non_background_sha256':sha(stable({k:v for k,v in old.items() if k!='background'})),'source_fields':evidence,'semantic_status':'requires independent re-review'})
 validator.validate(d);docs[p]=(before_bytes,(json.dumps(d,ensure_ascii=False,indent=2)+'\n').encode())
assert {e['id'] for e in records}==ids and len(records)==13
for p,(b,a) in docs.items():assert p.read_bytes()==b
for p,(b,a) in docs.items():p.write_bytes(a)
(RUN/'knowledge-context-refinement.json').write_text(json.dumps({'reason':'Independent full-982 review found 12 background semantic/privacy defects plus one concrete-ratio privacy issue; preserve all original fields and provenance while making structural applicability explicit.','records':records,'files':[{'path':str(p.relative_to(ROOT)),'before_sha256':sha(b),'after_sha256':sha(a)} for p,(b,a) in docs.items()],'schema_pass':True,'all_non_background_fields_preserved':True,'semantic_recheck_required':True},ensure_ascii=False,indent=2)+'\n')
print(json.dumps({'repaired_backgrounds':len(records),'files':len(docs),'schema':'PASS','independent_semantic_review':'PENDING'}))
