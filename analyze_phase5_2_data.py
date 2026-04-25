import json
from pathlib import Path
from collections import Counter

EVENTS_LOG_PATH = Path(__file__).parent / "Agent logs" / "events.log.jsonl"

def analyze_cache_performance():
    if not EVENTS_LOG_PATH.exists():
        print(f"❌ ERROR: Event log not found at {EVENTS_LOG_PATH}")
        return

    cache_hits = 0
    cache_misses = 0
    bypass_reasons = Counter()
    miss_clusters = Counter()

    with open(EVENTS_LOG_PATH, "r", encoding="utf-8") as f:
        for line in f:
            try:
                event = json.loads(line)
                event_type = event.get("type")
                metadata = event.get("metadata", {})

                if event_type == "CACHE_HIT":
                    cache_hits += 1
                elif event_type == "CACHE_MISS":
                    cache_misses += 1
                    # Assuming normalized_issue is logged in miss events
                    if "normalized_issue" in metadata:
                        miss_clusters[metadata["normalized_issue"]] += 1
                elif event_type == "CACHE_BYPASS":
                    reason = metadata.get("reason", "unknown")
                    bypass_reasons[reason] += 1
            except json.JSONDecodeError:
                continue

    total_lookups = cache_hits + cache_misses
    hit_rate = (cache_hits / total_lookups) * 100 if total_lookups > 0 else 0

    print("=" * 50)
    print("      PHASE 5.2 MEASUREMENT ANALYSIS")
    print("=" * 50)

    print("\n--- 1. CACHE HIT RATE ---")
    print(f"  - Total Lookups: {total_lookups}")
    print(f"  - Cache Hits:    {cache_hits}")
    print(f"  - Cache Misses:  {cache_misses}")
    print(f"  - Hit Rate:      {hit_rate:.2f}%")

    if hit_rate < 10:
        print("  - ANALYSIS: Hit rate is below the 10% 'healthy' threshold. Normalization may be too strict or inputs too unique.")
    elif 10 <= hit_rate <= 30:
        print("  - ANALYSIS: Hit rate is in the healthy 10-30% range for a Layer 1 cache.")
    else:
        print("  - ANALYSIS: Hit rate is strong (>30%). The cache is providing significant value.")


    print("\n--- 2. CACHE BYPASS DISTRIBUTION ---")
    if not bypass_reasons:
        print("  - No bypass events recorded.")
    else:
        for reason, count in bypass_reasons.most_common():
            print(f"  - {reason}: {count} times")

    print("\n--- 3. TOP CACHE MISS CLUSTERS ---")
    if not miss_clusters:
        print("  - No miss events with clustering data recorded.")
    else:
        print("  (These are the 'normalized_issue' forms that are repeatedly missed)")
        for issue, count in miss_clusters.most_common(5):
            print(f"  - (x{count}) {issue}")

    print("\n" + "=" * 50)
    print("ANALYSIS COMPLETE")
    print("=" * 50)


if __name__ == "__main__":
    analyze_cache_performance()
