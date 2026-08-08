"""Atomic optimistic edits for immutable V1 ``SpecRevision`` snapshots."""

from __future__ import annotations

import copy
import dataclasses
import typing
from dataclasses import dataclass

import lxml.etree as etree

from spec2gds.agent_spec.spec_format import ipxact
from spec2gds.agent_spec.spec_format.archive import SpecPackage, SpecValidationError
from spec2gds.agent_spec.spec_format.ir import ConnectionIR, InstanceIR, SpecRevision
from spec2gds.agent_spec.spec_format.models import (
    ID_PATTERN,
    ComponentComposition,
    DocumentKind,
    EntityRef,
    NarrativeBlock,
    new_entity_id,
)
from spec2gds.agent_spec.spec_format.source_edits import (
    add_component_port,
    set_entity_metadata,
    update_component_port,
)


@dataclass(frozen=True)
class UpsertDocumentXml:
    """Add or replace a profiled IP-XACT source document by its root ``xml:id``."""

    kind: DocumentKind
    xml: bytes


@dataclass(frozen=True)
class DeleteDocument:
    """Remove a component, design, bus, or abstraction document by stable ID."""

    ref: EntityRef


@dataclass(frozen=True)
class CreateEntity:
    """Create a minimal top-level component or entry design from a name."""

    kind: typing.Literal["component", "design"]
    name: str
    entity_id: str | None = None
    instances: tuple[InstanceIR, ...] = ()


@dataclass(frozen=True)
class SetDocumentTitle:
    """Replace the human-facing specification title without changing stable IDs."""

    title: str


@dataclass(frozen=True)
class SetEntityMetadata:
    """Replace optional descriptive metadata without changing VLNV identity."""

    entity: EntityRef
    display_name: str | None
    short_description: str | None
    description: str | None


@dataclass(frozen=True)
class WirePortInput:
    """Editable fields for the narrow physical wire-port profile."""

    direction: typing.Literal["in", "out", "inout"]
    range: str | None = None
    display_name: str | None = None
    description: str | None = None
    family: typing.Literal["wire"] = "wire"


@dataclass(frozen=True)
class TransactionalPortInput:
    """Editable fields for the common transactional-port profile."""

    initiative: typing.Literal["requires", "provides", "both"]
    kind: typing.Literal["tlm_port", "tlm_socket", "simple_socket", "multi_socket", "custom"] | None = None
    custom_kind: str | None = None
    bus_width: str | None = None
    display_name: str | None = None
    description: str | None = None
    family: typing.Literal["transactional"] = "transactional"


@dataclass(frozen=True)
class StructuredPortInput:
    """Editable fields for one opaque packed structured port."""

    direction: typing.Literal["in", "out", "inout"]
    display_name: str | None = None
    description: str | None = None
    family: typing.Literal["structured"] = "structured"


ComponentPortInput = typing.Union[WirePortInput, TransactionalPortInput, StructuredPortInput]


@dataclass(frozen=True)
class AddComponentPort:
    """Add one profiled physical port to a leaf component."""

    component: EntityRef
    name: str
    port: ComponentPortInput


@dataclass(frozen=True)
class UpdateComponentPort:
    """Update one existing physical port while preserving its name and family."""

    component: EntityRef
    name: str
    port: ComponentPortInput


@dataclass(frozen=True)
class UpsertInstance:
    """Add or replace a component instance in one design."""

    design: EntityRef
    instance: InstanceIR


@dataclass(frozen=True)
class DeleteInstance:
    """Delete one named component instance from a design."""

    design: EntityRef
    instance_name: str


@dataclass(frozen=True)
class ReorderInstances:
    """Replace one design's component-instance order without changing identities."""

    design: EntityRef
    instance_names: tuple[str, ...]


@dataclass(frozen=True)
class UpsertConnection:
    """Add or replace an interface or ad-hoc connection in one design."""

    design: EntityRef
    connection: ConnectionIR


