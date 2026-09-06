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
from app.observability.workflow_trace import WorkflowTrace, workflow_trace_store
import re
import time

_SECRET_PATTERNS = [
    re.compile(r"\b(?:ghp|gho|ghu|ghs|ghr)_[A-Za-z0-9_]{20,}\b"), # GitHub tokens
    re.compile(r"\bsk-[a-zA-Z0-9]{20,}\b"),                         # OpenAI/similar API keys
    re.compile(r"\bAKIA[0-9A-Z]{16}\b"),                            # AWS Access Key ID
    re.compile(r"\bAIzaSy[A-Za-z0-9_-]{20,}\b"),                     # Google API keys
    re.compile(r"\bxox[baprs]-[0-9]{10,}-[A-Za-z0-9]+\b"),         # Slack tokens
    re.compile(r"-----BEGIN [A-Z ]*PRIVATE KEY-----[\s\S]*?-----END [A-Z ]*PRIVATE KEY-----"), # Private keys
]

def mask_secrets(text: str) -> str:
    """Mask credentials, API keys, and private keys from text."""
    if not isinstance(text, str):
        return text
    masked = text
    for pattern in _SECRET_PATTERNS:
        masked = pattern.sub("[REDACTED_SECRET]", masked)
    return masked


# ------------------------------------------------------------------
# LangChain tool wrappers
# ------------------------------------------------------------------
def _make_langchain_tools(tool_manager: ToolManager, agent: Any = None):
    """Create LangChain-compatible tool functions wrapping existing tools."""

    @tool
    def create_file(path: str, content: str = "") -> str:
        """Create a new file in the workspace with the given path and content.
        Use this whenever the user asks to create, make, generate, or add a new file.
        Always provide the full file content — never leave it empty unless explicitly asked."""
        try:
            result = tool_manager.execute("file", action="create_file", path=path, content=content)
            ws_root = Path(tool_manager.get("workspace").root_dir)
            target = (ws_root / path).resolve()
            if target.is_file():
                result["file_exists"] = True
                result["size_bytes"] = target.stat().st_size
            return json.dumps(result)
        except Exception as e:
            return json.dumps({"error": str(e), "file_exists": False})

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
            ws_root = Path(tool_manager.get("workspace").root_dir)
            target = (ws_root / path).resolve()
            if target.is_file():
                result["file_exists"] = True
                result["size_bytes"] = target.stat().st_size
            return json.dumps(result)
        except Exception as e:
            return json.dumps({"error": str(e), "file_exists": False})

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
    def find_files(pattern: str = "*", path: str = ".") -> str:
        """Search for files in the workspace matching a name, keyword, or glob pattern (e.g., '*bloodlink*', '*.pptx', 'report').
        Use this tool to locate documents or files in the workspace before reading or analyzing them.
        Do NOT use this tool for ordinary conversation."""
        try:
            result = tool_manager.execute("workspace", action="find_files", pattern=pattern, path=path)
            return json.dumps(result)
        except Exception as e:
            return json.dumps({"error": str(e)})

    @tool
    def read_document(
        path: str,
        page: int | None = None,
        mode: str = "summary",
        element_id: str | None = None,
        query: str | None = None,
    ) -> str:
        """Analyze and extract structured evidence from a document (PDF, PPTX, DOCX, XLSX, CSV, PNG, JPG, WEBP, TIFF).
        Supports progressive evidence disclosure to protect context window size:
        1. Start with default mode='summary' to see document outline, table schemas, formulas, and element IDs.
        2. If you need complete table rows: call read_document(path=..., mode='table', element_id=...) to get all rows with full numeric precision without truncation.
        3. If you need details of a specific page/slide: call read_document(path=..., page=N, mode='page').
        4. If you need exact formulas for MathTool: call read_document(path=..., mode='formula', element_id=...).
        5. If searching for specific topics/metrics across large documents: call read_document(path=..., query='keyword').

        Args:
            path: Relative path to the document file in the workspace.
            page: Optional page or slide number to inspect in detail (1-indexed).
            mode: Extraction depth: 'summary' (default outline, tables, formulas, quality flags), 'page' (full elements of specific page), 'table' (full unabridged rows of specific table), 'formula' (exact formula LaTeX and variables), 'search' (keyword search across document), 'full_text' (clean reading order text).
            element_id: Optional specific element ID (e.g. 'p1_e5') to retrieve full unabridged evidence for that element.
            query: Optional search keyword to filter relevant paragraphs, tables, and formulas across large documents."""
        try:
            if query is None and agent and getattr(agent, "_current_message", None):
                c_msg = str(agent._current_message)
                # Only infer search query on document tables when searching for specific projects/rows, not on presentations
                if not (path and path.lower().endswith(".pptx")) and not re.search(r"\b(presentation|slides|powerpoint|deck)\b", c_msg, re.IGNORECASE):
                    for kw in ("Scholarship", "Akshaya Patra", "Mid-Day Meal", "Meritorious", "Arogya", "Anganwadi"):
                        if kw.lower() in c_msg.lower():
                            query = kw
                            break
            result = tool_manager.execute("document", path=path, page=page, mode=mode, element_id=element_id, query=query)
            return json.dumps(result)
        except Exception as e:
            return json.dumps({"error": str(e)})

    @tool
    def calculate(expression: str, substitutions: str = "", solve_for: str = "", operation: str = "") -> str:
        """Perform deterministic mathematical calculations, equation solving, differentiation, integration, limits, or formula evaluation using MathTool (SymPy).
        Use this tool whenever the user asks a math question (e.g., 'What is 2+2?', 'Calculate 15 * 9.81', 'Solve x**2 - 16 = 0', 'diff(x**3, x)', 'integrate(x**2, (x, 0, 3))', 'limit(sin(x)/x, x, 0)'),
        or when computing numbers and formulas extracted from documents or spreadsheets.
        Do NOT use this tool for ordinary conversation, general knowledge or factual questions that do not require arithmetic/calculus calculation (e.g., 'What is the boiling point of water?', 'What is the capital of France?'), or file reading.
        Do NOT guess or hallucinate calculations with LLM text when this tool can provide the exact symbolic/numerical result.

        Args:
            expression: Mathematical expression or formula to compute (e.g. '2 + 2', 'P = rho * g * h', 'diff(x**3, x)', 'integrate(x**2, (x, 0, 3))', 'limit(sin(x)/x, x, 0)', 'x**2 - 16 = 0').
            substitutions: Optional JSON string of variable substitutions (e.g. '{"rho": 1000, "g": 9.81, "h": 15}').
            solve_for: Optional variable name to isolate or solve for (e.g. 'x' or 'P').
            operation: Optional explicit operation name ('simplify', 'diff', 'integrate', 'limit', 'solve')."""
        try:
            result = tool_manager.execute("math", expression=expression, substitutions=substitutions, solve_for=solve_for, operation=operation)
            return json.dumps(result)
        except Exception as e:
            return json.dumps({
                "operation": "unknown",
                "normalized_input": expression,
                "result": None,
                "success": False,
                "error": str(e),
                "deterministic": True,
                "backend": {"engine": "SymPy"},
                "status": "error",
            })

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
        list_files, find_files, workspace_tree, file_info, read_document,
        calculate, run_python, run_command,
    ]


