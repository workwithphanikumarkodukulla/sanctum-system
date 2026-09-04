"""Routes module. Defines all API endpoints."""

import json
import queue
import threading

from flask import Blueprint, request, jsonify, current_app, render_template, Response, stream_with_context, send_file

from app.logger import logger

main_bp = Blueprint("main", __name__)


@main_bp.route("/")
def index():
    return render_template("index.html")


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
        return jsonify({
            "reply": result["reply"],
            "tool_actions": result.get("tool_actions", []),
            "activity_events": result.get("activity_events", []),
        })
    except Exception:
        logger.exception("Error while processing chat request.")
        return jsonify({"error": "Internal Server Error."}), 500


@main_bp.route("/tools", methods=["GET"])
@main_bp.route("/api/tools", methods=["GET"])
def list_tools():
    return jsonify({"tools": current_app.agent.list_tools()})


@main_bp.route("/api/system", methods=["GET"])
def system_info():
    """Expose local model, MCP, and data-sovereignty status."""
    return jsonify(current_app.agent.system_info())


@main_bp.route("/api/models", methods=["GET"])
def models():
    manager = current_app.agent.llm_manager
    return jsonify({"models": manager.list_models(), "active": manager.model_name,
                    "endpoint": manager.base_url, "local_only": True})


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


@main_bp.route("/history", methods=["GET"])
@main_bp.route("/api/history", methods=["GET"])
def history():
    return jsonify({"history": current_app.agent.get_history()})


@main_bp.route("/history", methods=["DELETE"])
@main_bp.route("/api/clear", methods=["POST"])
@main_bp.route("/api/history", methods=["DELETE"])
def clear_history():
    current_app.agent.clear_memory()
    return jsonify({"message": "Conversation history cleared successfully."})


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


@main_bp.route("/health", methods=["GET"])
@main_bp.route("/api/health", methods=["GET"])
def health():
    return jsonify({
        "status": "ok",
        "llm": current_app.agent.llm_manager.health_check(),
        "memory": True,
        "tools": True,
    })


@main_bp.route("/api/workspace/tree", methods=["GET"])
def workspace_tree():
    try:
        agent = current_app.agent
        tree_res = agent.execute_tool("workspace", action="tree")
        list_res = agent.execute_tool("workspace", action="list_files", recursive=True)
        return jsonify({
            "tree": tree_res.get("items", []),
            "files": list_res.get("items", []),
            "path": tree_res.get("path", "")
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
        return jsonify({"path": selected, "workspace": selected})
    except (OSError, ValueError) as error:
        return jsonify({"error": str(error)}), 400


@main_bp.route("/api/workspace/pick", methods=["POST"])
def pick_workspace():
    """Open a native folder picker when Sanctum is running on the local desktop."""
    try:
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
        file_res = agent.execute_tool("file", action="read_file", path=file_path)
        stat_res = agent.execute_tool("workspace", action="stat", path=file_path)
        return jsonify({
            "path": file_path,
            "content": file_res.get("content", ""),
            "stat": stat_res
        })
    except Exception as e:
        logger.exception(f"Error reading file '{file_path}'.")
        return jsonify({"error": str(e)}), 500


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
