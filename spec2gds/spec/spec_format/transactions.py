"""Atomic optimistic edits for immutable V1 ``SpecRevision`` snapshots."""

from __future__ import annotations

import copy
import dataclasses
import typing
from dataclasses import dataclass

import lxml.etree as etree

from spec2gds.spec.spec_format import ipxact
from spec2gds.spec.spec_format.archive import SpecPackage, SpecValidationError
from spec2gds.spec.spec_format.circuit_layouts import (
    DesignCircuitLayoutV1,
    delete_design_layout,
    upsert_design_layout,
)
from spec2gds.spec.spec_format.circuit_timings import (
    DesignCircuitTimingV1,
    DesignClockSignalV1,
    upsert_design_timing,
)
from spec2gds.spec.spec_format.ir import (
    ConnectionIR,
    ExternalPortEndpointIR,
    InstanceIR,
    SpecRevision,
)
from spec2gds.spec.spec_format.models import (
    ID_PATTERN,
    ComponentComposition,
    DocumentKind,
    EntityRef,
    NarrativeBlock,
    new_entity_id,
    validate_vlnv,
)
from spec2gds.spec.spec_format.naming import (
    clean_name,
    entity_name,
    hardware_name,
    require_unique_name,
    validate_package_names,
)
from spec2gds.spec.spec_format.sections import (
    SECTION_TYPES,
    delete_entity_section,
    delete_sections_for_parent,
    upsert_systemverilog_section,
)
from spec2gds.spec.spec_format.source_edits import (
    add_component_port,
    set_entity_metadata,
    update_component_port,
    upsert_component_port,
)
from spec2gds.spec.spec_format.sv_validation import (
    SectionValidation,
    validate_revision_sections,
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
class SetDocumentTitle:
    """Replace the human-facing specification title without changing stable IDs."""

    title: str


@dataclass(frozen=True)
class SetHardwareMetadata:
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
    description: str | None = None
    family: typing.Literal["wire"] = "wire"


@dataclass(frozen=True)
class TransactionalPortInput:
    """Editable fields for the common transactional-port profile."""

    initiative: typing.Literal["requires", "provides", "both"]
    kind: typing.Literal["tlm_port", "tlm_socket", "simple_socket", "multi_socket", "custom"] | None = None
    custom_kind: str | None = None
    bus_width: str | None = None
    description: str | None = None
    family: typing.Literal["transactional"] = "transactional"


@dataclass(frozen=True)
class StructuredPortInput:
    """Editable fields for one opaque packed structured port."""

    direction: typing.Literal["in", "out", "inout"]
    description: str | None = None
    family: typing.Literal["structured"] = "structured"


ComponentPortInput = typing.Union[WirePortInput, TransactionalPortInput, StructuredPortInput]


@dataclass(frozen=True)
class InitialComponentPort:
    """One named port created atomically with a new component."""

    name: str
    port: ComponentPortInput


@dataclass(frozen=True)
class CreateHardware:
    """Create a top-level component or entry design with optional initial content."""

    kind: typing.Literal["component", "design"]
    name: str
    entity_id: str | None = None
    instances: tuple[InstanceIR, ...] = ()
    ports: tuple[InitialComponentPort, ...] = ()
    systemverilog: str | None = None
    entry_design: bool = True
    vlnv: str | None = None


@dataclass(frozen=True)
class AddComponentPort:
    """Add one profiled physical port to a leaf component."""

    component: EntityRef
    name: str
    port: ComponentPortInput
    allow_composite: bool = False


@dataclass(frozen=True)
class UpdateComponentPort:
    """Update one existing physical port while preserving its name and family."""

    component: EntityRef
    name: str
    port: ComponentPortInput
    allow_composite: bool = False


@dataclass(frozen=True)
class RenameComponentPort:
    """Rename a physical component port and every package-local reference."""

    component: EntityRef
    old_name: str
    new_name: str


@dataclass(frozen=True)
class DeleteComponentPort:
    """Delete a component port after dependency checks performed by the caller."""

    component: EntityRef
    name: str


@dataclass(frozen=True)
class UpdateParameter:
    """Create or update a declared parameter through a manual transaction."""

    component: EntityRef
    parameter: dict[str, typing.Any]


@dataclass(frozen=True)
class DeleteParameter:
    """Remove one declared parameter without rewriting its consumers."""

    component: EntityRef
    name: str


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
class RenameInstance:
    """Rename one instance and all connection references in its design."""

    design: EntityRef
    old_name: str
    new_name: str


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
class SetNarrativeLinks:
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


@dataclass(frozen=True)
class UpsertSection:
    """Create or replace one registered entity section."""

    parent: EntityRef
    section_type: str
    payload: typing.Mapping[str, typing.Any]
    section_id: str | None = None
    type_version: int = 1


@dataclass(frozen=True)
class DeleteSection:
    """Delete one registered entity section from an owner."""

    parent: EntityRef
    section_type: str
    section_id: str | None = None


@dataclass(frozen=True)
class UpsertCircuitLayout:
    """Persist one source-semantic circuit layout annotation."""

    layout: DesignCircuitLayoutV1


@dataclass(frozen=True)
class UpsertCircuitTiming:
    """Persist one source-semantic circuit timing annotation."""

    timing: DesignCircuitTimingV1


EditOperation = typing.Union[
    UpsertDocumentXml,
    DeleteDocument,
    CreateHardware,
    SetDocumentTitle,
    SetHardwareMetadata,
    AddComponentPort,
    UpdateComponentPort,
    RenameComponentPort,
    DeleteComponentPort,
    UpdateParameter,
    DeleteParameter,
    UpsertInstance,
    DeleteInstance,
    RenameInstance,
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
    SetNarrativeLinks,
    AddAsset,
    RemoveAsset,
    UpsertSection,
    DeleteSection,
    UpsertCircuitLayout,
    UpsertCircuitTiming,
]


@dataclass(frozen=True)
class SpecEditTransaction:
    """A complete optimistic edit request against exactly one source revision."""

    base_source_revision_hash: str
    operations: tuple[EditOperation, ...]
    validation_mode: typing.Literal["strict", "authoring"] = "strict"

    def apply(self, revision: SpecRevision) -> "EditResult":
        """Apply all edits atomically or return diagnostics with no new revision."""
        if self.base_source_revision_hash != revision.source_revision_hash:
            return EditResult(
                revision=None,
                diagnostics=(
                    f"Stale base revision: expected {revision.source_revision_hash}, got {self.base_source_revision_hash}.",
                ),
            )
        # Mutate a detached package. Validation failure returns no candidate revision,
        # leaving the immutable input usable by readers and other guarded transactions.
        package = revision.to_package()
        created_sv_owners: set[EntityRef] = set()
        try:
            for operation in self.operations:
                created = _apply_operation(package, operation)
                if isinstance(operation, CreateHardware) and operation.systemverilog is not None and created is not None:
                    created_sv_owners.add(created)
            validate_package_names(package)
            next_revision = SpecRevision.from_package(package)
        except (KeyError, ValueError, SpecValidationError, etree.LxmlError) as exc:
            diagnostics = exc.diagnostics if isinstance(exc, SpecValidationError) else (str(exc),)
            return EditResult(revision=None, diagnostics=tuple(diagnostics))
        if self.validation_mode == "authoring":
            return EditResult(revision=next_revision, diagnostics=())
        updated_owners = {
            operation.parent
            for operation in self.operations
            if isinstance(operation, UpsertSection) and operation.section_type == "sv"
        }
        updated_owners.update(created_sv_owners)
        old_components = {component.ref: component for component in revision.components}
        for component in next_revision.components:
            previous = old_components.get(component.ref)
            if previous is None or component.ports != previous.ports or component.parameters != previous.parameters:
                updated_owners.add(component.ref)
        from dataclasses import asdict
        from spec2gds.spec.spec_format.rtl_interface import resolve_interface
        for component in next_revision.components:
            if component.ref not in updated_owners:
                continue
            body = "\n".join(section.content for section in next_revision.entity_sections_for(component.ref, "sv"))
            if not body and not component.parameters:
                continue
            try:
                resolved = resolve_interface(
                    [{"name": port.name, "direction": port.direction,
                      "range": port.width[1:-1] if isinstance(port.width, str) else None}
                     for port in component.ports if port.style == "wire"],
                    [asdict(parameter) for parameter in component.parameters], body,
                )
            except (ValueError, OSError) as exc:
                return EditResult(revision=None, diagnostics=(str(exc),))
            if resolved["status"] != "resolved":
                return EditResult(revision=None, diagnostics=tuple(item["message"] for item in resolved["diagnostics"]))
        updated_ids = {
            item.section_id for owner in updated_owners
            for item in next_revision.entity_sections_for(owner, "sv")
        }
        # Validate changed bodies against the fully updated ports/hierarchy, so a batch
        # can author an entity and its body atomically without validating an intermediate.
        section_validation = validate_revision_sections(next_revision, updated_ids)
        if any(item.blocking for item in section_validation):
            messages = tuple(
                diagnostic.message
                for result in section_validation
                for diagnostic in result.diagnostics
                if diagnostic.blocking
            )
            return EditResult(
                revision=None,
                diagnostics=messages or ("SystemVerilog validation failed.",),
                section_validation=section_validation,
            )
        return EditResult(revision=next_revision, diagnostics=(), section_validation=section_validation)


@dataclass(frozen=True)
class EditResult:
    """The all-or-nothing outcome of one edit transaction."""

    revision: SpecRevision | None
    diagnostics: tuple[str, ...]
    section_validation: tuple[SectionValidation, ...] = ()

    @property
    def succeeded(self) -> bool:
        """Whether every requested operation validated and produced a revision."""
        return self.revision is not None


def _apply_operation(package: SpecPackage, operation: EditOperation) -> EntityRef | None:
    """Apply a typed operation and return the stable reference for a creation."""
    if isinstance(operation, UpsertDocumentXml):
        package.add_document(operation.kind, operation.xml)
    elif isinstance(operation, DeleteDocument):
        if operation.ref.entity_kind == "design":
            delete_design_layout(package, operation.ref.entity_id)
        _delete_document(package, operation.ref)
    elif isinstance(operation, CreateHardware):
        return _create_entity(package, operation)
    elif isinstance(operation, SetDocumentTitle):
        if not operation.title.strip():
            raise ValueError("Spec name is required.")
        title = clean_name(operation.title)
        package.narrative = package.narrative.model_copy(update={"title": title})
    elif isinstance(operation, SetHardwareMetadata):
        root = _editable_entity_root(package, operation.entity)
        set_entity_metadata(
            root,
            display_name=clean_name(operation.display_name) if operation.display_name is not None else None,
            short_description=operation.short_description,
            description=operation.description,
        )
        package.add_document(typing.cast(DocumentKind, operation.entity.entity_kind), _serialize(root))
    elif isinstance(operation, AddComponentPort):
        root = _editable_component_root(package, operation.component, allow_composite=operation.allow_composite)
        add_component_port(root, {"name": operation.name, **_port_input_mapping(operation.port)})
        package.add_document("component", _serialize(root))
    elif isinstance(operation, UpdateComponentPort):
        root = _editable_component_root(package, operation.component, allow_composite=operation.allow_composite)
        update_component_port(root, name=operation.name, value=_port_input_mapping(operation.port))
        package.add_document("component", _serialize(root))
    elif isinstance(operation, RenameComponentPort):
        _rename_component_port(package, operation)
    elif isinstance(operation, DeleteComponentPort):
        _delete_component_port(package, operation)
    elif isinstance(operation, (UpdateParameter, DeleteParameter)):
        from spec2gds.spec.spec_format.source_edits import edit_parameter
        root = _editable_component_root(package, operation.component, allow_composite=True)
        edit_parameter(root, operation.parameter if isinstance(operation, UpdateParameter) else None,
                       operation.name if isinstance(operation, DeleteParameter) else "")
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
        timing_data = package.files.get(f"annotations/circuit-timing/{operation.design.entity_id}.json")
        if timing_data is not None:
            timing = DesignCircuitTimingV1.model_validate_json(timing_data)
            upsert_design_timing(package, timing.model_copy(update={
                "subject_domain_overrides": {
                    key: value for key, value in timing.subject_domain_overrides.items()
                    if key != f"instance:{operation.instance_name}"
                }
            }))
    elif isinstance(operation, RenameInstance):
        _rename_instance(package, operation)
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
        timing_data = package.files.get(f"annotations/circuit-timing/{operation.design.entity_id}.json")
        if timing_data is not None:
            timing = DesignCircuitTimingV1.model_validate_json(timing_data)
            domains = tuple(
                domain.model_copy(update={"signal": None})
                if domain.signal is not None and domain.signal.kind == "net" and domain.signal.id == operation.connection_name
                else domain
                for domain in timing.clock_domains
            )
            upsert_design_timing(package, timing.model_copy(update={"clock_domains": domains}))
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
    elif isinstance(operation, SetNarrativeLinks):
        _set_narrative_links(package, operation)
    elif isinstance(operation, AddAsset):
        package.add_asset(operation.asset_id, operation.data, operation.media_type, operation.extension)
    elif isinstance(operation, RemoveAsset):
        _remove_asset(package, operation.asset_id)
    elif isinstance(operation, UpsertSection):
        definition = SECTION_TYPES.get(operation.section_type)
        if definition is None or operation.type_version != definition.version:
            raise ValueError(
                f"Unsupported entity section type/version: {operation.section_type}@{operation.type_version}"
            )
        if operation.parent.entity_kind not in definition.entity_kinds:
            raise ValueError(f"Section type {operation.section_type} cannot attach to {operation.parent.entity_kind}.")
        payload = definition.payload_validator(operation.payload)
        if operation.section_type == "sv":
            upsert_systemverilog_section(package, operation.parent, typing.cast(str, payload), operation.section_id)
        elif operation.section_type == "text":
            root = _editable_entity_root(package, operation.parent)
            set_entity_metadata(
                root,
                display_name=_text(root, "displayName") or None,
                short_description=_text(root, "shortDescription") or None,
                description=typing.cast(str, payload),
            )
            package.add_document(typing.cast(DocumentKind, operation.parent.entity_kind), _serialize(root))
        elif operation.section_type == "ports":
            root = _editable_component_root(package, operation.parent)
            model = _child(root, "model")
            ports = _child(model, "ports") if model is not None else None
            if ports is not None and model is not None:
                model.remove(ports)
            for value in typing.cast(list[typing.Any], payload):
                if not isinstance(value, dict):
                    raise ValueError("Every ports payload item must be an object.")
                upsert_component_port(root, value)
            package.add_document("component", _serialize(root))
    elif isinstance(operation, DeleteSection):
        definition = SECTION_TYPES.get(operation.section_type)
        if definition is None or not definition.deletable:
            raise ValueError(f"Section type {operation.section_type} is not deletable.")
        delete_entity_section(package, operation.parent, operation.section_type, operation.section_id)
    elif isinstance(operation, UpsertCircuitLayout):
        upsert_design_layout(package, operation.layout)
    elif isinstance(operation, UpsertCircuitTiming):
        upsert_design_timing(package, operation.timing)
    else:  # pragma: no cover - protects this dispatcher when the union grows.
        raise TypeError(f"Unsupported edit operation: {type(operation).__name__}")
    return None


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
    delete_sections_for_parent(package, ref)
    package.files.pop(entry.path, None)
    package.manifest = package.manifest.model_copy(
        update={"documents": [item for item in package.manifest.documents if item.entity_id != ref.entity_id]}
    )


def _create_entity(package: SpecPackage, operation: CreateHardware) -> EntityRef:
    """Create an IP-XACT document and return its reference for content validation."""
    display_name = clean_name(operation.name)
    existing_revision = SpecRevision.from_package(package)
    require_unique_name(display_name, (entity_name(item) for item in (*existing_revision.components, *existing_revision.designs, *existing_revision.bus_definitions, *existing_revision.abstraction_definitions)))
    name = hardware_name(display_name, (item.vlnv.split(":")[2] for item in (*existing_revision.components, *existing_revision.designs) if item.ref.entity_kind == operation.kind))
    if operation.vlnv is not None:
        vlnv = validate_vlnv(operation.vlnv)
        vendor, library, vlnv_name, version = vlnv.split(":")
        if vlnv_name != name:
            raise ValueError(f"VLNV name {vlnv_name!r} does not match hardware name {name!r}.")
        if any(item.vlnv == vlnv for item in package.manifest.documents):
            raise ValueError(f"A document with VLNV {vlnv} already exists.")
    else:
        vendor = "spec2gds.local"
        library = "work"
        version = "1.0"
        vlnv = f"spec2gds.local:work:{name}:1.0"
        if any(item.kind == operation.kind and item.vlnv == vlnv for item in package.manifest.documents):
            raise ValueError(f"A {operation.kind.replace('_', ' ')} named {name} already exists.")
        if any(item.vlnv == vlnv for item in package.manifest.documents):
            raise ValueError(f"A document with VLNV {vlnv} already exists.")
    entity_id = operation.entity_id or new_entity_id(f"{operation.kind}_{name}")
    if not ID_PATTERN.fullmatch(entity_id):
        raise ValueError("Entity ID must be an XML-compatible identifier.")
    if any(item.entity_id == entity_id for item in package.manifest.documents):
        raise ValueError(f"Entity ID already exists: {entity_id}")
    if operation.kind == "component" and operation.instances:
        raise ValueError("Only designs may define component instances.")
    if operation.kind == "design" and operation.ports:
        raise ValueError("Only components may define initial ports.")
    if operation.kind == "design" and operation.systemverilog is not None:
        raise ValueError("Initial SystemVerilog behavior is supported only for components.")
    instance_names = [item.name for item in operation.instances]
    if len(instance_names) != len(set(instance_names)):
        raise ValueError("Design component instance names must be unique.")
    root_name = ipxact.ROOT_NAMES[operation.kind]
    root = etree.Element(_q(root_name), nsmap={"ipxact": ipxact.IPXACT_NAMESPACE})
    root.set(f"{{{ipxact.XML_NAMESPACE}}}id", entity_id)
    for field, value in (
        ("vendor", vendor),
        ("library", library),
        ("name", name),
        ("version", version),
        ("displayName", display_name),
    ):
        etree.SubElement(root, _q(field)).text = value
    for instance in operation.instances:
        _upsert_instance(root, instance)
    initial_port_names = [item.name for item in operation.ports]
    if len(initial_port_names) != len(set(initial_port_names)):
        raise ValueError("Initial component port names must be unique.")
    for initial_port in operation.ports:
        add_component_port(root, {"name": initial_port.name, **_port_input_mapping(initial_port.port)})
    package.add_document(operation.kind, _serialize(root))
    reference = EntityRef(
        document_id=package.manifest.document_id,
        entity_id=entity_id,
        entity_kind=operation.kind,
    )
    if operation.systemverilog is not None:
        upsert_systemverilog_section(package, reference, operation.systemverilog)
    if operation.kind == "design" and operation.entry_design:
        package.manifest = package.manifest.model_copy(
            update={"entry_designs": [*package.manifest.entry_designs, reference]}
        )
    return reference


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


def _editable_component_root(package: SpecPackage, ref: EntityRef, *, allow_composite: bool = False) -> etree._Element:
    """Load one component root for validated physical-port mutations."""
    _assert_local(package, ref)
    if ref.entity_kind != "component":
        raise ValueError("Port operations require a component reference.")
    if not allow_composite and any(item.component.entity_id == ref.entity_id for item in package.manifest.component_compositions):
        raise ValueError("Ports on components with internal designs require the circuit boundary editor.")
    entry = next(
        (item for item in package.manifest.documents if item.entity_id == ref.entity_id and item.kind == "component"),
        None,
    )
    if entry is None:
        raise KeyError(f"Unknown component: {ref.entity_id}")
    return ipxact.parse_xml(package.files[entry.path])


def _rename_instance(package: SpecPackage, operation: RenameInstance) -> None:
    """Rename an instance while retaining both visible and omitted connections."""
    if not ID_PATTERN.fullmatch(operation.new_name):
        raise ValueError("Instance name must be an XML-compatible identifier.")
    root, _ = _design_root(package, operation.design)
    container = _required_child(root, "componentInstances")
    target = _named_child(container, "componentInstance", operation.old_name, "instanceName")
    if target is None:
        raise KeyError(f"Design has no instance named {operation.old_name}.")
    if _named_child(container, "componentInstance", operation.new_name, "instanceName") is not None:
        raise ValueError(f"Design already has an instance named {operation.new_name}.")
    name = _child(target, "instanceName")
    assert name is not None
    name.text = operation.new_name
    for node in root.xpath(".//*[@componentInstanceRef]"):
        if node.get("componentInstanceRef") == operation.old_name:
            node.set("componentInstanceRef", operation.new_name)
    package.add_document("design", _serialize(root))
    layout_annotation = package.files.get(f"annotations/circuit-layout/{operation.design.entity_id}.json")
    if layout_annotation is not None:
        layout = DesignCircuitLayoutV1.model_validate_json(layout_annotation)
        old_prefix = f"instance:{operation.old_name}/"
        new_prefix = f"instance:{operation.new_name}/"

        def rename_key(key: str) -> str:
            if key == f"instance:{operation.old_name}":
                return f"instance:{operation.new_name}"
            return new_prefix + key[len(old_prefix):] if key.startswith(old_prefix) else key

        routes = copy.deepcopy(layout.net_routes)
        for route in routes.values():
            for vertex in route.get("vertices", []):
                if isinstance(vertex.get("terminal_id"), str):
                    vertex["terminal_id"] = rename_key(vertex["terminal_id"])
        geometry = dict(layout.instance_geometry)
        if operation.old_name in geometry:
            geometry[operation.new_name] = geometry.pop(operation.old_name)
        upsert_design_layout(package, layout.model_copy(update={
            "instance_geometry": geometry,
            "terminal_placements": {rename_key(key): value for key, value in layout.terminal_placements.items()},
            "label_geometry": {rename_key(key): value for key, value in layout.label_geometry.items()},
            "net_routes": routes,
        }))
    timing_annotation = package.files.get(f"annotations/circuit-timing/{operation.design.entity_id}.json")
    if timing_annotation is not None:
        timing = DesignCircuitTimingV1.model_validate_json(timing_annotation)
        old_key = f"instance:{operation.old_name}"
        new_key = f"instance:{operation.new_name}"
        overrides = dict(timing.subject_domain_overrides)
        if old_key in overrides:
            overrides[new_key] = overrides.pop(old_key)
        upsert_design_timing(package, timing.model_copy(update={"subject_domain_overrides": overrides}))


def _component_vlnv(package: SpecPackage, component: EntityRef) -> str:
    entry = next(
        (item for item in package.manifest.documents if item.entity_id == component.entity_id and item.kind == "component"),
        None,
    )
    if entry is None:
        raise KeyError(f"Unknown component: {component.entity_id}")
    return entry.vlnv


def _rename_component_port(package: SpecPackage, operation: RenameComponentPort) -> None:
    """Rename a port and all physical references throughout the package."""
    if not ID_PATTERN.fullmatch(operation.new_name):
        raise ValueError("Port name must be an XML-compatible identifier.")
    component_root = _editable_component_root(package, operation.component, allow_composite=True)
    ports = component_root.xpath("./*[local-name()='model']/*[local-name()='ports']")[0]
    target = _named_child(ports, "port", operation.old_name, "name")
    if target is None:
        raise KeyError(f"Unknown component port: {operation.old_name}")
    if _named_child(ports, "port", operation.new_name, "name") is not None:
        raise ValueError(f"Component already has a port named {operation.new_name}.")
    port_name = _child(target, "name")
    assert port_name is not None
    port_name.text = operation.new_name
    for node in component_root.xpath(".//*[local-name()='physicalPort']/*[local-name()='name']"):
        if (node.text or "").strip() == operation.old_name:
            node.text = operation.new_name
    package.add_document("component", _serialize(component_root))

    component_vlnv = _component_vlnv(package, operation.component)
    internal_design_ids = {
        item.internal_design.entity_id
        for item in package.manifest.component_compositions
        if item.component.entity_id == operation.component.entity_id
    }
    for entry in [item for item in package.manifest.documents if item.kind == "design"]:
        root = ipxact.parse_xml(package.files[entry.path])
        matching_instances: set[str] = set()
        for instance in root.xpath("./*[local-name()='componentInstances']/*[local-name()='componentInstance']"):
            component_ref = _child(instance, "componentRef")
            if component_ref is None:
                continue
            vlnv = ":".join(component_ref.get(field, "") for field in ("vendor", "library", "name", "version"))
            if vlnv == component_vlnv:
                matching_instances.add(_text(instance, "instanceName"))
        changed = False
        for node in root.xpath(".//*[local-name()='internalPortReference']"):
            if node.get("componentInstanceRef") in matching_instances and node.get("portRef") == operation.old_name:
                node.set("portRef", operation.new_name)
                changed = True
        if entry.entity_id in internal_design_ids:
            for node in root.xpath(".//*[local-name()='externalPortReference']"):
                if node.get("portRef") == operation.old_name:
                    node.set("portRef", operation.new_name)
                    changed = True
        if changed:
            package.add_document("design", _serialize(root))
        layout_annotation = package.files.get(f"annotations/circuit-layout/{entry.entity_id}.json")
        if layout_annotation is not None:
            layout = DesignCircuitLayoutV1.model_validate_json(layout_annotation)
            replacements = {
                **{
                    f"instance:{instance_name}/port:{operation.old_name}":
                    f"instance:{instance_name}/port:{operation.new_name}"
                    for instance_name in matching_instances
                },
                **({
                    f"boundary:{operation.old_name}": f"boundary:{operation.new_name}"
                } if entry.entity_id in internal_design_ids else {}),
            }

            def rename_keys(values: dict[str, typing.Any]) -> dict[str, typing.Any]:
                return {replacements.get(key, key): value for key, value in values.items()}

            routes = copy.deepcopy(layout.net_routes)
            for route in routes.values():
                for vertex in route.get("vertices", []):
                    terminal_id = vertex.get("terminal_id")
                    if terminal_id in replacements:
                        vertex["terminal_id"] = replacements[terminal_id]
            upsert_design_layout(package, layout.model_copy(update={
                "terminal_placements": rename_keys(layout.terminal_placements),
                "label_geometry": rename_keys(layout.label_geometry),
                "net_routes": routes,
            }))
        timing_annotation = package.files.get(f"annotations/circuit-timing/{entry.entity_id}.json")
        if timing_annotation is not None and entry.entity_id in internal_design_ids:
            timing = DesignCircuitTimingV1.model_validate_json(timing_annotation)
            old_key = f"boundary:{operation.old_name}"
            new_key = f"boundary:{operation.new_name}"
            overrides = dict(timing.subject_domain_overrides)
            if old_key in overrides:
                overrides[new_key] = overrides.pop(old_key)
            domains = tuple(
                domain.model_copy(update={"signal": DesignClockSignalV1(kind="boundary", id=operation.new_name)})
                if domain.signal is not None and domain.signal.kind == "boundary" and domain.signal.id == operation.old_name
                else domain
                for domain in timing.clock_domains
            )
            upsert_design_timing(package, timing.model_copy(update={"subject_domain_overrides": overrides, "clock_domains": domains}))


def _delete_component_port(package: SpecPackage, operation: DeleteComponentPort) -> None:
    """Delete an unreferenced component port; callers provide dependency policy."""
    component_vlnv = _component_vlnv(package, operation.component)
    revision = SpecRevision.from_package(package)
    internal_ids = {item.internal_design.entity_id for item in revision.manifest.component_compositions
                    if item.component.entity_id == operation.component.entity_id}
    for design in revision.designs:
        instances = {item.name for item in design.instances if item.component_vlnv == component_vlnv}
        for connection in design.connections:
            if any(item.instance_name in instances and item.port_name == operation.name for item in connection.port_endpoints) or (
                design.ref.entity_id in internal_ids and any(item.port_name == operation.name for item in connection.external_ports)
            ):
                raise ValueError(f"Port {operation.name} is used by connection {connection.name}. Remove that connection first.")
    component_root = _editable_component_root(package, operation.component, allow_composite=True)
    if component_root.xpath(
        ".//*[local-name()='physicalPort']/*[local-name()='name' and normalize-space(text())=$name]",
        name=operation.name,
    ):
        raise ValueError(f"Port {operation.name} is mapped by a bus interface and cannot be deleted.")
    model = _child(component_root, "model")
    ports = _child(model, "ports") if model is not None else None
    target = _named_child(ports, "port", operation.name, "name") if ports is not None else None
    if target is None or ports is None:
        raise KeyError(f"Unknown component port: {operation.name}")
    ports.remove(target)
    if not len(ports) and model is not None:
        model.remove(ports)
    package.add_document("component", _serialize(component_root))
    internal_design_ids = {
        item.internal_design.entity_id
        for item in package.manifest.component_compositions
        if item.component.entity_id == operation.component.entity_id
    }
    for entry in [item for item in package.manifest.documents if item.kind == "design"]:
        data = package.files.get(f"annotations/circuit-layout/{entry.entity_id}.json")
        timing_data = package.files.get(f"annotations/circuit-timing/{entry.entity_id}.json")
        if data is None and timing_data is None:
            continue
        root = ipxact.parse_xml(package.files[entry.path])
        instance_names = set()
        for instance in root.xpath("./*[local-name()='componentInstances']/*[local-name()='componentInstance']"):
            component_ref = _child(instance, "componentRef")
            if component_ref is None:
                continue
            vlnv = ":".join(component_ref.get(field, "") for field in ("vendor", "library", "name", "version"))
            if vlnv == component_vlnv:
                instance_names.add(_text(instance, "instanceName"))
        removed_keys = {f"instance:{name}/port:{operation.name}" for name in instance_names}
        if entry.entity_id in internal_design_ids:
            removed_keys.add(f"boundary:{operation.name}")
        if data is not None:
            layout = DesignCircuitLayoutV1.model_validate_json(data)
            upsert_design_layout(package, layout.model_copy(update={
                "terminal_placements": {key: value for key, value in layout.terminal_placements.items() if key not in removed_keys},
                "label_geometry": {key: value for key, value in layout.label_geometry.items() if key not in removed_keys},
            }))
        if timing_data is not None and entry.entity_id in internal_design_ids:
            timing = DesignCircuitTimingV1.model_validate_json(timing_data)
            boundary_key = f"boundary:{operation.name}"
            domains = tuple(
                domain.model_copy(update={"signal": None})
                if domain.signal is not None and domain.signal.kind == "boundary" and domain.signal.id == operation.name
                else domain
                for domain in timing.clock_domains
            )
            upsert_design_timing(package, timing.model_copy(update={
                "subject_domain_overrides": {key: value for key, value in timing.subject_domain_overrides.items() if key != boundary_key},
                "clock_domains": domains,
            }))


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
        def add_slice(node: etree._Element, endpoint_slice: typing.Any, symbolic_slice: str | None = None) -> None:
            if endpoint_slice is None and symbolic_slice is None:
                return
            part = etree.SubElement(node, _q("partSelect"))
            range_node = etree.SubElement(part, _q("range"))
            if endpoint_slice is not None:
                left = str(endpoint_slice.lsb + endpoint_slice.width - 1)
                right = str(endpoint_slice.lsb)
            else:
                left, _, right = symbolic_slice.partition(":")
            etree.SubElement(range_node, _q("left")).text = left
            etree.SubElement(range_node, _q("right")).text = right

        for endpoint in connection.port_endpoints:
            endpoint_node = etree.SubElement(references, _q("internalPortReference"), componentInstanceRef=endpoint.instance_name, portRef=endpoint.port_name)
            add_slice(endpoint_node, endpoint.slice, endpoint.symbolic_slice)
        for endpoint in connection.external_ports:
            if isinstance(endpoint, str):  # Backward-compatible internal callers.
                endpoint = ExternalPortEndpointIR(endpoint)
            endpoint_node = etree.SubElement(references, _q("externalPortReference"), portRef=endpoint.port_name)
            add_slice(endpoint_node, endpoint.slice, endpoint.symbolic_slice)
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
    if operation.block.type == "section":
        operation = dataclasses.replace(operation, block=operation.block.model_copy(update={"text": clean_name(operation.block.text)}))
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


def _set_narrative_links(package: SpecPackage, operation: SetNarrativeLinks) -> None:
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
