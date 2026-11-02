"""Build a transparent gallery; never count placeholders as generated art."""
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
DIR = ROOT / "docs/demo-assets"


def main():
    scenes = json.loads((DIR / "scenes.json").read_text(encoding="utf-8"))
    log = json.loads((DIR / "generation-log.json").read_text(encoding="utf-8"))
    by_id = {case["id"]: case for case in log["cases"]}
    assert log.get("generated_count") == 5
    lines = ["# Пять книжных иллюстраций — задача №40", "",
             "Все пять финальных изображений реально получены через GigaChat text2image. "
             "Они подготовлены офлайн с отдельным ожиданием до 90 секунд. Рабочий "
             "ImageGenerationClient по-прежнему ограничен 15 секундами и при задержке возвращает заглушку.", "",
             "[Интерактивные попытки с таймаутами](interactive-timeout-log.json) · "
             "[Финальные параметры/время](generation-log.json) · "
             "[Исходники и калибровка](scenes.json) · "
             "[Первые реальные варианты](calibration-before/generation-log.json)", "",
             "## Сводка", "",
             "| Книга | Исходная идиома | Файл | Время офлайн, с |",
             "|---|---|---|---:|"]
    for scene in scenes:
        case = by_id[scene["id"]]
        assert not case["is_fallback"]
        lines.append(f"| {scene['book_title']} | {scene['selected_text']} | [{case['image_file']}]({case['image_file']}) | {case['attempts'][-1]['elapsed_seconds']} |")
    lines += ["", "## Что калибровалось", "",
              "Сохранены три уровня: исходная идиома/контекст, прежний image_prompt из "
              "бенчмарка и вручную уточнённая сцена. Добавлены единый живописный "
              "книжный стиль и запрет текста. В первом прогоне замечены потеря "
              "Алисы, псевдозаписи в конторской книге, слишком приветливый Скрудж "
              "и взрослые персонажи вместо детей. Для повторной генерации явно "
              "заданы персонажи, пустые поверхности и закрытые/перевёрнутые карты.", "",
              "Изменения не маскируют запрещённое содержание: показаны безопасные "
              "литературные ассоциации без натуралистических деталей. Отказы "
              "провайдера не обходятся. Стилизация не гарантирует точную "
              "историческую реконструкцию или отсутствие любых мелких артефактов."]
    for scene in scenes:
        case = by_id[scene["id"]]
        lines += ["", f"## {scene['selected_text']} — {scene['book_title']}", "",
                  f"[Оригинал, {scene['source']['chapter']}]({scene['source']['reading_url']})", "",
                  "**Прежний prompt бенчмарка:** " + scene["benchmark_image_prompt"], "",
                  "**Откалиброванная сцена:** " + scene["calibrated_scene"], "",
                  "**Фактический запрос со стилем:** " + case["attempts"][-1]["effective_prompt"], "",
                  f"![{scene['id']}]({case['image_file']})"]
        if (DIR / "visual-review.json").exists():
            review = json.loads((DIR / "visual-review.json").read_text(encoding="utf-8"))
            notes = {item["id"]: item for item in review["cases"]}
            if scene["id"] in notes:
                lines += ["", "**Визуальная проверка ассистентом:** " + notes[scene["id"]]["note"]]
    (DIR / "README.md").write_text("\n".join(lines) + "\n", encoding="utf-8")
    print("Built gallery from five actual generated assets; offline timing explicitly labelled.")


if __name__ == "__main__":
    main()
