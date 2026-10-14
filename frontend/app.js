const form = document.querySelector("#run-form");
const example = document.querySelector("#example");
const useSource = document.querySelector("#use-source");
const sourceField = document.querySelector("#source-field");
const source = document.querySelector("#source");
const dataWidth = document.querySelector("#data-width");
const depth = document.querySelector("#depth");
const start = document.querySelector("#start");
const cancel = document.querySelector("#cancel");
const formError = document.querySelector("#form-error");
const status = document.querySelector("#status");
const runTitle = document.querySelector("#run-title");
const runId = document.querySelector("#run-id");
const emptyState = document.querySelector("#empty-state");
const results = document.querySelector("#results");
const timeline = document.querySelector("#timeline");
const evidencePanel = document.querySelector("#evidence-panel");
const evidenceBody = document.querySelector("#evidence-body");
const patchPanel = document.querySelector("#patch-panel");
const patch = document.querySelector("#patch");
const artifactsPanel = document.querySelector("#artifacts-panel");
const artifacts = document.querySelector("#artifacts");

let activeRun = null;
let eventStream = null;

function element(tag, text, className) {
  const node = document.createElement(tag);
  if (text !== undefined) node.textContent = text;
  if (className) node.className = className;
  return node;
}

async function api(path, options) {
  const response = await fetch(path, options);
  let body = null;
  try { body = await response.json(); } catch { body = null; }
  if (!response.ok) throw new Error(body?.error?.message || body?.detail || `Request failed (${response.status})`);
  return body;
}

async function loadExamples() {
  try {
    const items = await api("/api/examples");
    example.replaceChildren(...items.map((item) => {
      const option = element("option", `${item.id} · DW ${item.dataWidth} · DEPTH ${item.depth}`);
      option.value = item.id;
      option.dataset.width = item.dataWidth;
      option.dataset.depth = item.depth;
      return option;
    }));
    example.dispatchEvent(new Event("change"));
  } catch (error) {
    example.replaceChildren(element("option", "Examples unavailable"));
    formError.textContent = error.message;
  }
}

function setStatus(value) {
  const good = value === "completed";
  const bad = ["unresolved", "invalid_input", "infrastructure_error"].includes(value);
  status.className = `status ${good ? "good" : bad ? "bad" : value === "idle" ? "idle" : "active"}`;
  status.textContent = value.replaceAll("_", " ").toUpperCase();
}

function addEvent(event) {
  if (timeline.querySelector(`[data-sequence="${event.sequence}"]`)) return;
  const item = element("li");
  item.dataset.sequence = event.sequence;
  item.append(element("strong", event.state), element("span", event.message));
  timeline.append(item);
}

function renderEvidence(report) {
  const failure = report?.baseline?.failures?.[0];
  if (!failure) return;
  const rows = Object.keys(failure.expected).map((signal) => {
    const row = element("tr");
    [failure.cycle, signal, failure.expected[signal], failure.observed[signal]].forEach((value) => {
      row.append(element("td", String(value)));
    });
    return row;
  });
  evidenceBody.replaceChildren(...rows);
  evidencePanel.hidden = false;
}

function renderPatch(report) {
  const attempt = report?.attempts?.find((item) => item.diff);
  if (!attempt) return;
  patch.textContent = attempt.diff;
  patchPanel.hidden = false;
}

async function loadArtifacts() {
  const items = await api(`/api/runs/${activeRun}/artifacts`);
  artifacts.replaceChildren(...items.map((item) => {
    const li = element("li");
    const link = element("a");
    link.href = `/api/runs/${activeRun}/artifacts/${encodeURIComponent(item.name)}`;
    link.append(element("span", item.name), element("small", `${Math.max(1, Math.round(item.size / 1024))} KiB`));
    li.append(link);
    return li;
  }));
  artifactsPanel.hidden = items.length === 0;
  const reportItem = items.find((item) => item.name === "report.json");
  if (reportItem) {
    const report = await api(`/api/runs/${activeRun}/artifacts/report.json`);
    renderEvidence(report);
    renderPatch(report);
  }
}

async function finishRun() {
  const record = await api(`/api/runs/${activeRun}`);
  record.events.forEach(addEvent);
  setStatus(record.status);
  runTitle.textContent = record.verdict ? record.verdict.replaceAll("_", " ") : record.status;
  cancel.hidden = true;
  start.disabled = false;
  await loadArtifacts();
}

function followRun() {
  eventStream?.close();
  eventStream = new EventSource(`/api/runs/${activeRun}/events`);
  eventStream.addEventListener("run_event", (message) => addEvent(JSON.parse(message.data)));
  eventStream.addEventListener("done", async () => {
    eventStream.close();
    await finishRun();
  });
  eventStream.onerror = () => {
    formError.textContent = "Live updates disconnected; the run can still be retrieved by ID.";
  };
}

useSource.addEventListener("change", () => {
  sourceField.hidden = !useSource.checked;
  example.disabled = useSource.checked;
  source.required = useSource.checked;
});

example.addEventListener("change", () => {
  const selected = example.selectedOptions[0];
  if (selected?.dataset.width) dataWidth.value = selected.dataset.width;
  if (selected?.dataset.depth) depth.value = selected.dataset.depth;
});

form.addEventListener("submit", async (event) => {
  event.preventDefault();
  formError.textContent = "";
  start.disabled = true;
  const body = {
    dataWidth: Number(dataWidth.value),
    depth: Number(depth.value),
    ...(useSource.checked ? { source: source.value } : { exampleId: example.value }),
  };
  try {
    const created = await api("/api/runs", {
      method: "POST",
      headers: { "Content-Type": "application/json", "Idempotency-Key": crypto.randomUUID() },
      body: JSON.stringify(body),
    });
    activeRun = created.id;
    emptyState.hidden = true;
    results.hidden = false;
    timeline.replaceChildren();
    evidencePanel.hidden = true;
    patchPanel.hidden = true;
    artifactsPanel.hidden = true;
    runId.textContent = activeRun;
    runTitle.textContent = "Verification in progress";
    setStatus("queued");
    cancel.hidden = false;
    followRun();
  } catch (error) {
    formError.textContent = error.message;
    start.disabled = false;
  }
});

cancel.addEventListener("click", async () => {
  if (!activeRun) return;
  cancel.disabled = true;
  try {
    await api(`/api/runs/${activeRun}/cancel`, { method: "POST" });
  } catch (error) {
    formError.textContent = error.message;
  } finally {
    cancel.disabled = false;
  }
});

loadExamples();

