import React, {
  Fragment,
  createContext,
  useContext,
  useEffect,
  useMemo,
  useRef,
  useState,
} from "react";
import { A2uiSurface, createComponentImplementation } from "@a2ui/react/v0_9";
import {
  Catalog,
  CommonSchemas,
  MessageProcessor,
  type A2uiMessage,
} from "@a2ui/web_core/v0_9";
import { z } from "zod";

import type {
  A2UIDocumentBatch,
  DocumentCell,
  DocumentSectionData,
  DocumentTable,
  EntityMetadataInput,
  EntityRef,
  NarrativeBlock as NarrativeBlockData,
  TocEntry,
  WirePortInput,
} from "@spec2gds/document-core";

export const SPEC_DOCUMENT_CATALOG_ID = "urn:spec2gds:a2ui:document:v1";
export const SPEC_ENTITY_ACTION_EVENT = "spec2gds:entity-action";
export const SPEC_OPEN_CIRCUIT_EVENT = "spec2gds:open-circuit";

export interface SpecOpenCircuitEventDetail {
  entityRef: EntityRef;
}

export interface SpecDocumentEditController {
  createEntity(kind: "component" | "design", name: string): Promise<void>;
  updateEntityMetadata(ref: EntityRef, value: EntityMetadataInput): Promise<void>;
  addComponentPort(ref: EntityRef, value: WirePortInput): Promise<void>;
  updateComponentPort(ref: EntityRef, name: string, value: Omit<WirePortInput, "name">): Promise<void>;
  portEditingAvailability(ref: EntityRef): { enabled: boolean; reason: string };
}

interface EditCoordinator {
  controller: SpecDocumentEditController | null;
  activeEditorId: string;
  requestEditor(editorId: string): boolean;
  finishEditor(editorId: string): void;
}

const EditCoordinatorContext = createContext<EditCoordinator>({
  controller: null,
  activeEditorId: "",
  requestEditor: () => false,
  finishEditor: () => undefined,
});

function EditCoordinatorProvider({
  controller,
  children,
  resetKey,
}: {
  controller?: SpecDocumentEditController;
  children: React.ReactNode;
  resetKey: string;
}) {
  const [activeEditorId, setActiveEditorId] = useState("");
  const [notice, setNotice] = useState("");
  useEffect(() => {
    setActiveEditorId("");
    setNotice("");
  }, [resetKey]);
  const value = useMemo<EditCoordinator>(() => ({
    controller: controller ?? null,
    activeEditorId,
    requestEditor(editorId: string) {
      if (!controller) return false;
      if (activeEditorId && activeEditorId !== editorId) {
        setNotice("Save or cancel the current edit before starting another one.");
        return false;
      }
      setNotice("");
      setActiveEditorId(editorId);
      return true;
    },
    finishEditor(editorId: string) {
      setActiveEditorId((current) => current === editorId ? "" : current);
      setNotice("");
    },
  }), [activeEditorId, controller]);
  return (
    <EditCoordinatorContext.Provider value={value}>
      {notice && <div className="spec-edit-global-notice" role="status">{notice}</div>}
      {children}
    </EditCoordinatorContext.Provider>
  );
}

const SPEC_SECTION_MENU_OPEN_EVENT = "spec2gds:section-menu-open";

const SpecDocumentApi = {
  name: "SpecDocument",
  schema: z.object({
    title: z.string(),
    summary: z.string(),
    documentId: z.string(),
    sourceRevisionHash: z.string(),
    toc: z.array(z.object({
      section_id: z.string(),
      title: z.string(),
      level: z.number(),
    })),
    children: CommonSchemas.ChildList,
  }),
};

const SpecSectionApi = {
  name: "SpecSection",
  schema: z.object({
    section: z.custom<DocumentSectionData>(),
    children: CommonSchemas.ChildList,
  }),
};

const SpecTableApi = {
  name: "SpecTable",
  schema: z.object({ table: z.custom<DocumentTable>() }),
};

const NarrativeBlockApi = {
  name: "NarrativeBlock",
  schema: z.object({ block: z.custom<NarrativeBlockData>(), documentId: z.string() }),
};

const EntityLinkApi = {
  name: "EntityLink",
  schema: z.object({ block: z.custom<NarrativeBlockData>(), documentId: z.string() }),
};

const LiveViewApi = {
  name: "LiveView",
  schema: z.object({ block: z.custom<NarrativeBlockData>(), documentId: z.string() }),
};

