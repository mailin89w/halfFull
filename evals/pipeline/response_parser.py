"""
response_parser.py — Parses and validates MedGemma JSON responses.

Implements robust extraction: tries json.loads() first, falls back to
regex-based JSON block extraction on failure.
"""
from __future__ import annotations

import json
import logging
import re

import jsonschema

logger = logging.getLogger(__name__)

# JSON schema for MedGemma response validation
RESPONSE_SCHEMA = {
    "type": "object",
    "required": ["top_conditions"],
    "properties": {
        "top_conditions": {
            "type": "array",
            "minItems": 1,
            "maxItems": 3,
            "items": {
                "type": "object",
                "required": ["condition_id", "confidence"],
                "properties": {
                    "condition_id": {"type": "string"},
                    "confidence":   {"type": "number", "minimum": 0, "maximum": 1},
                    "reasoning":    {"type": "string"},
                },
            },
        }
    },
}

# Regex to extract the outermost {...} block from text
_JSON_BLOCK_RE = re.compile(r"\{.*\}", re.DOTALL)


class ResponseParser:
    """
    Parses raw MedGemma text responses into validated dicts.
    """

    def parse(self, raw_response: str) -> dict | None:
        """
        Parse a raw MedGemma response string into a validated dict.

        Attempts:
        1. Direct json.loads() on the full string.
        2. Regex extraction of first {...} block, then json.loads().

        Returns:
            Parsed dict on success, None on failure.
        """
        if not raw_response or not raw_response.strip():
            logger.warning("Empty response received from MedGemma")
            return None

        # Attempt 1: direct parse
        try:
            parsed = json.loads(raw_response.strip())
            return parsed
        except json.JSONDecodeError:
            pass

        # Attempt 2: regex extraction
        match = _JSON_BLOCK_RE.search(raw_response)
        if match:
            json_str = match.group(0)
            try:
                parsed = json.loads(json_str)
                return parsed
            except json.JSONDecodeError as exc:
                logger.warning(
                    "JSON extraction failed after regex match: %s\nRaw response:\n%s",
                    exc,
                    raw_response[:500],
                )
                return None

        logger.warning(
            "Could not extract JSON from MedGemma response.\nRaw (first 500 chars):\n%s",
            raw_response[:500],
        )
        return None

    def is_valid(self, parsed: dict) -> bool:
        """
        Validate parsed dict against RESPONSE_SCHEMA.

        Returns True if valid, False otherwise. Does not raise.
        """
        try:
            jsonschema.validate(instance=parsed, schema=RESPONSE_SCHEMA)
            return True
        except jsonschema.ValidationError as exc:
            logger.debug("Response schema validation failed: %s", exc.message)
            return False
