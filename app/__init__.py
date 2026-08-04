from flask import Flask, app
from app.agent import CodingAgent
from app.config import DevelopmentConfig
from app.logger import logger
from app.llm import LLMManager
def create_app():
    # These are what we are going to do in this and the function handles these ====================================
    # 1. Load configurations
    # 2. Initialize logging
    # 3. Connect to the database
    # 4. Initialize LangChain
    # 5. Initialize Groq
    # 6. Initialize MCP Client
    # 7. Register routes
    # 8. Initialize RAG
    # 9. Initialize memory
    # ============================================== *** ==========================================================
    app = Flask(__name__)
    # Load configuration
    app.config.from_object(DevelopmentConfig)
    # Initialize LLM Manager
    try:
        # This is called Dependency Injection (DI) (in a simple form).
        llm_manager = LLMManager()
        app.agent = CodingAgent(llm_manager)
    except Exception:
        logger.exception("Failed to initialize LLM Manager.")
        raise
    logger.info("Forge AI Backend Initialized Successfully.")
    # Register Routes
    from app.routes import main_bp
    app.register_blueprint(main_bp)
    return app
#Developers Special Note : If you are a developer and reading this code...
# I want to tell one thing bro..... 
#Seriously saying from the bottom of my heart, While I am writing this code the time is 10:22 pm and I am feeling so sleepy..... 
# If you wanna take this code you need to give me these accessories as componsiation bro :- 1.Air Pillow,2.Coke Can,3. A pair of slippers,4. A blanket,5. A pillow,6. A bed,7. A room,8. A house,9. A car,10. A bike,11. A plane,12. A ship,13. A train,14. A bus,15. A truck,16. A helicopter,17. A rocket,18. A satellite,19. A spaceship,20. A UFO, 21. 99.999999999999999% Shares.....
#All these are not for the lines of code i wrote bro.... These are for future plaining if this project grew up and gone into gallexy in collecting profits..... Then i can't meet you so i am asking in advance ðŸ˜ðŸ˜ðŸ˜ðŸ˜ðŸ˜
