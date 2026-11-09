# Spec Catalog Component contracts: phase 3

These contracts describe the Component interfaces and behavior. Check the [runtime inventory](../../../spec_catalog_service/catalog/inventory.json) for delivery status. Apply the [common rules](../common-rules.md).

## 2. Component contracts

Use the common REQ interface and edge-count convention. Every iterative unit has
one outstanding request. Every pipelined unit must propagate backpressure without
losing or reordering transactions. Tests must count transfer edges, not merely
inspect the first cycle in which an internal register changes.

### add_sub

- Parameters: W=32 [1..64].
- Ports: I(a_i:W,b_i:W,sub_i:1); O(result_o:W,carry_o:1,overflow_o:1).
- Behavior: sub=0: a+b, carry is unsigned carry-out. sub=1: a-b, carry=1 means no unsigned borrow (a>=b). overflow is signed two's-complement overflow for the selected operation.
- Required directed checks: Exhaust W=4, carry/borrow boundaries, signed min/max, zero subtraction.
- Presets: default; W=1; W=4; W=64.

### saturating_add_sub

- Parameters: W=32 [2..64], SIGNED=1 [0 or 1].
- Ports: I(a_i:W,b_i:W,sub_i:1); O(result_o:W,saturated_o:1).
- Behavior: Compute exact integer sum/difference, clamp to signed or unsigned W-bit range, assert saturated iff clamped.
- Required directed checks: Both saturation directions, exact limits without flag, unsigned subtract below zero, exhaustive W=4.
- Presets: default; W=2,SIGNED=0; W=4,SIGNED=1; W=64,SIGNED=0.

### comparator

- Parameters: W=32 [1..64], SIGNED=0 [0 or 1].
- Ports: I(a_i:W,b_i:W); O(lt_o:1,eq_o:1,gt_o:1).
- Behavior: Exactly one comparison flag is high according to SIGNED.
- Required directed checks: Equal words, sign-bit difference, adjacent limits, exhaustive W=4.
- Presets: default; W=1,SIGNED=1; W=4,SIGNED=0; W=64,SIGNED=1.

### min_max

- Parameters: W=32 [1..64], SIGNED=0 [0 or 1].
- Ports: I(a_i:W,b_i:W); O(min_o:W,max_o:W,min_from_b_o:1).
- Behavior: Return ordered input values; ties select a for minimum and min_from_b=0.
- Required directed checks: Signed/unsigned bounds, equal inputs, lane origin, exhaustive W=4.
- Presets: default; W=1,SIGNED=1; W=4,SIGNED=0; W=64,SIGNED=1.

### absolute_value

- Parameters: W=32 [2..64].
- Ports: I(data_i:W); O(magnitude_o:W,min_value_o:1).
- Behavior: Input signed; output unsigned magnitude. Most-negative input yields 2**(W-1), representable as unsigned, and min_value=1.
- Required directed checks: Zero, -1, min/max, exhaustive W=4.
- Presets: default; W=2; W=4; W=64.

### multiplier_comb

- Parameters: W=16 [1..32], SIGNED=0 [0 or 1].
- Ports: I(a_i:W,b_i:W); O(product_o:2*W).
- Behavior: Exact full-width signed or unsigned product. No truncation.
- Required directed checks: Zero, unit, signed extremes, exhaustive W=4, independent Python multiplication.
- Presets: default; W=1,SIGNED=1; W=4,SIGNED=0; W=32,SIGNED=1.

### multiplier_pipeline

- Parameters: W=16 [1..32], SIGNED=0 [0 or 1], STAGES=3 [1..8].
- Ports: REQ(a_i:W,b_i:W; product_o:2*W), pipelined.
- Behavior: Exact product, latency STAGES without stalls, one request per edge. Elastic valid pipeline; backpressure must preserve order and product.
- Required directed checks: Latency each preset, all-stage stalls, simultaneous input/output, signed limits.
- Presets: default; W=1,SIGNED=1,STAGES=1; W=7,SIGNED=0,STAGES=2; W=32,SIGNED=1,STAGES=8.

### multiplier_iterative

- Parameters: W=16 [1..32], SIGNED=0 [0 or 1].
- Ports: REQ(a_i:W,b_i:W; product_o:2*W).
- Behavior: Full product using shift/add, one arithmetic iteration per bit. Fixed response transfer latency W+1 without stall, no early zero shortcut. Handle signs through unsigned magnitudes with sufficient width.
- Required directed checks: Exact iteration count, held response, signed min*min, zero operands, reset busy.
- Presets: default; W=1,SIGNED=1; W=7,SIGNED=0; W=32,SIGNED=1.

