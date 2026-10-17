"""Optional GigaChat built-in text2image PoC using actual benchmark image_prompt."""
import argparse
import asyncio
import base64
from datetime import datetime, timezone
import hashlib
from html.parser import HTMLParser
import json
from pathlib import Path
import ssl
import sys
import time
import uuid

import httpx

ROOT=Path(__file__).resolve().parents[2]
sys.path.insert(0,str(ROOT))
from app.services.gigachat_settings import GigaChatSettings

class ImageReference(HTMLParser):
 def __init__(self):
  super().__init__()
  self.ids=[]
 def handle_starttag(self,tag,attrs):
  if tag.lower()=='img':
   value=dict(attrs).get('src','')
   try:
    parsed=uuid.UUID(value)
    if parsed.version==4: self.ids.append(str(parsed))
   except ValueError: pass

def image_id(content):
 parser=ImageReference()
 parser.feed(content)
 if not parser.ids: raise ValueError('Generation response contains no image UUID')
 return parser.ids[0]

async def main():
 parser=argparse.ArgumentParser()
 parser.add_argument('--env-file',type=Path,required=True)
 parser.add_argument('--case-id',default='01_tale_tail')
 parser.add_argument('--results',type=Path,default=ROOT/'benchmarks/literary/results.json')
 parser.add_argument('--output-dir',type=Path,default=ROOT/'benchmarks/literary/illustration')
 args=parser.parse_args()
 results=json.loads(args.results.read_text(encoding='utf-8'))
 case=next((c for c in results['cases'] if c['id']==args.case_id),None)
 if case is None: raise ValueError('Unknown case ID')
 prompt=case['response']['image_prompt']
 if not isinstance(prompt,str) or not prompt.strip(): raise ValueError('Selected result has no image_prompt')
 settings=GigaChatSettings.from_env_file(args.env_file)
 settings.model='GigaChat-2-Max'
 key=settings.auth_key.get_secret_value().strip() if settings.auth_key else ''
 if not key and settings.client_id and settings.client_secret:
  key=base64.b64encode(f'{settings.client_id}:{settings.client_secret.get_secret_value()}'.encode()).decode()
 if not key: raise ValueError('Authorization key missing')
 tls=ssl.create_default_context()
 if settings.ca_bundle: tls.load_verify_locations(cafile=str(settings.ca_bundle))
 payload={'model':settings.model,'messages':[
  {'role':'system','content':'Создай одну иллюстрацию литературной сцены по описанию пользователя. Без надписей и водяных знаков. Используй встроенную генерацию изображений.'},
  {'role':'user','content':'Нарисуй иллюстрацию сцены по следующему описанию на английском:\n'+prompt}],
  'function_call':'auto'}
 record={'timestamp_utc':datetime.now(timezone.utc).isoformat(),'provider':'GigaChat built-in text2image',
  'source_case_id':args.case_id,'source_image_prompt':prompt,
  'results_sha256':hashlib.sha256(args.results.read_bytes()).hexdigest(),
  'request_body':payload,'timeout_seconds':180,
  'parameters_not_exposed':['seed','width','height','diffusion_steps'],
  'documentation':'https://developers.sber.ru/docs/ru/gigachat/guides/images-generation'}
 args.output_dir.mkdir(parents=True,exist_ok=True)
 metadata=args.output_dir/'request-and-result.json'
 start=time.perf_counter()
 try:
  async with httpx.AsyncClient(verify=tls,timeout=180,follow_redirects=False) as client:
   auth=await client.post(settings.auth_url,headers={'Authorization':'Basic '+key,'RqUID':str(uuid.uuid4())},data={'scope':settings.scope})
   auth.raise_for_status()
   token=auth.json()['access_token']
   headers={'Authorization':'Bearer '+token}
   response=await client.post(settings.chat_url,headers=headers,json=payload)
   response.raise_for_status()
   result=response.json()
   choice=result['choices'][0]
   content=choice['message']['content']
   file_id=image_id(content)
   base=settings.chat_url.removesuffix('/chat/completions')
   image=await client.get(f'{base}/files/{file_id}/content',headers={**headers,'Accept':'image/jpeg'})
   image.raise_for_status()
   # Prevent writing an error document as a purported illustration.
   if not image.content.startswith(b'\xff\xd8\xff'): raise ValueError('Download is not a JPEG image')
   destination=args.output_dir/'scene.jpg'
   destination.write_bytes(image.content)
   record.update({'status':'success','model_returned':result.get('model'),
    'generation_response':content,'finish_reason':choice.get('finish_reason'),
    'usage':result.get('usage'),'file_id':file_id,'download_method':'GET',
    'image_file':destination.name,'image_bytes':len(image.content),
    'image_sha256':hashlib.sha256(image.content).hexdigest()})
 except (httpx.HTTPError,ValueError,KeyError,IndexError,TypeError) as error:
  record.update({'status':'failed','error_type':type(error).__name__})
  # HTTP exception strings may expose request information; never serialize them.
  if isinstance(error,httpx.HTTPStatusError): record['http_status']=error.response.status_code
  raise
 finally:
  record['elapsed_seconds']=round(time.perf_counter()-start,3)
  metadata.write_text(json.dumps(record,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
 print(f"Saved {destination.name}; {record['image_bytes']} bytes; metadata: {metadata.name}")

if __name__=='__main__':
 try: asyncio.run(main())
 except (httpx.HTTPError,OSError,ValueError,KeyError,IndexError,TypeError,StopIteration):
  sys.exit('Image PoC failed; inspect safe metadata, no credentials logged.')
