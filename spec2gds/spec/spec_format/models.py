"""Typed source contracts for the IP-XACT-centered V1 `.spec` package."""

import hashlib
import re
import typing
import uuid

import pydantic

MIMETYPE: str = "application/vnd.spec2gds.spec+zip"
FORMAT_VERSION: int = 1
PROFILE_VERSION: int = 1
IPXACT_VERSION: str = "1685-2022"
NARRATIVE_VERSION: int = 1
SHA256_PATTERN: re.Pattern[str] = re.compile(r"^sha256:[0-9a-f]{64}$")
ID_PATTERN: re.Pattern[str] = re.compile(r"^[A-Za-z_][A-Za-z0-9_.-]*$")
SAFE_PATH_PATTERN: re.Pattern[str] = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._/-]*$")

DocumentKind = typing.Literal[
    "component",
    "design",
    "bus_definition",
    "abstraction_definition",
]
EntityKind = typing.Literal[
    "component",
    "design",
    "bus_definition",
    "abstraction_definition",
    "narrative_block",
    "asset",
]
NarrativeBlockType = typing.Literal[
    "section",
    "paragraph",
    "list",
    "table",
    "image",
    "entity_link",
    "live_view",
]

_KIND_DIRECTORIES: dict[str, str] = {
    "component": "ipxact/components",
    "design": "ipxact/designs",
    "bus_definition": "ipxact/bus-definitions",
    "abstraction_definition": "ipxact/abstraction-definitions",
}


def sha256_digest(data: bytes) -> str:
    """Return the project-standard SHA-256 digest representation."""
    return f"sha256:{hashlib.sha256(data).hexdigest()}"


def new_entity_id(prefix: str) -> str:
    """Create a stable-format opaque identifier suitable for XML `xml:id`."""
    clean_prefix = re.sub(r"[^A-Za-z0-9_.-]", "_", prefix).strip("_.-") or "entity"
    if not clean_prefix[0].isalpha() and clean_prefix[0] != "_":
        clean_prefix = f"e_{clean_prefix}"
    return f"{clean_prefix}_{uuid.uuid4().hex}"


def validate_safe_path(value: str) -> str:
    """Reject archive paths that can escape or obscure the package layout."""
    if not value or value.startswith("/") or value.endswith("/"):
        raise ValueError("Package paths must be non-empty relative file paths.")
    if "\\" in value or "//" in value or not SAFE_PATH_PATTERN.fullmatch(value):
        raise ValueError(f"Unsafe package path: {value}")
    segments = value.split("/")
    if any(segment in {"", ".", ".."} for segment in segments):
        raise ValueError(f"Unsafe package path: {value}")
    return value


def document_directory(kind: DocumentKind) -> str:
    """Return the canonical package directory for one IP-XACT document kind."""
    return _KIND_DIRECTORIES[kind]


def validate_vlnv(value: str) -> str:
    """Validate the project string representation of an IP-XACT VLNV."""
    parts = value.split(":")
    if len(parts) != 4 or any(not part for part in parts):
        raise ValueError("VLNV must be formatted as vendor:library:name:version.")
    return value


class StrictModel(pydantic.BaseModel):
    """Base model that rejects unrecognized persisted fields."""

    model_config = pydantic.ConfigDict(extra="forbid", frozen=True)


class EntityRef(StrictModel):
    """Stable reference to a source entity in one `.spec` document."""

    document_id: str
    entity_id: str
    entity_kind: EntityKind

    @pydantic.field_validator("document_id", "entity_id")
    @classmethod
    def _validate_id(cls, value: str) -> str:
        """Require stable references to use the shared XML-compatible grammar."""
        if not ID_PATTERN.fullmatch(value):
            raise ValueError("Entity identifiers must be XML-ID-compatible opaque values.")
        return value


