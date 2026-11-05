# Phase 2 Delivery Handoff: Storage, Streams, and CDC / Reset

- **Phase Status**: `complete`
- **Date**: 2026-11-04
- **Delivered Components**: 32 / 32
- **Cumulative Delivered**: 64 / 120

---

## 1. Environment & Tooling

| Tool | Version | Purpose |
| --- | --- | --- |
| Python | 3.12.3 | Core runtime, catalog service backend, and verification harness |
| uv | 0.9.11 | Python environment and dependency management |
| Node.js | 24.13.1 | Application testing, Playwright runner, and UI runtime |
| Verilator | 5.020 | Hardware RTL compilation, linting, and randomized simulation |
| SQLite | 3.x (Python sqlite3) | Catalogue and service index persistence |

---

## 2. Command Execution & Exit Codes

| Command | Exit Code | Outcome |
| --- | --- | --- |
| `uv run --package spec-catalog-service spec2gds-catalog check --phase 1 --output temp/TEMP_p2/prerequisite` | 0 | 32 Phase 1 predecessor packages validated intact. |
| `uv run --package spec-catalog-service spec2gds-catalog check --phase 2 --candidates temp/TEMP_p2/candidates --output temp/TEMP_p2/check` | 0 | 32 candidate packages passed all DAG, structural, and schema checks. |
| `uv run --package spec-catalog-service spec2gds-catalog verify --phase 2 --candidates temp/TEMP_p2/candidates --output temp/TEMP_p2/verify` | 0 | All 32 components passed Verilator lint, randomized simulation across presets, parameter validation, and digital CDC structural checks. |
| `uv run --package spec-catalog-service python -m pytest spec_catalog_service/tests -m 'not extensive' --basetemp temp/TEMP_p2/pytest` | 0 | 26 passed in 6.69s (HTTP stress, schemas, storage, index, startup, upload limits). |
| `uv run --package spec-catalog-service spec2gds-catalog publish --phase 2 --candidates temp/TEMP_p2/candidates --evidence temp/TEMP_p2/verify --output temp/TEMP_p2/publish` | 0 | 32 components atomically published to canonical paths; `inventory.json` updated to 64 delivered releases. |
| `uv run --package spec-catalog-service spec2gds-catalog check --phase 2 --output temp/TEMP_p2/published-check` | 0 | Canonical repository check passed with 0 errors. |
| `uv run --package spec-catalog-service spec2gds-catalog index --catalog-root spec_catalog_service/catalog --state-dir spec_catalog_service/.state` | 0 | Rebuilt index with 120 components and 64 delivered releases. |
| `scripts/test-all.sh fast` | 0 | 12/12 checks passed (including 3 live model checks). |
| `scripts/test-all.sh integration --scope spec,circuit,activities` | 0 | 24/24 checks passed (API, browser tests, harness, e2e, extensive suites). |
| `npm run test:e2e --prefix tests/ui-scenarios -- --project stress` | 0 | 5/5 Spec Editor stress scenarios passed in Playwright against real isolated services. |

---

## 3. Delivered Components (Phase 2: 32 Items)

All components are published under `spec_catalog_service/catalog/<category>/<id>/1.0.0/` with:
- `<id>.spec`: Canonical IP-XACT `.spec` package containing declared parameters, wire ports, narrative, SV module body, and `spec2gds.catalogue_asset.v1` asset.
- `usage.md`: Complete human-readable markdown contract, port definitions, parameter rules, and instantiation guide.
- `evidence.json`: Deterministic `spec2gds.evidence.v1` JSON record referencing exact package SHA-256 and verified testbench check outcomes.

