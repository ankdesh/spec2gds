"""Deterministic custom ZIP package support for the V1 `.spec` format.

Reviewer path: validate container paths and manifest references before use,
compute source-only identity, then publish deterministic bytes atomically.
Activity history is preserved but must not change the semantic source hash.
"""

import copy
import io
import json
import os
import pathlib
import tempfile
import typing
import zipfile

import pydantic

from spec2gds.spec.spec_format import ipxact
from spec2gds.spec.spec_format.models import (
    MIMETYPE,
    AssetEntry,
    DocumentEntry,
    DocumentKind,
    EntityRef,
    NarrativeDocument,
    SpecManifest,
    document_directory,
    new_entity_id,
    sha256_digest,
    validate_safe_path,
)
from spec2gds.spec.spec_format.sections import load_entity_sections

_FIXED_ZIP_DATE: tuple[int, int, int, int, int, int] = (1980, 1, 1, 0, 0, 0)
_REQUIRED_PATHS: set[str] = {"mimetype", "manifest.json", "document/document.json"}
_ALLOWED_TOP_LEVELS: set[str] = {"mimetype", "manifest.json", "ipxact", "document", "assets", "annotations", "activity"}


class SpecValidationError(ValueError):
    """Raised when a package violates the V1 format, profile, or source rules."""

    def __init__(self, diagnostics: list[str]) -> None:
        """Join diagnostics for humans while retaining the structured list."""
        super().__init__("; ".join(diagnostics))
        self.diagnostics = diagnostics


def _json_bytes(value: typing.Any) -> bytes:
    """Serialize a Pydantic model or JSON-compatible value deterministically."""
    if hasattr(value, "model_dump"):
        value = value.model_dump(mode="json")
    return (json.dumps(value, ensure_ascii=False, indent=2, sort_keys=True) + "\n").encode("utf-8")


def _zip_info(path: str, compression: int) -> zipfile.ZipInfo:
    """Build deterministic ZIP metadata for one file entry."""
    info = zipfile.ZipInfo(path, date_time=_FIXED_ZIP_DATE)
    info.compress_type = compression
    info.create_system = 3
    info.external_attr = 0o100644 << 16
    return info


def _safe_entry_path(path: str) -> str:
    """Validate an archive entry path and restrict it to the V1 layout."""
    path = validate_safe_path(path)
    top_level = path.split("/", 1)[0]
    if top_level not in _ALLOWED_TOP_LEVELS:
        raise ValueError(f"Unexpected V1 package path: {path}")
    if path == "mimetype" or path == "manifest.json" or path == "document/document.json":
        return path
    if top_level == "ipxact" and path.endswith(".xml"):
        return path
    if top_level in {"assets", "annotations", "activity"} and "/" in path:
        return path
    raise ValueError(f"Unexpected V1 package path: {path}")


