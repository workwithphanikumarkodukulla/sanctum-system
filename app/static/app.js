const state = { screen: "overview", thread: [], history: [], activeFile: "", activeContent: "", sending: false, openFiles: [], bottomPanel: "terminal" };
const $ = (id) => document.getElementById(id);
const escapeHtml = (value) => { const node = document.createElement("div"); node.textContent = value ?? ""; return node.innerHTML; };

function enhanceIdeShell() {
    document.body.insertAdjacentHTML("beforeend", `<div class="command-palette" id="commandPalette" role="dialog" aria-modal="true" aria-label="Command palette" hidden>
        <div class="command-palette-box"><div class="command-input-row"><span class="material-icons">search</span><input id="commandInput" autocomplete="off" placeholder="Search files, commands, agents..." aria-label="Search commands"></div>
        <div class="command-results" id="commandResults"></div></div></div>`);
    const nav = document.querySelector(".main-nav");
    const topbar = document.querySelector(".topbar");
    const topbarRight = document.querySelector(".topbar-right");
    const workspaceControls = document.querySelector(".sidebar-bottom");
    const sidebar = document.querySelector(".sidebar");
    if (nav && sidebar) {
        nav.hidden = false;
        nav.classList.add("activity-bar-nav");
        const activityBar = document.createElement("aside");
        activityBar.className = "activity-rail";
        activityBar.setAttribute("aria-label", "Activity bar");
        activityBar.innerHTML = `<div class="activity-rail-logo">S</div><div class="activity-rail-title">SANCTUM</div>`;
        activityBar.appendChild(nav);
        document.querySelector(".app-window")?.insertBefore(activityBar, sidebar);
    }
    if (workspaceControls && topbar && topbarRight) {
        workspaceControls.classList.add("topbar-workspace");
        topbar.insertBefore(workspaceControls, topbarRight);
    }
    document.querySelector(".sidebar")?.setAttribute("hidden", "hidden");
    document.querySelectorAll(".nav-item").forEach((item) => {
        const icon = item.querySelector(".nav-icon");
        const label = item.textContent.replace(icon?.textContent || "", "").trim();
        item.setAttribute("aria-label", label);
        item.dataset.tooltip = label;
    });
    document.querySelector(".topbar")?.insertAdjacentHTML("afterbegin", `<button class="brand-compact" data-screen-target="overview" aria-label="Open overview"><span class="brand-mark">S</span><span>SANCTUM</span></button>`);
    document.querySelector(".brand-compact")?.addEventListener("click", () => showScreen("overview"));
    document.querySelector(".topbar-right")?.insertAdjacentHTML("afterbegin", `<button class="command-trigger" id="commandTrigger" aria-label="Open command palette"><span class="material-icons">search</span><span>Search files, commands...</span><kbd>Ctrl K</kbd></button>`);
    document.querySelectorAll(".screen-heading").forEach((heading) => heading.classList.add("ide-heading"));
    document.querySelectorAll(".code-panel").forEach((panel) => panel.insertAdjacentHTML("afterbegin", `<div class="editor-tabs" id="editorTabs"><button class="editor-tab active"><span class="material-icons">description</span><span>Workspace</span></button></div>`));
    document.querySelector(".app-window")?.insertAdjacentHTML("beforeend", `<div class="statusbar"><span><i class="status-dot"></i> LOCAL</span><span id="statusWorkspace">WORKSPACE READY</span><span class="status-spacer"></span><span id="statusModel">MODEL CONNECTING</span><span>UTF-8</span><span>Ln 1, Col 1</span></div>`);

    const commands = [
        ["SANCTUM: Start Agent", "agent"], ["SANCTUM: Open Workspace", "workspace"], ["SANCTUM: Select Model", "models"],
        ["SANCTUM: Manage Tools", "tools"], ["SANCTUM: Run Security Audit", "security"], ["SANCTUM: Open Overview", "overview"]
    ];
    const renderCommands = (query = "") => { const filtered = commands.filter(([label]) => label.toLowerCase().includes(query.toLowerCase())); $("commandResults").innerHTML = filtered.map(([label, screen]) => `<button class="command-result" data-command-screen="${screen}"><span class="material-icons">${screen === "agent" ? "auto_awesome" : "arrow_forward"}</span>${label}<kbd>Enter</kbd></button>`).join("") || `<div class="command-empty">No matching commands</div>`; };
    const closePalette = () => { $("commandPalette").hidden = true; $("commandInput").value = ""; };
    const openPalette = () => { $("commandPalette").hidden = false; renderCommands(); $("commandInput").focus(); };
    $("commandTrigger")?.addEventListener("click", openPalette);
    $("commandPalette")?.addEventListener("click", (event) => { if (event.target.id === "commandPalette") closePalette(); const action = event.target.closest("[data-command-screen]"); if (action) { showScreen(action.dataset.commandScreen); closePalette(); } });
    $("commandInput")?.addEventListener("input", (event) => renderCommands(event.target.value));
    document.addEventListener("keydown", (event) => { if ((event.ctrlKey || event.metaKey) && event.key.toLowerCase() === "k") { event.preventDefault(); openPalette(); } if (event.key === "Escape" && !$("commandPalette").hidden) closePalette(); });
}