function renderChildren(
  children: unknown,
  buildChild: (id: string, basePath?: string) => React.ReactNode,
): React.ReactNode {
  if (!Array.isArray(children)) return null;
  return children.map((child, index) => {
    if (typeof child === "string") {
      return <Fragment key={`${child}-${index}`}>{buildChild(child)}</Fragment>;
    }
    if (child && typeof child === "object" && "id" in child) {
      const value = child as { id: string; basePath?: string };
      return <Fragment key={`${value.id}-${index}`}>{buildChild(value.id, value.basePath)}</Fragment>;
    }
    return null;
  });
}

function shortHash(value: string): string {
  return value.length > 12 ? `${value.slice(0, 12)}…` : value;
}

const SpecDocument = createComponentImplementation(
  SpecDocumentApi,
  ({ props, buildChild }) => (
    <div className="spec-document">
      <aside className="spec-toc" aria-label="Document contents">
        <div className="spec-toc__sticky">
          <p className="spec-kicker">Contents</p>
          <nav>
            {(props.toc as TocEntry[]).map((entry) => (
              <a
                className={`spec-toc__link spec-toc__link--level-${entry.level}`}
                href={`#${entry.section_id}`}
                key={entry.section_id}
              >
                {entry.title}
              </a>
            ))}
          </nav>
          <dl className="spec-toc__meta">
            <div><dt>Document</dt><dd>{props.documentId}</dd></div>
            <div title={props.sourceRevisionHash}>
              <dt>Revision</dt><dd><code>{shortHash(props.sourceRevisionHash)}</code></dd>
            </div>
          </dl>
        </div>
      </aside>
      <article className="spec-paper">
        <header className="spec-cover">
          <p className="spec-kicker">Unified hardware specification</p>
          <h1>{props.title}</h1>
          <p>{props.summary}</p>
        </header>
        {renderChildren(props.children, buildChild)}
      </article>
    </div>
  ),
);

function dispatchEntityAction(entityRef: EntityRef): void {
  window.dispatchEvent(new CustomEvent(SPEC_ENTITY_ACTION_EVENT, {
    detail: { entityRef },
  }));
}

function dispatchOpenCircuit(entityRef: EntityRef): void {
  window.dispatchEvent(new CustomEvent<SpecOpenCircuitEventDetail>(SPEC_OPEN_CIRCUIT_EVENT, {
    detail: { entityRef },
  }));
}

