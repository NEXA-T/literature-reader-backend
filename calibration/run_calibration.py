"""Real GigaChat trials; strict JSON acceptance, no API secrets in artifacts."""
import argparse
from datetime import datetime, timezone
import hashlib
import json
import os
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
import test_gigachat as api


def strict_json(raw):
    def pairs(items):
        result = {}
        for key, value in items:
            if key in result:
                raise ValueError("Duplicate JSON key")
            result[key] = value
        return result

    def reject(value):
        raise ValueError("Nonstandard JSON constant")

    return json.loads(raw, object_pairs_hook=pairs, parse_constant=reject)


def validate(value, case, schema):
    if not isinstance(value, dict):
        raise ValueError("Output must be a JSON object, not a string/list")
    if set(value) != set(schema["required"]):
        missing = sorted(set(schema["required"]) - set(value))
        extra = sorted(set(value) - set(schema["required"]))
        raise ValueError(f"Missing keys: {missing}; unexpected keys: {extra}")
    for name, spec in schema["properties"].items():
        field = value[name]
        if spec["type"] == "string":
            if not isinstance(field, str) or (spec.get("minLength") and not field.strip()):
                raise ValueError(f"Invalid string: {name}")
            if "enum" in spec and field not in spec["enum"]:
                raise ValueError(f"Invalid enum: {name}")
        elif spec["type"] == "array":
            if not isinstance(field, list) or any(not isinstance(x, str) or not x.strip() for x in field):
                raise ValueError(f"Invalid string array: {name}")
            if not spec.get("minItems", 0) <= len(field) <= spec["maxItems"]:
                raise ValueError(f"Invalid array length: {name}")
    if value["term"] != case["selected_text"]:
        raise ValueError("term must exactly match selection")
    if any(quote not in case["context"] for quote in value.get("context_evidence", [])):
        raise ValueError("Evidence must be exact context substrings")
    if "uncertainty" in value and not case["context"] and not value["uncertainty"].strip():
        raise ValueError("Missing uncertainty for empty context")
    if value.get("expression_type") == "uncertain" and not value["uncertainty"].strip():
        raise ValueError("Missing uncertainty")


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--env-file", type=Path, required=True)
    parser.add_argument("--prompt", default="prompts/literary-analysis-v5.txt")
    parser.add_argument("--output", default="calibration/results-new.json")
    parser.add_argument("--limit", type=int)
    parser.add_argument("--model", default="GigaChat-2-Max", help="Does not modify .env")
    parser.add_argument("--schema", default="calibration/backend-response.schema.json")
    parser.add_argument("--structured", action="store_true", help="Use GigaChat response_format json_schema")
    args = parser.parse_args()
    if args.env_file.name != ".env" or not args.env_file.is_file():
        raise ValueError("--env-file must point to an existing local .env")
    api.ROOT = args.env_file.resolve().parent
    api.load_env()
    context = api.tls_context()
    token = api.post_json(api.AUTH_URL, {
        "Authorization": f"Basic {api.credentials()}", "RqUID": str(api.uuid.uuid4()),
        "Content-Type": "application/x-www-form-urlencoded", "Accept": "application/json"
    }, api.urllib.parse.urlencode({"scope": os.getenv("GIGACHAT_SCOPE", "GIGACHAT_API_PERS")}).encode(), context).get("access_token")
    if not isinstance(token, str) or not token.strip():
        raise RuntimeError("No access token")
    prompt = (ROOT / args.prompt).read_text(encoding="utf-8")
    schema = json.loads((ROOT / args.schema).read_text(encoding="utf-8"))
    cases = json.loads((ROOT / "calibration/cases.json").read_text(encoding="utf-8"))
    if args.limit:
        cases = cases[:args.limit]
    report = {"started_at_utc": datetime.now(timezone.utc).isoformat(), "model_requested": args.model or os.getenv("GIGACHAT_MODEL", "GigaChat"),
              "prompt_file": args.prompt, "system_prompt": prompt,
              "prompt_sha256": hashlib.sha256(prompt.encode()).hexdigest(),
              "schema_file": args.schema, "structured_output": args.structured, "temperature": 0.1,
              "cases": []}
    output = ROOT / args.output
    output.parent.mkdir(parents=True, exist_ok=True)
    for case in cases:
        entry = {"id": case["id"], "input": {k: case[k] for k in ("selected_text", "context")},
                 "expected": case["expected"], "attempts": [], "accepted": False}
        messages = [{"role":"system", "content":prompt},
                    {"role":"user", "content":json.dumps(entry["input"], ensure_ascii=False)}]
        for attempt in range(2):
            payload = {"model": report["model_requested"], "messages":messages,
                       "temperature":0.1, "max_tokens":1400, "stream":False}
            if args.structured:
                payload["response_format"] = {"type":"json_schema", "schema":schema, "strict":True}
            result = api.post_json(os.getenv("GIGACHAT_CHAT_URL", api.CHAT_URL),
                {"Authorization":f"Bearer {token}", "Content-Type":"application/json", "Accept":"application/json"},
                json.dumps(payload, ensure_ascii=False).encode(), context)
            choice = result["choices"][0]
            raw = choice["message"]["content"]
            trial = {"raw_content":raw, "finish_reason":choice.get("finish_reason"),
                     "model_returned":result.get("model"), "usage":result.get("usage")}
            try:
                if trial["finish_reason"] != "stop":
                    raise ValueError("Response not complete")
                parsed = strict_json(raw)
                validate(parsed, case, schema)
                trial["valid"] = True
                entry["response"] = parsed
                entry["accepted"] = True
            except (ValueError, TypeError) as error:
                trial["valid"] = False
                trial["validation_error"] = str(error)
                # Resend the original literary input, so parser diagnostics are not
                # mistaken for a new expression to analyse.
                messages = [{"role":"system", "content":prompt + "\nПредыдущий ответ отклонён валидатором: " + str(error)},
                            {"role":"user", "content":json.dumps(entry["input"], ensure_ascii=False)}]
            entry["attempts"].append(trial)
            if entry["accepted"]:
                break
        report["cases"].append(entry)
        output.write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
        print(case["id"], "VALID" if entry["accepted"] else "REJECTED", f"attempts={len(entry['attempts'])}", flush=True)
    report["completed_at_utc"] = datetime.now(timezone.utc).isoformat()
    report["accepted_count"] = sum(case["accepted"] for case in report["cases"])
    output.write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    return 0 if report["accepted_count"] == len(cases) else 1


if __name__ == "__main__":
    try:
        sys.exit(main())
    except (ValueError, RuntimeError) as error:
        print(f"Calibration failed: {error}", file=sys.stderr)
        sys.exit(1)
    except (OSError, KeyError, IndexError, TypeError):
        print("Calibration failed: network/file/response error; no secrets logged.", file=sys.stderr)
        sys.exit(1)
