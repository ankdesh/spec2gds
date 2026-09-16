import React, { useEffect, useMemo, useRef, useState } from "react";
import { createRoot } from "react-dom/client";
import "./styles.css";

type Domain = "spec" | "circuit";
interface Session { sessionId: string; domain: Domain; documentId: string; scope: "document" | "entity"; entityKind: string | null; entityId: string | null; title: string; ownerUrl: string; archived: boolean }
interface EventItem { type: string; seq: number; text?: string; callId?: string; name?: string; arguments?: unknown; message?: unknown; data?: unknown }
interface Review { proposalId: string; domain: Domain; state: string; artifact: Record<string, unknown>; preview: unknown; diagnostics: unknown; ownerResult: unknown }
interface Capabilities { assistant: { ready: boolean; modelConfigured: boolean }; owners: { spec: Array<{ available: boolean; url: string }>; circuit: Array<{ available: boolean; url: string }> } }

class ApiError extends Error {
  constructor(message: string, readonly status: number, readonly detail: unknown) { super(message); }
}

async function api<T>(path: string, value?: unknown): Promise<T> {
  const response = await fetch(`/api${path}`, {
    method: value === undefined ? "GET" : "POST",
    headers: value === undefined ? {} : { "Content-Type": "application/json" },
    body: value === undefined ? undefined : JSON.stringify(value),
  });
  const body = await response.json();
  if (!response.ok) throw new ApiError(body.error ?? `Request failed (${response.status})`, response.status, body.detail);
  return body as T;
}

function App() {
  const [sessions, setSessions] = useState<Session[]>([]);
  const [selected, setSelected] = useState<string | null>(() => new URLSearchParams(location.search).get("session"));
  const [events, setEvents] = useState<EventItem[]>([]);
  const [reviews, setReviews] = useState<Review[]>([]);
  const [running, setRunning] = useState(false);
  const [liveText, setLiveText] = useState("");
  const [notice, setNotice] = useState("");
  const [showArchived, setShowArchived] = useState(false);
  const [capabilities, setCapabilities] = useState<Capabilities | null>(null);
  const stream = useRef<EventSource | null>(null);

  const refreshSessions = () => api<{ sessions: Session[] }>("/sessions?archived=true").then(value => setSessions(value.sessions));
  useEffect(() => {
    void Promise.all([refreshSessions(), api<Capabilities>("/capabilities").then(setCapabilities)]).catch(error => setNotice(error.message));
  }, []);
  useEffect(() => {
    stream.current?.close(); setEvents([]); setReviews([]); setLiveText(""); setRunning(false);
    if (!selected) return;
    history.replaceState(null, "", `/?session=${encodeURIComponent(selected)}`);
    let offset = 0;
    let active = true;
    let reconnect: ReturnType<typeof setTimeout> | undefined;
    const consume = (packet: any) => {
      if (packet.kind === "snapshot") {
        setEvents(previous => mergeEvents(previous, packet.events as EventItem[]));
        offset = Math.max(offset, Number(packet.nextOffset ?? offset));
        setRunning(Boolean(packet.running)); setReviews(packet.reviews ?? []);
      }
      if (packet.kind === "event") {
        const item = packet.event as EventItem;
        offset = Math.max(offset, item.seq + 1);
        setEvents(previous => mergeEvents(previous, [item]));
        if (item.type === "assistant/message") setLiveText("");
      }
      if (packet.kind === "stream-start") setLiveText("");
      if (packet.kind === "delta") setLiveText(previous => previous + String(packet.text ?? ""));
      if (packet.kind === "status") { setRunning(Boolean(packet.running)); if (packet.reviews) setReviews(packet.reviews); }
      if (packet.kind === "reviews") setReviews(packet.reviews ?? []);
      if (packet.kind === "error") setNotice(String(packet.error));
    };
    const connect = () => {
      if (!active) return;
      const source = new EventSource(`/api/sessions/${encodeURIComponent(selected)}/events?offset=${offset}`);
      stream.current = source;
      source.onopen = () => setNotice("");
      source.onmessage = message => {
        const packet = JSON.parse(message.data);
        consume(packet);
        if (packet.kind === "snapshot" && packet.hasMore) {
          source.close();
          reconnect = setTimeout(connect, 0);
        }
      };
      source.onerror = () => {
        source.close();
        if (!active) return;
        setNotice("Connection interrupted; reconnecting to the persisted conversation…");
        reconnect = setTimeout(connect, 1_000);
      };
    };
    const loadHistory = async () => {
      do {
        const page = await api<{ events: EventItem[]; nextOffset: number; hasMore: boolean; running: boolean; reviews: Review[] }>(`/sessions/${encodeURIComponent(selected)}?offset=${offset}`);
        if (!active) return;
        consume({ kind: "snapshot", ...page });
        if (!page.hasMore) break;
      } while (active);
      connect();
    };
    void loadHistory().catch(error => { if (active) setNotice(error instanceof Error ? error.message : String(error)); });
    return () => { active = false; if (reconnect) clearTimeout(reconnect); stream.current?.close(); };
  }, [selected]);

  const current = sessions.find(item => item.sessionId === selected) ?? null;
  return <main className="app-shell">
    <aside>
      <div className="brand"><span>spec2gds</span><strong>Design assistant</strong></div>
      <button className="new-button" onClick={() => setSelected(null)}>＋ Connect document</button>
      <nav>{sessions.filter(session => showArchived || !session.archived).map(session => <button className={session.sessionId === selected ? "active" : ""} key={session.sessionId} onClick={() => setSelected(session.sessionId)}>
        <span className={`domain ${session.domain}`}>{session.domain}</span><b>{session.title}</b><small>{session.scope === "entity" ? `${session.entityKind}: ${session.entityId}` : session.documentId}</small>
      </button>)}</nav>
      <button className="archive-toggle" onClick={() => setShowArchived(value => !value)}>{showArchived ? "Hide archived" : `Archived (${sessions.filter(item => item.archived).length})`}</button>
      <footer><span>Harness · gpt-4o-mini</span>{capabilities && <div className="service-status"><span className={capabilities.assistant.modelConfigured ? "online" : "offline"}>Model</span><span className={capabilities.owners.spec.some(item => item.available) ? "online" : "offline"}>Spec</span><span className={capabilities.owners.circuit.some(item => item.available) ? "online" : "offline"}>Circuit</span></div>}</footer>
    </aside>
    <section className="workspace">
      {notice && <div className="notice" role="alert"><span>{notice}</span><button onClick={() => setNotice("")}>×</button></div>}
      {!selected ? <ConnectionPanel onCreated={session => { setSessions(previous => [session, ...previous]); setSelected(session.sessionId); }} onError={setNotice} />
        : <Conversation session={current} events={events} reviews={reviews} liveText={liveText} running={running} onRunning={setRunning} onReviews={setReviews} onError={setNotice} onSessionChanged={async archived => { await refreshSessions(); if (archived) setSelected(null); }} />}
    </section>
  </main>;
}

