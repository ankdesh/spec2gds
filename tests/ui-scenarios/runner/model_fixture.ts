/** Deterministic OpenAI-compatible provider using the real assistant transport. */
import { createServer } from "node:http";
import { once } from "node:events";

function content(message: any): string {
  return typeof message.content === "string" ? message.content
    : Array.isArray(message.content) ? message.content.map((part: any) => part.text ?? "").join("") : "";
}

export function parseToolOutputs(messages: any[]): any[] {
  const calls = new Map(messages.flatMap(message => (message.tool_calls || []).map((call: any) => [call.id, call.function.name])));
  return messages.filter(message => message.role === "tool").map(message => {
    const name = calls.get(message.tool_call_id) || "unknown tool";
    let result: any;
    try { result = JSON.parse(content(message)); }
    catch { throw new Error(`Malformed structured output from ${name} (${message.tool_call_id || "unknown call"}).`); }
    if (!result || typeof result !== "object" || Array.isArray(result)) throw new Error(`Invalid structured output from ${name}.`);
    if (["prepare_spec_proposal", "prepare_circuit_proposal"].includes(String(name)) && !result.review && !result.error && !result.required_input
      && !(typeof result.proposal_id === "string" && ["ready", "applied", "rejected", "stale", "reconcile", "sent", "discarded"].includes(result.state))) {
      throw new Error(`Missing proposal outcome from ${name}.`);
    }
    return result;
  });
}

export function componentDescription(large = false): string {
  return "Combinational IRQ replicates clk & rst_n into eight bits.\nThere is no clocked state or reset sequence; inputs act as logical values."
    + (large ? "\nDetailed interface explanation. ".repeat(2400) + "\nLarge proposal complete." : "");
}

