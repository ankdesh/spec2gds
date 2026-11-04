# Phase 4: protocols, peripherals, and complete IP starters

Status: implementation instructions. Requires completed Phases 1, 2, and 3.

## 1. Inputs, outputs, and ordered implementation

Read [the shared contract](../README.md), all predecessor handoffs, and verify
96 accepted releases. Deliver 24 new entries, 120 total, including the two
self-contained composite starters in section 4. Preserve accepted release bytes.

1. Implement arbitration/address checks, then the fixed CSR map and flat-wire
   protocol targets/bridge. Use independent bus drivers and side-effect scoreboards.
2. Implement digital peripheral models and bounded transaction checkers before
   peripheral SV. Split physical pins into sampled input and drive/enable outputs.
3. Implement the three DMA helpers against the defined simple memory interface.
   A full AXI memory master is not needed for this release.
4. Build the exact two composite Designs after their leaf releases pass. Use
   typed topology operations and embed all child definitions and source origins.
   Include small original glue Components with the exact behavior below. Internal
   glue definitions do not count as additional catalogue entries.
5. Execute the live AI Assistant stress below. This exercises published Spec
   flows on a temporary Spec, not a new Assistant library-integration feature.
6. Verify 24 new entries and run the complete 120-entry functional matrix once
   from canonical files after publication, with no neighboring-file dependencies
   for any individual RTL production. Complete hosting release/recovery checks,
   required profiles, final catalogue documentation, and handoff.

## 2. Protocol definitions and fixed CSR map

These are deliberately limited digital subsets, recorded in every usage document.
The four-register map is always 32-bit little-endian data at byte offsets:

| Offset | Name | Access and reset |
| --- | --- | --- |
| 0x0 | CONTROL | RW, reset 0; all bits retained, bit0 used as enable by composites |
| 0x4 | STATUS | RO live `status_i`, writes rejected |
| 0x8 | EVENTS | sticky W1C, reset 0; next=(old & ~masked_write_ones) OR event_i |
| 0xc | IRQ_MASK | RW, reset 0; irq=OR(EVENTS & IRQ_MASK) |

Byte strobe bit j selects data bits 8*j through 8*j+7. Disabled byte lanes do not
change RW or W1C state. All other addresses and unaligned accesses error, with no
side effects. Error reads return zero. Reading never clears. Status is sampled
when the protocol accepts a read; responses remain stable even if status changes.
Reset wins over bus writes/events. Protocol access logic may be factored into
maintained authoring helpers, but the saved file remains canonical source.

The following are exact port-set macros, added to shared notation:

| Macro | Inputs | Outputs |
| --- | --- | --- |
| APB_TARGET(A) | psel_i:1, penable_i:1, pwrite_i:1, paddr_i:A, pwdata_i:32, pstrb_i:4 | pready_o:1, prdata_o:32, pslverr_o:1 |
| APB_CONTROLLER(A) | pready_i:1, prdata_i:32, pslverr_i:1 | psel_o:1, penable_o:1, pwrite_o:1, paddr_o:A, pwdata_o:32, pstrb_o:4 |
| AXIL_TARGET(A) | awvalid_i:1, awaddr_i:A, awprot_i:3, wvalid_i:1, wdata_i:32, wstrb_i:4, bready_i:1, arvalid_i:1, araddr_i:A, arprot_i:3, rready_i:1 | awready_o:1, wready_o:1, bvalid_o:1, bresp_o:2, arready_o:1, rvalid_o:1, rdata_o:32, rresp_o:2 |

APB address/data/control remain stable through setup/access and all wait cycles.
Ignore protection features not listed; no hidden bus-interface declarations.
AXI4-Lite has no IDs, bursts, or exclusive accesses. Each valid channel holds all
fields until ready. Never require AW and W in the same edge. In the target, ready
must not be a combinational function of a different incoming valid channel;
registered slot state controls it. B/R payload and valid hold under stall.

Each peripheral test uses a behavioral peer that derives expected wire events
from the transaction contract, not by reusing the implementation state machine.
The slowest legal divider presets need one directed full transaction; randomized
coverage uses a smaller divider with the same state transitions, recorded explicitly.

