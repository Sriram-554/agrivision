const $ = (s) => document.querySelector(s);
const $$ = (s) => [...document.querySelectorAll(s)];
let charts = {};
let autoRefresh;

function toast(message, type = "success") {
  const el = document.createElement("div");
  el.className = `toast ${type === "error" ? "error" : ""}`;
  el.textContent = message;
  $("#toastContainer").appendChild(el);
  setTimeout(() => el.remove(), 3800);
}

function setLoading(show) { $("#loadingOverlay").classList.toggle("hidden", !show); }

async function api(url, options = {}) {
  const response = await fetch(url, {
    ...options,
    headers: { "Content-Type": "application/json", ...(options.headers || {}) },
  });
  const data = await response.json().catch(() => ({ error: "Unexpected server response." }));
  if (!response.ok) throw new Error(data.error || "Request failed.");
  return data;
}

function formatTime(value) {
  if (!value) return "--";
  const d = new Date(value);
  return Number.isNaNaN(d.getTime()) ? value : d.toLocaleString([], { dateStyle:"medium", timeStyle:"short" });
}

function navigate(page) {
  $$(".page").forEach(el => el.classList.remove("active"));
  $(`#page-${page}`).classList.add("active");
  $$(".nav-item[data-page]").forEach(el => el.classList.toggle("active", el.dataset.page === page));
  $("#sidebar").classList.remove("open");
  if (page === "dashboard") loadDashboard();
  if (page === "farms") loadFarms();
  if (page === "monitoring") loadLatest();
  if (page === "history") loadHistory();
  if (page === "prediction") loadPredictionOptions();
  if (page === "alerts") loadAlerts();
  if (page === "devices") loadDevices();
  if (page === "settings") loadSettings();
}

async function checkAuth() {
  try {
    const data = await api("/api/auth/status");
    if (data.authenticated) showApp(data.user);
  } catch (_) {}
}

function showApp(user) {
  $("#loginScreen").classList.add("hidden");
  $("#appShell").classList.remove("hidden");
  $("#profileName").textContent = user.name;
  $("#profileRole").textContent = user.role === "admin" ? "Administrator" : "Farmer";
  $("#profileInitial").textContent = user.name.split(" ").map(w => w[0]).join("").slice(0,2).toUpperCase();
  const hour = new Date().getHours();
  $("#welcomeTitle").textContent = `${hour < 12 ? "Good morning" : hour < 18 ? "Good afternoon" : "Good evening"}, ${user.name.split(" ")[0]}`;
  $("#topbarDate").textContent = new Date().toLocaleDateString([], { weekday:"long", month:"long", day:"numeric", year:"numeric" });
  navigate("dashboard");
  clearInterval(autoRefresh);
  autoRefresh = setInterval(async () => {
    if ($("#page-monitoring").classList.contains("active")) await loadLatest();
  }, 20000);
}

async function loadDashboard() {
  try {
    const data = await api("/api/dashboard");
    $("#totalFarms").textContent = data.total_farms;
    $("#activeDevices").textContent = data.active_devices;
    $("#deviceStatusText").textContent = data.active_devices ? "Sensors connected" : "No active sensors";
    if (data.reading) {
      const r = data.reading;
      $("#dashMoisture").textContent = `${r.soil_moisture}%`;
      $("#dashTemperature").textContent = `${r.temperature}°C`;
      $("#dashHumidity").textContent = `${r.humidity}%`;
      $("#dashLight").textContent = `${Number(r.light_intensity).toLocaleString()} lux`;
      $("#moistureStatus").textContent = r.soil_moisture < 30 ? "Below threshold" : "Within range";
      $("#temperatureStatus").textContent = r.temperature > 35 ? "Above threshold" : "Within range";
      $("#dashConnection").textContent = data.active_devices ? "● Online" : "● Offline";
      $("#dashConnection").className = `status-pill ${data.active_devices ? "online" : "offline"}`;
    }
    $("#dashYield").textContent = data.latest_yield ? `${data.latest_yield.estimated_yield} tonnes` : "-- tonnes";
    const unread = data.alerts.filter(a => !a.is_read).length;
    $("#alertCount").textContent = unread;
    $("#alertCount").classList.toggle("zero", unread === 0);
    $("#topAlertDot").style.display = unread ? "block" : "none";
    $("#recentAlerts").innerHTML = data.alerts.length ? data.alerts.slice(0,4).map(a => `
      <div class="alert-row"><i class="alert-dot ${a.severity}"></i><div><strong>${escapeHtml(a.title)}</strong><p>${formatTime(a.created_at)}</p></div></div>`).join("") :
      `<div class="empty-state">No recent alerts</div>`;
  } catch (e) { toast(e.message, "error"); }
}

