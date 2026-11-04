"""Bounded catalog downloads and atomic, self-contained Component imports."""

from __future__ import annotations

import io
import json
import zipfile
from hashlib import sha256
from typing import Any, Literal

import httpx
import pydantic
from lxml import etree

from spec2gds.spec.spec_format.archive import SpecPackage
from spec2gds.spec.spec_format.circuit_layouts import load_design_layout, upsert_design_layout
from spec2gds.spec.spec_format.circuit_timings import load_design_timing, upsert_design_timing
from spec2gds.spec.spec_format.ir import SpecRevision
from spec2gds.spec.spec_format.models import (
    AnnotationSchemaEntry,
    ComponentComposition,
    EntityRef,
    NarrativeBlock,
    StrictModel,
    sha256_digest,
)
from spec2gds.spec.spec_format.naming import (
    clean_name,
    entity_name,
    hardware_name,
    unique_name,
    validate_package_names,
)
from spec2gds.spec.spec_format.sections import upsert_systemverilog_section
from spec2gds.spec.spec_format.source_edits import set_entity_metadata

ORIGIN_ROOT = "annotations/catalog-imports"
ORIGIN_PATH = f"{ORIGIN_ROOT}/index.json"
MAX_DOWNLOAD = 8 * 1024 * 1024
MAX_EXPANDED = 64 * 1024 * 1024


class CatalogImportRequest(StrictModel):
    component_key: str
    version: str
    package_sha256: str
    expected_source_revision_hash: str
    renames: dict[str, str] = pydantic.Field(default_factory=dict)
    renamed_copy: bool = False


class CatalogOriginRecord(StrictModel):
    component_key: str
    version: str
    package_sha256: str
    source_document_id: str
    source_root: EntityRef
    source_vlnv: str
    root: EntityRef
    mappings: list[dict[str, Any]]
    fingerprints: dict[str, str]
    asset_fingerprints: dict[str, str]
    asset_mappings: dict[str, str] = pydantic.Field(default_factory=dict)
    block_ids: list[str]
    narrative_fingerprint: str
    metadata: dict[str, Any]
    evidence: list[dict[str, Any]]


class CatalogOriginIndex(StrictModel):
    schema_version: Literal[1]
    imports: list[CatalogOriginRecord]


def validate_origin_annotation(manifest: Any, files: Any) -> None:
    registered = any(s.namespace == "spec2gds.catalog-imports" for s in manifest.annotation_schemas)
    if not registered and ORIGIN_PATH not in files:
        return
    if not registered or ORIGIN_PATH not in files:
        raise ValueError("Catalog origins require their annotation registration and index.")
    index = CatalogOriginIndex.model_validate_json(files[ORIGIN_PATH])
    for record in index.imports:
        if record.root.document_id != manifest.document_id:
            raise ValueError("Catalog origin destination belongs to another Spec.")


class CatalogUnavailable(RuntimeError):
    """The configured catalog could not complete a request."""


