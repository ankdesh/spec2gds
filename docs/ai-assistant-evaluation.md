# AI assistant evaluation

The assistant keeps a versioned, non-production evaluation corpus in
`ai-assistant/evals/`. Each case names an immutable binding, an initial owner
fixture, a user intent, allowed outcomes, expected operation families, and
safety assertions. Cases compare owner semantics and invariants rather than
requiring one exact model wording or operation order.

The initial corpus contains the seven historical Spec requests plus document
creation, invalid reference, stale Spec and Circuit revisions, valid and
invalid Circuit connectivity, and an ambiguous request with only safe allowed
outcomes. It contains no credentials or production transcripts.

## Run

Use Node.js 24 or newer for the combined assistant and Circuit checks.

```bash
cd ai-assistant
npm run setup:harness
npm run eval -- --output /tmp/spec2gds-assistant-eval
```

The setup step prepares the pinned DSH checkout used by evaluation and replay.
It can be omitted on later runs while that checkout remains clean, pinned, and
built.

Pass `--session /path/to/session.jsonl` to calculate metrics from an
uncompressed DSH Session snapshot. The command writes versioned `events.jsonl`,
`results.json`, and `metrics.json` files to the selected output directory.

The real Harness integration test separately records a headless Session and
replays it with `@deepseek-ai/dsh-llm-replay`. It verifies that replay consumes
the same context/proposal/final-response trajectory without contacting the
provider fixture.

## Metric definitions

- Schema-valid calls are proposal calls that reach a structured product result.
- First-preview pass counts the first proposal result in a turn when it is
  `ready`.
- Proposed and applied/sent operation counts come from persisted artifacts.
- A retry is a second or later proposal call in the same user turn.
- A clarification is a terminal assistant question in a turn with no proposal.
- Latency is the durable `turn/start` to `turn/end` interval when timestamps are
  present.
- Token counts use DSH `assistant/message` usage.
- False completion is an explicit failed corpus assertion when no review is
  `applied` or `sent`.

These are raw measurements. Quality thresholds remain intentionally undefined.
