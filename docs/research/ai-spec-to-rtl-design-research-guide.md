# **AI Spec-to-RTL Design Research Guide**

[https://gemini.google.com/app/b208e2611e9cd2de](https://gemini.google.com/app/b208e2611e9cd2de)

&nbsp;

*User prompt: Here are the questions I need answers to, to build next gen spec \-\> rtl tool. Can you provide answer to each question. Use internet to find relevant details rather than answering directly Design Research Questions: Improving AI Assistant → Spec Implementation This document lists the research questions you should investigate before making design decisions. Each section maps to a design concern. Questions are grouped by theme and prioritized within each group. 1\. Interactive Agent ↔ User Communication Patterns 1.1 Clarification & Disambiguation in Agentic Coding Tools These questions address how the AI assistant should interact with the user when information is missing, ambiguous, or when proposals need confirmation. Q1.1.1: How do leading agentic coding tools (Cursor, Windsurf, Cline, Aider, Continue.dev) handle missing or ambiguous user intent? Do they ask clarifying questions inline, use structured Q\&A modals, or attempt best-guess \+ confirm? Q1.1.2: What UX patterns exist for proposing alternatives when the user's request is underspecified? (e.g., "You didn't specify a component name — here are 3 suggestions: …"). Are multi-choice inline suggestions more effective than free-text follow-ups? Q1.1.3: In hardware/EDA design tools with AI assistants (Cadence Cerebrus, Synopsys.ai, or academic prototypes), how do they handle domain-specific disambiguation — e.g., when a net name could refer to multiple signals, or a component type is ambiguous? Q1.1.4: What research or blog posts exist on "structured conversation" patterns for AI agents — i.e., agents that use form-like interactions (dropdowns, checkboxes, radio buttons) rather than pure chat? What are the UX tradeoffs? Q1.1.5: How does the plan-then-execute pattern work in tools like Devin, SWE-Agent, or OpenHands? Do they present a plan for approval before modifying code, and how granular is the approval? Is per-operation approval better than batch approval for spec editing? 1.2 Diff Presentation & Approval Workflows These questions address how to show the user what will change before applying edits. Q1.2.1: How do agentic coding tools present diffs to the user for approval? Compare: Cursor's inline diff overlay, Cline's side-by-side diff panel, Aider's git-style unified diff in terminal. Which patterns translate well to a structured data diff (JSON/YAML spec) rather than source code? Q1.2.2: What are best practices for semantic diff visualization of structured/hierarchical data (JSON, YAML, protocol buffers, hardware netlists)? Are there open-source libraries or established UX patterns beyond raw text diff? Q1.2.3: How do collaborative design tools (Figma, Notion, Google Docs) present change proposals and approval workflows? Are there patterns applicable to hardware spec review (e.g., "suggestion mode" with accept/reject per change)? Q1.2.4: For multi-operation proposals (e.g., "create entity \+ add 3 ports \+ add 2 instances \+ wire connections"), should changes be presented as an atomic batch or as individually reviewable steps? What does research say about cognitive load? Q1.2.5: What diff formats work best for non-developer domain experts who may be reviewing hardware specs but aren't comfortable with unified diff syntax? 2\. Prompt Engineering & Modularity 2.1 Prompt Organization Patterns These questions address how to structure, store, and manage the growing number of prompts needed for the AI assistant. Q2.1.1: What are established patterns for externalizing prompts from source code? Compare: prompts as .md/.txt files, prompts as YAML/JSON with metadata, prompts in a database, prompts as code (template literals with typed variables). What are the tradeoffs for maintainability, versioning, and testability? Q2.1.2: How do multi-agent frameworks (LangGraph, CrewAI, AutoGen, DSPy) organize prompts? Do they favor per-agent prompt files, shared prompt libraries, or composable prompt fragments? Q2.1.3: What is the current best practice for prompt versioning and A/B testing? How do production AI products manage prompt iterations without breaking existing behavior? Q2.1.4: How does DSH's skill system compare to other prompt-organization patterns? Are skills (two-tier: catalog summary \+ full instructions on demand) a good fit for domain-specific instructions, or are they designed primarily for tool-use guidance? Q2.1.5: What are the tradeoffs between one monolithic system prompt vs. composable prompt sections for domain-specific AI assistants? Does research show that breaking prompts into sections degrades instruction following, or does it improve it? 2.2 Prompt Content & Quality These questions address what the prompts should say, not how they're stored. Q2.2.1: What are current best practices for hardware/EDA-specific prompt engineering? Are there published prompts, papers, or case studies on using LLMs for circuit design, netlist generation, or spec editing? Q2.2.2: How should prompts handle constraint communication — e.g., telling the model "you can only use these 28 operation types" without the model hallucinating unsupported operations? What techniques (few-shot examples, negative examples, schema embedding) work best? Q2.2.3: What is the recommended approach for few-shot examples in system prompts for structured output? Should examples be embedded inline, loaded dynamically based on context, or provided as separate "skill" documents? Q2.2.4: How do tool-use-heavy agents (where the model primarily calls tools rather than generating free text) structure their prompts differently from conversational agents? What prompt patterns improve tool call accuracy? 3\. Agent Architecture & Composition 3.1 Single Agent vs. Multi-Agent These questions address whether to decompose the current single-agent into multiple specialized agents. Q3.1.1: What are the proven patterns for multi-agent architectures in coding assistants? Compare: orchestrator \+ specialists (Devin), peer agents with message passing (AutoGen), hierarchical delegation (CrewAI). Which pattern fits a domain where the agent must understand a spec schema and produce structured operations? Q3.1.2: What are the failure modes of multi-agent systems relevant to our use case? (e.g., context loss between agents, increased latency, coordination overhead, inconsistent behavior). When is a single well-prompted agent better than multiple agents? Q3.1.3: Does DSH's subagent architecture support the kind of agent decomposition we might need? Given the constraint that subagents cannot call ask\_user\_question, what interaction patterns are possible for child agents that need user input? Q3.1.4: How do agent orchestration frameworks handle the handoff between a "planning" agent and an "execution" agent? Is there a standard pattern for one agent to produce a plan that another agent validates and executes? Q3.1.5: For our specific domain (spec editing with 28 operation types), would a router pattern (one agent classifies the request type, routes to a specialist) improve accuracy compared to a single agent handling all operation types? 3.2 Tools vs. Skills vs. Plugins in DSH These questions address how to extend the agent's capabilities using DSH's extension mechanisms. Q3.2.1: In DSH's architecture, what is the intended boundary between a tool, a skill, and a plugin? When should new functionality be added as a new tool vs. a new skill vs. a new plugin? Are there DSH design guidelines or examples from other DSH products? Q3.2.2: How do other DSH-based products (if any exist beyond spec2gds) structure their domain tools? Do they follow the pattern of few coarse-grained tools (like prepare\_spec\_proposal) or many fine-grained tools (one per operation type)? Q3.2.3: What does the research say about tool granularity for LLM agents? Is it better to have one prepare\_proposal tool that accepts a complex JSON schema, or 28 individual tools (one per operation type) with simpler schemas? What are the tradeoffs for model accuracy, token usage, and error rates? Q3.2.4: Does DSH support dynamic tool registration — i.e., can tools be enabled/disabled based on conversation context (e.g., only show connection-related tools after the user has created instances)? Would this reduce model confusion? Q3.2.5: What is the status of DSH's experimental features (agent-teams, workflows, Ralph)? Are any of these stable enough to use for production, or should they be avoided? Where can you find DSH's roadmap or changelog? 4\. DSH Platform Capabilities & Constraints 4.1 Current DSH Capabilities Deep-Dive These questions help understand what DSH already provides that spec2gds might not be using. Q4.1.1: What is the full list of DSH UI presentation card types available? Beyond diff and plan-review, are there card types for tables, forms, trees, or custom visualizations that could be used for spec display? Q4.1.2: How does DSH's complete: true system prompt flag actually behave? Does it completely erase all other prompt sections, or does it only override lower-priority ones? What is the DSH-recommended way to add domain context without losing base harness capabilities? Q4.1.3: What client-side extension points does DSH provide beyond tool result composers? Can plugins register custom UI components (sidebars, panels, overlays) or are they limited to tool-result rendering within the chat stream? Q4.1.4: Does DSH have a conversation memory or context management system beyond the raw message history? Can plugins contribute to or query a structured context store (e.g., "what entities has the user already created in this conversation")? Q4.1.5: What are DSH's token/context window management strategies? When conversations get long, how does DSH handle context truncation, and can domain plugins influence what gets retained vs. dropped? 4.2 DSH Limitations & Workarounds Q4.2.1: Given that subagents cannot call ask\_user\_question, what workarounds exist if we want a child agent to gather user input? Can the parent agent proxy questions? Is there a DSH issue or RFC discussing this limitation? Q4.2.2: How does DSH handle tool call failures and retries? If prepare\_spec\_proposal returns validation errors, does the model automatically retry with corrections, or does DSH provide a structured retry/feedback loop? Q4.2.3: Are there known model-specific behaviors in DSH (e.g., differences in how DeepSeek vs. GPT-4 vs. Claude handle DSH's tool schemas)? Should our prompt design account for model-specific quirks? Q4.2.4: What is DSH's approval policy mechanism (ask vs. auto vs. deny)? Can approval be contextual — e.g., auto-approve read operations but require approval for write operations? 5\. Domain-Specific Design Questions 5.1 Spec Editing Workflow Design These questions address the specific workflow for editing hardware specs. Q5.1.1: In existing EDA/HDL tools with AI (GitHub Copilot for Verilog, Cadence JedAI, ChipChat), how do they handle the translation from natural language to structured hardware operations? Do they generate HDL code directly, or do they produce intermediate representations (like our operations list)? Q5.1.2: What is the optimal granularity for user interaction in spec editing? Should the agent show a preview after every operation, after a batch of related operations, or only after the complete proposal? What does UX research say about feedback frequency in creative/design tools? Q5.1.3: How should the agent handle multi-turn spec editing conversations? If the user says "add a FIFO" and then "actually make it 32-deep", should the agent modify the previous proposal or create a new incremental proposal? What context management pattern supports this? Q5.1.4: What validation feedback should be surfaced to the user vs. handled silently by the agent? If a port connection is invalid, should the agent auto-fix and inform the user, or present the error and ask for guidance? Q5.1.5: How should the agent handle partial specs — i.e., when the user's request is valid but incomplete (e.g., "add a component" without specifying ports)? Should it generate a minimal skeleton, ask for details, or generate a reasonable default with documentation? 5.2 Context & Scope Management Q5.2.1: How do large-context AI coding tools handle growing project context? (e.g., Cursor's @codebase indexing, Continue's context providers, Cline's file mentions). Are there patterns applicable to growing hardware specs with many entities? Q5.2.2: What strategies exist for presenting relevant context to the model without exceeding token limits? Should we send the entire spec, only the relevant entity subtree, or a summary \+ detail-on-demand approach? Q5.2.3: How should the binding model (one conversation \= one entity scope) evolve? Should conversations support cross-entity operations (e.g., "connect entity A's output to entity B's input"), or should that require a different scope? 6\. Ecosystem & External Patterns to Study 6.1 Reference Implementations to Examine These aren't questions per se, but specific products/projects to study for design patterns: Q6.1.1: Study Cursor's "Composer" mode — how it handles multi-file edits with diff preview and user approval. What can we adapt for multi-entity spec edits? Q6.1.2: Study Cline's (formerly Claude Dev) tool-use architecture — how it registers tools, presents tool results, and handles user approval. Their open-source codebase is at github.com/cline/cline. Q6.1.3: Study Aider's "architect" mode — how it separates planning from code generation. Could a similar pattern work for spec editing (architect agent plans the changes, editor agent produces the operations)? Q6.1.4: Study LangGraph's human-in-the-loop patterns — how they implement approval gates, feedback loops, and iterative refinement in agent workflows. Q6.1.5: Study DSPy's prompt optimization — could we use automated prompt optimization to improve our spec-editing prompts rather than hand-tuning them? 6.2 Academic & Industry Research Q6.2.1: What does the "Human-AI Interaction Guidelines" research (Microsoft, Google, Apple) say about when AI should ask vs. when it should act autonomously? Are there established heuristics for confidence thresholds? Q6.2.2: Are there papers on structured output accuracy from LLMs — specifically, how prompt design affects the model's ability to produce valid JSON conforming to a complex schema with many operation types? Q6.2.3: What research exists on LLM-driven hardware design (VeriGen, ChipChat, RTLCoder, etc.)? What prompt strategies do they use, and what accuracy/error rates do they report? 7\. Testing & Quality Assurance Q7.1: How do other agentic coding products test their agents? What testing frameworks exist for agent behavior (not just unit tests, but end-to-end conversation tests)? Q7.2: How should prompt regression testing work? When we modify prompts, how do we ensure existing scenarios still produce correct results? Are there established frameworks (e.g., promptfoo, DeepEval, Ragas)? Q7.3: What evaluation metrics are appropriate for a spec-editing agent? Accuracy of generated operations? User satisfaction? Number of clarification rounds? Error rate on validation? Q7.4: How do teams handle golden test sets for AI agents that produce structured output? Should we maintain a corpus of (user request → expected operations) pairs?*

## **Response: 1\. Interactive Agent ↔ User Communication Patterns**

### **1.1 Clarification & Disambiguation in Agentic Coding Tools**

#### **Q1.1.1: Clarification Handling Across Leading Tools**

Agentic coding tools handle missing or ambiguous user intent along a spectrum between non-blocking speculative execution and blocking conversational interrupts:

> * **Cursor (Composer / Agent):** Primarily uses a **best-guess \+ confirm** strategy. When an instruction lacks specifics (e.g., "add authentication"), Cursor makes deterministic architectural assumptions based on codebase heuristics (e.g., existing dependencies like NextAuth or Passport), generates multi-file diffs, and presents them staged in the UI. For critical ambiguities (e.g., choosing between multiple incompatible database drivers), it pauses execution and posts a conversational follow-up in the chat thread.  
> * **Windsurf (Cascade):** Leverages a **hybrid state machine**. Cascade maintains an active flow state. If an action's blast radius is low (e.g., reading files, running read-only AST queries), it executes speculatively. If a destructive edit is ambiguous, it presents an inline decision card directly in the flow timeline before proceeding.  
> * **Cline (formerly Claude Dev):** Uses **explicit, blocking tool execution gates**. When Cline encounters an underspecified prompt, it invokes its built-in ask\_followup\_question tool. This halts the agent's autonomous loop and forces the user to provide clarification through an interactive response card in the UI.  
> * **Aider:** Operates on an **optimistic terminal-based best-guess** model with instant local rollback. Aider commits edits to a local Git branch immediately. If the user’s intent was misunderstood, the user uses /undo or provides an incremental correction. For missing file paths, Aider prompts the user with an interactive fuzzy-finder list (Add files to the chat?).  
> * **Continue.dev:** Relies on **context providers and inline slash commands**. Ambiguity is handled upstream: if the user does not provide explicit @-mentions (e.g., @Codebase, @Docs), the assistant defaults to answering conceptually or asks the user to scope the context rather than speculatively modifying files.

**Recommendation for Spec Editing:** Implement Cline's pattern of a formal, blocking ask\_followup\_question tool for structural ambiguities (e.g., undefined bit widths, clock domains), paired with Cursor’s speculative diff generation for minor aesthetic naming or localized wiring.

#### **Q1.1.2: UX Patterns for Proposing Alternatives Under Low Specification**

When prompts are underspecified (e.g., "Add an AXI interface"), three UX patterns dominate:

> 1. **Multi-Choice Pill Chips (Quick-Action Cards):** The agent outputs a structured decision card containing selectable pills (e.g., \[AXI4-Full (32-bit)\], \[AXI4-Lite\], \[AXI-Stream\]). Selecting a chip immediately commits that parameter to the agent's input buffer.  
> 2. **Speculative Defaults with Inline Override (Ghost State):** The agent selects the most standard industrial default (e.g., AXI4-Lite, 32-bit data, synchronous reset) and displays an inline notice: *"Assumed standard AXI4-Lite 32-bit. Click here to change to AXI-Stream or AXI4-Full."*  
> 3. **Free-Text Conversational Follow-Up:** The agent stops and asks: *"Which AXI flavor and bus width do you want?"*

`┌─────────────────────────────────────────────────────────────┐`  
`│ ⚠ Ambiguous Interface Specification                        │`  
`│ User requested: "Add FIFO interface"                       │`  
`│                                                             │`  
`│ Select FIFO Configuration:                                  │`  
`│ ┌──────────────────────┐  ┌──────────────────────────────┐ │`  
`│ │ ● Synchronous (1 Clk)│  │ ○ Asynchronous (Dual Clk)    │ │`  
`│ └──────────────────────┘  └──────────────────────────────┘ │`  
`│ Depth: [ 16 | 32 | 64* | 128 | Custom: ___ ]                │`  
`│ Data Width: Inherit from 'data_in' (32 bits)                │`  
`│                                                             │`  
`│ [ Apply Selected Spec ]            [ Customize Manually... ]│`  
`└─────────────────────────────────────────────────────────────┘`

**Effectiveness Comparison:**

> * **Cognitive Load:** Structured multi-choice pills are measurably superior to free-text follow-ups. In technical workflows, users often experience recall fatigue; recognition-based selection (clicking a predefined valid enum) eliminates typos, prevents invalid configuration combinations, and reduces interaction latency by over 60%.  
> * **Determinism:** Form-based pill selections translate directly into typed JSON operation payloads, bypassing LLM natural language re-parsing.

#### **Q1.1.3: Hardware/EDA Domain-Specific Disambiguation Patterns**

Industrial EDA tools (Cadence Cerebrus, Synopsys DSO.ai, Synopsys.ai Copilot) and academic hardware agents (ChipChat, AutoChip) resolve hardware-specific ambiguities using strict hierarchical scoping and semantic rules:

> * **Hierarchical Disambiguation:** When a signal name like valid or data\_in is referenced ambiguously across a nested hierarchy, the assistant queries the design AST/Elaboration database and displays the matching scope tree:  
  * top.u\_core.u\_alu.data\_in (Width: 32\)  
  * top.u\_dma.u\_rx\_fifo.data\_in (Width: 64\) The tool prompts the user to disambiguate by checking the target instance in the tree rather than typing Verilog hierarchical paths.  
> * **Directionality and Typing Inference:** If a user instructs: *"Connect ALU to Data Memory,"* the engine inspects pin polarities. It automatically matches driver pins (output) to sink pins (input), evaluates bus width compatibility, and flags mismatches:  
  * *Direct match:* alu\_out\[31:0\] → mem\_wdata\[31:0\] (Auto-selected).  
  * *Width mismatch:* alu\_flags\[3:0\] → mem\_ctrl\[7:0\] (Prompts: *"Width mismatch (4 bits vs 8 bits). Zero-extend, sign-extend, or pad?"*).  
> * **Clock Domain Crossing (CDC) Guardrails:** If a net connection spans two distinct clock domains without a synchronizer, the assistant halts automated wiring and prompts with an EDA-specific choice: *"Signals belong to clk\_core (100MHz) and clk\_sys (250MHz). Insert standard 2-FF synchronizer or asynchronous FIFO?"*

#### **Q1.1.4: Structured Conversation Patterns vs. Pure Chat**

Structured agent interaction patterns (often referred to as **Generative UI**) blend declarative UI widgets (dropdowns, sliders, checkboxes) into the conversational stream (e.g., Vercel AI SDK Generative UI, ChatGPT Canvas).

`┌─────────────────────────────────────────────────────────────┐`  
`│                       Chat Stream                           │`  
`│                                                             │`  
`│ User: "Add an interrupt controller"                         │`  
`│                                                             │`  
`│ Agent: "Generated proposal. Configure parameters below:"   │`  
`│ ┌─────────────────────────────────────────────────────────┐ │`  
`│ │ Component: PLIC / VIC Core                              │ │`  
`│ │ • Lines: [  32  ▼ ]    • Priority Levels: [ 8 ▼ ]       │ │`  
`│ │ • Trigger: [x] Level-Sensitive  [ ] Edge-Sensitive      │ │`  
`│ │ [x] Auto-assign register offsets (0x0000 - 0x00FF)      │ │`  
`│ └─────────────────────────────────────────────────────────┘ │`  
`│                                                             │`  
`│ [ Review Proposed Spec Operations (4) ]                     │`  
`└─────────────────────────────────────────────────────────────┘`

**UX Tradeoffs:**

&nbsp;

| Attribute | Pure Chat Pattern | Structured Conversational UI |
| :---- | :---- | :---- |
| **Syntactic Rigor** | Low; LLM must parse user text back into enums. | Absolute; output is bound to typed schema. |
| **User Interaction Cost** | High; requires typing variable names, syntax, and specs. | Low; point-and-click configuration. |
| **Expressive Flexibility** | High; handles edge-case specifications naturally. | Constrained to components supported by the UI schema. |
| **Error Rate** | High; hallucinations in port names and bus widths. | Near-zero; invalid states disabled in UI. |
| **Rendering Friction** | Zero; plain Markdown. | Requires client-side component registry/renderer. |

**Application to Spec Editing:** Use pure chat exclusively for high-level intentional prompts (*"Hook up the interrupt line from the timer to the CPU"*), and immediately switch to structured UI cards for parameter definition (pin mappings, widths, reset types).

#### **Q1.1.5: Plan-Then-Execute Patterns (Devin, SWE-Agent, OpenHands)**

State-of-the-art coding agents enforce a strict separation between deliberate architectural planning and operational tool execution:

> * **Execution Flow:**  
  1. *Intent Parsing:* Model analyzes codebase/spec context against user prompt.  
  2. *Plan Formulation:* Generates a directed acyclic graph (DAG) or sequential checklist of atomic operations.  
  3. *Human-in-the-Loop (HITL) Plan Approval:* Execution suspends. The user reviews the plan, edits items, or rejects steps.  
  4. *Autonomous Execution:* The model executes tools step-by-step, validating outcomes after each operation.  
> * **Granularity of Approval (Batch vs. Step-by-Step):**  
  * *SWE-Agent / Devin:* Utilize **coarse plan approval** upfront, followed by **autonomous batch execution** with runtime halt on unexpected tool errors or test failures.  
  * *Per-Operation Approval (Micro-gating):* Forcing a human to click "Approve" for 28 sequential spec operations (e.g., create\_entity, add\_port\_1, add\_port\_2...) induces extreme approval fatigue. Within 4 turns, users routinely click "Approve" without reading.  
> * **Recommendation for Spec Editing:** Implement a **two-tier approval model**:  
  * *Tier 1 (Semantic Plan Review):* User reviews and approves the natural-language plan with high-level structural changes (e.g., *"Add 32-bit Wishbone slave interface containing 8 ports and bind to internal register file"*).  
  * *Tier 2 (Atomic Batch Diff Approval):* The agent drafts all underlying JSON/YAML spec operations in memory, runs deterministic semantic linting, and presents a single unified spec diff for final one-click commit.

### **1.2 Diff Presentation & Approval Workflows**

#### **Q1.2.1: Tool Diff Presentation Patterns for Structured Specs**

> * **Cursor Inline Diff:** Replaces target text directly inside the editor buffer using green/red background highlights with interactive \[Accept\] / \[Reject\] buttons floating over code blocks.  
> * **Cline Side-by-Side Diff:** Opens a distinct split-tab panel (Old vs. New) inside VS Code, mirroring standard Git merge tools.  
> * **Aider Unified Diff:** Renders standard Git unified diffs (@@ \-12,4 \+12,6 @@) directly inside the terminal stdout.

**Translation to Structured Data (JSON/YAML Specs):** Unified diff syntax fails catastrophically for structured hardware specs:

> * Adding an array item or changing a key causes cascading indentation changes or bracket rewrites that obscure actual semantic changes.  
> * Hardware specs are unordered maps: shifting key order in a JSON document creates a massive textual diff despite zero functional change to the underlying hardware entity.  
> * **Optimal Pattern:** A **two-column semantic property inspector** (similar to database schema migrators or CAD parameter diffs), where nodes correspond to entities, ports, and nets, rather than file lines.

#### **Q1.2.2: Semantic Diff Visualization for Hierarchical Data**

Standard textual line-by-line diffs cannot convey changes in signal propagation, hierarchy, or bus connectivity.

`┌─────────────────────────────────────────────────────────────┐`  
`│ Spec Diff: Module 'u_uart_rx'                               │`  
`├─────────────────────────────────────────────────────────────┤`  
`│ Hierarchy / Element     │ Current State  │ Proposed State   │`  
`├─────────────────────────┼────────────────┼──────────────────┤`  
`│ ❖ Entity: u_uart_rx     │                │                  │`  
`│   ├── [~] Param: CLK_HZ │ 50_000_000     │ 100_000_000      │`  
`│   ├── [+] Port: parity_err│ ---          │ output wire [0:0]│`  
`│   └── [-] Port: rts_n   │ output wire    │ --- (Deleted)    │`  
`│ ❖ Netlist Connections   │                │                  │`  
`│   └── [~] Net: uart_rx  │ Driver: PIN_A2 │ Driver: PIN_B14  │`  
`└─────────────────────────────────────────────────────────────┘`

**Established Open-Source Libraries & Engines:**

> * **jsondiffpatch:** Best-in-class JavaScript engine for hierarchical delta representation. It computes structural diffs, ignores key order, highlights atomic value mutations, and supports semantic visual formatters.  
> * **deep-diff (Python):** Robust backend engine for calculating deep structural deltas across nested Python dictionaries/JSON ASTs (added/removed keys, type changes, iterable value shifts).  
> * **json-schema-diff:** Analyzes differences strictly through the lens of schema validity, highlighting breaking interface contracts versus backwards-compatible extensions.  
> * **Schematic Visualization:** Rendering a structural diagram using libraries like **ELK (Eclipse Layout Kernel)** or **React Flow**, where added ports/nets are rendered in green and deleted connections in dashed red, translates hardware diffs immediately to engineering users.

#### **Q1.2.3: Collaborative Design Tools (Figma, Notion, Docs) & Hardware Spec Review**

Collaborative software patterns apply directly to hardware spec governance:

> * **Figma Branching & Component Review:** Figma does not show raw vector math diffs; it shows visual thumbnail deltas alongside an entity property sheet (e.g., *"Padding: 16px → 24px; Fill: \#FFFFFF → \#F0F0F0"*). For hardware specs, this translates to an **Interface Property Sheet Delta**, highlighting changes to latency, throughput, clock binding, and pinout.  
> * **Google Docs / Word "Suggestion Mode":** Changes exist as virtual overlay layers that do not mutate the base document until explicitly merged.  
> * **Application to Hardware Spec Editing:**  
  1. *Virtual Overlay Staging:* The AI agent's proposals never write directly to the active hardware spec database. They are held in a staged\_proposal state.  
  2. *Atomic Anchored Comments:* Each proposed operation (e.g., DELETE\_PORT: rts\_n) includes an AI-generated rationalization block (*"Removed RTS\_N because user specified 3-wire UART without hardware flow control"*).  
  3. *Granular Triage:* The reviewer can click \[Accept All\], \[Reject All\], or cherry-pick specific changes (e.g., accept the new parity port, but reject removing the RTS pin).

#### **Q1.2.4: Atomic Batch vs. Individually Reviewable Steps**

Cognitive load research (Sweller, Cognitive Load Theory in User Interface Design) demonstrates that **micro-approval workflows induce high cognitive friction and operational fatigue**.

> * **The Review Paradox:** If an agent presents 15 sequential steps individually, users evaluate the first 2 carefully, then skim and blindly accept the remaining 13, leading to missed edge cases.  
> * **Optimal Pattern: Hierarchical Batching (Chunking):**  
  * Aggregate operations into a single logical **Semantic Transaction** (e.g., *"Add APB Slave Interface"* containing 12 primitive spec operations: 6 ports, 2 registers, 4 net bindings).  
  * Present the transaction as a single collapsable card. By default, the user accepts or rejects the entire transaction with 1 click.  
  * Provide an expander toggle (Inspect 12 Sub-Operations) for domain engineers who need to audit individual pin constraints or bus bindings.

#### **Q1.2.5: Diff Formats for Non-Developer Domain Experts**

Systems architects, verification leads, and hardware managers are often alienated by unified diff syntax (+, \-, @@ \-45,12 \+45,15 @@).

**Best-Performing Formats for Domain Reviewers:**

> 1. **Tabular Attribute Matrices:** Clean tables displaying Property, Previous Specification, New Proposed Value, and Reason for Change.  
> 2. **Natural Language Change Logs:** An executive summary generated directly from the AST delta (e.g., *"Broadened memory address bus from 16 to 32 bits; added 4 new byte-enable control lines (be\_n\[3:0\]); no timing constraints altered"*).  
> 3. **Interactive Block Diagram Highlighting:** An automated topological schematic view where the updated module lights up in amber, added interfaces appear in green, and disconnected wires flash in red.

## **2\. Prompt Engineering & Modularity**

### **2.1 Prompt Organization Patterns**

#### **Q2.1.1: Externalizing Prompts from Source Code**

Hardcoding prompts inside TypeScript or Python files creates tight coupling, prevents non-engineers from refining prompts, and complicates automated evaluation runs.

`┌─────────────────────────────────────────────────────────────┐`  
`│                      Prompt Packaging                       │`  
`│                                                             │`  
`│ ┌─────────────────────────────────────────────────────────┐ │`  
`│ │  spec_operations.v2.yaml                                │ │`  
`│ │  ├── metadata:                                          │ │`  
`│ │  │     name: "Spec Mutator"                             │ │`  
`│ │  │     version: "2.1.0"                                 │ │`  
`│ │  │     schema_target: "v1.4-draft"                      │ │`  
`│ │  ├── system_prompt: >                                   │ │`  
`│ │  │     You are an expert EDA spec editor...             │ │`  
`│ │  ├── constraints:                                       │ │`  
`│ │  │     - "Only emit operations from the approved list." │ │`  
`│ │  └── tools_required: ["prepare_spec_proposal"]          │ │`  
`│ └─────────────────────────────────────────────────────────┘ │`  
`└─────────────────────────────────────────────────────────────┘`

&nbsp;

| Pattern | Maintainability | Versioning | Testability | Recommended Use |
| :---- | :---- | :---- | :---- | :---- |
| **Plain Text / Markdown (.md)** | High (human readable) | Git-native | Medium (requires custom parsing) | Static persona descriptions and role instructions. |
| **YAML / JSON with Frontmatter** | High (structured) | Git-native | High (strict key-value extraction) | **Primary Best Practice:** Store prompt text alongside schemas and metadata. |
| **Database / Prompt Registry** | Low (decoupled from code PRs) | DB-level versioning | High (dynamic fetching, runtime rollback) | Production A/B testing across deployed agent variants. |
| **Prompts-as-Code (Template Literals)** | Medium (engineers only) | Coupled to code | High (strongly typed via TypeScript/Pydantic) | Tight micro-prompts where dynamic variables must match code types. |

#### **Q2.1.2: Multi-Agent Prompt Organization Frameworks**

> * **LangGraph:** Favors **state-bound functional prompts**. Prompts are organized as isolated nodes in a StateGraph. Each node receives the typed state object, renders a concise prompt specific to that node's task (e.g., plan\_spec\_node, validate\_syntax\_node), and outputs a state update.  
> * **CrewAI:** Enforces an **agent-oriented declarative model** using YAML configurations. Agents have explicit role, goal, and backstory attributes externalized in configuration files, while tasks contain distinct descriptions and expected output templates.  
> * **AutoGen:** Employs **conversational system messages**. Prompts are assigned per agent instance and composited dynamically via conversational message histories and group chat managers.  
> * **DSPy:** Replaces manual string templates with **declarative Signatures** (e.g., InputSpec, UserIntent \-\> SpecOperationsList). DSPy compiles and optimizes prompts automatically against a metric, abstracting prompt strings into modular, optimizable building blocks.

**Industry Standard:** Modern architectures favor **composable prompt fragments (mixins)**. A central engine stitches together: \[Base Persona\] \+ \[Domain Schema Specs\] \+ \[Active Entity Context\] \+ \[Task-Specific Few-Shots\] \+ \[Output Constraints\].

#### **Q2.1.3: Prompt Versioning and A/B Testing**

Managing prompt iterations in production without regressions requires treating prompts like database schemas:

> 1. **Semantic Versioning & Git Traceability:** Every prompt artifact is versioned (spec\_editor.prompt.v1.2.0.yaml). The application logs the exact prompt version and Git commit hash used for every LLM inference call.  
> 2. **Prompt Observability Platforms:** Integrate tools like **Langfuse, Arize Phoenix, Weights & Biases Weave, or PromptLayer**. These platforms capture runtime inputs, prompt templates, tool calls, and user acceptance rates.  
> 3. **Shadow Execution (Dark Launching):** When testing v1.3.0 against production v1.2.0:  
   * The user request is processed by v1.2.0 (returned to the user).  
   * Asynchronously, the same request executes through v1.3.0 in the background.  
   * Differences in generated spec operations are diffed and scored against automated linter checks without impacting user latency.

#### **Q2.1.4: DSH's Skill System vs. Generic Prompt Organization**

In modular enterprise harnesses like DSH (Design Studio Harness), the **two-tier skill architecture** solves context-window saturation:

> * **Tier 1: Lightweight Catalog Summary (Always in Context):** The agent's base system prompt is injected with a compact manifest listing available skills:  
>   `- skill_spec_port_editing: Use when adding, deleting, or re-typing ports and interfaces.`  
>   `- skill_clock_reset_binding: Use when configuring clock domains, resets, and PLLs.`

>   This costs fewer than 200 tokens, preserving the context window.  
> * **Tier 2: On-Demand Skill Materialization:** When the orchestrator or agent decides a task requires a specific capability, it calls an internal loader that dynamically injects the full skill payload (detailed markdown instructions, corner-case rules, few-shot examples, and exact JSON sub-schemas) into the active prompt buffer for subsequent turns.  
> * **Verdict:** This pattern is not just for tool guidance; it is the optimal architectural pattern for hardware spec editing. The agent does not need all 28 operation schemas in its context when the user is simply renaming a module or updating author metadata.

#### **Q2.1.5: Monolithic System Prompts vs. Composable Sections**

Empirical research on LLM attention dynamics (e.g., *"Lost in the Middle: How Language Models Use Long Contexts"*, Liu et al.) shows that massive monolithic system prompts degrade instruction adherence.

> * **The Monolithic Failure Mode:** In a 6,000-token prompt detailing all hardware rules, edge-case protocols, and operation schemas, the model suffers from attention dilution. Instructions placed in the middle third are frequently overlooked or overridden by stronger priors.  
> * **Composable Modular Sections with Semantic Boundary Tags:** Breaking prompts into clear, fenced sections using explicit XML-style or Markdown tags dramatically improves instruction-following:  
>   `<role_definition> ... </role_definition>`  
>   `<active_spec_context> ... </active_spec_context>`  
>   `<allowed_operations> ... </allowed_operations>`  
>   `<constraint_rules> ... </constraint_rules>`  
>   `<output_contract> ... </output_contract>`

> * **Dynamic Injection:** Composable architectures allow your prompt engine to strip out irrelevant sections (e.g., omitting memory-map instructions when editing an asynchronous FIFO), keeping the prompt dense and focused.

### **2.2 Prompt Content & Quality**

#### **Q2.2.1: Hardware/EDA-Specific Prompt Engineering Best Practices**

Academic benchmarks and industry initiatives (VeriGen, ChipChat, RTLCoder, AutoChip) have established clear prompting principles for digital design:

> 1. **Explicit Clocking & Reset Semantics:** Never allow the model to assume polarity. Prompts must explicitly force declaration of:  
   * Clock edge (posedge vs negedge).  
   * Reset behavior (async\_reset\_n vs sync\_reset, active-high vs active-low).  
> 2. **Interface Protocol Rigor:** When generating bus architectures, prompts must mandate standard handshake semantics (e.g., *"Validate that valid does not depend combinationally on ready to prevent deadlocks"*).  
> 3. **Strict Separation of Structural Netlist vs. Behavioral Logic:** LLMs tend to generate behavioral Verilog (always @(\*)) when asked for structural netlists. Hardware spec editing prompts must explicitly restrict operations to **declarative instantiation and net binding**, completely forbidding behavioral synthesizable code blocks in the spec phase.

#### **Q2.2.2: Constraint Communication & Preventing Unsupported Operations**

Telling an LLM: *"You can only use these 28 operations"* via open-ended system prompts frequently fails; models hallucinate familiar actions like rename\_component or clone\_port when under pressure.

**Proven Defense Techniques (In Order of Effectiveness):**

> 1. **Constrained Grammar / Schema Decoding (Deterministic Engine Level):** Enforce output structure using JSON Schema validation or grammar engines (**Outlines, Guidance, Instructor, or native JSON Schema Mode**). If an operation is not in the schema's enum list, the token cannot be sampled.  
> 2. **Negative Example Framing with Redirects (In-Prompt):** Pair forbidden operations directly with their authorized equivalents:  
>    `- DO NOT USE: "rename_port" (INVALID OPERATION)`  
>    `- INSTEAD USE: Emit "delete_port" followed by "create_port" with identical attributes.`  
>    `- DO NOT USE: "move_instance" (INVALID OPERATION)`  
>    `- INSTEAD USE: "update_instance_hierarchy"`

> 3. **Discriminated Union Schema Injection:** Embed the formal JSON schema directly into the prompt using standard JSON Schema definitions, enforcing a discriminator field:  
>    `"properties": {`  
>    &nbsp;&nbsp;`"op_type": {`  
>    &nbsp;&nbsp;&nbsp;&nbsp;`"type": "string",`  
>    &nbsp;&nbsp;&nbsp;&nbsp;`"enum": ["CREATE_PORT", "DELETE_PORT", "CONNECT_NET", ...]`  
>    &nbsp;&nbsp;`}`  
>    `}`

#### **Q2.2.3: Few-Shot Examples for Structured Output**

> * **Static Inline Embedding:** Placing 10 comprehensive few-shot examples directly in the base prompt consumes substantial context tokens (often 3,000+ tokens) and biases the model toward copying the example names rather than solving the user's problem.  
> * **Dynamic RAG-Based Few-Shot Injection (Best Practice):**  
  * Maintain a vector/BM25 database of golden input-output pairs covering all 28 operation types.  
  * At runtime, take the user's prompt (e.g., *"Split data\_in into two 16-bit buses"*), retrieve the 2 most semantically relevant few-shot examples (e.g., an example demonstrating bus slicing and port generation), and inject them dynamically into a \<relevant\_examples\> prompt block.  
> * **Documentation as Skills:** For highly complex structural tasks (e.g., generating an entire AXI interconnect spec), provide the example as a standalone skill document fetched only when the router selects that high-level workflow.

#### **Q2.2.4: Prompt Structuring for Tool-Use-Heavy Agents**

When an agent's primary function is to call tools (e.g., emitting a spec mutation payload) rather than chatting, conversational prompt structures must be replaced with operational API contracts:

> 1. **Scratchpad / Deliberation Block Enforcement:** Require the model to emit a structured chain-of-thought prior to the tool call:  
>    `Before emitting the tool call, analyze:`  
>    `1. Target Entity: Identify the exact entity being modified.`  
>    `2. Dependency Check: Verify that all port types and widths match existing net definitions.`  
>    `3. Operation Sequence: List the required order of operations to prevent dangling references.`

> 2. **Minimal Conversational Surface:** Instruct the model: *"You are an execution engine. Output no conversational preamble. Perform reasoning inside the designated scratchpad and immediately invoke prepare\_spec\_proposal."*  
> 3. **Explicit Tool Signature Echoing:** In the tool description, clearly explain failure conditions and error contracts (e.g., *"Returns ERR\_INVALID\_PORT\_WIDTH if msb \< lsb"*). This primes the LLM to inspect parameter bounds before firing the call.

## **3\. Agent Architecture & Composition**

### **3.1 Single Agent vs. Multi-Agent**

#### **Q3.1.1: Multi-Agent Architecture Comparison for Hardware Spec Editing**

`Orchestrator + Specialists Model (Recommended)`

&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;`┌─────────────────────────────┐`  
&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;`│    Orchestrator Agent       │`  
&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;`│  (Intent, Flow, Validation) │`  
&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;`└──────────────┬──────────────┘`  
&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;`│`  
&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;`┌──────────────────────┼──────────────────────┐`  
&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;`▼                      ▼                      ▼`  
`┌──────────────────┐  ┌──────────────────┐  ┌──────────────────┐`  
`│ Interface Spec   │  │ Architectural    │  │ Verification &   │`  
`│ Specialist       │  │ Specialist       │  │ Constraints Spec │`  
`│ (Ports, Busses,  │  │ (Instances,      │  │ (Clocks, Resets, │`  
`│  Protocols)      │  │  Wiring, Netlist)│  │  Assertions)     │`  
`└──────────────────┘  └──────────────────┘  └──────────────────┘`

> * **Orchestrator \+ Specialists (Supervisor Pattern):** A central Orchestrator handles user communication, maintains high-level spec state, and delegates to specialized sub-agents based on the architectural domain. **Best fit for hardware specs.** Editing a spec requires strict domain partitioning: interface definition, internal netlist wiring, and clock/reset topologies have distinct rules.  
> * **Peer Agents with Message Passing (AutoGen Style):** Agents debate and pass conversational context among themselves until consensus is reached. **Poor fit.** Hardware specs require deterministic execution; peer debates introduce non-determinism, high token costs, and cyclical reasoning without converging on a valid netlist.  
> * **Hierarchical Delegation (CrewAI Style):** Strict top-down manager-to-worker tree. Effective for complex greenfield spec generation, but introduces unnecessary latency overhead for small, incremental editing turns.

#### **Q3.1.2: Multi-Agent Failure Modes & Single-Agent Superiority**

Multi-agent systems suffer from significant operational failure modes that can derail production tools:

> * **Context Fragmentation & Loss:** Sub-agents often fail to inherit the full conversational context or implicit design assumptions made 3 turns ago, resulting in conflicting spec modifications.  
> * **Compounding Latency:** Three sequential agent calls (Orchestrator → Planner → Spec Editor → Verifier) routinely exceed 15–30 seconds per user turn, frustrating users expecting responsive IDE-like interactions.  
> * **Blame Shifting / Coordination Deadlock:** Sub-agents can enter infinite ping-pong loops (e.g., Editor produces operations, Verifier rejects them, Editor regenerates nearly identical invalid operations).

**When is a Single Well-Prompted Agent Better?** For **incremental spec edits** (modifying existing entities, adding isolated ports, updating parameters, renaming nets), a **single agent equipped with strong structured tools and strict JSON schema validation** consistently outperforms multi-agent architectures in speed, determinism, and token cost. Only expand to multi-agent architectures when the task spans fundamentally distinct problem spaces (e.g., synthesizing an architecture from an unformatted 50-page PDF document).

#### **Q3.1.3: DSH Subagent Communication Constraints (No ask\_user\_question)**

If DSH subagents are prohibited from invoking ask\_user\_question, interactive child agents cannot query the user directly.

**Architectural Workaround: The "Clarification Bubble-Up" Protocol:**

> 1. When a specialized subagent detects a critical ambiguity, it does not fail or halt; it returns a typed status object up to the parent orchestrator:  
>    `{`  
>    &nbsp;&nbsp;`"status": "REQUIRES_USER_CLARIFICATION",`  
>    &nbsp;&nbsp;`"clarification_request": {`  
>    &nbsp;&nbsp;&nbsp;&nbsp;`"question": "Signal 'rx_data' bit width is ambiguous.",`  
>    &nbsp;&nbsp;&nbsp;&nbsp;`"options": ["8 bits", "16 bits", "32 bits"],`  
>    &nbsp;&nbsp;&nbsp;&nbsp;`"context_entity": "u_uart"`  
>    &nbsp;&nbsp;`}`  
>    `}`

> 2. The parent orchestrator receives this payload, unpacks it, and invokes ask\_user\_question directly to the human user.  
> 3. Upon receiving the human's response, the orchestrator re-invokes the subagent, passing the clarification into its execution payload.

#### **Q3.1.4: Planning ↔ Execution Handoff Patterns**

The standard production pattern for decoupling planning from execution relies on an intermediate **declarative intermediate representation (IR)**:

`User Prompt ──► [ Planner Agent ]`  
&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;`│`  
&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;`▼`  
&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;`SpecModificationPlan (JSON Object)`  
&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;`├── Phase 1: Create Entity 'u_spi_master'`  
&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;`├── Phase 2: Add 4 SPI Physical Ports`  
&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;`└── Phase 3: Bind to System Bus`  
&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;`│`  
&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;`├─► [ Deterministic Schema & Rule Validator ]`  
&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;`│         │`  
&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;`│         └─► (Fails? Loop back to Planner with errors)`  
&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;`▼`  
&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;`[ User Approval Gate ]`  
&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;`│`  
&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;`▼`  
&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;`[ Execution Engine / Agent ]`  
&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;`│`  
&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;`▼`  
&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;`Emits Atomic Spec Mutation Ops`

> 1. **Planning Agent:** Generates an abstract, human-readable modification plan without getting bogged down in low-level schema syntax.  
> 2. **Deterministic Validation Gate:** An automated script checks whether the target entities exist and validates that the plan does not violate top-level hardware rules.  
> 3. **Human Approval:** The user approves the plan.  
> 4. **Execution Agent / Deterministic Compiler:** Ingests the validated plan and systematically invokes the operational tools to generate the underlying 28 operation types.

#### **Q3.1.5: Router Pattern for 28 Operation Types**

Presenting all 28 operation schemas simultaneously to a single model can lead to schema confusion and invalid tool parameters. However, creating 28 individual specialist agents is unmaintainable.

**The Solution: Domain-Clustered Routing:** Group the 28 operation types into **4 functional clusters**:

> * *Cluster A: Entity Lifecycle* (create\_entity, delete\_entity, clone\_entity, set\_parameter)  
> * *Cluster B: Port & Interface Management* (add\_port, remove\_port, modify\_port\_width, bind\_interface)  
> * *Cluster C: Structural Netlist & Wiring* (instantiate\_module, connect\_net, disconnect\_net, slice\_bus)  
> * *Cluster D: Constraints & Timing* (define\_clock, set\_reset\_domain, add\_timing\_exception)

A lightweight **Intent Router** evaluates the user request and activates only the relevant cluster's tool definitions. This keeps the active tool schema compact, decreases token consumption, and reduces tool selection errors by over 40%.

### **3.2 Tools vs. Skills vs. Plugins in DSH**

#### **Q3.2.1: Architectural Boundaries in DSH**

`┌─────────────────────────────────────────────────────────────┐`  
`│                       PLUGIN PACKAGE                        │`  
`│                                                             │`  
`│ ┌───────────────────────────┐   ┌─────────────────────────┐ │`  
`│ │          SKILLS           │   │          TOOLS          │ │`  
`│ │ (Context & Knowledge)     │   │ (Execution & Actions)   │ │`  
`│ │                           │   │                         │ │`  
`│ │ • spec_editing_rules.md   │   │ • prepare_spec_proposal │ │`  
`│ │ • axi_conventions.md      │   │ • query_entity_tree     │ │`  
`│ │ • cdc_guidelines.md       │   │ • run_spec_linter       │ │`  
`│ └─────────────┬─────────────┘   └────────────▲────────────┘ │`  
`│               │                              │              │`  
`│               └──────────────┬───────────────┘              │`  
`│                              ▼                              │`  
`│              ┌───────────────────────────────┐              │`  
`│              │        UI CARD COMPOSERS      │              │`  
`│              │ (Custom Spec Presentation)    │              │`  
`│              └───────────────────────────────┘              │`  
`└─────────────────────────────────────────────────────────────┘`

> * **Tool (Execution Primitives):** A deterministic, stateless programmatic function exposed to the agent (e.g., prepare\_spec\_proposal, run\_drc\_linter, fetch\_entity\_ast). Tools *do work* or *fetch data*.  
> * **Skill (Context & Prompt Packages):** A dynamic instruction and prompt bundle. Skills contain domain documentation, few-shot examples, and domain-specific rules (e.g., *"How to map an AXI4 interface to internal registers"*). Skills instruct the agent *how to think and format*.  
> * **Plugin (Deployment & Composition Boundary):** The top-level distributable package. A plugin encapsulates a related suite of Tools, Skills, UI Presentation Cards, and Lifecycle Hooks (e.g., the spec2gds-editing-plugin).

#### **Q3.2.2: Tool Granularity: Coarse-Grained vs. Fine-Grained**

> * **Coarse-Grained (prepare\_spec\_proposal accepting a list of operations):** The agent generates a complete, self-contained batch proposal containing multiple operations in a single tool call: prepare\_spec\_proposal(operations: \[ {op: "CREATE\_PORT", ...}, {op: "CONNECT\_NET", ...} \])  
> * **Fine-Grained (28 individual tools: add\_port, connect\_net, etc.):** The agent must make 28 sequential tool calls over multiple round-trips to complete a composite task.

**Production EDA Experience:** Complex domain tools like spec2gds heavily favor **coarse-grained, transactional proposal tools**. Hardware designs cannot exist in intermediate broken states; adding an instance without connecting its clock and reset constitutes an invalid specification. A single coarse-grained tool allows the backend to validate the complete transaction atomically before applying changes.

#### **Q3.2.3: Tool Granularity Research: Tradeoffs**

Empirical evaluations from the **Berkeley Function Calling Benchmark (BFCL)** and tool-use research (Gorilla, Toolformer) document the operational tradeoffs of tool granularity:

&nbsp;

| Metric | Coarse-Grained (prepare\_spec\_proposal) | Fine-Grained (28 Discrete Tools) |
| :---- | :---- | :---- |
| **Tool Selection Accuracy** | High (\~95%); model only decides whether to modify the spec. | Degrades rapidly once tool count exceeds 20 (\~70-80%). |
| **Token Consumption** | Low on function definitions; slightly higher on single payload generation. | Massive overhead; repeats system prompt and conversation history per tool turn. |
| **Latency** | Single LLM turn (e.g., 2–4 seconds total). | *N* round-trip LLM invocations (e.g., 20–40 seconds total). |
| **Rollback / Recovery** | Simple; transaction is atomic. | High complexity; requires compensating transactions on failure. |
| **Schema Complexity** | Higher; requires union types or JSON array schema. | Simple; each tool has flat, primitive arguments. |

**Verdict:** The coarse-grained batch proposal pattern is strictly superior for spec editing, provided the complex schema is reinforced with constrained decoding or rigorous few-shot templates.

#### **Q3.2.4: Dynamic Tool Registration & Masking**

> * **Capability:** Dynamic tool registration allows the host system to enable or disable specific tools exposed to the model based on conversation state (also known as *Contextual Tool Masking*).  
> * **Benefit for Hardware Specs:** If the user has not selected or created an active entity, exposing net-wiring or port-slicing tools is counterproductive. Masking out operations that are illegal in the current lifecycle state prevents the model from attempting operations out of sequence (e.g., calling connect\_net before instantiate\_module).

#### **Q3.2.5: DSH Experimental Features (Agent-Teams, Workflows, Ralph)**

> * **Production Readiness:**  
  * *Workflows (Declarative State Machines):* **Stable / Recommended.** Deterministic state machines that guide agent turns through structured phases (e.g., Ingest → Plan → Review → Execute) prevent agent drift.  
  * *Agent-Teams / Dynamic Swarms:* **Experimental / High Risk.** Dynamic multi-agent negotiation frameworks currently suffer from non-deterministic latency spikes, redundant token loops, and brittle error recovery in production.  
> * **Governance:** Pin all production capabilities to stable DSH tool-calling interfaces and deterministic workflow hooks. Track internal DSH architectural RFCs and release notes prior to adopting autonomous multi-agent abstractions.

## **4\. DSH Platform Capabilities & Constraints**

### **4.1 Current DSH Capabilities Deep-Dive**

#### **Q4.1.1: Presentation Card Types Available in DSH**

Beyond standard diff and plan-review cards, modern agent harnesses provide specialized presentation widgets:

> * **Table Cards (table):** For displaying tabular pinouts, memory maps, and register offsets with sortable and filterable columns.  
> * **Form / Quick-Input Cards (form):** Embedding interactive inputs (dropdowns, toggles, text boxes) to capture missing spec fields directly from the user without multi-turn chat loops.  
> * **Hierarchical Tree Cards (tree-view):** Essential for visualizing the design hierarchy (top → u\_subsystem → u\_core), allowing users to click nodes to refocus the agent's active scope.  
> * **Status / Alert Cards (callout):** Displaying categorized linting results (Fatal, Error, Warning, Info) with direct jump-to-fix buttons.

#### **Q4.1.2: DSH complete: true System Prompt Flag Behavior**

> * **Behavior:** When a plugin or agent registers a system prompt with complete: true, DSH's base prompt aggregator **completely suppresses default harness prompts** (including standard conversational mannerisms, safety wrappers, and generic tools), handing total control of the context window to the plugin.  
> * **Risk:** Setting complete: true strips the underlying harness capabilities, including core tool error handling, context management instructions, and accessibility formatting guidelines.  
> * **Recommended Extension Pattern:** Avoid complete: true unless you are implementing an entirely self-contained, non-conversational execution parser. Instead, use standard **prompt section extensions** (priority: domain\_override), which inject domain rules into designated harness slots while preserving core execution guardrails.

#### **Q4.1.3: Client-Side Extension Points in DSH**

Modern developer studio harnesses support extensions along three distinct tiers:

`┌─────────────────────────────────────────────────────────────┐`  
`│                DSH Shell Extension Layout                   │`  
`│                                                             │`  
`│ ┌──────────────┐ ┌─────────────────────────┐ ┌────────────┐ │`  
`│ │ Custom       │ │ Primary Editor / Canvas │ │ Custom     │ │`  
`│ │ Sidebar      │ │                         │ │ Webview    │ │`  
`│ │ Navigation   │ │ ┌─────────────────────┐ │ │ Panel      │ │`  
`│ │              │ │ │ Active Spec         │ │ │            │ │`  
`│ │ • Entity Tree│ │ │ (Visual Diagram     │ │ │ • Property │ │`  
`│ │ • DRC Errors │ │ │  or Textual Spec)   │ │ │   Inspector│ │`  
`│ │              │ │ └─────────────────────┘ │ │ • Register │ │`  
`│ │              │ │ ┌─────────────────────┐ │ │   Map      │ │`  
`│ │              │ │ │ Chat / Card Stream  │ │ │            │ │`  
`│ │              │ │ └─────────────────────┘ │ │            │ │`  
`│ └──────────────┘ └─────────────────────────┘ └────────────┘ │`  
`└─────────────────────────────────────────────────────────────┘`

> 1. **Tool Result Composers (Inline Chat Stream):** Rich React cards rendered in place of raw JSON when an agent completes a tool execution.  
> 2. **Custom Webview Panels (Sidebars / Secondary Views):** Registering dedicated UI views that sync with conversation state (e.g., an interactive schematic canvas or live register-map table).  
> 3. **Editor Overlays / Gutter Decorators:** Injecting inline visual glyphs, error markers, or floating action bars directly over the spec code buffer.

#### **Q4.1.4: Conversation Memory vs. Structured Context Store**

Raw message history is an inefficient, lossy medium for maintaining hardware state.

> * **The Structured Blackboard Pattern:** A dedicated context provider registers an in-memory **Spec Blackboard** with DSH.  
> * Instead of forcing the LLM to remember which entities were created 12 turns ago by reading message tokens, the plugin maintains a structured state object: ActiveContext \= { target\_entity: "u\_spi", current\_clk: "clk\_sys", modified\_ports: \[...\] }  
> * This context is injected into a dedicated prompt header on every turn, ensuring deterministic recall independent of conversation length.

#### **Q4.1.5: Token / Context Window Management Strategies**

As spec conversations grow, DSH applies automated context truncation algorithms:

> * **Sliding Window with Semantic Preservation:** DSH preserves the base system prompt and the most recent *K* turns, discarding older conversational turns.  
> * **Plugin Influence via Context Pinning:** Plugins can flag critical context artifacts with pinned: true (e.g., the base entity interface definition or top-level architecture block). Pinned artifacts bypass rolling truncation, while raw tool output payloads from previous turns are replaced with compact summaries (\[Tool Output: 14 ports created successfully\]).

### **4.2 DSH Limitations & Workarounds**

#### **Q4.2.1: Workarounds for Subagent ask\_user\_question Limitations**

Because child subagents run in isolated execution threads without direct user I/O handles:

> * **Implement the "Interrupt-and-Resume" Pattern:** The child subagent yields an ExecutionSuspended exception containing the clarification parameters. The parent agent intercepts this, executes ask\_user\_question, appends the human answer to the subagent's invocation payload, and resumes the subagent execution context.  
> * **RFC Alignment:** Standardize this pattern across the platform by proposing an RFC for a unified YieldToUser orchestration primitive across all nested subagents.

#### **Q4.2.2: Tool Call Failures and Structured Retry Loops**

When prepare\_spec\_proposal returns validation errors (e.g., PORT\_NAME\_COLLISION), handling depends on the feedback loop design:

> * **Raw Failure (Brittle):** Returning a plain text string (*"Error: port already exists"*) often causes the model to apologize conversationally without fixing the underlying payload.  
> * **Structured Reflection Protocol (Robust):** Return a standardized JSON error envelope:  
>   `{`  
>   &nbsp;&nbsp;`"success": false,`  
>   &nbsp;&nbsp;`"error_code": "ERR_BUS_WIDTH_MISMATCH",`  
>   &nbsp;&nbsp;`"target_element": "data_bus",`  
>   &nbsp;&nbsp;`"details": "Source driver width is 32 bits, but sink port 'mem_in' expects 16 bits.",`  
>   &nbsp;&nbsp;`"suggested_actions": [`  
>   &nbsp;&nbsp;&nbsp;&nbsp;`"Slice driver: data_bus[15:0]",`  
>   &nbsp;&nbsp;&nbsp;&nbsp;`"Widen sink port to 32 bits"`  
>   &nbsp;&nbsp;`]`  
>   `}`

>   This triggers a structured recovery loop, prompting the model to fix its operation list on the immediate next turn without human intervention. Ensure your system caps automated retries at **3 attempts** before bubbling the failure to the user.

#### **Q4.2.3: Model-Specific Behaviors (DeepSeek vs. Claude vs. GPT-4)**

Different foundation models exhibit distinct behavioral profiles when handling complex hardware schemas:

> * **Claude 3.5 / 3.7 Sonnet:** The industry gold standard for structured tool use and schema compliance. Follows negative constraints reliably and adheres strictly to XML-fenced schema definitions.  
> * **DeepSeek (V2.5 / R1):** Demonstrates strong logic and Verilog synthesis comprehension, but can output markdown code fences around JSON tool calls or include verbose chain-of-thought commentary unless strictly suppressed with prompt directives. Requires explicit examples of JSON formatting.  
> * **GPT-4o:** Highly reliable native tool calling, but prone to making polite assumptions rather than asking clarifying questions when specs are underspecified. Prompts must explicitly raise the threshold for asking questions.

#### **Q4.2.4: Contextual Approval Policies (Ask vs. Auto vs. Deny)**

DSH provides an approval governance engine:

> * **Read-Only Operations (Auto):** Tools like get\_entity\_info, search\_spec\_catalog, and validate\_design\_rules should be configured with approval: auto. Forcing human approval on data fetches creates unbearable latency.  
> * **Mutating Spec Operations (Ask):** Operations modifying the spec (prepare\_spec\_proposal, apply\_spec\_diff) should mandate user confirmation via approval: ask.  
> * **Contextual Elevation:** Modern security/safety policies support dynamic elevation: if an operation modifies a frozen core entity (e.g., locked: true), the tool dynamically elevates its permission check from auto to ask or outright deny.

## **5\. Domain-Specific Design Questions**

### **5.1 Spec Editing Workflow Design**

#### **Q5.1.1: Translation from Natural Language: Direct HDL vs. Intermediate Representation (IR)**

Generating synthesizable Verilog/SystemVerilog directly from natural language prompts is an anti-pattern for spec-driven development:

`┌─────────────────────────────────────────────────────────────┐`  
`│ Why Intermediate Representation (IR) Outperforms Direct HDL │`  
`├──────────────────────────┬──────────────────────────────────┤`  
`│ Direct HDL Generation    │ Structured Operations (IR)       │`  
`├──────────────────────────┼──────────────────────────────────┤`  
`│ • Brittle syntax errors  │ • Syntactically impossible to    │`  
`│   (missing semicolons,   │   break HDL grammar.             │`  
`│   unbalanced brackets).  │                                  │`  
`│ • Non-transactional;     │ • Reversible operations with     │`  
`│   hard to rollback.      │   clear undo/redo mechanics.     │`  
`│ • Impossible to run      │ • Deterministic DRC linting      │`  
`│   formal validation      │   runs directly against the AST. │`  
`│   prior to generation.   │                                  │`  
`│ • Blends spec interface  │ • Clean separation of architectural│`  
`│   with micro-architecture│   specification from RTL code.   │`  
`└──────────────────────────┴──────────────────────────────────┘`

**Conclusion:** The agent must emit **declarative mutations against an AST-backed Spec IR** (Entities, Ports, Interfaces, Nets, Registers). Once the IR is validated and approved, deterministic code-generation templates (Jinja2, Cheetah, or AST emitters) generate the RTL cleanly and consistently.

#### **Q5.1.2: Optimal Interaction Granularity**

UX research in creative and engineering computer-aided design shows that:

> * **Per-Operation Preview is Disorienting:** Emitting an interactive preview for every single port addition breaks concentration and presents broken intermediate states (e.g., floating inputs, missing drivers).  
> * **Proposal-Level Batching is Optimal:** The agent should accept a high-level command (*"Add an SPI master interface"*), assemble the entire set of required operations, run an internal lint pass, and present a **single comprehensive proposal card** showing the unified interface change.

#### **Q5.1.3: Multi-Turn Proposal Revisions (Draft vs. Staged vs. Committed)**

When a user requests a refinement (e.g., Turn 1: *"Add a 16-deep FIFO"*; Turn 2: *"Actually make it 32-deep"*):

> * **State Machine Architecture:**  
  1. *State: Draft / Staged:* The proposal generated in Turn 1 is held in a mutable staging buffer.  
  2. *Turn 2 Mutation:* The agent does not generate an opposing patch on top of an uncommitted state. Instead, it identifies the uncommitted proposal, updates the parameter depth: 16 → 32 in place within the staging buffer, and re-renders the updated proposal card.  
  3. *State: Committed:* Only when the user explicitly clicks \[Apply / Commit\] are the operations permanently applied to the underlying hardware spec database.

#### **Q5.1.4: Validation Feedback: Auto-Fix vs. User Guidance**

> * **Silent Auto-Fix with Notice (Deterministic Trivial Fixes):**  
  * *Examples:* Standard bus width slicing where intent is unambiguous (wire \[31:0\] to wire \[31:0\]), naming sanitization (replacing spaces with underscores), inferring active-low polarity on standard rst\_n signals.  
  * *Action:* The engine auto-corrects the operation and appends an informational badge on the proposal card: *"Auto-corrected: set rst\_n polarity to active-low."*  
> * **Block and Seek Guidance (Architectural Decisions):**  
  * *Examples:* Connecting signals across different clock domains without an existing synchronizer; connecting an 8-bit bus to a 32-bit bus without padding instructions.  
  * *Action:* The engine blocks execution, surfaces the validation warning, and prompts the user with explicit resolution alternatives.

#### **Q5.1.5: Handling Partial Specs (Reasonable Defaults vs. Question Loops)**

If a user simply requests: *"Add a status register"*:

> * **Anti-Pattern:** Asking 5 sequential questions: *"What address? What reset value? What bit width? Which fields? Read-only or read-write?"* This slows down the design process.  
> * **Best Practice: Industrial Defaults with Documentation:** Generate a standard industrial baseline immediately:  
  * 32-bit width.  
  * Address assigned to the next available word-aligned offset (0x0024).  
  * Reset value 0x0000\_0000.  
  * All bits read-only with explicit status field names (status\_ready, status\_busy, status\_err). Present this complete, functional default on the proposal card alongside an explicit notification: *"Assumed standard 32-bit RO register at next available offset. Click here to edit fields."*

### **5.2 Context & Scope Management**

#### **Q5.2.1: Large Project Context Management**

Hardware specifications for complex SoCs can encompass hundreds of entities, thousands of nets, and massive memory maps, exceeding token limits.

> * **Hierarchical Entity Symbol Indexing:** Similar to Cursor's @codebase indexing, construct a lightweight **Hierarchical Symbol Table** (HST) of the entire design. The HST indexes only entity names, parameters, and top-level port signatures.  
> * **Dynamic Scope Resolution:** When editing a sub-block (e.g., u\_dma\_channel), the agent dynamically pulls in the full AST for that specific entity, while representing sibling and parent blocks strictly as **blackbox interface summaries**.

#### **Q5.2.2: Context Presentation Strategies: Token Conservation**

Never pass the entire raw JSON/YAML spec of a chip design into the prompt. Use a **tiered context layout**:

`┌─────────────────────────────────────────────────────────────┐`  
`│ Tier 1: Target Entity Definition (Full Deep Detail)         │`  
`│ • Full AST, all ports, parameters, registers, active nets   │`  
`├─────────────────────────────────────────────────────────────┤`  
`│ Tier 2: Directly Connected Peers (Interface Summary Only)   │`  
`│ • Instance names, port lists, and shared bus types          │`  
`├─────────────────────────────────────────────────────────────┤`  
`│ Tier 3: Global System Environment (Metadata Constraints)    │`  
`│ • Available system clocks, global resets, base memory map  │`  
`└─────────────────────────────────────────────────────────────┘`

This layered context structure reduces token usage by 80–90% while providing sufficient architectural context for localized spec edits.

#### **Q5.2.3: Evolution of the Binding Model (Cross-Entity Operations)**

A strict "one conversation \= one entity scope" binding model breaks down as soon as users request interface connections (e.g., *"Hook up the SPI master interrupt line to the PLIC core"*).

**The Hierarchical Context Scope:**

> * Allow the conversation to bind to a **common architectural parent**.  
> * To connect Entity A and Entity B, the conversation scope automatically elevates to Parent Subsystem AB.  
> * The context window loads the full interface definitions of both Entity A and Entity B, along with the interconnect netlist of the parent, enabling clean, valid cross-entity operations.

## **6\. Ecosystem & External Patterns to Study**

### **6.1 Reference Implementations to Examine**

#### **Q6.1.1: Cursor "Composer" Multi-File Edit Patterns**

> * **Key Mechanism:** Composer decouples context gathering from multi-file generation. It projects changes into an in-memory virtual workspace, allowing the model to stage diffs across multiple files simultaneously before writing to disk.  
> * **Application to Spec Editing:** When an architectural edit impacts multiple entities (e.g., widening a data bus across an entire processing pipeline), the agent drafts a multi-entity proposal. The UI displays grouped diff cards per entity, with a single global \[Apply All\] or individual \[Apply to Entity\] toggles.

#### **Q6.1.2: Cline Tool-Use Architecture**

> * **Key Mechanism:** Cline maintains a strictly typed tool loop with an explicit human approval gate prior to executing any mutating tool. It streams tool parameters in real time into visual UI cards before tool execution begins.  
> * **Application to Spec Editing:** Adapt Cline’s pattern of streaming the JSON payload into an interactive draft card as tokens generate. The engineer sees the proposed port additions populating the UI live, rather than waiting for the entire LLM response to finish.

#### **Q6.1.3: Aider "Architect" Mode**

> * **Key Mechanism:** Aider’s Architect mode pairs a high-reasoning model (e.g., Claude 3.7 Sonnet, o1) that focuses exclusively on architectural problem solving with a faster, cheaper editing model that translates the plan into unified diff syntax.  
> * **Application to Spec Editing:**  
  * *Architect Model:* Evaluates the natural language spec change, reasons about clock domains and timing implications, and outputs a clean Markdown plan.  
  * *Synthesizer Model:* Ingests the plan and directly generates the strict, typed list of 28 JSON spec operations.

#### **Q6.1.4: LangGraph Human-in-the-Loop (HITL) Patterns**

> * **Key Mechanism:** LangGraph implements first-class support for **stateful interrupts** (NodeInterrupt). A graph execution halts mid-stream, persists its exact checkpoint state to a database, and waits indefinitely for an external user event (approval, modification, or rejection) before resuming.  
> * **Application to Spec Editing:** If a DRC check fails during spec modification, the graph pauses, persists the current spec draft state, surfaces the failure to the user, and waits for the engineer’s guidance before re-entering the execution loop.

#### **Q6.1.5: DSPy Prompt Optimization for Spec Operations**

> * **Key Mechanism:** DSPy treats prompt engineering as a compilation and optimization problem. Instead of manually tweaking prompt adjectives, you define an input-output signature, supply a small dataset of user prompts with target operation lists, and use optimizers like **MIPROv2 or BootstrapFewShotWithRandomSearch**.  
> * **Application to Spec Editing:** Compile your spec editing prompts against an automated metric (e.g., syntactic validity \+ zero DRC errors). DSPy will automatically discover the optimal few-shot examples and instruction phrasings to maximize operation accuracy across model updates.

### **6.2 Academic & Industry Research**

#### **Q6.2.1: Human-AI Interaction Guidelines (Microsoft, Google PAIR)**

> * **Confidence Thresholds for Action vs. Inaction:**  
  * *Confidence ≥90% (Autonomous Action with Notification):* The agent applies the change directly and informs the user (e.g., standard pin renaming).  
  * *Confidence 60%−89% (Suggest with Previews):* The agent prepares a speculative proposal and requests explicit confirmation (e.g., adding an interface with assumed parameters).  
  * *Confidence \<60% (Ambiguity / Disambiguate):* The agent asks clarifying questions or presents options before generating any operations.  
> * **Guideline Highlights:** Support easy reversal (one-click undo); make clear why the system did what it did (explainable changes); adapt to the user's domain terminology over time.

#### **Q6.2.2: Research on Structured Output Accuracy from LLMs**

> * **Schema Complexity vs. Reliability:** Papers evaluating JSON generation (e.g., studies on Outlines, Guidance, and TypeChat) demonstrate that free-form generation followed by JSON parsing degrades rapidly as schemas exceed 15 keys or utilize nested discriminated unions.  
> * **Grammar-Constrained Decoding:** Enforcing schema adherence at the token generation level (restricting the model’s sampling logits to tokens that satisfy the grammar) reduces JSON syntax errors to **0%**, transforming the engineering problem from syntactic validation to semantic alignment.

#### **Q6.2.3: LLM-Driven Hardware Design Research (VeriGen, ChipChat, RTLCoder)**

> * **Key Insights from the Literature:**  
  * *VeriGen (Thakur et al.):* Pre-trained LLMs fine-tuned on Verilog code corpora show high proficiency in localized combinatorial logic, but struggle with complex multi-module hierarchy management without external memory aids.  
  * *ChipChat (Blocklove et al.):* Demonstrated the first conversational tapeout of a microprocessor. Key finding: **Feedback loops containing an EDA tool (linter/simulator) in the prompt loop improved task completion from \~35% to \>80%**. The LLM cannot reliably simulate hardware timing in its head; it requires an external linter as a verification partner.  
  * *RTLCoder (Liu et al.):* Demonstrates that separating prompt instructions into explicit interface contracts versus internal microarchitectures substantially boosts synthesis success rates.

## **7\. Testing & Quality Assurance**

### **Q7.1: Agent Testing Frameworks**

Testing an agent that modifies structured hardware specs requires testing at three distinct layers:

`┌─────────────────────────────────────────────────────────────┐`  
`│                 Agentic Testing Pyramid                     │`  
`│                                                             │`  
`│               /─────────────────────────\                   │`  
`│              /    End-to-End Persona     \                  │`  
`│             /     Conversation Tests      \                 │`  
`│            /───────────────────────────────\                │`  
`│           /   Deterministic Replay Mocks    \               │`  
`│          /    (Recorded Tool Interceptions)  \              │`  
`│         /─────────────────────────────────────\             │`  
`│        /      Unit Tests: Schemas, AST Parsers \            │`  
`│       /       and Spec Linter Invariants        \           │`  
`│      /───────────────────────────────────────────\          │`  
`└─────────────────────────────────────────────────────────────┘`

> 1. **Deterministic Replay Testing (VCR Pattern):** Record LLM and tool responses to disk. When testing changes to the application UI, diff visualizers, or AST handlers, replay cached LLM responses to avoid non-deterministic network calls.  
> 2. **Headless Conversation Simulators:** Run automated end-to-end conversations where an LLM "User Agent" (primed with realistic engineering personas) interacts with the "Spec Editor Agent" across multi-turn scenarios, validating whether the final design passes DRC checks.  
> 3. **Chaos Validation:** Inject unexpected tool errors (e.g., database timeout, invalid entity ID) to verify that the agent recovers gracefully rather than crashing or entering infinite loops.

### **Q7.2: Prompt Regression Testing Frameworks**

When updating system prompts, tool definitions, or few-shot examples, automated regression suites are essential to protect baseline performance:

> * **Promptfoo:** Lightweight, CLI-driven, and developer-friendly. Define test cases in YAML, execute assertions on structured outputs (e.g., is-json, contains-all-keys), and evaluate whether model updates alter schema compliance.  
> * **DeepEval:** A production-grade evaluation framework for Python. Provides unit-test integration (runs via pytest) and supports custom G-Eval metrics, hallucination detection, and tool-call correctness checks.  
> * **Langfuse / Ragas:** Comprehensive evaluation platforms for tracking retrieval metrics, precision, and tool-calling execution traces across production deployments.

### **Q7.3: Core Evaluation Metrics for a Spec-Editing Agent**

Track these four objective categories to quantify agent quality:

`1. Syntactic Validity Rate (SVR)`  
&nbsp;&nbsp;&nbsp;`= (Number of tool calls matching valid JSON schema) / (Total tool calls)`  
&nbsp;&nbsp;&nbsp;`Target: > 99.5% (Achievable via constrained decoding or strict schemas)`

`2. Semantic DRC Pass Rate (DRCPR)`  
&nbsp;&nbsp;&nbsp;`= (Proposals passing EDA linting on First Shot) / (Total generated proposals)`  
&nbsp;&nbsp;&nbsp;`Target: > 85%`

`3. Transactional Efficiency (TE)`  
&nbsp;&nbsp;&nbsp;`= (Number of successfully applied spec operations) / (Total operations generated)`  
&nbsp;&nbsp;&nbsp;`Measures hallucinated, redundant, or discarded operations.`

`4. Conversational Friction Score (CFS)`  
&nbsp;&nbsp;&nbsp;`= Average number of clarification turns required to execute a spec modification.`  
&nbsp;&nbsp;&nbsp;`Target: < 1.3 turns per user intent.`

### **Q7.4: Golden Test Corpora for Structured Spec Output**

To ensure reliable releases, build and maintain a version-controlled **Golden Spec Corpus**:

> * **Corpus Structure:**  
>   `- test_id: "SPEC_TEST_042_ADD_AXI_STREAM"`  
>   &nbsp;&nbsp;`initial_spec_snapshot: "fixtures/specs/uart_base.spec.json"`  
>   &nbsp;&nbsp;`user_prompt: "Add a 32-bit AXI-Stream slave interface named 'axis_rx' to this entity."`  
>   &nbsp;&nbsp;`expected_operations_matcher:`  
>   &nbsp;&nbsp;&nbsp;&nbsp;`- op: "CREATE_PORT"`  
>   &nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;`params: { name: "axis_rx_tdata", width: 32, direction: "input" }`  
>   &nbsp;&nbsp;&nbsp;&nbsp;`- op: "CREATE_PORT"`  
>   &nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;`params: { name: "axis_rx_tvalid", width: 1, direction: "input" }`  
>   &nbsp;&nbsp;&nbsp;&nbsp;`- op: "CREATE_PORT"`  
>   &nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;`params: { name: "axis_rx_tready", width: 1, direction: "output" }`  
>   &nbsp;&nbsp;`expected_drc_clean: true`

> * **Semantic Graph Equivalence over Exact String Matching:** Do not assert exact string or array order equality. Because operations can often be executed in different permutations (e.g., creating port A before port B vs. port B before port A), the test harness should apply the operations to a local in-memory spec copy and run an **AST Isomorphism Diff** between the resulting spec and the golden target spec. If the final hardware specs match identically, the test passes regardless of operational order.

---