async function api(path, options = {}) {
    const response = await fetch(path, { headers: { "Content-Type": "application/json" }, ...options });
    const data = await response.json().catch(() => ({}));
    if (!response.ok) throw new Error(data.error || `Request failed (${response.status})`);
    return data;
}

function showScreen(name) {
    state.screen = name;
    document.querySelectorAll(".screen").forEach((screen) => screen.classList.toggle("active", screen.id === `screen-${name}`));
    document.querySelectorAll(".nav-item").forEach((item) => item.classList.toggle("active", item.dataset.screen === name));
    $("screenTitle").textContent = name[0].toUpperCase() + name.slice(1);
    if (name === "workspace") loadWorkspace();
    if (name === "models") loadModels();
    if (name === "tools") loadTools();
    if (name === "security") loadRuntime();
    document.body.dataset.screen = name;
}

document.querySelectorAll("[data-screen], [data-screen-target]").forEach((item) => item.addEventListener("click", () => showScreen(item.dataset.screen || item.dataset.screenTarget)));

function renderTree(nodes, parent) {
    parent.innerHTML = "";
    if (!nodes.length) { parent.innerHTML = '<div class="empty-state">No files in this workspace.</div>'; return; }
    nodes.forEach((node) => {
        const row = document.createElement("button");
        row.className = `tree-row ${node.type === "directory" ? "directory" : "file"}`;
        row.innerHTML = `<span class="tree-symbol">${node.type === "directory" ? "▸" : "◻"}</span><span>${escapeHtml(node.name)}</span>`;
        if (node.type === "directory") {
            const children = document.createElement("div"); children.className = "tree-children";
            row.addEventListener("click", () => { row.classList.toggle("expanded"); children.classList.toggle("expanded"); });
            parent.append(row, children); renderTree(node.children || [], children);
        } else {
            row.addEventListener("click", () => openFile(node.path)); parent.appendChild(row);
        }
    });
}

async function loadWorkspace() {
    try {
        const data = await api("/api/workspace/tree");
        $("workspaceName").textContent = (data.path || "workspace").split(/[\\/]/).pop();
        $("overviewFiles").textContent = data.files.length;
        $("fileCountLabel").textContent = `${data.files.length} file${data.files.length === 1 ? "" : "s"}`;
        renderTree(data.tree || [], $("workspaceTree"));
    } catch (error) { $("workspaceTree").innerHTML = `<div class="empty-state error">${escapeHtml(error.message)}</div>`; }
}

async function selectWorkspace(path) {
    const selected = await api("/api/workspace/select", { method: "POST", body: JSON.stringify({ path }) });
    localStorage.setItem("sanctum-workspace", selected.path);
    $("workspacePathInput").value = selected.path;
    await loadWorkspace();
    await loadRuntime();
}

async function pickWorkspace() {
    const selected = await api("/api/workspace/pick", { method: "POST" });
    if (selected.cancelled) return;
    localStorage.setItem("sanctum-workspace", selected.path);
    $("workspacePathInput").value = selected.path;
    await loadWorkspace();
    await loadRuntime();
}

async function openFile(path) {
    state.activeFile = path; if (!state.openFiles.includes(path)) state.openFiles.push(path); $("filePathDisplay").textContent = path; $("fileMeta").textContent = "Loading..."; renderEditorTabs();
    try { const data = await api(`/api/workspace/file?path=${encodeURIComponent(path)}`); state.activeContent = data.content || ""; $("codeView").textContent = state.activeContent; $("fileMeta").textContent = `${(data.stat?.size || 0).toLocaleString()} bytes`; }
    catch (error) { $("codeView").textContent = error.message; $("fileMeta").textContent = "Error"; }
}

function renderEditorTabs() {
    const tabs = $("editorTabs"); if (!tabs) return;
    tabs.innerHTML = state.openFiles.length ? state.openFiles.map((path) => `<button class="editor-tab ${path === state.activeFile ? "active" : ""}" data-file-tab="${escapeHtml(path)}"><span class="material-icons">description</span><span>${escapeHtml(path.split(/[\\/]/).pop())}</span><span class="tab-close">×</span></button>`).join("") : `<button class="editor-tab active"><span class="material-icons">description</span><span>Workspace</span></button>`;
    tabs.querySelectorAll("[data-file-tab]").forEach((tab) => tab.addEventListener("click", (event) => { if (event.target.closest(".tab-close")) { state.openFiles = state.openFiles.filter((file) => file !== tab.dataset.fileTab); renderEditorTabs(); return; } openFile(tab.dataset.fileTab); }));
}

