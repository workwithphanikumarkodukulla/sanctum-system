/**
 * Sanctum Fluid Architecture — Studio Application Script
 * NVIDIA Green (#76B900), Pure Black (#000000), White (#FFFFFF) Theme
 */

const state = {
    screen: "overview",
    activeFile: "",
    activeContent: "",
    openFiles: [],
    history: [],
    activityEvents: [],
    isSending: false,
    tools: []
};

// Utility DOM selector
const $ = (id) => document.getElementById(id);
const escapeHtml = (str) => {
    if (!str) return "";
    return String(str)
        .replace(/&/g, "&amp;")
        .replace(/</g, "&lt;")
        .replace(/>/g, "&gt;")
        .replace(/"/g, "&quot;");
};

/**
 * Universal API helper
 */
async function api(path, options = {}) {
    const defaultHeaders = { "Content-Type": "application/json" };
    const response = await fetch(path, {
        headers: { ...defaultHeaders, ...(options.headers || {}) },
        ...options
    });
    const data = await response.json().catch(() => ({}));
    if (!response.ok) {
        throw new Error(data.error || `Request failed with status ${response.status}`);
    }
    return data;
}

/**
 * Screen Navigation
 */
function showScreen(screenName) {
    if (!screenName) return;
    state.screen = screenName;

    // Update screen section visibility
    document.querySelectorAll(".screen").forEach((sec) => {
        sec.classList.toggle("active", sec.id === `screen-${screenName}`);
    });

    // Update Rail buttons
    document.querySelectorAll(".rail-btn").forEach((btn) => {
        btn.classList.toggle("active", btn.dataset.screen === screenName);
    });

    // Update topbar breadcrumb
    const screenTitle = $("screenTitle");
    if (screenTitle) {
        screenTitle.textContent = screenName.charAt(0).toUpperCase() + screenName.slice(1);
    }

    // Trigger data loading for specific screens
    if (screenName === "agent") loadChatMessages();
    if (screenName === "workspace") loadWorkspace();
    if (screenName === "models") loadModels();
    if (screenName === "lkb") loadLkb();
    if (screenName === "tools") loadTools();
    if (screenName === "security") loadSecurity();
}

function setLockerMode(mode) {
    const isUnlock = mode === "unlock";
    if ($("lockerMode")) $("lockerMode").value = mode;
    document.querySelectorAll(".locker-mode").forEach((button) => {
        button.classList.toggle("active", button.dataset.lockerMode === mode);
        const buttonLabel = button.dataset.lockerMode === "unlock" ? "Remove Cover" : "Apply Cover";
        button.title = buttonLabel;
        button.setAttribute("aria-label", buttonLabel);
    });
    if ($("lockerFileLabel")) $("lockerFileLabel").textContent = isUnlock ? "Covered file to restore" : "File to cover";
    if ($("lockerDropTitle")) $("lockerDropTitle").textContent = isUnlock ? "Choose a .locked file" : "Choose a file to cover";
    if ($("lockerDropHint")) $("lockerDropHint").textContent = isUnlock ? "The restored file will download to your computer." : "Your original file stays on your machine.";
    if ($("lockerSubmitIcon")) $("lockerSubmitIcon").textContent = isUnlock ? "lock_open" : "lock";
    if ($("lockerSubmitText")) $("lockerSubmitText").textContent = isUnlock ? "Remove Cover and download" : "Apply Cover and download";
    if ($("lockerFile")) $("lockerFile").value = "";
    if ($("lockerFileName")) $("lockerFileName").textContent = "No file selected";
    if ($("lockerStatus")) $("lockerStatus").hidden = true;
}

async function submitLockerForm(event) {
    event.preventDefault();
    const fileInput = $("lockerFile");
    const passphrase = $("lockerPassphrase");
    const status = $("lockerStatus");
    const file = fileInput?.files?.[0];
    if (!file || !passphrase?.value) return;

    const mode = $("lockerMode")?.value || "lock";
    const payload = new FormData();
    payload.append("file", file);
    payload.append("passphrase", passphrase.value);
    status.hidden = false;
    status.className = "locker-status loading";
    status.textContent = mode === "unlock" ? "Authenticating and removing cover..." : "Applying cover locally...";

    try {
        const response = await fetch(`/api/locker/${mode}`, { method: "POST", body: payload });
        if (!response.ok) {
            const data = await response.json().catch(() => ({}));
            throw new Error(data.error || "Locker operation failed.");
        }
        const blob = await response.blob();
        const disposition = response.headers.get("Content-Disposition") || "";
        const nameMatch = disposition.match(/filename="?([^";]+)"?/i);
        const downloadName = nameMatch?.[1] || (mode === "unlock" ? "restored-file" : `${file.name}.locked`);
        const link = document.createElement("a");
        link.href = URL.createObjectURL(blob);
        link.download = downloadName;
        link.click();
        URL.revokeObjectURL(link.href);
        status.className = "locker-status success";
        status.textContent = mode === "unlock" ? "Cover removed and file downloaded." : "Cover applied and file downloaded.";
    } catch (error) {
        status.className = "locker-status error";
        status.textContent = error.message;
    }
}

/**
 * System Runtime Status
 */
async function loadRuntime() {
    try {
        const data = await api("/api/system");
        const modelName = data.model?.model || "qwen2.5-coder:7b";

        if ($("topbarModel")) $("topbarModel").textContent = modelName;
        if ($("topbarStatus")) $("topbarStatus").textContent = "127.0.0.1:11434";
        if ($("agentModelLabel")) $("agentModelLabel").textContent = `${modelName} · Isolated`;
        if ($("statusModel")) $("statusModel").textContent = modelName.toUpperCase();
        if ($("overviewEndpoint")) $("overviewEndpoint").textContent = data.model?.base_url || "http://127.0.0.1:11434";
        if ($("overviewMcp")) $("overviewMcp").textContent = `${data.mcp?.name || "Sanctum MCP"} Tools`;
    } catch (err) {
        if ($("topbarStatus")) $("topbarStatus").textContent = "Offline / Error";
    }
}

/**
 * Workspace Management & File Tree
 */
async function loadWorkspace() {
    try {
        const data = await api("/api/workspace/tree");
        const wsName = (data.path || "workspace").split(/[\\/]/).pop();
        if ($("workspaceName")) $("workspaceName").textContent = wsName;
        if ($("statusWorkspace")) $("statusWorkspace").textContent = `${wsName.toUpperCase()} READY`;

        const filesCount = data.files ? data.files.length : 0;
        if ($("overviewFiles")) $("overviewFiles").textContent = filesCount;
        if ($("ecosystemFiles")) $("ecosystemFiles").textContent = `${filesCount} file${filesCount === 1 ? "" : "s"}`;
        if ($("ecosystemWorkspace")) $("ecosystemWorkspace").textContent = wsName;
        if ($("fileCountLabel")) $("fileCountLabel").textContent = `${filesCount} File${filesCount === 1 ? "" : "s"}`;

        renderTree(data.tree || [], $("workspaceTree"));
    } catch (err) {
        if ($("workspaceTree")) {
            $("workspaceTree").innerHTML = `<div class="empty-state error"><span class="material-icons">warning</span><p>${escapeHtml(err.message)}</p></div>`;
        }
    }
}