I2C timing is fixed as follows. Let H=HALF_PERIOD. Wait for both synchronized
pins high before START, bounded by 16*H edges. Drive SDA low while SCL is released
for H edges, then start the first low phase. Each bit has H driven-low SCL edges,
with SDA set at the beginning, then release SCL and wait for synchronized SCL high.
Count H high edges after that observation, sample synchronized SDA on the final
high edge, then drive SCL low. A synchronized high observation wins over a timeout
on the same edge. Every wait for a released SCL high is bounded by 16*H edges from
release. Target ACKs use released controller SDA; read data uses released SDA,
and the controller's final NACK also releases SDA. STOP holds SDA low for H low
edges, releases/waits for SCL high, holds SDA low for H high edges, releases SDA,
then waits H edges before response. No repeated START is issued. Any detected
NACK ends the data sequence and attempts STOP. Any timeout releases both pins
immediately after that edge. For any failed transaction return rx_data=0;
timeout takes precedence over nack, so flags are never both 1. Successful writes
return rx_data=0. nack_o flags only a target NACK on address or write-data; the
controller's deliberate final read NACK is not an error. No arbitration is performed. This defines digital timing only.

## 3. Component contracts

### arbiter_fixed

- Parameters: N=4 [2..16].
- Ports: I(req_i:N); O(grant_o:N,index_o:L(N),valid_o:1).
- Behavior: Combinational lowest-index request wins. No request gives all zero. No fairness guarantee.
- Required directed checks: All masks at N<=8, one-hot grant, grant subset of request.
- Presets: default; N=2; N=3; N=16.

### arbiter_round_robin

- Parameters: N=4 [2..16].
- Ports: CLK; I(req_i:N,advance_i:1); O(grant_o:N,index_o:L(N),valid_o:1).
- Behavior: Search cyclically from pointer (reset 0); grant first requested lane. Advance pointer to granted+1 modulo N only on valid && advance. A requester holds its request until accepted. No request holds pointer.
- Required directed checks: All continuously requesting get one acceptance in N grants; stalls hold pointer; sparse and changing requests; wrap.
- Presets: default; N=2; N=3; N=16.

### arbiter_weighted

- Parameters: N=4 [2..16], WEIGHTS=16843009 [packed N lanes of 8 bits, each 1..255].
- Ports: CLK; I(req_i:N,advance_i:1); O(grant_o:N,index_o:L(N),valid_o:1).
- Behavior: Cyclic weighted burst service. Reset pointer0 and quota weight0. Search first requested lane from pointer; if it differs, use its full weight. On accepted grant decrement its quota; when exhausted move to next lane and reload that lane weight. Idle lanes are skipped; unused quota is discarded on switching. No request or no advance changes no state.
- Required directed checks: Weights 1/2/3 repeated continuous-request service pattern; sparse requests; no state advance while stalled; service bound sum(weights) accepted grants for persistent requests.
- Presets: default; N=2,WEIGHTS=513; N=3,WEIGHTS=197121; N=16,WEIGHTS=1334440654591915542993625911497130241.

### address_decoder

- Parameters: A=32 [8..32], N=4 [2..16], REGION_BYTES=4096 [4..65536, power of two], BASE=0 [0..2**A-1]; BASE aligned, BASE+N*REGION_BYTES<=2**A.
- Ports: I(addr_i:A); O(hit_o:1,index_o:L(N),select_o:N,offset_o:A).
- Behavior: Contiguous equal byte regions from BASE. Region j is [BASE+j*REGION_BYTES, BASE+(j+1)*REGION_BYTES). offset is address within selected region. Miss gives zero outputs.
- Required directed checks: Each boundary +/-1, final byte, base/nonzero base, no overlap, range constraint.
- Presets: default; A=8,N=2,REGION_BYTES=4,BASE=8; A=16,N=3,REGION_BYTES=256,BASE=256; A=32,N=16,REGION_BYTES=65536,BASE=0.

### csr_register_bank

- Parameters: A=12 [4..32].
- Ports: CLK; I(wr_i:1,rd_i:1,addr_i:A,wdata_i:32,wstrb_i:4,status_i:32,event_i:32); O(rdata_o:32,error_o:1,ctrl_o:32,irq_o:1).
- Behavior: Four-register map in section 2. Combinational read; write commits at edge. Error only when rd or wr enabled and request invalid. Byte strobes affect RW and W1C bits. Event set wins clear. Simultaneous read/write observes pre-edge state.
- Required directed checks: Every register, every byte strobe, RO write rejection, misalignment, unmapped address, W1C/set collision.
- Presets: default; A=4; A=32.

### apb_target

