/** Render the owner-produced specification projection and inline editing surfaces.
 * Draft text retains the revision it was authored against. A newer live view
 * must not overwrite it or restamp its save; the host must resolve a stale edit.
 * Source paths and semantic IDs come from the projection, not DOM layout. */
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
import { basicSetup } from "codemirror";
import { EditorState } from "@codemirror/state";
import { EditorView } from "@codemirror/view";
import { StreamLanguage } from "@codemirror/language";
import { setDiagnostics, type Diagnostic } from "@codemirror/lint";
import { verilog } from "@codemirror/legacy-modes/mode/verilog";
import {
  SPEC_DOCUMENT_CATALOG_ID,
  type PersistedEntitySectionType,
} from "./section-registry";
import { DesignTopologyLiveView } from "./DesignTopologyLiveView";
export { SPEC_DOCUMENT_CATALOG_ID, PERSISTED_ENTITY_SECTION_TYPES } from "./section-registry";

import type {
  A2UIDocumentBatch,
  ComponentInstanceInput,
  ComponentPortInput,
  ComponentPortUpdateInput,
  DocumentCell,
  DocumentSectionData,
  DocumentTable,
  EntityMetadataInput,
  EntityRef,
  EntityContentSection,
  NarrativeBlock as NarrativeBlockData,
  TocEntry,
  TransactionalPortKind,
} from "@spec2gds/document-core";

export const SPEC_HARDWARE_ACTION_EVENT = "spec2gds:entity-action";
export const SPEC_OPEN_CIRCUIT_EVENT = "spec2gds:open-circuit";
export const SPEC_LAUNCH_ACTIVITY_EVENT = "spec2gds:launch-activity";

export interface SpecOpenCircuitEventDetail {
  entityRef: EntityRef;
}

export interface SpecLaunchActivityEventDetail {
  entityRef: EntityRef;
}

export interface SpecDocumentEditController {
  updateDocumentTitle(title: string): Promise<void>;
  createEntity(kind: "component" | "design", name: string): Promise<void>;
  addComponentInstance(design: EntityRef, value: ComponentInstanceInput): Promise<void>;
  componentInstanceOptions(): ComponentInstanceOption[];
  updateEntityMetadata(ref: EntityRef, value: EntityMetadataInput): Promise<void>;
  renameNarrativeSection?(blockId: string, name: string): Promise<void>;
  addComponentPort(ref: EntityRef, value: ComponentPortInput): Promise<void>;
  updateComponentPort(ref: EntityRef, name: string, value: ComponentPortUpdateInput): Promise<void>;
  upsertEntitySection(ref: EntityRef, content: string, sectionId?: string): Promise<void>;
  deleteEntitySection(ref: EntityRef, sectionId?: string): Promise<void>;
  portEditingAvailability(ref: EntityRef): { enabled: boolean; reason: string };
}

