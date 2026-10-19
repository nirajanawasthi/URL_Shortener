from django.http import HttpResponse

PAGE = r"""<!doctype html>
<html lang="en">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>Shortly - URL Shortener</title>
<style>
  :root { --bg:#0f172a; --card:#1e293b; --line:#334155; --text:#e2e8f0; --muted:#94a3b8; --accent:#38bdf8; --ok:#4ade80; --err:#f87171; }
  * { box-sizing: border-box; }
  body { margin:0; font-family: system-ui, -apple-system, Segoe UI, Roboto, sans-serif; background:var(--bg); color:var(--text); min-height:100vh; }
  main { max-width: 860px; margin: 0 auto; padding: 40px 16px 64px; }
  h1 { font-size: 2rem; margin: 0 0 4px; }
  h1 span { color: var(--accent); }
  .sub { color: var(--muted); margin: 0 0 28px; }
  .card { background: var(--card); border: 1px solid var(--line); border-radius: 14px; padding: 20px; margin-bottom: 20px; }
  .card h2 { margin: 0 0 14px; font-size: 1.05rem; }
  label { display:block; font-size:.85rem; color:var(--muted); margin: 0 0 4px; }
  input { width:100%; padding: 11px 12px; border-radius: 9px; border: 1px solid var(--line); background:#0b1220; color:var(--text); font-size: 1rem; }
  input:focus { outline: 2px solid var(--accent); border-color: transparent; }
  .row { display:flex; gap:12px; flex-wrap:wrap; }
  .row > div { flex:1 1 220px; }
  .grow { flex: 3 1 340px !important; }
  button { cursor:pointer; border:0; border-radius:9px; padding: 11px 18px; font-size: 1rem; font-weight:600; background: var(--accent); color:#04263a; }
  button.ghost { background: transparent; color: var(--text); border: 1px solid var(--line); }
  button:disabled { opacity:.6; cursor:wait; }
  .actions { display:flex; gap:10px; margin-top: 14px; flex-wrap:wrap; }
  .msg { margin-top: 12px; min-height: 1.2em; font-size:.92rem; }
  .msg.err { color: var(--err); } .msg.ok { color: var(--ok); }
  .result { display:none; margin-top:16px; padding:14px; border:1px dashed var(--accent); border-radius:10px; }
  .result a { color: var(--accent); font-size: 1.15rem; font-weight:600; word-break: break-all; }
  .result .line { display:flex; gap:10px; align-items:center; flex-wrap:wrap; }
  table { width:100%; border-collapse: collapse; font-size:.92rem; }
  th, td { text-align:left; padding: 9px 8px; border-bottom: 1px solid var(--line); vertical-align: top; }
  th { color: var(--muted); font-weight:500; }
  td.orig { max-width: 300px; overflow:hidden; text-overflow: ellipsis; white-space: nowrap; color: var(--muted); }
  td a { color: var(--accent); text-decoration: none; }
  td.clicks { font-weight:700; font-variant-numeric: tabular-nums; }
  .top { display:flex; justify-content: space-between; align-items:center; gap:12px; flex-wrap:wrap; }
  .who { color: var(--muted); font-size:.9rem; }
  .hide { display:none; }
  .empty { color: var(--muted); padding: 8px 0; }
</style>
</head>
<body>
<main>
  <div class="top">
    <div>
      <h1>Short<span>ly</span></h1>
      <p class="sub">Paste a long link. Get a short one.</p>
    </div>
    <div id="who" class="who hide"><span id="whoName"></span> &middot; <a href="#" id="logout" style="color:var(--accent)">Log out</a></div>
  </div>

  <!-- Login / Register -->
  <section id="authCard" class="card">
    <h2>Sign in to create links</h2>
    <div class="row">
      <div><label for="username">Username</label><input id="username" autocomplete="username"></div>
      <div><label for="password">Password</label><input id="password" type="password" autocomplete="current-password"></div>
    </div>
    <div class="actions">
      <button id="loginBtn">Log in</button>
      <button id="registerBtn" class="ghost">Register</button>
    </div>
    <div id="authMsg" class="msg"></div>
  </section>

  <!-- Shorten -->
  <section id="appCard" class="hide">
    <div class="card">
      <h2>Shorten a URL</h2>
      <form id="shortenForm">
        <div class="row">
          <div class="grow"><label for="longUrl">Long URL</label><input id="longUrl" type="url" placeholder="https://example.com/some/very/long/path" required></div>
          <div><label for="alias">Custom alias (optional)</label><input id="alias" placeholder="my-link" maxlength="32"></div>
        </div>
        <div class="actions"><button id="shortenBtn" type="submit">Shorten</button></div>
        <div id="shortenMsg" class="msg"></div>
      </form>
      <div id="result" class="result">
        <div style="color:var(--muted);font-size:.85rem;margin-bottom:6px">Your short link</div>
        <div class="line">
          <a id="resultLink" href="#" target="_blank" rel="noopener"></a>
          <button id="copyBtn" class="ghost" type="button">Copy</button>
        </div>
      </div>
    </div>

    <div class="card">
      <div class="top"><h2>Your links</h2><button id="refreshBtn" class="ghost" type="button">Refresh</button></div>
      <div id="linksWrap"></div>
    </div>
  </section>
</main>

<script>
const $ = (id) => document.getElementById(id);
let token = null;
let pollTimer = null;
try { token = sessionStorage.getItem("access"); } catch (e) {}
try { var savedName = sessionStorage.getItem("name"); } catch (e) { var savedName = null; }

function flat(data) {
  if (typeof data === "string") return data;
  if (Array.isArray(data)) return data.map(flat).join(" ");
  if (data && typeof data === "object") {
    return Object.entries(data).map(([k, v]) => (k === "detail" || k === "non_field_errors" ? "" : k + ": ") + flat(v)).join(" ");
  }
  return String(data);
}

async function api(path, opts = {}) {
  const headers = Object.assign({ "Content-Type": "application/json" }, opts.headers || {});
  if (token) headers["Authorization"] = "Bearer " + token;
  const res = await fetch(path, Object.assign({}, opts, { headers }));
  let data = null;
  try { data = await res.json(); } catch (e) {}
  return { ok: res.ok, status: res.status, data };
}

function setMsg(el, text, kind) { el.textContent = text || ""; el.className = "msg" + (kind ? " " + kind : ""); }

function showApp(name) {
  $("authCard").classList.add("hide");
  $("appCard").classList.remove("hide");
  $("who").classList.remove("hide");
  $("whoName").textContent = name;
  loadLinks();
  clearInterval(pollTimer);
  pollTimer = setInterval(loadLinks, 4000);   // live click counts
}

function showAuth(message) {
  token = null;
  try { sessionStorage.removeItem("access"); sessionStorage.removeItem("name"); } catch (e) {}
  clearInterval(pollTimer);
  $("appCard").classList.add("hide");
  $("who").classList.add("hide");
  $("authCard").classList.remove("hide");
  setMsg($("authMsg"), message || "", message ? "err" : "");
}

async function login(username, password) {
  const r = await api("/api/auth/token/", { method: "POST", body: JSON.stringify({ username, password }) });
  if (!r.ok) { setMsg($("authMsg"), flat(r.data) || "Login failed.", "err"); return; }
  token = r.data.access;
  try { sessionStorage.setItem("access", token); sessionStorage.setItem("name", username); } catch (e) {}
  setMsg($("authMsg"), "");
  showApp(username);
}

$("loginBtn").onclick = () => login($("username").value.trim(), $("password").value);

$("registerBtn").onclick = async () => {
  const username = $("username").value.trim(), password = $("password").value;
  const r = await api("/api/auth/register/", { method: "POST", body: JSON.stringify({ username, password }) });
  if (!r.ok) { setMsg($("authMsg"), flat(r.data) || "Registration failed.", "err"); return; }
  await login(username, password);
};

$("logout").onclick = (e) => { e.preventDefault(); showAuth(); };

$("shortenForm").onsubmit = async (e) => {
  e.preventDefault();
  const body = { original_url: $("longUrl").value.trim() };
  const alias = $("alias").value.trim();
  if (alias) body.custom_alias = alias;
  $("shortenBtn").disabled = true;
  const r = await api("/api/urls/", { method: "POST", body: JSON.stringify(body) });
  $("shortenBtn").disabled = false;
  if (r.status === 401) { showAuth("Session expired, please log in again."); return; }
  if (!r.ok) { $("result").style.display = "none"; setMsg($("shortenMsg"), flat(r.data) || "Could not create link.", "err"); return; }
  setMsg($("shortenMsg"), "Link created!", "ok");
  $("resultLink").href = r.data.short_url;
  $("resultLink").textContent = r.data.short_url;
  $("result").style.display = "block";
  $("copyBtn").textContent = "Copy";
  $("longUrl").value = ""; $("alias").value = "";
  loadLinks();
};

$("copyBtn").onclick = async () => {
  try { await navigator.clipboard.writeText($("resultLink").textContent); $("copyBtn").textContent = "Copied!"; }
  catch (e) { $("copyBtn").textContent = "Press Ctrl+C"; }
};

$("refreshBtn").onclick = loadLinks;

async function loadLinks() {
  const r = await api("/api/urls/");
  if (r.status === 401) { showAuth("Session expired, please log in again."); return; }
  if (!r.ok) return;
  const items = r.data.results || [];
  const wrap = $("linksWrap");
  wrap.textContent = "";
  if (!items.length) { const d = document.createElement("div"); d.className = "empty"; d.textContent = "No links yet. Create your first one above."; wrap.appendChild(d); return; }
  const table = document.createElement("table");
  const head = table.createTHead().insertRow();
  ["Short link", "Original URL", "Clicks", "Created"].forEach((t) => { const th = document.createElement("th"); th.textContent = t; head.appendChild(th); });
  const body = table.createTBody();
  items.forEach((it) => {
    const tr = body.insertRow();
    const c1 = tr.insertCell(); const a = document.createElement("a");
    a.href = it.short_url; a.target = "_blank"; a.rel = "noopener"; a.textContent = it.short_url; c1.appendChild(a);
    const c2 = tr.insertCell(); c2.className = "orig"; c2.textContent = it.original_url; c2.title = it.original_url;
    const c3 = tr.insertCell(); c3.className = "clicks"; c3.textContent = it.click_count;
    const c4 = tr.insertCell(); c4.textContent = new Date(it.created_at).toLocaleString();
  });
  wrap.appendChild(table);
}

if (token) showApp(savedName || "you");
</script>
</body>
</html>
"""


def home(request):
    return HttpResponse(PAGE)