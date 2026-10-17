import hashlib
import json
from pathlib import Path
import uuid

from app.schemas.ai_analysis import AIAnalysis
from benchmarks.literary.generate_scene import image_id
import pytest

DIR=Path(__file__).resolve().parents[1]/'benchmarks/literary'

def load(name): return json.loads((DIR/name).read_text(encoding='utf-8'))

def test_corpus_references_and_selections_are_consistent():
 data=load('cases.json')
 assert len(data['cases'])==15
 assert len({c['id'] for c in data['cases']})==15
 assert len({c['book_title'] for c in data['cases']})==5
 for case in data['cases']:
  assert case['selected_text'] in case['context']
  assert hashlib.sha256(case['context'].encode()).hexdigest()==case['source']['context_sha256']
  assert case['source']['url'].startswith('https://www.gutenberg.org/cache/epub/')

def test_returned_objects_reviews_and_summary_are_consistent():
 data=load('cases.json')
 results=load('results.json')
 grades=load('reviews.json')['cases']
 summary=load('summary.json')
 ids={c['id'] for c in data['cases']}
 assert {c['id'] for c in results['cases']}=={c['id'] for c in grades}==ids
 assert results['dataset_sha256']==hashlib.sha256((DIR/'cases.json').read_bytes()).hexdigest()
 for case in results['cases']:
  assert case['status']=='success'
  assert isinstance(AIAnalysis.model_validate(case['response'],strict=True),AIAnalysis)
 for grade in grades:
  assert all(grade[k] in (0,1,2) for k in ('translation','context','background','image'))
  assert (grade['verdict']=='correct') == (sum(grade[k] for k in ('translation','context','background'))==6)
 assert summary['text_points']==sum(c[k] for c in grades for k in ('translation','context','background'))

def test_image_uses_actual_prompt_and_recorded_file():
 metadata=load('illustration/request-and-result.json')
 results=load('results.json')
 source=next(c for c in results['cases'] if c['id']==metadata['source_case_id'])
 assert metadata['source_image_prompt']==source['response']['image_prompt']
 assert source['response']['image_prompt'] in metadata['request_body']['messages'][1]['content']
 assert metadata['results_sha256']==hashlib.sha256((DIR/'results.json').read_bytes()).hexdigest()
 content=(DIR/'illustration/scene.jpg').read_bytes()
 assert content.startswith(b'\xff\xd8\xff')
 assert hashlib.sha256(content).hexdigest()==metadata['image_sha256']

def test_image_reference_is_uuid_not_arbitrary_remote_url():
 value=str(uuid.uuid4())
 assert image_id(f'<img src="{value}" fuse="true"/>')==value
 for raw in ('<img src="https://attacker.invalid/x"/>','<img src="../secret"/>','no image'):
  with pytest.raises(ValueError): image_id(raw)
