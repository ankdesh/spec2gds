"""Immutable semantic source graph for the V1 IP-XACT package profile."""

from __future__ import annotations

from dataclasses import dataclass
import json
from types import MappingProxyType
import typing

import lxml.etree as etree

from spec2gds.agent_spec.spec_format import ipxact
from spec2gds.agent_spec.spec_format.archive import SpecPackage, SpecValidationError
from spec2gds.agent_spec.spec_format.models import (
    AssetEntry,
    DocumentKind,
    EntityRef,
    NarrativeBlock,
    NarrativeDocument,
    SpecManifest,
)


_INTERFACE_ROLES = ("initiator", "target", "system", "monitor")


def _text(node: etree._Element, child_name: str) -> str:
    """Return direct child text without exposing XML nodes to callers."""
    values = node.xpath(f"./*[local-name()='{child_name}']/text()")
    return str(values[0]).strip() if values else ""


def _vlnv(node: etree._Element | None) -> str:
    """Convert an IP-XACT library reference node to the project VLNV form."""
    if node is None:
        return ""
    values = [node.get(name, "") for name in ("vendor", "library", "name", "version")]
    return ":".join(values) if all(values) else ""


def _first(nodes: list[typing.Any]) -> etree._Element | None:
    """Return the first XPath element result, if present."""
    return typing.cast(etree._Element, nodes[0]) if nodes else None


def _canonical_json(model: typing.Any) -> str:
    """Snapshot a persisted model so callers cannot mutate a revision in place."""
    return json.dumps(model.model_dump(mode="json"), ensure_ascii=False, sort_keys=True, separators=(",", ":"))


@dataclass(frozen=True)
class PortIR:
    """One explicitly classified component port in the editor profile."""

    name: str
    direction: str
    style: typing.Literal["wire", "transactional", "structured"]
    width: int | str | None = None
    initiative: str = ""
    bus_width: str = ""


@dataclass(frozen=True)
class InterfaceIR:
    """A component bus interface and its canonical compatibility identity."""

    name: str
    bus_vlnv: str
    abstraction_vlnv: str
    role: str
    port_maps: tuple[tuple[str, str], ...] = ()


@dataclass(frozen=True)
class ComponentIR:
    """Semantic component definition derived from one embedded IP-XACT document."""

    ref: EntityRef
    vlnv: str
    ports: tuple[PortIR, ...]
    interfaces: tuple[InterfaceIR, ...]


@dataclass(frozen=True)
class InstanceIR:
    """A component instance within an IP-XACT design."""

    name: str
    component_vlnv: str


@dataclass(frozen=True)
class InterfaceEndpointIR:
    """One component bus-interface endpoint in an interconnection."""

    instance_name: str
    interface_name: str


@dataclass(frozen=True)
class PortEndpointIR:
    """One instance-port endpoint in an ad-hoc connection."""

    instance_name: str
    port_name: str


@dataclass(frozen=True)
class ConnectionIR:
    """An interface or ad-hoc port connection in a design."""

    name: str
    kind: typing.Literal["interface", "ad_hoc"]
    interface_endpoints: tuple[InterfaceEndpointIR, ...] = ()
    port_endpoints: tuple[PortEndpointIR, ...] = ()
    external_ports: tuple[str, ...] = ()
    hierarchy_interfaces: tuple[str, ...] = ()


@dataclass(frozen=True)
class DesignIR:
    """Semantic design definition with its local instances and connections."""

    ref: EntityRef
    vlnv: str
    instances: tuple[InstanceIR, ...]
    connections: tuple[ConnectionIR, ...]


@dataclass(frozen=True)
class BusDefinitionIR:
    """A bus-definition identity available to component interfaces."""

    ref: EntityRef
    vlnv: str


@dataclass(frozen=True)
class AbstractionDefinitionIR:
    """An abstraction-definition identity available to component interfaces."""

    ref: EntityRef
    vlnv: str
    bus_vlnv: str
    logical_ports: tuple[str, ...] = ()


