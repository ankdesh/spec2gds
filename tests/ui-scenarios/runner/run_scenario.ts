/**
 * UI Automation Scenario Runner for spec2gds.
 *
 * Executes natural language test scenarios using Playwright against
 * the DeepSeek Harness AI Assistant UI (6013) and verifies results
 * in both the Assistant and Spec Editor (6010).
 */

import { chromium, type Browser, type Page } from "@playwright/test";
import { mkdirSync, writeFileSync, existsSync, rmSync } from "node:fs";
import { resolve, join, dirname } from "node:path";
import { fileURLToPath } from "node:url";

const RUNNER_DIR = dirname(fileURLToPath(import.meta.url));
const SCENARIOS_ROOT = resolve(RUNNER_DIR, "..");

interface ScenarioConfig {
  name: string;
  documentId: string;
  title: string;
  prompt: string;
  componentName: string;
  assistantUrl: string;
  specEditorUrl: string;
  headed: boolean;
  timeoutMs: number;
}

const DEFAULT_CONFIG: ScenarioConfig = {
  name: "create_spec_and_component",
  documentId: "ui_timer_spec",
  title: "UI Automation Timer Spec",
  prompt: "Create a timer component named timer_core with 32-bit counter, clk and rst_n inputs, and irq output.",
  componentName: "timer_core",
  assistantUrl: process.env.ASSISTANT_URL || "http://127.0.0.1:6013",
  specEditorUrl: process.env.SPEC_EDITOR_URL || "http://127.0.0.1:6010",
  headed: process.env.HEADED === "true",
  timeoutMs: 180_000,
};

class ScenarioRunner {
  private runDir: string;
  private screenshots: { step: string; filename: string; description: string }[] = [];
  private verifiedComponentDetails: any = null;

  constructor(private config: ScenarioConfig) {
    const timestamp = new Date().toISOString().replace(/[:.]/g, "-");
    this.runDir = resolve(SCENARIOS_ROOT, "results", config.name, timestamp);
    mkdirSync(this.runDir, { recursive: true });
  }

  private async captureMilestone(page: Page, stepNumber: string, name: string, description: string): Promise<string> {
    const filename = `${stepNumber}_${name}.png`;
    const fullPath = join(this.runDir, filename);
    await page.screenshot({ path: fullPath, fullPage: true });
    this.screenshots.push({ step: stepNumber, filename, description });
    console.log(`[Milestone ${stepNumber}] Captured: ${filename} - ${description}`);
    return fullPath;
  }

  private async assertServicesReady(): Promise<void> {
    console.log("Checking service health...");
    const checkEndpoint = async (url: string, name: string): Promise<boolean> => {
      try {
        const response = await fetch(url);
        return response.ok;
      } catch {
        return false;
      }
    };

    const specOk = await checkEndpoint(`${this.config.specEditorUrl}/health`, "Spec Editor");
    const assistantOk = await checkEndpoint(`${this.config.assistantUrl}/healthz`, "AI Assistant");

    if (!specOk) {
      throw new Error(`Spec Editor at ${this.config.specEditorUrl} is unreachable. Ensure services are running.`);
    }
    if (!assistantOk) {
      throw new Error(`AI Assistant at ${this.config.assistantUrl} is unreachable. Ensure services are running.`);
    }
    console.log("Both Spec Editor (port 6010) and AI Assistant (port 6013) services are healthy and reachable.");
  }

