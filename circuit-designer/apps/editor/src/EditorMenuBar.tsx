import { useEffect, useMemo, useRef, useState } from "react";

import type { DocumentSnapshot, FilesystemDirectoryListing } from "@spec2gds/document-core";

export type EditorView = "document" | "activity" | "diagnostics";

type MenuId = "file" | "edit" | "circuit" | "help";
type DialogId = "new" | "open" | "getting-started" | "shortcuts" | "about" | null;

interface EditorMenuBarProps {
  activityCount: number;
  diagnosticCount: number;
  launchingAssistant: boolean;
  launchingCircuit: boolean;
  loading: boolean;
  path: string;
  snapshot: DocumentSnapshot | null;
  view: EditorView;
  onCreate: (path: string, title: string) => Promise<boolean>;
  onBrowseDirectories: (path?: string) => Promise<FilesystemDirectoryListing>;
  onCreateDirectory: (parent: string, name: string) => Promise<FilesystemDirectoryListing>;
  onError: (message: string) => void;
  onOpen: (path: string) => Promise<boolean>;
  onOpenAssistant: () => Promise<void>;
  onOpenCircuit: (entityKind: "component" | "design", entityId: string) => Promise<void>;
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
  let safeTitle = title.trim()
    .replace(/[<>:"/\\|?*\u0000-\u001f]/g, "-")
    .replace(/[. ]+$/g, "") || "specification";
  if (/^(con|prn|aux|nul|com[1-9]|lpt[1-9])(?:\..*)?$/i.test(safeTitle)) {
    safeTitle = `_${safeTitle}`;
  }
  return `${safeTitle}.spec`;
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
}: {
  children: React.ReactNode;
  onClose: () => void;
  restoreFocusId: string;
  title: string;
  wide?: boolean;
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
        "button:not(:disabled), input:not(:disabled), [href], [tabindex]:not([tabindex='-1'])",
      ) ?? []);
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
      const preferred = dialogRef.current?.querySelector<HTMLElement>("[autofocus]");
      (preferred ?? dialogRef.current?.querySelector<HTMLElement>("button, input"))?.focus();
    });
    return () => {
      document.removeEventListener("keydown", onKeyDown);
      if (previousFocus?.isConnected && previousFocus !== document.body) previousFocus.focus();
      else document.getElementById(restoreFocusId)?.focus();
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
          <button aria-label="Close" className="icon-button" onClick={onClose} type="button">×</button>
        </header>
        {children}
      </section>
    </div>
  );
}

