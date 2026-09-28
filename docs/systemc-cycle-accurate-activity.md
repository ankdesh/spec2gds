# Cycle-accurate SystemC Activity

`systemc.generate_cycle_accurate` compiles a selected design's physical wire
hierarchy and stored SystemVerilog sections into a native SystemC project. It is
independent of `rtl.generate` and the TLM-oriented
`systemc.generate_at_skeleton` Activity. The generated code uses `SC_MODULE`
classes and builds against SystemC without Verilator.

## Source profile

The selected design and its reachable components must use unsigned, two-state
physical inputs and outputs of 1–64 bits. Connections must be full-width
ad-hoc wires with one driver and at least one sink. Every leaf component needs
a nonempty SystemVerilog body section. The initial combinational subset covers
bitwise logic, addition, subtraction, multiplication, muxes, equality and
unsigned comparisons, logical shifts, slices, concatenation, and replication.
Rising-edge registers may have synchronous or asynchronous reset. Operations
outside that subset, X/Z values, inout ports,
bus interfaces, port slices, and symbolic widths are reported before output is
published. A separate, explicit failure is preferable to silently producing a
model with different behavior.

The specification remains the source of truth for ports and hierarchy. The
Activity assembles temporary complete SystemVerilog modules, then uses the
Slang-enabled CIRCT `circt-verilog` frontend to lower behavior to HW/Comb/Seq
IR. A small CIRCT-linked emitter validates and translates the supported IR to
SystemC. No PyCDE-generated shell or region stitching is needed.

## Toolchain

Use `uv sync` to create/update the repository's `.venv`. Install a CIRCT build
from the `firtool-1.160.0` release with `circt-verilog`, CMake package files,
headers, and shared libraries. Build and install the repository's emitter
against that exact CIRCT installation:

```bash
cmake -S tools/systemc-rtl -B build/systemc-rtl-emitter \
  -DCMAKE_PREFIX_PATH=/path/to/circt-install \
  -DCMAKE_INSTALL_PREFIX=/path/to/circt-install
cmake --build build/systemc-rtl-emitter
cmake --install build/systemc-rtl-emitter
```

Install SystemC 2.3.3 or later for building the emitted project. Configure:

```bash
export CIRCT_PREFIX=/path/to/circt-install
export SYSTEMC_PREFIX=/path/to/systemc-install
```

The Activity expects `circt-verilog` and `spec2gds-systemc-emit` in
`$CIRCT_PREFIX/bin`. Shared-library search paths for CIRCT's dependencies must
also be configured if the installation does not provide them itself. Version
information is recorded in each output manifest.
The editor's launch dialog reports a missing compiler before starting a job.

## Output and use

Select a design in Spec Editor, choose **Launch activity…**, then **Generate
cycle-accurate SystemC**. The managed output is
`systemc-rtl/<document-id>/<design-id>/` beside the active `.spec` package. It
contains `include/design.h`, the assembled inputs in `source/`,
`src/main.cpp`, `CMakeLists.txt`, and `generation-manifest.json`. A typed Activity
report and JSON artifact contain source revision, source-section hashes, tool
versions, file inventory, and tree digest. Rerunning replaces only output
owned by this Activity and design.

Build the smoke executable from the generated directory:

```bash
cmake -S . -B build -DCMAKE_PREFIX_PATH="$SYSTEMC_PREFIX"
cmake --build build
./build/systemc_smoke
```

The smoke executable elaborates the selected top. To drive ports and check
cycle behavior, instantiate the generated component classes in your own
SystemC testbench. Signal values before the first reset are outside the
two-state model's equivalence contract.
