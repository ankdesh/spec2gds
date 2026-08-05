"""Extract hardware structure from tables and emit narrow V1 IP-XACT."""

from __future__ import annotations

import json
import re
from collections import defaultdict
from typing import Literal, Protocol, Sequence

import lxml.etree as etree
import pydantic
from spec2gds_runtime import StructuredLogger

from spec2gds.agent_spec.spec_format import ipxact
from spec2gds.agent_spec.spec_format.archive import SpecPackage
from spec2gds.agent_spec.spec_format.models import DocumentEntry

DEFAULT_OPENAI_MODEL = "gpt-5.6-sol"
_XML_NAMESPACE = "http://www.w3.org/XML/1998/namespace"


class _ExtractionModel(pydantic.BaseModel):
    """Strict base for OpenAI Structured Outputs."""

    model_config = pydantic.ConfigDict(extra="forbid", frozen=True)


class ExtractedPort(_ExtractionModel):
    """One physical component port explicitly supported by source evidence."""

    name: str
    direction: Literal["in", "out", "inout"]
    width: int = pydantic.Field(default=1, ge=1, le=1_048_576)
    description: str = ""

    @pydantic.field_validator("name")
    @classmethod
    def _name_not_blank(cls, value: str) -> str:
        value = value.strip()
        if not value:
            raise ValueError("Port names cannot be blank.")
        return value


class ExtractedPortMap(_ExtractionModel):
    """A logical protocol signal mapped to a physical component port."""

    logical_port: str
    physical_port: str


class ExtractedBusInterface(_ExtractionModel):
    """One formal protocol interface described by the source tables."""

    name: str
    bus_name: str
    role: Literal["initiator", "target"]
    port_maps: list[ExtractedPortMap] = pydantic.Field(min_length=1)


class HardwareTableExtraction(_ExtractionModel):
    """Structured hardware facts extracted from all candidate tables."""

    component_name: str = ""
    ports: list[ExtractedPort] = pydantic.Field(default_factory=list)
    bus_interfaces: list[ExtractedBusInterface] = pydantic.Field(default_factory=list)
    notes: list[str] = pydantic.Field(default_factory=list)


class HardwareTableEnricher(Protocol):
    """Boundary for optional table-to-hardware extraction providers."""

    model: str

    def extract(
        self,
        tables: Sequence[Sequence[Sequence[str]]],
        *,
        document_title: str,
    ) -> HardwareTableExtraction:
        """Return source-grounded physical ports and formal interfaces."""


_SYSTEM_PROMPT = """Extract hardware interface facts from document tables.
Use only facts explicitly present in the supplied evidence.
Return physical ports only when name and direction are supported.
Convert ranges such as [31:0] to width 32 and keep the base port name.
Create a bus interface only when protocol membership and initiator/target role
are explicit. Every returned bus interface must have at least one port map, and
every port map must reference a returned physical port. Omit an interface when
there are no explicit physical-to-logical signal mappings.
Put ambiguity or omitted unsupported information in notes. Do not guess."""


class OpenAIHardwareTableEnricher:
    """Use OpenAI Responses API Structured Outputs for table extraction."""

    def __init__(
        self,
        *,
        model: str = DEFAULT_OPENAI_MODEL,
        client: object | None = None,
        max_evidence_chars: int = 120_000,
        logger: StructuredLogger | None = None,
    ) -> None:
        if not model:
            raise ValueError("An OpenAI model is required.")
        self.model = model
        self._client = client
        self.max_evidence_chars = max_evidence_chars
        self.logger = logger

    @property
    def client(self):
        """Lazily create the official client so offline imports need no key."""
        if self._client is None:
            try:
                from openai import OpenAI
            except ModuleNotFoundError as exc:
                raise RuntimeError(
                    "The OpenAI SDK is not installed. Run `uv sync --extra document-import`."
                ) from exc

            self._client = OpenAI()
        return self._client

    def extract(
        self,
        tables: Sequence[Sequence[Sequence[str]]],
        *,
        document_title: str,
    ) -> HardwareTableExtraction:
        """Extract typed facts with one bounded Responses API request."""
        evidence = {
            "document_title": document_title,
            "tables": [
                {"table_id": f"table_{index:04d}", "rows": [list(row) for row in rows]}
                for index, rows in enumerate(tables, start=1)
            ],
        }
        encoded = json.dumps(evidence, ensure_ascii=False, separators=(",", ":"))
        if len(encoded) > self.max_evidence_chars:
            raise ValueError(
                f"Table evidence is {len(encoded)} characters; limit is {self.max_evidence_chars}. "
                "Reduce the source document or raise max_evidence_chars programmatically."
            )
        call = {
            "model": self.model,
            "reasoning": {"effort": "low"},
            "store": False,
            "input": [
                {"role": "system", "content": _SYSTEM_PROMPT},
                {"role": "user", "content": encoded},
            ],
            "text_format": HardwareTableExtraction.__name__,
        }
        if self.logger:
            self.logger.event(
                "openai", "request", "Sending document extraction request to OpenAI",
                details=call,
            )
        response = self.client.responses.parse(
            model=self.model,
            reasoning={"effort": "low"},
            store=False,
            input=[
                {"role": "system", "content": _SYSTEM_PROMPT},
                {"role": "user", "content": encoded},
            ],
            text_format=HardwareTableExtraction,
        )
        if self.logger:
            self.logger.event(
                "openai", "response", "Received document extraction response from OpenAI",
                details=response,
            )
        extraction = response.output_parsed
        if extraction is None:
            raise RuntimeError("OpenAI returned no parsed hardware extraction.")
        return HardwareTableExtraction.model_validate(extraction)


