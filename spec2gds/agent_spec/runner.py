"""Run coordinator for agent-spec v1 actions."""

import typing

import spec2gds.agent_spec.actions as agent_actions
import spec2gds.agent_spec.models as agent_models
import spec2gds.agent_spec.repository as agent_repository


class AgentSpecRunner:
    """Coordinates snapshots, action execution, sanity checks, and ODT writeback."""

    repository: agent_repository.AgentSpecRepository
    registry: agent_actions.ActionRegistry
    events: list[agent_models.RunEvent]

    def __init__(
        self,
        repository: agent_repository.AgentSpecRepository,
        registry: agent_actions.ActionRegistry,
    ) -> None:
        self.repository = repository
        self.registry = registry
        self.events = []

    def available_actions(self, block_id: str) -> list[agent_models.ActionSpec]:
        self.repository.project_graph()
        block = self.repository.graph.blocks[block_id]
        return self.registry.actions_for_tags(block.tags)

    def trigger_action(
        self,
        action_id: str,
        block_id: str,
        parameters: dict[str, typing.Any] | None = None,
    ) -> agent_models.RunRecord:
        if parameters is None:
            parameters = {}
        self.repository.project_graph()
        registered_action = self.registry.get(action_id)
        block = self.repository.graph.blocks[block_id]
        self._validate_action_for_block(registered_action.spec, block)
        snapshot = self._capture_snapshot(block_id, parameters)
        run_id = agent_repository.stable_id("run")
        run_record = agent_models.RunRecord(
            run_id=run_id,
            action_id=action_id,
            status="queued",
            input_snapshot_id=snapshot.snapshot_id,
            read_set=[
                agent_models.SourceTrace(
                    block_id=version.block_id,
                    version_id=version.version_id,
                    artifact_refs=[artifact.artifact_id for artifact in snapshot.artifact_refs],
                )
                for version in snapshot.selected_versions
            ],
        )
        run_events: list[agent_models.RunEvent] = []
        run_events.append(self._event("run.created", run_id, {"action_id": action_id}, len(run_events) + 1))
        run_record.status = "running"
        run_record.started_at = agent_repository.utc_now()
        run_events.append(self._event("run.started", run_id, {"snapshot_id": snapshot.snapshot_id}, len(run_events) + 1))
        context = agent_models.ActionRunContext(
            action=registered_action.spec,
            snapshot=snapshot,
            run_id=run_id,
            sidecar_root=str(self.repository.sidecar_root),
            user_identity=self.repository.user_identity,
        )
        try:
            result = registered_action.handler(context)
            diagnostics = list(result.diagnostics)
            accepted_artifacts: list[agent_models.ArtifactRef] = []
            for artifact in result.artifacts:
                artifact_diagnostics = self._artifact_diagnostics(artifact, snapshot, registered_action.spec)
                diagnostics.extend(artifact_diagnostics)
                if artifact_diagnostics:
                    continue
                self.repository.append_artifact(artifact, block_id=block_id, run_id=run_id)
                accepted_artifacts.append(artifact)
                run_events.append(
                    self._event(
                        "run.artifact.created",
                        run_id,
                        {"artifact_id": artifact.artifact_id, "external_uri": artifact.external_uri},
                        len(run_events) + 1,
                    )
                )
            writeback_status = "auto_applied" if not diagnostics else "needs_human_feedback"
            writeback = agent_models.WritebackRecord(
                writeback_id=agent_repository.stable_id("wb"),
                run_id=run_id,
                document_id=self.repository.manifest.document_id,
                base_document_hash=snapshot.source_document_hash,
                read_set=run_record.read_set,
                artifact_ids=[artifact.artifact_id for artifact in accepted_artifacts],
                diagnostics=diagnostics,
                status=writeback_status,
                created_at=agent_repository.utc_now(),
            )
            self.repository.persist_writeback(writeback)
            event_type = "run.writeback.applied" if writeback_status == "auto_applied" else "run.needs_human_feedback"
            run_events.append(self._event(event_type, run_id, {"writeback_id": writeback.writeback_id}, len(run_events) + 1))
            run_record.produced_artifact_ids = [artifact.artifact_id for artifact in accepted_artifacts]
            run_record.diagnostics = diagnostics
            run_record.status = "completed"
            run_record.completed_at = agent_repository.utc_now()
            run_events.append(self._event("run.completed", run_id, {"status": run_record.status}, len(run_events) + 1))
            self.repository.persist_snapshot(run_id, snapshot)
            self.repository.persist_run(run_record, run_events)
            self.repository.persist_checkpoint(
                agent_repository.stable_id("checkpoint"),
                {
                    "run_id": run_id,
                    "writeback_id": writeback.writeback_id,
                    "artifact_ids": run_record.produced_artifact_ids,
                    "status": writeback_status,
                },
            )
            self.repository.save()
        except Exception as exc:
            run_record.status = "failed"
            run_record.completed_at = agent_repository.utc_now()
            run_record.diagnostics.append(
                agent_models.AgentSpecDiagnostic(
                    severity="error",
                    source=action_id,
                    message=str(exc),
                )
            )
            run_events.append(self._event("run.failed", run_id, {"error": str(exc)}, len(run_events) + 1))
            self.repository.persist_snapshot(run_id, snapshot)
            self.repository.persist_run(run_record, run_events)
            self.repository.save()
        self.events.extend(run_events)
        return run_record

    def _validate_action_for_block(
        self,
        action: agent_models.ActionSpec,
        block: agent_models.BlockRecord,
    ) -> None:
        if action.required_tags and not set(action.required_tags).intersection(block.tags):
            raise ValueError(f"Action {action.action_id} is not available for block {block.block_id}.")

    def _capture_snapshot(
        self,
        block_id: str,
        parameters: dict[str, typing.Any],
    ) -> agent_models.InputSnapshot:
        active_version = self.repository.active_version(block_id)
        artifacts = self.repository.attachment_artifacts(block_id)
        return agent_models.InputSnapshot(
            snapshot_id=agent_repository.stable_id("snap"),
            document_id=self.repository.manifest.document_id,
            source_document_hash=self.repository._file_hash(),
            created_at=agent_repository.utc_now(),
            selected_versions=[active_version],
            artifact_refs=artifacts,
            parameters=dict(parameters),
        )

    def _artifact_diagnostics(
        self,
        artifact: agent_models.ArtifactRef,
        snapshot: agent_models.InputSnapshot,
        action: agent_models.ActionSpec,
    ) -> list[agent_models.AgentSpecDiagnostic]:
        diagnostics: list[agent_models.AgentSpecDiagnostic] = []
        if not artifact.sha256.startswith("sha256:") or len(artifact.sha256) != 71:
            diagnostics.append(self._diagnostic("Malformed artifact hash.", artifact.artifact_id))
        if not artifact.external_uri.startswith(("file://", "artifact-store://")):
            diagnostics.append(self._diagnostic("Unsupported artifact URI.", artifact.artifact_id))
        version_ids = {version.version_id for version in snapshot.selected_versions}
        if artifact.source_trace.version_id not in version_ids:
            diagnostics.append(self._diagnostic("Artifact source version was not in the input snapshot.", artifact.artifact_id))
        if action.output_roles and artifact.role not in action.output_roles:
            diagnostics.append(self._diagnostic("Artifact role is not allowed by action output contract.", artifact.artifact_id))
        if not artifact.summary or not artifact.media_type or not artifact.artifact_kind:
            diagnostics.append(self._diagnostic("Artifact metadata is incomplete.", artifact.artifact_id))
        return diagnostics

    def _diagnostic(self, message: str, target_id: str) -> agent_models.AgentSpecDiagnostic:
        return agent_models.AgentSpecDiagnostic(
            severity="error",
            source="writeback.sanity",
            message=message,
            target_id=target_id,
        )

    def _event(
        self,
        event_type: str,
        run_id: str,
        payload: dict[str, typing.Any],
        sequence: int,
    ) -> agent_models.RunEvent:
        return agent_models.RunEvent(
            event_id=agent_repository.stable_id("evt"),
            event_type=event_type,
            document_id=self.repository.manifest.document_id,
            aggregate_id=run_id,
            sequence=sequence,
            created_at=agent_repository.utc_now(),
            actor={"kind": "server", "id": self.repository.user_identity},
            payload=payload,
        )