function SectionOptionsMenu({
  section,
  onCreate,
  onEditDetails,
  onAddPort,
  portAvailability,
}: {
  section: DocumentSectionData;
  onCreate?: (kind: "component" | "design") => void;
  onEditDetails?: () => void;
  onAddPort?: () => void;
  portAvailability?: { enabled: boolean; reason: string };
}) {
  const [open, setOpen] = useState(false);
  const containerRef = useRef<HTMLDivElement>(null);
  const triggerRef = useRef<HTMLButtonElement>(null);
  const menuId = `${section.section_id}-options-menu`;
  const circuitRef = section.entity_ref
    && (section.entity_ref.entity_kind === "design" || section.entity_ref.entity_kind === "component")
    ? section.entity_ref
    : null;

  const close = (restoreFocus = false) => {
    setOpen(false);
    if (restoreFocus) triggerRef.current?.focus();
  };

  const openMenu = () => {
    window.dispatchEvent(new CustomEvent(SPEC_SECTION_MENU_OPEN_EVENT, {
      detail: { menuId },
    }));
    setOpen(true);
  };

  useEffect(() => {
    const onPointerDown = (event: PointerEvent) => {
      if (!containerRef.current?.contains(event.target as Node)) close();
    };
    const onOtherMenu = (event: Event) => {
      const detail = (event as CustomEvent<{ menuId: string }>).detail;
      if (detail.menuId !== menuId) close();
    };
    document.addEventListener("pointerdown", onPointerDown);
    window.addEventListener(SPEC_SECTION_MENU_OPEN_EVENT, onOtherMenu);
    return () => {
      document.removeEventListener("pointerdown", onPointerDown);
      window.removeEventListener(SPEC_SECTION_MENU_OPEN_EVENT, onOtherMenu);
    };
  }, [menuId]);

  useEffect(() => {
    if (!open) return;
    const firstItem = containerRef.current?.querySelector<HTMLButtonElement>("[role='menuitem']:not(:disabled)");
    firstItem?.focus();
  }, [open]);

  const onMenuKeyDown = (event: React.KeyboardEvent<HTMLDivElement>) => {
    if (event.key === "Escape") {
      event.preventDefault();
      close(true);
      return;
    }
    if (!["ArrowDown", "ArrowUp", "Home", "End"].includes(event.key)) return;
    const items = Array.from(
      containerRef.current?.querySelectorAll<HTMLButtonElement>("[role='menuitem']:not(:disabled)") ?? [],
    );
    if (!items.length) return;
    event.preventDefault();
    const current = items.indexOf(document.activeElement as HTMLButtonElement);
    const index = event.key === "Home" ? 0
      : event.key === "End" ? items.length - 1
        : event.key === "ArrowDown" ? (current + 1) % items.length
          : (current <= 0 ? items.length : current) - 1;
    items[index]?.focus();
  };

  return (
    <div className="spec-section-options" ref={containerRef}>
      <button
        aria-controls={menuId}
        aria-expanded={open}
        aria-haspopup="menu"
        className="spec-options-trigger"
        onClick={() => open ? close() : openMenu()}
        onKeyDown={(event) => {
          if (event.key === "Escape" && open) {
            event.preventDefault();
            close(true);
          } else if (["ArrowDown", "Enter", " "].includes(event.key) && !open) {
            event.preventDefault();
            openMenu();
          }
        }}
        ref={triggerRef}
        type="button"
      >
        Options <span aria-hidden="true">▾</span>
      </button>
      {open && (
        <div
          aria-label={`Options for ${section.title}`}
          className="spec-options-menu"
          id={menuId}
          onKeyDown={onMenuKeyDown}
          role="menu"
        >
          {section.section_id === "components" && onCreate && (
            <button
              onClick={() => {
                close(true);
                onCreate("component");
              }}
              role="menuitem"
              type="button"
            >
              Add component…
            </button>
          )}
          {section.section_id === "designs" && onCreate && (
            <button
              onClick={() => {
                close(true);
                onCreate("design");
              }}
              role="menuitem"
              type="button"
            >
              Add design…
            </button>
          )}
          {onEditDetails && (
            <button
              onClick={() => {
                close(true);
                onEditDetails();
              }}
              role="menuitem"
              type="button"
            >
              Edit details…
            </button>
          )}
          {onAddPort && (
            <button
              disabled={!portAvailability?.enabled}
              onClick={() => {
                close(true);
                onAddPort();
              }}
              role="menuitem"
              title={portAvailability?.enabled ? undefined : portAvailability?.reason}
              type="button"
            >
              <span>Add port…</span>
              {!portAvailability?.enabled && <small>Composite</small>}
            </button>
          )}
          {circuitRef && (
            <button
              onClick={() => {
                close(true);
                dispatchOpenCircuit(circuitRef);
              }}
              role="menuitem"
              type="button"
            >
              Open circuit
            </button>
          )}
          <button disabled role="menuitem" type="button">
            <span>Launch activity</span><small>Coming soon</small>
          </button>
          {section.entity_ref && (
            <button
              onClick={() => {
                close(true);
                dispatchEntityAction(section.entity_ref as EntityRef);
              }}
              role="menuitem"
              type="button"
            >
              More actions…
            </button>
          )}
        </div>
      )}
    </div>
  );
}

function FactList({
  section,
  changedPaths = [],
  excludeLabels = [],
}: {
  section: DocumentSectionData;
  changedPaths?: string[];
  excludeLabels?: string[];
}) {
  const facts = section.facts.filter((fact) => fact.value && !excludeLabels.includes(fact.label));
  if (!facts.length) return null;
  return (
    <dl className="spec-facts">
      {facts.map((fact) => (
        <div
          className={changedPaths.some((path) =>
            path.includes(section.section_id) && path.includes(`.facts[${fact.label}]`)
          ) ? "spec-proposal-changed" : undefined}
          key={`${fact.label}-${fact.schema_path}`}
          title={fact.schema_path}
        >
          <dt>{fact.label}</dt>
          <dd>
            {fact.reference_anchor
              ? <a href={`#${fact.reference_anchor}`}>{fact.value}</a>
              : fact.value}
          </dd>
        </div>
      ))}
    </dl>
  );
}

type SectionEditMode = "" | "create-component" | "create-design" | "metadata" | "add-port";

interface SectionEditState {
  section: DocumentSectionData;
  mode: SectionEditMode;
  editorId: string;
  controller: SpecDocumentEditController | null;
  portAvailability: { enabled: boolean; reason: string };
  cancel(): void;
}

const SectionEditContext = createContext<SectionEditState | null>(null);

function factValue(section: DocumentSectionData, label: string): string {
  return section.facts.find((fact) => fact.label === label)?.value ?? "";
}

function focusSectionOptions(sectionId: string): void {
  document.getElementById(sectionId)?.querySelector<HTMLButtonElement>(".spec-options-trigger")?.focus();
}