function ConnectionPanel({ onCreated, onError }: { onCreated(session: Session): void; onError(message: string): void }) {
  const [domain, setDomain] = useState<Domain>("spec");
  const [scope, setScope] = useState<"document" | "entity">("document");
  const [busy, setBusy] = useState(false);
  async function submit(event: React.FormEvent<HTMLFormElement>) {
    event.preventDefault(); setBusy(true);
    const data = new FormData(event.currentTarget);
    try {
      const result = await api<{ session: Session }>("/sessions", {
        domain, scope: domain === "circuit" ? "document" : scope,
        serviceBaseUrl: data.get("serviceBaseUrl"), documentId: data.get("documentId"),
        entityKind: scope === "entity" ? data.get("entityKind") : undefined,
        entityId: scope === "entity" ? data.get("entityId") : undefined,
      });
      onCreated(result.session);
    } catch (error) { onError(error instanceof Error ? error.message : String(error)); }
    finally { setBusy(false); }
  }
  return <div className="connect-panel">
    <p className="eyebrow">Existing documents</p><h1>Connect a design workspace</h1>
    <p>Each conversation is permanently bound to one owner. Discussion is safe; every proposed change is previewed and waits for your explicit action.</p>
    <div className="domain-tabs"><button className={domain === "spec" ? "active" : ""} onClick={() => setDomain("spec")}>Specification</button><button className={domain === "circuit" ? "active" : ""} onClick={() => setDomain("circuit")}>Circuit</button></div>
    <form onSubmit={submit}>
      <label>Owner service URL<input name="serviceBaseUrl" defaultValue={domain === "spec" ? "http://127.0.0.1:6010" : "http://127.0.0.1:6011/api/circuit-designer/v1"} key={domain} required /></label>
      <label>Document ID<input name="documentId" required /></label>
      {domain === "spec" && <><label>Scope<select value={scope} onChange={event => setScope(event.target.value as "document" | "entity")}><option value="document">Complete specification</option><option value="entity">Selected entity</option></select></label>
      {scope === "entity" && <div className="two"><label>Entity kind<select name="entityKind"><option>component</option><option>design</option><option>bus_definition</option><option>abstraction_definition</option><option>narrative_block</option></select></label><label>Entity ID<input name="entityId" required /></label></div>}</>}
      <button className="primary" disabled={busy}>{busy ? "Validating…" : "Connect document"}</button>
    </form>
  </div>;
}

