"""Resolve one workspace path to its exact V1 specification package."""

from __future__ import annotations

import hashlib
import re
from pathlib import Path


def resolve_spec_target(value: str, *, create: bool = False) -> Path:
    path = Path(value).expanduser().resolve()
    if path.suffix.lower() == ".spec":
        if path.exists() and not path.is_file():
            raise ValueError(f"Specification target is not a file: {path}")
        if not path.exists() and not create:
            raise FileNotFoundError(path)
        if create:
            path.parent.mkdir(parents=True, exist_ok=True)
        return path
    if path.exists() and not path.is_dir():
        raise ValueError(f"Workspace target is not a directory: {path}")
    if not path.exists():
        if not create:
            raise FileNotFoundError(path)
        path.mkdir(parents=True)
    candidates = sorted(item for item in path.glob("*.spec") if item.is_file())
    if len(candidates) > 1:
        raise ValueError("Workspace contains multiple .spec files; pass one explicitly: "
                         + ", ".join(str(item) for item in candidates))
    if candidates:
        return candidates[0]
    if not create:
        raise FileNotFoundError(f"Workspace has no .spec file: {path}")
    name = re.sub(r"[^A-Za-z0-9_.-]+", "_", path.name).strip("._-") or "design"
    return path / f"{name}.spec"


def assistant_state_root(spec_path: Path) -> Path:
    canonical = spec_path.expanduser().resolve()
    identity = hashlib.sha256(str(canonical).encode("utf-8")).hexdigest()[:20]
    return canonical.parent / ".spec2gds" / "assistant" / identity
