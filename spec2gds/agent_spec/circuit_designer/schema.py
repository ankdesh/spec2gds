"""Deterministically export the circuit-designer JSON Schema bundle."""

from __future__ import annotations

import argparse
import json
from pathlib import Path
import typing

from spec2gds.agent_spec.circuit_designer.contracts import CircuitDesignerProtocol


def schema_bytes() -> bytes:
    """Return stable, formatted JSON Schema bytes for generated clients."""
    schema = CircuitDesignerProtocol.model_json_schema(mode="validation")
    return (json.dumps(schema, indent=2, sort_keys=True, ensure_ascii=False) + "\n").encode("utf-8")


def main(argv: typing.Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Export circuit-designer.v1 JSON Schema")
    parser.add_argument("--output", type=Path, required=True)
    arguments = parser.parse_args(argv)
    arguments.output.parent.mkdir(parents=True, exist_ok=True)
    arguments.output.write_bytes(schema_bytes())
    return 0


if __name__ == "__main__":  # pragma: no cover
    raise SystemExit(main())
