"""Definitions of episodes, scenes, narration scripts, and chapter markers."""

from dataclasses import asdict, dataclass, field


@dataclass
class Scene:
    """A discrete visual and narration scene within an episode."""

    scene_id: str
    episode_id: str
    title: str
    chapter_title: str
    narration: str
    caption: str
    app: str  # e.g. "spec_editor", "circuit_designer"
    action: dict = field(default_factory=dict)
    hold_duration: float = 4.0
    operations: list[str] = field(default_factory=list)


@dataclass
class Episode:
    """An independent video learning module in the spec2hw video series."""

    id: str
    title: str
    application: str
    summary: str
    target_duration: str
    scenes: list[Scene] = field(default_factory=list)
    operations: list[str] = field(default_factory=list)

    def to_dict(self) -> dict:
        return {
            "id": self.id,
            "title": self.title,
            "application": self.application,
            "summary": self.summary,
            "target_duration": self.target_duration,
            "operations": self.operations,
            "scenes": [asdict(s) for s in self.scenes],
        }


def get_episodes_catalog() -> dict[str, Episode]:
    """Returns the full episode catalog with detailed scenes for Phase 1 (Pilot, V00, V01)."""
    episodes: dict[str, Episode] = {}

    # =========================================================================
    # Pilot Episode: End-to-End Validation & Application Handoff
    # =========================================================================
    pilot_scenes = [
        Scene(
            scene_id="pilot_s01_intro",
            episode_id="pilot",
            title="Introduction & Component Definition",
            chapter_title="Spec Editor Setup",
            narration=(
                "Welcome to spec2hw. In this pilot episode, we explore how hardware specifications "
                "are authored in Spec Editor and verified with real tools. We begin by creating a new Spec "
                "and defining a registered adder component."
            ),
            caption=(
                "Welcome to spec2hw. In this pilot episode, we explore how hardware specifications "
                "are authored in Spec Editor and verified with real tools. We begin by creating a new Spec "
                "and defining a registered adder component."
            ),
            app="spec_editor",
            action={"type": "spec_setup", "component_name": "Registered Adder"},
            hold_duration=4.5,
            operations=["OP_SPEC_NEW", "OP_SPEC_COMPONENT_ADD", "OP_SPEC_PORT_ADD"],
        ),
        Scene(
            scene_id="pilot_s02_port_range",
            episode_id="pilot",
            title="Explicit Port Range Validation",
            chapter_title="Port Interface & Range Validation",
            narration=(
                "Interface ports require explicit Range configuration. Notice the real-time Range validation "
                "as we define input ports a and b with seven down to zero bit widths, along with clock and reset_n."
            ),
            caption=(
                "Interface ports require explicit Range configuration. Notice the real-time Range validation "
                "as we define input ports a and b with 7:0 bit widths, along with clk and reset_n."
            ),
            app="spec_editor",
            action={"type": "spec_ports", "ports": ["a", "b", "clk", "reset_n", "sum"]},
            hold_duration=5.0,
            operations=["OP_SPEC_PORT_RANGE"],
        ),
        Scene(
            scene_id="pilot_s03_lint",
            episode_id="pilot",
            title="SystemVerilog Section & Diagnostics Panel",
            chapter_title="SystemVerilog Lint & Diagnostics",
            narration=(
                "Next, we add the SystemVerilog implementation section. When we trigger Verify Component, "
                "the backend runs Verilator lint. Notice that invalid drafts are never silently lost; "
                "the Diagnostics panel pinpoints the exact line while preserving your source."
            ),
            caption=(
                "Next, we add the SystemVerilog implementation section. When we trigger Verify Component, "
                "the backend runs Verilator lint. Notice that invalid drafts are never silently lost; "
                "the Diagnostics panel pinpoints the exact line while preserving your source."
            ),
            app="spec_editor",
            action={"type": "spec_sv_lint", "code": "always_ff @(posedge clk) sum <= a + b;"},
            hold_duration=5.5,
            operations=[
                "OP_SPEC_SV_SECTION_ADD",
                "OP_SPEC_VERIFY_COMPONENT",
                "OP_SPEC_DIAGNOSTICS_VIEW",
            ],
        ),
        Scene(
            scene_id="pilot_s04_handoff",
            episode_id="pilot",
            title="Topology Preview & Circuit Designer Handoff",
            chapter_title="Circuit Designer Handoff",
            narration=(
                "Spec Editor embeds a compact interface preview of the component topology. "
                "From here, we launch Circuit Designer, begin an editing session, place our instance, "
                "and execute Save to Spec to persist the schematic back to the authoritative specification."
            ),
            caption=(
                "Spec Editor embeds a compact interface preview of the component topology. "
                "From here, we launch Circuit Designer, begin an editing session, place our instance, "
                "and execute Save to Spec to persist the schematic back to the authoritative specification."
            ),
            app="circuit_designer",
            action={"type": "circuit_handoff", "entity": "registered_adder"},
            hold_duration=6.0,
            operations=[
                "OP_SPEC_CIRCUIT_PREVIEW",
                "OP_CIRCUIT_LAUNCH",
                "OP_CIRCUIT_EDIT_BEGIN",
                "OP_CIRCUIT_ADD_INSTANCE",
                "OP_CIRCUIT_SAVE_TO_SPEC",
            ],
        ),
    ]

    episodes["pilot"] = Episode(
        id="pilot",
        title="Pilot: Validation & Application Handoff",
        application="spec_editor",
        summary="Demonstrates port validation, Diagnostics lint findings, and application handoff to Circuit Designer.",
        target_duration="2–3 min",
        scenes=pilot_scenes,
        operations=[
            "OP_SPEC_NEW",
            "OP_SPEC_COMPONENT_ADD",
            "OP_SPEC_PORT_ADD",
            "OP_SPEC_PORT_RANGE",
            "OP_SPEC_SV_SECTION_ADD",
            "OP_SPEC_VERIFY_COMPONENT",
            "OP_SPEC_DIAGNOSTICS_VIEW",
            "OP_SPEC_CIRCUIT_PREVIEW",
            "OP_CIRCUIT_LAUNCH",
            "OP_CIRCUIT_EDIT_BEGIN",
            "OP_CIRCUIT_ADD_INSTANCE",
            "OP_CIRCUIT_SAVE_TO_SPEC",
        ],
    )

    # =========================================================================
    # V00: System Tour
    # =========================================================================
    v00_scenes = [
        Scene(
            scene_id="v00_s01_intro",
            episode_id="V00",
            title="spec2hw Architecture & Ecosystem Overview",
            chapter_title="System Overview",
            narration=(
                "Welcome to spec2hw. This series provides an independent guide for digital hardware designers. "
                "The environment brings together six specialized applications: Spec Editor, Circuit Designer, "
                "AI Assistant, Verification Planner, Spec Catalog, and Activities."
            ),
            caption=(
                "Welcome to spec2hw. This series provides an independent guide for digital hardware designers. "
                "The environment brings together six specialized applications: Spec Editor, Circuit Designer, "
                "AI Assistant, Verification Planner, Spec Catalog, and Activities."
            ),
            app="spec_editor",
            action={"type": "overview"},
            hold_duration=5.0,
            operations=["OP_SPEC_NEW"],
        ),
        Scene(
            scene_id="v00_s02_spec_editor",
            episode_id="V00",
            title="Spec Editor: The Logical Document Authority",
            chapter_title="Spec Editor Authority",
            narration=(
                "Spec Editor serves as the single source of authority for your hardware specifications. "
                "Within a Spec file, you define components, configure interface ports with explicit ranges, "
                "and embed SystemVerilog sections verified with automated linting."
            ),
            caption=(
                "Spec Editor serves as the single source of authority for your hardware specifications. "
                "Within a .spec file, you define components, configure interface ports with explicit ranges, "
                "and embed SystemVerilog sections verified with automated linting."
            ),
            app="spec_editor",
            action={"type": "show_spec_editor"},
            hold_duration=5.5,
            operations=[
                "OP_SPEC_COMPONENT_ADD",
                "OP_SPEC_PORT_ADD",
                "OP_SPEC_SV_SECTION_ADD",
                "OP_SPEC_VERIFY_COMPONENT",
            ],
        ),
        Scene(
            scene_id="v00_s03_circuit_designer",
            episode_id="V00",
            title="Circuit Designer: Visual Topology & Save to Spec",
            chapter_title="Circuit Designer",
            narration=(
                "Circuit Designer provides interactive schematic authoring. You arrange instances, "
                "route net connections, inspect bit-width matching, and commit your schematic layout back "
                "to the Spec using the canonical Save to Spec action."
            ),
            caption=(
                "Circuit Designer provides interactive schematic authoring. You arrange instances, "
                "route net connections, inspect bit-width matching, and commit your schematic layout back "
                "to the Spec using the canonical Save to Spec action."
            ),
            app="circuit_designer",
            action={"type": "show_circuit_designer"},
            hold_duration=5.5,
            operations=[
                "OP_CIRCUIT_LAUNCH",
                "OP_CIRCUIT_EDIT_BEGIN",
                "OP_CIRCUIT_SAVE_TO_SPEC",
            ],
        ),
        Scene(
            scene_id="v00_s04_ai_assistant",
            episode_id="V00",
            title="AI Assistant: Human-in-the-Loop Co-Design",
            chapter_title="AI Assistant",
            narration=(
                "The AI Assistant operates bound directly to your Spec context. It assists with multi-turn "
                "hardware queries, proposes architectural revisions, and submits diffs that always require "
                "explicit designer review and approval before anything is saved."
            ),
            caption=(
                "The AI Assistant operates bound directly to your Spec context. It assists with multi-turn "
                "hardware queries, proposes architectural revisions, and submits diffs that always require "
                "explicit designer review and approval before anything is saved."
            ),
            app="ai_assistant",
            action={"type": "show_ai_assistant"},
            hold_duration=5.5,
            operations=["OP_AI_LAUNCH_BOUND", "OP_AI_CONVERSATION_TURN"],
        ),
        Scene(
            scene_id="v00_s05_verif_planner",
            episode_id="V00",
            title="Verification Planner: Contracts & Coverage",
            chapter_title="Verification Planner",
            narration=(
                "Verification Planner establishes verified hardware contracts. You import Spec snapshots, "
                "author functional intent, configure coverage policies, and bind simulation recipes "
                "to ensure your RTL meets every requirement."
            ),
            caption=(
                "Verification Planner establishes verified hardware contracts. You import Spec snapshots, "
                "author functional intent, configure coverage policies, and bind simulation recipes "
                "to ensure your RTL meets every requirement."
            ),
            app="verification_planner",
            action={"type": "show_verification_planner"},
            hold_duration=5.5,
            operations=["OP_VERIF_IMPORT_SNAPSHOT", "OP_VERIF_AUTHOR_INTENT"],
        ),
        Scene(
            scene_id="v00_s06_catalog_activities",
            episode_id="V00",
            title="Spec Catalog & Activities: Reusability and Generation",
            chapter_title="Catalog & Activities",
            narration=(
                "Finally, Spec Catalog enables browsing and importing proven IP blocks, while Activities "
                "orchestrate automated workflows such as rtl.generate to synthesize production-ready RTL archives."
            ),
            caption=(
                "Finally, Spec Catalog enables browsing and importing proven IP blocks, while Activities "
                "orchestrate automated workflows such as rtl.generate to synthesize production-ready RTL archives."
            ),
            app="spec_catalog",
            action={"type": "show_catalog_and_activities"},
            hold_duration=5.0,
            operations=["OP_CATALOG_BROWSE", "OP_ACTIVITY_RTL_GENERATE"],
        ),
    ]

    episodes["V00"] = Episode(
        id="V00",
        title="System Tour",
        application="spec_editor",
        summary="Roles of Spec Editor, Circuit Designer, AI Assistant, Verification Planner, Catalog, and Activities; handoffs and authority.",
        target_duration="5–7 min",
        scenes=v00_scenes,
        operations=[
            "OP_SPEC_NEW",
            "OP_SPEC_COMPONENT_ADD",
            "OP_SPEC_PORT_ADD",
            "OP_SPEC_SV_SECTION_ADD",
            "OP_SPEC_VERIFY_COMPONENT",
            "OP_CIRCUIT_LAUNCH",
            "OP_CIRCUIT_EDIT_BEGIN",
            "OP_CIRCUIT_SAVE_TO_SPEC",
            "OP_AI_LAUNCH_BOUND",
            "OP_AI_CONVERSATION_TURN",
            "OP_VERIF_IMPORT_SNAPSHOT",
            "OP_VERIF_AUTHOR_INTENT",
            "OP_CATALOG_BROWSE",
            "OP_ACTIVITY_RTL_GENERATE",
        ],
    )

    # =========================================================================
    # V01: Spec Files and Navigation
    # =========================================================================
    v01_scenes = [
        Scene(
            scene_id="v01_s01_new_spec",
            episode_id="V01",
            title="Creating and Opening Spec Packages",
            chapter_title="Document Management",
            narration=(
                "In this episode, we master Spec file management and navigation. A Spec is stored as a physical "
                ".spec ZIP archive containing document.json and IP-XACT metadata. We open and create specs "
                "using the File menu."
            ),
            caption=(
                "In this episode, we master Spec file management and navigation. A Spec is stored as a physical "
                ".spec ZIP archive containing document.json and IP-XACT metadata. We open and create specs "
                "using the File menu."
            ),
            app="spec_editor",
            action={"type": "file_management"},
            hold_duration=5.0,
            operations=["OP_SPEC_NEW", "OP_SPEC_OPEN"],
        ),
        Scene(
            scene_id="v01_s02_navigation",
            episode_id="V01",
            title="Navigating Contents and Hierarchy",
            chapter_title="Navigation & Sections",
            narration=(
                "Spec Editor organizes content into clear sections: Cover, Components, and Designs. "
                "You can use the Table of Contents sidebar to quickly jump between blocks and review "
                "the hardware definition structure."
            ),
            caption=(
                "Spec Editor organizes content into clear sections: Cover, Components, and Designs. "
                "You can use the Table of Contents sidebar to quickly jump between blocks and review "
                "the hardware definition structure."
            ),
            app="spec_editor",
            action={"type": "navigation_toc"},
            hold_duration=4.5,
            operations=[],
        ),
        Scene(
            scene_id="v01_s03_edit_component",
            episode_id="V01",
            title="Authoring Narrative and Title Changes",
            chapter_title="Renaming & Metadata",
            narration=(
                "Updating document titles and descriptions is done right on the cover page. "
                "When you modify the title to Released Spec 1.0 and commit, the change is saved "
                "durably into narrative.title and preserved upon reopen."
            ),
            caption=(
                "Updating document titles and descriptions is done right on the cover page. "
                "When you modify the title to 'Released Spec 1.0' and commit, the change is saved "
                "durably into narrative.title and preserved upon reopen."
            ),
            app="spec_editor",
            action={"type": "rename_spec", "title": "Released Spec 1.0"},
            hold_duration=5.0,
            operations=["OP_SPEC_RENAME"],
        ),
        Scene(
            scene_id="v01_s04_draft_cancel",
            episode_id="V01",
            title="Draft State and Discarding Edits",
            chapter_title="Draft States & Cancellation",
            narration=(
                "Spec Editor protects against accidental modifications. When making changes, a private draft "
                "is maintained. If you decide not to proceed, clicking Cancel reverts the interface "
                "to the last saved source revision without touching your archive on disk."
            ),
            caption=(
                "Spec Editor protects against accidental modifications. When making changes, a private draft "
                "is maintained. If you decide not to proceed, clicking Cancel reverts the interface "
                "to the last saved source revision without touching your archive on disk."
            ),
            app="spec_editor",
            action={"type": "cancel_draft"},
            hold_duration=5.0,
            operations=["OP_SPEC_DRAFT_CANCEL"],
        ),
        Scene(
            scene_id="v01_s05_theme",
            episode_id="V01",
            title="Theme Preferences and View Modes",
            chapter_title="Themes & Preferences",
            narration=(
                "You can customize your authoring experience with Clean and Obsidian themes. "
                "Theme settings are preserved in local preferences without modifying document source hashes."
            ),
            caption=(
                "You can customize your authoring experience with Clean and Obsidian themes. "
                "Theme settings are preserved in local preferences without modifying document source hashes."
            ),
            app="spec_editor",
            action={"type": "switch_theme"},
            hold_duration=4.0,
            operations=["OP_SPEC_THEME_SWITCH"],
        ),
    ]

    episodes["V01"] = Episode(
        id="V01",
        title="Spec Files and Navigation",
        application="spec_editor",
        summary="New, open, copy, rename, Contents, draft saves/cancel, refresh, and read-only notices.",
        target_duration="6–8 min",
        scenes=v01_scenes,
        operations=[
            "OP_SPEC_NEW",
            "OP_SPEC_OPEN",
            "OP_SPEC_RENAME",
            "OP_SPEC_DRAFT_CANCEL",
            "OP_SPEC_THEME_SWITCH",
        ],
    )

    # =========================================================================
    # V02: Components, Ports, and Parameters
    # =========================================================================
    v02_scenes = [
        Scene(
            scene_id="v02_s01_component",
            episode_id="V02",
            title="Defining Hardware Components",
            chapter_title="Component Creation",
            narration=(
                "In this episode, we explore hardware component authoring in Spec Editor. Hardware blocks start "
                "as logical component definitions. We open our specification and create a new Arithmetic Logic Unit component."
            ),
            caption=(
                "In this episode, we explore hardware component authoring in Spec Editor. Hardware blocks start "
                "as logical component definitions. We open our specification and create a new Arithmetic Logic Unit component."
            ),
            app="spec_editor",
            action={"type": "add_component", "name": "Arithmetic Logic Unit"},
            hold_duration=5.0,
            operations=["OP_SPEC_COMPONENT_ADD"],
        ),
        Scene(
            scene_id="v02_s02_ports",
            episode_id="V02",
            title="Configuring Vector and Scalar Ports",
            chapter_title="Explicit Port Ranges",
            narration=(
                "Every interface port requires explicit Range specifications. Using the Save and add another workflow, "
                "we define data_a and data_b with fifteen down to zero vector ranges, followed by a one-bit scalar clock port "
                "where the Range field is left blank."
            ),
            caption=(
                "Every interface port requires explicit Range specifications. Using the Save and add another workflow, "
                "we define data_a and data_b with 15:0 vector ranges, followed by a 1-bit scalar clk port where the Range field is left blank."
            ),
            app="spec_editor",
            action={"type": "add_ports"},
            hold_duration=6.0,
            operations=["OP_SPEC_PORT_ADD", "OP_SPEC_PORT_RANGE"],
        ),
        Scene(
            scene_id="v02_s03_duplicate_delete",
            episode_id="V02",
            title="Duplicating and Removing Ports",
            chapter_title="Port Duplication and Deletion",
            narration=(
                "When designing wide buses or similar interfaces, the Duplicate action creates an exact copy with "
                "an automatically incremented identifier. Unneeded ports can be safely deleted with immediate confirmation."
            ),
            caption=(
                "When designing wide buses or similar interfaces, the Duplicate action creates an exact copy with "
                "an automatically incremented identifier. Unneeded ports can be safely deleted with immediate confirmation."
            ),
            app="spec_editor",
            action={"type": "duplicate_and_delete_port"},
            hold_duration=5.5,
            operations=["OP_SPEC_PORT_DUPLICATE", "OP_SPEC_PORT_DELETE"],
        ),
        Scene(
            scene_id="v02_s04_parameters",
            episode_id="V02",
            title="Hardware Parameters and Default Values",
            chapter_title="Configuring Parameters",
            narration=(
                "Hardware parameters allow reusable, parameterized RTL designs. In the Parameters panel, we configure "
                "parameter WIDTH with type int unsigned and default expression 16, then commit our changes durably back to the Spec."
            ),
            caption=(
                "Hardware parameters allow reusable, parameterized RTL designs. In the Parameters panel, we configure "
                "parameter WIDTH with type int unsigned and default expression 16, then commit our changes durably back to the Spec."
            ),
            app="spec_editor",
            action={"type": "configure_parameters"},
            hold_duration=5.5,
            operations=[],
        ),
    ]
    episodes["V02"] = Episode(
        id="V02",
        title="Components, Ports, and Parameters",
        application="spec_editor",
        summary="Create/edit definitions; add, edit, duplicate, and delete ports; Save and add another; scalar and explicit Range inputs; parameter controls.",
        target_duration="6–8 min",
        scenes=v02_scenes,
        operations=[
            "OP_SPEC_COMPONENT_ADD",
            "OP_SPEC_PORT_ADD",
            "OP_SPEC_PORT_RANGE",
            "OP_SPEC_PORT_DUPLICATE",
            "OP_SPEC_PORT_DELETE",
        ],
    )

    # =========================================================================
    # V03: Sections, Behavior, and Previews
    # =========================================================================
    v03_scenes = [
        Scene(
            scene_id="v03_s01_narrative",
            episode_id="V03",
            title="Authoring Narrative & Descriptions",
            chapter_title="Narrative Specifications",
            narration=(
                "In Spec Editor, hardware specifications combine formal interfaces with structured narrative. "
                "We author detailed functional descriptions and architectural notes directly in the component's narrative sections."
            ),
            caption=(
                "In Spec Editor, hardware specifications combine formal interfaces with structured narrative. "
                "We author detailed functional descriptions and architectural notes directly in the component's narrative sections."
            ),
            app="spec_editor",
            action={"type": "edit_narrative"},
            hold_duration=5.0,
            operations=[],
        ),
        Scene(
            scene_id="v03_s02_sv_section",
            episode_id="V03",
            title="Embedding SystemVerilog Code",
            chapter_title="SystemVerilog Implementation",
            narration=(
                "Next, we add a SystemVerilog implementation section. The built-in code editor provides real-time "
                "syntax styling and allows engineers to embed synthesizable RTL directly within the component."
            ),
            caption=(
                "Next, we add a SystemVerilog implementation section. The built-in code editor provides real-time "
                "syntax styling and allows engineers to embed synthesizable RTL directly within the component."
            ),
            app="spec_editor",
            action={"type": "add_sv_section"},
            hold_duration=5.5,
            operations=["OP_SPEC_SV_SECTION_ADD"],
        ),
        Scene(
            scene_id="v03_s03_hardware_settings",
            episode_id="V03",
            title="Configuring Hardware Settings",
            chapter_title="Hardware Settings",
            narration=(
                "Under Hardware Settings, you can designate entry designs and configure internal design hierarchies. "
                "This links logical component definitions to their underlying schematic implementations."
            ),
            caption=(
                "Under Hardware Settings, you can designate entry designs and configure internal design hierarchies. "
                "This links logical component definitions to their underlying schematic implementations."
            ),
            app="spec_editor",
            action={"type": "inspect_hardware_settings"},
            hold_duration=5.0,
            operations=[],
        ),
        Scene(
            scene_id="v03_s04_preview",
            episode_id="V03",
            title="Compact Previews and SVG Download",
            chapter_title="Interface Previews & SVG Export",
            narration=(
                "Spec Editor automatically generates a compact interface topology preview. We can inspect pin placements, "
                "expand the preview to review port layout, and download the original vector SVG file."
            ),
            caption=(
                "Spec Editor automatically generates a compact interface topology preview. We can inspect pin placements, "
                "expand the preview to review port layout, and download the original vector SVG file."
            ),
            app="spec_editor",
            action={"type": "preview_and_download_svg"},
            hold_duration=5.5,
            operations=["OP_SPEC_CIRCUIT_PREVIEW"],
        ),
    ]
    episodes["V03"] = Episode(
        id="V03",
        title="Sections, Behavior, and Previews",
        application="spec_editor",
        summary="Narrative, SystemVerilog, hardware settings, compact interface previews, Expand, and original SVG download.",
        target_duration="5–7 min",
        scenes=v03_scenes,
        operations=["OP_SPEC_SV_SECTION_ADD", "OP_SPEC_CIRCUIT_PREVIEW"],
    )

    # =========================================================================
    # V04: Verification and Diagnostics
    # =========================================================================
    v04_scenes = [
        Scene(
            scene_id="v04_s01_verify",
            episode_id="V04",
            title="Automated Verilator Linting",
            chapter_title="Component Verification",
            narration=(
                "Verifying hardware blocks early prevents costly bugs. Clicking Verify Component triggers automated "
                "backend Verilator linting, validating syntax and interface connections with an immediate notification."
            ),
            caption=(
                "Verifying hardware blocks early prevents costly bugs. Clicking Verify Component triggers automated "
                "backend Verilator linting, validating syntax and interface connections with an immediate notification."
            ),
            app="spec_editor",
            action={"type": "verify_component_pass"},
            hold_duration=5.0,
            operations=["OP_SPEC_VERIFY_COMPONENT"],
        ),
        Scene(
            scene_id="v04_s02_diagnostics",
            episode_id="V04",
            title="Diagnostics Drawer & Draft Preservation",
            chapter_title="Diagnostics Drawer",
            narration=(
                "When a lint error occurs, Spec Editor never discards your draft. The notification alerts you, "
                "and opening the Diagnostics drawer shows exact line numbers, compiler details, and navigation links back to the error."
            ),
            caption=(
                "When a lint error occurs, Spec Editor never discards your draft. The notification alerts you, "
                "and opening the Diagnostics drawer shows exact line numbers, compiler details, and navigation links back to the error."
            ),
            app="spec_editor",
            action={"type": "verify_component_fail_and_diagnostics"},
            hold_duration=6.0,
            operations=["OP_SPEC_DIAGNOSTICS_VIEW"],
        ),
        Scene(
            scene_id="v04_s03_resolve",
            episode_id="V04",
            title="Fixing Errors and Verifying Clean State",
            chapter_title="Resolving Diagnostics",
            narration=(
                "We correct the SystemVerilog syntax in the code editor and re-run verification. The Diagnostics "
                "status updates to passed, and the verified receipt is persisted into the Spec archive."
            ),
            caption=(
                "We correct the SystemVerilog syntax in the code editor and re-run verification. The Diagnostics "
                "status updates to passed, and the verified receipt is persisted into the Spec archive."
            ),
            app="spec_editor",
            action={"type": "fix_and_reverify"},
            hold_duration=5.5,
            operations=["OP_SPEC_VERIFY_COMPONENT"],
        ),
    ]
    episodes["V04"] = Episode(
        id="V04",
        title="Verification and Diagnostics",
        application="spec_editor",
        summary="Verify, result notification, manual panel opening, failed/current/stale results, source navigation, and generated-file locations.",
        target_duration="5–7 min",
        scenes=v04_scenes,
        operations=["OP_SPEC_VERIFY_COMPONENT", "OP_SPEC_DIAGNOSTICS_VIEW"],
    )

    # =========================================================================
    # V05: Catalog Reuse and Publishing
    # =========================================================================
    v05_scenes = [
        Scene(
            scene_id="v05_s01_browse",
            episode_id="V05",
            title="Catalog Overview & IP Discovery",
            chapter_title="Browsing the IP Catalog",
            narration=(
                "The Spec Catalog provides a shared repository of pre-verified, reusable IP blocks. "
                "Designers can browse available components, arithmetic units, and communication interfaces in a unified catalog grid."
            ),
            caption=(
                "The Spec Catalog provides a shared repository of pre-verified, reusable IP blocks. "
                "Designers can browse available components, arithmetic units, and communication interfaces in a unified catalog grid."
            ),
            app="spec_catalog",
            action={"type": "browse_catalog"},
            hold_duration=5.0,
            operations=["OP_CATALOG_BROWSE"],
        ),
        Scene(
            scene_id="v05_s02_search",
            episode_id="V05",
            title="Finding Components by Name and Interface",
            chapter_title="Search and Filtering",
            narration=(
                "Instant search and keyword filtering make finding specific hardware blocks fast. "
                "Filtering for barrel shift immediately narrows the library down to verified barrel shifter definitions."
            ),
            caption=(
                "Instant search and keyword filtering make finding specific hardware blocks fast. "
                "Filtering for barrel shift immediately narrows the library down to verified barrel shifter definitions."
            ),
            app="spec_catalog",
            action={"type": "search_and_filter"},
            hold_duration=5.0,
            operations=["OP_CATALOG_SEARCH_FILTER"],
        ),
        Scene(
            scene_id="v05_s03_inspect",
            episode_id="V05",
            title="Auditing Provenance and Test Receipts",
            chapter_title="Version and Evidence Inspection",
            narration=(
                "Selecting an IP package opens the details drawer. Here we inspect version history, "
                "author provenance, verification receipts, and lint evidence before deciding to bring it into our design."
            ),
            caption=(
                "Selecting an IP package opens the details drawer. Here we inspect version history, "
                "author provenance, verification receipts, and lint evidence before deciding to bring it into our design."
            ),
            app="spec_catalog",
            action={"type": "inspect_version_evidence"},
            hold_duration=5.5,
            operations=["OP_CATALOG_INSPECT_VERSION"],
        ),
        Scene(
            scene_id="v05_s04_import",
            episode_id="V05",
            title="Collision-Free Component Import",
            chapter_title="Importing Renamed Copies",
            narration=(
                "From Spec Editor, we import the catalog component. When names conflict, the renamed copy option "
                "allows setting a custom local name, avoiding collisions while preserving the catalog origin tag."
            ),
            caption=(
                "From Spec Editor, we import the catalog component. When names conflict, the renamed copy option "
                "allows setting a custom local name, avoiding collisions while preserving the catalog origin tag."
            ),
            app="spec_editor",
            action={"type": "import_renamed_copy"},
            hold_duration=6.0,
            operations=["OP_CATALOG_IMPORT_RENAMED"],
        ),
        Scene(
            scene_id="v05_s05_publish",
            episode_id="V05",
            title="Publishing to Local Private Catalog",
            chapter_title="Publishing Teaching Packages",
            narration=(
                "Once a component is verified and complete, you can publish it as a teaching package into your "
                "local private catalog, making proven designs instantly accessible across your engineering team."
            ),
            caption=(
                "Once a component is verified and complete, you can publish it as a teaching package into your "
                "local private catalog, making proven designs instantly accessible across your engineering team."
            ),
            app="spec_catalog",
            action={"type": "publish_teaching_package"},
            hold_duration=5.5,
            operations=["OP_CATALOG_PUBLISH_LOCAL"],
        ),
    ]
    episodes["V05"] = Episode(
        id="V05",
        title="Catalog Reuse and Publishing",
        application="spec_catalog",
        summary="Browse, search, filter, inspect versions/evidence, import review, renamed-copy conflicts, local origin, publish teaching package.",
        target_duration="6–8 min",
        scenes=v05_scenes,
        operations=[
            "OP_CATALOG_BROWSE",
            "OP_CATALOG_SEARCH_FILTER",
            "OP_CATALOG_INSPECT_VERSION",
            "OP_CATALOG_IMPORT_RENAMED",
            "OP_CATALOG_PUBLISH_LOCAL",
        ],
    )

    # =========================================================================
    # V06: Design Composition
    # =========================================================================
    v06_scenes = [
        Scene(
            scene_id="v06_s01_compose",
            episode_id="V06",
            title="Creating Composite Designs",
            chapter_title="Hierarchical Designs",
            narration=(
                "Hardware systems are structured hierarchically. In Spec Editor, the Designs section lets you create "
                "composite schematics. We create a top-level design named soc_top to organize our system blocks."
            ),
            caption=(
                "Hardware systems are structured hierarchically. In Spec Editor, the Designs section lets you create "
                "composite schematics. We create a top-level design named soc_top to organize our system blocks."
            ),
            app="spec_editor",
            action={"type": "create_composite_design"},
            hold_duration=5.0,
            operations=["OP_SPEC_DESIGN_COMPOSE"],
        ),
        Scene(
            scene_id="v06_s02_instances",
            episode_id="V06",
            title="Instantiating Component Definitions",
            chapter_title="Instance References",
            narration=(
                "We add component instances to the design by referencing verified definitions. Each instance "
                "receives a unique reference name while reusing the ports and parameters defined in the component."
            ),
            caption=(
                "We add component instances to the design by referencing verified definitions. Each instance "
                "receives a unique reference name while reusing the ports and parameters defined in the component."
            ),
            app="spec_editor",
            action={"type": "add_instances"},
            hold_duration=5.5,
            operations=["OP_SPEC_DESIGN_COMPOSE"],
        ),
        Scene(
            scene_id="v06_s03_internal_entry",
            episode_id="V06",
            title="Boundary Interfaces & Internal Design Binding",
            chapter_title="Boundary Interfaces and Entry Design",
            narration=(
                "Under Hardware Settings, we designate soc_top as the Entry Design for synthesis, and link "
                "components to internal sub-designs, establishing clean hierarchical boundaries across the system."
            ),
            caption=(
                "Under Hardware Settings, we designate soc_top as the Entry Design for synthesis, and link "
                "components to internal sub-designs, establishing clean hierarchical boundaries across the system."
            ),
            app="spec_editor",
            action={"type": "configure_entry_and_internal_design"},
            hold_duration=5.5,
            operations=[],
        ),
    ]
    episodes["V06"] = Episode(
        id="V06",
        title="Design Composition",
        application="spec_editor",
        summary="Boundary interfaces, Internal Design, instance references, entry Design, and definition reuse.",
        target_duration="5–7 min",
        scenes=v06_scenes,
        operations=["OP_SPEC_DESIGN_COMPOSE"],
    )

    # =========================================================================
    # V07: Circuit Editing and Connections
    # =========================================================================
    v07_scenes = [
        Scene(
            scene_id="v07_s01_launch",
            episode_id="V07",
            title="Launching Circuit Designer and Acquiring Edit Lease",
            chapter_title="Editing Session & Lease",
            narration=(
                "Circuit Designer provides an interactive schematic canvas. When opening a design, the canvas "
                "begins in read-only mode. Selecting Begin Editing acquires an exclusive draft lease and unlocks editing tools."
            ),
            caption=(
                "Circuit Designer provides an interactive schematic canvas. When opening a design, the canvas "
                "begins in read-only mode. Selecting Begin Editing acquires an exclusive draft lease and unlocks editing tools."
            ),
            app="circuit_designer",
            action={"type": "launch_and_begin_edit"},
            hold_duration=5.5,
            operations=["OP_CIRCUIT_LAUNCH", "OP_CIRCUIT_EDIT_BEGIN"],
        ),
        Scene(
            scene_id="v07_s02_instance",
            episode_id="V07",
            title="Placing and Moving Components on Grid",
            chapter_title="Placing Instances",
            narration=(
                "We place component instances on the canvas using the Components menu. Selected instances "
                "snap cleanly to the circuit grid, and can be repositioned using direct mouse dragging or arrow keys."
            ),
            caption=(
                "We place component instances on the canvas using the Components menu. Selected instances "
                "snap cleanly to the circuit grid, and can be repositioned using direct mouse dragging or arrow keys."
            ),
            app="circuit_designer",
            action={"type": "add_and_move_instances"},
            hold_duration=5.5,
            operations=["OP_CIRCUIT_ADD_INSTANCE"],
        ),
        Scene(
            scene_id="v07_s03_connect",
            episode_id="V07",
            title="Connecting Ports & Wiring Terminals",
            chapter_title="Net Routing and Port Connections",
            narration=(
                "Connecting components is intuitive. Dragging from an output terminal to an input terminal "
                "creates an orthogonal net route. Signals with matching bit-widths establish immediate valid connections."
            ),
            caption=(
                "Connecting components is intuitive. Dragging from an output terminal to an input terminal "
                "creates an orthogonal net route. Signals with matching bit-widths establish immediate valid connections."
            ),
            app="circuit_designer",
            action={"type": "connect_pins"},
            hold_duration=5.5,
            operations=["OP_CIRCUIT_CONNECT_PORTS"],
        ),
        Scene(
            scene_id="v07_s04_mismatch",
            episode_id="V07",
            title="Width Mismatch Warnings and Undo",
            chapter_title="Port Width Mismatch Inspection",
            narration=(
                "If you attempt to connect pins with different bit-widths, Circuit Designer flags a clear "
                "width mismatch warning badge. Selecting Undo immediately rolls back the invalid connection."
            ),
            caption=(
                "If you attempt to connect pins with different bit-widths, Circuit Designer flags a clear "
                "width mismatch warning badge. Selecting Undo immediately rolls back the invalid connection."
            ),
            app="circuit_designer",
            action={"type": "width_mismatch_and_undo"},
            hold_duration=5.5,
            operations=["OP_CIRCUIT_WIDTH_MISMATCH"],
        ),
        Scene(
            scene_id="v07_s05_save_discard",
            episode_id="V07",
            title="Discarding Drafts vs Committing to Spec",
            chapter_title="Cancel vs Save to Spec",
            narration=(
                "Private drafts isolate experimental work. Selecting Cancel changes completely discards "
                "uncommitted edits. When your schematic is ready, Save to Spec commits the topology durably to the authoritative Spec."
            ),
            caption=(
                "Private drafts isolate experimental work. Selecting Cancel changes completely discards "
                "uncommitted edits. When your schematic is ready, Save to Spec commits the topology durably to the authoritative Spec."
            ),
            app="circuit_designer",
            action={"type": "cancel_and_save_to_spec"},
            hold_duration=6.0,
            operations=["OP_CIRCUIT_SAVE_TO_SPEC", "OP_CIRCUIT_DISCARD_DRAFT"],
        ),
    ]
    episodes["V07"] = Episode(
        id="V07",
        title="Circuit Editing and Connections",
        application="circuit_designer",
        summary="Selection, movement, boundary controls, connections, width errors, undo, cancel, Save to Spec, and persistence.",
        target_duration="6–8 min",
        scenes=v07_scenes,
        operations=[
            "OP_CIRCUIT_LAUNCH",
            "OP_CIRCUIT_EDIT_BEGIN",
            "OP_CIRCUIT_ADD_INSTANCE",
            "OP_CIRCUIT_CONNECT_PORTS",
            "OP_CIRCUIT_WIDTH_MISMATCH",
            "OP_CIRCUIT_SAVE_TO_SPEC",
            "OP_CIRCUIT_DISCARD_DRAFT",
        ],
    )

    # =========================================================================
    # V08: Circuit Layout and Routing
    # =========================================================================
    v08_scenes = [
        Scene(
            scene_id="v08_s01_canvas_nav",
            episode_id="V08",
            title="Pan, Zoom, and Fit to View",
            chapter_title="Canvas Navigation",
            narration=(
                "Navigating complex schematics is seamless. Dragging empty canvas space pans smoothly "
                "across the sheet. Zoom controls and Fit Circuit center the entire circuit topology instantly."
            ),
            caption=(
                "Navigating complex schematics is seamless. Dragging empty canvas space pans smoothly "
                "across the sheet. Zoom controls and Fit Circuit center the entire circuit topology instantly."
            ),
            app="circuit_designer",
            action={"type": "canvas_navigation"},
            hold_duration=5.5,
            operations=["OP_CIRCUIT_CANVAS_NAV"],
        ),
        Scene(
            scene_id="v08_s02_inspector",
            episode_id="V08",
            title="Inspecting Node and Terminal Properties",
            chapter_title="Property Inspector",
            narration=(
                "Opening the Property Inspector reveals fine-grained details about selected instances, "
                "terminal widths, coordinates, and timing stages, helping you verify schematic attributes at a glance."
            ),
            caption=(
                "Opening the Property Inspector reveals fine-grained details about selected instances, "
                "terminal widths, coordinates, and timing stages, helping you verify schematic attributes at a glance."
            ),
            app="circuit_designer",
            action={"type": "toggle_inspector"},
            hold_duration=5.0,
            operations=[],
        ),
        Scene(
            scene_id="v08_s03_routing_bends",
            episode_id="V08",
            title="Adjusting Wire Bends and Rerouting Nets",
            chapter_title="Orthogonal Bends and Rerouting",
            narration=(
                "Signal routes can be fine-tuned directly on canvas. Double-clicking a wire segment inserts "
                "custom orthogonal bends, allowing you to route cleanly around dense logic clusters."
            ),
            caption=(
                "Signal routes can be fine-tuned directly on canvas. Double-clicking a wire segment inserts "
                "custom orthogonal bends, allowing you to route cleanly around dense logic clusters."
            ),
            app="circuit_designer",
            action={"type": "adjust_bends"},
            hold_duration=5.5,
            operations=[],
        ),
        Scene(
            scene_id="v08_s04_route_lock",
            episode_id="V08",
            title="Route Locking and Automatic Layout Protection",
            chapter_title="Locking Routes",
            narration=(
                "To prevent auto-layout adjustments from displacing carefully planned wire paths, "
                "the Lock Selected Route control pins waypoints permanently, ensuring your custom routing remains preserved."
            ),
            caption=(
                "To prevent auto-layout adjustments from displacing carefully planned wire paths, "
                "the Lock Selected Route control pins waypoints permanently, ensuring your custom routing remains preserved."
            ),
            app="circuit_designer",
            action={"type": "lock_routes"},
            hold_duration=5.5,
            operations=["OP_CIRCUIT_ROUTE_LOCK"],
        ),
    ]
    episodes["V08"] = Episode(
        id="V08",
        title="Circuit Layout and Routing",
        application="circuit_designer",
        summary="Pan, zoom, fit, Inspector, arrangement, bends, rerouting, and route locks.",
        target_duration="5–7 min",
        scenes=v08_scenes,
        operations=["OP_CIRCUIT_CANVAS_NAV", "OP_CIRCUIT_ROUTE_LOCK"],
    )

    # =========================================================================
    # V09 through V18 Definitions
    # =========================================================================
    remaining_episodes = [
        (
            "V09",
            "Hierarchy and Timing",
            "circuit_designer",
            "Child Designs, navigation, cycle edges, clock domains, timing analysis, warnings, and timing annotations versus actual RTL.",
            ["OP_CIRCUIT_HIERARCHY_INSPECT"],
        ),
        (
            "V10",
            "Circuit Files and Preferences",
            "circuit_designer",
            "Independent files, source binding, JSON/SVG/PNG exports, themes, shortcuts, and shortcut conflicts.",
            ["OP_CIRCUIT_EXPORT_SCHEMATIC", "OP_CIRCUIT_THEME_SWITCH"],
        ),
        (
            "V11",
            "Assistant Conversations and Context",
            "ai_assistant",
            "Bound launches, target scope, supported conversation modes, context, history, and the effect of opening a different Spec.",
            ["OP_AI_LAUNCH_BOUND", "OP_AI_CONVERSATION_TURN"],
        ),
        (
            "V12",
            "Assistant Architecture and Spec Changes",
            "ai_assistant",
            "Architecture review/revise/approve, execution progress and supported controls, restricted content approval/rejection.",
            ["OP_AI_ARCH_REVIEW_APPROVE", "OP_AI_DIFF_REVIEW_APPROVE", "OP_AI_CHANGE_REJECTION"],
        ),
        (
            "V13",
            "Assistant Circuit Proposals",
            "ai_assistant",
            "Circuit binding, proposal review, acceptance into a private draft, inspection, save, cancel, and final persistence.",
            ["OP_AI_CIRCUIT_PROPOSAL"],
        ),
        (
            "V14",
            "Activities and RTL Outputs",
            "activities",
            "Availability, launch, progress, cancellation, failures, results, downloads, revision identity, and actual RTL project inspection/lint.",
            [
                "OP_ACTIVITY_RTL_GENERATE",
                "OP_ACTIVITY_MONITOR_PROGRESS",
                "OP_ACTIVITY_DOWNLOAD_ARCHIVE",
                "OP_ACTIVITY_CANCEL_JOB",
                "OP_ACTIVITY_VERILATOR_LINT",
            ],
        ),
        (
            "V15",
            "Verification Planner: Intent",
            "verification_planner",
            "Snapshot import, source audit, captured requirements, intent authoring, review blockers, and P1.",
            ["OP_VERIF_IMPORT_SNAPSHOT", "OP_VERIF_AUTHOR_INTENT"],
        ),
        (
            "V16",
            "Verification Planner: Coverage",
            "verification_planner",
            "Objectives, policies, C1, campaigns/profiles, staged result import, gaps, trace, and failure retention.",
            ["OP_VERIF_COVERAGE_POLICY", "OP_VERIF_CAMPAIGN_IMPORT"],
        ),
        (
            "V17",
            "Verification Planner: Implementation",
            "verification_planner",
            "Bindings, recipes, Test IR, backend configuration, I1, preflight, reference generation, and supported exports/imports.",
            ["OP_VERIF_IMPL_BINDING", "OP_VERIF_PREFLIGHT_RUN"],
        ),
        (
            "V18",
            "Optional SystemC and TLM",
            "activities",
            "Compatible input profiles, tool requirements, availability limits, both generation paths, output inspection, and actual build checks.",
            [],
        ),
    ]

    for ep_id, title, app, summary, ops in remaining_episodes:
        episodes[ep_id] = Episode(
            id=ep_id,
            title=title,
            application=app,
            summary=summary,
            target_duration="6–10 min",
            scenes=[],
            operations=ops,
        )

    return episodes
