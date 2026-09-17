# DSH UI migration and extension map

## Result

The former custom React assistant and its REST/SSE chat protocol have been
removed. The assistant now uses the DSH web UI as its shell and extends it with
small product-owned Cordis plugins. Backward compatibility with the former chat
API is intentionally out of scope.

This split keeps changes in the DSH fork generic. DSH gained reusable product
profiles, product client bundles, new-session intent handlers, and locale policy;
spec2gds branding, binding forms, owner APIs, tools, prompts, and diff views stay
in this repository.

## Layer and dependency map

| Layer | Important plugins | Depends on | Responsibility |
| --- | --- | --- | --- |
| DSH base host | agent, session, JSONL persistence, LLM adapter, tools registry, prompt, goal | Cordis loader and profile | Agent lifecycle and durable runtime |
| DSH web host | web server, gateway/connection, session controller, settings controller | base host | Browser transport and session remote APIs |
| DSH client kernel | modules, connection, remotes, renderer, layout, locale | web host | Loads browser plugins and provides React/slots/services |
| DSH conversation UI | session, sidebar/workspace, conversation, chat, tool | kernel and session controller | Navigation, transcript, composer, streaming, cancellation, tool topology |
| spec2gds host bundle | `@spec2gds/harness-assistant` | agents, persistence; optionally web server | Bindings, owner tools, prompts, reviews, auxiliary HTTP routes |
| spec2gds web bundle | `@spec2gds/harness-web` | slots, UI session, sessions, tool renderer | Binding dialog, branding, proposal cards and diff visualizations |

Cordis profile rows are composed in order. `dsh-base` supplies the runtime,
`dsh-web-app` supplies the complete web surface, and later spec2gds patches
override or disable rows by stable ID. Browser plugins use dependency injection
instead of importing the whole UI. The most important extension points are:

- `uiSession.registerNewSessionHandler`, which lets the product own the binding
  flow while DSH still creates and navigates the session;
- `sidebar.brand.mark` and `sidebar.brand.name`, which replace branding;
- keyed `tool.call.toolview` entries, which replace only the views for
  `prepare_spec_proposal` and `prepare_circuit_proposal`;
- DSH session-controller services, which remain the single path for prompts,
  streaming, cancellation, rename, archive, restore, and export.

## Retain, extend, and drop

| DSH UI capability | Decision | Product behavior |
| --- | --- | --- |
| Layout, theme, renderer, connection | Retain unchanged | Foundation of the web client |
| Session sidebar/workspace | Retain | Durable conversation navigation |
| Chat composer and streaming transcript | Retain | DSH owns all model turns and cancellation |
| Rename, archive/restore, export | Retain | Uses DSH session contracts directly |
| Model status/selection | Retain | Defaults to `openai/gpt-4o-mini` |
| `/goal` and goal bar | Retain for now | Generic DSH semantics; later replace with spec2gds milestone/design-goal semantics |
| Generic tool renderer | Retain as fallback | Product keyed views replace only proposal tools |
| New-session behavior | Extend | Product binding dialog validates an existing owner before DSH session creation |
| Brand slots | Extend | spec2gds identity |
| Spec proposal card | Add | Semantic before/after values, exact operations, diagnostics, apply/discard |
| Circuit proposal card | Add | Before/after topology SVG, diff counts, exact operations, send/discard/reconcile |
| Coding agent presets | Drop | Prevents standard preset from restoring coding tools or persona |
| Shell, filesystem, web, skills, subagents, workflows, jobs | Drop | Not part of an owner-bound design assistant |
| Terminal/file/document sidebars and deliverables | Drop | Scratch workspace is an implementation detail |
| Plan UI | Drop for this milestone | No compatible focused plan-mode composition yet |
| Attachments and file references | Drop | Owner context is the authoritative design input |
| Schedules, plugin management, Cordis debug UI | Drop | Deployment/operator concerns, not end-user workflows |
| Permission chooser | Drop | Product enforces fixed read-only/no-general-tool policy |
| Official DSH branding and open-in-app | Drop | Replaced by product identity and editor launch links |
| Feedback controls | Drop | No product feedback backend or workflow |
| Language picker | Drop | Deployment is English-only for now |

## Custom visualization strategy

Proposal cards are business tool views, not transcript forks. A proposal tool
returns a JSON review object in its normal durable tool result. DSH pairs and
renders the call; the spec2gds keyed view reads that result and presents the
domain-specific visualization.

Spec preview responses expose semantic paths with before/after values, so the
card renders a two-column field diff and retains raw operations and diagnostics
under disclosures. Circuit previews contain the base document, candidate, and
logical diff. The card derives a compact topology drawing for each side and
highlights changed instances and nets. This approach is independently
replaceable later by the full Circuit renderer without changing the agent,
session protocol, or review state machine.

## Command-line profile

`spec2gds-headless` reuses the host plugin and prompt/tool contracts but omits
the web server and every browser plugin. `npm run request -- ...` creates a
fresh immutable binding or resumes a supplied session ID, submits exactly one
prompt through DSH headless, prints the answer (or JSON events), and exits. The
native release carries the equivalent `deployment/request.mjs` entry point.

## Maintenance policy

Keep application behavior in spec2gds. Changes belong in the DSH fork only when
they are product-neutral extension contracts or distribution features that
another DSH product could use. Pin the fork commit in `harness.lock.json`; make
and test DSH changes on `spec2gds/integration`; package only from a clean pinned
checkout. This prevents spec2gds-specific UI from becoming a permanent fork of
the upstream DSH web application.

## Follow-up work

The next product layer should redefine `/goal` around design milestones and
owner revisions instead of generic agent work. Other reasonable follow-ups are
reusing the Circuit Designer's production renderer in the proposal card,
adding browser-component tests for the binding dialog and tool cards, and
deciding whether any owner-native reference/attachment workflow should be
introduced. None requires reviving the old assistant API or custom transcript.
