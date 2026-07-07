import { expect, test } from "@playwright/test";

const generatedDirectory = "agent-spec://samples/generated";
const documentPath = "/workspace/spec2gds/spec2gds/agent_spec/samples/generated/synthetic_basic_with_ipxact.spec";

const snapshot = {
  document: {
    blocks: [
      {
        block_id: "h1-synthetic-basic-sample",
        block_type: "heading",
        text: "Synthetic basic sample",
        display_text: "Synthetic basic sample",
        level: 1,
        heading_id: "h1-synthetic-basic-sample",
        editable: true,
        editable_reason: "",
        links: [],
        table_rows: []
      },
      {
        block_id: "p-intro",
        block_type: "paragraph",
        text: "This small agent-spec is generated for spec2gds smoke testing.",
        display_text: "",
        editable: true,
        editable_reason: "",
        links: [],
        table_rows: []
      }
    ],
    section_groups: [],
    links: [],
    diagnostics: []
  },
  relations: {
    version: 2,
    section_groups: [],
    ipxact_attachments: {
      "h1-synthetic-basic-sample": [{ file_path: "spec_data/ipxact/sample_component.xml" }]
    }
  },
  ipxact_components: [
    {
      file_path: "spec_data/ipxact/sample_component.xml",
      component: {
        vendor: "acme",
        library: "peripherals",
        name: "sample_component",
        version: "1.0"
      },
      interfaces: [
        {
          name: "apb_slave",
          mode: "slave",
          bus_type: {
            vendor: "amba.com",
            library: "AMBA4",
            name: "APB",
            version: "r0p0"
          },
          abstraction_type: {
            vendor: "amba.com",
            library: "AMBA4",
            name: "APB_rtl",
            version: "r0p0"
          },
          port_maps: [{ logical_port: "PCLK", physical_port: "pclk" }]
        }
      ],
      diagnostics: []
    }
  ],
  active_section_versions: {},
  diagnostics: []
};

const agentDocumentState = {
  document_id: "doc_test",
  blocks: [
    {
      block_id: "h1-synthetic-basic-sample",
      title: "Synthetic basic sample",
      level: 1,
      tags: ["ip"]
    }
  ],
  artifact_refs: {},
  attachments: {}
};

test.beforeEach(async ({ page }) => {
  await page.route("http://127.0.0.1:8000/files?**", async (route) => {
    await route.fulfill({
      contentType: "application/json",
      body: JSON.stringify({
        directory: generatedDirectory,
        parent: null,
        entries: [
          {
            name: "synthetic_basic_with_ipxact.spec",
            path: documentPath,
            entry_type: "file"
          }
        ]
      })
    });
  });

  await page.route("http://127.0.0.1:8000/documents/snapshot?**", async (route) => {
    await route.fulfill({ contentType: "application/json", body: JSON.stringify(snapshot) });
  });

  await page.route("http://127.0.0.1:8000/agent-spec/documents/open", async (route) => {
    await route.fulfill({ contentType: "application/json", body: JSON.stringify(agentDocumentState) });
  });

  await page.route("http://127.0.0.1:8000/agent-spec/blocks/**/actions", async (route) => {
    await route.fulfill({
      contentType: "application/json",
      body: JSON.stringify({
        actions: [
          {
            action_id: "agent_spec.inspect",
            title: "Inspect Agent Spec",
            summary: "Validate graph, tags, versions, and artifact references."
          }
        ]
      })
    });
  });
});

test("loads a generated .spec document through the editor shell", async ({ page }) => {
  await page.goto("/");

  await expect(page.getByRole("heading", { name: "Agent-Spec Editor" })).toBeVisible();
  await expect(page.getByText("Choose an agent-spec file.")).toBeVisible();

  await page.getByRole("button", { name: /synthetic_basic_with_ipxact\.spec/ }).click();

  await expect(page.getByRole("heading", { name: "Synthetic basic sample" })).toBeVisible();
  await expect(page.getByText("This small agent-spec is generated for spec2gds smoke testing.")).toBeVisible();
  await expect(page.getByRole("button", { name: "Inspect Agent Spec" })).toBeVisible();
  await expect(page.getByText("Document loaded.")).toBeVisible();
});