@dataclass(frozen=True)
class AnnotationIR:
    """An accepted annotation payload owned by a manifest schema prefix."""

    path: str
    data: bytes


SemanticEntity = typing.Union[
    ComponentIR,
    DesignIR,
    BusDefinitionIR,
    AbstractionDefinitionIR,
    NarrativeBlock,
    AssetEntry,
]


@dataclass(frozen=True)
class SpecRevision:
    """Immutable, validated semantic snapshot of one V1 source package."""

    document_id: str
    source_revision_hash: str
    components: tuple[ComponentIR, ...]
    designs: tuple[DesignIR, ...]
    bus_definitions: tuple[BusDefinitionIR, ...]
    abstraction_definitions: tuple[AbstractionDefinitionIR, ...]
    assets: tuple[AssetEntry, ...]
    annotations: tuple[AnnotationIR, ...]
    diagnostics: tuple[str, ...]
    _manifest_json: str
    _narrative_json: str
    _files: typing.Mapping[str, bytes]

    @classmethod
    def from_package(cls, package: SpecPackage) -> "SpecRevision":
        """Load and validate a package into a source-only immutable semantic graph."""
        package.require_valid()
        manifest = SpecManifest.model_validate_json(_canonical_json(package.manifest))
        narrative = NarrativeDocument.model_validate_json(_canonical_json(package.narrative))
        documents = {entry.entity_id: entry for entry in manifest.documents}
        components: list[ComponentIR] = []
        designs: list[DesignIR] = []
        buses: list[BusDefinitionIR] = []
        abstractions: list[AbstractionDefinitionIR] = []
        for entry in manifest.documents:
            data = package.files[entry.path]
            root = ipxact.parse_xml(data)
            ref = EntityRef(document_id=manifest.document_id, entity_id=entry.entity_id, entity_kind=entry.kind)
            if entry.kind == "component":
                components.append(_component_ir(ref, entry.vlnv, root))
            elif entry.kind == "design":
                designs.append(_design_ir(ref, entry.vlnv, root))
            elif entry.kind == "bus_definition":
                buses.append(BusDefinitionIR(ref=ref, vlnv=entry.vlnv))
            else:
                bus_type = _first(root.xpath("./*[local-name()='busType']"))
                logical_ports = tuple(
                    _text(port, "logicalName")
                    for port in root.xpath("./*[local-name()='ports']/*[local-name()='port']")
                )
                abstractions.append(
                    AbstractionDefinitionIR(ref=ref, vlnv=entry.vlnv, bus_vlnv=_vlnv(bus_type), logical_ports=logical_ports)
                )

        diagnostics = _semantic_diagnostics(
            manifest,
            narrative,
            tuple(components),
            tuple(designs),
            tuple(buses),
            tuple(abstractions),
        )
        if diagnostics:
            raise SpecValidationError(diagnostics)
        return cls(
            document_id=manifest.document_id,
            source_revision_hash=package.source_hash(),
            components=tuple(components),
            designs=tuple(designs),
            bus_definitions=tuple(buses),
            abstraction_definitions=tuple(abstractions),
            assets=tuple(AssetEntry.model_validate(asset.model_dump(mode="json")) for asset in manifest.assets),
            annotations=tuple(
                AnnotationIR(path=path, data=bytes(data))
                for path, data in sorted(package.files.items())
                if path.startswith("annotations/")
            ),
            diagnostics=(),
            _manifest_json=_canonical_json(manifest),
            _narrative_json=_canonical_json(narrative),
            _files=MappingProxyType({path: bytes(data) for path, data in package.files.items()}),
        )

    @classmethod
    def load(cls, path: str) -> "SpecRevision":
        """Load a V1 package file into an immutable validated revision."""
        return cls.from_package(SpecPackage.load(path))

    @property
    def manifest(self) -> SpecManifest:
        """Return a defensive typed manifest copy for display or serialization."""
        return SpecManifest.model_validate_json(self._manifest_json)

    @property
    def narrative(self) -> NarrativeDocument:
        """Return a defensive typed narrative copy for display or serialization."""
        return NarrativeDocument.model_validate_json(self._narrative_json)

    def to_package(self) -> SpecPackage:
        """Materialize a mutable package only for transaction working copies or saving."""
        return SpecPackage(
            manifest=self.manifest,
            narrative=self.narrative,
            files={path: bytes(data) for path, data in self._files.items()},
        )

    def save(self, path: str) -> None:
        """Serialize this exact source revision through the deterministic package writer."""
        self.to_package().save(path)

    def resolve(self, ref: EntityRef) -> SemanticEntity:
        """Resolve a stable entity reference or raise a precise lookup error."""
        if ref.document_id != self.document_id:
            raise KeyError(f"Entity reference belongs to another document: {ref.document_id}")
        collections: dict[str, tuple[typing.Any, ...]] = {
            "component": self.components,
            "design": self.designs,
            "bus_definition": self.bus_definitions,
            "abstraction_definition": self.abstraction_definitions,
        }
        if ref.entity_kind in collections:
            for entity in collections[ref.entity_kind]:
                if entity.ref.entity_id == ref.entity_id:
                    return entity
        elif ref.entity_kind == "asset":
            for asset in self.assets:
                if asset.asset_id == ref.entity_id:
                    return AssetEntry.model_validate(asset.model_dump(mode="json"))
        elif ref.entity_kind == "narrative_block":
            for block in _walk_blocks(self.narrative.blocks):
                if block.block_id == ref.entity_id:
                    return block
        raise KeyError(f"Unknown {ref.entity_kind} entity id: {ref.entity_id}")

    def by_vlnv(self, kind: DocumentKind, vlnv: str) -> ComponentIR | DesignIR | BusDefinitionIR | AbstractionDefinitionIR:
        """Resolve one IP-XACT source document by its kind and VLNV."""
        collections: dict[str, tuple[typing.Any, ...]] = {
            "component": self.components,
            "design": self.designs,
            "bus_definition": self.bus_definitions,
            "abstraction_definition": self.abstraction_definitions,
        }
        for entity in collections[kind]:
            if entity.vlnv == vlnv:
                return entity
        raise KeyError(f"Unknown {kind} VLNV: {vlnv}")

    def document_by_vlnv(self, kind: DocumentKind, vlnv: str) -> ComponentIR | DesignIR | BusDefinitionIR | AbstractionDefinitionIR:
        """Publicly named alias for VLNV document lookup."""
        return self.by_vlnv(kind, vlnv)

    def instances(self, design: DesignIR | EntityRef) -> tuple[InstanceIR, ...]:
        """Return the instances declared by a resolved design."""
        entity = self.resolve(design) if isinstance(design, EntityRef) else design
        if not isinstance(entity, DesignIR):
            raise TypeError("Instance queries require a design reference.")
        return entity.instances

    def interfaces(self, component: ComponentIR | EntityRef) -> tuple[InterfaceIR, ...]:
        """Return the interfaces declared by a resolved component."""
        entity = self.resolve(component) if isinstance(component, EntityRef) else component
        if not isinstance(entity, ComponentIR):
            raise TypeError("Interface queries require a component reference.")
        return entity.interfaces

    def connections(self, design: DesignIR | EntityRef) -> tuple[ConnectionIR, ...]:
        """Return the interface and ad-hoc connections declared by a design."""
        entity = self.resolve(design) if isinstance(design, EntityRef) else design
        if not isinstance(entity, DesignIR):
            raise TypeError("Connection queries require a design reference.")
        return entity.connections

    def entry_designs(self) -> tuple[DesignIR, ...]:
        """Return the explicit top-level designs in manifest order."""
        return tuple(typing.cast(DesignIR, self.resolve(reference)) for reference in self.manifest.entry_designs)

    def internal_design(self, component: ComponentIR | EntityRef) -> DesignIR | None:
        """Resolve a component's optional internal design."""
        component_ref = component.ref if isinstance(component, ComponentIR) else component
        for composition in self.manifest.component_compositions:
            if composition.component.entity_id == component_ref.entity_id:
                return typing.cast(DesignIR, self.resolve(composition.internal_design))
        return None

    def narrative_blocks_for(self, entity: EntityRef) -> tuple[NarrativeBlock, ...]:
        """Return all narrative blocks that directly link to an entity."""
        matches: list[NarrativeBlock] = []
        for block in _walk_blocks(self.narrative.blocks):
            refs = [*block.entity_refs, *(inline.entity_ref for inline in block.inlines if inline.entity_ref)]
            if any(reference == entity for reference in refs):
                matches.append(block)
        return tuple(matches)

    def dependency_closure(self, target: ComponentIR | DesignIR | EntityRef) -> tuple[EntityRef, ...]:
        """Return stable source references reachable from a component or design."""
        entity = self.resolve(target) if isinstance(target, EntityRef) else target
        if not isinstance(entity, (ComponentIR, DesignIR)):
            raise TypeError("Dependency closure is defined only for components and designs.")
        seen: dict[tuple[str, str, str], EntityRef] = {}

        def key(reference: EntityRef) -> tuple[str, str, str]:
            """Build a stable, kind-sensitive traversal key."""
            return (reference.document_id, reference.entity_kind, reference.entity_id)

        def visit_component(component: ComponentIR) -> None:
            """Collect a component, its protocols, and owned internal design."""
            if key(component.ref) in seen:
                return
            seen[key(component.ref)] = component.ref
            for interface in component.interfaces:
                for kind, vlnv in (("bus_definition", interface.bus_vlnv), ("abstraction_definition", interface.abstraction_vlnv)):
                    if vlnv:
                        try:
                            candidate = self.by_vlnv(typing.cast(DocumentKind, kind), vlnv)
                            seen[key(candidate.ref)] = candidate.ref
                        except KeyError:
                            pass
            internal = self.internal_design(component)
            if internal is not None:
                visit_design(internal)

        def visit_design(design: DesignIR) -> None:
            """Collect a design and recursively resolve instantiated components."""
            if key(design.ref) in seen:
                return
            seen[key(design.ref)] = design.ref
            for instance in design.instances:
                try:
                    visit_component(typing.cast(ComponentIR, self.by_vlnv("component", instance.component_vlnv)))
                except KeyError:
                    pass

        if isinstance(entity, ComponentIR):
            visit_component(entity)
        else:
            visit_design(entity)
        return tuple(sorted(seen.values(), key=lambda ref: (ref.entity_kind, ref.entity_id)))


