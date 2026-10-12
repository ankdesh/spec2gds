"""IEEE 1685-2022 validation and the narrow project-owned V1 profile."""

import functools
import typing
from pathlib import Path

import lxml.etree as etree
import pyEDAA.IPXACT

from spec2gds.spec.spec_format.models import ID_PATTERN, DocumentKind, validate_vlnv

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
        """Copy safe XML while canonicalizing namespaces and attributes."""
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
            if (_local_name(node) == "port" and node.getparent() is not None
                    and node.getparent().getparent() is not None
                    and _local_name(node.getparent().getparent()) == "model"
                    and _local_name(child) == "displayName"):
                continue
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
        for port in root.xpath("./*[local-name()='model']/*[local-name()='ports']/*[local-name()='port']"):
            diagnostics.extend(_component_port_profile_diagnostics(port))

    if kind == "design" and root.xpath(".//*[local-name()='monitorInterconnection']"):
        diagnostics.append("V1 does not support monitorInterconnection records.")
    return sorted(set(diagnostics))


def _component_port_profile_diagnostics(port: etree._Element) -> list[str]:
    """Validate one component port against the editor-authored subset."""
    diagnostics: list[str] = []
    name = _direct_text(port, "name") or "<unnamed>"
    port_attributes = _attribute_names(port)
    if port_attributes:
        diagnostics.append(
            f"Port {name} uses unsupported attributes: {', '.join(port_attributes)}."
        )
    child_names = [_local_name(child) for child in port]
    families = [family for family in ("wire", "transactional", "structured") if family in child_names]
    if len(families) != 1:
        return [f"Port {name} must contain exactly one supported family."]
    family = families[0]
    allowed_port_children = {"name", "displayName", "description", family}
    unsupported_port_children = sorted(set(child_names) - allowed_port_children)
    if unsupported_port_children:
        diagnostics.append(
            f"Port {name} uses unsupported fields: {', '.join(unsupported_port_children)}."
        )
    family_node = next(child for child in port if _local_name(child) == family)
    if family == "wire":
        diagnostics.extend(_wire_port_profile_diagnostics(name, family_node))
    elif family == "transactional":
        diagnostics.extend(_transactional_port_profile_diagnostics(name, family_node))
    else:
        diagnostics.extend(_structured_port_profile_diagnostics(name, family_node))
    return diagnostics


def _wire_port_profile_diagnostics(name: str, wire: etree._Element) -> list[str]:
    diagnostics: list[str] = []
    attributes = sorted({
        attribute
        for node in wire.iter()
        for attribute in _attribute_names(node)
    })
    if attributes:
        diagnostics.append(
            f"Wire port {name} uses unsupported attributes: {', '.join(attributes)}."
        )
    child_names = [_local_name(child) for child in wire]
    unsupported = sorted(set(child_names) - {"direction", "vectors"})
    if unsupported:
        diagnostics.append(f"Wire port {name} uses unsupported fields: {', '.join(unsupported)}.")
    if _direct_text(wire, "direction") not in {"in", "out", "inout"}:
        diagnostics.append(f"Wire port {name} direction must be in, out, or inout.")
    vectors = wire.xpath("./*[local-name()='vectors']/*[local-name()='vector']")
    if len(vectors) > 1:
        diagnostics.append(f"Wire port {name} supports at most one vector range.")
    return diagnostics


def _transactional_port_profile_diagnostics(name: str, transactional: etree._Element) -> list[str]:
    diagnostics: list[str] = []
    attributes = set(_attribute_names(transactional))
    for child in transactional:
        allowed = {"custom"} if _local_name(child) == "kind" else set()
        attributes.update(set(_attribute_names(child)) - allowed)
    if attributes:
        diagnostics.append(
            f"Transactional port {name} uses unsupported attributes: {', '.join(sorted(attributes))}."
        )
    child_names = [_local_name(child) for child in transactional]
    unsupported = sorted(set(child_names) - {"initiative", "kind", "busWidth"})
    if unsupported:
        diagnostics.append(
            f"Transactional port {name} uses unsupported fields: {', '.join(unsupported)}."
        )
    if _direct_text(transactional, "initiative") not in {"requires", "provides", "both"}:
        diagnostics.append(
            f"Transactional port {name} initiative must be requires, provides, or both."
        )
    kind = next((child for child in transactional if _local_name(child) == "kind"), None)
    if kind is not None:
        kind_value = (kind.text or "").strip()
        custom = (kind.get("custom") or "").strip()
        if kind_value == "custom" and not custom:
            diagnostics.append(f"Transactional port {name} custom kind requires a custom name.")
        if kind_value != "custom" and custom:
            diagnostics.append(f"Transactional port {name} custom name requires kind custom.")
    return diagnostics


def _structured_port_profile_diagnostics(name: str, structured: etree._Element) -> list[str]:
    diagnostics: list[str] = []
    attributes = set(_attribute_names(structured)) - {"packed"}
    for child in structured.iterdescendants():
        allowed = {"direction"} if _local_name(child) == "struct" else set()
        attributes.update(set(_attribute_names(child)) - allowed)
    if attributes:
        diagnostics.append(
            f"Structured port {name} uses unsupported attributes: {', '.join(sorted(attributes))}."
        )
    packed = (structured.get("packed") or "true").strip().lower()
    if packed not in {"true", "1"}:
        diagnostics.append(f"Structured port {name} must be packed.")
    child_names = [_local_name(child) for child in structured]
    unsupported = sorted(set(child_names) - {"struct", "structPortTypeDefs"})
    if unsupported:
        diagnostics.append(
            f"Structured port {name} uses unsupported fields: {', '.join(unsupported)}."
        )
    structs = [child for child in structured if _local_name(child) == "struct"]
    if len(structs) != 1:
        diagnostics.append(f"Structured port {name} must contain exactly one struct definition.")
    elif (structs[0].get("direction") or "").strip() not in {"in", "out", "inout"}:
        diagnostics.append(f"Structured port {name} direction must be in, out, or inout.")
    type_defs = next(
        (child for child in structured if _local_name(child) == "structPortTypeDefs"),
        None,
    )
    definitions = [] if type_defs is None else [
        child for child in type_defs if _local_name(child) == "structPortTypeDef"
    ]
    if len(definitions) != 1:
        diagnostics.append(f"Structured port {name} requires one internal type definition.")
    elif [_local_name(child) for child in definitions[0]] != ["typeName"]:
        diagnostics.append(f"Structured port {name} internal type definition is not editor-owned.")
    elif _direct_text(definitions[0], "typeName") != f"{name}_struct_t":
        diagnostics.append(f"Structured port {name} internal type name must be {name}_struct_t.")
    return diagnostics


def _direct_text(root: etree._Element, name: str) -> str:
    child = next((item for item in root if _local_name(item) == name), None)
    return (child.text or "").strip() if child is not None else ""


def _attribute_names(root: etree._Element) -> list[str]:
    """Return stable namespace-independent attribute names for diagnostics."""
    return sorted(etree.QName(name).localname for name in root.attrib)