function Conversation({ session, events, reviews, liveText, running, onRunning, onReviews, onError, onSessionChanged }: {
  session: Session | null; events: EventItem[]; reviews: Review[]; liveText: string; running: boolean;
  onRunning(value: boolean): void; onReviews(value: Review[]): void; onError(message: string): void; onSessionChanged(archived: boolean): Promise<void>;
}) {
  const [text, setText] = useState("");
  const transcript = useMemo(() => events.filter(item => ["user/message", "assistant/message", "tool/call", "tool/result", "turn/end"].includes(item.type)), [events]);
  if (!session) return <div className="center">Loading conversation…</div>;
  async function send(event: React.FormEvent) {
    event.preventDefault(); if (!text.trim() || running) return;
    onRunning(true);
    try { await api(`/sessions/${session!.sessionId}/messages`, { text }); setText(""); }
    catch (error) { onRunning(false); onError(error instanceof Error ? error.message : String(error)); }
  }
  async function cancel() {
    try { await api(`/sessions/${session!.sessionId}/cancel`, {}); }
    catch (error) { onError(error instanceof Error ? error.message : String(error)); }
  }
  async function manage(action: "rename" | "archive" | "unarchive") {
    try {
      let title: string | undefined;
      if (action === "rename") {
        const value = window.prompt("Conversation title", session!.title);
        if (value === null) return;
        title = value;
      }
      await api(`/sessions/${session!.sessionId}/manage`, { action, ...(title === undefined ? {} : { title }) });
      await onSessionChanged(action === "archive");
    } catch (error) { onError(error instanceof Error ? error.message : String(error)); }
  }
  return <div className="conversation">
    <header><div><span className={`domain ${session.domain}`}>{session.domain}</span><h2>{session.title}</h2><p>{session.ownerUrl} · {session.documentId}{session.scope === "entity" ? ` · ${session.entityKind}/${session.entityId}` : ""}</p></div><div className="conversation-actions"><span className="owner-state">Owner checked per action</span><button onClick={() => void manage("rename")} disabled={running}>Rename</button><button onClick={() => void manage(session.archived ? "unarchive" : "archive")} disabled={running}>{session.archived ? "Unarchive" : "Archive"}</button></div></header>
    <div className="transcript">
      {!transcript.some(item => item.type === "user/message") && <div className="welcome"><p className="eyebrow">Bound and ready</p><h1>Discuss, inspect, then propose.</h1><p>I’ll read fresh owner context before working with concrete design facts. A proposal remains a preview until you use its review card.</p></div>}
      {transcript.map(item => <EventView item={item} key={`${item.seq}:${item.type}`} />)}
      {liveText && <article className="message assistant streaming"><span>Assistant</span><div>{liveText}</div></article>}
      <div className="review-feed">{reviews.map(review => <ReviewCard key={review.proposalId} review={review} sessionId={session.sessionId} onReviews={onReviews} onError={onError} />)}</div>
    </div>
    {!session.archived && <form className="composer" onSubmit={send}><textarea value={text} onChange={event => setText(event.target.value)} onKeyDown={event => { if (event.key === "Enter" && !event.shiftKey) { event.preventDefault(); event.currentTarget.form?.requestSubmit(); } }} placeholder="Ask about the design or request a proposal…" rows={3} /><div><small>{running ? "The assistant is working…" : "Enter to send · Shift+Enter for a new line"}</small>{running ? <button type="button" onClick={cancel}>Stop</button> : <button className="primary" disabled={!text.trim()}>Send</button>}</div></form>}
  </div>;
}

function EventView({ item }: { item: EventItem }) {
  if (item.type === "user/message" || item.type === "assistant/message") return <article className={`message ${item.type.startsWith("user") ? "user" : "assistant"}`}><span>{item.type.startsWith("user") ? "You" : "Assistant"}</span><div>{item.text}</div></article>;
  if (item.type === "tool/call") return <details className="tool"><summary>{item.name?.replaceAll("_", " ")}</summary><pre>{formatJson(item.arguments)}</pre></details>;
  if (item.type === "turn/end" && JSON.stringify(item.data).includes('"error"')) return <p className="inline-error">The model turn ended with an error. Check service logs and retry.</p>;
  return null;
}

