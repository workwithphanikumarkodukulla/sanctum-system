"""Routes module. Defines all API endpoints for Sanctum Fluid Architecture."""

import json
import queue
import shutil
import tempfile
import threading
from pathlib import Path

from flask import Blueprint, request, jsonify, current_app, render_template, Response, stream_with_context, send_file
from werkzeug.utils import secure_filename

from sanctum_locker import restrict_file, unrestrict_file

from app.logger import logger

main_bp = Blueprint("main", __name__)


@main_bp.route("/")
def index():
    return render_template("index.html")


# ─────────────────────────────────────────────────────────────────────────────
# Chat
# ─────────────────────────────────────────────────────────────────────────────

@main_bp.route("/chat", methods=["POST"])
@main_bp.route("/api/chat", methods=["POST"])
def chat():
    data = request.get_json()
    if not data:
        return jsonify({"error": "Request body is missing."}), 400
    if "message" not in data:
        return jsonify({"error": "'message' field is required."}), 400
    message = data["message"].strip()
    if not message:
        return jsonify({"error": "Message cannot be empty."}), 400
    try:
        agent = current_app.agent
        result = agent.chat(message)
        wf_trace = result.get("workflow_trace")
        if hasattr(wf_trace, "to_dict"):
            wf_trace = wf_trace.to_dict()
        return jsonify({
            "reply": result["reply"],
            "model_used": result.get("model_used"),
            "duration_ms": result.get("duration_ms"),
            "duration_s": result.get("duration_s"),
            "tool_actions": result.get("tool_actions", []),
            "activity_events": result.get("activity_events", []),
            "workflow_trace": wf_trace,
            "debug_trace": result.get("debug_trace"),
        })
    except Exception:
        logger.exception("Error while processing chat request.")
        return jsonify({"error": "Internal Server Error."}), 500


