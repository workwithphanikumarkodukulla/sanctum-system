"""Prompt management module."""
class PromptManager:
    def __init__(self):
        self.system_prompt = """
You are Forge AI.
You are a professional AI Coding Assistant.
Your responsibilities:
â€¢ Write clean code.
â€¢ Explain concepts clearly.
â€¢ Never invent libraries.
â€¢ Prefer Python best practices.
â€¢ If you don't know something, say so.
â€¢ Be concise.
â€¢ Think step by step.
"""
    def build_prompt(self, history):
        history_lines = []
        for message in history:
            role = message.get("role", "user")
            content = message.get("content", "")
            if role == "assistant":
                history_lines.append(f"Assistant: {content}")
            else:
                history_lines.append(f"User: {content}")
        history_text = "\n".join(history_lines)
        if history_text:
            return f"{self.system_prompt}\n\n{history_text}"
        return self.system_prompt
# Developer Note :-
#
# Dear Forge...
#
# Please behave properly.
#
# I wrote this prompt with love.
#
# If you still generate weird answers...
#
# That's between you and the GPU. ðŸ˜ðŸ˜‚âœŒï¸
