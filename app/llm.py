"""LLM module. Implements the LLM class for interacting with the language model."""
from langchain_groq import ChatGroq
from app.config import Config
from app.logger import logger
class LLMManager:
    def __init__(self):
        if not Config.GROQ_API_KEY:
            raise ValueError("GROQ_API_KEY is not set.")
        self.model_name = Config.GROQ_MODEL
        self._llm = ChatGroq(
            model=self.model_name,
            temperature=0,
            api_key=Config.GROQ_API_KEY,
        )
        logger.info("Groq LLM initialized successfully.")
    def invoke(self, prompt):
        return self._llm.invoke(prompt)
    def stream(self, prompt):
        return self._llm.stream(prompt)
    def health_check(self):
        try:
            self._llm.invoke("Hello")
            logger.info("Groq LLM Health Check Passed.")
            return True
        except Exception:
            logger.exception("Groq LLM Health Check Failed.")
            return False
    def change_model(self, model_name):
        self.model_name = model_name
        self._llm = ChatGroq(
            model=self.model_name,
            temperature=0,
            api_key=Config.GROQ_API_KEY,
        )
        logger.info("Model changed to '{}'.".format(self.model_name))
        self.health_check()
    def list_models():
        # Will be implemented later.
        return []
    def get_model_info(self):
        return {
            "provider": "Groq",
            "model": self.model_name,
            "temperature": 0,
        }
# Developer dairy : If anyone who are reading this code without knowledge on AI/ML/LLM's/AI Agents....
# They think that i really developed an LLM and used it.....
# NO bro.... Don't take this code and submit it to your teacher saying that
# "Madam! I developed an LLM and here is this....."
#
# Situation after that dialogue :
# "Call your guardians... let's have a talk with them....." ðŸ˜ðŸ˜…âœŒï¸
