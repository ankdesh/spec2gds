"""Write an importable per-run application factory for Python reload workers."""

from __future__ import annotations

import json
import sys
from pathlib import Path
from uuid import uuid4


def factory_bootstrap(body: str, config: dict, *, root: Path | None = None) -> str:
    """Keep resolved settings in files, including when uvicorn spawns a worker."""
    directory = (root or Path.cwd()) / "TEMP_serve-all" / f"python_{uuid4().hex}"
    directory.mkdir(parents=True)
    snapshot = directory / "services.json"
    snapshot.write_text(json.dumps(config, indent=2) + "\n")
    module = f"spec2gds_run_{uuid4().hex}"
    (directory / f"{module}.py").write_text(
        f"from pathlib import Path\nSERVICE_CONFIG = Path({str(snapshot)!r})\n" + body
    )
    sys.path.insert(0, str(directory))
    return f"{module}:create_app"