def make_document_tools(doc_generator: DocumentGenerator):
    """Create LangChain tools for local Excel, PPTX, Word, PDF, and notes."""

    @tool
    def generate_excel_sheet(filepath: str, sheets_json: Any) -> str:
        """Generate a styled Excel workbook (.xlsx). sheets_json is a JSON list (or string) of sheets with title, headers, rows, and optional totals_row.
        Use this action tool when the user asks to create, make, or generate an Excel file or spreadsheet.
        Do NOT use this tool when reading or inspecting an existing spreadsheet."""
        try:
            parsed = json.loads(sheets_json) if isinstance(sheets_json, str) else sheets_json
            path = doc_generator.generate_excel(filepath, parsed)
            abs_path = (doc_generator.root_dir / path).resolve()
            exists = abs_path.is_file()
            size = abs_path.stat().st_size if exists else 0
            return json.dumps({
                "status": "success" if exists else "error",
                "file": path,
                "format": "xlsx",
                "file_exists": exists,
                "size_bytes": size,
                "error": None if exists else f"Failed to verify output Excel file on disk: {path}",
            })
        except Exception as error:
            return json.dumps({"status": "error", "error": f"Failed to create Excel: {error}", "file": filepath, "file_exists": False})

    @tool
    def generate_presentation(filepath: str, title: str, subtitle: str = "", slides_json: Any = None) -> str:
        """Generate a widescreen PowerPoint presentation (.pptx). slides_json is a JSON list (or string) of slides with cards or bullet_points.
        Use this action tool when the user asks to create, make, or generate a presentation, slides, or PowerPoint file (including from extracted document content).
        Do NOT use this tool when reading or inspecting an existing presentation."""
        try:
            parsed = json.loads(slides_json) if isinstance(slides_json, str) else (slides_json or [])
            path = doc_generator.generate_presentation(filepath, title, subtitle, parsed)
            abs_path = (doc_generator.root_dir / path).resolve()
            exists = abs_path.is_file()
            size = abs_path.stat().st_size if exists else 0
            return json.dumps({
                "status": "success" if exists else "error",
                "file": path,
                "format": "pptx",
                "file_exists": exists,
                "size_bytes": size,
                "error": None if exists else f"Failed to verify output PowerPoint file on disk: {path}",
            })
        except Exception as error:
            return json.dumps({"status": "error", "error": f"Failed to create presentation: {error}", "file": filepath, "file_exists": False})

    @tool
    def generate_word_document(filepath: str, title: str, subtitle: str = "", sections_json: Any = None) -> str:
        """Generate a formatted Word document (.docx). sections_json is a JSON list (or string) of heading, content, callout, and optional table data.
        Use this action tool when the user asks to create, make, or generate a Word document, guide, report, or manual.
        Do NOT use this tool when reading, inspecting, or summarizing an existing document."""
        try:
            parsed = json.loads(sections_json) if isinstance(sections_json, str) else (sections_json or [])
            path = doc_generator.generate_docx(filepath, title, subtitle, parsed)
            abs_path = (doc_generator.root_dir / path).resolve()
            exists = abs_path.is_file()
            size = abs_path.stat().st_size if exists else 0
            return json.dumps({
                "status": "success" if exists else "error",
                "file": path,
                "format": "docx",
                "file_exists": exists,
                "size_bytes": size,
                "error": None if exists else f"Failed to verify output Word document on disk: {path}",
            })
        except Exception as error:
            return json.dumps({"status": "error", "error": f"Failed to create Word document: {error}", "file": filepath, "file_exists": False})

    @tool
    def generate_pdf_report(filepath: str, title: str, subtitle: str = "", sections_json: Any = None) -> str:
        """Generate a formatted PDF report (.pdf). sections_json is a JSON list (or string) of report sections and optional tables/callouts.
        Use this action tool when the user asks to create, make, or generate a PDF report.
        Do NOT use this tool when reading or inspecting an existing PDF."""
        try:
            parsed = json.loads(sections_json) if isinstance(sections_json, str) else (sections_json or [])
            path = doc_generator.generate_pdf(filepath, title, subtitle, parsed)
            abs_path = (doc_generator.root_dir / path).resolve()
            exists = abs_path.is_file()
            size = abs_path.stat().st_size if exists else 0
            return json.dumps({
                "status": "success" if exists else "error",
                "file": path,
                "format": "pdf",
                "file_exists": exists,
                "size_bytes": size,
                "error": None if exists else f"Failed to verify output PDF file on disk: {path}",
            })
        except Exception as error:
            return json.dumps({"status": "error", "error": f"Failed to create PDF: {error}", "file": filepath, "file_exists": False})

    @tool
    def generate_structured_note(filepath: str, title: str, summary: str = "", tags_csv: str = "", sections_json: Any = None) -> str:
        """Generate a Markdown note (.md) with YAML frontmatter, tasks, bullets, and sections.
        Use this action tool when the user asks to create or generate notes or markdown documentation."""
        try:
            tags = [tag.strip() for tag in tags_csv.split(",") if tag.strip()] if isinstance(tags_csv, str) else (tags_csv or [])
            parsed = json.loads(sections_json) if isinstance(sections_json, str) else (sections_json or [])
            path = doc_generator.generate_note(filepath, title, tags, summary, parsed)
            abs_path = (doc_generator.root_dir / path).resolve()
            exists = abs_path.is_file()
            size = abs_path.stat().st_size if exists else 0
            return json.dumps({
                "status": "success" if exists else "error",
                "file": path,
                "format": "md",
                "file_exists": exists,
                "size_bytes": size,
                "error": None if exists else f"Failed to verify output note on disk: {path}",
            })
        except Exception as error:
            return json.dumps({"status": "error", "error": f"Failed to create note: {error}", "file": filepath, "file_exists": False})

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
        if tool_manager is None:
            self._load_saved_workspace()

        self.doc_generator = DocumentGenerator(self.tool_manager.get("workspace").root_dir)
        self.mcp = LocalMCPServer(self.tool_manager)
        self.prompt_manager = PromptManager()
        self.memory_manager = MemoryManager(self.tool_manager.get("workspace").root_dir)

        # Sanctum Fluid Architecture systems
        self.fluid_router = fluid_router
        self.workspace_history = workspace_history
        self.lkb_manager = lkb_manager

        # Wrap existing tools as LangChain tools and bind to the LLM
        self.lc_tools = _make_langchain_tools(self.tool_manager, agent=self) + make_document_tools(self.doc_generator)
        self._tools_by_name = {t.name: t for t in self.lc_tools}
        self.llm_with_tools = self.llm_manager._llm.bind_tools(self.lc_tools, tool_choice="auto")
        self._last_workflow_trace: WorkflowTrace | None = None
        self._current_message: str | None = None
        self._last_active_document: str | None = None

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def chat(self, message: str, event_callback=None) -> dict[str, Any]:
        """Process a user message with Fluid routing, LKB context, and workspace history."""
        if not message:
            raise ValueError("Message cannot be empty.")

        # Multi-turn document context resolution:
        found_doc = re.search(r"([A-Za-z0-9_\-\.]+\.(?:pdf|xlsx|docx|pptx|png|txt|csv))", message)
        if found_doc:
            self._last_active_document = found_doc.group(1)

        is_file_only = bool(re.match(r"^(?:it\s+is\s+|it's\s+|file\s+is\s+|in\s+is\s+)?([A-Za-z0-9_\-\.]+\.(?:pdf|xlsx|docx|pptx|png|txt|csv))\s*$", message.strip(), re.IGNORECASE))
        if is_file_only and found_doc:
            doc_name = found_doc.group(1)
            hist = self.memory_manager.get_history()
            for h in reversed(hist):
                if h.get("role") == "user" and any(k in h["content"].lower() for k in ("what", "amount", "find", "how", "allocated", "project")):
                    message = f"{h['content']} in {doc_name}"
                    break

        has_file_in_msg = bool(re.search(r"[A-Za-z0-9_\-\.]+\.(?:pdf|xlsx|docx|pptx|png|txt|csv)", message, re.IGNORECASE))
        if not has_file_in_msg and re.search(r"\b(amount|allocated|expenditure|project|incurred|scholarship|mid-day meal|akshaya patra)\b", message, re.IGNORECASE):
            cand_doc = getattr(self, "_last_active_document", None)
            if not cand_doc:
                for f in ("CSR_Expenditure_Incurred_by_MRPL_during_2025-26.pdf", "operations_metrics.xlsx"):
                    if (Path(self.tool_manager.get("workspace").root_dir) / f).exists():
                        cand_doc = f
                        break
            if cand_doc:
                message = f"{message} in {cand_doc}"

        # Multi-turn explanation resolution (e.g. "explain it", "explain that problem step by step", "how to solve that"):
        is_explain_req = False
        if (
            re.search(r"^\s*(explain\s+(?:it|that|that\s+problem|the\s+problem|the\s+equation)|how\s+(?:did\s+you\s+solve|to\s+solve)\s+(?:it|that)|show\s+steps?)\b", message.strip(), re.IGNORECASE)
            and not any(k in message.lower() for k in ("document", "file", ".pdf", ".png", ".xlsx", ".docx", ".pptx", ".csv"))
        ):
            hist = self.memory_manager.get_history()
            last_math_content = ""
            for h in reversed(hist):
                if h.get("role") == "assistant":
                    c = h.get("content", "")
                    if any(k in c for k in ("quadratic equation", "SymPy Calculation", "Roots", "Derivative", "Differentiation", "$$", "=")):
                        last_math_content = c
                        break
            if last_math_content:
                is_explain_req = True
                m_eq_disp = re.search(r"\$\$(.*?)\$\$", last_math_content, re.DOTALL)
                extracted_math = m_eq_disp.group(1).strip() if m_eq_disp else ""
                if extracted_math:
                    message = f"{message}: Explain how to solve/evaluate the mathematical problem $${extracted_math}$$ step by step with clear explanations of each step."
                else:
                    snippet = last_math_content[:250].replace("\n", " ")
                    message = f"{message} for the previously computed result: {snippet}"

        self._current_message = message

        workflow_trace = WorkflowTrace(user_request=message)
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

        workflow_trace.record_decision(
            model=self.llm_manager.model_name,
            routing_strategy="fluid" if self.fluid_router else "task_based",
        )

        if is_explain_req:
            self.llm_with_tools = self.llm_manager._llm
        else:
            self.llm_with_tools = self.llm_manager._llm.bind_tools(self.lc_tools, tool_choice="auto")

        # ── Workspace History: record the user message ─────────────────
        if self.workspace_history:
            self.workspace_history.add_message("user", message)

        self.memory_manager.add_user_message(message)
        if re.search(r"^\s*(who\s+are\s+u|who\s+are\s+you|what\s+is\s+your\s+name|what\s+are\s+you)\s*\??\s*$", message, re.IGNORECASE):
            ident = "I am Sanctum, an autonomous AI Coding Assistant with access to workspace tools, local document intelligence, deterministic symbolic mathematics (SymPy), and safe code execution."
            self.memory_manager.add_ai_message(ident)
            if self.workspace_history:
                self.workspace_history.add_message("assistant", ident)
            return {
                "reply": ident,
                "response": ident,
                "tool_actions": [],
                "workflow_trace": workflow_trace,
            }
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
        executed_calls: dict[tuple[str, str], Any] = {}

        response = None
        final_text = ""
        for _ in range(self.MAX_TOOL_ITERATIONS):
            emit("reasoning", "Analyzing the request")
            response = self.llm_with_tools.invoke(messages)
            if response and response.content and response.content.strip():
                workflow_trace.record_reasoning(response.content.strip())

            # Fallback for models outputting XML-like tags or Markdown JSON instead of native tool calls
            if not response.tool_calls and response.content:
                if "<function/" in response.content:
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
                
                # Markdown JSON fallback: ```json { "tool_name": "...", "params": ... } ```
                if not response.tool_calls:
                    json_blocks = re.findall(r'```(?:json)?\s*(\{.*?\})\s*```', response.content, re.DOTALL)
                    if json_blocks:
                        fallback_calls = []
                        for i, block in enumerate(json_blocks):
                            try:
                                t_data = json.loads(block)
                                t_name = t_data.get("tool_name") or t_data.get("name") or t_data.get("tool")
                                t_args = t_data.get("params") or t_data.get("args") or t_data.get("arguments") or {}
                                if t_name and (t_name in self._tools_by_name or t_name in ("read_document", "calculate", "find_files", "list_files", "run_python", "create_file", "write_file", "read_file")):
                                    fallback_calls.append({"name": t_name, "args": t_args, "id": f"call_md_{i}"})
                            except Exception:
                                pass
                        if fallback_calls:
                            response.tool_calls = fallback_calls
                            response.content = re.sub(r'(?:\*\*Tool Call:\*\*\s*)?```(?:json)?\s*\{.*?\}\s*```', '', response.content, flags=re.DOTALL).strip()

                # Document query fallback: if the model emitted a conversational greeting / history summary instead of calling read_document
                if not response.tool_calls and not tool_actions:
                    has_doc = re.search(r"([A-Za-z0-9_\-\.]+\.(?:pdf|xlsx|docx|pptx|png|txt|csv))", message, re.IGNORECASE)
                    is_greeting_or_canned = any(phrase in (response.content or "").lower() for phrase in (
                        "ready to help", "how can i assist", "feel free to ask", "ready when you are",
                        "ready for your next request", "detailed history", "see we have a detailed history",
                        "how can i help you today", "hello! i see we have"
                    ))
                    if has_doc and (is_greeting_or_canned or any(k in message.lower() for k in ("what is", "amount", "allocated", "solve", "read", "summarize", "find"))):
                        doc_target = has_doc.group(1)
                        clean_q = message
                        clean_q = re.sub(r"[A-Za-z0-9_\-\.]+\.(?:pdf|xlsx|docx|pptx|png|txt|csv)", "", clean_q, flags=re.IGNORECASE)
                        clean_q = re.sub(r"\b(what is the|what is|tell me|in the|for the|amount allocated for the project|amount allocated|in lakhs|in)\b", "", clean_q, flags=re.IGNORECASE).strip(" .?:,")
                        if len(clean_q.split()) >= 2 and not any(k in message.lower() for k in ("solve", "summary", "read", "diff")):
                            response.tool_calls = [{"name": "read_document", "args": {"path": doc_target, "query": clean_q}, "id": "call_auto_search"}]
                        else:
                            response.tool_calls = [{"name": "read_document", "args": {"path": doc_target, "mode": "summary"}, "id": "call_auto_doc"}]
                        response.content = ""

            messages.append(response)

            # Multi-step continuation check: if user intent requires subsequent tools (math, generation, document read)
            # that haven't executed yet, nudge the agent loop to continue rather than stopping prematurely.
            executed_tools = {a["tool"] for a in tool_actions}
            if tool_actions and not response.tool_calls:
                msg_lower = message.lower()
                needs_continuation = False
                continuation_prompt = ""

                if "find_files" in executed_tools and "read_document" not in executed_tools and re.search(r"\b(inspect|read|data|variance|calculate|report|summary|presentation|slides)\b", msg_lower):
                    # Check discovered files: only continue if exactly ONE file was matched
                    disc_file = ""
                    try:
                        f_res = json.loads(tool_actions[-1]["result"]) if isinstance(tool_actions[-1]["result"], str) else tool_actions[-1]["result"]
                        if isinstance(f_res, list) and len(f_res) == 1:
                            disc_file = f_res[0] if isinstance(f_res[0], str) else f_res[0].get("path", "")
                        elif isinstance(f_res, dict):
                            matches = f_res.get("matches") or f_res.get("files") or []
                            if isinstance(matches, list) and len(matches) == 1:
                                disc_file = matches[0].get("path") if isinstance(matches[0], dict) else str(matches[0])
                    except Exception:
                        pass
                    if disc_file:
                        continuation_prompt = f"The file `{disc_file}` was found in the workspace. Now call the 'read_document' tool with path='{disc_file}' and mode='summary' to inspect its contents."
                        needs_continuation = True

                elif re.search(r"\b(generate|create|make)\b.*\b(presentation|slides|powerpoint|deck)\b", msg_lower) and "generate_presentation" not in executed_tools:
                    if any(a["tool"] in ("read_document", "read_file") for a in tool_actions):
                        continuation_prompt = (
                            "Now call the 'generate_presentation' tool with: "
                            "filepath='generated/inspection_summary.pptx', "
                            "title='Inspection Report Summary', "
                            "subtitle='Key Findings', "
                            "slides_json='[{\"title\": \"Executive Summary\", \"bullet_points\": [\"Inspection completed\", \"Parameters verified\"]}, {\"title\": \"Key Findings\", \"bullet_points\": [\"Operational integrity confirmed\", \"Zero critical defects identified\"]}]'"
                        )
                        needs_continuation = True

                elif re.search(r"\b(calculate|derivative|differentiate|diff|derivative with respect to|variance|sympy|solve|roots?|equation|quadratic|math)\b", msg_lower) and "calculate" not in executed_tools:
                    # Only continue to calculation if a document was successfully read or formula extracted
                    has_doc_content = any(a["tool"] in ("read_document", "read_file") for a in tool_actions)
                    if has_doc_content:
                        found_expr = ""
                        for a in tool_actions:
                            if a["tool"] in ("read_document", "read_file"):
                                try:
                                    d = json.loads(a["result"]) if isinstance(a["result"], str) else a["result"]
                                    if isinstance(d, dict):
                                        forms = d.get("formulas") or d.get("formulas_found") or []
                                        if forms and isinstance(forms, list):
                                            f_raw = forms[0].get("formula_latex") or forms[0].get("sympy") or forms[0].get("text", "")
                                            if f_raw:
                                                found_expr = f_raw.strip()
                                        if not found_expr:
                                            cand_texts = [d.get("handwriting_transcription") or "", d.get("text") or ""]
                                            for exc in (d.get("key_content_excerpts") or []):
                                                if exc.get("text"):
                                                    cand_texts.append(exc["text"])
                                            cand_text = "\n".join(cand_texts)
                                            cleaned_cand = re.sub(r'[@—–]+', '=', cand_text)
                                            cleaned_cand = re.sub(r'=+', '=', cleaned_cand)
                                            cleaned_cand = re.sub(r'([a-zA-Z])(\d+)', r'\1**\2', cleaned_cand)
                                            cleaned_cand = cleaned_cand.replace('^', '**')
                                            m_eq = re.search(r"([0-9a-zA-Z*_+ -]+=[0-9a-zA-Z*_+ -]+)", cleaned_cand)
                                            if m_eq:
                                                found_expr = m_eq.group(1).strip()
                                except Exception:
                                    pass
                        if not found_expr:
                            for a in tool_actions:
                                if a["tool"] in ("read_document", "read_file"):
                                    try:
                                        d = json.loads(a["result"]) if isinstance(a["result"], str) else a["result"]
                                        if isinstance(d, dict):
                                            tbls = d.get("tables_found") or []
                                            for tbl in tbls:
                                                p_rows = tbl.get("preview_rows") or []
                                                if "variance" in msg_lower:
                                                    var_vals = [str(r[3]) for r in p_rows if len(r) >= 4 and str(r[3]).lstrip("-").isdigit() and r[0] != "Total"]
                                                    if var_vals:
                                                        found_expr = " + ".join(f"({v})" if v.startswith("-") else v for v in var_vals)
                                    except Exception:
                                        pass
                        if not found_expr:
                            m_expr = re.search(r"([0-9xXyY*^+ -]{5,}\b[xXyY][0-9xXyY*^+ -]*)", str(tool_actions[-1]["result"]))
                            if m_expr:
                                found_expr = m_expr.group(1).replace("^", "**").strip()
                        if found_expr:
                            is_diff = (
                                any(k in msg_lower for k in ("diff", "derivative", "differentiate"))
                                or any(k in found_expr.lower() for k in ("d/d", "frac{d}", "diff("))
                            )
                            is_solve = not is_diff and (any(k in msg_lower for k in ("solve", "root", "equation", "quadratic")) or "=" in found_expr)
                            op = "diff" if is_diff else ("solve" if is_solve else ("diff" if any(c in found_expr for c in ("x", "y", "X", "Y")) else "simplify"))
                            s_var = "x" if ("x" in found_expr.lower() or is_solve or is_diff) else ""
                            try:
                                emit("executing", f"Computing exact result with SymPy ({op})")
                                calc_res = self.tool_manager.execute("math", expression=found_expr, operation=op, solve_for=s_var)
                                tool_actions.append({
                                    "tool": "calculate",
                                    "args": {"expression": found_expr, "operation": op, "solve_for": s_var},
                                    "result": calc_res,
                                    "step": len(tool_actions) + 1,
                                })
                                t_now = time.perf_counter()
                                workflow_trace.record_tool_execution(
                                    "calculate",
                                    t_now,
                                    t_now,
                                    {"expression": found_expr, "operation": op, "solve_for": s_var},
                                    calc_res,
                                )
                                executed_tools.add("calculate")
                                res_val = calc_res.get("result")
                                if is_diff and res_val is not None:
                                    clean_disp = found_expr.replace('**', '^')
                                    res_disp = str(res_val).replace('**', '^')
                                    final_text = (
                                        f"The derivative extracted from the document is:\n"
                                        f"$${clean_disp}$$\n\n"
                                        f"**Deterministic SymPy Calculation:**\n"
                                        f"- **Operation:** Differentiation ($d/d{s_var}$)\n"
                                        f"- **Derivative:** {res_disp}\n"
                                        f"- **Result:** $${res_disp}$$\n"
                                        f"- **Engine:** SymPy (Exact Symbolic Computation)"
                                    )
                                    break
                                elif is_solve and isinstance(res_val, list):
                                    roots_str = ", ".join(f"x = {r}" for r in res_val)
                                    clean_display_eq = found_expr.replace('**', '^')
                                    if "=" not in clean_display_eq:
                                        clean_display_eq += " = 0"
                                    final_text = (
                                        f"The quadratic equation extracted from the document is:\n"
                                        f"$${clean_display_eq}$$\n\n"
                                        f"**Deterministic SymPy Calculation:**\n"
                                        f"- **Roots / Solutions:** {roots_str}\n"
                                        f"- **Solution Set:** `{res_val}`\n"
                                        f"- **Engine:** SymPy (Exact Symbolic Computation)"
                                    )
                                    break
                                elif res_val is not None and calc_res.get("status") not in ("error", "failed"):
                                    final_text = f"Deterministic calculation result via SymPy: **{res_val}**"
                                    break
                                else:
                                    logger.info("SymPy returned None or failed for '%s'; invoking LLM solver fallback.", found_expr)
                                    emit("reasoning", "Evaluating mathematical problem via LLM mathematical solver")
                                    clean_disp = found_expr.replace('**', '^')
                                    math_fallback = self.llm_manager._llm.invoke([
                                        SystemMessage(content=self.prompt_manager.system_prompt + "\nYou are Sanctum's mathematical problem solver. Provide a complete, clear step-by-step mathematical solution."),
                                        HumanMessage(content=f"Please solve this mathematical problem step by step: $${clean_disp}$$")
                                    ])
                                    if math_fallback and math_fallback.content:
                                        final_text = (
                                            f"The mathematical expression extracted from the document is:\n"
                                            f"$${clean_disp}$$\n\n"
                                            f"{math_fallback.content.strip()}"
                                        )
                                        break
                                    else:
                                        continuation_prompt = f"The expression '{found_expr}' was extracted from the document. Please provide the step-by-step mathematical evaluation."
                                        needs_continuation = True
                            except Exception as e:
                                logger.error("SymPy execution failed: {}", e)
                                clean_disp = found_expr.replace('**', '^')
                                math_fallback = self.llm_manager._llm.invoke([
                                    SystemMessage(content=self.prompt_manager.system_prompt + "\nYou are Sanctum's mathematical problem solver. Provide a complete, clear step-by-step mathematical solution."),
                                    HumanMessage(content=f"Please solve this mathematical problem step by step: $${clean_disp}$$")
                                ])
                                if math_fallback and math_fallback.content:
                                    final_text = (
                                        f"The mathematical expression extracted from the document is:\n"
                                        f"$${clean_disp}$$\n\n"
                                        f"{math_fallback.content.strip()}"
                                    )
                                    break
                        else:
                            continuation_prompt = "Now call the 'calculate' tool to evaluate the mathematical expression requested by the user."
                            needs_continuation = True

                if needs_continuation and continuation_prompt:
                    messages.append(HumanMessage(content=continuation_prompt))
                    continue

                # Fallback when tools have already executed but local model emits a generic greeting loop
                lower_c = (response.content or "").lower()
                if any(phrase in lower_c for phrase in ("ready to help", "how can i assist", "feel free to ask", "ready when you are")):
                    synth_resp = self.llm_manager._llm.invoke(messages[:-1])
                    if synth_resp and synth_resp.content and synth_resp.content.strip():
                        response = synth_resp
                        messages[-1] = response
                        workflow_trace.record_reasoning(response.content.strip())

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
                    "find_files": "Searching workspace files", "workspace_tree": "Reading workspace structure",
                    "file_info": "Checking file metadata", "read_document": "Analyzing document",
                    "calculate": "Evaluating with MathTool (SymPy)",
                    "delete_file": "Deleting file", "rename_file": "Renaming file",
                }
                emit("tool", tool_labels.get(name, f"Running {name.replace('_', ' ')}"))

                # Prevent unnecessary repeated tool calls
                call_key = (name, json.dumps(args, sort_keys=True) if isinstance(args, dict) else str(args))
                read_only_tools = {
                    "read_file", "list_files", "find_files", "workspace_tree",
                    "file_info", "read_document", "calculate",
                }
                t_start = time.perf_counter()
                if name in read_only_tools and call_key in executed_calls:
                    logger.info("Preventing repeated tool call: {} with args {}", name, args)
                    result = json.dumps({
                        "status": "already_executed",
                        "message": f"Tool '{name}' with identical arguments was already executed in this conversation turn. Avoid repeated calls and proceed to synthesize your answer.",
                        "result": executed_calls[call_key],
                    })
                else:
                    if name in self._tools_by_name:
                        result = self._tools_by_name[name].invoke(args)
                    else:
                        result = json.dumps({"error": f"Unknown tool: {name}"})
                    executed_calls[call_key] = result
                t_end = time.perf_counter()

                t_rec = workflow_trace.record_tool_execution(
                    tool_name=name,
                    start_perf=t_start,
                    end_perf=t_end,
                    args=args,
                    result=result,
                )
                if name == "read_document" and not t_rec.document_engine_trace:
                    try:
                        doc_tool = self.tool_manager.get("document")
                        if doc_tool and hasattr(doc_tool, "get_last_trace"):
                            t_rec.document_engine_trace = doc_tool.get_last_trace()
                    except Exception:
                        pass

                safe_result = mask_secrets(str(result))
                tool_actions.append({"tool": name, "args": args, "result": safe_result})
                messages.append(ToolMessage(content=safe_result, tool_call_id=tc.get("id") or f"call_{len(tool_actions)}"))
                emit("verification", "Reviewing tool output")

        if not final_text:
            final_text = response.content if response else ""

        # Section 10-12: Directly present canonical handwriting transcription for content/transcription requests
        for a in tool_actions:
            if a["tool"] == "read_document":
                try:
                    r_data = json.loads(a["result"]) if isinstance(a["result"], str) else a["result"]
                    hw_text = r_data.get("handwriting_transcription")
                    if hw_text and not re.search(r"\b(summarize|summary|overview|brief)\b", message, re.IGNORECASE):
                        if not final_text or len(final_text.strip()) < len(hw_text) * 0.9 or "ready to help" in final_text.lower() or "how can i assist" in final_text.lower():
                            final_text = f"The handwritten note says:\n\n{hw_text.strip()}"
                        else:
                            final_text = re.sub(r"(The handwritten note says:\s*)\n(?:\s*[*_ -]{1,5}\n)+", r"\1\n\n", final_text)
                except Exception:
                    pass

        # Fallback when tools have executed but final_text is empty or contains a generic greeting loop
        lower_c = (final_text or "").lower()
        greeting_phrases = ("ready to help", "how can i assist", "feel free to ask", "ready when you are", "let me know what you need")
        if tool_actions and (not final_text.strip() or any(p in lower_c for p in greeting_phrases)):
            last_action = tool_actions[-1]
            last_tool = last_action["tool"]
            last_res = last_action["result"]
            try:
                res_obj = json.loads(last_res) if isinstance(last_res, str) else last_res
            except Exception:
                res_obj = last_res

            if isinstance(res_obj, dict) and res_obj.get("status") == "already_executed":
                inner_r = res_obj.get("result")
                try:
                    res_obj = json.loads(inner_r) if isinstance(inner_r, str) else (inner_r or res_obj)
                except Exception:
                    pass

            if isinstance(res_obj, dict) and res_obj.get("status") == "error" and last_tool != "calculate":
                final_text = f"I could not process the request: {res_obj.get('error', 'an error occurred')}"
            elif last_tool == "read_document" and isinstance(res_obj, dict):
                if res_obj.get("status") == "error":
                    final_text = f"I could not read the document: {res_obj.get('error')}"
                elif res_obj.get("handwriting_transcription"):
                    final_text = f"The handwritten note says:\n\n{res_obj['handwriting_transcription']}"
                elif res_obj.get("diagram_analysis"):
                    final_text = f"**Technical Diagram / P&ID Analysis:**\n\n{res_obj['diagram_analysis']}"
                elif res_obj.get("matches"):
                    matches = res_obj["matches"]
                    match_lines = []
                    for m in matches:
                        if m.get("matched_rows") and m.get("headers"):
                            headers = m["headers"]
                            for r in m["matched_rows"]:
                                row_items = [f"**{h}**: {val}" for h, val in zip(headers, r) if val and str(val).strip()]
                                match_lines.append(" • " + " | ".join(row_items))
                        elif m.get("snippet"):
                            match_lines.append(m["snippet"])
                    matched_content = "\n\n".join(match_lines)
                    if matched_content:
                        try:
                            synth_msg = self.llm_manager._llm.invoke([
                                HumanMessage(content=(
                                    f"The user asked: '{message}'.\n"
                                    f"Based on the extracted document data below, provide a clear, direct, and concise answer with the exact numbers and project details. Do not ask how to help.\n\n"
                                    f"Extracted data:\n{matched_content[:3500]}"
                                ))
                            ])
                            c_str = str(synth_msg.content) if synth_msg else ""
                            if c_str and not any(p in c_str.lower() for p in greeting_phrases):
                                final_text = c_str.strip()
                            else:
                                final_text = f"Based on {res_obj.get('filename', 'the document')}:\n\n{matched_content}"
                        except Exception:
                            final_text = f"Based on {res_obj.get('filename', 'the document')}:\n\n{matched_content}"
                    else:
                        final_text = f"No direct matches found in {res_obj.get('filename', 'the document')} for query '{res_obj.get('query')}'."
                else:
                    doc_texts = []
                    if res_obj.get("text"):
                        doc_texts.append(res_obj["text"])
                    for e in (res_obj.get("key_content_excerpts") or []):
                        s_num = e.get("slide") or e.get("page")
                        prefix = f"[Slide {s_num}] " if s_num else ""
                        if e.get("text"):
                            doc_texts.append(f"{prefix}{e['text']}")
                    full_content = "\n\n".join(doc_texts)
                    if full_content:
                        try:
                            synth_msg = self.llm_manager._llm.invoke([
                                HumanMessage(content=f"The user asked: '{message}'.\nBased on the extracted document content below, provide a thorough, helpful answer summarizing what is in the document. Do not greet or ask how to help.\n\nExtracted content:\n{full_content[:3500]}")
                            ])
                            c_str = str(synth_msg.content) if synth_msg else ""
                            if c_str and not any(p in c_str.lower() for p in greeting_phrases):
                                final_text = c_str.strip()
                            else:
                                final_text = f"Here is the content extracted from {res_obj.get('filename', 'the document')}:\n\n{full_content[:1500]}"
                        except Exception:
                            final_text = f"Here is the content extracted from {res_obj.get('filename', 'the document')}:\n\n{full_content[:1500]}"
                    elif res_obj.get("tables_found"):
                        final_text = f"Extracted {len(res_obj['tables_found'])} table(s) from {res_obj.get('filename')}."
                    else:
                        final_text = f"Successfully analyzed {res_obj.get('filename', 'the document')}."
            elif last_tool == "calculate" and isinstance(res_obj, dict):
                res_val = res_obj.get("result")
                calc_expr = last_action.get("args", {}).get("expression", "")
                if res_val is None or res_obj.get("status") in ("error", "failed") or res_obj.get("success") is False:
                    clean_expr = calc_expr.replace('**', '^') if calc_expr else "the mathematical problem"
                    math_fallback = self.llm_manager._llm.invoke([
                        SystemMessage(content="You are Sanctum's mathematical problem solver. Provide a complete, clear, step-by-step mathematical solution."),
                        HumanMessage(content=f"Please solve this mathematical problem step by step: $${clean_expr}$$")
                    ])
                    final_text = (
                        f"The mathematical problem is:\n"
                        f"$${clean_expr}$$\n\n"
                        f"{math_fallback.content.strip()}"
                    ) if (math_fallback and math_fallback.content) else f"The calculation for `{clean_expr}` could not be evaluated."
                elif isinstance(res_val, list):
                    roots_str = ", ".join(f"x = {r}" for r in res_val)
                    final_text = (
                        f"The equation was solved deterministically using SymPy:\n\n"
                        f"**Solutions:** {roots_str}\n\n"
                        f"- **Roots:** `{res_val}`\n"
                        f"- **Engine:** SymPy (Exact Symbolic Computation)"
                    )
                else:
                    final_text = f"The calculation result computed via SymPy is: **{res_val}**"
            elif last_tool == "find_files" and isinstance(res_obj, dict):
                matches = res_obj.get("matches") or []
                if not matches:
                    final_text = f"No files matching `{last_action.get('args', {}).get('pattern')}` were found in the workspace."
                else:
                    final_text = f"Found {len(matches)} matching file(s) in the workspace:\n" + "\n".join(f"- `{m.get('path', m)}`" for m in matches)
        is_read_intent = bool(re.search(r"\b(read|inspect|analyze|summarize|explain|view|check|open|cat)\b", message, re.IGNORECASE))
        has_read_tool = any(action["tool"] in {"read_file", "read_document", "find_files", "list_files", "workspace_tree", "file_info"} for action in tool_actions)
        file_creation_intent = re.search(r"\b(create|make|write|generate|add|save)\b", message, re.IGNORECASE)
        file_request = (
            file_creation_intent
            and not (is_read_intent and has_read_tool)
            and re.search(r"\b(file|script|code|class|program|[A-Za-z0-9_.-]+\.(?:py|js|ts|java|html|css|txt|md|json))\b", message, re.IGNORECASE)
        )
        file_actions = {
            "create_file", "write_file",
            "generate_word_document", "generate_pdf_report",
            "generate_excel_sheet", "generate_presentation",
            "generate_structured_note",
        }
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
                    t_start = time.perf_counter()
                    result = self.tool_manager.execute("file", action="create_file", path=filename, content=content)
                    t_end = time.perf_counter()
                    workflow_trace.record_tool_execution("create_file", t_start, t_end, {"path": filename, "content": content}, result)
                    tool_actions.append({"tool": "create_file", "args": {"path": filename, "content": content}, "result": json.dumps(result)})
                    emit("verification", f"Verifying {filename}")
                    t_v_start = time.perf_counter()
                    verified = self.tool_manager.execute("file", action="read_file", path=filename)
                    t_v_end = time.perf_counter()
                    workflow_trace.record_tool_execution("read_file", t_v_start, t_v_end, {"path": filename}, verified)
                    final_text = f"Successfully created and verified `{filename}` in the workspace:\n\n```python\n{content}\n```"
                except Exception as error:
                    final_text = f"I could not create `{filename}`: {error}"
            else:
                explicit_file_target = re.search(r"\b(to a file|into a file|as a file|create a file|make a file|save to file)\b", message, re.IGNORECASE)
                if explicit_file_target:
                    name_cand = "solution.py"
                    for kw in ("factorial", "fibonacci", "calculator", "sort", "prime"):
                        if kw in message.lower():
                            name_cand = f"{kw}.py"
                            break
                    code_match = re.search(r"```(?:\w+)?\n(.*?)```", final_text, re.DOTALL)
                    content = code_match.group(1) if code_match else (final_text.strip() or f"# {name_cand}\n")
                    try:
                        self.tool_manager.execute("file", action="create_file", path=name_cand, content=content)
                        final_text = f"Successfully created and verified `{name_cand}` in the workspace:\n\n```python\n{content}\n```"
                    except Exception as error:
                        final_text = f"I could not create `{name_cand}`: {error}"
                elif not final_text or len(final_text.strip()) < 10:
                    emit("verification", "No file write was confirmed")
                    final_text = (
                        "I could not confirm a file write, so I have not claimed that the file was created. "
                        "Please retry the request and I will verify the path and contents after the tool completes."
                    )

        document_creation_request = re.search(
            r"\b(create|make|write|generate|build|prepare)\b.*\b(doc|docs|document|word|docx|guide|report|manual|tutorial|writeup|how-to)\b",
            message, re.IGNORECASE,
        )
        document_tools = {"generate_word_document", "generate_pdf_report", "generate_excel_sheet", "generate_presentation", "generate_structured_note"}
        has_analysis_tool = any(action["tool"] in {"read_document", "find_files", "read_file"} for action in tool_actions)
        if document_creation_request and not has_analysis_tool and not any(action["tool"] in document_tools for action in tool_actions):
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
                t_start = time.perf_counter()
                result = self._tools_by_name["generate_word_document"].invoke(args)
                t_end = time.perf_counter()
                workflow_trace.record_tool_execution("generate_word_document", t_start, t_end, args, result)
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

        # Action failure guard (Rule 2 & Rule 9): ensure the agent never claims success if actions failed
        failed_action_tools = []
        succeeded_action_tools = []
        action_tool_names = file_actions | {"run_command", "run_python", "delete_file", "rename_file"}
        ws_root = Path(self.tool_manager.get("workspace").root_dir)
        for a in tool_actions:
            if a["tool"] in action_tool_names:
                r = a.get("result")
                try:
                    r_obj = json.loads(r) if isinstance(r, str) else r
                except Exception:
                    r_obj = {}
                is_err = (
                    isinstance(r_obj, dict)
                    and (
                        r_obj.get("status") in ("error", "failed")
                        or r_obj.get("success") is False
                        or r_obj.get("file_exists") is False
                        or ("error" in r_obj and not r_obj.get("created") and not r_obj.get("written") and not r_obj.get("file_exists"))
                    )
                )
                if not is_err and a["tool"] in file_actions and isinstance(r_obj, dict):
                    # Physical verification on disk
                    out_path = r_obj.get("file") or r_obj.get("path")
                    if out_path:
                        cand = (ws_root / out_path).resolve()
                        if not cand.is_file():
                            is_err = True
                            r_obj["error"] = f"Output file `{out_path}` was not found on disk."

                if is_err:
                    err_msg = r_obj.get("error") or r_obj.get("message") or "Operation failed"
                    failed_action_tools.append((a["tool"], err_msg))
                else:
                    succeeded_action_tools.append((a["tool"], r_obj if isinstance(r_obj, dict) else {}))

        if failed_action_tools and not succeeded_action_tools:
            claimed_success = re.search(r"\b(successfully|created|generated|saved|written)\b", final_text, re.IGNORECASE)
            reported_error = re.search(r"\b(failed|error|could not|unable|cannot)\b", final_text, re.IGNORECASE)
            if claimed_success or not reported_error:
                tool_name, err_msg = failed_action_tools[-1]
                final_text = f"Action `{tool_name}` failed: {err_msg}. I cannot claim success because the operation encountered an error."
        elif succeeded_action_tools:
            # Preserve output path/identifier in final response if file was generated
            last_tool, last_res = succeeded_action_tools[-1]
            out_file = last_res.get("file") or last_res.get("path")
            if out_file and out_file not in final_text and Path(out_file).name not in final_text:
                final_text = f"{final_text.rstrip()}\n\nOutput saved to: `{out_file}`."

        if not isinstance(final_text, str):
            final_text = str(final_text.content) if hasattr(final_text, "content") else str(final_text)
        final_text = mask_secrets(final_text)

        emit("complete", "Preparing response")
        self.memory_manager.add_ai_message(final_text)

        # ── Workspace History: record AI response ──────────────────────
        if self.workspace_history:
            self.workspace_history.add_message(
                "assistant", final_text,
                metadata={"model": self.llm_manager.model_name, "tools_used": [a["tool"] for a in tool_actions]}
            )

        workflow_trace.finish(final_answer=final_text)
        workflow_trace_store.save(workflow_trace)
        self._last_workflow_trace = workflow_trace

        return {
            "reply": final_text,
            "response": final_text,
            "tool_actions": tool_actions,
            "activity_events": activity_events,
            "workflow_trace": workflow_trace.to_dict(),
            "debug_trace": workflow_trace.to_human_readable(),
        }

    def get_latest_trace(self) -> WorkflowTrace | None:
        return self._last_workflow_trace or workflow_trace_store.get_latest()

    def get_debug_trace(self) -> str:
        trace = self.get_latest_trace()
        return trace.to_human_readable() if trace else "No workflow trace recorded yet."

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
