"""Build checked-in sample `.spec` documents for smoke tests and the editor."""

from pathlib import Path

import spec2gds.agent_spec.package.archive as container
import spec2gds.agent_spec.document.relations as relations
import spec2gds.agent_spec.document.semantic as semantic
import spec2gds.agent_spec.plugins.ipxact as ipxact_plugin
import spec2gds.agent_spec.plugins.json_payload as json_plugin
import spec2gds.agent_spec.plugins.manager as manager
import spec2gds.agent_spec.package.verifier as verifier


SAMPLE_DIR: Path = Path(__file__).resolve().parent
RAW_DIR: Path = SAMPLE_DIR / "raw"
GENERATED_DIR: Path = SAMPLE_DIR / "generated"
IPXACT_PATH: Path = SAMPLE_DIR / "ipxact" / "sample_component.xml"


BASIC_CONTENT_XML: bytes = b"""<?xml version="1.0" encoding="UTF-8"?>
<office:document-content
  xmlns:office="urn:oasis:names:tc:opendocument:xmlns:office:1.0"
  xmlns:text="urn:oasis:names:tc:opendocument:xmlns:text:1.0"
  xmlns:xlink="http://www.w3.org/1999/xlink"
  office:version="1.3">
  <office:body>
    <office:text>
      <text:h text:outline-level="1">Synthetic basic sample</text:h>
      <text:p>This small agent-spec is generated for spec2gds smoke testing.</text:p>
      <text:p><text:a xlink:type="simple" xlink:href="spec://ipxact/sample_component.xml/VLNV/Name">Linked IP name</text:a></text:p>
    </office:text>
  </office:body>
</office:document-content>
"""


VERSIONED_CONTENT_XML: bytes = b"""<?xml version="1.0" encoding="UTF-8"?>
<office:document-content
  xmlns:office="urn:oasis:names:tc:opendocument:xmlns:office:1.0"
  xmlns:text="urn:oasis:names:tc:opendocument:xmlns:text:1.0"
  xmlns:xlink="http://www.w3.org/1999/xlink"
  office:version="1.3">
  <office:body>
    <office:text>
      <text:h text:outline-level="1">Timer block specification</text:h>
      <text:p>Document with relation-based section variants.</text:p>
      <text:h text:outline-level="2">Register behavior v1</text:h>
      <text:p>Version one behavior for the generated timer sample.</text:p>
      <text:h text:outline-level="2">Register behavior v2</text:h>
      <text:p>Version two behavior for the generated timer sample.</text:p>
      <text:h text:outline-level="2">IP-XACT reference</text:h>
      <text:p><text:a xlink:type="simple" xlink:href="spec://ipxact/sample_component.xml/VLNV/Vendor">Linked IP vendor</text:a></text:p>
    </office:text>
  </office:body>
</office:document-content>
"""


def _manager() -> manager.PluginManager:
    """Build the same default plugin set used by the package CLI."""
    plugin_manager = manager.PluginManager()
    plugin_manager.register_plugin(json_plugin.SimpleJSONPlugin())
    plugin_manager.register_plugin(ipxact_plugin.IPXACTPlugin())
    return plugin_manager


def _write_synthetic_raw(name: str, content_xml: bytes) -> Path:
    """Write a small ODT-compatible `.spec` package from literal content XML."""
    output_path = RAW_DIR / name
    archive = container.AgentSpecArchive()
    archive.document.set_part("content.xml", content_xml)
    archive.save(str(output_path))
    return output_path


def _write_versioned_raw() -> Path:
    """Write the sample that demonstrates explicit section-version relations."""
    output_path = RAW_DIR / "synthetic_versioned_sections.spec"
    content_with_ids = semantic.ensure_heading_ids(VERSIONED_CONTENT_XML)
    parsed = semantic.parse_content_xml(content_with_ids)
    heading_by_text = {
        block.text: block
        for block in parsed.blocks
        if block.block_type == "heading"
    }
    v1_heading = heading_by_text["Register behavior v1"]
    v2_heading = heading_by_text["Register behavior v2"]
    editor_relations = relations.EditorRelations(
        section_groups=[
            relations.SectionVersionGroup(
                group_id="register-behavior",
                title="Register behavior",
                level=2,
                variants=[
                    relations.SectionVersionRef(
                        version="v1",
                        heading_id=v1_heading.heading_id or v1_heading.block_id,
                        block_ids=[v1_heading.block_id, "block-3"],
                    ),
                    relations.SectionVersionRef(
                        version="v2",
                        heading_id=v2_heading.heading_id or v2_heading.block_id,
                        block_ids=[v2_heading.block_id, "block-5"],
                    ),
                ],
                active_version="v1",
            )
        ],
    )
    archive = container.AgentSpecArchive()
    archive.document.set_part("content.xml", content_with_ids)
    archive.inject_file(
        relations.RELATIONS_PATH,
        relations.dump_relations(editor_relations),
        relations.RELATIONS_MEDIA_TYPE,
    )
    archive.save(str(output_path))
    return output_path


def _candidate_raw_documents() -> list[Path]:
    """Ensure raw sample inputs exist and return them in deterministic order."""
    RAW_DIR.mkdir(parents=True, exist_ok=True)
    GENERATED_DIR.mkdir(parents=True, exist_ok=True)

    _write_synthetic_raw("synthetic_basic.spec", BASIC_CONTENT_XML)
    _write_versioned_raw()

    return sorted(path for path in RAW_DIR.glob("*.spec") if path.is_file())


def _inject_ipxact(raw_path: Path, ipxact_bytes: bytes) -> Path:
    """Generate a sample by injecting the shared IP-XACT component XML."""
    output_path = GENERATED_DIR / f"{raw_path.stem}_with_ipxact.spec"
    archive = container.AgentSpecArchive(str(raw_path))
    plugin_manager = _manager()
    plugin_manager.inject_payload(
        archive,
        "ipxact",
        "sample_component.xml",
        ipxact_bytes,
    )
    archive.save(str(output_path))
    return output_path


def _verify_document(path: Path) -> verifier.ContainerVerificationReport:
    """Verify a generated sample before it becomes a test/editor fixture."""
    archive = container.AgentSpecArchive(str(path))
    report = verifier.ContainerVerifier(archive, _manager()).verify_all()
    if not report.is_fully_consistent:
        raise ValueError(f"Generated sample failed verification: {path}: {report}")
    return report


def build_samples() -> list[Path]:
    """Build every generated sample and return the output paths."""
    ipxact_bytes = IPXACT_PATH.read_bytes()
    # Validate the shared XML once before injecting it into each sample package.
    ipxact_plugin.IPXACTPlugin().validate_data(ipxact_bytes)

    generated_paths: list[Path] = []
    for raw_path in _candidate_raw_documents():
        generated_path = _inject_ipxact(raw_path, ipxact_bytes)
        _verify_document(generated_path)
        generated_paths.append(generated_path)
    return generated_paths


def main() -> None:
    """CLI entry point for rebuilding sample documents."""
    generated_paths = build_samples()
    for generated_path in generated_paths:
        print(generated_path)


if __name__ == "__main__":
    main()
