/** Deterministic OpenAI-compatible provider supporting standard and RTLLM tasks. */
import { createServer } from "node:http";
import { once } from "node:events";
import { existsSync, readFileSync } from "node:fs";

function content(message: any): string {
  return typeof message.content === "string" ? message.content
    : Array.isArray(message.content) ? message.content.map((part: any) => part.text ?? "").join("") : "";
}

function parseJsonSafe(text: string): any {
  const trimmed = text.trim();
  if (!trimmed) return {};
  try {
    return JSON.parse(trimmed);
  } catch (err) {
    const spillMatch = trimmed.match(/stored at: (\/[^\s)]+\.txt)/);
    if (spillMatch && existsSync(spillMatch[1])) {
      try {
        return JSON.parse(readFileSync(spillMatch[1], "utf8"));
      } catch {}
    }
    const omittedIdx = trimmed.indexOf("(Omitted");
    if (omittedIdx !== -1) {
      try {
        return JSON.parse(trimmed.slice(0, omittedIdx).trim());
      } catch {}
    }
    const lastBrace = trimmed.lastIndexOf("}");
    if (lastBrace !== -1) {
      try {
        return JSON.parse(trimmed.slice(0, lastBrace + 1));
      } catch {}
    }
    return {};
  }
}

export async function modelFixture(defaultDocId: string) {
  const requests: any[] = [];
  const server = createServer(async (request, response) => {
    try {
      let raw = ""; for await (const chunk of request) raw += chunk;
      const body = JSON.parse(raw); requests.push(body);
      const messages: any[] = body.messages;
      const latestUser = messages.findLastIndex(message => message.role === "user" && !content(message).startsWith("You are repeating"));
      const userText = latestUser >= 0 ? content(messages[latestUser]) : "";
      const turn = messages.slice(latestUser + 1);
      const outputs = turn.filter(message => message.role === "tool").map(message => parseJsonSafe(content(message)));
      const context = outputs.find(output => output.authoritative_context)?.authoritative_context;
      const hasBoundTools = body.tools?.some((tool: any) => tool.function?.name === "get_bound_context");
      let name: string | undefined;
      let args: any = {};
      let text = "Saved refinement completed.";

      const isFullAdder = /full_adder/i.test(userText) && !/adder_8bit/i.test(userText);
      const isAdder = /adder_8bit/i.test(userText) || (/adder/i.test(defaultDocId) && !isFullAdder);
      const isRam = /dual_port_RAM|fifomem/i.test(userText) && !/asyn_fifo/i.test(userText);
      const isFifo = /asyn_fifo/i.test(userText) || (/fifo/i.test(defaultDocId) && !isRam);
      const isCounter = /up_down_counter/i.test(userText) || /counter/i.test(defaultDocId);

      const targetDocId = (isAdder || isFullAdder) ? "rtllm_adder_8bit" : isCounter ? "rtllm_up_down_counter" : (isFifo || isRam) ? "rtllm_asyn_fifo" : defaultDocId;
      const targetTitle = (isAdder || isFullAdder) ? "8-bit Full Adder" : isCounter ? "16-bit Up Down Counter" : (isFifo || isRam) ? "Asynchronous FIFO" : "Iterative scenario";

      const hasStaleRevision = outputs.some(output => output.error?.error_code === "STALE_REVISION");
      const hasCompletedProposal = outputs.some(output => output.proposal_id || output.state === "applied" || output.review || output.required_input || (output.error && output.error.error_code !== "STALE_REVISION"));

      if (!hasBoundTools) {
        if (!outputs.some(output => output.source_creation || output.creation_error)) {
          name = "prepare_spec_document_creation";
          args = { document_id: targetDocId, title: targetTitle };
        } else {
          text = "The specification package is saved and its document chat will continue.";
        }
      } else if (!context || hasStaleRevision) {
        name = "get_bound_context";
      } else if (!hasCompletedProposal) {
        let operations: any[] = [];
        let proposalTitle = "Create component";
        let proposalSummary = "Add hardware component";

        if (isFullAdder) {
          proposalTitle = "Create 1-bit Full Adder";
          proposalSummary = "1-bit full adder sub-component with inputs a, b, cin and outputs sum, cout";
          operations = [{
            operation_id: "create_full_adder",
            type: "create_entity",
            kind: "component",
            name: "full_adder",
            entity_id: "component_full_adder",
            instances: [],
            ports: [
              { name: "a", family: "wire", direction: "in" },
              { name: "b", family: "wire", direction: "in" },
              { name: "cin", family: "wire", direction: "in" },
              { name: "sum", family: "wire", direction: "out" },
              { name: "cout", family: "wire", direction: "out" },
            ],
            systemverilog: "assign sum = a ^ b ^ cin;\nassign cout = (a & b) | (cin & (a ^ b));",
          }];
        } else if (isAdder) {
          proposalTitle = "Create Hierarchical 8-bit Adder";
          proposalSummary = "8-bit ripple-carry adder instantiating 8 full_adder sub-components";
          operations = [{
            operation_id: "create_adder",
            type: "create_entity",
            kind: "component",
            name: "adder_8bit",
            entity_id: "component_adder_8bit",
            instances: [],
            ports: [
              { name: "a", family: "wire", direction: "in", range: "7:0" },
              { name: "b", family: "wire", direction: "in", range: "7:0" },
              { name: "cin", family: "wire", direction: "in" },
              { name: "sum", family: "wire", direction: "out", range: "7:0" },
              { name: "cout", family: "wire", direction: "out" },
            ],
            systemverilog: `wire [7:0] c;
full_adder fa0 (.a(a[0]), .b(b[0]), .cin(cin), .sum(sum[0]), .cout(c[0]));
full_adder fa1 (.a(a[1]), .b(b[1]), .cin(c[0]), .sum(sum[1]), .cout(c[1]));
full_adder fa2 (.a(a[2]), .b(b[2]), .cin(c[1]), .sum(sum[2]), .cout(c[2]));
full_adder fa3 (.a(a[3]), .b(b[3]), .cin(c[2]), .sum(sum[3]), .cout(c[3]));
full_adder fa4 (.a(a[4]), .b(b[4]), .cin(c[3]), .sum(sum[4]), .cout(c[4]));
full_adder fa5 (.a(a[5]), .b(b[5]), .cin(c[4]), .sum(sum[5]), .cout(c[5]));
full_adder fa6 (.a(a[6]), .b(b[6]), .cin(c[5]), .sum(sum[6]), .cout(c[6]));
full_adder fa7 (.a(a[7]), .b(b[7]), .cin(c[6]), .sum(sum[7]), .cout(cout));`,
          }];
        } else if (isRam) {
          proposalTitle = "Create Dual-Port RAM";
          proposalSummary = "16-entry by 8-bit synchronous RAM sub-component";
          operations = [{
            operation_id: "create_ram",
            type: "create_entity",
            kind: "component",
            name: "dual_port_RAM",
            entity_id: "component_dual_port_RAM",
            instances: [],
            ports: [
              { name: "wclk", family: "wire", direction: "in" },
              { name: "wenc", family: "wire", direction: "in" },
              { name: "waddr", family: "wire", direction: "in", range: "3:0" },
              { name: "wdata", family: "wire", direction: "in", range: "7:0" },
              { name: "rclk", family: "wire", direction: "in" },
              { name: "renc", family: "wire", direction: "in" },
              { name: "raddr", family: "wire", direction: "in", range: "3:0" },
              { name: "rdata", family: "wire", direction: "out", range: "7:0" },
            ],
            systemverilog: `reg [7:0] RAM_MEM [0:15];
always @(posedge wclk) begin
    if (wenc) begin
        RAM_MEM[waddr] <= wdata;
    end
end
always @(posedge rclk) begin
    if (renc) begin
        rdata <= RAM_MEM[raddr];
    end
end`,
          }];
        } else if (isCounter) {
          proposalTitle = "Create Up-Down Counter";
          proposalSummary = "16-bit up-down counter with clk, reset, up_down, and count";
          operations = [{
            operation_id: "create_counter",
            type: "create_entity",
            kind: "component",
            name: "up_down_counter",
            entity_id: "component_up_down_counter",
            instances: [],
            ports: [
              { name: "clk", family: "wire", direction: "in" },
              { name: "reset", family: "wire", direction: "in" },
              { name: "up_down", family: "wire", direction: "in" },
              { name: "count", family: "wire", direction: "out", range: "15:0" },
            ],
            systemverilog: "always @(posedge clk or posedge reset) begin\n    if (reset) begin\n        count <= 16'b0;\n    end else begin\n        if (up_down) begin\n            count <= count + 1'b1;\n        end else begin\n            count <= count - 1'b1;\n        end\n    end\nend",
          }];
        } else if (isFifo) {
          proposalTitle = "Create Hierarchical Asynchronous FIFO";
          proposalSummary = "Dual-clock asynchronous FIFO instantiating dual_port_RAM sub-component";
          operations = [{
            operation_id: "create_fifo",
            type: "create_entity",
            kind: "component",
            name: "asyn_fifo",
            entity_id: "component_asyn_fifo",
            instances: [],
            ports: [
              { name: "wclk", family: "wire", direction: "in" },
              { name: "rclk", family: "wire", direction: "in" },
              { name: "wrstn", family: "wire", direction: "in" },
              { name: "rrstn", family: "wire", direction: "in" },
              { name: "winc", family: "wire", direction: "in" },
              { name: "rinc", family: "wire", direction: "in" },
              { name: "wdata", family: "wire", direction: "in", range: "7:0" },
              { name: "wfull", family: "wire", direction: "out" },
              { name: "rempty", family: "wire", direction: "out" },
              { name: "rdata", family: "wire", direction: "out", range: "7:0" },
            ],
            systemverilog: `reg [4:0] waddr_bin, raddr_bin, wptr, rptr;
wire [4:0] waddr_gray = waddr_bin ^ (waddr_bin >> 1);
wire [4:0] raddr_gray = raddr_bin ^ (raddr_bin >> 1);
reg [4:0] rptr_buff, rptr_syn, wptr_buff, wptr_syn;
assign wfull = (wptr == {~rptr_syn[4:3], rptr_syn[2:0]});
assign rempty = (rptr == wptr_syn);

always @(posedge wclk or negedge wrstn) begin
    if (~wrstn) begin waddr_bin <= 5'd0; wptr <= 5'd0; end
    else if (!wfull && winc) begin waddr_bin <= waddr_bin + 5'd1; wptr <= waddr_gray; end
end
always @(posedge rclk or negedge rrstn) begin
    if (~rrstn) begin raddr_bin <= 5'd0; rptr <= 5'd0; end
    else if (!rempty && rinc) begin raddr_bin <= raddr_bin + 5'd1; rptr <= raddr_gray; end
end
always @(posedge wclk or negedge wrstn) begin
    if (~wrstn) begin rptr_buff <= 5'd0; rptr_syn <= 5'd0; end
    else begin rptr_buff <= rptr; rptr_syn <= rptr_buff; end
end
always @(posedge rclk or negedge rrstn) begin
    if (~rrstn) begin wptr_buff <= 5'd0; wptr_syn <= 5'd0; end
    else begin wptr_buff <= wptr; wptr_syn <= wptr_buff; end
end

wire wen = winc && !wfull;
wire ren = rinc && !rempty;
dual_port_RAM ram_inst (
    .wclk(wclk),
    .wenc(wen),
    .waddr(waddr_bin[3:0]),
    .wdata(wdata),
    .rclk(rclk),
    .renc(ren),
    .raddr(raddr_bin[3:0]),
    .rdata(rdata)
);`,
          }];
        } else {
          // Default timer_core handling
          const component = context.available_references?.components?.find((item: any) => item.ref.entity_id === "component_timer_core");
          const width = component ? 16 : 8;
          proposalTitle = component ? "Refine timer" : "Create timer";
          proposalSummary = `Timer irq width ${width}`;
          operations = component ? [
            { operation_id: "port", type: "upsert_component_port", component: component.ref, port: { name: "irq", family: "wire", direction: "out", range: "15:0" } },
            { operation_id: "section", type: "upsert_entity_section", owner: component.ref, section_type: "sv", type_version: 1, payload: { content: "assign irq = {16{clk & rst_n}};" } },
          ] : [{
            operation_id: "create",
            type: "create_entity",
            kind: "component",
            name: "timer_core",
            entity_id: "component_timer_core",
            instances: [],
            ports: [
              { name: "clk", family: "wire", direction: "in" },
              { name: "rst_n", family: "wire", direction: "in" },
              { name: "irq", family: "wire", direction: "out", range: "7:0" },
            ],
            systemverilog: "assign irq = {8{clk & rst_n}};",
          }];
        }

        let confirmation: any = {};
        try {
          const input = JSON.parse(userText);
          if (input.kind === "confirmed_proposal_input") confirmation = { confirmed_input_id: input.input_id, confirmed_values: input.values };
        } catch { /* Ordinary natural-language request. */ }

        name = "prepare_spec_proposal";
        args = {
          supported: true,
          base_source_revision_hash: context.source_revision_hash,
          unsupported_reason: null,
          title: proposalTitle,
          summary: proposalSummary,
          rationale: "Requested hardware specification creation",
          assumptions: [],
          operations,
          ...confirmation,
        };
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
