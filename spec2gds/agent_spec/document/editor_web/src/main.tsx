import React, { useEffect, useMemo, useState } from "react";
import { createRoot } from "react-dom/client";
import { ReportSurface } from "./ReportSurface";
import "./styles.css";

type Diagnostic = {
  severity: string;
  source: string;
  message: string;
  block_id?: string | null;
};

type DocumentLink = {
  href: string;
  text: string;
  block_id: string;
};

type TableRow = {
  cells: Array<{ text: string }>;
};

type ImageRef = {
  asset_id: string;
  href: string;
  title: string;
};

type SemanticBlock = {
  block_id: string;
  block_type: string;
  text: string;
  display_text: string;
  level?: number | null;
  heading_id?: string | null;
  editable: boolean;
  editable_reason: string;
  links: DocumentLink[];
  table_rows: TableRow[];
  image?: ImageRef | null;
};

type SectionVariant = {
  version: string;
  heading_id?: string;
  heading_block_id?: string;
  block_ids: string[];
};

type SectionVariantGroup = {
  group_id: string;
  title: string;
  level: number;
  variants: SectionVariant[];
  active_version: string;
};

type IpxactVLNV = {
  vendor: string;
  library: string;
  name: string;
  version: string;
};

type IpxactInterface = {
  name: string;
  mode: string;
  bus_type: IpxactVLNV;
  abstraction_type: IpxactVLNV;
  port_maps: Array<{ logical_port: string; physical_port: string }>;
};

type IpxactSummary = {
  file_path: string;
  component: IpxactVLNV;
  interfaces: IpxactInterface[];
  diagnostics: Diagnostic[];
};

type Relations = {
  version: number;
  section_groups: SectionVariantGroup[];
  ipxact_attachments: Record<string, Array<{ file_path: string }>>;
};

type EditorSnapshot = {
  document: {
    blocks: SemanticBlock[];
    section_groups: SectionVariantGroup[];
    links: DocumentLink[];
    diagnostics: Diagnostic[];
  };
  relations: Relations;
  ipxact_components: IpxactSummary[];
  active_section_versions: Record<string, string>;
  diagnostics: Diagnostic[];
};

type FileBrowserEntry = {
  name: string;
  path: string;
  entry_type: "directory" | "file";
};

type FileBrowserResponse = {
  directory: string;
  parent?: string | null;
  entries: FileBrowserEntry[];
};

type AgentBlock = {
  block_id: string;
  title: string;
  level: number;
};

type AgentAction = {
  action_id: string;
  title: string;
  summary: string;
  input_schema: JsonSchema;
};

type JsonSchema = {
  type?: string;
  title?: string;
  description?: string;
  default?: unknown;
  enum?: unknown[];
  properties?: Record<string, JsonSchema>;
  required?: string[];
  additionalProperties?: boolean;
};

type ConditionCheck = { check_id: string; severity: string; message: string; passed: boolean };
type PreconditionReport = { can_execute: boolean; checks: ConditionCheck[] };
type RunRecord = { run_id: string; status: string; action_id: string; completed_at?: string };
type ActionSelection = { blockId: string; action: AgentAction };
type ActionReportDrawer = { surface_id: string; messages: Record<string, unknown>[]; title: string };
type DashboardRun = { document_id: string; document_path: string; run: RunRecord & { started_at?: string }; report: { review_required: boolean; surface_id: string } | null };

type AgentArtifact = {
  artifact_id: string;
  artifact_kind: string;
  media_type: string;
  summary: string;
  external_uri: string;
  producer: string;
  role: string;
};

type AgentAttachment = {
  attachment_id: string;
  block_id: string;
  artifact_id: string;
  role: string;
  run_id: string;
};

type AgentDocumentState = {
  document_id: string;
  blocks: AgentBlock[];
  artifact_refs: Record<string, AgentArtifact>;
  attachments: Record<string, AgentAttachment[]>;
};

