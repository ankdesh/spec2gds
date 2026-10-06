"""Application service coordinator for Verification Planner.

Reviewer path: compose imports, candidate commands, checkpoint review, evidence
and synchronous reference generation. Source snapshots are immutable imports;
this coordinator has no capability to mutate a live Spec or execute a simulator.
"""

from __future__ import annotations

import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from testplan_service.application.command_handler import CommandHandler
from testplan_service.application.coverage_service import CoverageService
from testplan_service.application.export_service import ExportService
from testplan_service.application.generation_runner import GenerationRunner
from testplan_service.application.review_engine import ReviewEngine
from testplan_service.domain.enums import SourceAuditDisposition
from testplan_service.domain.hierarchy import build_hierarchy_tree
from testplan_service.domain.models import (
    Intent,
    PlanCheckpoint,
    PlanHeader,
    Section,
    SourceAuditEntry,
)
from testplan_service.domain.recipe_validation import RecipeValidator
from testplan_service.domain.recipes import BackendConfiguration, Recipe, TargetBindingSet
from testplan_service.exceptions import PlanNotFoundError, RecordNotFoundError
from testplan_service.integrations.models import SourceSnapshotView
from testplan_service.integrations.snapshot_decoder import decode_snapshot_bytes
from testplan_service.storage.blob_store import BlobStore
from testplan_service.storage.sqlite_repo import SqlitePlanRepository


