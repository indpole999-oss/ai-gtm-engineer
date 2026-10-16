"""Build disposable n8n test copies; never overwrite canonical exports."""
import argparse, copy, json
from pathlib import Path
p=argparse.ArgumentParser();p.add_argument('--output',type=Path,required=True);args=p.parse_args()
root=Path(__file__).resolve().parents[1]
cases=[
 ('crm-invalid-id','05-crm-deduplication','Fixture duplicate leads',{'events':[{'id':' ','stage':'SQL'}]},'invalid lead event'),
 ('calendar-no-timezone','06-calendar-preview','Fixture meeting request',{'account':'Fictional','start':'2026-10-20T14:00:00','minutes':30},'explicit timezone'),
 ('calendar-invalid-duration','06-calendar-preview','Fixture meeting request',{'account':'Fictional','start':'2026-10-20T14:00:00Z','minutes':0},'explicit timezone'),
 ('missing-source','08-gtm-orchestrator','Fixture prospect',{'name':'Fictional','employees':20,'evidence':[{'claim':'unsupported'}]},'evidence requires'),
 ('outreach-bypass','04-outreach-draft-review','Create safe draft',{'sent':True,'approval':'PENDING_REVIEW'},'unsafe state'),
 ('journey-bypass','08-gtm-orchestrator','Create review draft',{'draft':{'sent':False,'approval':'APPROVED'},'trace':[]},'unsafe draft state'),
]
workflows=[];manifest=[]
for i,(name,file,node,data,error) in enumerate(cases,1):
 w=copy.deepcopy(json.loads((root/(file+'.json')).read_text()));w['id']=f'portfolioneg20261016{i:02}';w['name']='[ISOLATED NEGATIVE] '+name
 next(n for n in w['nodes'] if n['name']==node)['parameters']['jsCode']='return [{json:'+json.dumps(data)+'}];'
 workflows.append(w);manifest.append({'id':w['id'],'case':name,'expectedError':error})
args.output.mkdir(parents=True,exist_ok=False)
(args.output/'workflows.json').write_text(json.dumps(workflows,ensure_ascii=False,indent=2))
(args.output/'manifest.json').write_text(json.dumps(manifest,indent=2))
print('Built',len(workflows),'inactive test copies in',args.output)