@dataclass(frozen=True)
class DeleteConnection:
    """Delete one named connection from a design."""

    design: EntityRef
    connection_name: str


@dataclass(frozen=True)
class ReorderConnections:
    """Replace the order of interface or ad-hoc connections of one kind."""

    design: EntityRef
    kind: typing.Literal["interface", "ad_hoc"]
    connection_names: tuple[str, ...]


@dataclass(frozen=True)
class SetInternalDesign:
    """Set the sole internal design composition for a component."""

    component: EntityRef
    internal_design: EntityRef


@dataclass(frozen=True)
class ClearInternalDesign:
    """Clear a component's optional internal-design composition."""

    component: EntityRef


@dataclass(frozen=True)
class AddEntryDesign:
    """Add a design to the explicit entry-design list."""

    design: EntityRef


@dataclass(frozen=True)
class RemoveEntryDesign:
    """Remove a design from the explicit entry-design list."""

    design: EntityRef


@dataclass(frozen=True)
class UpsertNarrativeBlock:
    """Insert or replace one typed narrative block at an optional parent/index."""

    block: NarrativeBlock
    parent_block_id: str | None = None
    index: int | None = None


@dataclass(frozen=True)
class DeleteNarrativeBlock:
    """Delete one narrative block and its descendants."""

    block_id: str


@dataclass(frozen=True)
class ReorderNarrativeBlocks:
    """Reorder all children of a parent block, or all top-level blocks."""

    block_ids: tuple[str, ...]
    parent_block_id: str | None = None


@dataclass(frozen=True)
class SetNarrativeEntityLinks:
    """Replace the direct entity links on one narrative block."""

    block_id: str
    entity_refs: tuple[EntityRef, ...]


@dataclass(frozen=True)
class AddAsset:
    """Add or replace a source asset using its stable asset ID."""

    asset_id: str
    data: bytes
    media_type: str
    extension: str


@dataclass(frozen=True)
class RemoveAsset:
    """Remove a source asset by stable asset ID."""

    asset_id: str


EditOperation = typing.Union[
    UpsertDocumentXml,
    DeleteDocument,
    CreateEntity,
    SetDocumentTitle,
    SetEntityMetadata,
    AddComponentPort,
    UpdateComponentPort,
    UpsertInstance,
    DeleteInstance,
    ReorderInstances,
    UpsertConnection,
    DeleteConnection,
    ReorderConnections,
    SetInternalDesign,
    ClearInternalDesign,
    AddEntryDesign,
    RemoveEntryDesign,
    UpsertNarrativeBlock,
    DeleteNarrativeBlock,
    ReorderNarrativeBlocks,
    SetNarrativeEntityLinks,
    AddAsset,
    RemoveAsset,
]


@dataclass(frozen=True)
class SpecEditTransaction:
    """A complete optimistic edit request against exactly one source revision."""

    base_source_revision_hash: str
    operations: tuple[EditOperation, ...]

    def apply(self, revision: SpecRevision) -> "EditResult":
        """Apply all edits atomically or return diagnostics with no new revision."""
        if self.base_source_revision_hash != revision.source_revision_hash:
            return EditResult(
                revision=None,
                diagnostics=(
                    f"Stale base revision: expected {revision.source_revision_hash}, got {self.base_source_revision_hash}.",
                ),
            )
        package = revision.to_package()
        try:
            for operation in self.operations:
                _apply_operation(package, operation)
            next_revision = SpecRevision.from_package(package)
        except (KeyError, ValueError, SpecValidationError, etree.LxmlError) as exc:
            diagnostics = exc.diagnostics if isinstance(exc, SpecValidationError) else (str(exc),)
            return EditResult(revision=None, diagnostics=tuple(diagnostics))
        return EditResult(revision=next_revision, diagnostics=())


