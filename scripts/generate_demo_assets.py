"""Generate five actual provider images; fallbacks remain explicitly marked."""
import argparse
import asyncio
from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path
import sys
import time

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from app.services.gigachat_settings import GigaChatSettings
from app.services.image_generation_client import ImageGenerationClient
from app.services.image_generation_client import GeneratedImage
from app.services.image_provider import GigaChatImageProvider, ImageProviderError, IMAGE_SYSTEM_PROMPT
from app.services.image_prompts import STYLE_SUFFIX, prepare_image_prompt


async def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--env-file", type=Path, required=True)
    parser.add_argument("--output-dir", type=Path, default=ROOT / "docs/demo-assets")
    parser.add_argument("--attempts", type=int, default=2, choices=(1, 2, 3))
    parser.add_argument("--offline-assets", action="store_true", help="Explicit 90s offline asset preparation, NOT the 15s interactive client")
    parser.add_argument("--case-id", action="append", help="Regenerate selected cases, preserving other existing results")
    args = parser.parse_args()
    scenes = json.loads((ROOT / "docs/demo-assets/scenes.json").read_text(encoding="utf-8"))
    settings = GigaChatSettings.from_env_file(args.env_file)
    settings.model = "GigaChat-2-Max"
    provider = GigaChatImageProvider(settings)
    args.output_dir.mkdir(parents=True, exist_ok=True)
    record = {"started_at_utc": datetime.now(timezone.utc).isoformat(),
              "provider": provider.name, "model_requested": settings.model,
              "poll_interval_seconds": 1.5, "interactive_client_max_wait_seconds": 15,
              "max_wait_per_attempt_seconds": 90 if args.offline_assets else 15,
              "mode": "offline_asset_preparation" if args.offline_assets else "interactive_client",
              "regenerated_case_ids": args.case_id,
              "offline_render_deadline_seconds": 90 if args.offline_assets else None,
              "system_prompt": IMAGE_SYSTEM_PROMPT, "style_suffix": STYLE_SUFFIX, "cases": []}
    if args.case_id:
        previous = args.output_dir / "generation-log.json"
        if previous.exists():
            record["cases"] = json.loads(previous.read_text(encoding="utf-8"))["cases"]
    async with ImageGenerationClient(provider) as client:
        for scene in scenes:
            if args.case_id and scene["id"] not in args.case_id:
                continue
            entry = {"id": scene["id"], "idiom": scene["selected_text"], "attempts": []}
            for _ in range(args.attempts):
                if args.offline_assets:
                    start = time.monotonic()
                    effective = prepare_image_prompt(scene["calibrated_scene"])
                    job = await provider.submit(effective)
                    checks = 0
                    try:
                        async with asyncio.timeout(90):
                            while True:
                                image = await provider.check(job)
                                checks += 1
                                if image is not None:
                                    break
                                await asyncio.sleep(1.5)
                        result = GeneratedImage(image.content, image.media_type, False, None, effective,
                                                provider.name, checks, time.monotonic() - start)
                    finally:
                        await provider.cancel(job)
                else:
                    result = await client.generate(scene["calibrated_scene"])
                attempt = {"is_fallback": result.is_fallback, "reason": result.reason,
                           "elapsed_seconds": round(result.elapsed_seconds, 3),
                           "polling_checks": result.polling_checks, "effective_prompt": result.effective_prompt}
                entry["attempts"].append(attempt)
                if not result.is_fallback:
                    break
                # A separately logged retry is allowed only for availability, never moderation.
                if result.reason not in ("timeout", "network_error", "provider_http_error"):
                    break
            extension = ".svg" if result.is_fallback else ".jpg" if result.media_type == "image/jpeg" else ".png"
            destination = args.output_dir / (scene["id"] + extension)
            destination.write_bytes(result.content)
            entry.update({"image_file": destination.name, "media_type": result.media_type,
                          "is_fallback": result.is_fallback, "sha256": hashlib.sha256(result.content).hexdigest(),
                          "bytes": len(result.content)})
            record["cases"] = [item for item in record["cases"] if item["id"] != entry["id"]]
            record["cases"].append(entry)
            (args.output_dir / "generation-log.json").write_text(json.dumps(record, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
            print(scene["id"], "FALLBACK" if result.is_fallback else "GENERATED", attempt["elapsed_seconds"], flush=True)
    record["completed_at_utc"] = datetime.now(timezone.utc).isoformat()
    record["generated_count"] = sum(not case["is_fallback"] for case in record["cases"])
    (args.output_dir / "generation-log.json").write_text(json.dumps(record, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    return 0 if record["generated_count"] == 5 else 1


if __name__ == "__main__":
    try:
        sys.exit(asyncio.run(main()))
    except (OSError, ValueError, ImageProviderError, TimeoutError):
        sys.exit("Demo generation failed; no credentials logged.")
