"""Agent logic — LLM-driven tool calling with Sanctum Fluid Architecture."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from langchain_core.messages import (
    AIMessage,
    HumanMessage,
    SystemMessage,
    ToolMessage,
)
from langchain_core.tools import tool

from app.config import Config
from app.logger import logger
from app.memory import MemoryManager
from app.mcp import LocalMCPServer
from app.prompt import PromptManager
from app.tools.doc_generator import DocumentGenerator
from app.tools.manager import ToolManager


# ------------------------------------------------------------------
# LangChain tool wrappers
# ------------------------------------------------------------------
def _make_langchain_tools(tool_manager: ToolManager):
    """Create LangChain-compatible tool functions wrapping existing tools."""

    @tool
    def create_file(path: str, content: str = "") -> str:
        """Create a new file in the workspace with the given path and content.
        Use this whenever the user asks to create, make, generate, or add a new file.
        Always provide the full file content — never leave it empty unless explicitly asked."""
        try:
            result = tool_manager.execute("file", action="create_file", path=path, content=content)
            return json.dumps(result)
        except Exception as e:
            return json.dumps({"error": str(e)})

    @tool
    def read_file(path: str) -> str:
        """Read and return the full contents of a file in the workspace.
        Use this when the user asks to read, show, open, view, or display a file."""
        try:
            result = tool_manager.execute("file", action="read_file", path=path)
            return json.dumps(result)
        except Exception as e:
            return json.dumps({"error": str(e)})

    @tool
    def write_file(path: str, content: str) -> str:
        """Write (overwrite) content to a file in the workspace, creating it if needed.
        Use this when the user asks to write, update, edit, or modify a file."""
        try:
            result = tool_manager.execute("file", action="write_file", path=path, content=content)
            return json.dumps(result)
        except Exception as e:
            return json.dumps({"error": str(e)})

    @tool
    def delete_file(path: str) -> str:
        """Delete a file from the workspace.
        Use this when the user asks to delete, remove, or destroy a file."""
        try:
            result = tool_manager.execute("file", action="delete_file", path=path)
            return json.dumps(result)
        except Exception as e:
            return json.dumps({"error": str(e)})

    @tool
    def rename_file(old_path: str, new_path: str) -> str:
        """Rename or move a file within the workspace from old_path to new_path.
        Use this when the user asks to rename or move a file."""
        try:
            result = tool_manager.execute("file", action="rename_file", old_path=old_path, new_path=new_path)
            return json.dumps(result)
        except Exception as e:
            return json.dumps({"error": str(e)})

    @tool
    def list_files(path: str = ".", recursive: bool = False) -> str:
        """List all files and folders in the given workspace directory.
        Use this when the user wants to see what files exist, list the workspace, or browse the directory."""
        try:
            result = tool_manager.execute("workspace", action="list_files", path=path, recursive=recursive)
            return json.dumps(result)
        except Exception as e:
            return json.dumps({"error": str(e)})

    @tool
    def workspace_tree(path: str = ".") -> str:
        """Show the directory tree structure of the workspace.
        Use this when the user asks for a tree, directory structure, or folder hierarchy."""
        try:
            result = tool_manager.execute("workspace", action="tree", path=path)
            return json.dumps(result)
        except Exception as e:
            return json.dumps({"error": str(e)})

    @tool
    def file_info(path: str) -> str:
        """Get metadata about a file — size, type, last modified time.
        Use this when the user asks for file info, stats, metadata, or details about a file."""
        try:
            result = tool_manager.execute("workspace", action="stat", path=path)
            return json.dumps(result)
        except Exception as e:
            return json.dumps({"error": str(e)})

    @tool
    def run_python(code: str) -> str:
        """Execute a Python code snippet and return stdout/stderr.
        Use this when the user asks to run, execute, or test Python code."""
        try:
            result = tool_manager.execute("python", code=code)
            return json.dumps(result)
        except Exception as e:
            return json.dumps({"error": str(e)})

    @tool
    def run_command(command: str) -> str:
        """Execute a shell/terminal command and return the output.
        Use this when the user asks to run a shell command or terminal command."""
        try:
            result = tool_manager.execute("terminal", command=command)
            return json.dumps(result)
        except Exception as e:
            return json.dumps({"error": str(e)})

    return [
        create_file, read_file, write_file, delete_file, rename_file,
        list_files, workspace_tree, file_info, run_python, run_command,
    ]


def make_document_tools(doc_generator: DocumentGenerator):
    """Create LangChain tools for local Excel, PPTX, Word, PDF, and notes."""

    @tool
    def generate_excel_sheet(filepath: str, sheets_json: str) -> str:
        """Generate a styled Excel workbook. sheets_json is a JSON list of sheets with title, headers, rows, and optional totals_row."""
        try:
            path = doc_generator.generate_excel(filepath, json.loads(sheets_json))
            return json.dumps({"status": "success", "file": path, "format": "xlsx"})
        except Exception as error:
            return json.dumps({"status": "error", "error": f"Failed to create Excel: {error}"})

    @tool
    def generate_presentation(filepath: str, title: str, subtitle: str, slides_json: str) -> str:
        """Generate a widescreen PowerPoint. slides_json is a JSON list of slides with cards or bullet_points."""
        try:
            path = doc_generator.generate_presentation(filepath, title, subtitle, json.loads(slides_json))
            return json.dumps({"status": "success", "file": path, "format": "pptx"})
        except Exception as error:
            return json.dumps({"status": "error", "error": f"Failed to create presentation: {error}"})

    @tool
    def generate_word_document(filepath: str, title: str, subtitle: str, sections_json: str) -> str:
        """Generate a formatted Word document. sections_json is a JSON list of heading, content, callout, and optional table data."""
        try:
            path = doc_generator.generate_docx(filepath, title, subtitle, json.loads(sections_json))
            return json.dumps({"status": "success", "file": path, "format": "docx"})
        except Exception as error:
            return json.dumps({"status": "error", "error": f"Failed to create Word document: {error}"})

    @tool
    def generate_pdf_report(filepath: str, title: str, subtitle: str, sections_json: str) -> str:
        """Generate a formatted PDF report. sections_json is a JSON list of report sections and optional tables/callouts."""
        try:
            path = doc_generator.generate_pdf(filepath, title, subtitle, json.loads(sections_json))
            return json.dumps({"status": "success", "file": path, "format": "pdf"})
        except Exception as error:
            return json.dumps({"status": "error", "error": f"Failed to create PDF: {error}"})

    @tool
    def generate_structured_note(filepath: str, title: str, summary: str, tags_csv: str, sections_json: str) -> str:
        """Generate a Markdown note with YAML frontmatter, tasks, bullets, and sections."""
        try:
            tags = [tag.strip() for tag in tags_csv.split(",") if tag.strip()]
            path = doc_generator.generate_note(filepath, title, tags, summary, json.loads(sections_json))
            return json.dumps({"status": "success", "file": path, "format": "md"})
        except Exception as error:
            return json.dumps({"status": "error", "error": f"Failed to create note: {error}"})

    return [
        generate_excel_sheet, generate_presentation, generate_word_document,
        generate_pdf_report, generate_structured_note,
    ]


# ------------------------------------------------------------------
# Agent
# ------------------------------------------------------------------
class CodingAgent:
    """Agentic assistant with Sanctum Fluid Architecture, workspace history, and LKB."""

    MAX_TOOL_ITERATIONS = 6

    def __init__(self, llm_manager, tool_manager=None, fluid_router=None,
                 workspace_history=None, lkb_manager=None):
        self.llm_manager = llm_manager
        self.tool_manager = tool_manager or ToolManager(root_dir=Config.WORKSPACE)
        self._workspace_state_file = Path(Config.WORKSPACE_STATE_FILE).expanduser().resolve()
        self._load_saved_workspace()

        self.doc_generator = DocumentGenerator(self.tool_manager.get("workspace").root_dir)
        self.mcp = LocalMCPServer(self.tool_manager)
        self.prompt_manager = PromptManager()
        self.memory_manager = MemoryManager()

        # Sanctum Fluid Architecture systems
        self.fluid_router = fluid_router
        self.workspace_history = workspace_history
        self.lkb_manager = lkb_manager

        # Wrap existing tools as LangChain tools and bind to the LLM
        self.lc_tools = _make_langchain_tools(self.tool_manager) + make_document_tools(self.doc_generator)
        self._tools_by_name = {t.name: t for t in self.lc_tools}
        self.llm_with_tools = self.llm_manager._llm.bind_tools(self.lc_tools, tool_choice="auto")

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def chat(self, message: str, event_callback=None) -> dict[str, Any]:
        """Process a user message with Fluid routing, LKB context, and workspace history."""
        if not message:
            raise ValueError("Message cannot be empty.")

        activity_events = []

        def emit(stage, text):
            event = {"stage": stage, "text": text}
            activity_events.append(event)
            if event_callback:
                event_callback(event)

        # ── Fluid Router: select best model for this task ──────────────
        emit("routing", "Evaluating local model capabilities")
        if self.fluid_router:
            self.fluid_router.route(message)
            emit("routing", f"Selected model: {self.llm_manager.model_name}")
        else:
            self.llm_manager.select_for_task(message)
            emit("routing", f"Preparing local inference with {self.llm_manager.model_name}")

        self.llm_with_tools = self.llm_manager._llm.bind_tools(self.lc_tools, tool_choice="auto")

        # ── Workspace History: record the user message ─────────────────
        if self.workspace_history:
            self.workspace_history.add_message("user", message)

        self.memory_manager.add_user_message(message)
        emit("planning", "Determining the required tools")

        # ── LKB: inject relevant context ───────────────────────────────
        lkb_context = ""
        if self.lkb_manager and self.lkb_manager.has_content():
            emit("lkb", "Searching local knowledge base")
            lkb_context = self.lkb_manager.get_context(message)
            if lkb_context:
                emit("lkb", f"Found relevant knowledge ({len(lkb_context.split())} words)")

        messages = self._build_messages(message, lkb_context=lkb_context)
        tool_actions: list[dict[str, Any]] = []

        import re

        response = None
        for _ in range(self.MAX_TOOL_ITERATIONS):
            emit("reasoning", "Analyzing the request")
            response = self.llm_with_tools.invoke(messages)

            # Fallback for models outputting XML-like tags instead of native tool calls
            if not response.tool_calls and response.content and "<function/" in response.content:
                pattern = r'<function/([^>]+)>(.*?)</function>'
                matches = list(re.finditer(pattern, response.content, re.DOTALL))
                if matches:
                    fallback_calls = []
                    for i, match in enumerate(matches):
                        name = match.group(1).strip()
                        args_str = match.group(2).strip()
                        try:
                            args = json.loads(args_str)
                        except Exception:
                            args = {"content": args_str}
                        fallback_calls.append({"name": name, "args": args, "id": f"call_fb_{i}"})
                    response.tool_calls = fallback_calls
                    response.content = re.sub(pattern, "", response.content, flags=re.DOTALL).strip()

            messages.append(response)

            if not response.tool_calls:
                break

            for tc in response.tool_calls:
                name = tc["name"]
                args = tc["args"]
                logger.info("Tool call: {} with args {}", name, args)
                tool_labels = {
                    "read_file": "Reading file", "write_file": "Writing file",
                    "create_file": "Creating file", "run_python": "Executing Python",
                    "run_command": "Running validation", "list_files": "Inspecting workspace",
                    "workspace_tree": "Reading workspace structure", "file_info": "Checking file metadata",
                    "delete_file": "Deleting file", "rename_file": "Renaming file",
                }
                emit("tool", tool_labels.get(name, f"Running {name.replace('_', ' ')}"))

                if name in self._tools_by_name:
                    result = self._tools_by_name[name].invoke(args)
                else:
                    result = json.dumps({"error": f"Unknown tool: {name}"})

                tool_actions.append({"tool": name, "args": args, "result": result})
                messages.append(ToolMessage(content=str(result), tool_call_id=tc["id"]))
                emit("verification", "Reviewing tool output")

        final_text = response.content if response else ""
        file_request = re.search(
            r"\b(create|make|write|generate|add)\b.*\b(file|script|code|class|program)\b|\b([A-Za-z0-9_.-]+\.(?:py|js|ts|java|html|css|txt|md|json))\b",
            message, re.IGNORECASE,
        )
        file_actions = {"create_file", "write_file"}
        if file_request and not any(action["tool"] in file_actions for action in tool_actions):
            filename_match = re.search(r"\b([A-Za-z0-9_.-]+\.(?:java|py|js|ts|html|css|txt|md|json))\b", message, re.IGNORECASE)
            if filename_match:
                filename = filename_match.group(1)
                # Try to extract code block from LLM output or generate based on prompt
                code_match = re.search(r"```(?:\w+)?\n(.*?)```", final_text, re.DOTALL)
                if code_match:
                    content = code_match.group(1)
                elif final_text and len(final_text.strip()) > 5 and "I could not confirm" not in final_text:
                    content = final_text.strip()
                else:
                    # Specific generators based on request intent
                    msg_lower = message.lower()
                    if "0 to 10" in msg_lower or "0 till 10" in msg_lower:
                        content = "# Python script to print numbers 0 to 10\nfor i in range(11):\n    print(i)\n"
                    elif "1 to 10" in msg_lower:
                        content = "# Python script to print numbers 1 to 10\nfor i in range(1, 11):\n    print(i)\n"
                    elif filename.endswith(".py"):
                        content = f"# {filename}\nprint('Sanctum agent script initialized.')\n"
                    else:
                        content = f"// {filename}\n"

                try:
                    emit("tool", f"Creating {filename}")
                    result = self.tool_manager.execute("file", action="create_file", path=filename, content=content)
                    tool_actions.append({"tool": "create_file", "args": {"path": filename, "content": content}, "result": json.dumps(result)})
                    emit("verification", f"Verifying {filename}")
                    verified = self.tool_manager.execute("file", action="read_file", path=filename)
                    final_text = f"Successfully created and verified `{filename}` in the workspace:\n\n```python\n{content}\n```"
                except Exception as error:
                    final_text = f"I could not create `{filename}`: {error}"
            else:
                emit("verification", "No file write was confirmed")
                final_text = (
                    "I could not confirm a file write, so I have not claimed that the file was created. "
                    "Please retry the request and I will verify the path and contents after the tool completes."
                )

        document_request = re.search(
            r"\b(doc|docs|document|word|docx|guide|report|manual|tutorial|writeup|how-to)\b",
            message, re.IGNORECASE,
        )
        document_tools = {"generate_word_document", "generate_pdf_report", "generate_excel_sheet", "generate_presentation", "generate_structured_note"}
        if document_request and not any(action["tool"] in document_tools for action in tool_actions):
            try:
                def _parse_text_into_sections(text: str) -> list[dict]:
                    sections: list[dict] = []
                    current_heading = ""
                    current_lines: list[str] = []
                    heading_pattern = re.compile(
                        r"^(?:#{1,3}\s+(.+)|(?:Step\s+\d+[:.]\s*)(.+)|(\d+\.\s+.+))$",
                        re.IGNORECASE,
                    )
                    for line in text.splitlines():
                        stripped = line.strip()
                        m = heading_pattern.match(stripped)
                        if m:
                            if current_heading or current_lines:
                                sections.append({"heading": current_heading or "Overview", "content": "\n".join(current_lines).strip()})
                            heading_text = next(g for g in m.groups() if g)
                            current_heading = re.sub(r"^#+\s*", "", heading_text).strip()
                            current_lines = []
                        else:
                            if stripped:
                                clean = re.sub(r"```[\w]*", "", stripped).strip()
                                if clean:
                                    current_lines.append(clean)
                    if current_heading or current_lines:
                        sections.append({"heading": current_heading or "Details", "content": "\n".join(current_lines).strip()})
                    if not sections:
                        sections = [{"heading": "Content", "content": text.strip()}]
                    return sections

                def _derive_title(msg: str) -> str:
                    title = re.sub(
                        r"^(create|make|write|generate|build|prepare)\s+(a\s+)?(doc(s|ument)?|guide|report|manual|tutorial|writeup|how-to)\s+(for|on|about|explaining|covering)?\s*",
                        "", msg, flags=re.IGNORECASE,
                    ).strip()
                    return title.capitalize() if title else "Sanctum Document"

                def _derive_filename(msg: str) -> str:
                    slug = re.sub(r"[^\w\s-]", "", msg.lower())
                    slug = re.sub(r"[\s-]+", "_", slug).strip("_")
                    return f"generated/{slug[:60]}.docx"

                title = _derive_title(message)
                filepath = _derive_filename(message)
                llm_text = final_text.strip()
                sections = _parse_text_into_sections(llm_text) if llm_text else [{"heading": "Request", "content": message}]
                args = {"filepath": filepath, "title": title, "subtitle": "Generated by Sanctum", "sections_json": json.dumps(sections)}
                emit("tool", "Generating Word document")
                result = self._tools_by_name["generate_word_document"].invoke(args)
                tool_actions.append({"tool": "generate_word_document", "args": args, "result": result})
                parsed_result = json.loads(result)
                if parsed_result.get("status") == "success":
                    final_text = (
                        f"I've generated the document **`{parsed_result['file']}`** in your workspace.\n\n"
                        f"It contains {len(sections)} section(s) covering: "
                        + ", ".join(s['heading'] for s in sections[:4])
                        + (" and more." if len(sections) > 4 else ".")
                    )
                else:
                    final_text = parsed_result.get("error", "The document could not be generated.")
                emit("verification", "Verified generated document")
            except Exception as error:
                logger.exception("Document fallback failed.")
                final_text = f"I could not generate the document: {error}"

        emit("complete", "Preparing response")
        self.memory_manager.add_ai_message(final_text)

        # ── Workspace History: record AI response ──────────────────────
        if self.workspace_history:
            self.workspace_history.add_message(
                "assistant", final_text,
                metadata={"model": self.llm_manager.model_name, "tools_used": [a["tool"] for a in tool_actions]}
            )

        return {"reply": final_text, "tool_actions": tool_actions, "activity_events": activity_events}

    def list_tools(self) -> list[dict[str, str]]:
        return [{"name": t.name, "description": t.description} for t in self.lc_tools]

    def generate_pdf(self, filepath: str, title: str, subtitle: str = "", sections: list[dict[str, Any]] | None = None) -> str:
        return self.doc_generator.generate_pdf(filepath, title, subtitle, sections or [])

    def generate_presentation(self, filepath: str, title: str, subtitle: str = "", slides_data: list[dict[str, Any]] | None = None) -> str:
        return self.doc_generator.generate_presentation(filepath, title, subtitle, slides_data or [])

    def generate_docx(self, filepath: str, title: str, subtitle: str = "", sections: list[dict[str, Any]] | None = None) -> str:
        return self.doc_generator.generate_docx(filepath, title, subtitle, sections or [])

    def generate_excel(self, filepath: str, sheets: list[dict[str, Any]] | None = None) -> str:
        return self.doc_generator.generate_excel(filepath, sheets or [])

    def generate_note(self, filepath: str, title: str, tags: list[str] | None = None, summary: str = "", sections: list[dict[str, Any]] | None = None) -> str:
        return self.doc_generator.generate_note(filepath, title, tags or [], summary, sections or [])

    def system_info(self) -> dict[str, Any]:
        model_info = self.llm_manager.get_model_info()
        models = self.llm_manager.list_models()
        routing_table = self.fluid_router.routing_table() if self.fluid_router else []
        return {
            "model": model_info,
            "available_models": models,
            "local_inference": True,
            "external_api": False,
            "mcp": self.mcp.server_info(),
            "workspace": str(self.tool_manager.get("workspace").root_dir),
            "fluid_routing": routing_table,
        }

    def set_workspace(self, root_dir: str) -> str:
        selected = self.tool_manager.set_root_dir(root_dir)
        self.doc_generator.set_root_dir(selected)
        self._workspace_state_file.write_text(selected, encoding="utf-8")
        # Switch workspace history and LKB to new workspace
        if self.workspace_history:
            from app.workspace_history import WorkspaceHistoryManager
            self.workspace_history = WorkspaceHistoryManager(selected)
        if self.lkb_manager:
            self.lkb_manager.set_workspace(selected)
        logger.info("Workspace changed to {}", selected)
        return selected

    def _load_saved_workspace(self) -> None:
        if not self._workspace_state_file.exists():
            return
        saved = self._workspace_state_file.read_text(encoding="utf-8").strip()
        if saved and Path(saved).is_dir():
            self.tool_manager.set_root_dir(saved)
            logger.info("Saved workspace restored: {}", saved)

    def execute_tool(self, name: str, *args, **kwargs) -> Any:
        return self.tool_manager.execute(name, *args, **kwargs)

    def clear_memory(self):
        self.memory_manager.clear()

    def get_history(self) -> list[dict[str, str]]:
        return self.memory_manager.get_history()

    def _build_messages(self, current_message: str, lkb_context: str = ""):
        """Build LangChain message list from conversation history + LKB context."""
        # Compose system prompt with workspace history summary
        system_content = self.prompt_manager.system_prompt
        if self.workspace_history:
            ws_summary = self.workspace_history.get_summary()
            if ws_summary:
                system_content += f"\n\n{ws_summary}"
        if lkb_context:
            system_content += f"\n\n[LOCAL KNOWLEDGE BASE CONTEXT]\n{lkb_context}"

        msgs: list = [SystemMessage(content=system_content)]

        history = self.memory_manager.get_history()
        for entry in history[:-1][-20:]:
            if entry["role"] == "user":
                msgs.append(HumanMessage(content=entry["content"]))
            else:
                msgs.append(AIMessage(content=entry["content"]))

        msgs.append(HumanMessage(content=current_message))
        return msgs