export interface ComponentInstanceOption {
  label: string;
  vlnv: string;
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
  onEditingChange,
  resetKey,
}: {
  controller?: SpecDocumentEditController;
  children: React.ReactNode;
  onEditingChange?: (editing: boolean) => void;
  resetKey: string;
}) {
  const [activeEditorId, setActiveEditorId] = useState("");
  const [notice, setNotice] = useState("");
  useEffect(() => {
    setActiveEditorId("");
    setNotice("");
  }, [resetKey]);
  useEffect(() => {
    onEditingChange?.(Boolean(activeEditorId));
  }, [activeEditorId, onEditingChange]);
  useEffect(() => () => onEditingChange?.(false), [onEditingChange]);
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

const SpecEntitySectionApi = {
  name: "SpecEntitySection",
  schema: z.object({ section: z.custom<EntityContentSection>() }),
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

function DocumentContents({ entries }: { entries: TocEntry[] }) {
  const [activeId, setActiveId] = useState(entries[0]?.section_id ?? "");
  const [open, setOpen] = useState(false);
  const rootRef = useRef<HTMLElement>(null);
  const triggerRef = useRef<HTMLButtonElement>(null);
  const ids = entries.map(entry => entry.section_id).join("\0");

  useEffect(() => {
    let frame = 0;
    const update = () => {
      frame = 0;
      const sections = ids.split("\0").map(id => document.getElementById(id)).filter((section): section is HTMLElement => Boolean(section));
      if (!sections.length) return;
      const offset = (document.querySelector(".app-header")?.getBoundingClientRect().height ?? 0) + 32;
      let current = sections[0];
      for (const section of sections) {
        if (section.getBoundingClientRect().top <= offset) current = section;
      }
      if (window.scrollY + window.innerHeight >= document.documentElement.scrollHeight - 1) current = sections[sections.length - 1];
      setActiveId(current.id);
    };
    const schedule = () => { if (!frame) frame = requestAnimationFrame(update); };
    window.addEventListener("scroll", schedule, { passive: true });
    window.addEventListener("resize", schedule);
    window.addEventListener("hashchange", schedule);
    const observer = new ResizeObserver(schedule);
    const paper = rootRef.current?.parentElement?.querySelector(".spec-paper");
    if (paper) observer.observe(paper);
    schedule();
    return () => {
      cancelAnimationFrame(frame);
      observer.disconnect();
      window.removeEventListener("scroll", schedule);
      window.removeEventListener("resize", schedule);
      window.removeEventListener("hashchange", schedule);
    };
  }, [ids]);

  useEffect(() => {
    if (!open) return;
    const close = (event: PointerEvent) => { if (!rootRef.current?.contains(event.target as Node)) setOpen(false); };
    document.addEventListener("pointerdown", close);
    return () => document.removeEventListener("pointerdown", close);
  }, [open]);

  return <aside className={`spec-toc${open ? " spec-toc--open" : ""}`} aria-label="Document contents" ref={rootRef} onKeyDown={event => {
    if (event.key === "Escape" && open) { setOpen(false); triggerRef.current?.focus(); }
  }}>
    <button className="spec-toc__trigger" type="button" aria-controls="spec-contents-navigation" aria-expanded={open} ref={triggerRef} onClick={() => setOpen(!open)}>Contents</button>
    <div className="spec-toc__sticky">
      <p className="spec-toc__label">Contents</p>
      <nav id="spec-contents-navigation" aria-label="Spec Sections">
        {entries.map(entry => <a className={`spec-toc__link spec-toc__link--level-${entry.level}`} aria-current={activeId === entry.section_id ? "location" : undefined} href={`#${entry.section_id}`} key={entry.section_id} onClick={() => {
          setActiveId(entry.section_id);
          setOpen(false);
          requestAnimationFrame(() => {
            const section = document.getElementById(entry.section_id);
            const heading = section?.querySelector<HTMLElement>("h2, h3");
            heading?.focus({ preventScroll: true });
            section?.scrollIntoView({ block: "start" });
          });
        }}>{entry.title}</a>)}
      </nav>
    </div>
  </aside>;
}

const SpecDocument = createComponentImplementation(
  SpecDocumentApi,
  ({ props, buildChild }) => {
    const coordinator = useContext(EditCoordinatorContext);
    const [editingTitle, setEditingTitle] = useState(false);
    const [draftTitle, setDraftTitle] = useState(props.title);
    const [titleError, setTitleError] = useState("");
    const [titleBusy, setTitleBusy] = useState(false);
    const editButtonRef = useRef<HTMLButtonElement>(null);
    const inputRef = useRef<HTMLInputElement>(null);
    const editorId = "document-title";

    useEffect(() => {
      if (editingTitle) inputRef.current?.focus();
    }, [editingTitle]);

    const finishTitleEdit = () => {
      coordinator.finishEditor(editorId);
      setEditingTitle(false);
      setTitleError("");
      window.setTimeout(() => editButtonRef.current?.focus(), 0);
    };

    const saveTitle = async (event: React.FormEvent) => {
      event.preventDefault();
      const title = draftTitle.trim();
      if (!title) {
        setTitleError("Spec name is required.");
        return;
      }
      if (!coordinator.controller) return;
      setTitleBusy(true);
      setTitleError("");
      try {
        await coordinator.controller.updateDocumentTitle(title);
        finishTitleEdit();
      } catch (caught) {
        setTitleError(caught instanceof Error ? caught.message : String(caught));
      } finally {
        setTitleBusy(false);
      }
    };

    return (
      <div className="spec-document">
        <DocumentContents entries={props.toc as TocEntry[]} />
        <article className="spec-paper">
          <header className="spec-cover">

            {editingTitle ? (
              <form className="spec-title-editor" onSubmit={saveTitle}>
                <label htmlFor="specification-title">Spec name</label>
                <input
                  id="specification-title"
                  maxLength={200}
                  onChange={(event) => setDraftTitle(event.target.value)}
                  ref={inputRef}
                  value={draftTitle}
                />
                {titleError && <p className="spec-edit-error" role="alert">{titleError}</p>}
                <div className="spec-edit-actions">
                  <button disabled={titleBusy} type="submit">{titleBusy ? "Saving…" : "Save to Spec"}</button>
                  <button disabled={titleBusy} onClick={finishTitleEdit} type="button">Cancel</button>
                </div>
              </form>
            ) : (
              <div className="spec-cover__title-row">
                <h1>{props.title}</h1>
                {coordinator.controller && (
                  <button
                    className="spec-title-edit-button"
                    onClick={() => {
                      if (coordinator.requestEditor(editorId)) {
                        setDraftTitle(props.title);
                        setEditingTitle(true);
                      }
                    }}
                    ref={editButtonRef}
                    type="button"
                  >
                    Edit name
                  </button>
                )}
              </div>
            )}
            <p>{props.summary}</p>
            <details className="spec-document-details"><summary>Technical details</summary><dl className="spec-toc__meta">
              <div><dt>Document</dt><dd>{props.documentId}</dd></div>
              <div title={props.sourceRevisionHash}><dt>Revision</dt><dd><code>{shortHash(props.sourceRevisionHash)}</code></dd></div>
            </dl><button type="button" onClick={() => void navigator.clipboard.writeText(JSON.stringify({ document_id: props.documentId, revision: props.sourceRevisionHash }))}>Copy identifiers</button></details>
          </header>
          {renderChildren(props.children, buildChild)}
        </article>
      </div>
    );
  },
);

function dispatchEntityAction(entityRef: EntityRef): void {
  window.dispatchEvent(new CustomEvent(SPEC_HARDWARE_ACTION_EVENT, {
    detail: { entityRef },
  }));
}

function dispatchOpenCircuit(entityRef: EntityRef): void {
  window.dispatchEvent(new CustomEvent<SpecOpenCircuitEventDetail>(SPEC_OPEN_CIRCUIT_EVENT, {
    detail: { entityRef },
  }));
}

function dispatchLaunchActivity(entityRef: EntityRef): void {
  window.dispatchEvent(new CustomEvent<SpecLaunchActivityEventDetail>(SPEC_LAUNCH_ACTIVITY_EVENT, {
    detail: { entityRef },
  }));
}

function SectionOptionsMenu({
  section,
  onCreate,
  onRename,
  onEditDetails,
  onAddInstance,
  onAddPort,
  onAddSystemVerilog,
  instanceAvailability,
  portAvailability,
}: {
  section: DocumentSectionData;
  onCreate?: (kind: "component" | "design") => void;
  onRename?: () => void;
  onEditDetails?: () => void;
  onAddInstance?: () => void;
  onAddPort?: (family: ComponentPortInput["family"]) => void;
  onAddSystemVerilog?: () => void;
  instanceAvailability?: { enabled: boolean; reason: string };
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
          {onRename && (
            <button
              onClick={() => {
                close(true);
                onRename();
              }}
              role="menuitem"
              type="button"
            >
              Rename
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
              Edit text…
            </button>
          )}
          {onAddInstance && (
            <button
              disabled={!instanceAvailability?.enabled}
              onClick={() => {
                close(true);
                onAddInstance();
              }}
              role="menuitem"
              title={instanceAvailability?.enabled ? undefined : instanceAvailability?.reason}
              type="button"
            >
              <span>Add component instance…</span>
              {!instanceAvailability?.enabled && <small>No components</small>}
            </button>
          )}
          {onAddPort && (["wire", "transactional", "structured"] as const).map((family) => (
            <button
              disabled={!portAvailability?.enabled}
              key={family}
              onClick={() => {
                close(true);
                onAddPort(family);
              }}
              role="menuitem"
              title={portAvailability?.enabled ? undefined : portAvailability?.reason}
              type="button"
            >
              <span>Add {family} port…</span>
              {!portAvailability?.enabled && <small>Composite</small>}
            </button>
          ))}
          {onAddSystemVerilog && (
            <button
              onClick={() => {
                close(true);
                onAddSystemVerilog();
              }}
              role="menuitem"
              type="button"
            >
              Add section → SystemVerilog
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
          {section.entity_ref && (
            <button
              onClick={() => {
                close(true);
                dispatchLaunchActivity(section.entity_ref as EntityRef);
              }}
              role="menuitem"
              type="button"
            >
              Launch activity…
            </button>
          )}
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

const HIDDEN_IDENTITY_FACTS = new Set([
  "VLNV",
  "Vendor",
  "Library",
  "Name",
  "Version",
  "Display name",
  "Short description",
  "Description",
]);

function FactList({
  section,
  changedPaths = [],
  excludeLabels = [],
}: {
  section: DocumentSectionData;
  changedPaths?: string[];
  excludeLabels?: string[];
}) {
  const facts = section.facts.filter((fact) => (
    fact.value
    && !HIDDEN_IDENTITY_FACTS.has(fact.label)
    && !excludeLabels.includes(fact.label)
  ));
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
              ? <a href={`#${fact.reference_anchor}`}>{fact.display_text || fact.value}</a>
              : fact.display_text || fact.value}
          </dd>
        </div>
      ))}
    </dl>
  );
}

type SectionEditMode = ""
  | "create-component"
  | "create-design"
  | "add-component-instance"
  | "rename"
  | "metadata"
  | "add-wire-port"
  | "add-transactional-port"
  | "add-structured-port"
  | "add-sv";

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

function HardwareCreationForm({
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
          required
          maxLength={200}
          ref={inputRef}
          title="Enter a readable name. The hardware identifier is generated automatically."
          value={name}
        />
        <small>You can rename the section later without changing its hardware identifier.</small>
      </div>
      {error && <p className="spec-edit-error" role="alert">{error}</p>}
      <div className="spec-edit-actions">
        <button disabled={busy} type="submit">{busy ? "Creating…" : `Create ${kind}`}</button>
        <button disabled={busy} onClick={state.cancel} type="button">Cancel</button>
      </div>
    </form>
  );
}

function ComponentInstanceForm({ state }: { state: SectionEditState }) {
  const options = state.controller?.componentInstanceOptions() ?? [];
  const [name, setName] = useState("");
  const [componentVlnv, setComponentVlnv] = useState(options[0]?.vlnv ?? "");
  const [error, setError] = useState("");
  const [busy, setBusy] = useState(false);
  const inputRef = useRef<HTMLInputElement>(null);
  useEffect(() => inputRef.current?.focus(), []);
  const existingNames = new Set(
    state.section.tables
      .find((table) => table.kind === "design_instances")
      ?.rows.map((row) => String(row.cells.name?.value ?? "")) ?? [],
  );

  const submit = async (event: React.FormEvent) => {
    event.preventDefault();
    const design = state.section.entity_ref;
    const trimmedName = name.trim();
    if (!design || !state.controller) return;
    if (!trimmedName) {
      setError("Instance name is required.");
      return;
    }
    if (!/^[A-Za-z_][A-Za-z0-9_.-]*$/.test(trimmedName)) {
      setError("Use a letter or underscore first, followed by letters, numbers, dots, underscores, or hyphens.");
      return;
    }
    if (existingNames.has(trimmedName)) {
      setError(`This design already has an instance named ${trimmedName}.`);
      return;
    }
    if (!componentVlnv) {
      setError("Choose a component.");
      return;
    }
    setBusy(true);
    setError("");
    try {
      await state.controller.addComponentInstance(design, {
        name: trimmedName,
        component_vlnv: componentVlnv,
      });
      state.cancel();
    } catch (caught) {
      setError(caught instanceof Error ? caught.message : String(caught));
    } finally {
      setBusy(false);
    }
  };

  return (
    <form className="spec-inline-editor spec-instance-editor" onSubmit={submit}>
      <div>
        <label htmlFor={`${state.editorId}-name`}>Instance name</label>
        <input
          autoComplete="off"
          id={`${state.editorId}-name`}
          onChange={(event) => setName(event.target.value)}
          pattern="[A-Za-z_][A-Za-z0-9_.-]*"
          ref={inputRef}
          value={name}
        />
      </div>
      <div>
        <label htmlFor={`${state.editorId}-component`}>Component</label>
        <select
          id={`${state.editorId}-component`}
          onChange={(event) => setComponentVlnv(event.target.value)}
          value={componentVlnv}
        >
          {options.map((option) => (
            <option key={option.vlnv} value={option.vlnv}>{option.label}</option>
          ))}
        </select>
        <small>Components defined at the specification’s top level are available here.</small>
      </div>
      {error && <p className="spec-edit-error" role="alert">{error}</p>}
      <div className="spec-edit-actions">
        <button disabled={busy} type="submit">{busy ? "Adding…" : "Add instance"}</button>
        <button disabled={busy} onClick={state.cancel} type="button">Cancel</button>
      </div>
    </form>
  );
}

function HardwareMetadataForm({ state }: { state: SectionEditState }) {
  const [displayName] = useState(() => factValue(state.section, "Display name") || state.section.title);
  const [shortDescription] = useState(() => factValue(state.section, "Short description"));
  const [description, setDescription] = useState(() => factValue(state.section, "Description"));
  const [error, setError] = useState("");
  const [busy, setBusy] = useState(false);
  const inputRef = useRef<HTMLTextAreaElement>(null);
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
      <div className="spec-edit-field-wide">
        <label htmlFor={`${state.editorId}-description`}>{state.section.entity_ref?.entity_kind === "component" ? "Component explanation" : state.section.entity_ref?.entity_kind === "design" ? "Design explanation" : "Spec text"}</label>
        <textarea
          id={`${state.editorId}-description`}
          onChange={(event) => setDescription(event.target.value)}
          ref={inputRef}
          rows={4}
          value={description}
        />
        <small>Explain behavior, timing, reset and implementation assumptions. Stored RTL defines implemented behavior; editing this text does not change RTL.</small>
      </div>
      {error && <p className="spec-edit-error" role="alert">{error}</p>}
      <div className="spec-edit-actions spec-edit-field-wide">
        <button disabled={busy} type="submit">{busy ? "Saving…" : "Save to Spec"}</button>
        <button disabled={busy} onClick={state.cancel} type="button">Cancel</button>
      </div>
    </form>
  );
}