- Parameters: A=12 [4..32].
- Ports: CLK; APB_TARGET(A); I(status_i:32,event_i:32); O(ctrl_o:32,irq_o:1).
- Behavior: APB4 flat-wire four-register target. Section 2 map, zero wait; pready=psel && penable. Commit once per selected access completion edge. pslverr meaningful only at completion. Setup has no side effects.
- Required directed checks: Setup/access sequence, back-to-back accesses, idle signals, strobes, misaligned/error reads/writes, event races.
- Presets: default; A=4; A=32.

### axi_lite_target

- Parameters: A=12 [4..32].
- Ports: CLK; AXIL_TARGET(A); I(status_i:32,event_i:32); O(ctrl_o:32,irq_o:1).
- Behavior: AXI4-Lite 32-bit target with same map. Independently latch AW and W, one slot each; execute once both present and response slot free. Hold B response until accepted. One AR/read response slot; hold R. AWPROT/ARPROT ignored. Write/read may complete concurrently, read returns pre-write state. OKAY=0, SLVERR=2 for map/access error.
- Required directed checks: AW before W, W before AW, simultaneous, stalls on B/R, read/write same address, no duplicate side effects, unmapped/misaligned access.
- Presets: default; A=4; A=32.

### axi_lite_to_apb

- Parameters: A=12 [4..32].
- Ports: CLK; AXIL_TARGET(A); APB_CONTROLLER(A).
- Behavior: Bridge with independent one-slot AW/W and one AR slot. Single APB operation at a time, writes win when both eligible. Setup one edge then access until pready; stable APB controls while waiting. Translate pslverr to SLVERR, hold B/R. Do not issue another operation of the same direction until its response accepted; other direction may proceed. No address remap.
- Required directed checks: Independent AW/W, both directions pending, APB wait0/1/7, errors, downstream side effects once, reset during APB access.
- Presets: default; A=4; A=32.

### apb_demux

- Parameters: A=12 [8..32], N=4 [2..16], REGION_BYTES=256 [4..65536, power of two], BASE=0 [0..2**A-1]; aligned and BASE+N*REGION_BYTES<=2**A.
- Ports: CLK; APB_TARGET(A); O(d_psel_o:N,d_penable_o:1,d_pwrite_o:1,d_paddr_o:A,d_pwdata_o:32,d_pstrb_o:4); I(d_pready_i:N,d_prdata_i:N*32,d_pslverr_i:N).
- Behavior: Decode setup address into contiguous regions. Latch selected lane and local offset for access, hold through waits. Broadcast other controls. Only selected response returns; no match completes with pready=1/pslverr=1 during access and no downstream select.
- Required directed checks: Each region, wait states, setup has no side effects, miss, no response from unselected lane.
- Presets: default; A=8,N=2,REGION_BYTES=4,BASE=0; A=12,N=3,REGION_BYTES=256,BASE=256; A=32,N=16,REGION_BYTES=65536,BASE=0.

### wishbone_target

- Parameters: A=12 [4..32].
- Ports: CLK; I(cyc_i:1,stb_i:1,we_i:1,adr_i:A,dat_i:32,sel_i:4,status_i:32,event_i:32); O(ack_o:1,err_o:1,dat_o:32,ctrl_o:32,irq_o:1).
- Behavior: Classic single-transfer Wishbone subset; byte addresses and same map. Register exactly one ack or err after observing cyc&&stb. Commit at that observation edge; wait for cyc or stb low before another request. No pipelined/B4 burst support. Master holds request until response.
- Required directed checks: Held stb does not repeat writes, valid/misaligned/unmapped/RO cases, ack/err mutual exclusion, abandoned cycle before acceptance.
- Presets: default; A=4; A=32.

### axi_stream_register_slice

- Parameters: BYTES=4 [1..32].
- Ports: CLK; I(s_valid_i:1,s_data_i:8*BYTES,s_keep_i:BYTES,s_last_i:1,m_ready_i:1); O(s_ready_o:1,m_valid_o:1,m_data_o:8*BYTES,m_keep_o:BYTES,m_last_o:1).
- Behavior: One elastic register for AXI4-Stream subset TDATA/TKEEP/TLAST/TVALID/TREADY; no TID/TDEST/TUSER. Keep may be any mask including zero; preserve it exactly. Latency1 and one per edge.
- Required directed checks: All sidebands stable under stall, zero/sparse keep, back-to-back packet boundaries, reset occupied.
- Presets: default; BYTES=1; BYTES=3; BYTES=32.

### stream_packet_arbiter

