# SystemVerilog language examples

These standalone modules illustrate language constructs; they are not bundled
Activity output or evidence of Activity feature support. Test each fenced block
independently, except `two_bit_mux`, which also needs the first gate-based `mux`.
Spec Editor stores interfaces separately and accepts only SystemVerilog Section
content as module bodies; do not paste a full module into an SV Section.
Symbolic port ranges use stored Component parameters and local SV constants
through the shared interface resolver. The examples do not establish support
for parameterized topology; check the [RTL Activity profile](rtl-generation.md).
See [maintained RTL semantics and generation guide](rtl-generation.md) for source packages.

The parameterized examples use their shown defaults. The shift register requires
`N >= 2`; the register files require power-of-two `SIZE >= 2`. The dual-port RAM
reads the previous contents on each edge and gives port 0 priority for simultaneous
writes to one address.

## Simple mux using inbuilt gates

```verilog
module mux(
    input   logic a, b, sel,
    output  logic f
);
    logic n_sel, f1, f2;

    and g1(f1, a, n_sel);
    and g2 (f2, b, sel) ;
    or g3(f, f1, f2 );
    not g4(n_sel, sel);
endmodule
```

### Reuse that mux

```verilog
module two_bit_mux(
    input   logic [1:0] a, b,
    input   logic [0:0] sel,
    output  logic [1:0] f
);
mux mux_1(.f(f[0]), .a(a[0]), .b(b[0]), .sel);
mux mux_2(.f(f[1]), .a(a[1]), .b(b[1]), .sel);
endmodule
```

## Localparam and parameter

```verilog
module n_bit_or #(
    parameter N = 32
)(
    input   logic [N - 1:0] a,
    input   logic [N - 1:0] b,
    output  logic [N - 1:0] res
);
assign res = a | b;
endmodule
```

## Operators

### Conditional operator

```verilog
module mux(
    input   logic a, b, sel,
    output  logic f
);
assign f = sel ? b : a;
endmodule
```

### Bitwise operator

```verilog
module arithmetic(
    input   logic a, b,
    input   logic [4:0] c, d,
    output  logic res
);
logic e, f, g;
assign e = a | b;
assign f = ^a & b;
assign g = e ^ f;

logic [4:0] h;
assign h = c + d;
assign res = &h | g;

endmodule
```

### Concatenate and broadcast
```verilog
module sign_ext(
    input   logic [15:0] in,
    output  logic [31:0] out
);
assign out = {{16{in[15]}} , in};
endmodule
```

## Generate block
```verilog
module eq_n#(
    parameter N =4
)(
    input   logic [N-1:0] a, b,
    output  logic eq
);
logic [N-1:0] tmp;
generate
    genvar i;
    for (i = 0; i < N; i = i + 1)
        xnor gen_u(tmp[i], a[i], b[i]);
endgenerate
assign eq = &tmp;
endmodule
```

## Combinational block

```verilog
module add_or_sub#(
    parameter N = 4
)(
    input   logic [N-1:0] x, y,
    input   logic add,
    output  logic [N-1:0] z
);
always_comb begin
    if (add)
        z = x + y;
    else
        z = x - y;
end
endmodule
```

## Case block

```verilog
module mux4_1#(
    parameter N = 2
)(
    input   logic [N-1:0] a, b, c, d,
    input   logic [1:0] sel,
    output  logic [N-1:0] y
);
always_comb begin
    case (sel)
        2'b00: y = a;
        2'b01: y = b;
        2'b10: y = c;
        2'b11: y = d;
    endcase
end

endmodule
```
### Wildcard case
```verilog
module wild#(
    parameter N = 2
)(
    input   logic [N-1:0] a, b, c, d,
    input   logic [3:0] sel,
    output  logic [N-1:0] y
);
always_comb begin
    casez (sel)
        4'b1???: y = a;
        4'b01??: y = b;
        4'b001?: y = c;
        4'b0001: y = d;
        default: y = 'b0;
    endcase
end

endmodule
```

## Sequential block

```verilog
module d_ff(
    input   logic clk,
    input   logic [0:0] d,
    output  logic [0:0] q
);
always_ff @(posedge clk) begin
    q <= d;
end
endmodule
```

### Reset and Enable signals

```verilog
module d_ff_en(
    input   logic clk, rst, en,
    input   logic d,
    output  logic q
);
always_ff @(posedge clk , posedge rst) begin
    if (rst)
        q <= '0;
    else if (en)
        q <= d;
end

endmodule
```

### Shift register

```verilog
module shift_reg#(
    parameter N = 8
)(
    input   logic clk, rst, s_in,
    input   logic [1:0] ctrl,
    input   logic [N-1:0] d,
    output  logic [N-1:0] q,
    output  logic s_out
);

logic [N-1:0] r_reg, r_next;
// state register
always_ff @( posedge clk, posedge rst) begin
    if (rst)
        r_reg <= '0;
    else
        r_reg <= r_next;
end

// next - state logic
always_comb begin
    unique case (ctrl)
        2'b00 : r_next = r_reg;
        2'b01 : r_next = {s_in, r_reg[N-1:1]};
        2'b10 : r_next = d;
        default: r_next = r_reg;
    endcase
end

// output logic
assign q = r_reg;
assign s_out = r_reg[0];

endmodule
```

## Finite State Machine

```verilog
module edge_detect_moore(
    input   logic clk, rst,
    input   logic in,
    output  logic out
);
typedef enum {s1, s2, s3} state_t;
state_t state_reg, state_next;

always_ff @(posedge clk, posedge rst) begin
    if (rst)
        state_reg <= s1;
    else
        state_reg <= state_next;
end

always_comb begin
    state_next = state_reg;
    out = 1'b0;
    unique case ( state_reg )
        s1 : if (in)
            state_next = s2;
        s2 : begin
            out = 1'b1;
            if (in)
                state_next = s3;
            else
                state_next = s1;
        end
        s3 :
            if (~in)
                state_next = s1;
        default: state_next = s1;
    endcase
end

endmodule
```

## Register file

```verilog
module reg_file #(
    parameter DATA_N = 32,
    parameter SIZE = 32
)(
    input   logic clk, wr_en,
    input   logic [$clog2(SIZE)-1:0] w_addr, r0_addr, r1_addr,
    input   logic [DATA_N-1:0] w_data,
    output  logic [DATA_N-1:0] r0_data, r1_data
);
logic [DATA_N-1:0] regs [0:SIZE-1];
always_ff @(posedge clk) begin
    if (wr_en)
        regs[w_addr] <= w_data;
end

assign r0_data = regs[r0_addr];
assign r1_data = regs[r1_addr];
endmodule
```

### Dual port RAM

```verilog
module dual_port_ram #(
    parameter DATA_N = 32,
    parameter SIZE = 128
)(
    input   logic clk,
    input   logic we0, we1,
    input   logic [$clog2(SIZE)-1:0] addr0, addr1,
    input   logic [DATA_N-1:0] w0_data, w1_data,
    output  logic [DATA_N-1:0] r0_data, r1_data
);
logic [DATA_N-1:0] ram [0:SIZE-1];
always_ff @(posedge clk) begin
    if (we0)
        ram[addr0] <= w0_data;
    // Resolve same-address write collisions explicitly instead of relying on
    // scheduling order between independent procedural blocks.
    if (we1 && !(we0 && addr0 == addr1))
        ram[addr1] <= w1_data;
    r0_data <= ram[addr0];
    r1_data <= ram[addr1];
end

endmodule
```
