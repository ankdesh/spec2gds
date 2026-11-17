import { useEffect, useMemo, useRef, useState } from "react";

import type { DocumentSnapshot, FilesystemDirectoryListing } from "@spec2gds/document-core";
import { captureSpecTextEditTarget, type SpecTextEditTarget } from "@spec2gds/document-a2ui-react";
import { publicFilenameStem } from "@spec2gds/circuit-core";
import { PreferencesDialog } from "./PreferencesDialog";
import type { SpecEditorThemeId } from "./preferences";

export type EditorView = "document" | "activity" | "diagnostics";

type MenuId = "file" | "edit" | "circuit" | "help";
type DialogId = "new" | "copy" | "open" | "getting-started" | "shortcuts" | "about" | "preferences" | null;

interface EditorMenuBarProps {
  dialogError?: string;
  activityCount: number;
  diagnosticCount: number;
  launchingAssistant: boolean;
  launchingCircuit: boolean;
  loading: boolean;
  path: string;
  snapshot: DocumentSnapshot | null;
  themeId: SpecEditorThemeId;
  view: EditorView;
  onCopySuggestion?: () => Promise<{ path: string; title: string }>;
  onCopy?: (path: string, title: string) => Promise<boolean>;
  onCreate: (path: string, title: string) => Promise<boolean>;
  onBrowseDirectories: (path?: string) => Promise<FilesystemDirectoryListing>;
  onCreateDirectory: (parent: string, name: string) => Promise<FilesystemDirectoryListing>;
  onError: (message: string) => void;
  onOpen: (path: string) => Promise<boolean>;
  onClose: () => Promise<void>;
  onOpenAssistant: () => Promise<void>;
  onOpenCircuit: (entityKind: "component" | "design", entityId: string) => Promise<void>;
  onSelectTheme: (themeId: SpecEditorThemeId) => void;
  onToggleTheme: () => void;
  onViewChange: (view: EditorView) => void;
}

const MENU_ORDER: MenuId[] = ["file", "edit", "circuit", "help"];

function displayEntityName(vlnv?: string): string {
  return vlnv?.split(":")[2] || "source";
}

function displayPathName(path: string): string {
  return path.split(/[\\/]/).filter(Boolean).at(-1) || "No specification open";
}

function packageDirectory(path: string): string | undefined {
  const trimmed = path.trim();
  const separatorIndex = Math.max(trimmed.lastIndexOf("/"), trimmed.lastIndexOf("\\"));
  const filename = trimmed.slice(separatorIndex + 1);
  if (!filename.toLowerCase().endsWith(".spec")) return trimmed || undefined;
  if (separatorIndex < 0) return undefined;
  if (separatorIndex === 0) return trimmed[0];
  const directory = trimmed.slice(0, separatorIndex);
  return /^[a-z]:$/i.test(directory) ? `${directory}\\` : directory;
}

function portablePackageFilename(path: string, title: string): string {
  const existing = path.trim().split(/[\\/]/).at(-1) ?? "";
  if (existing.toLowerCase().endsWith(".spec")) return existing;
  return `${publicFilenameStem(title.replace(/\.spec$/i, ""), "specification")}.spec`;
}

function packagePathInDirectory(
  directory: string,
  currentPath: string,
  title: string,
  separator: string,
): string {
  const suffix = directory.endsWith("/") || directory.endsWith("\\") ? "" : separator;
  return `${directory}${suffix}${portablePackageFilename(currentPath, title)}`;
}

function nextMenu(current: MenuId, delta: number): MenuId {
  const index = MENU_ORDER.indexOf(current);
  return MENU_ORDER[(index + delta + MENU_ORDER.length) % MENU_ORDER.length];
}

function enabledMenuItems(container: HTMLElement | null): HTMLButtonElement[] {
  return Array.from(container?.querySelectorAll<HTMLButtonElement>("[role='menuitem']:not(:disabled)") ?? []);
}

function focusMenuItem(container: HTMLElement | null, position: "first" | "last"): void {
  const items = enabledMenuItems(container);
  const item = position === "first" ? items[0] : items.at(-1);
  if (item) item.focus();
  else container?.focus();
}