function SystemVerilogCodeEditor({
  value,
  onChange,
  diagnostics = [],
}: {
  value: string;
  onChange(value: string): void;
  diagnostics?: EntityContentSection["diagnostics"];
}) {
  const host = useRef<HTMLDivElement>(null);
  const view = useRef<EditorView | null>(null);
  const onChangeRef = useRef(onChange);
  onChangeRef.current = onChange;
  useEffect(() => {
    if (!host.current) return;
    const instance = new EditorView({
      parent: host.current,
      state: EditorState.create({
        doc: value,
        extensions: [
          basicSetup,
          StreamLanguage.define(verilog),
          EditorView.updateListener.of((update) => {
            if (update.docChanged) onChangeRef.current(update.state.doc.toString());
          }),
        ],
      }),
    });
    view.current = instance;
    return () => {
      view.current = null;
      instance.destroy();
    };
  }, []);
  useEffect(() => {
    const instance = view.current;
    if (!instance) return;
    const mapped: Diagnostic[] = diagnostics.map((item) => {
      const lineNumber = Math.min(Math.max(item.line ?? 1, 1), instance.state.doc.lines);
      const line = instance.state.doc.line(lineNumber);
      const from = Math.min(line.to, line.from + Math.max((item.column ?? 1) - 1, 0));
      return {
        from,
        to: Math.min(line.to, from + 1),
        severity: item.blocking ? "error" : "warning",
        message: `${item.code}: ${item.message}`,
      };
    });
    instance.dispatch(setDiagnostics(instance.state, mapped));
  }, [diagnostics]);
  return <div className="spec-sv-code-editor" ref={host} />;
}

