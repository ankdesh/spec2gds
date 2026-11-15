"""Designer operation inventory and coverage calculator for spec2hw videos."""

from dataclasses import asdict, dataclass, field
from typing import Optional


@dataclass
class DesignerOperation:
    """Represents a discrete, supported designer operation across the spec2hw system."""

    id: str
    application: str
    name: str
    purpose: str
    prerequisites: list[str]
    expected_visible_result: str
    durable_result: str
    priority: str  # "essential", "high", "normal"
    episode_ids: list[str]
    scene_ids: list[str]
    evidence_refs: list[str]
    status: str = "planned"  # "planned", "recorded", "validated", "blocked", "excluded"
    exclusion_reason: Optional[str] = None


@dataclass
class ApplicationCoverage:
    """Coverage statistics for a single application."""

    application: str
    total_operations: int
    validated_operations: int
    planned_operations: int
    blocked_operations: int
    excluded_operations: int
    coverage_percent: float


@dataclass
class CoverageReport:
    """Overall coverage report across all applications."""

    total_operations: int
    active_operations: int
    validated_operations: int
    planned_operations: int
    blocked_operations: int
    excluded_operations: int
    overall_coverage_percent: float
    by_application: dict[str, ApplicationCoverage] = field(default_factory=dict)

    def to_dict(self) -> dict:
        return {
            "total_operations": self.total_operations,
            "active_operations": self.active_operations,
            "validated_operations": self.validated_operations,
            "planned_operations": self.planned_operations,
            "blocked_operations": self.blocked_operations,
            "excluded_operations": self.excluded_operations,
            "overall_coverage_percent": self.overall_coverage_percent,
            "by_application": {k: asdict(v) for k, v in self.by_application.items()},
        }

    def print_summary(self) -> None:
        print("\n=== Designer Operation Coverage Audit ===")
        print(f"Total defined operations: {self.total_operations}")
        print(f"Active (non-excluded):    {self.active_operations}")
        print(f"Validated demonstrations: {self.validated_operations}")
        print(f"Planned demonstrations:   {self.planned_operations}")
        print(f"Overall Coverage:         {self.overall_coverage_percent:.1f}%\n")
        print(f"{'Application':<24} {'Total':<8} {'Validated':<10} {'Coverage':<10}")
        print("-" * 54)
        for app, stats in self.by_application.items():
            print(
                f"{app:<24} {stats.total_operations:<8} {stats.validated_operations:<10} "
                f"{stats.coverage_percent:.1f}%"
            )
        print("-" * 54 + "\n")


