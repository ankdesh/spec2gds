# Spec Editor visual improvement plan

Prepared on 8 October 2026. Status: implemented. See the
[implementation and verification record](spec-editor-visual-implementation.md).

## Design direction

Retain the green accent and light appearance. Make Spec Editor a compact,
consistent engineering editor. Give the Spec content the strongest visual
position. Use the same typography, controls, and spacing in the document,
Activity, Diagnostics, menus, and dialogs.

This direction gives designers more readable content in each view. It reduces
the current printed-document appearance. It also adds some frontend work for
active navigation and narrow layouts. The seven accepted changes remain in
scope. Use the existing React and A2UI components; a new theme package is not
needed for this work.

## Rendered evidence

The review used the current frontend source through its development server and
a real, isolated Spec service. The copied sample contains two Components, one
Design, eight wire ports, two SystemVerilog sections, and a derived circuit
preview. No source edits or Activity launches were made.

| View | Evidence |
| --- | --- |
| Document, 1440 × 1000 | [Desktop overview](evidence/spec-editor-visual-review-2026-10-08/overview-1440.png) |
| Document, 1728 × 1000 | [Wide overview](evidence/spec-editor-visual-review-2026-10-08/overview-1728.png) |
| Document, 1024 × 1000 | [Intermediate width](evidence/spec-editor-visual-review-2026-10-08/overview-1024.png) |
| Document, 390 × 844 | [Narrow overview](evidence/spec-editor-visual-review-2026-10-08/overview-390.png) |
| Component and port table | [Desktop Component](evidence/spec-editor-visual-review-2026-10-08/component-1440.png), [narrow Component](evidence/spec-editor-visual-review-2026-10-08/component-390.png) |
| Port draft | [Desktop draft](evidence/spec-editor-visual-review-2026-10-08/port-draft-1440.png), [narrow draft](evidence/spec-editor-visual-review-2026-10-08/port-draft-390.png) |
| Supporting views | [Activity](evidence/spec-editor-visual-review-2026-10-08/activity-1440.png), [Diagnostics](evidence/spec-editor-visual-review-2026-10-08/diagnostics-1440.png), [File menu](evidence/spec-editor-visual-review-2026-10-08/file-menu-1440.png) |
| Complete document | [Full desktop render](evidence/spec-editor-visual-review-2026-10-08/document-full-1440.png) |

Confirmed observations:

- At 1440 px, the title is 72 px and the cover is about 304 px high, with
  86.4 px padding. At 1728 px, the title reaches 75.2 px.
- The desktop toolbar is 64 px high. The Contents list sticks at 24 px from
  the top, so its first entries pass under the toolbar during scrolling.
- The Contents links have hover and focus styles, but no current-Section
  state. Contents is hidden below 800 px with no replacement control.
- At 1024 px, the document reports a page width of 1141 px. Table and hidden
  label containment need investigation during implementation.
- At 390 px, the toolbar is about 186 px high. The permanent status message
  covers the AI Assistant control. Port headers and Edit labels break into
  several short lines, including single-character lines.
- Table bodies use about 12.6 px text; column headers use about 10.9 px.
  Row headings inherit uppercase styling: the stored port ID `a` appears as
  `A`. Displayed hardware IDs must retain their exact case.
- This browser renders the application text with Noto Sans and the title
  with Liberation Serif. The named Inter and serif families are not bundled.
- Activity has a full-width history panel above its page heading, including
  a browser-default button. Diagnostics uses the same oversized serif title.

The final capture has no browser console errors or uncaught page errors. The
sample contains saved unverified SystemVerilog results and references to
missing historical artifact sidecars. These are visible source diagnostics,
not failures introduced by this review. Mixed port families, long Specs, and
live source-change states still require checks during implementation.

## The seven changes

### 1. Compact document header and Sections

Replace the large cover with a document header. Place the Spec name, Edit name
control, and Component/Design counts together. Use a 32 px desktop title,
28 px narrow title, and 24–32 px desktop padding. Aim for a 112–144 px header
for this short sample; let long names increase its height naturally.

Use 24 px group headings and 20 px Component/Design headings. Keep empty
Overview and group Sections as compact heading rows with their Options
controls. Keep authored narrative content, links, tables, and Sections.
Move necessary type context beside or below the heading. Remove repeated
decorative captions above headings, such as “IP-XACT hierarchy”.

Completion check: the first desktop view shows the document header, group
headings, and useful Design content without the current large empty bands.
Long Spec names wrap without pushing controls out of view.