- Parameters: W=32 [1..256], N=4 [2..16].
- Ports: CLK; I(s_valid_i:N,s_data_i:N*W,s_last_i:N,m_ready_i:1); O(s_ready_o:N,m_valid_o:1,m_data_o:W,m_last_o:1).
- Behavior: Round-robin choose first valid lane from pointer, lock at first exposed valid word even before transfer, retain through bubbles/stalls until last transfer. Advance pointer after last transfer. A packet source must eventually provide last; no forced preemption. No data buffer, combinational forwarding.
- Required directed checks: Stalled first beat, bubbles mid-packet, simultaneous requests, no interleaving, pointer advances only on last transfer.
- Presets: default; W=1,N=2; W=7,N=3; W=64,N=16.

### uart_tx

- Parameters: CLKS_PER_BIT=16 [4..65535].
- Ports: CLK; S(8); O(tx_o:1,busy_o:1).
- Behavior: 8N1, LSB first, idle high. Accept byte only idle; drive start low immediately after acceptance edge, then 8 data bits then stop high, each exactly CLKS_PER_BIT edges. Ready remains low until stop interval complete. No parity or flow-control pins.
- Required directed checks: 0x00/ff/55/a6 exact frame, period counts, back-to-back offer, reset mid-frame returns idle.
- Presets: default; CLKS_PER_BIT=4; CLKS_PER_BIT=7; CLKS_PER_BIT=65535 (one directed frame plus short randomized run with reduced divider).

### uart_rx

- Parameters: CLKS_PER_BIT=16 [4..65535].
- Ports: CLK; I(rx_i:1,m_ready_i:1); O(m_valid_o:1,m_data_o:8,framing_error_o:1,overrun_o:1).
- Behavior: Two-flop synchronize rx. Falling edge starts 8N1 receive; sample start after floor(CLKS_PER_BIT/2) clocks from synchronized edge, reject false start if high. Sample bits every CLKS_PER_BIT clocks thereafter, then stop. Bad stop pulses framing_error and drops byte. One output slot; occupied unconsumed slot causes new completed good byte to drop and overrun pulse. Simultaneous consume/complete replaces slot.
- Required directed checks: False starts, +/-2% input rate at divider>=16, exact-rate small divider, bad stop, overrun, reset in frame.
- Presets: default; CLKS_PER_BIT=4; CLKS_PER_BIT=7; CLKS_PER_BIT=65535 (one directed frame plus reduced-divider random run).

### spi_controller

- Parameters: HALF_PERIOD=4 [2..65535].
- Ports: REQ(tx_i:8; rx_o:8); I(miso_i:1); O(mosi_o:1,sclk_o:1,cs_no:1).
- Behavior: One chip select, mode0 CPOL=0/CPHA=0, MSB first, 8 bits. Assert cs low and present bit7 after request edge. Rising SCLK samples MISO, falling shifts MOSI. HALF_PERIOD system edges per half-cycle; after eighth falling edge deassert cs and return response. Transfer latency 16*HALF_PERIOD+1. No queued transfers.
- Required directed checks: Loopback, exact edges and bit order, response stall leaves cs high/sclk low, reset abort.
- Presets: default; HALF_PERIOD=2; HALF_PERIOD=7; HALF_PERIOD=65535 (one directed transaction).

### spi_target

- Parameters: None.
- Ports: CLK; I(sclk_i:1,cs_ni:1,mosi_i:1,tx_data_i:8,m_ready_i:1); O(miso_o:1,miso_oe_o:1,m_valid_o:1,m_data_o:8,overrun_o:1).
- Behavior: Mode0, MSB-first, one-byte frames. Synchronize sclk/cs/mosi with two flops then edge-detect. Require each external half-period >=4 clk edges, cs setup >=4 edges. On synchronized cs assertion latch tx byte and present bit7; sample MOSI on rising events, advance MISO on falling. After eighth rising event capture received byte. One output slot; overrun drops new byte if held. cs deassert resets bit counter; incomplete frame drops silently. miso_oe follows synchronized selected state.
- Required directed checks: Bit order, tx latch, partial frame abort, overrun, minimum legal clock ratio, selection latency, no analog timing claim.
- Presets: default only; external half-periods 4,7,16.

### i2c_controller

