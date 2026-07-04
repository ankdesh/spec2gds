import typing

import pydantic

import spec2gds.spec.odt_container.container as container_module
import spec2gds.spec.odt_container.editor_core.session as editor_session


class IpxactXmlRequest(pydantic.BaseModel):
    file_path: str
    xml_text: str


def create_app() -> typing.Any:
    """
    Create the local FastAPI app for the v1 ODT editor.

    FastAPI is imported lazily so the editor core remains testable in minimal
    environments before frontend dependencies are installed.
    """
    try:
        import fastapi
        import fastapi.middleware.cors
    except Exception as exc:
        raise RuntimeError(
            "FastAPI is required to run the local ODT editor API. "
            "Install project dependencies with uv sync."
        ) from exc

    app = fastapi.FastAPI(title="spec2gds ODT Container Editor API")
    app.add_middleware(
        fastapi.middleware.cors.CORSMiddleware,
        allow_origins=[
            "http://127.0.0.1:5173",
            "http://localhost:5173",
        ],
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    @app.get("/health")
    def health() -> dict[str, str]:
        return {"status": "ok"}

    @app.get("/documents/snapshot")
    def document_snapshot(path: str) -> dict[str, typing.Any]:
        session = editor_session.EditorSession.from_path(path)
        return session.snapshot().model_dump()

    @app.post("/documents/active-section-versions")
    def update_active_section_versions(
        path: str,
        active_section_versions: dict[str, str],
    ) -> dict[str, typing.Any]:
        session = editor_session.EditorSession.from_path(path)
        session.persist_active_versions(active_section_versions)
        session.save(path)
        return session.snapshot().model_dump()

    @app.post("/documents/text-edits")
    def apply_text_edits(
        path: str,
        edits: dict[str, str],
    ) -> dict[str, typing.Any]:
        session = editor_session.EditorSession.from_path(path)
        session.apply_text_edits(edits)
        session.save(path)
        return session.snapshot().model_dump()

    @app.post("/ipxact/preview")
    def preview_ipxact_xml(request: IpxactXmlRequest) -> dict[str, typing.Any]:
        empty_container = container_module.HybridODTContainer()
        session = editor_session.EditorSession(empty_container)
        return session.preview_ipxact_xml(request.file_path, request.xml_text).model_dump()

    @app.post("/documents/ipxact-xml")
    def update_ipxact_xml(
        path: str,
        request: IpxactXmlRequest,
    ) -> dict[str, typing.Any]:
        session = editor_session.EditorSession.from_path(path)
        session.update_ipxact_xml(request.file_path, request.xml_text)
        session.save(path)
        return session.snapshot().model_dump()

    return app
