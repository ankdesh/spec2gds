"""IEEE 1685-2022 validation and the narrow project-owned V1 profile."""

import functools
import re
import typing
from pathlib import Path

import lxml.etree as etree
import pyEDAA.IPXACT

from spec2gds.agent_spec.spec_format.models import DocumentKind, ID_PATTERN, validate_vlnv


IPXACT_NAMESPACE: str = "http://www.accellera.org/XMLSchema/IPXACT/1685-2022"
XML_NAMESPACE: str = "http://www.w3.org/XML/1998/namespace"

ROOT_NAMES: dict[DocumentKind, str] = {
    "component": "component",
    "design": "design",
    "bus_definition": "busDefinition",
    "abstraction_definition": "abstractionDefinition",
}

_BANNED_LOCAL_NAMES: set[str] = {
    "views",
    "view",
    "instantiations",
    "componentInstantiation",
    "designInstantiation",
    "designConfigurationInstantiation",
    "designConfiguration",
    "abstractor",
    "abstractorGenerators",
    "fileSets",
    "fileSetRef",
    "defaultFileBuilder",
    "componentGenerators",
    "generatorChain",
    "generatorChainConfiguration",
    "generatorExe",
    "clearboxElements",
    "clearboxElementRefs",
    "memoryMaps",
    "memoryMap",
    "addressSpaces",
    "addressSpace",
    "addressBlock",
    "register",
    "registerFile",
    "field",
    "cpus",
    "cpu",
    "indirectInterfaces",
    "indirectInterface",
    "structured",
    "subPorts",
    "subPort",
    "arrays",
    "array",
    "fieldMaps",
    "fieldMap",
    "powerDomains",
    "powerDomain",
    "powerDomainLinks",
    "powerConstraints",
    "modes",
    "mode",
    "resetTypes",
    "otherClockDrivers",
    "wireTypeDefs",
    "transTypeDefs",
    "signalTypeDefs",
    "domainTypeDefs",
    "structPortTypeDefs",
    "typeDefinitions",
    "vendorExtensions",
}
_BANNED_PREFIXES: tuple[str, ...] = ("mirrored",)


def _local_name(node: etree._Element) -> str:
    """Return an XML element's namespace-independent local name."""
    return etree.QName(node).localname


def _schema_directory() -> Path:
    """Locate the bundled official IEEE 1685-2022 schema set."""
    return Path(pyEDAA.IPXACT.__file__).resolve().parent / "Schema" / "ieee-1685-2022"


@functools.lru_cache(maxsize=1)
def _schema() -> etree.XMLSchema:
    """Compile the bundled top-level schema once per process."""
    index_path = _schema_directory() / "index.xsd"
    return etree.XMLSchema(etree.parse(str(index_path)))


def parse_xml(xml_bytes: bytes) -> etree._Element:
    """Parse untrusted XML with entities and network access disabled."""
    parser = etree.XMLParser(
        remove_blank_text=True,
        remove_comments=True,
        remove_pis=True,
        resolve_entities=False,
        no_network=True,
        load_dtd=False,
        huge_tree=False,
    )
    try:
        return typing.cast(etree._Element, etree.fromstring(xml_bytes, parser=parser))
    except etree.XMLSyntaxError as exc:
        raise ValueError(f"Invalid IP-XACT XML: {exc}") from exc


def normalize_xml(xml_bytes: bytes) -> bytes:
    """Return deterministic, safely parsed IP-XACT XML serialization."""
    root = parse_xml(xml_bytes)

    def clone(node: etree._Element, is_root: bool = False) -> etree._Element:
        # V1 rejects foreign elements later, but retain them here so its profile
        # diagnostic remains precise.  The IP-XACT namespace always uses the
        # project-owned prefix regardless of the input document's prefix.
        copied = etree.Element(
            node.tag,
            nsmap={"ipxact": IPXACT_NAMESPACE} if is_root else None,
        )
        for key, value in sorted(node.attrib.items(), key=lambda item: item[0]):
            copied.set(key, value)
        copied.text = node.text
        for child in node:
            copied_child = clone(child)
            copied_child.tail = child.tail
            copied.append(copied_child)
        return copied

    canonical_root = clone(root, is_root=True)
    etree.indent(canonical_root, space="  ")
    return etree.tostring(canonical_root, encoding="UTF-8", xml_declaration=True, pretty_print=True)


def root_vlnv(root: etree._Element) -> str:
    """Extract root VLNV children in the project's canonical string form."""
    fields: list[str] = []
    for field in ("vendor", "library", "name", "version"):
        matches = root.xpath(f"./*[local-name()='{field}']/text()")
        fields.append(str(matches[0]).strip() if matches else "")
    return validate_vlnv(":".join(fields))


def root_entity_id(root: etree._Element) -> str:
    """Read and validate the root XML identifier required by the V1 profile."""
    entity_id = root.get(f"{{{XML_NAMESPACE}}}id", "")
    if not ID_PATTERN.fullmatch(entity_id):
        raise ValueError("V1 IP-XACT document roots require a valid xml:id.")
    return entity_id


def validate_ipxact_document(xml_bytes: bytes, kind: DocumentKind) -> tuple[bytes, str, str]:
    """Validate XSD and V1 profile rules, returning normalized bytes and identity."""
    normalized = normalize_xml(xml_bytes)
    root = parse_xml(normalized)
    if etree.QName(root).namespace != IPXACT_NAMESPACE:
        raise ValueError("V1 requires the IEEE 1685-2022 IP-XACT namespace.")
    expected_root = ROOT_NAMES[kind]
    if _local_name(root) != expected_root:
        raise ValueError(f"Manifest kind {kind} requires <{expected_root}> XML root.")
    try:
        _schema().assertValid(root)
    except etree.DocumentInvalid as exc:
        raise ValueError(f"IP-XACT XSD validation failed: {exc}") from exc
    profile_errors = profile_diagnostics(root, kind)
    if profile_errors:
        raise ValueError("V1 IP-XACT profile validation failed: " + "; ".join(profile_errors))
    return normalized, root_vlnv(root), root_entity_id(root)


def profile_diagnostics(root: etree._Element, kind: DocumentKind) -> list[str]:
    """Return narrow V1 profile violations after ordinary XSD validation."""
    diagnostics: list[str] = []
    for node in root.iter():
        local_name = _local_name(node)
        namespace = etree.QName(node).namespace
        if namespace != IPXACT_NAMESPACE:
            diagnostics.append(f"Unsupported element namespace on {local_name}.")
            continue
        if local_name in _BANNED_LOCAL_NAMES or local_name.startswith(_BANNED_PREFIXES):
            diagnostics.append(f"V1 does not support IP-XACT element {local_name}.")

    if kind == "component":
        for model in root.xpath("./*[local-name()='model']"):
            model_children = [_local_name(child) for child in model]
            unsupported = [name for name in model_children if name != "ports"]
            if unsupported:
                diagnostics.append("V1 component model supports only ports, not " + ", ".join(unsupported) + ".")
        for interface in root.xpath(".//*[local-name()='busInterface']"):
            abstractions = interface.xpath("./*[local-name()='abstractionTypes']/*[local-name()='abstractionType']")
            if len(abstractions) != 1:
                diagnostics.append("Each V1 busInterface requires exactly one abstractionType.")
            if interface.xpath(".//*[local-name()='viewRef']"):
                diagnostics.append("V1 busInterface mappings cannot use viewRef.")

    if kind == "design" and root.xpath(".//*[local-name()='monitorInterconnection']"):
        diagnostics.append("V1 does not support monitorInterconnection records.")
    return sorted(set(diagnostics))