function NewSystemVerilogForm({ state }: { state: SectionEditState }) {
  const [draft, setDraft] = useState("");
  const [error, setError] = useState("");
  const [busy, setBusy] = useState(false);
  const submit = async (event: React.FormEvent) => {
    event.preventDefault();
    if (!state.controller || !state.section.entity_ref) return;
    setBusy(true);
    setError("");
    try {
      await state.controller.upsertEntitySection(state.section.entity_ref, draft);
      state.cancel();
    } catch (caught) {
      setError(caught instanceof Error ? caught.message : String(caught));
    } finally {
      setBusy(false);
    }
  };
  return (
    <form className="spec-inline-editor spec-sv-editor-form" onSubmit={submit}>
      <label>SystemVerilog module body</label>
      <SystemVerilogCodeEditor onChange={setDraft} value={draft} />
      <small>Declarations, assignments, procedural blocks, tasks, functions, and assertions are accepted.</small>
      {error && <p className="spec-edit-error" role="alert">{error}</p>}
      <div className="spec-edit-actions">
        <button disabled={busy} type="submit">{busy ? "Validating…" : "Add section"}</button>
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
    const instanceOptions = coordinator.controller?.componentInstanceOptions() ?? [];
    const instanceAvailability = instanceOptions.length
      ? { enabled: true, reason: "" }
      : { enabled: false, reason: "Create a component before adding an instance." };
    const isEntryDesign = section.entity_ref?.entity_kind === "design"
      && section.eyebrow === "Entry design";

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
    const sectionText = factValue(section, "Description");
    const missingLeafRtl = section.entity_ref?.entity_kind === "component"
      && !factValue(section, "Internal design")
      && !(section.content_sections ?? []).some((item) =>
        item.section_type === "sv" && item.payload.content?.trim());

    return (
      <SectionEditContext.Provider value={editState}>
        <section
          className={`spec-section spec-section--level-${section.level}`}
          id={section.section_id}
        >
          <header className="spec-section__header">
            <div>
              <Heading tabIndex={-1}>{section.title}</Heading>
              {section.entity_ref && <span className="spec-section-type">{section.eyebrow || titleCase(section.entity_ref.entity_kind)}</span>}
            </div>
            <SectionOptionsMenu
              instanceAvailability={instanceAvailability}
              onAddInstance={isEntryDesign && coordinator.controller
                ? () => begin("add-component-instance")
                : undefined}
              onAddPort={section.entity_ref?.entity_kind === "component" && coordinator.controller
                ? (family) => begin(`add-${family}-port`)
                : undefined}
              onAddSystemVerilog={coordinator.controller
                && (section.available_section_types ?? []).some((item) => item.section_type === "sv")
                ? () => begin("add-sv")
                : undefined}
              onCreate={coordinator.controller && ["components", "designs"].includes(section.section_id)
                ? (kind) => begin(kind === "component" ? "create-component" : "create-design")
                : undefined}
              onEditDetails={entityIsEditable ? () => begin("metadata") : undefined}
              onRename={entityIsEditable ? () => begin("rename") : undefined}
              portAvailability={portAvailability}
              section={section}
            />
          </header>
          {mode === "rename" && entityIsEditable && <RenameForm
            id={editorId}
            name={section.title}
            onSave={(name) => coordinator.controller!.updateEntityMetadata(section.entity_ref!, {
              display_name: name,
              short_description: factValue(section, "Short description"),
              description: factValue(section, "Description"),
            })}
            finish={cancel}
          />}
          {section.entity_ref && <details><summary>Technical details</summary><pre>{JSON.stringify({ reference: section.entity_ref, identity: section.facts.filter(fact => HIDDEN_IDENTITY_FACTS.has(fact.label)) }, null, 2)}</pre><button type="button" onClick={() => void navigator.clipboard.writeText(JSON.stringify(section.entity_ref))}>Copy reference</button></details>}
          {missingLeafRtl && (
            <p className="spec-implementation-status">RTL implementation missing. Generation produces a compile-safe scaffold; functional behavior is unimplemented.</p>
          )}
          {mode === "create-component" && <HardwareCreationForm kind="component" state={editState} />}
          {mode === "create-design" && <HardwareCreationForm kind="design" state={editState} />}
          {mode === "add-component-instance" && <ComponentInstanceForm state={editState} />}
          {mode === "add-sv" && <NewSystemVerilogForm state={editState} />}
          {mode === "metadata"
            ? <HardwareMetadataForm state={editState} />
            : sectionText && <p className="spec-section-text" style={{ whiteSpace: "pre-wrap" }}>{sectionText}</p>}
          <FactList
            excludeLabels={mode === "metadata"
              ? ["Display name", "Short description", "Description"]
              : []}
            section={section}
          />
          {renderChildren(props.children, buildChild)}
        </section>
      </SectionEditContext.Provider>
    );
  },
);

