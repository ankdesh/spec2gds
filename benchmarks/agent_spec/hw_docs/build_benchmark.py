"""Build deterministic V1 ``.spec`` packages from the hardware-doc corpus.

Each benchmark combines three complementary source representations:

* HTML supplies the typed human-readable narrative tree.
* PDF is retained byte-for-byte as provenance for visual comparison.
* The existing IEEE 1685-2014 component conversion supplies formal hardware
  structure and is migrated into the project's narrow 1685-2022 profile.

The original HTML, PDF, and XML are embedded below a registered annotation
namespace.  A generated package is therefore independently auditable rather
than being only a lossy conversion result.
"""

from __future__ import annotations

import argparse
from collections import Counter
from collections.abc import Sequence
from dataclasses import dataclass, field
import hashlib
import json
from pathlib import Path
import re
from urllib.parse import urljoin

import lxml.etree as etree
import lxml.html

from spec2gds.agent_spec.spec_format import ipxact
from spec2gds.agent_spec.spec_format.archive import SpecPackage
from spec2gds.agent_spec.spec_format.models import (
    AnnotationSchemaEntry,
    EntityRef,
    NarrativeBlock,
)


_HERE = Path(__file__).resolve().parent
_INPUT_ROOT = _HERE / "inputs"
_COMPONENT_ROOT = _HERE / "converted" / "ipxact"
_DEFAULT_OUTPUT = _HERE / "generated"
_XML_NAMESPACE = "http://www.w3.org/XML/1998/namespace"
_XSI_NAMESPACE = "http://www.w3.org/2001/XMLSchema-instance"


@dataclass(frozen=True)
class BenchmarkCase:
    """One HTML/PDF pair and the formal component source that describes it."""

    stem: str
    component_stem: str


CASES: tuple[BenchmarkCase, ...] = (
    BenchmarkCase("apb_gpio", "apb_gpio"),
    BenchmarkCase("apb_i2c_slave", "apb_i2c_slave"),
    BenchmarkCase("apb_timer", "apb_timer"),
    BenchmarkCase("cv_hpdcache_csrs", "cv_hpdcache"),
    BenchmarkCase("cv_hpdcache_interface", "cv_hpdcache"),
    BenchmarkCase("cvfpu_readme", "cvfpu"),
)


@dataclass
class _IdFactory:
    """Issue readable, deterministic, document-wide narrative identifiers."""

    stem: str
    count: int = 0

    def next(self, kind: str, hint: str = "") -> str:
        """Return the next XML-ID-safe identifier without content collisions."""
        self.count += 1
        slug = _identifier(hint)[:48].strip("_") or kind
        return f"{self.stem}_{kind}_{self.count:04d}_{slug}"


@dataclass
class _Protocol:
    """Self-contained bus and abstraction data derived from one component."""

    bus_vlnv: tuple[str, str, str, str]
    abstraction_vlnv: tuple[str, str, str, str]
    is_addressable: bool = False
    # logical name -> (direction on initiator, direction on target)
    ports: dict[str, tuple[str, str]] = field(default_factory=dict)


def _identifier(value: str) -> str:
    """Normalize arbitrary source text into the shared XML identifier grammar."""
    value = re.sub(r"[^A-Za-z0-9_.-]+", "_", value).strip("_.-") or "entity"
    return value if value[0].isalpha() or value[0] == "_" else f"e_{value}"


def _text(node: etree._Element) -> str:
    """Collapse browser-oriented whitespace into stable narrative text."""
    return " ".join("".join(node.itertext()).split())


def _heading_text(node: etree._Element) -> str:
    """Remove Sphinx's visible permalink glyph from an authored heading."""
    return _text(node).removesuffix("").strip()


def _content_root(document: etree._Element) -> etree._Element:
    """Select authored documentation while excluding site navigation chrome."""
    selectors = (
        "//*[@itemprop='articleBody']",
        "//article[contains(concat(' ', normalize-space(@class), ' '), ' markdown-body ')]",
        "//*[@role='main']",
        "//main",
    )
    for selector in selectors:
        matches = document.xpath(selector)
        if matches:
            # Some Sphinx pages nest candidate regions.  The deepest match is
            # closest to authored content and avoids breadcrumbs/navigation.
            return max(matches, key=lambda node: len(list(node.iterancestors())))
    body = document.find("body")
    return body if body is not None else document