@dataclass(frozen=True)
class EditResult:
    """The all-or-nothing outcome of one edit transaction."""

    revision: SpecRevision | None
    diagnostics: tuple[str, ...]

    @property
    def succeeded(self) -> bool:
        """Whether every requested operation validated and produced a revision."""
        return self.revision is not None


def _apply_operation(package: SpecPackage, operation: EditOperation) -> None:
    """Apply a typed operation to a private package working copy."""
    if isinstance(operation, UpsertDocumentXml):
        package.add_document(operation.kind, operation.xml)
    elif isinstance(operation, DeleteDocument):
        _delete_document(package, operation.ref)
    elif isinstance(operation, CreateEntity):
        _create_entity(package, operation)
    elif isinstance(operation, SetDocumentTitle):
        title = operation.title.strip()
        if not title:
            raise ValueError("Specification name is required.")
        package.narrative = package.narrative.model_copy(update={"title": title})
    elif isinstance(operation, SetEntityMetadata):
        root = _editable_entity_root(package, operation.entity)
        set_entity_metadata(
            root,
            display_name=operation.display_name,
            short_description=operation.short_description,
            description=operation.description,
        )
        package.add_document(typing.cast(DocumentKind, operation.entity.entity_kind), _serialize(root))
    elif isinstance(operation, AddComponentPort):
        root = _editable_component_root(package, operation.component)
        add_component_port(root, {"name": operation.name, **_port_input_mapping(operation.port)})
        package.add_document("component", _serialize(root))
    elif isinstance(operation, UpdateComponentPort):
        root = _editable_component_root(package, operation.component)
        update_component_port(root, name=operation.name, value=_port_input_mapping(operation.port))
        package.add_document("component", _serialize(root))
    elif isinstance(operation, UpsertInstance):
        root, entry = _design_root(package, operation.design)
        _upsert_instance(root, operation.instance)
        package.add_document("design", _serialize(root))
    elif isinstance(operation, DeleteInstance):
        root, _ = _design_root(package, operation.design)
        container = _child(root, "componentInstances")
        if container is None:
            raise KeyError(f"Design has no instance named {operation.instance_name}.")
        target = _named_child(container, "componentInstance", operation.instance_name, "instanceName")
        if target is None:
            raise KeyError(f"Design has no instance named {operation.instance_name}.")
        container.remove(target)
        if not len(container):
            root.remove(container)
        package.add_document("design", _serialize(root))
    elif isinstance(operation, ReorderInstances):
        root, _ = _design_root(package, operation.design)
        container = _required_child(root, "componentInstances")
        _reorder_named_children(container, "componentInstance", operation.instance_names, "instanceName")
        package.add_document("design", _serialize(root))
    elif isinstance(operation, UpsertConnection):
        root, _ = _design_root(package, operation.design)
        _upsert_connection(root, operation.connection)
        package.add_document("design", _serialize(root))
    elif isinstance(operation, DeleteConnection):
        root, _ = _design_root(package, operation.design)
        if not _delete_connection(root, operation.connection_name):
            raise KeyError(f"Design has no connection named {operation.connection_name}.")
        package.add_document("design", _serialize(root))
    elif isinstance(operation, ReorderConnections):
        root, _ = _design_root(package, operation.design)
        container = _required_child(root, "interconnections" if operation.kind == "interface" else "adHocConnections")
        tag = "interconnection" if operation.kind == "interface" else "adHocConnection"
        _reorder_named_children(container, tag, operation.connection_names, "name")
        package.add_document("design", _serialize(root))
    elif isinstance(operation, SetInternalDesign):
        _set_composition(package, operation.component, operation.internal_design)
    elif isinstance(operation, ClearInternalDesign):
        mappings = [mapping for mapping in package.manifest.component_compositions if mapping.component.entity_id != operation.component.entity_id]
        package.manifest = package.manifest.model_copy(update={"component_compositions": mappings})
    elif isinstance(operation, AddEntryDesign):
        package.manifest = package.manifest.model_copy(update={"entry_designs": [*package.manifest.entry_designs, operation.design]})
    elif isinstance(operation, RemoveEntryDesign):
        package.manifest = package.manifest.model_copy(
            update={"entry_designs": [entry for entry in package.manifest.entry_designs if entry.entity_id != operation.design.entity_id]}
        )
    elif isinstance(operation, UpsertNarrativeBlock):
        _upsert_narrative_block(package, operation)
    elif isinstance(operation, DeleteNarrativeBlock):
        _delete_narrative_block(package, operation.block_id)
    elif isinstance(operation, ReorderNarrativeBlocks):
        _reorder_narrative_blocks(package, operation)
    elif isinstance(operation, SetNarrativeEntityLinks):
        _set_narrative_links(package, operation)
    elif isinstance(operation, AddAsset):
        package.add_asset(operation.asset_id, operation.data, operation.media_type, operation.extension)
    elif isinstance(operation, RemoveAsset):
        _remove_asset(package, operation.asset_id)
    else:  # pragma: no cover - protects this dispatcher when the union grows.
        raise TypeError(f"Unsupported edit operation: {type(operation).__name__}")