function escapeHtml(value) {
  const div = document.createElement("div");
  div.textContent = value ?? "";
  return div.innerHTML;
}

async function loadFarms() {
  try {
    const data = await api("/api/farms");
    $("#farmsGrid").innerHTML = data.farms.length ? data.farms.map(f => `
      <article class="farm-card">
        <div class="farm-card-top"><h2>${escapeHtml(f.name)}</h2><p>📍 ${escapeHtml(f.location)}</p></div>
        <div class="farm-card-body"><div class="farm-facts"><div><span>Area</span><strong>${f.area} ha</strong></div><div><span>Crop</span><strong>${escapeHtml(f.crop_type)}</strong></div></div>
        <div class="farm-actions"><button class="secondary-btn" onclick="openFarmModal(${f.id})">Edit</button><button class="danger-btn" onclick="deleteFarm(${f.id})">Delete</button></div></div>
      </article>`).join("") : `<div class="empty-state">No farms registered yet.</div>`;
  } catch (e) { toast(e.message, "error"); }
}

function openFarmModal(id = null) {
  $("#farmError").textContent = "";
  $("#farmId").value = id || "";
  $("#farmModalTitle").textContent = id ? "Edit farm" : "Add new farm";
  $("#saveFarmBtn").textContent = id ? "Update farm" : "Save farm";
  if (id) {
    api("/api/farms").then(data => {
      const farm = data.farms.find(f => f.id === id);
      if (farm) {
        $("#farmName").value = farm.name; $("#farmLocation").value = farm.location;
        $("#farmArea").value = farm.area; $("#farmCrop").value = farm.crop_type;
      }
      $("#farmModal").classList.remove("hidden");
    }).catch(e => toast(e.message, "error"));
  } else {
    $("#farmForm").reset(); $("#farmModal").classList.remove("hidden");
  }
}

function closeFarmModal() { $("#farmModal").classList.add("hidden"); }

async function deleteFarm(id) {
  if (!confirm("Delete this farm?")) return;
  setLoading(true);
  try { await api(`/api/farms/${id}`, { method:"DELETE" }); toast("Farm deleted."); await loadFarms(); }
  catch (e) { toast(e.message, "error"); } finally { setLoading(false); }
}

async function loadLatest() {
  try {
    const data = await api("/api/readings/latest");
    const r = data.reading;
    if (!r) return;
    const stamp = formatTime(r.recorded_at);
    ["moisture","temperature","humidity","light"].forEach(name => $(`#${name}Time`).textContent = `Last update ${stamp}`);
    $("#soilValue").innerHTML = `${r.soil_moisture}<small>%</small>`;
    $("#temperatureValue").innerHTML = `${r.temperature}<small>°C</small>`;
    $("#humidityValue").innerHTML = `${r.humidity}<small>%</small>`;
    $("#lightValue").innerHTML = `${Number(r.light_intensity).toLocaleString()}<small>lux</small>`;
    $("#soilProgress").style.width = `${r.soil_moisture}%`;
    $("#temperatureProgress").style.width = `${Math.min(r.temperature / 40 * 100, 100)}%`;
    $("#humidityProgress").style.width = `${r.humidity}%`;
    $("#lightProgress").style.width = `${Math.min(r.light_intensity / 5200 * 100, 100)}%`;
    $("#soilHint").textContent = r.soil_moisture < 30 ? "Abnormal — below configured threshold" : "Normal — moisture level is adequate";
    $("#temperatureHint").textContent = r.temperature > 35 ? "Abnormal — above configured threshold" : "Normal — temperature is within range";
    $("#humidityHint").textContent = r.humidity < 40 ? "Low humidity" : r.humidity > 85 ? "High humidity" : "Normal — humidity is within range";
    $("#lightHint").textContent = r.light_intensity < 500 ? "Low light intensity" : "Normal — adequate light detected";
    const online = data.device?.status === "online";
    ["moistureState","temperatureState","humidityState","lightState"].forEach(id => {
      $(`#${id}`).textContent = online ? "Online" : "Offline";
      $(`#${id}`).className = `status-pill ${online ? "online" : "offline"}`;
    });
  } catch (e) { toast(e.message, "error"); }
}

async function simulateReading() {
  setLoading(true);
  try {
    const data = await api("/api/readings/simulate", { method:"POST", body:"{}" });
    toast(data.message);
    await loadLatest();
  } catch (e) { toast(e.message, "error"); } finally { setLoading(false); }
}

