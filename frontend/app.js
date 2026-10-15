const form = document.querySelector("#run-form");
const contract = document.querySelector("#contract");
const example = document.querySelector("#example");
const useSource = document.querySelector("#use-source");
const sourceField = document.querySelector("#source-field");
const source = document.querySelector("#source");
const dataWidth = document.querySelector("#data-width");
const depth = document.querySelector("#depth");
const requesters = document.querySelector("#requesters");
const fifoParameters = document.querySelector("#fifo-parameters");
const arbiterParameters = document.querySelector("#arbiter-parameters");
const contractSummary = document.querySelector("#contract-summary");
const contractRules = document.querySelector("#contract-rules");
const pipelineContract = document.querySelector("#pipeline-contract");
const start = document.querySelector("#start");
const cancel = document.querySelector("#cancel");
const refresh = document.querySelector("#refresh");
const formError = document.querySelector("#form-error");
const runtimeStatus = document.querySelector("#runtime-status");
const status = document.querySelector("#status");
const runTitle = document.querySelector("#run-title");
const runId = document.querySelector("#run-id");
const emptyState = document.querySelector("#empty-state");
const results = document.querySelector("#results");
const proofPanel = document.querySelector("#proof-panel");
const proofClaim = document.querySelector("#proof-claim");
const proofGates = document.querySelector("#proof-gates");
const timeline = document.querySelector("#timeline");
const evidencePanel = document.querySelector("#evidence-panel");
const evidenceBody = document.querySelector("#evidence-body");
const patchPanel = document.querySelector("#patch-panel");
const patch = document.querySelector("#patch");
const artifactsPanel = document.querySelector("#artifacts-panel");
const artifacts = document.querySelector("#artifacts");

let activeRun = null;
let eventStream = null;
let examples = [];
const terminalStates = ["completed", "unresolved", "invalid_input", "cancelled", "infrastructure_error"];

const contractDetails = {
  fifo: {
    label: "Synchronous FIFO",
    summary: "Selected FIFO contract",
    placeholder: "module fifo #(…",
    rules: [
      "Synchronous active-high reset; registered read output.",
      "Acceptance uses state immediately before the rising edge.",
      "At full: read accepted, write rejected. At empty: write accepted, read rejected.",
      "Explicit wrapping supports non-power-of-two depths.",
    ],
  },
  arbiter: {
    label: "Round-robin arbiter",
    summary: "Selected arbiter contract",
    placeholder: "module round_robin_arbiter #(…",
    rules: [
      "Synchronous active-high reset; registered one-hot-or-zero grant.",
      "Selection starts at the saved priority and wraps by requester index.",
      "Each successful grant advances priority to the following requester.",
      "No request produces zero grant and preserves the current priority.",
    ],
  },
};

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

function renderExamples() {
  const items = examples.filter((item) => item.contractId === contract.value);
  example.replaceChildren(...items.map((item) => {
    const parameters = item.contractId === "arbiter"
      ? `REQUESTERS ${item.requesters}`
      : `DW ${item.dataWidth} · DEPTH ${item.depth}`;
    const option = element("option", `${item.id} · ${parameters}`);
    option.value = item.id;
    if (item.dataWidth) option.dataset.width = item.dataWidth;
    if (item.depth) option.dataset.depth = item.depth;
    if (item.requesters) option.dataset.requesters = item.requesters;
    return option;
  }));
  if (items.length === 0) example.append(element("option", "No bundled cases"));
  example.dispatchEvent(new Event("change"));
}

async function loadExamples() {
  try {
    examples = await api("/api/examples");
    renderExamples();
  } catch (error) {
    example.replaceChildren(element("option", "Examples unavailable"));
    formError.textContent = error.message;
  }
}

async function loadHealth() {
  try {
    const health = await api("/api/health");
    runtimeStatus.className = `runtime-status ${health.repairReady ? "ready" : "unavailable"}`;
    runtimeStatus.textContent = health.repairReady
      ? `Repair ready · ${health.provider.modelId}`
      : "Verification ready · repair unavailable until NEBIUS_API_KEY is set";
  } catch (error) {
    runtimeStatus.className = "runtime-status unavailable";
    runtimeStatus.textContent = `Readiness unavailable · ${error.message}`;
  }
}

