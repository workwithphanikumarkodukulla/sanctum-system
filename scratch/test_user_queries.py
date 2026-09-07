"""Test script simulating the exact 4 user requests."""
import sys
from pathlib import Path

# Add project root to sys.path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from app import create_app

def test_queries():
    app = create_app()
    agent = app.agent
    
    queries = [
        "list all the files in present directory",
        "solve diff.png",
        "solve diff4.png",
        "what is the content in handwritten_note.png",
    ]
    
    for q in queries:
        print("\n" + "=" * 70)
        print(f"TESTING QUERY: {q}")
        print("=" * 70)
        res = agent.chat(q)
        print("AGENT REPLY:")
        print(res.get("reply"))
        print("\nTOOL ACTIONS:")
        for a in res.get("tool_actions", []):
            print(f"- {a.get('tool')}: args={a.get('args')}")
        print("=" * 70)

if __name__ == "__main__":
    test_queries()
