# Spec Editor and Circuit Designer layout proposal

This proposal is separate from the focused release changes. It is not an implemented product UI. The saved source, manual authoring path, stable identities, and Spec/Circuit boundary remain the same in both options.

## Options

**Document with contextual Inspector (recommended).** Keep the explanation, Ports, SystemVerilog, and read-only interface preview in one document. Put settings and selected-object details in a right Inspector. The designer can compare content while editing; less horizontal space remains for the document.

**Document with editing sheets.** Use the full document width while reading. Open a temporary sheet for port batches, parameter edits, or selected Circuit details. This provides more reading space; the sheet covers some content during comparison.

Circuit Designer keeps the canvas as its main surface in both options. Hierarchy and selection stay explicit. Full instance and connection-table editing, transactional/structured ports, bus interfaces, port maps, channels, and protocol definitions remain later feature work.

## Mockups

The editable source and twelve image views (six scenes for each option) are in the ignored `artifacts/ui-redesign-proposal/` directory. Serve the built `dist/` directory to switch between the two layout options, themes, and scenes. The React source must be built; the source `index.html` is not a standalone browser file. Images use real acceptance names and interfaces; their statuses illustrate proposed UI states and are not execution evidence.

| Scene | Intended review |
| --- | --- |
| Readable Spec | Document hierarchy, embedded pin preview, concise status |
| Port entry | Defaults, duplication, paste review, atomic save |
| Implementation | Explicit verification, diagnostics, generation readiness |
| Connected Circuit | Two reusable 32-bit adders and the carry chain |
| Circuit selection | Widths, endpoints, contextual Inspector or sheet |
| Compact Spec | Reachable document content and authoring controls |

Keep existing theme tokens and native engineering names. Use Better Design principles for contextual actions, readable hierarchy, and errors beside the failed control. The references considered were Linear, Slate, and Interior; no replacement design system is required.

## Release contract

Manual UI saves use structural checks and can store unverified SV. Verify Component or Verify Design explicitly runs lint on the saved revision. A current passing result enables UI RTL generation. Generated-project lint and functional simulation remain separate evidence; simulation is unverified until executed.

Use the release evidence record under `/tmp/spec2gds-acceptance/release-ui-20261019/` for implemented behavior and test limits. Do not use these mockups as evidence of working controls.

## Image review links

| Scene | Contextual Inspector | Editing sheets |
| --- | --- | --- |
| Readable Spec | [Proposal 1](../../artifacts/ui-redesign-proposal/images/inspector-1.png) | [Proposal 1](../../artifacts/ui-redesign-proposal/images/sheet-1.png) |
| Port entry | [Proposal 2](../../artifacts/ui-redesign-proposal/images/inspector-2.png) | [Proposal 2](../../artifacts/ui-redesign-proposal/images/sheet-2.png) |
| Implementation | [Proposal 3](../../artifacts/ui-redesign-proposal/images/inspector-3.png) | [Proposal 3](../../artifacts/ui-redesign-proposal/images/sheet-3.png) |
| Connected Circuit | [Proposal 4](../../artifacts/ui-redesign-proposal/images/inspector-4.png) | [Proposal 4](../../artifacts/ui-redesign-proposal/images/sheet-4.png) |
| Circuit selection | [Proposal 5](../../artifacts/ui-redesign-proposal/images/inspector-5.png) | [Proposal 5](../../artifacts/ui-redesign-proposal/images/sheet-5.png) |
| Compact Spec | [Proposal 6](../../artifacts/ui-redesign-proposal/images/inspector-6.png) | [Proposal 6](../../artifacts/ui-redesign-proposal/images/sheet-6.png) |

Build the editable proposal with `node circuit-designer/node_modules/vite/bin/vite.js build artifacts/ui-redesign-proposal --outDir dist`. Serve `artifacts/ui-redesign-proposal/dist/` with a local static server. Both options remain proposals. The existing theme tokens remain the release design system.

The later catalog search ranked [Linear Quality](https://better-design.com/design-systems/linear-quality), [Cerulean](https://better-design.com/design-systems/cerulean), and [Linear](https://better-design.com/design-systems/linear). These are reference directions for restrained engineering tools. They do not replace the project themes. Cerulean emphasizes keyboard navigation; the Linear options emphasize compact hierarchy.