def _port_input_mapping(value: ComponentPortInput) -> dict[str, typing.Any]:
    """Convert one typed transaction value to the shared source-helper shape."""
    result = {field.name: getattr(value, field.name) for field in dataclasses.fields(value)}
    return typing.cast(dict[str, typing.Any], result)


def _delete_document(package: SpecPackage, ref: EntityRef) -> None:
    """Remove source bytes and manifest row; final validation checks dependent links."""
    _assert_local(package, ref)
    entry = next((item for item in package.manifest.documents if item.entity_id == ref.entity_id and item.kind == ref.entity_kind), None)
    if entry is None:
        raise KeyError(f"Unknown document entity: {ref.entity_id}")
    package.files.pop(entry.path, None)
    package.manifest = package.manifest.model_copy(
        update={"documents": [item for item in package.manifest.documents if item.entity_id != ref.entity_id]}
    )


def _create_entity(package: SpecPackage, operation: CreateEntity) -> None:
    """Create one minimal valid IP-XACT document with editor-owned defaults."""
    name = operation.name.strip()
    if not name or not ID_PATTERN.fullmatch(name):
        raise ValueError("Entity name must be a non-empty XML-compatible identifier.")
    vlnv = f"spec2gds.local:work:{name}:1.0"
    if any(item.kind == operation.kind and item.vlnv == vlnv for item in package.manifest.documents):
        raise ValueError(f"A {operation.kind.replace('_', ' ')} named {name} already exists.")
    entity_id = operation.entity_id or new_entity_id(f"{operation.kind}_{name}")
    if not ID_PATTERN.fullmatch(entity_id):
        raise ValueError("Entity ID must be an XML-compatible identifier.")
    if any(item.entity_id == entity_id for item in package.manifest.documents):
        raise ValueError(f"Entity ID already exists: {entity_id}")
    if operation.kind == "component" and operation.instances:
        raise ValueError("Only designs may define component instances.")
    instance_names = [item.name for item in operation.instances]
    if len(instance_names) != len(set(instance_names)):
        raise ValueError("Design component instance names must be unique.")
    root_name = ipxact.ROOT_NAMES[operation.kind]
    root = etree.Element(_q(root_name), nsmap={"ipxact": ipxact.IPXACT_NAMESPACE})
    root.set(f"{{{ipxact.XML_NAMESPACE}}}id", entity_id)
    for field, value in (
        ("vendor", "spec2gds.local"),
        ("library", "work"),
        ("name", name),
        ("version", "1.0"),
    ):
        etree.SubElement(root, _q(field)).text = value
    for instance in operation.instances:
        _upsert_instance(root, instance)
    package.add_document(operation.kind, _serialize(root))
    if operation.kind == "design":
        reference = EntityRef(
            document_id=package.manifest.document_id,
            entity_id=entity_id,
            entity_kind="design",
        )
        package.manifest = package.manifest.model_copy(
            update={"entry_designs": [*package.manifest.entry_designs, reference]}
        )