const apiBase = "http://127.0.0.1:8000";
const initialBrowseDirectory = "agent-spec://samples/generated";

function headingForVariant(variant: SectionVariant): string {
  return variant.heading_id ?? variant.heading_block_id ?? "";
}

function isHiddenByVariant(block: SemanticBlock, groups: SectionVariantGroup[]): boolean {
  for (const group of groups) {
    for (const variant of group.variants) {
      if (variant.version === group.active_version) {
        continue;
      }
      if (variant.block_ids.includes(block.block_id)) {
        return true;
      }
    }
  }
  return false;
}

function groupForHeading(block: SemanticBlock, groups: SectionVariantGroup[]): SectionVariantGroup | null {
  if (!block.heading_id) {
    return null;
  }
  for (const group of groups) {
    for (const variant of group.variants) {
      if (headingForVariant(variant) === block.heading_id) {
        return group;
      }
    }
  }
  return null;
}

function vlnvText(vlnv: IpxactVLNV): string {
  return [vlnv.vendor, vlnv.library, vlnv.name, vlnv.version].filter(Boolean).join(":") || "Unknown VLNV";
}

function cloneRelations(relations: Relations): Relations {
  return JSON.parse(JSON.stringify(relations)) as Relations;
}

function App() {
  const [path, setPath] = useState("");
  const [sidebarOpen, setSidebarOpen] = useState(true);
  const [browserDir, setBrowserDir] = useState(initialBrowseDirectory);
  const [browserData, setBrowserData] = useState<FileBrowserResponse | null>(null);
  const [browserStatus, setBrowserStatus] = useState("Choose an agent-spec file.");
  const [snapshot, setSnapshot] = useState<EditorSnapshot | null>(null);
  const [relationsDraft, setRelationsDraft] = useState<Relations | null>(null);
  const [textEdits, setTextEdits] = useState<Record<string, string>>({});
  const [xmlEdits, setXmlEdits] = useState<Record<string, string>>({});
  const [openAttachHeading, setOpenAttachHeading] = useState<string | null>(null);
  const [openVersionGroup, setOpenVersionGroup] = useState<string | null>(null);
  const [openActionHeading, setOpenActionHeading] = useState<string | null>(null);
  const [openAgentArtifactHeading, setOpenAgentArtifactHeading] = useState<string | null>(null);
  const [drawerPath, setDrawerPath] = useState<string | null>(null);
  const [reportDrawer, setReportDrawer] = useState<ActionReportDrawer | null>(null);
  const [xmlEditPath, setXmlEditPath] = useState<string | null>(null);
  const [status, setStatus] = useState("Choose an agent-spec file to load.");
  const [agentBlocks, setAgentBlocks] = useState<Record<string, AgentBlock>>({});
  const [agentActions, setAgentActions] = useState<AgentAction[]>([]);
  const [agentArtifacts, setAgentArtifacts] = useState<Record<string, AgentArtifact>>({});
  const [agentAttachments, setAgentAttachments] = useState<Record<string, AgentAttachment[]>>({});
  const [actionSelection, setActionSelection] = useState<ActionSelection | null>(null);
  const [actionInputs, setActionInputs] = useState<Record<string, unknown>>({});
  const [preconditions, setPreconditions] = useState<PreconditionReport | null>(null);
  const [inputsDirty, setInputsDirty] = useState(false);
  const [runsDashboardOpen, setRunsDashboardOpen] = useState(false);
  const [dashboardRuns, setDashboardRuns] = useState<DashboardRun[]>([]);

  const relations = relationsDraft ?? snapshot?.relations ?? null;
  const sectionGroups = relations?.section_groups ?? snapshot?.document.section_groups ?? [];
  const diagnostics = snapshot
    ? [
        ...snapshot.document.diagnostics,
        ...snapshot.diagnostics,
        ...snapshot.ipxact_components.flatMap((item) => item.diagnostics)
      ]
    : [];
  const componentsByPath = useMemo(() => {
    const entries = snapshot?.ipxact_components.map((component) => [component.file_path, component]) ?? [];
    return Object.fromEntries(entries) as Record<string, IpxactSummary>;
  }, [snapshot]);
  const drawerComponent = drawerPath ? componentsByPath[drawerPath] : null;
  const drawerOpen = Boolean(drawerComponent || reportDrawer || runsDashboardOpen);
  const hasDraft =
    Object.keys(textEdits).length > 0 ||
    Object.keys(xmlEdits).length > 0 ||
    JSON.stringify(relationsDraft) !== JSON.stringify(snapshot?.relations ?? null);

  function closeRightPanels() {
    setDrawerPath(null);
    setReportDrawer(null);
    setRunsDashboardOpen(false);
    setXmlEditPath(null);
  }

  function openIpxactPanel(filePath: string) {
    closeRightPanels();
    setDrawerPath(filePath);
  }

  function openRunsPanel() {
    closeRightPanels();
    setRunsDashboardOpen(true);
  }

  useEffect(() => {
    if (sidebarOpen) {
      void browseFiles(browserDir);
    }
  }, [sidebarOpen]);

  useEffect(() => {
    function closeFloatingMenus(event: PointerEvent) {
      const target = event.target;
      if (!(target instanceof Element)) {
        return;
      }
      if (target.closest(".floating-menu") || target.closest(".heading-actions")) {
        return;
      }
      setOpenAttachHeading(null);
      setOpenVersionGroup(null);
      setOpenActionHeading(null);
      setOpenAgentArtifactHeading(null);
    }

    document.addEventListener("pointerdown", closeFloatingMenus);
    return () => document.removeEventListener("pointerdown", closeFloatingMenus);
  }, []);

  async function refreshDashboardRuns() {
    const response = await fetch(`${apiBase}/agent-spec/runs`);
    if (!response.ok) return;
    const payload = (await response.json()) as { runs: DashboardRun[] };
    setDashboardRuns(payload.runs);
  }

  useEffect(() => {
    if (!runsDashboardOpen) return;
    void refreshDashboardRuns();
    const timer = window.setInterval(() => void refreshDashboardRuns(), 5000);
    return () => window.clearInterval(timer);
  }, [runsDashboardOpen]);

  async function browseFiles(directory: string) {
    const response = await fetch(`${apiBase}/files?directory=${encodeURIComponent(directory)}`);
    if (!response.ok) {
      setBrowserStatus(`Browse failed: ${response.status}`);
      return;
    }
    const data = (await response.json()) as FileBrowserResponse;
    setBrowserData(data);
    setBrowserDir(data.directory);
    setBrowserStatus("Choose an agent-spec file.");
  }

  async function loadSnapshotForPath(nextPath: string) {
    const response = await fetch(`${apiBase}/documents/snapshot?path=${encodeURIComponent(nextPath)}`);
    if (!response.ok) {
      setStatus(`Load failed: ${response.status}`);
      return;
    }
    const data = (await response.json()) as EditorSnapshot;
    setPath(nextPath);
    setSnapshot(data);
    setRelationsDraft(cloneRelations(data.relations));
    setTextEdits({});
    setXmlEdits({});
    closeRightPanels();
    setStatus("Document loaded.");
    await openAgentSpec(nextPath);
  }

  async function loadSnapshot() {
    if (!path) {
      setStatus("Choose an agent-spec file first.");
      return;
    }
    await loadSnapshotForPath(path);
  }

  async function saveAll() {
    if (!relationsDraft) {
      return;
    }
    const response = await fetch(`${apiBase}/documents/save?path=${encodeURIComponent(path)}`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({
        text_edits: textEdits,
        relations: relationsDraft,
        ipxact_xml_edits: xmlEdits
      })
    });
    if (!response.ok) {
      setStatus(`Save failed: ${response.status}`);
      return;
    }
    const data = (await response.json()) as EditorSnapshot;
    setSnapshot(data);
    setRelationsDraft(cloneRelations(data.relations));
    setTextEdits({});
    setXmlEdits({});
    setStatus("Saved.");
  }

  function setActiveVersion(groupId: string, version: string) {
    setRelationsDraft((current) => {
      if (!current) {
        return current;
      }
      const next = cloneRelations(current);
      const group = next.section_groups.find((candidate) => candidate.group_id === groupId);
      if (group) {
        group.active_version = version;
      }
      return next;
    });
  }

  function toggleAttachment(headingId: string, filePath: string) {
    setRelationsDraft((current) => {
      if (!current) {
        return current;
      }
      const next = cloneRelations(current);
      const attachments = next.ipxact_attachments[headingId] ?? [];
      const exists = attachments.some((attachment) => attachment.file_path === filePath);
      next.ipxact_attachments[headingId] = exists
        ? attachments.filter((attachment) => attachment.file_path !== filePath)
        : [...attachments, { file_path: filePath }];
      return next;
    });
  }

  async function openAgentSpec(nextPath: string) {
    const response = await fetch(`${apiBase}/agent-spec/documents/open`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({
        path: nextPath,
        sidecar_root: `${nextPath}.agent-spec-sidecar`,
        user_identity: "local"
      })
    });
    if (!response.ok) {
      setStatus(`Document loaded. Agent-spec open failed: ${response.status}`);
      return;
    }
    const data = (await response.json()) as AgentDocumentState;
    const nextBlocks = Object.fromEntries(data.blocks.map((block) => [block.block_id, block])) as Record<string, AgentBlock>;
    setAgentBlocks(nextBlocks);
    setAgentArtifacts(data.artifact_refs);
    setAgentAttachments(data.attachments);
    const actionsResponse = await fetch(`${apiBase}/agent-spec/actions`);
    if (actionsResponse.ok) {
      const actions = (await actionsResponse.json()) as { actions: AgentAction[] };
      setAgentActions(actions.actions);
    }
  }

  function defaultsForSchema(schema: JsonSchema): Record<string, unknown> {
    return Object.fromEntries(Object.entries(schema.properties ?? {}).flatMap(([name, field]) =>
      field.default === undefined ? [] : [[name, field.default]]
    ));
  }

  async function checkAction(selection = actionSelection, inputs = actionInputs) {
    if (!selection) return;
    const response = await fetch(
      `${apiBase}/agent-spec/blocks/${encodeURIComponent(selection.blockId)}/actions/${encodeURIComponent(selection.action.action_id)}/preconditions`,
      { method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify({ inputs }) }
    );
    if (!response.ok) {
      setStatus(`Precondition check failed: ${response.status}`);
      return;
    }
    setPreconditions((await response.json()) as PreconditionReport);
    setInputsDirty(false);
  }

  async function selectAction(blockId: string, action: AgentAction) {
    const inputs = defaultsForSchema(action.input_schema);
    const selection = { blockId, action };
    setActionSelection(selection);
    setActionInputs(inputs);
    setPreconditions(null);
    setInputsDirty(false);
    await checkAction(selection, inputs);
  }

  async function runAgentAction() {
    if (!actionSelection) return;
    const { blockId, action } = actionSelection;
    setStatus(`Dispatching ${action.title}...`);
    const response = await fetch(
      `${apiBase}/agent-spec/blocks/${encodeURIComponent(blockId)}/actions/${encodeURIComponent(action.action_id)}/runs`,
      {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ inputs: actionInputs })
      }
    );
    if (!response.ok) {
      setStatus(`Action launch failed: ${response.status}`);
      return;
    }
    setStatus(`${action.title} was dispatched. Track it from Runs.`);
    setOpenActionHeading(null);
  }

  async function openRunReport(item: DashboardRun) {
    const response = await fetch(`${apiBase}/agent-spec/runs/${encodeURIComponent(item.run.run_id)}`);
    if (!response.ok) {
      setStatus(`Could not load report: ${response.status}`);
      return;
    }
    const payload = (await response.json()) as { data: { report: { surface_id: string } | null; a2ui_messages: Record<string, unknown>[] } };
    if (!payload.data.report) {
      setStatus("This run has no completed report yet.");
      return;
    }
    closeRightPanels();
    setReportDrawer({ surface_id: payload.data.report.surface_id, messages: payload.data.a2ui_messages, title: `Action report: ${item.run.action_id}` });
  }

  function renderText(block: SemanticBlock) {
    const text = textEdits[block.block_id] ?? (block.display_text || block.text);
    if (!block.editable) {
      return (
        <span className="read-only-text" title={block.editable_reason}>
          {text}
        </span>
      );
    }
    return (
      <span
        className="editable-text"
        contentEditable
        suppressContentEditableWarning
        onBlur={(event) => {
          const nextText = event.currentTarget.textContent ?? "";
          setTextEdits((current) => ({ ...current, [block.block_id]: nextText }));
        }}
      >
        {text}
      </span>
    );
  }

  function renderHeading(block: SemanticBlock) {
    const headingTag = `h${Math.min(Math.max(block.level ?? 1, 1), 6)}` as "h1" | "h2" | "h3" | "h4" | "h5" | "h6";
    const group = groupForHeading(block, sectionGroups);
    const headingId = block.heading_id ?? block.block_id;
    const attachments = relations?.ipxact_attachments[headingId] ?? [];
    const agentBlock = agentBlocks[headingId];
    const actions = agentActions;
    const agentBlockAttachments = agentAttachments[headingId] ?? [];
    const attachedComponents = attachments
      .map((attachment) => componentsByPath[attachment.file_path])
      .filter((component): component is IpxactSummary => component !== undefined);
    return (
      <div className="heading-row">
        {React.createElement(headingTag, null, renderText(block))}
        <div className="heading-actions">
          {group && (
            <button
              className="icon-button"
              type="button"
              title="Choose version"
              onClick={() => setOpenVersionGroup(openVersionGroup === group.group_id ? null : group.group_id)}
            >
              ▾
            </button>
          )}
          <button
            className={attachments.length > 0 ? "icon-button artifact-button has-artifacts" : "icon-button artifact-button"}
            type="button"
            title={`${attachments.length} IP-XACT attachment${attachments.length === 1 ? "" : "s"}`}
            onClick={() => setOpenAttachHeading(openAttachHeading === headingId ? null : headingId)}
          >
            <span aria-hidden="true">⧉</span>
            <span>{attachments.length}</span>
          </button>
          {agentBlockAttachments.length > 0 && (
            <button
              className="icon-button agent-artifact-button has-agent-artifacts"
              type="button"
              title={`${agentBlockAttachments.length} agent artifact${agentBlockAttachments.length === 1 ? "" : "s"}`}
              onClick={() =>
                setOpenAgentArtifactHeading(openAgentArtifactHeading === headingId ? null : headingId)
              }
            >
              <span>{agentBlockAttachments.length}</span>
            </button>
          )}
          {agentBlock && (
            <button
              className="action-button"
              type="button"
              title="Choose an action"
              onClick={() => setOpenActionHeading(openActionHeading === headingId ? null : headingId)}
            >
              Actions ▾
            </button>
          )}
        </div>
        {group && openVersionGroup === group.group_id && (
          <div className="floating-menu version-menu">
            {group.variants.map((variant) => (
              <button
                key={variant.version}
                className={variant.version === group.active_version ? "menu-item active" : "menu-item"}
                type="button"
                onClick={() => {
                  setActiveVersion(group.group_id, variant.version);
                  setOpenVersionGroup(null);
                }}
              >
                {variant.version}
              </button>
            ))}
          </div>
        )}
        {openAttachHeading === headingId && snapshot && (
          <div className="floating-menu attachment-menu">
            <strong>IP-XACT attachments</strong>
            {attachedComponents.map((component) => (
              <div key={component.file_path} className="attachment-row">
                <span>{component.component.name || component.file_path}</span>
                <div className="attachment-actions">
                  <button type="button" onClick={() => openIpxactPanel(component.file_path)}>
                    Open
                  </button>
                  <button type="button" onClick={() => toggleAttachment(headingId, component.file_path)}>
                    Detach
                  </button>
                </div>
              </div>
            ))}
            {attachments.length > attachedComponents.length && (
              <p className="empty-note">Some attached IP-XACT files are missing from the agent-spec archive.</p>
            )}
            {attachedComponents.length === 0 && <p className="empty-note">No IP-XACT attached to this heading.</p>}
          </div>
        )}
        {openActionHeading === headingId && (
          <div className="floating-menu action-menu">
            {!actionSelection || actionSelection.blockId !== headingId ? (
              <>
                <strong>Actions</strong>
                {actions.map((action) => (
                  <button key={action.action_id} className="menu-item" type="button" onClick={() => void selectAction(headingId, action)}>
                    <strong>{action.title}</strong><small>{action.summary}</small>
                  </button>
                ))}
              </>
            ) : (
              <>
                <button className="secondary-button" type="button" onClick={() => { setActionSelection(null); setPreconditions(null); }}>← All actions</button>
                <strong>{actionSelection.action.title}</strong>
                <p>{actionSelection.action.summary}</p>
                {Object.entries(actionSelection.action.input_schema.properties ?? {}).map(([name, field]) => {
                  const unsupported = field.type === "object" || field.type === "array" || !["string", "number", "integer", "boolean", undefined].includes(field.type);
                  const value = actionInputs[name];
                  return <label key={name} className="action-input">{field.title ?? name}
                    {field.description && <small>{field.description}</small>}
                    {unsupported ? <span className="input-error">Unsupported input schema.</span> : field.enum ? <select value={String(value ?? "")} onChange={(event) => { setActionInputs((current) => ({ ...current, [name]: event.target.value })); setInputsDirty(true); }}><option value="">Select…</option>{field.enum.map((item) => <option key={String(item)} value={String(item)}>{String(item)}</option>)}</select> : field.type === "boolean" ? <input type="checkbox" checked={Boolean(value)} onChange={(event) => { setActionInputs((current) => ({ ...current, [name]: event.target.checked })); setInputsDirty(true); }} /> : <input type={field.type === "number" || field.type === "integer" ? "number" : "text"} value={String(value ?? "")} onChange={(event) => { const next = field.type === "number" || field.type === "integer" ? Number(event.target.value) : event.target.value; setActionInputs((current) => ({ ...current, [name]: next })); setInputsDirty(true); }} />}
                  </label>;
                })}
                {preconditions && <div className="condition-list">{preconditions.checks.map((check) => <p key={check.check_id} className={check.passed ? "passed" : "failed"}>{check.passed ? "✓" : "!"} {check.message}</p>)}</div>}
                <button type="button" className="secondary-button" onClick={() => void checkAction()}>Check prerequisites</button>
                <button type="button" disabled={!preconditions?.can_execute || inputsDirty} onClick={() => void runAgentAction()}>Trigger action</button>
              </>
            )}
          </div>
        )}
        {openAgentArtifactHeading === headingId && (
          <div className="floating-menu agent-artifact-menu">
            <strong>Agent artifacts</strong>
            {agentBlockAttachments.map((attachment) => {
              const artifact = agentArtifacts[attachment.artifact_id];
              return (
                <div key={attachment.attachment_id} className="attachment-row">
                  <span>{artifact?.summary ?? attachment.artifact_id}</span>
                  <small>{artifact?.producer ?? attachment.role}</small>
                </div>
              );
            })}
          </div>
        )}
      </div>
    );
  }

  function renderBlock(block: SemanticBlock) {
    if (isHiddenByVariant(block, sectionGroups)) {
      return null;
    }
    if (block.block_type === "heading") {
      return <section key={block.block_id} className="doc-block heading-block">{renderHeading(block)}</section>;
    }
    if (block.block_type === "table") {
      return (
        <section key={block.block_id} className="doc-block table-block">
          <table>
            <tbody>
              {block.table_rows.map((row, rowIndex) => (
                <tr key={rowIndex}>
                  {row.cells.map((cell, cellIndex) => (
                    <td key={cellIndex}>{cell.text}</td>
                  ))}
                </tr>
              ))}
            </tbody>
          </table>
        </section>
      );
    }
    if (block.block_type === "image" && block.image) {
      return (
        <section key={block.block_id} className="doc-block image-block">
          <img
            src={`${apiBase}/documents/assets/${block.image.asset_id}?path=${encodeURIComponent(path)}`}
            alt={block.image.title || block.image.href}
          />
        </section>
      );
    }
    if (block.block_type === "list_item") {
      return <li key={block.block_id} className="doc-block list-block">{renderText(block)}</li>;
    }
    return <p key={block.block_id} className="doc-block paragraph-block">{renderText(block)}</p>;
  }

  return (
    <main className="app-shell">
      <header className="command-bar">
        <button type="button" className="icon-button" title="Toggle file browser" onClick={() => setSidebarOpen(!sidebarOpen)}>
          ☰
        </button>
        <div className="brand">
          <h1>Agent-Spec Editor</h1>
          <p>{status}</p>
        </div>
        <div className="command-actions">
          <span className="current-file" title={path}>
            {path || "No document selected"}
          </span>
          <button type="button" onClick={() => setSidebarOpen(true)}>Open</button>
          <button type="button" onClick={loadSnapshot} disabled={!path}>Reload</button>
          <button type="button" onClick={saveAll} disabled={!snapshot || !hasDraft}>Save</button>
          <button type="button" onClick={openRunsPanel}>Runs{dashboardRuns.length ? ` (${dashboardRuns.length})` : ""}</button>
        </div>
      </header>

      {diagnostics.length > 0 && (
        <section className="diagnostics">
          {diagnostics.map((diagnostic, index) => (
            <p key={`${diagnostic.source}-${index}`} className={diagnostic.severity}>
              <strong>{diagnostic.severity}</strong> {diagnostic.source}: {diagnostic.message}
            </p>
          ))}
        </section>
      )}

      <section className={`${drawerOpen ? "workspace drawer-open" : "workspace"} ${sidebarOpen ? "sidebar-open" : ""}`}>
        {sidebarOpen && (
          <aside className="file-sidebar">
            <div className="sidebar-header">
              <div>
                <h2>Open Document</h2>
                <p>{browserStatus}</p>
              </div>
              <button type="button" className="icon-button" onClick={() => setSidebarOpen(false)}>
                ×
              </button>
            </div>
            <div className="browser-path" title={browserData?.directory ?? browserDir}>
              {browserData?.directory ?? browserDir}
            </div>
            <div className="browser-list">
              {browserData?.parent && (
                <button type="button" className="browser-entry directory" onClick={() => browseFiles(browserData.parent!)}>
                  <span>..</span>
                  <small>Parent folder</small>
                </button>
              )}
              {browserData?.entries.map((entry) => (
                <button
                  key={entry.path}
                  type="button"
                  className={`browser-entry ${entry.entry_type}`}
                  onClick={() => {
                    if (entry.entry_type === "directory") {
                      void browseFiles(entry.path);
                    } else {
                      void loadSnapshotForPath(entry.path);
                      setSidebarOpen(false);
                    }
                  }}
                >
                  <span>{entry.name}</span>
                  <small>{entry.entry_type === "directory" ? "Folder" : "agent-spec document"}</small>
                </button>
              ))}
              {browserData && browserData.entries.length === 0 && <p className="empty-note">No folders or agent-spec files here.</p>}
            </div>
          </aside>
        )}
        <article className="document-canvas">
          {!snapshot && <p className="empty-state">Load an agent-spec file to begin.</p>}
          {snapshot?.document.blocks.map(renderBlock)}
        </article>

        {runsDashboardOpen && (
          <aside className="ipxact-drawer runs-sidebar" aria-label="All runs">
            <div className="drawer-header">
              <div><h2>All runs</h2><p>Runs continue after changing documents.</p></div>
              <button type="button" className="icon-button" onClick={() => setRunsDashboardOpen(false)}>×</button>
            </div>
            <button type="button" className="secondary-button" onClick={() => void refreshDashboardRuns()}>Refresh</button>
            <div className="runs-list">
              {dashboardRuns.map((item) => (
                <article key={item.run.run_id} className="run-card">
                  <div><strong>{item.run.action_id}</strong><p>{item.document_path}</p><small>{item.run.run_id}</small></div>
                  <span className={`run-state ${item.run.status}`}>{item.run.status}{item.report?.review_required ? " · review" : ""}</span>
                  <div className="run-card-actions">
                    <button type="button" disabled={!item.report} onClick={() => void openRunReport(item)}>Report</button>
                    <button type="button" className="secondary-button" onClick={() => setStatus("Cancel will be available in a future executor update.")}>Cancel</button>
                    <button type="button" className="secondary-button" onClick={() => setStatus("Restart will be available in a future executor update.")}>Restart</button>
                  </div>
                </article>
              ))}
              {dashboardRuns.length === 0 && <p className="empty-note">No runs have been dispatched in this server session.</p>}
            </div>
          </aside>
        )}

        {drawerComponent && (
          <aside className="ipxact-drawer">
            <div className="drawer-header">
              <div>
                <h2>{drawerComponent.component.name || drawerComponent.file_path}</h2>
                <p>{vlnvText(drawerComponent.component)}</p>
              </div>
              <button type="button" className="icon-button" onClick={() => setDrawerPath(null)}>
                ×
              </button>
            </div>
            {drawerComponent.interfaces.map((iface) => (
              <section key={iface.name} className="interface-section">
                <h3>{iface.name}</h3>
                <p>
                  {iface.mode || "unknown"} · {iface.bus_type.name || "unknown bus"} ·{" "}
                  {iface.abstraction_type.name || "unknown abstraction"}
                </p>
                <table>
                  <thead>
                    <tr>
                      <th>Logical</th>
                      <th>Physical</th>
                    </tr>
                  </thead>
                  <tbody>
                    {iface.port_maps.map((port) => (
                      <tr key={`${port.logical_port}-${port.physical_port}`}>
                        <td>{port.logical_port}</td>
                        <td>{port.physical_port}</td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </section>
            ))}
            <button
              type="button"
              className="secondary-button"
              onClick={() => setXmlEditPath(xmlEditPath === drawerComponent.file_path ? null : drawerComponent.file_path)}
            >
              Edit Raw XML
            </button>
            {xmlEditPath === drawerComponent.file_path && (
              <textarea
                className="xml-textarea"
                value={xmlEdits[drawerComponent.file_path] ?? ""}
                onChange={(event) =>
                  setXmlEdits((current) => ({ ...current, [drawerComponent.file_path]: event.target.value }))
                }
                placeholder="Paste replacement IP-XACT XML here"
              />
            )}
          </aside>
        )}
        {reportDrawer && (
          <aside className="ipxact-drawer report-drawer">
            <div className="drawer-header">
              <div><h2>{reportDrawer.title}</h2><p>Read-only executor result</p></div>
              <button type="button" className="icon-button" onClick={() => setReportDrawer(null)}>×</button>
            </div>
            <ReportSurface messages={reportDrawer.messages} surfaceId={reportDrawer.surface_id} />
          </aside>
        )}
      </section>
    </main>
  );
}

createRoot(document.getElementById("root")!).render(<App />);
