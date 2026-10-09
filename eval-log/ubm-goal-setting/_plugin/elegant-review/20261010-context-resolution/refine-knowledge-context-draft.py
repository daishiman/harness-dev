"""Evidence-preserving draft refinement; source cards remain untouched."""
import hashlib,json,re,runpy
from pathlib import Path
P=Path(__file__).parent
# Reuse the audit preimage captured before background mutation, never production source inference.
a=json.loads((P/'knowledge-context-draft.json').read_text())
entries={e['id']:e for f in a['files'] for e in f['before_document']['entries']}
ns=runpy.run_path(str(P/'prepare-knowledge-context-migration.py'))
sentences=ns['sentences'];sha=ns['sha']
privacy=re.compile(r'[0-9０-９]|北原|高山|松本|並木|今岡|小林|吉田|万壽本|平田|伊藤|柿原|石川|福島|UBM|ディアーズ|アカデミー|YouTube|Instagram|Google|美容|税理士|飲食|介護|看護|サロン|焼き菓子|インテリア|管理栄養士|整体|保育|工務店|ハンドメイド|プロテイン|トレーディングカード|医療|旅館|ホテル|n8n|LINE|楽天|Amazon|AIコンサル')
# Each replacement generalizes an existing role/quantity; source values are retained verbatim.
replacements=[('1社長','一人の経営者'),('ナンバー1・2・3全員','各階層の責任者全員'),('ナンバー2（補佐役）','補佐役'),('ナンバー2','補佐役'),('0→1→10→100','事業の各成長段階'),('0→1フェーズ','最初の売上を作る段階'),('0→1前','最初の売上を作る前'),('0→1を達成','最初の売上を達成'),('0→1','最初の売上を作る段階'),('1→10→100','再現性の確立から組織の拡張'),('1→10フェーズ','再現性の確立と組織化の段階'),('1→10','再現性の確立と組織化'),('10→100','組織の拡張'),('1on1','個別面談'),('1対1','個別の関わり'),('1歩目','最初の行動'),('1人','一人'),('1つ','一つ'),('1点','一点'),('1社','特定の事業者'),('2B','法人向け'),('2C','個人向け'),('北原さん','指導者'),('北原氏','指導者'),('Googleマップ','地図サービス'),('YouTube','一般公開の動画'),('Instagram','SNS'),('LINE','連絡手段'),('AIコンサル','技術の導入支援'),('税理士事務所','専門サービス事業'),('美容室','店舗事業'),('訪問美容','訪問型のサービス'),('医療職','専門職'),('保育業界','対人サービスの事業'),('n8n','特定の技術'),('16項目','普遍ルール'),('この16項目','この普遍ルール'),('10年20年','長期'),('10年','長期'),('7〜8年間','長期間'),('6ヶ月以上','一定期間以上'),('6ヶ月等','長期間等'),('3ヶ月・6ヶ月','継続的な期間'),('3ヶ月','一定期間'),('半年','中期'),('1日','一日'),('3階層目','次の組織階層'),('3つの場面','上長・顧客・家庭との関係が崩れる場面'),('3点セット','相互に補完する組み合わせ'),('前段の6段階','お金を得る前の段階'),('5点','各要素'),('5要素','各要素'),('この5項目','この行動群'),('5つとも','各項目とも'),('5層','異なる時間軸'),('6通り','複数の種類'),('4通り','複数の種類'),('そのうち3つ','その多く'),('3層','目的・目標・大義の層'),('5段階','複数の段階')]

replacements.sort(key=lambda pair:len(pair[0]),reverse=True)

def source(k,e,excerpt):return {'field':k,'source_value':e[k],'source_value_sha256':sha(e[k].encode()),'selected_excerpt':excerpt,'exact_excerpt':excerpt in e[k]}
for r in a['records']:
 e=entries[r['id']];parts=r['source_fields'];ck=parts[-1]['field']
 # Remove event-only introductions; use the actual causal paragraph or source-defined application instead.
 if parts[0]['field']=='background' and privacy.search(parts[0]['selected_excerpt']):
  reason=next((k for k in ['root_cause','rationale','why_the_shift_matters','key_factor','insight'] if e.get(k)),None)
  if reason and len(sentences(e[reason]))>=2:
   parts=[source(reason,e,s) for s in sentences(e[reason])[:5]]
  elif e.get('how_to_use'):
   h=sentences(e['how_to_use'])[0];match=re.search(r'(.+?)(?:という相談(?:者)?に対し|という相談に対して)',h)
   if match:h=match.group(1)+'という相談がある。'
   parts=[source('how_to_use',e,h)]+[x for x in parts[1:]]
 text=''.join(x['selected_excerpt'] for x in parts)
 transforms=[]
 for old,new in replacements:
  if old in text:
   text=text.replace(old,new);transforms.append({'from':old,'to':new,'reason':'Generalize identifiable speaker, concrete sample scale/time, or role label while preserving the original structural condition; original value retained in source/audit.'})
 # A declared applicable_when / trigger is frequently a noun phrase, not a sentence.
 for terminal in ['ユーザー。','経営者。']:
  if text.startswith(parts[0]['selected_excerpt'].replace('1人','一人').replace('1つ','一つ')) and parts[0]['selected_excerpt'].endswith(terminal):
   prefix=parts[0]['selected_excerpt'];replacement=prefix[:-1]+'がいる場面である。'
   if prefix in text:text=text.replace(prefix,replacement,1);transforms.append({'from':prefix,'to':replacement,'reason':'Make source-defined application noun phrase a complete situational sentence.'})
 r['new_background']=text;r['source_fields']=parts;r['transformation_notes']=transforms
(P/'knowledge-context-draft-refined.json').write_text(json.dumps(a,ensure_ascii=False,indent=2)+'\n')
bad=[r for r in a['records'] if privacy.search(r['new_background'])]
print('Remaining privacy triage:',len(bad))
for r in bad:print(r['id'],r['new_background'])