### mac

- Parameters: W=16 [1..32], ACC_W=40 [2*W..128], SIGNED=1 [0 or 1].
- Ports: REQ(a_i:W,b_i:W,clear_i:1; sum_o:ACC_W), one elastic response register.
- Behavior: Each accepted request computes accumulator + full product, or 0 + product when clear_i=1; wrap to ACC_W. Accumulator changes only on accepted input. Can accept each edge when output capacity permits; response latency 1. Reset accumulator zero.
- Required directed checks: Clear+multiply, accumulated wrap, stalled response prevents unintended accumulation, signed extremes.
- Presets: default; W=1,ACC_W=2,SIGNED=0; W=7,ACC_W=20,SIGNED=1; W=32,ACC_W=128,SIGNED=1.

### divider_iterative

- Parameters: W=16 [2..32], SIGNED=0 [0 or 1].
- Ports: REQ(dividend_i:W,divisor_i:W; quotient_o:W,remainder_o:W,div_zero_o:1,overflow_o:1).
- Behavior: One restoring iteration per dividend bit; one outstanding request. Transfer latency W+1 without stalls, including error cases. Signed quotient truncates toward zero; remainder has dividend sign. Divide by zero: quotient=0, remainder=dividend, div_zero=1. Signed min/-1: quotient=min, remainder=0, overflow=1. Other flags zero.
- Required directed checks: All sign pairs; quotient*divisor+remainder=dividend outside exceptional cases; remainder magnitude bound; zero, min/-1; exact latency and held response; exhaustive W=4.
- Presets: default; W=2,SIGNED=1; W=4,SIGNED=0; W=32,SIGNED=1.

### divider_pipeline

- Parameters: W=16 [2..32], SIGNED=0 [0 or 1].
- Ports: REQ(dividend_i:W,divisor_i:W; quotient_o:W,remainder_o:W,div_zero_o:1,overflow_o:1), pipelined.
- Behavior: Fully staged restoring division; one request per edge. Transfer latency W+1 without stalls, including error cases. Signed quotient truncates toward zero; remainder has dividend sign. Divide by zero: quotient=0, remainder=dividend, div_zero=1. Signed min/-1: quotient=min, remainder=0, overflow=1. Other flags zero.
- Required directed checks: All sign pairs; quotient*divisor+remainder=dividend outside exceptional cases; remainder magnitude bound; zero, min/-1; exact latency and held response; exhaustive W=4.
- Presets: default; W=2,SIGNED=1; W=4,SIGNED=0; W=32,SIGNED=1.

### integer_sqrt

- Parameters: W=32 [2..64, even].
- Ports: REQ(radicand_i:W; root_o:W/2,remainder_o:W).
- Behavior: Unsigned floor square root by digit-pair restoring algorithm. Fixed transfer latency W/2+1. remainder=x-root**2.
- Required directed checks: x=0/1/max, perfect squares and neighbors; root**2<=x<(root+1)**2; exhaustive W=8.
- Presets: default; W=2; W=8; W=64.

### fixed_round

- Parameters: IW=32 [2..64], OW=16 [1..IW], DROP=8 [0..IW-1].
- Ports: I(data_i:IW); O(data_o:OW,overflow_o:1).
- Behavior: Signed integer divide by 2**DROP, round to nearest with exact halfway ties to even. Wrap rounded integer to OW bits. overflow indicates rounded integer outside signed OW-bit range. DROP=0 is unchanged scale.
- Required directed checks: Positive/negative half ties, above/below ties, negative zero rounding, rounded overflow, DROP=0.
- Presets: default; IW=8,OW=8,DROP=0; IW=8,OW=4,DROP=3; IW=64,OW=32,DROP=31.

### fixed_saturate

- Parameters: IW=32 [2..64], OW=16 [1..IW].
- Ports: I(data_i:IW); O(data_o:OW,clipped_o:1).
- Behavior: Signed integer clamp to signed OW-bit limits. No binary-point shift. clipped iff value changes.
- Required directed checks: Both limits and one beyond, equal width, negative values.
- Presets: default; IW=2,OW=1; IW=8,OW=4; IW=64,OW=32.

### fixed_scale