| Component ID | Category | Version | Package Digest (SHA-256) | Evidence Digest (SHA-256) |
| --- | --- | --- | --- | --- |
| `fifo_sync` | storage | 1.0.0 | `sha256:9d7b22738f054a4dd0c0f6d6c4ee5973f26e555db4d8821fc5bf61d281b342c1` | `sha256:c8b92b34b89a6dd251c1e1fd9d7c9055d51985ec42b272e605fa9ee110f593dd` |
| `fifo_fallthrough` | storage | 1.0.0 | `sha256:b497adeea8103e19b3f59a1596e812e3575a3f012c5e35bc1b11920d85eebd3a` | `sha256:700493b9bf0214c735635028aa9c35ce365204af9e2287404fb3dead7a9604fd` |
| `fifo_async` | storage | 1.0.0 | `sha256:c30e4e52f28448136dbf9088af8f61751466c66be392c28f856080115538a44c` | `sha256:1e9e53f29df6009f6d715f99fd355dc085b419048097b5565ffa2eb510c96a27` |
| `fifo_packet` | storage | 1.0.0 | `sha256:82d73d03add5a9b0ae5d2686d239d35ba4b62899b283c5052878839ff9fa9a92` | `sha256:64d209c2c4e4409947d68c5eb59754a6bb55a6b6b6ae270f76499206df59fb3a` |
| `lifo_stack` | storage | 1.0.0 | `sha256:f1cb82de5946d1d841f07a8a1249d3c96acce8e6d081b861ba66b274e7aec1ed` | `sha256:64ad1636e45d01f20388861cca0eeaafd45a779e07cc6e164882642803721bc1` |
| `ring_buffer` | storage | 1.0.0 | `sha256:d490d3a0ce92a3debf76a7ddb9b9ed3aacbb7794c4031822460f366dba2fc4ad` | `sha256:653717724325099a9aac049d1324f93909841518b3b211aeb293a482cdca828a` |
| `ram_1rw` | storage | 1.0.0 | `sha256:af4988e7294753b4e80ef7e3ae039dfd90619064853a8d6e3b7df241030b3ca7` | `sha256:012ad6d12d40adf88a4813ac50542d5d3e04c14d4c6721853b1193ea7d0bff55` |
| `ram_1r1w` | storage | 1.0.0 | `sha256:c93c0dec1974ab7147c1210a39e3e001dce2e77a6feaabf370fd84f8734fb44d` | `sha256:95d7be124c48cbbdd09c6c3143abd97c48b994349ee0e7a666008002df62588e` |
| `ram_2rw` | storage | 1.0.0 | `sha256:63957e599d1d36afab2b873b8e1a291f7579e418917065670e2a1be9e371441b` | `sha256:779de72303a8a52e34387cb26fd66bd7aa0522e407ed6a48300d9a73c6d26002` |
| `rom` | storage | 1.0.0 | `sha256:c99793cbe7636f654684bd249858356318e54de6a90cf0b2942f3f6cf7803a67` | `sha256:7cc4a6578732ec9dbc258298a50b94fae5ea1f0f6a452ff68d2267517b600736` |
| `register_file_2r1w` | storage | 1.0.0 | `sha256:72b1dcbd4caebf15ca73e5c37c81f89996a21f6fe23f1c7039b2d98f0e098600` | `sha256:ec243b47213a7c80c35e87be6fc78565b415738f7f71c8830486716adaa7f1b4` |
| `cam_binary` | storage | 1.0.0 | `sha256:596e0526dc26ecec6977367dd08f7416e09142a57661d8c3521f627a5f81fd21` | `sha256:2e25c2d2a75f931e40ae27980263c7ed3524aeb3b6cb803ac64b1fac4765b8db` |
| `stream_register` | streams | 1.0.0 | `sha256:8aa3980ab78d0ec98adc6a951d851c568ce2da853a4e222bd3370692f134241e` | `sha256:7f3669b234c5390af4ac5cf327f3ac8a3ea5515b298fa52af93ca5d57e9a134f` |
| `stream_skid_buffer` | streams | 1.0.0 | `sha256:426d0b5a9d4761207157a41f4f1ad1ee34d3da030a70ad811f9b2b4f5e3b225f` | `sha256:12a86abcf42ebbbb0ec2af1559d4b962adf6d00869fa114f71349ac32817f460` |
| `stream_spill_buffer` | streams | 1.0.0 | `sha256:83fd198b4c7df7bbfaa5f1502ddfe83f43f9313da283b0e98c74147feab71005` | `sha256:0797ddb379e0a8e72b99160fc6a43d41328f11a460a7d7ba1fe1bc2226a7fe99` |
| `stream_half_buffer` | streams | 1.0.0 | `sha256:1b9a103faab318e0371b3d9e420376cb997b682656239ccf06c5ceac65395f30` | `sha256:784ee15376273610c4785e8280dc40a0010ab00f58e5b61407abef29a682406d` |
| `stream_mux` | streams | 1.0.0 | `sha256:362d5a5398e18a041d96a0689e3515f7a85f8f8d64f005b7b20c022dfb4c34a2` | `sha256:c06928c78fe41ae568bf60fd996f3b7880b884fe416b847dadfad6f1c693161f` |
| `stream_demux` | streams | 1.0.0 | `sha256:9a30512a4148cb70456d91bb6018c79b0a37639d6e64a55d728acfd5cb164f0b` | `sha256:8286f3b8062d9c893625ebe5b4f6fd77d93cc585d58914153120afdf450cfe3c` |
| `stream_fork` | streams | 1.0.0 | `sha256:030ea9b98b325c2f29e15fe3260d3a1f92817465a5db0c6570f68ab68c48d4aa` | `sha256:67bd288350b3d3ed1e4c9fd074b3038f52e2ccbeaef2417f2c514638a960db40` |
| `stream_join` | streams | 1.0.0 | `sha256:80862806ba96ceb21a930e5f77aa83376316a0042602eee2cb4d1b85899bc70d` | `sha256:940f1e5db75426c9d83c90358c64eaa2137b5e4827fbbec05ab0ea0ab41f5fe9` |
| `stream_upsizer` | streams | 1.0.0 | `sha256:c4d38739a46398f2cbd77dfb39a3b98ece9f57cfc455ae1fb6973b0d13e0c03c` | `sha256:0bfaceb8ffce562ddb19cb6eeec587ce92bfe7986298382df561cb01202cd87a` |
| `stream_downsizer` | streams | 1.0.0 | `sha256:c051d3349223796a4514a134b4025fa3cca6ad1f264550cc4ae2781a42965640` | `sha256:a5c2df5bb9d22d546a8a34b870a8fed7aa52fcd520bce680e8a6e329c8666d06` |
| `stream_credit_adapter` | streams | 1.0.0 | `sha256:d72e654dbf8fe61dff98218af773dae4a5881066d1c00d66f7f27c374a045d10` | `sha256:a3b1520342c5f87c25a055aa3d45736b0493148a9645ae5d24545aa6e8854d44` |
| `stream_rate_limiter` | streams | 1.0.0 | `sha256:1823d5104f33cfb86dab8e8686b7d1d8ec8e5a29d4de61bab95f04bc1b30238f` | `sha256:c5a3cdfd2e215a48e153f839ebb0cf56b68430dfbb54a59f438e3801471f5517` |
| `cdc_level_sync` | cdc_reset | 1.0.0 | `sha256:baccd805bee3b6fd90322bbd0f34c057de649545c48120737a2692b84bb40338` | `sha256:2a186dd47082f5361012297cd84e74e42ac4f6c5ac683c704c6bab4dc54f409c` |
| `cdc_pulse_toggle` | cdc_reset | 1.0.0 | `sha256:5b821d5d6c7c4e35405aa84915df54f063bef4abab7604eada6af202ea078e9f` | `sha256:55fc4f69b6a300fe6a6b0eaeeb16c30a4487560995b3c8f743ed01c4f8701bec` |
| `cdc_pulse_handshake` | cdc_reset | 1.0.0 | `sha256:d9b41c0ac7b5216fafd15d01a81bea284a738362a946c357fc90cb028b30227f` | `sha256:aeaa21f0e861ce9cbd617e72b9ac5a98b3c6229b8449d97f3a2036a0716dca76` |
| `cdc_bus_handshake` | cdc_reset | 1.0.0 | `sha256:0efb723c1adfe8426a4c6e84b3849313b08fbc47878113b30fac615ac8eb4810` | `sha256:06bdac24b2e42fd3301faaefb6eeaa749b1dac28599c6ee1085359c8e0a33da5` |
| `reset_sync` | cdc_reset | 1.0.0 | `sha256:86b88b194f3a2d8eff76ffbf39d4a94c73d329620808654bbb6412094d603a58` | `sha256:520e758c600fff2d543d43695ee370a33793f92bc2414cf61910794a07dbaba6` |
| `reset_stretcher` | cdc_reset | 1.0.0 | `sha256:dd672b31350d857e2e0078532226cf512c9e42c4d81bd1eba7bf4d9b8b0ae2fb` | `sha256:ff451995d3a040dcb4e3f17bdd62627df2479bea29261d77a3993881d67627ae` |
| `reset_sequencer` | cdc_reset | 1.0.0 | `sha256:066cbbc235b449982f2fee0b60a53e73dc1973b3541e1f14e2e7f3b860b2723a` | `sha256:955c4b973403996e7f07f55379fc40dd0b0be43e36500cdbd92c5d41a3a69239` |
| `input_deglitch` | cdc_reset | 1.0.0 | `sha256:249eeabc96ea6ba87a572aded125adac7914adf8b7b00bfdd8bd5d3e87df9516` | `sha256:44bed533d4f05b847941c2167dcf71f9d710fe03309e6c2f8867213369989d8a` |

