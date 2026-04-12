import os
import re

def parse_markdown_table(content):
    """Simple parser for the Field/Detail metadata table at the top of AGENTS docs."""
    data = {}
    lines = content.split('\n')
    for line in lines:
        if line.startswith('| **') or line.startswith('|**'):
            # Match | **Key** | Value |
            match = re.search(r'\|\s*\*\*([^*]+)\*\*\s*\|\s*([^|]+)\s*\|', line)
            if match:
                key = match.group(1).strip()
                val = match.group(2).strip()
                data[key] = val
    return data

def validate_system():
    base_dir = "."
    reg_path = os.path.join(base_dir, "Governance Layer", "registers", "AGENTS-DOC-REG-001.md")
    
    print("=" * 60)
    print("  A.G.E.N.T.S. MARKDOWN ARCHITECTURE VALIDATION")
    print("=" * 60)

    if not os.path.exists(reg_path):
        print(f"[CRITICAL FAIL] Master Register not found at {reg_path}")
        return

    with open(reg_path, 'r', encoding='utf-8') as f:
        lines = f.readlines()

    docs_to_check = []
    for line in lines:
        if any(line.startswith(f"| {prefix}") for prefix in ["AGENTS-", "SEC-", "HR-", "GOV-", "AGT-"]):
            parts = [p.strip() for p in line.split('|')[1:-1]]
            if len(parts) >= 9:
                docs_to_check.append({
                    'id': parts[0],
                    'title': parts[1],
                    'status': parts[3],
                    'version': parts[4],
                    'classification': parts[7],
                    'location': parts[8]
                })

    print(f"\n--- SCRAPING MASTER REGISTER ({len(docs_to_check)} ENTRIES) ---\n")

    pass_count = 0
    fail_count = 0

    for doc in docs_to_check:
        full_path = os.path.join(base_dir, doc['location'])
        if not os.path.exists(full_path):
            print(f"  [MISSING] {doc['id']:18} | Location: {doc['location']}")
            fail_count += 1
            continue

        try:
            with open(full_path, 'r', encoding='utf-8-sig') as f:
                content = f.read()
            
            meta = parse_markdown_table(content)
            
            # Validation Logic
            mismatches = []
            if meta.get('Document ID') != doc['id']:
                mismatches.append(f"ID ({meta.get('Document ID')} vs {doc['id']})")
            if meta.get('Status') != doc['status']:
                mismatches.append(f"Status ({meta.get('Status')} vs {doc['status']})")
            if meta.get('Version') != doc['version']:
                mismatches.append(f"Version ({meta.get('Version')} vs {doc['version']})")
            
            # Safe print to avoid charmap errors on Windows terminals
            clean_title = doc['title'].encode('ascii', 'ignore').decode('ascii')[:40]
            if not mismatches:
                print(f"  [OK]      {doc['id']:18} | {clean_title}")
                pass_count += 1
            else:
                mismatch_str = ', '.join(mismatches).encode('ascii', 'ignore').decode('ascii')
                print(f"  [MISMATCH] {doc['id']:18} | {mismatch_str}")
                fail_count += 1
                
        except Exception as e:
            print(f"  [ERROR]    {doc['id']:18} | {str(e)}")
            fail_count += 1

    print("\n" + "=" * 60)
    print(f"  VALIDATION SUMMARY: {pass_count} PASSED, {fail_count} FAILED")
    if fail_count == 0:
        print("  ALL SYSTEMS NOMINAL - ARCHITECTURE 100% COMPLIANT")
    else:
        print("  WARNING: SYSTEM DEVIATIONS DETECTED")
    print("=" * 60)

if __name__ == "__main__":
    validate_system()
