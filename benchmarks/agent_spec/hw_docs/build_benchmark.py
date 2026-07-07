"""Build the hardware-document benchmark `.spec` files.

The benchmark stores original PDF/HTML source documents, converted office
documents, and extracted IP-XACT-like XML. This builder turns each converted
office document into a loadable `.spec` file by embedding the matching XML
payload under `spec_data/ipxact/` and adding editor relation metadata that
attaches the payload to the first document heading.
"""

from __future__ import annotations

import dataclasses
import hashlib
import json
from pathlib import Path
import typing

import spec2gds.agent_spec.document.ipxact_view as ipxact_view
import spec2gds.agent_spec.document.relations as relations
import spec2gds.agent_spec.document.session as editor_session
import spec2gds.agent_spec.package.archive as archive
import spec2gds.agent_spec.plugins.ipxact as ipxact_plugin


BENCHMARK_ROOT = Path(__file__).resolve().parent
INPUT_PDF_DIR = BENCHMARK_ROOT / "inputs" / "pdf"
INPUT_HTML_DIR = BENCHMARK_ROOT / "inputs" / "html"
CONVERTED_ODT_DIR = BENCHMARK_ROOT / "converted" / "odt"
CONVERTED_IPXACT_DIR = BENCHMARK_ROOT / "converted" / "ipxact"
GENERATED_DIR = BENCHMARK_ROOT / "generated"
MANIFEST_PATH = BENCHMARK_ROOT / "benchmark_manifest.json"


@dataclasses.dataclass(frozen=True)
class BenchmarkCase:
    """One source document and its converted structured payload."""

    case_id: str
    title: str
    pdf_name: str
    html_name: str
    odt_name: str
    ipxact_name: str

    @property
    def spec_name(self) -> str:
        """Return the generated `.spec` filename for this case."""
        return f"{self.case_id}.spec"


CASES: tuple[BenchmarkCase, ...] = (
    BenchmarkCase(
        case_id="apb_gpio",
        title="APB GPIO",
        pdf_name="apb_gpio.pdf",
        html_name="apb_gpio.html",
        odt_name="apb_gpio.odt",
        ipxact_name="apb_gpio.xml",
    ),
    BenchmarkCase(
        case_id="apb_i2c_slave",
        title="APB I2C Slave",
        pdf_name="apb_i2c_slave.pdf",
        html_name="apb_i2c_slave.html",
        odt_name="apb_i2c_slave.odt",
        ipxact_name="apb_i2c_slave.xml",
    ),
    BenchmarkCase(
        case_id="apb_timer",
        title="APB Timer",
        pdf_name="apb_timer.pdf",
        html_name="apb_timer.html",
        odt_name="apb_timer.odt",
        ipxact_name="apb_timer.xml",
    ),
    BenchmarkCase(
        case_id="cv_hpdcache_csrs",
        title="CV HPDcache CSRs",
        pdf_name="cv_hpdcache_csrs.pdf",
        html_name="cv_hpdcache_csrs.html",
        odt_name="cv_hpdcache_csrs.odt",
        ipxact_name="cv_hpdcache.xml",
    ),
    BenchmarkCase(
        case_id="cv_hpdcache_interface",
        title="CV HPDcache Interface",
        pdf_name="cv_hpdcache_interface.pdf",
        html_name="cv_hpdcache_interface.html",
        odt_name="cv_hpdcache_interface.odt",
        ipxact_name="cv_hpdcache.xml",
    ),
    BenchmarkCase(
        case_id="cvfpu_readme",
        title="CVFPU README",
        pdf_name="cvfpu_readme.pdf",
        html_name="cvfpu_readme.html",
        odt_name="cvfpu_readme.odt",
        ipxact_name="cvfpu.xml",
    ),
)


def _sha256(path: Path) -> str:
    """Return a stable content hash for benchmark provenance."""
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _relative(path: Path) -> str:
    """Format a path relative to the benchmark root for manifest entries."""
    return path.relative_to(BENCHMARK_ROOT).as_posix()


def _require_file(path: Path) -> None:
    """Fail early if the benchmark source copy is incomplete."""
    if not path.exists() or not path.is_file():
        raise FileNotFoundError(f"Missing benchmark source file: {path}")


