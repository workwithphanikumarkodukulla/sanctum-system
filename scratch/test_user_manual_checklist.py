"""Comprehensive automated execution and validation of the user's manual checklist."""
import os
import json
import time
import requests

BASE_URL = "http://127.0.0.1:5050"
WORKSPACE_DIR = "/Users/burlaprudhviraj/Downloads/Waste"

def clear_memory():
    print("\n--- Clearing Memory and Resetting History ---")
    resp = requests.post(f"{BASE_URL}/api/clear")
    print(f"Clear status: {resp.status_code}")
    assert resp.status_code == 200, f"Clear failed: {resp.text}"

def send_chat(message: str, timeout: int = 180):
    t0 = time.perf_counter()
    resp = requests.post(f"{BASE_URL}/api/chat", json={"message": message}, timeout=timeout)
    dt = time.perf_counter() - t0
    if resp.status_code != 200:
        raise RuntimeError(f"Chat failed ({resp.status_code}): {resp.text[:300]}")
    data = resp.json()
    data["_elapsed_client"] = dt
    return data

def run_tests():
    clear_memory()
    results = []

    # 1. hi
    print("\n=======================================================")
    print("TEST 1: 'hi'")
    d1 = send_chat("hi")
    r1 = d1.get("reply", "")
    m1 = d1.get("model_used")
    dur1 = d1.get("duration_s")
    print(f"Model: {m1} | Duration: {dur1}s | Client: {d1['_elapsed_client']:.2f}s")
    print(f"Reply preview: {r1[:150]}")
    passed1 = bool(r1 and m1 == "gemma4:latest" and dur1 is not None)
    results.append(("1. Greeting 'hi'", passed1, f"Model: {m1}, Reply: {r1[:60]}"))

    # 2. my name prudhvi
    print("\n=======================================================")
    print("TEST 2: 'my name prudhvi'")
    d2 = send_chat("my name prudhvi")
    r2 = d2.get("reply", "")
    m2 = d2.get("model_used")
    print(f"Model: {m2} | Reply: {r2[:150]}")
    passed2 = bool("prudhvi" in r2.lower() or "nice to meet you" in r2.lower() or "remember" in r2.lower() or "hello" in r2.lower())
    results.append(("2. Set Name 'my name prudhvi'", passed2, f"Reply: {r2[:60]}"))

    # 3. what is my name
    print("\n=======================================================")
    print("TEST 3: 'what is my name'")
    d3 = send_chat("what is my name")
    r3 = d3.get("reply", "")
    m3 = d3.get("model_used")
    print(f"Model: {m3} | Reply: {r3[:150]}")
    passed3 = bool("prudhvi" in r3.lower())
    results.append(("3. Recall Name 'what is my name'", passed3, f"Reply: {r3[:60]}"))

    # 4. list all files
    print("\n=======================================================")
    print("TEST 4: 'list all files'")
    d4 = send_chat("list all files")
    r4 = d4.get("reply", "")
    m4 = d4.get("model_used")
    print(f"Model: {m4} | Reply preview: {r4[:200]}")
    passed4 = bool(any(ext in r4 for ext in [".png", ".pdf", ".py", "diff", "CSR"]))
    results.append(("4. List Files 'list all files'", passed4, f"Found files in listing: {passed4}"))

    # 5. write a program in py file(see if model switches)
    print("\n=======================================================")
    print("TEST 5: 'write a program in py file(see if model switches)'")
    d5 = send_chat("write a program in py file(see if model switches)")
    r5 = d5.get("reply", "")
    m5 = d5.get("model_used")
    print(f"Model: {m5} | Reply preview: {r5[:200]}")
    switched_to_coder = "qwen" in m5.lower() or "coder" in m5.lower()
    has_code = "```python" in r5 or "def " in r5 or "print(" in r5
    passed5 = bool(switched_to_coder and has_code)
    results.append(("5. Code Program & Model Switch", passed5, f"Model: {m5}, Has code block: {has_code}"))

    # 6. check what is in handnotes.png(dont know the file name)
    print("\n=======================================================")
    print("TEST 6: 'check what is in handnotes.png(dont know the file name)'")
    d6 = send_chat("check what is in handnotes.png(dont know the file name)")
    r6 = d6.get("reply", "")
    m6 = d6.get("model_used")
    print(f"Model: {m6} | Reply preview: {r6[:250]}")
    has_letter_text = any(k in r6.lower() for k in ["magnus", "tilburg", "metaverse", "web 3.0", "guest lecture", "gratitude"])
    passed6 = bool(has_letter_text)
    results.append(("6. Fuzzy Handnotes Reading", passed6, f"Extracted letter keywords: {has_letter_text}"))

    # 7. give a query in the big pdf
    print("\n=======================================================")
    print("TEST 7: 'give a query in the big pdf'")
    d7 = send_chat("give a query in the big pdf")
    r7 = d7.get("reply", "")
    m7 = d7.get("model_used")
    print(f"Model: {m7} | Reply preview: {r7[:250]}")
    has_csr_data = any(k in r7.lower() for k in ["csr", "expenditure", "allocated", "scholarship", "lakhs", "shiksha", "project"])
    passed7 = bool(has_csr_data)
    results.append(("7. Query in Big PDF", passed7, f"Extracted CSR project data: {has_csr_data}"))

    # 8. solve all the five diff and intergrate png for maths(check if simpy)
    print("\n=======================================================")
    print("TEST 8: 'solve all the five diff and intergrate png for maths(check if simpy)'")
    d8 = send_chat("solve all the five diff and intergrate png for maths(check if simpy)")
    r8 = d8.get("reply", "")
    m8 = d8.get("model_used")
    print(f"Model: {m8} | Reply preview: {r8[:400]}")
    has_diff_results = "3x^2 + 4x - 5" in r8 or "3*x**2 + 4*x - 5" in r8
    has_diff2 = "log" in r8.lower()
    has_diff3 = "1/x" in r8
    has_diff4 = "34x - 33" in r8 or "34*x - 33" in r8
    has_int = "x^6" in r8 or "x**6" in r8
    has_sympy = "sympy" in r8.lower()
    passed8 = bool(has_diff_results and has_diff4 and has_int and has_sympy)
    results.append(("8. Solve 5 Math PNGs with SymPy", passed8, f"Diff1: {has_diff_results}, Diff4: {has_diff4}, Int: {has_int}, SymPy cited: {has_sympy}"))

    # 9. generate pdf,dox,csv,excel,and check the output as well
    print("\n=======================================================")
    print("TEST 9: 'generate pdf,dox,csv,excel,and check the output as well'")
    d9 = send_chat("generate pdf,dox,csv,excel,and check the output as well")
    r9 = d9.get("reply", "")
    m9 = d9.get("model_used")
    print(f"Model: {m9} | Reply preview: {r9[:300]}")
    gen_dir = os.path.join(WORKSPACE_DIR, "generated")
    gen_files = os.listdir(gen_dir) if os.path.isdir(gen_dir) else []
    print(f"Files in generated/: {gen_files}")
    has_pdf = any(f.endswith(".pdf") for f in gen_files)
    has_docx = any(f.endswith(".docx") for f in gen_files)
    has_xlsx = any(f.endswith(".xlsx") for f in gen_files)
    has_csv = any(f.endswith(".csv") for f in gen_files)
    passed9 = bool(has_pdf and has_docx and has_xlsx and has_csv)
    results.append(("9. Generate & Verify PDF, DOCX, XLSX, CSV", passed9, f"PDF: {has_pdf}, DOCX: {has_docx}, XLSX: {has_xlsx}, CSV: {has_csv}"))

    # 10. Direct Model Inquiry
    print("\n=======================================================")
    print("TEST 10: 'which model are you using?'")
    d10 = send_chat("which model are you using?")
    r10 = d10.get("reply", "")
    m10 = d10.get("model_used")
    print(f"Model: {m10} | Reply preview: {r10[:300]}")
    has_router_mention = "fluid model router" in r10.lower() or "fluid" in r10.lower()
    passed10 = bool(has_router_mention and m10)
    results.append(("10. Direct Model Inquiry", passed10, f"Model: {m10}, Explains Fluid Router: {has_router_mention}"))

    # 11. Verify /api/history has model badges and durations for every message
    print("\n=======================================================")
    print("TEST 11: /api/history Badges & Metadata")
    h_resp = requests.get(f"{BASE_URL}/api/history")
    hist = h_resp.json().get("history", [])
    assistant_msgs = [m for m in hist if m.get("role") == "assistant"]
    print(f"Total Assistant Turns: {len(assistant_msgs)}")
    all_have_badges = True
    for i, m in enumerate(assistant_msgs):
        has_m = bool(m.get("model"))
        has_d = bool(m.get("duration"))
        print(f"Turn {i+1}: Model='{m.get('model')}', Duration='{m.get('duration')}' -> Badges OK: {has_m and has_d}")
        if not (has_m and has_d):
            all_have_badges = False
    results.append(("11. History Model & Duration Badges", all_have_badges, f"All {len(assistant_msgs)} assistant turns have badges: {all_have_badges}"))

    # Final Report
    print("\n=======================================================")
    print("JURY READINESS FINAL EVALUATION REPORT:")
    all_ok = True
    for title, passed, note in results:
        status = "PASSED [OK]" if passed else "FAILED [FAIL]"
        if not passed:
            all_ok = False
        print(f"{status:15} | {title} | {note}")
    print(f"\nOVERALL RESULT: {'100% READY FOR JURIES - ZERO FAILURES' if all_ok else 'ATTENTION NEEDED'}")
    return all_ok

if __name__ == "__main__":
    success = run_tests()
    exit(0 if success else 1)