Keep the desktop toolbar in one row: application menus on the left, document
views in the middle, and Spec identity plus AI Assistant on the right. Below
620 px, place application menus behind a labelled Menu control and keep the
view controls in a second row. Aim for a 104–120 px narrow toolbar with usable
hit areas. Keep all existing menu commands available.

### 2. One typography system

Use one reliable system sans-serif stack across all Spec Editor views. Start
with `system-ui`; remove unavailable font names from the intended typography.
If Inter is selected later, bundle it and verify the actual rendered font.
Use monospace for hardware IDs, range expressions, revisions, and the
SystemVerilog section.

| Role | Target size | Treatment |
| --- | --- | --- |
| Spec title | 32 px desktop; 28 px narrow | Semibold |
| Section / Component or Design heading | 24 px / 20 px | Semibold |
| Narrative content | 16 px | Regular; 1.6 line height |
| Controls, navigation, table body | 14 px | Regular; medium for active items |
| Labels and supporting metadata | 13 px | Medium labels; regular metadata |
| SystemVerilog and compact IDs | 13–14 px | Monospace; retain exact case |

Completion check: one font family is actually rendered for headings and UI
text. Menu, table, and form text remains readable at 200% zoom.

### 3. Reliable Contents navigation

Keep a 224–240 px Contents column on desktop, with consistent nested
indentation. Add a current-Section background and `aria-current="location"`.
Track the visible Section as the designer scrolls. Retain native anchor links.

Set the sticky offset and anchor scroll margin from the actual toolbar height,
with a 16 px gap. Give long Contents lists their own vertical scroll area.
At narrow widths, provide a Contents disclosure in the document area. Selecting
a Section closes it and moves focus to the target heading. Support Escape,
keyboard use, and focus restoration.

Completion check: neither a selected heading nor the first Contents item is
covered by the toolbar. Navigation works at 390, 800, 1024, 1440, and 1728 px.

### 4. Consistent controls and draft actions

Use 6 px corners and 36 px control heights on desktop. Use at least 44 px
interactive hit areas on narrow screens and coarse-pointer devices. Keep
labels on one line; permit groups of controls to wrap as a group.

Use shared button treatments for primary, secondary, quiet, and destructive
actions. Apply them to Edit name, Options, port Edit, draft actions, menus,
dialogs, SystemVerilog controls, and supporting views. Keep status badges small
and distinct from action buttons. Use red for Delete and other destructive
actions.

Use **Save to Spec** as the primary action inside an active private draft, with
Cancel beside it. Keep its saving and validation states visible. Give
**AI Assistant** a secondary toolbar treatment. Keep read-only document views
free of a new global Save action; accepted edits already save through the
existing Spec service.

Completion check: peer controls have equal height. Focus rings remain visible.
Save errors retain the draft. Cancel restores focus to the originating control.

### 5. Clear status and notification placement

Replace the permanent floating status message with a compact area in normal
layout, attached to the active Spec. Show synchronization state and Assistant
approval mode with text. Keep these facts available at narrow widths.

Use an in-flow notice below the toolbar when a source update requires review,
a save fails, or another action is needed. Keep the existing recovery actions
and revision checks. Give independent messages separate places rather than
placing them at the same fixed coordinates. Use appropriate status/alert
announcements without repeatedly announcing an unchanged state.

Completion check: status and notices cover no toolbar control, heading, form,
or Diagnostics badge. An incoming source change preserves an active draft and
still requires the existing explicit review before a stale save can proceed.

### 6. Restrained surfaces, color, and spacing

Remove the cover gradient and large paper shadow. Use a near-neutral canvas,
white content, subtle borders, and one quiet elevation level for content.
Reserve stronger shadows for open menus and dialogs. Retain green for primary
actions and selection. Use distinct success, warning, error, and neutral
statuses, always with text or another cue.

Use spacing steps of 4, 8, 12, 16, 24, and 32 px, expressed through tokens in
rem. Keep small gaps inside related groups and larger gaps between Sections.
Retain the existing `--spec-*` token interface and scope new styling to Spec
Editor. Keep the Circuit Designer visual system and circuit preview semantics
separate.

Completion check: title, content, and the current action have clear priority.
Green text and borders do not make every secondary control equally prominent.
Text and control contrast pass the relevant accessibility checks.

### 7. Readable tables and narrow forms

