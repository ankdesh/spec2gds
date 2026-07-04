import os
import shutil
import typing
from pathlib import Path

import spec2gds.spec.odt_container.container as container
import spec2gds.spec.odt_container.ipxact_plugin as ipxact_plugin
import spec2gds.spec.odt_container.json_plugin as json_plugin
import spec2gds.spec.odt_container.manager as manager
import spec2gds.spec.odt_container.verifier as verifier


SAMPLE_DIR: Path = Path(__file__).resolve().parent
REPO_ROOT: Path = SAMPLE_DIR.parents[3]
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
      <text:p>This small ODT is generated for spec2gds smoke testing.</text:p>
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
      <text:p>Document with heading-based section variants.</text:p>
      <text:h text:outline-level="2">Register behavior//v1</text:h>
      <text:p>Version one behavior for the generated timer sample.</text:p>
      <text:h text:outline-level="2">Register behavior//v2</text:h>
      <text:p>Version two behavior for the generated timer sample.</text:p>
      <text:h text:outline-level="2">IP-XACT reference</text:h>
      <text:p><text:a xlink:type="simple" xlink:href="spec://ipxact/sample_component.xml/VLNV/Vendor">Linked IP vendor</text:a></text:p>
    </office:text>
  </office:body>
</office:document-content>
"""


def _manager() -> manager.PluginManager:
    plugin_manager = manager.PluginManager()
    plugin_manager.register_plugin(json_plugin.SimpleJSONPlugin())
    plugin_manager.register_plugin(ipxact_plugin.IPXACTPlugin())
    return plugin_manager


def _write_synthetic_raw(name: str, content_xml: bytes) -> Path:
    output_path = RAW_DIR / name
    odt = container.HybridODTContainer()
    odt.document.set_part("content.xml", content_xml)
    odt.save(str(output_path))
    return output_path


def _candidate_raw_documents() -> list[Path]:
    RAW_DIR.mkdir(parents=True, exist_ok=True)
    GENERATED_DIR.mkdir(parents=True, exist_ok=True)

    package_template = REPO_ROOT / ".venv/lib/python3.12/site-packages/odfdo/templates/lpod_styles.odt"
    if package_template.exists():
        shutil.copy2(package_template, RAW_DIR / "odfdo_lpod_styles.odt")

    _write_synthetic_raw("synthetic_basic.odt", BASIC_CONTENT_XML)
    _write_synthetic_raw("synthetic_versioned_sections.odt", VERSIONED_CONTENT_XML)

    return sorted(path for path in RAW_DIR.glob("*.odt") if path.is_file())


def _inject_ipxact(raw_path: Path, ipxact_bytes: bytes) -> Path:
    output_path = GENERATED_DIR / f"{raw_path.stem}_with_ipxact.odt"
    odt = container.HybridODTContainer(str(raw_path))
    plugin_manager = _manager()
    plugin_manager.inject_payload(
        odt,
        "ipxact",
        "sample_component.xml",
        ipxact_bytes,
    )
    odt.save(str(output_path))
    return output_path


def _verify_document(path: Path) -> verifier.ContainerVerificationReport:
    odt = container.HybridODTContainer(str(path))
    report = verifier.ContainerVerifier(odt, _manager()).verify_all()
    if not report.is_fully_consistent:
        raise ValueError(f"Generated sample failed verification: {path}: {report}")
    return report


def build_samples() -> list[Path]:
    ipxact_bytes = IPXACT_PATH.read_bytes()
    ipxact_plugin.IPXACTPlugin().validate_data(ipxact_bytes)

    generated_paths: list[Path] = []
    for raw_path in _candidate_raw_documents():
        generated_path = _inject_ipxact(raw_path, ipxact_bytes)
        _verify_document(generated_path)
        generated_paths.append(generated_path)
    return generated_paths


def main() -> None:
    generated_paths = build_samples()
    for generated_path in generated_paths:
        print(generated_path)


if __name__ == "__main__":
    main()