def _source_url(document: etree._Element) -> str:
    """Recover a canonical source URL when the archived page records one."""
    candidates = document.xpath(
        "//link[contains(concat(' ', normalize-space(@rel), ' '), ' canonical ')]/@href"
        " | //meta[@property='og:url']/@content"
    )
    if candidates:
        return str(candidates[0]).strip()

    # ReadTheDocs exports resolver metadata even when it omits a canonical
    # link.  Reconstruct only from explicit metadata rather than guessing.
    def meta(name: str) -> str:
        values = document.xpath(f"//meta[@name='{name}']/@content")
        return str(values[0]).strip() if values else ""

    project = meta("readthedocs-project-slug")
    version = meta("readthedocs-version-slug")
    source_path = meta("readthedocs-resolver-filename")
    if project and version and source_path:
        return urljoin(f"https://{project}.readthedocs.io/en/{version}/", source_path.lstrip("/"))
    return ""


def _has_selected_ancestor(node: etree._Element, content: etree._Element) -> bool:
    """Prevent duplicate blocks from paragraphs nested in lists or tables."""
    selected = {"h1", "h2", "h3", "h4", "h5", "h6", "p", "pre", "ul", "ol", "table"}
    for ancestor in node.iterancestors():
        if ancestor is content:
            return False
        if isinstance(ancestor.tag, str) and ancestor.tag.lower() in selected:
            return True
    return False


def _list_block(node: etree._Element, ids: _IdFactory) -> NarrativeBlock | None:
    """Convert one HTML list into typed paragraph children."""
    children = []
    for item in node.xpath("./li"):
        value = _text(item)
        if value:
            children.append(NarrativeBlock(block_id=ids.next("item", value), type="paragraph", text=value))
    if not children:
        return None
    return NarrativeBlock(
        block_id=ids.next("list"),
        type="list",
        ordered=node.tag.lower() == "ol",
        children=children,
    )


def _table_block(node: etree._Element, ids: _IdFactory) -> NarrativeBlock | None:
    """Convert visible HTML table cells while retaining source row order."""
    rows: list[list[str]] = []
    for row in node.xpath(".//tr"):
        cells = [_text(cell) for cell in row.xpath("./th | ./td")]
        if cells and any(cells):
            rows.append(cells)
    if not rows:
        return None
    return NarrativeBlock(block_id=ids.next("table"), type="table", rows=rows)


def _html_narrative(
    html_bytes: bytes,
    stem: str,
    component_ref: EntityRef,
    annotation_paths: Sequence[str],
) -> tuple[str, list[NarrativeBlock], str, Counter[str]]:
    """Convert authored HTML into a heading-preserving typed narrative AST."""
    parser = lxml.html.HTMLParser(encoding="utf-8", recover=True)
    document = lxml.html.fromstring(html_bytes, parser=parser)
    content = _content_root(document)
    source_url = _source_url(document)
    headings = content.xpath(".//h1")
    title = _heading_text(headings[0]) if headings and _heading_text(headings[0]) else stem.replace("_", " ").title()
    ids = _IdFactory(stem)
    root = NarrativeBlock(block_id=ids.next("section", title), type="section", text=title, children=[])
    root.children.extend(
        [
            NarrativeBlock(
                block_id=ids.next("source"),
                type="paragraph",
                text=(
                    "Benchmark conversion from archived HTML and PDF source. "
                    f"Original evidence is retained at {', '.join(annotation_paths)}."
                    + (f" Canonical source: {source_url}" if source_url else "")
                ),
            ),
            NarrativeBlock(
                block_id=ids.next("component"),
                type="entity_link",
                text="Canonical IP-XACT component",
                entity_refs=[component_ref],
            ),
        ]
    )
    stack: list[tuple[int, NarrativeBlock]] = [(0, root)]
    first_title_skipped = False

    for node in content.iter():
        if not isinstance(node.tag, str):
            continue
        tag = node.tag.lower()
        if tag not in {"h1", "h2", "h3", "h4", "h5", "h6", "p", "pre", "ul", "ol", "table", "img"}:
            continue
        if _has_selected_ancestor(node, content):
            continue

        if tag.startswith("h"):
            value = _heading_text(node)
            if not value:
                continue
            if tag == "h1" and value == title and not first_title_skipped:
                first_title_skipped = True
                continue
            level = int(tag[1])
            section = NarrativeBlock(block_id=ids.next("section", value), type="section", text=value, children=[])
            while stack[-1][0] >= level:
                stack.pop()
            stack[-1][1].children.append(section)
            stack.append((level, section))
            continue

        block: NarrativeBlock | None = None
        if tag in {"p", "pre"}:
            value = _text(node)
            if value:
                block = NarrativeBlock(block_id=ids.next("paragraph", value), type="paragraph", text=value)
        elif tag in {"ul", "ol"}:
            block = _list_block(node, ids)
        elif tag == "table":
            block = _table_block(node, ids)
        elif tag == "img":
            # External image files were not captured with the archived HTML.
            # Preserve their meaningful labels without inventing a source asset.
            value = " ".join((node.get("alt") or node.get("title") or "").split())
            if value:
                block = NarrativeBlock(
                    block_id=ids.next("paragraph", value),
                    type="paragraph",
                    text=f"Figure: {value}",
                )
        if block is not None:
            stack[-1][1].children.append(block)

    counts: Counter[str] = Counter()

    def count(block: NarrativeBlock) -> None:
        """Count the final tree, including paragraphs owned by list blocks."""
        counts[block.type] += 1
        for child in block.children:
            count(child)

    count(root)
    return title, [root], source_url, counts


