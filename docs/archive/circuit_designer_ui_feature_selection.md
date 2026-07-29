# Historical: Circuit Designer UI Feature Selection

Use this document to select the next Circuit Designer implementation scope.
Selections are intentionally independent of IP-XACT persistence unless a feature
explicitly says otherwise. The standalone application should remain the primary
development and test environment.

## How to make selections

For every feature, place one `x` in one of these columns:

- **Now**: include in the next implementation milestone.
- **Next**: retain as the likely following milestone.
- **Later**: useful, but not currently scheduled.
- **No**: intentionally outside the product direction.

Example:

```text
| F01 | Manual orthogonal route editing | [x] | [ ] | [ ] | [ ] |
```

You can also add requirements or limits in the **Selection notes** section. The
feature IDs should be used in plans, issues, tests, and implementation reports.

## Recommended starter selection

The recommended first milestone is **F01-F10**. It addresses the current diagram
quality and basic interaction problems before adding higher-level IP-XACT and SoC
features.

If that milestone is too large, start with this minimum coherent slice:

- **F01** Manual orthogonal route editing
- **F02** Connectivity-preserving component drag
- **F03** Separate route optimization from automatic layout
- **F04** Port placement and ordering
- **F06** Compatible-target connection guidance
- **F08** Net highlighting and navigator

## Selection summary

Fill this in after making the detailed selections.

```text
Milestone name:
Selected feature IDs:
Primary acceptance goal:
Explicitly excluded behavior:
Target standalone examples or test circuits:
```

## A. Diagram and routing quality

| ID | Feature | Now | Next | Later | No | Effort | Dependencies |
|---|---|:---:|:---:|:---:|:---:|---|---|
| F01 | Manual orthogonal route editing | [ ] | [ ] | [ ] | [ ] | L | Existing route-tree contract |
| F02 | Connectivity-preserving component drag | [ ] | [ ] | [ ] | [ ] | M | F01 route editing model |
| F03 | Separate **Optimize Routes** from **Auto Layout** | [ ] | [ ] | [ ] | [ ] | M | Router service boundary |
| F04 | Port side, order, and position controls | [ ] | [ ] | [ ] | [ ] | M | Existing terminal placement command |
| F05 | Route constraints and locked segments | [ ] | [ ] | [ ] | [ ] | L | F01, persisted route metadata |
| F06 | Compatible-target connection guidance | [ ] | [ ] | [ ] | [ ] | M | Compatibility rules service |
| F07 | Clear crossing and junction semantics | [ ] | [ ] | [ ] | [ ] | S | Edge renderer changes |
| F08 | Net highlighting and endpoint navigator | [ ] | [ ] | [ ] | [ ] | M | Graph index already exists |
| F09 | Multi-select, align, distribute, and group move | [ ] | [ ] | [ ] | [ ] | M | Batch geometry commands |
| F10 | Explicit select/connect/route/pan interaction modes | [ ] | [ ] | [ ] | [ ] | M | Canvas interaction state |
| F11 | Keyboard nudging and **Align to Grid** repair | [ ] | [ ] | [ ] | [ ] | S | F09 recommended |
| F12 | Optional flow-oriented layout presets/regions | [ ] | [ ] | [ ] | [ ] | L | F03, placement constraints |

### F01 acceptance outline: manual route editing

- A horizontal segment can only be dragged vertically.
- A vertical segment can only be dragged horizontally.
- Users can add and remove orthogonal bends.
- Users can move explicit junctions without creating diagonal segments.
- Users can reset one branch or the entire net to its automatic route.
- Every committed route remains grid-aligned and renderer-independent.
- Undo/redo treats each completed gesture as one operation.

### F02 acceptance outline: connectivity-preserving drag

- Moving a component preserves every semantic connection.
- Only attached endpoint branches are rerouted where possible.
- Unaffected trunks, junctions, and manual routes remain stable.
- Component movement never pans or zooms the viewport automatically.
- The final component origin snaps to the visible grid.

### F03 acceptance outline: route versus layout

- **Optimize Selected Net** does not move any component or external port.
- **Optimize Connected Nets** affects only nets touching the selection.
- **Optimize All Routes** preserves all component geometry.
- **Auto Layout** is a separate, explicit operation.
- Pinned components are not moved by **Auto Layout**.

## B. Editing productivity

