"""Build the hardware-document benchmark `.spec` files.

The benchmark stores original PDF/HTML source documents, converted office
documents, and extracted XML. This builder normalizes the converted XML into
strict IP-XACT with formal bus interfaces, then turns each converted office
document into a loadable `.spec` file by embedding the matching payload under
`spec_data/ipxact/` and adding editor relation metadata that attaches the
payload to the first document heading.
"""

from __future__ import annotations

import dataclasses
import hashlib
import json
from pathlib import Path
import typing

import lxml.etree as etree
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
IPXACT_NS = "http://www.accellera.org/XMLSchema/IPXACT/1685-2014"
IPXACT = f"{{{IPXACT_NS}}}"


def _qname(local_name: str) -> str:
    """Return an IP-XACT 2014 qualified tag name."""
    return f"{IPXACT}{local_name}"


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

APB_MAPS: dict[str, list[tuple[str, str]]] = {
    "apb_gpio": [
        ("PCLK", "HCLK"),
        ("PRESETn", "HRESETn"),
        ("PADDR", "PADDR"),
        ("PWDATA", "PWDATA"),
        ("PWRITE", "PWRITE"),
        ("PSEL", "PSEL"),
        ("PENABLE", "PENABLE"),
        ("PRDATA", "PRDATA"),
        ("PREADY", "PREADY"),
        ("PSLVERR", "PSLVERR"),
    ],
    "apb_i2c_slave": [
        ("PCLK", "apb_pclk_i"),
        ("PRESETn", "apb_presetn_i"),
        ("PADDR", "apb_paddr_i"),
        ("PSEL", "apb_psel_i"),
        ("PENABLE", "apb_penable_i"),
        ("PWRITE", "apb_pwrite_i"),
        ("PWDATA", "apb_pwdata_i"),
        ("PREADY", "apb_pready_o"),
        ("PRDATA", "apb_prdata_o"),
    ],
    "apb_timer": [
        ("PCLK", "HCLK"),
        ("PRESETn", "HRESETn"),
        ("PADDR", "PADDR"),
        ("PSEL", "PSEL"),
        ("PENABLE", "PENABLE"),
        ("PWRITE", "PWRITE"),
        ("PWDATA", "PWDATA"),
        ("PREADY", "PREADY"),
        ("PRDATA", "PRDATA"),
        ("PSLVERR", "PSLVERR"),
    ],
}

CUSTOM_INTERFACE_MAPS: dict[str, list[tuple[str, list[str]]]] = {
    "apb_gpio": [
        ("gpio", ["gpio_in", "gpio_in_sync", "gpio_out", "gpio_dir", "interrupt"]),
    ],
    "apb_i2c_slave": [
        ("i2c", ["i2c_scl_i", "i2c_sda_i", "i2c_sda_o", "i2c_sda_oe", "i2c_interrupt_o"]),
    ],
    "apb_timer": [
        ("timer_events", ["event_lo_o", "event_hi_o", "irq_lo_o", "irq_hi_o"]),
    ],
    "cv_hpdcache": [
        ("hpdcache_core", ["core_req", "core_rsp"]),
        ("hpdcache_memory_read", ["mem_req_read", "mem_resp_read"]),
        ("hpdcache_memory_write", ["mem_req_write", "mem_resp_write"]),
        ("hpdcache_events", ["evt_o"]),
    ],
    "cvfpu": [
        ("fpu_operation", []),
    ],
}


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


def _child_text(element: etree._Element, local_name: str) -> str:
    """Read direct child text from a namespaced XML element."""
    child = element.find(_qname(local_name))
    if child is None or child.text is None:
        return ""
    return child.text.strip()


def _port_names(root: etree._Element) -> list[str]:
    """Return component physical port names in document order."""
    names: list[str] = []
    for port in root.xpath("./*[local-name()='model']/*[local-name()='ports']/*[local-name()='port']"):
        name = _child_text(typing.cast(etree._Element, port), "name")
        if name:
            names.append(name)
    return names


def _fix_vector_elements(root: etree._Element) -> None:
    """Normalize `wire/vector` into the IP-XACT 2014 `wire/vectors/vector` shape."""
    for wire in root.xpath(".//*[local-name()='wire']"):
        wire_element = typing.cast(etree._Element, wire)
        vector = wire_element.find(_qname("vector"))
        if vector is None:
            continue
        wire_element.remove(vector)
        vectors = etree.Element(_qname("vectors"))
        vectors.append(vector)
        insert_at = 0
        direction = wire_element.find(_qname("direction"))
        if direction is not None:
            insert_at = list(wire_element).index(direction) + 1
        wire_element.insert(insert_at, vectors)


def _fix_parameter_description_order(root: etree._Element) -> None:
    """Move parameter descriptions before values as required by IP-XACT 2014."""
    for parameter in root.xpath(".//*[local-name()='parameters']/*[local-name()='parameter']"):
        parameter_element = typing.cast(etree._Element, parameter)
        description = parameter_element.find(_qname("description"))
        value = parameter_element.find(_qname("value"))
        if description is None or value is None:
            continue
        if list(parameter_element).index(description) < list(parameter_element).index(value):
            continue
        parameter_element.remove(description)
        insert_at = list(parameter_element).index(value)
        parameter_element.insert(insert_at, description)


def _append_port_map(parent: etree._Element, logical_port: str, physical_port: str) -> None:
    """Append one standard IP-XACT logical-to-physical port map."""
    port_map = etree.SubElement(parent, _qname("portMap"))
    logical = etree.SubElement(port_map, _qname("logicalPort"))
    etree.SubElement(logical, _qname("name")).text = logical_port
    physical = etree.SubElement(port_map, _qname("physicalPort"))
    etree.SubElement(physical, _qname("name")).text = physical_port