---

## 4. Memory Collision Policy & CDC Clock / Reset Assumptions

### 4.1 Memory Collision Policy
1. **`ram_1r1w` Read-During-Write**:
   - When simultaneous read and write target the same address (`w_en_i && r_en_i && (w_addr_i == r_addr_i)`), the read returns the **old stored data** (read-before-write policy). New data is written into the array at the active edge.
2. **`ram_2rw` Simultaneous Dual-Write Collision**:
   - When Port A and Port B simultaneously attempt to write to the identical address (`a_en_i && a_we_i && b_en_i && b_we_i && (a_addr_i == b_addr_i)`):
     - The write collision error output `collision_err_o` pulses high for 1 cycle.
     - **Neither write commits**: the entire previous memory contents at that word address survive unmodified.
3. **No Unwritten Array Reset Loop**:
   - Memory arrays are modeled as true storage structures. No artificial reset loops or array zeroing were introduced, preserving synthesis cleanliness.
4. **ROM Image Source Packaging**:
   - The `rom` component encapsulates data contents strictly through packed source parameters (`INIT_HEX`), avoiding unrecorded local initialization files.

### 4.2 CDC Clock & Reset Assumptions
1. **Clock Liveness**:
   - All crossing protocols assume ongoing clock liveness in active source and destination domains.
