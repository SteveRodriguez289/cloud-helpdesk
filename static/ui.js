// ---------- Auth storage ----------
function getApiKey(){ return localStorage.getItem("apiKey") || ""; }
function getName(){ return localStorage.getItem("name") || "User"; }

// ---------- Dark mode ----------
function applyTheme(){
  const dark = localStorage.getItem("darkMode")==="1";
  document.body.classList.toggle("dark", dark);
}
function toggleDark(){
  const dark = localStorage.getItem("darkMode")==="1";
  localStorage.setItem("darkMode", dark ? "0" : "1");
  applyTheme();
}

// ---------- Login / Logout ----------
async function doLogin(){
  const name = (document.getElementById("loginName").value || "").trim() || "User";
  const key  = (document.getElementById("loginKey").value || "").trim();
  const msg = document.getElementById("loginMsg");
  msg.className = "hint";
  msg.textContent = "";

  if(!key){
    msg.textContent = "Please enter an API key.";
    msg.className = "hint error";
    return;
  }

  // quick validation: try GET /tickets with header
  try{
    const res = await fetch("/tickets", { headers: { "X-API-KEY": key }});
    if(!res.ok){
      const j = await safeJson(res);
      msg.textContent = (j && j.error) ? j.error : ("Login failed: " + res.status);
      msg.className = "hint error";
      return;
    }
    localStorage.setItem("apiKey", key);
    localStorage.setItem("name", name);
    showApp();
    await loadTickets();
  }catch(e){
    msg.textContent = "Could not reach server.";
    msg.className = "hint error";
  }
}

function logout(){
  localStorage.removeItem("apiKey");
  showLogin();
}

function showLogin(){
  document.getElementById("appShell").style.display="none";
  document.getElementById("loginScreen").style.display="grid";
  document.getElementById("loginKey").value = "";
  document.getElementById("loginName").value = getName();
}

function showApp(){
  document.getElementById("loginScreen").style.display="none";
  document.getElementById("appShell").style.display="grid";
  document.getElementById("profileName").textContent = getName();
  document.getElementById("avatar").textContent = (getName().slice(0,1) || "U").toUpperCase();
  document.getElementById("setName").value = getName();
}

function saveSettings(){
  const n = (document.getElementById("setName").value || "").trim() || "User";
  const k = (document.getElementById("setKey").value || "").trim();
  localStorage.setItem("name", n);
  if(k) localStorage.setItem("apiKey", k);
  document.getElementById("settingsMsg").textContent = "Saved.";
  showApp();
}

// ---------- Sidebar toggle (mobile) ----------
function toggleSidebar(){
  document.getElementById("sidebar").classList.toggle("open");
}

// ---------- Navigation ----------
function navTo(e){
  e.preventDefault();
  const link = e.currentTarget;
  const sec = link.getAttribute("data-section");
  document.querySelectorAll(".nav a").forEach(a => a.classList.remove("active"));
  link.classList.add("active");

  document.querySelectorAll(".section").forEach(s => s.classList.remove("active"));
  document.getElementById("sec-" + sec).classList.add("active");

  const titleMap = {
    dashboard: ["Dashboard", "Overview + quick actions"],
    tickets: ["Tickets", "Filter, search, and manage"],
    reports: ["Reports", "Charts + trends (next)"],
    settings: ["Settings", "Profile + API key"]
  };
  document.getElementById("pageTitle").textContent = titleMap[sec][0];
  document.getElementById("pageSub").textContent = titleMap[sec][1];

  if(window.innerWidth <= 980){
    document.getElementById("sidebar").classList.remove("open");
  }
}

// ---------- Modal ----------
function openModal(){
  document.getElementById("createMsg").textContent = "";
  document.getElementById("overlay").classList.add("show");
  document.getElementById("tTitle").focus();
}
function closeModal(){
  document.getElementById("overlay").classList.remove("show");
}

// ---------- Helpers ----------
async function safeJson(res){
  try{ return await res.json(); }catch{ return null; }
}
function priorityClass(p){
  if(p==="High") return "prio-high";
  if(p==="Medium") return "prio-med";
  return "prio-low";
}
function statusClass(s){
  if(s==="Closed") return "status-closed";
  if(s==="Pending") return "status-pending";
  return "status-open";
}
function fmtDate(dt){
  try{ return new Date(dt).toLocaleString(); }catch{ return dt; }
}

function escapeHtml(s){
  return String(s||"")
    .replaceAll("&","&amp;")
    .replaceAll("<","&lt;")
    .replaceAll(">","&gt;")
    .replaceAll('"',"&quot;")
    .replaceAll("'","&#039;");
}

// ---------- API ----------
async function apiFetch(path, opts={}){
  const key = getApiKey();
  opts.headers = opts.headers || {};
  opts.headers["X-API-KEY"] = key;
  return fetch(path, opts);
}

// ---------- Data ----------
let allTickets = [];
let chartRef = null;

async function loadTickets(){
  const msg = document.getElementById("apiMsg");
  if(msg){ msg.textContent = "Loading..."; msg.className="muted"; }

  try{
    const res = await apiFetch("/tickets");
    const data = await safeJson(res);

    if(!res.ok){
      const err = data && data.error ? data.error : ("Error " + res.status);
      if(msg){ msg.textContent = err; msg.className="muted error"; }
      return;
    }

    allTickets = Array.isArray(data) ? data : [];
    if(msg){ msg.textContent = "Loaded " + allTickets.length + " tickets."; msg.className="muted ok"; }
    const last = document.getElementById("lastLoad");
    if(last) last.textContent = "Last refreshed: " + new Date().toLocaleTimeString();

    updateStats();
    renderTickets();
    renderDashboardTable();
    renderChart();

  }catch(e){
    if(msg){ msg.textContent = "Network error."; msg.className="muted error"; }
  }
}

