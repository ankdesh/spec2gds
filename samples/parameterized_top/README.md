# Parameterized top-level Design

Open `system.spec` in Spec Editor. The **System** top-level Design declares input
`a`, output `y`, and parameter `DATA_WIDTH = 8`. Both ports use `DATA_WIDTH-1:0`.

The reusable **Buffer** Component declares its own `WIDTH` parameter. Instance
`u` explicitly maps `WIDTH = DATA_WIDTH` and connects to the top-level ports.
Instance `small` uses `WIDTH = 4` and connects to the separate four-bit input
`b` and output `z`. Both instances use the same Component. Their effective
interfaces are independent.

Use the instance Options menu to edit parameter mappings. Open the Design in
Circuit Designer to inspect the boundary terminals and the two effective port
widths. Select **Begin editing** before circuit changes and **Save to Spec** to
commit them. No hidden Component holds the top-level interface.