- Parameters: IW=16 [2..32], OW=16 [2..32], COEFF_W=16 [2..32], FRAC=8 [0..COEFF_W-1], GAIN=256 [-2**(COEFF_W-1)..2**(COEFF_W-1)-1].
- Ports: I(data_i:IW); O(data_o:OW,clipped_o:1).
- Behavior: Exact signed data*GAIN, nearest-even divide by 2**FRAC, then signed OW-bit saturation. GAIN is a signed raw fixed-point integer, not a float.
- Required directed checks: Gain 0, positive/negative gain, half ties, saturation, identity gain.
- Presets: default; IW=8,OW=8,COEFF_W=8,FRAC=4,GAIN=16; IW=8,OW=4,COEFF_W=8,FRAC=3,GAIN=-7; IW=32,OW=32,COEFF_W=32,FRAC=16,GAIN=65536.

### dot_product

- Parameters: W=16 [2..32], N=4 [1..16], OUT_W=40 [2*W+L(N)..128].
- Ports: REQ(a_i:N*W,b_i:N*W; sum_o:OUT_W).
- Behavior: Signed dot product, iterate one pair per edge; exact full-precision sum sign-extended to OUT_W. Transfer latency N+1. L(N) bound deliberately includes a guard bit.
- Required directed checks: Lane ordering, cancellation, all min operands, N=1, independently summed products.
- Presets: default; W=2,N=1,OUT_W=5; W=7,N=3,OUT_W=16; W=32,N=16,OUT_W=68.

### fir_filter

- Parameters: W=16 [2..32], TAPS=4 [1..16], CW=16 [2..32], FRAC=8 [0..CW-1], COEFFS=256 [0..2**(TAPS*CW)-1], OW=16 [2..64].
- Ports: CLK; S(W); M(OW); O(clipped_o:1).
- Behavior: Accepted samples shift signed history; coefficient lane 0 multiplies newest sample. Interpret each CW-bit coefficient as signed. Exact accumulation, nearest-even shift FRAC, signed OW saturation. One elastic output register, latency 1; accept only when response slot free or consumed. clipped travels with output. Reset history zero.
- Required directed checks: Impulse response for mixed signed coefficients; step; independent convolution; stalls do not shift history; saturation.
- Presets: default; W=8,TAPS=1,CW=8,FRAC=4,COEFFS=16,OW=8; W=8,TAPS=3,CW=8,FRAC=4,COEFFS=66040,OW=16; W=32,TAPS=16,CW=32,FRAC=16,COEFFS=65536,OW=64.

### cic_decimator

- Parameters: W=16 [2..24], R=4 [2..16], ORDER=2 [1..4].
- Ports: CLK; S(W); M(W+ORDER*L(R)).
- Behavior: Signed CIC, differential delay 1; internal/output width B=W+ORDER*L(R). At each accepted input update cascaded integrators using each preceding stage NEW value modulo 2**B. Every R-th accepted input pass new last-integrator value through ORDER comb stages, each subtracting its saved previous input modulo 2**B. No scaling. Hold output; stall all input when output occupied and not consumed. Output latency 1 from each R-th input; initial decimation phase count zero.
- Required directed checks: Bit-exact modular reference recurrence, impulse/constant inputs, R-th alignment, wrap, arbitrary stalls.
- Presets: default; W=2,R=2,ORDER=1; W=7,R=3,ORDER=3; W=24,R=16,ORDER=4.

### cic_interpolator

- Parameters: W=16 [2..24], R=4 [2..16], ORDER=2 [1..4].
- Ports: CLK; S(W); M(W+ORDER*L(R)).
- Behavior: Signed width B as decimator. At accepted input run ORDER comb differences at input rate (delay 1), then emit R output samples. Feed comb result to integrators for first sample, zero for remaining samples. Cascade integrators using NEW preceding-stage values modulo 2**B. State advances once per emitted output transfer; held payload is computed from uncommitted next state. No new input until group complete; latency 1 to first output. No normalization.
- Required directed checks: Exact recurrence and gain, R outputs per input, stalls freeze state, impulse/constant, reset mid-group.
- Presets: default; W=2,R=2,ORDER=1; W=7,R=3,ORDER=3; W=24,R=16,ORDER=4.

### cordic_rotate

- Parameters: W=24 [16..32], ITER=16 [8..W-3].
- Ports: REQ(x_i:W,y_i:W,angle_i:W; x_o:W,y_o:W,angle_o:W,range_error_o:1).
- Behavior: Iterative circular CORDIC rotation; exact recurrence, angle format, gain correction, range checks, and error bounds are fixed in section 3 below. Transfer latency ITER+2 for all inputs; response stable under stall.
- Required directed checks: Axes, quadrants, zero vector, positive/negative angles, range rejection, exact integer recurrence and separate floating mathematical check within stated bound.
- Presets: default; W=16,ITER=8; W=24,ITER=12; W=32,ITER=24.