function TopMenu({
  children,
  id,
  label,
  openMenu,
  setOpenMenu,
}: {
  children: React.ReactNode;
  id: MenuId;
  label: string;
  openMenu: MenuId | null;
  setOpenMenu: (menu: MenuId | null) => void;
}) {
  const panelRef = useRef<HTMLDivElement>(null);
  const open = openMenu === id;

  useEffect(() => {
    if (open) focusMenuItem(panelRef.current, "first");
  }, [open]);

  const moveToMenu = (delta: number, keepOpen: boolean) => {
    const target = nextMenu(id, delta);
    setOpenMenu(keepOpen ? target : null);
    if (!keepOpen) {
      requestAnimationFrame(() => {
        document.getElementById(`editor-${target}-menu-trigger`)?.focus();
      });
    }
  };

  const onPanelKeyDown = (event: React.KeyboardEvent<HTMLDivElement>) => {
    if (event.key === "Escape") {
      event.preventDefault();
      setOpenMenu(null);
      document.getElementById(`editor-${id}-menu-trigger`)?.focus();
      return;
    }
    if (event.key === "ArrowRight" || event.key === "ArrowLeft") {
      event.preventDefault();
      moveToMenu(event.key === "ArrowRight" ? 1 : -1, true);
      return;
    }
    if (!["ArrowDown", "ArrowUp", "Home", "End"].includes(event.key)) return;
    const items = enabledMenuItems(panelRef.current);
    if (!items.length) return;
    event.preventDefault();
    if (event.key === "Home") return items[0]?.focus();
    if (event.key === "End") return items.at(-1)?.focus();
    const current = items.indexOf(document.activeElement as HTMLButtonElement);
    const index = event.key === "ArrowDown"
      ? (current + 1) % items.length
      : (current <= 0 ? items.length : current) - 1;
    items[index]?.focus();
  };

  return (
    <div className="editor-menu" role="none">
      <button
        aria-controls={`editor-${id}-menu`}
        aria-expanded={open}
        aria-haspopup="menu"
        id={`editor-${id}-menu-trigger`}
        onClick={() => setOpenMenu(open ? null : id)}
        onKeyDown={(event) => {
          if (["Enter", " ", "ArrowDown"].includes(event.key)) {
            event.preventDefault();
            setOpenMenu(id);
          } else if (event.key === "ArrowRight" || event.key === "ArrowLeft") {
            event.preventDefault();
            moveToMenu(event.key === "ArrowRight" ? 1 : -1, false);
          }
        }}
        role="menuitem"
        type="button"
      >
        {label}
      </button>
      {open && (
        <div
          aria-label={label}
          className={`editor-menu__panel editor-menu__panel--${id}`}
          id={`editor-${id}-menu`}
          onKeyDown={onPanelKeyDown}
          ref={panelRef}
          role="menu"
          tabIndex={-1}
        >
          {children}
        </div>
      )}
    </div>
  );
}

function MenuAction({
  children,
  disabled = false,
  onActivate,
  shortcut,
  status,
}: {
  children: React.ReactNode;
  disabled?: boolean;
  onActivate?: () => void;
  shortcut?: string;
  status?: string;
}) {
  return (
    <button disabled={disabled} onClick={onActivate} role="menuitem" type="button">
      <span>{children}</span>
      {(shortcut || status) && <small>{status || shortcut}</small>}
    </button>
  );
}

function Modal({
  children,
  onClose,
  restoreFocusId,
  title,
  wide = false,
  dismissDisabled = false,
}: {
  children: React.ReactNode;
  onClose: () => void;
  restoreFocusId: string;
  title: string;
  wide?: boolean;
  dismissDisabled?: boolean;
}) {
  const dialogRef = useRef<HTMLElement>(null);
  const onCloseRef = useRef(onClose);
  onCloseRef.current = onClose;

  useEffect(() => {
    const previousFocus = document.activeElement as HTMLElement | null;
    const onKeyDown = (event: KeyboardEvent) => {
      if (event.key === "Escape") {
        event.preventDefault();
        onCloseRef.current();
        return;
      }
      if (event.key !== "Tab") return;
      const focusable = Array.from(dialogRef.current?.querySelectorAll<HTMLElement>(
        "button:not(:disabled), input:not(:disabled), textarea:not(:disabled), select:not(:disabled), summary, [href], [tabindex]:not([tabindex='-1'])",
      ) ?? []).filter(element => element.getClientRects().length > 0);
      if (!focusable.length) return;
      const first = focusable[0];
      const last = focusable.at(-1);
      if (event.shiftKey && document.activeElement === first) {
        event.preventDefault();
        last?.focus();
      } else if (!event.shiftKey && document.activeElement === last) {
        event.preventDefault();
        first?.focus();
      }
    };
    document.addEventListener("keydown", onKeyDown);
    requestAnimationFrame(() => {
      const preferred = dialogRef.current?.querySelector<HTMLElement>("[data-dialog-autofocus], [autofocus]");
      (preferred ?? dialogRef.current?.querySelector<HTMLElement>("button, input"))?.focus();
    });
    return () => {
      document.removeEventListener("keydown", onKeyDown);
      if (previousFocus?.isConnected && previousFocus !== document.body && previousFocus.getClientRects().length) previousFocus.focus();
      else {
        const trigger = document.getElementById(restoreFocusId);
        (trigger?.getClientRects().length ? trigger : document.getElementById("editor-mobile-menu-trigger"))?.focus();
      }
    };
  }, [restoreFocusId]);

  return (
    <div className="editor-dialog-backdrop" onMouseDown={onClose} role="presentation">
      <section
        aria-labelledby="editor-dialog-title"
        aria-modal="true"
        className={`editor-dialog${wide ? " editor-dialog--wide" : ""}`}
        onMouseDown={(event) => event.stopPropagation()}
        ref={dialogRef}
        role="dialog"
      >
        <header>
          <h2 id="editor-dialog-title">{title}</h2>
          <button aria-label="Close" className="icon-button" disabled={dismissDisabled} onClick={onClose} type="button">×</button>
        </header>
        {children}
      </section>
    </div>
  );
}