async function loadRuntime() {
    try {
        const data = await api("/api/system"); const model = data.model;
        $("topbarModel").textContent = model.model; $("statusModel") && ($("statusModel").textContent = model.model); $("topbarStatus").textContent = data.local_inference ? "Local runtime" : "Review runtime";
        $("agentModelLabel").textContent = `${model.model} · ${data.mcp.name}`;
        $("overviewEndpoint").textContent = model.base_url; $("overviewMcp").textContent = data.mcp.name;
        $("securityEndpoint").textContent = model.base_url; $("securityNetwork").textContent = model.network_scope; $("securityTransport").textContent = data.mcp.transport; $("securityProtocol").textContent = data.mcp.protocol_version; $("securityStatus").textContent = data.external_api ? "External API detected" : "Local-only inference confirmed";
        $("overviewModels").textContent = data.available_models.length;
    } catch (error) { $("topbarStatus").textContent = "Runtime unavailable"; $("securityStatus").textContent = error.message; }
}

async function loadModels() {
    try {
        const data = await api("/api/models"); $("overviewModels").textContent = data.models.length;
        $("modelsGrid").innerHTML = data.models.length ? data.models.map((model) => {
            const capability = /code|coder|deepseek/i.test(model) ? "CODING" : /vision|llava|vl/i.test(model) ? "VISION" : "GENERAL";
            return `<article class="model-card ${model === data.active ? "selected" : ""}"><div class="model-icon">◉</div><div class="model-copy"><h2>${escapeHtml(model)}</h2><p>Ollama local registry · ${capability} workload</p></div><span class="model-route">LOCAL</span><button class="model-action" data-model="${escapeHtml(model)}">${model === data.active ? "Active" : "Use model"}</button></article>`;
        }).join("") : '<div class="empty-state wide">No Ollama models installed. Pull one locally, then refresh this registry.</div>';
        document.querySelectorAll(".model-action").forEach((button) => button.addEventListener("click", () => selectModel(button.dataset.model)));
    }
    catch (error) { $("modelsGrid").innerHTML = `<div class="empty-state error wide">${escapeHtml(error.message)}</div>`; }
}
async function selectModel(model) { try { await api("/api/models/select", { method: "POST", body: JSON.stringify({ model }) }); await loadModels(); await loadRuntime(); } catch (error) { alert(error.message); } }

async function loadTools() {
    try { const data = await api("/api/tools"); $("overviewTools").textContent = data.tools.length; $("toolsGrid").innerHTML = data.tools.map((tool) => `<article class="tool-card"><span class="tool-icon">⌘</span><div><h2>${escapeHtml(tool.name.replaceAll("_", " "))}</h2><p>${escapeHtml(tool.description)}</p><small>WORKSPACE LOCAL</small></div></article>`).join(""); }
    catch (error) { $("toolsGrid").innerHTML = `<div class="empty-state error wide">${escapeHtml(error.message)}</div>`; }
}