def _migrate_component(xml_bytes: bytes, component_stem: str) -> bytes:
    """Migrate a known 2014 component into the intentionally narrow V1 profile."""
    source = ipxact.parse_xml(xml_bytes)

    def clone(node: etree._Element, *, root: bool = False) -> etree._Element:
        """Clone one subtree while translating namespace and role vocabulary."""
        local_name = etree.QName(node).localname
        if local_name == "slave":
            local_name = "target"
        elif local_name == "master":
            local_name = "initiator"
        copied = etree.Element(
            etree.QName(ipxact.IPXACT_NAMESPACE, local_name),
            nsmap={"ipxact": ipxact.IPXACT_NAMESPACE} if root else None,
        )
        for name, value in sorted(node.attrib.items()):
            if etree.QName(name).namespace != _XSI_NAMESPACE:
                copied.set(name, value)
        copied.text = node.text
        for child in node:
            # Implementation views are outside V1's source profile and do not
            # describe ports or interfaces used by these benchmarks.
            if etree.QName(child).localname == "views":
                continue
            child_copy = clone(child)
            child_copy.tail = child.tail
            copied.append(child_copy)
        return copied

    migrated = clone(source, root=True)
    migrated.set(etree.QName(_XML_NAMESPACE, "id"), f"component_{_identifier(component_stem)}")
    raw = etree.tostring(migrated, encoding="UTF-8", xml_declaration=True)
    normalized, _, _ = ipxact.validate_ipxact_document(raw, "component")
    return normalized


def _vlnv(node: etree._Element) -> tuple[str, str, str, str]:
    """Read a complete VLNV attribute tuple from a reference element."""
    values = tuple(node.get(name, "").strip() for name in ("vendor", "library", "name", "version"))
    if not all(values):
        raise ValueError("Benchmark IP-XACT reference has an incomplete VLNV.")
    return values  # type: ignore[return-value]


def _opposite(direction: str) -> str:
    """Return a peer-facing wire direction."""
    return {"in": "out", "out": "in"}.get(direction, "inout")


def _protocols(component_xml: bytes) -> list[_Protocol]:
    """Derive minimal self-contained bus/abstraction documents from port maps."""
    root = ipxact.parse_xml(component_xml)
    physical_directions = {
        str(port.xpath("string(./*[local-name()='name'])")): str(
            port.xpath("string(./*[local-name()='wire']/*[local-name()='direction'])")
        )
        for port in root.xpath("./*[local-name()='model']/*[local-name()='ports']/*[local-name()='port']")
    }
    by_abstraction: dict[tuple[str, str, str, str], _Protocol] = {}
    for interface in root.xpath("./*[local-name()='busInterfaces']/*[local-name()='busInterface']"):
        bus_node = interface.xpath("./*[local-name()='busType']")[0]
        abstraction_node = interface.xpath(
            "./*[local-name()='abstractionTypes']/*[local-name()='abstractionType']/*[local-name()='abstractionRef']"
        )[0]
        bus_vlnv = _vlnv(bus_node)
        abstraction_vlnv = _vlnv(abstraction_node)
        protocol = by_abstraction.setdefault(
            abstraction_vlnv,
            _Protocol(bus_vlnv=bus_vlnv, abstraction_vlnv=abstraction_vlnv),
        )
        role = "initiator" if interface.xpath("./*[local-name()='initiator']") else "target"
        for mapping in interface.xpath(".//*[local-name()='portMap']"):
            logical = str(mapping.xpath("string(./*[local-name()='logicalPort']/*[local-name()='name'])"))
            physical = str(mapping.xpath("string(./*[local-name()='physicalPort']/*[local-name()='name'])"))
            direction = physical_directions.get(physical, "inout") or "inout"
            if role == "initiator":
                pair = (direction, _opposite(direction))
            else:
                pair = (_opposite(direction), direction)
            protocol.ports.setdefault(logical, pair)
            protocol.is_addressable |= "ADDR" in logical.upper()
    return list(by_abstraction.values())