class CatalogClient:
    def __init__(self, base_url: str) -> None:
        self.base_url = base_url.rstrip("/")

    def get(self, path: str, params: dict | None = None, *, binary: bool = False) -> Any:
        try:
            with httpx.Client(timeout=30, trust_env=False) as client:
                with client.stream("GET", self.base_url + path, params=params) as response:
                    if response.status_code == 404:
                        raise KeyError("The catalog release is unavailable.")
                    if 400 <= response.status_code < 500:
                        raise ValueError(
                            "The catalog rejected this request. Check the selected release and filters."
                        )
                    response.raise_for_status()
                    data = bytearray()
                    for chunk in response.iter_bytes():
                        data.extend(chunk)
                        if len(data) > MAX_DOWNLOAD:
                            raise ValueError("Catalog response exceeds the download limit.")
            return bytes(data) if binary else json.loads(data)
        except (httpx.HTTPError, json.JSONDecodeError) as exc:
            raise CatalogUnavailable(
                "Spec Catalog is unavailable. Retry when the service is ready."
            ) from exc

    def release(self, request: CatalogImportRequest) -> tuple[SpecRevision, dict]:
        from urllib.parse import quote

        path = f"/components/{quote(request.component_key, safe='')}/versions/{quote(request.version, safe='')}"
        details = self.get(path)
        raw = self.get(path + "/download", binary=True)
        if (
            details["package_sha256"] != request.package_sha256
            or sha256_digest(raw) != request.package_sha256
        ):
            raise ValueError("The downloaded package does not match the selected release digest.")
        source = bounded_package(raw)
        metadata = details["metadata"]
        expected_vlnv = f"spec2gds.local:{metadata['category']}:{metadata['id']}:{request.version}"
        expected_key = sha256(
            f"spec2gds.local:{metadata['category']}:{metadata['id']}".encode()
        ).hexdigest()
        if request.component_key != expected_key:
            raise ValueError("The catalog Component key does not match the selected root identity.")
        root = EntityRef.model_validate(metadata["root"])
        if root.entity_kind != "component" or source.resolve(root).vlnv != expected_vlnv:
            raise ValueError("The downloaded package does not match the catalog root identity.")
        embedded = next((a for a in source.assets if a.asset_id == "library_catalogue_v1"), None)
        if embedded is None or json.loads(source.to_package().files[embedded.path]) != metadata:
            raise ValueError("The catalog metadata does not match the downloaded package.")
        for dependency in metadata.get("dependencies", []):
            try:
                local = source.resolve(EntityRef.model_validate(dependency["local_ref"]))
                if local.vlnv != dependency["vlnv"]:
                    raise ValueError("Dependency identity mismatch")
            except KeyError as exc:
                raise ValueError("The package is missing a declared catalog dependency.") from exc
        details["evidence"] = self.get(path + "/evidence")["items"]
        return source, details


def bounded_package(raw: bytes) -> SpecRevision:
    if len(raw) > MAX_DOWNLOAD:
        raise ValueError("Catalog package exceeds the download limit.")
    if not zipfile.is_zipfile(io.BytesIO(raw)):
        raise ValueError("Catalog download is not a valid .spec archive.")
    with zipfile.ZipFile(io.BytesIO(raw)) as archive:
        infos = archive.infolist()
        if len(infos) > 1024 or sum(i.file_size for i in infos) > MAX_EXPANDED:
            raise ValueError("Catalog package exceeds the expanded archive limit.")
        for info in infos:
            if (
                info.file_size > 4 * 1024 * 1024
                or info.flag_bits & 1
                or (info.external_attr >> 16) & 0o170000 == 0o120000
            ):
                raise ValueError("Catalog package contains an unsupported archive member.")
            if info.file_size > max(info.compress_size, 1) * 100:
                raise ValueError("Catalog package exceeds the compression ratio limit.")
    return SpecRevision.from_package(SpecPackage.from_bytes(raw))


def origins(revision: SpecRevision) -> list[dict]:
    raw = revision.to_package().files.get(ORIGIN_PATH)
    return (
        [
            record.model_dump(mode="json")
            for record in CatalogOriginIndex.model_validate_json(raw).imports
        ]
        if raw
        else []
    )


def _closure(revision: SpecRevision, root: EntityRef) -> list[Any]:
    result: dict[str, Any] = {}

    def visit(entity: Any) -> None:
        if entity.ref.entity_id in result:
            return
        result[entity.ref.entity_id] = entity
        if entity.ref.entity_kind == "component":
            internal = revision.internal_design(entity)
            if internal:
                visit(internal)
            for interface in entity.interfaces:
                for kind, vlnv in (
                    ("bus_definition", interface.bus_vlnv),
                    ("abstraction_definition", interface.abstraction_vlnv),
                ):
                    if vlnv:
                        visit(revision.by_vlnv(kind, vlnv))
        if entity.ref.entity_kind == "design":
            for instance in entity.instances:
                visit(revision.by_vlnv("component", instance.component_vlnv))
        if entity.ref.entity_kind == "abstraction_definition" and entity.bus_vlnv:
            visit(revision.by_vlnv("bus_definition", entity.bus_vlnv))

    visit(revision.resolve(root))
    return list(result.values())


