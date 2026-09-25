# AI Assistant Integration Issues and Remediation Plan

Status: active defect log and implementation guide  
Created: 2026-09-25  
Scope: Spec Editor, Circuit Designer, and AI Assistant integration boundaries

---

## 1. Overview and Problem Summary

An architectural and implementation audit of the integration between **Spec Editor**, **Circuit Designer**, and the **AI Assistant** identified critical defects where:
1. **The Specification Save Boundary is bypassed**: AI proposals accepted in Circuit Designer for source-bound circuits mutate in-memory state but are never committed back to the `.spec` package.
2. **Decoupled design principles are violated**: Hardcoded network addresses, domain gate libraries, and SystemVerilog synthesis logic are embedded directly into frontend and assistant tool wrappers.
3. **Documented contracts diverge from code**: Documented review cycles, proposal previews, and multi-tool contributions do not reflect actual runtime behavior.

This document serves as an actionable specification for loading and executing fixes.

---

## 2. Issue Index

| ID | Title | Severity | Component(s) | Primary File(s) |
|---|---|---|---|---|
| **ISSUE-CD-01** | Source-bound Circuit proposals bypass Spec save boundary on Accept | **Critical** | Circuit Service, Circuit UI | `circuit-designer/packages/service/src/session-backend.ts`, `server.ts` |
| **ISSUE-CD-02** | Circuit AI proposal preview ignores IP-XACT / Spec-level constraints | **High** | Circuit Service, AI Assistant | `circuit-designer/packages/service/src/server.ts`, `ai-assistant/src/tools.ts` |
| **ISSUE-CD-03** | Severed feedback loop in Circuit Designer proposal review lifecycle | **High** | AI Assistant, Circuit Service | `ai-assistant/src/index.ts`, `circuit-designer/packages/service/src/server.ts` |
| **ISSUE-CD-04** | Hardcoded loopback ports and URLs in Circuit Designer standalone launch | **Medium** | Circuit Standalone App | `circuit-designer/apps/standalone/src/App.tsx` |
| **ISSUE-CD-05** | Single primary tool hardcoding in Circuit Designer menu shell | **Medium** | Circuit React Shell | `circuit-designer/packages/app-react/src/CircuitMenuBar.tsx`, `App.tsx` |
| **ISSUE-AI-01** | Logic gate implementations and SystemVerilog synthesis leaked into Assistant | **High** | AI Assistant Tools | `ai-assistant/src/tools.ts` |
| **ISSUE-AI-02** | Schema duplication and split semantic validation rules | **Medium** | AI Assistant Schemas | `ai-assistant/src/operation-schemas.ts`, `assistant.py` |
| **ISSUE-AI-03** | Unbound session persona ignores Circuit Designer | **Low** | AI Assistant Host | `ai-assistant/src/index.ts` |
| **ISSUE-AI-04** | Interactive parameter clarification form restricted to Spec components | **Medium** | AI Assistant Tools | `ai-assistant/src/tools.ts` |

---

## 3. Detailed Issue Specifications & Remediation Plans

### ISSUE-CD-01: Source-bound Circuit proposals bypass Spec save boundary on Accept