@main_bp.route("/api/chat/stream", methods=["POST"])
def chat_stream():
    """Stream activity events from the real agent execution loop."""
    data = request.get_json() or {}
    message = str(data.get("message", "")).strip()
    if not message:
        return jsonify({"error": "Message cannot be empty."}), 400

    events = queue.Queue()
    agent = current_app.agent

    def run_agent():
        try:
            result = agent.chat(message, event_callback=lambda event: events.put({"type": "activity", **event}))
            events.put({"type": "result", **result})
        except Exception as error:
            logger.exception("Error while streaming chat request.")
            events.put({"type": "error", "message": str(error)})
        finally:
            events.put(None)

    threading.Thread(target=run_agent, daemon=True).start()

    @stream_with_context
    def generate():
        while True:
            event = events.get()
            if event is None:
                break
            yield f"data: {json.dumps(event)}\n\n"

    return Response(generate(), mimetype="text/event-stream", headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"})


# ─────────────────────────────────────────────────────────────────────────────
# System & Models
# ─────────────────────────────────────────────────────────────────────────────

@main_bp.route("/api/system", methods=["GET"])
def system_info():
    """Expose local model, MCP, Fluid routing, and data-sovereignty status."""
    return jsonify(current_app.agent.system_info())


@main_bp.route("/api/sovereign/network", methods=["GET"])
@main_bp.route("/api/network/audit", methods=["GET"])
def sovereign_network_audit():
    """Return live sovereign air-gap telemetry and packet egress logs."""
    from app.sovereign_network import sovereign_auditor
    return jsonify(sovereign_auditor.get_audit_summary())


@main_bp.route("/api/wireshark/pcap", methods=["GET"])
def download_wireshark_pcap():
    """Download authentic binary libpcap capture file verifiable with desktop Wireshark or tcpdump."""
    from app.sovereign_network import sovereign_auditor
    pcap_data = sovereign_auditor.generate_pcap_bytes(limit=100)
    return Response(
        pcap_data,
        mimetype="application/vnd.tcpdump.pcap",
        headers={
            "Content-Disposition": "attachment; filename=sanctum_airgap.pcap",
            "Content-Length": str(len(pcap_data)),
        },
    )


@main_bp.route("/api/wireshark/packets", methods=["GET"])
def get_wireshark_packets():
    """Return packet stream with dissection tree and hexdump for Wireshark UI."""
    from app.sovereign_network import sovereign_auditor
    summary = sovereign_auditor.get_audit_summary()
    return jsonify({
        "packets": summary.get("recent_events", []),
        "airgap_integrity_pct": summary.get("airgap_integrity_pct", 100.0),
        "external_calls_allowed": summary.get("external_calls_allowed", 0),
        "external_calls_blocked": summary.get("external_calls_blocked", 0),
        "loopback_calls_count": summary.get("loopback_calls_count", 0),
        "service_breakdown": summary.get("service_breakdown", {}),
    })


@main_bp.route("/api/wireshark/test-egress", methods=["POST"])
def test_wan_egress():
    """Trigger a live egress probe to demonstrate active airgap socket blocking."""
    from app.sovereign_network import sovereign_auditor
    data = request.get_json() or {}
    target = data.get("target", "api.openai.com")
    try:
        port = int(data.get("port", 443))
    except (TypeError, ValueError):
        port = 443
    result = sovereign_auditor.trigger_egress_test(target_host=target, target_port=port)
    return jsonify(result)


@main_bp.route("/api/logs", methods=["GET"])
def get_logs():
    """Retrieve structured system, agent execution, and air-gap network logs."""
    source = request.args.get("source", "all").lower()
    level_filter = request.args.get("level", "ALL").upper()
    search = request.args.get("search", "").lower()
    try:
        limit = int(request.args.get("limit", 250))
    except (TypeError, ValueError):
        limit = 250

    parsed_logs = []

    # Read sovereign air-gap network log
    if source in ("all", "network"):
        net_log_path = Path("logs/sovereign_network.log")
        if net_log_path.exists():
            try:
                with open(net_log_path, "r", encoding="utf-8", errors="replace") as f:
                    for line in f:
                        line_str = line.strip()
                        if not line_str:
                            continue
                        if search and search not in line_str.lower():
                            continue
                        ts = line_str[1:20] if line_str.startswith("[") else ""
                        parsed_logs.append({
                            "timestamp": ts,
                            "level": "SOVEREIGN",
                            "source": "network",
                            "component": "airgap_auditor",
                            "message": line_str,
                            "raw": line_str
                        })
            except Exception as e:
                parsed_logs.append({"timestamp": "", "level": "ERROR", "source": "network", "component": "logs", "message": f"Error reading network log: {e}", "raw": str(e)})

    # Read system application / agent log
    if source in ("all", "system"):
        sys_log_path = Path("logs/sanctum.log")
        if sys_log_path.exists():
            try:
                with open(sys_log_path, "r", encoding="utf-8", errors="replace") as f:
                    for line in f:
                        line_str = line.strip()
                        if not line_str:
                            continue
                        if search and search not in line_str.lower():
                            continue
                        parts = line_str.split(" | ", 3)
                        ts = parts[0] if len(parts) > 0 else ""
                        lvl = parts[1].strip() if len(parts) > 1 else "INFO"
                        comp = parts[2].strip() if len(parts) > 2 else "system"
                        msg = parts[3] if len(parts) > 3 else line_str
                        if level_filter != "ALL" and lvl != level_filter:
                            continue
                        parsed_logs.append({
                            "timestamp": ts,
                            "level": lvl,
                            "source": "system",
                            "component": comp,
                            "message": msg,
                            "raw": line_str
                        })
            except Exception as e:
                parsed_logs.append({"timestamp": "", "level": "ERROR", "source": "system", "component": "logs", "message": f"Error reading system log: {e}", "raw": str(e)})

    # Sort logs chronologically
    parsed_logs.sort(key=lambda x: x.get("timestamp", ""))
    if len(parsed_logs) > limit:
        parsed_logs = parsed_logs[-limit:]

    from app.sovereign_network import sovereign_auditor
    net_summary = sovereign_auditor.get_audit_summary()

    return jsonify({
        "status": "ok",
        "source": source,
        "count": len(parsed_logs),
        "logs": parsed_logs,
        "airgap_integrity": net_summary.get("airgap_integrity_pct", 100.0),
        "external_calls": net_summary.get("external_calls_allowed", 0),
        "loopback_calls": net_summary.get("loopback_calls_count", 0)
    })


@main_bp.route("/api/logs/clear", methods=["POST"])
def clear_logs():
    """Clear logs if requested."""
    try:
        Path("logs/sanctum.log").write_text("", encoding="utf-8")
        Path("logs/sovereign_network.log").write_text("", encoding="utf-8")
        return jsonify({"status": "cleared", "message": "System and network logs successfully cleared."})
    except Exception as e:
        return jsonify({"error": str(e)}), 500


@main_bp.route("/api/logs/download", methods=["GET"])
def download_logs():
    """Download consolidated audit and system logs."""
    source = request.args.get("source", "all")
    content = []
    if source in ("all", "system") and Path("logs/sanctum.log").exists():
        content.append("=== SANCTUM SYSTEM & AGENT LOGS ===\n")
        content.append(Path("logs/sanctum.log").read_text(encoding="utf-8", errors="replace"))
    if source in ("all", "network") and Path("logs/sovereign_network.log").exists():
        content.append("\n=== SOVEREIGN AIR-GAP NETWORK AUDIT LOGS ===\n")
        content.append(Path("logs/sovereign_network.log").read_text(encoding="utf-8", errors="replace"))
    return Response(
        "".join(content),
        mimetype="text/plain",
        headers={"Content-Disposition": f"attachment; filename=sanctum_{source}_logs.txt"}
    )


@main_bp.route("/api/document/open", methods=["POST"])
def open_system_document():
    """Open a generated document directly in native OS application (Word / Pages / Preview)."""
    import subprocess
    data = request.get_json() or {}
    rel_path = data.get("path", "generated/PV_204B_Inspection_Approval_Note.docx").strip()

    candidates = [
        Path(rel_path),
        Path("generated") / Path(rel_path).name,
        Path("/Users/burlaprudhviraj/Downloads/Waste") / rel_path,
        Path("/Users/burlaprudhviraj/Downloads/integrate/sanctum-system") / rel_path,
        Path(current_app.agent.tool_manager.get("workspace").root_dir) / rel_path,
    ]

    target = None
    for cand in candidates:
        if cand.exists() and cand.is_file():
            target = cand
            break

    if not target:
        return jsonify({"error": f"Document '{rel_path}' not found on disk."}), 404

    try:
        subprocess.Popen(["open", str(target.resolve())])
        return jsonify({
            "status": "opened",
            "path": str(target.resolve()),
            "filename": target.name,
            "message": f"Opened {target.name} in native application."
        })
    except Exception as e:
        return jsonify({"error": f"Failed to open native application: {e}"}), 500



@main_bp.route("/api/models", methods=["GET"])
@main_bp.route("/models", methods=["GET"])
def models():
    manager = current_app.agent.llm_manager
    return jsonify({
        "models": manager.list_models(),
        "active": manager.model_name,
        "endpoint": manager.base_url,
        "local_only": True,
    })


@main_bp.route("/api/models/select", methods=["POST"])
def select_model():
    data = request.get_json() or {}
    model_name = str(data.get("model", "")).strip()
    manager = current_app.agent.llm_manager
    if not model_name:
        return jsonify({"error": "Model name is required."}), 400
    if model_name not in manager.list_models():
        return jsonify({"error": "Model is not available from the local Ollama server."}), 404
    manager.change_model(model_name)
    return jsonify({"active": manager.model_name, "local_only": True})


# ─────────────────────────────────────────────────────────────────────────────
# Tools
# ─────────────────────────────────────────────────────────────────────────────

@main_bp.route("/tools", methods=["GET"])
@main_bp.route("/api/tools", methods=["GET"])
def list_tools():
    return jsonify({"tools": current_app.agent.list_tools()})


# ─────────────────────────────────────────────────────────────────────────────
# Session History (in-session, not workspace-scoped)
# ─────────────────────────────────────────────────────────────────────────────

@main_bp.route("/history", methods=["GET"])
@main_bp.route("/api/history", methods=["GET"])
def history():
    return jsonify({"history": current_app.agent.get_history()})


@main_bp.route("/history", methods=["DELETE"])
@main_bp.route("/api/clear", methods=["POST"])
@main_bp.route("/api/history", methods=["DELETE"])
def clear_history():
    current_app.agent.clear_memory()
    wh = getattr(current_app, "workspace_history", None) or getattr(current_app.agent, "workspace_history", None)
    if wh:
        wh.clear()
    return jsonify({"message": "Conversation history cleared successfully."})


# ─────────────────────────────────────────────────────────────────────────────
# Workspace History (per-workspace persistent history)
# ─────────────────────────────────────────────────────────────────────────────

@main_bp.route("/api/workspace/history", methods=["GET"])
def workspace_history():
    """Return the isolated history for the current workspace."""
    wh = getattr(current_app, "workspace_history", None) or getattr(current_app.agent, "workspace_history", None)
    if not wh:
        return jsonify({"history": [], "summary": ""})
    return jsonify({
        "history": wh.get_all(),
        "summary": wh.get_summary(),
        "workspace": wh.workspace_root(),
        "profile": wh.profile(),
    })


@main_bp.route("/api/workspace/history", methods=["DELETE"])
def clear_workspace_history():
    """Clear the isolated history for the current workspace."""
    wh = getattr(current_app, "workspace_history", None) or getattr(current_app.agent, "workspace_history", None)
    if not wh:
        return jsonify({"message": "No workspace history manager found."}), 404
    wh.clear()
    return jsonify({"message": "Workspace history cleared."})


# ─────────────────────────────────────────────────────────────────────────────
# Sanctum Locker
# ─────────────────────────────────────────────────────────────────────────────

def _cleanup_paths(*paths):
    for path in paths:
        try:
            target = Path(path)
            if target.is_dir():
                shutil.rmtree(target, ignore_errors=True)
            else:
                target.unlink(missing_ok=True)
        except OSError:
            logger.warning("Could not clean up locker temporary file: %s", path)


@main_bp.route("/api/locker/lock", methods=["POST"])
def lock_workspace_file():
    uploaded = request.files.get("file")
    passphrase = request.form.get("passphrase", "")
    if not uploaded or not uploaded.filename:
        return jsonify({"error": "Select a file to lock."}), 400
    if not passphrase:
        return jsonify({"error": "A passphrase is required."}), 400

    original_name = secure_filename(uploaded.filename) or "protected-file"
    temp_dir = Path(tempfile.mkdtemp(prefix="sanctum-locker-"))
    source_path = temp_dir / original_name
    locked_path = temp_dir / f"{original_name}.locked"
    uploaded.save(source_path)
    try:
        restrict_file(source_path, passphrase, locked_path)
        response = send_file(locked_path, as_attachment=True, download_name=f"{original_name}.locked")
        response.call_on_close(lambda: _cleanup_paths(source_path, locked_path, temp_dir))
        return response
    except Exception as error:
        _cleanup_paths(source_path, locked_path, temp_dir)
        logger.exception("Error locking uploaded file.")
        return jsonify({"error": f"Could not lock file: {error}"}), 500


@main_bp.route("/api/locker/unlock", methods=["POST"])
def unlock_workspace_file():
    uploaded = request.files.get("file")
    passphrase = request.form.get("passphrase", "")
    if not uploaded or not uploaded.filename:
        return jsonify({"error": "Select a .locked file to unlock."}), 400
    if not passphrase:
        return jsonify({"error": "A passphrase is required."}), 400

    original_name = secure_filename(uploaded.filename) or "locked-file.locked"
    temp_dir = Path(tempfile.mkdtemp(prefix="sanctum-unlocker-"))
    source_path = temp_dir / original_name
    output_dir = temp_dir / "restored"
    output_dir.mkdir()
    uploaded.save(source_path)
    try:
        restored_path = Path(unrestrict_file(source_path, passphrase, output_dir))
        download_name = original_name[:-7] if original_name.endswith(".locked") else f"{original_name}.restored"
        response = send_file(restored_path, as_attachment=True, download_name=download_name)
        response.call_on_close(lambda: _cleanup_paths(source_path, restored_path, temp_dir))
        return response
    except Exception:
        _cleanup_paths(source_path, temp_dir)
        logger.exception("Error unlocking uploaded file.")
        return jsonify({"error": "Unable to unlock file. Check the passphrase and file integrity."}), 400


# ─────────────────────────────────────────────────────────────────────────────
# Workspace Files
# ─────────────────────────────────────────────────────────────────────────────

@main_bp.route("/api/workspace/tree", methods=["GET"])
def workspace_tree():
    try:
        agent = current_app.agent
        tree_res = agent.execute_tool("workspace", action="tree")
        list_res = agent.execute_tool("workspace", action="list_files", recursive=True)
        return jsonify({
            "tree": tree_res.get("items", []),
            "files": list_res.get("items", []),
            "path": tree_res.get("path", ""),
        })
    except Exception as e:
        logger.exception("Error reading workspace tree.")
        return jsonify({"error": str(e)}), 500


@main_bp.route("/api/workspace/select", methods=["POST"])
def select_workspace():
    """Set an explicit local directory as the active workspace root."""
    data = request.get_json() or {}
    root_dir = str(data.get("path", "")).strip()
    if not root_dir:
        return jsonify({"error": "Workspace path is required."}), 400
    try:
        selected = current_app.agent.set_workspace(root_dir)
        # Update app-level references
        if hasattr(current_app, "workspace_history"):
            current_app.workspace_history = current_app.agent.workspace_history
        if hasattr(current_app, "lkb_manager"):
            current_app.lkb_manager = current_app.agent.lkb_manager
        if hasattr(current_app, "workspace_registry"):
            current_app.workspace_registry.register(selected)
        return jsonify({"path": selected, "workspace": selected})
    except (OSError, ValueError) as error:
        return jsonify({"error": str(error)}), 400


@main_bp.route("/api/workspace/pick", methods=["POST"])
def pick_workspace():
    """Open a native folder picker when Sanctum is running on the local desktop."""
    try:
        import sys
        if sys.platform == "darwin":
            import subprocess
            cmd = ["osascript", "-e", 'POSIX path of (choose folder with prompt "Choose Sanctum workspace")']
            res = subprocess.run(cmd, capture_output=True, text=True, timeout=60)
            if res.returncode != 0 or not res.stdout.strip():
                return jsonify({"cancelled": True}), 200
            selected = res.stdout.strip()
        else:
            import tkinter as tk
            from tkinter import filedialog
            root = tk.Tk()
            root.withdraw()
            root.attributes("-topmost", True)
            selected = filedialog.askdirectory(title="Choose Sanctum workspace")
            root.destroy()
        if not selected:
            return jsonify({"cancelled": True}), 200
        active = current_app.agent.set_workspace(selected)
        if hasattr(current_app, "workspace_history"):
            current_app.workspace_history = current_app.agent.workspace_history
        if hasattr(current_app, "lkb_manager"):
            current_app.lkb_manager = current_app.agent.lkb_manager
        if hasattr(current_app, "workspace_registry"):
            current_app.workspace_registry.register(active)
        return jsonify({"cancelled": False, "path": active, "workspace": active})
    except Exception as error:
        logger.exception("Native workspace picker failed.")
        return jsonify({"error": "Native folder picker is unavailable: {}".format(error)}), 500


@main_bp.route("/api/workspace/file", methods=["GET"])
def read_workspace_file():
    file_path = request.args.get("path", "")
    if not file_path:
        return jsonify({"error": "File path parameter 'path' is required."}), 400
    try:
        agent = current_app.agent
        stat_res = agent.execute_tool("workspace", action="stat", path=file_path)
        try:
            file_res = agent.execute_tool("file", action="read_file", path=file_path)
            content = file_res.get("content", "")
            is_binary = False
        except ValueError as ve:
            if "binary file" in str(ve).lower():
                content = f"[Binary file / Image: {Path(file_path).name}. Use Document Analysis to inspect content.]"
                is_binary = True
            else:
                raise
        return jsonify({"path": file_path, "content": content, "stat": stat_res, "is_binary": is_binary})
    except Exception as e:
        logger.exception(f"Error reading file '{file_path}'.")
        return jsonify({"error": str(e)}), 500


@main_bp.route("/api/workspace/preview", methods=["GET"])
def preview_workspace_file():
    """Serve a workspace PDF inline for the embedded editor viewer."""
    requested = request.args.get("path", "").strip()
    if not requested:
        return jsonify({"error": "File path parameter 'path' is required."}), 400
    root = current_app.agent.tool_manager.get("workspace").root_dir.resolve()
    candidate = (root / requested).expanduser().resolve()
    try:
        candidate.relative_to(root)
    except ValueError:
        return jsonify({"error": "Preview path escapes the configured workspace root."}), 403
    if not candidate.is_file() or candidate.suffix.lower() != ".pdf":
        return jsonify({"error": "A workspace PDF was not found at this path."}), 404
    return send_file(candidate, mimetype="application/pdf", as_attachment=False, download_name=candidate.name)


@main_bp.route("/api/workspace/download", methods=["GET"])
def download_workspace_file():
    """Download a generated file from the active workspace only."""
    requested = request.args.get("path", "").strip()
    if not requested:
        return jsonify({"error": "File path parameter 'path' is required."}), 400
    root = current_app.agent.tool_manager.get("workspace").root_dir
    candidate = (root / requested).expanduser().resolve()
    try:
        candidate.relative_to(root)
    except ValueError:
        return jsonify({"error": "Download path escapes the configured workspace root."}), 403
    if not candidate.is_file():
        return jsonify({"error": "Generated file was not found."}), 404
    return send_file(candidate, as_attachment=True, download_name=candidate.name)


# ─────────────────────────────────────────────────────────────────────────────
# Local Knowledge Base (LKB)
# ─────────────────────────────────────────────────────────────────────────────

@main_bp.route("/api/lkb/index", methods=["POST"])
def lkb_index():
    """Index a file or directory into the workspace LKB."""
    data = request.get_json() or {}
    path = str(data.get("path", "")).strip()
    recursive = bool(data.get("recursive", True))
    if not path:
        return jsonify({"error": "Path is required."}), 400
    lkb = getattr(current_app, "lkb_manager", None) or getattr(current_app.agent, "lkb_manager", None)
    if not lkb:
        return jsonify({"error": "LKB not initialized."}), 503
    from pathlib import Path as P
    ws_root = current_app.agent.tool_manager.get("workspace").root_dir.resolve()
    full_path = P(path).expanduser()
    if not full_path.is_absolute():
        full_path = ws_root / full_path
    full_path = full_path.resolve()
    try:
        full_path.relative_to(ws_root)
    except ValueError:
        return jsonify({"error": "Path must stay inside the active workspace."}), 400
    if not full_path.exists():
        return jsonify({"error": f"Path not found: {path}"}), 404
    try:
        if full_path.is_dir():
            result = lkb.index_directory(str(full_path), recursive=recursive)
        else:
            result = lkb.index_file(str(full_path))
        if result.get("status") in {"error", "skipped"}:
            return jsonify(result), 400
        return jsonify(result)
    except Exception as e:
        logger.exception("LKB indexing failed.")
        return jsonify({"error": str(e)}), 500


@main_bp.route("/api/lkb/search", methods=["GET"])
def lkb_search():
    """Search the workspace LKB."""
    query = request.args.get("q", "").strip()
    top_k = int(request.args.get("top_k", 5))
    if not query:
        return jsonify({"error": "Query parameter 'q' is required."}), 400
    lkb = getattr(current_app, "lkb_manager", None) or getattr(current_app.agent, "lkb_manager", None)
    if not lkb:
        return jsonify({"error": "LKB not initialized."}), 503
    results = lkb.search(query, top_k=top_k)
    return jsonify({"results": results, "query": query})


@main_bp.route("/api/lkb/list", methods=["GET"])
def lkb_list():
    """List all indexed files in the workspace LKB."""
    lkb = getattr(current_app, "lkb_manager", None) or getattr(current_app.agent, "lkb_manager", None)
    if not lkb:
        return jsonify({"files": []})
    return jsonify({"files": lkb.list_indexed()})


@main_bp.route("/api/lkb/clear", methods=["DELETE"])
def lkb_clear():
    """Clear the workspace LKB."""
    lkb = getattr(current_app, "lkb_manager", None) or getattr(current_app.agent, "lkb_manager", None)
    if not lkb:
        return jsonify({"error": "LKB not initialized."}), 503
    lkb.clear()
    return jsonify({"message": "LKB cleared."})


@main_bp.route("/api/memory", methods=["GET"])
def get_memory():
    """Return active ChatGPT-style memory context profile."""
    agent = getattr(current_app, "agent", None)
    if not agent or not hasattr(agent, "memory_manager"):
        return jsonify({"user_name": "", "facts": [], "preferences": [], "projects": []})
    mm = agent.memory_manager
    return jsonify({
        "user_name": getattr(mm, "user_name", ""),
        "facts": getattr(mm, "facts", []),
        "preferences": getattr(mm, "preferences", []),
        "projects": getattr(mm, "projects", []),
    })


# ─────────────────────────────────────────────────────────────────────────────
# Fluid Architecture
# ─────────────────────────────────────────────────────────────────────────────

@main_bp.route("/api/fluid/registry", methods=["GET"])
def fluid_registry():
    """Return all model capability profiles."""
    registry = getattr(current_app, "model_registry", None)
    if not registry:
        return jsonify({"profiles": {}})
    available_models = current_app.agent.llm_manager.list_models()
    profiler = getattr(current_app, "model_profiler", None)
    if profiler:
        for model in available_models:
            if profiler.needs_profiling(model):
                profiler.profile_async(model)
    profiles = {
        model: registry.get_profile(model)
        for model in available_models
    }
    routing_table = current_app.fluid_router.routing_table() if hasattr(current_app, "fluid_router") else []
    return jsonify({
        "profiles": profiles,
        "routing_table": routing_table,
    })


@main_bp.route("/api/fluid/profile", methods=["POST"])
def fluid_profile():
    """Trigger manual model profiling."""
    data = request.get_json() or {}
    model_name = str(data.get("model", "")).strip()
    profiler = getattr(current_app, "model_profiler", None)
    if not profiler:
        return jsonify({"error": "Profiler not initialized."}), 503
    if not model_name:
        return jsonify({"error": "Model name is required."}), 400
    profiler.profile_async(model_name)
    return jsonify({"message": f"Profiling started for '{model_name}' in background."})


@main_bp.route("/api/fluid/route", methods=["GET"])
def fluid_route():
    """Preview which model would handle a task."""
    task = request.args.get("task", "").strip()
    router = getattr(current_app, "fluid_router", None)
    if not router:
        return jsonify({"error": "Fluid router not initialized."}), 503
    return jsonify(router.preview_route(task or "general task"))


@main_bp.route("/api/fluid/workspaces", methods=["GET"])
def fluid_workspaces():
    """List all known workspaces."""
    wr = getattr(current_app, "workspace_registry", None)
    if not wr:
        return jsonify({"workspaces": []})
    return jsonify({"workspaces": wr.list_workspaces()})


# ─────────────────────────────────────────────────────────────────────────────
# Health
# ─────────────────────────────────────────────────────────────────────────────

@main_bp.route("/health", methods=["GET"])
@main_bp.route("/api/health", methods=["GET"])
def health():
    return jsonify({
        "status": "ok",
        "llm": current_app.agent.llm_manager.health_check(),
        "memory": True,
        "tools": True,
        "fluid": bool(getattr(current_app, "fluid_router", None)),
        "lkb": bool(getattr(current_app, "lkb_manager", None)),
    })


# ─────────────────────────────────────────────────────────────────────────────
# Observability & Trace Endpoints
# ─────────────────────────────────────────────────────────────────────────────

@main_bp.route("/api/traces/latest", methods=["GET"])
def get_latest_trace():
    """Return latest workflow trace in JSON format."""
    from app.observability import workflow_trace_store
    trace = workflow_trace_store.get_latest()
    if not trace:
        return jsonify({"error": "No workflow traces available."}), 404
    return jsonify(trace.to_dict())


@main_bp.route("/api/traces/latest/text", methods=["GET"])
def get_latest_trace_text():
    """Return latest workflow debug trace in human-readable ASCII format."""
    from app.observability import workflow_trace_store
    trace = workflow_trace_store.get_latest()
    if not trace:
        return Response("No workflow traces available.", mimetype="text/plain", status=404)
    return Response(trace.to_human_readable(), mimetype="text/plain")


@main_bp.route("/api/traces/<trace_id>", methods=["GET"])
def get_trace_by_id(trace_id: str):
    """Return specific workflow trace in JSON format."""
    from app.observability import workflow_trace_store
    trace = workflow_trace_store.get(trace_id)
    if not trace:
        return jsonify({"error": f"Workflow trace '{trace_id}' not found."}), 404
    return jsonify(trace.to_dict())


@main_bp.route("/api/traces/<trace_id>/text", methods=["GET"])
def get_trace_by_id_text(trace_id: str):
    """Return specific workflow trace in human-readable ASCII format."""
    from app.observability import workflow_trace_store
    trace = workflow_trace_store.get(trace_id)
    if not trace:
        return Response(f"Workflow trace '{trace_id}' not found.", mimetype="text/plain", status=404)
    return Response(trace.to_human_readable(), mimetype="text/plain")

