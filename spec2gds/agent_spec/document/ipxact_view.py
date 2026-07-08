"""Lightweight IP-XACT summarizer for editor previews.

This module intentionally extracts a small namespace-tolerant summary instead
of replacing the strict IP-XACT plugin. The editor needs fast, readable
component/interface feedback, but it must still preserve IP-XACT semantics:
ports are not treated as bus interfaces unless formal `busInterface` nodes
exist in the XML.
"""

import typing

import lxml.etree as etree
import pydantic


class Diagnostic(pydantic.BaseModel):
    """Editor-facing diagnostic produced while summarizing IP-XACT XML."""

    severity: str
    source: str
    message: str


class IpxactVLNV(pydantic.BaseModel):
    """Vendor/library/name/version identifier used throughout IP-XACT."""

    vendor: str = ""
    library: str = ""
    name: str = ""
    version: str = ""


class IpxactPortMap(pydantic.BaseModel):
    """Logical-to-physical port mapping for one bus interface."""

    logical_port: str = ""
    physical_port: str = ""


class IpxactInterfaceSummary(pydantic.BaseModel):
    """Compact editor summary of one IP-XACT bus interface."""

    name: str
    mode: str = ""
    bus_type: IpxactVLNV = pydantic.Field(default_factory=IpxactVLNV)
    abstraction_type: IpxactVLNV = pydantic.Field(default_factory=IpxactVLNV)
    port_maps: list[IpxactPortMap] = pydantic.Field(default_factory=list)


class IpxactComponentSummary(pydantic.BaseModel):
    """Compact editor summary of one IP-XACT component XML file."""

    file_path: str
    component: IpxactVLNV = pydantic.Field(default_factory=IpxactVLNV)
    interfaces: list[IpxactInterfaceSummary] = pydantic.Field(default_factory=list)
    diagnostics: list[Diagnostic] = pydantic.Field(default_factory=list)

    @property
    def has_blocking_diagnostics(self) -> bool:
        """Return whether the editor should block saving this XML."""
        for diagnostic in self.diagnostics:
            if diagnostic.severity in {"warning", "error"}:
                return True
        return False


def _text(element: etree._Element, local_name: str) -> str:
    """Return direct child text by local name, ignoring XML namespace prefixes."""
    result = element.xpath(f"./*[local-name()='{local_name}']/text()")
    if not result:
        return ""
    return str(result[0]).strip()


def _vlnv_from_children(element: etree._Element) -> IpxactVLNV:
    """Read VLNV fields stored as child elements."""
    return IpxactVLNV(
        vendor=_text(element, "vendor"),
        library=_text(element, "library"),
        name=_text(element, "name"),
        version=_text(element, "version"),
    )


def _vlnv_from_attributes(element: etree._Element | None) -> IpxactVLNV:
    """Read VLNV fields stored as attributes on a reference element."""
    if element is None:
        return IpxactVLNV()
    return IpxactVLNV(
        vendor=element.get("vendor", ""),
        library=element.get("library", ""),
        name=element.get("name", ""),
        version=element.get("version", ""),
    )


def _first_child(element: etree._Element, local_name: str) -> etree._Element | None:
    """Return the first direct child with a matching local name."""
    result = element.xpath(f"./*[local-name()='{local_name}']")
    if not result:
        return None
    return typing.cast(etree._Element, result[0])


def _extract_port_maps(interface_element: etree._Element) -> list[IpxactPortMap]:
    """Extract all logical/physical port map pairs from an interface."""
    port_maps: list[IpxactPortMap] = []
    for port_map in interface_element.xpath(".//*[local-name()='portMap']"):
        logical = ""
        physical = ""
        logical_nodes = port_map.xpath(".//*[local-name()='logicalPort']/*[local-name()='name']/text()")
        physical_nodes = port_map.xpath(".//*[local-name()='physicalPort']/*[local-name()='name']/text()")
        if logical_nodes:
            logical = str(logical_nodes[0]).strip()
        if physical_nodes:
            physical = str(physical_nodes[0]).strip()
        port_maps.append(
            IpxactPortMap(
                logical_port=logical,
                physical_port=physical,
            )
        )
    return port_maps


def _extract_mode(interface_element: etree._Element) -> str:
    """Infer interface mode across IP-XACT schema variants."""
    for mode_name in [
        "master",
        "slave",
        "system",
        "mirroredSlave",
        "mirroredMaster",
        "mirroredSystem",
        "monitor",
    ]:
        mode_node = _first_child(interface_element, mode_name)
        if mode_node is not None:
            if mode_name == "monitor":
                return mode_node.get("interfaceMode", "monitor")
            return mode_name

    legacy_mode = _text(interface_element, "interfaceMode")
    if legacy_mode:
        # Some older or simplified XML stores mode as text rather than a named
        # child element.
        return legacy_mode
    return ""


def _extract_interface(interface_element: etree._Element) -> IpxactInterfaceSummary:
    """Build a compact summary for one `busInterface` element."""
    bus_type = _vlnv_from_attributes(_first_child(interface_element, "busType"))
    abstraction_type = IpxactVLNV()
    abstraction_ref_elements = interface_element.xpath(".//*[local-name()='abstractionRef']")
    if abstraction_ref_elements:
        abstraction_type = _vlnv_from_attributes(
            typing.cast(etree._Element, abstraction_ref_elements[0])
        )
    else:
        abstraction_type_elements = interface_element.xpath(".//*[local-name()='abstractionType']")
        if abstraction_type_elements:
            abstraction_type = _vlnv_from_attributes(
                typing.cast(etree._Element, abstraction_type_elements[0])
            )
    return IpxactInterfaceSummary(
        name=_text(interface_element, "name"),
        mode=_extract_mode(interface_element),
        bus_type=bus_type,
        abstraction_type=abstraction_type,
        port_maps=_extract_port_maps(interface_element),
    )


def extract_ipxact_summary(file_path: str, xml_bytes: bytes) -> IpxactComponentSummary:
    """Parse XML bytes and return a namespace-tolerant component summary."""
    diagnostics: list[Diagnostic] = []
    try:
        root = etree.fromstring(xml_bytes)
    except Exception as exc:
        return IpxactComponentSummary(
            file_path=file_path,
            diagnostics=[
                Diagnostic(
                    severity="error",
                    source=file_path,
                    message=f"Failed to parse IP-XACT XML: {exc}",
                )
            ],
        )

    component = _vlnv_from_children(root)
    missing: list[str] = []
    for name, value in component.model_dump().items():
        if not value:
            missing.append(name)
    if missing:
        diagnostics.append(
            Diagnostic(
                severity="warning",
                source=file_path,
                message="Missing component VLNV fields: " + ", ".join(missing),
            )
        )

    interface_nodes = root.xpath(".//*[local-name()='busInterfaces']/*[local-name()='busInterface']")
    interfaces: list[IpxactInterfaceSummary] = []
    for interface_node in interface_nodes:
        interfaces.append(_extract_interface(typing.cast(etree._Element, interface_node)))
    if not interfaces:
        diagnostics.append(
            Diagnostic(
                severity="warning",
                source=file_path,
                message="No IP-XACT bus interfaces found.",
            )
        )

    return IpxactComponentSummary(
        file_path=file_path,
        component=component,
        interfaces=interfaces,
        diagnostics=diagnostics,
    )