Use 14 px table bodies and 13 px sentence-case column headings. Align row
content consistently, with about 12 px horizontal and 8–12 px vertical padding.
Use subtle horizontal separators; reduce the strong spreadsheet grid. Give
each hardware ID exact-case monospace styling. Give Edit a stable action
column; its label must not split into single-character lines.

Keep all six port-table columns. At constrained widths, allow horizontal
scroll within the table container instead of compressing each column. Keep
the action column reachable. Ensure hidden accessible labels do not extend
the page width. For a port draft, let the spanning editor fit the visible
container with a single-column form on narrow screens, even when read-only
rows need horizontal scrolling. All fields and actions must remain reachable.

Apply the same table rules to instance, connection, and parameter tables.
Preserve wire, transactional, and structured port definitions. Keep the circuit
preview derived and read-only; its underlying tables remain authoritative.

Completion check: the page has no horizontal overflow at tested widths.
Table scrolling works with keyboard and touch. IDs retain exact case, and
all fields, descriptions, and actions remain available.

## Implementation order

| Phase | Work | Exit condition |
| --- | --- | --- |
| A — Shared visual rules | Define typography, spacing, surface, color, and control tokens. Apply them to menus and dialogs. | The same components have the same appearance across views. |
| B — Document layout | Implement the compact header and Sections; fix sticky offsets; add current-Section navigation and narrow Contents. | The baseline Spec has a clear hierarchy at all reviewed widths. |
| C — Editing and status | Align draft forms and actions; replace floating status; fix table overflow, wrapping, and ID case. | Draft, validation, recovery, and narrow table checks pass. |
| D — Supporting views and verification | Apply the same rules to Activity and Diagnostics. Place Activity history inside the page layout. Capture matching after renders. | Rendered, accessibility, and relevant existing behavior checks pass. |

Activity should start with its page heading and Refresh action. Keep submission
history, job results, artifacts, and proposals in the same content layout.
Use the shared button treatment for Latest submissions. Preserve all history
records, output paths, warnings, and proposal decisions. Diagnostics keeps its
source, Section, and artifact groups, with readable severity and counts.

## Expected frontend files

| File | Planned responsibility |
| --- | --- |
| `circuit-designer/apps/editor/src/styles.css` | Application tokens, toolbar, status, controls, menus, dialogs, and supporting-view spacing |
| `circuit-designer/apps/editor/src/EditorMenuBar.tsx` | Toolbar layout, Spec identity/status integration, and secondary AI Assistant action |
| `circuit-designer/apps/editor/src/App.tsx` | In-flow status and recovery notices; Activity and Diagnostics layout |
| `circuit-designer/packages/document-a2ui-react/src/styles.css` | Compact document, Contents, tables, draft forms, and responsive rules |
| `circuit-designer/packages/document-a2ui-react/src/index.tsx` | Active Contents state, narrow disclosure, heading context, exact-case IDs, and draft labels |
| `circuit-designer/apps/editor/e2e/` | Extend focused browser checks for new navigation and responsive behavior |
| `docs/editor-ui.md` | Update the documented controls and layout after implementation |

No Spec schema, deterministic Activity generation, or Circuit service changes
are expected. Build the generated editor bundle from the edited frontend
source; do not edit the generated bundle directly.

## Verification and acceptance

Compare before and after renders of the same sample and states at 390, 1024,
1440, and 1728 px. Add boundary checks at 620, 800, and 1100 px. Keep the
document order, six Contents destinations, eight ports, two SystemVerilog
sections, and all source text visible or reachable. Compare complete content,
not only Section counts.

Add focused browser assertions for the new behavior: current-Section state,
uncovered anchor targets, narrow Contents focus handling, page-width
containment, readable Edit controls, and exact-case hardware IDs. Use existing
browser fixtures to check all port families, long names, and long descriptions.

Run the editor build and the relevant document-renderer and editor browser
suites. Confirm existing name/port edits, SystemVerilog validation, one active
draft, Cancel, stale-save recovery, approval-mode display, Circuit Designer
launch, and Activity controls. Use isolated sample copies for any saved edits.

Check keyboard traversal, menu/dialog focus restoration, visible focus,
200% zoom, contrast, and coarse-pointer hit areas. Check that printed circuit
previews still show complete diagrams and omit interactive preview controls.
Use Better Design's copy and spacing checks on the after renders, then inspect
each screenshot. Resolve confirmed serious issues before calling the visual
change complete.

These screenshots establish the original baseline. The implementation record
contains the matching after renders and verification results.