function renderMessage(message) {
    const isUser = message.role === "user";
    const actions = (message.toolActions || []).map((action) => {
        let result = {};
        try { result = typeof action.result === "string" ? JSON.parse(action.result) : (action.result || {}); } catch (_) { }
        const generatedFile = result.status === "success" && result.file ? `<a class="download-link" href="/api/workspace/download?path=${encodeURIComponent(result.file)}" download><span class="material-icons">download</span>Download ${escapeHtml(result.format || "file")}</a>` : "";
        return `<div class="trace-item"><span>✓</span><b>${escapeHtml(action.tool)}</b><small>${escapeHtml(action.args?.path || action.args?.filepath || action.args?.command || result.file || "completed")}</small>${generatedFile}</div>`;
    }).join("");
    return `<div class="message ${isUser ? "user" : "assistant"}"><span class="message-label">${isUser ? "You" : "Sanctum"}</span>${actions}<div>${escapeHtml(message.content)}</div></div>`;
}
function renderActivity(events, active = false) { $("activityList").innerHTML = events.length ? events.map((event) => `<div class="activity-event ${active ? "active" : ""}"><span class="activity-state">${active ? "●" : "✓"}</span><div><b>${escapeHtml(event.text)}</b><small>${escapeHtml(event.stage)}</small></div></div>`).join("") : '<div class="empty-state">Real execution activity will appear here.</div>'; }
function renderChat() { $("messages").innerHTML = state.thread.length ? state.thread.map(renderMessage).join("") : '<div class="chat-empty"><span>✦</span><h2>What should Sanctum do?</h2><p>Ask for a code change, workspace inspection, test run, or explanation.</p></div>'; $("messages").scrollTop = $("messages").scrollHeight; }
function renderHistory() { const query = $("historySearch").value.trim().toLowerCase(); const turns = state.history.filter((item) => item.role === "user").map((item, index, all) => ({ item, number: all.length - index })).filter(({ item }) => !query || item.content.toLowerCase().includes(query)).slice(-20).reverse(); $("historyCount").textContent = `${state.history.filter((item) => item.role === "user").length} messages`; $("historyList").innerHTML = turns.length ? turns.map(({ item, number }) => `<button class="history-item" title="${escapeHtml(item.content)}"><span class="history-index">${String(number).padStart(2, "0")}</span><span class="history-copy"><b>${escapeHtml(item.content.slice(0, 90))}</b><small>Saved local mission</small></span><span class="material-icons history-arrow">chevron_right</span></button>`).join("") : `<div class="empty-state">${query ? "No saved missions match your search." : "No conversations saved yet."}</div>`; }
async function loadHistory() { try { const data = await api("/api/history"); state.history = data.history || []; renderHistory(); } catch (_) { } }
async function sendMessage(text) {
    if (!text.trim() || state.sending) return; state.sending = true; state.thread.push({ role: "user", content: text }); renderChat(); renderActivity([{ stage: "queued", text: "Preparing the local agent" }], true); $("messageInput").value = "";
    try {
        const response = await fetch("/api/chat/stream", { method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify({ message: text }) });
        if (!response.ok) throw new Error("Agent stream unavailable"); const reader = response.body.getReader(); const decoder = new TextDecoder(); let buffer = ""; let result = null; let events = [];
        while (true) { const chunk = await reader.read(); if (chunk.done) break; buffer += decoder.decode(chunk.value, { stream: true }); const packets = buffer.split("\n\n"); buffer = packets.pop(); packets.forEach((packet) => { const line = packet.split("\n").find((entry) => entry.startsWith("data: ")); if (!line) return; const event = JSON.parse(line.slice(6)); if (event.type === "activity") { events.push(event); renderActivity(events, true); } if (event.type === "result") result = event; if (event.type === "error") throw new Error(event.message); }); }
        if (result) { renderActivity(events.concat([{ stage: "complete", text: "Task completed" }]), false); state.thread.push({ role: "assistant", content: result.reply || "", toolActions: result.tool_actions || [] }); }
        await loadHistory(); loadWorkspace();
    } catch (error) { renderActivity([{ stage: "error", text: "The agent could not complete this task" }], false); state.thread.push({ role: "assistant", content: `Request failed: ${error.message}` }); }
    finally { state.sending = false; renderChat(); }
}

$("chatForm").addEventListener("submit", (event) => { event.preventDefault(); sendMessage($("messageInput").value); });
$("messageInput").addEventListener("keydown", (event) => { if (event.key === "Enter" && !event.shiftKey) { event.preventDefault(); $("chatForm").requestSubmit(); } });
document.querySelectorAll("[data-prompt]").forEach((button) => button.addEventListener("click", () => { $("messageInput").value = button.dataset.prompt; $("messageInput").focus(); }));
$("newChatBtn").addEventListener("click", () => { state.thread = []; renderChat(); });
$("clearMemoryBtn").addEventListener("click", async () => { await api("/api/clear", { method: "POST" }); state.thread = []; renderChat(); });
$("workspaceForm").addEventListener("submit", async (event) => { event.preventDefault(); const path = $("workspacePathInput").value.trim(); if (!path) return; try { await selectWorkspace(path); } catch (error) { alert(error.message); } });
$("workspacePickerBtn").addEventListener("click", async () => { try { await pickWorkspace(); } catch (error) { alert(error.message); } });
$("refreshBtn").addEventListener("click", () => { loadWorkspace(); loadRuntime(); }); $("workspaceRefresh").addEventListener("click", loadWorkspace); $("modelsRefresh").addEventListener("click", loadModels); $("securityRefresh").addEventListener("click", loadRuntime); $("copyFileBtn").addEventListener("click", () => navigator.clipboard.writeText(state.activeContent));
if ($("historySearch")) $("historySearch").addEventListener("input", renderHistory);

enhanceIdeShell();

const savedWorkspace = localStorage.getItem("sanctum-workspace");
if (savedWorkspace) { $("workspacePathInput").value = savedWorkspace; selectWorkspace(savedWorkspace).catch(() => loadWorkspace()); } else { loadWorkspace(); }
loadTools(); loadRuntime(); loadHistory(); renderChat(); renderActivity([]);
