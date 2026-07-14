"""Diagnostic and sanitization helpers for `.spec` documents.

The web editor intentionally shows a focused projection of the document. This
module is the opposite: it exposes the package anatomy, custom payloads,
semantic projection, editor metadata, IP-XACT summaries, and persisted
agent-spec run state so engineers can debug documents that do not open cleanly.
"""

import collections
import datetime
import hashlib
import json
import os
import pathlib
import typing
import zipfile

import pydantic

import spec2gds.agent_spec.document.ipxact_view as ipxact_view
import spec2gds.agent_spec.document.relations as relations
import spec2gds.agent_spec.document.semantic as semantic
import spec2gds.agent_spec.models as agent_models
import spec2gds.agent_spec.package.archive as archive
import spec2gds.agent_spec.package.verifier as verifier
import spec2gds.agent_spec.plugins.ipxact as ipxact_plugin
import spec2gds.agent_spec.plugins.json_payload as json_plugin
import spec2gds.agent_spec.plugins.manager as plugin_manager


MAX_PREVIEW_CHARS: int = 180
MANIFEST_PATH: str = "spec_data/agent-spec/manifest.json"
GRAPH_PATH: str = "spec_data/agent-spec/graph.json"


class SanitizationResult(pydantic.BaseModel):
    """Summary of a conservative `.spec` package sanitization pass."""

    source_path: str
    output_path: str
    dry_run: bool = False
    actions: list[str] = pydantic.Field(default_factory=list)
    warnings: list[str] = pydantic.Field(default_factory=list)
    changed: bool = False
    saved: bool = False


def build_default_manager() -> plugin_manager.PluginManager:
    """Return the same built-in modality registry used by package tooling."""
    manager = plugin_manager.PluginManager()
    manager.register_plugin(json_plugin.SimpleJSONPlugin())
    manager.register_plugin(ipxact_plugin.IPXACTPlugin())
    return manager


def build_diagnostic_report(spec_path: str | os.PathLike[str]) -> dict[str, typing.Any]:
    """Build a detailed machine-readable report for one `.spec` document."""
    path = pathlib.Path(spec_path)
    report: dict[str, typing.Any] = {
        "schema": "spec2gds.agent_spec.diagnostic.v1",
        "generated_at": _utc_now(),
        "document": _document_info(path),
        "package": {},
        "manifest": {},
        "custom_files": [],
        "verification": {},
        "semantic_document": {},
        "editor_metadata": {},
        "ipxact": [],
        "agent_spec_metadata": {},
        "errors": [],
    }

    report["package"] = _zip_package_info(path)
    try:
        spec_archive = archive.AgentSpecArchive(str(path))
    except Exception as exc:
        report["errors"].append(f"failed to open .spec archive: {exc}")
        return report

    manifest_paths = _manifest_paths(spec_archive)
    report["manifest"] = _manifest_info(spec_archive, manifest_paths)
    report["custom_files"] = _custom_file_info(spec_archive, manifest_paths)
    report["verification"] = _verification_info(spec_archive)
    report["semantic_document"] = _semantic_info(spec_archive)
    report["editor_metadata"] = _editor_metadata_info(spec_archive)
    report["ipxact"] = _ipxact_info(spec_archive)
    report["agent_spec_metadata"] = _agent_spec_metadata_info(spec_archive)
    return report