def _component_ir(ref: EntityRef, vlnv: str, root: etree._Element) -> ComponentIR:
    """Project one validated component XML document into immutable SpecIR."""
    ports: list[PortIR] = []
    for port in root.xpath("./*[local-name()='model']/*[local-name()='ports']/*[local-name()='port']"):
        wire = _first(port.xpath("./*[local-name()='wire']"))
        transactional = _first(port.xpath("./*[local-name()='transactional']"))
        structured = _first(port.xpath("./*[local-name()='structured']"))
        style: typing.Literal["wire", "transactional", "structured"]
        style = "wire" if wire is not None else "transactional" if transactional is not None else "structured"
        width: int | str | None = 1 if wire is not None else None
        direction = ""
        initiative = ""
        bus_width = ""
        if wire is not None:
            direction = _text(wire, "direction")
            style_node = wire
            vectors = style_node.xpath("./*[local-name()='vectors']/*[local-name()='vector']")
            if len(vectors) == 1:
                left = _text(vectors[0], "left")
                right = _text(vectors[0], "right")
                width = f"[{left}:{right}]" if left and right else None
            elif len(vectors) > 1:
                width = None
        elif transactional is not None:
            initiative = _text(transactional, "initiative")
            bus_width = _text(transactional, "busWidth")
        elif structured is not None:
            struct = _first(structured.xpath("./*[local-name()='struct']"))
            direction = (struct.get("direction") or "").strip() if struct is not None else ""
        ports.append(
            PortIR(
                name=_text(port, "name"),
                direction=direction,
                style=style,
                width=width,
                initiative=initiative,
                bus_width=bus_width,
            )
        )
    interfaces: list[InterfaceIR] = []
    for interface in root.xpath("./*[local-name()='busInterfaces']/*[local-name()='busInterface']"):
        bus = _first(interface.xpath("./*[local-name()='busType']"))
        abstraction = _first(interface.xpath("./*[local-name()='abstractionTypes']/*[local-name()='abstractionType']/*[local-name()='abstractionRef']"))
        role = next((name for name in _INTERFACE_ROLES if interface.xpath(f"./*[local-name()='{name}']")), "")
        port_maps: list[tuple[str, str]] = []
        for port_map in interface.xpath("./*[local-name()='abstractionTypes']/*[local-name()='abstractionType']/*[local-name()='portMaps']/*[local-name()='portMap']"):
            logical = _first(port_map.xpath("./*[local-name()='logicalPort']/*[local-name()='name']"))
            physical = _first(port_map.xpath("./*[local-name()='physicalPort']/*[local-name()='name']"))
            port_maps.append(((logical.text or "").strip() if logical is not None else "", (physical.text or "").strip() if physical is not None else ""))
        interfaces.append(InterfaceIR(_text(interface, "name"), _vlnv(bus), _vlnv(abstraction), role, tuple(port_maps)))
    return ComponentIR(ref=ref, vlnv=vlnv, ports=tuple(ports), interfaces=tuple(interfaces))