function PathDialog({
  initialPath,
  loading,
  mode,
  onBrowseDirectories,
  onClose,
  onCreateDirectory,
  onSubmit,
}: {
  initialPath: string;
  loading: boolean;
  mode: "new" | "open";
  onBrowseDirectories: (path?: string) => Promise<FilesystemDirectoryListing>;
  onClose: () => void;
  onCreateDirectory: (parent: string, name: string) => Promise<FilesystemDirectoryListing>;
  onSubmit: (path: string, title: string) => Promise<boolean>;
}) {
  const [value, setValue] = useState(initialPath);
  const [title, setTitle] = useState("");
  const [browserOpen, setBrowserOpen] = useState(false);
  const [browserLoading, setBrowserLoading] = useState(false);
  const [browserError, setBrowserError] = useState("");
  const [listing, setListing] = useState<FilesystemDirectoryListing | null>(null);
  const [selectedDirectory, setSelectedDirectory] = useState<string | null>(null);
  const [creatingFolder, setCreatingFolder] = useState(false);
  const [folderName, setFolderName] = useState("");
  const action = mode === "new" ? "Create" : "Open";
  const browse = async (path?: string) => {
    setBrowserLoading(true);
    setBrowserError("");
    setSelectedDirectory(null);
    setCreatingFolder(false);
    try {
      setListing(await onBrowseDirectories(path));
    } catch (caught) {
      setBrowserError(caught instanceof Error ? caught.message : String(caught));
    } finally {
      setBrowserLoading(false);
    }
  };
  const createFolder = async () => {
    const name = folderName.trim();
    if (!listing || !name) return;
    setBrowserLoading(true);
    setBrowserError("");
    try {
      setListing(await onCreateDirectory(listing.path, name));
      setFolderName("");
      setCreatingFolder(false);
      setSelectedDirectory(null);
    } catch (caught) {
      setBrowserError(caught instanceof Error ? caught.message : String(caught));
    } finally {
      setBrowserLoading(false);
    }
  };
  return (
    <Modal
      onClose={onClose}
      restoreFocusId="editor-file-menu-trigger"
      title={`${mode === "new" ? "New" : "Open"} specification`}
      wide={browserOpen}
    >
      <form
        onSubmit={async (event) => {
          event.preventDefault();
          const nextPath = value.trim();
          const nextTitle = title.trim();
          if (nextPath && (mode === "open" || nextTitle) && await onSubmit(nextPath, nextTitle)) onClose();
        }}
      >
        {mode === "new" && (
          <>
            <label htmlFor="specification-name">Specification name</label>
            <input
              autoFocus
              id="specification-name"
              maxLength={200}
              onChange={(event) => setTitle(event.target.value)}
              placeholder="My hardware specification"
              value={title}
            />
          </>
        )}
        <label htmlFor="specification-path">Server-local package path</label>
        <div className="editor-dialog__path-field">
          <input
            autoFocus={mode === "open"}
            id="specification-path"
            onChange={(event) => setValue(event.target.value)}
            placeholder="/path/to/design.spec"
            value={value}
          />
          <button
            className="secondary"
            onClick={() => {
              if (browserOpen) {
                setBrowserOpen(false);
                return;
              }
              setBrowserOpen(true);
              void browse(packageDirectory(value));
            }}
            type="button"
          >
            {browserOpen ? "Hide" : "Browse…"}
          </button>
        </div>
        <p className="editor-dialog__hint">
          Enter a <code>.spec</code> path visible to the server running spec2gds.
          {mode === "new" && " Generated output folders will be created beside this package."}
        </p>
        {browserOpen && (
          <section aria-label="Server directory browser" className="directory-browser">
            <header>
              <strong>{mode === "new" ? "Choose a folder on the server" : "Choose a specification on the server"}</strong>
              {listing && <code title={listing.path}>{listing.path}</code>}
            </header>
            <div className="directory-browser__toolbar">
              <button
                disabled={browserLoading || !listing?.parent}
                onClick={() => { if (listing?.parent) void browse(listing.parent); }}
                type="button"
              >
                Up
              </button>
              <button
                disabled={browserLoading || !listing || listing.path === listing.home}
                onClick={() => { if (listing) void browse(listing.home); }}
                type="button"
              >
                Home
              </button>
              {listing?.roots.map((root) => (
                <button
                  disabled={browserLoading || listing.path === root}
                  key={root}
                  onClick={() => void browse(root)}
                  type="button"
                >
                  {root}
                </button>
              ))}
              <span className="directory-browser__toolbar-spacer" />
              <button
                disabled={browserLoading || !listing || creatingFolder}
                onClick={() => {
                  setCreatingFolder(true);
                  setFolderName("");
                  setSelectedDirectory(null);
                }}
                type="button"
              >
                ＋ New folder
              </button>
            </div>
            {creatingFolder && (
              <div className="directory-browser__new-folder">
                <input
                  aria-label="New folder name"
                  autoFocus
                  onChange={(event) => setFolderName(event.target.value)}
                  onKeyDown={(event) => {
                    if (event.key === "Escape") {
                      event.preventDefault();
                      event.stopPropagation();
                      setCreatingFolder(false);
                    } else if (event.key === "Enter") {
                      event.preventDefault();
                      void createFolder();
                    }
                  }}
                  placeholder="Folder name"
                  value={folderName}
                />
                <button disabled={browserLoading || !folderName.trim()} onClick={() => void createFolder()} type="button">
                  Create
                </button>
                <button className="secondary" onClick={() => setCreatingFolder(false)} type="button">
                  Cancel
                </button>
              </div>
            )}
            {browserError && <p className="directory-browser__error" role="alert">{browserError}</p>}
            {browserLoading && <p className="directory-browser__status" role="status">Loading folders…</p>}
            {!browserLoading && listing && (
              <div
                aria-label={mode === "new" ? "Folders" : "Folders and specifications"}
                className="directory-browser__folders"
                role="list"
              >
                {listing.directories
                  .filter((directory) => mode === "new" || !directory.name.toLowerCase().endsWith(".spec"))
                  .map((directory) => (
                    <div key={directory.path} role="listitem">
                      <button
                        aria-pressed={selectedDirectory === directory.path}
                        className={selectedDirectory === directory.path ? "selected" : ""}
                        onClick={() => setSelectedDirectory(directory.path)}
                        onDoubleClick={() => void browse(directory.path)}
                        title={directory.path}
                        type="button"
                      >
                        <span aria-hidden="true">📁</span> {directory.name}
                      </button>
                    </div>
                  ))}
                {mode === "open" && (listing.specifications ?? []).map((specification) => (
                  <div key={specification.path} role="listitem">
                    <button
                      aria-pressed={selectedDirectory === specification.path}
                      className={selectedDirectory === specification.path ? "selected" : ""}
                      onClick={() => setSelectedDirectory(specification.path)}
                      onDoubleClick={() => {
                        setValue(specification.path);
                        setBrowserOpen(false);
                      }}
                      title={specification.path}
                      type="button"
                    >
                      <span aria-hidden="true">📄</span> {specification.name}
                    </button>
                  </div>
                ))}
                {!listing.directories.length && (mode === "new" || !(listing.specifications ?? []).length) && (
                  <p>{mode === "new" ? "No subfolders" : "No folders or specifications"}</p>
                )}
              </div>
            )}
            <div className="directory-browser__actions">
              <button
                disabled={browserLoading || !listing || (mode === "open" && !selectedDirectory?.toLowerCase().endsWith(".spec"))}
                onClick={() => {
                  if (!listing) return;
                  setValue(mode === "new"
                    ? packagePathInDirectory(
                      selectedDirectory ?? listing.path,
                      value,
                      title,
                      listing.separator,
                    )
                    : selectedDirectory ?? value);
                  setBrowserOpen(false);
                }}
                type="button"
              >
                {mode === "new" ? "Select folder" : "Select specification"}
              </button>
            </div>
          </section>
        )}
        <div className="editor-dialog__actions">
          <button className="secondary" onClick={onClose} type="button">Cancel</button>
          <button disabled={!value.trim() || (mode === "new" && !title.trim()) || loading} type="submit">
            {loading ? `${action}ing…` : action}
          </button>
        </div>
      </form>
    </Modal>
  );
}