def get_default_operations_registry() -> list[DesignerOperation]:
    """Returns the frozen canonical designer operations registry for spec2hw."""
    ops: list[DesignerOperation] = []

    # -------------------------------------------------------------
    # 1. Spec Editor Operations
    # -------------------------------------------------------------
    ops.extend(
        [
            DesignerOperation(
                id="OP_SPEC_NEW",
                application="spec_editor",
                name="Create New Spec",
                purpose="Initialize a blank specification package with canonical structure",
                prerequisites=["Spec service running"],
                expected_visible_result="Spec Editor opens blank Spec with editable title and sections",
                durable_result="Fresh .spec archive created with document/document.json",
                priority="essential",
                episode_ids=["pilot", "V00", "V01"],
                scene_ids=["pilot_s01_intro", "v00_s01_intro", "v01_s01_new_spec"],
                evidence_refs=["tests/ui-scenarios/e2e/spec.spec.ts:9"],
            ),
            DesignerOperation(
                id="OP_SPEC_OPEN",
                application="spec_editor",
                name="Open Existing Spec",
                purpose="Load an existing .spec bundle from disk into the editor",
                prerequisites=["Valid .spec file on disk"],
                expected_visible_result="Document title, components, and designs render in editor paper",
                durable_result="Editor session bound to target file path",
                priority="essential",
                episode_ids=["V01"],
                scene_ids=["v01_s01_new_spec"],
                evidence_refs=["tests/ui-scenarios/e2e/spec.spec.ts:20"],
            ),
            DesignerOperation(
                id="OP_SPEC_RENAME",
                application="spec_editor",
                name="Rename Spec Document",
                purpose="Update document title in narrative metadata",
                prerequisites=["Open Spec"],
                expected_visible_result="Cover page header updates to new title",
                durable_result="document.json narrative.title updated and persisted",
                priority="essential",
                episode_ids=["V01"],
                scene_ids=["v01_s03_edit_component"],
                evidence_refs=["tests/ui-scenarios/e2e/spec.spec.ts:13"],
            ),
            DesignerOperation(
                id="OP_SPEC_COMPONENT_ADD",
                application="spec_editor",
                name="Add Component Definition",
                purpose="Create a new logical hardware component definition",
                prerequisites=["Open Spec"],
                expected_visible_result="Component card appears in Components section",
                durable_result="Component added to document AST and disk archive",
                priority="essential",
                episode_ids=["pilot", "V00", "V02"],
                scene_ids=["pilot_s01_intro", "v00_s02_spec_editor", "v02_s01_component"],
                evidence_refs=["tests/ui-scenarios/e2e/spec.spec.ts:27"],
            ),
            DesignerOperation(
                id="OP_SPEC_PORT_ADD",
                application="spec_editor",
                name="Add Port to Component",
                purpose="Define input/output/inout interface port with width/type",
                prerequisites=["Component exists in Spec"],
                expected_visible_result="Port row displayed in component ports table",
                durable_result="Port entry persisted in component model",
                priority="essential",
                episode_ids=["pilot", "V00", "V02"],
                scene_ids=["pilot_s01_intro", "v00_s02_spec_editor", "v02_s02_ports"],
                evidence_refs=["tests/ui-scenarios/e2e/spec.spec.ts:35"],
            ),
            DesignerOperation(
                id="OP_SPEC_PORT_RANGE",
                application="spec_editor",
                name="Configure Explicit Port Range",
                purpose="Specify explicit MSB:LSB vector range or scalar format",
                prerequisites=["Port editor open"],
                expected_visible_result="Validation indicator reflects valid range (e.g. 7:0)",
                durable_result="Range bounds saved into port definition",
                priority="essential",
                episode_ids=["pilot", "V02"],
                scene_ids=["pilot_s02_port_range", "v02_s02_ports"],
                evidence_refs=["tests/ui-scenarios/e2e/spec.spec.ts:40"],
            ),
            DesignerOperation(
                id="OP_SPEC_PORT_DUPLICATE",
                application="spec_editor",
                name="Duplicate Port",
                purpose="Clone an existing port with automatic disambiguated ID",
                prerequisites=["Port exists in table"],
                expected_visible_result="New port row with incremented suffix appears",
                durable_result="Cloned port persisted in component",
                priority="normal",
                episode_ids=["V02"],
                scene_ids=["v02_s03_duplicate_delete"],
                evidence_refs=["tests/ui-scenarios/e2e/spec.spec.ts:111"],
            ),
            DesignerOperation(
                id="OP_SPEC_PORT_DELETE",
                application="spec_editor",
                name="Delete Port",
                purpose="Remove an obsolete interface port",
                prerequisites=["Port exists in table"],
                expected_visible_result="Port row removed from table",
                durable_result="Port removed from component definition",
                priority="normal",
                episode_ids=["V02"],
                scene_ids=["v02_s03_duplicate_delete"],
                evidence_refs=["tests/ui-scenarios/e2e/spec.spec.ts:118"],
            ),
            DesignerOperation(
                id="OP_SPEC_SV_SECTION_ADD",
                application="spec_editor",
                name="Add SystemVerilog Section",
                purpose="Embed SystemVerilog implementation code into component",
                prerequisites=["Component exists in Spec"],
                expected_visible_result="Code editor card appears with syntax highlighting",
                durable_result="RTL implementation section saved in archive",
                priority="essential",
                episode_ids=["pilot", "V00", "V03"],
                scene_ids=["pilot_s03_lint", "v00_s02_spec_editor", "v03_s02_sv_section"],
                evidence_refs=["tests/ui-scenarios/e2e/spec.spec.ts:47"],
            ),
            DesignerOperation(
                id="OP_SPEC_VERIFY_COMPONENT",
                application="spec_editor",
                name="Verify Component (Lint)",
                purpose="Run Verilator lint check on component SV implementation",
                prerequisites=["Component has SV section"],
                expected_visible_result="Toast notification shows 'Lint passed' or 'Lint failed'",
                durable_result="Verification status recorded in document cache",
                priority="essential",
                episode_ids=["pilot", "V00", "V04"],
                scene_ids=[
                    "pilot_s03_lint",
                    "v00_s02_spec_editor",
                    "v04_s01_verify",
                    "v04_s03_resolve",
                ],
                evidence_refs=["tests/ui-scenarios/e2e/spec.spec.ts:53"],
            ),
            DesignerOperation(
                id="OP_SPEC_DIAGNOSTICS_VIEW",
                application="spec_editor",
                name="Inspect Diagnostics Panel",
                purpose="Review detailed lint diagnostics and source line navigation",
                prerequisites=["Verification run performed"],
                expected_visible_result="Diagnostics panel displays error line, code, and remedy",
                durable_result="Preserves invalid draft without discarding source",
                priority="essential",
                episode_ids=["pilot", "V04"],
                scene_ids=["pilot_s03_lint", "v04_s02_diagnostics"],
                evidence_refs=["tests/ui-scenarios/e2e/spec.spec.ts:89"],
            ),
            DesignerOperation(
                id="OP_SPEC_THEME_SWITCH",
                application="spec_editor",
                name="Switch Editor Theme",
                purpose="Toggle between Clean and Obsidian themes",
                prerequisites=["Spec Editor open"],
                expected_visible_result="Editor background and typography switch immediately",
                durable_result="Theme preference saved in local preferences",
                priority="normal",
                episode_ids=["V01"],
                scene_ids=["v01_s05_theme"],
                evidence_refs=["tests/ui-scenarios/e2e/spec.spec.ts:60"],
            ),
            DesignerOperation(
                id="OP_SPEC_CIRCUIT_PREVIEW",
                application="spec_editor",
                name="Inspect Circuit Preview",
                purpose="View read-only topology thumbnail card in Spec",
                prerequisites=["Component or Design with topology"],
                expected_visible_result="Topology thumbnail card renders with port boundary pins",
                durable_result="SVG preview embedded in document presentation",
                priority="high",
                episode_ids=["pilot", "V03"],
                scene_ids=["pilot_s04_handoff", "v03_s04_preview"],
                evidence_refs=["tests/ui-scenarios/e2e/spec.spec.ts:56"],
            ),
            DesignerOperation(
                id="OP_SPEC_DESIGN_COMPOSE",
                application="spec_editor",
                name="Create Hierarchical Design",
                purpose="Instantiate components inside a composite Design",
                prerequisites=["Components defined in Spec"],
                expected_visible_result="Design section shows instance cards and net connections",
                durable_result="Design hierarchy written to IP-XACT / Spec structure",
                priority="high",
                episode_ids=["V06"],
                scene_ids=["v06_s01_compose", "v06_s02_instances"],
                evidence_refs=["tests/ui-scenarios/e2e/spec.spec.ts:302"],
            ),
            DesignerOperation(
                id="OP_SPEC_DRAFT_CANCEL",
                application="spec_editor",
                name="Cancel Unsaved Draft",
                purpose="Discard in-progress edits and revert to last saved state",
                prerequisites=["Unsaved changes in active draft"],
                expected_visible_result="Form resets to previous saved values without persisting",
                durable_result="No changes committed to .spec archive",
                priority="high",
                episode_ids=["V01"],
                scene_ids=["v01_s04_draft_cancel"],
                evidence_refs=["tests/ui-scenarios/e2e/spec.spec.ts:236"],
            ),
        ]
    )

    # -------------------------------------------------------------
    # 2. Circuit Designer Operations
    # -------------------------------------------------------------
    ops.extend(
        [
            DesignerOperation(
                id="OP_CIRCUIT_LAUNCH",
                application="circuit_designer",
                name="Launch Circuit Designer",
                purpose="Open Circuit Designer bound to target Design from Spec",
                prerequisites=["Design exists in Spec"],
                expected_visible_result="Schematic canvas loads with component blocks and pins",
                durable_result="Circuit session bound to source revision hash",
                priority="essential",
                episode_ids=["pilot", "V00", "V07"],
                scene_ids=["pilot_s04_handoff", "v00_s03_circuit_designer", "v07_s01_launch"],
                evidence_refs=["tests/ui-scenarios/e2e/circuit.spec.ts:20"],
            ),
            DesignerOperation(
                id="OP_CIRCUIT_EDIT_BEGIN",
                application="circuit_designer",
                name="Begin Editing Session",
                purpose="Acquire edit lock and initialize private draft",
                prerequisites=["Canvas in read-only view"],
                expected_visible_result="Toolbar unlocks, draft banner appears",
                durable_result="Private draft storage created",
                priority="essential",
                episode_ids=["pilot", "V00", "V07"],
                scene_ids=["pilot_s04_handoff", "v00_s03_circuit_designer", "v07_s01_launch"],
                evidence_refs=["tests/ui-scenarios/e2e/circuit.spec.ts:31"],
            ),
            DesignerOperation(
                id="OP_CIRCUIT_ADD_INSTANCE",
                application="circuit_designer",
                name="Add Component Instance",
                purpose="Place a new component instance block onto the schematic canvas",
                prerequisites=["Editing session active"],
                expected_visible_result="New node appears on canvas with input/output pins",
                durable_result="Instance added to private draft topology",
                priority="essential",
                episode_ids=["pilot", "V07"],
                scene_ids=["pilot_s04_handoff", "v07_s02_instance"],
                evidence_refs=["tests/ui-scenarios/e2e/circuit.spec.ts:12"],
            ),
            DesignerOperation(
                id="OP_CIRCUIT_CONNECT_PORTS",
                application="circuit_designer",
                name="Connect Instance Pins",
                purpose="Drag and connect wire net between matching port pins",
                prerequisites=["At least two compatible ports on canvas"],
                expected_visible_result="Orthogonal net wire connects source to destination pin",
                durable_result="Net interconnection stored in draft",
                priority="essential",
                episode_ids=["V07"],
                scene_ids=["v07_s03_connect"],
                evidence_refs=["tests/ui-scenarios/e2e/circuit.spec.ts:33"],
            ),
            DesignerOperation(
                id="OP_CIRCUIT_WIDTH_MISMATCH",
                application="circuit_designer",
                name="Inspect Port Width Mismatch",
                purpose="Observe visual warning badge when connecting mismatched bit widths",
                prerequisites=["Ports of differing widths connected"],
                expected_visible_result="Orange/red warning badge on net with mismatch tooltip",
                durable_result="Non-blocking warning flagged in circuit diagnostics",
                priority="high",
                episode_ids=["V07"],
                scene_ids=["v07_s04_mismatch"],
                evidence_refs=["docs/circuit-designer.md:45"],
            ),
            DesignerOperation(
                id="OP_CIRCUIT_SAVE_TO_SPEC",
                application="circuit_designer",
                name="Save to Spec",
                purpose="Commit schematic layout and connections back to Spec source",
                prerequisites=["Valid changes in private draft"],
                expected_visible_result="Notice banner displays 'Changes saved to the source'",
                durable_result="Spec archive updated with new revision hash",
                priority="essential",
                episode_ids=["pilot", "V00", "V07"],
                scene_ids=["pilot_s04_handoff", "v00_s03_circuit_designer", "v07_s05_save_discard"],
                evidence_refs=["tests/ui-scenarios/e2e/circuit.spec.ts:33"],
            ),
            DesignerOperation(
                id="OP_CIRCUIT_DISCARD_DRAFT",
                application="circuit_designer",
                name="Discard Draft",
                purpose="Cancel editing session and revert canvas to last saved Spec state",
                prerequisites=["Active editing session with uncommitted changes"],
                expected_visible_result="Canvas reloads original topology; draft discarded",
                durable_result="Draft files cleared, source revision intact",
                priority="high",
                episode_ids=["V07"],
                scene_ids=["v07_s05_save_discard"],
                evidence_refs=["tests/ui-scenarios/e2e/circuit.spec.ts:53"],
            ),
            DesignerOperation(
                id="OP_CIRCUIT_CANVAS_NAV",
                application="circuit_designer",
                name="Navigate Canvas (Pan / Zoom / Fit)",
                purpose="Inspect schematic layout at various zoom levels",
                prerequisites=["Circuit Designer open"],
                expected_visible_result="Canvas zooms smoothly, fit-to-view centers all nodes",
                durable_result="Viewport state retained in session",
                priority="normal",
                episode_ids=["V08"],
                scene_ids=["v08_s01_canvas_nav"],
                evidence_refs=["circuit-designer/README.md:30"],
            ),
            DesignerOperation(
                id="OP_CIRCUIT_ROUTE_LOCK",
                application="circuit_designer",
                name="Lock and Reroute Net",
                purpose="Pin custom wire bends to prevent automatic layout reshuffling",
                prerequisites=["Selected net wire"],
                expected_visible_result="Lock icon appears on route segments",
                durable_result="Route waypoints marked immutable in draft",
                priority="normal",
                episode_ids=["V08"],
                scene_ids=["v08_s04_route_lock"],
                evidence_refs=["docs/circuit-designer.md:88"],
            ),
            DesignerOperation(
                id="OP_CIRCUIT_EXPORT_SCHEMATIC",
                application="circuit_designer",
                name="Export Schematic (JSON / SVG / PNG)",
                purpose="Download circuit layout as standalone graphic or JSON file",
                prerequisites=["Circuit loaded on canvas"],
                expected_visible_result="File download dialog prompts with exported file",
                durable_result="Exported file saved to designer's computer",
                priority="high",
                episode_ids=["V10"],
                scene_ids=["v10_s01_export"],
                evidence_refs=["tests/ui-scenarios/e2e/circuit.spec.ts:111"],
            ),
            DesignerOperation(
                id="OP_CIRCUIT_HIERARCHY_INSPECT",
                application="circuit_designer",
                name="Inspect Child Design Hierarchy",
                purpose="Double click composite instance to traverse into child schematic",
                prerequisites=["Design with hierarchical sub-designs"],
                expected_visible_result="Breadcrumb navigation updates, child canvas renders",
                durable_result="Navigation history updated",
                priority="high",
                episode_ids=["V09"],
                scene_ids=["v09_s01_hierarchy"],
                evidence_refs=["docs/circuit-designer.md:120"],
            ),
            DesignerOperation(
                id="OP_CIRCUIT_THEME_SWITCH",
                application="circuit_designer",
                name="Switch Circuit Theme",
                purpose="Toggle dark/light schematic styling",
                prerequisites=["Circuit Designer open"],
                expected_visible_result="Schematic grid and node colors invert smoothly",
                durable_result="Saved to preferences.json",
                priority="normal",
                episode_ids=["V10"],
                scene_ids=["v10_s02_preferences"],
                evidence_refs=["tests/ui-scenarios/e2e/circuit.spec.ts:217"],
            ),
        ]
    )

    # -------------------------------------------------------------
    # 3. AI Assistant Operations
    # -------------------------------------------------------------
    ops.extend(
        [
            DesignerOperation(
                id="OP_AI_LAUNCH_BOUND",
                application="ai_assistant",
                name="Launch Assistant Bound to Spec",
                purpose="Open AI Assistant sidebar linked to current Spec document",
                prerequisites=["Open Spec in Spec Editor"],
                expected_visible_result="AI Assistant panel opens showing bound document title",
                durable_result="Assistant session initialized with document context",
                priority="essential",
                episode_ids=["V00", "V11"],
                scene_ids=["v00_s04_ai_assistant", "v11_s01_launch_bound"],
                evidence_refs=["tests/ui-scenarios/runner/run_scenario.ts:29"],
            ),
            DesignerOperation(
                id="OP_AI_CONVERSATION_TURN",
                application="ai_assistant",
                name="Perform Multi-turn Conversation",
                purpose="Ask Assistant questions regarding hardware specifications or RTL",
                prerequisites=["Assistant active"],
                expected_visible_result="Streaming response with markdown explanation and citations",
                durable_result="Conversation turn appended to persistent chat log",
                priority="essential",
                episode_ids=["V00", "V11"],
                scene_ids=["v00_s04_ai_assistant", "v11_s02_chat"],
                evidence_refs=["tests/ui-scenarios/runner/run_scenario.ts:31"],
            ),
            DesignerOperation(
                id="OP_AI_ARCH_REVIEW_APPROVE",
                application="ai_assistant",
                name="Review & Approve Architecture Plan",
                purpose="Inspect proposed structural plan and approve execution",
                prerequisites=["Assistant generated architecture proposal"],
                expected_visible_result="Interactive checklist and 'Approve Plan' action button",
                durable_result="Execution phase transitions from planned to executing",
                priority="essential",
                episode_ids=["V12"],
                scene_ids=["v12_s01_arch_review"],
                evidence_refs=["tests/ui-scenarios/runner/run_scenario.ts:36"],
            ),
            DesignerOperation(
                id="OP_AI_DIFF_REVIEW_APPROVE",
                application="ai_assistant",
                name="Review & Approve Spec Diffs",
                purpose="Inspect side-by-side AST / SystemVerilog diff before applying changes",
                prerequisites=["Assistant produced candidate changes"],
                expected_visible_result="Diff view shows added/removed ports or code lines",
                durable_result="Approved diff applied to Spec; receipt hash displayed",
                priority="essential",
                episode_ids=["V12"],
                scene_ids=["v12_s02_diff_review"],
                evidence_refs=["tests/ui-scenarios/runner/run_scenario.ts:37"],
            ),
            DesignerOperation(
                id="OP_AI_CIRCUIT_PROPOSAL",
                application="ai_assistant",
                name="Accept Circuit Topology Proposal",
                purpose="Review schematic wiring proposed by AI and stage into private draft",
                prerequisites=["Assistant generated circuit proposal"],
                expected_visible_result="Schematic preview shows proposed nodes and connections",
                durable_result="Staged into Circuit Designer draft for designer review",
                priority="high",
                episode_ids=["V13"],
                scene_ids=["v13_s01_circuit_proposal"],
                evidence_refs=["docs/ai-assistant-flows.md:60"],
            ),
            DesignerOperation(
                id="OP_AI_CHANGE_REJECTION",
                application="ai_assistant",
                name="Reject or Request Revision",
                purpose="Decline candidate changes and request refined hardware architecture",
                prerequisites=["Review state active"],
                expected_visible_result="Changes discarded; prompt field re-enabled for feedback",
                durable_result="No changes applied to Spec",
                priority="high",
                episode_ids=["V12"],
                scene_ids=["v12_s03_rejection"],
                evidence_refs=["docs/ai-assistant.md:95"],
            ),
        ]
    )

    # -------------------------------------------------------------
    # 4. Verification Planner Operations
    # -------------------------------------------------------------
    ops.extend(
        [
            DesignerOperation(
                id="OP_VERIF_IMPORT_SNAPSHOT",
                application="verification_planner",
                name="Import Spec Snapshot",
                purpose="Initialize Test Plan by importing verified Spec requirements",
                prerequisites=["Valid Spec package"],
                expected_visible_result="Verification Planner dashboard displays imported interfaces",
                durable_result="Audit record linking Test Plan to source revision hash",
                priority="essential",
                episode_ids=["V00", "V15"],
                scene_ids=["v00_s05_verif_planner", "v15_s01_import"],
                evidence_refs=["docs/verification-planner.md:20"],
            ),
            DesignerOperation(
                id="OP_VERIF_AUTHOR_INTENT",
                application="verification_planner",
                name="Author Verification Intent",
                purpose="Specify functional verification requirements and test scenarios",
                prerequisites=["Snapshot imported"],
                expected_visible_result="Intent tree table updates with requirement items",
                durable_result="Requirements persisted in verification database",
                priority="essential",
                episode_ids=["V00", "V15"],
                scene_ids=["v00_s05_verif_planner", "v15_s02_intent"],
                evidence_refs=["docs/verification-planner.md:40"],
            ),
            DesignerOperation(
                id="OP_VERIF_COVERAGE_POLICY",
                application="verification_planner",
                name="Configure Coverage Policies",
                purpose="Set minimum statement, branch, and functional coverpoint thresholds",
                prerequisites=["Intent defined"],
                expected_visible_result="Policy threshold gauges configure (e.g. 95% branch coverage)",
                durable_result="Coverage contract stored in Test Plan",
                priority="high",
                episode_ids=["V16"],
                scene_ids=["v16_s01_coverage"],
                evidence_refs=["docs/verification-planner.md:75"],
            ),
            DesignerOperation(
                id="OP_VERIF_CAMPAIGN_IMPORT",
                application="verification_planner",
                name="Import Simulation Results",
                purpose="Upload Verilator or simulator coverage trace logs into campaign",
                prerequisites=["Simulation artifacts available"],
                expected_visible_result="Coverage breakdown charts update with measured percentages",
                durable_result="Run metrics recorded against campaign ID",
                priority="high",
                episode_ids=["V16"],
                scene_ids=["v16_s02_campaign"],
                evidence_refs=["docs/verification-planner.md:95"],
            ),
            DesignerOperation(
                id="OP_VERIF_IMPL_BINDING",
                application="verification_planner",
                name="Configure Implementation Bindings",
                purpose="Bind Test IR recipes to concrete simulator backends (Verilator / SystemC)",
                prerequisites=["Test Plan ready for execution"],
                expected_visible_result="Backend recipe configuration panel validates simulator path",
                durable_result="Binding manifest saved",
                priority="normal",
                episode_ids=["V17"],
                scene_ids=["v17_s01_binding"],
                evidence_refs=["docs/verification-planner.md:120"],
            ),
            DesignerOperation(
                id="OP_VERIF_PREFLIGHT_RUN",
                application="verification_planner",
                name="Execute Verification Preflight",
                purpose="Validate simulation environment prerequisites prior to full suite execution",
                prerequisites=["Bindings configured"],
                expected_visible_result="Preflight checklist indicators display green checks",
                durable_result="Preflight validation record logged",
                priority="normal",
                episode_ids=["V17"],
                scene_ids=["v17_s02_preflight"],
                evidence_refs=["docs/verification-planner.md:145"],
            ),
        ]
    )

    # -------------------------------------------------------------
    # 5. Spec Catalog Operations
    # -------------------------------------------------------------
    ops.extend(
        [
            DesignerOperation(
                id="OP_CATALOG_BROWSE",
                application="spec_catalog",
                name="Browse Spec Catalog",
                purpose="View library of reusable IP components and golden reference designs",
                prerequisites=["Catalog service running"],
                expected_visible_result="Catalog card grid displays available IP packages",
                durable_result="Catalog items listed with version tags",
                priority="essential",
                episode_ids=["V00", "V05"],
                scene_ids=["v00_s06_catalog_activities", "v05_s01_browse"],
                evidence_refs=["spec_catalog_service/README.md:10"],
            ),
            DesignerOperation(
                id="OP_CATALOG_SEARCH_FILTER",
                application="spec_catalog",
                name="Search and Filter Packages",
                purpose="Query IP catalog by tags, component name, or bus interface",
                prerequisites=["Catalog open"],
                expected_visible_result="Filtered card list matches search query in real time",
                durable_result="Filter state reflected in URL parameters",
                priority="high",
                episode_ids=["V05"],
                scene_ids=["v05_s02_search"],
                evidence_refs=["spec_catalog_service/README.md:25"],
            ),
            DesignerOperation(
                id="OP_CATALOG_INSPECT_VERSION",
                application="spec_catalog",
                name="Inspect Version & Evidence",
                purpose="Review package verification receipts, lint status, and changelog",
                prerequisites=["Selected catalog package"],
                expected_visible_result="Package drawer shows provenance, author, and evidence",
                durable_result="Full package metadata displayed without downloading",
                priority="high",
                episode_ids=["V05"],
                scene_ids=["v05_s03_inspect"],
                evidence_refs=["spec_catalog_service/README.md:40"],
            ),
            DesignerOperation(
                id="OP_CATALOG_IMPORT_RENAMED",
                application="spec_catalog",
                name="Import Package as Renamed Copy",
                purpose="Pull IP component into active workspace resolving name collisions",
                prerequisites=["Active workspace open"],
                expected_visible_result="Component added to workspace under disambiguated name",
                durable_result="Package contents copied into local Spec",
                priority="essential",
                episode_ids=["V05"],
                scene_ids=["v05_s04_import"],
                evidence_refs=["tests/ui-scenarios/e2e/import_flow.ts:15"],
            ),
            DesignerOperation(
                id="OP_CATALOG_PUBLISH_LOCAL",
                application="spec_catalog",
                name="Publish Teaching Package to Private Catalog",
                purpose="Publish validated Spec into local private catalog repository",
                prerequisites=["Fully verified Spec bundle"],
                expected_visible_result="Publish dialog confirms package addition to local catalog",
                durable_result="Package archive indexed in catalog root",
                priority="normal",
                episode_ids=["V05"],
                scene_ids=["v05_s05_publish"],
                evidence_refs=["spec_catalog_service/README.md:60"],
            ),
        ]
    )

    # -------------------------------------------------------------
    # 6. Activities & RTL Operations
    # -------------------------------------------------------------
    ops.extend(
        [
            DesignerOperation(
                id="OP_ACTIVITY_RTL_GENERATE",
                application="activities",
                name="Launch rtl.generate Activity",
                purpose="Execute automated SystemVerilog synthesis/generation job",
                prerequisites=["Verified Component in Spec"],
                expected_visible_result="Activity progress bar tracks execution steps",
                durable_result="RTL project generated in private scratch directory",
                priority="essential",
                episode_ids=["V00", "V14"],
                scene_ids=["v00_s06_catalog_activities", "v14_s01_generate"],
                evidence_refs=["scripts/run_rtl_activity.py:10"],
            ),
            DesignerOperation(
                id="OP_ACTIVITY_MONITOR_PROGRESS",
                application="activities",
                name="Monitor Activity Progress & Logs",
                purpose="Inspect live stdout/stderr streams from running activity job",
                prerequisites=["Activity execution in progress"],
                expected_visible_result="Console log drawer scrolls with step progress",
                durable_result="Job logs persisted to events.jsonl",
                priority="high",
                episode_ids=["V14"],
                scene_ids=["v14_s02_progress"],
                evidence_refs=["scripts/run_rtl_activity.py:25"],
            ),
            DesignerOperation(
                id="OP_ACTIVITY_DOWNLOAD_ARCHIVE",
                application="activities",
                name="Download Generated RTL Archive",
                purpose="Download complete generated RTL ZIP package with Makefiles",
                prerequisites=["Activity completed successfully"],
                expected_visible_result="Browser download of rtl-generated.tar.gz / .zip starts",
                durable_result="Generated files exported outside scratch directory",
                priority="essential",
                episode_ids=["V14"],
                scene_ids=["v14_s03_download"],
                evidence_refs=["scripts/run_rtl_activity.py:45"],
            ),
            DesignerOperation(
                id="OP_ACTIVITY_CANCEL_JOB",
                application="activities",
                name="Cancel Running Activity",
                purpose="Abort an in-flight long-running simulation or synthesis job",
                prerequisites=["Activity job currently running"],
                expected_visible_result="Status updates to 'Cancelled'; process group killed",
                durable_result="Child processes terminated cleanly",
                priority="normal",
                episode_ids=["V14"],
                scene_ids=["v14_s04_cancel"],
                evidence_refs=["docs/activities.md:80"],
            ),
            DesignerOperation(
                id="OP_ACTIVITY_VERILATOR_LINT",
                application="activities",
                name="Execute Verilator Lint Activity",
                purpose="Perform deep multi-file RTL linting with Verilator toolchain",
                prerequisites=["Verilator installed locally"],
                expected_visible_result="Detailed terminal lint output displayed in results view",
                durable_result="Lint receipts logged with tool versions",
                priority="high",
                episode_ids=["V14"],
                scene_ids=["v14_s05_lint"],
                evidence_refs=["scripts/rtl_evaluation.py:20"],
            ),
        ]
    )

    return ops


