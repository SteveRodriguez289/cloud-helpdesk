async function login() {
  const apiKey = document.getElementById("apiKey").value.trim();

  const res = await fetch("/login", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ api_key: apiKey })
  });

  const data = await res.json();
  document.getElementById("loginMsg").textContent = JSON.stringify(data);

  if (res.ok) {
    // cookie is set by server (httponly), so browser requests will work now
    await loadTickets();
  }
}

async function loadTickets() {
  const res = await fetch("/tickets");
  const data = await res.json();
  document.getElementById("tickets").textContent = JSON.stringify(data, null, 2);
}

async function createTicket() {
  const title = document.getElementById("title").value.trim();
  const description = document.getElementById("desc").value.trim();

  const res = await fetch("/tickets", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ title, description })
  });

  const data = await res.json();
  document.getElementById("createMsg").textContent = JSON.stringify(data);

  if (res.ok) {
    document.getElementById("title").value = "";
    document.getElementById("desc").value = "";
    await loadTickets();
  }
}

document.getElementById("loginBtn").addEventListener("click", login);
document.getElementById("refreshBtn").addEventListener("click", loadTickets);
document.getElementById("createBtn").addEventListener("click", createTicket);

loadTickets();