export function PathDialog({
  error,
  initialPath,
  initialTitle = "",
  loading,
  mode,
  onBrowseDirectories,
  onClearError,
  onClose,
  onCreateDirectory,
  onSubmit,
  onSuggest,
  restoreFocusId = "editor-file-menu-trigger",
}: {
  onSuggest?: () => Promise<{ path: string; title: string }>;
  error?: string;
  initialPath: string;
  initialTitle?: string;
  loading: boolean;
  mode: "new" | "open" | "copy";
  onBrowseDirectories: (path?: string) => Promise<FilesystemDirectoryListing>;
  onClearError?: () => void;
  onClose: () => void;
  onCreateDirectory: (parent: string, name: string) => Promise<FilesystemDirectoryListing>;
  onSubmit: (path: string, title: string) => Promise<boolean>;
  restoreFocusId?: string;
}) {
  const [title, setTitle] = useState(initialTitle);
  const [directory, setDirectory] = useState(mode === "copy" ? packageDirectory(initialPath) ?? "" : "");
  const [suggestedFilename, setSuggestedFilename] = useState(mode === "copy" ? initialPath : "");
  const [manualPath, setManualPath] = useState<string | null>(null);
  const [selectedFile, setSelectedFile] = useState("");
  const [locationView, setLocationView] = useState(false);
  const [listing, setListing] = useState<FilesystemDirectoryListing | null>(null);
  const [root, setRoot] = useState("");
  const [separator, setSeparator] = useState("/");
  const [browserLoading, setBrowserLoading] = useState(true);
  const [browserError, setBrowserError] = useState("");
  const [suggestionError, setSuggestionError] = useState("");
  const [localError, setLocalError] = useState("");
  const [filter, setFilter] = useState("");
  const [creatingFolder, setCreatingFolder] = useState(false);
  const [folderName, setFolderName] = useState("");
  const [submitting, setSubmitting] = useState(false);
  const mounted = useRef(false);
  const browseSequence = useRef(0);
  const suggestionSequence = useRef(0);
  const lastBrowse = useRef<string | undefined>(undefined);
  const titleEdited = useRef(false);
  const destinationEdited = useRef(false);
  const submitPending = useRef(false);
  const callbacks = useRef({ onBrowseDirectories, onCreateDirectory, onSuggest });
  callbacks.current = { onBrowseDirectories, onCreateDirectory, onSuggest };
  const busy = loading || submitting;
  const browserVisible = mode === "open" || locationView;
  const generatedPath = directory ? packagePathInDirectory(directory, suggestedFilename, title, separator) : "";
  const value = manualPath ?? (mode === "open" ? selectedFile : generatedPath);
  const message = localError || browserError || suggestionError || error;
  const action = mode === "new" ? "Create Spec" : mode === "copy" ? "Create Copy" : "Open Spec";

  const clearError = () => { setLocalError(""); onClearError?.(); };
  const browse = async (path?: string) => {
    const sequence = ++browseSequence.current;
    lastBrowse.current = path;
    setBrowserLoading(true);
    setBrowserError("");
    setSelectedFile("");
    setFilter("");
    setCreatingFolder(false);
    try {
      const result = await callbacks.current.onBrowseDirectories(path);
      if (!mounted.current || sequence !== browseSequence.current) return;
      setListing(result);
      setRoot(result.home);
      setSeparator(result.separator);
      setDirectory(current => current || result.home);
    } catch (caught) {
      if (mounted.current && sequence === browseSequence.current) {
        setBrowserError(caught instanceof Error ? caught.message : String(caught));
      }
    } finally {
      if (mounted.current && sequence === browseSequence.current) setBrowserLoading(false);
    }
  };
  const suggest = async () => {
    const sequence = ++suggestionSequence.current;
    setSuggestionError("");
    try {
      const suggestion = await callbacks.current.onSuggest?.();
      if (!mounted.current || sequence !== suggestionSequence.current || !suggestion) return;
      if (!titleEdited.current) {
        setTitle(suggestion.title);
        setSuggestedFilename(suggestion.path);
      }
      if (!destinationEdited.current) setDirectory(packageDirectory(suggestion.path) ?? "");
    } catch {
      if (mounted.current && sequence === suggestionSequence.current) {
        setSuggestionError("Could not suggest a copy name. Enter a name or retry.");
      }
    }
  };
  useEffect(() => {
    mounted.current = true;
    void browse();
    if (mode === "copy") void suggest();
    return () => {
      mounted.current = false;
      ++browseSequence.current;
      ++suggestionSequence.current;
    };
  }, []);

  const submit = async (path = value) => {
    if (busy || submitPending.current || !path.trim() || (mode !== "open" && !title.trim())) return;
    submitPending.current = true;
    ++suggestionSequence.current;
    setSubmitting(true);
    clearError();
    try {
      if (await onSubmit(path.trim(), title.trim()) && mounted.current) onClose();
    } catch (caught) {
      if (mounted.current) setLocalError(caught instanceof Error ? caught.message : String(caught));
    } finally {
      submitPending.current = false;
      if (mounted.current) setSubmitting(false);
    }
  };
  const close = () => { if (!busy && !submitPending.current) onClose(); };
  const commitLocation = () => {
    if (!listing || browserLoading || browserError) return;
    destinationEdited.current = true;
    setDirectory(listing.path);
    if (manualPath !== null) {
      setManualPath(packagePathInDirectory(listing.path, manualPath, title, listing.separator));
    }
    setLocationView(false);
    clearError();
  };
  const createFolder = async () => {
    if (!listing || !folderName.trim() || browserLoading || busy) return;
    const sequence = ++browseSequence.current;
    setBrowserLoading(true);
    clearError();
    try {
      const result = await callbacks.current.onCreateDirectory(listing.path, folderName.trim());
      if (!mounted.current || sequence !== browseSequence.current) return;
      setListing(result);
      lastBrowse.current = result.path;
      setFolderName("");
      setCreatingFolder(false);
      setFilter("");
    } catch (caught) {
      if (mounted.current && sequence === browseSequence.current) {
        setLocalError(caught instanceof Error ? caught.message : String(caught));
      }
    } finally {
      if (mounted.current && sequence === browseSequence.current) setBrowserLoading(false);
    }
  };
  const relativeLocation = (path: string) => {
    if (!root || !path) return path || "Loading location…";
    if (path === root) return "Spec root";
    const prefix = root.endsWith(separator) ? root : root + separator;
    return path.startsWith(prefix) ? `Spec root / ${path.slice(prefix.length).split(separator).join(" / ")}` : path;
  };
  const rootPrefix = root.endsWith(separator) ? root : root + separator;
  const parts = listing?.path.startsWith(rootPrefix) ? listing.path.slice(rootPrefix.length).split(separator).filter(Boolean) : [];
  const breadcrumbs = [{ name: "Spec root", path: root }, ...parts.map((name, index) => ({
    name, path: rootPrefix + parts.slice(0, index + 1).join(separator),
  }))];
  const matches = (name: string) => name.toLocaleLowerCase().includes(filter.trim().toLocaleLowerCase());
  const folders = listing?.directories.filter(item => matches(item.name)) ?? [];
  const files = mode === "open" ? listing?.specifications?.filter(item => matches(item.name)) ?? [] : [];

  return (
    <Modal onClose={close} restoreFocusId={restoreFocusId} dismissDisabled={busy}
      title={locationView ? "Choose location" : mode === "new" ? "New Spec" : action} wide={browserVisible}>
      <form onSubmit={event => {
        event.preventDefault();
        if (locationView) commitLocation();
        else void submit();
      }}>
        {!browserVisible && <>
          <label htmlFor="specification-name">Spec name</label>
          <input autoFocus data-dialog-autofocus id="specification-name" maxLength={200} disabled={busy}
            onChange={event => {
              titleEdited.current = true;
              setTitle(event.target.value);
              setSuggestedFilename("");
              setSuggestionError("");
              clearError();
            }} placeholder="My hardware Spec" value={title} />
          <div className="spec-location">
            <div><span>Save location</span><strong title={packageDirectory(value) || directory}>{relativeLocation(packageDirectory(value) || directory)}</strong></div>
            <button className="secondary" type="button" disabled={!root || busy} onClick={() => {
              clearError();
              setLocationView(true);
              void browse(packageDirectory(value) || directory);
            }}>Change location</button>
          </div>
          <p className="editor-dialog__hint spec-filename">File: <code>{title.trim() || manualPath !== null ? displayPathName(value || portablePackageFilename(suggestedFilename, title)) : "Enter a name to set the filename"}</code></p>
          {browserLoading && <p className="editor-dialog__hint" role="status">Loading location…</p>}
        </>}
        {browserVisible && <section aria-label="Server directory browser" className="directory-browser">
          <nav aria-label="Folder location" className="directory-browser__breadcrumbs">
            {breadcrumbs.map((crumb, index) => <span key={crumb.path || "root"}>
              {index > 0 && <span aria-hidden="true"> / </span>}
              <button type="button" disabled={!root || busy || listing?.path === crumb.path}
                aria-current={listing?.path === crumb.path ? "location" : undefined}
                onClick={() => { clearError(); if (mode === "open") setManualPath(null); void browse(crumb.path); }}>{crumb.name}</button>
            </span>)}
          </nav>
          <label className="visually-hidden" htmlFor="specification-filter">{mode === "open" ? "Filter folders and Specs" : "Filter folders"}</label>
          <input autoFocus data-dialog-autofocus id="specification-filter" type="search" disabled={busy}
            placeholder={mode === "open" ? "Filter folders and Specs…" : "Filter folders…"} value={filter}
            onChange={event => {
              setFilter(event.target.value);
              setSelectedFile("");
              if (mode === "open") setManualPath(null);
            }} />
          {mode !== "open" && <div className="directory-browser__toolbar">
            <button type="button" disabled={busy || browserLoading || !listing || creatingFolder || !!browserError}
              onClick={() => { setCreatingFolder(true); setFolderName(""); clearError(); }}>＋ New folder</button>
          </div>}
          {creatingFolder && <div className="directory-browser__new-folder">
            <input aria-label="New folder name" autoFocus disabled={busy || browserLoading} value={folderName} placeholder="Folder name"
              onChange={event => { setFolderName(event.target.value); clearError(); }}
              onKeyDown={event => {
                if (event.key === "Escape") { event.preventDefault(); event.stopPropagation(); setCreatingFolder(false); }
                if (event.key === "Enter") { event.preventDefault(); void createFolder(); }
              }} />
            <button disabled={busy || browserLoading || !folderName.trim()} type="button" onClick={() => void createFolder()}>Add folder</button>
            <button className="secondary" type="button" disabled={busy || browserLoading} onClick={() => setCreatingFolder(false)}>Cancel folder</button>
          </div>}
          {browserLoading && <p role="status" className="directory-browser__status">Loading folders…</p>}
          {!browserLoading && !browserError && listing && <div role="list" aria-label={mode === "open" ? "Folders and Specs" : "Folders"} className="directory-browser__folders">
            {folders.map(folder => <div role="listitem" key={folder.path}>
              <button type="button" disabled={busy} title={folder.path} onClick={() => {
                clearError();
                if (mode === "open") setManualPath(null);
                void browse(folder.path);
              }}><span aria-hidden="true">📁</span> {folder.name}<span aria-hidden="true" className="directory-browser__enter">›</span></button>
            </div>)}
            {files.map(file => <div role="listitem" key={file.path}>
              <button type="button" disabled={busy} title={file.path} aria-pressed={selectedFile === file.path && manualPath === null}
                className={selectedFile === file.path && manualPath === null ? "selected" : ""}
                onClick={() => { setSelectedFile(file.path); setManualPath(null); clearError(); }}
                onDoubleClick={() => void submit(file.path)}><span aria-hidden="true">📄</span> {file.name}</button>
            </div>)}
            {!folders.length && !files.length && <p>{filter.trim() ? "No matching names" : mode === "open" ? "No folders or Specs" : "No subfolders"}</p>}
          </div>}
          {mode === "open" && selectedFile && manualPath === null && <p className="editor-dialog__hint">Selected: {displayPathName(selectedFile)}</p>}
        </section>}
        {!locationView && <details className="spec-path-options">
          <summary>More options</summary>
          <label htmlFor="specification-path">File path</label>
          <input id="specification-path" disabled={busy} value={value} placeholder="Path to a .spec file"
            onChange={event => { destinationEdited.current = true; setManualPath(event.target.value); clearError(); }} />
          <p className="editor-dialog__hint">Files are stored on the server and must stay within Spec root{root ? <>: <code>{root}</code></> : "."}</p>
          {manualPath !== null && <button className="secondary" type="button" disabled={busy} onClick={() => {
            setManualPath(null); setSuggestedFilename(""); clearError();
          }}>Reset to automatic</button>}
        </details>}
        {message && <p className="spec-edit-error" role="alert">{message}</p>}
        {browserError && <button className="secondary" type="button" disabled={busy || browserLoading} onClick={() => void browse(lastBrowse.current)}>Retry loading folders</button>}
        {suggestionError && <button className="secondary" type="button" disabled={busy} onClick={() => void suggest()}>Retry suggestion</button>}
        <div className="editor-dialog__actions">
          <button className="secondary" disabled={busy} type="button" onClick={() => {
            if (locationView) { ++browseSequence.current; setBrowserLoading(false); setBrowserError(""); setLocationView(false); clearError(); }
            else close();
          }}>{locationView ? "Back" : "Cancel"}</button>
          <button disabled={busy || !root || browserLoading || (locationView ? !listing || !!browserError : !value.trim() || (mode !== "open" && !title.trim()))} type="submit">
            {busy ? mode === "open" ? "Opening…" : "Creating…" : locationView ? "Use this folder" : action}
          </button>
        </div>
      </form>
    </Modal>
  );
}

