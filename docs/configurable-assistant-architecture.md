# Configurable Assistant architecture

The product composes immutable owner binding and domain capabilities with one of three conversation presets. The [operations reference](event-driven-assistant-operations.md) owns monitoring, waiting and recovery; the [event reference](event-driven-assistant-system.md) owns configuration and inspection.

| Responsibility | Owner | Implementation |
| --- | --- | --- |
| Native execution, inbox, transcript, compaction, cancellation | Harness | Existing agent/session services and extension points |
| Persistent event members, subscriptions, delivery receipt/outcome, spending | Harness event-system packages | Conversation-local storage-domain ledger and native inbox dispatcher |
| Single-agent goal continuation | Native Harness goal service and driver | Native goal tools/rounds governed by the same admission and request accounting |
| Prompts and event definitions | Trusted deployment catalog and human template store | Startup YAML/Markdown, reviewed JSON revisions, pinned resolved definitions |
| Spec/Circuit identity and semantic context | spec2gds adapter | Immutable ProductState binding and owner context/schema reads |
| Proposal validation, apply/save approval, receipt | Bound owner and product review adapter | Existing proposal tools, review cards, revision checks, automatic/restricted policy |
| Human execution controls | Product API and dock | Revision-checked pause/resume/stop and acknowledged manual retry |

The `orchestrated` primary's direct user request publishes `user.requested`. The analyst's typed `analysis.ready` result reaches the reviewer; `review.ready` returns to the primary. Specialists keep native sessions between activations and receive read-only owner context tools. Only the primary can prepare proposals, and its guard requires a causal review for the latest human request or HTTP observation. Native receipt and turn-end observations distinguish delivery acceptance from completion.

The `goal` primary continues through the native goal driver. It does not route every round through subscriptions. A pending owner proposal blocks native continuation with a correlated durable wait. Resolving that exact review resumes the saved goal revision with its remaining allowance. Owner receipts do not automatically mark a goal complete.

Model publication cannot change capabilities or authorize owner mutation. The immutable owner binding is derived from specialist membership rather than fork lineage or model arguments. Native transcripts log every model-visible delivered message. The ledger validates its pinned configuration and relationships before recovering work; restart never grants automatic execution or fresh resources.

`focused` retains its existing bounded context/proposal exchange. Existing legacy goal/orchestrated chats stay readable; new bound conversations use the replacement runtime. Historical workflow services remain only to interpret saved transcripts. Workflow authoring, graph execution, webhooks, and file watchers remain outside the implemented scope; see [design rationale](agentic-systems-architecture-report.md).

HTTP condition monitoring, durable waiting, and controlled retries are covered in [operations](event-driven-assistant-operations.md).

Visual template editing, reviewed revisions, immutable configuration pins and causal inspection are described in [the event/plugin reference](event-driven-assistant-system.md); [the tutorial](event-driven-assistant-tutorial.md) covers both presets and their three browser tests.
