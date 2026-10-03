/** Deterministic OpenAI-compatible provider using the real assistant transport. */
import { createServer } from "node:http";
import { once } from "node:events";

function content(message: any): string {
  return typeof message.content === "string" ? message.content
    : Array.isArray(message.content) ? message.content.map((part: any) => part.text ?? "").join("") : "";
}

export async function modelFixture() {
  const requests: any[] = [];
  const server = createServer(async (request, response) => {
    try {
      let raw = ""; for await (const chunk of request) raw += chunk;
      const body = JSON.parse(raw); requests.push(body);
      const messages: any[] = body.messages;
      const latestUser = messages.findLastIndex(message => message.role === "user");
      const turn = messages.slice(latestUser + 1);
      const outputs = turn.filter(message => message.role === "tool").map(message => JSON.parse(content(message)));
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
      if (userText.trim().startsWith("{")) decision = JSON.parse(userText);
      const architectureId = decision.decision === "approved" ? decision.architecture_review_id
        : /Approved architecture_review_id: ([^\n]+)/.exec(userText)?.[1];
      let name: string | undefined;
      let args: any = {};
      let text = "Saved refinement completed.";
      const width = component ? 16 : 8;
      const architecture = { title: `Timer architecture (${width} bits)`,
        components: [{ name: "timer_core", purpose: "Replicate the logical conjunction of clk and rst_n" }], designs: [],
        interfaces: [{ name: "clk", direction: "in", width: 1 }, { name: "rst_n", direction: "in", width: 1 }, { name: "irq", direction: "out", width }],
        clocks_resets: ["Inputs are used as combinational values, with no stored state."],
        decomposition_rationale: "Keep this cohesive combinational leaf unified.", assumptions: [], open_questions: [], concrete_configuration: { width } };
      if (!hasBoundTools) {
        if (outputs.some(output => output.architecture_review)) text = "Review the architecture card before creating contents.";
        else if (outputs.some(output => output.source_creation || output.creation_error)) text = "The specification package is saved and its document chat will continue.";
        else if (!architectureId) { name = "prepare_architecture_review"; args = architecture; }
        else { name = "prepare_spec_document_creation"; args = { title: "Iterative scenario", architecture_review_id: architectureId }; }
      } else if (!context) name = "get_bound_context";
      else if (context.incomplete) { name = "get_bound_context"; args = { cursor: context.next_cursor }; }
      else if (outputs.some(output => output.architecture_review)) text = "Review the architecture card before creating contents.";
      else if (!architectureId) { name = "prepare_architecture_review"; args = architecture; }
      else if (!outputs.some(output => output.review || output.required_input || output.error)) {
        const operations = component ? [
          { operation_id: "port", type: "upsert_component_port", component: component.ref, port: { name: "irq", family: "wire", direction: "out", range: "15:0" } },
          { operation_id: "section", type: "upsert_entity_section", owner: component.ref, section_type: "sv", type_version: 1, payload: { content: "assign irq = {16{clk & rst_n}};" } },
        ] : [{ operation_id: "create", type: "create_entity", kind: "component", name: "timer_core", entity_id: "local_timer", instances: [],
          ports: [{ name: "clk", family: "wire", direction: "in" }, { name: "rst_n", family: "wire", direction: "in" }, { name: "irq", family: "wire", direction: "out", range: "7:0" }],
          systemverilog: "assign irq = {8{clk & rst_n}};" },
          { operation_id: "explain", type: "set_entity_metadata", entity: { document_id: context.document_id, entity_id: "local_timer", entity_kind: "component" },
            description: "Combinational IRQ replicates clk & rst_n into eight bits.\nThere is no clocked state or reset sequence; inputs act as logical values." }];
        name = "prepare_spec_proposal";
        args = { supported: true, base_source_revision_hash: context.source_revision_hash, unsupported_reason: null,
          title: component ? "Refine timer" : "Create timer", summary: `Timer irq width ${width}`, rationale: "Requested iterative refinement", assumptions: [], operations,
          architecture_review_id: architectureId };
      }
      const delta = name ? { tool_calls: [{ index: 0, id: `fixture_${requests.length}`, type: "function", function: { name, arguments: JSON.stringify(args) } }] } : { content: text };
      response.writeHead(200, { "Content-Type": "text/event-stream" });
      for (const [index, value] of [{ role: "assistant" }, delta, {}].entries()) {
        response.write(`data: ${JSON.stringify({ id: "fixture", object: "chat.completion.chunk", created: 1, model: body.model, choices: [{ index: 0, delta: value, finish_reason: index === 2 ? name ? "tool_calls" : "stop" : null }] })}\n\n`);
      }
      response.end("data: [DONE]\n\n");
    } catch (error) { response.writeHead(500); response.end(String(error)); }
  });
  server.listen(0, "127.0.0.1"); await once(server, "listening");
  const address = server.address(); if (!address || typeof address === "string") throw new Error("Fixture address missing");
  return { url: `http://127.0.0.1:${address.port}/v1`, requests,
    close: () => new Promise<void>(resolve => { server.closeAllConnections(); server.close(() => resolve()); }) };
}