def _editable_entity_root(package: SpecPackage, ref: EntityRef) -> etree._Element:
    """Load a component or design root for descriptive editor changes."""
    _assert_local(package, ref)
    if ref.entity_kind not in {"component", "design"}:
        raise ValueError("Direct metadata editing supports only components and designs.")
    entry = next(
        (item for item in package.manifest.documents if item.entity_id == ref.entity_id and item.kind == ref.entity_kind),
        None,
    )
    if entry is None:
        raise KeyError(f"Unknown {ref.entity_kind}: {ref.entity_id}")
    return ipxact.parse_xml(package.files[entry.path])


def _editable_component_root(package: SpecPackage, ref: EntityRef) -> etree._Element:
    """Load a leaf component root and reject composite boundary mutations."""
    _assert_local(package, ref)
    if ref.entity_kind != "component":
        raise ValueError("Port operations require a component reference.")
    if any(item.component.entity_id == ref.entity_id for item in package.manifest.component_compositions):
        raise ValueError("Ports on components with internal designs are read-only until boundary editing is supported.")
    entry = next(
        (item for item in package.manifest.documents if item.entity_id == ref.entity_id and item.kind == "component"),
        None,
    )
    if entry is None:
        raise KeyError(f"Unknown component: {ref.entity_id}")
    return ipxact.parse_xml(package.files[entry.path])


def _set_composition(package: SpecPackage, component: EntityRef, internal_design: EntityRef) -> None:
    """Replace a component composition mapping while preserving its stable refs."""
    _assert_local(package, component)
    _assert_local(package, internal_design)
    mappings = [mapping for mapping in package.manifest.component_compositions if mapping.component.entity_id != component.entity_id]
    mappings.append(ComponentComposition(component=component, internal_design=internal_design))
    package.manifest = package.manifest.model_copy(update={"component_compositions": mappings})


def _design_root(package: SpecPackage, ref: EntityRef) -> tuple[etree._Element, typing.Any]:
    """Load one design XML root from the private transaction working package."""
    _assert_local(package, ref)
    if ref.entity_kind != "design":
        raise ValueError("Instance and connection operations require a design reference.")
    entry = next((item for item in package.manifest.documents if item.entity_id == ref.entity_id and item.kind == "design"), None)
    if entry is None:
        raise KeyError(f"Unknown design entity: {ref.entity_id}")
    return ipxact.parse_xml(package.files[entry.path]), entry


def _assert_local(package: SpecPackage, ref: EntityRef) -> None:
    """Reject cross-document references before editing a package working copy."""
    if ref.document_id != package.manifest.document_id:
        raise ValueError("V1 edit references must belong to the revision document.")


def _q(name: str) -> str:
    """Qualify an IP-XACT local name for element construction."""
    return f"{{{ipxact.IPXACT_NAMESPACE}}}{name}"


def _child(root: etree._Element, name: str) -> etree._Element | None:
    """Return the first direct child with the requested local name."""
    return next((child for child in root if etree.QName(child).localname == name), None)


def _required_child(root: etree._Element, name: str) -> etree._Element:
    """Resolve a required XML container with an actionable error."""
    child = _child(root, name)
    if child is None:
        raise KeyError(f"Missing {name} container.")
    return child


def _named_child(parent: etree._Element, tag: str, name: str, name_child: str) -> etree._Element | None:
    """Find a typed child by the text of its stable name element."""
    for child in parent:
        if etree.QName(child).localname == tag and _text(child, name_child) == name:
            return child
    return None


def _text(node: etree._Element, name: str) -> str:
    """Read normalized direct-child text, defaulting to empty."""
    child = _child(node, name)
    return (child.text or "").strip() if child is not None else ""