def sanitize_spec_document(
    spec_path: str | os.PathLike[str],
    output_path: str | os.PathLike[str] | None = None,
    *,
    in_place: bool = False,
    dry_run: bool = False,
) -> SanitizationResult:
    """Apply conservative repairs that preserve existing `.spec` payload bytes.

    Sanitization intentionally avoids protocol or content invention. It can add
    missing heading ids, add missing manifest registrations for existing
    `spec_data/` files, and re-save the package so the mimetype entry is in the
    office-compatible ZIP position.
    """
    source = pathlib.Path(spec_path)
    if in_place and output_path is not None:
        raise ValueError("Use either output_path or in_place, not both.")
    if not in_place and output_path is None:
        raise ValueError("Sanitization requires output_path unless in_place=True.")

    target = source if in_place else pathlib.Path(typing.cast(os.PathLike[str], output_path))
    result = SanitizationResult(
        source_path=str(source),
        output_path=str(target),
        dry_run=dry_run,
    )

    spec_archive = archive.AgentSpecArchive(str(source))
    content_xml = _content_xml(spec_archive)
    updated_content_xml = semantic.ensure_heading_ids(content_xml)
    if updated_content_xml != content_xml:
        result.actions.append("added missing xml:id values to document headings")
        result.changed = True
        if not dry_run:
            spec_archive.document.set_part("content.xml", updated_content_xml)

    manifest = spec_archive.document.get_part("META-INF/manifest.xml")
    if manifest is None or not hasattr(manifest, "add_full_path"):
        result.warnings.append("manifest object is unavailable; cannot add missing custom-file registrations")
    else:
        registered_paths = set(_manifest_paths(spec_archive))
        for custom_path in sorted(spec_archive.custom_files):
            if custom_path in registered_paths:
                continue
            media_type = infer_media_type(custom_path)
            result.actions.append(f"registered {custom_path} in manifest as {media_type}")
            result.changed = True
            if not dry_run:
                manifest.add_full_path(custom_path, media_type)

    result.actions.append("normalized package mimetype entry on save")
    if not dry_run:
        spec_archive.save(str(target))
        result.saved = True
    return result


def render_text_report(report: dict[str, typing.Any]) -> str:
    """Render the diagnostic report as dense human-readable terminal text."""
    lines: list[str] = []
    document = report.get("document", {})
    package = report.get("package", {})
    manifest = report.get("manifest", {})
    semantic_report = report.get("semantic_document", {})
    agent_spec = report.get("agent_spec_metadata", {})

    lines.append("Agent-Spec Diagnostic Report")
    lines.append(f"  Path: {document.get('path', '')}")
    lines.append(f"  Exists: {document.get('exists')}  Size: {document.get('size_bytes')} bytes")
    lines.append(f"  SHA-256: {document.get('sha256', '')}")
    lines.append("")
    lines.append("Package")
    lines.append(f"  ZIP readable: {package.get('zip_readable')}")
    lines.append(f"  Parts: {package.get('part_count', 0)}")
    lines.append(f"  mimetype first: {package.get('mimetype_first')}")
    lines.append(f"  mimetype: {package.get('mimetype', '')}")
    lines.append("")
    lines.append("Manifest")
    lines.append(f"  Registered paths: {manifest.get('registered_path_count', 0)}")
    lines.append(f"  spec_data files: {manifest.get('spec_data_file_count', 0)}")
    lines.append(f"  Missing registrations: {len(manifest.get('missing_spec_data_entries', []))}")
    for missing in manifest.get("missing_spec_data_entries", []):
        lines.append(f"    - {missing}")
    lines.append("")
    lines.append("Semantic Document")
    lines.append(
        "  Blocks: "
        f"{semantic_report.get('block_count', 0)} "
        f"(headings={semantic_report.get('heading_count', 0)}, "
        f"tables={semantic_report.get('table_count', 0)}, "
        f"images={semantic_report.get('image_count', 0)})"
    )
    lines.append(f"  Links: {semantic_report.get('link_count', 0)}")
    for diagnostic in semantic_report.get("diagnostics", []):
        lines.append(f"  {diagnostic.get('severity', 'info')}: {diagnostic.get('source', '')}: {diagnostic.get('message', '')}")
    lines.append("")
    lines.append("IP-XACT")
    for component in report.get("ipxact", []):
        c_vlnv = component.get("component", {})
        name = _vlnv_label(c_vlnv) or "<unknown component>"
        lines.append(f"  {component.get('file_path')}: {name}")
        lines.append(f"    interfaces: {component.get('interface_count', 0)}")
        for diagnostic in component.get("diagnostics", []):
            lines.append(f"    {diagnostic.get('severity')}: {diagnostic.get('message')}")
    if not report.get("ipxact"):
        lines.append("  <none>")
    lines.append("")
    lines.append("Agent-Spec Metadata")
    lines.append(f"  Manifest present: {agent_spec.get('manifest', {}).get('present')}")
    lines.append(f"  Graph blocks: {agent_spec.get('graph', {}).get('block_count', 0)}")
    lines.append(f"  Runs: {agent_spec.get('runs', {}).get('count', 0)}")
    lines.append(f"  Writebacks: {agent_spec.get('writebacks', {}).get('count', 0)}")

    errors = report.get("errors", [])
    if errors:
        lines.append("")
        lines.append("Errors")
        for error in errors:
            lines.append(f"  - {error}")
    return "\n".join(lines)