def _identity_children(root: etree._Element, values: tuple[str, str, str, str]) -> None:
    """Append the schema-ordered IP-XACT identity fields."""
    for name, value in zip(("vendor", "library", "name", "version"), values, strict=True):
        etree.SubElement(root, etree.QName(ipxact.IPXACT_NAMESPACE, name)).text = value


def _bus_xml(protocol: _Protocol) -> bytes:
    """Build the minimal bus definition required by a component reference."""
    root = etree.Element(
        etree.QName(ipxact.IPXACT_NAMESPACE, "busDefinition"),
        nsmap={"ipxact": ipxact.IPXACT_NAMESPACE},
    )
    root.set(etree.QName(_XML_NAMESPACE, "id"), f"bus_{_identifier('_'.join(protocol.bus_vlnv))}")
    _identity_children(root, protocol.bus_vlnv)
    etree.SubElement(root, etree.QName(ipxact.IPXACT_NAMESPACE, "directConnection")).text = "true"
    etree.SubElement(root, etree.QName(ipxact.IPXACT_NAMESPACE, "isAddressable")).text = (
        "true" if protocol.is_addressable else "false"
    )
    return etree.tostring(root, encoding="UTF-8", xml_declaration=True)


def _abstraction_xml(protocol: _Protocol) -> bytes:
    """Build logical wire roles needed to validate every component port map."""
    root = etree.Element(
        etree.QName(ipxact.IPXACT_NAMESPACE, "abstractionDefinition"),
        nsmap={"ipxact": ipxact.IPXACT_NAMESPACE},
    )
    root.set(
        etree.QName(_XML_NAMESPACE, "id"),
        f"abstraction_{_identifier('_'.join(protocol.abstraction_vlnv))}",
    )
    _identity_children(root, protocol.abstraction_vlnv)
    bus_type = etree.SubElement(root, etree.QName(ipxact.IPXACT_NAMESPACE, "busType"))
    for name, value in zip(("vendor", "library", "name", "version"), protocol.bus_vlnv, strict=True):
        bus_type.set(name, value)
    ports = etree.SubElement(root, etree.QName(ipxact.IPXACT_NAMESPACE, "ports"))
    for logical_name, (initiator_direction, target_direction) in protocol.ports.items():
        port = etree.SubElement(ports, etree.QName(ipxact.IPXACT_NAMESPACE, "port"))
        etree.SubElement(port, etree.QName(ipxact.IPXACT_NAMESPACE, "logicalName")).text = logical_name
        wire = etree.SubElement(port, etree.QName(ipxact.IPXACT_NAMESPACE, "wire"))
        on_initiator = etree.SubElement(wire, etree.QName(ipxact.IPXACT_NAMESPACE, "onInitiator"))
        etree.SubElement(on_initiator, etree.QName(ipxact.IPXACT_NAMESPACE, "direction")).text = initiator_direction
        on_target = etree.SubElement(wire, etree.QName(ipxact.IPXACT_NAMESPACE, "onTarget"))
        etree.SubElement(on_target, etree.QName(ipxact.IPXACT_NAMESPACE, "direction")).text = target_direction
    return etree.tostring(root, encoding="UTF-8", xml_declaration=True)


def _document_counts(component_xml: bytes) -> dict[str, int]:
    """Return formal-structure metrics useful for benchmark quality checks."""
    root = ipxact.parse_xml(component_xml)
    return {
        "ports": len(root.xpath("./*[local-name()='model']/*[local-name()='ports']/*[local-name()='port']")),
        "bus_interfaces": len(root.xpath("./*[local-name()='busInterfaces']/*[local-name()='busInterface']")),
        "port_maps": len(root.xpath(".//*[local-name()='portMap']")),
    }


def _raw_sha256(data: bytes) -> str:
    """Return a plain digest for the external benchmark manifest."""
    return hashlib.sha256(data).hexdigest()