def xml_identifier(value: str) -> str:
    """Normalize external names to the project's XML-ID-compatible grammar."""
    value = re.sub(r"[^A-Za-z0-9_.-]+", "_", value).strip("_.-") or "entity"
    return value if value[0].isalpha() or value[0] == "_" else f"e_{value}"


def _opposite(direction: str) -> str:
    """Return a peer-facing wire direction."""
    return {"in": "out", "out": "in"}.get(direction, "inout")


def _identity(root: etree._Element, values: tuple[str, str, str, str]) -> None:
    """Append schema-ordered IP-XACT VLNV children."""
    for name, value in zip(("vendor", "library", "name", "version"), values, strict=True):
        etree.SubElement(root, etree.QName(ipxact.IPXACT_NAMESPACE, name)).text = value


def _new_root(kind: str, entity_id: str) -> etree._Element:
    """Create one namespaced IP-XACT document root with stable identity."""
    root = etree.Element(
        etree.QName(ipxact.IPXACT_NAMESPACE, kind),
        nsmap={"ipxact": ipxact.IPXACT_NAMESPACE},
    )
    root.set(etree.QName(_XML_NAMESPACE, "id"), entity_id)
    return root


def _normalized_extraction(extraction: HardwareTableExtraction) -> HardwareTableExtraction:
    """Normalize names and reject unresolved or conflicting source facts."""
    ports = [
        port.model_copy(update={"name": xml_identifier(port.name)})
        for port in extraction.ports
    ]
    port_names = [port.name for port in ports]
    if len(port_names) != len(set(port_names)):
        raise ValueError("Extracted physical port names are not unique after normalization.")
    known_ports = set(port_names)

    interfaces: list[ExtractedBusInterface] = []
    interface_names: set[str] = set()
    for interface in extraction.bus_interfaces:
        if not interface.port_maps:
            raise ValueError(f"Interface {interface.name!r} has no explicit port maps.")
        normalized_maps = [
            mapping.model_copy(
                update={
                    "logical_port": xml_identifier(mapping.logical_port),
                    "physical_port": xml_identifier(mapping.physical_port),
                }
            )
            for mapping in interface.port_maps
        ]
        missing = sorted({mapping.physical_port for mapping in normalized_maps} - known_ports)
        if missing:
            raise ValueError(
                f"Interface {interface.name!r} maps unknown physical ports: {', '.join(missing)}"
            )
        logical_names = [mapping.logical_port for mapping in normalized_maps]
        if len(logical_names) != len(set(logical_names)):
            raise ValueError(
                f"Interface {interface.name!r} maps a logical port more than once."
            )
        name = xml_identifier(interface.name)
        if name in interface_names:
            raise ValueError(f"Extracted bus interface name is duplicated: {name}")
        interface_names.add(name)
        interfaces.append(
            interface.model_copy(
                update={
                    "name": name,
                    "bus_name": xml_identifier(interface.bus_name),
                    "port_maps": normalized_maps,
                }
            )
        )
    return extraction.model_copy(
        update={
            "component_name": xml_identifier(extraction.component_name) if extraction.component_name else "",
            "ports": ports,
            "bus_interfaces": interfaces,
        }
    )