function EntityCreationForm({
  kind,
  state,
}: {
  kind: "component" | "design";
  state: SectionEditState;
}) {
  const [name, setName] = useState("");
  const [error, setError] = useState("");
  const [busy, setBusy] = useState(false);
  const inputRef = useRef<HTMLInputElement>(null);
  useEffect(() => inputRef.current?.focus(), []);

  const submit = async (event: React.FormEvent) => {
    event.preventDefault();
    if (!name.trim() || !state.controller) {
      setError("Name is required.");
      return;
    }
    if (!/^[A-Za-z_][A-Za-z0-9_.-]*$/.test(name.trim())) {
      setError("Use a letter or underscore first, followed by letters, numbers, dots, underscores, or hyphens.");
      return;
    }
    setBusy(true);
    setError("");
    try {
      await state.controller.createEntity(kind, name.trim());
      state.cancel();
    } catch (caught) {
      setError(caught instanceof Error ? caught.message : String(caught));
    } finally {
      setBusy(false);
    }
  };

  return (
    <form className="spec-inline-editor spec-create-editor" onSubmit={submit}>
      <div>
        <label htmlFor={`${state.editorId}-name`}>{kind === "component" ? "Component" : "Design"} name</label>
        <input
          autoComplete="off"
          id={`${state.editorId}-name`}
          onChange={(event) => setName(event.target.value)}
          pattern="[A-Za-z_][A-Za-z0-9_.-]*"
          ref={inputRef}
          title="Start with a letter or underscore; then use letters, numbers, dots, underscores, or hyphens."
          value={name}
        />
        <small>Creates <code>spec2gds.local:work:{name.trim() || "name"}:1.0</code>.</small>
      </div>
      {error && <p className="spec-edit-error" role="alert">{error}</p>}
      <div className="spec-edit-actions">
        <button disabled={busy} type="submit">{busy ? "Creating…" : `Create ${kind}`}</button>
        <button disabled={busy} onClick={state.cancel} type="button">Cancel</button>
      </div>
    </form>
  );
}

function EntityMetadataForm({ state }: { state: SectionEditState }) {
  const [displayName, setDisplayName] = useState(() => factValue(state.section, "Display name"));
  const [shortDescription, setShortDescription] = useState(() => factValue(state.section, "Short description"));
  const [description, setDescription] = useState(() => factValue(state.section, "Description"));
  const [error, setError] = useState("");
  const [busy, setBusy] = useState(false);
  const inputRef = useRef<HTMLInputElement>(null);
  useEffect(() => inputRef.current?.focus(), []);

  const submit = async (event: React.FormEvent) => {
    event.preventDefault();
    const ref = state.section.entity_ref;
    if (!ref || !state.controller) return;
    setBusy(true);
    setError("");
    try {
      await state.controller.updateEntityMetadata(ref, {
        display_name: displayName,
        short_description: shortDescription,
        description,
      });
      state.cancel();
    } catch (caught) {
      setError(caught instanceof Error ? caught.message : String(caught));
    } finally {
      setBusy(false);
    }
  };

  return (
    <form className="spec-inline-editor spec-metadata-editor" onSubmit={submit}>
      <div>
        <label htmlFor={`${state.editorId}-display-name`}>Display name</label>
        <input
          id={`${state.editorId}-display-name`}
          onChange={(event) => setDisplayName(event.target.value)}
          ref={inputRef}
          value={displayName}
        />
      </div>
      <div>
        <label htmlFor={`${state.editorId}-short-description`}>Short description</label>
        <input
          id={`${state.editorId}-short-description`}
          onChange={(event) => setShortDescription(event.target.value)}
          value={shortDescription}
        />
      </div>
      <div className="spec-edit-field-wide">
        <label htmlFor={`${state.editorId}-description`}>Description</label>
        <textarea
          id={`${state.editorId}-description`}
          onChange={(event) => setDescription(event.target.value)}
          rows={4}
          value={description}
        />
      </div>
      {error && <p className="spec-edit-error" role="alert">{error}</p>}
      <div className="spec-edit-actions spec-edit-field-wide">
        <button disabled={busy} type="submit">{busy ? "Saving…" : "Save changes"}</button>
        <button disabled={busy} onClick={state.cancel} type="button">Cancel</button>
      </div>
    </form>
  );
}

