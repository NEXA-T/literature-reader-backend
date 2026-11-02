"""Explicit real API call followed by repeated cache hits; no secrets in log."""
import argparse
import asyncio
from datetime import datetime, timezone
import json
from pathlib import Path
import statistics
import sys
import time

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from pydantic import ValidationError
from app.services.gigachat_client import GigaChatClient, GigaChatError
from app.services.gigachat_settings import GigaChatSettings


async def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--env-file", type=Path, required=True)
    parser.add_argument("--log", type=Path, default=Path("docs/llm-cache-measurement.json"))
    args = parser.parse_args()
    config = GigaChatSettings.from_env_file(args.env_file)
    config.model = "GigaChat-2-Max"
    config.cache_ttl_seconds = 300
    selection = "bite the bullet"
    context = (
        "For three nights Eleanor had avoided telling her father that she had lost the scholarship. "
        "There was no painless way to say it. At breakfast she decided to bite the bullet and "
        "confess before he opened the university's letter."
    )
    async with GigaChatClient(config) as client:
        start = time.perf_counter()
        result = await client.analyze_text(selection, context)
        real_ms = (time.perf_counter() - start) * 1000
        real_requests = client.request_count
    # Recreate client as explain_service currently does for each HTTP request.
    async with GigaChatClient(config) as client:
        times = []
        for _ in range(100):
            start = time.perf_counter()
            cached = await client.analyze_text(selection, context)
            times.append((time.perf_counter() - start) * 1000)
            assert result == cached
        cached_requests = client.request_count
        hits = client.cache_hits
    record = {
        "timestamp_utc": datetime.now(timezone.utc).isoformat(),
        "model_requested": config.model, "deadline_seconds": 8.0, "cache_ttl_seconds": 300,
        "real_call_ms": round(real_ms, 3), "real_api_requests_including_oauth": real_requests,
        "cached_first_ms": round(times[0], 4), "cached_median_ms": round(statistics.median(times), 4),
        "cached_max_ms": round(max(times), 4), "cache_samples": len(times),
        "cached_api_requests": cached_requests, "cache_hits": hits,
        "cached_median_below_5_ms": statistics.median(times) < 5,
        "measurement_scope": "analyze_text only; client construction, HTTP round trip and server serialization excluded",
        "result_type": type(result).__name__, "result": result.model_dump(),
        "image_prompt_length": len(result.image_prompt) if result.image_prompt is not None else None,
    }
    assert real_requests > 0 and cached_requests == 0 and hits == 100
    args.log.parent.mkdir(parents=True, exist_ok=True)
    args.log.write_text(json.dumps(record, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(record, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    try:
        asyncio.run(main())
    except (GigaChatError, ValueError, ValidationError, OSError):
        sys.exit("Measurement failed; check API/configuration. No secrets logged.")