| ID | Feature | Now | Next | Later | No | Effort | Dependencies |
|---|---|:---:|:---:|:---:|:---:|---|---|
| F13 | Rectangle/lasso selection and selection filters | [ ] | [ ] | [ ] | [ ] | M | F09 |
| F14 | Hardware-style keyboard shortcuts | [ ] | [ ] | [ ] | [ ] | S | F10 |
| F15 | Context menus for blocks, ports, nets, and canvas | [ ] | [ ] | [ ] | [ ] | S | Command availability rules |
| F16 | Smart duplicate with legal auto-incremented names | [ ] | [ ] | [ ] | [ ] | S | Existing duplicate command |
| F17 | Draft/incomplete components for top-down design | [ ] | [ ] | [ ] | [ ] | M | Local contract extension |
| F18 | Replace component while preserving placement/connectivity | [ ] | [ ] | [ ] | [ ] | L | Compatibility and endpoint mapping |
| F19 | Search and go-to across blocks, ports, and nets | [ ] | [ ] | [ ] | [ ] | M | Search index |
| F20 | Minimap and saved viewport per design/hierarchy | [ ] | [ ] | [ ] | [ ] | S | View-only state |

## C. Validation and design comprehension

| ID | Feature | Now | Next | Later | No | Effort | Dependencies |
|---|---|:---:|:---:|:---:|:---:|---|---|
| F21 | Live, navigable Problems panel | [ ] | [ ] | [ ] | [ ] | L | Renderer-independent validation API |
| F22 | Direction, role, and terminal-kind connection checks | [ ] | [ ] | [ ] | [ ] | M | F21; useful for F06 |
| F23 | Multiple-driver, dangling-net, and self-connect checks | [ ] | [ ] | [ ] | [ ] | M | F21 |
| F24 | Width and bus/interface compatibility checks | [ ] | [ ] | [ ] | [ ] | L | Width/interface metadata |
| F25 | Intentional no-connect marker | [ ] | [ ] | [ ] | [ ] | M | Contract and persistence decision |
| F26 | Fan-in, fan-out, neighbour, and path tracing | [ ] | [ ] | [ ] | [ ] | M | F08 graph navigation |
| F27 | Semantic visibility presets and dim-unrelated mode | [ ] | [ ] | [ ] | [ ] | M | Net classification metadata |
| F28 | Connection table synchronized with canvas | [ ] | [ ] | [ ] | [ ] | M | Selection/search model |

### Suggested initial validation rules

If **F21-F23** are selected, the first rule set should be limited to facts the
current graph contract can prove:

- missing or unknown endpoint;
- net with fewer than two endpoints;
- terminal connected to itself;
- duplicate endpoint on one net;
- output-to-output or initiator-to-initiator connection;
- interface terminal connected to a physical-port terminal;
- terminal or node referencing a missing owner;
- duplicate element IDs or conflicting names;
- non-orthogonal persisted route;
- route endpoint not matching its terminal position.

Rules requiring complete width, clock, reset, or protocol semantics should not
guess when metadata is absent. They should report **unknown/not checked** rather
than a false pass or failure.

## D. Interfaces and abstraction

| ID | Feature | Now | Next | Later | No | Effort | Dependencies |
|---|---|:---:|:---:|:---:|:---:|---|---|
| F29 | First-class interface/bus bundles | [ ] | [ ] | [ ] | [ ] | L | Interface membership model |
| F30 | Expand/collapse interface into physical signals | [ ] | [ ] | [ ] | [ ] | L | F29, port-map data |
| F31 | Interface-only canvas view | [ ] | [ ] | [ ] | [ ] | M | F29 |
| F32 | Semantic styles for clock/reset/interrupt/control/data | [ ] | [ ] | [ ] | [ ] | M | Net classification metadata |
| F33 | Width, protocol, role, and clock metadata on canvas | [ ] | [ ] | [ ] | [ ] | M | Metadata availability |
| F34 | Named off-page connectors with peer reveal | [ ] | [ ] | [ ] | [ ] | M | F08 net navigator |
| F35 | Make selected port/interface external | [ ] | [ ] | [ ] | [ ] | M | Boundary mutation command |

## E. Library and hierarchy

| ID | Feature | Now | Next | Later | No | Effort | Dependencies |
|---|---|:---:|:---:|:---:|:---:|---|---|
| F36 | Searchable component/IP library | [ ] | [ ] | [ ] | [ ] | M | Component catalog query API |
| F37 | Component preview with ports and interfaces | [ ] | [ ] | [ ] | [ ] | M | F36 |
| F38 | Drag component from library to canvas | [ ] | [ ] | [ ] | [ ] | M | F36, placement mode |
| F39 | Hierarchy breadcrumb with back/up/top navigation | [ ] | [ ] | [ ] | [ ] | M | Existing hierarchy links |
| F40 | Recursive hierarchy tree and usage information | [ ] | [ ] | [ ] | [ ] | M | Catalog hierarchy projection |
| F41 | Create subsystem/hierarchy from selection | [ ] | [ ] | [ ] | [ ] | XL | F09, boundary commands, SpecIR support |
| F42 | Synchronize parent and child boundary interfaces | [ ] | [ ] | [ ] | [ ] | XL | F41, transactional persistence |

## F. SoC/IP-XACT companion views

