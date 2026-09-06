"""Comprehensive automated validation for the extended 14-point jury checklist."""
import os
import time
import requests

BASE_URL = "http://127.0.0.1:5050"
WORKSPACE_DIR = "/Users/burlaprudhviraj/Downloads/Waste"

def clear_memory():
    print("\n--- Clearing Memory and Resetting History ---")
    resp = requests.post(f"{BASE_URL}/api/clear")
    print(f"Clear status: {resp.status_code}")
    assert resp.status_code == 200, f"Clear failed: {resp.text}"

def send_chat(message: str, timeout: int = 120):
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
    passed1 = bool(r1 and m1 == "gemma4:latest")
    results.append(("1. Greeting 'hi'", passed1, f"Model: {m1}, Duration: {d1.get('duration_s')}s"))

    # 2. my name prudhvi
    print("\n=======================================================")
    print("TEST 2: 'my name prudhvi'")
    d2 = send_chat("my name prudhvi")
    r2 = d2.get("reply", "")
    m2 = d2.get("model_used")
    passed2 = bool("prudhvi" in r2.lower() or "remember" in r2.lower() or "nice to meet" in r2.lower())
    results.append(("2. Set Name 'my name prudhvi'", passed2, f"Model: {m2}, Reply: {r2[:60]}"))

    # 3. what is my name
    print("\n=======================================================")
    print("TEST 3: 'what is my name'")
    d3 = send_chat("what is my name")
    r3 = d3.get("reply", "")
    m3 = d3.get("model_used")
    passed3 = bool("prudhvi" in r3.lower())
    results.append(("3. Recall Name 'what is my name'", passed3, f"Model: {m3}, Reply: {r3[:60]}"))

    # 4. list all files
    print("\n=======================================================")
    print("TEST 4: 'list all files'")
    d4 = send_chat("list all files")
    r4 = d4.get("reply", "")
    m4 = d4.get("model_used")
    passed4 = bool(any(ext in r4 for ext in [".png", ".pdf", ".py", "diff", "CSR"]))
    results.append(("4. List Files 'list all files'", passed4, f"Model: {m4}, Cataloged files: {passed4}"))

    # 5. write a program in py file(see if model switches)
    print("\n=======================================================")
    print("TEST 5: 'write a program in py file(see if model switches)'")
    d5 = send_chat("write a program in py file(see if model switches)")
    r5 = d5.get("reply", "")
    m5 = d5.get("model_used")
    switched_to_coder = "qwen" in m5.lower() or "coder" in m5.lower()
    has_code = "```python" in r5 or "def " in r5 or "print(" in r5
    passed5 = bool(switched_to_coder and has_code)
    results.append(("5. Code Program & Model Switch", passed5, f"Model: {m5}, Code generated: {has_code}"))

    # 6. check what is in handnotes.png(dont know the file name)
    print("\n=======================================================")
    print("TEST 6: 'check what is in handnotes.png(dont know the file name)'")
    d6 = send_chat("check what is in handnotes.png(dont know the file name)")
    r6 = d6.get("reply", "")
    m6 = d6.get("model_used")
    has_letter_text = any(k in r6.lower() for k in ["magnus", "tilburg", "metaverse", "web 3.0", "guest lecture", "gratitude"])
    passed6 = bool(has_letter_text and "mistral" in m6.lower())
    results.append(("6. Fuzzy Handnotes Reading", passed6, f"Model: {m6}, Magnus letter extracted: {has_letter_text}"))

    # 7. give a query in the big pdf
    print("\n=======================================================")
    print("TEST 7: 'give a query in the big pdf'")
    d7 = send_chat("give a query in the big pdf")
    r7 = d7.get("reply", "")
    m7 = d7.get("model_used")
    has_csr_data = any(k in r7.lower() for k in ["csr", "expenditure", "allocated", "scholarship", "lakhs", "shiksha", "project"])
    passed7 = bool(has_csr_data and "mistral" in m7.lower())
    results.append(("7. Query in Big PDF", passed7, f"Model: {m7}, CSR allocated extracted: {has_csr_data}"))

    # 8. solve all the five diff and intergrate png for maths(check if simpy)
    print("\n=======================================================")
    print("TEST 8: 'solve all the five diff and intergrate png for maths(check if simpy)'")
    d8 = send_chat("solve all the five diff and intergrate png for maths(check if simpy)")
    r8 = d8.get("reply", "")
    m8 = d8.get("model_used")
    has_diff_results = "3x^2 + 4x - 5" in r8 or "3*x**2 + 4*x - 5" in r8
    has_diff4 = "34x - 33" in r8 or "34*x - 33" in r8
    has_int = "x^6" in r8 or "x**6" in r8
    has_sympy = "sympy" in r8.lower()
    passed8 = bool(has_diff_results and has_diff4 and has_int and has_sympy and "gemma" in m8.lower())
    results.append(("8. Solve 5 Math PNGs with SymPy", passed8, f"Model: {m8}, Exact solutions: {has_diff_results and has_int}"))

    # 9. generate pdf,dox,csv,excel,and check the output as well
    print("\n=======================================================")
    print("TEST 9: 'generate pdf,dox,csv,excel,and check the output as well'")
    d9 = send_chat("generate pdf,dox,csv,excel,and check the output as well")
    r9 = d9.get("reply", "")
    m9 = d9.get("model_used")
    gen_dir = os.path.join(WORKSPACE_DIR, "generated")
    gen_files = os.listdir(gen_dir) if os.path.isdir(gen_dir) else []
    has_pdf = any(f.endswith(".pdf") for f in gen_files)
    has_docx = any(f.endswith(".docx") for f in gen_files)
    has_xlsx = any(f.endswith(".xlsx") for f in gen_files)
    has_csv = any(f.endswith(".csv") for f in gen_files)
    passed9 = bool(has_pdf and has_docx and has_xlsx and has_csv and "mistral" in m9.lower())
    results.append(("9. Generate 4 Document Formats", passed9, f"Model: {m9}, Formats: PDF={has_pdf}, DOCX={has_docx}, XLSX={has_xlsx}, CSV={has_csv}"))

    # 10. Direct Model Inquiry
    print("\n=======================================================")
    print("TEST 10: 'which model are you using?'")
    d10 = send_chat("which model are you using?")
    r10 = d10.get("reply", "")
    m10 = d10.get("model_used")
    has_router = "fluid model router" in r10.lower() or "fluid" in r10.lower()
    passed10 = bool(has_router and m10)
    results.append(("10. Direct Model Inquiry", passed10, f"Model: {m10}, Explains Fluid Router: {has_router}"))

    # 11. Who are you
    print("\n=======================================================")
    print("TEST 11: 'who are you'")
    d11 = send_chat("who are you")
    r11 = d11.get("reply", "")
    m11 = d11.get("model_used")
    passed11 = bool("sanctum" in r11.lower())
    results.append(("11. Agent Identity 'who are you'", passed11, f"Model: {m11}, Reply: {r11[:60]}"))

    # 12. Calculate 45 * 12 + sqrt(256)
    print("\n=======================================================")
    print("TEST 12: 'calculate 45 * 12 + sqrt(256)'")
    d12 = send_chat("calculate 45 * 12 + sqrt(256)")
    r12 = d12.get("reply", "")
    m12 = d12.get("model_used")
    has_556 = "556" in r12
    passed12 = bool(has_556)
    results.append(("12. Arithmetic Calculation (556)", passed12, f"Model: {m12}, Calculated 556: {has_556}"))

    # 13. Query PowerPoint Presentation
    print("\n=======================================================")
    print("TEST 13: 'what is bloodlink pptx about'")
    d13 = send_chat("what is bloodlink pptx about")
    r13 = d13.get("reply", "")
    m13 = d13.get("model_used")
    has_bloodlink = any(k in r13.lower() for k in ["blood", "donor", "donation", "bloodlink", "codealchem"])
    passed13 = bool(has_bloodlink)
    results.append(("13. PPTX Document Intelligence", passed13, f"Model: {m13}, BloodLink themes extracted: {has_bloodlink}"))

    # 14. History Badges on all assistant turns
    print("\n=======================================================")
    print("TEST 14: /api/history Badges & Metadata")
    h_resp = requests.get(f"{BASE_URL}/api/history")
    hist = h_resp.json().get("history", [])
    assistant_msgs = [m for m in hist if m.get("role") == "assistant"]
    all_have_badges = True
    for i, m in enumerate(assistant_msgs):
        has_m = bool(m.get("model"))
        has_d = bool(m.get("duration"))
        if not (has_m and has_d):
            all_have_badges = False
    passed14 = bool(all_have_badges and len(assistant_msgs) >= 13)
    results.append(("14. History Model & Duration Badges", passed14, f"All {len(assistant_msgs)} assistant turns badged: {all_have_badges}"))

    # Final Summary Report
    print("\n=======================================================")
    print("EXTENDED JURY READINESS EVALUATION REPORT:")
    all_ok = True
    for title, passed, note in results:
        status = "PASSED [OK]" if passed else "FAILED [FAIL]"
        if not passed:
            all_ok = False
        print(f"{status:15} | {title:<35} | {note}")
    print(f"\nOVERALL RESULT: {'100% READY FOR JURIES - ZERO FAILURES' if all_ok else 'ATTENTION NEEDED'}")
    return all_ok

if __name__ == "__main__":
    success = run_tests()
    exit(0 if success else 1)
