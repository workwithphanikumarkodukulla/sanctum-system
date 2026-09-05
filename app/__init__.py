from flask import Flask
from app.agent import CodingAgent
from app.config import DevelopmentConfig
from app.logger import logger
from app.llm import LLMManager
from app.fluid.model_registry import ModelRegistry
from app.fluid.model_profiler import ModelProfiler
from app.fluid.workspace_registry import WorkspaceRegistry
from app.fluid.router import FluidRouter
from app.lkb.manager import LKBManager
from app.workspace_history import WorkspaceHistoryManager
from app.config import Config
from pathlib import Path


def create_app():
    app = Flask(__name__)
    app.config.from_object(DevelopmentConfig)

    try:
        # ── Local LLM ─────────────────────────────────────────────────
        llm_manager = LLMManager()

        # ── Sanctum Fluid Architecture ─────────────────────────────────
        model_registry = ModelRegistry()
        model_profiler = ModelProfiler(model_registry, llm_manager)
        workspace_registry = WorkspaceRegistry()
        fluid_router = FluidRouter(model_registry, model_profiler, llm_manager)

        # ── Workspace History ──────────────────────────────────────────
        workspace_root = Path(Config.WORKSPACE).expanduser().resolve()
        workspace_root.mkdir(parents=True, exist_ok=True)
        workspace_history = WorkspaceHistoryManager(workspace_root)
        workspace_registry.register(str(workspace_root))

        # ── Local Knowledge Base ───────────────────────────────────────
        lkb_manager = LKBManager(workspace_root)

        # ── Agent (inject all systems) ─────────────────────────────────
        app.agent = CodingAgent(
            llm_manager,
            fluid_router=fluid_router,
            workspace_history=workspace_history,
            lkb_manager=lkb_manager,
        )

        # Attach shared services to app for route access
        app.model_registry = model_registry
        app.model_profiler = model_profiler
        app.workspace_registry = workspace_registry
        app.fluid_router = fluid_router
        app.workspace_history = workspace_history
        app.lkb_manager = lkb_manager

    except Exception:
        logger.exception("Failed to initialize Sanctum systems.")
        raise

    logger.info("Sanctum Fluid Backend Initialized Successfully.")

    # Register Routes
    from app.routes import main_bp
    app.register_blueprint(main_bp)
    return app
#Developers Special Note : If you are a developer and reading this code...
# I want to tell one thing bro.....
#Seriously saying from the bottom of my heart, While I am writing this code the time is 10:22 pm and I am feeling so sleepy.....
# If you wanna take this code you need to give me these accessories as componsiation bro :- 1.Air Pillow,2.Coke Can,3. A pair of slippers,4. A blanket,5. A pillow,6. A bed,7. A room,8. A house,9. A car,10. A bike,11. A plane,12. A ship,13. A train,14. A bus,15. A truck,16. A helicopter,17. A rocket,18. A satellite,19. A spaceship,20. A UFO, 21. 99.999999999999999% Shares.....
#All these are not for the lines of code i wrote bro.... These are for future plaining if this project grew up and gone into gallexy in collecting profits..... Then i can't meet you so i am asking in advance 😁😁😁😁😁