def infer_media_type(file_path: str) -> str:
    """Infer the manifest media type for a known custom archive path."""
    if file_path.startswith("spec_data/ipxact/"):
        return "application/xml+ipxact"
    if file_path.startswith("spec_data/simple-json/"):
        return "application/x-spec-json"
    if file_path == "spec_data/agent-spec-editor/relations.json":
        return relations.RELATIONS_MEDIA_TYPE
    if file_path.startswith("spec_data/agent-spec-editor/"):
        return "application/vnd.spec2gds.spec-editor-state+json"
    if file_path.startswith("spec_data/agent-spec/"):
        return "application/vnd.spec2gds.agent-spec+json"
    if file_path.endswith(".json"):
        return "application/json"
    if file_path.endswith(".xml"):
        return "application/xml"
    return "application/octet-stream"


def _document_info(path: pathlib.Path) -> dict[str, typing.Any]:
    """Return filesystem-level facts before any package parser runs."""
    exists = path.exists()
    return {
        "path": str(path),
        "exists": exists,
        "size_bytes": path.stat().st_size if exists else 0,
        "sha256": _file_sha256(path) if exists else "",
    }


def _zip_package_info(path: pathlib.Path) -> dict[str, typing.Any]:
    """Return ZIP-level package facts, including part sizes and mimetype order."""
    info: dict[str, typing.Any] = {
        "zip_readable": False,
        "part_count": 0,
        "mimetype_first": False,
        "mimetype": "",
        "total_compressed_bytes": 0,
        "total_uncompressed_bytes": 0,
        "parts": [],
        "errors": [],
    }
    if not path.exists():
        info["errors"].append("file does not exist")
        return info
    try:
        with zipfile.ZipFile(path, "r") as zip_file:
            entries = zip_file.infolist()
            info["zip_readable"] = True
            info["part_count"] = len(entries)
            if entries:
                info["mimetype_first"] = entries[0].filename == "mimetype" and entries[0].compress_type == zipfile.ZIP_STORED
            names = zip_file.namelist()
            if "mimetype" in names:
                info["mimetype"] = zip_file.read("mimetype").decode("utf-8", errors="replace")
            for entry in entries:
                info["total_compressed_bytes"] += entry.compress_size
                info["total_uncompressed_bytes"] += entry.file_size
                info["parts"].append(
                    {
                        "path": entry.filename,
                        "compressed_size": entry.compress_size,
                        "uncompressed_size": entry.file_size,
                        "compression": entry.compress_type,
                        "is_spec_data": entry.filename.startswith("spec_data/"),
                    }
                )
    except Exception as exc:
        info["errors"].append(str(exc))
    return info


def _manifest_paths(spec_archive: archive.AgentSpecArchive) -> list[str]:
    """Read all manifest paths exposed by the package manifest object."""
    manifest = spec_archive.document.get_part("META-INF/manifest.xml")
    if manifest is None or not hasattr(manifest, "get_paths"):
        return []
    try:
        return list(manifest.get_paths())
    except Exception:
        return []


