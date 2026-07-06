import React, { useEffect, useMemo, useState } from "react";
import { createRoot } from "react-dom/client";
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
  tags: string[];
};

type AgentAction = {
  action_id: string;
  title: string;
  summary: string;
};

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
const initialBrowseDirectory = "spec2gds/spec/odt_container/samples/generated";
const v1Tags = ["systemc-perf", "systemc-bitaccurate", "rtl", "ip", "interface", "configuration"];

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
  const [browserStatus, setBrowserStatus] = useState("Choose an ODT file.");
  const [snapshot, setSnapshot] = useState<EditorSnapshot | null>(null);
  const [relationsDraft, setRelationsDraft] = useState<Relations | null>(null);
  const [textEdits, setTextEdits] = useState<Record<string, string>>({});
  const [xmlEdits, setXmlEdits] = useState<Record<string, string>>({});
  const [openAttachHeading, setOpenAttachHeading] = useState<string | null>(null);
  const [openVersionGroup, setOpenVersionGroup] = useState<string | null>(null);
  const [openTagHeading, setOpenTagHeading] = useState<string | null>(null);
  const [openAgentArtifactHeading, setOpenAgentArtifactHeading] = useState<string | null>(null);
  const [drawerPath, setDrawerPath] = useState<string | null>(null);
  const [xmlEditPath, setXmlEditPath] = useState<string | null>(null);
  const [status, setStatus] = useState("Choose an ODT file to load.");
  const [agentBlocks, setAgentBlocks] = useState<Record<string, AgentBlock>>({});
  const [agentActions, setAgentActions] = useState<Record<string, AgentAction[]>>({});
  const [agentArtifacts, setAgentArtifacts] = useState<Record<string, AgentArtifact>>({});
  const [agentAttachments, setAgentAttachments] = useState<Record<string, AgentAttachment[]>>({});

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
  const hasDraft =
    Object.keys(textEdits).length > 0 ||
    Object.keys(xmlEdits).length > 0 ||
    JSON.stringify(relationsDraft) !== JSON.stringify(snapshot?.relations ?? null);

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
      setOpenTagHeading(null);
      setOpenAgentArtifactHeading(null);
    }

    document.addEventListener("pointerdown", closeFloatingMenus);
    return () => document.removeEventListener("pointerdown", closeFloatingMenus);
  }, []);

  async function browseFiles(directory: string) {
    const response = await fetch(`${apiBase}/files?directory=${encodeURIComponent(directory)}`);
    if (!response.ok) {
      setBrowserStatus(`Browse failed: ${response.status}`);
      return;
    }
    const data = (await response.json()) as FileBrowserResponse;
    setBrowserData(data);
    setBrowserDir(data.directory);
    setBrowserStatus("Choose an ODT file.");
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
    setDrawerPath(null);
    setStatus("Document loaded.");
    await openAgentSpec(nextPath);
  }

  async function loadSnapshot() {
    if (!path) {
      setStatus("Choose an ODT file first.");
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
    await refreshAgentActions(data.blocks);
  }

  async function refreshAgentActions(blocks: AgentBlock[]) {
    const entries = await Promise.all(
      blocks.map(async (block) => {
        const response = await fetch(`${apiBase}/agent-spec/blocks/${encodeURIComponent(block.block_id)}/actions`);
        if (!response.ok) {
          return [block.block_id, []] as const;
        }
        const data = (await response.json()) as { actions: AgentAction[] };
        return [block.block_id, data.actions] as const;
      })
    );
    setAgentActions(Object.fromEntries(entries) as Record<string, AgentAction[]>);
  }

  async function updateAgentTags(blockId: string, tags: string[]) {
    const response = await fetch(`${apiBase}/agent-spec/blocks/${encodeURIComponent(blockId)}/tags`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ tags })
    });
    if (!response.ok) {
      setStatus(`Tag update failed: ${response.status}`);
      return;
    }
    const block = (await response.json()) as AgentBlock;
    const nextBlocks = { ...agentBlocks, [block.block_id]: block };
    setAgentBlocks(nextBlocks);
    await refreshAgentActions(Object.values(nextBlocks));
  }

  async function runAgentAction(blockId: string, actionId: string) {
    setStatus(`Running ${actionId}...`);
    const response = await fetch(
      `${apiBase}/agent-spec/blocks/${encodeURIComponent(blockId)}/actions/${encodeURIComponent(actionId)}/runs`,
      {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ parameters: { delay_seconds: 1 } })
      }
    );
    if (!response.ok) {
      setStatus(`Action failed: ${response.status}`);
      return;
    }
    await openAgentSpec(path);
    setStatus(`${actionId} completed and attached artifact metadata.`);
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
    const actions = agentActions[headingId] ?? [];
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
          {agentBlock && (
            <button
              className={agentBlock.tags.length > 0 ? "icon-button tag-button has-tags" : "icon-button tag-button"}
              type="button"
              title={`${agentBlock.tags.length} tag${agentBlock.tags.length === 1 ? "" : "s"}`}
              onClick={() => setOpenTagHeading(openTagHeading === headingId ? null : headingId)}
            >
              #
            </button>
          )}
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
          {actions.map((action) => (
            <button
              key={action.action_id}
              className="action-button"
              type="button"
              title={action.summary}
              onClick={() => void runAgentAction(headingId, action.action_id)}
            >
              {action.title}
            </button>
          ))}
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
                  <button type="button" onClick={() => setDrawerPath(component.file_path)}>
                    Open
                  </button>
                  <button type="button" onClick={() => toggleAttachment(headingId, component.file_path)}>
                    Detach
                  </button>
                </div>
              </div>
            ))}
            {attachments.length > attachedComponents.length && (
              <p className="empty-note">Some attached IP-XACT files are missing from the ODT package.</p>
            )}
            {attachedComponents.length === 0 && <p className="empty-note">No IP-XACT attached to this heading.</p>}
          </div>
        )}
        {openTagHeading === headingId && agentBlock && (
          <div className="floating-menu tag-menu">
            <strong>Tags</strong>
            {v1Tags.map((tag) => {
              const checked = agentBlock.tags.includes(tag);
              const nextTags = checked
                ? agentBlock.tags.filter((candidate) => candidate !== tag)
                : [...agentBlock.tags, tag];
              return (
                <button
                  key={tag}
                  className={checked ? "menu-item active" : "menu-item"}
                  type="button"
                  onClick={() => void updateAgentTags(headingId, nextTags)}
                >
                  {tag}
                </button>
              );
            })}
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
          <h1>ODT Container Editor</h1>
          <p>{status}</p>
        </div>
        <div className="command-actions">
          <span className="current-file" title={path}>
            {path || "No document selected"}
          </span>
          <button type="button" onClick={() => setSidebarOpen(true)}>Open</button>
          <button type="button" onClick={loadSnapshot} disabled={!path}>Reload</button>
          <button type="button" onClick={saveAll} disabled={!snapshot || !hasDraft}>Save</button>
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

      <section className={`${drawerComponent ? "workspace drawer-open" : "workspace"} ${sidebarOpen ? "sidebar-open" : ""}`}>
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
                  <small>{entry.entry_type === "directory" ? "Folder" : "ODT document"}</small>
                </button>
              ))}
              {browserData && browserData.entries.length === 0 && <p className="empty-note">No folders or ODT files here.</p>}
            </div>
          </aside>
        )}
        <article className="document-canvas">
          {!snapshot && <p className="empty-state">Load an ODT file to begin.</p>}
          {snapshot?.document.blocks.map(renderBlock)}
        </article>

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
      </section>
    </main>
  );
}

createRoot(document.getElementById("root")!).render(<App />);