function HelpDialog({ dialog, onClose }: { dialog: Exclude<DialogId, "new" | "copy" | "open">; onClose: () => void }) {
  if (!dialog) return null;
  if (dialog === "getting-started") {
    return (
      <Modal onClose={onClose} restoreFocusId="editor-help-menu-trigger" title="Getting started">
        <div className="editor-dialog__copy">
          <p>Use <strong>File → New Spec</strong>, enter a name, and select <strong>Create Spec</strong>. The file saves in Spec root. Use <strong>Change location</strong> to choose another folder, or <strong>File → Open Spec</strong> to browse saved Specs.</p>
          <p>Edit the specification name from the document cover. Use group <strong>Options</strong> menus to create components and entry designs, and entity menus to edit their introductory text.</p>
          <p>Entry designs can add named instances of available top-level components. Leaf Components support wire-port editing. Existing transaction and structured ports are read-only; wire ranges use <code>left:right</code> syntax.</p>
          <p>Use Save to Spec to validate and save each draft. Options lists compatible Activities; Export target details (JSON) exports the saved target and its dependencies.</p>
          <p>Use the <strong>Diagnostics</strong> toolbar button for verification reports and source findings. Use <strong>Activity</strong> for job progress, downloads, and change reviews. Checks and jobs keep the panel closed until you open it, or select <strong>View details</strong> in a notification.</p>
          <p>Add ports individually with <strong>Add port</strong> or <strong>Save and add another</strong>. Leave Range blank for a scalar, or enter explicit bounds such as <code>15:0</code>. Correct an invalid Range in the retained draft before saving.</p>
        </div>
      </Modal>
    );
  }
  if (dialog === "shortcuts") {
    return (
      <Modal onClose={onClose} restoreFocusId="editor-help-menu-trigger" title="Keyboard shortcuts">
        <dl className="shortcut-list">
          <div><dt>New specification</dt><dd><kbd>Ctrl/⌘</kbd> + <kbd>N</kbd></dd></div>
          <div><dt>Open specification</dt><dd><kbd>Ctrl/⌘</kbd> + <kbd>O</kbd></dd></div>
          <div><dt>Move between menus</dt><dd><kbd>←</kbd> <kbd>→</kbd></dd></div>
          <div><dt>Move within a menu</dt><dd><kbd>↑</kbd> <kbd>↓</kbd></dd></div>
          <div><dt>Close menu or dialog</dt><dd><kbd>Esc</kbd></dd></div>
          <div><dt>Edit text in a field</dt><dd>Native <kbd>Ctrl/⌘</kbd> + <kbd>X</kbd>/<kbd>V</kbd></dd></div>
        </dl>
      </Modal>
    );
  }
  return (
    <Modal onClose={onClose} restoreFocusId="editor-help-menu-trigger" title="About spec2hw">
      <div className="editor-dialog__copy">
        <p><strong>spec2hw Spec Editor</strong></p>
        <p>A deterministic editor for <code>spec2gds-v1</code> hardware specification packages.</p>
      </div>
    </Modal>
  );
}