- Parameters: HALF_PERIOD=8 [4..65535].
- Ports: REQ(addr_i:7,read_i:1,tx_data_i:8; rx_data_o:8,nack_o:1,timeout_o:1); I(scl_i:1,sda_i:1); O(scl_drive_low_o:1,sda_drive_low_o:1).
- Behavior: Single-controller standard digital I2C subset, one byte per transaction. Fixed START, address+R/W, ACK, one read/write data byte, ACK check for write or controller NACK for read, STOP. Open-drain split pins only: output1 drives low, output0 releases. Two-flop sample pins. Respect clock stretching on every released high phase, timeout after 16*HALF_PERIOD system edges per high wait; on NACK stop early; on timeout release both pins, return timeout. No arbitration, repeated START, 10-bit address, or multi-controller support.
- Required directed checks: Digital wired-AND target model, read/write, address/data NACK, finite stretch, stuck-low timeout, final read NACK, reset releases pins.
- Presets: default; HALF_PERIOD=4; HALF_PERIOD=7; HALF_PERIOD=65535 (one directed transaction).

### gpio

- Parameters: N=16 [1..64].
- Ports: CLK; I(pin_i:N,out_i:N,oe_i:N,irq_enable_i:N,irq_clear_i:N); O(pin_o:N,pin_oe_o:N,sampled_o:N,irq_pending_o:N,irq_o:1).
- Behavior: Combinational output/enable from out/oe; sampled input through two flops. Sticky rising-edge pending uses enabled synchronized edges, set wins clear. Reset synchronized input/history/pending zero; output pins remain direct input controls. Pad implementation is external.
- Required directed checks: Input synchronization, rising-only irq, mask/clear/set collision, output enable propagation, reset input-high behavior.
- Presets: default; N=1; N=3; N=64.

### pwm

- Parameters: W=16 [2..32].
- Ports: CLK; I(enable_i:1,period_i:W,duty_i:W); O(pwm_o:1,cycle_o:1).
- Behavior: On enable from idle latch period and min(duty,period), phase0. Period0 disables output; retry latching each enabled edge until nonzero. Each period contains exactly period clock intervals; pwm high when phase<duty. Latch updated settings only at wrap; cycle pulses at each wrap. Disable clears phase and output immediately after edge. Duty0 always low, duty>=period always high.
- Required directed checks: Period1, duty0/period/above, runtime updates at wrap, enable/disable, period becomes zero.
- Presets: default; W=2; W=5; W=32.

### dma_address_sequencer

- Parameters: A=32 [8..32], COUNT_W=16 [1..24], STRIDE=4 [1..256].
- Ports: REQ(base_i:A,count_i:COUNT_W; addr_o:A,last_o:1,error_o:1), multiple responses per request.
- Behavior: One request emits count ascending addresses base+j*STRIDE; response stall holds address. count0 emits one terminal response addr=base,last=1,error=1. Precheck last address in widened arithmetic; overflow emits one terminal error response, no address series. Otherwise last marks final address, error0. New request only after final response consumed.
- Required directed checks: Counts0/1/many, overflow near top, arbitrary base alignment permitted, stalls and exact last.
- Presets: default; A=8,COUNT_W=3,STRIDE=1; A=16,COUNT_W=8,STRIDE=3; A=32,COUNT_W=24,STRIDE=256.

### dma_descriptor_queue

- Parameters: A=32 [8..32], LEN_W=16 [1..24], DEPTH=4 [1..64].
- Ports: CLK; I(s_valid_i:1,s_addr_i:A,s_length_i:LEN_W,s_tag_i:8,m_ready_i:1); O(s_ready_o:1,m_valid_o:1,m_addr_o:A,m_length_o:LEN_W,m_tag_o:8,level_o:C(DEPTH)).
- Behavior: FIFO of descriptors, no interpretation of zero length. No fall-through, s_ready iff not full; full pop does not accept push that edge. Preserve all fields.
- Required directed checks: Full/empty/wrap, zero-length descriptor retained, tag association, stalls.
- Presets: default; A=8,LEN_W=1,DEPTH=1; A=16,LEN_W=7,DEPTH=3; A=32,LEN_W=24,DEPTH=64.

### dma_stream_engine