def _strict_ipxact_status(xml_bytes: bytes) -> tuple[bool, str | None]:
    """Run the current strict IP-XACT validator and capture its status."""
    try:
        ipxact_plugin.IPXACTPlugin().validate_data(xml_bytes)
    except Exception as exc:
        return False, str(exc)
    return True, None


def _first_heading_id(document_path: Path) -> str:
    """Find a stable heading for attaching the benchmark XML in the editor."""
    session = editor_session.EditorSession.from_path(str(document_path))
    snapshot = session.snapshot()
    for block in snapshot.document.blocks:
        if block.block_type == "heading" and block.heading_id:
            return block.heading_id
    if snapshot.document.blocks:
        return snapshot.document.blocks[0].block_id
    raise ValueError(f"Benchmark document has no semantic blocks: {document_path}")


def _build_case(case: BenchmarkCase) -> dict[str, typing.Any]:
    """Generate one `.spec` file and return its manifest record."""
    pdf_path = INPUT_PDF_DIR / case.pdf_name
    html_path = INPUT_HTML_DIR / case.html_name
    odt_path = CONVERTED_ODT_DIR / case.odt_name
    xml_path = CONVERTED_IPXACT_DIR / case.ipxact_name
    for source_path in [pdf_path, html_path, odt_path, xml_path]:
        _require_file(source_path)

    GENERATED_DIR.mkdir(parents=True, exist_ok=True)
    output_path = GENERATED_DIR / case.spec_name
    xml_bytes = xml_path.read_bytes()
    spec_archive = archive.AgentSpecArchive(str(odt_path))
    ipxact_container_path = f"spec_data/ipxact/{case.ipxact_name}"
    spec_archive.inject_file(
        ipxact_container_path,
        xml_bytes,
        "application/xml+ipxact",
    )
    spec_archive.save(str(output_path))

    heading_id = _first_heading_id(output_path)
    editor_relations = relations.EditorRelations(
        ipxact_attachments={
            heading_id: [
                relations.HeadingIpxactAttachment(file_path=ipxact_container_path)
            ]
        }
    )
    spec_archive = archive.AgentSpecArchive(str(output_path))
    spec_archive.inject_file(
        relations.RELATIONS_PATH,
        relations.dump_relations(editor_relations),
        relations.RELATIONS_MEDIA_TYPE,
    )
    spec_archive.save(str(output_path))

    summary = ipxact_view.extract_ipxact_summary(ipxact_container_path, xml_bytes)
    strict_valid, strict_error = _strict_ipxact_status(xml_bytes)
    files = {
        "pdf": pdf_path,
        "html": html_path,
        "odt": odt_path,
        "ipxact_xml": xml_path,
        "spec": output_path,
    }
    return {
        "case_id": case.case_id,
        "title": case.title,
        "files": {name: _relative(path) for name, path in files.items()},
        "sha256": {name: _sha256(path) for name, path in files.items()},
        "ipxact_container_path": ipxact_container_path,
        "attached_heading_id": heading_id,
        "component": summary.component.model_dump(),
        "semantic_interface_count": len(summary.interfaces),
        "semantic_diagnostics": [
            diagnostic.model_dump() for diagnostic in summary.diagnostics
        ],
        "strict_ipxact_schema_valid": strict_valid,
        "strict_ipxact_schema_error": strict_error,
    }


def build_benchmark() -> dict[str, typing.Any]:
    """Build every benchmark case and write the manifest."""
    records = [_build_case(case) for case in CASES]
    manifest: dict[str, typing.Any] = {
        "version": 1,
        "description": (
            "Hardware-document benchmark with original PDF/HTML inputs, "
            "converted ODT/XML artifacts, and generated .spec packages."
        ),
        "cases": records,
    }
    MANIFEST_PATH.write_text(json.dumps(manifest, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    return manifest


def main() -> None:
    """CLI entry point for rebuilding benchmark `.spec` files."""
    manifest = build_benchmark()
    for record in manifest["cases"]:
        print(record["files"]["spec"])


if __name__ == "__main__":
    main()
