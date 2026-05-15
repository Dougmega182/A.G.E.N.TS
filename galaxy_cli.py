import requests
import time
import json
import os

# =========================
# CONFIG
# =========================

API_KEY = "gx_VEHLBDavwRUnwtrv78GRFy"
BASE_URL = "https://app.galaxy.ai/api/v1"
WORKFLOW_ID = "cmonfiheh0000kz04dpoe8cjz"

MEMORY_FILE = "conversation.json"
MAX_TURNS = 6

HEADERS = {
    "Authorization": f"Bearer {API_KEY}",
    "Content-Type": "application/json"
}

# =========================
# MEMORY
# =========================

def load_memory():
    if not os.path.exists(MEMORY_FILE):
        return []
    with open(MEMORY_FILE, "r") as f:
        return json.load(f)

def save_memory(memory):
    with open(MEMORY_FILE, "w") as f:
        json.dump(memory, f, indent=2)

def reset_memory():
    if os.path.exists(MEMORY_FILE):
        os.remove(MEMORY_FILE)
    return []

# =========================
# PROMPT BUILDER
# =========================

def build_prompt(memory, user_input):
    memory.append({"role": "user", "content": user_input})

    trimmed = memory[-MAX_TURNS*2:]

    prompt = ""
    for msg in trimmed:
        if msg["role"] == "user":
            prompt += f"USER: {msg['content']}\n"
        else:
            prompt += f"AI: {msg['content']}\n"

    return prompt, memory

# =========================
# API
# =========================

def start_run(prompt):
    payload = {
        "workflowId": WORKFLOW_ID,
        "graphInputOverrides": {
            "node_1777880629463_rsg0d00a2": {
                "prompt": f"CONTEXT:\n{prompt}\n\nTASK:\nProduce internal reasoning trace only.\n\nFORMAT:\n<thinking>...</thinking>"
            }
        }
    }
    res = requests.post(
        f"{BASE_URL}/runs",
        headers=HEADERS,
        json=payload
    )
    if res.status_code != 200:
        print("Start error:", res.text)
        return None
    return res.json().get("runId")


def poll_for_result(run_id):
    url = f"{BASE_URL}/runs/{run_id}?inDetails=true"

    while True:
        res = requests.get(url, headers=HEADERS)

        if res.status_code != 200:
            print("Poll error:", res.text)
            return None

        data = res.json()
        status = data.get("status")

        if status == "COMPLETED":
            return data

        elif status in ["FAILED", "CANCELED"]:
            print("Run failed:", data.get("error"))
            return None

        time.sleep(2)

# =========================
# OUTPUT EXTRACTION (CLEAN)
# =========================

def extract_output(run_data):
    try:
        for node in run_data.get("nodeRuns", []):
            if node.get("nodeType") == "claude_opus_4_6":
                return str(node["output"].get("output", ""))
    except:
        pass
    return ""

# =========================
# MAIN
# =========================

def main():
    print("===================================")
    print(" Galaxy CLI — CLEAN MODE")
    print("===================================")
    print("Commands: /reset, /exit\n")

    memory = load_memory()

    while True:
        user_input = input("> ")

        if user_input.lower() == "/exit":
            break

        if user_input.lower() == "/reset":
            memory = reset_memory()
            print("[memory cleared]\n")
            continue

        prompt, memory = build_prompt(memory, user_input)

        run_id = start_run(prompt)

        if not run_id:
            continue

        print("[running...]")

        run_data = poll_for_result(run_id)

        if not run_data:
            continue

        output = extract_output(run_data)

        # No need to extract anymore — already clean
        print("\n" + output + "\n")

        memory.append({"role": "assistant", "content": output})
        save_memory(memory)


if __name__ == "__main__":
    main()