def _manifest_media_type(spec_archive: archive.AgentSpecArchive, file_path: str) -> str:
    """Return the manifest media type for one package path when available."""
    manifest = spec_archive.document.get_part("META-INF/manifest.xml")
    if manifest is None or not hasattr(manifest, "get_media_type"):
        return ""
    try:
        return str(manifest.get_media_type(file_path))
    except Exception:
        return ""


def _manifest_info(
    spec_archive: archive.AgentSpecArchive,
    manifest_paths: list[str],
) -> dict[str, typing.Any]:
    """Compare custom payload files against manifest registrations."""
    custom_paths = sorted(spec_archive.custom_files)
    registered = set(manifest_paths)
    return {
        "registered_path_count": len(manifest_paths),
        "registered_paths": sorted(manifest_paths),
        "spec_data_file_count": len(custom_paths),
        "missing_spec_data_entries": [path for path in custom_paths if path not in registered],
        "registered_spec_data_entries_without_payload": [
            path
            for path in sorted(registered)
            if path.startswith("spec_data/") and path not in spec_archive.custom_files
        ],
    }


def _custom_file_info(
    spec_archive: archive.AgentSpecArchive,
    manifest_paths: list[str],
) -> list[dict[str, typing.Any]]:
    """Summarize every cached `spec_data/` payload."""
    registered = set(manifest_paths)
    files: list[dict[str, typing.Any]] = []
    for file_path, payload in sorted(spec_archive.custom_files.items()):
        entry: dict[str, typing.Any] = {
            "path": file_path,
            "size_bytes": len(payload),
            "sha256": _bytes_sha256(payload),
            "registered": file_path in registered,
            "media_type": _manifest_media_type(spec_archive, file_path),
            "inferred_media_type": infer_media_type(file_path),
            "json": None,
        }
        if file_path.endswith(".json"):
            entry["json"] = _json_preview(payload)
        files.append(entry)
    return files


def _verification_info(spec_archive: archive.AgentSpecArchive) -> dict[str, typing.Any]:
    """Run the existing verifier and package its result for diagnostics."""
    try:
        report = verifier.ContainerVerifier(spec_archive, build_default_manager()).verify_all()
        return report.model_dump(mode="json")
    except Exception as exc:
        return {"error": str(exc)}


def _semantic_info(spec_archive: archive.AgentSpecArchive) -> dict[str, typing.Any]:
    """Parse `content.xml` into semantic blocks without mutating the package."""
    try:
        content_xml = _content_xml(spec_archive)
        document = semantic.parse_content_xml(content_xml)
        block_type_counts = collections.Counter(block.block_type for block in document.blocks)
        heading_ids = [
            block.heading_id
            for block in document.blocks
            if block.block_type == "heading" and block.heading_id is not None
        ]
        return {
            "block_count": len(document.blocks),
            "block_type_counts": dict(sorted(block_type_counts.items())),
            "heading_count": block_type_counts.get("heading", 0),
            "table_count": block_type_counts.get("table", 0),
            "image_count": block_type_counts.get("image", 0),
            "link_count": len(document.links),
            "heading_ids": heading_ids,
            "blocks": [_block_info(block) for block in document.blocks],
            "links": [link.model_dump(mode="json") for link in document.links],
            "diagnostics": [diagnostic.model_dump(mode="json") for diagnostic in document.diagnostics],
        }
    except Exception as exc:
        return {"error": str(exc)}


def _editor_metadata_info(spec_archive: archive.AgentSpecArchive) -> dict[str, typing.Any]:
    """Read editor-owned metadata without requiring the frontend."""
    output: dict[str, typing.Any] = {
        "relations": {"present": relations.RELATIONS_PATH in spec_archive.custom_files},
        "active_section_versions": {},
    }
    if relations.RELATIONS_PATH in spec_archive.custom_files:
        loaded_relations = relations.load_relations(spec_archive.extract_file(relations.RELATIONS_PATH))
        output["relations"].update(
            {
                "version": loaded_relations.version,
                "section_group_count": len(loaded_relations.section_groups),
                "section_groups": [group.model_dump(mode="json") for group in loaded_relations.section_groups],
                "ipxact_attachment_count": sum(len(items) for items in loaded_relations.ipxact_attachments.values()),
                "ipxact_attachments": {
                    heading_id: [item.model_dump(mode="json") for item in items]
                    for heading_id, items in loaded_relations.ipxact_attachments.items()
                },
            }
        )
    active_path = "spec_data/agent-spec-editor/active_section_versions.json"
    if active_path in spec_archive.custom_files:
        output["active_section_versions"] = _safe_json_payload(spec_archive.extract_file(active_path))
    return output