def calculate_coverage(
    operations: list[DesignerOperation],
    validated_episode_ids: Optional[set[str]] = None,
) -> CoverageReport:
    """Calculates coverage metrics overall and per application."""
    if validated_episode_ids is None:
        validated_episode_ids = set()

    by_app_ops: dict[str, list[DesignerOperation]] = {}
    for op in operations:
        by_app_ops.setdefault(op.application, []).append(op)

    by_app_stats: dict[str, ApplicationCoverage] = {}
    total_val = 0
    total_plan = 0
    total_active = 0
    total_blocked = 0
    total_excluded = 0

    for app, app_ops in by_app_ops.items():
        app_total = len(app_ops)
        app_excluded = sum(1 for o in app_ops if o.status == "excluded")
        app_blocked = sum(1 for o in app_ops if o.status == "blocked")
        app_active = app_total - app_excluded

        # If operation belongs to any validated episode, consider it validated
        app_val = sum(
            1
            for o in app_ops
            if o.status == "validated" or (set(o.episode_ids) & validated_episode_ids)
        )
        app_plan = sum(1 for o in app_ops if o.status == "planned")

        cov_pct = (app_val / app_active * 100.0) if app_active > 0 else 0.0

        by_app_stats[app] = ApplicationCoverage(
            application=app,
            total_operations=app_total,
            validated_operations=app_val,
            planned_operations=app_plan,
            blocked_operations=app_blocked,
            excluded_operations=app_excluded,
            coverage_percent=cov_pct,
        )

        total_val += app_val
        total_plan += app_plan
        total_active += app_active
        total_blocked += app_blocked
        total_excluded += app_excluded

    overall_pct = (total_val / total_active * 100.0) if total_active > 0 else 0.0

    return CoverageReport(
        total_operations=len(operations),
        active_operations=total_active,
        validated_operations=total_val,
        planned_operations=total_plan,
        blocked_operations=total_blocked,
        excluded_operations=total_excluded,
        overall_coverage_percent=overall_pct,
        by_application=by_app_stats,
    )
