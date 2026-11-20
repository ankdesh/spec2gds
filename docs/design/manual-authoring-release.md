# Manual authoring and explicit verification

Spec Editor keeps explanations, Ports, SystemVerilog Sections, and derived Circuit previews in one readable document. The release uses the existing light and dark themes. Full layout changes are a separate [proposal](ui-redesign-proposal.md).

## Save and verify

1. Save ports, parameters, and body-only SystemVerilog with **Save to Spec**. Incomplete implementation text can be saved. Structural checks, source identity, package integrity, and stale-write checks still apply.
2. Select **Verify Component** or **Verify Design**. This checks the saved target, its reachable implementations, and resolved interface widths. It lints both the leaf Sections and the selected root hierarchy with Verilator. Diagnostics and the saved source remain available after failure.
3. Inspect **Lint passed**, **Lint failed**, **Not verified**, or **Out of date**. Open Verification details for tool identity, resolved widths, and diagnostics. Non-blocking warnings remain visible. A missing compiler cannot produce a passing result.
4. Generate RTL from a target with a current passing result. The Activity result identifies its target, top module, file count, output path, and downloadable report. Run `make lint` in that actual generated project for acceptance. Generation, Component verification, project lint, and functional simulation are separate records.

Functional simulation remains unverified until it is executed. Lint does not prove hardware behavior.

Verification results are held in the Spec service cache. They identify the target, exact source revision, and tool version. A source change makes the prior result out of date. Service restart can return the target to Not verified. There is no `.spec` migration and no verification stamp written into implementation text.

## Manual controls

- Use readable Component and Design names. The service derives the hardware ID; a rename preserves that ID.
- New wire ports start at `in` and `0:0`. Clear Range for a scalar. **Save and add another** retains direction and range, clears ID and description, and returns focus to Port ID. Cancel discards only the current draft.
- **Duplicate** creates a draft with a unique ID suggestion. It copies no connections or bus mappings.
- **Paste rows** accepts TSV or Markdown. Review each row before **Add N ports**. Edit the pasted text to correct rows. Blank ranges stay scalar; omitted ranges use `0:0`. The complete batch saves in one transaction. Rejection retains the draft and changes no saved rows.
- Hardware settings contain entry Design membership, internal Design assignment, Clear assignment, and confirmed deletion. Structural references block unsafe deletion. Clearing an assignment keeps the Design.
- Parameters provide the ID, RTL type, default expression, and description. Symbolic port ranges remain source expressions; explicit verification reports their resolved widths.
- Leaf Components have an embedded read-only interface preview, Expand, and SVG download. The rendered SVG follows the active theme without changing source or geometry. Composite Components and Designs open Circuit Designer. Existing read-only launch URLs remain supported.
- Circuit connection entry has separate **LSB for A** and **LSB for B** fields and a shared transfer width. This permits a high-half boundary slice to connect to a child port whose index starts at zero.

The source keeps supported content for which manual controls are not yet exposed. Full instance update/deletion/ordering, connection-table authoring, transactional and structured ports, and bus/protocol definitions remain the next feature pass.

## Service contract

`POST /transactions` accepts `validation_mode: "authoring"` for manual UI edits. Its default remains `"strict"` for existing clients. Both modes use private transaction copies and commit atomically. Authoring mode does not start interface elaboration or SV lint.

Manual operations include `delete_component_port`, `update_parameter`, and `delete_parameter`, in addition to existing structural operations. Bulk port entry sends one transaction containing all `add_component_port` operations. Manual actions do not use AI Assistant proposals.

`POST /entities/{kind}/{entity_id}/verify` accepts `expected_source_revision_hash` and an exact package binding. A stale request returns 409. Snapshots include revision-scoped verification receipts. Document Sections include implementation presence and preview mode before parent payload bodies are removed for A2UI delivery. Normal document reads return cached Section checks and do not start a compiler.

Reading the RTL Activity menu also avoids interface elaboration. It reports a cached failure when available, or states that validation is deferred. The UI still requires a current passing receipt. Direct API generation retains its full launch-time validation.

Cycle-accurate SystemC availability checks its source profile and compiler paths without starting a compiler. Its explicit generation still compiles the project. Default full validation remains available to existing callers.

The Python API and TypeScript document client carry the same authoring mode, operation, metadata, and verification fields. Circuit launch and save callbacks use the exact package binding, including when another Spec opens. Circuit manual saves use authoring validation under the package lock. Relaunch refreshes an existing Circuit through the source-reload protocol, and an active draft blocks binding replacement. The Circuit document format is unchanged.

## Regression and acceptance

Lower-layer checks cover saved invalid SV, compiler-free reads/saves, atomic port batches, parameter resolution, stale verification, missing tools, and projection metadata. Browser checks cover readable names, repeated port entry, duplication/deletion, independent bus offsets, status updates after reopen, and stale command responses. Existing browser suites cover focus, themes, exports, persistence, and source conflicts.

Run the profiles in sequence. Their builds share the packaged UI output directory.

```bash
scripts/test-all.sh fast
scripts/test-all.sh integration --scope spec,circuit,activities,shared
scripts/test-all.sh regression
```

Full regression includes the three live model smoke checks. Report missing required prerequisites as incomplete. Optional SystemC/CIRCT skips do not provide SystemC coverage. Use the [acceptance catalogue](../ui-test-scenarios/README.md) for manual review and retain screenshots, source, generated projects, lint logs, and scored records under `temp/TEMP_spec2gds_acceptance/<run-id>/`. The catalogue and this contract are independent of any earlier case result.
