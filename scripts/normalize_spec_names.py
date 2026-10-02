"""Normalize current source names without changing identity or saved paths."""

from __future__ import annotations

import argparse
from pathlib import Path

from spec2gds.agent_spec.spec_format.ir import SpecRevision
from spec2gds.agent_spec.spec_format.naming import normalize_package_names, readable_name
from spec2gds.agent_spec.spec_format.owner_store import OwnerBindings
from spec2gds.agent_spec.spec_format.v1_api import V1Session


def normalize_sources(paths: list[Path], catalog: OwnerBindings) -> list[str]:
    """Use the owner's validated save and service-wide naming reservation."""
    changed: list[str] = []
    for path in sorted({path.expanduser().resolve() for path in paths}):
        session = V1Session(str(path))
        title = session.revision.narrative.title or readable_name(path.stem)
        with catalog.reserve_name(str(path), session.revision.document_id, title, normalize=True) as name:
            package = session.revision.to_package()
            if normalize_package_names(package, name):
                session.commit_revision(SpecRevision.from_package(package))
                changed.append(str(path))
        catalog.register(str(path), session.revision.document_id)
    return changed


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("paths", nargs="*", type=Path)
    parser.add_argument("--state-root", type=Path, help="Spec service catalog directory")
    parser.add_argument("--repository", action="store_true", help="Normalize repository samples and known packages")
    args = parser.parse_args()
    catalog = OwnerBindings(args.state_root)
    paths = [*args.paths, *(Path(row["path"]) for row in catalog.catalog())]
    if args.repository:
        paths.extend(Path("samples").rglob("*.spec"))
    for path in normalize_sources(paths, catalog):
        print(f"Normalized names: {path}")


if __name__ == "__main__":
    main()
