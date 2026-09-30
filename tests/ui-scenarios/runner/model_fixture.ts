/** Deterministic OpenAI-compatible provider using the real assistant transport. */
import { createServer } from "node:http";
import { once } from "node:events";

function content(message: any): string {
  return typeof message.content === "string" ? message.content
    : Array.isArray(message.content) ? message.content.map((part: any) => part.text ?? "").join("") : "";
}

export async function modelFixture(documentId: string) {
  const requests: any[] = [];
  const server = createServer(async (request, response) => {
    try {
      let raw = ""; for await (const chunk of request) raw += chunk;
      const body = JSON.parse(raw); requests.push(body);
      const messages: any[] = body.messages;
      const latestUser = messages.findLastIndex(message => message.role === "user");
      const turn = messages.slice(latestUser + 1);
      const outputs = turn.filter(message => message.role === "tool").map(message => {
        try { return JSON.parse(content(message)); } catch { return {}; }
      });
      const context = outputs.find(output => output.authoritative_context)?.authoritative_context;
      const hasBoundTools = body.tools?.some((tool: any) => tool.function?.name === "get_bound_context");
      let name: string | undefined;
      let args: any = {};
      let text = "Saved refinement completed.";
      if (!hasBoundTools) {
        if (!outputs.some(output => output.source_creation || output.creation_error)) {
          name = "prepare_spec_document_creation"; args = { document_id: documentId, title: "Iterative scenario" };
        } else text = "The specification package is saved and its document chat will continue.";
      } else if (!context) name = "get_bound_context";
      else if (!outputs.some(output => output.review || output.required_input || output.error)) {
        const component = context.available_references?.components?.find((item: any) => item.ref.entity_id === "component_timer_core");
        const width = component ? 16 : 8;
        const operations = component ? [
          { operation_id: "port", type: "upsert_component_port", component: component.ref, port: { name: "irq", family: "wire", direction: "out", range: "15:0" } },
          { operation_id: "section", type: "upsert_entity_section", owner: component.ref, section_type: "sv", type_version: 1, payload: { content: "assign irq = {16{clk & rst_n}};" } },
        ] : [{ operation_id: "create", type: "create_entity", kind: "component", name: "timer_core", entity_id: "component_timer_core", instances: [],
          ports: [{ name: "clk", family: "wire", direction: "in" }, { name: "rst_n", family: "wire", direction: "in" }, { name: "irq", family: "wire", direction: "out", range: "7:0" }],
          systemverilog: "assign irq = {8{clk & rst_n}};" }];
        let confirmation: any = {};
        try {
          const input = JSON.parse(content(messages[latestUser]));
          if (input.kind === "confirmed_proposal_input") confirmation = { confirmed_input_id: input.input_id, confirmed_values: input.values };
        } catch { /* Ordinary natural-language request. */ }
        name = "prepare_spec_proposal";
        args = { supported: true, base_source_revision_hash: context.source_revision_hash, unsupported_reason: null,
          title: component ? "Refine timer" : "Create timer", summary: `Timer irq width ${width}`, rationale: "Requested iterative refinement", assumptions: [], operations,
          required_fields: [{ name: "width", label: "IRQ width", description: "Requested width", default_value: String(width) }], ...confirmation };
      }
      const delta = name ? { tool_calls: [{ index: 0, id: `fixture_${requests.length}`, type: "function", function: { name, arguments: JSON.stringify(args) } }] } : { content: text };
      response.writeHead(200, { "Content-Type": "text/event-stream" });
      for (const [index, value] of [{ role: "assistant" }, delta, {}].entries()) {
        response.write(`data: ${JSON.stringify({ id: "fixture", object: "chat.completion.chunk", created: 1, model: "gpt-4o-mini", choices: [{ index: 0, delta: value, finish_reason: index === 2 ? name ? "tool_calls" : "stop" : null }] })}\n\n`);
      }
      response.end("data: [DONE]\n\n");
    } catch (error) { response.writeHead(500); response.end(String(error)); }
  });
  server.listen(0, "127.0.0.1"); await once(server, "listening");
  const address = server.address(); if (!address || typeof address === "string") throw new Error("Fixture address missing");
  return { url: `http://127.0.0.1:${address.port}/v1`, requests,
    close: () => new Promise<void>(resolve => { server.closeAllConnections(); server.close(() => resolve()); }) };
}
