# Sanctum — Project Overview

Sanctum is a local-first desktop-style agent studio. It runs inference through an OpenAI-compatible server on loopback (Ollama, LM Studio, llama.cpp, or vLLM), keeps workspace data on the host, and exposes the agent's approved tools through a local MCP-shaped boundary.

## Architecture & Layers

The system follows a classic client-server architecture with an intelligent agentic loop at its core.

### 1. Frontend Layer (User Interface)

**Technologies Used:** Vanilla HTML, CSS, JavaScript

- **3-Panel Layout:**
  - **Left Panel (Workspace Explorer):** Displays a real-time directory tree, active workspace path, and a list of available AI tools.
  - **Center Panel (Dashboard & Editor):** Features a dynamic UI with two states—an Agent Info Dashboard tracking active capabilities, and a Code Viewer/Editor with syntax highlighting and line numbers.
  - **Right Panel (AI Assistant Chat):** An interactive chat interface that streams Markdown-formatted responses and visually renders the agent's tool execution steps (Tool Action Cards).
- **Client Logic (`app.js`):** Interacts asynchronously with backend REST endpoints (`/api/chat`, `/api/workspace/*`, `/api/tools`).

### 2. Backend API Layer

**Technologies Used:** Python, Flask

- **Routing (`routes.py`):** Exposes endpoints that bridge the UI with the agent framework. Handles chat POST requests, history tracking, and workspace read operations.
- **Dependency Injection:** Centralized initialization in `app/__init__.py` where components like logging, configurations, and the `CodingAgent` are instantiated.

### 3. Agent Core Layer (The Brain)

**Technologies Used:** Python, Flask, LangChain (`langchain-core`, `langchain-openai`) and a loopback-only OpenAI-compatible inference server.

- **LLM Manager (`llm.py`):** Discovers locally installed models, selects coding/reasoning/vision variants from task hints, and rejects non-loopback endpoints.
- **Agent Loop (`agent.py`):** Acts as the orchestrator. When a user sends a message, the `CodingAgent`:
  1. Combines the system prompt, conversational memory, and the new query.
  2. Binds available tools to the LLM using LangChain's `bind_tools`.
  3. Evaluates the LLM's response. If the LLM requests a tool call (either natively or via fallback XML parsing like `<function/...>`), it intercepts the call, extracts arguments, and executes the physical tool.
  4. Feeds the tool's execution result back to the LLM.
  5. Repeats this cycle (up to a max iteration limit) until the LLM formulates a final response for the user.
- **Prompt Management (`prompt.py`):** Defines strict operational boundaries, formatting rules, and the Sanctum persona for the assistant.

### 4. Tool Execution Layer

**Technologies Used:** Python

- **Tool Manager (`tools/` directory):** Contains isolated scripts for distinct capabilities:
  - **File Operations (`file_tool.py`):** Create, read, write, rename, and delete workspace files.
  - **Workspace Explorer (`workspace.py`):** Inspect directory trees and fetch file metadata.
  - **Python Sandbox (`python_tool.py`):** Executes arbitrary Python snippets securely using subprocesses.
  - **Terminal (`terminal_tool.py`):** Runs shell/PowerShell commands directly in the host OS.

## Local Architecture

The system architecture anticipates the integration of more complex cognitive paradigms:

- **MCP boundary (`app/mcp/`):** The in-process server publishes tool names, descriptions, workspace scope, protocol version, and dispatches only registered local tools. The boundary is exposed through `/api/system` and `/api/tools` for auditability.
- **Air-gap proof:** `/api/system` reports the active loopback endpoint, local-only flag, MCP data boundary, and discovered model list. There is no cloud SDK or external API credential in the runtime path.
- **Model setup:** Install Ollama or another compatible local server, load a model, then optionally set `LOCAL_LLM_MODEL`. The UI discovers available models from `/v1/models`.

## System Workflow Example

1. **User input:** _"Create a file named hello.py and write a print statement."_
2. **Frontend:** Sends POST request to `/api/chat`.
3. **Agent:** LLM decides to use `create_file` and generates a tool call.
4. **Backend:** Executes `create_file` via Tool Manager, physically creating the file on the user's disk.
5. **Agent:** Receives success confirmation and drafts the final user-facing response.
6. **Frontend:** Displays the agent's message alongside an expandable "Tool Action Card" showing exactly what file was created, and updates the workspace file tree automatically.
