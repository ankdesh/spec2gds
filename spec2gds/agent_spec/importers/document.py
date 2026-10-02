"""Build validated V1 ``.spec`` packages from Docling-parsed documents.

Reviewer path: imported text/media become narrative provenance. Optional
structured extraction is a separate configured step; parser headings and lists
do not by themselves establish validated IP-XACT hardware semantics.
"""

from __future__ import annotations

import hashlib
import importlib.metadata
import json
from dataclasses import dataclass
from pathlib import Path

from spec2gds.agent_spec.importers.docling_reader import (
    DoclingDocumentReader,
    ParsedDocument,
    ParsedImage,
    ParsedTable,
    ParsedText,
)
from spec2gds.agent_spec.importers.ipxact_from_tables import (
    HardwareTableEnricher,
    HardwareTableExtraction,
    add_extracted_ipxact,
    xml_identifier,
)
from spec2gds.agent_spec.spec_format.archive import SpecPackage
from spec2gds.agent_spec.spec_format.models import (
    AnnotationSchemaEntry,
    EntityRef,
    NarrativeBlock,
    NarrativeDocument,
    sha256_digest,
)

_ANNOTATION_ROOT = "annotations/document_import"


@dataclass(frozen=True)
class DocumentImportOptions:
    """Stable source identities and IP-XACT defaults for one import."""

    vendor: str = "spec2gds.imported"
    library: str = "documents"
    component_name: str = ""
    component_version: str = "1.0"
    document_id: str = ""


@dataclass(frozen=True)
class DocumentImportResult:
    """User-facing summary of a completed conversion."""

    output_path: Path
    document_id: str
    source_hash: str
    block_count: int
    table_count: int
    image_count: int
    port_count: int
    interface_count: int
    openai_model: str = ""


@dataclass
class _IdFactory:
    """Issue readable, deterministic narrative identifiers."""

    stem: str
    count: int = 0

    def next(self, kind: str) -> str:
        self.count += 1
        return f"{self.stem}_{kind}_{self.count:04d}"


def _json_bytes(value: object) -> bytes:
    """Serialize deterministic UTF-8 annotation JSON."""
    return (
        json.dumps(value, ensure_ascii=False, indent=2, sort_keys=True, separators=(",", ": "))
        + "\n"
    ).encode("utf-8")


def _docling_version() -> str:
    """Return the installed version without making conversion depend on metadata."""
    try:
        return importlib.metadata.version("docling")
    except importlib.metadata.PackageNotFoundError:
        return "unknown"


def _count_blocks(blocks: list[NarrativeBlock]) -> int:
    """Count every node in a narrative tree."""
    return sum(1 + _count_blocks(block.children) for block in blocks)


class _NarrativeBuilder:
    """Project parsed items into the typed V1 narrative tree and package assets."""

    def __init__(self, package: SpecPackage, parsed: ParsedDocument, ids: _IdFactory) -> None:
        self.package = package
        self.ids = ids
        self.root = NarrativeBlock(
            block_id=ids.next("section"),
            type="section",
            text=parsed.title,
            children=[],
        )
        self.sections: list[tuple[int, NarrativeBlock]] = [(-1, self.root)]
        self.asset_by_digest: dict[str, str] = {}
        self.image_count = 0
        self.table_count = 0
        self._last_list: tuple[NarrativeBlock, int, NarrativeBlock] | None = None

    @property
    def parent(self) -> NarrativeBlock:
        return self.sections[-1][1]

    def add_provenance(self, source_path: str) -> None:
        """Place an auditable source pointer at the start of the narrative."""
        self.root.children.append(
            NarrativeBlock(
                block_id=self.ids.next("paragraph"),
                type="paragraph",
                text=(
                    "Imported with Docling. Original source bytes are retained at "
                    f"{source_path}."
                ),
            )
        )

    def add_component_link(self, component_entity_id: str) -> None:
        """Link generated formal structure from the imported narrative."""
        self.root.children.insert(
            1,
            NarrativeBlock(
                block_id=self.ids.next("component"),
                type="entity_link",
                text="IP-XACT component extracted from source tables",
                entity_refs=[
                    EntityRef(
                        document_id=self.package.manifest.document_id,
                        entity_id=component_entity_id,
                        entity_kind="component",
                    )
                ],
            ),
        )

    def add(self, item: ParsedText | ParsedTable | ParsedImage) -> None:
        """Add one parsed item in source reading order."""
        if isinstance(item, ParsedText):
            self._add_text(item)
        elif isinstance(item, ParsedTable):
            self._last_list = None
            self.parent.children.append(
                NarrativeBlock(
                    block_id=self.ids.next("table"),
                    type="table",
                    rows=[list(row) for row in item.rows],
                )
            )
            self.table_count += 1
        else:
            self._last_list = None
            self._add_image(item)

    def _add_text(self, item: ParsedText) -> None:
        """Project parser text into narrative blocks without inventing hardware semantics.

        Section levels maintain a parent stack; adjacent compatible list items share
        one list block. Titles are handled outside this body projection.
        """
        if item.kind == "title":
            self._last_list = None
            return
        if item.kind == "section":
            self._last_list = None
            while len(self.sections) > 1 and self.sections[-1][0] >= item.level:
                self.sections.pop()
            section = NarrativeBlock(
                block_id=self.ids.next("section"),
                type="section",
                text=item.text,
                children=[],
            )
            self.parent.children.append(section)
            self.sections.append((item.level, section))
            return
        if item.kind == "list_item":
            if (
                self._last_list is None
                or self._last_list[0] is not self.parent
                or self._last_list[1] != item.level
            ):
                list_block = NarrativeBlock(
                    block_id=self.ids.next("list"),
                    type="list",
                    children=[
                        NarrativeBlock(
                            block_id=self.ids.next("item"),
                            type="paragraph",
                            text=item.text,
                        )
                    ],
                )
                self.parent.children.append(list_block)
                self._last_list = (self.parent, item.level, list_block)
            else:
                self._last_list[2].children.append(
                    NarrativeBlock(
                        block_id=self.ids.next("item"),
                        type="paragraph",
                        text=item.text,
                    )
                )
            return
        self._last_list = None
        self.parent.children.append(
            NarrativeBlock(
                block_id=self.ids.next("paragraph"),
                type="paragraph",
                text=item.text,
            )
        )

    def _add_image(self, item: ParsedImage) -> None:
        digest = hashlib.sha256(item.data).hexdigest()
        asset_id = self.asset_by_digest.get(digest)
        if asset_id is None:
            self.image_count += 1
            asset_id = f"import_image_{self.image_count:04d}"
            asset = self.package.add_asset(asset_id, item.data, "image/png", "png")
            self.asset_by_digest[digest] = asset.asset_id
        self.parent.children.append(
            NarrativeBlock(
                block_id=self.ids.next("image"),
                type="image",
                asset_id=asset_id,
                alt_text=item.alt_text,
                caption=item.caption,
            )
        )