function updateStats(){
  const total = allTickets.length;
  let open=0, closed=0, pending=0;
  allTickets.forEach(t=>{
    if(t.status==="Closed") closed++;
    else if(t.status==="Pending") pending++;
    else open++;
  });

  document.getElementById("totalTickets").textContent = total;
  document.getElementById("openTickets").textContent = open;
  document.getElementById("closedTickets").textContent = closed;
  document.getElementById("pendingTickets").textContent = pending;

  document.getElementById("pillTotal").textContent = total;
  document.getElementById("pillOpen").textContent = open;
}

function getTicketPriority(t){
  return t.priority || "Medium";
}
function getTicketAssigned(t){
  return t.assigned_to || t.assigned || "—";
}

function renderDashboardTable(){
  const body = document.getElementById("dashRows");
  body.innerHTML = "";
  const items = allTickets.slice(0, 8);
  items.forEach(t=>{
    const pr = getTicketPriority(t);
    const as = getTicketAssigned(t);
    body.insertAdjacentHTML("beforeend", `
      <tr>
        <td>${t.id}</td>
        <td><b>${escapeHtml(t.title)}</b><div class="muted">${escapeHtml((t.description||"").slice(0,50))}${(t.description||"").length>50?"...":""}</div></td>
        <td><span class="chip ${statusClass(t.status)}"><span class="dot"></span>${t.status}</span></td>
        <td><span class="chip ${priorityClass(pr)}">${pr}</span></td>
        <td>${escapeHtml(as)}</td>
        <td>${fmtDate(t.created_at)}</td>
        <td class="muted">—</td>
      </tr>
    `);
  });
}

function renderTickets(){
  const status = document.getElementById("filterStatus").value;
  const prio   = document.getElementById("filterPriority").value;
  const q      = (document.getElementById("searchBox").value || "").toLowerCase();

  const filtered = allTickets.filter(t=>{
    const p = getTicketPriority(t);
    if(status !== "all" && t.status !== status) return false;
    if(prio !== "all" && p !== prio) return false;
    if(q){
      const hay = (t.title||"") + " " + (t.description||"");
      if(!hay.toLowerCase().includes(q)) return false;
    }
    return true;
  });

  const body = document.getElementById("ticketRows");
  body.innerHTML = "";
  filtered.forEach(t=>{
    const pr = getTicketPriority(t);
    const as = getTicketAssigned(t);
    body.insertAdjacentHTML("beforeend", `
      <tr class="fade-in">
        <td>${t.id}</td>
        <td><b>${escapeHtml(t.title)}</b><div class="muted">${escapeHtml((t.description||"").slice(0,60))}${(t.description||"").length>60?"...":""}</div></td>
        <td><span class="chip ${statusClass(t.status)}"><span class="dot"></span>${t.status}</span></td>
        <td><span class="chip ${priorityClass(pr)}">${pr}</span></td>
        <td>${escapeHtml(as)}</td>
        <td>${fmtDate(t.created_at)}</td>
        <td class="muted">—</td>
      </tr>
    `);
  });
}

function renderChart(){
  let open=0, closed=0, pending=0;
  allTickets.forEach(t=>{
    if(t.status==="Closed") closed++;
    else if(t.status==="Pending") pending++;
    else open++;
  });

  const ctx = document.getElementById("ticketChart");

  if(chartRef) chartRef.destroy();
  chartRef = new Chart(ctx, {
    type: "doughnut",
    data: {
      labels: ["Open", "Closed", "Pending"],
      datasets: [{
        data: [open, closed, pending],
        backgroundColor: ["#3b82f6","#10b981","#f59e0b"]
      }]
    },
    options:{
      responsive:true,
      maintainAspectRatio:false,
      plugins:{ legend:{ position:"bottom" } },
      cutout:"68%"
    }
  });
}

async function createTicket(){
  const title = (document.getElementById("tTitle").value||"").trim();
  const description = (document.getElementById("tDesc").value||"").trim();
  const priority = document.getElementById("tPriority").value;
  const assigned_to = (document.getElementById("tAssigned").value||"").trim();

  const msg = document.getElementById("createMsg");
  msg.className="hint";
  msg.textContent="";

  if(!title || !description){
    msg.textContent="Title and description required.";
    msg.className="hint error";
    return;
  }

  const payload = { title, description, priority, assigned_to };

  try{
    const res = await apiFetch("/tickets", {
      method:"POST",
      headers:{ "Content-Type":"application/json" },
      body: JSON.stringify(payload)
    });
    const data = await safeJson(res);

    if(!res.ok){
      msg.textContent = (data && data.error) ? data.error : ("Error " + res.status);
      msg.className="hint error";
      return;
    }

    msg.textContent="Ticket created.";
    msg.className="hint ok";

    document.getElementById("tTitle").value="";
    document.getElementById("tDesc").value="";
    document.getElementById("tAssigned").value="";
    document.getElementById("tPriority").value="Medium";

    closeModal();
    await loadTickets();

  }catch(e){
    msg.textContent="Network error.";
    msg.className="hint error";
  }
}

// ---------- Boot ----------
applyTheme();
if(getApiKey()){
  showApp();
  loadTickets();
}else{
  showLogin();
}