### cordic_vector

- Parameters: W=24 [16..32], ITER=16 [8..W-3].
- Ports: REQ(x_i:W,y_i:W; magnitude_o:W,angle_o:W,range_error_o:1).
- Behavior: Iterative circular CORDIC vectoring; exact recurrence, angle format, gain correction, range checks, and error bounds are fixed in section 3 below. Transfer latency ITER+2 for all inputs; response stable under stall.
- Required directed checks: Axes, quadrants, zero vector, positive/negative angles, range rejection, exact integer recurrence and separate floating mathematical check within stated bound.
- Presets: default; W=16,ITER=8; W=24,ITER=12; W=32,ITER=24.

### parity

- Parameters: W=32 [1..256].
- Ports: I(data_i:W,parity_i:1); O(even_parity_o:1,odd_parity_o:1,error_o:1).
- Behavior: even_parity=XOR of data; odd_parity=inverse. error=XOR(data) XOR parity_i (even-parity check).
- Required directed checks: Every single-bit change, zero/ones, exhaustive W=8.
- Presets: default; W=1; W=8; W=256.

### crc_serial

- Parameters: WIDTH=32 [8..32], POLY=79764919 [1..2**WIDTH-1, odd], INIT=4294967295 [0..2**WIDTH-1], XOROUT=4294967295 [0..2**WIDTH-1].
- Ports: CLK; I(clear_i:1,valid_i:1,bit_i:1); O(crc_o:WIDTH).
- Behavior: Non-reflected, MSB-first CRC. clear wins and restores INIT; reset restores INIT. For each bit b: feedback=state[WIDTH-1] XOR b; state=(state<<1) masked to WIDTH XOR (POLY if feedback else 0). Output=state XOR XOROUT. Process one bit per valid edge.
- Required directed checks: Independent polynomial long division; byte sequence ASCII 123456789 -> CRC-32/MPEG-2 0x0376e6e7 when XOROUT=0, and 0xfc891918 for default XOROUT; clear+valid; serial/parallel equivalence with same bit stream.
- Presets: default; WIDTH=8,POLY=7,INIT=0,XOROUT=0; WIDTH=16,POLY=4129,INIT=65535,XOROUT=0; WIDTH=32,POLY=79764919,INIT=4294967295,XOROUT=0.

### crc_parallel

- Parameters: WIDTH=32 [8..32], POLY=79764919 [1..2**WIDTH-1, odd], INIT=4294967295 [0..2**WIDTH-1], XOROUT=4294967295 [0..2**WIDTH-1]. BYTES=4 [1..16].
- Ports: CLK; I(clear_i:1,valid_i:1,data_i:8*BYTES); O(crc_o:WIDTH).
- Behavior: Non-reflected, MSB-first CRC. clear wins and restores INIT; reset restores INIT. For each bit b: feedback=state[WIDTH-1] XOR b; state=(state<<1) masked to WIDTH XOR (POLY if feedback else 0). Output=state XOR XOROUT. Process bytes in ascending lane order, each byte bit 7 through 0, all BYTES per valid edge; no partial-byte mask.
- Required directed checks: Independent polynomial long division; byte sequence ASCII 123456789 -> CRC-32/MPEG-2 0x0376e6e7 when XOROUT=0, and 0xfc891918 for default XOROUT; clear+valid; serial/parallel equivalence with same bit stream.
- Presets: default; WIDTH=8,POLY=7,INIT=0,XOROUT=0,BYTES=1; WIDTH=16,POLY=4129,INIT=65535,XOROUT=0,BYTES=3; BYTES=16.

### lfsr

- Parameters: W=16 [2..64], TAPS=45 [1..2**W-1], SEED=1 [1..2**W-1].
- Ports: CLK; I(en_i:1,load_i:1,seed_i:W); O(state_o:W,seed_error_o:1).
- Behavior: load wins over enable. Nonzero seed loads; zero seed rejects/holds and pulses seed_error. Otherwise enabled next=((state<<1) | parity(state & TAPS)) masked to W. Reset uses SEED. TAPS/SEED must fit W. Maximal period is not promised for arbitrary taps.
- Required directed checks: Reference recurrence, load priority, zero rejection, repeatability; prove period 15 for W=4,TAPS=12,SEED=1 by enumeration.
- Presets: default; W=2,TAPS=3,SEED=1; W=4,TAPS=12,SEED=1; W=64,TAPS=27,SEED=1.

