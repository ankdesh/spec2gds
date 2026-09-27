"""Generation job runner, orchestrating backend plugins and artifact persistence."""

from __future__ import annotations

from datetime import datetime, timezone
import hashlib
from typing import Any
import uuid

from testplan_service.constants import SCHEMA_VERSION_GENERATION_REQUEST
from testplan_service.domain.hash import canonical_json, sha256_digest
from testplan_service.domain.objectives import CoverageObjective
from testplan_service.domain.plugins import (
    BackendPlugin,
    GenerationRequest,
    GenerationResult,
    OutputWriter,
    default_plugin_registry,
)
from testplan_service.domain.recipes import BackendConfiguration, ProducerManifest, Recipe, TargetBindingSet
from testplan_service.exceptions import (
    DomainValidationError,
    PlanNotFoundError,
    RecordNotFoundError,
)
from testplan_service.storage.blob_store import BlobStore
from testplan_service.storage.sqlite_repo import SqlitePlanRepository


class GenerationRunner:
    """Executes backend code generation jobs against immutable implementation checkpoints."""

    def __init__(self, repo: SqlitePlanRepository, blob_store: ContentAddressedBlobStore) -> None:
        self.repo = repo
        self.blob_store = blob_store

    def build_generation_request(
        self,
        plan_id: str,
        checkpoint_id: str,
        plugin_id: str | None = None,
        plugin_version: str | None = None,
    ) -> tuple[GenerationRequest, BackendPlugin]:
        """Construct immutable GenerationRequest from checkpoint data."""
        plan = self.repo.get_plan(plan_id)
        if not plan:
            raise PlanNotFoundError(plan_id)

        cp = self.repo.get_checkpoint(plan_id, checkpoint_id)
        if not cp:
            raise RecordNotFoundError(plan_id, checkpoint_id)
        if cp.layer != "implementation":
            raise DomainValidationError(
                f"Checkpoint '{checkpoint_id}' is of layer '{cp.layer}', but 'implementation' layer is required."
            )

        payload = cp.payload
        raw_recipes = payload.get("recipes", [])
        raw_bindings = payload.get("target_binding_sets", [])
        raw_bcfgs = payload.get("backend_configurations", [])

        recipes = [Recipe.model_validate(r) for r in raw_recipes]
        binding_sets = [TargetBindingSet.model_validate(b) for b in raw_bindings]
        backend_configs = [BackendConfiguration.model_validate(c) for c in raw_bcfgs]

        # Select backend configuration
        target_bcfg = None
        if backend_configs:
            target_bcfg = backend_configs[0]
        else:
            # Fallback default configuration
            target_bcfg = BackendConfiguration(
                id=f"bcfg-default-{checkpoint_id[:8]}",
                key="BCFG-default",
                plan_id=plan_id,
                plugin_id=plugin_id or "spec2gds.reference.bundle",
                plugin_version=plugin_version or "1.0.0",
                package_digest=sha256_digest(b"spec2gds.reference.bundle:1.0.0"),
                toolchain_identifier="reference",
                version_constraints=">=1.0",
                config_json={},
                capability_snapshot={},
                configuration_digest=sha256_digest(b"{}"),
                created_at=datetime.now(timezone.utc).isoformat(),
            )

        resolved_plugin_id = plugin_id or target_bcfg.plugin_id
        resolved_version = plugin_version or target_bcfg.plugin_version

        plugin = default_plugin_registry.get_backend(resolved_plugin_id, resolved_version)
        if not plugin:
            raise DomainValidationError(
                f"Required backend plugin '{resolved_plugin_id}' version '{resolved_version}' is not installed."
            )

        # Retrieve coverage objectives from upstream coverage checkpoint
        objectives: list[CoverageObjective] = []
        if cp.upstream_checkpoint_id:
            upstream_cp = self.repo.get_checkpoint(plan_id, cp.upstream_checkpoint_id)
            if upstream_cp and upstream_cp.payload:
                raw_objs = upstream_cp.payload.get("objectives", [])
                objectives = [CoverageObjective.model_validate(o) for o in raw_objs]

        # Calculate canonical input digest
        request_summary = {
            "checkpoint_id": cp.id,
            "content_hash": cp.content_hash,
            "plugin_id": resolved_plugin_id,
            "plugin_version": resolved_version,
            "recipes": [r.model_dump() for r in sorted(recipes, key=lambda x: x.id)],
            "target_binding_sets": [b.model_dump() for b in sorted(binding_sets, key=lambda x: x.id)],
            "backend_configuration": target_bcfg.model_dump(),
        }
        input_digest = sha256_digest(canonical_json(request_summary))

        request = GenerationRequest(
            schema_version=SCHEMA_VERSION_GENERATION_REQUEST,
            checkpoint_id=cp.id,
            recipes=recipes,
            target_binding_sets=binding_sets,
            backend_configuration=target_bcfg,
            coverage_objectives=objectives,
            input_digest=input_digest,
        )
        return request, plugin

    def preview_generation(
        self,
        plan_id: str,
        checkpoint_id: str,
        plugin_id: str | None = None,
        plugin_version: str | None = None,
    ) -> dict[str, Any]:
        """Preview generation without writing files or mutating state."""
        request, plugin = self.build_generation_request(
            plan_id, checkpoint_id, plugin_id, plugin_version
        )
        manifest = plugin.describe()
        diagnostics = plugin.validate(request)

        return {
            "plan_id": plan_id,
            "checkpoint_id": checkpoint_id,
            "input_digest": request.input_digest,
            "plugin": manifest.model_dump(),
            "recipes_count": len(request.recipes),
            "diagnostics": diagnostics,
            "ready_to_generate": len([d for d in diagnostics if d.get("severity") == "error"]) == 0,
        }

    def run_generation(
        self,
        plan_id: str,
        checkpoint_id: str,
        plugin_id: str | None = None,
        plugin_version: str | None = None,
    ) -> dict[str, Any]:
        """Execute generation synchronously and store artifacts."""
        request, plugin = self.build_generation_request(
            plan_id, checkpoint_id, plugin_id, plugin_version
        )
        manifest = plugin.describe()

        # Idempotency check: see if identical job already succeeded
        existing_jobs = self.repo.list_generation_jobs(plan_id)
        for job in existing_jobs:
            if (
                job["checkpoint_id"] == checkpoint_id
                and job["plugin_id"] == manifest.plugin_id
                and job["plugin_version"] == manifest.version
                and job["status"] == "succeeded"
                and job["request_data"].get("input_digest") == request.input_digest
            ):
                return job

        now_iso = datetime.now(timezone.utc).isoformat()
        job_id = str(uuid.uuid4())

        # Validate request
        diagnostics = plugin.validate(request)
        error_diags = [d for d in diagnostics if d.get("severity") == "error"]
        if error_diags:
            job_record = {
                "id": job_id,
                "plan_id": plan_id,
                "checkpoint_id": checkpoint_id,
                "plugin_id": manifest.plugin_id,
                "plugin_version": manifest.version,
                "status": "failed",
                "request_data": request.model_dump(),
                "result_data": None,
                "diagnostics": diagnostics,
                "created_at": now_iso,
                "updated_at": now_iso,
            }
            self.repo.save_generation_job(job_record)
            return job_record

        # Save running job record
        job_record = {
            "id": job_id,
            "plan_id": plan_id,
            "checkpoint_id": checkpoint_id,
            "plugin_id": manifest.plugin_id,
            "plugin_version": manifest.version,
            "status": "running",
            "request_data": request.model_dump(),
            "result_data": None,
            "diagnostics": diagnostics,
            "created_at": now_iso,
            "updated_at": now_iso,
        }
        self.repo.save_generation_job(job_record)

        try:
            # Lower & Generate
            lowered = plugin.lower(request)
            writer = OutputWriter()
            gen_result = plugin.generate(request, lowered, writer)

            # Persist artifacts into BlobStore and database
            all_staged = writer.get_all_artifacts()
            persisted_descriptors = []

            for rel_path, (data_bytes, role, media_type) in all_staged.items():
                blob_hash = self.blob_store.put_bytes(data_bytes)
                sha = hashlib.sha256(data_bytes).hexdigest()
                artifact_id = str(uuid.uuid4())
                artifact_record = {
                    "id": artifact_id,
                    "job_id": job_id,
                    "plan_id": plan_id,
                    "relative_path": rel_path,
                    "role": role,
                    "media_type": media_type,
                    "sha256": sha,
                    "blob_digest": blob_hash if blob_hash.startswith("sha256:") else f"sha256:{blob_hash}",
                    "size_bytes": len(data_bytes),
                    "created_at": now_iso,
                }
                self.repo.save_generated_artifact(artifact_record)
                persisted_descriptors.append(artifact_record)

            # Save producer manifest
            self.repo.save_producer_manifest(gen_result.producer_manifest, plan_id)

            # Update job record to succeeded
            result_payload = gen_result.model_dump() | {
                "artifact_records": persisted_descriptors,
            }
            now_finished = datetime.now(timezone.utc).isoformat()
            self.repo.update_generation_job_status(
                job_id=job_id,
                status="succeeded",
                result_data=result_payload,
                diagnostics=diagnostics,
                updated_at=now_finished,
            )
            return self.repo.get_generation_job(plan_id, job_id) or job_record

        except Exception as exc:
            now_failed = datetime.now(timezone.utc).isoformat()
            fail_diags = diagnostics + [{
                "code": "generation.exception",
                "severity": "error",
                "message": f"Plugin generation failed: {str(exc)}",
            }]
            self.repo.update_generation_job_status(
                job_id=job_id,
                status="failed",
                result_data=None,
                diagnostics=fail_diags,
                updated_at=now_failed,
            )
            return self.repo.get_generation_job(plan_id, job_id) or job_record

    def cancel_generation(self, plan_id: str, job_id: str) -> dict[str, Any]:
        """Cancel queued or running generation job."""
        job = self.repo.get_generation_job(plan_id, job_id)
        if not job:
            raise RecordNotFoundError(plan_id, job_id)
        if job["status"] in {"running", "queued"}:
            now_iso = datetime.now(timezone.utc).isoformat()
            self.repo.update_generation_job_status(
                job_id=job_id,
                status="cancelled",
                result_data=None,
                diagnostics=job.get("diagnostics", []),
                updated_at=now_iso,
            )
        return self.repo.get_generation_job(plan_id, job_id) or job

    def retry_generation(self, plan_id: str, job_id: str) -> dict[str, Any]:
        """Retry generation using the identical saved immutable request."""
        job = self.repo.get_generation_job(plan_id, job_id)
        if not job:
            raise RecordNotFoundError(plan_id, job_id)
        return self.run_generation(
            plan_id=plan_id,
            checkpoint_id=job["checkpoint_id"],
            plugin_id=job["plugin_id"],
            plugin_version=job["plugin_version"],
        )