function SystemVerilogSectionRenderer({ section }: { section: EntityContentSection }) {
  const coordinator = useContext(EditCoordinatorContext);
  const [editing, setEditing] = useState(false);
  const [draft, setDraft] = useState(section.payload.content ?? "");
  const [error, setError] = useState("");
  const [busy, setBusy] = useState(false);
  const editorId = `${section.section_id}-source`;
  const cancel = () => {
    coordinator.finishEditor(editorId);
    setEditing(false);
    setError("");
  };
  const save = async () => {
    if (!coordinator.controller) return;
    setBusy(true);
    setError("");
    try {
      await coordinator.controller.upsertEntitySection(section.parent, draft, section.section_id);
      cancel();
    } catch (caught) {
      setError(caught instanceof Error ? caught.message : String(caught));
    } finally {
      setBusy(false);
    }
  };
  const remove = async () => {
    if (!coordinator.controller || !window.confirm("Delete this SystemVerilog section?")) return;
    setBusy(true);
    setError("");
    try {
      await coordinator.controller.deleteEntitySection(section.parent, section.section_id);
    } catch (caught) {
      setError(caught instanceof Error ? caught.message : String(caught));
    } finally {
      setBusy(false);
    }
  };
  return (
    <section className="spec-entity-section spec-sv-section" aria-labelledby={`${section.section_id}-title`}>
      <header>
        <div>
          <h4 id={`${section.section_id}-title`}>{section.title}</h4>
          <span className={`spec-validation-badge spec-validation-badge--${section.validation_status}`}>
            {section.validation_status}
          </span>
        </div>
        {!editing && coordinator.controller && (
          <div className="spec-edit-actions">
            <button onClick={() => {
              if (coordinator.requestEditor(editorId)) {
                setDraft(section.payload.content ?? "");
                setEditing(true);
              }
            }} type="button">Edit</button>
            <button className="spec-delete-button" disabled={busy} onClick={() => void remove()} type="button">Delete</button>
          </div>
        )}
      </header>
      {editing ? (
        <div className="spec-sv-editor-form">
          <SystemVerilogCodeEditor diagnostics={section.diagnostics} onChange={setDraft} value={draft} />
          <div className="spec-edit-actions">
            <button className="spec-save-button" disabled={busy} onClick={() => void save()} type="button">{busy ? "Validating…" : "Save to Spec"}</button>
            <button disabled={busy} onClick={cancel} type="button">Cancel</button>
          </div>
        </div>
      ) : (
        <pre className="spec-sv-source"><code>{section.payload.content || "// Empty SystemVerilog body"}</code></pre>
      )}
      {section.diagnostics.length > 0 && (
        <ul className="spec-section-diagnostics">
          {section.diagnostics.map((item, index) => (
            <li key={`${item.code}-${index}`}>
              <code>{item.code}</code> {item.message}
              {item.line ? ` (line ${item.line}${item.column ? `:${item.column}` : ""})` : ""}
            </li>
          ))}
        </ul>
      )}
      {error && <p className="spec-edit-error" role="alert">{error}</p>}
    </section>
  );
}

export const ENTITY_SECTION_RENDERERS = {
  sv: SystemVerilogSectionRenderer,
} satisfies Record<PersistedEntitySectionType, React.ComponentType<{ section: EntityContentSection }>>;

const SpecEntitySection = createComponentImplementation(
  SpecEntitySectionApi,
  ({ props }) => {
    const section = props.section as EntityContentSection;
    const Renderer = ENTITY_SECTION_RENDERERS[section.section_type as keyof typeof ENTITY_SECTION_RENDERERS];
    return Renderer ? <Renderer section={section} /> : (
      <div className="spec-render-error" role="alert">Unsupported section type: {section.section_type}</div>
    );
  },
);