def _ipxact_info(spec_archive: archive.AgentSpecArchive) -> list[dict[str, typing.Any]]:
    """Summarize all embedded IP-XACT XML payloads."""
    summaries: list[dict[str, typing.Any]] = []
    for file_path in sorted(spec_archive.custom_files):
        if not file_path.startswith("spec_data/ipxact/"):
            continue
        summary = ipxact_view.extract_ipxact_summary(file_path, spec_archive.extract_file(file_path))
        data = summary.model_dump(mode="json")
        data["interface_count"] = len(summary.interfaces)
        data["port_map_count"] = sum(len(interface.port_maps) for interface in summary.interfaces)
        summaries.append(data)
    return summaries


def _agent_spec_metadata_info(spec_archive: archive.AgentSpecArchive) -> dict[str, typing.Any]:
    """Summarize server-owned graph, run, artifact, and writeback metadata."""
    manifest_payload = _load_model(spec_archive, MANIFEST_PATH, agent_models.AgentSpecManifest)
    graph_payload = _load_model(spec_archive, GRAPH_PATH, agent_models.SpecGraph)
    paths = sorted(path for path in spec_archive.custom_files if path.startswith("spec_data/agent-spec/"))
    output: dict[str, typing.Any] = {
        "manifest": {
            "present": manifest_payload is not None,
            "value": manifest_payload.model_dump(mode="json") if manifest_payload is not None else None,
        },
        "graph": {"present": graph_payload is not None},
        "runs": {"count": 0, "items": []},
        "writebacks": {"count": 0, "items": []},
        "artifacts": {"count": 0, "items": []},
        "versions": {"count": 0, "paths": []},
        "checkpoints": {"count": 0, "paths": []},
        "raw_paths": paths,
    }
    if isinstance(graph_payload, agent_models.SpecGraph):
        output["graph"].update(
            {
                "block_count": len(graph_payload.blocks),
                "active_version_count": len(graph_payload.active_versions),
                "artifact_count": len(graph_payload.artifact_refs),
                "attachment_count": sum(len(items) for items in graph_payload.attachments.values()),
                "blocks": [
                    {
                        "block_id": block.block_id,
                        "heading_id": block.heading_id,
                        "title": block.title,
                        "level": block.level,
                        "version_count": len(block.versions),
                        "active_version": graph_payload.active_versions.get(block.block_id, ""),
                    }
                    for block in graph_payload.blocks.values()
                ],
            }
        )

    for file_path in paths:
        payload = spec_archive.extract_file(file_path)
        if file_path.endswith("/run.json"):
            output["runs"]["items"].append(_safe_json_payload(payload))
        elif file_path.endswith("/events.ndjson"):
            run_id = file_path.split("/")[-2]
            events = [_safe_json_line(line) for line in payload.decode("utf-8", errors="replace").splitlines() if line.strip()]
            output["runs"]["items"].append({"run_id": run_id, "events": events})
        elif "/writebacks/" in file_path and file_path.endswith(".json"):
            output["writebacks"]["items"].append(_safe_json_payload(payload))
        elif "/artifacts/" in file_path and file_path.endswith(".json"):
            output["artifacts"]["items"].append(_safe_json_payload(payload))
        elif "/versions/" in file_path and file_path.endswith(".json"):
            output["versions"]["paths"].append(file_path)
        elif "/checkpoints/" in file_path and file_path.endswith(".json"):
            output["checkpoints"]["paths"].append(file_path)

    output["runs"]["count"] = len(output["runs"]["items"])
    output["writebacks"]["count"] = len(output["writebacks"]["items"])
    output["artifacts"]["count"] = len(output["artifacts"]["items"])
    output["versions"]["count"] = len(output["versions"]["paths"])
    output["checkpoints"]["count"] = len(output["checkpoints"]["paths"])
    return output