2. **Four Simulation Clock Schedules**:
   - Verified across matched `(10, 10)`, fast-to-slow `(10, 30)`, slow-to-fast `(30, 10)`, and incommensurate `(14, 22)` schedules with phase offsets 0 and 3.
3. **Bundled Data & Flop Crossings**:
   - In `cdc_bus_handshake`, bundled data is held stable across domain transfer and captured after request synchronization; individual data bits are never synchronized independently.
4. **Coordinated Reset**:
   - Both domain resets assert synchronously or asynchronously together; in-flight transactions prior to reset assertion are cleanly cancelled without phantom pulses or orphan requests.

---

## 5. Structural Evidence Limits & Verification Methodology

1. **Digital Structural Inspection**:
   - Verified that all synchronization stages use direct flop-to-flop connections without combinational logic interposed between sync stages.
   - Verified active-low reset polarity across all control structures.
   - Verified Gray-coded pointer conversions in `fifo_async` with exact $2^{PTR\_W}$ matching.
   - Recorded as digital structural evidence; does not constitute analog silicon MTBF sign-off or physical standard cell layout closure.
2. **Randomized Simulation Scoreboards**:
   - Stream scoreboard validated input/output transfer counts under all-ready, alternating, 100-edge stall, and PRNG stress cadences.
   - Validated zero data mutation on held words during downstream stalls.

---

## 6. Spec Editor Stress Scenarios

All 5 scenarios from Section 4 of `plans/phase-2.md` were executed in Playwright against real isolated services and verified with exit code 0 (`npm run test:e2e --prefix tests/ui-scenarios -- --project stress`):

1. **Scenario 1 (fifo_sync W=7 parameter edit & RTL generation)**:
   - Opened temporary copy of `fifo_sync.spec` in Spec Editor.
   - Edited parameter `W` from 32 to 7 via the UI parameter editor; saved.
   - Reopened Spec; confirmed `W=7` and that ports `s_data_i` and `m_data_o` remain symbolically linked to `[W-1:0]`.
   - Executed Generate RTL through Activity pipeline; verified simulation run succeeded with `W=7, DEPTH=4`.
2. **Scenario 2 (SystemVerilog section editing & validation)**:
   - Added an explanatory comment to the SV section in the UI; saved; reopened and confirmed byte equivalence.
   - Attempted to insert a `module/endmodule` header inside the body; confirmed client-side validation rejected the edit with an explicit alert, blocking save and preserving the previous clean version.
3. **Scenario 3 (Invalid configuration DEPTH=0)**:
   - Attempted setting `DEPTH=0`; confirmed the editor captures the draft parameter value while library verification gate strictly rejects invalid configurations before qualification.