def _insert_ordered(root: etree._Element, element: etree._Element, name: str) -> None:
    """Insert a design child in the IEEE sequence required by the XSD."""
    order = ["componentInstances", "interconnections", "adHocConnections", "choices", "parameters", "assertions", "vendorExtensions"]
    position = order.index(name)
    for index, child in enumerate(root):
        child_name = etree.QName(child).localname
        if child_name in order and order.index(child_name) > position:
            root.insert(index, element)
            return
    root.append(element)


def _ensure_container(root: etree._Element, name: str) -> etree._Element:
    """Return or create an XML container at its schema-defined position."""
    container = _child(root, name)
    if container is None:
        container = etree.Element(_q(name))
        _insert_ordered(root, container, name)
    return container


def _upsert_instance(root: etree._Element, instance: InstanceIR) -> None:
    """Replace an instance by name while preserving canonical document order."""
    container = _ensure_container(root, "componentInstances")
    existing = _named_child(container, "componentInstance", instance.name, "instanceName")
    if existing is not None:
        container.remove(existing)
    component = etree.Element(_q("componentInstance"))
    etree.SubElement(component, _q("instanceName")).text = instance.name
    vendor, library, name, version = instance.component_vlnv.split(":", 3)
    etree.SubElement(component, _q("componentRef"), vendor=vendor, library=library, name=name, version=version)
    container.append(component)


def _upsert_connection(root: etree._Element, connection: ConnectionIR) -> None:
    """Serialize an interface or ad-hoc connection from its typed IR."""
    _delete_connection(root, connection.name)
    if connection.kind == "interface":
        container = _ensure_container(root, "interconnections")
        node = etree.Element(_q("interconnection"))
        etree.SubElement(node, _q("name")).text = connection.name
        for endpoint in connection.interface_endpoints:
            etree.SubElement(node, _q("activeInterface"), componentInstanceRef=endpoint.instance_name, busRef=endpoint.interface_name)
        for interface_name in connection.hierarchy_interfaces:
            etree.SubElement(node, _q("hierInterface"), busRef=interface_name)
    else:
        container = _ensure_container(root, "adHocConnections")
        node = etree.Element(_q("adHocConnection"))
        etree.SubElement(node, _q("name")).text = connection.name
        references = etree.SubElement(node, _q("portReferences"))
        for endpoint in connection.port_endpoints:
            etree.SubElement(references, _q("internalPortReference"), componentInstanceRef=endpoint.instance_name, portRef=endpoint.port_name)
        for port_name in connection.external_ports:
            etree.SubElement(references, _q("externalPortReference"), portRef=port_name)
    container.append(node)


def _delete_connection(root: etree._Element, connection_name: str) -> bool:
    """Delete a connection from either legal container and prune empties."""
    deleted = False
    for container_name, connection_name_tag in (("interconnections", "interconnection"), ("adHocConnections", "adHocConnection")):
        container = _child(root, container_name)
        if container is None:
            continue
        target = _named_child(container, connection_name_tag, connection_name, "name")
        if target is not None:
            container.remove(target)
            deleted = True
        if not len(container):
            root.remove(container)
    return deleted


def _reorder_named_children(parent: etree._Element, tag: str, names: tuple[str, ...], name_child: str) -> None:
    """Apply an exact permutation after validating its membership."""
    children = [child for child in parent if etree.QName(child).localname == tag]
    by_name = {_text(child, name_child): child for child in children}
    if len(by_name) != len(children) or set(names) != set(by_name) or len(names) != len(by_name):
        raise ValueError(f"Reorder set must contain every {tag} name exactly once.")
    for child in children:
        parent.remove(child)
    for name in names:
        parent.append(by_name[name])


def _serialize(root: etree._Element) -> bytes:
    """Serialize edited XML in the package's canonical readable form."""
    return etree.tostring(root, encoding="UTF-8", xml_declaration=True, pretty_print=True)