- Parameters: A=32 [8..32], LEN_W=16 [1..24].
- Ports: CLK; descriptor input I(d_valid_i:1,d_addr_i:A,d_length_i:LEN_W,d_tag_i:8), O(d_ready_o:1); O(mem_req_valid_o:1,mem_req_addr_o:A), I(mem_req_ready_i:1,mem_rsp_valid_i:1,mem_rsp_data_i:32,mem_rsp_error_i:1), O(mem_rsp_ready_o:1); ML(32); O(done_valid_o:1,done_tag_o:8,done_error_o:1), I(done_ready_i:1).
- Behavior: Read-only memory-to-stream starter. Length is number of 32-bit words. One descriptor and one memory read outstanding. Aligned base required; precheck final address base+4*(length-1). Zero length completes successfully with no reads/output. Invalid alignment/overflow completes error with no reads. Each successful response emits a word, last on final word. On memory error drop that response and terminate with error, retaining already transferred prefix. Hold completion until accepted; next descriptor only after completion. No response timeout; memory must eventually respond. No AXI master implementation.
- Required directed checks: Zero/one/many words, misalignment/overflow, memory and stream stalls independently, error on first/middle/final read, tag/done stability, no next read before previous word consumed.
- Presets: default; A=8,LEN_W=3; A=16,LEN_W=7; A=32,LEN_W=24.

### stream_processing_subsystem

- Parameters: None; fixed preset, not a parameterized wrapper.
- Ports: CLK; two ingress lanes I(s_valid_i:2,s_data_i:64,s_last_i:2), O(s_ready_o:2); ML(32); APB_TARGET(12); O(irq_o:1).
- Behavior: Exact composite in section 4: two packet FIFOs, packet arbiter, APB CSR target, output gating, and event register. All child definitions embedded. Register-controlled enable drains/stalls according to specified gating; no inferred connections.
- Required directed checks: End-to-end two-source packet ordering, backpressure, CSR enable, packet oversize event/IRQ W1C, reset, isolated RTL production without service.
- Presets: fixed only.

### sensor_capture_subsystem

- Parameters: None; fixed preset, not a parameterized wrapper.
- Ports: CLK; I(sensor_valid_i:1,sensor_data_i:16), O(sensor_ready_o:1); ML(16); APB_TARGET(12); O(irq_o:1).
- Behavior: Exact composite in section 4: fixed FIR, packet marker, FIFO, APB target, and clipping/status reporting. Sensor is synchronous and must obey ready/valid; no analog model. All definitions embedded.
- Required directed checks: Known FIR impulse, eight-word packet boundaries, stream stalls, disable gate and IRQ, reset mid-packet, isolated RTL production.
- Presets: fixed only.

## 4. Exact composite Designs

Both root Components use `SetInternalDesign`. Embed required child definitions
and internal glue. Specialize child definitions to concrete numeric widths using
typed edits; record original release digest and parameter map. Use fresh local
identities for specialized copies, and remap every instance reference. No shared
mutable link to another file is permitted. Every net below is a typed ad-hoc
wire connection with one driver. Explicit slices/concatenations are implemented
inside glue Components when the connection profile cannot express them.

All instances named here have clk_i/rst_ni connected to root clk_i/rst_ni. Fanout
is permitted; multiple drivers are not. Every child input must be connected,
including inactive controls. Unused diagnostic outputs are listed as intentionally
unconnected in usage; never ignore an error path that affects the contract.

### stream_processing_subsystem topology

| Instance | Definition / concrete settings |
| --- | --- |
| u_in0, u_in1 | fifo_packet W=32,DEPTH=16 |
| u_arb | stream_packet_arbiter W=32,N=2 |
| u_csr | apb_target A=12 |
| u_gate | local one-word elastic enable gate described below |
| u_status | local combinational packing, plus accepted-word counter |

Map root ingress lane j to u_inj.s_valid/data/last; return u_inj.s_ready to that
root lane. Pack FIFO output lane j to corresponding arbiter input and return
arbiter ready lane j to FIFO m_ready. u_arb output goes through u_gate to root
m_valid/data/last; root m_ready returns through gate to u_arb.m_ready.

`u_gate`: input en_i=CONTROL[0], s_valid/data/last from arbiter, m_ready from root.
The gate holds one word and last flag. Its input ready is en_i AND
(!full OR m_ready_i); its output valid is full, independent of en_i. Capture or
replace on an input transfer; clear full on an output transfer without replacement.
Reset clears full. This adds one cycle of output latency. CONTROL reset 0, so
incoming packets can fill FIFO storage before enable, but no word enters the gate.
Disabling stops new gate acceptance; an already accepted gate word may drain.
Remaining packet words stay in their FIFO/arbiter until reenable. Never withdraw
an exposed stalled valid word. Each transfer uses the pre-edge enable value.