def _append_interface(
    parent: etree._Element,
    name: str,
    bus_type: tuple[str, str, str, str],
    abstraction_type: tuple[str, str, str, str],
    port_maps: list[tuple[str, str]],
) -> None:
    """Append one formal IP-XACT busInterface with abstraction-owned port maps."""
    if not port_maps:
        return
    interface = etree.SubElement(parent, _qname("busInterface"))
    etree.SubElement(interface, _qname("name")).text = name
    etree.SubElement(
        interface,
        _qname("busType"),
        vendor=bus_type[0],
        library=bus_type[1],
        name=bus_type[2],
        version=bus_type[3],
    )
    abstraction_types = etree.SubElement(interface, _qname("abstractionTypes"))
    abstraction = etree.SubElement(abstraction_types, _qname("abstractionType"))
    etree.SubElement(
        abstraction,
        _qname("abstractionRef"),
        vendor=abstraction_type[0],
        library=abstraction_type[1],
        name=abstraction_type[2],
        version=abstraction_type[3],
    )
    port_map_container = etree.SubElement(abstraction, _qname("portMaps"))
    for logical_port, physical_port in port_maps:
        _append_port_map(port_map_container, logical_port, physical_port)
    etree.SubElement(interface, _qname("slave"))
    etree.SubElement(interface, _qname("connectionRequired")).text = "true"
    etree.SubElement(interface, _qname("bitsInLau")).text = "8"
    etree.SubElement(interface, _qname("endianness")).text = "little"


def _custom_port_maps(case: BenchmarkCase, port_names: list[str]) -> list[tuple[str, list[tuple[str, str]]]]:
    """Group non-APB physical ports into benchmark-specific formal interfaces."""
    if case.case_id.startswith("cv_hpdcache"):
        config_key = "cv_hpdcache"
    elif case.case_id.startswith("cvfpu"):
        config_key = "cvfpu"
    else:
        config_key = case.case_id
    groups = CUSTOM_INTERFACE_MAPS.get(config_key, [])
    if not groups:
        return []
    grouped: list[tuple[str, list[tuple[str, str]]]] = []
    for interface_name, prefixes in groups:
        if prefixes:
            physical_ports = [
                port_name
                for port_name in port_names
                if any(port_name.startswith(prefix) for prefix in prefixes)
            ]
        else:
            physical_ports = list(port_names)
        maps = [(port_name.upper(), port_name) for port_name in physical_ports]
        grouped.append((interface_name, maps))
    return grouped


def _normalized_ipxact_bytes(case: BenchmarkCase, xml_path: Path) -> bytes:
    """Return strict IP-XACT XML that preserves ports while adding interfaces."""
    root = etree.fromstring(xml_path.read_bytes())
    _fix_vector_elements(root)
    _fix_parameter_description_order(root)

    existing_interfaces = root.find(_qname("busInterfaces"))
    if existing_interfaces is not None:
        root.remove(existing_interfaces)
    bus_interfaces = etree.Element(_qname("busInterfaces"))
    port_names = _port_names(root)
    port_name_set = set(port_names)

    apb_maps = [
        (logical, physical)
        for logical, physical in APB_MAPS.get(case.case_id, [])
        if physical in port_name_set
    ]
    _append_interface(
        bus_interfaces,
        "apb_slave",
        ("amba.com", "AMBA4", "APB", "r0p0"),
        ("amba.com", "AMBA4", "APB_rtl", "r0p0"),
        apb_maps,
    )

    for interface_name, maps in _custom_port_maps(case, port_names):
        _append_interface(
            bus_interfaces,
            interface_name,
            ("openhwgroup.org", "interfaces", interface_name, "1.0"),
            ("openhwgroup.org", "interfaces", f"{interface_name}_rtl", "1.0"),
            maps,
        )

    if len(bus_interfaces) == 0:
        raise ValueError(f"No formal IP-XACT bus interfaces could be created for {case.case_id}.")

    version = root.find(_qname("version"))
    if version is None:
        raise ValueError(f"Missing IP-XACT version in {xml_path}.")
    root.insert(list(root).index(version) + 1, bus_interfaces)
    return etree.tostring(root, xml_declaration=True, encoding="UTF-8", pretty_print=True)


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
    xml_bytes = _normalized_ipxact_bytes(case, xml_path)
    xml_path.write_bytes(xml_bytes)
    # Start from the converted ODT so the generated `.spec` preserves the
    # visible benchmark document exactly, then add structured IP-XACT metadata.
    spec_archive = archive.AgentSpecArchive(str(odt_path))
    ipxact_container_path = f"spec_data/ipxact/{case.ipxact_name}"
    spec_archive.inject_file(
        ipxact_container_path,
        xml_bytes,
        "application/xml+ipxact",
    )
    spec_archive.save(str(output_path))

    # Attach the XML payload to a visible heading so the editor can show the
    # relation instead of leaving the embedded file as orphaned package data.
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
    if not strict_valid:
        raise ValueError(f"Benchmark IP-XACT must validate for {case.case_id}: {strict_error}")
    files = {
        "pdf": pdf_path,
        "html": html_path,
        "odt": odt_path,
        "ipxact_xml": xml_path,
        "spec": output_path,
    }
    return {
        # The manifest intentionally records both semantic summary data and file
        # hashes so benchmark consumers can detect accidental fixture drift.
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