const SpecSection = createComponentImplementation(
  SpecSectionApi,
  ({ props, buildChild }) => {
    const section = props.section as DocumentSectionData;
    const coordinator = useContext(EditCoordinatorContext);
    const [mode, setMode] = useState<SectionEditMode>("");
    const Heading = (section.level === 1 ? "h2" : "h3") as "h2" | "h3";
    const editorId = mode ? `${section.section_id}-${mode}` : "";
    const portAvailability = section.entity_ref?.entity_kind === "component" && coordinator.controller
      ? coordinator.controller.portEditingAvailability(section.entity_ref)
      : { enabled: false, reason: "Port editing is unavailable." };

    const begin = (nextMode: Exclude<SectionEditMode, "">) => {
      const nextEditorId = `${section.section_id}-${nextMode}`;
      if (coordinator.requestEditor(nextEditorId)) setMode(nextMode);
    };
    const cancel = () => {
      if (editorId) coordinator.finishEditor(editorId);
      setMode("");
      focusSectionOptions(section.section_id);
    };
    const editState: SectionEditState = {
      section,
      mode,
      editorId,
      controller: coordinator.controller,
      portAvailability,
      cancel,
    };
    const entityIsEditable = coordinator.controller
      && section.entity_ref
      && ["component", "design"].includes(section.entity_ref.entity_kind);

    return (
      <SectionEditContext.Provider value={editState}>
        <section
          className={`spec-section spec-section--level-${section.level}`}
          id={section.section_id}
        >
          <header className="spec-section__header">
            <div>
              {section.eyebrow && <p className="spec-kicker">{section.eyebrow}</p>}
              <Heading>{section.title}</Heading>
            </div>
            <SectionOptionsMenu
              onAddPort={section.entity_ref?.entity_kind === "component" && coordinator.controller
                ? () => begin("add-port")
                : undefined}
              onCreate={coordinator.controller && ["components", "designs"].includes(section.section_id)
                ? (kind) => begin(kind === "component" ? "create-component" : "create-design")
                : undefined}
              onEditDetails={entityIsEditable ? () => begin("metadata") : undefined}
              portAvailability={portAvailability}
              section={section}
            />
          </header>
          {mode === "create-component" && <EntityCreationForm kind="component" state={editState} />}
          {mode === "create-design" && <EntityCreationForm kind="design" state={editState} />}
          <FactList
            excludeLabels={mode === "metadata"
              ? ["Display name", "Short description", "Description"]
              : []}
            section={section}
          />
          {mode === "metadata" && <EntityMetadataForm state={editState} />}
          {renderChildren(props.children, buildChild)}
        </section>
      </SectionEditContext.Provider>
    );
  },
);

function CellValue({ cell }: { cell: DocumentCell }) {
  if (cell.presence === "absent") {
    return <span className="spec-cell--absent" aria-label="Not present in source">—</span>;
  }
  const text = typeof cell.value === "boolean"
    ? (cell.value ? "Yes" : "No")
    : String(cell.value ?? "");
  const content = cell.reference_anchor
    ? <a href={`#${cell.reference_anchor}`}>{text}</a>
    : text;
  return (
    <>
      {content}
      {cell.presence === "defaulted" && (
        <span className="spec-default-badge" title="Value supplied by the IP-XACT profile default">
          default
        </span>
      )}
    </>
  );
}

const SpecTable = createComponentImplementation(
  SpecTableApi,
  ({ props }) => <DocumentTableView table={props.table as DocumentTable} />,
);

export function DocumentTableView({
  table,
  changedPaths = [],
}: {
  table: DocumentTable;
  changedPaths?: string[];
}) {
  const sectionEdit = useContext(SectionEditContext);
  const editablePorts = table.kind === "component_ports"
    && sectionEdit?.section.entity_ref?.entity_kind === "component"
    && sectionEdit.controller;
  const showActions = Boolean(editablePorts);
  return (
    <section className="spec-table-block" aria-labelledby={`${table.table_id}-title`}>
        <div className="spec-table-block__heading">
          <h4 id={`${table.table_id}-title`}>{table.title}</h4>
          <span>{table.rows.length} {table.rows.length === 1 ? "entry" : "entries"}</span>
        </div>
        <div className="spec-table-scroll">
          <table>
            <thead>
              <tr>
                {table.columns.map((column) => (
                  <th key={column.key} scope="col" title={column.schema_path}>
                    {column.label}
                  </th>
                ))}
                {showActions && <th scope="col">Actions</th>}
              </tr>
            </thead>
            <tbody>
              {sectionEdit?.mode === "add-port" && editablePorts && (
                <PortEditorRows
                  adding
                  columns={table.columns.map((column) => column.key)}
                  sectionEdit={sectionEdit}
                />
              )}
              {table.rows.map((row) => editablePorts ? (
                <EditablePortRow
                  changedPaths={changedPaths}
                  key={row.row_id}
                  row={row}
                  sectionEdit={sectionEdit}
                  table={table}
                />
              ) : (
                <tr
                  className={changedPaths.some((path) =>
                    path.includes(table.table_id) && path.includes(row.row_id)
                  ) ? "spec-proposal-row-changed" : undefined}
                  key={row.row_id}
                >
                    {table.columns.map((column) => {
                      const cell = row.cells[column.key];
                      return (
                        <td
                          className={changedPaths.some((path) =>
                            path.includes(table.table_id)
                            && path.includes(row.row_id)
                            && path.includes(`.cells.${column.key}`)
                          ) ? "spec-proposal-changed" : undefined}
                          key={column.key}
                          title={cell?.schema_path || column.schema_path}
                        >
                          {cell ? <CellValue cell={cell} /> : <span className="spec-cell--absent">—</span>}
                        </td>
                      );
                    })}
                  </tr>
              ))}
            </tbody>
          </table>
        </div>
    </section>
  );
}

