"""Controlled test Activities, loaded only by the isolated browser registry."""
import os
import threading
from pathlib import Path

import pydantic

from spec2gds.spec.activities import ActivityContext, ActivityResult, ActivityScopes, activity


class Proof(pydantic.BaseModel):
    source_revision: str


@activity(activity_id="tests.proof", version="1.0.0", title="Source proof",
          description="Produce deterministic source evidence.",
          scopes=ActivityScopes(entity_kinds=("component", "design")), report_model=Proof,
          artifact_roles=("source-proof",))
def proof(context: ActivityContext) -> ActivityResult:
    revision = context.snapshot.source.source_revision_hash
    artifact = context.outputs.add_bytes(role="source-proof", name="source-proof.txt",
                                         media_type="text/plain", data=revision.encode(), source_entities=(context.target,))
    return ActivityResult(summary="Source proof completed.", report={"source_revision": revision}, artifacts=(artifact,))


@activity(activity_id="tests.failure", version="1.0.0", title="Controlled failure",
          description="Exercise truthful failure reporting.",
          scopes=ActivityScopes(entity_kinds=("component", "design")), report_model=Proof)
def failure(context: ActivityContext) -> ActivityResult:
    raise ValueError("Controlled Activity failure")


@activity(activity_id="tests.barrier", version="1.0.0", title="Controlled barrier",
          description="Wait for test release or cancellation.",
          scopes=ActivityScopes(entity_kinds=("component", "design")), report_model=Proof,
          artifact_roles=("source-proof",))
def barrier(context: ActivityContext) -> ActivityResult:
    directory = Path(os.environ["SPEC2GDS_E2E_BARRIER"])
    directory.mkdir(exist_ok=True)
    (directory / "started").write_text(context.snapshot.source.source_revision_hash)
    while not (directory / "release").exists():
        context.cancellation.raise_if_cancelled()
        threading.Event().wait(0.02)
    return proof.run(context)


def register(registry):
    for extension in (proof, failure, barrier):
        registry.register_activity(extension)
