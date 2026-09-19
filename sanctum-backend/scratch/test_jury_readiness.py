"""Comprehensive Jury-Readiness Test Suite for Sanctum System."""
import json
import time
import requests

BASE_URL = "http://127.0.0.1:5050"

def test_api(name, payload, expected_substrings=None, forbidden_substrings=None):
    print(f"\n=======================================================")
    print(f"RUNNING JURY TEST: {name}")
    print(f"Payload: {payload}")
    t0 = time.perf_counter()
    try:
        resp = requests.post(f"{BASE_URL}/api/chat", json=payload, timeout=90)
        dt = time.perf_counter() - t0
        print(f"Status Code: {resp.status_code} (took {dt:.2f}s)")
        if resp.status_code != 200:
            print(f"FAILED: status {resp.status_code}, text: {resp.text[:300]}")
            return False
        data = resp.json()
        reply = data.get("reply", "")
        model_used = data.get("model_used")
        duration_s = data.get("duration_s")
        print(f"Model Used: {model_used} | Reported Duration: {duration_s}s")
        print(f"Reply Preview: {reply[:250]}...")

        # Assertions
        if not model_used:
            print("FAILED: model_used is missing in response!")
            return False
        if duration_s is None:
            print("FAILED: duration_s is missing in response!")
            return False

        if expected_substrings:
            for sub in expected_substrings:
                if sub.lower() not in reply.lower():
                    print(f"FAILED: Expected substring '{sub}' not found in reply!")
                    return False

        if forbidden_substrings:
            for bad in forbidden_substrings:
                if bad.lower() in reply.lower():
                    print(f"FAILED: Forbidden substring '{bad}' detected in reply!")
                    return False

        print(f"PASSED: {name}")
        return True
    except Exception as e:
        print(f"EXCEPTION: {e}")
        return False

def run_all():
    results = []

    # 1. Identity
    results.append(("Identity & Quick Response", test_api(
        "Identity Check",
        {"message": "who are you"},
        expected_substrings=["Sanctum", "AI Coding Assistant"],
        forbidden_substrings=["error", "exception"]
    )))

    # 2. SymPy Math
    results.append(("SymPy Deterministic Math", test_api(
        "Solve Equation",
        {"message": "solve x^2 - 49 = 0"},
        expected_substrings=["-7", "7"],
        forbidden_substrings=["cannot solve", "error"]
    )))

    # 3. Directory Listing
    results.append(("Workspace Directory Listing", test_api(
        "List Files",
        {"message": "list the files in this directory"},
        expected_substrings=["hello", ".py"],
        forbidden_substrings=["I am ready to assist you with file operations", "I will call"]
    )))

    # 4. Code Generation & File Creation
    results.append(("Code Creation", test_api(
        "Python Code Creation",
        {"message": "write a python file printing hello"},
        expected_substrings=["hello.py", "print("],
        forbidden_substrings=["failed", "error"]
    )))

    # 5. Memory Extraction & Recall
    test_api("Set Name", {"message": "My name is Prudhvi"})
    results.append(("Memory Recall", test_api(
        "Recall Name",
        {"message": "What is my name?"},
        expected_substrings=["Prudhvi"],
        forbidden_substrings=["don't know", "do not know"]
    )))

    # 6. Word Document Generation
    results.append(("Word Document Generation", test_api(
        "Word Doc Generation",
        {"message": "Create a Word document titled Quantum Computing covering Principles, Applications, and Future Outlook"},
        expected_substrings=["quantum_computing", ".docx"],
        forbidden_substrings=["error", "could not generate"]
    )))

    # 7. Check History endpoint metadata
    print("\n=======================================================")
    print("VERIFYING /api/history METADATA FOR BADGES...")
    h_resp = requests.get(f"{BASE_URL}/api/history")
    if h_resp.status_code == 200:
        hist = h_resp.json().get("history", [])
        print(f"Total turns in history: {len(hist)}")
        last_asst = [m for m in hist if m.get("role") == "assistant"]
        if last_asst:
            latest = last_asst[-1]
            print(f"Latest Assistant Turn: Model='{latest.get('model')}', Duration='{latest.get('duration')}'")
            if latest.get('model') and latest.get('duration'):
                print("PASSED: History metadata has model and duration for badges!")
                results.append(("History Metadata Badges", True))
            else:
                print("FAILED: Latest turn missing model or duration in history!")
                results.append(("History Metadata Badges", False))
    else:
        results.append(("History Metadata Badges", False))

    print("\n=======================================================")
    print("SUMMARY OF JURY READINESS TEST SUITE:")
    all_passed = True
    for name, res in results:
        status = "PASSED" if res else "FAILED"
        if not res:
            all_passed = False
        print(f" - {name}: {status}")
    print(f"OVERALL JURY READINESS: {'100% READY' if all_passed else 'ATTENTION NEEDED'}")

if __name__ == "__main__":
    run_all()
