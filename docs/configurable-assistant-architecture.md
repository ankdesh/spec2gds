# Configurable Assistant Architecture

Status: implemented foundation, 2026-09-22

This design separates what the assistant is working on from how it works. A
service adapter supplies domain prompts, tools, and review rules. A user-chosen
preset supplies the execution shape. Adding another design service should
normally mean adding catalog documents and an owner adapter, not cloning the
agent runtime.

## Composition model

| Axis | Current values | Owner | Immutable boundary |
| --- | --- | --- | --- |
| Execution preset | `focused`, `goal`, `orchestrated` | Product preset catalog | Selected when the DSH Session is created |
| Service adapter | `spec-editor@1.0.0`, `circuit-editor@1.0.0` | Product workflow catalog | Selected from the permanent owner binding |
| Prompt bundle | `spec2gds.spec@1.0.0`, `spec2gds.circuit@1.0.0` | DSH prompt catalog | Exact version and content digest |
| Workflow | `prepare-reviewed-change@1.0.0` | DSH workflow catalog | Exact version and content digest |
| Target | owner URL, document, scope, optional entity | Product SQLite binding | Permanent for the conversation |

The prompt and workflow YAML providers are startup services. They reject YAML
directives, custom tags, anchors, aliases, merge keys, duplicate/unknown fields,
non-string keys, and oversized files. The product waits for both providers,
checks every exact reference, and seals both catalogs. Running sessions never
observe a hot reload or an implicit latest version.

## Implemented improvements and DSH use

| Improvement | Product changes | DSH changes/capability used | Why it matters |
| --- | --- | --- | --- |
| Versioned prompt catalog | Spec/Circuit YAML bundles; exact variable binding and section checks | New Cordis `promptCatalog` service and strict YAML provider | Domain instructions become reusable, testable configuration without losing deterministic section order |
| Generic workflow catalog | One generic workflow plus Spec/Circuit adapter YAML | New Cordis `sWorkflow` service and strict YAML provider | New services reuse lifecycle/budget behavior while contributing exact domain capabilities |
| Execution presets | Browser selector and immutable binding field | Existing `agent-presets`, `persona`, goal command/tool, and preset-scoped composition | One assistant supports one-shot Q&A, long-running goals, and orchestration without conflating service logic |
| Interactive clarification | All browser root presets mount the structured question tool; the host adds a conditional mandatory-use prompt section | Existing `user-questions`, `tool-ask-user`, `system-prompt`, and `ui-user-questions` composition | Missing proposal fields use a composer takeover and resume the same turn instead of an unstructured final response |
| Durable workflow state | Product starts the exact workflow on the first direct user request | Full-snapshot `s-workflow/change` Session event and strict projection | Pause/resume/replay retains exact definitions, budgets, progress, draft, and human decisions |
| Restricted model progress | Goal/orchestrated presets mount five workflow tools | Existing typed DSH tool registry plus new `tool-s-workflow` | The model can report work but cannot grant itself lifecycle, budget, approval, or mutation authority |
| Human workflow controls | Conversation dock and same-origin CAS endpoints | Client slot `conversation.input.dock` and DSH Session projection | Humans can pause, resume, cancel, answer, and approve without model-owned control flow |
| Bounded delegation | Parent binding inheritance, child/concurrency accounting, read-only child prompt | Existing in-process spawn provider, tool filtering, persona shadowing, depth limit | Multi-agent work reuses DSH while preventing child proposal, user-question, workflow, or recursive authority |
| Review completion bridge | Apply/send completes; discard cancels | Existing owner review card plus host workflow methods | Long-running work ends only at the same explicit mutation boundary as focused work |

## Authority matrix

| Operation | Model | Human/browser | Host/deployment |
| --- | ---: | ---: | ---: |
| Read bound owner context | Yes | — | Validates owner and binding |
| Prepare an owner proposal | Root agent only | Reviews | Persists artifact and preview |
| Request immediate clarification | Root agent only | Answers in structured composer | Routes the answer back into the same turn |
| Update draft/checkpoint | Yes, exact workflow revision | Observes | Enforces schema and budget |
| Request durable workflow input/completion review | Goal/orchestrated root only | Answers/reviews | Persists pending state |
| Start/pause/resume/cancel | No | Yes | Yes |
| Raise workflow budgets | No | Authorized API | Enforces preset hard caps |
| Apply/send owner artifact | No | Explicit review action | Loads persisted artifact and checks revision/digest |
| Delegate analysis | Orchestrated root only | Can cancel workflow | Enforces child count, concurrency, depth, persona, and tool filter |

The product automatically copies each successfully previewed domain proposal
into the workflow's complete draft slot. Apply/send is accepted only while the
run is active or already awaiting completion, then the same explicit review
action records completion approval. This prevents a paused or input-blocked
workflow from drifting behind an already-mutated owner document.

## Preset budgets

| Preset | Default rounds/requests | Default tokens/time | Children/concurrency/depth | Hard maximum |
| --- | --- | --- | --- | --- |
| `focused` | 3 / 4 | 1,200 / 5 min | 0 / 0 / 0 | Fixed at defaults |
| `goal` | 8 / 32 | 300,000 / 30 min | 0 / 0 / 0 | 24 rounds, 96 requests, 1M tokens, 120 min |
| `orchestrated` | 8 / 48 | 500,000 / 45 min | 6 / 3 / 1 | 24 rounds, 144 requests, 2M tokens, 120 min, 20 / 4 / 1 |

The service validates defaults and raised values. Product turn policy also caps
focused turns at three model steps, with one extra step only after a visible
structured-question call in that turn. Goal/orchestrated turns remain capped at
eight, and every individual model response at 1,200 output tokens. Workflow
checkpoint usage is monotonic; delegated child creation consumes the child
budget before work starts.

## Adding a service

1. Implement and test an owner client that returns authoritative context and a
   non-mutating preview, then applies only a persisted artifact after explicit
   review.
2. Add a versioned prompt bundle with the four required section IDs and stable
   orders.
3. Add a versioned `ServiceAdapter` naming exact prompt bundles, model-visible
   tool packages, optional skill packages, and review kind.
4. Add product binding validation, typed proposal normalization, and a review
   presenter for the service.
5. Add exact-ref startup checks, focused/preset tests, owner fixture coverage,
   and one real Harness integration trajectory.

No model-authored JavaScript, YAML expression, artifact mutation tool, or
service-selected preset is permitted. If a future service needs a capability
outside the generic workflow, add a bounded Cordis/DSH plugin with an explicit
authority and persistence contract rather than embedding executable workflow
logic in catalog data.

## Deferred work

- Domain skills remain deferred until measured prompt size or maintenance cost
  justifies on-demand loading; adapters already reserve exact `skillPackages`.
- Few-shot examples remain deferred pending a measured corpus-based policy.
- Additional generic workflows require their own versioned definition and
  review contract; no router silently changes workflow inside a conversation.
- Headless mode intentionally remains focused until a noninteractive approval
  and resumption contract is specified.

For a guided introduction to the DSH plugins and end-to-end execution paths,
read the [DSH configurable assistant tutorial](dsh-configurable-assistant-tutorial.md).
See [AI Assistant](ai-assistant.md), the
[improvement plan](ai-assistant-improvement-plan.md), and the preserved
[research guide](research/ai-spec-to-rtl-design-research-guide.md) for current
behavior, backlog decisions, and research provenance.
