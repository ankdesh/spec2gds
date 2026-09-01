# Circuit Designer feature gaps compared with Chipmind

This is a product inventory, not a commitment to reproduce Chipmind. It was
reviewed on 1 September 2026 against Chipmind's official
[product page](https://www.chipmind.ai/product),
[technology page](https://www.chipmind.ai/technology), and
[RTL Canvas announcement](https://www.chipmind.ai/post/chipmind-introduces-rtl-canvas-generative-ui-for-chip-design-agents).
Marketing claims are recorded as reported capabilities; they were not
independently benchmarked.

## Current overlap

Circuit Designer already provides a direct-manipulation block-and-net canvas,
hierarchical component resolution, explicit edit staging through leases and
drafts, source-bound commits, review-gated proposals, timing stages and clock
domains, deterministic layout/routing, and matching JSON/SVG/PNG exports.
Those foundations overlap with Chipmind's visual architecture navigation and
human-reviewed staging story, but not its broader autonomous agent platform.

## Missing or partial capabilities

| Potential capability | Current state | Suggested priority | Product boundary |
| --- | --- | --- | --- |
| Structural visual diff with added/removed/changed ghosting | Proposal review reports counts; it does not render a before/after topology overlay | P0 | Circuit Designer |
| Smooth hierarchy drill-down with breadcrumbs and lazy subgraph loading | Child designs can be resolved, but navigation is not a continuous canvas workflow | P0 | Circuit Designer |
| Bus-aware topology and cross-hierarchy signal moves | Current source profile is intentionally wire-only | P0 | Circuit model + source adapters |
| RTL-to-canvas and canvas-to-RTL round trip | `.spec` topology round trips; HDL structure does not | P1 | Activities/source integration |
| Context-sensitive FSM, waveform, and register-map views | Only topology and timing-stage overlays exist | P1 | Pluggable visualization surfaces |
| Constraint validation while staging architecture changes | Schema/connectivity checks exist; simulation, synthesis, CDC, and protocol evidence do not | P1 | Tool runner + evidence contract |
| In-canvas natural-language intent and agent plan | Assistant opens as an optional host tool and authors bounded proposals | P1 | Optional tool contribution |
| Full design/repository index with cross-file dependencies | Circuit documents and `.spec` entities are indexed only within their own models | P1 | Separate design-context service |
| EDA flow execution: lint, simulation, synthesis, P&R, regressions | Activities can generate/verify bounded artifacts; no general flow orchestrator | P1 | Separate execution service |
| Waveform ingestion and debug correlation | No waveform model or viewer | P2 | Visualization/tool plugin |
| VCS issues, PR/MR review, execution logs, and verification evidence | No native VCS workflow or task audit bundle | P2 | Host integration |
| Background autonomous workers and webhook/CI triggers | Assistant is interactive and activities use a local single worker | P2 | Automation platform, not canvas core |
| VS Code surface sharing the same session | Browser application only | P2 | Alternate host using app-react |
| MCP/agent protocol surface and multi-agent orchestration | No Circuit-specific MCP/ACP task interface | P2 | External agent gateway |
| Persistent team conventions and project learning | Preferences store input mappings only; no design-method memory | P3 | Governance-sensitive context service |
| On-prem/air-gapped deployment controls and ephemeral task isolation | Components run locally, but no formal deployment/isolation product contract | P3 | Operations/security |

## Recommended sequence

1. Build visual topology diffs and hierarchy breadcrumbs. Both improve human
   review without coupling the canvas to a particular AI system.
2. Extend the canonical model and adapters for buses and richer hierarchy
   before attempting general RTL round trips.
3. Define an evidence attachment contract for lint, simulation, CDC, waveform,
   and synthesis results; render evidence through contributed tools/views.
4. Keep autonomous execution, VCS, institutional memory, and deployment policy
   outside `circuit-core` and the reusable React shell.

The reusable adapter boundary implemented alongside this inventory is what
allows those capabilities to be added without making Circuit Designer depend
on Spec Editor or any single assistant.
