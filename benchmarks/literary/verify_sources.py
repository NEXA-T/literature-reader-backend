"""Verify exact provenance against cached, downloaded source texts; no API calls."""
import hashlib
import json
from pathlib import Path
import sys
sys.path.insert(0,str(Path(__file__).resolve().parents[2]))
from benchmarks.literary.build_dataset import source_paragraphs

DIR=Path(__file__).resolve().parent

def main():
 dataset=json.loads((DIR/'cases.json').read_text(encoding='utf-8'))
 for case in dataset['cases']:
  source=case['source']
  number=source['url'].split('/epub/')[1].split('/')[0]
  raw=(DIR/f'.cache/{number}.txt').read_bytes()
  assert hashlib.sha256(raw).hexdigest()==source['source_sha256'],case['id']+': source changed'
  paras=source_paragraphs(raw.decode('utf-8-sig'))
  start,end=source['paragraph_indices_zero_based']
  assert '\n\n'.join(paras[start:end+1])==case['context'],case['id']+': context mismatch'
  assert case['selected_text'] in case['context'],case['id']+': selection missing'
 print('All 15 contexts exactly match source paragraphs and SHA-256.')

if __name__=='__main__': main()