class VerificationPlannerService:
    """Core application coordinator managing domain transactions, persistence, and jobs."""

    def __init__(self, storage_dir: Path | str) -> None:
        self.storage_dir = Path(storage_dir).resolve()
        self.storage_dir.mkdir(parents=True, exist_ok=True)

        self.blob_store = BlobStore(self.storage_dir)
        self.repo = SqlitePlanRepository(self.storage_dir / "verification.db")
        self.command_handler = CommandHandler(self.repo)
        self.review_engine = ReviewEngine(self.repo)
        self.export_service = ExportService(self.repo, self.blob_store)
        self.coverage_service = CoverageService(self.repo)
        self.generation_runner = GenerationRunner(self.repo, self.blob_store)
        self.recipe_validator = RecipeValidator()

    def import_source(self, data: bytes) -> tuple[str, SourceSnapshotView]:
        """Stage, decode, and store an Activity Snapshot v1."""
        view = decode_snapshot_bytes(data)
        blob_hash = self.blob_store.put_bytes(data)
        now_iso = datetime.now(timezone.utc).isoformat()
        self.repo.save_snapshot(view, blob_hash, now_iso)
        return view.snapshot_id, view

    def create_plan(
        self,
        name: str,
        snapshot_id: str,
        root_scope_id: str,
        description: str = "",
        designer_label: str | None = None,
        tags: list[str] | None = None,
    ) -> PlanHeader:
        """Create a new plan bound to a validated snapshot, initializing audit entries."""
        snapshot = self.repo.get_snapshot(snapshot_id)
        if not snapshot:
            raise RecordNotFoundError("snapshot", snapshot_id)

        plan_id = str(uuid.uuid4())
        now_iso = datetime.now(timezone.utc).isoformat()

        # Initialize source audit entries for each in-scope section
        source_audit: dict[str, SourceAuditEntry] = {}
        for sec in snapshot.source_sections:
            source_audit[sec.section_id] = SourceAuditEntry(
                section_id=sec.section_id,
                disposition=SourceAuditDisposition.UNREVIEWED,
                reason=None,
                linked_requirement_ids=[],
                reviewer_label=designer_label or "author",
                source_digest=sec.content_digest,
                updated_at=now_iso,
            )

        header = PlanHeader(
            id=plan_id,
            name=name,
            description=description,
            snapshot_id=snapshot_id,
            root_scope_id=root_scope_id,
            designer_label=designer_label,
            tags=tags or [],
            source_audit=source_audit,
            edit_revision=1,
            created_at=now_iso,
            updated_at=now_iso,
        )

        self.repo.create_plan(header)
        return header

    def get_plan(self, plan_id: str) -> PlanHeader | None:
        return self.repo.get_plan(plan_id)

    def list_plans(self) -> list[PlanHeader]:
        return self.repo.list_plans()

    def get_snapshot_view(self, snapshot_id: str) -> SourceSnapshotView | None:
        return self.repo.get_snapshot(snapshot_id)

    def execute_commands(
        self,
        plan_id: str,
        base_edit_revision: int,
        request_id: str,
        operations: list[dict[str, Any]],
        preview_only: bool = False,
    ) -> dict[str, Any]:
        return self.command_handler.execute_batch(
            plan_id=plan_id,
            base_edit_revision=base_edit_revision,
            request_id=request_id,
            operations=operations,
            preview_only=preview_only,
        )

    def preview_checkpoint(
        self,
        plan_id: str,
        layer: str = "plan",
        upstream_checkpoint_id: str | None = None,
    ) -> dict[str, Any]:
        return self.review_engine.evaluate_checklist(
            plan_id=plan_id,
            layer=layer,
            upstream_checkpoint_id=upstream_checkpoint_id,
        )

    def create_checkpoint(
        self,
        plan_id: str,
        reviewer_label: str,
        comment: str,
        expected_digest: str | None = None,
        acknowledged_warnings: list[str] | None = None,
        layer: str = "plan",
        upstream_checkpoint_id: str | None = None,
    ) -> PlanCheckpoint:
        return self.review_engine.create_checkpoint(
            plan_id=plan_id,
            reviewer_label=reviewer_label,
            comment=comment,
            expected_digest=expected_digest,
            acknowledged_warnings=acknowledged_warnings,
            layer=layer,
            upstream_checkpoint_id=upstream_checkpoint_id,
        )

    def get_checkpoint(self, plan_id: str, checkpoint_id: str) -> PlanCheckpoint | None:
        return self.repo.get_checkpoint(plan_id, checkpoint_id)

    def list_checkpoints(self, plan_id: str) -> list[PlanCheckpoint]:
        return self.repo.list_checkpoints(plan_id)

    def export_bundle(self, plan_id: str) -> bytes:
        return self.export_service.export_vplan_bundle(plan_id)

    def import_bundle(self, bundle_bytes: bytes, resolution: str = "create") -> str:
        return self.export_service.import_vplan_bundle(bundle_bytes, resolution)

    def export_markdown(self, plan_id: str) -> str:
        return self.export_service.export_markdown(plan_id)

    def export_csv(self, plan_id: str) -> str:
        return self.export_service.export_csv(plan_id)

    def get_records(
        self,
        plan_id: str,
        record_type: str | None = None,
        scope_id: str | None = None,
        include_archived: bool = False,
    ) -> list[dict[str, Any]]:
        return self.repo.get_records(plan_id, record_type, scope_id, include_archived)

    def get_record(self, plan_id: str, record_id: str) -> dict[str, Any] | None:
        return self.repo.get_record(plan_id, record_id)

    def get_hierarchy(self, plan_id: str, filter_scope_id: str | None = None) -> list[dict[str, Any]]:
        plan = self.repo.get_plan(plan_id)
        if not plan:
            raise PlanNotFoundError(plan_id)

        snapshot = self.repo.get_snapshot(plan.snapshot_id)
        scopes = [o.model_dump() for o in snapshot.occurrences] if snapshot else []

        raw_records = self.repo.get_records(plan_id, include_archived=False)
        sections = {
            r["id"]: Section.model_validate(r)
            for r in raw_records
            if r.get("record_type") == "section"
        }
        intents = {
            r["id"]: Intent.model_validate(r)
            for r in raw_records
            if r.get("record_type") == "intent"
        }

        return build_hierarchy_tree(scopes, sections, intents, filter_scope_id)

    def search_plan(self, plan_id: str, query: str) -> list[dict[str, Any]]:
        """Search records, requirements, and source sections matching query string."""
        plan = self.repo.get_plan(plan_id)
        if not plan:
            raise PlanNotFoundError(plan_id)

        q = query.strip().lower()
        if not q:
            return []

        records = self.repo.get_records(plan_id, include_archived=False)
        results: list[dict[str, Any]] = []

        for rec in records:
            title = rec.get("title", "").lower()
            key = rec.get("key", "").lower()
            statement = rec.get("statement", "").lower()
            given = rec.get("preconditions", "").lower()
            when = rec.get("trigger", "").lower()
            then = rec.get("expected_behavior", "").lower()

            if q in title or q in key or q in statement or q in given or q in when or q in then:
                results.append({
                    "id": rec["id"],
                    "key": rec["key"],
                    "kind": rec["record_type"],
                    "title": rec.get("title", ""),
                    "scope_id": rec.get("scope_id", ""),
                })

        return results

    def get_events(self, plan_id: str, since_event_id: str | None = None) -> list[dict[str, Any]]:
        return self.repo.get_events(plan_id, since_event_id)

    # --- Layer 2 Coverage Delegations ---
    def create_profile(
        self,
        plan_id: str,
        display_name: str,
        coverage_checkpoint_id: str,
        source_snapshot_id: str,
        source_snapshot_hash: str,
        dut_source_hash: str,
        root_occurrence_id: str,
        resolved_parameters: dict[str, Any] | None = None,
        clock_reset_config: dict[str, Any] | None = None,
        realization_descriptors: list[dict[str, Any]] | None = None,
        profile_id: str | None = None,
    ) -> Any:
        return self.coverage_service.create_profile(
            plan_id=plan_id,
            display_name=display_name,
            coverage_checkpoint_id=coverage_checkpoint_id,
            source_snapshot_id=source_snapshot_id,
            source_snapshot_hash=source_snapshot_hash,
            dut_source_hash=dut_source_hash,
            root_occurrence_id=root_occurrence_id,
            resolved_parameters=resolved_parameters,
            clock_reset_config=clock_reset_config,
            realization_descriptors=realization_descriptors,
            profile_id=profile_id,
        )

    def get_profile(self, plan_id: str, profile_id: str) -> Any:
        return self.coverage_service.get_profile(plan_id, profile_id)

    def list_profiles(self, plan_id: str) -> list[Any]:
        return self.coverage_service.list_profiles(plan_id)

    def create_campaign(
        self,
        plan_id: str,
        title: str,
        coverage_checkpoint_id: str = "",
        required_profile_ids: list[str] | None = None,
        purpose: str = "verification",
        campaign_id: str | None = None,
    ) -> Any:
        return self.coverage_service.create_campaign(
            plan_id=plan_id,
            title=title,
            coverage_checkpoint_id=coverage_checkpoint_id,
            required_profile_ids=required_profile_ids or [],
            purpose=purpose,
            campaign_id=campaign_id,
        )

    def get_campaign(self, plan_id: str, campaign_id: str) -> Any:
        return self.coverage_service.get_campaign(plan_id, campaign_id)

    def list_campaigns(self, plan_id: str) -> list[Any]:
        return self.coverage_service.list_campaigns(plan_id)

    def execute_campaign_commands(
        self,
        plan_id: str,
        campaign_id: str,
        base_campaign_revision: int,
        request_id: str,
        operations: list[dict[str, Any]],
    ) -> dict[str, Any]:
        return self.coverage_service.execute_campaign_commands(
            plan_id=plan_id,
            campaign_id=campaign_id,
            base_campaign_revision=base_campaign_revision,
            request_id=request_id,
            operations=operations,
        )

    def stage_result_import(self, plan_id: str, payload: dict[str, Any]) -> dict[str, Any]:
        return self.coverage_service.stage_result_import(plan_id, payload)

    def commit_result_import(
        self,
        plan_id: str,
        staging_id: str,
        expected_preview_digest: str | None = None,
        campaign_id: str | None = None,
        campaign_revision: int | None = None,
    ) -> dict[str, Any]:
        return self.coverage_service.commit_result_import(
            plan_id=plan_id,
            staging_id=staging_id,
            expected_preview_digest=expected_preview_digest,
            campaign_id=campaign_id,
            campaign_revision=campaign_revision,
        )

    def get_coverage_matrix(
        self,
        plan_id: str,
        checkpoint_id: str | None = None,
        campaign_id: str | None = None,
        filtered_intent_ids: set[str] | None = None,
        status_filter: str | None = None,
    ) -> dict[str, Any]:
        return self.coverage_service.get_coverage_matrix(
            plan_id=plan_id,
            checkpoint_id=checkpoint_id,
            campaign_id=campaign_id,
            filtered_intent_ids=filtered_intent_ids,
            status_filter=status_filter,
        )

    def get_coverage_gaps(
        self,
        plan_id: str,
        checkpoint_id: str | None = None,
        campaign_id: str | None = None,
    ) -> list[Any]:
        return self.coverage_service.get_coverage_gaps(
            plan_id=plan_id,
            checkpoint_id=checkpoint_id,
            campaign_id=campaign_id,
        )

    def create_evidence_report(
        self,
        plan_id: str,
        coverage_checkpoint_id: str,
        campaign_id: str,
    ) -> Any:
        return self.coverage_service.create_evidence_report(
            plan_id=plan_id,
            coverage_checkpoint_id=coverage_checkpoint_id,
            campaign_id=campaign_id,
        )

    def get_evidence_report(self, plan_id: str, report_id: str) -> Any:
        return self.coverage_service.get_evidence_report(plan_id, report_id)

    def get_run(self, plan_id: str, run_id: str) -> Any:
        return self.repo.get_run(plan_id, run_id)

    def list_runs(self, plan_id: str, profile_id: str | None = None) -> list[Any]:
        return self.repo.list_runs(plan_id, profile_id=profile_id)

    def get_observations_for_run(self, run_id: str) -> list[Any]:
        return self.repo.get_observations_for_run(run_id)

    # --- Layer 3 Implementation & Generation Methods ---
    def validate_recipe(self, plan_id: str, recipe_id: str) -> list[dict[str, Any]]:
        recipe = self.repo.get_recipe(plan_id, recipe_id)
        if not recipe:
            raise RecordNotFoundError(plan_id, recipe_id)
        bnd_set = self.repo.get_binding_set(plan_id, recipe.target_binding_set_id) if recipe.target_binding_set_id else None
        upstream_obj_ids = None
        if recipe.coverage_checkpoint_id:
            cp = self.repo.get_checkpoint(plan_id, recipe.coverage_checkpoint_id)
            if cp and cp.payload:
                upstream_obj_ids = {o["id"] for o in cp.payload.get("objectives", [])}
        return self.recipe_validator.validate_recipe(recipe, bnd_set, upstream_obj_ids)

    def get_recipes(self, plan_id: str) -> list[Recipe]:
        return self.repo.get_recipes(plan_id, include_archived=False)

    def get_recipe(self, plan_id: str, recipe_id: str) -> Recipe | None:
        return self.repo.get_recipe(plan_id, recipe_id)

    def get_binding_sets(self, plan_id: str) -> list[TargetBindingSet]:
        return self.repo.get_binding_sets(plan_id, include_archived=False)

    def get_binding_set(self, plan_id: str, binding_set_id: str) -> TargetBindingSet | None:
        return self.repo.get_binding_set(plan_id, binding_set_id)

    def get_backend_configurations(self, plan_id: str) -> list[BackendConfiguration]:
        return self.repo.get_backend_configurations(plan_id)

    def get_backend_configuration(self, plan_id: str, config_id: str) -> BackendConfiguration | None:
        return self.repo.get_backend_configuration(plan_id, config_id)

    def preview_generation(
        self,
        plan_id: str,
        checkpoint_id: str,
        plugin_id: str | None = None,
        plugin_version: str | None = None,
    ) -> dict[str, Any]:
        return self.generation_runner.preview_generation(
            plan_id, checkpoint_id, plugin_id, plugin_version
        )

    def run_generation(
        self,
        plan_id: str,
        checkpoint_id: str,
        plugin_id: str | None = None,
        plugin_version: str | None = None,
    ) -> dict[str, Any]:
        return self.generation_runner.run_generation(
            plan_id, checkpoint_id, plugin_id, plugin_version
        )

    def get_generation_job(self, plan_id: str, job_id: str) -> dict[str, Any] | None:
        return self.repo.get_generation_job(plan_id, job_id)

    def list_generation_jobs(self, plan_id: str) -> list[dict[str, Any]]:
        return self.repo.list_generation_jobs(plan_id)

    def cancel_generation(self, plan_id: str, job_id: str) -> dict[str, Any]:
        return self.generation_runner.cancel_generation(plan_id, job_id)

    def retry_generation(self, plan_id: str, job_id: str) -> dict[str, Any]:
        return self.generation_runner.retry_generation(plan_id, job_id)

    def get_generated_artifact(self, artifact_id: str) -> dict[str, Any] | None:
        return self.repo.get_generated_artifact(artifact_id)

    def get_producer_manifest(self, digest: str) -> Any:
        return self.repo.get_producer_manifest(digest)