class DocumentToSpecConverter:
    """Coordinate Docling parsing, optional table enrichment, and package I/O."""

    def __init__(
        self,
        *,
        reader: DoclingDocumentReader | None = None,
        enricher: HardwareTableEnricher | None = None,
    ) -> None:
        self.reader = reader or DoclingDocumentReader()
        self.enricher = enricher

    def convert(
        self,
        input_path: Path,
        output_path: Path,
        *,
        options: DocumentImportOptions | None = None,
    ) -> DocumentImportResult:
        """Convert one local source file and save a validated ``.spec`` package."""
        parsed = self.reader.convert(input_path)
        package, extraction, table_count, image_count = self.build_package(
            parsed,
            input_path=input_path,
            options=options,
        )
        package.save(str(output_path))
        return DocumentImportResult(
            output_path=output_path,
            document_id=package.manifest.document_id,
            source_hash=package.source_hash(),
            block_count=_count_blocks(package.narrative.blocks),
            table_count=table_count,
            image_count=image_count,
            port_count=len(extraction.ports) if extraction else 0,
            interface_count=len(extraction.bus_interfaces) if extraction else 0,
            openai_model=self.enricher.model if extraction is not None and self.enricher else "",
        )

    def build_package(
        self,
        parsed: ParsedDocument,
        *,
        input_path: Path,
        options: DocumentImportOptions | None = None,
    ) -> tuple[SpecPackage, HardwareTableExtraction | None, int, int]:
        """Build an in-memory package from parsed content for tests and embedding."""
        options = options or DocumentImportOptions()
        source_bytes = input_path.read_bytes()
        stem = xml_identifier(input_path.stem)
        document_id = options.document_id or f"spec_import_{stem}"
        package = SpecPackage.create(document_id)
        package.manifest = package.manifest.model_copy(
            update={
                "annotation_schemas": [
                    AnnotationSchemaEntry(
                        namespace="document_import",
                        version=1,
                        path_prefix=_ANNOTATION_ROOT,
                    )
                ]
            }
        )
        suffix = input_path.suffix.lower()
        if not suffix or not suffix.lstrip(".").isalnum():
            suffix = ".bin"
        source_annotation = f"{_ANNOTATION_ROOT}/source{suffix}"
        package.files[source_annotation] = source_bytes

        tables = [item.rows for item in parsed.items if isinstance(item, ParsedTable)]
        extraction: HardwareTableExtraction | None = None
        component = None
        if self.enricher is not None and tables:
            extraction = self.enricher.extract(tables, document_title=parsed.title)
            component = add_extracted_ipxact(
                package,
                extraction,
                vendor=options.vendor,
                library=options.library,
                component_name=options.component_name or stem,
                version=options.component_version,
            )
            package.files[f"{_ANNOTATION_ROOT}/openai-extraction.json"] = _json_bytes(
                {
                    "model": self.enricher.model,
                    "result": extraction.model_dump(mode="json"),
                }
            )

        package.files[f"{_ANNOTATION_ROOT}/import.json"] = _json_bytes(
            {
                "docling_version": _docling_version(),
                "format": "spec2gds-document-import-v1",
                "source_name": input_path.name,
                "source_path": source_annotation,
                "source_sha256": sha256_digest(source_bytes),
            }
        )

        ids = _IdFactory(f"import_{stem}")
        builder = _NarrativeBuilder(package, parsed, ids)
        builder.add_provenance(source_annotation)
        if component is not None:
            builder.add_component_link(component.entity_id)
        for item in parsed.items:
            builder.add(item)
        package.narrative = NarrativeDocument(
            document_id=package.manifest.document_id,
            blocks=[builder.root],
        )
        package.require_valid()
        return package, extraction, builder.table_count, builder.image_count