| ID | Feature | Now | Next | Later | No | Effort | Dependencies |
|---|---|:---:|:---:|:---:|:---:|---|---|
| F43 | Clock-domain explorer and canvas overlay | [ ] | [ ] | [ ] | [ ] | L | Clock metadata projection |
| F44 | Reset-domain explorer and canvas overlay | [ ] | [ ] | [ ] | [ ] | L | Reset metadata projection |
| F45 | Address-map editor with conflict detection | [ ] | [ ] | [ ] | [ ] | XL | Memory-map SpecIR projection/mutations |
| F46 | Address-path cross-probing to the canvas | [ ] | [ ] | [ ] | [ ] | L | F45, graph path mapping |
| F47 | Read-only derived interconnect/adapter view | [ ] | [ ] | [ ] | [ ] | XL | Generated interconnect model |
| F48 | Board/platform-aware connection presets | [ ] | [ ] | [ ] | [ ] | XL | Board metadata outside current scope |

## G. Human/AI collaboration and review

| ID | Feature | Now | Next | Later | No | Effort | Dependencies |
|---|---|:---:|:---:|:---:|:---:|---|---|
| F49 | Visual preview/diff for agent command batches | [ ] | [ ] | [ ] | [ ] | L | Existing preview/proposal contract |
| F50 | Human/agent edit-lease status and read-only UX | [ ] | [ ] | [ ] | [ ] | S | Existing lease API |
| F51 | Human-readable transaction history | [ ] | [ ] | [ ] | [ ] | M | Command summarizer/history extension |
| F52 | Accept/reject/revert agent changes from canvas | [ ] | [ ] | [ ] | [ ] | L | F49, proposal API |
| F53 | Comments and TODO markers attached to design objects | [ ] | [ ] | [ ] | [ ] | M | Annotation sidecar/commands |
| F54 | Export clean SVG/PNG for architecture specifications | [ ] | [ ] | [ ] | [ ] | M | Export renderer and font policy |

## Effort legend

These are relative estimates for planning, not calendar commitments.

| Size | Meaning |
|---|---|
| S | Local UI change or small use of an existing command |
| M | One cross-package feature with focused model/UI/test changes |
| L | New shared service or contract plus substantial interaction work |
| XL | Multi-layer feature requiring new source semantics or major workflows |

## Selection notes

Add constraints, behavior decisions, or acceptance examples here.

```text
-
-
-
```

## Implementation principles that apply to every selection

1. The standalone application remains usable without Python, FastAPI, SpecIR,
   IP-XACT, or the spec editor.
2. React components do not contain IP-XACT-specific semantics.
3. Human and agent mutations use the same typed command API.
4. Semantic connectivity and visual route geometry remain separate.
5. Deterministic grid placement is separate from the electrical router, which
   owns final route quality and persisted manual routes.
6. Every mutation is revision guarded, previewable where appropriate, atomic,
   undoable, and validated.
7. Automatic operations preserve pinned or manually constrained content.
8. Missing source metadata produces an explicit unsupported/unknown state; it
   must not be silently invented.
9. Features are verified first with standalone examples, unit tests, and browser
   interaction tests before enabling them through the SpecIR adapter.

## Features intentionally outside the current product boundary

Unless explicitly reconsidered, do not select or infer work for:

- PCB placement or copper routing;
- footprints and bill-of-material management;
- electrical simulation;
- synthesis, timing closure, or physical implementation;
- full IEEE 1685 coverage beyond the spec2gds profile;
- protocol-specific RTL interconnect generation;
- simultaneous human and agent mutation without an exclusive edit lease.

## Research references

- [Kactus2 repository and product scope](https://github.com/kactus2/kactus2dev)
- [Kactus2 hardware design editor](https://github.com/kactus2/kactus2dev/blob/main/Help/hwdesign/hwdesign.html)
- [Kactus2 toolbars and views](https://github.com/kactus2/kactus2dev/blob/main/Help/general/toolbarsAndViews.html)
- [Kactus2 memory designer](https://github.com/kactus2/kactus2dev/blob/main/Help/memoryDesign/memoryDesign.html)
- [KiCad Schematic Editor](https://docs.kicad.org/master/en/eeschema/eeschema.html)
- [AMD Vivado IP Integrator block designs](https://docs.amd.com/r/en-US/ug994-vivado-ip-subsystems/Block-Designs)
- [Vivado connection assistance](https://docs.amd.com/r/2024.1-English/ug994-vivado-ip-subsystems/Using-the-Designer-Assistance-Feature)
- [Vivado hierarchy creation](https://docs.amd.com/r/2023.1-English/ug994-vivado-ip-subsystems/Creating-Hierarchies)
- [Intel Platform Designer System View](https://www.intel.com/content/www/us/en/programmable/quartushelp/20.1/mapIdTopics/qoz1534468463800.htm)
- [Intel Platform Designer Address Map](https://www.intel.com/content/www/us/en/programmable/quartushelp/18.0/system/qsys/qsys_tab_add_map.htm)
