"""Canonical JSON serialization and SHA-256 hashing for Verification Planner."""

from __future__ import annotations

import hashlib
import json
import math
from typing import Any


def _validate_finite_numbers(val: Any) -> None:
    """Ensure no nonfinite numbers or floating-point numbers in identity-bearing records."""
    if isinstance(val, float):
        if not math.isfinite(val):
            raise ValueError(f"Non-finite float value '{val}' is not allowed in canonical representation.")
    elif isinstance(val, dict):
        for v in val.values():
            _validate_finite_numbers(v)
    elif isinstance(val, (list, tuple)):
        for item in val:
            _validate_finite_numbers(item)


def canonical_json(data: Any) -> bytes:
    """Emit canonical compact UTF-8 JSON with sorted keys, no extra whitespace, Unicode intact."""
    _validate_finite_numbers(data)
    return json.dumps(
        data,
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
    ).encode("utf-8")


def sha256_digest(data: bytes | str | Any) -> str:
    """Compute standard SHA-256 hexadecimal string from bytes or JSON data."""
    if isinstance(data, str):
        payload = data.encode("utf-8")
    elif isinstance(data, bytes):
        payload = data
    else:
        payload = canonical_json(data)
    return hashlib.sha256(payload).hexdigest()