function rowText(row: DocumentTable["rows"][number], key: string): string {
  const value = row.cells[key]?.value;
  return value === null || value === undefined ? "" : String(value);
}

function EditablePortRow({
  row,
  table,
  changedPaths,
  sectionEdit,
}: {
  row: DocumentTable["rows"][number];
  table: DocumentTable;
  changedPaths: string[];
  sectionEdit: SectionEditState;
}) {
  const coordinator = useContext(EditCoordinatorContext);
  const [editing, setEditing] = useState(false);
  const buttonRef = useRef<HTMLButtonElement>(null);
  const name = rowText(row, "name");
  const editorId = `${sectionEdit.section.section_id}-port-${name}`;
  if (editing) {
    return (
      <PortEditorRows
        columns={table.columns.map((column) => column.key)}
        initial={{
          name,
          direction: rowText(row, "direction") as WirePortInput["direction"],
          left: rowText(row, "left") || null,
          right: rowText(row, "right") || null,
          description: rowText(row, "description"),
        }}
        onFinished={() => {
          coordinator.finishEditor(editorId);
          setEditing(false);
          window.setTimeout(() => buttonRef.current?.focus(), 0);
        }}
        sectionEdit={sectionEdit}
      />
    );
  }
  const isWire = rowText(row, "style") === "wire";
  const canEdit = sectionEdit.portAvailability.enabled && isWire;
  return (
    <tr
      className={changedPaths.some((path) =>
        path.includes(table.table_id) && path.includes(row.row_id)
      ) ? "spec-proposal-row-changed" : undefined}
    >
      {table.columns.map((column) => {
        const cell = row.cells[column.key];
        return (
          <td key={column.key} title={cell?.schema_path || column.schema_path}>
            {cell ? <CellValue cell={cell} /> : <span className="spec-cell--absent">—</span>}
          </td>
        );
      })}
      <td className="spec-port-actions">
        {canEdit ? (
          <button
            onClick={() => {
              if (coordinator.requestEditor(editorId)) setEditing(true);
            }}
            ref={buttonRef}
            type="button"
          >
            Edit
          </button>
        ) : (
          <small title={isWire ? sectionEdit.portAvailability.reason : "Transactional ports are read-only."}>
            {isWire ? "Composite boundary" : "Transactional"}
          </small>
        )}
      </td>
    </tr>
  );
}