function HelpDialog({ dialog, onClose }: { dialog: Exclude<DialogId, "new" | "open">; onClose: () => void }) {
  if (!dialog) return null;
  if (dialog === "getting-started") {
    return (
      <Modal onClose={onClose} restoreFocusId="editor-help-menu-trigger" title="Getting started">
        <div className="editor-dialog__copy">
          <p>Use <strong>File → New Specification</strong> to name and create a server-local package, or <strong>File → Open Specification</strong> to load one.</p>
          <p>Edit the specification name from the document cover. Use group <strong>Options</strong> menus to create components and entry designs, and entity menus to edit their introductory text.</p>
          <p>Entry designs can add named instances of available top-level components. Leaf components keep wire, transactional, and packed structured ports together in one editable table; wire ranges use <code>left:right</code> syntax.</p>
          <p>Saved edits are validated and persisted automatically after an explicit Save.</p>
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
    <Modal onClose={onClose} restoreFocusId="editor-help-menu-trigger" title="About spec2gds">
      <div className="editor-dialog__copy">
        <p><strong>spec2gds Specification Editor</strong></p>
        <p>A deterministic editor for <code>spec2gds-v1</code> hardware specification packages.</p>
      </div>
    </Modal>
  );
}

export default function EditorMenuBar({
  activityCount,
  diagnosticCount,
  launchingAssistant,
  launchingCircuit,
  loading,
  path,
  snapshot,
  view,
  onCreate,
  onBrowseDirectories,
  onCreateDirectory,
  onError,
  onOpen,
  onOpenAssistant,
  onOpenCircuit,
  onViewChange,
}: EditorMenuBarProps) {
  const [openMenu, setOpenMenu] = useState<MenuId | null>(null);
  const [dialog, setDialog] = useState<DialogId>(null);
  const [canCopy, setCanCopy] = useState(false);
  const rootRef = useRef<HTMLDivElement>(null);

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
    .map(({ design }) => design), [entryIds, snapshot]);
  const components = snapshot?.components ?? [];

  const openPathDialog = (mode: "new" | "open") => {
    setOpenMenu(null);
    setDialog(mode);
  };

  useEffect(() => {
    const onPointerDown = (event: PointerEvent) => {
      if (!rootRef.current?.contains(event.target as Node)) setOpenMenu(null);
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
      openPathDialog(key === "n" ? "new" : "open");
    };
    document.addEventListener("keydown", onShortcut);
    return () => document.removeEventListener("keydown", onShortcut);
  });

  useEffect(() => {
    const onSelectionChange = () => {
      const selection = window.getSelection();
      const paper = document.querySelector(".spec-paper");
      setCanCopy(Boolean(
        selection
        && !selection.isCollapsed
        && selection.toString()
        && paper
        && selection.anchorNode
        && selection.focusNode
        && paper.contains(selection.anchorNode)
        && paper.contains(selection.focusNode),
      ));
    };
    document.addEventListener("selectionchange", onSelectionChange);
    return () => document.removeEventListener("selectionchange", onSelectionChange);
  }, []);

  const activate = (callback: () => void) => () => {
    setOpenMenu(null);
    callback();
  };

  const copySelection = async () => {
    const selection = window.getSelection()?.toString() ?? "";
    try {
      await navigator.clipboard.writeText(selection);
    } catch (caught) {
      onError(caught instanceof Error ? caught.message : "Could not copy the selected text.");
    }
  };

  const selectAll = () => {
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
      <header className="app-header" ref={rootRef}>
        <div className="app-header__primary">
          <a className="brand" href="#" onClick={(event) => { event.preventDefault(); onViewChange("document"); }}>
            <span className="brand__mark" aria-hidden="true">S</span>
            <span><strong>spec2gds</strong><small>Specification document</small></span>
          </a>
          <nav aria-label="Application menu" className="editor-menubar" role="menubar">
            <TopMenu id="file" label="File" openMenu={openMenu} setOpenMenu={setOpenMenu}>
              <MenuAction onActivate={activate(() => openPathDialog("new"))} shortcut="Ctrl/⌘ N">New Specification…</MenuAction>
              <MenuAction onActivate={activate(() => openPathDialog("open"))} shortcut="Ctrl/⌘ O">Open Specification…</MenuAction>
              <MenuAction
                disabled={!path || loading}
                onActivate={activate(() => { void onOpen(path); })}
              >
                Refresh From Disk
              </MenuAction>
              <div className="editor-menu__separator" role="separator" />
              <MenuAction disabled status="Automatic">Save</MenuAction>
            </TopMenu>
            <TopMenu id="edit" label="Edit" openMenu={openMenu} setOpenMenu={setOpenMenu}>
              <MenuAction disabled status="Coming later">Undo</MenuAction>
              <MenuAction disabled status="Coming later">Redo</MenuAction>
              <div className="editor-menu__separator" role="separator" />
              <MenuAction disabled status="Use keyboard in fields">Cut</MenuAction>
              <MenuAction disabled={!canCopy} onActivate={activate(() => { void copySelection(); })}>Copy</MenuAction>
              <MenuAction disabled status="Use keyboard in fields">Paste</MenuAction>
              <MenuAction disabled={!snapshot} onActivate={activate(selectAll)}>Select All</MenuAction>
              <div className="editor-menu__separator" role="separator" />
              <MenuAction disabled status="Coming soon">Find</MenuAction>
            </TopMenu>
            <TopMenu id="circuit" label="Circuit" openMenu={openMenu} setOpenMenu={setOpenMenu}>
              {designs.length > 0 && <div className="editor-menu__group" role="presentation">Designs</div>}
              {designs.map((design) => (
                <MenuAction
                  disabled={launchingCircuit}
                  key={`design-${design.ref.entity_id}`}
                  onActivate={activate(() => { void onOpenCircuit("design", design.ref.entity_id); })}
                  status={entryIds.has(design.ref.entity_id) ? "Entry" : undefined}
                >
                  {displayEntityName(design.vlnv)}
                </MenuAction>
              ))}
              {components.length > 0 && <div className="editor-menu__group" role="presentation">Components</div>}
              {components.map((component) => (
                <MenuAction
                  disabled={launchingCircuit}
                  key={`component-${component.ref.entity_id}`}
                  onActivate={activate(() => { void onOpenCircuit("component", component.ref.entity_id); })}
                >
                  {displayEntityName(component.vlnv)}
                </MenuAction>
              ))}
              {!designs.length && !components.length && (
                <MenuAction disabled>No circuit sources</MenuAction>
              )}
            </TopMenu>
            <TopMenu id="help" label="Help" openMenu={openMenu} setOpenMenu={setOpenMenu}>
              <MenuAction onActivate={activate(() => setDialog("getting-started"))}>Getting Started</MenuAction>
              <MenuAction onActivate={activate(() => setDialog("shortcuts"))}>Keyboard Shortcuts</MenuAction>
              <MenuAction onActivate={activate(openApiReference)}>API Reference</MenuAction>
              <div className="editor-menu__separator" role="separator" />
              <MenuAction onActivate={activate(() => setDialog("about"))}>About spec2gds</MenuAction>
            </TopMenu>
          </nav>
        </div>

        <nav className="app-nav" aria-label="Editor views">
          {(["document", "activity", "diagnostics"] as EditorView[]).map((item) => (
            <button
              className={view === item ? "active" : ""}
              key={item}
              onClick={() => onViewChange(item)}
              type="button"
            >
              {item[0].toUpperCase() + item.slice(1)}
              {item === "activity" && <span>{activityCount}</span>}
              {item === "diagnostics" && <span>{diagnosticCount}</span>}
            </button>
          ))}
        </nav>

        <div className="app-header__utilities">
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

      {dialog === "new" && (
        <PathDialog
          initialPath=""
          loading={loading}
          mode="new"
          onBrowseDirectories={onBrowseDirectories}
          onClose={() => setDialog(null)}
          onCreateDirectory={onCreateDirectory}
          onSubmit={onCreate}
        />
      )}
      {dialog === "open" && (
        <PathDialog
          initialPath={path}
          loading={loading}
          mode="open"
          onBrowseDirectories={onBrowseDirectories}
          onClose={() => setDialog(null)}
          onCreateDirectory={onCreateDirectory}
          onSubmit={(nextPath) => onOpen(nextPath)}
        />
      )}
      {dialog && !["new", "open"].includes(dialog) && (
        <HelpDialog dialog={dialog as Exclude<DialogId, "new" | "open">} onClose={() => setDialog(null)} />
      )}
    </>
  );
}