class DocumentEntry(StrictModel):
    """Manifest index row for one canonical IP-XACT document."""

    kind: DocumentKind
    vlnv: str
    entity_id: str
    path: str
    sha256: str

    @pydantic.field_validator("vlnv")
    @classmethod
    def _validate_vlnv(cls, value: str) -> str:
        """Validate the manifest's canonical four-part hardware identity."""
        return validate_vlnv(value)

    @pydantic.field_validator("entity_id")
    @classmethod
    def _validate_entity_id(cls, value: str) -> str:
        """Require a stable XML-compatible document identity."""
        if not ID_PATTERN.fullmatch(value):
            raise ValueError("Document entity_id must be XML-ID-compatible.")
        return value

    @pydantic.field_validator("path")
    @classmethod
    def _validate_path(cls, value: str) -> str:
        """Reject archive traversal and non-canonical paths."""
        return validate_safe_path(value)

    @pydantic.field_validator("sha256")
    @classmethod
    def _validate_sha256(cls, value: str) -> str:
        """Require a canonical source-content digest."""
        if not SHA256_PATTERN.fullmatch(value):
            raise ValueError("sha256 must use the sha256:<64 lowercase hex> format.")
        return value

    @pydantic.model_validator(mode="after")
    def _validate_kind_path(self) -> "DocumentEntry":
        """Keep each IP-XACT kind in its fixed package directory."""
        expected_prefix = document_directory(self.kind) + "/"
        if not self.path.startswith(expected_prefix) or not self.path.endswith(".xml"):
            raise ValueError(f"{self.kind} documents must be stored below {expected_prefix}.")
        return self


class AssetEntry(StrictModel):
    """Metadata for one content-addressed source asset."""

    asset_id: str
    path: str
    sha256: str
    media_type: str

    @pydantic.field_validator("asset_id")
    @classmethod
    def _validate_asset_id(cls, value: str) -> str:
        """Require a stable XML-compatible asset identity."""
        if not ID_PATTERN.fullmatch(value):
            raise ValueError("asset_id must be XML-ID-compatible.")
        return value

    @pydantic.field_validator("path")
    @classmethod
    def _validate_asset_path(cls, value: str) -> str:
        """Confine source assets to the package asset directory."""
        value = validate_safe_path(value)
        if not value.startswith("assets/"):
            raise ValueError("Assets must be stored below assets/.")
        return value

    @pydantic.field_validator("sha256")
    @classmethod
    def _validate_asset_hash(cls, value: str) -> str:
        """Require a canonical digest for immutable asset bytes."""
        if not SHA256_PATTERN.fullmatch(value):
            raise ValueError("sha256 must use the sha256:<64 lowercase hex> format.")
        return value


class AnnotationSchemaEntry(StrictModel):
    """Registered schema namespace for optional source annotations."""

    namespace: str
    version: int
    path_prefix: str

    @pydantic.field_validator("namespace")
    @classmethod
    def _validate_namespace(cls, value: str) -> str:
        """Keep annotation namespaces compact and path-safe."""
        if not value or "/" in value or " " in value:
            raise ValueError("Annotation namespaces must be compact path-safe identifiers.")
        return value

    @pydantic.field_validator("path_prefix")
    @classmethod
    def _validate_annotation_path(cls, value: str) -> str:
        """Confine extension schemas to the annotation subtree."""
        value = validate_safe_path(value)
        if not value.startswith("annotations/"):
            raise ValueError("Annotation schemas must be stored below annotations/.")
        return value


class ComponentComposition(StrictModel):
    """Project-owned link from one component to its single internal design."""

    component: EntityRef
    internal_design: EntityRef

    @pydantic.model_validator(mode="after")
    def _validate_kinds(self) -> "ComponentComposition":
        """Enforce the local component-to-design ownership relationship."""
        if self.component.entity_kind != "component":
            raise ValueError("Component composition source must be a component.")
        if self.internal_design.entity_kind != "design":
            raise ValueError("Component composition target must be a design.")
        if self.component.document_id != self.internal_design.document_id:
            raise ValueError("Component compositions cannot cross document boundaries in V1.")
        return self