class SpecPackage:
    """Mutable construction facade over one validated V1 source package."""

    def __init__(
        self,
        manifest: SpecManifest,
        narrative: NarrativeDocument,
        files: dict[str, bytes] | None = None,
        path: str | None = None,
    ) -> None:
        """Create a working package from already typed source structures."""
        self.manifest = manifest
        self.narrative = narrative
        self.files: dict[str, bytes] = copy.deepcopy(files or {})
        self.path = path

    @classmethod
    def create(cls, document_id: str | None = None, title: str | None = None) -> "SpecPackage":
        """Create an empty V1 package with a matching narrative document."""
        identity = document_id or new_entity_id("spec")
        return cls(
            manifest=SpecManifest(document_id=identity),
            narrative=NarrativeDocument(document_id=identity, title=title or ""),
        )

    @classmethod
    def load(cls, path: str) -> "SpecPackage":
        """Load a V1 package and reject every unsupported container format."""
        package_path = pathlib.Path(path)
        if not package_path.exists():
            raise FileNotFoundError(path)
        package = cls.from_bytes(package_path.read_bytes())
        package.path = str(package_path)
        return package

    @classmethod
    def from_bytes(cls, data: bytes) -> "SpecPackage":
        """Load a validated V1 package from immutable in-memory bytes."""
        try:
            with zipfile.ZipFile(io.BytesIO(data), "r") as archive:
                names = archive.namelist()
                if len(names) != len(set(names)):
                    raise SpecValidationError(["ZIP package contains duplicate entries."])
                if not names or names[0] != "mimetype":
                    raise SpecValidationError(["V1 package must store mimetype as the first ZIP entry."])
                if "mimetype" not in names:
                    raise SpecValidationError(["Missing required package entry: mimetype"])
                mimetype_info = archive.getinfo("mimetype")
                if mimetype_info.compress_type != zipfile.ZIP_STORED:
                    raise SpecValidationError(["V1 mimetype entry must be uncompressed."])
                if archive.read("mimetype") != MIMETYPE.encode("ascii"):
                    raise SpecValidationError(["Unsupported package mimetype."])
                for info in archive.infolist():
                    if info.is_dir():
                        raise SpecValidationError([f"V1 package cannot contain directory entry: {info.filename}"])
                    try:
                        _safe_entry_path(info.filename)
                    except ValueError as exc:
                        raise SpecValidationError([str(exc)]) from exc
                if not _REQUIRED_PATHS.issubset(names):
                    missing = sorted(_REQUIRED_PATHS - set(names))
                    raise SpecValidationError(["Missing required package entries: " + ", ".join(missing)])
                try:
                    manifest = SpecManifest.model_validate_json(archive.read("manifest.json"))
                    narrative = NarrativeDocument.model_validate_json(archive.read("document/document.json"))
                except Exception as exc:
                    raise SpecValidationError([f"Failed to parse V1 JSON metadata: {exc}"]) from exc
                files = {
                    name: archive.read(name)
                    for name in names
                    if name not in {"mimetype", "manifest.json", "document/document.json"}
                }
        except zipfile.BadZipFile as exc:
            raise SpecValidationError([f"Invalid .spec ZIP package: {exc}"]) from exc
        package = cls(manifest=manifest, narrative=narrative, files=files)
        package.require_valid()
        return package

    @classmethod
    def from_directory(cls, directory: str) -> "SpecPackage":
        """Read an unpacked V1 package directory for the `pack` CLI command."""
        root = pathlib.Path(directory)
        if not root.is_dir():
            raise NotADirectoryError(directory)
        paths = [path for path in root.rglob("*") if path.is_file()]
        entries: dict[str, bytes] = {}
        for path in paths:
            relative = path.relative_to(root).as_posix()
            _safe_entry_path(relative)
            entries[relative] = path.read_bytes()
        if "manifest.json" not in entries or "document/document.json" not in entries:
            raise SpecValidationError(["Unpacked package is missing manifest.json or document/document.json."])
        if entries.get("mimetype") != MIMETYPE.encode("ascii"):
            raise SpecValidationError(["Unpacked package has an unsupported or missing mimetype."])
        manifest = SpecManifest.model_validate_json(entries.pop("manifest.json"))
        narrative = NarrativeDocument.model_validate_json(entries.pop("document/document.json"))
        entries.pop("mimetype")
        package = cls(manifest=manifest, narrative=narrative, files=entries)
        package.require_valid()
        return package

    def add_document(self, kind: DocumentKind, xml_bytes: bytes) -> DocumentEntry:
        """Validate, normalize, and add one canonical IP-XACT source document."""
        normalized, vlnv, entity_id = ipxact.validate_ipxact_document(xml_bytes, kind)
        filename = "-".join(part.replace("/", "_").replace(" ", "_") for part in vlnv.split(":")) + ".xml"
        path = f"{document_directory(kind)}/{filename}"
        entry = DocumentEntry(
            kind=kind,
            vlnv=vlnv,
            entity_id=entity_id,
            path=path,
            sha256=sha256_digest(normalized),
        )
        replaced = [item for item in self.manifest.documents if item.entity_id == entity_id]
        replacement_index = next(
            (index for index, item in enumerate(self.manifest.documents) if item.entity_id == entity_id),
            None,
        )
        documents = [item for item in self.manifest.documents if item.entity_id != entity_id]
        if any(item.path == path for item in documents):
            raise ValueError(f"Document path collision for VLNV: {vlnv}")
        if replacement_index is None:
            documents.append(entry)
        else:
            documents.insert(replacement_index, entry)
        self.manifest = self.manifest.model_copy(update={"documents": documents})
        for previous in replaced:
            self.files.pop(previous.path, None)
        self.files[path] = normalized
        return entry

    def add_asset(self, asset_id: str, data: bytes, media_type: str, extension: str) -> AssetEntry:
        """Add one content-addressed narrative asset and update manifest metadata."""
        clean_extension = extension.lstrip(".").lower()
        if not clean_extension or not clean_extension.replace("-", "").isalnum():
            raise ValueError("Asset extension must be a simple alphanumeric suffix.")
        digest = sha256_digest(data)
        path = f"assets/{digest.removeprefix('sha256:')}.{clean_extension}"
        asset = AssetEntry(asset_id=asset_id, path=path, sha256=digest, media_type=media_type)
        assets = [item for item in self.manifest.assets if item.asset_id != asset_id]
        if any(item.path == path and item.asset_id != asset_id for item in assets):
            raise ValueError("Asset content hash is already registered under a different asset id.")
        assets.append(asset)
        self.manifest = self.manifest.model_copy(update={"assets": assets})
        self.files[path] = bytes(data)
        return asset

    def source_hash(self) -> str:
        """Hash logical source entries while deliberately excluding activity metadata."""
        self.require_valid()
        source_entries: dict[str, bytes] = {
            "manifest.json": _json_bytes(self.manifest),
            "document/document.json": _json_bytes(self.narrative),
        }
        for path, data in self.files.items():
            if not path.startswith("activity/"):
                source_entries[path] = data
        material = b"".join(
            path.encode("utf-8") + b"\0" + source_entries[path] + b"\0"
            for path in sorted(source_entries)
        )
        return sha256_digest(material)

    def diagnostics(self) -> list[str]:
        """Return all package/profile diagnostics without mutating the package."""
        diagnostics: list[str] = []
        try:
            self.manifest = SpecManifest.model_validate(self.manifest.model_dump(mode="json"))
            self.narrative = NarrativeDocument.model_validate(self.narrative.model_dump(mode="json"))
        except Exception as exc:
            return [f"Invalid typed metadata: {exc}"]
        if self.manifest.document_id != self.narrative.document_id:
            diagnostics.append("Manifest and narrative document_id must match.")

        expected_document_paths = {entry.path for entry in self.manifest.documents}
        actual_document_paths = {path for path in self.files if path.startswith("ipxact/")}
        if expected_document_paths != actual_document_paths:
            diagnostics.append("Manifest document entries do not match embedded IP-XACT paths.")
        for entry in self.manifest.documents:
            data = self.files.get(entry.path)
            if data is None:
                diagnostics.append(f"Missing embedded document: {entry.path}")
                continue
            if sha256_digest(data) != entry.sha256:
                diagnostics.append(f"Document hash mismatch: {entry.path}")
                continue
            try:
                _, vlnv, entity_id = ipxact.validate_ipxact_document(data, entry.kind)
                if vlnv != entry.vlnv:
                    diagnostics.append(f"Document VLNV mismatch: {entry.path}")
                if entity_id != entry.entity_id:
                    diagnostics.append(f"Document xml:id mismatch: {entry.path}")
            except ValueError as exc:
                diagnostics.append(f"Invalid IP-XACT document {entry.path}: {exc}")

        expected_asset_paths = {asset.path for asset in self.manifest.assets}
        actual_asset_paths = {path for path in self.files if path.startswith("assets/")}
        if expected_asset_paths != actual_asset_paths:
            diagnostics.append("Manifest asset entries do not match embedded asset paths.")
        for asset in self.manifest.assets:
            data = self.files.get(asset.path)
            if data is None:
                diagnostics.append(f"Missing embedded asset: {asset.path}")
            elif sha256_digest(data) != asset.sha256:
                diagnostics.append(f"Asset hash mismatch: {asset.path}")

        known_entities = {entry.entity_id: entry.kind for entry in self.manifest.documents}
        known_entities.update({asset.asset_id: "asset" for asset in self.manifest.assets})
        narrative_block_ids = {block.block_id for block in _walk_blocks(self.narrative.blocks)}

        def validate_reference(block_id: str, reference: EntityRef) -> None:
            """Validate one narrative reference against package-local identity."""
            if reference.document_id != self.manifest.document_id:
                diagnostics.append(f"Narrative block {block_id} references another document.")
            elif reference.entity_kind == "narrative_block":
                if reference.entity_id not in narrative_block_ids:
                    diagnostics.append(f"Narrative block {block_id} references unknown narrative block {reference.entity_id}.")
            elif known_entities.get(reference.entity_id) != reference.entity_kind:
                diagnostics.append(f"Narrative block {block_id} references unknown source entity {reference.entity_id}.")

        for block in _walk_blocks(self.narrative.blocks):
            if block.type == "image" and block.asset_id not in {asset.asset_id for asset in self.manifest.assets}:
                diagnostics.append(f"Image block {block.block_id} references missing asset {block.asset_id}.")
            for reference in block.entity_refs:
                validate_reference(block.block_id, reference)
            for inline in block.inlines:
                if inline.entity_ref is not None:
                    validate_reference(block.block_id, inline.entity_ref)

        annotation_paths = [path for path in self.files if path.startswith("annotations/")]
        annotation_prefixes = [schema.path_prefix.rstrip("/") + "/" for schema in self.manifest.annotation_schemas]
        for path in annotation_paths:
            if not any(path.startswith(prefix) for prefix in annotation_prefixes):
                diagnostics.append(f"Annotation path {path} is not owned by a registered annotation schema.")

        try:
            load_entity_sections(self.manifest, self.files)
        except (ValueError, pydantic.ValidationError) as exc:
            diagnostics.append(f"Invalid entity sections: {exc}")

        try:
            from spec2gds.spec.spec_format.circuit_layouts import validate_layout_annotations

            validate_layout_annotations(self.manifest, self.files)
        except (ValueError, pydantic.ValidationError) as exc:
            diagnostics.append(f"Invalid circuit layouts: {exc}")

        try:
            from spec2gds.spec.spec_format.circuit_timings import validate_timing_annotations

            validate_timing_annotations(self.manifest, self.files)
        except (ValueError, pydantic.ValidationError) as exc:
            diagnostics.append(f"Invalid circuit timing: {exc}")

        diagnostics.extend(_reference_diagnostics(self.manifest, self.files))
        return sorted(set(diagnostics))

    def require_valid(self) -> None:
        """Raise one aggregate error when the package is not valid V1 source."""
        diagnostics = self.diagnostics()
        if diagnostics:
            raise SpecValidationError(diagnostics)

    def save(self, path: str | None = None) -> None:
        """Validate and write a deterministic package without in-place corruption."""
        destination_value = path or self.path
        if not destination_value:
            raise ValueError("A destination path is required for a new .spec package.")
        destination = pathlib.Path(destination_value)
        destination.parent.mkdir(parents=True, exist_ok=True)
        fd, temporary_name = tempfile.mkstemp(prefix=f".{destination.name}.", suffix=".tmp", dir=destination.parent)
        os.close(fd)
        try:
            pathlib.Path(temporary_name).write_bytes(self.to_bytes())
            os.replace(temporary_name, destination)
            self.path = str(destination)
        finally:
            if os.path.exists(temporary_name):
                os.remove(temporary_name)

    def to_bytes(self) -> bytes:
        """Return the validated package as deterministic ZIP bytes."""
        self.require_valid()
        entries: dict[str, bytes] = {
            "mimetype": MIMETYPE.encode("ascii"),
            "manifest.json": _json_bytes(self.manifest),
            "document/document.json": _json_bytes(self.narrative),
            **self.files,
        }
        for entry_path in entries:
            _safe_entry_path(entry_path)
        output = io.BytesIO()
        with zipfile.ZipFile(output, "w", compression=zipfile.ZIP_DEFLATED, compresslevel=9) as archive:
            archive.writestr(_zip_info("mimetype", zipfile.ZIP_STORED), entries.pop("mimetype"))
            for entry_path in sorted(entries):
                archive.writestr(_zip_info(entry_path, zipfile.ZIP_DEFLATED), entries[entry_path])
        return output.getvalue()

    def unpack(self, destination: str) -> None:
        """Write an unpacked package tree after validating its source contents."""
        self.require_valid()
        output = pathlib.Path(destination)
        if output.exists() and any(output.iterdir()):
            raise ValueError("Unpack destination must not already contain files.")
        output.mkdir(parents=True, exist_ok=True)
        entries = {
            "mimetype": MIMETYPE.encode("ascii"),
            "manifest.json": _json_bytes(self.manifest),
            "document/document.json": _json_bytes(self.narrative),
            **self.files,
        }
        for entry_path, data in entries.items():
            _safe_entry_path(entry_path)
            target = output / entry_path
            target.parent.mkdir(parents=True, exist_ok=True)
            target.write_bytes(data)


