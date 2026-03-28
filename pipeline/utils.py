"""Shared utilities for the pipeline."""

import json


def parse_json_response(text: str) -> dict:
    """Extract and parse the first JSON object from a Gemini response.

    Uses JSONDecoder.raw_decode to find the exact boundary of the first JSON
    object, handling filler text before/after and nested objects correctly.
    """
    start = text.find("{")
    if start == -1:
        raise ValueError(f"No JSON object found in response: {text[:200]}")
    try:
        result, _ = json.JSONDecoder().raw_decode(text, start)
        return result  # type: ignore[no-any-return]
    except json.JSONDecodeError as e:
        raise ValueError(f"Failed to parse JSON from response: {text[:200]}") from e