class InlineNode(StrictModel):
    """Small inline node vocabulary used inside paragraph and table text."""

    type: typing.Literal["text", "emphasis", "strong", "code", "link"]
    text: str
    href: str = ""
    entity_ref: EntityRef | None = None

    @pydantic.model_validator(mode="after")
    def _validate_link(self) -> "InlineNode":
        """Require link nodes to name a URL or stable source entity."""
        if self.type == "link" and not self.href and self.entity_ref is None:
            raise ValueError("Links require href or entity_ref.")
        return self


class NarrativeBlock(StrictModel):
    """One typed narrative node with stable identity and optional children."""

    block_id: str
    type: NarrativeBlockType
    text: str = ""
    inlines: list[InlineNode] = pydantic.Field(default_factory=list)
    children: list["NarrativeBlock"] = pydantic.Field(default_factory=list)
    ordered: bool = False
    rows: list[list[str]] = pydantic.Field(default_factory=list)
    asset_id: str = ""
    alt_text: str = ""
    caption: str = ""
    entity_refs: list[EntityRef] = pydantic.Field(default_factory=list)
    renderer_id: str = ""
    options: dict[str, typing.Any] = pydantic.Field(default_factory=dict)

    @pydantic.field_validator("block_id")
    @classmethod
    def _validate_block_id(cls, value: str) -> str:
        """Require narrative identity to survive JSON and XML projections."""
        if not ID_PATTERN.fullmatch(value):
            raise ValueError("Narrative block ids must be XML-ID-compatible.")
        return value

    @pydantic.model_validator(mode="after")
    def _validate_shape(self) -> "NarrativeBlock":
        """Validate fields whose meaning depends on the narrative node type."""
        if self.type == "image" and not self.asset_id:
            raise ValueError("Image blocks require asset_id.")
        if self.type == "entity_link" and not self.entity_refs:
            raise ValueError("Entity-link blocks require at least one entity reference.")
        if self.type == "live_view" and (not self.renderer_id or len(self.entity_refs) != 1):
            raise ValueError("Live-view blocks require renderer_id and exactly one entity reference.")
        if self.type == "table" and not self.rows:
            raise ValueError("Table blocks require at least one row.")
        if self.type == "list" and not self.children:
            raise ValueError("List blocks require child blocks.")
        return self


NarrativeBlock.model_rebuild()


class NarrativeDocument(StrictModel):
    """Project-owned human-authored document tree stored beside IP-XACT XML."""

    version: int = NARRATIVE_VERSION
    document_id: str
    title: str = ""
    blocks: list[NarrativeBlock] = pydantic.Field(default_factory=list)

    @pydantic.field_validator("document_id")
    @classmethod
    def _validate_document_id(cls, value: str) -> str:
        """Require the narrative tree to carry a stable document identity."""
        if not ID_PATTERN.fullmatch(value):
            raise ValueError("Narrative document_id must be XML-ID-compatible.")
        return value

    @pydantic.field_validator("title")
    @classmethod
    def _validate_title(cls, value: str) -> str:
        """Keep the optional human-facing title compact and normalized."""
        value = value.strip()
        if len(value) > 200:
            raise ValueError("Specification title must be 200 characters or fewer.")
        return value

    @pydantic.model_validator(mode="after")
    def _validate_unique_block_ids(self) -> "NarrativeDocument":
        """Ensure every nested narrative node is addressable without ambiguity."""
        seen: set[str] = set()

        def visit(block: NarrativeBlock) -> None:
            """Collect one subtree while rejecting repeated stable ids."""
            if block.block_id in seen:
                raise ValueError(f"Narrative block id is duplicated: {block.block_id}")
            seen.add(block.block_id)
            for child in block.children:
                visit(child)

        for block in self.blocks:
            visit(block)
        return self