### secded_encode

- Parameters: DATA_W=32 [8,16,32,64 only].
- Ports: I(data_i:DATA_W); O(code_o:DATA_W+P+1), where P is smallest integer with 2**P>=DATA_W+P+1.
- Behavior: Shortened extended Hamming SECDED. Bit placement, even parity, and overall parity are fixed in section 4.
- Required directed checks: Zero, each data bit, exhaustive DATA_W=8, independent parity-check matrix.
- Presets: default; DATA_W=8; DATA_W=16; DATA_W=64.

### secded_decode

- Parameters: DATA_W=32 [8,16,32,64 only].
- Ports: I(code_i:DATA_W+P+1); O(data_o:DATA_W,single_error_o:1,double_error_o:1), P as encoder.
- Behavior: Correct any single-bit error, including overall parity; flag every two-bit error. Fixed syndrome mapping in section 4. No correction promise for 3+ errors.
- Required directed checks: Every single-bit and every bit pair for every DATA_W=8 codeword; all positions/pairs on 32 random words for larger widths; independent matrix.
- Presets: default; DATA_W=8; DATA_W=16; DATA_W=64.

### watchdog

- Parameters: W=16 [1..32].
- Ports: CLK; I(enable_i:1,kick_i:1,limit_i:W,clear_i:1); O(expired_o:1,count_o:W).
- Behavior: clear wins; disabling clears count but preserves sticky expired. Enabled kick clears count. Otherwise increment up to limit; expire on the edge reaching limit. limit=0 expires on first enabled non-kick edge. expired remains until clear/reset. Runtime limit reduction below current count expires next non-kick edge; do not wrap.
- Required directed checks: Kick at expiry, clear priority, disabled interval, limit 0/1, runtime reduction, sticky flag.
- Presets: default; W=1; W=4; W=32.

### timeout_monitor

- Parameters: W=16 [1..32].
- Ports: CLK; I(start_i:1,complete_i:1,cancel_i:1,limit_i:W); O(busy_o:1,timeout_o:1).
- Behavior: cancel wins, then complete, then start. Start captures limit; zero limit pulses timeout immediately, otherwise timeout after limit subsequent active edges. Start while busy restarts. timeout is one edge, busy clears on completion/timeout/cancel.
- Required directed checks: Same-edge start/complete, completion on expiry edge wins, start while busy, zero limit, runtime limit ignored until restart.
- Presets: default; W=1; W=4; W=32.

### interrupt_controller

- Parameters: N=8 [1..64].
- Ports: CLK; I(irq_i:N,enable_i:N,clear_i:N); O(pending_o:N,irq_o:1,index_o:L(N),valid_o:1).
- Behavior: Pending next=(pending & ~clear) | irq, so set wins. Mask affects aggregate/index only, not capture. Lowest enabled pending bit wins; no eligible source gives index0/valid0. Level sources reassert until low.
- Required directed checks: Set/clear collision, masked accumulation, unmask, priorities, no eligible source.
- Presets: default; N=1; N=3; N=64.

### fault_collector

- Parameters: N=8 [1..64].
- Ports: CLK; I(fault_i:N,clear_i:N); O(sticky_o:N,any_o:1,first_valid_o:1,first_index_o:L(N)).
- Behavior: Sticky bits use set-wins-clear. Capture lowest fault index on first fault after no sticky bits remain. Keep that first index while any sticky bit remains, even if its own bit clears. Clear first_valid when all resulting sticky bits zero.
- Required directed checks: Simultaneous faults, clear original while another remains, full clear and recapture, set+clear collision.
- Presets: default; N=1; N=3; N=64.

### lockstep_compare

- Parameters: W=32 [1..256].
- Ports: CLK; I(valid_a_i:1,data_a_i:W,valid_b_i:1,data_b_i:W,clear_i:1); O(mismatch_o:1,sticky_o:1).
- Behavior: Register mismatch each edge when valids differ or both valid and data differ. Both invalid ignore data. Sticky set wins over clear. No temporal alignment buffer.
- Required directed checks: Valid mismatch, invalid payload ignored, data mismatch, clear+new mismatch.
- Presets: default; W=1; W=7; W=256.