Map every root APB input to the matching u_csr input and every response back.
u_status emits 32-bit STATUS with bit0=enable, bits[5:1]=u_in0.level,
bits[10:6]=u_in1.level, bits[31:11]=accepted output word counter modulo 2**21.
Counter increments on root output transfer and resets0. u_status emits EVENTS
bit0=u_in0.drop, bit1=u_in1.drop, other bits0. Connect u_csr.ctrl_o to status/gate,
status output to status_i, event output to event_i, and irq_o to root irq_o.
Combinational status/CONTROL path must contain no feedback loop through CSR read.

Proof example: mask IRQ bits0/1, leave disabled, submit one short packet on each
input, confirm no output; enable via APB, observe packets whole with round-robin
order from lane0. Send an oversized lane1 packet, see one EVENTS bit1 and IRQ;
W1C clears after the drop pulse is gone. Backpressure cannot interleave packets.

### sensor_capture_subsystem topology

| Instance | Definition / concrete settings |
| --- | --- |
| u_ingress | local one-word elastic enable gate, W=16, no last flag |
| u_fir | fir_filter W=16,TAPS=2,CW=16,FRAC=8,COEFFS=8388736,OW=16 |
| u_packet | local modulo-eight accepted-sample marker |
| u_fifo | fifo_sync W=17,DEPTH=16 |
| u_csr | apb_target A=12 |
| u_status | local packing and accepted-word counter |

The two signed FIR coefficients are 128/256 each. Gate root sensor stream into
u_fir with CONTROL[0], using the same elastic gate equations above without last.
Disabled returns sensor_ready0; any already accepted gate word still advances
into FIR. Disabling stops new root input acceptance; accepted gate/FIR/FIFO words
continue draining. Connect u_fir.m_data/valid into u_packet;
return FIFO input-ready to FIR output-ready. u_packet has a three-bit counter
reset 0; combinational last=(counter==7), increment modulo8 only on FIR output
transfer. It does not buffer or alter data/valid. Pack data into bits[15:0] and
last into bit16 for u_fifo input; unpack its output to root ML(16). Return root
m_ready directly to FIFO m_ready.

u_status emits STATUS bit0=enable, bits[5:1]=FIFO level,
bits[31:6]=accepted sensor sample counter modulo 2**26. Counter increments only
on root sensor_valid&&sensor_ready, resets0. EVENTS bit0 pulses when a FIR output
with clipped_o=1 transfers into FIFO; other event bits0. IRQ is the CSR irq_o.
Map APB exactly as in the first composite. Do not label ordinary valid/ready
backpressure as sensor overrun. A source that ignores ready violates this input
contract and is outside the functional guarantee.

Proof example: enable, inject an impulse raw value256 followed by zeros. Expect
FIR outputs128,128,0,... with last on outputs8,16,... and unchanged sequence under
stalls. Normal legal input cannot clip this averaging FIR, so inject its event
path in a separate glue/CSR unit check and report end-to-end clipping as
not_applicable for this fixed preset; do not claim a saturated waveform occurred.
Disable mid-stream and confirm only already accepted samples drain.

For both composites copy the single `.spec` to an empty ignored temporary
directory with no catalogue or service. Load it, produce RTL, and run the same
scoreboard. Check a dependency closure and exact instance/terminal netlist dump
against the tables. Check duplicate drivers, dangling references, name collisions,
and a missing child as negative cases; require failure, never a partial RTL file.

## 5. Live AI Assistant stress

Use existing published flows and a document-bound Focused or Goal Spec
conversation. Orchestrated conversations are read-only; Circuit conversations do
not expose Spec authoring tools. Respect actual structural approvals and Activity
proposal decisions. Do not invent library tools or bypass those decisions.

Prepare a new temporary empty Spec and bind the Assistant to it. Submit a precise
request through the live AI Assistant, with the following required content:

> Add one Component named assistant_counter_reference. Use W=8 and ports clk_i,
> rst_ni, en_i, clear_i, count_o[7:0], wrap_o. Use asynchronous active-low reset.
> clear wins over enable, clear resets count0, enable increments modulo256, and
> wrap pulses for one edge on enabled255-to0 only. Declare W, provide body-only
> SystemVerilog, and save the Component. Do not add another Component or Design.

Allow the published `flow_add_component` / `flow_edit_spec` behavior to select the
supported execution sequence. Capture exact applied receipt, operation digest,
source revision, decisions, and reopened `.spec`. Validate behavior against
counter_up W=8. Then ask to change W to5 without changing the behavior and rerun
at W=5. An accepted flow status without a saved applied receipt is not success.

