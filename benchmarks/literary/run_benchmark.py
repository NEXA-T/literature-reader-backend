"""Run frozen literary inputs through the actual GigaChatClient."""
import argparse
import asyncio
from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path
import sys
import time

ROOT=Path(__file__).resolve().parents[2]
sys.path.insert(0,str(ROOT))
from app.services.gigachat_client import GigaChatClient, GigaChatError, SYSTEM_PROMPT
from app.services.gigachat_settings import GigaChatSettings

async def main():
 parser=argparse.ArgumentParser()
 parser.add_argument('--env-file',type=Path,required=True)
 parser.add_argument('--output',type=Path,default=ROOT/'benchmarks/literary/results-new.json')
 args=parser.parse_args()
 dataset_path=ROOT/'benchmarks/literary/cases.json'
 dataset=json.loads(dataset_path.read_text(encoding='utf-8'))
 settings=GigaChatSettings.from_env_file(args.env_file)
 settings.model='GigaChat-2-Max'
 report={'started_at_utc':datetime.now(timezone.utc).isoformat(),'model_requested':settings.model,
  'dataset_sha256':hashlib.sha256(dataset_path.read_bytes()).hexdigest(),
  'system_prompt_sha256':hashlib.sha256(SYSTEM_PROMPT.encode()).hexdigest(),
  'temperature':0.1,'max_tokens':1400,'max_attempts':settings.max_attempts,'cases':[]}
 args.output.parent.mkdir(parents=True,exist_ok=True)
 async with GigaChatClient(settings) as client:
  for case in dataset['cases']:
   start=time.perf_counter()
   item={'id':case['id']}
   try:
    result=await client.analyze_text(case['selected_text'],case['context'],case['book_title'])
    item.update({'status':'success','result_type':type(result).__name__,'response':result.model_dump()})
   except GigaChatError as error:
    item.update({'status':'failed','error_type':type(error).__name__,'error':str(error)})
   item['latency_seconds']=round(time.perf_counter()-start,3)
   report['cases'].append(item)
   args.output.write_text(json.dumps(report,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
   print(item['id'],item['status'],item['latency_seconds'],flush=True)
 report['completed_at_utc']=datetime.now(timezone.utc).isoformat()
 args.output.write_text(json.dumps(report,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
 return 0 if all(x['status']=='success' for x in report['cases']) else 1

if __name__=='__main__':
 try: sys.exit(asyncio.run(main()))
 except (OSError,ValueError,GigaChatError): sys.exit('Benchmark failed; no secrets logged.')