function fileIcon(fileName, type) {
    if (type === "directory") return { name: "folder", className: "icon-folder" };
    const extension = fileName.split(".").pop().toLowerCase();
    const iconByExtension = {
        py: ["code", "icon-python"], js: ["javascript", "icon-javascript"], ts: ["javascript", "icon-typescript"],
        jsx: ["javascript", "icon-javascript"], html: ["language", "icon-html"], css: ["style", "icon-css"],
        json: ["data_object", "icon-json"], md: ["article", "icon-markdown"], java: ["coffee", "icon-java"],
        sh: ["terminal", "icon-shell"], yml: ["settings", "icon-config"], yaml: ["settings", "icon-config"],
        txt: ["description", "icon-text"]
    };
    const [name, className] = iconByExtension[extension] || ["insert_drive_file", "icon-file"];
    return { name, className };
}

function renderTree(nodes, parentEl) {
    if (!parentEl) return;
    parentEl.innerHTML = "";
    if (!nodes || !nodes.length) {
        parentEl.innerHTML = `<div class="empty-state"><span class="material-icons">folder_open</span><p>Workspace is empty</p></div>`;
        return;
    }

    nodes.forEach((node) => {
        const row = document.createElement("button");
        row.className = `tree-row ${node.type === "directory" ? "directory" : "file"}`;

        const icon = fileIcon(node.name, node.type);
        row.innerHTML = `<span class="material-icons tree-symbol ${icon.className}" style="font-size:16px">${icon.name}</span><span>${escapeHtml(node.name)}</span>`;

        if (node.type === "directory") {
            const childrenContainer = document.createElement("div");
            childrenContainer.className = "tree-children";
            row.addEventListener("click", () => {
                row.classList.toggle("expanded");
                childrenContainer.classList.toggle("expanded");
            });
            parentEl.appendChild(row);
            parentEl.appendChild(childrenContainer);
            renderTree(node.children || [], childrenContainer);
        } else {
            row.addEventListener("click", () => openFile(node.path));
            parentEl.appendChild(row);
        }
    });
}

async function openFile(filePath) {
    state.activeFile = filePath;
    if (!state.openFiles.includes(filePath)) {
        state.openFiles.push(filePath);
    }
    renderEditorTabs();

    if ($("filePathDisplay")) $("filePathDisplay").textContent = filePath;
    if ($("fileMeta")) $("fileMeta").textContent = "Loading file content...";
    const fileName = filePath.split(/[\\/]/).pop();
    const extension = fileName.split(".").pop().toLowerCase();

    if (extension === "pdf") {
        state.activeContent = "";
        if ($("codeView")) {
            const previewUrl = `/api/workspace/preview?path=${encodeURIComponent(filePath)}`;
            $("codeView").innerHTML = `<iframe class="pdf-viewer" src="${previewUrl}" title="${escapeHtml(fileName)}"></iframe>`;
        }
        if ($("fileMeta")) $("fileMeta").textContent = "PDF document";
        return;
    }

    try {
        const data = await api(`/api/workspace/file?path=${encodeURIComponent(filePath)}`);
        state.activeContent = data.content || "";
        if ($("codeView")) {
            $("codeView").innerHTML = extension === "txt" || extension === "text"
                ? renderPlainText(state.activeContent)
                : highlightCode(state.activeContent, fileName);
        }
        if ($("fileMeta")) $("fileMeta").textContent = `${(data.stat?.size || 0).toLocaleString()} bytes`;
    } catch (err) {
        if ($("codeView")) $("codeView").textContent = `Error reading file: ${err.message}`;
        if ($("fileMeta")) $("fileMeta").textContent = "Error";
    }
}

function renderPlainText(source) {
    return String(source).split("\n").map((line, index) =>
        `<span class="code-line"><span class="line-number">${index + 1}</span><span class="line-content">${escapeHtml(line) || " "}</span></span>`
    ).join("");
}

function highlightCode(source, fileName) {
    const extension = fileName.split(".").pop().toLowerCase();
    const languageKeywords = {
        py: "and|as|assert|async|await|break|class|continue|def|del|elif|else|except|False|finally|for|from|global|if|import|in|is|lambda|None|not|or|pass|raise|return|True|try|while|with|yield",
        js: "as|await|break|case|catch|class|const|continue|debugger|default|delete|else|export|extends|false|finally|for|from|function|if|import|in|let|new|null|of|return|static|switch|this|throw|true|try|typeof|var|while|with",
        ts: "as|await|break|case|catch|class|const|continue|debugger|default|delete|else|export|extends|false|finally|for|from|function|if|import|in|interface|let|new|null|of|return|static|switch|this|throw|true|try|type|typeof|var|while|with",
        java: "abstract|boolean|break|case|catch|class|const|continue|default|do|else|extends|final|finally|for|if|implements|import|instanceof|int|interface|new|null|package|private|protected|public|return|static|super|switch|this|throw|throws|true|false|try|void|while",
        json: "true|false|null"
    };
    const keywordPattern = languageKeywords[extension] || languageKeywords.js;
    const tokenPattern = new RegExp(`(\\/\\*[\\s\\S]*?\\*\\/|\\/\\/[^\\n]*|#[^\\n]*|<!--[\\s\\S]*?-->|"(?:\\\\.|[^"\\\\])*"|'(?:\\\\.|[^'\\\\])*'|\\b(?:${keywordPattern})\\b|\\b\\d+(?:\\.\\d+)?\\b)`, "g");
    const lines = String(source).split("\\n");
    return lines.map((line, index) => {
        let cursor = 0;
        let highlighted = "";
        line.replace(tokenPattern, (token, _match, offset) => {
            highlighted += escapeHtml(line.slice(cursor, offset));
            const escaped = escapeHtml(token);
            const tokenClass = token.startsWith("//") || token.startsWith("#") || token.startsWith("/*") || token.startsWith("<!--") ? "syntax-comment" :
                token.startsWith('"') || token.startsWith("'") ? "syntax-string" :
                    /^\\d/.test(token) ? "syntax-number" : "syntax-keyword";
            highlighted += `<span class="${tokenClass}">${escaped}</span>`;
            cursor = offset + token.length;
            return token;
        });
        highlighted += escapeHtml(line.slice(cursor));
        return `<span class="code-line"><span class="line-number">${index + 1}</span><span class="line-content">${highlighted || " "}</span></span>`;
    }).join("");
}

function renderEditorTabs() {
    const tabsContainer = $("editorTabs");
    if (!tabsContainer) return;
    if (!state.openFiles.length) {
        tabsContainer.innerHTML = `<button class="editor-tab active"><span class="material-icons">description</span><span>No file selected</span></button>`;
        return;
    }

    tabsContainer.innerHTML = state.openFiles.map((path) => {
        const fileName = path.split(/[\\/]/).pop();
        const isActive = path === state.activeFile ? "active" : "";
        const icon = fileIcon(fileName, "file");
        return `<button class="editor-tab ${isActive}" data-file="${escapeHtml(path)}">
            <span class="material-icons ${icon.className}">${icon.name}</span>
            <span>${escapeHtml(fileName)}</span>
            <span class="material-icons editor-tab-close" data-close-file="${escapeHtml(path)}" title="Close ${escapeHtml(fileName)}" aria-label="Close ${escapeHtml(fileName)}">close</span>
        </button>`;
    }).join("");

    tabsContainer.querySelectorAll(".editor-tab").forEach((tab) => {
        tab.addEventListener("click", (event) => {
            if (event.target.closest(".editor-tab-close")) {
                closeEditorFile(tab.dataset.file);
                return;
            }
            const path = tab.dataset.file;
            if (path) openFile(path);
        });
    });
}