function PortEditorRows({
  adding = false,
  columns,
  initial,
  onFinished,
  sectionEdit,
}: {
  adding?: boolean;
  columns: string[];
  initial?: WirePortInput;
  onFinished?: () => void;
  sectionEdit: SectionEditState;
}) {
  const [name, setName] = useState(initial?.name ?? "");
  const [direction, setDirection] = useState<WirePortInput["direction"]>(initial?.direction ?? "in");
  const [left, setLeft] = useState(initial?.left ?? "");
  const [right, setRight] = useState(initial?.right ?? "");
  const [description, setDescription] = useState(initial?.description ?? "");
  const [error, setError] = useState("");
  const [busy, setBusy] = useState(false);
  const rowRef = useRef<HTMLTableRowElement>(null);
  useEffect(() => rowRef.current?.querySelector<HTMLInputElement | HTMLSelectElement>("input, select")?.focus(), []);
  const finish = onFinished ?? sectionEdit.cancel;
  const ref = sectionEdit.section.entity_ref;

  const save = async () => {
    if (!sectionEdit.controller || !ref) return;
    if (!name.trim()) {
      setError("Port name is required.");
      return;
    }
    if ((left.trim() && !right.trim()) || (!left.trim() && right.trim())) {
      setError("Vector ports require both left and right bounds.");
      return;
    }
    setBusy(true);
    setError("");
    const value: WirePortInput = {
      name: name.trim(),
      direction,
      left: left.trim() || null,
      right: right.trim() || null,
      description,
    };
    try {
      if (adding) await sectionEdit.controller.addComponentPort(ref, value);
      else await sectionEdit.controller.updateComponentPort(ref, value.name, {
        direction: value.direction,
        left: value.left,
        right: value.right,
        description: value.description,
      });
      finish();
    } catch (caught) {
      setError(caught instanceof Error ? caught.message : String(caught));
    } finally {
      setBusy(false);
    }
  };

  const editorCell = (key: string): React.ReactNode => {
    const id = `${sectionEdit.section.section_id}-${adding ? "new" : name}-${key}`;
    if (key === "name") return adding ? (
      <input aria-label="Port name" id={id} onChange={(event) => setName(event.target.value)} value={name} />
    ) : <strong>{name}</strong>;
    if (key === "style") return "wire";
    if (key === "direction") return (
      <select aria-label={`Direction for ${name || "new port"}`} id={id} onChange={(event) => setDirection(event.target.value as WirePortInput["direction"])} value={direction}>
        <option value="in">in</option>
        <option value="out">out</option>
        <option value="inout">inout</option>
      </select>
    );
    if (key === "left") return <input aria-label={`Left bound for ${name || "new port"}`} id={id} onChange={(event) => setLeft(event.target.value)} value={left} />;
    if (key === "right") return <input aria-label={`Right bound for ${name || "new port"}`} id={id} onChange={(event) => setRight(event.target.value)} value={right} />;
    if (key === "description") return <input aria-label={`Description for ${name || "new port"}`} id={id} onChange={(event) => setDescription(event.target.value)} value={description} />;
    return <span className="spec-cell--absent">—</span>;
  };

  return (
    <>
      <tr className="spec-port-edit-row" ref={rowRef}>
        {columns.map((key) => <td key={key}>{editorCell(key)}</td>)}
        <td className="spec-port-actions">
          <button disabled={busy} onClick={() => void save()} type="button">{busy ? "Saving…" : "Save"}</button>
          <button disabled={busy} onClick={finish} type="button">Cancel</button>
        </td>
      </tr>
      {error && (
        <tr className="spec-port-error-row">
          <td colSpan={columns.length + 1}><span role="alert">{error}</span></td>
        </tr>
      )}
    </>
  );
}

function safeHref(value: string): string | undefined {
  if (value.startsWith("#") || value.startsWith("/assets/")) return value;
  try {
    const parsed = new URL(value, window.location.origin);
    return ["http:", "https:"].includes(parsed.protocol) ? value : undefined;
  } catch {
    return undefined;
  }
}

function renderInlines(block: NarrativeBlockData): React.ReactNode {
  if (!block.inlines.length) return block.text;
  return block.inlines.map((inline, index) => {
    const key = `${block.block_id}-inline-${index}`;
    if (inline.type === "emphasis") return <em key={key}>{inline.text}</em>;
    if (inline.type === "strong") return <strong key={key}>{inline.text}</strong>;
    if (inline.type === "code") return <code key={key}>{inline.text}</code>;
    if (inline.type === "link") {
      const href = inline.entity_ref
        ? `#${inline.entity_ref.entity_kind.replaceAll("_", "-")}-${inline.entity_ref.entity_id}`
        : safeHref(inline.href);
      return href
        ? <a href={href} key={key}>{inline.text}</a>
        : <span key={key}>{inline.text}</span>;
    }
    return <Fragment key={key}>{inline.text}</Fragment>;
  });
}