def _walk_blocks(blocks: list[typing.Any]) -> typing.Iterator[typing.Any]:
    """Yield all narrative blocks in depth-first document order."""
    for block in blocks:
        yield block
        yield from _walk_blocks(block.children)


def _reference_diagnostics(manifest: SpecManifest, files: dict[str, bytes]) -> list[str]:
    """Check V1 self-contained component, bus, and abstraction references."""
    diagnostics: list[str] = []
    by_kind_vlnv = {(entry.kind, entry.vlnv) for entry in manifest.documents}
    for entry in manifest.documents:
        data = files.get(entry.path)
        if data is None:
            continue
        try:
            root = ipxact.parse_xml(data)
        except ValueError:
            continue
        reference_kinds = {
            "componentRef": "component",
            "busType": "bus_definition",
            "abstractionRef": "abstraction_definition",
        }
        for local_name, target_kind in reference_kinds.items():
            for node in root.xpath(f".//*[local-name()='{local_name}']"):
                attributes = [node.get(name, "") for name in ("vendor", "library", "name", "version")]
                if all(attributes):
                    target_vlnv = ":".join(attributes)
                    if (target_kind, target_vlnv) not in by_kind_vlnv:
                        diagnostics.append(
                            f"{entry.path} references missing embedded {target_kind} VLNV {target_vlnv}."
                        )
    return diagnostics
