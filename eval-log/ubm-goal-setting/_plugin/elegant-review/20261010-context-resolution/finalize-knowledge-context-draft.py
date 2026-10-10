"""Attach curated source-grounded summaries and real raw-source receipts to an audit draft."""
import json,hashlib,re
from pathlib import Path
P=Path(__file__).parent;ROOT=P.parents[4];KB=ROOT/'plugins/ubm-goal-setting/knowledge'
a=json.loads((P/'knowledge-context-draft-refined.json').read_text());es={e['id']:e for f in a['files'] for e in f['before_document']['entries']};over=json.loads((P/'knowledge-context-curated-overrides.json').read_text())
sha=lambda v:hashlib.sha256(v.encode()).hexdigest()
for r in a['records']:
 if r['id'] in over:
  o=over[r['id']];e=es[r['id']];r['new_background']=o['background'];r['source_fields']=[{'field':k,'source_value':e[k],'source_value_sha256':sha(e[k]),'selected_excerpt':e[k],'exact_excerpt':True} for k in o['fields']];r['transformation_notes']=[{'reason':'Individually curated faithful structural summary of these exact original fields; remove identifying particulars and sample numeric facts while preserving applicable conditions and explanation. Original full background and all source field values are preserved.'}]
raw=KB/'sources/アカデミー/2026-09-09 - アカデミー勉強会（地域戦略・大義・QPMI・普遍16項目）.md';lines=raw.read_text().splitlines();rawsha=hashlib.sha256(raw.read_bytes()).hexdigest()
new={
 'PR-342':('売上を作ろうとして、サービスの説明から入ってしまう。相手の困りごとを引き受け、時間や食事を通じて関わることが信頼の入口になるため、知識・技術・サービスは販売の説明だけでなく関係を作るきっかけとして使う必要がある。',[(46,50,'地域戦略（data） / 信頼関係を生み出す機能が会社に入っているか'),(64,70,'地域戦略（data） / 川下の困りごとを買ってでも関わる')]),
 'PR-386':('管理手法や制度の整備だけでは人が動かない。本人が直接否定するとチームの関係を壊してしまう会議では、反対意見を出せる雰囲気と発言者の配置を作る必要がある。人を動かす力は相手を幸せにも不幸にもするため、利他的に使い、相手の意図を理解して働きかけることが制約になる。',[(358,374,'人を操る（data） / マネジメントに絶対的に必要なのは人を操る能力 / ダークスキルとは人を操る力 / 言えないことは、言える人を操って言わせる'),(386,390,'人を操る（data） / コミュニケーションとは人を動かすこと')]),
 'PR-390':('マネジメントの対象が下方向に限定されている。上司に仕えることだけを優先すると川下の人材が成長しなくなる。下の人間を動かして成果を上司へ届ける集団ができれば、上司もその集団を率いる人の発言を丁寧に扱う必要が生まれる。',[(376,384,'人を操る（data） / マネジメントは部下ではなく上司にするもの')])}
for r in a['records']:
 if r['id'] in new:
  text,ranges=new[r['id']];r['new_background']=text;e=es[r['id']];r['source_fields']=[{'field':k,'source_value':e[k],'source_value_sha256':sha(e[k]),'selected_excerpt':e[k],'exact_excerpt':True} for k in ['background','content','intent']]
  r['raw_source_evidence']=[{'path':str(raw.relative_to(ROOT)),'file_sha256':rawsha,'source_identity':'Exact basename/date matches source.file; registry records original dated-folder path. This is the normalized local source copy, not an invented new provenance.','section':section,'line_start':start,'line_end':end,'quote':'\n'.join(lines[start-1:end]),'quote_sha256':sha('\n'.join(lines[start-1:end])),'actually_read':True} for start,end,section in ranges]
  r['transformation_notes']=[{'reason':'The original card alone lacked sufficient concrete explanation. Source-directed read-only lookup located the matching normalized original source and these exact sections were read. Background now summarizes the specific mechanism/constraint; source and every non-background card field remain unchanged.'}]
a['claim']='User-authorized post-review supplemental background repair. All982 audit records and original file/card preimages; no new review iterations or bulk semantic PASS manufactured. Independent all-card L1 assessment still required.'
(P/'knowledge-context-final-draft.json').write_text(json.dumps(a,ensure_ascii=False,indent=2)+'\n')
privacy=re.compile(r'[0-9０-９]|北原|高山|松本|並木|今岡|小林|吉田|万壽本|平田|伊藤|柿原|石川|福島|UBM|ディアーズ|アカデミー|YouTube|Instagram|Google|美容|税理士|飲食|介護|看護|サロン|焼き菓子|インテリア|管理栄養士|整体|保育|工務店|ハンドメイド|プロテイン|トレーディングカード|医療|旅館|ホテル|n8n|LINE|楽天|Amazon|AIコンサル')
bad=[r for r in a['records'] if privacy.search(r['new_background'])];print('Residual privacy triage',len(bad))
for r in bad:print(r['id'],r['new_background'])
for r in a['records']:
 if re.search(r'[一-龥]{2,5}(?:さん|氏)|スターバックス|サイバーエージェント|東京|大阪|北海道|福岡|仙台|愛知|岡山|山梨|Dears|DEARS',r['new_background']):print('NAME/PLACE CHECK',r['id'],r['new_background'])