function NarrativeNode({ block }: { block: NarrativeBlockData }): React.ReactNode {
  if (block.type === "section") {
    return (
      <section className="spec-narrative__section">
        <h4>{block.text}</h4>
        {block.children.map((child) => <NarrativeNode block={child} key={child.block_id} />)}
      </section>
    );
  }
  if (block.type === "list") {
    const ListTag = block.ordered ? "ol" : "ul";
    return (
      <ListTag>
        {block.children.map((child) => <li key={child.block_id}><NarrativeNode block={child} /></li>)}
      </ListTag>
    );
  }
  if (block.type === "table") {
    return (
      <div className="spec-table-scroll">
        <table className="spec-narrative__table">
          <tbody>
            {block.rows.map((row, rowIndex) => (
              <tr key={`${block.block_id}-${rowIndex}`}>
                {row.map((cell, cellIndex) => <td key={cellIndex}>{cell}</td>)}
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    );
  }
  if (block.type === "image") {
    return (
      <figure>
        <img src={`/assets/${encodeURIComponent(block.asset_id)}/content`} alt={block.alt_text} />
        {block.caption && <figcaption>{block.caption}</figcaption>}
      </figure>
    );
  }
  return <p>{renderInlines(block)}</p>;
}

export function DocumentSectionView({
  section,
  changedPaths = [],
  label,
}: {
  section: DocumentSectionData;
  changedPaths?: string[];
  label?: string;
}) {
  const Heading = (section.level === 1 ? "h2" : "h3") as "h2" | "h3";
  return (
    <section className="spec-section spec-section--proposal" id={section.section_id}>
      <header className="spec-section__header">
        <div>
          {label && <p className="spec-kicker">{label}</p>}
          <Heading>{section.title}</Heading>
        </div>
      </header>
      <FactList section={section} changedPaths={changedPaths} />
      {section.tables.map((table) => (
        <DocumentTableView table={table} changedPaths={changedPaths} key={table.table_id} />
      ))}
      {section.narrative.map((block) => (
        <div
          className={changedPaths.some((path) => path.includes(block.block_id))
            ? "spec-narrative spec-proposal-changed"
            : "spec-narrative"}
          key={block.block_id}
        >
          <NarrativeNode block={block} />
        </div>
      ))}
    </section>
  );
}

const NarrativeBlock = createComponentImplementation(
  NarrativeBlockApi,
  ({ props }) => (
    <div className="spec-narrative">
      <NarrativeExploreButton block={props.block as NarrativeBlockData} documentId={props.documentId} />
      <NarrativeNode block={props.block as NarrativeBlockData} />
    </div>
  ),
);

const EntityLink = createComponentImplementation(
  EntityLinkApi,
  ({ props }) => {
    const block = props.block as NarrativeBlockData;
    return (
      <div className="spec-callout spec-callout--link">
        <span className="spec-callout__icon" aria-hidden="true">↗</span>
        <div>
          <NarrativeExploreButton block={block} documentId={props.documentId} />
          <strong>{block.text || "Related specification entities"}</strong>
          <div className="spec-link-row">
            {block.entity_refs.map((ref) => (
              <a
                href={`#${ref.entity_kind.replaceAll("_", "-")}-${ref.entity_id}`}
                key={`${ref.entity_kind}-${ref.entity_id}`}
              >
                {ref.entity_kind.replaceAll("_", " ")} · {ref.entity_id}
              </a>
            ))}
          </div>
        </div>
      </div>
    );
  },
);

const LiveView = createComponentImplementation(
  LiveViewApi,
  ({ props }) => {
    const block = props.block as NarrativeBlockData;
    return (
      <div className="spec-callout spec-callout--live">
        <span className="spec-live-dot" aria-hidden="true" />
        <div>
          <NarrativeExploreButton block={block} documentId={props.documentId} />
          <strong>{block.text || "Live design view"}</strong>
          <p>Renderer: <code>{block.renderer_id || "default"}</code></p>
          {block.entity_refs.map((ref) => (
            <a
              href={`#${ref.entity_kind.replaceAll("_", "-")}-${ref.entity_id}`}
              key={`${ref.entity_kind}-${ref.entity_id}`}
            >
              Open {ref.entity_kind.replaceAll("_", " ")}
            </a>
          ))}
        </div>
      </div>
    );
  },
);

function NarrativeExploreButton({ block, documentId }: { block: NarrativeBlockData; documentId: string }) {
  return (
    <button
      className="spec-narrative-action"
      type="button"
      onClick={() => dispatchEntityAction({
        document_id: documentId,
        entity_id: block.block_id,
        entity_kind: "narrative_block",
      })}
    >
      Actions
    </button>
  );
}

export const specDocumentCatalog = new Catalog(
  SPEC_DOCUMENT_CATALOG_ID,
  [SpecDocument, SpecSection, SpecTable, NarrativeBlock, EntityLink, LiveView],
);

export function createDocumentMessageProcessor(batch: A2UIDocumentBatch) {
  if (batch.catalog_id !== SPEC_DOCUMENT_CATALOG_ID) {
    throw new Error(`Unsupported A2UI catalog: ${batch.catalog_id}`);
  }
  if (batch.protocol_version !== "v0.9") {
    throw new Error(`Unsupported A2UI protocol: ${batch.protocol_version}`);
  }
  const processor = new MessageProcessor([specDocumentCatalog]);
  processor.processMessages(batch.messages as A2uiMessage[]);
  return processor;
}

export function A2UIDocumentSurface({
  batch,
  editController,
}: {
  batch: A2UIDocumentBatch;
  editController?: SpecDocumentEditController;
}) {
  const processor = useMemo(() => createDocumentMessageProcessor(batch), [batch]);
  const surface = processor.model.surfacesMap.get(batch.surface_id);
  if (!surface) {
    return <div className="spec-render-error" role="alert">The A2UI document surface was not created.</div>;
  }
  return (
    <EditCoordinatorProvider controller={editController} resetKey={batch.source_revision_hash}>
      <A2uiSurface surface={surface} />
    </EditCoordinatorProvider>
  );
}
