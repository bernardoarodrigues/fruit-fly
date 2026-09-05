"use strict";

const $ = (id) => document.getElementById(id);
let state = null;
let frameSequence = -1;
let activitySequence = -1;
let frameURL = null;
let lastTime = -1;
let connectionError = false;
let commandError = null;
const activity = [];
const number = (value, digits = 2) => Number.isFinite(Number(value)) && value !== null && value !== undefined ? Number(value).toFixed(digits) : "—";
const count = (value) => value === undefined || value === null ? "—" : Number(value).toLocaleString();
const setText = (id, text) => { $(id).textContent = text; };

async function control(command) {
  try {
    const response = await fetch("/api/control", {method: "POST", headers: {"Content-Type": "application/json"}, body: JSON.stringify(command)});
    const result = await response.json();
    if (!response.ok) throw new Error(result.error || "The control was not accepted.");
    commandError = null;
  } catch (error) {
    commandError = error.message;
    showError(commandError);
  }
}

function showError(message) {
  $("error").hidden = !message;
  $("error").textContent = message || "";
}

function plotActivity(value, sequence, simTime) {
  if (!Number.isFinite(Number(value)) || value === null || value === undefined || sequence === activitySequence) return;
  activitySequence = sequence;
  if (simTime < lastTime) activity.length = 0;
  lastTime = simTime;
  activity.push(Number(value));
  if (activity.length > 120) activity.shift();
  const peak = Math.max(1, ...activity);
  const coordinates = activity.map((v, index) => `${(index / 119 * 800).toFixed(2)},${(88 - v / peak * 76).toFixed(2)}`);
  $("chart-line").setAttribute("d", coordinates.length > 1 ? `M${coordinates.join(" L")}` : "");
  $("chart-fill").setAttribute("d", coordinates.length > 1 ? `M0,96 L${coordinates.join(" L")} L${((activity.length - 1) / 119 * 800).toFixed(2)},96 Z` : "");
  setText("chart-range", `0 – ${count(peak)}`);
}