* **Severity:** **Critical** (Data loss, state corruption)
* **Components:** Circuit Service (`service`), Circuit React App (`app-react`)
* **Relevant Files:**
  * [`circuit-designer/packages/service/src/session-backend.ts`](file:///home/ankdesh/explore/spec2gds/circuit-designer/packages/service/src/session-backend.ts#L332-L365)
  * [`circuit-designer/packages/service/src/server.ts`](file:///home/ankdesh/explore/spec2gds/circuit-designer/packages/service/src/server.ts#L452-L461)
  * [`circuit-designer/packages/app-react/src/App.tsx`](file:///home/ankdesh/explore/spec2gds/circuit-designer/packages/app-react/src/App.tsx#L863-L872)
* **Documented Intent:**  
  [spec-circuit-integration-architecture.md](file:///home/ankdesh/explore/spec2gds/docs/spec-circuit-integration-architecture.md#L7-L12) establishes:
  > *"Spec Editor owns the saved design. Circuit Designer edits a temporary projection of that design. The `.spec` package is the durable source of truth... A Circuit save is complete only after the Spec API accepts and saves the change."*
* **Observed Defect:**  
  When an AI Assistant proposal is sent to Circuit Designer, it arrives at `POST /documents/{id}/proposals`. When the user accepts it in the "Review proposals" modal, `decideProposal` invokes:
  ```typescript
  // session-backend.ts line 345
  if (decision === "accept") {
    if (proposal.batch) result = await this.commit(documentId, proposal.batch);
  }
  ```
  `this.commit` applies changes **only in-memory** to `record.snapshot` in `SessionBackend`. It completely bypasses `StoredSourceBinding` and `SourceProvider`.
  * The `.spec` package is never written.
  * No `source.changed` event is emitted.
  * Spec Editor is never notified.
  * Circuit Designer is not put into edit mode (no lease, no dirty draft), so the "Save to Specification" action is disabled.
  * A page refresh or backend restart discards the accepted changes completely.
* **Remediation Plan:**
  1. In `server.ts` (`proposalRoute`), inspect whether `this.sourceBindings.get(documentId)` exists.
  2. If the document is source-bound and `decision === "accept"`:
     * Evaluate the batch to generate the candidate `CircuitDocument`.
     * Submit candidate to `stored.provider.preview` and then `stored.provider.commit` (invoking Spec API `POST /circuit-designer/source/commit`).
     * Replace the in-memory session with the authoritative re-projection returned by Spec API.
     * Emit `proposal.changed` and return the updated snapshot.
  3. If not source-bound (standalone `.circuit.json`), preserve the existing in-memory commit behavior.

---

### ISSUE-CD-02: Circuit AI proposal preview ignores IP-XACT / Spec-level constraints

* **Severity:** **High** (False positive preview)
* **Components:** Circuit Service (`service`), AI Assistant (`ai-assistant`)
* **Relevant Files:**
  * [`circuit-designer/packages/service/src/server.ts`](file:///home/ankdesh/explore/spec2gds/circuit-designer/packages/service/src/server.ts#L203-L207)
  * [`ai-assistant/src/tools.ts`](file:///home/ankdesh/explore/spec2gds/ai-assistant/src/tools.ts#L463)
* **Documented Intent:**  
  [circuit-designer-spec-sync.md](file:///home/ankdesh/explore/spec2gds/docs/circuit-designer-spec-sync.md#L83-L96) requires that changes to projected circuits preserve omitted interfaces and validate against the underlying IP-XACT schema.
* **Observed Defect:**  
  When `prepare_circuit_proposal` calls `POST /documents/{id}/operations/preview`, `server.ts` forwards directly to `this.backend.preview(documentId, batch)`. This only checks Circuit schema constraints (e.g. net connectivity). It does not validate against `SourceProvider` (`POST /circuit-designer/source/preview`).
  The AI Assistant shows a green "ready" review for proposals that violate IP-XACT rules (e.g., deleting instances with omitted interface connections or altering port widths used in symbolic slices).
* **Remediation Plan:**
  1. In `server.ts`, update `POST /documents/{id}/operations/preview` to check for an active `StoredSourceBinding`.
  2. If present, evaluate candidate document and delegate preview to `stored.provider.preview(stored.binding, batch.request_id, candidate)`.
  3. Merge any source diagnostics (with source line/entity details) into the preview response returned to the AI Assistant.

---

### ISSUE-CD-03: Severed feedback loop in Circuit Designer proposal review lifecycle

* **Severity:** **High** (Incorrect workflow state)
* **Components:** AI Assistant Host, Circuit Service
* **Relevant Files:**
  * [`ai-assistant/src/index.ts`](file:///home/ankdesh/explore/spec2gds/ai-assistant/src/index.ts#L457-L482)
  * [`ai-assistant/src/index.ts`](file:///home/ankdesh/explore/spec2gds/ai-assistant/src/index.ts#L501-L535)
  * [`circuit-designer/packages/service/src/server.ts`](file:///home/ankdesh/explore/spec2gds/circuit-designer/packages/service/src/server.ts#L452-L461)
* **Documented Intent:**  
  [ai-assistant.md](file:///home/ankdesh/explore/spec2gds/docs/ai-assistant.md#L103-L107) defines proposal review as an explicit human decision that drives workflow completion or cancellation.
* **Observed Defect:**  
  When a user clicks "Send to Circuit Designer" in the AI Assistant:
  1. Review state is marked `sent` in SQLite.
  2. In `settleReviewedWorkflow`, the workflow treats `sent` as terminal completion (`if (review.state !== "applied" && review.state !== "sent") return;`).
  3. The Assistant workflow completes immediately—before the designer has even opened Circuit Designer or reviewed the proposal.
  4. If the designer clicks "Reject" in Circuit Designer, the Assistant review card remains permanently `sent` with no indication of rejection.
* **Remediation Plan:**
  1. Extend Circuit service's proposal decision endpoint (`POST /documents/{id}/proposals/{proposalId}/decision`) to notify the Assistant or maintain a queryable decision status.
  2. Add a reconcile/sync step in `ai-assistant` that checks `GET /documents/{id}/proposals` to detect whether a proposal was `accepted`, `rejected`, or remains `pending`.
  3. In `settleReviewedWorkflow`, do not complete the workflow on `sent`; keep it in `awaiting-user-completion` until Circuit Designer confirms acceptance.

---

### ISSUE-CD-04: Hardcoded loopback ports and URLs in Circuit Designer standalone launch

* **Severity:** **Medium** (Portability and environment breakage)
* **Components:** Circuit Designer Standalone App (`apps/standalone`)
* **Relevant Files:**
  * [`circuit-designer/apps/standalone/src/App.tsx`](file:///home/ankdesh/explore/spec2gds/circuit-designer/apps/standalone/src/App.tsx#L26-L36)
* **Documented Intent:**  
  [service-configuration.md](file:///home/ankdesh/explore/spec2gds/docs/service-configuration.md#L79-L97) specifies that services must honor configured URLs and allowlists derived from `services.json` and environment variables (`CIRCUIT_DESIGNER_SERVICE_URL`, `AI_ASSISTANT_URL`).
* **Observed Defect:**  
  Lines 31-33 in `apps/standalone/src/App.tsx` hardcode:
  ```typescript
  const host = window.location.hostname;
  const target = assistantUrl(`http://${host}:6013`, `http://${host}:6011/api/circuit-designer/v1`, snapshot.document.document_id);
  ```
  This breaks in any environment with non-default ports, HTTPS termination, containerized setups, or reverse proxies.
* **Remediation Plan:**
  1. Support `import.meta.env.VITE_AI_ASSISTANT_UI_URL` and `import.meta.env.VITE_CIRCUIT_DESIGNER_API_BASE` in `apps/standalone`.
  2. On initial mount, query the backend's `/services` or `/capabilities` endpoint to resolve the canonical UI and API URLs for `ai_assistant` and `circuit_designer`.
  3. Fall back to window location origin with default relative paths rather than hardcoding port `6013` and `6011`.

---

### ISSUE-CD-05: Single primary tool hardcoding in Circuit Designer menu shell

* **Severity:** **Medium** (Extensibility defect)
* **Components:** Circuit React Shell (`circuit-app-react`)
* **Relevant Files:**
  * [`circuit-designer/packages/app-react/src/App.tsx`](file:///home/ankdesh/explore/spec2gds/circuit-designer/packages/app-react/src/App.tsx#L874-L880)
  * [`circuit-designer/packages/app-react/src/CircuitMenuBar.tsx`](file:///home/ankdesh/explore/spec2gds/circuit-designer/packages/app-react/src/CircuitMenuBar.tsx#L20)
* **Documented Intent:**  
  `CircuitDesignerApp` accepts an array of tool contributions: `tools?: CircuitToolContribution[]`.
* **Observed Defect:**  
  `CircuitMenuBar` only renders one tool entry (`action("run-primary-tool")`) with label `toolLabel` (`tools[0]?.label`).
  In `App.tsx`:
  ```typescript
  function runPrimaryTool(): void {
    const tool = tools[0];
    ...
  }
  ```
  Any additional tools passed in the `tools` array (`tools[1]`, etc.) are completely omitted from the UI and cannot be executed.
* **Remediation Plan:**
  1. Update `CircuitMenuBar.tsx` to dynamically map all entries in `tools` into the "Tools" dropdown menu.
  2. Pass `onRunTool: (toolId: string) => void` down from `App.tsx` to execute any matching contribution by ID.

---

### ISSUE-AI-01: Logic gate implementations and SystemVerilog synthesis leaked into Assistant

* **Severity:** **High** (Architectural coupling violation)
* **Components:** AI Assistant Host (`ai-assistant`)
* **Relevant Files:**
  * [`ai-assistant/src/tools.ts`](file:///home/ankdesh/explore/spec2gds/ai-assistant/src/tools.ts#L54-L81)
  * [`ai-assistant/src/tools.ts`](file:///home/ankdesh/explore/spec2gds/ai-assistant/src/tools.ts#L135-L173)
* **Documented Intent:**  
  [ai-assistant.md](file:///home/ankdesh/explore/spec2gds/docs/ai-assistant.md#L12-L19) states that the assistant is an orchestration client that passes typed JSON operations to owner backends.
* **Observed Defect:**  
  1. `componentDefaults` in `tools.ts` contains a hardcoded lookup table of elementary logic gates (`xnor`, `nand`, `nor`, `xor`, `and`, `or`, `not`, `buffer`) with pre-canned pinouts and behavioral expressions.
  2. `applyConfirmedComponentDetails` parses strings for `"Continue the pending design proposal using these user-confirmed values:"`, synthesizes `assign` expressions, calculates port bit ranges (`${width - 1}:0`), and generates SystemVerilog module content in TypeScript.
* **Remediation Plan:**
  1. Remove hardcoded gate tables from `ai-assistant/src/tools.ts`.
  2. Standardize the schema for component creation so that default ports and behavioral RTL are generated directly by the LLM or delegated to the Spec API's template/component creation endpoint.
  3. Replace brittle string-prefix parsing (`CONFIRMED_COMPONENT_PREFIX`) with structured tool parameter passing.

---

### ISSUE-AI-02: Schema duplication and split semantic validation rules

* **Severity:** **Medium** (Maintenance hazard)
* **Components:** AI Assistant Schemas, Spec API (`spec2gds`)
* **Relevant Files:**
  * [`ai-assistant/src/operation-schemas.ts`](file:///home/ankdesh/explore/spec2gds/ai-assistant/src/operation-schemas.ts)
  * [`spec2gds/agent_spec/spec_format/assistant.py`](file:///home/ankdesh/explore/spec2gds/spec2gds/agent_spec/spec_format/assistant.py)
* **Documented Intent:**  
  Spec Editor and Circuit Designer own semantic validity; the assistant validates envelope structure and review metadata.
* **Observed Defect:**  
  Full operation schemas (e.g. `create_entity`, `upsert_connection`, `circuitEndpoint`, `circuitTerminal`) are manually duplicated in TypeScript Schemastery definitions in `ai-assistant`. Semantic checks (such as verifying at least 2 endpoints for ad-hoc connections) are enforced in both `operation-schemas.ts` and `assistant.py`.
* **Remediation Plan:**
  1. Generate TypeScript schemas from shared JSON Schema definitions or export them from the Python/TypeScript backends during build.
  2. Treat owner preview as the single source of truth for semantic validity, keeping the assistant tool schema focused on structural argument validation.

---

### ISSUE-AI-03: Unbound session persona ignores Circuit Designer

* **Severity:** **Low** (Prompt / UX defect)
* **Components:** AI Assistant Prompt System
* **Relevant Files:**
  * [`ai-assistant/src/index.ts`](file:///home/ankdesh/explore/spec2gds/ai-assistant/src/index.ts#L242-L245)
* **Documented Intent:**  
  Unbound conversations provide a general fail-closed landing state when no design is bound, prompting the user to select any valid design source.
* **Observed Defect:**  
  The system prompt states:
  ```typescript
  text: `This conversation is not bound to a Spec Editor design source.
  Do not answer questions about a document, component, design, or requested edit. Do not claim that work was completed and do not create a goal.
  Tell the user to start a new conversation and choose a Spec Editor document or entity.`
  ```
  It ignores Circuit Designer completely.
* **Remediation Plan:**
  Update the unbound prompt text in `index.ts` to instruct the user to select either a **Spec Editor document/entity** or a **Circuit Designer document**.

---

### ISSUE-AI-04: Interactive parameter clarification form restricted to Spec components

* **Severity:** **Medium** (Feature asymmetry)
* **Components:** AI Assistant Client and Tools
* **Relevant Files:**
  * [`ai-assistant/src/tools.ts`](file:///home/ankdesh/explore/spec2gds/ai-assistant/src/tools.ts#L84-L112)
  * [`ai-assistant/client/index.js`](file:///home/ankdesh/explore/spec2gds/ai-assistant/client/index.js#L346-L374)
* **Documented Intent:**  
  [ai-assistant.md](file:///home/ankdesh/explore/spec2gds/docs/ai-assistant.md#L110-L123) describes persistent product details cards that prompt for missing values with request-derived defaults before generating a proposal.
* **Observed Defect:**  
  In `tools.ts`, `proposalInputRequest` is guarded by:
  ```typescript
  const component = binding.domain === "spec" && binding.scope === "document" && /component|gate/i.test(`${reason} ${context}`);
  ```
  It is only enabled for Spec component creation. Circuit Designer has no interactive parameter form support and immediately returns an error or unsupported request.
* **Remediation Plan:**
  1. Generalize `proposalInputRequest` to accept field definitions for any domain when `supported=false` and `required_fields` are provided by the model.
  2. Implement Circuit-specific parameter prompts (e.g., component label, terminal directions, net names) using the same UI card.

---

## 4. Verification and Testing Checklist

When implementing fixes for the issues above, verify each item using the following procedures:

- [ ] **ISSUE-CD-01 Verification:**
  - Launch Circuit Designer from Spec Editor (`POST /circuit-designer/launch`).
  - Open AI Assistant bound to the circuit (`/launch/circuit`).
  - Request adding a net and two instances. Send proposal to Circuit Designer.
  - In Circuit Designer, click **Accept**.
  - Verify that Spec API's `/circuit-designer/source/commit` is called and `.spec` package hash changes.
  - Verify that Spec Editor receives `source.changed` and updates automatically.
  - Reload Circuit Designer page and verify accepted changes persist.

- [ ] **ISSUE-CD-02 Verification:**
  - Request an invalid IP-XACT edit in a source-bound circuit (e.g. removing an instance bound to an omitted bus interface).
  - Verify `operations/preview` forwards to Spec preview and returns an error diagnostic rather than passing cleanly.

- [ ] **ISSUE-CD-03 Verification:**
  - Send a proposal to Circuit Designer. Verify AI Assistant review state is `sent` and workflow remains non-terminal.
  - Reject the proposal in Circuit Designer. Verify AI Assistant updates to `rejected` or indicates rejection.

- [ ] **ISSUE-CD-04 Verification:**
  - Start Circuit Designer and AI Assistant on non-default ports (`CIRCUIT_DESIGNER_PORT=7011`, `ASSISTANT_PORT=7013`).
  - Click **Tools → AI Assistant** in Circuit Designer.
  - Verify it connects to port `7013` without connection errors.

- [ ] **ISSUE-AI-01 & ISSUE-AI-04 Verification:**
  - Ask the assistant to create a component with ambiguous parameters.
  - Verify the details card renders in both Spec and Circuit domains and submits structured parameters without relying on hardcoded gate maps.