def _content_xml(spec_archive: archive.AgentSpecArchive) -> bytes:
    """Return raw `content.xml` bytes using the package abstraction."""
    content_part = spec_archive.document.get_part("content.xml")
    if hasattr(content_part, "serialize"):
        return typing.cast(bytes, content_part.serialize())
    if isinstance(content_part, bytes):
        return content_part
    return str(content_part).encode("utf-8")


def _block_info(block: semantic.SemanticBlock) -> dict[str, typing.Any]:
    """Return a compact but useful semantic block diagnostic entry."""
    return {
        "block_id": block.block_id,
        "block_type": block.block_type,
        "heading_id": block.heading_id,
        "level": block.level,
        "editable": block.editable,
        "editable_reason": block.editable_reason,
        "style_name": block.style_name,
        "text_preview": _preview(block.display_text or block.text),
        "link_count": len(block.links),
        "table_row_count": len(block.table_rows),
        "image": block.image.model_dump(mode="json") if block.image is not None else None,
    }


def _load_model(
    spec_archive: archive.AgentSpecArchive,
    file_path: str,
    model_type: type[pydantic.BaseModel],
) -> pydantic.BaseModel | None:
    """Load one Pydantic model from archive bytes, returning None on absence."""
    if file_path not in spec_archive.custom_files:
        return None
    raw = json.loads(spec_archive.extract_file(file_path).decode("utf-8"))
    return model_type.model_validate(raw)


def _json_preview(payload: bytes) -> dict[str, typing.Any]:
    """Return JSON parse status and top-level shape without hiding errors."""
    try:
        value = json.loads(payload.decode("utf-8"))
    except Exception as exc:
        return {"valid": False, "error": str(exc)}
    return {
        "valid": True,
        "type": type(value).__name__,
        "top_level_keys": sorted(value.keys()) if isinstance(value, dict) else [],
    }


def _safe_json_payload(payload: bytes) -> dict[str, typing.Any]:
    """Decode one JSON payload for reports without throwing diagnostics away."""
    try:
        parsed = json.loads(payload.decode("utf-8"))
    except Exception as exc:
        return {"_parse_error": str(exc)}
    if isinstance(parsed, dict):
        return parsed
    return {"value": parsed}


def _safe_json_line(line: str) -> dict[str, typing.Any]:
    """Decode one NDJSON event line for reports."""
    try:
        parsed = json.loads(line)
    except Exception as exc:
        return {"_parse_error": str(exc), "raw": line}
    if isinstance(parsed, dict):
        return parsed
    return {"value": parsed}


def _file_sha256(path: pathlib.Path) -> str:
    """Hash a file in chunks so large `.spec` documents stay cheap to inspect."""
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return f"sha256:{digest.hexdigest()}"


def _bytes_sha256(payload: bytes) -> str:
    """Return a repository-style SHA-256 digest for bytes."""
    return f"sha256:{hashlib.sha256(payload).hexdigest()}"


def _utc_now() -> str:
    """Return a JSON-friendly UTC timestamp."""
    return datetime.datetime.now(datetime.UTC).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def _preview(value: str) -> str:
    """Trim long text fields for diagnostic readability."""
    collapsed = " ".join(value.split())
    if len(collapsed) <= MAX_PREVIEW_CHARS:
        return collapsed
    return collapsed[: MAX_PREVIEW_CHARS - 3] + "..."


def _vlnv_label(vlnv: dict[str, typing.Any]) -> str:
    """Format a VLNV dictionary for text reports."""
    values = [str(vlnv.get(field, "")) for field in ["vendor", "library", "name", "version"]]
    return ":".join(value for value in values if value)
