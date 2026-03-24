"""
profile_loader.py — Loads and validates synthetic profiles from profiles.json.
"""
from __future__ import annotations

import json
import logging
from pathlib import Path

import jsonschema

logger = logging.getLogger(__name__)


class ProfileLoader:
    """
    Loads synthetic user profiles from a JSON file and validates them
    against the profile schema.
    """

    def __init__(self, profiles_path: str | Path, schema_path: str | Path) -> None:
        self.profiles_path = Path(profiles_path)
        self.schema_path = Path(schema_path)
        self._profiles: list[dict] | None = None
        self._schema: dict | None = None

    @property
    def schema(self) -> dict:
        if self._schema is None:
            with self.schema_path.open() as f:
                self._schema = json.load(f)
        return self._schema

    def load_all(self) -> list[dict]:
        """Load all profiles from disk, validate each against schema."""
        if self._profiles is not None:
            return self._profiles

        if not self.profiles_path.exists():
            raise FileNotFoundError(
                f"Profiles file not found: {self.profiles_path}\n"
                "Run: python evals/cohort_generator.py --seed 42"
            )

        with self.profiles_path.open() as f:
            profiles = json.load(f)

        logger.info("Loaded %d profiles from %s", len(profiles), self.profiles_path)

        for profile in profiles:
            self.validate(profile)

        self._profiles = profiles
        return self._profiles

    def load_by_type(self, profile_type: str) -> list[dict]:
        """Return only profiles of the given type (e.g. 'positive', 'healthy')."""
        return [p for p in self.load_all() if p.get("profile_type") == profile_type]

    def load_by_condition(self, condition_id: str) -> list[dict]:
        """Return only profiles targeting the given condition ID."""
        return [p for p in self.load_all() if p.get("target_condition") == condition_id]

    def validate(self, profile: dict) -> bool:
        """
        Validate a profile against the JSON schema.
        Raises jsonschema.ValidationError on failure.
        Returns True on success.
        """
        jsonschema.validate(instance=profile, schema=self.schema)
        return True