export default function EditorMenuBar({
  onClose,
  dialogError,
  activityCount,
  diagnosticCount,
  launchingAssistant,
  launchingCircuit,
  loading,
  path,
  snapshot,
  themeId,
  view,
  onCreate,
  onCopy,
  onCopySuggestion,
  onBrowseDirectories,
  onCreateDirectory,
  onError,
  onOpen,
  onOpenAssistant,
  onOpenCircuit,
  onSelectTheme,
  onToggleTheme,
  onViewChange,
}: EditorMenuBarProps) {
  const [openMenu, setOpenMenu] = useState<MenuId | null>(null);
  const [dialog, setDialog] = useState<DialogId>(null);
  const [mobileMenuOpen, setMobileMenuOpen] = useState(false);
  const [canCopy, setCanCopy] = useState(false);
  const [canCut, setCanCut] = useState(false);
  const [canPaste, setCanPaste] = useState(false);
  const clipboardPending = useRef(false);
  const textTarget = useRef<SpecTextEditTarget | null>(null);
  const rootRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    const header = rootRef.current;
    const shell = header?.closest<HTMLElement>(".app-shell");
    if (!header || !shell) return;
    const measure = () => shell.style.setProperty("--spec-toolbar-height", `${header.getBoundingClientRect().height}px`);
    measure();
    const observer = new ResizeObserver(measure);
    observer.observe(header);
    return () => observer.disconnect();
  }, []);

  const entryIds = useMemo(
    () => new Map(snapshot?.entry_designs.map((entry, index) => [entry.ref.entity_id, index]) ?? []),
    [snapshot],
  );
  const designs = useMemo(() => (snapshot?.designs ?? [])
    .map((design, index) => ({ design, index }))
    .sort((left, right) => {
      const leftEntry = entryIds.get(left.design.ref.entity_id);
      const rightEntry = entryIds.get(right.design.ref.entity_id);
      if (leftEntry !== undefined && rightEntry !== undefined) return leftEntry - rightEntry;
      if (leftEntry !== undefined) return -1;
      if (rightEntry !== undefined) return 1;
      return left.index - right.index;
    })
    .map(({ design }) => design).filter(design => !snapshot?.component_compositions.some(item => item.internal_design.entity_id === design.ref.entity_id)), [entryIds, snapshot]);
  const components = snapshot?.components ?? [];

  const openPathDialog = (mode: "new" | "open") => {
    onError("");
    setOpenMenu(null);
    setMobileMenuOpen(false);
    setDialog(mode);
  };

  useEffect(() => {
    const onPointerDown = (event: PointerEvent) => {
      if (!rootRef.current?.contains(event.target as Node)) {
        setOpenMenu(null);
        setMobileMenuOpen(false);
      }
    };
    document.addEventListener("pointerdown", onPointerDown);
    return () => document.removeEventListener("pointerdown", onPointerDown);
  }, []);

  useEffect(() => {
    const onShortcut = (event: KeyboardEvent) => {
      if (!(event.ctrlKey || event.metaKey) || event.altKey) return;
      const key = event.key.toLowerCase();
      if (key !== "n" && key !== "o") return;
      event.preventDefault();
      if (dialog !== null || document.querySelector("[aria-modal='true']")) return;
      openPathDialog(key === "n" ? "new" : "open");
    };
    document.addEventListener("keydown", onShortcut);
    return () => document.removeEventListener("keydown", onShortcut);
  });

  useEffect(() => {
    const update = () => {
      const active = document.activeElement;
      const captured = captureSpecTextEditTarget(active);
      if (captured || !rootRef.current?.contains(active)) textTarget.current = captured;
      const target = textTarget.current;
      const editable = Boolean(target?.isCurrent());
      const selection = window.getSelection();
      const paper = document.querySelector(".spec-paper");
      const paperSelection = Boolean(selection && !selection.isCollapsed && selection.toString()
        && Boolean(paper?.getClientRects().length) && paper?.contains(selection.anchorNode) && paper.contains(selection.focusNode));
      setCanCopy(Boolean(editable && target?.selectedText) || paperSelection);
      setCanCut(Boolean(editable && target?.selectedText));
      setCanPaste(editable);
    };
    const events = ["focusin", "selectionchange", "keyup", "pointerup", "input"];
    events.forEach(event => document.addEventListener(event, update));
    return () => events.forEach(event => document.removeEventListener(event, update));
  }, []);

  const editClipboard = async (operation: "cut" | "paste") => {
    const target = textTarget.current;
    if (clipboardPending.current || !target?.isCurrent()) return;
    clipboardPending.current = true;
    try {
      if (operation === "cut") {
        await navigator.clipboard.writeText(target.selectedText);
        target.replaceSelection("", "cut");
      } else {
        const text = await navigator.clipboard.readText();
        if (text) target.replaceSelection(text, "paste");
        else target.focus();
      }
    } catch (caught) {
      target.focus();
      onError(`Could not ${operation} text: ${caught instanceof Error ? caught.message : String(caught)}. You can use the keyboard shortcut in the field.`);
    } finally { clipboardPending.current = false; }
  };

  const activate = (callback: () => void) => () => {
    setOpenMenu(null);
    setMobileMenuOpen(false);
    callback();
  };

  const copySelection = async () => {
    const selection = textTarget.current?.isCurrent() ? textTarget.current.selectedText : window.getSelection()?.toString() ?? "";
    try {
      await navigator.clipboard.writeText(selection);
    } catch (caught) {
      onError(caught instanceof Error ? caught.message : "Could not copy the selected text.");
    }
  };

  const selectAll = () => {
    if (textTarget.current?.isCurrent()) { textTarget.current.selectAll(); return; }
    const paper = document.querySelector(".spec-paper");
    const selection = window.getSelection();
    if (!paper || !selection) return;
    const range = document.createRange();
    range.selectNodeContents(paper);
    selection.removeAllRanges();
    selection.addRange(range);
  };

  const openApiReference = () => {
    const opened = window.open("/docs", "_blank", "noopener,noreferrer");
    if (opened) opened.opener = null;
  };

  return (
    <>
      <header className="app-header" ref={rootRef} onKeyDown={(event) => {
        if (event.key === "Escape" && !openMenu && mobileMenuOpen) {
          setMobileMenuOpen(false);
          document.getElementById("editor-mobile-menu-trigger")?.focus();
        }
      }}>
        <div className="app-header__primary">
          <a className="brand" aria-label="Spec Editor" href="#" onClick={(event) => { event.preventDefault(); onViewChange("document"); }}>
            <span className="brand__mark" aria-hidden="true">S</span>
            <span><strong>spec2hw</strong><small>Spec Editor</small></span>
          </a>
          <button
            className="editor-mobile-menu-trigger"
            id="editor-mobile-menu-trigger"
            aria-controls="editor-application-menu"
            aria-expanded={mobileMenuOpen}
            type="button"
            onClick={() => {
              setMobileMenuOpen(!mobileMenuOpen);
              setOpenMenu(null);
              if (!mobileMenuOpen) requestAnimationFrame(() => document.getElementById("editor-file-menu-trigger")?.focus());
            }}
          >Menu</button>
          <nav id="editor-application-menu" aria-label="Application menu" className={`editor-menubar${mobileMenuOpen ? " editor-menubar--open" : ""}`} role="menubar">
            <TopMenu id="file" label="File" openMenu={openMenu} setOpenMenu={setOpenMenu}>
              <MenuAction onActivate={activate(() => openPathDialog("new"))} shortcut="Ctrl/⌘ N">New Spec…</MenuAction>
              <MenuAction onActivate={activate(() => openPathDialog("open"))} shortcut="Ctrl/⌘ O">Open Spec…</MenuAction>
              {snapshot && onCopy && <MenuAction onActivate={activate(() => { onError(""); setDialog("copy"); })}>Create Copy…</MenuAction>}
              <MenuAction disabled={!snapshot || loading} onActivate={activate(() => { void onClose(); })}>Close Spec</MenuAction>
              <MenuAction
                disabled={!path || loading}
                onActivate={activate(() => { void onOpen(path); })}
              >
                Refresh From Disk
              </MenuAction>
            </TopMenu>
            <TopMenu id="edit" label="Edit" openMenu={openMenu} setOpenMenu={setOpenMenu}>
              <MenuAction disabled={!canCut} onActivate={activate(() => { void editClipboard("cut"); })}>Cut</MenuAction>
              <MenuAction disabled={!canCopy} onActivate={activate(() => { void copySelection(); })}>Copy</MenuAction>
              <MenuAction disabled={!canPaste} onActivate={activate(() => { void editClipboard("paste"); })}>Paste</MenuAction>
              <MenuAction disabled={!snapshot} onActivate={activate(selectAll)}>Select All</MenuAction>
              <div className="editor-menu__separator" role="separator" />
              <MenuAction onActivate={activate(() => setDialog("preferences"))} shortcut="Ctrl/⌘ ,">Preferences…</MenuAction>
            </TopMenu>
            <TopMenu id="circuit" label="Circuit Designer" openMenu={openMenu} setOpenMenu={setOpenMenu}>
              {designs.length > 0 && <div className="editor-menu__group" role="presentation">Top-level Designs</div>}
              {designs.map((design) => (
                <MenuAction
                  disabled={launchingCircuit}
                  key={`design-${design.ref.entity_id}`}
                  onActivate={activate(() => { void onOpenCircuit("design", design.ref.entity_id); })}
                  status={entryIds.has(design.ref.entity_id) ? "Entry · Edit Design" : "Edit Design"}
                >
                  {design.display_name || displayEntityName(design.vlnv)}
                </MenuAction>
              ))}
              {components.length > 0 && <div className="editor-menu__group" role="presentation">Components</div>}
              {components.map((component) => (
                <MenuAction
                  disabled={launchingCircuit}
                  key={`component-${component.ref.entity_id}`}
                  status={snapshot?.component_compositions.some(item => item.component.entity_id === component.ref.entity_id)
                    ? "Open assigned Design" : "Read-only preview"}
                  onActivate={activate(() => { void onOpenCircuit("component", component.ref.entity_id); })}
                >
                  {component.display_name || displayEntityName(component.vlnv)}
                </MenuAction>
              ))}
              {!designs.length && !components.length && (
                <MenuAction disabled>No circuit sources</MenuAction>
              )}
            </TopMenu>
            <TopMenu id="help" label="Help" openMenu={openMenu} setOpenMenu={setOpenMenu}>
              <MenuAction onActivate={activate(() => setDialog("getting-started"))}>Getting Started</MenuAction>
              <MenuAction onActivate={activate(() => setDialog("shortcuts"))}>Keyboard Shortcuts</MenuAction>
              <MenuAction onActivate={activate(openApiReference)}>Developer API Reference</MenuAction>
              <div className="editor-menu__separator" role="separator" />
              <MenuAction onActivate={activate(() => setDialog("about"))}>About spec2hw</MenuAction>
            </TopMenu>
          </nav>
        </div>

        <nav className="app-nav" aria-label="Editor panels">
          {(["diagnostics", "activity"] as EditorView[]).map((item) => (
            <button
              className={view === item ? "active" : ""}
              id={`editor-${item}-trigger`}
              aria-expanded={view === item}
              aria-controls={view === item ? "editor-utility-panel" : undefined}
              key={item}
              onClick={() => onViewChange(item)}
              type="button"
            >
              {item[0].toUpperCase() + item.slice(1)}
              {item === "activity" && activityCount > 0 && <span>{activityCount}</span>}
              {item === "diagnostics" && diagnosticCount > 0 && <span>{diagnosticCount}</span>}
            </button>
          ))}
        </nav>

        <div className="app-header__utilities">
          <button
            aria-label={`Switch theme (currently ${themeId === "obsidian" ? "Dark" : "Light"})`}
            className="theme-quick-toggle"
            onClick={onToggleTheme}
            title={`Switch to ${themeId === "obsidian" ? "Clean (Light)" : "Obsidian (Dark)"}`}
            type="button"
          >
            <span aria-hidden="true">{themeId === "obsidian" ? "☀️" : "🌙"}</span>
          </button>
          <button
            className="assistant-launch"
            disabled={launchingAssistant}
            onClick={() => { void onOpenAssistant(); }}
            type="button"
          >
            {launchingAssistant ? "Opening…" : "AI Assistant"} <span aria-hidden="true">↗</span>
          </button>
          <div className="active-document" title={path || "No server-local package is open"}>
            <span className={snapshot ? "active-document__status" : "active-document__status active-document__status--idle"} />
            <span><small>{snapshot ? displayPathName(path) : "File → New or Open"}</small><strong>{snapshot?.narrative.title || displayPathName(path)}</strong></span>
          </div>
        </div>
      </header>

      {dialog === "copy" && onCopy && <PathDialog error={dialogError} onClearError={() => onError("")} initialTitle={`${snapshot?.narrative.title || "Spec"} copy`} initialPath={path.replace(/\.spec$/i, "-copy.spec")} loading={loading} mode="copy" onSuggest={onCopySuggestion} onBrowseDirectories={onBrowseDirectories} onClose={() => { onError(""); setDialog(null); }} onCreateDirectory={onCreateDirectory} onSubmit={onCopy} />}
      {dialog === "new" && (
        <PathDialog
          error={dialogError}
          onClearError={() => onError("")}
          initialPath=""
          loading={loading}
          mode="new"
          onBrowseDirectories={onBrowseDirectories}
          onClose={() => { onError(""); setDialog(null); }}
          onCreateDirectory={onCreateDirectory}
          onSubmit={onCreate}
        />
      )}
      {dialog === "open" && (
        <PathDialog
          error={dialogError}
          onClearError={() => onError("")}
          initialPath={path}
          loading={loading}
          mode="open"
          onBrowseDirectories={onBrowseDirectories}
          onClose={() => { onError(""); setDialog(null); }}
          onCreateDirectory={onCreateDirectory}
          onSubmit={(nextPath) => onOpen(nextPath)}
        />
      )}
      {dialog === "preferences" && (
        <PreferencesDialog
          currentThemeId={themeId}
          onClose={() => setDialog(null)}
          onThemeChange={onSelectTheme}
          restoreFocusId="editor-edit-menu-trigger"
        />
      )}
      {dialog && !["new", "copy", "open", "preferences"].includes(dialog) && (
        <HelpDialog dialog={dialog as Exclude<DialogId, "new" | "copy" | "open" | "preferences">} onClose={() => setDialog(null)} />
      )}
    </>
  );
}
