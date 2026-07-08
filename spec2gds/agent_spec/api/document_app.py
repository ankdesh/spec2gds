"""FastAPI app used by the local React document editor."""

import pathlib
import typing

import pydantic

import spec2gds.agent_spec.package.archive as container_module
import spec2gds.agent_spec.document.relations as editor_relations
import spec2gds.agent_spec.document.session as editor_session
import spec2gds.agent_spec.api.app as agent_spec_api
import spec2gds.agent_spec.query as agent_query


class IpxactXmlRequest(pydantic.BaseModel):
    """Request body carrying editable IP-XACT XML text."""

    file_path: str
    xml_text: str


class EditorSaveRequest(pydantic.BaseModel):
    """Combined save payload from the document editor."""

    text_edits: dict[str, str] = pydantic.Field(default_factory=dict)
    relations: editor_relations.EditorRelations | None = None
    ipxact_xml_edits: dict[str, str] = pydantic.Field(default_factory=dict)


class FileBrowserEntry(pydantic.BaseModel):
    """One entry displayed by the editor's restricted file browser."""

    name: str
    path: str
    entry_type: str


class FileBrowserResponse(pydantic.BaseModel):
    """File browser response for one directory."""

    directory: str
    parent: str | None = None
    entries: list[FileBrowserEntry]


GENERATED_SAMPLES_ALIAS = "agent-spec://samples/generated"


def _repo_root() -> pathlib.Path:
    """Return the repository root based on this module's package location."""
    return pathlib.Path(__file__).resolve().parents[3]


def _generated_samples_directory() -> pathlib.Path:
    """Return the checked-in directory containing loadable sample .spec files."""
    return _repo_root() / "spec2gds" / "agent_spec" / "samples" / "generated"


def _resolve_browse_directory(directory: str) -> pathlib.Path:
    """Resolve file browser paths without depending on the server cwd.

    The frontend starts at a named generated-samples location so users always
    see a loadable agent-spec document after opening the editor. Absolute paths
    and legacy relative paths are still accepted for normal navigation and for
    older frontend bundles.
    """
    if directory in {"", ".", "generated", "@generated", GENERATED_SAMPLES_ALIAS}:
        return _generated_samples_directory().resolve()

    requested = pathlib.Path(directory).expanduser()
    candidates = [requested]
    if not requested.is_absolute():
        candidates.append(_repo_root() / requested)

    for candidate in candidates:
        resolved = candidate.resolve()
        if resolved.exists() and resolved.is_dir():
            return resolved
    raise ValueError(f"Not a directory: {directory}")


def create_app() -> typing.Any:
    """
    Create the local FastAPI app for the v1 agent-spec editor.

    FastAPI is imported lazily so the editor core remains testable in minimal
    environments before frontend dependencies are installed.
    """
    try:
        import fastapi
        import fastapi.middleware.cors
    except Exception as exc:
        raise RuntimeError(
            "FastAPI is required to run the local agent-spec editor API. "
            "Install project dependencies with uv sync."
        ) from exc

    app = fastapi.FastAPI(title="spec2gds Agent-Spec Editor API")
    app.mount("/agent-spec", agent_spec_api.create_app())
    app.add_middleware(
        fastapi.middleware.cors.CORSMiddleware,
        allow_origins=[
            "http://127.0.0.1:5173",
            "http://127.0.0.1:5174",
            "http://localhost:5173",
            "http://localhost:5174",
        ],
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    @app.get("/health")
    def health() -> dict[str, str]:
        """Simple health endpoint for frontend/dev-server checks."""
        return {"status": "ok"}

    @app.get("/documents/snapshot")
    def document_snapshot(path: str) -> dict[str, typing.Any]:
        """Return a full editor snapshot for the requested document path."""
        return agent_query.AgentSpecQueryService(path).editor_snapshot().model_dump()

    @app.post("/documents/active-section-versions")
    def update_active_section_versions(
        path: str,
        active_section_versions: dict[str, str],
    ) -> dict[str, typing.Any]:
        """Persist active section-version selections and return a fresh snapshot."""
        session = editor_session.EditorSession.from_path(path)
        session.persist_active_versions(active_section_versions)
        session.save(path)
        return session.snapshot().model_dump()

    @app.post("/documents/text-edits")
    def apply_text_edits(
        path: str,
        edits: dict[str, str],
    ) -> dict[str, typing.Any]:
        """Apply plain-text block edits and return a fresh snapshot."""
        session = editor_session.EditorSession.from_path(path)
        session.apply_text_edits(edits)
        session.save(path)
        return session.snapshot().model_dump()

    @app.post("/ipxact/preview")
    def preview_ipxact_xml(request: IpxactXmlRequest) -> dict[str, typing.Any]:
        """Summarize unsaved IP-XACT XML without touching a document package."""
        empty_container = container_module.AgentSpecArchive()
        session = editor_session.EditorSession(empty_container)
        return session.preview_ipxact_xml(request.file_path, request.xml_text).model_dump()

    @app.post("/documents/ipxact-xml")
    def update_ipxact_xml(
        path: str,
        request: IpxactXmlRequest,
    ) -> dict[str, typing.Any]:
        """Replace one embedded IP-XACT XML payload and return a fresh snapshot."""
        session = editor_session.EditorSession.from_path(path)
        session.update_ipxact_xml(request.file_path, request.xml_text)
        session.save(path)
        return session.snapshot().model_dump()

    @app.post("/documents/save")
    def save_document(
        path: str,
        request: EditorSaveRequest,
    ) -> dict[str, typing.Any]:
        """Apply all editor save changes in one session and return a snapshot."""
        session = editor_session.EditorSession.from_path(path)
        session.apply_editor_save(
            text_edits=request.text_edits,
            editor_relations=request.relations,
            ipxact_xml_edits=request.ipxact_xml_edits,
        )
        session.save(path)
        return session.snapshot().model_dump()

    @app.get("/documents/assets/{asset_id}")
    def document_asset(path: str, asset_id: str) -> typing.Any:
        """Serve embedded image bytes referenced by a semantic image block."""
        session = editor_session.EditorSession.from_path(path)
        try:
            data, media_type = session.asset_bytes(asset_id)
        except KeyError as exc:
            raise fastapi.HTTPException(status_code=404, detail=str(exc)) from exc
        return fastapi.Response(content=data, media_type=media_type)

    @app.get("/files")
    def browse_files(directory: str = GENERATED_SAMPLES_ALIAS) -> dict[str, typing.Any]:
        """Browse directories and expose only subdirectories plus `.spec` files."""
        try:
            current = _resolve_browse_directory(directory)
            entries: list[FileBrowserEntry] = []
            for child in sorted(current.iterdir(), key=lambda item: (not item.is_dir(), item.name.lower())):
                if child.name.startswith("."):
                    continue
                if child.name.endswith(".agent-spec-sidecar"):
                    continue
                if child.is_dir():
                    entries.append(
                        FileBrowserEntry(
                            name=child.name,
                            path=str(child),
                            entry_type="directory",
                        )
                    )
                elif child.suffix.lower() == ".spec":
                    entries.append(
                        FileBrowserEntry(
                            name=child.name,
                            path=str(child),
                            entry_type="file",
                        )
                    )
            parent = str(current.parent) if current.parent != current else None
            return FileBrowserResponse(
                directory=str(current),
                parent=parent,
                entries=entries,
            ).model_dump()
        except Exception as exc:
            raise fastapi.HTTPException(status_code=400, detail=str(exc)) from exc

    return app