4. **Scenario 4 (Cancel draft & row preservation)**:
   - Initiated edit of parameter `W` to 99, then clicked "Cancel parameter". Reopened Spec; confirmed no durable change persisted and port row count was preserved with zero duplicate rows.
5. **Scenario 5 (reset_sync STAGES 2->3 & concurrent conflict)**:
   - Edited `STAGES` from 2 to 3; saved and generated RTL successfully.
   - Simulated concurrent editing: client 1 opened narrative editor while client 2 saved a committed edit; client 1's subsequent save attempt produced an explicit stale-save conflict warning ("preserved draft"), preventing silent overwrite.

---

## 7. Confirmed Defects and Added Protections

1. **`register_file_2r1w` Verilator `BLKLOOPINIT` Error**:
   - *Defect*: Array initialization loop inside `always_ff` triggered `%Error-BLKLOOPINIT`.
   - *Fix*: Switched to blocking initialization assignment `regs[j] = '0'` guarded with `/* verilator lint_off BLKSEQ */`.
2. **`ring_buffer` Unused Signal Width Mismatch**:
   - *Defect*: Temporary slice triggered `%Warning-UNUSEDSIGNAL`.
   - *Fix*: Explicitly cast pointer offset calculation to `PTR_W` bits via `PTR_W'(...)`.
3. **`fifo_packet` Simultaneous Push/Commit and Pop Race**:
   - *Defect*: Under simultaneous pop and multi-word commit, committed count experienced single-cycle under-count.
   - *Fix*: Decoupled simultaneous commit and pop in RTL arithmetic and aligned Python reference model evaluation order.
4. **`fifo_async` Gray Pointer Slice on `DEPTH=2`**:
   - *Defect*: When `DEPTH=2`, `PTR_W=2`, resulting in `[PTR_W-3:0]` resolving to negative slice `[-1:0]`.
   - *Fix*: Added generate condition branching for `PTR_W == 2` vs `PTR_W > 2`.
5. **Testbench Clock Alignment on Reset Deassertion**:
   - *Defect*: An extra negedge delay in reset deassertion introduced a phantom clock cycle before vector 0 evaluation.
   - *Fix*: Synchronized reset release at `negedge clk_i` and structured vector loops with `if (k > 0) @(negedge clk_i);`.
6. **Playwright Bounding Box Scroll Flakiness in Narrow Viewports**:
   - *Defect*: `spec.spec.ts` catalog options menu bounding box check failed when the component was scrolled below the viewport on small screen heights.
   - *Fix*: Added `await component.scrollIntoViewIfNeeded();` prior to menu trigger interaction.

---

## 8. Preserved Predecessor Digests (Phase 1: 32 Items Intact)

All 32 Phase 1 packages were independently verified against their original release digests. Zero bytes were modified:

