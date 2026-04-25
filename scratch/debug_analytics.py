import json
from collections import Counter
import re

LOG_FILE = "Agent logs/events.log.jsonl"

def normalize_v1(text):
    if not text: return ""
    text = text.lower().strip()
    text = re.sub(r'[^\w\s]', '', text)
    words = text.split()
    # Remove 's' at end of words longer than 3 chars
    words = [w[:-1] if w.endswith('s') and len(w) > 3 else w for w in words]
    return " ".join(words)

def analyze():
    miss_issues = []
    with open(LOG_FILE, "r") as f:
        for line in f:
            try:
                event = json.loads(line)
                if event.get("type") == "CACHE_MISS":
                    trace_id = event.get("trace_id")
                    # We need to find the LOOP_STARTED for this trace
                    pass
            except: continue
    
    # Actually, let's just extract all LOOP_STARTED first
    trace_to_issue = {}
    trace_to_status = {}
    with open(LOG_FILE, "r") as f:
        for line in f:
            try:
                event = json.loads(line)
                etype = event.get("type")
                tid = event.get("trace_id")
                if etype == "LOOP_STARTED":
                    inp = event.get("metadata", {}).get("input", "")
                    if "Variation:" in inp:
                        trace_to_issue[tid] = inp.split(",")[-1].strip()
                elif etype in ["CACHE_HIT", "CACHE_MISS", "CACHE_BYPASS"]:
                    trace_to_status[tid] = etype
            except: continue
            
    miss_issues = [issue for tid, issue in trace_to_issue.items() if trace_to_status.get(tid) == "CACHE_MISS"]
    
    print(f"Total Misses found with issue text: {len(miss_issues)}")
    
    print("\n=== RAW MISSES (Top 20) ===")
    for issue, count in Counter(miss_issues).most_common(20):
        print(f" - {count}x: {issue}")

    print("\n=== THEORETICAL NORMALIZATION (STRICT+) COLLISIONS ===")
    norm_map = {}
    for issue in miss_issues:
        n = normalize_v1(issue)
        if n not in norm_map: norm_map[n] = []
        norm_map[n].append(issue)
        
    for n, issues in norm_map.items():
        if len(issues) > 1:
            print(f" - Normalized: '{n}' ({len(issues)} occurrences)")
            for i in set(issues):
                print(f"   * {i}")

if __name__ == "__main__":
    analyze()
