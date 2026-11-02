# spec2gds AI Assistant

This package adds permanent Spec/Circuit bindings, product tools, reviews, and
execution presets to DeepSeek Harness. Harness owns the chat shell, model loop,
native sessions, and transcript. Spec and Circuit services own their documents.

Use the maintained guides:

- [System contract](../docs/ai-assistant.md): required behavior and tool rules.
- [Operations and tests](../docs/ai-assistant-operations.md): setup, configuration,
  CLI, diagnostics, test commands, and packaging.
- [Package releases](../docs/harness-packages.md): registry access, selected profiles, and upgrades.
- [Reusable flows](../docs/ai-assistant-flows.md): definitions, execution, controls,
  approvals, and recovery.

Model output alone is not proof of a saved document. An applied service receipt proves saved content.

From the repository root, install the locked packages:

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

Set the provider key before model calls. Use the operations guide for service startup,
package release verification, browser dependencies, and flow controls and Spec Editor decisions.
Keep configuration defaults in that guide. Do not create another behavior or
setup reference here.