def _fingerprint(revision: SpecRevision, ref: EntityRef) -> str:
    package = revision.to_package()
    entry = next(e for e in package.manifest.documents if e.entity_id == ref.entity_id)
    xml = etree.fromstring(
        package.files[entry.path], parser=etree.XMLParser(remove_blank_text=True)
    )
    xml.attrib.pop("{http://www.w3.org/XML/1998/namespace}id", None)
    set_entity_metadata(
        xml,
        display_name=entity_name(revision.resolve(ref)),
        short_description=xml.findtext("{*}shortDescription"),
        description=xml.findtext("{*}description"),
    )
    data = {
        "xml": etree.tostring(xml, method="c14n").decode(),
        "sections": [s.content for s in revision.entity_sections_for(ref, "sv")],
    }
    if ref.entity_kind == "component":
        internal = revision.internal_design(revision.resolve(ref))
        data["internal"] = internal.vlnv if internal else None
    if ref.entity_kind == "design":
        for label, loader in (("layout", load_design_layout), ("timing", load_design_timing)):
            annotation = loader(revision, ref)
            data[label] = (
                annotation.model_dump(mode="json", exclude={"design"}) if annotation else None
            )
    return sha256_digest(json.dumps(data, sort_keys=True).encode())


def _subtree_fingerprint(revision: SpecRevision, ref: EntityRef) -> str:
    values = sorted(
        (e.ref.entity_kind, e.vlnv, _fingerprint(revision, e.ref)) for e in _closure(revision, ref)
    )
    return sha256_digest(json.dumps(values, sort_keys=True).encode())


def _unchanged(revision: SpecRevision, record: dict) -> bool:
    try:
        for entity_id, fingerprint in record["fingerprints"].items():
            entry = next(
                e for e in revision.to_package().manifest.documents if e.entity_id == entity_id
            )
            if (
                _fingerprint(
                    revision,
                    EntityRef(
                        document_id=revision.document_id,
                        entity_id=entity_id,
                        entity_kind=entry.kind,
                    ),
                )
                != fingerprint
            ):
                return False
        package = revision.to_package()
        if any(
            sha256_digest(package.files.get(path, b"")) != digest
            for path, digest in record.get("asset_fingerprints", {}).items()
        ):
            return False
        block_ids = set(record.get("block_ids", []))
        blocks = [
            b.model_dump(mode="json") for b in package.narrative.blocks if b.block_id in block_ids
        ]
        return sha256_digest(json.dumps(blocks, sort_keys=True).encode()) == record.get(
            "narrative_fingerprint"
        )
    except (KeyError, StopIteration):
        return False


