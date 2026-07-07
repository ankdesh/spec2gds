# Agent-Spec UI Testing

The local document editor has a Playwright smoke test under:

```text
spec2gds/agent_spec/document/editor_web/tests/
```

Install frontend dependencies:

```bash
cd spec2gds/agent_spec/document/editor_web
npm install
```

Install the managed Chromium browser:

```bash
npx playwright install chromium
```

Run the UI test:

```bash
npm run test:e2e
```

In restricted environments, keep npm, temporary files, and browser downloads
inside the workspace:

```bash
mkdir -p .npm-cache .tmp .playwright-browsers
TMPDIR="$PWD/.tmp" \
PLAYWRIGHT_BROWSERS_PATH="$PWD/.playwright-browsers" \
npm_config_cache="$PWD/.npm-cache" \
npx playwright install chromium

TMPDIR="$PWD/.tmp" \
PLAYWRIGHT_BROWSERS_PATH="$PWD/.playwright-browsers" \
npm_config_cache="$PWD/.npm-cache" \
npm run test:e2e
```

The current desktop sandbox can install Playwright and download Chromium, but
Chromium cannot launch until system browser libraries such as `libnspr4.so` are
installed. On a normal development machine or CI image, use:

```bash
npx playwright install-deps chromium
```

That command may require sudo/root access.