function update(data) {
  state = data;
  const ready = ["running", "paused"].includes(data.status);
  const telemetry = data.telemetry || {};
  const neural = telemetry.neural || {};
  const senses = telemetry.senses || {};
  const stimuli = telemetry.stimuli || {};
  const physiology = telemetry.physiology || {};
  const assays = {
    sensory: ["Sensory assay", "Environmental stimuli feed the neural model."],
    motor_probe: ["Direct DN motor calibration", "Selected descending neurons receive artificial stimulation."],
    controller_only: ["Controller-only baseline", "Walking commands bypass neural activity."],
  };
  const assay = assays[telemetry.assay] || ["Assay not reported", "The runtime has not identified its experiment mode."];
  setText("assay-label", assay[0]);
  setText("assay-description", assay[1]);
  $("assay-bar").classList.toggle("calibration", ["motor_probe", "controller_only"].includes(telemetry.assay));
  const labels = {initializing: "Initializing", running: "Simulation running", paused: "Paused", error: "Worker error", stopped: "Stopped"};
  setText("status-label", labels[data.status] || data.status);
  $("status-dot").className = `dot ${data.status === "running" ? "live" : data.status === "error" ? "error" : ""}`;
  setText("frame-label", ready ? "LIVE ARENA / MALE 01" : (data.status === "error" ? "SIMULATION STOPPED" : "WAITING FOR SIMULATION"));
  setText("frame-age", data.frame_age_seconds === null ? "" : `${number(data.frame_age_seconds, 1)}s since update`);
  for (const control of document.querySelectorAll(".transport button, .transport select, .sidebar input")) control.disabled = !ready;
  setText("pause-label", data.paused ? "Resume" : "Pause");
  setText("pause-icon", data.paused ? "▶" : "Ⅱ");
  $("pause").setAttribute("aria-label", data.paused ? "Resume simulation" : "Pause simulation");
  for (const camera of document.querySelectorAll("[data-camera]")) {
    const selected = camera.dataset.camera === data.camera;
    camera.classList.toggle("selected", selected);
    camera.setAttribute("aria-pressed", String(selected));
  }
  if (document.activeElement !== $("speed")) $("speed").value = String(data.speed);
  for (const name of ["odor", "light"]) {
    if (typeof stimuli[name] === "number" && Number.isFinite(stimuli[name]) && document.activeElement !== $(name)) {
      $(name).value = String(stimuli[name]);
      setText(`${name}-value`, `${number(stimuli[name])}×`);
    }
  }
  $("time").replaceChildren(document.createTextNode(`${number(telemetry.t_s)} `), Object.assign(document.createElement("small"), {textContent: "s"}));
  $("realtime").replaceChildren(document.createTextNode(`${number(data.observed_realtime_factor)} `), Object.assign(document.createElement("small"), {textContent: "× realtime"}));
  setText("behavior", String(telemetry.behavior || "Awaiting state").replaceAll("_", " "));
  setText("active-neurons", count(neural.active_neurons));
  setText("neuron-count", count(neural.neurons));
  setText("edge-count", count(neural.edges));
  setText("spike-count", count(neural.spikes));
  setText("backend", neural.backend || "—");
  for (const [label, key] of [["min", "minimum"], ["mean", "mean"], ["max", "maximum"]]) {
    const value = neural.voltage_mv?.[key];
    setText(`voltage-${label}`, typeof value === "number" && Number.isFinite(value) ? `${number(value, 1)} mV` : "—");
  }
  const vision = telemetry.vision || {};
  setText("vision-status", vision.enabled === true ? "Camera enabled" : vision.enabled === false ? "Disabled" : "Not reported");
  setText("vision-values", Array.isArray(vision.mean_by_eye)
    ? `L ${number(vision.mean_by_eye[0], 3)} · R ${number(vision.mean_by_eye[1], 3)} · native intensity`
    : "No eye samples available.");
  setText("vision-sample", vision.sample_t_s == null ? "No sampling time reported."
    : `Sample at ${number(vision.sample_t_s, 3)} s${Array.isArray(vision.shape) ? ` · shape ${vision.shape.join(" × ")}` : ""}`);
  const clubRates = senses.club_event_rates_hz || {};
  const clubEntries = Object.entries(clubRates);
  setText("club-status", clubEntries.length ? "Club adapter enabled"
    : Object.hasOwn(senses, "club_event_rates_hz") ? "Adapter disabled" : "Not reported");
  $("club-rates").replaceChildren();
  for (const [leg, rate] of clubEntries) {
    const chip = document.createElement("span");
    chip.className = "output-rate";
    chip.textContent = leg;
    chip.append(Object.assign(document.createElement("strong"), {textContent: `${number(rate, 1)} Hz`}));
    $("club-rates").append(chip);
  }
  setText("neural-subtitle", neural.ablated ? `${neural.ablation_target || "Motor readout"} muted` : neural.neurons ? "Spiking network telemetry" : "Waiting for neural telemetry");
  if (typeof neural.ablated === "boolean") $("ablation").checked = neural.ablated;
  if (neural.ablation_target) {
    setText("intervention-label", `Mute ${neural.ablation_target}`);
    setText("intervention-target", `Target: ${neural.ablation_target}`);
  }
  if (neural.ablation_description) setText("ablation-note", neural.ablation_description);
  for (const name of ["energy", "hydration", "crop"]) {
    const value = physiology[name];
    const capacity = physiology.capacities?.[name];
    const hasCapacity = typeof capacity === "number" && Number.isFinite(capacity) && capacity > 0;
    const hasValue = typeof value === "number" && Number.isFinite(value);
    $(name).hidden = !hasCapacity || !hasValue;
    $(name).max = hasCapacity ? capacity : 1;
    $(name).value = hasValue ? value : 0;
    const label = !hasValue ? "—" : hasCapacity ? `${number(value / capacity * 100, 0)}%` : `${number(value, 3)} units`;
    $(name).setAttribute("aria-label", `${name}: ${label}`);
    setText(`${name}-value`, label);
  }
  setText("odor-left", number(senses.odor?.[0], 3));
  setText("odor-right", number(senses.odor?.[1], 3));
  setText("food-contact", senses.taste_food == null ? "—" : senses.taste_food ? "Detected" : "No contact");
  setText("water-contact", senses.taste_water == null ? "—" : senses.taste_water ? "Detected" : "No contact");
  const position = telemetry.pose?.position_mm;
  setText("coordinates", position ? `x ${number(position[0], 1)} · y ${number(position[1], 1)} mm` : "x — · y — mm");
  if (telemetry.provenance) setText("provenance", typeof telemetry.provenance === "string" ? telemetry.provenance : JSON.stringify(telemetry.provenance));
  const warnings = telemetry.warnings || data.warnings;
  if (warnings) setText("warnings", Array.isArray(warnings) ? warnings.join(" ") : String(warnings));
  else if (ready) setText("warnings", "Behavior and physiological variables are model approximations. Inspect the repository research and validation notes for evidence and limitations.");
  plotActivity(neural.active_neurons, data.frame_sequence, telemetry.t_s);
  $("output-rates").replaceChildren();
  for (const [name, rate] of Object.entries(neural.output_rates || {})) {
    const chip = document.createElement("span");
    chip.className = "output-rate";
    chip.textContent = name.replaceAll("_", " ");
    chip.append(Object.assign(document.createElement("strong"), {textContent: `${number(rate, 1)} Hz`}));
    $("output-rates").append(chip);
  }
  showError(data.error || commandError);
  if (data.status === "error" && !frameURL) {
    $("loading").querySelector(".loader").hidden = true;
    $("loading").querySelector("strong").textContent = "The simulation could not start";
    $("loading").querySelector("span").textContent = "See the error above and the server terminal for details.";
  }
}