function closeEditorFile(filePath) {
    const closedIndex = state.openFiles.indexOf(filePath);
    if (closedIndex === -1) return;
    state.openFiles.splice(closedIndex, 1);

    if (state.activeFile !== filePath) {
        renderEditorTabs();
        return;
    }

    const nextFile = state.openFiles[Math.min(closedIndex, state.openFiles.length - 1)];
    if (nextFile) {
        openFile(nextFile);
        return;
    }

    state.activeFile = "";
    state.activeContent = "";
    renderEditorTabs();
    if ($("filePathDisplay")) $("filePathDisplay").textContent = "—";
    if ($("fileMeta")) $("fileMeta").textContent = "—";
    if ($("codeView")) $("codeView").innerHTML = emptyEditorMarkup();
}

function emptyEditorMarkup() {
    return `<div class="editor-empty-state">
        <pre class="editor-welcome-logo">000000000000000000000000000000000000000000
0                                            0
0              SANCTUM GTRIX                 0
0              ---------------               0
0                                            0
000000000000000000000000000000000000000000</pre>
        <span class="editor-empty-hint">OPEN A FILE TO START EDITING</span>
    </div>`;
}

async function selectWorkspace(path) {
    try {
        const result = await api("/api/workspace/select", {
            method: "POST",
            body: JSON.stringify({ path })
        });
        localStorage.setItem("sanctum_workspace", result.path);
        await loadWorkspace();
        await loadRuntime();
    } catch (err) {
        alert(`Workspace selection failed: ${err.message}`);
    }
}

async function pickWorkspace() {
    try {
        const res = await api("/api/workspace/pick", { method: "POST" });
        if (!res.cancelled && res.path) {
            localStorage.setItem("sanctum_workspace", res.path);
            await loadWorkspace();
            await loadRuntime();
        }
    } catch (err) {
        alert(`Native picker unavailable: ${err.message}`);
    }
}

/**
 * Agent Chat & Streaming Activity Execution
 */
async function sendMessage(text) {
    if (!text || !text.trim() || state.isSending) return;
    state.isSending = true;

    const messageInput = $("messageInput");
    if (messageInput) messageInput.value = "";

    appendChatMessage("user", text);
    renderActivityEvent("Processing mission request...", "thinking");
    // Note: Activity panel does not auto-expand per design; user expands on demand from the right

    // ── Live dynamic thinking bubble in the chat (Claude Code & Antigravity style) ──
    const thinkingBubble = createThinkingBubble();
    const startTime = Date.now();
    let resultModel = "";
    let resultDuration = "";

    try {
        const response = await fetch("/api/chat/stream", {
            method: "POST",
            headers: { "Content-Type": "application/json" },
            body: JSON.stringify({ message: text })
        });

        if (!response.ok) throw new Error(`Agent error (${response.status})`);

        const reader = response.body.getReader();
        const decoder = new TextDecoder();
        let buffer = "";
        let finalReply = "";

        while (true) {
            const { done, value } = await reader.read();
            if (done) break;
            buffer += decoder.decode(value, { stream: true });

            const lines = buffer.split("\n\n");
            buffer = lines.pop() || "";

            for (const line of lines) {
                const trimmed = line.trim();
                if (trimmed.startsWith("data: ")) {
                    try {
                        const eventData = JSON.parse(trimmed.slice(6));
                        if (eventData.type === "activity") {
                            const stepText = eventData.text || eventData.stage;
                            updateThinkingBubble(thinkingBubble, stepText);
                            renderActivityEvent(stepText, "active");
                        } else if (eventData.type === "result") {
                            finalReply = eventData.reply || "";
                            if (eventData.model_used) {
                                resultModel = eventData.model_used;
                            }
                            if (eventData.duration_s !== undefined && eventData.duration_s !== null) {
                                resultDuration = `${eventData.duration_s}s`;
                            } else if (eventData.duration_ms !== undefined && eventData.duration_ms !== null) {
                                resultDuration = `${(eventData.duration_ms / 1000).toFixed(1)}s`;
                            }
                            if (eventData.tool_actions) {
                                eventData.tool_actions.forEach((act) => {
                                    renderActivityEvent(`Tool call: ${act.tool}`, "complete");
                                });
                            }
                        } else if (eventData.type === "error") {
                            throw new Error(eventData.message);
                        }
                    } catch (_) { }
                }
            }
        }

        if (!resultDuration) {
            resultDuration = `${((Date.now() - startTime) / 1000).toFixed(1)}s`;
        }
        if (!resultModel && state.activeModel) {
            resultModel = state.activeModel;
        }

        // Replace thinking bubble with final response
        resolveThinkingBubble(thinkingBubble, finalReply || "", false, { model: resultModel, duration: resultDuration });
        if (finalReply) renderActivityEvent("Mission completed successfully.", "complete");
        await loadSessionHistory();
    } catch (err) {
        const errDuration = `${((Date.now() - startTime) / 1000).toFixed(1)}s`;
        resolveThinkingBubble(thinkingBubble, `Execution failure: ${err.message}`, true, { model: state.activeModel || "", duration: errDuration });
        renderActivityEvent(`Failed: ${err.message}`, "error");
    } finally {
        state.isSending = false;
    }
}

/** Create a live thinking bubble in the chat with dynamic shimmer text */
function createThinkingBubble() {
    const container = $("messages");
    if (!container) return null;

    const bubble = document.createElement("div");
    bubble.className = "message-bubble assistant thinking-bubble";
    bubble._startTime = Date.now();
    bubble._completedSteps = [];
    bubble._currentStep = "Analyzing request...";

    bubble.innerHTML = `
        <div class="message-meta">
            <span>SANCTUM AGENT</span>
            <span class="thinking-meta-status"><span class="thinking-pulse-dot"></span>Thinking</span>
        </div>
        <div class="message-content thinking-bubble-content">
            <div class="thinking-status-row">
                <div class="thinking-spinner-wrap" aria-hidden="true">
                    <div class="thinking-spinner-ring"></div>
                    <div class="thinking-spinner-core"></div>
                </div>
                <div class="thinking-action-box">
                    <span class="thinking-shimmer-text" id="thinkingLabel">Analyzing request...</span>
                </div>
                <span class="thinking-timer" id="thinkingTimer">0.0s</span>
            </div>
            <div class="thinking-steps-container" id="thinkingStepsContainer" style="display:none;">
                <div class="thinking-steps-list" id="thinkingStepsList"></div>
            </div>
            <button type="button" class="thinking-steps-toggle" id="thinkingStepsToggle" style="display:none;" aria-expanded="false">
                <span class="material-icons">expand_more</span>
                <span class="steps-toggle-label">0 steps</span>
            </button>
        </div>
    `;
    container.appendChild(bubble);
    bubble.scrollIntoView({ behavior: "smooth", block: "end" });

    // Timer updater
    bubble._timerInterval = setInterval(() => {
        const timerEl = bubble.querySelector("#thinkingTimer");
        if (timerEl) {
            const elapsed = ((Date.now() - bubble._startTime) / 1000).toFixed(1);
            timerEl.textContent = `${elapsed}s`;
        }
    }, 100);

    // Toggle previous steps disclosure
    const toggleBtn = bubble.querySelector("#thinkingStepsToggle");
    const stepsContainer = bubble.querySelector("#thinkingStepsContainer");
    if (toggleBtn && stepsContainer) {
        toggleBtn.addEventListener("click", () => {
            const isHidden = stepsContainer.style.display === "none";
            stepsContainer.style.display = isHidden ? "block" : "none";
            toggleBtn.setAttribute("aria-expanded", String(isHidden));
            const icon = toggleBtn.querySelector(".material-icons");
            if (icon) icon.textContent = isHidden ? "expand_less" : "expand_more";
            bubble.scrollIntoView({ behavior: "smooth", block: "end" });
        });
    }

    return bubble;
}