class SpecManifest(StrictModel):
    """Canonical source manifest for an IP-XACT-centered `.spec` package."""

    format_version: int = FORMAT_VERSION
    profile_version: int = PROFILE_VERSION
    document_id: str
    ipxact_version: str = IPXACT_VERSION
    documents: list[DocumentEntry] = pydantic.Field(default_factory=list)
    entry_designs: list[EntityRef] = pydantic.Field(default_factory=list)
    component_compositions: list[ComponentComposition] = pydantic.Field(default_factory=list)
    narrative_path: str = "document/document.json"
    assets: list[AssetEntry] = pydantic.Field(default_factory=list)
    annotation_schemas: list[AnnotationSchemaEntry] = pydantic.Field(default_factory=list)

    @pydantic.field_validator("document_id")
    @classmethod
    def _validate_document_id(cls, value: str) -> str:
        """Require the package's root identity to be XML-compatible."""
        if not ID_PATTERN.fullmatch(value):
            raise ValueError("document_id must be XML-ID-compatible.")
        return value

    @pydantic.field_validator("ipxact_version")
    @classmethod
    def _validate_ipxact_version(cls, value: str) -> str:
        """Reject schema generations outside the explicit V1 profile."""
        if value != IPXACT_VERSION:
            raise ValueError("V1 requires IP-XACT 1685-2022.")
        return value

    @pydantic.field_validator("narrative_path")
    @classmethod
    def _validate_narrative_path(cls, value: str) -> str:
        """Keep the narrative document at its single canonical path."""
        value = validate_safe_path(value)
        if value != "document/document.json":
            raise ValueError("V1 narrative_path must be document/document.json.")
        return value

    @pydantic.model_validator(mode="after")
    def _validate_manifest_relations(self) -> "SpecManifest":
        """Validate uniqueness and every cross-entity manifest relationship."""
        document_ids = [entry.entity_id for entry in self.documents]
        document_paths = [entry.path for entry in self.documents]
        document_keys = [(entry.kind, entry.vlnv) for entry in self.documents]
        if len(document_ids) != len(set(document_ids)):
            raise ValueError("Manifest document entity_ids must be unique.")
        if len(document_paths) != len(set(document_paths)):
            raise ValueError("Manifest document paths must be unique.")
        if len(document_keys) != len(set(document_keys)):
            raise ValueError("Manifest VLNV values must be unique per document kind.")

        known = {entry.entity_id: entry.kind for entry in self.documents}
        entry_ids: set[str] = set()
        for entry_design in self.entry_designs:
            if entry_design.document_id != self.document_id or entry_design.entity_kind != "design":
                raise ValueError("Entry designs must reference local design documents.")
            if known.get(entry_design.entity_id) != "design":
                raise ValueError("Entry design must reference a manifest design document.")
            if entry_design.entity_id in entry_ids:
                raise ValueError("Entry design references must be unique.")
            entry_ids.add(entry_design.entity_id)

        composition_ids: set[str] = set()
        owned_designs: set[str] = set()
        for composition in self.component_compositions:
            if (
                composition.component.document_id != self.document_id
                or composition.internal_design.document_id != self.document_id
            ):
                raise ValueError("Component compositions must reference this manifest's document.")
            if known.get(composition.component.entity_id) != "component":
                raise ValueError("Composition component must reference a manifest component.")
            if known.get(composition.internal_design.entity_id) != "design":
                raise ValueError("Composition design must reference a manifest design.")
            if composition.component.entity_id in composition_ids:
                raise ValueError("Each component can own at most one internal design.")
            if composition.internal_design.entity_id in owned_designs:
                raise ValueError("An internal design can have at most one component owner.")
            composition_ids.add(composition.component.entity_id)
            owned_designs.add(composition.internal_design.entity_id)

        asset_ids = [asset.asset_id for asset in self.assets]
        asset_paths = [asset.path for asset in self.assets]
        if len(asset_ids) != len(set(asset_ids)) or len(asset_paths) != len(set(asset_paths)):
            raise ValueError("Manifest assets must have unique ids and paths.")
        annotation_namespaces = [schema.namespace for schema in self.annotation_schemas]
        annotation_prefixes = [schema.path_prefix for schema in self.annotation_schemas]
        if len(annotation_namespaces) != len(set(annotation_namespaces)):
            raise ValueError("Annotation schema namespaces must be unique.")
        if len(annotation_prefixes) != len(set(annotation_prefixes)):
            raise ValueError("Annotation schema path prefixes must be unique.")
        return self
