"""Application entry point."""
from app import create_app
from app.logger import logger
app = create_app()
if __name__ == "__main__":
    logger.debug("AI Agent's Backend Started")
    app.run(debug=False)
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