def _bus_xml(vlnv: tuple[str, str, str, str]) -> bytes:
    """Build a minimal direct-connection bus definition."""
    root = _new_root("busDefinition", f"bus_{xml_identifier('_'.join(vlnv))}")
    _identity(root, vlnv)
    etree.SubElement(root, etree.QName(ipxact.IPXACT_NAMESPACE, "directConnection")).text = "true"
    etree.SubElement(root, etree.QName(ipxact.IPXACT_NAMESPACE, "isAddressable")).text = "false"
    return etree.tostring(root, encoding="UTF-8", xml_declaration=True)


def _abstraction_xml(
    bus_vlnv: tuple[str, str, str, str],
    abstraction_vlnv: tuple[str, str, str, str],
    directions: dict[str, tuple[str, str]],
) -> bytes:
    """Build the logical wire roles required by extracted port maps."""
    root = _new_root(
        "abstractionDefinition",
        f"abstraction_{xml_identifier('_'.join(abstraction_vlnv))}",
    )
    _identity(root, abstraction_vlnv)
    bus_type = etree.SubElement(root, etree.QName(ipxact.IPXACT_NAMESPACE, "busType"))
    for name, value in zip(("vendor", "library", "name", "version"), bus_vlnv, strict=True):
        bus_type.set(name, value)
    ports = etree.SubElement(root, etree.QName(ipxact.IPXACT_NAMESPACE, "ports"))
    for logical_name, (initiator_direction, target_direction) in sorted(directions.items()):
        port = etree.SubElement(ports, etree.QName(ipxact.IPXACT_NAMESPACE, "port"))
        etree.SubElement(port, etree.QName(ipxact.IPXACT_NAMESPACE, "logicalName")).text = logical_name
        wire = etree.SubElement(port, etree.QName(ipxact.IPXACT_NAMESPACE, "wire"))
        on_initiator = etree.SubElement(wire, etree.QName(ipxact.IPXACT_NAMESPACE, "onInitiator"))
        etree.SubElement(on_initiator, etree.QName(ipxact.IPXACT_NAMESPACE, "direction")).text = (
            initiator_direction
        )
        on_target = etree.SubElement(wire, etree.QName(ipxact.IPXACT_NAMESPACE, "onTarget"))
        etree.SubElement(on_target, etree.QName(ipxact.IPXACT_NAMESPACE, "direction")).text = target_direction
    return etree.tostring(root, encoding="UTF-8", xml_declaration=True)


