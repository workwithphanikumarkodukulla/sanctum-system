"""Routes module. Defines all API endpoints."""
from flask import Blueprint, request, jsonify, current_app
from app.logger import logger
main_bp = Blueprint("main", __name__)
@main_bp.route("/")
def index():
    return jsonify({
        "status": "running",
        "message": "Forge AI Backend Running"
    })
@main_bp.route("/chat", methods=["POST"])
def chat():
    """
    Pipeline :-
    Receive Request
           â”‚
           â–¼
    Validate JSON
           â”‚
           â–¼
    Extract "message"
           â”‚
           â–¼
    Call CodingAgent
           â”‚
           â–¼
    Return JSON Response
    """
    data = request.get_json()
    if not data:
        return jsonify({
            "error": "Request body is missing."
        }), 400
    if "message" not in data:
        return jsonify({
            "error": "'message' field is required."
        }), 400
    message = data["message"].strip()
    if not message:
        return jsonify({
            "error": "Message cannot be empty."
        }), 400
    try:
        agent = current_app.agent
        response = agent.chat(message)
        return jsonify({
            "response": response
        })
    except Exception:
        logger.exception("Error while processing chat request.")
        return jsonify({
            "error": "Internal Server Error."
        }), 500
@main_bp.route("/tools", methods=["GET"])
def list_tools():
    return jsonify({
        "tools": current_app.agent.list_tools()
    })
@main_bp.route("/history", methods=["GET"])
def history():
    return jsonify({
        "history": current_app.agent.get_history()
    })
@main_bp.route("/history", methods=["DELETE"])
def clear_history():
    current_app.agent.clear_memory()
    return jsonify({
        "message": "Conversation history cleared successfully."
    })
@main_bp.route("/health", methods=["GET"])
def health():
    return jsonify({
        "status": "ok",
        "llm": current_app.agent.llm_manager.health_check(),
        "memory": True,
        "tools": True,
    })
# Pre Developer Note :
# It's better to wear slippers to move through these routes....
# because at the end of the day your foot will turn into pure
# red painted objects ðŸ˜‚ðŸ˜‚
#
# One more note :-
# Don't forget to use Google Maps to find the way to reach these
# routes.... because these routes are so complex that even Google
# Maps will get confused and won't be able to find the way. ðŸ˜ðŸ˜…âœŒï¸
