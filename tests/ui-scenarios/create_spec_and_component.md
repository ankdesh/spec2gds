# Manual smoke: create a Spec and timer component

This optional live-model scenario complements the deterministic
[acceptance suites](../../docs/assistant-acceptance-tests.md). It is not a claim
that browser acceptance requires a model key.

Start the combined stack with `OPENAI_API_KEY` configured. Use
`scripts/serve-all.sh start --require-human-approval` when testing review; the
default Spec policy saves valid submissions automatically. Choose a fresh document
ID so creation does not collide with an existing package.

1. Open the Assistant at `http://127.0.0.1:6013`, select **New conversation**,
   **Create new**, the Spec Editor service, a document ID such as `ui_timer_spec`,
   and title `UI Automation Timer Spec`. Select **Focused** and **Start conversation**.
2. Send: `Create a timer component named timer_core with a 32-bit counter,
   clk and rst_n inputs, and irq output.` Confirm any genuinely missing details
   through **Continue proposal** if offered.
3. Inspect the proposal's operations and assumptions. Under restricted policy,
   confirm the source is unchanged before **Approve and apply**. Under automatic
   policy, inspect the saved/applied receipt without an approval click.
4. Open Spec Editor at `http://127.0.0.1:6010/editor` and use **File → Open
   Specification** to open `<SPEC_DOCUMENT_ROOT>/ui_timer_spec.spec` on the server.
   Verify `timer_core`, its ports, any authored SystemVerilog body and the saved
   source revision. There is no `/specs/<document-id>` editor route.

For automated evidence, use the acceptance runner's `automatic` and `restricted`
scenarios. `--live-model` is explicitly optional; the runner's normal fixtures do
not contact an external model.