Negative/recovery cases: cancel a structural proposal and prove no durable
change; change the Spec through another client while a proposal is pending and
require conflict/refresh rather than silent overwrite; interrupt after a request
is submitted and explicitly resume/reconcile using the existing request identity
and receipt so no duplicate Component appears. Do not test uncertain completion
by issuing a fresh create request. If unavailable, report that case incomplete.
Do not request secrets or change model settings to manufacture a passing result.

Finally ask the Assistant to explain the saved stream_processing_subsystem from
its supplied source refs and propose an extra FIFO without applying it. Check that
it identifies actual ports and reset assumptions and does not claim a hosted
library integration exists. Do not make a model's free-form answer the hardware
verification oracle. Retain sanitized live evidence and required credentials
availability, with no secrets in the handoff.

## 6. Protocol, peripheral, DMA, and hosting release checks

Protocol scoreboards must count accepted side effects independently of responses.
For every CSR bus wrapper sweep all 16 byte strobes on RW/W1C registers, each legal
register, a RO write, unaligned addresses, unmapped addresses, and event/clear
collisions. For AXI4-Lite use AW/W separation delays 0,1,7 edges in both orders,
B/R stalls 0,1,100 edges, independent read/write traffic, and reset in each buffered
state. APB bridge target wait states 0,1,7 and injected error. Packet arbitration
must survive source bubbles and output stalls without changing selected packet.

Peripheral directed tests assert timing from sampled wires. I2C uses split
open-drain pins with the digital resolution `line = !(controller_low || target_low)`.
No analog pull-up timing, multi-controller arbitration, or physical sign-off is
claimed. SPI target uses only legal external/system clock ratios. UART tests
label the allowed divider-specific baud tolerance, not a universal tolerance.
DMA reference memory is deterministic `word(addr)=(addr XOR 0xa5a55a5a)&0xffffffff`;
inject an error on selected read indices and prove exact output-prefix/completion.
Watchdogs derive from words, peer waits, divider and frame length; deliberately
stuck memory is an environmental liveness failure because no DMA timeout is
implemented. I2C stuck-low must exercise its actual specified timeout.

Run service checks on all 120 canonical files: exact inventory set, no duplicate
identity, category counts, full-text/filter results, numeric version sorting,
report status precedence, HTML escaping, offline index rebuild, simultaneous
upload/read, immutable version conflict, restart after durable-write/index gap,
corrupt durable file -> degraded/read-only state, recovery after restoring that
file, and download digest equality. Use temporary roots for destructive checks.
Test a second version of one copied Component to prove version listing without
changing its accepted 1.0.0 release. Export the canonical tree to an isolated
temporary root; service startup and all downloads must work there without the
original checkout path or other application processes.

## 7. Commands and final gate

```bash
uv run spec2gds-library check --phase 3 --output temp/TEMP_p4/prerequisite
uv run spec2gds-library check --phase 4 --candidates temp/TEMP_p4/candidates --output temp/TEMP_p4/check
uv run spec2gds-library verify --phase 4 --candidates temp/TEMP_p4/candidates --output temp/TEMP_p4/verify
uv run pytest tests/spec_library -m 'not extensive'
scripts/test-all.sh fast
scripts/test-all.sh integration --scope spec,circuit,assistant,activities,shared
scripts/test-all.sh regression
uv run spec2gds-library publish --phase 4 --candidates temp/TEMP_p4/candidates --evidence temp/TEMP_p4/verify --output temp/TEMP_p4/publish
uv run spec2gds-library check --phase 4 --output temp/TEMP_p4/published-check
```

After exact candidate publication, run `check` and `verify` separately for phases
1,2,3,4 against the canonical root with new output directories. This is the one
required complete 120-entry release sweep. Report actual commands per phase;
this sweep does not require repeating browser/Assistant scenarios per entry.
If shared changes affect Verification Planner, include `verification` in integration
or use all scopes. Missing required credentials makes the profiles incomplete.

Accept only with120 delivered inventory records,120 self-contained `.spec` files,
120 usage documents and digest-bound evidence records; working local upload/
browse/search/download service; two composite closure/functional passes; complete
hardware matrices; and passing required software profiles. Record secondary
stress limitations separately. Create final `handoffs/phase-4.md` with a category
coverage table, exact source/evidence digests, complete matrix results, service
startup/example requests, confirmed defect fixes, and deferred families. Update
the shared README status to describe the actual delivered state only then.