def _design_ir(ref: EntityRef, vlnv: str, root: etree._Element) -> DesignIR:
    """Project instances and both connection kinds into immutable SpecIR."""
    instances: list[InstanceIR] = []
    for instance in root.xpath("./*[local-name()='componentInstances']/*[local-name()='componentInstance']"):
        component_ref = _first(instance.xpath("./*[local-name()='componentRef']"))
        instances.append(InstanceIR(name=_text(instance, "instanceName"), component_vlnv=_vlnv(component_ref)))
    connections: list[ConnectionIR] = []
    for connection in root.xpath("./*[local-name()='interconnections']/*[local-name()='interconnection']"):
        endpoints = tuple(
            InterfaceEndpointIR(instance_name=node.get("componentInstanceRef", ""), interface_name=node.get("busRef", ""))
            for node in connection.xpath("./*[local-name()='activeInterface']")
        )
        hierarchy = tuple(node.get("busRef", "") for node in connection.xpath("./*[local-name()='hierInterface']"))
        connections.append(ConnectionIR(name=_text(connection, "name"), kind="interface", interface_endpoints=endpoints, hierarchy_interfaces=hierarchy))
    for connection in root.xpath("./*[local-name()='adHocConnections']/*[local-name()='adHocConnection']"):
        endpoints = tuple(
            PortEndpointIR(instance_name=node.get("componentInstanceRef", ""), port_name=node.get("portRef", ""))
            for node in connection.xpath("./*[local-name()='portReferences']/*[local-name()='internalPortReference']")
        )
        external = tuple(node.get("portRef", "") for node in connection.xpath("./*[local-name()='portReferences']/*[local-name()='externalPortReference']"))
        connections.append(ConnectionIR(name=_text(connection, "name"), kind="ad_hoc", port_endpoints=endpoints, external_ports=external))
    return DesignIR(ref=ref, vlnv=vlnv, instances=tuple(instances), connections=tuple(connections))