/** Update the status label in the thinking bubble with shimmer text and step recording */
function updateThinkingBubble(bubble, text) {
    if (!bubble || !text) return;
    const label = bubble.querySelector("#thinkingLabel");
    if (!label) return;

    // Record previous completed step if changed
    if (bubble._currentStep && bubble._currentStep !== text) {
        bubble._completedSteps.push({
            text: bubble._currentStep,
            time: ((Date.now() - bubble._startTime) / 1000).toFixed(1) + "s"
        });

        // Update past steps list
        const stepsContainer = bubble.querySelector("#thinkingStepsContainer");
        const stepsList = bubble.querySelector("#thinkingStepsList");
        const toggleBtn = bubble.querySelector("#thinkingStepsToggle");
        const toggleLabel = bubble.querySelector(".steps-toggle-label");

        if (stepsList && toggleBtn && toggleLabel) {
            stepsList.innerHTML = bubble._completedSteps.map(s => `
                <div class="thinking-past-step">
                    <span class="material-icons past-step-icon">check_circle</span>
                    <span class="past-step-text">${escapeHtml(s.text)}</span>
                    <span class="past-step-time">${s.time}</span>
                </div>
            `).join("");

            toggleBtn.style.display = "inline-flex";
            const count = bubble._completedSteps.length;
            toggleLabel.textContent = `${count} completed step${count > 1 ? "s" : ""}`;
        }
    }

    bubble._currentStep = text;

    // Smoothly animate the label update with shimmer
    label.style.opacity = "0";
    label.style.transform = "translateY(-3px)";
    setTimeout(() => {
        label.textContent = text;
        label.style.opacity = "1";
        label.style.transform = "translateY(0)";
    }, 150);

    bubble.scrollIntoView({ behavior: "smooth", block: "end" });
}

/** Replace thinking bubble with the real final content */
function resolveThinkingBubble(bubble, finalText, isError = false, meta = {}) {
    if (!bubble) {
        if (finalText) appendChatMessage("assistant", finalText, meta);
        return;
    }
    if (bubble._timerInterval) {
        clearInterval(bubble._timerInterval);
        bubble._timerInterval = null;
    }
    if (!finalText) {
        bubble.remove();
        return;
    }
    bubble.classList.remove("thinking-bubble");
    bubble.classList.add("resolving");
    if (isError) bubble.classList.add("error-bubble");

    // Remove thinking badge from meta
    const metaStatus = bubble.querySelector(".thinking-meta-status");
    if (metaStatus) metaStatus.remove();

    // Add model & time badges to message-meta
    const metaEl = bubble.querySelector(".message-meta");
    if (metaEl && (meta.model || meta.duration)) {
        let metaTags = metaEl.querySelector(".message-meta-tags");
        if (!metaTags) {
            metaTags = document.createElement("div");
            metaTags.className = "message-meta-tags";
            metaEl.appendChild(metaTags);
        }
        let badgesHtml = "";
        if (meta.model) {
            badgesHtml += `<span class="message-meta-badge model-badge" title="Model: ${escapeHtml(meta.model)}"><span class="material-icons meta-icon">memory</span>${escapeHtml(meta.model)}</span>`;
        }
        if (meta.duration) {
            badgesHtml += `<span class="message-meta-badge time-badge" title="Response time: ${escapeHtml(meta.duration)}"><span class="material-icons meta-icon">schedule</span>${escapeHtml(meta.duration)}</span>`;
        }
        metaTags.innerHTML = badgesHtml;
    }

    const content = bubble.querySelector(".message-content");
    if (content) {
        content.classList.remove("thinking-bubble-content");
        content.innerHTML = isError
            ? `<p style="color:#f87171">${escapeHtml(finalText)}</p>`
            : renderMarkdownAndMath(finalText);
        content.style.opacity = "0";
        content.style.transform = "translateY(6px)";
        requestAnimationFrame(() => {
            requestAnimationFrame(() => {
                content.style.transition = "opacity 0.32s ease, transform 0.32s cubic-bezier(0.22,1,0.36,1)";
                content.style.opacity = "1";
                content.style.transform = "translateY(0)";
            });
        });
    }
    bubble.scrollIntoView({ behavior: "smooth", block: "end" });
}

/**

 * Render Markdown and LaTeX Math safely
 * Converts $...$, $$...$$, \[...\], \(...\) to KaTeX typography
 * Converts **bold**, *italic*, headers, lists, code to styled HTML
 */
