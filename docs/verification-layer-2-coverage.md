# Layer 2: Coverage and Evidence

Layer 2 maps reviewed intents to objectives and evaluates explicitly imported
evidence. It does not execute DUT tests. Its schemas are in `domain/objectives.py`,
`domain/policies.py` and `domain/evidence.py`; computation belongs to
`domain/coverage_evaluator.py` and `application/coverage_service.py`.

## Objectives and policies

The model declares scenario, functional, correctness, property, structural and
mutation families. An objective links intent IDs, scope, family, acceptance data,
dimensions and explicit bins. Bins have required hits or a justified exclusion;
selected crosses are expanded through authoring commands. Family declarations
do not imply an installed native collector or executable backend.

An `IntentEvidencePolicy` contains alternative branches of objective IDs and
supplemental objectives. The coverage review checks mappings and requires a
checking family in each branch: scenario/functional hits alone do not demonstrate
correct behavior. Exclusions and waivers record deliberate omissions rather
than converting missing evidence to pass.

C-series checkpoints freeze coverage records with a selected upstream plan
checkpoint. Later draft changes do not rewrite the frozen objective definitions.

## Profiles, campaigns and imports

Evaluation profiles identify the DUT/configuration being assessed. Campaigns
pin a coverage checkpoint and profile selection, include/exclude runs, retain
failure dispositions and waivers, and can freeze. Fixture and verification
campaigns have different evidence meaning.

Stage normalized `verification.results.v1` payloads using
`/plans/{id}/result-imports`, inspect the response, then commit the staging ID.
Runs and observations retain provenance and replay identity. A duplicate import
must not fabricate additional observations. The service exposes matrices, gaps,
trace views and frozen evidence reports through its versioned API.

The bundled reference backend supplies synthetic fixture result templates.
No installed simulator, formal, structural or mutation collector is implied.
External results must carry an approved producer mapping and objective identity;
plain test-name similarity is not adequate provenance.

## Status interpretation

The evaluator uses precedence `fail > blocked > satisfied > waived > open >
not_evaluated`. A later passing retry does not erase an included failing run.
An explicit invalid-run or superseded-after-fix disposition is needed to remove
that failure from eligible evidence. Waivers cannot hide unresolved failures.

Objective evaluation is family-specific: explicit bin hits, evaluated/failed
checks, property outcomes and metric denominators have distinct meanings.
A zero/unknown denominator must not be interpreted as full coverage. Matrices
and gaps are projections of selected baselines, profiles and campaign evidence;
they are not independently editable truth. Gap notes cannot substitute for
changing the underlying records or evidence.

The implemented evaluator contains limited family handling and direct records;
it is not the complete formal-quality/assumption, million-observation or native
adapter design from the earlier plan. [The backlog](verification-planner-backlog.md)
preserves those requirements without claiming they already pass.

## Verification

Run `uv run python -m pytest testplan-service/tests/test_layer2_acceptance.py -q`.
These fixtures cover family records, policies, imports, campaigns, status
precedence, gaps and reports. They do not certify a real DUT, simulator result
adapter or exhaustive formal semantics.
