"""Build pre-registered cases from exact, verified Gutenberg paragraphs."""
from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path
import re

ROOT=Path(__file__).resolve().parents[2]
DIR=Path(__file__).resolve().parent
BOOKS={
 11:("Alice’s Adventures in Wonderland","Lewis Carroll"),
 1342:("Pride and Prejudice","Jane Austen"),
 46:("A Christmas Carol","Charles Dickens"),
 120:("Treasure Island","Robert Louis Stevenson"),
 1400:("Great Expectations","Charles Dickens")}

# Expected meanings are fixed before requests to GigaChat, never sent to it.
SPECS=[
 ("01_tale_tail",11,105,106,"long tail","Chapter III","wordplay",
  "Алиса слышит tale (рассказ) как tail (хвост). Ответ должен сохранить буквальный хвост и объяснить омофонию, а не только длину истории."),
 ("02_murdering_time",11,380,384,"murdering the time","Chapter VII","wordplay_metaphor",
  "Двойной смысл: плохое исполнение/нарушение музыкального времени и олицетворённое Время, обиженное Шляпником. Из-за этого часы стоят на шести. Не реальное убийство человека."),
 ("03_sense_sounds",11,513,515,"Take care of the sense, and the sounds will take care of themselves.","Chapter IX","proverb_parody",
  "Пародия на Take care of the pence, and the pounds will take care of themselves; подмена pence/pounds на sense/sounds и навязчивый поиск морали Герцогиней. Не обычный совет о голосе."),
 ("04_consequence",1342,243,244,"give consequence","Chapter III","historical_idiom",
  "Дарси не хочет оказывать вниманием общественную значимость девушкам, которыми пренебрегают другие. consequence здесь значимость/статус, не последствия или наказание."),
 ("05_entail",1342,362,362,"entailed","Chapter VII","historical_term",
  "Имущественное ограничение наследования: при отсутствии сыновей поместье переходит дальнему родственнику; дочери лишаются этого наследства. Не просто залог или необходимость."),
 ("06_fine_eyes",1342,426,430,"fine eyes","Chapter VIII","irony_subtext",
  "Каролина Бингли пытается высмеять привлекательность Элизабет после её прихода; Дарси возражает, что глаза стали ярче от движения. Красивые/выразительные глаза, не хорошее зрение; подкол и интерес Дарси."),
 ("07_door_nail",46,19,20,"dead as a door-nail","Stave I","idiom",
  "Совершенно мёртв: повествователь настаивает на смерти Марли, чтобы последующее появление призрака было значимым; шутит о буквальном гвозде. Не описание самого гвоздя как умершего."),
 ("08_gravy_grave",46,133,134,"more of gravy than of grave","Stave I","wordplay",
  "Созвучие gravy (подливка) и grave (могила): Скрудж объясняет призрака несварением и шутит, подавляя страх. Не призрак, буквально состоящий из соуса."),
 ("09_humbug",46,30,34,"Humbug","Stave I","historical_colloquialism",
  "Скрудж презрительно называет рождественские поздравления чепухой/обманом/вздором; это скептическое отвержение праздника, не жук, не имя человека."),
 ("10_black_spot",120,153,153,"black spot","Chapter III","cultural_term",
  "Пиратская чёрная метка: почерневший кружок бумаги с ультиматумом до десяти; знак угрозы/приговора. Не болезнь или просто грязное пятно. Не выдавать литературный обычай за доказанную общую историю пиратов."),
 ("11_pieces_eight",120,164,164,"pieces of eight","Chapter IV","historical_term",
  "Испанские серебряные монеты достоинством восемь реалов среди разных валют в сундуке; не восемь случайных кусочков и не обязательно золотые монеты."),
 ("12_dead_men",120,1074,1074,"dead men don’t bite","Chapter XXVI","violent_idiom",
  "Мёртвые не могут отомстить/помешать: Хэндс оправдывает упреждающее насилие, предпочитает ударить первым; не совет о животных или просто очевидный биологический факт."),
 ("13_by_hand",1400,64,64,"by hand","Chapter II","wordplay_historical",
  "Базовое старое значение — вскармливание младенца без матери/кормилицы; детский Пип связывает выражение с тяжёлой рукой сестры и побоями. Нужны оба слоя, не только строгая дисциплина."),
 ("14_bolted",1400,98,101,"I Bolted","Chapter II","polysemy_colloquialism",
  "Джо говорит о быстром заглатывании пищи, не о побеге или запирании двери; сравнивает Пипа с собой ребёнком, боится, что тот подавится. Контекст еды и кусок за щекой важны."),
 ("15_common_boy",1400,465,468,"common labouring-boy","Chapter VIII","class_subtext",
  "Эстелла презрительно называет Пипа простым мальчиком из рабочего сословия; common — низкое социальное положение в её оценке, а не общий/обычный трудящийся без подтекста. Контраст богатого дома и презрения к происхождению.")]

def source_paragraphs(text):
 return [re.sub(r"\s+"," ",p).strip() for p in re.split(r"\n\s*\n",text)]

def main():
 cases=[]
 for cid,number,start,end,selection,chapter,category,expected in SPECS:
  raw=(DIR/f'.cache/{number}.txt').read_bytes()
  paras=source_paragraphs(raw.decode('utf-8-sig'))
  context='\n\n'.join(paras[start:end+1])
  assert selection in context,(cid,selection)
  title,author=BOOKS[number]
  cases.append({"id":cid,"selected_text":selection,"context":context,"book_title":title,
   "author":author,"category":category,"expected_meaning":expected,
   "source":{"url":f'https://www.gutenberg.org/cache/epub/{number}/pg{number}.txt',
             "reading_url":f'https://www.gutenberg.org/ebooks/{number}',"chapter":chapter,
             "paragraph_indices_zero_based":[start,end],"source_sha256":hashlib.sha256(raw).hexdigest(),
             "context_sha256":hashlib.sha256(context.encode()).hexdigest()},
   "reference_notes":[]})
 for c in cases:
  if c['id']=='03_sense_sounds':
   c['reference_notes']=['https://tile.loc.gov/storage-services/public/gdcmassbookdig/alicesadventures00carr_10/alicesadventures00carr_10.pdf']
  if c['id']=='05_entail':
   c['reference_notes']=['https://www.jasna.org/publications-2/persuasions-online/volume-44-no-1/hall/']
  if c['id']=='13_by_hand':
   c['reference_notes']=['https://www.ncgsjournal.com/issue41/antonio.html','https://academic.oup.com/cornell-scholarship-online/book/56639/chapter-abstract/453306062']
 data={'version':'1.0','frozen_at_utc':datetime.now(timezone.utc).isoformat(),
  'normalization':'Only paragraph-internal whitespace collapsed to one space; original punctuation and Gutenberg underscore emphasis preserved. Adjacent complete paragraphs joined by two newlines. No invented bridge text.',
  'scope':'15 English-language public-domain excerpts, 5 books, 4 authors; not multilingual or independent human-reviewed gold standard.',
  'cases':cases}
 (DIR/'cases.json').write_text(json.dumps(data,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
 print('Froze 15 cases with verified exact source paragraphs and expectations before model calls.')

if __name__=='__main__': main()