def build_case(case: BenchmarkCase, output_root: Path) -> dict[str, object]:
    """Build, validate, and save one benchmark package plus manifest metadata."""
    html_path = _INPUT_ROOT / "html" / f"{case.stem}.html"
    pdf_path = _INPUT_ROOT / "pdf" / f"{case.stem}.pdf"
    component_path = _COMPONENT_ROOT / f"{case.component_stem}.xml"
    html_bytes = html_path.read_bytes()
    pdf_bytes = pdf_path.read_bytes()
    original_component = component_path.read_bytes()
    if not pdf_bytes.startswith(b"%PDF-"):
        raise ValueError(f"Benchmark PDF has no PDF header: {pdf_path}")

    migrated_component = _migrate_component(original_component, case.component_stem)
    package = SpecPackage.create(f"benchmark_{case.stem}")
    protocols = _protocols(migrated_component)
    added_bus_vlnvs: set[tuple[str, str, str, str]] = set()
    for protocol in protocols:
        if protocol.bus_vlnv not in added_bus_vlnvs:
            package.add_document("bus_definition", _bus_xml(protocol))
            added_bus_vlnvs.add(protocol.bus_vlnv)
        package.add_document("abstraction_definition", _abstraction_xml(protocol))
    component = package.add_document("component", migrated_component)

    annotation_root = "annotations/benchmark_source"
    annotation_paths = (
        f"{annotation_root}/{case.stem}.html",
        f"{annotation_root}/{case.stem}.pdf",
        f"{annotation_root}/{case.stem}.source.xml",
    )
    package.manifest = package.manifest.model_copy(
        update={
            "annotation_schemas": [
                AnnotationSchemaEntry(namespace="benchmark_source", version=1, path_prefix=annotation_root)
            ]
        }
    )
    package.files.update(dict(zip(annotation_paths, (html_bytes, pdf_bytes, original_component), strict=True)))
    component_ref = EntityRef(
        document_id=package.manifest.document_id,
        entity_id=component.entity_id,
        entity_kind="component",
    )
    title, narrative, source_url, narrative_counts = _html_narrative(
        html_bytes,
        case.stem,
        component_ref,
        annotation_paths,
    )
    package.narrative = package.narrative.model_copy(update={"blocks": narrative})
    package.require_valid()

    output_path = output_root / f"{case.stem}.spec"
    package.save(str(output_path))
    return {
        "benchmark_id": case.stem,
        "title": title,
        "source_url": source_url,
        "output": output_path.name,
        "component_vlnv": component.vlnv,
        "component_entity_id": component.entity_id,
        "source_revision_hash": package.source_hash(),
        "package_sha256": _raw_sha256(output_path.read_bytes()),
        "source": {
            "html": {"path": str(html_path.relative_to(_HERE)), "bytes": len(html_bytes), "sha256": _raw_sha256(html_bytes)},
            "pdf": {"path": str(pdf_path.relative_to(_HERE)), "bytes": len(pdf_bytes), "sha256": _raw_sha256(pdf_bytes)},
            "ipxact_2014": {
                "path": str(component_path.relative_to(_HERE)),
                "bytes": len(original_component),
                "sha256": _raw_sha256(original_component),
            },
        },
        "formal_counts": _document_counts(migrated_component),
        "narrative_counts": dict(sorted(narrative_counts.items())),
        "embedded_documents": len(package.manifest.documents),
    }


def build_benchmarks(output_root: Path = _DEFAULT_OUTPUT) -> dict[str, object]:
    """Rebuild all six packages and their deterministic external index."""
    output_root.mkdir(parents=True, exist_ok=True)
    entries = [build_case(case, output_root) for case in CASES]
    manifest: dict[str, object] = {
        "format": "spec2gds-hardware-document-benchmark-v1",
        "package_count": len(entries),
        "packages": entries,
    }
    (output_root / "benchmark_manifest.json").write_text(
        json.dumps(manifest, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    return manifest


def main(argv: Sequence[str] | None = None) -> int:
    """Run the deterministic corpus builder from the repository root or module."""
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--output",
        type=Path,
        default=_DEFAULT_OUTPUT,
        help="generated-package directory (default: benchmarks/agent_spec/hw_docs/generated)",
    )
    arguments = parser.parse_args(argv)
    manifest = build_benchmarks(arguments.output.resolve())
    print(f"built {manifest['package_count']} benchmark packages in {arguments.output.resolve()}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