function ReviewCard({ review, sessionId, onReviews, onError }: { review: Review; sessionId: string; onReviews(value: Review[]): void; onError(message: string): void }) {
  const [busy, setBusy] = useState(false);
  const title = String(review.artifact.title ?? "Design proposal");
  async function act(action: "apply" | "send" | "discard") {
    setBusy(true);
    try {
      await api(`/sessions/${sessionId}/reviews/${encodeURIComponent(review.proposalId)}/actions`, { action });
      const result = await api<{ reviews: Review[] }>(`/sessions/${sessionId}/reviews`); onReviews(result.reviews);
    } catch (error) { onError(error instanceof Error ? error.message : String(error)); }
    finally { setBusy(false); }
  }
  return <article className={`review ${review.state}`}><header><div><span>Proposal review</span><h3>{title}</h3></div><b>{review.state}</b></header><p>{String(review.artifact.summary ?? "")}</p>
    <section className="proposal-notes"><div><strong>Rationale</strong><p>{String(review.artifact.rationale ?? "")}</p></div><div><strong>Assumptions</strong>{Array.isArray(review.artifact.assumptions) && review.artifact.assumptions.length ? <ul>{review.artifact.assumptions.map((item, index) => <li key={index}>{String(item)}</li>)}</ul> : <p>None stated.</p>}</div></section>
    {Boolean(review.preview) && <PreviewDiff review={review} />}
    <details><summary>Exact operations</summary><pre>{formatJson(review.artifact.operations ?? (review.artifact.batch as Record<string, unknown> | undefined)?.operations)}</pre></details>
    {Boolean(review.preview) && <details><summary>Raw owner preview</summary><pre>{formatJson(review.preview)}</pre></details>}
    {Boolean(review.diagnostics && JSON.stringify(review.diagnostics) !== "[]") && <div className="diagnostics"><strong>Owner diagnostics</strong><pre>{formatJson(review.diagnostics)}</pre></div>}
    {["ready", "rejected", "stale", "reconcile"].includes(review.state) && <div className="actions"><button onClick={() => void act("discard")} disabled={busy}>Discard</button>{["ready", "reconcile"].includes(review.state) && <button className="primary" onClick={() => void act(review.domain === "spec" ? "apply" : "send")} disabled={busy}>{review.state === "reconcile" ? "Reconcile with owner" : review.domain === "spec" ? "Approve and apply" : "Send to Circuit Designer"}</button>}</div>}
    {review.state === "reconcile" && <p className="warning">The owner response was uncertain. Retry the same action to reconcile by proposal identity.</p>}
  </article>;
}

function PreviewDiff({ review }: { review: Review }) {
  if (!isRecord(review.preview)) return null;
  if (review.domain === "spec") {
    const changes = Array.isArray(review.preview.diff) ? review.preview.diff.filter(isRecord) : [];
    return <section className="preview-diff"><strong>Specification preview</strong>{changes.length ? <div className="change-list">{changes.map((change, index) => <div className="change" key={index}><code>{String(change.path ?? "change")}</code><span>{String(change.change ?? "changed")}</span><div><small>Before</small><pre>{formatJson(change.before)}</pre></div><div><small>After</small><pre>{formatJson(change.after)}</pre></div></div>)}</div> : <p>No semantic section changes reported.</p>}</section>;
  }
  const diff = isRecord(review.preview.diff) ? review.preview.diff : {};
  const groups = ["added", "removed", "changed", "connections_changed"].map(name => ({ name, values: Array.isArray(diff[name]) ? diff[name] as unknown[] : [] }));
  return <section className="preview-diff"><strong>Circuit preview</strong><div className="diff-summary">{groups.map(group => <span key={group.name}><b>{group.values.length}</b>{group.name.replaceAll("_", " ")}</span>)}</div>{groups.some(group => group.values.length) ? <div className="change-list">{groups.filter(group => group.values.length).map(group => <details key={group.name}><summary>{group.name.replaceAll("_", " ")}</summary><pre>{formatJson(group.values)}</pre></details>)}</div> : <p>No logical circuit changes reported.</p>}</section>;
}

function isRecord(value: unknown): value is Record<string, unknown> {
  return Boolean(value) && typeof value === "object" && !Array.isArray(value);
}

function mergeEvents(previous: EventItem[], incoming: EventItem[]): EventItem[] {
  const values = new Map(previous.map(item => [item.seq, item]));
  for (const item of incoming) values.set(item.seq, item);
  return [...values.values()].sort((left, right) => left.seq - right.seq);
}

function formatJson(value: unknown): string {
  if (typeof value === "string") { try { return JSON.stringify(JSON.parse(value), null, 2); } catch { return value; } }
  return JSON.stringify(value, null, 2);
}

createRoot(document.getElementById("root")!).render(<React.StrictMode><App /></React.StrictMode>);