function renderMarkdownAndMath(content) {
    if (!content) return "";

    const codePlaceholders = [];
    const mathPlaceholders = [];

    // 1. Protect fenced code blocks ``` ... ```
    let text = content.replace(/(```[\s\S]*?```)/g, (match) => {
        const id = "%%CODE_BLOCK_" + codePlaceholders.length + "%%";
        codePlaceholders.push(match);
        return id;
    });

    // 2. Protect inline code ` ... `
    text = text.replace(/(`[^`\n\r]+?`)/g, (match) => {
        const id = "%%CODE_INLINE_" + codePlaceholders.length + "%%";
        codePlaceholders.push(match);
        return id;
    });

    // Helper to render KaTeX safely
    function renderTex(expr, isDisplay) {
        if (typeof katex !== "undefined" && katex.renderToString) {
            try {
                return katex.renderToString(expr.trim(), {
                    displayMode: isDisplay,
                    throwOnError: false
                });
            } catch (e) {
                return isDisplay
                    ? `<div class="katex-display"><code class="tex-err">${escapeHtml(expr)}</code></div>`
                    : `<span class="katex"><code class="tex-err">${escapeHtml(expr)}</code></span>`;
            }
        }
        return isDisplay
            ? `<div class="katex-display"><span class="math-expr">${escapeHtml(expr)}</span></div>`
            : `<span class="katex"><span class="math-expr">${escapeHtml(expr)}</span></span>`;
    }

    // 3. Extract display math $$...$$
    text = text.replace(/\$\$([\s\S]*?)\$\$/g, (_, math) => {
        const id = "%%MATH_BLOCK_" + mathPlaceholders.length + "%%";
        mathPlaceholders.push({ rendered: renderTex(math, true), isBlock: true });
        return "\n\n" + id + "\n\n";
    });

    // 4. Extract display math \[...\]
    text = text.replace(/\\\[([\s\S]*?)\\\]/g, (_, math) => {
        const id = "%%MATH_BLOCK_" + mathPlaceholders.length + "%%";
        mathPlaceholders.push({ rendered: renderTex(math, true), isBlock: true });
        return "\n\n" + id + "\n\n";
    });

    // 5. Extract inline math \(...\)
    text = text.replace(/\\\(([\s\S]*?)\\\)/g, (_, math) => {
        const id = "%%MATH_INLINE_" + mathPlaceholders.length + "%%";
        mathPlaceholders.push({ rendered: renderTex(math, false), isBlock: false });
        return id;
    });

    // 6. Extract inline math $...$
    text = text.replace(/(^|[^\\])\$([^$\n\r]+?)\$/g, (match, prefix, math) => {
        const id = "%%MATH_INLINE_" + mathPlaceholders.length + "%%";
        mathPlaceholders.push({ rendered: renderTex(math, false), isBlock: false });
        return prefix + id;
    });

    // 7. Restore protected code blocks & inlines before passing to marked
    codePlaceholders.forEach((code, i) => {
        text = text.replace("%%CODE_BLOCK_" + i + "%%", code);
        text = text.replace("%%CODE_INLINE_" + i + "%%", code);
    });

    // 8. Parse Markdown
    let html = "";
    if (typeof marked !== "undefined" && marked.parse) {
        try {
            html = marked.parse(text);
        } catch (_) {
            html = escapeHtml(text).replace(/\n/g, "<br>");
        }
    } else {
        // Fallback simple markdown parser
        html = escapeHtml(text)
            .replace(/\*\*(.*?)\*\*/g, "<strong>$1</strong>")
            .replace(/\*(.*?)\*/g, "<em>$1</em>")
            .replace(/`([^`]+)`/g, "<code>$1</code>")
            .replace(/\n\n/g, "</p><p>")
            .replace(/\n/g, "<br>");
        html = `<p>${html}</p>`;
    }

    // 9. Restore math blocks and inlines
    mathPlaceholders.forEach((item, i) => {
        if (item.isBlock) {
            html = html.replace(new RegExp("<p>\\s*%%MATH_BLOCK_" + i + "%%\\s*<\\/p>", "g"), item.rendered);
            html = html.replace(new RegExp("%%MATH_BLOCK_" + i + "%%", "g"), item.rendered);
        } else {
            html = html.replace(new RegExp("%%MATH_INLINE_" + i + "%%", "g"), item.rendered);
        }
    });

    return html;
}

function appendChatMessage(role, content, meta = {}) {
    const container = $("messages");
    if (!container) return;

    const bubble = document.createElement("div");
    bubble.className = `message-bubble ${role}`;
    const renderedContent = renderMarkdownAndMath(content);

    let metaTagsHtml = "";
    if (role === "assistant" && (meta.model || meta.duration)) {
        metaTagsHtml = `<div class="message-meta-tags">`;
        if (meta.model) {
            metaTagsHtml += `<span class="message-meta-badge model-badge" title="Model: ${escapeHtml(meta.model)}"><span class="material-icons meta-icon">memory</span>${escapeHtml(meta.model)}</span>`;
        }
        if (meta.duration) {
            metaTagsHtml += `<span class="message-meta-badge time-badge" title="Response time: ${escapeHtml(meta.duration)}"><span class="material-icons meta-icon">schedule</span>${escapeHtml(meta.duration)}</span>`;
        }
        metaTagsHtml += `</div>`;
    }

    bubble.innerHTML = `
        <div class="message-meta">
            <span>${role === "user" ? "YOU" : "SANCTUM AGENT"}</span>
            ${metaTagsHtml}
        </div>
        <div class="message-content">${renderedContent}</div>
    `;
    container.appendChild(bubble);
    container.scrollTop = container.scrollHeight;
    bubble.scrollIntoView({ behavior: "smooth", block: "end" });
}

async function loadChatMessages() {
    const container = $("messages");
    if (!container || container.children.length > 0) return;
    try {
        const data = await api("/api/history");
        const items = data.history || [];
        items.forEach((item) => {
            appendChatMessage(item.role, item.content, { model: item.model, duration: item.duration });
        });
    } catch (_) { }
}

function expandActivityPanel() {
    const layout = $("agentLayout");
    const btn = $("activityCollapseBtn");
    const headerBtn = $("toggleRailBtn");
    if (layout) layout.classList.remove("rail-collapsed");
    if (btn) {
        btn.setAttribute("aria-expanded", "true");
        btn.setAttribute("title", "Collapse execution trace to the right");
        const icon = btn.querySelector(".material-icons");
        if (icon) icon.textContent = "chevron_right";
    }
    if (headerBtn) headerBtn.classList.add("active");
}

function collapseActivityPanel() {
    const layout = $("agentLayout");
    const btn = $("activityCollapseBtn");
    const headerBtn = $("toggleRailBtn");
    if (layout) layout.classList.add("rail-collapsed");
    if (btn) {
        btn.setAttribute("aria-expanded", "false");
        btn.setAttribute("title", "Expand execution trace");
        const icon = btn.querySelector(".material-icons");
        if (icon) icon.textContent = "chevron_right";
    }
    if (headerBtn) headerBtn.classList.remove("active");
}

function toggleActivityPanel() {
    const layout = $("agentLayout");
    if (!layout) return;
    if (layout.classList.contains("rail-collapsed")) {
        expandActivityPanel();
    } else {
        collapseActivityPanel();
    }
}

function renderActivityEvent(text, stateType = "info") {
    const list = $("activityList");
    if (!list) return;

    const empty = list.querySelector(".empty-state");
    if (empty) empty.remove();

    // Mark previous active item as complete
    const prevActive = list.querySelector(".activity-event.active");
    if (prevActive && (stateType === "active" || stateType === "complete" || stateType === "error")) {
        prevActive.classList.remove("active");
        prevActive.classList.add("complete");
        const prevText = prevActive.querySelector(".activity-event-text");
        if (prevText) prevText.classList.remove("active-shimmer");
    }

    const ev = document.createElement("div");
    ev.className = `activity-event ${stateType}`;
    ev.style.setProperty("--activity-delay", `${Math.min(list.children.length, 8) * 50}ms`);

    const isLive = stateType === "active" || stateType === "thinking";

    ev.innerHTML = `
        <span class="activity-marker" aria-hidden="true"><span class="activity-dot"></span></span>
        <div class="activity-event-content">
            <div class="activity-event-text ${isLive ? 'active-shimmer' : ''}">${escapeHtml(text)}</div>
            <small class="activity-event-time">${new Date().toLocaleTimeString()}</small>
        </div>
    `;
    list.prepend(ev);
}

async function loadSessionHistory() {
    try {
        const data = await api("/api/history");
        const items = data.history || [];
        if ($("historyCount")) $("historyCount").textContent = items.length;

        const historyList = $("historyList");
        if (!historyList) return;

        if (!items.length) {
            historyList.innerHTML = `<div class="empty-state"><p>No session history.</p></div>`;
            return;
        }

        historyList.innerHTML = items.slice(-15).reverse().map((item) => `
            <div class="ws-history-card">
                <strong style="color:var(--nvidia-green)!important">${escapeHtml(item.role?.toUpperCase())}</strong>
                <small>${escapeHtml(item.content ? item.content.slice(0, 70) + "..." : "")}</small>
            </div>
        `).join("");
    } catch (_) { }
}

/**
 * Models & Fluid Routing
 */
async function loadModels() {
    try {
        const data = await api("/api/models");
        const fluidData = await api("/api/fluid/registry").catch(() => ({ profiles: {} }));

        if ($("overviewModels")) $("overviewModels").textContent = (data.models || []).length;
        if ($("ecosystemModels")) $("ecosystemModels").textContent = `${(data.models || []).length} local`;
        const grid = $("modelsGrid");
        if (!grid) return;

        const modelsList = data.models || [];
        if (!modelsList.length) {
            grid.innerHTML = `<div class="empty-state wide"><span class="material-icons">device_hub</span><p>No local Ollama models detected.</p></div>`;
            return;
        }

        const workloadLabels = {
            code: "Code Generation",
            docs: "Documentation",
            reasoning: "Analytical Reasoning",
            vision: "Vision / Multimodal",
            general: "General Purpose"
        };
        const routingRows = new Map((fluidData.routing_table || []).map((row) => [row.model, row]));

        grid.innerHTML = modelsList.map((m) => {
            const isActive = m === data.active;
            const profile = fluidData.profiles[m] || {};
            const bestFor = workloadLabels[routingRows.get(m)?.best_for] || "General Purpose";
            return `
                <div class="model-row ${isActive ? "active" : ""}">
                    <strong style="font-family:var(--font-mono);color:var(--nvidia-white)!important">${escapeHtml(m)}</strong>
                    <span>${Math.round((profile.code ?? 0.5) * 100)}%</span>
                    <span>${Math.round((profile.docs ?? 0.5) * 100)}%</span>
                    <span>${Math.round((profile.reasoning ?? 0.5) * 100)}%</span>
                    <span>${Math.round((profile.general ?? 0.5) * 100)}%</span>
                    <span style="color:var(--text-muted)">${bestFor}</span>
                    <button class="btn-secondary small select-model-btn" data-model="${escapeHtml(m)}">
                        ${isActive ? "ACTIVE" : "SELECT"}
                    </button>
                </div>
            `;
        }).join("");

        grid.querySelectorAll(".select-model-btn").forEach((btn) => {
            btn.addEventListener("click", async () => {
                await api("/api/models/select", {
                    method: "POST",
                    body: JSON.stringify({ model: btn.dataset.model })
                });
                await loadModels();
                await loadRuntime();
            });
        });
    } catch (err) {
        if ($("modelsGrid")) {
            $("modelsGrid").innerHTML = `<div class="empty-state error"><p>${escapeHtml(err.message)}</p></div>`;
        }
    }
}

/**
 * Local Knowledge Base (LKB)
 */
async function loadLkb() {
    try {
        const data = await api("/api/lkb/list");
        const files = data.files || [];
        if ($("overviewLkb")) $("overviewLkb").textContent = files.length;
        if ($("ecosystemLkb")) $("ecosystemLkb").textContent = `${files.length} indexed`;
        if ($("lkbFileCount")) $("lkbFileCount").textContent = `${files.length} file${files.length === 1 ? "" : "s"}`;

        const listEl = $("lkbFileList");
        if (listEl) {
            if (!files.length) {
                listEl.innerHTML = `<div class="empty-state"><span class="material-icons">folder_open</span><p>No documents indexed in LKB yet.</p></div>`;
            } else {
                listEl.innerHTML = files.map((f) => `
                    <div class="lkb-file-item">
                        <span>${escapeHtml(f.path || f)}</span>
                        <span class="material-icons" style="font-size:16px">check_circle</span>
                    </div>
                `).join("");
            }
        }
    } catch (_) { }
}

async function searchLkb() {
    const query = $("lkbSearchInput")?.value.trim();
    if (!query) return;
    const resultsContainer = $("lkbResults");
    if (!resultsContainer) return;

    try {
        const data = await api(`/api/lkb/search?q=${encodeURIComponent(query)}`);
        const results = data.results || [];
        if (!results.length) {
            resultsContainer.innerHTML = `<div class="empty-state"><p>No relevant documents found for '${escapeHtml(query)}'.</p></div>`;
            return;
        }

        resultsContainer.innerHTML = results.map((res) => `
            <div class="lkb-card">
                <header>${escapeHtml(res.file || res.path || "Document")}</header>
                <p>${escapeHtml(res.content || res.snippet || "")}</p>
            </div>
        `).join("");
    } catch (err) {
        resultsContainer.innerHTML = `<div class="empty-state error"><p>${escapeHtml(err.message)}</p></div>`;
    }
}

async function indexLkbPath() {
    const pathInput = $("lkbPathInput");
    const path = pathInput?.value.trim();
    if (!path) return;
    const statusEl = $("lkbIndexStatus");
    if (statusEl) {
        statusEl.classList.remove("hidden");
        statusEl.textContent = `Indexing '${path}'...`;
    }

    try {
        const isRecursive = $("lkbRecursive")?.checked ?? true;
        const result = await api("/api/lkb/index", {
            method: "POST",
            body: JSON.stringify({ path, recursive: isRecursive })
        });
        if (statusEl) {
            if (result.status === "done") {
                statusEl.textContent = `Indexed ${result.indexed} of ${result.total} file(s).`;
            } else {
                statusEl.textContent = `Successfully indexed '${path}'.`;
            }
        }
        if (pathInput) pathInput.value = "";
        await loadLkb();
    } catch (err) {
        if (statusEl) statusEl.textContent = `Indexing error: ${err.message}`;
    }
}

/**
 * Tools & Security Posture
 */
async function loadTools() {
    try {
        const data = await api("/api/tools");
        const toolsList = data.tools || [];
        state.tools = toolsList;
        if ($("overviewTools")) $("overviewTools").textContent = toolsList.length;
        if ($("ecosystemTools")) $("ecosystemTools").textContent = toolsList.length;

        const fileEl = $("toolsFile");
        const execEl = $("toolsExec");
        const docsEl = $("toolsDocs");

        if (fileEl) fileEl.innerHTML = "";
        if (execEl) execEl.innerHTML = "";
        if (docsEl) docsEl.innerHTML = "";

        const toolDetails = {
            create_file: { icon: "note_add", points: ["Create a new file in the workspace", "Write supplied content to a chosen path"] },
            read_file: { icon: "description", points: ["Read text from a workspace file", "Return its contents for analysis or explanation"] },
            write_file: { icon: "edit_document", points: ["Update an existing workspace file", "Apply requested content changes precisely"] },
            delete_file: { icon: "delete_outline", points: ["Remove a file from the workspace", "Keep all operations inside the workspace boundary"] },
            rename_file: { icon: "drive_file_rename_outline", points: ["Rename a workspace file", "Move it to a new name without leaving the workspace"] },
            list_files: { icon: "format_list_bulleted", points: ["List files in a folder", "Optionally scan nested directories"] },
            workspace_tree: { icon: "account_tree", points: ["Map the workspace directory tree", "See folders and files at a glance"] },
            file_info: { icon: "info_outline", points: ["Inspect file metadata", "Check size, type, and modification details"] },
            run_python: { icon: "code", points: ["Run Python code locally", "Return output and execution errors clearly"] },
            run_command: { icon: "terminal", points: ["Run an approved terminal command", "Work from the configured workspace root"] },
            generate_excel_sheet: { icon: "table_view", points: ["Create an Excel workbook", "Build sheets with structured data"] },
            generate_presentation: { icon: "slideshow", points: ["Create a PowerPoint presentation", "Organize content into a clear slide structure"] },
            generate_word_document: { icon: "article", points: ["Create a Word document", "Format a polished document from a brief"] },
            generate_pdf_report: { icon: "picture_as_pdf", points: ["Create a PDF report", "Turn research or notes into a shareable document"] },
            generate_structured_note: { icon: "sticky_note_2", points: ["Create a structured Markdown note", "Turn ideas into headings, lists, and sections"] }
        };

        toolsList.forEach((t) => {
            const card = document.createElement("div");
            const name = (t.name || "").toLowerCase();
            const details = toolDetails[name] || { icon: "build", points: ["Execute an approved local capability", "Available through the Sanctum agent"] };
            card.className = `tool-card tool-card-rich tool-${name}`;
            card.innerHTML = `<div class="tool-card-heading"><span class="tool-card-icon"><span class="material-icons">${details.icon}</span></span><strong>${escapeHtml(t.name || "Tool")}</strong></div><ul>${details.points.map((point) => `<li>${escapeHtml(point)}</li>`).join("")}</ul>`;
            if (name.includes("file") && !name.includes("info")) {
                if (fileEl) fileEl.appendChild(card);
            } else if (name.includes("generate")) {
                if (docsEl) docsEl.appendChild(card);
            } else {
                if (execEl) execEl.appendChild(card);
            }
        });
        document.querySelectorAll(".tool-category").forEach((category) => {
            category.open = true;
        });
    } catch (_) { }
}

function openModal(id) {
    const modal = $(id);
    if (modal) modal.hidden = false;
}

function closeModal(id) {
    const modal = $(id);
    if (modal) modal.hidden = true;
}

function toolPrompt(toolName) {
    const prompts = {
        create_file: "Create a new file named [filename] containing:",
        read_file: "Read and explain the file [filename].",
        write_file: "Update the file [filename] with the following changes:",
        delete_file: "Delete the file [filename].",
        rename_file: "Rename [old filename] to [new filename].",
        list_files: "List the files in [folder or .].",
        workspace_tree: "Show the workspace tree for [folder or .].",
        file_info: "Show metadata for the file [filename].",
        run_python: "Run this Python code and explain the result:\n[code]",
        run_command: "Run this terminal command:\n[command]",
        generate_excel_sheet: "Create an Excel workbook at [path] with these sheets and data:",
        generate_presentation: "Create a presentation titled [title] about:",
        generate_word_document: "Create a Word document titled [title] about:",
        generate_pdf_report: "Create a PDF report titled [title] about:",
        generate_structured_note: "Create a structured Markdown note titled [title] about:"
    };
    return prompts[toolName] || `Use ${toolName} to complete this task:`;
}

function renderToolPicker() {
    const list = $("toolPickerList");
    if (!list) return;
    if (!state.tools.length) {
        list.innerHTML = `<div class="empty-state"><p>Open the Tools page to load available tools.</p></div>`;
        return;
    }
    list.innerHTML = state.tools.map((tool) => `
        <div class="tool-picker-row">
            <span class="material-icons">build</span>
            <strong>${escapeHtml(tool.name)}</strong>
            <button class="btn-secondary small choose-tool-btn" data-tool="${escapeHtml(tool.name)}" type="button">Select</button>
        </div>
    `).join("");
    list.querySelectorAll(".choose-tool-btn").forEach((button) => {
        button.addEventListener("click", () => {
            const input = $("messageInput");
            if (input) {
                input.value = toolPrompt(button.dataset.tool);
                input.focus();
                input.setSelectionRange(input.value.length, input.value.length);
            }
            closeModal("toolPickerModal");
        });
    });
}

async function loadSecurity() {
    try {
        const data = await api("/api/system");
        if ($("securityStatus")) $("securityStatus").textContent = "100% AIR-GAPPED & ISOLATED";
        if ($("securityEndpoint")) $("securityEndpoint").textContent = data.model?.base_url || "127.0.0.1:11434";
        if ($("securityNetwork")) $("securityNetwork").textContent = data.model?.network_scope || "Loopback (Localhost)";
        if ($("securityTransport")) $("securityTransport").textContent = data.mcp?.transport || "STDIO / Subprocess";
        if ($("securityProtocol")) $("securityProtocol").textContent = data.mcp?.protocol_version || "2024-11-05 (MCP Draft)";
    } catch (_) { }
}

/**
 * Command Palette Commands list
 */
const availableCommands = [
    { title: "Open Overview Dashboard", icon: "dashboard", screen: "overview" },
    { title: "Explore Workspace Files", icon: "folder_open", screen: "workspace" },
    { title: "Start Autonomous Agent Task", icon: "auto_awesome", screen: "agent" },
    { title: "Configure Local LLM Models & Routing", icon: "device_hub", screen: "models" },
    { title: "Search Local Knowledge Base (LKB)", icon: "library_books", screen: "lkb" },
    { title: "View Approved MCP Tools", icon: "construction", screen: "tools" },
    { title: "Open Sanctum Locker", icon: "lock", screen: "locker" },
    { title: "Inspect Security & Loopback Isolation", icon: "shield", screen: "security" }
];

function renderCommandResults(query = "") {
    const resultsContainer = $("commandResults");
    if (!resultsContainer) return;

    const filtered = availableCommands.filter((cmd) =>
        cmd.title.toLowerCase().includes(query.toLowerCase())
    );

    if (!filtered.length) {
        resultsContainer.innerHTML = `<div class="empty-state"><p>No commands matching '${escapeHtml(query)}'</p></div>`;
        return;
    }

    resultsContainer.innerHTML = filtered.map((cmd) => `
        <div class="cmd-item" data-screen="${cmd.screen}">
            <span class="material-icons">${cmd.icon}</span>
            <span>${escapeHtml(cmd.title)}</span>
        </div>
    `).join("");

    resultsContainer.querySelectorAll(".cmd-item").forEach((item) => {
        item.addEventListener("click", () => {
            showScreen(item.dataset.screen);
            const palette = $("commandPalette");
            if (palette) palette.hidden = true;
        });
    });
}

/**
 * Event Listeners & Initialization
 */
document.addEventListener("DOMContentLoaded", () => {
    // Activity Rail Screen Switching
    document.querySelectorAll(".rail-btn, .workflow-btn, [data-screen]").forEach((btn) => {
        btn.addEventListener("click", () => {
            const targetScreen = btn.dataset.screen;
            if (targetScreen) showScreen(targetScreen);
        });
    });

    // Command Palette
    const palette = $("commandPalette");
    const cmdInput = $("commandInput");
    const cmdTrigger = $("commandTrigger");

    function openCommandPalette() {
        if (palette) palette.hidden = false;
        renderCommandResults("");
        if (cmdInput) {
            cmdInput.value = "";
            cmdInput.focus();
        }
    }

    function closeCommandPalette() {
        if (palette) palette.hidden = true;
    }

    if (cmdTrigger) cmdTrigger.addEventListener("click", openCommandPalette);

    if (cmdInput) {
        cmdInput.addEventListener("input", (e) => {
            renderCommandResults(e.target.value);
        });
    }

    document.addEventListener("keydown", (e) => {
        if ((e.ctrlKey || e.metaKey) && e.key.toLowerCase() === "k") {
            e.preventDefault();
            if (palette && palette.hidden) openCommandPalette();
            else closeCommandPalette();
        } else if (e.key === "Escape") {
            closeCommandPalette();
        }
    });

    if (palette) {
        palette.addEventListener("click", (e) => {
            if (e.target === palette) closeCommandPalette();
        });
    }

    // Chat Form
    const chatForm = $("chatForm");
    if (chatForm) {
        chatForm.addEventListener("submit", (e) => {
            e.preventDefault();
            const msgInput = $("messageInput");
            if (msgInput) sendMessage(msgInput.value);
        });
    }

    const msgInput = $("messageInput");
    if (msgInput) {
        msgInput.addEventListener("keydown", (e) => {
            if (e.key === "Enter" && !e.shiftKey) {
                e.preventDefault();
                sendMessage(msgInput.value);
            }
        });
    }

    // Quick Prompts
    document.querySelectorAll(".qp-btn").forEach((btn) => {
        btn.addEventListener("click", () => {
            const prompt = btn.dataset.prompt;
            if (prompt) sendMessage(prompt);
        });
    });

    document.querySelectorAll("[data-overview-prompt]").forEach((btn) => {
        btn.addEventListener("click", () => {
            const input = $("overviewCommandInput");
            if (input) input.value = btn.dataset.overviewPrompt;
            showScreen("agent");
            sendMessage(btn.dataset.overviewPrompt);
        });
    });

    document.querySelectorAll(".tool-launch-card").forEach((card) => {
        card.addEventListener("click", () => {
            const prompt = card.dataset.toolPrompt;
            if (!prompt) return;
            const input = $("messageInput");
            if (input) input.value = prompt;
            showScreen("agent");
            if (input) input.focus();
        });
    });
    if ($("overviewCommandBtn")) {
        $("overviewCommandBtn").addEventListener("click", () => {
            const input = $("overviewCommandInput");
            if (input?.value.trim()) {
                showScreen("agent");
                sendMessage(input.value);
            }
        });
    }
    if ($("overviewCommandInput")) {
        $("overviewCommandInput").addEventListener("keydown", (event) => {
            if (event.key === "Enter" && !event.shiftKey) {
                event.preventDefault();
                if (event.currentTarget.value.trim()) {
                    showScreen("agent");
                    sendMessage(event.currentTarget.value);
                }
            }
        });
    }

    // New Chat Button
    if ($("newChatBtn")) {
        $("newChatBtn").addEventListener("click", async () => {
            try {
                await api("/api/clear", { method: "POST" });
            } catch (err) {
                console.warn("Error clearing chat session:", err);
            }
            if ($("messages")) $("messages").innerHTML = "";
            if ($("activityList")) {
                $("activityList").innerHTML = '<div class="empty-state"><span class="material-icons">bolt</span><p>Activity appears here.</p></div>';
            }
            if ($("historyCount")) $("historyCount").textContent = "0";
            state.activeThinkingBubble = null;
        });
    }
    if ($("toolPickerBtn")) {
        $("toolPickerBtn").addEventListener("click", async () => {
            openModal("toolPickerModal");
            if (!state.tools.length) await loadTools();
            renderToolPicker();
        });
    }
    if ($("historyBtn")) $("historyBtn").addEventListener("click", () => {
        openModal("historyModal");
        loadSessionHistory();
    });
    if ($("railDockTab")) {
        $("railDockTab").addEventListener("click", () => {
            expandActivityPanel();
        });
    }
    if ($("toggleRailBtn")) {
        $("toggleRailBtn").addEventListener("click", () => {
            toggleActivityPanel();
        });
    }
    if ($("activityCollapseBtn")) {
        $("activityCollapseBtn").addEventListener("click", (e) => {
            e.stopPropagation();
            collapseActivityPanel();
        });
    }
    const actHeader = document.querySelector(".activity-panel-header");
    if (actHeader) {
        actHeader.addEventListener("click", () => {
            collapseActivityPanel();
        });
    }

    document.querySelectorAll("[data-modal-close]").forEach((button) => {
        button.addEventListener("click", () => closeModal(button.dataset.modalClose));
    });
    document.querySelectorAll(".modal-backdrop").forEach((modal) => {
        modal.addEventListener("click", (event) => {
            if (event.target === modal) closeModal(modal.id);
        });
    });
    document.addEventListener("keydown", (event) => {
        if (event.key === "Escape") {
            closeModal("toolPickerModal");
            closeModal("historyModal");
        }
    });

    // Workspace & Header Actions
    if ($("workspacePickerBtn")) $("workspacePickerBtn").addEventListener("click", pickWorkspace);
    if ($("refreshBtn")) $("refreshBtn").addEventListener("click", () => { loadWorkspace(); loadRuntime(); });
    if ($("clearMemoryBtn")) {
        $("clearMemoryBtn").addEventListener("click", async () => {
            await api("/api/clear", { method: "POST" });
            if ($("messages")) $("messages").innerHTML = "";
        });
    }
    if ($("copyFileBtn")) {
        $("copyFileBtn").addEventListener("click", () => {
            if (state.activeContent) {
                navigator.clipboard.writeText(state.activeContent);
            }
        });
    }
    document.querySelectorAll(".locker-mode").forEach((button) => {
        button.addEventListener("click", () => setLockerMode(button.dataset.lockerMode));
    });
    if ($("lockerFile")) {
        $("lockerFile").addEventListener("change", () => {
            const file = $("lockerFile").files?.[0];
            if ($("lockerFileName")) $("lockerFileName").textContent = file ? file.name : "No file selected";
        });
    }
    if ($("lockerPassphraseToggle")) {
        $("lockerPassphraseToggle").addEventListener("click", () => {
            const input = $("lockerPassphrase");
            if (!input) return;
            input.type = input.type === "password" ? "text" : "password";
        });
    }
    if ($("lockerForm")) $("lockerForm").addEventListener("submit", submitLockerForm);

    // LKB Form Actions
    if ($("lkbSearchBtn")) $("lkbSearchBtn").addEventListener("click", searchLkb);
    if ($("lkbSearchInput")) {
        $("lkbSearchInput").addEventListener("keydown", (e) => {
            if (e.key === "Enter") searchLkb();
        });
    }
    if ($("lkbIndexBtn")) $("lkbIndexBtn").addEventListener("click", indexLkbPath);
    if ($("lkbClearBtn")) {
        $("lkbClearBtn").addEventListener("click", async () => {
            await api("/api/lkb/clear", { method: "DELETE" });
            await loadLkb();
        });
    }
    if ($("historySearch")) {
        $("historySearch").addEventListener("input", (event) => {
            const query = event.target.value.toLowerCase();
            document.querySelectorAll("#historyList .ws-history-card").forEach((item) => {
                item.hidden = !item.textContent.toLowerCase().includes(query);
            });
        });
    }

    // Route Preview Action
    if ($("routePreviewBtn")) {
        $("routePreviewBtn").addEventListener("click", async () => {
            const task = $("routePreviewInput")?.value.trim();
            if (!task) return;
            const resBox = $("routePreviewResult");
            try {
                const res = await api(`/api/fluid/route?task=${encodeURIComponent(task)}`);
                if (resBox) {
                    resBox.classList.remove("hidden");
                    resBox.innerHTML = `<strong>Selected Model:</strong> ${escapeHtml(res.selected_model)}<br><small>Confidence: ${Math.round((res.confidence || 0.9) * 100)}%</small>`;
                }
            } catch (err) {
                if (resBox) {
                    resBox.classList.remove("hidden");
                    resBox.textContent = `Route preview error: ${err.message}`;
                }
            }
        });
    }

    // Initial Load
    loadRuntime();
    loadWorkspace();
    loadModels();
    loadLkb();
    loadTools();
    loadSessionHistory();
    showScreen("overview");
});
