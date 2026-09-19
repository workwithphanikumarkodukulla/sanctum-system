"""Application entry point."""
from app import create_app
from app.logger import logger
import os
app = create_app()
if __name__ == "__main__":
    port = int(os.getenv("PORT", 5050))
    logger.debug(f"AI Agent's Backend Started on port {port}")
    app.run(host="127.0.0.1", port=port, debug=False)
# Developer Note :-
#
# Yesterday:
#     Me  : "Run locally."
#     Laptop : "No."
#
# Today:
#     Me  : "Local model."
#     Laptop : "Finally... no network required."
#
# Moral:
# Sometimes the smartest optimization
# is knowing what NOT to run locally. ðŸ˜âœŒï¸