export async function modelFixture(documentId: string, options: { title?: string; largeProposal?: boolean; presentation?: boolean } = {}) {
  const requests: any[] = [];
  const failures: string[] = [];
  const fail = (response: any, error: unknown) => {
    const failure = String(error); failures.push(failure);
    response.writeHead(200, { "Content-Type": "text/event-stream" });
    response.end(`data: ${JSON.stringify({ id: "fixture-failure", object: "chat.completion.chunk", created: 1, model: "gpt-4o-mini", choices: [{ index: 0, delta: { role: "assistant", content: failure }, finish_reason: "stop" }] })}\n\ndata: [DONE]\n\n`);
  };
  const server = createServer(async (request, response) => {
    try {
      let raw = ""; for await (const chunk of request) raw += chunk;
      const body = JSON.parse(raw); requests.push(body);
      const messages: any[] = body.messages;
      const latestUser = messages.findLastIndex(message => message.role === "user");
      const turn = messages.slice(latestUser + 1);
      let outputs: any[];
      try { outputs = parseToolOutputs([...messages.slice(0, latestUser + 1).filter(message => message.role === "assistant"), ...turn]); }
      catch (error) {
        fail(response, error);
        return;
      }
      const contextPages = outputs.filter(output => output.authoritative_context).map(output => output.authoritative_context);
      const context = contextPages.at(-1);
      const materialized: any = {};
      for (const page of contextPages) for (const record of page.records || []) {
        let node = materialized;
        for (let index=0; index<record.path.length-1; index++) {
          const key = record.path[index];
          node = node[key] ??= typeof record.path[index+1] === "number" ? [] : {};
        }
        const key = record.path.at(-1);
        node[key] = record.offset === undefined || record.offset === 0 ? record.value : String(node[key] || "") + record.value;
      }
      const component = (materialized.entities || []).map((item: any) => item.entity).find((item: any) => item.vlnv === "spec2gds.local:work:timer_core:1.0")
        || context?.available_references?.components?.find((item: any) => item.vlnv === "spec2gds.local:work:timer_core:1.0");
      const hasBoundTools = body.tools?.some((tool: any) => tool.function?.name === "get_bound_context");
      const userText = content(messages[latestUser]);
      let decision: any = {};
      if (userText.trim().startsWith("{")) {
        try { decision = JSON.parse(userText); } catch { /* Ordinary designer text can start with a brace. */ }
      }
      const architectureId = decision.decision === "approved" ? decision.architecture_review_id
        : /Approved architecture_review_id: ([^\n]+)/.exec(userText)?.[1];
      let name: string | undefined;
      let args: any = {};
      const outcome = outputs.find(output => output.review || typeof output.proposal_id === "string");
      const outcomeState = outcome?.state || outcome?.review?.state;
      let text = outcomeState === "applied" ? "Saved refinement completed."
        : outcomeState === "ready" ? "The proposal is ready for review."
        : outputs.some(output => output.error) ? "The proposal could not be prepared. Inspect the reported error."
        : "Inspect the proposal result before continuing.";
      const width = component ? 16 : 8;
      const architecture = { title: `${options.presentation ? "IRQ pipeline" : "Timer"} architecture (${width} bits)`,
        components: [{ name: "timer_core", purpose: "Replicate the logical conjunction of clk and rst_n" }], designs: options.presentation ? [{ name: "irq_pipeline", purpose: "Connect two instances through bit zero of the first IRQ output" }] : [],
        interfaces: [{ name: "clk", direction: "in", width: 1 }, { name: "rst_n", direction: "in", width: 1 }, { name: "irq", direction: "out", width }],
        clocks_resets: ["Inputs are used as combinational values, with no stored state."],
        decomposition_rationale: options.presentation ? "Reuse one combinational Component in two connected stages." : "Keep this cohesive combinational leaf unified.", assumptions: [], open_questions: [], concrete_configuration: { width, ...(options.presentation ? { stages: 2, connection: "stage_a.irq[0] → stage_b.clk" } : {}) } };
      if (!hasBoundTools) {
        if (outputs.some(output => output.architecture_review)) text = "Review the architecture card before creating contents.";
        else if (outputs.some(output => output.creation_error)) text = "Spec creation failed. Inspect the reported error.";
        else if (outputs.some(output => output.source_creation)) text = "The Spec creation result is available in its card.";
        else if (!architectureId) { name = "prepare_architecture_review"; args = architecture; }
        else { name = "prepare_spec_document_creation"; args = { document_id: documentId, title: options.title || "Iterative scenario", architecture_review_id: architectureId }; }
      } else if (!context) name = "get_bound_context";
      else if (context.incomplete) { name = "get_bound_context"; args = { cursor: context.next_cursor }; }
      else if (outputs.some(output => output.architecture_review)) text = "Review the architecture card before creating contents.";
      else if (!architectureId) { name = "prepare_architecture_review"; args = architecture; }
      else if (!outputs.some(output => output.review || (typeof output.proposal_id === "string" && typeof output.state === "string") || output.required_input || output.error)) {
        const operations = component ? [
          { operation_id: "port", type: "upsert_component_port", component: component.ref, port: { name: "irq", family: "wire", direction: "out", range: "15:0" } },
          { operation_id: "section", type: "upsert_entity_section", owner: component.ref, section_type: "sv", type_version: 1, payload: { content: "assign irq = {16{clk & rst_n}};" } },
        ] : [{ operation_id: "create", type: "create_entity", kind: "component", name: "timer_core", entity_id: "local_timer", instances: [],
          ports: [{ name: "clk", family: "wire", direction: "in" }, { name: "rst_n", family: "wire", direction: "in" }, { name: "irq", family: "wire", direction: "out", range: "7:0" }],
          systemverilog: "assign irq = {8{clk & rst_n}};" },
          { operation_id: "explain", type: "set_entity_metadata", entity: { document_id: context.document_id, entity_id: "local_timer", entity_kind: "component" },
            description: componentDescription(options.largeProposal), ...(options.presentation ? { display_name: "IRQ logic" } : {}) }];
        if (options.presentation && component) operations.push({ operation_id: "refine-explanation", type: "set_entity_metadata", entity: component.ref,
          description: "Combinational IRQ replicates clk & rst_n into sixteen bits. There is no clocked state or reset sequence; inputs act as logical values." } as any);
        if (options.presentation && !component) {
          const design = { document_id: context.document_id, entity_id: "local_pipeline", entity_kind: "design" };
          operations.push({ operation_id: "pipeline", type: "create_entity", kind: "design", name: "irq_pipeline", entity_id: "local_pipeline", entry_design: true,
            instances: [{ name: "stage_a", component_vlnv: "spec2gds.local:work:timer_core:1.0" }, { name: "stage_b", component_vlnv: "spec2gds.local:work:timer_core:1.0" }] } as any,
            { operation_id: "pipeline-link", type: "upsert_connection", design, connection: { name: "irq_bit_zero", kind: "ad_hoc",
              port_endpoints: [{ instance_name: "stage_a", port_name: "irq", slice: { lsb: 0, width: 1 } }, { instance_name: "stage_b", port_name: "clk" }] } } as any,
            { operation_id: "pipeline-description", type: "set_entity_metadata", entity: design, display_name: "IRQ pipeline", description: "Two instances of IRQ logic form a combinational path. The first IRQ output bit drives the second logical input." } as any);
        }
        name = "prepare_spec_proposal";
        args = { supported: true, base_source_revision_hash: context.source_revision_hash, unsupported_reason: null,
          title: component ? "Refine timer" : "Create timer", summary: `Timer irq width ${width}`, rationale: "Requested iterative refinement", assumptions: [], operations,
          architecture_review_id: architectureId };
      }
      const delta = name ? { tool_calls: [{ index: 0, id: `fixture_${requests.length}`, type: "function", function: { name, arguments: JSON.stringify(args) } }] } : { content: text };
      response.writeHead(200, { "Content-Type": "text/event-stream" });
      for (const [index, value] of [{ role: "assistant" }, delta, {}].entries()) {
        response.write(`data: ${JSON.stringify({ id: "fixture", object: "chat.completion.chunk", created: 1, model: "gpt-4o-mini", choices: [{ index: 0, delta: value, finish_reason: index === 2 ? name ? "tool_calls" : "stop" : null }] })}\n\n`);
      }
      response.end("data: [DONE]\n\n");
    } catch (error) { fail(response, error); }
  });
  server.listen(0, "127.0.0.1"); await once(server, "listening");
  const address = server.address(); if (!address || typeof address === "string") throw new Error("Fixture address missing");
  return { url: `http://127.0.0.1:${address.port}/v1`, requests, failures,
    close: () => new Promise<void>(resolve => { server.closeAllConnections(); server.close(() => resolve()); }) };
}