def _component_xml(
    extraction: HardwareTableExtraction,
    *,
    vendor: str,
    library: str,
    name: str,
    version: str,
) -> bytes:
    """Build a narrow V1 component from normalized extraction facts."""
    root = _new_root(
        "component",
        f"component_{xml_identifier('_'.join((vendor, library, name, version)))}",
    )
    _identity(root, (vendor, library, name, version))
    if extraction.bus_interfaces:
        interfaces = etree.SubElement(root, etree.QName(ipxact.IPXACT_NAMESPACE, "busInterfaces"))
        for interface in extraction.bus_interfaces:
            bus = etree.SubElement(interfaces, etree.QName(ipxact.IPXACT_NAMESPACE, "busInterface"))
            etree.SubElement(bus, etree.QName(ipxact.IPXACT_NAMESPACE, "name")).text = interface.name
            bus_type = etree.SubElement(bus, etree.QName(ipxact.IPXACT_NAMESPACE, "busType"))
            bus_vlnv = (vendor, library, interface.bus_name, version)
            for field, value in zip(("vendor", "library", "name", "version"), bus_vlnv, strict=True):
                bus_type.set(field, value)
            abstraction_types = etree.SubElement(
                bus, etree.QName(ipxact.IPXACT_NAMESPACE, "abstractionTypes")
            )
            abstraction_type = etree.SubElement(
                abstraction_types, etree.QName(ipxact.IPXACT_NAMESPACE, "abstractionType")
            )
            abstraction_ref = etree.SubElement(
                abstraction_type, etree.QName(ipxact.IPXACT_NAMESPACE, "abstractionRef")
            )
            abstraction_vlnv = (vendor, library, f"{interface.bus_name}_wire", version)
            for field, value in zip(
                ("vendor", "library", "name", "version"), abstraction_vlnv, strict=True
            ):
                abstraction_ref.set(field, value)
            maps = etree.SubElement(
                abstraction_type, etree.QName(ipxact.IPXACT_NAMESPACE, "portMaps")
            )
            for mapping in interface.port_maps:
                port_map = etree.SubElement(maps, etree.QName(ipxact.IPXACT_NAMESPACE, "portMap"))
                logical = etree.SubElement(
                    port_map, etree.QName(ipxact.IPXACT_NAMESPACE, "logicalPort")
                )
                etree.SubElement(logical, etree.QName(ipxact.IPXACT_NAMESPACE, "name")).text = (
                    mapping.logical_port
                )
                physical = etree.SubElement(
                    port_map, etree.QName(ipxact.IPXACT_NAMESPACE, "physicalPort")
                )
                etree.SubElement(physical, etree.QName(ipxact.IPXACT_NAMESPACE, "name")).text = (
                    mapping.physical_port
                )
            etree.SubElement(bus, etree.QName(ipxact.IPXACT_NAMESPACE, interface.role))

    model = etree.SubElement(root, etree.QName(ipxact.IPXACT_NAMESPACE, "model"))
    ports = etree.SubElement(model, etree.QName(ipxact.IPXACT_NAMESPACE, "ports"))
    for extracted_port in extraction.ports:
        port = etree.SubElement(ports, etree.QName(ipxact.IPXACT_NAMESPACE, "port"))
        etree.SubElement(port, etree.QName(ipxact.IPXACT_NAMESPACE, "name")).text = extracted_port.name
        wire = etree.SubElement(port, etree.QName(ipxact.IPXACT_NAMESPACE, "wire"))
        etree.SubElement(wire, etree.QName(ipxact.IPXACT_NAMESPACE, "direction")).text = (
            extracted_port.direction
        )
        if extracted_port.width > 1:
            vectors = etree.SubElement(wire, etree.QName(ipxact.IPXACT_NAMESPACE, "vectors"))
            vector = etree.SubElement(vectors, etree.QName(ipxact.IPXACT_NAMESPACE, "vector"))
            etree.SubElement(vector, etree.QName(ipxact.IPXACT_NAMESPACE, "left")).text = str(
                extracted_port.width - 1
            )
            etree.SubElement(vector, etree.QName(ipxact.IPXACT_NAMESPACE, "right")).text = "0"
    return etree.tostring(root, encoding="UTF-8", xml_declaration=True)


def add_extracted_ipxact(
    package: SpecPackage,
    extraction: HardwareTableExtraction,
    *,
    vendor: str,
    library: str,
    component_name: str,
    version: str,
) -> DocumentEntry | None:
    """Add generated bus, abstraction, and component documents to a package."""
    extraction = _normalized_extraction(extraction)
    if not extraction.ports:
        return None
    name = xml_identifier(component_name) if component_name else extraction.component_name
    name = name or "imported_component"
    port_directions = {port.name: port.direction for port in extraction.ports}
    protocol_directions: dict[str, dict[str, tuple[str, str]]] = defaultdict(dict)
    for interface in extraction.bus_interfaces:
        for mapping in interface.port_maps:
            physical_direction = port_directions[mapping.physical_port]
            pair = (
                (physical_direction, _opposite(physical_direction))
                if interface.role == "initiator"
                else (_opposite(physical_direction), physical_direction)
            )
            existing = protocol_directions[interface.bus_name].get(mapping.logical_port)
            if existing is not None and existing != pair:
                raise ValueError(
                    f"Conflicting directions for logical port {mapping.logical_port!r} "
                    f"on bus {interface.bus_name!r}."
                )
            protocol_directions[interface.bus_name][mapping.logical_port] = pair

    for bus_name, directions in sorted(protocol_directions.items()):
        bus_vlnv = (vendor, library, bus_name, version)
        abstraction_vlnv = (vendor, library, f"{bus_name}_wire", version)
        package.add_document("bus_definition", _bus_xml(bus_vlnv))
        package.add_document(
            "abstraction_definition",
            _abstraction_xml(bus_vlnv, abstraction_vlnv, directions),
        )
    return package.add_document(
        "component",
        _component_xml(
            extraction,
            vendor=vendor,
            library=library,
            name=name,
            version=version,
        ),
    )
