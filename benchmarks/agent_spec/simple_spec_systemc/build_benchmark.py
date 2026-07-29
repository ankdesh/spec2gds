"""Build and verify ``.spec`` imports for the simple SystemC ODT corpus."""

from __future__ import annotations

import argparse
from collections.abc import Sequence
import hashlib
import json
from pathlib import Path

from spec2gds.agent_spec.importers import (
    DoclingDocumentReader,
    DocumentToSpecConverter,
    OpenAIHardwareTableEnricher,
)
from spec2gds.agent_spec.importers.ipxact_from_tables import DEFAULT_OPENAI_MODEL
from spec2gds.agent_spec.spec_format.archive import SpecPackage
from spec2gds.agent_spec.spec_format.ir import SpecRevision


_HERE = Path(__file__).resolve().parent
_DEFAULT_OUTPUT = _HERE / "generated"
_MANIFEST_NAME = "benchmark_manifest.json"


def _sha256(data: bytes) -> str:
    """Return a plain SHA-256 digest for the external benchmark manifest."""
    return hashlib.sha256(data).hexdigest()


def _source_paths() -> list[Path]:
    """Return every authored ODT input in deterministic order."""
    return sorted(_HERE.glob("*_hw_spec.odt"))


def build_benchmarks(
    output_root: Path = _DEFAULT_OUTPUT,
    *,
    use_openai: bool = False,
    model: str = DEFAULT_OPENAI_MODEL,
) -> dict[str, object]:
    """Convert every ODT input and write an audit manifest."""
    output_root.mkdir(parents=True, exist_ok=True)
    converter = DocumentToSpecConverter(
        reader=DoclingDocumentReader(ocr=False),
        enricher=OpenAIHardwareTableEnricher(model=model) if use_openai else None,
    )
    entries: list[dict[str, object]] = []
    for source in _source_paths():
        output = output_root / f"{source.stem}.spec"
        result = converter.convert(source, output)
        if use_openai and result.port_count == 0:
            raise RuntimeError(
                f"OpenAI enrichment produced no IP-XACT ports for {source.name}."
            )
        package = SpecPackage.load(str(output))
        entries.append(
            {
                "benchmark_id": source.stem,
                "source": source.name,
                "source_bytes": source.stat().st_size,
                "source_sha256": _sha256(source.read_bytes()),
                "output": output.name,
                "package_bytes": output.stat().st_size,
                "package_sha256": _sha256(output.read_bytes()),
                "source_revision_hash": result.source_hash,
                "document_id": result.document_id,
                "narrative_counts": {
                    "blocks": result.block_count,
                    "images": result.image_count,
                    "tables": result.table_count,
                },
                "formal_counts": {
                    "ipxact_documents": len(package.manifest.documents),
                    "bus_interfaces": result.interface_count,
                    "ports": result.port_count,
                },
                "openai_model": result.openai_model,
            }
        )
    manifest: dict[str, object] = {
        "format": "spec2gds-simple-spec-systemc-import-v1",
        "generator": "spec2gds-import-document",
        "enrichment": {
            "openai": use_openai,
            "model": model if use_openai else "",
        },
        "package_count": len(entries),
        "packages": entries,
    }
    (output_root / _MANIFEST_NAME).write_text(
        json.dumps(manifest, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    return manifest


def verify_benchmarks(output_root: Path = _DEFAULT_OUTPUT) -> list[str]:
    """Verify package hashes, package validity, and embedded source fidelity."""
    manifest_path = output_root / _MANIFEST_NAME
    if not manifest_path.is_file():
        return [f"Missing benchmark manifest: {manifest_path}"]
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    diagnostics: list[str] = []
    expected_sources = {path.name: path for path in _source_paths()}
    entries = manifest.get("packages", [])
    if manifest.get("package_count") != len(entries):
        diagnostics.append("Manifest package_count does not match its package entries.")
    if {entry.get("source") for entry in entries} != set(expected_sources):
        diagnostics.append("Manifest source entries do not match the ODT corpus.")

    for entry in entries:
        source_name = entry.get("source", "")
        source = expected_sources.get(source_name)
        output = output_root / str(entry.get("output", ""))
        if source is None or not output.is_file():
            diagnostics.append(f"Missing source or output for {source_name!r}.")
            continue
        source_bytes = source.read_bytes()
        package_bytes = output.read_bytes()
        if _sha256(source_bytes) != entry.get("source_sha256"):
            diagnostics.append(f"Source hash mismatch: {source.name}")
        if _sha256(package_bytes) != entry.get("package_sha256"):
            diagnostics.append(f"Package hash mismatch: {output.name}")
        try:
            package = SpecPackage.load(str(output))
        except (OSError, ValueError) as exc:
            diagnostics.append(f"Invalid package {output.name}: {exc}")
            continue
        embedded_path = f"annotations/document_import/source{source.suffix.lower()}"
        if package.files.get(embedded_path) != source_bytes:
            diagnostics.append(f"Embedded source mismatch: {output.name}")
        if package.source_hash() != entry.get("source_revision_hash"):
            diagnostics.append(f"Source revision hash mismatch: {output.name}")
        revision = SpecRevision.from_package(package)
        actual_ports = sum(len(component.ports) for component in revision.components)
        actual_interfaces = sum(
            len(component.interfaces) for component in revision.components
        )
        expected_counts = entry.get("formal_counts", {})
        if len(package.manifest.documents) != expected_counts.get("ipxact_documents"):
            diagnostics.append(f"IP-XACT document count mismatch: {output.name}")
        if actual_ports != expected_counts.get("ports"):
            diagnostics.append(f"IP-XACT port count mismatch: {output.name}")
        if actual_interfaces != expected_counts.get("bus_interfaces"):
            diagnostics.append(f"IP-XACT interface count mismatch: {output.name}")
        if manifest.get("enrichment", {}).get("openai") and actual_ports == 0:
            diagnostics.append(f"Enriched package contains no IP-XACT ports: {output.name}")
    return diagnostics


def main(argv: Sequence[str] | None = None) -> int:
    """Build or verify the benchmark corpus."""
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--check",
        action="store_true",
        help="Verify existing outputs instead of rebuilding them.",
    )
    parser.add_argument(
        "--openai",
        action="store_true",
        help="Use OpenAI Structured Outputs to generate IP-XACT ports and interfaces.",
    )
    parser.add_argument(
        "--model",
        default=DEFAULT_OPENAI_MODEL,
        help=f"OpenAI model used with --openai (default: {DEFAULT_OPENAI_MODEL}).",
    )
    args = parser.parse_args(argv)
    if args.check:
        diagnostics = verify_benchmarks()
        if diagnostics:
            print(json.dumps({"valid": False, "diagnostics": diagnostics}, indent=2))
            return 2
        print(json.dumps({"valid": True, "package_count": len(_source_paths())}, sort_keys=True))
        return 0
    manifest = build_benchmarks(use_openai=args.openai, model=args.model)
    print(json.dumps({"package_count": manifest["package_count"], "output": str(_DEFAULT_OUTPUT)}))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