function chartOptions(label, color) {
  return { responsive:true, maintainAspectRatio:false, plugins:{ legend:{ display:false } },
    scales:{ x:{ grid:{display:false}, ticks:{color:"#8a9890",font:{size:9},maxTicksLimit:8}},
      y:{ grid:{color:"#edf1ed"}, ticks:{color:"#8a9890",font:{size:9}}}} ,
    elements:{ line:{borderColor:color,borderWidth:2,tension:.35},point:{radius:0,hoverRadius:4,backgroundColor:color}}
  };
}

async function loadHistory() {
  try {
    const hours = $("#historyPeriod").value;
    const data = await api(`/api/readings/history?hours=${hours}`);
    const rows = data.readings;
    const labels = rows.map(r => new Date(r.recorded_at).toLocaleString([], {month:"short",day:"numeric",hour:"2-digit",minute:"2-digit"}));
    const series = [
      ["moistureChart","soil_moisture","#678fa3"],
      ["temperatureChart","temperature","#d18b51"],
      ["humidityChart","humidity","#6d9c7a"],
      ["lightChart","light_intensity","#c6a84f"],
    ];
    series.forEach(([id,key,color]) => {
      if (charts[id]) charts[id].destroy();
      charts[id] = new Chart($(`#${id}`), { type:"line", data:{labels,datasets:[{label:key,data:rows.map(r=>r[key]),borderColor:color,backgroundColor:color+"18",fill:true}]}, options:chartOptions(key,color) });
    });
  } catch (e) { toast(e.message, "error"); }
}

async function loadPredictionOptions() {
  try {
    const data = await api("/api/farms");
    const select = $("#predictFarm");
    select.innerHTML = data.farms.length ? data.farms.map(f=>`<option value="${f.id}" data-area="${f.area}" data-crop="${escapeHtml(f.crop_type)}">${escapeHtml(f.name)}</option>`).join("") : `<option value="">Add a farm first</option>`;
    if (data.farms.length) {
      const first = data.farms[0];
      $("#predictArea").value = first.area;
      $("#predictCrop").value = first.crop_type;
    }
  } catch (e) { toast(e.message, "error"); }
}

async function loadAlerts() {
  try {
    const data = await api("/api/alerts");
    $("#alertsList").innerHTML = data.alerts.length ? data.alerts.map(a => `
      <div class="full-alert ${a.is_read ? "" : "unread"}">
        <i class="alert-dot ${a.severity}"></i><div><h3>${escapeHtml(a.title)}</h3><p>${escapeHtml(a.message)}</p></div>
        <time>${formatTime(a.created_at)}</time>${a.is_read ? `<span class="status-pill">Read</span>` : `<button class="mark-read" onclick="markRead(${a.id})">Mark as read</button>`}
      </div>`).join("") : `<div class="empty-state">No alerts available.</div>`;
  } catch (e) { toast(e.message, "error"); }
}

async function markRead(id) {
  try { await api(`/api/alerts/${id}/read`, {method:"PUT",body:"{}"}); toast("Alert marked as read."); await loadAlerts(); await loadDashboard(); }
  catch (e) { toast(e.message, "error"); }
}

async function loadDevices() {
  try {
    const data = await api("/api/devices");
    $("#devicesTable").innerHTML = data.devices.length ? data.devices.map(d=>`
      <tr><td><strong>${escapeHtml(d.device_id)}</strong></td><td>${escapeHtml(d.name)}</td><td>${escapeHtml(d.farm_name || "Unassigned")}</td>
      <td><span class="status-pill ${d.status === "online" ? "online":"offline"}">${d.status === "online" ? "● Online":"● Offline"}</span></td>
      <td>${formatTime(d.last_communication)}</td><td><button class="device-toggle ${d.status}" onclick="toggleDevice(${d.id}, '${d.status === "online" ? "offline":"online"}')">${d.status === "online" ? "Set offline":"Set online"}</button></td></tr>`).join("") :
      `<tr><td colspan="6"><div class="empty-state">No devices registered.</div></td></tr>`;
  } catch (e) { toast(e.message, "error"); }
}

async function toggleDevice(id,status) {
  setLoading(true);
  try { const data = await api(`/api/devices/${id}/status`,{method:"PUT",body:JSON.stringify({status})}); toast(data.message); await loadDevices(); }
  catch (e) { toast(e.message,"error"); } finally { setLoading(false); }
}

async function loadSettings() {
  try {
    const data = await api("/api/settings");
    $("#profileNameInput").value = data.profile.name || "";
    $("#profileEmail").value = data.profile.email || "";
    $("#profilePhone").value = data.profile.phone || "";
    $("#profileLocation").value = data.profile.location || "";
    $("#moistureThreshold").value = data.settings.moisture_threshold;
    $("#temperatureThreshold").value = data.settings.temperature_threshold;
  } catch (e) { toast(e.message,"error"); }
}