  async run(): Promise<boolean> {
    console.log(`=== Starting UI Automation Scenario: ${this.config.name} ===`);
    console.log(`Results directory: ${this.runDir}`);

    await this.assertServicesReady();

    // Clean up any existing spec file with the same document ID so we start cleanly
    const projectRoot = resolve(SCENARIOS_ROOT, "../..");
    const existingSpecPath = resolve(projectRoot, "ai-assistant/.dev/spec-documents", `${this.config.documentId}.spec`);
    if (existsSync(existingSpecPath)) {
      rmSync(existingSpecPath, { force: true });
      console.log(`Cleaned up pre-existing spec: ${existingSpecPath}`);
    }

    const browsersPath = resolve(projectRoot, "circuit-designer/.playwright-browsers");
    if (existsSync(browsersPath)) {
      process.env.PLAYWRIGHT_BROWSERS_PATH = browsersPath;
    }

    const browser: Browser = await chromium.launch({
      headless: !this.config.headed,
      args: ["--no-sandbox", "--disable-setuid-sandbox"],
    });

    const context = await browser.newContext({
      viewport: { width: 1440, height: 900 },
    });

    const page: Page = await context.newPage();
    page.setDefaultTimeout(this.config.timeoutMs);

    try {
      // Step 1: Open AI Assistant Home via authenticated launch URL
      console.log("\n[Step 1] Navigating to AI Assistant...");
      await page.goto(`${this.config.assistantUrl}/launch`, { waitUntil: "domcontentloaded" });
      await page.waitForTimeout(3000);
      await this.captureMilestone(page, "01", "assistant_home", "Initial AI Assistant home screen");

      // Step 2: Open Dialog & Create New Spec Session
      console.log("\n[Step 2] Initiating new spec creation...");
      const newSessionBtn = page.locator("button[aria-label='New session'], button.Wwdj9a_newSession").first();
      await newSessionBtn.click();
      await page.waitForTimeout(1500);

      const dialog = page.locator(".s2g-dialog");
      await dialog.waitFor({ state: "visible", timeout: 15_000 });
      console.log("Design conversation dialog opened.");

      // Switch mode to "Create new"
      const createRadio = page.locator("input[name='mode'][value='create']");
      await createRadio.check();
      await page.waitForTimeout(500);

      // Enter Document ID and Title
      await page.locator("input[name='documentId']").fill(this.config.documentId);
      await page.locator("input[name='title']").fill(this.config.title);

      await this.captureMilestone(page, "02", "spec_create_dialog", "Filled new spec creation form");

      // Submit creation form
      const submitBtn = page.locator("button.primary[type='submit']");
      await submitBtn.click();

      // Wait for dialog mask to dismiss
      await page.waitForSelector(".s2g-mask", { state: "detached", timeout: 20_000 });
      await page.waitForTimeout(2000);

      // Verify chat input is ready
      const promptInput = page.locator("textarea, [contenteditable='true'], [role='textbox']").first();
      await promptInput.waitFor({ state: "visible", timeout: 20_000 });
      await this.captureMilestone(page, "02b", "spec_created_session", "Bound conversation session active");

      // Step 3: Submit Natural Language Prompt
      console.log("\n[Step 3] Submitting prompt to assistant...");
      await promptInput.fill(this.config.prompt);
      await this.captureMilestone(page, "03", "prompt_entered", "Prompt text entered in chat input");

      const sendBtn = page.locator("button[aria-label='Send message'], button._HjNYG_primary").first();
      await sendBtn.click();
      console.log("Prompt sent. Waiting for assistant response and interactive cards...");

      // Step 4: Handle Question Composer and Details Confirmation Cards
      console.log("\n[Step 4] Processing conversation turn and proposals...");
      const startTime = Date.now();
      let proposalCardFound = false;

      while (Date.now() - startTime < 120_000) {
        // Check for Question Composer
        const skipBtn = page.locator("button:has-text('Skip'), button:has-text('跳过')").first();
        if (await skipBtn.isVisible()) {
          console.log("Question composer active. Handling interactive questions...");
          // Try selecting first option if available
          const firstOption = page.locator("[role='radio'], [role='checkbox'], button:has-text('timer_core')").first();
          if (await firstOption.isVisible()) {
            try {
              await firstOption.click();
              await page.waitForTimeout(300);
            } catch {}
          }
          // Click Next/Submit if enabled, otherwise Skip
          const nextBtn = page.locator("button:has-text('Next'), button:has-text('Submit'), button:has-text('下一步'), button:has-text('提交')").last();
          if (await nextBtn.isVisible() && (await nextBtn.isEnabled())) {
            await nextBtn.click();
          } else {
            await skipBtn.click();
          }
          await page.waitForTimeout(1000);
          continue;
        }

        // Check for Review Card / Details Card
        const reviewCard = page.locator(".s2g-review, .s2g-details, [data-review]").first();
        if (await reviewCard.isVisible()) {
          console.log("Review / details card detected.");
          await this.captureMilestone(page, "04", "proposal_review_surface", "Proposal review or details card visible");

          const continueBtn = page.locator("button:has-text('Continue proposal')");
          if (await continueBtn.isVisible()) {
            console.log("Clicking 'Continue proposal' to confirm component details...");
            await continueBtn.click();
            await page.waitForTimeout(2000);
          }

          // Wait for Approve button
          const approveBtn = page.locator("button:has-text('Approve and apply')");
          try {
            await approveBtn.waitFor({ state: "visible", timeout: 45_000 });
            await this.captureMilestone(page, "04b", "proposal_ready", "Approve and apply button ready on review card");
            proposalCardFound = true;
            break;
          } catch {
            // Keep checking in loop
          }
        }

        await page.waitForTimeout(1000);
      }

      if (!proposalCardFound) {
        throw new Error("Timeout waiting for 'Approve and apply' proposal review card.");
      }

      // Step 5: Approve Proposal & Verify Assistant Status
      console.log("\n[Step 5] Approving proposal...");
      const approveBtn = page.locator("button:has-text('Approve and apply')");
      await approveBtn.click();
      await page.waitForTimeout(3000);
      await this.captureMilestone(page, "05", "proposal_approved", "Proposal approved and committed in Assistant UI");

      // Step 6: Dual-surface verification in Spec Editor UI & REST API
      console.log("\n[Step 6] Dual-surface verification in Spec Editor...");
      const editorPage = await context.newPage();
      await editorPage.goto(`${this.config.specEditorUrl}/editor`, {
        waitUntil: "domcontentloaded",
      });
      await editorPage.waitForTimeout(2000);

      // Open the created spec document in the Spec Editor canvas
      const specDocumentPath = resolve(projectRoot, "ai-assistant/.dev/spec-documents", `${this.config.documentId}.spec`);
      try {
        const fileMenu = editorPage.getByRole("menuitem", { name: "File", exact: true });
        if (await fileMenu.isVisible()) {
          await fileMenu.click();
          const openAction = editorPage.getByRole("menuitem", { name: /Open Specification/ });
          if (await openAction.isVisible()) {
            await openAction.click();
            const pathInput = editorPage.getByLabel("Server-local package path");
            await pathInput.fill(specDocumentPath);
            await editorPage.getByRole("button", { name: "Open", exact: true }).click();
            await editorPage.waitForTimeout(2000);
          }
        }
      } catch (e: any) {
        console.warn("Could not visually open spec in editor menu:", e.message);
      }
      await this.captureMilestone(editorPage, "06", "spec_editor_verified", "Spec Editor UI showing new spec and component");

      // Cross-verify via Spec Editor API
      const snapshotUrl = `${this.config.specEditorUrl}/documents/snapshot?document_id=${encodeURIComponent(this.config.documentId)}`;
      console.log(`Querying Spec Editor Snapshot API: ${snapshotUrl}`);
      const snapshotRes = await fetch(snapshotUrl);
      if (!snapshotRes.ok) {
        throw new Error(`Failed to retrieve spec snapshot from ${snapshotUrl}: HTTP ${snapshotRes.status}`);
      }

      const snapshot = await snapshotRes.json();
      console.log(`Snapshot components count: ${snapshot.components?.length || 0}`);
      const matchedComponent = (snapshot.components || []).find((c: any) =>
        (c.vlnv && c.vlnv.includes(this.config.componentName)) ||
        (c.ref?.entity_id && c.ref.entity_id.includes(this.config.componentName))
      );

      if (!matchedComponent) {
        throw new Error(`Component '${this.config.componentName}' was not found in Spec Editor snapshot: ${JSON.stringify(snapshot.components)}`);
      }

      this.verifiedComponentDetails = matchedComponent;
      console.log(` Verified component '${this.config.componentName}' in Spec Editor:`, JSON.stringify(matchedComponent, null, 2));

      await editorPage.close();

      console.log("\n All UI Automation milestones completed successfully!");
      this.writeReport(true);
      return true;
    } catch (error: any) {
      console.error("\n Scenario failed with error:", error.message);
      try {
        await this.captureMilestone(page, "99", "failure_state", `Failure: ${error.message}`);
      } catch {}
      this.writeReport(false, error.message);
      return false;
    } finally {
      await browser.close();
    }
  }

