# spec2gds AI Assistant

This package adds permanent Spec/Circuit bindings, owner tools, reviews, and
execution presets to DeepSeek Harness. Harness owns the chat shell, model loop,
native sessions, and transcript. Spec and Circuit services own their documents.

Use the maintained guides:

- [System contract](../docs/ai-assistant.md): required behavior and tool rules.
- [Operations and tests](../docs/ai-assistant-operations.md): setup, configuration,
  CLI, diagnostics, test commands, and packaging.
- [TEMP implementation gaps](../docs/TEMP-ai-assistant-implementation-gaps.md):
  current differences from the required behavior.
- [Reusable flows](../docs/ai-assistant-flows.md): definitions, execution, controls,
  approvals, and recovery.
- [Future work](../docs/ai-assistant-future-work.md): proposed improvements.

The contract includes accepted changes that still need code work. Check TEMP
before assuming that a workflow is complete. Model output alone is not proof of
a saved document.

From the repository root, prepare the source-linked product:

```bash
scripts/setup-all.sh
```

Then run development or checks from this directory:

```bash
npm run dev
```

```bash
npm run typecheck
npm test
npm run build
npm run test:harness
```

Set the provider key before model calls. Use the operations guide for owner startup,
source-pin verification, browser dependencies, and flow controls and Spec Editor decisions.
Keep configuration defaults in that guide. Do not create another behavior or
setup reference here.
