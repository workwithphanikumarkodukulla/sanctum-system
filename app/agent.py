"""Agent logic."""
from app.config import Config
from app.prompt import PromptManager
from app.memory import MemoryManager
from app.tools.manager import ToolManager
class CodingAgent:
    def __init__(self, llm_manager, tool_manager=None):
        self.llm_manager = llm_manager
        self.llm = llm_manager
        self.tool_manager = tool_manager or ToolManager(root_dir=Config.WORKSPACE)
        self.prompt_manager = PromptManager()
        self.memory_manager = MemoryManager()
    def ask_llm(self, prompt):
        return self.llm_manager.invoke(prompt)
    def should_use_tool(self, message):
        return False
    def chat(self, message):
        if not message:
            raise ValueError("Message cannot be empty.")
        self.memory_manager.add_user_message(message)
        history = self.memory_manager.get_history()
        prompt = self.prompt_manager.build_prompt(history)
        if self.should_use_tool(message):
            pass
        else:
            response = self.ask_llm(prompt)
        self.memory_manager.add_ai_message(response.content)
        return response.content
    def list_tools(self):
        return self.tool_manager.list_tools()
    def execute_tool(self, name, *args, **kwargs):
        return self.tool_manager.execute(name, *args, **kwargs)
    def clear_memory(self):
        self.memory_manager.clear()
    def get_history(self):
        return self.memory_manager.get_history()
# Developer Note :- Time is 7:20 am now.....
# As a responsible lazy programmer and dedicating to my laziness....
# I am making agents to work for me so that I can sleep and they will do the work for me.....
#
# Cross check before using my code (Crazy Danger):
# Note :- Literally if anything goes wrong.....
# Your boss is ready with a white letter cover and I think some emotional
# beautiful text will be there in that letter that makes your LinkedIn
# status to "Open To Work" just within 2 seconds.....
#
# That's the power of agents.....
# Depends on their mood ðŸ˜âœŒï¸ðŸ˜…
