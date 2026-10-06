"""Reference Bundle foundation backend plugin.

Implements 'spec2gds.reference.bundle', emitting deterministic, audit-ready
artifacts (Test IR, Markdown recipe, Producer Manifest, synthetic template,
and validation report) without claiming executable test generation.
"""

from __future__ import annotations

import hashlib
from datetime import datetime, timezone
from typing import Any

from testplan_service.constants import SCHEMA_VERSION_TEST_IR
from testplan_service.domain.hash import canonical_json, sha256_digest
from testplan_service.domain.plugins.base import BackendPlugin, OutputWriter
from testplan_service.domain.plugins.models import (
    GenerationRequest,
    GenerationResult,
    PluginKind,
    PluginManifest,
    PluginPortability,
)
from testplan_service.domain.recipe_validation import RecipeValidator
from testplan_service.domain.recipes import ProducerManifest, ProducerObservation

PLUGIN_ID = "spec2gds.reference.bundle"
PLUGIN_VERSION = "1.0.0"
PACKAGE_DIGEST = sha256_digest(f"{PLUGIN_ID}:{PLUGIN_VERSION}".encode("utf-8"))


class ReferenceBundlePlugin(BackendPlugin):
    """Foundation backend generating deterministic reference artifact bundles."""

    def __init__(self) -> None:
        self.validator = RecipeValidator()

    def describe(self) -> PluginManifest:
        """Return immutable plugin manifest."""
        return PluginManifest(
            plugin_id=PLUGIN_ID,
            version=PLUGIN_VERSION,
            package_digest=PACKAGE_DIGEST,
            kind=PluginKind.BACKEND,
            title="Reference bundle — no executable tests",
            description=(
                "Deterministic foundation backend emitting canonical Test IR, "
                "human-readable recipe markdown, producer manifest, and synthetic result template."
            ),
            contract_versions=["1.0"],
            input_schema_versions=[SCHEMA_VERSION_TEST_IR],
            capabilities={
                "recipe_kinds": ["scenario", "property"],
                "executable": False,
                "produces_rtl": False,
                "supports_parallel": True,
                "supports_models": ["record", "fsm", "bounded_queue"],
                "supports_properties": [
                    "invariant",
                    "implication_fixed_delay",
                    "bounded_response",
                    "stability_window",
                    "reachability_cover",
                ],
            },
            configuration_schema={
                "type": "object",
                "properties": {
                    "include_markdown": {"type": "boolean", "default": True},
                    "include_synthetic_template": {"type": "boolean", "default": True},
                },
                "additionalProperties": False,
            },
            artifact_roles=[
                "test_ir",
                "target_bindings",
                "documentation",
                "producer_manifest",
                "result_template",
                "validation_report",
            ],
            tool_requirements={"python": ">=3.12"},
            portability=PluginPortability.PORTABLE,
            enabled=True,
        )

    def validate(self, request: GenerationRequest) -> list[dict[str, Any]]:
        """Preflight capability and semantic checks."""
        diagnostics: list[dict[str, Any]] = []
        bnd_map = {b.id: b for b in request.target_binding_sets}
        obj_ids = {o.id for o in request.coverage_objectives}

        for recipe in request.recipes:
            bnd_set = bnd_map.get(recipe.target_binding_set_id) if recipe.target_binding_set_id else None
            recipe_diags = self.validator.validate_recipe(recipe, bnd_set, obj_ids)
            diagnostics.extend(recipe_diags)

        return diagnostics

    def lower(self, request: GenerationRequest) -> dict[str, Any]:
        """Prepare lowered realization plan and trace maps."""
        trace_map: list[dict[str, Any]] = []
        realization_states: dict[str, str] = {}

        for recipe in request.recipes:
            realization_states[recipe.id] = "generated"
            if recipe.test_ir:
                for chk in recipe.test_ir.checks:
                    trace_map.append({
                        "recipe_id": recipe.id,
                        "check_id": chk.get("check_id"),
                        "objective_id": chk.get("objective_id"),
                        "intent_ids": recipe.intent_ids,
                    })

        return {
            "trace_map": trace_map,
            "realization_states": realization_states,
        }

    def generate(
        self,
        request: GenerationRequest,
        lowered_plan: dict[str, Any],
        writer: OutputWriter,
    ) -> GenerationResult:
        """Produce deterministic bundle files."""
        # 1. Canonical test-ir.json
        recipes_data = [r.model_dump() for r in sorted(request.recipes, key=lambda x: x.id)]
        ir_json_bytes = canonical_json({
            "schema_version": SCHEMA_VERSION_TEST_IR,
            "checkpoint_id": request.checkpoint_id,
            "recipes": recipes_data,
        })
        writer.write_artifact("test-ir.json", ir_json_bytes, role="test_ir", media_type="application/json")

        # 2. Canonical target-bindings.json
        bnd_data = [b.model_dump() for b in sorted(request.target_binding_sets, key=lambda x: x.id)]
        bnd_json_bytes = canonical_json({
            "target_binding_sets": bnd_data,
        })
        writer.write_artifact("target-bindings.json", bnd_json_bytes, role="target_bindings", media_type="application/json")

        # 3. Human-readable recipe.md
        md_lines = [
            f"# Verification Implementation Bundle: {request.checkpoint_id}",
            "",
            f"**Backend**: `{PLUGIN_ID}` (v{PLUGIN_VERSION})  ",
            "**Notice**: Reference bundle — contains no executable tests or simulation runner.  ",
            "",
            "## Recipes",
            "",
        ]
        for r in sorted(request.recipes, key=lambda x: x.id):
            md_lines.extend([
                f"### Recipe `{r.key}`: {r.title}",
                f"- **Kind**: {r.kind.value}",
                f"- **Intents**: {', '.join(r.intent_ids)}",
                f"- **Objectives**: {', '.join(r.objective_ids)}",
                f"- **Oracle Description**: {r.oracle_provenance.description or 'None provided'}",
                "",
            ])
            if r.test_ir:
                md_lines.append("#### Sequence Overview")
                if r.test_ir.setup:
                    md_lines.append(f"- Setup steps: {len(r.test_ir.setup)}")
                if r.test_ir.body:
                    md_lines.append(f"- Body steps: {len(r.test_ir.body)}")
                if r.test_ir.teardown:
                    md_lines.append(f"- Teardown steps: {len(r.test_ir.teardown)}")
                if r.test_ir.checks:
                    md_lines.append(f"- Checks: {len(r.test_ir.checks)}")
                md_lines.append("")

        md_content = "\n".join(md_lines).encode("utf-8")
        writer.write_artifact("recipe.md", md_content, role="documentation", media_type="text/markdown")

        # 4. Producer Manifest
        observations: dict[str, ProducerObservation] = {}
        for r in request.recipes:
            for eb in r.evidence_bindings:
                obs_key = f"{r.key}.{eb.observation_key}"
                observations[obs_key] = ProducerObservation(
                    observation_key=obs_key,
                    objective_id=eb.objective_id,
                    objective_definition_hash=eb.definition_hash,
                    bin_ids=[eb.bin_id] if eb.bin_id else [],
                    scope="dut",
                    family=r.kind.value,
                    check_id=eb.check_id,
                    field_shape="scalar",
                )

        # Deterministic manifest digest calculation
        obs_payload = {k: v.model_dump() for k, v in sorted(observations.items())}
        raw_manifest_payload = {
            "checkpoint_id": request.checkpoint_id,
            "plugin_id": PLUGIN_ID,
            "plugin_version": PLUGIN_VERSION,
            "observations": obs_payload,
        }
        manifest_digest = sha256_digest(canonical_json(raw_manifest_payload))

        producer_manifest = ProducerManifest(
            producer_id=f"prod-{request.checkpoint_id[:8]}",
            manifest_digest=manifest_digest,
            implementation_checkpoint_id=request.checkpoint_id,
            recipe_ids=[r.id for r in request.recipes],
            coverage_checkpoint_id=request.recipes[0].coverage_checkpoint_id if request.recipes else "",
            source_hash=request.input_digest,
            coverage_hash=request.input_digest,
            target_hash=request.input_digest,
            backend_plugin_id=PLUGIN_ID,
            backend_plugin_version=PLUGIN_VERSION,
            tool_configuration=request.backend_configuration.config_json,
            observations=observations,
            created_at=datetime.now(timezone.utc).isoformat(),
        )

        manifest_bytes = canonical_json(producer_manifest.model_dump())
        writer.write_artifact(
            "producer-manifest.json",
            manifest_bytes,
            role="producer_manifest",
            media_type="application/json",
        )

        # 5. Synthetic Result Template
        synth_results = {
            "schema_version": "verification.results.v1",
            "synthetic": True,
            "producer_manifest_digest": manifest_digest,
            "note": "EXPLICITLY SYNTHETIC: Not valid for real production campaign closure.",
            "runs": [
                {
                    "run_id": "synth-run-001",
                    "status": "passed",
                    "observations": [
                        {
                            "observation_key": k,
                            "outcome": "passed",
                            "evaluated_count": 1,
                        }
                        for k in sorted(observations.keys())
                    ],
                }
            ],
        }
        writer.write_artifact(
            "synthetic-result-template.json",
            canonical_json(synth_results),
            role="result_template",
            media_type="application/json",
        )

        # 6. Validation Report
        val_report = {
            "valid": True,
            "diagnostics": [],
            "plugin_id": PLUGIN_ID,
            "generated_at": datetime.now(timezone.utc).isoformat(),
        }
        writer.write_artifact(
            "validation-report.json",
            canonical_json(val_report),
            role="validation_report",
            media_type="application/json",
        )

        return GenerationResult(
            input_digest=request.input_digest,
            plugin_id=PLUGIN_ID,
            plugin_version=PLUGIN_VERSION,
            plugin_digest=PACKAGE_DIGEST,
            artifacts=writer.get_descriptors(),
            producer_manifest=producer_manifest,
            source_map=lowered_plan["trace_map"],
            realization_states=lowered_plan["realization_states"],
            diagnostics=[],
        )