## 3. Normative CORDIC algorithm and numeric checks

The two CORDIC entries use signed Cartesian raw integers with F=W-3 fractional
bits (range [-4,4)). Legal inputs satisfy abs(x_raw)<=2**(F-1) and
abs(y_raw)<=2**(F-1). This keeps headroom and defines the promised accuracy domain.
Angles use signed turns: raw integer a represents a/2**W turns, so the signed
range is [-0.5,0.5). Rotation accepts angles from -0.25 through +0.25 turns,
inclusive. Out-of-range input returns zero data/angle and range_error=1 at the
normal latency. Other inputs return range_error=0.

Generate constants with Decimal precision80, nearest-even rounding. Compute pi
by Machin's formula `16*atan(1/5)-4*atan(1/239)`; use the alternating arctangent
series until the next term is below 1e-78. For i=0 use atan(1)=pi/4, for i>0 use
the same convergent series. Constants are:

- A[i]=round_even(atan(2**(-i))/(2*pi)*2**W), i=0..ITER-1.
- K=product over i of 1/sqrt(1+2**(-2*i)).
- Kraw=round_even(K*2**(W+4)); gain correction multiplies input by Kraw then
  nearest-even divides by 2**(W+4).

Store generated constants in the SV source as localparams. Do not compute real
numbers in hardware. Use W+4 signed Cartesian intermediates with F fractional
bits and W+4 signed angle intermediates with the same turn scale as above.
Arithmetic shifts round toward negative infinity; every iteration uses the old
x/y/z values for all three next-state expressions. Do not truncate Cartesian
state to W bits between iterations.

Rotation starts at gain-corrected x/y and z=input angle. At iteration i set d=+1
when z>=0, else -1. Then `x'=x-d*(y>>>i)`, `y'=y+d*(x>>>i)`, `z'=z-d*A[i]`.
Return x/y low W bits (the promised domain avoids overflow) and residual z as
angle_o. No saturation or hidden angle remapping.

Vectoring starts with gain-corrected x/y and z=0. If x<0, negate both Cartesian
values and set z=+0.5 turns when original y>=0, otherwise -0.5 turns; intermediate
width represents both. At iteration i set d=+1 when y>=0, otherwise -1. Then
`x'=x+d*(y>>>i)`, `y'=y-d*(x>>>i)`, `z'=z+d*A[i]`. Return x as magnitude and z
wrapped modulo one turn into [-0.5,0.5). Special-case input (0,0) to magnitude 0,
angle 0, no error. Both algorithms use ITER iteration edges plus a gain/setup
edge; response transfer is at request edge + ITER+2.

Require bit-for-bit comparison with an independent integer recurrence. In
addition compare against mathematical rotation/hypot/atan2 in a separate model.
Cartesian absolute error bound is `(8*ITER+16)*2**(-F)+8*2**(-ITER)` in real units.
Vector angle circular error bound is `8*2**(-ITER)+(ITER+4)*2**(-W)` turns, applied
only when input magnitude>=0.125; below that, require bit-exact recurrence but do
not promise a relative angle accuracy. Check rotation residual angle against the
same angular bound. Report measured worst errors and the exact domain; these are
starter implementations with a declared bound, not unspecified DSP accuracy.

## 4. Normative SECDED layout

Let P be the least integer satisfying 2**P>=DATA_W+P+1 and H=DATA_W+P. Number
Hamming positions from 1 through H. Code bit position-1 corresponds to that
position; code bit H is overall parity. Place data bits in ascending non-power-of-
two positions, least significant data bit first. Power-of-two positions hold even
Hamming parity over all positions whose index contains that parity index bit.
Set overall parity to XOR of all H Hamming bits, giving even parity over the code.

Decoder syndrome is XOR of indices of set Hamming bits; overall check is XOR of
all H+1 code bits. Cases:

| Syndrome | Overall check | Action |
| --- | --- | --- |
| 0 | 0 | no correction, flags 0 |
| 0 | 1 | overall-parity-only error, single_error=1, unchanged data |
| 1..H | 1 | flip that Hamming position, single_error=1 |
| nonzero | 0 | double_error=1, no correction |
| >H | 1 | uncorrectable diagnostic: double_error=1, no correction |

Extract data after the indicated correction; on double_error return extracted
uncorrected data, which is not valid corrected data. Flags are mutually exclusive.
For zero/one/two injected errors check all guarantees. Do not describe a 3+ error
pattern that aliases a correctable syndrome as detected by SECDED.