def prepare_import(
    destination: SpecRevision, source: SpecRevision, details: dict, request: CatalogImportRequest
) -> tuple[dict, SpecRevision | None]:
    """Return a reviewable mapping and a detached candidate; never save source."""
    if destination.source_revision_hash != request.expected_source_revision_hash:
        raise ValueError("Stale Spec revision. Refresh the import preview.")
    root = EntityRef.model_validate(details["metadata"]["root"])
    entities = _closure(source, root)
    records = origins(destination)
    if not request.renamed_copy and not request.renames:
        for record in records:
            if (
                record["component_key"] == request.component_key
                and record["package_sha256"] == request.package_sha256
                and _unchanged(destination, record)
            ):
                return {
                    "can_import": True,
                    "reused": True,
                    "root": record["root"],
                    "definitions": record["mappings"],
                    "conflicts": [],
                }, destination
    source_pkg, target = source.to_package(), destination.to_package()
    supported = {"spec2gds.entity-sections", "spec2gds.circuit-layout", "spec2gds.circuit-timing"}
    for schema in source_pkg.manifest.annotation_schemas:
        if schema.namespace not in supported:
            raise ValueError(f"Import does not support annotation namespace {schema.namespace}.")
    existing = [
        destination.resolve(
            EntityRef(
                document_id=destination.document_id, entity_id=e.entity_id, entity_kind=e.kind
            )
        )
        for e in target.manifest.documents
    ]
    occupied_names = [entity_name(e) for e in existing]
    occupied_symbols = [e.vlnv.split(":")[2] for e in existing]
    vlnvs: dict[str, str] = {}
    refs: dict[str, EntityRef] = {}
    rows, conflicts, reused_ids = [], [], set()
    private_designs: set[str] = set()
    seed = sha256(
        json.dumps(
            [
                destination.document_id,
                destination.source_revision_hash,
                request.package_sha256,
                request.renames,
                request.renamed_copy,
            ],
            sort_keys=True,
        ).encode()
    ).hexdigest()[:12]
    for entity in entities:
        eid = entity.ref.entity_id
        matching = next((e for e in existing if e.vlnv == entity.vlnv), None)
        if (
            entity.ref != root
            and matching
            and eid not in private_designs
            and _subtree_fingerprint(source, entity.ref)
            == _subtree_fingerprint(destination, matching.ref)
        ):
            refs[eid] = matching.ref
            vlnvs[entity.vlnv] = matching.vlnv
            reused_ids.add(eid)
            rows.append(
                {
                    "source_id": eid,
                    "name": entity_name(matching),
                    "vlnv": matching.vlnv,
                    "reused": True,
                    "target": refs[eid].model_dump(mode="json"),
                }
            )
            continue
        if entity.ref.entity_kind == "component":
            internal = source.internal_design(entity)
            if internal:
                private_designs.add(internal.ref.entity_id)
        proposed = request.renames.get(eid, entity_name(entity))
        suggested = unique_name(proposed, occupied_names)
        collision = matching is not None or suggested != proposed
        renamed = request.renamed_copy or eid in request.renames
        if collision and not renamed:
            conflicts.append(
                {
                    "source_id": eid,
                    "name": proposed,
                    "suggested_name": suggested,
                    "reason": "A definition with this name or identity already exists.",
                }
            )
        name = clean_name(
            suggested if request.renamed_copy and eid not in request.renames else proposed
        )
        if name in occupied_names or unique_name(name, occupied_names) != name:
            conflicts.append(
                {
                    "source_id": eid,
                    "name": name,
                    "suggested_name": suggested,
                    "reason": "Choose a unique name.",
                }
            )
        symbol = hardware_name(name, occupied_symbols)
        vlnv = f"spec2gds.local:work:{symbol}:1.0" if renamed else entity.vlnv
        new_id = f"import_{seed}_{eid}"
        if any(e.entity_id == new_id for e in target.manifest.documents):
            new_id += "_" + sha256(destination.source_revision_hash.encode()).hexdigest()[:8]
        refs[eid] = EntityRef(
            document_id=destination.document_id,
            entity_id=new_id,
            entity_kind=entity.ref.entity_kind,
        )
        vlnvs[entity.vlnv] = vlnv
        rows.append(
            {
                "source_id": eid,
                "name": name,
                "vlnv": vlnv,
                "reused": False,
                "target": refs[eid].model_dump(mode="json"),
            }
        )
        occupied_names.append(name)
        occupied_symbols.append(symbol)
    preview = {
        "can_import": not conflicts,
        "reused": False,
        "root": refs[root.entity_id].model_dump(mode="json"),
        "definitions": rows,
        "conflicts": conflicts,
    }
    if conflicts:
        return preview, None
    for entity, row in zip(entities, rows):
        if entity.ref.entity_id in reused_ids:
            continue
        entry = next(
            e for e in source_pkg.manifest.documents if e.entity_id == entity.ref.entity_id
        )
        xml = etree.fromstring(source_pkg.files[entry.path])
        xml.set("{http://www.w3.org/XML/1998/namespace}id", refs[entity.ref.entity_id].entity_id)
        for node in xml.iter():
            if (
                not isinstance(node.tag, str)
                or etree.QName(node).namespace != etree.QName(xml).namespace
                or etree.QName(node).localname not in {"componentRef", "busType", "abstractionRef"}
            ):
                continue
            reference = ":".join(node.get(k, "") for k in ("vendor", "library", "name", "version"))
            if reference in vlnvs:
                for k, value in zip(
                    ("vendor", "library", "name", "version"), vlnvs[reference].split(":")
                ):
                    node.set(k, value)
        for field, value in zip(("vendor", "library", "name", "version"), row["vlnv"].split(":")):
            xml.find(f"{{*}}{field}").text = value
        set_entity_metadata(
            xml,
            display_name=row["name"],
            short_description=xml.findtext("{*}shortDescription"),
            description=xml.findtext("{*}description"),
        )
        target.add_document(entry.kind, etree.tostring(xml, encoding="utf-8", xml_declaration=True))
    compositions = list(target.manifest.component_compositions)
    for composition in source_pkg.manifest.component_compositions:
        if (
            composition.component.entity_id in refs
            and composition.component.entity_id not in reused_ids
        ):
            compositions.append(
                ComponentComposition(
                    component=refs[composition.component.entity_id],
                    internal_design=refs[composition.internal_design.entity_id],
                )
            )
    target.manifest = target.manifest.model_copy(update={"component_compositions": compositions})
    for section in source.entity_sections:
        if section.parent.entity_id in refs and section.parent.entity_id not in reused_ids:
            upsert_systemverilog_section(
                target,
                refs[section.parent.entity_id],
                section.content,
                f"import_{seed}_{section.section_id}",
            )
    for entity in entities:
        if entity.ref.entity_kind == "design" and entity.ref.entity_id not in reused_ids:
            for loader, writer in (
                (load_design_layout, upsert_design_layout),
                (load_design_timing, upsert_design_timing),
            ):
                annotation = loader(source, entity.ref)
                if annotation:
                    writer(
                        target, annotation.model_copy(update={"design": refs[entity.ref.entity_id]})
                    )
    asset_ids, asset_fingerprints = {}, {}
    for asset in source.assets:
        same = next((a for a in target.manifest.assets if a.path == asset.path), None)
        copied = same or target.add_asset(
            f"import_{seed}_{asset.asset_id}",
            source_pkg.files[asset.path],
            asset.media_type,
            asset.path.rsplit(".", 1)[1],
        )
        asset_ids[asset.asset_id] = copied.asset_id
        asset_fingerprints[copied.path] = copied.sha256

    narrative_refs = {(ref.entity_kind, old): ref for old, ref in refs.items()}
    narrative_refs.update(
        {
            ("asset", old): EntityRef(
                document_id=destination.document_id, entity_id=new, entity_kind="asset"
            )
            for old, new in asset_ids.items()
        }
    )

    def map_blocks(blocks: list[NarrativeBlock]) -> None:
        for block in blocks:
            narrative_refs[("narrative_block", block.block_id)] = EntityRef(
                document_id=destination.document_id,
                entity_id=f"import_{seed}_{block.block_id}",
                entity_kind="narrative_block",
            )
            map_blocks(block.children)

    map_blocks(source_pkg.narrative.blocks)

    def remap_options(value: Any) -> Any:
        if isinstance(value, dict):
            if set(value) == {"document_id", "entity_id", "entity_kind"}:
                old = EntityRef.model_validate(value)
                if (
                    old.document_id != source.document_id
                    or (old.entity_kind, old.entity_id) not in narrative_refs
                ):
                    raise ValueError(
                        "Narrative options reference content outside the imported closure."
                    )
                return narrative_refs[(old.entity_kind, old.entity_id)].model_dump(mode="json")
            return {key: remap_options(item) for key, item in value.items()}
        if isinstance(value, list):
            return [remap_options(item) for item in value]
        return value

    def block_copy(block: NarrativeBlock) -> NarrativeBlock | None:
        if block.entity_refs and not any(
            (r.entity_kind, r.entity_id) in narrative_refs for r in block.entity_refs
        ):
            return None
        children = [copied for b in block.children if (copied := block_copy(b)) is not None]
        if block.type == "list" and not children:
            return None
        inlines = []
        for node in block.inlines:
            if node.entity_ref:
                copied = narrative_refs.get(
                    (node.entity_ref.entity_kind, node.entity_ref.entity_id)
                )
                inlines.append(
                    node.model_copy(update={"entity_ref": copied})
                    if copied
                    else node.model_copy(update={"type": "text", "href": "", "entity_ref": None})
                )
            else:
                inlines.append(node)
        return block.model_copy(
            update={
                "block_id": f"import_{seed}_{block.block_id}",
                "entity_refs": [
                    narrative_refs[(r.entity_kind, r.entity_id)]
                    for r in block.entity_refs
                    if (r.entity_kind, r.entity_id) in narrative_refs
                ],
                "asset_id": asset_ids.get(block.asset_id, block.asset_id),
                "children": children,
                "inlines": inlines,
                "options": remap_options(block.options),
            }
        )

    block_ids = []
    if source_pkg.narrative.blocks:
        wrapper = NarrativeBlock(
            block_id=f"import_{seed}_narrative",
            type="section",
            text=unique_name(
                f"Imported {rows[0]['name']}",
                [b.text for b in target.narrative.blocks if b.type == "section"],
            ),
            children=[
                copied for b in source_pkg.narrative.blocks if (copied := block_copy(b)) is not None
            ],
        )
        target.narrative = target.narrative.model_copy(
            update={"blocks": [*target.narrative.blocks, wrapper]}
        )
        block_ids.append(wrapper.block_id)
    validate_package_names(target)
    candidate = SpecRevision.from_package(target)
    copied_refs = list(refs.values())
    record = {
        "component_key": request.component_key,
        "version": request.version,
        "package_sha256": request.package_sha256,
        "source_document_id": source.document_id,
        "source_root": root.model_dump(mode="json"),
        "source_vlnv": source.resolve(root).vlnv,
        "root": refs[root.entity_id].model_dump(mode="json"),
        "mappings": rows,
        "fingerprints": {r.entity_id: _fingerprint(candidate, r) for r in copied_refs},
        "asset_fingerprints": asset_fingerprints,
        "asset_mappings": asset_ids,
        "block_ids": block_ids,
        "narrative_fingerprint": sha256_digest(
            json.dumps(
                [
                    b.model_dump(mode="json")
                    for b in target.narrative.blocks
                    if b.block_id in block_ids
                ],
                sort_keys=True,
            ).encode()
        ),
        "metadata": details["metadata"],
        "evidence": details.get("evidence", []),
    }
    target.files[ORIGIN_PATH] = (
        json.dumps({"schema_version": 1, "imports": [*records, record]}, indent=2, sort_keys=True)
        + "\n"
    ).encode()
    schemas = [
        s for s in target.manifest.annotation_schemas if s.namespace != "spec2gds.catalog-imports"
    ]
    target.manifest = target.manifest.model_copy(
        update={
            "annotation_schemas": [
                *schemas,
                AnnotationSchemaEntry(
                    namespace="spec2gds.catalog-imports", version=1, path_prefix=ORIGIN_ROOT
                ),
            ]
        }
    )
    return preview, SpecRevision.from_package(target)
