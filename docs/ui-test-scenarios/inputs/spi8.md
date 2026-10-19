# Input pack: Eight-bit SPI Mode 0 master

Definition reference: `spi8`. Use this readable Component name: **Eight-bit SPI Mode 0 master**.
The reference is a catalogue alias, not a required service-generated ID or module filename.

## Authoring instructions

Create this Component through Spec Editor. Copy the explanation below into its
text Section. Add each wire port separately using its exact Port ID. Add the
SystemVerilog body to the SystemVerilog Section. Save each authored draft.
Do not enter module headers or redeclare ports. Do not replace this body with
connections in narrative text. Record the actual stable Component ID after creation.

## Complete explanation to copy

```text
Purpose
Perform one full-duplex, eight-bit SPI Mode 0 transfer at a fixed clock division.

Requirements and implemented behavior
R1: CPOL=0 and CPHA=0. On accepted start, lower cs_n, present tx_data[7], and keep sclk low. Each half-period is two clk cycles. R2: Sample miso on each of eight rising SCLK edges. Advance mosi on falling edges. On the final falling edge, raise cs_n, lower busy, publish rx_data, and pulse done. R3: Reset aborts to cs_n=1, sclk=0, mosi=0, busy=0, done=0, rx_data=0.

Interface
The Ports Section defines every physical wire. Port IDs, directions, ranges, and descriptions are part of this contract. All data is unsigned unless this explanation says otherwise.

Timing and reset
All state uses rising clk edges and synchronous active-high reset. Reset has priority over the other controls. Read the requirements above for enable and transfer priorities.

Corner cases and integration assumptions
Requests while busy are ignored, including the completion edge. tx_data is captured on acceptance. rx_data holds between complete transfers. This pack has no multi-byte hold-CS mode, programmable divider, or other SPI mode.

Verification boundary
Review this explanation against the Ports and SystemVerilog Sections. Generate RTL from the saved Component and run the published project lint command. Lint is not functional simulation. Reference examples describe intended behavior; they are not executed test results.
```

## Complete interface

| Port ID | Direction | Range to enter | Bits | Description |
| --- | --- | --- | ---: | --- |
| `clk` | `in` | leave blank (scalar) | 1 | Rising-edge input clock. |
| `reset` | `in` | leave blank (scalar) | 1 | Synchronous active-high reset; highest priority. |
| `start` | `in` | leave blank (scalar) | 1 | Accept a transfer only while idle before the edge. |
| `tx_data` | `in` | `7:0` | 8 | Captured MSB-first transmit byte. |
| `miso` | `in` | leave blank (scalar) | 1 | Serial input sampled on SCLK rising edges. |
| `mosi` | `out` | leave blank (scalar) | 1 | Serial output; zero while idle. |
| `sclk` | `out` | leave blank (scalar) | 1 | SPI clock; idle low, half-period two clk cycles. |
| `cs_n` | `out` | leave blank (scalar) | 1 | Active-low chip select. |
| `rx_data` | `out` | `7:0` | 8 | Last completed received byte. |
| `busy` | `out` | leave blank (scalar) | 1 | Transfer active. |
| `done` | `out` | leave blank (scalar) | 1 | One-clock completion pulse. |

## Body-only SystemVerilog to copy

```systemverilog
logic divider;
logic [3:0] sampled;
logic [6:0] tx_remaining;
logic [7:0] rx_shift;
always_ff @(posedge clk) begin
    if (reset) begin
        divider <= 1'b0;
        sampled <= '0;
        tx_remaining <= '0;
        rx_shift <= '0;
        mosi <= 1'b0;
        sclk <= 1'b0;
        cs_n <= 1'b1;
        rx_data <= '0;
        busy <= 1'b0;
        done <= 1'b0;
    end else begin
        done <= 1'b0;
        if (!busy) begin
            if (start) begin
                divider <= 1'b0;
                sampled <= '0;
                tx_remaining <= tx_data[6:0];
                rx_shift <= '0;
                mosi <= tx_data[7];
                sclk <= 1'b0;
                cs_n <= 1'b0;
                busy <= 1'b1;
            end
        end else if (divider) begin
            divider <= 1'b0;
            if (!sclk) begin
                sclk <= 1'b1;
                rx_shift <= {rx_shift[6:0], miso};
                sampled <= sampled + 4'd1;
            end else begin
                sclk <= 1'b0;
                if (sampled == 4'd8) begin
                    busy <= 1'b0;
                    cs_n <= 1'b1;
                    mosi <= 1'b0;
                    rx_data <= rx_shift;
                    done <= 1'b1;
                end else begin
                    mosi <= tx_remaining[6];
                    tx_remaining <= {tx_remaining[5:0], 1'b0};
                end
            end
        end else divider <= 1'b1;
    end
end
```

## Expected document and Circuit

The saved Component has one complete explanation, exactly 11 wire
ports with the table's directions and widths, and one SystemVerilog Section
containing this body. No placeholder output tie-offs replace the supplied logic.
The leaf Circuit preview shows one Component and its physical terminals, with no
invented internal instances or internal nets. That leaf preview is read-only.
The generated module wraps these ports and this body. Its technical module name
can differ from `spi8`; use the generated manifest and file list to identify it.

## Manual review checkpoints

- Check the explanation, interfaces, and body together; identify contradictions.
- Check scalar ports remain scalar and vector bounds survive save and reopen.
- Inspect every terminal label and width in the leaf preview in both themes.
- Generate from the saved revision, retain the project, and run its `make lint`.
- Record reference-input lint separately from actual UI-generated project lint.
- Keep functional simulation marked **unverified**.

Return to the [catalogue](../README.md).
