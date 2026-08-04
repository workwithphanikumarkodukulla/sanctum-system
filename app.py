"""Application entry point."""
from app import create_app
from app.logger import logger
app = create_app()
if __name__ == "__main__":
    logger.debug("AI Agent's Backend Started")
    app.run(debug=True)
# Developer Note :-
#
# Yesterday:
#     Me  : "Run locally."
#     Laptop : "No."
#
# Today:
#     Me  : "Groq API."
#     Laptop : "Finally... some respect." ðŸ˜Œâ˜•
#
# Moral:
# Sometimes the smartest optimization
# is knowing what NOT to run locally. ðŸ˜âœŒï¸
