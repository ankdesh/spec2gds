import React, { useState } from "react";
import { createRoot } from "react-dom/client";
import "./styles.css";

type Diagnostic = {
  severity: string;
  source: string;
  message: string;
  block_id?: string | null;
};

type SemanticBlock = {
  block_id: string;
  block_type: string;
  text: string;
  level?: number | null;
  editable: boolean;
};

type SectionVariant = {
  version: string;
  heading_block_id: string;
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

type EditorSnapshot = {
  document: {
    blocks: SemanticBlock[];
    section_groups: SectionVariantGroup[];
    links: Array<{ href: string; text: string; block_id: string }>;
    diagnostics: Diagnostic[];
  };
  ipxact_components: IpxactSummary[];
  active_section_versions: Record<string, string>;
  diagnostics: Diagnostic[];
};

const apiBase = "http://127.0.0.1:8000";

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

function App() {
  const [path, setPath] = useState("");
  const [snapshot, setSnapshot] = useState<EditorSnapshot | null>(null);
  const [edits, setEdits] = useState<Record<string, string>>({});
  const [ipxactXml, setIpxactXml] = useState<Record<string, string>>({});
  const [status, setStatus] = useState("Enter a local .odt path and load a snapshot.");

  async function loadSnapshot() {
    const response = await fetch(`${apiBase}/documents/snapshot?path=${encodeURIComponent(path)}`);
    if (!response.ok) {
      setStatus(`Load failed: ${response.status}`);
      return;
    }
    const data = (await response.json()) as EditorSnapshot;
    setSnapshot(data);
    setEdits({});
    setIpxactXml({});
    setStatus("Snapshot loaded.");
  }

  async function saveTextEdits() {
    const response = await fetch(`${apiBase}/documents/text-edits?path=${encodeURIComponent(path)}`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(edits)
    });
    if (!response.ok) {
      setStatus(`Save failed: ${response.status}`);
      return;
    }
    const data = (await response.json()) as EditorSnapshot;
    setSnapshot(data);
    setEdits({});
    setStatus("Text edits saved.");
  }

  async function setActiveVersion(groupId: string, version: string) {
    if (!snapshot) {
      return;
    }
    const nextActive = { ...snapshot.active_section_versions, [groupId]: version };
    const response = await fetch(
      `${apiBase}/documents/active-section-versions?path=${encodeURIComponent(path)}`,
      {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(nextActive)
      }
    );
    if (!response.ok) {
      setStatus(`Version save failed: ${response.status}`);
      return;
    }
    const data = (await response.json()) as EditorSnapshot;
    setSnapshot(data);
    setStatus("Active section version saved.");
  }

  async function previewIpxact(filePath: string) {
    const xmlText = ipxactXml[filePath];
    if (!xmlText) {
      setStatus("Paste IP-XACT XML before previewing.");
      return;
    }
    const response = await fetch(`${apiBase}/ipxact/preview`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ file_path: filePath, xml_text: xmlText })
    });
    if (!response.ok) {
      setStatus(`IP-XACT preview failed: ${response.status}`);
      return;
    }
    const preview = (await response.json()) as IpxactSummary;
    const messages = preview.diagnostics.map((diagnostic) => diagnostic.message).join("; ");
    setStatus(messages || `Preview OK: ${preview.interfaces.length} interface(s).`);
  }

  async function saveIpxact(filePath: string) {
    const xmlText = ipxactXml[filePath];
    if (!xmlText) {
      setStatus("Paste IP-XACT XML before saving.");
      return;
    }
    const response = await fetch(`${apiBase}/documents/ipxact-xml?path=${encodeURIComponent(path)}`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ file_path: filePath, xml_text: xmlText })
    });
    if (!response.ok) {
      setStatus(`IP-XACT save failed: ${response.status}`);
      return;
    }
    const data = (await response.json()) as EditorSnapshot;
    setSnapshot(data);
    setStatus("IP-XACT XML saved.");
  }

  const diagnostics = snapshot
    ? [...snapshot.document.diagnostics, ...snapshot.diagnostics, ...snapshot.ipxact_components.flatMap((item) => item.diagnostics)]
    : [];

  return (
    <main className="app-shell">
      <header className="toolbar">
        <div>
          <h1>ODT Editor</h1>
          <p>{status}</p>
        </div>
        <div className="path-row">
          <input
            value={path}
            onChange={(event) => setPath(event.target.value)}
            placeholder="/path/to/spec.odt"
          />
          <button onClick={loadSnapshot}>Load</button>
          <button onClick={saveTextEdits} disabled={!snapshot || Object.keys(edits).length === 0}>
            Save Text
          </button>
        </div>
      </header>

      {diagnostics.length > 0 && (
        <section className="diagnostics">
          <h2>Diagnostics</h2>
          {diagnostics.map((diagnostic, index) => (
            <p key={`${diagnostic.source}-${index}`} className={diagnostic.severity}>
              <strong>{diagnostic.severity}</strong> {diagnostic.source}: {diagnostic.message}
            </p>
          ))}
        </section>
      )}

      {snapshot && (
        <section className="workspace">
          <article className="document-pane">
            {snapshot.document.section_groups.map((group) => (
              <div key={group.group_id} className="version-control">
                <span>{group.title}</span>
                <select
                  value={group.active_version}
                  onChange={(event) => setActiveVersion(group.group_id, event.target.value)}
                >
                  {group.variants.map((variant) => (
                    <option key={variant.version} value={variant.version}>
                      {variant.version}
                    </option>
                  ))}
                </select>
              </div>
            ))}

            {snapshot.document.blocks
              .filter((block) => !isHiddenByVariant(block, snapshot.document.section_groups))
              .map((block) => (
                <div key={block.block_id} className={`block ${block.block_type}`}>
                  <label>{block.block_type}</label>
                  {block.editable ? (
                    <textarea
                      value={edits[block.block_id] ?? block.text}
                      onChange={(event) =>
                        setEdits((current) => ({ ...current, [block.block_id]: event.target.value }))
                      }
                    />
                  ) : (
                    <p>{block.text}</p>
                  )}
                </div>
              ))}
          </article>

          <aside className="ipxact-pane">
            <h2>IP-XACT Interfaces</h2>
            {snapshot.ipxact_components.map((component) => (
              <section key={component.file_path}>
                <h3>{component.component.name || component.file_path}</h3>
                <p>
                  {component.component.vendor}:{component.component.library}:{component.component.name}:
                  {component.component.version}
                </p>
                <table>
                  <thead>
                    <tr>
                      <th>Name</th>
                      <th>Mode</th>
                      <th>Bus Type</th>
                      <th>Ports</th>
                    </tr>
                  </thead>
                  <tbody>
                    {component.interfaces.map((iface) => (
                      <tr key={iface.name}>
                        <td>{iface.name}</td>
                        <td>{iface.mode}</td>
                        <td>{iface.bus_type.name}</td>
                        <td>{iface.port_maps.length}</td>
                      </tr>
                    ))}
                  </tbody>
                </table>
                <div className="xml-editor">
                  <label>Raw IP-XACT XML</label>
                  <textarea
                    value={ipxactXml[component.file_path] ?? ""}
                    onChange={(event) =>
                      setIpxactXml((current) => ({
                        ...current,
                        [component.file_path]: event.target.value
                      }))
                    }
                    placeholder="Paste updated IP-XACT XML here"
                  />
                  <div className="button-row">
                    <button onClick={() => previewIpxact(component.file_path)}>Preview XML</button>
                    <button onClick={() => saveIpxact(component.file_path)}>Save XML</button>
                  </div>
                </div>
              </section>
            ))}
            {snapshot.ipxact_components.length === 0 && (
              <section className="xml-editor">
                <h3>Import IP-XACT</h3>
                <input
                  value={ipxactXml["new.xml"] ? "new.xml" : ""}
                  readOnly
                  placeholder="new.xml"
                />
                <textarea
                  value={ipxactXml["new.xml"] ?? ""}
                  onChange={(event) =>
                    setIpxactXml((current) => ({ ...current, "new.xml": event.target.value }))
                  }
                  placeholder="Paste IP-XACT XML here"
                />
                <div className="button-row">
                  <button onClick={() => previewIpxact("new.xml")}>Preview XML</button>
                  <button onClick={() => saveIpxact("new.xml")}>Save XML</button>
                </div>
              </section>
            )}
          </aside>
        </section>
      )}
    </main>
  );
}

const root = createRoot(document.getElementById("root") as HTMLElement);
root.render(<App />);