def _semantic_diagnostics(
    manifest: SpecManifest,
    narrative: NarrativeDocument,
    components: tuple[ComponentIR, ...],
    designs: tuple[DesignIR, ...],
    buses: tuple[BusDefinitionIR, ...],
    abstractions: tuple[AbstractionDefinitionIR, ...],
) -> list[str]:
    """Validate graph-only rules that XSD/package validation cannot express."""
    diagnostics: list[str] = []
    del narrative  # Package validation owns narrative reference checking.
    component_by_vlnv = {component.vlnv: component for component in components}
    design_by_id = {design.ref.entity_id: design for design in designs}
    bus_vlnvs = {bus.vlnv for bus in buses}
    abstraction_by_vlnv = {abstraction.vlnv: abstraction for abstraction in abstractions}
    owner_by_design = {mapping.internal_design.entity_id: mapping.component.entity_id for mapping in manifest.component_compositions}

    for component in components:
        port_names = [port.name for port in component.ports]
        interface_names = [interface.name for interface in component.interfaces]
        if len(port_names) != len(set(port_names)):
            diagnostics.append(f"Component {component.vlnv} contains duplicate port names.")
        if len(interface_names) != len(set(interface_names)):
            diagnostics.append(f"Component {component.vlnv} contains duplicate interface names.")
        for interface in component.interfaces:
            if interface.bus_vlnv not in bus_vlnvs:
                diagnostics.append(f"Component {component.vlnv} interface {interface.name} references an unknown bus definition.")
            abstraction = abstraction_by_vlnv.get(interface.abstraction_vlnv)
            if abstraction is None:
                diagnostics.append(f"Component {component.vlnv} interface {interface.name} references an unknown abstraction definition.")
            elif abstraction.bus_vlnv != interface.bus_vlnv:
                diagnostics.append(f"Component {component.vlnv} interface {interface.name} uses an abstraction for another bus definition.")
            else:
                component_ports = {port.name for port in component.ports}
                logical_ports = set(abstraction.logical_ports)
                physical_names = [physical for _, physical in interface.port_maps]
                logical_names = [logical for logical, _ in interface.port_maps]
                if len(physical_names) != len(set(physical_names)) or len(logical_names) != len(set(logical_names)):
                    diagnostics.append(f"Component {component.vlnv} interface {interface.name} has duplicate port mappings.")
                if any(physical not in component_ports for physical in physical_names):
                    diagnostics.append(f"Component {component.vlnv} interface {interface.name} maps an unknown physical port.")
                if any(logical not in logical_ports for logical in logical_names):
                    diagnostics.append(f"Component {component.vlnv} interface {interface.name} maps an unknown logical port.")

    for design in designs:
        instance_by_name = {instance.name: instance for instance in design.instances}
        if len(instance_by_name) != len(design.instances):
            diagnostics.append(f"Design {design.vlnv} contains duplicate instance names.")
        connection_names = [connection.name for connection in design.connections]
        if len(connection_names) != len(set(connection_names)):
            diagnostics.append(f"Design {design.vlnv} contains duplicate connection names.")
        for instance in design.instances:
            if instance.component_vlnv not in component_by_vlnv:
                diagnostics.append(f"Design {design.vlnv} instance {instance.name} references missing component {instance.component_vlnv}.")
        owner_component = next((component for component in components if owner_by_design.get(design.ref.entity_id) == component.ref.entity_id), None)
        exported_interfaces = {name for connection in design.connections for name in connection.hierarchy_interfaces}
        external_ports = {name for connection in design.connections for name in connection.external_ports}
        if owner_component is not None:
            if exported_interfaces != {interface.name for interface in owner_component.interfaces}:
                diagnostics.append(f"Internal design {design.vlnv} does not match component {owner_component.vlnv} interface boundary.")
            if external_ports != {port.name for port in owner_component.ports}:
                diagnostics.append(f"Internal design {design.vlnv} does not match component {owner_component.vlnv} port boundary.")
        for connection in design.connections:
            if connection.kind == "interface":
                if len(connection.interface_endpoints) < 2:
                    diagnostics.append(f"Design {design.vlnv} connection {connection.name} needs at least two interface endpoints.")
                peers: list[InterfaceIR] = []
                for endpoint in connection.interface_endpoints:
                    instance = instance_by_name.get(endpoint.instance_name)
                    if instance is None:
                        diagnostics.append(f"Design {design.vlnv} connection {connection.name} references missing instance {endpoint.instance_name}.")
                        continue
                    component = component_by_vlnv.get(instance.component_vlnv)
                    interface = next((item for item in component.interfaces if item.name == endpoint.interface_name), None) if component else None
                    if interface is None:
                        diagnostics.append(f"Design {design.vlnv} connection {connection.name} references missing interface {endpoint.interface_name}.")
                    else:
                        peers.append(interface)
                if peers and len({(peer.bus_vlnv, peer.abstraction_vlnv) for peer in peers}) != 1:
                    diagnostics.append(f"Design {design.vlnv} connection {connection.name} has incompatible bus or abstraction definitions.")
                roles = {peer.role for peer in peers}
                if "monitor" in roles or (("initiator" in roles or "target" in roles) and not {"initiator", "target"}.issubset(roles)):
                    diagnostics.append(f"Design {design.vlnv} connection {connection.name} has incompatible interface roles.")
                if peers and len({endpoint.instance_name for endpoint in connection.interface_endpoints}) != len(connection.interface_endpoints):
                    diagnostics.append(f"Design {design.vlnv} connection {connection.name} connects an instance to itself.")
            else:
                if len(connection.port_endpoints) + len(connection.external_ports) < 2:
                    diagnostics.append(f"Design {design.vlnv} connection {connection.name} needs at least two port endpoints.")
                directions: list[str] = []
                for endpoint in connection.port_endpoints:
                    instance = instance_by_name.get(endpoint.instance_name)
                    component = component_by_vlnv.get(instance.component_vlnv) if instance else None
                    port = next((item for item in component.ports if item.name == endpoint.port_name), None) if component else None
                    if instance is None or component is None or port is None:
                        diagnostics.append(f"Design {design.vlnv} connection {connection.name} references missing port endpoint {endpoint.instance_name}.{endpoint.port_name}.")
                    else:
                        directions.append(port.direction)
                if len(directions) >= 2 and (not any(direction in {"out", "inout"} for direction in directions) or not any(direction in {"in", "inout"} for direction in directions)):
                    diagnostics.append(f"Design {design.vlnv} connection {connection.name} has incompatible port directions.")

    composition_by_component = {mapping.component.entity_id: mapping.internal_design.entity_id for mapping in manifest.component_compositions}

    def visit(component_id: str, ancestry: set[str]) -> None:
        """Detect recursive component ownership through internal designs."""
        if component_id in ancestry:
            diagnostics.append(f"Component composition cycle includes {component_id}.")
            return
        internal_design_id = composition_by_component.get(component_id)
        if internal_design_id is None:
            return
        design = design_by_id.get(internal_design_id)
        if design is None:
            return
        next_ancestry = {*ancestry, component_id}
        for instance in design.instances:
            child = component_by_vlnv.get(instance.component_vlnv)
            if child is not None:
                visit(child.ref.entity_id, next_ancestry)

    for component in components:
        visit(component.ref.entity_id, set())
    return sorted(set(diagnostics))


def _walk_blocks(blocks: list[NarrativeBlock]) -> typing.Iterator[NarrativeBlock]:
    """Yield narrative blocks without sharing their mutable list containers."""
    for block in blocks:
        yield block
        yield from _walk_blocks(block.children)
