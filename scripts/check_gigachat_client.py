"""Explicit real-API smoke test; never run as part of pytest."""
import argparse
import asyncio
from datetime import datetime, timezone
import json
from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from pydantic import ValidationError
from app.services.gigachat_client import GigaChatClient, GigaChatError
from app.services.gigachat_settings import GigaChatSettings


async def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--env-file", type=Path, required=True)
    parser.add_argument("--model", default="GigaChat-2-Max")
    parser.add_argument("--log", type=Path)
    args = parser.parse_args()
    settings = GigaChatSettings.from_env_file(args.env_file)
    settings.model = args.model
    selected_text = "bite the bullet"
    context = (
        "For three nights Eleanor had avoided telling her father that she had lost the scholarship. "
        "There was no painless way to say it. At breakfast she decided to bite the bullet and "
        "confess before he opened the university's letter."
    )
    async with GigaChatClient(settings) as client:
        result = await client.analyze_text(selected_text, context, book_title=None)
    record = {
        "timestamp_utc": datetime.now(timezone.utc).isoformat(), "model_requested": settings.model,
        "method": "GigaChatClient.analyze_text", "result_type": type(result).__name__,
        "input": {"selected_text": selected_text, "context": context},
        "result": result.model_dump(), "validation": "passed",
    }
    text = json.dumps(record, ensure_ascii=False, indent=2) + "\n"
    print(text, end="")
    if args.log:
        args.log.parent.mkdir(parents=True, exist_ok=True)
        args.log.write_text(text, encoding="utf-8")


if __name__ == "__main__":
    try:
        asyncio.run(main())
    except (GigaChatError, ValidationError, ValueError, OSError):
        print("Проверка не выполнена. Проверьте настройки, сертификат и доступность API; секреты не выводятся.", file=sys.stderr)
        sys.exit(1)