def _blocks_copy(package: SpecPackage) -> list[NarrativeBlock]:
    """Copy the narrative tree so a failed edit cannot mutate source state."""
    return copy.deepcopy(package.narrative.blocks)


def _find_block_list(blocks: list[NarrativeBlock], block_id: str) -> tuple[list[NarrativeBlock], int] | None:
    """Locate a block together with its owning list and index."""
    for index, block in enumerate(blocks):
        if block.block_id == block_id:
            return blocks, index
        nested = _find_block_list(block.children, block_id)
        if nested is not None:
            return nested
    return None


def _upsert_narrative_block(package: SpecPackage, operation: UpsertNarrativeBlock) -> None:
    """Replace a block by id or insert it at a validated tree location."""
    blocks = _blocks_copy(package)
    existing = _find_block_list(blocks, operation.block.block_id)
    if existing is not None:
        parent, index = existing
        parent[index] = copy.deepcopy(operation.block)
    else:
        target = blocks
        if operation.parent_block_id is not None:
            parent_location = _find_block_list(blocks, operation.parent_block_id)
            if parent_location is None:
                raise KeyError(f"Unknown narrative parent block: {operation.parent_block_id}")
            target = parent_location[0][parent_location[1]].children
        index = operation.index if operation.index is not None else len(target)
        if index < 0 or index > len(target):
            raise ValueError("Narrative insertion index is outside the target block list.")
        target.insert(index, copy.deepcopy(operation.block))
    package.narrative = package.narrative.model_copy(update={"blocks": blocks})


def _delete_narrative_block(package: SpecPackage, block_id: str) -> None:
    """Remove one narrative subtree by stable block id."""
    blocks = _blocks_copy(package)
    location = _find_block_list(blocks, block_id)
    if location is None:
        raise KeyError(f"Unknown narrative block: {block_id}")
    location[0].pop(location[1])
    package.narrative = package.narrative.model_copy(update={"blocks": blocks})


def _reorder_narrative_blocks(package: SpecPackage, operation: ReorderNarrativeBlocks) -> None:
    """Apply an exact sibling permutation at the root or below a parent."""
    blocks = _blocks_copy(package)
    target = blocks
    if operation.parent_block_id is not None:
        location = _find_block_list(blocks, operation.parent_block_id)
        if location is None:
            raise KeyError(f"Unknown narrative parent block: {operation.parent_block_id}")
        target = location[0][location[1]].children
    by_id = {block.block_id: block for block in target}
    if len(by_id) != len(target) or set(operation.block_ids) != set(by_id) or len(operation.block_ids) != len(by_id):
        raise ValueError("Narrative reorder set must contain every target block id exactly once.")
    target[:] = [by_id[block_id] for block_id in operation.block_ids]
    package.narrative = package.narrative.model_copy(update={"blocks": blocks})


def _set_narrative_links(package: SpecPackage, operation: SetNarrativeEntityLinks) -> None:
    """Replace entity links on one narrative block without changing its id."""
    blocks = _blocks_copy(package)
    location = _find_block_list(blocks, operation.block_id)
    if location is None:
        raise KeyError(f"Unknown narrative block: {operation.block_id}")
    parent, index = location
    parent[index] = parent[index].model_copy(update={"entity_refs": list(operation.entity_refs)})
    package.narrative = package.narrative.model_copy(update={"blocks": blocks})


def _remove_asset(package: SpecPackage, asset_id: str) -> None:
    """Remove both source bytes and manifest metadata for one asset."""
    asset = next((item for item in package.manifest.assets if item.asset_id == asset_id), None)
    if asset is None:
        raise KeyError(f"Unknown asset: {asset_id}")
    package.files.pop(asset.path, None)
    package.manifest = package.manifest.model_copy(
        update={"assets": [item for item in package.manifest.assets if item.asset_id != asset_id]}
    )
