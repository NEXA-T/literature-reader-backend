"""Compare uncached GigaChat image generations against the same literary scenes."""
import argparse
import asyncio
import json
from pathlib import Path
from time import perf_counter

from app.services.gigachat_settings import GigaChatSettings
from app.services.image_generation_client import ImageGenerationClient
from app.services.image_provider import GigaChatImageProvider

MODELS = ("GigaChat-2-Max", "GigaChat-2-Pro", "GigaChat-2")


async def run(args):
    scenes = json.loads(Path("docs/demo-assets/scenes.json").read_text(encoding="utf-8"))
    scenes = [scene for scene in scenes if scene["id"] in args.scenes]
    if len(scenes) != len(set(args.scenes)):
        raise ValueError("Unknown scene ID")
    args.output.mkdir(parents=True, exist_ok=True)
    settings = GigaChatSettings.from_env_file(args.env)
    rows = []
    for index, scene in enumerate(scenes):
        models = args.models[index % len(args.models):] + args.models[:index % len(args.models)]
        for model in models:
            provider = GigaChatImageProvider(settings.model_copy(update={"image_model": model}))
            async with ImageGenerationClient(provider, max_wait=40.0) as client:
                request_times = {}

                async def request_started(request):
                    request.extensions["benchmark_started"] = perf_counter()

                async def response_received(response):
                    await response.aread()
                    request = response.request
                    if request.url == settings.chat_url:
                        phase = "chat_completions"
                    elif request.method == "GET":
                        phase = "image_download"
                    else:
                        phase = "oauth"
                    request_times[phase] = {
                        "seconds": round(perf_counter() - request.extensions["benchmark_started"], 3),
                        "status": response.status_code,
                    }

                start = perf_counter()
                provider._http_client().event_hooks = {
                    "request": [request_started], "response": [response_received],
                }
                image = await client.generate(scene["calibrated_scene"])
                elapsed = perf_counter() - start
            filename = None
            if not image.is_fallback:
                extension = "jpg" if image.media_type == "image/jpeg" else "png"
                filename = f"{scene['id']}_{model}.{extension}"
                (args.output / filename).write_bytes(image.content)
            row = {
                "scene": scene["id"], "model": model, "seconds": round(elapsed, 3),
                "fallback": image.is_fallback, "reason": image.reason, "image": filename,
                "http": request_times,
            }
            rows.append(row)
            (args.output / "timings.json").write_text(
                json.dumps(rows, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
            )
            print(json.dumps(row), flush=True)


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--env", required=True, type=Path)
    parser.add_argument("--output", required=True, type=Path)
    parser.add_argument("--models", nargs="+", choices=MODELS, default=list(MODELS))
    parser.add_argument("--scenes", nargs="+", default=["01_tale_tail", "06_fine_eyes", "09_humbug"])
    asyncio.run(run(parser.parse_args()))
