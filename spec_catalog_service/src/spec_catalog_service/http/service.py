"""FastAPI application for the Spec2GDS Component Library standalone service."""

from __future__ import annotations

from pathlib import Path
from typing import Any

from fastapi import FastAPI, File, Header, HTTPException, Query, Request, Response, UploadFile
from fastapi.responses import JSONResponse
from fastapi.staticfiles import StaticFiles

from spec2gds.spec.spec_format.ir import SpecRevision
from spec_catalog_service.catalog.indexer import LibraryIndexer
from spec_catalog_service.catalog.schemas import SUPPORTED_CATEGORIES, compute_identity_key
from spec_catalog_service.http.index import CatalogueIndex
from spec_catalog_service.http.storage import (
    MAX_COMPRESSED_BYTES,
    MAX_COMPRESSION_RATIO,
    MAX_EVIDENCE_BYTES,
    MAX_MEMBER_BYTES,
    MAX_MEMBERS,
    MAX_UNCOMPRESSED_BYTES,
    ImmutableConflictError,
    InvalidPackageError,
    LibraryStorage,
    LimitExceededError,
    StorageError,
    StoragePathError,
)


class LibraryServiceApp:
    """Encapsulates the FastAPI application and service dependencies."""

    def __init__(self, library_root: Path, state_dir: Path) -> None:
        self.library_root = library_root.resolve()
        self.state_dir = state_dir.resolve()
        if self.library_root.is_dir():
            report = LibraryIndexer(self.library_root, self.state_dir).rebuild()
            if report["errors"]:
                raise ValueError("Catalog indexing failed: " + "; ".join(report["errors"]))
        self.storage = LibraryStorage(library_root=self.library_root)
        self.index = CatalogueIndex(
            db_path=self.state_dir / "catalogue.db",
            library_root=self.library_root,
        )
        self.app = FastAPI(title="Spec Catalog service", docs_url=None, redoc_url=None)
        self._setup_routes()

    def _setup_routes(self) -> None:
        api = FastAPI()

        @api.exception_handler(StorageError)
        async def storage_error_handler(request: Request, exc: StorageError) -> JSONResponse:
            status_code = 400
            if isinstance(exc, LimitExceededError):
                status_code = 413
            elif isinstance(exc, ImmutableConflictError):
                status_code = 409
            elif isinstance(exc, StoragePathError):
                status_code = 403
            elif isinstance(exc, InvalidPackageError):
                status_code = 422
            return JSONResponse(
                status_code=status_code,
                content={"error": {"code": exc.code, "message": exc.message, "details": exc.details}},
            )

        @api.get("/health")
        async def health() -> JSONResponse:
            root_ok = self.storage.is_root_readable()
            status = "ready" if root_ok else "degraded"
            gen = self.index.get_generation()
            content = {
                "schema_version": 1,
                "status": status,
                "root_readable": root_ok,
                "index_generation": gen,
            }
            return JSONResponse(status_code=200 if root_ok else 503, content=content)

        @api.get("/capabilities")
        async def capabilities() -> dict[str, Any]:
            return {
                "schema_version": 1,
                "metadata_versions": [1],
                "evidence_versions": [1],
                "limits": {
                    "max_compressed_bytes": MAX_COMPRESSED_BYTES,
                    "max_uncompressed_bytes": MAX_UNCOMPRESSED_BYTES,
                    "max_member_bytes": MAX_MEMBER_BYTES,
                    "max_members": MAX_MEMBERS,
                    "max_compression_ratio": MAX_COMPRESSION_RATIO,
                    "max_evidence_bytes": MAX_EVIDENCE_BYTES,
                },
                "categories": sorted(SUPPORTED_CATEGORIES),
                "profile": "trusted_local",
            }

        @api.get("/components")
        async def list_components(
            q: str | None = Query(None),
            category: str | None = Query(None),
            implementation: str | None = Query(None),
            functional_status: str | None = Query(None),
            limit: int = Query(25, ge=1, le=100),
            offset: int = Query(0, ge=0),
        ) -> dict[str, Any]:
            total, items = self.index.list_components(
                q=q,
                category=category,
                implementation=implementation,
                functional_status=functional_status,
                limit=limit,
                offset=offset,
            )
            return {
                "total": total,
                "limit": limit,
                "offset": offset,
                "items": items,
            }

        @api.get("/components/{key}")
        async def get_component(key: str) -> dict[str, Any]:
            comp = self.index.get_component_by_key(key)
            if not comp:
                raise HTTPException(
                    status_code=404,
                    detail={"error": {"code": "NOT_FOUND", "message": f"Component key {key} not found", "details": {}}},
                )
            return comp

        @api.get("/components/{key}/versions/{version}")
        async def get_version_details(key: str, version: str) -> dict[str, Any]:
            vrow = self.index.get_version_details(key, version)
            if not vrow:
                raise HTTPException(
                    status_code=404,
                    detail={"error": {"code": "NOT_FOUND", "message": f"Version {version} not found for key {key}", "details": {}}},
                )
            return vrow

        @api.get("/components/{key}/versions/{version}/download")
        async def download_component(
            key: str, version: str, if_none_match: str | None = Header(None)
        ) -> Response:
            vrow = self.index.get_version_details(key, version)
            if not vrow:
                raise HTTPException(
                    status_code=404,
                    detail={"error": {"code": "NOT_FOUND", "message": f"Version {version} not found for key {key}", "details": {}}},
                )

            res = self.storage.get_package_bytes(vrow["category"], vrow["id"], version)
            if not res:
                raise HTTPException(
                    status_code=404,
                    detail={"error": {"code": "NOT_FOUND", "message": "Package file missing from storage", "details": {}}},
                )

            pkg_bytes, pkg_sha = res
            quoted_etag = f'"{pkg_sha}"'
            if if_none_match and (if_none_match == quoted_etag or if_none_match == pkg_sha):
                return Response(status_code=304, headers={"ETag": quoted_etag})

            return Response(
                content=pkg_bytes,
                media_type="application/zip",
                headers={
                    "Content-Disposition": f'attachment; filename="{vrow["id"]}-{version}.spec"',
                    "ETag": quoted_etag,
                },
            )

        @api.post("/uploads")
        async def upload_component(file: UploadFile = File(...)) -> JSONResponse:
            content = await file.read()
            pkg, cat_asset, pkg_sha, pkg_size = self.storage.validate_archive_bytes(content)
            is_created, target_path, actual_sha = self.storage.publish_package(content, cat_asset)

            rel_path = str(target_path.relative_to(self.library_root))
            rev = SpecRevision.from_package(pkg)
            self.index.record_published_package(
                cat_asset=cat_asset,
                rel_path=rel_path,
                pkg_sha=actual_sha,
                source_rev_hash=rev.source_revision_hash,
            )

            key = compute_identity_key("spec2gds.local", cat_asset.category, cat_asset.id)
            vrow = self.index.get_version_details(key, cat_asset.version)
            status_code = 201 if is_created else 200
            return JSONResponse(status_code=status_code, content={"created": is_created, "version": vrow})

        @api.post("/components/{key}/versions/{version}/evidence")
        async def submit_evidence(key: str, version: str, request: Request) -> JSONResponse:
            comp = self.index.get_component_by_key(key)
            if not comp:
                raise HTTPException(
                    status_code=404,
                    detail={"error": {"code": "NOT_FOUND", "message": f"Component key {key} not found", "details": {}}},
                )

            body_bytes = await request.body()
            is_created, ev_sha, received_at = self.storage.store_evidence(
                category=comp["category"],
                comp_id=comp["id"],
                version=version,
                ev_bytes=body_bytes,
            )

            self.index.record_evidence_submission(
                comp_id=comp["id"],
                version=version,
                ev_sha=ev_sha,
                ev_bytes=body_bytes,
                received_at=received_at,
            )

            status_code = 201 if is_created else 200
            return JSONResponse(
                status_code=status_code,
                content={"created": is_created, "evidence_sha256": ev_sha, "received_at": received_at},
            )

        @api.get("/components/{key}/versions/{version}/evidence")
        async def get_evidence(key: str, version: str) -> dict[str, Any]:
            items = self.index.list_evidence_submissions(key, version)
            if items is None:
                raise HTTPException(
                    status_code=404,
                    detail={"error": {"code": "NOT_FOUND", "message": f"Version {version} not found for key {key}", "details": {}}},
                )
            return {"items": items}

        self.app.mount("/api/spec-catalog/v1", api)

        # Static UI mount at /
        static_dir = Path(__file__).parent / "static"
        if static_dir.exists():
            self.app.mount("/", StaticFiles(directory=str(static_dir), html=True), name="static")


def create_app(library_root: Path = Path("spec_catalog_service/catalog"), state_dir: Path = Path("spec_catalog_service/.state")) -> FastAPI:
    """Factory creating configured FastAPI application."""
    svc = LibraryServiceApp(library_root=library_root, state_dir=state_dir)
    return svc.app