function CellValue({ cell }: { cell: DocumentCell }) {
  if (cell.presence === "absent") {
    return <span className="spec-cell--absent" aria-label="Not present in source">—</span>;
  }
  const text = typeof cell.value === "boolean"
    ? (cell.value ? "Yes" : "No")
    : cell.display_text || String(cell.value ?? "");
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
  if (table.kind === "component_ports" || table.kind === "component_port") {
    return <ComponentPortsTable changedPaths={changedPaths} sectionEdit={sectionEdit} table={table} />;
  }
  if (table.kind === "component_ports_empty") {
    return (
      <section className="spec-ports-empty" aria-labelledby={`${table.table_id}-title`}>
        <h4 id={`${table.table_id}-title`}>Ports</h4>
        <p>No wire, transactional, or structured ports have been defined.</p>
      </section>
    );
  }
  return (
    <section className="spec-table-block" aria-labelledby={`${table.table_id}-title`}>
        <div className="spec-table-block__heading">
          <h4 id={`${table.table_id}-title`}>{table.title}</h4>
          <span>{table.rows.length} {table.rows.length === 1 ? "entry" : "entries"}</span>
        </div>
        <div className="spec-table-scroll" role="group" aria-labelledby={`${table.table_id}-title`} tabIndex={0}>
          <table>
            <thead>
              <tr>
                {table.columns.map((column) => (
                  <th key={column.key} scope="col" title={column.schema_path}>
                    {column.label}
                  </th>
                ))}
              </tr>
            </thead>
            <tbody>
              {table.rows.map((row) => (
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

type PortFamily = ComponentPortInput["family"];

function titleCase(value: string): string {
  return value.replaceAll("_", " ").replace(/\b\w/g, (letter) => letter.toUpperCase());
}

function portInputFromRow(row: DocumentTable["rows"][number]): ComponentPortInput {
  const name = rowText(row, "name");
  const display_name = rowText(row, "display_name");
  const description = rowText(row, "description");
  const family = rowText(row, "family") as PortFamily;
  if (family === "transactional") {
    return {
      name,
      family,
      display_name,
      description,
      initiative: rowText(row, "initiative") as Extract<ComponentPortInput, { family: "transactional" }>["initiative"],
      kind: (rowText(row, "transaction_kind") || null) as TransactionalPortKind | null,
      custom_kind: rowText(row, "custom_kind") || null,
      bus_width: rowText(row, "bus_width") || null,
    };
  }
  if (family === "structured") {
    return {
      name,
      family,
      display_name,
      description,
      direction: rowText(row, "direction") as Extract<ComponentPortInput, { family: "structured" }>["direction"],
    };
  }
  return {
    name,
    family: "wire",
    display_name,
    description,
    direction: rowText(row, "direction") as Extract<ComponentPortInput, { family: "wire" }>["direction"],
    range: rowText(row, "range") || null,
  };
}

const PORT_FAMILY_BY_MODE: Partial<Record<SectionEditMode, PortFamily>> = {
  "add-wire-port": "wire",
  "add-transactional-port": "transactional",
  "add-structured-port": "structured",
};

function portDefinition(row: DocumentTable["rows"][number], family: PortFamily): React.ReactNode {
  if (family === "wire") {
    return <>{rowText(row, "direction") || "—"}{rowText(row, "range") && <> · <code>{rowText(row, "range")}</code></>}</>;
  }
  if (family === "transactional") {
    const details = [
      rowText(row, "initiative"),
      titleCase(rowText(row, "transaction_kind")),
      rowText(row, "custom_kind"),
      rowText(row, "bus_width") && `width ${rowText(row, "bus_width")}`,
    ].filter(Boolean);
    return details.join(" · ") || "—";
  }
  return <>{rowText(row, "direction") || "—"} · Packed struct</>;
}

function ComponentPortsTable({
  table,
  changedPaths,
  sectionEdit,
}: {
  table: DocumentTable;
  changedPaths: string[];
  sectionEdit: SectionEditState | null;
}) {
  const addFamily = sectionEdit ? PORT_FAMILY_BY_MODE[sectionEdit.mode] : undefined;
  return (
    <section className="spec-table-block spec-ports-table" aria-labelledby={`${table.table_id}-title`}>
      <div className="spec-table-block__heading">
        <h4 id={`${table.table_id}-title`}>Ports</h4>
        <span>{table.rows.length} {table.rows.length === 1 ? "port" : "ports"}</span>
      </div>
      <div className="spec-table-scroll" role="group" aria-labelledby={`${table.table_id}-title`} tabIndex={0}>
        <table>
          <thead>
            <tr>
              <th scope="col">Name</th>
              <th scope="col">Family</th>
              <th scope="col">Display name</th>
              <th scope="col">Definition</th>
              <th scope="col">Description</th>
              <th scope="col"><span className="spec-visually-hidden">Actions</span></th>
            </tr>
          </thead>
          <tbody>
            {addFamily && sectionEdit && (
              <tr className="spec-port-editor-row">
                <td colSpan={6}><PortEditorCard adding family={addFamily} sectionEdit={sectionEdit} /></td>
              </tr>
            )}
            {table.rows.map((row) => (
              <ComponentPortRow
                changedPaths={changedPaths}
                key={row.row_id}
                row={row}
                sectionEdit={sectionEdit}
                table={table}
              />
            ))}
            {!table.rows.length && !addFamily && (
              <tr><td className="spec-table-empty" colSpan={6}>No wire, transactional, or structured ports have been defined.</td></tr>
            )}
          </tbody>
        </table>
      </div>
    </section>
  );
}

function ComponentPortRow({
  table,
  row,
  changedPaths,
  sectionEdit,
}: {
  table: DocumentTable;
  row: DocumentTable["rows"][number];
  changedPaths: string[];
  sectionEdit: SectionEditState | null;
}) {
  const coordinator = useContext(EditCoordinatorContext);
  const [editing, setEditing] = useState(false);
  const buttonRef = useRef<HTMLButtonElement>(null);
  const name = rowText(row, "name");
  const editorId = `${sectionEdit?.section.section_id ?? table.table_id}-port-${name}`;
  const family = rowText(row, "family") as PortFamily;
  const editingSupported = Boolean(sectionEdit?.controller);
  const canEdit = Boolean(sectionEdit?.portAvailability.enabled && sectionEdit.controller);
  if (editing && sectionEdit) {
    return (
      <tr className="spec-port-editor-row">
        <td colSpan={6}>
          <PortEditorCard
            family={family}
            initial={portInputFromRow(row)}
            onFinished={() => {
              coordinator.finishEditor(editorId);
              setEditing(false);
              window.setTimeout(() => buttonRef.current?.focus(), 0);
            }}
            sectionEdit={sectionEdit}
          />
        </td>
      </tr>
    );
  }
  const displayName = rowText(row, "display_name");
  const description = rowText(row, "description");
  const changed = changedPaths.some((path) => path.includes(table.table_id) || path.includes(row.row_id));
  return (
    <tr className={`spec-port-row${changed ? " spec-proposal-changed" : ""}`}>
      <th scope="row"><strong>{name}</strong></th>
      <td><span className="spec-port-family">{titleCase(family)}</span></td>
      <td>{displayName || "—"}</td>
      <td>{portDefinition(row, family)}</td>
      <td className="spec-port-text">{description || "—"}</td>
      <td className="spec-port-row-actions">
        {canEdit ? (
          <button
            className="spec-port-edit-button"
            onClick={() => {
              if (coordinator.requestEditor(editorId)) setEditing(true);
            }}
            ref={buttonRef}
            type="button"
          >
            Edit
          </button>
        ) : editingSupported ? (
          <small title={sectionEdit?.portAvailability.reason}>
            Read-only
          </small>
        ) : null}
      </td>
    </tr>
  );
}

function PortEditorCard({
  adding = false,
  family,
  initial,
  onFinished,
  sectionEdit,
}: {
  adding?: boolean;
  family: PortFamily;
  initial?: ComponentPortInput;
  onFinished?: () => void;
  sectionEdit: SectionEditState;
}) {
  const [name, setName] = useState(initial?.name ?? "");
  const [displayName, setDisplayName] = useState(initial?.display_name ?? "");
  const [direction, setDirection] = useState<"in" | "out" | "inout">(
    initial && initial.family !== "transactional" ? initial.direction : "in",
  );
  const [range, setRange] = useState(initial?.family === "wire" ? initial.range ?? "" : "");
  const [initiative, setInitiative] = useState<"requires" | "provides" | "both">(
    initial?.family === "transactional" ? initial.initiative : "requires",
  );
  const [transactionKind, setTransactionKind] = useState<TransactionalPortKind | "">(
    initial?.family === "transactional" ? initial.kind ?? "" : "",
  );
  const [customKind, setCustomKind] = useState(
    initial?.family === "transactional" ? initial.custom_kind ?? "" : "",
  );
  const [busWidth, setBusWidth] = useState(
    initial?.family === "transactional" ? initial.bus_width ?? "" : "",
  );
  const [description, setDescription] = useState(initial?.description ?? "");
  const [error, setError] = useState("");
  const [busy, setBusy] = useState(false);
  const formRef = useRef<HTMLFormElement>(null);
  useEffect(() => formRef.current?.querySelector<HTMLInputElement | HTMLSelectElement>("input, select")?.focus(), []);
  const finish = onFinished ?? sectionEdit.cancel;
  const ref = sectionEdit.section.entity_ref;

  const save = async () => {
    if (!sectionEdit.controller || !ref) return;
    if (!name.trim()) {
      setError("Port name is required.");
      return;
    }
    if (!/^[A-Za-z_][A-Za-z0-9_.-]*$/.test(name.trim())) {
      setError("Use a letter or underscore first, followed by letters, numbers, dots, underscores, or hyphens.");
      return;
    }
    if (family === "wire" && (
      range.trim().split(":").length > 2
      || (range.includes(":") && range.split(":").some((part) => !part.trim()))
    )) {
      setError("Range must be empty, one expression, or a left:right expression pair.");
      return;
    }
    if (family === "transactional" && transactionKind === "custom" && !customKind.trim()) {
      setError("Custom transactional ports require a custom kind name.");
      return;
    }
    setBusy(true);
    setError("");
    const common = { name: name.trim(), display_name: displayName, description };
    const value: ComponentPortInput = family === "wire"
      ? { ...common, family, direction, range: range.trim() || null }
      : family === "transactional"
        ? {
          ...common,
          family,
          initiative,
          kind: transactionKind || null,
          custom_kind: transactionKind === "custom" ? customKind.trim() : null,
          bus_width: busWidth.trim() || null,
        }
        : { ...common, family, direction };
    try {
      if (adding) await sectionEdit.controller.addComponentPort(ref, value);
      else {
        const { name: _immutableName, ...update } = value;
        await sectionEdit.controller.updateComponentPort(ref, value.name, update);
      }
      finish();
    } catch (caught) {
      setError(caught instanceof Error ? caught.message : String(caught));
    } finally {
      setBusy(false);
    }
  };

  const idPrefix = `${sectionEdit.section.section_id}-${adding ? `new-${family}` : name}`;

  return (
    <form
      className="spec-port-editor"
      onSubmit={(event) => { event.preventDefault(); void save(); }}
      ref={formRef}
    >
      <header>
        <div>
          <span className="spec-port-kind">{titleCase(family)} port</span>
          <h4>{adding ? `Add ${family} port` : name}</h4>
        </div>
      </header>
      <div className="spec-port-editor-grid">
        {adding && (
          <div>
            <label htmlFor={`${idPrefix}-name`}>Port name</label>
            <input
              autoComplete="off"
              id={`${idPrefix}-name`}
              onChange={(event) => setName(event.target.value)}
              pattern="[A-Za-z_][A-Za-z0-9_.-]*"
              value={name}
            />
          </div>
        )}
        <div>
          <label htmlFor={`${idPrefix}-display-name`}>Display name</label>
          <input id={`${idPrefix}-display-name`} onChange={(event) => setDisplayName(event.target.value)} value={displayName} />
        </div>
        {family !== "transactional" && (
          <div>
            <label htmlFor={`${idPrefix}-direction`}>Direction</label>
            <select id={`${idPrefix}-direction`} onChange={(event) => setDirection(event.target.value as typeof direction)} value={direction}>
              <option value="in">in</option>
              <option value="out">out</option>
              <option value="inout">inout</option>
            </select>
          </div>
        )}
        {family === "wire" && (
          <div className="spec-edit-field-wide">
            <label htmlFor={`${idPrefix}-range`}>Range</label>
            <input id={`${idPrefix}-range`} onChange={(event) => setRange(event.target.value)} placeholder="DATA_WIDTH-1:0" value={range} />
            <small>Optional. Use left:right, or one expression for identical bounds.</small>
          </div>
        )}
        {family === "transactional" && (
          <>
            <div>
              <label htmlFor={`${idPrefix}-initiative`}>Initiative</label>
              <select id={`${idPrefix}-initiative`} onChange={(event) => setInitiative(event.target.value as typeof initiative)} value={initiative}>
                <option value="requires">requires</option>
                <option value="provides">provides</option>
                <option value="both">both</option>
              </select>
            </div>
            <div>
              <label htmlFor={`${idPrefix}-kind`}>Kind</label>
              <select id={`${idPrefix}-kind`} onChange={(event) => setTransactionKind(event.target.value as typeof transactionKind)} value={transactionKind}>
                <option value="">Unspecified</option>
                <option value="tlm_port">TLM port</option>
                <option value="tlm_socket">TLM socket</option>
                <option value="simple_socket">Simple socket</option>
                <option value="multi_socket">Multi socket</option>
                <option value="custom">Custom</option>
              </select>
            </div>
            {transactionKind === "custom" && (
              <div>
                <label htmlFor={`${idPrefix}-custom-kind`}>Custom kind name</label>
                <input id={`${idPrefix}-custom-kind`} onChange={(event) => setCustomKind(event.target.value)} value={customKind} />
              </div>
            )}
            <div>
              <label htmlFor={`${idPrefix}-bus-width`}>Bus width</label>
              <input id={`${idPrefix}-bus-width`} onChange={(event) => setBusWidth(event.target.value)} value={busWidth} />
            </div>
          </>
        )}
        {family === "structured" && (
          <div>
            <span className="spec-port-editor-label">Structure</span>
            <strong>Packed struct</strong>
          </div>
        )}
        <div className="spec-edit-field-wide">
          <label htmlFor={`${idPrefix}-description`}>Description</label>
          <textarea id={`${idPrefix}-description`} onChange={(event) => setDescription(event.target.value)} rows={3} value={description} />
        </div>
      </div>
      {error && <p className="spec-edit-error" role="alert">{error}</p>}
      <div className="spec-port-actions">
          <button disabled={busy} type="submit">{busy ? "Saving…" : "Save to Spec"}</button>
          <button disabled={busy} onClick={finish} type="button">Cancel</button>
      </div>
    </form>
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

function RenameControl({ id, name, onSave }: { id: string; name: string; onSave: (name: string) => Promise<void> }) {
  const coordinator = useContext(EditCoordinatorContext);
  const [editing, setEditing] = useState(false);
  const finish = () => { coordinator.finishEditor(id); setEditing(false); };
  if (!editing) return <button type="button" className="spec-text-edit" onClick={() => {
    if (coordinator.requestEditor(id)) setEditing(true);
  }}>Rename</button>;
  return <RenameForm id={id} name={name} onSave={onSave} finish={finish} />;
}

function RenameForm({ id, name, onSave, finish }: {
  id: string;
  name: string;
  onSave: (name: string) => Promise<void>;
  finish: () => void;
}) {
  const [draft, setDraft] = useState(name);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState("");
  return <form className="spec-inline-editor" onSubmit={async event => {
    event.preventDefault(); setBusy(true); setError("");
    try { await onSave(draft); finish(); }
    catch (caught) { setError(caught instanceof Error ? caught.message : String(caught)); }
    finally { setBusy(false); }
  }}>
    <label htmlFor={id}>Name</label><input autoFocus id={id} maxLength={200} required value={draft} onChange={event => setDraft(event.target.value)} />
    {error && <p role="alert">{error}</p>}
    <button disabled={busy} type="submit">Save to Spec</button><button disabled={busy} type="button" onClick={finish}>Cancel</button>
  </form>;
}

function referenceLabel(block: NarrativeBlockData, ref: EntityRef) {
  return block.entity_labels?.[`${ref.entity_kind}:${ref.entity_id}`] || {
    name: `${ref.entity_kind.replaceAll("_", " ")}`, anchor: `${ref.entity_kind.replaceAll("_", "-")}-${ref.entity_id}`.replaceAll("_", "-"),
  };
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
        ? `#${referenceLabel(block, inline.entity_ref).anchor}`
        : safeHref(inline.href);
      return href
        ? <a href={href} key={key}>{inline.text}</a>
        : <span key={key}>{inline.text}</span>;
    }
    return <Fragment key={key}>{inline.text}</Fragment>;
  });
}

function NarrativeNode({ block }: { block: NarrativeBlockData }): React.ReactNode {
  const coordinator = useContext(EditCoordinatorContext);
  if (block.type === "section") {
    return (
      <section className="spec-narrative__section" id={`narrative-block-${block.block_id}`.replaceAll("_", "-")}>
        <h4>{block.text}</h4>
        {coordinator.controller?.renameNarrativeSection && <RenameControl id={`${block.block_id}-rename`} name={block.text} onSave={name => coordinator.controller!.renameNarrativeSection!(block.block_id, name)} />}
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
          <Heading tabIndex={-1}>{section.title}</Heading>
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
                href={`#${referenceLabel(block, ref).anchor}`}
                key={`${ref.entity_kind}-${ref.entity_id}`}
              >
                {referenceLabel(block, ref).name}
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
    if (block.renderer_id === "design.topology") {
      const circuitRef = block.entity_refs[0];
      return <DesignTopologyLiveView
        block={block}
        documentId={props.documentId}
        onOpenCircuit={circuitRef && (circuitRef.entity_kind === "design" || circuitRef.entity_kind === "component")
          ? () => dispatchOpenCircuit(circuitRef)
          : undefined}
      />;
    }
    return (
      <div className="spec-callout spec-callout--live">
        <span className="spec-live-dot" aria-hidden="true" />
        <div>
          <NarrativeExploreButton block={block} documentId={props.documentId} />
          <strong>{block.text || "Live design view"}</strong>
          <details><summary>Technical details</summary><p>Renderer: <code>{block.renderer_id || "default"}</code></p></details>
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
  [SpecDocument, SpecSection, SpecTable, SpecEntitySection, NarrativeBlock, EntityLink, LiveView],
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
  onEditingChange,
}: {
  batch: A2UIDocumentBatch;
  editController?: SpecDocumentEditController;
  onEditingChange?: (editing: boolean) => void;
}) {
  const processor = useMemo(() => createDocumentMessageProcessor(batch), [batch]);
  const surface = processor.model.surfacesMap.get(batch.surface_id);
  if (!surface) {
    return <div className="spec-render-error" role="alert">The A2UI document surface was not created.</div>;
  }
  return (
    <EditCoordinatorProvider
      controller={editController}
      onEditingChange={onEditingChange}
      resetKey={batch.source_revision_hash}
    >
      <A2uiSurface surface={surface} />
    </EditCoordinatorProvider>
  );
}
