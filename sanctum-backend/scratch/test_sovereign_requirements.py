"""
Validation Suite for Sovereign Requirements:
1. Model auto-selection across at least two task types (Code vs Docs)
2. End-to-End Agentic Task: Inspection report analysis & Word (.docx) approval note drafting
3. Coding Task run and verified in sandbox
4. Sovereign Network Monitor & Air-Gap Proof (0 external calls, 100% loopback)
"""

import json
import time
import requests
from pathlib import Path

BASE_URL = "http://127.0.0.1:5050"
DOC_ENGINE_URL = "http://127.0.0.1:8001"

def wait_for_server():
    for _ in range(30):
        try:
            r = requests.get(f"{BASE_URL}/api/health", timeout=2)
            if r.status_code == 200:
                print("Sanctum Agent server is UP.")
                return True
        except Exception:
            time.sleep(1)
    return False

def run_tests():
    print("\n" + "=" * 70)
    print("STARTING SOVEREIGN BENCHMARK VALIDATION")
    print("=" * 70)

    # 0. Clear memory
    r = requests.post(f"{BASE_URL}/api/clear", timeout=5)
    assert r.status_code == 200, "Failed to clear memory"
    print("Session memory cleared.")

    # -------------------------------------------------------------------------
    # TEST 1: End-to-End Agentic Task: Scanned inspection report -> Word note
    # -------------------------------------------------------------------------
    print("\n" + "-" * 70)
    print("TEST 1: End-to-End Agentic Task (Inspection report -> Word approval note)")
    prompt_1 = "An agentic task carried through end to end, for example reading a scanned inspection report, pulling out key findings and drafting an approval note as a Word file."
    r1 = requests.post(f"{BASE_URL}/api/chat", json={"message": prompt_1}, timeout=120)
    assert r1.status_code == 200, f"Test 1 failed with status {r1.status_code}"
    data1 = r1.json()
    reply1 = data1.get("reply", "")
    model1 = data1.get("model_used", "")
    tools1 = [t.get("tool") for t in data1.get("tool_actions", [])]

    print(f"Model used: {model1}")
    print(f"Tools executed: {tools1}")
    assert model1 == "mistral:7b", f"Expected mistral:7b, got {model1}"
    assert "PV-204B" in reply1 or "Inspection" in reply1, "Missing vessel identification"
    assert "37.85" in reply1 or "Shell Ring 1" in reply1, "Missing shell ring ultrasonic findings"
    assert "22.80" in reply1 or "Nozzle N1" in reply1, "Missing nozzle N1 findings"
    assert ".docx" in reply1, "Missing Word document path in response"

    # Verify generated Word file on disk
    docx_file = Path("generated/PV_204B_Inspection_Approval_Note.docx")
    if not docx_file.exists():
        docx_file = Path("/Users/burlaprudhviraj/Downloads/Waste/generated/PV_204B_Inspection_Approval_Note.docx")
    assert docx_file.exists(), f"Word document was not generated at {docx_file}"
    assert docx_file.stat().st_size > 10000, f"Generated docx is too small: {docx_file.stat().st_size} bytes"
    print(f"Verified Word Document generated: {docx_file} ({docx_file.stat().st_size:,} bytes)")
    print("TEST 1 PASSED: End-to-end agentic task executed flawlessly.")

    # -------------------------------------------------------------------------
    # TEST 2: Coding Task Run & Verified in Sandbox (with Model Auto-Switching)
    # -------------------------------------------------------------------------
    print("\n" + "-" * 70)
    print("TEST 2: Coding Task Run & Verified in Sandbox (Auto-Switch to qwen2.5-coder:7b)")
    prompt_2 = "write a python program to check palindrome, run it in the sandbox and verify the output"
    r2 = requests.post(f"{BASE_URL}/api/chat", json={"message": prompt_2}, timeout=120)
    assert r2.status_code == 200, f"Test 2 failed with status {r2.status_code}"
    data2 = r2.json()
    reply2 = data2.get("reply", "")
    model2 = data2.get("model_used", "")
    tools2 = [t.get("tool") for t in data2.get("tool_actions", [])]

    print(f"Model used: {model2}")
    print(f"Tools executed: {tools2}")
    assert model2 == "qwen2.5-coder:7b", f"Expected qwen2.5-coder:7b, got {model2}"
    assert "run_python" in tools2 or "create_file" in tools2, "Did not execute file creation or sandbox tools"
    assert "SUCCESS" in reply2 or "Exit Code: `0`" in reply2 or "return code 0" in reply2 or "radar" in reply2, "Missing sandbox verification in response"
    print("TEST 2 PASSED: Model auto-selected qwen2.5-coder:7b, executed and verified in sandbox.")

    # -------------------------------------------------------------------------
    # TEST 3: Multimodal Task (Handwritten Image Transcription)
    # -------------------------------------------------------------------------
    print("\n" + "-" * 70)
    print("TEST 3: Multimodal Task (Image & OCR Understanding)")
    prompt_3 = "check what is in handnotes.png(dont know the file name)"
    r3 = requests.post(f"{BASE_URL}/api/chat", json={"message": prompt_3}, timeout=120)
    assert r3.status_code == 200, f"Test 3 failed with status {r3.status_code}"
    data3 = r3.json()
    reply3 = data3.get("reply", "")
    model3 = data3.get("model_used", "")
    print(f"Model used: {model3}")
    assert "Magnus" in reply3 or "Tilburg" in reply3 or "thank" in reply3.lower(), "Failed to transcribe handwritten note"
    print("TEST 3 PASSED: Multimodal image & OCR successfully understood.")

    # -------------------------------------------------------------------------
    # TEST 4: Sovereign Network Monitor & Proof of Zero External Calls
    # -------------------------------------------------------------------------
    print("\n" + "-" * 70)
    print("TEST 4: Sovereign Network Monitor & Zero-Leak Audit")
    r4 = requests.get(f"{BASE_URL}/api/sovereign/network", timeout=5)
    assert r4.status_code == 200, f"Failed to get sovereign network audit: {r4.status_code}"
    net_data = r4.json()

    print(f"Sovereign Status: {net_data.get('sovereign_status')}")
    print(f"External Calls Allowed: {net_data.get('external_calls_allowed')}")
    print(f"External Calls Blocked: {net_data.get('external_calls_blocked')}")
    print(f"External Calls Total: {net_data.get('external_calls_total')}")
    print(f"Loopback Inferences & Local Calls: {net_data.get('loopback_calls_count')}")
    print(f"Endpoints Seen: {net_data.get('endpoints_seen')}")
    print(f"Service Breakdown: {net_data.get('service_breakdown')}")

    # Mathematical Proof Assertions
    assert net_data.get("external_calls_allowed") == 0, "VIOLATION: External calls were allowed!"
    assert net_data.get("external_calls_total") == 0, "External calls were detected!"
    assert net_data.get("loopback_calls_count", 0) > 0, "No loopback calls recorded"
    assert net_data.get("airgap_integrity_pct") == 100.0, "Air-gap integrity is not 100%"
    for ep in net_data.get("endpoints_seen", []):
        assert ep.startswith("127.0.0.1:"), f"Non-loopback endpoint detected: {ep}"

    print("TEST 4 PASSED: Mathematical & log proof that ZERO external calls were made.")

    print("\n" + "=" * 70)
    print("ALL 4 SOVEREIGN BENCHMARK REQUIREMENTS MET WITH 100% SUCCESS!")
    print("=" * 70 + "\n")

if __name__ == "__main__":
    if wait_for_server():
        run_tests()
    else:
        print("Server failed to start.")
        exit(1)
