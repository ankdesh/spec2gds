"""Action run coordinator with executor callbacks and report persistence."""

import json
import pathlib
import threading
import time
import typing

import jsonschema

import spec2gds.agent_spec.actions as agent_actions
import spec2gds.agent_spec.models as agent_models
import spec2gds.agent_spec.storage.repository as agent_repository


REPORT_CATALOG = json.loads((pathlib.Path(__file__).resolve().parents[1] / "a2ui" / "report_catalog.json").read_text(encoding="utf-8"))


class ExecutorDispatcher:
    """Boundary for future codegen, compile, and simulation integrations."""

    def dispatch(self, action: agent_models.ActionSpec, launch: agent_models.ActionLaunch) -> None:
        """Record-only default; integrations may override this to start work."""
        del action, launch


class AgentSpecRunner:
    """Captures inputs, dispatches runs, and validates executor completion."""

    def __init__(
        self,
        repository: agent_repository.AgentSpecRepository,
        registry: agent_actions.ActionRegistry,
        dispatcher: ExecutorDispatcher | None = None,
    ) -> None:
        self.repository = repository
        self.registry = registry
        self.dispatcher = dispatcher or ExecutorDispatcher()
        self.events: list[agent_models.RunEvent] = []

    def available_actions(self, block_id: str) -> list[agent_models.ActionSpec]:
        self.repository.project_graph()
        if block_id not in self.repository.graph.blocks:
            raise KeyError(f"Unknown block: {block_id}")
        return self.registry.list_actions()

    def check_preconditions(
        self,
        action_id: str,
        block_id: str,
        inputs: dict[str, typing.Any] | None = None,
    ) -> agent_models.PreconditionReport:
        inputs = inputs or {}
        self.repository.project_graph()
        if block_id not in self.repository.graph.blocks:
            raise KeyError(f"Unknown block: {block_id}")
        action = self.registry.get(action_id)
        checks: list[agent_models.ConditionCheck] = []
        try:
            jsonschema.validate(inputs, action.spec.input_schema)
            checks.append(agent_models.ConditionCheck(check_id="input-schema", severity="info", message="Action input is valid.", passed=True))
        except jsonschema.ValidationError as exc:
            checks.append(agent_models.ConditionCheck(check_id="input-schema", severity="error", message=exc.message, passed=False))
        checks.extend(self._input_schema_support_checks(action.spec.input_schema))
        if action.precondition is not None:
            checks.extend(action.precondition(block_id, inputs))
        return agent_models.PreconditionReport(
            action_id=action_id,
            block_id=block_id,
            can_execute=all(check.passed for check in checks),
            checks=checks,
            checked_at=agent_repository.utc_now(),
        )

    def _input_schema_support_checks(self, schema: dict[str, typing.Any]) -> list[agent_models.ConditionCheck]:
        """Reject schemas the generic Actions popover cannot render safely."""
        unsupported: list[str] = []
        if schema.get("type") != "object":
            unsupported.append("root must be an object")
        for name, field in schema.get("properties", {}).items():
            if not isinstance(field, dict) or field.get("type", "string") not in {"string", "number", "integer", "boolean"}:
                unsupported.append(name)
            if any(key in field for key in ("oneOf", "anyOf", "allOf", "items", "properties")):
                unsupported.append(name)
        if not unsupported:
            return []
        return [
            agent_models.ConditionCheck(
                check_id="input-form-support",
                severity="error",
                message=f"The generic Actions form cannot render this input schema: {', '.join(sorted(set(unsupported)))}.",
                passed=False,
            )
        ]

    def launch_action(
        self,
        action_id: str,
        block_id: str,
        inputs: dict[str, typing.Any] | None = None,
    ) -> agent_models.ActionLaunch:
        inputs = inputs or {}
        action = self.registry.get(action_id)
        preconditions = self.check_preconditions(action_id, block_id, inputs)
        if not preconditions.can_execute:
            raise ValueError("Action preconditions did not pass.")
        snapshot = self._capture_snapshot(block_id, inputs, preconditions)
        run_id = agent_repository.stable_id("run")
        run = agent_models.RunRecord(
            run_id=run_id,
            action_id=action_id,
            status="queued",
            input_snapshot_id=snapshot.snapshot_id,
            read_set=self._read_set(snapshot),
        )
        events = [self._event("run.created", run_id, {"action_id": action_id}, 1)]
        run.status = "running"
        run.started_at = agent_repository.utc_now()
        events.append(self._event("run.started", run_id, {"snapshot_id": snapshot.snapshot_id}, 2))
        completion_url = f"/agent-spec/runs/{run_id}/completion"
        launch = agent_models.ActionLaunch(run=run, snapshot=snapshot, completion_url=completion_url)
        self.repository.persist_snapshot(run_id, snapshot)
        events.append(
            self._event(
                "run.executor.dispatched",
                run_id,
                {"executor_id": action.spec.executor_id, "completion_url": completion_url},
                3,
            )
        )
        self.repository.persist_run(run, events)
        self.repository.save()
        self.events.extend(events)
        self.dispatcher.dispatch(action.spec, launch)
        if action.spec.executor_id == "agent-spec.pseudo-delayed-report":
            self._start_delayed_report(launch)
        return launch

    def _start_delayed_report(self, launch: agent_models.ActionLaunch) -> None:
        """Run the local demonstration executor without blocking the request."""
        def complete_after_delay() -> None:
            time.sleep(5)
            self.complete_action(
                launch.run.run_id,
                "succeeded",
                [],
                {
                    "summary": "Delayed report completed.",
                    "details": "The local pseudo executor waited five seconds before reporting success.",
                },
            )

        threading.Thread(target=complete_after_delay, name=f"agent-spec-{launch.run.run_id}", daemon=True).start()

    def complete_action(
        self,
        run_id: str,
        outcome: str,
        artifacts: list[agent_models.ArtifactRef],
        report_data: dict[str, typing.Any],
    ) -> agent_models.RunRecord:
        if outcome not in {"succeeded", "failed"}:
            raise ValueError("Executor outcome must be 'succeeded' or 'failed'.")
        run = self._load_run(run_id)
        if run.status not in {"queued", "running"}:
            raise ValueError(f"Run {run_id} is not accepting completion.")
        snapshot = self._load_snapshot(run_id)
        action = self.registry.get(run.action_id)
        events = self._load_events(run_id)
        checks: list[agent_models.ConditionCheck] = []
        accepted: list[agent_models.ArtifactRef] = []

        if outcome == "succeeded":
            try:
                jsonschema.validate(report_data, action.spec.report_schema)
                checks.append(agent_models.ConditionCheck(check_id="report-schema", severity="info", message="Executor report is valid.", passed=True))
            except jsonschema.ValidationError as exc:
                checks.append(agent_models.ConditionCheck(check_id="report-schema", severity="error", message=exc.message, passed=False))
            for artifact in artifacts:
                diagnostics = self._artifact_diagnostics(artifact, snapshot, action.spec)
                if diagnostics:
                    checks.extend(diagnostics)
                    continue
                self.repository.append_artifact(artifact, snapshot.selected_versions[0].block_id, run_id)
                accepted.append(artifact)
                events.append(self._event("run.artifact.created", run_id, {"artifact_id": artifact.artifact_id}, len(events) + 1))
            if action.postcondition is not None:
                checks.extend(action.postcondition(report_data))
        else:
            checks.append(agent_models.ConditionCheck(check_id="executor-outcome", severity="error", message="Executor reported failure.", passed=False))

        review_required = outcome == "succeeded" and not all(check.passed for check in checks)
        postconditions = agent_models.PostconditionReport(
            action_id=run.action_id,
            run_id=run_id,
            review_required=review_required,
            checks=checks,
            checked_at=agent_repository.utc_now(),
        )
        messages = self._report_messages(run, outcome, report_data, accepted, postconditions)
        try:
            self._validate_report_messages(messages)
        except ValueError as exc:
            review_required = True
            postconditions.review_required = True
            postconditions.checks.append(
                agent_models.ConditionCheck(check_id="report-surface", severity="error", message=str(exc), passed=False)
            )
            messages = self._fallback_report_messages(run, outcome, str(exc))
        report = agent_models.ActionReport(
            run_id=run_id,
            action_id=run.action_id,
            executor_outcome=outcome,
            data=report_data,
            artifact_ids=[artifact.artifact_id for artifact in accepted],
            postcondition_report=postconditions,
            review_required=review_required,
            surface_id=f"report-{run_id}",
        )
        self.repository.persist_report(report, messages)
        run.produced_artifact_ids = report.artifact_ids
        run.diagnostics = [
            agent_models.AgentSpecDiagnostic(severity=check.severity, source="postcondition", message=check.message)
            for check in checks
            if not check.passed
        ]
        run.status = "completed" if outcome == "succeeded" else "failed"
        run.completed_at = agent_repository.utc_now()
        events.append(self._event("run.completed" if outcome == "succeeded" else "run.failed", run_id, {"status": run.status}, len(events) + 1))
        self.repository.persist_run(run, events)
        self.repository.persist_checkpoint(
            agent_repository.stable_id("checkpoint"),
            {"run_id": run_id, "artifact_ids": report.artifact_ids, "review_required": review_required},
        )
        self.repository.save()
        self.events.extend(events)
        return run

    def _capture_snapshot(
        self,
        block_id: str,
        inputs: dict[str, typing.Any],
        precondition_report: agent_models.PreconditionReport,
    ) -> agent_models.InputSnapshot:
        active = self.repository.active_version(block_id)
        return agent_models.InputSnapshot(
            snapshot_id=agent_repository.stable_id("snapshot"),
            document_id=self.repository.manifest.document_id,
            source_document_hash=self.repository.loaded_file_hash,
            created_at=agent_repository.utc_now(),
            selected_versions=[active],
            artifact_refs=self.repository.attachment_artifacts(block_id),
            inputs=inputs,
            precondition_report=precondition_report,
        )

    def _read_set(self, snapshot: agent_models.InputSnapshot) -> list[agent_models.SourceTrace]:
        return [
            agent_models.SourceTrace(
                block_id=item.block_id,
                version_id=item.version_id,
                artifact_refs=[artifact.artifact_id for artifact in snapshot.artifact_refs],
            )
            for item in snapshot.selected_versions
        ]

    def _fallback_report_messages(self, run: agent_models.RunRecord, outcome: str, message: str) -> list[dict[str, typing.Any]]:
        return [
            {"version": "v0.9", "createSurface": {"surfaceId": f"report-{run.run_id}", "catalogId": REPORT_CATALOG["catalogId"]}},
            {"version": "v0.9", "updateComponents": {"surfaceId": f"report-{run.run_id}", "components": [
                {"id": "root", "component": "Column", "children": ["summary", "checks", "artifacts"]},
                {"id": "summary", "component": "ReportSummary", "outcome": outcome, "summary": "Report rendering requires review."},
                {"id": "checks", "component": "CheckList", "checks": [{"check_id": "report-surface", "severity": "error", "message": message, "passed": False}]},
                {"id": "artifacts", "component": "ArtifactList", "artifacts": []},
            ]}},
        ]

    def _validate_report_messages(self, messages: list[dict[str, typing.Any]]) -> None:
        """Enforce the small read-only report catalog before persistence."""
        allowed = set(REPORT_CATALOG["components"])
        for message in messages:
            update = message.get("updateComponents")
            if not isinstance(update, dict):
                continue
            for component in update.get("components", []):
                if not isinstance(component, dict) or component.get("component") not in allowed:
                    raise ValueError("Generated report uses a component outside agent-spec.report.v1.")

    def _artifact_diagnostics(
        self,
        artifact: agent_models.ArtifactRef,
        snapshot: agent_models.InputSnapshot,
        action: agent_models.ActionSpec,
    ) -> list[agent_models.ConditionCheck]:
        checks: list[agent_models.ConditionCheck] = []
        if not artifact.sha256.startswith("sha256:") or len(artifact.sha256) != 71:
            checks.append(agent_models.ConditionCheck(check_id="artifact-hash", severity="error", message="Artifact hash must be a SHA-256 value.", passed=False))
        if not artifact.external_uri.startswith(("file://", "artifact-store://")):
            checks.append(agent_models.ConditionCheck(check_id="artifact-uri", severity="error", message="Artifact URI is unsupported.", passed=False))
        selected = snapshot.selected_versions[0]
        if artifact.source_trace.block_id != selected.block_id or artifact.source_trace.version_id != selected.version_id:
            checks.append(agent_models.ConditionCheck(check_id="artifact-source", severity="error", message="Artifact source trace does not match the run snapshot.", passed=False))
        if action.output_roles and artifact.role not in action.output_roles:
            checks.append(agent_models.ConditionCheck(check_id="artifact-role", severity="error", message="Artifact role is not allowed by this action.", passed=False))
        if not artifact.summary or not artifact.media_type or not artifact.artifact_kind:
            checks.append(agent_models.ConditionCheck(check_id="artifact-metadata", severity="error", message="Artifact metadata is incomplete.", passed=False))
        return checks

    def _report_messages(
        self,
        run: agent_models.RunRecord,
        outcome: str,
        data: dict[str, typing.Any],
        artifacts: list[agent_models.ArtifactRef],
        postconditions: agent_models.PostconditionReport,
    ) -> list[dict[str, typing.Any]]:
        """Build the only A2UI vocabulary accepted by the report renderer."""
        surface_id = f"report-{run.run_id}"
        components = [
            {"id": "root", "component": "Column", "children": ["summary", "checks", "artifacts"]},
            {"id": "summary", "component": "ReportSummary", "outcome": outcome, "summary": str(data.get("summary", "Executor completion report."))},
            {"id": "checks", "component": "CheckList", "checks": [check.model_dump(mode="json") for check in postconditions.checks]},
            {"id": "artifacts", "component": "ArtifactList", "artifacts": [artifact.model_dump(mode="json") for artifact in artifacts]},
        ]
        return [
            {"version": "v0.9", "createSurface": {"surfaceId": surface_id, "catalogId": REPORT_CATALOG["catalogId"]}},
            {"version": "v0.9", "updateComponents": {"surfaceId": surface_id, "components": components}},
            {
                "version": "v0.9",
                "updateDataModel": {
                    "surfaceId": surface_id,
                    "path": "/",
                    "value": {
                        "report": data,
                        "checks": [check.model_dump(mode="json") for check in postconditions.checks],
                        "artifacts": [artifact.model_dump(mode="json") for artifact in artifacts],
                    },
                },
            },
        ]

    def _load_snapshot(self, run_id: str) -> agent_models.InputSnapshot:
        path = f"spec_data/agent-spec/runs/{run_id}/input_snapshot.json"
        if path not in self.repository.container.custom_files:
            raise KeyError(f"Missing input snapshot for run: {run_id}")
        return agent_models.InputSnapshot.model_validate_json(self.repository.container.extract_file(path))

    def _load_run(self, run_id: str) -> agent_models.RunRecord:
        path = f"spec_data/agent-spec/runs/{run_id}/run.json"
        if path not in self.repository.container.custom_files:
            raise KeyError(f"Unknown run: {run_id}")
        return agent_models.RunRecord.model_validate_json(self.repository.container.extract_file(path))

    def _load_events(self, run_id: str) -> list[agent_models.RunEvent]:
        path = f"spec_data/agent-spec/runs/{run_id}/events.ndjson"
        if path not in self.repository.container.custom_files:
            return []
        return [agent_models.RunEvent.model_validate(json.loads(line)) for line in self.repository.container.extract_file(path).decode().splitlines() if line]

    def _event(self, event_type: str, run_id: str, payload: dict[str, typing.Any], sequence: int) -> agent_models.RunEvent:
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
