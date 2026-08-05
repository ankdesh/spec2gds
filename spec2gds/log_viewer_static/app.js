const records = new Map();
const list = document.querySelector("#records");
const empty = document.querySelector("#empty");
const status = document.querySelector("#status");
const filters = ["application", "component", "severity", "correlation", "query"];

function add(record, update = true) {
  if (!record?.event_id || records.has(record.event_id)) return;
  records.set(record.event_id, record);
  if (update) { refreshOptions(); render(); }
}

function refreshOptions() {
  for (const field of ["application", "component"]) {
    const select = document.querySelector(`#${field}`);
    const selected = select.value;
    const values = [...new Set([...records.values()].map((item) => item[field]).filter(Boolean))].sort();
    select.replaceChildren(new Option(`All ${field === "application" ? "applications" : "components"}`, ""), ...values.map((value) => new Option(value, value)));
    select.value = selected;
  }
}

function matches(record) {
  const application = document.querySelector("#application").value;
  const component = document.querySelector("#component").value;
  const severity = document.querySelector("#severity").value;
  const correlation = document.querySelector("#correlation").value.trim();
  const query = document.querySelector("#query").value.trim().toLowerCase();
  return (!application || record.application === application)
    && (!component || record.component === component)
    && (!severity || record.severity === severity)
    && (!correlation || record.correlation_id === correlation)
    && (!query || JSON.stringify(record).toLowerCase().includes(query));
}

function render() {
  const visible = [...records.values()].filter(matches).slice(-500);
  list.replaceChildren(...visible.map(row));
  empty.hidden = visible.length > 0;
  if (document.querySelector("#follow").checked) window.scrollTo({ top: document.body.scrollHeight });
}

function row(record) {
  const item = document.createElement("li");
  item.className = `record ${record.severity}`;
  const button = document.createElement("button");
  button.className = "summary";
  button.setAttribute("aria-expanded", "false");
  for (const [className, value] of [
    ["time", new Date(record.timestamp).toLocaleTimeString()],
    ["severity", record.severity], ["application", record.application],
    ["component", record.component], ["message", record.message],
  ]) {
    const span = document.createElement("span"); span.className = className; span.textContent = value ?? "—"; button.append(span);
  }
  const details = document.createElement("pre"); details.hidden = true; details.textContent = JSON.stringify(record, null, 2);
  button.addEventListener("click", () => { details.hidden = !details.hidden; button.setAttribute("aria-expanded", String(!details.hidden)); });
  item.append(button, details); return item;
}

for (const id of filters) document.querySelector(`#${id}`).addEventListener("input", render);
const initial = await fetch("/api/logs").then((response) => response.json());
const baseStatus = initial.logging_enabled ? `Logging ON · ${initial.level}` : "Logging OFF · showing retained entries";
status.textContent = baseStatus;
for (const record of initial.records) add(record, false);
refreshOptions(); render();
const stream = new EventSource("/api/logs/stream");
stream.onmessage = (event) => add(JSON.parse(event.data));
stream.onopen = () => { status.textContent = baseStatus; };
stream.onerror = () => { status.textContent = `${baseStatus} · viewer reconnecting`; };
