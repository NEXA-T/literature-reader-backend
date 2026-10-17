"""Download source text for provenance checks; full books remain untracked."""
import hashlib
import json
from pathlib import Path
import re
import sys
import urllib.request

root=Path(sys.argv[1]) if len(sys.argv)>1 else Path(__file__).resolve().parents[2]
cache=root/'benchmarks/literary/.cache'
cache.mkdir(parents=True,exist_ok=True)
books=[(11,'Alice','tale|tail|murdering the time|take care of the sense'),
       (1342,'Pride','give consequence|entail|fine eyes'),
       (46,'Carol','door-nail|gravy|humbug'),
       (120,'Treasure','black spot|dead men|pieces of eight'),
       (1400,'Expectations','by hand|common|bolter')]
for number,title,pattern in books:
 url=f'https://www.gutenberg.org/cache/epub/{number}/pg{number}.txt'
 path=cache/f'{number}.txt'
 if not path.exists():
  req=urllib.request.Request(url,headers={'User-Agent':'LiteraryBenchmark/1.0'})
  with urllib.request.urlopen(req,timeout=60) as response:
   path.write_bytes(response.read())
 text=path.read_text(encoding='utf-8-sig')
 metadata={'url':url,'sha256':hashlib.sha256(path.read_bytes()).hexdigest()}
 (cache/f'{number}.json').write_text(json.dumps(metadata,indent=2),encoding='utf-8')
 print('\nBOOK',number,title)
 paragraphs=[re.sub(r'\s+',' ',p).strip() for p in re.split(r'\n\s*\n',text)]
 shown=0
 for i,p in enumerate(paragraphs):
  if re.search(pattern,p,re.IGNORECASE):
   print('PARAGRAPH',i,p[:1800])
   shown+=1
   if shown>=14: break