$("#loginForm").addEventListener("submit", async e => {
  e.preventDefault();
  $("#loginError").textContent = "";
  setLoading(true);
  try {
    const data = await api("/api/login",{method:"POST",body:JSON.stringify({email:$("#email").value,password:$("#password").value})});
    toast(data.message); showApp(data.user);
  } catch (e) { $("#loginError").textContent = e.message; } finally { setLoading(false); }
});
$("#togglePassword").addEventListener("click",()=>{ const input=$("#password"); input.type=input.type==="password"?"text":"password"; $("#togglePassword").textContent=input.type==="password"?"Show":"Hide"; });
$$(".demo-credentials button").forEach(btn=>btn.addEventListener("click",()=>{$("#email").value=btn.dataset.email;$("#password").value=btn.dataset.password;}));
$$(".nav-item[data-page]").forEach(btn=>btn.addEventListener("click",()=>navigate(btn.dataset.page)));
$$("[data-nav]").forEach(btn=>btn.addEventListener("click",()=>navigate(btn.dataset.nav)));
$("#logoutBtn").addEventListener("click",async()=>{try{await api("/api/logout",{method:"POST",body:"{}"});clearInterval(autoRefresh);$("#appShell").classList.add("hidden");$("#loginScreen").classList.remove("hidden");$("#password").value="";}catch(e){toast(e.message,"error");}});
$("#menuBtn").addEventListener("click",()=>$("#sidebar").classList.toggle("open"));
$("#topAlertBtn").addEventListener("click",()=>navigate("alerts"));
$("#addFarmBtn").addEventListener("click",()=>openFarmModal());
$("#closeFarmModal").addEventListener("click",closeFarmModal);
$("#cancelFarmModal").addEventListener("click",closeFarmModal);
$("#simulateBtn").addEventListener("click",simulateReading);
$("#historyPeriod").addEventListener("change",loadHistory);
$("#predictFarm").addEventListener("change",()=>{
  const option=$("#predictFarm").selectedOptions[0];
  if(option?.dataset.area)$("#predictArea").value=option.dataset.area;
  if(option?.dataset.crop)$("#predictCrop").value=option.dataset.crop;
});

$("#farmForm").addEventListener("submit",async e=>{
  e.preventDefault(); $("#farmError").textContent="";
  const id=$("#farmId").value;
  const payload={name:$("#farmName").value.trim(),location:$("#farmLocation").value.trim(),area:$("#farmArea").value,crop_type:$("#farmCrop").value};
  if(!payload.name||!payload.location||!payload.area||!payload.crop_type){$("#farmError").textContent="Complete all farm fields.";return;}
  setLoading(true);
  try {const data=await api(id?`/api/farms/${id}`:"/api/farms",{method:id?"PUT":"POST",body:JSON.stringify(payload)});toast(data.message);closeFarmModal();await loadFarms();}
  catch(err){$("#farmError").textContent=err.message;}finally{setLoading(false);}
});

$("#predictionForm").addEventListener("submit",async e=>{
  e.preventDefault();$("#predictionError").textContent="";
  const payload={farm_id:$("#predictFarm").value,crop_type:$("#predictCrop").value,area:$("#predictArea").value,soil_moisture:$("#predictSoil").value,temperature:$("#predictTemperature").value,humidity:$("#predictHumidity").value};
  if(!payload.farm_id||!payload.crop_type||!payload.area||payload.soil_moisture===""||payload.temperature===""||payload.humidity===""){$("#predictionError").textContent="Complete all prediction fields.";return;}
  const btn=$("#predictBtn");btn.disabled=true;btn.textContent="Generating estimate...";
  try {const data=await api("/api/predict",{method:"POST",body:JSON.stringify(payload)});$("#predictionValue").textContent=`${data.estimated_yield} ${data.unit}`;$("#predictionTimestamp").textContent=`Generated ${formatTime(data.timestamp)} · Sample result`;toast(data.message);}
  catch(err){$("#predictionError").textContent=err.message;}finally{btn.disabled=false;btn.textContent="Predict yield";}
});

$("#settingsForm").addEventListener("submit",async e=>{
  e.preventDefault();$("#settingsError").textContent="";
  const payload={name:$("#profileNameInput").value,phone:$("#profilePhone").value,location:$("#profileLocation").value,moisture_threshold:$("#moistureThreshold").value,temperature_threshold:$("#temperatureThreshold").value};
  setLoading(true);
  try{const data=await api("/api/settings",{method:"PUT",body:JSON.stringify(payload)});toast(data.message);await loadSettings();}
  catch(err){$("#settingsError").textContent=err.message;}finally{setLoading(false);}
});

window.openFarmModal=openFarmModal;
window.deleteFarm=deleteFarm;
window.markRead=markRead;
window.toggleDevice=toggleDevice;
checkAuth();