  private writeReport(passed: boolean, errorMessage?: string): void {
    const reportPath = join(this.runDir, "summary.md");
    const content = `# Test Run Summary: ${this.config.name}

- **Result**: ${passed ? "PASSED" : "FAILED"}
- **Timestamp**: ${new Date().toISOString()}
- **Document ID**: \`${this.config.documentId}\`
- **Component**: \`${this.config.componentName}\`
- **Prompt**: "${this.config.prompt}"
${errorMessage ? `\n### Error Details\n\`\`\`\n${errorMessage}\n\`\`\`\n` : ""}
${this.verifiedComponentDetails ? `
### Verified Component in Spec Editor
\`\`\`json
${JSON.stringify(this.verifiedComponentDetails, null, 2)}
\`\`\`
` : ""}

## Milestone Screenshots

| Step | Milestone | Screenshot | Description |
| --- | --- | --- | --- |
${this.screenshots.map(s => `| ${s.step} | ${s.filename} | [${s.filename}](./${s.filename}) | ${s.description} |`).join("\n")}
`;
    writeFileSync(reportPath, content, "utf8");
    console.log(`Summary report written to: ${reportPath}`);
  }
}

async function main() {
  const runner = new ScenarioRunner(DEFAULT_CONFIG);
  const success = await runner.run();
  process.exit(success ? 0 : 1);
}

main().catch(err => {
  console.error("Fatal test runner error:", err);
  process.exit(1);
});