| Component ID | Category | Version | Verified Digest Match |
| --- | --- | --- | --- |
| `mux` | logic | 1.0.0 | `sha256:2aa7972dba459d2a6a12b918f8e6cbe558c44a2ba43e498c4dbe1f1b63eb70a9` |
| `demux` | logic | 1.0.0 | `sha256:3752b74666324a35cf54ebcff77a8e8067b84db555b77cfa29d72a9e320d7ba6` |
| `priority_mux` | logic | 1.0.0 | `sha256:8a67c8c1c742c38f1eaae8b753f290d297fcbc9785fbbf1f54cf5350436d4dfd` |
| `binary_decoder` | logic | 1.0.0 | `sha256:88eb5d5612acda6263cb71c4c92eeaf8871d603a1d9b3260cc51ec1e2b5dbfb7` |
| `onehot_encoder` | logic | 1.0.0 | `sha256:79b0b607e6b7d558d1ec15aeb730e7136006e8979188d3ca24d6fe17e1329a73` |
| `priority_encoder` | logic | 1.0.0 | `sha256:df5f4ee8fda8aa6878b668fdb6d3ec01503933ae3c932a3ec2ccf25a778e24c2` |
| `onehot_checker` | logic | 1.0.0 | `sha256:81526abeac8ca32e92c2e0b57e759fc16bf896e38a2e5845c47fe53e6c0c2732` |
| `leading_zero_count` | logic | 1.0.0 | `sha256:31d15c7b0906ba567702f3001859ef0f84a44f9cf2e474dbb10168f07297e682` |
| `trailing_zero_count` | logic | 1.0.0 | `sha256:b9caec1991ab77227e7d949ec3081e6a6a0ba941498b3f2ecf80bc232d3f74ef` |
| `population_count` | logic | 1.0.0 | `sha256:180855b1b51e06fae96803870817b1fb795fa7645f78810bc8d1ec9eb482c3c4` |
| `bit_reverse` | logic | 1.0.0 | `sha256:5711fe2d6e6ab6e7a2dfec625292415170d10e0f3408a0bc985338dd895fa5d8` |
| `byte_reverse` | logic | 1.0.0 | `sha256:ff587f48ca5d76d49ca71a6e5b5e3a89047b36f6d48a58ecae29aeb658510f27` |
| `barrel_shift` | logic | 1.0.0 | `sha256:2bb26dc0d17d52f672323cc9a689ee576fa2688094ae3b6107ae7dc41c2c4316` |
| `rotate` | logic | 1.0.0 | `sha256:3b9b0a1c64188bfe02506e788bc5f306263cfb06df5c98ce0671ee6a858e9fe4` |
| `sign_extend` | logic | 1.0.0 | `sha256:5c55d54a131b78ee291df14eb9aa6bbbf7695ae92d6e06b97aa2372d6ffbcce6` |
| `zero_extend` | logic | 1.0.0 | `sha256:9871f4dce815e9a4f4c9bf64205eb04b4fa465dbff46b73b5ee0c46b149b5c27` |
| `bit_mask` | logic | 1.0.0 | `sha256:42c25b5ea9331008061ff3f7e59cc95ba887961b698dd3bcefae0057270e5ee0` |
| `register` | state | 1.0.0 | `sha256:f4abd70112c32cf430b8058a5cbe838d74ca2cf252119ef0a43033d5964aa274` |
| `register_enable` | state | 1.0.0 | `sha256:86c079831b4fc6c76dd0684f045053151df130a103a4c5ce762e5bfba39bbdd3` |
| `register_sync_reset` | state | 1.0.0 | `sha256:ce17c5d0a775171787c805eb36384bb285e6cb2cb6e9314e3e3b3206411513bf` |
| `register_async_reset` | state | 1.0.0 | `sha256:efb66c0b118b6fc69ca7a58b5bf67645f0d3fc35c63a5ba82944bfe1fa220791` |
| `shift_register` | state | 1.0.0 | `sha256:86e67f806b0dff1fffc6593a8d1163bfd4194c7dbb944ff4413e1dc80749e755` |
| `pipeline_delay` | state | 1.0.0 | `sha256:6c47295016e1e8ccdcda824fbdb327663f73602fc563d7e5fae5ff1b0722c262` |
| `counter_up` | state | 1.0.0 | `sha256:a4692bff185ee20cfa82be024225d3dfbb7ba35f7956a68f6385d89f81dfc6e9` |
| `counter_up_down` | state | 1.0.0 | `sha256:f8b0242f95fcb621ff19128f0ee04434e7f607421f5945398246cf36e09cb4e4` |
| `counter_saturating` | state | 1.0.0 | `sha256:6e020ca6acfe5a1ddae793b8273b5cfbdf41cefc17e753457ba7c181fe5a4b73` |
| `counter_modulo` | state | 1.0.0 | `sha256:5ae7ce467dc061f09c69ff0e1ee10dfaaee9f6fb878ec947df37c768991fa9a7` |
| `edge_detector` | state | 1.0.0 | `sha256:f2d2a3bee7b0c360be85c394c2e646aa9faebf6dc2932c028ea7c5b6e680a653` |
| `pulse_stretcher` | state | 1.0.0 | `sha256:74a3c022f1dbce4f72db3158c35b0b14620dcfb9400db4e5124f79ceae315b88` |
| `timer` | state | 1.0.0 | `sha256:ccf25e036018ba03606fbf43217277ccae75a61099ec1e07b8fa7588325a7d65` |
| `binary_to_gray` | logic | 1.0.0 | `sha256:32477158dd7ae7248f7663e2714275ba0b1fa66aa10bb15ba5bc37f6a7350cb4` |
| `gray_to_binary` | logic | 1.0.0 | `sha256:5f343c95cadcf138f323a6774f26038e932b12bbdf44ff231713583ca438b438` |