function updateContract() {
  const isArbiter = contract.value === "arbiter";
  const details = contractDetails[contract.value];
  fifoParameters.hidden = isArbiter;
  arbiterParameters.hidden = !isArbiter;
  dataWidth.disabled = isArbiter;
  depth.disabled = isArbiter;
  requesters.disabled = !isArbiter;
  contractSummary.textContent = details.summary;
  contractRules.replaceChildren(...details.rules.map((rule) => element("li", rule)));
  pipelineContract.textContent = details.label;
  source.placeholder = details.placeholder;
  renderExamples();
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

function renderProof(report) {
  const attempt = report?.attempts?.at(-1);
  const requests = attempt?.provider_requests || [];
  const request = requests.at(-1);
  const totalTokens = requests.reduce((sum, item) => sum + (item?.usage?.total_tokens || 0), 0);
  const verification = attempt?.verification;
  const gates = [
    ["Baseline", report?.baseline_summary?.status || "not completed"],
    ["NVIDIA model", request ? `${request.model_id}${totalTokens ? ` · ${totalTokens} tokens` : ""}` : "not called"],
    ["Reproducer", verification?.reproducer?.status || "not required"],
    ["Locked regression", verification?.regression?.status || "not required"],
    ["Locked assets", report?.integrity?.locked_assets_unchanged ? "unchanged" : "not verified"],
    ["Repair attempts", `${report?.attempts?.length || 0} / ${report?.run_limits?.max_patch_attempts || 0}`],
  ];
  proofClaim.textContent = report?.claim || "No proof claim was recorded.";
  proofGates.replaceChildren(...gates.map(([label, value]) => {
    const item = element("div");
    item.append(element("dt", label), element("dd", value));
    return item;
  }));
  proofPanel.hidden = false;
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
    renderProof(report);
    renderEvidence(report);
    renderPatch(report);
  }
}

async function finishRun(record = null) {
  record ||= await api(`/api/runs/${activeRun}`);
  record.events.forEach(addEvent);
  setStatus(record.status);
  runTitle.textContent = record.verdict ? record.verdict.replaceAll("_", " ") : record.status;
  cancel.hidden = true;
  refresh.hidden = true;
  start.disabled = false;
  await loadArtifacts();
}

function handleRunError(error) {
  formError.textContent = `Run results could not be loaded: ${error.message}`;
  cancel.hidden = true;
  refresh.hidden = false;
  start.disabled = false;
}

async function recoverRun() {
  refresh.disabled = true;
  try {
    const record = await api(`/api/runs/${activeRun}`);
    record.events.forEach(addEvent);
    if (terminalStates.includes(record.status)) {
      await finishRun(record);
    } else {
      setStatus(record.status);
      formError.textContent = "";
      refresh.hidden = true;
      followRun();
    }
  } catch (error) {
    handleRunError(error);
  } finally {
    refresh.disabled = false;
  }
}

function followRun() {
  eventStream?.close();
  eventStream = new EventSource(`/api/runs/${activeRun}/events`);
  eventStream.addEventListener("run_event", (message) => {
    addEvent(JSON.parse(message.data));
    formError.textContent = "";
    refresh.hidden = true;
  });
  eventStream.addEventListener("done", () => {
    eventStream.close();
    finishRun().catch(handleRunError);
  });
  eventStream.onerror = () => {
    formError.textContent = "Live updates disconnected. Refresh this run to recover its latest state.";
    refresh.hidden = false;
  };
}

useSource.addEventListener("change", () => {
  sourceField.hidden = !useSource.checked;
  example.disabled = useSource.checked;
  source.required = useSource.checked;
});

contract.addEventListener("change", updateContract);

example.addEventListener("change", () => {
  const selected = example.selectedOptions[0];
  if (selected?.dataset.width) dataWidth.value = selected.dataset.width;
  if (selected?.dataset.depth) depth.value = selected.dataset.depth;
  if (selected?.dataset.requesters) requesters.value = selected.dataset.requesters;
});

form.addEventListener("submit", async (event) => {
  event.preventDefault();
  formError.textContent = "";
  start.disabled = true;
  const parameters = contract.value === "arbiter"
    ? { requesters: Number(requesters.value) }
    : { dataWidth: Number(dataWidth.value), depth: Number(depth.value) };
  const body = {
    contractId: contract.value,
    ...parameters,
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
    proofPanel.hidden = true;
    evidencePanel.hidden = true;
    patchPanel.hidden = true;
    artifactsPanel.hidden = true;
    runId.textContent = activeRun;
    runTitle.textContent = "Verification in progress";
    setStatus("queued");
    refresh.hidden = true;
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

refresh.addEventListener("click", recoverRun);

updateContract();
loadExamples();
loadHealth();