async function poll() {
  try {
    const response = await fetch("/api/state");
    if (!response.ok) throw new Error(`Server returned ${response.status}`);
    const data = await response.json();
    connectionError = false;
    update(data);
    if (data.frame_sequence > 0 && data.frame_sequence !== frameSequence) {
      const imageResponse = await fetch("/api/frame");
      if (imageResponse.ok && imageResponse.status !== 204) {
        const blob = await imageResponse.blob();
        const nextURL = URL.createObjectURL(blob);
        const previousURL = frameURL;
        const image = $("simulation-image");
        image.onload = () => { if (previousURL) URL.revokeObjectURL(previousURL); };
        image.src = nextURL;
        image.hidden = false;
        $("loading").hidden = true;
        frameURL = nextURL;
        frameSequence = Number(imageResponse.headers.get("X-Frame-Sequence")) || data.frame_sequence;
      }
    }
  } catch (error) {
    connectionError = true;
    if (state) state.status = "disconnected";
    for (const control of document.querySelectorAll(".transport button, .transport select, .sidebar input")) control.disabled = true;
    setText("status-label", "Disconnected");
    setText("frame-label", "DISCONNECTED / LAST RECEIVED FRAME");
    $("status-dot").className = "dot error";
    showError(`Cannot reach the local simulation server. ${error.message}`);
  } finally {
    window.setTimeout(poll, document.hidden ? 1500 : connectionError ? 1000 : 150);
  }
}

$("pause").addEventListener("click", () => control({type: "pause", paused: !state?.paused}));
$("reset").addEventListener("click", () => control({type: "reset"}));
$("speed").addEventListener("change", (event) => control({type: "speed", value: Number(event.target.value)}));
$("ablation").addEventListener("change", (event) => control({type: "ablation", enabled: event.target.checked}));
for (const button of document.querySelectorAll("[data-camera]")) button.addEventListener("click", () => control({type: "camera", camera: button.dataset.camera}));
for (const name of ["odor", "light"]) {
  $(name).addEventListener("input", (event) => setText(`${name}-value`, `${number(event.target.value)}×`));
  $(name).addEventListener("change", (event) => control({type: "stimulus", name, value: Number(event.target.value)}));
}
document.addEventListener("keydown", (event) => {
  if (["INPUT", "SELECT", "TEXTAREA", "BUTTON", "SUMMARY"].includes(event.target.tagName) || event.ctrlKey || event.metaKey || event.altKey || !["running", "paused"].includes(state?.status)) return;
  if (event.code === "Space") { event.preventDefault(); control({type: "pause", paused: !state.paused}); }
  if (["1", "2", "3"].includes(event.key)) control({type: "camera", camera: ["overview", "follow", "side"][Number(event.key) - 1]});
});
poll();
