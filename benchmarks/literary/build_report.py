"""Render reproducible Markdown tables from model responses and explicit review."""
from collections import Counter
from datetime import datetime
import hashlib
import json
from pathlib import Path
import statistics

DIR=Path(__file__).resolve().parent

def load(name): return json.loads((DIR/name).read_text(encoding='utf-8'))

def main():
 dataset=load('cases.json')
 results=load('results.json')
 reviews=load('reviews.json')
 assert hashlib.sha256((DIR/'cases.json').read_bytes()).hexdigest()==results['dataset_sha256']
 outputs={c['id']:c for c in results['cases']}
 grades={c['id']:c for c in reviews['cases']}
 assert set(outputs)==set(grades)=={c['id'] for c in dataset['cases']}
 verdicts=Counter(c['verdict'] for c in reviews['cases'])
 total=sum(c[k] for c in reviews['cases'] for k in ('translation','context','background'))
 valid=sum(c['status']=='success' for c in results['cases'])
 nulls=sum(c.get('response',{}).get('slang_or_etymology') is None for c in results['cases'])
 lines=['# Бенчмарк литературного анализа — задача №26','',
  f"Реальный API-прогон: {results['started_at_utc']}. Модель: **{results['model_requested']}**; вызов через `GigaChatClient.analyze_text`, без изменений промпта и клиента в ходе бенчмарка.",'',
  f"**Валидная структура: {valid}/15. Полностью корректный текст по нашей рубрике: {verdicts['correct']}/15 ({verdicts['correct']/15:.1%}); частично: {verdicts['partial']}; неверный основной смысл: {verdicts['incorrect']}. Баллы текста: {total}/90 ({total/90:.1%}).** Это описательная оценка одного небольшого набора, не статистическая точность модели на всей литературе.",'',
  f"Медианное время метода: {statistics.median(c['latency_seconds'] for c in results['cases']):.3f} с. Включает OAuth при первом запросе и возможные внутренние повторы клиента; число таких повторов отдельно не измерялось.",'',
  '## Набор и методика','',
  '15 сложных отрывков из 5 реальных книг, 4 авторов. Только английский оригинал XIX века: другие языки и современная литература не охвачены. Набор специально сложный, не случайная репрезентативная выборка. Цитаты сверены с Project Gutenberg; chapter, абзацы и SHA-256 сохранены в cases.json. Полные книги находятся только в игнорируемом .cache. Их полные лицензии/заголовки не подменяются нашей разметкой.','',
  'Ожидаемые трактовки и корпус зафиксированы до API-запросов; они не передавались модели. Это новый набор относительно калибровочных синтетических примеров задачи №10, но оценка проведена тем же ассистентом, который подготовил задания. Нет независимых экспертов, слепой разметки и измерения согласия оценщиков.','',
  'Каждый результат оценён отдельно от валидности JSON. Баллы 0–2: перевод, привязка к контексту, дополнительный смысл/достоверность. Максимум 6 за текст; отдельная оценка image_prompt 0–2 в сумму текста не входит. correct означает 6/6; partial — основной смысл понят, но есть существенная потеря нюанса; incorrect — неверна центральная трактовка. Критерии и конкретные замечания записаны в reviews.json. Поле slang_or_etymology может быть null, если необходимый каламбур уже объяснён в context_meaning.','',
  '## Таблица 15 тестов','',
  '| № | Книга / место | Выделение | Тип сложности | Перевод | Контекст | Доп. смысл | Текст /6 | image /2 | Вердикт |',
  '|---|---|---|---|---:|---:|---:|---:|---:|---|']
 for i,c in enumerate(dataset['cases'],1):
  g=grades[c['id']]
  score=sum(g[k] for k in ('translation','context','background'))
  lines.append(f"| {i} | [{c['book_title']}]({c['source']['reading_url']}) — {c['source']['chapter']} | {c['selected_text']} | {c['category']} | {g['translation']} | {g['context']} | {g['background']} | {score} | {g['image']} | {g['verdict']} |")
 lines += ['', '## Что выявлено','',
  'Клиент надёжно отфильтровал формат в этом прогоне, но правильная Pydantic-модель не гарантирует верный смысл. Наиболее серьёзные ошибки — by hand (искусственное вскармливание/тяжёлая рука) и Bolted (заглатывание еды вместо побега). Пародия sense/sounds не распознана, каламбур gravy/grave раскрыт не полностью.','',
  f'Во всех {nulls}/15 ответах slang_or_etymology=null. Это валидно по схеме, но модель избегает отдельного культурного/этимологического объяснения даже там, где оно полезно. Изображения также требуют смысловой проверки: дверь с гвоздём вместо смысла идиомы, золотые монеты вместо серебряных, придуманная сцена с хватанием за волосы.','',
  'Рекомендуемый следующий шаг — отдельно доработать промпт для полисемии и игры слов, а затем повторить этот набор и новый независимый набор. В рамках №26 модельные ответы не исправлялись, промпт не подгонялся под оценку.']
 for c in dataset['cases']:
  r=outputs[c['id']]
  lines += ['',f"## {c['id']}",'',f"**Источник:** {c['author']}, *{c['book_title']}*, {c['source']['chapter']}; [полный текст]({c['source']['url']}).",'',
   f"**Выделение:** {c['selected_text']}",'','**Реальный контекст:**','',*['> '+p for p in c['context'].split('\n\n')],'',
   '**Ожидаемый смысл (до запуска):** '+c['expected_meaning'],'','**Ответ GigaChat:**','','```json',json.dumps(r.get('response',r),ensure_ascii=False,indent=2),'```','',
   '**Оценка:** '+grades[c['id']]['note']]
  if c['reference_notes']:
   lines += ['', '**Дополнительная проверка трактовки:** '+', '.join(c['reference_notes'])]
 lines += ['', '## PoC генерации иллюстрации','',
  'Скрипт generate_scene.py берёт image_prompt из фактического результата бенчмарка и отправляет отдельный запрос GigaChat с function_call=auto. Затем извлекает UUID из тега img и скачивает JPG через GET /files/{file_id}/content. Это встроенный text2image GigaChat, а не локальная заглушка и не другая модель, выданная за Kandinsky.','',
  'Параметры и фактический ответ: [illustration/request-and-result.json](illustration/request-and-result.json). Иллюстрация: [illustration/scene.jpg](illustration/scene.jpg). Seed, шаги диффузии и размер запроса через этот PoC не задаются; их значения нельзя выдумывать.','',
  '![Тестовая иллюстрация Алисы и Мыши, полученная через GigaChat text2image](illustration/scene.jpg)','',
  'Визуально проверено: персонажи узнаваемы, но добавлены интерьер и стопка книг, которых нет в цитате; пушистый хвост похож на беличий. Это работоспособный PoC цепочки, не гарантия точной иллюстрации оригинальной главы.','',
  'Документация: https://developers.sber.ru/docs/ru/gigachat/guides/images-generation','']
 (DIR/'report.md').write_text('\n'.join(lines),encoding='utf-8')
 summary={'valid_structure':valid,'cases':15,'verdicts':dict(verdicts),'text_points':total,'max_text_points':90,
  'median_latency_seconds':statistics.median(c['latency_seconds'] for c in results['cases']),
  'reviewer':reviews['reviewer'],'scope':dataset['scope']}
 (DIR/'summary.json').write_text(json.dumps(summary,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
 print(json.dumps(summary,ensure_ascii=False))

if __name__=='__main__': main()
