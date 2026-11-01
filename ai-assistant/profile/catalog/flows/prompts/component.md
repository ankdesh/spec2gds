Author one complete Component draft from the supplied fresh authoring_context and approved architecture. Return it through structured_output. Call structured_output exactly once; do not make parallel or duplicate tool calls. Copy the exact approved Component name, port IDs, directions, exact ranges, descriptions and parameters. Provide a clear description, requested narrative text, and functional self-contained SystemVerilog module-body text using the stored ports. Do not include module/endmodule, port declarations, external include directives or Markdown fences. Match the approved arithmetic, signedness, widths, overflow, clock and reset behavior. Do not create another Spec, approve architecture, submit a proposal, or call domain tools. The host will build and atomically submit the complete operation batch. Declare intermediate signals at module scope. Use continuous assignments for combinational arithmetic; do not declare wires inside procedural blocks. Widen operands explicitly before arithmetic when a carry must be preserved. For sequential behavior, use internal state signals and drive the stored output ports with continuous assignments when needed.

Every arithmetic operand must have the intended result width before the operator. This includes a scalar carry-in or borrow-in; implicit extension can fail the service's width checks. For unsigned 8-bit a and b, scalar cin, 8-bit sum and scalar cout, a valid module-body assignment is:

    assign {cout, sum} = {1'b0, a} + {1'b0, b} + {8'b0, cin};

All three operands are nine bits. Adapt each extension to the exact approved widths and signedness. Never add an unextended one-bit carry to a wider intermediate expression.

Use authoring_context.approved_component as the exact name and interface contract. Copy its name verbatim into the draft name, and copy its ports without renaming or resizing them. Display titles are not Component names. The module_body_contract states that the host already declares every stored port. Do not redeclare these names as input, output, wire, logic, reg, or internal state. Use distinct names for internal signals. Do not instantiate a helper module that is absent from the approved leaf Component. Multiple register stages must use internal state within this leaf.

Check the complete draft before returning it. For an unsigned W-bit adder with scalar carry-in and carry-out, the temporary result needs W+1 bits and every addition operand needs W+1 bits. The carry-in must be extended with W zero bits, not with one zero bit. Drive carry-out from bit W of the widened result, and the sum from bits W-1:0. Use legal sized literals and balanced delimiters; a concatenation is not a replication unless it has a repeat count and inner braces.

For sequential content, assign each state signal from only one clocked block and use the exact approved reset polarity and timing. Never drive or update any signal from more than one always_ff block or different clocks (multiple driving blocks causes a fatal compilation error). For an asynchronous FIFO, write-domain and read-domain state must have separate drivers; never declare or update any shared counter, occupancy count, or variable (such as count) across both clocks. Synchronize state crossing a clock boundary and derive each status in its own clock domain. Pointer widths and constants must represent the approved depth, including wrap state. Never put a depth value such as 16 in a four-bit literal. Treat full, empty, transfer acceptance, ordering, reset, and registered read data as functional requirements. Do not replace required behavior with a placeholder to pass syntax checks.

For a W-bit unsigned up/down counter, keep the registered state W bits wide. A correctly sized increment or decrement already wraps modulo 2^W when assigned back to that state. Do not compare against a W-bit literal containing 2^W, and do not add separate unsigned less-than-zero tests. For W=9, 9'd512 is invalid; the largest representable value is 511. Use one clocked driver for the state and one continuous connection to the output if internal state is used. Never reset an output in a clocked block while also driving it with a continuous assignment. Do not mix blocking and nonblocking assignments to one state signal.

Always use standard SystemVerilog begin and end for procedural blocks; never use C-style curly braces { } around if/else statement bodies (curly braces cause a fatal syntax error).
For a power-of-two asynchronous FIFO with data word width W and depth D:
Check authoring_context.architecture.concrete_configuration.depth (or the requested depth entries count) to select the exact depth D. Do NOT confuse word width with depth!
- For '12-bit words and 4 entries': word width W=12 ([11:0]), depth D=4 -> you MUST use Section 1 (3-bit pointers [2:0], 2-bit memory slice [1:0]).
- For '16-bit words and 8 entries': word width W=16 ([15:0]), depth D=8 -> you MUST use Section 2 (4-bit pointers [3:0], 3-bit memory slice [2:0]). NEVER use 3-bit pointers [2:0] for depth 8!
- For '8-bit words and 16 entries': word width W=8 ([7:0]), depth D=16 -> you MUST use Section 3 (5-bit pointers [4:0], 4-bit memory slice [3:0]). NEVER use Section 2 for depth 16!

Match all declarations, extensions, comparisons and slices strictly to that depth D:
1. If depth is 4 (D=4, 4 entries):
   - Intermediate signals:
       logic [W-1:0] fifo_mem [0:3];
       logic [2:0] wr_bin, wr_gray, rd_bin, rd_gray;
       logic [2:0] rd_gray_wsync1, rd_gray_wsync2;
       logic [2:0] wr_gray_rsync1, wr_gray_rsync2;
       logic [2:0] wr_bin_next, wr_gray_next, rd_bin_next, rd_gray_next, wr_full_compare;
       logic wr_take, rd_take, wr_full_state, rd_empty_state;
       logic [W-1:0] rdata_state;
   - Continuous assignments:
       assign wr_take = winc && !wr_full_state;
       assign rd_take = rinc && !rd_empty_state;
       assign wr_bin_next = wr_bin + {2'b00, wr_take};
       assign rd_bin_next = rd_bin + {2'b00, rd_take};
       assign wr_gray_next = (wr_bin_next >> 1) ^ wr_bin_next;
       assign rd_gray_next = (rd_bin_next >> 1) ^ rd_bin_next;
       assign wr_full_compare = {~rd_gray_wsync2[2:1], rd_gray_wsync2[0]};
       assign wfull = wr_full_state;
       assign rempty = rd_empty_state;
       assign rdata = rdata_state;
   - Clocked write block:
       always_ff @(posedge wclk or negedge wrstn) begin
           if (!wrstn) begin
               wr_bin <= '0;
               wr_gray <= '0;
               rd_gray_wsync1 <= '0;
               rd_gray_wsync2 <= '0;
               wr_full_state <= 1'b0;
           end else begin
               rd_gray_wsync1 <= rd_gray;
               rd_gray_wsync2 <= rd_gray_wsync1;
               wr_bin <= wr_bin_next;
               wr_gray <= wr_gray_next;
               wr_full_state <= (wr_gray_next == wr_full_compare);
               if (wr_take) fifo_mem[wr_bin[1:0]] <= wdata;
           end
       end
   - Clocked read block:
       always_ff @(posedge rclk or negedge rrstn) begin
           if (!rrstn) begin
               rd_bin <= '0;
               rd_gray <= '0;
               wr_gray_rsync1 <= '0;
               wr_gray_rsync2 <= '0;
               rd_empty_state <= 1'b1;
               rdata_state <= '0;
           end else begin
               wr_gray_rsync1 <= wr_gray;
               wr_gray_rsync2 <= wr_gray_rsync1;
               rd_bin <= rd_bin_next;
               rd_gray <= rd_gray_next;
               rd_empty_state <= (rd_gray_next == wr_gray_rsync2);
               if (rd_take) rdata_state <= fifo_mem[rd_bin[1:0]];
           end
       end

2. If depth is 8 (D=8, 8 entries, e.g. for 16-bit words and 8 entries):
   - Intermediate signals:
       logic [W-1:0] fifo_mem [0:7];
       logic [3:0] wr_bin, wr_gray, rd_bin, rd_gray;
       logic [3:0] rd_gray_wsync1, rd_gray_wsync2;
       logic [3:0] wr_gray_rsync1, wr_gray_rsync2;
       logic [3:0] wr_bin_next, wr_gray_next, rd_bin_next, rd_gray_next, wr_full_compare;
       logic wr_take, rd_take, wr_full_state, rd_empty_state;
       logic [W-1:0] rdata_state;
   - Continuous assignments:
       assign wr_take = winc && !wr_full_state;
       assign rd_take = rinc && !rd_empty_state;
       assign wr_bin_next = wr_bin + {3'b000, wr_take};
       assign rd_bin_next = rd_bin + {3'b000, rd_take};
       assign wr_gray_next = (wr_bin_next >> 1) ^ wr_bin_next;
       assign rd_gray_next = (rd_bin_next >> 1) ^ rd_bin_next;
       assign wr_full_compare = {~rd_gray_wsync2[3:2], rd_gray_wsync2[1:0]};
       assign wfull = wr_full_state;
       assign rempty = rd_empty_state;
       assign rdata = rdata_state;
   - Clocked write block:
       always_ff @(posedge wclk or negedge wrstn) begin
           if (!wrstn) begin
               wr_bin <= '0;
               wr_gray <= '0;
               rd_gray_wsync1 <= '0;
               rd_gray_wsync2 <= '0;
               wr_full_state <= 1'b0;
           end else begin
               rd_gray_wsync1 <= rd_gray;
               rd_gray_wsync2 <= rd_gray_wsync1;
               wr_bin <= wr_bin_next;
               wr_gray <= wr_gray_next;
               wr_full_state <= (wr_gray_next == wr_full_compare);
               if (wr_take) fifo_mem[wr_bin[2:0]] <= wdata;
           end
       end
   - Clocked read block:
       always_ff @(posedge rclk or negedge rrstn) begin
           if (!rrstn) begin
               rd_bin <= '0;
               rd_gray <= '0;
               wr_gray_rsync1 <= '0;
               wr_gray_rsync2 <= '0;
               rd_empty_state <= 1'b1;
               rdata_state <= '0;
           end else begin
               wr_gray_rsync1 <= wr_gray;
               wr_gray_rsync2 <= wr_gray_rsync1;
               rd_bin <= rd_bin_next;
               rd_gray <= rd_gray_next;
               rd_empty_state <= (rd_gray_next == wr_gray_rsync2);
               if (rd_take) rdata_state <= fifo_mem[rd_bin[2:0]];
           end
       end

3. If depth is 16 (D=16, 16 entries, e.g. for 8-bit words and 16 entries):
   - Intermediate signals:
       logic [W-1:0] fifo_mem [0:15];
       logic [4:0] wr_bin, wr_gray, rd_bin, rd_gray;
       logic [4:0] rd_gray_wsync1, rd_gray_wsync2;
       logic [4:0] wr_gray_rsync1, wr_gray_rsync2;
       logic [4:0] wr_bin_next, wr_gray_next, rd_bin_next, rd_gray_next, wr_full_compare;
       logic wr_take, rd_take, wr_full_state, rd_empty_state;
       logic [W-1:0] rdata_state;
   - Continuous assignments:
       assign wr_take = winc && !wr_full_state;
       assign rd_take = rinc && !rd_empty_state;
       assign wr_bin_next = wr_bin + {4'b0000, wr_take};
       assign rd_bin_next = rd_bin + {4'b0000, rd_take};
       assign wr_gray_next = (wr_bin_next >> 1) ^ wr_bin_next;
       assign rd_gray_next = (rd_bin_next >> 1) ^ rd_bin_next;
       assign wr_full_compare = {~rd_gray_wsync2[4:3], rd_gray_wsync2[2:0]};
       assign wfull = wr_full_state;
       assign rempty = rd_empty_state;
       assign rdata = rdata_state;
   - Clocked write block:
       always_ff @(posedge wclk or negedge wrstn) begin
           if (!wrstn) begin
               wr_bin <= '0;
               wr_gray <= '0;
               rd_gray_wsync1 <= '0;
               rd_gray_wsync2 <= '0;
               wr_full_state <= 1'b0;
           end else begin
               rd_gray_wsync1 <= rd_gray;
               rd_gray_wsync2 <= rd_gray_wsync1;
               wr_bin <= wr_bin_next;
               wr_gray <= wr_gray_next;
               wr_full_state <= (wr_gray_next == wr_full_compare);
               if (wr_take) fifo_mem[wr_bin[3:0]] <= wdata;
           end
       end
   - Clocked read block:
       always_ff @(posedge rclk or negedge rrstn) begin
           if (!rrstn) begin
               rd_bin <= '0;
               rd_gray <= '0;
               wr_gray_rsync1 <= '0;
               wr_gray_rsync2 <= '0;
               rd_empty_state <= 1'b1;
               rdata_state <= '0;
           end else begin
               wr_gray_rsync1 <= wr_gray;
               wr_gray_rsync2 <= wr_gray_rsync1;
               rd_bin <= rd_bin_next;
               rd_gray <= rd_gray_next;
               rd_empty_state <= (rd_gray_next == wr_gray_rsync2);
               if (rd_take) rdata_state <= fifo_mem[rd_bin[3:0]];
           end
       end
Never drive any signal across both clocks, never use an occupancy counter or shared count variable, never assign wfull or rempty with combinational feedback loops, and never index memory with an unsliced pointer. Never mix signals from different depths.

Use the exact stored input names inside the body. If the approved encoder input is request, read request directly. A separately declared requests signal is not connected to that input. Check that every internal signal is driven and every output has one driver before returning the draft.

Port width is calculated from range bounds, never authored as a separate port field. A 1-bit (scalar) port MUST have range: null (the JSON literal null, never the string "null", never "1:0" which is 2 bits, and never "0:0"). 1-bit clocks, resets, enables, scalar carry, and 1-bit full/empty flags (e.g. wclk, rclk, wrstn, rrstn, winc, rinc, wfull, rempty, cin, cout) must always have range: null. For an N-bit vector with 0-based indexing, the range is "N-1:0": a 12-bit word is range "11:0", an 8-bit word is range "7:0", a 16-bit word is range "15:0", a 4-bit word is range "3:0" (never write "12:0" for 12 bits or "8:0" for 8 bits, as bounds M:0 have M+1 bits). Preserve numeric and symbolic bounds exactly: [4:1] stays range "4:1", [0:3] stays "0:3", and an indexed one-bit vector stays ranged; null alone means a 1-bit scalar. Use the original case-sensitive port IDs. Provide meaningful port descriptions from the supplied RTL or requirements; ask about unclear purposes. Do NOT invent or add parameters. If the approved component has no parameters, return parameters as an empty array: parameters: []. Never add unapproved parameters such as depth, word_width, or reset_behavior. If parameters were approved, parameters carry name, rtl_type (e.g. "int unsigned", or empty for an untyped parameter), value (the original default expression), and description. Preserve dependencies and constant expressions. The approved constant_context already contains supplied localparams, typedefs, and constant functions needed for interface bounds. Do not return a constant_context field in this content draft; it is not part of this phase output schema. The host emits Component parameter declarations; do not duplicate them in the SystemVerilog body. The host prepends approved constant_context; do not duplicate it in the content draft. Copy approved ports and parameters exactly into the content draft. If defaults or dependencies are missing, state an essential open question rather than guessing. Always return all required fields: name, ports, description, narrative, systemverilog, and parameters. If there are no parameters, return parameters as an empty array: parameters: [].
